"""#3814: names follow Unicode UAX #31, not `[A-Za-z_]\\w*`. Part 4: C, C++, Objective-C and Go.

A unit named in Devanagari or Tamil (combining vowel signs and viramas, Mn/Mc), with a decomposed
accent, in Hangul, Han or with a non-ASCII capital is found whole -- never cut at its first combining
mark, nor missed for starting outside ASCII -- and a call to it is counted as a call to that name.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.core.wrapper_extractor import _CALLED, _DEFINE
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

NAMES = ["नाम", "பெயர்", "café", "cafe\u0301", "BELØP", "変数", "이름"]
_C = "int {n}(int env) {{\n    return env;\n}}\n\nint caller(int x) {{\n    return {n}(x);\n}}\n"
TEMPLATES = {
    "c": _C,
    "cpp": _C,
    "objective-c": _C,
    "go": "func {n}(env int) int {{\n    return env\n}}\n\nfunc caller(x int) int {{\n    return {n}(x)\n}}\n",
}
PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _functions(lang: str, code: str) -> list[dict]:
    streams = PRISM.split_streams(code, lang)
    out = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(
        code_stream=streams["code_stream"], comment_stream=streams["comment_stream"], confidence=1.0
    )
    return out["functions"]


@pytest.mark.parametrize("lang", sorted(TEMPLATES))
@pytest.mark.parametrize("n", NAMES)
def test_a_unicode_named_unit_is_found_whole_and_its_call_counted(lang, n):
    functions = _functions(lang, TEMPLATES[lang].format(n=n))
    assert [f["name"] for f in functions] == [n, "caller"]
    assert functions[1]["calls_out_to"] == [n]


@pytest.mark.parametrize("n", ["नाम", "~変数"])
def test_a_cpp_method_and_destructor_named_in_unicode_are_found(n):
    code = f"Widget::{n}() {{\n    reset();\n}}\n"
    assert f"Widget::{n}" in [f["name"] for f in _functions("cpp", code)]


def test_an_objective_c_method_named_in_devanagari_is_found_whole():
    code = "@implementation Box\n- (int)नाम:(int)env {\n    return env;\n}\n@end\n"
    assert "नाम" in [f["name"] for f in _functions("objective-c", code)]


def test_a_unicode_named_macro_alias_is_read_whole():
    m = _DEFINE.search("#define नाम(x) பெயர்(x)\n")
    assert m and m.group(1) == "नाम"
    assert [c.group(1) for c in _CALLED.finditer(m.group(3))] == ["பெயர்"]
