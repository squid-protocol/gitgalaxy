"""
#6454 (calls_out contract C3): the pattern operand of `matches!` / `assert_matches!` names variants, it calls nothing, however
deeply the first operand nests or however long it is. The guard and the other arguments keep their calls.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import time

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _callees(body: str) -> list[str]:
    code = "fn t(x: E) -> bool {\n" + body + "\n}\n"
    functions = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == "t")["calls_out_to"]


@pytest.mark.parametrize(
    "body, callees",
    [
        ("assert!(matches!(x.f(g(h(i(j(1))))), Bar(_)));", ["assert", "matches", "f", "g", "h", "i", "j"]),
        ("assert!(matches!(x.f(g(h(i(j(k(1)))))), Bar(_)));", ["assert", "matches", "f", "g", "h", "i", "j", "k"]),
        (
            "assert!(matches!(x.f(g(h(i(j(1))))), Bar(_) if k(Baz(1))));",
            ["assert", "matches", "f", "g", "h", "i", "j", "k", "Baz"],
        ),
        ('assert!(matches!(x.f("a, )"), Foo(_)));', ["assert", "matches", "f"]),
        ("assert!(matches!(x.f(','), Foo(_)));", ["assert", "matches", "f"]),
        ('assert!(matches!(x, Foo(_)), "m", Bar(1));', ["assert", "matches", "Bar"]),
        ("assert!(matches!(x.f(g(h(i(j(1))))), Foo(_) | Bar(_),));", ["assert", "matches", "f", "g", "h", "i", "j"]),
        ("assert_matches!(x.f(g(h(i(j(1))))), Foo(a) if a > 1);", ["assert_matches", "f", "g", "h", "i", "j"]),
    ],
)
def test_matches_pattern_operand_is_no_call(body, callees):
    assert _callees(body) == callees


def test_unbalanced_matches_does_not_crash():
    assert "matches" in _callees("assert!(matches!(x, Foo(_)")


def test_unclosed_matches_run_is_linear():
    start = time.perf_counter()
    _callees("assert!(" + "matches!(x, " * 20000)
    assert time.perf_counter() - start < 5


def test_long_operand_is_linear():
    operand = "x" + ".f(1)" * 400
    start = time.perf_counter()
    callees = _callees("assert!(matches!(" + operand + ", Bar(_)));")
    assert "Bar" not in callees
    assert time.perf_counter() - start < 5
