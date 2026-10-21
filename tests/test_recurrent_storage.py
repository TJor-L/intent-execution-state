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
def test_every_git_storage_layout_is_rejected(storage, marker, role):
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
    expected = "legacy_input_git_unavailable" if role == "cohort" else "inside_repository"
    with pytest.raises(RecurrentTaskError, match=expected):
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
    assert result["error_code"] == "recurrent_legacy_input_git_unavailable"
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


@pytest.mark.parametrize(
    "problem", [None, "inner_tracked", "outer_tracked", "inner_unignored", "outer_unignored"]
)
def test_same_project_nested_worktree_input_is_read_only(storage, legacy, monkeypatch, problem):
    # Mirror the server's original-repo/handoff/<checkout> layout, not sibling trees.
    (legacy.original / ".gitignore").write_text("private/\nhandoff/\n")
    old_checkout = legacy.original / "handoff" / "old"
    active_checkout = legacy.original / "handoff" / "active"
    legacy.git("worktree", "add", "--detach", str(old_checkout))
    legacy.git("worktree", "add", "--detach", str(active_checkout))
    monkeypatch.setattr(runner, "ROOT", active_checkout)
    cohort = old_checkout / "private" / "cohort"
    cohort.mkdir(parents=True)
    (cohort / "manifest.json").write_text('{"generated": true}\n')
    (cohort / "cohort.parquet").write_bytes(b"generated fixture, not decoded")
    original_bytes = {p.name: p.read_bytes() for p in cohort.iterdir()}
    output = storage.root / "new-results"
    if problem:
        owner = old_checkout if problem.startswith("inner") else legacy.original
        if problem.endswith("unignored"):
            (owner / ".gitignore").write_text("")
            if problem == "outer_unignored":
                # An anchored common exclude ignores /private in the owning worktree,
                # but not /handoff/old/private as seen by the containing checkout.
                (old_checkout / ".gitignore").write_text("")
                (legacy.original / ".git" / "info" / "exclude").write_text("/private/\n")
        else:
            tracked = cohort / "cohort.parquet"
            digest = legacy.git("hash-object", "-w", str(tracked), cwd=owner).stdout.strip()
            legacy.git(
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{digest},{tracked.relative_to(owner).as_posix()}",
                cwd=owner,
            )
        review = runner.review_storage(cohort, output, storage.mapping)
        assert review["storage_checks"]["cohort_input"]["status"] == "blocked"
        assert review["storage_checks"]["new_output"]["status"] == "passed"
        assert review["storage_checks"]["overlap"]["status"] == "not_checked"
        with pytest.raises(RecurrentTaskError, match="legacy_input"):
            runner.validate_paths(cohort, output, storage.mapping)
        assert original_bytes == {p.name: p.read_bytes() for p in cohort.iterdir()}
        assert not output.exists()
        return
    runner.validate_paths(cohort, output, storage.mapping)
    assert original_bytes == {p.name: p.read_bytes() for p in cohort.iterdir()}
    assert not output.exists()
    with pytest.raises(RecurrentTaskError, match="inside_repository"):
        runner.validate_paths(cohort, old_checkout / "private" / "new", storage.mapping)


@pytest.mark.parametrize("problem", ["tracked", "unignored", "foreign", "nested"])
def test_legacy_exception_does_not_allow_tracked_or_other_repository_data(storage, legacy, problem):
    cohort = legacy.cohort
    if problem == "tracked":
        legacy.git("add", "-f", "private/cohort/cohort.parquet")
    elif problem == "unignored":
        (legacy.original / ".gitignore").write_text("")
    elif problem == "foreign":
        other = storage.root / "foreign"
        other.mkdir()
        legacy.git("init", "-q", cwd=other)
        (other / ".gitignore").write_text("private/\n")
        cohort = other / "private"
        cohort.mkdir()
    else:
        legacy.git("init", "-q", cwd=cohort)
    expected = (
        "legacy_input_foreign_repository" if problem in {"foreign", "nested"} else "legacy_input"
    )
    with pytest.raises(RecurrentTaskError, match=expected):
        runner.validate_paths(cohort, storage.root / "new-results", storage.mapping)


