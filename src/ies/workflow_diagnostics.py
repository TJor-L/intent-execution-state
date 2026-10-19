"""W002: replay frozen development folds and bound execution-probability errors.

Completion bounds are finite-sample diagnostics, not confidence intervals. No censoring
independence assumption, model fit or clinical advancement rule is introduced here.
"""

import hashlib

import numpy as np

from ies.data.events import CAUSES
from ies.losses.competing_risks import validate_edges
from ies.models.history_piecewise import individual_nll, predict_hazards
from ies.workflow_cv import (
    DIMENSIONS,
    MODELS,
    encode_workflow,
    paired_patient_intervals,
    patient_folds,
    validate_workflow_config,
)

MODE = "workflow_frozen_probability_diagnostics"
HORIZONS = [1.0, 4.0, 12.0, 24.0]
RISK_BINS = np.linspace(0, 1, 11)
COMPARISONS = {
    "counts_minus_intercept": ("counts", "intercept"),
    "pooled_minus_counts": ("pooled_timing", "counts"),
    "pooled_minus_intercept": ("pooled_timing", "intercept"),
    "typed_minus_pooled": ("typed_timing", "pooled_timing"),
    "typed_minus_intercept": ("typed_timing", "intercept"),
}


def cumulative_risks(hazards, edges, horizons):
    edges = validate_edges(edges)
    rates = np.asarray(hazards, dtype=float)
    times = np.asarray(horizons, dtype=float)
    if (
        rates.ndim != 3
        or rates.shape[1:] != (len(edges) - 1, len(CAUSES))
        or not np.isfinite(rates).all()
        or (rates < 0).any()
        or times.ndim != 1
        or not len(times)
        or not np.isfinite(times).all()
        or (times < 0).any()
        or (times > edges[-1]).any()
        or (np.diff(times) <= 0).any()
    ):
        raise ValueError("Invalid probability diagnostic inputs")
    totals = rates.sum(axis=2)
    if not np.isfinite(totals).all():
        raise ValueError("Invalid total hazard")
    results = []
    for horizon in times:
        survival = np.ones(len(rates))
        incidence = np.zeros((len(rates), len(CAUSES)))
        for j, width in enumerate(np.clip(horizon - edges[:-1], 0, np.diff(edges))):
            total = totals[:, j]
            shares = np.divide(
                rates[:, j, :],
                total[:, None],
                out=np.zeros_like(incidence),
                where=total[:, None] > 0,
            )
            incidence += survival[:, None] * (-np.expm1(-total * width))[:, None] * shares
            survival *= np.exp(-total * width)
        if not np.allclose(survival + incidence.sum(axis=1), 1, atol=1e-12, rtol=1e-12):
            raise ValueError("Invalid probability mass")
        results.append(np.clip(incidence, 0, 1))
    return np.stack(results, axis=1)


def execution_targets(durations, causes, horizon):
    durations, causes = np.asarray(durations, dtype=float), np.asarray(causes)
    if (
        durations.ndim != 1
        or not len(durations)
        or causes.shape != durations.shape
        or not np.isfinite(durations).all()
        or (durations <= 0).any()
        or (durations > 24).any()
        or not np.isin(causes, [0, 1, 2, 3]).all()
        or not np.isfinite(horizon)
        or not 0 <= horizon <= 24
    ):
        raise ValueError("Invalid diagnostic outcomes")
    # Events on the horizon count; censoring at the horizon means observed through it.
    unknown = (causes == 0) & (durations < horizon)
    positive = (causes == 1) & (durations <= horizon)
    return positive.astype(float), unknown


def _probabilities(values, target):
    values = np.asarray(values, dtype=float)
    if (
        values.shape != target.shape
        or not np.isfinite(values).all()
        or not ((values >= 0) & (values <= 1)).all()
    ):
        raise ValueError("Invalid execution probabilities")
    return values


def squared_error_bounds(predicted, target, unknown, comparator=None):
    """Bounds over binary completions, paired on the SAME unknown label for contrasts."""
    target, unknown = np.asarray(target, dtype=float), np.asarray(unknown)
    if (
        target.ndim != 1
        or not len(target)
        or unknown.shape != target.shape
        or unknown.dtype != bool
        or not np.isin(target, [0, 1]).all()
    ):
        raise ValueError("Invalid completion targets")
    predicted = _probabilities(predicted, target)
    zero, one = predicted**2, (1 - predicted) ** 2
    if comparator is not None:
        other = _probabilities(comparator, target)
        zero, one = zero - other**2, one - (1 - other) ** 2
    observed = np.where(target == 1, one, zero)
    lower = np.where(unknown, np.minimum(zero, one), observed)
    upper = np.where(unknown, np.maximum(zero, one), observed)
    return [float(lower.mean()), float(upper.mean())]


