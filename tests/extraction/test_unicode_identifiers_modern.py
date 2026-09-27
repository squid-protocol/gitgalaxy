"""#3814: names follow Unicode UAX #31, not `[A-Za-z_]\\w*`. Part 5: Rust, Swift, Dart, PHP and Ruby.

A unit named in Devanagari or Tamil (combining vowel signs and viramas, Mn/Mc), with a decomposed
accent, in Hangul, Han or with a non-ASCII capital is found whole -- never cut at its first combining
mark, nor missed for starting outside ASCII -- and a call to it is counted as a call to that name.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.standards.language_standards._shared_patterns import CALLS_OUT_RUBY

NAMES = ["नाम", "பெயர்", "café", "café", "BELØP", "変数", "이름"]
TEMPLATES = {
    "rust": "fn {n}(env: i32) -> i32 {{\n    env\n}}\n\nfn caller(x: i32) -> i32 {{\n    {n}(x)\n}}\n",
    "swift": "func {n}(env: Int) -> Int {{\n    return env\n}}\n\nfunc caller(x: Int) -> Int {{\n    return {n}(env: x)\n}}\n",
    "dart": "int {n}(int env) {{\n  return env;\n}}\n\nint caller(int x) {{\n  return {n}(x);\n}}\n",
    "php": "<?php\nfunction {n}($env) {{\n    return $env;\n}}\n\nfunction caller($x) {{\n    return {n}($x);\n}}\n",
    "ruby": "def {n}(env)\n  env\nend\n\ndef caller(x)\n  {n}(x)\nend\n",
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


@pytest.mark.parametrize("n", ["नाम", "பெயர்"])
def test_a_ruby_block_opened_by_an_assignment_to_a_unicode_name_still_closes(n):
    code = f"def outer(x)\n  {n} = if x\n    1\n  else\n    2\n  end\n  {n}\nend\n\ndef after(y)\n  y\nend\n"
    assert [f["name"] for f in _functions("ruby", code)] == ["outer", "after"]


def test_ruby_calls_on_a_unicode_receiver_and_in_command_position_are_calls():
    assert [m.group(1) for m in CALLS_OUT_RUBY.finditer("x = பெயர்.save\n")] == ["save"]
    assert [m.group(1) for m in CALLS_OUT_RUBY.finditer("probe_नाम x\n")] == ["probe_नाम"]


def test_a_php_name_takes_any_non_ascii_character_as_php_does():
    # php.net: a name is `[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*` over BYTES -- every UTF-8 code point
    assert "変数ー" in [f["name"] for f in _functions("php", "<?php\nfunction 変数ー($a) {\n    return $a;\n}\n")]
