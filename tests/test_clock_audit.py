"""Generated-only tests of the private, outcome-free training-clock audit."""

import json
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import load_script

from ies import clinical_baseline, clock_audit, clock_audit_runner
from ies.cli import main
from ies.clinical_baseline import ClinicalBaselineError
from ies.cohort_readiness.extract import SCHEMA
from ies.dual_clock_history import HISTORY_SCHEMA
from ies.io import sha256, write_json


def _refresh(directory, filename):
    path = directory / "manifest.json"
    value = json.loads(path.read_text())
    value["artifacts_sha256"][filename] = sha256(directory / filename)
    write_json(path, value)
    return sha256(path)


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    cohort, history = tmp_path / "cohort", tmp_path / "history"
    cohort.mkdir()
    history.mkdir()
    rows = [
        dict(
            patient_id=f"toy-p-{i}",
            order_id=f"toy-o-{i}",
            encounter_id=f"toy-e-{i}",
            split=split,
            index_time_hours=100.0,
            duration_hours=float("nan"),
            cause=-99,
            outcome="not-read",
        )
        for i, split in enumerate(["train", "train", "train", "validation", "test"])
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), cohort / "cohort.parquet")
    write_json(
        cohort / "manifest.json",
        {
            "mode": "bounded_phase0_cohort_extraction",
            "status": "complete",
            "data_class": "restricted_clinical",
            "bounded_domain": True,
            "mapping_sha256": "a" * 64,
            "artifacts_sha256": {"cohort.parquet": sha256(cohort / "cohort.parquet")},
        },
    )
    history_rows = []
    for i, available in [
        (0, [3.0, 1.0]),
        (1, [8.0, 4.0]),
        (3, [float("nan"), float("nan")]),
        (4, [float("nan"), float("nan")]),
    ]:
        for j, (occurred, known) in enumerate(zip([8.0, 4.0], available, strict=True)):
            history_rows.append(
                dict(
                    patient_id=f"toy-p-{i}",
                    index_order_id=f"toy-o-{i}",
                    event_id=f"toy-event-{i}-{j}",
                    event_kind=0,
                    occurrence_lag_hours=occurred,
                    availability_lag_hours=known,
                    documentation_delay_hours=occurred - known,
                )
            )
    pq.write_table(
        pa.Table.from_pylist(history_rows, schema=HISTORY_SCHEMA), history / "history.parquet"
    )
    write_json(
        history / "qc_report.json",
        {
            "status": "complete",
            "complete_full_source_scan": True,
            "source_stable": True,
            "outcome_features_used": False,
        },
    )
    write_json(
        history / "manifest.json",
        {
            "mode": "dual_clock_history_extraction",
            "status": "complete",
            "data_class": "restricted_clinical",
            "cohort_manifest_sha256": sha256(cohort / "manifest.json"),
            "mapping_sha256": "a" * 64,
            "lookback_hours": 24,
            "max_events_per_order": 24,
            "sequence_truncation_rule": "most_recent_occurrence_then_availability",
            "availability_masked": True,
            "outcome_features_used": False,
            "artifacts_sha256": {
                name: sha256(history / name) for name in ("history.parquet", "qc_report.json")
            },
        },
    )
    return cohort, history


def _run(artifacts, output):
    cohort, history = artifacts
    output.mkdir()
    return clock_audit.audit_training_clocks(
        cohort,
        history,
        output,
        sha256(cohort / "manifest.json"),
        sha256(history / "manifest.json"),
        "b" * 40,
    )


