"""T001 full-source access for selected old-training patients; no row persistence."""

import hashlib
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from ies.clock_audit import _manifest, _parquet
from ies.cohort_readiness.eligibility import _base_source, _inventory
from ies.cohort_readiness.extract import SCHEMA
from ies.dual_clock_history import _decode_identifier
from ies.feasibility.contract import identity
from ies.io import sha256
from ies.recurrent_task import (
    HORIZON_HOURS,
    LOOKBACK_HOURS,
    MAX_ADMINISTRATIONS,
    MAX_ANCHORS,
    MAX_OBSERVATIONS,
    MAX_ORDERS,
    MODE,
    RecurrentTaskError,
    audit_recurrent_rows,
)


@dataclass(frozen=True)
class AccessLimits:
    max_files_per_source: int = 1000
    max_entries_per_source: int = 2000
    max_row_groups_per_pass: int = 2000
    max_rows_per_pass: int = 500_000_000
    max_source_bytes: int = 64 * 1024**3
    max_total_charged_file_bytes: int = 64 * 1024**3
    max_total_decoded_bytes: int = 64 * 1024**3
    batch_rows: int = 8192
    runtime_seconds: int = 1200
    cpu_seconds: int = 1200
    cpus: int = 2
    memory_mb: int = 4096


LIMITS = AccessLimits()
RESOURCE_PROFILES = ("baseline64", "expanded160")


def resource_limits(profile="baseline64"):
    if profile == "baseline64":
        return LIMITS
    if profile == "expanded160":
        return replace(
            LIMITS,
            max_total_charged_file_bytes=160 * 1024**3,
            max_total_decoded_bytes=128 * 1024**3,
        )
    raise RecurrentTaskError("recurrent_invalid_resource_profile")


SELECTION_SALT = "T001:20261020"


def plan_recurrent_task(profile="baseline64"):
    limits = resource_limits(profile)
    return {
        "resource_profile": profile,
        "mode": MODE,
        "submitted": False,
        "operation": "full_declared_source_scans_with_selected_patient_retention",
        "source_passes": {"orders": 2, "administrations": 1, "observations": 1},
        "source_content_hash_passes": 2,
        "source_inventory_stability_checked": True,
        "max_training_patients": 32,
        "max_retained_orders": MAX_ORDERS,
        "max_retained_administrations": MAX_ADMINISTRATIONS,
        "max_retained_observations": MAX_OBSERVATIONS,
        "max_anchors_per_patient": MAX_ANCHORS,
        "lookback_hours": LOOKBACK_HOURS,
        "diagnostic_horizon_hours": HORIZON_HOURS,
        "limits": asdict(limits),
        "model_fitted": False,
        "validation_split_evaluated": False,
        "test_split_evaluated": False,
        "row_persistence": False,
        "gpu_used": False,
        "note": (
            "Explicit full-source operation, not a prefix probe. File bytes charge full files "
            "per pass plus before/after content hashing; decoded bytes charge full row groups. "
            "These are work ceilings, not measured disk I/O or runtime estimates."
        ),
    }


def select_training_patients(cohort_dir: Path, digest: str, mapping_digest: str):
    manifest = _manifest(cohort_dir, digest)
    if (
        manifest.get("mode") != "bounded_phase0_cohort_extraction"
        or manifest.get("bounded_domain") is not True
        or manifest.get("mapping_sha256") != mapping_digest
    ):
        raise RecurrentTaskError("recurrent_cohort_binding")
    path = _parquet(cohort_dir, "cohort.parquet", manifest, SCHEMA, 20_000)
    table = pq.read_table(path, columns=["patient_id", "order_id", "split"])
    patients, orders = {}, set()
    for row in table.to_pylist():
        patient = _decode_identifier(row["patient_id"])
        order = _decode_identifier(row["order_id"])
        split = row["split"]
        if (
            split not in {"train", "validation", "test"}
            or order in orders
            or patients.setdefault(patient, split) != split
        ):
            raise RecurrentTaskError("recurrent_patient_split")
        orders.add(order)
    selected = sorted(
        (patient for patient, split in patients.items() if split == "train"),
        key=lambda p: hashlib.sha256(f"{SELECTION_SALT}:{p[0]}:{p[1]}".encode()).digest(),
    )[:32]
    if not selected:
        raise RecurrentTaskError("recurrent_empty_training")
    return frozenset(selected), [
        (cohort_dir / "manifest.json", digest),
        (path, manifest["artifacts_sha256"]["cohort.parquet"]),
    ]


