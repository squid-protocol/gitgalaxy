"""SOP-002-v1 gap-cell decoy suite for C (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)

Covers the three code-stream families that had a rule in c.py but no decoy row in
tests/family_validity_baseline.json: explicit_casts, globals, import. Every check runs through the real
Prism.split_streams() + StructuralExtractor.splice() pipeline.

C comment forms (C11 6.4.9, plus translation phases 1-4): `//` line comments, `/* */` block comments (no nesting),
and a backslash-newline is spliced BEFORE comments are recognised, so a `//` comment ending in `\\` also comments the
next line (#9434, a leak, strict xfail). Preprocessor lines (`#include`, `#define`, `#if 0`) are not comments to the
lexer; the engine blanks statically-dead `#if 0` / `#if 1 ... #else` branches before the rules run
(signal_contracts.py, gitgalaxy#2814), pinned below.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import family_decoy_runner as fdr
import family_validity_chart as fvc

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor("c", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
_ISSUES = "https://github.com/squid-protocol/gitgalaxy/issues/"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "c")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


C_FAMILIES: dict[str, str] = {
    "explicit_casts": "int n = (int) x;",
    "globals": "static int counter = 0;",
    "import": "#include <stdio.h>",
}

# G6: strings holding the keyword. The anchored rules (`^static`, `^#include`) never see a mid-line string; the cast
# text does count inside a string (#2535, by design).
C_STRING_COUNTS: dict[str, bool] = {"explicit_casts": True, "globals": False, "import": False}

# An indented, non-global prefix: a column-0 `int z = 1;` would itself be a `globals` hit.
_NOISE = "    z = 1;"


def test_c_gap_cells_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    expected = (defined["c"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(C_FAMILIES) <= expected
    assert set(C_STRING_COUNTS) == set(C_FAMILIES)


def test_c_baseline_has_sop002_row_for_each_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["c"]
    for family in C_FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family


@pytest.mark.parametrize(("family", "snippet"), sorted(C_FAMILIES.items()))
def test_c_positive_control_and_all_spec_comment_forms(family: str, snippet: str):
    # G1
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for c.{family}: {snippet!r}"
    # Req A: `//` and `/* */`
    assert _hits(family, f"// {snippet}\n") == 0, f"// leak for c.{family}"
    assert _hits(family, f"    // {snippet}\n") == 0, f"indented // leak for c.{family}"
    assert _hits(family, f"/* {snippet} */\n") == 0, f"/* */ leak for c.{family}"
    assert _hits(family, f"/*\n{snippet}\n*/\n") == 0, f"multi-line /* */ leak for c.{family}"
    assert _hits(family, f"/*\n * {snippet}\n */\n") == 0, f"starred /* */ leak for c.{family}"
    assert _hits(family, f"/* a // b\n{snippet}\n*/\n") == 0, f"// inside /* */ leak for c.{family}"
    assert _hits(family, f"/*/ {snippet} */\n") == 0, f"/*/ leak for c.{family}"
    # `// ... \` ends at the newline when the backslash is not last, and a `//` comment then a live line stays live
    assert _hits(family, f"// note \\ x\n{snippet}\n") >= 1, f"non-final backslash swallowed code for c.{family}"
    # inline trailing forms (delta over a sentinel)
    base = _hits(family, f"{_NOISE} // SENTINEL_NOOP\n")
    assert _hits(family, f"{_NOISE} // {snippet}\n") <= base, f"trailing // leak for c.{family}"
    base = _hits(family, f"{_NOISE} /* SENTINEL_NOOP */\n")
    assert _hits(family, f"{_NOISE} /* {snippet} */\n") <= base, f"trailing /* */ leak for c.{family}"
    # `#define` carrying a comment is still a directive, and its comment is still a comment
    assert _hits(family, f"#define X 1 /* {snippet} */\n") == 0, f"#define trailing comment leak for c.{family}"
    # G6 boundary: comment markers inside string and char literals
    for prefix in ('    s = "http://x";', '    s = "a \\" b";', "    q = '\"';", "    q = '\\'';"):
        base = _hits(family, f"{prefix} // SENTINEL_NOOP\n")
        assert _hits(family, f"{prefix} // {snippet}\n") <= base, f"string-comment leak for c.{family}: {prefix}"
        base = _hits(family, f"{prefix} /* SENTINEL_NOOP */\n")
        assert _hits(family, f"{prefix} /* {snippet} */\n") <= base, f"string-block leak for c.{family}: {prefix}"


@pytest.mark.parametrize(("family", "snippet"), sorted(C_FAMILIES.items()))
def test_c_comment_openers_in_other_forms_do_not_swallow_code(family: str, snippet: str):
    """C block comments do not nest, a `//` line cannot open one, and string/char literals open nothing."""
    assert _hits(family, f"/* a /* b */\n{snippet}\n") >= 1  # ends at the FIRST `*/`
    assert _hits(family, f"// /*\n{snippet}\n") >= 1
    assert _hits(family, f"/* // */\n{snippet}\n") >= 1
    assert _hits(family, f"/**/\n{snippet}\n") >= 1
    assert _hits(family, f'    s = "/*";\n{snippet}\n') >= 1
    assert _hits(family, f"    q = '\"';\n{snippet}\n") >= 1


@pytest.mark.parametrize(
    "family",
    [
        pytest.param(f, marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9434"))
        for f in ("explicit_casts", "globals", "import")
    ],
)
def test_c_line_continuation_extends_a_line_comment(family: str):
    """C11 5.1.1.2 phase 2: backslash-newline is spliced before comments, so `// x \\` comments the next line too."""
    assert _hits(family, f"// first \\\n{C_FAMILIES[family]}\n") == 0
    assert _hits(family, f"// first \\\n   {C_FAMILIES[family]}\n// done\n") == 0


@pytest.mark.parametrize(("family", "snippet"), sorted(C_FAMILIES.items()))
def test_c_preprocessor_conditionals(family: str, snippet: str):
    """Pinned engine behaviour: `#if 0` is not a comment to the lexer, but statically dead branches are blanked (#2814).

    `#ifdef X` / `#if FOO` (unknown condition) keep both branches live.
    """
    assert _hits(family, f"#if 0\n{snippet}\n#endif\n") == 0
    assert _hits(family, f"#if 0\n{snippet}\n#else\n#endif\n") == 0
    assert _hits(family, f"#if 0\n#else\n{snippet}\n#endif\n") >= 1
    assert _hits(family, f"#if 1\n{snippet}\n#endif\n") >= 1
    assert _hits(family, f"#if 1\n#else\n{snippet}\n#endif\n") == 0
    assert _hits(family, f"#ifdef FOO\n{snippet}\n#endif\n") >= 1
    assert _hits(family, f"#if defined(FOO)\n#else\n{snippet}\n#endif\n") >= 1


@pytest.mark.parametrize(("family", "snippet"), sorted(C_FAMILIES.items()))
def test_c_string_literal_behaviour(family: str, snippet: str):
    """G6: record what a string holding the keyword does (#2535: strings count by design)."""
    quoted = snippet.replace('"', '\\"')
    assert (_hits(family, f'    s = "{quoted}";\n') >= 1) is C_STRING_COUNTS[family]


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # every literal arm can fire
        *[(("explicit_casts"), f"x = ({t}) y;\n") for t in ("int", "float", "double", "char", "bool", "long", "short")],
        ("explicit_casts", "x = (unsigned) y;\n"),
        ("explicit_casts", "x = (signed) y;\n"),
        ("explicit_casts", "(void) y;\n"),
        ("explicit_casts", "p = (char *) q;\n"),
        ("explicit_casts", "p = (int * *) q;\n"),
        ("globals", "int counter;\n"),
        ("globals", "extern int counter;\n"),
        ("globals", 'const char *name = "x";\n'),
        ("globals", "volatile int flag;\n"),
        ("globals", "_Thread_local int tl;\n"),
        ("globals", "static _Atomic int a;\n"),
        ("globals", "struct node *head = NULL;\n"),
        ("globals", "int table[10];\n"),
        ("globals", "void f(void) {\n    static int n = 0;\n}\n"),
        ("globals", "void f(void) {\n    _Thread_local int n;\n}\n"),
        ("import", '#include "local.h"\n'),
        ("import", "# include <stdio.h>\n"),
        ("import", "  #  include <stdio.h>\n"),
        ("import", '#embed "data.bin"\n'),
        ("import", "/* c */ #include <x.h>\n"),
        ("import", "#include <a.h> // trailing\n"),
    ],
)
def test_c_every_authentic_arm_fires(family: str, src: str):
    assert _hits(family, src) >= 1


