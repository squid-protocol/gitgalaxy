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
    ("api", "var Foo = 5", "var foo = 5"),
    ("args", "func foo(x int) {", "foo(x)"),
    ("args", "func (s *Server) Handle(ctx context.Context) {", "func_name(x)"),
    ("args", "func Map[T any, M any](a []T, f func(T) M) {", "func_call()"),
    ("args", "func \n(s *Server)\nHandle(\n ctx context.Context\n) {", "foo(x)"),
    ("args", "func (s *Server[T]) Foo[U []int](x U)", "foo(x)"),
    ("bitwise_ops", "x := a &^ b", "x := a && b"),
    ("branch", "if err != nil {", "err != nil"),
    ("branch", "else if true {", "else_case"),
    ("branch", "case <-ch:", "mycase := 1"),
    ("branch", "for k, v := range m {", "for_loop"),
    ("branch", "select {", "goto L"),  # 2822 corollary 3
    ("structural_boundaries", "fallthrough", "fallthrough_var := 1"),  # 2832: unconditional transfer, not a branch
    ("class_start", "type Foo struct {", "Foo struct {}"),
    ("class_start", "type Foo[T map[string]int] struct {", "type Foo[T map[string]int] func()"),
    ("class_start", "type \n Foo \n [T map[string]int] \n struct {", "type \n Foo \n int"),
    ("class_start", "type Stack[T any] interface {", "type Stack int"),
    ("class_start", "type Foo[T constraints.Ordered] struct {", "type Foo bool"),
    ("cleanup", "defer f.Close()", "f.Closed = true"),
    ("closures", "func(x int) { return x }", "func foo(x int) { return x }"),
    ("comprehensions", "slices.Filter(s, f)", "slices.Len(s)"),
    ("concurrency", "go func() { }()", "goto label"),
    ("debug_prints", 'fmt.Println("debug")', 'fmt.Sprintf("debug")'),
    ("decorators", "//go:build linux", "// go to sleep"),
    ("dependency_injection", "wire.Build(NewFoo)", "wire.NewFoo()"),
    ("doc", "// Foo does something useful.", "// foo does something useful"),
    ("encapsulation", "var foo = 5", "var Foo = 5"),
    ("events", "bus.Publish(event)", "bus.Published = true"),
    ("explicit_casts", "int(x)", "intVar := 5"),
    ("fragile_debt", "// HACK: workaround", "// HACKATHON: event"),
    ("func_start", "func foo() {", "type Foo struct {"),
    ("func_start", "func Foo[T map[string]int](x T) {", "func(x int) {"),
    ("func_start", "func (s *Server[T]) Foo[U []int](x U) {", "func_name()"),
    ("func_start", "func \n(s *Server)\nFoo\n[T map[string]int]\n(x T) {", "myfunc Foo() {"),
    ("func_start", "func (s *Server[map[string]int]) Foo() {", "func_name()"),
    ("generics", "[T any]", "x := 5"),
    ("generics", "[T map[string]any]", "any_var := 5"),
    ("generics", "[T []any]", "anyvar := 2"),
    ("generics", "[T interface{ M() []any }]", "x := any_val"),
    ("generics", "[T ~int | ~string]", "x := ~intVal"),
    ("globals", "var globalCount = 0", "count := 0"),
    ("high_risk_execution", "os.Exit(1)", "foo.Exit()"),
    ("immutability_locks", "const Pi = 3.14", "var Pi = 3.14"),
    ("import", 'import "fmt"', "imported = true"),
    ("io", 'os.Open("file.txt")', "os.Opened = true"),
    ("ipc_rpc_bridges", "grpc.Dial(addr)", "grpc.Dialed = true"),
    ("listeners", "func recv(ch <-chan int) {}", "chan int"),
    ("macros", "//go:generate mockgen", "// go generator"),
    ("memory_alloc", "make([]int, 10)", "x := makeVar"),
    ("ownership", "// Author: Jane Doe", "// Authorized by"),
    ("panics_and_aborts", 'panic("oops")', "panicked := true"),
    ("planned_debt", "// TODO: fix this", "// TODONE"),
    ("pointers", "p := &x", "p := x"),
    ("reflection_metaprogramming", "reflect.TypeOf(x)", "x := reflectVar"),
    ("regex_execution", "regexp.MustCompile(pattern)", "regexp.Compiled = true"),
    ("safety", "if err != nil {", "err == nil"),
    ("safety_bypasses", "_, err = foo()", "x, err = foo()"),
    ("safety_bypasses", 'import . "fmt"', 'import "fmt"'),
    ("scientific", "math.Sqrt(4)", "foo.math()"),
    ("serialization_parsing", "json.Unmarshal(data, &v)", "json.Marshaled = true"),
    ("spec_exposure", "// [SPEC-123] implements the contract", "// spec sheet"),
    ("ssr_boundaries", "var w http.ResponseWriter", "var w foo.ResponseWriter"),
    ("state_mutation", "x = 5", "x := 5"),  # #2765: `:=` declares; the re-assignment is the write
    ("structural_boundaries", "package main", "packaged = true"),
    ("structural_boundaries", "map[string]int", "map_name"),
    ("structural_boundaries", "<-chan int", "channel"),
    ("structural_boundaries", "go func(){}()", "going"),
    ("structural_boundaries", "defer f.Close()", "deferred"),
    ("sync_locks", "mu.Lock()", "mu.Locked = true"),
    ("telemetry", 'slog.Info("message")', "slog.Informed = true"),
    ("test", "func TestFoo(t *testing.T) {", "func foo() {"),
    ("test_skip", 't.Skip("reason")', "t.Skipped = true"),
    ("thread_sleeps", "time.Sleep(time.Second)", "time.Slept = true"),
    ("time_date_logic", "time.Now()", "time.New()"),
    ("ui_framework", 'http.HandleFunc("/", handler)', "http.Handled = true"),
    ("dead_code", "// func foo() {", "// just a note"),
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
    4. #2730 (api contract): excluding a following `(` was not enough --
       ANY line starting with an exported identifier counted, so a
       struct-literal field key (`Group: "apps",`) and a method call on an
       exported package var (`DefaultServeMux.register(...)`) both scored as
       public surface. Those are references to an exported name, not
       declarations of one. The indented alternative now requires what a
       grouped `var`/`const` member or a struct field actually looks like
       (`Name = value`, `Name Type`, or a bare embedded type alone on its
       line), which is why the struct-literal assertion below is now
       negative.
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

    # Grouped var/const block members: indented, but still top-level. api keeps
    # its indented arm (uppercase can't collide with keywords/locals). #2766 removed
    # encapsulation's indented arm entirely: a lowercase `name = value` at indent is
    # regex-indistinguishable from a function-local assignment (the old arm's 4521
    # crucible hits were locals), so grouped-member privates are a KNOWN LIMIT until
    # #2859's go_package_scope brace-walking filter exists.
    assert api.search("\tBurstReplicas = 500"), "api failed on an indented grouped-const member"
    assert not encap.search("\tBurstReplicas = 500")
    assert not encap.search("\tenableFoo = true"), "grouped-member privates are out until #2859's scope filter"
    assert not api.search("\tenableFoo = true")
    # Struct TYPE fields and embedded types are declarations -- they stay.
    assert api.search("\tName string"), "api failed on an indented exported struct field"
    assert api.search("\tItems []Thing"), "api failed on an indented exported slice field"
    assert api.search("\tMaxSize, MinSize int"), "api failed on a multi-name field declaration"
    assert api.search("\tReader"), "api failed on a bare embedded exported type"

    # #2730: references to an exported name are not declarations.
    assert not api.search('\t\tGroup:    "apps",'), "api counted a struct-literal field key"
    assert not api.search("\tDefaultServeMux.register(pattern, handler)"), (
        "api counted a method call on an exported package var"
    )
    assert not api.search("\tAlpha,"), "api counted a composite-literal element"

    # The new multi-name run (`Name, Name, ... Type`) repeats an alternation
    # that needs a literal comma per step, so it cannot backtrack ambiguously.
    # Detonated on a run that never reaches a type or an `=`.
    assert_redos_immune(api, "\tA" + ", A" * 40000, timeout_sec=3.0)


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


