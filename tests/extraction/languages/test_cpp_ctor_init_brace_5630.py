"""
#5630: a C++ constructor whose member-initializer list holds a brace-init keeps its whole body.

`Impl(i) : Base(i), tags({"a", "b"}) { ... }` ended the unit at the brace-init's `{`, three lines in, so every
call in the body was credited to nobody (doomsday's `Impl` in packageswidget.cpp lost 60 edges). Driven through
`StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _ctor_calls(init: str) -> tuple[list[str], list[str]]:
    code = f"struct W : Base\n{{\n    W(int i)\n        : Base(i)\n{init}\n    {{\n        first();\n        second();\n    }}\n}};\n"
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    w = next(f for f in functions if f["name"] == "W")
    return w["calls_out_to"], [f["name"] for f in functions]


@pytest.mark.parametrize(
    "init",
    [
        '        , tags({"hidden", "core"})',
        "        , ids{1, 2}",
        "        , m(std::vector<int>{1, 2})",
        "        , cb([this]() { if (a) { run(); } })",
        '        , tags({"hidden"})\n        , ids{1, 2}\n        , n(3)',
    ],
)
def test_body_calls_survive_a_brace_init_in_the_initializer_list(init):
    calls, names = _ctor_calls(init)
    assert "first" in calls and "second" in calls
    assert names.count("W") == 1


def test_plain_initializer_list_is_unchanged():
    calls, _ = _ctor_calls("        , n(3)")
    assert calls[-2:] == ["first", "second"]


def test_default_argument_brace_init_keeps_the_body():
    code = "void f(Opts o = {}) {\n    first();\n    second();\n}\n"
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert next(f["calls_out_to"] for f in functions if f["name"] == "f") == ["first", "second"]
