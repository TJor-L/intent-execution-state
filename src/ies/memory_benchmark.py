"""Reproducible generated-only context-allocation mechanism benchmark."""

import importlib.metadata
import math
import platform
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml

from ies.io import sha256, write_json
from ies.memory_data import SCENARIOS, generate, label_mask
from ies.memory_models import (
    aligned_outcomes,
    allocate,
    encode,
    fit_allocator,
    fit_decoder,
    observed_nll,
    predict,
    utilities,
)
from ies.training.pipeline import git_provenance
from ies.workflow_diagnostic import _source_hashes

ROOT = Path(__file__).resolve().parents[2]
POLICIES = (
    "recent",
    "balanced",
    "static_utility",
    "learned_utility",
    "all_recent_depth",
    "per_order_summary",
    "descriptor_direct",
    "history_free",
)
INTEGER_LIMITS = {
    "decoder_patients": (12, 512),
    "allocator_patients": (12, 512),
    "evaluation_patients": (12, 512),
    "history_steps": (16, 128),
    "horizon_steps": (2, 8),
    "max_depth": (1, 12),
    "hidden_units": (2, 32),
    "epochs": (1, 300),
    "bootstrap_replicates": (10, 1000),
}
KEYS = {
    "schema_version",
    "data_class",
    "seeds",
    "scenarios",
    "orders_per_patient",
    "budgets",
    "censor_probability",
    "learning_rate",
    "ridge",
    *INTEGER_LIMITS,
}


def load_config(path):
    if path.stat().st_size > 16384:
        raise ValueError("Oversized generated config")
    config = yaml.safe_load(path.read_text())
    if (
        not isinstance(config, dict)
        or set(config) != KEYS
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or config["data_class"] != "synthetic"
    ):
        raise ValueError("Generated-only memory config required")
    for key, (lower, upper) in INTEGER_LIMITS.items():
        if type(config[key]) is not int or not lower <= config[key] <= upper:
            raise ValueError("Invalid generated resource bounds")
    for key, lower, upper, maximum in (
        ("seeds", 0, 2**31 - 1, 5),
        ("orders_per_patient", 2, 24, 3),
        ("budgets", 0, 64, 4),
    ):
        values = config[key]
        if (
            not isinstance(values, list)
            or not 1 <= len(values) <= maximum
            or any(type(v) is not int or not lower <= v <= upper for v in values)
            or len(values) != len(set(values))
        ):
            raise ValueError("Invalid generated case list")
    scenarios = config["scenarios"]
    if (
        not isinstance(scenarios, list)
        or not scenarios
        or any(not isinstance(v, str) or v not in SCENARIOS for v in scenarios)
        or len(scenarios) != len(set(scenarios))
    ):
        raise ValueError("Invalid generated scenarios")
    for key, lower, upper in (
        ("censor_probability", 0, 1),
        ("learning_rate", 0.0001, 0.1),
        ("ridge", 0.0001, 1),
    ):
        value = config[key]
        if (
            type(value) not in {int, float}
            or not math.isfinite(value)
            or not lower <= value <= upper
        ):
            raise ValueError("Invalid generated numerical setting")
    work = (
        len(config["seeds"])
        * len(scenarios)
        * sum(config["orders_per_patient"])
        * config["decoder_patients"]
        * (config["max_depth"] + 1)
        * config["epochs"]
    )
    if work > 100_000_000:
        raise ValueError("Generated fit work bound exceeded")
    case_orders = len(config["seeds"]) * len(scenarios) * sum(config["orders_per_patient"])
    generated_steps = (
        case_orders
        * (
            config["decoder_patients"]
            + config["allocator_patients"]
            + config["evaluation_patients"]
        )
        * (config["history_steps"] + config["horizon_steps"])
    )
    allocation_work = (
        case_orders
        * config["evaluation_patients"]
        * sum(b + 1 for b in config["budgets"])
        * (config["max_depth"] + 1)
    )
    if generated_steps > 50_000_000 or allocation_work > 100_000_000:
        raise ValueError("Generated simulation or allocation work bound exceeded")
    return config, sha256(path)


def _flatten(samples, encoded, summary=False):
    x, outcomes, weights = [], [], []
    for sample, item in zip(samples, encoded, strict=True):
        labels = aligned_outcomes(item, sample.observed)
        count = len(labels)
        if summary:
            x.extend(item.summaries)
            outcomes.extend(labels)
            weights.extend([1 / count] * count)
        else:
            actions = item.features.shape[1]
            x.extend(item.features.reshape(-1, item.features.shape[-1]))
            outcomes.extend(label for label in labels for _ in range(actions))
            weights.extend([1 / (count * actions)] * (count * actions))
    return np.asarray(x), outcomes, weights


