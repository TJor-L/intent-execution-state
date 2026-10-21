"""Generated exact adjoints and likelihood derivatives of J011's fixed law.

Uses ordinary reverse-mode differentiation/forward-backward identities. This is
not a new differentiation theorem, an optimizer, or a clinical learner.
"""

import numpy as np

from ies.factored_history import FactoredFilter, binomial_table
from ies.history_roles import validate_path


def _axis_contract(matrix, value, axis):
    return np.moveaxis(np.tensordot(matrix, value, axes=(1, axis)), 0, axis)


def _pair_derivatives(size, first, second):
    tables = [binomial_table(size, p) for p in (first, second)]
    rows, columns = np.indices((size + 1, size + 1))
    derivatives = [
        table * (rows - columns * p) for table, p in zip(tables, (first, second), strict=True)
    ]
    output = []
    for which in range(2):
        a, b = (derivatives[0], tables[1]) if which == 0 else (tables[0], derivatives[1])
        output.append(
            tuple(
                np.column_stack(
                    [np.convolve(a[: x + 1, x], b[: n - x + 1, n - x]) for x in range(n + 1)]
                )
                for n in range(size + 1)
            )
        )
    return tuple(output)


def _tilt_value_gradient(plan, observed, probability, theta):
    """Layered polynomial derivatives in four field logits and theta."""
    base, derivative = np.array([1.0]), np.zeros((4, 1))
    for h, n in enumerate(observed):
        p = probability[h]
        for _ in range(int(n)):
            following = np.array([np.convolve(d, [1 - p, p]) for d in derivative])
            following[h] += np.convolve(base, [-p * (1 - p), p * (1 - p)])
            base = np.convolve(base, [1 - p, p])
            derivative = following
    previous, gradient = base[None], derivative[None]
    values, gradients = [], []
    for n in range(len(plan["layers"])):
        if n:
            selected = previous[plan["parents"][n]]
            dselected = gradient[plan["parents"][n]]
            category = plan["categories"][n]
            p = probability[category][:, None]
            following = np.zeros((len(selected), selected.shape[1] + 1))
            following[:, :-1] = selected * (1 - p)
            following[:, 1:] += selected * p
            dg = np.zeros((len(selected), 4, selected.shape[1] + 1))
            dg[:, :, :-1] = dselected * (1 - p[:, None])
            dg[:, :, 1:] += dselected * p[:, None]
            direct = selected * p * (1 - p)
            rows = np.arange(len(selected))
            dg[rows, category, :-1] -= direct
            dg[rows, category, 1:] += direct
            previous, gradient = following, dg
        k = int(observed.sum()) + n
        phi = (np.arange(k + 1) - k / 2) ** 2 / max(k, 1)
        potential = np.exp(theta * phi)
        values.append(previous @ potential)
        gradients.append(np.column_stack([gradient @ potential, previous @ (potential * phi)]))
    return np.concatenate(values), np.concatenate(gradients)


