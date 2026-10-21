import json
from itertools import product

import numpy as np
import pytest
import yaml

from ies.cardinality import (
    count_distribution,
    feature_values,
    fit_strength,
    interaction_feature,
    log_probability,
    sample_sets,
    tilt_model,
)
from ies.cardinality_demo import (
    draw,
    empirical_count_model,
    fit_mixture,
    generated_law,
    load_config,
    log_density,
    run_demo,
)
from ies.cardinality_limits import (
    count_family_witness,
    feature_range,
    population_projection,
    run_audit,
)
from ies.cli import parser


def _events(k):
    return np.asarray(list(product((0, 1), repeat=k)), dtype=int).reshape(-1, k)


def test_dynamic_program_and_marginals_equal_exhaustive_enumeration():
    fields = np.array([-1.3, 0.2, 0.7, -0.6, -1.9])
    potential = np.array([0.2, -0.4, 1.3, 0.5, -0.2, 0.3])
    model = count_distribution(fields, potential)
    events = _events(5)
    energy = events @ fields + potential[events.sum(axis=1)]
    probability = np.exp(energy - np.log(np.exp(energy).sum()))
    np.testing.assert_allclose(np.exp(log_probability(model, events)), probability, atol=1e-14)
    np.testing.assert_allclose(model["marginals"], probability @ events, atol=1e-14)
    np.testing.assert_allclose(
        model["count_probability"], np.bincount(events.sum(axis=1), weights=probability), atol=1e-14
    )


def test_reverse_dp_marginals_equal_log_partition_derivatives():
    fields = np.array([-1.7, 0.5, 1.3, -0.2])
    potential = np.cos(np.arange(5))
    model = count_distribution(fields, potential)
    epsilon = 1e-5
    for i in range(4):
        direction = np.eye(4)[i]
        upper = count_distribution(fields + epsilon * direction, potential)["log_normalizer"]
        lower = count_distribution(fields - epsilon * direction, potential)["log_normalizer"]
        assert (upper - lower) / (2 * epsilon) == pytest.approx(model["marginals"][i], abs=1e-10)


@pytest.mark.parametrize("kind", ("projected_bounded", "projected_quadratic"))
def test_projected_score_has_unit_variance_and_zero_marginal_covariances(kind):
    p = np.array([0.07, 0.17, 0.38, 0.63, 0.81])
    events = _events(len(p))
    feature = interaction_feature(p, kind)
    probability = np.exp(log_probability(tilt_model(feature, 0), events))
    values = feature_values(feature, events)
    assert probability @ values == pytest.approx(0, abs=1e-12)
    assert probability @ values**2 == pytest.approx(1, abs=1e-11)
    np.testing.assert_allclose((probability * values) @ (events - p), 0, atol=1e-12)
    for strength in (-0.4, 0.3):
        model = tilt_model(feature, strength)
        actual = log_probability(model, events)
        expected = np.log(probability) + strength * values
        expected -= np.log(np.exp(expected).sum())
        np.testing.assert_allclose(actual, expected, atol=1e-12)


def test_projection_is_only_local_marginal_preservation():
    p = np.array([0.1, 0.3, 0.6, 0.8])
    feature = interaction_feature(p)
    epsilon = 1e-5
    derivative = (
        tilt_model(feature, epsilon)["marginals"] - tilt_model(feature, -epsilon)["marginals"]
    ) / (2 * epsilon)
    np.testing.assert_allclose(derivative, 0, atol=1e-9)
    assert np.max(abs(tilt_model(feature, 0.8)["marginals"] - p)) > 0.001
    ordinary = interaction_feature(p, "unprojected_bounded")
    derivative = (
        tilt_model(ordinary, epsilon)["marginals"] - tilt_model(ordinary, -epsilon)["marginals"]
    ) / (2 * epsilon)
    assert np.max(abs(derivative)) > 0.01


def test_tilt_likelihood_derivative_matches_sufficient_statistic():
    feature = interaction_feature([0.2, 0.3, 0.4, 0.6])
    events = _events(4)
    strength, epsilon = 0.4, 1e-5
    model = tilt_model(feature, strength)
    upper, lower = tilt_model(feature, strength + epsilon), tilt_model(feature, strength - epsilon)
    numerical = (log_probability(upper, events) - log_probability(lower, events)) / (2 * epsilon)
    np.testing.assert_allclose(
        numerical, feature_values(feature, events) - model["expected_feature"], atol=2e-9
    )


def test_exact_backward_sampling_matches_joint_and_count_distribution():
    model = tilt_model(interaction_feature([0.1, 0.3, 0.7, 0.8]), -0.6)
    draws = sample_sets(model, 40_000, 11)
    np.testing.assert_allclose(draws.mean(axis=0), model["marginals"], atol=0.012)
    empirical = np.bincount(draws.sum(axis=1), minlength=5) / len(draws)
    np.testing.assert_allclose(empirical, model["count_probability"], atol=0.012)
    states = _events(4)
    encoded = draws @ (2 ** np.arange(4))
    probabilities = np.exp(log_probability(model, states))
    np.testing.assert_allclose(
        np.bincount(encoded, minlength=16)[states @ (2 ** np.arange(4))] / len(draws),
        probabilities,
        atol=0.008,
    )
    np.testing.assert_array_equal(sample_sets(model, 20, 8), sample_sets(model, 20, 8))


