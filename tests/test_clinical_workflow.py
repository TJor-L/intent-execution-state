"""Generated artifact, no-held-out-label and bounded server entry tests for W001."""

import json
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from conftest import load_script

from ies import clinical_baseline, workflow_artifacts, workflow_runner
from ies.cli import main
from ies.clinical_baseline import ClinicalBaselineError
from ies.clinical_workflow import run_clinical_workflow
from ies.clock_audit_ops import ClockAuditOpsError, wait_for_workflow_cv
from ies.cohort_readiness.extract import SCHEMA
from ies.dual_clock_history import HISTORY_SCHEMA
from ies.io import sha256, write_json
from ies.workflow_cv import MODE, load_workflow_config
from ies.workflow_diagnostic import generate_workflow_case

ROOT = Path(__file__).resolve().parents[1]


def _refresh(directory, name):
    path = directory / "manifest.json"
    value = json.loads(path.read_text())
    value["artifacts_sha256"][name] = sha256(directory / name)
    write_json(path, value)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    cohort_dir, history_dir = tmp_path / "cohort", tmp_path / "history"
    cohort_dir.mkdir()
    history_dir.mkdir()
    cohort, grouped = generate_workflow_case(31, "type_timing_signal", patients=60)
    cohort += [
        dict(order_id=split, patient_id=split, split=split, duration=float("nan"), cause=-99)
        for split in ("validation", "test")
    ]
    cohort_rows, history_rows = [], []
    for row in cohort:
        cohort_rows.append(
            dict(
                patient_id=row["patient_id"],
                order_id=row["order_id"],
                encounter_id="generated-encounter",
                split=row["split"],
                index_time_hours=100.0,
                duration_hours=row["duration"],
                cause=row["cause"],
                outcome="not-projected",
            )
        )
        events = grouped.get(
            row["order_id"],
            [
                dict(
                    event_kind=0,
                    occurrence_lag_hours=float("nan"),
                    availability_lag_hours=float("nan"),
                )
            ],
        )
        for index, event in enumerate(events):
            history_rows.append(
                dict(
                    patient_id=row["patient_id"],
                    index_order_id=row["order_id"],
                    event_id=f"generated-event-{index}",
                    **event,
                    documentation_delay_hours=event["occurrence_lag_hours"]
                    - event["availability_lag_hours"],
                )
            )
    pq.write_table(pa.Table.from_pylist(cohort_rows, schema=SCHEMA), cohort_dir / "cohort.parquet")
    pq.write_table(
        pa.Table.from_pylist(history_rows, schema=HISTORY_SCHEMA), history_dir / "history.parquet"
    )
    write_json(
        cohort_dir / "manifest.json",
        dict(
            status="complete",
            data_class="restricted_clinical",
            mode="bounded_phase0_cohort_extraction",
            bounded_domain=True,
            mapping_sha256="a" * 64,
            artifacts_sha256={"cohort.parquet": sha256(cohort_dir / "cohort.parquet")},
        ),
    )
    write_json(
        history_dir / "qc_report.json",
        dict(
            status="complete",
            complete_full_source_scan=True,
            source_stable=True,
            outcome_features_used=False,
        ),
    )
    write_json(
        history_dir / "manifest.json",
        dict(
            status="complete",
            data_class="restricted_clinical",
            mode="dual_clock_history_extraction",
            cohort_manifest_sha256=sha256(cohort_dir / "manifest.json"),
            mapping_sha256="a" * 64,
            lookback_hours=24,
            max_events_per_order=24,
            sequence_truncation_rule="most_recent_occurrence_then_availability",
            availability_masked=True,
            outcome_features_used=False,
            artifacts_sha256={
                n: sha256(history_dir / n) for n in ("history.parquet", "qc_report.json")
            },
        ),
    )
    config, _ = load_workflow_config(ROOT / "configs/workflow_cv.yaml")
    config["bootstrap_replicates"] = 20
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    return cohort_dir, history_dir, config_path


def _read(inputs):
    cohort, history, _ = inputs
    return workflow_artifacts.load_workflow_training(
        cohort, history, sha256(cohort / "manifest.json"), sha256(history / "manifest.json")
    )


def _run(inputs, output):
    output.mkdir()
    cohort, history, config = inputs
    return run_clinical_workflow(
        cohort,
        history,
        config,
        output,
        sha256(cohort / "manifest.json"),
        sha256(history / "manifest.json"),
        sha256(config),
        "b" * 40,
    )


