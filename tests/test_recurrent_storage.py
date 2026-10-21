"""Generated filesystem layouts only; no clinical source contents or scheduler."""

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from conftest import load_script

from ies import recurrent_task_runner as runner
from ies.recurrent_task import RecurrentTaskError


@pytest.fixture
def storage(tmp_path, monkeypatch):
    root = tmp_path.resolve() / "physical"
    root.mkdir()
    alias = tmp_path.resolve() / "scratch"
    alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(runner, "AUTHORIZED_ROOT", alias)
    monkeypatch.setattr(runner, "ROOT", root / "checkout")
    cohort = root / "cohort"
    cohort.mkdir()
    source = root / "source"
    source.mkdir()
    mapping = SimpleNamespace(feasibility=SimpleNamespace(sources=[SimpleNamespace(path=source)]))
    return SimpleNamespace(root=root, alias=alias, cohort=cohort, source=source, mapping=mapping)


@pytest.mark.parametrize("canonical", [False, True])
def test_trusted_root_alias_and_canonical_spelling_agree(storage, canonical):
    prefix = storage.root if canonical else storage.alias
    output = prefix / "jobs" / "new"
    cohort = prefix / "cohort"
    runner.validate_paths(cohort, output, storage.mapping)
    result = runner.review_storage(cohort, output, storage.mapping)
    assert result["status"] == "passed"
    assert result["legacy_rejection_checks"]["output_not_literal_scratch_child"] is canonical
    assert result["legacy_rejection_checks"]["output_has_symlink_ancestor"] is not canonical
    assert not output.exists()
    assert str(storage.root) not in json.dumps(result)


@pytest.mark.parametrize("target", ["inside", "outside"])
@pytest.mark.parametrize("role", ["cohort", "output"])
def test_links_below_trusted_root_remain_rejected(storage, target, role):
    destination = storage.cohort if target == "inside" else storage.root.parent
    link = storage.root / "redirect"
    link.symlink_to(destination, target_is_directory=True)
    cohort = link if role == "cohort" else storage.cohort
    output = link / "new" if role == "output" else storage.root / "new"
    with pytest.raises(RecurrentTaskError, match="symlink_below_root|outside_authorized_root"):
        runner.validate_paths(cohort, output, storage.mapping)
    assert runner.review_storage(cohort, output, storage.mapping)["status"] == "blocked"


@pytest.mark.parametrize("marker", ["directory", "worktree_file", "broken_symlink"])
@pytest.mark.parametrize("role", ["cohort", "output"])
def test_git_markers_block_writes_but_do_not_authorize_reads(storage, marker, role):
    folder = storage.cohort if role == "cohort" else storage.root / "other_repo"
    folder.mkdir(exist_ok=True)
    git = folder / ".git"
    if marker == "directory":
        git.mkdir()
    elif marker == "worktree_file":
        git.write_text("gitdir: synthetic-reference\n")
    else:
        git.symlink_to(storage.root / "absent")
    output = storage.root / "new" if role == "cohort" else folder / "private"
    if role == "cohort":
        runner.validate_paths(storage.cohort, output, storage.mapping)
    else:
        with pytest.raises(RecurrentTaskError, match="inside_repository"):
            runner.validate_paths(storage.cohort, output, storage.mapping)
    assert not output.exists()


def test_arbitrary_alias_to_storage_is_not_a_trusted_root(storage):
    alias = storage.root.parent / "unapproved_alias"
    alias.symlink_to(storage.root)
    with pytest.raises(RecurrentTaskError, match="unapproved_alias"):
        runner.validate_paths(storage.cohort, alias / "new", storage.mapping)


@pytest.mark.parametrize("kind", ["relative", "parent", "outside", "checkout"])
def test_invalid_paths_keep_distinct_fixed_codes(storage, kind):
    paths = {
        "relative": (type(storage.root)("relative"), "invalid_path"),
        "parent": (storage.root / "unused" / ".." / "new", "invalid_path"),
        "outside": (storage.root.parent / "new", "outside_authorized_root"),
        "checkout": (storage.root / "checkout" / "private", "inside_repository"),
    }
    path, code = paths[kind]
    with pytest.raises(RecurrentTaskError, match=code):
        runner.validate_paths(storage.cohort, path, storage.mapping)


@pytest.mark.parametrize("kind", ["source_child", "source_parent", "cohort_child", "equal"])
def test_overlap_uses_canonical_paths(storage, kind):
    paths = {
        "source_child": storage.alias / "source" / "new",
        "source_parent": storage.alias,
        "cohort_child": storage.alias / "cohort" / "new",
        "equal": storage.alias / "source",
    }
    with pytest.raises(RecurrentTaskError, match="overlapping_storage"):
        runner.validate_paths(storage.cohort, paths[kind], storage.mapping)


