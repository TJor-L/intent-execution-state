"""Generated operational checks; no remote submission or clinical data."""

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from conftest import load_script

from ies import recurrent_task_runner as runner
from ies.io import sha256, write_json
from ies.recurrent_task import MODE, RecurrentTaskError
from ies.recurrent_task_demo import run_generated_cases


def report():
    value = run_generated_cases()["cases"]["complete"]
    value.update(
        data_class="restricted_aggregate", source_stable=True, complete_full_source_scan=True
    )
    return value


def test_qualitative_feedback_does_not_copy_counts_or_private_payloads():
    value = report()
    value["private_sentinel"] = "never_emit_this"
    result = runner.summarize_report(value)
    assert result["recurrent_paths_in_selected_domain"] == "observed"
    assert result["ascertained_multiorder_windows"] == "observed"
    assert "never_emit_this" not in json.dumps(result)
    assert "counts" not in result
    value["test_split_evaluated"] = True
    with pytest.raises(RecurrentTaskError):
        runner.summarize_report(value)


def test_result_review_checks_commit_and_report_digest(tmp_path):
    write_json(tmp_path / "task_report.json", report())
    write_json(
        tmp_path / "manifest.json",
        {
            "mode": MODE,
            "status": "complete",
            "source_commit": "a" * 40,
            "data_class": "restricted_aggregate",
            "artifacts_sha256": {"task_report.json": sha256(tmp_path / "task_report.json")},
        },
    )
    assert runner.read_summary(tmp_path, "a" * 40)["coverage_verified"]
    with pytest.raises(RecurrentTaskError):
        runner.read_summary(tmp_path, "c" * 40)
    write_json(tmp_path / "task_report.json", {})
    with pytest.raises(RecurrentTaskError):
        runner.read_summary(tmp_path, "a" * 40)


def test_existing_mapping_discovery_uses_exact_prior_bytes_and_fails_if_ambiguous(tmp_path):
    configs, cohort = tmp_path / "configs", tmp_path / "cohort"
    configs.mkdir()
    cohort.mkdir()
    candidate = configs / "toy.local.yaml"
    candidate.write_text("synthetic_mapping_only: true\n")
    write_json(cohort / "manifest.json", {"mapping_sha256": sha256(candidate)})
    assert runner.discover_existing_mapping(configs, cohort) == candidate
    (configs / "duplicate.local.yaml").write_bytes(candidate.read_bytes())
    with pytest.raises(RecurrentTaskError, match="not_unique"):
        runner.discover_existing_mapping(configs, cohort)


def test_server_plan_binds_only_metadata_and_overrides_fixed_resources(tmp_path, monkeypatch):
    server = load_script("server")
    cohort = tmp_path / "cohort"
    cohort.mkdir()
    write_json(
        cohort / "manifest.json",
        {
            "mode": "bounded_phase0_cohort_extraction",
            "status": "complete",
            "data_class": "restricted_clinical",
            "mapping_sha256": "b" * 64,
        },
    )
    mapping = SimpleNamespace(feasibility=SimpleNamespace(sources=[]))
    monkeypatch.setattr(server, "load_eligibility_mapping", lambda p: (mapping, "b" * 64))
    monkeypatch.setattr(runner, "AUTHORIZED_ROOT", tmp_path)
    monkeypatch.setattr(runner, "ROOT", tmp_path / "checkout")
    config = {
        "slurm": {
            "cpus": 1,
            "memory": "2G",
            "time_limit": "00:10:00",
            "partition": "toy_cpu",
            "account": None,
        },
        "output_root": str(tmp_path),
        "python_executable": sys.executable,
    }
    command = server.sbatch_command(
        config,
        "recurrent-audit",
        tmp_path / "job",
        mapping_path=tmp_path / "existing.local.yaml",
        cohort_dir=cohort,
    )
    assert "--mem=4096M" in command and "--time=00:22:00" in command
    assert "--cpus-per-task=2" in command
    export = next(arg for arg in command if arg.startswith("--export="))
    assert "IES_MAPPING_SHA256=" + "b" * 64 in export
    assert sha256(cohort / "manifest.json") in export
    assert "IES_COHORT_PATH_SHA256=" + runner.cohort_path_digest(cohort) in export
    assert not (cohort / "cohort.parquet").exists()
    assert not (tmp_path / "job").exists()

    # Input authority is the configured artifact root, independent of Git metadata.
    with pytest.raises(ValueError, match="private output storage"):
        server.sbatch_command(
            dict(config, output_root=str(tmp_path / "different_artifacts")),
            "recurrent-audit",
            tmp_path / "job",
            mapping_path=tmp_path / "existing.local.yaml",
            cohort_dir=cohort,
        )
    assert not (tmp_path / "job").exists()

    # A real invalid output fails before creating a run directory or submitting.
    (tmp_path / "job").mkdir()
    (tmp_path / "job" / ".git").write_text("gitdir: synthetic\n")
    with pytest.raises(RecurrentTaskError, match="inside_repository"):
        server.sbatch_command(
            config,
            "recurrent-audit",
            tmp_path / "job",
            mapping_path=tmp_path / "existing.local.yaml",
            cohort_dir=cohort,
        )
    assert not (tmp_path / "job" / "recurrent-audit").exists()


