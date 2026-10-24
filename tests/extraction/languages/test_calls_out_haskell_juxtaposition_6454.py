"""
#6454 (calls_out contract C2/C3, docs/calls_out_rule_contract.md): Haskell calls have no parentheses, so the
rule recognises juxtaposition application (`f x y`, `f (g x)`) and constructor application (`Just x`) by the
head's position (after an operator, bracket, `do`/`then`/`case`, or at the start of a body line) and an
argument-start token after it. A type signature is masked, `return`/`try`/`catch`/`finally` are ordinary
functions, and a pattern line (`Left e -> ...`, `f (Foo a) = ...`) binds names rather than calling.

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
        ("run x = foo bar baz\n", {"foo"}),
        ("run x = do\n  r <- toArchive bs\n  return (go r)\n", {"toArchive", "return", "go"}),
        ("run x = Just x\n", {"Just"}),
        ("run x = Left (Err x)\n", {"Left", "Err"}),
        ("run x = case parseIt x of\n  Left e -> Nothing\n  Right v -> Just v\n", {"parseIt", "Just"}),
    ],
)
def test_application_heads_are_captured(body, callees):
    assert callees <= _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        ("run x = if x then y else z\n", {"then", "else", "y", "z"}),
        ("run a b = a `div` b\n", {"a", "div"}),
        ("run x = case parseIt x of\n  Left e -> Nothing\n", {"Left", "e"}),
    ],
)
def test_keywords_operands_and_patterns_are_not_calls(body, absent):
    assert not absent & _callees(body)


def test_signature_continuation_lines_are_masked():
    code = "run :: Maybe Int\n  -> Either String Int\n  -> IO ()\nrun a b = pure ()\n"
    funcs = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    out = {c for f in funcs for c in f["calls_out_to"]}
    assert not {"Maybe", "Either", "IO"} & out


def test_rule_shape_is_two_groups():
    pattern = LANGUAGE_DEFINITIONS["haskell"]["rules"]["calls_out"]
    assert pattern.groups == 2


def test_juxtaposition_alternative_is_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["haskell"]["rules"]["calls_out"]
    assert_redos_immune(pattern, "x = f " + "a " * 50000, timeout_sec=3.0)
    assert_redos_immune(pattern, "x = " + "(" * 50000, timeout_sec=3.0)
    assert_redos_immune(pattern, "A" + "b'" * 50000 + " ", timeout_sec=3.0)
