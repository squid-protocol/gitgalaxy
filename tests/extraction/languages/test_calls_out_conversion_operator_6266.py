"""
#6266: `operator String () const` names the type it converts to; it does not call `String`. A function type in a
template argument may carry a namespace qualifier (`std::function<de::LoopResult (Item &)>`).
(doomsday: `operator String -> String` x8, `forAllImpulseBindings -> LoopResult` x6.)
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(code: str, unit: str) -> list[str]:
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f for f in functions if f["name"] == unit)["calls_out_to"]


@pytest.mark.parametrize(
    "code, unit, ghost",
    [
        ("struct P {\n  inline operator String() const { return toString(); }\n};\n", "operator String", "String"),
        ("struct P {\n  inline operator CString() const { return toCString(); }\n};\n", "operator CString", "CString"),
        ("Id::operator String () const\n{\n  return asText();\n}\n", "Id::operator String", "String"),
        ("Id::operator Value::Number () const\n{\n  return asNumber();\n}\n", "Id::operator Value::Number", "Number"),
    ],
)
def test_a_conversion_operator_does_not_call_its_target_type(code, unit, ghost):
    calls = _calls(code, unit)
    assert ghost not in calls
    assert set(calls) & {"toString", "toCString", "asText", "asNumber"}


def test_a_call_to_the_type_inside_the_body_stays_a_call():
    code = "struct P {\n  operator String() const { return String(raw()); }\n};\n"
    assert "String" in _calls(code, "operator String")


@pytest.mark.parametrize("qualifier", ["", "de::", "a::b::"])
def test_a_qualified_function_type_argument_is_not_a_call(qualifier):
    code = (
        "struct B {\n  inline bool all(std::function<" + qualifier + "LoopResult (Item &)> func) const {\n"
        "    return all(-1, func);\n  }\n};\n"
    )
    calls = _calls(code, "all")
    assert "LoopResult" not in calls
