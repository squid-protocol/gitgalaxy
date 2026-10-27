"""
#6266: a default argument is evaluated at the caller, so a call written in a parameter list is no call of the unit
(doomsday: ~30 engine-only edges, `ActionItem -> RefArg`, `Status -> invalidTime`, `mid -> max`).
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(code: str, unit: str) -> list[str]:
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == unit)["calls_out_to"]


@pytest.mark.parametrize(
    "code, unit",
    [
        # an inline constructor: a constructed temporary, then a mem-initializer
        ('struct A {\n  A(const String &l = "", RefArg<Action> a = RefArg<Action>())\n    : Base(l) { setup(a); }\n};\n', "A"),
        # a function-call default after a plain one
        ("struct S {\n  S(int n = 0, const Time &t = Time::invalidTime()) : size(n) { setup(t); }\n};\n", "S"),
        # a template argument with a comma inside a default, and a later default
        (
            "struct L {\n  List mid(size_t p, size_t c = std::numeric_limits<size_t>::max(), int d = mx(1)) const\n"
            "  { return setup(p); }\n};\n",
            "mid",
        ),
        # an out-of-line definition
        ("void K::run(int a = pick(), int b = 2)\n{\n  setup(a);\n}\n", "K::run"),
    ],
)
def test_a_default_argument_call_is_not_a_call_of_the_unit(code, unit):
    calls = _calls(code, unit)
    assert "setup" in calls
    assert not {"RefArg", "invalidTime", "max", "mx", "pick"} & set(calls)


@pytest.mark.parametrize(
    "code, unit, callee",
    [
        # the body's own call, and a comparison in the parameter list, are not defaults
        ("void f(int a)\n{\n  int b = g(a);\n  h(b = k(a));\n}\n", "f", "k"),
        ("bool Op::operator()(int a = 1) const\n{\n  return g(a);\n}\n", "Op::operator()", "g"),
        ("void f(int (*cb)(int) = nullptr, int n = 3)\n{\n  cb(n);\n  g(n);\n}\n", "f", "g"),
    ],
)
def test_a_body_call_beside_defaults_stays_a_call(code, unit, callee):
    assert callee in _calls(code, unit)
