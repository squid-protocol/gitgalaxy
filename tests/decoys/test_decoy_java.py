"""SOP-002-v1 gap-cell decoy suite for Java (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1).
Covers only the code-stream families that had a rule in java.py but no decoy row
in tests/family_validity_baseline.json: api, explicit_casts, import.
Nested block comments are NOT part of Java (JLS 3.7): the first `*/` closes the comment, so the nested test asserts the code after it counts.
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

_LANG = "java"
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
    "api": "public class Foo {",
    "explicit_casts": "int n = (int) value;",
    "import": "import java.util.List;",
}

# Java comment forms (JLS s3.7): `//`, `/* */`, Javadoc `/** */`, multi-line, Javadoc with leading stars.
COMMENT_FORMS: dict[str, str] = {
    "line": "// {s}\n",
    "block": "/* {s} */\n",
    "javadoc": "/** {s} */\n",
    "multiline_block": "/*\n{s}\n*/\n",
    "javadoc_stars": "/**\n * {s}\n */\n",
}

STRING_LEADS = ['String u = "http://x";', 'String u = "a \\" b";', 'String u = """\n http://x\n """;']

# G6: the string-literal keyword counts for every family whose rule is not line-anchored (`import` is).
STRING_COUNTS: dict[str, bool] = {"api": True, "explicit_casts": True, "import": False}

BOUNDARY_DECOYS: list[tuple[str, str]] = (
    [
        ("api", d)
        for d in (
            "mypublic class Foo {\n",
            "public_class Foo {\n",
            "publicclass Foo {\n",
            "myprotected void run() {\n",
            "protected_x void run() {\n",
            "public_static void run() {\n",
            "public;\n",
        )
    ]
    + [
        ("explicit_casts", d)
        for d in (
            "if (flag) return;\n",
            "(foo) bar\n",
            "(x + y) z\n",
            "System.out.println(MAX);\n",
        )
    ]
    + [
        ("import", d)
        for d in (
            "important java.util.X;\n",
            "my_import java.util.List;\n",
            "x import java.util.List;\n",
            "import_ java.util.List;\n",
            "importstatic java.util.List;\n",
        )
    ]
)

NEGATIVES: list = [
    # non-public access levels are not the api surface
    ("api", "private class Foo {\n"),
    ("api", "class Foo {\n"),
    ("api", "private void run() {\n"),
    ("api", "void run() {\n"),
    ("api", "private static final int X = 1;\n"),
    # instanceof is a type test, not a cast
    ("explicit_casts", "if (obj instanceof Customer) go();\n"),
    ("explicit_casts", "if (obj instanceof Customer c) go();\n"),
    # an unterminated import and a string holding one are not imports
    ("import", "import java.util.List\n"),
    ("import", 'String s = "import java.util.List;";\n'),
    # #9424: a parenthesised capitalised condition is not a cast
    pytest.param("explicit_casts", "if (DEBUG) log(x);\n", marks=_xfail(9424)),
    pytest.param("explicit_casts", "while (RUNNING) tick();\n", marks=_xfail(9424)),
    pytest.param("explicit_casts", "if (Ready) go();\n", marks=_xfail(9424)),
]


@pytest.mark.parametrize(
    ("family", "src"),
    [
        ("api", "public class Foo {"),
        ("api", "public interface Foo {"),
        ("api", "public enum Foo {"),
        ("api", "public record Foo(int a) {"),
        ("api", "public @interface Foo {"),
        ("api", "public void run() {"),
        ("api", "protected static void run() {"),
        ("api", "public static final int X = 1;"),
        ("api", "public <T> List<T> make() {"),
        ("api", "public final String name;"),
        ("explicit_casts", "int n = (int) value;"),
        ("explicit_casts", "Customer c = (Customer) obj;"),
        ("explicit_casts", "double d = (double) n;"),
        ("import", "import java.util.List;"),
        ("import", "import static java.util.List.of;"),
    ],
)
def test_java_every_branch_fires(family: str, src: str):
    assert _hits(family, src + "\n") >= 1


def test_java_nested_block_comment_does_not_nest():
    """Java block comments do NOT nest (JLS 3.7): the first `*/` closes, so the code after it is real code and counts (passes)."""
    for family, snippet in FAMILIES.items():
        assert _hits(family, f"/* a /* b */\n{snippet}\n*/\n") >= 1, family


def test_java_covers_the_gap_cell_families():
    families, _, defined = fvc.engine_grid()
    keys = {f.key for f in families} - fdr.NON_DECOY_FAMILIES
    assert set(FAMILIES) <= (defined[_LANG] & keys)


def test_java_baseline_has_sop002_rows():
    path = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
    rows = json.loads(path.read_text())["decoys"][_LANG]
    for family in FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family
        assert rows[family]["keyword"] == FAMILIES[family], family


@pytest.mark.parametrize(("family", "snippet"), sorted(FAMILIES.items()))
def test_java_positive_control_and_comment_forms(family: str, snippet: str):
    # G1: the authentic snippet fires.
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for java.{family}: {snippet!r}"
    # G2 (Req A): every comment form of the spec hides it.
    for name, form in COMMENT_FORMS.items():
        assert _hits(family, form.format(s=snippet)) == 0, f"G2 {name} comment leak for java.{family}"
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
def test_java_string_literal_behaviour(family: str, snippet: str):
    """G6: today a keyword inside a string literal counts for the families whose rule is not line-anchored (#2535)."""
    counted = _hits(family, f'x = "{snippet}";\n') >= 1
    assert counted is STRING_COUNTS[family]


@pytest.mark.parametrize(("family", "decoy"), BOUNDARY_DECOYS)
def test_java_all_branch_word_boundaries(family: str, decoy: str):
    """Req B: every alternation branch with an identifier prefix / suffix or a non-matching shape gives 0 hits."""
    assert _hits(family, decoy) == 0, f"java.{family} leaks on {decoy!r}"


def test_java_scraped_branch_boundaries():
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
    assert leaks == [], f"java scraped-branch boundary leaks: {leaks}"


@pytest.mark.parametrize(("family", "negative_src"), NEGATIVES)
def test_java_negative_controls(family: str, negative_src: str):
    """Req D: constructs the family contract says must not count."""
    assert _hits(family, negative_src) == 0
