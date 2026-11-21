"""#8774: a delta scan (`--incremental <baseline.db> --baseline <sha>`) records what a full scan of the
same commit records, in the columns it SHOULD match.

Three losses pinned here, each found by diffing a delta chain against a full scan of one commit:
  * `directory_group` was '__monolith__' on every file: the delta never ran the spatial mapper (#8774);
  * `excluded_artifacts` / `total_excluded_artifacts` were not carried: the delta recorded only the
    auditor's drops, and `audit_binary_anomalies` / `audit_unknown_packages` (Phase 10) read 0 (#8774);
  * a modified manifest (`pyproject.toml`) vanished: it passes the extension gate only through the
    Intent Lock, which the delta's hand-rolled census never consulted (#8774).
Also pinned: a rehydrated file keeps its raw pre-adjustment counts and its parent classes.
"""

import os
import shutil
import sqlite3
import subprocess
import sys

import pytest


def _body(prefix: str, n: int) -> str:
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


def _head(root) -> str:
    return subprocess.run(  # noqa: S603
        ["git", "rev-parse", "HEAD"],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _scan(src, out, *extra):
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GITGALAXY_DISABLE_GIT_HISTORY": "1"}
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--db-only", "--output", str(out), *extra],
        check=True,
        env=env,
        capture_output=True,
        timeout=600,
    )
    return out / f"{src.name}_galaxy_master.db"


def _snapshot(db):
    con = sqlite3.connect(db)
    try:
        files = dict(con.execute("SELECT file_path, directory_group FROM file_data"))
        excluded = set(con.execute("SELECT file_path, exclusion_reason FROM excluded_artifacts"))
        repo = con.execute(
            "SELECT total_files, total_excluded_artifacts, total_loc, total_doc_files, "
            "audit_binary_anomalies, audit_unknown_packages FROM repo_data"
        ).fetchone()
        raw = dict(con.execute("SELECT file_path, raw_arch_api * 1000 + raw_state_unreferenced FROM file_data"))
        return files, excluded, repo, raw
    finally:
        con.close()


@pytest.fixture
def repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required")
    root = tmp_path / "estate"
    (root / "pkg" / "sub").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "estate"\nversion = "1.0"\n')
    (root / "pkg" / "a.py").write_text(_body("a", 12))
    (root / "pkg" / "sub" / "b.py").write_text(_body("b", 12) + "class B(Base):\n    pass\n")
    (root / "pkg" / "edited.py").write_text(_body("e", 12))
    (root / "logo.png").write_text("not really an image\n")  # a denied extension: excluded from both scans
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "baseline")
    return root


def test_delta_matches_full_after_a_commit(repo, tmp_path):
    baseline_db = _scan(repo, tmp_path / "baseline")
    baseline_sha = _head(repo)
    assert "pyproject.toml" in _snapshot(baseline_db)[0], "sanity: the full scan indexes the manifest"

    # one commit: modify the root manifest and a nested module, add a file and an excluded one
    (repo / "pyproject.toml").write_text('[project]\nname = "estate"\nversion = "1.1"\n')
    (repo / "pkg" / "edited.py").write_text(_body("e", 12) + "def added():\n    return 1\n")
    (repo / "pkg" / "new.py").write_text(_body("n", 12))
    (repo / "icon.gif").write_text("not really an image either\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")

    full = _snapshot(_scan(repo, tmp_path / "full"))
    delta = _snapshot(_scan(repo, tmp_path / "delta", "--incremental", str(baseline_db), "--baseline", baseline_sha))

    f_files, f_excluded, f_repo, f_raw = full
    d_files, d_excluded, d_repo, d_raw = delta
    assert set(d_files) == set(f_files), "#8774: the delta drops no file a full scan keeps (nor adds one)"
    assert "pyproject.toml" in d_files
    assert d_files == f_files, "#8774: directory_group is the folder group, never '__monolith__'"
    assert d_files["pkg/sub/b.py"] == "pkg/sub"
    assert d_excluded == f_excluded, "#8774: excluded artifacts are carried, old and new"
    assert {p for p, _ in d_excluded} >= {"logo.png", "icon.gif"}
    assert d_repo == f_repo, "repo totals (files, excluded, loc, docs, audits) match"
    assert d_raw == f_raw, "a rehydrated file keeps its raw pre-adjustment counts"
