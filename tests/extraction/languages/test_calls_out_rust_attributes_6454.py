"""
#6454: `#` is not a Rust comment. An attribute on the same line as a statement (`#[cfg(unix)] f();`, a `cfg_if!` arm)
used to blank the rest of the line in the literal shield, dropping the call. The shield now reads only `//`, and the
calls_out rewrite blanks the attribute itself so `cfg` / `derive` are no calls.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards.languages.rust import _blank_binding_patterns

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import assert_redos_immune  # noqa: E402 # type: ignore


def _callees(body: str) -> list[str]:
    code = "fn t(x: E) -> bool {\n" + body + "\n}\n"
    functions = StructuralExtractor("rust", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == "t")["calls_out_to"]


@pytest.mark.parametrize(
    "body, callees",
    [
        ("#[cfg(unix)] f();", ["f"]),
        ("#[inline] f();", ["f"]),
        ("#[cfg(unix)]\nf();", ["f"]),
        ("#[cfg(unix)] { f() }", ["f"]),
        ("#![allow(unused)] f();", ["f"]),
        ("#[cfg(all(unix, not(test)))] f();", ["f"]),
        ('#[doc = "a ] b"] f();', ["f"]),
        ("let a = #[allow(x)] f();", ["f"]),
        ("cfg_if! { if #[cfg(unix)] { f() } else { g() } }", ["cfg_if", "f", "g"]),
        ("m! { #[cfg(unix)] f(); }", ["m", "f"]),
        ("#[cfg(a)] f(); #[cfg(b)] g();", ["f", "g"]),
        ("#[derive(Debug)] struct S; g();", ["g"]),
    ],
)
def test_calls_after_an_attribute_stay(body, callees):
    assert _callees(body) == callees


@pytest.mark.parametrize(
    "body",
    [
        "#[derive(Debug, Clone)]\nstruct S;",
        "#[cfg(unix)]\nf();",
        '#[cfg_attr(feature = "x", derive(Debug))] f();',
        "#[test_case(Foo(1))] f();",
    ],
)
def test_attribute_arguments_are_no_calls(body):
    assert not {"derive", "cfg", "cfg_attr", "Debug", "Clone", "test_case", "Foo"} & set(_callees(body))


@pytest.mark.parametrize(
    "body, callees",
    [
        ("// #[cfg(x)] h();\nf();", ["f"]),
        ('let s = r#"#[a] h()"#; f();', ["f"]),
        ("f(); // #[x] h()", ["f"]),
    ],
)
def test_comments_and_strings_still_blank(body, callees):
    assert _callees(body) == callees


def test_rewrite_keeps_length_and_newlines():
    src = "#[a(\n1)]\nf();"
    out = _blank_binding_patterns(src)
    assert len(out) == len(src) and out.count("\n") == src.count("\n") and "f();" in out


class _Rewrite:
    def search(self, text):
        _blank_binding_patterns(text)
        return None


@pytest.mark.parametrize(
    "payload",
    ["#[" * 50000, "#[a" + "[" * 50000, "#![" + "(" * 50000, "#[a(" * 30000 + "]", "#[a[b]" * 30000],
)
def test_attribute_redos_immunity(payload):
    assert_redos_immune(_Rewrite(), payload, timeout_sec=3.0)
