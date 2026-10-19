"""Bounded schema reconnaissance, not format conformance or clinical feasibility.

Signatures below contain public OMOP CDM 5.4 names, not a UCSF column mapping:
https://ohdsi.github.io/CommonDataModel/cdm54.html
Only Parquet header/trailer/footer bytes are opened. No data pages are read.
"""

import os
import stat
from collections import deque
from pathlib import Path

MODE = "bounded_format_probe"
LIMITS = {
    "max_files": 12,
    "max_directories": 100,
    "max_entries": 10000,
    "max_footer_bytes": 8 * 1024**2,
    "max_total_footer_bytes": 32 * 1024**2,
    "worker_seconds": 120,
    "cpus": 2,
    "memory_mb": 4096,
}
SIGNATURES = {
    "drug_exposure": {
        "drug_exposure_id",
        "person_id",
        "drug_concept_id",
        "drug_exposure_start_date",
        "drug_type_concept_id",
    },
    "person": {"person_id", "gender_concept_id", "year_of_birth", "race_concept_id"},
    "visit_occurrence": {
        "visit_occurrence_id",
        "person_id",
        "visit_concept_id",
        "visit_start_date",
    },
    "observation_period": {
        "observation_period_id",
        "person_id",
        "observation_period_start_date",
        "observation_period_end_date",
        "period_type_concept_id",
    },
    "concept": {"concept_id", "concept_name", "domain_id", "vocabulary_id", "concept_class_id"},
    "cdm_source": {"cdm_source_name", "cdm_source_abbreviation", "cdm_version", "cdm_release_date"},
}


def plan_format_probe() -> dict:
    return {
        "mode": MODE,
        "submitted": False,
        "limits": dict(LIMITS),
        "metadata_only": True,
        "row_values_read": False,
        "column_statistics_inspected": False,
        "model_fitted": False,
        "validation_split_evaluated": False,
        "test_split_evaluated": False,
        "format_confirmation": False,
        "clinical_advancement_decision": "not_applicable",
    }


def _footer_schema(path: Path, budget: dict):
    import pyarrow as pa
    import pyarrow.parquet as pq

    # O_NOFOLLOW + fstat reject links and devices even if a directory entry changes.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    # Unbuffered: a four-byte header read must not prefetch adjacent data pages.
    with os.fdopen(fd, "rb", buffering=0) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size < 12:
            raise ValueError("unsupported_file")
        if stream.read(4) != b"PAR1":
            raise ValueError("unsupported_parquet")
        stream.seek(-8, os.SEEK_END)
        trailer = stream.read(8)
        size = int.from_bytes(trailer[:4], "little")
        if trailer[4:] != b"PAR1" or not 0 < size <= before.st_size - 12:
            raise ValueError("unsupported_parquet")
        if size > min(LIMITS["max_footer_bytes"], budget["remaining"]):
            return None
        # Charge before reading/decoding, including corrupt footers that later fail.
        budget["remaining"] -= size
        stream.seek(-8 - size, os.SEEK_END)
        footer = stream.read(size)
        after = os.fstat(stream.fileno())
        if len(footer) != size or (before.st_size, before.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ):
            raise ValueError("source_changed")
    # Give Arrow a footer-only container, so it cannot read source data pages even
    # if its implementation prefetches. Do not inspect key/value metadata or stats.
    with pq.ParquetFile(
        pa.BufferReader(b"PAR1" + footer + trailer),
        thrift_string_size_limit=1024**2,
        thrift_container_size_limit=100000,
    ) as parquet:
        schema = parquet.schema_arrow
        if len(schema) > 1024:
            raise ValueError("schema_limit")
        names = [name.lower() for name in schema.names]
        if len(set(names)) != len(names):
            raise ValueError("ambiguous_schema")
        matches = sorted(name for name, required in SIGNATURES.items() if required <= set(names))
        storage = "not_observed"
        if "drug_exposure" in matches and "drug_exposure_start_datetime" in names:
            field = schema.field(names.index("drug_exposure_start_datetime"))
            storage = "timestamp" if pa.types.is_timestamp(field.type) else "other_declared_type"
        return {"signatures": matches, "drug_datetime_storage": storage}


