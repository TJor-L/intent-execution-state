"""Reviewed coherent-manifest contract and explicit row-group reader."""

from __future__ import annotations

import hashlib
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from ies.feasibility.analysis import Budget, analyze
from ies.feasibility.contract import ROOT, FeasibilityError, Mapping, Source, identity

ACCESS_LIMIT_CAPS = {
    "max_files": 64,
    "max_row_groups": 256,
    "max_scanned_rows_per_source": 100_000,
    "max_row_group_bytes_per_source": 64 * 1024 * 1024,
    "max_retained_rows_per_source": 100_000,
    "max_seed_keys": 100_000,
}
ROLES = ("orders", "administrations", "observations")


def require(condition: bool) -> None:
    if not condition:
        raise FeasibilityError("invalid_access_manifest")


def private_evidence(value) -> str:
    require(isinstance(value, str) and 0 < len(value.strip()) <= 2048)
    require("\x00" not in value)
    return value


@dataclass(frozen=True, repr=False)
class Locator:
    path: Path
    row_groups: tuple[int, ...]


@dataclass(frozen=True, repr=False)
class SourceAccess:
    snapshot_generation: str
    coverage_reference: str
    locators: tuple[Locator, ...]


@dataclass(frozen=True, repr=False)
class AccessLimits:
    max_files: int
    max_row_groups: int
    max_scanned_rows_per_source: int
    max_row_group_bytes_per_source: int
    max_retained_rows_per_source: int
    max_seed_keys: int


@dataclass(frozen=True, repr=False)
class CoherentManifest:
    mapping_sha256: str
    snapshot_generation: str
    snapshot_reference: str
    seed_rule: str
    seed_reference: str
    sources: dict[str, SourceAccess]
    limits: AccessLimits


def _locator(value, source: Source) -> Locator:
    require(isinstance(value, dict) and set(value) == {"path", "row_groups"})
    raw = value["path"]
    require(isinstance(raw, str) and raw and "\x00" not in raw)
    path = Path(raw)
    require(path.is_absolute() and ".." not in path.parts and path.suffix.lower() == ".parquet")
    require(path != Path("/") and not path.is_relative_to(ROOT))
    root = source.path
    if root.suffix.lower() == ".parquet":
        require(path == root)
    else:
        require(path.is_relative_to(root))
    groups = value["row_groups"]
    require(isinstance(groups, list) and groups)
    require(all(type(group) is int and group >= 0 for group in groups))
    require(len(groups) == len(set(groups)))
    return Locator(path, tuple(groups))


def parse_access_manifest(value: dict, mapping: Mapping, mapping_sha256: str) -> CoherentManifest:
    require(
        isinstance(value, dict)
        and set(value)
        == {"schema_version", "mode", "mapping_sha256", "snapshot", "seed", "sources", "limits"}
    )
    require(value["schema_version"] == 1 and value["mode"] == "coherent_manifest")
    require(value["mapping_sha256"] == mapping_sha256)
    snapshot = value["snapshot"]
    require(
        isinstance(snapshot, dict)
        and set(snapshot) == {"generation", "immutable_provenance_reviewed", "evidence_reference"}
    )
    generation = snapshot["generation"]
    require(isinstance(generation, str) and 0 < len(generation) <= 256)
    require(snapshot["immutable_provenance_reviewed"] is True)
    snapshot_reference = private_evidence(snapshot["evidence_reference"])
    seed = value["seed"]
    require(
        isinstance(seed, dict)
        and set(seed) == {"source", "selection_rule", "reviewed", "evidence_reference"}
    )
    require(seed["source"] == "orders" and seed["reviewed"] is True)
    require(isinstance(seed["selection_rule"], str) and 0 < len(seed["selection_rule"]) <= 512)
    seed_reference = private_evidence(seed["evidence_reference"])
    raw_sources = value["sources"]
    require(isinstance(raw_sources, dict) and set(raw_sources) == set(ROLES))
    parsed_sources = {}
    for role in ROLES:
        raw = raw_sources[role]
        require(
            isinstance(raw, dict)
            and set(raw)
            == {
                "snapshot_generation",
                "coverage_reviewed",
                "complete_for_seed_domain",
                "coverage_reference",
                "locators",
            }
        )
        require(raw["snapshot_generation"] == generation)
        require(raw["coverage_reviewed"] is True and raw["complete_for_seed_domain"] is True)
        source = getattr(mapping, role)
        locators = tuple(_locator(item, source) for item in raw["locators"])
        require(locators)
        require(len({locator.path for locator in locators}) == len(locators))
        parsed_sources[role] = SourceAccess(
            generation, private_evidence(raw["coverage_reference"]), locators
        )
    raw_limits = value["limits"]
    require(isinstance(raw_limits, dict) and set(raw_limits) == set(ACCESS_LIMIT_CAPS))
    require(
        all(
            type(raw_limits[name]) is int and 1 <= raw_limits[name] <= cap
            for name, cap in ACCESS_LIMIT_CAPS.items()
        )
    )
    limits = AccessLimits(**raw_limits)
    require(limits.max_retained_rows_per_source <= limits.max_scanned_rows_per_source)
    require(limits.max_seed_keys <= limits.max_retained_rows_per_source)
    require(sum(len(source.locators) for source in parsed_sources.values()) <= limits.max_files)
    require(
        sum(
            len(locator.row_groups)
            for source in parsed_sources.values()
            for locator in source.locators
        )
        <= limits.max_row_groups
    )
    return CoherentManifest(
        mapping_sha256,
        generation,
        snapshot_reference,
        seed["selection_rule"],
        seed_reference,
        parsed_sources,
        limits,
    )


