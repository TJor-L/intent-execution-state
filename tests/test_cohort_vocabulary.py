"""Generated-only tests for the private aggregate vocabulary audit."""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from conftest import load_script

from ies.cli import main
from ies.cohort_readiness.contract import CohortAuditError, load_vocabulary_mapping
from ies.cohort_readiness.runner import plan_vocabulary_audit
from ies.cohort_readiness.vocabulary import scan_vocabulary


def mapping(tmp_path: Path, **limit_updates) -> Path:
    source = tmp_path / "toy-source"
    source.mkdir()
    value = {
        "schema_version": 1,
        "execution_context": "ucsf",
        "institutional_access_confirmed": True,
        "mapping_reviewed": True,
        "protocol_frozen_reviewed": True,
        "purpose": "frequency_prn_vocabulary",
        "source": {
            "path": str(source),
            "columns": {"prn": "toy_prn", "frequency": "toy_frequency"},
        },
        "limits": {
            "max_files": 4,
            "max_entries": 8,
            "max_row_groups": 8,
            "max_rows": 100,
            "max_source_bytes": 1_000_000,
            "max_distinct_per_column": 8,
            "minimum_report_count": 2,
            "batch_rows": 2,
            "runtime_seconds": 30,
            "cpu_seconds": 30,
            "cpus": 1,
            "memory_mb": 512,
        },
    }
    value["limits"].update(limit_updates)
    path = tmp_path / "cohort_vocabulary.local.yaml"
    path.write_text(yaml.safe_dump(value, sort_keys=False))
    return path


def write_source(path: Path) -> None:
    config = yaml.safe_load(path.read_text())
    source = Path(config["source"]["path"])
    pq.write_table(
        pa.table(
            {
                "toy_prn": [False, False, True, None],
                "toy_frequency": ["single", "single", "recurring", "rare-private"],
                "do_not_read": ["PRIVATE_ROW"] * 4,
            }
        ),
        source / "part.parquet",
        row_group_size=2,
    )


def test_complete_projected_vocabulary_suppresses_rare_values(tmp_path, monkeypatch):
    path = mapping(tmp_path)
    write_source(path)
    original = pq.ParquetFile

    class ProjectedOnly:
        def __init__(self, *args, **kwargs):
            self.inner = original(*args, **kwargs)
            self.schema_arrow = self.inner.schema_arrow
            self.metadata = self.inner.metadata

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.inner.close()

        def iter_batches(self, *, columns, **kwargs):
            assert columns == ["toy_prn", "toy_frequency"]
            return self.inner.iter_batches(columns=columns, **kwargs)

    monkeypatch.setattr(pq, "ParquetFile", ProjectedOnly)
    report = scan_vocabulary(load_vocabulary_mapping(path)[0])
    rendered = json.dumps(report)
    assert report["status"] == "complete" and report["scan"]["projected_columns"] == 2
    assert report["vocabulary"]["prn"]["null_rows"] == 1
    assert report["vocabulary"]["frequency"]["values"] == [
        {"kind": "string", "value": "single", "count": 2}
    ]
    assert report["vocabulary"]["frequency"]["suppressed_rows"] == 2
    assert "rare-private" not in rendered and "PRIVATE_ROW" not in rendered


def test_data_free_plan_contains_no_paths_or_private_columns(tmp_path, monkeypatch):
    path = mapping(tmp_path)
    monkeypatch.setattr(pq, "ParquetFile", lambda *a, **k: pytest.fail("plan opened data"))
    plan = plan_vocabulary_audit(path)
    rendered = yaml.safe_dump(plan)
    assert plan["full_reviewed_snapshot_required"] is True
    assert str(tmp_path) not in rendered and "toy_prn" not in rendered


@pytest.mark.parametrize(
    ("update", "error"),
    [
        ({"max_files": 0}, "invalid_cohort_audit_mapping"),
        ({"max_rows": 3}, "cohort_vocabulary_rows_limit"),
        ({"max_row_groups": 1}, "cohort_vocabulary_row_groups_limit"),
        ({"max_distinct_per_column": 1}, "cohort_vocabulary_distinct_limit"),
    ],
)
def test_mapping_and_scan_limits_fail_closed(tmp_path, update, error):
    path = mapping(tmp_path, **update)
    if update == {"max_files": 0}:
        with pytest.raises(CohortAuditError, match=error):
            load_vocabulary_mapping(path)
        return
    write_source(path)
    with pytest.raises(CohortAuditError, match=error):
        scan_vocabulary(load_vocabulary_mapping(path)[0])


def test_unknown_keys_and_unreviewed_protocol_fail(tmp_path):
    path = mapping(tmp_path)
    value = yaml.safe_load(path.read_text())
    value["unknown"] = True
    path.write_text(yaml.safe_dump(value))
    with pytest.raises(CohortAuditError, match="invalid_cohort_audit_mapping"):
        load_vocabulary_mapping(path)
    value.pop("unknown")
    value["protocol_frozen_reviewed"] = False
    path.write_text(yaml.safe_dump(value))
    with pytest.raises(CohortAuditError):
        load_vocabulary_mapping(path)


def test_cli_plan_is_sanitized_and_run_requires_slurm(tmp_path, capsys):
    path = mapping(tmp_path)
    assert main(["cohort-vocabulary", "plan", "--mapping", str(path)]) == 0
    assert str(tmp_path) not in capsys.readouterr().out
    with pytest.raises(SystemExit) as error:
        main(
            [
                "cohort-vocabulary",
                "run",
                "--mapping",
                str(path),
                "--output-dir",
                str(tmp_path / "output"),
            ]
        )
    assert error.value.code == 2
    assert str(tmp_path) not in capsys.readouterr().err


def test_server_submission_binds_digest_and_worker_resources(tmp_path):
    path = mapping(tmp_path)
    server = load_script("server")
    config = {
        "python_executable": "/server/python",
        "data_root": "/restricted/input",
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 4,
            "memory": "8G",
            "time_limit": "00:20:00",
        },
    }
    command = server.sbatch_command(config, "cohort-vocabulary", tmp_path / "output", path)
    export = next(item for item in command if item.startswith("--export="))
    assert "IES_COHORT_AUDIT_SHA256=" in export
    assert "--cpus-per-task=1" in command and "--mem=512M" in command
    assert str(server.ROOT / "slurm/cohort_vocabulary.sbatch") in command
    assert str(path.absolute()) in command
