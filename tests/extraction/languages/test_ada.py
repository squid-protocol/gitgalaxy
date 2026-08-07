"""
Ada/SPARK extraction gauntlet (issue #76, epic #75). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for ada in one file: func_start, args,
class_start, _dependency_capture.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo, so a dotted
# `tests.extraction._extraction_harness` import only works by accident
# locally (e.g. `python -m pytest` from the repo root happens to put the
# root on sys.path) and fails in CI, which invokes the `pytest` console
# script directly. Insert this file's parent (tests/extraction/) onto
# sys.path instead, so the harness imports as a plain top-level module.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

ADA_RULES = LANGUAGE_DEFINITIONS["ada"]["rules"]

# ==============================================================================
# FUNC_START (func_start) -- subprogram BODIES only, not spec-only declarations.
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("procedure Foo is", "Foo"),  # no parameters
        ("procedure Foo (X : Integer) is", "Foo"),
        ("function Bar (X : Integer) return Integer is", "Bar"),
        ("function Bar return Integer is", "Bar"),  # no parameters, function still needs return
        ("procedure foo is", "foo"),  # lowercase (Ada is case-insensitive)
        (
            "procedure Increment (X : in out Integer) with Pre => X < Integer'Last, Post => X = X'Old + 1 is",
            "Increment",
        ),  # SPARK aspect clause between the profile and "is"
        ("   procedure Foo (X : Integer) is", "Foo"),  # leading indentation
    ],
    "invalid": [
        "procedure Foo (X : Integer);",  # bare spec declaration, no body -- no "is" at all
        "procedure Foo is abstract;",  # abstract subprogram, still just a declaration
        "procedure Foo (X : Integer) is null;",  # null procedure, still just a declaration
        "procedure Foo is new Generic_Proc (Integer);",  # generic instantiation, not a body
        "package Foo is new Generic_Pkg (Integer);",  # unrelated construct entirely
        "PROCEDURE_COUNT : Integer := 0;",  # substring lookalike, no word boundary after "procedure"
    ],
    "pathological": [
        ("procedure\n   Foo\n   (X : Integer)\n   is", "Foo"),  # vertical split
        ("procedure Foo (X : in out Integer := Compute(A, (B + C))) is", "Foo"),  # nested-paren default
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_ada_func_start_valid(payload, expected_name):
    assert_valid_match(ADA_RULES["func_start"], payload, expected_name, "ada.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_ada_func_start_invalid(payload):
    assert_invalid_no_match(ADA_RULES["func_start"], payload, "ada.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_ada_func_start_pathological(payload, expected_name):
    assert_pathological_match(ADA_RULES["func_start"], payload, expected_name, "ada.func_start")


def test_ada_func_start_redos_immunity():
    func_start = ADA_RULES["func_start"]
    assert_redos_immune(func_start, "procedure Foo (" + "A" * 200000, timeout_sec=3.0)
    assert_redos_immune(func_start, "procedure Foo with " + "A" * 200000, timeout_sec=3.0)
    assert func_start.search("procedure Foo is")


# ==============================================================================
# CLASS_START (class_start) -- tagged type declarations (root and derived).
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("type Animal is tagged record", "Animal"),  # root tagged type
        ("type Animal is tagged null record;", "Animal"),
        ("type Shape is abstract tagged record", "Shape"),
        ("type Shape is limited tagged record", "Shape"),
        ("type Dog is new Animal with record", "Dog"),  # derived/extended tagged type
        ("type Dog is new Animal with null record;", "Dog"),
        ("type Dog is abstract new Animal with private;", "Dog"),
    ],
    "invalid": [
        "type Celsius is range -273 .. 1000;",  # plain range type, not tagged
        "type Status is (Ok, Error);",  # enumeration type
        "subtype Positive is Integer range 1 .. Integer'Last;",  # subtype, not a tagged type
    ],
    "pathological": [
        ("type Dog is\n   new Animal\n   with record", "Dog"),  # vertical split
        ("type Foo is new " + "A" * 100 + " with record", "Foo"),  # long base-type name
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_ada_class_start_valid(payload, expected_name):
    assert_valid_match(ADA_RULES["class_start"], payload, expected_name, "ada.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_ada_class_start_invalid(payload):
    assert_invalid_no_match(ADA_RULES["class_start"], payload, "ada.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_ada_class_start_pathological(payload, expected_name):
    assert_pathological_match(ADA_RULES["class_start"], payload, expected_name, "ada.class_start")


def test_ada_class_start_redos_immunity():
    class_start = ADA_RULES["class_start"]
    assert_redos_immune(class_start, "type Foo is new " + "A" * 200000, timeout_sec=3.0)
    assert class_start.search("type Foo is tagged record")


# ==============================================================================
# ARGS (args) -- procedure/function parameter profiles.
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("procedure Foo (X : Integer)", "X"),
        ("function Bar (X : Integer; Y : Float) return Boolean", "X"),
        ("procedure Foo (X : in out Integer)", "X"),
    ],
    "invalid": [
        "PROCEDURE_COUNT : Integer := Foo (X);",  # substring lookalike, no word boundary
        "Configure (X : Integer);",  # plain call/declaration, no procedure/function keyword
    ],
    "pathological": [
        ("procedure Foo (X : in out Integer := Compute(A, (B + C)))", "X"),  # nested-paren default
        ("procedure\n   Foo\n   (X : Integer)", "X"),  # vertical split
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_ada_args_valid(payload, expected_name):
    assert_valid_match(ADA_RULES["args"], payload, expected_name, "ada.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_ada_args_invalid(payload):
    assert_invalid_no_match(ADA_RULES["args"], payload, "ada.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_ada_args_pathological(payload, expected_name):
    assert_pathological_match(ADA_RULES["args"], payload, expected_name, "ada.args")


def test_ada_args_redos_immunity():
    args = ADA_RULES["args"]
    assert_redos_immune(args, "procedure Foo (" + "A" * 200000, timeout_sec=3.0)
    assert args.search("procedure Foo (X : Integer)")


# ==============================================================================
# DEPENDENCY (_dependency_capture) -- context-clause `with` statements.
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("with Ada.Text_IO;", "Ada.Text_IO"),
        ("with Ada.Text_IO, Ada.Integer_Text_IO;", "Ada.Text_IO"),
        ("   with GNAT.Sockets;", "GNAT.Sockets"),
        ("with ada.text_io;", "ada.text_io"),  # lowercase
    ],
    "invalid": [
        "   with Pre => X > 0;",  # aspect specification, not a context clause
        "   with Global => (Input => X);",  # SPARK Global aspect, not a context clause
        "   with Inline;",  # boolean aspect, no arrow at all -- must still be excluded
    ],
    "pathological": [
        ("with \n Ada.Text_IO;", "Ada.Text_IO"),  # vertical split
        ("with Ada.Text_IO,\n     Ada.Integer_Text_IO;", "Ada.Text_IO"),  # multi-name, vertical split
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_ada_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(ADA_RULES["_dependency_capture"], payload, expected_path, "ada._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_ada_dependency_capture_invalid(payload):
    assert_invalid_no_match(ADA_RULES["_dependency_capture"], payload, "ada._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_ada_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        ADA_RULES["_dependency_capture"], payload, expected_path, "ada._dependency_capture"
    )


def test_ada_dependency_capture_redos_immunity():
    dep = ADA_RULES["_dependency_capture"]
    assert_redos_immune(dep, "with " + "A" * 200000, timeout_sec=3.0)
    assert dep.search("with Ada.Text_IO;")


def test_ada_import_excludes_aspect_specifications_regression():
    """
    Rule 15 (A Documented Exclusion Must Actually Exclude): import/
    _dependency_capture share a negative-lookahead exclusion list with
    decorators' aspect-mark vocabulary, so a `with Pre => ...`-style aspect
    clause on a declaration is never miscounted as a compilation-unit
    dependency. Verify the exclusion actually blocks every listed aspect
    mark, not just a couple of examples.
    """
    import_rule = ADA_RULES["import"]
    for aspect in (
        "Pre",
        "Post",
        "Global",
        "Depends",
        "Convention",
        "Inline",
        "Volatile",
        "SPARK_Mode",
        "Abstract_State",
        "Initializes",
        "Refined_Global",
        "Refined_Post",
        "Refined_State",
        "Refined_Depends",
    ):
        payload = f"   with {aspect} => True;"
        assert not import_rule.search(payload), f"import incorrectly matched aspect clause: {payload!r}"
    assert import_rule.search("   with Ada.Text_IO;"), "plain context clause must still match"
