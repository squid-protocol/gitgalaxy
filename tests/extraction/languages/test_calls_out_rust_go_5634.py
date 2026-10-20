"""
#5634: the Rust / Go call-graph shapes the DOOM-port body oracle found.

1. a Rust macro invocation `write!(f, ..)` is a call to the macro, never to a same-named `fn write`;
2. a Rust fn named like a keyword of another language (`def`) is still a callee, also inside `vec![..]`;
3. a Go generic instantiation `F[*T](x)` is a call; an index then a call (`fns[i](x)`) is not.

Driven through `StructuralExtractor.splice()` and `resolve_calls`, the paths a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_GO

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _go(text: str) -> list[str]:
    return [m.group(1) for m in CALLS_OUT_GO.finditer(text)]


_RUST = """
fn write() {}

fn def(a: u8, b: u8) -> u8 { a }

fn fmt(f: &mut F) -> R {
    write!(f, "x")?;
    std::write!(f, "y")?;
    write(1);
    Ok(())
}

fn only_macro(f: &mut F) -> R {
    write!(f, "x")
}

fn upload_ui(s: &S) -> U {
    U {
        pixels: as_u32_slice(s.pixels()),
        w: s.width(),
    }
}

fn lumps() {
    encode_texture_lumps(&[vec![def(1, 2)]]);
}
"""


def _sites(code: str, lang: str = "rust") -> list[dict]:
    funcs = list(StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"])
    return resolve_calls([{"path": "src/lib.rs", "lang_id": lang, "raw_imports": [], "functions": funcs}], [])[0]


def test_macro_invocation_carries_a_macro_qualifier():
    funcs = _functions("rust", _RUST)
    assert funcs["only_macro"]["calls_out_to"] == ["write"]
    assert funcs["only_macro"]["calls_out_qualifiers"] == {"write": ["!"]}
    assert funcs["fmt"]["calls_out_qualifiers"]["write"] == ["!", "!std", ""]


def test_macro_is_not_linked_to_a_same_named_fn_but_a_call_is():
    sites = [s for s in _sites(_RUST) if s["callee"] == "write"]
    by_src = {}
    for s in sites:
        by_src.setdefault(s["src_name"], []).append(s)
    assert [s["dst_name"] for s in by_src["only_macro"]] == [None]
    assert [s["dst_name"] for s in by_src["fmt"]] == ["write"]  # the plain `write(1)`, not the macros


def test_call_inside_a_struct_literal_and_a_macro_argument():
    funcs = _functions("rust", _RUST)
    assert "as_u32_slice" in funcs["upload_ui"]["calls_out_to"]
    assert {"width", "pixels"} <= set(funcs["upload_ui"]["calls_out_to"])
    assert funcs["lumps"]["calls_out_to"] == ["encode_texture_lumps", "vec", "def"]
    assert [s["dst_name"] for s in _sites(_RUST) if s["src_name"] == "lumps" and s["callee"] == "def"] == ["def"]


@pytest.mark.parametrize(
    "text, callees",
    [
        ("patch := w_CacheLumpNumT[*patch_t](lump)", ["w_CacheLumpNumT"]),
        ("Map[int, string](xs)", ["Map"]),
        ("New[pkg.T]()", ["New"]),
        ("Of[[]byte](b)", ["Of"]),
        ("Keys[map[string]int](m)", ["Keys"]),
        ("Gen[int](1)", ["Gen"]),
        ("Pair[K, V](a, b)", ["Pair"]),
        ("f(Gen[*T](x))", ["f", "Gen"]),
    ],
)
def test_go_generic_instantiation_is_a_call(text, callees):
    assert _go(text) == callees


@pytest.mark.parametrize("text", ["fns[i](y)", "m[k](v)", "xs[0:2](y)", "x := arr[*p]", "tbl[a.b]"])
def test_go_index_then_call_is_not_a_generic_call(text):
    assert _go(text) == []


def test_go_generic_call_reaches_calls_out():
    code = "package main\n\nfunc init_() {\n\tp := CacheLumpNumT[*patch_t](n)\n\tq := Gen[int, string](1)\n}\n"
    assert _functions("go", code)["init_"]["calls_out_to"] == ["CacheLumpNumT", "Gen"]


@pytest.mark.parametrize(
    "payload",
    [
        "a[" * 50000,
        "a[*" * 50000,
        "a[int" + "[x" * 50000,
        "a[" + "b," * 50000,
        "a[x." * 50000,
        "a[[]" * 30000 + "(",
        "a[" + "[" * 100000,
    ],
)
def test_go_generic_calls_out_redos_immunity(payload):
    assert_redos_immune(CALLS_OUT_GO, payload, timeout_sec=3.0)
