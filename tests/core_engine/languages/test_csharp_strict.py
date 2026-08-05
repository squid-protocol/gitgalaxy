"""csharp strict structural-signature coverage.

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


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
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


def test_csharp_args_lambda_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["csharp"]["rules"]["args"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("x => x + 1")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/core_engine/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
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


def test_csharp_should_and_wait_boundary_regression():
    r = LANGUAGE_DEFINITIONS["csharp"]["rules"]
    assert r["test"].search("result.Should().Be(x);")
    assert r["thread_sleeps"].search("task.Wait();")
    assert not r["thread_sleeps"].search("myWait();"), "thread_sleeps incorrectly matched a substring identifier"


# ==============================================================================
# CSHARP: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #775, part of epic #518)
# ==============================================================================
# NOTE: filed as one of 6 new sub-issues (#773-778) after auditing and
# rejecting the epic's founding premise that C/C++/C#/COBOL/Rust/TypeScript
# already had adequate coverage -- see #518's updated "Why" section. This
# language previously had only four isolated regression tests
# (test_csharp_iron_wall_redos covering func_start's multi-line-generic
# ReDoS, test_csharp_args_lambda_redos_immunity, test_csharp_events_plus_
# minus_equals_operators, and test_csharp_should_and_wait_boundary_
# regression), not the full per-signature template. All four are folded
# into this suite below rather than duplicated.
#
# Separately filed as issue #789 (architectural, not fixed here, matching
# this epic's established pattern of scoping pipeline-level findings
# separately from per-language regex correctness): csharp's `func_start`
# regex intentionally stops at the opening `(` and relies on downstream
# `detector.py` brace-search to find the real function body -- this means
# expression-bodied methods (`=>`, no `{` at all) are never counted as
# functions, and a bare call statement with no enclosing scope (C# 9+
# top-level statements) can be hallucinated as a function. The `func_start`
# regex tests below verify its actual, currently observed `.search()`/
# `.finditer()` behavior (which does correctly anchor on real brace-bodied
# method signatures), not the full pipeline's behavior.
CSHARP_RULES = LANGUAGE_DEFINITIONS["csharp"]["rules"]

_CSHARP_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x > 0) {", "int x = 1;"),
    ("args", "public Task<int> Foo(int a, int b) {", "Foo(a, b);"),
    ("structural_boundaries", "return x;", "x = 1;"),
    ("func_start", "public int Foo(int a) {", "if (x) {"),
    ("class_start", "public class Foo {", "int x;"),
    ("safety", "try { f(); } catch (Exception e) { g(); }", "x = 1;"),
    ("safety_bypasses", "var x = obj!.Value;", "var x = obj.Value;"),
    ("high_risk_execution", "Environment.Exit(1);", 'Console.WriteLine("hi");'),
    ("io", "File.ReadAllText(path);", "int x = 1;"),
    ("api", "public void Foo() {}", "private void Foo() {}"),
    ("state_mutation", "myField = 5;", "if (x == 5)"),
    ("dead_code", "// if (x) foo();", "// just a note"),
    ("doc", "/// <summary>Does X</summary>", "// just a note"),
    ("test", "[Fact]\npublic void Foo() {}", "x = 1;"),
    ("concurrency", "await Task.Run(() => f());", "x = 1;"),
    ("ui_framework", "public class Home : ComponentBase {}", "x = 1;"),
    ("closures", "x => x + 1", "int x;"),
    ("globals", "public static readonly int MAX_VALUE = 100;", "int x = 1;"),
    ("decorators", "[Obsolete]\npublic void Foo() {}", "public void Foo() {}"),
    ("generics", "List<Foo> items;", "int x;"),
    ("comprehensions", "items.Where(x => x > 0);", "x = 1;"),
    ("scientific", "Math.Sqrt(x);", "Foo(x);"),
    ("reflection_metaprogramming", 'MethodInfo m = typeof(Foo).GetMethod("Bar");', "x = 1;"),
    ("import", "using System.Collections.Generic;", "int x = 1;"),
    ("ownership", "// Author: Jane Doe", "// just a note"),
    ("planned_debt", "// TODO: fix this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "[SPEC-123]", "// just a note"),
    ("ssr_boundaries", '@page "/counter"', "x = 1;"),
    ("events", "MyEvent += Handler;", "x = 1;"),
    ("dependency_injection", "services.AddScoped<IFoo, Foo>();", "x = 1;"),
    ("macros", "#define FOO", "int x = 1;"),
    ("pointers", "IntPtr ptr = IntPtr.Zero;", "int x = 1;"),
    ("memory_alloc", "Marshal.AllocHGlobal(100);", "x = 1;"),
    ("telemetry", '_logger.LogInformation("started");', "x = 1;"),
    ("debug_prints", 'Console.WriteLine("debug");', "x = 1;"),
    ("explicit_casts", "var x = (int)y;", "int x;"),
    ("panics_and_aborts", 'throw new Exception("bad");', "return 0;"),
    ("thread_sleeps", "Thread.Sleep(1000);", "x = 1;"),
    ("bitwise_ops", "x = a << 2;", "x = a + 2;"),
    ("sync_locks", "lock (obj) { f(); }", "x = 1;"),
    ("immutability_locks", "const int x = 1;", "int x = 1;"),
    ("cleanup", "conn.Dispose();", "conn.Open();"),
    ("encapsulation", "private int x;", "public int x;"),
    ("listeners", "button.Click += OnClick;", "x = 1;"),
    ("test_skip", "[Ignore]\npublic void Foo() {}", "public void Foo() {}"),
    ("serialization_parsing", "JsonSerializer.Deserialize<Foo>(json);", "x = 1;"),
    ("regex_execution", "Regex.IsMatch(input, pattern);", "x = 1;"),
    ("time_date_logic", "DateTime.Now;", "x = 1;"),
    ("ipc_rpc_bridges", 'Process.Start("foo");', "x = 1;"),
]


@pytest.mark.parametrize("signature,positive,negative", _CSHARP_SIMPLE_CASES)
def test_csharp_signature_positive_and_negative(signature, positive, negative):
    pattern = CSHARP_RULES[signature]
    assert pattern is not None, f"csharp's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"csharp {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"csharp {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_csharp_dependency_capture_extracts_using_targets():
    dep = CSHARP_RULES["_dependency_capture"]
    m = dep.search("using System.Collections.Generic;")
    assert m and m.group(1) == "System.Collections.Generic"

    m2 = dep.search("global using static System.Math;")
    assert m2 and m2.group(1) == "System.Math"


def test_csharp_state_mutation_multiline_regression():
    """
    Real bug found and fixed (Rule 13): `^[ \\t]*(?:this\\.)?\\w+[ \\t]*=`
    requires `re.M` for `^` to anchor per-line -- without it, `^` only
    matches true string-start, so this alternative (the plain `field =
    value;` assignment form, arguably the most common state-mutation shape
    in any real C# file) could only ever fire if the assignment happened
    to be the first line of the entire scanned content.
    """
    old_pattern = re.compile(
        r"\b(set|field)\s*[{;]|volatile|ref\s|out\s|^[ \t]*(?:this\.)?\w+[ \t]*=|(?:\w+\.)?(?:Add|Remove|Clear|Insert|Push|Pop|Update)\s*\("
    )
    realistic = "public class Foo {\n    myField = 5;\n}"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    state_mutation = CSHARP_RULES["state_mutation"]
    assert state_mutation.search(realistic)
    assert state_mutation.search("myField = 5;"), "the already-working first-line form must still work"


def test_csharp_dead_code_block_comment_completeness_regression():
    """
    Real bug found and fixed (Rule 12): only checked `//` line comments,
    entirely missing `/* */` block comments despite csharp being a
    `standard_block` language where both styles are equally idiomatic.
    """
    old_pattern = re.compile(
        r"//[ \t]*(?:public|private|protected|internal|class|void|if|for|foreach|while|return|using)\b"
    )
    assert not old_pattern.search("/* if (x) foo(); */"), "sanity check: bug must reproduce"

    dead_code = CSHARP_RULES["dead_code"]
    assert dead_code.search("/* if (x) foo(); */")
    assert dead_code.search("// if (x) foo();"), "the already-working line-comment form must still work"


def test_csharp_globals_static_field_boundary_regression():
    """
    Real bug found and fixed (Rule 9): the `public static ... = `
    alternative ends in `=` (non-word) but shared a trailing `\\b` with
    word-ending siblings -- only fired when the assignment had zero
    whitespace around `=` (`X=5;`), breaking on the idiomatic spaced form
    (`MAX_VALUE = 100;`) that's the dominant real C# style.
    """
    old_pattern = re.compile(
        r"\b(ConfigurationManager|Environment\.|public\s+static\s+(?:readonly[ \t]+)?[\w<>]+\s+[A-Z_0-9]+[ \t]*=|AsyncLocal)\b|\[ThreadStatic\]"
    )
    realistic = "public static readonly int MAX_VALUE = 100;"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    globals_rule = CSHARP_RULES["globals"]
    assert globals_rule.search(realistic)
    assert globals_rule.search("public static int X=5;"), "the already-working zero-space form must still work"
    assert globals_rule.search("Environment.MachineName;"), "the already-working Environment. form must still work"


def test_csharp_cleanup_and_listeners_pascal_case_regression():
    """
    Real bug found and fixed (grammar mismatch): `cleanup`'s
    `dispose(`/`close(` and `listeners`' `subscribe`/`on` were entirely
    case-sensitive lowercase, but idiomatic C# always PascalCases public
    members -- `.Dispose()`, `.Close()`, Rx.NET's `.Subscribe(...)`, and
    SignalR's `.On<T>(...)` never matched at all; only a non-idiomatic
    lowercase call would.
    """
    old_cleanup = re.compile(r"\b(dispose|close|free|delete|GC\.Collect|GC\.SuppressFinalize)\b\s*\(")
    assert not old_cleanup.search("conn.Dispose();"), "sanity check: bug must reproduce"
    assert not old_cleanup.search("stream.Close();"), "sanity check: bug must reproduce"

    cleanup = CSHARP_RULES["cleanup"]
    assert cleanup.search("conn.Dispose();")
    assert cleanup.search("stream.Close();")
    assert cleanup.search("GC.Collect();"), "the already-working GC.Collect form must still work"

    old_listeners = re.compile(r"\b(on|addEventListener|subscribe|EventHandler)\b|\+=")
    assert not old_listeners.search("observable.Subscribe(x => f(x));"), "sanity check: bug must reproduce"
    assert not old_listeners.search('hubConnection.On<string>("Msg", h);'), "sanity check: bug must reproduce"

    listeners = CSHARP_RULES["listeners"]
    assert listeners.search("observable.Subscribe(x => f(x));")
    assert listeners.search('hubConnection.On<string>("Msg", h);')
    assert listeners.search("public event EventHandler Clicked;"), (
        "the already-working EventHandler form must still work"
    )


def test_csharp_test_skip_xunit_fact_skip_attribute_regression():
    """
    Real coverage gap found and fixed: xUnit's `[Fact(Skip = "...")]` /
    `[Theory(Skip = "...")]` form -- the dominant real xUnit skip idiom --
    was entirely missing (NUnit/MSTest use a standalone `[Ignore]`
    attribute instead, which was already covered).
    """
    old_pattern = re.compile(r"\[(?:Ignore|Skipped)\]|test\.skip\(|mock\(|stub\(|Substitute\.For")
    assert not old_pattern.search('[Fact(Skip = "not ready")]'), "sanity check: bug must reproduce"

    test_skip = CSHARP_RULES["test_skip"]
    assert test_skip.search('[Fact(Skip = "not ready")]')
    assert test_skip.search('[Theory(Skip = "x")]')
    assert test_skip.search("[Ignore]"), "the already-working NUnit/MSTest form must still work"
    assert not test_skip.search("[Fact]"), "a plain [Fact] with no Skip must not be flagged"


def test_csharp_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template: already found in
    TypeScript (`myRegex.test('x')` miscounted as a test-framework call) --
    checked for the same collision given C#'s `Regex.IsMatch`/`.Match(`
    methods. csharp's `test` rule requires specific attribute markers
    (`[Fact]`, `[Test]`, ...) or `Assert.`/`Mock.`/`Substitute.For`/
    `Should()`, none of which overlap with `Regex.IsMatch`/`Regex.Match`/
    `new Regex` -- confirmed clean, no bug (unlike TypeScript's generic
    `.test(` heuristic, C#'s is attribute/prefix-anchored and specific).
    """
    test_rule = CSHARP_RULES["test"]
    regex_rule = CSHARP_RULES["regex_execution"]

    assert not test_rule.search("Regex.IsMatch(input, pattern);")
    assert regex_rule.search("Regex.IsMatch(input, pattern);")

    assert not test_rule.search("var m = Regex.Match(input, pattern);")
    assert regex_rule.search("var m = Regex.Match(input, pattern);")

    assert not test_rule.search("var re = new Regex(pattern);")
    assert regex_rule.search("var re = new Regex(pattern);")


def test_csharp_func_start_generics_redos_immunity():
    """
    Known ambiguity pattern from the issue template, and this language's
    own pre-existing regression test (test_csharp_iron_wall_redos), folded
    into this suite with a proper scaling sweep (not just the original
    single-timing check): deeply nested generic return types must not
    trigger catastrophic backtracking.
    """
    func_start = CSHARP_RULES["func_start"]

    poison_cs = "    public static async Task<Dictionary<string, List<Tuple<int, string>>>>\n" * 20 + "    BrokenMethod"
    assert_redos_immune(func_start, poison_cs, timeout_sec=3.0)

    valid_cs = "public async Task<List<string>> FetchData() {"
    matches = list(func_start.finditer(valid_cs))
    assert len(matches) == 1
    assert matches[0].group(1) == "FetchData"


def test_csharp_func_start_redos_regression():
    """
    Real ReDoS bug found and fixed (Rule 14): the return-type loop's
    trailing whitespace and the final whitespace before the opening `(`
    are two effectively-adjacent unbounded whitespace quantifiers -- once
    a real method never follows (no `(` anywhere), the engine must retry
    every possible split of the same trailing whitespace run across both
    gaps, O(n^2). Confirmed ~4x/doubling, 1.5s at n=32000 on a bare
    `"int foo" + " "*n` payload before the fix. Bounded both to `{1,200}`/
    `{0,200}`, same fix shape already applied in cpp.
    """
    func_start = CSHARP_RULES["func_start"]
    assert_redos_immune(func_start, "int foo" + " " * 100000, timeout_sec=3.0)
    m = func_start.search("public int Foo() {")
    assert m and m.group(1) == "Foo"


def test_csharp_func_start_regex_unchanged_by_789():
    """
    #789 (expression-bodied members never counted; bare top-level calls
    hallucinated as functions) is fixed entirely in detector.py's
    _slice_by_braces (see test_detector_csharp_* in test_detector.py), NOT
    by adding a terminator requirement to this regex. An earlier attempt
    did add a `{`/`=>`-requiring lookahead here, but that broke the
    pre-existing cross-language "extraction gauntlet"
    (test_function_extraction_strict.py), which deliberately tests
    func_start against bare signature fragments with no terminator visible
    at all -- true for csharp's own fixtures there and for most other
    languages' fixtures too (e.g. typescript's
    `"function TargetFunc<T, U>("`). This test locks in that the regex
    still matches a bare fragment exactly as before, so a future change
    doesn't reintroduce that conflict.
    """
    func_start = CSHARP_RULES["func_start"]
    m = func_start.search("protected override void TargetFunc(int x)")
    assert m and m.group(1) == "TargetFunc", "func_start must still match a bare signature fragment with no terminator"


def test_csharp_args_lambda_redos_immunity_folded():
    """
    Pre-existing regression test (test_csharp_args_lambda_redos_immunity),
    folded into this suite unchanged.
    """
    pattern = CSHARP_RULES["args"]
    assert_redos_immune(pattern, "x" * 40000, timeout_sec=3.0)
    assert pattern.search("x => x + 1")


def test_csharp_events_plus_minus_equals_operators_folded():
    """
    Pre-existing regression test (test_csharp_events_plus_minus_equals_
    operators), folded into this suite unchanged.
    """
    pattern = CSHARP_RULES["events"]
    assert pattern.search("MyEvent += handler;"), "Failed to match the idiomatic spaced += form"
    assert pattern.search("MyEvent -= handler;"), "Failed to match the idiomatic spaced -= form"
    assert pattern.search("public event EventHandler Clicked;")


def test_csharp_should_and_wait_boundary_regression_folded():
    """
    Pre-existing regression test (test_csharp_should_and_wait_boundary_
    regression), folded into this suite unchanged.
    """
    r = CSHARP_RULES
    assert r["test"].search("result.Should().Be(x);")
    assert r["thread_sleeps"].search("task.Wait();")
    assert not r["thread_sleeps"].search("myWait();"), "thread_sleeps incorrectly matched a substring identifier"


def test_csharp_intentional_double_classification_sweep():
    """
    Ambiguity sweep finding: several C# constructs legitimately fire two
    signatures representing different perspectives on the same underlying
    action, or share a literal keyword between two independently-authored
    rule lists -- intentional, not false collisions:
    - `class Foo {` -> class_start + structural_boundaries (`class` is a
      literal keyword in both rules' own lists)
    - `// if (x) foo();` -> dead_code + branch (`if` is a literal keyword
      in both rules' own lists)
    - `public static readonly int MAX = 1;` -> globals + immutability_locks
      (`readonly` is a literal keyword in both rules' own lists)
    - `MyEvent += Handler;` -> events + listeners (`+=` is explicitly
      defined in both rules' own alternatives)
    - `public class Home : ComponentBase {}` -> ui_framework +
      ssr_boundaries (`ComponentBase` is a literal keyword in both rules'
      own lists)
    - `Process.Start("foo");` -> ipc_rpc_bridges + high_risk_execution
      (`Process.Start` is a literal keyword in both rules' own lists)
    - `x = a << 2;` -> bitwise_ops (the shift) + state_mutation (the
      assignment) -- any real shift-and-assign statement naturally fires
      both
    - `JsonSerializer.Deserialize<Foo>(json);` -> generics (the `<Foo>`) +
      serialization_parsing -- any generic-typed serialization call
      naturally fires both
    """
    class_decl = "class Foo {"
    assert CSHARP_RULES["class_start"].search(class_decl)
    assert CSHARP_RULES["structural_boundaries"].search(class_decl)

    dead_if = "// if (x) foo();"
    assert CSHARP_RULES["dead_code"].search(dead_if)
    assert CSHARP_RULES["branch"].search(dead_if)

    readonly_field = "public static readonly int MAX = 1;"
    assert CSHARP_RULES["globals"].search(readonly_field)
    assert CSHARP_RULES["immutability_locks"].search(readonly_field)

    event_sub = "MyEvent += Handler;"
    assert CSHARP_RULES["events"].search(event_sub)
    assert CSHARP_RULES["listeners"].search(event_sub)

    blazor_component = "public class Home : ComponentBase {}"
    assert CSHARP_RULES["ui_framework"].search(blazor_component)
    assert CSHARP_RULES["ssr_boundaries"].search(blazor_component)

    process_start = 'Process.Start("foo");'
    assert CSHARP_RULES["ipc_rpc_bridges"].search(process_start)
    assert CSHARP_RULES["high_risk_execution"].search(process_start)

    shift_assign = "x = a << 2;"
    assert CSHARP_RULES["bitwise_ops"].search(shift_assign)
    assert CSHARP_RULES["state_mutation"].search(shift_assign)

    generic_deserialize = "JsonSerializer.Deserialize<Foo>(json);"
    assert CSHARP_RULES["generics"].search(generic_deserialize)
    assert CSHARP_RULES["serialization_parsing"].search(generic_deserialize)


def test_csharp_spec_exposure_redos_regression():
    """
    Real bug found and fixed (Rule 14): adjacent unbounded quantifiers with
    overlapping character sets (`\\d+` next to `[^\\]]*`) -- the same ReDoS
    shape already found and fixed independently in embedded_python, css,
    tcl, matlab, scheme, typescript, rust, c, and cpp earlier in this epic
    (the 10th hit).
    """
    old_pattern = re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I)
    # Scale-relative sanity check (not an absolute wall-clock threshold,
    # which is flaky across CI hardware of varying speed): a payload-size
    # doubling should cost ~4x on the quadratic OLD pattern, vs ~2x for
    # linear.
    small_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 8000 + " " * 8000)
    large_duration = _best_of_timing(old_pattern, "[SPEC-" + "1" * 16000 + " " * 16000)
    ratio = large_duration / small_duration if small_duration > 0 else 0
    assert ratio > 2.2, (
        f"sanity check: old pattern was expected to show quadratic (~4x) scaling on a payload "
        f"doubling, but only scaled {ratio:.2f}x ({small_duration:.4f}s -> {large_duration:.4f}s)"
    )

    spec_exposure = CSHARP_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-" + " " * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123]")
    assert spec_exposure.search("[audit]")


def test_csharp_redos_immunity_sweep():
    """
    ReDoS immunity sweep across csharp's remaining rules with unbounded-
    looking quantifiers, verified via a systematic scaling sweep
    (n=2000/4000/8000/16000/32000) before writing this test.
    """
    assert_redos_immune(CSHARP_RULES["args"], "int foo(int " + "a," * 16000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["args"], "MyClass(" + "a," * 16000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["func_start"], "[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["class_start"], "class " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["class_start"], "[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["memory_alloc"], "ArrayPool<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["generics"], "<A" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["globals"], "public static " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["_dependency_capture"], "using " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(CSHARP_RULES["import"], "using " + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert CSHARP_RULES["func_start"].search("public int Foo() {")
    assert CSHARP_RULES["class_start"].search("class Foo {")
    assert CSHARP_RULES["args"].search("x => x + 1")
