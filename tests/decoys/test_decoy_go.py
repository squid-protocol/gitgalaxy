"""SOP-002-v1 gap-cell decoy suite for Go (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)

Covers the six code-stream families that had a rule in go.py but no decoy row in
tests/family_validity_baseline.json: api, encapsulation, listeners, macros, safety_bypasses, scientific.
`macros` has no authentic positive control (its `//go:` pragma arm only matches comment text, which is blanked
before the rule runs, #9429): it keeps a strict xfail and gets no baseline row. Every check runs through the real
Prism.split_streams() + StructuralExtractor.splice() pipeline.

Go comment forms (Go spec, "Comments"): `//` line comments and `/* */` general comments. Block comments do NOT
nest, and backtick raw strings may contain comment-looking text.
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
_EXTRACTOR = StructuralExtractor("go", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
_ISSUES = "https://github.com/squid-protocol/gitgalaxy/issues/"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "go")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


# Authentic Go positive controls (Req C) for the five cells that can fire. `macros` is in the dead-rule test below.
GO_FAMILIES: dict[str, str] = {
    "api": "func ServeHTTP(w http.ResponseWriter, r *http.Request) {",
    "encapsulation": "func helper(x int) int {",
    "listeners": "msgs := make(<-chan string)",
    "safety_bypasses": "_, err = os.Open(name)",
    "scientific": "y := math.Sqrt(x)",
}

# G6: what a string literal holding the keyword does today (strings count by design, #2535). The anchored rules
# (`^func`, `^type`) never see a mid-line string, so they stay 0.
GO_STRING_COUNTS: dict[str, bool] = {
    "api": False,
    "encapsulation": False,
    "listeners": True,
    "safety_bypasses": True,
    "scientific": True,
}


def test_go_gap_cells_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    expected = (defined["go"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(GO_FAMILIES) | {"macros"} <= expected
    assert set(GO_STRING_COUNTS) == set(GO_FAMILIES)


def test_go_baseline_has_sop002_row_for_each_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["go"]
    for family in GO_FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family
    assert "macros" not in rows  # dead rule (#9429): no row until a pragma can fire


@pytest.mark.parametrize(("family", "snippet"), sorted(GO_FAMILIES.items()))
def test_go_positive_control_and_all_spec_comment_forms(family: str, snippet: str):
    # G1
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for go.{family}: {snippet!r}"
    # Req A: every Go comment form
    assert _hits(family, f"// {snippet}\n") == 0, f"// leak for go.{family}"
    assert _hits(family, f"    // {snippet}\n") == 0, f"indented // leak for go.{family}"
    assert _hits(family, f"/* {snippet} */\n") == 0, f"/* */ leak for go.{family}"
    assert _hits(family, f"/*\n{snippet}\n*/\n") == 0, f"multi-line /* */ leak for go.{family}"
    assert _hits(family, f"/*\n * {snippet}\n */\n") == 0, f"starred /* */ leak for go.{family}"
    assert _hits(family, f"/* a // b\n{snippet}\n*/\n") == 0, f"// inside /* */ leak for go.{family}"
    assert _hits(family, f"/*/ {snippet} */\n") == 0, f"/*/ leak for go.{family}"
    base_line = _hits(family, "x := 1 // SENTINEL_NOOP\n")
    assert _hits(family, f"x := 1 // {snippet}\n") <= base_line, f"trailing // leak for go.{family}"
    base_blk = _hits(family, "x := 1 /* SENTINEL_NOOP */\n")
    assert _hits(family, f"x := 1 /* {snippet} */\n") <= base_blk, f"trailing /* */ leak for go.{family}"
    # G6 boundary: a comment marker inside a string literal is not a comment, and the real comment after the string is
    for prefix in ('s := "http://x"', 's := "a \\" b"', "s := `http://x`", "r := '\"'"):
        base = _hits(family, f"{prefix} // SENTINEL_NOOP\n")
        assert _hits(family, f"{prefix} // {snippet}\n") <= base, f"string-comment leak for go.{family}: {prefix}"
        base = _hits(family, f"{prefix} /* SENTINEL_NOOP */\n")
        assert _hits(family, f"{prefix} /* {snippet} */\n") <= base, f"string-block leak for go.{family}: {prefix}"


@pytest.mark.parametrize(("family", "snippet"), sorted(GO_FAMILIES.items()))
def test_go_comment_openers_in_other_forms_do_not_swallow_code(family: str, snippet: str):
    """Go block comments do not nest and a raw string or `//` line cannot open one: the code after them still counts."""
    # `/* a /* b */` ends at the FIRST `*/` (no nesting), so the snippet below is live code; the `*/` after it is stray
    assert _hits(family, f"/* a /* b */\n{snippet}\n") >= 1
    assert _hits(family, f"// /*\n{snippet}\n") >= 1
    assert _hits(family, f"/* // */\n{snippet}\n") >= 1
    assert _hits(family, f"/**/\n{snippet}\n") >= 1
    # a raw string holding `/*` or `//` opens nothing
    assert _hits(family, f"x := `/*`\n{snippet}\n") >= 1
    assert _hits(family, f"x := `//`\n{snippet}\n") >= 1


@pytest.mark.parametrize(("family", "snippet"), sorted(GO_FAMILIES.items()))
def test_go_string_literal_behaviour(family: str, snippet: str):
    """G6: record what a string holding the keyword does (#2535: strings count by design)."""
    quoted = snippet.replace('"', '\\"')
    assert (_hits(family, f's := "{quoted}"\n') >= 1) is GO_STRING_COUNTS[family]


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # extra authentic arms of the rules (every alternation branch can fire)
        ("api", "type Server struct {\n"),
        ("api", "var Debug = false\n"),
        ("api", "const MaxN = 3\n"),
        ("api", "func Serve() {\n"),
        ("api", "func (s *S) Handle() {\n"),
        ("api", "type S struct {\n\tName string\n}\n"),
        ("api", "func handle(c gin.Context) {\n"),
        ("api", "func handle(c echo.Context) {\n"),
        ("encapsulation", "type thing struct {\n"),
        ("encapsulation", "var counter int\n"),
        ("encapsulation", "const maxN = 3\n"),
        ("encapsulation", "func (s *S) helper() {\n"),
        ("listeners", "func f(c <-chan int) {}\n"),
        ("listeners", 'bus.On("e", h)\n'),
        ("listeners", 'bus.Subscribe("t", h)\n'),
        ("safety_bypasses", "_ = x\n"),
        ("safety_bypasses", 'import . "fmt"\n'),
        ("scientific", "y := gonum.Dot(a)\n"),
        ("scientific", "x := a / math.Pi\n"),
    ],
)
def test_go_every_authentic_arm_fires(family: str, src: str):
    assert _hits(family, src) >= 1


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req B: identifier-embedded and prefixed forms of every literal arm
        ("api", "mytype Foo int\n"),
        ("api", "types Foo int\n"),
        ("api", "myfunc Foo()\n"),
        ("api", "func helper(x int) int {\n"),
        ("encapsulation", "myfunc helper()\n"),
        ("encapsulation", "typed thing int\n"),
        ("encapsulation", "funcs x()\n"),
        ("listeners", 'bus.Once("e", h)\n'),
        ("listeners", "bus.Online(x)\n"),
        ("listeners", 'bus.Unsubscribe("t")\n'),
        ("listeners", "bus.OnX(h)\n"),
        ("listeners", "x := <-channel\n"),
        ("listeners", "x := <-chans\n"),
        ("safety_bypasses", 'reimport . "fmt"\n'),
        ("safety_bypasses", "_, myerr = f()\n"),
        ("safety_bypasses", "a_ == b\n"),
        ("scientific", "y := mymath.Sqrt(x)\n"),
        ("scientific", "y := maths.Sqrt(x)\n"),
        ("scientific", "y := math_.Sqrt(x)\n"),
        ("scientific", "y := mygonum.Dot(a)\n"),
        ("scientific", "y := mymath/cmplx.X\n"),
        ("scientific", "y := mymath/rand.X\n"),
        ("scientific", "y := mycrypto/rand.X\n"),
    ],
)
def test_go_all_branch_word_boundaries(family: str, src: str):
    assert _hits(family, src) == 0


