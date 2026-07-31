"""
Rust extraction hardening (epic #813, issue #819). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for rust in one file: func_start, args,
class_start, _dependency_capture. Migrated out of the four old monolithic
dict files (test_function_extraction_strict.py, test_args_extraction_strict.py,
test_class_extraction_strict.py, test_dependency_extraction_strict.py) --
rust's entries were removed from those four when this file was added.
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

RUST_RULES = LANGUAGE_DEFINITIONS["rust"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("fn TargetFunc()", "TargetFunc"),
        ("pub async fn TargetFunc<T>() -> Result<()> {", "TargetFunc"),
        ("pub(crate) unsafe fn TargetFunc()", "TargetFunc"),
        # Syntax-era / feature coverage
        ("fn TargetFunc<'a, T>(x: &'a T) {", "TargetFunc"),  # lifetime + generic
        ("fn TargetFunc<T>(x: T) where T: Clone {", "TargetFunc"),  # where-clause
        ("const fn TargetFunc() -> i32 {", "TargetFunc"),  # const fn
        ('extern "C" fn TargetFunc() {', "TargetFunc"),  # extern C fn (FFI)
        (
            "fn TargetFunc<T: Clone + Into<Vec<u8>>>(x: T) {",
            "TargetFunc",
        ),  # two-level nested trait bound (already fixed pre-epic)
        # Testing-framework-shaped functions that ARE real functions
        ("#[test]\nfn TargetFunc() {", "TargetFunc"),  # #[test] attribute
        ("#[tokio::test]\nasync fn TargetFunc() {", "TargetFunc"),  # #[tokio::test] attribute
    ],
    "invalid": [
        "struct TargetFunc",  # struct decl lookalike
        "impl TargetFunc",  # impl block lookalike
        "let TargetFunc =",  # let binding lookalike
        "type TargetFunc = fn();",  # type alias for a function pointer lookalike
    ],
    "pathological": [
        (
            '#[inline(always)]\n#[cfg(test)]\npub \n async \n unsafe \n extern \n "C" \n fn \n TargetFunc \n < \n \'a \n , \n T \n > \n (',
            "TargetFunc",
        ),  # carried-forward: macro attributes, lifetimes, extreme vertical modifiers
        (
            "fn TargetFunc<T: Clone + Into<Vec<u8>>>(\n    x: T,\n) {",
            "TargetFunc",
        ),  # two-level nested trait bound, params split vertically
        (
            '#[derive(Debug)]\n#[cfg(feature = "async")]\n#[tokio::test(flavor = "multi_thread")]\nasync fn TargetFunc() {',
            "TargetFunc",
        ),  # 3+ stacked attribute macros with nested-paren arguments
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_rust_func_start_valid(payload, expected_name):
    assert_valid_match(RUST_RULES["func_start"], payload, expected_name, "rust.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_rust_func_start_invalid(payload):
    assert_invalid_no_match(RUST_RULES["func_start"], payload, "rust.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_rust_func_start_pathological(payload, expected_name):
    assert_pathological_match(RUST_RULES["func_start"], payload, expected_name, "rust.func_start")


def test_rust_func_start_known_limitation_raw_string_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a Rust raw
    string literal (`r#"..."#`, commonly used for embedded SQL/regex/JSON
    templates) that happens to land at true line start still matches --
    the same architectural class of bug confirmed for javascript/typescript
    template literals, Java 15+ text blocks, and Go raw strings (recurring
    bug class 3 in how_to_harden_extraction.md), now confirmed on a
    FOURTH, unrelated syntax feature. The real fix (matching against
    shielded code) lives in detector.py's _slice_by_braces and is
    currently gated to javascript/typescript only; broadening it to other
    Mode B languages (rust included) is tracked as its own future audited
    follow-up, not fixed here.
    """
    func_start = RUST_RULES["func_start"]
    raw_string = 's = r#"\nfn TargetFunc() {\n"#;'
    assert func_start.search(raw_string), "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("fn TargetFunc(a: i32, b: &str) {", None),
        ("pub async fn TargetFunc<T>(items: Vec<T>) -> Result<()> {", None),
        ("|x, y| x + y", None),  # closure
        ("fn TargetFunc(cb: impl FnOnce(i32)) {", None),  # nested-paren closure param
    ],
    "invalid": [
        "TargetFunc(a, b);",
        "while let Some(x) = iter.next() {",
    ],
    "pathological": [
        (
            "pub \n async \n fn \n TargetFunc \n <T> \n (\n  mut items: Vec<T>,\n  cb: impl FnOnce(i32) -> String\n)",
            None,
        ),  # carried-forward: massive vertical spacing with generic impl traits
        (
            "fn TargetFunc<T: Clone + Into<Vec<u8>>>(x: T) {",
            None,
        ),  # two-level nested trait bound -- was a real bug (args never got the Rule-11
        # widening func_start already had), now fixed
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_rust_args_valid(payload, expected_name):
    assert_valid_match(RUST_RULES["args"], payload, expected_name, "rust.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_rust_args_invalid(payload):
    assert_invalid_no_match(RUST_RULES["args"], payload, "rust.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_rust_args_pathological(payload, expected_name):
    assert_pathological_match(RUST_RULES["args"], payload, expected_name, "rust.args")


def test_rust_args_nested_trait_bound_regression():
    """
    Regression test for a real bug (epic #813/#819): unlike func_start
    (which already had the Rule-11 two-level-nesting idiom applied in an
    earlier pass), args' generic step-over was still the flat `<[^>]*>`,
    breaking on any nested trait bound (`fn Foo<T: Into<String>>(x: T) {`,
    a realistic, common Rust pattern -- e.g. any generic function bounded
    by a `From`/`Into` conversion trait). Widened to match func_start's
    already-proven two-level idiom.
    """
    args = RUST_RULES["args"]
    assert args.search("fn TargetFunc<T: Into<String>>(x: T) {"), "one-level nested trait bound regressed"
    assert args.search("fn TargetFunc<T: Clone + Into<Vec<u8>>>(x: T) {"), "two-level nested trait bound regressed"


def test_rust_args_redos_immunity():
    """ReDoS sweep for the widened generic-parameter step-over."""
    args = RUST_RULES["args"]
    assert_redos_immune(args, "fn Foo<T: " + "a" * 100000, timeout_sec=3.0)
    assert args.search("fn Foo<T: Into<String>>(x: T) {")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("struct TargetEntity {", "TargetEntity"),
        ("pub enum TargetEntity", "TargetEntity"),
        ("pub(crate) trait TargetEntity", "TargetEntity"),
        ("union TargetEntity {", "TargetEntity"),  # union (unsafe, rare but real)
        ("#[derive(Debug, Clone)]\nstruct TargetEntity {", "TargetEntity"),  # derive macro
    ],
    "invalid": [
        "impl TargetEntity {",  # impl block, not a declaration
        "let x = struct {};",
        "fn my_class() {",
        "impl Display for TargetEntity {",  # trait impl block, not a declaration
        "let x = TargetEntity {};",  # struct literal instantiation
    ],
    "pathological": [
        (
            "pub \n ( \n crate \n ) \n struct \n TargetEntity \n {",
            "TargetEntity",
        ),  # carried-forward: visibility modifier and vertical spacing
        (
            '#[derive(Debug)]\n#[serde(rename_all = "camelCase")]\n#[cfg(feature = "full")]\npub struct TargetEntity {',
            "TargetEntity",
        ),  # 3+ stacked derive/attribute macros
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_rust_class_start_valid(payload, expected_name):
    assert_valid_match(RUST_RULES["class_start"], payload, expected_name, "rust.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_rust_class_start_invalid(payload):
    assert_invalid_no_match(RUST_RULES["class_start"], payload, "rust.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_rust_class_start_pathological(payload, expected_name):
    assert_pathological_match(RUST_RULES["class_start"], payload, expected_name, "rust.class_start")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("use std::collections::HashMap;", "std::collections::HashMap"),
        ("pub use crate::networking::Socket;", "crate::networking::Socket"),
        ("use std::collections::{HashMap, HashSet};", "std::collections"),  # comma-grouped
        ("use super::*;", "super::*"),  # glob import via `super` -- was a real bug, now fixed
        ("use std::io::*;", "std::io"),  # plain glob import -- was a real bug, now fixed
    ],
    "invalid": [
        "let use_cache = true;",
    ],
    "pathological": [
        (
            "pub \n use \n crate::core::networking \n :: \n { \n  tcp::TcpSocket \n };",
            "crate::core::networking",
        ),  # carried-forward: vertical grouped re-export
        (
            "use \n std::io \n :: \n * \n ;",
            "std::io",
        ),  # glob import split vertically
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_rust_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(RUST_RULES["_dependency_capture"], payload, expected_path, "rust._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_rust_dependency_capture_invalid(payload):
    assert_invalid_no_match(RUST_RULES["_dependency_capture"], payload, "rust._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_rust_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        RUST_RULES["_dependency_capture"], payload, expected_path, "rust._dependency_capture"
    )


def test_rust_dependency_capture_glob_import_regression():
    """
    Regression test for a real bug (epic #813/#819): the capture group's
    character class (`[a-zA-Z0-9_:{},\\s]`) was missing `*`, so a glob
    import (`use std::io::*;`, extremely common Rust for re-exporting a
    module's entire public surface, e.g. `use super::*;` in almost every
    Rust test submodule) didn't match at all -- the whole `use` statement
    was invisible to the dependency graph.
    """
    pattern = RUST_RULES["_dependency_capture"]
    m = pattern.search("use std::io::*;")
    assert m and "std::io" in m.group(1), "glob import capture regressed"

    m2 = pattern.search("use super::*;")
    assert m2 and "super" in m2.group(1), "super-glob import capture regressed"


def test_rust_dependency_capture_redos_immunity():
    """ReDoS sweep for the widened character class."""
    pattern = RUST_RULES["_dependency_capture"]
    assert_redos_immune(pattern, "use " + "a" * 100000, timeout_sec=3.0)
    assert pattern.search("use std::io::*;")


def test_rust_dependency_capture_known_limitation_raw_string_lookalike_still_matches_at_regex_level():
    """
    Companion to func_start's own raw-string known-limitation test above:
    _dependency_capture is matched against fully unshielded raw file
    content for every language (see the java pass's #816 finding), so a
    `use ...;`-shaped line inside a Rust raw string literal at true line
    start still produces a phantom dependency-graph edge. Documented, not
    fixed here -- see how_to_harden_extraction.md's recurring bug class 10.
    """
    dependency_capture = RUST_RULES["_dependency_capture"]
    raw_string = 's = r#"\nuse std::io;\n"#;'
    assert dependency_capture.search(raw_string), "documents current (accepted, unfixed) regex behavior"
