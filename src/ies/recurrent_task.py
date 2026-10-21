"""T001 linked recurrent-window contract; no model fitting or source I/O."""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ies.feasibility.analysis import check_encounter, known_by, pair
from ies.feasibility.contract import Mapping, identity

MODE = "recurrent_task_support"
LOOKBACK_HOURS = 24.0
HORIZON_HOURS = 4.0
MAX_ANCHORS = 64
MAX_ROSTER = 64
MAX_ORDERS = 20_000
MAX_ADMINISTRATIONS = 200_000
MAX_OBSERVATIONS = 20_000


class RecurrentTaskError(ValueError):
    """Only fixed codes may leave the task boundary."""


@dataclass(repr=False)
class Path:
    key: tuple
    patient: tuple | None
    encounter: tuple | None
    observation: tuple | None
    creation: tuple[float, float] | None
    terminals: list = field(default_factory=list)
    events: list = field(default_factory=list)
    observation_end: float | None = None
    invalid: bool = False


@dataclass(frozen=True, repr=False)
class Window:
    """Private in-memory object. Future ascertainment is separate from inputs."""

    patient: tuple
    cutoff: float
    order_keys: tuple
    history: tuple
    status: str
    observed_hours: float | None = None
    prefix_counts: tuple | None = None
    horizon_counts: tuple | None = None
    endpoint_kinds: tuple | None = None


def _bounded(rows, maximum):
    for index, row in enumerate(rows):
        if index >= maximum:
            raise RecurrentTaskError("recurrent_retention_limit")
        if not isinstance(row, dict):
            raise RecurrentTaskError("recurrent_invalid_rows")
        yield row


