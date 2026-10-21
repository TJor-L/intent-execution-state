"""Experimental prefix-aware interaction shrinkage in the finite J001 laboratory.

Weighted tree contrasts and block shrinkage are established ingredients. This is a
candidate adaptation to shared prefix observations, not a novelty or optimality claim.
Only generated observed-prefix counts enter fitting; no clinical adapter is provided.
"""

import numpy as np

from ies.joint_observation import (
    HORIZON,
    PAIRS,
    PATHS,
    STATES,
    PrefixCounts,
    _probability,
    observed_nll,
    projection,
)


def combine_counts(a: PrefixCounts, b: PrefixCounts):
    a.validate()
    b.validate()
    result = PrefixCounts(tuple(x + y for x, y in zip(a.counts, b.counts, strict=True)))
    result.validate()
    return result


def split_counts(observed: PrefixCounts, seed: int):
    """Independent Bernoulli assignment of patients, represented as cell counts."""
    observed.validate()
    rng = np.random.default_rng(seed)
    left = PrefixCounts(tuple(rng.binomial(count, 0.5) for count in observed.counts))
    right = PrefixCounts(tuple(x - y for x, y in zip(observed.counts, left.counts, strict=True)))
    left.validate()
    right.validate()
    return left, right


def prefix_counts(observed: PrefixCounts, depth: int):
    """Only subjects observed THROUGH depth contribute; unknown tails are excluded."""
    observed.validate()
    if type(depth) is not int or not 0 <= depth <= HORIZON:
        raise ValueError("Invalid generated prefix depth")
    target = projection(depth)
    result = np.zeros(int(target.max()) + 1)
    for window in range(depth, HORIZON + 1):
        representatives = np.unique(projection(window), return_index=True)[1]
        result += np.bincount(
            target[representatives], weights=observed.counts[window], minlength=len(result)
        )
    return result


def tree_basis(marginal):
    """Weighted orthonormal martingale contrasts, grouped by first revealing bin.

    Each contrast has zero conditional mean before its reveal depth under the supplied
    marginal. This is weighted Gram–Schmidt on nested prefix partitions, not a new basis.
    """
    marginal = _probability(marginal, len(PATHS))
    if np.any(marginal <= 0):
        raise ValueError("Strictly positive reference marginals required")
    basis, depths = [], []
    for depth in range(1, HORIZON + 1):
        parents = sorted({tuple(row[: depth - 1]) for row in PATHS})
        for parent in parents:
            member = np.array([tuple(row[: depth - 1]) == parent for row in PATHS])
            children = sorted(set(PATHS[member, depth - 1]))
            local = []
            for child in children[:-1]:
                indicator = member & (PATHS[:, depth - 1] == child)
                value = indicator.astype(float) - member * (marginal @ indicator) / (
                    marginal @ member
                )
                for previous in local:
                    value -= previous * np.sum(marginal * value * previous)
                norm = np.sqrt(np.sum(marginal * value**2))
                if norm < 1e-12:
                    raise ValueError("Degenerate generated contrast")
                local.append(value / norm)
            basis.extend(local)
            depths.extend([depth] * len(local))
    return np.column_stack(basis), np.asarray(depths, dtype=int)


