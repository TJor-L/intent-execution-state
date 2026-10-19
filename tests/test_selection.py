import copy
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from ies import selection_cv as cv
from ies.models.history_piecewise import individual_nll
from ies.models.survival_tree import fit_tree, predict_tree
from ies.selection_scores import cause_losses, coherent_rows, patient_weights
from ies.workflow_diagnostic import generate_workflow_case


def test_coherent_bounds_against_exhaustive_completions():
    p = np.array([[0.1, 0.4, 0.7], [0.2, 0.3, 0.8], [0.1, 0.2, 0.5]])
    q = np.array([[0.2, 0.3, 0.6], [0.1, 0.4, 0.6], [0.2, 0.3, 0.4]])
    weights = np.array([0.2, 0.3, 0.5])
    bounds = coherent_rows(p, [1, 2, 4], [0, 1, 2], [1, 2, 4], weights, q)
    feasible = [
        [y for y in product((0, 1), repeat=3) if y[0] == 0 and y[1] <= y[2]],
        [(0, 1, 1)],
        [(0, 0, 0)],
    ]
    for i, completions in enumerate(feasible):
        scores = [weights @ ((p[i] - y) ** 2 - (q[i] - y) ** 2) for y in np.array(completions)]
        np.testing.assert_allclose(bounds[i], [min(scores), max(scores)])
    np.testing.assert_array_equal(coherent_rows(p, [0.5] * 3, [0] * 3, [1, 2, 4], weights, p), 0)


def test_coherent_comparison_can_be_tighter_than_separate_horizons():
    p, q = np.array([[0.1, 0.9]]), np.array([[0.4, 0.6]])
    joint = coherent_rows(p, [0.5], [0], [1, 4], [0.5, 0.5], q)[0]
    separate = np.mean(
        [
            coherent_rows(p[:, j : j + 1], [0.5], [0], [h], [1], q[:, j : j + 1])[0]
            for j, h in enumerate([1, 4])
        ],
        axis=0,
    )
    assert joint[0] >= separate[0] - 1e-12
    assert joint[1] < separate[1]


def test_patient_weighting_and_cause_decomposition():
    np.testing.assert_allclose(patient_weights(["a", "a", "b"]), [0.25, 0.25, 0.5])
    rates = np.full((4, 2, 3), 0.2)
    times, causes, edges = [1, 2, 4, 3], [1, 2, 3, 0], [0, 2, 4]
    np.testing.assert_allclose(
        cause_losses(times, causes, rates, edges).sum(axis=1),
        individual_nll(times, causes, rates, edges),
    )


def test_worst_completion_objective_is_not_a_proper_probability_score():
    # With every label unknown, the worst squared error favors .5 irrespective of
    # the latent event probability. R001 compares this policy; it does not endorse it.
    bounds = coherent_rows([[0.1], [0.5], [0.9]], [0.5] * 3, [0] * 3, [4], [1])
    np.testing.assert_allclose(bounds[:, 1], [0.81, 0.25, 0.81])


@pytest.mark.parametrize(
    "p,t,c,h,w",
    [
        ([[0.5, 0.2]], [1], [0], [1, 4], [0.5, 0.5]),
        ([[float("nan")]], [1], [0], [4], [1]),
        ([[0.2, 0.4]], [1], [0], [4, 1], [0.5, 0.5]),
        ([[0.2, 0.4]], [1], [0], [1, 4], [-1, 2]),
        ([[0.2]], [1], [-1], [4], [1]),
    ],
)
def test_invalid_scores(p, t, c, h, w):
    with pytest.raises(ValueError):
        coherent_rows(p, t, c, h, w)


def test_tree_recovers_nonlinear_partition_and_intercept():
    x = np.repeat([0.0, 1.0, 2.0], 30)[:, None]
    times = np.repeat([1.0, 10.0, 1.0], 30)
    patients = [f"generated-{i}" for i in range(90)]
    args = (x, times, [1] * 90, patients, [0, 24])
    model = fit_tree(*args, min_leaf_patients=10)
    assert model == fit_tree(*args, min_leaf_patients=10)
    np.testing.assert_allclose(
        predict_tree(model, [[0], [1], [2]])[:, 0, 0], [30.5 / 31, 30.5 / 301, 30.5 / 31]
    )
    assert "generated-" not in str(model)
    intercept = fit_tree(np.zeros((90, 0)), times, [1] * 90, patients, [0, 24])
    np.testing.assert_allclose(
        predict_tree(intercept, np.zeros((1, 0)))[0, 0], [90.5 / 361, 0.5 / 361, 0.5 / 361]
    )


