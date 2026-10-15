"""Generated-only tests for aggregate clinical cohort eligibility."""

import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from conftest import load_script

from ies.cli import main
from ies.cohort_readiness.eligibility import (
    EligibilityError,
    audit_eligibility,
    load_eligibility_mapping,
)
from ies.cohort_readiness.eligibility_runner import plan_eligibility

ROOT = Path(__file__).resolve().parents[1]


def _base_mapping(tmp_path: Path) -> tuple[Path, dict]:
    value = yaml.safe_load((ROOT / "configs/feasibility.example.yaml").read_text())
    for flag in (
        "institutional_access_confirmed",
        "mapping_reviewed",
        "source_coverage_reviewed",
        "observation_linkage_reviewed",
        "observation_end_reviewed",
        "qualifying_actions_reviewed",
    ):
        value[flag] = True
    value["time_encoding"] = "timestamp_naive"
    value["naive_time_policy"] = {
        "reviewed": True,
        "clock": "shifted_common",
        "timezone": None,
        "ambiguous": "reject",
        "nonexistent": "reject",
        "evidence_reference": "toy shifted clock review",
    }
    value["qualifying_actions"] = ["given"]
    value["terminal_semantics_reviewed"] = True
    value["limits"]["max_rows_per_source"] = 100
    value["limits"]["batch_rows"] = 2
    for role in ("orders", "administrations", "observations"):
        value[role]["path"] = str(tmp_path / role)
        value[role]["columns"] = {logical: f"toy_{logical}" for logical in value[role]["columns"]}
        Path(value[role]["path"]).mkdir()
    value["administrations"]["columns"]["documentation_status"] = None
    path = tmp_path / "feasibility.local.yaml"
    path.write_text(yaml.safe_dump(value, sort_keys=False))
    return path, value


def _eligibility_mapping(tmp_path: Path) -> tuple[Path, dict, dict]:
    base_path, base = _base_mapping(tmp_path)
    value = yaml.safe_load((ROOT / "configs/cohort_eligibility.example.yaml").read_text())
    value.update(
        institutional_access_confirmed=True,
        mapping_reviewed=True,
        protocol_frozen_reviewed=True,
        criteria_reviewed=True,
        evidence_reference="toy generated review",
    )
    value["feasibility_mapping"] = {
        "path": str(base_path),
        "sha256": hashlib.sha256(base_path.read_bytes()).hexdigest(),
    }
    value["order_criteria_columns"] = {
        "therapeutic_class": "toy_class",
        "route": "toy_route",
        "prn": "toy_prn",
        "frequency": "toy_frequency",
    }
    value["patients"] = {
        "path": str(tmp_path / "patients"),
        "columns": {
            "patient_id": "toy_patient_id",
            "birth_date": "toy_birth_date",
            "current_status": "toy_current",
            "valid_status": "toy_valid",
        },
    }
    value["encounters"] = {
        "path": str(tmp_path / "encounters"),
        "columns": {
            "encounter_id": "toy_encounter_id",
            "patient_id": "toy_patient_id",
            "patient_class": "toy_patient_class",
        },
    }
    Path(value["patients"]["path"]).mkdir()
    Path(value["encounters"]["path"]).mkdir()
    value["accepted_values"] = {
        "therapeutic_class": ["toy-diuretic"],
        "route": ["toy-iv"],
        "non_prn": [False],
        "one_time_frequency": ["toy-once"],
        "current_status": [True],
        "valid_status": [True],
        "inpatient_class": ["toy-inpatient"],
    }
    value["limits"].update(
        max_files_per_source=4,
        max_entries_per_source=8,
        max_row_groups_per_source=8,
        max_rows_per_source=100,
        max_source_bytes=1_000_000,
        max_candidate_orders=20,
        max_retained_rows_per_source=60,
        batch_rows=2,
        runtime_seconds=30,
        cpu_seconds=30,
        cpus=1,
        memory_mb=1024,
    )
    path = tmp_path / "eligibility.local.yaml"
    path.write_text(yaml.safe_dump(value, sort_keys=False))
    return path, value, base


def _physical(columns: dict, rows: list[dict]) -> pa.Table:
    return pa.Table.from_pylist(
        [
            {physical: row.get(logical) for logical, physical in columns.items() if physical}
            for row in rows
        ]
    )


