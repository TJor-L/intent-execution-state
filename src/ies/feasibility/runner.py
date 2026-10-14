"""Safe public entry points. Planning reads configuration only; execution is Slurm-only."""

import json
import os
import re
import signal
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from ies.feasibility.access import load_access_snapshot, plan_access
from ies.feasibility.contract import (
    ROOT,
    FeasibilityError,
    Mapping,
    load_mapping_snapshot,
)
from ies.io import write_json

LIMIT_NAMES = (
    "files",
    "directories",
    "entries",
    "rows",
    "bytes",
    "keys",
    "runtime",
    "cpu",
    "memory",
)


def identity_budget(mapping: Mapping) -> dict:
    """Arithmetic upper bound for the current reader's three identity registries only."""
    source_count = len(mapping.sources)
    worst_case = source_count * mapping.limits.max_rows_per_source
    capacity = mapping.limits.max_keys
    return {
        "source_count": source_count,
        "worst_case_registry_keys": worst_case,
        "shared_key_capacity": capacity,
        "worst_case_key_shortfall": max(0, worst_case - capacity),
        "all_source_row_caps_fit": worst_case <= capacity,
        "balanced_rows_per_source_at_key_capacity": capacity // source_count,
    }


def plan_feasibility(path: Path, access_manifest: Path | None = None) -> dict:
    mapping, mapping_digest = load_mapping_snapshot(path)
    plan = {
        "mode": "bounded_feasibility",
        "submitted": False,
        "limits": asdict(mapping.limits),
        "identity_budget": identity_budget(mapping),
        "sampling": "independent_source_prefixes",
        "coherent_linkage_coverage_verified": False,
        "laboratory_features_enabled": False,
    }
    if access_manifest is not None:
        manifest, _ = load_access_snapshot(access_manifest, mapping, mapping_digest)
        plan["sampling"] = "coherent_manifest"
        plan["coherent_linkage_coverage_verified"] = True
        plan["access"] = plan_access(manifest)
    return plan


def verify_execution_context():
    if (
        os.environ.get("IES_EXECUTION_CONTEXT") != "ucsf"
        or sys.platform != "linux"
        or not re.fullmatch(r"\d+", os.environ.get("SLURM_JOB_ID", ""))
    ):
        raise FeasibilityError("authorized_slurm_context_required")
    expected = os.environ.get("IES_EXPECTED_COMMIT", "")
    if not re.fullmatch(r"[a-f0-9]{40}", expected):
        raise FeasibilityError("expected_commit_required")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
    ).strip()
    if head != expected or dirty:
        raise FeasibilityError("source_revision_changed")


def resource_report(limit: str | None = None) -> dict:
    return {
        "schema_version": 2,
        "mode": "bounded_feasibility",
        "data_class": "restricted_aggregate",
        "status": "limited" if limit else "failed",
        "counts": None,
        "limits_reached": {name: name == limit for name in LIMIT_NAMES},
    }


def run_feasibility(path: Path, output_dir: Path, access_manifest: Path | None = None) -> dict:
    verify_execution_context()
    mapping, digest = load_mapping_snapshot(path)
    expected = os.environ.get("IES_MAPPING_SHA256")
    if expected and expected != digest:
        raise FeasibilityError("mapping_changed")
    access_digest = None
    if access_manifest is not None:
        _, access_digest = load_access_snapshot(access_manifest, mapping, digest)
        expected_access = os.environ.get("IES_ACCESS_SHA256")
        if expected_access != access_digest:
            raise FeasibilityError("access_manifest_changed")
    output = output_dir.resolve()
    if not output_dir.is_absolute() or output.is_relative_to(ROOT):
        raise FeasibilityError("invalid_output_boundary")
    for source in mapping.sources:
        data = source.path.resolve()
        if output.is_relative_to(data) or data.is_relative_to(output):
            raise FeasibilityError("invalid_output_boundary")
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        report_path = output / "feasibility_report.json"
        env = dict(os.environ)
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            env[name] = str(mapping.limits.cpus)
        env["PYTHONFAULTHANDLER"] = "0"
        try:
            command = [
                sys.executable,
                "-m",
                "ies.feasibility.worker",
                str(path.resolve()),
                str(report_path),
                digest,
            ]
            if access_manifest is not None:
                command.extend([str(access_manifest.resolve()), access_digest])
            completed = subprocess.run(
                command,
                timeout=mapping.limits.runtime_seconds,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if completed.returncode != 0:
                limit = {71: "runtime", 72: "memory", -signal.SIGXCPU: "cpu"}.get(
                    completed.returncode
                )
                write_json(report_path, resource_report(limit))
        except subprocess.TimeoutExpired:
            write_json(report_path, resource_report("runtime"))
        report = json.loads(report_path.read_text())
        # Do not print any raw worker/config/exception content.
        if report.get("status") not in ("complete", "limited", "failed"):
            raise FeasibilityError("invalid_report")
        return {"mode": "bounded_feasibility", "status": report["status"]}
    finally:
        os.umask(old_umask)
