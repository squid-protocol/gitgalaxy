"""rust strict structural-signature coverage.

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


# ==============================================================================
# RUST: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #777, part of epic #518)
# ==============================================================================
# NOTE: filed as one of 6 new sub-issues (#773-778) after auditing and
# rejecting the epic's founding premise that C/C++/C#/COBOL/Rust/TypeScript
# already had adequate coverage -- see #518's updated "Why" section. This
# language previously had only one isolated regression test (the Rust half
# of test_thermodynamic_operator_collisions, covering bitwise_ops vs
# closures), not the full per-signature template.
RUST_RULES = LANGUAGE_DEFINITIONS["rust"]["rules"]

_RUST_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x > 0 {", "let x = 1;"),
    ("args", "fn foo(x: i32) {", "let x = 1;"),
    ("structural_boundaries", "let x = 1;", "x + 1;"),
    ("func_start", "fn foo() {}", "struct Foo {}"),
    ("class_start", "struct Foo {}", "fn foo() {}"),
    ("safety", "match x {", "let x = 1;"),
    ("safety_bypasses", "x.unwrap()", "let x = 1;"),
    ("high_risk_execution", 'panic!("oops")', "let x = 1;"),
    ("io", "std::fs::read(path)", "let x = 1;"),
    ("api", "pub fn foo() {}", "fn foo() {}"),
    ("state_mutation", "let mut x = 1;", "let x = 1;"),
    ("dead_code", "// fn foo() {}", "// just a note"),
    ("doc", "/// doc comment", "// just a note"),
    ("test", "assert!(x)", "let x = 1;"),
    ("concurrency", "async fn foo() {}", "fn foo() {}"),
    ("ui_framework", "html! { <div></div> }", "let x = 1;"),
    ("closures", "let f = |a| { a + 1 };", "let x = 1;"),
    ("globals", "lazy_static! { static ref X: u32 = 5; }", "let x = 1;"),
    ("decorators", "#[derive(Debug)]", "let x = 1;"),
    ("generics", "fn foo<T>(x: T) {}", "let x = 1;"),
    ("comprehensions", ".map(|x| x + 1)", "let x = 1;"),
    ("scientific", "let x: f64 = 1.0;", "let x = 1;"),
    ("reflection_metaprogramming", "macro_rules! foo {}", "let x = 1;"),
    ("import", "use std::collections::HashMap;", "let x = 1;"),
    ("ownership", "// Author: Jane Doe", "// just a note"),
    ("planned_debt", "// TODO: fix this", "// done"),
    ("fragile_debt", "// HACK: workaround", "// clean"),
    ("spec_exposure", "[SPEC-123]", "// just a note"),
    ("ssr_boundaries", "use actix_web::web;", "let x = 1;"),
    ("events", "let tx: Sender<i32>;", "let x = 1;"),
    ("dependency_injection", "use axum::extract::State;", "let x = 1;"),
    ("memory_alloc", "Box::new(x)", "let x = 1;"),
    ("telemetry", 'info!("msg")', 'println!("msg")'),
    ("debug_prints", 'println!("hi")', 'info!("msg")'),
    ("explicit_casts", "x as u32", "let x = 1;"),
    ("panics_and_aborts", 'panic!("oops")', "let x = 1;"),
    ("thread_sleeps", "std::thread::sleep(d)", "let x = 1;"),
    ("bitwise_ops", "x << 2", "let x = 1;"),
    ("sync_locks", "Mutex::new(x)", "let x = 1;"),
    ("immutability_locks", "const X: i32 = 1;", "let x = 1;"),
    ("cleanup", "drop(x)", "let x = 1;"),
    ("encapsulation", "pub(crate) fn foo() {}", "fn foo() {}"),
    ("listeners", ".subscribe(cb)", "let x = 1;"),
    ("test_skip", "#[ignore]", "let x = 1;"),
    ("inline_asm", 'asm!("nop")', "let x = 1;"),
    ("macros", "macro_rules! foo {}", "let x = 1;"),
    ("pointers", "let p: *const i32 = &x;", "let x = 1;"),
    ("serialization_parsing", "serde_json::from_str(s)", "let x = 1;"),
    ("regex_execution", "Regex::new(pattern)", "let x = 1;"),
    ("time_date_logic", "std::time::Instant::now()", "let x = 1;"),
    ("ipc_rpc_bridges", 'std::process::Command::new("ls")', "let x = 1;"),
]


@pytest.mark.parametrize("signature,positive,negative", _RUST_SIMPLE_CASES)
def test_rust_signature_positive_and_negative(signature, positive, negative):
    pattern = RUST_RULES[signature]
    assert pattern is not None, f"rust's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"rust {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), f"rust {signature!r} incorrectly matched an excluded case: {negative!r}"


def test_rust_dependency_capture_extracts_use_path_and_destructured_block():
    dep = RUST_RULES["_dependency_capture"]
    m = dep.search("use std::collections::HashMap;")
    assert m and m.group(1).strip() == "std::collections::HashMap"

    m2 = dep.search("use std::collections::{HashMap, HashSet};")
    assert m2 and m2.group(1).strip() == "std::collections::{HashMap, HashSet}"


def test_rust_func_start_excludes_structural_headers():
    func_start = RUST_RULES["func_start"]
    for excluded in ("struct Foo {", "enum Foo {", "union Foo {", "trait Foo {", "if (x) {", "for (;;) {"):
        assert not func_start.search(excluded), f"func_start incorrectly matched {excluded!r}"


def test_rust_func_start_macro_and_modifier_stacking():
    """
    Real Rust functions are frequently preceded by multiple attribute
    macros and stacked modifiers (pub/const/async/unsafe/extern), possibly
    spread across several lines.
    """
    func_start = RUST_RULES["func_start"]
    for line, name in [
        ("#[inline]\nfn foo() {}", "foo"),
        ("#[inline]\n#[must_use]\npub async fn foo() {}", "foo"),
        ("pub(crate) fn foo() {}", "foo"),
        ("const fn foo() {}", "foo"),
        ('extern "C" fn foo() {}', "foo"),
        ("unsafe fn foo() {}", "foo"),
    ]:
        m = func_start.search(line)
        assert m and m.group(1) == name, f"func_start failed on {line!r}"


def test_rust_macro_invocation_boundary_regression():
    """
    Real bugs found and fixed: Rust's macro-invocation syntax (`name!(...)`)
    means the literal `!` character is always immediately followed by `(`
    or whitespace/`{` in real code -- never a word character. Nine
    different rules shared a trailing `\\b` between these `!`-ending
    macro-name alternatives and word-ending siblings, so `\\b` could never
    fire, and NONE of the affected macros -- including some of the most
    common constructs in any real Rust file (`println!`, `panic!`,
    `assert!`, `dbg!`) -- ever matched.
    """
    old_patterns = {
        "high_risk_execution": re.compile(r"\b(panic!|todo!|unimplemented!|process::exit|abort)\b"),
        "test": re.compile(
            r"#\[(?:tokio::)?test\]|#\[cfg\(test\)\]|\b(?:assert!|assert_eq!|assert_ne!)\b|\b(?:describe|it|test)\s*\("
        ),
        "globals": re.compile(r"\b(static\s+mut|lazy_static!|OnceCell|OnceLock|LazyLock|std::env::var)\b"),
        "reflection_metaprogramming": re.compile(
            r"\b(macro_rules!|std::mem::transmute|Pin::|PhantomData|UnsafeCell)\b"
        ),
        "macros": re.compile(r"\b(macro_rules!|proc_macro|proc_macro_derive|proc_macro_attribute)\b"),
        "inline_asm": re.compile(r"\b(?:core::arch::asm!|std::arch::asm!|asm!|global_asm!)\b"),
        "telemetry": re.compile(r"\b(?:log::|tracing::)?(?:info!|warn!|error!|debug!|trace!|span!|instrument)\b"),
        "debug_prints": re.compile(r"\b(println!|print!|eprintln!|eprint!|dbg!)\b"),
        "panics_and_aborts": re.compile(r"\b(panic!|abort|process::exit|fatalError)\b"),
        "ui_framework": re.compile(r"\b(yew::|dioxus::|iced::|html!|rsx!|view!|slint|leptos::|tauri::)\b"),
    }
    realistic = {
        "high_risk_execution": 'panic!("oops")',
        "test": "assert!(x)",
        "globals": "lazy_static! { static ref X: u32 = 5; }",
        "reflection_metaprogramming": "macro_rules! foo { () => {}; }",
        "macros": "macro_rules! foo { () => {}; }",
        "inline_asm": 'asm!("nop")',
        "telemetry": 'info!("msg")',
        "debug_prints": 'println!("hi")',
        "panics_and_aborts": 'panic!("oops")',
        "ui_framework": "html! { <div></div> }",
    }

    for rule_name, old_pattern in old_patterns.items():
        text = realistic[rule_name]
        assert not old_pattern.search(text), f"sanity check: bug must reproduce for {rule_name} on {text!r}"
        assert RUST_RULES[rule_name].search(text), f"{rule_name} must now match {text!r}"

    # already-working, word-ending siblings in the same groups must still work
    assert RUST_RULES["high_risk_execution"].search("process::exit(1)")
    assert RUST_RULES["test"].search("#[test]")
    assert RUST_RULES["globals"].search("static mut X: u32 = 5;")
    assert RUST_RULES["reflection_metaprogramming"].search("std::mem::transmute(x)")
    assert RUST_RULES["macros"].search("#[proc_macro]")
    assert RUST_RULES["inline_asm"].search('core::arch::asm!("nop")')
    assert RUST_RULES["telemetry"].search("#[instrument]")
    assert RUST_RULES["panics_and_aborts"].search("abort()")
    assert RUST_RULES["ui_framework"].search("yew::Component")


def test_rust_dead_code_comment_style_completeness_regression():
    """
    Real bug found and fixed (Engine Rule 12): rust is `recursive_block`
    (both `//` and nested `/* */` are real comment styles), but dead_code
    only ever checked `//` -- a block-commented-out function/struct was
    invisible.
    """
    old_pattern = re.compile(r"//[ \t]*(?:fn|let|struct|impl|mod|use|match|for|while|loop|if|return)\b")
    realistic = "/* fn foo() {} */"
    assert not old_pattern.search(realistic), "sanity check: bug must reproduce against the old pattern"

    dead_code = RUST_RULES["dead_code"]
    assert dead_code.search(realistic)
    assert dead_code.search("// fn foo() {}"), "the already-working // form must still work"
    assert not dead_code.search("// just a note")


def test_rust_spec_exposure_redos_regression():
    """
    Real bug found and fixed: adjacent unbounded quantifiers with
    overlapping character sets (`\\d+` next to `[^\\]]*`) -- the same
    ReDoS shape already found and fixed independently in embedded_python,
    css, tcl, matlab, scheme, and typescript earlier in this epic (the
    7th language now).
    """
    assert_redos_immune(RUST_RULES["spec_exposure"], "[SPEC-1" + "1" * 100000, timeout_sec=3.0)
    assert RUST_RULES["spec_exposure"].search("[SPEC-123]")


def test_rust_func_start_nested_generic_bound_regression():
    """
    Real bug found and fixed (Rule 11, nested-delimiter coverage): the flat
    `[^>]*` generic step-over broke on nested angle brackets in a trait
    bound -- both one level (`fn foo<T: Into<String>>`) and two levels
    (`fn foo<T: Clone + Into<Vec<u8>>>`), both common realistic Rust
    patterns -- func_start silently failed to match the WHOLE function.
    Widened to tolerate two levels of self-nesting.
    """
    old_pattern = re.compile(
        r"^[ \t]*(?:#\[[^\]]*\][ \t\n]*){0,5}"
        r"(?:pub(?:\([^)]*\))?[ \t\n]+){0,3}"
        r"(?:(?:const|async|unsafe|extern(?:[ \t\n]+\"[^\"]*\")?)[ \t\n]+){0,3}"
        r"fn[ \t\n]+([a-zA-Z_]\w*)(?:[ \t\n]*<[^>]*>)?[ \t\n]*(?=\()",
        re.M,
    )
    for realistic in ("fn foo<T: Into<String>>(x: T) {}", "fn foo<T: Clone + Into<Vec<u8>>>(x: T) {}"):
        assert not old_pattern.search(realistic), f"sanity check: bug must reproduce for {realistic!r}"

    func_start = RUST_RULES["func_start"]
    m1 = func_start.search("fn foo<T: Into<String>>(x: T) {}")
    assert m1 and m1.group(1) == "foo"
    m2 = func_start.search("fn foo<T: Clone + Into<Vec<u8>>>(x: T) {}")
    assert m2 and m2.group(1) == "foo"
    # non-nested and no-generic forms must still work
    m3 = func_start.search("fn foo<T>(x: T) {}")
    assert m3 and m3.group(1) == "foo"
    m4 = func_start.search("fn foo(x: i32) {}")
    assert m4 and m4.group(1) == "foo"

    assert_redos_immune(func_start, "fn foo<" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(func_start, "fn foo<T: " + "<" * 100000, timeout_sec=3.0)


def test_rust_bitwise_ops_vs_closures_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in Rust
    itself: `|a| a + 1` miscounted as bitwise-OR -- confirmed with a
    dedicated regression test elsewhere in this file,
    `test_thermodynamic_operator_collisions`). Confirms it's absorbed into
    this language's full per-signature suite too.
    """
    closures = RUST_RULES["closures"]
    bitwise_ops = RUST_RULES["bitwise_ops"]

    closure = "let f = |a| { a + 1 };"
    assert closures.search(closure)
    assert not bitwise_ops.search(closure)

    shift = "a ^ b"
    assert bitwise_ops.search(shift)
    assert not closures.search(shift)