def probability_summary(predicted, target, unknown):
    predicted = _probabilities(predicted, target)
    bins = np.clip(np.searchsorted(RISK_BINS, predicted, side="right") - 1, 0, 9)
    calibration = []
    for index in range(10):
        selected = bins == index
        if not selected.any():
            calibration.append({"bin": index, "orders": 0, "status": "empty"})
            continue
        mean = float(predicted[selected].mean())
        positive = float(target[selected & ~unknown].sum())
        total, missing = int(selected.sum()), int((selected & unknown).sum())
        bounds = [positive / total, (positive + missing) / total]
        calibration.append(
            dict(
                bin=index,
                orders=total,
                unknown_outcomes=missing,
                mean_predicted=mean,
                event_fraction_completion_bounds=bounds,
                observed_minus_predicted_completion_bounds=[x - mean for x in bounds],
            )
        )
    return {
        "brier_completion_bounds": squared_error_bounds(predicted, target, unknown),
        "mean_predicted": float(predicted.mean()),
        "event_fraction_completion_bounds": [
            float(target[~unknown].sum() / len(target)),
            float((target[~unknown].sum() + unknown.sum()) / len(target)),
        ],
        "calibration_bins": calibration,
        "unknown_outcomes": int(unknown.sum()),
        "note": "Finite-sample completion bounds; not sampling intervals or proof of calibration.",
    }


def summarize_diagnostics(report):
    """Allowlisted qualitative feedback; numeric metrics and calibration bins stay private."""
    if (
        report["mode"] != MODE
        or report["status"] != "complete"
        or report["source_replay_verified"] is not True
        or report["model_fitted"] is not False
        or report["validation_split_evaluated"] is not False
        or report["test_split_evaluated"] is not False
    ):
        raise ValueError("Invalid diagnostic summary")

    def position(bounds):
        if len(bounds) != 2 or not np.isfinite(bounds).all() or bounds[0] > bounds[1]:
            raise ValueError("Invalid diagnostic bounds")
        return "below_zero" if bounds[1] < 0 else "above_zero" if bounds[0] > 0 else "includes_zero"

    nll = {}
    for name in COMPARISONS:
        metric = report["nll_comparisons"][name]
        mean, folds = metric["mean_difference"], metric["fold_mean_differences"]
        if not np.isfinite(mean) or len(folds) != 5 or not np.isfinite(folds).all():
            raise ValueError("Invalid diagnostic differences")
        nll[name] = dict(
            mean_loss_direction="lower" if mean < 0 else "higher" if mean > 0 else "equal",
            conditional_interval=position(metric["conditional_patient_bootstrap_95ci"]),
            fold_directions="all_lower"
            if all(x < 0 for x in folds)
            else "all_higher"
            if all(x > 0 for x in folds)
            else "mixed",
        )
    if [r["horizon_hours"] for r in report["horizons"]] != HORIZONS:
        raise ValueError("Invalid diagnostic horizons")
    horizons = []
    for row in report["horizons"]:
        calibration = {}
        for model in MODELS:
            m = row["models"][model]
            mean, bounds = m["mean_predicted"], m["event_fraction_completion_bounds"]
            position(bounds)
            if not np.isfinite(mean) or not 0 <= mean <= 1 or not 0 <= bounds[0] <= bounds[1] <= 1:
                raise ValueError("Invalid diagnostic mean risks")
            calibration[model] = (
                "below" if mean < bounds[0] else "above" if mean > bounds[1] else "inside"
            )
        horizons.append(
            dict(
                horizon_hours=row["horizon_hours"],
                paired_brier_completion_bounds={
                    name: position(row["paired_brier_completion_bounds"][name])
                    for name in COMPARISONS
                },
                empirical_mean_risk_vs_outcome_bounds=calibration,
            )
        )
    return dict(
        nll_comparisons=nll,
        execution_probability_diagnostics=horizons,
        clinical_advancement_decision="not_applicable",
        note="Completion bounds are finite-sample descriptions, not confidence intervals. "
        "Inside does not establish calibration; outside does not by itself establish population "
        "miscalibration. No refit, independent validation or advancement gate.",
    )


