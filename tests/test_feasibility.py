"""All rows, fields, actions, identities and paths in these tests are generated toys."""

import hashlib
import json
import os
import signal
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from conftest import ROOT, load_script

from ies.cli import main
from ies.feasibility import runner, worker
from ies.feasibility.analysis import Budget, analyze, known_by
from ies.feasibility.contract import FeasibilityError, parse_mapping
from ies.feasibility.reader import inspect_sources
from ies.preprocessing.cohort import patient_partitions


@pytest.fixture
def case(tmp_path):
    config = yaml.safe_load((ROOT / "configs/feasibility.example.yaml").read_text())
    for flag in (
        "institutional_access_confirmed",
        "mapping_reviewed",
        "source_coverage_reviewed",
        "qualifying_actions_reviewed",
        "terminal_semantics_reviewed",
    ):
        config[flag] = True
    config["time_encoding"] = "numeric_hours"
    config["qualifying_actions"] = ["toy-dose"]
    for kind in ("orders", "administrations"):
        config[kind]["path"] = str(tmp_path / "inputs" / f"{kind}.parquet")
        config[kind]["columns"] = {
            logical: f"toy_slot_{i}" for i, logical in enumerate(config[kind]["columns"])
        }
    order = {
        "order_id": "toy-order-0",
        "patient_id": "toy-person-0",
        "encounter_id": "toy-encounter-0",
        "occurred_at": 48.0,
        "available_at": 48.0,
        "observation_end_at": 72.0,
        "discontinued_at": None,
        "discontinued_available_at": None,
        "ended_at": None,
        "ended_available_at": None,
    }
    administration = {
        "administration_id": "toy-dose-0",
        "order_id": "toy-order-0",
        "patient_id": "toy-person-0",
        "encounter_id": "toy-encounter-0",
        "occurred_at": 50.0,
        "available_at": 50.5,
        "action": "toy-dose",
    }
    return config, order, administration


def result(case, *, orders=None, administrations=None):
    config, order, administration = case
    return analyze(
        [order] if orders is None else orders,
        [administration] if administrations is None else administrations,
        parse_mapping(config),
    )


