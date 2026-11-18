# ruff: noqa: S101, S603
"""`debt_marker`: where each TODO / FIXME / HACK / XXX marker sits (line, class, comment text), written by a real scan."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = """#include <stdio.h>

/* TODO: handle the empty case */
int add(int a, int b) {
    // FIXME: overflow is not checked
    return a + b;
}

int sub(int a, int b) {
    int x = a - b; /* HACK: clamp later */
    return x;
}
"""


def _scan(tmp: Path) -> Path:
    src, out = tmp / "proj", tmp / "out"
    (src / "src").mkdir(parents=True)
    (src / "src" / "a.c").write_text(SOURCE)
    env = {**os.environ, "GITGALAXY_DISABLE_GIT_HISTORY": "1", "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"}
    env["PYTHONPATH"] = str(REPO)
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--db-only", "--output", str(out)],
        check=True,
        capture_output=True,
        env=env,
        cwd=tmp,
    )
    return next(out.glob("*_galaxy_master.db"))


def test_a_scan_records_each_marker_with_its_line_class_and_text(tmp_path):
    db = _scan(tmp_path)
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT f.file_path, m.line, m.class, m.text FROM debt_marker m JOIN file_data f ON f.id = m.file_id ORDER BY m.line"
        ).fetchall()
        assert rows == [
            ("src/a.c", 3, "planned", "/* TODO: handle the empty case */"),
            ("src/a.c", 5, "fragile", "// FIXME: overflow is not checked"),
            ("src/a.c", 10, "fragile", "/* HACK: clamp later */"),
        ]
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("DELETE FROM file_data")
        assert con.execute("SELECT COUNT(*) FROM debt_marker").fetchone() == (0,)
    finally:
        con.close()
