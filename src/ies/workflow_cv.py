"""W001: fixed single-clock workflow controls, cross-fitted within training patients."""

import hashlib
import math
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from ies.clinical_baseline import ClinicalBaselineError
from ies.models.history_piecewise import fit_history_model, individual_nll, predict_hazards

MODE = "workflow_training_cross_validation"
MODELS = ("intercept", "counts", "pooled_timing", "typed_timing")
DIMENSIONS = dict(zip(MODELS, (0, 2, 6, 10), strict=True))
CONTRASTS = {
    "counts_minus_intercept": ("counts", "intercept"),
    "pooled_minus_counts": ("pooled_timing", "counts"),
    "typed_minus_pooled": ("typed_timing", "pooled_timing"),
    "typed_minus_intercept": ("typed_timing", "intercept"),
}


def load_workflow_config(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    try:
        value = yaml.safe_load(content)
        expected = {
            "schema_version",
            "experiment",
            "evaluation_scope",
            "seed",
            "folds",
            "scales_hours",
            "bin_edges_hours",
            "ridge",
            "max_iterations",
            "tolerance",
            "bootstrap_replicates",
            "minimum_nll_improvement",
            "minimum_improved_folds",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError
        if (
            type(value["schema_version"]) is not int
            or value["schema_version"] != 1
            or value["experiment"] != "W001"
            or value["evaluation_scope"] != "training_patient_cross_validation"
            or type(value["seed"]) is not int
            or not 0 <= value["seed"] < 2**32
            or type(value["folds"]) is not int
            or value["folds"] != 5
            or type(value["minimum_improved_folds"]) is not int
            or not 1 <= value["minimum_improved_folds"] <= value["folds"]
            or type(value["max_iterations"]) is not int
            or not 1 <= value["max_iterations"] <= 100
            or type(value["bootstrap_replicates"]) is not int
            or not 2 <= value["bootstrap_replicates"] <= 1000
        ):
            raise ValueError
        for key in ("ridge", "tolerance", "minimum_nll_improvement"):
            number = value[key]
            if type(number) not in (int, float) or not math.isfinite(number) or number <= 0:
                raise ValueError
        for key, expected_values in (
            ("scales_hours", [1, 4, 12, 24]),
            ("bin_edges_hours", [0, 1, 2, 4, 8, 12, 24]),
        ):
            values = value[key]
            if (
                not isinstance(values, list)
                or values != expected_values
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in values)
            ):
                raise ValueError
    except (ValueError, TypeError, KeyError, yaml.YAMLError):
        raise ClinicalBaselineError("invalid_workflow_config") from None
    return value, hashlib.sha256(content).hexdigest()


def encode_workflow(rows: list[dict], scales: list[float]) -> dict[str, np.ndarray]:
    """Counts refer to retained events only, never pending orders or service workload."""
    if scales != [1, 4, 12, 24]:
        raise ValueError("Invalid workflow scales")
    counts = np.zeros(2)
    decays = np.zeros((2, 4))
    if len(rows) > 24:
        raise ValueError("Workflow retained history cap exceeded")
    for row in rows:
        kind = row["event_kind"]
        occurred, available = row["occurrence_lag_hours"], row["availability_lag_hours"]
        if (
            type(kind) is not int
            or kind not in (0, 1)
            or not all(
                isinstance(x, (int, float)) and math.isfinite(x) for x in (occurred, available)
            )
            or not 0 < occurred <= 24
            or not 0 <= available <= occurred
        ):
            raise ValueError("Invalid workflow history")
        counts[kind] += 1
        decays[kind] += np.exp(-available / np.asarray(scales))
    return {
        "intercept": np.zeros(0),
        "counts": counts,
        "pooled_timing": np.concatenate([counts, decays.sum(axis=0)]),
        "typed_timing": np.concatenate([counts, decays.ravel()]),
    }


def patient_folds(patients: list[str], folds: int, seed: int) -> dict[str, int]:
    patients = set(patients)
    if folds != 5 or len(patients) < folds or any(not p for p in patients):
        raise ValueError("Insufficient workflow patients")
    ordered = sorted(
        patients, key=lambda p: (hashlib.sha256(f"W001:{seed}:{p}".encode()).digest(), p)
    )
    return {patient: index % folds for index, patient in enumerate(ordered)}


def paired_patient_intervals(rows, values, replicates, seed):
    """Order-weighted paired cluster bootstrap, conditional on the fitted CV models."""
    _, inverse = np.unique([r["patient_id"] for r in rows], return_inverse=True)
    sizes = np.bincount(inverse)
    names = list(values)
    sums = np.stack([np.bincount(inverse, weights=values[name]) for name in names], axis=1)
    samples = np.zeros((replicates, len(names)))
    rng = np.random.default_rng(seed)
    for index in range(replicates):
        chosen = rng.integers(len(sizes), size=len(sizes))
        samples[index] = sums[chosen].sum(axis=0) / sizes[chosen].sum()
    return {
        name: np.quantile(samples[:, index], [0.025, 0.975]).tolist()
        for index, name in enumerate(names)
    }


def workflow_cross_validation(cohort, grouped, config, *, data_class):
    if data_class not in {"synthetic", "restricted_clinical"}:
        raise ValueError("Invalid workflow data class")
    # This engine accepts only original training records. It cannot repurpose held-out data.
    cohort = sorted(cohort, key=lambda row: (row["patient_id"], row["order_id"]))
    if not cohort or len({r["order_id"] for r in cohort}) != len(cohort):
        raise ValueError("Invalid workflow cohort")
    for row in cohort:
        if (
            row["split"] != "train"
            or not row["patient_id"]
            or not row["order_id"]
            or type(row["cause"]) is not int
            or row["cause"] not in (0, 1, 2, 3)
            or not math.isfinite(row["duration"])
            or not 0 < row["duration"] <= 24
        ):
            raise ValueError("Invalid workflow training record")
    if set(grouped) - {r["order_id"] for r in cohort}:
        raise ValueError("Unexpected workflow history")
    folds = patient_folds([r["patient_id"] for r in cohort], config["folds"], config["seed"])
    encoded = {
        r["order_id"]: encode_workflow(grouped.get(r["order_id"], []), config["scales_hours"])
        for r in cohort
    }
    features = {mode: {order: values[mode] for order, values in encoded.items()} for mode in MODELS}
    row_folds = np.array([folds[r["patient_id"]] for r in cohort])
    losses = {mode: np.full(len(cohort), np.nan) for mode in MODELS}
    models, fold_reports = [], []
    for fold in range(config["folds"]):
        training = [r for r, f in zip(cohort, row_folds, strict=True) if f != fold]
        indexes = np.flatnonzero(row_folds == fold)
        evaluation = [cohort[i] for i in indexes]
        if not evaluation or not any(r["cause"] == 1 for r in training):
            raise ValueError("Workflow fold lacks training event support")
        held_out = {r["patient_id"] for r in evaluation}
        fold_models = {}
        for mode in MODELS:
            # Normalization and fitting see only the other four patient folds.
            model = fit_history_model(
                training,
                features[mode],
                config["bin_edges_hours"],
                config["ridge"],
                config["max_iterations"],
                config["tolerance"],
                mode,
                data_class=data_class,
            )
            if held_out & set(model["train_patients"]):
                raise ValueError("Workflow patient leakage")
            hazards = predict_hazards(
                model, np.stack([features[mode][r["order_id"]] for r in evaluation])
            )
            losses[mode][indexes] = individual_nll(
                [r["duration"] for r in evaluation],
                [r["cause"] for r in evaluation],
                hazards,
                config["bin_edges_hours"],
            )
            # Persist reproducible weights, not repeated lists of private patient IDs.
            train_patients = model.pop("train_patients")
            model["train_patient_assignment_sha256"] = hashlib.sha256(
                "\n".join(train_patients).encode()
            ).hexdigest()
            fold_models[mode] = model
        models.append({"fold": fold, "models": fold_models})
        fold_reports.append(
            {
                "fold": fold,
                "evaluation_patients": len(held_out),
                "evaluation_orders": len(evaluation),
                "training_outcome_counts": {
                    str(cause): sum(r["cause"] == cause for r in training) for cause in (0, 1, 2, 3)
                },
                "nll_per_order": {m: float(losses[m][indexes].mean()) for m in MODELS},
                "contrasts": {
                    name: float((losses[a][indexes] - losses[b][indexes]).mean())
                    for name, (a, b) in CONTRASTS.items()
                },
            }
        )
    if any(not np.isfinite(value).all() for value in losses.values()):
        raise ValueError("Incomplete workflow cross-validation")
    values = dict(losses, **{name: losses[a] - losses[b] for name, (a, b) in CONTRASTS.items()})
    intervals = paired_patient_intervals(
        cohort, values, config["bootstrap_replicates"], config["seed"]
    )
    summaries = {
        name: {
            "nll_per_order": float(value.mean()),
            "conditional_patient_bootstrap_95ci": intervals[name],
        }
        for name, value in values.items()
    }
    primary = summaries["typed_minus_pooled"]
    improved = sum(f["contrasts"]["typed_minus_pooled"] < 0 for f in fold_reports)
    supported = (
        primary["nll_per_order"] <= -config["minimum_nll_improvement"]
        and primary["conditional_patient_bootstrap_95ci"][1] < 0
        and improved >= config["minimum_improved_folds"]
        and summaries["typed_minus_intercept"]["nll_per_order"] < 0
    )
    report = {
        "mode": MODE,
        "experiment": "W001",
        "status": "complete",
        "data_class": "synthetic" if data_class == "synthetic" else "restricted_aggregate",
        "evaluation_scope": config["evaluation_scope"],
        "validation_split_evaluated": False,
        "test_split_evaluated": False,
        "original_splits_changed": False,
        "feature_dimensions": DIMENSIONS,
        "n_patients": len(folds),
        "n_orders": len(cohort),
        "outcome_counts": dict(Counter(r["cause"] for r in cohort)),
        "metrics": summaries,
        "folds": fold_reports,
        "primary_contrast": "typed_minus_pooled",
        "typed_timing_development_support": bool(supported),
        "minimum_nll_improvement": config["minimum_nll_improvement"],
        "minimum_improved_folds": config["minimum_improved_folds"],
        "improved_folds": improved,
        "clinical_advancement_decision": "not_applicable",
        "automatic_test_or_gpu": False,
        "note": "Exploratory development CV after a data-informed pivot; unequal feature "
        "capacity. Bootstrap conditions on overlapping fitted folds and omits "
        "model-fitting and design-selection uncertainty; not independent confirmation.",
    }
    return report, {"data_class": data_class, "fold_models": models}
