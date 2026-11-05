"""
#6454: a match arm's pattern and a closure's parameter patterns name constructors, they call nothing (contract C3).
rust's `_calls_out_rewrite` blanks them; arm bodies, guards, closure bodies and scrutinees keep their calls.

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
        ("match x { Foo(a) => g(a), Bar(B(b), c) => h(), _ => k() }", ["g", "h", "k"]),
        ("match x { (A(a), B(b)) => g(a), }", ["g"]),
        ("match x { Foo(a) | Baz(a) if ok(a) => g(a), }", ["ok", "g"]),
        ("match x {\n  Some(A(a))\n  | Some(B(a)) if ok(a) => g(a),\n}", ["ok", "g"]),
        ("match x { 1..=5 => g(), Wrap(Inner(v)) => h(v), }", ["g", "h"]),
        ("let f = |Foo(a): Foo, b| m(a);", ["m"]),
        ("let f = |(A(a), b)| m(a);", ["m"]),
        ("let f = move |A(a)| m(a);", ["m"]),
        ("xs.map(|Pair(a, B(b))| m(a));", ["map", "m"]),
    ],
)
def test_arm_and_closure_patterns_are_no_call(body, callees):
    assert _callees(body) == callees


@pytest.mark.parametrize(
    "body, callees",
    [
        ("match x { Foo(a) => Bar(a), }", ["Bar"]),
        ("match x { _ => g(a, Foo(1)), Bar(b) => h(), }", ["g", "Foo", "h"]),
        ("match s { U => P::<F, ()>::new().into_iter(), N(f) => f.go(), }", ["new", "into_iter", "go"]),
        ("match s { U => a.span(), V(v) => w(), }", ["span", "w"]),
        ("let r = a || d(1) || e(2);", ["d", "e"]),
        ("g(|| h(1), |x| k(x));", ["g", "h", "k"]),
        ("let f = |x| Foo(x);", ["Foo"]),
        ("let r = a | c(2);", ["c"]),
        ("select! { v = rx.recv() => g(v), }", ["select", "recv", "g"]),
    ],
)
def test_bodies_guards_and_operands_stay(body, callees):
    assert _callees(body) == callees


class _Rewrite:
    """Adapts the rewrite callable to the `.search` shape `assert_redos_immune` drives (picklable)."""

    def __init__(self, fn):
        self.fn = fn

    def search(self, text):
        return self.fn(text)


@pytest.mark.parametrize(
    "payload",
    [
        "{ " * 50000,
        "{," * 50000,
        "{ A(" * 50000,
        "{ A(b)" * 30000,
        "{ A(b(c)) " * 20000,
        ", A(b) | " * 20000,
        "{ " + "a" * 100000,
        "= |" * 50000,
        "(|" + "a" * 100000,
        "move |" * 50000,
        "{ if " * 30000,
    ],
)
def test_rewrite_redos_immunity(payload):
    rewrite = LANGUAGE_DEFINITIONS["rust"]["rules"]["_calls_out_rewrite"]
    assert_redos_immune(_Rewrite(rewrite), payload, timeout_sec=3.0)
