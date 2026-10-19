"""R001: nested patient CV comparing two selection objectives on one fixed model bank.

This is a post-pivot development benchmark, not independent clinical confirmation or
a new scoring-rule method. Original W001/W002 settings and decisions are untouched.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

from ies.models.history_piecewise import fit_history_model, predict_hazards
from ies.models.survival_tree import fit_tree, predict_tree
from ies.selection_scores import (
    cause_losses,
    coherent_rows,
    conditional_endpoint_percentiles,
    patient_weights,
)
from ies.workflow_cv import MODELS, encode_workflow
from ies.workflow_diagnostics import cumulative_risks, execution_targets, probability_summary

MODE = "workflow_selection_objective_benchmark"
SEEDS = [20261020, 20261021, 20261022]
CANDIDATES = [(family, representation) for representation in MODELS for family in ("ph", "tree")]
NAMES = [f"{family}_{representation}" for family, representation in CANDIDATES]
POLICIES = ("joint_nll", "upper_brier")
FIXED = dict(
    schema_version=1,
    experiment="R001",
    evaluation_scope="original_training_nested_patient_cv",
    outer_folds=5,
    inner_folds=3,
    scales_hours=[1.0, 4.0, 12.0, 24.0],
    bin_edges_hours=[0.0, 1.0, 2.0, 4.0, 8.0, 12.0, 24.0],
    horizons_hours=[1.0, 4.0, 12.0, 24.0],
    horizon_weights=[0.25] * 4,
    ridge=1.0,
    max_iterations=100,
    tolerance=1e-8,
    tree_max_depth=2,
    tree_min_leaf_patients=25,
    tree_quantiles=[0.25, 0.5, 0.75],
    tree_prior_events=0.5,
    tree_prior_hours=1.0,
    selection_tie_tolerance=1e-12,
)


def validate_config(config):
    if not isinstance(config, dict) or set(config) != set(FIXED) | {
        "seeds",
        "bootstrap_replicates",
    }:
        raise ValueError("Invalid selection config")
    if any(
        config[key] != expected
        or type(config[key]) is not type(expected)
        or (isinstance(expected, list) and any(type(x) not in (int, float) for x in config[key]))
        for key, expected in FIXED.items()
    ):
        raise ValueError("Selection design changed")
    if (
        not isinstance(config["seeds"], list)
        or not config["seeds"]
        or any(type(s) is not int or s not in SEEDS for s in config["seeds"])
        or len(set(config["seeds"])) != len(config["seeds"])
        or type(config["bootstrap_replicates"]) is not int
        or not 2 <= config["bootstrap_replicates"] <= 1000
    ):
        raise ValueError("Invalid selection repetitions")
    return config


def load_config(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise ValueError("Invalid selection config file")
    content = path.read_bytes()
    return validate_config(yaml.safe_load(content)), hashlib.sha256(content).hexdigest()


def group_folds(patients, count, seed, context):
    unique = set(patients)
    if len(unique) < count or count not in (3, 5) or any(not p for p in unique):
        raise ValueError("Insufficient selection patients")
    ordered = sorted(
        unique, key=lambda p: (hashlib.sha256(f"R001:{seed}:{context}:{p}".encode()).digest(), p)
    )
    assignment = {patient: i % count for i, patient in enumerate(ordered)}
    return np.array([assignment[p] for p in patients])


def _fit(rows, features, candidate, config, data_class):
    family, representation = candidate
    x = features[representation]
    if family == "ph":
        model = fit_history_model(
            rows,
            {r["order_id"]: v for r, v in zip(rows, x, strict=True)},
            config["bin_edges_hours"],
            config["ridge"],
            config["max_iterations"],
            config["tolerance"],
            representation,
            data_class=data_class,
        )
        model.pop("train_patients")
    else:
        model = fit_tree(
            x,
            [r["duration"] for r in rows],
            [r["cause"] for r in rows],
            [r["patient_id"] for r in rows],
            config["bin_edges_hours"],
            max_depth=config["tree_max_depth"],
            min_leaf_patients=config["tree_min_leaf_patients"],
            quantiles=config["tree_quantiles"],
            prior_events=config["tree_prior_events"],
            prior_hours=config["tree_prior_hours"],
        )
    return model


def _predict(model, features, candidate):
    return (predict_hazards if candidate[0] == "ph" else predict_tree)(
        model, features[candidate[1]]
    )


def _take(features, selected):
    return {name: values[selected] for name, values in features.items()}


def _digest(patients):
    return hashlib.sha256("\n".join(sorted(set(patients))).encode()).hexdigest()


def select_candidates(rows, features, config, seed, context, data_class):
    """Only the outer TRAINING partition can enter this function."""
    patients = [r["patient_id"] for r in rows]
    assignments = group_folds(patients, config["inner_folds"], seed, context)
    weights = patient_weights(patients)
    scores = np.full((len(rows), len(CANDIDATES), 2), np.nan)
    audits = []
    for fold in range(config["inner_folds"]):
        train, evaluate = assignments != fold, assignments == fold
        training = [r for r, use in zip(rows, train, strict=True) if use]
        evaluation = [r for r, use in zip(rows, evaluate, strict=True) if use]
        train_patients, eval_patients = (
            {r["patient_id"] for r in training},
            {r["patient_id"] for r in evaluation},
        )
        if train_patients & eval_patients:
            raise ValueError("Inner patient leakage")
        audits.append(
            dict(
                fold=fold,
                training_patient_sha256=_digest(train_patients),
                evaluation_patient_sha256=_digest(eval_patients),
            )
        )
        times, causes = [r["duration"] for r in evaluation], [r["cause"] for r in evaluation]
        for j, candidate in enumerate(CANDIDATES):
            model = _fit(training, _take(features, train), candidate, config, data_class)
            rates = _predict(model, _take(features, evaluate), candidate)
            probabilities = cumulative_risks(
                rates, config["bin_edges_hours"], config["horizons_hours"]
            )[:, :, 0]
            scores[evaluate, j, 0] = cause_losses(
                times, causes, rates, config["bin_edges_hours"]
            ).sum(axis=1)
            scores[evaluate, j, 1] = coherent_rows(
                probabilities, times, causes, config["horizons_hours"], config["horizon_weights"]
            )[:, 1]
    if not np.isfinite(scores).all():
        raise ValueError("Incomplete inner selection")
    means = np.einsum("i,ijk->jk", weights, scores)
    selected = [
        int(np.flatnonzero(means[:, j] <= means[:, j].min() + config["selection_tie_tolerance"])[0])
        for j in (0, 1)
    ]
    return selected, means.tolist(), audits


def _summary(probabilities, losses, times, causes, patients, config):
    weights = patient_weights(patients)
    bounds = coherent_rows(
        probabilities, times, causes, config["horizons_hours"], config["horizon_weights"]
    )
    horizons = []
    for j, h in enumerate(config["horizons_hours"]):
        target, unknown = execution_targets(times, causes, h)
        point_bounds = coherent_rows(probabilities[:, j : j + 1], times, causes, [h], [1.0])
        description = probability_summary(probabilities[:, j], target, unknown)
        # Existing calibration bins are order-weighted; primary aggregate is patient-weighted.
        horizons.append(
            dict(
                horizon_hours=h,
                patient_mean_brier_bounds=(weights @ point_bounds).tolist(),
                order_weighted_description=description,
            )
        )
    return dict(
        patient_mean_nll=float(weights @ losses.sum(axis=1)),
        patient_mean_cause_nll=(weights @ losses).tolist(),
        order_mean_nll=float(losses.sum(axis=1).mean()),
        patient_mean_brier_bounds=(weights @ bounds).tolist(),
        order_mean_brier_bounds=bounds.mean(axis=0).tolist(),
        horizons=horizons,
    )


def run_selection_cv(cohort, grouped, config, *, data_class):
    validate_config(config)
    if data_class not in {"synthetic", "restricted_clinical"}:
        raise ValueError("Invalid selection data class")
    rows = sorted(cohort, key=lambda r: (r["patient_id"], r["order_id"]))
    if (
        not rows
        or len(rows) > 20000
        or len({r["order_id"] for r in rows}) != len(rows)
        or set(grouped) - {r["order_id"] for r in rows}
        or any(
            r["split"] != "train"
            or not r["patient_id"]
            or not r["order_id"]
            or type(r["cause"]) is not int
            for r in rows
        )
    ):
        raise ValueError("Invalid selection cohort")
    times, causes = np.array([r["duration"] for r in rows]), np.array([r["cause"] for r in rows])
    execution_targets(times, causes, 24)
    patients = np.array([r["patient_id"] for r in rows])
    if len(set(patients)) < 30:
        raise ValueError("Insufficient nested patient support")
    encoded = [
        encode_workflow(grouped.get(r["order_id"], []), config["scales_hours"]) for r in rows
    ]
    features = {mode: np.stack([values[mode] for values in encoded]) for mode in MODELS}
    reports, saved_models = [], []
    for seed in config["seeds"]:
        assignments = group_folds(patients, config["outer_folds"], seed, "outer")
        risks = np.full((len(rows), len(CANDIDATES), 4), np.nan)
        losses = np.full((len(rows), len(CANDIDATES), 3), np.nan)
        selected_risks = np.full((len(rows), 2, 4), np.nan)
        selected_losses = np.full((len(rows), 2, 3), np.nan)
        choices = []
        for fold in range(config["outer_folds"]):
            train, evaluate = assignments != fold, assignments == fold
            training = [r for r, use in zip(rows, train, strict=True) if use]
            if set(patients[train]) & set(patients[evaluate]):
                raise ValueError("Outer patient leakage")
            selected, inner_scores, audits = select_candidates(
                training, _take(features, train), config, seed, f"inner:{fold}", data_class
            )
            fold_models = {}
            for j, candidate in enumerate(CANDIDATES):
                model = _fit(training, _take(features, train), candidate, config, data_class)
                rates = _predict(model, _take(features, evaluate), candidate)
                risks[evaluate, j] = cumulative_risks(
                    rates, config["bin_edges_hours"], config["horizons_hours"]
                )[:, :, 0]
                losses[evaluate, j] = cause_losses(
                    times[evaluate], causes[evaluate], rates, config["bin_edges_hours"]
                )
                fold_models[NAMES[j]] = model
            for policy, candidate_index in enumerate(selected):
                selected_risks[evaluate, policy] = risks[evaluate, candidate_index]
                selected_losses[evaluate, policy] = losses[evaluate, candidate_index]
            choice = dict(
                fold=fold,
                selected=dict(zip(POLICIES, [NAMES[j] for j in selected], strict=True)),
                inner_patient_mean_scores=inner_scores,
                training_patient_sha256=_digest(patients[train]),
                evaluation_patient_sha256=_digest(patients[evaluate]),
                inner_assignments=audits,
            )
            choices.append(choice)
            saved_models.append(
                dict(
                    seed=seed,
                    fold=fold,
                    training_patient_sha256=choice["training_patient_sha256"],
                    models=fold_models,
                )
            )
        if not all(np.isfinite(a).all() for a in (risks, losses, selected_risks, selected_losses)):
            raise ValueError("Incomplete outer predictions")
        primary_rows = coherent_rows(
            selected_risks[:, 1],
            times,
            causes,
            config["horizons_hours"],
            config["horizon_weights"],
            selected_risks[:, 0],
        )
        delta_nll = selected_losses[:, 1] - selected_losses[:, 0]
        weights = patient_weights(patients)
        reports.append(
            dict(
                seed=seed,
                choices=choices,
                candidates={
                    name: _summary(risks[:, j], losses[:, j], times, causes, patients, config)
                    for j, name in enumerate(NAMES)
                },
                policies={
                    policy: _summary(
                        selected_risks[:, j], selected_losses[:, j], times, causes, patients, config
                    )
                    for j, policy in enumerate(POLICIES)
                },
                primary_comparison=dict(
                    name="upper_brier_minus_joint_nll",
                    patient_mean_completion_bounds=(weights @ primary_rows).tolist(),
                    order_mean_completion_bounds=primary_rows.mean(axis=0).tolist(),
                    conditional_endpoint_percentiles=conditional_endpoint_percentiles(
                        patients, primary_rows, config["bootstrap_replicates"], seed
                    ),
                    patient_mean_nll_difference=float(weights @ delta_nll.sum(axis=1)),
                    patient_mean_cause_nll_difference=(weights @ delta_nll).tolist(),
                    fold_patient_mean_completion_bounds=[
                        (
                            patient_weights(patients[assignments == f])
                            @ primary_rows[assignments == f]
                        ).tolist()
                        for f in range(config["outer_folds"])
                    ],
                    horizon_patient_mean_completion_bounds=[
                        (
                            weights
                            @ coherent_rows(
                                selected_risks[:, 1, j : j + 1],
                                times,
                                causes,
                                [h],
                                [1.0],
                                selected_risks[:, 0, j : j + 1],
                            )
                        ).tolist()
                        for j, h in enumerate(config["horizons_hours"])
                    ],
                ),
            )
        )
    report = dict(
        schema_version=1,
        mode=MODE,
        experiment="R001",
        status="complete",
        data_class="synthetic" if data_class == "synthetic" else "restricted_aggregate",
        evaluation_scope=config["evaluation_scope"],
        candidate_names=NAMES,
        horizons_hours=config["horizons_hours"],
        primary_comparison="upper_brier_minus_joint_nll",
        primary_weighting="equal_patient_equal_horizon",
        validation_split_evaluated=False,
        test_split_evaluated=False,
        raw_source_scan=False,
        n_patients=len(set(patients)),
        n_orders=len(rows),
        seeds=reports,
        clinical_advancement_decision="not_applicable",
        publication_readiness="not_established",
        note="Data-informed exploratory nested CV, not independent confirmation. Finite-sample "
        "completion bounds are not confidence intervals. Endpoint bootstraps condition on fitted "
        "overlapping folds and omit fitting/selection uncertainty. "
        "Seeds are not independent studies. "
        "Bounds do not assume independent censoring; fitted models retain their assumptions.",
    )
    return report, dict(data_class=data_class, models=saved_models)


def qualitative_summary(report):
    if (
        report["mode"] != MODE
        or report["status"] != "complete"
        or report["validation_split_evaluated"] is not False
        or report["test_split_evaluated"] is not False
        or report["candidate_names"] != NAMES
        or report["horizons_hours"] != FIXED["horizons_hours"]
    ):
        raise ValueError("Invalid selection summary")

    def position(bounds):
        if len(bounds) != 2 or not np.isfinite(bounds).all() or bounds[0] > bounds[1]:
            raise ValueError("Invalid selection bounds")
        return "below_zero" if bounds[1] < 0 else "above_zero" if bounds[0] > 0 else "includes_zero"

    seeds = []
    if not 1 <= len(report["seeds"]) <= 3:
        raise ValueError("Invalid summary repetitions")
    seen = set()
    for run in report["seeds"]:
        if type(run["seed"]) is not int or run["seed"] not in SEEDS:
            raise ValueError("Invalid selection seed")
        if run["seed"] in seen:
            raise ValueError("Duplicate summary seed")
        seen.add(run["seed"])
        result = run["primary_comparison"]
        if len(result["horizon_patient_mean_completion_bounds"]) != 4:
            raise ValueError("Invalid summary horizons")
        nll = result["patient_mean_nll_difference"]
        if not np.isfinite(nll):
            raise ValueError("Invalid selection loss")
        chosen = [r["selected"] for r in run["choices"]]
        if len(chosen) != 5 or any(
            set(row) != set(POLICIES) or any(v not in NAMES for v in row.values()) for row in chosen
        ):
            raise ValueError("Invalid selected candidate")
        seeds.append(
            dict(
                seed=run["seed"],
                selected_candidates_by_outer_fold=chosen,
                selections="identical"
                if all(c[POLICIES[0]] == c[POLICIES[1]] for c in chosen)
                else "some_different",
                primary_completion_bounds=position(result["patient_mean_completion_bounds"]),
                order_weighted_sensitivity=position(result["order_mean_completion_bounds"]),
                horizon_completion_bounds=[
                    position(v) for v in result["horizon_patient_mean_completion_bounds"]
                ],
                nll_direction="lower" if nll < 0 else "higher" if nll > 0 else "equal",
            )
        )
    return dict(
        mode=MODE,
        evaluation_scope="original_training_nested_patient_cv",
        seeds=seeds,
        horizons_hours=FIXED["horizons_hours"],
        comparison="upper_brier_minus_joint_nll",
        clinical_advancement_decision="not_applicable",
        publication_readiness="not_established",
        note="Descriptive development results only. Bounds are not confidence intervals; "
        "no automatic next experiment.",
    )


def paper_tables(report):
    """Numeric aggregate material stays in private storage; never print this in the CLI."""
    qualitative_summary(report)
    lines = [
        "# R001 private aggregate tables",
        "",
        "Data class: " + report["data_class"],
        "",
        "Exploratory development analysis; not an accepted or completed manuscript.",
        "Completion bounds are not confidence intervals. Utility and novelty are unproven.",
        "No original validation/test evaluation. All horizons and all seeds retained.",
        "",
        f"Patients: {report['n_patients']}; orders: {report['n_orders']}.",
        "",
        "| Seed | Model/policy | Patient NLL | Cause 1 / 2 / 3 NLL | "
        "Patient Brier bounds | Order Brier bounds |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for run in report["seeds"]:
        for name, row in dict(run["candidates"], **run["policies"]).items():
            lines.append(
                f"| {run['seed']} | {name} | {row['patient_mean_nll']:.8g} | "
                f"{json.dumps(row['patient_mean_cause_nll'])} | "
                f"{json.dumps(row['patient_mean_brier_bounds'])} | "
                f"{json.dumps(row['order_mean_brier_bounds'])} |"
            )
    lines += [
        "",
        "## All horizon results",
        "",
        "| Seed | Model/policy | Horizon (h) | Patient Brier bounds |",
        "| --- | --- | --- | --- |",
    ]
    for run in report["seeds"]:
        for name, row in dict(run["candidates"], **run["policies"]).items():
            for h in row["horizons"]:
                lines.append(
                    f"| {run['seed']} | {name} | {h['horizon_hours']} | "
                    f"{json.dumps(h['patient_mean_brier_bounds'])} |"
                )
    lines += [
        "",
        "## Primary paired comparison: upper_brier minus joint_nll",
        "",
        "Equal patient and equal horizon weights. Negative favors upper_brier.",
        "",
    ]
    for run in report["seeds"]:
        lines += [
            f"### Seed {run['seed']}",
            "",
            "```json",
            json.dumps(run["primary_comparison"], indent=2),
            "```",
            "",
        ]
    return "\n".join(lines) + "\n"
