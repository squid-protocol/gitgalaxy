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
        ("foreign export ccall \"foo\" foo :: Int -> IO ()", "foo"),
    ],
    "invalid": [
        "data TargetFunc",
        "class TargetFunc",
        "newtype TargetFunc",
        "type TargetFunc",
        "instance TargetFunc",
        # String literal lookalike
        "let query = \"TargetFunc :: Int -> Int\"",
    ],
    "pathological": [
        ("TargetFunc \n :: \n Maybe \n ( \n Int \n -> \n Int \n )", "TargetFunc"),
        ("TargetFunc {- comment -} :: {- another -} Int -> Int", "TargetFunc"),
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
        "data targetClass", # Lowercase
        "let query = \"data TargetClass\"",
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
        ("\\x ->", "\\x ->"),
        ("\\(x, y) ->", "\\(x, y) ->"),
        ("@Int", "@Int"),
    ],
    "invalid": [
        "foo",
        "let x = 1",
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
    assert_pathological_dependency_match(HASKELL_RULES["_dependency_capture"], payload, expected_name, "_dependency_capture")  # noqa: S101
