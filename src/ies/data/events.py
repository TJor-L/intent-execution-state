"""Canonical synthetic event contract. Times are patient-relative hours."""

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

CAUSES = ("administration", "cancellation", "other_terminal")
EVENT_TYPES = {"observation", "order", "followup_end", *CAUSES}


@dataclass(frozen=True)
class Event:
    event_id: str
    patient_id: str
    encounter_id: str
    event_type: str
    code: str
    event_time: float
    available_time: float
    order_id: str | None = None
    value: float | None = None
    synthetic: bool = True


EVENT_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("patient_id", pa.string()),
        ("encounter_id", pa.string()),
        ("event_type", pa.string()),
        ("code", pa.string()),
        ("event_time", pa.float64()),
        ("available_time", pa.float64()),
        ("order_id", pa.string()),
        ("value", pa.float64()),
        ("synthetic", pa.bool_()),
    ],
    metadata={b"ies_schema_version": b"1", b"ies_data_class": b"synthetic"},
)


def validate_events(events: list[Event]) -> dict:
    """Fail without revealing row values, identifiers, or source records."""
    if not events:
        raise ValueError("Event collection is empty")
    ids = set()
    orders = {}
    linked = defaultdict(list)
    for event in events:
        if event.synthetic is not True:
            raise ValueError(
                "This MVP accepts synthetic events only; UCSF adapter is not implemented"
            )
        if any(
            not isinstance(value, str) or not value
            for value in (event.event_id, event.patient_id, event.encounter_id, event.code)
        ):
            raise ValueError("Missing event identity or code")
        if event.event_id in ids:
            raise ValueError("Duplicate event identifier")
        ids.add(event.event_id)
        if event.event_type not in EVENT_TYPES:
            raise ValueError("Unknown event type")
        if not all(
            isinstance(t, (int, float)) and math.isfinite(t)
            for t in (event.event_time, event.available_time)
        ):
            raise ValueError("Invalid event time")
        if event.available_time < event.event_time:
            raise ValueError("Availability precedes occurrence")
        if event.event_type == "observation":
            if event.order_id is not None:
                raise ValueError("Observation must not imply an unverified order linkage")
            if event.value is None or not math.isfinite(event.value):
                raise ValueError("Observation requires finite numeric value")
            continue
        if event.value is not None:
            raise ValueError("Non-observation event must not carry a measured value")
        if not isinstance(event.order_id, str) or not event.order_id:
            raise ValueError("Order-linked event requires order identifier")
        if event.event_type == "order":
            if event.order_id in orders:
                raise ValueError("Duplicate order identifier")
            if event.available_time != event.event_time:
                raise ValueError("MVP requires order creation available at index time")
            orders[event.order_id] = event
        else:
            linked[event.order_id].append(event)
    if not orders:
        raise ValueError("No orders found")
    if set(linked) - set(orders):
        raise ValueError("Orphan order linkage")
    for order_id, order in orders.items():
        children = linked[order_id]
        ends = [e for e in children if e.event_type == "followup_end"]
        terminal = [e for e in children if e.event_type in CAUSES]
        if len(ends) != 1:
            raise ValueError("Each order needs exactly one observable followup boundary")
        if len(terminal) > 1:
            raise ValueError("Repeated or conflicting outcomes unsupported by first-event MVP")
        for child in children:
            if (child.patient_id, child.encounter_id, child.code) != (
                order.patient_id,
                order.encounter_id,
                order.code,
            ):
                raise ValueError("Cross-patient, cross-encounter, or mismatched-code linkage")
            if child.event_time <= order.event_time:
                raise ValueError("Outcome/followup must occur strictly after order")
            if child.available_time > ends[0].event_time:
                raise ValueError("Outcome unavailable before observation boundary")
    return {"events": len(events), "orders": len(orders), "data_class": "synthetic"}


def write_events(path: Path, events: list[Event]) -> None:
    validate_events(events)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist([asdict(e) for e in events], schema=EVENT_SCHEMA), path)


def read_events(path: Path) -> list[Event]:
    # Read footer first: do not load an unmarked private Parquet file by mistake.
    with pq.ParquetFile(path) as parquet:
        if not parquet.schema_arrow.equals(EVENT_SCHEMA, check_metadata=True):
            raise ValueError("Expected canonical synthetic schema and provenance metadata")
        events = [Event(**row) for row in parquet.read().to_pylist()]
    validate_events(events)
    return events
