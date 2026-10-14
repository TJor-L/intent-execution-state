"""In-memory bounded validation. Public results are fixed aggregate counters only."""

import math
import time
from collections import Counter
from dataclasses import dataclass, field

from ies.feasibility.contract import FeasibilityError, Mapping, identity
from ies.feasibility.time import time_value

COUNT_NAMES = (
    "considered_orders",
    "considered_administrations",
    "considered_observations",
    "missing_order_identities",
    "missing_administration_identities",
    "missing_direct_order_identity",
    "missing_observation_identities",
    "missing_direct_observation_identity",
    "missing_required_times",
    "invalid_time_values",
    "duplicate_order_identities",
    "duplicate_administration_identities",
    "duplicate_observation_identities",
    "matched_direct_links",
    "unmatched_direct_links",
    "patient_mismatches",
    "encounter_mismatches",
    "encounter_missing_links",
    "encounter_checks_unavailable",
    "matched_observation_links",
    "unmatched_observation_links",
    "observation_patient_mismatches",
    "observation_encounter_mismatches",
    "observation_encounter_missing_links",
    "observation_encounter_checks_unavailable",
    "observation_endpoint_unavailable_at_boundary_orders",
    "qualifying_actions",
    "excluded_actions",
    "missing_actions",
    "retrospective_execution_rows",
    "unresolved_documentation_rows",
    "excluded_documentation_orders",
    "order_unavailable_at_index",
    "temporal_ordering_violations",
    "administrations_unavailable_at_boundary",
    "single_qualifying_orders",
    "repeated_qualifying_orders",
    "rejected_orders",
    "accepted_execution_orders",
    "terminal_without_execution_orders",
    "right_censored_orders",
    "unresolved_due_to_limits_orders",
    "ambiguous_terminal_ties",
)
LIMIT_NAMES = (
    "files",
    "directories",
    "entries",
    "rows",
    "bytes",
    "keys",
    "runtime",
    "cpu",
    "memory",
)


@dataclass
class Budget:
    mapping: Mapping = field(repr=False)
    started: float = field(default_factory=time.monotonic)
    reached: dict = field(default_factory=lambda: dict.fromkeys(LIMIT_NAMES, False))

    def check_time(self):
        if time.monotonic() - self.started >= self.mapping.limits.runtime_seconds:
            self.reached["runtime"] = True
            raise FeasibilityError("runtime_limit")


def known_by(occurred: float, available: float, cutoff: float) -> bool:
    return occurred <= available <= cutoff


@dataclass(repr=False)
class Order:
    patient: tuple | None
    encounter: tuple | None
    observation_id: tuple | None
    occurred: float | None
    boundary: float | None
    terminals: list[tuple[float, float]]
    invalid: bool = False
    qualifying: int = 0
    first: tuple[float, float] | None = None
    documentation_excluded: bool = False


@dataclass(repr=False)
class Observation:
    patient: tuple | None
    encounter: tuple | None
    times: tuple[float, float] | None
    invalid: bool


def pair(row, occurrence, availability, mapping, counts, optional=False):
    raw = (row.get(occurrence), row.get(availability))
    if optional and raw == (None, None):
        return None, False
    if any(value is None for value in raw):
        counts["missing_required_times"] += 1
        return None, True
    times = tuple(time_value(value, mapping) for value in raw)
    if any(value is None for value in times):
        counts["invalid_time_values"] += 1
        return None, True
    if times[1] < times[0]:
        counts["temporal_ordering_violations"] += 1
        return None, True
    return times, False


def check_encounter(order, encounter, mapped, policy, counts, prefix="") -> bool:
    if not mapped:
        counts[f"{prefix}encounter_checks_unavailable"] += 1
        return False
    mismatch = encounter is not None and order.encounter is not None
    mismatch = mismatch and encounter != order.encounter
    missing = encounter is None or order.encounter is None
    counts[f"{prefix}encounter_mismatches"] += int(mismatch)
    counts[f"{prefix}encounter_missing_links"] += int(missing)
    return (mismatch or missing) and policy == "reject_order"


