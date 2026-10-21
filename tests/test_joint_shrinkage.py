import json

import numpy as np
import pytest
import yaml

from ies.cli import parser
from ies.joint_observation import (
    PAIRS,
    PATHS,
    STATES,
    PrefixCounts,
    fit_independent,
    joint_law,
    projection,
    sample_observed,
)
from ies.joint_shrinkage import (
    combine_counts,
    prefix_counts,
    select_tree_shrinkage,
    spectral_fit,
    split_counts,
    tree_basis,
    tree_shrink_fit,
)
from ies.joint_shrinkage_demo import run_demo
from ies.joint_stress import (
    POLICIES,
    SCENARIOS,
    observation_kernel,
    sample_stopped,
    stress_law,
    stress_scores,
)


def test_weighted_tree_basis_is_orthonormal_and_adapted_to_prefix():
    marginal = joint_law("independent").reshape(15, 15).sum(axis=1)
    basis, depths = tree_basis(marginal)
    assert basis.shape == (15, 14)
    assert [int(np.sum(depths == d)) for d in (1, 2, 3)] == [2, 4, 8]
    np.testing.assert_allclose(marginal @ basis, 0, atol=1e-14)
    np.testing.assert_allclose(basis.T @ (marginal[:, None] * basis), np.eye(14), atol=1e-14)
    for depth in (0, 1, 2):
        for prefix in {tuple(row[:depth]) for row in PATHS}:
            mask = np.array([tuple(row[:depth]) == prefix for row in PATHS])
            np.testing.assert_allclose(
                marginal[mask] @ basis[mask][:, depths > depth], 0, atol=1e-14
            )


def test_common_observation_fisher_diagonal_uses_max_reveal_not_product():
    baseline = joint_law("independent")
    marginal = baseline.reshape(15, 15).sum(axis=0)
    basis, depth = tree_basis(marginal)
    features = (basis[PAIRS[:, 0], :, None] * basis[PAIRS[:, 1], None, :]).reshape(225, -1)
    reveals = np.maximum(depth[:, None], depth[None, :]).ravel()
    windows = np.array([0.0, 0.5, 0.3, 0.2])
    information = np.zeros((196, 196))
    for c in range(4):
        index = projection(c)
        mass = np.bincount(index, weights=baseline)
        conditional = np.column_stack(
            [np.bincount(index, weights=baseline * feature) / mass for feature in features.T]
        )
        information += windows[c] * conditional.T @ (mass[:, None] * conditional)
    survival = np.array([windows[d:].sum() for d in reveals])
    np.testing.assert_allclose(information, np.diag(survival), atol=1e-12)
    late = np.flatnonzero(reveals == 3)[0]
    assert information[late, late] == pytest.approx(0.2)
    assert information[late, late] != pytest.approx(0.2**2)


def test_patient_splitting_and_prefix_exposure_are_consistent():
    observed = sample_stopped(
        stress_law("synchronized"), observation_kernel("independent_short"), 500, 1
    )
    left, right = split_counts(observed, 22)
    combined = combine_counts(left, right)
    for original, recovered in zip(observed.counts, combined.counts, strict=True):
        np.testing.assert_array_equal(original, recovered)
    assert prefix_counts(observed, 1).sum() == 500
    assert prefix_counts(observed, 3).sum() == observed.counts[3].sum()
    assert prefix_counts(observed, 2).sum() >= prefix_counts(observed, 3).sum()


@pytest.mark.parametrize("grouping", ["none", "global", "reveal"])
def test_spectral_prediction_preserves_marginals_and_positive_mass(grouping):
    pilot = sample_observed(joint_law("synchronized"), [0, 0.5, 0.3, 0.2], 200, 42)
    observed = sample_observed(joint_law("synchronized"), [0, 0.5, 0.3, 0.2], 300, 43)
    baseline = fit_independent(pilot)
    prediction, diagnostic = spectral_fit(observed, baseline, grouping)
    assert prediction.sum() == pytest.approx(1)
    assert np.min(prediction) > 0
    for axis in (0, 1):
        np.testing.assert_allclose(
            prediction.reshape(15, 15).sum(axis=axis),
            baseline.reshape(15, 15).sum(axis=axis),
            atol=1e-12,
        )
    assert 0 < diagnostic["positivity_contraction"] <= 1
    assert diagnostic["maximum_marginal_error"] < 1e-12


def test_no_supported_tail_interactions_and_empty_observation_fallback():
    baseline = joint_law("independent")
    observed = sample_observed(joint_law("synchronized"), [0, 0.5, 0.5, 0], 1000, 3)
    _, diagnostic = spectral_fit(observed, baseline, "reveal")
    assert diagnostic["observed_patients_by_reveal_depth"][-1] == 0
    assert diagnostic["unsupported_coefficients_nonzero"] == 0
    empty = PrefixCounts(tuple(np.zeros(projection(c).max() + 1, dtype=int) for c in range(4)))
    empty.counts[0][0] = 20
    prediction, _ = spectral_fit(empty, baseline, "reveal")
    np.testing.assert_allclose(prediction, baseline, atol=1e-14)
    np.testing.assert_allclose(tree_shrink_fit(empty, baseline, 10), baseline, atol=1e-14)