def test_go_safety_bypasses_dot_import_only_regression():
    """
    Regression test (#2542): the import alternation made the dot OPTIONAL
    (`import\\s+(?:\\.[ \\t]+)?"`), so EVERY plain quoted import
    (`import "fmt"`) counted as a safety bypass -- Go's completely normal,
    idiomatic import form -- not just the namespace-polluting dot-import
    (`import . "fmt"`). The dot is now mandatory.

    Grouped imports are documented, not changed, by the fix: the `(` between
    `import` and the quoted path means this alternation never matched any
    line of a grouped block (dot-prefixed or not) before the fix, and still
    doesn't after -- the fix only removes the false positive on the
    single-line plain form.
    """
    pattern = GO_RULES["safety_bypasses"]

    assert len(pattern.findall('import . "fmt"')) == 1, "dot-import must count exactly one safety bypass"
    assert not pattern.search('import "fmt"'), "a plain quoted import is not a safety bypass"
    assert not pattern.search('import f "fmt"'), "an aliased import is not a safety bypass"
    assert pattern.search('import .\t"unsafe"'), "tab-separated dot-import must still match"

    # Grouped forms: never matched by this alternation, before or after.
    assert not pattern.search('import (\n\t"fmt"\n\t"os"\n)')
    assert not pattern.search('import (\n\t. "fmt"\n)')


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