def _write_case(tmp_path: Path) -> tuple[Path, Path]:
    mapping_path, config, base = _eligibility_mapping(tmp_path)
    start = datetime(2020, 1, 2, 12)
    orders = []
    administrations = []
    observations = []
    patients = []
    encounters = []
    for index in range(4):
        patient = f"person-{index}"
        encounter = f"visit-{index}"
        order = f"order-{index}"
        observation = f"coverage-{index}"
        orders.append(
            {
                "order_id": order,
                "patient_id": patient,
                "encounter_id": encounter,
                "occurred_at": start,
                "available_at": start,
                "observation_id": observation,
                "therapeutic_class": "toy-diuretic",
                "route": "toy-iv",
                "prn": False,
                "frequency": "toy-once",
            }
        )
        observations.append(
            {
                "observation_id": observation,
                "patient_id": patient,
                "encounter_id": encounter,
                "ended_at": start + timedelta(hours=24),
                "available_at": start + timedelta(hours=24),
            }
        )
        patients.append(
            {
                "patient_id": patient,
                "birth_date": date(1980, 1, 1) if index != 2 else date(2010, 1, 1),
                "current_status": True,
                "valid_status": True,
            }
        )
        encounters.append(
            {
                "encounter_id": encounter,
                "patient_id": patient,
                "patient_class": "toy-inpatient" if index != 3 else "toy-outpatient",
            }
        )
    administrations.append(
        {
            "administration_id": "dose-0",
            "order_id": "order-0",
            "patient_id": "person-0",
            "encounter_id": "visit-0",
            "occurred_at": start + timedelta(hours=1),
            "available_at": start + timedelta(hours=1),
            "action": "given",
        }
    )
    order_columns = {
        **{k: v for k, v in base["orders"]["columns"].items() if v},
        **config["order_criteria_columns"],
    }
    pq.write_table(_physical(order_columns, orders), Path(base["orders"]["path"]) / "part.parquet")
    pq.write_table(
        _physical(base["administrations"]["columns"], administrations),
        Path(base["administrations"]["path"]) / "part.parquet",
    )
    pq.write_table(
        _physical(base["observations"]["columns"], observations),
        Path(base["observations"]["path"]) / "part.parquet",
    )
    pq.write_table(
        _physical(config["patients"]["columns"], patients),
        Path(config["patients"]["path"]) / "part.parquet",
    )
    pq.write_table(
        _physical(config["encounters"]["columns"], encounters),
        Path(config["encounters"]["path"]) / "part.parquet",
    )
    protocol = yaml.safe_load((ROOT / "configs/clinical_protocol.example.yaml").read_text())
    protocol["status"] = "frozen"
    protocol["population"].update(
        adult_derivation_reviewed=True,
        adult_derivation_evidence_reference="toy adult",
        inpatient_definition_reviewed=True,
        inpatient_definition_evidence_reference="toy inpatient",
        medication_categories=["toy medication"],
        medication_category_system="toy system",
        medication_eligibility_reviewed=True,
        medication_eligibility_evidence_reference="toy medication",
    )
    protocol["acceptance"].update(minimum_eligible_orders=2, minimum_execution_events=1)
    protocol_path = tmp_path / "clinical_protocol.local.yaml"
    protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))
    return mapping_path, protocol_path


def test_aggregate_audit_applies_adult_inpatient_and_outcome_rules(tmp_path):
    mapping_path, _ = _write_case(tmp_path)
    report = audit_eligibility(load_eligibility_mapping(mapping_path)[0], 2, 1)
    assert report["status"] == "complete" and report["source_stable"] is True
    assert report["counts"]["one_time_non_prn_orders"] == 4
    assert report["counts"]["adult_inpatient_orders"] == 2
    assert report["outcome_counts"]["accepted_execution_orders"] == 1
    assert report["outcome_counts"]["right_censored_orders"] == 1
    assert report["thresholds"]["ready"] is True
    assert report["row_persistence"] is False


def test_unreviewed_values_and_changed_base_mapping_fail_closed(tmp_path):
    path, value, _ = _eligibility_mapping(tmp_path)
    value["accepted_values"]["one_time_frequency"] = []
    path.write_text(yaml.safe_dump(value))
    with pytest.raises(EligibilityError, match="invalid_eligibility_mapping"):
        load_eligibility_mapping(path)
    value["accepted_values"]["one_time_frequency"] = ["toy-once"]
    value["feasibility_mapping"]["sha256"] = "0" * 64
    path.write_text(yaml.safe_dump(value))
    with pytest.raises(EligibilityError):
        load_eligibility_mapping(path)


def test_plan_is_data_free_and_suppresses_private_values(tmp_path, monkeypatch):
    mapping_path, protocol_path = _write_case(tmp_path)
    monkeypatch.setattr(pq, "ParquetFile", lambda *a, **k: pytest.fail("plan read data"))
    plan = plan_eligibility(mapping_path, protocol_path)
    rendered = yaml.safe_dump(plan)
    assert plan["population_counts_may_be_lower_bounds"] is True
    assert str(tmp_path) not in rendered and "toy-diuretic" not in rendered


def test_candidate_cap_produces_sound_lower_bound_not_population_count(tmp_path):
    mapping_path, _ = _write_case(tmp_path)
    value = yaml.safe_load(mapping_path.read_text())
    value["limits"]["max_candidate_orders"] = 1
    mapping_path.write_text(yaml.safe_dump(value))
    report = audit_eligibility(load_eligibility_mapping(mapping_path)[0], 1, 1)
    assert report["population_counts_complete"] is False
    assert report["counts"]["candidate_orders_not_retained"] == 3
    assert report["threshold_evidence_complete"] is True


def test_cli_plan_and_server_submission_are_sanitized_and_digest_bound(tmp_path, capsys):
    mapping_path, protocol_path = _write_case(tmp_path)
    assert (
        main(
            [
                "cohort-eligibility",
                "plan",
                "--mapping",
                str(mapping_path),
                "--protocol",
                str(protocol_path),
            ]
        )
        == 0
    )
    assert str(tmp_path) not in capsys.readouterr().out
    server = load_script("server")
    config = {
        "python_executable": "/server/python",
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 4,
            "memory": "8G",
            "time_limit": "00:20:00",
        },
    }
    command = server.sbatch_command(
        config,
        "cohort-eligibility",
        tmp_path / "output",
        mapping_path,
        protocol_path=protocol_path,
    )
    export = next(item for item in command if item.startswith("--export="))
    assert "IES_ELIGIBILITY_SHA256=" in export and "IES_PROTOCOL_SHA256=" in export
    assert str(server.ROOT / "slurm/cohort_eligibility.sbatch") in command
    assert command[-3:] == [
        str(mapping_path.absolute()),
        str(protocol_path.absolute()),
        str(tmp_path / "output/cohort-eligibility"),
    ]
