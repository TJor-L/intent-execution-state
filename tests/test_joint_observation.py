import json

import numpy as np
import pytest
import yaml

from ies.cli import parser
from ies.joint_demo import load_config, mechanism_audit, run_demo
from ies.joint_observation import (
    LAWS,
    PATHS,
    STATES,
    WINDOWS,
    PrefixCounts,
    fit_independent,
    fit_joint,
    fit_mixture,
    fit_zero_filled,
    joint_law,
    nonidentifiability_witness,
    observed_nll,
    population_scores,
    projection,
    sample_observed,
)


def test_support_contains_recurrence_and_absorbing_termination():
    assert PATHS.shape == (15, 3)
    assert STATES.shape == (225, 2, 3)
    assert any(np.array_equal(row, [1, 1, 1]) for row in PATHS)
    for row in PATHS:
        if 2 in row:
            assert np.all(row[np.flatnonzero(row == 2)[0] + 1 :] == 3)
        else:
            assert 3 not in row


def test_identical_marginals_hide_distinct_joint_outcomes():
    laws = [joint_law(name) for name in LAWS]
    for law in laws:
        assert law.sum() == pytest.approx(1)
        assert np.all(law > 0)
        for axis in (0, 1):
            np.testing.assert_allclose(
                law.reshape(15, 15).sum(axis=axis), laws[0].reshape(15, 15).sum(axis=axis)
            )
    events = np.all((STATES == 1).sum(axis=2) >= 2, axis=1)
    assert laws[1] @ events > laws[0] @ events > laws[2] @ events
    scores = population_scores(laws[0], laws[1], WINDOWS["full"])
    assert scores["marginal_count_mean_squared_error"] < 1e-25
    assert scores["latent_joint_kl"] > 0.01


def test_prefix_equivalence_does_not_fill_unseen_future():
    index = projection(1)
    keys = [tuple(state[:, :1].ravel()) for state in STATES]
    for a, key in enumerate(keys):
        for b in range(a):
            assert (index[a] == index[b]) == (key == keys[b])
    assert len(set(projection(0))) == 1
    assert len(set(projection(3))) == len(STATES)
    assert len(set(projection(2))) == 49


def test_nonidentifiability_witness_and_rank():
    witness = nonidentifiability_witness()
    assert witness["prefix_l1_differences"] == [0, 0, 0, 2]
    assert witness["final_bin_both_recur_probabilities"] == [0.5, 0]
    audit = mechanism_audit()
    assert audit["window_support"]["no_tail_support"]["observation_operator_rank"] == 49
    assert not audit["window_support"]["no_tail_support"]["full_distribution_identified"]
    assert audit["window_support"]["independent_short"]["full_distribution_identified"]


def _first_prefix_count(observed):
    result = np.zeros(9)
    for window, count in enumerate(observed.counts):
        if not count.sum():
            continue
        representatives = np.unique(projection(window), return_index=True)[1]
        result += np.bincount(projection(1)[representatives], weights=count, minlength=9)
    return result


def test_censor_policy_changes_do_not_change_latent_rng():
    p = joint_law("synchronized")
    full = sample_observed(p, WINDOWS["full"], 1024, 3)
    short = sample_observed(p, WINDOWS["independent_short"], 1024, 3)
    np.testing.assert_array_equal(_first_prefix_count(full), _first_prefix_count(short))
    assert full.patients == short.patients == 1024


def test_full_observation_em_matches_closed_form():
    observed = sample_observed(joint_law("opposed"), WINDOWS["full"], 300, 5)
    p = fit_joint(observed)
    count = observed.counts[3][projection(3)]
    np.testing.assert_allclose(p, (count + 1 / len(STATES)) / 301)
    np.testing.assert_allclose(fit_zero_filled(observed), p)


def test_latent_states_cannot_enter_fit_api_and_no_observation_is_uninformative():
    counts = tuple(np.zeros(projection(c).max() + 1, dtype=int) for c in range(4))
    counts[0][0] = 100
    observed = PrefixCounts(counts)
    uniform = np.full(len(STATES), 1 / len(STATES))
    np.testing.assert_allclose(fit_joint(observed), uniform)
    assert observed_nll(uniform, observed) == pytest.approx(0)
    with pytest.raises(TypeError):
        fit_joint(observed, latent=joint_law("synchronized"))


