"""Clean-commit, bounded Slurm execution of the W001 training-only experiment."""

import json
import os
import signal
import subprocess
import sys

from ies.clinical_baseline import ClinicalBaselineError, _verify_artifact_directory
from ies.feasibility.runner import verify_execution_context
from ies.io import sha256, write_json
from ies.workflow_cv import MODE, load_workflow_config


def run_workflow(cohort_dir, history_dir, config_path, output_dir):
    verify_execution_context()
    cohort = _verify_artifact_directory(cohort_dir, "invalid_workflow_cohort")
    history = _verify_artifact_directory(history_dir, "invalid_workflow_history")
    output = _verify_artifact_directory(output_dir, "invalid_workflow_output")
    if any(output.is_relative_to(s) or s.is_relative_to(output) for s in (cohort, history)):
        raise ClinicalBaselineError("invalid_workflow_output")
    _, config_digest = load_workflow_config(config_path)
    cohort_digest = os.environ.get("IES_COHORT_MANIFEST_SHA256", "")
    history_digest = os.environ.get("IES_HISTORY_MANIFEST_SHA256", "")
    if (
        os.environ.get("IES_WORKFLOW_CONFIG_SHA256") != config_digest
        or sha256(cohort / "manifest.json") != cohort_digest
        or sha256(history / "manifest.json") != history_digest
    ):
        raise ClinicalBaselineError("workflow_inputs_changed")
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
                    "ies.workflow_worker",
                    str(cohort),
                    str(history),
                    str(config_path.resolve()),
                    str(output),
                    cohort_digest,
                    history_digest,
                    config_digest,
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
                status = "limited" if limit else "failed"
                write_json(output / "failure.json", {"status": status, "limit_reached": limit})
                return {"mode": MODE, "status": status}
        except subprocess.TimeoutExpired:
            write_json(output / "failure.json", {"status": "limited", "limit_reached": "runtime"})
            return {"mode": MODE, "status": "limited"}
        manifest = json.loads((output / "manifest.json").read_bytes())
        if (
            manifest.get("mode") != MODE
            or manifest.get("status") != "complete"
            or manifest.get("data_class") != "restricted_clinical"
            or manifest.get("source_commit") != os.environ.get("IES_EXPECTED_COMMIT")
            or manifest.get("cohort_manifest_sha256") != cohort_digest
            or manifest.get("history_manifest_sha256") != history_digest
            or manifest.get("config_sha256") != config_digest
            or manifest.get("validation_split_evaluated") is not False
            or manifest.get("test_split_evaluated") is not False
        ):
            raise ClinicalBaselineError("invalid_workflow_result")
        for name in ("workflow_report.json", "models.json", "config.json"):
            if manifest.get("artifacts_sha256", {}).get(name) != sha256(output / name):
                raise ClinicalBaselineError("invalid_workflow_result")
        return {"mode": MODE, "status": "complete"}
    finally:
        os.umask(old_umask)
