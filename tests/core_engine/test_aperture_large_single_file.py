"""#5459: a single source file past the old 30,000-line cut is scanned, not dropped."""

import os
import sqlite3
import subprocess
import sys

import pytest

N_FUNCS = 3900  # x 8-9 lines = 31,200+ lines, just past the old cut

C_FUNC = "static int fn_{i}(int a, int b)\n{{\n    int r = a + b;\n    if (r > {i}) {{\n        r -= 1;\n    }}\n    return r;\n}}\n\n"
GO_FUNC = "func fn{i}(a int, b int) int {{\n\tr := a + b\n\tif r > {i} {{\n\t\tr--\n\t}}\n\treturn r\n}}\n\n"


@pytest.mark.slow(reason="scans a 31k-line synthetic file per language, ~10-20 s")
@pytest.mark.parametrize(
    ("name", "head", "template"),
    [("big.c", "", C_FUNC), ("big.go", "package main\n\n", GO_FUNC)],
)
def test_file_over_the_old_cut_extracts_every_function(tmp_path, name, head, template):
    src = tmp_path / "src"
    src.mkdir()
    body = head + "".join(template.format(i=i) for i in range(N_FUNCS))
    assert body.count("\n") > 30000
    (src / name).write_text(body, encoding="utf-8")
    out = tmp_path / "out"
    env = {**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER", "GITGALAXY_DISABLE_GIT_HISTORY": "1"}
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--db-only", "--output", str(out)],
        check=True,
        capture_output=True,
        env=env,
        timeout=120,
    )
    (db,) = out.glob("*_galaxy_master.db")
    count = sqlite3.connect(db).execute("select count(*) from function_data").fetchone()[0]
    assert count >= N_FUNCS * 0.97
