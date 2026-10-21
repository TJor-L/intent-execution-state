"""Generated T001 contract fixtures. These contain no clinical values or mappings."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from ies.feasibility.contract import (
    ADMIN_OPTIONAL,
    ADMIN_REQUIRED,
    OBSERVATION_OPTIONAL,
    OBSERVATION_REQUIRED,
    ORDER_OPTIONAL,
    ORDER_REQUIRED,
    Limits,
    Mapping,
    Source,
)
from ies.recurrent_task import audit_recurrent_rows


def generated_case():
    def source(role, names):
        return Source(
            Path(f"/generated-placeholder/{role}.parquet"),
            {name: f"toy_{name}" for name in sorted(names)},
        )

    mapping = Mapping(
        source("orders", ORDER_REQUIRED | ORDER_OPTIONAL),
        source("administrations", ADMIN_REQUIRED | ADMIN_OPTIONAL),
        source("observations", OBSERVATION_REQUIRED | OBSERVATION_OPTIONAL),
        frozenset({("string", "toy_dose")}),
        "reject_order",
        "reject_order",
        "column",
        None,
        "numeric_hours",
        None,
        24.0,
        Limits(4, 4, 16, 1000, 3000, 128, 60, 60, 1, 1024),
    )
    orders = [
        {
            "order_id": f"toy_order_{index}",
            "patient_id": "toy_patient",
            "encounter_id": "toy_encounter",
            "observation_id": f"toy_observation_{index}",
            "occurred_at": float(index),
            "available_at": float(index),
        }
        for index in range(3)
    ]
    administrations = [
        {
            "administration_id": f"toy_event_{index}",
            "order_id": f"toy_order_{order}",
            "patient_id": "toy_patient",
            "encounter_id": "toy_encounter",
            "occurred_at": occurrence,
            "available_at": occurrence,
            "action": "toy_dose",
        }
        for index, (order, occurrence) in enumerate(
            [(0, 0.5), (0, 1.5), (0, 3.0), (1, 2.5), (1, 4.0)]
        )
    ]
    observations = [
        {
            "observation_id": f"toy_observation_{index}",
            "patient_id": "toy_patient",
            "encounter_id": "toy_encounter",
            "ended_at": 12.0,
            "available_at": 14.0,
        }
        for index in range(3)
    ]
    return mapping, orders, administrations, observations, frozenset({("string", "toy_patient")})


def run_generated_cases():
    base = generated_case()
    reports = {}
    for name in ("complete", "short_observation", "terminal", "late_outcome", "wrong_patient"):
        mapping, orders, administrations, observations, patients = deepcopy(base)
        if name == "short_observation":
            observations[1]["ended_at"] = 3.0
        elif name == "terminal":
            orders[2].update(ended_at=3.0, ended_available_at=3.0)
        elif name == "late_outcome":
            administrations[2]["available_at"] = 20.0
        elif name == "wrong_patient":
            administrations[2]["patient_id"] = "toy_other_patient"
        reports[name] = audit_recurrent_rows(
            orders,
            administrations,
            observations,
            replace(mapping),
            patients,
            coverage_complete=True,
            data_class="synthetic",
        )
    return {
        "mode": "generated_recurrent_task_checks",
        "data_class": "synthetic",
        "clinical_inputs_used": False,
        "model_fitted": False,
        "cases": reports,
    }


def main():
    import json

    print(json.dumps(run_generated_cases(), indent=2))


if __name__ == "__main__":
    main()
