from itertools import product

import numpy as np
import pytest

from ies.cardinality import count_distribution
from ies.competition import (
    LOWER,
    PARTITIONS,
    UPPER,
    GroupDesign,
    batch_log_normalizer,
    count_emissions,
    features,
    fit_competition,
    fit_emission,
    fit_single,
    generate,
    score,
)
from ies.history_roles import (
    GeneratedPath,
    emissions,
    fit_hmm,
    fit_reference,
    forward_emissions,
    hmm_score,
    pack,
)


def training(scenario="combined", patients=32):
    return pack(generate(scenario, patients, [4, 8], 7, "adaptive"))


def test_group_normalizer_and_labeled_likelihood_match_binary_enumeration():
    y = np.array(list(product((0, 1), repeat=4)))
    history = np.array([0, 1, 1, 3])
    paths = [GeneratedPath(history, row[None]) for row in y]
    data = pack(paths)
    signs = np.array([1, -1, -1, 1])
    params = np.array([-0.8, 0.5, -1.0, 0.2, -2.1])
    design = GroupDesign(data, signs)
    energy = y @ params[history] + params[4] * ((y - 0.5) @ signs[history]) ** 2 / 4
    normalizer = np.log(np.exp(energy).sum())
    np.testing.assert_allclose(design.emission(params)[:, 0], energy - normalizer, atol=1e-14)
    assert np.exp(design.emission(params)[:, 0]).sum() == pytest.approx(1, abs=1e-14)
    np.testing.assert_allclose(
        batch_log_normalizer(design.contexts, params, signs),
        design.distribution(params)[0],
        atol=1e-14,
    )


def test_convex_objective_gradient_hessian_and_psd():
    design = GroupDesign(training(), PARTITIONS[2])
    weights = np.random.default_rng(1).uniform(size=design.shape)
    params = np.array([-0.4, 0.2, -0.3, 0.6, -1.3])
    _, grad, hess = design.objective(params, weights)
    eps = 1e-5
    for i in range(5):
        delta = np.eye(5)[i] * eps
        a, ga, _ = design.objective(params + delta, weights)
        b, gb, _ = design.objective(params - delta, weights)
        assert (a - b) / (2 * eps) == pytest.approx(grad[i], abs=1e-9)
        np.testing.assert_allclose((ga - gb) / (2 * eps), hess[:, i], atol=1e-9)
    assert np.linalg.eigvalsh(hess).min() > 0


@pytest.mark.parametrize("scenario", ["independent", "signed_capacity", "combined"])
def test_emission_box_certificate_monotonicity_and_feasible_perturbations(scenario):
    data = training(scenario)
    design = GroupDesign(data, PARTITIONS[3])
    weights = np.ones(design.shape)
    estimate, diagnostic = fit_emission(design, weights, np.array([0.0, 0.0, 0.0, 0.0, 0.0]))
    assert diagnostic["convex_gap"] <= 2e-7
    assert min(np.diff(diagnostic["objective"])) <= 0
    assert max(np.diff(diagnostic["objective"])) <= 1e-11
    value, grad, _ = design.objective(estimate, weights)
    assert grad @ (estimate - np.where(grad > 0, LOWER, UPPER)) <= 2e-7
    for noise in np.random.default_rng(8).normal(0, 0.03, (20, 5)):
        assert (
            design.objective(np.clip(estimate + noise, LOWER, UPPER), weights, False)
            >= value - 1e-9
        )


def test_zero_competition_is_exact_bernoulli_hmm_and_unobserved_tail_is_zero():
    data = training()
    reference = fit_reference(data)
    learned, _ = fit_hmm(data, reference, 9, iterations=5)
    p = learned["probability"]
    model = dict(
        parameters=np.column_stack([np.log(p) - np.log1p(-p), np.zeros(2)]),
        signs=PARTITIONS[0],
        initial=learned["initial"],
        transition=learned["transition"],
        terminal=learned["terminal"],
    )
    np.testing.assert_allclose(count_emissions(data, model), emissions(data, p), atol=2e-14)
    np.testing.assert_allclose(score(data, model), hmm_score(data, learned), atol=3e-14)
    wrong = count_emissions(data, model)
    empty = data["lengths"][:, None] <= np.arange(8)[None]
    wrong[empty] = -1
    with pytest.raises(ValueError, match="tails"):
        forward_emissions(wrong, model["initial"], model["transition"], data["lengths"])


def test_grouped_large_roster_dp_matches_individual_count_dp():
    contexts = np.array([[40, 30, 20, 38], [0, 0, 0, 0], [0, 2, 0, 1]])
    params = np.array([-0.9, -0.4, 0.5, 0.1, -3.2])
    signs = PARTITIONS[2]
    actual = batch_log_normalizer(contexts, params, signs)
    for counts, value in zip(contexts, actual, strict=True):
        fields = np.repeat(signs * params[:4], counts)
        k = len(fields)
        base = count_distribution(fields, params[4] * (np.arange(k + 1) - k / 2) ** 2 / max(k, 1))
        assert value == pytest.approx(
            base["log_normalizer"] + counts[signs < 0] @ params[:4][signs < 0], abs=1e-12
        )


