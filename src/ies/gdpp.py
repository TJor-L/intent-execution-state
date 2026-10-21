"""Known cardinality-weighted DPP probability references, generated only.

Sharghi et al., ECCV 2018, Eq. 12. J009 count emissions are a diagonal-kernel
special case. This module supplies probabilities, not a new fitting algorithm.
"""

import numpy as np

from ies.competition import LOWER, UPPER
from ies.hidden_history import filter_missing, validate_model
from ies.history_roles import forward_emissions, lse, terminal_score


def spectral_law(eigenvalues, log_cardinality):
    eigenvalues = np.asarray(eigenvalues, dtype=float)
    log_cardinality = np.asarray(log_cardinality, dtype=float)
    k = len(eigenvalues) if eigenvalues.ndim == 1 else -1
    if (
        not 0 <= k <= 128
        or not np.isfinite(eigenvalues).all()
        or np.any((eigenvalues <= 0) | (eigenvalues > 1e6))
        or log_cardinality.shape != (k + 1,)
        or np.isnan(log_cardinality).any()
        or np.isposinf(log_cardinality).any()
        or not np.isfinite(log_cardinality).any()
        or np.any(np.abs(log_cardinality[np.isfinite(log_cardinality)]) > 1e6)
    ):
        raise ValueError("Invalid bounded generated GDPP spectrum or cardinality weights")
    coefficients = np.full(k + 1, -np.inf)
    coefficients[0] = 0
    for i, value in enumerate(np.log(eigenvalues)):
        coefficients[1 : i + 2] = np.logaddexp(
            coefficients[1 : i + 2], coefficients[: i + 1] + value
        )
    normalizer = float(lse(coefficients + log_cardinality))
    return dict(
        log_coefficients=coefficients,
        log_normalizer=normalizer,
        cardinality_probability=np.exp(coefficients + log_cardinality - normalizer),
    )


def law(kernel, log_cardinality):
    kernel = np.asarray(kernel, dtype=float)
    if (
        kernel.ndim != 2
        or kernel.shape[0] != kernel.shape[1]
        or len(kernel) > 128
        or not np.isfinite(kernel).all()
        or not np.allclose(kernel, kernel.T, rtol=0, atol=1e-12)
    ):
        raise ValueError("Generated symmetric positive definite GDPP kernel required")
    result = spectral_law(np.linalg.eigvalsh(kernel), log_cardinality)
    return result | dict(kernel=kernel.copy(), log_cardinality=np.asarray(log_cardinality).copy())


def log_probability(distribution, outcomes):
    outcomes = np.asarray(outcomes)
    kernel = distribution["kernel"]
    if (
        outcomes.ndim != 2
        or outcomes.shape[1] != len(kernel)
        or not 1 <= len(outcomes) <= 4096
        or not np.isin(outcomes, [0, 1]).all()
    ):
        raise ValueError("Bounded generated GDPP binary patterns required")
    result = []
    for outcome in outcomes:
        selected = np.flatnonzero(outcome)
        sign, logdet = np.linalg.slogdet(kernel[np.ix_(selected, selected)])
        if sign <= 0:
            raise ValueError("Generated GDPP selected minor is not positive")
        result.append(
            logdet + distribution["log_cardinality"][len(selected)] - distribution["log_normalizer"]
        )
    return np.array(result)


def validate_parameters(parameters, factor):
    parameters, factor = np.asarray(parameters, dtype=float), np.asarray(factor, dtype=float)
    if (
        parameters.shape != (5,)
        or not np.isfinite(parameters).all()
        or np.any(parameters < LOWER)
        or np.any(parameters > UPPER)
        or factor.shape != (4, 4)
        or not np.isfinite(factor).all()
        or np.any(np.abs(factor) > 4)
    ):
        raise ValueError("Invalid bounded generated history-GDPP parameters")
    return parameters, factor


def validate_counts(counts):
    counts = np.asarray(counts)
    if (
        counts.ndim != 2
        or counts.shape[1] != 4
        or not 1 <= len(counts) <= 100_000
        or counts.dtype.kind not in "iu"
        or np.any(counts < 0)
        or np.any(counts > 128)
        or np.any(counts.sum(axis=1) > 128)
    ):
        raise ValueError("Invalid bounded generated history counts")
    return counts


