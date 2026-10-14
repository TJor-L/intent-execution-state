from dataclasses import replace

import pytest

from ies.data.events import CAUSES
from ies.preprocessing.cohort import available_history, build_cohort, patient_partitions


def test_patient_exclusive_and_seeded_splits(events):
    cohort = build_cohort(events, 7)
    groups = {
        split: {r["patient_id"] for r in cohort if r["split"] == split}
        for split in ("train", "validation", "test")
    }
    assert all(groups.values())
    assert not (groups["train"] & groups["test"])
    assert not (groups["train"] & groups["validation"])
    assert not (groups["test"] & groups["validation"])
    patients = [e.patient_id for e in events]
    assert patient_partitions(patients, 7) == patient_partitions(list(reversed(patients)), 7)
    assert patient_partitions(patients, 7) != patient_partitions(patients, 8)
    with pytest.raises(ValueError):
        patient_partitions(["a", "b"], 7)


def test_information_available_at_cutoff_only(events):
    for order in (e for e in events if e.event_type == "order"):
        history = available_history(events, order, 24)
        assert order in history
        assert all(
            e.event_time <= order.event_time and e.available_time <= order.event_time
            for e in history
        )
        assert not any(e.event_id.endswith(("obs-delayed", "obs-future")) for e in history)
    changed = [replace(e, value=1e10) if e.event_id.endswith("obs-delayed") else e for e in events]
    original = build_cohort(events, 7)
    assert original == build_cohort(changed, 7)
    assert all(r["features"]["observation_count"] == 2 for r in original)


def test_censoring_not_labeled_as_failure_and_horizon_truncation(events):
    cohort = build_cohort(events, 7)
    by_order = {e.order_id: e for e in events if e.event_type in CAUSES}
    for row in cohort:
        outcome = by_order.get(row["order_id"])
        assert row["cause"] == (CAUSES.index(outcome.event_type) + 1 if outcome else 0)
    short = build_cohort(events, 7, horizon_hours=0.001)
    assert all(r["cause"] == 0 for r in short)
    assert all(r["duration"] == pytest.approx(0.001) for r in short)