@pytest.mark.parametrize("method", [fit_joint, fit_independent, fit_zero_filled])
def test_estimators_normalize_and_keep_training_scores_finite(method):
    observed = sample_observed(joint_law("synchronized"), WINDOWS["independent_short"], 128, 8)
    p = method(observed)
    assert p.sum() == pytest.approx(1)
    assert np.all(p > 0)
    assert np.isfinite(observed_nll(p, observed))


def test_latent_class_em_is_deterministic_and_improves_uniform_training_loss():
    observed = sample_observed(joint_law("opposed"), WINDOWS["independent_short"], 1024, 10)
    p = fit_mixture(observed, 31, steps=100)
    np.testing.assert_array_equal(p, fit_mixture(observed, 31, steps=100))
    assert p.sum() == pytest.approx(1)
    assert observed_nll(p, observed) < observed_nll(np.full(225, 1 / 225), observed)


def test_observed_information_cannot_exceed_full_information():
    p, q = joint_law("independent"), joint_law("opposed")
    scores = population_scores(p, q, WINDOWS["independent_short"])
    assert 0 <= scores["observed_prefix_kl"] <= scores["latent_joint_kl"]
    zero = population_scores(q, q, WINDOWS["full"])
    assert zero["latent_joint_kl"] == pytest.approx(0)


@pytest.mark.parametrize("invalid", [-1, 4, True, 1.5])
def test_invalid_windows_rejected(invalid):
    with pytest.raises(ValueError):
        projection(invalid)


def test_observed_statistics_validate_counts_and_bounds():
    observed = sample_observed(joint_law("independent"), WINDOWS["full"], 10, 2)
    wrong = list(observed.counts)
    wrong[1] = np.array([10])
    with pytest.raises(ValueError):
        fit_joint(PrefixCounts(tuple(wrong)))
    with pytest.raises(ValueError):
        fit_joint(observed, steps=1001)
    with pytest.raises(ValueError):
        sample_observed(joint_law("independent"), [0, 0, 0, 0], 10, 2)


def test_generated_config_and_cli_reject_clinical_inputs(tmp_path):
    path = tmp_path / "config.yaml"
    config = dict(schema_version=1, data_class="synthetic", seeds=[7], patients=[32], em_steps=2)
    path.write_text(yaml.safe_dump(config))
    assert load_config(path)[0] == config
    for changes in ({"data_root": "/restricted"}, {"em_steps": 1001}, {"data_class": "clinical"}):
        path.write_text(yaml.safe_dump(config | changes))
        with pytest.raises(ValueError):
            load_config(path)
    with pytest.raises(SystemExit):
        parser().parse_args(["joint-audit-demo", "--cohort-dir", "/restricted"])


def test_generated_runner_provenance_reproducibility_and_no_overwrite(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            dict(schema_version=1, data_class="synthetic", seeds=[7], patients=[32], em_steps=2)
        )
    )
    a, b = tmp_path / "a", tmp_path / "b"
    assert run_demo(config, a)["cases"] == 9
    run_demo(config, b)
    for filename in ("models.json", "metrics.json", "audit.json"):
        assert (a / filename).read_bytes() == (b / filename).read_bytes()
    manifest = json.loads((a / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert not manifest["clinical_inputs_used"]
    with pytest.raises(FileExistsError):
        run_demo(config, a)


def test_failure_manifest_omits_exception_payload(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            dict(schema_version=1, data_class="synthetic", seeds=[7], patients=[32], em_steps=2)
        )
    )

    def fail(*args):
        raise ValueError("not-for-logs")

    monkeypatch.setattr("ies.joint_demo.sample_observed", fail)
    run_dir = tmp_path / "failed"
    with pytest.raises(ValueError):
        run_demo(config, run_dir)
    text = (run_dir / "manifest.json").read_text()
    assert "not-for-logs" not in text
    assert json.loads(text)["status"] == "failed"
