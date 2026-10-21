from itertools import product

import numpy as np
import pytest

from ies.competition import count_emissions, features, field_prior, fit_competition, score
from ies.hidden_history import filter_missing
from ies.hidden_history_audit import entity_paths, fixed_models
from ies.hidden_learning import LearningDesign, MissingSubject, fit_missing, initialize
from ies.history_roles import (
    GeneratedPath,
    fit_hmm,
    fit_reference,
    forward_emissions,
    generate,
    pack,
)


def small_subject():
    return MissingSubject(GeneratedPath(np.array([0]), np.array([[1], [0], [1]])), np.array([1, 2]))


def test_smoothing_statistics_match_exhaustive_labeled_recurrent_paths():
    model = fixed_models()["combined"]
    subject = small_subject()
    design = LearningDesign([subject], model["signs"])
    expected = design.expectation(model, posterior=True)
    paths = entity_paths(3)
    complete = [
        GeneratedPath(
            np.array([0, 1, 2]), np.column_stack([subject.observed.events, paths[a], paths[b]])
        )
        for a, b in product(range(len(paths)), repeat=2)
    ]
    data = pack(complete)
    probabilities = np.exp(score(data, model))
    assert expected["log_probability"][0] == pytest.approx(np.log(probabilities.sum()), abs=2e-14)
    probabilities /= probabilities.sum()
    _, gamma, xi = forward_emissions(
        count_emissions(data, model), model["initial"], model["transition"], data["lengths"], True
    )
    x = features(data["success"].reshape(-1, 4), data["trials"].reshape(-1, 4), model["signs"])
    target = np.einsum("n,ntz,ntf->zf", probabilities, gamma, x.reshape(len(complete), 8, 5))
    np.testing.assert_allclose(expected["target"], target, atol=3e-13)
    np.testing.assert_allclose(expected["initial"], probabilities @ gamma[:, 0], atol=2e-14)
    np.testing.assert_allclose(
        expected["transition"], np.einsum("n,ntzq->zq", probabilities, xi), atol=2e-14
    )
    for name in ("terminal", "exposure"):
        np.testing.assert_allclose(
            expected[name], probabilities @ data[name].sum(axis=1), atol=3e-14
        )
    np.testing.assert_allclose(
        expected["context_weights"].sum(axis=0),
        np.einsum("n,ntz->z", probabilities, gamma),
        atol=3e-14,
    )
    np.testing.assert_allclose(
        expected["edge_posterior"].reshape(3, -1, 2).sum(axis=(1, 2)), 1, atol=2e-14
    )


def test_fisher_identity_matches_observed_likelihood_finite_differences():
    subject = small_subject()
    model = fixed_models()["combined"]
    design = LearningDesign([subject], model["signs"])
    expected = design.expectation(model)
    eps = 1e-5
    for z in range(2):
        cw, target = expected["context_weights"][:, z], expected["target"][z]
        _, gradient, _ = design.normalizer.objective(model["parameters"][z], (cw, target))
        log_gradient = -max(cw.sum(), 1) * gradient + field_prior(model["parameters"][z])[1]
        for j in range(5):
            delta = np.zeros((2, 5))
            delta[z, j] = eps
            plus = design.expectation(model | {"parameters": model["parameters"] + delta})[
                "log_probability"
            ].sum()
            minus = design.expectation(model | {"parameters": model["parameters"] - delta})[
                "log_probability"
            ].sum()
            assert (plus - minus) / (2 * eps) == pytest.approx(log_gradient[j], abs=2e-9)
    p = model["terminal"]
    gradient = expected["terminal"] / p - (expected["exposure"] - expected["terminal"]) / (1 - p)
    for j in range(4):
        delta = np.eye(4)[j] * eps
        plus = design.expectation(model | {"terminal": p + delta})["log_probability"].sum()
        minus = design.expectation(model | {"terminal": p - delta})["log_probability"].sum()
        assert (plus - minus) / (2 * eps) == pytest.approx(gradient[j], abs=1e-7)


def test_filter_equivalence_for_variable_prefix_lengths_and_empty_data():
    model = fixed_models()["combined"]
    p = small_subject().observed
    subjects = [
        MissingSubject(GeneratedPath(p.initial, p.events[:t]), np.array([1, 2])) for t in range(4)
    ]
    design = LearningDesign(subjects, model["signs"])
    result = design.expectation(model)
    reference = [
        filter_missing(s.observed, s.missing_initial, model)["log_probability"] for s in subjects
    ]
    np.testing.assert_allclose(result["log_probability"], reference, atol=2e-14)
    assert result["initial"].sum() == pytest.approx(3)
    assert result["transition"].sum() == pytest.approx(3)
    empty = LearningDesign(subjects[:1], model["signs"]).expectation(model)
    assert empty["target"].sum() == 0 and empty["log_probability"].sum() == 0


@pytest.mark.parametrize("single", [False, True])
def test_em_observed_map_monotonic_certified_and_inputs_unchanged(single):
    paths = generate("history_persistent", 20, [4], 15)
    subjects = [
        MissingSubject(GeneratedPath(p.initial[:2], p.events[:, :2]), p.initial[2:]) for p in paths
    ]
    data = pack([s.observed for s in subjects])
    reference = fit_reference(data)
    hmm, _ = fit_hmm(data, reference, 3, iterations=3)
    signs = np.ones(4, dtype=int)
    initial = initialize(hmm, signs, single, reference)
    snapshot = {k: v.copy() for k, v in initial.items()}
    design = LearningDesign(subjects, signs)
    learned, diagnostic = fit_missing(design, initial, iterations=5, single_state=single)
    assert min(np.diff(diagnostic["objective"])) >= -1e-8
    assert max(d["convex_gap"] for d in diagnostic["msteps"]) <= 2e-7
    assert diagnostic["global_optimum_claimed"] is False
    for k in initial:
        np.testing.assert_array_equal(initial[k], snapshot[k])
    assert np.isfinite(design.expectation(learned)["log_probability"]).all()
    if single:
        np.testing.assert_array_equal(learned["parameters"][0], learned["parameters"][1])


