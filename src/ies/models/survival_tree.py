"""Small reference likelihood-partition tree, not a new survival algorithm.

Axis-aligned, training-only quantile splits; each leaf has separate cause/bin hazards.
This relaxes the PH head's linear feature effects and common effects across time bins.
"""

import numpy as np

from ies.losses.competing_risks import exposure, validate_edges


def fit_tree(
    features,
    durations,
    causes,
    patients,
    edges,
    *,
    max_depth=2,
    min_leaf_patients=25,
    quantiles=(0.25, 0.5, 0.75),
    prior_events=0.5,
    prior_hours=1.0,
):
    x, times, causes = np.asarray(features, float), np.asarray(durations, float), np.asarray(causes)
    edges = validate_edges(edges)
    patients = np.asarray(patients)
    if (
        x.ndim != 2
        or len(x) != len(times)
        or not len(x)
        or causes.shape != times.shape
        or patients.shape != times.shape
        or not np.isfinite(x).all()
        or not np.issubdtype(causes.dtype, np.integer)
        or not np.isin(causes, [0, 1, 2, 3]).all()
        or not 0 <= max_depth <= 3
        or min_leaf_patients < 2
        or not 0 < prior_events <= 1
        or not 0 < prior_hours <= 1
        or not all(0 < q < 1 for q in quantiles)
    ):
        raise ValueError("Invalid tree inputs")
    exp = exposure(times, edges)
    event = np.zeros((len(x), len(edges) - 1, 3))
    observed = np.flatnonzero(causes > 0)
    bins = np.searchsorted(edges[1:], times, side="left")
    event[observed, bins[observed], causes[observed] - 1] = 1

    def leaf(indexes):
        time = exp[indexes].sum(axis=0)[:, None]
        counts = event[indexes].sum(axis=0)
        rates = (counts + prior_events) / (time + prior_hours)
        # Compare the actual smoothed leaf likelihood; no pseudo-observations in scores.
        score = float(np.sum(time * rates - counts * np.log(rates)))
        return rates, score

    def grow(indexes, depth):
        rates, score = leaf(indexes)
        node = dict(hazards=rates.tolist())
        if depth >= max_depth or len(set(patients[indexes])) < 2 * min_leaf_patients:
            return node
        best = None
        for feature in range(x.shape[1]):
            for cut in np.unique(np.quantile(x[indexes, feature], quantiles)):
                left = indexes[x[indexes, feature] <= cut]
                right = indexes[x[indexes, feature] > cut]
                if min(len(set(patients[left])), len(set(patients[right]))) < min_leaf_patients:
                    continue
                improvement = score - leaf(left)[1] - leaf(right)[1]
                if improvement > 1e-10 and (best is None or improvement > best[0] + 1e-10):
                    best = (improvement, feature, float(cut), left, right)
        if best is not None:
            _, feature, cut, left, right = best
            node.update(
                feature=feature, cut=cut, left=grow(left, depth + 1), right=grow(right, depth + 1)
            )
        return node

    return dict(
        model="reference_piecewise_survival_tree_v1",
        feature_dimension=x.shape[1],
        edges_hours=edges.tolist(),
        tree=grow(np.arange(len(x)), 0),
    )


def predict_tree(model, features):
    x = np.asarray(features, float)
    if x.ndim != 2 or x.shape[1] != model["feature_dimension"] or not np.isfinite(x).all():
        raise ValueError("Invalid tree features")
    rates = np.full((len(x), len(model["edges_hours"]) - 1, 3), np.nan)

    def walk(node, indexes):
        if "feature" not in node:
            rates[indexes] = node["hazards"]
        else:
            left = x[indexes, node["feature"]] <= node["cut"]
            walk(node["left"], indexes[left])
            walk(node["right"], indexes[~left])

    walk(model["tree"], np.arange(len(x)))
    if not np.isfinite(rates).all() or (rates <= 0).any():
        raise ValueError("Invalid tree hazards")
    return rates
