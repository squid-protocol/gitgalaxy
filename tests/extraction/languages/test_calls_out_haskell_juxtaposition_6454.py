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


@pytest.mark.parametrize(
    "body, callees",
    [
        ('run x = object [ "type" .= String "c" ]\n', {"object", "String"}),
        ("run x = foo [ k .= v ]\n", {"foo"}),
        ("run x = do\n  total %= bump 1\n  pure x\n", {"bump", "pure"}),
        ("run x = parseIt x >>= go y\n", {"parseIt", "go"}),
        ("run x = foo [ 1 ] =<< bar x\n", {"foo", "bar"}),
    ],
)
def test_operators_ending_on_equals_do_not_make_an_expression_a_definition(body, callees):
    assert callees <= _callees(body)


def test_a_lone_equals_still_makes_a_definition():
    assert not {"getLevel"} & _callees("run x = Min x\n  where\n    getLevel (Header l) = Min l\n")


def test_definition_mask_keeps_calls_on_expression_lines():
    out = _callees("run x = do\n  when (a <= b) $ h (y)\n  r <- g (x)\n  k (z { f = 1 })\n")
    assert {"when", "h", "g", "k"} <= out


def test_signature_continuation_lines_are_masked():
    code = "run :: Maybe Int\n  -> Either String Int\n  -> IO ()\nrun a b = pure ()\n"
    funcs = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    out = {c for f in funcs for c in f["calls_out_to"]}
    assert not {"Maybe", "Either", "IO"} & out


@pytest.mark.parametrize(
    "body, callees",
    [
        ('run x = putStrLn "hi"\n', {"putStrLn"}),
        ('run x = do\n  putStrLn "hi"\n  return ()\n', {"putStrLn", "return"}),
        ('run x = error "boom"\n', {"error"}),
        ('run x = Format "markdown"\n', {"Format"}),
        ('run x = foo (Bar "x") 1\n', {"foo", "Bar"}),
        ('run x = [Opt "a", Fmt "m"]\n', {"Opt", "Fmt"}),
        ('run x = putStrLn "a" ++ show x\n', {"putStrLn", "show"}),
    ],
)
def test_string_literal_argument_ends_an_application(body, callees):
    assert callees <= _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        # the shield makes a backtick operator the same `""` as a string: an operand after it is no argument
        ("run a b = a `op` b\n", {"a", "op"}),
        ("run b = Foo `op` b\n", {"Foo"}),
        ('run t = t `elem` "abc"\n', {"t"}),
        ('run y = case y of\n  Foo "a" -> 1\n', {"Foo"}),
    ],
)
def test_string_argument_lookalikes_are_not_calls(body, absent):
    assert not absent & _callees(body)


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
    assert_redos_immune(pattern, "x = f " + '"' * 50000, timeout_sec=3.0)
    assert_redos_immune(pattern, "x = f " + '"a" ' * 30000, timeout_sec=3.0)


def _by_name(code: str) -> dict[str, set[str]]:
    funcs = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: set(f["calls_out_to"]) for f in funcs}


@pytest.mark.parametrize(
    "directives",
    [
        ("#ifdef W", "#else", "#endif"),
        ("#if defined(W)", "#elif X", "#endif"),
        ("#ifndef W", "#else", "# endif"),
    ],
)
def test_cpp_directive_lines_do_not_end_a_function_body(directives):
    d_if, d_else, d_end = directives
    code = f"f :: Int -> IO ()\nf x = do\n  a <- g x\n{d_if}\n  let t = True\n{d_else}\n  t <- h x\n{d_end}\n  k t\n  m n\n"
    assert {"g", "h", "k", "m"} <= _by_name(code)["f"]


def test_cpp_guarded_next_definition_stays_its_own_function():
    code = "f :: Int -> Int\nf x = g x\n#ifdef W\nh :: Int -> Int\nh y = k y\n#endif\n"
    got = _by_name(code)
    assert "k" not in got["f"]
    assert "k" in got["h"]


@pytest.mark.parametrize(
    "body, callees",
    [
        ("run x = BL.writeFile path x\n", {"writeFile"}),
        (
            'run x = do\n  BL.writeFile p x\n  T.putStrLn "a"\n  M.Map.insert k v m\n',
            {"writeFile", "putStrLn", "insert"},
        ),
        ("run x = Map.fromList (Map.toList x)\n", {"fromList", "toList"}),
        ("run x = f $ Map.insert k v m\n", {"f", "insert"}),
        ("run x = Foo.Bar x\n", {"Bar"}),
        ("run x = Seq.empty Seq.|> y\n", set()),
    ],
)
def test_qualified_heads_are_captured_unqualified(body, callees):
    assert callees <= _callees(body)


@pytest.mark.parametrize(
    "body, absent",
    [
        ("run x = Foo.Bar.Baz\n", {"Foo", "Bar", "Baz"}),
        ("run (M.Just x) = x\n", {"Just", "M"}),
        ("run x = case x of\n  M.Just y -> y\n  Q.R.Nothing -> 0\n", {"Just", "Nothing", "M", "Q", "R"}),
        ("import qualified Data.Map as M\nrun x = x\n", {"Data", "Map", "M", "qualified"}),
        ("module A.B (run) where\nimport Data.Map (fromList)\nrun x = x\n", {"A", "B", "Data", "fromList", "Map"}),
    ],
)
def test_qualified_lookalikes_are_not_calls(body, absent):
    assert not absent & _callees(body)


def test_qualified_alternative_is_redos_immune():
    pattern = LANGUAGE_DEFINITIONS["haskell"]["rules"]["calls_out"]
    # The regex is linear (about 35us per char of `Ab'.` on Linux), but a Windows runner is ~4x slower: 20000 repeats
    # measured 3.0-3.2s against the 3.0s bound (#7745). The sizes keep a ~3x margin there; a quadratic regex on
    # 24k chars still takes seconds.
    assert_redos_immune(pattern, "x = " + "A." * 8000, timeout_sec=3.0)
    assert_redos_immune(pattern, "x = " + "A.b " * 15000, timeout_sec=3.0)
    assert_redos_immune(pattern, "x = " + "Ab'." * 6000 + " ", timeout_sec=3.0)
