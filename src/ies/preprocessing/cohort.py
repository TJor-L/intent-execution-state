"""First-outcome cohort with patient-exclusive partitions."""

import hashlib
import math
from collections import defaultdict

from ies.data.events import CAUSES, Event, validate_events


def patient_partitions(patient_ids: list[str], seed: int) -> dict[str, str]:
    patients = sorted(
        set(patient_ids),
        key=lambda p: hashlib.sha256(f"{seed}:{p}".encode()).hexdigest(),
    )
    if len(patients) < 3:
        raise ValueError("Need at least three patients for disjoint train/validation/test")
    n_train = min(max(1, int(0.7 * len(patients))), len(patients) - 2)
    n_val = min(max(1, int(0.15 * len(patients))), len(patients) - n_train - 1)
    return {
        patient: "train" if i < n_train else "validation" if i < n_train + n_val else "test"
        for i, patient in enumerate(patients)
    }


def available_history(events: list[Event], order: Event, lookback_hours: float) -> list[Event]:
    return [
        event
        for event in events
        if event.patient_id == order.patient_id
        and event.event_type != "followup_end"
        and order.event_time - lookback_hours <= event.event_time <= order.event_time
        and event.available_time <= order.event_time
    ]


def build_cohort(
    events: list[Event], seed: int, horizon_hours: float = 24.0, lookback_hours: float = 24.0
) -> list[dict]:
    validate_events(events)
    if not all(math.isfinite(v) and v > 0 for v in (horizon_hours, lookback_hours)):
        raise ValueError("Horizon and lookback must be finite and positive")
    partitions = patient_partitions([e.patient_id for e in events], seed)
    by_patient = defaultdict(list)
    linked = defaultdict(list)
    for event in events:
        by_patient[event.patient_id].append(event)
        if event.order_id:
            linked[event.order_id].append(event)
    cohort = []
    for order in (e for e in events if e.event_type == "order"):
        related = linked[order.order_id]
        end = next(e.event_time for e in related if e.event_type == "followup_end")
        boundary = min(end, order.event_time + horizon_hours)
        outcomes = [e for e in related if e.event_type in CAUSES and e.event_time <= boundary]
        outcome = min(outcomes, key=lambda e: e.event_time) if outcomes else None
        history = available_history(by_patient[order.patient_id], order, lookback_hours)
        observations = [e for e in history if e.event_type == "observation"]
        latest = max(observations, key=lambda e: (e.event_time, e.event_id), default=None)
        cohort.append(
            {
                "patient_id": order.patient_id,
                "order_id": order.order_id,
                "split": partitions[order.patient_id],
                "index_time": order.event_time,
                "duration": (outcome.event_time if outcome else boundary) - order.event_time,
                "cause": CAUSES.index(outcome.event_type) + 1 if outcome else 0,
                "features": {
                    "observation_count": len(observations),
                    "latest_value": latest.value if latest else 0.0,
                    "latest_missing": int(latest is None),
                    "latest_age_hours": order.event_time - latest.event_time if latest else 0.0,
                },
            }
        )
    return cohort