def write_sources(case, orders=None, administrations=None):
    config, order, administration = case
    for kind, data in (
        ("orders", [order] if orders is None else orders),
        ("administrations", [administration] if administrations is None else administrations),
    ):
        path = Path(config[kind]["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = config[kind]["columns"]
        rows = [
            {physical: row.get(logical) for logical, physical in columns.items() if physical}
            for row in data
        ]
        if rows:
            table = pa.Table.from_pylist(rows)
        else:
            table = pa.table(
                {
                    physical: pa.array([], type=pa.null())
                    for physical in columns.values()
                    if physical
                }
            )
        pq.write_table(table, path, row_group_size=3)
    return parse_mapping(config)


def test_valid_linkage_and_aggregate_only(case):
    report = result(case)
    assert report["status"] == "complete"
    assert report["counts"]["accepted_execution_orders"] == 1
    assert report["counts"]["matched_direct_links"] == 1
    rendered = json.dumps(report)
    assert "toy-" not in rendered and "toy_slot" not in rendered
    assert str(Path(case[0]["orders"]["path"]).parent) not in rendered
    assert all(type(n) is int and n >= 0 for n in report["counts"].values())


@pytest.mark.parametrize(
    "field,value,counter",
    [
        ("patient_id", "toy-other", "patient_mismatches"),
        ("encounter_id", "toy-other", "encounter_mismatches"),
        ("encounter_id", None, "encounter_missing_links"),
        ("administration_id", None, "missing_administration_identities"),
        ("occurred_at", None, "missing_required_times"),
        ("available_at", 49.0, "temporal_ordering_violations"),
        ("occurred_at", 47.0, "temporal_ordering_violations"),
        ("action", None, "missing_actions"),
    ],
)
def test_invalid_link_or_time_rejects_order(case, field, value, counter):
    case[2][field] = value
    counts = result(case)["counts"]
    assert counts[counter] == 1
    assert counts["rejected_orders"] == 1
    assert counts["accepted_execution_orders"] == counts["right_censored_orders"] == 0


def test_explicit_count_only_encounter_policy_and_absent_mapping(case):
    case[0]["encounter_policy"] = "count_only"
    case[2]["encounter_id"] = "toy-other"
    counts = result(case)["counts"]
    assert counts["encounter_mismatches"] == counts["accepted_execution_orders"] == 1
    for source in ("orders", "administrations"):
        case[0][source]["columns"]["encounter_id"] = None
    counts = result(case)["counts"]
    assert counts["encounter_checks_unavailable"] == 1


def test_missing_direct_link_is_unmatched_not_a_failed_execution(case):
    case[2]["order_id"] = None
    report = result(case)
    assert report["counts"]["missing_direct_order_identity"] == 1
    assert report["counts"]["unmatched_direct_links"] == 1
    assert report["counts"]["right_censored_orders"] == 1
    assert "failed_execution" not in json.dumps(report)


def test_repeated_doses_rejected_including_after_observation_end(case):
    second = dict(case[2], administration_id="toy-dose-1", occurred_at=100.0, available_at=100.0)
    counts = result(case, administrations=[case[2], second])["counts"]
    assert counts["qualifying_actions"] == 2
    assert counts["repeated_qualifying_orders"] == counts["rejected_orders"] == 1
    assert counts["accepted_execution_orders"] == 0


def test_non_dose_continuation_excluded_by_reviewed_policy(case):
    continuation = dict(case[2], administration_id="toy-continuation", action="toy-continue")
    counts = result(case, administrations=[continuation, case[2]])["counts"]
    assert counts["excluded_actions"] == 1
    assert counts["single_qualifying_orders"] == counts["accepted_execution_orders"] == 1


@pytest.mark.parametrize("terminal", ["discontinued", "ended"])
def test_terminal_distinct_from_execution_and_censoring(case, terminal):
    case[1][f"{terminal}_at"] = 49.0
    case[1][f"{terminal}_available_at"] = 49.5
    counts = result(case, administrations=[])["counts"]
    assert counts["terminal_without_execution_orders"] == 1
    assert counts["right_censored_orders"] == counts["accepted_execution_orders"] == 0
    case[1]["observation_end_at"] = 49.25
    assert result(case, administrations=[])["counts"]["right_censored_orders"] == 1


def test_observation_end_and_delayed_availability_censor_without_failure(case):
    case[1]["observation_end_at"] = 49.0
    assert result(case)["counts"]["right_censored_orders"] == 1
    case[1]["observation_end_at"] = 72.0
    case[2]["available_at"] = 73.0
    counts = result(case)["counts"]
    assert counts["right_censored_orders"] == counts["administrations_unavailable_at_boundary"] == 1
    assert result(case, administrations=[])["counts"]["right_censored_orders"] == 1


def test_index_availability_and_post_cutoff_features(case):
    assert known_by(47.0, 48.0, 48.0)
    assert not known_by(47.0, 49.0, 48.0)  # Measured before cutoff, first known after it.
    assert not known_by(49.0, 49.0, 48.0)
    assert not known_by(48.0, 47.0, 48.0)
    case[1]["available_at"] = 49.0
    assert result(case)["counts"]["order_unavailable_at_index"] == 1
    case[0]["laboratory_features_enabled"] = True
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


def test_duplicate_identity_rejection(case):
    counts = result(case, orders=[case[1], dict(case[1])])["counts"]
    assert counts["duplicate_order_identities"] == counts["rejected_orders"] == 1
    counts = result(case, administrations=[case[2], dict(case[2])])["counts"]
    assert counts["duplicate_administration_identities"] == counts["rejected_orders"] == 1


def test_terminal_competition_and_tie(case):
    case[1].update(discontinued_at=49.0, discontinued_available_at=49.0)
    assert result(case)["counts"]["terminal_without_execution_orders"] == 1
    case[1].update(discontinued_at=50.0, discontinued_available_at=50.0)
    counts = result(case)["counts"]
    assert counts["ambiguous_terminal_ties"] == counts["rejected_orders"] == 1
    case[1].update(discontinued_at=51.0, discontinued_available_at=51.0)
    assert result(case)["counts"]["accepted_execution_orders"] == 1


def test_time_encoding_explicit_utc_and_shifted_dates(case):
    config, order, administration = case
    config["time_encoding"] = "timestamp_utc"
    # Future shifted dates are allowed; use only intervals within each patient.
    base = datetime(2126, 1, 1, tzinfo=UTC)
    for row in (order, administration):
        for field in list(row):
            if field.endswith("_at") and row[field] is not None:
                row[field] = base + timedelta(hours=row[field])
    assert result(case)["counts"]["accepted_execution_orders"] == 1
    order["occurred_at"] = order["occurred_at"].replace(tzinfo=None)
    assert result(case)["counts"]["invalid_time_values"] == 1


def test_availability_equality_requires_explicit_reviewed_policy(case):
    config = case[0]
    config["administrations"]["columns"]["available_at"] = None
    with pytest.raises(FeasibilityError):
        parse_mapping(config)
    config["administration_availability"] = "occurrence_reviewed"
    assert result(case)["counts"]["accepted_execution_orders"] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("institutional_access_confirmed", False),
        ("mapping_reviewed", False),
        ("source_coverage_reviewed", False),
        ("qualifying_actions_reviewed", False),
        ("terminal_semantics_reviewed", False),
        ("qualifying_actions", []),
        ("time_encoding", None),
        ("encounter_policy", "guess"),
        ("horizon_hours", float("nan")),
    ],
)
def test_contract_fails_closed(case, field, value):
    case[0][field] = value
    with pytest.raises(FeasibilityError, match="invalid_mapping"):
        parse_mapping(case[0])


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_files_per_source", 0),
        ("max_rows_per_source", 100001),
        ("memory_mb", 1),
        ("cpus", 8),
        ("runtime_seconds", 0),
        ("max_keys", True),
    ],
)
def test_explicit_hard_resource_limits(case, field, value):
    case[0]["limits"][field] = value
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


