"""Generated shards exercise actual projections, coverage and immutable bindings."""

import json
import os
from dataclasses import replace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ies.cohort_readiness.extract import SCHEMA
from ies.io import sha256, write_json
from ies.recurrent_task import RecurrentTaskError
from ies.recurrent_task_access import (
    LIMITS,
    FullSourceReader,
    audit_sources,
    plan_recurrent_task,
    select_training_patients,
    verify_bindings,
)
from ies.recurrent_task_demo import generated_case


def write_case(tmp_path, mutate=None):
    mapping, orders, administrations, observations, patients = generated_case()
    if mutate:
        mutate(orders, administrations, observations)
    sources = {}
    for role, rows in (
        ("orders", orders),
        ("administrations", administrations),
        ("observations", observations),
    ):
        directory = tmp_path / role
        directory.mkdir()
        source = replace(getattr(mapping, role), path=directory)
        sources[role] = source
        for index, row in enumerate(rows):
            table = pa.Table.from_pylist(
                [
                    {
                        physical: row.get(logical)
                        for logical, physical in source.columns.items()
                        if physical is not None
                    }
                ]
            )
            pq.write_table(table, directory / f"{index:03d}.parquet")
    return replace(mapping, **sources), patients


def test_complete_scans_keep_off_prefix_recurrence_and_preserve_private_boundary(tmp_path):
    mapping, patients = write_case(tmp_path)
    before = sorted(str(path) for path in tmp_path.rglob("*"))
    report = audit_sources(mapping, patients, data_class="synthetic")
    assert report["counts"]["valid_recurrent_paths"] == 2
    assert report["complete_full_source_scan"] is True
    assert report["access_counts"]["source_passes_completed"] == 4
    assert report["source_pass_counts"]["all_linked_administrations"]["scanned_rows"] == 5
    assert report["source_pass_counts"]["order_patient_selection"]["scanned_rows"] == 3
    assert report["access_counts"]["hash_file_reads"] == 2 * 11
    assert "toy_" not in json.dumps(report) and str(tmp_path) not in json.dumps(report)
    assert before == sorted(str(path) for path in tmp_path.rglob("*"))


def test_selected_key_confirmation_finds_duplicate_in_another_patient(tmp_path):
    def mutate(orders, _admins, _observations):
        orders.append(dict(orders[0], patient_id="toy_outside_training"))

    mapping, patients = write_case(tmp_path, mutate)
    report = audit_sources(mapping, patients, data_class="synthetic")
    assert report["counts"]["patients_with_invalid_roster"] == 1
    assert report["counts"]["multiorder_ascertained_windows"] == 0
    assert report["source_pass_counts"]["order_patient_selection"]["matched_rows"] == 3
    assert report["source_pass_counts"]["order_key_confirmation"]["matched_rows"] == 4


def test_patient_mismatch_is_not_filtered_out_and_missing_order_key_is_not_discarded(tmp_path):
    def mutate(orders, admins, _observations):
        admins[0]["patient_id"] = "toy_outside_training"
        orders.append(dict(orders[0], order_id=None))

    mapping, patients = write_case(tmp_path, mutate)
    report = audit_sources(mapping, patients, data_class="synthetic")
    assert report["counts"]["patient_mismatches"] == 1
    assert report["counts"]["invalid_order_identity"] == 1
    assert report["window_status_counts"] == {"unresolved_roster": 3}


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_total_charged_file_bytes", 1),
        ("max_total_decoded_bytes", 1),
        ("max_rows_per_pass", 1),
        ("max_row_groups_per_pass", 1),
    ],
)
def test_exceeded_work_bound_has_no_successful_partial_report(tmp_path, field, value):
    mapping, patients = write_case(tmp_path)
    with pytest.raises(RecurrentTaskError, match="_limit"):
        audit_sources(
            mapping, patients, data_class="synthetic", limits=replace(LIMITS, **{field: value})
        )


def test_content_change_is_detected_even_when_file_size_and_mtime_are_restored(tmp_path):
    mapping, _ = write_case(tmp_path)
    reader = FullSourceReader(mapping)
    path = mapping.administrations.path / "000.parquet"
    original = path.read_bytes()
    stat = path.stat()
    changed = bytearray(original)
    changed[20] ^= 1
    path.write_bytes(changed)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(RecurrentTaskError, match="recurrent_source_changed"):
        reader.finish()


def test_added_file_and_symlink_cannot_certify_snapshot(tmp_path):
    mapping, _ = write_case(tmp_path)
    reader = FullSourceReader(mapping)
    source = mapping.orders.path / "000.parquet"
    (mapping.orders.path / "added.parquet").write_bytes(source.read_bytes())
    with pytest.raises(RecurrentTaskError, match="recurrent_source_changed"):
        reader.finish()
    (mapping.orders.path / "added.parquet").unlink()
    (mapping.orders.path / "link.parquet").symlink_to(source)
    with pytest.raises(ValueError):
        FullSourceReader(mapping)


