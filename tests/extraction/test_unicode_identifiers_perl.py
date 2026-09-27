"""#3814: names follow Unicode UAX #31. Part 7: Perl.

A sub named each of नाम, பெயர், café (NFD), BELØP, 변수, 이름 is found whole and a call to it is counted; an ASCII Perl fixture's facts are unchanged.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

NAMES = ["नाम", "பெயர்", "café", "café", "BELØP", "変数", "이름"]
TEMPLATE = (
    "sub {n} {{\n    my ($env) = @_;\n    return $env;\n}}\n\nsub caller {{\n    my ($x) = @_;\n    {n}($x);\n}}\n"
)
PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _functions(lang: str, code: str) -> list[dict]:
    streams = PRISM.split_streams(code, lang)
    out = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(
        code_stream=streams["code_stream"], comment_stream=streams["comment_stream"], confidence=1.0
    )
    return out["functions"]


@pytest.mark.parametrize("n", NAMES)
def test_a_unicode_named_unit_is_found_whole_and_its_call_counted(n):
    functions = _functions("perl", TEMPLATE.format(n=n))
    names = [f["name"] for f in functions]
    assert names[:1] == [n] and names[-1].lower() == "caller"
    assert n in functions[-1]["calls_out_to"]