class DifferentiableFilter(FactoredFilter):
    """Model-specific factored forward/backward; no compound-edge materialization."""

    def __init__(self, missing, model):
        super().__init__(missing, model)
        self.deven = tuple(_pair_derivatives(missing, p[0], p[2]) for p in self.probability)
        self.dodd = tuple(_pair_derivatives(missing, p[1], p[3]) for p in self.probability)
        rows, columns = np.indices((missing + 1, missing + 1))
        self.dthinning = tuple(
            table * (columns * (1 - q) - rows)
            for table, q in zip(self.thinning, self.terminal, strict=True)
        )

    def step_pullback(self, predictive, cotangent, observed_trials, observed_success):
        """Adjoint wrt input mass, emission fields/theta, and terminal logits.

        Observed Bernoulli and terminal constants are excluded, as in step().
        Cotangents may be signed; primal mass must be nonnegative and supported.
        """
        shape = self.plan["shape"] + (2,)
        trials, success = np.asarray(observed_trials), np.asarray(observed_success)
        if (
            predictive.shape != shape
            or cotangent.shape != shape
            or not np.isfinite(predictive).all()
            or not np.isfinite(cotangent).all()
            or np.any(predictive < 0)
            or trials.shape != (4,)
            or success.shape != (4,)
            or trials.dtype.kind not in "iu"
            or success.dtype.kind not in "iu"
            or np.any(trials < 0)
            or np.any(trials > 128)
            or np.any(success < 0)
            or np.any(success > trials)
            or trials.sum() + self.missing > 128
        ):
            raise ValueError("Invalid generated factored pullback inputs")
        stages = [predictive]
        for h, transform in enumerate(self.thinning):
            stages.append(_axis_contract(transform, stages[-1], h))
        thinned_gradient = np.zeros_like(predictive)
        parameters_gradient = np.zeros((2, 5))
        for z in range(2):
            normalizer, derivative = _tilt_value_gradient(
                self.plan, trials, self.probability[z], self.parameters[z, 4]
            )
            if not np.isfinite(normalizer).all() or np.any(normalizer <= 0):
                raise RuntimeError("Generated derivative normalizer lost support")
            weighted = np.zeros(self.plan["shape"])
            weighted[self.indices] = stages[-1][self.indices + (z,)] / normalizer
            weighted_gradient = np.zeros(self.plan["shape"])
            for total, a, b, source, target, events in self.blocks:
                k = int(trials.sum()) + total
                phi = (events + success.sum() - k / 2) ** 2 / max(k, 1)
                adjoint = cotangent[target + (z,)] * np.exp(self.parameters[z, 4] * phi)
                even, odd = self.even[z][a], self.odd[z][b]
                value = weighted[source]
                weighted_gradient[source] = even.T @ adjoint @ odd
                parameters_gradient[z, 4] += np.sum(adjoint * (even @ value @ odd.T) * phi)
                for h, derivative_matrix in (
                    (0, self.deven[z][0][a]),
                    (2, self.deven[z][1][a]),
                ):
                    parameters_gradient[z, h] += np.sum(
                        adjoint * (derivative_matrix @ value @ odd.T)
                    )
                for h, derivative_matrix in (
                    (1, self.dodd[z][0][b]),
                    (3, self.dodd[z][1][b]),
                ):
                    parameters_gradient[z, h] += np.sum(
                        adjoint * (even @ value @ derivative_matrix.T)
                    )
            weights = weighted_gradient[self.indices] * weighted[self.indices]
            parameters_gradient[z] -= weights @ (derivative / normalizer[:, None])
            thinned_gradient[self.indices + (z,)] = weighted_gradient[self.indices] / normalizer
        terminal_gradient = np.zeros(4)
        mass_gradient = thinned_gradient
        for h in reversed(range(4)):
            terminal_gradient[h] = np.sum(
                mass_gradient * _axis_contract(self.dthinning[h], stages[h], h)
            )
            mass_gradient = _axis_contract(self.thinning[h].T, mass_gradient, h)
        if not all(
            np.isfinite(v).all() for v in (mass_gradient, parameters_gradient, terminal_gradient)
        ):
            raise RuntimeError("Generated factored pullback lost finite derivatives")
        return mass_gradient, parameters_gradient, terminal_gradient

    def likelihood_gradient(self, observed, missing_initial):
        filtered = self.filter(observed, missing_initial)
        history, events = validate_path(observed)
        contexts = []
        alive = np.ones(len(history), dtype=bool)
        for row in events:
            survivor = alive & (row != 2)
            contexts.append(
                (
                    np.bincount(history[survivor], minlength=4),
                    np.bincount(history[row == 1], minlength=4),
                    np.bincount(history[row == 2], minlength=4),
                )
            )
            history[survivor] = 2 * (history[survivor] % 2) + row[survivor]
            alive = survivor
        first = tuple(np.bincount(missing_initial, minlength=4))
        shape = self.plan["shape"] + (2,)
        beta = np.ones(shape)
        parameter_gradient, terminal_gradient = np.zeros((2, 5)), np.zeros(4)
        initial_counts, transition_counts = np.zeros(2), np.zeros((2, 2))
        smoothed = [None] * len(events)
        for t in reversed(range(len(events))):
            alpha = filtered["posteriors"][t]
            smooth = alpha * beta[self.indices]
            if not np.isfinite(smooth).all() or abs(smooth.sum() - 1) > 1e-8:
                raise RuntimeError("Generated factored smoothed posterior did not normalize")
            smoothed[t] = smooth
            trials, success, dead = contexts[t]
            observed_logp = np.log(self.probability) @ success + np.log1p(-self.probability) @ (
                trials - success
            )
            terminal_logp = dead @ np.log(self.terminal) + trials @ np.log1p(-self.terminal)
            shift = float(observed_logp.max())
            scale = np.exp(filtered["log_increments"][t] - shift - terminal_logp)
            before = np.zeros(shape)
            if t:
                before[self.indices] = filtered["posteriors"][t - 1] @ self.transition
            else:
                before[first] = self.initial
            cotangent = beta * np.exp(observed_logp - shift) / scale
            mass_gradient, dp, dq = self.step_pullback(before, cotangent, trials, success)
            parameter_gradient += dp
            parameter_gradient[:, :4] += smooth.sum(axis=0)[:, None] * (
                success - self.probability * trials
            )
            terminal_gradient += dq + dead - (dead + trials) * self.terminal
            if t:
                transition_counts += np.einsum(
                    "hz,zq,hq->zq",
                    filtered["posteriors"][t - 1],
                    self.transition,
                    mass_gradient[self.indices],
                )
                beta = mass_gradient @ self.transition.T
            else:
                initial_counts = self.initial * mass_gradient[first]
        gradient = dict(
            parameters=parameter_gradient,
            terminal_logits=terminal_gradient,
            initial_logits=initial_counts - (self.initial if len(events) else 0),
            transition_logits=transition_counts
            - transition_counts.sum(axis=1, keepdims=True) * self.transition,
        )
        if not all(np.isfinite(v).all() for v in gradient.values()):
            raise RuntimeError("Generated factored likelihood derivatives are not finite")
        return dict(
            data_class="synthetic",
            log_probability=filtered["log_probability"],
            gradient=gradient,
            smoothed_histograms=np.array(smoothed).reshape(len(events), len(self.indices[0]), 2),
            histogram_states=filtered["histogram_states"],
            initial=initial_counts,
            transition=transition_counts,
            compound_transition_terms_materialized=0,
        )


def perturb(model, direction, amount):
    """Perturb generated parameters and probability-simplex logits for verification."""
    if not np.isfinite(amount):
        raise ValueError("Finite generated parameter perturbation required")
    result = {k: np.array(v, copy=True) for k, v in model.items()}
    result["parameters"] = result["parameters"] + amount * direction["parameters"]
    q = result["terminal"]
    logit = np.log(q) - np.log1p(-q) + amount * direction["terminal_logits"]
    result["terminal"] = 1 / (1 + np.exp(-logit))
    for name in ("initial", "transition"):
        logits = np.log(result[name]) + amount * direction[name + "_logits"]
        probability = np.exp(logits - logits.max(axis=-1, keepdims=True))
        result[name] = probability / probability.sum(axis=-1, keepdims=True)
    return result