def test_invalid_baseline_or_prior_rejected():
    observed = sample_observed(joint_law("independent"), [0, 0, 0, 1], 10, 4)
    with pytest.raises(ValueError):
        spectral_fit(observed, joint_law("synchronized"), "reveal")
    with pytest.raises(ValueError):
        tree_shrink_fit(observed, joint_law("independent"), -1)
    with pytest.raises(ValueError):
        prefix_counts(observed, True)


def test_dirichlet_tree_counts_and_limit_match_direct_recursive_prediction():
    observed = sample_observed(joint_law("opposed"), [0, 0, 0, 1], 100, 6)
    baseline = joint_law("independent")
    prediction = tree_shrink_fit(observed, baseline, 10)
    first_counts = prefix_counts(observed, 1)
    first_base = np.bincount(projection(1), weights=baseline)
    np.testing.assert_allclose(
        np.bincount(projection(1), weights=prediction), (first_counts + 10 * first_base) / 110
    )
    assert prediction.sum() == pytest.approx(1)


def test_cv_uses_only_observed_training_and_fixed_candidate_grid():
    observed = sample_observed(joint_law("opposed"), [0, 0.5, 0.3, 0.2], 100, 9)
    p, metadata = select_tree_shrinkage(observed, joint_law("independent"), 18)
    assert metadata["candidates"] == 15
    assert metadata["selected_joint_weight"] in {0, 0.25, 0.5, 0.75, 1}
    assert p.sum() == pytest.approx(1)
    with pytest.raises(TypeError):
        select_tree_shrinkage(observed, joint_law("independent"), 18, latent=joint_law("opposed"))


def test_stress_laws_and_observation_kernels_are_normalized():
    for scenario in SCENARIOS:
        truth = stress_law(scenario)
        assert truth.sum() == pytest.approx(1)
        assert np.all(truth > 0)
        for policy in POLICIES:
            kernel = observation_kernel(policy)
            np.testing.assert_allclose(kernel.sum(axis=0), 1, atol=1e-14)
            observed = sample_stopped(truth, kernel, 100, 17)
            assert observed.patients == 100
            scores = stress_scores(truth, truth, kernel)
            assert scores["latent_joint_kl"] == pytest.approx(0)
            assert scores["observation_channel_kl"] == pytest.approx(0)


def test_predictable_stopping_is_constant_within_observed_cell():
    kernel = observation_kernel("adaptive_past")
    for c in (1, 2, 3):
        index = projection(c)
        for cell in np.unique(index):
            assert np.ptp(kernel[c, index == cell]) < 1e-14
    future = observation_kernel("informative_future")
    assert max(np.ptp(future[1, projection(1) == cell]) for cell in np.unique(projection(1))) > 0.1


def test_ignorable_and_informative_scores_are_distinguished():
    p, q = stress_law("independent"), stress_law("synchronized")
    for policy in ("full", "independent_short", "adaptive_past"):
        score = stress_scores(p, q, observation_kernel(policy))
        assert score["ignorability_score_excess"] == pytest.approx(score["observation_channel_kl"])
    score = stress_scores(p, q, observation_kernel("informative_future"))
    assert abs(score["ignorability_score_excess"] - score["observation_channel_kl"]) > 1e-4
    assert score["observation_channel_kl"] >= 0


def test_informative_stopping_can_reward_wrong_ignorability_forecast():
    lookup = {tuple(state.ravel()): i for i, state in enumerate(STATES)}
    a, b = lookup[(0, 0, 0, 0, 0, 0)], lookup[(0, 0, 1, 0, 0, 1)]
    truth, wrong = np.zeros(225), np.zeros(225)
    truth[[a, b]], wrong[[a, b]] = [0.5, 0.5], [0.9, 0.1]
    kernel = observation_kernel("full")
    kernel[:, a], kernel[:, b] = [0, 0.1, 0, 0.9], [0, 0.9, 0, 0.1]
    score = stress_scores(wrong, truth, kernel)
    assert score["ignorability_score_excess"] < 0
    assert score["observation_channel_kl"] > 0
    assert score["latent_joint_kl"] > 0


def test_entity_exchange_equivariance_for_spectral_and_tree():
    observed = sample_observed(joint_law("opposed"), [0, 0.5, 0.3, 0.2], 800, 7)
    swapped = []
    swap = np.arange(225).reshape(15, 15).T.ravel()
    for c in range(4):
        index = projection(c)
        reps = np.unique(index, return_index=True)[1]
        swapped.append(np.bincount(index[swap[reps]], weights=observed.counts[c]).astype(int))
    other = PrefixCounts(tuple(swapped))
    baseline = fit_independent(observed)
    p, _ = spectral_fit(observed, baseline, "reveal")
    q, _ = spectral_fit(other, baseline[swap], "reveal")
    np.testing.assert_allclose(q, p[swap], atol=1e-12)
    np.testing.assert_allclose(
        tree_shrink_fit(other, baseline[swap], 10),
        tree_shrink_fit(observed, baseline, 10)[swap],
        atol=1e-12,
    )


def test_generated_runner_and_no_clinical_cli(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            dict(schema_version=1, data_class="synthetic", seeds=[4], patients=[32], em_steps=2)
        )
    )
    result = run_demo(config, tmp_path / "run")
    assert result["cases"] == 25
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert not manifest["novel_algorithm_established"]
    with pytest.raises(SystemExit):
        parser().parse_args(["joint-shrinkage-demo", "--data-root", "/restricted"])
    with pytest.raises(FileExistsError):
        run_demo(config, tmp_path / "run")
