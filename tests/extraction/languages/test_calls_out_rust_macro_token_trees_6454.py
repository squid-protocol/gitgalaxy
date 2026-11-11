"""
#6454 (calls_out contract C3): a pattern written inside a macro's token tree (`assert!(matches!(..))`, a `match` arm
or closure parameter inside `vec!` / `dbg!` / `println!` arguments) names variants, it calls nothing, while an
expression call in the same token tree stays a call. tree-sitter leaves such token trees flat, so these are pinned here.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

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
        ("assert!(matches!(w.get(e), Err(X::NotSpawned(e)) if e.id() == 1));", ["assert", "matches", "get", "id"]),
        ("assert!(matches!(w.get(e), Ok(A(_)) | Err(B(_))));", ["assert", "matches", "get"]),
        ("assert!(matches!(x, Foo(_)) && matches!(y, Bar(_)));", ["assert", "matches"]),
        ("assert!(v.iter().any(|x| matches!(x, &Foo(a) if a == 1)));", ["assert", "iter", "any", "matches"]),
        ("assert!(matches!(x, Foo(1..=3)));", ["assert", "matches"]),
        ("assert!(matches!(x, Foo { a: Bar(_), .. }));", ["assert", "matches"]),
        ("assert!(match x { Foo(_) => true, _ => false });", ["assert"]),
        ("dbg!(match x { Some(Foo(a)) | Some(Bar(a)) => h(a), None => 0 });", ["dbg", "h"]),
        ("assert!(if let Foo(a) = x { true } else { false });", ["assert"]),
        ("assert!(v.iter().any(|&Foo(a)| a == 1));", ["assert", "iter", "any"]),
        ('assert!(matches!(x, Foo(_)), "{:?}", Baz(1));', ["assert", "matches", "Baz"]),
    ],
)
def test_macro_token_tree_patterns(body, callees):
    assert _callees(body) == callees
