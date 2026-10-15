"""Slurm-only execution boundary for the private clinical intercept baseline."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from ies.clinical_baseline import ClinicalBaselineError, load_baseline_config
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json


def run_baseline(cohort_dir: Path, config_path: Path, output_dir: Path) -> dict:
    verify_execution_context()
    if not os.environ.get("SLURM_JOB_ID", "").isdigit():
        raise ClinicalBaselineError("baseline_requires_slurm")
    _, config_digest = load_baseline_config(config_path)
    cohort_manifest_digest = sha256(cohort_dir / "manifest.json")
    if (
        os.environ.get("IES_BASELINE_CONFIG_SHA256") != config_digest
        or os.environ.get("IES_COHORT_MANIFEST_SHA256") != cohort_manifest_digest
    ):
        raise ClinicalBaselineError("baseline_inputs_changed")
    output = output_dir.resolve()
    cohort = cohort_dir.resolve()
    if (
        not output_dir.is_absolute()
        or not output.is_relative_to(Path("/scratch/tliu7"))
        or output.is_relative_to(ROOT)
        or output.is_relative_to(cohort)
        or cohort.is_relative_to(output)
    ):
        raise ClinicalBaselineError("invalid_baseline_output")
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        environment = dict(os.environ)
        environment.update(
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
                    "ies.clinical_baseline_worker",
                    str(cohort),
                    str(config_path.resolve()),
                    str(output),
                    config_digest,
                    cohort_manifest_digest,
                ],
                timeout=1200,
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
            return {"mode": "clinical_intercept_baseline", "status": "failed"}
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "complete":
            raise ClinicalBaselineError("invalid_baseline_manifest")
        return {"mode": manifest["mode"], "status": "complete"}
    finally:
        os.umask(old_umask)
