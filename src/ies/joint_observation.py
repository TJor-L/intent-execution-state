"""Finite generated recurrent-path laboratory; reference estimators, not a novel model.

There are two anonymous linked entities and three abstract future bins. An entity
can recur repeatedly, or terminate once. Observation ends jointly for both entities.
All possible paths are enumerated, making likelihoods and population risks exact.
This module has no clinical reader, clock adapter, covariates or extraction policy.
"""

from dataclasses import dataclass
from itertools import product

import numpy as np

HORIZON = 3
# 0: observed no recurrence, 1: recurrence, 2: terminal, 3: post-terminal padding.
LAWS = ("independent", "synchronized", "opposed")
WINDOWS = {
    "full": (0.0, 0.0, 0.0, 1.0),
    "independent_short": (0.0, 0.5, 0.3, 0.2),
    "no_tail_support": (0.0, 0.5, 0.5, 0.0),
}


def entity_paths() -> np.ndarray:
    paths = []
    for row in product(range(3), repeat=HORIZON):
        if 2 in row:
            end = row.index(2)
            row = row[: end + 1] + (3,) * (HORIZON - end - 1)
        if row not in paths:
            paths.append(row)
    return np.asarray(paths, dtype=int)


PATHS = entity_paths()
PAIRS = np.asarray(list(product(range(len(PATHS)), repeat=2)), dtype=int)
STATES = PATHS[PAIRS]


def _probability(value, size):
    value = np.asarray(value, dtype=float)
    if (
        value.shape != (size,)
        or not np.isfinite(value).all()
        or np.any(value < 0)
        or not np.isclose(value.sum(), 1, rtol=0, atol=1e-10)
    ):
        raise ValueError("Invalid finite generated distribution")
    return value


def entity_law(rate: float) -> np.ndarray:
    if not np.isfinite(rate) or not 0 < rate < 0.9:
        raise ValueError("Invalid generated recurrence probability")
    step = np.asarray([0.92 - rate, rate, 0.08, 1.0])
    return _probability(np.prod(step[PATHS], axis=1), len(PATHS))


def joint_law(name: str) -> np.ndarray:
    """All three laws have exactly the same marginal entity-path distributions."""
    if name not in LAWS:
        raise ValueError("Unknown generated joint mechanism")
    low, high = entity_law(0.08), entity_law(0.50)
    if name == "independent":
        mean = (low + high) / 2
        value = np.outer(mean, mean)
    elif name == "synchronized":
        value = (np.outer(low, low) + np.outer(high, high)) / 2
    else:
        value = (np.outer(low, high) + np.outer(high, low)) / 2
    return _probability(value.ravel(), len(STATES))


def projection(window: int, entity: int | None = None) -> np.ndarray:
    """Map latent states to observed-prefix equivalence classes, not padded outcomes."""
    if type(window) is not int or not 0 <= window <= HORIZON or entity not in {None, 0, 1}:
        raise ValueError("Invalid generated observation projection")
    values = STATES if entity is None else STATES[:, entity : entity + 1]
    keys = [tuple(row[:, :window].ravel()) for row in values]
    labels = {key: i for i, key in enumerate(sorted(set(keys)))}
    return np.asarray([labels[key] for key in keys], dtype=int)


@dataclass(frozen=True)
class PrefixCounts:
    """Sufficient observed statistics; latent training states cannot enter fitting."""

    counts: tuple[np.ndarray, ...]

    def validate(self):
        if len(self.counts) != HORIZON + 1:
            raise ValueError("Invalid generated observation count")
        for window, count in enumerate(self.counts):
            count = np.asarray(count)
            if (
                count.shape != (int(projection(window).max()) + 1,)
                or count.dtype.kind not in "iu"
                or np.any(count < 0)
            ):
                raise ValueError("Invalid generated prefix statistics")
        if not 1 <= self.patients <= 100_000:
            raise ValueError("Invalid generated patient bound")

    @property
    def patients(self):
        return sum(int(count.sum()) for count in self.counts)


