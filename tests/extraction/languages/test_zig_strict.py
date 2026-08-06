"""zig strict structural-signature coverage.

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
import re

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


def test_zig_at_builtins_leading_boundary_regression():
    """
    Zig's cast/reflection/atomics/scientific operations are all `@builtin`
    forms -- this was the single most affected language, with 8 separate
    signatures silently blind to their primary detection surface.
    """
    r = LANGUAGE_DEFINITIONS["zig"]["rules"]
    assert r["safety_bypasses"].search("@ptrCast(x)")
    assert r["safety_bypasses"].search("const x: u8 = @truncate(y);")
    assert r["high_risk_execution"].search('@panic("oops");')
    assert r["concurrency"].search("@atomicLoad(u32, &x, .SeqCst);")
    assert r["scientific"].search("const v = @Vector(4, f32);")
    assert r["reflection_metaprogramming"].search("@typeInfo(T);")
    assert r["import"].search('@import("std");')
    assert r["explicit_casts"].search("@intCast(x);")
    assert r["panics_and_aborts"].search('@panic("err");')


# ==============================================================================
# ZIG: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #618, part of epic #518)
# ==============================================================================
# NOTE: most of zig's @-prefixed-builtin rules (safety_bypasses,
# high_risk_execution, concurrency, scientific, reflection_metaprogramming,
# import, explicit_casts, panics_and_aborts) already carry BUG FIX comments
# from an earlier cross-language sweep fixing the leading-\b-before-@ trap --
# not re-litigated here, just covered by the positive/negative table below
# like any other already-correct rule.
ZIG_RULES = LANGUAGE_DEFINITIONS["zig"]["rules"]

_ZIG_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if (x == 0) { return; }", "const x = 5;"),
    ("args", "fn add(a: i32, b: i32) i32 {", "const x = 5;"),
    ("structural_boundaries", "var x: i32 = 0;", "const x: i32 = 0;"),
    ("func_start", "pub fn main() void {", "const Point = struct {"),
    ("class_start", "const Point = struct {", "pub fn main() void {"),
    ("safety", "try foo();", "foo();"),
    ("safety_bypasses", "const x = @ptrCast(*u8, &y);", "const x: *u8 = &y;"),
    ("high_risk_execution", '@panic("unreachable state");', "return error.Bad;"),
    ("io", "const file = try std.fs.cwd().openFile(path, .{});", "const x = 5;"),
    ("api", "pub fn main() void {", "fn helper() void {"),
    ("state_mutation", "var x: i32 = 0;", "const x: i32 = 0;"),
    ("dead_code", "// fn oldFunc() void {}", "// just a note"),
    ("doc", "/// Computes the sum of two integers.", "// just a note"),
    ("test", 'test "basic addition" {', "fn add() void {}"),
    ("concurrency", "const t = try std.Thread.spawn(.{}, worker, .{});", "const x = 5;"),
    ("ui_framework", 'mach.core.setTitle("App");', "const x = 5;"),
    ("globals", 'pub const version = "1.0";', "x.field = 5;"),
    ("generics", "fn max(comptime T: type, a: T, b: T) T {", "fn add(a: i32, b: i32) i32 {"),
    ("scientific", "const result = std.math.sqrt(x);", "const x = 5;"),
    ("reflection_metaprogramming", "const info = @typeInfo(T);", "const x = 5;"),
    ("import", 'const std = @import("std");', "const x = 5;"),
    ("ownership", "// Author: Jane Doe", "// just a note"),
    ("planned_debt", "// TODO: refactor this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "// [SPEC-123]", "// just a note"),
    ("ssr_boundaries", "fn handler(req: zap.Request) void {", "fn handler() void {"),
    ("events", "std.posix.epoll_wait(fd, &events, -1);", "const x = 5;"),
    ("pointers", "const p: *const u8 = &x;", "const x: u8 = 5;"),
    ("memory_alloc", "const buf = try allocator.alloc(u8, 10);", "const x = 5;"),
    ("inline_asm", 'asm volatile ("nop");', "const x = 5;"),
    ("telemetry", 'std.log.info("starting", .{});', "const x = 5;"),
    ("debug_prints", 'std.debug.print("x = {}\\n", .{x});', 'std.log.info("x", .{});'),
    ("explicit_casts", "const y = @intCast(i32, x);", "const y: i32 = x;"),
    ("panics_and_aborts", "unreachable;", "const x = 5;"),
    ("thread_sleeps", "std.time.sleep(1000);", "const x = 5;"),
    ("bitwise_ops", "const mask = a & b;", "const sum = a + b;"),
    ("sync_locks", "var mutex = std.Thread.Mutex{};", "const x = 5;"),
    ("immutability_locks", "const x: i32 = 5;", "var x: i32 = 5;"),
    ("cleanup", "defer allocator.free(buf);", "const x = 5;"),
    ("encapsulation", "fn helper() void {", "pub fn helper() void {"),
    ("test_skip", "std.testing.expect(true) catch unreachable;", "const x = 5;"),
    ("serialization_parsing", "const parsed = try std.json.parseFromSlice(T, allocator, data, .{});", "const x = 5;"),
    ("regex_execution", "const idx = std.mem.indexOf(u8, haystack, needle);", "const x = 5;"),
    ("time_date_logic", "const ts = std.time.milliTimestamp();", "const x = 5;"),
    ("ipc_rpc_bridges", "var child = std.process.Child.init(&argv, allocator);", "const x = 5;"),
]


@pytest.mark.parametrize("signature,positive,negative", _ZIG_SIMPLE_CASES)
def test_zig_signature_positive_and_negative(signature, positive, negative):
    pattern = ZIG_RULES[signature]
    assert pattern is not None, f"zig's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"zig {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"zig {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_zig_func_start_and_class_start_capture_names():
    func_start = ZIG_RULES["func_start"]
    m = func_start.search("pub fn main() void {")
    assert m and m.group(1) == "main"
    m2 = func_start.search("fn max(comptime T: type, a: T, b: T) T {")
    assert m2 and m2.group(1) == "max", "func_start should still capture the name past a generic comptime param"

    class_start = ZIG_RULES["class_start"]
    m3 = class_start.search("pub const Point = struct {")
    assert m3 and m3.group(1) == "Point"
    m4 = class_start.search("const Color = enum {")
    assert m4 and m4.group(1) == "Color"

    assert not class_start.search("pub fn main() void {"), "class_start incorrectly matched a function"
    assert not func_start.search("const Point = struct {"), "func_start incorrectly matched a struct"


def test_zig_dependency_capture_extracts_import_path():
    pattern = ZIG_RULES["_dependency_capture"]
    m = pattern.search('const std = @import("std");')
    assert m and m.group(1) == "std"
    m2 = pattern.search('@cInclude("stdio.h");')
    assert m2 and m2.group(1) == "stdio.h"


def test_zig_at_prefixed_builtins_already_fixed_confirmed():
    """
    Confirms the leading-\\b-before-@ trap fix (from an earlier
    cross-language sweep) actually holds for all 8 already-BUG-FIX-annotated
    rules -- not re-deriving the fix, just verifying it against realistic
    same-line usage (an @builtin is virtually always preceded by whitespace
    or `=`, never a word character, so this is the realistic form the old
    shared \\b would have failed on).
    """
    assert ZIG_RULES["safety_bypasses"].search("const y = @ptrCast(*u8, &x);")
    assert ZIG_RULES["high_risk_execution"].search('if (bad) @panic("oops");')
    assert ZIG_RULES["concurrency"].search("const v = @atomicLoad(i32, &counter, .seq_cst);")
    assert ZIG_RULES["scientific"].search("const v: @Vector(4, f32) = undefined;")
    assert ZIG_RULES["reflection_metaprogramming"].search("const info = @typeInfo(T);")
    assert ZIG_RULES["import"].search('const std = @import("std");')
    assert ZIG_RULES["explicit_casts"].search("const y = @intCast(i32, x);")
    assert ZIG_RULES["panics_and_aborts"].search('if (bad) @panic("oops");')


def test_zig_args_nested_fn_pointer_param_regression():
    """
    Regression test for a real bug (Rule 11, nested-delimiter): `[^)]*` is a
    flat negated class, can't represent even one level of nesting. Zig
    function-pointer-type parameters nest constantly (`fn foo(callback:
    fn(i32) void) void`, a common callback-parameter idiom) -- confirmed the
    old pattern truncated at the first *inner* `)` instead of the true
    closing one.
    """
    old_pattern = re.compile(r"\bfn\s*(?:[a-zA-Z_]\w*\s*)?\([^)]*\)")
    nested = "fn foo(callback: fn(i32) void) void {"
    old_m = old_pattern.search(nested)
    assert old_m and old_m.group(0) == "fn foo(callback: fn(i32)", "sanity check: old pattern must truncate"

    args = ZIG_RULES["args"]
    m = args.search(nested)
    assert m and m.group(0) == "fn foo(callback: fn(i32) void)", (
        f"nested fn-pointer-param call truncated: {m.group(0) if m else None!r}"
    )
    assert args.search("fn add(a: i32, b: i32) i32").group(0) == "fn add(a: i32, b: i32)"


def test_zig_args_nested_redos_immunity():
    assert_redos_immune(ZIG_RULES["args"], "fn(" + "(" * 20000, timeout_sec=3.0)
    assert ZIG_RULES["args"].search("fn add(a: i32, b: i32) i32")


def test_zig_test_quoted_name_trailing_boundary_regression():
    """
    Regression test for a real bug: `test\\s+"[^"]*"` ended on `"`, inside
    the shared trailing `\\b` group. The character after a closing quote in
    real usage (`test "basic" {`) is a space then `{` -- both non-word, so
    the shared trailing `\\b` never fired. This is Zig's *dominant* real-
    world test declaration shape (a quoted description), not an edge case.
    """
    old_pattern = re.compile(r'\b(test\s+"[^"]*"|test\s+[a-zA-Z_]\w*|std\.testing\.expect|std\.testing\.expectEqual)\b')
    realistic = 'test "basic addition" {'
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    test_ = ZIG_RULES["test"]
    assert test_.search(realistic), "quoted test-name form still didn't match"
    assert test_.search("test my_named_test {"), "named-identifier test form regressed"
    assert test_.search("try std.testing.expect(x == 1);"), "std.testing.expect form regressed"
    assert test_.search("try std.testing.expectEqual(1, x);"), "std.testing.expectEqual form regressed"


def test_zig_func_start_vs_generics_no_false_collision():
    """
    Known ambiguity pattern from the issue template (deeply nested generic
    return types triggering catastrophic backtracking against func_start,
    as seen in C#). Verified empirically rather than assumed: a comptime
    generic parameter inside the arg list (`fn max(comptime T: type, a: T,
    b: T) T {`) doesn't confuse func_start's name capture, and doesn't
    trigger pathological backtracking even with a long chain of comptime
    params.
    """
    func_start = ZIG_RULES["func_start"]
    generics = ZIG_RULES["generics"]

    generic_fn = "fn max(comptime T: type, a: T, b: T) T {"
    assert generics.search(generic_fn)
    m = func_start.search(generic_fn)
    assert m and m.group(1) == "max"

    assert_redos_immune(func_start, "pub " * 50000 + "fn foo(", timeout_sec=3.0)


def test_zig_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (C's cast syntax
    overlapping pointer-asterisk repetition). Verified empirically: casts
    (`@ptrCast`/`@intCast`/etc.) and pointer syntax (`*const T`, `[*]T`,
    `.*`) are structurally distinct token shapes in Zig and never match the
    *same* substring -- a statement combining both (`const p: *const u8 =
    @ptrCast(&x);`) correctly fires both signatures on their own disjoint
    spans, which is genuine intentional double-classification (the
    statement really does contain both a cast and a pointer type), not a
    false collision.
    """
    casts = ZIG_RULES["explicit_casts"]
    pointers = ZIG_RULES["pointers"]

    combined = "const p: *const u8 = @ptrCast(&x);"
    cast_match = casts.search(combined)
    ptr_match = pointers.search(combined)
    assert cast_match and cast_match.group(0) == "@ptrCast"
    assert ptr_match and ptr_match.group(0) == "*const u8"
    assert cast_match.group(0) != ptr_match.group(0), "should match disjoint spans, not the same text"


def test_zig_test_vs_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (TypeScript's
    `.test('x')` regex method miscounted as a test-framework call). Zig has
    no native regex; `regex_execution` maps to `std.mem` string-search
    functions instead -- structurally distinct from `test`'s
    `test "..."`/`test name`/`std.testing.*` forms, no realistic overlap.
    """
    test_ = ZIG_RULES["test"]
    regex_execution = ZIG_RULES["regex_execution"]

    mem_search = "const idx = std.mem.indexOf(u8, haystack, needle);"
    assert regex_execution.search(mem_search)
    assert not test_.search(mem_search)

    test_block = 'test "basic" {'
    assert test_.search(test_block)
    assert not regex_execution.search(test_block)


def test_zig_state_mutation_and_pointers_deref_assign_intentional_double_classification():
    """
    Ambiguity sweep: `state_mutation` and `pointers` both fire on a pointer
    dereference assignment (`ptr.* = 5;`). Confirmed genuine, intentional
    double-classification: the statement is simultaneously a state mutation
    (flux) AND explicit pointer dereference syntax -- both readings are
    correct for the same construct.
    """
    state_mutation = ZIG_RULES["state_mutation"]
    pointers = ZIG_RULES["pointers"]
    deref_assign = "ptr.* = 5;"
    assert state_mutation.search(deref_assign)
    assert pointers.search(deref_assign)


def test_zig_structural_boundaries_and_panics_and_aborts_shared_literals_intentional():
    """
    Ambiguity sweep: `structural_boundaries` and `panics_and_aborts` both
    list `return` and `unreachable`. Confirmed intentional, not a bug:
    both constructs genuinely interrupt straight-line execution flow
    (structural_boundaries' framing) AND forcefully end the current
    execution context (panics_and_aborts' framing) -- both readings are
    correct for the same keywords, found empirically by checking the
    actual .search() results rather than assumed from the shared literal
    alone.
    """
    structural_boundaries = ZIG_RULES["structural_boundaries"]
    panics_and_aborts = ZIG_RULES["panics_and_aborts"]

    assert structural_boundaries.search("return;")
    assert panics_and_aborts.search("return;")
    assert structural_boundaries.search("unreachable;")
    assert panics_and_aborts.search("unreachable;")


def test_zig_encapsulation_default_private_semantics():
    """
    `encapsulation` uses a negative lookahead ((?!(?:pub|export|extern)\\b))
    to capture Zig's implicit-private-by-default visibility model (Rule 1:
    semantic intent over keyword matching) -- a declaration is "encapsulated"
    precisely when it's NOT explicitly marked pub/export/extern.
    """
    encapsulation = ZIG_RULES["encapsulation"]
    assert encapsulation.search("fn helper() void {"), "unmarked (private-by-default) fn should match"
    assert encapsulation.search("const secret = 42;"), "unmarked (private-by-default) const should match"
    assert not encapsulation.search("pub fn helper() void {"), "pub fn incorrectly matched as encapsulated"
    assert not encapsulation.search("export fn helper() void {"), "export fn incorrectly matched as encapsulated"


def test_zig_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: zig is `line_exclusive` (Zig intentionally has no
    block comments, only `//`) -- no rule tracks open/close block-comment
    state, matching the language's own real syntax. Confirms a stray `*/`
    (invalid in Zig, but plausible as accidental leftover text) doesn't fool
    any rule into a false structural match.
    """
    branch = ZIG_RULES["branch"]
    stray_close = "some text */ if (x == 0) { return; }"
    assert branch.search(stray_close), "branch should still see 'if' regardless of the stray */ before it"


def test_zig_redos_immunity_sweep():
    """
    ReDoS immunity sweep across zig's remaining unbounded-quantifier rules.
    Verified via a systematic scaling sweep before writing this test (7
    adversarial payload shapes -- unterminated parens/braces/pipes/brackets/
    at-signs, cross-newline runs, and long trailing content -- at
    n=2000/8000/32000 against every non-None rule): nothing exceeded 0.3s at
    n=32000 against any shape. This locks that in with
    assert_redos_immune's subprocess-kill timeout for the rules with the
    most visible unbounded quantifiers.
    """
    assert_redos_immune(ZIG_RULES["func_start"], "pub " * 50000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["class_start"], "const " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["globals"], "const x" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["safety"], "|" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["inline_asm"], "asm volatile (" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["pointers"], "= *" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(ZIG_RULES["_dependency_capture"], '@import("' + "a" * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert ZIG_RULES["func_start"].search("pub fn main() void {")
    assert ZIG_RULES["class_start"].search("const Point = struct {")

def test_zig_deep_structural_signatures_ambiguity():
    """
    Adversarial and deep case testing for the high-ambiguity signatures:
    branch, args, func_start, class_start, and structural_boundaries.
    """
    # 1. branch
    branch = ZIG_RULES["branch"]
    assert branch.search("if (x) {")
    assert branch.search("} else if (y) {")
    assert branch.search("for (items) |item| {")
    assert branch.search("while (true) : (i += 1) {")
    assert branch.search("try doSomething();")
    assert branch.search("catch |err| return err;")
    assert branch.search("const a = b orelse c;")
    assert branch.search("a && b")
    assert branch.search("a || b")
    
    # Negative (exact identifier escapes)
    assert not branch.search('const @"if" = 5;')
    assert not branch.search('const @"catch" = true;')
    
    # 2. args
    args = ZIG_RULES["args"]
    # Deep parens up to depth 4
    deep_args = 'fn max(a: typeof(foo(bar(baz())))) void {'
    m = args.search(deep_args)
    assert m and m.group(1) == "a: typeof(foo(bar(baz())))", "args regex should handle deep nested parens"
    
    # Missing delimiter (should not match endlessly or match invalid args)
    assert not args.search('fn broken(a: type, ')
    
    # 3. func_start
    func_start = ZIG_RULES["func_start"]
    # Weird modifier stacking and nested parens in attributes
    weird_func = 'pub inline extern "C" callconv(.C) align(@alignOf(T(u8, F(1)))) linksection(".text.(main)") fn @"my weird func"() void {'
    m = func_start.search(weird_func)
    assert m and m.group(1) == '@"my weird func"', "func_start should handle complex modifier stacking and deep parens in align()"
    
    # 4. class_start
    class_start = ZIG_RULES["class_start"]
    assert class_start.search('pub const Tuple = struct {')
    assert class_start.search('const @"My Tuple" = packed struct {')
    assert class_start.search('const State = enum(u8) {')
    assert class_start.search('const MyUnion = extern union {')
    assert class_start.search('const E = error {')
    assert class_start.search('const O = opaque {')
    
    # Negative (type info)
    assert not class_start.search('const Foo = @typeInfo(T).Struct;')
    
    # 5. structural_boundaries
    struct_bounds = ZIG_RULES["structural_boundaries"]
    assert struct_bounds.search('var x: i32 = 0;')
    assert struct_bounds.search('return 5;')
    assert struct_bounds.search('defer file.close();')
    assert struct_bounds.search('errdefer |err| log(err);')
    assert struct_bounds.search('unreachable;')
    assert struct_bounds.search('resume frame;')
    assert struct_bounds.search('suspend {}')
    assert struct_bounds.search('await p;')
    assert struct_bounds.search('usingnamespace std;')
    
    # Negative (exact identifier escapes)
    assert not struct_bounds.search('const @"var" = 5;')
    assert not struct_bounds.search('const @"return" = 5;')
