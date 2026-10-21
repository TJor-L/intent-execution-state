"""Generated recurrent reference models with history-only, permutation-equivariant roles.

Known finite mixtures and hidden Markov inference, not a claimed new architecture.
No files, clinical mappings, or future-tail imputations are accepted here.
"""

from dataclasses import dataclass
from itertools import product

import numpy as np

from ies.cardinality import count_distribution, sample_sets

HORIZON = 8
SCENARIOS = (
    "independent",
    "shared_fresh",
    "history_fresh",
    "history_persistent",
    "hidden_persistent",
    "history_capacity",
)
BASE = np.array([0.18, 0.32, 0.25, 0.42])
TERMINAL = np.array([0.03, 0.04, 0.05, 0.06])
PARITY = np.array([1, -1, -1, 1])


@dataclass(frozen=True)
class GeneratedPath:
    initial: np.ndarray
    events: np.ndarray
    data_class: str = "synthetic"


def validate_path(path):
    if not isinstance(path, GeneratedPath) or path.data_class != "synthetic":
        raise ValueError("Generated recurrent paths required")
    initial, events = np.asarray(path.initial), np.asarray(path.events)
    if (
        initial.ndim != 1
        or not 1 <= len(initial) <= 128
        or initial.dtype.kind not in "iu"
        or not np.isin(initial, [0, 1, 2, 3]).all()
        or events.ndim != 2
        or events.shape[1] != len(initial)
        or not 0 <= len(events) <= HORIZON
        or events.dtype.kind not in "iu"
        or not np.isin(events, [-1, 0, 1, 2]).all()
    ):
        raise ValueError("Invalid generated recurrent support")
    alive = np.ones(len(initial), dtype=bool)
    for row in events:
        if not np.array_equal(row == -1, ~alive):
            raise ValueError("Inactive padding or absorbing termination violated")
        alive &= row != 2
    return initial.astype(int), events.astype(int)


def generate(scenario, patients, rosters, seed, policy="complete"):
    if (
        scenario not in SCENARIOS
        or policy not in ("complete", "adaptive")
        or type(patients) is not int
        or not 1 <= patients <= 4096
        or not isinstance(rosters, (list, tuple))
        or not 1 <= len(rosters) <= 4
        or any(type(k) is not int or not 1 <= k <= 128 for k in rosters)
        or type(seed) is not int
        or not 0 <= seed < 2**32
    ):
        raise ValueError("Invalid generated history-role resource bound")
    paths = []
    for index in range(patients):
        rng = np.random.default_rng(np.random.SeedSequence([seed, index, 0]))
        stop_rng = np.random.default_rng(np.random.SeedSequence([seed, index, 1]))
        k = rosters[index % len(rosters)]
        initial = rng.integers(0, 4, size=k)
        history, alive = initial.copy(), np.ones(k, dtype=bool)
        hidden_role = rng.choice([-1, 1], size=k)
        shock = rng.choice([-1, 1])
        rows = []
        for time in range(HORIZON):
            if policy == "adaptive" and time >= 2:
                rate = float((history[alive] % 2).mean()) if alive.any() else 0.0
                if stop_rng.random() < 0.12 + 0.25 * rate:
                    break
            row = np.full(k, -1, dtype=int)
            row[alive] = 0
            terminal = alive & (rng.random(k) < TERMINAL[history])
            row[terminal] = 2
            survivor = alive & ~terminal
            p = BASE[history[survivor]]
            signs = PARITY[history[survivor]]
            if scenario in ("history_persistent", "hidden_persistent"):
                if time and rng.random() < (1 - 0.85) / 2:
                    shock *= -1
            else:
                shock = rng.choice([-1, 1])
            if scenario == "history_capacity":
                signed_p = np.where(signs > 0, p, 1 - p)
                m = len(p)
                model = count_distribution(
                    np.log(signed_p) - np.log1p(-signed_p),
                    -4 * (np.arange(m + 1) - signed_p.sum()) ** 2 / max(m, 1),
                )
                signed_y = sample_sets(model, 1, rng)[0]
                y = np.where(signs > 0, signed_y, 1 - signed_y)
            else:
                if scenario == "shared_fresh":
                    signs = np.ones(len(p))
                elif scenario == "hidden_persistent":
                    signs = hidden_role[survivor]
                amplitude = 0 if scenario == "independent" else 0.55
                probability = p + amplitude * shock * signs * np.minimum(p, 1 - p)
                y = rng.random(len(p)) < probability
            row[survivor] = y
            rows.append(row)
            history[survivor] = (history[survivor] % 2) * 2 + y
            alive = survivor
        paths.append(GeneratedPath(initial, np.array(rows, dtype=int).reshape(-1, k)))
    return paths


