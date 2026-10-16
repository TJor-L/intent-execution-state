"""Leakage-safe dual-clock order/administration histories for a frozen cohort."""

import hashlib
import json
import math
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from ies.cohort_readiness.eligibility import _base_source, _inventory, _scan
from ies.cohort_readiness.extract import SCHEMA as COHORT_SCHEMA
from ies.feasibility.analysis import known_by, pair
from ies.feasibility.contract import ROOT, Mapping, identity
from ies.io import sha256, write_json


class HistoryError(ValueError):
    pass


AUTHORIZED_ROOT = Path("/scratch/tliu7")


HISTORY_SCHEMA = pa.schema(
    [
        ("patient_id", pa.string()),
        ("index_order_id", pa.string()),
        ("event_id", pa.string()),
        ("event_kind", pa.int8()),
        ("occurrence_lag_hours", pa.float64()),
        ("availability_lag_hours", pa.float64()),
        ("documentation_delay_hours", pa.float64()),
    ]
)


def load_history_config(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    try:
        value = yaml.safe_load(content)
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "lookback_hours",
            "minimum_history_events",
            "minimum_orders_with_history",
            "max_history_rows",
            "max_events_per_order",
        }:
            raise HistoryError("invalid_history_config")
        if value["schema_version"] != 1:
            raise HistoryError("invalid_history_config")
        if type(value["lookback_hours"]) not in (int, float) or not math.isfinite(
            value["lookback_hours"]
        ):
            raise HistoryError("invalid_history_config")
        if not 0 < value["lookback_hours"] <= 168:
            raise HistoryError("invalid_history_config")
        for name in (
            "minimum_history_events",
            "minimum_orders_with_history",
            "max_history_rows",
            "max_events_per_order",
        ):
            if type(value[name]) is not int or value[name] <= 0:
                raise HistoryError("invalid_history_config")
        if value["minimum_history_events"] > value["max_history_rows"]:
            raise HistoryError("invalid_history_config")
        return value, hashlib.sha256(content).hexdigest()
    except (OSError, yaml.YAMLError, TypeError, KeyError):
        raise HistoryError("invalid_history_config") from None


def _decode_identifier(value: str) -> tuple[str, str | int]:
    if not isinstance(value, str) or ":" not in value:
        raise HistoryError("invalid_history_identity")
    kind, raw = value.split(":", 1)
    if kind == "string" and raw:
        return kind, raw
    if kind == "integer":
        try:
            parsed = int(raw)
        except ValueError:
            raise HistoryError("invalid_history_identity") from None
        return kind, parsed
    raise HistoryError("invalid_history_identity")


def _canonical(value) -> str:
    key = identity(value)
    if key is None:
        raise HistoryError("invalid_history_identity")
    return f"{key[0]}:{key[1]}"


