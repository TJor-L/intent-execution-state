import numpy as np
import pytest

from ies.competition import field_prior
from ies.factored_history import FactoredFilter, filter_factored, tilt_expectations
from ies.factored_learning import DifferentiableFilter, _tilt_value_gradient, perturb
from ies.hidden_history_audit import fixed_models
from ies.hidden_learning import LearningDesign, MissingSubject
from ies.history_roles import GeneratedPath


def path():
    return GeneratedPath(np.array([0, 2]), np.array([[1, 0], [0, 2], [1, -1]]))


def sparse_gradient(subject, model):
    design = LearningDesign([subject], model["signs"])
    expected = design.expectation(model, posterior=True)
    parameters = []
    for z in range(2):
        cw, target = expected["context_weights"][:, z], expected["target"][z]
        _, gradient, _ = design.normalizer.objective(model["parameters"][z], (cw, target))
        parameters.append(-max(cw.sum(), 1) * gradient + field_prior(model["parameters"][z])[1])
    return expected, dict(
        parameters=np.array(parameters),
        terminal_logits=expected["terminal"] - expected["exposure"] * model["terminal"],
        initial_logits=expected["initial"]
        - (model["initial"] if len(subject.observed.events) else 0),
        transition_logits=expected["transition"]
        - expected["transition"].sum(axis=1, keepdims=True) * model["transition"],
    )


@pytest.mark.parametrize("missing", [0, 1, 2, 4])
def test_exact_smoothing_and_gradients_equal_sparse_expected_statistics(missing):
    model = fixed_models()["combined"]
    subject = MissingSubject(path(), np.arange(missing) % 4)
    engine = DifferentiableFilter(missing, model)
    result = engine.likelihood_gradient(subject.observed, subject.missing_initial)
    expected, gradient = sparse_gradient(subject, model)
    assert result["log_probability"] == pytest.approx(expected["log_probability"][0], abs=1e-12)
    for key in gradient:
        np.testing.assert_allclose(result["gradient"][key], gradient[key], atol=2e-12)
    for key in ("initial", "transition"):
        np.testing.assert_allclose(result[key], expected[key], atol=2e-12)
    from ies.hidden_history import histogram_plan

    plan = histogram_plan(missing)
    weights = expected["edge_posterior"].reshape(3, -1, 2)
    target_posterior = np.array(
        [
            np.column_stack(
                [
                    np.bincount(plan["target"], weights=w[:, z], minlength=len(plan["states"]))
                    for z in range(2)
                ]
            )
            for w in weights
        ]
    )
    lookup = {tuple(s): i for i, s in enumerate(plan["states"])}
    index = [lookup[tuple(s)] for s in result["histogram_states"]]
    np.testing.assert_allclose(
        result["smoothed_histograms"], target_posterior[:, index], atol=2e-12
    )


def test_supported_forward_adjoint_dot_product_with_signed_cotangent():
    model = fixed_models()["combined"]
    engine = DifferentiableFilter(4, model)
    rng = np.random.default_rng(1)
    before = np.zeros(engine.plan["shape"] + (2,))
    before[engine.indices] = rng.random((len(engine.indices[0]), 2))
    before /= before.sum()
    adjoint = rng.normal(size=before.shape)
    trials, success = np.array([2, 0, 1, 1]), np.array([1, 0, 1, 0])
    value = engine.step(before, trials, success)
    back, _, _ = engine.step_pullback(before, adjoint, trials, success)
    assert np.sum(value * adjoint) == pytest.approx(np.sum(before * back), abs=1e-13)


def test_all_likelihood_parameter_derivatives_against_finite_differences():
    model = fixed_models()["combined"]
    missing = np.array([1, 3])
    result = DifferentiableFilter(2, model).likelihood_gradient(path(), missing)
    epsilon = 1e-5
    for key, values in result["gradient"].items():
        for index in np.ndindex(values.shape):
            direction = {k: np.zeros_like(v) for k, v in result["gradient"].items()}
            direction[key][index] = 1
            a = filter_factored(path(), missing, perturb(model, direction, epsilon))[
                "log_probability"
            ]
            b = filter_factored(path(), missing, perturb(model, direction, -epsilon))[
                "log_probability"
            ]
            assert (a - b) / (2 * epsilon) == pytest.approx(values[index], abs=2e-8)
    assert result["gradient"]["initial_logits"].sum() == pytest.approx(0, abs=1e-13)
    np.testing.assert_allclose(result["gradient"]["transition_logits"].sum(axis=1), 0, atol=1e-13)


def test_layered_polynomial_derivatives_match_independent_normalizer():
    model = fixed_models()["combined"]
    engine = DifferentiableFilter(3, model)
    observed = np.array([0, 1, 2, 0])
    parameters = model["parameters"][0]
    actual, derivative = _tilt_value_gradient(
        engine.plan, observed, engine.probability[0], parameters[4]
    )
    np.testing.assert_allclose(
        actual,
        tilt_expectations(engine.plan, observed, engine.probability[0], parameters[4]),
        atol=1e-14,
    )
    epsilon = 1e-5
    for j in range(5):
        values = []
        for sign in (1, -1):
            p = parameters + sign * epsilon * np.eye(5)[j]
            values.append(tilt_expectations(engine.plan, observed, 1 / (1 + np.exp(-p[:4])), p[4]))
        np.testing.assert_allclose(
            (values[0] - values[1]) / (2 * epsilon), derivative[:, j], atol=2e-10
        )


