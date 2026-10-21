"""J007 conditional count emissions plus latent Markov dynamics, generated-only.

Combines known finite cardinality laws, Newton fitting and HMM EM. It does not
establish novelty, global HMM optimality, missing-history identification or causality.
"""

from itertools import product
from math import lgamma

import numpy as np

from ies.cardinality import count_distribution, sample_sets
from ies.history_roles import (
    BASE,
    HORIZON,
    PARITY,
    TERMINAL,
    GeneratedPath,
    fit_reference,
    forward_emissions,
    lse,
    terminal_score,
)
from ies.history_roles import (
    generate as generate_reference,
)

PARTITIONS = np.array([(1, *v) for v in product((-1, 1), repeat=3)], dtype=int)
SCENARIOS = ("independent", "history_fresh", "signed_capacity", "combined", "hidden_persistent")
LOWER = np.array([-8.0, -8.0, -8.0, -8.0, -8.0])
UPPER = np.array([8.0, 8.0, 8.0, 8.0, 0.0])


def validate_signs(signs):
    signs = np.asarray(signs)
    if signs.shape != (4,) or not np.isin(signs, [-1, 1]).all():
        raise ValueError("Invalid generated history partition")
    return signs.astype(int)


def features(success, trials, signs):
    signs = validate_signs(signs)
    success, trials = np.asarray(success, dtype=float), np.asarray(trials, dtype=float)
    if (
        success.shape != trials.shape
        or success.ndim != 2
        or success.shape[1] != 4
        or not np.isfinite(success).all()
        or not np.isfinite(trials).all()
        or np.any(success < 0)
        or np.any(success > trials)
        or np.any(trials < 0)
        or np.any(success != np.floor(success))
        or np.any(trials != np.floor(trials))
        or np.any(trials.sum(axis=1) > 128)
    ):
        raise ValueError("Invalid generated grouped events")
    contrast = ((success - trials / 2) @ signs) ** 2 / np.maximum(trials.sum(axis=1), 1)
    return np.column_stack([success, contrast])


def field_prior(params):
    b, theta = params[:4], params[4]
    p = 1 / (1 + np.exp(-b))
    value = np.sum(np.logaddexp(0, b) - 0.5 * b) + 0.05 * theta**2
    gradient = np.r_[p - 0.5, 0.1 * theta]
    hessian = np.diag(np.r_[p * (1 - p), 0.1])
    return value, gradient, hessian


class CountDesign:
    """Exact small-roster normalizers and weighted sufficient-statistic objective."""

    def __init__(self, contexts, signs):
        self.signs = validate_signs(signs)
        self.contexts = np.asarray(contexts)
        if (
            self.contexts.ndim != 2
            or self.contexts.shape[1] != 4
            or not 1 <= len(self.contexts) <= 495
            or self.contexts.dtype.kind not in "iu"
            or np.any(self.contexts < 0)
            or np.any(self.contexts.sum(axis=1) > 8)
        ):
            raise ValueError("Training enumeration is bounded to eight entities")
        rows, groups, multiplicity = [], [], []
        for c, counts in enumerate(self.contexts):
            y = np.array(list(product(*(range(n + 1) for n in counts))), dtype=int)
            rows.append(features(y, np.broadcast_to(counts, y.shape), self.signs))
            groups.extend([c] * len(y))
            multiplicity.extend(
                [
                    sum(
                        lgamma(n + 1) - lgamma(v + 1) - lgamma(n - v + 1)
                        for n, v in zip(counts, row, strict=True)
                    )
                    for row in y
                ]
            )
        self.x = np.concatenate(rows)
        self.groups = np.asarray(groups)
        self.multiplicity = np.asarray(multiplicity)
        self.groups_count = len(self.contexts)

    def distribution(self, params):
        logits = self.x @ params + self.multiplicity
        maximum = np.full(self.groups_count, -np.inf)
        np.maximum.at(maximum, self.groups, logits)
        mass = np.exp(logits - maximum[self.groups])
        total = np.bincount(self.groups, weights=mass, minlength=self.groups_count)
        return maximum + np.log(total), mass / total[self.groups]

    def objective(self, params, weights, derivatives=True):
        group_weights, target = [np.asarray(value, dtype=float) for value in weights]
        if (
            group_weights.shape != (self.groups_count,)
            or target.shape != (5,)
            or not np.isfinite(group_weights).all()
            or not np.isfinite(target).all()
            or np.any(group_weights < 0)
        ):
            raise ValueError("Invalid generated count sufficient statistics")
        scale = max(group_weights.sum(), 1)
        logz, probability = self.distribution(params)
        prior, pg, ph = field_prior(params)
        value = (group_weights @ logz - target @ params + prior) / scale
        if not derivatives:
            return value
        means = np.column_stack(
            [
                np.bincount(
                    self.groups, weights=probability * self.x[:, j], minlength=self.groups_count
                )
                for j in range(5)
            ]
        )
        gradient = (group_weights @ means - target + pg) / scale
        point_weights = probability * group_weights[self.groups]
        hessian = (
            self.x.T @ (point_weights[:, None] * self.x)
            - means.T @ (group_weights[:, None] * means)
            + ph
        ) / scale
        return value, gradient, (hessian + hessian.T) / 2


