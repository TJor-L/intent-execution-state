"""Reviewed pre-index features for the bounded private UCSF cohort."""

import json
import os
import re
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ies.cohort_readiness.eligibility import EligibilityMapping, audit_eligibility
from ies.cohort_readiness.extract import SCHEMA as COHORT_SCHEMA
from ies.feasibility.contract import ROOT
from ies.io import sha256, write_json


class ClinicalFeatureError(ValueError):
    pass


AUTHORIZED_ROOT = Path("/scratch/tliu7")


FEATURE_SCHEMA = pa.schema(
    [
        ("patient_id", pa.string()),
        ("order_id", pa.string()),
        ("age_years_at_order", pa.int32()),
    ]
)


def extract_clinical_features(
    mapping: EligibilityMapping,
    minimum_orders: int,
    minimum_events: int,
    cohort_dir: Path,
    output_dir: Path,
    cohort_manifest_sha256: str,
    mapping_sha256: str,
    protocol_sha256: str,
    source_commit: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or any(output_dir.iterdir()):
        raise ClinicalFeatureError("invalid_feature_output")
    cohort_dir = cohort_dir.resolve()
    if not cohort_dir.is_relative_to(AUTHORIZED_ROOT) or cohort_dir.is_relative_to(ROOT):
        raise ClinicalFeatureError("invalid_feature_cohort")
    manifest_path = cohort_dir / "manifest.json"
    if sha256(manifest_path) != cohort_manifest_sha256:
        raise ClinicalFeatureError("feature_cohort_changed")
    cohort_manifest = json.loads(manifest_path.read_text())
    cohort_path = cohort_dir / "cohort.parquet"
    if cohort_manifest.get("status") != "complete" or cohort_manifest.get(
        "artifacts_sha256", {}
    ).get("cohort.parquet") != sha256(cohort_path):
        raise ClinicalFeatureError("invalid_feature_cohort")
    cohort = pq.read_table(cohort_path)
    if cohort.schema != COHORT_SCHEMA or cohort.num_rows == 0:
        raise ClinicalFeatureError("invalid_feature_cohort")

    regenerated: list[dict] = []
    report = audit_eligibility(
        mapping,
        minimum_orders,
        minimum_events,
        cohort_rows=regenerated,
    )
    existing = {row["order_id"]: row for row in cohort.to_pylist()}
    if len(existing) != cohort.num_rows or len(regenerated) != cohort.num_rows:
        raise ClinicalFeatureError("feature_cohort_mismatch")
    features = []
    for row in regenerated:
        prior = existing.get(row["order_id"])
        if prior is None or any(
            prior[name] != row[name]
            for name in (
                "patient_id",
                "encounter_id",
                "split",
                "index_time_hours",
                "duration_hours",
                "cause",
                "outcome",
            )
        ):
            raise ClinicalFeatureError("feature_cohort_mismatch")
        age = row.get("age_years_at_order")
        if type(age) is not int or age < 18:
            raise ClinicalFeatureError("invalid_age_feature")
        features.append(
            {
                "patient_id": row["patient_id"],
                "order_id": row["order_id"],
                "age_years_at_order": age,
            }
        )
    features.sort(key=lambda row: (row["patient_id"], row["order_id"]))
    table = pa.Table.from_pylist(features, schema=FEATURE_SCHEMA)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_dir, prefix=".features-", suffix=".parquet"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    feature_path = output_dir / "features.parquet"
    try:
        pq.write_table(table, temporary, compression="zstd")
        os.chmod(temporary, 0o600)
        os.replace(temporary, feature_path)
    finally:
        temporary.unlink(missing_ok=True)
    qc = {
        "schema_version": 1,
        "mode": "bounded_preindex_feature_qc",
        "data_class": "restricted_aggregate",
        "status": "complete",
        "cohort_rows_aligned": True,
        "age_feature_complete": True,
        "laboratory_features_enabled": False,
        "outcome_features_used": False,
        "population_counts_complete": report["population_counts_complete"],
    }
    qc_path = output_dir / "qc_report.json"
    write_json(qc_path, qc)
    os.chmod(qc_path, 0o600)
    manifest = {
        "schema_version": 1,
        "mode": "bounded_preindex_feature_extraction",
        "data_class": "restricted_clinical",
        "status": "complete",
        "source_commit": source_commit,
        "cohort_manifest_sha256": cohort_manifest_sha256,
        "mapping_sha256": mapping_sha256,
        "protocol_sha256": protocol_sha256,
        "features": ["age_years_at_order"],
        "availability": "known_at_order_index",
        "laboratory_features_enabled": False,
        "outcome_features_used": False,
        "database_write": False,
        "gpu_used": False,
        "artifacts_sha256": {
            feature_path.name: sha256(feature_path),
            qc_path.name: sha256(qc_path),
        },
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    os.chmod(manifest_path, 0o600)
    return manifest