_CAST_TYPES = ("int", "float", "double", "char", "bool", "long", "short", "unsigned", "signed", "void")


@pytest.mark.parametrize("kw", _CAST_TYPES)
def test_c_explicit_casts_type_arm_word_boundaries(kw: str):
    """Req B: every type arm embedded in a longer identifier (prefix, suffix, both) is a typedef name, not a cast."""
    for decoy in (f"my_{kw}", f"{kw}_t", f"{kw}s", f"x{kw}"):
        assert _hits("explicit_casts", f"n = ({decoy}) y;\n") == 0, decoy


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req B: globals modifier arms embedded in identifiers, indented (the indented arm is the static-only one)
        ("globals", "void f(void) {\n    my_static int x = 0;\n}\n"),
        ("globals", "void f(void) {\n    mystatic int x = 0;\n}\n"),
        ("globals", "void f(void) {\n    static_x y = 1;\n}\n"),
        ("globals", "void f(void) {\n    static_value = 3;\n}\n"),
        ("globals", "void f(void) {\n    _Thread_local_x y = 1;\n}\n"),
        ("globals", "mystatic int counter = 0;\n"),
        # Req B: include/embed arms embedded in directive names
        ("import", "#myinclude <stdio.h>\n"),
        ("import", "#my_include <a.h>\n"),
        ("import", "#includes <stdio.h>\n"),
        ("import", "#include_x <stdio.h>\n"),
        ("import", '#embedded "x"\n'),
        ("import", '#my_embed "x"\n'),
    ],
)
def test_c_all_branch_word_boundaries(family: str, src: str):
    assert _hits(family, src) == 0