def sample_observed(law, window_law, patients: int, seed: int) -> PrefixCounts:
    law = _probability(law, len(STATES))
    windows = _probability(window_law, HORIZON + 1)
    if type(patients) is not int or not 1 <= patients <= 100_000:
        raise ValueError("Invalid generated patient bound")
    # Separate RNGs keep the latent sample fixed when only observation policy changes.
    latent = np.random.default_rng(seed).choice(len(STATES), patients, p=law)
    stops = np.random.default_rng(seed + 1_000_003).choice(HORIZON + 1, patients, p=windows)
    counts = []
    for window in range(HORIZON + 1):
        index = projection(window)
        counts.append(np.bincount(index[latent[stops == window]], minlength=index.max() + 1))
    result = PrefixCounts(tuple(counts))
    result.validate()
    return result


def observed_nll(probability, observed: PrefixCounts) -> float:
    probability = _probability(probability, len(STATES))
    observed.validate()
    loss = 0.0
    for window, count in enumerate(observed.counts):
        marginal = np.bincount(projection(window), weights=probability)
        selected = count > 0
        loss -= float(count[selected] @ np.log(np.maximum(marginal[selected], 1e-300)))
    return loss / observed.patients


def fit_joint(observed: PrefixCounts, steps: int = 300, prior_mass: float = 1.0):
    """Standard incomplete-multinomial EM with a symmetric Dirichlet MAP penalty.

    No new algorithm is claimed. Uniform initialization only chooses an extrapolation
    when a tail is unidentified; it does not make that tail identifiable.
    """
    observed.validate()
    if type(steps) is not int or not 1 <= steps <= 1000 or not 0 < prior_mass <= 100:
        raise ValueError("Invalid finite fit resource bound")
    p = np.full(len(STATES), 1 / len(STATES))
    maps = [projection(c) for c in range(HORIZON + 1)]
    for _ in range(steps):
        expected = np.full(len(STATES), prior_mass / len(STATES))
        for index, counts in zip(maps, observed.counts, strict=True):
            total = np.bincount(index, weights=p)
            expected += p * (counts / np.maximum(total, 1e-300))[index]
        updated = expected / expected.sum()
        if np.max(np.abs(updated - p)) < 1e-10:
            p = updated
            break
        p = updated
    return p


def fit_independent(observed: PrefixCounts, steps: int = 300):
    """Two saturated per-entity path models fitted to the same observed prefixes."""
    observed.validate()
    if type(steps) is not int or not 1 <= steps <= 1000:
        raise ValueError("Invalid finite fit resource bound")
    marginals = []
    for entity in range(2):
        p = np.full(len(PATHS), 1 / len(PATHS))
        maps, counts = [], []
        for window, joint_count in enumerate(observed.counts):
            joint_index, entity_index = projection(window), projection(window, entity)
            # Each joint observed cell maps to one entity cell; no hidden tail read.
            representatives = np.unique(joint_index, return_index=True)[1]
            count = np.bincount(entity_index[representatives], weights=joint_count)
            maps.append(
                entity_index[
                    np.arange(len(PATHS)) * len(PATHS) if entity == 0 else np.arange(len(PATHS))
                ]
            )
            counts.append(count)
        for _ in range(steps):
            expected = np.full(len(PATHS), 1 / len(PATHS))
            for index, count in zip(maps, counts, strict=True):
                marginal = np.bincount(index, weights=p)
                expected += p * (count / np.maximum(marginal, 1e-300))[index]
            p = expected / expected.sum()
        marginals.append(p)
    return np.outer(*marginals).ravel()