def test_rust_explicit_casts_vs_pointers_no_false_collision():
    """
    Known ambiguity pattern from the issue template (already found in C:
    cast syntax overlapping pointer-asterisk repetition). Rust's
    explicit_casts uses the `as <primitive>` keyword form and pointers
    uses `*const`/`*mut`/`NonNull`, structurally distinct -- no realistic
    overlap.
    """
    explicit_casts = RUST_RULES["explicit_casts"]
    pointers = RUST_RULES["pointers"]

    cast = "let y = x as u32;"
    assert explicit_casts.search(cast)
    assert not pointers.search(cast)

    raw_ptr = "let p: *const i32 = &x;"
    assert pointers.search(raw_ptr)
    assert not explicit_casts.search(raw_ptr)


def test_rust_intentional_double_classification_sweep():
    """
    Ambiguity sweep finding: several rust constructs legitimately fire two
    signatures representing different perspectives on the same underlying
    action -- intentional, not false collisions:
    - `pub fn foo() {}` -> api (public surface) + encapsulation (visibility
      modifier)
    - `struct Foo {}` -> class_start (entity declaration) +
      structural_boundaries (structural keyword)
    - `async fn foo() {}` -> concurrency (async marker) + func_start
    - `foo().await` -> concurrency + structural_boundaries
    - `const fn foo() {}` -> func_start + immutability_locks
    - `panic!(...)` -> high_risk_execution + panics_and_aborts
    - `*const i32` -> pointers (raw pointer type) + immutability_locks
      (bare `const` inside the pointer type)
    - `macro_rules! foo {}` -> macros + reflection_metaprogramming (Rust's
      macro system IS its metaprogramming system)
    """
    assert RUST_RULES["api"].search("pub fn foo() {}")
    assert RUST_RULES["encapsulation"].search("pub fn foo() {}")

    struct_decl = "struct Foo {}"
    assert RUST_RULES["class_start"].search(struct_decl)
    assert RUST_RULES["structural_boundaries"].search(struct_decl)

    async_fn = "async fn foo() {}"
    assert RUST_RULES["concurrency"].search(async_fn)
    assert RUST_RULES["func_start"].search(async_fn)

    await_expr = "foo().await;"
    assert RUST_RULES["concurrency"].search(await_expr)
    assert RUST_RULES["structural_boundaries"].search(await_expr)

    const_fn = "const fn foo() {}"
    assert RUST_RULES["func_start"].search(const_fn)
    assert RUST_RULES["immutability_locks"].search(const_fn)

    panic_call = 'panic!("oops")'
    assert RUST_RULES["high_risk_execution"].search(panic_call)
    assert RUST_RULES["panics_and_aborts"].search(panic_call)

    raw_ptr = "let p: *const i32 = &x;"
    assert RUST_RULES["pointers"].search(raw_ptr)
    assert RUST_RULES["immutability_locks"].search(raw_ptr)

    macro_def = "macro_rules! foo {}"
    assert RUST_RULES["macros"].search(macro_def)
    assert RUST_RULES["reflection_metaprogramming"].search(macro_def)