def test_known_competition_can_express_negative_identical_history_covariance():
    y = np.array(list(product((0, 1), repeat=4)))
    data = pack([GeneratedPath(np.zeros(4, dtype=int), row[None]) for row in y])
    design = GroupDesign(data, PARTITIONS[-1])
    logp = design.emission(np.array([-0.8, -0.8, -0.8, -0.8, -4]))[:, 0]
    q = np.exp(logp)
    covariance = q @ (y[:, 0] * y[:, 1]) - (q @ y[:, 0]) * (q @ y[:, 1])
    assert covariance < -0.02


def test_joint_em_and_single_state_fitting_keep_checked_inner_steps():
    data = training()
    reference = fit_reference(data)
    learned, _ = fit_hmm(data, reference, 1, iterations=10)
    model, diagnostics = fit_competition(data, learned, iterations=3, partitions=PARTITIONS[[0, 7]])
    for item in diagnostics["partitions"]:
        assert min(np.diff(item["objective"])) >= -1e-7
        assert max(x["convex_gap"] for x in item["msteps"]) <= 2e-7
    assert not diagnostics["global_optimum_claimed"]
    single, _ = fit_single(data, partitions=PARTITIONS[[0, 7]])
    for k in (4, 16, 32):
        other = pack(generate("combined", 3, [k], 20))
        assert np.isfinite(score(other, model)).all()
        assert np.isfinite(score(other, single)).all()


def test_generators_have_coupled_prefixes_absorbing_support_and_permutation_invariance():
    for scenario in ("signed_capacity", "combined"):
        a = generate(scenario, 8, [4, 8], 10)
        b = generate(scenario, 8, [4, 8], 10, "adaptive")
        for left, right in zip(a, b, strict=True):
            np.testing.assert_array_equal(left.events[: len(right.events)], right.events)
        data = pack(a)
        permuted = pack([GeneratedPath(p.initial[::-1], p.events[:, ::-1]) for p in a])
        for key in data:
            np.testing.assert_array_equal(data[key], permuted[key])


def test_emission_transition_and_prefix_probabilities_normalize_with_terminal_events():
    m = dict(
        parameters=np.array([[-1.0, -0.3, -0.8, 0.1, -3.0], [-0.4, -1.0, 0.5, -0.9, -2.0]]),
        signs=PARTITIONS[2],
        initial=np.array([0.4, 0.6]),
        transition=np.array([[0.8, 0.2], [0.2, 0.8]]),
        terminal=np.full(4, 0.08),
    )
    first = [
        GeneratedPath(np.array([0, 1]), np.array(row)[None]) for row in product((0, 1, 2), repeat=2)
    ]
    assert np.exp(score(pack(first), m)).sum() == pytest.approx(1, abs=1e-13)
    for prefix in first:
        alive = prefix.events[0] < 2
        children = []
        for values in product((0, 1, 2), repeat=int(alive.sum())):
            row = np.full(2, -1)
            row[alive] = values
            children.append(GeneratedPath(prefix.initial, np.vstack([prefix.events, row])))
        assert np.exp(score(pack(children), m)).sum() == pytest.approx(
            np.exp(score(pack([prefix]), m)[0]), abs=1e-13
        )


def test_invalid_support_and_bounds_fail_explicitly():
    with pytest.raises(ValueError):
        GroupDesign(pack(generate("independent", 1, [9], 1)), PARTITIONS[0])
    with pytest.raises(ValueError):
        batch_log_normalizer(np.array([[129, 0, 0, 0]]), np.zeros(5), PARTITIONS[0])
    with pytest.raises(ValueError):
        features(np.array([[-1, 0, 0, 0]]), np.ones((1, 4)), PARTITIONS[0])
    with pytest.raises(ValueError):
        features(np.zeros((1, 4)), np.ones((1, 4)), np.zeros(4))


