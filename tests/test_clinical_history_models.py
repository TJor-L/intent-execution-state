"""Generated-only tests for matched clinical history models."""

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from conftest import load_script

from ies import clinical_baseline
from ies.clinical_baseline import ClinicalBaselineError
from ies.clinical_history_models import (
    _bootstrap,
    _validation_decision,
    load_history_model_config,
    run_clinical_history_models,
)
from ies.cohort_readiness.extract import SCHEMA
from ies.dual_clock_history import HISTORY_SCHEMA
from ies.io import sha256, write_json
from ies.models.history_piecewise import encode_history

ROOT = Path(__file__).resolve().parents[1]


def _artifacts(tmp_path: Path):
    cohort_dir = tmp_path / "cohort"
    cohort_dir.mkdir()
    rows = []
    for index in range(24):
        split = "train" if index < 16 else "validation" if index < 20 else "test"
        rows.append(
            {
                "patient_id": f"string:person-{index}",
                "order_id": f"string:order-{index}",
                "encounter_id": f"string:visit-{index}",
                "split": split,
                "index_time_hours": 100.0 + index,
                "duration_hours": float(1 + index % 20),
                "cause": index % 4,
                "outcome": (
                    "right_censored"
                    if index % 4 == 0
                    else "execution"
                    if index % 4 == 1
                    else "terminal_without_execution"
                ),
            }
        )
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), cohort_dir / "cohort.parquet")
    cohort_manifest = {
        "status": "complete",
        "mode": "bounded_phase0_cohort_extraction",
        "data_class": "restricted_clinical",
        "bounded_domain": True,
        "source_commit": "a" * 40,
        "artifacts_sha256": {"cohort.parquet": sha256(cohort_dir / "cohort.parquet")},
    }
    write_json(cohort_dir / "manifest.json", cohort_manifest)
    cohort_digest = sha256(cohort_dir / "manifest.json")

    history_dir = tmp_path / "history"
    history_dir.mkdir()
    history_rows = []
    for index, row in enumerate(rows):
        history_rows.append(
            {
                "patient_id": row["patient_id"],
                "index_order_id": row["order_id"],
                "event_id": f"string:event-{index}",
                "event_kind": index % 2,
                "occurrence_lag_hours": float(2 + index % 8),
                "availability_lag_hours": float(1 + index % 4),
                "documentation_delay_hours": 1.0,
            }
        )
    pq.write_table(
        pa.Table.from_pylist(history_rows, schema=HISTORY_SCHEMA),
        history_dir / "history.parquet",
    )
    history_manifest = {
        "status": "complete",
        "mode": "dual_clock_history_extraction",
        "cohort_manifest_sha256": cohort_digest,
        "availability_masked": True,
        "outcome_features_used": False,
        "artifacts_sha256": {"history.parquet": sha256(history_dir / "history.parquet")},
    }
    write_json(history_dir / "manifest.json", history_manifest)
    return cohort_dir, history_dir, cohort_digest, sha256(history_dir / "manifest.json")


def test_history_encoding_is_matched_and_shift_masks_unavailable_events():
    rows = [
        {
            "event_kind": 1,
            "occurrence_lag_hours": 4.0,
            "availability_lag_hours": 1.0,
        }
    ]
    single = encode_history(rows, "availability", [1, 2, 4, 8], [], 0)
    dual = encode_history(rows, "dual_clock", [2, 8], [2, 8], 0)
    shifted = encode_history(rows, "dual_clock", [2, 8], [2, 8], 2)
    assert single.shape == dual.shape == shifted.shape == (8,)
    assert np.count_nonzero(single) == 4 and np.count_nonzero(dual) == 4
    assert not shifted.any()


@pytest.mark.parametrize(
    "field",
    [
        "availability_scales_hours",
        "dual_occurrence_scales_hours",
        "dual_availability_scales_hours",
        "delay_shifts_hours",
    ],
)
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_history_config_rejects_nonfinite_scales_and_shifts(tmp_path, field, invalid):
    config, _ = load_history_model_config(ROOT / "configs/clinical_history_models.yaml")
    config[field][-1] = invalid
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ClinicalBaselineError, match="^invalid_history_model_config$"):
        load_history_model_config(path)


@pytest.mark.parametrize("shift", [float("nan"), float("inf"), -1.0])
def test_history_encoder_rejects_invalid_shift_even_without_events(shift):
    with pytest.raises(ValueError, match="Invalid history encoding"):
        encode_history([], "availability", [1, 4, 12, 24], [], shift)


def test_patient_bootstrap_keeps_pairs_and_all_orders_for_sampled_patients():
    rows = [{"patient_id": patient} for patient in ("a", "a", "b")]
    single = np.array([1.0, 3.0, 10.0])
    dual = single - 0.5
    actual = _bootstrap(rows, {"single": single, "dual": dual, "delta": dual - single}, 200, 7)
    # Independently enumerate seeded two-patient draws, retaining both orders for a.
    rng = np.random.default_rng(7)
    draws = rng.integers(2, size=(200, 2))
    samples = [
        sum(4.0 if patient == 0 else 10.0 for patient in draw)
        / sum(2 if patient == 0 else 1 for patient in draw)
        for draw in draws
    ]
    expected = np.quantile(samples, [0.025, 0.975])
    np.testing.assert_allclose(actual["single"], expected)
    np.testing.assert_allclose(actual["dual"], expected - 0.5)
    np.testing.assert_allclose(actual["delta"], [-0.5, -0.5])


