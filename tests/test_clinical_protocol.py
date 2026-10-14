"""Generated-only tests for the data-free clinical cohort protocol gate."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from ies.cli import main
from ies.clinical_protocol import ProtocolError, plan_protocol

ROOT = Path(__file__).resolve().parents[1]


def draft() -> dict:
    return yaml.safe_load((ROOT / "configs/clinical_protocol.example.yaml").read_text())


def frozen() -> dict:
    value = draft()
    value["status"] = "frozen"
    value["population"].update(
        adult_derivation_reviewed=True,
        adult_derivation_evidence_reference="toy adult review",
        inpatient_definition_reviewed=True,
        inpatient_definition_evidence_reference="toy inpatient review",
        medication_categories=["toy-category"],
        medication_category_system="toy-system",
        medication_eligibility_reviewed=True,
        medication_eligibility_evidence_reference="toy medication review",
    )
    value["acceptance"].update(
        minimum_eligible_orders=100,
        minimum_execution_events=20,
    )
    return value


def write(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "clinical_protocol.local.yaml"
    path.write_text(yaml.safe_dump(value, sort_keys=False))
    return path


def test_draft_plan_lists_only_generic_missing_decisions(tmp_path):
    plan = plan_protocol(write(tmp_path, draft()))
    assert plan["ready_for_extraction"] is False
    assert set(plan["missing_decisions"]) == {
        "adult_derivation_review",
        "inpatient_definition_review",
        "medication_eligibility_review",
        "minimum_eligible_orders",
        "minimum_execution_events",
    }
    rendered = yaml.safe_dump(plan)
    assert "medication_categories" not in rendered and "evidence_reference" not in rendered


def test_frozen_protocol_is_ready_and_preserves_invariants(tmp_path):
    plan = plan_protocol(write(tmp_path, frozen()))
    assert plan["ready_for_extraction"] is True and plan["missing_decisions"] == []
    assert plan["patient_level_split"] is True
    assert plan["global_calendar_split"] is False
    assert plan["first_execution_only"] is True
    assert plan["repeated_administrations_rejected"] is True
    assert plan["laboratory_features_enabled"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(extra=True),
        lambda value: value["temporal"].update(global_calendar_split=True),
        lambda value: value["task"].update(repeated_administrations="keep_first"),
        lambda value: value["population"].update(minimum_age_years=16),
        lambda value: value["population"].update(medication_categories=["a", "b", "c"]),
        lambda value: value["acceptance"].update(minimum_execution_events=0),
    ],
)
def test_invalid_protocols_fail_closed(tmp_path, mutation):
    value = draft()
    mutation(value)
    with pytest.raises(ProtocolError, match="invalid_clinical_protocol"):
        plan_protocol(write(tmp_path, value))


def test_frozen_protocol_rejects_each_unresolved_gate(tmp_path):
    value = frozen()
    cases = []
    for section, name, replacement in (
        ("population", "adult_derivation_evidence_reference", None),
        ("population", "inpatient_definition_reviewed", False),
        ("population", "medication_categories", []),
        ("acceptance", "minimum_eligible_orders", None),
        ("acceptance", "minimum_execution_events", None),
    ):
        case = deepcopy(value)
        case[section][name] = replacement
        cases.append(case)
    for case in cases:
        with pytest.raises(ProtocolError, match="invalid_clinical_protocol"):
            plan_protocol(write(tmp_path, case))


def test_cli_plan_reads_no_clinical_source_and_emits_no_private_values(
    tmp_path, monkeypatch, capsys
):
    path = write(tmp_path, frozen())
    monkeypatch.setattr("sys.argv", ["ies", "protocol-plan", "--protocol", str(path)])
    assert main() == 0
    output = capsys.readouterr().out
    assert "toy-category" not in output and "toy adult review" not in output
    assert yaml.safe_load(output)["ready_for_extraction"] is True
