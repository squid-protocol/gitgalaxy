"""
C++ extraction hardening (epic #813, issue #821). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for cpp in one file: func_start, args,
class_start, _dependency_capture. Migrated out of the four old monolithic
dict files (test_function_extraction_strict.py, test_args_extraction_strict.py,
test_class_extraction_strict.py, test_dependency_extraction_strict.py) --
cpp's entries were removed from those four when this file was added.
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

CPP_RULES = LANGUAGE_DEFINITIONS["cpp"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("int TargetFunc() {", "TargetFunc"),
        ("std::vector<std::string> TargetFunc(int a, float b) {", "TargetFunc"),
        ("inline static const char* TargetFunc() {", "TargetFunc"),
        ("TargetFunc() : a(1) {", "TargetFunc"),  # constructor w/ member-init list
        # Syntax-era / feature coverage
        ("auto TargetFunc() -> std::vector<int> {", "TargetFunc"),  # trailing return type (C++11+)
        ("constexpr int TargetFunc() {", "TargetFunc"),  # constexpr (C++11+)
        (
            "bool TargetClass::operator==(const TargetClass& other) const {",
            "TargetClass::operator==",
        ),  # out-of-line operator== -- was a real bug, now fixed
        (
            "TargetClass& TargetClass::operator=(const TargetClass& other) {",
            "TargetClass::operator=",
        ),  # out-of-line operator= -- was a real bug, now fixed
        (
            "MyClass::operator()() const {",
            "MyClass::operator()",
        ),  # functor operator()
        (
            "MyClass::operator bool() const {",
            "MyClass::operator bool",
        ),  # primitive type conversion operator
        (
            "MyClass::operator std::string() const {",
            "MyClass::operator std::string",
        ),  # namespace-qualified type conversion operator
        (
            "MyClass::operator Foo() const {",
            "MyClass::operator Foo",
        ),  # custom type conversion operator
        (
            "MyClass::MyClass(int x) : field_(x), other_(0) {",
            "MyClass::MyClass",
        ),  # out-of-line constructor, multi-field member-init list
        (
            "MyClass::MyClass(int x) : " + "field_a(1), " * 60 + "field_z(2) {",
            "MyClass::MyClass",
        ),  # synthetic long initializer-list (over 500 chars, under 2000)
    ],
    "invalid": [
        "class TargetFunc {",  # class decl lookalike
        "#define TargetFunc()",  # macro-expansion lookalike
        "if (TargetFunc()) {",  # call inside condition
    ],
    "pathological": [
        (
            # carried-forward: the only way to separate a header declaration
            # from a source definition in an AST-free engine is the opening
            # brace -- this payload deliberately includes it.
            "int \n TargetFunc \n ( \n ) \n {",
            "TargetFunc",
        ),
        (
            "template<typename T>\ninline static const T& \nTargetFunc\n( \n const T& a, \n const T& b \n ) \n {",
            "TargetFunc",
        ),  # templated function, vertical
        (
            "TargetClass& TargetClass::operator=(TargetClass&& other) noexcept {",
            "TargetClass::operator=",
        ),  # move-assignment operator, noexcept modifier
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_cpp_func_start_valid(payload, expected_name):
    assert_valid_match(CPP_RULES["func_start"], payload, expected_name, "cpp.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_cpp_func_start_invalid(payload):
    assert_invalid_no_match(CPP_RULES["func_start"], payload, "cpp.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_cpp_func_start_pathological(payload, expected_name):
    assert_pathological_match(CPP_RULES["func_start"], payload, expected_name, "cpp.func_start")


def test_cpp_func_start_out_of_line_operator_regression():
    """
    Regression test for a real bug (epic #813/#821): none of func_start's
    three name-alternatives supported a class-qualifier prefix before the
    `operator` keyword, so out-of-line operator overload definitions
    (declared in a header, defined in the .cpp file --
    `TargetClass::operator=(...)`, `TargetClass::operator==(...)`,
    mainstream, common C++) were completely invisible. Confirmed via
    crucible_check.py: a real NVDA corpus file's function count jumped
    10 -> 13, the three new detections being exactly its three out-of-line
    comparison operators (operator<, operator!=, operator==).
    """
    func_start = CPP_RULES["func_start"]
    m1 = func_start.search("TargetClass& TargetClass::operator=(const TargetClass& other) {")
    assert m1 and m1.group(1) == "TargetClass::operator=", "out-of-line operator= regressed"
    m2 = func_start.search("bool TargetClass::operator==(const TargetClass& other) const {")
    assert m2 and m2.group(1) == "TargetClass::operator==", "out-of-line operator== regressed"


def test_cpp_func_start_conversion_operator_template_regression():
    """
    Regression test for issue #2010: func_start's conversion operator branch
    did not support template argument lists in the return type (e.g.
    `operator Vector<T>()`).
    """
    func_start = CPP_RULES["func_start"]

    # (a) Target repro
    m1 = func_start.search("Variant::operator Vector<::RID>() const {")
    assert m1 and m1.group(1) == "Variant::operator Vector<::RID>", "conversion operator with template arg regressed"

    # (b) Multi-type-param generic
    m2 = func_start.search("operator TypedDictionary<K,V>() {")
    assert m2 and m2.group(1) == "operator TypedDictionary<K,V>", "conversion operator with multi-param template arg regressed"

    # (c) Plain non-template conversion operator (should still match)
    m3 = func_start.search("Variant::operator bool() const {")
    assert m3 and m3.group(1) == "Variant::operator bool", "plain conversion operator regressed"

    # (d) Normal function with a template return type
    m4 = func_start.search("Vector<T> get_vector() {")
    assert m4 and m4.group(1) == "get_vector", "normal function with template return type regressed"


def test_cpp_func_start_redos_immunity():
    """ReDoS sweep for the new class-qualified operator alternatives."""
    func_start = CPP_RULES["func_start"]
    assert_redos_immune(func_start, "Foo::" * 5000 + "operator=(", timeout_sec=3.0)
    assert_redos_immune(func_start, "Foo::operator" + "=" * 100000, timeout_sec=3.0)
    assert func_start.search("Foo::operator=(const Foo& other) {")


def test_cpp_func_start_known_limitation_raw_string_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a C++ raw
    string literal (`R"(...)"`, commonly used for embedded SQL/regex/JSON)
    that happens to land at true line start still matches -- the same
    architectural class of bug confirmed for javascript/typescript template
    literals, Java text blocks, Go raw strings, Rust raw strings, and C#
    verbatim/raw strings (recurring bug class 3 in
    how_to_harden_extraction.md), now confirmed on a SIXTH language. cpp
    routes through Mode B (_slice_by_braces), currently gated to
    javascript/typescript only. Not fixed here -- tracked as its own
    future audited follow-up in the epic.
    """
    func_start = CPP_RULES["func_start"]
    raw_string = 'std::string s = R"(\nint TargetFunc() {\n)";'
    assert func_start.search(raw_string), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"

def test_cpp_macro_shield_does_not_exclude_prior_function_definition():
    """
    Regression test for issue #2240: A real function definition followed by a
    macro #define of the same name later in the file (e.g. CPython's release-build
    stub idiom) should not be excluded by the macro shield.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor(lang_id="cpp", language_definitions=LANGUAGE_DEFINITIONS)
    code = """
static void validate_list(PyGC_Head *head, enum flagstates flags) {
    // real body
}

#define validate_list(x, y) do{}while(0)
"""
    satellites, _ = detector._slice_by_braces(
        code=code,
        lang_id="cpp",
        rules=CPP_RULES,
        offset=0,
        spatial_map={},
    )
    assert len(satellites) == 1, "The real function should be found"
    assert satellites[0]["name"] == "validate_list"


def test_cpp_macro_shield_excludes_macro_invocation():
    """
    Ensures the original known-macro shield behavior is preserved: a macro definition
    followed by a function-shaped invocation of it should be excluded.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor(lang_id="cpp", language_definitions=LANGUAGE_DEFINITIONS)
    code = """
#define OPCODE(m_op) do{}while(0)

OPCODE(m_op) {
    case m_op:
        break;
}
"""
    satellites, _ = detector._slice_by_braces(
        code=code,
        lang_id="cpp",
        rules=CPP_RULES,
        offset=0,
        spatial_map={},
    )
    assert len(satellites) == 0, "The macro invocation should be excluded"


def test_cpp_macro_shield_excludes_macro_only():
    """
    Ensures that a macro definition without any prior function definition is excluded,
    not flagged as a function itself.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    detector = StructuralExtractor(lang_id="cpp", language_definitions=LANGUAGE_DEFINITIONS)
    code = """
#define MACRO_ONLY(x, y) do{}while(0)
"""
    satellites, _ = detector._slice_by_braces(
        code=code,
        lang_id="cpp",
        rules=CPP_RULES,
        offset=0,
        spatial_map={},
    )
    assert len(satellites) == 0, "The macro definition should not be found as a function"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("void TargetFunc(int a, float b) {", "TargetFunc"),
        ("std::vector<int> TargetFunc(const std::string& name) {", "TargetFunc"),
        (
            "bool TargetClass::operator==(const TargetClass& other) const {",
            "TargetClass::operator==",
        ),  # out-of-line operator args -- was a real bug, now fixed
    ],
    "invalid": [
        "TargetFunc(a, b);",
        "if (a > b) {",
    ],
    "pathological": [
        (
            "inline \n static \n void \n TargetFunc \n (\n  std::vector<std::string>&& items,\n  void (*callback)(int, float)\n)",
            "TargetFunc",
        ),  # carried-forward: vertical, nested-generic move param, function-pointer param
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_cpp_args_valid(payload, expected_name):
    assert_valid_match(CPP_RULES["args"], payload, expected_name, "cpp.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_cpp_args_invalid(payload):
    assert_invalid_no_match(CPP_RULES["args"], payload, "cpp.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_cpp_args_pathological(payload, expected_name):
    assert_pathological_match(CPP_RULES["args"], payload, expected_name, "cpp.args")


def test_cpp_args_out_of_line_operator_and_nested_template_regression():
    """
    Regression test for two real bugs fixed together (epic #813/#821):
    args had the same missing class-qualified-operator support as
    func_start, AND its own template-argument step-over was the flat
    `<[^>]*>`, breaking a nested type arg on the method's own template
    parameters (`Foo::Bar<Baz<int>>(...)`, an explicit template
    specialization). Confirmed via crucible_check.py: a real mlir corpus
    file's parameter count jumped 69 -> 73 (operator=(...) = delete/default
    declarations, which have no body so func_start correctly still doesn't
    count them as functions, but DO have a real parameter signature args
    should count for coupling purposes).
    """
    args = CPP_RULES["args"]
    m1 = args.search("bool TargetClass::operator==(const TargetClass& other) const {")
    assert m1, "out-of-line operator args regressed"
    m2 = args.search("void Foo::Bar<Baz<int>>(int x) {")
    assert m2, "nested-template method args regressed"


def test_cpp_args_redos_immunity():
    """ReDoS sweep for the new operator alternative and nested-template step-over."""
    args = CPP_RULES["args"]
    assert_redos_immune(args, "void Foo::Bar<" + "a" * 100000, timeout_sec=3.0)
    assert args.search("void Foo::Bar<Baz<int>>(int x) {")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class TargetEntity {", "TargetEntity"),
        ("struct TargetEntity : public Base {", "TargetEntity"),
        ("template <typename T> class TargetEntity", "TargetEntity"),
        ("enum class TargetEntity {", "TargetEntity"),  # scoped enum (C++11+)
        (
            "template <typename T, typename U = std::allocator<T>> class TargetEntity {",
            "TargetEntity",
        ),  # template w/ default arg, nested generic
    ],
    "invalid": [
        "enum classy {",
        "TargetEntity obj;",
        "friend class TargetEntity;",
    ],
    "pathological": [
        (
            "template \n < \n typename T \n > \n class \n [[nodiscard]] \n TargetEntity \n : \n public Base",
            "TargetEntity",
        ),  # carried-forward: vertical template definitions and C++ attributes
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_cpp_class_start_valid(payload, expected_name):
    assert_valid_match(CPP_RULES["class_start"], payload, expected_name, "cpp.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_cpp_class_start_invalid(payload):
    assert_invalid_no_match(CPP_RULES["class_start"], payload, "cpp.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_cpp_class_start_pathological(payload, expected_name):
    assert_pathological_match(CPP_RULES["class_start"], payload, expected_name, "cpp.class_start")


def test_cpp_class_start_known_limitation_no_base_clause_capture():
    """
    Documents current (accepted, not a bug) behavior: unlike java/csharp/
    python's class_start, cpp's class_start has only ONE capture group --
    it deliberately never captures the base-class/interface list at all
    (`struct Foo : public Base {` only captures "Foo", nothing for
    "Base"). This is the pre-existing, original design (confirmed by the
    original monolithic test file already testing `struct TargetEntity :
    public Base {"` as valid with ONLY the entity name expected, never a
    base). Not treated as a gap to fix in this pass -- class_start's role
    here is anchoring the class/struct/union/enum START position, and
    cpp's base-list was never part of its contract, unlike languages where
    a second capture group already exists and was merely broken.
    """
    class_start = CPP_RULES["class_start"]
    assert class_start.groups == 1, "documents current (accepted) single-capture-group design"


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("#include <sys/types.h>", "sys/types.h"),
        ("import std.core;", "std.core"),
        ('#include "local.h"', "local.h"),  # quoted include
        ("export import foo.bar;", "foo.bar"),  # C++20 exported module import
    ],
    "invalid": [
        "int include_count = 0;",
    ],
    "pathological": [
        (
            "export \n import \n external.module.name \n ;",
            "external.module.name",
        ),  # carried-forward: vertical exported module import
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_cpp_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(CPP_RULES["_dependency_capture"], payload, expected_path, "cpp._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_cpp_dependency_capture_invalid(payload):
    assert_invalid_no_match(CPP_RULES["_dependency_capture"], payload, "cpp._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_cpp_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        CPP_RULES["_dependency_capture"], payload, expected_path, "cpp._dependency_capture"
    )
