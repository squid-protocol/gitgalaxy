"""
#6454: a C++ functional cast to a built-in type (`bool(x)`, `unsigned(n)`) is no call.

`bool can_expand = bool(EDITOR_GET(...))` listed `bool` as a callee of its unit. A cast to a type keyword
constructs nothing (like `int n(5)`, #3644); `operator bool()` and a real class constructor stay calls.
Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _callees(body: str) -> list[str]:
    code = "void A::f() {\n" + body + "\n}\n"
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f["calls_out_to"] for f in functions if f["name"] == "A::f")


@pytest.mark.parametrize(
    "keyword",
    ["bool", "int", "char", "float", "double", "long", "short", "unsigned", "signed", "wchar_t", "char16_t"],
)
def test_keyword_cast_is_not_a_callee(keyword):
    assert _callees(f"    auto v = {keyword}(inner());") == ["inner"]


def test_cast_in_condition_and_initializer():
    assert _callees("    bool b = bool(get());\n    if (!bool(check())) { go(); }") == ["get", "check", "go"]


def test_classes_and_identifier_typedefs_stay_calls():
    assert _callees("    auto a = Foo(g());\n    auto b = size_t(h());\n    auto c = uint32_t(k());") == [
        "Foo",
        "g",
        "size_t",
        "h",
        "uint32_t",
        "k",
    ]


def test_conversion_operator_call_stays_a_call():
    assert "bool" in _callees("    auto v = x.operator bool();")
