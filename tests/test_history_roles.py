import json
from itertools import product

import numpy as np
import pytest
import yaml

from ies.cli import parser
from ies.history_roles import (
    SCENARIOS,
    GeneratedPath,
    bank_models,
    bank_score,
    emissions,
    fit_bank,
    fit_hmm,
    fit_reference,
    fit_weights,
    forward,
    generate,
    hmm_score,
    pack,
    validate_path,
)
from ies.history_roles_demo import load_config, run_demo
from ies.io import sha256


def path(initial, rows):
    return GeneratedPath(
        np.asarray(initial, dtype=int), np.asarray(rows, dtype=int).reshape(-1, len(initial))
    )


def model():
    return dict(
        probability=np.array([[0.1, 0.2, 0.3, 0.4], [0.65, 0.7, 0.55, 0.8]]),
        initial=np.array([0.3, 0.7]),
        transition=np.array([[0.8, 0.2], [0.1, 0.9]]),
        terminal=np.array([0.05, 0.1, 0.15, 0.2]),
    )


def extensions(prefix):
    initial, events = validate_path(prefix)
    alive = np.ones(len(initial), dtype=bool) if len(events) == 0 else events[-1] < 2
    if len(events):
        alive &= events[-1] >= 0
    for choices in product((0, 1, 2), repeat=int(alive.sum())):
        row = np.full(len(initial), -1)
        row[alive] = choices
        yield path(initial, np.vstack([events, row]))


def test_absorbing_support_and_private_input_rejection():
    validate_path(path([0, 2], [[2, 1], [-1, 2], [-1, -1]]))
    for bad in (
        path([0], [[2], [0]]),
        path([0], [[-1]]),
        path([4], [[0]]),
        GeneratedPath(np.array([0]), np.array([[0]]), "restricted"),
    ):
        with pytest.raises(ValueError):
            pack([bad])


def test_packing_uses_past_bits_and_distinguishes_termination():
    data = pack([path([1, 2], [[1, 0], [2, 1], [-1, 0]])])
    np.testing.assert_array_equal(data["success"][0, 0], [0, 1, 0, 0])
    np.testing.assert_array_equal(data["exposure"][0, 1], [1, 0, 0, 1])
    np.testing.assert_array_equal(data["terminal"][0, 1], [0, 0, 0, 1])
    np.testing.assert_array_equal(data["trials"][0, 2], [0, 1, 0, 0])
    assert data["exposure"].sum() == 5


def test_forward_backward_matches_hidden_state_enumeration():
    data = pack([path([1, 3], [[1, 0], [0, 1]])])
    m = model()
    score, gamma, xi = forward(data, m, posterior=True)
    e = np.exp(emissions(data, m["probability"])[0, :2])
    joint = m["initial"][:, None] * e[0, :, None] * m["transition"] * e[1, None]
    assert score[0] == pytest.approx(np.log(joint.sum()), abs=1e-13)
    np.testing.assert_allclose(xi[0, 0], joint / joint.sum(), atol=1e-13)
    np.testing.assert_allclose(gamma[0, 0], joint.sum(axis=1) / joint.sum(), atol=1e-13)
    np.testing.assert_allclose(gamma[0, 1], joint.sum(axis=0) / joint.sum(), atol=1e-13)
    assert not gamma[0, 2:].any() and not xi[0, 1:].any()


def test_complete_transition_law_and_all_prefix_marginals_normalize():
    empty = path([0, 2], [])
    first = list(extensions(empty))
    assert np.exp(hmm_score(pack(first), model())).sum() == pytest.approx(1, abs=1e-13)
    for prefix in first:
        full = list(extensions(prefix))
        assert np.exp(hmm_score(pack(full), model())).sum() == pytest.approx(
            np.exp(hmm_score(pack([prefix]), model())[0]), abs=1e-13
        )
    assert hmm_score(pack([empty]), model())[0] == pytest.approx(0, abs=1e-13)


def test_mixture_preserves_prefix_probabilities_and_component_bound():
    training = pack(generate("history_persistent", 32, [4, 8], 1))
    ref = fit_reference(training)
    bank = fit_bank(training, ref)
    prefix = path([1, 0], [[1, 0]])
    all_next = list(extensions(prefix))
    assert np.exp(bank_score(pack(all_next), bank)).sum() == pytest.approx(
        np.exp(bank_score(pack([prefix]), bank))[0], abs=1e-13
    )
    test = pack(generate("history_fresh", 12, [16], 90))
    mixture = bank_score(test, bank)
    for weight, component in zip(bank["weights"], bank["models"], strict=True):
        component = component | {"terminal": bank["terminal"]}
        assert np.all(-mixture <= -hmm_score(test, component) - np.log(weight) + 1e-12)


def test_truncation_is_marginalization_not_zero_filling():
    short = path([0], [[1]])
    zeros = path([0], [[1], [0], [0]])
    assert hmm_score(pack([short]), model())[0] > hmm_score(pack([zeros]), model())[0]
    dead = path([0], [[2]])
    padded = path([0], [[2], [-1], [-1]])
    assert hmm_score(pack([dead]), model())[0] == pytest.approx(
        hmm_score(pack([padded]), model())[0], abs=1e-13
    )


