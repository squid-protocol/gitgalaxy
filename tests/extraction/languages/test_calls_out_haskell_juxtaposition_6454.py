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


@pytest.mark.parametrize(
    "body, callees",
    [
        ("run x = do\n  res <- runIO $ conv a b\n  pure res\n", {"runIO"}),
        ("run x = do\n  case x of\n    Left e -> E.throwIO $ Err $ pack e\n", {"throwIO", "Err", "pack"}),
        ('run x = do\n  fail $ "Unknown " <> show x\n', {"fail", "show"}),
        ('run x = do\n  withObject "Filter" $ \\m -> go m\n', {"withObject", "go"}),
        ("run x = drop (x - 1) $ cycle $ ys\n", {"drop", "cycle"}),
        ("run x = do\n  print $! total x\n", {"print"}),
    ],
)
def test_dollar_application_heads_are_captured(body, callees):
    assert callees <= _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        # a section, a splice and a backtick operator are not `f $ x`
        ("run x = map ($) fs\n", {"$"}),
        ("run x = apply (f $) y\n", {"f"}),
        ("run x = id $(splice)\n", {"splice"}),
        ("run s = s `notElem` [1, 2]\n", {"s"}),
        ("run s = ys `elem` s\n", {"ys"}),
        ('run s = t `elem` "abc"\n', {"t"}),
    ],
)
def test_dollar_lookalikes_are_not_calls(body, absent):
    assert not absent & _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        ("run x = Min x\n  where\n    getLevel (Header l _ _) = Min l\n    getLevel _ = Max\n", {"getLevel"}),
        ('run x = do\n  let isHA ("k", _) = False\n      isHB (a, b) = True\n  foo x\n', {"isHA", "isHB"}),
        ("run x = do\n  let q y = 1\n  foo x\n", {"q"}),
    ],
)
def test_definition_left_sides_bind_names(body, absent):
    assert not absent & _callees(body)


def test_definition_mask_keeps_calls_on_expression_lines():
    out = _callees("run x = do\n  when (a <= b) $ h (y)\n  r <- g (x)\n  k (z { f = 1 })\n")
    assert {"when", "h", "g", "k"} <= out


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
    assert_redos_immune(pattern, "x = f " + "$ " * 50000, timeout_sec=3.0)
    assert_redos_immune(pattern, "f " + "a (" * 30000 + "=", timeout_sec=3.0)
    assert_redos_immune(pattern, "  let f " + "a " * 50000, timeout_sec=3.0)
    masked = LANGUAGE_DEFINITIONS["haskell"]["rules"]["_calls_out_masked_blocks"]
    assert_redos_immune(masked, "f " + "a (" * 30000, timeout_sec=3.0)
    assert_redos_immune(masked, ("f " + "x " * 100 + "\n") * 2000, timeout_sec=3.0)
