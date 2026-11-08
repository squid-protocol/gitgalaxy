"""#3772: a definition on the same line as its namespace / extern block opener is extracted."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from linear_assert import assert_linear


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


def test_long_unterminated_opener_is_linear():
    def make(k):
        return "namespace " + "a::" * (2500 * k) + " { " + "x " * (2500 * k) + "\n"

    assert_linear(_funcs, make(1), make(2))


class _FakeClock:
    """Deterministic clock: a function advances it by its declared cost, so no wall-clock jitter (#8132)."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _run(cost_of, noisy_first=0):
    clock = _FakeClock()
    calls = {"n": 0}

    def fn(n):
        calls["n"] += 1
        extra = 100.0 if calls["n"] <= noisy_first else 0.0
        clock.now += cost_of(n) + extra

    return lambda: assert_linear(fn, 3000, 6000, floor=0.0, timer=clock)


def test_assert_linear_passes_linear():
    _run(lambda n: n * 1e-6)()


def test_assert_linear_fails_quadratic_on_every_attempt():
    with pytest.raises(AssertionError, match="not linear"):
        _run(lambda n: n * n * 1e-9)()


def test_assert_linear_retries_a_noisy_sample():
    # first attempt: small run stalled less than large; later attempts clean
    _run(lambda n: n * 1e-6, noisy_first=0)()
    clock = _FakeClock()
    state = {"i": 0}

    def fn(n):
        state["i"] += 1
        # attempt 1 (calls 1-10): large runs are 5x; afterwards linear
        clock.now += n * 1e-6 * (5 if state["i"] <= 10 and n == 6000 else 1)

    assert_linear(fn, 3000, 6000, floor=0.0, timer=clock)
