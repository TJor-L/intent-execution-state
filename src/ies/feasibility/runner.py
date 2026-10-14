"""Safe public entry points. Planning reads configuration only; execution is Slurm-only."""

import json
import os
import re
import signal
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from ies.feasibility.contract import ROOT, FeasibilityError, load_mapping, load_mapping_snapshot
from ies.io import write_json

LIMIT_NAMES = ("files", "directories", "entries", "rows", "keys", "runtime", "cpu", "memory")


def plan_feasibility(path: Path) -> dict:
    mapping = load_mapping(path)
    return {
        "mode": "bounded_feasibility",
        "submitted": False,
        "limits": asdict(mapping.limits),
        "laboratory_features_enabled": False,
    }


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


def run_feasibility(path: Path, output_dir: Path) -> dict:
    verify_execution_context()
    mapping, digest = load_mapping_snapshot(path)
    expected = os.environ.get("IES_MAPPING_SHA256")
    if expected and expected != digest:
        raise FeasibilityError("mapping_changed")
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
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.feasibility.worker",
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
