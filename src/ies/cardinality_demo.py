"""J005 generated finite-set mechanism comparisons; not a recurrent clinical model."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml

from ies.cardinality import (
    binary_events,
    count_distribution,
    fit_strength,
    interaction_feature,
    log_probability,
    sample_sets,
    tilt_model,
)
from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("independent", "shared_shift", "opposed_shift", "soft_capacity")


def load_config(path):
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError("Invalid generated cardinality config")
    config = yaml.safe_load(path.read_text())
    if (
        not isinstance(config, dict)
        or set(config)
        != {"schema_version", "data_class", "seeds", "entities", "patients", "evaluation_patients"}
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or config["data_class"] != "synthetic"
        or type(config["evaluation_patients"]) is not int
        or not 128 <= config["evaluation_patients"] <= 8192
    ):
        raise ValueError("Generated-only cardinality configuration required")
    for key, low, high, limit in (
        ("seeds", 0, 2**31 - 1, 3),
        ("entities", 2, 128, 3),
        ("patients", 32, 1024, 2),
    ):
        values = config[key]
        if (
            not isinstance(values, list)
            or not 1 <= len(values) <= limit
            or len(set(values)) != len(values)
            or any(type(x) is not int or not low <= x <= high for x in values)
        ):
            raise ValueError("Invalid generated cardinality resource bound")
    return config, sha256(path)


def _logsumexp(value, axis):
    maximum = value.max(axis=axis, keepdims=True)
    return np.squeeze(maximum, axis=axis) + np.log(np.exp(value - maximum).sum(axis=axis))


def mixture_model(weights, probabilities):
    weights, probabilities = (
        np.asarray(weights, dtype=float),
        np.asarray(probabilities, dtype=float),
    )
    if (
        weights.shape != (2,)
        or probabilities.ndim != 2
        or probabilities.shape[0] != 2
        or not 1 <= probabilities.shape[1] <= 128
        or not np.isfinite(weights).all()
        or not np.isfinite(probabilities).all()
        or np.any(weights <= 0)
        or not np.isclose(weights.sum(), 1, rtol=0, atol=1e-12)
        or np.any((probabilities <= 0) | (probabilities >= 1))
    ):
        raise ValueError("Invalid generated product mixture")
    counts = [
        count_distribution(np.log(p) - np.log1p(-p), np.zeros(len(p) + 1))["count_probability"]
        for p in probabilities
    ]
    return dict(
        kind="product_mixture",
        weights=weights,
        probabilities=probabilities,
        marginals=weights @ probabilities,
        count_probability=weights @ np.asarray(counts),
    )


def log_density(model, events):
    if model.get("kind") != "product_mixture":
        return log_probability(model, events)
    p = model["probabilities"]
    log_terms = (
        events @ (np.log(p) - np.log1p(-p)).T + np.log1p(-p).sum(axis=1) + np.log(model["weights"])
    )
    return _logsumexp(log_terms, 1)


def draw(model, patients, seed):
    if model.get("kind") != "product_mixture":
        return sample_sets(model, patients, seed)
    if (
        type(patients) is not int
        or not 1 <= patients <= 100_000
        or patients * model["probabilities"].shape[1] > 4_000_000
    ):
        raise ValueError("Invalid generated mixture sampling bound")
    rng = np.random.default_rng(seed)
    component = rng.choice(2, patients, p=model["weights"])
    return (
        rng.random((patients, model["probabilities"].shape[1])) < model["probabilities"][component]
    ).astype(int)


def generated_law(scenario, entities):
    if scenario not in SCENARIOS or type(entities) is not int or not 2 <= entities <= 128:
        raise ValueError("Invalid generated cardinality law")
    reference = np.linspace(0.08, 0.45, entities)
    logits = np.log(reference) - np.log1p(-reference)
    if scenario in {"shared_shift", "opposed_shift"}:
        sign = (
            np.ones(entities)
            if scenario == "shared_shift"
            else np.where(reference <= np.median(reference), 1.0, -1.0)
        )
        probabilities = 1 / (1 + np.exp(-(logits[None, :] + np.array([-1.0, 1.0])[:, None] * sign)))
        return mixture_model([0.5, 0.5], probabilities)
    potential = np.zeros(entities + 1)
    if scenario == "soft_capacity":
        potential = -2 * (np.arange(entities + 1) - round(reference.sum())) ** 2
    return count_distribution(logits, potential)


def fit_mixture(events, seed, steps=100):
    """Known two-product mixture MAP-EM; fixed count-based and random starts."""
    events = np.asarray(events)
    if (
        events.ndim != 2
        or not 1 <= events.shape[1] <= 128
        or type(steps) is not int
        or not 1 <= steps <= 100
    ):
        raise ValueError("Invalid generated mixture fit")
    events = binary_events(events, events.shape[1])
    rng = np.random.default_rng(seed)
    starts = [
        np.where(events.sum(axis=1) > np.median(events.sum(axis=1)), 0.8, 0.2),
        rng.uniform(0.1, 0.9, len(events)),
    ]
    best, best_objective, best_trace = None, -np.inf, None
    for start in starts:
        responsibility = np.column_stack([start, 1 - start])
        trace = []
        for _ in range(steps):
            totals = responsibility.sum(axis=0)
            weights = (totals + 0.5) / (len(events) + 1)
            probabilities = (responsibility.T @ events + 0.5) / (totals[:, None] + 1)
            log_terms = (
                events @ (np.log(probabilities) - np.log1p(-probabilities)).T
                + np.log1p(-probabilities).sum(axis=1)
                + np.log(weights)
            )
            normalizer = _logsumexp(log_terms, 1)
            responsibility = np.exp(log_terms - normalizer[:, None])
            objective = float(
                normalizer.sum()
                + 0.5 * np.log(weights).sum()
                + 0.5 * (np.log(probabilities) + np.log1p(-probabilities)).sum()
            )
            trace.append(objective)
        if objective > best_objective:
            best_objective, best = objective, mixture_model(weights, probabilities)
            best_trace = trace
    return best, dict(
        steps=steps, starts=2, selection="training_MAP_objective", objective_trace=best_trace
    )


def empirical_count_model(reference, events, strength=10):
    events = binary_events(events, len(reference))
    if not np.isfinite(strength) or not 0 < strength <= 1000:
        raise ValueError("Invalid generated count smoothing strength")
    base = tilt_model(interaction_feature(reference), 0)
    counts = np.bincount(events.sum(axis=1), minlength=len(reference) + 1)
    log_counts = np.log(counts, out=np.full(len(counts), -np.inf), where=counts > 0)
    log_prior = base["forward"][-1] - base["log_normalizer"]
    log_mass = np.logaddexp(log_counts, np.log(strength) + log_prior) - np.log(
        len(events) + strength
    )
    return count_distribution(base["fields"], log_mass - base["forward"][-1])


def _serialize(model):
    return {
        name: value.tolist() if isinstance(value, np.ndarray) else value
        for name, value in model.items()
        if name != "forward"
    }


def run_demo(config_path, run_dir):
    config, digest = load_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_projected_cardinality",
        data_class="synthetic",
        status="running",
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        config_file_sha256=digest,
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        numpy_version=np.__version__,
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        gpu_used=False,
        complete_observed_transition_only=True,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        cases, resources, models = [], [], []
        for seed in config["seeds"]:
            for entities in config["entities"]:
                for patients in config["patients"]:
                    for scenario in SCENARIOS:
                        truth = generated_law(scenario, entities)
                        train = draw(truth, patients, seed + 600_003)
                        evaluation = draw(truth, config["evaluation_patients"], seed + 700_003)
                        true_log = log_density(truth, evaluation)
                        reference = (train.sum(axis=0) + 0.5) / (patients + 1)
                        predictions, diagnostics, times = {}, {}, {}
                        for kind in (
                            "projected_bounded",
                            "unprojected_bounded",
                            "projected_quadratic",
                        ):
                            started = perf_counter()
                            predictions[kind], diagnostics[kind] = fit_strength(
                                reference, train, kind
                            )
                            times[kind] = perf_counter() - started
                        started = perf_counter()
                        predictions["independent"] = tilt_model(interaction_feature(reference), 0)
                        times["independent"] = perf_counter() - started
                        started = perf_counter()
                        predictions["empirical_count"] = empirical_count_model(reference, train)
                        times["empirical_count"] = perf_counter() - started
                        started = perf_counter()
                        predictions["product_mixture"], diagnostics["product_mixture"] = (
                            fit_mixture(train, seed)
                        )
                        times["product_mixture"] = perf_counter() - started
                        started = perf_counter()
                        (
                            predictions["oracle_marginal_projected"],
                            diagnostics["oracle_marginal_projected"],
                        ) = fit_strength(truth["marginals"], train)
                        times["oracle_marginal_projected"] = perf_counter() - started
                        metrics = {}
                        candidate_loss = -log_density(predictions["projected_bounded"], evaluation)
                        for name, model in predictions.items():
                            log_prediction = log_density(model, evaluation)
                            ratio = true_log - log_prediction
                            difference = candidate_loss + log_prediction
                            exact_cross_entropy = None
                            if model.get("kind") != "product_mixture":
                                exact_cross_entropy = float(
                                    model["log_normalizer"]
                                    - model["fields"] @ truth["marginals"]
                                    - model["potential"] @ truth["count_probability"]
                                )
                            metrics[name] = dict(
                                feasible=name != "oracle_marginal_projected",
                                joint_kl_monte_carlo=float(ratio.mean()),
                                joint_kl_monte_carlo_se=float(
                                    ratio.std(ddof=1) / np.sqrt(len(ratio))
                                ),
                                projected_minus_method_nll_mc=float(difference.mean()),
                                paired_monte_carlo_se=float(
                                    difference.std(ddof=1) / np.sqrt(len(difference))
                                ),
                                exact_joint_cross_entropy=exact_cross_entropy,
                                count_kl=float(
                                    truth["count_probability"]
                                    @ np.log(
                                        np.maximum(truth["count_probability"], 1e-300)
                                        / np.maximum(model["count_probability"], 1e-300)
                                    )
                                ),
                                marginal_mse=float(
                                    np.mean((model["marginals"] - truth["marginals"]) ** 2)
                                ),
                            )
                        key = dict(
                            seed=seed, entities=entities, patients=patients, scenario=scenario
                        )
                        cases.append(dict(**key, methods=metrics, diagnostics=diagnostics))
                        resources.append(dict(**key, fit_seconds=times))
                        models.append(
                            dict(
                                **key,
                                models={
                                    name: _serialize(model) for name, model in predictions.items()
                                },
                            )
                        )
        write_json(run_dir / "config.json", config)
        write_json(run_dir / "metrics.json", dict(data_class="synthetic", cases=cases))
        write_json(run_dir / "resources.json", dict(data_class="synthetic", cases=resources))
        write_json(run_dir / "models.json", dict(data_class="synthetic", cases=models))
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise ValueError("Cardinality experiment source or config changed")
        manifest.update(
            status="complete",
            artifacts_sha256={
                name: sha256(run_dir / name)
                for name in ("config.json", "metrics.json", "resources.json", "models.json")
            },
        )
        return dict(
            status="complete",
            data_class="synthetic",
            cases=len(cases),
            run_dir=str(run_dir),
            publication_readiness="not_established",
        )
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
