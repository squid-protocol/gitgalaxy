# ruff: noqa: S101, S603, S607
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""The activity readings in plain units (wiki 08-27): commits in 365 and 90 days, authors, the top author's share and days since the last change.

They come from their own complete pass anchored at HEAD's commit time, so they are the same in every mode and on every machine, and they are
reported only when measured (never a partial count)."""

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
KEYS = ("commits_365d", "commits_90d", "authors_365d", "top_author_share_365d", "days_since_last_change")


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
        (repo / rel).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"c{when}", when=when, author=author)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """HEAD is 2015-01-01, over a decade before any test run: the wall-clock year holds none of this history, the HEAD-anchored year holds all of it."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _commit(r, T2014 - 400 * DAY, {"stale.c": "int stale;\n", "hot.c": "int a;\n"})
    _commit(r, T2014 + 30 * DAY, {"hot.c": "int a;\nint b;\n"}, author="Bob")
    _commit(r, T2014 + 200 * DAY, {"hot.c": "int a;\nint b;\nint c;\n"})
    _commit(r, T2015 - 40 * DAY, {"hot.c": "int a;\nint b;\nint c;\nint d;\n"})
    _commit(r, T2015, {"new.c": "int n;\n"}, author="Bob")
    return r


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(chronometer.HISTORY_ASOF_ENV, raising=False)
    monkeypatch.delenv(chronometer.HISTORY_NOW_ENV, raising=False)
    monkeypatch.delenv("GITGALAXY_DISABLE_GIT_HISTORY", raising=False)


def _cfg(**chrono):
    return {"CHRONOMETER_CONFIG": chrono, "APERTURE_CONFIG": {}}


def test_readings_count_the_year_before_head_not_the_wall_clock_year(repo):
    hot = Chronometer(repo).get_file_history_metrics("hot.c")
    assert hot["commits_365d"] == 3  # Bob at +30 d, Alice at +200 d and -40 d; the 2012 creation is outside the year
    assert hot["commits_90d"] == 1
    assert hot["authors_365d"] == 2
    assert hot["top_author_share_365d"] == 0.667
    assert hot["days_since_last_change"] == 40.0
    new = Chronometer(repo).get_file_history_metrics("new.c")
    assert (
        new["commits_365d"],
        new["commits_90d"],
        new["authors_365d"],
        new["top_author_share_365d"],
        new["days_since_last_change"],
    ) == (
        1,
        1,
        1,
        1.0,
        0.0,
    )


def test_a_file_the_year_missed_is_dated_by_its_last_commit(repo):
    stale = Chronometer(repo).get_file_history_metrics("stale.c")
    assert stale["commits_365d"] == 0
    assert stale["authors_365d"] == 0
    assert "top_author_share_365d" not in stale  # nobody to share it between
    assert stale["days_since_last_change"] == 765.0  # 400 days before the year began, plus the year


def test_as_of_mode_gives_the_same_readings(repo, monkeypatch):
    plain = Chronometer(repo)
    monkeypatch.setenv(chronometer.HISTORY_ASOF_ENV, "1")
    as_of = Chronometer(repo)
    for rel in ("hot.c", "new.c", "stale.c"):
        a, b = plain.get_file_history_metrics(rel), as_of.get_file_history_metrics(rel)
        assert {k: a.get(k) for k in KEYS} == {k: b.get(k) for k in KEYS}


def test_a_cut_window_reports_nothing_rather_than_a_partial_count(repo):
    cut = Chronometer(repo, resolved_config=_cfg(ACTIVITY_MAX_COMMITS=2))
    assert cut.activity_complete is False
    assert not any(k in cut.get_file_history_metrics("hot.c") for k in KEYS)


def test_a_cut_dating_pass_leaves_only_the_undated_file_unmeasured(repo):
    chrono = Chronometer(repo, resolved_config=_cfg(ACTIVITY_DATING_MAX_COMMITS=1))
    assert chrono.get_file_history_metrics("hot.c")["commits_365d"] == 3
    stale = chrono.get_file_history_metrics("stale.c")
    assert stale["commits_365d"] == 0
    assert "days_since_last_change" not in stale


def test_no_readings_without_usable_history(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.c").write_text("int a;\n")
    assert not any(k in Chronometer(plain).get_file_history_metrics("a.c") for k in KEYS)
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _commit(r, T2015, {"a.c": "int a;\n"})
    monkeypatch.setenv("GITGALAXY_DISABLE_GIT_HISTORY", "1")
    assert not any(k in Chronometer(r).get_file_history_metrics("a.c") for k in KEYS)
