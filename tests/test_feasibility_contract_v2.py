"""Generated fixtures exercise the server's contract gaps without importing its data."""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from test_feasibility import case as case
from test_feasibility import enable_equality, result, write_sources

from ies.cli import main
from ies.feasibility import runner
from ies.feasibility.contract import FeasibilityError, parse_mapping
from ies.feasibility.reader import inspect_sources
from ies.feasibility.time import time_value


def enable_naive(case, clock="named_timezone", ambiguous="reject"):
    case[0]["time_encoding"] = "timestamp_naive"
    case[0]["naive_time_policy"] = {
        "reviewed": True,
        "clock": clock,
        "timezone": "America/Los_Angeles" if clock == "named_timezone" else None,
        "ambiguous": ambiguous,
        "nonexistent": "reject",
        "evidence_reference": "toy-private-time-review",
    }


def convert_times(case, base):
    for row in case[1:]:
        for field, value in row.items():
            if field.endswith("_at") and value is not None:
                row[field] = base + timedelta(hours=value)


@pytest.mark.parametrize("encoding", ["numeric_hours", "timestamp_utc", "timestamp_naive"])
def test_naive_timestamps_need_explicit_review(case, encoding):
    case[0]["time_encoding"] = encoding
    convert_times(case, datetime(2126, 1, 1))
    if encoding == "timestamp_naive":
        with pytest.raises(FeasibilityError, match="invalid_mapping"):
            result(case)
    else:
        counts = result(case)["counts"]
        assert counts["invalid_time_values"] == 3
        assert counts["accepted_execution_orders"] == counts["right_censored_orders"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewed", False),
        ("timezone", None),
        ("timezone", "toy-private-invalid-zone"),
        ("clock", "guess"),
        ("evidence_reference", " "),
        ("ambiguous", "guess"),
        ("nonexistent", "shift_forward"),
    ],
)
def test_time_policy_fails_closed(case, field, value):
    enable_naive(case)
    case[0]["naive_time_policy"][field] = value
    with pytest.raises(FeasibilityError, match="^invalid_mapping$"):
        parse_mapping(case[0])


def test_reviewed_zone_normalizes_to_utc_without_host_timezone(case, monkeypatch):
    enable_naive(case)
    mapping = parse_mapping(case[0])
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    actual = time_value(datetime(2026, 1, 10, 12), mapping)
    utc_mapping = replace(mapping, time_encoding="timestamp_utc", naive_time_policy=None)
    assert actual == time_value(datetime(2026, 1, 10, 20, tzinfo=UTC), utc_mapping)
    offset = timezone(timedelta(hours=9))
    assert actual == time_value(datetime(2026, 1, 11, 5, tzinfo=offset), utc_mapping)
    assert time_value(datetime(2026, 1, 10, 12, tzinfo=UTC), mapping) is None
    assert time_value("2026-01-10T12:00:00", mapping) is None


@pytest.mark.parametrize("ambiguous", ["reject", "earlier", "later"])
def test_dst_overlap_and_nonexistent_times(case, ambiguous):
    enable_naive(case, ambiguous=ambiguous)
    mapping = parse_mapping(case[0])
    overlap = datetime(2026, 11, 1, 1, 30)
    actual = time_value(overlap, mapping)
    if ambiguous == "reject":
        assert actual is None
        assert time_value(overlap.replace(fold=1), mapping) is None
    else:
        expected_hour = 8 if ambiguous == "earlier" else 9
        utc_mapping = replace(mapping, time_encoding="timestamp_utc", naive_time_policy=None)
        assert actual == time_value(
            datetime(2026, 11, 1, expected_hour, 30, tzinfo=UTC), utc_mapping
        )
    # An explicit overlap choice never legitimizes a nonexistent spring-forward time.
    assert time_value(datetime(2026, 3, 8, 2, 30), mapping) is None


def test_dst_conversion_changes_elapsed_horizon_correctly_through_parquet(case):
    enable_naive(case)
    case[0]["horizon_hours"] = 1
    case[1].update(
        occurred_at=datetime(2026, 3, 8, 1, 30), available_at=datetime(2026, 3, 8, 1, 30)
    )
    case[2].update(occurred_at=datetime(2026, 3, 8, 3), available_at=datetime(2026, 3, 8, 3, 10))
    case[3].update(ended_at=datetime(2026, 3, 8, 4), available_at=datetime(2026, 3, 8, 4))
    # 30 minutes actually elapsed across the clock jump, not 90 minutes.
    counts = inspect_sources(write_sources(case))["counts"]
    assert counts["accepted_execution_orders"] == 1
    assert counts["right_censored_orders"] == 0


def test_shifted_clock_is_common_within_patient_not_civil_or_current_calendar(case):
    enable_naive(case, clock="shifted_common")
    convert_times(case, datetime(2126, 1, 1))
    assert inspect_sources(write_sources(case))["counts"]["accepted_execution_orders"] == 1
    mapping = parse_mapping(case[0])
    # A synthetic shifted clock need not obey civil daylight-saving transitions.
    assert time_value(datetime(2026, 3, 8, 2, 30), mapping) is not None
    case[0]["naive_time_policy"]["timezone"] = "UTC"
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


