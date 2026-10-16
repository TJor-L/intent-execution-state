"""Slurm-only boundary for matched private history models."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from ies.clinical_baseline import ClinicalBaselineError
from ies.clinical_history_models import load_history_model_config
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json


def run_history_models(
    cohort_dir: Path,
    history_dir: Path,
    config_path: Path,
    output_dir: Path,
) -> dict:
    verify_execution_context()
    if not os.environ.get("SLURM_JOB_ID", "").isdigit():
        raise ClinicalBaselineError("history_models_require_slurm")
    _, config_digest = load_history_model_config(config_path)
    cohort_digest = sha256(cohort_dir / "manifest.json")
    history_digest = sha256(history_dir / "manifest.json")
    if (
        os.environ.get("IES_HISTORY_MODEL_CONFIG_SHA256") != config_digest
        or os.environ.get("IES_COHORT_MANIFEST_SHA256") != cohort_digest
        or os.environ.get("IES_HISTORY_MANIFEST_SHA256") != history_digest
    ):
        raise ClinicalBaselineError("history_model_inputs_changed")
    output = output_dir.resolve()
    sources = (cohort_dir.resolve(), history_dir.resolve())
    if not output_dir.is_absolute() or not output.is_relative_to(Path("/scratch/tliu7")):
        raise ClinicalBaselineError("invalid_history_model_output")
    if output.is_relative_to(ROOT) or any(
        output.is_relative_to(source) or source.is_relative_to(output) for source in sources
    ):
        raise ClinicalBaselineError("invalid_history_model_output")
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
                    "ies.clinical_history_models_worker",
                    str(cohort_dir.resolve()),
                    str(history_dir.resolve()),
                    str(config_path.resolve()),
                    str(output),
                    config_digest,
                    history_digest,
                    os.environ.get("IES_EXPECTED_COMMIT", ""),
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
            return {"mode": "clinical_matched_history_models", "status": "failed"}
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "complete":
            raise ClinicalBaselineError("invalid_history_model_manifest")
        return {"mode": manifest["mode"], "status": "complete"}
    finally:
        os.umask(old_umask)
