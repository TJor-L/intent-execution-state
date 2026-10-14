"""Generated-only tests for the reviewed coherent-manifest backend."""

import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from conftest import load_script

from ies.feasibility.access import (
    inspect_coherent_sources,
    load_access_snapshot,
)
from ies.feasibility.contract import FeasibilityError, load_mapping_snapshot
from ies.feasibility.runner import plan_feasibility


def _mapping(tmp_path: Path) -> tuple[Path, dict]:
    columns = {
        "orders": {
            "order_id": "toy_order",
            "patient_id": "toy_patient",
            "encounter_id": "toy_encounter",
            "occurred_at": "toy_occurred",
            "available_at": "toy_available",
            "observation_id": "toy_observation",
            "discontinued_at": None,
            "discontinued_available_at": None,
            "ended_at": None,
            "ended_available_at": None,
        },
        "administrations": {
            "administration_id": "toy_administration",
            "order_id": "toy_order",
            "patient_id": "toy_patient",
            "encounter_id": "toy_encounter",
            "occurred_at": "toy_occurred",
            "available_at": "toy_available",
            "action": "toy_action",
            "documentation_status": None,
        },
        "observations": {
            "observation_id": "toy_observation",
            "patient_id": "toy_patient",
            "encounter_id": "toy_encounter",
            "ended_at": "toy_ended",
            "available_at": "toy_available",
        },
    }
    config = {
        "schema_version": 2,
        "execution_context": "ucsf",
        "institutional_access_confirmed": True,
        "mapping_reviewed": True,
        "source_coverage_reviewed": True,
        "observation_linkage_reviewed": True,
        "observation_end_reviewed": True,
        "qualifying_actions_reviewed": True,
        "terminal_semantics_reviewed": False,
        "laboratory_features_enabled": False,
        "time_encoding": "numeric_hours",
        "naive_time_policy": None,
        "horizon_hours": 24.0,
        "encounter_policy": "reject_order",
        "observation_encounter_policy": "reject_order",
        "administration_availability": "column",
        "occurrence_equality_policy": None,
        "qualifying_actions": ["toy-dose"],
        "orders": {"path": str(tmp_path / "orders"), "columns": columns["orders"]},
        "administrations": {
            "path": str(tmp_path / "administrations"),
            "columns": columns["administrations"],
        },
        "observations": {
            "path": str(tmp_path / "observations"),
            "columns": columns["observations"],
        },
        "limits": {
            "max_files_per_source": 4,
            "max_directories_per_source": 4,
            "max_entries_per_source": 20,
            "max_rows_per_source": 20,
            "max_keys": 100,
            "batch_rows": 2,
            "runtime_seconds": 60,
            "cpu_seconds": 60,
            "cpus": 1,
            "memory_mb": 512,
        },
    }
    path = tmp_path / "mapping.local.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path, config


def _physical(columns: dict, rows: list[dict]) -> list[dict]:
    return [
        {physical: row.get(logical) for logical, physical in columns.items() if physical}
        for row in rows
    ]


def _write_role(config: dict, role: str, name: str, rows: list[dict]) -> Path:
    path = Path(config[role]["path"]) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(_physical(config[role]["columns"], rows)), path)
    return path


def _rows():
    order = {
        "order_id": "toy-order",
        "patient_id": "toy-patient",
        "encounter_id": "toy-encounter",
        "occurred_at": 10.0,
        "available_at": 10.0,
        "observation_id": "toy-observation",
    }
    administration = {
        "administration_id": "toy-administration",
        "order_id": "toy-order",
        "patient_id": "toy-patient",
        "encounter_id": "toy-encounter",
        "occurred_at": 11.0,
        "available_at": 11.0,
        "action": "toy-dose",
    }
    observation = {
        "observation_id": "toy-observation",
        "patient_id": "toy-patient",
        "encounter_id": "toy-encounter",
        "ended_at": 20.0,
        "available_at": 20.0,
    }
    return order, administration, observation


def _manifest(mapping_path: Path, config: dict, files: dict[str, list[Path]], **limit_overrides):
    digest = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
    limits = {
        "max_files": 12,
        "max_row_groups": 24,
        "max_scanned_rows_per_source": 100,
        "max_row_group_bytes_per_source": 1024 * 1024,
        "max_retained_rows_per_source": 100,
        "max_seed_keys": 20,
    }
    limits.update(limit_overrides)
    value = {
        "schema_version": 1,
        "mode": "coherent_manifest",
        "mapping_sha256": digest,
        "snapshot": {
            "generation": "toy-generation",
            "immutable_provenance_reviewed": True,
            "evidence_reference": "toy-private-snapshot-review",
        },
        "seed": {
            "source": "orders",
            "selection_rule": "toy deterministic seed",
            "reviewed": True,
            "evidence_reference": "toy-private-seed-review",
        },
        "sources": {},
        "limits": limits,
    }
    for role in ("orders", "administrations", "observations"):
        value["sources"][role] = {
            "snapshot_generation": "toy-generation",
            "coverage_reviewed": True,
            "complete_for_seed_domain": True,
            "coverage_reference": f"toy-private-{role}-coverage",
            "locators": [{"path": str(path), "row_groups": [0]} for path in files[role]],
        }
    path = mapping_path.parent / "access.local.yaml"
    path.write_text(yaml.safe_dump(value, sort_keys=False))
    return path, value


