"""#3772: a definition on the same line as its namespace / extern block opener is extracted."""

import time

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _funcs(src):
    out = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(src, "")
    return {f["name"]: f for f in out["functions"]}


CASES = [
    ("namespace n { template<class T> T Box<T>::get() { return h(1); } }\n", "Box::get"),
    ("namespace n { void f() { h(1); } }\n", "f"),
    ("namespace a::b { int g(int x) { return h(x); } }\n", "g"),
    ("namespace a { namespace b { int g() { return h(1); } } }\n", "g"),
    ("namespace n { template<class T> Box<T>::Box() { h(1); } }\n", "Box::Box"),
    ("namespace n { bool Foo::operator==(const Foo& o) const { return h(1); } }\n", "Foo::operator=="),
    ("namespace { int anon() { return h(1); } }\n", "anon"),
]


@pytest.mark.parametrize("src,name", CASES)
def test_one_line_namespace_member_is_extracted(src, name):
    fns = _funcs(src)
    assert name in fns
    assert fns[name]["calls_out_to"] == ["h"]


def test_multi_line_namespace_is_unchanged():
    assert "Box::get" in _funcs("namespace n {\ntemplate<class T> T Box<T>::get() { return h(1); }\n}\n")


@pytest.mark.parametrize(
    "src",
    [
        "namespace n { int x = f(1); }\n",
        "namespace n { using std::swap; }\n",
        "namespace n { if (x) { h(1); } }\n",
    ],
)
def test_non_definitions_after_an_opener_yield_no_function(src):
    assert _funcs(src) == {}


def test_long_unterminated_opener_is_fast():
    t = time.time()
    _funcs("namespace " + "a::" * 5000 + " { " + "x " * 5000 + "\n")
    assert time.time() - t < 5
