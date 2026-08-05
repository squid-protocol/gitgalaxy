"""haskell strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)


# ==============================================================================
# HASKELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #585)
# ==============================================================================
HS_RULES = LANGUAGE_DEFINITIONS["haskell"]["rules"]

_HS_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x then y else z", None),
    ("structural_boundaries", "module Foo where", None),
    ("safety", "case result of\n  Just x -> x\n  Nothing -> 0", None),
    ("safety_bypasses", "fromJust maybeValue", None),
    ("high_risk_execution", "exitWith (ExitFailure 1)", None),
    ("io", 'contents <- readFile "f.txt"', None),
    ("state_mutation", "modifyIORef ref (+1)", None),
    ("dead_code", "-- data OldType = OldType", "-- just a note"),
    ("doc", "-- | A Haddock doc comment", None),
    ("test", 'describe "my suite" $ do', None),
    ("concurrency", 'forkIO (putStrLn "hi")', None),
    ("ui_framework", "import Brick", None),
    ("closures", "\\x -> x + 1", None),
    ("globals", "counter :: IORef Int\ncounter = unsafePerformIO (newIORef 0)", None),
    ("decorators", "{-# INLINE foo #-}", None),
    ("generics", "instance (Show a) => Show (Box a) where", None),
    ("comprehensions", "[x * 2 | x <- [1..10]]", None),
    ("scientific", "import Numeric.LinearAlgebra", None),
    ("reflection_metaprogramming", "{-# LANGUAGE TemplateHaskell #-}", None),
    ("ownership", "-- Author: Jane Doe", None),
    ("planned_debt", "-- TODO: refactor this", None),
    ("fragile_debt", "-- HACK: temporary workaround", None),
    ("spec_exposure", "-- [SPEC-123]", None),
    ("ssr_boundaries", "import Yesod", None),
    ("events", "import Reactive.Banana (Event)", None),
    ("dependency_injection", "config <- ask", None),
    ("macros", "{-# LANGUAGE OverloadedStrings #-}", None),
    ("pointers", "peek ptr", None),
    ("memory_alloc", "allocaBytes 1024 $ \\p -> f p", None),
    ("inline_asm", 'foreign import ccall "sin" c_sin :: Double -> Double', None),
    ("telemetry", 'logInfo "started"', None),
    ("debug_prints", 'putStrLn "debug"', None),
    ("explicit_casts", "fromIntegral x", None),
    ("panics_and_aborts", "throwIO MyException", None),
    ("thread_sleeps", "threadDelay 1000000", None),
    ("sync_locks", "takeMVar lock", None),
    ("immutability_locks", "pure x", None),
    ("cleanup", "hClose handle", None),
    ("listeners", "subscribe channel handler", None),
    ("test_skip", 'it "should work" $ pending', None),
    ("serialization_parsing", "decode jsonBytes", None),
    ("regex_execution", "text =~ pattern", None),
    ("time_date_logic", "getCurrentTime", None),
    ("ipc_rpc_bridges", "createProcess someProc", None),
]


@pytest.mark.parametrize("signature,positive,negative", _HS_SIMPLE_CASES)
def test_haskell_signature_positive_and_negative(signature, positive, negative):
    pattern = HS_RULES[signature]
    assert pattern is not None, f"haskell's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"haskell {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"haskell {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_haskell_func_start_excludes_type_level_declarations():
    """func_start's negative lookahead must exclude data/type/newtype/class/instance declarations."""
    pattern = HS_RULES["func_start"]
    assert pattern.search("myFunction :: Int -> Int")
    for reserved in ("data", "type", "newtype", "class", "instance"):
        assert not pattern.search(f"{reserved} Foo = Foo"), (
            f"func_start hallucinated on a {reserved!r} type-level declaration"
        )


def test_haskell_class_start_captures_type_name():
    pattern = HS_RULES["class_start"]
    m = pattern.search("data Animal = Dog | Cat")
    assert m is not None
    assert m.group(1) == "Animal"

    m2 = pattern.search("newtype Wrapper = Wrapper Int")
    assert m2 is not None
    assert m2.group(1) == "Wrapper"


def test_haskell_import_dependency_capture():
    dep_pattern = HS_RULES["_dependency_capture"]
    m = dep_pattern.search("import qualified Data.Map as Map")
    assert m is not None
    assert m.group(1) == "Data.Map"


def test_haskell_dead_code_requires_comment_prefix_not_shared_with_func_start():
    """
    Ambiguity check: dead_code and func_start share the literal keywords
    data/type/newtype/class/instance, but dead_code requires a `--` comment
    prefix while func_start's negative lookahead explicitly excludes those
    same words as real declarations -- neither can fire on the other's
    intended input.
    """
    dead_code = HS_RULES["dead_code"]
    func_start = HS_RULES["func_start"]
    assert dead_code.search("-- data OldType = OldType")
    assert not dead_code.search("data OldType = OldType"), "dead_code fired without a comment prefix"
    assert not func_start.search("-- data OldType = OldType"), "func_start hallucinated inside a comment"


def test_haskell_doc_vs_ownership_no_overlap():
    """
    doc's `--\\s*@author` (JSDoc-style tag) and ownership's `--\\s*Author:`
    (Haddock-style field) share the literal word "author" but use different
    conventions and must not cross-fire.
    """
    doc = HS_RULES["doc"]
    ownership = HS_RULES["ownership"]
    assert not doc.search("-- Author: Jane Doe"), "doc incorrectly matched a Haddock Author: field"
    assert not ownership.search("-- @author Jane Doe"), "ownership incorrectly matched a JSDoc-style @author tag"


def test_haskell_regex_execution_symbolic_operator_bug():
    """
    Regression test: `=~` used to be inside the shared \\b(...)\\b wrapper.
    \\b requires a word/non-word transition, but neither `=` nor `~` is a
    word character, so `\\b=~\\b` could only match with no surrounding
    whitespace at either edge (e.g. "x=~y") -- never idiomatic Haskell like
    "text =~ pattern" (spaced on both sides, the only way anyone actually
    writes this operator).
    """
    pattern = HS_RULES["regex_execution"]
    assert pattern.search("text =~ pattern"), "Failed to match the idiomatic spaced form of =~"
    assert pattern.search("makeRegex pat")


def test_haskell_globals_unsafeperformio_bug():
    """
    Regression test: the trailing `[^=]*` between the IORef/TVar/MVar type
    annotation and `unsafePerformIO` blocked crossing the `=` that MUST
    appear before `unsafePerformIO` in any real usage (the binding's own
    `counter = unsafePerformIO ...` line) -- this signature could never
    match a single real occurrence of the exact idiom it exists to detect.
    """
    pattern = HS_RULES["globals"]
    assert pattern.search("counter :: IORef Int\ncounter = unsafePerformIO (newIORef 0)"), (
        "Failed to match the real-world unsafePerformIO global idiom across two lines"
    )
    assert pattern.search("counter :: IORef Int\n{-# NOINLINE counter #-}\ncounter = unsafePerformIO (newIORef 0)"), (
        "Failed to match with a NOINLINE pragma between the signature and the binding"
    )
    assert not pattern.search("counter :: IORef Int\ncounter = newIORef 0"), (
        "Incorrectly matched a plain IORef binding with no unsafePerformIO at all"
    )
