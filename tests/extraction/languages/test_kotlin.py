"""
Kotlin extraction hardening (epic #813, issue #823). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for kotlin in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- kotlin's entries were removed
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

KOTLIN_RULES = LANGUAGE_DEFINITIONS["kotlin"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("fun TargetFunc()", "TargetFunc"),
        ("suspend fun TargetFunc()", "TargetFunc"),
        ("internal inline fun TargetFunc()", "TargetFunc"),
        # Syntax-era / feature coverage
        (
            "fun <T, U : Comparable<U>> TargetFunc(x: T, y: U): T {",
            "TargetFunc",
        ),  # nested generic bound -- was a real bug, now fixed
        ("fun String.TargetFunc(): Int {", "TargetFunc"),  # extension function
        # Testing-framework-shaped functions that ARE real functions
        ("@Test\nfun TargetFunc() {", "TargetFunc"),  # JUnit @Test
    ],
    "invalid": [
        "class TargetFunc",  # class decl lookalike
        "val TargetFunc =",  # val decl lookalike
        "if (TargetFunc)",  # if lookalike
    ],
    "pathological": [
        (
            "@JvmStatic\n@Throws(Exception::class)\npublic \n suspend \n inline \n fun \n < \n T \n > \n TargetFunc \n (",
            "TargetFunc",
        ),  # carried-forward: JVM annotations and extreme generic spacing
        (
            "fun <T, U : Comparable<U>> TargetFunc(\n    x: T,\n    y: U,\n): T {",
            "TargetFunc",
        ),  # nested generic bound, params split vertically
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_kotlin_func_start_valid(payload, expected_name):
    assert_valid_match(KOTLIN_RULES["func_start"], payload, expected_name, "kotlin.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_kotlin_func_start_invalid(payload):
    assert_invalid_no_match(KOTLIN_RULES["func_start"], payload, "kotlin.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_kotlin_func_start_pathological(payload, expected_name):
    assert_pathological_match(KOTLIN_RULES["func_start"], payload, expected_name, "kotlin.func_start")


def test_kotlin_func_start_nested_generic_bound_regression():
    """
    Regression test for a real bug (epic #813/#823): the generic-parameter
    step-over was the flat `<[^>]{0,100}>`, truncating at the FIRST `>` and
    breaking any nested generic bound (`fun <T, U : Comparable<U>>
    foo(x: T, y: U): T {`, a realistic bounded generic function -- the
    same Rule-11 bug class already fixed for java/python/csharp/rust).
    """
    func_start = KOTLIN_RULES["func_start"]
    m = func_start.search("fun <T, U : Comparable<U>> TargetFunc(x: T, y: U): T {")
    assert m and m.group(1) == "TargetFunc", "nested generic bound detection regressed"


def test_kotlin_func_start_redos_immunity():
    """ReDoS sweep for the widened generic-parameter step-over."""
    func_start = KOTLIN_RULES["func_start"]
    assert_redos_immune(func_start, "fun <T, U : " + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("fun <T, U : Comparable<U>> Foo(x: T, y: U): T {")


def test_kotlin_func_start_known_limitation_raw_string_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a Kotlin raw
    (triple-quoted) string literal that happens to land at true line start
    still matches -- the same architectural class of bug confirmed for
    javascript/typescript template literals, Java text blocks, Go/Rust raw
    strings, and C# verbatim/raw strings (recurring bug class 3 in
    how_to_harden_extraction.md), now confirmed on a SEVENTH language.
    kotlin routes through Mode B (_slice_by_braces), currently gated to
    javascript/typescript only. Not fixed here -- tracked as its own
    future audited follow-up in the epic.
    """
    func_start = KOTLIN_RULES["func_start"]
    raw_string = 'val s = """\nfun TargetFunc() {\n"""'
    assert func_start.search(raw_string), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("fun TargetFunc(a: Int, b: String) {", "TargetFunc"),
        ("suspend fun TargetFunc(items: List<String>) {", "TargetFunc"),
        (
            "fun <T, U : Comparable<U>> TargetFunc(x: T, y: U): T {",
            "TargetFunc",
        ),  # nested generic bound -- was a real bug, now fixed
    ],
    "invalid": [
        "TargetFunc(a, b)",
        "when (x) {",
    ],
    "pathological": [
        (
            "internal \n suspend \n fun \n <T> \n TargetFunc \n (\n  items: List<T> = emptyList(),\n  callback: (Result<T>) -> Unit\n)",
            "TargetFunc",
        ),  # carried-forward: vertical generics, default arguments, lambda parameters
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_kotlin_args_valid(payload, expected_name):
    assert_valid_match(KOTLIN_RULES["args"], payload, expected_name, "kotlin.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_kotlin_args_invalid(payload):
    assert_invalid_no_match(KOTLIN_RULES["args"], payload, "kotlin.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_kotlin_args_pathological(payload, expected_name):
    assert_pathological_match(KOTLIN_RULES["args"], payload, expected_name, "kotlin.args")


def test_kotlin_args_nested_generic_bound_regression():
    """Regression test for the same root-cause bug as func_start's own regression test above."""
    args = KOTLIN_RULES["args"]
    assert args.search("fun <T, U : Comparable<U>> TargetFunc(x: T, y: U): T {"), (
        "nested generic bound args detection regressed"
    )


def test_kotlin_args_redos_immunity():
    """ReDoS sweep for the widened generic-parameter step-over."""
    args = KOTLIN_RULES["args"]
    assert_redos_immune(args, "fun <T, U : " + "a" * 100000, timeout_sec=3.0)
    assert args.search("fun <T, U : Comparable<U>> Foo(x: T, y: U): T {")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class TargetEntity {", None),
        ("data class TargetEntity(", None),
        ("sealed interface TargetEntity", None),
        ("enum class TargetEntity {", None),  # scoped enum class
        (
            "companion object {",
            None,
        ),  # anonymous companion object -- was a real bug, now fixed
        (
            "companion object TargetEntity {",
            None,
        ),  # named companion object -- was a real bug, now fixed
        ("companion object : Factory<TargetEntity> {", None),  # companion object with supertype
    ],
    "invalid": [
        "val x = TargetEntity()",
        "fun classLike()",
        "object: TargetEntity",
        "val x = object : Base() {",  # object expression, not a declaration
    ],
    "pathological": [
        (
            "@JvmInline\npublic \n data \n class \n TargetEntity \n (",
            None,
        ),  # carried-forward: Kotlin annotations and vertical modifier stacking
        (
            "companion \n object \n TargetEntity \n {",
            None,
        ),  # named companion object, vertically split
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_kotlin_class_start_valid(payload, expected_name):
    assert_valid_match(KOTLIN_RULES["class_start"], payload, expected_name, "kotlin.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_kotlin_class_start_invalid(payload):
    assert_invalid_no_match(KOTLIN_RULES["class_start"], payload, "kotlin.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_kotlin_class_start_pathological(payload, expected_name):
    assert_pathological_match(KOTLIN_RULES["class_start"], payload, expected_name, "kotlin.class_start")


def test_kotlin_class_start_companion_object_regression():
    """
    Regression test for a real bug (epic #813/#823): `companion object {
    ... }` (almost always anonymous -- a name is rare and optional in real
    Kotlin) never matched class_start at all. "companion" wasn't in the
    modifier list, and even adding it wouldn't have been sufficient since
    the class/interface/object/enum-class branch's name was mandatory.
    Fixed with a dedicated alternative narrowly scoped to the literal
    `companion object` shape with an optional name -- NOT by making the
    general branch's name optional, which would have opened a new false
    positive on object EXPRESSIONS (`object : Base() {`, an anonymous
    object literal used inline, a different construct from an object
    DECLARATION). Confirmed both directions still behave correctly.
    """
    class_start = KOTLIN_RULES["class_start"]
    assert class_start.search("companion object {"), "anonymous companion object regressed"
    assert class_start.search("companion object TargetEntity {"), "named companion object regressed"
    assert not class_start.search("val x = object : Base() {"), (
        "object expression must still NOT match (companion-object fix must not have broadened this)"
    )


def test_kotlin_class_start_redos_immunity():
    """ReDoS sweep for the new companion-object alternative."""
    class_start = KOTLIN_RULES["class_start"]
    assert_redos_immune(class_start, "companion object " + "a" * 100000, timeout_sec=3.0)
    assert class_start.search("companion object Foo {")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("import java.util.*", "java.util.*"),
        ("import static org.mockito.Mockito.*", "org.mockito.Mockito.*"),
        ("import foo.Bar as Baz", "foo.Bar"),  # aliased import
    ],
    "invalid": [
        "val importPath = false",
    ],
    "pathological": [
        (
            "import \n kotlinx.coroutines.flow.*",
            "kotlinx.coroutines.flow.*",
        ),  # carried-forward: vertical wildcard import
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_kotlin_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        KOTLIN_RULES["_dependency_capture"], payload, expected_path, "kotlin._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_kotlin_dependency_capture_invalid(payload):
    assert_invalid_no_match(KOTLIN_RULES["_dependency_capture"], payload, "kotlin._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_kotlin_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        KOTLIN_RULES["_dependency_capture"], payload, expected_path, "kotlin._dependency_capture"
    )
