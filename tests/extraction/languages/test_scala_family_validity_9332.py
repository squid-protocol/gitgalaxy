"""Scala keyword-family validity (#9332, part of #8863): `closures` and `bitwise_ops` count only their own construct.

`closures` counted every `=>` (a `case` match arm, a function-type arrow) and `_` in a pattern; `bitwise_ops` counted `|` in a
pattern alternative, a `stripMargin` bar and text such as `[a|b]`.
"""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_RULES = LANGUAGE_DEFINITIONS["scala"]["rules"]


def _count(rule: str, src: str) -> int:
    return len(_RULES[rule].findall(src))


@pytest.mark.parametrize(
    "src",
    [
        "val f = (x: Int) => x + 1",
        "xs.map(x => x * 2)",
        "xs.foreach { x =>\n  println(x)\n}",
        "xs.map(_.name)",
        "xs.map(_ + 1)",
        "f(_, 2)",
        "xs.collect { case Some(v) => v }",
        "val g = () => 42",
    ],
)
def test_closures_counts_an_anonymous_function(src):
    assert _count("closures", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "x match {\n  case Some(v) => v\n  case None => 0\n}",
        "  case NonFatal(_) => null",
        "  case _ =>\n    fail()",
        "def foreach(record: Map[String, Any])(f: Any => Unit): Unit = ()",
        "  callback: ((Errors, Guard)) => Unit,",
        "  isStray: Log => Boolean): Log = {",
        "type Handler = Int => Unit",
    ],
)
def test_closures_ignores_match_arms_and_function_types(src):
    assert _count("closures", src) == 0


@pytest.mark.parametrize(
    "src",
    [
        "val b = bytes(i) & 0xF",
        "val hi = (n >> 8) & 0xFF",
        "val m = a ^ b",
        "val s = a << 2",
        "val c = ~mask",
        "val o = flags | other",
        "  case x if x == A | x == B => 1",
    ],
)
def test_bitwise_counts_an_operator_between_values(src):
    assert _count("bitwise_ops", src) >= 1


@pytest.mark.parametrize(
    "src",
    [
        "  case Errors.A | Errors.B =>\n    fail()",
        "  case Errors.A |\n       Errors.B =>",
        "  case e @ (_: IllegalStateException | _: IOException) =>",
        '      |          05  A PIC X\n      |""".stripMargin',
        's" buffer [actual|requested]: [$a|$b]"',
        "val ok = a && b || c",
        "p ~ q",
    ],
)
def test_bitwise_ignores_patterns_text_and_combinators(src):
    assert _count("bitwise_ops", src) == 0
