"""#5629: a C/C++ unit's `calls_out_to` is collected from its body. The macro that defines a
macro-defined unit (`CCMD(map) {`, `CUSTOM_CVAR(...) {`) and a macro in the parameter list
(`TXT_UNCAST_ARG(x)`) are not calls; a macro called inside the body, and a call in a C++
constructor's initializer list, stay calls (#3327 C2, #3644)."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

LANGS = ("c", "cpp")


def _calls(lang: str, code: str) -> dict[str, list[str]]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f["calls_out_to"] for f in functions}


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize(
    ("src", "unit", "defining"),
    [
        ("#define CCMD(n) void ccmd_##n(void)\nCCMD(map)\n{\n\thelper(1);\n}\n", "map", "CCMD"),
        ("CCMD(map) {\n\thelper(1);\n}\n", "map", "CCMD"),
        ("CUSTOM_CVAR(Int, sv_x, 0, CVAR_ARCHIVE)\n{\n\thelper(1);\n}\n", "sv_x", "CUSTOM_CVAR"),
        ("CVAR_FUNC_IMPL(snd_nomusic)\n{\n\thelper(1);\n}\n", "snd_nomusic", "CVAR_FUNC_IMPL"),
    ],
)
def test_defining_macro_is_not_a_call(lang, src, unit, defining):
    calls = _calls(lang, src)[unit]
    assert defining not in calls
    assert calls == ["helper"]


@pytest.mark.parametrize("lang", LANGS)
def test_parameter_list_macro_is_not_a_call(lang):
    src = "void GenerateSizesTable(void *a, int b TXT_UNCAST_ARG(b))\n{\n\tother(b);\n}\n"
    assert _calls(lang, src)["GenerateSizesTable"] == ["other"]


@pytest.mark.parametrize("lang", LANGS)
def test_macro_called_in_the_body_stays_a_call(lang):
    src = "CCMD(map)\n{\n\tREAL_MACRO(2);\n\thelper(1);\n}\n"
    assert _calls(lang, src)["map"] == ["REAL_MACRO", "helper"]
    src = "void f(int b TXT_UNCAST_ARG(b))\n{\n\tTXT_UNCAST_ARG(b);\n}\n"
    assert _calls(lang, src)["f"] == ["TXT_UNCAST_ARG"]


def test_cpp_constructor_initializer_calls_stay():
    src = "Foo::Foo(int a TXT_UNCAST_ARG(a)) : x(MAKE_X(a)), y(b())\n{\n}\n"
    calls = _calls("cpp", src)
    (unit,) = calls
    assert "TXT_UNCAST_ARG" not in calls[unit]
    assert "MAKE_X" in calls[unit] and "b" in calls[unit]
