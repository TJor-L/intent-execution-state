"""Adversarial generated records for the separate recurrent task contract."""

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from ies.feasibility.analysis import analyze
from ies.feasibility.contract import EqualityPolicy
from ies.recurrent_task import RecurrentTaskError, audit_recurrent_rows
from ies.recurrent_task_demo import generated_case, run_generated_cases


def run(case, **kwargs):
    mapping, orders, administrations, observations, patients = case
    windows = []
    report = audit_recurrent_rows(
        orders,
        administrations,
        observations,
        mapping,
        patients,
        coverage_complete=kwargs.pop("coverage_complete", True),
        data_class=kwargs.pop("data_class", "synthetic"),
        synthetic_windows=windows if not kwargs.pop("private", False) else None,
        **kwargs,
    )
    return report, windows


def test_recurrence_and_joint_history_without_changing_original_first_execution_rules():
    case = generated_case()
    report, windows = run(case)
    assert report["counts"]["valid_recurrent_paths"] == 2
    assert windows[-1].cutoff == 2
    assert windows[-1].history == (((1.5, 1.5), (0.5, 0.5)), (), ())
    assert windows[-1].horizon_counts == (1, 2, 0)
    old = analyze(case[1], case[2], case[3], case[0])
    assert old["counts"]["repeated_qualifying_orders"] == 2
    assert old["counts"]["rejected_orders"] == 2
    assert "toy_" not in json.dumps(report)


def test_censoring_retains_roster_and_unknown_tail_instead_of_zero():
    case = generated_case()
    case[3][1]["ended_at"] = 3.0
    report, windows = run(case)
    window = windows[-1]
    assert window.status == "partial"
    assert len(window.order_keys) == 3
    assert window.observed_hours == 1
    assert window.prefix_counts == (1, 1, 0)
    assert window.horizon_counts == (None, None, None)
    assert window.endpoint_kinds == ("right_censored",) * 3
    assert report["counts"]["multiorder_partial_windows"] == 2


def test_terminal_and_observation_end_are_distinct_and_future_terminal_not_an_input():
    case = generated_case()
    _, original = run(case)
    case[3][1]["ended_at"] = 3.0
    case[1][2].update(ended_at=2.5, ended_available_at=2.5)
    _, windows = run(case)
    window = windows[-1]
    assert window.order_keys == original[-1].order_keys
    assert window.history == original[-1].history
    assert window.horizon_counts == (None, None, 0)
    assert window.endpoint_kinds == ("right_censored", "right_censored", "terminal")
    case[1][2].update(ended_at=2.5, ended_available_at=10)
    assert run(case)[1][-1].horizon_counts == (None, None, None)


def test_future_changes_do_not_change_cutoff_membership_or_available_history():
    case = generated_case()
    _, original = run(case)
    cutoff = original[-1]
    case[2].append(dict(case[2][0], administration_id="toy_new", occurred_at=5, available_at=5))
    case[1].append(dict(case[1][2], order_id="toy_future", occurred_at=10, available_at=10))
    _, windows = run(case)
    same = next(window for window in windows if window.cutoff == cutoff.cutoff)
    assert (same.order_keys, same.history) == (cutoff.order_keys, cutoff.history)
    assert same.horizon_counts == (2, 2, 0)


def test_delayed_past_event_excluded_from_input_and_delayed_future_label_unresolved():
    case = generated_case()
    case[2][1]["available_at"] = 2.25
    _, windows = run(case)
    assert windows[-1].history[0] == ((1.5, 1.5),)
    assert windows[-1].horizon_counts == (1, 2, 0)
    case[2][2]["available_at"] = 20
    _, windows = run(case)
    assert windows[-1].status == "unresolved_outcome_availability"
    assert windows[-1].horizon_counts is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c[2][0].update(patient_id="toy_wrong"),
        lambda c: c[2][0].update(encounter_id="toy_wrong"),
        lambda c: c[2][0].update(administration_id=None),
        lambda c: c[2][0].update(available_at=-1),
        lambda c: c[2].append(deepcopy(c[2][0])),
        lambda c: c[3].append(deepcopy(c[3][0])),
        lambda c: c[3][0].update(patient_id="toy_wrong"),
        lambda c: c[1][0].update(observation_id="toy_absent"),
    ],
)
def test_bad_member_invalidates_joint_window_instead_of_improving_roster(mutation):
    case = generated_case()
    mutation(case)
    report, windows = run(case)
    assert windows[-1].status == "invalid_path"
    assert len(windows[-1].order_keys) == 3
    assert report["counts"]["multiorder_ascertained_windows"] == 0


