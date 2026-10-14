"""Seeded toy trajectories, with no clinical medication or lab claims."""

import math

import numpy as np

from ies.data.events import CAUSES, Event, validate_events


def generate_events(
    n_patients: int = 300,
    seed: int = 20261014,
    orders_per_patient: int = 2,
    horizon_hours: float = 24.0,
    delay_scale: float = 1.0,
) -> list[Event]:
    if n_patients < 3 or not 1 <= orders_per_patient <= 10:
        raise ValueError("Need at least 3 patients and 1–10 orders per patient")
    if not all(math.isfinite(x) and x > 0 for x in (horizon_hours, delay_scale)):
        raise ValueError("Horizon and delay scale must be finite and positive")
    rng = np.random.default_rng(seed)
    events = []
    for patient in range(n_patients):
        patient_id = f"synthetic-p{patient:06d}"
        encounter = f"synthetic-enc{patient:06d}"
        state = float(rng.normal())
        for ordinal in range(orders_per_patient):
            order_id = f"{patient_id}-o{ordinal}"
            index = 48.0 * (ordinal + 1)
            code = f"synthetic-med-{int(rng.integers(0, 2))}"

            def add(
                kind,
                time,
                available=None,
                value=None,
                suffix=None,
                *,
                order_id=order_id,
                patient_id=patient_id,
                encounter=encounter,
                code=code,
            ):
                events.append(
                    Event(
                        event_id=f"{order_id}-{suffix or kind}",
                        patient_id=patient_id,
                        encounter_id=encounter,
                        event_type=kind,
                        code="synthetic-lab" if kind == "observation" else code,
                        event_time=time,
                        available_time=time if available is None else available,
                        order_id=None if kind == "observation" else order_id,
                        value=value,
                    )
                )

            add("observation", index - 20, index - 19, state + float(rng.normal()), "obs-old")
            add("observation", index - 2, index - 1, state + float(rng.normal()), "obs-recent")
            # Occurs before cutoff, but is not available until afterwards: leakage fixture.
            add("observation", index - 0.5, index + 1, 999.0, "obs-delayed")
            add("order", index)
            # Independent administrative censoring in the toy generator only.
            followup = horizon_hours * float(rng.uniform(0.1, 1.0))
            rates = np.array([0.18 * math.exp(0.2 * state), 0.035, 0.012])
            waiting = rng.exponential(1.0 / rates) * delay_scale
            cause = int(waiting.argmin())
            if waiting[cause] <= followup:
                add(CAUSES[cause], index + float(waiting[cause]))
            add("followup_end", index + followup)
            add(
                "observation",
                index + followup / 2,
                value=state + float(rng.normal()),
                suffix="obs-future",
            )
    events.sort(key=lambda e: (e.patient_id, e.event_time, e.event_id))
    validate_events(events)
    return events
