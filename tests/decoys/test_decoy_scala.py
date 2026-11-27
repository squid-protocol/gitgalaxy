"""SOP-002-v1 gap-cell decoy suite for Scala (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers ONLY the one scala code-stream family that had a rule but no decoy row: `explicit_casts`
(`asInstanceOf[T]` and the numeric conversions `.toInt/.toLong/.toFloat/.toDouble/.toByte/.toShort`),
through the real Prism.split_streams() + StructuralExtractor.splice() pipeline. Scala comment forms
(`//`, `/* */`, scaladoc `/** */`) include NESTED block comments, which the Scala spec allows to any depth.
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
_EXTRACTOR = StructuralExtractor("scala", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "scala")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


SCALA_FAMILIES: dict[str, str] = {
    "explicit_casts": "val count = raw.toInt",
}
# The second rule alternative (a checked downcast), kept as its own authentic positive control.
_DOWNCAST = "val name = value.asInstanceOf[String]"
_SNIPPETS = {"toInt": SCALA_FAMILIES["explicit_casts"], "asInstanceOf": _DOWNCAST}


def test_scala_gap_families_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    allowed = (defined["scala"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(SCALA_FAMILIES) <= allowed


def test_scala_baseline_has_a_sop002_row_for_each_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["scala"]
    for fam in SCALA_FAMILIES:
        assert rows[fam]["protocol"] == "SOP-002-v1", fam
        assert rows[fam]["corpus"] == "decoy-spec", fam


@pytest.mark.parametrize("branch", sorted(_SNIPPETS))
def test_scala_g1_positive_control(branch: str):
    assert _hits("explicit_casts", _SNIPPETS[branch] + "\n") >= 1


# --- Req A: every Scala comment form, including nesting ---------------------------------------------------------
_COMMENT_FORMS: list[tuple[str, str]] = [
    ("line", "// {S}\n"),
    ("line_triple_slash", "/// {S}\n"),
    ("block", "/* {S} */\n"),
    ("scaladoc", "/** {S} */\n"),
    ("block_multiline", "/*\n{S}\n*/\n"),
    ("scaladoc_multiline_tag", "/**\n * Converts a value.\n * @param raw {S}\n */\n"),
    # NESTED block comments (Scala spec 1.5: comments nest to any depth)
    ("nested_depth2_inline", "/* outer /* inner */ {S} */\n"),
    ("nested_depth2_multiline", "/* outer\n/* inner\n*/\n{S}\n*/\n"),
    ("nested_depth3", "/* a /* b /* c */ {S} */ still */\n"),
    ("nested_scaladoc", "/** doc /* inner */ {S} */\n"),
    ("nested_multiline_after_inner", "/*\n/* inner */\n{S}\n*/\n"),
    ("inline_trailing_line", "val x = 1 // {S}\n"),
    ("inline_trailing_block", "val x = 1 /* {S} */\n"),
    ("inline_between_tokens", "val x = /* {S} */ 1\n"),
    ("string_then_line", 'val u = "http://x" // {S}\n'),
    ("string_then_block", 'val u = "http://x" /* {S} */\n'),
    ("string_escaped_quote_then_line", 'val u = "a \\" b" // {S}\n'),
    ("triple_quote_then_line", 'val u = """http://x""" // {S}\n'),
    ("char_slash_then_line", "val c = '/' // {S}\n"),
    ("block_marker_after_slash_char", "val c = '/'; /* {S} */\n"),
]


@pytest.mark.parametrize(("form", "template"), _COMMENT_FORMS, ids=[f for f, _ in _COMMENT_FORMS])
@pytest.mark.parametrize("branch", sorted(_SNIPPETS))
def test_scala_comment_forms_do_not_count(branch: str, form: str, template: str):
    assert _hits("explicit_casts", template.format(S=_SNIPPETS[branch])) == 0, f"scala.explicit_casts leaks in {form}"


# Look-alikes that are NOT comments: the snippet is code (positive controls for the lexer).
_NOT_A_COMMENT: list[tuple[str, str]] = [
    ("code_after_closed_nested_comment", "/* a /* b */ c */ {S}\n"),
    ("block_marker_inside_line_comment", "// /* \n{S}\n"),
    ("line_marker_inside_block_comment", "/* // */\n{S}\n"),
    ("quote_inside_block_comment", '/* " */ {S}\n'),
    ("block_marker_in_string", 'val s = "/*"; {S}\n'),
]


@pytest.mark.parametrize(("form", "template"), _NOT_A_COMMENT, ids=[f for f, _ in _NOT_A_COMMENT])
@pytest.mark.parametrize("branch", sorted(_SNIPPETS))
def test_scala_comment_lookalikes_do_not_hide_code(branch: str, form: str, template: str):
    assert _hits("explicit_casts", template.format(S=_SNIPPETS[branch])) >= 1, f"hidden by {form}"


# --- G6: a cast written inside a string literal counts today (#2535); recorded, not endorsed -------------------
def test_scala_string_literal_content_counts_by_design():
    for snippet in _SNIPPETS.values():
        assert _hits("explicit_casts", f'val s = "{snippet}"\n') >= 1
        assert _hits("explicit_casts", f'val s = """\n{snippet}\n"""\n') >= 1
    assert _hits("explicit_casts", 'val s = s"${raw.toInt}"\n') >= 1


# --- Req B: every literal alternation branch ------------------------------------------------------------------------
_NUMERIC_CONVERSIONS = ["toInt", "toLong", "toFloat", "toDouble", "toByte", "toShort"]


@pytest.mark.parametrize("fn", _NUMERIC_CONVERSIONS)
def test_scala_numeric_conversion_branches(fn: str):
    assert _hits("explicit_casts", f"val v = raw.{fn}\n") >= 1
    assert _hits("explicit_casts", f"val v = raw.my_{fn}\n") == 0  # identifier prefix after the dot
    assert _hits("explicit_casts", f"val v = raw{fn}\n") == 0  # no dot: a plain identifier
    assert _hits("explicit_casts", f"val v = raw.{fn}Option\n") == 0  # longer member name
    assert _hits("explicit_casts", f"val v = raw.{fn}_x\n") == 0


def test_scala_as_instance_of_branch():
    assert _hits("explicit_casts", "val v = raw.asInstanceOf[Int]\n") >= 1
    assert _hits("explicit_casts", "val v = raw.asInstanceOf[Map[String, List[Int]]]\n") >= 1
    assert _hits("explicit_casts", "val v = my_asInstanceOf[Int]\n") == 0
    assert _hits("explicit_casts", "val v = raw.my_asInstanceOf[Int]\n") == 0
    assert _hits("explicit_casts", "val v = asInstanceOfX[Int]\n") == 0
    assert _hits("explicit_casts", "val v = raw.asInstanceOf\n") == 0  # no type argument: not a cast site


# --- Req D: contract negatives ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "negative_src",
    [
        "val ok = value.isInstanceOf[String]\n",  # a type test is not a conversion
        "val s = value.toString\n",
        "val s = value.toString()\n",
        "val xs = value.toList\n",
        "val m = pairs.toSeq.toMap\n",
        "val n = raw.toIntOption\n",
        "val n = Integer.parseInt(raw)\n",  # a library parse call, not the cast form
        "val n: Int = 3\n",  # a type ascription
        "val r = value match { case i: Int => i; case _ => 0 }\n",  # a typed pattern is a match, not a cast
        "val big = BigInt(5)\n",
    ],
)
def test_scala_cross_family_negative_controls(negative_src: str):
    assert _hits("explicit_casts", negative_src) == 0
