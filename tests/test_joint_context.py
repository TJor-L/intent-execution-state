import json

import numpy as np
import pytest
import yaml

from ies.cli import parser
from ies.joint_context import fit_context, select_contexts
from ies.joint_context_demo import run_demo
from ies.joint_observation import STATES, PrefixCounts, joint_law, projection, sample_observed
from ies.joint_shrinkage import split_counts, tree_shrink_fit


@pytest.mark.parametrize("scope", ("independent", "joint"))
@pytest.mark.parametrize("memory", (0, 1, 2))
def test_all_context_models_normalized_positive_and_absorbing(scope, memory):
    observed = sample_observed(joint_law("synchronized"), [0, 0.5, 0.3, 0.2], 200, 61)
    p, diagnostic = fit_context(observed, scope, memory, 10)
    assert p.sum() == pytest.approx(1)
    assert p.min() > 0
    assert diagnostic["observed_patients_by_transition"][0] == 200
    assert 0 < diagnostic["nominal_transition_dimension"] <= 224
    if scope == "independent":
        q = p.reshape(15, 15)
        np.testing.assert_allclose(q, np.outer(q.sum(axis=1), q.sum(axis=0)), atol=1e-12)


def test_full_joint_context_equals_dirichlet_tree_with_matching_structural_prior():
    observed = sample_observed(joint_law("opposed"), [0, 0.5, 0.3, 0.2], 200, 31)
    base = np.prod(np.array([1 / 3, 1 / 3, 1 / 3, 1])[STATES], axis=(1, 2))
    p, diagnostic = fit_context(observed, "joint", 2, 10)
    np.testing.assert_allclose(p, tree_shrink_fit(observed, base, 10), atol=1e-12)
    assert diagnostic["nominal_transition_dimension"] == 224


def test_unobserved_tail_not_counted_as_zero_or_used_to_change_early_predictions():
    counts = [np.zeros(projection(c).max() + 1, dtype=int) for c in range(4)]
    counts[1][0] = 40
    observed = PrefixCounts(tuple(counts))
    p, diagnostic = fit_context(observed, "joint", 1, 10)
    assert diagnostic["observed_patients_by_transition"] == [40, 0, 0]
    # After a nonterminal first bin, unsupported second-bin valid outcomes are uniform.
    second, first = projection(2), projection(1)
    reps = np.unique(second, return_index=True)[1]
    parent = first[reps]
    mass = np.bincount(second, weights=p)
    for label in np.unique(parent):
        conditional = mass[parent == label] / mass[parent == label].sum()
        np.testing.assert_allclose(conditional, 1 / len(conditional), atol=1e-12)


def test_entity_swap_equivariance_of_fixed_context_models():
    observed = sample_observed(joint_law("opposed"), [0, 0.5, 0.3, 0.2], 200, 31)
    swap = np.arange(225).reshape(15, 15).T.ravel()
    counts = []
    for c in range(4):
        index = projection(c)
        reps = np.unique(index, return_index=True)[1]
        counts.append(np.bincount(index[swap[reps]], weights=observed.counts[c]).astype(int))
    for scope in ("independent", "joint"):
        for memory in (0, 1, 2):
            p, _ = fit_context(observed, scope, memory, 10)
            q, _ = fit_context(PrefixCounts(tuple(counts)), scope, memory, 10)
            np.testing.assert_allclose(q, p[swap], atol=1e-12)


def test_cv_split_counts_and_shared_candidate_losses(monkeypatch):
    import ies.joint_context as module

    observed = sample_observed(joint_law("synchronized"), [0, 0.5, 0.3, 0.2], 200, 12)
    seen = []
    original = module._observed_levels

    def record(data):
        seen.append(data.patients)
        return original(data)

    monkeypatch.setattr(module, "_observed_levels", record)
    predictions, diagnostics = select_contexts(observed, 71)
    left, right = split_counts(observed, 71)
    assert seen == [left.patients, right.patients, observed.patients]
    all_candidates = diagnostics["context_all_cv"]["candidates"]
    assert len(all_candidates) == 18
    assert (
        all_candidates
        == diagnostics["context_independent_cv"]["candidates"]
        + diagnostics["context_joint_cv"]["candidates"]
    )
    selected = diagnostics["context_all_cv"]["selected"]
    p, _ = fit_context(observed, selected["scope"], selected["memory"], selected["strength"])
    np.testing.assert_array_equal(p, predictions["context_all_cv"])


def test_invalid_parameters_and_latent_labels_rejected():
    observed = sample_observed(joint_law("independent"), [0, 0, 0, 1], 50, 3)
    for scope, memory, strength in (("unknown", 0, 1), ("joint", 3, 1), ("joint", 1, 0)):
        with pytest.raises(ValueError):
            fit_context(observed, scope, memory, strength)
    with pytest.raises(TypeError):
        fit_context(observed, "joint", 1, 1, latent=joint_law("independent"))


def test_context_runner_determinism_and_no_clinical_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr("ies.joint_context_demo.SCENARIOS", ("lagged_dependence",))
    monkeypatch.setattr("ies.joint_context_demo.POLICIES", ("independent_short",))
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            dict(schema_version=1, data_class="synthetic", seeds=[1], patients=[32], em_steps=2)
        )
    )
    a, b = tmp_path / "a", tmp_path / "b"
    assert run_demo(config, a)["cases"] == 1
    run_demo(config, b)
    assert (a / "metrics.json").read_bytes() == (b / "metrics.json").read_bytes()
    assert (a / "models.json").read_bytes() == (b / "models.json").read_bytes()
    assert json.loads((a / "manifest.json").read_text())["status"] == "complete"
    with pytest.raises(FileExistsError):
        run_demo(config, a)
    with pytest.raises(SystemExit):
        parser().parse_args(["joint-context-demo", "--data-root", "/restricted"])
