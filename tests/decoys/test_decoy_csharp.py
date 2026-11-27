"""SOP-002-v1 gap-cell decoy suite for C# (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1).
Covers only the code-stream families that had a rule in csharp.py but no decoy row
in tests/family_validity_baseline.json: auth_middleware, comprehensions, explicit_casts, import.
Nested block comments are NOT part of C# (ECMA-334): the first `*/` closes the comment, so the nested test asserts the code after it counts.
Every check runs through the real Prism.split_streams() + StructuralExtractor.splice()
pipeline. Known engine leaks are locked as xfail(strict=True) with their issue.
"""

from __future__ import annotations

import json
import re
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

_LANG = "csharp"
_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor(_LANG, LANGUAGE_DEFINITIONS)


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, _LANG)
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


def _xfail(issue: int):
    return pytest.mark.xfail(strict=True, reason=f"https://github.com/squid-protocol/gitgalaxy/issues/{issue}")


# One authentic positive control per gap-cell family (Req C).
FAMILIES: dict[str, str] = {
    "auth_middleware": "app.UseAuthentication();",
    "comprehensions": "var r = items.Where(x => x > 1);",
    "explicit_casts": "var c = obj as Customer;",
    "import": "using System.Linq;",
}

# C# comment forms (ECMA-334 s6.3.3): `//`, XML doc `///`, delimited `/* */`, delimited doc `/** */`, multi-line.
COMMENT_FORMS: dict[str, str] = {
    "line": "// {s}\n",
    "xml_doc": "/// {s}\n",
    "xml_doc_summary": "/// <summary>\n/// {s}\n/// </summary>\n",
    "block": "/* {s} */\n",
    "doc_block": "/** {s} */\n",
    "multiline_block": "/*\n{s}\n*/\n",
}

STRING_LEADS = ['var u = "http://x";', 'var u = "a \\" b";', 'var u = @"http://x";', 'var u = $"{x}http://x";']

# G6: the string-literal keyword counts for every family whose rule is not line-anchored (`import` is).
STRING_COUNTS: dict[str, bool] = {
    "auth_middleware": True,
    "comprehensions": True,
    "explicit_casts": True,
    "import": False,
}

BOUNDARY_DECOYS: list[tuple[str, str]] = (
    [
        ("auth_middleware", d)
        for d in (
            "[MyAuthorize]\n",
            "[AuthorizeFoo]\n",
            "app.MyUseAuthentication();\n",
            "my_UseAuthentication();\n",
            "x.MyUseAuthorization();\n",
            "x.MySignInAsync(u);\n",
            "x.MySignOutAsync();\n",
            "x.MyCheckPasswordAsync(u, p);\n",
            "x.MyVerifyHashedPassword(u, h, p);\n",
            "x.MyIsInRole(r);\n",
            "my_IsInRole(r);\n",
        )
    ]
    + [
        ("comprehensions", d)
        for d in (
            "x.MySelect(f);\n",
            "x.Selectx(f);\n",
            "x.MyWhere(f);\n",
            "x.MyOrderBy(f);\n",
            "x.MyGroupBy(f);\n",
            "x.MyAggregate(f);\n",
            "x.MyAny(f);\n",
            "x.MyAll(f);\n",
            "x.MyToList();\n",
            "x.ToListX();\n",
            "x.MyToArray();\n",
            "x.MySelectMany(f);\n",
            "Select(f);\n",
            "myfrom x in xs\n",
            "var xfrom = 1;\n",
            "foreach (var x in xs) {\n",
        )
    ]
    + [
        ("explicit_casts", d)
        for d in (
            "var c = has Customer;\n",
            "var c = myas Customer;\n",
            "var c = obj as customer;\n",
        )
    ]
    + [
        ("import", d)
        for d in (
            "xusing System;\n",
            "myusing System;\n",
            "usings System;\n",
            "using_System;\n",
            "global_using System;\n",
            "using staticx System.Math;\n",
            "x.using System;\n",
        )
    ]
)

NEGATIVES: list = [
    # a definition named like an auth call is not a call site
    ("auth_middleware", "public Task SignInAsync(User u) {\n"),
    ("auth_middleware", "void UseAuthentication() {}\n"),
    # an authorization opt-out is not an auth gate
    ("auth_middleware", "[AllowAnonymous]\n"),
    # a foreach loop is not a query expression
    ("comprehensions", "foreach (var x in xs) {\n"),
    # type tests and generic constraints are not casts
    ("explicit_casts", "if (obj is Customer) go();\n"),
    ("explicit_casts", "if (obj is Customer c) go();\n"),
    ("explicit_casts", "where T : Customer\n"),
    ("explicit_casts", "using Alias = A.B;\n"),
    # #2875 contract C1: a using statement / declaration is a scope, not an import
    ("import", "using (var x = new Foo()) {\n"),
    ("import", "using var f = File.Open(p);\n"),
    # #9424: a parenthesised capitalised condition is not a cast
    pytest.param("explicit_casts", "if (IsReady) Run();\n", marks=_xfail(9424)),
    pytest.param("explicit_casts", "if (DEBUG) Log();\n", marks=_xfail(9424)),
]