def test_reader_projects_only_training_labels_and_history(inputs, monkeypatch):
    original = pq.read_table
    calls = []

    def read(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(workflow_artifacts.pq, "read_table", read)
    cohort, grouped, _ = _read(inputs)
    assert {r["split"] for r in cohort} == {"train"}
    assert calls[0] == dict(columns=["patient_id", "order_id", "split"])
    assert calls[1] == dict(
        columns=["patient_id", "order_id", "duration_hours", "cause"],
        filters=[("split", "==", "train")],
    )
    assert calls[2]["filters"][0][:2] == ("index_order_id", "in")
    assert set(calls[2]["filters"][0][2]) == set(grouped)
    assert "validation" not in grouped and "test" not in grouped


def test_private_cv_is_reproducible_held_out_agnostic_and_identifier_free(inputs, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    manifest = _run(inputs, first)
    assert manifest["mode"] == MODE and not manifest["validation_split_evaluated"]
    assert not manifest["test_split_evaluated"] and not manifest["prediction_rows_persisted"]
    cohort, history, _ = inputs
    rows = pq.read_table(cohort / "cohort.parquet").to_pylist()
    for row in rows:
        if row["split"] != "train":
            row.update(duration_hours=-500.0, cause=-50)
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), cohort / "cohort.parquet")
    _refresh(cohort, "cohort.parquet")
    binding = json.loads((history / "manifest.json").read_text())
    binding["cohort_manifest_sha256"] = sha256(cohort / "manifest.json")
    write_json(history / "manifest.json", binding)
    _run(inputs, second)
    for name in ("workflow_report.json", "models.json", "config.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert (first / name).stat().st_mode & 0o077 == 0
        assert "generated-patient-" not in (first / name).read_text()
        assert manifest["artifacts_sha256"][name] == sha256(first / name)


@pytest.mark.parametrize(
    "mutation",
    ["patient_overlap", "bad_label", "history_patient", "duplicate", "future", "cap", "incomplete"],
)
def test_invalid_training_artifacts_reject(inputs, mutation):
    cohort, history, _ = inputs
    if mutation in {"patient_overlap", "bad_label"}:
        rows = pq.read_table(cohort / "cohort.parquet").to_pylist()
        if mutation == "patient_overlap":
            rows[-1]["patient_id"] = rows[0]["patient_id"]
        else:
            rows[0]["cause"] = -99
        pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), cohort / "cohort.parquet")
        _refresh(cohort, "cohort.parquet")
        binding = json.loads((history / "manifest.json").read_text())
        binding["cohort_manifest_sha256"] = sha256(cohort / "manifest.json")
        write_json(history / "manifest.json", binding)
    elif mutation == "incomplete":
        value = json.loads((history / "qc_report.json").read_text())
        value["complete_full_source_scan"] = False
        write_json(history / "qc_report.json", value)
        _refresh(history, "qc_report.json")
    else:
        rows = pq.read_table(history / "history.parquet").to_pylist()
        if mutation == "history_patient":
            rows[0]["patient_id"] = "unrelated-generated-person"
        elif mutation == "duplicate":
            rows.append(dict(rows[0]))
        elif mutation == "future":
            rows[0]["availability_lag_hours"] = -1.0
        else:
            rows.extend(dict(rows[0], event_id=f"extra-{i}") for i in range(25))
        pq.write_table(
            pa.Table.from_pylist(rows, schema=HISTORY_SCHEMA), history / "history.parquet"
        )
        _refresh(history, "history.parquet")
    with pytest.raises(ClinicalBaselineError):
        _read(inputs)


def test_input_mutation_between_fit_and_write_cannot_publish_success(inputs, tmp_path, monkeypatch):
    import ies.clinical_workflow as clinical

    original = clinical.workflow_cross_validation

    def fit(*args, **kwargs):
        value = original(*args, **kwargs)
        (inputs[1] / "qc_report.json").write_text("{}")
        return value

    monkeypatch.setattr(clinical, "workflow_cross_validation", fit)
    output = tmp_path / "changed"
    with pytest.raises(ClinicalBaselineError, match="artifact_changed"):
        _run(inputs, output)
    assert not (output / "manifest.json").exists()


