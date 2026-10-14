import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import load_script

boundary = load_script("check_repository")
handoff = load_script("handoff")
server = load_script("server")


@pytest.mark.parametrize(
    "path",
    [
        "data/patients.parquet",
        "artifacts/metrics.json",
        "configs/remote.local.yaml",
        "src/ies/records.csv",
        "docs/patient.parquet",
        ".env",
        "checkpoints/model.pt",
        "fixtures/real.json",
        "results/unreviewed.md",
        "../README.md",
    ],
)
def test_publication_allowlist_rejects_private_artifacts(path):
    assert not boundary.allowed(path)


def test_publication_allows_data_source_code():
    assert boundary.allowed("src/ies/data/events.py")
    assert boundary.allowed("configs/remote.example.yaml")


def test_handoff_pins_clean_commit_and_rejects_dirty_tree(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/server_codex_prompt.md").write_text("Expected {{COMMIT_SHA}}")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    output = tmp_path.parent / f"{tmp_path.name}-prompt.md"
    revision = handoff.create_handoff(tmp_path, output)
    assert output.read_text() == f"Expected {revision}"
    assert server.source_revision(tmp_path) == revision
    (tmp_path / "change.py").write_text("# pending\n")
    with pytest.raises(ValueError, match="Commit"):
        handoff.create_handoff(tmp_path, output)
    with pytest.raises(ValueError, match="clean"):
        server.source_revision(tmp_path)


def test_slurm_revision_guard_rejects_wrong_commit(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "file.py").write_text("# fixture\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    result = subprocess.run(
        ["bash", str(server.ROOT / "slurm/verify_source.sh")],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "IES_EXPECTED_COMMIT": "incorrect"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Source revision" in result.stderr


def test_server_configuration_requires_authorized_context(tmp_path, monkeypatch):
    monkeypatch.delenv("IES_EXECUTION_CONTEXT", raising=False)
    example = Path(server.ROOT / "configs/remote.example.yaml")
    with pytest.raises(ValueError, match="Institutional"):
        server.load_server_config(example)
    value = yaml.safe_load(example.read_text())
    value["institutional_access_confirmed"] = True
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(value))
    with pytest.raises(ValueError, match="authorized server"):
        server.load_server_config(path)


def test_server_command_is_argument_vector_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("IES_EXECUTION_CONTEXT", "ucsf")
    data = tmp_path / "private source"
    data.mkdir()
    config = {
        "execution_context": "ucsf",
        "institutional_access_confirmed": True,
        "data_root": str(data),
        "output_root": str(tmp_path / "outputs"),
        "python_executable": sys.executable,
        "slurm": {
            "partition": "cpu",
            "account": None,
            "cpus": 2,
            "memory": "4G",
            "time_limit": "00:10:00",
        },
        "audit": {"max_files": 12, "max_directories": 100},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config))
    loaded = server.load_server_config(path)
    command = server.sbatch_command(loaded, "schema-audit", tmp_path / "outputs/job")
    assert str(data) in command  # Remains a single argument even with whitespace.
    assert command[:2] == ["sbatch", "--parsable"]
    assert not any("gpu" in arg or "gres" in arg for arg in command)
    assert command[-2:] == ["12", "100"]
    with pytest.raises(ValueError, match="Only"):
        server.sbatch_command(loaded, "gpu", tmp_path)
    config["slurm"]["cpus"] = 8
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="CPU"):
        server.load_server_config(path)
