"""Generated prior-family containment, not a learned GDPP comparison."""

from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import numpy as np

from ies import cardinality, gdpp
from ies.competition import score as count_score
from ies.hidden_history import filter_missing
from ies.hidden_history_audit import entity_paths, fixed_models
from ies.history_roles import GeneratedPath, pack
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]
SEEDS = (20261114, 20261115, 20261116)
SIZES = (0, 1, 4, 8, 16, 64, 128)


def _require_close(error, tolerance=1e-10):
    if not np.isfinite(error) or error > tolerance:
        raise RuntimeError("Generated GDPP probability identity failed")


def static_cases():
    cases = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        parameters = np.r_[rng.uniform(-3, 3, 4), rng.uniform(-6, -0.5)]
        factor = rng.normal(0, 0.5, (4, 4))
        for k in SIZES:
            histories = rng.integers(0, 4, k)
            potential = parameters[4] * (np.arange(k + 1) - k / 2) ** 2 / max(k, 1)
            outcomes = (
                np.array(list(product((0, 1), repeat=k)), dtype=int).reshape(2**k, k)
                if k <= 8
                else rng.integers(0, 2, (16, k))
            )
            fields = parameters[histories]
            count = cardinality.count_distribution(fields, potential)
            diagonal = gdpp.law(np.diag(np.exp(fields)), potential)
            probability_error = float(
                np.max(
                    np.abs(
                        cardinality.log_probability(count, outcomes)
                        - gdpp.log_probability(diagonal, outcomes)
                    )
                )
            )
            cardinality_error = float(
                np.max(np.abs(count["count_probability"] - diagonal["cardinality_probability"]))
            )
            histories_onehot = np.eye(4, dtype=int)[histories]
            success = outcomes @ histories_onehot
            trials = np.tile(histories_onehot.sum(axis=0), (len(outcomes), 1))
            kernel = gdpp.history_kernel(histories, parameters, factor)
            dense = gdpp.law(kernel, potential)
            reduced = gdpp.history_log_probability(success, trials, parameters, factor)
            dense_probability = gdpp.log_probability(dense, outcomes)
            reduction_error = float(np.max(np.abs(reduced - dense_probability)))
            normalizer_error = float(
                abs(
                    gdpp.history_normalizer(trials[:1], parameters, factor)[0]
                    - dense["log_normalizer"]
                )
            )
            normalization_error = (
                float(abs(np.exp(dense_probability).sum() - 1)) if k <= 8 else None
            )
            for error in (probability_error, cardinality_error, reduction_error, normalizer_error):
                _require_close(error)
            if normalization_error is not None:
                _require_close(normalization_error)
            cases.append(
                dict(
                    seed=seed,
                    roster=k,
                    labeled_patterns_checked=len(outcomes),
                    all_patterns_enumerated=k <= 8,
                    diagonal_log_probability_error=probability_error,
                    diagonal_cardinality_probability_error=cardinality_error,
                    nondiagonal_reduced_log_probability_error=reduction_error,
                    nondiagonal_reduced_log_normalizer_error=normalizer_error,
                    nondiagonal_enumerated_normalization_error=normalization_error,
                )
            )
    return cases