def pack(paths):
    if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= 4096:
        raise ValueError("Bounded generated subject list required")
    shape = (len(paths), HORIZON, 4)
    exposure, terminal, trials, success = [np.zeros(shape) for _ in range(4)]
    lengths = np.zeros(len(paths), dtype=int)
    for i, path in enumerate(paths):
        history, events = validate_path(path)
        lengths[i] = len(events)
        for t, row in enumerate(events):
            for h in range(4):
                chosen = (history == h) & (row >= 0)
                exposure[i, t, h] = chosen.sum()
                terminal[i, t, h] = np.sum(chosen & (row == 2))
                trials[i, t, h] = np.sum(chosen & (row != 2))
                success[i, t, h] = np.sum(chosen & (row == 1))
            observed = (row == 0) | (row == 1)
            history[observed] = (history[observed] % 2) * 2 + row[observed]
    return dict(
        exposure=exposure, terminal=terminal, trials=trials, success=success, lengths=lengths
    )


def fit_reference(data):
    return dict(
        probability=(data["success"].sum(axis=(0, 1)) + 0.5)
        / (data["trials"].sum(axis=(0, 1)) + 1),
        terminal=(data["terminal"].sum(axis=(0, 1)) + 0.5)
        / (data["exposure"].sum(axis=(0, 1)) + 1),
    )


def lse(a, axis=-1):
    maximum = np.max(a, axis=axis, keepdims=True)
    return np.squeeze(maximum, axis=axis) + np.log(np.exp(a - maximum).sum(axis=axis))


def emissions(data, probability):
    return np.einsum("nth,zh->ntz", data["success"], np.log(probability)) + np.einsum(
        "nth,zh->ntz", data["trials"] - data["success"], np.log1p(-probability)
    )


def terminal_score(data, probability):
    return (
        data["terminal"] * np.log(probability)
        + (data["exposure"] - data["terminal"]) * np.log1p(-probability)
    ).sum(axis=(1, 2))


def validate_hmm(model):
    p, initial, transition = [
        np.asarray(model[k], dtype=float) for k in ("probability", "initial", "transition")
    ]
    if (
        p.shape != (2, 4)
        or initial.shape != (2,)
        or transition.shape != (2, 2)
        or any(not np.isfinite(a).all() for a in (p, initial, transition))
        or np.any((p <= 0) | (p >= 1))
        or np.any(initial <= 0)
        or np.any(transition <= 0)
        or not np.isclose(initial.sum(), 1, atol=1e-12, rtol=0)
        or not np.allclose(transition.sum(axis=1), 1, atol=1e-12, rtol=0)
    ):
        raise ValueError("Invalid conditional Markov reference")
    return p, initial, transition


def forward(data, model, posterior=False):
    p, initial, transition = validate_hmm(model)
    return forward_emissions(emissions(data, p), initial, transition, data["lengths"], posterior)


def forward_emissions(e, initial, transition, lengths, posterior=False):
    """Exact two-state filtering for a supplied normalized conditional emission law."""
    e = np.asarray(e, dtype=float)
    lengths = np.asarray(lengths)
    if (
        e.ndim != 3
        or e.shape[2] != 2
        or not 1 <= e.shape[0] <= 4096
        or not 1 <= e.shape[1] <= HORIZON
        or not np.isfinite(e).all()
        or lengths.shape != (e.shape[0],)
        or lengths.dtype.kind not in "iu"
        or np.any((lengths < 0) | (lengths > e.shape[1]))
    ):
        raise ValueError("Invalid bounded conditional emissions")
    validate_hmm(dict(probability=np.full((2, 4), 0.5), initial=initial, transition=transition))
    initial, transition = np.asarray(initial), np.asarray(transition)
    observed = np.arange(e.shape[1])[None] < lengths[:, None]
    if np.any(np.abs(e[~observed]) > 1e-12):
        raise ValueError("Unobserved tails must be marginalized")
    n, tmax, _ = e.shape
    alpha, scales = np.empty_like(e), np.empty((n, tmax))
    prior = np.broadcast_to(np.log(initial), (n, 2))
    for t in range(tmax):
        value = prior + e[:, t]
        scales[:, t] = lse(value)
        alpha[:, t] = value - scales[:, t, None]
        prior = lse(alpha[:, t, :, None] + np.log(transition), axis=1)
    score = scales.sum(axis=1)
    if not posterior:
        return score
    beta = np.zeros_like(e)
    xi = np.zeros((n, tmax - 1, 2, 2))
    for t in range(tmax - 2, -1, -1):
        next_value = e[:, t + 1] + beta[:, t + 1]
        beta[:, t] = lse(np.log(transition)[None] + next_value[:, None], axis=2)
        beta[:, t] -= scales[:, t + 1, None]
        pair = alpha[:, t, :, None] + np.log(transition) + next_value[:, None]
        xi[:, t] = np.exp(pair - lse(pair.reshape(n, 4))[:, None, None])
    gamma = np.exp(alpha + beta - lse(alpha + beta)[:, :, None])
    gamma *= (np.arange(tmax)[None] < lengths[:, None])[:, :, None]
    xi *= (np.arange(tmax - 1)[None] < lengths[:, None] - 1)[:, :, None, None]
    return score, gamma, xi


