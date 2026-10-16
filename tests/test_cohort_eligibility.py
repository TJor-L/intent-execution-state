"""Generated-only tests for aggregate clinical cohort eligibility."""

import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from conftest import load_script

from ies import clinical_features, dual_clock_history
from ies.cli import main
from ies.clinical_features import extract_clinical_features
from ies.cohort_readiness.eligibility import (
    EligibilityError,
    _private_mapping_path,
    audit_eligibility,
    load_eligibility_mapping,
)
from ies.cohort_readiness.eligibility_runner import plan_eligibility
from ies.cohort_readiness.extract import extract_cohort
from ies.dual_clock_history import build_history_rows, extract_history, load_history_config
from ies.io import sha256

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


def test_only_ignored_local_config_reference_is_allowed_inside_repository():
    allowed = ROOT / "configs/toy.local.yaml"
    assert _private_mapping_path(str(allowed)) == allowed
    for path in (ROOT / "configs/tracked.yaml", ROOT / "src/toy.local.yaml"):
        with pytest.raises(EligibilityError, match="invalid_eligibility_mapping"):
            _private_mapping_path(str(path))


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


def _set_tiny_outcome_key_budget(mapping_path: Path) -> dict:
    eligibility = yaml.safe_load(mapping_path.read_text())
    base_path = Path(eligibility["feasibility_mapping"]["path"])
    base = yaml.safe_load(base_path.read_text())
    base["limits"]["max_keys"] = 3
    base_path.write_text(yaml.safe_dump(base, sort_keys=False))
    eligibility["feasibility_mapping"]["sha256"] = hashlib.sha256(
        base_path.read_bytes()
    ).hexdigest()
    mapping_path.write_text(yaml.safe_dump(eligibility, sort_keys=False))
    return base


def test_outcomes_are_batched_without_expanding_mapping_key_budget(tmp_path):
    mapping_path, _ = _write_case(tmp_path)
    _set_tiny_outcome_key_budget(mapping_path)
    report = audit_eligibility(load_eligibility_mapping(mapping_path)[0], 2, 1)
    assert report["thresholds"]["ready"] is True
    assert report["outcome_counts"]["accepted_execution_orders"] == 1
    assert report["outcome_counts"]["right_censored_orders"] == 1


def test_cross_batch_administration_duplicates_reject_every_linked_order(tmp_path):
    mapping_path, _ = _write_case(tmp_path)
    base = _set_tiny_outcome_key_budget(mapping_path)
    path = Path(base["administrations"]["path"]) / "part.parquet"
    table = pq.read_table(path)
    duplicate = table.to_pylist()[0]
    columns = base["administrations"]["columns"]
    duplicate.update(
        {
            columns["order_id"]: "order-1",
            columns["patient_id"]: "person-1",
            columns["encounter_id"]: "visit-1",
        }
    )
    duplicate_table = pa.Table.from_pylist([duplicate], schema=table.schema)
    pq.write_table(pa.concat_tables([table, duplicate_table]), path)
    report = audit_eligibility(load_eligibility_mapping(mapping_path)[0], 2, 1)
    assert report["thresholds"]["ready"] is False
    assert report["outcome_counts"]["duplicate_administration_identities"] == 1
    assert report["outcome_counts"]["rejected_orders"] >= 2


def test_cohort_rows_include_only_classified_orders_with_patient_exclusive_splits(tmp_path):
    mapping_path, _ = _write_case(tmp_path)
    value = yaml.safe_load(mapping_path.read_text())
    patient_path = Path(value["patients"]["path"]) / "part.parquet"
    patients = pq.read_table(patient_path).to_pylist()
    patients[2][value["patients"]["columns"]["birth_date"]] = date(1980, 1, 1)
    pq.write_table(pa.Table.from_pylist(patients), patient_path)
    encounter_path = Path(value["encounters"]["path"]) / "part.parquet"
    encounters = pq.read_table(encounter_path).to_pylist()
    encounters[2][value["encounters"]["columns"]["patient_class"]] = "toy-inpatient"
    pq.write_table(pa.Table.from_pylist(encounters), encounter_path)

    first = []
    second = []
    mapping = load_eligibility_mapping(mapping_path)[0]
    audit_eligibility(mapping, 3, 1, cohort_rows=first)
    audit_eligibility(mapping, 3, 1, cohort_rows=second)

    assert first == second
    assert {row["order_id"] for row in first} == {
        "string:order-0",
        "string:order-1",
        "string:order-2",
    }
    assert {row["outcome"] for row in first} == {"execution", "right_censored"}
    patient_splits = {(row["patient_id"], row["split"]) for row in first}
    assert len(patient_splits) == 3
    assert {split for _, split in patient_splits} == {"train", "validation", "test"}


