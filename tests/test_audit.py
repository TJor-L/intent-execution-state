import json
import os

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ies.cli import main
from ies.data.audit import audit_parquet


def test_metadata_only_no_values_statistics_or_paths(tmp_path, monkeypatch):
    path = tmp_path / "private-name.parquet"
    table = pa.table({"number": [987654321], "text": ["DO_NOT_EMIT"]})
    table = table.replace_schema_metadata({b"private-note": b"DO_NOT_EMIT"})
    pq.write_table(table, path)
    original = pq.ParquetFile

    class FooterOnly:
        def __init__(self, path):
            self.file = original(path)
            self.schema_arrow = self.file.schema_arrow
            self.metadata = self.file.metadata

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def read(self, *args, **kwargs):
            pytest.fail("Audit attempted to read rows")

    monkeypatch.setattr(pq, "ParquetFile", FooterOnly)
    report = audit_parquet(path)
    rendered = json.dumps(report)
    assert "DO_NOT_EMIT" not in rendered and "987654321" not in rendered
    assert "private-name" not in rendered and "statistics" not in report["files"][0]
    assert report["files"][0]["rows_in_footer"] == 1


def test_audit_limits_and_symlinks(tmp_path):
    for i in range(5):
        directory = tmp_path / f"part{i}"
        directory.mkdir()
        pq.write_table(pa.table({"a": [i]}), directory / "part.parquet")
    (tmp_path / "linked").symlink_to(tmp_path / "part0", target_is_directory=True)
    report = audit_parquet(tmp_path, max_files=2, max_directories=3)
    assert len(report["files"]) <= 2
    assert report["directories_visited"] <= 3
    assert report["truncated_or_limit_reached"]
    with pytest.raises(ValueError):
        audit_parquet(tmp_path, max_files=0)


def test_audit_error_does_not_emit_path_or_value(tmp_path):
    (tmp_path / "secret.parquet").write_text("PRIVATE_VALUE")
    report = audit_parquet(tmp_path)
    assert report["failures"] == 1
    assert "PRIVATE_VALUE" not in json.dumps(report)
    assert "secret" not in json.dumps(report)


def test_cli_blocks_audit_outside_server_context(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("IES_EXECUTION_CONTEXT", raising=False)
    with pytest.raises(SystemExit) as error:
        main(["audit", "--data-root", str(tmp_path), "--output", str(tmp_path / "result.json")])
    assert error.value.code == 2
    assert not (tmp_path / "result.json").exists()
    assert str(tmp_path) not in capsys.readouterr().err


def test_empty_audit_fails_cli_instead_of_claiming_success(tmp_path, monkeypatch):
    monkeypatch.setenv("IES_EXECUTION_CONTEXT", "ucsf")
    with pytest.raises(SystemExit) as error:
        main(["audit", "--data-root", str(tmp_path), "--output", str(tmp_path / "report.json")])
    assert error.value.code == 2
    assert os.path.isfile(tmp_path / "report.json")
