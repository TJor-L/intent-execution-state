"""Exact factored filtering for the known unsigned count model, generated only.

Terminal binomial thinning, polynomial recurrence and sum-product contraction are
known primitives. This specialized factorization does not establish method novelty.
The full initial roster and its histories must be known; hidden outcomes stay hidden.
"""

from functools import lru_cache
from math import comb

import numpy as np

from ies.hidden_history import compositions, validate_model
from ies.history_roles import validate_path

MAX_MISSING = 24


@lru_cache(maxsize=3)
def count_plan(missing):
    if type(missing) is not int or not 0 <= missing <= MAX_MISSING:
        raise ValueError("Invalid bounded generated factored missing roster")
    layers = [np.array(list(compositions(n, 4)), dtype=int) for n in range(missing + 1)]
    counts = np.concatenate(layers)
    states = np.column_stack([counts, missing - counts.sum(axis=1)])
    shape = (missing + 1,) * 4
    # Each layer's predecessor lookup refers only to the immediately smaller layer.
    lookup = np.zeros(shape, dtype=int)
    parents, categories = [None], [None]
    for n, layer in enumerate(layers):
        if n:
            category = np.argmax(layer > 0, axis=1)
            predecessor = layer.copy()
            predecessor[np.arange(len(layer)), category] -= 1
            parents.append(lookup[tuple(predecessor.T)].copy())
            categories.append(category)
        lookup[tuple(layer.T)] = np.arange(len(layer))
    for value in [states, counts, *layers, *parents[1:], *categories[1:]]:
        value.setflags(write=False)
    return dict(
        states=states,
        counts=counts,
        layers=tuple(layers),
        parents=tuple(parents),
        categories=tuple(categories),
        shape=shape,
        histogram_states=comb(missing + 4, 4),
        sparse_transition_terms=comb(missing + 12, 12),
    )


def binomial_table(size, probability):
    """Column n is the normalized Binomial(n,p) distribution, rows 0..size."""
    if (
        type(size) is not int
        or not 0 <= size <= 128
        or not np.isfinite(probability)
        or not 0 < probability < 1
    ):
        raise ValueError("Invalid generated binomial transform")
    table = np.zeros((size + 1, size + 1))
    table[0, 0] = 1
    for n in range(1, size + 1):
        table[:n, n] += table[:n, n - 1] * (1 - probability)
        table[1 : n + 1, n] += table[:n, n - 1] * probability
    return table


def pair_transforms(size, first, second):
    a, b = binomial_table(size, first), binomial_table(size, second)
    return tuple(
        np.column_stack([np.convolve(a[: x + 1, x], b[: n - x + 1, n - x]) for x in range(n + 1)])
        for n in range(size + 1)
    )


def tilt_expectations(plan, observed_trials, probability, theta):
    """E_product Bernoulli[exp(theta*(count-K/2)^2/K)] for every hidden context."""
    observed_trials = np.asarray(observed_trials)
    probability = np.asarray(probability, dtype=float)
    if (
        observed_trials.shape != (4,)
        or observed_trials.dtype.kind not in "iu"
        or np.any(observed_trials < 0)
        or np.any(observed_trials > 128)
        or observed_trials.sum() + len(plan["layers"]) - 1 > 128
        or probability.shape != (4,)
        or not np.isfinite(probability).all()
        or np.any((probability <= 0) | (probability >= 1))
        or not np.isfinite(theta)
        or not -8 <= theta <= 0
    ):
        raise ValueError("Invalid generated count-tilt context")
    observed = int(observed_trials.sum())
    base = np.array([1.0])
    for h, n in enumerate(observed_trials):
        for _ in range(int(n)):
            base = np.convolve(base, [1 - probability[h], probability[h]])
    previous = base[None]
    values = []
    for n in range(len(plan["layers"])):
        if n:
            selected = previous[plan["parents"][n]]
            p = probability[plan["categories"][n]][:, None]
            following = np.zeros((len(selected), selected.shape[1] + 1))
            following[:, :-1] = selected * (1 - p)
            following[:, 1:] += selected * p
            previous = following
        k = observed + n
        potential = np.exp(theta * (np.arange(k + 1) - k / 2) ** 2 / max(k, 1))
        values.append(previous @ potential)
    result = np.concatenate(values)
    if not np.isfinite(result).all() or np.any(result <= 0) or np.any(result > 1 + 1e-12):
        raise RuntimeError("Generated factored normalizer lost probability support")
    return result


