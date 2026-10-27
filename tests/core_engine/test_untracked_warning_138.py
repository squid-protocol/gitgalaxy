"""#138: a git census (`git ls-files`) skips untracked files; the scan must say so."""

import logging
import shutil
import subprocess
from unittest.mock import patch

import pytest

from gitgalaxy import galaxyscope
from gitgalaxy.galaxyscope import Orchestrator, _untracked_files, _untracked_warning

GIT = shutil.which("git") or "git"
_CONFIG = {"LANGUAGE_DEFINITIONS": {}, "APERTURE_CONFIG": {}, "PARANOID_MODE": False}
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(root, *args):
    subprocess.run(  # noqa: S603
        [GIT, "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def _census_warnings(root, caplog):
    scope = Orchestrator(str(root), _CONFIG)
    with caplog.at_level(logging.WARNING, logger="GalaxyScope"):
        scope._build_file_census()
    return scope, [r.getMessage() for r in caplog.records if "UNTRACKED_FILES" in r.getMessage()]


def test_untracked_file_warns_and_is_not_scanned(repo, caplog):
    (repo / "new.py").write_text("y = 2\n")
    scope, warns = _census_warnings(repo, caplog)
    assert len(warns) == 1 and "new.py" in warns[0] and "git add" in warns[0]
    assert scope.untracked_files == ["new.py"]
    assert "new.py" not in scope.git_tracked_files and "a.py" in scope.git_tracked_files


def test_modified_unstaged_is_scanned_so_no_warning(repo, caplog):
    (repo / "a.py").write_text("x = 2\n")
    scope, warns = _census_warnings(repo, caplog)
    assert warns == [] and "a.py" in scope.git_tracked_files
    assert _untracked_files(repo) == []


def test_clean_repo_has_no_warning(repo, caplog):
    assert _census_warnings(repo, caplog)[1] == []


def test_gitignored_untracked_file_is_not_reported(repo, caplog):
    (repo / ".gitignore").write_text("*.log\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore")
    (repo / "build.log").write_text("noise\n")
    assert _census_warnings(repo, caplog)[1] == []


def test_non_git_dir_returns_empty_and_does_not_warn(tmp_path, caplog):
    (tmp_path / "a.py").write_text("x = 1\n")
    assert _untracked_files(tmp_path) == []
    scope, warns = _census_warnings(tmp_path, caplog)
    assert warns == [] and scope.git_tracked_files == set()  # filesystem-walk fallback


def test_git_missing_returns_empty(repo):
    with patch.object(galaxyscope.subprocess, "check_output", side_effect=FileNotFoundError):
        assert _untracked_files(repo) == []


def test_warning_text_truncates_long_lists():
    msg = _untracked_warning([f"f{i}.py" for i in range(8)])
    assert msg.startswith("8 untracked") and "f4.py" in msg and "f5.py" not in msg and msg.endswith("...")