def test_rejected_cross_batch_duplicate_orders_never_enter_cohort_rows(tmp_path):
    mapping_path, _ = _write_case(tmp_path)
    base = _set_tiny_outcome_key_budget(mapping_path)
    path = Path(base["administrations"]["path"]) / "part.parquet"
    table = pq.read_table(path)
    duplicate = table.to_pylist()[0]
    columns = base["administrations"]["columns"]
    duplicate.update(
        {
            columns["order_id"]: "order-1",
            columns["patient_id"]: "person-1",
            columns["encounter_id"]: "visit-1",
        }
    )
    pq.write_table(
        pa.concat_tables([table, pa.Table.from_pylist([duplicate], schema=table.schema)]),
        path,
    )
    rows = []
    mapping = load_eligibility_mapping(mapping_path)[0]
    with pytest.raises(EligibilityError, match="eligibility_thresholds_not_met"):
        audit_eligibility(mapping, 1, 1, cohort_rows=rows)
    assert rows == []


def test_private_extraction_writes_bound_manifest_and_rejects_overwrite(tmp_path):
    mapping_path, protocol_path = _write_case(tmp_path)
    value = yaml.safe_load(mapping_path.read_text())
    patient_path = Path(value["patients"]["path"]) / "part.parquet"
    patients = pq.read_table(patient_path).to_pylist()
    patients[2][value["patients"]["columns"]["birth_date"]] = date(1980, 1, 1)
    pq.write_table(pa.Table.from_pylist(patients), patient_path)
    encounter_path = Path(value["encounters"]["path"]) / "part.parquet"
    encounters = pq.read_table(encounter_path).to_pylist()
    encounters[2][value["encounters"]["columns"]["patient_class"]] = "toy-inpatient"
    pq.write_table(pa.Table.from_pylist(encounters), encounter_path)

    mapping, mapping_digest = load_eligibility_mapping(mapping_path)
    protocol_digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    output = tmp_path / "private-output"
    output.mkdir(mode=0o700)
    manifest = extract_cohort(
        mapping,
        3,
        1,
        output,
        mapping_digest,
        protocol_digest,
        "a" * 40,
    )

    assert manifest["status"] == "complete"
    assert manifest["mapping_sha256"] == mapping_digest
    assert manifest["protocol_sha256"] == protocol_digest
    assert manifest["population_counts_complete"] is True
    assert pq.read_table(output / "cohort.parquet").num_rows == 3
    for filename, digest in manifest["artifacts_sha256"].items():
        assert sha256(output / filename) == digest
        assert (output / filename).stat().st_mode & 0o077 == 0
    assert (output / "manifest.json").stat().st_mode & 0o077 == 0
    with pytest.raises(EligibilityError, match="extraction_output_not_empty"):
        extract_cohort(mapping, 3, 1, output, mapping_digest, protocol_digest, "a" * 40)