def _go_globals(code: str) -> int:
    """Filtered globals count: the real extractor applies the registry-declared
    `go_declaration_group` scope filter, which the bare regex does not."""
    from gitgalaxy.core.detector import StructuralExtractor

    return StructuralExtractor("go", LANGUAGE_DEFINITIONS).splice(code, "")["equations"]["globals"]


def test_go_globals_anchor_bug_regression():
    """#2660: a gofmt-indented function-local `var` must not count as a global.
    #2859: the column-0 anchor could not see `var (`/`const (` group members
    either, so the rule now over-matches every indented identifier line and the
    `go_declaration_group` scope filter (detector.py) keeps only the true group
    members -- these tests go through the real extractor, not the bare regex."""
    assert _go_globals("var registry = map[string]int{}") == 1, "true top-level var must count"
    assert _go_globals('os.Getenv("X")') == 1, "os.Getenv must still count"

    # #2660: the over-matching arm now matches the indented `var local`, but the
    # scope filter drops it -- it is a function body, not a declaration group.
    func_local = "func foo() {\n\tvar local = 5\n\tother := 3\n\treturn local\n}"
    assert GO_RULES["globals"].search(func_local), "sanity: the bare regex over-matches the indented line"
    assert _go_globals(func_local) == 0, "tab-indented function-local var must NOT count as global"

    # #2859: grouped `var (...)` / `const (...)` members now count -- the whole
    # point of the widening.
    grouped = "var (\n\tregistry = map[string]int{}\n\tcounter int\n)\n"
    assert _go_globals(grouped) == 2, "both group members count as globals"

    # A struct-literal field inside a group member is not itself a global.
    with_struct = 'var (\n\tres = schema.GroupResource{\n\t\tGroup:    "apps",\n\t\tResource: "sets",\n\t}\n)\n'
    assert _go_globals(with_struct) == 1, "only the member binding counts, not its struct fields"


def test_go_scope_filter_is_declared_for_globals():
    assert GO_RULES["_scope_filters"] == {"globals": "go_declaration_group"}


def test_go_declaration_group_walk_is_linear_on_pathological_input():
    """The member walk is a single tokenizer pass, not backtracking."""
    import time

    from gitgalaxy.core.detector import StructuralExtractor

    d = StructuralExtractor("go", LANGUAGE_DEFINITIONS)
    payloads = ["var (\n" + "\tx = 1\n" * 20000 + ")\n", "(" * 60000, "`" * 60000, "\t" * 60000 + "x"]
    for p in payloads:
        t = time.perf_counter()
        d._go_declaration_group_member_offsets(p)
        assert time.perf_counter() - t < 1.0


def test_go_unknown_scope_filter_name_is_ignored_not_zeroed():
    import copy

    from gitgalaxy.core.detector import StructuralExtractor

    defs = copy.deepcopy(LANGUAGE_DEFINITIONS)
    defs["go"]["rules"]["_scope_filters"] = {"globals": "no-such-filter"}
    counts, *_ = StructuralExtractor("go", defs).coding_analysis([("go", "var top = 1\n", 0)])
    assert counts["globals"] >= 1
