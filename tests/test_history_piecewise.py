"""Generated controls and analytical checks; no clinical performance evidence."""

import numpy as np

from ies.models.history_piecewise import (
    encode_history,
    fit_history_model,
    individual_nll,
    predict_hazards,
)


def test_individual_likelihood_matches_hand_calculation_at_bin_edges_and_censoring():
    hazards = np.array(
        [
            [[0.2, 0.3, 0.5], [0.1, 0.2, 0.3]],
            [[0.4, 0.2, 0.1], [0.1, 0.3, 0.5]],
            [[0.1, 0.2, 0.3], [0.6, 0.4, 0.2]],
        ]
    )
    actual = individual_nll([1.0, 2.0, 3.0], [1, 0, 3], hazards, [0, 1, 3])
    expected = [1.0 - np.log(0.2), 0.7 + 0.9, 0.6 + 2 * 1.2 - np.log(0.2)]
    np.testing.assert_allclose(actual, expected, rtol=1e-12)


def test_constant_features_recover_analytic_rates_and_ignore_held_out_rows():
    cohort = [
        {
            "order_id": f"train-{index}",
            "patient_id": f"person-{index}",
            "split": "train",
            "duration": duration,
            "cause": cause,
        }
        for index, (duration, cause) in enumerate(
            [(1.0, cause) for cause in range(4)] + [(3.0, cause) for cause in range(4)]
        )
    ]
    held_out = [
        {"order_id": split, "patient_id": split, "split": split, "duration": 2.5, "cause": 0}
        for split in ("validation", "test")
    ]
    features = {row["order_id"]: np.ones(8) for row in cohort + held_out}
    for row in held_out:
        features[row["order_id"]] = np.full(8, 1e6)
    args = (features, [0, 1, 3], 1.0, 100, 1e-10, "availability")
    fitted = fit_history_model(cohort + held_out, *args)
    assert fitted == fit_history_model(cohort, *args)
    # Eight subjects contribute one hour to bin 1; four contribute two to bin 2.
    # Each cause has one event per bin: its unpenalized intercept MLE is 1 / 8.
    np.testing.assert_allclose(predict_hazards(fitted, np.ones((1, 8))), 1 / 8, rtol=1e-5)
    np.testing.assert_allclose(fitted["coefficients"], 0, atol=1e-10)
    np.testing.assert_allclose(fitted["feature_mean"], 1)


def test_encoder_discards_event_pairing_even_when_documentation_delays_differ():
    def history(available):
        return [
            {
                "event_kind": 0,
                "occurrence_lag_hours": occurred,
                "availability_lag_hours": known,
            }
            for occurred, known in zip([8.0, 4.0], available, strict=True)
        ]

    first = history([3.0, 1.0])  # Paired delays: 5, 3 hours.
    second = history([1.0, 3.0])  # Paired delays: 7, 1 hours.
    np.testing.assert_allclose(
        encode_history(first, "dual_clock", [2, 12], [2, 12]),
        encode_history(second, "dual_clock", [2, 12], [2, 12]),
    )


def test_equal_clocks_duplicate_dual_features_under_frozen_scales():
    rows = [
        {"event_kind": kind, "occurrence_lag_hours": lag, "availability_lag_hours": lag}
        for kind, lag in [(0, 1.0), (0, 10.0), (1, 3.0)]
    ]
    encoded = encode_history(rows, "dual_clock", [2, 12], [2, 12]).reshape(2, 4)
    np.testing.assert_allclose(encoded[:, :2], encoded[:, 2:])


def test_equal_clock_duplication_halves_ridge_on_the_unique_basis():
    # For a total coefficient b on two identical standardized columns, the minimum
    # squared coefficient norm is b**2 / 2, attained by coefficients (b/2, b/2).
    # Hence duplicated features with ridge L must match unique features with L/2.
    # This verifies an algebraic equivalence, not a clinical refit or proposed tuning.
    rng = np.random.default_rng(20261019)
    cohort, duplicated, unique = [], {}, {}
    for index in range(96):
        order = f"generated-equal-clock-{index}"
        history = []
        for kind in (0, 1):
            for lag in rng.uniform(0.5, 20.0, size=int(rng.integers(1, 4))):
                history.append(
                    {
                        "event_kind": kind,
                        "occurrence_lag_hours": float(lag),
                        "availability_lag_hours": float(lag),
                    }
                )
        duplicated[order] = encode_history(history, "dual_clock", [2, 12], [2, 12])
        unique[order] = duplicated[order].reshape(2, 4)[:, :2].ravel()
        cohort.append(
            {
                "order_id": order,
                "patient_id": f"generated-person-{index}",
                "split": "train",
                "duration": float(rng.uniform(0.2, 24.0)),
                "cause": index % 4,
            }
        )
    models = [
        fit_history_model(
            cohort, features, [0, 4, 24], ridge, 100, 1e-12, mode, data_class="synthetic"
        )
        for features, ridge, mode in (
            (duplicated, 4.0, "generated_duplicated_basis"),
            (unique, 2.0, "generated_unique_basis"),
        )
    ]
    coefficients = np.asarray(models[0]["coefficients"]).reshape(3, 2, 4)
    np.testing.assert_allclose(coefficients[:, :, :2], coefficients[:, :, 2:], atol=1e-8)
    effective = (coefficients[:, :, :2] + coefficients[:, :, 2:]).reshape(3, 4)
    np.testing.assert_allclose(effective, models[1]["coefficients"], atol=1e-7)
    np.testing.assert_allclose(
        predict_hazards(models[0], np.stack(list(duplicated.values()))),
        predict_hazards(models[1], np.stack(list(unique.values()))),
        rtol=1e-7,
    )


def test_model_can_learn_generated_occurrence_signal_hidden_from_availability():
    rng = np.random.default_rng(20261016)
    cohort = []
    features = {"availability": {}, "dual_clock": {}}
    for index in range(1500):
        recent = bool(rng.integers(2))
        history = [
            {
                "event_kind": 0,
                "occurrence_lag_hours": 1.0 if recent else 16.0,
                "availability_lag_hours": 0.5,
            }
        ]
        rates = np.array([0.08 * np.exp(1.2 if recent else -1.2), 0.04, 0.02])
        duration = float(rng.exponential(1 / rates.sum()))
        cause = int(rng.choice([1, 2, 3], p=rates / rates.sum())) if duration <= 24 else 0
        order = f"generated-order-{index}"
        cohort.append(
            {
                "order_id": order,
                "patient_id": f"generated-person-{index}",
                "split": "train" if index < 1000 else "validation",
                "duration": min(duration, 24.0),
                "cause": cause,
            }
        )
        features["availability"][order] = encode_history(
            history, "availability", [1, 4, 12, 24], []
        )
        features["dual_clock"][order] = encode_history(history, "dual_clock", [2, 12], [2, 12])
    edges = [0, 1, 2, 4, 8, 12, 24]
    validation = [row for row in cohort if row["split"] == "validation"]
    losses = {}
    for mode in features:
        model = fit_history_model(cohort, features[mode], edges, 1.0, 100, 1e-8, mode)
        matrix = np.stack([features[mode][row["order_id"]] for row in validation])
        losses[mode] = individual_nll(
            [row["duration"] for row in validation],
            [row["cause"] for row in validation],
            predict_hazards(model, matrix),
            edges,
        )
    # A strong, deliberately generated signal checks power of the implementation,
    # without a search over seeds, clinical values or the clinical advancement rule.
    assert losses["dual_clock"].mean() < losses["availability"].mean() - 0.1
