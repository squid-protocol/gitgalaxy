"""
#6454 (calls_out contract C3): a `select!` arm pattern ends at `=`, not `=>` (`Foo { v: Bar(b) } = fut => ..`,
`(A(a), B(b)) = fut => ..`). It names variants, it calls nothing; the future expression and the arm body keep their calls.

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
        ("select! { Foo { v: Bar(b) } = f() => h(b) }", ["select", "f", "h"]),
        ("select! { (A(a), B(b)) = f() => h(a) }", ["select", "f", "h"]),
        ("select! { Foo(a) = f() => h(a), Bar { v: Baz(c) } = g() => k(c) }", ["select", "f", "h", "g", "k"]),
        ("select! { biased; &Foo(a) = f(), if ok(a) => h(a) }", ["select", "f", "ok", "h"]),
        ("select! { Foo { v: Bar(b) } = f() => 1, else => 0 }", ["select", "f"]),
        ("(A(a), B(b)) = pair();", ["pair"]),
        # lowercase / member / index targets are expressions: their calls stay
        ("*f(x) = 1;", ["f"]),
        ("x.y = g(1);", ["g"]),
        ("v[h(1)] = 2;", ["h"]),
        ("let ok = a == Foo(1);", ["Foo"]),
    ],
)
def test_select_arm_patterns(body, callees):
    assert _callees(body) == callees


def test_long_input_is_bounded():
    body = "select! { " + "Foo { " * 200 + "x" + " }" * 50 + " = f() => 1 }"
    start = time.monotonic()
    _callees(body)
    assert time.monotonic() - start < 5
