"""Generated exact lifted smoothing and MAP-EM reference, not a novel EM method."""

from dataclasses import dataclass

import numpy as np

from ies.competition import CountDesign, features, field_prior, fit_emission, validate_signs
from ies.hidden_history import histogram_plan, validate_model
from ies.history_roles import GeneratedPath, validate_path


@dataclass(frozen=True)
class MissingSubject:
    observed: GeneratedPath
    missing_initial: np.ndarray
    data_class: str = "synthetic"


def smooth_path(kernel, first, initial, transition, plan):
    """Scaled forward/backward on sparse histogram-emission transitions."""
    source, target = plan["source"], plan["target"]
    state_count, length = len(plan["states"]), len(kernel)
    predictive = np.zeros((state_count, 2))
    predictive[first] = initial
    before, after, scales = [], [], []
    for k in kernel:
        before.append(predictive)
        joint = predictive[source] * k
        filtered = np.column_stack(
            [np.bincount(target, weights=joint[:, z], minlength=state_count) for z in range(2)]
        )
        scale = float(filtered.sum())
        if not np.isfinite(scale) or scale <= 0:
            raise RuntimeError("Generated smoothing lost supported mass")
        scales.append(scale)
        filtered /= scale
        after.append(filtered)
        predictive = filtered @ transition
    beta = np.ones((state_count, 2))
    weights = np.zeros_like(kernel)
    latent_transition = np.zeros((2, 2))
    for t in reversed(range(length)):
        future = beta @ transition.T
        weights[t] = before[t][source] * kernel[t] * future[target] / scales[t]
        if abs(weights[t].sum() - 1) > 1e-9:
            raise RuntimeError("Generated smoothed transitions did not normalize")
        if t < length - 1:
            latent_transition += np.einsum("hz,zq,hq->zq", after[t], transition, beta)
        beta = np.column_stack(
            [
                np.bincount(
                    source, weights=kernel[t, :, z] * future[target, z], minlength=state_count
                )
                / scales[t]
                for z in range(2)
            ]
        )
    return dict(
        log_scale=float(np.log(scales).sum()),
        weights=weights,
        initial=weights[0].sum(axis=0),
        transition=latent_transition,
    )


class LearningDesign:
    """Reusable exact training design: full roster <=8, hidden <=4, <=500k terms."""

    def __init__(self, subjects, signs):
        self.signs = validate_signs(signs)
        if not isinstance(subjects, (tuple, list)) or not 1 <= len(subjects) <= 512:
            raise ValueError("Bounded generated missing-subject list required")
        self.subjects = []
        records, trials, success, dead = 0, [], [], []
        for subject in subjects:
            if not isinstance(subject, MissingSubject) or subject.data_class != "synthetic":
                raise ValueError("Generated missing-history subjects required")
            history, events = validate_path(subject.observed)
            missing = np.asarray(subject.missing_initial)
            if (
                missing.ndim != 1
                or missing.dtype.kind not in "iu"
                or not 0 <= len(missing) <= 4
                or len(history) + len(missing) > 8
                or not np.isin(missing, [0, 1, 2, 3]).all()
            ):
                raise ValueError("Known bounded generated initial roster required")
            plan = histogram_plan(len(missing))
            count = len(plan["source"])
            end = records + len(events) * count
            if end > 500_000:
                raise ValueError("Generated missing-history training term budget exceeded")
            initial = np.r_[np.bincount(missing, minlength=4), 0]
            first = int(np.flatnonzero(np.all(plan["states"] == initial, axis=1))[0])
            self.subjects.append(
                dict(start=records, end=end, length=len(events), first=first, plan=plan)
            )
            alive = np.ones(len(history), dtype=bool)
            for row in events:
                survivor = alive & (row != 2)
                trials.append(plan["trials"] + np.bincount(history[survivor], minlength=4))
                success.append(plan["success"] + np.bincount(history[row == 1], minlength=4))
                dead.append(plan["terminal"] + np.bincount(history[row == 2], minlength=4))
                history[survivor] = 2 * (history[survivor] % 2) + row[survivor]
                alive = survivor
            records = end
        self.trials = np.concatenate(trials) if trials else np.zeros((0, 4), dtype=int)
        successes = np.concatenate(success) if success else np.zeros((0, 4), dtype=int)
        self.terminal = np.concatenate(dead) if dead else np.zeros((0, 4), dtype=int)
        self.exposure = self.trials + self.terminal
        self.x = features(successes, self.trials, self.signs)
        contexts, self.index = np.unique(self.trials, axis=0, return_inverse=True)
        self.normalizer = CountDesign(
            contexts if len(contexts) else np.zeros((1, 4), dtype=int), signs
        )
        self.multiplicity = np.concatenate(
            [np.tile(s["plan"]["log_multiplicity"], s["length"]) for s in self.subjects]
        )

    def expectation(self, model, posterior=False):
        parameters, terminal, signs, initial, transition = validate_model(model)
        if not np.array_equal(signs, self.signs):
            raise ValueError("Generated model partition differs from training design")
        logz = np.column_stack([self.normalizer.distribution(p)[0] for p in parameters])
        log_kernel = self.x @ parameters.T - logz[self.index]
        log_kernel += (
            self.terminal @ np.log(terminal) + self.trials @ np.log1p(-terminal) + self.multiplicity
        )[:, None]
        weights = np.zeros_like(log_kernel)
        initial_counts, transitions = np.zeros(2), np.zeros((2, 2))
        likelihoods = []
        for s in self.subjects:
            if not s["length"]:
                likelihoods.append(0.0)
                continue
            sl = slice(s["start"], s["end"])
            logk = log_kernel[sl].reshape(s["length"], -1, 2)
            maximum = logk.max(axis=(1, 2))
            kernel = np.exp(logk - maximum[:, None, None])
            result = smooth_path(kernel, s["first"], initial, transition, s["plan"])
            weights[sl] = result["weights"].reshape(-1, 2)
            likelihoods.append(result["log_scale"] + maximum.sum())
            initial_counts += result["initial"]
            transitions += result["transition"]
        result = dict(
            log_probability=np.array(likelihoods),
            initial=initial_counts,
            transition=transitions,
            terminal=weights.sum(axis=1) @ self.terminal,
            exposure=weights.sum(axis=1) @ self.exposure,
            context_weights=np.column_stack(
                [
                    np.bincount(self.index, weights=weights[:, z], minlength=len(logz))
                    for z in range(2)
                ]
            ),
            target=weights.T @ self.x,
        )
        if posterior:
            result["edge_posterior"] = weights
        return result


