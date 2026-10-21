import numpy as np
import pytest

from ies.competition import batch_log_normalizer, score
from ies.factored_history import (
    FactoredFilter,
    binomial_table,
    count_plan,
    filter_factored,
    tilt_expectations,
)
from ies.hidden_history import filter_missing
from ies.hidden_history_audit import fixed_models
from ies.history_roles import GeneratedPath, pack


def path():
    return GeneratedPath(np.array([0, 2]), np.array([[1, 0], [0, 2], [1, -1]]))


def compare(a, b):
    np.testing.assert_allclose(a["log_increments"], b["log_increments"], atol=2e-12)
    lookup = {tuple(row): i for i, row in enumerate(b["histogram_states"])}
    index = [lookup[tuple(row)] for row in a["histogram_states"]]
    for field in ("posterior", "next_state_probability"):
        np.testing.assert_allclose(a[field], b[field][index], atol=2e-12)
    for p, q in zip(a["posteriors"], b["posteriors"], strict=True):
        np.testing.assert_allclose(p, q[index], atol=2e-12)


@pytest.mark.parametrize("missing", [0, 1, 2, 4, 8])
@pytest.mark.parametrize("theta", [0, -4])
def test_factored_filter_matches_sparse_likelihood_and_all_posteriors(missing, theta):
    model = fixed_models()["combined"]
    model["parameters"][:, 4] = theta
    initial = np.arange(missing) % 4
    compare(filter_factored(path(), initial, model), filter_missing(path(), initial, model))


def test_layered_normalizers_equal_existing_count_dynamic_program():
    model = fixed_models()["combined"]
    plan = count_plan(5)
    observed = np.array([2, 0, 1, 1])
    for parameters in model["parameters"]:
        p = 1 / (1 + np.exp(-parameters[:4]))
        actual = tilt_expectations(plan, observed, p, parameters[4])
        context = plan["counts"] + observed
        reference = batch_log_normalizer(context, parameters, np.ones(4))
        product_normalizer = context @ np.logaddexp(0, parameters[:4])
        np.testing.assert_allclose(np.log(actual), reference - product_normalizer, atol=2e-13)
    np.testing.assert_allclose(binomial_table(24, 0.6).sum(axis=0), 1, atol=2e-14)


def test_complete_observation_absorption_prefix_and_permutation():
    model = fixed_models()["combined"]
    empty = np.array([], dtype=int)
    for t in range(4):
        prefix = GeneratedPath(path().initial, path().events[:t])
        result = filter_factored(prefix, empty, model)
        assert result["log_probability"] == pytest.approx(
            score(pack([prefix]), model)[0], abs=2e-13
        )
    observed = GeneratedPath(np.array([0, 2]), np.array([[1, 0], [2, 2], [-1, -1]]))
    a = filter_factored(observed, np.array([1, 3, 2]), model)
    b = filter_factored(
        GeneratedPath(observed.initial[::-1], observed.events[:, ::-1]),
        np.array([3, 2, 1]),
        model,
    )
    compare(a, b)
    assert a["log_increments"][-1] == pytest.approx(0, abs=1e-13)
    prefix = GeneratedPath(observed.initial, observed.events[:1])
    first = filter_factored(prefix, np.array([1, 3, 2]), model)
    np.testing.assert_allclose(a["posteriors"][0], first["posterior"], atol=1e-14)


def test_large_missing_population_independent_deletion_identity():
    model = fixed_models()["combined"]
    model["parameters"][:, 4] = 0
    result = filter_factored(path(), np.arange(24) % 4, model)
    assert result["log_probability"] == pytest.approx(score(pack([path()]), model)[0], abs=1e-11)
    assert result["posterior"].sum() == pytest.approx(1, abs=1e-13)
    assert result["compound_transition_terms_materialized"] == 0


def test_extreme_bounded_parameters_remain_exact():
    model = fixed_models()["combined"]
    model["parameters"] = np.array([[-8, 8, -8, 8, -8], [8, -8, 8, -8, 0]], dtype=float)
    model["terminal"] = np.array([0.001, 0.999, 0.1, 0.9])
    initial = np.arange(4) % 4
    compare(filter_factored(path(), initial, model), filter_missing(path(), initial, model))


def test_invalid_roster_signed_model_and_private_support_rejected():
    model = fixed_models()["combined"]
    for missing in (np.zeros(25, dtype=int), np.array([0.0]), np.array([-1]), np.zeros((1, 1))):
        with pytest.raises(ValueError):
            filter_factored(path(), missing, model)
    with pytest.raises(ValueError):
        filter_factored(path(), np.array([0]), model | {"signs": np.array([1, -1, 1, -1])})
    with pytest.raises(ValueError):
        filter_factored(
            GeneratedPath(path().initial, path().events, "restricted"), np.array([0]), model
        )
    with pytest.raises(ValueError):
        FactoredFilter(2, model).filter(path(), np.array([0]))
    with pytest.raises(ValueError):
        filter_factored(
            GeneratedPath(np.zeros(128, dtype=int), np.zeros((0, 128), dtype=int)),
            np.array([0]),
            model,
        )
    assert all(not value.flags.writeable for value in count_plan(2)["layers"])


def test_audit_artifact_provenance_cli_and_failure(tmp_path, monkeypatch):
    import json

    from ies import factored_history_audit as audit
    from ies.cli import dispatch, parser
    from ies.io import sha256

    monkeypatch.setattr(audit, "SEEDS", (20261117,))
    monkeypatch.setattr(audit, "MISSING", (2,))
    directory = tmp_path / "audit"
    result = dispatch(parser().parse_args(["factored-history-audit", "--run-dir", str(directory)]))
    assert result["cases"] == 3 and result["model_fitted"] is False
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["clinical_inputs_used"] is False
    assert manifest["output_files_sha256"]["results.json"] == sha256(directory / "results.json")
    for name, digest in manifest["source_files_sha256"].items():
        assert sha256(audit.ROOT / name) == digest
    with pytest.raises(FileExistsError):
        audit.run_audit(directory)

    def fail():
        raise ValueError("forbidden-example-payload")

    monkeypatch.setattr(audit, "run_cases", fail)
    with pytest.raises(RuntimeError, match="Generated factored-history audit failed") as exception:
        audit.run_audit(tmp_path / "failed")
    assert "forbidden-example-payload" not in str(exception.value)
    text = (tmp_path / "failed" / "manifest.json").read_text()
    assert "forbidden-example-payload" not in text
    assert json.loads(text)["status"] == "failed"


def test_audit_source_stability_guard(tmp_path, monkeypatch):
    import json

    from ies import factored_history_audit as audit

    hashes = iter([{"example": "before"}, {"example": "after"}])
    monkeypatch.setattr(audit, "_source_hashes", lambda: next(hashes))
    monkeypatch.setattr(audit, "run_cases", lambda: [])
    with pytest.raises(RuntimeError, match="Generated factored-history audit failed"):
        audit.run_audit(tmp_path / "audit")
    manifest = json.loads((tmp_path / "audit" / "manifest.json").read_text())
    assert manifest["status"] == "failed" and "output_files_sha256" not in manifest