def _case(tmp_path):
    mapping_path, config = _mapping(tmp_path)
    order, administration, observation = _rows()
    # Distractor prefix files prove the executor uses explicit reviewed locators.
    _write_role(config, "orders", "000-prefix.parquet", [dict(order, order_id="other-order")])
    _write_role(
        config,
        "administrations",
        "000-prefix.parquet",
        [dict(administration, order_id="other-order")],
    )
    _write_role(
        config,
        "observations",
        "000-prefix.parquet",
        [dict(observation, observation_id="other-observation")],
    )
    files = {
        "orders": [_write_role(config, "orders", "999-reviewed.parquet", [order])],
        "administrations": [
            _write_role(config, "administrations", "999-reviewed.parquet", [administration])
        ],
        "observations": [
            _write_role(config, "observations", "999-reviewed.parquet", [observation])
        ],
    }
    access_path, access = _manifest(mapping_path, config, files)
    return mapping_path, config, access_path, access, files


def test_coherent_manifest_finds_links_outside_independent_prefix(tmp_path):
    mapping_path, _, access_path, _, _ = _case(tmp_path)
    mapping, mapping_hash = load_mapping_snapshot(mapping_path)
    manifest, _ = load_access_snapshot(access_path, mapping, mapping_hash)
    report = inspect_coherent_sources(mapping, manifest)
    assert report["status"] == "complete"
    assert report["counts"]["accepted_execution_orders"] == 1
    assert report["counts"]["matched_direct_links"] == 1
    assert report["counts"]["matched_observation_links"] == 1
    assert report["access_mode"] == "coherent_manifest"
    assert report["coherent_linkage_coverage_verified"] is True
    assert all(v["files_read"] == 1 for v in report["access_counts"].values())


def test_plan_is_data_free_and_reports_only_public_budget(tmp_path, monkeypatch):
    mapping_path, _, access_path, _, _ = _case(tmp_path)
    monkeypatch.setattr(pq, "ParquetFile", lambda *a, **k: pytest.fail("plan read data"))
    plan = plan_feasibility(mapping_path, access_path)
    assert plan["sampling"] == "coherent_manifest"
    assert plan["coherent_linkage_coverage_verified"] is True
    rendered = yaml.safe_dump(plan)
    assert "toy-private" not in rendered and str(tmp_path) not in rendered


def test_manifest_mapping_binding_and_unknown_mode_fail_closed(tmp_path):
    mapping_path, config, access_path, access, _ = _case(tmp_path)
    mapping, digest = load_mapping_snapshot(mapping_path)
    access["mapping_sha256"] = "0" * 64
    access_path.write_text(yaml.safe_dump(access))
    with pytest.raises(FeasibilityError, match="invalid_access_manifest"):
        load_access_snapshot(access_path, mapping, digest)
    access["mapping_sha256"] = digest
    access["mode"] = "indexed_probe"
    access_path.write_text(yaml.safe_dump(access))
    with pytest.raises(FeasibilityError):
        load_access_snapshot(access_path, mapping, digest)
    assert config["orders"]["path"] not in str(FeasibilityError("invalid_access_manifest"))


def test_scanned_bound_forces_limited_and_suppresses_outcomes(tmp_path):
    mapping_path, config, _, _, files = _case(tmp_path)
    access_path, _ = _manifest(
        mapping_path,
        config,
        files,
        max_scanned_rows_per_source=1,
        max_retained_rows_per_source=1,
        max_seed_keys=1,
    )
    # Replace the reviewed order file with a two-row group that exceeds the cap atomically.
    order, _, _ = _rows()
    pq.write_table(
        pa.Table.from_pylist(_physical(config["orders"]["columns"], [order, order])),
        files["orders"][0],
        row_group_size=2,
    )
    mapping, digest = load_mapping_snapshot(mapping_path)
    manifest, _ = load_access_snapshot(access_path, mapping, digest)
    report = inspect_coherent_sources(mapping, manifest)
    assert report["status"] == "limited" and report["limits_reached"]["rows"]
    assert report["counts"]["accepted_execution_orders"] == 0
    assert report["coherent_linkage_coverage_verified"] is False


def test_row_group_byte_bound_forces_limited_before_materialization(tmp_path):
    mapping_path, config, _, _, files = _case(tmp_path)
    access_path, _ = _manifest(mapping_path, config, files, max_row_group_bytes_per_source=1)
    mapping, digest = load_mapping_snapshot(mapping_path)
    manifest, _ = load_access_snapshot(access_path, mapping, digest)
    report = inspect_coherent_sources(mapping, manifest)
    assert report["status"] == "limited" and report["limits_reached"]["bytes"]
    assert report["access_counts"]["orders"]["projected_rows_scanned"] == 0
    assert report["counts"]["accepted_execution_orders"] == 0