def fit_mixture(observed: PrefixCounts, seed: int, steps: int = 300):
    """Standard two-class product-multinomial missing-data EM, two fixed restarts.

    A strong low-dimensional reference when dependence is a shared latent class.
    It is not a new neural method and does not identify unsupported tails.
    """
    observed.validate()
    if type(steps) is not int or not 1 <= steps <= 1000:
        raise ValueError("Invalid finite fit resource bound")
    rng = np.random.default_rng(seed)
    maps = [projection(c) for c in range(HORIZON + 1)]
    candidates = []
    for _ in range(2):
        weights = np.full(2, 0.5)
        factors = rng.dirichlet(np.ones(len(PATHS)), size=(2, 2))
        for _ in range(steps):
            component = weights[:, None] * np.asarray([np.outer(a, b).ravel() for a, b in factors])
            expected = np.zeros_like(component)
            for index, count in zip(maps, observed.counts, strict=True):
                total = np.bincount(index, weights=component.sum(axis=0))
                expected += component * (count / np.maximum(total, 1e-300))[index]
            weights = expected.sum(axis=1) + 0.5
            weights /= weights.sum()
            cube = expected.reshape(2, len(PATHS), len(PATHS))
            factors = np.stack([cube.sum(axis=2), cube.sum(axis=1)], axis=1) + 1 / len(PATHS)
            factors /= factors.sum(axis=2, keepdims=True)
        p = sum(w * np.outer(a, b).ravel() for w, (a, b) in zip(weights, factors, strict=True))
        # Select only on observed training loss, never latent evaluation risk.
        candidates.append((observed_nll(p, observed), p))
    return min(candidates, key=lambda item: item[0])[1]


def fit_zero_filled(observed: PrefixCounts):
    """Deliberately invalid control: impute an unobserved future as no events."""
    observed.validate()
    count = np.full(len(STATES), 1 / len(STATES))
    lookup = {tuple(state.ravel()): i for i, state in enumerate(STATES)}
    for window, values in enumerate(observed.counts):
        index = projection(window)
        for cell, representative in enumerate(np.unique(index, return_index=True)[1]):
            state = STATES[representative].copy()
            for entity in range(2):
                state[entity, window:] = 3 if 2 in state[entity, :window] else 0
            count[lookup[tuple(state.ravel())]] += values[cell]
    return count / count.sum()


def population_scores(prediction, truth, windows):
    """Exact simulator population scores; no Monte Carlo evaluation or clinical claim."""
    prediction = _probability(prediction, len(STATES))
    truth = _probability(truth, len(STATES))
    windows = _probability(windows, HORIZON + 1)
    kl = float(truth @ np.log(np.maximum(truth, 1e-300) / np.maximum(prediction, 1e-300)))
    observed_kl = 0.0
    for window, weight in enumerate(windows):
        index = projection(window)
        p = np.bincount(index, weights=prediction)
        q = np.bincount(index, weights=truth)
        observed_kl += weight * float(q @ np.log(np.maximum(q, 1e-300) / np.maximum(p, 1e-300)))
    counts = (STATES == 1).sum(axis=2)
    both_repeat = np.all(counts >= 2, axis=1)
    return dict(
        latent_joint_kl=kl,
        observed_prefix_kl=observed_kl,
        both_repeat_probability=float(prediction @ both_repeat),
        both_repeat_probability_error=float((prediction - truth) @ both_repeat),
        marginal_count_mean_squared_error=float(np.mean(((prediction - truth) @ counts) ** 2)),
    )


def nonidentifiability_witness():
    """Two laws identical through bin 2, with different joint recurrence in bin 3."""
    lookup = {tuple(state.ravel()): i for i, state in enumerate(STATES)}
    p = np.zeros(len(STATES))
    q = p.copy()
    for a, b in ((0, 0), (1, 1)):
        p[lookup[(0, 0, a, 0, 0, b)]] = 0.5
    for a, b in ((0, 1), (1, 0)):
        q[lookup[(0, 0, a, 0, 0, b)]] = 0.5
    observed_differences = [
        float(np.abs(np.bincount(projection(c), weights=p - q)).sum()) for c in range(HORIZON + 1)
    ]
    both = np.all(STATES[:, :, -1] == 1, axis=1)
    return dict(
        prefix_l1_differences=observed_differences,
        final_bin_both_recur_probabilities=[float(p @ both), float(q @ both)],
        conclusion="Joint tail is not identified when every observation ends before bin 3.",
    )
