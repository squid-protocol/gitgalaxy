"""php strict structural-signature coverage.

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


def test_php_state_mutation_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["php"]["rules"]["state_mutation"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("$obj->prop = 1")
    assert pattern.search("Foo::CONST_NAME = 1")


# ==============================================================================
# PHP: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #603)
# ==============================================================================
PHP_RULES = LANGUAGE_DEFINITIONS["php"]["rules"]

_PHP_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if ($x) {", "$total = $a + $b;"),
    ("args", "function foo($x) {", "foo($x);"),
    ("structural_boundaries", "namespace App;", "$x = compute();"),
    ("func_start", "function foo() {", "foo();"),
    ("class_start", "class Foo {", "$foo = new Foo();"),
    ("safety", "try { risky(); } catch (Exception $e) {}", "if ($x !== null) { doThing(); }"),
    ("safety_bypasses", "@$x;", "if ($x === null) {}"),
    ("high_risk_execution", 'exec("ls");', "execute($cmd);"),
    ("io", 'fopen($path, "r");', "file_exists($path);"),
    ("api", "public function foo() {}", "private function foo() {}"),
    ("state_mutation", "$x = 5;", "return $x;"),
    ("dead_code", "// function foo() {}", "// just a note"),
    ("doc", "/** A doc comment */", "/* internal note, not exported */"),
    ("test", "assertEquals($a, $b);", "compute($a, $b);"),
    ("concurrency", "Fiber::suspend();", "pcntl_wait($status);"),
    ("ui_framework", 'view("index");', "viewportSettings();"),
    ("closures", "function() use ($x) {", "function foo() {"),
    ("globals", '$_SERVER["HOST"]', '$_POST["data"]'),
    ("decorators", '#[Route("/foo")]', "$config['route'] = '/foo';"),
    ("generics", "@template T", "@param T $value"),
    ("comprehensions", "array_map($fn, $arr);", "array_merge($a, $b);"),
    ("scientific", "sqrt(4);", "$x = $y ** 2;"),
    ("reflection_metaprogramming", "__get($name)", "__construct($name)"),
    ("import", 'require "foo.php";', "$required = true;"),
    ("ownership", "@author Jane Doe", "@since 2.0"),
    ("planned_debt", "// TODO: refactor", "// DONE: refactored, no further action"),
    ("fragile_debt", "// HACK: workaround", "// NOTE: applied a clean, permanent fix"),
    ("spec_exposure", "// [SPEC-123]", "// [TICKET-456] fix later"),
    ("ssr_boundaries", "new JsonResponse($data);", "new ArrayObject($data);"),
    ("events", "dispatchEvent($event);", "sendEvent($event);"),
    ("dependency_injection", "app();", "application();"),
    ("macros", "Macroable;", "trait Foo {}"),
    ("pointers", 'FFI::cast("int", $x);', "FFI::free($ptr);"),
    ("memory_alloc", "new Foo();", "clone $foo;"),
    ("telemetry", "Log::info('msg');", "Log::channel('slack');"),
    ("debug_prints", "echo $x;", "log($x);"),
    ("explicit_casts", "(int) $x;", "($x + 1) * 2;"),
    ("panics_and_aborts", "throw new Exception();", "return new Exception();"),
    ("thread_sleeps", "sleep(1);", "sleepMode(true);"),
    ("bitwise_ops", "$a & $b;", "$a && $b;"),
    ("sync_locks", "flock($f, LOCK_EX);", "flush($f);"),
    ("immutability_locks", "const FOO = 1;", "static $foo = 1;"),
    ("cleanup", "unset($x);", "$unsetFlag = true;"),
    ("encapsulation", "private $x;", "public $x;"),
    ("listeners", "addEventListener($cb);", "removeEventListener($cb);"),
    ("test_skip", 'markTestSkipped("reason");', "markTestIncomplete('reason');"),
    ("serialization_parsing", "json_decode($str);", "json_last_error();"),
    ("regex_execution", "preg_match($pattern, $str);", "preg_quote($str);"),
    ("time_date_logic", 'strtotime("now");', "date_diff($a, $b);"),
    ("ipc_rpc_bridges", 'shell_exec("ls");', "curl_init();"),
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


def test_php_state_mutation_redos_immunity_2():
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
