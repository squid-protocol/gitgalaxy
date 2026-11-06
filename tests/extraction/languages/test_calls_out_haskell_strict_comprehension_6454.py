"""
#6454 (calls_out contract C2/C3): a Haskell application head keeps its call after the strict-apply operators
(`f $! Bar 1`, `g <$!> Foo 1`) and inside a list comprehension (`[Foo 1 | y <- ys]`, where the `<-` after the `|`
is a generator, not the bind that would make `Foo 1` a pattern). Bind patterns, pattern guards and bang patterns
stay non-calls.

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


def _callees(body: str) -> set[str]:
    code = "run :: Int -> Int\n" + body
    funcs = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    out: set[str] = set()
    for f in funcs:
        out.update(f["calls_out_to"])
    return out


@pytest.mark.parametrize(
    "body, callees",
    [
        ("run x = f $! Bar 1\n", {"f", "Bar"}),
        ("run x = f $! g 1\n", {"f", "g"}),
        ("run x = g <$!> Foo 1\n", {"Foo"}),
        ("run x = [Foo 1 | y <- ys]\n", {"Foo"}),
        ("run x = [bar y | y <- ys]\n", {"bar"}),
        ("run x = [Foo y 1 | y <- ys, odd y]\n", {"Foo"}),
        ("run x = do\n  r <- f $! Baz 2\n  pure r\n", {"f", "Baz", "pure"}),
    ],
)
def test_heads_after_strict_apply_and_in_comprehensions_are_captured(body, callees):
    assert callees <= _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        ("run x = do\n  Just y <- foo\n  pure y\n", {"Just"}),
        ("run x = do\n  Foo a b <- foo\n  pure a\n", {"Foo"}),
        ("run x = case m of\n  Foo a | Just b <- g a -> 1\n", {"Foo", "Just"}),
        ("run x = go !acc 1\n", {"acc"}),
    ],
)
def test_bind_patterns_guards_and_bang_patterns_are_not_calls(body, absent):
    assert not absent & _callees(body)


def test_strict_apply_and_comprehension_alternatives_are_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["haskell"]["rules"]["calls_out"]
    assert_redos_immune(pattern, "x = f $! " + "Foo " * 30000, timeout_sec=3.0)
    assert_redos_immune(pattern, "x = [" + "Foo 1 | " * 20000 + "y <- ys]", timeout_sec=3.0)
    assert_redos_immune(pattern, "x = " + "$! " * 50000, timeout_sec=3.0)
