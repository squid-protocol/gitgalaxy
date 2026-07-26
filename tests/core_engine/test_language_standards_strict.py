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
