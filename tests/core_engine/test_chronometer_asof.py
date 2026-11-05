# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""As-of-HEAD history mode (temporal-crucible#29): every history field is a
deterministic function of the checked-out commit, never of the wall clock or
of how fast the machine streams `git log`."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from gitgalaxy.metrics import chronometer
from gitgalaxy.metrics.chronometer import Chronometer

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

DAY = 24 * 3600
T2014 = 1388534400  # 2014-01-01T00:00:00Z
T2015 = 1420070400  # 2015-01-01T00:00:00Z


def _git(repo: Path, *args: str, when: int | None = None, author: str = "Alice") -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": author,
        "GIT_AUTHOR_EMAIL": f"{author.lower()}@example.com",
        "GIT_COMMITTER_NAME": author,
        "GIT_COMMITTER_EMAIL": f"{author.lower()}@example.com",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }
    if when is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"@{when} +0000"
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def _commit(repo: Path, when: int, files: dict[str, str], author: str = "Alice") -> None:
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"c{when}", when=when, author=author)


@pytest.fixture
def old_repo(tmp_path: Path) -> Path:
    """A repository whose newest commit is 2015-01-01: over a decade before any
    plausible test run, so the wall-clock window holds none of its history."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, T2014 - 400 * DAY, {"stale.c": "int stale;\n", "hot.c": "int a;\n"})
    _commit(repo, T2014 + 30 * DAY, {"hot.c": "int a;\nint b;\n"}, author="Bob")
    _commit(repo, T2014 + 200 * DAY, {"hot.c": "int a;\nint b;\nint c;\n"})
    _commit(repo, T2015, {"new.c": "int n;\n"}, author="Bob")
    return repo


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(chronometer.HISTORY_ASOF_ENV, raising=False)
    monkeypatch.delenv(chronometer.HISTORY_NOW_ENV, raising=False)
    monkeypatch.delenv("GITGALAXY_DISABLE_GIT_HISTORY", raising=False)


def test_since_arg_anchors_to_now_when_given(monkeypatch):
    assert chronometer._since_arg(T2015) == f"--since=@{T2015 - chronometer._YEAR_SECONDS}"
    monkeypatch.setenv(chronometer.HISTORY_NOW_ENV, "1000000000")
    # An explicit pin still wins over the as-of anchor.
    assert chronometer._since_arg(T2015) == f"--since=@{1000000000 - chronometer._YEAR_SECONDS}"


def test_default_mode_sees_no_history_for_an_old_head(old_repo):
    chrono = Chronometer(old_repo)
    assert chrono.history_as_of is False
    assert chrono.get_file_history_metrics("hot.c")["commit_count"] == 0


def test_as_of_head_windows_history_at_the_commit(old_repo, monkeypatch):
    monkeypatch.setenv(chronometer.HISTORY_ASOF_ENV, "1")
    chrono = Chronometer(old_repo)
    assert chrono.history_as_of is True
    assert chrono.repo_max_time == T2015
    hot = chrono.get_file_history_metrics("hot.c")
    # The two 2014 edits are inside [2014-01-01, 2015-01-01]; the 2012 creation is not.
    assert hot["commit_count"] == 2
    assert hot["authors"] == {"Bob": 1, "Alice": 1}
    assert hot["mtime"] == T2014 + 200 * DAY
    assert chrono.get_file_history_metrics("new.c")["commit_count"] == 1


def test_as_of_head_dates_out_of_window_files_by_their_last_commit(old_repo, monkeypatch):
    monkeypatch.setenv(chronometer.HISTORY_ASOF_ENV, "1")
    stale = Chronometer(old_repo).get_file_history_metrics("stale.c")
    assert stale["commit_count"] == 0
    # Its last commit, not the checkout time the filesystem reports.
    assert stale["mtime"] == T2014 - 400 * DAY


def test_config_key_enables_as_of_head(old_repo):
    cfg = {"CHRONOMETER_CONFIG": {"HISTORY_AS_OF_HEAD": True}, "APERTURE_CONFIG": {}}
    chrono = Chronometer(old_repo, resolved_config=cfg)
    assert chrono.history_as_of is True
    assert chrono.get_file_history_metrics("hot.c")["commit_count"] == 2


def test_as_of_head_never_stops_at_the_coverage_guard(tmp_path, monkeypatch):
    """Above 200 files the default stream stops once ~50% of files are mapped, so
    which files carry history depends on log order and timing. As-of maps all."""
    repo = tmp_path / "wide"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, T2015 - 10 * DAY, {f"f{i:03d}.c": f"int v{i};\n" for i in range(250)})

    default = Chronometer(repo)
    mapped_default = sum(1 for i in range(250) if default.churn_map.get(f"f{i:03d}.c"))
    assert mapped_default < 250

    monkeypatch.setenv(chronometer.HISTORY_ASOF_ENV, "1")
    as_of = Chronometer(repo)
    assert all(as_of.churn_map.get(f"f{i:03d}.c") == 1 for i in range(250))