def test_unrelated_rows_consume_scan_not_retention_or_validation(tmp_path):
    mapping_path, config, access_path, _, files = _case(tmp_path)
    _, administration, observation = _rows()
    pq.write_table(
        pa.Table.from_pylist(
            _physical(
                config["administrations"]["columns"],
                [
                    administration,
                    dict(
                        administration,
                        order_id="unrelated-order",
                        administration_id=administration["administration_id"],
                    ),
                ],
            )
        ),
        files["administrations"][0],
    )
    pq.write_table(
        pa.Table.from_pylist(
            _physical(
                config["observations"]["columns"],
                [observation, dict(observation, observation_id="unrelated-observation")],
            )
        ),
        files["observations"][0],
    )
    mapping, digest = load_mapping_snapshot(mapping_path)
    manifest, _ = load_access_snapshot(access_path, mapping, digest)
    report = inspect_coherent_sources(mapping, manifest)
    assert report["status"] == "complete"
    assert report["counts"]["accepted_execution_orders"] == 1
    for role in ("administrations", "observations"):
        assert report["access_counts"][role]["projected_rows_scanned"] == 2
        assert report["access_counts"][role]["rows_retained"] == 1


def test_retained_bound_is_independent_of_scanned_bound(tmp_path):
    mapping_path, config, _, _, files = _case(tmp_path)
    _, administration, _ = _rows()
    pq.write_table(
        pa.Table.from_pylist(
            _physical(
                config["administrations"]["columns"],
                [administration, dict(administration, administration_id="toy-second-dose")],
            )
        ),
        files["administrations"][0],
    )
    access_path, _ = _manifest(
        mapping_path,
        config,
        files,
        max_retained_rows_per_source=1,
        max_seed_keys=1,
    )
    mapping, digest = load_mapping_snapshot(mapping_path)
    manifest, _ = load_access_snapshot(access_path, mapping, digest)
    report = inspect_coherent_sources(mapping, manifest)
    assert report["status"] == "limited" and report["limits_reached"]["rows"]
    assert report["access_counts"]["administrations"]["projected_rows_scanned"] == 2
    assert report["access_counts"]["administrations"]["rows_retained"] == 1
    assert report["counts"]["accepted_execution_orders"] == 0


def test_duplicate_order_outside_seed_location_remains_visible(tmp_path):
    mapping_path, config, _, _, files = _case(tmp_path)
    order, _, _ = _rows()
    duplicate = _write_role(config, "orders", "998-duplicate.parquet", [order])
    files["orders"].append(duplicate)
    access_path, _ = _manifest(mapping_path, config, files)
    mapping, digest = load_mapping_snapshot(mapping_path)
    manifest, _ = load_access_snapshot(access_path, mapping, digest)
    counts = inspect_coherent_sources(mapping, manifest)["counts"]
    assert counts["duplicate_order_identities"] == counts["rejected_orders"] == 1
    assert counts["accepted_execution_orders"] == 0


def test_locator_outside_mapping_root_and_changed_row_group_rejected(tmp_path):
    mapping_path, config, access_path, access, files = _case(tmp_path)
    mapping, digest = load_mapping_snapshot(mapping_path)
    access["sources"]["orders"]["locators"][0]["path"] = str(files["administrations"][0])
    access_path.write_text(yaml.safe_dump(access))
    with pytest.raises(FeasibilityError):
        load_access_snapshot(access_path, mapping, digest)
    access_path, access = _manifest(mapping_path, config, files)
    access["sources"]["orders"]["locators"][0]["row_groups"] = [99]
    access_path.write_text(yaml.safe_dump(access))
    manifest, _ = load_access_snapshot(access_path, mapping, digest)
    with pytest.raises(FeasibilityError, match="source_generation_changed"):
        inspect_coherent_sources(mapping, manifest)


def test_server_command_pins_access_digest_and_argument_order(tmp_path):
    mapping_path, _, access_path, _, _ = _case(tmp_path)
    server = load_script("server")
    config = {
        "python_executable": "/server/python",
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 1,
            "memory": "2G",
            "time_limit": "00:02:00",
        },
    }
    command = server.sbatch_command(
        config, "feasibility", tmp_path / "output", mapping_path, access_path
    )
    export = next(item for item in command if item.startswith("--export="))
    assert hashlib.sha256(mapping_path.read_bytes()).hexdigest() in export
    assert hashlib.sha256(access_path.read_bytes()).hexdigest() in export
    assert command[-5:] == [
        str(server.ROOT / "slurm/feasibility.sbatch"),
        "/server/python",
        str(mapping_path),
        str(access_path),
        str(tmp_path / "output/feasibility"),
    ]
