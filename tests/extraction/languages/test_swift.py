"""
Swift extraction hardening (epic #813, issue #824). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for swift in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- swift's entries were removed
from those four when this file was added.
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

SWIFT_RULES = LANGUAGE_DEFINITIONS["swift"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("func TargetFunc()", "TargetFunc"),
        ("public mutating func TargetFunc()", "TargetFunc"),
        ("open override func TargetFunc<T>()", "TargetFunc"),
        # Syntax-era / feature coverage
        (
            "func TargetFunc<T: Collection<Int>>(x: T) {",
            "TargetFunc",
        ),  # nested generic bound via primary associated type (Swift 5.7+) --
        # was a real bug, now fixed
        ("func TargetFunc() async throws -> Int {", "TargetFunc"),  # async/throws effect specifiers
        # Testing-framework-shaped functions that ARE real functions
        ("func test_TargetFunc() {", "test_TargetFunc"),  # XCTest-style test method
        ("@Test\nfunc TargetFunc() {", "TargetFunc"),  # Swift Testing @Test macro
    ],
    "invalid": [
        "class TargetFunc",  # class decl lookalike
        "let TargetFunc =",  # let decl lookalike
        "guard let TargetFunc",  # guard-let lookalike
    ],
    "pathological": [
        (
            "@available(iOS 14.0, *)\npublic \n mutating \n isolated \n func \n TargetFunc \n < \n T \n > \n (",
            "TargetFunc",
        ),  # carried-forward: availability macros and deep modifier stacking
        (
            "func TargetFunc<T: Collection<Int>>(\n    x: T\n) {",
            "TargetFunc",
        ),  # nested generic bound, params split vertically
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_swift_func_start_valid(payload, expected_name):
    assert_valid_match(SWIFT_RULES["func_start"], payload, expected_name, "swift.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_swift_func_start_invalid(payload):
    assert_invalid_no_match(SWIFT_RULES["func_start"], payload, "swift.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_swift_func_start_pathological(payload, expected_name):
    assert_pathological_match(SWIFT_RULES["func_start"], payload, expected_name, "swift.func_start")


def test_swift_func_start_nested_generic_bound_regression():
    """
    Regression test for a real bug (epic #813/#824): the generic-parameter
    step-over was the flat `<[^>]*>`, truncating at the FIRST `>` and
    breaking any nested generic bound via a primary associated type
    constraint (`func foo<T: Collection<Int>>(x: T) {`, Swift 5.7+,
    mainstream -- the same Rule-11 bug class already fixed for
    java/python/csharp/rust/kotlin).
    """
    func_start = SWIFT_RULES["func_start"]
    m = func_start.search("func TargetFunc<T: Collection<Int>>(x: T) {")
    assert m and m.group(1) == "TargetFunc", "nested generic bound detection regressed"


def test_swift_func_start_redos_immunity():
    """ReDoS sweep for the widened generic-parameter step-over."""
    func_start = SWIFT_RULES["func_start"]
    assert_redos_immune(func_start, "func Foo<T: " + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("func Foo<T: Collection<Int>>(x: T) {")


def test_swift_func_start_known_limitation_raw_string_lookalikes_still_match_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a Swift
    triple-quoted multi-line string or a raw string literal (`#"..."#`)
    that happens to land at true line start still matches -- the same
    architectural class of bug confirmed for javascript/typescript
    template literals, Java text blocks, Go/Rust raw strings, C#
    verbatim/raw strings, and Kotlin raw strings (recurring bug class 3 in
    how_to_harden_extraction.md), now confirmed on an EIGHTH language.
    swift routes through Mode B (_slice_by_braces), currently gated to
    javascript/typescript only. Not fixed here -- tracked as its own
    future audited follow-up in the epic.
    """
    func_start = SWIFT_RULES["func_start"]
    triple_quoted = 'let s = """\nfunc TargetFunc() {\n"""'
    raw_string = 'let s = #"\nfunc TargetFunc() {\n"#'
    assert func_start.search(triple_quoted), (
        "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"
    )
    assert func_start.search(raw_string), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("func TargetFunc(a: Int, b: String) {", "TargetFunc"),
        ("init(config: Config) {", "init"),
        (
            "func TargetFunc<T: Collection<Int>>(x: T) {",
            "TargetFunc",
        ),  # nested generic bound -- was a real bug, now fixed
    ],
    "invalid": [
        'TargetFunc(a: 1, b: "2")',
        "guard let a = b else {",
    ],
    "pathological": [
        (
            "public \n mutating \n func \n TargetFunc \n <T> \n (\n  _ items: [T],\n  completion: @escaping (Result<Void, Error>) -> Void\n)",
            "TargetFunc",
        ),  # carried-forward: vertical modifiers and escaping closures
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_swift_args_valid(payload, expected_name):
    assert_valid_match(SWIFT_RULES["args"], payload, expected_name, "swift.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_swift_args_invalid(payload):
    assert_invalid_no_match(SWIFT_RULES["args"], payload, "swift.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_swift_args_pathological(payload, expected_name):
    assert_pathological_match(SWIFT_RULES["args"], payload, expected_name, "swift.args")


def test_swift_args_nested_generic_bound_regression():
    """Regression test for the same root-cause bug as func_start's own regression test above."""
    args = SWIFT_RULES["args"]
    assert args.search("func TargetFunc<T: Collection<Int>>(x: T) {"), "nested generic bound args detection regressed"


def test_swift_args_redos_immunity():
    """ReDoS sweep for the widened generic-parameter step-over."""
    args = SWIFT_RULES["args"]
    assert_redos_immune(args, "func Foo<T: " + "a" * 100000, timeout_sec=3.0)
    assert args.search("func Foo<T: Collection<Int>>(x: T) {")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class TargetEntity {", None),
        ("public struct TargetEntity: Protocol", None),
        ("actor TargetEntity", None),
        ("extension TargetEntity {", None),  # extension declaration
        ("macro TargetEntity()", None),  # macro declaration (Swift 5.9+)
    ],
    "invalid": [
        "let obj = TargetEntity()",
        "func classMethod()",
        "guard let x = TargetEntity else",
    ],
    "pathological": [
        (
            "@available(iOS 14.0, *)\npublic \n final \n actor \n TargetEntity \n : \n Base",
            None,
        ),  # carried-forward: Swift attributes and vertical modifier stacking
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_swift_class_start_valid(payload, expected_name):
    assert_valid_match(SWIFT_RULES["class_start"], payload, expected_name, "swift.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_swift_class_start_invalid(payload):
    assert_invalid_no_match(SWIFT_RULES["class_start"], payload, "swift.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_swift_class_start_pathological(payload, expected_name):
    assert_pathological_match(SWIFT_RULES["class_start"], payload, expected_name, "swift.class_start")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("import Foundation", "Foundation"),
        ("@_exported import UIKit", "UIKit"),
    ],
    "invalid": [
        "var importData = true",
    ],
    "pathological": [
        (
            "@_exported \n import \n typealias \n CustomModule.TargetType",
            "CustomModule.TargetType",
        ),  # carried-forward: vertical exported typealias import
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_swift_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        SWIFT_RULES["_dependency_capture"], payload, expected_path, "swift._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_swift_dependency_capture_invalid(payload):
    assert_invalid_no_match(SWIFT_RULES["_dependency_capture"], payload, "swift._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_swift_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        SWIFT_RULES["_dependency_capture"], payload, expected_path, "swift._dependency_capture"
    )
