"""#6770: `calls_out_to` reads no call in a statically-dead C-family preprocessor branch -- `#if 0`, the dead side of
`#if 1`, and `#if defined(X)` / `#ifdef X` / `#ifndef X` of a repo-owned toggle that no file of the scan defines."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.core import detector as det
from gitgalaxy.core.preproc_toggles import toggle_condition_value, unset_toggles
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

UNSET = frozenset({"NEVER", "ALSO_NEVER"})


@pytest.mark.parametrize(
    ("condition", "value"),
    [
        ("defined(NEVER)", False),
        ("defined NEVER", False),
        ("!defined(NEVER)", True),
        ("defined(NEVER) && defined(OTHER)", False),
        ("defined(NEVER) || defined(ALSO_NEVER)", False),
        ("defined(NEVER) || defined(OTHER)", None),
        ("!defined(NEVER) || defined(OTHER)", True),
        ("(defined(NEVER)) || (defined(ALSO_NEVER))", False),
        ("NEVER", False),
        ("defined(OTHER)", None),
        ("NEVER > 2", None),
        ("NEVER(1)", None),
        ("defined(NEVER) ? 1 : 0", None),
        ("defined(NEVER", None),
        ("", None),
    ],
)
def test_condition_value_is_three_valued(condition, value):
    assert toggle_condition_value(condition, UNSET) is value


def test_unset_toggles_keeps_only_repo_owned_toggles():
    header = "#ifndef GUARD_H\n#define GUARD_H\n#define SET_HERE 1\n#endif\n"
    source = (
        "// #define COMMENTED_OUT\n"
        "#if defined(COMMENTED_OUT)\nint a;\n#endif\n"
        "#ifdef SET_HERE\nint b;\n#endif\n"
        "#if defined(NAMED_IN_BUILD)\nint c;\n#endif\n"
        "#ifdef PATH_MAX\nchar buf[PATH_MAX];\n#endif\n"
        "#ifdef _WIN32\nint d;\n#endif\n"
        "#if defined(NDEBUG)\nint e;\n#endif\n"
        "#ifndef GUARD_H\nint f;\n#endif\n"
    )
    names = unset_toggles([header, source], ["add_definitions(-DNAMED_IN_BUILD)\n"])
    assert names == {"COMMENTED_OUT"}  # defined, built, code-used, platform and guard names are all undecided


def test_unset_toggles_leaves_system_header_macro_shapes_undecided():
    source = (
        "#ifdef UINT_MAX\nint a;\n#endif\n#ifdef Q_WS_X11\nint b;\n#endif\n#if defined(MY_FEATURE)\nint c;\n#endif\n"
    )
    assert unset_toggles([source], []) == {"MY_FEATURE"}


def test_unset_toggles_is_off_for_an_oversized_scan(monkeypatch):
    from gitgalaxy.core import preproc_toggles

    monkeypatch.setattr(preproc_toggles, "MAX_TEXT_BYTES", 10)
    assert unset_toggles(["#ifdef LONG_TOGGLE_NAME\n#endif\n"], []) == frozenset()


def _blank(code, unset=UNSET, lang="c", mask=True):
    ex = det.StructuralExtractor(lang_id=lang, language_definitions=LANGUAGE_DEFINITIONS)
    return ex._blank_dead_preproc_branches(code, lang, unset, mask_comments=mask)


@pytest.mark.parametrize(
    ("code", "dead", "live"),
    [
        ("#if 0\ndead();\n#endif\nlive();\n", "dead", "live"),
        ("#if 1\nlive();\n#else\ndead();\n#endif\n", "dead", "live"),
        ("#if defined(NEVER)\ndead();\n#else\nlive();\n#endif\n", "dead", "live"),
        ("#ifdef NEVER\ndead();\n#else\nlive();\n#endif\n", "dead", "live"),
        ("#ifndef NEVER\nlive();\n#else\ndead();\n#endif\n", "dead", "live"),
        ("#if !defined(NEVER)\nlive();\n#elif defined(ALSO_NEVER)\ndead();\n#endif\n", "dead", "live"),
        ("#if defined(NEVER)\ndead();\n#elif defined(ALSO_NEVER)\ndead2();\n#else\nlive();\n#endif\n", "dead2", "live"),
        ("#if defined(NEVER)\n#if 1\ndead();\n#endif\n#endif\nlive();\n", "dead", "live"),
    ],
)
def test_dead_branches_are_blanked_in_every_form(code, dead, live):
    out = _blank(code)
    assert dead + "(" not in out and live + "(" in out
    assert len(out) == len(code) and out.count("\n") == code.count("\n")


@pytest.mark.parametrize(
    "code",
    [
        "#if defined(OTHER)\nlive();\n#else\nlive2();\n#endif\n",  # defined somewhere: unknown, both sides kept
        "#ifdef _WIN32\nlive();\n#endif\n",
        "#if NEVER > 1\nlive();\n#endif\n",
        "/*\n#if 0\n*/\nlive();\n",  # a directive-looking line inside a block comment decides nothing
    ],
)
def test_undecidable_conditions_keep_both_sides(code):
    assert _blank(code) == code


def test_without_a_toggle_table_only_the_static_forms_are_dead():
    code = "#if defined(NEVER)\nlive();\n#endif\n#if 0\ndead();\n#endif\n"
    out = _blank(code, unset=frozenset())
    assert "live(" in out and "dead(" not in out


def test_csharp_never_reads_the_toggle_table(monkeypatch):
    monkeypatch.setattr(det, "_C_REPO_UNSET_TOGGLES", UNSET)
    code = "#if NEVER\nlive();\n#endif\n#if 0\ndead();\n#endif\n"
    for lang, expected in (("c", False), ("cs", True)):
        ex = det.StructuralExtractor(lang_id=lang, language_definitions=LANGUAGE_DEFINITIONS)
        out = ex._call_scan_shield(code)
        assert ("live(" in out) is expected and "dead(" not in out, lang


C_SOURCE = """\
#include "net.h"
void live(void) { }
void dead_zero(void) { }
void dead_toggle(void) { }
void dead_ifdef(void) { }
void kept_defined(void) { }
void kept_built(void) { }
void kept_vs(void) { }
void kept_else(void) { }
void run(void)
{
    live();
#if 0 // moved
    dead_zero();
#endif
#if defined(NEVER_TOGGLE)
    dead_toggle();
#endif
#ifdef NEVER_IFDEF
    dead_ifdef();
#endif
#if defined(DEFINED_IN_HEADER)
    kept_defined();
#endif
#if defined(BUILT_BY_CMAKE)
    kept_built();
#endif
#ifdef BUILT_BY_VS
    kept_vs();
#endif
#ifdef NEVER_ELSE
#else
    kept_else();
#endif
}
"""


def test_a_scan_drops_dead_branch_calls_and_keeps_the_rest(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    (src / "run.c").write_text(C_SOURCE)
    (src / "net.h").write_text("#define DEFINED_IN_HEADER 1\n")
    (src / "CMakeLists.txt").write_text("add_definitions(-DBUILT_BY_CMAKE)\n")
    # #6266: the aperture blocks a `.vcxproj` for its extension, but its compiler defines still make a toggle live
    (src / "app.vcxproj").write_text("<PreprocessorDefinitions>NDEBUG;BUILT_BY_VS</PreprocessorDefinitions>\n")
    out = tmp_path / "out"
    env = {
        **os.environ,
        "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER",
        "GITGALAXY_DISABLE_GIT_HISTORY": "1",
        "GALAXYSCOPE_MAX_WORKERS": "1",
    }
    code = "import sys; from gitgalaxy.galaxyscope import main; sys.argv = ['galaxyscope', *sys.argv[1:]]; main()"
    done = subprocess.run(
        [sys.executable, "-c", code, str(src), "--db-only", "--output", str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    dbs = list(out.glob("*.db"))
    assert dbs, done.stderr[-2000:]
    con = sqlite3.connect(dbs[0])
    try:
        calls = {
            c for (blob,) in con.execute("select calls_out_to from function_data") for c in json.loads(blob or "[]")
        }
    finally:
        con.close()
    assert {"live", "kept_defined", "kept_built", "kept_vs", "kept_else"} <= calls
    assert not {"dead_zero", "dead_toggle", "dead_ifdef"} & calls
    assert Path(dbs[0]).exists()
