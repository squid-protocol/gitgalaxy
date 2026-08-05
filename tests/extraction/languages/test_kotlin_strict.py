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