def test_entity_permutation_equivariance():
    p = np.array([0.09, 0.21, 0.51, 0.7, 0.8])
    permutation = np.array([4, 0, 2, 1, 3])
    model = tilt_model(interaction_feature(p), 0.5)
    other = tilt_model(interaction_feature(p[permutation]), 0.5)
    np.testing.assert_allclose(other["marginals"], model["marginals"][permutation], atol=1e-12)
    events = _events(5)
    np.testing.assert_allclose(
        log_probability(other, events[:, permutation]), log_probability(model, events), atol=1e-12
    )


def test_empty_and_single_entity_cannot_have_projected_interactions():
    for p in ([], [0.3]):
        feature = interaction_feature(p)
        assert feature["degenerate"]
        model = tilt_model(feature, 2)
        np.testing.assert_allclose(model["marginals"], p, atol=1e-12)
        assert sample_sets(model, 10, 1).shape == (10, len(p))


def test_128_entity_engine_uses_quadratic_workspace_and_finite_probabilities():
    p = np.linspace(0.05, 0.8, 128)
    for kind in ("projected_bounded", "projected_quadratic"):
        model = tilt_model(interaction_feature(p, kind), 0.5)
        assert model["forward"].shape == (129, 129)
        assert model["count_probability"].sum() == pytest.approx(1)
        assert np.isfinite(log_probability(model, sample_sets(model, 10, 21))).all()
        assert model["marginals"].sum() == pytest.approx(
            model["count_probability"] @ np.arange(129), abs=1e-9
        )


def test_positive_and_negative_association_are_both_representable():
    p = np.full(6, 0.3)
    events = _events(6)
    feature = interaction_feature(p)
    covariances = []
    for strength in (-0.5, 0.5):
        model = tilt_model(feature, strength)
        probability = np.exp(log_probability(model, events))
        covariance = probability @ (events[:, 0] * events[:, 1]) - np.prod(model["marginals"][:2])
        covariances.append(covariance)
    assert covariances[0] > 0 and covariances[1] < 0


def test_scalar_fit_certifies_optimum_against_grid():
    p = np.array([0.1, 0.2, 0.4, 0.6])
    model = tilt_model(interaction_feature(p), -0.5)
    events = sample_sets(model, 300, 8)
    fitted, diagnostic = fit_strength(p, events)
    assert diagnostic["convex_gap"] < 1e-7
    assert diagnostic["strength"] < 0
    assert not diagnostic["reference_fitted_here"]
    feature = interaction_feature(p)
    for strength in np.linspace(-2, 2, 31):
        alternative = tilt_model(feature, strength)
        objective = -log_probability(alternative, events).mean() + 0.005 * strength**2
        assert diagnostic["objective"] <= objective + 1e-9
    assert np.isfinite(log_probability(fitted, events)).all()


def test_scalar_boundary_optimum_is_explicit_and_invalid_inputs_rejected():
    _, diagnostic = fit_strength(np.full(4, 0.3), np.ones((30, 4), dtype=int), bound=0.05)
    assert diagnostic["status"] in {"lower_bound", "upper_bound"}
    assert diagnostic["convex_gap"] < 1e-7
    with pytest.raises(ValueError):
        interaction_feature([0.0, 0.5])
    with pytest.raises(ValueError):
        fit_strength([0.2, 0.3], [[0, -1]])
    with pytest.raises(ValueError):
        count_distribution(np.zeros(129), np.zeros(130))
    with pytest.raises(ValueError):
        count_distribution([0, np.nan], [0, 0, 0])
    with pytest.raises(ValueError):
        sample_sets(tilt_model(interaction_feature([0.3]), 0), 0, 1)


def test_generated_laws_normalized_and_exact_moments_verified_by_enumeration():
    events = _events(4)
    for scenario in ("independent", "shared_shift", "opposed_shift", "soft_capacity"):
        model = generated_law(scenario, 4)
        probability = np.exp(log_density(model, events))
        assert probability.sum() == pytest.approx(1)
        np.testing.assert_allclose(probability @ events, model["marginals"], atol=1e-12)
        np.testing.assert_allclose(
            np.bincount(events.sum(axis=1), weights=probability),
            model["count_probability"],
            atol=1e-12,
        )
        fitted = tilt_model(interaction_feature([0.2, 0.3, 0.5, 0.7]), -0.3)
        expectation = (
            fitted["log_normalizer"]
            - fitted["fields"] @ model["marginals"]
            - fitted["potential"] @ model["count_probability"]
        )
        assert expectation == pytest.approx(-probability @ log_density(fitted, events), abs=1e-12)


