"""#4548 items 3+4: threat inflation on C/C++ (Doom study).

3. `threat_obfuscated` counted every `\\xNN` escape, so an embedded glyph table scored 32,987 hits.
   The class: a run of escapes, however it is split (one literal, adjacent string pieces, array elements,
   `\\u` escapes), is one finding; separate payloads are still separate findings.
4. `fam_threat` summed the language-level `reflection_metaprogramming` (C/C++ function-like macros and
   `goto`), so macro-only headers (glext.h, _sal.h) read as threats with every named threat_* at 0.
"""

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards import analysis_lens
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _hits(lens, text, lang="c"):
    code = PRISM.split_streams(text, lang)["code_stream"]
    return lens.scan_content(text, code_stream=code)["counts"]["reflection_metaprogramming"]


def _glyph(n):
    return "".join(f"\\x{(0x50 + i) % 256:02X}" for i in range(n))


def test_one_long_escape_literal_is_one_hit(lens):
    assert _hits(lens, f'static const char *g = "{_glyph(50)}";\n') == 1


def test_escapes_split_across_string_pieces_are_one_hit(lens):
    pieces = "\n".join(f'    "{_glyph(23)}"' for _ in range(40))
    assert _hits(lens, f"static const char g[] =\n{pieces};\n") == 1


def test_a_table_of_escape_strings_is_one_hit(lens):
    rows = "\n".join(f'    // {i}\n    "{_glyph(23)}",' for i in range(60))
    assert _hits(lens, f"static const char *glyphs[] = {{\n{rows}\n}};\n") == 1


def test_unicode_escapes_are_one_hit(lens):
    assert _hits(lens, 'var s = "\\u0065\\u0076\\u0061\\u006c\\u0028";\n', lang="javascript") == 1


@pytest.mark.parametrize(
    "literal",
    ['"%i\\xB0"', '"\\x1b[0m"', '"caf\\u00e9"', '"\\x93" BOLD("m") "\\x94" "\\xB0" "\\xB1"', '"\\x1b[1m\\x1b[0m"'],
)
def test_character_escapes_are_not_obfuscation(lens, literal):
    assert _hits(lens, f"#define MSG {literal}\nint x;\n") == 0


def test_separate_payloads_still_count_separately(lens):
    src = f'char *a = "{_glyph(8)}";\nint pad = 1;\nint pad2 = 2;\nchar *b = "{_glyph(8)}";\n'
    assert _hits(lens, src) == 2


def test_encoded_eval_is_still_flagged(lens):
    assert _hits(lens, 'var f = "\\x65\\x76\\x61\\x6c";\n', lang="javascript") == 1


def test_other_obfuscation_keywords_are_unchanged(lens):
    assert _hits(lens, "var a = atob(blob);\n", lang="javascript") == 1


def test_macro_only_header_has_no_threat_family_signal():
    assert "reflection_metaprogramming" not in analysis_lens.SURFACE_FAMILIES["threat"]
    assert "sec_reflection_metaprogramming" in analysis_lens.SURFACE_FAMILIES["threat"]
    assert "reflection_metaprogramming" in analysis_lens.SURFACE_FAMILY_EXEMPT
    assert "sec_reflection_metaprogramming" not in analysis_lens.SURFACE_FAMILY_EXEMPT


def test_function_like_macros_do_not_trip_the_security_lens(lens):
    header = "#define glFoo(a, b) glFooImpl(a, b)\n" * 200
    code = PRISM.split_streams(header, "c")["code_stream"]
    counts = lens.scan_content(header, code_stream=code)["counts"]
    assert counts["reflection_metaprogramming"] == 0
