"""Slurm-only boundary for private dual-clock history extraction."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from ies.cohort_readiness.eligibility import load_eligibility_mapping
from ies.dual_clock_history import HistoryError, load_history_config
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json


def run_history(
    mapping_path: Path,
    config_path: Path,
    cohort_dir: Path,
    output_dir: Path,
) -> dict:
    verify_execution_context()
    if not os.environ.get("SLURM_JOB_ID", "").isdigit():
        raise HistoryError("history_requires_slurm")
    mapping, mapping_digest = load_eligibility_mapping(mapping_path)
    _, config_digest = load_history_config(config_path)
    cohort_digest = sha256(cohort_dir / "manifest.json")
    if (
        os.environ.get("IES_ELIGIBILITY_SHA256") != mapping_digest
        or os.environ.get("IES_HISTORY_CONFIG_SHA256") != config_digest
        or os.environ.get("IES_COHORT_MANIFEST_SHA256") != cohort_digest
    ):
        raise HistoryError("history_inputs_changed")
    output = output_dir.resolve()
    cohort = cohort_dir.resolve()
    if (
        not output_dir.is_absolute()
        or not output.is_relative_to(Path("/scratch/tliu7"))
        or output.is_relative_to(ROOT)
        or output.is_relative_to(cohort)
        or cohort.is_relative_to(output)
    ):
        raise HistoryError("invalid_history_output")
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        environment = dict(os.environ, PYTHONFAULTHANDLER="0")
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            environment[name] = str(mapping.limits.cpus)
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.dual_clock_history_worker",
                    str(mapping_path.resolve()),
                    str(config_path.resolve()),
                    str(cohort),
                    str(output),
                    mapping_digest,
                    cohort_digest,
                ],
                timeout=mapping.limits.runtime_seconds,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if completed.returncode:
                limit = {-signal.SIGXCPU: "cpu", 72: "memory"}.get(completed.returncode)
                write_json(
                    output / "failure.json",
                    {"status": "limited" if limit else "failed", "limit_reached": limit},
                )
        except subprocess.TimeoutExpired:
            write_json(output / "failure.json", {"status": "limited", "limit_reached": "runtime"})
        manifest_path = output / "manifest.json"
        if not manifest_path.exists():
            return {"mode": "dual_clock_history_extraction", "status": "failed"}
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "complete":
            raise HistoryError("invalid_history_manifest")
        return {"mode": manifest["mode"], "status": "complete"}
    finally:
        os.umask(old_umask)
