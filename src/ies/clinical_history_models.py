"""Validation-only matched single-clock and dual-clock clinical history models."""

import hashlib
import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import yaml

from ies.clinical_baseline import ClinicalBaselineError, _verify_cohort
from ies.dual_clock_history import HISTORY_SCHEMA
from ies.feasibility.contract import ROOT
from ies.io import sha256, write_json
from ies.models.history_piecewise import (
    encode_history,
    fit_history_model,
    individual_nll,
    predict_hazards,
)


def load_history_model_config(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    expected = {
        "schema_version",
        "seed",
        "bin_edges_hours",
        "bootstrap_replicates",
        "evaluation_split",
        "availability_scales_hours",
        "dual_occurrence_scales_hours",
        "dual_availability_scales_hours",
        "delay_shifts_hours",
        "ridge",
        "max_iterations",
        "tolerance",
        "minimum_nll_improvement",
        "max_shift_nll_degradation",
    }
    try:
        value = yaml.safe_load(content)
        if not isinstance(value, dict) or set(value) != expected:
            raise ClinicalBaselineError("invalid_history_model_config")
        if (
            value["schema_version"] != 1
            or type(value["seed"]) is not int
            or value["evaluation_split"] != "validation"
            or type(value["bootstrap_replicates"]) is not int
            or not 2 <= value["bootstrap_replicates"] <= 10_000
            or type(value["max_iterations"]) is not int
            or not 1 <= value["max_iterations"] <= 1_000
        ):
            raise ClinicalBaselineError("invalid_history_model_config")
        for name, length in (
            ("availability_scales_hours", 4),
            ("dual_occurrence_scales_hours", 2),
            ("dual_availability_scales_hours", 2),
        ):
            values = value[name]
            if (
                not isinstance(values, list)
                or len(values) != length
                or any(type(item) not in (int, float) or item <= 0 for item in values)
            ):
                raise ClinicalBaselineError("invalid_history_model_config")
        shifts = value["delay_shifts_hours"]
        if (
            not isinstance(shifts, list)
            or len(shifts) < 2
            or shifts[0] != 0
            or any(type(item) not in (int, float) or item < 0 for item in shifts)
            or any(left >= right for left, right in zip(shifts, shifts[1:], strict=False))
        ):
            raise ClinicalBaselineError("invalid_history_model_config")
        edges = value["bin_edges_hours"]
        if (
            not isinstance(edges, list)
            or len(edges) < 2
            or edges[0] != 0
            or edges[-1] != 24
            or any(type(item) not in (int, float) or not math.isfinite(item) for item in edges)
            or any(left >= right for left, right in zip(edges, edges[1:], strict=False))
        ):
            raise ClinicalBaselineError("invalid_history_model_config")
        for name in (
            "ridge",
            "tolerance",
            "minimum_nll_improvement",
            "max_shift_nll_degradation",
        ):
            item = value[name]
            if type(item) not in (int, float) or not math.isfinite(item) or item <= 0:
                raise ClinicalBaselineError("invalid_history_model_config")
        return value, hashlib.sha256(content).hexdigest()
    except (OSError, yaml.YAMLError, TypeError, KeyError):
        raise ClinicalBaselineError("invalid_history_model_config") from None


def _bootstrap(rows, values: dict[str, np.ndarray], replicates: int, seed: int) -> dict:
    patients = sorted({row["patient_id"] for row in rows})
    by_patient = {
        patient: np.flatnonzero([row["patient_id"] == patient for row in rows])
        for patient in patients
    }
    rng = np.random.default_rng(seed)
    estimates = {name: [] for name in values}
    for _ in range(replicates):
        selected = rng.integers(len(patients), size=len(patients))
        indexes = np.concatenate([by_patient[patients[index]] for index in selected])
        for name, losses in values.items():
            estimates[name].append(float(losses[indexes].mean()))
    return {
        name: np.quantile(samples, [0.025, 0.975]).tolist() for name, samples in estimates.items()
    }


def _history_features(grouped, cohort, config, mode, shift=0.0):
    availability = (
        config["availability_scales_hours"]
        if mode == "availability"
        else config["dual_availability_scales_hours"]
    )
    occurrence = [] if mode == "availability" else config["dual_occurrence_scales_hours"]
    return {
        row["order_id"]: encode_history(
            grouped.get(row["order_id"], []), mode, availability, occurrence, shift
        )
        for row in cohort
    }


def run_clinical_history_models(
    cohort_dir: Path,
    history_dir: Path,
    output_dir: Path,
    config: dict,
    config_sha256: str,
    cohort_manifest_sha256: str,
    history_manifest_sha256: str,
    source_commit: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or any(output_dir.iterdir()):
        raise ClinicalBaselineError("invalid_history_model_output")
    cohort, _ = _verify_cohort(cohort_dir, cohort_manifest_sha256)
    history_dir = history_dir.resolve()
    if not history_dir.is_relative_to(Path("/scratch/tliu7")) or history_dir.is_relative_to(ROOT):
        raise ClinicalBaselineError("invalid_history_artifact")
    manifest_path = history_dir / "manifest.json"
    if sha256(manifest_path) != history_manifest_sha256:
        raise ClinicalBaselineError("history_artifact_changed")
    history_manifest = json.loads(manifest_path.read_text())
    history_path = history_dir / "history.parquet"
    if (
        history_manifest.get("status") != "complete"
        or history_manifest.get("mode") != "dual_clock_history_extraction"
        or history_manifest.get("cohort_manifest_sha256") != cohort_manifest_sha256
        or history_manifest.get("availability_masked") is not True
        or history_manifest.get("outcome_features_used") is not False
        or history_manifest.get("artifacts_sha256", {}).get("history.parquet")
        != sha256(history_path)
    ):
        raise ClinicalBaselineError("invalid_history_artifact")
    history = pq.read_table(history_path)
    if history.schema != HISTORY_SCHEMA:
        raise ClinicalBaselineError("invalid_history_artifact")
    cohort_by_order = {row["order_id"]: row for row in cohort}
    grouped = {}
    for row in history.to_pylist():
        index = cohort_by_order.get(row["index_order_id"])
        if index is None:
            continue
        if index["patient_id"] != row["patient_id"]:
            raise ClinicalBaselineError("history_alignment")
        grouped.setdefault(row["index_order_id"], []).append(row)

    base_features = {
        mode: _history_features(grouped, cohort, config, mode)
        for mode in ("availability", "dual_clock")
    }
    models = {
        mode: fit_history_model(
            cohort,
            base_features[mode],
            config["bin_edges_hours"],
            config["ridge"],
            config["max_iterations"],
            config["tolerance"],
            mode,
        )
        for mode in ("availability", "dual_clock")
    }
    validation = [row for row in cohort if row["split"] == "validation"]
    if not validation:
        raise ClinicalBaselineError("empty_history_validation")
    if any(
        set(model["train_patients"]) & {row["patient_id"] for row in validation}
        for model in models.values()
    ):
        raise ClinicalBaselineError("history_patient_overlap")
    losses = {}
    metrics = {"data_class": "restricted_clinical", "split": "validation", "shifts": {}}
    for shift in config["delay_shifts_hours"]:
        shift_key = str(float(shift))
        shift_losses = {}
        for mode in ("availability", "dual_clock"):
            features = _history_features(grouped, cohort, config, mode, shift)
            matrix = np.stack([features[row["order_id"]] for row in validation])
            hazards = predict_hazards(models[mode], matrix)
            shift_losses[mode] = individual_nll(
                [row["duration"] for row in validation],
                [row["cause"] for row in validation],
                hazards,
                config["bin_edges_hours"],
            )
            losses[f"{mode}:{shift_key}"] = shift_losses[mode]
        losses[f"delta:{shift_key}"] = shift_losses["dual_clock"] - shift_losses["availability"]
    intervals = _bootstrap(validation, losses, config["bootstrap_replicates"], config["seed"])
    for shift in config["delay_shifts_hours"]:
        shift_key = str(float(shift))
        metrics["shifts"][shift_key] = {
            mode: {
                "nll_per_order": float(losses[f"{mode}:{shift_key}"].mean()),
                "nll_patient_bootstrap_95ci": intervals[f"{mode}:{shift_key}"],
            }
            for mode in ("availability", "dual_clock")
        }
        metrics["shifts"][shift_key]["dual_minus_availability"] = {
            "nll_per_order": float(losses[f"delta:{shift_key}"].mean()),
            "nll_patient_bootstrap_95ci": intervals[f"delta:{shift_key}"],
        }
    base = metrics["shifts"]["0.0"]["dual_minus_availability"]
    shift_deltas = [
        metrics["shifts"][str(float(shift))]["dual_minus_availability"]["nll_per_order"]
        for shift in config["delay_shifts_hours"][1:]
    ]
    decision = {
        "rule_frozen_before_test": True,
        "minimum_nll_improvement": config["minimum_nll_improvement"],
        "max_shift_nll_degradation": config["max_shift_nll_degradation"],
        "requires_paired_interval_below_zero": True,
        "advance_dual_clock": (
            base["nll_per_order"] <= -config["minimum_nll_improvement"]
            and base["nll_patient_bootstrap_95ci"][1] < 0
            and all(value <= config["max_shift_nll_degradation"] for value in shift_deltas)
        ),
        "test_split_evaluated": False,
    }
    predictions = [
        {
            "patient_id": row["patient_id"],
            "order_id": row["order_id"],
            "availability_nll": float(losses["availability:0.0"][index]),
            "dual_clock_nll": float(losses["dual_clock:0.0"][index]),
        }
        for index, row in enumerate(validation)
    ]
    artifacts = {
        "models.json": models,
        "validation_metrics.json": metrics,
        "validation_decision.json": decision,
        "validation_predictions.json": predictions,
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
        os.chmod(output_dir / name, 0o600)
    manifest = {
        "schema_version": 1,
        "mode": "clinical_matched_history_models",
        "data_class": "restricted_clinical",
        "status": "complete",
        "source_commit": source_commit,
        "cohort_manifest_sha256": cohort_manifest_sha256,
        "history_manifest_sha256": history_manifest_sha256,
        "config_sha256": config_sha256,
        "evaluation_split": "validation",
        "test_split_evaluated": False,
        "models": ["availability", "dual_clock"],
        "feature_dimension": 8,
        "delay_perturbation_refit": False,
        "database_write": False,
        "gpu_used": False,
        "artifacts_sha256": {name: sha256(output_dir / name) for name in artifacts},
    }
    write_json(output_dir / "manifest.json", manifest)
    os.chmod(output_dir / "manifest.json", 0o600)
    return manifest
