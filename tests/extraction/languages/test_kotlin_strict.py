"""kotlin strict structural-signature coverage.

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

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
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


# ==============================================================================
# KOTLIN: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #592)
# ==============================================================================
KOTLIN_RULES = LANGUAGE_DEFINITIONS["kotlin"]["rules"]

_KOTLIN_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x) { return }", "val ifBlock = IfBlock()"),
    ("args", "fun foo(x: Int) {", "val result = foo(x, y)"),
    ("func_start", "fun foo() {", "val result = foo()"),
    ("class_start", "class Foo {", "val foo = Foo()"),
    ("safety", "val x = require(x > 0)", "val isValid = true"),
    ("safety_bypasses", "val x = value!!", "val x = value?.let { it }"),
    ("high_risk_execution", "exitProcess(1)", "Runtime.version()"),
    ("io", "val f = File(path)", "val hash = FileUtils.hash(path)"),
    ("api", "public fun foo() {}", "private fun foo() {}"),
    ("state_mutation", "var count = 0", "val count = 0"),
    ("dead_code", "// fun foo() {}", "// this is deprecated, remove later"),
    ("doc", "/** A doc comment */", "/* internal note, not exported */"),
    ("test", "assertEquals(a, b)", "computeTotal(a, b)"),
    ("concurrency", "launch { compute() }", "fun compute() { return result }"),
    ("ui_framework", "@Composable\nfun Foo() {}", "fun calculateTotal(items: List<Item>): Double {"),
    ("closures", "{ x -> x * 2 }", '{ println("hi") }'),
    ("globals", "companion object", 'val userName = "joe"'),
    ("decorators", "@JvmStatic", "// uses JvmStatic annotation"),
    ("generics", "fun <T> foo(x: T) {}", "if (a < b) return"),
    ("comprehensions", "list.map { it * 2 }", "list.sortedBy { it.name }"),
    ("scientific", "kotlin.math.sqrt(4.0)", "val distance = calculateDistance(a, b)"),
    ("reflection_metaprogramming", "Foo::class", "val instance = Foo()"),
    ("import", "import kotlin.collections.List", "// import kotlin.collections.List (removed)"),
    ("ownership", "@author Jane Doe", "// Reviewed by: Jane Doe"),
    ("planned_debt", "// TODO: refactor", "// DONE: refactored, no further action"),
    ("fragile_debt", "// HACK: workaround", "// NOTE: applied a clean, permanent fix"),
    ("spec_exposure", "// [SPEC-123] implements the contract", "// [TICKET-456] fix later"),
    ("ssr_boundaries", "call.respond(HttpStatusCode.OK)", "call.enqueue(callback)"),
    ("events", "flow.collect { value -> use(value) }", "flow.count()"),
    ("dependency_injection", "@Inject\nlateinit var foo: Foo", "val item = repository.getById(id)"),
    ("macros", '@Suppress("unused")', "@JvmStatic"),
    ("pointers", "val p: CPointer<IntVar>", "val p: IntArray = IntArray(5)"),
    ("memory_alloc", "memScoped { }", "val list = mutableListOf<Int>()"),
    ("telemetry", 'Log.i("tag", "message")', "Log.getName()"),
    ("debug_prints", 'println("debug")', "printer.printLabel()"),
    ("explicit_casts", "x as String", 'val note = "referred to as legacy code"'),
    ("panics_and_aborts", 'throw RuntimeException("err")', "val result = compute()"),
    ("thread_sleeps", "delay(1000)", "Thread.currentThread().name"),
    ("bitwise_ops", "a xor b", "val valid = a && b"),
    ("sync_locks", "val mutex = Mutex()", "val lockPosition = getDoorState()"),
    ("immutability_locks", "val x = 5", "var x = 5"),
    ("cleanup", "conn.close()", "conn.closeQuietly()"),
    ("encapsulation", "private val x = 5", "public val x = 5"),
    ("listeners", "button.setOnClickListener { doThing() }", "button.performClick()"),
    ("test_skip", "@Ignore", "@Test"),
    ("serialization_parsing", "Json.decodeFromString(str)", "val json = Json { prettyPrint = true }"),
    ("regex_execution", "Regex(pattern)", "val regexLibrary = RegexUtils.compile(pattern)"),
    ("time_date_logic", "Instant.now()", 'val timestamp = Instant.parse("2024-01-01T00:00:00Z")'),
    ("ipc_rpc_bridges", "val intent = Intent(this, Foo::class.java)", "val intentFilter = IntentFilter()"),
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


def test_kotlin_redos_immunity_sweep():
    """
    Issue #1070: kotlin had zero per-language ReDoS regression coverage.
    `args`/`func_start` both use the 1-level-nesting-trick paren stepper
    plus a generic-parameter stepper `(?:[^<>]|<[^<>]*>)*`, and
    `decorators` has an unbounded dotted-chain repeat -- the "nested
    quantifiers" and "alternation" shapes epic #518 flagged repeatedly.
    Diagnosed clean via `check_redos_scaling` (consistent ~2x-per-doubling
    ratios) before writing these as permanent regression pins.
    """
    assert_redos_immune(KOTLIN_RULES["args"], "fun foo(" + "(" * 100000, timeout_sec=3.0)
    assert_redos_immune(KOTLIN_RULES["args"], "fun foo<" + "<" * 100000, timeout_sec=3.0)
    assert_redos_immune(KOTLIN_RULES["func_start"], "fun foo<" + "<" * 100000, timeout_sec=3.0)
    assert_redos_immune(KOTLIN_RULES["class_start"], "@a(" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(KOTLIN_RULES["decorators"], "@a" + ".a" * 50000, timeout_sec=3.0)
