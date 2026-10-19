"""Generated private-artifact replay, Slurm binding and no-refit output boundaries."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import load_script
from test_clinical_workflow import _run
from test_clinical_workflow import inputs as inputs

from ies import clinical_workflow_diagnostics as clinical
from ies import workflow_diagnostics_runner as runner
from ies.cli import main
from ies.clock_audit_ops import wait_for_workflow_diagnostics
from ies.io import sha256, write_json
from ies.workflow_diagnostics import MODE, summarize_diagnostics


@pytest.fixture
def frozen(inputs, tmp_path):
    workflow = tmp_path / "jobs" / "generated-original" / "workflow-cv"
    workflow.parent.mkdir(parents=True)
    _run(inputs, workflow)
    write_json(
        workflow.parent / "submission.json", dict(job_id="71", job="workflow-cv", commit="b" * 40)
    )
    return (*inputs, workflow)


def run(frozen, output):
    cohort, history, config, workflow = frozen
    output.mkdir()
    return clinical.run_clinical_diagnostics(
        cohort,
        history,
        config,
        workflow,
        output,
        sha256(cohort / "manifest.json"),
        sha256(history / "manifest.json"),
        sha256(config),
        sha256(workflow / "manifest.json"),
        "c" * 40,
        "b" * 40,
    )


def test_private_diagnostics_verify_replay_without_rows_or_refit(frozen, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Frozen clinical diagnostics must not fit")

    monkeypatch.setattr("ies.workflow_cv.fit_history_model", forbidden)
    monkeypatch.setattr("ies.models.history_piecewise.fit_history_model", forbidden)
    before = {
        p: p.read_bytes()
        for directory in [frozen[0], frozen[1], frozen[3]]
        for p in directory.iterdir()
    }
    output = tmp_path / "diagnostics"
    manifest = run(frozen, output)
    assert manifest["source_replay_verified"] is True and manifest["model_fitted"] is False
    assert manifest["original_workflow_commit"] == "b" * 40
    assert not manifest["validation_split_evaluated"] and not manifest["test_split_evaluated"]
    assert {p.name for p in output.iterdir()} == {"diagnostic_report.json", "manifest.json"}
    for p in output.iterdir():
        assert p.stat().st_mode & 0o077 == 0
        text = p.read_text()
        assert "generated-patient-" not in text and "generated-order-" not in text
    assert all(p.read_bytes() == content for p, content in before.items())
    report = json.loads((output / "diagnostic_report.json").read_bytes())
    summary = summarize_diagnostics(report)
    assert "pooled_minus_intercept" in summary["nll_comparisons"]
    assert len(summary["execution_probability_diagnostics"]) == 4
    assert "calibration_bins" not in json.dumps(summary)
    assert "unknown_outcomes" not in json.dumps(summary)


@pytest.mark.parametrize(
    "key", ["cohort_manifest_sha256", "history_manifest_sha256", "config_sha256", "source_commit"]
)
def test_original_manifest_binding_is_required(frozen, tmp_path, key):
    path = frozen[3] / "manifest.json"
    value = json.loads(path.read_bytes())
    value[key] = "d" * (40 if key == "source_commit" else 64)
    write_json(path, value)
    with pytest.raises(ValueError):
        run(frozen, tmp_path / "rejected")
    assert not (tmp_path / "rejected" / "manifest.json").exists()


def test_mid_replay_model_mutation_prevents_complete_manifest(frozen, tmp_path, monkeypatch):
    original = clinical.replay_diagnostics

    def mutate(*args, **kwargs):
        report = original(*args, **kwargs)
        (frozen[3] / "models.json").write_text("{}")
        return report

    monkeypatch.setattr(clinical, "replay_diagnostics", mutate)
    with pytest.raises(ValueError):
        run(frozen, tmp_path / "rejected")
    assert not (tmp_path / "rejected" / "manifest.json").exists()


def set_runner_environment(frozen, monkeypatch):
    cohort, history, config, workflow = frozen
    for name, value in {
        "IES_COHORT_MANIFEST_SHA256": sha256(cohort / "manifest.json"),
        "IES_HISTORY_MANIFEST_SHA256": sha256(history / "manifest.json"),
        "IES_WORKFLOW_MANIFEST_SHA256": sha256(workflow / "manifest.json"),
        "IES_WORKFLOW_CONFIG_SHA256": sha256(config),
        "IES_EXPECTED_COMMIT": "c" * 40,
        "IES_ORIGINAL_WORKFLOW_COMMIT": "b" * 40,
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)


def test_runner_worker_arguments_and_monitor_return_only_qualitative_feedback(
    frozen, tmp_path, monkeypatch
):
    set_runner_environment(frozen, monkeypatch)

    def worker(command, **kwargs):
        assert (
            kwargs["timeout"] == 300
            and kwargs["stdout"] is subprocess.DEVNULL
            and kwargs["stderr"] is subprocess.DEVNULL
        )
        clinical.run_clinical_diagnostics(*map(Path, command[3:8]), *command[8:14])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", worker)
    output = tmp_path / "generated-job" / "workflow-diagnostics"
    output.parent.mkdir()
    cohort, history, config, workflow = frozen
    assert runner.run_diagnostics(cohort, history, config, workflow, output) == dict(
        mode=MODE, status="complete"
    )
    assert output.stat().st_mode & 0o077 == 0
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess([], 0, "72|COMPLETED|0:0\n", ""),
    )
    result = wait_for_workflow_diagnostics("72", output.parent, "c" * 40)
    assert result["status"] == "complete" and "diagnostics" in result
    assert str(tmp_path) not in json.dumps(result)
    assert "mean_difference" not in json.dumps(result)


@pytest.mark.parametrize("result,status", [(70, "failed"), (72, "limited"), ("timeout", "limited")])
def test_runner_limits_and_error_payload_suppression(frozen, tmp_path, monkeypatch, result, status):
    set_runner_environment(frozen, monkeypatch)

    def worker(command, **kwargs):
        if result == "timeout":
            raise subprocess.TimeoutExpired(command, 300, output="generated-private-payload")
        return subprocess.CompletedProcess(command, result)

    monkeypatch.setattr(runner.subprocess, "run", worker)
    cohort, history, config, workflow = frozen
    output = tmp_path / "failed"
    assert runner.run_diagnostics(cohort, history, config, workflow, output)["status"] == status
    assert "generated-private" not in (output / "failure.json").read_text()


def test_diagnostic_sbatch_binds_original_artifacts_and_preserves_bounds(frozen, tmp_path):
    server = load_script("server")
    cohort, history, config, workflow = frozen
    settings = dict(
        output_root=str(tmp_path),
        python_executable="/generated/python",
        slurm=dict(partition="cpu", account=None, cpus=2, memory="4G", time_limit="00:20:00"),
    )
    command = server.sbatch_command(
        settings,
        "workflow-diagnostics",
        tmp_path / "new-job",
        cohort_dir=cohort,
        history_dir=history,
        workflow_config=config,
        workflow_dir=workflow,
        original_commit="b" * 40,
    )
    assert (
        "--time=00:05:30" in command and "--mem=4096M" in command and "--cpus-per-task=2" in command
    )
    exports = next(x for x in command if x.startswith("--export="))
    assert "IES_WORKFLOW_MANIFEST_SHA256=" + sha256(workflow / "manifest.json") in exports
    assert "IES_ORIGINAL_WORKFLOW_COMMIT=" + "b" * 40 in exports
    assert command[-6:] == [
        "/generated/python",
        str(cohort),
        str(history),
        str(config),
        str(workflow),
        str(tmp_path / "new-job" / "workflow-diagnostics"),
    ]
    with pytest.raises(ValueError):
        server.sbatch_command(
            settings,
            "workflow-diagnostics",
            tmp_path / "new-job",
            cohort_dir=cohort,
            history_dir=history,
            workflow_config=config,
            workflow_dir=workflow,
            original_commit="d" * 40,
        )


def test_server_plan_submit_monitor_uses_original_job_and_sanitized_receipt(
    frozen, tmp_path, monkeypatch, capsys
):
    server = load_script("server")
    cohort, history, config, _ = frozen
    settings = dict(
        output_root=str(tmp_path),
        python_executable="/generated/python",
        slurm=dict(partition="cpu", account=None, cpus=2, memory="4G", time_limit="00:20:00"),
    )
    monkeypatch.setattr(server, "load_server_config", lambda *a, **kw: settings)
    monkeypatch.setattr(server, "discover_clock_artifacts", lambda root: (cohort, history))
    monkeypatch.setattr(server, "source_revision", lambda: "c" * 40)
    options = [
        "workflow-diagnostics",
        "--auto-artifacts",
        "--workflow-config",
        str(config),
        "--job-id",
        "71",
        "--source-commit",
        "b" * 40,
    ]

    def forbidden(*args, **kwargs):
        pytest.fail("Planning cannot submit a job")

    monkeypatch.setattr(server.subprocess, "run", forbidden)
    monkeypatch.setattr("sys.argv", ["server.py", "plan", *options])
    assert server.main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mode"] == MODE and plan["original_job_id"] == "71"
    assert not plan["submitted"] and not plan["model_fitted"]
    assert not plan["validation_split_evaluated"] and not plan["test_split_evaluated"]
    assert len(list((tmp_path / "jobs").iterdir())) == 1

    def submit(command, **kwargs):
        assert command[0] == "sbatch"
        assert any("IES_EXPECTED_COMMIT=" + "c" * 40 in arg for arg in command)
        assert str(server.ROOT / "slurm/workflow_diagnostics.sbatch") in command
        return subprocess.CompletedProcess(command, 0, "72\n", "")

    def monitor(job, directory, commit):
        receipt = json.loads((directory / "submission.json").read_bytes())
        assert receipt == dict(job_id="72", job="workflow-diagnostics", commit="c" * 40)
        assert job == "72" and commit == "c" * 40
        return dict(mode=MODE, job_id=job, status="complete", diagnostics={"verified": True})

    monkeypatch.setattr(server.subprocess, "run", submit)
    monkeypatch.setattr(server, "wait_for_workflow_diagnostics", monitor)
    monkeypatch.setattr("sys.argv", ["server.py", "submit", *options, "--wait"])
    assert server.main() == 0
    stdout = capsys.readouterr().out
    assert str(tmp_path) not in stdout
    result = [json.loads(line) for line in stdout.splitlines()]
    assert result[0]["submitted"] and result[1]["diagnostics"]["verified"]


@pytest.mark.parametrize("filename", ["submission.json", "manifest.json"])
def test_server_rejects_malformed_original_binding_without_traceback(
    frozen, tmp_path, monkeypatch, capsys, filename
):
    server = load_script("server")
    cohort, history, config, workflow = frozen
    path = workflow.parent / filename if filename == "submission.json" else workflow / filename
    write_json(path, ["generated-private-payload"])
    settings = dict(
        output_root=str(tmp_path),
        python_executable="/generated/python",
        slurm=dict(partition="cpu", account=None, cpus=2, memory="4G", time_limit="00:20:00"),
    )
    monkeypatch.setattr(server, "load_server_config", lambda *a, **kw: settings)
    monkeypatch.setattr(server, "discover_clock_artifacts", lambda root: (cohort, history))
    monkeypatch.setattr(
        "sys.argv",
        [
            "server.py",
            "plan",
            "workflow-diagnostics",
            "--auto-artifacts",
            "--workflow-config",
            str(config),
            "--job-id",
            "71",
            "--source-commit",
            "b" * 40,
        ],
    )
    with pytest.raises(SystemExit) as error:
        server.main()
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert not captured.out and "Traceback" not in captured.err
    assert "generated-private" not in captured.err and str(tmp_path) not in captured.err


@pytest.mark.parametrize("status,code", [("complete", 0), ("failed", 2), ("limited", 2)])
def test_diagnostic_cli_status_and_sanitized_errors(monkeypatch, capsys, status, code):
    args = ["workflow-diagnostics", "run"]
    for name in ("cohort-dir", "history-dir", "config", "workflow-dir", "output-dir"):
        args += ["--" + name, "generated"]
    monkeypatch.setattr(runner, "run_diagnostics", lambda *a: dict(mode=MODE, status=status))
    assert main(args) == code
    assert json.loads(capsys.readouterr().out)["status"] == status

    def fail(*args):
        raise RuntimeError("generated-private-payload")

    monkeypatch.setattr(runner, "run_diagnostics", fail)
    with pytest.raises(SystemExit):
        main(args)
    assert "generated-private" not in capsys.readouterr().err
