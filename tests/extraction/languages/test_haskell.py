"""
Haskell extraction hardening (epic #813, issue #833). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for haskell in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the old
monolithic dict files.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any  # noqa: E402

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_valid_dependency_match,
    assert_valid_match,
)

HASKELL_RULES = LANGUAGE_DEFINITIONS["haskell"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("TargetFunc :: Int -> Int", "TargetFunc"),
        ("TargetFunc :: Maybe String", "TargetFunc"),
        # Valid operators?
        ("(+++) :: Int -> Int", "(+++)"),
        ("target_func :: a -> b", "target_func"),
        ("targetFunc' :: a -> b", "targetFunc'"),
        # Foreign export
        ('foreign export ccall "foo" foo :: Int -> IO ()', "foo"),
        # #1442: equation-form (no `::` anywhere) -- typeclass instance
        # method equations and where-clause locals, both pattern-matched
        # on constructor args with no restated signature.
        ('  targetFunc PlainMath = String "plain"', "targetFunc"),
        ('  targetFunc (WebTeX "") = String "webtex"', "targetFunc"),
        ("  targetFunc doc (JSONFilter f) =", "targetFunc"),
        ("  targetFunc f action = do", "targetFunc"),
        (' targetFunc CiteprocFilter = object [ "type" .= String "citeproc" ]', "targetFunc"),
        # #1564: a same-line `let name args = expr` local binding inside a
        # `do` block -- the reserved-word exclusion used to sit right after
        # `^[ \t]+` with no way to look past a leading "let ", so the whole
        # line was blocked outright instead of anchoring on the real name.
        ("  let targetFunc fmt = Format.FlavoredFormat fmt mempty", "targetFunc"),
        ("  let targetFunc msg = messageVerbosity msg == WARNING", "targetFunc"),
    ],
    "invalid": [
        "data TargetFunc",
        "class TargetFunc",
        "newtype TargetFunc",
        "type TargetFunc",
        "instance TargetFunc",
        # String literal lookalike
        'let query = "TargetFunc :: Int -> Int"',
        # #1442: equation-form must not fire on column-0 (top-level, out of
        # scope -- see the issue), zero-arg value bindings, `==`/`=>`/`<=`/
        # `>=`/`/=` lookalikes, `<-`-bound do-statements, or reserved words.
        "targetFunc x = x + 1",
        "  targetFunc = 5",
        "  targetFunc = foo bar",
        "  when (verbosity == INFO) $ report $ RunningFilter f",
        "  targetFunc <- getLine",
        "  where",
        "  case targetFunc of",
        # #1564: a bare multi-binding-block opener (nothing on the same
        # line after "let") and a zero-arg `let`-bound value binding must
        # still be excluded, same reasoning as the non-`let` cases above.
        "  let",
        "  let targetFunc = 5",
    ],
    "pathological": [
        ("TargetFunc \n :: \n Maybe \n ( \n Int \n -> \n Int \n )", "TargetFunc"),
        ("TargetFunc {- comment -} :: {- another -} Int -> Int", "TargetFunc"),
        ("   targetFunc (Foo (Bar baz)) qux = frobnicate baz qux", "targetFunc"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_haskell_func_start_valid(payload, expected_name):
    assert_valid_match(HASKELL_RULES["func_start"], payload, expected_name, "func_start")  # noqa: S101


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_haskell_func_start_invalid(payload):
    assert_invalid_no_match(HASKELL_RULES["func_start"], payload, "func_start")  # noqa: S101


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_haskell_func_start_pathological(payload, expected_name):
    assert_pathological_match(HASKELL_RULES["func_start"], payload, expected_name, "func_start")  # noqa: S101


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("data TargetClass", "TargetClass"),
        ("newtype TargetClass", "TargetClass"),
        ("class TargetClass", "TargetClass"),
        ("type TargetClass", "TargetClass"),
        ("type family TargetClass", "TargetClass"),
        ("data TargetClass a =", "TargetClass"),
        ("class Show a => TargetClass a where", "TargetClass"),
        ("data TargetClass deriving (Show)", "TargetClass"),
    ],
    "invalid": [
        "data targetClass",  # Lowercase
        'let query = "data TargetClass"',
        "TargetClass :: Int -> Int",
    ],
    "pathological": [
        ("data \n TargetClass", "TargetClass"),
        ("class \n (Show a, Eq a) \n => \n TargetClass \n a \n where", "TargetClass"),
        ("data {- comment -} TargetClass {- comment -} a = Foo", "TargetClass"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_haskell_class_start_valid(payload, expected_name):
    assert_valid_match(HASKELL_RULES["class_start"], payload, expected_name, "class_start")  # noqa: S101


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_haskell_class_start_invalid(payload):
    assert_invalid_no_match(HASKELL_RULES["class_start"], payload, "class_start")  # noqa: S101


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_haskell_class_start_pathological(payload, expected_name):
    assert_pathological_match(HASKELL_RULES["class_start"], payload, expected_name, "class_start")  # noqa: S101


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        (":: Int -> Int", ":: Int -> Int"),
        (":: (Eq a) => a -> a", ":: (Eq a) => a -> a"),
        # #1505: qualified/dotted type names must not truncate the captured
        # signature -- pre-fix this only captured "T" (one letter, zero
        # arrows) from a real 1-arrow signature.
        (":: T.Text -> T.Text", ":: T.Text -> T.Text"),
        ("\\x ->", "\\x ->"),
        ("\\(x, y) ->", "\\(x, y) ->"),
        ("@Int", "@Int"),
        # #1505: signature-less equation form -- a typeclass instance method
        # or where/let-local helper with no restated `::` signature is
        # defined purely by its pattern-matched LHS.
        ("identity x = x", "identity x ="),
        ("combine newval (MetaList xs) = MetaList xs", "combine newval (MetaList xs) ="),
        # #1564: a same-line `let name args = expr` local binding must count
        # its own args too, not just get recognized by func_start -- mirrors
        # the identical fix on that rule.
        ("let targetFunc fmt = mempty", "let targetFunc fmt ="),
    ],
    "invalid": [
        "foo",
        # `let x = 1` is a value binding, not a function equation -- "let"
        # must never be treated as the function name being defined (#1505).
        # Still true post-#1564: the fix only skips PAST a leading "let ",
        # it doesn't relax the zero-arg value-binding exclusion.
        "let x = 1",
        "where x = 1",
        # A guard between the pattern list and the real `=` isn't a shape
        # the equation-form alternative understands (#1505) -- must not
        # match at all rather than mis-binding the guard as part of the args.
        "foo x | x > 0 = 1",
    ],
    "pathological": [
        (":: \n (Eq a, \n Show a) \n => \n a \n -> \n a", ":: \n (Eq a, \n Show a) \n => \n a \n -> \n a"),
        ("\\ {- comment -} x {- comment -} ->", "\\ {- comment -} x {- comment -} ->"),
        (":: (a -> (b -> c)) -> (a -> b) -> a -> c", ":: (a -> (b -> c)) -> (a -> b) -> a -> c"),
    ],
}


@pytest.mark.parametrize("payload,expected_match", ARGS_CASES["valid"])
def test_haskell_args_valid(payload, expected_match):
    match = HASKELL_RULES["args"].search(payload)
    assert match is not None  # noqa: S101
    assert match.group(0) == expected_match  # noqa: S101


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_haskell_args_invalid(payload):
    match = HASKELL_RULES["args"].search(payload)
    assert match is None  # noqa: S101


@pytest.mark.parametrize("payload,expected_match", ARGS_CASES["pathological"])
def test_haskell_args_pathological(payload, expected_match):
    match = HASKELL_RULES["args"].search(payload)
    assert match is not None  # noqa: S101
    assert match.group(0) == expected_match  # noqa: S101


# ==============================================================================
# DEPENDENCY_CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("import Control.Monad", "Control.Monad"),
        ("import qualified Data.Text as T", "Data.Text"),
        ("import Data.List (map, filter)", "Data.List"),
        ("import qualified Data.Map.Strict as Map", "Data.Map.Strict"),
        ("import Data.Set hiding (empty)", "Data.Set"),
    ],
    "invalid": [
        "let import_val = 1",
        "foo import bar",
        "importData :: Int",
    ],
    "pathological": [
        ("import \n qualified \n Data.Map", "Data.Map"),
        ("import {- comment -} Control.Monad {- comment -}", "Control.Monad"),
    ],
}


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_CASES["valid"])
def test_haskell_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(HASKELL_RULES["_dependency_capture"], payload, expected_name, "_dependency_capture")  # noqa: S101


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_haskell_dependency_invalid(payload):
    assert_invalid_no_match(HASKELL_RULES["_dependency_capture"], payload, "_dependency_capture")  # noqa: S101


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_CASES["pathological"])
def test_haskell_dependency_pathological(payload, expected_name):
    assert_pathological_dependency_match(
        HASKELL_RULES["_dependency_capture"], payload, expected_name, "_dependency_capture"
    )  # noqa: S101


# ==============================================================================
# BLOCK SLICING / POINT-FREE LOGIC (#1312)
# ==============================================================================


def test_haskell_func_start_point_free_value_binding_rejected():
    """#1312: point-free value bindings lack an arrow in their signature and must be rejected."""
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    extractor = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS)
    payload = 'defaultKaTeXURL :: Text\ndefaultKaTeXURL = "https://..."\n'

    # We call coding_analysis directly to exercise _slice_by_indentation.
    segments = extractor._partition_segments(payload, "haskell")

    equations = {}
    mitigation_telemetry = {}
    segment_spatial_maps = [{}]

    functions, _ = extractor._function_slice(
        segments,
        segment_spatial_maps,
        equations,
        mitigation_telemetry,
        None,
    )

    # defaultKaTeXURL should NOT be extracted as a function
    extracted_names = [f["name"] for f in functions]
    assert "defaultKaTeXURL" not in extracted_names  # noqa: S101


