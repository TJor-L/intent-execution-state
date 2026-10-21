"""Convex generated-path likelihood with smooth interaction-group penalties.

This finite solver studies the J003 estimator design. Convex regularized likelihood,
group norms and constrained Newton steps are established methods; no novelty or
statistical superiority is claimed. Observed prefixes are the only fitting inputs.
"""

import numpy as np

from ies.joint_observation import (
    HORIZON,
    PAIRS,
    PATHS,
    STATES,
    PrefixCounts,
    _probability,
    fit_independent,
    observed_nll,
    projection,
)
from ies.joint_shrinkage import split_counts, tree_basis, tree_shrink_fit


class JointObjective:
    """A fixed, strictly convex objective on the positive probability simplex.

    L(p) = observed-prefix NLL + tau/n KL(reference || p)
           + strength * sum_g w_g (sqrt(||Z_g.T(p-reference)||^2 + delta^2) - delta).

    The reference and basis are frozen during optimization. All marginals may change.
    Weights reflect independent common-window information; under adaptive stopping the
    likelihood may remain ignorable, but these weights are only a heuristic.
    """

    def __init__(
        self,
        observed: PrefixCounts,
        reference,
        grouping: str,
        strength: float,
        prior_mass: float = 1.0,
        smoothing: float = 0.001,
    ):
        observed.validate()
        reference = _probability(reference, len(STATES))
        if (
            np.any(reference <= 0)
            or grouping not in {"global", "reveal"}
            or not np.isfinite([strength, prior_mass, smoothing]).all()
            or not 0 <= strength <= 8
            or not 0 < prior_mass <= 100
            or not 1e-5 <= smoothing <= 0.1
        ):
            raise ValueError("Invalid generated likelihood objective")
        matrix = reference.reshape(len(PATHS), len(PATHS))
        a, b = matrix.sum(axis=1), matrix.sum(axis=0)
        if not np.allclose(matrix, np.outer(a, b), atol=1e-12, rtol=0):
            raise ValueError("Factorized generated reference required")
        self.reference = reference.copy()
        self.patients = observed.patients
        self.prior_scale = prior_mass / self.patients
        self.smoothing = smoothing
        self.strength = strength
        self.maps = [projection(c) for c in range(HORIZON + 1)]
        self.counts = [count.astype(float) / self.patients for count in observed.counts]
        self.same_cell = [index[:, None] == index[None, :] for index in self.maps]
        u, du = tree_basis(a)
        v, dv = tree_basis(b)
        features = (u[PAIRS[:, 0], :, None] * v[PAIRS[:, 1], None, :]).reshape(len(STATES), -1)
        reveal = np.maximum(du[:, None], dv[None, :]).ravel()
        survival = np.asarray(
            [
                sum(int(count.sum()) for count in observed.counts[d:]) / self.patients
                for d in range(HORIZON + 1)
            ]
        )
        groups = (
            [np.ones_like(reveal, dtype=bool)]
            if grouping == "global"
            else [reveal == d for d in range(1, HORIZON + 1)]
        )
        self.blocks = []
        for selected in groups:
            z = features[:, selected]
            weight = np.sqrt(np.sum(survival[reveal[selected]]) / self.patients)
            self.blocks.append((z, z @ z.T, float(weight)))
        self.observed_fraction_by_depth = survival.tolist()

    def evaluate(self, probability, *, hessian: bool = False):
        p = _probability(probability, len(STATES))
        if np.any(p <= 0):
            raise ValueError("Positive generated probability required")
        value = self.prior_scale * float(self.reference @ np.log(self.reference / p))
        gradient = -self.prior_scale * self.reference / p
        second = np.diag(self.prior_scale * self.reference / p**2) if hessian else None
        for index, count, same in zip(self.maps, self.counts, self.same_cell, strict=True):
            mass = np.bincount(index, weights=p)
            value -= float(count @ np.log(mass))
            gradient -= (count / mass)[index]
            if hessian:
                second += (count / mass**2)[index, None] * same
        for z, gram, weight in self.blocks:
            if self.strength * weight == 0:
                continue
            coefficient = z.T @ (p - self.reference)
            radius = np.sqrt(coefficient @ coefficient + self.smoothing**2)
            direction = z @ coefficient
            value += self.strength * weight * (radius - self.smoothing)
            gradient += self.strength * weight * direction / radius
            if hessian:
                second += (
                    self.strength
                    * weight
                    * (gram / radius - np.outer(direction, direction) / radius**3)
                )
        return float(value), gradient, second