def charged_inventory_bytes(inventory):
    """Conservative whole-file charges, including both content hash passes."""
    return sum(
        (4 if role == "orders" else 3) * item.size
        for role, files in inventory.items()
        for item in files
    )


class FullSourceReader:
    """All read attempts are charged; a failed/limited pass never certifies coverage."""

    def __init__(self, mapping, limits=LIMITS):
        self.mapping = mapping
        self.limits = limits
        self.started = time.monotonic()
        self.counts = {
            "charged_file_bytes": 0,
            "decoded_row_group_bytes": 0,
            "hash_file_reads": 0,
            "source_passes_completed": 0,
        }
        self.passes = {}
        self.sources = {
            role: _base_source(getattr(mapping, role))
            for role in ("orders", "administrations", "observations")
        }
        self.before = {role: _inventory(source, limits) for role, source in self.sources.items()}
        # Preflight the conservative file-byte cost before opening any source contents.
        needed = charged_inventory_bytes(self.before)
        if needed > limits.max_total_charged_file_bytes:
            raise RecurrentTaskError("recurrent_file_byte_limit")
        self.hashes = self._hash_sources()

    def check_time(self):
        if time.monotonic() - self.started > self.limits.runtime_seconds:
            raise RecurrentTaskError("recurrent_runtime_limit")

    def _charge_file(self, item):
        self.check_time()
        if item.path.is_symlink():
            raise RecurrentTaskError("recurrent_source_changed")
        state = item.path.stat()
        if state.st_size != item.size or state.st_mtime_ns != item.mtime_ns:
            raise RecurrentTaskError("recurrent_source_changed")
        charged = self.counts["charged_file_bytes"] + item.size
        if charged > self.limits.max_total_charged_file_bytes:
            raise RecurrentTaskError("recurrent_file_byte_limit")
        self.counts["charged_file_bytes"] = charged

    def _hash_sources(self):
        hashes = {}
        for role, files in self.before.items():
            for item in files:
                self._charge_file(item)
                digest = hashlib.sha256()
                read_bytes = 0
                with item.path.open("rb") as stream:
                    while chunk := stream.read(min(1024**2, item.size - read_bytes + 1)):
                        self.check_time()
                        read_bytes += len(chunk)
                        if read_bytes > item.size:
                            raise RecurrentTaskError("recurrent_source_changed")
                        digest.update(chunk)
                if read_bytes != item.size:
                    raise RecurrentTaskError("recurrent_source_changed")
                self.counts["hash_file_reads"] += 1
                hashes[(role, item.path)] = digest.hexdigest()
        return hashes

    def selected_rows(self, role, label, logical_names, filter_name, keys):
        source = self.sources[role]
        physical = list(
            dict.fromkeys(
                source.columns[name]
                for name in logical_names
                if source.columns.get(name) is not None
            )
        )
        progress = {"files": 0, "row_groups": 0, "scanned_rows": 0, "matched_rows": 0}
        if label in self.passes:
            raise RecurrentTaskError("recurrent_repeated_pass")
        self.passes[label] = progress
        for item in self.before[role]:
            self._charge_file(item)
            progress["files"] += 1
            with pq.ParquetFile(item.path, pre_buffer=False) as parquet:
                if any(parquet.schema_arrow.names.count(name) != 1 for name in physical):
                    raise RecurrentTaskError("recurrent_source_columns")
                for group in range(parquet.metadata.num_row_groups):
                    self.check_time()
                    metadata = parquet.metadata.row_group(group)
                    progress["row_groups"] += 1
                    progress["scanned_rows"] += metadata.num_rows
                    self.counts["decoded_row_group_bytes"] += metadata.total_byte_size
                    if (
                        progress["row_groups"] > self.limits.max_row_groups_per_pass
                        or progress["scanned_rows"] > self.limits.max_rows_per_pass
                        or self.counts["decoded_row_group_bytes"]
                        > self.limits.max_total_decoded_bytes
                    ):
                        raise RecurrentTaskError("recurrent_scan_limit")
                    for batch in parquet.iter_batches(
                        row_groups=[group],
                        columns=physical,
                        batch_size=self.limits.batch_rows,
                        use_threads=False,
                    ):
                        self.check_time()
                        column = batch.column(
                            batch.schema.get_field_index(source.columns[filter_name])
                        )
                        if pa.types.is_dictionary(column.type):
                            column = column.cast(column.type.value_type)
                        if pa.types.is_null(column.type):
                            accepted = []
                        elif pa.types.is_integer(column.type):
                            bits = column.type.bit_width
                            signed = pa.types.is_signed_integer(column.type)
                            lower = -(2 ** (bits - 1)) if signed else 0
                            upper = 2 ** (bits - int(signed)) - 1
                            accepted = [
                                value
                                for kind, value in keys
                                if kind == "integer" and lower <= value <= upper
                            ]
                        elif pa.types.is_string(column.type) or pa.types.is_large_string(
                            column.type
                        ):
                            accepted = [value for kind, value in keys if kind == "string"]
                        else:
                            raise RecurrentTaskError("recurrent_identity_type")
                        selected = batch.filter(
                            pc.fill_null(
                                pc.is_in(column, value_set=pa.array(accepted, type=column.type)),
                                False,
                            )
                        )
                        progress["matched_rows"] += selected.num_rows
                        arrays = {
                            name: selected.column(
                                selected.schema.get_field_index(source.columns[name])
                            ).to_pylist()
                            for name in logical_names
                            if source.columns.get(name) is not None
                        }
                        for index in range(selected.num_rows):
                            yield {name: values[index] for name, values in arrays.items()}
        self.counts["source_passes_completed"] += 1

    def finish(self):
        if {role: _inventory(source, self.limits) for role, source in self.sources.items()} != (
            self.before
        ):
            raise RecurrentTaskError("recurrent_source_changed")
        if self._hash_sources() != self.hashes:
            raise RecurrentTaskError("recurrent_source_changed")
        if {role: _inventory(source, self.limits) for role, source in self.sources.items()} != (
            self.before
        ):
            raise RecurrentTaskError("recurrent_source_changed")
        self.check_time()


