"""Slurm-only boundary for reviewed bounded clinical feature extraction."""

import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from ies.clinical_features import ClinicalFeatureError
from ies.cohort_readiness.eligibility import load_eligibility_mapping
from ies.cohort_readiness.eligibility_runner import _protocol_thresholds
from ies.feasibility.contract import ROOT
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json


def run_features(
    mapping_path: Path,
    protocol_path: Path,
    cohort_dir: Path,
    output_dir: Path,
) -> dict:
    verify_execution_context()
    if not os.environ.get("SLURM_JOB_ID", "").isdigit():
        raise ClinicalFeatureError("features_require_slurm")
    mapping, mapping_digest = load_eligibility_mapping(mapping_path)
    protocol_digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    cohort_manifest_digest = sha256(cohort_dir / "manifest.json")
    if (
        os.environ.get("IES_ELIGIBILITY_SHA256") != mapping_digest
        or os.environ.get("IES_PROTOCOL_SHA256") != protocol_digest
        or os.environ.get("IES_COHORT_MANIFEST_SHA256") != cohort_manifest_digest
    ):
        raise ClinicalFeatureError("feature_inputs_changed")
    _protocol_thresholds(protocol_path)
    output = output_dir.resolve()
    cohort = cohort_dir.resolve()
    if (
        not output_dir.is_absolute()
        or not output.is_relative_to(Path("/scratch/tliu7"))
        or output.is_relative_to(ROOT)
        or output.is_relative_to(cohort)
        or cohort.is_relative_to(output)
    ):
        raise ClinicalFeatureError("invalid_feature_output")
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
                    "ies.clinical_features_worker",
                    str(mapping_path.resolve()),
                    str(protocol_path.resolve()),
                    str(cohort),
                    str(output),
                    mapping_digest,
                    cohort_manifest_digest,
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
            return {"mode": "bounded_preindex_feature_extraction", "status": "failed"}
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") != "complete":
            raise ClinicalFeatureError("invalid_feature_manifest")
        return {"mode": manifest["mode"], "status": "complete"}
    finally:
        os.umask(old_umask)
