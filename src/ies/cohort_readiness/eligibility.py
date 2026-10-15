"""Bounded, aggregate-only adult inpatient medication eligibility audit."""

from __future__ import annotations

import hashlib
import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml

from ies.feasibility.analysis import analyze
from ies.feasibility.contract import (
    ROOT,
    FeasibilityError,
    Mapping,
    identity,
    load_mapping_snapshot,
)


class EligibilityError(ValueError):
    """Fixed error code for private eligibility-audit failures."""


def require(condition: bool) -> None:
    if not condition:
        raise EligibilityError("invalid_eligibility_mapping")


@dataclass(frozen=True, repr=False)
class DimensionSource:
    path: Path
    columns: dict[str, str]


@dataclass(frozen=True, repr=False)
class EligibilityLimits:
    max_files_per_source: int
    max_entries_per_source: int
    max_row_groups_per_source: int
    max_rows_per_source: int
    max_source_bytes: int
    max_candidate_orders: int
    max_retained_rows_per_source: int
    batch_rows: int
    runtime_seconds: int
    cpu_seconds: int
    cpus: int
    memory_mb: int


@dataclass(frozen=True, repr=False)
class EligibilityMapping:
    feasibility_path: Path
    feasibility_sha256: str
    feasibility: Mapping
    order_criteria_columns: dict[str, str]
    patients: DimensionSource
    encounters: DimensionSource
    therapeutic_class_values: frozenset[tuple[str, str | int]]
    route_values: frozenset[tuple[str, str | int]]
    non_prn_values: frozenset[tuple[str, str | int]]
    one_time_frequency_values: frozenset[tuple[str, str | int]]
    current_values: frozenset[tuple[str, str | int]]
    valid_values: frozenset[tuple[str, str | int]]
    inpatient_values: frozenset[tuple[str, str | int]]
    limits: EligibilityLimits


LIMIT_CAPS = {
    "max_files_per_source": 1_000,
    "max_entries_per_source": 2_000,
    "max_row_groups_per_source": 2_000,
    "max_rows_per_source": 500_000_000,
    "max_source_bytes": 64 * 1024**3,
    "max_candidate_orders": 100_000,
    "max_retained_rows_per_source": 300_000,
    "batch_rows": 65_536,
    "runtime_seconds": 1_500,
    "cpu_seconds": 1_500,
    "cpus": 4,
    "memory_mb": 16_384,
}


def _path(value) -> Path:
    require(isinstance(value, str) and value and "\x00" not in value)
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and path != Path("/"))
    require(not path.is_relative_to(ROOT))
    return path


def _private_mapping_path(value) -> Path:
    require(isinstance(value, str) and value and "\x00" not in value)
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and path != Path("/"))
    if path.is_relative_to(ROOT):
        require(path.parent == ROOT / "configs" and path.name.endswith(".local.yaml"))
    return path


def _column(value) -> str:
    require(
        isinstance(value, str)
        and 0 < len(value) <= 256
        and not any(character in value for character in ("\x00", "\n", "\r", "."))
    )
    return value


def _source(value, names: set[str]) -> DimensionSource:
    require(isinstance(value, dict) and set(value) == {"path", "columns"})
    columns = value["columns"]
    require(isinstance(columns, dict) and set(columns) == names)
    parsed = {name: _column(column) for name, column in columns.items()}
    require(len(set(parsed.values())) == len(parsed))
    return DimensionSource(_path(value["path"]), parsed)


def _evidence(value) -> None:
    require(isinstance(value, str) and 0 < len(value.strip()) <= 2_048 and "\x00" not in value)


def criterion_identity(value) -> tuple[str, str | int | bool] | None:
    if type(value) is bool:
        return ("boolean", value)
    return identity(value)


def _criterion_set(value) -> frozenset[tuple[str, str | int | bool]]:
    require(isinstance(value, list) and 1 <= len(value) <= 64)
    require(all(criterion_identity(item) is not None for item in value))
    return frozenset(criterion_identity(item) for item in value)


