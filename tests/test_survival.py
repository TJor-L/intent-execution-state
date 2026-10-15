import copy

import numpy as np
import pytest

from ies.evaluation.metrics import evaluate
from ies.losses.competing_risks import negative_log_likelihood
from ies.models.age_stratified import evaluate_age_stratified, fit_age_stratified
from ies.models.piecewise import cumulative_incidence, fit_baseline
from ies.preprocessing.cohort import build_cohort


def test_likelihood_matches_hand_calculation_with_partial_censor_and_edge():
    hazards = [[0.2, 0.1, 0.05], [0.1, 0.05, 0.01]]
    actual = negative_log_likelihood([1, 3, 4, 2, 0.5], [1, 2, 0, 3, 0], hazards, [0, 2, 4])
    expected = [
        0.35 - np.log(0.2),
        0.7 + 0.16 - np.log(0.05),
        0.7 + 0.32,
        0.7 - np.log(0.05),
        0.175,
    ]
    np.testing.assert_allclose(actual, expected)


@pytest.mark.parametrize(
    "duration,cause,hazards,edges",
    [
        ([0], [0], [[0.1]], [0, 1]),
        ([2], [0], [[0.1]], [0, 1]),
        ([0.5], [2], [[0.1]], [0, 1]),
        ([0.5], [0], [[0.0]], [0, 1]),
        ([0.5], [0], [[float("nan")]], [0, 1]),
        ([0.5], [0], [[0.1]], [0, 0]),
    ],
)
def test_invalid_likelihood_inputs(duration, cause, hazards, edges):
    with pytest.raises(ValueError):
        negative_log_likelihood(duration, cause, hazards, edges)


def test_fit_counts_and_censored_exposure():
    cohort = [
        {"split": "train", "patient_id": "a", "duration": 1.0, "cause": 1},
        {"split": "train", "patient_id": "b", "duration": 2.0, "cause": 0},
    ]
    model = fit_baseline(cohort, [0, 2])
    np.testing.assert_allclose(model["hazards_per_hour"], [[1.5 / 4, 0.5 / 4, 0.5 / 4]])


def test_test_labels_cannot_change_training_and_cif_is_probability(events):
    cohort = build_cohort(events, 7)
    model = fit_baseline(cohort, [0, 2, 6, 24])
    changed = [dict(r, cause=0, duration=24) if r["split"] != "train" else r for r in cohort]
    assert fit_baseline(changed, [0, 2, 6, 24]) == model
    curve = cumulative_incidence(model)["curve"]
    cif = np.array([r["cif"] for r in curve])
    survival = np.array([r["survival"] for r in curve])
    np.testing.assert_allclose(cif.sum(axis=1) + survival, 1)
    assert (np.diff(cif, axis=0) >= 0).all()
    assert (np.diff(survival) <= 0).all()


def test_bootstrap_is_seeded_finite_and_rejects_patient_overlap(events):
    cohort = build_cohort(events, 7)
    model = fit_baseline(cohort, [0, 2, 6, 24])
    result, predictions = evaluate(cohort, model, bootstrap=30, seed=7)
    assert evaluate(cohort, model, bootstrap=30, seed=7) == (result, predictions)
    assert np.isfinite(result["nll_per_order"])
    assert len(predictions["orders"]) == result["n_orders"]
    leaking = copy.deepcopy(model)
    leaking["train_patients"].append(next(r["patient_id"] for r in cohort if r["split"] == "test"))
    with pytest.raises(ValueError, match="overlap"):
        evaluate(cohort, leaking)


def test_fixed_age_baseline_uses_training_only_and_global_fallback():
    cohort = [
        {
            "split": "train",
            "patient_id": "a",
            "order_id": "1",
            "duration": 1.0,
            "cause": 1,
            "age_years_at_order": 30,
        },
        {
            "split": "train",
            "patient_id": "b",
            "order_id": "2",
            "duration": 2.0,
            "cause": 0,
            "age_years_at_order": 70,
        },
        {
            "split": "validation",
            "patient_id": "c",
            "order_id": "3",
            "duration": 3.0,
            "cause": 2,
            "age_years_at_order": 50,
        },
    ]
    model = fit_age_stratified(cohort, [0, 2, 6, 24])
    assert "45-64" not in model["age_bands"]
    metrics, predictions = evaluate_age_stratified(
        cohort, model, split="validation", bootstrap=10, seed=7
    )
    assert np.isfinite(metrics["nll_per_order"])
    assert predictions["orders"][0]["order_id"] == "3"
