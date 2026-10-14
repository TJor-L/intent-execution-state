"""One-command reproducible synthetic experiment with an auditable manifest."""

import importlib.metadata
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from ies.config import load_config
from ies.data.events import read_events, write_events
from ies.data.synthetic import generate_events
from ies.evaluation.metrics import evaluate
from ies.io import sha256, write_json
from ies.models.piecewise import fit_baseline
from ies.preprocessing.cohort import build_cohort


def git_provenance() -> dict:
    repository = Path(__file__).resolve().parents[3]
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, stderr=subprocess.DEVNULL, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=repository, text=True
            ).strip()
        )
        return {"commit": revision, "dirty": dirty}
    except (subprocess.CalledProcessError, OSError):
        return {"commit": None, "dirty": True}


def run_experiment(config_path: Path, run_dir: Path) -> dict:
    config = load_config(config_path)
    # Never overwrite an existing experiment, including a failed or incomplete run.
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "status": "running",
        "data_class": "synthetic",
        "config": config,
        "started_utc": datetime.now(UTC).isoformat(),
        "git": git_provenance(),
        "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pyarrow", "PyYAML")},
        "config_file_sha256": sha256(config_path),
    }
    lock = Path(__file__).resolve().parents[3] / "uv.lock"
    manifest["dependency_lock_sha256"] = sha256(lock) if lock.exists() else None
    write_json(run_dir / "manifest.json", manifest)
    try:
        events = generate_events(
            **{
                key: config[key]
                for key in (
                    "n_patients",
                    "seed",
                    "orders_per_patient",
                    "horizon_hours",
                    "delay_scale",
                )
            }
        )
        event_file = run_dir / "events.parquet"
        write_events(event_file, events)
        cohort = build_cohort(
            read_events(event_file),
            config["seed"],
            config["horizon_hours"],
            config["lookback_hours"],
        )
        write_json(run_dir / "cohort.json", {"data_class": "synthetic", "rows": cohort})
        model = fit_baseline(cohort, config["bin_edges_hours"])
        write_json(run_dir / "model.json", model)
        for split in ("validation", "test"):
            metrics, predictions = evaluate(
                cohort, model, split, config["bootstrap_replicates"], config["seed"]
            )
            write_json(run_dir / f"metrics_{split}.json", metrics)
            write_json(run_dir / f"predictions_{split}.json", predictions)
        manifest["artifacts_sha256"] = {
            path.name: sha256(path)
            for path in sorted(run_dir.iterdir())
            if path.name != "manifest.json"
        }
        manifest["status"] = "complete"
        return metrics
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error_type"] = type(error).__name__
        raise
    finally:
        manifest["finished_utc"] = datetime.now(UTC).isoformat()
        write_json(run_dir / "manifest.json", manifest)
