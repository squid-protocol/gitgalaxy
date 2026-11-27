"""SOP-002-v1 gap-cell decoy suite for Rust (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)

Covers the three code-stream families that had a rule in rust.py but no decoy row in
tests/family_validity_baseline.json: encapsulation, import, inline_asm. Every check runs through the real
Prism.split_streams() + StructuralExtractor.splice() pipeline.

Rust comment forms (Rust reference, "Comments"): `//` line, `///` outer line doc, `//!` inner line doc, `/* */`
block, `/** */` outer block doc, `/*! */` inner block doc, and block comments NEST (`/* /* */ */`). Raw strings
(`r#"..."#`) and char literals (`'"'`) can hold comment-looking text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import family_decoy_runner as fdr
import family_validity_chart as fvc

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor("rust", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "rust")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


RUST_FAMILIES: dict[str, str] = {
    "encapsulation": "pub(crate) fn helper() {}",
    "import": "use std::collections::HashMap;",
    "inline_asm": 'unsafe { asm!("nop"); }',
}

# G6: strings holding the keyword count today (#2535, by design).
RUST_STRING_COUNTS: dict[str, bool] = {"encapsulation": True, "import": True, "inline_asm": True}


def test_rust_gap_cells_are_defined_code_stream_families():
    families, _, defined = fvc.engine_grid()
    expected = (defined["rust"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(RUST_FAMILIES) <= expected
    assert set(RUST_STRING_COUNTS) == set(RUST_FAMILIES)


def test_rust_baseline_has_sop002_row_for_each_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["rust"]
    for family in RUST_FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family


@pytest.mark.parametrize(("family", "snippet"), sorted(RUST_FAMILIES.items()))
def test_rust_positive_control_and_all_spec_comment_forms(family: str, snippet: str):
    # G1
    assert _hits(family, snippet + "\n") >= 1, f"G1 failed for rust.{family}: {snippet!r}"
    # Req A: line, outer doc, inner doc
    for opener in ("//", "///", "//!"):
        assert _hits(family, f"{opener} {snippet}\n") == 0, f"{opener} leak for rust.{family}"
        assert _hits(family, f"    {opener} {snippet}\n") == 0, f"indented {opener} leak for rust.{family}"
    # block, outer block doc, inner block doc: single-line and multi-line
    for opener in ("/*", "/**", "/*!"):
        assert _hits(family, f"{opener} {snippet} */\n") == 0, f"{opener} */ leak for rust.{family}"
        assert _hits(family, f"{opener}\n{snippet}\n*/\n") == 0, f"multi-line {opener} leak for rust.{family}"
    assert _hits(family, f"/*\n * {snippet}\n */\n") == 0, f"starred block leak for rust.{family}"
    # NESTED block comments (spec: they nest): the first `*/` must not end the outer comment
    assert _hits(family, f"/* outer /* inner */ {snippet} */\n") == 0, f"nested leak for rust.{family}"
    assert _hits(family, f"/* outer\n/* inner */\n{snippet}\n*/\n") == 0, f"nested multi-line leak for rust.{family}"
    assert _hits(family, f"/* a /* b /* c */ d */ {snippet} */\n") == 0, f"3-deep nested leak for rust.{family}"
    assert _hits(family, f"/* a /* b */ /* c */ {snippet} */\n") == 0, f"sibling nested leak for rust.{family}"
    # inline trailing forms (delta over a sentinel)
    base = _hits(family, "let x = 1; // SENTINEL_NOOP\n")
    assert _hits(family, f"let x = 1; // {snippet}\n") <= base, f"trailing // leak for rust.{family}"
    assert _hits(family, f"let x = 1; /// {snippet}\n") <= base, f"trailing /// leak for rust.{family}"
    base = _hits(family, "let x = 1; /* SENTINEL_NOOP */\n")
    assert _hits(family, f"let x = 1; /* {snippet} */\n") <= base, f"trailing block leak for rust.{family}"
    assert _hits(family, f"let x = 1; /* a /* b */ {snippet} */\n") <= base, f"trailing nested leak for rust.{family}"
    # G6 boundary: comment markers inside string, raw string and char literals
    for prefix in (
        'let s = "http://x";',
        'let s = "a \\" b";',
        'let s = r#"http://x"#;',
        "let c = '\"';",
        "let c = '/';",
    ):
        base = _hits(family, f"{prefix} // SENTINEL_NOOP\n")
        assert _hits(family, f"{prefix} // {snippet}\n") <= base, f"string-comment leak for rust.{family}: {prefix}"
        base = _hits(family, f"{prefix} /* SENTINEL_NOOP */\n")
        assert _hits(family, f"{prefix} /* {snippet} */\n") <= base, f"string-block leak for rust.{family}: {prefix}"


@pytest.mark.xfail(strict=True, reason="https://github.com/squid-protocol/gitgalaxy/issues/9461")
@pytest.mark.parametrize(("family", "snippet"), sorted(RUST_FAMILIES.items()))
def test_rust_slash_star_slash_opens_a_comment(family: str, snippet: str):
    """`/*/` opens a block comment (the `/` is ordinary text), so everything up to `*/` is comment."""
    assert _hits(family, f"/*/ {snippet} */\n") == 0


@pytest.mark.parametrize(("family", "snippet"), sorted(RUST_FAMILIES.items()))
def test_rust_comment_openers_in_other_forms_do_not_swallow_code(family: str, snippet: str):
    """A `//` line cannot open a block, an empty `/**/` closes itself, a raw string holding `/*` opens nothing."""
    assert _hits(family, f"// /*\n{snippet}\n") >= 1
    assert _hits(family, f"/* // */\n{snippet}\n") >= 1
    assert _hits(family, f"/**/\n{snippet}\n") >= 1
    assert _hits(family, f"/* a /* b */ c */\n{snippet}\n") >= 1  # balanced nesting closes fully, code after is live
    assert _hits(family, f'let r = r#"/*"#;\n{snippet}\n') >= 1
    assert _hits(family, f"let c = '\"';\n{snippet}\n") >= 1
    assert _hits(family, f"fn f<'a>(x: &'a str) {{}}\n{snippet}\n") >= 1


@pytest.mark.parametrize(("family", "snippet"), sorted(RUST_FAMILIES.items()))
def test_rust_string_literal_behaviour(family: str, snippet: str):
    """G6: record what a string holding the keyword does (#2535: strings count by design)."""
    quoted = snippet.replace('"', '\\"')
    assert (_hits(family, f'let s = "{quoted}";\n') >= 1) is RUST_STRING_COUNTS[family]


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # every literal arm can fire
        ("encapsulation", "pub(super) struct S;\n"),
        ("encapsulation", "pub(self) fn f() {}\n"),
        ("import", "pub use std::io::Read;\n"),
        ("import", "use std::{io, fs};\n"),
        ("import", "use std::{\n    io,\n    fs,\n};\n"),
        ("import", "pub(crate) use crate::a::B;\n"),
        ("inline_asm", 'core::arch::asm!("nop");\n'),
        ("inline_asm", 'core::arch::global_asm!(".global x");\n'),
        ("inline_asm", 'core::arch::naked_asm!("ret");\n'),
        ("inline_asm", 'std::arch::asm!("nop");\n'),
        ("inline_asm", 'std::arch::global_asm!(".global x");\n'),
        ("inline_asm", 'std::arch::naked_asm!("ret");\n'),
        ("inline_asm", 'global_asm!(".global x");\n'),
        ("inline_asm", 'naked_asm!("ret");\n'),
        ("inline_asm", 'llvm_asm!("nop");\n'),
    ],
)
def test_rust_every_authentic_arm_fires(family: str, src: str):
    assert _hits(family, src) >= 1


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req B: identifier-embedded and prefixed forms of every literal arm
        ("encapsulation", "my_pub(crate) fn f() {}\n"),
        ("encapsulation", "xpub(crate) fn f() {}\n"),
        ("encapsulation", "pub(crates) fn f() {}\n"),
        ("encapsulation", "pub(crate_x) fn f() {}\n"),
        ("encapsulation", "pub(supers) fn f() {}\n"),
        ("encapsulation", "pub(selfish) fn f() {}\n"),
        ("import", "my_use std::io;\n"),
        ("import", "reuse std::io;\n"),
        ("import", "use_it std::io;\n"),
        ("import", "unused std::io;\n"),
        ("inline_asm", "my_asm!(x);\n"),
        ("inline_asm", "asm_x!(x);\n"),
        ("inline_asm", "my_global_asm!(x);\n"),
        ("inline_asm", "my_naked_asm!(x);\n"),
        ("inline_asm", "my_llvm_asm!(x);\n"),
        ("inline_asm", "asm(x);\n"),
        ("inline_asm", "mycore_arch::asm_x!(x);\n"),
    ],
)
def test_rust_all_branch_word_boundaries(family: str, src: str):
    assert _hits(family, src) == 0