def test_server_workflow_job_binds_inputs_config_and_existing_cpu_budget(inputs, tmp_path):
    cohort, history, config = inputs
    server = load_script("server")
    settings = dict(
        python_executable="/generated/python",
        output_root=str(tmp_path),
        slurm=dict(partition="cpu", account=None, cpus=4, memory="8G", time_limit="00:20:00"),
    )
    command = server.sbatch_command(
        settings,
        "workflow-cv",
        tmp_path / "job",
        cohort_dir=cohort,
        history_dir=history,
        workflow_config=config,
    )
    assert "--cpus-per-task=2" in command and "--mem=4096M" in command
    assert "--time=00:20:30" in command
    export = next(s for s in command if s.startswith("--export="))
    assert f"IES_WORKFLOW_CONFIG_SHA256={sha256(config)}" in export
    assert f"IES_COHORT_MANIFEST_SHA256={sha256(cohort / 'manifest.json')}" in export
    assert f"IES_HISTORY_MANIFEST_SHA256={sha256(history / 'manifest.json')}" in export
    with pytest.raises(ValueError):
        server.sbatch_command(
            settings,
            "workflow-cv",
            tmp_path / "job",
            mapping_path=tmp_path,
            cohort_dir=cohort,
            history_dir=history,
            workflow_config=config,
        )


@pytest.mark.parametrize("result,status", [(70, "failed"), (72, "limited"), ("timeout", "limited")])
def test_runner_preserves_failure_and_resource_limits_without_private_output(
    inputs, tmp_path, monkeypatch, result, status
):
    cohort, history, config = inputs
    monkeypatch.setattr(workflow_runner, "verify_execution_context", lambda: None)
    monkeypatch.setenv("IES_COHORT_MANIFEST_SHA256", sha256(cohort / "manifest.json"))
    monkeypatch.setenv("IES_HISTORY_MANIFEST_SHA256", sha256(history / "manifest.json"))
    monkeypatch.setenv("IES_WORKFLOW_CONFIG_SHA256", sha256(config))
    monkeypatch.setenv("IES_EXPECTED_COMMIT", "b" * 40)

    def run(command, **kwargs):
        assert kwargs["timeout"] == 1200
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        if result == "timeout":
            raise subprocess.TimeoutExpired(command, 1200, output="private-generated-message")
        return subprocess.CompletedProcess(command, result)

    monkeypatch.setattr(workflow_runner.subprocess, "run", run)
    output = tmp_path / "run"
    assert workflow_runner.run_workflow(cohort, history, config, output) == dict(
        mode=MODE, status=status
    )
    assert output.stat().st_mode & 0o077 == 0
    assert "private-generated" not in (output / "failure.json").read_text()


def test_monitor_verifies_all_workflow_artifacts_and_refuses_held_out_evaluation(
    inputs, tmp_path, monkeypatch
):
    output = tmp_path / "job/workflow-cv"
    output.parent.mkdir()
    _run(inputs, output)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0, "99|COMPLETED|0:0\n", ""),
    )
    result = wait_for_workflow_cv("99", output.parent, "b" * 40)
    assert result == dict(mode=MODE, job_id="99", status="complete", private_review_required=True)
    (output / "models.json").write_text("{}")
    with pytest.raises(ClockAuditOpsError, match="workflow_cv_result_invalid"):
        wait_for_workflow_cv("99", output.parent, "b" * 40)


