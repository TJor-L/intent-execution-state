"""Observed-data likelihood and patient-cluster bootstrap; no naive censor labels."""

import numpy as np

from ies.losses.competing_risks import negative_log_likelihood
from ies.models.piecewise import cumulative_incidence


def evaluate(cohort: list[dict], model: dict, split="test", bootstrap=200, seed=0):
    if split not in {"validation", "test"}:
        raise ValueError("Evaluation requires validation or test split")
    rows = [r for r in cohort if r["split"] == split]
    if not rows:
        raise ValueError("Empty evaluation partition")
    patients = sorted({r["patient_id"] for r in rows})
    if set(patients) & set(model["train_patients"]):
        raise ValueError("Evaluation patients overlap training patients")
    losses = negative_log_likelihood(
        [r["duration"] for r in rows],
        [r["cause"] for r in rows],
        model["hazards_per_hour"],
        model["edges_hours"],
    )
    if bootstrap < 2:
        raise ValueError("Need at least two bootstrap replicates")
    per_patient = [losses[[r["patient_id"] == p for r in rows]] for p in patients]
    rng = np.random.default_rng(seed)
    estimates = [
        float(
            np.concatenate(
                [per_patient[j] for j in rng.integers(len(patients), size=len(patients))]
            ).mean()
        )
        for _ in range(bootstrap)
    ]
    data_class = model.get("data_class", "synthetic")
    metrics = {
        "data_class": data_class,
        "split": split,
        "n_patients": len(patients),
        "n_orders": len(rows),
        "nll_per_order": float(losses.mean()),
        "nll_patient_bootstrap_95ci": np.quantile(estimates, [0.025, 0.975]).tolist(),
        "bootstrap_replicates": bootstrap,
        "outcomes": {str(k): sum(r["cause"] == k for r in rows) for k in range(4)},
        "note": (
            "Synthetic pipeline smoke test; not evidence of clinical performance or novelty."
            if data_class == "synthetic"
            else "Intercept-only label-pipeline validation; no individual predictive claim."
        ),
    }
    predictions = {
        "data_class": data_class,
        "population_curve": cumulative_incidence(model),
        "orders": [
            {"order_id": r["order_id"], "patient_id": r["patient_id"], "nll": float(loss)}
            for r, loss in zip(rows, losses, strict=True)
        ],
    }
    return metrics, predictions
