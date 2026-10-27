"""
#6266: a `\\`-continued C/C++ directive or `//` comment is blanked to its last line, like its one-line twin.

A function-local multi-line `#define` leaked its body's calls into the enclosing function (srb2
`P_PlayerWeaponPanelOrAmmoBurst`: `P_SpawnMobj`, `P_SetScale` in `DROP_WEAPON`) while the single-line form was
already blanked, so the engine's callees depended on how the macro was wrapped. Line numbers stay put.
Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(lang: str, code: str) -> dict:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_a_continued_define_body_is_no_call_of_the_enclosing_function(lang):
    code = (
        "void f(int t)\n{\n"
        "#define ONE(m) one(m)\n"
        "#define MANY(m) \\\n"
        "\tmany(m); \\\n"
        "\tmore(m)\n"
        "\tMANY(t);\n\tafter(t);\n}\n"
    )
    assert _units(lang, code)["f"]["calls_out_to"] == ["MANY", "after"]


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_the_lines_after_a_continued_directive_keep_their_numbers(lang):
    code = "#define A(x) \\\n  g(x) \\\n  h(x)\nvoid f(void)\n{\n  k();\n}\nvoid g2(void)\n{\n}\n"
    units = _units(lang, code)
    assert (units["f"]["start_line"], units["g2"]["start_line"]) == (4, 8)


def test_a_directive_with_a_lone_backslash_stops_at_its_line_and_crlf_continues():
    code = "void f(void)\n{\n#pragma once \\ not continued\n  real();\n#define A(x) \\\r\n  one(x)\n  last();\n}\n"
    assert _units("c", code)["f"]["calls_out_to"] == ["real", "last"]
