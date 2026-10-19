"""Generated W001 controls with equal clocks, known mechanisms and no external inputs."""

import importlib.metadata
import platform
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ies.io import sha256, write_json
from ies.training.pipeline import git_provenance
from ies.workflow_cv import load_workflow_config, workflow_cross_validation
from ies.workflow_diagnostics import replay_diagnostics

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("volume_signal", "pooled_timing_signal", "type_timing_signal", "null")
SEEDS = (20261019, 20261020, 20261021)


def generate_workflow_case(seed, scenario, patients=240):
    if scenario not in SCENARIOS or not 20 <= patients <= 2000:
        raise ValueError("Invalid generated workflow case")
    rng = np.random.default_rng(seed)
    cohort, grouped = [], {}
    for patient in range(patients):
        bit = int(rng.integers(2))
        jitter = float(rng.uniform(-0.25, 0.25))
        if scenario == "volume_signal":
            pairs = [
                (kind, float(lag)) for kind in (0, 1) for lag in np.linspace(1, 18, 3 if bit else 1)
            ]
        elif scenario == "pooled_timing_signal":
            lags = [1, 2, 4, 6] if bit else [8, 10, 14, 20]
            kinds = rng.permutation([0, 0, 1, 1]).tolist()
            pairs = list(zip(kinds, lags, strict=True))
        else:
            kinds = [0, 0, 1, 1] if bit else [1, 1, 0, 0]
            pairs = list(zip(kinds, [1, 3, 12, 18], strict=True))
        for repeat in range(2):
            order = f"generated-order-{patient}-{repeat}"
            grouped[order] = [
                {
                    "event_kind": kind,
                    "occurrence_lag_hours": lag + jitter,
                    "availability_lag_hours": lag + jitter,
                }
                for kind, lag in pairs
            ]
            effect = 0.0 if scenario == "null" else (0.9 if bit else -0.9)
            rates = np.array([0.08 * np.exp(effect), 0.04, 0.02])
            duration = float(rng.exponential(1 / rates.sum()))
            cause = int(rng.choice([1, 2, 3], p=rates / rates.sum())) if duration <= 24 else 0
            cohort.append(
                {
                    "order_id": order,
                    "patient_id": f"generated-patient-{patient}",
                    "split": "train",
                    "duration": min(duration, 24.0),
                    "cause": cause,
                }
            )
    return cohort, grouped


def _source_hashes():
    return {
        str(path.relative_to(ROOT)): sha256(path) for path in sorted((ROOT / "src").rglob("*.py"))
    }


def run_workflow_demo(config_path, run_dir):
    config, digest = load_workflow_config(config_path)
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "mode": "synthetic_workflow_cv",
        "status": "running",
        "data_class": "synthetic",
        "started_utc": datetime.now(UTC).isoformat(),
        "git": git_provenance(),
        "source_files_sha256": _source_hashes(),
        "config_file_sha256": digest,
        "dependency_lock_sha256": sha256(ROOT / "uv.lock"),
        "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pyarrow", "PyYAML")},
        "clinical_inputs_used": False,
        "clinical_test_evaluated": False,
        "gpu_used": False,
        "seeds": list(SEEDS),
        "scenarios": list(SCENARIOS),
        "patients_per_case": 240,
        "orders_per_patient": 2,
    }
    write_json(run_dir / "manifest.json", manifest)
    try:
        write_json(run_dir / "config.json", config)
        cases, fitted, diagnostics = [], {}, []
        for seed in SEEDS:
            for scenario in SCENARIOS:
                cohort, grouped = generate_workflow_case(seed, scenario)
                report, models = workflow_cross_validation(
                    cohort, grouped, config, data_class="synthetic"
                )
                report.update(seed=seed, scenario=scenario)
                cases.append(report)
                fitted[f"{seed}:{scenario}"] = models
                diagnostic = replay_diagnostics(
                    cohort, grouped, config, models, report, data_class="synthetic"
                )
                diagnostic.update(seed=seed, scenario=scenario)
                diagnostics.append(diagnostic)
        summary = {
            scenario: {
                contrast: float(
                    np.mean(
                        [
                            case["metrics"][contrast]["nll_per_order"]
                            for case in cases
                            if case["scenario"] == scenario
                        ]
                    )
                )
                for contrast in (
                    "counts_minus_intercept",
                    "pooled_minus_counts",
                    "typed_minus_pooled",
                )
            }
            for scenario in SCENARIOS
        }
        write_json(
            run_dir / "metrics.json",
            {"data_class": "synthetic", "cases": cases, "summary": summary},
        )
        write_json(run_dir / "models.json", {"data_class": "synthetic", "models": fitted})
        write_json(run_dir / "diagnostics.json", {"data_class": "synthetic", "cases": diagnostics})
        if _source_hashes() != manifest["source_files_sha256"] or sha256(config_path) != digest:
            raise ValueError("Workflow demo source or config changed")
        manifest["artifacts_sha256"] = {
            name: sha256(run_dir / name)
            for name in ("config.json", "metrics.json", "models.json", "diagnostics.json")
        }
        manifest["status"] = "complete"
        return {
            "status": "complete",
            "data_class": "synthetic",
            "run_dir": str(run_dir),
            "summary": summary,
            "clinical_advancement_decision": "not_applicable",
        }
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