def bank_models(reference, shared_only=False):
    p = reference["probability"]
    result = [
        dict(
            name="independent",
            probability=np.stack([p, p]),
            initial=np.array([0.5, 0.5]),
            transition=np.full((2, 2), 0.5),
        )
    ]
    signs_bank = [(1, 1, 1, 1)] if shared_only else [(1, *v) for v in product([-1, 1], repeat=3)]
    for signs in signs_bank:
        for amplitude in (0.3, 0.7):
            for rho in (0.0, 0.85):
                shift = amplitude * np.asarray(signs) * np.minimum(p, 1 - p)
                result.append(
                    dict(
                        name=(
                            f"roles_{''.join('p' if s > 0 else 'm' for s in signs)}"
                            f"_a{amplitude}_r{rho}"
                        ),
                        probability=np.stack([p - shift, p + shift]),
                        initial=np.array([0.5, 0.5]),
                        transition=np.array(
                            [[(1 + rho) / 2, (1 - rho) / 2], [(1 - rho) / 2, (1 + rho) / 2]]
                        ),
                    )
                )
    return result


def fit_weights(scores, iterations=200):
    scores = np.asarray(scores, dtype=float)
    if (
        scores.ndim != 2
        or not 1 <= scores.shape[0] <= 4096
        or not 1 <= scores.shape[1] <= 65
        or not np.isfinite(scores).all()
        or type(iterations) is not int
        or not 1 <= iterations <= 500
    ):
        raise ValueError("Invalid generated mixture fit")
    n, m = scores.shape
    weights = np.full(m, 1 / m)
    trace = []
    for _ in range(iterations):
        joint = scores + np.log(weights)
        norm = lse(joint)
        trace.append(float(norm.sum() + np.log(weights).mean()))
        responsibilities = np.exp(joint - norm[:, None])
        weights = (responsibilities.sum(axis=0) + 1 / m) / (n + 1)
    final = lse(scores + np.log(weights))
    trace.append(float(final.sum() + np.log(weights).mean()))
    if np.min(np.diff(trace)) < -1e-7:
        raise ValueError("Mixture MAP objective decreased")
    return weights, trace


def fit_bank(data, reference, shared_only=False):
    models = bank_models(reference, shared_only)
    scores = np.column_stack([forward(data, model) for model in models])
    weights, trace = fit_weights(scores)
    return dict(models=models, weights=weights, terminal=reference["terminal"], objective=trace)


def bank_score(data, bank):
    scores = np.column_stack([forward(data, model) for model in bank["models"]])
    return lse(scores + np.log(bank["weights"])) + terminal_score(data, bank["terminal"])


def hmm_score(data, model):
    return forward(data, model) + terminal_score(data, model["terminal"])


def fit_hmm(data, reference, seed, iterations=60):
    if type(iterations) is not int or not 1 <= iterations <= 100:
        raise ValueError("Invalid bounded Markov iteration count")
    rng = np.random.default_rng(seed)
    starts, candidates = [], []
    p = reference["probability"]
    for start in range(3):
        signs = np.ones(4) if start == 0 else PARITY if start == 1 else rng.choice([-1, 1], 4)
        shift = 0.5 * signs * np.minimum(p, 1 - p)
        model = dict(
            probability=np.stack([p - shift, p + shift]),
            initial=np.array([0.5, 0.5]),
            transition=np.array([[0.8, 0.2], [0.2, 0.8]]),
            terminal=reference["terminal"],
        )
        trace = []
        for iteration in range(iterations + 1):
            score, gamma, xi = forward(data, model, posterior=True)
            q = model["probability"]
            objective = (
                score.sum()
                + 0.5 * (np.log(q) + np.log1p(-q)).sum()
                + 0.5 * np.log(model["transition"]).sum()
                + 0.5 * np.log(model["initial"]).sum()
            )
            trace.append(float(objective))
            if iteration == iterations:
                break
            successes = np.einsum("ntz,nth->zh", gamma, data["success"])
            trials = np.einsum("ntz,nth->zh", gamma, data["trials"])
            model["probability"] = (successes + 0.5) / (trials + 1)
            counts = xi.sum(axis=(0, 1)) + 0.5
            model["transition"] = counts / counts.sum(axis=1, keepdims=True)
            counts = gamma[:, 0].sum(axis=0) + 0.5
            model["initial"] = counts / counts.sum()
        if np.min(np.diff(trace)) < -1e-6:
            raise ValueError("Conditional Markov MAP objective decreased")
        starts.append(trace)
        candidates.append(model)
    best = int(np.argmax([trace[-1] for trace in starts]))
    return candidates[best], dict(
        selected_start=best, objective_traces=starts, global_optimum_claimed=False
    )
