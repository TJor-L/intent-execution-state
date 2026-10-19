"""All operational discovery and scheduler tests use generated local artifacts."""

import json
import shutil
import subprocess

import pytest
import yaml
from conftest import load_script

from ies import clinical_baseline
from ies import clock_audit_ops as ops
from ies.io import sha256, write_json


def _jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    cohort = tmp_path / "jobs/first/cohort-extract"
    history = tmp_path / "jobs/second/dual-clock-history"
    cohort.mkdir(parents=True)
    history.mkdir(parents=True)
    write_json(
        cohort / "manifest.json",
        {
            "status": "complete",
            "data_class": "restricted_clinical",
            "mode": "bounded_phase0_cohort_extraction",
        },
    )
    write_json(
        history / "manifest.json",
        {
            "status": "complete",
            "data_class": "restricted_clinical",
            "mode": "dual_clock_history_extraction",
            "cohort_manifest_sha256": sha256(cohort / "manifest.json"),
        },
    )
    return cohort, history


def test_discovery_selects_only_a_unique_bound_pair_and_respects_bounds(tmp_path, monkeypatch):
    cohort, history = _jobs(tmp_path, monkeypatch)
    assert ops.discover_clock_artifacts(tmp_path) == (cohort, history)
    with pytest.raises(ops.ClockAuditOpsError, match="discovery_limit"):
        ops.discover_clock_artifacts(tmp_path, max_jobs=1)
    with pytest.raises(ops.ClockAuditOpsError, match="discovery_limit"):
        ops.discover_clock_artifacts(tmp_path, max_manifest_bytes=1)
    duplicate = tmp_path / "jobs/third/dual-clock-history"
    shutil.copytree(history, duplicate)
    with pytest.raises(ops.ClockAuditOpsError, match="not_unique"):
        ops.discover_clock_artifacts(tmp_path)


def test_discovery_rejects_symlinks_and_bad_binding(tmp_path, monkeypatch):
    _, history = _jobs(tmp_path, monkeypatch)
    manifest = json.loads((history / "manifest.json").read_text())
    manifest["cohort_manifest_sha256"] = ["not-a-digest"]
    write_json(history / "manifest.json", manifest)
    with pytest.raises(ops.ClockAuditOpsError, match="invalid_manifest"):
        ops.discover_clock_artifacts(tmp_path)
    (tmp_path / "jobs/first").rename(tmp_path / "relocated")
    (tmp_path / "jobs/first").symlink_to(tmp_path / "relocated", target_is_directory=True)
    with pytest.raises(ops.ClockAuditOpsError):
        ops.discover_clock_artifacts(tmp_path)


def _result(tmp_path):
    output = tmp_path / "clock-audit"
    output.mkdir()
    write_json(output / "clock_report.json", {"private-generated-counter": 100})
    write_json(
        output / "manifest.json",
        {
            "status": "complete",
            "mode": ops.MODE,
            "data_class": "restricted_aggregate",
            "source_commit": "a" * 40,
            "artifacts_sha256": {"clock_report.json": sha256(output / "clock_report.json")},
        },
    )


def test_monitor_waits_for_exact_job_and_emits_no_private_results(tmp_path, monkeypatch):
    _result(tmp_path)
    replies = iter(
        [
            "12|PENDING|0:0\n",
            "12.batch|COMPLETED|0:0\n",
            "12|COMPLETED|0:0\n12.batch|COMPLETED|0:0\n",
        ]
    )

    def run(command, **kwargs):
        assert command[0] == "sacct" and kwargs["timeout"] == 30
        return subprocess.CompletedProcess(command, 0, next(replies), "")

    monkeypatch.setattr(ops.subprocess, "run", run)
    monkeypatch.setattr(ops.time, "sleep", lambda _: None)
    result = ops.wait_for_clock_audit("12", tmp_path, "a" * 40)
    assert result == {
        "mode": ops.MODE,
        "job_id": "12",
        "status": "complete",
        "private_review_required": True,
    }
    assert "100" not in json.dumps(result)


