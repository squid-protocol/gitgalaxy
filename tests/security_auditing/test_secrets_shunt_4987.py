"""#4987: the aperture secrets shunt and the lens COBOL secrets rule, whole input class.

The shunt nominates a key/cert-named file by extension and only content may clear it. Content now means
the whole file (bounded), not its first 64 KB, and a binary DER certificate counts as public material.
"""

import re
import time

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.core.prism import Prism
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG, LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

CERT = "-----BEGIN CERTIFICATE-----\n"
PRIV = "-----BEGIN RSA PRIVATE KEY-----\n"
MB = 1024 * 1024

DER_CERT = b"\x30\x82\x03\x10\x30\x82\x02\xf8\xa0\x03\x02\x01\x02" + b"\x01" * 600  # v3
DER_CERT_V1 = b"\x30\x82\x03\x10\x30\x82\x02\xf8\x02\x01\x05" + b"\x01" * 600
# encrypted PKCS#8: SEQUENCE { SEQUENCE { AlgorithmIdentifier (PBES2 OID) ... } OCTET STRING }
DER_ENC_PKCS8 = (
    b"\x30\x82\x03\x10\x30\x4f\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x05\x0d"
    + b"\x01" * 80
    + b"\x04\x82\x02\x90"
    + b"\x01" * 600
)
DER_PKCS8 = b"\x30\x82\x04\xa4\x02\x01\x00\x02\x82\x01\x01" + b"\x01" * 600
DER_PKCS12 = (
    b"\x30\x82\x0a\x00\x02\x01\x03\x30\x82\x04\x00\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x07\x01"
    + b"\x2a\x86\x48\x86\xf7\x0d\x01\x0c" * 4
)
DER_P7B = b"\x30\x82\x03\x10\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x07\x02" + b"\x01" * 300


def _leak(tmp_path, name, data):
    f = tmp_path / name
    f.write_bytes(data if isinstance(data, bytes) else data.encode())
    eng = ApertureFilter(root_dir=tmp_path, language_definitions=LANGUAGE_DEFINITIONS, aperture_config=APERTURE_CONFIG)
    _, _, reason = eng.evaluate_path_integrity(f)
    return "CRITICAL LEAK" in reason


@pytest.mark.parametrize(
    ("name", "data", "leak"),
    [
        # armor text: size no longer decides
        ("big.crt", CERT + "A" * (200 * 1024), False),
        ("big.pem", CERT + "A" * (3 * MB), False),
        ("big.pem", CERT + "A" * (200 * 1024) + PRIV, True),  # private block past the old 64 KB read
        ("big.pem", CERT + "A" * (3 * MB) + PRIV, True),  # ... past a chunk boundary
        ("big.pem", CERT + "A" * (MB - 5) + "PRIVATE KEY\n", True),  # marker straddling the chunk boundary
        ("big.pem", CERT + "A" * (9 * MB), True),  # past the scan cap: stays a candidate
        ("small.pem", CERT, False),
        ("small.pem", PRIV, True),
        # binary DER
        ("a.cer", DER_CERT, False),
        ("a.crt", DER_CERT, False),
        ("a.cer", DER_CERT_V1, False),
        ("a.crt", DER_CERT_V1, False),
        ("a.cer", DER_ENC_PKCS8, True),
        ("a.crt", DER_ENC_PKCS8, True),
        ("a.der", DER_CERT, False),
        ("a.p7b", DER_P7B, False),
        ("a.cer", DER_PKCS8, True),
        ("a.cer", DER_PKCS12, True),
        ("a.p12", DER_PKCS12, True),
        ("a.pfx", DER_CERT, True),  # PKCS#12 extensions never clear on a cert shape
        ("a.key", DER_CERT, True),
        ("a.cer", b"", True),
        ("a.cer", b"\x30", True),
        ("a.cer", b"\x30\x82", True),
        ("a.cer", b"not der at all", True),
    ],
)
def test_shunt_clears_only_public_material(tmp_path, name, data, leak):
    assert _leak(tmp_path, name, data) is leak


PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
LENS = SecurityLens()


def _secrets(text):
    code = PRISM.split_streams(text, "cobol")["code_stream"]
    return LENS.scan_content(text, code_stream=code)


