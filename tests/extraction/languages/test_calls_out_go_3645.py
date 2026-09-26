"""
#3645 (contracts C2, C3, docs/calls_out_rule_contract.md): two Go calls_out gaps.

1. `throw` sat in the global keyword ignore set, so go's runtime `throw("...")` (a real
   function, `runtime/panic.go`) was never a call. It now lives in the per-language set of
   each language where it is a keyword (C2: keywords are per language).
2. A conversion to a parenthesized type -- `(*T)(x)`, `(*unsafe.Pointer)(p)` -- is a call
   (C3), but `\\b(name)\\s*\\(` cannot see past the `)`. go now uses `CALLS_OUT_GO`.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import _CALLS_OUT_GLOBAL_IGNORE, StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_GO, QUALIFIED_CALLS_OUT_PATTERNS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def _callees(text: str) -> list[str]:
    return [m.group(1) for m in CALLS_OUT_GO.finditer(text)]


# ----------------------------------------------------------------------------- 1. throw


def test_go_throw_is_a_call():
    code = 'package runtime\n\nfunc gcMark(n int) {\n\tif n < 0 {\n\t\tthrow("gcMark: negative")\n\t}\n}\n'
    assert _functions("go", code)["gcMark"]["calls_out_to"] == ["throw"]


def test_throw_left_the_global_set():
    assert "throw" not in _CALLS_OUT_GLOBAL_IGNORE


# Every calls_out language where `throw` is a keyword keeps it out of calls_out_to.
_THROW_KEYWORD_LANGS = (
    "apex", "cpp", "csharp", "dart", "groovy", "java", "javascript", "kotlin", "livecode", "objective-c",
    "php", "powershell", "scala", "solidity", "swift", "typescript",
)  # fmt: skip


@pytest.mark.parametrize("lang", _THROW_KEYWORD_LANGS)
def test_throw_is_still_a_keyword_where_it_is_one(lang):
    assert "throw" in LANGUAGE_DEFINITIONS[lang]["rules"]["_calls_out_ignore"]


def test_cpp_throw_expression_is_not_a_call():
    code = "void f(int a) {\n    if (a) throw(Error(a));\n    g(a);\n}\n"
    assert _functions("cpp", code)["f"]["calls_out_to"] == ["Error", "g"]


def test_js_throw_is_not_a_call():
    code = "function f(a) {\n  if (a) throw(new Error(a));\n  return g(a);\n}\n"
    assert _functions("javascript", code)["f"]["calls_out_to"] == ["Error", "g"]


# ----------------------------------------------------------------------------- 2. conversions


def test_go_pattern_is_registered_and_used():
    assert CALLS_OUT_GO in QUALIFIED_CALLS_OUT_PATTERNS
    assert LANGUAGE_DEFINITIONS["go"]["rules"]["calls_out"] is CALLS_OUT_GO


@pytest.mark.parametrize(
    "text, callees",
    [
        ("(*gcBgMarkWorkerNode)(nodep)", ["gcBgMarkWorkerNode"]),
        ("p := (*uintptr)(unsafe.Pointer(x))", ["uintptr", "Pointer"]),
        ("(*unsafe.Pointer)(p)", ["Pointer"]),
        ("(Duration)(n)", ["Duration"]),
        ("return (*m)(unsafe.Pointer(old))", ["return", "m", "Pointer"]),  # `return (`: paren left for the prefix
        ("(**g)(add(p))", ["g", "add"]),
        ("(*[2]Timeval)(unsafe.Pointer(&tv[0]))", ["Timeval", "Pointer"]),
        ("return (*unsafeheader.String)(v.ptr).Data", ["return", "String"]),
        ("((*T)(p)).m()", ["T", "m"]),
        ("plain(x)", ["plain"]),
        ("f(g(x))", ["f", "g"]),
    ],
)
def test_conversion_is_captured(text, callees):
    assert _callees(text) == callees


@pytest.mark.parametrize(
    "text, callees",
    [
        ("h(next)(w, r)", ["h"]),  # a call of the returned func: `next` is an argument
        ("xs[i](y)", []),
        ("m[k](v)", []),
        ("(a + b)(c)", []),
        ("(*a).b(c)", ["b"]),
    ],
)
def test_a_closing_paren_is_not_a_conversion_prefix(text, callees):
    assert _callees(text) == callees


def test_conversion_reaches_calls_out_with_its_qualifier():
    code = (
        "package runtime\n\nfunc load(p unsafe.Pointer) uintptr {\n"
        "\tnode := (*gcBgMarkWorkerNode)(p)\n\tq := (*unsafe.Pointer)(p)\n\treturn *(*uintptr)(q)\n}\n"
    )
    funcs = _functions("go", code)
    assert funcs["load"]["calls_out_to"] == ["gcBgMarkWorkerNode", "Pointer", "uintptr"]
    assert funcs["load"]["calls_out_qualifiers"]["Pointer"] == ["unsafe"]
    assert funcs["load"]["calls_out_qualifiers"]["uintptr"] == [""]


@pytest.mark.parametrize(
    "payload",
    [
        "(" * 100000,
        "(*" * 50000,
        "(a." * 50000,
        "(" + "a" * 100000 + ")",
        "(*" + "a" * 100000 + ".b)(",
        "(a)" * 50000,
        "(*[" + "x" * 100000,
        "return " + " " * 100000 + "(",
        "(**[1]" * 20000,
    ],
)
def test_go_calls_out_redos_immunity(payload):
    assert_redos_immune(CALLS_OUT_GO, payload, timeout_sec=3.0)