def test_rust_test_vs_test_skip_no_false_collision_on_dotted_skip():
    """
    Ambiguity sweep finding: `test`'s bare `test(` call-form alternative
    requires literal `(` immediately after (with optional whitespace), so
    it correctly does NOT fire on `test.skip(...)` (test_skip's territory)
    -- the `.` breaks the match.
    """
    skip_call = "test.skip(x)"
    assert not RUST_RULES["test"].search(skip_call)
    assert RUST_RULES["test_skip"].search(skip_call)


def test_rust_redos_immunity_sweep():
    """
    ReDoS immunity sweep across rust's remaining rules with unbounded-
    looking quantifiers, verified via a systematic scaling sweep
    (n=2000/4000/8000/16000/32000) before writing this test.
    """
    assert_redos_immune(RUST_RULES["args"], "fn foo(" + "a," * 50000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["args"], "|" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["class_start"], "pub struct " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["generics"], "<Foo" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["decorators"], "#[" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["_dependency_capture"], "use " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["import"], "use " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["doc"], "#[doc" + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["ownership"], "// Author: " + " " * 100000, timeout_sec=3.0)
    assert_redos_immune(RUST_RULES["cleanup"], "drop" + " " * 100000, timeout_sec=3.0)

    # sanity: all still match their real positive cases after the sweep
    assert RUST_RULES["func_start"].search("fn foo() {}")
    assert RUST_RULES["class_start"].search("struct Foo {}")
    assert RUST_RULES["debug_prints"].search('println!("hi")')

