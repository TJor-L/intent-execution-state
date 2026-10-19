"""Private, label-free audit of retained training histories; never a model gate."""

import json
import math
import os
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pyarrow.parquet as pq

from ies.clinical_baseline import ClinicalBaselineError, _verify_artifact_directory
from ies.cohort_readiness.extract import SCHEMA as COHORT_SCHEMA
from ies.dual_clock_history import HISTORY_SCHEMA
from ies.io import sha256, write_json

MODE = "training_clock_audit"
MAX_COHORT_ROWS = 20_000
MAX_HISTORY_ROWS = 500_000
MAX_FILE_BYTES = 256 * 1024**2
MAX_DECODED_BYTES = 512 * 1024**2
CLOCK_TOLERANCE_HOURS = 1e-6


def plan_clock_audit() -> dict:
    return {
        "mode": MODE,
        "submitted": False,
        "inputs": "existing_cohort_and_history_artifacts_only",
        "feature_split": "train",
        "outcome_columns_read": False,
        "model_fitted": False,
        "clinical_test_evaluated": False,
        "raw_source_scan": False,
        "row_persistence": False,
        "max_cohort_rows": MAX_COHORT_ROWS,
        "max_history_rows": MAX_HISTORY_ROWS,
        "max_file_bytes": MAX_FILE_BYTES,
        "max_decoded_bytes_per_parquet": MAX_DECODED_BYTES,
        "cpus": 2,
        "memory_mb": 4096,
        "worker_seconds": 300,
        "gpu_used": False,
    }


def _file(directory: Path, name: str, max_bytes: int) -> Path:
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ClinicalBaselineError("invalid_clock_audit_file")
    return path


def _manifest(directory: Path, expected_digest: str) -> dict:
    path = _file(directory, "manifest.json", 1024**2)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest) or sha256(path) != expected_digest:
        raise ClinicalBaselineError("clock_audit_manifest_changed")
    value = json.loads(path.read_bytes())
    if (
        not isinstance(value, dict)
        or value.get("status") != "complete"
        or value.get("data_class") != "restricted_clinical"
    ):
        raise ClinicalBaselineError("invalid_clock_audit_manifest")
    return value


def _parquet(directory, name, manifest, schema, max_rows):
    path = _file(directory, name, MAX_FILE_BYTES)
    if sha256(path) != manifest.get("artifacts_sha256", {}).get(name):
        raise ClinicalBaselineError("clock_audit_artifact_changed")
    with pq.ParquetFile(path) as parquet:
        metadata = parquet.metadata
        if parquet.schema_arrow != schema:
            raise ClinicalBaselineError("invalid_clock_audit_schema")
        if (
            metadata.num_rows > max_rows
            or sum(
                metadata.row_group(index).total_byte_size
                for index in range(metadata.num_row_groups)
            )
            > MAX_DECODED_BYTES
        ):
            raise ClinicalBaselineError("clock_audit_input_limit")
    return path


