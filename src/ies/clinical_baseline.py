"""Private CPU-only intercept baseline for a verified bounded UCSF cohort."""

import hashlib
import json
import math
import os
import re
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from ies.cohort_readiness.extract import SCHEMA
from ies.evaluation.metrics import evaluate
from ies.feasibility.contract import ROOT
from ies.io import sha256, write_json
from ies.models.piecewise import fit_baseline


class ClinicalBaselineError(ValueError):
    pass


AUTHORIZED_ROOT = Path("/scratch/tliu7")


def load_baseline_config(path: Path) -> tuple[dict, str]:
    content = path.read_bytes()
    try:
        value = yaml.safe_load(content)
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "seed",
            "bin_edges_hours",
            "bootstrap_replicates",
            "evaluation_split",
        }:
            raise ClinicalBaselineError("invalid_baseline_config")
        if value["schema_version"] != 1 or type(value["seed"]) is not int:
            raise ClinicalBaselineError("invalid_baseline_config")
        if value["evaluation_split"] != "validation":
            raise ClinicalBaselineError("invalid_baseline_config")
        if (
            type(value["bootstrap_replicates"]) is not int
            or not 2 <= value["bootstrap_replicates"] <= 10_000
        ):
            raise ClinicalBaselineError("invalid_baseline_config")
        edges = value["bin_edges_hours"]
        if (
            not isinstance(edges, list)
            or len(edges) < 2
            or edges[0] != 0
            or edges[-1] != 24
            or any(type(item) not in (int, float) or not math.isfinite(item) for item in edges)
            or any(left >= right for left, right in zip(edges, edges[1:], strict=False))
        ):
            raise ClinicalBaselineError("invalid_baseline_config")
        return value, hashlib.sha256(content).hexdigest()
    except (OSError, yaml.YAMLError, TypeError, KeyError):
        raise ClinicalBaselineError("invalid_baseline_config") from None


def _verify_artifact_directory(path: Path, error_code: str) -> Path:
    """Use one server storage boundary; generated tests replace it in-process only."""
    resolved = path.resolve()
    if (
        not path.is_absolute()
        or not resolved.is_relative_to(AUTHORIZED_ROOT.resolve())
        or resolved.is_relative_to(ROOT.resolve())
    ):
        raise ClinicalBaselineError(error_code)
    return resolved


def _verify_cohort(cohort_dir: Path, expected_manifest_sha256: str) -> tuple[list[dict], dict]:
    cohort_dir = _verify_artifact_directory(cohort_dir, "invalid_clinical_cohort")
    manifest_path = cohort_dir / "manifest.json"
    if sha256(manifest_path) != expected_manifest_sha256:
        raise ClinicalBaselineError("clinical_cohort_changed")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("status") != "complete"
        or manifest.get("mode") != "bounded_phase0_cohort_extraction"
        or manifest.get("data_class") != "restricted_clinical"
        or manifest.get("bounded_domain") is not True
    ):
        raise ClinicalBaselineError("invalid_clinical_cohort")
    cohort_path = cohort_dir / "cohort.parquet"
    if manifest.get("artifacts_sha256", {}).get("cohort.parquet") != sha256(cohort_path):
        raise ClinicalBaselineError("clinical_cohort_changed")
    parquet = pq.ParquetFile(cohort_path)
    if parquet.schema_arrow != SCHEMA:
        raise ClinicalBaselineError("invalid_clinical_cohort")
    table = pq.read_table(
        cohort_path,
        filters=[("split", "in", ["train", "validation"])],
    )
    if table.num_rows == 0 or any(c.null_count for c in table.columns):
        raise ClinicalBaselineError("invalid_clinical_cohort")
    rows = table.to_pylist()
    converted = []
    patient_splits = {}
    order_ids = set()
    for row in rows:
        if row["order_id"] in order_ids or row["split"] not in {"train", "validation", "test"}:
            raise ClinicalBaselineError("invalid_clinical_cohort")
        order_ids.add(row["order_id"])
        previous = patient_splits.setdefault(row["patient_id"], row["split"])
        if previous != row["split"] or not 0 < row["duration_hours"] <= 24:
            raise ClinicalBaselineError("invalid_clinical_cohort")
        converted.append(
            {
                "patient_id": row["patient_id"],
                "order_id": row["order_id"],
                "split": row["split"],
                "duration": row["duration_hours"],
                "cause": row["cause"],
            }
        )
    return converted, manifest


def run_clinical_baseline(
    cohort_dir: Path,
    output_dir: Path,
    config: dict,
    config_sha256: str,
    cohort_manifest_sha256: str,
    source_commit: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or any(output_dir.iterdir()):
        raise ClinicalBaselineError("invalid_baseline_output")
    cohort, cohort_manifest = _verify_cohort(cohort_dir, cohort_manifest_sha256)
    model = fit_baseline(
        cohort,
        config["bin_edges_hours"],
        data_class="restricted_clinical",
    )
    metrics, predictions = evaluate(
        cohort,
        model,
        split=config["evaluation_split"],
        bootstrap=config["bootstrap_replicates"],
        seed=config["seed"],
    )
    artifacts = {
        "model.json": model,
        "validation_metrics.json": metrics,
        "validation_predictions.json": predictions,
    }
    for name, value in artifacts.items():
        write_json(output_dir / name, value)
        os.chmod(output_dir / name, 0o600)
    manifest = {
        "schema_version": 1,
        "mode": "clinical_intercept_baseline",
        "data_class": "restricted_clinical",
        "status": "complete",
        "source_commit": source_commit,
        "cohort_source_commit": cohort_manifest["source_commit"],
        "cohort_manifest_sha256": cohort_manifest_sha256,
        "config_sha256": config_sha256,
        "evaluation_split": "validation",
        "test_split_evaluated": False,
        "features_used": False,
        "database_write": False,
        "gpu_used": False,
        "artifacts_sha256": {name: sha256(output_dir / name) for name in artifacts},
    }
    write_json(output_dir / "manifest.json", manifest)
    os.chmod(output_dir / "manifest.json", 0o600)
    return manifest
