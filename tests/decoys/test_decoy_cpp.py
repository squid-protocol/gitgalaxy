"""SOP-002-v1 gap-cell decoy suite for C++ (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers ONLY the three cpp code-stream families that had a rule but no decoy row:
`closures`, `import` and `telemetry`, through the real Prism.split_streams() +
StructuralExtractor.splice() pipeline. Every comment form of ISO C++ is exercised
(`//`, `///`, `//!`, `/* */`, `/** */`, `/*! */`, trailing forms) plus the raw string
literal `R"x(...)x"`. C++ block comments do NOT nest, so a nested `/* a /* b */ S */`
leaves S as code; that is asserted as a positive control, not a decoy.
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
_EXTRACTOR = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"

_ISSUE_SPLICE = "https://github.com/squid-protocol/gitgalaxy/issues/9439"
_ISSUE_ARRAY_BRACE = "https://github.com/squid-protocol/gitgalaxy/issues/9441"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "cpp")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


# The three cpp cells that had no decoy row, each with an authentic positive control (Req C).
CPP_FAMILIES: dict[str, str] = {
    "closures": "auto add = [base](int v) { return base + v; };",
    "import": "#include <vector>",
    "telemetry": 'logger.info("service started");',
}

_FAMILIES = sorted(CPP_FAMILIES)


def test_cpp_gap_families_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    allowed = (defined["cpp"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(CPP_FAMILIES) <= allowed


def test_cpp_baseline_has_a_sop002_row_for_each_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["cpp"]
    for fam in CPP_FAMILIES:
        assert rows[fam]["protocol"] == "SOP-002-v1", fam
        assert rows[fam]["corpus"] == "decoy-spec", fam


@pytest.mark.parametrize("family", _FAMILIES)
def test_cpp_g1_positive_control(family: str):
    assert _hits(family, CPP_FAMILIES[family] + "\n") >= 1


# --- Req A: every comment form of ISO C++ -------------------------------------------------------------------------
# Each template wraps the snippet S. None of these may count S.
_COMMENT_FORMS: list[tuple[str, str]] = [
    ("line", "// {S}\n"),
    ("doc_line_triple_slash", "/// {S}\n"),
    ("doc_line_bang", "//! {S}\n"),
    ("block", "/* {S} */\n"),
    ("doc_block_star", "/** {S} */\n"),
    ("doc_block_bang", "/*! {S} */\n"),
    ("block_multiline", "/*\n{S}\n*/\n"),
    ("doc_block_multiline", "/**\n * @brief x\n * {S}\n */\n"),
    ("inline_trailing_line", "int x; // {S}\n"),
    ("inline_trailing_block", "int x; /* {S} */\n"),
    ("inline_between_tokens", "int x = /* {S} */ 1;\n"),
    # string-then-comment boundary: a comment-like URL inside a literal must not hide or open a comment wrongly
    ("string_then_line", 'const char* u = "http://x"; // {S}\n'),
    ("string_then_block", 'const char* u = "http://x"; /* {S} */\n'),
    ("string_escaped_quote_then_line", 'const char* u = "a \\" b"; // {S}\n'),
    ("char_quote_then_line", "char q = '\"'; // {S}\n"),
    ("raw_string_then_line", 'auto r = R"x(http://y)x"; // {S}\n'),
    ("raw_string_then_block", 'auto r = R"x(http://y)x"; /* {S} */\n'),
]


@pytest.mark.parametrize(("form", "template"), _COMMENT_FORMS, ids=[f for f, _ in _COMMENT_FORMS])
@pytest.mark.parametrize("family", _FAMILIES)
def test_cpp_comment_forms_do_not_count(family: str, form: str, template: str):
    assert _hits(family, template.format(S=CPP_FAMILIES[family])) == 0, f"cpp.{family} leaks in {form}"


@pytest.mark.parametrize("family", _FAMILIES)
@pytest.mark.xfail(strict=True, reason=_ISSUE_SPLICE)
def test_cpp_line_comment_continued_by_backslash_newline(family: str):
    """[lex.phases]/[lex.comment]: a backslash-newline splices lines first, so the next line is still the `//` comment."""
    assert _hits(family, "// note \\\n" + CPP_FAMILIES[family] + "\n") == 0


# Comment markers that are NOT comments in C++: the snippet that follows is code (positive controls for the lexer).
_NOT_A_COMMENT: list[tuple[str, str]] = [
    # C++ block comments do not nest: the first `*/` ends the comment, S is code, the stray `*/` is just text.
    ("block_does_not_nest", "/* a /* b */\n{S}\n*/\n"),
    ("raw_string_with_line_marker", 'auto r = R"x(// )x";\n{S}\n'),
    ("raw_string_with_block_marker", 'auto r = R"x(/* )x";\n{S}\n'),
    ("block_marker_in_ordinary_string", 'const char* s = "/*";\n{S}\n'),
]


@pytest.mark.parametrize(("form", "template"), _NOT_A_COMMENT, ids=[f for f, _ in _NOT_A_COMMENT])
@pytest.mark.parametrize("family", _FAMILIES)
def test_cpp_comment_lookalikes_do_not_hide_code(family: str, form: str, template: str):
    assert _hits(family, template.format(S=CPP_FAMILIES[family])) >= 1, f"cpp.{family} wrongly hidden by {form}"


# --- G6: keyword inside a string literal (#2535: strings count by design, except where the rule is line-anchored) ---
@pytest.mark.parametrize("family", ["closures", "telemetry"])
def test_cpp_string_literal_content_counts_by_design(family: str):
    snippet = CPP_FAMILIES[family].replace('"', "'")
    assert _hits(family, f'const char* s = "{snippet}";\n') >= 1
    assert _hits(family, f'auto r = R"x(\n{CPP_FAMILIES[family]}\n)x";\n') >= 1


def test_cpp_import_is_line_anchored_so_a_quoted_string_does_not_count():
    assert _hits("import", 'const char* s = "#include <vector>";\n') == 0
    assert _hits("import", 'const char* s = "import std.core;";\n') == 0
    # but a raw string whose body puts the text at the start of a line does (recorded, #2535)
    assert _hits("import", 'auto r = R"x(\n#include <vector>\n)x";\n') >= 1


# --- Req B: every literal alternation branch of the rule -----------------------------------------------------------
_IMPORT_BRANCHES: list[tuple[str, str, str]] = [
    # (branch, authentic positive, identifier-prefixed decoy)
    ("#include <>", "#include <vector>", "x #include <vector>"),
    ('#include ""', '#include "util.h"', 'x #include "util.h"'),
    ("import", "import std.core;", "my_import std.core;"),
    ("import (word tail)", "import std.core;", "important std.core;"),
    ("export import", "export import std.core;", "x export import std.core;"),
    ("export import (word head)", "export import std.core;", "myexport import std.core;"),
    ("#include (tail)", "#include <vector>", "#include_next <vector>"),
]


@pytest.mark.parametrize(
    ("branch", "positive", "decoy"), _IMPORT_BRANCHES, ids=[b[0] + str(i) for i, b in enumerate(_IMPORT_BRANCHES)]
)
def test_cpp_import_branch_boundaries(branch: str, positive: str, decoy: str):
    assert _hits("import", positive + "\n") >= 1, f"branch {branch} does not fire on its authentic form"
    assert _hits("import", decoy + "\n") == 0, f"branch {branch} leaks on {decoy!r}"


_TELEMETRY_OBJECTS = ["log", "logger", "LOGGER", "spdlog", "glog", "syslog"]
_TELEMETRY_METHODS = ["info", "error", "warn", "debug", "trace"]


@pytest.mark.parametrize("obj", _TELEMETRY_OBJECTS)
def test_cpp_telemetry_object_branches(obj: str):
    assert _hits("telemetry", f'{obj}.info("x");\n') >= 1
    assert _hits("telemetry", f'my_{obj}.info("x");\n') == 0  # identifier prefix
    assert _hits("telemetry", f'{obj}_x.info("x");\n') == 0  # identifier suffix
    assert _hits("telemetry", f'{obj}.information("x");\n') == 0  # method is a longer word


@pytest.mark.parametrize("method", _TELEMETRY_METHODS)
def test_cpp_telemetry_method_branches(method: str):
    assert _hits("telemetry", f'logger.{method}("x");\n') >= 1
    assert _hits("telemetry", f'logger.my_{method}("x");\n') == 0
    assert _hits("telemetry", f'logger.{method}_x("x");\n') == 0


def test_cpp_closures_has_no_literal_word_branch_so_only_structure_is_audited():
    """closures is the structural `[captures](params) { body }` shape: there is no word alternation to embed."""
    assert _hits("closures", "auto f = []{ return 1; };\n") >= 1
    assert _hits("closures", "auto f = [=]() mutable { return 1; };\n") >= 1
    assert _hits("closures", "auto f = [&](auto&& v) noexcept -> int { return v; };\n") >= 1
    assert _hits("closures", "std::sort(a.begin(), a.end(), [](int l, int r) { return l < r; });\n") >= 1


# --- Req D: contract negatives ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("family", "negative_src"),
    [
        # closures: an anonymous callable only; a named function or method is not one
        ("closures", "void run() { }\n"),
        ("closures", "int Widget::size() const noexcept { return n; }\n"),
        ("closures", "template <class T> void swap(T& a, T& b) { }\n"),
        ("closures", "struct Op { int operator()(int v) const { return v; } };\n"),
        ("closures", "[[nodiscard]] int next() { return 1; }\n"),
        ("closures", "if (table[i]) { use(); }\n"),
        ("closures", "int grid[2][2] = {{1, 2}, {3, 4}};\n"),
        # import: neither a preprocessor line that is not an include, nor a name that merely contains the word
        ("import", "#pragma once\n"),
        ("import", "#define IMPORT_TOKEN 1\n"),
        ("import", "int import = 1;\n"),
        ("import", "using import_t = int;\n"),
        ("import", "export module math.core;\n"),
        # telemetry: a bare print / stream write is debug_prints, and std::log is the math function
        ("telemetry", 'std::cout << "info\\n";\n'),
        ("telemetry", 'std::cerr << "error\\n";\n'),
        ("telemetry", 'printf("started\\n");\n'),
        ("telemetry", "double e = std::log(x);\n"),
        ("telemetry", "double e = log(x) + y;\n"),
    ],
)
def test_cpp_cross_family_negative_controls(family: str, negative_src: str):
    assert _hits(family, negative_src) == 0


# A brace initialiser after an array declarator is not a lambda (precision leak, filed).
@pytest.mark.parametrize(
    "src",
    [
        "int a[] {1, 2, 3};\n",
        "auto* p = new int[3]{1, 2, 3};\n",
        "struct S { int m[2] {}; };\n",
    ],
)
@pytest.mark.xfail(strict=True, reason=_ISSUE_ARRAY_BRACE)
def test_cpp_closures_array_brace_initialiser_is_not_a_lambda(src: str):
    assert _hits("closures", src) == 0
