"""Typed server-local mapping. Parsing does not stat, enumerate or read source data."""

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
ORDER_REQUIRED = {"order_id", "patient_id", "occurred_at", "available_at", "observation_end_at"}
ORDER_OPTIONAL = {
    "encounter_id",
    "discontinued_at",
    "discontinued_available_at",
    "ended_at",
    "ended_available_at",
}
ADMIN_REQUIRED = {"administration_id", "order_id", "patient_id", "occurred_at", "action"}
ADMIN_OPTIONAL = {"encounter_id", "available_at"}
LIMIT_CAPS = {
    "max_files_per_source": 64,
    "max_directories_per_source": 256,
    "max_entries_per_source": 10000,
    "max_rows_per_source": 100000,
    "max_keys": 100000,
    "batch_rows": 1024,
    "runtime_seconds": 900,
    "cpu_seconds": 900,
    "cpus": 4,
    "memory_mb": 4096,
}


class FeasibilityError(ValueError):
    """Only fixed, non-sensitive error codes may cross the command boundary."""


def require(condition: bool) -> None:
    if not condition:
        raise FeasibilityError("invalid_mapping")


@dataclass(frozen=True, repr=False)
class Source:
    path: Path
    columns: dict[str, str | None]


@dataclass(frozen=True, repr=False)
class Limits:
    max_files_per_source: int
    max_directories_per_source: int
    max_entries_per_source: int
    max_rows_per_source: int
    max_keys: int
    batch_rows: int
    runtime_seconds: int
    cpu_seconds: int
    cpus: int
    memory_mb: int


@dataclass(frozen=True, repr=False)
class Mapping:
    orders: Source
    administrations: Source
    qualifying_actions: frozenset[tuple[str, str | int]]
    encounter_policy: str
    administration_availability: str
    time_encoding: str
    horizon_hours: float
    limits: Limits


def identity(value) -> tuple[str, str | int] | None:
    # No coercion: integer 1 and string "1" cannot silently become the same identity.
    if type(value) is int:
        return ("integer", value)
    if isinstance(value, str) and 0 < len(value) <= 256:
        return ("string", value)
    return None


def absolute_path(value) -> Path:
    require(isinstance(value, str) and bool(value) and "\x00" not in value)
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and path != Path("/"))
    require(not path.is_relative_to(ROOT))
    return path


def source(value, required: set[str], optional: set[str]) -> Source:
    require(isinstance(value, dict) and set(value) == {"path", "columns"})
    path = absolute_path(value["path"])
    columns = value["columns"]
    require(isinstance(columns, dict) and set(columns) == required | optional)
    for logical, physical in columns.items():
        if logical in optional and physical is None:
            continue
        require(isinstance(physical, str) and 0 < len(physical) <= 256)
        require(not any(c in physical for c in ("\x00", "\n", "\r", ".")))
    return Source(path, dict(columns))


def parse_mapping(value: dict) -> Mapping:
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "schema_version",
            "execution_context",
            "institutional_access_confirmed",
            "mapping_reviewed",
            "source_coverage_reviewed",
            "qualifying_actions_reviewed",
            "terminal_semantics_reviewed",
            "laboratory_features_enabled",
            "time_encoding",
            "horizon_hours",
            "encounter_policy",
            "administration_availability",
            "qualifying_actions",
            "orders",
            "administrations",
            "limits",
        }
    )
    require(type(value["schema_version"]) is int and value["schema_version"] == 1)
    require(value["execution_context"] == "ucsf")
    for flag in (
        "institutional_access_confirmed",
        "mapping_reviewed",
        "source_coverage_reviewed",
        "qualifying_actions_reviewed",
    ):
        require(value[flag] is True)
    require(value["laboratory_features_enabled"] is False)
    require(value["time_encoding"] in ("numeric_hours", "timestamp_utc"))
    require(value["encounter_policy"] in ("reject_order", "count_only"))
    require(value["administration_availability"] in ("column", "occurrence_reviewed"))
    horizon = value["horizon_hours"]
    require(type(horizon) in (int, float) and math.isfinite(horizon) and 0 < horizon <= 168)
    actions = value["qualifying_actions"]
    require(isinstance(actions, list) and 1 <= len(actions) <= 64)
    require(all(identity(action) is not None for action in actions))
    orders = source(value["orders"], ORDER_REQUIRED, ORDER_OPTIONAL)
    administrations = source(value["administrations"], ADMIN_REQUIRED, ADMIN_OPTIONAL)
    require(
        (orders.columns["encounter_id"] is None)
        == (administrations.columns["encounter_id"] is None)
    )
    if value["administration_availability"] == "column":
        require(administrations.columns["available_at"] is not None)
    else:
        require(administrations.columns["available_at"] is None)
    for terminal in ("discontinued", "ended"):
        occurrence = orders.columns[f"{terminal}_at"]
        available = orders.columns[f"{terminal}_available_at"]
        require((occurrence is None) == (available is None))
        if occurrence is not None:
            require(value["terminal_semantics_reviewed"] is True)
    bounds = value["limits"]
    require(isinstance(bounds, dict) and set(bounds) == set(LIMIT_CAPS))
    require(all(type(bounds[k]) is int and 1 <= bounds[k] <= cap for k, cap in LIMIT_CAPS.items()))
    require(bounds["memory_mb"] >= 512)
    require(bounds["batch_rows"] <= bounds["max_rows_per_source"])
    return Mapping(
        orders,
        administrations,
        frozenset(identity(a) for a in actions),
        value["encounter_policy"],
        value["administration_availability"],
        value["time_encoding"],
        float(horizon),
        Limits(**bounds),
    )


def load_mapping(path: Path) -> Mapping:
    return load_mapping_snapshot(path)[0]


def load_mapping_snapshot(path: Path) -> tuple[Mapping, str]:
    """Validate and fingerprint exactly the same bytes, without persisting a private copy."""
    try:
        content = path.read_bytes()
        return parse_mapping(yaml.safe_load(content)), hashlib.sha256(content).hexdigest()
    except Exception:
        raise FeasibilityError("invalid_mapping") from None
