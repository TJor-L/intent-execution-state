"""Data-free contract for freezing a future clinical cohort definition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class ProtocolError(ValueError):
    """Fixed public error for an invalid or incomplete protocol."""


def require(condition: bool) -> None:
    if not condition:
        raise ProtocolError("invalid_clinical_protocol")


@dataclass(frozen=True, repr=False)
class ClinicalProtocol:
    status: str
    adult_reviewed: bool
    inpatient_reviewed: bool
    medication_reviewed: bool
    medication_category_count: int
    minimum_eligible_orders: int | None
    minimum_execution_events: int | None


def parse_protocol(value: dict) -> ClinicalProtocol:
    require(
        isinstance(value, dict)
        and set(value)
        == {"schema_version", "status", "task", "population", "temporal", "split", "acceptance"}
    )
    require(value["schema_version"] == 1 and value["status"] in ("draft", "frozen"))
    task = value["task"]
    require(
        isinstance(task, dict)
        and task
        == {
            "estimand": "first_execution_competing_risk",
            "eligible_orders": "all_distinct_orders",
            "repeated_administrations": "reject_order",
            "terminal_ties": "reject_order",
            "continuous_infusions": "exclude",
            "unresolved_prn": "exclude",
        }
    )
    population = value["population"]
    require(
        isinstance(population, dict)
        and set(population)
        == {
            "minimum_age_years",
            "adult_derivation_reviewed",
            "adult_derivation_evidence_reference",
            "inpatient_only",
            "inpatient_definition_reviewed",
            "inpatient_definition_evidence_reference",
            "medication_categories",
            "medication_category_system",
            "medication_eligibility_reviewed",
            "medication_eligibility_evidence_reference",
        }
    )
    require(population["minimum_age_years"] == 18 and population["inpatient_only"] is True)
    for flag in (
        "adult_derivation_reviewed",
        "inpatient_definition_reviewed",
        "medication_eligibility_reviewed",
    ):
        require(type(population[flag]) is bool)
    categories = population["medication_categories"]
    require(isinstance(categories, list) and len(categories) <= 2)
    require(
        all(
            isinstance(item, str) and 0 < len(item.strip()) <= 256 and "\x00" not in item
            for item in categories
        )
    )
    system = population["medication_category_system"]
    require(system is None or isinstance(system, str) and 0 < len(system.strip()) <= 256)
    evidence = {}
    for name in (
        "adult_derivation_evidence_reference",
        "inpatient_definition_evidence_reference",
        "medication_eligibility_evidence_reference",
    ):
        reference = population[name]
        require(
            reference is None
            or isinstance(reference, str)
            and 0 < len(reference.strip()) <= 2048
            and "\x00" not in reference
        )
        evidence[name] = reference is not None
    temporal = value["temporal"]
    require(
        temporal
        == {
            "index": "order_created_and_available",
            "input_window_hours": 24,
            "followup_horizon_hours": 24,
            "occurrence_and_availability_required": True,
            "observation_coverage_required": True,
            "laboratory_features_enabled": False,
        }
    )
    split = value["split"]
    require(
        split
        == {
            "unit": "patient",
            "seed": 20261014,
            "train_fraction": 0.7,
            "validation_fraction": 0.15,
            "test_fraction": 0.15,
            "global_calendar_split": False,
        }
    )
    acceptance = value["acceptance"]
    require(
        isinstance(acceptance, dict)
        and set(acceptance) == {"minimum_eligible_orders", "minimum_execution_events"}
    )
    for name in acceptance:
        threshold = acceptance[name]
        require(threshold is None or type(threshold) is int and threshold > 0)
    protocol = ClinicalProtocol(
        value["status"],
        population["adult_derivation_reviewed"] and evidence["adult_derivation_evidence_reference"],
        population["inpatient_definition_reviewed"]
        and evidence["inpatient_definition_evidence_reference"],
        population["medication_eligibility_reviewed"]
        and evidence["medication_eligibility_evidence_reference"]
        and system is not None,
        len(categories),
        acceptance["minimum_eligible_orders"],
        acceptance["minimum_execution_events"],
    )
    if protocol.status == "frozen":
        require(not missing_decisions(protocol))
    return protocol


def missing_decisions(protocol: ClinicalProtocol) -> list[str]:
    missing = []
    if not protocol.adult_reviewed:
        missing.append("adult_derivation_review")
    if not protocol.inpatient_reviewed:
        missing.append("inpatient_definition_review")
    if not protocol.medication_reviewed or not 1 <= protocol.medication_category_count <= 2:
        missing.append("medication_eligibility_review")
    if protocol.minimum_eligible_orders is None:
        missing.append("minimum_eligible_orders")
    if protocol.minimum_execution_events is None:
        missing.append("minimum_execution_events")
    return missing


def plan_protocol(path: Path) -> dict:
    try:
        protocol = parse_protocol(yaml.safe_load(path.read_bytes()))
    except ProtocolError:
        raise
    except Exception:
        raise ProtocolError("invalid_clinical_protocol") from None
    missing = missing_decisions(protocol)
    return {
        "mode": "clinical_cohort_protocol",
        "status": protocol.status,
        "ready_for_extraction": protocol.status == "frozen" and not missing,
        "missing_decisions": missing,
        "patient_level_split": True,
        "global_calendar_split": False,
        "first_execution_only": True,
        "repeated_administrations_rejected": True,
        "laboratory_features_enabled": False,
        "submitted": False,
    }
