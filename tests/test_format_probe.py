"""Generated schemas only; no UCSF column mappings or patient fixtures."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import load_script

from ies import clock_audit_ops
from ies import format_probe_runner as runner
from ies.data import format_probe as probe
from ies.io import sha256, write_json

DEFAULT_TIMESTAMP = pa.timestamp("us")


def fixture(path, signature="drug_exposure", *, datetime_type=DEFAULT_TIMESTAMP):
    fields = [pa.field(name, pa.int64()) for name in sorted(probe.SIGNATURES[signature])]
    if signature == "drug_exposure" and datetime_type is not None:
        fields.append(pa.field("drug_exposure_start_datetime", datetime_type))
    schema = pa.schema(fields, metadata={b"private-metadata": b"DO_NOT_EXPORT"})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_batches([], schema=schema), path)
    return path


def test_empty_standard_shaped_table_is_candidate_not_semantic_or_data_confirmation(tmp_path):
    path = fixture(tmp_path / "private.parquet")
    summary = probe.summarize_format_probe(probe.probe_format(path))
    assert summary["format_candidate"] == "omop_like_schema"
    assert summary["omop_signature_observed"]["drug_exposure"] is True
    assert summary["drug_datetime_storage"] == ["timestamp"]
    assert summary["format_confirmed"] is False
    assert summary["new_server_update_verified"] is False
    assert summary["source_event_linkage"] == "not_assessed"
    assert summary["order_administration_distinction"] == "not_assessed"
    assert summary["occurrence_availability_semantics"] == "not_assessed"
    assert summary["research_feasibility"] == "not_established"


def test_reader_only_opens_header_trailer_footer_and_cannot_decode_data_pages(
    tmp_path, monkeypatch
):
    path = tmp_path / "SECRET_PATH.parquet"
    table = pa.table({"SECRET_COLUMN": ["PRIVATE_ROW_VALUE"] * 1000})
    table = table.replace_schema_metadata({b"PRIVATE_KEY": b"PRIVATE_METADATA"})
    pq.write_table(table, path)
    data = path.read_bytes()
    footer_size = int.from_bytes(data[-8:-4], "little")
    reads = []
    original_fdopen, original_parquet = os.fdopen, pq.ParquetFile

    class FooterStream:
        def __init__(self, stream):
            assert isinstance(stream, io.FileIO)  # Buffered headers can prefetch data pages.
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def read(self, size):
            reads.append((self.stream.tell(), size))
            return self.stream.read(size)

    def footer_parquet(source, **kwargs):
        assert isinstance(source, pa.BufferReader)
        content = source.read()
        assert content == b"PAR1" + data[-8 - footer_size :]
        source.seek(0)
        return original_parquet(source, **kwargs)

    monkeypatch.setattr(os, "fdopen", lambda *a, **k: FooterStream(original_fdopen(*a, **k)))
    monkeypatch.setattr(pq, "ParquetFile", footer_parquet)
    monkeypatch.setattr(pq, "read_table", lambda *a, **k: pytest.fail("Row read"))
    report = probe.probe_format(path)
    assert reads == [(0, 4), (len(data) - 8, 8), (len(data) - 8 - footer_size, footer_size)]
    rendered = json.dumps(report) + json.dumps(probe.summarize_format_probe(report))
    assert "PRIVATE" not in rendered and "SECRET" not in rendered
    assert "statistics" not in report


@pytest.mark.parametrize(
    "dtype,expected",
    [
        (None, "not_observed"),
        (pa.string(), "other_declared_type"),
        (pa.date32(), "other_declared_type"),
        (pa.timestamp("ns"), "timestamp"),
    ],
)
def test_declared_type_never_establishes_actual_precision(tmp_path, dtype, expected):
    report = probe.probe_format(fixture(tmp_path / "part.PARQUET", datetime_type=dtype))
    summary = probe.summarize_format_probe(report)
    assert summary["drug_datetime_storage"] == [expected]
    assert summary["declared_datetime_is_not_verified_precision"] is True


def test_names_match_within_one_schema_only_and_filename_is_not_evidence(tmp_path):
    required = sorted(probe.SIGNATURES["drug_exposure"])
    for index, fields in enumerate((required[:2], required[2:])):
        pq.write_table(
            pa.table({name: [] for name in fields}), tmp_path / f"drug_exposure{index}.parquet"
        )
    summary = probe.summarize_format_probe(probe.probe_format(tmp_path))
    assert summary["format_candidate"] == "unidentified_in_sample"
    assert summary["coverage"].endswith("no_absence_inference")


def test_case_insensitive_signature_and_ambiguous_case_rejected(tmp_path):
    fields = {name.upper(): [] for name in probe.SIGNATURES["drug_exposure"]}
    path = tmp_path / "upper.parquet"
    pq.write_table(pa.table(fields), path)
    assert probe.probe_format(path)["files"][0]["signatures"] == ["drug_exposure"]
    fields["person_id"] = []
    pq.write_table(pa.table(fields), path)
    assert probe.probe_format(path)["read_failures"] == 1


def test_sampling_prefers_distinct_directories_and_respects_file_cap(tmp_path, monkeypatch):
    monkeypatch.setitem(probe.LIMITS, "max_files", 2)
    for index in range(5):
        fixture(tmp_path / "partitioned" / f"part{index}.parquet")
    fixture(tmp_path / "other" / "person.parquet", "person")
    report = probe.probe_format(tmp_path)
    assert len(report["files"]) == 2
    assert report["limit_reached"]
    summary = probe.summarize_format_probe(report)
    assert summary["omop_signature_observed"]["person"]
    assert summary["omop_signature_observed"]["drug_exposure"]


def test_directory_and_entry_caps_and_symlinks_are_explicit(tmp_path, monkeypatch):
    fixture(tmp_path / "one" / "two" / "part.parquet")
    (tmp_path / "link").symlink_to(tmp_path / "one", target_is_directory=True)
    monkeypatch.setitem(probe.LIMITS, "max_directories", 1)
    report = probe.probe_format(tmp_path)
    assert report["directories_visited"] == 1
    assert report["limit_reached"] and report["symlinks_skipped"]
    monkeypatch.setitem(probe.LIMITS, "max_entries", 1)
    assert probe.probe_format(tmp_path)["limit_reached"]
    with pytest.raises(ValueError):
        probe.probe_format(tmp_path / "link")


def test_non_parquet_contents_are_never_opened(tmp_path):
    (tmp_path / "source.csv").write_text("PRIVATE_COLUMN\nPRIVATE_VALUE\n")
    summary = probe.summarize_format_probe(probe.probe_format(tmp_path))
    assert summary["non_parquet_files_seen"] and not summary["readable_parquet_observed"]
    assert "PRIVATE" not in json.dumps(summary)


def test_footer_budget_counts_failed_decoding_and_rejects_large_footers(tmp_path, monkeypatch):
    for index in range(3):
        (tmp_path / f"bad{index}.parquet").write_bytes(
            b"PAR1" + b"X" * 100 + (100).to_bytes(4, "little") + b"PAR1"
        )
    monkeypatch.setitem(probe.LIMITS, "max_total_footer_bytes", 150)
    report = probe.probe_format(tmp_path)
    assert report["footer_bytes_read"] == 100
    assert report["limit_reached"] and report["read_failures"] == 1
    monkeypatch.setitem(probe.LIMITS, "max_footer_bytes", 50)
    assert probe.probe_format(tmp_path)["footer_bytes_read"] == 0


def test_report_projection_rejects_arbitrary_strings_and_types(tmp_path):
    report = probe.probe_format(fixture(tmp_path / "part.parquet"))
    report["files"][0]["signatures"].append("PRIVATE_COLUMN")
    with pytest.raises(ValueError, match="invalid_format_report"):
        probe.summarize_format_probe(report)
    report["files"] = []
    report["limit_reached"] = "PRIVATE"
    with pytest.raises(ValueError, match="invalid_format_report"):
        probe.summarize_format_probe(report)


def test_storage_rejects_repositories_overlaps_and_symlink_parents(tmp_path):
    tmp_path = tmp_path.resolve()
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"
    assert runner.validate_probe_paths(source, output) == (source, output)
    with pytest.raises(ValueError):
        runner.validate_probe_paths(source, source / "output")
    (source / ".git").write_text("worktree")
    with pytest.raises(ValueError):
        runner.validate_probe_paths(source, output)
    (source / ".git").unlink()
    (tmp_path / "link").symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError):
        runner.validate_probe_paths(tmp_path / "link" / "nested", output)


def create_result(tmp_path):
    output = tmp_path / "format-probe"
    output.mkdir()
    source = fixture(tmp_path / "generated" / "part.parquet")
    write_json(output / "format_report.json", probe.probe_format(source))
    write_json(
        output / "manifest.json",
        {
            "mode": probe.MODE,
            "status": "complete",
            "source_commit": "a" * 40,
            "data_class": "restricted_metadata",
            "row_values_read": False,
            "artifacts_sha256": {"format_report.json": sha256(output / "format_report.json")},
        },
    )
    return output


def test_monitor_verifies_binding_and_checksum_before_summary(tmp_path, monkeypatch):
    output = create_result(tmp_path)
    monkeypatch.setattr(
        clock_audit_ops.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, "12|COMPLETED|0:0\n", "PRIVATE"),
    )
    summary = runner.wait_for_format_probe("12", tmp_path, "a" * 40)
    assert summary["format_probe"]["format_candidate"] == "omop_like_schema"
    assert str(tmp_path) not in json.dumps(summary)
    with pytest.raises(clock_audit_ops.ClockAuditOpsError):
        runner.wait_for_format_probe("12", tmp_path, "b" * 40)
    (output / "format_report.json").write_text("PRIVATE")
    with pytest.raises(clock_audit_ops.ClockAuditOpsError):
        runner.wait_for_format_probe("12", tmp_path, "a" * 40)


def test_cli_requires_authorized_slurm_and_sanitizes_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("IES_EXECUTION_CONTEXT", raising=False)
    monkeypatch.setattr(sys, "argv", ["probe", str(tmp_path / "PRIVATE"), str(tmp_path / "out")])
    assert runner.main() == 2
    assert not (tmp_path / "out").exists()
    assert "PRIVATE" not in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["timeout", "exit"])
def test_worker_failure_is_sanitized_and_never_retried(tmp_path, monkeypatch, failure):
    from ies.feasibility import runner as guards

    monkeypatch.setattr(guards, "verify_execution_context", lambda: None)
    source = tmp_path.resolve() / "source"
    source.mkdir()
    output = tmp_path.resolve() / "output"
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 120
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 120, output="PRIVATE", stderr="PRIVATE")
        return subprocess.CompletedProcess(command, 2)

    monkeypatch.setattr(runner.subprocess, "run", run)
    result = runner.run_format_probe(source, output)
    assert result["status"] in {"limited", "failed"} and len(calls) == 1
    assert output.stat().st_mode & 0o077 == 0
    assert "PRIVATE" not in (output / "failure.json").read_text()
    assert not (output / "manifest.json").exists()


def test_successful_generated_worker_sets_limits_and_binds_private_artifacts(tmp_path, monkeypatch):
    from ies.feasibility import runner as guards
    from ies.feasibility import worker as limits

    tmp_path = tmp_path.resolve()
    source = fixture(tmp_path / "generated" / "source.parquet")
    output = tmp_path / "output"
    monkeypatch.setenv("IES_EXPECTED_COMMIT", "a" * 40)
    monkeypatch.setattr(guards, "verify_execution_context", lambda: None)
    applied = []
    monkeypatch.setattr(
        limits,
        "apply_limits",
        lambda value: applied.append((value.memory_mb, value.cpu_seconds, value.cpus)),
    )

    def generated_worker(command, **kwargs):
        assert command[1:4] == ["-m", "ies.format_probe_runner", "--worker"]
        return subprocess.CompletedProcess(command, runner._worker(source, output))

    monkeypatch.setattr(runner.subprocess, "run", generated_worker)
    result = runner.run_format_probe(source, output)
    assert result["status"] == "complete"
    assert applied == [(4096, 120, 2)]
    assert runner.read_probe_summary(output, "a" * 40)["format_candidate"] == "omop_like_schema"
    assert (output / "format_report.json").stat().st_mode & 0o077 == 0
    assert (output / "manifest.json").stat().st_mode & 0o077 == 0


def server_config(tmp_path):
    return {
        "data_root": str(tmp_path / "original-source"),
        "output_root": str(tmp_path / "output"),
        "python_executable": "/server/python",
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 4,
            "memory": "16G",
            "time_limit": "00:10:00",
        },
    }


def test_server_plan_does_not_open_rows_or_submit_and_labels_input_scope(
    tmp_path, monkeypatch, capsys
):
    server = load_script("server")
    monkeypatch.setattr(server, "load_server_config", lambda *a, **k: server_config(tmp_path))
    monkeypatch.setattr(
        sys,
        "argv",
        ["server.py", "plan", "format-probe", "--probe-root", str(tmp_path / "new-source")],
    )
    monkeypatch.setattr(server.subprocess, "run", lambda *a, **k: pytest.fail("Plan submitted"))
    assert server.main() == 0
    rendered = capsys.readouterr().out
    value = json.loads(rendered)
    assert value["input_scope"] == "explicit_probe_root" and value["metadata_only"]
    assert value["row_values_read"] is False and str(tmp_path) not in rendered


def test_server_submission_limits_receipt_and_monitoring(tmp_path, monkeypatch, capsys):
    tmp_path = tmp_path.resolve()
    server = load_script("server")
    config = server_config(tmp_path)
    Path(config["data_root"]).mkdir()
    monkeypatch.setattr(server, "load_server_config", lambda *a, **k: config)
    monkeypatch.setattr(server, "source_revision", lambda: "a" * 40)
    monkeypatch.setattr(sys, "argv", ["server.py", "submit", "format-probe", "--wait"])

    def submit(command, **kwargs):
        assert "--cpus-per-task=2" in command and "--mem=4096M" in command
        assert "--time=00:02:30" in command
        assert any("IES_EXPECTED_COMMIT=" + "a" * 40 in item for item in command)
        assert command[-2] == config["data_root"]
        return subprocess.CompletedProcess(command, 0, "123\n", "")

    def monitor(job_id, run_dir, commit):
        assert json.loads((run_dir / "submission.json").read_text()) == {
            "job": "format-probe",
            "job_id": "123",
            "commit": "a" * 40,
        }
        return {"status": "complete"}

    monkeypatch.setattr(server.subprocess, "run", submit)
    monkeypatch.setattr(server, "wait_for_format_probe", monitor)
    assert server.main() == 0
    assert str(tmp_path) not in capsys.readouterr().out


def test_missing_probe_source_is_rejected_before_submission(tmp_path, monkeypatch, capsys):
    server = load_script("server")
    monkeypatch.setattr(server, "load_server_config", lambda *a, **k: server_config(tmp_path))
    monkeypatch.setattr(sys, "argv", ["server.py", "submit", "format-probe"])
    monkeypatch.setattr(
        server.subprocess, "run", lambda *a, **k: pytest.fail("Submitted missing source")
    )
    with pytest.raises(SystemExit):
        server.main()
    assert str(tmp_path) not in capsys.readouterr().err
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("options", [["--auto-artifacts"], ["--mapping", "/private/mapping"]])
def test_probe_rejects_clinical_artifact_options(monkeypatch, capsys, options):
    server = load_script("server")
    monkeypatch.setattr(sys, "argv", ["server.py", "plan", "format-probe", *options])
    with pytest.raises(SystemExit):
        server.main()
    assert "/private" not in capsys.readouterr().err
