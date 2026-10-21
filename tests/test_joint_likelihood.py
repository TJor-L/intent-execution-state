import json

import numpy as np
import pytest
import yaml

from ies.cli import parser
from ies.joint_likelihood import (
    JointObjective,
    fit_likelihood,
    minimize_objective,
    select_likelihood,
    select_tree_all,
)
from ies.joint_likelihood_demo import run_demo
from ies.joint_observation import (
    PrefixCounts,
    fit_independent,
    fit_joint,
    joint_law,
    projection,
    sample_observed,
)
from ies.joint_shrinkage import split_counts
from ies.joint_stress import observation_kernel, sample_stopped, stress_law


def _example(seed=11):
    observed = sample_observed(joint_law("synchronized"), [0, 0.5, 0.3, 0.2], 300, seed)
    reference = fit_independent(observed)
    return observed, reference


def test_objective_gradient_and_hessian_match_directional_differences():
    observed, reference = _example()
    objective = JointObjective(observed, reference, "reveal", 0.5)
    p = 0.6 * reference + 0.4 * np.full(225, 1 / 225)
    value, gradient, hessian = objective.evaluate(p, hessian=True)
    rng = np.random.default_rng(2)
    for _ in range(4):
        direction = rng.normal(size=225)
        direction -= direction.mean()
        direction /= np.max(np.abs(direction))
        epsilon = 1e-7
        plus, plus_gradient, _ = objective.evaluate(p + epsilon * direction)
        minus, minus_gradient, _ = objective.evaluate(p - epsilon * direction)
        assert (plus - minus) / (2 * epsilon) == pytest.approx(
            gradient @ direction, rel=1e-5, abs=1e-6
        )
        np.testing.assert_allclose(
            (plus_gradient - minus_gradient) / (2 * epsilon),
            hessian @ direction,
            rtol=2e-5,
            atol=1e-4,
        )
    assert np.isfinite(value)
    np.testing.assert_allclose(hessian, hessian.T, atol=1e-10)
    assert np.linalg.eigvalsh(hessian).min() > 0


def test_convexity_on_simplex():
    observed, reference = _example()
    objective = JointObjective(observed, reference, "reveal", 0.5)
    rng = np.random.default_rng(8)
    p, q = rng.dirichlet(np.ones(225), size=2)
    fp, _, _ = objective.evaluate(p)
    fq, _, _ = objective.evaluate(q)
    fm, _, _ = objective.evaluate(0.3 * p + 0.7 * q)
    assert fm <= 0.3 * fp + 0.7 * fq


def test_full_observation_solution_and_dual_gap_bound():
    observed = sample_observed(joint_law("opposed"), [0, 0, 0, 1], 120, 17)
    reference = joint_law("independent")
    objective = JointObjective(observed, reference, "reveal", 0, prior_mass=2)
    optimum = (observed.counts[3][projection(3)] + 2 * reference) / 122
    optimum_value, _, _ = objective.evaluate(optimum)
    p, diagnostic = minimize_objective(objective)
    assert diagnostic["converged"]
    np.testing.assert_allclose(p, optimum, rtol=1e-6, atol=1e-10)
    assert diagnostic["final_objective"] - optimum_value <= diagnostic["simplex_dual_gap"] + 1e-12
    assert (
        np.max(np.abs(p.reshape(15, 15).sum(axis=1) - reference.reshape(15, 15).sum(axis=1))) > 0.01
    )


@pytest.mark.parametrize("group", ["global", "reveal"])
def test_penalized_solver_positive_normalized_decreasing_and_certified(group):
    observed, reference = _example()
    objective = JointObjective(observed, reference, group, 0.5)
    p, diagnostic = minimize_objective(objective)
    assert diagnostic["converged"], diagnostic
    assert diagnostic["simplex_dual_gap"] <= 1e-7
    assert np.min(p) > 0
    assert p.sum() == pytest.approx(1)
    assert np.max(np.diff(diagnostic["objective_trace"])) <= 2e-12
    assert diagnostic["final_objective"] <= diagnostic["initial_objective"]


def test_unpenalized_censored_solution_agrees_with_em():
    observed, _ = _example()
    reference = np.full(225, 1 / 225)
    objective = JointObjective(observed, reference, "reveal", 0)
    p, diagnostic = minimize_objective(objective)
    em = fit_joint(observed, steps=1000)
    assert diagnostic["converged"]
    np.testing.assert_allclose(p, em, atol=1e-7)


def test_no_observed_information_retains_reference_without_iteration():
    count = tuple(np.zeros(projection(c).max() + 1, dtype=int) for c in range(4))
    count[0][0] = 100
    objective = JointObjective(PrefixCounts(count), joint_law("independent"), "reveal", 1)
    p, diagnostic = minimize_objective(objective)
    np.testing.assert_array_equal(p, objective.reference)
    assert diagnostic["converged"] and diagnostic["iterations"] == 0


def test_solver_limits_do_not_claim_success():
    observed, reference = _example()
    _, diagnostic = minimize_objective(
        JointObjective(observed, reference, "reveal", 0.5), max_steps=1
    )
    assert not diagnostic["converged"]
    assert diagnostic["status"] == "iteration_limit"
    assert diagnostic["simplex_dual_gap"] > diagnostic["tolerance"]