@pytest.mark.parametrize(
    "response", ["12|FAILED|1:0", "12|OUT_OF_MEMORY|0:9", "12|COMPLETED|1:0", "12|COMPLETED|0:0"]
)
def test_monitor_does_not_accept_failure_or_missing_result(tmp_path, monkeypatch, response):
    monkeypatch.setattr(
        ops.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, response, "private-error"),
    )
    with pytest.raises(ops.ClockAuditOpsError):
        ops.wait_for_clock_audit("12", tmp_path, "a" * 40)


def test_monitor_timeout_never_cancels_or_resubmits(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("No scheduler mutation or query expected after immediate timeout")

    monkeypatch.setattr(ops.subprocess, "run", unexpected)
    with pytest.raises(ops.ClockAuditOpsError, match="not_cancelled_or_resubmitted"):
        ops.wait_for_clock_audit("12", tmp_path, "a" * 40, timeout_seconds=0)


def test_server_plan_auto_discovery_is_sanitized_and_does_not_submit(tmp_path, monkeypatch, capsys):
    _jobs(tmp_path, monkeypatch)
    server = load_script("server")
    config = {
        "execution_context": "ucsf",
        "institutional_access_confirmed": True,
        "data_root": str(tmp_path / "not-opened-raw"),
        "output_root": str(tmp_path),
        "python_executable": "/server/python",
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 2,
            "memory": "4G",
            "time_limit": "00:05:30",
        },
        "audit": {"max_files": 10, "max_directories": 100},
    }
    # Source and output roots must be disjoint even for planning.
    config["data_root"] = str(tmp_path.parent / "raw-unused")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config))
    monkeypatch.setenv("IES_EXECUTION_CONTEXT", "ucsf")
    monkeypatch.setattr(server, "load_server_config", lambda *a, **k: config)
    monkeypatch.setattr(
        "sys.argv", ["server.py", "plan", "clock-audit", "--config", str(path), "--auto-artifacts"]
    )

    def fail(*args, **kwargs):
        pytest.fail("Plan must not submit")

    monkeypatch.setattr(server.subprocess, "run", fail)
    assert server.main() == 0
    output = capsys.readouterr().out
    assert str(tmp_path) not in output and "raw-unused" not in output
    assert json.loads(output)["outcome_columns_read"] is False


def test_server_submit_then_wait_records_receipt_before_monitoring(tmp_path, monkeypatch, capsys):
    _jobs(tmp_path, monkeypatch)
    server = load_script("server")
    config = {
        "output_root": str(tmp_path),
        "python_executable": "/server/python",
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 2,
            "memory": "4G",
            "time_limit": "00:05:30",
        },
    }
    monkeypatch.setattr(server, "load_server_config", lambda *a, **k: config)
    monkeypatch.setattr(server, "source_revision", lambda: "a" * 40)
    monkeypatch.setattr(
        "sys.argv", ["server.py", "submit", "clock-audit", "--auto-artifacts", "--wait"]
    )

    def submit(command, **kwargs):
        assert command[0] == "sbatch"
        assert any("IES_EXPECTED_COMMIT=" + "a" * 40 in item for item in command)
        return subprocess.CompletedProcess(command, 0, "123\n", "")

    def monitor(job_id, run_dir, commit):
        receipt = json.loads((run_dir / "submission.json").read_text())
        assert receipt == {"job_id": "123", "job": "clock-audit", "commit": "a" * 40}
        assert run_dir.stat().st_mode & 0o077 == 0
        assert (job_id, commit) == ("123", "a" * 40)
        return {"status": "complete", "private_review_required": True}

    monkeypatch.setattr(server.subprocess, "run", submit)
    monkeypatch.setattr(server, "wait_for_clock_audit", monitor)
    assert server.main() == 0
    output = capsys.readouterr().out
    assert str(tmp_path) not in output
    assert [json.loads(line).get("submitted", False) for line in output.splitlines()] == [
        True,
        False,
    ]
