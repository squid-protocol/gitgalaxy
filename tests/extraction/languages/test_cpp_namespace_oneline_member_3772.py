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


def _best_of(fn, arg, runs: int = 3) -> float:
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        fn(arg)
        best = min(best, time.perf_counter() - start)
    return best


def _assert_linear(fn, make) -> None:
    # #7792: an absolute wall-clock bound flaked on CI; doubling the input must not quadruple the time.
    small, large = _best_of(fn, make(1)), _best_of(fn, make(2))
    assert large < max(small * 3.2, 0.5)


def test_long_unterminated_opener_is_linear():
    _assert_linear(_funcs, lambda k: "namespace " + "a::" * (2500 * k) + " { " + "x " * (2500 * k) + "\n")
