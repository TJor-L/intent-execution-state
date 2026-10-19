"""Generated R001 mechanism checks; latent complete outcomes are simulation-only."""

import copy
import importlib.metadata
import platform
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ies.io import sha256, write_json
from ies.selection_cv import (
    CANDIDATES,
    NAMES,
    POLICIES,
    _predict,
    group_folds,
    load_config,
    run_selection_cv,
)
from ies.selection_scores import coherent_rows, patient_weights
from ies.training.pipeline import git_provenance
from ies.workflow_cv import MODELS, encode_workflow
from ies.workflow_diagnostic import _source_hashes
from ies.workflow_diagnostics import cumulative_risks

SCENARIOS = ("execution_only", "competing_only", "nonlinear_execution", "time_varying", "null")
DATA_SEEDS = (20261023, 20261024, 20261025)
REGIMES = ("administrative_only", "feature_dependent_censoring")
ROOT = Path(__file__).resolve().parents[2]


def generate_case(seed, scenario, regime, patients=240):
    if scenario not in SCENARIOS or regime not in REGIMES or not 30 <= patients <= 10000:
        raise ValueError("Invalid generated selection case")
    rng = np.random.default_rng(seed)
    censor_rng = np.random.default_rng(seed + 100)
    observed, complete, history = [], [], {}
    edges = [0, 1, 2, 4, 8, 12, 24]
    for patient in range(patients):
        level = int(rng.integers(3))
        for repeat in range(1 + patient % 3):
            order = f"generated-selection-order-{patient}-{repeat}"
            pairs = [(kind, float(lag)) for kind in (0, 1) for lag in np.linspace(1, 20, level + 1)]
            history[order] = [
                dict(event_kind=kind, occurrence_lag_hours=lag, availability_lag_hours=lag)
                for kind, lag in pairs
            ]
            time, cause = 24.0, 0
            for left, right in zip(edges[:-1], edges[1:], strict=True):
                rates = np.array([0.06, 0.04, 0.02])
                if scenario == "execution_only":
                    rates[0] *= np.exp(level - 1)
                elif scenario == "competing_only":
                    rates[1] *= np.exp(level - 1)
                elif scenario == "nonlinear_execution":
                    rates[0] *= np.exp(1 if level != 1 else -1)
                elif scenario == "time_varying":
                    rates[0] *= np.exp((level - 1) * (1.2 if left < 4 else -1.2))
                waiting = float(rng.exponential(1 / rates.sum()))
                if waiting < right - left:
                    time = left + waiting
                    cause = int(rng.choice([1, 2, 3], p=rates / rates.sum()))
                    break
            full = dict(
                order_id=order,
                patient_id=f"generated-selection-patient-{patient}",
                split="train",
                duration=time,
                cause=cause,
            )
            complete.append(full)
            row = dict(full)
            if regime == "feature_dependent_censoring":
                censor = max(0.005, float(censor_rng.exponential(18 / (level + 1))))
                if censor < time:
                    row.update(duration=censor, cause=0)
            observed.append(row)
    return observed, history, complete


