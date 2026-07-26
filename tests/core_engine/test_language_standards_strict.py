import pytest
import re
import time
import multiprocessing
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


# ==============================================================================
# THE BLAST CHAMBER (ReDoS Detonator)
# ==============================================================================
def _detonate(pattern: re.Pattern, payload: str, result_queue: multiprocessing.Queue):
    """
    Executes a regex against a payload inside an isolated OS process.
    Passes the duration back via a multiprocessing Queue.
    """
    start = time.perf_counter()
    list(pattern.finditer(payload))
    result_queue.put(time.perf_counter() - start)


def assert_redos_immune(pattern: re.Pattern, payload: str, timeout_sec: float = 1.0):
    """
    Runs a regex in an isolated process. If it exceeds timeout_sec, it is
    flagged as a Catastrophic Backtracking (ReDoS) vulnerability, and the
    OS process is violently terminated to prevent pytest from hanging.
    """
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()

    p = ctx.Process(target=_detonate, args=(pattern, payload, result_queue))
    p.start()
    p.join(timeout_sec)

    if p.is_alive():
        # THE FIX: Violently kill the OS process so it doesn't trap pytest's atexit handler
        p.terminate()
        p.join()  # Reap the zombie process instantly
        raise AssertionError(
            f"🔥 ReDoS TRIGGERED! Regex hung on payload:\n{payload}\nRegex: {pattern.pattern}"
        )

    if not result_queue.empty():
        duration = result_queue.get()
        assert duration < timeout_sec, f"Regex took too long: {duration:.4f}s"


# ==============================================================================
# TEST 1: THE C/C++ K&R AMBIGUITY TRAP
# Reference: language_standards.py (Line ~1365)
# ==============================================================================
def test_c_knr_ambiguity_trap():
    """
    Proves the C/C++ function spawner does not spiral into a 32,768-permutation
    death loop when encountering the MS-DOS BEGIN macro or massive parameter gaps.
    """
    c_func = LANGUAGE_DEFINITIONS["c"]["rules"]["func_start"]

    # The Pathological String: 100 parameters, no semicolon, ending in an invalid token.
    # Without the negative lookahead and {0,150} bounds, this will freeze the CPU.
    poison_knr = (
        "int legacy_func(a, b, c) \n"
        + "    int a; int b; int c;\n" * 50
        + "    INVALID_MACRO"
    )

    assert_redos_immune(c_func, poison_knr, timeout_sec=3.0)

    # Ensure it still correctly matches the MS-DOS BEGIN edge case
    valid_knr = "int legacy_func(a) \n    int a; \n BEGIN \n"
    matches = list(c_func.finditer(valid_knr))
    assert len(matches) == 1
    assert matches[0].group(1) == "legacy_func"


# ==============================================================================
# TEST 2: THE C# "IRON WALL" RETURN TYPE SHIELD
# Reference: language_standards.py (Line ~443)
# ==============================================================================
def test_csharp_iron_wall_redos():
    """
    Proves the C# function spawner survives pathologically massive nested return
    types without triggering overlapping whitespace ReDoS.
    """
    cs_func = LANGUAGE_DEFINITIONS["csharp"]["rules"]["func_start"]

    # The Pathological String: Deeply nested generics, missing the final brace,
    # packed with spaces that would normally trigger (Space)+ Space+ overlaps.
    poison_cs = (
        "    public static async Task<Dictionary<string, List<Tuple<int, string>>>>\n"
        * 20
        + "    BrokenMethod"
    )

    assert_redos_immune(cs_func, poison_cs)

    # Ensure a valid massive return type still works
    valid_cs = "public async Task<List<string>> FetchData() {"
    matches = list(cs_func.finditer(valid_cs))
    assert len(matches) == 1
    assert matches[0].group(1) == "FetchData"


# ==============================================================================
# TEST 3: THE C++ MACRO MULTI-LINE SPIRAL
# Reference: language_standards.py (Line ~1020)
# ==============================================================================
def test_cpp_macro_multiline_spiral():
    """
    Proves the C++ function spawner respects the (?![ \t]*#) negative lookaheads
    and does not cross into preprocessor directives to build hallucinated functions.
    """
    cpp_func = LANGUAGE_DEFINITIONS["cpp"]["rules"]["func_start"]

    # The Pathological String: A dangling return type that falls into a massive macro map.
    poison_cpp = "std::vector<int>\n" + "#define FOO 1\n" * 1000 + "myFunc() {"

    assert_redos_immune(cpp_func, poison_cpp)

    # Prove it actually stops at the macro and DOES NOT match the return type!
    # Instead of finding 0 matches, it will instantly skip the macros and find
    # "myFunc() {" as a valid, return-type-less constructor at the end of the file.
    matches = list(cpp_func.finditer(poison_cpp))
    assert len(matches) == 1, "Failed to safely skip the macros!"
    assert matches[0].group(1) == "myFunc", "Matched the wrong part of the string!"