def test_rust_branch_deep_cases():
    """Deep case variants for 'branch' structural signature."""
    branch = RUST_RULES["branch"]
    # Positive deep cases
    assert branch.search("if let Some(x) = y {")
    assert branch.search("while let Ok(x) = stream.next().await {")
    assert branch.search("foo()?.bar()")
    assert branch.search("x && y || z")
    assert branch.search("break 'outer;")
    assert branch.search("continue 'inner;")
    assert branch.search("} else if {")
    # Negative deep cases (bugs we fixed)
    assert not branch.search("let r#match = 1;")
    assert not branch.search("let r#if = true;")
    assert not branch.search("'loop: {") # The 'loop itself shouldn't trigger branch
    assert not branch.search("T: ?Sized")

def test_rust_args_deep_cases():
    """Deep case variants for 'args' structural signature."""
    args = RUST_RULES["args"]
    # Positive deep cases
    assert args.search("fn foo<'a, T: Clone + Iterator<Item = String>>(x: i32, y: &mut T) {")
    assert args.search("let f = |x, y| x + y;")
    assert args.search("let g = move |x: i32| {")
    assert args.search("async fn do_work<const N: usize>(arr: [i32; N])")
    assert args.search("fn nested_parens(f: impl Fn(i32) -> i32) {")
    assert args.search("map(|x| x + 1)")
    # Negative deep cases
    assert not args.search("let x = a | b | c;")
    assert not args.search("if a | b | c {")

