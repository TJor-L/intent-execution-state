"""Typed server-local mapping. Parsing does not stat, enumerate or read source data."""

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

ROOT = Path(__file__).resolve().parents[3]
ORDER_REQUIRED = {"order_id", "patient_id", "occurred_at", "available_at", "observation_id"}
ORDER_OPTIONAL = {
    "encounter_id",
    "discontinued_at",
    "discontinued_available_at",
    "ended_at",
    "ended_available_at",
}
ADMIN_REQUIRED = {"administration_id", "order_id", "patient_id", "occurred_at", "action"}
ADMIN_OPTIONAL = {"encounter_id", "available_at", "documentation_status"}
OBSERVATION_REQUIRED = {"observation_id", "patient_id", "ended_at", "available_at"}
OBSERVATION_OPTIONAL = {"encounter_id"}
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
class NaiveTimePolicy:
    clock: str
    timezone: ZoneInfo | None
    ambiguous: str
    evidence_reference: str


@dataclass(frozen=True, repr=False)
class EqualityPolicy:
    evidence_reference: str
    exclusion_evidence_reference: str
    contemporaneous_values: frozenset[tuple[str, str | int]]
    retrospective_values: frozenset[tuple[str, str | int]]


@dataclass(frozen=True, repr=False)
class Mapping:
    orders: Source
    administrations: Source
    observations: Source
    qualifying_actions: frozenset[tuple[str, str | int]]
    encounter_policy: str
    observation_encounter_policy: str
    administration_availability: str
    occurrence_equality_policy: EqualityPolicy | None
    time_encoding: str
    naive_time_policy: NaiveTimePolicy | None
    horizon_hours: float
    limits: Limits

    @property
    def sources(self) -> tuple[Source, ...]:
        return self.orders, self.administrations, self.observations


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


def evidence(value) -> str:
    # Private, server-local provenance. It must never be copied into public reports.
    require(isinstance(value, str) and 0 < len(value.strip()) <= 2048)
    require("\x00" not in value)
    return value


def identity_set(value) -> frozenset[tuple[str, str | int]]:
    require(isinstance(value, list) and 1 <= len(value) <= 64)
    require(all(identity(item) is not None for item in value))
    return frozenset(identity(item) for item in value)


def naive_policy(value, encoding) -> NaiveTimePolicy | None:
    if encoding != "timestamp_naive":
        require(value is None)
        return None
    require(
        isinstance(value, dict)
        and set(value)
        == {"reviewed", "clock", "timezone", "ambiguous", "nonexistent", "evidence_reference"}
    )
    require(value["reviewed"] is True)
    require(value["clock"] in ("named_timezone", "shifted_common"))
    require(value["ambiguous"] in ("reject", "earlier", "later"))
    # Moving nonexistent wall times would invent event times; no repair is implemented.
    require(value["nonexistent"] == "reject")
    zone = None
    if value["clock"] == "named_timezone":
        require(isinstance(value["timezone"], str) and bool(value["timezone"]))
        try:
            zone = ZoneInfo(value["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise FeasibilityError("invalid_mapping") from None
    else:
        require(value["timezone"] is None and value["ambiguous"] == "reject")
    return NaiveTimePolicy(
        value["clock"], zone, value["ambiguous"], evidence(value["evidence_reference"])
    )


def equality_policy(value, availability) -> EqualityPolicy | None:
    if availability == "column":
        require(value is None)
        return None
    require(
        isinstance(value, dict)
        and set(value) == {"reviewed", "evidence_reference", "retrospective_exclusion"}
    )
    require(value["reviewed"] is True)
    exclusion = value["retrospective_exclusion"]
    require(
        isinstance(exclusion, dict)
        and set(exclusion)
        == {
            "reviewed",
            "evidence_reference",
            "contemporaneous_values",
            "retrospective_values",
        }
    )
    require(exclusion["reviewed"] is True)
    contemporaneous = identity_set(exclusion["contemporaneous_values"])
    retrospective = identity_set(exclusion["retrospective_values"])
    require(not contemporaneous & retrospective)
    return EqualityPolicy(
        evidence(value["evidence_reference"]),
        evidence(exclusion["evidence_reference"]),
        contemporaneous,
        retrospective,
    )


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
            "observation_linkage_reviewed",
            "observation_end_reviewed",
            "qualifying_actions_reviewed",
            "terminal_semantics_reviewed",
            "laboratory_features_enabled",
            "time_encoding",
            "naive_time_policy",
            "horizon_hours",
            "encounter_policy",
            "observation_encounter_policy",
            "administration_availability",
            "occurrence_equality_policy",
            "qualifying_actions",
            "orders",
            "administrations",
            "observations",
            "limits",
        }
    )
    require(type(value["schema_version"]) is int and value["schema_version"] == 2)
    require(value["execution_context"] == "ucsf")
    for flag in (
        "institutional_access_confirmed",
        "mapping_reviewed",
        "source_coverage_reviewed",
        "observation_linkage_reviewed",
        "observation_end_reviewed",
        "qualifying_actions_reviewed",
    ):
        require(value[flag] is True)
    require(value["laboratory_features_enabled"] is False)
    require(value["time_encoding"] in ("numeric_hours", "timestamp_utc", "timestamp_naive"))
    clock = naive_policy(value["naive_time_policy"], value["time_encoding"])
    require(value["encounter_policy"] in ("reject_order", "count_only"))
    require(value["observation_encounter_policy"] in ("reject_order", "count_only"))
    require(value["administration_availability"] in ("column", "occurrence_reviewed"))
    equality = equality_policy(
        value["occurrence_equality_policy"], value["administration_availability"]
    )
    horizon = value["horizon_hours"]
    require(type(horizon) in (int, float) and math.isfinite(horizon) and 0 < horizon <= 168)
    actions = identity_set(value["qualifying_actions"])
    orders = source(value["orders"], ORDER_REQUIRED, ORDER_OPTIONAL)
    administrations = source(value["administrations"], ADMIN_REQUIRED, ADMIN_OPTIONAL)
    observations = source(value["observations"], OBSERVATION_REQUIRED, OBSERVATION_OPTIONAL)
    require(
        (orders.columns["encounter_id"] is None)
        == (administrations.columns["encounter_id"] is None)
    )
    require(
        observations.columns["encounter_id"] is None or orders.columns["encounter_id"] is not None
    )
    if value["administration_availability"] == "column":
        require(administrations.columns["available_at"] is not None)
        require(administrations.columns["documentation_status"] is None)
    else:
        require(administrations.columns["available_at"] is None)
        require(administrations.columns["documentation_status"] is not None)
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
        orders=orders,
        administrations=administrations,
        observations=observations,
        qualifying_actions=actions,
        encounter_policy=value["encounter_policy"],
        observation_encounter_policy=value["observation_encounter_policy"],
        administration_availability=value["administration_availability"],
        occurrence_equality_policy=equality,
        time_encoding=value["time_encoding"],
        naive_time_policy=clock,
        horizon_hours=float(horizon),
        limits=Limits(**bounds),
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
