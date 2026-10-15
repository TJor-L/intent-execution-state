"""Private, bounded Phase 0 cohort extraction on the authorized UCSF server."""

import os
import re
import tempfile
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ies.cohort_readiness.eligibility import EligibilityError, EligibilityMapping, audit_eligibility
from ies.io import sha256, write_json

SCHEMA = pa.schema(
    [
        ("patient_id", pa.string()),
        ("order_id", pa.string()),
        ("encounter_id", pa.string()),
        ("split", pa.string()),
        ("index_time_hours", pa.float64()),
        ("duration_hours", pa.float64()),
        ("cause", pa.int8()),
        ("outcome", pa.string()),
    ]
)


def _private_file(path: Path) -> None:
    os.chmod(path, 0o600)


def extract_cohort(
    mapping: EligibilityMapping,
    minimum_orders: int,
    minimum_events: int,
    output_dir: Path,
    mapping_sha256: str,
    protocol_sha256: str,
    source_commit: str,
) -> dict:
    """Extract the validated bounded domain; all returned details are UCSF-private."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise EligibilityError("invalid_extraction_commit")
    if any(output_dir.iterdir()):
        raise EligibilityError("extraction_output_not_empty")

    rows: list[dict] = []
    eligibility = audit_eligibility(
        mapping,
        minimum_orders,
        minimum_events,
        cohort_rows=rows,
    )
    rows.sort(key=lambda row: (row["patient_id"], row["order_id"]))
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    if table.num_rows != len(rows) or table.num_rows == 0:
        raise EligibilityError("invalid_extracted_cohort")

    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_dir, prefix=".cohort-", suffix=".parquet"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    cohort_path = output_dir / "cohort.parquet"
    try:
        pq.write_table(table, temporary, compression="zstd")
        _private_file(temporary)
        os.replace(temporary, cohort_path)
    finally:
        temporary.unlink(missing_ok=True)

    outcome_counts = Counter(row["outcome"] for row in rows)
    split_counts = Counter(row["split"] for row in rows)
    patient_counts = Counter(row["split"] for row in {r["patient_id"]: r for r in rows}.values())
    qc = {
        "schema_version": 1,
        "mode": "bounded_phase0_cohort_qc",
        "data_class": "restricted_aggregate",
        "status": "complete",
        "population_counts_complete": eligibility["population_counts_complete"],
        "thresholds": eligibility["thresholds"],
        "eligibility_counts": eligibility["counts"],
        "outcome_validation_counts": eligibility["outcome_counts"],
        "cohort_rows": len(rows),
        "cohort_patients": len({row["patient_id"] for row in rows}),
        "outcomes": dict(sorted(outcome_counts.items())),
        "rows_by_split": dict(sorted(split_counts.items())),
        "patients_by_split": dict(sorted(patient_counts.items())),
        "laboratory_features_enabled": False,
    }
    qc_path = output_dir / "qc_report.json"
    write_json(qc_path, qc)
    _private_file(qc_path)

    manifest = {
        "schema_version": 1,
        "mode": "bounded_phase0_cohort_extraction",
        "data_class": "restricted_clinical",
        "status": "complete",
        "source_commit": source_commit,
        "mapping_sha256": mapping_sha256,
        "protocol_sha256": protocol_sha256,
        "bounded_domain": True,
        "population_counts_complete": eligibility["population_counts_complete"],
        "row_persistence": True,
        "database_write": False,
        "gpu_used": False,
        "artifacts_sha256": {
            cohort_path.name: sha256(cohort_path),
            qc_path.name: sha256(qc_path),
        },
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    _private_file(manifest_path)
    return manifest
