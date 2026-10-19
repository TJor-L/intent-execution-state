"""Generated-only comparison of within-event clock pairing and marginal summaries."""

import hashlib
import importlib.metadata
import math
import platform
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import yaml

from ies.clinical_history_models import _bootstrap
from ies.io import sha256, write_json
from ies.losses.competing_risks import validate_edges
from ies.models.history_piecewise import fit_history_model, individual_nll, predict_hazards
from ies.models.paired_history import encode_clock_pairs
from ies.training.pipeline import git_provenance

SCENARIOS = ("pairing_signal", "null", "scrambled_pairing")
MODES = ("marginal", "unpaired", "paired")
STRESS_SCENARIOS = (*SCENARIOS, "equal_clocks")
STRESS_SHIFTS = (0.0, 1.0, 4.0, 8.0)
ROOT = Path(__file__).resolve().parents[2]
CONFIG_KEYS = {
    "schema_version",
    "data_class",
    "seeds",
    "train_patients",
    "validation_patients",
    "orders_per_patient",
    "scales_hours",
    "bin_edges_hours",
    "occurrence_lags_hours",
    "availability_lags_hours",
    "jitter_hours",
    "base_rates_per_hour",
    "pairing_log_rate_effect",
    "ridge",
    "max_iterations",
    "tolerance",
    "bootstrap_replicates",
}


