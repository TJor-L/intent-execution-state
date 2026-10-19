"""Bounded W001 reader: identities across splits, labels/features only from training."""

import json
import math
import re
from collections import Counter, defaultdict

import pyarrow.parquet as pq

from ies.clinical_baseline import ClinicalBaselineError, _verify_artifact_directory
from ies.clock_audit import (
    MAX_COHORT_ROWS,
    MAX_HISTORY_ROWS,
    _file,
    _manifest,
    _parquet,
)
from ies.cohort_readiness.extract import SCHEMA
from ies.dual_clock_history import HISTORY_SCHEMA
from ies.io import sha256


def verify_bindings(bindings):
    for path, digest in bindings:
        if path.is_symlink() or not path.is_file() or sha256(path) != digest:
            raise ClinicalBaselineError("workflow_artifact_changed")


def load_workflow_training(cohort_dir, history_dir, cohort_digest, history_digest):
    cohort_dir = _verify_artifact_directory(cohort_dir, "invalid_workflow_cohort")
    history_dir = _verify_artifact_directory(history_dir, "invalid_workflow_history")
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
        raise ClinicalBaselineError("workflow_input_contract")
    qc_path = _file(history_dir, "qc_report.json", 1024**2)
    qc_digest = history_manifest.get("artifacts_sha256", {}).get("qc_report.json")
    if sha256(qc_path) != qc_digest:
        raise ClinicalBaselineError("workflow_qc_changed")
    qc = json.loads(qc_path.read_bytes())
    if (
        qc.get("status") != "complete"
        or qc.get("complete_full_source_scan") is not True
        or qc.get("source_stable") is not True
        or qc.get("outcome_features_used") is not False
    ):
        raise ClinicalBaselineError("workflow_history_incomplete")
    cohort_path = _parquet(cohort_dir, "cohort.parquet", cohort_manifest, SCHEMA, MAX_COHORT_ROWS)
    history_path = _parquet(
        history_dir, "history.parquet", history_manifest, HISTORY_SCHEMA, MAX_HISTORY_ROWS
    )
    bindings = [
        (cohort_dir / "manifest.json", cohort_digest),
        (history_dir / "manifest.json", history_digest),
        (qc_path, qc_digest),
        (cohort_path, cohort_manifest["artifacts_sha256"]["cohort.parquet"]),
        (history_path, history_manifest["artifacts_sha256"]["history.parquet"]),
    ]
    metadata = pq.read_table(cohort_path, columns=["patient_id", "order_id", "split"])
    if any(c.null_count for c in metadata.columns):
        raise ClinicalBaselineError("workflow_identity")
    patient_splits, orders, training = {}, set(), {}
    for row in metadata.to_pylist():
        patient, order, split = row["patient_id"], row["order_id"], row["split"]
        if (
            not patient
            or not order
            or order in orders
            or split not in {"train", "validation", "test"}
            or patient_splits.setdefault(patient, split) != split
        ):
            raise ClinicalBaselineError("workflow_patient_split_or_identity")
        orders.add(order)
        if split == "train":
            training[order] = patient
    if not training:
        raise ClinicalBaselineError("workflow_empty_training")
    table = pq.read_table(
        cohort_path,
        columns=["patient_id", "order_id", "duration_hours", "cause"],
        filters=[("split", "==", "train")],
    )
    if any(c.null_count for c in table.columns):
        raise ClinicalBaselineError("workflow_training_labels")
    cohort, seen = [], set()
    for row in table.to_pylist():
        order, patient = row["order_id"], row["patient_id"]
        duration, cause = row["duration_hours"], row["cause"]
        if (
            training.get(order) != patient
            or order in seen
            or not math.isfinite(duration)
            or not 0 < duration <= 24
            or cause not in (0, 1, 2, 3)
        ):
            raise ClinicalBaselineError("workflow_training_labels")
        seen.add(order)
        cohort.append(
            dict(patient_id=patient, order_id=order, split="train", duration=duration, cause=cause)
        )
    if seen != set(training):
        raise ClinicalBaselineError("workflow_training_alignment")
    history = pq.read_table(history_path, filters=[("index_order_id", "in", list(training))])
    if any(c.null_count for c in history.columns):
        raise ClinicalBaselineError("workflow_history_identity")
    grouped, seen, counts = defaultdict(list), set(), Counter()
    for row in history.to_pylist():
        order, kind = row["index_order_id"], row["event_kind"]
        key = (order, kind, row["event_id"])
        occurred, available, delay = (
            row[name]
            for name in (
                "occurrence_lag_hours",
                "availability_lag_hours",
                "documentation_delay_hours",
            )
        )
        if (
            row["patient_id"] != training.get(order)
            or kind not in (0, 1)
            or not row["event_id"]
            or key in seen
            or not all(math.isfinite(x) for x in (occurred, available, delay))
            or not 0 < occurred <= 24
            or not 0 <= available <= occurred
            or delay < 0
            or not math.isclose(delay, occurred - available, rel_tol=1e-10, abs_tol=1e-8)
        ):
            raise ClinicalBaselineError("workflow_history_alignment_or_time")
        seen.add(key)
        counts[order] += 1
        if counts[order] > 24:
            raise ClinicalBaselineError("workflow_history_cap")
        grouped[order].append(row)
    verify_bindings(bindings)
    return cohort, grouped, bindings
