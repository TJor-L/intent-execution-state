"""Analytic and exhaustive generated checks for frozen probability diagnostics."""

import copy
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from ies import workflow_diagnostics as diagnostic
from ies.workflow_cv import load_workflow_config, workflow_cross_validation
from ies.workflow_diagnostic import generate_workflow_case


def test_competing_risk_probabilities_match_closed_form_and_conserve_mass():
    rates = np.tile([0.2, 0.1, 0.1], (2, 3, 1))
    result = diagnostic.cumulative_risks(rates, [0, 1, 4, 24], [0, 1, 3, 24])
    for j, time in enumerate([0, 1, 3, 24]):
        expected = (1 - np.exp(-0.4 * time)) * np.array([0.5, 0.25, 0.25])
        np.testing.assert_allclose(result[:, j], np.tile(expected, (2, 1)))
        np.testing.assert_allclose(result[:, j].sum(axis=1) + np.exp(-0.4 * time), 1)
    assert (np.diff(result, axis=1) >= 0).all()
    # Treating competing terminal events as censoring would incorrectly predict this.
    assert result[0, -1, 0] < 1 - np.exp(-0.2 * 24)


def test_piecewise_probabilities_and_zero_hazards():
    rates = np.array([[[0, 0, 0], [0.2, 0.3, 0.5]]])
    result = diagnostic.cumulative_risks(rates, [0, 2, 24], [1, 2, 3])
    np.testing.assert_allclose(result[0, :2], 0)
    np.testing.assert_allclose(result[0, 2], (1 - np.exp(-1)) * np.array([0.2, 0.3, 0.5]))


def test_known_terminal_outcomes_and_horizon_ties_are_not_early_censors():
    target, unknown = diagnostic.execution_targets([1, 1, 1, 4, 5, 4], [1, 2, 0, 0, 1, 1], 4)
    np.testing.assert_array_equal(target, [1, 0, 0, 0, 0, 1])
    np.testing.assert_array_equal(unknown, [False, False, True, False, False, False])


@pytest.mark.parametrize("paired", [False, True])
def test_completion_bounds_equal_exhaustive_binary_completions(paired):
    prediction = np.array([0.1, 0.8, 0.4, 0.95, 0.2])
    reference = np.array([0.7, 0.6, 0.3, 0.85, 0.9]) if paired else None
    target = np.array([1, 0, 0, 0, 0])
    unknown = np.array([False, False, True, True, True])
    possibilities = []
    for missing in product([0, 1], repeat=3):
        complete = target.copy()
        complete[unknown] = missing
        losses = (prediction - complete) ** 2
        if paired:
            losses -= (reference - complete) ** 2
        possibilities.append(losses.mean())
    bounds = diagnostic.squared_error_bounds(prediction, target, unknown, reference)
    np.testing.assert_allclose(bounds, [min(possibilities), max(possibilities)])


def test_paired_bounds_use_one_common_unknown_outcome_and_collapse_when_observed():
    unknown = np.array([True, True])
    predicted = np.array([0.2, 0.8])
    assert diagnostic.squared_error_bounds(predicted, [0, 0], unknown, predicted) == [0, 0]
    values = diagnostic.squared_error_bounds(predicted, [0, 1], ~unknown)
    np.testing.assert_allclose(values, [0.04, 0.04])


def test_calibration_bins_handle_endpoints_empty_bins_and_unknown_labels():
    result = diagnostic.probability_summary(
        np.array([0, 0.05, 1.0]), np.array([0, 0, 1]), np.array([False, True, False])
    )
    first, last = result["calibration_bins"][0], result["calibration_bins"][-1]
    assert first["event_fraction_completion_bounds"] == [0, 0.5]
    assert last["event_fraction_completion_bounds"] == [1, 1]
    assert result["calibration_bins"][1]["status"] == "empty"
    assert result["unknown_outcomes"] == 1


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_probabilities_fail(bad):
    with pytest.raises(ValueError):
        diagnostic.squared_error_bounds([bad], [0], np.array([True]))


@pytest.fixture
def frozen():
    config, _ = load_workflow_config(Path("configs/workflow_cv.yaml"))
    config["bootstrap_replicates"] = 20
    cohort, history = generate_workflow_case(411, "pooled_timing_signal", patients=60)
    report, models = workflow_cross_validation(cohort, history, config, data_class="synthetic")
    return cohort, history, config, models, report


def test_replay_is_out_of_fold_reproducible_and_does_not_fit(frozen, monkeypatch):
    original = copy.deepcopy(frozen)

    def forbidden(*args, **kwargs):
        pytest.fail("Frozen diagnostics cannot fit a model")

    monkeypatch.setattr("ies.models.history_piecewise.fit_history_model", forbidden)
    monkeypatch.setattr("ies.workflow_cv.fit_history_model", forbidden)
    result = diagnostic.replay_diagnostics(*frozen, data_class="synthetic")
    reversed_inputs = list(frozen)
    reversed_inputs[0] = list(reversed(reversed_inputs[0]))
    assert diagnostic.replay_diagnostics(*reversed_inputs, data_class="synthetic") == result
    assert frozen == original
    assert not result["model_fitted"] and result["source_replay_verified"]
    assert not result["test_split_evaluated"] and not result["validation_split_evaluated"]
    assert len(result["horizons"]) == 4
    for name, old in frozen[-1]["metrics"].items():
        if name in result["nll_comparisons"]:
            np.testing.assert_allclose(
                result["nll_comparisons"][name]["conditional_patient_bootstrap_95ci"],
                old["conditional_patient_bootstrap_95ci"],
                atol=1e-12,
                rtol=1e-12,
            )
    expected = (
        frozen[-1]["metrics"]["pooled_minus_counts"]["nll_per_order"]
        + frozen[-1]["metrics"]["counts_minus_intercept"]["nll_per_order"]
    )
    assert result["nll_comparisons"]["pooled_minus_intercept"]["mean_difference"] == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    "change",
    ["split", "assignment", "scale", "weights", "fold_loss", "global_loss", "duplicate_fold"],
)
def test_replay_rejects_binding_and_prediction_mismatches(frozen, change):
    cohort, _, _, models, report = frozen
    model = models["fold_models"][0]["models"]["pooled_timing"]
    if change == "split":
        cohort[0]["split"] = "test"
    elif change == "assignment":
        model["train_patient_assignment_sha256"] = "a" * 64
    elif change == "scale":
        model["feature_scale"][0] *= 2
    elif change == "weights":
        model["intercepts_log_rate"][0][0] += 1
    elif change == "fold_loss":
        report["folds"][0]["nll_per_order"]["intercept"] += 1
    elif change == "global_loss":
        report["metrics"]["intercept"]["nll_per_order"] += 1
    else:
        models["fold_models"][0]["fold"] = models["fold_models"][1]["fold"]
    with pytest.raises(ValueError):
        diagnostic.replay_diagnostics(*frozen, data_class="synthetic")
