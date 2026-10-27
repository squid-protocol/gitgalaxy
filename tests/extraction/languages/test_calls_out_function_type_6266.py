"""
#6266: `std::function<LoopResult (Item &)>` names a return type before a parameter list; it is no call to `LoopResult`
(doomsday: 80 engine-only edges `forAll -> LoopResult`).
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(code: str, unit: str) -> list[str]:
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == unit)["calls_out_to"]


@pytest.mark.parametrize(
    "code",
    [
        # a definition's parameter
        "LoopResult Chans::forAll(const std::function<LoopResult (Chan &)>& func) const\n{\n  return go(func);\n}\n",
        # a by-value parameter, `const` qualified function type, a nested template
        "LoopResult Chans::forAll(std::function<LoopResult (const Chan &) const> func)\n{\n  return go(func);\n}\n",
        # a local in the body
        "LoopResult Chans::forAll()\n{\n  std::function<LoopResult (Chan &)> f = pick();\n  return go(f);\n}\n",
        # an inline member with the type in the header and a different body
        "struct C {\n  inline LoopResult forAll(std::function<LoopResult (Chan &)> func) const {\n    return go(func);\n  }\n};\n",
    ],
)
def test_function_type_in_a_template_argument_is_no_call(code):
    calls = _calls(code, "forAll" if "struct C" in code else "Chans::forAll")
    assert "LoopResult" not in calls
    assert "go" in calls or "pick" in calls


@pytest.mark.parametrize(
    "code, callee",
    [
        ("void f(int a)\n{\n  x = a < g (a);\n}\n", "g"),
        ("void f(int a)\n{\n  h(a, LoopResult (a));\n}\n", "LoopResult"),
        ("void f(int a)\n{\n  v = std::max<int>(a, g (a));\n}\n", "g"),
    ],
)
def test_a_real_call_beside_angle_brackets_stays_a_call(code, callee):
    assert callee in _calls(code, "f")
