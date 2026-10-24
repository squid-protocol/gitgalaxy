"""#138: warn when `git ls-files` (the census) skips untracked files."""

import logging
import shutil
import subprocess

import pytest

from gitgalaxy import galaxyscope
from gitgalaxy.galaxyscope import _untracked_files, _warn_untracked

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(root, *args):
    subprocess.run(  # noqa: S603
        [galaxyscope._GIT_BIN, "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


@needs_git
def test_untracked_file_listed(repo):
    (repo / "new.py").write_text("y = 2\n")
    assert _untracked_files(repo) == ["new.py"]


@needs_git
def test_modified_unstaged_is_not_untracked(repo):
    (repo / "a.py").write_text("x = 2\n")  # tracked, scanned from disk
    assert _untracked_files(repo) == []


@needs_git
def test_clean_repo_and_ignored_files(repo):
    (repo / ".gitignore").write_text("junk.py\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore")
    (repo / "junk.py").write_text("z = 3\n")
    assert _untracked_files(repo) == []


@needs_git
def test_staged_new_file_is_not_untracked(repo):
    (repo / "b.py").write_text("q = 1\n")
    _git(repo, "add", "b.py")
    assert _untracked_files(repo) == []


def test_non_git_dir(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    assert _untracked_files(tmp_path) == []


def test_git_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(galaxyscope, "_GIT_BIN", str(tmp_path / "no-such-git"))
    assert _untracked_files(tmp_path) == []


def test_warning_text_and_truncation(caplog):
    with caplog.at_level(logging.WARNING):
        _warn_untracked([])
        assert not caplog.records
        _warn_untracked([f"f{i}.py" for i in range(7)])
    msg = caplog.records[0].getMessage()
    assert "7 untracked file(s) are NOT scanned" in msg
    assert "f4.py" in msg
    assert "f5.py" not in msg
    assert msg.endswith("...")


@needs_git
def test_census_warns_on_untracked(repo, caplog):
    (repo / "new.py").write_text("y = 2\n")
    scope = galaxyscope.Orchestrator(str(repo), config={})
    with caplog.at_level(logging.WARNING):
        scope._build_file_census()
    assert any("new.py" in r.getMessage() and "NOT scanned" in r.getMessage() for r in caplog.records)
    assert "a.py" in scope.git_tracked_files