def replay_diagnostics(cohort, grouped, config, models, original_report, *, data_class):
    validate_workflow_config(config)
    if data_class not in {"synthetic", "restricted_clinical"} or models["data_class"] != data_class:
        raise ValueError("Invalid diagnostic data class")
    cohort = sorted(cohort, key=lambda r: (r["patient_id"], r["order_id"]))
    if (
        not cohort
        or any(r["split"] != "train" for r in cohort)
        or len({r["order_id"] for r in cohort}) != len(cohort)
    ):
        raise ValueError("Invalid diagnostic training cohort")
    if set(grouped) - {r["order_id"] for r in cohort}:
        raise ValueError("Unexpected diagnostic history")
    durations, causes = [r["duration"] for r in cohort], [r["cause"] for r in cohort]
    execution_targets(durations, causes, 24)
    folds = patient_folds([r["patient_id"] for r in cohort], config["folds"], config["seed"])
    assignments = np.array([folds[r["patient_id"]] for r in cohort])
    encoded = [
        encode_workflow(grouped.get(r["order_id"], []), config["scales_hours"]) for r in cohort
    ]
    features = {mode: np.stack([row[mode] for row in encoded]) for mode in MODELS}
    saved = models["fold_models"]
    if len(saved) != 5 or {r["fold"] for r in saved} != set(range(5)):
        raise ValueError("Invalid diagnostic folds")
    old_folds = {f["fold"]: f for f in original_report["folds"]}
    losses = {mode: np.full(len(cohort), np.nan) for mode in MODELS}
    predictions = {mode: np.full((len(cohort), len(HORIZONS)), np.nan) for mode in MODELS}
    for saved_fold in saved:
        fold = saved_fold["fold"]
        held_out, training = assignments == fold, assignments != fold
        patient_hash = hashlib.sha256(
            "\n".join(
                sorted({r["patient_id"] for r, keep in zip(cohort, training, strict=True) if keep})
            ).encode()
        ).hexdigest()
        for mode in MODELS:
            model = saved_fold["models"][mode]
            dimension = DIMENSIONS[mode]
            if (
                model["model"] != "history_piecewise_proportional_v1"
                or model["mode"] != mode
                or model["data_class"] != data_class
                or model["edges_hours"] != config["bin_edges_hours"]
                or model["causes"] != list(CAUSES)
                or model["feature_dimension"] != dimension
                or model["ridge"] != config["ridge"]
                or model["optimization_converged"] is not True
                or model["train_patient_assignment_sha256"] != patient_hash
                or "train_patients" in model
            ):
                raise ValueError("Frozen model binding mismatch")
            for name, shape in (
                ("feature_mean", (dimension,)),
                ("feature_scale", (dimension,)),
                ("coefficients", (3, dimension)),
                ("intercepts_log_rate", (3, 6)),
            ):
                array = np.asarray(model[name], dtype=float)
                if array.shape != shape or not np.isfinite(array).all():
                    raise ValueError("Invalid frozen model")
            scales = features[mode][training].std(axis=0)
            scales[scales < 1e-8] = 1
            if not np.allclose(
                model["feature_mean"], features[mode][training].mean(axis=0), rtol=1e-10, atol=1e-12
            ) or not np.allclose(model["feature_scale"], scales, rtol=1e-10, atol=1e-12):
                raise ValueError("Frozen normalization mismatch")
            rates = predict_hazards(model, features[mode][held_out])
            losses[mode][held_out] = individual_nll(
                np.asarray(durations)[held_out],
                np.asarray(causes)[held_out],
                rates,
                config["bin_edges_hours"],
            )
            if not np.isclose(
                losses[mode][held_out].mean(),
                old_folds[fold]["nll_per_order"][mode],
                rtol=1e-9,
                atol=1e-10,
            ):
                raise ValueError("Frozen fold replay mismatch")
            predictions[mode][held_out] = cumulative_risks(
                rates, config["bin_edges_hours"], HORIZONS
            )[:, :, 0]
    for mode in MODELS:
        if (
            not np.isfinite(losses[mode]).all()
            or not np.isfinite(predictions[mode]).all()
            or not np.isclose(
                losses[mode].mean(),
                original_report["metrics"][mode]["nll_per_order"],
                rtol=1e-9,
                atol=1e-10,
            )
        ):
            raise ValueError("Frozen replay incomplete or inconsistent")
    contrasts = {name: losses[a] - losses[b] for name, (a, b) in COMPARISONS.items()}
    intervals = paired_patient_intervals(
        cohort, contrasts, config["bootstrap_replicates"], config["seed"]
    )
    horizon_reports = []
    for j, horizon in enumerate(HORIZONS):
        target, unknown = execution_targets(durations, causes, horizon)
        horizon_reports.append(
            {
                "horizon_hours": horizon,
                "models": {
                    m: probability_summary(predictions[m][:, j], target, unknown) for m in MODELS
                },
                "paired_brier_completion_bounds": {
                    name: squared_error_bounds(
                        predictions[a][:, j], target, unknown, predictions[b][:, j]
                    )
                    for name, (a, b) in COMPARISONS.items()
                },
            }
        )
    return {
        "mode": MODE,
        "experiment": "W002",
        "status": "complete",
        "data_class": "synthetic" if data_class == "synthetic" else "restricted_aggregate",
        "source_replay_verified": True,
        "diagnostic_spec": {
            "horizons_hours": HORIZONS,
            "risk_bin_edges": RISK_BINS.tolist(),
            "execution_cause": 1,
            "unknown_outcome_rule": "cause_zero_and_duration_strictly_before_horizon",
            "completion_bounds_are_confidence_intervals": False,
        },
        "model_fitted": False,
        "evaluation_scope": "original_training_out_of_fold_replay",
        "validation_split_evaluated": False,
        "test_split_evaluated": False,
        "horizons": horizon_reports,
        "nll_comparisons": {
            name: {
                "mean_difference": float(values.mean()),
                "conditional_patient_bootstrap_95ci": intervals[name],
                "fold_mean_differences": [float(values[assignments == f].mean()) for f in range(5)],
            }
            for name, values in contrasts.items()
        },
        "clinical_advancement_decision": "not_applicable",
        "note": "Post-selection development diagnostics, not independent validation. Completion "
        "bounds describe unknown binary outcomes, not sampling uncertainty. Bounds containing zero "
        "do not prove calibration or equivalence. Existing negative primary results remain "
        "unchanged.",
    }
