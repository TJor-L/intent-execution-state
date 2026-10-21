"""Fixed generated exactness and scaling audit; no parameter fitting."""

from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from time import perf_counter

import numpy as np

from ies.competition import forecast, score
from ies.hidden_history import filter_missing, histogram_plan
from ies.history_roles import GeneratedPath, pack
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]


def fixed_models():
    base = dict(
        parameters=np.array([[-1.0, 0.7, -0.5, 0.4, -4.0], [0.3, -0.9, 0.8, -0.2, -4.0]]),
        signs=np.ones(4, dtype=int),
        terminal=np.array([0.1, 0.15, 0.2, 0.25]),
        initial=np.array([0.4, 0.6]),
        transition=np.array([[0.9, 0.1], [0.2, 0.8]]),
    )
    capacity = base | {
        "parameters": np.tile(base["parameters"][0], (2, 1)),
        "signs": np.array([1, -1, -1, 1]),
    }
    independent = capacity | {"parameters": capacity["parameters"].copy()}
    independent["parameters"][:, 4] = 0
    return dict(independent=independent, signed_capacity=capacity, combined=base)


def entity_paths(length):
    rows = [()]
    for _ in range(length):
        rows = [(*p, y) for p in rows for y in ((-1,) if 2 in p else (0, 1, 2))]
    return np.array(rows, dtype=int)


def exhaustive_cases():
    rows = entity_paths(3)
    triples = list(product(range(len(rows)), repeat=3))
    full = [GeneratedPath(np.array([0, 1, 2]), rows[list(i)].T) for i in triples]
    observed = [GeneratedPath(np.array([0]), p[:, None]) for p in rows]
    observed_index = np.array(triples)[:, 0]
    cases = []
    for name, model in fixed_models().items():
        full_probability = np.exp(score(pack(full), model))
        reference = np.bincount(observed_index, weights=full_probability)
        filtered = np.array(
            [
                np.exp(filter_missing(p, np.array([1, 2]), model)["log_probability"])
                for p in observed
            ]
        )
        deletion = np.exp(score(pack(observed), model))
        error = float(np.abs(filtered - reference).max())
        if error > 1e-12 or abs(filtered.sum() - 1) > 1e-12:
            raise RuntimeError("Generated hidden-history enumeration disagreement")
        cases.append(
            dict(
                mechanism=name,
                observed_entity_paths=rows.tolist(),
                exact_probability=filtered.tolist(),
                full_labeled_reference=reference.tolist(),
                incorrect_deleted_roster_probability=deletion.tolist(),
                max_absolute_enumeration_error=error,
                total_variation_from_deleting_population=float(
                    np.abs(filtered - deletion).sum() / 2
                ),
            )
        )
    return cases


def scaling_cases():
    model = fixed_models()["combined"]
    cases = []
    for missing in (0, 1, 2, 4, 8):
        # Exactness checks may already have cached B=2: measure cold construction.
        histogram_plan.cache_clear()
        started = perf_counter()
        plan = histogram_plan(missing)
        plan_seconds = perf_counter() - started
        for kept in (1, 4, 16):
            initial = np.arange(kept + missing, dtype=int) % 4
            prefix = GeneratedPath(initial, np.empty((0, len(initial)), dtype=int))
            full = forecast(prefix, model, 1, 20261110 + kept + 100 * missing)["events"][0]
            # Do not pass any unobserved generated outcomes into the filter.
            observed = GeneratedPath(initial[:kept], full[:, :kept])
            started = perf_counter()
            result = filter_missing(observed, initial[kept:], model)
            seconds = perf_counter() - started
            cases.append(
                dict(
                    missing_entities=missing,
                    observed_entities=kept,
                    steps=8,
                    histogram_states=len(plan["states"]),
                    labeled_history_states=5**missing,
                    latent_states_per_histogram=2,
                    transition_terms=len(plan["source"]),
                    cached_plan_bytes=sum(v.nbytes for v in plan.values()),
                    plan_build_seconds=plan_seconds,
                    filter_seconds=seconds,
                    log_probability=result["log_probability"],
                    posterior_normalization_error=float(abs(result["posterior"].sum() - 1)),
                )
            )
    return cases


def run_audit(run_dir):
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_hidden_history_audit",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        model_fitted=False,
        gpu_used=False,
        known_full_initial_roster_required=True,
        unknown_initial_histories_supported=False,
        informative_observation_model_fitted=False,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        exact = exhaustive_cases()
        scaling = scaling_cases()
        write_json(
            run_dir / "results.json",
            dict(
                data_class="synthetic",
                exactness=exact,
                scaling=scaling,
                note="Exact symmetry aggregation of a known generated model. Missing future "
                "histories are marginalized; full initial roster is supplied. No unknown "
                "roster identification, new fitting algorithm or clinical result.",
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
        manifest.update(status="failed", failure="synthetic_hidden_history_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated hidden-history audit failed") from None
    return dict(
        run_dir=str(run_dir),
        status="complete",
        exactness_cases=len(exact),
        scaling_cases=len(scaling),
    )
