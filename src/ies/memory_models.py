"""CPU prototypes for context allocation, not a new-method or streaming-memory claim."""

from dataclasses import dataclass

import numpy as np

from ies.memory_data import Context, Outcome, label_mask, visible


@dataclass(frozen=True)
class Encoded:
    patient_id: str
    order_ids: tuple[str, ...]
    signatures: tuple[tuple, ...]
    counts: np.ndarray
    features: np.ndarray  # order x retained depth x feature
    descriptors: np.ndarray  # prefix-only allocation features, charged separately
    summaries: np.ndarray  # strong constant-size per-order reference
    scanned_events: int


def _stats(lags):
    gaps = np.diff(lags)
    return [
        np.log1p(len(lags)),
        float(bool(lags)),
        lags[0] / 48 if lags else 0.0,
        float(gaps.mean()) / 12 if len(gaps) else 0.0,
        float(gaps.std()) / 12 if len(gaps) else 0.0,
        float(len(gaps) > 0),
    ]


def encode(context: Context, depth: int) -> Encoded:
    """Offline prefix encoding: all selectors may inspect the same complete past.

    The cap is on retained EVENT CONTEXT, not total RAM. Full-prefix scanning, the
    order roster, four shared counters and allocator descriptors are explicitly extra.
    No outcome or post-cutoff record is accepted by this function's interface.
    """
    rows = visible(context)
    if not rows or type(depth) is not int or not 1 <= depth <= 12:
        raise ValueError("Invalid generated context encoding")
    all_lags = np.array([lag for _, lags in rows for lag in lags])
    global_features = [
        float(np.log1p(np.sum(all_lags <= window) / len(rows))) for window in (2, 8, 24, np.inf)
    ]
    features, descriptors, summaries, signatures = [], [], [], []
    for order, lags in rows:
        age = context.cutoff - order.occurred
        signatures.append((age, lags))
        common = [*global_features, age / 48]
        summaries.append([*common, *_stats(lags)])
        descriptor = [age / 48, *_stats(lags)]
        gaps = np.diff(lags)
        descriptor += [float(gaps[:2].mean()) / 12 if len(gaps) else 0.0]
        # Quadratic features for the small ridge utility regressor; not a neural SOTA.
        descriptors.append(
            descriptor + [a * b for i, a in enumerate(descriptor) for b in descriptor[i:]]
        )
        options = []
        for count in range(depth + 1):
            retained = lags[:count]
            padded = [lag / 48 for lag in retained] + [0.0] * (depth - len(retained))
            mask = [1.0] * len(retained) + [0.0] * (depth - len(retained))
            options.append([*common, *_stats(retained), *padded, *mask])
        features.append(options)
    return Encoded(
        context.patient_id,
        tuple(o.order_id for o, _ in rows),
        tuple(signatures),
        np.array([len(lags) for _, lags in rows], dtype=int),
        np.asarray(features),
        np.asarray(descriptors),
        np.asarray(summaries),
        len(context.events),
    )


def observed_nll(probabilities, mask):
    if (
        probabilities.shape != mask.shape
        or not np.isfinite(probabilities).all()
        or not np.all(probabilities > 0)
        or not np.allclose(probabilities.sum(axis=1), 1)
        or not mask.any(axis=1).all()
    ):
        raise ValueError("Invalid censored probability forecast")
    return -np.log((probabilities * mask).sum(axis=1))


def _softmax(logits):
    value = np.exp(logits - logits.max(axis=1, keepdims=True))
    return value / value.sum(axis=1, keepdims=True)


def objective_gradient(x, mask, parameters, weights, ridge):
    """Censored categorical likelihood with analytic gradients for a small tanh MLP."""
    w1, b1, w2, b2 = parameters
    hidden = np.tanh(x @ w1 + b1)
    probability = _softmax(hidden @ w2 + b2)
    mass = (probability * mask).sum(axis=1, keepdims=True)
    if np.any(mass <= 0) or not np.isfinite(mass).all():
        raise ValueError("Nonfinite generated model likelihood")
    loss = float(weights @ -np.log(mass[:, 0]) + ridge * ((w1**2).sum() + (w2**2).sum()) / 2)
    delta = weights[:, None] * (probability - probability * mask / mass)
    back = (delta @ w2.T) * (1 - hidden**2)
    gradient = [x.T @ back + ridge * w1, back.sum(0), hidden.T @ delta + ridge * w2, delta.sum(0)]
    return loss, gradient


