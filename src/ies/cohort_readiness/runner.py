"""Data-free plan and Slurm-only execution for aggregate cohort audits."""

import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from ies.cohort_readiness.contract import CohortAuditError, load_vocabulary_mapping
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import write_json


def plan_vocabulary_audit(path: Path) -> dict:
    mapping, _ = load_vocabulary_mapping(path)
    return {
        "mode": "frequency_prn_vocabulary",
        "submitted": False,
        "projected_columns": 2,
        "full_reviewed_snapshot_required": True,
        "row_persistence": False,
        "limits": asdict(mapping.limits),
    }


def _resource_report(limit: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "mode": "frequency_prn_vocabulary",
        "data_class": "restricted_aggregate",
        "status": "limited" if limit else "failed",
        "limit_reached": limit,
        "vocabulary": None,
        "complete_for_reviewed_snapshot": False,
        "row_persistence": False,
    }


def run_vocabulary_audit(path: Path, output_dir: Path) -> dict:
    verify_execution_context()
    mapping, digest = load_vocabulary_mapping(path)
    if os.environ.get("IES_COHORT_AUDIT_SHA256") != digest:
        raise CohortAuditError("cohort_audit_mapping_changed")
    output = output_dir.resolve()
    source = mapping.source.path.resolve()
    if (
        not output_dir.is_absolute()
        or output.is_relative_to(ROOT)
        or output.is_relative_to(source)
        or source.is_relative_to(output)
    ):
        raise CohortAuditError("invalid_cohort_audit_output")
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        report_path = output / "vocabulary_report.json"
        env = dict(os.environ)
        env["PYTHONFAULTHANDLER"] = "0"
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            env[name] = str(mapping.limits.cpus)
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.cohort_readiness.worker",
                    str(path.resolve()),
                    str(report_path),
                    digest,
                ],
                timeout=mapping.limits.runtime_seconds,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if completed.returncode:
                limit = {-signal.SIGXCPU: "cpu", 72: "memory"}.get(completed.returncode)
                write_json(report_path, _resource_report(limit))
        except subprocess.TimeoutExpired:
            write_json(report_path, _resource_report("runtime"))
        report = json.loads(report_path.read_text())
        if report.get("status") not in ("complete", "limited", "failed"):
            raise CohortAuditError("invalid_cohort_audit_report")
        return {"mode": "frequency_prn_vocabulary", "status": report["status"]}
    finally:
        os.umask(old_umask)