@pytest.mark.parametrize(
    "src",
    [
        pytest.param(
            "void abort(void) __attribute__((noreturn));\n",
            marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9433"),
        ),
        pytest.param("extern int f(void) __THROW;\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9433")),
    ],
)
def test_c_explicit_casts_prototype_with_trailing_attribute(src: str):
    assert _hits("explicit_casts", src) == 0


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req D: contract negatives written in C syntax
        # explicit_casts: a prototype / definition header / sizeof is not a conversion
        ("explicit_casts", "void f(void);\n"),
        ("explicit_casts", "int main(void) {\n"),
        ("explicit_casts", "int main(void)\n{\n"),
        ("explicit_casts", "n = sizeof(int);\n"),
        ("explicit_casts", "n = sizeof(int)*4;\n"),
        ("explicit_casts", "void (*cb)(int);\n"),
        # globals corollary 1/C1: a function-local, an indented declaration and a prototype are not globals
        ("globals", "int main(void) {\n    int x = 1;\n    return x;\n}\n"),
        ("globals", "    int x = 1;\n"),
        ("globals", "    extern int x;\n"),
        ("globals", "static void f(void);\n"),
        ("globals", "extern void f(int x);\n"),
        ("globals", "void f(void) {\n    static int g(void);\n}\n"),
        ("globals", 'void f(void) {\n    static_assert(sizeof(int) == 4, "m");\n}\n'),
        # import: other directives, computed includes and the text inside a string/error are not an include
        ("import", "#define INCLUDE_H <x.h>\n"),
        ("import", "#pragma once\n"),
        ("import", "#ifndef FOO_H\n"),
        ("import", "#import <Foo.h>\n"),
        ("import", "#include MACRO\n"),
        ("import", '#error "#include <x.h>"\n'),
        ("import", 'const char *s = "#include <x.h>";\n'),
        # a GNU `#include_next` is a different directive name: not counted today (documented)
        ("import", "#include_next <stdio.h>\n"),
    ],
)
def test_c_cross_family_negative_controls(family: str, src: str):
    assert _hits(family, src) == 0
