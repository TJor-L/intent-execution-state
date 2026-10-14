from dataclasses import replace

import pyarrow.parquet as pq
import pytest

from ies.data.events import CAUSES, read_events, validate_events, write_events
from ies.data.synthetic import generate_events


def changed(events, kind, **updates):
    index = next(i for i, event in enumerate(events) if event.event_type == kind)
    result = list(events)
    result[index] = replace(result[index], **updates)
    return result


def test_deterministic_generation_and_explicit_censoring(events):
    assert events == generate_events(n_patients=40, seed=81)
    assert set(CAUSES) <= {e.event_type for e in events}
    terminal_orders = {e.order_id for e in events if e.event_type in CAUSES}
    assert len(terminal_orders) < sum(e.event_type == "order" for e in events)
    validate_events(list(reversed(events)))


def test_roundtrip_and_private_provenance_rejection(events, tmp_path):
    path = tmp_path / "synthetic.parquet"
    write_events(path, events)
    assert read_events(path) == events
    table = pq.read_table(path).replace_schema_metadata(None)
    pq.write_table(table, path)
    with pytest.raises(ValueError, match="synthetic schema"):
        read_events(path)


@pytest.mark.parametrize(
    "kind,updates,reason",
    [
        ("administration", {"order_id": "orphan"}, "Orphan"),
        ("administration", {"patient_id": "different"}, "Cross-patient"),
        ("administration", {"encounter_id": "different"}, "Cross-patient"),
        ("administration", {"code": "different"}, "mismatched-code"),
        ("administration", {"event_time": -1.0}, "strictly after"),
        ("administration", {"available_time": 1e9}, "unavailable"),
        ("order", {"event_time": float("nan")}, "Invalid event time"),
        ("order", {"available_time": 1e9}, "creation available"),
        ("order", {"synthetic": False}, "synthetic events only"),
        ("observation", {"value": float("nan")}, "finite numeric"),
        ("observation", {"available_time": -1e9}, "Availability precedes"),
    ],
)
def test_reject_invalid_events(events, kind, updates, reason):
    with pytest.raises(ValueError, match=reason):
        validate_events(changed(events, kind, **updates))


def test_reject_duplicate_conflicting_outcomes_and_missing_followup(events):
    administration = next(e for e in events if e.event_type == "administration")
    with pytest.raises(ValueError, match="Duplicate event"):
        validate_events(events + [administration])
    other = replace(administration, event_id="extra", event_type="cancellation")
    with pytest.raises(ValueError, match="Repeated or conflicting"):
        validate_events(events + [other])
    with pytest.raises(ValueError, match="followup boundary"):
        validate_events([e for e in events if e.event_type != "followup_end"])
