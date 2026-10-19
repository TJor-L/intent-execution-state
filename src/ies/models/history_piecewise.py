"""Matched fixed history encoders with convex competing-risk hazard heads."""

import math

import numpy as np

from ies.data.events import CAUSES
from ies.losses.competing_risks import exposure, validate_edges


def encode_history(
    rows: list[dict],
    mode: str,
    availability_scales: list[float],
    occurrence_scales: list[float],
    delay_shift_hours: float = 0.0,
) -> np.ndarray:
    if (
        mode not in {"availability", "dual_clock"}
        or not math.isfinite(delay_shift_hours)
        or delay_shift_hours < 0
    ):
        raise ValueError("Invalid history encoding")
    if mode == "availability":
        if len(availability_scales) != 4:
            raise ValueError("Availability encoder requires four scales")
        scales = availability_scales
    else:
        if len(availability_scales) != 2 or len(occurrence_scales) != 2:
            raise ValueError("Dual-clock encoder requires two scales per clock")
        scales = occurrence_scales + availability_scales
    if any(value <= 0 or not math.isfinite(value) for value in scales):
        raise ValueError("Invalid history scale")

    features = np.zeros(8, dtype=np.float64)
    for row in rows:
        kind = row["event_kind"]
        occurred = row["occurrence_lag_hours"]
        available = row["availability_lag_hours"] - delay_shift_hours
        if kind not in (0, 1) or not all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in (occurred, available)
        ):
            raise ValueError("Invalid history row")
        if occurred <= 0 or available < 0:
            continue
        offset = kind * 4
        if mode == "availability":
            values = [math.exp(-available / scale) for scale in availability_scales]
        else:
            values = [math.exp(-occurred / scale) for scale in occurrence_scales]
            values += [math.exp(-available / scale) for scale in availability_scales]
        features[offset : offset + 4] += values
    return features


def _objective(
    design: np.ndarray,
    exposures: np.ndarray,
    event_bins: np.ndarray,
    event_causes: np.ndarray,
    cause: int,
    parameters: np.ndarray,
    ridge: float,
) -> float:
    bins = exposures.shape[1]
    intercepts = parameters[:bins]
    coefficients = parameters[bins:]
    linear = np.clip(intercepts[None, :] + design @ coefficients[:, None], -30, 30)
    rates = np.exp(linear)
    value = float(np.sum(exposures * rates) + 0.5 * ridge * coefficients @ coefficients)
    selected = event_causes == cause
    if selected.any():
        value -= float(np.sum(linear[selected, event_bins[selected]]))
    return value