@pytest.mark.parametrize(
    ("family", "src"),
    [
        pytest.param(
            "api", "func h(w myhttp.ResponseWriter) {\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9430")
        ),
        pytest.param(
            "api", "func h(w mygin.Context) {\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9430")
        ),
        pytest.param(
            "api", "func h(c myecho.Context) {\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9430")
        ),
        pytest.param(
            "api", "func h(w http.ResponseWriterFoo) {\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9430")
        ),
        pytest.param("safety_bypasses", "my_ = x\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9431")),
        pytest.param(
            "safety_bypasses", "result_, err = f()\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9431")
        ),
    ],
)
def test_go_boundary_leaks_known(family: str, src: str):
    assert _hits(family, src) == 0


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req D: contract negatives written in Go syntax
        # api corollary 1/2: a reference or an unexported name is not an exported declaration
        ("api", "\tx := Foo(1)\n"),
        ("api", "\tfmt.Println(x)\n"),
        ("api", "var counter int\n"),
        ("api", "const maxN = 3\n"),
        ("api", "type thing struct {\n"),
        # encapsulation C4: exported names and function-locals mark no hidden surface
        ("encapsulation", "func Serve() {\n"),
        ("encapsulation", "type Server struct {\n"),
        ("encapsulation", "\tvar helper int\n"),
        ("encapsulation", "func f() {\n\thelper := 1\n}\n"),
        # listeners: a channel send/receive is not a registration
        ("listeners", "v := <-ch\n"),
        ("listeners", "ch <- v\n"),
        # safety_bypasses: handled errors and ok-checks are not bypasses
        ("safety_bypasses", "x, err := f()\n"),
        ("safety_bypasses", "_, err := f()\n"),
        ("safety_bypasses", "_, ok := m[k]\n"),
        ("safety_bypasses", "for _, v := range xs {\n"),
        ("safety_bypasses", "var _ I = (*T)(nil)\n"),
        # scientific: other packages and the bare word are not a math facility
        ("scientific", "y := strings.Contains(s, t)\n"),
        ("scientific", "math := 3\n"),
        ("scientific", "y := Math.Sqrt(x)\n"),
    ],
)
def test_go_cross_family_negative_controls(family: str, src: str):
    assert _hits(family, src) == 0


@pytest.mark.parametrize(
    "src",
    [
        pytest.param(
            "//go:generate stringer -type=Color\n",
            marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9429"),
        ),
        pytest.param(
            "package main\n\n//go:noinline\nfunc add(a, b int) int { return a + b }\n",
            marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9429"),
        ),
    ],
)
def test_go_macros_positive_control_is_dead(src: str):
    """The only authentic `macros` input is a `//go:` pragma comment, which the lexer blanks first."""
    assert _hits("macros", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        pytest.param("y := cmplx.Abs(z)\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9432")),
        pytest.param("n := rand.Intn(10)\n", marks=pytest.mark.xfail(strict=True, reason=_ISSUES + "9432")),
    ],
)
def test_go_scientific_math_cmplx_and_rand_calls(src: str):
    assert _hits("scientific", src) >= 1
