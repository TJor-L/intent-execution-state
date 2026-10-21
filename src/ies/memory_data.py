"""Generated linked recurrent histories. No file reader or clinical adapter."""

from dataclasses import dataclass

import numpy as np

SCENARIOS = ("renewal", "switching", "shared", "null")


@dataclass(frozen=True)
class Order:
    order_id: str
    patient_id: str
    occurred: float
    available: float


@dataclass(frozen=True)
class Event:
    event_id: str
    order_id: str
    patient_id: str
    occurred: float
    available: float


@dataclass(frozen=True)
class Context:
    patient_id: str
    split: str
    cutoff: float
    orders: tuple[Order, ...]
    events: tuple[Event, ...]


@dataclass(frozen=True)
class Outcome:
    order_id: str
    duration: int
    cause: int  # 0: observation ends; 1: next recurrent event; 2: terminal event


@dataclass(frozen=True)
class Sample:
    context: Context
    observed: tuple[Outcome, ...]
    complete: tuple[Outcome, ...]  # Simulation-only oracle; never an encoder input.


def visible(context: Context) -> tuple[tuple[Order, tuple[float, ...]], ...]:
    """Validate links, then apply BOTH clocks before allocating any context budget.

    Return occurrence lags in newest-first order. Canonical ordering uses observable
    times, never identifiers. Exact identical signatures are handled symmetrically
    by the allocator. Events at the cutoff are excluded (left-limit prediction).
    """
    if not np.isfinite(context.cutoff):
        raise ValueError("Invalid generated cutoff")
    orders = {o.order_id: o for o in context.orders}
    if len(orders) != len(context.orders):
        raise ValueError("Duplicate order identity")
    for order in context.orders:
        if (
            order.patient_id != context.patient_id
            or not np.isfinite([order.occurred, order.available]).all()
            or order.available < order.occurred
        ):
            raise ValueError("Invalid order link or clocks")
    times = {key: [] for key in orders}
    seen = set()
    for event in context.events:
        order = orders.get(event.order_id)
        if (
            event.event_id in seen
            or order is None
            or event.patient_id != context.patient_id
            or not np.isfinite([event.occurred, event.available]).all()
            or event.available < event.occurred
            or event.occurred < order.occurred
        ):
            raise ValueError("Invalid event identity, linkage or clocks")
        seen.add(event.event_id)
        if event.occurred < context.cutoff and event.available <= context.cutoff:
            times[event.order_id].append(float(context.cutoff - event.occurred))
    rows = [
        (o, tuple(sorted(times[o.order_id])))
        for o in context.orders
        if o.occurred < context.cutoff and o.available <= context.cutoff
    ]
    # Birth time plus event lags are invariant to renaming and input row permutation.
    return tuple(sorted(rows, key=lambda row: (context.cutoff - row[0].occurred, row[1])))


def generate(
    seed: int,
    scenario: str,
    patients: int,
    orders: int,
    split: str,
    history_steps: int,
    horizon: int,
    censor_probability: float,
) -> list[Sample]:
    """Discrete-time mechanisms; no clinical rates, units or fitted parameters.

    All generated orders survive to the sole prediction cutoff. Post-cutoff termination
    competes with recurrence. Terminal probability is fixed across mechanisms. This
    deliberately limited simulator does NOT establish a real recurrent cohort design.
    """
    if (
        scenario not in SCENARIOS
        or split not in {"decoder", "allocator", "evaluation"}
        or not 1 <= patients <= 1000
        or not 1 <= orders <= 24
        or not 16 <= history_steps <= 128
        or not 1 <= horizon <= 8
        or not 0 <= censor_probability <= 1
    ):
        raise ValueError("Invalid generated memory case")
    rng = np.random.default_rng(seed)
    # Independent censoring RNG leaves histories/latent outcomes invariant to its rate.
    censor_rng = np.random.default_rng(seed + 1_000_003)
    samples = []
    for patient in range(patients):
        patient_id = f"generated-memory-{seed}-{split}-{patient}"
        births = -rng.uniform(history_steps * 0.65, history_steps, size=orders)
        roster = tuple(
            Order(f"{patient_id}-order-{i}", patient_id, float(birth), float(birth))
            for i, birth in enumerate(births)
        )
        intervals = rng.uniform(2, 10, size=orders)
        state = rng.integers(2, size=orders)
        last = births.copy()
        next_time = np.full(orders, horizon, dtype=int)
        next_cause = np.zeros(orders, dtype=int)
        alive = np.ones(orders, dtype=bool)
        events = []
        burst = 0
        for time in range(-history_steps, horizon + 1):
            # Time zero belongs to neither the left-limit history nor future bins.
            if time == 0:
                continue
            if rng.random() < 0.15:
                burst = 1 - burst
            for i, order in enumerate(roster):
                if not alive[i] or time <= order.occurred:
                    continue
                if scenario in {"renewal", "switching"}:
                    interval = intervals[i] if scenario == "renewal" else (2 if state[i] else 8)
                    ratio = (time - last[i] - interval) / (0.45 * interval)
                    probability = 0.04 + 0.50 / (1 + np.exp(-ratio))
                else:
                    probability = 0.04 + 0.4 * burst if scenario == "shared" else 0.18
                terminal = time > 0 and rng.random() < 0.025
                occurred = not terminal and rng.random() < probability
                if time > 0 and (terminal or occurred) and next_cause[i] == 0:
                    next_time[i], next_cause[i] = time, 2 if terminal else 1
                if terminal:
                    alive[i] = False
                if occurred:
                    last[i] = time
                    if time < 0:
                        events.append(
                            Event(
                                f"{order.order_id}-event-{time}",
                                order.order_id,
                                patient_id,
                                float(time),
                                float(time),
                            )
                        )
                    if scenario == "switching" and rng.random() < 0.25:
                        state[i] = 1 - state[i]
        censor = horizon
        if censor_rng.random() < censor_probability:
            censor = int(censor_rng.integers(1, horizon + 1))
        complete, observed = [], []
        for i, order in enumerate(roster):
            time, cause = int(next_time[i]), int(next_cause[i])
            complete.append(Outcome(order.order_id, time, cause))
            observed.append(
                Outcome(order.order_id, min(censor, time), cause if time <= censor else 0)
            )
        samples.append(
            Sample(
                Context(patient_id, split, 0.0, roster, tuple(events)),
                tuple(observed),
                tuple(complete),
            )
        )
    return samples


def label_mask(outcomes: list[Outcome], horizon: int) -> np.ndarray:
    """Allowed categorical outcomes: no event by H, recurrence bins, terminal bins.

    A censored observation permits BOTH later causes plus the no-event-by-H category.
    An event exactly at the censor boundary is observed under this generated convention.
    """
    mask = np.zeros((len(outcomes), 1 + 2 * horizon), dtype=bool)
    for i, outcome in enumerate(outcomes):
        if (
            type(outcome.duration) is not int
            or not 1 <= outcome.duration <= horizon
            or type(outcome.cause) is not int
            or outcome.cause not in {0, 1, 2}
        ):
            raise ValueError("Invalid discrete recurrent outcome")
        if outcome.cause:
            mask[i, 1 + (outcome.cause - 1) * horizon + outcome.duration - 1] = True
        else:
            mask[i, 0] = True
            for cause in (0, 1):
                mask[i, 1 + cause * horizon + outcome.duration : 1 + (cause + 1) * horizon] = True
    return mask