def test_storage_review_cli_never_submits_or_writes(storage, monkeypatch, capsys):
    cli = load_script("recurrent_audit")
    monkeypatch.setattr(
        cli.runpy,
        "run_path",
        lambda *args: {
            "load_server_config": lambda *args, **kw: {"output_root": str(storage.alias)},
            "main": lambda: pytest.fail("Storage review cannot invoke the submit entry"),
        },
    )
    monkeypatch.setattr(cli, "discover_clock_artifacts", lambda p: (storage.cohort, None))
    monkeypatch.setattr(cli, "discover_existing_mapping", lambda *args: storage.root / "mapping")
    monkeypatch.setattr(cli, "load_eligibility_mapping", lambda p: (storage.mapping, "b" * 64))
    monkeypatch.setattr(sys, "argv", ["recurrent_audit", "check-storage", "--config", "toy"])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed" and result["submitted"] is False
    assert not (storage.root / "jobs").exists()
    (storage.root / ".git").mkdir()
    assert cli.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error_code"] == "recurrent_storage_inside_repository"
    assert (
        result["storage_checks"]["new_output"]["error_code"]
        == "recurrent_storage_inside_repository"
    )
    assert not (storage.root / "jobs").exists()


@pytest.fixture
def legacy(storage, monkeypatch):
    original = storage.root / "original"
    original.mkdir()

    def git(*args, cwd=original):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

    git("init", "-q")
    (original / ".gitignore").write_text("private/\n")
    git("add", ".gitignore")
    git(
        "-c",
        "user.name=Generated Test",
        "-c",
        "user.email=generated@example.invalid",
        "commit",
        "-qm",
        "Generated fixture only",
    )
    checkout = storage.root / "job-checkout"
    git("worktree", "add", "--detach", str(checkout))
    monkeypatch.setattr(runner, "ROOT", checkout)
    cohort = original / "private" / "cohort"
    cohort.mkdir(parents=True)
    (cohort / "manifest.json").write_text('{"generated": true}\n')
    (cohort / "cohort.parquet").write_bytes(b"generated bytes, never decoded by path checks")
    return SimpleNamespace(original=original, checkout=checkout, cohort=cohort, git=git)


def test_legacy_ignored_input_read_only_with_external_write_root(storage, legacy):
    before = {p.name: p.read_bytes() for p in legacy.cohort.iterdir()}
    output = storage.root / "new-results" / "jobs" / "new"
    runner.validate_paths(legacy.cohort, output, storage.mapping)
    assert runner.review_storage(legacy.cohort, output, storage.mapping)["status"] == "passed"
    assert before == {p.name: p.read_bytes() for p in legacy.cohort.iterdir()}
    assert not output.exists()
    # The same ignored location remains forbidden for every new write.
    with pytest.raises(RecurrentTaskError, match="inside_repository"):
        runner.validate_paths(legacy.cohort, legacy.original / "private" / "new", storage.mapping)


@pytest.mark.parametrize("layout", ["original", "nested_worktree", "broken_git", "gitlink"])
def test_read_only_input_does_not_query_git(storage, legacy, monkeypatch, layout):
    cohort = legacy.cohort
    if layout in {"nested_worktree", "gitlink"}:
        (legacy.original / ".gitignore").write_text("private/\nhandoff/\n")
        owner = legacy.original / "handoff" / "old"
        legacy.git("worktree", "add", "--detach", str(owner))
        cohort = owner / "private" / "cohort"
        cohort.mkdir(parents=True)
        (cohort / "manifest.json").write_text('{"generated": true}')
        if layout == "gitlink":
            head = legacy.git("rev-parse", "HEAD").stdout.strip()
            legacy.git("update-index", "--add", "--cacheinfo", f"160000,{head},handoff/old")
    elif layout == "broken_git":
        (cohort / ".git").write_text("gitdir: missing-synthetic-path\n")
    before = {p.name: p.read_bytes() for p in cohort.iterdir()}
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("Input must not query Git"))
    output = storage.root / "new-results"
    runner.validate_paths(cohort, output, storage.mapping)
    report = runner.review_storage(cohort, output, storage.mapping)
    assert report["status"] == "passed" and report["input_git_queries"] is False
    assert before == {p.name: p.read_bytes() for p in cohort.iterdir()}
    assert not output.exists()
    with pytest.raises(RecurrentTaskError, match="inside_repository"):
        runner.validate_paths(cohort, cohort.parent / "new", storage.mapping)