def test_audit_materializes_only_train_features_never_labels(artifacts, tmp_path, monkeypatch):
    original = pq.read_table
    calls = []

    def read(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(clock_audit.pq, "read_table", read)
    output = tmp_path / "report"
    manifest = _run(artifacts, output)
    assert calls[0]["columns"] == ["patient_id", "order_id", "split"]
    assert calls[1]["filters"] == [("index_order_id", "in", ["toy-o-0", "toy-o-1", "toy-o-2"])]
    report = json.loads((output / "clock_report.json").read_text())
    assert report["training_orders"] == 3 and report["training_orders_without_history"] == 1
    assert report["counts_by_event_kind"]["0"] == dict(
        relationships=4,
        equal_clock_relationships=2,
        positive_delay_relationships=2,
        orders_with_history=2,
        orders_with_multiple_events=2,
        orders_with_valid_pair_swap=1,
    )
    assert report["clinical_advancement_decision"] == "not_applicable"
    assert not report["outcome_columns_read"] and not report["clinical_test_evaluated"]
    for path in output.iterdir():
        assert path.stat().st_mode & 0o077 == 0
        assert "toy-" not in path.read_text()
    assert manifest["artifacts_sha256"]["clock_report.json"] == sha256(output / "clock_report.json")
    with pytest.raises(ClinicalBaselineError, match="invalid_clock_audit_output"):
        clock_audit.audit_training_clocks(*artifacts, output, "a" * 64, "b" * 64, "b" * 40)


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("patient", "history_alignment"),
        ("delay", "invalid_time_pair"),
        ("future", "invalid_time_pair"),
        ("duplicate", "duplicate_history"),
        ("cap", "sequence_cap_exceeded"),
    ],
)
def test_invalid_training_histories_fail_explicitly(artifacts, tmp_path, mutation, code):
    _, history = artifacts
    rows = pq.read_table(history / "history.parquet").to_pylist()
    if mutation == "patient":
        rows[0]["patient_id"] = "different-toy-patient"
    elif mutation == "delay":
        rows[0]["documentation_delay_hours"] = 100.0
    elif mutation == "future":
        rows[0]["availability_lag_hours"] = -1.0
    elif mutation == "duplicate":
        rows.append(rows[0])
    else:
        rows.extend(dict(rows[0], event_id=f"extra-{i}") for i in range(25))
    pq.write_table(pa.Table.from_pylist(rows, schema=HISTORY_SCHEMA), history / "history.parquet")
    _refresh(history, "history.parquet")
    with pytest.raises(ClinicalBaselineError, match=code):
        _run(artifacts, tmp_path / "failed")


def test_cross_split_patients_reject_without_reading_history(artifacts, tmp_path):
    cohort, history = artifacts
    rows = pq.read_table(cohort / "cohort.parquet").to_pylist()
    rows[-1]["patient_id"] = rows[0]["patient_id"]
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), cohort / "cohort.parquet")
    digest = _refresh(cohort, "cohort.parquet")
    manifest = json.loads((history / "manifest.json").read_text())
    manifest["cohort_manifest_sha256"] = digest
    write_json(history / "manifest.json", manifest)
    with pytest.raises(ClinicalBaselineError, match="patient_overlap"):
        _run(artifacts, tmp_path / "failed")


def test_input_change_during_read_is_detected_before_report(artifacts, tmp_path, monkeypatch):
    _, history = artifacts
    original = pq.read_table

    def read(path, **kwargs):
        result = original(path, **kwargs)
        if path == history / "history.parquet":
            write_json(history / "qc_report.json", {"changed": True})
        return result

    monkeypatch.setattr(clock_audit.pq, "read_table", read)
    output = tmp_path / "failed"
    with pytest.raises(ClinicalBaselineError, match="artifact_changed"):
        _run(artifacts, output)
    assert not (output / "manifest.json").exists()