def spectral_fit(observed: PrefixCounts, baseline, grouping: str):
    """Learn marginal-preserving interactions with observation-depth block shrinkage.

    A disjoint pilot supplies baseline marginals. Empirical covariance centers remove
    the product-of-mean artifact when pilot marginals differ from population marginals.
    Plug-in variance/shrinkage is heuristic, not a finite-sample risk guarantee. Selection
    of complete prefixes assumes observation independent of paths. Adaptively stopped
    data are a deliberately adverse stress case, not covered by that assumption.
    """
    observed.validate()
    baseline = _probability(baseline, len(STATES)).reshape(len(PATHS), len(PATHS))
    a, b = baseline.sum(axis=1), baseline.sum(axis=0)
    if not np.allclose(baseline, np.outer(a, b), atol=1e-12, rtol=0):
        raise ValueError("Factorized generated reference required")
    if grouping not in {"global", "reveal", "none"}:
        raise ValueError("Invalid generated shrinkage grouping")
    u, du = tree_basis(a)
    v, dv = tree_basis(b)
    reveal = np.maximum(du[:, None], dv[None, :])
    estimates = np.zeros_like(reveal, dtype=float)
    variances = np.zeros_like(estimates)
    support = []
    for depth in range(1, HORIZON + 1):
        counts = prefix_counts(observed, depth)
        n = float(counts.sum())
        support.append(int(n))
        if n < 3:
            continue
        reps = np.unique(projection(depth), return_index=True)[1]
        x, y = u[PAIRS[reps, 0]].copy(), v[PAIRS[reps, 1]].copy()
        # Never evaluate unavailable contrasts using an arbitrary tail representative.
        x[:, du > depth] = 0
        y[:, dv > depth] = 0
        weights = counts / n
        x -= weights @ x
        y -= weights @ y
        products = x[:, :, None] * y[:, None, :]
        mean = np.einsum("n,nij->ij", weights, products)
        variance = np.einsum("n,nij->ij", weights, (products - mean) ** 2) / (n - 1)
        mask = reveal == depth
        estimates[mask] = mean[mask] * n / (n - 1)
        variances[mask] = variance[mask]
    factors = {}
    group_ids = [0] if grouping in {"none", "global"} else list(range(1, HORIZON + 1))
    for group in group_ids:
        selected = np.ones_like(reveal, dtype=bool) if group == 0 else reveal == group
        energy = float(np.sum(estimates[selected] ** 2))
        noise = float(np.sum(variances[selected]))
        factor = 1.0 if grouping == "none" else max(0.0, 1 - noise / max(energy, 1e-300))
        estimates[selected] *= factor
        factors[str(group)] = factor
    interaction = u @ estimates @ v.T
    minimum = float(interaction.min())
    # A single contraction preserves zero marginal contrasts and unsupported blocks.
    contraction = min(1.0, 0.99 / -minimum) if minimum < 0 else 1.0
    probability = baseline * (1 + contraction * interaction)
    error = max(
        np.max(np.abs(probability.sum(axis=1) - a)), np.max(np.abs(probability.sum(axis=0) - b))
    )
    if error > 1e-9 or np.any(probability <= 0):
        raise ValueError("Generated marginal/positivity constraint failed")
    return _probability(probability.ravel(), len(STATES)), dict(
        observed_patients_by_reveal_depth=support,
        block_factors=factors,
        positivity_contraction=contraction,
        maximum_marginal_error=float(error),
        retained_coefficient_energy=float(np.sum((contraction * estimates) ** 2)),
        unsupported_coefficients_nonzero=int(
            np.count_nonzero(
                estimates[reveal > max((i + 1 for i, n in enumerate(support) if n >= 3), default=0)]
            )
        ),
    )


def tree_shrink_fit(observed: PrefixCounts, baseline, strength: float):
    """Standard Dirichlet-tree posterior prediction centered on a fixed path law."""
    observed.validate()
    baseline = _probability(baseline, len(STATES))
    if np.any(baseline <= 0) or not np.isfinite(strength) or not 0 < strength <= 1000:
        raise ValueError("Invalid generated tree prior")
    result = np.ones(len(STATES))
    for depth in range(1, HORIZON + 1):
        child, parent = projection(depth), projection(depth - 1)
        representatives = np.unique(child, return_index=True)[1]
        parent_of_child = parent[representatives]
        counts = prefix_counts(observed, depth)
        parent_counts = np.bincount(parent_of_child, weights=counts)
        child_mass = np.bincount(child, weights=baseline)
        parent_mass = np.bincount(parent, weights=baseline)
        prior = child_mass / parent_mass[parent_of_child]
        conditional = (counts + strength * prior) / (parent_counts[parent_of_child] + strength)
        result *= conditional[child]
    return _probability(result, len(STATES))


def select_tree_shrinkage(observed: PrefixCounts, baseline, seed: int):
    """Fixed two-fold observed-likelihood CV; no latent risk is available here."""
    left, right = split_counts(observed, seed)
    candidates = []
    for strength in (1.0, 10.0, 100.0):
        fold_predictions = [
            tree_shrink_fit(left, baseline, strength),
            tree_shrink_fit(right, baseline, strength),
        ]
        for weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            loss = (
                sum(
                    observed_nll((1 - weight) * baseline + weight * p, validation)
                    * validation.patients
                    for p, validation in zip(fold_predictions, (right, left), strict=True)
                )
                / observed.patients
            )
            candidates.append((loss, strength, weight))
    _, strength, weight = min(candidates)
    joint = tree_shrink_fit(observed, baseline, strength)
    return (1 - weight) * baseline + weight * joint, dict(
        selected_strength=strength,
        selected_joint_weight=weight,
        selection="two_fold_observed_prefix_nll",
        candidates=len(candidates),
    )
