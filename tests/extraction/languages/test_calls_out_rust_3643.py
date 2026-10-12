"""
#3643 (contract C3 and its 2026-09-25 pattern amendment, docs/calls_out_rule_contract.md): rust's
calls_out. `\\b(name)\\s*\\(` missed macros (`format!(`, `vec![`) and turbofish calls
(`collect::<Vec<_>>()`), and counted tuple-struct patterns (`Ok(t) =>`, `if let Some(x) =`) as
calls. rust now uses `CALLS_OUT_RUST`; closure-trait bounds (`F: Fn(&T)`) are keywords (C2).

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_RUST, QUALIFIED_CALLS_OUT_PATTERNS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _functions(code: str) -> dict[str, dict]:
    functions = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _callees(text: str) -> list[str]:
    return [m.group(1) for m in CALLS_OUT_RUST.finditer(text)]


def test_rust_pattern_is_registered_and_used():
    assert CALLS_OUT_RUST in QUALIFIED_CALLS_OUT_PATTERNS
    assert LANGUAGE_DEFINITIONS["rust"]["rules"]["calls_out"] is CALLS_OUT_RUST


@pytest.mark.parametrize(
    "text, callees",
    [
        ("_ => unreachable!(),", ["unreachable"]),
        ('format_ident!("field{}", m)', ["format_ident"]),
        ("let v = vec![1, 2];", ["vec"]),
        ("quote! { #x }", ["quote"]),
        ("std::println!(\"{}\", x)", ["println"]),
    ],
)
def test_macro_is_a_call_to_its_name(text, callees):
    assert _callees(text) == callees


@pytest.mark.parametrize("text", ["macro_rules! foo {", "a != (b)", "if !(x) {"])
def test_macro_decoys(text):
    assert _callees(text) == []


@pytest.mark.parametrize(
    "text, callees",
    [
        ("xs.collect::<Vec<_>>()", ["collect"]),
        ("world.query::<&A>().iter(&world)", ["query", "iter"]),
        ("assert_all_sizes_equal::<&A, With<B>>(&mut world, 1);", ["assert_all_sizes_equal"]),
        ("m::<HashMap<K, Vec<V>>>()", ["m"]),
        ("size_of::<[u8; 32]>()", ["size_of"]),
    ],
)
def test_turbofish_call_is_captured(text, callees):
    assert _callees(text) == callees


@pytest.mark.parametrize(
    "text, callees",
    [
        ("Data::Struct(data) => (&data.fields, None),", []),
        ("Err(X::NotSpawned(err)) => {", []),
        ("Ok(t) => t,", []),
        ("Some(_) => assert_eq!(b.0, 1),", ["assert_eq"]),
        ("Some(1) | None => 0,", []),
        ("syn::Type::Array(_)\n        | syn::Type::TraitObject(_)\n        | syn::Type::Tuple(_) => {}", []),
        ("while let Some([mut a, mut b]) = it.next() {", ["next"]),
        ("if let Ok(inner) = self {", []),
        ("let Ok(mut e) = self.world.get(self.entity) else {", ["get"]),
        ("let Wrapper(inner) = w;", []),
    ],
)
def test_tuple_struct_pattern_is_not_a_call(text, callees):
    assert _callees(text) == callees


@pytest.mark.parametrize(
    "text, callees",
    [
        ("let s = Some(5);", ["Some"]),  # a constructor in an expression is a call (C3)
        ("self.state = State::Idle(x);", ["Idle"]),
        ("Some(x) if valid(x) => go(x),", ["valid", "go"]),  # the pattern goes, the guard's call stays
        ("Some(x) if x.is_empty() => 0,", ["is_empty"]),
        ("syn::Fields::Unnamed(fields) if fields.unnamed.len() == 1 => {", ["len"]),
        ("if f(a) == b {", ["f"]),
        ("a || Bar(2) || c", ["Bar"]),
        ("foo(a) >= b", ["foo"]),
        ("run(Foo(1))\n    if ready {", ["run", "Foo"]),  # only `|` may be on the next line
        ("Foo(1)\n    || Bar(2)", ["Foo", "Bar"]),
    ],
)
def test_expression_calls_stay(text, callees):
    assert _callees(text) == callees


def test_closure_trait_bounds_are_not_calls():
    code = "fn on_spawn<F>(f: F)\nwhere\n    F: Fn(&Meta) + Send,\n{\n    run(f);\n}\n"
    assert _functions(code)["on_spawn"]["calls_out_to"] == ["run"]


def test_shapes_reach_calls_out():
    code = (
        "fn derive(input: Input) -> Out {\n"
        "    let ids = input.items.iter().collect::<Vec<_>>();\n"
        "    match input.data {\n"
        "        Data::Struct(s) => build(s),\n"
        "        Data::Enum(_) => unreachable!(),\n"
        "    }\n"
        "}\n"
    )
    funcs = _functions(code)
    assert funcs["derive"]["calls_out_to"] == ["iter", "collect", "build", "unreachable"]


@pytest.mark.parametrize(
    "payload",
    [
        "A(" * 50000,
        "A" + "(" * 50000 + ")" * 50000,
        "a::<" * 50000,
        "a::<" + "<b" * 50000,
        "a::<" + "b" * 100000,
        "Some(" + "x" * 100000 + ")" + " )" * 20000,
        "A(x)" + " )" * 50000 + " =",
        "a!" + " " * 100000,
    ],
)
def test_rust_calls_out_redos_immunity(payload):
    assert_redos_immune(CALLS_OUT_RUST, payload, timeout_sec=3.0)