def _inventory_digest(inventories) -> str:
    digest = hashlib.sha256()
    for role in sorted(inventories):
        for item in inventories[role]:
            digest.update(role.encode())
            digest.update(b"\0")
            digest.update(str(item.path).encode())
            digest.update(b"\0")
            digest.update(str(item.size).encode())
            digest.update(b"\0")
            digest.update(str(item.mtime_ns).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _history_matches(
    indexes, event_id, occurred, available, kind, config, sink, per_order, diagnostics
):
    if not known_by(occurred, available, math.inf):
        raise HistoryError("invalid_history_time")
    for index in indexes:
        cutoff = index["index_time_hours"]
        if not cutoff - config["lookback_hours"] <= occurred < cutoff or available > cutoff:
            continue
        order_id = index["order_id"]
        per_order[order_id] += 1
        diagnostics["eligible_history_relationships"] += 1
        bucket = sink.setdefault(order_id, [])
        bucket.append(
            {
                "patient_id": index["patient_id"],
                "index_order_id": order_id,
                "event_id": _canonical(event_id),
                "event_kind": kind,
                "occurrence_lag_hours": cutoff - occurred,
                "availability_lag_hours": cutoff - available,
                "documentation_delay_hours": available - occurred,
            }
        )
        if len(bucket) > config["max_events_per_order"]:
            bucket.sort(
                key=lambda row: (
                    row["occurrence_lag_hours"],
                    row["availability_lag_hours"],
                    row["event_kind"],
                    row["event_id"],
                )
            )
            bucket.pop()
            diagnostics["truncated_history_relationships"] += 1


def build_history_rows(
    order_rows,
    administration_rows,
    indexes_by_patient,
    mapping,
    config,
    diagnostics: Counter | None = None,
):
    diagnostics = diagnostics if diagnostics is not None else Counter()
    rows_by_order = {}
    per_order = Counter()
    seen_orders = set()
    counts = Counter()
    for row in order_rows:
        patient = identity(row.get("patient_id"))
        event = identity(row.get("order_id"))
        if patient not in indexes_by_patient:
            continue
        if event is None or event in seen_orders:
            raise HistoryError("duplicate_history_order")
        seen_orders.add(event)
        times, bad = pair(row, "occurred_at", "available_at", mapping, counts)
        if bad or times is None:
            diagnostics["excluded_invalid_order_times"] += 1
            continue
        _history_matches(
            indexes_by_patient[patient],
            row["order_id"],
            *times,
            0,
            config,
            rows_by_order,
            per_order,
            diagnostics,
        )
    seen_administrations = set()
    for row in administration_rows:
        patient = identity(row.get("patient_id"))
        event = identity(row.get("administration_id"))
        if patient not in indexes_by_patient:
            continue
        if event is None or event in seen_administrations:
            raise HistoryError("duplicate_history_administration")
        seen_administrations.add(event)
        if identity(row.get("action")) not in mapping.qualifying_actions:
            continue
        availability = "available_at"
        if mapping.occurrence_equality_policy is not None:
            policy = mapping.occurrence_equality_policy
            status = identity(row.get("documentation_status"))
            if status not in policy.contemporaneous_values:
                continue
            availability = "occurred_at"
        times, bad = pair(row, "occurred_at", availability, mapping, counts)
        if bad or times is None:
            diagnostics["excluded_invalid_administration_times"] += 1
            continue
        _history_matches(
            indexes_by_patient[patient],
            row["administration_id"],
            *times,
            1,
            config,
            rows_by_order,
            per_order,
            diagnostics,
        )
    rows = [row for bucket in rows_by_order.values() for row in bucket]
    if len(rows) > config["max_history_rows"]:
        raise HistoryError("history_rows_limit")
    rows.sort(
        key=lambda row: (
            row["patient_id"],
            row["index_order_id"],
            -row["occurrence_lag_hours"],
            row["event_kind"],
            row["event_id"],
        )
    )
    return rows, per_order


def extract_history(
    mapping: Mapping,
    eligibility_limits,
    cohort_dir: Path,
    output_dir: Path,
    config: dict,
    config_sha256: str,
    cohort_manifest_sha256: str,
    mapping_sha256: str,
    source_commit: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or any(output_dir.iterdir()):
        raise HistoryError("invalid_history_output")
    cohort_dir = cohort_dir.resolve()
    if not cohort_dir.is_relative_to(AUTHORIZED_ROOT) or cohort_dir.is_relative_to(ROOT):
        raise HistoryError("invalid_history_cohort")
    manifest_path = cohort_dir / "manifest.json"
    if sha256(manifest_path) != cohort_manifest_sha256:
        raise HistoryError("history_cohort_changed")
    cohort_manifest = json.loads(manifest_path.read_text())
    cohort_path = cohort_dir / "cohort.parquet"
    if (
        cohort_manifest.get("status") != "complete"
        or cohort_manifest.get("mapping_sha256") != mapping_sha256
        or cohort_manifest.get("artifacts_sha256", {}).get("cohort.parquet") != sha256(cohort_path)
    ):
        raise HistoryError("invalid_history_cohort")
    cohort = pq.read_table(cohort_path)
    if cohort.schema != COHORT_SCHEMA or cohort.num_rows == 0:
        raise HistoryError("invalid_history_cohort")
    indexes_by_patient = {}
    raw_patients = set()
    for row in cohort.to_pylist():
        patient = _decode_identifier(row["patient_id"])
        raw_patients.add(patient[1])
        indexes_by_patient.setdefault(patient, []).append(row)

    started = time.monotonic()
    sources = {
        "orders": _base_source(mapping.orders),
        "administrations": _base_source(mapping.administrations),
    }
    before = {name: _inventory(source, eligibility_limits) for name, source in sources.items()}
    inventory_digest = _inventory_digest(before)
    filters = {"patient_id": raw_patients}
    order_rows = _scan(sources["orders"], before["orders"], eligibility_limits, started, filters)
    administration_rows = _scan(
        sources["administrations"],
        before["administrations"],
        eligibility_limits,
        started,
        filters,
    )
    diagnostics = Counter()
    rows, per_order = build_history_rows(
        order_rows,
        administration_rows,
        indexes_by_patient,
        mapping,
        config,
        diagnostics,
    )
    after = {name: _inventory(source, eligibility_limits) for name, source in sources.items()}
    if before != after:
        raise HistoryError("history_source_changed")
    if len(rows) < config["minimum_history_events"]:
        raise HistoryError("insufficient_history_events")
    if sum(value > 0 for value in per_order.values()) < config["minimum_orders_with_history"]:
        raise HistoryError("insufficient_orders_with_history")

    table = pa.Table.from_pylist(rows, schema=HISTORY_SCHEMA)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_dir, prefix=".history-", suffix=".parquet"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    history_path = output_dir / "history.parquet"
    try:
        pq.write_table(table, temporary, compression="zstd")
        os.chmod(temporary, 0o600)
        os.replace(temporary, history_path)
    finally:
        temporary.unlink(missing_ok=True)
    qc = {
        "schema_version": 1,
        "mode": "dual_clock_history_qc",
        "data_class": "restricted_aggregate",
        "status": "complete",
        "history_events": len(rows),
        "orders_with_history": sum(value > 0 for value in per_order.values()),
        "lookback_hours": config["lookback_hours"],
        "source_stable": True,
        "complete_full_source_scan": True,
        "laboratory_features_enabled": False,
        "outcome_features_used": False,
        "excluded_invalid_order_times": diagnostics["excluded_invalid_order_times"],
        "excluded_invalid_administration_times": diagnostics[
            "excluded_invalid_administration_times"
        ],
        "eligible_history_relationships": diagnostics["eligible_history_relationships"],
        "truncated_history_relationships": diagnostics["truncated_history_relationships"],
    }
    qc_path = output_dir / "qc_report.json"
    write_json(qc_path, qc)
    os.chmod(qc_path, 0o600)
    manifest = {
        "schema_version": 1,
        "mode": "dual_clock_history_extraction",
        "data_class": "restricted_clinical",
        "status": "complete",
        "source_commit": source_commit,
        "cohort_manifest_sha256": cohort_manifest_sha256,
        "mapping_sha256": mapping_sha256,
        "source_inventory_sha256": inventory_digest,
        "config_sha256": config_sha256,
        "lookback_hours": config["lookback_hours"],
        "event_kinds": ["order", "qualifying_administration"],
        "max_events_per_order": config["max_events_per_order"],
        "sequence_truncation_rule": "most_recent_occurrence_then_availability",
        "availability_masked": True,
        "outcome_features_used": False,
        "database_write": False,
        "gpu_used": False,
        "artifacts_sha256": {
            history_path.name: sha256(history_path),
            qc_path.name: sha256(qc_path),
        },
    }
    write_json(output_dir / "manifest.json", manifest)
    os.chmod(output_dir / "manifest.json", 0o600)
    return manifest
