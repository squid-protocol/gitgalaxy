"""dart strict structural-signature coverage.

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


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
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


def test_dart_router_boundary_regression():
    assert LANGUAGE_DEFINITIONS["dart"]["rules"]["ssr_boundaries"].search("final app = Router();")