def oracle_check(observed, history, complete, config, report, models):
    """Replay saved synthetic outer models against latent outcomes; never a clinical API."""
    if report["data_class"] != "synthetic" or models["data_class"] != "synthetic":
        raise ValueError("Oracle is synthetic only")
    rows = sorted(observed, key=lambda r: (r["patient_id"], r["order_id"]))
    full = {r["order_id"]: r for r in complete}
    patients = np.array([r["patient_id"] for r in rows])
    weights = patient_weights(patients)
    encoded = [encode_workflow(history[r["order_id"]], config["scales_hours"]) for r in rows]
    features = {name: np.stack([r[name] for r in encoded]) for name in MODELS}
    outcomes = np.array(
        [
            [
                full[r["order_id"]]["cause"] == 1 and full[r["order_id"]]["duration"] <= h
                for h in config["horizons_hours"]
            ]
            for r in rows
        ]
    )
    fitted = {(m["seed"], m["fold"]): m["models"] for m in models["models"]}
    results = []
    for run in report["seeds"]:
        folds = group_folds(patients, 5, run["seed"], "outer")
        predictions = np.full((len(rows), 8, 4), np.nan)
        selected = np.full((len(rows), 2, 4), np.nan)
        for fold in range(5):
            use = folds == fold
            for j, candidate in enumerate(CANDIDATES):
                rates = _predict(
                    fitted[run["seed"], fold][NAMES[j]],
                    {name: x[use] for name, x in features.items()},
                    candidate,
                )
                predictions[use, j] = cumulative_risks(
                    rates, config["bin_edges_hours"], config["horizons_hours"]
                )[:, :, 0]
            for j, policy in enumerate(POLICIES):
                index = NAMES.index(run["choices"][fold]["selected"][policy])
                selected[use, j] = predictions[use, index]
        scores = ((predictions - outcomes[:, None]) ** 2) @ config["horizon_weights"]
        truth = ((selected[:, 1] - outcomes) ** 2 - (selected[:, 0] - outcomes) ** 2) @ config[
            "horizon_weights"
        ]
        bounds = coherent_rows(
            selected[:, 1],
            [r["duration"] for r in rows],
            [r["cause"] for r in rows],
            config["horizons_hours"],
            config["horizon_weights"],
            selected[:, 0],
        )
        if not ((truth >= bounds[:, 0] - 1e-12) & (truth <= bounds[:, 1] + 1e-12)).all():
            raise ValueError("Generated truth outside completion set")
        difference = float(weights @ truth)
        reported = run["primary_comparison"]["patient_mean_completion_bounds"]
        np.testing.assert_allclose(weights @ bounds, reported, atol=1e-12)
        results.append(
            dict(
                seed=run["seed"],
                oracle_candidate_brier=dict(zip(NAMES, (weights @ scores).tolist(), strict=True)),
                oracle_policy_difference=difference,
                completion_bounds=reported,
                true_direction="lower"
                if difference < 0
                else "higher"
                if difference > 0
                else "equal",
                truth_within_bounds=True,
            )
        )
    return results


def run_demo(config_path, run_dir):
    config, digest = load_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(
        mode="synthetic_selection_benchmark",
        status="running",
        data_class="synthetic",
        started_utc=datetime.now(UTC).isoformat(),
        git=git_provenance(),
        source_files_sha256=_source_hashes(),
        config_file_sha256=digest,
        dependency_lock_sha256=sha256(ROOT / "uv.lock"),
        python=platform.python_version(),
        packages={p: importlib.metadata.version(p) for p in ("numpy", "pyarrow", "PyYAML")},
        clinical_inputs_used=False,
        clinical_test_evaluated=False,
        gpu_used=False,
        data_seeds=list(DATA_SEEDS),
        scenarios=list(SCENARIOS),
        regimes=list(REGIMES),
        patients_per_case=240,
        orders_per_patient="1, 2 or 3 (fixed by generated patient index)",
    )
    write_json(run_dir / "manifest.json", manifest)
    try:
        write_json(run_dir / "config.json", config)
        cases = []
        for seed in DATA_SEEDS:
            for scenario in SCENARIOS:
                for regime in REGIMES:
                    cohort, history, complete = generate_case(seed, scenario, regime)
                    before = copy.deepcopy(cohort)
                    report, models = run_selection_cv(
                        cohort, history, config, data_class="synthetic"
                    )
                    if cohort != before:
                        raise ValueError("Generated inputs mutated")
                    oracle = oracle_check(cohort, history, complete, config, report, models)
                    cases.append(
                        dict(
                            data_seed=seed,
                            scenario=scenario,
                            regime=regime,
                            report=report,
                            oracle=oracle,
                        )
                    )
        write_json(run_dir / "metrics.json", dict(data_class="synthetic", cases=cases))
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise ValueError("Selection demo source or config changed")
        manifest.update(
            status="complete",
            artifacts_sha256={
                name: sha256(run_dir / name) for name in ("metrics.json", "config.json")
            },
        )
        return dict(
            status="complete",
            data_class="synthetic",
            run_dir=str(run_dir),
            cases=len(cases),
            oracle_checks="all_truths_within_bounds",
            clinical_advancement_decision="not_applicable",
        )
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