@pytest.mark.parametrize(
    "mutation", ["checksum", "cohort_binding", "coverage", "row_limit", "symlink"]
)
def test_integrity_coverage_bounds_and_symlinks_fail(artifacts, tmp_path, monkeypatch, mutation):
    _, history = artifacts
    manifest = json.loads((history / "manifest.json").read_text())
    if mutation == "checksum":
        manifest["artifacts_sha256"]["history.parquet"] = "0" * 64
    elif mutation == "cohort_binding":
        manifest["cohort_manifest_sha256"] = "0" * 64
    elif mutation == "coverage":
        qc = json.loads((history / "qc_report.json").read_text())
        qc["complete_full_source_scan"] = False
        write_json(history / "qc_report.json", qc)
        manifest["artifacts_sha256"]["qc_report.json"] = sha256(history / "qc_report.json")
    elif mutation == "row_limit":
        monkeypatch.setattr(clock_audit, "MAX_HISTORY_ROWS", 1)
    else:
        target = tmp_path / "outside.parquet"
        (history / "history.parquet").rename(target)
        (history / "history.parquet").symlink_to(target)
    write_json(history / "manifest.json", manifest)
    with pytest.raises(ClinicalBaselineError):
        _run(artifacts, tmp_path / "failed")


def test_server_submission_binds_artifacts_and_exact_resources(artifacts, tmp_path):
    server = load_script("server")
    cohort, history = artifacts
    config = {
        "python_executable": "/server/python",
        "output_root": str(tmp_path),
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 4,
            "memory": "8G",
            "time_limit": "00:20:00",
        },
    }
    command = server.sbatch_command(
        config, "clock-audit", tmp_path / "job", cohort_dir=cohort, history_dir=history
    )
    export = next(arg for arg in command if arg.startswith("--export="))
    assert f"IES_COHORT_MANIFEST_SHA256={sha256(cohort / 'manifest.json')}" in export
    assert f"IES_HISTORY_MANIFEST_SHA256={sha256(history / 'manifest.json')}" in export
    assert (
        "--cpus-per-task=2" in command and "--mem=4096M" in command and "--time=00:05:30" in command
    )
    assert str(server.ROOT / "slurm/clock_audit.sbatch") in command
    with pytest.raises(ValueError, match="mappings"):
        server.sbatch_command(
            config,
            "clock-audit",
            tmp_path / "job",
            cohort_dir=cohort,
            history_dir=history,
            mapping_path=Path("forbidden"),
        )


@pytest.mark.parametrize("failure", [70, 72, "timeout"])
def test_runner_propagates_failures_without_private_payload(
    artifacts, tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(clock_audit_runner, "verify_execution_context", lambda: None)

    def execute(*args, **kwargs):
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        if failure == "timeout":
            raise subprocess.TimeoutExpired("private-payload", 300)
        return subprocess.CompletedProcess(args, failure)

    monkeypatch.setattr(clock_audit_runner.subprocess, "run", execute)
    result = clock_audit_runner.run_clock_audit(*artifacts, tmp_path / "job")
    assert result == {"mode": clock_audit.MODE, "status": "failed" if failure == 70 else "limited"}
    assert "private-payload" not in (tmp_path / "job/failure.json").read_text()
    assert (tmp_path / "job").stat().st_mode & 0o077 == 0


def test_cli_rejects_local_execution_with_sanitized_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("IES_EXECUTION_CONTEXT", raising=False)
    with pytest.raises(SystemExit) as error:
        main(
            [
                "clock-audit",
                "run",
                "--cohort-dir",
                str(tmp_path / "sensitive"),
                "--history-dir",
                str(tmp_path / "history"),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
    assert error.value.code == 2
    assert "sensitive" not in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_runner_completes_with_only_operational_status(artifacts, tmp_path, monkeypatch):
    monkeypatch.setattr(clock_audit_runner, "verify_execution_context", lambda: None)
    cohort, history = artifacts
    monkeypatch.setenv("IES_COHORT_MANIFEST_SHA256", sha256(cohort / "manifest.json"))
    monkeypatch.setenv("IES_HISTORY_MANIFEST_SHA256", sha256(history / "manifest.json"))
    monkeypatch.setenv("IES_EXPECTED_COMMIT", "b" * 40)

    def execute(command, **kwargs):
        clock_audit.audit_training_clocks(*map(Path, command[3:6]), *command[6:9])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(clock_audit_runner.subprocess, "run", execute)
    assert clock_audit_runner.run_clock_audit(cohort, history, tmp_path / "job") == {
        "mode": clock_audit.MODE,
        "status": "complete",
    }