def test_no_invented_columns_or_relative_paths(case):
    case[0]["orders"]["columns"]["order_id"] = None
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])
    case[0]["orders"]["columns"]["order_id"] = "toy_slot_0"
    case[0]["orders"]["path"] = "relative.parquet"
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


def test_patient_split_invariants_remain_patient_level():
    patient_ids = [f"toy-person-{i // 3}" for i in range(30)]
    split = patient_partitions(patient_ids, 123)
    assert split == patient_partitions(patient_ids[::-1], 123)
    sets = [
        {p for p in patient_ids if split[p] == name} for name in ("train", "validation", "test")
    ]
    assert all(sets) and not any(a & b for i, a in enumerate(sets) for b in sets[i + 1 :])


def test_projected_reader_matches_analysis_without_read_table(case, monkeypatch):
    mapping = write_sources(case)
    monkeypatch.setattr(pq, "read_table", lambda *a, **k: pytest.fail("Unbounded table read"))
    assert inspect_sources(mapping) == result(case)


def test_truncated_admins_do_not_prove_single_execution_or_censoring(case):
    second = dict(case[2], administration_id="toy-dose-1")
    mapping = write_sources(case, administrations=[case[2], second])
    mapping = replace(mapping, limits=replace(mapping.limits, max_rows_per_source=1, batch_rows=1))
    report = inspect_sources(mapping)
    assert report["status"] == "limited" and report["limits_reached"]["rows"]
    counts = report["counts"]
    assert counts["considered_administrations"] == counts["single_qualifying_orders"] == 1
    assert counts["accepted_execution_orders"] == counts["right_censored_orders"] == 0
    assert counts["unresolved_due_to_limits_orders"] == 1


def test_logical_row_limit_across_groups_and_key_limit(case):
    rows = [dict(case[2], administration_id=f"toy-dose-{i}") for i in range(20)]
    mapping = write_sources(case, administrations=rows)
    mapping = replace(mapping, limits=replace(mapping.limits, max_rows_per_source=7, batch_rows=4))
    report = inspect_sources(mapping)
    assert report["counts"]["considered_administrations"] == 7
    assert report["limits_reached"]["rows"]
    mapping = replace(mapping, limits=replace(mapping.limits, max_keys=1))
    report = inspect_sources(mapping)
    assert report["limits_reached"]["keys"]
    assert report["counts"]["accepted_execution_orders"] == 0


@pytest.mark.parametrize(
    "bound", ["max_files_per_source", "max_directories_per_source", "max_entries_per_source"]
)
def test_filesystem_limits_mark_incomplete_coverage(case, bound, tmp_path):
    mapping = write_sources(case)
    source_path = Path(case[0]["administrations"]["path"])
    root = tmp_path / "many-files"
    for i in range(3):
        folder = root / str(i)
        folder.mkdir(parents=True)
        (folder / "shard.parquet").write_bytes(source_path.read_bytes())
    mapping = replace(
        mapping,
        administrations=replace(mapping.administrations, path=root),
        limits=replace(mapping.limits, **{bound: 1}),
    )
    report = inspect_sources(mapping)
    assert report["status"] == "limited"
    assert report["limits_reached"][
        {
            "max_files_per_source": "files",
            "max_directories_per_source": "directories",
            "max_entries_per_source": "entries",
        }[bound]
    ]
    assert report["counts"]["accepted_execution_orders"] == 0


