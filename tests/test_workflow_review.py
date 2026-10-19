"""Generated-only checks for immutable report review and qualitative output."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import load_script

from ies import clinical_baseline, workflow_review
from ies.clock_audit_ops import ClockAuditOpsError
from ies.io import sha256, write_json
from ies.workflow_cv import CONTRASTS, MODE, load_workflow_config, workflow_cross_validation
from ies.workflow_diagnostic import generate_workflow_case

ROOT = Path(__file__).resolve().parents[1]
JOB = "71"
COMMIT = "a" * 40


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    monkeypatch.setattr(workflow_review.sys, "platform", "linux")
    monkeypatch.setenv("IES_EXECUTION_CONTEXT", "ucsf")
    config, _ = load_workflow_config(ROOT / "configs/workflow_cv.yaml")
    cohort, grouped = generate_workflow_case(17, "type_timing_signal", patients=60)
    report, models = workflow_cross_validation(cohort, grouped, config, data_class="synthetic")
    report["data_class"] = "restricted_aggregate"
    report["generated_private_sentinel"] = "never-print-this-generated-payload"
    run = tmp_path / "jobs" / "generated-run"
    output = run / "workflow-cv"
    write_json(run / "submission.json", dict(job_id=JOB, job="workflow-cv", commit=COMMIT))
    write_json(output / "workflow_report.json", report)
    write_json(output / "models.json", models)
    write_json(output / "config.json", config)
    manifest = dict(
        schema_version=1,
        mode=MODE,
        status="complete",
        data_class="restricted_clinical",
        source_commit=COMMIT,
        evaluation_scope=config["evaluation_scope"],
        validation_split_evaluated=False,
        test_split_evaluated=False,
        original_splits_changed=False,
        raw_source_scan=False,
        gpu_used=False,
        prediction_rows_persisted=False,
        artifacts_sha256={
            name: sha256(output / name)
            for name in ("workflow_report.json", "config.json", "models.json")
        },
    )
    write_json(output / "manifest.json", manifest)
    return tmp_path, output, report, config


def refresh(output, name):
    manifest = json.loads((output / "manifest.json").read_bytes())
    manifest["artifacts_sha256"][name] = sha256(output / name)
    write_json(output / "manifest.json", manifest)


def test_review_is_read_only_without_fit_scheduler_or_row_access(artifacts, monkeypatch):
    root, output, report, _ = artifacts
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        pytest.fail("Review cannot fit, submit or decode row artifacts")

    monkeypatch.setattr("ies.workflow_cv.workflow_cross_validation", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr("pyarrow.parquet.read_table", forbidden)
    original = Path.read_bytes
    original_open = Path.open
    reads = []

    def open_read(path, mode="r", *args, **kwargs):
        assert mode == "rb", "Review must not open artifacts for writing"
        reads.append(path.name)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_read)
    result = workflow_review.review_workflow(root, JOB, COMMIT)
    assert result["report_verified"] is True
    assert result["typed_timing_development_support"] == report["typed_timing_development_support"]
    assert set(reads) == {
        "submission.json",
        "manifest.json",
        "workflow_report.json",
        "config.json",
        "models.json",
    }
    assert set(result["comparisons"]) == set(CONTRASTS)
    rendered = json.dumps(result)
    assert str(root) not in rendered and "never-print" not in rendered
    assert "n_orders" not in rendered and "nll_per_order" not in rendered
    assert {p: original(p) for p in root.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    "mean,interval,fold_values,expected",
    [
        (-0.03, [-0.06, -0.01], [-1] * 5, ("lower", "below_zero", "all_lower")),
        (0.03, [0.01, 0.06], [1] * 5, ("higher", "above_zero", "all_higher")),
        (0.0, [-0.01, 0.01], [0] * 5, ("equal", "includes_zero", "all_equal")),
        (-0.01, [-0.04, 0.0], [-1, -1, -1, -1, 1], ("lower", "includes_zero", "mixed")),
        (0.01, [0.0, 0.04], [0, 1, 1, 1, 1], ("higher", "includes_zero", "mixed")),
    ],
)
def test_secondary_descriptions_never_create_a_new_pass_rule(
    artifacts, mean, interval, fold_values, expected
):
    _, _, report, config = artifacts
    report["metrics"]["counts_minus_intercept"] = dict(
        nll_per_order=mean, conditional_patient_bootstrap_95ci=interval
    )
    for fold, value in zip(report["folds"], fold_values, strict=True):
        fold["contrasts"]["counts_minus_intercept"] = value
    summary = workflow_review._summarize(report, config)
    comparison = summary["comparisons"]["counts_minus_intercept"]
    assert tuple(comparison.values()) == expected
    assert set(comparison) == {"mean_loss_direction", "conditional_interval", "fold_directions"}
    assert summary["typed_timing_development_support"] == report["typed_timing_development_support"]


@pytest.mark.parametrize("name", ["models.json", "config.json", "workflow_report.json"])
def test_review_rejects_altered_files_without_exposing_contents(artifacts, name):
    root, output, _, _ = artifacts
    (output / name).write_text("generated-sensitive-invalid-payload")
    with pytest.raises(ClockAuditOpsError, match="^workflow_review_invalid_result$"):
        workflow_review.review_workflow(root, JOB, COMMIT)


@pytest.mark.parametrize(
    "defect",
    [
        "flag_type",
        "flag_disagrees",
        "held_out",
        "duplicate_fold",
        "interval",
        "nonfinite",
        "fold_count",
    ],
)
def test_review_validates_report_semantics_even_with_matching_hash(artifacts, defect):
    root, output, report, _ = artifacts
    if defect == "flag_type":
        report["typed_timing_development_support"] = "false"
    elif defect == "flag_disagrees":
        report["typed_timing_development_support"] = not report["typed_timing_development_support"]
    elif defect == "held_out":
        report["test_split_evaluated"] = True
    elif defect == "duplicate_fold":
        report["folds"][0]["fold"] = report["folds"][1]["fold"]
    elif defect == "interval":
        report["metrics"]["counts_minus_intercept"]["conditional_patient_bootstrap_95ci"] = [1, -1]
    elif defect == "nonfinite":
        report["metrics"]["counts_minus_intercept"]["nll_per_order"] = float("nan")
    else:
        report["improved_folds"] += 1
    (output / "workflow_report.json").write_text(json.dumps(report))
    refresh(output, "workflow_report.json")
    with pytest.raises(ClockAuditOpsError, match="^workflow_review_invalid_result$"):
        workflow_review.review_workflow(root, JOB, COMMIT)


@pytest.mark.parametrize(
    "defect", ["wrong_commit", "duplicate", "bound", "symlink", "large_receipt"]
)
def test_review_receipt_discovery_is_exact_and_bounded(artifacts, defect):
    root, output, _, _ = artifacts
    receipt = output.parent / "submission.json"
    if defect == "wrong_commit":
        value = json.loads(receipt.read_bytes())
        value["commit"] = "b" * 40
        write_json(receipt, value)
    elif defect == "duplicate":
        write_json(
            root / "jobs" / "duplicate" / "submission.json", json.loads(receipt.read_bytes())
        )
    elif defect == "bound":
        for index in range(1000):
            (root / "jobs" / f"generated-{index}").mkdir()
    elif defect == "symlink":
        (root / "jobs" / "link").symlink_to(output.parent, target_is_directory=True)
    else:
        receipt.write_text(" " * (16 * 1024 + 1))
    with pytest.raises(ClockAuditOpsError):
        workflow_review.review_workflow(root, JOB, COMMIT)


def test_review_detects_mid_review_mutation(artifacts, monkeypatch):
    root, output, _, _ = artifacts
    summarize = workflow_review._summarize

    def mutate(report, config):
        result = summarize(report, config)
        (output / "workflow_report.json").write_text("{}")
        return result

    monkeypatch.setattr(workflow_review, "_summarize", mutate)
    with pytest.raises(ClockAuditOpsError):
        workflow_review.review_workflow(root, JOB, COMMIT)


def test_review_refuses_mac_before_reading(artifacts, monkeypatch):
    root, _, _, _ = artifacts
    monkeypatch.setattr(workflow_review.sys, "platform", "darwin")
    with pytest.raises(ClockAuditOpsError, match="workflow_review_requires_ucsf"):
        workflow_review.review_workflow(root, JOB, COMMIT)


def test_server_review_returns_before_any_submission_or_artifact_discovery(
    artifacts, monkeypatch, capsys
):
    root, _, _, _ = artifacts
    server = load_script("server")
    monkeypatch.setattr(server, "load_server_config", lambda *a, **kw: {"output_root": str(root)})
    monkeypatch.setattr(server, "source_revision", lambda: "b" * 40)

    def forbidden(*a, **kw):
        pytest.fail("Read-only review entered a submission path")

    monkeypatch.setattr(server, "sbatch_command", forbidden)
    monkeypatch.setattr(server, "discover_clock_artifacts", forbidden)
    monkeypatch.setattr(server.subprocess, "run", forbidden)
    argv = ["server.py", "review", "workflow-cv", "--job-id", JOB, "--source-commit", COMMIT]
    monkeypatch.setattr("sys.argv", argv)
    assert server.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source_commit"] == COMMIT and result["reviewer_commit"] == "b" * 40
    assert result["clinical_advancement_decision"] == "not_applicable"
    monkeypatch.setattr("sys.argv", argv + ["--wait"])
    with pytest.raises(SystemExit) as error:
        server.main()
    assert error.value.code == 2
    assert str(root) not in capsys.readouterr().err


def test_invalid_reader_inputs_never_include_payloads(artifacts):
    root, output, _, _ = artifacts
    manifest = json.loads((output / "manifest.json").read_bytes())
    manifest["artifacts_sha256"] = ["generated-private-payload"]
    write_json(output / "manifest.json", manifest)
    with pytest.raises(ClockAuditOpsError) as error:
        workflow_review.review_workflow(root, JOB, COMMIT)
    assert str(error.value) == "workflow_review_invalid_result"
