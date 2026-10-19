"""Bounded manifest discovery and scheduler monitoring; no clinical result export."""

import json
import os
import re
import subprocess
import time
from pathlib import Path

from ies.clinical_baseline import _verify_artifact_directory
from ies.clock_audit import MODE
from ies.io import sha256


class ClockAuditOpsError(ValueError):
    """Only fixed operational codes are safe for terminal output."""


def discover_clock_artifacts(
    output_root: Path, max_jobs: int = 1000, max_manifest_bytes: int = 16 * 1024**2
) -> tuple[Path, Path]:
    root = _verify_artifact_directory(output_root, "invalid_clock_audit_storage")
    jobs = root / "jobs"
    if jobs.is_symlink() or not jobs.is_dir():
        raise ClockAuditOpsError("artifact_discovery_unavailable_use_explicit_paths")
    cohorts, histories = {}, []
    manifest_bytes = 0
    with os.scandir(jobs) as entries:
        for count, entry in enumerate(entries, 1):
            if count > max_jobs:
                raise ClockAuditOpsError("artifact_discovery_limit_use_explicit_paths")
            if entry.is_symlink():
                raise ClockAuditOpsError("artifact_discovery_symlink")
            if not entry.is_dir(follow_symlinks=False):
                continue
            for name in ("cohort-extract", "dual-clock-history"):
                directory = Path(entry.path) / name
                path = directory / "manifest.json"
                if directory.is_symlink() or path.is_symlink():
                    raise ClockAuditOpsError("artifact_discovery_symlink")
                if not path.exists():
                    continue
                if not path.is_file() or path.stat().st_size > 1024**2:
                    raise ClockAuditOpsError("artifact_discovery_invalid_manifest")
                manifest_bytes += path.stat().st_size
                if manifest_bytes > max_manifest_bytes:
                    raise ClockAuditOpsError("artifact_discovery_limit_use_explicit_paths")
                value = json.loads(path.read_bytes())
                if not isinstance(value, dict):
                    raise ClockAuditOpsError("artifact_discovery_invalid_manifest")
                if (
                    value.get("status") != "complete"
                    or value.get("data_class") != "restricted_clinical"
                ):
                    continue
                if (
                    name == "cohort-extract"
                    and value.get("mode") == "bounded_phase0_cohort_extraction"
                ):
                    cohorts.setdefault(sha256(path), []).append(directory)
                elif (
                    name == "dual-clock-history"
                    and value.get("mode") == "dual_clock_history_extraction"
                ):
                    digest = value.get("cohort_manifest_sha256")
                    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                        raise ClockAuditOpsError("artifact_discovery_invalid_manifest")
                    histories.append((directory, digest))
    pairs = [
        (cohort, history) for history, digest in histories for cohort in cohorts.get(digest, [])
    ]
    if len(pairs) != 1:
        raise ClockAuditOpsError("artifact_discovery_not_unique_use_explicit_paths")
    return pairs[0]


def wait_for_clock_audit(
    job_id: str, run_dir: Path, commit: str, *, timeout_seconds=3600, poll_seconds=15
) -> dict:
    if not re.fullmatch(r"\d+", job_id):
        raise ClockAuditOpsError("invalid_job_id")
    deadline = time.monotonic() + timeout_seconds
    active = {
        "PENDING",
        "RUNNING",
        "CONFIGURING",
        "COMPLETING",
        "SUSPENDED",
        "REQUEUED",
        "REQUEUE_FED",
        "RESIZING",
    }
    while time.monotonic() < deadline:
        completed = subprocess.run(
            [
                "sacct",
                "--noheader",
                "--parsable2",
                "-j",
                job_id,
                "--format=JobIDRaw,State,ExitCode",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode:
            raise ClockAuditOpsError("scheduler_query_failed_job_not_resubmitted")
        matches = [
            line.split("|")
            for line in completed.stdout.splitlines()
            if line.split("|")[0] == job_id
        ]
        if len(matches) > 1:
            raise ClockAuditOpsError("scheduler_result_ambiguous")
        if matches:
            fields = matches[0]
            if len(fields) < 3 or not fields[1]:
                raise ClockAuditOpsError("scheduler_result_invalid")
            state = fields[1].split()[0].rstrip("+")
            if state == "COMPLETED":
                if fields[2] != "0:0":
                    raise ClockAuditOpsError("clock_audit_job_failed")
                output = run_dir / "clock-audit"
                path = output / "manifest.json"
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**2:
                    raise ClockAuditOpsError("clock_audit_result_missing")
                manifest = json.loads(path.read_bytes())
                report = output / "clock_report.json"
                if (
                    not isinstance(manifest, dict)
                    or manifest.get("mode") != MODE
                    or manifest.get("status") != "complete"
                    or manifest.get("source_commit") != commit
                    or manifest.get("data_class") != "restricted_aggregate"
                    or report.is_symlink()
                    or not report.is_file()
                    or report.stat().st_size > 1024**2
                    or manifest.get("artifacts_sha256", {}).get("clock_report.json")
                    != sha256(report)
                ):
                    raise ClockAuditOpsError("clock_audit_result_invalid")
                return {
                    "mode": MODE,
                    "job_id": job_id,
                    "status": "complete",
                    "private_review_required": True,
                }
            if state not in active:
                raise ClockAuditOpsError("clock_audit_job_failed_no_automatic_retry")
        time.sleep(poll_seconds)
    raise ClockAuditOpsError("monitor_timeout_job_not_cancelled_or_resubmitted")
