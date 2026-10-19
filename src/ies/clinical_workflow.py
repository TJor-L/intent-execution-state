"""Private W001 output boundary; original validation and test outcomes stay unprojected."""

import os
import re

from ies.clinical_baseline import ClinicalBaselineError
from ies.io import sha256, write_json
from ies.workflow_artifacts import load_workflow_training, verify_bindings
from ies.workflow_cv import MODE, load_workflow_config, workflow_cross_validation


def run_clinical_workflow(
    cohort_dir,
    history_dir,
    config_path,
    output_dir,
    cohort_digest,
    history_digest,
    config_digest,
    source_commit,
):
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or any(output_dir.iterdir()):
        raise ClinicalBaselineError("invalid_workflow_output")
    config, digest = load_workflow_config(config_path)
    if digest != config_digest:
        raise ClinicalBaselineError("workflow_config_changed")
    cohort, grouped, bindings = load_workflow_training(
        cohort_dir,
        history_dir,
        cohort_digest,
        history_digest,
    )
    report, models = workflow_cross_validation(
        cohort, grouped, config, data_class="restricted_clinical"
    )
    verify_bindings(bindings + [(config_path, config_digest)])
    artifacts = {"workflow_report.json": report, "models.json": models, "config.json": config}
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
        os.chmod(output_dir / name, 0o600)
    manifest = {
        "schema_version": 1,
        "mode": MODE,
        "status": "complete",
        "data_class": "restricted_clinical",
        "source_commit": source_commit,
        "cohort_manifest_sha256": cohort_digest,
        "history_manifest_sha256": history_digest,
        "config_sha256": config_digest,
        "evaluation_scope": config["evaluation_scope"],
        "validation_split_evaluated": False,
        "test_split_evaluated": False,
        "raw_source_scan": False,
        "original_splits_changed": False,
        "gpu_used": False,
        "prediction_rows_persisted": False,
        "artifacts_sha256": {name: sha256(output_dir / name) for name in artifacts},
    }
    write_json(output_dir / "manifest.json", manifest)
    os.chmod(output_dir / "manifest.json", 0o600)
    return manifest
