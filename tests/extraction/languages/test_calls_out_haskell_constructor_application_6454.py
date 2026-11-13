"""
#6454 (calls_out contract C2/C3): a constructor or function head followed by arguments is an application even when
a later `->` on the same line belongs to a lambda, a `case ... of` arm or an `if ... then` branch, not to the
head. A head whose own case-arm arrow follows (`Foo y -> ...`) is still a pattern and binds names.

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
        # a lambda after the application
        ("run x = Foo x $ \\y -> y\n", {"Foo"}),
        ("run x = Foo x >>= \\y -> bar y\n", {"Foo", "bar"}),
        ("run x = Foo \\y -> y\n", {"Foo"}),
        ("run x = [Foo y, \\z -> z]\n", {"Foo"}),
        ("run x = y\n  where y = Foo a $ \\b -> b\n", {"Foo"}),
        ("run x = mk x $ \\y -> y\n", {"mk"}),
        # the scrutinee of a one-line case, before `of`
        ("run x = case Foo y of z -> z\n", {"Foo"}),
        ("run x = case Foo y of Bar z -> z\n", {"Foo"}),
        ("run x = case parseIt y of z -> z\n", {"parseIt"}),
        # a condition before `then`, `else`
        ("run x = if Foo y then \\z -> z else id\n", {"Foo"}),
    ],
)
def test_head_before_a_later_arrow_is_a_call(body, callees):
    assert callees <= _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        # the head's own case-arm arrow: a pattern, not a call
        ("run x = case x of Foo y -> Bar y\n", {"Foo"}),
        ("run x = case x of\n  Foo y -> \\z -> z\n  Nothing -> Bar 1\n", {"Foo", "Nothing"}),
        ("run x = case () of _ | Foo y <- z -> w\n", {"Foo"}),
        ("run x = f (Foo y -> z)\n", {"Foo"}),
        ("run x = Foo x -> y\n", {"Foo"}),
    ],
)
def test_a_case_arm_pattern_is_not_a_call(body, absent):
    assert not absent & _callees(body)


@pytest.mark.parametrize("unit", ["\\a ", "(f x) ", "Foo y "])
def test_a_long_arrowless_line_is_redos_immune(unit):
    pattern = LANGUAGE_DEFINITIONS["haskell"]["rules"]["calls_out"]
    assert_redos_immune(pattern, "run x = Foo " + unit * 400 + "\n")