def log_prior(model, single_state=False):
    emission = model["parameters"][:1] if single_state else model["parameters"]
    prior = -sum(field_prior(p)[0] for p in emission)
    prior += 0.5 * (np.log(model["terminal"]) + np.log1p(-model["terminal"])).sum()
    if not single_state:
        prior += 0.5 * (np.log(model["initial"]).sum() + np.log(model["transition"]).sum())
    return float(prior)


def initialize(hmm, signs, single_state=False, reference=None):
    p = hmm["probability"]
    model = dict(
        parameters=np.column_stack([np.log(p) - np.log1p(-p), np.zeros(2)]),
        signs=validate_signs(signs),
        initial=hmm["initial"].copy(),
        transition=hmm["transition"].copy(),
        terminal=hmm["terminal"].copy(),
    )
    if single_state:
        if reference is None:
            raise ValueError("Observed reference required for one-state initialization")
        p = reference["probability"]
        model["parameters"] = np.tile(np.r_[np.log(p) - np.log1p(-p), 0.0], (2, 1))
        model["initial"] = np.full(2, 0.5)
        model["transition"] = np.full((2, 2), 0.5)
        model["terminal"] = reference["terminal"].copy()
    return model


def fit_missing(design, initial_model, iterations=20, single_state=False):
    if type(iterations) is not int or not 1 <= iterations <= 30 or type(single_state) is not bool:
        raise ValueError("Invalid generated missing-history EM budget")
    validate_model(initial_model)
    model = {k: np.array(v, copy=True) for k, v in initial_model.items()}
    if single_state and (
        not np.array_equal(model["parameters"][0], model["parameters"][1])
        or not np.array_equal(model["initial"], np.full(2, 0.5))
        or not np.array_equal(model["transition"], np.full((2, 2), 0.5))
    ):
        raise ValueError("Tied one-state generated initialization required")
    trace, certificates = [], []
    for iteration in range(iterations + 1):
        expected = design.expectation(model)
        trace.append(float(expected["log_probability"].sum() + log_prior(model, single_state)))
        if iteration == iterations:
            break
        for z in range(1 if single_state else 2):
            weights = (
                expected["context_weights"].sum(axis=1)
                if single_state
                else expected["context_weights"][:, z],
                expected["target"].sum(axis=0) if single_state else expected["target"][z],
            )
            params, certificate = fit_emission(design.normalizer, weights, model["parameters"][z])
            model["parameters"][z] = params
            certificates.append({k: v for k, v in certificate.items() if k != "objective"})
        if single_state:
            model["parameters"][1] = model["parameters"][0]
        else:
            counts = expected["initial"] + 0.5
            model["initial"] = counts / counts.sum()
            counts = expected["transition"] + 0.5
            model["transition"] = counts / counts.sum(axis=1, keepdims=True)
        model["terminal"] = (expected["terminal"] + 0.5) / (expected["exposure"] + 1)
    if np.min(np.diff(trace)) < -1e-6:
        raise RuntimeError("Generated observed-data MAP objective decreased")
    return model, dict(
        objective=trace,
        msteps=certificates,
        single_state=single_state,
        global_optimum_claimed=False,
        records=len(design.x),
    )