# ==============================================================================
# TEST 4: AMBIGUITY OVERLAP AVOIDANCE (Pointers)
# Reference: language_standards.py (Line ~1430 & 1523)
# ==============================================================================
def test_c_pointer_ambiguity_overlap():
    r"""
    Proves that O(1) alternation `(?:\s*[*&]+\s*|\s+)` successfully prevents
    exponential evaluation on massive strings of pointer asterisks.
    """
    c_api = LANGUAGE_DEFINITIONS["c"]["rules"]["api"]
    c_cast = LANGUAGE_DEFINITIONS["c"]["rules"]["explicit_casts"]

    # The Pathological String: An unclosed cast with absurd pointer depth
    poison_cast = "( int " + "* " * 200 + ") "
    poison_api = "extern int " + "* " * 200 + " var"

    assert_redos_immune(c_cast, poison_cast)
    assert_redos_immune(c_api, poison_api)


# ==============================================================================
# TEST 5: COBOL GHOST SATELLITE HALLUCINATIONS
# Reference: language_standards.py (Line ~2470)
# ==============================================================================
def test_cobol_ghost_satellite_prevention():
    """
    Proves that heavily indented SQL queries or data divisions are explicitly
    blocked from being hallucinated as executable paragraphs.
    """
    cobol_func = LANGUAGE_DEFINITIONS["cobol"]["rules"]["func_start"]

    # 1. The SQL Ghost (Indented table column with a period)
    sql_ghost = "           POLICY.CUSTOMERNUMBER."
    assert len(list(cobol_func.finditer(sql_ghost))) == 0, (
        "Hallucinated an SQL column as a paragraph!"
    )

    # 2. The Data Ghost (01 Level)
    data_ghost = "       01  WS-POLICY-RECORD."
    assert len(list(cobol_func.finditer(data_ghost))) == 0, (
        "Hallucinated a Data Division struct as a paragraph!"
    )

    # 3. The Valid Paragraph
    valid_para = "       100-PROCESS-RECORDS SECTION."
    matches = list(cobol_func.finditer(valid_para))
    assert len(matches) == 1
    assert matches[0].group(1) == "100-PROCESS-RECORDS"


# ==============================================================================
# TEST 6: THE THERMODYNAMIC BALANCE COLLISIONS
# Proving that operators don't cannibalize each other across rules.
# ==============================================================================
def test_thermodynamic_operator_collisions():
    """
    Proves that common language operators (<<, |, &, !) do not trigger false
    positives in the wrong metric categories.
    """
    # 1. C++ Bitwise vs. I/O Streams
    cpp_bitwise = LANGUAGE_DEFINITIONS["cpp"]["rules"]["bitwise_ops"]
    assert len(list(cpp_bitwise.finditer("std::cout << 'Hello'"))) == 0, (
        "C++ bitwise tripped on a cout stream!"
    )
    assert len(list(cpp_bitwise.finditer("x <<= 1;"))) == 1, (
        "C++ bitwise failed to catch explicit shift assignment!"
    )

    # 2. Rust Closures vs. Bitwise
    rust_bitwise = LANGUAGE_DEFINITIONS["rust"]["rules"]["bitwise_ops"]
    assert len(list(rust_bitwise.finditer("let x = |a| a + 1;"))) == 0, (
        "Rust bitwise tripped on a closure!"
    )
    assert len(list(rust_bitwise.finditer("a ^ b"))) == 1, (
        "Rust bitwise failed to catch XOR!"
    )

    # 3. TypeScript Test Assertions vs. Object Methods
    ts_test = LANGUAGE_DEFINITIONS["typescript"]["rules"]["test"]
    assert len(list(ts_test.finditer("myRegex.test('string')"))) == 0, (
        "TS test metric tripped on a regex.test() call!"
    )
    assert len(list(ts_test.finditer("test('should work', () => {"))) == 1, (
        "TS test metric missed a real test block!"
    )


# ==============================================================================
# TEST 7: THE GLOBAL FUZZER (The Safety Net)
# ==============================================================================
def test_global_regex_syntax_integrity():
    """
    A final sanity check. Iterates over EVERY regex in the entire file and
    verifies it compiles correctly without throwing a re.error.
    """
    failed = []

    for lang, config in LANGUAGE_DEFINITIONS.items():
        rules = config.get("rules", {})
        for rule_name, pattern in rules.items():
            if pattern is not None:
                try:
                    # Accessing .pattern proves it's a valid compiled regex object
                    _ = pattern.pattern
                except Exception as e:
                    failed.append(f"{lang}::{rule_name} -> {e}")

    assert not failed, (
        f"Found {len(failed)} uncompiled or broken regexes in production schema:\n"
        + "\n".join(failed)
    )