def _paths(order_rows, administration_rows, observation_rows, mapping, patients, counts):
    paths = {}
    bad_rosters = set()
    observations = {}
    for row in _bounded(order_rows, MAX_ORDERS):
        counts["order_rows"] += 1
        key, patient = identity(row.get("order_id")), identity(row.get("patient_id"))
        if key is None:
            counts["invalid_order_identity"] += 1
            if patient in patients:
                bad_rosters.add(patient)
            continue
        if key in paths:
            counts["duplicate_order_identities"] += 1
            paths[key].invalid = True
            bad_rosters.update((patient, paths[key].patient))
            continue
        creation, invalid = pair(row, "occurred_at", "available_at", mapping, counts)
        if patient not in patients:
            invalid = True
        if invalid:
            counts["invalid_order_creation"] += 1
            bad_rosters.add(patient)
        path = Path(
            key,
            patient,
            identity(row.get("encounter_id")),
            identity(row.get("observation_id")),
            creation,
            invalid=invalid,
        )
        for name in ("discontinued", "ended"):
            if mapping.orders.columns[f"{name}_at"] is None:
                continue
            terminal, bad = pair(
                row, f"{name}_at", f"{name}_available_at", mapping, counts, optional=True
            )
            path.invalid |= bad
            if terminal is not None:
                if creation is not None and terminal[0] <= creation[0]:
                    path.invalid = True
                    counts["invalid_terminal_time"] += 1
                path.terminals.append(terminal)
        paths[key] = path

    for row in _bounded(observation_rows, MAX_OBSERVATIONS):
        counts["observation_rows"] += 1
        key = identity(row.get("observation_id"))
        if key is None:
            counts["invalid_observation_identity"] += 1
            continue
        if key in observations:
            counts["duplicate_observation_identities"] += 1
            observations[key] = None
            continue
        times, invalid = pair(row, "ended_at", "available_at", mapping, counts)
        observations[key] = (row, times, invalid)

    for path in paths.values():
        observation = observations.get(path.observation)
        if observation is None:
            counts["unresolved_observation_links"] += 1
            path.invalid = True
            continue
        row, times, invalid = observation
        if identity(row.get("patient_id")) != path.patient:
            counts["observation_patient_mismatches"] += 1
            invalid = True
        invalid |= check_encounter(
            path,
            identity(row.get("encounter_id")),
            mapping.observations.columns["encounter_id"] is not None,
            mapping.observation_encounter_policy,
            counts,
            "observation_",
        )
        if times is not None:
            path.observation_end = times[0]
            if path.creation is not None and times[0] <= path.creation[0]:
                invalid = True
                counts["invalid_observation_end"] += 1
            # Retrospective coverage availability is not a cutoff feature.
        path.invalid |= invalid

    administration_ids = {}
    for row in _bounded(administration_rows, MAX_ADMINISTRATIONS):
        counts["administration_rows"] += 1
        key = identity(row.get("order_id"))
        event_id = identity(row.get("administration_id"))
        path = paths.get(key)
        if path is None:
            raise RecurrentTaskError("recurrent_unselected_order_link")
        invalid = event_id is None
        if event_id is None:
            counts["invalid_administration_identity"] += 1
        elif event_id in administration_ids:
            paths[administration_ids[event_id]].invalid = True
            invalid = True
            counts["duplicate_administration_identities"] += 1
        else:
            administration_ids[event_id] = key
        if identity(row.get("patient_id")) != path.patient:
            invalid = True
            counts["patient_mismatches"] += 1
        invalid |= check_encounter(
            path,
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
            counts["qualifying_rows"] += 1
            availability = "available_at"
            if mapping.occurrence_equality_policy is not None:
                availability = "occurred_at"
                policy = mapping.occurrence_equality_policy
                status = identity(row.get("documentation_status"))
                if status not in policy.contemporaneous_values:
                    invalid = True
                    counts[
                        "retrospective_execution_rows"
                        if status in policy.retrospective_values
                        else "unresolved_documentation_rows"
                    ] += 1
            times, bad = pair(row, "occurred_at", availability, mapping, counts)
            invalid |= bad
            if times is not None:
                if path.creation is not None and times[0] <= path.creation[0]:
                    invalid = True
                    counts["execution_before_or_at_creation"] += 1
                path.events.append(times)
        path.invalid |= invalid

    for path in paths.values():
        path.events.sort()
        terminal = min((t[0] for t in path.terminals), default=math.inf)
        if any(t[0] >= terminal for t in path.events):
            path.invalid = True
            counts["execution_at_or_after_terminal_orders"] += 1
        counts["invalid_paths"] += int(path.invalid)
        counts["valid_paths"] += int(not path.invalid)
        observed_events = [
            times
            for times in path.events
            if path.observation_end is not None and known_by(*times, path.observation_end)
        ]
        counts["valid_recurrent_paths"] += int(not path.invalid and len(observed_events) > 1)
        counts["paths_with_multiple_qualifying_rows"] += int(len(path.events) > 1)
        if not path.invalid:
            counts["tied_event_paths"] += int(len({t[0] for t in path.events}) < len(path.events))
    return paths, bad_rosters


def _window(patient, cutoff, roster, bad_rosters):
    keys = tuple(path.key for path in roster)
    histories = tuple(
        tuple(
            (cutoff - occurred, cutoff - available)
            for occurred, available in path.events
            if cutoff - LOOKBACK_HOURS <= occurred <= cutoff
            and known_by(occurred, available, cutoff)
        )
        for path in roster
    )
    args = (patient, cutoff, keys, histories)
    if patient in bad_rosters:
        return Window(*args, "unresolved_roster")
    if len(roster) > MAX_ROSTER:
        return Window(*args, "oversized_roster")
    if any(path.invalid for path in roster):
        return Window(*args, "invalid_path")
    boundary = min(cutoff + HORIZON_HOURS, *(path.observation_end for path in roster))
    if boundary <= cutoff:
        return Window(*args, "no_common_followup", observed_hours=0.0)
    prefix, complete, endpoints = [], [], []
    for path in roster:
        terminal = min((t[0] for t in path.terminals if known_by(*t, boundary)), default=math.inf)
        endpoint = min(boundary, terminal)
        # A late-available occurrence within this target cannot be silently discarded.
        if any(
            cutoff < occurred <= endpoint and available > boundary
            for occurred, available in path.events
        ):
            return Window(*args, "unresolved_outcome_availability")
        count = sum(cutoff < occurred <= endpoint for occurred, _ in path.events)
        kind = (
            "terminal"
            if terminal <= boundary
            else "horizon"
            if boundary == cutoff + HORIZON_HOURS
            else "right_censored"
        )
        prefix.append(count)
        complete.append(count if kind != "right_censored" else None)
        endpoints.append(kind)
    return Window(
        *args,
        "ascertained" if all(value is not None for value in complete) else "partial",
        observed_hours=boundary - cutoff,
        prefix_counts=tuple(prefix),
        horizon_counts=tuple(complete),
        endpoint_kinds=tuple(endpoints),
    )


def audit_recurrent_rows(
    order_rows,
    administration_rows,
    observation_rows,
    mapping: Mapping,
    patients: frozenset,
    *,
    coverage_complete: bool,
    data_class: str,
    synthetic_windows: list | None = None,
):
    """Aggregate a complete selected-patient snapshot; access must prove completeness.

    The synthetic-only sink enables independent leakage/censoring tests. The clinical
    caller cannot request window rows. No identity appears in the returned report.
    """
    if (
        data_class not in {"synthetic", "restricted_clinical"}
        or not isinstance(patients, frozenset)
        or not patients
        or len(patients) > 32
        or any(
            not isinstance(patient, tuple) or len(patient) != 2 or identity(patient[1]) != patient
            for patient in patients
        )
        or type(coverage_complete) is not bool
        or (synthetic_windows is not None and data_class != "synthetic")
    ):
        raise RecurrentTaskError("recurrent_invalid_contract")
    base = {
        "schema_version": 1,
        "mode": MODE,
        "data_class": "synthetic" if data_class == "synthetic" else "restricted_aggregate",
        "status": "complete" if coverage_complete else "limited",
        "coverage_scope": "selected_original_training_patients_all_mapped_orders",
        "roster_definition": "recent_known_orders_excluding_known_terminals",
        "lookback_hours": LOOKBACK_HOURS,
        "diagnostic_horizon_hours": HORIZON_HOURS,
        "max_anchors_per_patient": MAX_ANCHORS,
        "model_fitted": False,
        "validation_split_evaluated": False,
        "test_split_evaluated": False,
        "row_persistence": False,
        "publication_readiness": "not_established",
        "counts": None,
        "window_status_counts": None,
    }
    # Incomplete scans cannot even certify empty or single-event paths.
    if not coverage_complete:
        return base
    counts = Counter()
    paths, bad_rosters = _paths(
        order_rows, administration_rows, observation_rows, mapping, patients, counts
    )
    grouped = defaultdict(list)
    for path in paths.values():
        if path.patient in patients and path.creation is not None:
            grouped[path.patient].append(path)
    statuses = Counter()
    sizes = Counter(dict.fromkeys(("one", "two_to_four", "five_to_sixteen", "over_sixteen"), 0))
    for patient in sorted(patients):
        members = sorted(grouped[patient], key=lambda path: path.key)
        anchors = sorted({path.creation[1] for path in members})
        counts["patients"] += 1
        counts["patients_with_invalid_roster"] += int(patient in bad_rosters)
        counts["patients_without_orders"] += int(not members)
        counts["anchors_outside_fixed_domain"] += max(0, len(anchors) - MAX_ANCHORS)
        for cutoff in anchors[:MAX_ANCHORS]:
            roster = [
                path
                for path in members
                if cutoff - LOOKBACK_HOURS <= path.creation[0]
                and known_by(*path.creation, cutoff)
                and not any(known_by(*terminal, cutoff) for terminal in path.terminals)
            ]
            if not roster:
                counts["empty_roster_anchors"] += 1
                continue
            window = _window(patient, cutoff, roster, bad_rosters)
            counts["candidate_windows"] += 1
            multiple = len(roster) >= 2
            counts["multiorder_candidate_windows"] += int(multiple)
            statuses[window.status] += 1
            if multiple:
                counts["multiorder_ascertained_windows"] += int(window.status == "ascertained")
                counts["multiorder_partial_windows"] += int(window.status == "partial")
                counts["multiorder_windows_with_recurrent_history"] += int(
                    window.status in {"ascertained", "partial"}
                    and any(len(history) >= 2 for history in window.history)
                )
            size = (
                "one"
                if len(roster) == 1
                else "two_to_four"
                if len(roster) <= 4
                else "five_to_sixteen"
                if len(roster) <= 16
                else "over_sixteen"
            )
            sizes[size] += 1
            if synthetic_windows is not None:
                synthetic_windows.append(window)
    base.update(
        counts=dict(sorted(counts.items())),
        window_status_counts=dict(sorted(statuses.items())),
        roster_size_counts=dict(sizes),
        interpretation=(
            "Task support in a fixed selected domain only; no prediction, sample sufficiency, "
            "causal competition or population claim. Future quality exclusions remain explicit."
        ),
    )
    return base
