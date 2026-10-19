"""Generated mechanism, null, provenance and no-clinical-input regression checks."""

import json
from itertools import permutations
from pathlib import Path

import numpy as np
import pytest
import yaml

from ies import pairing_diagnostic as diagnostic
from ies.cli import main
from ies.io import sha256
from ies.models.paired_history import encode_clock_pairs

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path):
    value, _ = diagnostic.load_pairing_config(ROOT / "configs/synthetic_pairing.yaml")
    value.update(
        seeds=[20261016], train_patients=40, validation_patients=20, bootstrap_replicates=10
    )
    path = tmp_path / "synthetic.yaml"
    path.write_text(yaml.safe_dump(value))
    return path


def _history(availability):
    return [
        {"event_kind": 0, "occurrence_lag_hours": occurred, "availability_lag_hours": known}
        for occurred, known in zip([8.0, 4.0], availability, strict=True)
    ]


def test_joint_features_detect_pairing_with_identical_marginals_and_scales():
    first, second = _history([3.0, 1.0]), _history([1.0, 3.0])
    for mode in ("marginal", "unpaired"):
        np.testing.assert_allclose(
            encode_clock_pairs(first, [2, 12], mode),
            encode_clock_pairs(second, [2, 12], mode),
        )
    assert not np.allclose(
        encode_clock_pairs(first, [2, 12], "paired"),
        encode_clock_pairs(second, [2, 12], "paired"),
    )
    assert encode_clock_pairs(first, [2, 12], "unpaired").shape == (16,)
    for mode in diagnostic.MODES:
        np.testing.assert_allclose(
            encode_clock_pairs(first, [2, 12], mode),
            encode_clock_pairs(first[::-1], [2, 12], mode),
        )


def test_unpaired_control_is_exact_average_over_valid_pair_permutations():
    expected = np.mean(
        [
            encode_clock_pairs(_history(list(pairing)), [2, 12], "paired")
            for pairing in permutations([3.0, 1.0])
        ],
        axis=0,
    )
    np.testing.assert_allclose(
        encode_clock_pairs(_history([3.0, 1.0]), [2, 12], "unpaired"), expected
    )


def test_harmonic_basis_matches_joint_features_when_clocks_coincide():
    rows = _history([8.0, 4.0])
    np.testing.assert_array_equal(
        encode_clock_pairs(rows, [2, 12], "paired"),
        encode_clock_pairs(rows, [2, 12], "availability_basis"),
    )
    np.testing.assert_allclose(
        encode_clock_pairs(_history([3.0, 1.0]), [2, 12], "availability_basis"),
        encode_clock_pairs(_history([1.0, 3.0]), [2, 12], "availability_basis"),
    )


def test_stress_reuses_fitted_models_and_reports_absolute_degradation(config, monkeypatch):
    value, _ = diagnostic.load_pairing_config(config)
    original = diagnostic.fit_history_model
    calls = []

    def fit(*args, **kwargs):
        calls.append(args[6])
        return original(*args, **kwargs)

    monkeypatch.setattr(diagnostic, "fit_history_model", fit)
    metrics, models = diagnostic._compare_case(value, 42, "equal_clocks", stress=True)
    assert len(calls) == 4  # One fit per encoder, never one per shift.
    assert metrics["losses"]["paired_minus_availability_basis"]["nll_per_order"] == 0
    for key in ("coefficients", "feature_mean", "feature_scale", "intercepts_log_rate"):
        assert models["paired"][key] == models["availability_basis"][key]
    for shift in diagnostic.STRESS_SHIFTS[1:]:
        for mode in (*diagnostic.MODES, "availability_basis"):
            assert metrics["losses"][f"{mode}:shift={shift}:minus_own_unshifted"][
                "nll_per_order"
            ] == pytest.approx(
                metrics["losses"][f"{mode}:shift={shift}"]["nll_per_order"]
                - metrics["losses"][mode]["nll_per_order"]
            )
    assert metrics["perturbation_refit"] is False


def test_both_clocks_filter_before_features_and_invalid_pairs_fail():
    visible = _history([3.0, 0.0])
    excluded = [
        {"event_kind": 0, "occurrence_lag_hours": occurred, "availability_lag_hours": known}
        for occurred, known in [(2.0, -1.0), (-1.0, -2.0), (0.0, 0.0), (25.0, 1.0)]
    ]
    for mode in diagnostic.MODES:
        np.testing.assert_allclose(
            encode_clock_pairs(visible + excluded, [2, 12], mode),
            encode_clock_pairs(visible, [2, 12], mode),
        )
        assert not encode_clock_pairs([], [2, 12], mode).any()
    with pytest.raises(ValueError, match="Inverted"):
        encode_clock_pairs(_history([3.0, 5.0]), [2, 12], "paired")
    with pytest.raises(ValueError, match="Invalid clock-pair"):
        encode_clock_pairs(_history([3.0, float("nan")]), [2, 12], "paired")
    with pytest.raises(ValueError, match="finite positive"):
        encode_clock_pairs([], [2, float("inf")], "paired")


