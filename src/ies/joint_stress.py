"""Exact generated misspecification and observation policies for the J002 experiment."""

import numpy as np

from ies.joint_observation import (
    HORIZON,
    LAWS,
    STATES,
    WINDOWS,
    PrefixCounts,
    _probability,
    joint_law,
    projection,
)

SCENARIOS = (*LAWS, "alternating_dependence", "lagged_dependence")
POLICIES = (*WINDOWS, "adaptive_past", "informative_future")


def stress_law(name: str):
    if name in LAWS:
        return joint_law(name)
    if name not in SCENARIOS:
        raise ValueError("Unknown generated dependency stress")
    probability = np.ones(len(STATES))
    low, high = np.array([0.84, 0.08, 0.08]), np.array([0.42, 0.50, 0.08])
    for i, state in enumerate(STATES):
        for time in range(HORIZON):
            alive = [2 not in row[:time] for row in state]
            codes = state[:, time]
            if not any(alive):
                continue
            if name == "alternating_dependence":
                if all(alive):
                    a, b = codes
                    if time == 1:
                        probability[i] *= (low[a] * high[b] + high[a] * low[b]) / 2
                    else:
                        probability[i] *= (low[a] * low[b] + high[a] * high[b]) / 2
                else:
                    code = codes[alive.index(True)]
                    probability[i] *= (low[code] + high[code]) / 2
            else:
                for entity in range(2):
                    if alive[entity]:
                        rate = 0.08 + 0.45 * (time > 0 and state[1 - entity, time - 1] == 1)
                        probability[i] *= (0.92 - rate, rate, 0.08)[codes[entity]]
    return _probability(probability, len(STATES))


def observation_kernel(name: str):
    """P(C=c | latent path), used only for simulation and exact evaluation.

    adaptive_past depends on the already observed path when deciding whether to stop.
    informative_future also depends on unseen outcomes. Neither kernel is passed to a fit.
    """
    if name in WINDOWS:
        return np.tile(WINDOWS[name], (len(STATES), 1)).T
    if name not in POLICIES:
        raise ValueError("Unknown generated observation stress")
    if name == "adaptive_past":
        first = np.where(np.any(STATES[:, :, 0] == 1, axis=1), 0.8, 0.2)
        second = np.where((STATES[:, :, :2] == 1).sum(axis=(1, 2)) >= 2, 0.7, 0.25)
    else:
        first = np.where(np.all((STATES == 1).sum(axis=2) >= 2, axis=1), 0.85, 0.15)
        second = np.where(np.any(STATES[:, :, 2] == 1, axis=1), 0.7, 0.2)
    return np.stack(
        [np.zeros(len(STATES)), first, (1 - first) * second, (1 - first) * (1 - second)]
    )


def _kernel(value):
    value = np.asarray(value, dtype=float)
    if (
        value.shape != (HORIZON + 1, len(STATES))
        or not np.isfinite(value).all()
        or np.any(value < 0)
        or not np.allclose(value.sum(axis=0), 1, atol=1e-12, rtol=0)
    ):
        raise ValueError("Invalid generated observation kernel")
    return value


def sample_stopped(law, kernel, patients: int, seed: int):
    law, kernel = _probability(law, len(STATES)), _kernel(kernel)
    if type(patients) is not int or not 1 <= patients <= 100_000:
        raise ValueError("Invalid generated patient bound")
    latent = np.random.default_rng(seed).choice(len(STATES), patients, p=law)
    uniforms = np.random.default_rng(seed + 1_000_003).random(patients)
    stops = (uniforms[None, :] > np.cumsum(kernel[:, latent], axis=0)).sum(axis=0)
    result = PrefixCounts(
        tuple(
            np.bincount(projection(c)[latent[stops == c]], minlength=projection(c).max() + 1)
            for c in range(HORIZON + 1)
        )
    )
    result.validate()
    return result


def stress_scores(prediction, truth, kernel):
    prediction = _probability(prediction, len(STATES))
    truth, kernel = _probability(truth, len(STATES)), _kernel(kernel)
    channel_kl, prefix_score_excess = 0.0, 0.0
    for c in range(HORIZON + 1):
        index = projection(c)
        observed_p = np.bincount(index, weights=prediction * kernel[c])
        observed_q = np.bincount(index, weights=truth * kernel[c])
        active = observed_q > 0
        channel_kl += float(
            observed_q[active] @ np.log(observed_q[active] / np.maximum(observed_p[active], 1e-300))
        )
        p_prefix = np.bincount(index, weights=prediction)
        q_prefix = np.bincount(index, weights=truth)
        prefix_score_excess += float(
            observed_q[active] @ np.log(q_prefix[active] / np.maximum(p_prefix[active], 1e-300))
        )
    both = np.all((STATES == 1).sum(axis=2) >= 2, axis=1)
    return dict(
        latent_joint_kl=float(
            truth @ np.log(np.maximum(truth, 1e-300) / np.maximum(prediction, 1e-300))
        ),
        observation_channel_kl=channel_kl,
        ignorability_score_excess=prefix_score_excess,
        both_repeat_probability_error=float((prediction - truth) @ both),
    )
