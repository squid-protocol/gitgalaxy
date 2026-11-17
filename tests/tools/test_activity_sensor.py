# ruff: noqa: S101, S603, S607
"""`gitgalaxy activity`: windows, rename-following age, ownership, roles and worklists, on a git history built with fixed dates."""

import os
import subprocess
import sys
from pathlib import Path

from gitgalaxy.tools.sensors import activity

REPO = Path(__file__).resolve().parents[2]
NOW = 1_800_000_000  # a fixed "today"
DAY = 86400


def _commit(tmp, who, when, message, files=None):
    env = {**os.environ, "GIT_AUTHOR_DATE": f"{when} +0000", "GIT_COMMITTER_DATE": f"{when} +0000"}
    for name, text in (files or {}).items():
        (tmp / name).write_text(text)
    subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True, capture_output=True, env=env)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp),
            "-c",
            f"user.name={who}",
            "-c",
            f"user.email={who}@example.com",
            "commit",
            "-qm",
            message,
        ],
        check=True,
        capture_output=True,
        env=env,
    )


def _history(tmp):
    """old.c (ann adds, bob touches, cara moves it to moved.c), hot.c (six commits by cara in the last 60 days), dormant.c and notes.md (ann, once)."""
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    body = "int a;\n" * 20
    _commit(
        tmp, "ann", NOW - 3000 * DAY, "add", {"old.c": body, "hot.c": body, "dormant.c": body, "notes.md": "hello\n"}
    )
    _commit(tmp, "bob", NOW - 1000 * DAY, "touch old", {"old.c": body + "// x\n"})
    for i in range(6):
        _commit(tmp, "cara", NOW - (60 - 10 * i) * DAY, f"hot {i}", {"hot.c": body + f"// {i}\n"})
    subprocess.run(["git", "-C", str(tmp), "mv", "old.c", "moved.c"], check=True)
    _commit(tmp, "cara", NOW - 2 * DAY, "move")
    return tmp


def _panel(tmp, now=NOW):
    events, authors = activity.history(tmp, "HEAD")
    return {r["path"]: r for r in activity.panel(events, authors, now)}


def test_windows_counts_and_ownership(tmp_path):
    hot = _panel(_history(tmp_path))["hot.c"]
    assert hot["commits_365d"] == 6
    assert hot["commits_90d"] == 6
    assert hot["commits_lifetime"] == 7
    assert hot["authors_365d"] == 1
    assert hot["top_author"] == "cara@example.com"
    assert hot["top_author_share"] == 1.0
    assert hot["owner_active"] is True


def test_a_rename_keeps_the_files_age_and_history(tmp_path):
    rows = _panel(_history(tmp_path))
    assert "old.c" not in rows
    assert rows["moved.c"]["commits_lifetime"] == 3  # the add, bob's touch, the move
    assert rows["moved.c"]["age_years"] > 8  # from the add 3000 days before NOW, not from the move


def test_a_dormant_file_has_no_recent_activity_and_roles_are_told_apart(tmp_path):
    rows = _panel(_history(tmp_path))
    dormant = rows["dormant.c"]
    assert dormant["commits_365d"] == 0
    assert dormant["top_author_share"] is None
    assert dormant["days_since_last_change"] == 3000.0
    assert dormant["role"] == "source"
    assert rows["notes.md"]["role"] == "other"  # prose, not code


def test_owner_active_means_a_commit_in_the_last_two_years(tmp_path):
    repo = _history(tmp_path)
    assert _panel(repo)["dormant.c"]["owner_active"] is False  # ann's last commit anywhere is 3000 days back
    assert (
        _panel(repo, NOW - 2500 * DAY)["dormant.c"]["owner_active"] is True
    )  # 500 days after her commit, 2500 days before NOW


def test_worklists_default_to_source_and_split_by_reach(tmp_path):
    events, authors = activity.history(_history(tmp_path), "HEAD")
    lists = activity.worklists(activity.panel(events, authors, NOW), {"dormant.c": 40, "hot.c": 1})
    assert [r["path"] for r in lists["hot_now"]] == ["hot.c"]
    assert [r["path"] for r in lists["dormant"]] == ["dormant.c"]  # notes.md is prose
    assert [r["path"] for r in lists["quiet_foundations"]] == ["dormant.c"]
    assert lists["quiet_foundations"][0]["reach_files"] == 40


def test_the_command_runs_on_a_real_history(tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "gitgalaxy.cli", "activity", str(_history(tmp_path)), "--rev", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout
    assert "HOT NOW" in out
    assert "OWNERSHIP CONTEXT" in out
    assert "hot.c: 6 commits in 365 d (6 in 90 d)" in out
