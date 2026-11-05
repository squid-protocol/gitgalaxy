# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 18: Instructional Code Examples (`lit_code_blocks`) probed through a real scan.

The rule counts fence lines (opening and closing), so one closed fence reads 2. This plants one doc per fence
shape and extension and reads `lit_code_blocks` from the scan DB. Near misses (no fence, a 4-space indented
fence, fence text inside source comments) stay 0. AsciiDoc `----` listing blocks are claimed by the language
profile but read 0: a strict xfail (sibling gap, a different mechanism).
"""

import os
import sqlite3
import subprocess
import sys

import pytest

pytestmark = pytest.mark.slow(
    reason="two real scans of planted files; the fixture's cost lands on whichever test runs first in a CI split part"
)

_FENCE = "```py\nx = 1\n```\n"
# name -> (file name, body, expected count)
FIRE = {
    "md": ("a.md", f"# T\n\n{_FENCE}", 2),
    "mdx": ("a.mdx", f"# T\n\n{_FENCE}", 2),
    "markdown": ("a.markdown", f"# T\n\n{_FENCE}", 2),
    "mdown": ("a.mdown", f"# T\n\n{_FENCE}", 2),
    "mkd": ("a.mkd", f"# T\n\n{_FENCE}", 2),
    "tilde": ("tilde.md", "# T\n\n~~~py\nx = 1\n~~~\n", 2),
    "list_item": ("list.md", "# T\n\n- item\n\n  ```py\n  x = 1\n  ```\n", 2),
    "blockquote": ("quote.md", "# T\n\n> ```py\n> x = 1\n> ```\n", 2),
    "two_blocks": ("two.md", f"# T\n\n{_FENCE}\ntext\n\n{_FENCE}", 4),
    "unclosed": ("unclosed.md", "# T\n\n```py\nx = 1\n", 1),
}
QUIET = {
    "no_fence": ("none.md", "# T\n\ninline `x` only\n"),
    # four spaces make the fence literal code text (CommonMark)
    "indented_four": ("indented4.md", "# T\n\n    ```py\n    x = 1\n    ```\n"),
    "python_comment": ("a.py", "x = 1\n# ```py\n"),
    "c_comment": ("a.c", "int x = 1;\n/* ```py */\n"),
}
GAPS = {
    "asciidoc_listing": ("a.adoc", "= T\n\n[source,py]\n----\nx = 1\n----\n"),
}


def _scan(tmp_path, files) -> dict:
    src = tmp_path / "src"
    src.mkdir()
    for name, body in files.items():
        (src / name).write_text(body, "utf-8")
    out = tmp_path / "out"
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(src), "--db-only", "--output", str(out)],
        env=env,
        check=True,
        capture_output=True,
        timeout=180,
    )
    (db,) = out.glob("*_galaxy_master.db")
    con = sqlite3.connect(db)
    try:
        return {p: n for p, n in con.execute("select file_path, lit_code_blocks from file_data")}
    finally:
        con.close()


@pytest.fixture(scope="module")
def scans(tmp_path_factory):
    fire = {f: b for f, b, _ in FIRE.values()}
    return (
        _scan(tmp_path_factory.mktemp("fire"), fire),
        _scan(tmp_path_factory.mktemp("quiet"), {**dict(QUIET.values()), **dict(GAPS.values())}),
    )


@pytest.mark.parametrize("name", sorted(FIRE))
def test_fence_is_counted_through_a_real_scan(scans, name):
    fname, _, expected = FIRE[name]
    assert scans[0][fname] == expected


@pytest.mark.parametrize("name", sorted(QUIET))
def test_near_miss_is_not_counted(scans, name):
    assert scans[1][QUIET[name][0]] == 0


@pytest.mark.xfail(strict=True, reason="sibling gap: AsciiDoc ---- listing blocks are not read")
@pytest.mark.parametrize("name", sorted(GAPS))
def test_unread_shape_is_counted(scans, name):
    assert scans[1][GAPS[name][0]] >= 1