def test_age_feature_is_preindex_aligned_and_bound_to_cohort(tmp_path, monkeypatch):
    mapping_path, protocol_path = _write_case(tmp_path)
    value = yaml.safe_load(mapping_path.read_text())
    patient_path = Path(value["patients"]["path"]) / "part.parquet"
    patients = pq.read_table(patient_path).to_pylist()
    patients[2][value["patients"]["columns"]["birth_date"]] = date(1980, 1, 1)
    pq.write_table(pa.Table.from_pylist(patients), patient_path)
    encounter_path = Path(value["encounters"]["path"]) / "part.parquet"
    encounters = pq.read_table(encounter_path).to_pylist()
    encounters[2][value["encounters"]["columns"]["patient_class"]] = "toy-inpatient"
    pq.write_table(pa.Table.from_pylist(encounters), encounter_path)
    mapping, mapping_digest = load_eligibility_mapping(mapping_path)
    protocol_digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    cohort = tmp_path / "cohort"
    cohort.mkdir()
    extract_cohort(mapping, 3, 1, cohort, mapping_digest, protocol_digest, "a" * 40)
    cohort_digest = sha256(cohort / "manifest.json")
    output = tmp_path / "features"
    output.mkdir()
    monkeypatch.setattr(clinical_features, "AUTHORIZED_ROOT", tmp_path)

    manifest = extract_clinical_features(
        mapping,
        3,
        1,
        cohort,
        output,
        cohort_digest,
        mapping_digest,
        protocol_digest,
        "b" * 40,
    )

    assert manifest["features"] == ["age_years_at_order"]
    assert manifest["outcome_features_used"] is False
    features = pq.read_table(output / "features.parquet")
    assert features.num_rows == pq.read_table(cohort / "cohort.parquet").num_rows
    assert all(value >= 18 for value in features.column("age_years_at_order").to_pylist())
    assert all(path.stat().st_mode & 0o077 == 0 for path in output.iterdir())
    server = load_script("server")
    command = server.sbatch_command(
        {
            "python_executable": "/server/python",
            "output_root": str(tmp_path),
            "slurm": {
                "partition": "cpu",
                "account": None,
                "cpus": 4,
                "memory": "8G",
                "time_limit": "00:20:00",
            },
        },
        "clinical-features",
        tmp_path / "job",
        mapping_path,
        protocol_path=protocol_path,
        cohort_dir=cohort,
    )
    export = next(item for item in command if item.startswith("--export="))
    assert "IES_COHORT_MANIFEST_SHA256=" in export
    assert "IES_ELIGIBILITY_SHA256=" in export and "IES_PROTOCOL_SHA256=" in export
    assert str(server.ROOT / "slurm/clinical_features.sbatch") in command
    history_command = server.sbatch_command(
        {
            "python_executable": "/server/python",
            "output_root": str(tmp_path),
            "slurm": {
                "partition": "cpu",
                "account": None,
                "cpus": 4,
                "memory": "8G",
                "time_limit": "00:20:00",
            },
        },
        "dual-clock-history",
        tmp_path / "history-job",
        mapping_path,
        cohort_dir=cohort,
        history_config=ROOT / "configs/dual_clock_history.yaml",
    )
    history_export = next(item for item in history_command if item.startswith("--export="))
    assert "IES_HISTORY_CONFIG_SHA256=" in history_export
    assert "IES_COHORT_MANIFEST_SHA256=" in history_export
    assert str(server.ROOT / "slurm/dual_clock_history.sbatch") in history_command

    eligibility_value = yaml.safe_load(mapping_path.read_text())
    feasibility_value = yaml.safe_load(
        Path(eligibility_value["feasibility_mapping"]["path"]).read_text()
    )
    order_path = Path(feasibility_value["orders"]["path"]) / "part.parquet"
    order_table = pq.read_table(order_path)
    prior_order = order_table.to_pylist()[0]
    order_columns = feasibility_value["orders"]["columns"]
    prior_order.update(
        {
            order_columns["order_id"]: "prior-order",
            order_columns["occurred_at"]: datetime(2020, 1, 2, 10),
            order_columns["available_at"]: datetime(2020, 1, 2, 10, 30),
        }
    )
    pq.write_table(
        pa.concat_tables(
            [order_table, pa.Table.from_pylist([prior_order], schema=order_table.schema)]
        ),
        order_path,
    )
    administration_path = Path(feasibility_value["administrations"]["path"]) / "part.parquet"
    administration_table = pq.read_table(administration_path)
    prior_dose = administration_table.to_pylist()[0]
    administration_columns = feasibility_value["administrations"]["columns"]
    prior_dose.update(
        {
            administration_columns["administration_id"]: "prior-dose",
            administration_columns["order_id"]: "prior-order",
            administration_columns["occurred_at"]: datetime(2020, 1, 2, 11),
            administration_columns["available_at"]: datetime(2020, 1, 2, 11, 15),
        }
    )
    pq.write_table(
        pa.concat_tables(
            [
                administration_table,
                pa.Table.from_pylist([prior_dose], schema=administration_table.schema),
            ]
        ),
        administration_path,
    )
    history_config, history_digest = load_history_config(ROOT / "configs/dual_clock_history.yaml")
    history_config.update(minimum_history_events=1, minimum_orders_with_history=1)
    history_output = tmp_path / "history-output"
    history_output.mkdir()
    monkeypatch.setattr(dual_clock_history, "AUTHORIZED_ROOT", tmp_path)
    history_manifest = extract_history(
        mapping.feasibility,
        mapping.limits,
        cohort,
        history_output,
        history_config,
        history_digest,
        cohort_digest,
        mapping_digest,
        "c" * 40,
    )
    assert history_manifest["status"] == "complete"
    assert history_manifest["availability_masked"] is True
    history_table = pq.read_table(history_output / "history.parquet")
    assert {row["event_id"] for row in history_table.to_pylist()} == {
        "string:prior-order",
        "string:prior-dose",
    }


