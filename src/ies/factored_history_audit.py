"""Fixed generated correctness/scaling screen for factored exact filtering."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from ies.competition import forecast
from ies.factored_history import FactoredFilter, count_plan
from ies.hidden_history import filter_missing, histogram_plan
from ies.hidden_history_audit import fixed_models
from ies.history_roles import GeneratedPath
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]
SEEDS = (20261117, 20261118, 20261119)
MISSING = (0, 1, 2, 4, 8, 12, 16, 24)


def models():
    base = fixed_models()["combined"]
    independent = base | {"parameters": base["parameters"].copy()}
    independent["parameters"][:, 4] = 0
    capacity = base | {"parameters": np.tile(base["parameters"][0], (2, 1))}
    return dict(independent=independent, unsigned_capacity=capacity, combined=base)


def compare_results(actual, reference):
    lookup = {tuple(row): i for i, row in enumerate(reference["histogram_states"])}
    indices = [lookup[tuple(row)] for row in actual["histogram_states"]]
    error = float(np.max(np.abs(actual["log_increments"] - reference["log_increments"])))
    posterior = float(
        max(
            np.max(np.abs(a - b[indices]))
            for a, b in zip(actual["posteriors"], reference["posteriors"], strict=True)
        )
    )
    next_error = float(
        np.max(
            np.abs(actual["next_state_probability"] - reference["next_state_probability"][indices])
        )
    )
    if max(error, posterior, next_error) > 1e-10:
        raise RuntimeError("Generated factored and sparse filters disagree")
    return dict(
        max_increment_error=error,
        max_posterior_error=posterior,
        next_state_error=next_error,
        log_likelihood_error=float(abs(actual["log_probability"] - reference["log_probability"])),
    )


def run_cases():
    cases = []
    for name, model in models().items():
        for seed in SEEDS:
            for missing in MISSING:
                initial = np.arange(4 + missing) % 4
                empty = GeneratedPath(initial, np.zeros((0, len(initial)), dtype=int))
                generated = forecast(empty, model, 1, seed + missing)["events"][0]
                observed = GeneratedPath(initial[:4], generated[:, :4])
                # Filtering receives no future events of the omitted entities.
                count_plan.cache_clear()
                started = perf_counter()
                engine = FactoredFilter(missing, model)
                prepare_seconds = perf_counter() - started
                started = perf_counter()
                actual = engine.filter(observed, initial[4:])
                filter_seconds = perf_counter() - started
                sparse_prepare, sparse_seconds, agreement = None, None, None
                if missing <= 8:
                    histogram_plan.cache_clear()
                    started = perf_counter()
                    histogram_plan(missing)
                    sparse_prepare = perf_counter() - started
                    started = perf_counter()
                    reference = filter_missing(observed, initial[4:], model)
                    sparse_seconds = perf_counter() - started
                    agreement = compare_results(actual, reference)
                # After every observed entity has terminated, summing all subsequent
                # hidden outcomes must have conditional probability one.
                absorbed = GeneratedPath(initial[:4], np.array([[2] * 4, [-1] * 4]))
                absorbed_result = engine.filter(absorbed, initial[4:])
                absorption_error = float(abs(absorbed_result["log_increments"][1]))
                normalization_error = float(abs(actual["posterior"].sum() - 1))
                if max(absorption_error, normalization_error) > 1e-10:
                    raise RuntimeError("Generated factored normalization failed")
                cases.append(
                    dict(
                        mechanism=name,
                        seed=seed,
                        observed_entities=4,
                        missing_entities=missing,
                        steps=8,
                        histogram_states=engine.plan["histogram_states"],
                        sparse_compound_term_count=engine.plan["sparse_transition_terms"],
                        sparse_compound_terms_allocated=missing <= 8,
                        factored_compound_terms_allocated=0,
                        one_dense_two_latent_array_bytes=8 * 2 * (missing + 1) ** 4,
                        peak_memory_measured=False,
                        factored_prepare_seconds=prepare_seconds,
                        factored_filter_seconds=filter_seconds,
                        sparse_prepare_seconds=sparse_prepare,
                        sparse_filter_seconds=sparse_seconds,
                        agreement=agreement,
                        posterior_normalization_error=normalization_error,
                        fully_absorbed_next_likelihood_error=absorption_error,
                        log_probability=actual["log_probability"],
                    )
                )
    return cases


def run_audit(run_dir):
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_factored_history_audit",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        seeds=list(SEEDS),
        missing_counts=list(MISSING),
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
                note="Same unsigned count law; exact binomial-thinning/polynomial contractions. "
                "Single-run CPU timings include preparation separately and omit generation. "
                "Sparse costs above eight missing entities are counts, not measured runtimes. "
                "Array bytes are not peak memory. No fitting, new law or clinical claim.",
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
        manifest.update(status="failed", failure="synthetic_factored_history_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated factored-history audit failed") from None
    return dict(run_dir=str(run_dir), status="complete", cases=len(cases), model_fitted=False)
