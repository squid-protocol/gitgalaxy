"""#3772: an out-of-line member of a class template is named `Class::member`, as the compiler reference names it."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _funcs(src):
    out = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(src, "")
    return {f["name"]: f for f in out["functions"]}


CASES = [
    ("template <typename T>\nvoid Foo<T>::bar(int x) {\n  helper(x);\n}\n", "Foo::bar"),
    ("template <typename T, typename U>\nint Pair<T, U>::sum() const {\n  return helper(1);\n}\n", "Pair::sum"),
    ("template <class T>\nvoid ns::Foo<T>::m() {\n  helper(1);\n}\n", "ns::Foo::m"),
    ("template <class T>\nvoid Foo<std::map<int, std::vector<int>>>::m() {\n  helper(1);\n}\n", "Foo::m"),
    ("template <class T>\nFoo<T>::Foo(int x) {\n  helper(x);\n}\n", "Foo::Foo"),
    ("template <class T>\nFoo<T>::~Foo() {\n  helper(1);\n}\n", "Foo::~Foo"),
    (
        "template <class T>\nbool Foo<T>::operator==(const Foo<T>& o) const {\n  return helper(1);\n}\n",
        "Foo::operator==",
    ),
    ("template <class T>\nT& Foo<T>::operator[](int i) {\n  return helper(i);\n}\n", "Foo::operator[]"),
    ("template <>\nvoid Foo<std::vector<int>>::m() {\n  helper(1);\n}\n", "Foo::m"),
]


@pytest.mark.parametrize("src,name", CASES)
def test_template_qualified_member_keeps_its_class(src, name):
    fns = _funcs(src)
    assert name in fns
    assert fns[name]["calls_out_to"] == ["helper"]  # its own header is no call to itself


@pytest.mark.parametrize(
    "src,name",
    [
        ("bool operator<(const A& a, const A& b) {\n  return helper(1);\n}\n", "operator<"),
        ("Stream& operator<<(Stream& s, int v) {\n  return helper(1);\n}\n", "operator<<"),
        ("void Baz::run() {\n  helper(2);\n}\n", "Baz::run"),
        ("template <class T>\nT freefn(T v) {\n  return helper(v);\n}\n", "freefn"),
    ],
)
def test_names_without_a_template_qualifier_are_unchanged(src, name):
    assert name in _funcs(src)


def test_a_call_to_another_object_of_the_same_name_is_kept():
    src = "template <class T>\nint Foo<T>::depth(int n) {\n  return n ? other.depth(n - 1) : 0;\n}\n"
    assert "depth" in _funcs(src)["Foo::depth"]["calls_out_to"]