def cohort_artifact(tmp_path):
    rows = [
        {
            "patient_id": f"string:toy_patient_{index}",
            "order_id": f"string:toy_order_{index}",
            "encounter_id": "string:toy_encounter",
            "split": "train" if index < 40 else "validation" if index == 40 else "test",
            # Deliberately unusable labels: the task selector must never project them.
            "index_time_hours": float("nan"),
            "duration_hours": float("nan"),
            "cause": -1,
            "outcome": "toy_unread_label",
        }
        for index in range(42)
    ]
    path = tmp_path / "cohort.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), path)
    manifest = {
        "mode": "bounded_phase0_cohort_extraction",
        "status": "complete",
        "data_class": "restricted_clinical",
        "bounded_domain": True,
        "mapping_sha256": "b" * 64,
        "artifacts_sha256": {"cohort.parquet": sha256(path)},
    }
    write_json(tmp_path / "manifest.json", manifest)
    return sha256(tmp_path / "manifest.json")


def test_training_only_identity_projection_and_immutable_bindings(tmp_path, monkeypatch):
    digest = cohort_artifact(tmp_path)
    original_read = pq.read_table
    projections = []

    def tracked_read(path, *, columns, **kwargs):
        projections.append(columns)
        return original_read(path, columns=columns, **kwargs)

    monkeypatch.setattr(pq, "read_table", tracked_read)
    patients, bindings = select_training_patients(tmp_path, digest, "b" * 64)
    assert len(patients) == 32
    assert all(int(patient[1].rsplit("_", 1)[-1]) < 40 for patient in patients)
    assert projections == [["patient_id", "order_id", "split"]]
    assert select_training_patients(tmp_path, digest, "b" * 64)[0] == patients
    verify_bindings(bindings)
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(RecurrentTaskError, match="recurrent_inputs_changed"):
        verify_bindings(bindings)


def test_patient_overlap_rejected_even_when_order_ids_differ(tmp_path):
    digest = cohort_artifact(tmp_path)
    table = pq.read_table(tmp_path / "cohort.parquet")
    rows = table.to_pylist()
    rows[-1]["patient_id"] = rows[0]["patient_id"]
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), tmp_path / "cohort.parquet")
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["artifacts_sha256"]["cohort.parquet"] = sha256(tmp_path / "cohort.parquet")
    write_json(tmp_path / "manifest.json", manifest)
    digest = sha256(tmp_path / "manifest.json")
    with pytest.raises(RecurrentTaskError, match="recurrent_patient_split"):
        select_training_patients(tmp_path, digest, "b" * 64)


def test_plan_is_explicit_about_full_scan_and_has_no_private_paths():
    plan = plan_recurrent_task()
    assert plan["source_passes"] == {"orders": 2, "administrations": 1, "observations": 1}
    assert plan["source_content_hash_passes"] == 2
    assert plan["limits"]["max_total_charged_file_bytes"] == 64 * 1024**3
    assert plan["row_persistence"] is False and plan["model_fitted"] is False


def test_dictionary_identities_and_mixed_integer_widths_preserve_exact_key_semantics(tmp_path):
    mapping, patients = write_case(tmp_path)
    for source in mapping.sources:
        for path in source.path.glob("*.parquet"):
            table = pq.read_table(path)
            for logical in ("patient_id", "order_id", "observation_id"):
                name = source.columns.get(logical)
                if name in table.column_names:
                    index = table.schema.get_field_index(name)
                    column = table.column(index)
                    table = table.set_column(index, name, column.dictionary_encode())
            pq.write_table(table, path)
    assert (
        audit_sources(mapping, patients, data_class="synthetic")["counts"]["valid_recurrent_paths"]
        == 2
    )
    # A large selected integer key cannot match an int8 shard, but must not abort
    # scanning that shard or be coerced to a string key.
    path = mapping.orders.path / "000.parquet"
    table = pq.read_table(path)
    index = table.schema.get_field_index(mapping.orders.columns["patient_id"])
    table = table.set_column(index, mapping.orders.columns["patient_id"], pa.array([1], pa.int8()))
    pq.write_table(table, path)
    reader = FullSourceReader(mapping)
    rows = list(
        reader.selected_rows(
            "orders",
            "typed_probe",
            ("patient_id", "order_id"),
            "patient_id",
            frozenset({("integer", 1), ("integer", 1000), ("string", "1")}),
        )
    )
    assert len(rows) == 1 and rows[0]["patient_id"] == 1
