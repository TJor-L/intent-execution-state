from itertools import product

import numpy as np
import pytest

from ies import cardinality, gdpp
from ies.competition import score as count_score
from ies.hidden_history import filter_missing
from ies.hidden_history_audit import entity_paths, fixed_models
from ies.history_roles import GeneratedPath, pack


def patterns(k):
    return np.array(list(product((0, 1), repeat=k)), dtype=int).reshape(2**k, k)


def reference_model(factor=True):
    model = fixed_models()["combined"]
    rng = np.random.default_rng(20261114)
    return model | {"factors": rng.normal(0, 0.5, (2, 4, 4)) if factor else np.zeros((2, 4, 4))}


def test_general_dense_law_matches_subset_enumeration_and_cardinality_marginals():
    rng = np.random.default_rng(1)
    a = rng.normal(size=(6, 6))
    kernel = np.eye(6) + a @ a.T
    weights = rng.normal(size=7)
    distribution = gdpp.law(kernel, weights)
    outcomes = patterns(6)
    unnormalized = np.array(
        [
            np.linalg.det(kernel[np.ix_(row == 1, row == 1)]) * np.exp(weights[row.sum()])
            for row in outcomes
        ]
    )
    probability = np.exp(gdpp.log_probability(distribution, outcomes))
    np.testing.assert_allclose(probability, unnormalized / unnormalized.sum(), atol=1e-14)
    np.testing.assert_allclose(
        np.bincount(outcomes.sum(axis=1), weights=probability),
        distribution["cardinality_probability"],
        atol=1e-14,
    )
    ordinary = gdpp.law(kernel, np.zeros(7))
    assert ordinary["log_normalizer"] == pytest.approx(np.linalg.slogdet(kernel + np.eye(6))[1])


@pytest.mark.parametrize("k", [0, 1, 4, 8, 16, 64, 128])
def test_diagonal_law_is_count_emission_at_all_fixed_sizes(k):
    rng = np.random.default_rng(20261114 + k)
    fields = rng.uniform(-3, 3, k)
    weights = -3 * (np.arange(k + 1) - k / 2) ** 2 / max(k, 1)
    count = cardinality.count_distribution(fields, weights)
    dpp = gdpp.law(np.diag(np.exp(fields)), weights)
    outcomes = patterns(k) if k <= 8 else rng.integers(0, 2, (12, k))
    np.testing.assert_allclose(
        gdpp.log_probability(dpp, outcomes),
        cardinality.log_probability(count, outcomes),
        atol=3e-12,
        rtol=0,
    )
    np.testing.assert_allclose(
        dpp["cardinality_probability"], count["count_probability"], atol=1e-13
    )


def test_group_kernel_normalization_and_minors_match_dense_reference():
    rng = np.random.default_rng(4)
    p = np.array([-1.1, 0.2, 0.8, -0.4, -2])
    factor = rng.normal(0, 0.5, (4, 4))
    for history in (np.array([], dtype=int), np.array([0, 0, 2, 2, 2, 3]), np.arange(8) % 4):
        k = len(history)
        kernel = gdpp.history_kernel(history, p, factor)
        weights = p[4] * (np.arange(k + 1) - k / 2) ** 2 / max(k, 1)
        dense = gdpp.law(kernel, weights)
        outcomes = patterns(k)
        counts = np.bincount(history, minlength=4)
        success = outcomes @ np.eye(4, dtype=int)[history]
        trials = np.tile(counts, (len(outcomes), 1))
        reduced = gdpp.history_log_probability(success, trials, p, factor)
        np.testing.assert_allclose(reduced, gdpp.log_probability(dense, outcomes), atol=1e-13)
        assert np.exp(reduced).sum() == pytest.approx(1, abs=2e-14)
        assert gdpp.history_normalizer(counts[None], p, factor)[0] == pytest.approx(
            dense["log_normalizer"], abs=1e-13
        )
        perm = rng.permutation(k)
        np.testing.assert_allclose(
            gdpp.history_kernel(history[perm], p, factor), kernel[np.ix_(perm, perm)], atol=1e-14
        )


