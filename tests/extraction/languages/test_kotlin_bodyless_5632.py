"""#5632: a Kotlin declaration with no body (`fun interface` member, interface member,
`abstract fun`, `expect fun`) is a one-line unit. It used to walk on to a LATER unit's
`{` and borrow that body as a runaway extent."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _units(src: str) -> dict:
    st = _PRISM.split_streams(src, "kotlin")
    out = StructuralExtractor("kotlin", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, "kotlin"),
    )
    return {f["name"]: f for f in out["functions"]}


_TAIL = """
fun later(x: Int): Int {
    val a = x + 1
    if (a > 2) {
        return a
    }
    return 0
}
"""


@pytest.mark.parametrize(
    "decl",
    [
        "fun interface DoubleGetter {\n    fun bodyless(i: Int): Double\n}\n\ncompanion object {\n    fun other() { }\n}",
        "interface Shape {\n    fun bodyless(scale: Double): Double\n    fun area(): Double\n}\nobject Holder {\n    fun other() { }\n}",
        "abstract class Base {\n    abstract fun bodyless(x: Int): Int\n}\nobject Holder {\n    fun other() { }\n}",
        "expect fun bodyless(x: Int): Int\n\nobject Holder {\n    fun other() { }\n}",
        "interface Shape {\n    fun bodyless(\n        a: Int,\n        b: Int\n    ): Map<String, List<Int>>\n}\nobject Holder {\n    fun other() { }\n}",
    ],
)
def test_bodyless_declaration_is_not_a_runaway(decl):
    units = _units(decl + "\n" + _TAIL)
    f = units["bodyless"]
    assert f["end_line"] - f["start_line"] <= 4, f
    assert f["end_line"] < units["later"]["start_line"]
    assert units["later"]["end_line"] - units["later"]["start_line"] == 6


def test_bodied_forms_still_extend():
    src = (
        "fun blockBody(x: Int): Int {\n    return x\n}\n"
        "fun exprBody(x: Int): Int =\n    x + 1\n"
        "fun newlineBrace(x: Int): Int\n{\n    return x\n}\n"
        "fun retOnNextLine(x: Int)\n    : Int {\n    return x\n}\n"
        "fun whereClause(x: T)\n    where T : Any {\n    return x\n}\n"
    )
    u = _units(src)
    assert u["blockBody"]["end_line"] - u["blockBody"]["start_line"] == 2
    assert u["exprBody"]["end_line"] >= u["exprBody"]["start_line"] + 1
    assert u["newlineBrace"]["end_line"] - u["newlineBrace"]["start_line"] == 3
    assert u["retOnNextLine"]["end_line"] - u["retOnNextLine"]["start_line"] == 3
    assert u["whereClause"]["end_line"] - u["whereClause"]["start_line"] == 3