@pytest.mark.parametrize("kind", ["legacy", "source", "ancestor", "new"])
def test_separate_write_root_is_disjoint_and_never_created(storage, legacy, kind):
    roots = {
        "legacy": legacy.original / "private" / "new",
        "source": storage.source / "new",
        "ancestor": storage.root,
        "new": storage.root / "new-results",
    }
    root = roots[kind]
    if kind == "new":
        runner.validate_output_root(root, storage.source, legacy.original / "private")
        assert not root.exists()
    else:
        with pytest.raises(RecurrentTaskError):
            runner.validate_output_root(root, storage.source, legacy.original / "private")


@pytest.mark.parametrize("action", ["check-storage", "plan", "submit"])
def test_cli_keeps_legacy_discovery_separate_from_write_destination(
    storage, legacy, monkeypatch, capsys, action
):
    cli = load_script("recurrent_audit")
    artifact_root = legacy.original / "private"
    destination = storage.root / "new-results"
    config = {"output_root": str(artifact_root), "data_root": str(storage.source)}
    discovery = []
    forwarded = []

    def server_main():
        forwarded.extend(sys.argv)
        return 0

    monkeypatch.setattr(
        cli.runpy,
        "run_path",
        lambda *args: {
            "load_server_config": lambda *args, **kwargs: config,
            "main": server_main,
        },
    )

    def discover(path):
        discovery.append(path)
        return legacy.cohort, None

    monkeypatch.setattr(cli, "discover_clock_artifacts", discover)
    monkeypatch.setattr(cli, "discover_existing_mapping", lambda *args: storage.root / "mapping")
    monkeypatch.setattr(cli, "load_eligibility_mapping", lambda p: (storage.mapping, "b" * 64))
    monkeypatch.setattr(
        sys,
        "argv",
        ["recurrent_audit", action, "--config", "toy", "--output-root", str(destination)],
    )
    assert cli.main() == 0
    assert discovery == [artifact_root]
    assert config["output_root"] == str(artifact_root)
    assert not destination.exists()
    if action == "check-storage":
        assert not forwarded
        assert json.loads(capsys.readouterr().out)["status"] == "passed"
    else:
        assert forwarded[forwarded.index("--cohort-dir") + 1] == str(legacy.cohort)
        assert forwarded[forwarded.index("--recurrent-output-root") + 1] == str(destination)
        assert ("--wait" in forwarded) is (action == "submit")


@pytest.mark.parametrize("valid_destination", [True, False])
def test_server_submission_writes_only_to_the_separate_root(
    storage, legacy, monkeypatch, capsys, valid_destination
):
    server = load_script("server")
    artifact_root = legacy.original / "private"
    destination = storage.root / "new-results" if valid_destination else storage.source / "new"
    (legacy.cohort / "manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "mode": "bounded_phase0_cohort_extraction",
                "data_class": "restricted_clinical",
                "mapping_sha256": "b" * 64,
            }
        )
    )
    original_files = {p.name: p.read_bytes() for p in legacy.cohort.iterdir()}
    config = {
        "data_root": str(storage.source),
        "output_root": str(artifact_root),
        "python_executable": sys.executable,
        "slurm": {
            "cpus": 1,
            "memory": "2G",
            "time_limit": "00:10:00",
            "partition": "synthetic",
            "account": None,
        },
    }
    monkeypatch.setattr(server, "load_server_config", lambda *a, **kw: config)
    monkeypatch.setattr(server, "load_eligibility_mapping", lambda p: (storage.mapping, "b" * 64))
    monkeypatch.setattr(server, "source_revision", lambda: "a" * 40)
    commands = []
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if command[0] == "sbatch":
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="999999\n", stderr="")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "server",
            "submit",
            "recurrent-audit",
            "--config",
            "toy",
            "--mapping",
            "toy",
            "--cohort-dir",
            str(legacy.cohort),
            "--recurrent-output-root",
            str(destination),
        ],
    )
    assert server.main() == (0 if valid_destination else 2)
    assert original_files == {p.name: p.read_bytes() for p in legacy.cohort.iterdir()}
    assert not (artifact_root / "jobs").exists()
    captured = capsys.readouterr()
    assert str(storage.root) not in captured.out + captured.err
    if valid_destination:
        assert len(commands) == 1
        assert commands[0][-2] == str(legacy.cohort)
        assert type(destination)(commands[0][-1]).is_relative_to(destination)
        (receipt,) = destination.glob("jobs/*/submission.json")
        assert json.loads(receipt.read_text()) == {
            "job_id": "999999",
            "job": "recurrent-audit",
            "commit": "a" * 40,
        }
    else:
        assert not commands and not destination.exists()
