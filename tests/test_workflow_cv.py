"""Generated mechanisms, patient isolation and fixed W001 development controls."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import yaml

from ies import workflow_cv as workflow
from ies.clinical_baseline import ClinicalBaselineError
from ies.workflow_diagnostic import generate_workflow_case

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workflow_config():
    value, _ = workflow.load_workflow_config(ROOT / "configs/workflow_cv.yaml")
    return dict(value, bootstrap_replicates=30)


def test_workflow_controls_separate_volume_pooled_recency_and_type_recency():
    rows = [
        dict(event_kind=kind, occurrence_lag_hours=lag, availability_lag_hours=lag)
        for kind, lag in [(0, 1.0), (0, 3.0), (1, 12.0), (1, 18.0)]
    ]
    swapped = [dict(row, event_kind=1 - row["event_kind"]) for row in rows]
    first = workflow.encode_workflow(rows, [1, 4, 12, 24])
    second = workflow.encode_workflow(swapped, [1, 4, 12, 24])
    assert {m: len(v) for m, v in first.items()} == workflow.DIMENSIONS
    for mode in ("intercept", "counts", "pooled_timing"):
        np.testing.assert_array_equal(first[mode], second[mode])
    assert not np.allclose(first["typed_timing"], second["typed_timing"])
    np.testing.assert_allclose(
        first["pooled_timing"][2:], first["typed_timing"][2:6] + first["typed_timing"][6:]
    )
    for value in workflow.encode_workflow([], [1, 4, 12, 24]).values():
        assert not value.any()


@pytest.mark.parametrize(
    "changes",
    [
        dict(availability_lag_hours=-1.0),
        dict(availability_lag_hours=5.0),
        dict(occurrence_lag_hours=0.0),
        dict(occurrence_lag_hours=25.0),
        dict(event_kind=2),
        dict(availability_lag_hours=float("nan")),
    ],
)
def test_workflow_encoder_rejects_future_invalid_or_out_of_window_events(changes):
    row = dict(event_kind=0, occurrence_lag_hours=4.0, availability_lag_hours=2.0)
    row.update(changes)
    with pytest.raises(ValueError):
        workflow.encode_workflow([row], [1, 4, 12, 24])


def test_folds_are_patient_grouped_order_invariant_and_balanced():
    patients = [f"generated-{i}" for i in range(23)]
    folds = workflow.patient_folds(patients * 2, 5, 7)
    assert folds == workflow.patient_folds(patients[::-1], 5, 7)
    sizes = [list(folds.values()).count(i) for i in range(5)]
    assert max(sizes) - min(sizes) <= 1


def test_crossfit_fits_each_model_on_only_other_patients(workflow_config, monkeypatch):
    cohort, grouped = generate_workflow_case(31, "type_timing_signal", patients=60)
    assignment = workflow.patient_folds(
        [r["patient_id"] for r in cohort], 5, workflow_config["seed"]
    )
    original = workflow.fit_history_model
    calls = []

    def fit(rows, features, *args, **kwargs):
        fold = len(calls) // len(workflow.MODELS)
        assert {r["patient_id"] for r in rows} == {p for p, f in assignment.items() if f != fold}
        fitted = original(rows, features, *args, **kwargs)
        if fitted["feature_dimension"]:
            expected = np.stack([features[r["order_id"]] for r in rows]).mean(axis=0)
            np.testing.assert_allclose(fitted["feature_mean"], expected)
        calls.append(fitted["mode"])
        return fitted

    monkeypatch.setattr(workflow, "fit_history_model", fit)
    report, models = workflow.workflow_cross_validation(
        cohort, grouped, workflow_config, data_class="synthetic"
    )
    assert calls == list(workflow.MODELS) * 5
    assert not report["validation_split_evaluated"] and not report["test_split_evaluated"]
    assert sum(f["evaluation_orders"] for f in report["folds"]) == len(cohort)
    assert report["clinical_advancement_decision"] == "not_applicable"
    assert not report["automatic_test_or_gpu"]
    assert "generated-patient" not in str(models)
    calls.clear()
    reordered, _ = workflow.workflow_cross_validation(
        cohort[::-1], grouped, workflow_config, data_class="synthetic"
    )
    assert reordered == report


def test_engine_rejects_original_validation_and_test_records(workflow_config):
    cohort, grouped = generate_workflow_case(7, "null", patients=40)
    for split in ("validation", "test"):
        changed = deepcopy(cohort)
        changed[0]["split"] = split
        with pytest.raises(ValueError, match="training record"):
            workflow.workflow_cross_validation(
                changed, grouped, workflow_config, data_class="synthetic"
            )


def test_conditional_cluster_bootstrap_is_paired_and_order_weighted():
    rows = [{"patient_id": p} for p in ("a", "a", "b")]
    one = np.array([1.0, 3.0, 10.0])
    actual = workflow.paired_patient_intervals(rows, {"one": one, "delta": one - one - 0.5}, 100, 9)
    draws = np.random.default_rng(9).integers(2, size=(100, 2))
    expected = [
        (sum(4 if p == 0 else 10 for p in draw) / sum(2 if p == 0 else 1 for p in draw))
        for draw in draws
    ]
    np.testing.assert_allclose(actual["one"], np.quantile(expected, [0.025, 0.975]))
    np.testing.assert_allclose(actual["delta"], [-0.5, -0.5])


@pytest.mark.parametrize(
    "key,value",
    [
        ("evaluation_scope", "test"),
        ("folds", 10),
        ("ridge", float("nan")),
        ("scales_hours", [2.0, 4.0, 12.0, 24.0]),
        ("max_iterations", 1001),
        ("minimum_improved_folds", True),
        ("seed", -1),
        ("schema_version", True),
    ],
)
def test_config_rejects_unplanned_scope_and_invalid_values(tmp_path, workflow_config, key, value):
    workflow_config[key] = value
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(workflow_config))
    with pytest.raises(ClinicalBaselineError, match="invalid_workflow_config"):
        workflow.load_workflow_config(path)


def test_generated_type_signal_is_learnable_without_clock_differences(workflow_config):
    cohort, grouped = generate_workflow_case(20261019, "type_timing_signal")
    assert all(
        r["occurrence_lag_hours"] == r["availability_lag_hours"]
        for events in grouped.values()
        for r in events
    )
    assert any(r["cause"] == 0 for r in cohort)
    report, _ = workflow.workflow_cross_validation(
        cohort, grouped, workflow_config, data_class="synthetic"
    )
    assert report["metrics"]["typed_minus_pooled"]["nll_per_order"] < -0.05
    assert report["typed_timing_development_support"]


def test_absent_terminal_causes_do_not_require_new_labels_or_fail_a_valid_fold(workflow_config):
    cohort, grouped = generate_workflow_case(31, "null", patients=60)
    # Generated independent terminal clocks now act only as censoring clocks.
    # No clinical labels are altered; this fixture checks an absent competing cause.
    for row in cohort:
        if row["cause"] in (2, 3):
            row["cause"] = 0
    report, models = workflow.workflow_cross_validation(
        cohort, grouped, workflow_config, data_class="synthetic"
    )
    for fold in report["folds"]:
        assert fold["training_outcome_counts"]["1"] > 0
        assert fold["training_outcome_counts"]["2"] == fold["training_outcome_counts"]["3"] == 0
    assert all(np.isfinite(v["nll_per_order"]) for v in report["metrics"].values())
    assert all(
        m["optimization_converged"] for f in models["fold_models"] for m in f["models"].values()
    )
