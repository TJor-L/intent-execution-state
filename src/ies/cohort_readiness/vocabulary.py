"""Projected, aggregate-only frequency/PRN vocabulary scan."""

from __future__ import annotations

import os
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq

from ies.cohort_readiness.contract import CohortAuditError, VocabularyMapping


@dataclass(frozen=True, repr=False)
class FileState:
    path: Path
    size: int
    mtime_ns: int


def _fail(code: str = "cohort_vocabulary_failed") -> None:
    raise CohortAuditError(code)


def inventory(mapping: VocabularyMapping) -> tuple[FileState, ...]:
    root = mapping.source.path
    limits = mapping.limits
    if root.is_symlink() or not root.exists():
        _fail()
    if root.is_file():
        candidates = [root]
    else:
        candidates = []
        entries = 0
        try:
            with os.scandir(root) as stream:
                for entry in stream:
                    entries += 1
                    if entries > limits.max_entries:
                        _fail("cohort_vocabulary_entries_limit")
                    if entry.is_symlink():
                        _fail()
                    if entry.is_dir(follow_symlinks=False):
                        _fail("cohort_vocabulary_nested_source")
                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(
                        ".parquet"
                    ):
                        candidates.append(Path(entry.path))
        except CohortAuditError:
            raise
        except OSError:
            _fail()
    if not candidates or len(candidates) > limits.max_files:
        _fail("cohort_vocabulary_files_limit")
    states = []
    for path in sorted(candidates):
        try:
            stat = path.stat(follow_symlinks=False)
        except OSError:
            _fail()
        states.append(FileState(path.resolve(), stat.st_size, stat.st_mtime_ns))
    if sum(item.size for item in states) > limits.max_source_bytes:
        _fail("cohort_vocabulary_bytes_limit")
    return tuple(states)


def _private_scalar(value):
    if value is None:
        return None
    if type(value) is bool:
        return ("boolean", value)
    if type(value) is int:
        return ("integer", value)
    if isinstance(value, str) and len(value) <= 256 and "\x00" not in value:
        return ("string", value)
    return ("invalid", None)


def _private_values(counter: Counter, minimum_count: int) -> dict:
    values = []
    suppressed_rows = 0
    suppressed_distinct = 0
    for (kind, value), count in sorted(counter.items(), key=lambda item: (-item[1], item[0][0])):
        if kind == "invalid" or count < minimum_count:
            suppressed_rows += count
            suppressed_distinct += 1
        else:
            values.append({"kind": kind, "value": value, "count": count})
    return {
        "values": values,
        "suppressed_rows": suppressed_rows,
        "suppressed_distinct_values": suppressed_distinct,
        "distinct_values": len(counter),
    }


def scan_vocabulary(mapping: VocabularyMapping) -> dict:
    before = inventory(mapping)
    limits = mapping.limits
    columns = [mapping.source.prn_column, mapping.source.frequency_column]
    counters = {"prn": Counter(), "frequency": Counter()}
    nulls = {"prn": 0, "frequency": 0}
    rows = 0
    row_groups = 0
    start = time.monotonic()
    for item in before:
        try:
            with pq.ParquetFile(item.path, pre_buffer=False) as parquet:
                if any(parquet.schema_arrow.names.count(column) != 1 for column in columns):
                    _fail("cohort_vocabulary_invalid_columns")
                for group in range(parquet.metadata.num_row_groups):
                    row_groups += 1
                    group_rows = parquet.metadata.row_group(group).num_rows
                    if row_groups > limits.max_row_groups:
                        _fail("cohort_vocabulary_row_groups_limit")
                    if rows + group_rows > limits.max_rows:
                        _fail("cohort_vocabulary_rows_limit")
                    for batch in parquet.iter_batches(
                        batch_size=limits.batch_rows,
                        row_groups=[group],
                        columns=columns,
                        use_threads=True,
                    ):
                        if time.monotonic() - start > limits.runtime_seconds:
                            _fail("cohort_vocabulary_runtime_limit")
                        for logical, array in zip(("prn", "frequency"), batch.columns, strict=True):
                            for value in array.to_pylist():
                                scalar = _private_scalar(value)
                                if scalar is None:
                                    nulls[logical] += 1
                                else:
                                    counters[logical][scalar] += 1
                                    if len(counters[logical]) > limits.max_distinct_per_column:
                                        _fail("cohort_vocabulary_distinct_limit")
                    rows += group_rows
        except CohortAuditError:
            raise
        except Exception:
            _fail()
    after = inventory(mapping)
    if before != after:
        _fail("cohort_vocabulary_source_changed")
    return {
        "schema_version": 1,
        "mode": "frequency_prn_vocabulary",
        "data_class": "restricted_aggregate",
        "status": "complete",
        "source_stable": True,
        "scan": {
            "files": len(before),
            "row_groups": row_groups,
            "rows": rows,
            "source_bytes": sum(item.size for item in before),
            "projected_columns": 2,
        },
        "vocabulary": {
            name: {
                "null_rows": nulls[name],
                **_private_values(counters[name], limits.minimum_report_count),
            }
            for name in ("prn", "frequency")
        },
        "complete_for_reviewed_snapshot": True,
        "row_persistence": False,
    }