class GroupDesign(CountDesign):
    """Small-roster exact group-count design with labeled-pattern probabilities."""

    def __init__(self, data, signs):
        self.shape = data["lengths"].shape[0], HORIZON
        trials = data["trials"].reshape(-1, 4).astype(int)
        if len(trials) > 8192:
            raise ValueError("Training enumeration is bounded to eight entities")
        contexts, self.index = np.unique(trials, axis=0, return_inverse=True)
        super().__init__(contexts, signs)
        self.observed = features(data["success"].reshape(-1, 4), trials, self.signs)

    def emission(self, params):
        logz, _ = self.distribution(params)
        return (self.observed @ params - logz[self.index]).reshape(self.shape)

    def objective(self, params, weights, derivatives=True):
        weights = np.asarray(weights, dtype=float).reshape(-1)
        if (
            weights.shape != self.index.shape
            or not np.isfinite(weights).all()
            or np.any(weights < 0)
        ):
            raise ValueError("Invalid generated conditional weights")
        grouped = np.bincount(self.index, weights=weights, minlength=self.groups_count)
        return super().objective(params, (grouped, weights @ self.observed), derivatives)


def fit_emission(design, weights, initial):
    params = np.clip(np.asarray(initial, dtype=float), LOWER, UPPER)
    if params.shape != (5,) or not np.isfinite(params).all():
        raise ValueError("Invalid generated emission initialization")
    trace = []
    for iteration in range(81):
        value, gradient, hessian = design.objective(params, weights)
        trace.append(float(value))
        gap = float(gradient @ (params - np.where(gradient > 0, LOWER, UPPER)))
        if gap <= 2e-7:
            return params, dict(
                convex_gap=gap,
                iterations=iteration,
                objective=trace,
                competition_boundary=bool(params[4] < -8 + 1e-8 or params[4] > -1e-8),
            )
        if iteration == 80:
            break
        active = ((params <= LOWER + 1e-10) & (gradient > 0)) | (
            (params >= UPPER - 1e-10) & (gradient < 0)
        )
        # A coupled Newton direction can point outside a bound even when that
        # coordinate's gradient points inward. Freeze such coordinates while
        # solving the local quadratic; otherwise the feasible step is zero.
        for _ in range(6):
            free = ~active
            direction = np.zeros(5)
            direction[free] = -np.linalg.solve(hessian[np.ix_(free, free)], gradient[free])
            outward = ((params <= LOWER + 1e-10) & (direction < 0)) | (
                (params >= UPPER - 1e-10) & (direction > 0)
            )
            if not np.any(outward & free):
                break
            active |= outward
        if gradient @ direction >= -1e-15:
            direction = np.clip(params - gradient / np.diag(hessian), LOWER, UPPER) - params
        step = 1.0
        positive, negative = direction > 0, direction < 0
        if positive.any():
            step = min(
                step, float(np.min((UPPER[positive] - params[positive]) / direction[positive]))
            )
        if negative.any():
            step = min(
                step, float(np.min((LOWER[negative] - params[negative]) / direction[negative]))
            )
        for _ in range(45):
            proposal = np.clip(params + step * direction, LOWER, UPPER)
            next_value = design.objective(proposal, weights, derivatives=False)
            if next_value <= value + 1e-4 * gradient @ (proposal - params) + 1e-14:
                params = proposal
                break
            step *= 0.5
        else:
            raise RuntimeError("Generated convex emission line search failed")
    raise RuntimeError("Generated convex emission certificate failed")


def batch_log_normalizer(contexts, params, signs):
    """O(C*K^2) grouped log-polynomial DP, with no exponential outcome enumeration."""
    contexts = np.asarray(contexts)
    signs = validate_signs(signs)
    params = np.asarray(params, dtype=float)
    if (
        contexts.ndim != 2
        or contexts.shape[1] != 4
        or not 1 <= len(contexts) <= 32768
        or contexts.dtype.kind not in "iu"
        or np.any(contexts < 0)
        or np.any(contexts.sum(axis=1) > 128)
        or params.shape != (5,)
        or not np.isfinite(params).all()
        or np.any(params < LOWER)
        or np.any(params > UPPER)
    ):
        raise ValueError("Invalid bounded grouped normalizer")
    total = contexts.sum(axis=1)
    kmax = int(total.max())
    coefficient = np.full((len(contexts), kmax + 1), -np.inf)
    coefficient[:, 0] = 0
    for h in range(4):
        for j in range(int(contexts[:, h].max())):
            chosen = contexts[:, h] > j
            old = coefficient[chosen].copy()
            coefficient[chosen, 1:] = np.logaddexp(old[:, 1:], old[:, :-1] + signs[h] * params[h])
    potential = (
        params[4]
        * (np.arange(kmax + 1)[None] - total[:, None] / 2) ** 2
        / np.maximum(total[:, None], 1)
    )
    constant = contexts[:, signs < 0] @ params[:4][signs < 0]
    return constant + lse(coefficient + potential)


