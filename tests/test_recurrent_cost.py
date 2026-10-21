"""Generated Parquet cost estimates; no clinical inputs or source data-page reads."""

import json
import os
from dataclasses import replace

import pyarrow.parquet as pq
import pytest
from test_recurrent_task_access import write_case

from ies import recurrent_cost as cost
from ies.recurrent_task import RecurrentTaskError
from ies.recurrent_task_access import LIMITS, FullSourceReader


def test_metadata_cost_matches_pass_accounting_and_does_not_emit_schema(tmp_path, monkeypatch):
    mapping, _ = write_case(tmp_path)
    roles = ("orders", "administrations", "observations")
    expected_file = expected_decoded = 0
    boundaries = {}
    for role in roles:
        for path in getattr(mapping, role).path.glob("*.parquet"):
            content = path.read_bytes()
            footer_size = int.from_bytes(content[-8:-4], "little")
            boundaries[str(path)] = (len(content) - 8 - footer_size, len(content))
            expected_file += len(content) * (4 if role == "orders" else 3)
            metadata = pq.read_metadata(path)
            expected_decoded += (2 if role == "orders" else 1) * sum(
                metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups)
            )
    original_open, original_fdopen = os.open, os.fdopen
    descriptors, reads = {}, []

    def open_file(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        descriptors[descriptor] = str(path)
        return descriptor

    class Guarded:
        def __init__(self, stream, path):
            self.stream, self.path = stream, path

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def read(self, size):
            begin = self.stream.tell()
            low, high = boundaries[self.path]
            assert (begin == 0 and size == 4) or (low <= begin and begin + size <= high)
            reads.append(size)
            return self.stream.read(size)

    def fdopen(descriptor, *args, **kwargs):
        assert kwargs["buffering"] == 0
        return Guarded(original_fdopen(descriptor, *args, **kwargs), descriptors[descriptor])

    monkeypatch.setattr(os, "open", open_file)
    monkeypatch.setattr(os, "fdopen", fdopen)
    monkeypatch.setattr(pq, "read_table", lambda *a, **k: pytest.fail("No row reads"))
    # A budget violation is a measured planning result, not permission to retry.
    limits = replace(LIMITS, max_total_charged_file_bytes=expected_file - 1)
    report = cost.review_cost(mapping, limits)
    assert report["status"] == "complete" and report["submitted"] is False
    assert report["current_limit_checks"]["charged_file_bytes"] is False
    assert (
        report["required_charged_file_gib_rounded_up"] == (expected_file + cost.GIB - 1) // cost.GIB
    )
    assert (
        report["required_decoded_gib_rounded_up"] == (expected_decoded + cost.GIB - 1) // cost.GIB
    )
    assert len(reads) == 3 * len(boundaries)
    exact_limits = replace(
        LIMITS,
        max_total_charged_file_bytes=expected_file,
        max_total_decoded_bytes=expected_decoded,
    )
    assert cost.review_cost(mapping, exact_limits)["current_limits_fit_metadata"] is True
    assert (
        cost.review_cost(
            mapping, replace(exact_limits, max_total_decoded_bytes=expected_decoded - 1)
        )["current_limit_checks"]["decoded_row_group_bytes"]
        is False
    )
    assert "toy_" not in json.dumps(report) and str(tmp_path) not in json.dumps(report)


def test_original_reader_rejects_predicted_file_budget_before_any_hash(tmp_path, monkeypatch):
    mapping, _ = write_case(tmp_path)
    monkeypatch.setattr(
        FullSourceReader, "_hash_sources", lambda self: pytest.fail("No source reads")
    )
    with pytest.raises(RecurrentTaskError, match="recurrent_file_byte_limit"):
        FullSourceReader(mapping, replace(LIMITS, max_total_charged_file_bytes=1))


@pytest.mark.parametrize(
    "field,key",
    [
        ("max_total_decoded_bytes", "decoded_row_group_bytes"),
        ("max_rows_per_pass", "rows_per_pass"),
        ("max_row_groups_per_pass", "row_groups_per_pass"),
    ],
)
def test_reports_other_predicted_limits_without_running_scan(tmp_path, field, key):
    mapping, _ = write_case(tmp_path)
    result = cost.review_cost(mapping, replace(LIMITS, **{field: 1}))
    assert result["current_limit_checks"][key] is False
    assert result["current_limits_fit_metadata"] is False
    assert result["runtime_memory_and_retention_verified"] is False


def test_footer_budget_and_inventory_change_reject_incomplete_review(tmp_path, monkeypatch):
    mapping, _ = write_case(tmp_path)
    monkeypatch.setattr(cost, "MAX_TOTAL_FOOTER_BYTES", 1)
    with pytest.raises(RecurrentTaskError, match="footer_limit"):
        cost.review_cost(mapping)
    monkeypatch.setattr(cost, "MAX_TOTAL_FOOTER_BYTES", 32 * 1024**2)
    original = cost._footer_cost
    changed = False

    def mutate(item, budget):
        nonlocal changed
        result = original(item, budget)
        if not changed:
            changed = True
            state = item.path.stat()
            os.utime(item.path, ns=(state.st_atime_ns, state.st_mtime_ns + 1000000))
        return result

    monkeypatch.setattr(cost, "_footer_cost", mutate)
    with pytest.raises(RecurrentTaskError, match="source_changed"):
        cost.review_cost(mapping)


def test_metadata_runtime_limit_stops_before_inventory(tmp_path, monkeypatch):
    mapping, _ = write_case(tmp_path)
    times = iter([0, 121])
    monkeypatch.setattr(cost.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(cost, "_inventory", lambda *a: pytest.fail("Must stop before inventory"))
    with pytest.raises(RecurrentTaskError, match="time_limit"):
        cost.review_cost(mapping)
