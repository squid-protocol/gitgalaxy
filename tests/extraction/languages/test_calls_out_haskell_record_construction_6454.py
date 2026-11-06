"""
#6454 (calls_out contract C2/C3): a Haskell constructor head followed by a record brace is a record construction and
keeps its call (`Foo{..}`, `Foo { a = 1 }`, the brace on the next line). A record pattern (a brace group followed by
`=`, `<-` or `->`), a record update on a lowercase head and a `data` declaration's field list stay non-calls.

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
        ("run x = Foo{..}\n", {"Foo"}),
        ("run x = Foo {..}\n", {"Foo"}),
        ("run x = Foo { a = 1, b = 2 }\n", {"Foo"}),
        ("run x = Foo\n  { a = 1\n  , b = 2\n  }\n", {"Foo"}),
        ("run x = Cfg {\n  a = 1\n}\n", {"Cfg"}),
        ("run x = f (Foo{a=1})\n", {"f", "Foo"}),
        ("run x = Foo\n  { a = g 1\n  }\n", {"Foo", "g"}),
        ("run x = do\n  r <- f $! Bar { a = 1 }\n  pure r\n", {"f", "Bar", "pure"}),
    ],
)
def test_record_construction_heads_are_captured(body, callees):
    assert callees <= _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        ("run Foo{..} = 1\n", {"Foo"}),
        ("run Foo { a = x } = x\n", {"Foo"}),
        ("run x = do\n  Foo{..} <- foo\n  pure a\n", {"Foo"}),
        ("run x = case m of\n  Foo{a = y} -> y\n", {"Foo"}),
        ("run x = r { a = 1 }\n", {"r"}),
        ("data Foo = Foo { a :: Int, b :: Int }\n", {"Foo"}),
    ],
)
def test_record_patterns_updates_and_declarations_are_not_calls(body, absent):
    assert not absent & _callees(body)


def test_record_brace_alternatives_are_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["haskell"]["rules"]["calls_out"]
    assert_redos_immune(pattern, "x = " + "Foo{" * 20000, timeout_sec=3.0)
    assert_redos_immune(pattern, "x = Foo { " + "a = 1, " * 20000 + "}", timeout_sec=3.0)
    assert_redos_immune(pattern, "x = " + "{a} " * 30000, timeout_sec=3.0)
    assert_redos_immune(pattern, "x = " + "Foo {a} " * 20000, timeout_sec=3.0)