def test_dual_clock_history_excludes_unavailable_and_post_index_events(tmp_path):
    mapping_path, _ = _write_case(tmp_path)
    mapping = load_eligibility_mapping(mapping_path)[0].feasibility
    config = load_history_config(ROOT / "configs/dual_clock_history.yaml")[0]
    start = datetime(2020, 1, 2, 12)
    indexes = {
        ("string", "person-0"): [
            {
                "patient_id": "string:person-0",
                "order_id": "string:index-0",
                "index_time_hours": (start - datetime(1970, 1, 1)).total_seconds() / 3600,
            }
        ]
    }
    orders = [
        {
            "order_id": "prior-visible",
            "patient_id": "person-0",
            "occurred_at": start - timedelta(hours=2),
            "available_at": start - timedelta(hours=1),
        },
        {
            "order_id": "prior-unavailable",
            "patient_id": "person-0",
            "occurred_at": start - timedelta(hours=2),
            "available_at": start + timedelta(hours=1),
        },
        {
            "order_id": "index-0",
            "patient_id": "person-0",
            "occurred_at": start,
            "available_at": start,
        },
        {
            "order_id": "invalid-time",
            "patient_id": "person-0",
            "occurred_at": start - timedelta(hours=1),
            "available_at": None,
        },
    ]
    administrations = [
        {
            "administration_id": "dose-visible",
            "order_id": "prior-visible",
            "patient_id": "person-0",
            "occurred_at": start - timedelta(minutes=30),
            "available_at": start - timedelta(minutes=15),
            "action": "given",
        },
        {
            "administration_id": "dose-future",
            "order_id": "index-0",
            "patient_id": "person-0",
            "occurred_at": start + timedelta(hours=1),
            "available_at": start + timedelta(hours=1),
            "action": "given",
        },
    ]
    rows, per_order = build_history_rows(orders, administrations, indexes, mapping, config)
    assert {row["event_id"] for row in rows} == {
        "string:prior-visible",
        "string:dose-visible",
    }
    assert per_order["string:index-0"] == 2
    assert all(row["availability_lag_hours"] >= 0 for row in rows)
    assert all(row["documentation_delay_hours"] >= 0 for row in rows)
    limited_config = dict(config, max_events_per_order=1)
    limited, totals = build_history_rows(orders, administrations, indexes, mapping, limited_config)
    assert [row["event_id"] for row in limited] == ["string:dose-visible"]
    assert totals["string:index-0"] == 2


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
    extract_command = server.sbatch_command(
        config,
        "cohort-extract",
        tmp_path / "extract-output",
        mapping_path,
        protocol_path=protocol_path,
    )
    extract_export = next(item for item in extract_command if item.startswith("--export="))
    assert "IES_ELIGIBILITY_SHA256=" in extract_export
    assert "IES_PROTOCOL_SHA256=" in extract_export
    assert str(server.ROOT / "slurm/cohort_extract.sbatch") in extract_command
    assert extract_command[-1] == str(tmp_path / "extract-output/cohort-extract")


def test_cli_returns_nonzero_for_limited_eligibility(monkeypatch, capsys):
    monkeypatch.setattr(
        "ies.cli.dispatch",
        lambda args: {"mode": "aggregate_cohort_eligibility", "status": "limited"},
    )
    assert (
        main(
            [
                "cohort-eligibility",
                "run",
                "--mapping",
                "/private/mapping.local.yaml",
                "--protocol",
                "/private/protocol.local.yaml",
                "--output-dir",
                "/private/output",
            ]
        )
        == 2
    )
    assert "private" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "cohort-extract",
            "run",
            "--mapping",
            "/private/mapping.local.yaml",
            "--protocol",
            "/private/protocol.local.yaml",
            "--output-dir",
            "/private/output",
        ],
        [
            "clinical-baseline",
            "run",
            "--cohort-dir",
            "/private/cohort",
            "--baseline-config",
            "/private/baseline.yaml",
            "--output-dir",
            "/private/output",
        ],
        [
            "clinical-features",
            "run",
            "--mapping",
            "/private/mapping.local.yaml",
            "--protocol",
            "/private/protocol.local.yaml",
            "--cohort-dir",
            "/private/cohort",
            "--output-dir",
            "/private/output",
        ],
        [
            "clinical-age-baseline",
            "run",
            "--cohort-dir",
            "/private/cohort",
            "--feature-dir",
            "/private/features",
            "--baseline-config",
            "/private/baseline.yaml",
            "--output-dir",
            "/private/output",
        ],
        [
            "dual-clock-history",
            "run",
            "--mapping",
            "/private/mapping.local.yaml",
            "--history-config",
            "/private/history.yaml",
            "--cohort-dir",
            "/private/cohort",
            "--output-dir",
            "/private/output",
        ],
    ],
)
def test_private_commands_return_nonzero_for_failed_status(arguments, monkeypatch, capsys):
    monkeypatch.setattr("ies.cli.dispatch", lambda args: {"status": "failed"})
    assert main(arguments) == 2
    assert "private" not in capsys.readouterr().out
