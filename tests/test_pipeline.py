import json
from pathlib import Path

import pytest
import yaml

from ies.cli import main
from ies.config import DEFAULT_CONFIG, load_config
from ies.training import pipeline


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "synthetic.yaml"
    path.write_text(yaml.safe_dump(dict(DEFAULT_CONFIG, n_patients=12, bootstrap_replicates=10)))
    return path


def test_full_reproducible_run_manifests_and_no_overwrite(tmp_path, config):
    first, second = tmp_path / "first", tmp_path / "second"
    assert pipeline.run_experiment(config, first) == pipeline.run_experiment(config, second)
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["data_class"] == "synthetic"
    for filename, digest in manifest["artifacts_sha256"].items():
        assert pipeline.sha256(first / filename) == digest
        assert pipeline.sha256(second / filename) == digest
    with pytest.raises(FileExistsError):
        pipeline.run_experiment(config, first)


def test_failed_run_is_recorded_without_exception_payload(tmp_path, config, monkeypatch):
    def fail(*args):
        raise ValueError("unshareable-payload")

    monkeypatch.setattr(pipeline, "fit_baseline", fail)
    with pytest.raises(ValueError):
        pipeline.run_experiment(config, tmp_path / "failure")
    manifest = (tmp_path / "failure/manifest.json").read_text()
    assert json.loads(manifest)["status"] == "failed"
    assert "unshareable-payload" not in manifest


def test_individual_cli_stages(tmp_path, config, capsys):
    events, cohort, model = [tmp_path / p for p in ("events.parquet", "cohort.json", "model.json")]
    assert main(["generate", "--config", str(config), "--output", str(events)]) == 0
    assert main(["validate", "--events", str(events)]) == 0
    assert (
        main(
            [
                "build-cohort",
                "--config",
                str(config),
                "--events",
                str(events),
                "--output",
                str(cohort),
            ]
        )
        == 0
    )
    assert (
        main(["train", "--config", str(config), "--cohort", str(cohort), "--output", str(model)])
        == 0
    )
    assert (
        main(
            [
                "evaluate",
                "--cohort",
                str(cohort),
                "--model",
                str(model),
                "--output-dir",
                str(tmp_path / "evaluation"),
                "--bootstrap",
                "10",
            ]
        )
        == 0
    )
    assert Path(tmp_path / "evaluation/metrics.json").exists()
    assert "synthetic" in capsys.readouterr().out


def test_config_rejects_unknown_keys_and_mismatched_horizon(tmp_path, config):
    value = yaml.safe_load(config.read_text())
    value["clinical_path"] = "not-allowed"
    config.write_text(yaml.safe_dump(value))
    with pytest.raises(ValueError, match="exactly"):
        load_config(config)
    value.pop("clinical_path")
    value["horizon_hours"] = 12
    config.write_text(yaml.safe_dump(value))
    with pytest.raises(ValueError, match="horizon"):
        load_config(config)
