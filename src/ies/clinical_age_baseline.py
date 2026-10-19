"""Private fixed age-band baseline over verified cohort and feature artifacts."""

import json
import os
import re
from pathlib import Path

import pyarrow.parquet as pq

from ies.clinical_baseline import (
    ClinicalBaselineError,
    _verify_artifact_directory,
    _verify_cohort,
)
from ies.clinical_features import FEATURE_SCHEMA
from ies.io import sha256, write_json
from ies.models.age_stratified import evaluate_age_stratified, fit_age_stratified


def run_clinical_age_baseline(
    cohort_dir: Path,
    feature_dir: Path,
    output_dir: Path,
    config: dict,
    config_sha256: str,
    cohort_manifest_sha256: str,
    feature_manifest_sha256: str,
    source_commit: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or any(output_dir.iterdir()):
        raise ClinicalBaselineError("invalid_age_baseline_output")
    cohort, _ = _verify_cohort(cohort_dir, cohort_manifest_sha256)
    feature_dir = _verify_artifact_directory(feature_dir, "invalid_age_features")
    manifest_path = feature_dir / "manifest.json"
    if sha256(manifest_path) != feature_manifest_sha256:
        raise ClinicalBaselineError("age_features_changed")
    feature_manifest = json.loads(manifest_path.read_text())
    feature_path = feature_dir / "features.parquet"
    if (
        feature_manifest.get("status") != "complete"
        or feature_manifest.get("features") != ["age_years_at_order"]
        or feature_manifest.get("outcome_features_used") is not False
        or feature_manifest.get("artifacts_sha256", {}).get("features.parquet")
        != sha256(feature_path)
    ):
        raise ClinicalBaselineError("invalid_age_features")
    features = pq.read_table(feature_path)
    if features.schema != FEATURE_SCHEMA or any(column.null_count for column in features.columns):
        raise ClinicalBaselineError("invalid_age_features")
    by_order = {row["order_id"]: row for row in features.to_pylist()}
    if len(by_order) != features.num_rows:
        raise ClinicalBaselineError("invalid_age_features")
    joined = []
    for row in cohort:
        feature = by_order.get(row["order_id"])
        if feature is None or feature["patient_id"] != row["patient_id"]:
            raise ClinicalBaselineError("age_feature_alignment")
        joined.append(dict(row, age_years_at_order=feature["age_years_at_order"]))
    model = fit_age_stratified(joined, config["bin_edges_hours"])
    metrics, predictions = evaluate_age_stratified(
        joined,
        model,
        split="validation",
        bootstrap=config["bootstrap_replicates"],
        seed=config["seed"],
    )
    artifacts = {
        "model.json": model,
        "validation_metrics.json": metrics,
        "validation_predictions.json": predictions,
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
        os.chmod(output_dir / name, 0o600)
    manifest = {
        "schema_version": 1,
        "mode": "clinical_fixed_age_band_baseline",
        "data_class": "restricted_clinical",
        "status": "complete",
        "source_commit": source_commit,
        "cohort_manifest_sha256": cohort_manifest_sha256,
        "feature_manifest_sha256": feature_manifest_sha256,
        "config_sha256": config_sha256,
        "evaluation_split": "validation",
        "test_split_evaluated": False,
        "features": ["age_years_at_order"],
        "database_write": False,
        "gpu_used": False,
        "artifacts_sha256": {name: sha256(output_dir / name) for name in artifacts},
    }
    write_json(output_dir / "manifest.json", manifest)
    os.chmod(output_dir / "manifest.json", 0o600)
    return manifest