def test_minor_gradients_match_finite_differences():
    p, factor = reference_model()["parameters"][0], reference_model()["factors"][0]
    counts = np.array([[0, 0, 0, 0], [1, 2, 3, 0], [0, 4, 0, 1]])
    _, fields, factors = gdpp.log_minor(counts, p, factor, gradient=True)
    eps = 1e-5
    for h in range(4):
        delta = np.eye(5)[h] * eps
        actual = (
            gdpp.log_minor(counts, p + delta, factor) - gdpp.log_minor(counts, p - delta, factor)
        ) / (2 * eps)
        np.testing.assert_allclose(actual, fields[:, h], atol=1e-9)
    for h, j in product(range(4), repeat=2):
        delta = np.zeros((4, 4))
        delta[h, j] = eps
        actual = (
            gdpp.log_minor(counts, p, factor + delta) - gdpp.log_minor(counts, p, factor - delta)
        ) / (2 * eps)
        np.testing.assert_allclose(actual, factors[:, h, j], atol=1e-9)


def test_recurrent_diagonal_scores_and_missing_posteriors_reduce_to_count_model():
    m = reference_model(False)
    path = GeneratedPath(np.array([0, 2]), np.array([[1, 0], [0, 2], [1, -1]]))
    for length in range(4):
        prefix = GeneratedPath(path.initial, path.events[:length])
        np.testing.assert_allclose(
            gdpp.score(pack([prefix]), m), count_score(pack([prefix]), m), atol=1e-13
        )
        for missing in (np.array([], dtype=int), np.array([1, 3])):
            result = gdpp.filter_history(prefix, missing, m)
            reference = filter_missing(prefix, missing, m)
            for field in (
                "log_probability",
                "posterior",
                "next_state_probability",
                "log_increments",
            ):
                np.testing.assert_allclose(result[field], reference[field], atol=1e-13)


def test_nondiagonal_hidden_filter_matches_all_labeled_paths_and_prefixes():
    m = reference_model()
    rows = entity_paths(3)
    triples = list(product(range(len(rows)), repeat=3))
    full = [GeneratedPath(np.array([0, 1, 2]), rows[list(i)].T) for i in triples]
    probability = np.exp(gdpp.score(pack(full), m))
    assert probability.sum() == pytest.approx(1, abs=2e-13)
    expected = np.bincount(np.array(triples)[:, 0], weights=probability)
    for i, row in enumerate(rows):
        observed = GeneratedPath(np.array([0]), row[:, None])
        result = gdpp.filter_history(observed, np.array([1, 2]), m)
        assert np.exp(result["log_probability"]) == pytest.approx(expected[i], abs=1e-13)
        assert result["posterior"].sum() == pytest.approx(1)
    prefix = GeneratedPath(np.array([0, 2]), np.array([[1, 0], [0, 2]]))
    missing = np.array([1, 3])
    result = gdpp.filter_history(prefix, missing, m)
    future = [
        gdpp.filter_history(
            GeneratedPath(prefix.initial, np.r_[prefix.events, [[y, -1]]]), missing, m
        )["log_probability"]
        for y in (0, 1, 2)
    ]
    assert np.exp(np.array(future) - result["log_probability"]).sum() == pytest.approx(1, abs=1e-13)
    permuted = gdpp.filter_history(
        GeneratedPath(prefix.initial[::-1], prefix.events[:, ::-1]), missing[::-1], m
    )
    np.testing.assert_allclose(result["posterior"], permuted["posterior"], atol=1e-13)


def test_fixed_cardinality_is_outside_invariant_ordinary_dpp_covariance_bound():
    k, count = 8, 4
    weights = np.full(k + 1, -np.inf)
    weights[count] = 0
    distribution = gdpp.law(np.eye(k), weights)
    outcomes = patterns(k)
    probability = np.exp(gdpp.log_probability(distribution, outcomes))
    marginals = probability @ outcomes
    covariance = (probability * outcomes[:, 0]) @ outcomes[:, 1] - marginals[0] * marginals[1]
    assert probability.sum() == pytest.approx(1)
    assert np.all(probability[outcomes.sum(axis=1) != count] == 0)
    assert covariance == pytest.approx(-0.25 / (k - 1))
    assert covariance < -1 / k**2
    # Kernel restriction, not a bound for all DPP representations or mixtures.
    for diagonal_eigenvalue, constant_eigenvalue in product((0.1, 0.4, 0.9), repeat=2):
        beta = (constant_eigenvalue - diagonal_eigenvalue) / k
        kernel = np.eye(k) * diagonal_eigenvalue + np.full((k, k), beta)
        assert np.linalg.eigvalsh(kernel).min() > 0
        assert np.linalg.eigvalsh(kernel).max() < 1
        assert -(kernel[0, 1] ** 2) >= -1 / k**2