def test_empty_prefix_permutation_absorption_and_inputs_unchanged():
    model = fixed_models()["combined"]
    snapshot = {k: v.copy() for k, v in model.items()}
    engine = DifferentiableFilter(2, model)
    observed = GeneratedPath(path().initial, np.empty((0, 2), dtype=int))
    empty = engine.likelihood_gradient(observed, np.array([1, 3]))
    assert empty["log_probability"] == 0 and empty["smoothed_histograms"].shape == (0, 15, 2)
    for value in empty["gradient"].values():
        np.testing.assert_array_equal(value, 0)
    a = engine.likelihood_gradient(path(), np.array([1, 3]))
    b = engine.likelihood_gradient(
        GeneratedPath(path().initial[::-1], path().events[:, ::-1]), np.array([3, 1])
    )
    for key in a["gradient"]:
        np.testing.assert_allclose(a["gradient"][key], b["gradient"][key], atol=1e-12)
    prefix = GeneratedPath(np.array([0]), np.array([[2]]))
    tail = GeneratedPath(np.array([0]), np.array([[2], [-1], [-1]]))
    a = engine.likelihood_gradient(prefix, np.array([1, 3]))
    b = engine.likelihood_gradient(tail, np.array([1, 3]))
    for key in a["gradient"]:
        np.testing.assert_allclose(a["gradient"][key], b["gradient"][key], atol=2e-12)
    for key in model:
        np.testing.assert_array_equal(model[key], snapshot[key])


def test_large_hidden_direction_and_private_input_rejection():
    model = fixed_models()["combined"]
    engine = DifferentiableFilter(16, model)
    missing = np.arange(16) % 4
    result = engine.likelihood_gradient(path(), missing)
    rng = np.random.default_rng(20261120)
    direction = {k: rng.normal(0, 0.1, v.shape) for k, v in result["gradient"].items()}
    analytic = sum(np.sum(direction[k] * v) for k, v in result["gradient"].items())
    eps = 1e-5
    scores = [
        FactoredFilter(16, perturb(model, direction, sign * eps)).filter(path(), missing)[
            "log_probability"
        ]
        for sign in (1, -1)
    ]
    assert (scores[0] - scores[1]) / (2 * eps) == pytest.approx(analytic, abs=2e-8)
    with pytest.raises(ValueError):
        engine.likelihood_gradient(
            GeneratedPath(path().initial, path().events, "restricted"), missing
        )
    with pytest.raises(ValueError):
        DifferentiableFilter(25, model)


def test_extreme_parameters_and_empty_sparse_reduction():
    model = fixed_models()["combined"]
    model["parameters"] = np.array([[-8, 8, -8, 8, -8], [8, -8, 8, -8, 0]], dtype=float)
    model["terminal"] = np.array([0.001, 0.999, 0.1, 0.9])
    engine = DifferentiableFilter(4, model)
    for observed in (path(), GeneratedPath(path().initial, path().events[:0])):
        subject = MissingSubject(observed, np.arange(4))
        result = engine.likelihood_gradient(observed, subject.missing_initial)
        _, reference = sparse_gradient(subject, model)
        for key in reference:
            np.testing.assert_allclose(result["gradient"][key], reference[key], atol=2e-10)


def test_audit_cli_provenance_and_sanitized_failure(tmp_path, monkeypatch):
    import json

    from ies import factored_learning_audit as audit
    from ies.cli import dispatch, parser
    from ies.io import sha256

    monkeypatch.setattr(audit, "SEEDS", (20261120,))
    monkeypatch.setattr(audit, "MISSING", (2,))
    directory = tmp_path / "audit"
    result = dispatch(parser().parse_args(["factored-gradient-audit", "--run-dir", str(directory)]))
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
    with pytest.raises(RuntimeError, match="Generated factored-gradient audit failed") as exception:
        audit.run_audit(tmp_path / "failed")
    assert "forbidden-example-payload" not in str(exception.value)
    text = (tmp_path / "failed" / "manifest.json").read_text()
    assert "forbidden-example-payload" not in text
    assert json.loads(text)["status"] == "failed"


def test_audit_source_drift_is_not_reported_as_complete(tmp_path, monkeypatch):
    import json

    from ies import factored_learning_audit as audit

    hashes = iter([{"example": "before"}, {"example": "after"}])
    monkeypatch.setattr(audit, "_source_hashes", lambda: next(hashes))
    monkeypatch.setattr(audit, "run_cases", lambda: [])
    with pytest.raises(RuntimeError, match="Generated factored-gradient audit failed"):
        audit.run_audit(tmp_path / "audit")
    manifest = json.loads((tmp_path / "audit" / "manifest.json").read_text())
    assert manifest["status"] == "failed" and "output_files_sha256" not in manifest