def count_emissions(data, model):
    trials = data["trials"].reshape(-1, 4).astype(int)
    contexts, index = np.unique(trials, axis=0, return_inverse=True)
    x = features(data["success"].reshape(-1, 4), trials, model["signs"])
    return np.stack(
        [
            (x @ params - batch_log_normalizer(contexts, params, model["signs"])[index]).reshape(
                len(data["lengths"]), HORIZON
            )
            for params in model["parameters"]
        ],
        axis=2,
    )


def score(data, model):
    return forward_emissions(
        count_emissions(data, model), model["initial"], model["transition"], data["lengths"]
    ) + terminal_score(data, model["terminal"])


def _prior(model):
    return (
        -sum(field_prior(p)[0] for p in model["parameters"])
        + 0.5 * np.log(model["initial"]).sum()
        + 0.5 * np.log(model["transition"]).sum()
    )


def fit_competition(data, learned_hmm, iterations=20, partitions=PARTITIONS):
    if type(iterations) is not int or not 1 <= iterations <= 30:
        raise ValueError("Invalid bounded joint EM iterations")
    candidates, diagnostics = [], []
    for signs in partitions:
        design = GroupDesign(data, signs)
        p = learned_hmm["probability"]
        parameters = np.column_stack([np.log(p) - np.log1p(-p), np.zeros(2)])
        model = dict(
            parameters=np.clip(parameters, LOWER, UPPER),
            signs=validate_signs(signs),
            initial=learned_hmm["initial"].copy(),
            transition=learned_hmm["transition"].copy(),
            terminal=learned_hmm["terminal"].copy(),
        )
        trace, certificates = [], []
        for iteration in range(iterations + 1):
            e = np.stack([design.emission(p) for p in model["parameters"]], axis=2)
            likelihood, gamma, xi = forward_emissions(
                e, model["initial"], model["transition"], data["lengths"], posterior=True
            )
            trace.append(float(likelihood.sum() + _prior(model)))
            if iteration == iterations:
                break
            for z in range(2):
                model["parameters"][z], diagnostic = fit_emission(
                    design, gamma[:, :, z], model["parameters"][z]
                )
                certificates.append({k: v for k, v in diagnostic.items() if k != "objective"})
            counts = xi.sum(axis=(0, 1)) + 0.5
            model["transition"] = counts / counts.sum(axis=1, keepdims=True)
            counts = gamma[:, 0].sum(axis=0) + 0.5
            model["initial"] = counts / counts.sum()
        if min(np.diff(trace)) < -1e-6:
            raise RuntimeError("Generated joint EM objective decreased")
        candidates.append(model)
        diagnostics.append(dict(signs=list(map(int, signs)), objective=trace, msteps=certificates))
    best = int(np.argmax([d["objective"][-1] for d in diagnostics]))
    return candidates[best], dict(
        selected_partition=best, partitions=diagnostics, global_optimum_claimed=False
    )


def fit_single(data, partitions=PARTITIONS):
    reference = fit_reference(data)
    p = reference["probability"]
    initial = np.r_[np.log(p) - np.log1p(-p), 0.0]
    weights = (np.arange(HORIZON)[None] < data["lengths"][:, None]).astype(float)
    candidates, diagnostics = [], []
    for signs in partitions:
        design = GroupDesign(data, signs)
        params, diagnostic = fit_emission(design, weights, initial)
        candidates.append(
            dict(
                parameters=np.stack([params, params]),
                signs=validate_signs(signs),
                initial=np.array([0.5, 0.5]),
                transition=np.full((2, 2), 0.5),
                terminal=reference["terminal"],
            )
        )
        diagnostics.append(diagnostic)
    best = int(np.argmin([d["objective"][-1] for d in diagnostics]))
    return candidates[best], dict(selected_partition=best, partitions=diagnostics)


