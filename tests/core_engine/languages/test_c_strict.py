"""c strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py as part of
splitting that file into tests/core_engine/languages/, one file per language,
mirroring tests/extraction/languages/. See that file's git history for the
original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest
import re

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune, _best_of_timing  # noqa: E402 # type: ignore


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
# C: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #773, part of epic #518)
# ==============================================================================
# NOTE: filed as one of 6 new sub-issues (#773-778) after auditing and
# rejecting the epic's founding premise that C/C++/C#/COBOL/Rust/TypeScript
# already had adequate coverage -- see #518's updated "Why" section. This
# language previously had only two isolated regression tests
# (test_c_knr_ambiguity_trap covering func_start's K&R ReDoS trap, and
# test_c_pointer_ambiguity_overlap covering api/explicit_casts pointer-depth
# ReDoS), not the full per-signature template. Both are folded into this
# suite below rather than duplicated.
C_RULES = LANGUAGE_DEFINITIONS["c"]["rules"]

_C_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x > 0) {", "int x = 1;"),
    ("args", "int foo(int a, int b) {", "foo(a, b);"),
    ("structural_boundaries", "return x;", "x = 1;"),
    ("func_start", "int foo(int a) {", "if (x) {"),
    ("class_start", "struct Point {", "int x;"),
    ("safety", "assert(x > 0);", "x = 1;"),
    ("safety_bypasses", "strcpy(dst, src);", "memcpy(dst, src, n);"),
    ("high_risk_execution", 'system("ls");', 'printf("hi");'),
    ("io", 'fopen("file", "r");', "malloc(10);"),
    ("api", "extern int foo(void);", "static int foo(void);"),
    ("state_mutation", "x = 5;", "if (x == 5)"),
    ("dead_code", "// if (x) foo();", "// just a note"),
    ("doc", "/** @brief does X */", "// just a note"),
    ("test", "TEST(Foo, Bar) {", "x = 1;"),
    ("concurrency", "pthread_create(&t, NULL, f, NULL);", "x = 1;"),
    ("ui_framework", "GtkWidget *w;", "x = 1;"),
    ("globals", "int global_var = 5;", "if (x == 1)"),
    ("decorators", "[[nodiscard]] int foo();", "int foo();"),
    ("generics", "_Generic(x, int: 1, float: 2);", "int x;"),
    ("scientific", "sqrt(x);", "foo(x);"),
    ("reflection_metaprogramming", "#define MAX(a,b) ((a)>(b)?(a):(b))", "#define MAX 100"),
    ("import", "#include <stdio.h>", "#define FOO 1"),
    ("ownership", "// Author: Jane Doe", "// just a note"),
    ("planned_debt", "// TODO: fix this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "[SPEC-123]", "// just a note"),
    ("ssr_boundaries", "FCGI_Accept();", "x = 1;"),
    ("events", "epoll_wait(fd, events, 10, -1);", "x = 1;"),
    ("dependency_injection", "struct foo_ops ops;", "x = 1;"),
    ("macros", "#define FOO 1", "int x = 1;"),
    ("pointers", "int *p = &x;", "int x = 1;"),
    ("memory_alloc", "malloc(10);", "x = 1;"),
    ("inline_asm", 'asm("nop");', "x = 1;"),
    ("telemetry", 'syslog(LOG_INFO, "msg");', "x = 1;"),
    ("debug_prints", 'printf("hi");', 'syslog(LOG_INFO, "x");'),
    ("explicit_casts", "y = (int)x;", "int x;"),
    ("panics_and_aborts", "abort();", "return 0;"),
    ("thread_sleeps", "sleep(5);", "x = 1;"),
    ("bitwise_ops", "x = a << 2;", "x = a + 2;"),
    ("sync_locks", "pthread_mutex_lock(&m);", "x = 1;"),
    ("immutability_locks", "const int x = 1;", "int x = 1;"),
    ("cleanup", "fclose(f);", 'fopen(f, "r");'),
    ("encapsulation", "static int helper(void) {", "int helper(void) {"),
    ("listeners", "signal(SIGINT, handler);", "x = 1;"),
    ("test_skip", "mock();", "test_run();"),
    ("serialization_parsing", "cJSON_Parse(str);", "x = 1;"),
    ("regex_execution", "regcomp(&re, pattern, 0);", "x = 1;"),
    ("time_date_logic", "time_t t = time(NULL);", "x = 1;"),
    ("ipc_rpc_bridges", "pipe(fds);", "x = 1;"),
]


@pytest.mark.parametrize("signature,positive,negative", _C_SIMPLE_CASES)
def test_c_signature_positive_and_negative(signature, positive, negative):
    pattern = C_RULES[signature]
    assert pattern is not None, f"c's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"c {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"c {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_c_dependency_capture_extracts_include_targets():
    dep = C_RULES["_dependency_capture"]
    m = dep.search('#include "myheader.h"')
    assert m and m.group(1) == "myheader.h"

    m2 = dep.search("#include <stdio.h>")
    assert m2 and m2.group(1) == "stdio.h"

    m3 = dep.search("#embed <data.bin>")
    assert m3 and m3.group(1) == "data.bin"


def test_c_api_declspec_and_attribute_boundary_regression():
    """
    Real bug found and fixed (Rule 9): `__declspec(dllexport)` and
    `__attribute__((visibility("default")))` both end in `)` (non-word) but
    shared a trailing `\\b` with word-ending `extern` -- `\\b` right after
    can only fire if the next char is a word character, never true for the
    realistic form (whitespace/newline before the return type follows).
    """
    old_pattern = re.compile(
        r'\b(extern|__declspec\(dllexport\)|__attribute__\(\(visibility\("default"\)\)\))\b|'
        r"^[ \t]*(?!static\b)[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*(?:\[[^\]]*\])?\s*=?|"
        r"^[ \t]*[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*\s*\([^)]*\)\s*;",
        re.M,
    )
    realistic = "__declspec(dllexport) void foo();"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    api = C_RULES["api"]
    assert api.search(realistic)
    assert api.search("extern int x;"), "the already-working extern form must still work"
    assert api.search('__attribute__((visibility("default"))) void foo();')


def test_c_scientific_cblas_prefix_boundary_regression():
    """
    Real bug found and fixed (Rule 9): `cblas_` ends in `_` (a word char)
    and was clearly intended as a prefix match for any BLAS routine
    (cblas_dgemm, cblas_sgemm, ...), but shared a trailing `\\b` with
    word-ending siblings -- real usage always continues with more word
    characters right after, so the boundary could never fire (both sides
    word chars).
    """
    old_pattern = re.compile(
        r"\b(math\.h|tgmath\.h|complex\.h|cblas_|dgemm|sin|cos|tan|exp|log|sqrt|complex|I|_Float\d+|__m\d+)\b"
    )
    realistic = "cblas_dgemm(args);"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    scientific = C_RULES["scientific"]
    assert scientific.search(realistic)
    assert scientific.search("dgemm(args);"), "the already-working bare dgemm form must still work"


def test_c_test_skip_empty_call_boundary_regression():
    """
    Real bug found and fixed (Rule 10): `mock\\(`/`fake\\(` end in a literal
    `(` but shared a trailing `\\b` with word-ending siblings -- broke on
    the truly-empty-argument call form (`mock()`), where the next char
    after `(` is `)`, not a word char.
    """
    old_pattern = re.compile(r"\b(IGNORE_TEST|test\.skip|mock\(|fake\()\b")
    realistic = "mock();"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    test_skip = C_RULES["test_skip"]
    assert test_skip.search(realistic)
    assert test_skip.search("fake();")
    assert test_skip.search("IGNORE_TEST(foo)"), "the already-working IGNORE_TEST form must still work"


def test_c_spec_exposure_redos_regression():
    """
    Real bug found and fixed (Rule 14): adjacent unbounded quantifiers with
    overlapping character sets (`\\d+` next to `[^\\]]*`) -- the same ReDoS
    shape already found and fixed independently in embedded_python, css,
    tcl, matlab, scheme, typescript, and rust earlier in this epic (the 8th
    language with this exact shape). Bounded both quantifiers.
    """
    old_pattern = re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I)
    # Prove the quadratic blowup via a scale-relative comparison (not an
    # absolute wall-clock threshold, which is flaky across CI hardware of
    # varying speed): unclosed bracket with digits then padding forces the
    # engine to re-partition the trailing run between `\d+` and `[^\]]*` on
    # every failed attempt to find `]`, so a payload-size doubling should
    # cost ~4x on the quadratic OLD pattern, vs ~2x for linear.
    small_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 4000 + " " * 4000)
    large_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 8000 + " " * 8000)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: old pattern was expected to show quadratic (~4x) scaling on a payload "
        f"doubling, but only scaled {ratio:.2f}x ({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    spec_exposure = C_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + " " * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123]")
    assert spec_exposure.search("[audit]")


def test_c_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template: C-style cast syntax
    (e.g. `(int*)`) can overlap with pointer-asterisk repetition. Verified
    no false collision -- a bare cast without a pointer declaration doesn't
    also fire `pointers`, and a line with both a real pointer declaration
    and a cast legitimately fires both (intentional dual classification,
    not a bug).
    """
    explicit_casts = C_RULES["explicit_casts"]
    pointers = C_RULES["pointers"]

    bare_cast = "double val = (double)x;"
    assert explicit_casts.search(bare_cast)
    assert not pointers.search(bare_cast)

    cast_and_ptr = "int *y = (int*)malloc(10);"
    assert explicit_casts.search(cast_and_ptr)
    assert pointers.search(cast_and_ptr), "a real pointer declaration alongside a cast should still fire pointers"


