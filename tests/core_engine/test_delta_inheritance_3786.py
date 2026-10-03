"""#3786: a delta scan keeps the inherited-method call links a full scan records.

The resolver reads each class's parents from `cls["inheritance"]`; the DB stores them in
`class_data.inheritance_parents`. The rehydrator must hand the resolver the same key and shape.
"""

import os
import shutil
import sqlite3
import subprocess
import sys

import pytest

BASE = "class Base:\n    def load(self):\n        return 1\n"
CHILD = "from base import Base\n\n\nclass Child(Base):\n    def run(self):\n        return self.load()\n"
OTHER = "def unrelated():\n    return 0\n"

_SQL = """
    SELECT sf.func_name, f.callee, f.step, df.file_path, dfn.func_name
    FROM fcall_data f
    JOIN function_data sf ON sf.id = f.src_func_id
    LEFT JOIN file_data df ON df.id = f.dst_file_id
    LEFT JOIN function_data dfn ON dfn.id = f.dst_func_id
    WHERE f.callee = 'load' ORDER BY 1, 2, 3
"""


def _git(root, *args):
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
    )


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


def _edges(db):
    con = sqlite3.connect(db)
    try:
        commit = con.execute("SELECT commit_hash FROM file_data ORDER BY id DESC LIMIT 1").fetchone()[0]
        n = con.execute("SELECT COUNT(*) FROM fcall_data").fetchone()[0]
        return con.execute(_SQL).fetchall(), n, commit
    finally:
        con.close()


def test_delta_scan_keeps_inherited_method_call_edge(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required")
    repo = tmp_path / "estate"
    repo.mkdir()
    for name, text in (("base.py", BASE), ("child.py", CHILD), ("other.py", OTHER)):
        (repo / name).write_text(text)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")
    full_db = _scan(repo, tmp_path / "full")
    full, _, _ = _edges(full_db)
    assert full, "the full scan must record the inherited self.load() call"
    assert full[0][2] == "class"
    (repo / "other.py").write_text(OTHER + "\n\ndef another():\n    return 2\n")
    _git(repo, "commit", "-qam", "touch an unrelated file")
    delta, _, _ = _edges(_scan(repo, tmp_path / "delta", "--incremental", str(full_db)))
    assert delta == full