def load_pairing_config(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    config = yaml.safe_load(content)
    if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
        raise ValueError("Pairing config must contain exactly the documented synthetic keys")
    if (
        type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or config["data_class"] != "synthetic"
    ):
        raise ValueError("Pairing diagnostic requires synthetic schema version 1")
    seeds = config["seeds"]
    if (
        not isinstance(seeds, list)
        or not 1 <= len(seeds) <= 5
        or any(type(seed) is not int or not 0 <= seed < 2**32 for seed in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise ValueError("Invalid diagnostic seeds")
    for key, lower, upper in (
        ("train_patients", 20, 2000),
        ("validation_patients", 20, 1000),
        ("orders_per_patient", 1, 4),
        ("max_iterations", 1, 200),
        ("bootstrap_replicates", 2, 1000),
    ):
        if type(config[key]) is not int or not lower <= config[key] <= upper:
            raise ValueError("Diagnostic count exceeds supported bounds")

    def positive(value):
        return type(value) in (int, float) and math.isfinite(value) and value > 0

    for key in ("pairing_log_rate_effect", "jitter_hours", "ridge", "tolerance"):
        if not positive(config[key]):
            raise ValueError("Invalid diagnostic numeric setting")
    if config["pairing_log_rate_effect"] > 2 or config["jitter_hours"] > 0.5:
        raise ValueError("Diagnostic signal or jitter exceeds supported bounds")
    for key, size in (
        ("scales_hours", 2),
        ("occurrence_lags_hours", 2),
        ("availability_lags_hours", 2),
        ("base_rates_per_hour", 3),
    ):
        values = config[key]
        if not isinstance(values, list) or len(values) != size or not all(map(positive, values)):
            raise ValueError("Invalid diagnostic numeric vector")
    if len(set(config["scales_hours"])) != 2:
        raise ValueError("Diagnostic scales must be distinct")
    occurred, available = config["occurrence_lags_hours"], config["availability_lags_hours"]
    jitter = config["jitter_hours"]
    if (
        len(set(occurred)) != 2
        or len(set(available)) != 2
        or min(occurred) < max(available)
        or min(available) <= jitter
        or max(occurred) + jitter > 24
    ):
        raise ValueError("Every diagnostic permutation must retain valid pre-index clock pairs")
    edges = config["bin_edges_hours"]
    if (
        not isinstance(edges, list)
        or len(edges) > 16
        or any(type(item) not in (int, float) for item in edges)
        or validate_edges(edges)[-1] != 24
    ):
        raise ValueError("Diagnostic bins must cover 24 hours")
    return config, hashlib.sha256(content).hexdigest()


def generate_pairing_case(config: dict, seed: int, scenario: str) -> tuple[list[dict], dict]:
    """One latent bit per patient changes only the clock pairing, never the marginals.

    Null labels ignore this bit. Scrambled histories use an independent bit, with
    the exact same outcomes as the signal case. Separate RNG streams ensure that
    generating outcomes never changes histories or patient assignment.
    """
    if scenario not in STRESS_SCENARIOS or config["data_class"] != "synthetic":
        raise ValueError("Only generated pairing scenarios are supported")
    streams = np.random.SeedSequence(seed).spawn(3)
    layout, outcomes, scrambling = [np.random.default_rng(stream) for stream in streams]
    rows, histories = [], {}
    n_patients = config["train_patients"] + config["validation_patients"]
    for patient in range(n_patients):
        latent = int(layout.integers(2))
        split = "train" if patient < config["train_patients"] else "validation"
        for order_index in range(config["orders_per_patient"]):
            jitter = float(layout.uniform(-config["jitter_hours"], config["jitter_hours"]))
            pairing = int(scrambling.integers(2)) if scenario == "scrambled_pairing" else latent
            available = list(config["availability_lags_hours"])
            if pairing:
                available.reverse()
            if scenario == "equal_clocks":
                available = list(config["occurrence_lags_hours"])
            order_id = f"generated-{seed}-{patient}-{order_index}"
            histories[order_id] = [
                {
                    "event_kind": order_index % 2,
                    "occurrence_lag_hours": occurred + jitter,
                    "availability_lag_hours": known + jitter,
                }
                for occurred, known in zip(config["occurrence_lags_hours"], available, strict=True)
            ]
            rates = np.array(config["base_rates_per_hour"], dtype=float)
            if scenario == "equal_clocks":
                rates[0] *= math.exp(
                    config["pairing_log_rate_effect"] * jitter / config["jitter_hours"]
                )
            elif scenario != "null":
                rates[0] *= math.exp(config["pairing_log_rate_effect"] * (1 if latent else -1))
            duration = float(outcomes.exponential(1 / rates.sum()))
            cause = int(outcomes.choice([1, 2, 3], p=rates / rates.sum()))
            rows.append(
                {
                    "patient_id": f"generated-{seed}-{patient}",
                    "order_id": order_id,
                    "split": split,
                    "duration": min(duration, 24.0),
                    "cause": cause if duration <= 24 else 0,
                }
            )
    return rows, histories


def _source_hashes() -> dict:
    return {
        str(path.relative_to(ROOT)): sha256(path)
        for path in sorted((ROOT / "src" / "ies").rglob("*.py"))
    }


def _compare_case(config, seed, scenario, *, stress=False):
    cohort, histories = generate_pairing_case(config, seed, scenario)
    validation = [row for row in cohort if row["split"] == "validation"]
    train_patients = {row["patient_id"] for row in cohort if row["split"] == "train"}
    if train_patients & {row["patient_id"] for row in validation}:
        raise ValueError("Generated patient split overlap")
    losses, models = {}, {}
    modes = (*MODES, "availability_basis") if stress else MODES
    for mode in modes:
        features = {
            order: encode_clock_pairs(history, config["scales_hours"], mode)
            for order, history in histories.items()
        }
        model = fit_history_model(
            cohort,
            features,
            config["bin_edges_hours"],
            config["ridge"],
            config["max_iterations"],
            config["tolerance"],
            mode,
            data_class="synthetic",
        )
        matrix = np.stack([features[row["order_id"]] for row in validation])
        losses[mode] = individual_nll(
            [row["duration"] for row in validation],
            [row["cause"] for row in validation],
            predict_hazards(model, matrix),
            config["bin_edges_hours"],
        )
        models[mode] = model
    for control in ("marginal", "unpaired", *(("availability_basis",) if stress else ())):
        losses[f"paired_minus_{control}"] = losses["paired"] - losses[control]
    if stress:
        for shift in STRESS_SHIFTS[1:]:
            for mode in modes:
                matrix = np.stack(
                    [
                        encode_clock_pairs(
                            [
                                dict(
                                    event,
                                    availability_lag_hours=event["availability_lag_hours"] - shift,
                                )
                                for event in histories[row["order_id"]]
                            ],
                            config["scales_hours"],
                            mode,
                        )
                        for row in validation
                    ]
                )
                shifted = individual_nll(
                    [row["duration"] for row in validation],
                    [row["cause"] for row in validation],
                    predict_hazards(models[mode], matrix),
                    config["bin_edges_hours"],
                )
                losses[f"{mode}:shift={shift}"] = shifted
                losses[f"{mode}:shift={shift}:minus_own_unshifted"] = shifted - losses[mode]
            for control in ("unpaired", "availability_basis"):
                losses[f"paired_minus_{control}:shift={shift}"] = (
                    losses[f"paired:shift={shift}"] - losses[f"{control}:shift={shift}"]
                )
    intervals = _bootstrap(validation, losses, config["bootstrap_replicates"], seed)
    return (
        {
            "scenario": scenario,
            "seed": seed,
            "data_class": "synthetic",
            "split": "validation",
            "train_patients": len(train_patients),
            "validation_patients": config["validation_patients"],
            "validation_orders": len(validation),
            "feature_dimensions": {mode: models[mode]["feature_dimension"] for mode in modes},
            **(
                {
                    "delay_shifts_hours": list(STRESS_SHIFTS),
                    "perturbation_refit": False,
                    "history_refill": False,
                }
                if stress
                else {}
            ),
            "outcome_counts": {
                str(cause): sum(row["cause"] == cause for row in validation) for cause in range(4)
            },
            "losses": {
                name: {
                    "nll_per_order": float(value.mean()),
                    "patient_bootstrap_95ci": intervals[name],
                }
                for name, value in losses.items()
            },
        },
        models,
    )


def run_pairing_diagnostic(config_path: Path, run_dir: Path, *, stress=False) -> dict:
    """No input-data argument: all records and labels are generated inside this run."""
    config, config_digest = load_pairing_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "status": "running",
        "mode": "synthetic_clock_pairing_stress"
        if stress
        else "synthetic_clock_pairing_diagnostic",
        "data_class": "synthetic",
        "started_utc": datetime.now(UTC).isoformat(),
        "git": git_provenance(),
        "source_files_sha256": _source_hashes(),
        "config_file_sha256": config_digest,
        "dependency_lock_sha256": sha256(ROOT / "uv.lock"),
        "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pyarrow", "PyYAML")},
        "clinical_inputs_used": False,
        "clinical_test_evaluated": False,
        "gpu_used": False,
    }
    write_json(run_dir / "manifest.json", manifest)
    try:
        write_json(run_dir / "config.json", config)
        cases, fitted = [], {}
        scenarios = STRESS_SCENARIOS if stress else SCENARIOS
        for seed in config["seeds"]:
            for scenario in scenarios:
                metrics, models = _compare_case(config, seed, scenario, stress=stress)
                cases.append(metrics)
                fitted[f"{seed}:{scenario}"] = models
        summaries = {
            scenario: {
                "mean_paired_minus_unpaired_nll": float(
                    np.mean(
                        [
                            case["losses"]["paired_minus_unpaired"]["nll_per_order"]
                            for case in cases
                            if case["scenario"] == scenario
                        ]
                    )
                ),
                "seeds": len(config["seeds"]),
            }
            for scenario in scenarios
        }
        if stress:
            for scenario, summary in summaries.items():
                selected = [case for case in cases if case["scenario"] == scenario]
                summary["mean_paired_minus_availability_basis_nll"] = float(
                    np.mean(
                        [
                            case["losses"]["paired_minus_availability_basis"]["nll_per_order"]
                            for case in selected
                        ]
                    )
                )
                summary["paired_shift_degradation"] = {
                    str(shift): float(
                        np.mean(
                            [
                                case["losses"][f"paired:shift={shift}:minus_own_unshifted"][
                                    "nll_per_order"
                                ]
                                for case in selected
                            ]
                        )
                    )
                    for shift in STRESS_SHIFTS[1:]
                }
        report = {
            "data_class": "synthetic",
            "mode": manifest["mode"],
            "cases": cases,
            "summary": summaries,
            "clinical_advancement_decision": "not_applicable",
            "note": (
                "Generated mechanism diagnostic, not clinical performance or novelty evidence. "
                "All seeds/scenarios reported; no selection or refitting on validation. "
                "Per-seed intervals condition on fitted models; seed means are descriptive."
            ),
        }
        write_json(run_dir / "metrics.json", report)
        write_json(run_dir / "models.json", {"data_class": "synthetic", "models": fitted})
        if _source_hashes() != manifest["source_files_sha256"]:
            raise ValueError("Diagnostic source changed during execution")
        manifest["artifacts_sha256"] = {
            path.name: sha256(path)
            for path in sorted(run_dir.iterdir())
            if path.name != "manifest.json"
        }
        manifest["status"] = "complete"
        return {
            "status": "complete",
            "data_class": "synthetic",
            "run_dir": str(run_dir),
            "summary": summaries,
            "clinical_advancement_decision": "not_applicable",
        }
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error_type"] = type(error).__name__
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