def audit_training_clocks(
    cohort_dir: Path,
    history_dir: Path,
    output_dir: Path,
    cohort_digest: str,
    history_digest: str,
    source_commit: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or any(output_dir.iterdir()):
        raise ClinicalBaselineError("invalid_clock_audit_output")
    cohort_dir = _verify_artifact_directory(cohort_dir, "invalid_clock_audit_cohort")
    history_dir = _verify_artifact_directory(history_dir, "invalid_clock_audit_history")
    cohort_manifest = _manifest(cohort_dir, cohort_digest)
    history_manifest = _manifest(history_dir, history_digest)
    if (
        cohort_manifest.get("mode") != "bounded_phase0_cohort_extraction"
        or cohort_manifest.get("bounded_domain") is not True
        or not re.fullmatch(r"[0-9a-f]{64}", cohort_manifest.get("mapping_sha256", ""))
        or history_manifest.get("mode") != "dual_clock_history_extraction"
        or history_manifest.get("cohort_manifest_sha256") != cohort_digest
        or history_manifest.get("mapping_sha256") != cohort_manifest["mapping_sha256"]
        or history_manifest.get("lookback_hours") != 24
        or history_manifest.get("max_events_per_order") != 24
        or history_manifest.get("sequence_truncation_rule")
        != "most_recent_occurrence_then_availability"
        or history_manifest.get("availability_masked") is not True
        or history_manifest.get("outcome_features_used") is not False
    ):
        raise ClinicalBaselineError("clock_audit_contract_mismatch")
    qc_path = _file(history_dir, "qc_report.json", 1024**2)
    if sha256(qc_path) != history_manifest.get("artifacts_sha256", {}).get("qc_report.json"):
        raise ClinicalBaselineError("clock_audit_qc_changed")
    qc = json.loads(qc_path.read_bytes())
    if (
        qc.get("status") != "complete"
        or qc.get("complete_full_source_scan") is not True
        or qc.get("source_stable") is not True
        or qc.get("outcome_features_used") is not False
    ):
        raise ClinicalBaselineError("clock_audit_history_incomplete")
    cohort_path = _parquet(
        cohort_dir, "cohort.parquet", cohort_manifest, COHORT_SCHEMA, MAX_COHORT_ROWS
    )
    history_path = _parquet(
        history_dir, "history.parquet", history_manifest, HISTORY_SCHEMA, MAX_HISTORY_ROWS
    )
    # Inspect only identities/splits across the cohort to verify patient separation.
    # Duration, cause, outcome and index time are never projected or materialized.
    cohort = pq.read_table(cohort_path, columns=["patient_id", "order_id", "split"])
    if any(column.null_count for column in cohort.columns):
        raise ClinicalBaselineError("invalid_clock_audit_identity")
    patients, orders, training = {}, set(), {}
    for row in cohort.to_pylist():
        patient, order, split = row["patient_id"], row["order_id"], row["split"]
        if (
            not patient
            or not order
            or order in orders
            or split not in {"train", "validation", "test"}
        ):
            raise ClinicalBaselineError("invalid_clock_audit_identity")
        orders.add(order)
        if patients.setdefault(patient, split) != split:
            raise ClinicalBaselineError("clock_audit_patient_overlap")
        if split == "train":
            training[order] = patient
    if not training:
        raise ClinicalBaselineError("clock_audit_empty_training")
    # Files may share pages across splits, but only selected training histories are
    # materialized as rows and aggregated. Hashing binds the entire immutable files.
    history = pq.read_table(history_path, filters=[("index_order_id", "in", list(training))])
    if any(column.null_count for column in history.columns):
        raise ClinicalBaselineError("invalid_clock_audit_history")
    grouped = defaultdict(list)
    identities = set()
    order_sizes = Counter()
    kind_counts = {kind: Counter() for kind in (0, 1)}
    for row in history.to_pylist():
        order, kind = row["index_order_id"], row["event_kind"]
        if (
            row["patient_id"] != training.get(order)
            or kind not in kind_counts
            or not row["event_id"]
        ):
            raise ClinicalBaselineError("clock_audit_history_alignment")
        key = (order, kind, row["event_id"])
        if key in identities:
            raise ClinicalBaselineError("clock_audit_duplicate_history")
        identities.add(key)
        order_sizes[order] += 1
        if order_sizes[order] > 24:
            raise ClinicalBaselineError("clock_audit_sequence_cap_exceeded")
        occurred, available, delay = (
            row[name]
            for name in (
                "occurrence_lag_hours",
                "availability_lag_hours",
                "documentation_delay_hours",
            )
        )
        if (
            not all(math.isfinite(value) for value in (occurred, available, delay))
            or not 0 < occurred <= 24
            or not 0 <= available <= occurred
            or delay < 0
            or not math.isclose(delay, occurred - available, rel_tol=1e-10, abs_tol=1e-8)
        ):
            raise ClinicalBaselineError("clock_audit_invalid_time_pair")
        counts = kind_counts[kind]
        counts["relationships"] += 1
        counts[
            "equal_clock_relationships"
            if delay <= CLOCK_TOLERANCE_HOURS
            else "positive_delay_relationships"
        ] += 1
        grouped[(order, kind)].append((occurred, available))
    for (_order, kind), pairs in grouped.items():
        counts = kind_counts[kind]
        counts["orders_with_history"] += 1
        if len(pairs) >= 2:
            counts["orders_with_multiple_events"] += 1
        # Existence of a different valid pairing preserving both empirical marginals.
        # Zero excludes only this specific contrast in the retained histories.
        if any(
            first[0] >= second[1]
            and second[0] >= first[1]
            and abs(first[0] - second[0]) > CLOCK_TOLERANCE_HOURS
            and abs(first[1] - second[1]) > CLOCK_TOLERANCE_HOURS
            for first, second in combinations(pairs, 2)
        ):
            counts["orders_with_valid_pair_swap"] += 1
    # Recheck all bindings after the read, rather than accepting mutated inputs.
    if (
        _manifest(cohort_dir, cohort_digest) != cohort_manifest
        or _manifest(history_dir, history_digest) != history_manifest
    ):
        raise ClinicalBaselineError("clock_audit_manifest_changed")
    for path, manifest in (
        (cohort_path, cohort_manifest),
        (history_path, history_manifest),
        (qc_path, history_manifest),
    ):
        if sha256(path) != manifest["artifacts_sha256"][path.name]:
            raise ClinicalBaselineError("clock_audit_artifact_changed")
    fields = (
        "relationships",
        "equal_clock_relationships",
        "positive_delay_relationships",
        "orders_with_history",
        "orders_with_multiple_events",
        "orders_with_valid_pair_swap",
    )
    report = {
        "schema_version": 1,
        "mode": MODE,
        "data_class": "restricted_aggregate",
        "status": "complete",
        "training_orders": len(training),
        "training_patients": len(set(training.values())),
        "training_orders_without_history": len(training) - len(order_sizes),
        "training_orders_at_retained_cap": sum(size == 24 for size in order_sizes.values()),
        "counts_by_event_kind": {
            str(kind): {field: kind_counts[kind][field] for field in fields} for kind in (0, 1)
        },
        "clock_tolerance_hours": CLOCK_TOLERANCE_HOURS,
        "coverage_scope": "retained_training_history_only",
        "outcome_columns_read": False,
        "model_fitted": False,
        "clinical_test_evaluated": False,
        "raw_source_scan": False,
        "row_persistence": False,
        "requires_private_semantic_review": True,
        "clinical_advancement_decision": "not_applicable",
        "interpretation": (
            "Descriptive support audit only; no prediction, power, sufficiency or population claim."
        ),
    }
    write_json(output_dir / "clock_report.json", report)
    os.chmod(output_dir / "clock_report.json", 0o600)
    result = {
        "schema_version": 1,
        "mode": MODE,
        "data_class": "restricted_aggregate",
        "status": "complete",
        "source_commit": source_commit,
        "cohort_manifest_sha256": cohort_digest,
        "history_manifest_sha256": history_digest,
        "outcome_columns_read": False,
        "clinical_test_evaluated": False,
        "model_fitted": False,
        "artifacts_sha256": {"clock_report.json": sha256(output_dir / "clock_report.json")},
    }
    write_json(output_dir / "manifest.json", result)
    os.chmod(output_dir / "manifest.json", 0o600)
    return result