def test_rust_func_start_deep_cases():
    """Deep case variants for 'func_start' structural signature."""
    func_start = RUST_RULES["func_start"]
    # Positive deep cases
    assert func_start.search("pub(crate) async unsafe extern \"C\" fn do_stuff() {")
    assert func_start.search("#[inline(always)]\n#[no_mangle]\nfn foo() {")
    assert func_start.search("fn r#do() {")
    assert func_start.search("fn generic<T: Trait<Associated = <Type as Trait>::Assoc>>() {")
    assert func_start.search("extern \"system\" fn sys_call() {")
    # Negative deep cases
    assert not func_start.search("let fn_ptr = 1;")
    assert not func_start.search("struct fn_struct {}")

def test_rust_class_start_deep_cases():
    """Deep case variants for 'class_start' structural signature."""
    class_start = RUST_RULES["class_start"]
    # Positive deep cases
    assert class_start.search("pub(in crate::my_mod) struct Foo {")
    assert class_start.search("pub struct r#Struct {")
    assert class_start.search("unsafe trait Send {}")
    assert class_start.search("pub auto trait Send {}")
    assert class_start.search("pub unsafe auto trait Send {}")
    # Negative deep cases
    assert not class_start.search("let struct_name = 1;")
    assert not class_start.search("let trait_name = 1;")

def test_rust_structural_boundaries_deep_cases():
    """Deep case variants for 'structural_boundaries' structural signature."""
    sb = RUST_RULES["structural_boundaries"]
    # Positive deep cases
    assert sb.search("impl<T> Struct<T> where T: Clone {")
    assert sb.search("let ref mut x = 1;")
    assert sb.search("yield x;")
    assert sb.search("await")
    # Negative deep cases
    assert not sb.search("r#let")
    assert not sb.search("r#type")
    assert not sb.search("'yield")