def generate(scenario, patients, rosters, seed, policy="complete"):
    if scenario not in SCENARIOS:
        raise ValueError("Invalid generated joint-dependence scenario")
    if scenario not in ("signed_capacity", "combined"):
        return generate_reference(scenario, patients, rosters, seed, policy)
    # Reuse the reference generator's validation before constructing a different law.
    generate_reference("independent", 1, rosters, seed, policy)
    if type(patients) is not int or not 1 <= patients <= 4096:
        raise ValueError("Invalid generated subject bound")
    paths = []
    for i in range(patients):
        rng = np.random.default_rng(np.random.SeedSequence([seed, i, 0]))
        stop = np.random.default_rng(np.random.SeedSequence([seed, i, 1]))
        k = rosters[i % len(rosters)]
        initial = rng.integers(0, 4, k)
        history, alive = initial.copy(), np.ones(k, dtype=bool)
        state = rng.choice([-1, 1])
        rows = []
        for t in range(HORIZON):
            if policy == "adaptive" and t >= 2:
                rate = float((history[alive] % 2).mean()) if alive.any() else 0.0
                if stop.random() < 0.12 + 0.25 * rate:
                    break
            if t and rng.random() < 0.075:
                state *= -1
            row = np.full(k, -1, dtype=int)
            row[alive] = 0
            terminal = alive & (rng.random(k) < TERMINAL[history])
            row[terminal] = 2
            survivor = alive & ~terminal
            h = history[survivor]
            b = np.log(BASE[h]) - np.log1p(-BASE[h])
            signs = PARITY[h] if scenario == "signed_capacity" else np.ones(len(h))
            if scenario == "combined":
                b += 0.8 * state * PARITY[h]
            m = len(h)
            law = count_distribution(signs * b, -4 * (np.arange(m + 1) - m / 2) ** 2 / max(m, 1))
            signed_y = sample_sets(law, 1, rng)[0]
            y = np.where(signs > 0, signed_y, 1 - signed_y)
            row[survivor] = y
            rows.append(row)
            history[survivor] = 2 * (history[survivor] % 2) + y
            alive = survivor
        paths.append(GeneratedPath(initial, np.array(rows, dtype=int)))
    return paths


def forecast(prefix, model, samples, seed, horizon=HORIZON):
    """Sample a conditional future from a fully observed roster prefix.

    Filtering uses only supplied past transitions. Already terminated entities stay
    inactive; unknown future terminals are sampled, not supplied as conditioning.
    This is not an adapter for missing entities, unseen history states, or clinical data.
    """
    from ies.history_roles import pack, validate_path

    history, observed = validate_path(prefix)
    parameters = np.asarray(model["parameters"], dtype=float)
    signs = validate_signs(model["signs"])
    terminal = np.asarray(model["terminal"], dtype=float)
    if (
        type(samples) is not int
        or not 1 <= samples <= 10_000
        or type(horizon) is not int
        or not 1 <= horizon <= HORIZON
        or samples * horizon * len(history) > 1_000_000
        or type(seed) is not int
        or not 0 <= seed < 2**32
        or parameters.shape != (2, 5)
        or not np.isfinite(parameters).all()
        or np.any(parameters < LOWER)
        or np.any(parameters > UPPER)
        or terminal.shape != (4,)
        or not np.isfinite(terminal).all()
        or np.any((terminal <= 0) | (terminal >= 1))
    ):
        raise ValueError("Invalid bounded generated forecast")
    data = pack([prefix])
    _, gamma, _ = forward_emissions(
        count_emissions(data, model),
        model["initial"],
        model["transition"],
        data["lengths"],
        posterior=True,
    )
    initial = (
        gamma[0, len(observed) - 1] @ model["transition"]
        if len(observed)
        else np.asarray(model["initial"])
    )
    alive = np.ones(len(history), dtype=bool)
    for row in observed:
        active = (row == 0) | (row == 1)
        history[active] = 2 * (history[active] % 2) + row[active]
        alive &= row != 2
    rng = np.random.default_rng(seed)
    future = np.full((samples, horizon, len(history)), -1, dtype=np.int8)
    for sample in range(samples):
        current_history, current_alive = history.copy(), alive.copy()
        z = rng.choice(2, p=initial)
        for t in range(horizon):
            if t:
                z = rng.choice(2, p=model["transition"][z])
            terminated = current_alive & (rng.random(len(history)) < terminal[current_history])
            future[sample, t, current_alive] = 0
            future[sample, t, terminated] = 2
            survivor = current_alive & ~terminated
            h = current_history[survivor]
            k = len(h)
            b, theta = parameters[z, :4], parameters[z, 4]
            law = count_distribution(
                signs[h] * b[h], theta * (np.arange(k + 1) - k / 2) ** 2 / max(k, 1)
            )
            signed_y = sample_sets(law, 1, rng)[0]
            y = np.where(signs[h] > 0, signed_y, 1 - signed_y)
            future[sample, t, survivor] = y
            current_history[survivor] = 2 * (current_history[survivor] % 2) + y
            current_alive = survivor
    return dict(
        events=future,
        next_latent_probability=initial.copy(),
        histories_at_cutoff=history,
        alive_at_cutoff=alive,
        data_class="synthetic",
    )