def test_workflow_cli_refuses_local_execution_before_reading_inputs(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(
            [
                "workflow-cv",
                "run",
                "--cohort-dir",
                str(tmp_path / "cohort"),
                "--history-dir",
                str(tmp_path / "history"),
                "--config",
                str(tmp_path / "config"),
                "--output-dir",
                str(tmp_path / "output"),
            ]
        )
    assert error.value.code == 2 and not (tmp_path / "output").exists()
    assert str(tmp_path) not in capsys.readouterr().err


@pytest.mark.parametrize("status,code", [("complete", 0), ("failed", 2), ("limited", 2)])
def test_workflow_cli_propagates_worker_status(status, code, monkeypatch, capsys):
    monkeypatch.setattr(
        workflow_runner, "run_workflow", lambda *args: dict(mode=MODE, status=status)
    )
    result = main(
        [
            "workflow-cv",
            "run",
            "--cohort-dir",
            "generated-cohort",
            "--history-dir",
            "generated-history",
            "--config",
            "generated-config",
            "--output-dir",
            "generated-output",
        ]
    )
    captured = capsys.readouterr()
    assert result == code
    assert json.loads(captured.out) == dict(mode=MODE, status=status)
    assert not captured.err


@pytest.mark.parametrize("exception", [ValueError, OSError, RuntimeError])
def test_workflow_cli_suppresses_private_exception_payload(exception, monkeypatch, capsys):
    def fail(*args):
        raise exception("generated-private-payload-must-not-appear")

    monkeypatch.setattr(workflow_runner, "run_workflow", fail)
    with pytest.raises(SystemExit) as error:
        main(
            [
                "workflow-cv",
                "run",
                "--cohort-dir",
                "generated-cohort",
                "--history-dir",
                "generated-history",
                "--config",
                "generated-config",
                "--output-dir",
                "generated-output",
            ]
        )
    captured = capsys.readouterr()
    assert error.value.code == 2
    assert not captured.out
    assert captured.err == "Workflow CV failed; inspect the private UCSF run directory.\n"


def test_runner_accepts_only_verified_success_and_returns_operational_status(
    inputs, tmp_path, monkeypatch
):
    cohort, history, config = inputs
    monkeypatch.setattr(workflow_runner, "verify_execution_context", lambda: None)
    monkeypatch.setenv("IES_COHORT_MANIFEST_SHA256", sha256(cohort / "manifest.json"))
    monkeypatch.setenv("IES_HISTORY_MANIFEST_SHA256", sha256(history / "manifest.json"))
    monkeypatch.setenv("IES_WORKFLOW_CONFIG_SHA256", sha256(config))
    monkeypatch.setenv("IES_EXPECTED_COMMIT", "b" * 40)

    def worker(command, **kwargs):
        # Generated worker stand-in uses the exact serialized production arguments.
        run_clinical_workflow(*map(Path, command[3:7]), *command[7:11])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(workflow_runner.subprocess, "run", worker)
    output = tmp_path / "success"
    assert workflow_runner.run_workflow(cohort, history, config, output) == dict(
        mode=MODE, status="complete"
    )
    assert output.stat().st_mode & 0o077 == 0
    monkeypatch.setenv("IES_WORKFLOW_CONFIG_SHA256", "c" * 64)
    with pytest.raises(ClinicalBaselineError, match="inputs_changed"):
        workflow_runner.run_workflow(cohort, history, config, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_server_workflow_plan_submit_and_monitor_emit_no_private_details(
    inputs, tmp_path, monkeypatch, capsys
):
    server = load_script("server")
    cohort, history, config = inputs
    settings = dict(
        output_root=str(tmp_path),
        python_executable="/generated/python",
        slurm=dict(partition="cpu", account=None, cpus=2, memory="4G", time_limit="00:20:00"),
    )
    monkeypatch.setattr(server, "load_server_config", lambda *a, **kw: settings)
    monkeypatch.setattr(server, "discover_clock_artifacts", lambda root: (cohort, history))
    monkeypatch.setattr(server, "source_revision", lambda: "b" * 40)

    def forbidden(*args, **kwargs):
        pytest.fail("Planning cannot submit a job")

    monkeypatch.setattr(server.subprocess, "run", forbidden)
    monkeypatch.setattr(
        "sys.argv",
        ["server.py", "plan", "workflow-cv", "--auto-artifacts", "--workflow-config", str(config)],
    )
    assert server.main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == MODE and not plan["submitted"]
    assert not plan["validation_split_evaluated"] and not plan["test_split_evaluated"]

    def submit(command, **kwargs):
        assert command[0] == "sbatch"
        assert any("IES_EXPECTED_COMMIT=" + "b" * 40 in arg for arg in command)
        assert str(server.ROOT / "slurm/workflow_cv.sbatch") in command
        return subprocess.CompletedProcess(command, 0, "99\n", "")

    def monitor(job, directory, commit):
        receipt = json.loads((directory / "submission.json").read_text())
        assert receipt == dict(job_id="99", job="workflow-cv", commit="b" * 40)
        return dict(mode=MODE, job_id=job, status="complete", private_review_required=True)

    monkeypatch.setattr(server.subprocess, "run", submit)
    monkeypatch.setattr(server, "wait_for_workflow_cv", monitor)
    monkeypatch.setattr(
        "sys.argv",
        [
            "server.py",
            "submit",
            "workflow-cv",
            "--auto-artifacts",
            "--workflow-config",
            str(config),
            "--wait",
        ],
    )
    assert server.main() == 0
    stdout = capsys.readouterr().out
    assert str(tmp_path) not in stdout
    assert [json.loads(line).get("submitted", False) for line in stdout.splitlines()] == [
        True,
        False,
    ]
