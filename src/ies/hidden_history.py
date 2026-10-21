"""Exact generated filtering of permanently unobserved recurrent entities.

Known initial histories and a fixed full roster are required. Histogram lumping
uses standard finite-state symmetry; it is not a novelty or identification claim.
No entity reappearance, unknown roster or informative observation law is inferred.
"""

from functools import lru_cache
from itertools import product
from math import comb, lgamma

import numpy as np

from ies.competition import LOWER, UPPER, batch_log_normalizer, features, validate_signs
from ies.history_roles import validate_hmm, validate_path


def compositions(total, parts):
    if parts == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for rest in compositions(total - first, parts - 1):
                yield (first, *rest)


@lru_cache(maxsize=3)
def histogram_plan(missing):
    """Sparse exact count transitions, with labeled-assignment multiplicities."""
    if type(missing) is not int or not 0 <= missing <= 8:
        raise ValueError("Invalid bounded generated missing roster")
    states = np.array(list(compositions(missing, 5)), dtype=np.int16)
    lookup = {tuple(row): i for i, row in enumerate(states)}
    sources, targets, trials, successes, terminals, multiplicities = [], [], [], [], [], []
    for source, state in enumerate(states):
        choices = [
            [(dead, event) for dead in range(n + 1) for event in range(n - dead + 1)]
            for n in state[:4]
        ]
        for outcomes in product(*choices):
            dead, event = np.array(outcomes).T
            survivor = state[:4] - dead
            following = np.zeros(5, dtype=int)
            following[4] = state[4] + dead.sum()
            multiplicity = 0.0
            for h in range(4):
                following[2 * (h % 2)] += survivor[h] - event[h]
                following[2 * (h % 2) + 1] += event[h]
                multiplicity += (
                    lgamma(state[h] + 1)
                    - lgamma(dead[h] + 1)
                    - lgamma(event[h] + 1)
                    - lgamma(survivor[h] - event[h] + 1)
                )
            sources.append(source)
            targets.append(lookup[tuple(following)])
            trials.append(survivor)
            successes.append(event)
            terminals.append(dead)
            multiplicities.append(multiplicity)
    if len(states) != comb(missing + 4, 4) or len(sources) != comb(missing + 12, 12):
        raise RuntimeError("Generated histogram transition support mismatch")
    plan = dict(
        states=states,
        source=np.array(sources, dtype=np.int32),
        target=np.array(targets, dtype=np.int32),
        trials=np.array(trials, dtype=np.int16),
        success=np.array(successes, dtype=np.int16),
        terminal=np.array(terminals, dtype=np.int16),
        log_multiplicity=np.array(multiplicities),
    )
    # Cached arrays must not change between subjects or model evaluations.
    for value in plan.values():
        value.setflags(write=False)
    return plan


def validate_model(model):
    parameters = np.asarray(model["parameters"], dtype=float)
    terminal = np.asarray(model["terminal"], dtype=float)
    signs = validate_signs(model["signs"])
    _, initial, transition = validate_hmm(model | {"probability": np.full((2, 4), 0.5)})
    if (
        parameters.shape != (2, 5)
        or not np.isfinite(parameters).all()
        or np.any(parameters < LOWER)
        or np.any(parameters > UPPER)
        or terminal.shape != (4,)
        or not np.isfinite(terminal).all()
        or np.any((terminal <= 0) | (terminal >= 1))
    ):
        raise ValueError("Invalid generated count-filter model")
    return parameters, terminal, signs, initial, transition


def filter_missing(observed, missing_initial, model, *, emission=None):
    """Marginal prefix law for a known observed subset of one fixed population.

    The omitted entities are never observed after the initial histories. All their
    subsequent histories and terminal events are summed out. Observation masks must
    be fixed/ignorable; this conditional model does not establish that assumption.
    Returns filtering (not smoothing) posteriors and next-state predictive masses.
    An optional emission callback supplies normalized, strictly positive labeled
    pattern log probabilities for each latent state. Numeric checks here do not
    prove its normalization; the callback's law must be independently verified.
    """
    history, events = validate_path(observed)
    missing_initial = np.asarray(missing_initial)
    if (
        missing_initial.ndim != 1
        or missing_initial.dtype.kind not in "iu"
        or not 0 <= len(missing_initial) <= 8
        or len(history) + len(missing_initial) > 128
        or not np.isin(missing_initial, [0, 1, 2, 3]).all()
    ):
        raise ValueError("Known generated missing initial histories required")
    parameters, terminal, signs, initial, transition = validate_model(model)
    plan = histogram_plan(len(missing_initial))
    states, source, target = plan["states"], plan["source"], plan["target"]
    initial_counts = np.r_[np.bincount(missing_initial, minlength=4), 0]
    first = np.flatnonzero(np.all(states == initial_counts, axis=1))[0]
    predictive = np.zeros((len(states), 2))
    predictive[first] = initial
    posterior = predictive.copy()
    alive = np.ones(len(history), dtype=bool)
    increments, posteriors = [], []
    hidden_terminal = (
        plan["terminal"] @ np.log(terminal)
        + plan["trials"] @ np.log1p(-terminal)
        + plan["log_multiplicity"]
    )
    for row in events:
        survivor = alive & (row != 2)
        observed_trials = np.bincount(history[survivor], minlength=4)
        observed_success = np.bincount(history[row == 1], minlength=4)
        dead = np.bincount(history[row == 2], minlength=4)
        terminal_logp = dead @ np.log(terminal) + observed_trials @ np.log1p(-terminal)
        trials = plan["trials"] + observed_trials
        success = plan["success"] + observed_success
        if emission is None:
            contexts, index = np.unique(trials, axis=0, return_inverse=True)
            x = features(success, trials, signs)
            log_emission = np.column_stack(
                [x @ p - batch_log_normalizer(contexts, p, signs)[index] for p in parameters]
            )
        else:
            log_emission = np.asarray(emission(success, trials), dtype=float)
            if (
                log_emission.shape != (len(trials), 2)
                or not np.isfinite(log_emission).all()
                or np.any(log_emission > 1e-9)
            ):
                raise ValueError("Invalid generated custom emission probabilities")
        log_predictive = np.full(predictive.shape, -np.inf)
        np.log(predictive, out=log_predictive, where=predictive > 0)
        joint = log_predictive[source] + log_emission + hidden_terminal[:, None] + terminal_logp
        maximum = joint.max()
        if not np.isfinite(maximum):
            raise RuntimeError("Generated filter has no supported mass")
        mass = np.exp(joint - maximum)
        posterior = np.column_stack(
            [np.bincount(target, weights=mass[:, z], minlength=len(states)) for z in range(2)]
        )
        total = posterior.sum()
        increment = float(maximum + np.log(total))
        if not np.isfinite(increment) or increment > 1e-10:
            raise RuntimeError("Generated marginal transition is not a subprobability")
        posterior /= total
        increments.append(increment)
        posteriors.append(posterior.copy())
        predictive = posterior @ transition
        history[survivor] = 2 * (history[survivor] % 2) + row[survivor]
        alive = survivor
    return dict(
        data_class="synthetic",
        log_probability=float(sum(increments)),
        log_increments=np.array(increments),
        histogram_states=states.copy(),
        posterior=posterior,
        next_state_probability=predictive,
        posteriors=tuple(posteriors),
        histogram_states_count=len(states),
        transition_terms=len(source),
        labeled_history_states_count=5 ** len(missing_initial),
        unknown_initial_histories_supported=False,
    )