def load_access_snapshot(
    path: Path, mapping: Mapping, mapping_sha256: str
) -> tuple[CoherentManifest, str]:
    try:
        content = path.read_bytes()
        manifest = parse_access_manifest(yaml.safe_load(content), mapping, mapping_sha256)
        return manifest, hashlib.sha256(content).hexdigest()
    except FeasibilityError:
        raise
    except Exception:
        raise FeasibilityError("invalid_access_manifest") from None


def plan_access(manifest: CoherentManifest) -> dict:
    return {
        "mode": "coherent_manifest",
        "limits": asdict(manifest.limits),
        "locator_files": sum(len(source.locators) for source in manifest.sources.values()),
        "locator_row_groups": sum(
            len(locator.row_groups)
            for source in manifest.sources.values()
            for locator in source.locators
        ),
        "coherent_linkage_coverage_verified": True,
    }


def _supported_schema(parquet: pq.ParquetFile, columns: list[str]) -> None:
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


def inspect_coherent_sources(mapping: Mapping, manifest: CoherentManifest) -> dict:
    """Read only reviewed files/row groups; no recursive discovery or predicate fallback."""
    budget = Budget(mapping)
    pa.set_cpu_count(mapping.limits.cpus)
    counters = {
        role: {
            "files_read": 0,
            "row_groups_read": 0,
            "projected_rows_scanned": 0,
            "row_group_bytes": 0,
            "rows_retained": 0,
        }
        for role in ROLES
    }
    seed_keys = set()
    observation_keys = set()

    def role_rows(role: str):
        source = getattr(mapping, role)
        columns = list(dict.fromkeys(column for column in source.columns.values() if column))
        root = source.path.resolve()
        for locator in manifest.sources[role].locators:
            budget.check_time()
            path = locator.path
            if path.is_symlink():
                raise FeasibilityError("symlink_source")
            resolved = path.resolve()
            if root.suffix.lower() == ".parquet":
                if resolved != root:
                    raise FeasibilityError("source_generation_changed")
            elif not resolved.is_relative_to(root):
                raise FeasibilityError("source_generation_changed")
            with pq.ParquetFile(resolved, pre_buffer=False) as parquet:
                _supported_schema(parquet, columns)
                counters[role]["files_read"] += 1
                for group in locator.row_groups:
                    budget.check_time()
                    if group >= parquet.metadata.num_row_groups:
                        raise FeasibilityError("source_generation_changed")
                    rows = parquet.metadata.row_group(group).num_rows
                    row_group_bytes = parquet.metadata.row_group(group).total_byte_size
                    scanned = counters[role]["projected_rows_scanned"]
                    if scanned + rows > manifest.limits.max_scanned_rows_per_source:
                        budget.reached["rows"] = True
                        return
                    if (
                        counters[role]["row_group_bytes"] + row_group_bytes
                        > manifest.limits.max_row_group_bytes_per_source
                    ):
                        budget.reached["bytes"] = True
                        return
                    counters[role]["row_groups_read"] += 1
                    counters[role]["projected_rows_scanned"] += rows
                    counters[role]["row_group_bytes"] += row_group_bytes
                    for batch in parquet.iter_batches(
                        batch_size=mapping.limits.batch_rows,
                        row_groups=[group],
                        columns=columns,
                        use_threads=False,
                    ):
                        budget.check_time()
                        for physical in batch.to_pylist():
                            logical = {
                                name: physical.get(column) if column else None
                                for name, column in source.columns.items()
                            }
                            if role == "orders":
                                key = identity(logical.get("order_id"))
                                if key is not None:
                                    seed_keys.add(key)
                                    if len(seed_keys) > manifest.limits.max_seed_keys:
                                        budget.reached["keys"] = True
                                        return
                                observation = identity(logical.get("observation_id"))
                                if observation is not None:
                                    observation_keys.add(observation)
                            elif role == "administrations":
                                if identity(logical.get("order_id")) not in seed_keys:
                                    continue
                            elif identity(logical.get("observation_id")) not in observation_keys:
                                continue
                            if (
                                counters[role]["rows_retained"]
                                >= manifest.limits.max_retained_rows_per_source
                            ):
                                budget.reached["rows"] = True
                                return
                            counters[role]["rows_retained"] += 1
                            yield logical

    with closing(role_rows("orders")) as orders:
        with closing(role_rows("administrations")) as administrations:
            with closing(role_rows("observations")) as observations:
                report = analyze(orders, administrations, observations, mapping, budget)
    report["access_mode"] = "coherent_manifest"
    report["coherent_linkage_coverage_verified"] = not any(budget.reached.values())
    report["access_counts"] = counters
    report["seed_keys_retained"] = len(seed_keys)
    return report
