"""Fail-closed Slurm execution for the private training-clock audit."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from ies.clinical_baseline import ClinicalBaselineError, _verify_artifact_directory
from ies.clock_audit import MODE
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json


def run_clock_audit(cohort_dir: Path, history_dir: Path, output_dir: Path) -> dict:
    verify_execution_context()
    cohort = _verify_artifact_directory(cohort_dir, "invalid_clock_audit_cohort")
    history = _verify_artifact_directory(history_dir, "invalid_clock_audit_history")
    output = _verify_artifact_directory(output_dir, "invalid_clock_audit_output")
    if any(
        output.is_relative_to(source) or source.is_relative_to(output)
        for source in (cohort, history)
    ):
        raise ClinicalBaselineError("invalid_clock_audit_output")
    cohort_digest, history_digest = (
        os.environ.get(name, "")
        for name in ("IES_COHORT_MANIFEST_SHA256", "IES_HISTORY_MANIFEST_SHA256")
    )
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        environment = dict(
            os.environ,
            PYTHONFAULTHANDLER="0",
            OMP_NUM_THREADS="2",
            OPENBLAS_NUM_THREADS="2",
            MKL_NUM_THREADS="2",
        )
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.clock_audit_worker",
                    str(cohort),
                    str(history),
                    str(output),
                    cohort_digest,
                    history_digest,
                    os.environ.get("IES_EXPECTED_COMMIT", ""),
                ],
                timeout=300,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if completed.returncode:
                limit = {-signal.SIGXCPU: "cpu", 72: "memory"}.get(completed.returncode)
                status = "limited" if limit else "failed"
                write_json(output / "failure.json", {"status": status, "limit_reached": limit})
                return {"mode": MODE, "status": status}
        except subprocess.TimeoutExpired:
            write_json(output / "failure.json", {"status": "limited", "limit_reached": "runtime"})
            return {"mode": MODE, "status": "limited"}
        manifest = json.loads((output / "manifest.json").read_bytes())
        if (
            manifest.get("status") != "complete"
            or manifest.get("mode") != MODE
            or manifest.get("data_class") != "restricted_aggregate"
            or manifest.get("source_commit") != os.environ.get("IES_EXPECTED_COMMIT")
            or manifest.get("cohort_manifest_sha256") != cohort_digest
            or manifest.get("history_manifest_sha256") != history_digest
            or manifest.get("artifacts_sha256", {}).get("clock_report.json")
            != sha256(output / "clock_report.json")
        ):
            raise ClinicalBaselineError("invalid_clock_audit_result")
        # No private counts, diagnostic conclusions, fields or paths on stdout.
        return {"mode": MODE, "status": "complete"}
    finally:
        os.umask(old_umask)