@pytest.mark.parametrize(
    "failure,expected",
    [
        (SimpleNamespace(returncode=71), "limited"),
        (SimpleNamespace(returncode=72), "limited"),
        (SimpleNamespace(returncode=70), "failed"),
        (subprocess.TimeoutExpired("toy", 1), "limited"),
    ],
)
def test_worker_failure_has_no_private_exception_or_partial_success(
    tmp_path, monkeypatch, failure, expected
):
    cohort, output = tmp_path / "cohort", tmp_path / "output"
    cohort.mkdir()
    write_json(cohort / "manifest.json", {})
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)
    monkeypatch.setattr(runner, "load_eligibility_mapping", lambda p: (None, "b" * 64))
    monkeypatch.setattr(runner, "validate_paths", lambda *args: None)
    monkeypatch.setenv("IES_MAPPING_SHA256", "b" * 64)
    monkeypatch.setenv("IES_COHORT_PATH_SHA256", runner.cohort_path_digest(cohort))
    monkeypatch.setenv("IES_COHORT_MANIFEST_SHA256", sha256(cohort / "manifest.json"))

    def failed(*args, **kwargs):
        assert kwargs["stdout"] == subprocess.DEVNULL and kwargs["stderr"] == subprocess.DEVNULL
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(runner.subprocess, "run", failed)
    result = runner.run_task(tmp_path / "mapping", cohort, output)
    assert result["status"] == expected
    assert not (output / "manifest.json").exists()
    value = json.loads((output / "failure.json").read_text())
    assert value["automatic_retry"] is False and "counts" not in value


def test_source_context_error_is_sanitized(monkeypatch, capsys):
    def reject():
        raise ValueError("toy_private_value_never_print")

    monkeypatch.setattr(runner, "verify_execution_context", reject)
    assert runner.main() == 2
    assert "toy_private_value" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "error,category,code",
    [
        (ValueError("source_revision_changed"), "validation_error", "source_revision_changed"),
        (ValueError("private_path_or_record"), "validation_error", "unclassified"),
        (PermissionError("private_path_or_record"), "permission_error", "unclassified"),
        (FileExistsError("private_path_or_record"), "output_already_exists", "unclassified"),
        (RuntimeError("private_path_or_record"), "unclassified_error", "unclassified"),
        (MemoryError("private_path_or_record"), "memory_error", "unclassified"),
    ],
)
def test_early_failures_emit_only_fixed_categories(monkeypatch, capsys, error, category, code):
    def reject():
        raise error

    monkeypatch.setattr(runner, "verify_execution_context", reject)
    assert runner.main() == (72 if isinstance(error, MemoryError) else 2)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "private_path_or_record" not in captured.err
    assert json.loads(captured.err) == {
        "mode": MODE,
        "status": "failed",
        "error_category": category,
        "error_code": code,
        "automatic_retry": False,
    }