@pytest.mark.parametrize(
    "field,value,counter",
    [
        ("patient_id", "toy-other", "observation_patient_mismatches"),
        ("patient_id", None, "missing_observation_identities"),
        ("observation_id", None, "missing_observation_identities"),
        ("encounter_id", "toy-other", "observation_encounter_mismatches"),
        ("encounter_id", None, "observation_encounter_missing_links"),
        ("ended_at", None, "missing_required_times"),
        ("available_at", None, "missing_required_times"),
        ("available_at", 71.0, "temporal_ordering_violations"),
        ("ended_at", 47.0, "temporal_ordering_violations"),
        ("ended_at", "toy-not-a-time", "invalid_time_values"),
    ],
)
def test_observation_link_or_time_problems_reject_order(case, field, value, counter):
    case[3][field] = value
    counts = result(case)["counts"]
    assert counts[counter] == counts["rejected_orders"] == 1
    assert counts["accepted_execution_orders"] == counts["right_censored_orders"] == 0


@pytest.mark.parametrize("encounter", [None, "toy-other"])
def test_observation_encounter_count_only_never_relaxes_patient_match(case, encounter):
    case[0]["observation_encounter_policy"] = "count_only"
    case[3]["encounter_id"] = encounter
    counts = result(case)["counts"]
    assert counts["accepted_execution_orders"] == 1
    assert (
        counts[
            "observation_encounter_missing_links"
            if encounter is None
            else "observation_encounter_mismatches"
        ]
        == 1
    )
    case[3]["patient_id"] = "toy-other"
    assert result(case)["counts"]["accepted_execution_orders"] == 0


def test_optional_observation_encounter_mapping_is_reported_as_unavailable(case):
    case[0]["observations"]["columns"]["encounter_id"] = None
    counts = result(case)["counts"]
    assert counts["observation_encounter_checks_unavailable"] == 1
    assert counts["accepted_execution_orders"] == 1


@pytest.mark.parametrize("missing", ["no_row", "no_link", "unmatched", "typed_identity"])
def test_missing_coverage_cannot_fall_back_to_order_end_or_censoring(case, missing):
    observations = [case[3]]
    if missing == "no_row":
        observations = []
    elif missing == "no_link":
        case[1]["observation_id"] = None
    elif missing == "unmatched":
        case[1]["observation_id"] = "toy-unmatched"
    else:
        case[1]["observation_id"], case[3]["observation_id"] = 1, "1"
    case[1].update(ended_at=49.0, ended_available_at=49.0)
    counts = result(case, administrations=[], observations=observations)["counts"]
    assert counts["unmatched_observation_links"] == counts["rejected_orders"] == 1
    assert counts["terminal_without_execution_orders"] == counts["right_censored_orders"] == 0


def test_observation_duplicate_rejects_all_linked_orders(case):
    orders = [case[1], dict(case[1], order_id="toy-order-1")]
    counts = result(case, orders=orders, administrations=[])["counts"]
    assert counts["matched_observation_links"] == counts["right_censored_orders"] == 2
    counts = result(case, orders=orders, observations=[case[3], dict(case[3])])["counts"]
    assert counts["duplicate_observation_identities"] == 1
    assert counts["rejected_orders"] == 2
    assert counts["accepted_execution_orders"] == counts["right_censored_orders"] == 0


def test_observation_availability_is_ascertainment_not_extra_followup(case):
    case[3].update(ended_at=49.0, available_at=100.0)
    counts = result(case)["counts"]
    assert counts["observation_endpoint_unavailable_at_boundary_orders"] == 1
    assert counts["right_censored_orders"] == 1
    assert counts["accepted_execution_orders"] == 0  # The dose at 50 is after followup ends.
    case[3].update(ended_at=100.0, available_at=100.0)
    case[2].update(occurred_at=73.0, available_at=73.0)
    assert result(case)["counts"]["right_censored_orders"] == 1  # Horizon still ends at 72.


def test_third_source_row_truncation_prevents_any_outcome_claim(case):
    mapping = write_sources(case, observations=[case[3], dict(case[3])])
    mapping = replace(mapping, limits=replace(mapping.limits, max_rows_per_source=1, batch_rows=1))
    report = inspect_sources(mapping)
    assert report["status"] == "limited" and report["limits_reached"]["rows"]
    assert report["counts"]["considered_observations"] == 1
    assert report["counts"]["unresolved_due_to_limits_orders"] == 1
    assert (
        report["counts"]["accepted_execution_orders"]
        == report["counts"]["right_censored_orders"]
        == 0
    )


@pytest.mark.parametrize(
    "bound,flag",
    [
        ("max_files_per_source", "files"),
        ("max_directories_per_source", "directories"),
        ("max_entries_per_source", "entries"),
    ],
)
def test_third_source_filesystem_limits(case, tmp_path, bound, flag):
    mapping = write_sources(case)
    root = tmp_path / "observation-shards"
    for i in range(3):
        folder = root / str(i)
        folder.mkdir(parents=True)
        (folder / "shard.parquet").write_bytes(mapping.observations.path.read_bytes())
    mapping = replace(
        mapping,
        observations=replace(mapping.observations, path=root),
        limits=replace(mapping.limits, **{bound: 1}),
    )
    report = inspect_sources(mapping)
    assert report["status"] == "limited" and report["limits_reached"][flag]
    assert report["counts"]["accepted_execution_orders"] == 0