@pytest.mark.parametrize(
    "text",
    [
        "       05 WS-PASSWORD PIC X(8) VALUE 'hunter22'.\n",
        "       05 WS-PASSWORD\n           PIC X(8) VALUE 'hunter22'.\n",
        "       05 WS-PASSWORD PIC X(8)\n           VALUE 'hunter22'.\n",
        "       05 WS-PASSWORD\n           PIC X(8)\n           VALUE\n           'hunter22'.\n",
        "       05 WS-PASSWORD\r\n           PIC X(8)\r\n           VALUE 'hunter22'.\r\n",
        "       05 WS-PASSWORD\n000200     PIC X(8)\n000300     VALUE 'hunter22'.\n",
        "       05 WS-PASSWORD\n           VALUE 'hunter22'.\n",
        "       05 WS-PASSWORD IS\n           PIC X(8) VALUE 'hunter22'.\n",
    ],
)
def test_cobol_secret_item_across_continuation_lines(text):
    r = _secrets(text)
    assert r["counts"]["hardcoded_secrets"] == 1
    assert r["positions"]["hardcoded_secrets"] == [1]


@pytest.mark.parametrize(
    "text",
    [
        "       05 WS-NAME\n           PIC X(8) VALUE 'hunter22'.\n",  # not a credential name
        "       WS-PASSWORD\n           PIC X(8) VALUE 'hunter22'.\n",  # no level number at all
        "       05 WS-PASSWORD\n\n\n\n\n           VALUE 'hunter22'.\n",  # more than 3 line breaks
        "       05 WS-PASSWORD\n           PIC X(8).\n       05 WS-FLAG PIC X VALUE 'Y'.\n",  # VALUE of a later item
        "       88 PROMPT-FOR-SEARCH-KEYS VALUE\n           'Enter or update id'.\n",  # level-88 condition name
        "       05 CCDA-MSG-INVALID-KEY PIC X(50) VALUE\n           'Invalid key pressed.'.\n",  # a message, not a secret
    ],
)
def test_cobol_secret_negatives(text):
    assert _secrets(text)["counts"]["hardcoded_secrets"] == 0


@pytest.mark.parametrize(
    "text",
    [
        "05 WS-PASSWORD" + "\n" * 5000 + "VALUE x",
        "05 WS-PASSWORD" + " \n" * 5000,
        "05 WS-PASSWORD" + " " * 100000 + "PIC",
        "05 WS-PASSWORD\n" + "000100 " * 20000,
        "05 WS-PASSWORD IS\n" * 5000,
    ],
)
def test_cobol_secret_rule_is_redos_proof(text):
    rx = re.compile(
        LENS.THREAT_SIGNATURES["hardcoded_secrets"].pattern, LENS.THREAT_SIGNATURES["hardcoded_secrets"].flags
    )
    t = time.perf_counter()
    rx.search(text)
    assert time.perf_counter() - t < 1.0


def test_sarif_never_invents_a_position(tmp_path):
    """#4987 recorders audit: every lens finding carries its recorded (line, col); a finding with no
    recorded column carries none; file-level findings carry only the file's start_line."""
    import json

    from gitgalaxy.recorders.sarif_recorder import SarifRecorder

    node = {
        "path": "src/a.cbl",
        "start_line": 7,
        "telemetry": {
            "threat_snippets": {
                "hardcoded_secrets": ["PASSWORD A", "PASSWORD B"],
                "unpinned_install": ["pip install x"],
            },
            "threat_sites": {"hardcoded_secrets": [[12, 8], [40, 8]]},
            "threat_locations": {"hardcoded_secrets": [99, 98], "sec_unpinned_install": [5]},
            "ai_guardrails": {"warnings": ["w"]},
        },
    }
    out = tmp_path / "o.sarif"
    SarifRecorder().generate_report([node], {}, {}, str(out))
    regions = [
        (r["ruleId"], r["locations"][0]["physicalLocation"]["region"])
        for r in json.loads(out.read_text())["runs"][0]["results"]
    ]
    assert regions[0] == ("GG-SAST-HARDCODED_SECRETS", {"startLine": 12, "startColumn": 8})
    assert regions[1] == ("GG-SAST-HARDCODED_SECRETS", {"startLine": 40, "startColumn": 8})
    assert regions[2] == ("GG-SAST-UNPINNED_INSTALL", {"startLine": 5})
    assert regions[3] == ("GG-AGENT-GUARDRAIL", {"startLine": 7})


@pytest.mark.parametrize("ext", [".der", ".cer", ".crt", ".p7b"])
@pytest.mark.parametrize(
    ("data", "public"),
    [(DER_CERT, True), (DER_CERT_V1, True), (DER_ENC_PKCS8, False), (DER_PKCS8, False), (DER_PKCS12, False)],
)
def test_der_classifier_per_extension(tmp_path, ext, data, public):
    """`.der` is not itself a shunt extension, so the classifier is pinned directly for every cert extension."""
    from gitgalaxy.core.aperture import _is_public_key_material

    f = tmp_path / f"a{ext}"
    f.write_bytes(data)
    assert _is_public_key_material(f) is public