# ==============================================================================
# TEST 8: TEST HARNESS EXCEPTION CATCHING (Coverage Completion)
# ==============================================================================
def test_redos_detonator_timeout_catch():
    """Proves the Blast Chamber successfully catches and kills hung regexes."""
    # A classic catastrophic backtracking regex: (a+)+$
    # Constructed dynamically to blind CodeQL from flagging the intentional trap
    evil_pattern = "(" + "a+" + ")+$"
    evil_regex = re.compile(evil_pattern)
    poison_payload = "a" * 30 + "b"

    # We now catch the standard AssertionError we just updated
    with pytest.raises(AssertionError) as exc_info:
        assert_redos_immune(evil_regex, poison_payload, timeout_sec=0.1)

    assert "ReDoS TRIGGERED" in str(exc_info.value)


def test_global_regex_syntax_integrity_catch(monkeypatch):
    """Proves the fuzzer catches malformed regex objects."""
    import sys

    # Inject a fake broken regex to trigger the exception block
    fake_defs = {
        "fake_lang": {
            "rules": {"broken_rule": "This is a string, not a compiled regex object!"}
        }
    }

    # Patch the locally imported variable inside THIS file's namespace!
    monkeypatch.setattr(sys.modules[__name__], "LANGUAGE_DEFINITIONS", fake_defs)

    with pytest.raises(AssertionError) as exc_info:
        test_global_regex_syntax_integrity()

    assert "Found 1 uncompiled or broken regexes" in str(exc_info.value)


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


# ==============================================================================
# CROSS-LANGUAGE REDOS SWEEP: "BARE IDENTIFIER BEFORE ARROW" FAMILY
# ==============================================================================
# All found by a systematic ReDoS sweep across every language's compiled
# patterns (not just the ones with an existing historical-bug comment):
# an unbounded identifier/word-run quantifier with no preceding \b anchor,
# immediately followed by a required-but-often-absent literal suffix
# (=>, ->, __c.getInstance, etc.). Because the leading character class has
# no boundary anchor, the engine retries the greedy-then-backtrack match at
# EVERY position in a long run of matching characters -- O(n^2) total, not
# exponential, but still a real DoS risk on a single pathologically long
# line (e.g. minified/obfuscated code). All bounded with numeric clamps
# instead of possessive quantifiers (`*+`), since those aren't available
# until Python 3.11 and this package supports 3.9+.
def test_java_args_lambda_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["java"]["rules"]["args"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("x -> x + 1")
    assert pattern.search("public void foo(int x) {")


def test_csharp_args_lambda_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["csharp"]["rules"]["args"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("x => x + 1")


def test_groovy_args_closure_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["groovy"]["rules"]["args"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("x -> x + 1")


def test_fortran_state_mutation_redos_immunity_and_kind_exclusion():
    """
    Two bugs, found together: the ReDoS sweep caught the quadratic blowup,
    and fixing it (adding a real \\b anchor) also fixed a pre-existing leak
    in the KIND=/LEN=/etc exclusion -- the original negative lookahead only
    blocked a match starting exactly at "KIND", not one starting mid-word
    ("KIND = 5" still matched "IND = " starting at its 2nd character, since
    \\bKIND doesn't apply there). Confirmed this leak existed before the
    ReDoS fix too, via the pattern's original (unbounded) form.
    """
    pattern = LANGUAGE_DEFINITIONS["fortran"]["rules"]["state_mutation"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("myvar = 5")
    assert pattern.search("mystruct%field = 1")
    assert not pattern.search("KIND = 5"), "Failed to exclude the KIND= false-positive trap"
    assert not pattern.search("LEN = 10"), "Failed to exclude the LEN= false-positive trap"


def test_embedded_python_comprehensions_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["embedded_python"]["rules"]["comprehensions"]
    assert_redos_immune(pattern, "(" * 40000, timeout_sec=3.0)
    assert pattern.search("[x for x in range(10)]")


def test_php_state_mutation_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["php"]["rules"]["state_mutation"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("$obj->prop = 1")
    assert pattern.search("Foo::CONST_NAME = 1")


def test_shell_state_mutation_arithmetic_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["shell"]["rules"]["state_mutation"]
    assert_redos_immune(pattern, "(" * 40000, timeout_sec=3.0)
    assert pattern.search("((i++))")


def test_apex_globals_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["apex"]["rules"]["globals"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("MyObject__c.getInstance()")