def test_invalid_support_parameters_and_private_paths_are_rejected():
    for kernel in (np.zeros((2, 2)), np.array([[1, 1], [0, 1]]), np.eye(129), np.eye(2) * np.nan):
        with pytest.raises(ValueError):
            gdpp.law(kernel, np.zeros(len(kernel) + 1))
    for weights in (np.zeros(2), np.array([0, 0, np.inf]), np.full(3, -np.inf)):
        with pytest.raises(ValueError):
            gdpp.law(np.eye(2), weights)
    for counts in (
        np.zeros((1, 4)),
        np.array([[-1, 0, 0, 0]]),
        np.full((1, 4), 128),
        np.full((1, 4), 2**63, dtype=np.uint64),
    ):
        with pytest.raises(ValueError):
            gdpp.history_normalizer(counts, np.zeros(5), np.zeros((4, 4)))
    with pytest.raises(ValueError):
        gdpp.history_log_probability(
            np.zeros((1, 4), dtype=int), np.zeros((1, 4), dtype=int), [], np.zeros((4, 4))
        )
    with pytest.raises(ValueError):
        gdpp.history_log_probability(
            np.ones((1, 4), dtype=int), np.zeros((1, 4), dtype=int), np.zeros(5), np.zeros((4, 4))
        )
    with pytest.raises(ValueError):
        gdpp.validate_history_model(reference_model() | {"signs": np.array([1, -1, 1, -1])})
    with pytest.raises(ValueError):
        gdpp.filter_history(
            GeneratedPath(np.array([0]), np.array([[0]]), "restricted"),
            np.array([1]),
            reference_model(),
        )
    for value in (np.full((3, 2), np.nan), np.zeros((2, 2)), np.ones((3, 2))):
        with pytest.raises(ValueError):
            filter_missing(
                GeneratedPath(np.array([0]), np.array([[0]])),
                np.array([], dtype=int),
                reference_model(),
                emission=lambda success, trials, v=value: v,
            )


def test_audit_artifacts_cli_no_overwrite_and_sanitized_failure(tmp_path, monkeypatch):
    import json

    from ies import gdpp_audit as audit
    from ies.cli import dispatch, parser
    from ies.io import sha256

    monkeypatch.setattr(audit, "SEEDS", (20261114,))
    monkeypatch.setattr(audit, "SIZES", (0, 4))
    monkeypatch.setattr(audit, "recurrent_cases", lambda: [])
    directory = tmp_path / "audit"
    result = dispatch(parser().parse_args(["gdpp-containment-audit", "--run-dir", str(directory)]))
    assert result["static_cases"] == 2 and result["covariance_cases"] == 4
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["model_fitted"] is False and manifest["clinical_inputs_used"] is False
    assert manifest["output_files_sha256"]["results.json"] == sha256(directory / "results.json")
    for name, digest in manifest["source_files_sha256"].items():
        assert sha256(audit.ROOT / name) == digest
    with pytest.raises(FileExistsError):
        audit.run_audit(directory)

    def fail():
        raise ValueError("forbidden-example-payload")

    monkeypatch.setattr(audit, "static_cases", fail)
    with pytest.raises(RuntimeError, match="Generated GDPP containment audit failed") as exception:
        audit.run_audit(tmp_path / "failed")
    assert "forbidden-example-payload" not in str(exception.value)
    text = (tmp_path / "failed" / "manifest.json").read_text()
    assert "forbidden-example-payload" not in text
    assert json.loads(text)["status"] == "failed"


def test_audit_rejects_source_drift(tmp_path, monkeypatch):
    import json

    from ies import gdpp_audit as audit

    hashes = iter([{"example": "before"}, {"example": "after"}])
    monkeypatch.setattr(audit, "_source_hashes", lambda: next(hashes))
    for name in ("static_cases", "recurrent_cases", "covariance_cases"):
        monkeypatch.setattr(audit, name, lambda: [])
    with pytest.raises(RuntimeError, match="Generated GDPP containment audit failed"):
        audit.run_audit(tmp_path / "audit")
    manifest = json.loads((tmp_path / "audit" / "manifest.json").read_text())
    assert manifest["status"] == "failed" and "output_files_sha256" not in manifest