def recurrent_cases():
    rows = entity_paths(3)
    triples = list(product(range(len(rows)), repeat=3))
    paths = [GeneratedPath(np.array([0, 1, 2]), rows[list(i)].T) for i in triples]
    data = pack(paths)
    observations = [GeneratedPath(np.array([0]), row[:, None]) for row in rows]
    base = fixed_models()["combined"]
    rng = np.random.default_rng(SEEDS[0])
    results = []
    for name, factors in (
        ("diagonal", np.zeros((2, 4, 4))),
        ("nondiagonal", rng.normal(0, 0.5, (2, 4, 4))),
    ):
        model = base | {"factors": factors}
        log_full = gdpp.score(data, model)
        full_probability = np.exp(log_full)
        reference = np.bincount(np.array(triples)[:, 0], weights=full_probability)
        filtered = [gdpp.filter_history(p, np.array([1, 2]), model) for p in observations]
        marginal = np.exp([r["log_probability"] for r in filtered])
        normalization_error = float(abs(full_probability.sum() - 1))
        marginal_error = float(np.max(np.abs(reference - marginal)))
        prefix = GeneratedPath(np.array([0]), np.array([[1], [0]]))
        prefix_result = gdpp.filter_history(prefix, np.array([1, 2]), model)
        following = [
            gdpp.filter_history(
                GeneratedPath(prefix.initial, np.r_[prefix.events, [[y]]]),
                np.array([1, 2]),
                model,
            )["log_probability"]
            for y in (0, 1, 2)
        ]
        next_error = float(
            abs(np.exp(np.array(following) - prefix_result["log_probability"]).sum() - 1)
        )
        complete_error, posterior_error = None, None
        if name == "diagonal":
            complete_error = float(np.max(np.abs(log_full - count_score(data, base))))
            posterior_error = float(
                max(
                    np.max(
                        np.abs(
                            r["posterior"] - filter_missing(p, np.array([1, 2]), base)["posterior"]
                        )
                    )
                    for r, p in zip(filtered, observations, strict=True)
                )
            )
            _require_close(complete_error)
            _require_close(posterior_error)
        for error in (normalization_error, marginal_error, next_error):
            _require_close(error)
        results.append(
            dict(
                kernel=name,
                full_paths=len(paths),
                observed_paths=len(observations),
                hidden_entities=2,
                steps=3,
                terminal_events_summed=True,
                full_normalization_error=normalization_error,
                hidden_marginal_error=marginal_error,
                next_observation_normalization_error=next_error,
                diagonal_complete_log_probability_error=complete_error,
                diagonal_hidden_posterior_error=posterior_error,
            )
        )
    return results


def covariance_cases():
    cases = []
    for k in (4, 8, 16, 32):
        count = k // 2
        weights = np.full(k + 1, -np.inf)
        weights[count] = 0
        distribution = gdpp.law(np.eye(k), weights)
        q = distribution["cardinality_probability"]
        values = np.arange(k + 1)
        mean = float(q @ values / k)
        covariance = float(q @ (values * (values - 1)) / (k * (k - 1)) - mean**2)
        _require_close(abs(covariance + mean * (1 - mean) / (k - 1)))
        bound = -1 / k**2
        if not covariance < bound:
            raise RuntimeError("Generated invariant-kernel counterexample failed")
        cases.append(
            dict(
                roster=k,
                fixed_cardinality=count,
                invariant_ordinary_marginal_kernel_covariance_lower_bound=bound,
                uniform_fixed_cardinality_gdpp_covariance=covariance,
                restriction_applies_to_all_dpps_or_gdpps=False,
            )
        )
    return cases


def run_audit(run_dir):
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_gdpp_containment_audit",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        seeds=list(SEEDS),
        sizes=list(SIZES),
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        model_fitted=False,
        gpu_used=False,
        novel_algorithm_established=False,
        publication_readiness="not_established",
        prior_source="https://arxiv.org/abs/1807.10957",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        static = static_cases()
        recurrent = recurrent_cases()
        covariance = covariance_cases()
        write_json(
            run_dir / "results.json",
            dict(
                data_class="synthetic",
                static=static,
                recurrent=recurrent,
                covariance=covariance,
                conclusion="J009 unsigned count emissions are diagonal cardinality-weighted "
                "GDPPs. Non-diagonal history-shared probabilities are verified, not fitted. "
                "The invariant ordinary-kernel bound is not a bound for all DPPs or GDPPs. "
                "No new model architecture or clinical result is established.",
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
        manifest.update(status="failed", failure="synthetic_gdpp_containment_failure")
        write_json(run_dir / "manifest.json", manifest)
        raise RuntimeError("Generated GDPP containment audit failed") from None
    return dict(
        run_dir=str(run_dir),
        status="complete",
        static_cases=len(static),
        recurrent_cases=len(recurrent),
        covariance_cases=len(covariance),
        model_fitted=False,
    )
