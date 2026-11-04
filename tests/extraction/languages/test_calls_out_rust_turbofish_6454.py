"""
#6454: a rust turbofish call keeps its callee however the generic argument list is written: nested more than two
levels, a `->` in a `Fn` bound, a tuple type, a const-generic block. A turbofish that is not followed by `(` is no call.

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
    code = "fn t(x: E) {\n" + body + "\n}\n"
    functions = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == "t")["calls_out_to"]


@pytest.mark.parametrize(
    "body, callee",
    [
        ("x.collect::<Vec<u8>>()", "collect"),
        ("x.collect::<Vec<Vec<u8>>>()", "collect"),
        ("x.collect::<Vec<Vec<Vec<u8>>>>()", "collect"),
        ("x.collect::<HashMap<String, Vec<Vec<u8>>>>()", "collect"),
        ("x.get::<A<B<C<D<E>>>>>()", "get"),
        ("x.into::<Box<dyn Fn(u8) -> u8>>()", "into"),
        ("x.get::<Vec<(u8, u8)>>()", "get"),
        ("f::<{ N + 1 }>(x)", "f"),
        ("f::<Foo<{ N + 1 }>>(x)", "f"),
        ("x.sum::<Foo<'a, T>>()", "sum"),
        ("x.parse::<[u8; 4]>()", "parse"),
        ("mem::size_of::<Vec<Vec<Vec<u8>>>>()", "size_of"),
        ("run::<Vec<Vec<Vec<u8>>>>\n    (x)", "run"),
    ],
)
def test_turbofish_callee_kept(body, callee):
    assert _callees(body) == [callee]


@pytest.mark.parametrize(
    "body",
    [
        "let n = size::<Vec<Vec<Vec<u8>>>>;",
        "let f = parse::<Box<dyn Fn(u8) -> u8>>;",
        "let ok = a < b && c > d;",
    ],
)
def test_no_call_without_paren(body):
    assert _callees(body) == []


def test_pattern_is_still_no_call():
    assert _callees("match x { Foo(y) => 1, Bar(Baz(z)) | Qux(_) => 2, _ => 3 };") == []


@pytest.mark.parametrize(
    "payload",
    [
        "f::<" + "<" * 50000,
        "f::<" + "A<" * 50000,
        "f::<" + "(" * 50000,
        "f::<" + "{" * 50000,
        "f::<" + "-" * 50000,
        "f::<" + "->" * 50000,
        "f::<A<B<C<D<" + "x" * 100000,
        "f::<" + "<(" * 30000,
    ],
)
def test_turbofish_redos_immunity(payload):
    assert_redos_immune(LANGUAGE_DEFINITIONS["rust"]["rules"]["calls_out"], payload, timeout_sec=3.0)