@pytest.mark.parametrize("src", ['other::asm!("x");\n', 'x86::asm!("x");\n', 'mycore::arch::asm!("nop");\n'])
def test_rust_inline_asm_any_path_qualified_asm_macro_counts(src: str):
    """Documented current behaviour, not a defect filed: the bare `\\basm!` arm matches after any `::`.

    `use core::arch::asm;` makes the bare form legitimate, and a re-export (`crate::asm!`) is the same macro, so the
    lexer cannot tell `other::asm!` from the std one without name resolution.
    """
    assert _hits("inline_asm", src) == 1


@pytest.mark.parametrize(
    ("family", "src"),
    [
        # Req D: contract negatives written in Rust syntax
        # encapsulation C3: bare `pub` is the PUBLIC side (api's token), never a hiding marker
        ("encapsulation", "pub fn f() {}\n"),
        ("encapsulation", "fn f() {}\n"),
        ("encapsulation", "pub struct S { pub x: i32 }\n"),
        # import: a word that merely contains `use`, or other item kinds
        ("import", "let used = 1;\n"),
        ("import", "#![allow(unused_imports)]\n"),
        ("import", "extern crate std;\n"),
        ("import", "mod foo;\n"),
        ("import", "fn f() -> impl Sized + use<'a> { 0 }\n"),
        # inline_asm: importing or naming the macro is not its opener (count contract corollary 1)
        ("inline_asm", "use core::arch::asm;\n"),
        ("inline_asm", "let asm = 1;\n"),
        ("inline_asm", "#[naked]\nfn f() {}\n"),
        ("inline_asm", "let _ = core::arch::x86_64::_mm_pause();\n"),
    ],
)
def test_rust_cross_family_negative_controls(family: str, src: str):
    assert _hits(family, src) == 0