def parse_eligibility_mapping(value: dict) -> EligibilityMapping:
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "schema_version",
            "execution_context",
            "institutional_access_confirmed",
            "mapping_reviewed",
            "protocol_frozen_reviewed",
            "criteria_reviewed",
            "evidence_reference",
            "feasibility_mapping",
            "order_criteria_columns",
            "patients",
            "encounters",
            "accepted_values",
            "limits",
        }
    )
    require(value["schema_version"] == 1 and value["execution_context"] == "ucsf")
    for flag in (
        "institutional_access_confirmed",
        "mapping_reviewed",
        "protocol_frozen_reviewed",
        "criteria_reviewed",
    ):
        require(value[flag] is True)
    _evidence(value["evidence_reference"])
    feasibility_value = value["feasibility_mapping"]
    require(isinstance(feasibility_value, dict) and set(feasibility_value) == {"path", "sha256"})
    feasibility_path = _private_mapping_path(feasibility_value["path"])
    expected_sha = feasibility_value["sha256"]
    require(isinstance(expected_sha, str) and len(expected_sha) == 64)
    feasibility, actual_sha = load_mapping_snapshot(feasibility_path)
    require(actual_sha == expected_sha)
    raw_order_columns = value["order_criteria_columns"]
    require(
        isinstance(raw_order_columns, dict)
        and set(raw_order_columns) == {"therapeutic_class", "route", "prn", "frequency"}
    )
    order_columns = {name: _column(column) for name, column in raw_order_columns.items()}
    require(len(set(order_columns.values())) == 4)
    patients = _source(
        value["patients"], {"patient_id", "birth_date", "current_status", "valid_status"}
    )
    encounters = _source(value["encounters"], {"encounter_id", "patient_id", "patient_class"})
    accepted = value["accepted_values"]
    require(
        isinstance(accepted, dict)
        and set(accepted)
        == {
            "therapeutic_class",
            "route",
            "non_prn",
            "one_time_frequency",
            "current_status",
            "valid_status",
            "inpatient_class",
        }
    )
    parsed_values = {name: _criterion_set(raw) for name, raw in accepted.items()}
    raw_limits = value["limits"]
    require(isinstance(raw_limits, dict) and set(raw_limits) == set(LIMIT_CAPS))
    require(
        all(
            type(raw_limits[name]) is int and 1 <= raw_limits[name] <= maximum
            for name, maximum in LIMIT_CAPS.items()
        )
    )
    require(raw_limits["memory_mb"] >= 1_024)
    require(raw_limits["max_candidate_orders"] <= raw_limits["max_retained_rows_per_source"])
    return EligibilityMapping(
        feasibility_path,
        actual_sha,
        feasibility,
        order_columns,
        patients,
        encounters,
        parsed_values["therapeutic_class"],
        parsed_values["route"],
        parsed_values["non_prn"],
        parsed_values["one_time_frequency"],
        parsed_values["current_status"],
        parsed_values["valid_status"],
        parsed_values["inpatient_class"],
        EligibilityLimits(**raw_limits),
    )


def load_eligibility_mapping(path: Path) -> tuple[EligibilityMapping, str]:
    try:
        content = path.read_bytes()
        mapping = parse_eligibility_mapping(yaml.safe_load(content))
        return mapping, hashlib.sha256(content).hexdigest()
    except (EligibilityError, FeasibilityError):
        raise EligibilityError("invalid_eligibility_mapping") from None
    except Exception:
        raise EligibilityError("invalid_eligibility_mapping") from None


@dataclass(frozen=True, repr=False)
class FileState:
    path: Path
    size: int
    mtime_ns: int


def _inventory(source: DimensionSource, limits: EligibilityLimits) -> tuple[FileState, ...]:
    root = source.path
    if root.is_symlink() or not root.exists():
        raise EligibilityError("eligibility_source_unavailable")
    candidates = []
    if root.is_file():
        candidates.append(root)
    else:
        entries = 0
        with os.scandir(root) as stream:
            for entry in stream:
                entries += 1
                if entries > limits.max_entries_per_source:
                    raise EligibilityError("eligibility_entries_limit")
                if entry.is_symlink() or entry.is_dir(follow_symlinks=False):
                    raise EligibilityError("eligibility_invalid_source_layout")
                if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".parquet"):
                    candidates.append(Path(entry.path))
    if not candidates or len(candidates) > limits.max_files_per_source:
        raise EligibilityError("eligibility_files_limit")
    states = []
    for path in sorted(candidates):
        stat = path.stat(follow_symlinks=False)
        states.append(FileState(path.resolve(), stat.st_size, stat.st_mtime_ns))
    if sum(item.size for item in states) > limits.max_source_bytes:
        raise EligibilityError("eligibility_bytes_limit")
    return tuple(states)


