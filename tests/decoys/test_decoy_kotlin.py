"""SOP-002-v1 gap-cell decoy suite for Kotlin (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1).
Covers only the code-stream families that had a rule in kotlin.py but no decoy row
in tests/family_validity_baseline.json: api, explicit_casts, immutability_locks, listeners.
Kotlin block comments NEST (kotlinlang grammar), so the nested form is tested against the spec: it leaks today (#9423, xfail strict).
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

_LANG = "kotlin"
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
    "api": "public class Foo",
    "explicit_casts": "val c = obj as Customer",
    "immutability_locks": "const val MAX = 10",
    "listeners": "button.setOnClickListener { }",
}

# Kotlin comment forms (Kotlin grammar): `//`, `/* */`, KDoc `/** */`, multi-line, KDoc with leading stars.
COMMENT_FORMS: dict[str, str] = {
    "line": "// {s}\n",
    "block": "/* {s} */\n",
    "kdoc": "/** {s} */\n",
    "multiline_block": "/*\n{s}\n*/\n",
    "kdoc_stars": "/**\n * {s}\n */\n",
}

STRING_LEADS = [
    'val u = "http://x"',
    'val u = "a \\" b"',
    'val u = """http://x"""',
    'val u = "${x}http://x"',
]

# G6: a keyword inside a string literal counts for every one of these families today (#2535).
STRING_COUNTS: dict[str, bool] = {
    "api": True,
    "explicit_casts": True,
    "immutability_locks": True,
    "listeners": True,
}

BOUNDARY_DECOYS: list[tuple[str, str]] = (
    [
        ("api", d)
        for d in (
            "mypublic class Foo\n",
            "public_class Foo\n",
            "publicclass Foo\n",
            "internal_fun x()\n",
            "public classy Foo\n",
            "public valid\n",
            "public variable\n",
            "public objects\n",
            "public funny\n",
            "@MyRestController\n",
            "@RestControllerAdvice\n",
            "@MyController\n",
            "@Controllers\n",
            "@MyService\n",
            "@Services\n",
            "@MyComponent\n",
            "@Components\n",
            "@MyRequestMapping\n",
            "@RequestMappings\n",
            "@MyGetMapping\n",
            "@GetMappings\n",
            "@MyPostMapping\n",
            "@PostMappings\n",
            "@MyRoute\n",
            "@Routes\n",
        )
    ]
    + [
        ("explicit_casts", d)
        for d in (
            "val c = has Customer\n",
            "val c = myas Customer\n",
            "val c = obj as customer\n",
            "x.myToInt()\n",
            "x.toIntOrNull()\n",
            "x.toLongs()\n",
            "x.toStringx()\n",
            "x.toBooleanx()\n",
            "x.toDoubled()\n",
            "x.toFloats()\n",
            "x.toShorts()\n",
            "x.toBytes()\n",
            "x.toUIntx()\n",
            "x.toULongx()\n",
            "x.toUShortx()\n",
            "x.toUBytex()\n",
            "val toInt = 1\n",
        )
    ]
    + [
        ("immutability_locks", d)
        for d in (
            "myconst val X = 1\n",
            "const_val X = 1\n",
            "constval X = 1\n",
            "const valid = 1\n",
            "const value = 1\n",
        )
    ]
    + [
        ("listeners", d)
        for d in (
            "x.recollect { }\n",
            "x.mycollect { }\n",
            "x.collectAsList()\n",
            "x.myObserve { }\n",
            "x.mysubscribe { }\n",
            "x.once { }\n",
            "x.myonClick { }\n",
            "x.setOnClick { }\n",
            "x.mysetOnClickListener { }\n",
            "x.setOnClickListeners { }\n",
            "x.subscribed { }\n",
            "x.observer { }\n",
            "x.collect\n",
            "collect { }\n",
            "val onClick = 1\n",
            "fun onClick() {}\n",
            "fun subscribe(x: Int) {}\n",
        )
    ]
)

NEGATIVES: list = [
    # non-public visibilities and plain declarations are not the api surface
    ("api", "private class Foo\n"),
    ("api", "private fun x() {}\n"),
    ("api", "class Foo\n"),
    ("api", "fun main() {}\n"),
    # type tests are not casts
    ("explicit_casts", "if (x is Customer) go()\n"),
    ("explicit_casts", "when (x) { is Foo -> 1 }\n"),
    # #2772 C1: `val` / `var` / `lateinit` are ordinary bindings, not locks
    ("immutability_locks", "val X = 1\n"),
    ("immutability_locks", "private val X = 1\n"),
    ("immutability_locks", "var x = 1\n"),
    ("immutability_locks", "lateinit var x: Foo\n"),
    # a declaration named like a listener registration is not a registration call
    ("listeners", "fun subscribe(x: Int) {}\n"),
    # #9425: an import alias is not a cast
    pytest.param("explicit_casts", "import a.b.Bar as Baz\n", marks=_xfail(9425)),
    # #9426: Result.onSuccess runs at once, it registers nothing
    pytest.param("listeners", "result.onSuccess { }\n", marks=_xfail(9426)),
]


