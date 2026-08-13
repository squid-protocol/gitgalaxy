"""
JavaScript extraction hardening (epic #813, issue #814). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for javascript in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- javascript's entries were removed
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

JS_RULES = LANGUAGE_DEFINITIONS["javascript"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("function TargetFunc() {", "TargetFunc"),
        ("async function TargetFunc (req, res)", "TargetFunc"),
        ("export const TargetFunc = async () =>", "TargetFunc"),
        ("TargetFunc: function() {", "TargetFunc"),
        ("  async TargetFunc() {", "TargetFunc"),  # ES6 class async method
        # Syntax-era / feature coverage
        ("function* TargetFunc() {", "TargetFunc"),  # generator function declaration
        (
            "class Foo {\n  *TargetFunc() {}\n}",
            "TargetFunc",
        ),  # generator method -- was a real bug, now fixed
        (
            "class Foo {\n  async *TargetFunc() {}\n}",
            "TargetFunc",
        ),  # async generator method -- was a real bug, now fixed
        (
            "class Foo {\n  static *TargetFunc() {}\n}",
            "TargetFunc",
        ),  # static generator method -- was a real bug, now fixed
        ("class Foo {\n  get TargetFunc() {}\n}", "TargetFunc"),  # getter
        ("class Foo {\n  set TargetFunc(v) {}\n}", "TargetFunc"),  # setter
        ("class Foo {\n  #TargetFunc() {}\n}", "TargetFunc"),  # private method
        ("class Foo {\n  TargetFunc = () => {}\n}", "TargetFunc"),  # class field arrow function
    ],
    "invalid": [
        "class TargetFunc {",  # class decl lookalike
        "if (TargetFunc) {",  # if lookalike
        "typeof TargetFunc",  # typeof lookalike
        "if ((TargetFunc = compute()) !== null) {",  # assignment-in-condition lookalike
        "class Foo {\n  [Symbol.iterator]() {}\n}",  # computed method name, out of scope
    ],
    "pathological": [
        (
            "export \n const \n TargetFunc \n = \n async \n (req, res) \n =>",
            "TargetFunc",
        ),  # carried-forward: extreme spacing, vertical async arrow assignment
        (
            "class Foo {\n  static \n async \n *TargetFunc \n ( \n ) \n {}\n}",
            "TargetFunc",
        ),  # static async generator method, modifiers split vertically (the star
        # itself deliberately stays hugged to the name -- see the known-limitation
        # test below for why)
        (
            "export default class Foo {\n  async *TargetFunc(x, y) {\n    yield x + y;\n  }\n}",
            "TargetFunc",
        ),  # async generator method inside default-exported class
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_javascript_func_start_valid(payload, expected_name):
    assert_valid_match(JS_RULES["func_start"], payload, expected_name, "javascript.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_javascript_func_start_invalid(payload):
    assert_invalid_no_match(JS_RULES["func_start"], payload, "javascript.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_javascript_func_start_pathological(payload, expected_name):
    assert_pathological_match(JS_RULES["func_start"], payload, expected_name, "javascript.func_start")


def test_javascript_func_start_generator_method_regression():
    """
    Regression test for a real bug (epic #813/#814): class/object-literal
    generator methods (`*foo() {}`, `async *foo() {}`, `static *foo() {}`)
    were completely invisible to func_start -- the class-member branch had
    no allowance for the leading `*` ES6 generator method shorthand uses,
    unlike the plain `function*` declaration branch which already had
    `\\*?`. Generators are a common, legitimate ES6+ feature (iterables,
    custom iteration protocols).
    """
    func_start = JS_RULES["func_start"]
    assert func_start.search("class Foo {\n  *TargetFunc() {}\n}"), "plain generator method regressed"
    assert func_start.search("class Foo {\n  async *TargetFunc() {}\n}"), "async generator method regressed"
    assert func_start.search("class Foo {\n  static *TargetFunc() {}\n}"), "static generator method regressed"


def test_javascript_func_start_redos_immunity():
    """ReDoS sweep for the new optional generator-star branch."""
    func_start = JS_RULES["func_start"]
    assert_redos_immune(func_start, "  static *" + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("  static *TargetFunc() {")


def test_javascript_func_start_known_limitation_no_whitespace_tolerance_between_star_and_name():
    """
    Documents a DELIBERATE choice, not an oversight: the generator-method
    fix above allows zero whitespace between `*` and the method name
    (`*foo(`), not `[ \\t\\n]*` like the other modifier gaps (static/async/
    get/set) get. An earlier version of this fix DID allow whitespace
    there and was caught, via crucible_check.py against real corpus code
    (threejs), false-positive-matching a JSDoc comment continuation line
    as a generator method: `* A (storage) buffer attribute...` -- the `*`
    is the comment's own continuation marker, "A" is the first word of a
    plain-English sentence, and the following `(storage)` satisfied the
    args lookahead. Real generator methods always hug the star to the name
    with zero space (every real formatter emits `*foo()`, never `* foo()`
    or `*\\nfoo()`), so this is both safe AND more accurate than the
    original whitespace-tolerant version -- not a regression in
    flexibility, since no real formatted code needed that tolerance.
    """
    func_start = JS_RULES["func_start"]
    jsdoc_comment_line = "\t\t/**\n\t\t * A (storage) buffer attribute which was generated\n\t\t */"
    assert not func_start.search(jsdoc_comment_line), (
        "JSDoc comment prose must not be hallucinated as a generator method"
    )
    assert func_start.search("  *TargetFunc() {"), "sanity: the real, zero-space generator form still matches"


def test_javascript_func_start_bare_call_site_identifier_no_longer_matches():
    """
    Verifies that a bare call statement written at true line start with no
    preceding modifier keyword (e.g. `swap( elem, cssShow, function() {`)
    or a Jest/Mocha `it('...', () => {...})` block is correctly REJECTED.
    Previously, the func_start regex falsely matched these as method definitions
    because the `[^)]*` catch-all for parameter lists greedily consumed inline
    callbacks (which contain their own `)`), leading to phantom extractions
    (issue #1452). This is fixed by restricting the parenthesis match to `[^)(]*`.
    """
    func_start = JS_RULES["func_start"]
    jest_block = "describe('suite', () => {\n  it('does the thing', () => {\n    TargetFunc();\n  });\n});"
    swap_block = "\t\t\t\t\tswap( elem, cssShow, function() {"
    
    assert not func_start.search(jest_block), "the inline arrow function in the arguments prevents match"
    assert not func_start.search(swap_block), "the inline function in the arguments prevents match"


def test_javascript_func_start_string_literal_lookalike_still_matches_at_regex_level():
    """
    Documents a known, NOT-fixed limitation: func_start's own regex has no
    string/comment awareness, so function-shaped text inside a template
    literal (or any string) that happens to land at true line start still
    matches -- this is the ORIGINAL recurring bug class 3 finding
    (how_to_harden_extraction.md) that motivated this whole epic. The real
    fix (matching against shielded code) lives in detector.py's
    _slice_by_braces and IS gated for javascript (unlike most other Mode B
    languages, gated to javascript/typescript only) -- verified at the
    pipeline level in
    test_detector.py::test_detector_js_ts_string_literal_no_longer_hallucinated_as_function,
    not here.
    """
    func_start = JS_RULES["func_start"]
    assert func_start.search('let query = "function Foo() {";'), (
        "documents current (expected, pipeline-level-fixed-elsewhere) regex behavior"
    )


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("function TargetFunc(req, res) {", "TargetFunc"),
        ("const TargetFunc = async (data) =>", None),  # arrow branch doesn't capture the assigned name
        ("  TargetFunc(config) {", "TargetFunc"),
        (
            "class Foo {\n  *TargetFunc(a, b) {}\n}",
            None,
        ),  # generator method args -- was a real bug, now fixed
        (
            "class Foo {\n  async *TargetFunc(a, b) {}\n}",
            None,
        ),  # async generator method args -- was a real bug, now fixed
    ],
    "invalid": [
        "TargetFunc(req, res)",
        "while (i < 10) {",
    ],
    "pathological": [
        (
            # NOTE: expected_name is None here deliberately -- args has no capture
            # group for javascript, so the arrow-function branch's match is just
            # the parameter list itself; it doesn't include the assigned name.
            # args' job is proving a parameter block is captured without ReDoS,
            # not name-anchoring (same convention already documented for
            # typescript's/go's own args pathological cases).
            "export \n const \n TargetFunc \n = \n async \n (\n  { id, user: { name } },\n  [first, ...rest] = []\n) \n =>",
            None,
        ),  # carried-forward: destructured params w/ defaults and rest, vertical
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_javascript_args_valid(payload, expected_name):
    assert_valid_match(JS_RULES["args"], payload, expected_name, "javascript.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_javascript_args_invalid(payload):
    assert_invalid_no_match(JS_RULES["args"], payload, "javascript.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_javascript_args_pathological(payload, expected_name):
    assert_pathological_match(JS_RULES["args"], payload, expected_name, "javascript.args")


def test_javascript_args_generator_method_regression():
    """
    Regression test for the same root-cause bug as func_start's own
    regression test above. Also mirrors func_start's own zero-whitespace-
    between-star-and-name choice (no `[ \\t\\n]*` after `\\*?`) -- see
    func_start's known-limitation test for the JSDoc-comment false-positive
    this deliberately avoids.
    """
    args = JS_RULES["args"]
    assert args.search("class Foo {\n  *TargetFunc(a, b) {}\n}"), "plain generator method args regressed"
    assert args.search("class Foo {\n  async *TargetFunc(a, b) {}\n}"), "async generator method args regressed"


def test_javascript_args_redos_immunity():
    """ReDoS sweep for the new optional generator-star branch."""
    args = JS_RULES["args"]
    assert_redos_immune(args, "  static *" + "a" * 100000, timeout_sec=3.0)
    assert args.search("  static *TargetFunc(a) {")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class TargetEntity {", "TargetEntity"),
        ("export default class TargetEntity extends Base", "TargetEntity"),
        ("export class TargetEntity", "TargetEntity"),
        (
            "class TargetEntity extends Base.SubBase {",
            "TargetEntity",
        ),  # member-expression extends target
        ("class TargetEntity extends mixins(Base) {", "TargetEntity"),  # mixin function-call extends target
    ],
    "invalid": [
        "const a = class {}",
        "function classy() {",
        "import { TargetEntity } from 'foo';",
    ],
    "pathological": [
        (
            "export \n default \n class \n TargetEntity \n extends \n Base",
            "TargetEntity",
        ),  # carried-forward: vertical default exports and inheritance
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_javascript_class_start_valid(payload, expected_name):
    assert_valid_match(JS_RULES["class_start"], payload, expected_name, "javascript.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_javascript_class_start_invalid(payload):
    assert_invalid_no_match(JS_RULES["class_start"], payload, "javascript.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_javascript_class_start_pathological(payload, expected_name):
    assert_pathological_match(JS_RULES["class_start"], payload, expected_name, "javascript.class_start")


def test_javascript_class_start_known_limitation_extends_captures_first_segment_only():
    """
    Documents current (accepted, not a bug) behavior: class_start's extends
    capture is a plain identifier (`[a-zA-Z_$][\\w$]*`), so an extends
    target that's a member expression or call (`extends Base.SubBase`,
    `extends mixins(Base)`) only captures the FIRST identifier segment
    (`Base`, `mixins`) rather than the full expression. This is unrelated
    to the Rule-11 nested-generic bug class (JS has no generics) -- it's
    simply a partial capture of a compound expression, which is enough for
    the dependency/inheritance graph's purposes (identifying the base
    namespace) without needing the full expression.
    """
    class_start = JS_RULES["class_start"]
    m = class_start.search("class Foo extends Base.SubBase {")
    assert m and m.group(2) == "Base.SubBase", "documents current (accepted) partial-capture behavior"


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ('import { Component } from "@scope/package/module";', "@scope/package/module"),
        ('const fs = require("fs");', "fs"),
        ("import React, { useState } from 'react';", "react"),  # default + named import
        ("export * from './utils';", "./utils"),  # re-export all
    ],
    "invalid": [
        'const importPath = "x";',
        'console.log("imported");',
    ],
    "pathological": [
        (
            "export \n type \n { \n  ComponentA \n } \n from \n '@scope/custom-module'",
            "@scope/custom-module",
        ),  # carried-forward: vertical type-only re-export
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_javascript_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        JS_RULES["_dependency_capture"], payload, expected_path, "javascript._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_javascript_dependency_capture_invalid(payload):
    assert_invalid_no_match(JS_RULES["_dependency_capture"], payload, "javascript._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_javascript_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        JS_RULES["_dependency_capture"], payload, expected_path, "javascript._dependency_capture"
    )