def fit_decoder(x, outcomes, horizon, hidden, epochs, learning_rate, ridge, seed, weights):
    """Fixed-iteration deterministic CPU control; no validation-based epoch selection."""
    mask = label_mask(outcomes, horizon)
    if len(x) != len(outcomes) or not np.isfinite(x).all():
        raise ValueError("Invalid generated decoder input")
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (len(x),) or not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError("Invalid decoder weights")
    weights = weights / weights.sum()
    mean = weights @ x
    scale = np.sqrt(weights @ ((x - mean) ** 2))
    scale[scale < 1e-6] = 1
    x = (x - mean) / scale
    rng = np.random.default_rng(seed)
    parameters = [
        rng.normal(0, 1 / np.sqrt(x.shape[1]), size=(x.shape[1], hidden)),
        np.zeros(hidden),
        rng.normal(0, 0.1, size=(hidden, mask.shape[1])),
        np.zeros(mask.shape[1]),
    ]
    first = [np.zeros_like(p) for p in parameters]
    second = [np.zeros_like(p) for p in parameters]
    initial = objective_gradient(x, mask, parameters, weights, ridge)[0]
    for step in range(1, epochs + 1):
        _, gradients = objective_gradient(x, mask, parameters, weights, ridge)
        for i, gradient in enumerate(gradients):
            first[i] = 0.9 * first[i] + 0.1 * gradient
            second[i] = 0.999 * second[i] + 0.001 * gradient**2
            parameters[i] -= (
                learning_rate
                * first[i]
                / (1 - 0.9**step)
                / (np.sqrt(second[i] / (1 - 0.999**step)) + 1e-8)
            )
    final = objective_gradient(x, mask, parameters, weights, ridge)[0]
    if not np.isfinite(final):
        raise ValueError("Nonfinite generated fit")
    return {
        "data_class": "synthetic",
        "kind": "small_censored_categorical_mlp",
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "parameters": [p.tolist() for p in parameters],
        "parameter_count": int(sum(p.size for p in parameters)),
        "epochs": epochs,
        "initial_training_objective": initial,
        "final_training_objective": final,
        "convergence_claimed": False,
    }


def predict(model, x):
    if model.get("data_class") != "synthetic":
        raise ValueError("Generated decoder only")
    w1, b1, w2, b2 = map(np.asarray, model["parameters"])
    z = (x - np.asarray(model["mean"])) / np.asarray(model["scale"])
    probability = _softmax(np.tanh(z @ w1 + b1) @ w2 + b2)
    if not np.isfinite(probability).all() or np.any(probability <= 0):
        raise ValueError("Nonfinite generated predictions")
    return probability


def fit_allocator(descriptors, losses, weights, ridge):
    """Learn expected loss reduction on patients NOT used to fit the decoder.

    This is supervised budget allocation with a standard ridge regressor and exact
    multiple-choice knapsack solver; these ingredients are not claimed as novel.
    """
    weights = np.asarray(weights, dtype=float)
    weights /= weights.sum()
    mean = weights @ descriptors
    scale = np.sqrt(weights @ (descriptors - mean) ** 2)
    scale[scale < 1e-6] = 1
    x = np.column_stack([np.ones(len(descriptors)), (descriptors - mean) / scale])
    utility = losses[:, :1] - losses
    penalty = np.eye(x.shape[1]) * ridge
    penalty[0, 0] = 1e-10
    coefficients = np.linalg.solve(
        x.T @ (weights[:, None] * x) + penalty, x.T @ (weights[:, None] * utility)
    )
    return dict(
        data_class="synthetic",
        mean=mean.tolist(),
        scale=scale.tolist(),
        coefficients=coefficients.tolist(),
        static_utility=(weights @ utility).tolist(),
        parameter_count=int(coefficients.size),
    )


def utilities(model, descriptors):
    x = np.column_stack([np.ones(len(descriptors)), (descriptors - model["mean"]) / model["scale"]])
    return x @ np.asarray(model["coefficients"])


def _groups(encoded):
    groups = {}
    for i, signature in enumerate(encoded.signatures):
        groups.setdefault(signature, []).append(i)
    return sorted(groups.items())


def allocate(encoded: Encoded, budget: int, policy: str, utility=None):
    """Exact additive allocation, with identical observable histories kept symmetric.

    Identical signatures receive equal depths. This can leave budget unused. The DP
    is optimal within that symmetry constraint; it is not optimal for the true unknown
    loss or an arbitrary dependent joint event process.
    """
    depth = encoded.features.shape[1] - 1
    if type(budget) is not int or budget < 0 or policy not in {"recent", "balanced", "utility"}:
        raise ValueError("Invalid context allocation")
    groups = _groups(encoded)
    allocation = np.zeros(len(encoded.order_ids), dtype=int)
    if policy in {"recent", "balanced"}:
        candidates = []
        for signature, members in groups:
            for rank, lag in enumerate(signature[1][:depth]):
                priority = (lag, signature, rank) if policy == "recent" else (rank, lag, signature)
                candidates.append((priority, members, rank))
        for _, members, rank in sorted(candidates, key=lambda row: row[0]):
            if allocation[members[0]] == rank and len(members) <= budget:
                allocation[members] += 1
                budget -= len(members)
        return allocation
    if (
        utility is None
        or utility.shape != encoded.features.shape[:2]
        or not np.isfinite(utility).all()
    ):
        raise ValueError("Invalid allocation utility")
    # states: exact cost -> (predicted utility, group-depth tuple)
    states = {0: (0.0, ())}
    for _, members in groups:
        updated = {}
        for cost, (value, choices) in states.items():
            for count in range(min(depth, encoded.counts[members[0]]) + 1):
                total = cost + count * len(members)
                if total > budget:
                    break
                candidate = value + float(utility[members, count].sum())
                if total not in updated or candidate > updated[total][0] + 1e-12:
                    updated[total] = (candidate, (*choices, count))
        states = updated
    best_cost = max(states, key=lambda cost: (states[cost][0], -cost))
    for (_, members), count in zip(groups, states[best_cost][1], strict=True):
        allocation[members] = count
    return allocation


def aligned_outcomes(encoded: Encoded, outcomes: tuple[Outcome, ...]):
    lookup = {o.order_id: o for o in outcomes}
    if len(lookup) != len(outcomes) or set(lookup) != set(encoded.order_ids):
        raise ValueError("Outcome identity mismatch")
    return [lookup[key] for key in encoded.order_ids]
