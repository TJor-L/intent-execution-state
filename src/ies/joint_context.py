"""Strong finite sequential context references; no novel algorithm is claimed."""

from functools import lru_cache

import numpy as np

from ies.joint_observation import (
    HORIZON,
    STATES,
    PrefixCounts,
    _probability,
    observed_nll,
    projection,
)
from ies.joint_shrinkage import prefix_counts, split_counts


@lru_cache(maxsize=27)
def _layout(time: int, memory: int, entities: tuple[int, ...]):
    selected = STATES[:, list(entities)]
    context = [
        tuple((row[:, :time] != 2).all(axis=1))
        + tuple(row[:, max(0, time - memory) : time].ravel())
        for row in selected
    ]
    outcome = [tuple(row[:, time]) for row in selected]
    keys = sorted(set(zip(context, outcome, strict=True)))
    labels = {key: i for i, key in enumerate(keys)}
    parents = {key: i for i, key in enumerate(sorted(set(context)))}
    cell = np.asarray([labels[key] for key in zip(context, outcome, strict=True)], dtype=int)
    parent = np.asarray([parents[key[0]] for key in keys], dtype=int)
    outcomes_per_parent = np.bincount(parent)
    reps = np.unique(projection(time + 1), return_index=True)[1]
    return cell, parent, outcomes_per_parent, reps


def _observed_levels(observed):
    observed.validate()
    return [prefix_counts(observed, depth) for depth in range(1, HORIZON + 1)]


def _fit(levels, scope, memory, strength):
    probability = np.ones(len(STATES))
    dimension = 0
    groups = ((0,), (1,)) if scope == "independent" else ((0, 1),)
    for time, counts in enumerate(levels):
        for entities in groups:
            cell, parent, sizes, representatives = _layout(time, memory, entities)
            frequencies = np.bincount(cell[representatives], weights=counts, minlength=len(parent))
            totals = np.bincount(parent, weights=frequencies)
            conditional = (frequencies + strength / sizes[parent]) / (totals[parent] + strength)
            probability *= conditional[cell]
            dimension += int(np.sum(sizes - 1))
    return _probability(probability, len(STATES)), dict(
        scope=scope,
        memory_bins=memory,
        prior_strength=strength,
        nominal_transition_dimension=dimension,
        observed_patients_by_transition=[int(counts.sum()) for counts in levels],
    )


def fit_context(observed: PrefixCounts, scope: str, memory: int, strength: float):
    if (
        scope not in {"independent", "joint"}
        or type(memory) is not int
        or memory not in (0, 1, 2)
        or not np.isfinite(strength)
        or not 0 < strength <= 1000
    ):
        raise ValueError("Invalid generated context model")
    return _fit(_observed_levels(observed), scope, memory, strength)


def select_contexts(observed: PrefixCounts, seed: int):
    """Select independent, joint and unrestricted families on the same two folds."""
    left, right = split_counts(observed, seed)
    levels = [_observed_levels(left), _observed_levels(right)]
    candidates = []
    for scope in ("independent", "joint"):
        for memory in (0, 1, 2):
            for strength in (1.0, 10.0, 100.0):
                losses = [
                    observed_nll(_fit(data, scope, memory, strength)[0], validation)
                    for data, validation in zip(levels, (right, left), strict=True)
                ]
                loss = (right.patients * losses[0] + left.patients * losses[1]) / observed.patients
                candidates.append(dict(scope=scope, memory=memory, strength=strength, cv_nll=loss))
    full = _observed_levels(observed)
    predictions, diagnostics = {}, {}
    for name, scope in (
        ("context_independent_cv", "independent"),
        ("context_joint_cv", "joint"),
        ("context_all_cv", None),
    ):
        choices = [c for c in candidates if scope is None or c["scope"] == scope]
        selected = min(choices, key=lambda c: c["cv_nll"])
        predictions[name], fit = _fit(
            full, selected["scope"], selected["memory"], selected["strength"]
        )
        diagnostics[name] = dict(
            selection="two_fold_observed_prefix_nll",
            selected=selected,
            candidates=choices,
            fold_patients=[left.patients, right.patients],
            final_fit=fit,
        )
    return predictions, diagnostics
