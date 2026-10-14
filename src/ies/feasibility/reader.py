"""Bounded projected Parquet reads. No joins spill to disk and no rows are persisted."""

import os
from contextlib import ExitStack, closing
from math import gcd
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ies.feasibility.analysis import Budget, analyze
from ies.feasibility.contract import ROOT, FeasibilityError, Mapping, Source


def files(source: Source, budget: Budget):
    limits = budget.mapping.limits
    root = source.path
    if root.is_symlink() or root.resolve().is_relative_to(ROOT):
        raise FeasibilityError("invalid_source")
    visited = found = entries_seen = 0
    stopped = False

    def walk(path):
        nonlocal visited, found, entries_seen, stopped
        budget.check_time()
        if path.is_symlink():
            raise FeasibilityError("symlink_source")
        if path.is_file():
            if path.suffix.lower() == ".parquet":
                if found >= limits.max_files_per_source:
                    budget.reached["files"] = True
                    stopped = True
                    return
                found += 1
                yield path
            return
        if not path.is_dir():
            raise FeasibilityError("invalid_source")
        if visited >= limits.max_directories_per_source:
            budget.reached["directories"] = True
            stopped = True
            return
        visited += 1
        with os.scandir(path) as entries:
            for entry in entries:
                budget.check_time()
                if entries_seen >= limits.max_entries_per_source:
                    budget.reached["entries"] = True
                    stopped = True
                    return
                entries_seen += 1
                if entry.is_symlink():
                    # Silently skipping a partition would falsely imply complete coverage.
                    raise FeasibilityError("symlink_source")
                yield from walk(Path(entry.path))
                if stopped:
                    return

    yield from walk(root)
    if found == 0 and not any(budget.reached.values()):
        raise FeasibilityError("empty_source")


def rows(source: Source, budget: Budget):
    count = 0
    columns = list(dict.fromkeys(c for c in source.columns.values() if c is not None))
    with closing(files(source, budget)) as paths:
        for path in paths:
            budget.check_time()
            if count >= budget.mapping.limits.max_rows_per_source:
                budget.reached["rows"] = True
                return
            with pq.ParquetFile(path, pre_buffer=False) as parquet:
                schema = parquet.schema_arrow
                for name in columns:
                    if schema.names.count(name) != 1:
                        raise FeasibilityError("invalid_columns")
                    dtype = schema.field(name).type
                    if not (
                        pa.types.is_string(dtype)
                        or pa.types.is_large_string(dtype)
                        or pa.types.is_integer(dtype)
                        or pa.types.is_floating(dtype)
                        or pa.types.is_timestamp(dtype)
                        or pa.types.is_null(dtype)
                    ):
                        raise FeasibilityError("unsupported_column_type")
                remaining = budget.mapping.limits.max_rows_per_source - count
                take = min(remaining, parquet.metadata.num_rows)
                size = min(budget.mapping.limits.batch_rows, remaining)
                read = 0
                # Batch sizes divide the remaining allowance, so no excess rows are yielded
                # or converted. Parquet still performs I/O/decompression at page granularity.
                for group in range(parquet.metadata.num_row_groups):
                    if read >= take:
                        break
                    group_take = min(take - read, parquet.metadata.row_group(group).num_rows)
                    group_read = 0
                    for batch in parquet.iter_batches(
                        batch_size=gcd(size, group_take) or 1,
                        row_groups=[group],
                        columns=columns,
                        use_threads=False,
                    ):
                        budget.check_time()
                        batch = batch.slice(0, min(batch.num_rows, group_take - group_read))
                        group_read += batch.num_rows
                        read += batch.num_rows
                        count += batch.num_rows
                        for physical in batch.to_pylist():
                            yield {
                                logical: physical.get(column) if column else None
                                for logical, column in source.columns.items()
                            }
                        if group_read >= group_take:
                            break
                if take < parquet.metadata.num_rows:
                    budget.reached["rows"] = True
                    return


def inspect_sources(mapping: Mapping) -> dict:
    budget = Budget(mapping)
    pa.set_cpu_count(mapping.limits.cpus)
    with ExitStack() as stack:
        sources = [stack.enter_context(closing(rows(source, budget))) for source in mapping.sources]
        return analyze(*sources, mapping, budget)