def test_generator_preserves_marginals_labels_and_patient_splits_in_controls(config):
    value, _ = diagnostic.load_pairing_config(config)
    signal, histories = diagnostic.generate_pairing_case(value, 42, "pairing_signal")
    scrambled, shuffled = diagnostic.generate_pairing_case(value, 42, "scrambled_pairing")
    null, null_histories = diagnostic.generate_pairing_case(value, 42, "null")
    assert signal == scrambled
    assert null_histories == histories
    assert signal != null
    assert {row["patient_id"] for row in signal if row["split"] == "train"}.isdisjoint(
        {row["patient_id"] for row in signal if row["split"] == "validation"}
    )
    changed = 0
    for order in histories:
        assert all(
            0 <= event["availability_lag_hours"] <= event["occurrence_lag_hours"] <= 24
            for event in shuffled[order]
        )
        np.testing.assert_allclose(
            encode_clock_pairs(histories[order], value["scales_hours"], "unpaired"),
            encode_clock_pairs(shuffled[order], value["scales_hours"], "unpaired"),
        )
        changed += histories[order] != shuffled[order]
    assert 0 < changed < len(histories)
    changed_effect = dict(value, pairing_log_rate_effect=0.1)
    assert diagnostic.generate_pairing_case(changed_effect, 42, "null") == (null, null_histories)


@pytest.mark.parametrize("scenario", diagnostic.SCENARIOS)
def test_generated_mechanism_has_gain_only_when_pair_information_predicts_outcome(scenario):
    config, _ = diagnostic.load_pairing_config(ROOT / "configs/synthetic_pairing.yaml")
    metrics, _ = diagnostic._compare_case(config, config["seeds"][0], scenario)
    delta = metrics["losses"]["paired_minus_unpaired"]["nll_per_order"]
    # Broad engineering tolerances on a deliberately strong generated effect;
    # neither a clinical advancement rule nor a statistical equivalence claim.
    assert delta < -0.05 if scenario == "pairing_signal" else abs(delta) < 0.05


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("clinical_path", "not-an-input"),
        ("data_class", "restricted_clinical"),
        ("seeds", [1, 1]),
        ("seeds", [-1]),
        ("train_patients", 2001),
        ("orders_per_patient", True),
        ("base_rates_per_hour", [0.1, 0.1, float("inf")]),
        ("pairing_log_rate_effect", float("nan")),
        ("availability_lags_hours", [5.0, 1.0]),
        ("scales_hours", [2.0, 2.0]),
        ("bin_edges_hours", [0.0, 12.0]),
    ],
)
def test_strict_config_rejects_inputs_invalid_numbers_and_resource_expansion(config, key, value):
    contents = yaml.safe_load(config.read_text())
    contents[key] = value
    config.write_text(yaml.safe_dump(contents))
    with pytest.raises(ValueError):
        diagnostic.load_pairing_config(config)


def test_reproducible_artifacts_are_explicitly_synthetic_and_never_overwritten(config, tmp_path):
    outputs = [tmp_path / "first", tmp_path / "second"]
    for output in outputs:
        result = diagnostic.run_pairing_diagnostic(config, output)
        assert result["status"] == "complete"
        assert result["clinical_advancement_decision"] == "not_applicable"
        manifest = json.loads((output / "manifest.json").read_text())
        assert manifest["status"] == "complete" and manifest["data_class"] == "synthetic"
        assert manifest["clinical_inputs_used"] is False
        assert manifest["clinical_test_evaluated"] is False
        assert manifest["source_files_sha256"]["src/ies/models/paired_history.py"] == sha256(
            ROOT / "src/ies/models/paired_history.py"
        )
        for filename, digest in manifest["artifacts_sha256"].items():
            assert sha256(output / filename) == digest
        models = json.loads((output / "models.json").read_text())
        assert all(
            model["data_class"] == "synthetic"
            for case in models["models"].values()
            for model in case.values()
        )
    for name in ("metrics.json", "models.json", "config.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
    with pytest.raises(FileExistsError):
        diagnostic.run_pairing_diagnostic(config, outputs[0])


def test_failed_diagnostic_is_explicit_and_does_not_persist_exception_payload(
    config, tmp_path, monkeypatch
):
    def fail(*args, **kwargs):
        raise ValueError("arbitrary-payload")

    monkeypatch.setattr(diagnostic, "_compare_case", fail)
    output = tmp_path / "failed"
    with pytest.raises(ValueError):
        diagnostic.run_pairing_diagnostic(config, output)
    manifest = (output / "manifest.json").read_text()
    assert json.loads(manifest)["status"] == "failed"
    assert "arbitrary-payload" not in manifest


def test_cli_runs_without_external_data_arguments(config, tmp_path, capsys):
    assert (
        main(["pairing-diagnostic", "--config", str(config), "--run-dir", str(tmp_path / "cli")])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["data_class"] == "synthetic"
    with pytest.raises(SystemExit):
        main(["pairing-diagnostic", "--cohort-dir", "not-supported"])