def test_worker_end_to_end_writes_only_verified_aggregates(tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from test_recurrent_task_access import cohort_artifact, write_case

    from ies.feasibility import worker
    from ies.recurrent_task_access import select_training_patients

    sources = tmp_path / "sources"
    sources.mkdir()
    mapping, _ = write_case(sources)
    cohort = tmp_path / "cohort"
    cohort.mkdir()
    digest = cohort_artifact(cohort)
    selected, _ = select_training_patients(cohort, digest, "b" * 64)
    target_patient = min(selected)[1]
    # Match one selected generated original-cohort patient; all other selected patients
    # deliberately have no mapped orders in this complete toy snapshot.
    for source in mapping.sources:
        for path in source.path.glob("*.parquet"):
            rows = pq.read_table(path).to_pylist()
            for row in rows:
                row[source.columns["patient_id"]] = target_patient
            pq.write_table(pa.Table.from_pylist(rows), path)
    config = tmp_path / "mapping.local.yaml"
    config.write_text("generated_mapping: true\n")
    feasibility = tmp_path / "feasibility.local.yaml"
    feasibility.write_text("generated_clocks: true\n")
    # The selector binds the exact old mapping digest; adjust the generated manifest.
    manifest = json.loads((cohort / "manifest.json").read_text())
    manifest["mapping_sha256"] = sha256(config)
    write_json(cohort / "manifest.json", manifest)
    digest = sha256(cohort / "manifest.json")
    private = SimpleNamespace(
        feasibility=mapping,
        feasibility_path=feasibility,
        feasibility_sha256=sha256(feasibility),
    )
    monkeypatch.setattr(runner, "load_eligibility_mapping", lambda p: (private, sha256(config)))
    monkeypatch.setattr(runner, "validate_paths", lambda *args: None)
    monkeypatch.setattr(worker, "apply_limits", lambda limits: None)
    monkeypatch.setenv("IES_MAPPING_SHA256", sha256(config))
    monkeypatch.setenv("IES_COHORT_PATH_SHA256", runner.cohort_path_digest(cohort))
    monkeypatch.setenv("IES_COHORT_MANIFEST_SHA256", digest)
    monkeypatch.setenv("IES_EXPECTED_COMMIT", "a" * 40)
    output = tmp_path / "output"
    output.mkdir()
    assert runner._worker(config, cohort, output) == 0
    assert {path.name for path in output.iterdir()} == {"task_report.json", "manifest.json"}
    summary = runner.read_summary(output, "a" * 40)
    assert summary["coverage_verified"] is True
    assert summary["recurrent_paths_in_selected_domain"] == "observed"
    combined = "".join(path.read_text() for path in output.iterdir())
    assert "toy_patient" not in combined and "toy_event" not in combined


def test_main_rejects_missing_slurm_context_before_access(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("IES_EXECUTION_CONTEXT", "ucsf")
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            str(tmp_path / "absent_mapping"),
            str(tmp_path / "absent_cohort"),
            str(tmp_path / "output"),
        ],
    )
    assert runner.main() == 2
    assert not (tmp_path / "output").exists()
    assert str(tmp_path) not in capsys.readouterr().err


@pytest.mark.parametrize("entry", ["run_task", "_worker"])
@pytest.mark.parametrize("pin", [None, "wrong", "different_path"])
def test_changed_input_location_stops_before_mapping_read(tmp_path, monkeypatch, entry, pin):
    from ies.feasibility import worker

    cohort, output = tmp_path / "cohort", tmp_path / "output"
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)
    monkeypatch.setattr(worker, "apply_limits", lambda limits: None)
    monkeypatch.setattr(
        runner, "load_eligibility_mapping", lambda p: pytest.fail("Must not read mapping")
    )
    monkeypatch.delenv("IES_COHORT_PATH_SHA256", raising=False)
    if pin is not None:
        value = runner.cohort_path_digest(tmp_path / "other") if pin == "different_path" else pin
        monkeypatch.setenv("IES_COHORT_PATH_SHA256", value)
    with pytest.raises(RecurrentTaskError, match="cohort_path_changed"):
        getattr(runner, entry)(tmp_path / "mapping", cohort, output)
    assert not output.exists()
