"""
C extraction hardening (epic #813, issue #822). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for c in one file: func_start, args,
class_start, _dependency_capture. Migrated out of the four old monolithic
dict files (test_function_extraction_strict.py, test_args_extraction_strict.py,
test_class_extraction_strict.py, test_dependency_extraction_strict.py) --
c's entries were removed from those four when this file was added (class_start
had no prior entry there at all -- untested before this pass).
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

C_RULES = LANGUAGE_DEFINITIONS["c"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("static inline void TargetFunc(int a) {", "TargetFunc"),
        ("struct MyStruct * TargetFunc() {", "TargetFunc"),
        # Syntax-era / feature coverage
        ("int TargetFunc(const char *fmt, ...) {", "TargetFunc"),  # variadic function
        (
            "int TargetFunc(a, b)\n    int a;\n    int b;\n{",
            "TargetFunc",
        ),  # K&R old-style function definition
        # Testing-framework-shaped functions that ARE real functions
        ("void test_TargetFunc(void) {", "test_TargetFunc"),  # Unity-style test function
        # Macros after return type and complex nested parenthesis args
        ("PyObject* _Py_HOT_FUNCTION DONT_SLP_VECTORIZE \n TargetFunc(PyThreadState *tstate) {", "TargetFunc"),
        ("int TargetFunc(PyObject* Py_UNUSED(consts)) {", "TargetFunc"),
        ("Py_ssize_t TargetFunc(int (*check_lookup)(PyDictObject *, Py_ssize_t)) {", "TargetFunc"),
        # K&R style with macro return type
        ("PRIVATE void TargetFunc(out,plp,tag)\nFILE *out;\nstruct plink *plp;\nchar *tag;\n{", "TargetFunc"),
    ],
    "invalid": [
        "typedef struct TargetFunc {",  # struct decl lookalike
        "#define TargetFunc",  # macro-expansion lookalike
        "while(TargetFunc)",  # while lookalike
        "typedef void (*TargetFunc)(int, int);",  # function pointer typedef, not a definition
        "void (*callback)(int);",  # function pointer variable decl, no body
    ],
    "pathological": [
        (
            "__attribute__((always_inline))\nstatic \n inline \n struct \n MyStruct \n * \n TargetFunc \n () \n {",
            "TargetFunc",
        ),  # carried-forward: macro stacking, compiler attributes, erratic pointer spacing
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_c_func_start_valid(payload, expected_name):
    assert_valid_match(C_RULES["func_start"], payload, expected_name, "c.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_c_func_start_invalid(payload):
    assert_invalid_no_match(C_RULES["func_start"], payload, "c.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_c_func_start_pathological(payload, expected_name):
    assert_pathological_match(C_RULES["func_start"], payload, expected_name, "c.func_start")


def test_c_func_start_known_limitation_block_comment_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text on an UN-decorated
    block-comment continuation line (`/*\\nint TargetFunc() {\\n*/` -- no
    leading `*` continuation marker, a common real style for commenting
    out code) still matches at true line start. This is a variant of
    recurring bug class 3 (how_to_harden_extraction.md) manifesting via
    COMMENTS rather than STRING LITERALS -- C has no raw string syntax
    (unlike C++'s R"()"), so the string-literal variant doesn't reproduce
    here the same way (every C string-literal content line necessarily
    starts with a literal `"` character, which blocks the match at
    `^[ \\t]*` before any identifier can be reached) -- but the
    comment-based variant does. The real fix (matching against shielded
    code) lives in detector.py's _slice_by_braces and is currently gated
    to javascript/typescript only. Not fixed here -- tracked as its own
    future audited follow-up in the epic.
    """
    func_start = C_RULES["func_start"]
    block_comment = "/*\nint TargetFunc() {\n*/"
    assert func_start.search(block_comment), (
        "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"
    )


