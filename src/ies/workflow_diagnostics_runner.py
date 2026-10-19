"""Bounded Slurm entry for replaying existing W001 folds without fitting."""

import json
import os
import signal
import subprocess
import sys

from ies.clinical_baseline import ClinicalBaselineError, _verify_artifact_directory
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json
from ies.workflow_cv import load_workflow_config
from ies.workflow_diagnostics import MODE


def run_diagnostics(cohort_dir, history_dir, config_path, workflow_dir, output_dir):
    verify_execution_context()
    inputs = [
        _verify_artifact_directory(p, "invalid_diagnostic_input")
        for p in (cohort_dir, history_dir, workflow_dir)
    ]
    output = _verify_artifact_directory(output_dir, "invalid_diagnostic_output")
    if any(output.is_relative_to(p) or p.is_relative_to(output) for p in inputs):
        raise ClinicalBaselineError("invalid_diagnostic_output")
    _, config_digest = load_workflow_config(config_path)
    cohort_digest, history_digest, workflow_digest = [
        os.environ.get(name, "")
        for name in (
            "IES_COHORT_MANIFEST_SHA256",
            "IES_HISTORY_MANIFEST_SHA256",
            "IES_WORKFLOW_MANIFEST_SHA256",
        )
    ]
    if config_digest != os.environ.get("IES_WORKFLOW_CONFIG_SHA256") or any(
        sha256(p / "manifest.json") != expected
        for p, expected in zip(
            inputs, (cohort_digest, history_digest, workflow_digest), strict=True
        )
    ):
        raise ClinicalBaselineError("diagnostic_input_changed")
    source_commit = os.environ.get("IES_EXPECTED_COMMIT", "")
    original_commit = os.environ.get("IES_ORIGINAL_WORKFLOW_COMMIT", "")
    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ies.workflow_diagnostics_worker",
                    str(inputs[0]),
                    str(inputs[1]),
                    str(config_path.resolve()),
                    str(inputs[2]),
                    str(output),
                    cohort_digest,
                    history_digest,
                    config_digest,
                    workflow_digest,
                    source_commit,
                    original_commit,
                ],
                env=dict(
                    os.environ,
                    PYTHONFAULTHANDLER="0",
                    OMP_NUM_THREADS="2",
                    OPENBLAS_NUM_THREADS="2",
                    MKL_NUM_THREADS="2",
                ),
                timeout=300,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode:
                limit = {-signal.SIGXCPU: "cpu", 72: "memory"}.get(result.returncode)
                status = "limited" if limit else "failed"
                write_json(output / "failure.json", dict(status=status, limit_reached=limit))
                return dict(mode=MODE, status=status)
        except subprocess.TimeoutExpired:
            write_json(output / "failure.json", dict(status="limited", limit_reached="runtime"))
            return dict(mode=MODE, status="limited")
        manifest = json.loads((output / "manifest.json").read_bytes())
        expected = dict(
            mode=MODE,
            status="complete",
            data_class="restricted_aggregate",
            source_commit=source_commit,
            original_workflow_commit=original_commit,
            workflow_manifest_sha256=workflow_digest,
            cohort_manifest_sha256=cohort_digest,
            history_manifest_sha256=history_digest,
            config_sha256=config_digest,
            model_fitted=False,
            source_replay_verified=True,
            validation_split_evaluated=False,
            test_split_evaluated=False,
        )
        if any(
            type(manifest.get(k)) is not type(v) or manifest[k] != v for k, v in expected.items()
        ) or manifest.get("artifacts_sha256", {}).get("diagnostic_report.json") != sha256(
            output / "diagnostic_report.json"
        ):
            raise ClinicalBaselineError("invalid_diagnostic_result")
        return dict(mode=MODE, status="complete")
    finally:
        os.umask(old_umask)