def test_haskell_func_start_point_free_function_accepted():
    """#1312: point-free functions have an arrow in their signature and must be accepted."""
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    extractor = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS)
    payload = "htmlFormat :: Text -> Bool\nhtmlFormat = (`elem` [...])\n"

    segments = extractor._partition_segments(payload, "haskell")
    equations = {}
    mitigation_telemetry = {}
    segment_spatial_maps = [{}]

    functions, _ = extractor._function_slice(
        segments,
        segment_spatial_maps,
        equations,
        mitigation_telemetry,
        None,
    )

    extracted_names = [f["name"] for f in functions]
    assert "htmlFormat" in extracted_names  # noqa: S101


def test_haskell_func_start_wrapped_multiline_signature_accepted():
    """#1312: real functions with wrapped multiline signatures must be accepted."""
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    extractor = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS)
    # The -> is on the second line of the signature.
    payload = "myFunc :: Int\n  -> Int\nmyFunc = (+ 1)\n"

    segments = extractor._partition_segments(payload, "haskell")
    equations = {}
    mitigation_telemetry = {}
    segment_spatial_maps = [{}]

    functions, _ = extractor._function_slice(
        segments,
        segment_spatial_maps,
        equations,
        mitigation_telemetry,
        None,
    )

    extracted_names = [f["name"] for f in functions]
    assert "myFunc" in extracted_names  # noqa: S101


