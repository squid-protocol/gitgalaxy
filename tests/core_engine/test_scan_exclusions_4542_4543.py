"""#4542 / #4543: the scanner's file gate must not silently drop real source.

#4542: a directory named `env` (or `.env`, `virtualenv`) is a virtualenv only when it carries a
virtualenv's markers; room4doom's `gameplay/src/env/*.rs` is game code.
#4543: a long line that is wholly a prose comment does not trip the saturation gate (room4doom's
`//!` module docs, crispy-doom's hexen p_map.c block comment); minified code and data payloads do.
"""

import pytest

from gitgalaxy.core.aperture import ApertureFilter, looks_like_virtualenv
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PROSE = (
    "The refresh uses the next and prev links to follow lists of things in sectors as they are "
    "being drawn. The sprite, frame, and angle elements determine which patch is used to draw "
    "the sprite if it is visible. "
) * 4  # ~760 chars of spaced words
assert len(PROSE) > 600


def _filter(root):
    return ApertureFilter(root, LANGUAGE_DEFINITIONS, APERTURE_CONFIG)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _scan(root, rel, text):
    f = _write(root / rel, text)
    return _filter(root).is_in_scope(f, content=text)


# ------------------------------------------------------------------------------
# #4542: virtualenvs by marker, not by name
# ------------------------------------------------------------------------------
def test_env_source_directory_is_scanned(tmp_path):
    f = _write(tmp_path / "gameplay/src/env/doors.rs", "pub fn open_door() {}\n")
    ok, _, reason = _filter(tmp_path).evaluate_path_integrity(f)
    assert ok, reason


def test_virtualenv_named_source_package_is_scanned(tmp_path):
    f = _write(tmp_path / "src/virtualenv/__init__.py", "x = 1\n")
    ok, _, reason = _filter(tmp_path).evaluate_path_integrity(f)
    assert ok, reason


@pytest.mark.parametrize(
    "marker",
    ["pyvenv.cfg", "bin/activate", "Scripts/activate", "lib/python3.12/site-packages/pkg/__init__.py", "conda-meta/x"],
)
def test_real_virtualenv_named_env_stays_excluded(tmp_path, marker):
    _write(tmp_path / "env" / marker, "")
    f = _write(tmp_path / "env/lib/python3.12/site-packages/six.py", "x = 1\n")
    assert looks_like_virtualenv(tmp_path / "env")
    ok, _, reason = _filter(tmp_path).evaluate_path_integrity(f)
    assert not ok
    assert "System Exclusion" in reason


def test_venv_and_dotvenv_stay_excluded_by_name(tmp_path):
    flt = _filter(tmp_path)
    for rel in ("venv/app.py", ".venv/app.py"):
        f = _write(tmp_path / rel, "x = 1\n")
        assert not flt.evaluate_path_integrity(f)[0], rel


def test_file_named_env_is_not_a_virtualenv(tmp_path):
    assert not looks_like_virtualenv(_write(tmp_path / "env", "PATH=/bin\n"))


# ------------------------------------------------------------------------------
# #4543: comment lines do not trip the saturation gate
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "rel,text",
    [
        ("tools/editor-core/src/project.rs", f"//! {PROSE}\n\nuse std::error::Error;\n\nfn main() {{}}\n"),
        ("src/hexen/p_map.c", f"/*\nmobj_t NOTES\n\n{PROSE}\n*/\n\nint x;\n"),
        ("src/p_map.c", f"/* {PROSE} */\nint x;\n"),
        ("src/thing.cpp", f"#include <vector>\n// {PROSE}\nint main() {{ return 0; }}\n"),
        ("src/doc.h", f"/**\n * {PROSE}\n */\nint x;\n"),
        ("tool.py", f"# {PROSE}\nimport os\n"),
    ],
)
def test_long_comment_line_is_scanned(tmp_path, rel, text):
    result = _scan(tmp_path, rel, text)
    assert result["is_in_scope"], result["reason"]


MINIFIED_JS = (
    '/*! tinylib v1.2.3 | MIT */!function(e,t){"use strict";var n=[],r=e.document,i=Object.getPrototypeOf,'
    + "o=n.slice,a=n.concat,s=n.push,u=n.indexOf,l={},c=l.toString,f=l.hasOwnProperty;" * 12
    + "}(window);\n"
)
MINIFIED_CSS = (
    "/*! normalize.css v8.0.1 | MIT License */html{line-height:1.15;-webkit-text-size-adjust:100%}"
    + "body{margin:0}main{display:block}h1{font-size:2em;margin:.67em 0}hr{box-sizing:content-box;height:0}" * 8
    + "\n"
)


@pytest.mark.parametrize(
    "rel,text",
    [
        # minifier output: a license comment glued to code on one line
        ("static/tinylib.js", MINIFIED_JS),
        ("static/app.css", MINIFIED_CSS),
        # minified with no comment at all
        ("lib/plain.js", MINIFIED_JS.split("*/", 1)[1]),
        # data payload: a table literal on one line (room4doom math/src/og_trig_tables.rs)
        ("math/src/og_trig_tables.rs", "pub static FINESINE: [i32; 300] = [" + ",".join(map(str, range(300))) + "];\n"),
        # data payload inside a comment: no spaces, not prose
        ("src/blob.c", "/* " + "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo" * 20 + " */\nint x;\n"),
        # inline source map
        (
            "src/app.js",
            "var a = 1;\n//# sourceMappingURL=data:application/json;base64," + "eyJ2ZXJzaW9uIjozfQ" * 40 + "\n",
        ),
        # a long preprocessor line is code, not a comment, in C
        ("src/macros.h", "#define TABLE " + " ".join(f"X({i})" for i in range(150)) + "\nint x;\n"),
        # a block comment closed mid-line with code after it
        ("src/tail.c", f"/* {PROSE} */ int a = 1;\n"),
    ],
)
def test_minified_and_payload_lines_stay_blocked(tmp_path, rel, text):
    result = _scan(tmp_path, rel, text)
    assert not result["is_in_scope"]
    assert "Saturation" in result["reason"], result["reason"]


def test_comment_line_beyond_comment_bound_stays_blocked(tmp_path):
    text = "// " + PROSE * 10 + "\nint x;\n"
    assert len(text) > APERTURE_CONFIG["MAX_COMMENT_LINE_LENGTH"]
    result = _scan(tmp_path, "src/huge.c", text)
    assert not result["is_in_scope"]
