"""Fixed generated exact-gradient audit; no model optimization."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from ies.competition import field_prior, forecast
from ies.factored_history import FactoredFilter, count_plan
from ies.factored_history_audit import models
from ies.factored_learning import DifferentiableFilter, perturb
from ies.hidden_learning import LearningDesign, MissingSubject
from ies.history_roles import GeneratedPath
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]
SEEDS = (20261120, 20261121, 20261122)
MISSING = (0, 2, 4, 8, 16, 24)
EPSILON = 1e-5


def sparse_reference(subject, model):
    """Ordinary Fisher identity from the independently enumerated J009 posterior."""
    started = perf_counter()
    design = LearningDesign([subject], model["signs"])
    prepare_seconds = perf_counter() - started
    started = perf_counter()
    expected = design.expectation(model)
    parameters = []
    for z in range(2):
        weights = (expected["context_weights"][:, z], expected["target"][z])
        _, gradient, _ = design.normalizer.objective(model["parameters"][z], weights)
        parameters.append(
            -max(weights[0].sum(), 1) * gradient + field_prior(model["parameters"][z])[1]
        )
    gradient = dict(
        parameters=np.array(parameters),
        terminal_logits=expected["terminal"] - expected["exposure"] * model["terminal"],
        initial_logits=expected["initial"]
        - (model["initial"] if len(subject.observed.events) else 0),
        transition_logits=expected["transition"]
        - expected["transition"].sum(axis=1, keepdims=True) * model["transition"],
    )
    return expected, gradient, prepare_seconds, perf_counter() - started


def run_cases():
    cases = []
    for name, model in models().items():
        for seed in SEEDS:
            for missing in MISSING:
                initial = np.arange(missing + 4) % 4
                empty = GeneratedPath(initial, np.zeros((0, len(initial)), dtype=int))
                events = forecast(empty, model, 1, seed + missing)["events"][0]
                observed = GeneratedPath(initial[:4], events[:, :4])
                subject = MissingSubject(observed, initial[4:])
                count_plan.cache_clear()
                started = perf_counter()
                engine = DifferentiableFilter(missing, model)
                preparation = perf_counter() - started
                started = perf_counter()
                forward = engine.filter(observed, initial[4:])
                forward_seconds = perf_counter() - started
                started = perf_counter()
                result = engine.likelihood_gradient(observed, initial[4:])
                gradient_seconds = perf_counter() - started
                if abs(result["log_probability"] - forward["log_probability"]) > 1e-11:
                    raise RuntimeError("Generated gradient forward likelihood changed")
                rng = np.random.default_rng(np.random.SeedSequence([seed, missing, 1]))
                direction = {k: rng.normal(0, 0.1, v.shape) for k, v in result["gradient"].items()}
                if name == "independent":
                    direction["parameters"][:, 4] = 0
                analytic = float(
                    sum(np.sum(direction[k] * v) for k, v in result["gradient"].items())
                )
                values = [
                    FactoredFilter(missing, perturb(model, direction, sign * EPSILON)).filter(
                        observed, initial[4:]
                    )["log_probability"]
                    for sign in (1, -1)
                ]
                numerical = (values[0] - values[1]) / (2 * EPSILON)
                error = abs(analytic - numerical)
                if error > 2e-6 + 2e-6 * abs(numerical):
                    raise RuntimeError("Generated factored directional derivative disagreed")
                normalization_error = float(
                    np.max(np.abs(result["smoothed_histograms"].sum(axis=(1, 2)) - 1))
                )
                if normalization_error > 1e-9:
                    raise RuntimeError("Generated factored smoother normalization failed")
                comparison = None
                if missing <= 4:
                    expected, gradient, sparse_prepare, sparse_seconds = sparse_reference(
                        subject, model
                    )
                    errors = {
                        k: float(np.max(np.abs(v - result["gradient"][k])))
                        for k, v in gradient.items()
                    }
                    errors["initial_counts"] = float(
                        np.max(np.abs(expected["initial"] - result["initial"]))
                    )
                    errors["transition_counts"] = float(
                        np.max(np.abs(expected["transition"] - result["transition"]))
                    )
                    if max(errors.values()) > 1e-9:
                        raise RuntimeError("Generated factored/sparse gradients disagreed")
                    comparison = dict(
                        max_absolute_errors=errors,
                        sparse_design_seconds=sparse_prepare,
                        sparse_expectation_and_gradient_seconds=sparse_seconds,
                    )
                cases.append(
                    dict(
                        mechanism=name,
                        seed=seed,
                        observed_entities=4,
                        missing_entities=missing,
                        steps=8,
                        histogram_states=len(result["histogram_states"]),
                        factored_preparation_seconds=preparation,
                        factored_forward_seconds=forward_seconds,
                        factored_forward_backward_gradient_seconds=gradient_seconds,
                        sparse_reference=comparison,
                        direction_derivative=analytic,
                        finite_difference_derivative=numerical,
                        derivative_absolute_error=error,
                        derivative_relative_error=error / max(abs(numerical), 1e-12),
                        smoothed_normalization_error=normalization_error,
                        log_probability=result["log_probability"],
                        compound_transition_terms_materialized=0,
                    )
                )
    return cases


def run_audit(run_dir):
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_factored_likelihood_gradient_audit",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        seeds=list(SEEDS),
        missing_counts=list(MISSING),
        finite_difference_epsilon=EPSILON,
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        model_fitted=False,
        gpu_used=False,
        full_initial_roster_known=True,
        unknown_initial_histories_supported=False,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        cases = run_cases()
        write_json(
            run_dir / "results.json",
            dict(
                data_class="synthetic",
                cases=cases,
                note="Exact derivatives of the unchanged unsigned known-roster model. "
                "Ordinary adjoint/Fisher identities; no new optimizer or model fitted. "
                "Single-run local CPU times exclude generation and finite-difference checks. "
                "Sparse gradient reference is limited to hidden <=4 and full roster <=8.",
            ),
        )
        if _source_hashes() != manifest["source_files_sha256"]:
            raise RuntimeError("Generated audit source changed during execution")
        manifest.update(
            status="complete",
            completed_at=datetime.now(UTC).isoformat(),
            output_files_sha256={"results.json": sha256(run_dir / "results.json")},
        )
        write_json(run_dir / "manifest.json", manifest)
    except Exception:
        manifest.update(status="failed", failure="synthetic_factored_gradient_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated factored-gradient audit failed") from None
    return dict(run_dir=str(run_dir), status="complete", cases=len(cases), model_fitted=False)
