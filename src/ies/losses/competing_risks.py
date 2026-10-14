"""Piecewise exponential competing-risk log likelihood, including censoring."""

import numpy as np


def validate_edges(edges) -> np.ndarray:
    edges = np.asarray(edges, dtype=float)
    if edges.ndim != 1 or len(edges) < 2 or edges[0] != 0:
        raise ValueError("Bin edges must be a vector starting at zero")
    if not np.isfinite(edges).all() or not (np.diff(edges) > 0).all():
        raise ValueError("Bin edges must be finite and strictly increasing")
    return edges


def exposure(duration, edges) -> np.ndarray:
    edges = validate_edges(edges)
    duration = np.asarray(duration, dtype=float)
    if duration.ndim != 1 or not np.isfinite(duration).all():
        raise ValueError("Duration must be a finite vector")
    if not ((duration > 0) & (duration <= edges[-1])).all():
        raise ValueError("Duration must lie in (0, model horizon]")
    return np.clip(duration[:, None] - edges[:-1], 0, np.diff(edges))


def negative_log_likelihood(duration, cause, hazards, edges) -> np.ndarray:
    durations = np.asarray(duration, dtype=float)
    causes = np.asarray(cause)
    hazards = np.asarray(hazards, dtype=float)
    edges = validate_edges(edges)
    if hazards.ndim != 2 or hazards.shape[0] != len(edges) - 1 or hazards.shape[1] < 1:
        raise ValueError("Expected bins × causes hazard matrix")
    if not np.isfinite(hazards).all() or not (hazards > 0).all():
        raise ValueError("Hazards must be finite and strictly positive")
    if causes.shape != durations.shape or not np.isin(causes, range(hazards.shape[1] + 1)).all():
        raise ValueError("Invalid competing-risk causes")
    causes = causes.astype(int)
    losses = exposure(durations, edges) @ hazards.sum(axis=1)
    observed = causes > 0
    # Intervals are (left, right]; an event exactly on an edge belongs to the prior bin.
    bins = np.searchsorted(edges[1:], durations, side="left")
    losses[observed] -= np.log(hazards[bins[observed], causes[observed] - 1])
    return losses