def test_invalid_inputs_and_latent_training_labels_rejected():
    observed, reference = _example()
    for params in ({"strength": -1}, {"strength": float("nan")}, {"strength": 0.5, "smoothing": 0}):
        with pytest.raises(ValueError):
            JointObjective(observed, reference, "reveal", **params)
    with pytest.raises(ValueError):
        JointObjective(observed, joint_law("synchronized"), "reveal", 1)
    with pytest.raises(TypeError):
        fit_likelihood(observed, "reveal", 1, latent=joint_law("synchronized"))


def test_predictable_stopping_and_no_tail_support_are_numerically_supported():
    for policy in ("adaptive_past", "no_tail_support"):
        observed = sample_stopped(
            stress_law("lagged_dependence"), observation_kernel(policy), 256, 31
        )
        p, diagnostic = fit_likelihood(observed, "reveal", 0.5)
        assert diagnostic["converged"]
        assert not diagnostic["marginals_fixed"]
        assert p.sum() == pytest.approx(1)
        if policy == "no_tail_support":
            assert diagnostic["observed_fraction_by_depth"][-1] == 0


def test_entity_exchange_equivariance():
    observed, reference = _example()
    swap = np.arange(225).reshape(15, 15).T.ravel()
    swapped = []
    for c in range(4):
        index = projection(c)
        reps = np.unique(index, return_index=True)[1]
        swapped.append(np.bincount(index[swap[reps]], weights=observed.counts[c]).astype(int))
    p, first = minimize_objective(JointObjective(observed, reference, "reveal", 0.5))
    q, second = minimize_objective(
        JointObjective(PrefixCounts(tuple(swapped)), reference[swap], "reveal", 0.5)
    )
    assert first["converged"] and second["converged"]
    np.testing.assert_allclose(q, p[swap], atol=1e-8)


def test_cv_fits_reference_inside_each_training_fold(monkeypatch):
    observed, _ = _example()
    seen = []
    original = fit_independent

    def record(data, steps=300):
        seen.append(data)
        return original(data, steps)

    monkeypatch.setattr("ies.joint_likelihood.fit_independent", record)
    prediction, diagnostic = select_likelihood(observed, "reveal", 99)
    left, right = split_counts(observed, 99)
    for actual, expected in zip(seen[:2], (left, right), strict=True):
        for a, b in zip(actual.counts, expected.counts, strict=True):
            np.testing.assert_array_equal(a, b)
    assert all(item.patients < observed.patients for item in seen[:2])
    assert seen[-1].patients == observed.patients
    assert diagnostic["strengths"] == [None, 0.25, 1, 4]
    assert len(diagnostic["solver_fits"]) == 6
    assert all(fit["dual_gap"] <= 1e-7 for fit in diagnostic["solver_fits"])
    assert sum(diagnostic["fold_patients"]) == observed.patients
    assert prediction.sum() == pytest.approx(1)


def test_tree_all_uses_same_patient_budget_and_fixed_grid():
    observed, _ = _example()
    prediction, diagnostic = select_tree_all(observed, 99)
    assert diagnostic["candidates"] == 15
    assert sum(diagnostic["fold_patients"]) == observed.patients
    assert diagnostic["selected_strength"] in (1, 10, 100)
    assert prediction.sum() == pytest.approx(1)


def test_uncertified_solver_cannot_silently_enter_cv(monkeypatch):
    observed, reference = _example()
    monkeypatch.setattr(
        "ies.joint_likelihood.minimize_objective",
        lambda objective: (reference, dict(converged=False, status="iteration_limit")),
    )
    with pytest.raises(RuntimeError, match="certify convergence"):
        select_likelihood(observed, "reveal", 20)


def _small_config(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            dict(schema_version=1, data_class="synthetic", seeds=[1], patients=[32], em_steps=2)
        )
    )
    return config


def test_runner_provenance_determinism_and_clinical_input_rejection(tmp_path, monkeypatch):
    monkeypatch.setattr("ies.joint_likelihood_demo.SCENARIOS", ("opposed",))
    monkeypatch.setattr("ies.joint_likelihood_demo.POLICIES", ("independent_short",))
    config = _small_config(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    assert run_demo(config, a)["cases"] == 1
    run_demo(config, b)
    for name in ("metrics.json", "models.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    manifest = json.loads((a / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert not manifest["novel_algorithm_established"]
    assert not manifest["clinical_inputs_used"]
    with pytest.raises(FileExistsError):
        run_demo(config, a)
    with pytest.raises(SystemExit):
        parser().parse_args(["joint-likelihood-demo", "--data-root", "/restricted"])


def test_solver_failure_is_recorded_without_exception_payload(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("do-not-persist")

    monkeypatch.setattr("ies.joint_likelihood_demo.select_likelihood", fail)
    config = _small_config(tmp_path)
    with pytest.raises(RuntimeError):
        run_demo(config, tmp_path / "failed")
    content = (tmp_path / "failed" / "manifest.json").read_text()
    assert "do-not-persist" not in content
    assert json.loads(content)["status"] == "failed"