@pytest.mark.parametrize(
    ("base_delta", "upper", "shift_delta", "advance"),
    [
        (-0.005, -0.001, 0.005, True),
        (-0.0049, -0.001, 0.005, False),
        (-0.005, 0.0, 0.005, False),
        (-0.005, -0.001, 0.0051, False),
    ],
)
def test_frozen_advancement_requires_all_three_conditions(base_delta, upper, shift_delta, advance):
    config, _ = load_history_model_config(ROOT / "configs/clinical_history_models.yaml")
    metrics = {"shifts": {}}
    for shift in config["delay_shifts_hours"]:
        metrics["shifts"][str(float(shift))] = {
            "dual_minus_availability": {
                "nll_per_order": base_delta if shift == 0 else shift_delta,
                "nll_patient_bootstrap_95ci": [-0.01, upper],
            }
        }
    decision = _validation_decision(metrics, config)
    assert decision["advance_dual_clock"] is advance
    assert decision["test_split_evaluated"] is False


def test_history_models_are_validation_only_digest_bound_and_reproducible(tmp_path, monkeypatch):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    cohort, history, cohort_digest, history_digest = _artifacts(tmp_path)
    config, config_digest = load_history_model_config(ROOT / "configs/clinical_history_models.yaml")
    config = dict(config, bootstrap_replicates=10)
    outputs = []
    for name in ("first", "second"):
        output = tmp_path / name
        output.mkdir()
        manifest = run_clinical_history_models(
            cohort,
            history,
            output,
            config,
            config_digest,
            cohort_digest,
            history_digest,
            "b" * 40,
        )
        assert manifest["status"] == "complete"
        assert manifest["test_split_evaluated"] is False
        assert manifest["feature_dimension"] == 8
        assert manifest["gpu_used"] is False and manifest["database_write"] is False
        assert all(path.stat().st_mode & 0o077 == 0 for path in output.iterdir())
        decision = json.loads((output / "validation_decision.json").read_text())
        assert decision["rule_frozen_before_test"] is True
        assert decision["test_split_evaluated"] is False
        predictions = json.loads((output / "validation_predictions.json").read_text())
        assert {row["order_id"] for row in predictions} == {
            f"string:order-{index}" for index in range(16, 20)
        }
        outputs.append(output)
    for filename in (
        "models.json",
        "validation_metrics.json",
        "validation_decision.json",
        "validation_predictions.json",
    ):
        assert (outputs[0] / filename).read_bytes() == (outputs[1] / filename).read_bytes()

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
        "clinical-history-models",
        tmp_path / "job",
        cohort_dir=cohort,
        history_dir=history,
        history_model_config=ROOT / "configs/clinical_history_models.yaml",
    )
    export = next(item for item in command if item.startswith("--export="))
    assert "IES_HISTORY_MODEL_CONFIG_SHA256=" in export
    assert f"IES_COHORT_MANIFEST_SHA256={cohort_digest}" in export
    assert f"IES_HISTORY_MANIFEST_SHA256={history_digest}" in export
    assert "--cpus-per-task=2" in command and "--mem=4096M" in command
    assert str(server.ROOT / "slurm/clinical_history_models.sbatch") in command


def test_test_partition_labels_and_histories_do_not_change_validation_outputs(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    cohort, history, cohort_digest, history_digest = _artifacts(tmp_path)
    config, config_digest = load_history_model_config(ROOT / "configs/clinical_history_models.yaml")
    config = dict(config, bootstrap_replicates=10)

    def run(name):
        output = tmp_path / name
        output.mkdir()
        run_clinical_history_models(
            cohort, history, output, config, config_digest, cohort_digest, history_digest, "c" * 40
        )
        return {
            filename: (output / filename).read_bytes()
            for filename in (
                "models.json",
                "validation_metrics.json",
                "validation_decision.json",
                "validation_predictions.json",
            )
        }

    original = run("original")
    rows = pq.read_table(cohort / "cohort.parquet").to_pylist()
    test_orders = {row["order_id"] for row in rows if row["split"] == "test"}
    for row in rows:
        if row["order_id"] in test_orders:
            row.update(duration_hours=float("nan"), cause=-99)
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), cohort / "cohort.parquet")
    manifest = json.loads((cohort / "manifest.json").read_text())
    manifest["artifacts_sha256"]["cohort.parquet"] = sha256(cohort / "cohort.parquet")
    write_json(cohort / "manifest.json", manifest)
    cohort_digest = sha256(cohort / "manifest.json")

    histories = pq.read_table(history / "history.parquet").to_pylist()
    for row in histories:
        if row["index_order_id"] in test_orders:
            row.update(occurrence_lag_hours=float("nan"), availability_lag_hours=float("nan"))
    pq.write_table(
        pa.Table.from_pylist(histories, schema=HISTORY_SCHEMA), history / "history.parquet"
    )
    manifest = json.loads((history / "manifest.json").read_text())
    manifest["cohort_manifest_sha256"] = cohort_digest
    manifest["artifacts_sha256"]["history.parquet"] = sha256(history / "history.parquet")
    write_json(history / "manifest.json", manifest)
    history_digest = sha256(history / "manifest.json")
    assert run("changed-test-only") == original
