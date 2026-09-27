"""#3814: names follow Unicode UAX #31, not `[A-Za-z_]\\w*`. Part 2: JVM languages and C#."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

NAMES = ["नाम", "பெயர்", "café", "café", "BELØP", "変数", "이름"]
TEMPLATES = {
    "kotlin": "fun {n}(env: Int): Int {{\n    return env\n}}\n",
    "groovy": "def {n}(env) {{\n    return env\n}}\n",
    "scala": "def {n}(env: Int): Int = {{\n    env\n}}\n",
    "csharp": "public int {n}(int env) {{\n    return env;\n}}\n",
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
def test_a_unicode_named_unit_is_found_whole(lang, n):
    assert n in [f["name"] for f in _functions(lang, TEMPLATES[lang].format(n=n))]