def analyze(
    order_rows,
    administration_rows,
    observation_rows,
    mapping: Mapping,
    budget: Budget | None = None,
) -> dict:
    budget = budget or Budget(mapping)
    counts = Counter(dict.fromkeys(COUNT_NAMES, 0))
    orders = {}
    administration_ids = {}
    observations = {}

    def room_for_key():
        if len(orders) + len(administration_ids) + len(observations) >= mapping.limits.max_keys:
            budget.reached["keys"] = True
            return False
        return True

    for row in order_rows:
        budget.check_time()
        counts["considered_orders"] += 1
        key, patient = identity(row.get("order_id")), identity(row.get("patient_id"))
        if key is None or patient is None:
            counts["missing_order_identities"] += 1
        if key is None:
            continue
        if key in orders:
            counts["duplicate_order_identities"] += 1
            orders[key].invalid = True
            continue
        if not room_for_key():
            break
        times, invalid = pair(row, "occurred_at", "available_at", mapping, counts)
        occurred = times[0] if times else None
        if times and not known_by(*times, occurred):
            counts["order_unavailable_at_index"] += 1
            invalid = True
        terminals = []
        for name in ("discontinued", "ended"):
            if mapping.orders.columns[f"{name}_at"] is None:
                continue
            terminal, bad = pair(
                row,
                f"{name}_at",
                f"{name}_available_at",
                mapping,
                counts,
                optional=True,
            )
            invalid |= bad
            if terminal is not None:
                if occurred is not None and terminal[0] <= occurred:
                    counts["temporal_ordering_violations"] += 1
                    invalid = True
                terminals.append(terminal)
        orders[key] = Order(
            patient,
            identity(row.get("encounter_id")),
            identity(row.get("observation_id")),
            occurred,
            None,
            terminals,
            invalid or patient is None,
        )

    for row in observation_rows:
        budget.check_time()
        counts["considered_observations"] += 1
        key, patient = identity(row.get("observation_id")), identity(row.get("patient_id"))
        if key is None or patient is None:
            counts["missing_observation_identities"] += 1
        if key is None:
            continue
        if key in observations:
            counts["duplicate_observation_identities"] += 1
            observations[key].invalid = True
            continue
        if not room_for_key():
            break
        times, invalid = pair(row, "ended_at", "available_at", mapping, counts)
        observations[key] = Observation(
            patient, identity(row.get("encounter_id")), times, invalid or patient is None
        )

    for order in orders.values():
        budget.check_time()
        if order.observation_id is None:
            counts["missing_direct_observation_identity"] += 1
        observation = observations.get(order.observation_id)
        if observation is None:
            counts["unmatched_observation_links"] += 1
            order.invalid = True
            continue
        counts["matched_observation_links"] += 1
        order.invalid |= observation.invalid
        if observation.patient is not None and observation.patient != order.patient:
            counts["observation_patient_mismatches"] += 1
            order.invalid = True
        order.invalid |= check_encounter(
            order,
            observation.encounter,
            mapping.observations.columns["encounter_id"] is not None,
            mapping.observation_encounter_policy,
            counts,
            "observation_",
        )
        if observation.times and order.occurred is not None:
            end, available = observation.times
            if end <= order.occurred:
                counts["temporal_ordering_violations"] += 1
                order.invalid = True
            order.boundary = min(end, order.occurred + mapping.horizon_hours)
            # Coverage is retrospectively ascertained, never an index-time feature.
            # Evidence availability does not extend followup or imply online knowledge.
            counts["observation_endpoint_unavailable_at_boundary_orders"] += int(
                available > order.boundary
            )

    for row in administration_rows:
        budget.check_time()
        counts["considered_administrations"] += 1
        key = identity(row.get("order_id"))
        administration = identity(row.get("administration_id"))
        patient = identity(row.get("patient_id"))
        if key is None:
            counts["missing_direct_order_identity"] += 1
        if administration is None or patient is None:
            counts["missing_administration_identities"] += 1
        order = orders.get(key)
        counts["matched_direct_links" if order else "unmatched_direct_links"] += 1
        invalid = key is None or administration is None or patient is None
        if administration is not None:
            if administration in administration_ids:
                counts["duplicate_administration_identities"] += 1
                previous = orders.get(administration_ids[administration])
                if previous:
                    previous.invalid = True
                invalid = True
            elif not room_for_key():
                break
            else:
                administration_ids[administration] = key
        if order is not None:
            if patient is not None and patient != order.patient:
                counts["patient_mismatches"] += 1
                invalid = True
            invalid |= check_encounter(
                order,
                identity(row.get("encounter_id")),
                mapping.administrations.columns["encounter_id"] is not None,
                mapping.encounter_policy,
                counts,
            )
        action = identity(row.get("action"))
        if action is None:
            counts["missing_actions"] += 1
            invalid = True
        elif action not in mapping.qualifying_actions:
            counts["excluded_actions"] += 1
        else:
            counts["qualifying_actions"] += 1
            availability = "available_at"
            if mapping.occurrence_equality_policy is not None:
                availability = "occurred_at"
                policy = mapping.occurrence_equality_policy
                status = identity(row.get("documentation_status"))
                retrospective = status in policy.retrospective_values
                unresolved = status not in policy.contemporaneous_values and not retrospective
                counts["retrospective_execution_rows"] += int(retrospective)
                counts["unresolved_documentation_rows"] += int(unresolved)
                if retrospective or unresolved:
                    invalid = True
                    if order is not None:
                        # Dropping just the dose could falsely manufacture censoring or a singleton.
                        order.documentation_excluded = True
            times, bad = pair(row, "occurred_at", availability, mapping, counts)
            invalid |= bad
            if order is not None:
                # Count repeats even if a row has bad times or is outside the horizon.
                order.qualifying += 1
                if times and order.occurred is not None and times[0] <= order.occurred:
                    counts["temporal_ordering_violations"] += 1
                    invalid = True
                if order.qualifying == 1:
                    order.first = times
        if order is not None:
            order.invalid |= invalid

    for order in orders.values():
        budget.check_time()
        counts["single_qualifying_orders"] += int(order.qualifying == 1)
        counts["repeated_qualifying_orders"] += int(order.qualifying > 1)
        counts["excluded_documentation_orders"] += int(order.documentation_excluded)
        if order.invalid or order.qualifying > 1:
            counts["rejected_orders"] += 1
            continue
        if any(budget.reached.values()):
            # A truncated source may hide another dose or a duplicate order. Never label it.
            counts["unresolved_due_to_limits_orders"] += 1
            continue
        terminal = min(
            (t[0] for t in order.terminals if known_by(*t, order.boundary)), default=math.inf
        )
        execution = math.inf
        if order.first:
            if known_by(*order.first, order.boundary):
                execution = order.first[0]
            else:
                counts["administrations_unavailable_at_boundary"] += 1
        if math.isfinite(execution) and execution == terminal:
            counts["ambiguous_terminal_ties"] += 1
            counts["rejected_orders"] += 1
        elif execution < terminal:
            counts["accepted_execution_orders"] += 1
        elif math.isfinite(terminal):
            counts["terminal_without_execution_orders"] += 1
        else:
            counts["right_censored_orders"] += 1
    return {
        "schema_version": 2,
        "mode": "bounded_feasibility",
        "data_class": "restricted_aggregate",
        "status": "limited" if any(budget.reached.values()) else "complete",
        "counts": dict(counts),
        "limits_reached": budget.reached,
    }