def fit_case(config, train, calibration):
    """The allocator's outcome-based utility targets are out of decoder training sample."""
    training_ids = {s.context.patient_id for s in train}
    calibration_ids = {s.context.patient_id for s in calibration}
    if (
        training_ids & calibration_ids
        or any(s.context.split != "decoder" for s in train)
        or any(s.context.split != "allocator" for s in calibration)
    ):
        raise ValueError("Generated training split violation")
    encoded = [encode(s.context, config["max_depth"]) for s in train]
    arguments = dict(
        horizon=config["horizon_steps"],
        hidden=config["hidden_units"],
        epochs=config["epochs"],
        learning_rate=config["learning_rate"],
        ridge=config["ridge"],
        seed=711,
    )
    x, labels, weights = _flatten(train, encoded)
    decoder = fit_decoder(x, labels, weights=weights, **arguments)
    x, labels, weights = _flatten(train, encoded, summary=True)
    summary = fit_decoder(x, labels, weights=weights, **arguments)
    direct_x = np.concatenate(
        [np.column_stack([item.summaries[:, :4], item.descriptors]) for item in encoded]
    )
    direct = fit_decoder(direct_x, labels, weights=weights, **arguments)
    constant = fit_decoder(np.zeros((len(labels), 1)), labels, weights=weights, **arguments)
    descriptors, losses, weights = [], [], []
    for sample in calibration:
        item = encode(sample.context, config["max_depth"])
        labels = aligned_outcomes(item, sample.observed)
        actions = item.features.shape[1]
        probability = predict(decoder, item.features.reshape(-1, item.features.shape[-1]))
        mask = label_mask(
            [label for label in labels for _ in range(actions)], config["horizon_steps"]
        )
        losses.extend(observed_nll(probability, mask).reshape(len(labels), actions))
        descriptors.extend(item.descriptors)
        weights.extend([1 / len(labels)] * len(labels))
    allocator = fit_allocator(np.array(descriptors), np.array(losses), weights, config["ridge"])
    return {
        "decoder": decoder,
        "summary": summary,
        "allocator": allocator,
        "direct": direct,
        "constant": constant,
    }


def _paired(difference, seed, replicates):
    rng = np.random.default_rng(seed)
    means = [
        float(np.mean(rng.choice(difference, len(difference), replace=True)))
        for _ in range(replicates)
    ]
    return {
        "patient_mean_difference": float(np.mean(difference)),
        "conditional_patient_bootstrap_95": np.quantile(means, [0.025, 0.975]).tolist(),
        "includes_fitting_or_selection_uncertainty": False,
    }


def evaluate_case(config, samples, models, seed):
    if any(s.context.split != "evaluation" for s in samples):
        raise ValueError("Generated evaluation split violation")
    started = perf_counter()
    encoded = [encode(s.context, config["max_depth"]) for s in samples]
    encoding_seconds = perf_counter() - started
    reports, resources = [], []
    horizon = config["horizon_steps"]
    for budget in config["budgets"]:
        metrics, costs, patient_scores = {}, {}, {}
        for policy in POLICIES:
            observed, complete, brier, permuted, retained = [], [], [], [], []
            selection_time, decoder_time = 0.0, 0.0
            permutation_rng = np.random.default_rng(seed + 1009)
            for sample, item in zip(samples, encoded, strict=True):
                started = perf_counter()
                if policy in {"per_order_summary", "descriptor_direct", "history_free"}:
                    allocation = np.zeros(len(item.order_ids), dtype=int)
                    if policy == "per_order_summary":
                        x, model = item.summaries, models["summary"]
                    elif policy == "descriptor_direct":
                        x = np.column_stack([item.summaries[:, :4], item.descriptors])
                        model = models["direct"]
                    else:
                        x, model = np.zeros((len(item.order_ids), 1)), models["constant"]
                else:
                    if policy == "all_recent_depth":
                        allocation = np.minimum(item.counts, config["max_depth"])
                    elif policy in {"recent", "balanced"}:
                        allocation = allocate(item, budget, policy)
                    else:
                        value = (
                            utilities(models["allocator"], item.descriptors)
                            if policy == "learned_utility"
                            else np.broadcast_to(
                                models["allocator"]["static_utility"], item.features.shape[:2]
                            )
                        )
                        allocation = allocate(item, budget, "utility", value)
                    x = item.features[np.arange(len(item.order_ids)), allocation]
                    model = models["decoder"]
                selection_time += perf_counter() - started
                if (
                    policy in {"recent", "balanced", "static_utility", "learned_utility"}
                    and allocation.sum() > budget
                ):
                    raise ValueError("Context budget exceeded")
                retained.append(int(allocation.sum()))
                started = perf_counter()
                probability = predict(model, x)
                decoder_time += perf_counter() - started
                observed_mask = label_mask(aligned_outcomes(item, sample.observed), horizon)
                complete_mask = label_mask(aligned_outcomes(item, sample.complete), horizon)
                observed.append(float(observed_nll(probability, observed_mask).mean()))
                complete.append(float(observed_nll(probability, complete_mask).mean()))
                risk = probability[:, 1 : 1 + horizon].sum(axis=1)
                outcome = complete_mask[:, 1 : 1 + horizon].sum(axis=1)
                brier.append(float(np.mean((risk - outcome) ** 2)))
                # Assignment ablation only: no refit, no input or label modification.
                shuffled = probability[permutation_rng.permutation(len(probability))]
                permuted.append(float(observed_nll(shuffled, observed_mask).mean()))
            scores = np.array(observed)
            patient_scores[policy] = scores
            metrics[policy] = dict(
                observed_nll=float(scores.mean()),
                synthetic_complete_nll=float(np.mean(complete)),
                synthetic_complete_execution_brier=float(np.mean(brier)),
                prediction_assignment_permutation_nll=float(np.mean(permuted)),
                mean_retained_event_slots=float(np.mean(retained)),
                max_retained_event_slots=max(retained),
                obeys_context_budget=policy
                in {"recent", "balanced", "static_utility", "learned_utility"},
            )
            costs[policy] = dict(
                selection_seconds=selection_time,
                decoder_seconds=decoder_time,
                decoder_parameter_count=model["parameter_count"],
                allocator_parameter_count=models["allocator"]["parameter_count"]
                if policy == "learned_utility"
                else 0,
                extra_per_order_summary_floats=6 if policy == "per_order_summary" else 0,
                extra_per_order_allocator_descriptor_floats=encoded[0].descriptors.shape[1]
                if policy in {"learned_utility", "descriptor_direct"}
                else 0,
            )
        comparisons = {
            "learned_minus_" + policy: _paired(
                patient_scores["learned_utility"] - patient_scores[policy],
                seed + 71,
                config["bootstrap_replicates"],
            )
            for policy in POLICIES
            if policy != "learned_utility"
        }
        reports.append(dict(budget=budget, metrics=metrics, paired_observed_nll=comparisons))
        resources.append(dict(budget=budget, policies=costs))
    return reports, dict(
        prefix_encoding_seconds=encoding_seconds,
        mean_scanned_events=float(np.mean([e.scanned_events for e in encoded])),
        max_per_patient_encoded_array_bytes=max(
            e.features.nbytes + e.descriptors.nbytes + e.summaries.nbytes + e.counts.nbytes
            for e in encoded
        ),
        total_materialized_evaluation_array_bytes=sum(
            e.features.nbytes + e.descriptors.nbytes + e.summaries.nbytes + e.counts.nbytes
            for e in encoded
        ),
        shared_counter_floats=4,
        known_order_birth_times_charged_separately=True,
        total_peak_ram_measured=False,
        event_context_budget_is_not_total_memory_budget=True,
        full_prefix_scanned_by_implementation=True,
        budgets=resources,
    )


