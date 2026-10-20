"""#5628 (part 2): a scoped unit's call to a DIFFERENT unit of the same leaf name is a call
(`Scope::f` -> free `f`, C# `IEnumerable.GetEnumerator` -> `GetEnumerator`). Self-recursion
stays dropped (#3327), as do nested declarations (#3360) and `this->f(` / `Scope::f(`."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _fns(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def test_cpp_scoped_unit_calling_free_function_keeps_the_edge():
    src = "void f(int a) {\n  g(a);\n}\nvoid Scope::f(int a) {\n  f(a);\n}\n"
    fns = _fns("cpp", src)
    assert fns["Scope::f"]["calls_out_to"] == ["f"]
    assert fns["Scope::f"]["calls_out_qualifiers"] == {"f": [""]}
    assert fns["f"]["calls_out_to"] == ["g"]  # the free f's own recursion-free body


def test_cpp_scoped_unit_with_no_other_unit_is_recursion():
    assert _fns("cpp", "void Scope::f(int a) {\n  f(a);\n}\n")["Scope::f"]["calls_out_to"] == []


def test_cpp_explicit_self_references_stay_dropped():
    src = "void f() {}\nvoid Scope::f(int a) {\n  this->f(a);\n  Scope::f(a);\n}\n"
    assert _fns("cpp", src)["Scope::f"]["calls_out_to"] == []


def test_cpp_receiver_call_to_same_name_was_and_stays_a_call():
    src = "void Scope::f(int a) {\n  child->f(a);\n}\n"
    assert _fns("cpp", src)["Scope::f"]["calls_out_to"] == ["f"]


def test_cpp_other_class_unit_is_not_reachable_by_a_bare_name():
    src = "void Other::f() {\n}\nvoid Scope::f(int a) {\n  f(a);\n}\n"
    assert _fns("cpp", src)["Scope::f"]["calls_out_to"] == []


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_direct_recursion_stays_dropped(lang):
    src = "int r(int n) {\n  return r(n - 1) + helper(n);\n}\n"
    assert _fns(lang, src)["r"]["calls_out_to"] == ["helper"]


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_free_function_does_not_gain_an_edge_from_a_scoped_namesake(lang):
    src = "void f(int a) {\n  f(a);\n}\n"
    assert _fns(lang, src)["f"]["calls_out_to"] == []


def test_csharp_explicit_interface_impl_calls_the_same_named_method():
    src = (
        "class A : IEnumerable {\n"
        "  public IEnumerator GetEnumerator() { return null; }\n"
        "  IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();\n"
        "  int Rec(int n) { return Rec(n - 1); }\n"
        "}\n"
    )
    fns = _fns("csharp", src)
    assert fns["IEnumerable.GetEnumerator"]["calls_out_to"] == ["GetEnumerator"]
    assert fns["Rec"]["calls_out_to"] == []
    assert fns["GetEnumerator"]["calls_out_to"] == []


def test_csharp_explicit_interface_impl_without_a_namesake_is_recursion():
    src = "class A : IEnumerable {\n  IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();\n}\n"
    assert _fns("csharp", src)["IEnumerable.GetEnumerator"]["calls_out_to"] == []


def test_nested_declaration_shapes_are_still_dropped():
    py = "def outer(x):\n    def inner(y):\n        return y\n    return inner\n"
    assert "inner" not in _fns("python", py)["outer"]["calls_out_to"]
    js = "function outer() {\n  function inner() { return 1; }\n  return helper();\n}\n"
    assert _fns("javascript", js)["outer"]["calls_out_to"] == ["helper"]