def test_c_func_start_vs_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C++:
    a multi-line #define spiral hallucinating a function match). Unlike
    C++'s func_start (which allows a bare constructor-style identifier
    with no preceding return type, and so can hallucinate a match by
    skipping the macro run to reach a later bare `myFunc() {`), C's
    func_start always requires an explicit return-type token immediately
    before the identifier -- so a dangling return type followed by a long
    run of #define lines can never bridge across them to a hallucinated
    match; it correctly finds nothing at all.
    """
    func_start = C_RULES["func_start"]
    macros = C_RULES["macros"]

    poison = "int\n" + "#define FOO 1\n" * 1000 + "myFunc() {"
    assert_redos_immune(func_start, poison, timeout_sec=3.0)
    matches = list(func_start.finditer(poison))
    assert len(matches) == 0, "C's func_start requires a return type -- a bare 'myFunc() {' must never match"
    assert macros.search("#define FOO 1")

    # A real return type immediately preceding the identifier still matches.
    valid = "int myFunc() {"
    matches2 = list(func_start.finditer(valid))
    assert len(matches2) == 1
    assert matches2[0].group(1) == "myFunc"


def test_c_intentional_double_classification_sweep():
    """
    Ambiguity sweep finding: several C constructs legitimately fire two
    signatures representing different perspectives on the same underlying
    action -- intentional, not false collisions:
    - `free(p)` -> cleanup (resource release) + memory_alloc (deallocation)
    - `mmap(...)` -> memory_alloc + ipc_rpc_bridges (mmap is both a raw
      allocation and a common shared-memory/IPC primitive)
    - `socket(...)` -> io + ipc_rpc_bridges
    - `fork()` -> high_risk_execution (process-killing context switch) +
      ipc_rpc_bridges (process creation for IPC)
    - `close(fd)` -> io + cleanup
    - `alloca(10)` -> safety_bypasses (unchecked stack allocation) +
      memory_alloc
    - `pthread_mutex_lock(&m)` -> concurrency + sync_locks (both explicitly
      define this as their own primitive)
    - `restrict`/`alignas(...)` -> structural_boundaries (own keyword list)
      + immutability_locks (own keyword list) -- both rules intentionally
      claim these qualifiers
    - `goto end;` -> branch (control-flow jump) + reflection_metaprogramming
      (unstructured jump signal)
    - `struct foo_ops ops;` -> class_start (any struct declaration) +
      dependency_injection (the `_ops` vtable-style suffix)
    """
    free_call = "free(p);"
    assert C_RULES["cleanup"].search(free_call)
    assert C_RULES["memory_alloc"].search(free_call)

    mmap_call = "mmap(NULL, len, PROT_READ, 0, fd, 0);"
    assert C_RULES["memory_alloc"].search(mmap_call)
    assert C_RULES["ipc_rpc_bridges"].search(mmap_call)

    socket_call = "socket(AF_INET, SOCK_STREAM, 0);"
    assert C_RULES["io"].search(socket_call)
    assert C_RULES["ipc_rpc_bridges"].search(socket_call)

    fork_call = "fork();"
    assert C_RULES["high_risk_execution"].search(fork_call)
    assert C_RULES["ipc_rpc_bridges"].search(fork_call)

    close_call = "close(fd);"
    assert C_RULES["io"].search(close_call)
    assert C_RULES["cleanup"].search(close_call)

    alloca_call = "alloca(10);"
    assert C_RULES["safety_bypasses"].search(alloca_call)
    assert C_RULES["memory_alloc"].search(alloca_call)

    mutex_call = "pthread_mutex_lock(&m);"
    assert C_RULES["concurrency"].search(mutex_call)
    assert C_RULES["sync_locks"].search(mutex_call)

    assert C_RULES["structural_boundaries"].search("restrict")
    assert C_RULES["immutability_locks"].search("restrict")
    assert C_RULES["structural_boundaries"].search("alignas(16)")
    assert C_RULES["immutability_locks"].search("alignas(16)")

    goto_stmt = "goto end;"
    assert C_RULES["branch"].search(goto_stmt)
    assert C_RULES["reflection_metaprogramming"].search(goto_stmt)

    ops_struct = "struct foo_ops ops;"
    assert C_RULES["class_start"].search(ops_struct)
    assert C_RULES["dependency_injection"].search(ops_struct)


def test_c_knr_ambiguity_trap_2():
    """
    Proves the C function spawner does not spiral into a permutation death
    loop when encountering the MS-DOS BEGIN macro or massive parameter
    gaps. Pre-existing regression test, folded into this suite unchanged.
    """
    c_func = C_RULES["func_start"]

    poison_knr = "int legacy_func(a, b, c) \n" + "    int a; int b; int c;\n" * 50 + "    INVALID_MACRO"
    assert_redos_immune(c_func, poison_knr, timeout_sec=3.0)

    valid_knr = "int legacy_func(a) \n    int a; \n BEGIN \n"
    matches = list(c_func.finditer(valid_knr))
    assert len(matches) == 1
    assert matches[0].group(1) == "legacy_func"


def test_c_pointer_ambiguity_overlap_2():
    r"""
    Proves that O(1) alternation `(?:\s*[*&]+\s*|\s+)` successfully prevents
    exponential evaluation on massive strings of pointer asterisks.
    Pre-existing regression test, folded into this suite unchanged.
    """
    c_api = C_RULES["api"]
    c_cast = C_RULES["explicit_casts"]

    poison_cast = "( int " + "* " * 200 + ") "
    poison_api = "extern int " + "* " * 200 + " var"

    assert_redos_immune(c_cast, poison_cast)
    assert_redos_immune(c_api, poison_api)


def test_c_redos_immunity_sweep():
    """
    ReDoS immunity sweep across c's remaining rules with unbounded-looking
    quantifiers, verified via a systematic scaling sweep (n=2000/4000/8000/
    16000/32000) before writing this test.
    """
    assert_redos_immune(C_RULES["args"], "int foo(" + "int a," * 6000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["args"], "int foo(int (*cb)(" + "a," * 16000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["func_start"], "int foo" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["func_start"], "__attribute__((" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["class_start"], "struct " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["decorators"], "[[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["generics"], "_Generic(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["explicit_casts"], "(int" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["_dependency_capture"], "#include <" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["import"], "#include <" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["inline_asm"], "asm" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(C_RULES["globals"], "a" * 100000 + " = 1;", timeout_sec=3.0)
    assert_redos_immune(C_RULES["pointers"], "&" + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert C_RULES["func_start"].search("int foo(int a) {")
    assert C_RULES["class_start"].search("struct Point {")
    assert C_RULES["explicit_casts"].search("y = (int)x;")
