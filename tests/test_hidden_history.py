from itertools import product
from math import comb

import numpy as np
import pytest

from ies.competition import count_emissions, score
from ies.hidden_history import filter_missing, histogram_plan
from ies.history_roles import GeneratedPath, forward_emissions, pack


def model(theta=-3.0):
    return dict(
        parameters=np.array([[-1.0, 0.7, -0.5, 0.4, theta], [0.3, -0.9, 0.8, -0.2, theta]]),
        signs=np.array([1, -1, -1, 1]),
        terminal=np.array([0.1, 0.15, 0.2, 0.25]),
        initial=np.array([0.4, 0.6]),
        transition=np.array([[0.9, 0.1], [0.2, 0.8]]),
    )


def entity_paths(length):
    paths = [()]
    for _ in range(length):
        paths = [(*p, event) for p in paths for event in ((-1,) if 2 in p else (0, 1, 2))]
    return np.array(paths)


def final_hidden_counts(initial, events):
    h = initial.copy()
    alive = np.ones(len(h), dtype=bool)
    for row in events:
        survivor = alive & (row != 2)
        h[survivor] = 2 * (h[survivor] % 2) + row[survivor]
        alive = survivor
    return tuple(np.r_[np.bincount(h[alive], minlength=4), (~alive).sum()])


@pytest.mark.parametrize("theta", [0.0, -3.0])
def test_exact_labeled_path_sum_and_hidden_histogram_posterior(theta):
    m = model(theta)
    paths = entity_paths(3)
    triples = list(product(range(len(paths)), repeat=3))
    complete = [GeneratedPath(np.array([0, 1, 2]), paths[list(indices)].T) for indices in triples]
    data = pack(complete)
    probability = np.exp(score(data, m))
    assert probability.sum() == pytest.approx(1, abs=1e-13)
    _, gamma, _ = forward_emissions(
        count_emissions(data, m), m["initial"], m["transition"], data["lengths"], True
    )
    for i, path in enumerate(paths):
        result = filter_missing(GeneratedPath(np.array([0]), path[:, None]), np.array([1, 2]), m)
        selected = np.array([j for j, indices in enumerate(triples) if indices[0] == i])
        total = probability[selected].sum()
        assert np.exp(result["log_probability"]) == pytest.approx(total, abs=2e-14)
        states = {tuple(s): k for k, s in enumerate(result["histogram_states"])}
        posterior = np.zeros_like(result["posterior"])
        for j in selected:
            counts = final_hidden_counts(np.array([1, 2]), complete[j].events[:, 1:])
            posterior[states[counts]] += probability[j] * gamma[j, 2]
        np.testing.assert_allclose(result["posterior"], posterior / total, atol=2e-13)
        np.testing.assert_allclose(
            result["next_state_probability"], result["posterior"] @ m["transition"], atol=1e-14
        )


def test_full_observation_reduction_and_prefix_filtering_consistency():
    m = model()
    p = GeneratedPath(np.array([0, 2]), np.array([[1, 0], [0, 2], [1, -1]]))
    empty = np.array([], dtype=int)
    complete = filter_missing(p, empty, m)
    assert complete["log_probability"] == pytest.approx(score(pack([p]), m)[0], abs=1e-13)
    for length in range(4):
        prefix = GeneratedPath(p.initial, p.events[:length])
        result = filter_missing(prefix, np.array([1, 3]), m)
        all_result = filter_missing(p, np.array([1, 3]), m)
        np.testing.assert_allclose(result["log_increments"], all_result["log_increments"][:length])
        for a, b in zip(result["posteriors"], all_result["posteriors"][:length], strict=True):
            np.testing.assert_allclose(a, b, atol=1e-14)
        assert result["posterior"].sum() == pytest.approx(1)


def test_zero_competition_is_consistent_under_whole_entity_deletion():
    m = model(0)
    p = GeneratedPath(np.array([0, 2]), np.array([[1, 0], [0, 2], [1, -1]]))
    actual_smaller = score(pack([p]), m)[0]
    for missing in (np.array([3]), np.array([0, 1, 2, 3])):
        assert filter_missing(p, missing, m)["log_probability"] == pytest.approx(
            actual_smaller, abs=2e-13
        )


def test_competition_entity_deletion_is_not_marginalization_and_next_law_normalizes():
    m = model(-5)
    initial = np.array([0])
    missing = np.array([0, 0])
    paths = entity_paths(3)
    probabilities, deleted = [], []
    for path in paths:
        p = GeneratedPath(initial, path[:, None])
        probabilities.append(np.exp(filter_missing(p, missing, m)["log_probability"]))
        deleted.append(np.exp(score(pack([p]), m)[0]))
    assert sum(probabilities) == pytest.approx(1, abs=1e-13)
    assert sum(deleted) == pytest.approx(1, abs=1e-13)
    assert np.abs(np.array(probabilities) - deleted).sum() / 2 > 0.03
    prefix = GeneratedPath(initial, np.array([[1], [0]]))
    old = filter_missing(prefix, missing, m)["log_probability"]
    following = [
        filter_missing(GeneratedPath(initial, np.r_[prefix.events, [[y]]]), missing, m)[
            "log_probability"
        ]
        for y in (0, 1, 2)
    ]
    assert np.exp(np.array(following) - old).sum() == pytest.approx(1, abs=1e-13)


