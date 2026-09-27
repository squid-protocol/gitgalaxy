"""#3814: names follow Unicode UAX #31, not `[A-Za-z_]\\w*`.

Python, Java, JavaScript and TypeScript units named in Devanagari (combining vowel signs and
viramas, Mn/Mc), Tamil, a decomposed accent (`e` + U+0301) and a ZWJ conjunct (`क्‍ष`) are found
whole; a Unicode-named def's parameters stay parameters (not references); the wrapper census
sees Unicode-named calls; and a joiner after a virama is spelling, not "invisible Unicode".
"""

import re

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.core.wrapper_extractor import _UNQUALIFIED_CALL
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE, ID_START, NAME, VIRAMA

NAMES = ["नाम", "பெயர்", "café", "café", "क्‍ष", "BELØP", "変数", "이름"]
TEMPLATES = {
    "python": "def {n}(env):\n    return env\n",
    "java": "class T {{\n    public int {n}(int env) {{\n        return env;\n    }}\n}}\n",
    "javascript": "function {n}(env) {{\n    return env;\n}}\n",
    "typescript": "function {n}(env: number): number {{\n    return env;\n}}\n",
}
PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _functions(lang: str, code: str) -> list[dict]:
    streams = PRISM.split_streams(code, lang)
    out = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(
        code_stream=streams["code_stream"], comment_stream=streams["comment_stream"], confidence=1.0
    )
    return out["functions"]


def test_the_classes_follow_uax31():
    name = re.compile(NAME)
    assert all(name.fullmatch(n) for n in NAMES)
    assert not name.fullmatch("1abc") and not name.fullmatch("a-b")
    assert re.fullmatch(f"[{ID_CONTINUE}]", "ा")  # a Devanagari vowel sign (Mc): not in \w
    assert not re.fullmatch(f"[{ID_START}]", "ा")  # ...and it cannot lead
    assert re.fullmatch(f"[{VIRAMA}]", "्") and not re.fullmatch(f"[{VIRAMA}]", "a")


@pytest.mark.parametrize("lang", sorted(TEMPLATES))
@pytest.mark.parametrize("n", NAMES)
def test_a_unicode_named_unit_is_found_whole(lang, n):
    assert n in [f["name"] for f in _functions(lang, TEMPLATES[lang].format(n=n))]


@pytest.mark.parametrize("n", ["probe_io_x", "probe_io_नाम", "probe_io_é"])
def test_a_unicode_named_defs_parameters_are_not_references(n):
    (f,) = _functions("python", f"def {n}(env):\n    return env.get('A')\n")
    assert f["references_to"] == []


def test_the_wrapper_census_sees_unicode_named_calls():
    assert [m.group(1) for m in _UNQUALIFIED_CALL.finditer("x = probeRiskनाम(1) + obj.skip(2)")] == ["probeRiskनाम"]


def test_a_joiner_after_a_virama_is_spelling_not_hidden_text():
    lens = SecurityLens()
    hidden = "reflection_metaprogramming"
    assert lens.scan_content("def क्‍ष(): pass\n")["counts"][hidden] == 0  # क्‍ष
    assert lens.scan_content("user‍name = 1\n")["counts"][hidden] == 1  # a bare ZWJ is still hidden
    assert lens.scan_content("x = 'a‮b'\n")["counts"][hidden] == 1  # and a bidi override
