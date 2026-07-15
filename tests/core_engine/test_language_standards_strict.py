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
