"""Metadata-only cost assessment for the unchanged T001 scan; never reads data pages."""

import os
import stat
import time

import pyarrow as pa
import pyarrow.parquet as pq

from ies.cohort_readiness.eligibility import _base_source, _inventory
from ies.recurrent_task import RecurrentTaskError
from ies.recurrent_task_access import LIMITS, charged_inventory_bytes

GIB = 1024**3
MAX_FOOTER_BYTES = 8 * 1024**2
MAX_TOTAL_FOOTER_BYTES = 32 * 1024**2
MAX_METADATA_SECONDS = 120


def _footer_cost(item, budget):
    fd = os.open(item.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb", buffering=0) as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size < 12
            or (before.st_size, before.st_mtime_ns) != (item.size, item.mtime_ns)
        ):
            raise RecurrentTaskError("recurrent_cost_source_changed")
        if stream.read(4) != b"PAR1":
            raise RecurrentTaskError("recurrent_cost_invalid_footer")
        stream.seek(-8, os.SEEK_END)
        trailer = stream.read(8)
        size = int.from_bytes(trailer[:4], "little")
        if trailer[4:] != b"PAR1" or not 0 < size <= item.size - 12:
            raise RecurrentTaskError("recurrent_cost_invalid_footer")
        if size > min(MAX_FOOTER_BYTES, budget["remaining"]):
            raise RecurrentTaskError("recurrent_cost_footer_limit")
        budget["remaining"] -= size
        stream.seek(-8 - size, os.SEEK_END)
        footer = stream.read(size)
        after = os.fstat(stream.fileno())
        if len(footer) != size or (after.st_size, after.st_mtime_ns) != (item.size, item.mtime_ns):
            raise RecurrentTaskError("recurrent_cost_source_changed")
    # Arrow only receives a footer container; it cannot prefetch source data pages.
    # Do not inspect column names, statistics or arbitrary key/value metadata.
    with pq.ParquetFile(
        pa.BufferReader(b"PAR1" + footer + trailer),
        thrift_string_size_limit=1024**2,
        thrift_container_size_limit=100000,
    ) as parquet:
        metadata = parquet.metadata
        if metadata.num_row_groups > 100000:
            raise RecurrentTaskError("recurrent_cost_footer_limit")
        decoded = sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups))
        if decoded < 0 or metadata.num_rows < 0:
            raise RecurrentTaskError("recurrent_cost_invalid_footer")
        return metadata.num_row_groups, metadata.num_rows, decoded


def review_cost(mapping, limits=LIMITS):
    started = time.monotonic()

    def check_time():
        if time.monotonic() - started > MAX_METADATA_SECONDS:
            raise RecurrentTaskError("recurrent_cost_time_limit")

    sources = {
        role: _base_source(getattr(mapping, role))
        for role in ("orders", "administrations", "observations")
    }
    before = {}
    for role, source in sources.items():
        check_time()
        before[role] = _inventory(source, limits)
    charged = charged_inventory_bytes(before)
    budget = {"remaining": MAX_TOTAL_FOOTER_BYTES}
    decoded = 0
    groups_pass = rows_pass = True
    for role, files in before.items():
        groups = rows = size = 0
        for item in files:
            check_time()
            group_count, row_count, byte_count = _footer_cost(item, budget)
            groups += group_count
            rows += row_count
            size += byte_count
        groups_pass &= groups <= limits.max_row_groups_per_pass
        rows_pass &= rows <= limits.max_rows_per_pass
        decoded += (2 if role == "orders" else 1) * size
    for role, source in sources.items():
        check_time()
        if _inventory(source, limits) != before[role]:
            raise RecurrentTaskError("recurrent_cost_source_changed")
    check_time()
    checks = {
        "charged_file_bytes": charged <= limits.max_total_charged_file_bytes,
        "decoded_row_group_bytes": decoded <= limits.max_total_decoded_bytes,
        "row_groups_per_pass": groups_pass,
        "rows_per_pass": rows_pass,
    }
    return {
        "mode": "recurrent_cost_review",
        "status": "complete",
        "submitted": False,
        "raw_source_scan": False,
        "source_content_hashed": False,
        "row_persistence": False,
        "source_access": "file_inventory_and_parquet_header_trailer_footer_only",
        "inventory_metadata_stable": True,
        "current_limits_fit_metadata": all(checks.values()),
        "current_limit_checks": checks,
        "required_charged_file_gib_rounded_up": (charged + GIB - 1) // GIB,
        "required_decoded_gib_rounded_up": (decoded + GIB - 1) // GIB,
        "configured_charged_file_gib": limits.max_total_charged_file_bytes / GIB,
        "configured_decoded_gib": limits.max_total_decoded_bytes / GIB,
        "footer_budget_bytes": MAX_TOTAL_FOOTER_BYTES,
        "runtime_memory_and_retention_verified": False,
        "note": (
            "Metadata cost only, not measured I/O, memory, runtime or task support. "
            "No content-stability proof or automatic resource expansion/submission."
        ),
    }