@pytest.fixture
def inputs():
    config, _ = cv.load_config(Path("configs/workflow_selection.yaml"))
    config.update(seeds=[cv.SEEDS[0]], bootstrap_replicates=20)
    cohort, history = generate_workflow_case(seed=312, scenario="pooled_timing_signal", patients=40)
    for i, row in enumerate(cohort):
        if i % 3 == 0 and row["duration"] > 0.5:
            row.update(duration=0.5, cause=0)
    return cohort, history, config


def test_nested_reproducibility_and_private_tables(inputs):
    cohort, history, config = inputs
    before = copy.deepcopy(inputs)
    result = cv.run_selection_cv(cohort, history, config, data_class="synthetic")
    assert result == cv.run_selection_cv(
        list(reversed(cohort)), history, config, data_class="synthetic"
    )
    assert inputs == before
    report, models = result
    assert len(report["seeds"][0]["candidates"]) == 8
    assert report["validation_split_evaluated"] is report["test_split_evaluated"] is False
    assert len(models["models"]) == 5
    table = cv.paper_tables(report)
    for row in cohort:
        assert row["patient_id"] not in str(result) + table
    summary = cv.qualitative_summary(report)
    assert "n_patients" not in str(summary)
    assert "patient_mean_nll_difference" not in str(summary)


def test_outer_outcomes_cannot_enter_inner_selection(inputs, monkeypatch):
    cohort, history, config = inputs
    ordered = sorted(cohort, key=lambda r: (r["patient_id"], r["order_id"]))
    folds = cv.group_folds([r["patient_id"] for r in ordered], 5, cv.SEEDS[0], "outer")
    held_out = {r["patient_id"] for r, fold in zip(ordered, folds, strict=True) if fold == 0}
    original = cv.select_candidates
    calls = []

    def capture(rows, *args):
        if len(calls) % 5 == 0:
            assert not held_out & {r["patient_id"] for r in rows}
        result = original(rows, *args)
        calls.append(result)
        return result

    monkeypatch.setattr(cv, "select_candidates", capture)
    cv.run_selection_cv(cohort, history, config, data_class="synthetic")
    altered = copy.deepcopy(cohort)
    for row in altered:
        if row["patient_id"] in held_out:
            row.update(duration=24.0, cause=0)
    cv.run_selection_cv(altered, history, config, data_class="synthetic")
    assert calls[0] == calls[5]


def test_group_folds_and_scope(inputs):
    patients = [f"patient-{i}" for i in range(30) for _ in range(3)]
    folds = cv.group_folds(patients, 5, cv.SEEDS[0], "outer").reshape(30, 3)
    assert np.all(folds == folds[:, :1])
    cohort, history, config = inputs
    cohort[0]["split"] = "validation"
    with pytest.raises(ValueError):
        cv.run_selection_cv(cohort, history, config, data_class="synthetic")

    cohort[0]["split"] = "train"
    history["outside-cohort"] = []
    with pytest.raises(ValueError):
        cv.run_selection_cv(cohort, history, config, data_class="synthetic")


@pytest.mark.parametrize("regime", ["administrative_only", "feature_dependent_censoring"])
def test_generated_oracle_contains_complete_truth_and_rejects_clinical(inputs, regime):
    from ies.selection_demo import generate_case, oracle_check

    config = inputs[2]
    cohort, history, full = generate_case(45, "time_varying", regime, patients=40)
    report, models = cv.run_selection_cv(cohort, history, config, data_class="synthetic")
    results = oracle_check(cohort, history, full, config, report, models)
    assert all(row["truth_within_bounds"] for row in results)
    if regime == "administrative_only":
        np.testing.assert_allclose(
            results[0]["completion_bounds"], results[0]["oracle_policy_difference"]
        )
    report["data_class"] = "restricted_aggregate"
    with pytest.raises(ValueError, match="synthetic only"):
        oracle_check(cohort, history, full, config, report, models)


def test_selection_configuration_is_fixed(inputs):
    config = inputs[2]
    config["horizon_weights"] = [1.0, 0.0, 0.0, 0.0]
    with pytest.raises(ValueError):
        cv.validate_config(config)
    config["horizon_weights"] = [0.25] * 4
    config["scales_hours"][0] = True
    with pytest.raises(ValueError):
        cv.validate_config(config)