def test_observation_keys_share_the_global_budget(case):
    mapping = write_sources(case)
    for maximum in (1, 2):
        report = inspect_sources(replace(mapping, limits=replace(mapping.limits, max_keys=maximum)))
        assert report["status"] == "limited" and report["limits_reached"]["keys"]
        assert report["counts"]["accepted_execution_orders"] == 0
    report = inspect_sources(replace(mapping, limits=replace(mapping.limits, max_keys=3)))
    assert report["status"] == "complete" and report["counts"]["accepted_execution_orders"] == 1


@pytest.mark.parametrize("field", ["reviewed", "evidence_reference"])
@pytest.mark.parametrize("section", ["equality", "exclusion"])
def test_equality_and_exclusion_both_need_review_and_evidence(case, field, section):
    enable_equality(case)
    policy = case[0]["occurrence_equality_policy"]
    if section == "exclusion":
        policy = policy["retrospective_exclusion"]
    policy[field] = False if field == "reviewed" else " "
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


def test_equality_requires_mapped_disjoint_documentation_classes(case):
    enable_equality(case)
    policy = case[0]["occurrence_equality_policy"]["retrospective_exclusion"]
    policy["retrospective_values"] = ["toy-live"]
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])
    policy["retrospective_values"] = []
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])
    policy["retrospective_values"] = ["toy-retro"]
    case[0]["administrations"]["columns"]["documentation_status"] = None
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


@pytest.mark.parametrize("status", ["toy-retro", None, "toy-unknown"])
def test_retrospective_or_unknown_dose_rejects_order_without_false_censoring(case, status):
    enable_equality(case)
    case[2]["documentation_status"] = status
    counts = inspect_sources(write_sources(case))["counts"]
    assert counts["excluded_documentation_orders"] == counts["rejected_orders"] == 1
    assert (
        counts[
            "retrospective_execution_rows"
            if status == "toy-retro"
            else "unresolved_documentation_rows"
        ]
        == 1
    )
    assert counts["accepted_execution_orders"] == counts["right_censored_orders"] == 0
    second = dict(case[2], administration_id="toy-dose-1", documentation_status="toy-live")
    counts = result(case, administrations=[case[2], second])["counts"]
    assert counts["repeated_qualifying_orders"] == 1
    assert counts["accepted_execution_orders"] == 0


def test_equality_accepts_only_reviewed_class_and_never_exports_evidence(case):
    enable_equality(case)
    report = inspect_sources(write_sources(case))
    assert report["counts"]["accepted_execution_orders"] == 1
    assert "toy-" not in json.dumps(report) and "evidence" not in json.dumps(report)


def test_independent_availability_cannot_be_bypassed_by_equality_metadata(case):
    case[2]["available_at"] = None
    assert result(case)["counts"]["rejected_orders"] == 1
    case[0]["occurrence_equality_policy"] = {"reviewed": True}
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


def test_v1_configs_are_rejected_without_silent_semantic_migration(case):
    case[0]["schema_version"] = 1
    with pytest.raises(FeasibilityError):
        parse_mapping(case[0])


def test_third_source_is_protected_from_output_overlap(case, tmp_path, monkeypatch):
    case[0]["observations"]["path"] = str(tmp_path / "coverage")
    path = tmp_path / "mapping.local.yaml"
    path.write_text(yaml.safe_dump(case[0]))
    monkeypatch.setattr(runner, "verify_execution_context", lambda: None)
    with pytest.raises(FeasibilityError, match="invalid_output_boundary"):
        runner.run_feasibility(path, tmp_path / "coverage/out")
    assert not (tmp_path / "coverage").exists()


def test_reviewed_clock_plan_reads_only_config_and_sanitizes_bad_zone(
    case, tmp_path, monkeypatch, capsys
):
    enable_naive(case)
    enable_equality(case)
    path = tmp_path / "mapping.local.yaml"
    path.write_text(yaml.safe_dump(case[0]))
    original_read = Path.read_bytes

    def config_only_read(self):
        assert self == path
        return original_read(self)

    monkeypatch.setattr(Path, "read_bytes", config_only_read)
    monkeypatch.setattr(Path, "stat", lambda *a, **k: pytest.fail("Planning inspected storage"))
    monkeypatch.setattr(os, "scandir", lambda *a: pytest.fail("Planning traversed storage"))
    assert main(["feasibility", "plan", "--mapping", str(path)]) == 0
    output = capsys.readouterr()
    assert "toy-" not in output.out and str(tmp_path) not in output.out
    case[0]["naive_time_policy"]["timezone"] = "toy-private-zone-sentinel"
    path.write_text(yaml.safe_dump(case[0]))
    with pytest.raises(SystemExit) as error:
        main(["feasibility", "plan", "--mapping", str(path)])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert "toy-private" not in output.err and str(tmp_path) not in output.err
