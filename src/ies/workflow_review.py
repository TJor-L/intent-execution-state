"""Read existing W001 results without fitting, resampling, writing or opening rows."""

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

from ies.clinical_baseline import _verify_artifact_directory
from ies.clock_audit_ops import ClockAuditOpsError
from ies.io import sha256
from ies.workflow_cv import CONTRASTS, DIMENSIONS, MODE, validate_workflow_config


def _require(condition, code="workflow_review_invalid_result"):
    if not condition:
        raise ClockAuditOpsError(code)


def _read(path, limit=1024**2):
    _require(not path.is_symlink() and path.is_file() and path.stat().st_size <= limit)
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    _require(len(content) <= limit)
    return content


def _number(value):
    _require(type(value) in (int, float) and math.isfinite(value))
    return value


def _direction(value):
    return "lower" if value < 0 else "higher" if value > 0 else "equal"


def _summarize(report, config):
    _require(
        report["mode"] == MODE
        and report["experiment"] == "W001"
        and report["status"] == "complete"
        and report["data_class"] == "restricted_aggregate"
        and report["evaluation_scope"] == config["evaluation_scope"]
        and report["validation_split_evaluated"] is False
        and report["test_split_evaluated"] is False
        and report["original_splits_changed"] is False
        and report["automatic_test_or_gpu"] is False
        and report["clinical_advancement_decision"] == "not_applicable"
        and report["feature_dimensions"] == DIMENSIONS
        and report["primary_contrast"] == "typed_minus_pooled"
        and type(report["typed_timing_development_support"]) is bool
        and report["minimum_nll_improvement"] == config["minimum_nll_improvement"]
        and report["minimum_improved_folds"] == config["minimum_improved_folds"]
    )
    folds = report["folds"]
    _require(isinstance(folds, list) and len(folds) == config["folds"])
    _require(
        all(type(f["fold"]) is int for f in folds)
        and {f["fold"] for f in folds} == set(range(config["folds"]))
    )
    comparisons = {}
    for name in CONTRASTS:
        metric = report["metrics"][name]
        mean = _number(metric["nll_per_order"])
        interval = metric["conditional_patient_bootstrap_95ci"]
        _require(isinstance(interval, list) and len(interval) == 2)
        low, high = map(_number, interval)
        _require(low <= high)
        directions = {_direction(_number(f["contrasts"][name])) for f in folds}
        comparisons[name] = {
            "mean_loss_direction": _direction(mean),
            "conditional_interval": (
                "below_zero" if high < 0 else "above_zero" if low > 0 else "includes_zero"
            ),
            "fold_directions": "all_" + next(iter(directions)) if len(directions) == 1 else "mixed",
        }
    improved = sum(f["contrasts"]["typed_minus_pooled"] < 0 for f in folds)
    _require(type(report["improved_folds"]) is int and report["improved_folds"] == improved)
    primary = report["metrics"]["typed_minus_pooled"]
    supported = (
        primary["nll_per_order"] <= -config["minimum_nll_improvement"]
        and primary["conditional_patient_bootstrap_95ci"][1] < 0
        and improved >= config["minimum_improved_folds"]
        and report["metrics"]["typed_minus_intercept"]["nll_per_order"] < 0
    )
    _require(report["typed_timing_development_support"] == supported)
    return {
        "typed_timing_development_support": supported,
        "comparisons": comparisons,
        "clinical_advancement_decision": "not_applicable",
        "interpretation": "Descriptive review of existing development CV only; conditional "
        "intervals omit fitting and selection uncertainty. No new secondary pass rule.",
    }


def review_workflow(output_root: Path, job_id: str, source_commit: str) -> dict:
    """Return only allowlisted qualitative findings; source rows/models are never decoded."""
    try:
        _require(
            sys.platform == "linux" and os.environ.get("IES_EXECUTION_CONTEXT") == "ucsf",
            "workflow_review_requires_ucsf",
        )
        _require(
            bool(re.fullmatch(r"\d+", job_id))
            and bool(re.fullmatch(r"[0-9a-f]{40}", source_commit)),
            "workflow_review_invalid_job_binding",
        )
        root = _verify_artifact_directory(output_root, "workflow_review_invalid_storage")
        jobs = root / "jobs"
        _require(not jobs.is_symlink() and jobs.is_dir())
        matches = []
        with os.scandir(jobs) as entries:
            for index, entry in enumerate(entries, 1):
                _require(index <= 1000, "workflow_review_discovery_limit")
                _require(not entry.is_symlink())
                if not entry.is_dir(follow_symlinks=False):
                    continue
                receipt = Path(entry.path) / "submission.json"
                _require(not receipt.is_symlink())
                if not receipt.exists():
                    continue
                value = json.loads(_read(receipt, 16 * 1024))
                if value.get("job_id") == job_id:
                    _require(value == dict(job_id=job_id, job="workflow-cv", commit=source_commit))
                    matches.append(Path(entry.path))
        _require(len(matches) == 1, "workflow_review_job_not_unique")
        output = matches[0] / "workflow-cv"
        _require(not output.is_symlink())
        manifest_bytes = _read(output / "manifest.json")
        manifest = json.loads(manifest_bytes)
        _require(
            manifest["schema_version"] == 1
            and manifest["mode"] == MODE
            and manifest["status"] == "complete"
            and manifest["data_class"] == "restricted_clinical"
            and manifest["source_commit"] == source_commit
            and manifest["validation_split_evaluated"] is False
            and manifest["test_split_evaluated"] is False
            and manifest["original_splits_changed"] is False
            and manifest["raw_source_scan"] is False
            and manifest["gpu_used"] is False
            and manifest["prediction_rows_persisted"] is False
        )
        digests = manifest["artifacts_sha256"]
        report_bytes = _read(output / "workflow_report.json")
        config_bytes = _read(output / "config.json")
        for name, payload in (
            ("workflow_report.json", report_bytes),
            ("config.json", config_bytes),
        ):
            _require(hashlib.sha256(payload).hexdigest() == digests[name])
        models = output / "models.json"
        _require(
            not models.is_symlink() and models.is_file() and models.stat().st_size <= 64 * 1024**2
        )
        _require(sha256(models) == digests["models.json"])
        config = validate_workflow_config(json.loads(config_bytes))
        _require(manifest["evaluation_scope"] == config["evaluation_scope"])
        summary = _summarize(json.loads(report_bytes), config)
        _require(_read(output / "manifest.json") == manifest_bytes)
        _require(sha256(output / "workflow_report.json") == digests["workflow_report.json"])
        _require(sha256(output / "config.json") == digests["config.json"])
        return dict(
            mode="workflow_report_review",
            job_id=job_id,
            source_commit=source_commit,
            report_verified=True,
            validation_split_evaluated=False,
            test_split_evaluated=False,
            **summary,
        )
    except ClockAuditOpsError:
        raise
    except Exception:
        raise ClockAuditOpsError("workflow_review_invalid_result") from None