def test_empty_source_and_symlinks_never_imply_complete_followup(case, tmp_path):
    mapping = write_sources(case)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FeasibilityError, match="empty_source"):
        inspect_sources(
            replace(mapping, administrations=replace(mapping.administrations, path=empty))
        )
    (empty / "link.parquet").symlink_to(mapping.administrations.path)
    with pytest.raises(FeasibilityError, match="symlink_source"):
        inspect_sources(
            replace(mapping, administrations=replace(mapping.administrations, path=empty))
        )


def test_runtime_budget_check(case):
    mapping = parse_mapping(case[0])
    with pytest.raises(FeasibilityError, match="runtime_limit"):
        analyze([case[1]], [case[2]], mapping, Budget(mapping, started=0))


def test_plan_never_reads_sources_or_creates_output(case, tmp_path, monkeypatch, capsys):
    path = tmp_path / "feasibility.local.yaml"
    path.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setattr(os, "scandir", lambda *a: pytest.fail("Planning traversed data"))
    monkeypatch.setattr(pq, "ParquetFile", lambda *a, **k: pytest.fail("Planning read data"))
    assert main(["feasibility", "plan", "--mapping", str(path)]) == 0
    output = capsys.readouterr().out
    assert "toy_" not in output and "toy-" not in output and str(tmp_path) not in output
    assert not (tmp_path / "inputs").exists()


def test_sanitized_config_and_context_errors(case, tmp_path, monkeypatch, capsys):
    path = tmp_path / "feasibility.local.yaml"
    path.write_text("private-sentinel: [broken")
    with pytest.raises(SystemExit) as failure:
        main(["feasibility", "plan", "--mapping", str(path)])
    assert failure.value.code == 2
    path.write_text(yaml.safe_dump(case[0]))
    monkeypatch.delenv("IES_EXECUTION_CONTEXT", raising=False)
    with pytest.raises(SystemExit):
        main(["feasibility", "run", "--mapping", str(path), "--output-dir", str(tmp_path / "out")])
    output = capsys.readouterr()
    assert "private-sentinel" not in output.err and str(tmp_path) not in output.err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "returncode,limit", [(70, None), (71, "runtime"), (72, "memory"), (-signal.SIGXCPU, "cpu")]
)
def test_worker_failures_are_sanitized_aggregate_reports(
    case, tmp_path, monkeypatch, returncode, limit
):
    config = tmp_path / "mapping.local.yaml"
    config.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=returncode))
    output = tmp_path / "output"
    summary = runner.run_feasibility(config, output)
    report = json.loads((output / "feasibility_report.json").read_text())
    assert report["counts"] is None
    assert summary["status"] == ("limited" if limit else "failed")
    if limit:
        assert report["limits_reached"][limit]
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output / "feasibility_report.json").stat().st_mode & 0o777 == 0o600


def test_parent_kills_worker_on_runtime_timeout(case, tmp_path, monkeypatch):
    config = tmp_path / "mapping.local.yaml"
    config.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == case[0]["limits"]["runtime_seconds"]
        raise subprocess.TimeoutExpired("private-sentinel", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    runner.run_feasibility(config, tmp_path / "out")
    report = json.loads((tmp_path / "out/feasibility_report.json").read_text())
    assert report["limits_reached"]["runtime"] and report["counts"] is None


def test_mapping_changes_after_submission_fail_before_data_access(case, tmp_path, monkeypatch):
    config = tmp_path / "mapping.local.yaml"
    config.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)
    monkeypatch.setenv("IES_MAPPING_SHA256", "0" * 64)
    with pytest.raises(FeasibilityError, match="mapping_changed"):
        runner.run_feasibility(config, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_output_cannot_be_written_inside_source_tree(case, tmp_path, monkeypatch):
    config = tmp_path / "mapping.local.yaml"
    config.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)
    with pytest.raises(FeasibilityError, match="output_boundary"):
        runner.run_feasibility(config, ROOT / "artifacts/forbidden-feasibility")


def test_linux_worker_limits_include_core_dump_cpu_memory_and_affinity(case, monkeypatch):
    calls = {}
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(worker.resource, "setrlimit", lambda key, value: calls.update({key: value}))
    monkeypatch.setattr(os, "sched_getaffinity", lambda pid: {2, 3}, raising=False)
    monkeypatch.setattr(
        os, "sched_setaffinity", lambda pid, cpus: calls.update(affinity=cpus), raising=False
    )
    worker.apply_limits(parse_mapping(case[0]).limits)
    assert calls[worker.resource.RLIMIT_CORE] == (0, 0)
    assert calls[worker.resource.RLIMIT_AS] == (2048 * 1024**2,) * 2
    assert calls[worker.resource.RLIMIT_CPU] == (60, 61)
    assert calls["affinity"] == {2}


