"""Fixed age-band piecewise baseline with a global fallback."""

import numpy as np

from ies.losses.competing_risks import negative_log_likelihood
from ies.models.piecewise import fit_baseline

BANDS = ((18, 45), (45, 65), (65, 80), (80, None))


def age_band(age: int) -> str:
    if type(age) is not int or age < 18:
        raise ValueError("Invalid age feature")
    for lower, upper in BANDS:
        if upper is None or age < upper:
            return f"{lower}+" if upper is None else f"{lower}-{upper - 1}"
    raise AssertionError("unreachable")


def fit_age_stratified(cohort: list[dict], edges: list[float]) -> dict:
    global_model = fit_baseline(cohort, edges, data_class="restricted_clinical")
    bands = {}
    for lower, upper in BANDS:
        name = f"{lower}+" if upper is None else f"{lower}-{upper - 1}"
        subset = [
            row
            for row in cohort
            if row["split"] == "train"
            and row["age_years_at_order"] >= lower
            and (upper is None or row["age_years_at_order"] < upper)
        ]
        if subset:
            bands[name] = fit_baseline(
                subset,
                edges,
                data_class="restricted_clinical",
            )["hazards_per_hour"]
    return {
        "model": "piecewise_exponential_fixed_age_bands_v1",
        "data_class": "restricted_clinical",
        "edges_hours": global_model["edges_hours"],
        "causes": global_model["causes"],
        "global_hazards_per_hour": global_model["hazards_per_hour"],
        "age_bands": bands,
        "band_boundaries_years": [18, 45, 65, 80],
        "train_patients": global_model["train_patients"],
        "n_train_orders": global_model["n_train_orders"],
        "prior_shape": global_model["prior_shape"],
        "prior_rate_hours": global_model["prior_rate_hours"],
    }


def evaluate_age_stratified(
    cohort: list[dict], model: dict, *, split: str, bootstrap: int, seed: int
) -> tuple[dict, dict]:
    if split != "validation" or bootstrap < 2:
        raise ValueError("Age baseline evaluation is validation-only")
    rows = [row for row in cohort if row["split"] == split]
    if not rows:
        raise ValueError("Empty validation partition")
    patients = sorted({row["patient_id"] for row in rows})
    if set(patients) & set(model["train_patients"]):
        raise ValueError("Evaluation patients overlap training patients")
    losses = []
    for row in rows:
        hazards = model["age_bands"].get(
            age_band(row["age_years_at_order"]), model["global_hazards_per_hour"]
        )
        losses.append(
            float(
                negative_log_likelihood(
                    [row["duration"]],
                    [row["cause"]],
                    hazards,
                    model["edges_hours"],
                )[0]
            )
        )
    losses_array = np.asarray(losses)
    per_patient = [
        losses_array[[row["patient_id"] == patient for row in rows]] for patient in patients
    ]
    rng = np.random.default_rng(seed)
    estimates = [
        float(
            np.concatenate(
                [per_patient[index] for index in rng.integers(len(patients), size=len(patients))]
            ).mean()
        )
        for _ in range(bootstrap)
    ]
    metrics = {
        "data_class": "restricted_clinical",
        "split": "validation",
        "n_patients": len(patients),
        "n_orders": len(rows),
        "nll_per_order": float(losses_array.mean()),
        "nll_patient_bootstrap_95ci": np.quantile(estimates, [0.025, 0.975]).tolist(),
        "bootstrap_replicates": bootstrap,
        "note": "Fixed age-band feature-pipeline baseline; no causal or clinical claim.",
    }
    predictions = {
        "data_class": "restricted_clinical",
        "orders": [
            {"order_id": row["order_id"], "patient_id": row["patient_id"], "nll": loss}
            for row, loss in zip(rows, losses, strict=True)
        ],
    }
    return metrics, predictions