def test_haskell_func_start_abstract_method_accepted():
    """#1435: abstract typeclass methods with no equations (1-line block) must be accepted."""
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    extractor = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS)
    payload = "class HasSyntaxExtensions a where\n  getExtensions :: a -> Extensions\n"

    segments = extractor._partition_segments(payload, "haskell")
    equations = {}
    mitigation_telemetry = {}
    segment_spatial_maps = [{}]

    functions, _ = extractor._function_slice(
        segments,
        segment_spatial_maps,
        equations,
        mitigation_telemetry,
        None,
    )

    extracted_names = [f["name"] for f in functions]
    assert "getExtensions" in extracted_names  # noqa: S101


def _extract_function_names(payload: str) -> list[str]:
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    extractor = StructuralExtractor("haskell", LANGUAGE_DEFINITIONS)
    segments = extractor._partition_segments(payload, "haskell")
    functions, _ = extractor._function_slice(segments, [{}], {}, {}, None)
    return [f["name"] for f in functions]


def test_haskell_func_start_instance_method_equations_accepted():
    """#1442: typeclass instance method equations (no restated `::`) must be found,
    and every pattern-matched clause of the same method must collapse into ONE node
    (real example: pandoc's `ToJSON HTMLMathMethod` instance, 10 clauses)."""
    payload = (
        "instance ToJSON HTMLMathMethod where\n"
        '  toJSON PlainMath = String "plain"\n'
        '  toJSON (WebTeX "") = String "webtex"\n'
        '  toJSON (WebTeX url) = object ["method" .= String "webtex",\n'
        '                                "url" .= String url]\n'
        '  toJSON GladTeX = String "gladtex"\n'
        "\n"
        "data CiteMethod = Citeproc | Natbib deriving (Show)\n"
    )
    names = _extract_function_names(payload)
    assert names.count("toJSON") == 1  # noqa: S101


def test_haskell_func_start_where_clause_local_helpers_accepted():
    """#1442: `where`-bound local helpers with no signature must be found as their
    own named functions, distinct from the enclosing top-level function (real
    example: pandoc's `applyFilters`/`applyFilter`/`withMessages`)."""
    payload = (
        "applyFilters :: [Filter] -> [String] -> Pandoc -> m Pandoc\n"
        "applyFilters filters args d = do\n"
        "  expandedFilters <- mapM expandFilterPath filters\n"
        "  foldM applyFilter d expandedFilters\n"
        " where\n"
        "  applyFilter doc (JSONFilter f) =\n"
        "    withMessages f $ JSONFilter.apply args f doc\n"
        "  applyFilter doc (LuaFilter f)  =\n"
        "    withMessages f $ engineApplyFilter args f doc\n"
        "  withMessages f action = do\n"
        "    verbosity <- getVerbosity\n"
        "    when (verbosity == INFO) $ report $ RunningFilter f\n"
        "    return action\n"
    )
    names = _extract_function_names(payload)
    assert "applyFilters" in names  # noqa: S101
    assert names.count("applyFilter") == 1  # noqa: S101 -- 2 clauses, must dedup
    assert "withMessages" in names  # noqa: S101


def test_haskell_func_start_where_clause_zero_arg_binding_rejected():
    """#1442: a plain `where`-bound value binding (no argument pattern before `=`)
    must stay rejected, same as #1312's top-level point-free-value precedent."""
    payload = "total :: Int\ntotal = go\n  where\n    go = 5\n    count = base + 1\n"
    names = _extract_function_names(payload)
    assert "go" not in names  # noqa: S101
    assert "count" not in names  # noqa: S101