def probe_format(root: Path) -> dict:
    """Generated-testable engine; the clinical CLI is guarded by its Slurm runner.

    Directory breadth-first sampling prefers one file per visited directory before
    extra partitions. Enumeration and footer reads have independent fixed caps.
    No absence, population coverage, non-nullness, or semantic claim is possible.
    """
    if root.is_symlink() or not root.exists():
        raise ValueError("invalid_probe_root")
    first, extra = [], []
    pending = deque([root]) if root.is_dir() else deque()
    directories = entries_seen = failures = 0
    limited = skipped_links = non_parquet = False
    if root.is_file():
        if root.suffix.lower() == ".parquet":
            first.append(root)
        else:
            non_parquet = True
    while pending:
        if directories >= LIMITS["max_directories"] or entries_seen >= LIMITS["max_entries"]:
            limited = True
            break
        directory = pending.popleft()
        directories += 1
        found_first = False
        try:
            if directory.is_symlink():
                skipped_links = True
                continue
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entries_seen >= LIMITS["max_entries"]:
                        limited = True
                        break
                    entries_seen += 1
                    if entry.is_symlink():
                        skipped_links = True
                    elif entry.is_dir(follow_symlinks=False):
                        if len(pending) + directories < LIMITS["max_directories"]:
                            pending.append(Path(entry.path))
                        else:
                            limited = True
                    elif entry.is_file(follow_symlinks=False):
                        if Path(entry.name).suffix.lower() != ".parquet":
                            non_parquet = True
                            continue
                        target = extra if found_first else first
                        found_first = True
                        if len(target) < LIMITS["max_files"]:
                            target.append(Path(entry.path))
                        else:
                            limited = True
        except OSError:
            failures += 1
    candidates = first + extra
    limited |= len(candidates) > LIMITS["max_files"]
    files = []
    budget = {"remaining": LIMITS["max_total_footer_bytes"]}
    for path in candidates[: LIMITS["max_files"]]:
        try:
            value = _footer_schema(path, budget)
            if value is None:
                limited = True
            else:
                files.append(value)
        except Exception:
            failures += 1
    return {
        "schema_version": 1,
        "mode": MODE,
        "status": "complete",
        "data_class": "restricted_metadata",
        "files": files,
        "read_failures": failures,
        "directories_visited": directories,
        "footer_bytes_read": LIMITS["max_total_footer_bytes"] - budget["remaining"],
        "limit_reached": limited,
        "symlinks_skipped": skipped_links,
        "non_parquet_files_seen": non_parquet,
        "sampling": "bounded_directory_breadth_first_not_representative",
    }


def summarize_format_probe(report: dict) -> dict:
    """Project onto fixed categories only; never relay arbitrary input strings."""
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != 1
        or report.get("mode") != MODE
        or report.get("status") != "complete"
        or report.get("data_class") != "restricted_metadata"
        or not isinstance(report.get("files"), list)
        or len(report["files"]) > LIMITS["max_files"]
    ):
        raise ValueError("invalid_format_report")
    observed, storage = set(), set()
    for file in report["files"]:
        if (
            not isinstance(file, dict)
            or set(file) != {"signatures", "drug_datetime_storage"}
            or not isinstance(file["signatures"], list)
            or any(type(name) is not str or name not in SIGNATURES for name in file["signatures"])
            or file["drug_datetime_storage"]
            not in {"not_observed", "timestamp", "other_declared_type"}
        ):
            raise ValueError("invalid_format_report")
        observed.update(file["signatures"])
        if "drug_exposure" in file["signatures"]:
            storage.add(file["drug_datetime_storage"])
    for key in ("limit_reached", "symlinks_skipped", "non_parquet_files_seen"):
        if type(report.get(key)) is not bool:
            raise ValueError("invalid_format_report")
    if type(report.get("read_failures")) is not int or report["read_failures"] < 0:
        raise ValueError("invalid_format_report")
    return {
        "format_candidate": "omop_like_schema" if observed else "unidentified_in_sample",
        "format_confirmed": False,
        "new_server_update_verified": False,
        "readable_parquet_observed": bool(report["files"]),
        "omop_signature_observed": {name: name in observed for name in SIGNATURES},
        "drug_datetime_storage": sorted(storage),
        "declared_datetime_is_not_verified_precision": True,
        "limit_reached": report["limit_reached"],
        "read_errors_observed": report["read_failures"] > 0,
        "symlinks_skipped": report["symlinks_skipped"],
        "non_parquet_files_seen": report["non_parquet_files_seen"],
        "row_values_read": False,
        "source_event_linkage": "not_assessed",
        "order_administration_distinction": "not_assessed",
        "occurrence_availability_semantics": "not_assessed",
        "research_feasibility": "not_established",
        "coverage": "bounded_metadata_sample_only_no_absence_inference",
    }
