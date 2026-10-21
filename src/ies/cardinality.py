"""Generated cardinality interaction laboratory with exact finite-set inference.

Cardinality dynamic programs, exponential tilts, and projection away from marginal
scores are established constructions. This module tests a bounded projected feature;
it is not a claimed novel algorithm, clinical adapter, or full recurrent-path learner.
"""

import numpy as np

MAX_ENTITIES = 128


def _reference(value):
    p = np.asarray(value, dtype=float)
    if (
        p.ndim != 1
        or not 0 <= len(p) <= MAX_ENTITIES
        or not np.isfinite(p).all()
        or np.any((p < 1e-4) | (p > 1 - 1e-4))
    ):
        raise ValueError("Invalid generated Bernoulli reference")
    return p


def count_distribution(fields, potential):
    """Exact normalizer, count probabilities and marginals in O(K^2) time/space.

    Density is proportional to exp(fields.y + potential[sum(y)]). Reverse
    differentiation of the log-polynomial recurrence computes all marginals without
    repeating K separate convolutions. No enumeration of 2^K configurations occurs.
    """
    fields, potential = np.asarray(fields, dtype=float), np.asarray(potential, dtype=float)
    if (
        fields.ndim != 1
        or not 0 <= len(fields) <= MAX_ENTITIES
        or potential.shape != (len(fields) + 1,)
        or not np.isfinite(fields).all()
        or not np.isfinite(potential).all()
        or np.any(np.abs(fields) > 1e9)
        or np.any(np.abs(potential) > 1e9)
    ):
        raise ValueError("Invalid generated cardinality parameters")
    k = len(fields)
    forward = np.full((k + 1, k + 1), -np.inf)
    forward[0, 0] = 0
    for i, field in enumerate(fields):
        forward[i + 1, : i + 2] = np.logaddexp(
            forward[i, : i + 2], np.r_[-np.inf, forward[i, : i + 1] + field]
        )
    logits = forward[k] + potential
    maximum = float(logits.max())
    mass = np.exp(logits - maximum)
    log_normalizer = maximum + float(np.log(mass.sum()))
    count_probability = mass / mass.sum()
    derivative = count_probability.copy()
    marginals = np.zeros(k)
    for i in range(k - 1, -1, -1):
        child = forward[i + 1, : i + 2]
        take = np.exp(fields[i] + forward[i, : i + 1] - child[1:])
        stay = np.exp(forward[i, : i + 1] - child[: i + 1])
        take_flow = derivative[1:] * take
        marginals[i] = take_flow.sum()
        derivative = derivative[: i + 1] * stay + take_flow
    return dict(
        fields=fields.copy(),
        potential=potential.copy(),
        log_normalizer=log_normalizer,
        count_probability=count_probability,
        marginals=marginals,
        forward=forward,
    )


def binary_events(value, entities):
    events = np.asarray(value)
    if (
        events.ndim != 2
        or events.shape[1] != entities
        or events.shape[0] < 1
        or events.size > 4_000_000
        or not np.isfinite(events).all()
        or np.any((events != 0) & (events != 1))
    ):
        raise ValueError("Complete generated binary transitions required")
    return events.astype(int)


def log_probability(model, events):
    events = binary_events(events, len(model["fields"]))
    return (
        events @ model["fields"] + model["potential"][events.sum(axis=1)] - model["log_normalizer"]
    )


def sample_sets(model, patients: int, seed: int):
    k = len(model["fields"])
    if type(patients) is not int or not 1 <= patients <= 100_000 or patients * k > 4_000_000:
        raise ValueError("Invalid generated sampling bound")
    rng = np.random.default_rng(seed)
    remaining = rng.choice(k + 1, patients, p=model["count_probability"])
    events = np.zeros((patients, k), dtype=int)
    forward = model["forward"]
    for i in range(k, 0, -1):
        take = np.zeros(patients)
        active = remaining > 0
        r = remaining[active]
        take[active] = np.exp(model["fields"][i - 1] + forward[i - 1, r - 1] - forward[i, r])
        chosen = rng.random(patients) < np.clip(take, 0, 1)
        events[:, i - 1] = chosen
        remaining -= chosen
    if np.any(remaining):
        raise RuntimeError("Generated backward count sampling failed")
    return events


