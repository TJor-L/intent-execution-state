"""Slurm-only boundary for bounded private cohort extraction."""

import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from ies.cohort_readiness.eligibility import EligibilityError, load_eligibility_mapping
from ies.cohort_readiness.eligibility_runner import _protocol_thresholds
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import write_json

AUTHORIZED_OUTPUT_ROOT = Path("/scratch/tliu7")


def _validate_output(mapping, output_dir: Path) -> Path:
    output = output_dir.resolve()
    if (
        not output_dir.is_absolute()
        or not output.is_relative_to(AUTHORIZED_OUTPUT_ROOT)
        or output.is_relative_to(ROOT)
    ):
        raise EligibilityError("invalid_extraction_output")
    for source in (
        mapping.feasibility.orders,
        mapping.feasibility.administrations,
        mapping.feasibility.observations,
        mapping.patients,
        mapping.encounters,
    ):
        source_path = source.path.resolve()
        if output.is_relative_to(source_path) or source_path.is_relative_to(output):
            raise EligibilityError("invalid_extraction_output")
    return output


def run_extraction(path: Path, protocol_path: Path, output_dir: Path) -> dict:
    verify_execution_context()
    if not os.environ.get("SLURM_JOB_ID", "").isdigit():
        raise EligibilityError("extraction_requires_slurm")
    mapping, digest = load_eligibility_mapping(path)
    protocol_digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    if (
        os.environ.get("IES_ELIGIBILITY_SHA256") != digest
        or os.environ.get("IES_PROTOCOL_SHA256") != protocol_digest
    ):
        raise EligibilityError("extraction_inputs_changed")
    _protocol_thresholds(protocol_path)
    output = _validate_output(mapping, output_dir)
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        environment = dict(os.environ)
        environment["PYTHONFAULTHANDLER"] = "0"
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            environment[name] = str(mapping.limits.cpus)
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.cohort_readiness.extract_worker",
                    str(path.resolve()),
                    str(protocol_path.resolve()),
                    str(output),
                    digest,
                    protocol_digest,
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
            return {"mode": "bounded_phase0_cohort_extraction", "status": "failed"}
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "complete":
            raise EligibilityError("invalid_extraction_manifest")
        return {"mode": manifest["mode"], "status": "complete"}
    finally:
        os.umask(old_umask)
