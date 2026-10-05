"""#4483: a delta scan (`--incremental <baseline.db>`) indexes exactly what a full scan of the same
tree does -- same files, functions and classes.

The loss it guards: an unchanged file under SARIF_IGNORED_PATHS is persisted with zeroed signal
counts (Phase 10.5 sanitises it after the audit), and the delta's statistical auditor re-judged
that zero-signal row as a data dump and dropped it. Also pinned: uncommitted edits to tracked
files (staged and unstaged) ARE re-scanned; an untracked file is not, because a full scan's
census (`git ls-files`) never lists it either.
"""

import os
import shutil
import sqlite3
import subprocess
import sys

import pytest

_CONFIG = 'galaxyscope:\n  SARIF_IGNORED_PATHS:\n    - "tests/"\n'


def _body(prefix: str, n: int) -> str:
    """A >50 LOC module with real branching, so a full scan measures signal in it."""
    return "".join(
        f"def {prefix}_{i}(x, y):\n    if x > y:\n        return x - y\n    for k in range(y):\n        x += k\n    return x\n\n\n"
        for i in range(n)
    )


def _git(root, *args):
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
    )


def _scan(src, out, config, *extra):
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GITGALAXY_DISABLE_GIT_HISTORY": "1"}
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "gitgalaxy.galaxyscope",
            str(src),
            "--config",
            str(config),
            "--db-only",
            "--output",
            str(out),
            *extra,
        ],
        check=True,
        env=env,
        capture_output=True,
        timeout=600,
    )
    return out / f"{src.name}_galaxy_master.db"


def _sets(db):
    con = sqlite3.connect(db)
    try:
        files = {r[0] for r in con.execute("SELECT file_path FROM file_data")}
        funcs = set(
            con.execute(
                "SELECT f.file_path, fn.func_name FROM function_data fn JOIN file_data f ON f.id = fn.file_id"
            ).fetchall()
        )
        classes = set(
            con.execute(
                "SELECT f.file_path, c.class_name FROM class_data c JOIN file_data f ON f.id = c.file_id"
            ).fetchall()
        )
        return files, funcs, classes
    finally:
        con.close()


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required")
    root = tmp_path / "estate"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "unchanged.py").write_text(_body("keep", 12) + "class Keep:\n    def m(self):\n        return 1\n")
    (root / "src" / "modified.py").write_text(_body("mod", 12))
    (root / "src" / "deleted.py").write_text(_body("gone", 12))
    (root / "src" / "edited.py").write_text(_body("edit", 12))
    # unchanged AND under SARIF_IGNORED_PATHS: persisted with zeroed signals (the #4483 victim)
    (root / "tests" / "ignored_big.py").write_text(_body("ign", 20) + "class Ign:\n    pass\n")
    (tmp_path / "cfg.yaml").write_text(_CONFIG)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "baseline")
    return root


def test_delta_equals_full_after_commit_and_uncommitted_edits(repo, tmp_path):
    cfg = tmp_path / "cfg.yaml"
    baseline_db = _scan(repo, tmp_path / "baseline", cfg)
    base_files, _, _ = _sets(baseline_db)
    assert "tests/ignored_big.py" in base_files

    # committed: modify one file, delete another
    (repo / "src" / "modified.py").write_text(_body("mod", 12) + "class Added:\n    def n(self):\n        return 2\n")
    (repo / "src" / "deleted.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    # uncommitted: one unstaged edit, one staged new file, one untracked file
    (repo / "src" / "edited.py").write_text(_body("edit", 12) + "def uncommitted_edit():\n    return 3\n")
    (repo / "src" / "staged_new.py").write_text(_body("stg", 12))
    (repo / "src" / "logo.png").write_text("not really an image\n")  # a denied extension: both scans skip it
    _git(repo, "add", "src/staged_new.py", "src/logo.png")
    (repo / "src" / "untracked.py").write_text(_body("unt", 12))

    full = _sets(_scan(repo, tmp_path / "full", cfg))
    delta = _sets(_scan(repo, tmp_path / "delta", cfg, "--incremental", str(baseline_db)))

    assert "tests/ignored_big.py" in full[0], "sanity: the full scan indexes the ignored-path file"
    assert "src/unchanged.py" in delta[0]
    assert "tests/ignored_big.py" in delta[0], "#4483: the zero-signal ignored-path file must not be dropped"
    assert "src/deleted.py" not in delta[0]
    assert ("src/edited.py", "uncommitted_edit") in delta[1], "an unstaged edit is re-scanned"
    assert "src/staged_new.py" in delta[0], "a staged new file is scanned"
    assert "src/untracked.py" not in full[0], "a full scan never lists an untracked file"
    assert "src/untracked.py" not in delta[0]
    assert ("src/modified.py", "n") in delta[1] and ("src/modified.py", "Added") in delta[2]
    assert "src/logo.png" not in full[0] and "src/logo.png" not in delta[0]
    assert delta[0] == full[0]
    assert delta[1] == full[1]
    assert delta[2] == full[2]