@pytest.mark.parametrize(
    ("family", "src"),
    [
        ("api", "public class Foo"),
        ("api", "internal class Foo"),
        ("api", "public open class Foo"),
        ("api", "public interface Foo"),
        ("api", "public object Foo"),
        ("api", "public fun run() {}"),
        ("api", "public val x = 1"),
        ("api", "public var x = 1"),
        ("api", "public typealias Id = Int"),
        ("api", "public suspend fun run() {}"),
        ("api", "@RestController"),
        ("api", "@Controller"),
        ("api", "@Service"),
        ("api", "@Component"),
        ("api", "@RequestMapping"),
        ("api", "@GetMapping"),
        ("api", "@PostMapping"),
        ("api", "@Route"),
        ("explicit_casts", "val c = obj as Customer"),
        ("explicit_casts", "val c = obj as? Customer"),
        ("explicit_casts", "val n = x.toInt()"),
        ("explicit_casts", "val n = x.toLong()"),
        ("explicit_casts", "val n = x.toString()"),
        ("explicit_casts", "val n = x.toUInt()"),
        ("immutability_locks", "const val MAX = 10"),
        ("immutability_locks", "private const val MAX = 10"),
        ("listeners", "flow.collect { }"),
        ("listeners", "data.observe(owner) { }"),
        ("listeners", "bus.subscribe { }"),
        ("listeners", "button.onClick { }"),
        ("listeners", "button.setOnClickListener { }"),
        ("listeners", "button.setOnClickListener(l)"),
    ],
)
def test_kotlin_every_branch_fires(family: str, src: str):
    assert _hits(family, src + "\n") >= 1


@pytest.mark.parametrize("family", sorted(FAMILIES), ids=sorted(FAMILIES))
def test_kotlin_code_after_a_closed_block_comment_counts(family: str):
    """Control: once the real (outermost) closer has been seen, the next line is code again (passes)."""
    snippet = FAMILIES[family]
    assert _hits(family, f"/* a /* b */ c */\n{snippet}\n") >= 1


@pytest.mark.parametrize(
    "family",
    [pytest.param(f, marks=_xfail(9423)) for f in sorted(FAMILIES)],
    ids=sorted(FAMILIES),
)
def test_kotlin_nested_block_comment_hides_the_snippet(family: str):
    """Kotlin block comments NEST (kotlinlang grammar): `/* a /* b */ ... */` stays one comment to the last closer.

    Today kotlin is a flat `standard_block` family, so the first `*/` closes the comment and the
    commented snippet leaks (#9423). Both the single-line and the multi-line nested forms leak.
    """
    snippet = FAMILIES[family]
    assert _hits(family, f"/* a /* b */\n{snippet}\n*/\n") == 0
    assert _hits(family, f"/* a /* b */ {snippet} */\n") == 0


def test_kotlin_covers_the_gap_cell_families():
    families, _, defined = fvc.engine_grid()
    keys = {f.key for f in families} - fdr.NON_DECOY_FAMILIES
    assert set(FAMILIES) <= (defined[_LANG] & keys)


def test_kotlin_baseline_has_sop002_rows():
    path = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
    rows = json.loads(path.read_text())["decoys"][_LANG]
    for family in FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family
        assert rows[family]["keyword"] == FAMILIES[family], family


@pytest.mark.parametrize(("family", "snippet"), sorted(FAMILIES.items()))
def test_kotlin_positive_control_and_comment_forms(family: str, snippet: str):
    # G1: the authentic snippet fires.
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for kotlin.{family}: {snippet!r}"
    # G2 (Req A): every comment form of the spec hides it.
    for name, form in COMMENT_FORMS.items():
        assert _hits(family, form.format(s=snippet)) == 0, f"G2 {name} comment leak for kotlin.{family}"
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
def test_kotlin_string_literal_behaviour(family: str, snippet: str):
    """G6: today a keyword inside a string literal counts for the families whose rule is not line-anchored (#2535)."""
    counted = _hits(family, f'x = "{snippet}";\n') >= 1
    assert counted is STRING_COUNTS[family]


@pytest.mark.parametrize(("family", "decoy"), BOUNDARY_DECOYS)
def test_kotlin_all_branch_word_boundaries(family: str, decoy: str):
    """Req B: every alternation branch with an identifier prefix / suffix or a non-matching shape gives 0 hits."""
    assert _hits(family, decoy) == 0, f"kotlin.{family} leaks on {decoy!r}"


def test_kotlin_scraped_branch_boundaries():
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
    assert leaks == [], f"kotlin scraped-branch boundary leaks: {leaks}"


@pytest.mark.parametrize(("family", "negative_src"), NEGATIVES)
def test_kotlin_negative_controls(family: str, negative_src: str):
    """Req D: constructs the family contract says must not count."""
    assert _hits(family, negative_src) == 0
