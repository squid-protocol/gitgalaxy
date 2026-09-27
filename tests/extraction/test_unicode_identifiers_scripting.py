"""#3814: names follow Unicode UAX #31, not `[A-Za-z_]\\w*`. Part 6: Ada, Tcl, Haskell, Scheme and PowerShell.

A unit named in Devanagari or Tamil (combining vowel signs and viramas, Mn/Mc), with a decomposed
accent, in Hangul, Han or with a non-ASCII capital is found whole -- never cut at its first combining
mark, nor missed for starting outside ASCII -- and a call to it is counted as a call to that name.
"""

import re

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import (
    CALLS_OUT_COMMAND_POSITION,
    CALLS_OUT_LISP_FAMILY,
)
from gitgalaxy.standards.language_standards.identifiers import SMALL

NAMES = ["नाम", "பெயர்", "café", "café", "BELØP", "変数", "이름"]
TEMPLATES = {
    "ada": "procedure {n} (Env : Integer) is\nbegin\n   null;\nend {n};\n\n"
    "procedure Caller (X : Integer) is\nbegin\n   {n} (X);\nend Caller;\n",
    "tcl": "proc {n} {{env}} {{\n    return $env\n}}\n\nproc caller {{x}} {{\n    {n} $x\n}}\n",
    "haskell": "{n} :: Int -> Int\n{n} env = env\n\ncaller :: Int -> Int\ncaller x = {n} (x)\n",
    "scheme": "(define ({n} env)\n  env)\n\n(define (caller x)\n  ({n} x))\n",
    "powershell": "function {n}($env) {{\n    return $env\n}}\n\nfunction caller($x) {{\n    {n} $x\n}}\n",
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
    if lang == "haskell" and n[0].isupper():
        n = "x" + n  # a Haskell function starts small: an upper-case initial is a constructor
    functions = _functions(lang, TEMPLATES[lang].format(n=n))
    names = [f["name"] for f in functions]
    assert names[:1] == [n] and names[-1].lower() == "caller"
    assert n in functions[-1]["calls_out_to"]  # haskell also counts `(x)`'s `x`, as it does on ASCII


def test_the_shared_call_patterns_read_unicode_names_whole():
    assert [m.group(1) for m in CALLS_OUT_LISP_FAMILY.finditer("(probe-नाम x)")] == ["probe-नाम"]
    assert [m.group(1) for m in CALLS_OUT_COMMAND_POSITION.finditer("Get-பெயர் -Name x\n")] == ["Get-பெயர்"]
    # the old `\b` word end, kept: a trailing `-` or `:` is not part of the command
    assert [m.group(1) for m in CALLS_OUT_COMMAND_POSITION.finditer("foo- x\n")] == ["foo"]


def test_small_is_what_a_haskell_variable_may_start_with():
    small = re.compile(f"[{SMALL}]")
    assert all(small.fullmatch(c) for c in "az_変नä")  # lower-case, `_`, and uncased letters
    assert not any(small.fullmatch(c) for c in "AZÄ1ा")  # never a capital, a digit or a mark
