"""Private mapping contract for a bounded frequency/PRN vocabulary audit."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from ies.feasibility.contract import ROOT


class CohortAuditError(ValueError):
    """Fixed error code for private cohort-audit failures."""


def require(condition: bool) -> None:
    if not condition:
        raise CohortAuditError("invalid_cohort_audit_mapping")


@dataclass(frozen=True, repr=False)
class VocabularySource:
    path: Path
    prn_column: str
    frequency_column: str


@dataclass(frozen=True, repr=False)
class VocabularyLimits:
    max_files: int
    max_entries: int
    max_row_groups: int
    max_rows: int
    max_source_bytes: int
    max_distinct_per_column: int
    minimum_report_count: int
    batch_rows: int
    runtime_seconds: int
    cpu_seconds: int
    cpus: int
    memory_mb: int


@dataclass(frozen=True, repr=False)
class VocabularyMapping:
    source: VocabularySource
    limits: VocabularyLimits


LIMIT_CAPS = {
    "max_files": 1_000,
    "max_entries": 2_000,
    "max_row_groups": 2_000,
    "max_rows": 500_000_000,
    "max_source_bytes": 64 * 1024**3,
    "max_distinct_per_column": 1_024,
    "minimum_report_count": 10_000,
    "batch_rows": 65_536,
    "runtime_seconds": 900,
    "cpu_seconds": 900,
    "cpus": 4,
    "memory_mb": 16_384,
}


def _absolute_path(value) -> Path:
    require(isinstance(value, str) and value and "\x00" not in value)
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts and path != Path("/"))
    require(not path.is_relative_to(ROOT))
    return path


def _column(value) -> str:
    require(
        isinstance(value, str)
        and 0 < len(value) <= 256
        and not any(character in value for character in ("\x00", "\n", "\r", "."))
    )
    return value


def parse_vocabulary_mapping(value: dict) -> VocabularyMapping:
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "schema_version",
            "execution_context",
            "institutional_access_confirmed",
            "mapping_reviewed",
            "protocol_frozen_reviewed",
            "purpose",
            "source",
            "limits",
        }
    )
    require(value["schema_version"] == 1)
    require(value["execution_context"] == "ucsf")
    require(value["institutional_access_confirmed"] is True)
    require(value["mapping_reviewed"] is True)
    require(value["protocol_frozen_reviewed"] is True)
    require(value["purpose"] == "frequency_prn_vocabulary")
    raw_source = value["source"]
    require(isinstance(raw_source, dict) and set(raw_source) == {"path", "columns"})
    columns = raw_source["columns"]
    require(isinstance(columns, dict) and set(columns) == {"prn", "frequency"})
    prn = _column(columns["prn"])
    frequency = _column(columns["frequency"])
    require(prn != frequency)
    raw_limits = value["limits"]
    require(isinstance(raw_limits, dict) and set(raw_limits) == set(LIMIT_CAPS))
    require(
        all(
            type(raw_limits[name]) is int and 1 <= raw_limits[name] <= maximum
            for name, maximum in LIMIT_CAPS.items()
        )
    )
    require(raw_limits["memory_mb"] >= 512)
    require(raw_limits["batch_rows"] <= raw_limits["max_rows"])
    return VocabularyMapping(
        VocabularySource(_absolute_path(raw_source["path"]), prn, frequency),
        VocabularyLimits(**raw_limits),
    )


def load_vocabulary_mapping(path: Path) -> tuple[VocabularyMapping, str]:
    try:
        content = path.read_bytes()
        mapping = parse_vocabulary_mapping(yaml.safe_load(content))
        return mapping, hashlib.sha256(content).hexdigest()
    except CohortAuditError:
        raise
    except Exception:
        raise CohortAuditError("invalid_cohort_audit_mapping") from None