class FactoredFilter:
    """Prepared model-specific contractions; never builds sparse compound edges."""

    def __init__(self, missing, model):
        parameters, self.terminal, signs, self.initial, self.transition = validate_model(model)
        if not np.array_equal(signs, np.ones(4)):
            raise ValueError("Factored filter requires unsigned generated count emissions")
        self.plan = count_plan(missing)
        self.parameters = parameters.copy()
        self.probability = 1 / (1 + np.exp(-parameters[:, :4]))
        self.thinning = tuple(binomial_table(missing, 1 - q) for q in self.terminal)
        self.even = tuple(pair_transforms(missing, p[0], p[2]) for p in self.probability)
        self.odd = tuple(pair_transforms(missing, p[1], p[3]) for p in self.probability)
        self.missing = missing
        self.indices = tuple(self.plan["counts"].T)
        self.blocks = []
        for total in range(missing + 1):
            for a in range(total + 1):
                b = total - a
                i, j = np.meshgrid(np.arange(a + 1), np.arange(b + 1), indexing="ij")
                source = (i, j, a - i, b - j)
                target = (a - i, i, b - j, j)
                self.blocks.append((total, a, b, source, target, i + j))

    def step(self, predictive, observed_trials, observed_success):
        """Unnormalized posterior, excluding observed terminal/Bernoulli constants."""
        if (
            predictive.shape != self.plan["shape"] + (2,)
            or not np.isfinite(predictive).all()
            or np.any(predictive < 0)
        ):
            raise ValueError("Invalid generated factored predictive mass")
        thinned = predictive
        for h, transform in enumerate(self.thinning):
            thinned = np.moveaxis(np.tensordot(transform, thinned, axes=(1, h)), 0, h)
        result = np.zeros_like(predictive)
        for z in range(2):
            normalizer = tilt_expectations(
                self.plan, observed_trials, self.probability[z], self.parameters[z, 4]
            )
            weighted = np.zeros(self.plan["shape"])
            weighted[self.indices] = thinned[self.indices + (z,)] / normalizer
            for total, a, b, source, target, events in self.blocks:
                contracted = self.even[z][a] @ weighted[source] @ self.odd[z][b].T
                k = int(observed_trials.sum()) + total
                potential = (
                    self.parameters[z, 4]
                    * (events + observed_success.sum() - k / 2) ** 2
                    / max(k, 1)
                )
                result[target + (z,)] = contracted * np.exp(potential)
        return result

    def filter(self, observed, missing_initial):
        history, events = validate_path(observed)
        missing_initial = np.asarray(missing_initial)
        if (
            missing_initial.shape != (self.missing,)
            or missing_initial.dtype.kind not in "iu"
            or not np.isin(missing_initial, range(4)).all()
            or len(history) + self.missing > 128
        ):
            raise ValueError("Known generated missing initial histories required")
        predictive = np.zeros(self.plan["shape"] + (2,))
        predictive[tuple(np.bincount(missing_initial, minlength=4))] = self.initial
        posterior = predictive.copy()
        alive = np.ones(len(history), dtype=bool)
        increments, posteriors = [], []
        for row in events:
            survivor = alive & (row != 2)
            trials = np.bincount(history[survivor], minlength=4)
            success = np.bincount(history[row == 1], minlength=4)
            dead = np.bincount(history[row == 2], minlength=4)
            terminal_logp = dead @ np.log(self.terminal) + trials @ np.log1p(-self.terminal)
            observed_logp = np.log(self.probability) @ success + np.log1p(-self.probability) @ (
                trials - success
            )
            shift = float(observed_logp.max())
            mass = self.step(predictive, trials, success) * np.exp(observed_logp - shift)
            total = mass.sum()
            if not np.isfinite(total) or total <= 0:
                raise RuntimeError("Generated factored filter lost supported mass")
            increment = float(np.log(total) + shift + terminal_logp)
            if not np.isfinite(increment) or increment > 1e-10:
                raise RuntimeError("Generated factored transition is not a subprobability")
            posterior = mass / total
            increments.append(increment)
            posteriors.append(posterior[self.indices].copy())
            predictive = posterior @ self.transition
            history[survivor] = 2 * (history[survivor] % 2) + row[survivor]
            alive = survivor
        return dict(
            data_class="synthetic",
            log_probability=float(sum(increments)),
            log_increments=np.array(increments),
            histogram_states=self.plan["states"].copy(),
            posterior=posterior[self.indices].copy(),
            next_state_probability=predictive[self.indices].copy(),
            posteriors=tuple(posteriors),
            histogram_states_count=self.plan["histogram_states"],
            compound_transition_terms_materialized=0,
            unknown_initial_histories_supported=False,
        )


def filter_factored(observed, missing_initial, model):
    missing_initial = np.asarray(missing_initial)
    if missing_initial.ndim != 1:
        raise ValueError("Known generated missing initial histories required")
    return FactoredFilter(len(missing_initial), model).filter(observed, missing_initial)
