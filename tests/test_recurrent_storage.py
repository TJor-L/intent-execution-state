"""Generated filesystem layouts only; no clinical source contents or scheduler."""

import json
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
    assert not (storage.root / "jobs").exists()
