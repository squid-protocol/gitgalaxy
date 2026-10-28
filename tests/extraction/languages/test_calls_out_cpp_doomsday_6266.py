"""
#6266: C++ call-graph classes found on Doomsday.

A `{}` default argument must not cut a constructor's member-init span, `d->import(...)` is a member call (not the
`import` keyword), `decltype(...)` inside a template argument still reads as a call, and a nested struct constructor
with a braced default argument is its own unit. Driven through `StructuralExtractor.splice()`.
"""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(code: str) -> dict[str, list[str]]:
    funcs = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in funcs}


def test_member_import_is_a_call():
    assert _functions("void A::f() {\n    d->import(x);\n}\n")["A::f"] == ["import"]


def test_decltype_template_argument_call():
    assert "convert" in _functions("void A::f() {\n    auto v = convert<decltype(a + b)>(c);\n}\n")["A::f"]


def test_brace_default_argument_keeps_constructor_body_calls():
    code = "A::A(const Foo &f = {}) : b(1) {\n    init();\n}\n"
    assert "init" in _functions(code)["A::A"]


def test_nested_constructor_with_braced_default_argument_is_a_unit():
    code = "struct S {\n    struct Line {\n        Line(const W &ln = {CString(), 0}, int n = 0) : x(n) { setup(); }\n    };\n};\n"
    assert any(name.endswith("Line") and "setup" in calls for name, calls in _functions(code).items())
