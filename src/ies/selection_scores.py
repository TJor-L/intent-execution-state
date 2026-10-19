"""Finite-sample, coherent multi-horizon completion bounds; not population CIs.

Each censored order has at most one first-execution transition, shared by all models
and horizons. No imputation or censoring independence assumption is used for bounds.
"""

import numpy as np

from ies.losses.competing_risks import exposure
from ies.workflow_diagnostics import execution_targets


def patient_weights(patients):
    _, inverse, counts = np.unique(patients, return_inverse=True, return_counts=True)
    if not len(counts):
        raise ValueError("Empty patient weights")
    return 1 / (len(counts) * counts[inverse])


def coherent_rows(predictions, durations, causes, horizons, weights, comparator=None):
    """Return n x 2 sharp bounds over admissible binary horizon trajectories per order."""
    predictions = np.asarray(predictions, dtype=float)
    horizons, weights = np.asarray(horizons, float), np.asarray(weights, float)
    durations, causes = np.asarray(durations, float), np.asarray(causes)
    if (
        horizons.ndim != 1
        or not len(horizons)
        or not np.isfinite(horizons).all()
        or (np.diff(horizons) <= 0).any()
        or weights.shape != horizons.shape
        or not np.isfinite(weights).all()
        or (weights < 0).any()
        or not np.isclose(weights.sum(), 1)
        or predictions.shape != (len(durations), len(horizons))
        or not np.isfinite(predictions).all()
        or not ((predictions >= 0) & (predictions <= 1)).all()
        or (np.diff(predictions, axis=1) < -1e-12).any()
    ):
        raise ValueError("Invalid coherent scoring inputs")
    targets, unknowns = zip(
        *(execution_targets(durations, causes, h) for h in horizons), strict=True
    )
    targets, unknown = np.stack(targets, axis=1), np.stack(unknowns, axis=1)
    # Pattern j means first execution after horizon j-1 and by j; H means none by H.
    patterns = np.arange(len(horizons))[None, :] >= np.arange(len(horizons) + 1)[:, None]
    admissible = np.all(unknown[:, None, :] | (targets[:, None, :] == patterns[None]), axis=2)
    errors = (predictions[:, None, :] - patterns[None]) ** 2
    if comparator is not None:
        comparator = np.asarray(comparator, dtype=float)
        if (
            comparator.shape != predictions.shape
            or not np.isfinite(comparator).all()
            or not ((comparator >= 0) & (comparator <= 1)).all()
            or (np.diff(comparator, axis=1) < -1e-12).any()
        ):
            raise ValueError("Invalid comparator probabilities")
        errors -= (comparator[:, None, :] - patterns[None]) ** 2
    scores = errors @ weights
    result = np.stack(
        [
            np.where(admissible, scores, np.inf).min(axis=1),
            np.where(admissible, scores, -np.inf).max(axis=1),
        ],
        axis=1,
    )
    if not np.isfinite(result).all():
        raise ValueError("No admissible completion")
    return result


def cause_losses(durations, causes, hazards, edges):
    """Observed likelihood components; decomposition is descriptive, not causal."""
    hazards = np.asarray(hazards, float)
    causes = np.asarray(causes)
    if (
        hazards.shape != (len(durations), len(edges) - 1, 3)
        or not np.isfinite(hazards).all()
        or (hazards <= 0).any()
        or not np.issubdtype(causes.dtype, np.integer)
        or not np.isin(causes, [0, 1, 2, 3]).all()
    ):
        raise ValueError("Invalid likelihood decomposition")
    losses = np.sum(exposure(durations, edges)[:, :, None] * hazards, axis=1)
    selected = np.flatnonzero(causes > 0)
    bins = np.searchsorted(np.asarray(edges)[1:], np.asarray(durations), side="left")
    losses[selected, causes[selected] - 1] -= np.log(
        hazards[selected, bins[selected], causes[selected] - 1]
    )
    return losses


def conditional_endpoint_percentiles(patients, bounds, replicates, seed):
    """Patient-average endpoint bootstrap, conditional on overlapping fitted CV models."""
    _, inverse, counts = np.unique(patients, return_inverse=True, return_counts=True)
    means = np.stack([np.bincount(inverse, weights=bounds[:, j]) / counts for j in (0, 1)], axis=1)
    rng = np.random.default_rng(seed)
    samples = np.array(
        [means[rng.integers(len(counts), size=len(counts))].mean(axis=0) for _ in range(replicates)]
    )
    return dict(
        lower_endpoint=np.quantile(samples[:, 0], [0.025, 0.975]).tolist(),
        upper_endpoint=np.quantile(samples[:, 1], [0.025, 0.975]).tolist(),
        interpretation="Conditional endpoint percentiles, not full-pipeline population intervals.",
    )