def test_future_append_cannot_change_past_features():
    short = path([0, 3], [[0, 1], [1, 2]])
    long = path([0, 3], [[0, 1], [1, 2], [1, -1], [0, -1]])
    a, b = pack([short]), pack([long])
    for key in ("exposure", "terminal", "trials", "success"):
        np.testing.assert_array_equal(a[key][:, :2], b[key][:, :2])
        assert not a[key][:, 2:].any()


def test_entity_permutation_and_history_ties_do_not_change_probabilities():
    paths = generate("hidden_persistent", 10, [8], 51)
    permutation = np.array([5, 7, 2, 0, 1, 6, 3, 4])
    permuted = [path(p.initial[permutation], p.events[:, permutation]) for p in paths]
    a, b = pack(paths), pack(permuted)
    for key in a:
        np.testing.assert_array_equal(a[key], b[key])
    ref = fit_reference(a)
    bank = fit_bank(a, ref)
    np.testing.assert_array_equal(bank_score(a, bank), bank_score(b, bank))
    np.testing.assert_array_equal(hmm_score(a, model()), hmm_score(b, model()))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_generated_policies_are_coupled_observed_prefixes(scenario):
    complete = generate(scenario, 12, [4, 8], 6)
    adaptive = generate(scenario, 12, [4, 8], 6, "adaptive")
    repeat = generate(scenario, 12, [4, 8], 6, "adaptive")
    for a, b, c in zip(complete, adaptive, repeat, strict=True):
        validate_path(a)
        validate_path(b)
        np.testing.assert_array_equal(a.initial, b.initial)
        np.testing.assert_array_equal(a.events[: len(b.events)], b.events)
        np.testing.assert_array_equal(b.events, c.events)
    assert sum(len(p.events) for p in adaptive) < 12 * 8


def test_weight_map_is_monotone_and_uses_subject_path_likelihood():
    scores = np.array([[-1, -7, -5], [-5, -1, -6], [-1, -8, -9]])
    weights, trace = fit_weights(scores)
    assert min(np.diff(trace)) >= -1e-12
    assert weights.sum() == pytest.approx(1)
    assert np.min(weights) >= 1 / (3 * 4)
    assert weights[0] > weights[1] > weights[2]


def test_markov_map_learning_monotonicity_and_unseen_roster_use():
    train = pack(generate("history_persistent", 40, [4, 8], 19, "adaptive"))
    ref = fit_reference(train)
    learned, diagnostics = fit_hmm(train, ref, 17, iterations=20)
    assert all(min(np.diff(t)) >= -1e-8 for t in diagnostics["objective_traces"])
    assert not diagnostics["global_optimum_claimed"]
    for k in (1, 16, 32, 128):
        evaluation = pack(generate("history_persistent", 2, [k], 22))
        assert np.isfinite(hmm_score(evaluation, learned)).all()
    assert learned["probability"].shape == (2, 4)


def test_role_bank_size_and_global_sign_symmetry():
    data = pack(generate("independent", 6, [4], 33))
    models = bank_models(fit_reference(data))
    assert len(models) == 33
    assert len(bank_models(fit_reference(data), shared_only=True)) == 5
    for m in models:
        reverse = m | {"probability": m["probability"][::-1]}
        np.testing.assert_allclose(forward(data, m), forward(data, reverse), atol=1e-13)


def test_resource_bounds_and_invalid_models_are_explicit():
    for args in (
        ("bad", 1, [4], 1),
        ("independent", True, [4], 1),
        ("independent", 1, [129], 1),
        ("independent", 1, [4], -1),
    ):
        with pytest.raises(ValueError):
            generate(*args)
    with pytest.raises(ValueError):
        fit_weights(np.array([[np.nan, 1]]))
    data = pack([path([0], [[1]])])
    with pytest.raises(ValueError):
        forward(data, model() | {"transition": np.ones((2, 2))})


def test_config_manifest_no_data_boundary_and_sanitized_failure(tmp_path, monkeypatch):
    config = dict(
        schema_version=1, data_class="synthetic", seeds=[1], patients=[32], evaluation_patients=64
    )
    location = tmp_path / "config.yaml"
    location.write_text(yaml.safe_dump(config))
    assert load_config(location)[0] == config
    assert parser().parse_args(["history-roles-demo"]).config.name == "synthetic_history_roles.yaml"
    monkeypatch.setattr("ies.history_roles_demo.SCENARIOS", ("independent",))
    directory = tmp_path / "run"
    result = run_demo(location, directory)
    assert result["evaluation_cases"] == 8
    manifest = json.loads((directory / "manifest.json").read_text())
    assert not manifest["clinical_inputs_used"] and not manifest["novel_algorithm_established"]
    assert manifest["fit_reused_without_refitting_for_unseen_rosters"]
    for name, digest in manifest["output_files_sha256"].items():
        assert sha256(directory / name) == digest
    with pytest.raises(FileExistsError):
        run_demo(location, directory)
    location.write_text(yaml.safe_dump(config | {"data_class": "restricted"}))
    with pytest.raises(ValueError):
        load_config(location)
    location.write_text(yaml.safe_dump(config))

    def fail(*args, **kwargs):
        raise ValueError("SECRET generated failure test payload")

    monkeypatch.setattr("ies.history_roles_demo.generate", fail)
    with pytest.raises(RuntimeError, match="Generated history-role experiment failed"):
        run_demo(location, tmp_path / "failure")
    assert "SECRET" not in (tmp_path / "failure" / "manifest.json").read_text()