@pytest.mark.parametrize("timeout", [False, True])
def test_git_context_failure_has_its_own_sanitized_input_diagnostic(
    storage, legacy, monkeypatch, timeout
):
    def fail(*args, **kwargs):
        if timeout:
            raise subprocess.TimeoutExpired("private_sentinel", 30, stderr="private_sentinel")
        return subprocess.CompletedProcess(args[0], 128, stdout="", stderr="private_sentinel")

    monkeypatch.setattr(subprocess, "run", fail)
    result = runner.review_storage(legacy.cohort, storage.root / "new-results", storage.mapping)
    assert result["error_code"] == "recurrent_legacy_input_git_unavailable"
    assert result["storage_checks"]["cohort_input"]["status"] == "blocked"
    assert result["storage_checks"]["new_output"]["status"] == "passed"
    assert result["storage_checks"]["cohort_input"]["git_failure"] == {
        "operation": "common_directory",
        "location": "active_checkout",
        "reason": "timeout" if timeout else "unclassified_git_error",
        "exit_code": None if timeout else 128,
    }
    assert "private_sentinel" not in json.dumps(result)


@pytest.mark.parametrize(
    "operation,location",
    [
        ("common_directory", "active_checkout"),
        ("common_directory", "input_owner"),
        ("ignored_directory", "input_owner"),
        ("tracked_files", "input_owner"),
        ("ignored_directory", "input_ancestor"),
    ],
)
def test_failed_git_step_and_location_are_reported_without_stderr(
    storage, legacy, monkeypatch, capsys, operation, location
):
    (legacy.original / ".gitignore").write_text("private/\nhandoff/\n")
    owner = legacy.original / "handoff" / "old"
    legacy.git("worktree", "add", "--detach", str(owner))
    cohort = owner / "private" / "cohort"
    cohort.mkdir(parents=True)
    cwd = {
        "active_checkout": legacy.checkout,
        "input_owner": owner,
        "input_ancestor": legacy.original,
    }[location]
    verb = {
        "common_directory": "rev-parse",
        "ignored_directory": "check-ignore",
        "tracked_files": "ls-files",
    }[operation]
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        assert kwargs["env"]["LC_ALL"] == "C"
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        if kwargs["cwd"] == cwd and command[1] == verb:
            return subprocess.CompletedProcess(
                command,
                128,
                stdout="",
                stderr="fatal: detected dubious ownership in repository at PRIVATE_SENTINEL",
            )
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    report = runner.review_storage(cohort, storage.root / "new", storage.mapping)
    diagnostic = {
        "operation": operation,
        "location": location,
        "reason": "dubious_ownership",
        "exit_code": 128,
    }
    assert report["storage_checks"]["cohort_input"]["git_failure"] == diagnostic
    assert report["storage_checks"]["new_output"]["status"] == "passed"
    assert "PRIVATE_SENTINEL" not in json.dumps(report)
    with pytest.raises(runner.RecurrentGitError) as caught:
        runner.validate_paths(cohort, storage.root / "new", storage.mapping)
    runner.report_error(caught.value)
    captured = capsys.readouterr()
    assert json.loads(captured.err)["git_failure"] == diagnostic
    assert "PRIVATE_SENTINEL" not in captured.out + captured.err


def test_real_gitlink_error_is_classified_without_ignoring_it(storage, legacy):
    (legacy.original / ".gitignore").write_text("private/\nhandoff/\n")
    owner = legacy.original / "handoff" / "old"
    legacy.git("worktree", "add", "--detach", str(owner))
    cohort = owner / "private" / "cohort"
    cohort.mkdir(parents=True)
    head = legacy.git("rev-parse", "HEAD").stdout.strip()
    legacy.git("update-index", "--add", "--cacheinfo", f"160000,{head},handoff/old")
    report = runner.review_storage(cohort, storage.root / "new", storage.mapping)
    assert report["storage_checks"]["cohort_input"]["git_failure"] == {
        "operation": "ignored_directory",
        "location": "input_ancestor",
        "reason": "submodule_path",
        "exit_code": 128,
    }
    assert report["status"] == "blocked"
    assert not (storage.root / "new").exists()


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