def _scan(
    source: DimensionSource,
    files: tuple[FileState, ...],
    limits: EligibilityLimits,
    started: float,
    filters: dict[str, set] | None = None,
):
    physical = list(dict.fromkeys(source.columns.values()))
    rows = 0
    groups = 0
    for item in files:
        try:
            with pq.ParquetFile(item.path, pre_buffer=False) as parquet:
                if any(parquet.schema_arrow.names.count(name) != 1 for name in physical):
                    raise EligibilityError("eligibility_invalid_columns")
                for group in range(parquet.metadata.num_row_groups):
                    groups += 1
                    group_rows = parquet.metadata.row_group(group).num_rows
                    if groups > limits.max_row_groups_per_source:
                        raise EligibilityError("eligibility_row_groups_limit")
                    if rows + group_rows > limits.max_rows_per_source:
                        raise EligibilityError("eligibility_rows_limit")
                    for batch in parquet.iter_batches(
                        batch_size=limits.batch_rows,
                        row_groups=[group],
                        columns=physical,
                        use_threads=True,
                    ):
                        if time.monotonic() - started > limits.runtime_seconds:
                            raise EligibilityError("eligibility_runtime_limit")
                        if filters:
                            mask = None
                            for logical, accepted in filters.items():
                                column = batch.column(
                                    batch.schema.get_field_index(source.columns[logical])
                                )
                                try:
                                    value_set = pa.array(list(accepted), type=column.type)
                                    matched = pc.fill_null(
                                        pc.is_in(column, value_set=value_set), False
                                    )
                                except (pa.ArrowException, TypeError, ValueError):
                                    raise EligibilityError("eligibility_filter_type") from None
                                mask = matched if mask is None else pc.and_(mask, matched)
                            batch = batch.filter(mask)
                            if batch.num_rows == 0:
                                continue
                        arrays = {
                            logical: batch.column(batch.schema.get_field_index(name)).to_pylist()
                            for logical, name in source.columns.items()
                        }
                        for index in range(batch.num_rows):
                            yield {name: values[index] for name, values in arrays.items()}
                    rows += group_rows
        except EligibilityError:
            raise
        except Exception:
            raise EligibilityError("eligibility_scan_failed") from None


def _base_source(source, extra: dict[str, str] | None = None) -> DimensionSource:
    columns = {name: physical for name, physical in source.columns.items() if physical is not None}
    if extra:
        columns.update(extra)
    return DimensionSource(source.path, columns)


def _adult(birth, occurred) -> bool:
    if isinstance(birth, datetime):
        birth = birth.date()
    if isinstance(occurred, datetime):
        occurred = occurred.date()
    if not isinstance(birth, date) or not isinstance(occurred, date) or occurred < birth:
        return False
    years = occurred.year - birth.year - ((occurred.month, occurred.day) < (birth.month, birth.day))
    return years >= 18


def _raw(values: frozenset[tuple]) -> set:
    return {value for _, value in values}