def interaction_feature(reference, kind: str = "projected_bounded"):
    """Remove constant and single-entity L2 projections at the product reference.

    Orthogonality is local at the supplied reference, not exact marginal preservation
    after a nonzero tilt. A learned reference does not supply a population guarantee.
    """
    p = _reference(reference)
    if kind not in {"projected_bounded", "unprojected_bounded", "projected_quadratic"}:
        raise ValueError("Invalid generated interaction feature")
    variance = p * (1 - p)
    count = np.arange(len(p) + 1, dtype=float)
    fields = np.log(p) - np.log1p(-p)
    base = count_distribution(fields, np.zeros(len(p) + 1))
    if kind == "projected_quadratic":
        g = count * (count - 1) / 2
        mean = (p.sum() ** 2 - p @ p) / 2
        linear = p.sum() - p
        residual_variance = (variance.sum() ** 2 - variance @ variance) / 2
    else:
        log_g = -((count - p.sum()) ** 2) / (2 * (variance.sum() + 1))
        g = np.exp(log_g)
        weighted = count_distribution(fields, log_g)
        mean = float(base["count_probability"] @ g)
        linear = mean * (weighted["marginals"] - p) / variance
        if kind == "unprojected_bounded":
            linear = np.zeros(len(p))
        residual_variance = float(
            base["count_probability"] @ g**2 - mean**2 - (linear**2) @ variance
        )
    if residual_variance < -1e-10:
        raise RuntimeError("Generated feature variance became negative")
    degenerate = residual_variance <= 1e-12
    return dict(
        reference=p.copy(),
        kind=kind,
        count_feature=g,
        linear=linear,
        mean=float(mean),
        scale=1.0 if degenerate else float(np.sqrt(residual_variance)),
        degenerate=degenerate,
        reference_variance=float(max(0, residual_variance)),
    )


def feature_values(feature, events):
    p = feature["reference"]
    events = binary_events(events, len(p))
    if feature["degenerate"]:
        return np.zeros(len(events))
    return (
        feature["count_feature"][events.sum(axis=1)]
        - feature["mean"]
        - (events - p) @ feature["linear"]
    ) / feature["scale"]


def tilt_model(feature, strength: float):
    if not np.isfinite(strength) or abs(strength) > 4:
        raise ValueError("Invalid generated tilt strength")
    p = feature["reference"]
    effective = 0.0 if feature["degenerate"] else strength / feature["scale"]
    model = count_distribution(
        np.log(p) - np.log1p(-p) - effective * feature["linear"],
        effective * feature["count_feature"],
    )
    expected_feature = (
        model["count_probability"] @ feature["count_feature"]
        - feature["mean"]
        - (model["marginals"] - p) @ feature["linear"]
    ) / feature["scale"]
    model.update(
        strength=float(strength),
        kind=feature["kind"],
        expected_feature=0.0 if feature["degenerate"] else float(expected_feature),
    )
    return model


def fit_strength(reference, events, kind="projected_bounded", *, ridge=0.01, bound=2.0):
    """Convex scalar likelihood fit at a fixed reference, with bounded optimization.

    Bisection uses exact expected sufficient statistics. This is not joint nuisance
    fitting or a claim that references supplied by a simulator are feasible estimates.
    """
    if not np.isfinite([ridge, bound]).all() or not 0 < ridge <= 10 or not 0 < bound <= 4:
        raise ValueError("Invalid generated scalar-fit configuration")
    feature = interaction_feature(reference, kind)
    events = binary_events(events, len(feature["reference"]))
    target = float(feature_values(feature, events).mean())

    def evaluate(strength):
        model = tilt_model(feature, strength)
        derivative = model["expected_feature"] - target + ridge * strength
        return model, derivative

    low, high = -bound, bound
    low_model, low_gradient = evaluate(low)
    high_model, high_gradient = evaluate(high)
    iterations = 0
    if low_gradient >= 0:
        model, gradient, status = low_model, low_gradient, "lower_bound"
    elif high_gradient <= 0:
        model, gradient, status = high_model, high_gradient, "upper_bound"
    else:
        status = "interior"
        for iteration in range(1, 81):
            iterations = iteration
            strength = (low + high) / 2
            model, gradient = evaluate(strength)
            if abs(gradient) <= 1e-10:
                break
            if gradient > 0:
                high = strength
            else:
                low = strength
    gap = max(0.0, gradient * model["strength"] + abs(gradient) * bound)
    if gap > 1e-7:
        raise RuntimeError("Generated scalar likelihood fit did not certify convergence")
    return model, dict(
        status=status,
        strength=model["strength"],
        convex_gap=gap,
        iterations=iterations,
        empirical_feature_mean=target,
        objective=float(
            -log_probability(model, events).mean() + ridge * model["strength"] ** 2 / 2
        ),
        ridge=ridge,
        bound=bound,
        reference_fitted_here=False,
        exact_marginal_preservation=False,
    )