@pytest.mark.parametrize(
    "src",
    [
        "using System.Linq;",
        "global using System.Linq;",
        "using static System.Math;",
        "using Alias = System.Collections.Generic.List<int>;",
    ],
)
def test_csharp_import_directive_forms_fire(src: str):
    assert _hits("import", src + "\n") >= 1


@pytest.mark.parametrize(
    ("family", "src"),
    [
        ("auth_middleware", "[Authorize]"),
        ("auth_middleware", '[Authorize(Roles = "Admin")]'),
        ("auth_middleware", "app.UseAuthorization();"),
        ("auth_middleware", "await s.SignInAsync(u);"),
        ("auth_middleware", "await s.SignOutAsync();"),
        ("auth_middleware", "await m.CheckPasswordAsync(u, p);"),
        ("auth_middleware", "h.VerifyHashedPassword(u, hash, p);"),
        ("auth_middleware", "if (user.IsInRole(r)) go();"),
        ("comprehensions", "var a = xs.Select(x => x);"),
        ("comprehensions", "var a = xs.ToList();"),
        ("comprehensions", "var a = xs.OrderBy(x => x);"),
        ("comprehensions", "var a = xs.GroupBy(x => x);"),
        ("comprehensions", "var a = xs.SelectMany(x => x);"),
        ("explicit_casts", "var n = (int)x;"),
        ("explicit_casts", "var n = (Customer) obj;"),
    ],
)
def test_csharp_every_branch_fires(family: str, src: str):
    assert _hits(family, src + "\n") >= 1


def test_csharp_nested_block_comment_does_not_nest():
    """C# block comments do NOT nest: the first `*/` closes, so the code after it is real code and counts (passes)."""
    for family, snippet in FAMILIES.items():
        assert _hits(family, f"/* a /* b */\n{snippet}\n*/\n") >= 1, family


def test_csharp_covers_the_gap_cell_families():
    families, _, defined = fvc.engine_grid()
    keys = {f.key for f in families} - fdr.NON_DECOY_FAMILIES
    assert set(FAMILIES) <= (defined[_LANG] & keys)


def test_csharp_baseline_has_sop002_rows():
    path = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
    rows = json.loads(path.read_text())["decoys"][_LANG]
    for family in FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family
        assert rows[family]["keyword"] == FAMILIES[family], family


@pytest.mark.parametrize(("family", "snippet"), sorted(FAMILIES.items()))
def test_csharp_positive_control_and_comment_forms(family: str, snippet: str):
    # G1: the authentic snippet fires.
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for csharp.{family}: {snippet!r}"
    # G2 (Req A): every comment form of the spec hides it.
    for name, form in COMMENT_FORMS.items():
        assert _hits(family, form.format(s=snippet)) == 0, f"G2 {name} comment leak for csharp.{family}"
    # G4: inline trailing comments add nothing over a sentinel baseline.
    base_sl = _hits(family, "int x = 1; // SENTINEL_NOOP\n")
    assert _hits(family, f"int x = 1; // {snippet}\n") <= base_sl, "inline // leak"
    base_blk = _hits(family, "int x = 1; /* SENTINEL_NOOP */\n")
    assert _hits(family, f"int x = 1; /* {snippet} */\n") <= base_blk, "inline /* */ leak"
    # G6b: a comment-like URL in a string must not swallow or leak the comment after it.
    for lead in STRING_LEADS:
        base = _hits(family, lead + " // SENTINEL_NOOP\n")
        assert _hits(family, f"{lead} // {snippet}\n") <= base, f"G6b string-comment leak ({lead})"


@pytest.mark.parametrize(("family", "snippet"), sorted(FAMILIES.items()))
def test_csharp_string_literal_behaviour(family: str, snippet: str):
    """G6: today a keyword inside a string literal counts for the families whose rule is not line-anchored (#2535)."""
    counted = _hits(family, f'x = "{snippet}";\n') >= 1
    assert counted is STRING_COUNTS[family]


@pytest.mark.parametrize(("family", "decoy"), BOUNDARY_DECOYS)
def test_csharp_all_branch_word_boundaries(family: str, decoy: str):
    """Req B: every alternation branch with an identifier prefix / suffix or a non-matching shape gives 0 hits."""
    assert _hits(family, decoy) == 0, f"csharp.{family} leaks on {decoy!r}"


def test_csharp_scraped_branch_boundaries():
    """Req B: scraped literal branches of each rule, embedded in a longer identifier, give 0 hits."""
    rules = LANGUAGE_DEFINITIONS[_LANG]["rules"]
    leaks: list[tuple[str, str, str]] = []
    for fam in sorted(FAMILIES):
        for cand in fdr.scrape_candidates(rules[fam].pattern, fam):
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{1,40}$", cand):
                continue
            bare_ctx = next((c for c in (cand, f"{cand}(x)") if _hits(fam, c + "\n") > 0), None)
            if bare_ctx is None:
                continue
            decoy = f"my_{cand}(x)\n" if "(x)" in bare_ctx else f"my_{cand}_val\n"
            if _hits(fam, decoy) > 0:
                leaks.append((fam, cand, decoy.strip()))
    assert leaks == [], f"csharp scraped-branch boundary leaks: {leaks}"


@pytest.mark.parametrize(("family", "negative_src"), NEGATIVES)
def test_csharp_negative_controls(family: str, negative_src: str):
    """Req D: constructs the family contract says must not count."""
    assert _hits(family, negative_src) == 0
