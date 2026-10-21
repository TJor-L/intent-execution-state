import json

import numpy as np
import pytest

from ies.cli import parser
from ies.joint_information import channel_scores, information_audit, path_contrasts, run_audit
from ies.joint_observation import entity_law, joint_law, projection
from ies.joint_stress import POLICIES, observation_kernel


def test_full_contrast_basis_includes_nuisance_and_handles_unequal_marginals():
    q = np.outer(entity_law(0.11), entity_law(0.43)).ravel()
    z, depths = path_contrasts(q)
    assert z.shape == (225, 224)
    np.testing.assert_allclose(q @ z, 0, atol=1e-14)
    np.testing.assert_allclose(z.T @ (q[:, None] * z), np.eye(224), atol=1e-13)
    assert [sum(depths == d) for d in (1, 2, 3)] == [8, 40, 176]


@pytest.mark.parametrize("policy", POLICIES)
def test_known_channel_scores_match_probability_derivatives_and_information_contracts(policy):
    q, kernel = joint_law("independent"), observation_kernel(policy)
    z, _ = path_contrasts(q)
    result = channel_scores(q, kernel)
    direction = np.random.default_rng(71).normal(size=224)
    direction /= np.max(abs(z @ direction))
    epsilon = 1e-6
    plus, minus = q * (1 + epsilon * (z @ direction)), q * (1 - epsilon * (z @ direction))
    upper, lower = [], []
    for c in range(4):
        index = projection(c)
        upper.extend(np.bincount(index, weights=plus * kernel[c]))
        lower.extend(np.bincount(index, weights=minus * kernel[c]))
    active = result["weights"] > 0
    numerical = (np.log(np.asarray(upper)[active]) - np.log(np.asarray(lower)[active])) / (
        2 * epsilon
    )
    np.testing.assert_allclose(numerical, result["channel_scores"][active] @ direction, atol=2e-9)
    w, score = result["weights"], result["channel_scores"]
    np.testing.assert_allclose(w @ score, 0, atol=1e-13)
    eigenvalues = np.linalg.eigvalsh(score.T @ (w[:, None] * score))
    assert eigenvalues.min() > -1e-12
    assert eigenvalues.max() <= 1 + 1e-12


def test_independent_windows_have_diagonal_information_and_no_nuisance_loss():
    summary, matrices = information_audit(
        joint_law("independent"), observation_kernel("independent_short")
    )
    depths = np.asarray(matrices["reveal_depth"])
    survival = np.asarray(summary["observed_fraction_by_depth"])
    np.testing.assert_allclose(
        matrices["ordinary_second_moment"], np.diag(survival[depths]), atol=1e-12
    )
    assert summary["kernel_is_car_on_prefix_cells"]
    assert summary["efficient_interaction_information"]["nuisance_loss_trace"] < 1e-12
    assert summary["known_channel_information_rank"] == 224


def test_predictable_stopping_preserves_depth_blocks_but_couples_nuisance():
    summary, matrices = information_audit(
        joint_law("independent"), observation_kernel("adaptive_past")
    )
    assert summary["kernel_is_car_on_prefix_cells"]
    assert summary["ordinary_score_mean_max"] < 1e-12
    assert summary["ordinary_second_moment_between_depth_max"] < 1e-12
    assert summary["ordinary_marginal_interaction_max"] > 0.1
    assert summary["efficient_interaction_information"]["nuisance_loss_trace"] > 1
    assert summary["efficient_interaction_information"]["minimum_eigenvalue"] > -1e-12
    np.testing.assert_allclose(
        matrices["ordinary_second_moment"], matrices["known_channel_information"], atol=1e-12
    )


def test_no_tail_information_stays_rank_deficient():
    summary, matrices = information_audit(
        joint_law("independent"), observation_kernel("no_tail_support")
    )
    assert summary["known_channel_information_rank"] == 48
    assert summary["efficient_interaction_information"]["rank"] == 36
    late = np.asarray(matrices["reveal_depth"]) == 3
    np.testing.assert_allclose(
        np.asarray(matrices["known_channel_information"])[late], 0, atol=1e-12
    )


def test_future_stopping_exposes_nonzero_naive_score_without_claiming_fisher():
    summary, _ = information_audit(
        joint_law("independent"), observation_kernel("informative_future")
    )
    assert not summary["kernel_is_car_on_prefix_cells"]
    assert not summary["ordinary_second_moment_is_fisher"]
    assert summary["ordinary_score_mean_max"] > 0.01
    assert summary["channel_score_mean_max"] < 1e-12
    assert summary["supported_score_discrepancy_max"] > 0.1
    assert summary["efficient_interaction_information"] is None
    assert not summary["observational_test_of_car"]


def test_invalid_reference_and_kernel_rejected():
    with pytest.raises(ValueError):
        path_contrasts(joint_law("synchronized"))
    with pytest.raises(ValueError):
        information_audit(joint_law("independent"), np.zeros((4, 225)))


def test_information_runner_provenance_and_clinical_flags_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("ies.joint_information.POLICIES", ("adaptive_past",))
    assert run_audit(tmp_path / "audit")["policies"] == 1
    manifest = json.loads((tmp_path / "audit/manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert not manifest["model_fitted"] and not manifest["clinical_inputs_used"]
    assert len(manifest["artifacts_sha256"]) == 2
    with pytest.raises(FileExistsError):
        run_audit(tmp_path / "audit")
    with pytest.raises(SystemExit):
        parser().parse_args(["joint-information-demo", "--data-root", "/restricted"])