def test_local_mapping_ignored_and_disallowed_for_publication():
    boundary = load_script("check_repository")
    assert not boundary.allowed("configs/feasibility.local.yaml")
    assert boundary.allowed("configs/feasibility.example.yaml")
    completed = subprocess.run(
        ["git", "check-ignore", "configs/feasibility.local.yaml"], cwd=ROOT, capture_output=True
    )
    assert completed.returncode == 0


def test_slurm_feasibility_plan_uses_limits_without_data_access(
    case, tmp_path, monkeypatch, capsys
):
    server = load_script("server")
    config_path = tmp_path / "remote.local.yaml"
    config = yaml.safe_load((ROOT / "configs/remote.example.yaml").read_text())
    config.update(
        institutional_access_confirmed=True,
        data_root=str(tmp_path / "inputs"),
        output_root=str(tmp_path / "outputs"),
        python_executable=sys.executable,
    )
    config["slurm"]["partition"] = "toy-cpu"
    config_path.write_text(yaml.safe_dump(config))
    mapping_path = tmp_path / "feasibility.local.yaml"
    mapping_path.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setenv("IES_EXECUTION_CONTEXT", "ucsf")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "server.py",
            "plan",
            "feasibility",
            "--config",
            str(config_path),
            "--mapping",
            str(mapping_path),
        ],
    )
    assert server.main() == 0
    assert not (tmp_path / "inputs").exists() and not (tmp_path / "outputs").exists()
    assert "toy-cpu" not in capsys.readouterr().out
    command = server.sbatch_command(config, "feasibility", tmp_path / "outputs", mapping_path)
    assert "--cpus-per-task=1" in command and "--mem=2048M" in command
    assert "--time=00:01:30" in command
    assert not any("gpu" in item or "gres" in item for item in command)


def test_slurm_submit_pins_source_and_mapping_without_logging_private_arguments(
    case, tmp_path, monkeypatch, capsys
):
    server = load_script("server")
    (tmp_path / "inputs").mkdir()
    remote = yaml.safe_load((ROOT / "configs/remote.example.yaml").read_text())
    remote.update(
        institutional_access_confirmed=True,
        data_root=str(tmp_path / "inputs"),
        output_root=str(tmp_path / "outputs"),
        python_executable=sys.executable,
    )
    remote["slurm"]["partition"] = "toy-cpu"
    remote_path = tmp_path / "remote.local.yaml"
    remote_path.write_text(yaml.safe_dump(remote))
    mapping_path = tmp_path / "mapping.local.yaml"
    mapping_path.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setenv("IES_EXECUTION_CONTEXT", "ucsf")
    revision = "a" * 40
    monkeypatch.setattr(server, "source_revision", lambda: revision)
    commands = []

    def submitted(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="12345\n")

    monkeypatch.setattr(server.subprocess, "run", submitted)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "server.py",
            "submit",
            "feasibility",
            "--config",
            str(remote_path),
            "--mapping",
            str(mapping_path),
        ],
    )
    assert server.main() == 0
    export = next(arg for arg in commands[0] if arg.startswith("--export="))
    assert f"IES_EXPECTED_COMMIT={revision}" in export
    assert hashlib.sha256(mapping_path.read_bytes()).hexdigest() in export
    submission = next((tmp_path / "outputs").glob("jobs/*/submission.json"))
    assert json.loads(submission.read_text()) == {
        "job_id": "12345",
        "job": "feasibility",
        "commit": revision,
    }
    console = capsys.readouterr().out
    assert str(tmp_path) not in console and "toy-dose" not in console
    assert not list((tmp_path / "outputs").rglob("*.parquet"))


@pytest.mark.skipif(sys.platform != "linux", reason="Production resource caps require Linux")
def test_real_linux_worker_on_generated_parquet(case, tmp_path):
    write_sources(case)
    path = tmp_path / "mapping.local.yaml"
    path.write_text(yaml.safe_dump(case[0]))
    output = tmp_path / "report.json"
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ies.feasibility.worker",
            str(path),
            str(output),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ],
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, "Resource-constrained synthetic worker failed"
    assert completed.stdout == completed.stderr == b""
    assert json.loads(output.read_text())["counts"]["accepted_execution_orders"] == 1
    bad = dict(case[0])
    bad["orders"]["columns"]["order_id"] = "toy-private-error-sentinel"
    path.write_text(yaml.safe_dump(bad))
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ies.feasibility.worker",
            str(path),
            str(output),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ],
        env=env,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 70
    assert completed.stdout == completed.stderr == b""
