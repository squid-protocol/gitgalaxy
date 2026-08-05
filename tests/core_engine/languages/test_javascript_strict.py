"""javascript strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py as part of
splitting that file into tests/core_engine/languages/, one file per language,
mirroring tests/extraction/languages/. See that file's git history for the
original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# JAVASCRIPT: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #589)
# ==============================================================================
# One positive-match case (and, where the doc's EXCLUDES wording calls for
# one, a negative-match case) per non-None structural signature javascript
# defines. Signatures whose behavior is simple/self-evident from a single
# keyword match are grouped into one parametrized test; signatures with
# real ReDoS history, control-flow exclusion shields, or cross-rule
# ambiguity risk get their own dedicated test below.
JS_RULES = LANGUAGE_DEFINITIONS["javascript"]["rules"]

_JS_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { y(); }", "throw new Error('x');"),
    ("safety", "try { f(); } catch (e) { g(); }", None),
    ("safety_bypasses", "if (x == y) {}", "if (x === y) {}"),
    ("high_risk_execution", "eval(userInput);", "console.log('safe');"),
    ("io", "fetch('/api/data');", None),
    ("api", "export default Foo;", None),
    ("state_mutation", "this.value = 1;", None),
    ("dead_code", "// if (debug) { doThing(); }", "// just a note"),
    ("doc", "/** @param {string} name */", None),
    ("concurrency", "async function f() { await g(); }", None),
    ("ui_framework", "const [x, setX] = useState(0);", None),
    ("globals", "window.location.href;", None),
    ("decorators", "@Component({})", None),
    ("generics", "/** @template T */", None),
    ("comprehensions", "arr.map(x => x * 2);", None),
    ("scientific", "const cv = require('opencv');", None),
    ("reflection_metaprogramming", "Object.assign(target, source);", None),
    ("ownership", "// @author Jane Doe", None),
    ("planned_debt", "// TODO: refactor this", None),
    ("fragile_debt", "// HACK: temporary workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "export async function getServerSideProps() {}", None),
    ("events", "emitter.on('data', handler);", None),
    ("dependency_injection", "@Injectable()", None),
    ("memory_alloc", "const x = new Foo();", "const x = new foo();"),
    ("telemetry", "logger.info('started');", None),
    ("debug_prints", "console.log('debug value:', x);", None),
    ("explicit_casts", "Number('42');", None),
    ("panics_and_aborts", "throw new Error('bad state');", None),
    ("thread_sleeps", "setTimeout(fn, 100);", None),
    ("sync_locks", "mutex.lock();", None),
    ("immutability_locks", "const x = Object.freeze({});", None),
    ("cleanup", "resource.dispose();", None),
    ("encapsulation", "class Foo { #secret; }", None),
    ("listeners", "el.addEventListener('click', fn);", None),
    ("test_skip", "test.skip('not ready', () => {});", None),
    ("serialization_parsing", "JSON.parse(raw);", None),
    ("regex_execution", "str.match(/foo/);", None),
    ("time_date_logic", "Date.now();", None),
    ("ipc_rpc_bridges", "worker.postMessage(data);", None),
]


@pytest.mark.parametrize("signature,positive,negative", _JS_SIMPLE_CASES)
def test_javascript_signature_positive_and_negative(signature, positive, negative):
    pattern = JS_RULES[signature]
    assert pattern is not None, f"javascript's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"javascript {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"javascript {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_javascript_structural_boundaries_excludes_const():
    """const is explicitly reserved for immutability_locks, not structural_boundaries."""
    pattern = JS_RULES["structural_boundaries"]
    assert pattern.search("let x = 1;")
    assert not pattern.search("const x = 1;")


def test_javascript_args_control_flow_shield():
    """
    Regression guard for the documented "Control Flow Shield": args must not
    hallucinate control-flow statements (while/if/for/switch/catch/return)
    that structurally resemble a method signature followed by a block.
    """
    pattern = JS_RULES["args"]
    assert pattern.search("function foo(a, b) {")
    assert pattern.search("(a, b) => {")
    assert pattern.search("myMethod(a, b) {")
    assert not pattern.search("while (i < 10) {")
    assert not pattern.search("if (x) {")
    assert not pattern.search("switch (x) {")


def test_javascript_args_redos_immunity():
    """The 'Ghost Args Shield' comment documents this as a historical ReDoS trap."""
    pattern = JS_RULES["args"]
    poison = "myMethod(" + "a, " * 20000 + "z) {"
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_javascript_func_start_excludes_control_flow_and_reserved_words():
    """
    func_start's negative lookahead explicitly excludes if/for/while/switch/
    catch/return/throw/new/typeof/jQuery/function so these never get
    hallucinated as function declarations just because they're followed by
    an open paren.
    """
    pattern = JS_RULES["func_start"]
    assert pattern.search("function namedFn() {")
    assert pattern.search("const foo = () => {")
    assert pattern.search("methodName(a, b) {")
    for reserved in ("if", "for", "while", "switch", "catch", "return", "throw", "typeof"):
        assert not pattern.search(f"{reserved} (x) {{"), f"func_start hallucinated on reserved word {reserved!r}"


def test_javascript_func_start_vertical_assignment_redos_immunity():
    """
    Regression guard for the documented 'Vertical Assignment Shield': a
    deeply multi-line-formatted async arrow assignment must not trigger
    catastrophic backtracking across vertical whitespace.
    """
    pattern = JS_RULES["func_start"]
    poison = "export const\n" + "  \n" * 5000 + "foo\n = \n async () => {"
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_javascript_class_start_captures_name_and_parent():
    pattern = JS_RULES["class_start"]
    m = pattern.search("export default class Dog extends Animal {")
    assert m is not None
    assert m.group(1) == "Dog"
    assert m.group(2) == "Animal"


def test_javascript_import_dependency_capture():
    """import/_dependency_capture must extract the exact module path string, not just match generically."""
    dep_pattern = JS_RULES["_dependency_capture"]
    m = dep_pattern.search("import { Component } from 'react';")
    assert m is not None
    assert "react" in m.groups()

    m2 = dep_pattern.search("const fs = require('fs');")
    assert m2 is not None
    assert "fs" in m2.groups()


def test_javascript_test_vs_regex_execution_ambiguity():
    """
    Regression test: javascript's `test` signature used to lack the
    negative lookbehind TypeScript's near-identical rule already had,
    so `myRegex.test('x')` -- a regex method call -- was miscounted as a
    unit-test-framework call (confirmed against the real config and fixed
    as part of this issue; jQuery's ajax.js/css.js in the golden-crucible
    corpus both had this exact false positive before the fix).
    """
    test_pattern = JS_RULES["test"]
    assert not test_pattern.search("myRegex.test('some string');"), (
        "test incorrectly matched a .test( regex method call"
    )
    assert test_pattern.search("test('should work', () => {});"), "test failed to match a real bare test( call"
    assert test_pattern.search("it('should work', () => {});"), "test failed to match a real bare it( call"
    assert test_pattern.search("describe('suite', () => {});"), "test failed to match describe("


def test_javascript_bitwise_ops_and_closures_do_not_collide():
    """
    The known bitwise_ops/closures ambiguity found in Rust (`|a| a + 1`) and
    C++ (`std::cout <<`) doesn't reproduce in javascript's own token set --
    javascript's arrow syntax (`=>`) shares no substring with its bitwise
    operators (`<<`, `>>`, `>>>`, `^`, `~`). This test confirms that holds,
    rather than assuming it from the other languages' bug reports.
    """
    bitwise = JS_RULES["bitwise_ops"]
    closures = JS_RULES["closures"]

    assert bitwise.search("x = a << 2;")
    assert not bitwise.search("const f = (x) => x + 1;"), "bitwise_ops false-positived on an arrow function"

    assert closures.search("const f = (x) => { return x; };")
    assert not closures.search("x = a << 2;"), "closures false-positived on a bitwise shift"


def test_javascript_standard_block_redos_immunity_for_deeply_nested_jsdoc_generics():
    """
    C#'s func_start ReDoS'd on deeply nested generic return types (already
    found and fixed). javascript doesn't have real generics, but its JSDoc
    '@template'-based simulation still needs to survive a pathological
    payload rather than assume small-input testing is representative.
    """
    pattern = JS_RULES["generics"]
    poison = "/**\n" + " * @template T\n" * 20000 + " */"
    assert_redos_immune(pattern, poison, timeout_sec=3.0)