def test_no_missing_learning_reduces_to_existing_count_hmm_updates():
    paths = generate("history_fresh", 20, [4, 8], 16)
    data = pack(paths)
    reference = fit_reference(data)
    hmm, _ = fit_hmm(data, reference, 3, iterations=3)
    signs = np.ones(4, dtype=int)
    subjects = [MissingSubject(p, np.array([], dtype=int)) for p in paths]
    estimate, _ = fit_missing(LearningDesign(subjects, signs), initialize(hmm, signs), iterations=4)
    existing, _ = fit_competition(data, hmm, iterations=4, partitions=[signs])
    for key in estimate:
        np.testing.assert_allclose(estimate[key], existing[key], atol=2e-8)


def test_permutation_invariance_of_expectations():
    paths = generate("history_fresh", 2, [4], 29)
    subjects = [
        MissingSubject(GeneratedPath(p.initial[:2], p.events[:, :2]), p.initial[2:]) for p in paths
    ]
    permuted = [
        MissingSubject(
            GeneratedPath(s.observed.initial[::-1], s.observed.events[:, ::-1]),
            s.missing_initial[::-1],
        )
        for s in subjects
    ]
    model = fixed_models()["combined"]
    a = LearningDesign(subjects, model["signs"]).expectation(model)
    b = LearningDesign(permuted, model["signs"]).expectation(model)
    for key in a:
        np.testing.assert_allclose(a[key], b[key], atol=3e-14)


def test_reject_invalid_class_unknown_initial_history_bounds_and_partition():
    subject = small_subject()
    model = fixed_models()["combined"]
    signs = model["signs"]
    bad = [
        [],
        [subject] * 513,
        [MissingSubject(subject.observed, subject.missing_initial, "restricted")],
        [MissingSubject(subject.observed, np.array([-1]))],
        [MissingSubject(subject.observed, np.zeros(5, dtype=int))],
        [MissingSubject(subject.observed, np.zeros(2, dtype=float))],
    ]
    for subjects in bad:
        with pytest.raises(ValueError):
            LearningDesign(subjects, signs)
    design = LearningDesign([subject], signs)
    with pytest.raises(ValueError):
        design.expectation(model | {"signs": -signs})
    with pytest.raises(ValueError):
        fit_missing(design, model, iterations=31)
    with pytest.raises(ValueError):
        fit_missing(design, model, single_state=True)


def test_mask_does_not_expose_hidden_realizations_and_evaluation_matches_product_hmm():
    from ies.hidden_learning_demo import evaluate, mask_paths

    p = GeneratedPath(np.arange(4), np.zeros((8, 4), dtype=int))
    s = mask_paths([p], 2, 31)[0]
    other = p.events.copy()
    other[:, s.missing_initial] = 1
    changed = mask_paths([GeneratedPath(p.initial, other)], 2, 31)[0]
    np.testing.assert_array_equal(s.observed.events, changed.observed.events)
    np.testing.assert_array_equal(s.missing_initial, changed.missing_initial)
    model = fixed_models()["independent"]
    hmm = dict(
        probability=1 / (1 + np.exp(-model["parameters"][:, :4])),
        terminal=model["terminal"],
        initial=model["initial"],
        transition=model["transition"],
    )
    metrics = evaluate(
        [s, changed], dict(product_hmm=hmm, count_only=model, combined=model, naive_deleted=model)
    )
    assert abs(metrics["product_hmm"]["combined_minus_reference_nll"]) < 1e-13


def test_generated_learning_artifacts_cli_and_sanitized_failure(tmp_path, monkeypatch):
    import json

    from ies import hidden_learning_demo as demo
    from ies.cli import dispatch, parser
    from ies.io import sha256

    config = tmp_path / "config.yaml"
    config.write_text(
        "schema_version: 1\ndata_class: synthetic\nseeds: [3]\n"
        "patients: 32\nevaluation_patients: 64\n"
    )
    monkeypatch.setattr(demo, "SCENARIOS", ("independent",))
    monkeypatch.setattr(demo, "fit_models", lambda subjects, seed: ({}, {}, {}))
    monkeypatch.setattr(demo, "evaluate", lambda subjects, models: {})
    out = tmp_path / "run"
    result = dispatch(
        parser().parse_args(
            ["hidden-learning-demo", "--config", str(config), "--run-dir", str(out)]
        )
    )
    assert result["fits"] == 2 and result["cases"] == 12
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["clinical_inputs_used"] is False
    assert manifest["config_file_sha256"] == sha256(config)
    for name, digest in manifest["output_files_sha256"].items():
        assert sha256(out / name) == digest
    with pytest.raises(FileExistsError):
        demo.run_demo(config, out)

    def fail(*args):
        raise ValueError("forbidden-example-payload")

    monkeypatch.setattr(demo, "fit_models", fail)
    with pytest.raises(RuntimeError, match="Generated missing-history learning benchmark failed"):
        demo.run_demo(config, tmp_path / "failed")
    text = (tmp_path / "failed" / "manifest.json").read_text()
    assert "forbidden-example-payload" not in text and json.loads(text)["status"] == "failed"