def test_nonqualifying_actions_still_check_identity_and_encounter_policy_is_explicit():
    case = generated_case()
    case[2][0].update(action="toy_continuation", patient_id="toy_wrong")
    assert run(case)[1][-1].status == "invalid_path"
    case = generated_case()
    case[2][0].update(action="toy_continuation", encounter_id="toy_wrong")
    case = (replace(case[0], encounter_policy="count_only"), *case[1:])
    report, windows = run(case)
    assert windows[-1].status == "ascertained"
    assert report["counts"]["encounter_mismatches"] == 1
    assert len(windows[-1].history[0]) == 1


def test_equality_policy_rejects_whole_path_for_future_retrospective_or_unknown_record():
    for status, counter in (
        ("toy_late", "retrospective_execution_rows"),
        ("toy_unknown", "unresolved_documentation_rows"),
    ):
        case = generated_case()
        policy = EqualityPolicy(
            "generated_evidence",
            "generated_exclusion",
            frozenset({("string", "toy_current")}),
            frozenset({("string", "toy_late")}),
        )
        mapping = replace(
            case[0],
            administration_availability="occurrence_with_review",
            occurrence_equality_policy=policy,
        )
        for row in case[2]:
            row["documentation_status"] = "toy_current"
        case[2][-1]["documentation_status"] = status
        report, windows = run((mapping, *case[1:]))
        assert report["counts"][counter] == 1
        assert windows[-1].status == "invalid_path"


def test_terminal_tie_and_later_execution_reject_but_simultaneous_doses_are_retained():
    for terminal in (3.0, 2.9):
        case = generated_case()
        case[1][0].update(ended_at=terminal, ended_available_at=terminal)
        assert run(case)[1][-1].status == "invalid_path"
    case = generated_case()
    case[2].append(dict(case[2][2], administration_id="toy_tied"))
    report, windows = run(case)
    assert report["counts"]["tied_event_paths"] == 1
    assert windows[-1].horizon_counts[0] == 2


def test_incomplete_coverage_never_consumes_rows_or_confirms_empty_outcomes():
    def unread():
        raise AssertionError("Incomplete source must not be used to certify outcomes")
        yield

    case = generated_case()
    report, windows = run(
        (case[0], unread(), unread(), unread(), case[-1]), coverage_complete=False
    )
    assert report["status"] == "limited"
    assert report["counts"] is None and not windows


def test_duplicates_outside_patient_and_missing_creation_invalidate_roster():
    case = generated_case()
    case[1].append(dict(case[1][0], patient_id="toy_other"))
    assert all(w.status == "unresolved_roster" for w in run(case)[1])
    case = generated_case()
    case[1].append(dict(case[1][0], order_id="toy_bad_creation", available_at=None))
    assert all(w.status == "unresolved_roster" for w in run(case)[1])


def test_anchor_selection_and_large_roster_are_not_outcome_based():
    case = generated_case()
    case[1].extend(
        dict(case[1][0], order_id=f"toy_extra_{index}", occurred_at=2, available_at=2)
        for index in range(65)
    )
    window = run(case)[1][-1]
    assert window.status == "oversized_roster" and len(window.order_keys) == 68
    case = generated_case()
    case[1].extend(
        dict(
            case[1][0], order_id=f"toy_extra_{index}", occurred_at=index + 3, available_at=index + 3
        )
        for index in range(66)
    )
    report, windows = run(case)
    assert len(windows) == 64
    assert report["counts"]["anchors_outside_fixed_domain"] == 5


def test_private_sink_forbidden_and_generated_fixture_repeatable():
    with pytest.raises(RecurrentTaskError, match="recurrent_invalid_contract"):
        run(generated_case(), data_class="restricted_clinical")
    report, _ = run(generated_case(), data_class="restricted_clinical", private=True)
    assert report["data_class"] == "restricted_aggregate"
    assert run_generated_cases() == run_generated_cases()