def test_generated_runner_provenance_config_boundaries_and_sanitized_failure(tmp_path, monkeypatch):
    import json

    import yaml

    from ies.cli import parser
    from ies.competition_demo import load_config, run_demo
    from ies.io import sha256

    config = dict(
        schema_version=1, data_class="synthetic", seeds=[2], patients=32, evaluation_patients=64
    )
    location = tmp_path / "config.yaml"
    location.write_text(yaml.safe_dump(config))
    assert load_config(location)[0] == config
    assert parser().parse_args(["competition-demo"]).config.name == "synthetic_competition.yaml"
    monkeypatch.setattr("ies.competition_demo.SCENARIOS", ("independent",))
    original = fit_competition

    def small(data, hmm):
        return original(data, hmm, iterations=2, partitions=PARTITIONS[[0, 7]])

    monkeypatch.setattr("ies.competition_demo.fit_competition", small)
    result = run_demo(location, tmp_path / "run")
    assert result["fit_cases"] == 2 and result["evaluation_cases"] == 8
    manifest = json.loads((tmp_path / "run/manifest.json").read_text())
    assert (
        not manifest["clinical_inputs_used"]
        and not manifest["partial_entity_observations_supported"]
    )
    assert not manifest["novel_algorithm_established"]
    for name, digest in manifest["output_files_sha256"].items():
        assert sha256(tmp_path / "run" / name) == digest
    with pytest.raises(FileExistsError):
        run_demo(location, tmp_path / "run")
    location.write_text(yaml.safe_dump(config | {"patients": True}))
    with pytest.raises(ValueError):
        load_config(location)
    location.write_text(yaml.safe_dump(config | {"data_class": "restricted"}))
    with pytest.raises(ValueError):
        load_config(location)
    location.write_text(yaml.safe_dump(config))

    def fail(*args, **kwargs):
        raise ValueError("SECRET generated diagnostic marker")

    monkeypatch.setattr("ies.competition_demo.generate", fail)
    with pytest.raises(RuntimeError, match="Generated competition experiment failed"):
        run_demo(location, tmp_path / "failure")
    assert "SECRET" not in (tmp_path / "failure/manifest.json").read_text()


def test_coupled_newton_outward_at_zero_competition_does_not_stall():
    # The first full run exposed an inward gradient but outward Newton component
    # at theta=0. This generated regression previously exhausted the solver.
    data = pack(generate("hidden_persistent", 256, [4, 8], 20261109 + 200003, "adaptive"))
    hmm, _ = fit_hmm(data, fit_reference(data), 20261109)
    _, diagnostic = fit_competition(data, hmm, partitions=PARTITIONS[[4]])
    assert (
        max(step["convex_gap"] for item in diagnostic["partitions"] for step in item["msteps"])
        <= 2e-7
    )


def test_forecast_samples_conditional_joint_law_including_unknown_terminal_events():
    from ies.competition import forecast

    model = dict(
        parameters=np.array([[-1.0, -0.3, -0.8, 0.1, -3.0], [-0.4, -1.0, 0.5, -0.9, -2.0]]),
        signs=PARTITIONS[2],
        initial=np.array([0.4, 0.6]),
        transition=np.array([[0.8, 0.2], [0.2, 0.8]]),
        terminal=np.full(4, 0.08),
    )
    prefix = GeneratedPath(np.array([0, 1]), np.array([[1, 0]]))
    patterns = np.array(list(product((0, 1, 2), repeat=2)))
    extended = [GeneratedPath(prefix.initial, np.vstack([prefix.events, row])) for row in patterns]
    expected = np.exp(score(pack(extended), model) - score(pack([prefix]), model)[0])
    result = forecast(prefix, model, 4096, 31, horizon=1)
    empirical = np.array([np.all(result["events"][:, 0] == row, axis=1).mean() for row in patterns])
    np.testing.assert_allclose(empirical, expected, atol=0.025)
    assert result["next_latent_probability"].sum() == pytest.approx(1)
    np.testing.assert_array_equal(result["histories_at_cutoff"], [1, 2])
    np.testing.assert_array_equal(prefix.events, [[1, 0]])


def test_forecast_preserves_absorption_and_is_seeded_with_explicit_bounds():
    from ies.competition import forecast

    model = dict(
        parameters=np.array([[-1.0, -0.3, -0.8, 0.1, -3.0], [-0.4, -1.0, 0.5, -0.9, -2.0]]),
        signs=PARTITIONS[2],
        initial=np.array([0.4, 0.6]),
        transition=np.array([[0.8, 0.2], [0.2, 0.8]]),
        terminal=np.full(4, 0.4),
    )
    prefix = GeneratedPath(np.array([0, 1]), np.array([[2, 0]]))
    a = forecast(prefix, model, 20, 9, horizon=4)
    b = forecast(prefix, model, 20, 9, horizon=4)
    np.testing.assert_array_equal(a["events"], b["events"])
    assert np.all(a["events"][:, :, 0] == -1)
    for future in a["events"]:
        pack([GeneratedPath(prefix.initial, np.vstack([prefix.events, future]))])
    for samples in (0, True, 10_001):
        with pytest.raises(ValueError):
            forecast(prefix, model, samples, 1)
    dead = GeneratedPath(np.array([0, 1]), np.array([[2, 2]]))
    assert np.all(forecast(dead, model, 10, 1)["events"] == -1)