def audit_eligibility(
    mapping: EligibilityMapping, minimum_orders: int, minimum_events: int
) -> dict:
    limits = mapping.limits
    started = time.monotonic()
    sources = {
        "orders": _base_source(mapping.feasibility.orders, mapping.order_criteria_columns),
        "administrations": _base_source(mapping.feasibility.administrations),
        "observations": _base_source(mapping.feasibility.observations),
        "patients": mapping.patients,
        "encounters": mapping.encounters,
    }
    before = {name: _inventory(source, limits) for name, source in sources.items()}
    counts = Counter()
    selected_keys = set()
    order_rows = []
    order_filters = {
        "therapeutic_class": _raw(mapping.therapeutic_class_values),
        "route": _raw(mapping.route_values),
        "prn": _raw(mapping.non_prn_values),
        "frequency": _raw(mapping.one_time_frequency_values),
    }
    for row in _scan(sources["orders"], before["orders"], limits, started, filters=order_filters):
        counts["one_time_non_prn_orders"] += 1
        key = identity(row.get("order_id"))
        if key is None:
            counts["invalid_candidate_order_identities"] += 1
            continue
        if key not in selected_keys and len(selected_keys) >= limits.max_candidate_orders:
            counts["candidate_orders_not_retained"] += 1
            continue
        selected_keys.add(key)
        order_rows.append({name: row.get(name) for name in mapping.feasibility.orders.columns})
        if len(order_rows) > limits.max_retained_rows_per_source:
            raise EligibilityError("eligibility_retained_rows_limit")
    patient_keys = {identity(row.get("patient_id")) for row in order_rows} - {None}
    encounter_keys = {identity(row.get("encounter_id")) for row in order_rows} - {None}
    patients: dict[tuple, list] = {}
    retained_patient_rows = 0
    patient_filters = {
        "patient_id": {value for _, value in patient_keys},
        "current_status": _raw(mapping.current_values),
        "valid_status": _raw(mapping.valid_values),
    }
    for row in _scan(
        sources["patients"], before["patients"], limits, started, filters=patient_filters
    ):
        key = identity(row.get("patient_id"))
        patients.setdefault(key, []).append(row.get("birth_date"))
        retained_patient_rows += 1
        if retained_patient_rows > limits.max_retained_rows_per_source:
            raise EligibilityError("eligibility_retained_rows_limit")
    encounters: dict[tuple, list] = {}
    retained_encounter_rows = 0
    for row in _scan(
        sources["encounters"],
        before["encounters"],
        limits,
        started,
        filters={"encounter_id": {value for _, value in encounter_keys}},
    ):
        key = identity(row.get("encounter_id"))
        if key in encounter_keys:
            encounters.setdefault(key, []).append(row)
            retained_encounter_rows += 1
            if retained_encounter_rows > limits.max_retained_rows_per_source:
                raise EligibilityError("eligibility_retained_rows_limit")
    eligible_orders = []
    for row in order_rows:
        patient = identity(row.get("patient_id"))
        encounter = identity(row.get("encounter_id"))
        births = patients.get(patient, [])
        encounter_rows = encounters.get(encounter, [])
        adult = len(births) == 1 and _adult(births[0], row.get("occurred_at"))
        inpatient = (
            len(encounter_rows) == 1
            and identity(encounter_rows[0].get("patient_id")) == patient
            and criterion_identity(encounter_rows[0].get("patient_class"))
            in mapping.inpatient_values
        )
        counts["adult_orders"] += int(adult)
        counts["adult_inpatient_orders"] += int(adult and inpatient)
        if adult and inpatient:
            eligible_orders.append(row)
    eligible_keys = {identity(row.get("order_id")) for row in eligible_orders} - {None}
    observation_keys = {identity(row.get("observation_id")) for row in eligible_orders} - {None}
    administration_rows = []
    for row in _scan(
        sources["administrations"],
        before["administrations"],
        limits,
        started,
        filters={"order_id": {value for _, value in eligible_keys}},
    ):
        administration_rows.append(row)
        if len(administration_rows) > limits.max_retained_rows_per_source:
            raise EligibilityError("eligibility_retained_rows_limit")
    observation_rows = []
    for row in _scan(
        sources["observations"],
        before["observations"],
        limits,
        started,
        filters={"observation_id": {value for _, value in observation_keys}},
    ):
        observation_rows.append(row)
        if len(observation_rows) > limits.max_retained_rows_per_source:
            raise EligibilityError("eligibility_retained_rows_limit")
    after = {name: _inventory(source, limits) for name, source in sources.items()}
    if before != after:
        raise EligibilityError("eligibility_source_changed")
    outcome = analyze(
        eligible_orders,
        administration_rows,
        observation_rows,
        mapping.feasibility,
    )
    if outcome["status"] != "complete":
        raise EligibilityError("eligibility_outcome_incomplete")
    outcome_counts = outcome["counts"]
    classified_orders = (
        outcome_counts["accepted_execution_orders"]
        + outcome_counts["terminal_without_execution_orders"]
        + outcome_counts["right_censored_orders"]
    )
    orders_met = classified_orders >= minimum_orders
    events_met = outcome_counts["accepted_execution_orders"] >= minimum_events
    return {
        "schema_version": 1,
        "mode": "aggregate_cohort_eligibility",
        "data_class": "restricted_aggregate",
        "status": "complete",
        "source_stable": True,
        "population_counts_complete": counts["candidate_orders_not_retained"] == 0,
        "threshold_evidence_complete": orders_met and events_met,
        "thresholds": {
            "minimum_eligible_orders_met": orders_met,
            "minimum_execution_events_met": events_met,
            "ready": orders_met and events_met,
        },
        "counts": dict(counts),
        "outcome_counts": outcome_counts,
        "row_persistence": False,
        "patient_level_split_required": True,
        "laboratory_features_enabled": False,
    }