def minimize_objective(objective: JointObjective, *, max_steps: int = 100, tolerance: float = 1e-7):
    """Equality-constrained damped Newton with positivity and an explicit convex gap.

    The gap g.p - min(g) upper-bounds the objective error on the simplex by convexity.
    It is numerical optimization evidence only, not a prediction-risk guarantee.
    Iteration/line-search failures are returned explicitly and never called convergence.
    """
    if (
        type(max_steps) is not int
        or not 1 <= max_steps <= 200
        or not np.isfinite(tolerance)
        or not 1e-10 <= tolerance <= 1e-3
    ):
        raise ValueError("Invalid generated solver bounds")
    p = objective.reference.copy()
    initial, _, _ = objective.evaluate(p)
    status, backtracks, iterations = "iteration_limit", 0, 0
    trace = [initial]
    for iteration in range(max_steps):
        value, gradient, hessian = objective.evaluate(p, hessian=True)
        gap = max(0.0, float(gradient @ p - gradient.min()))
        if gap <= tolerance:
            status = "converged"
            break
        # Whiten probability coordinates before the two right-hand-side KKT solve.
        root = np.sqrt(p)
        scaled = root[:, None] * hessian * root[None, :]
        solutions = np.linalg.solve(scaled, np.column_stack([root * gradient, root]))
        descent, constraint = solutions.T
        multiplier = (root @ descent) / (root @ constraint)
        direction = -root * (descent - multiplier * constraint)
        direction -= p * direction.sum()
        slope = float(gradient @ direction)
        if not np.isfinite(direction).all() or slope >= 0:
            status = "no_descent"
            break
        negative = direction < 0
        step = (
            min(1.0, float(np.min(-0.99 * p[negative] / direction[negative])))
            if negative.any()
            else 1.0
        )
        accepted = False
        for _attempt in range(40):
            proposal = p + step * direction
            proposal /= proposal.sum()
            if np.min(proposal) > 0:
                candidate_value, _, _ = objective.evaluate(proposal)
                if candidate_value <= value + 0.01 * step * slope + 1e-14:
                    accepted = True
                    break
            step *= 0.5
        backtracks += _attempt
        if not accepted:
            status = "line_search_limit"
            break
        p = proposal
        iterations = iteration + 1
        trace.append(candidate_value)
    value, gradient, _ = objective.evaluate(p)
    gap = max(0.0, float(gradient @ p - gradient.min()))
    if gap <= tolerance:
        status = "converged"
    return p, dict(
        status=status,
        converged=status == "converged",
        iterations=iterations,
        backtracks=backtracks,
        initial_objective=initial,
        final_objective=value,
        simplex_dual_gap=gap,
        tolerance=tolerance,
        minimum_probability=float(p.min()),
        probability_sum=float(p.sum()),
        objective_trace=trace,
    )


def fit_likelihood(observed: PrefixCounts, grouping: str, strength: float, *, em_steps: int = 300):
    reference = fit_independent(observed, em_steps)
    objective = JointObjective(observed, reference, grouping, strength)
    prediction, diagnostic = minimize_objective(objective)
    diagnostic.update(
        grouping=grouping,
        penalty_strength=strength,
        prior_mass=1.0,
        smoothing=0.001,
        observed_fraction_by_depth=objective.observed_fraction_by_depth,
        marginals_fixed=False,
        postfit_contraction=False,
    )
    if not diagnostic["converged"]:
        raise RuntimeError("Generated convex solver did not certify convergence")
    return prediction, diagnostic


def _cv_parts(observed, seed, em_steps):
    left, right = split_counts(observed, seed)
    return [
        (left, right, fit_independent(left, em_steps)),
        (right, left, fit_independent(right, em_steps)),
    ]


def select_likelihood(observed: PrefixCounts, grouping: str, seed: int, *, em_steps: int = 300):
    """Two-fold selection with all nuisance/reference fitting inside each fit fold.

    Candidates are the independent reference and strengths 0.25, 1, 4. No true law,
    stopping kernel, latent outcomes or evaluation metric is available to selection.
    """
    folds = _cv_parts(observed, seed, em_steps)
    strengths = (None, 0.25, 1.0, 4.0)
    losses, fits = [], []
    for strength in strengths:
        loss = 0.0
        for fold_index, (train, validation, reference) in enumerate(folds):
            if strength is None:
                probability = reference
            else:
                objective = JointObjective(train, reference, grouping, strength)
                probability, diagnostic = minimize_objective(objective)
                if not diagnostic["converged"]:
                    raise RuntimeError("Generated CV solver did not certify convergence")
                fits.append(
                    dict(
                        fold=fold_index,
                        strength=strength,
                        fit_patients=train.patients,
                        iterations=diagnostic["iterations"],
                        dual_gap=diagnostic["simplex_dual_gap"],
                    )
                )
            loss += validation.patients * observed_nll(probability, validation)
        losses.append(loss / observed.patients)
    selected = strengths[int(np.argmin(losses))]
    if selected is None:
        probability = fit_independent(observed, em_steps)
        final = dict(status="independent_reference_selected", solver_called=False)
    else:
        probability, final = fit_likelihood(observed, grouping, selected, em_steps=em_steps)
    return probability, dict(
        selection="two_fold_observed_prefix_nll",
        grouping=grouping,
        strengths=list(strengths),
        cv_losses=losses,
        selected_strength=selected,
        fold_patients=[fold[0].patients for fold in folds],
        solver_fits=fits,
        final_fit=final,
    )


def select_tree_all(observed: PrefixCounts, seed: int, *, em_steps: int = 300):
    """All-patient Dirichlet-tree/blend reference with fold-local nuisance fitting."""
    folds = _cv_parts(observed, seed, em_steps)
    candidates = []
    for strength in (1.0, 10.0, 100.0):
        predictions = [tree_shrink_fit(train, reference, strength) for train, _, reference in folds]
        for weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            loss = (
                sum(
                    validation.patients
                    * observed_nll((1 - weight) * reference + weight * p, validation)
                    for p, (_, validation, reference) in zip(predictions, folds, strict=True)
                )
                / observed.patients
            )
            candidates.append((loss, strength, weight))
    _, strength, weight = min(candidates)
    reference = fit_independent(observed, em_steps)
    probability = (1 - weight) * reference + weight * tree_shrink_fit(observed, reference, strength)
    return probability, dict(
        selection="two_fold_observed_prefix_nll",
        selected_strength=strength,
        selected_joint_weight=weight,
        candidates=len(candidates),
        fold_patients=[fold[0].patients for fold in folds],
    )