def fit_history_model(
    cohort: list[dict],
    features: dict[str, np.ndarray],
    edges: list[float],
    ridge: float,
    max_iterations: int,
    tolerance: float,
    mode: str,
    *,
    data_class: str = "restricted_clinical",
) -> dict:
    if data_class not in {"synthetic", "restricted_clinical"}:
        raise ValueError("Invalid history data class")
    training = [row for row in cohort if row["split"] == "train"]
    if not training or ridge <= 0 or max_iterations <= 0 or tolerance <= 0:
        raise ValueError("Invalid history model fit")
    edges_array = validate_edges(edges)
    raw = np.stack([features[row["order_id"]] for row in training])
    means = raw.mean(axis=0)
    scales = raw.std(axis=0)
    scales[scales < 1e-8] = 1.0
    design = (raw - means) / scales
    durations = np.asarray([row["duration"] for row in training], dtype=np.float64)
    causes = np.asarray([row["cause"] for row in training], dtype=np.int64)
    if not np.isin(causes, range(len(CAUSES) + 1)).all():
        raise ValueError("Unknown training cause")
    exposures = exposure(durations, edges_array)
    event_bins = np.searchsorted(edges_array[1:], durations, side="left")
    coefficients = []
    intercepts = []
    converged = []
    for cause in range(1, len(CAUSES) + 1):
        counts = np.bincount(event_bins[causes == cause], minlength=len(edges_array) - 1).astype(
            float
        )
        person_time = exposures.sum(axis=0)
        parameters = np.concatenate(
            [np.log((counts + 0.5) / (person_time + 1.0)), np.zeros(design.shape[1])]
        )
        previous = _objective(design, exposures, event_bins, causes, cause, parameters, ridge)
        did_converge = False
        for _ in range(max_iterations):
            bins = exposures.shape[1]
            alpha = parameters[:bins]
            beta = parameters[bins:]
            linear = np.clip(alpha[None, :] + design @ beta[:, None], -30, 30)
            weighted = exposures * np.exp(linear)
            selected = causes == cause
            gradient_alpha = weighted.sum(axis=0) - counts
            gradient_beta = np.sum(design[:, :, None] * weighted[:, None, :], axis=(0, 2))
            gradient_beta -= design[selected].sum(axis=0)
            gradient_beta += ridge * beta
            gradient = np.concatenate([gradient_alpha, gradient_beta])
            hessian = np.zeros((len(parameters), len(parameters)), dtype=np.float64)
            hessian[:bins, :bins] = np.diag(weighted.sum(axis=0))
            cross = np.einsum("ib,id->bd", weighted, design)
            hessian[:bins, bins:] = cross
            hessian[bins:, :bins] = cross.T
            hessian[bins:, bins:] = np.einsum(
                "ib,id,ie->de", weighted, design, design
            ) + ridge * np.eye(design.shape[1])
            hessian += 1e-8 * np.eye(len(parameters))
            step = np.linalg.solve(hessian, gradient)
            step_size = 1.0
            while step_size >= 2**-20:
                candidate = parameters - step_size * step
                objective = _objective(
                    design, exposures, event_bins, causes, cause, candidate, ridge
                )
                if math.isfinite(objective) and objective <= previous:
                    break
                step_size /= 2
            else:
                raise ValueError("History model optimization failed")
            parameters = candidate
            improvement = previous - objective
            previous = objective
            if improvement <= tolerance * max(1.0, abs(previous)):
                did_converge = True
                break
        if not did_converge:
            raise ValueError("History model did not converge")
        intercepts.append(parameters[: len(edges_array) - 1].tolist())
        coefficients.append(parameters[len(edges_array) - 1 :].tolist())
        converged.append(did_converge)
    return {
        "model": "history_piecewise_proportional_v1",
        "mode": mode,
        "data_class": data_class,
        "edges_hours": edges_array.tolist(),
        "causes": list(CAUSES),
        "feature_dimension": design.shape[1],
        "feature_mean": means.tolist(),
        "feature_scale": scales.tolist(),
        "intercepts_log_rate": intercepts,
        "coefficients": coefficients,
        "ridge": ridge,
        "optimization_converged": all(converged),
        "train_patients": sorted({row["patient_id"] for row in training}),
    }


def predict_hazards(model: dict, feature_matrix: np.ndarray) -> np.ndarray:
    if feature_matrix.ndim != 2 or feature_matrix.shape[1] != model["feature_dimension"]:
        raise ValueError("Invalid history feature matrix")
    design = (feature_matrix - np.asarray(model["feature_mean"])) / np.asarray(
        model["feature_scale"]
    )
    intercepts = np.asarray(model["intercepts_log_rate"], dtype=np.float64).T
    coefficients = np.asarray(model["coefficients"], dtype=np.float64).T
    linear = intercepts[None, :, :] + np.einsum("nd,dk->nk", design, coefficients)[:, None, :]
    hazards = np.exp(np.clip(linear, -30, 30))
    if not np.isfinite(hazards).all() or (hazards <= 0).any():
        raise ValueError("Invalid predicted hazards")
    return hazards


def individual_nll(durations, causes, hazards: np.ndarray, edges: list[float]) -> np.ndarray:
    edges_array = validate_edges(edges)
    durations = np.asarray(durations, dtype=np.float64)
    causes = np.asarray(causes, dtype=np.int64)
    if (
        hazards.shape != (len(durations), len(edges_array) - 1, len(CAUSES))
        or not np.isfinite(hazards).all()
        or (hazards <= 0).any()
        or not np.isin(causes, range(len(CAUSES) + 1)).all()
    ):
        raise ValueError("Invalid individual hazards")
    losses = np.sum(exposure(durations, edges_array) * hazards.sum(axis=2), axis=1)
    selected = causes > 0
    bins = np.searchsorted(edges_array[1:], durations, side="left")
    losses[selected] -= np.log(
        hazards[np.flatnonzero(selected), bins[selected], causes[selected] - 1]
    )
    if not np.isfinite(losses).all():
        raise ValueError("Non-finite history likelihood")
    return losses
