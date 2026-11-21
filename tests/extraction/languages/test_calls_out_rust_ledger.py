"""
Regression tests for Rust call-graph comparison ledger cells:
- Tuple-struct declarations inside a function body (`struct QueryDataA(Entity, &'static A);`)
  are declarations (C5), not calls.
- Match/select arm tuple patterns nested 4 parens deep
  (`(Some((untagged_tokens, ())), Some((tag_tokens, _)), None) =>`) are patterns (C3), not calls.
- Type-position macro invocations inside `fn` parameter lists (`Token![,]`, `syn::Token![+]`)
  remain calls (C3) even while parameter patterns and `Fn(...)` bounds stay blanked.
- Macro invocations inside a turbofish (`input.parse::<Token![+]>()`) are not swallowed by the
  enclosing turbofish match: both `parse` and `Token` are extracted.
"""

import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_RUST
from gitgalaxy.standards.language_standards.languages.rust import _ARM_PATTERN

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _calls(code: str, fn_name: str) -> list[str]:
    units = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(u for u in units if u["name"].split("::")[-1] == fn_name)["calls_out_to"]


def test_nested_tuple_struct_declaration_is_not_a_call():
    code = (
        "fn test_structs() {\n"
        "    struct QueryDataA(Entity, &'static A);\n"
        "    struct Newtype(bool);\n"
        "    let x = Newtype(true);\n"
        "    consume(x);\n"
        "}\n"
    )
    calls = _calls(code, "test_structs")
    assert "QueryDataA" not in calls
    assert "Newtype" in calls
    assert "consume" in calls


def test_deep_nested_tuple_match_arm_pattern_is_not_a_call():
    code = (
        "fn decide_tag(a: Opt, b: Opt, c: Opt) -> Tag {\n"
        "    match (a.get(), b.get(), c.get()) {\n"
        "        (None, None, None) => Tag::External,\n"
        "        (Some((untagged_tokens, ())), Some((tag_tokens, _)), None) => {\n"
        "            report(untagged_tokens, tag_tokens);\n"
        "            Tag::External\n"
        "        }\n"
        "        _ => Tag::None,\n"
        "    }\n"
        "}\n"
    )
    calls = _calls(code, "decide_tag")
    assert "Some" not in calls
    assert "get" in calls
    assert "report" in calls


def test_fn_param_macro_invocation_is_kept_while_patterns_and_fn_bounds_stay_dropped():
    code = (
        "fn enum_from_ast<'a>(\n"
        "    Wrapper(cx): Wrapper,\n"
        "    variants: &'a Punctuated<syn::Variant, Token![,]>,\n"
        "    cb: impl Fn(u8) -> u8,\n"
        ") {\n"
        "    process(variants);\n"
        "}\n"
    )
    calls = _calls(code, "enum_from_ast")
    assert "Token" in calls
    assert "process" in calls
    assert "Wrapper" not in calls
    assert "Fn" not in calls


def test_macro_inside_turbofish_is_captured_alongside_outer_call():
    code = "fn parse_lifetimes(input: ParseStream) -> Result<()> {\n    input.parse::<Token![+]>()?;\n    Ok(())\n}\n"
    calls = _calls(code, "parse_lifetimes")
    assert "parse" in calls
    assert "Token" in calls
    assert "Ok" in calls


def test_rust_ledger_patterns_are_redos_immune():
    assert_redos_immune(CALLS_OUT_RUST, "f::<" + "<" * 80 + "a" * 80, timeout_sec=3.0)
    assert_redos_immune(_ARM_PATTERN, "{ " + "(" * 40 + "A" * 40, timeout_sec=3.0)
