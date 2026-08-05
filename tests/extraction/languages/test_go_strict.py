"""go strict structural-signature coverage.

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


# ==============================================================================
# GO: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #583)
# ==============================================================================
GO_RULES = LANGUAGE_DEFINITIONS["go"]["rules"]

_GO_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ('api', 'var Foo = 5', 'var foo = 5'),
    ('args', 'func foo(x int) {', 'foo(x)'),
    ('bitwise_ops', 'x := a &^ b', 'x := a && b'),
    ('branch', 'if err != nil {', 'err != nil'),
    ('class_start', 'type Foo struct {', 'Foo struct {}'),
    ('cleanup', 'defer f.Close()', 'f.Closed = true'),
    ('closures', 'func(x int) { return x }', 'func foo(x int) { return x }'),
    ('comprehensions', 'slices.Filter(s, f)', 'slices.Len(s)'),
    ('concurrency', 'go func() { }()', 'goto label'),
    ('debug_prints', 'fmt.Println("debug")', 'fmt.Sprintf("debug")'),
    ('decorators', '//go:build linux', '// go to sleep'),
    ('dependency_injection', 'wire.Build(NewFoo)', 'wire.NewFoo()'),
    ('doc', '// Foo does something useful.', '// foo does something useful'),
    ('encapsulation', 'var foo = 5', 'var Foo = 5'),
    ('events', 'bus.Publish(event)', 'bus.Published = true'),
    ('explicit_casts', 'int(x)', 'intVar := 5'),
    ('fragile_debt', '// HACK: workaround', '// HACKATHON: event'),
    ('func_start', 'func foo() {', 'type Foo struct {'),
    ('generics', '[T any]', 'x := 5'),
    ('globals', 'var globalCount = 0', 'count := 0'),
    ('high_risk_execution', 'os.Exit(1)', 'foo.Exit()'),
    ('immutability_locks', 'const Pi = 3.14', 'var Pi = 3.14'),
    ('import', 'import "fmt"', 'imported = true'),
    ('io', 'os.Open("file.txt")', 'os.Opened = true'),
    ('ipc_rpc_bridges', 'grpc.Dial(addr)', 'grpc.Dialed = true'),
    ('listeners', 'func recv(ch <-chan int) {}', 'chan int'),
    ('macros', '//go:generate mockgen', '// go generator'),
    ('memory_alloc', 'make([]int, 10)', 'x := makeVar'),
    ('ownership', '// Author: Jane Doe', '// Authorized by'),
    ('panics_and_aborts', 'panic("oops")', 'panicked := true'),
    ('planned_debt', '// TODO: fix this', '// TODONE'),
    ('pointers', 'p := &x', 'p := x'),
    ('reflection_metaprogramming', 'reflect.TypeOf(x)', 'x := reflectVar'),
    ('regex_execution', 'regexp.MustCompile(pattern)', 'regexp.Compiled = true'),
    ('safety', 'if err != nil {', 'err == nil'),
    ('safety_bypasses', '_, err = foo()', 'x, err = foo()'),
    ('scientific', 'math.Sqrt(4)', 'foo.math()'),
    ('serialization_parsing', 'json.Unmarshal(data, &v)', 'json.Marshaled = true'),
    ('spec_exposure', '// [SPEC-123] implements the contract', '// spec sheet'),
    ('ssr_boundaries', 'var w http.ResponseWriter', 'var w foo.ResponseWriter'),
    ('state_mutation', 'x := 5', 'x == 5'),
    ('structural_boundaries', 'package main', 'packaged = true'),
    ('sync_locks', 'mu.Lock()', 'mu.Locked = true'),
    ('telemetry', 'slog.Info("message")', 'slog.Informed = true'),
    ('test', 'func TestFoo(t *testing.T) {', 'func foo() {'),
    ('test_skip', 't.Skip("reason")', 't.Skipped = true'),
    ('thread_sleeps', 'time.Sleep(time.Second)', 'time.Slept = true'),
    ('time_date_logic', 'time.Now()', 'time.New()'),
    ('ui_framework', 'http.HandleFunc("/", handler)', 'http.Handled = true'),
    ('dead_code', '// func foo() {', '// just a note'),
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
