"""Separately authorized full-source preparation of a restricted coherent extract."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml

from ies.feasibility.access import load_access_snapshot
from ies.feasibility.contract import (
    ROOT,
    FeasibilityError,
    Mapping,
    Source,
    identity,
    load_mapping_snapshot,
)
from ies.io import sha256, write_json

ROLES = ("orders", "administrations", "observations")
SEED_COUNT = 64
MAX_FILES_PER_SOURCE = 1_000
MAX_ENTRIES_PER_SOURCE = 2_000
MAX_ROW_GROUPS_PER_SOURCE = 2_000
MAX_ROWS_PER_SOURCE = 500_000_000
MAX_BYTES_PER_SOURCE = 64 * 1024**3
MAX_RETAINED_ROWS_PER_SOURCE = 33_333
MAX_RETAINED_KEYS = 100_000
BATCH_ROWS = 65_536


@dataclass(frozen=True, repr=False)
class FileState:
    path: Path
    size: int
    mtime_ns: int


def fail(code: str = "preparation_failed") -> None:
    raise FeasibilityError(code)


def inventory(source: Source) -> tuple[FileState, ...]:
    root = source.path
    if root.is_symlink() or not root.exists():
        fail()
    if root.is_file():
        candidates = [root]
        entries = 1
    else:
        candidates = []
        entries = 0
        try:
            with os.scandir(root) as stream:
                for entry in stream:
                    entries += 1
                    if entries > MAX_ENTRIES_PER_SOURCE:
                        fail("preparation_entries_limit")
                    if entry.is_symlink():
                        fail()
                    if entry.is_dir(follow_symlinks=False):
                        fail("preparation_nested_source")
                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(
                        ".parquet"
                    ):
                        candidates.append(Path(entry.path))
        except OSError:
            fail()
    if not candidates or len(candidates) > MAX_FILES_PER_SOURCE:
        fail("preparation_files_limit")
    states = []
    for path in sorted(candidates):
        try:
            stat = path.stat(follow_symlinks=False)
        except OSError:
            fail()
        states.append(FileState(path.resolve(), stat.st_size, stat.st_mtime_ns))
    if sum(item.size for item in states) > MAX_BYTES_PER_SOURCE:
        fail("preparation_bytes_limit")
    return tuple(states)


def inventory_digest(inventories: dict[str, tuple[FileState, ...]]) -> str:
    digest = hashlib.sha256()
    for role in ROLES:
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


def projected_schema(source: Source, first: Path) -> pa.Schema:
    try:
        with pq.ParquetFile(first, pre_buffer=False) as parquet:
            schema = parquet.schema_arrow
    except Exception:
        fail()
    fields = []
    for logical, physical in source.columns.items():
        if physical is None:
            continue
        if schema.names.count(physical) != 1:
            fail("preparation_invalid_columns")
        fields.append(pa.field(logical, schema.field(physical).type, nullable=True))
    return pa.schema(fields)


def raw_identity_values(keys: set[tuple[str, str | int]], dtype: pa.DataType) -> pa.Array:
    raw = [value for _, value in sorted(keys)]
    try:
        return pa.array(raw, type=dtype)
    except (pa.ArrowException, TypeError, ValueError):
        fail("preparation_identity_type")


def batches(
    source: Source,
    files: tuple[FileState, ...],
    columns: list[str],
    counters: dict,
):
    for item in files:
        try:
            with pq.ParquetFile(item.path, pre_buffer=False) as parquet:
                for name in columns:
                    if parquet.schema_arrow.names.count(name) != 1:
                        fail("preparation_invalid_columns")
                for group in range(parquet.metadata.num_row_groups):
                    counters["row_groups"] += 1
                    rows = parquet.metadata.row_group(group).num_rows
                    counters["rows"] += rows
                    if counters["row_groups"] > MAX_ROW_GROUPS_PER_SOURCE:
                        fail("preparation_row_groups_limit")
                    if counters["rows"] > MAX_ROWS_PER_SOURCE:
                        fail("preparation_rows_limit")
                    yield from parquet.iter_batches(
                        batch_size=BATCH_ROWS,
                        row_groups=[group],
                        columns=columns,
                        use_threads=True,
                    )
        except FeasibilityError:
            raise
        except Exception:
            fail()


def select_seed(mapping: Mapping, files: tuple[FileState, ...]) -> set[tuple[str, str | int]]:
    physical = mapping.orders.columns["order_id"]
    counters = {"row_groups": 0, "rows": 0}
    selected: set[tuple[str, str | int]] = set()
    for batch in batches(mapping.orders, files, [physical], counters):
        for value in batch.column(0).to_pylist():
            key = identity(value)
            if key is not None:
                selected.add(key)
                if len(selected) == SEED_COUNT:
                    return selected
    if not selected:
        fail("preparation_empty_seed")
    return selected


def scan_matches(
    source: Source,
    files: tuple[FileState, ...],
    identity_logical: str,
    keys: set[tuple[str, str | int]],
) -> tuple[pa.Table, dict]:
    physical_columns = list(dict.fromkeys(v for v in source.columns.values() if v is not None))
    schema = projected_schema(source, files[0].path)
    key_physical = source.columns[identity_logical]
    counters = {
        "files": len(files),
        "row_groups": 0,
        "rows": 0,
        "bytes": sum(item.size for item in files),
        "retained_rows": 0,
    }
    retained = []
    value_set = None
    for batch in batches(source, files, physical_columns, counters):
        key_array = batch.column(batch.schema.get_field_index(key_physical))
        if value_set is None:
            value_set = raw_identity_values(keys, key_array.type)
        try:
            mask = pc.fill_null(pc.is_in(key_array, value_set=value_set), False)
            selected = pa.Table.from_batches([batch]).filter(mask)
        except (pa.ArrowException, TypeError, ValueError):
            fail()
        if selected.num_rows == 0:
            continue
        counters["retained_rows"] += selected.num_rows
        if counters["retained_rows"] > MAX_RETAINED_ROWS_PER_SOURCE:
            fail("preparation_retained_rows_limit")
        selected = pa.Table.from_arrays(
            [selected[physical] for physical in source.columns.values() if physical is not None],
            names=[logical for logical, physical in source.columns.items() if physical is not None],
        )
        retained.append(selected)
    if retained:
        table = pa.concat_tables(retained, promote_options="default").select(schema.names)
    else:
        table = pa.Table.from_arrays([pa.array([], type=f.type) for f in schema], schema=schema)
    return table, counters


def retained_identities(table: pa.Table, column: str) -> set[tuple[str, str | int]]:
    values = {key for value in table[column].to_pylist() if (key := identity(value)) is not None}
    if len(values) > MAX_RETAINED_KEYS:
        fail("preparation_retained_keys_limit")
    return values


def private_mapping(raw: dict, paths: dict[str, Path]) -> dict:
    result = json.loads(json.dumps(raw))
    for role in ROLES:
        result[role]["path"] = str(paths[role])
        result[role]["columns"] = {
            logical: logical if physical is not None else None
            for logical, physical in result[role]["columns"].items()
        }
    result["limits"] = {
        "max_files_per_source": 4,
        "max_directories_per_source": 4,
        "max_entries_per_source": 20,
        "max_rows_per_source": MAX_RETAINED_ROWS_PER_SOURCE,
        "max_keys": MAX_RETAINED_KEYS,
        "batch_rows": 256,
        "runtime_seconds": 60,
        "cpu_seconds": 60,
        "cpus": 1,
        "memory_mb": 2048,
    }
    return result


def prepare_coherent(mapping_path: Path, output_dir: Path) -> dict:
    mapping, mapping_digest = load_mapping_snapshot(mapping_path)
    raw = yaml.safe_load(mapping_path.read_bytes())
    output = output_dir.resolve()
    if not output_dir.is_absolute() or output.exists() or output.is_relative_to(ROOT):
        fail("preparation_output_boundary")
    for source in mapping.sources:
        root = source.path.resolve()
        if output.is_relative_to(root) or root.is_relative_to(output):
            fail("preparation_output_boundary")
    inventories = {role: inventory(getattr(mapping, role)) for role in ROLES}
    before = inventory_digest(inventories)
    seed = select_seed(mapping, inventories["orders"])
    orders, order_counts = scan_matches(mapping.orders, inventories["orders"], "order_id", seed)
    observation_keys = retained_identities(orders, "observation_id")
    administrations, administration_counts = scan_matches(
        mapping.administrations, inventories["administrations"], "order_id", seed
    )
    observations, observation_counts = scan_matches(
        mapping.observations,
        inventories["observations"],
        "observation_id",
        observation_keys,
    )
    after_inventories = {role: inventory(getattr(mapping, role)) for role in ROLES}
    after = inventory_digest(after_inventories)
    if inventories != after_inventories or before != after:
        fail("preparation_source_changed")

    old_umask = os.umask(0o077)
    try:
        output.mkdir(parents=True, mode=0o700)
        extracts = output / "extracts"
        extracts.mkdir(mode=0o700)
        paths = {role: extracts / f"{role}.parquet" for role in ROLES}
        tables = {
            "orders": orders,
            "administrations": administrations,
            "observations": observations,
        }
        for role, table in tables.items():
            pq.write_table(
                table,
                paths[role],
                compression="zstd",
                row_group_size=max(1, table.num_rows),
                use_dictionary=True,
            )
            os.chmod(paths[role], 0o600)
            with pq.ParquetFile(paths[role], pre_buffer=False) as parquet:
                if (
                    parquet.metadata.num_row_groups != 1
                    or parquet.metadata.row_group(0).total_byte_size > 64 * 1024 * 1024
                ):
                    fail("preparation_extract_limit")
        output_hashes = {role: sha256(path) for role, path in paths.items()}
        generation = hashlib.sha256(
            (before + "".join(output_hashes[role] for role in ROLES)).encode()
        ).hexdigest()
        mapping_value = private_mapping(raw, paths)
        mapping_bytes = yaml.safe_dump(mapping_value, sort_keys=False).encode()
        prepared_mapping = output / "feasibility.local.yaml"
        prepared_mapping.write_bytes(mapping_bytes)
        os.chmod(prepared_mapping, 0o600)
        prepared_mapping_digest = hashlib.sha256(mapping_bytes).hexdigest()
        manifest = {
            "schema_version": 1,
            "mode": "coherent_manifest",
            "mapping_sha256": prepared_mapping_digest,
            "snapshot": {
                "generation": generation,
                "immutable_provenance_reviewed": True,
                "evidence_reference": "private coherent preparation receipt",
            },
            "seed": {
                "source": "orders",
                "selection_rule": (
                    "up to first 64 unique valid typed order identities in stable "
                    "file/row-group/row traversal"
                ),
                "reviewed": True,
                "evidence_reference": "private coherent preparation receipt",
            },
            "sources": {},
            "limits": {
                "max_files": 3,
                "max_row_groups": 3,
                "max_scanned_rows_per_source": MAX_RETAINED_ROWS_PER_SOURCE,
                "max_row_group_bytes_per_source": 64 * 1024 * 1024,
                "max_retained_rows_per_source": MAX_RETAINED_ROWS_PER_SOURCE,
                "max_seed_keys": SEED_COUNT,
            },
        }
        for role in ROLES:
            manifest["sources"][role] = {
                "snapshot_generation": generation,
                "coverage_reviewed": True,
                "complete_for_seed_domain": True,
                "coverage_reference": "private coherent preparation receipt",
                "locators": [{"path": str(paths[role]), "row_groups": [0]}],
            }
        manifest_path = output / "coherent_access.local.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
        os.chmod(manifest_path, 0o600)
        prepared, digest = load_mapping_snapshot(prepared_mapping)
        load_access_snapshot(manifest_path, prepared, digest)
        receipt = {
            "schema_version": 1,
            "data_class": "restricted_preparation_receipt",
            "status": "complete",
            "source_mapping_sha256": mapping_digest,
            "source_inventory_sha256": before,
            "prepared_mapping_sha256": prepared_mapping_digest,
            "manifest_sha256": sha256(manifest_path),
            "generation": generation,
            "seed_keys": len(seed),
            "observation_keys": len(observation_keys),
            "source_counts": {
                "orders": order_counts,
                "administrations": administration_counts,
                "observations": observation_counts,
            },
            "retained_rows": {role: table.num_rows for role, table in tables.items()},
            "output_sha256": output_hashes,
        }
        write_json(output / "preparation_receipt.json", receipt)
        return {"mode": "coherent_preparation", "status": "complete"}
    finally:
        os.umask(old_umask)


def main() -> int:
    try:
        if len(sys.argv) != 3:
            fail()
        from ies.feasibility.runner import verify_execution_context

        verify_execution_context()
        mapping_path, output_dir = map(Path, sys.argv[1:])
        expected = os.environ.get("IES_MAPPING_SHA256")
        _, digest = load_mapping_snapshot(mapping_path)
        if expected != digest:
            fail("mapping_changed")
        result = prepare_coherent(mapping_path, output_dir)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        # Never expose source paths, rows, config values or Arrow exception payloads.
        print('{"mode":"coherent_preparation","status":"failed"}')
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
