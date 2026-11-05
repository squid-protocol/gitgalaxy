"""
#6454: a struct-pattern match arm (`Foo { v: Bar(b) } =>`) and a fn's parameter patterns bind names, they call nothing
(contract C3). rust's `_calls_out_rewrite` blanks them; arm bodies, guards and fn bodies keep their calls.

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


def _callees_of(code: str, name: str = "t") -> list[str]:
    functions = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == name)["calls_out_to"]


def _body(body: str) -> list[str]:
    return _callees_of("fn t(x: E) -> bool {\n" + body + "\n}\n")


@pytest.mark.parametrize(
    "body, callees",
    [
        ("match x { Foo { v: Bar(b), .. } => g(b), _ => h() }", ["g", "h"]),
        ("match x { Foo { v: Bar { w: Qux(q) } } => g(q), }", ["g"]),
        ("match x { Foo { v: Bar(b) } | Baz { v: Bar(b) } => g(b), }", ["g"]),
        ("match x { Foo { v: Bar(b) } if ok(b) => g(b), }", ["ok", "g"]),
        ("match x { Q::Foo { v: Some(B(b)), .. } => g(b), }", ["g"]),
    ],
)
def test_struct_arm_patterns_are_no_call(body, callees):
    assert _body(body) == callees


@pytest.mark.parametrize(
    "code, callees",
    [
        ("fn t(Foo(a): Foo, (A(b), c): (A, i32)) -> i32 {\n real(a)\n}\n", ["real"]),
        ("fn t<T: Into<String>>(Wrap(a): Wrap<T>) { real(a) }\n", ["real"]),
        ("fn t(f: impl Fn(A) -> B, Pair(a, B(b)): P) { real(a) }\n", ["real"]),
        ("fn t(&self, Wrapper(inner): Wrapper) { real(inner) }\n", ["real"]),
        ("fn t() { real() }\n", ["real"]),
        ("pub async fn t(\n    Json(p): Json<P>,\n    State(s): State<S>,\n) -> R {\n real(p, s)\n}\n", ["real"]),
    ],
)
def test_fn_parameter_patterns_are_no_call(code, callees):
    assert _callees_of(code) == callees


@pytest.mark.parametrize(
    "body, callees",
    [
        ("match x { _ => Foo { v: g(1) }, }", ["g"]),
        ("match x { A => W { a: rd(d, 0) }, B => k(), }", ["rd", "k"]),
        ("let w = W { a: rd(d, 0) };", ["rd"]),
        ("let f: fn(Foo) -> Bar = h; f(Foo(1));", ["f", "Foo"]),
        ("match x { Foo { v } => Bar(v), }", ["Bar"]),
        # an `else { .. }` block followed by an `if` statement is no struct pattern (room4doom, 5 call-graph misses)
        ("if a { b(); } else { if c() { d = e(); } f.g(); }\nif h { k(); }", ["b", "c", "e", "g", "k"]),
        ("if a { b(); } else { c() }\nif h { k(); }", ["b", "c", "k"]),
    ],
)
def test_bodies_literals_and_fn_pointer_types_stay(body, callees):
    assert _body(body) == callees


class _Rewrite:
    """Adapts the rewrite callable to the `.search` shape `assert_redos_immune` drives (picklable)."""

    def __init__(self, fn):
        self.fn = fn

    def search(self, text):
        return self.fn(text)


@pytest.mark.parametrize(
    "payload",
    [
        "{ " + "A { b: " * 30000,
        "{ A { b: C(d) }" * 20000,
        "{ A {" + "x" * 100000,
        "fn f(" * 50000,
        "fn f(" + "(" * 50000,
        "fn f<" * 50000,
        "fn f<" + "<" * 50000,
        "fn f(" + "a(b)" * 30000,
        "fn f" + "a" * 100000,
    ],
)
def test_rewrite_redos_immunity(payload):
    rewrite = LANGUAGE_DEFINITIONS["rust"]["rules"]["_calls_out_rewrite"]
    assert_redos_immune(_Rewrite(rewrite), payload, timeout_sec=3.0)