def run_demo(config_path: Path, run_dir: Path):
    config, digest = load_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_relation_memory_prototype",
        status="running",
        data_class="synthetic",
        started_utc=datetime.now(UTC).isoformat(),
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        config_file_sha256=digest,
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        python=platform.python_version(),
        packages={p: importlib.metadata.version(p) for p in ("numpy", "PyYAML")},
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        gpu_used=False,
        novel_algorithm_established=False,
        publication_readiness="not_established",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        write_json(run_dir / "config.json", config)
        cases, resources, fitted = [], [], []
        for seed in config["seeds"]:
            for scenario in config["scenarios"]:
                for orders in config["orders_per_patient"]:
                    groups = []
                    for offset, split in enumerate(("decoder", "allocator", "evaluation")):
                        groups.append(
                            generate(
                                seed + offset * 100_003,
                                scenario,
                                config[split + "_patients"],
                                orders,
                                split,
                                config["history_steps"],
                                config["horizon_steps"],
                                config["censor_probability"],
                            )
                        )
                    patient_sets = [{s.context.patient_id for s in group} for group in groups]
                    if any(patient_sets[i] & patient_sets[j] for i in range(3) for j in range(i)):
                        raise ValueError("Generated patient leakage")
                    started = perf_counter()
                    models = fit_case(config, groups[0], groups[1])
                    fit_seconds = perf_counter() - started
                    results, cost = evaluate_case(config, groups[2], models, seed)
                    key = dict(seed=seed, scenario=scenario, orders_per_patient=orders)
                    cases.append(dict(**key, budgets=results))
                    resources.append(dict(**key, fit_seconds=fit_seconds, **cost))
                    fitted.append(dict(**key, models=models))
        write_json(
            run_dir / "metrics.json",
            dict(
                data_class="synthetic",
                cases=cases,
                interpretation=(
                    "Generated mechanism comparison only; conditional intervals omit fitting "
                    "and selection uncertainty. No clinical gate or SOTA comparison."
                ),
            ),
        )
        write_json(run_dir / "resources.json", dict(data_class="synthetic", cases=resources))
        write_json(run_dir / "models.json", dict(data_class="synthetic", cases=fitted))
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise ValueError("Memory prototype source or config changed")
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
            run_dir=str(run_dir),
            cases=len(cases),
            budget_comparisons=len(cases) * len(config["budgets"]),
            clinical_advancement_decision="not_applicable",
            publication_readiness="not_established",
        )
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
