import json
from itertools import product

import numpy as np
import pytest

from ies.cardinality import count_distribution, log_probability
from ies.history_roles import GeneratedPath, hmm_score, pack
from ies.roster_marginal import (
    exchangeable_pair_moments,
    marginalize_count,
    run_audit,
    same_history_capacity,
)


def states(k):
    return np.array(list(product((0, 1), repeat=k)), dtype=int).reshape(2**k, k)


def test_fixed_population_marginal_matches_enumeration_with_unequal_fields():
    model = count_distribution(np.array([-1.1, 0.2, 0.7, -0.8, -0.2]), np.sin(np.arange(6)))
    all_states = states(5)
    q = np.exp(log_probability(model, all_states))
    for keep in ([1, 4], [4, 1], [2], [], [0, 1, 2, 3, 4]):
        marginal = marginalize_count(model, keep)
        outcomes = states(len(keep))
        exact = np.array([q[np.all(all_states[:, keep] == row, axis=1)].sum() for row in outcomes])
        np.testing.assert_allclose(np.exp(log_probability(marginal, outcomes)), exact, atol=2e-15)


def test_successive_deletions_associate_and_preserve_original_pair_moments():
    original = same_history_capacity(128)
    intermediate = marginalize_count(original, list(range(64)))
    sequential = marginalize_count(intermediate, [3, 40])
    direct = marginalize_count(original, [3, 40])
    np.testing.assert_allclose(
        log_probability(sequential, states(2)), log_probability(direct, states(2)), atol=1e-12
    )
    pair = exchangeable_pair_moments(original)
    q = np.exp(log_probability(direct, states(2)))
    assert q[3] == pytest.approx(pair["both"], abs=1e-13)
    assert q[2:].sum() == pytest.approx(pair["mean"], abs=1e-13)


def test_negative_covariance_is_finite_but_not_infinite_exchangeable():
    for k in (4, 8, 16, 32, 128):
        pair = exchangeable_pair_moments(same_history_capacity(k))
        rho = pair["correlation"]
        assert -1 / (k - 1) <= rho < 0
        assert pair["necessary_extension_size_ceiling"] >= k
        assert not pair["extension_bound_is_sufficient"]
        n = int(np.ceil(pair["necessary_extension_size_ceiling"])) + 1
        assert 1 + (n - 1) * rho < 0


def test_latent_iid_has_nonnegative_same_history_covariance_but_signed_roles_can_differ():
    weights = np.array([0.1, 0.2, 0.7])
    p = np.array([0.1, 0.4, 0.8])
    covariance = weights @ p**2 - (weights @ p) ** 2
    assert covariance >= 0
    assert weights @ (p * (1 - p)) - (weights @ p) * (weights @ (1 - p)) < 0


def test_recurrent_hidden_markov_law_marginalizes_whole_entities():
    model = dict(
        probability=np.array([[0.1, 0.2, 0.3, 0.4], [0.65, 0.7, 0.55, 0.8]]),
        initial=np.array([0.3, 0.7]),
        transition=np.array([[0.8, 0.2], [0.1, 0.9]]),
        terminal=np.array([0.05, 0.1, 0.15, 0.2]),
    )
    valid = [[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2], [2, -1]]
    for own in valid:
        single = GeneratedPath(np.array([1]), np.array(own).reshape(2, 1))
        pairs = [GeneratedPath(np.array([1, 3]), np.column_stack([own, other])) for other in valid]
        assert np.exp(hmm_score(pack(pairs), model)).sum() == pytest.approx(
            np.exp(hmm_score(pack([single]), model)[0]), abs=1e-13
        )


def test_known_population_deletion_differs_from_actual_smaller_population_and_artifact(tmp_path):
    result = run_audit(tmp_path / "audit")
    assert result["cases"] == 6
    report = json.loads((tmp_path / "audit/results.json").read_text())
    assert all(x["total_variation_from_changing_population_size"] > 0.05 for x in report["cases"])
    with pytest.raises(ValueError):
        marginalize_count(same_history_capacity(4), [0, 0])
    with pytest.raises(ValueError):
        marginalize_count(same_history_capacity(4), [5])
    with pytest.raises(ValueError):
        marginalize_count(same_history_capacity(4), [True])