def test_empirical_count_smoothing_matches_counts_and_handles_tiny_tail_masses():
    p = np.array([0.1, 0.2, 0.3, 0.4])
    events = draw(generated_law("shared_shift", 4), 60, 12)
    model = empirical_count_model(p, events)
    base = tilt_model(interaction_feature(p), 0)
    expected = (np.bincount(events.sum(axis=1), minlength=5) + 10 * base["count_probability"]) / 70
    np.testing.assert_allclose(model["count_probability"], expected, atol=1e-13)
    rare = empirical_count_model(np.full(128, 0.0001), np.zeros((32, 128), dtype=int))
    assert np.isfinite(log_density(rare, np.ones((1, 128), dtype=int))).all()


def test_mixture_em_objective_is_monotone_and_preserves_normalization():
    events = draw(generated_law("opposed_shift", 4), 200, 17)
    model, diagnostic = fit_mixture(events, 31)
    assert np.min(np.diff(diagnostic["objective_trace"])) > -1e-9
    assert np.exp(log_density(model, _events(4))).sum() == pytest.approx(1)
    with pytest.raises(ValueError):
        fit_mixture([[0, -1]], 1)


def _config(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            dict(
                schema_version=1,
                data_class="synthetic",
                seeds=[1],
                entities=[4],
                patients=[32],
                evaluation_patients=128,
            )
        )
    )
    return path


def test_runner_determinism_provenance_oracle_label_and_private_input_rejection(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("ies.cardinality_demo.SCENARIOS", ("shared_shift",))
    config = _config(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    assert run_demo(config, a)["cases"] == 1
    run_demo(config, b)
    for filename in ("metrics.json", "models.json"):
        assert (a / filename).read_bytes() == (b / filename).read_bytes()
    manifest = json.loads((a / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["complete_observed_transition_only"]
    assert not manifest["clinical_inputs_used"] and not manifest["novel_algorithm_established"]
    methods = json.loads((a / "metrics.json").read_text())["cases"][0]["methods"]
    assert not methods["oracle_marginal_projected"]["feasible"]
    assert all(methods[name]["feasible"] for name in methods if name != "oracle_marginal_projected")
    with pytest.raises(FileExistsError):
        run_demo(config, a)
    with pytest.raises(SystemExit):
        parser().parse_args(["cardinality-demo", "--data-root", "/restricted"])
    value = yaml.safe_load(config.read_text())
    value["data_class"] = "clinical"
    config.write_text(yaml.safe_dump(value))
    with pytest.raises(ValueError):
        load_config(config)


def test_failure_manifest_omits_exception_payload(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("do-not-log-this-payload")

    monkeypatch.setattr("ies.cardinality_demo.fit_strength", fail)
    with pytest.raises(RuntimeError):
        run_demo(_config(tmp_path), tmp_path / "failed")
    content = (tmp_path / "failed/manifest.json").read_text()
    assert "do-not-log-this-payload" not in content
    assert json.loads(content)["status"] == "failed"


def test_feature_range_and_density_ratio_bound_match_enumeration():
    feature = interaction_feature([0.1, 0.3, 0.5, 0.8])
    events = _events(4)
    values = feature_values(feature, events)
    low, high = feature_range(feature)
    assert low == pytest.approx(values.min()) and high == pytest.approx(values.max())
    base = tilt_model(feature, 0)
    for strength in (-2, 0.3, 2):
        ratio = log_density(tilt_model(feature, strength), events) - log_density(base, events)
        assert abs(ratio).max() <= abs(strength) * (high - low) + 1e-12


def test_count_family_witness_has_equal_sufficient_statistics_and_irreducible_gap():
    states, p, q = count_family_witness()
    np.testing.assert_array_equal(p @ states, q @ states)
    np.testing.assert_array_equal(
        np.bincount(states.sum(axis=1), weights=p), np.bincount(states.sum(axis=1), weights=q)
    )
    pair = np.all(states[:, :2] == 1, axis=1)
    assert p @ pair == 0.5 and q @ pair == 0
    for seed in range(5):
        rng = np.random.default_rng(seed)
        model = count_distribution(rng.normal(size=4), rng.normal(size=5))
        logs = log_density(model, states)
        assert p @ logs == pytest.approx(q @ logs, abs=1e-12)
        assert -p @ logs - np.log(2) >= np.log(3) - 1e-12
    # Concentrating the count at two with equal fields attains the infimum in the limit.
    model = count_distribution(np.zeros(4), np.array([-100.0, -100, 0, -100, -100]))
    assert -p @ log_density(model, states) - np.log(2) == pytest.approx(np.log(3), abs=1e-12)


def test_population_projection_is_explicit_oracle_and_audit_writes_verified_manifest(tmp_path):
    result = population_projection(generated_law("shared_shift", 64))
    assert result["infeasible_oracle"] and result["bound_unchanged"] == 2
    assert result["strength"] == pytest.approx(-2)
    assert result["convex_gap"] < 1e-7
    assert result["exact_count_kl"] > 1
    assert run_audit(tmp_path / "limits")["cases"] == 12
    manifest = json.loads((tmp_path / "limits/manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["population_oracles_only"]
    assert not manifest["clinical_inputs_used"]
