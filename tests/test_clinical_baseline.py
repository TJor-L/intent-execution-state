"""Generated-only tests for the private clinical intercept baseline."""

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import load_script

from ies import clinical_baseline
from ies.clinical_baseline import (
    ClinicalBaselineError,
    load_baseline_config,
    run_clinical_baseline,
)
from ies.cohort_readiness.extract import SCHEMA
from ies.io import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]


def _cohort(tmp_path: Path, duration: float = 1.0) -> tuple[Path, str]:
    path = tmp_path / "cohort"
    path.mkdir(mode=0o700)
    rows = []
    for index, split in enumerate(("train", "train", "validation", "test")):
        rows.append(
            {
                "patient_id": f"string:person-{index}",
                "order_id": f"string:order-{index}",
                "encounter_id": f"string:visit-{index}",
                "split": split,
                "index_time_hours": 100.0 + index,
                "duration_hours": duration if index == 0 else 2.0 + index,
                "cause": index % 3,
                "outcome": ("right_censored", "execution", "terminal_without_execution")[index % 3],
            }
        )
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), path / "cohort.parquet")
    manifest = {
        "status": "complete",
        "mode": "bounded_phase0_cohort_extraction",
        "data_class": "restricted_clinical",
        "bounded_domain": True,
        "source_commit": "a" * 40,
        "artifacts_sha256": {"cohort.parquet": sha256(path / "cohort.parquet")},
    }
    write_json(path / "manifest.json", manifest)
    return path, sha256(path / "manifest.json")


def test_clinical_baseline_is_private_validation_only_and_reproducible(tmp_path, monkeypatch):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    cohort, cohort_digest = _cohort(tmp_path)
    config_path = ROOT / "configs/clinical_baseline.yaml"
    config, config_digest = load_baseline_config(config_path)
    outputs = []
    for name in ("first", "second"):
        output = tmp_path / name
        output.mkdir(mode=0o700)
        manifest = run_clinical_baseline(
            cohort,
            output,
            config,
            config_digest,
            cohort_digest,
            "b" * 40,
        )
        assert manifest["status"] == "complete"
        assert manifest["test_split_evaluated"] is False
        assert manifest["features_used"] is False
        assert manifest["gpu_used"] is False and manifest["database_write"] is False
        assert set(output.iterdir()) == {
            output / "model.json",
            output / "validation_metrics.json",
            output / "validation_predictions.json",
            output / "manifest.json",
        }
        assert all(path.stat().st_mode & 0o077 == 0 for path in output.iterdir())
        outputs.append(output)
    for filename in ("model.json", "validation_metrics.json", "validation_predictions.json"):
        assert (outputs[0] / filename).read_bytes() == (outputs[1] / filename).read_bytes()
    model = json.loads((outputs[0] / "model.json").read_text())
    assert model["data_class"] == "restricted_clinical"
    assert "string:person-3" not in model["train_patients"]


def test_clinical_baseline_rejects_zero_duration_and_changed_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(clinical_baseline, "AUTHORIZED_ROOT", tmp_path)
    cohort, cohort_digest = _cohort(tmp_path, duration=0.0)
    config, config_digest = load_baseline_config(ROOT / "configs/clinical_baseline.yaml")
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(ClinicalBaselineError, match="invalid_clinical_cohort"):
        run_clinical_baseline(cohort, output, config, config_digest, cohort_digest, "b" * 40)
    with pytest.raises(ClinicalBaselineError, match="clinical_cohort_changed"):
        clinical_baseline._verify_cohort(cohort, hashlib.sha256(b"changed").hexdigest())


def test_server_submission_is_digest_bound_and_cpu_only(tmp_path):
    cohort, cohort_digest = _cohort(tmp_path)
    server = load_script("server")
    config = {
        "python_executable": "/server/python",
        "output_root": str(tmp_path),
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 4,
            "memory": "8G",
            "time_limit": "00:20:00",
        },
    }
    baseline_config = ROOT / "configs/clinical_baseline.yaml"
    command = server.sbatch_command(
        config,
        "clinical-baseline",
        tmp_path / "job",
        cohort_dir=cohort,
        baseline_config=baseline_config,
    )
    export = next(item for item in command if item.startswith("--export="))
    assert f"IES_COHORT_MANIFEST_SHA256={cohort_digest}" in export
    assert "IES_BASELINE_CONFIG_SHA256=" in export
    assert "--cpus-per-task=2" in command and "--mem=4096M" in command
    assert str(server.ROOT / "slurm/clinical_baseline.sbatch") in command