def test_observed_and_hidden_permutation_and_observed_absorption():
    m = model()
    p = GeneratedPath(np.array([0, 3]), np.array([[1, 0], [2, 2], [-1, -1], [-1, -1]]))
    result = filter_missing(p, np.array([0, 1, 3]), m)
    permuted = filter_missing(
        GeneratedPath(p.initial[::-1], p.events[:, ::-1]), np.array([3, 0, 1]), m
    )
    np.testing.assert_allclose(result["posterior"], permuted["posterior"], atol=1e-14)
    np.testing.assert_allclose(result["log_increments"], permuted["log_increments"], atol=1e-14)
    np.testing.assert_allclose(result["log_increments"][2:], 0, atol=2e-14)


def test_histogram_state_term_counts_and_absorbing_hidden_state():
    for b in (0, 1, 2, 4, 8):
        plan = histogram_plan(b)
        assert len(plan["states"]) == comb(b + 4, 4)
        assert len(plan["source"]) == comb(b + 12, 12)
        np.testing.assert_array_equal(plan["states"].sum(axis=1), b)
        dead = np.flatnonzero(plan["states"][:, 4] == b)[0]
        mask = plan["source"] == dead
        assert mask.sum() == 1 and plan["target"][mask][0] == dead
        assert plan["log_multiplicity"][mask][0] == 0
        assert all(not value.flags.writeable for value in plan.values())


def test_invalid_support_class_model_and_resources():
    p = GeneratedPath(np.array([0]), np.zeros((1, 1), dtype=int))
    for missing in (np.array([0.0]), np.array([-1]), np.zeros(9, dtype=int), np.zeros((1, 1))):
        with pytest.raises(ValueError):
            filter_missing(p, missing, model())
    with pytest.raises(ValueError):
        filter_missing(GeneratedPath(p.initial, p.events, "restricted"), np.array([0]), model())
    with pytest.raises(ValueError):
        filter_missing(
            GeneratedPath(np.zeros(128, dtype=int), np.zeros((0, 128), dtype=int)),
            np.array([0]),
            model(),
        )
    for field, value in (
        ("parameters", np.full((2, 5), np.nan)),
        ("parameters", np.full((2, 5), 1)),
        ("initial", np.array([0.3, 0.3])),
        ("transition", np.ones((2, 2))),
        ("terminal", np.zeros(4)),
        ("signs", np.ones(3)),
    ):
        with pytest.raises(ValueError):
            filter_missing(p, np.array([0]), model() | {field: value})
    with pytest.raises(ValueError):
        histogram_plan(9)


def test_artifact_hashes_cli_no_overwrite_and_sanitized_failure(tmp_path, monkeypatch):
    import json

    from ies import hidden_history_audit as audit
    from ies.cli import dispatch, parser
    from ies.io import sha256

    monkeypatch.setattr(audit, "scaling_cases", lambda: [])
    directory = tmp_path / "audit"
    result = dispatch(parser().parse_args(["hidden-history-audit", "--run-dir", str(directory)]))
    assert result["exactness_cases"] == 3
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["clinical_inputs_used"] is False
    assert manifest["model_fitted"] is False
    assert manifest["output_files_sha256"]["results.json"] == sha256(directory / "results.json")
    for name, digest in manifest["source_files_sha256"].items():
        assert sha256(audit.ROOT / name) == digest
    with pytest.raises(FileExistsError):
        audit.run_audit(directory)

    def fail():
        raise ValueError("forbidden-example-payload")

    monkeypatch.setattr(audit, "exhaustive_cases", fail)
    failed = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="Generated hidden-history audit failed") as exception:
        audit.run_audit(failed)
    assert "forbidden-example-payload" not in str(exception.value)
    text = (failed / "manifest.json").read_text()
    assert "forbidden-example-payload" not in text
    assert json.loads(text)["status"] == "failed"


def test_audit_detects_changed_source_before_marking_complete(tmp_path, monkeypatch):
    import json

    from ies import hidden_history_audit as audit

    hashes = iter([{"example": "before"}, {"example": "after"}])
    monkeypatch.setattr(audit, "_source_hashes", lambda: next(hashes))
    monkeypatch.setattr(audit, "exhaustive_cases", lambda: [])
    monkeypatch.setattr(audit, "scaling_cases", lambda: [])
    with pytest.raises(RuntimeError, match="Generated hidden-history audit failed"):
        audit.run_audit(tmp_path / "run")
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert "output_files_sha256" not in manifest
