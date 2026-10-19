"""Private frozen-fold diagnostic artifacts; never persist predictions or rows."""

import hashlib
import json
import os
import re

from ies.clinical_baseline import ClinicalBaselineError, _verify_artifact_directory
from ies.io import sha256, write_json
from ies.workflow_artifacts import load_workflow_training, verify_bindings
from ies.workflow_cv import MODE as ORIGINAL_MODE
from ies.workflow_cv import load_workflow_config
from ies.workflow_diagnostics import MODE, replay_diagnostics
from ies.workflow_review import _read, _summarize


def run_clinical_diagnostics(
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
        raise ClinicalBaselineError("invalid_diagnostic_output")
    workflow = _verify_artifact_directory(workflow_dir, "invalid_diagnostic_workflow")
    config, digest = load_workflow_config(config_path)
    if digest != config_digest or sha256(workflow / "manifest.json") != workflow_digest:
        raise ClinicalBaselineError("diagnostic_input_changed")
    original = json.loads(_read(workflow / "manifest.json"))
    if (
        original["mode"] != ORIGINAL_MODE
        or original["status"] != "complete"
        or original["data_class"] != "restricted_clinical"
        or original["source_commit"] != original_commit
        or original["cohort_manifest_sha256"] != cohort_digest
        or original["history_manifest_sha256"] != history_digest
        or original["config_sha256"] != config_digest
        or original["validation_split_evaluated"] is not False
        or original["test_split_evaluated"] is not False
        or original["original_splits_changed"] is not False
        or original["raw_source_scan"] is not False
    ):
        raise ClinicalBaselineError("diagnostic_original_binding")
    payloads = {}
    frozen_bindings = [(workflow / "manifest.json", workflow_digest), (config_path, config_digest)]
    for name, maximum in (
        ("workflow_report.json", 1024**2),
        ("config.json", 1024**2),
        ("models.json", 64 * 1024**2),
    ):
        content = _read(workflow / name, maximum)
        expected = original["artifacts_sha256"][name]
        if hashlib.sha256(content).hexdigest() != expected:
            raise ClinicalBaselineError("diagnostic_frozen_artifact_changed")
        payloads[name] = json.loads(content)
        frozen_bindings.append((workflow / name, expected))
    if payloads["config.json"] != config:
        raise ClinicalBaselineError("diagnostic_config_changed")
    _summarize(payloads["workflow_report.json"], config)
    cohort, history, bindings = load_workflow_training(
        cohort_dir, history_dir, cohort_digest, history_digest
    )
    report = replay_diagnostics(
        cohort,
        history,
        config,
        payloads["models.json"],
        payloads["workflow_report.json"],
        data_class="restricted_clinical",
    )
    verify_bindings(bindings + frozen_bindings)
    write_json(output_dir / "diagnostic_report.json", report)
    os.chmod(output_dir / "diagnostic_report.json", 0o600)
    manifest = dict(
        schema_version=1,
        mode=MODE,
        status="complete",
        data_class="restricted_aggregate",
        source_commit=source_commit,
        original_workflow_commit=original_commit,
        workflow_manifest_sha256=workflow_digest,
        cohort_manifest_sha256=cohort_digest,
        history_manifest_sha256=history_digest,
        config_sha256=config_digest,
        validation_split_evaluated=False,
        test_split_evaluated=False,
        model_fitted=False,
        source_replay_verified=True,
        raw_source_scan=False,
        prediction_rows_persisted=False,
        gpu_used=False,
        artifacts_sha256={"diagnostic_report.json": sha256(output_dir / "diagnostic_report.json")},
    )
    write_json(output_dir / "manifest.json", manifest)
    os.chmod(output_dir / "manifest.json", 0o600)
    return manifest
