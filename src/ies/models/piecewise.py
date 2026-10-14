"""Intercept-only piecewise exponential baseline with Gamma smoothing."""

import numpy as np

from ies.data.events import CAUSES
from ies.losses.competing_risks import exposure, negative_log_likelihood, validate_edges


def fit_baseline(cohort: list[dict], edges: list[float]) -> dict:
    training = [r for r in cohort if r["split"] == "train"]
    if not training:
        raise ValueError("No training patients")
    edges_array = validate_edges(edges)
    durations = np.asarray([r["duration"] for r in training])
    causes = np.asarray([r["cause"] for r in training])
    if not np.isin(causes, range(len(CAUSES) + 1)).all():
        raise ValueError("Unknown training cause")
    person_time = exposure(durations, edges_array).sum(axis=0)
    counts = np.zeros((len(edges_array) - 1, len(CAUSES)))
    bins = np.searchsorted(edges_array[1:], durations, side="left")
    for index, cause in zip(bins, causes, strict=True):
        if cause > 0:
            counts[index, int(cause) - 1] += 1
    # Posterior mean under independent Gamma(shape=.5, rate=1 hour) priors.
    hazards = (counts + 0.5) / (person_time[:, None] + 1.0)
    return {
        "model": "piecewise_exponential_intercept_v1",
        "data_class": "synthetic",
        "edges_hours": list(edges_array),
        "causes": list(CAUSES),
        "hazards_per_hour": hazards.tolist(),
        "prior_shape": 0.5,
        "prior_rate_hours": 1.0,
        "train_patients": sorted({r["patient_id"] for r in training}),
        "n_train_orders": len(training),
    }


def cumulative_incidence(model: dict) -> dict:
    hazards = np.asarray(model["hazards_per_hour"])
    edges = validate_edges(model["edges_hours"])
    # Reuse likelihood validation for malformed or non-finite model files.
    negative_log_likelihood([edges[-1]], [0], hazards, edges)
    survival = 1.0
    incidence = np.zeros(hazards.shape[1])
    rows = []
    for width, rates in zip(np.diff(edges), hazards, strict=True):
        total = rates.sum()
        mass = -np.expm1(-total * width)
        incidence = incidence + survival * mass * rates / total
        survival *= np.exp(-total * width)
        rows.append({"survival": float(survival), "cif": incidence.tolist()})
    return {"times_hours": list(edges[1:]), "causes": model["causes"], "curve": rows}
