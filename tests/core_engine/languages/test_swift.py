"""swift strict structural-signature coverage.

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


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
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


def test_swift_at_prefixed_attributes_leading_boundary_regression():
    r = LANGUAGE_DEFINITIONS["swift"]["rules"]
    assert r["api"].search("@objc func foo() {}")
    assert r["api"].search("@IBOutlet weak var label: UILabel!")
    assert r["ui_framework"].search("@State private var count = 0")
    assert r["reflection_metaprogramming"].search("@objc dynamic func foo() {}")
    assert r["events"].search("@Published var value = 0")
    assert r["dependency_injection"].search("@Inject var service: FooService")


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


def test_swift_empty_parens_calls_boundary_regression():
    r = LANGUAGE_DEFINITIONS["swift"]["rules"]
    assert r["memory_alloc"].search("ptr.deallocate()")
    assert r["memory_alloc"].search("let p = UnsafeMutablePointer<Int>.allocate(capacity: 1)")
    assert r["time_date_logic"].search("let now = Date()")
    assert r["ipc_rpc_bridges"].search("let p = Process()")


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
