"""
#6454: the pattern a `let` / `for` binds names constructors, it calls nothing (contract C3). rust declares a
`_calls_out_rewrite` that blanks the binding pattern; the initialiser and the iterator expression keep their calls.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _callees(body: str) -> list[str]:
    code = "fn t(x: E) -> bool {\n" + body + "\n}\n"
    functions = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == "t")["calls_out_to"]


@pytest.mark.parametrize(
    "body, callees",
    [
        ("let (A(a), b) = baz();", ["baz"]),
        ("let (a, B(b)) = baz();", ["baz"]),
        ("let [A(a), ..] = baz();", ["baz"]),
        ("let ((A(a), B(b)), c) = z();", ["z"]),
        ("let (A(a), B(b)): (A, B) = baz();", ["baz"]),
        ("let Foo(a): Foo = bar();", ["bar"]),
        ("let Foo { a: Bar(b), .. } = z;", []),
        ("if let (A(a), B(b)) = z() {}", ["z"]),
        ("while let Some(A(a)) = it.next() {}", ["next"]),
        ("for Foo(a) in xs {}", []),
        ("for (i, Foo(a)) in xs {}", []),
        ("for Foo(a) in xs.iter() {}", ["iter"]),
        ("let (\n    A(a),\n    b,\n) = baz();", ["baz"]),
    ],
)
def test_binding_pattern_is_no_call(body, callees):
    assert _callees(body) == callees


@pytest.mark.parametrize(
    "body, callees",
    [
        ("let (x, y) = (A(1), B(2));", ["A", "B"]),
        ("let v = build(Foo(1));", ["build", "Foo"]),
        ("let n: usize = len(xs);", ["len"]),
        ("let ok = a == B(1);", ["B"]),
        ("let f = g(x) == H(1);", ["g", "H"]),
        ("let x = if let Some(y) = f() { g(y) } else { h() };", ["f", "g", "h"]),
        ("let r = for_each(x);", ["for_each"]),
        ("let formal = Foo(1);", ["Foo"]),
        ("foo(Bar(1));", ["foo", "Bar"]),
    ],
)
def test_initialiser_and_calls_stay(body, callees):
    assert _callees(body) == callees


def test_impl_for_is_untouched():
    code = "impl Tr for Foo {\n    fn t(&self) -> i32 {\n        build(Bar(1))\n    }\n}\n"
    functions = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert next(f for f in functions if f["name"] == "t")["calls_out_to"] == ["build", "Bar"]


class _Rewrite:
    """Adapts the rewrite callable to the `.search` shape `assert_redos_immune` drives (picklable)."""

    def __init__(self, fn):
        self.fn = fn

    def search(self, text):
        return self.fn(text)


@pytest.mark.parametrize(
    "payload",
    [
        "let " * 50000,
        "let " + "(" * 50000,
        "let " + "A(" * 50000,
        "let " + "a" * 100000,
        "let x" + " {" * 50000,
        "for " * 50000,
        "for " + "a " * 50000,
        "for " + "{a}" * 50000,
        "let " + "{a}" * 50000 + ";",
        "let (A(a), " * 20000,
    ],
)
def test_rewrite_redos_immunity(payload):
    rewrite = LANGUAGE_DEFINITIONS["rust"]["rules"]["_calls_out_rewrite"]
    assert_redos_immune(_Rewrite(rewrite), payload, timeout_sec=3.0)
