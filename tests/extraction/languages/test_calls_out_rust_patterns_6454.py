"""
#6454: the pattern operand of a `matches!`-style macro (`matches!(x, Foo(_) | Bar(..))`) names variants, it calls
nothing (contract C3). `CALLS_OUT_RUST` cannot tell the last alternative (followed by the macro's `)`) from an
expression call, so rust declares `_calls_out_masked_blocks` with a named `mask` group that detector.py blanks.
The macro name, a guard's calls and an expression-position constructor stay calls.

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
    "body",
    [
        "matches!(x, Foo(_))",
        "matches!(x.kind, Kind::A(_) | Kind::B(..) | C(..))",
        "matches!(x, Kind::B { n: Some(_) })",
        "matches!(x, Foo(Bar(1)))",
        "matches!(x, [Foo(_), ..])",
        "matches!(&x, &Foo(_))",
        "assert_matches!(x, Foo(_));",
        "debug_assert_matches!(x, Foo(_) | Bar(_));",
        "assert!(matches!(x, Foo(_)));",
        "matches!(\n        x,\n        Foo(_)\n            | Bar(_)\n    )",
        "matches!(get(x), Foo(_))",
        "matches!(w.get(e).map(|_| {}), Err(X::NotSpawned(e)) if e.entity() == e1)",
        "assert!(matches!(\n        w.get([e1, e2]).map(|_| {}),\n        Err(X::NotSpawned(e)) if ok(e)));",
        "assert!(matches!(w.get(&vec![e1, e2][..]).map(|_| {}), Foo(_),));",
        "assert!(matches!(w.get(&[e1] /* an array, not a slice */).m(), Foo(_)));",
        "assert_matches!(f(g(x)), Foo(_) | Bar(_));",
        "debug_assert_matches!(f(x), Foo(_));",
    ],
)
def test_pattern_operand_is_no_call(body):
    callees = _callees(body)
    assert callees[0] in {"matches", "assert_matches", "debug_assert_matches", "assert"}
    assert not {"Foo", "Bar", "C", "Some", "A", "B"} & set(callees)


@pytest.mark.parametrize(
    "body, callees",
    [
        ("matches!(x, Foo(y) if check(y))", ["matches", "check"]),
        ("let d = foo(Some(3));", ["foo", "Some"]),
        ("matches!(x, Foo(_)); build(Bar(1));", ["matches", "build", "Bar"]),
        ("rematches!(x, Foo(_));", ["rematches", "Foo"]),
        ("matches!(get(x), Qux(_))", ["matches", "get"]),
        ("matches!(w.get([a, b]).map(|_| {}), Qux(_) if ok(1))", ["matches", "get", "map", "ok"]),
        ("assert!(matches!(f(g(x)), Foo(_)));", ["assert", "matches", "f", "g"]),
    ],
)
def test_real_calls_stay(body, callees):
    assert _callees(body) == callees


def test_other_masks_keep_whole_match_blanking():
    for lang in ("cobol", "pli", "haskell"):
        assert "mask" not in LANGUAGE_DEFINITIONS[lang]["rules"]["_calls_out_masked_blocks"].groupindex


@pytest.mark.parametrize(
    "payload",
    [
        "matches!(x," + "A(" * 50000,
        "matches!(x," + "a" * 100000,
        "matches!(" + "a" * 100000,
        "matches!(x, " + "(" * 50000 + ")" * 50000,
        "matches!(x, A(" + "B(" * 50000,
        "matches!(x, " + "if " * 50000,
        "matches!(" + "(" * 50000,
        "matches!(" + "[" * 50000,
        "matches!(" + "{" * 50000,
        "matches!(" + "f(" * 50000,
        "matches!(" + "f([{" * 20000 + ",",
        "matches!(" + "(a)" * 50000,
    ],
)
def test_mask_redos_immunity(payload):
    mask = LANGUAGE_DEFINITIONS["rust"]["rules"]["_calls_out_masked_blocks"]
    assert_redos_immune(mask, payload, timeout_sec=3.0)
