"""Generated receipts/logs only; inspection must not emit arbitrary log payloads."""

import json

import pytest
from conftest import load_script

from ies import recurrent_task_runner as runner
from ies.recurrent_task import MODE


@pytest.fixture
def records(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "AUTHORIZED_ROOT", tmp_path)
    monkeypatch.setattr(runner, "ROOT", tmp_path / "code")
    root = tmp_path / "results"
    run = root / "jobs" / "toy"
    run.mkdir(parents=True)
    (run / "submission.json").write_text(
        json.dumps(
            {
                "job_id": "123",
                "job": "recurrent-audit",
                "commit": "a" * 40,
            }
        )
    )
    return load_script("inspect_recurrent_job"), root, run


def test_sanitizes_existing_logs_without_writing_or_reading_inputs(records):
    script, root, run = records
    (run / "slurm-123.err").write_text(
        "PRIVATE_SENTINEL\n"
        + json.dumps(
            {
                "mode": MODE,
                "status": "failed",
                "error_category": "validation_error",
                "error_code": "recurrent_inputs_changed",
                "private": "PRIVATE_SENTINEL",
            }
        )
        + "\n"
        + json.dumps(
            {
                "mode": MODE,
                "status": "failed",
                "error_category": ["PRIVATE_SENTINEL"],
                "error_code": "PRIVATE_SENTINEL",
            }
        )
    )
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = script.inspect_job(root, "123", "a" * 40)
    assert result["failure_record"] == "absent"
    assert result["runner_errors"] == [
        {"error_code": "recurrent_inputs_changed", "error_category": "validation_error"},
        {"error_code": "unclassified", "error_category": "unclassified_error"},
    ]
    assert "PRIVATE_SENTINEL" not in json.dumps(result)
    assert result["resubmitted"] is False and result["raw_source_scan"] is False
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("limit", [None, "memory", "cpu", "runtime", "recurrent_file_byte_limit"])
def test_reads_worker_failure_but_does_not_invent_discarded_detail(records, limit):
    script, root, run = records
    folder = run / "recurrent-audit"
    folder.mkdir()
    (folder / "failure.json").write_text(
        json.dumps(
            {
                "status": "limited" if limit else "failed",
                "limit": limit,
                "automatic_retry": False,
            }
        )
    )
    result = script.inspect_job(root, "123", "a" * 40)
    assert result["worker_limit"] == limit
    assert result["worker_detail_available"] is False


@pytest.mark.parametrize("problem", ["commit", "duplicate", "link", "oversize", "bad_failure"])
def test_unverified_records_are_rejected(records, problem):
    script, root, run = records
    if problem == "commit":
        (run / "submission.json").write_text('{"job_id": "123"}')
    elif problem == "duplicate":
        other = root / "jobs" / "duplicate"
        other.mkdir()
        (other / "submission.json").write_bytes((run / "submission.json").read_bytes())
    elif problem == "link":
        (run / "slurm-123.err").symlink_to(run / "missing")
    elif problem == "oversize":
        (run / "slurm-123.err").write_bytes(b"x" * 65537)
    else:
        folder = run / "recurrent-audit"
        folder.mkdir()
        (folder / "failure.json").write_text('{"status":"PRIVATE_SENTINEL"}')
    with pytest.raises(ValueError):
        script.inspect_job(root, "123", "a" * 40)