def history_kernel(histories, parameters, factor):
    parameters, factor = validate_parameters(parameters, factor)
    histories = np.asarray(histories)
    if (
        histories.ndim != 1
        or histories.dtype.kind not in "iu"
        or len(histories) > 128
        or not np.isin(histories, range(4)).all()
    ):
        raise ValueError("Known generated histories required for GDPP kernel")
    rows = factor[histories]
    return np.diag(np.exp(parameters[histories])) + rows @ rows.T


def log_minor(counts, parameters, factor, gradient=False):
    """Determinant lemma for repeated-history selected entities; optionally d/db,d/dR."""
    counts = validate_counts(counts)
    parameters, factor = validate_parameters(parameters, factor)
    scaled = counts * np.exp(-parameters[:4])
    block = np.eye(4)[None] + np.einsum("hi,nh,hj->nij", factor, scaled, factor)
    sign, determinant = np.linalg.slogdet(block)
    if np.any(sign <= 0):
        raise RuntimeError("Generated GDPP determinant reduction lost positivity")
    value = counts @ parameters[:4] + determinant
    if not gradient:
        return value
    inverse = np.linalg.inv(block)
    right = np.einsum("hi,nij->nhj", factor, inverse)
    field_gradient = counts - scaled * np.einsum("nhi,hi->nh", right, factor)
    factor_gradient = 2 * scaled[:, :, None] * right
    return value, field_gradient, factor_gradient


def history_normalizer(contexts, parameters, factor):
    contexts = validate_counts(contexts)
    parameters, factor = validate_parameters(parameters, factor)
    diagonal, interaction = np.exp(parameters[:4]), factor @ factor.T
    result = []
    for counts in contexts:
        active = np.flatnonzero(counts)
        scale = np.sqrt(counts[active])
        block = (
            np.diag(diagonal[active])
            + interaction[np.ix_(active, active)] * scale[:, None] * scale[None]
        )
        repeated = np.repeat(diagonal[active], counts[active] - 1)
        eigenvalues = np.r_[repeated, np.linalg.eigvalsh(block)]
        k = int(counts.sum())
        potential = parameters[4] * (np.arange(k + 1) - k / 2) ** 2 / max(k, 1)
        result.append(spectral_law(eigenvalues, potential)["log_normalizer"])
    return np.array(result)


def history_log_probability(success, trials, parameters, factor):
    parameters, factor = validate_parameters(parameters, factor)
    success, trials = validate_counts(success), validate_counts(trials)
    if success.shape != trials.shape or np.any(success > trials):
        raise ValueError("Invalid generated GDPP successes and survivor counts")
    contexts, index = np.unique(trials, axis=0, return_inverse=True)
    total = trials.sum(axis=1)
    potential = parameters[4] * (success.sum(axis=1) - total / 2) ** 2 / np.maximum(total, 1)
    return (
        log_minor(success, parameters, factor)
        + potential
        - history_normalizer(contexts, parameters, factor)[index]
    )


def validate_history_model(model):
    validate_model(model)
    factors = np.asarray(model["factors"], dtype=float)
    if not np.array_equal(model["signs"], np.ones(4)) or factors.shape != (2, 4, 4):
        raise ValueError("Generated GDPP reference requires unsigned event cardinality")
    for p, r in zip(model["parameters"], factors, strict=True):
        validate_parameters(p, r)


def emissions(success, trials, model):
    validate_history_model(model)
    return np.column_stack(
        [
            history_log_probability(success, trials, p, r)
            for p, r in zip(model["parameters"], model["factors"], strict=True)
        ]
    )


def score(data, model):
    values = emissions(
        data["success"].reshape(-1, 4).astype(int), data["trials"].reshape(-1, 4).astype(int), model
    )
    values = values.reshape(len(data["lengths"]), -1, 2)
    return forward_emissions(
        values, model["initial"], model["transition"], data["lengths"]
    ) + terminal_score(data, model["terminal"])


def filter_history(observed, missing_initial, model):
    validate_history_model(model)
    return filter_missing(
        observed,
        missing_initial,
        model,
        emission=lambda success, trials: emissions(success, trials, model),
    )