def test_c_func_start_string_literal_concatenation_does_not_false_positive():
    """
    Companion to the known-limitation test above: unlike the block-comment
    variant, adjacent string-literal concatenation (a real C idiom for
    building long strings across multiple lines) does NOT reproduce
    recurring bug class 3 here, because every content line necessarily
    starts with a literal `"` character before any identifier -- blocking
    `^[ \\t]*` from ever reaching function-shaped text. Documented as a
    genuine negative result (not just an untested gap) so a future pass
    doesn't waste time re-verifying this.
    """
    func_start = C_RULES["func_start"]
    concatenated_string = 'const char *s = "line1"\n    "int TargetFunc() {"\n    "line3";'
    assert not func_start.search(concatenated_string), (
        "documents current (confirmed-safe) behavior: string concatenation does not false-positive"
    )


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("void TargetFunc(int a, float *b) {", "TargetFunc"),
        ("static inline struct MyStruct* TargetFunc(void) {", "TargetFunc"),
        ("int TargetFunc(const char *fmt, ...) {", "TargetFunc"),  # variadic function args
    ],
    "invalid": [
        "TargetFunc(a, b);",
        "while (a < b) {",
    ],
    "pathological": [
        (
            "__attribute__((always_inline)) \n static \n void \n TargetFunc \n (\n  int a,\n  void (*callback)(int, void*)\n)",
            "TargetFunc",
        ),  # carried-forward: attributes, vertical spaces, function pointer arguments
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_c_args_valid(payload, expected_name):
    assert_valid_match(C_RULES["args"], payload, expected_name, "c.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_c_args_invalid(payload):
    assert_invalid_no_match(C_RULES["args"], payload, "c.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_c_args_pathological(payload, expected_name):
    assert_pathological_match(C_RULES["args"], payload, expected_name, "c.args")


def test_c_args_lowercase_typedef_pointer_with_body_call_regression():
    """
    Regression test for issue #1646: a function whose SIGNATURE has a
    plain-lowercase custom-typedef pointer parameter (`compiler *c`)
    and whose BODY contains a `SOMETHING(SomeCall(a->b, c))`-shaped
    nested call. The signature's own args should be what gets counted (2),
    not the body call.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor(lang_id="c", language_definitions=LANGUAGE_DEFINITIONS)
    code = """
int _PyCompile_MaybeAddStaticAttributeToClass(compiler *c, expr_ty e) {
    RETURN_IF_ERROR(PySet_Add(u->u_static_attributes, e->v.Attribute.attr));
}
"""
    satellites, _ = detector._slice_by_braces(
        code=code,
        lang_id="c",
        rules=C_RULES,
        offset=0,
        spatial_map={},
    )
    assert len(satellites) == 1
    assert satellites[0]["args_count"] == 2, (
        f"Expected 2 args, got {satellites[0]['args_count']}. "
        f"If 1, the regex falsely matched the body call. If 0, the regex failed to match the signature."
    )


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("struct TargetEntity {", None),
        ("typedef struct TargetEntity {", None),
        ("typedef struct {", None),  # anonymous typedef struct -- was a real bug, now fixed
        ("union TargetEntity {", None),
        ("enum TargetEntity {", None),
        (
            "struct foo_ops ops;",
            None,
        ),  # variable decl using an existing struct type -- DELIBERATELY matches (see
        # test_c_class_start_intentional_variable_declaration_match below); NOT a bug
    ],
    "invalid": [
        "return TargetEntity;",  # return statement lookalike
        "TargetEntity = 5;",  # assignment lookalike, no struct/union/enum keyword at all
    ],
    "pathological": [
        (
            "typedef \n struct \n TargetEntity \n {",
            None,
        ),  # tagged typedef struct, vertically split
        (
            "typedef \n struct \n {",
            None,
        ),  # anonymous typedef struct, vertically split
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_c_class_start_valid(payload, expected_name):
    assert_valid_match(C_RULES["class_start"], payload, expected_name, "c.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_c_class_start_invalid(payload):
    assert_invalid_no_match(C_RULES["class_start"], payload, "c.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_c_class_start_pathological(payload, expected_name):
    assert_pathological_match(C_RULES["class_start"], payload, expected_name, "c.class_start")


def test_c_class_start_anonymous_typedef_struct_regression():
    """
    Regression test for a real bug (epic #813/#822): the struct/union/enum
    tag name was mandatory, so anonymous typedef'd structs
    (`typedef struct { ... } MyStruct;`, an extremely common real C idiom
    -- confirmed via crucible_check.py: cpython's dictobject.c gained a
    newly-detected entity from exactly this shape) never matched
    class_start at all, undercounting this structural signature.
    """
    class_start = C_RULES["class_start"]
    assert class_start.search("typedef struct {"), "anonymous typedef struct detection regressed"
    assert class_start.search("typedef struct TargetEntity {"), "tagged typedef struct still works"


def test_c_class_start_intentional_variable_declaration_match():
    """
    Documents DELIBERATE (not a bug) behavior: class_start also matches a
    bare variable declaration using an existing struct/enum type
    (`struct foo_ops ops;`), because it has no trailing-`{` requirement.
    A version of this fix that added one was tried and reverted: it broke
    test_c_intentional_double_classification_sweep
    (tests/extraction/languages/test_c_strict.py), which documents this exact
    co-firing as intentional -- `struct foo_ops ops;` is meant to match
    BOTH class_start ("any struct declaration") AND the
    dependency_injection rule's `_ops`-vtable-style-suffix heuristic
    together. Recorded here so a future pass doesn't rediscover this and
    "fix" it again without checking that other test first.
    """
    class_start = C_RULES["class_start"]
    assert class_start.search("struct foo_ops ops;"), "documents current (intentional) behavior: this does match"


def test_c_class_start_redos_immunity():
    """ReDoS sweep for the widened (optional tag name) pattern."""
    class_start = C_RULES["class_start"]
    assert_redos_immune(class_start, "typedef struct " + "a" * 100000, timeout_sec=3.0)
    assert class_start.search("typedef struct Foo {")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("#include <stdio.h>", "stdio.h"),
        ('#include "local.h"', "local.h"),
        ("#embed <data.bin>", "data.bin"),  # C23 #embed directive
    ],
    "invalid": [
        "int include_path = 1;",
    ],
    "pathological": [
        (
            "# \n include \n <sys/socket.h>",
            "sys/socket.h",
        ),  # carried-forward: vertical, hash-space-directive
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_c_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(C_RULES["_dependency_capture"], payload, expected_path, "c._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_c_dependency_capture_invalid(payload):
    assert_invalid_no_match(C_RULES["_dependency_capture"], payload, "c._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_c_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        C_RULES["_dependency_capture"], payload, expected_path, "c._dependency_capture"
    )