def _collect(rows, cap):
    result = []
    for row in rows:
        if len(result) >= cap:
            raise RecurrentTaskError("recurrent_retention_limit")
        result.append(row)
    return result


def audit_sources(mapping, patients, *, data_class, limits=LIMITS):
    reader = FullSourceReader(mapping, limits)
    # First pass discovers identities only; it does not select successful outcomes.
    seed = _collect(
        reader.selected_rows(
            "orders", "order_patient_selection", ("order_id", "patient_id"), "patient_id", patients
        ),
        MAX_ORDERS,
    )
    order_keys = frozenset(
        key for row in seed if (key := identity(row.get("order_id"))) is not None
    )
    malformed = [row for row in seed if identity(row.get("order_id")) is None]
    del seed
    orders = _collect(
        reader.selected_rows(
            "orders",
            "order_key_confirmation",
            tuple(mapping.orders.columns),
            "order_id",
            order_keys,
        ),
        MAX_ORDERS - len(malformed),
    )
    orders.extend(malformed)
    observation_keys = frozenset(
        key for row in orders if (key := identity(row.get("observation_id"))) is not None
    )
    administrations = _collect(
        reader.selected_rows(
            "administrations",
            "all_linked_administrations",
            tuple(mapping.administrations.columns),
            "order_id",
            order_keys,
        ),
        MAX_ADMINISTRATIONS,
    )
    observations = _collect(
        reader.selected_rows(
            "observations",
            "all_linked_observations",
            tuple(mapping.observations.columns),
            "observation_id",
            observation_keys,
        ),
        MAX_OBSERVATIONS,
    )
    reader.finish()
    report = audit_recurrent_rows(
        orders,
        administrations,
        observations,
        mapping,
        patients,
        coverage_complete=True,
        data_class=data_class,
    )
    reader.check_time()
    report.update(
        source_stable=True,
        complete_full_source_scan=True,
        raw_source_scan=True,
        access_counts=reader.counts,
        source_pass_counts=reader.passes,
        source_identity_scope="selected_order_keys_not_global_identity_uniqueness",
    )
    return report


def verify_bindings(bindings):
    if any(sha256(path) != expected for path, expected in bindings):
        raise RecurrentTaskError("recurrent_inputs_changed")
