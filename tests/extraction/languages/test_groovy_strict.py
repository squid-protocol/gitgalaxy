"""groovy strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import _best_of_timing, assert_redos_immune  # noqa: E402 # type: ignore

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
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


def test_groovy_args_closure_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["groovy"]["rules"]["args"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("x -> x + 1")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
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


def test_groovy_at_prefixed_annotations_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["groovy"]["rules"]
    assert r["ssr_boundaries"].search("@ResponseBody\ndef foo() {}")
    assert r["events"].search("@EventListener\ndef onEvent() {}")
    assert r["dependency_injection"].search("@Autowired\nFooService foo")
    assert r["immutability_locks"].search("@Immutable\nclass Point {}")


# ==============================================================================
# GROOVY: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #584)
# ==============================================================================
GROOVY_RULES = LANGUAGE_DEFINITIONS["groovy"]["rules"]

_GROOVY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "if (x > 0) { return x } else { return -x }", "String x = 1"),
    ("args", "def calculate(int x, int y = Math.max(3, 4)) {", "String x = 1"),
    ("structural_boundaries", "class Foo {}", "if (x > 0) { println x }"),
    ("func_start", "void plainMethod(String x) {", "if (x) {"),
    ("class_start", "class Foo extends Bar {", "def foo() {}"),
    # --- PHASE 2 ---
    ("safety", "try { risky() } catch (Exception e) { }", "String x = 1"),
    ("safety_bypasses", "def x = null", "def x = 5"),
    ("high_risk_execution", "System.exit(1)", "println 'hi'"),
    ("io", "def f = new File('data.txt')", "String x = 1"),
    ("api", "@RestController\nclass FooController {}", "class Foo {}"),
    ("state_mutation", "count = count + 1", "count == expected"),
    ("dead_code", "// def oldMethod() {}", "// just a comment"),
    ("doc", "/**\n * @param x the value\n */", "// just a comment"),
    ("test", "@Test\nvoid testFoo() { assert x == 1 }", "String x = 1"),
    # --- PHASE 3 ---
    ("concurrency", "def t = new Thread({ doWork() })", "String x = 1"),
    ("ui_framework", "def frame = new JFrame('Title')", "String x = 1"),
    ("closures", "list.each { it * 2 }", "String x = 1"),
    ("globals", "def home = System.getProperty('user.home')", "String x = 1"),
    ("decorators", "@CompileStatic\nclass Foo {}", "class Foo {}"),
    ("generics", "Map<String, List<Id>> data", "String data"),
    ("comprehensions", "list.collect { it.toUpperCase() }", "String x = 1"),
    ("scientific", "def r = Math.sqrt(4)", "String x = 1"),
    ("reflection_metaprogramming", "foo.metaClass.bar = { -> 42 }", "String x = 1"),
    ("import", "import com.example.Foo", "String x = 1"),
    ("ownership", "// @author Jane Doe", "// regular comment"),
    # --- PHASE 4 ---
    ("planned_debt", "// TODO: refactor this", "// regular comment"),
    ("fragile_debt", "// HACK: workaround for build tool bug", "// regular comment"),
    ("spec_exposure", "// [SPEC-123] audit trail", "// regular comment"),
    ("ssr_boundaries", "@ResponseBody\ndef foo() {}", "def foo() {}"),
    ("events", "@EventListener\ndef onFoo() {}", "def foo() {}"),
    ("dependency_injection", "dependencies {\n    implementation 'foo'\n}", "String x = 1"),
    # --- PHASE 5 ---
    ("telemetry", "logger.info('starting')", "println 'starting'"),
    ("debug_prints", "println 'debug value: ' + x", "logger.info('x')"),
    ("explicit_casts", "def x = (int) y", "def x = y"),
    ("panics_and_aborts", "throw new RuntimeException('bad')", "return x"),
    ("thread_sleeps", "Thread.sleep(1000)", "String x = 1"),
    ("bitwise_ops", "def flags = mask ^ other", "def flags = mask && other"),
    ("sync_locks", "synchronized(lock) { doWork() }", "String x = 1"),
    ("immutability_locks", "final String name = 'x'", "String name = 'x'"),
    ("cleanup", "connection.close()", "String x = 1"),
    ("encapsulation", "private String name", "String name"),
    ("listeners", "button.addListener(handler)", "String x = 1"),
    ("test_skip", "@Ignore\nvoid testFoo() {}", "void testFoo() {}"),
]


@pytest.mark.parametrize("signature,positive,negative", _GROOVY_SIMPLE_CASES)
def test_groovy_signature_positive_and_negative(signature, positive, negative):
    pattern = GROOVY_RULES[signature]
    assert pattern is not None, f"groovy's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"groovy {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
        )

_GROOVY_DEEP_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # branch: ternary, Elvis, safe navigation, ensure map literals are ignored
    ("branch", "def result = (x > 5) ? 'high' : 'low'", "def map = [key: 'value']"),
    ("branch", "def name = user?.name", "foo(a: 1)"),
    ("branch", "def a = b ?: c", "String type"),
    ("branch", "switch(x) { case 1: break }", "def list = [1, 2]"),
    ("branch", "for (String s in list) {", "def map = [a: 1]"),

    # args: complex generic types, string method names, intermixed annotations
    ("args", "public static final Map<String, List<Tuple2<Integer, String>>> complexArgMethod(int x, List<String> y) {", "if (Map<String) {"),
    ("args", "def \"a method with spaces in its name\"(int x) {", "def \"not a method\" = 1"),
    ("args", "public @CompileStatic final void foo(int x) {", "if (x > 0) {"),
    ("args", "def foo(int x, \n String y) {", "while (x) {"),
    ("args", "abstract def \"test case\"(String input)", "synchronized(lock) {"),

    # func_start: generics, string names, intermixed annotations
    ("func_start", "public <T extends Number> void process(T t) {", "class List<T> {"),
    ("func_start", "def \"a method with spaces\"() {", "String x = 1"),
    ("func_start", "@Test\n@Timeout(value = 1)\ndef testMethod() {", "class Foo {"),
    ("func_start", "public @CompileStatic def myMethod() {", "def var = 1"),
    ("func_start", "abstract Map<String, Integer> calculateTotals(List<Item> items)", "if (items) {"),

    # class_start: sealed, non-sealed, intermixed annotations
    ("class_start", "abstract sealed class Shape permits Circle, Square {", "def abstract() {}"),
    ("class_start", "final @CompileStatic class Optimizer {", "def foo() {}"),
    ("class_start", "@Entity\npublic class User {", "def class_name = 1"),
    ("class_start", "public non-sealed class MyClass {", "public void method() {}"),
    ("class_start", "protected @Deprecated abstract sealed class Internal {", "String x = 1"),

    # structural_boundaries: includes sealed, permits, non-sealed
    ("structural_boundaries", "sealed class MyClass {", "int x = 1"),
    ("structural_boundaries", "abstract sealed class Shape permits Circle, Square {", "if (Circle) {"),
    ("structural_boundaries", "public non-sealed class MyClass {", "int y = 2"),
    ("structural_boundaries", "package com.example.foo", "int package_name = 1"),
    ("structural_boundaries", "import static org.junit.Assert.*", "int import_value = 2"),
]

@pytest.mark.parametrize("signature,positive,negative", _GROOVY_DEEP_CASES)
def test_groovy_signature_deep_positive_and_negative(signature, positive, negative):
    pattern = GROOVY_RULES[signature]
    assert pattern is not None, f"groovy's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"groovy {signature!r} failed to match deep positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), (
            f"groovy {signature!r} incorrectly matched an excluded/negative deep case: {negative!r}"
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

    # _best_of_timing (min-of-5) instead of a single perf_counter() sample
    # per size -- see the explicit_casts test above for why.
    timings = [_best_of_timing(pattern, "{" + " " * n) for n in (2000, 4000, 8000, 16000, 32000)]

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

    # _best_of_timing (min-of-5) instead of a single perf_counter() sample
    # per size -- see explicit_casts's own test earlier in this file for
    # why (this exact test failed in CI this way on macos-3.10 during
    # #770's PR: [0.0007, 0.0014, 0.0036, 0.0064, 0.0202]s, tripping the
    # 0.02s floor on the last size by a hair under runner contention).
    timings = [_best_of_timing(pattern, "[SPEC-" + "1" * n) for n in (2000, 4000, 8000, 16000, 32000)]

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


def test_groovy_func_start_markup_builder_dsl_call_false_positive_regression():
    """
    #2530: func_start's zero-prefix branch (needed to match a real bare
    constructor, `MyClass(String arg) {`) is syntactically indistinguishable
    from Groovy's MarkupBuilder/NodeBuilder DSL idiom -- a method call with
    a named-argument map plus a trailing closure (`div(class: "x") { ... }`,
    `button(name: "clear", type: "submit") { ... }`). Confirmed against the
    `language-crucible` `jenkins_view_groovy/` corpus (29 files): 44 of the
    57 misdetected "functions" in that folder were this exact shape.

    Fix: a real Groovy declaration's parameter list can never contain a
    `key:` token (that syntax is call-site named-argument sugar only), so
    branch 2 now rejects a candidate whose parenthesized argument list
    contains an identifier immediately followed by `:` (no intervening
    whitespace, to tell it apart from a ternary's `cond ? a : b`, which
    conventionally has a space before the colon).

    Verified via a full corpus differential scan (galaxyscope --db-only,
    201 files, 1135 -> 1092 total functions): all 44 removed matches were
    in `jenkins_view_groovy/`, zero removals anywhere else in the corpus --
    no legitimate bare constructor lost recall. `div`/`section`/`ul`/`li`/
    `stage`(single-positional-arg Jenkins Pipeline steps like `stage('x')
    { }`/`node('x') { }`/`dir(x) { }`, which have no named-arg map at all)
    remain a known, unaddressed residual -- same class the issue explicitly
    scoped out (a curated tag-name denylist is fragile/incomplete by
    construction).
    """
    func_start = GROOVY_RULES["func_start"]

    dsl_builder_calls = [
        'div(class: "empty-state-block") {',
        'form(method: "post", name: "clear", action: "x") {',
        'button(name: "clear", type: "submit", class: "jenkins-button") {',
        "timeout(time: 6, unit: 'HOURS') {",
        "withChecks(name: 'Tests', includeStage: true) {",
        "a(href: \"newJob\", class: \"content-block__link\") {",
    ]
    for snippet in dsl_builder_calls:
        assert not func_start.search(snippet), f"func_start incorrectly matched a DSL builder call: {snippet!r}"

    # Real bare constructors/methods -- including ones that take a Map
    # literal or a colon-containing default -- must still match.
    assert func_start.search("MyClass(String constructorArg) {")
    assert func_start.search("MyClass(Map config = [:]) {")
    match = func_start.search("MyClass(String x = cond ? a : b) {")
    assert match and match.group(0).strip().startswith("MyClass"), (
        "func_start should still match a bare constructor whose default value is a ternary "
        "(space-before-colon), only the tight `key:` named-arg shape is excluded"
    )
