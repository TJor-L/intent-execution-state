"""Bounded Parquet footer inspection. Never reads batches, statistics, or values."""

import hashlib
import json
import os
from pathlib import Path

import pyarrow.parquet as pq


def audit_parquet(data_root: Path, max_files=12, max_directories=100) -> dict:
    if not 1 <= max_files <= 1000 or not 1 <= max_directories <= 10000:
        raise ValueError("Audit limits must be positive and bounded")
    if data_root.is_symlink() or not data_root.exists():
        raise ValueError("Audit root must exist and must not be a symlink")
    files = []
    failed = 0
    visited = 0
    entries_seen = 0
    truncated = False

    def inspect(path):
        nonlocal failed
        try:
            with pq.ParquetFile(path) as parquet:
                schema = [
                    {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                    for field in parquet.schema_arrow
                ]
                files.append(
                    {
                        "file_ordinal": len(files) + failed + 1,
                        "rows_in_footer": parquet.metadata.num_rows,
                        "row_groups": parquet.metadata.num_row_groups,
                        "fields": schema,
                        "schema_sha256": hashlib.sha256(
                            json.dumps(schema, sort_keys=True).encode()
                        ).hexdigest(),
                    }
                )
        except Exception:
            # Exception strings and paths can contain restricted identifiers.
            failed += 1

    if data_root.is_file():
        if data_root.suffix.lower() != ".parquet":
            raise ValueError("Expected a Parquet file or dataset directory")
        inspect(data_root)
    else:
        pending = [data_root]
        while pending:
            if visited >= max_directories or len(files) + failed >= max_files:
                truncated = True
                break
            directory = pending.pop()
            visited += 1
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        entries_seen += 1
                        if entries_seen > 10000 or len(files) + failed >= max_files:
                            truncated = True
                            break
                        if entry.is_symlink():
                            continue
                        if entry.is_file(follow_symlinks=False) and entry.name.endswith(".parquet"):
                            inspect(Path(entry.path))
                        elif entry.is_dir(follow_symlinks=False):
                            if len(pending) + visited < max_directories:
                                pending.append(Path(entry.path))
                            else:
                                truncated = True
                if entries_seen > 10000:
                    break
            except OSError:
                failed += 1
    return {
        "mode": "metadata_only",
        "data_class": "restricted_metadata",
        "files": files,
        "failures": failed,
        "directories_visited": visited,
        "truncated_or_limit_reached": truncated,
        "sampling": "bounded filesystem traversal; not representative or exhaustive",
        "note": "No row values, column statistics, paths, or arbitrary metadata emitted.",
    }
