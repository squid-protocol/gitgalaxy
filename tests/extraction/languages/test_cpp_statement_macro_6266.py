"""
#6266: an indented ALL_CAPS statement macro is a call inside its function, never a function.

odamex `LoadResolvedFiles` holds `SERVER_ONLY(\n EXTERN_CVAR(x)\n if (a < 3) { .. } else { .. }\n)` and `Launch` holds
`AGOBJECT_FOREACH_CHILD(drv, &list, type)\n{ .. }`. The C++ rule read the first as a nested function named `SERVER_ONLY`
(the parenthesis in `if (a < 3)` balanced it) and the second as one named `AGOBJECT_FOREACH_CHILD`, which cut the
enclosing unit short. Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(lang: str, code: str) -> dict:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_a_statement_macro_wrapping_an_if_is_a_call_in_the_enclosing_function(lang):
    code = (
        "static void Load(int a)\n{\n\t::wad = a;\n\n\tSERVER_ONLY(\n\t\tEXTERN_CVAR(sv_cur)\n"
        "\t\tif (::wad.size() < 3)\n\t\t{\n\t\t\tsv_cur.ForceSet(\"\");\n\t\t}\n\t)\n\n\tDone();\n}\n"
    )
    units = _units(lang, code)
    assert list(units) == ["Load"]
    assert units["Load"]["calls_out_to"] == ["SERVER_ONLY", "EXTERN_CVAR", "size", "ForceSet", "Done"]


@pytest.mark.parametrize("lang", ["c", "cpp"])
def test_a_foreach_statement_macro_with_a_body_does_not_cut_the_unit(lang):
    code = (
        "int Launch()\n{\n\tint x;\n\n\tAGOBJECT_FOREACH_CHILD(drv, &agDrivers, ag_driver)\n\t{\n"
        "\t\tpost(drv);\n\t}\n\n\tSave();\n}\nint Other()\n{\n\treturn go();\n}\n"
    )
    units = _units(lang, code)
    assert list(units) == ["Launch", "Other"]
    assert units["Launch"]["calls_out_to"] == ["AGOBJECT_FOREACH_CHILD", "post", "Save"]
    assert units["Other"]["start_line"] == 12


def test_a_column_zero_function_macro_and_an_indented_constructor_stay_functions():
    code = (
        "TEST_CASE(Suite, Name)\n{\n\trun();\n}\n"
        "class Box\n{\npublic:\n\tBox(int n) { init(n); }\n\tBOX_RESET() { clear(); }\n};\n"
    )
    units = _units("cpp", code)
    assert "Name" in units
    assert "Box" in units
