"""R001 private output boundary; original W001 manifest fixes the artifact population."""

import json
import os
import re

from ies.clinical_baseline import ClinicalBaselineError, _verify_artifact_directory
from ies.io import sha256, write_json
from ies.selection_cv import MODE, load_config, paper_tables, run_selection_cv
from ies.workflow_artifacts import load_workflow_training, verify_bindings
from ies.workflow_cv import MODE as ORIGINAL_MODE
from ies.workflow_review import _read

ARTIFACTS = {
    "selection_report.json": 4 * 1024**2,
    "models.json": 64 * 1024**2,
    "config.json": 16384,
    "paper_tables.md": 4 * 1024**2,
}


def check_original(original, cohort_digest, history_digest, original_commit):
    expected = dict(
        mode=ORIGINAL_MODE,
        status="complete",
        data_class="restricted_clinical",
        source_commit=original_commit,
        cohort_manifest_sha256=cohort_digest,
        history_manifest_sha256=history_digest,
        validation_split_evaluated=False,
        test_split_evaluated=False,
        original_splits_changed=False,
        raw_source_scan=False,
    )
    if not isinstance(original, dict) or any(
        type(original.get(k)) is not type(v) or original[k] != v for k, v in expected.items()
    ):
        raise ClinicalBaselineError("selection_original_binding")


def run_clinical_selection(
    cohort_dir,
    history_dir,
    config_path,
    workflow_dir,
    output_dir,
    cohort_digest,
    history_digest,
    config_digest,
    workflow_digest,
    source_commit,
    original_commit,
):
    if not all(re.fullmatch(r"[0-9a-f]{40}", x) for x in (source_commit, original_commit)) or any(
        output_dir.iterdir()
    ):
        raise ClinicalBaselineError("invalid_selection_output")
    workflow = _verify_artifact_directory(workflow_dir, "invalid_selection_workflow")
    config, digest = load_config(config_path)
    if digest != config_digest or sha256(workflow / "manifest.json") != workflow_digest:
        raise ClinicalBaselineError("selection_input_changed")
    original = json.loads(_read(workflow / "manifest.json"))
    check_original(original, cohort_digest, history_digest, original_commit)
    # Old fitted models/metrics are deliberately not inputs to the new selection experiment.
    cohort, history, bindings = load_workflow_training(
        cohort_dir, history_dir, cohort_digest, history_digest
    )
    report, models = run_selection_cv(cohort, history, config, data_class="restricted_clinical")
    verify_bindings(
        bindings + [(config_path, config_digest), (workflow / "manifest.json", workflow_digest)]
    )
    for name, value in {
        "selection_report.json": report,
        "models.json": models,
        "config.json": config,
    }.items():
        write_json(output_dir / name, value)
    (output_dir / "paper_tables.md").write_text(paper_tables(report))
    for name, maximum in ARTIFACTS.items():
        os.chmod(output_dir / name, 0o600)
        if (output_dir / name).stat().st_size > maximum:
            raise ClinicalBaselineError("selection_output_limit")
    manifest = dict(
        schema_version=1,
        mode=MODE,
        status="complete",
        data_class="restricted_clinical",
        source_commit=source_commit,
        original_workflow_commit=original_commit,
        workflow_manifest_sha256=workflow_digest,
        cohort_manifest_sha256=cohort_digest,
        history_manifest_sha256=history_digest,
        config_sha256=config_digest,
        evaluation_scope=config["evaluation_scope"],
        validation_split_evaluated=False,
        test_split_evaluated=False,
        original_splits_changed=False,
        raw_source_scan=False,
        model_fitted=True,
        prediction_rows_persisted=False,
        gpu_used=False,
        artifacts_sha256={name: sha256(output_dir / name) for name in ARTIFACTS},
    )
    write_json(output_dir / "manifest.json", manifest)
    os.chmod(output_dir / "manifest.json", 0o600)
    return manifest
