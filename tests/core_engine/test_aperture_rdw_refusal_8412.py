"""#8412: the aperture names a RECFM=V export when it drops one, instead of a generic binary reason.

Authored fixtures (invented COBOL lines) framed with RDW / BDW+RDW descriptor words. The file is still refused
(no decode); only the reason changes. Ordinary binaries keep the generic reason, and plain text stays in scope.
"""

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.core.source_text import decode_bytes

LINES = [
    "       IDENTIFICATION DIVISION.",
    "       PROGRAM-ID. PLUMB02.",
    "       PROCEDURE DIVISION.",
    "           ADD 1 TO WS-COUNT.",
    "           GOBACK.",
]
CONFIG = {"MAX_FILE_SIZE_MB": 10, "MAX_LINE_LENGTH": 500, "IGNORED_DIRECTORIES": set()}
REGISTRY = {"cobol": {"extensions": [".cbl"], "exact_matches": []}}


def _rdw(lines, cp):
    out = b""
    for line in lines:
        rec = line.encode(cp)
        out += (len(rec) + 4).to_bytes(2, "big") + b"\x00\x00" + rec
    return out


def _bdw(blocks, cp):
    out = b""
    for block in blocks:
        body = _rdw(block, cp)
        out += (len(body) + 4).to_bytes(2, "big") + b"\x00\x00" + body
    return out


def _verdict(tmp_path, data):
    src = tmp_path / "PLUMB02.cbl"
    src.write_bytes(data)
    engine = ApertureFilter(root_dir=tmp_path, language_definitions=REGISTRY, aperture_config=CONFIG)
    return engine.is_in_scope(src, content=decode_bytes(data))


@pytest.mark.parametrize("cp", ["cp037", "cp1047", "ascii", "cp1252"])
def test_an_rdw_export_is_refused_by_name(tmp_path, cp):
    result = _verdict(tmp_path, _rdw(LINES, cp))
    assert not result["is_in_scope"]
    assert result["classification"] == "binary_payload"
    assert "RECFM=V export: RDW" in result["reason"]


@pytest.mark.parametrize("cp", ["cp037", "ascii"])
def test_a_blocked_export_is_refused_by_name(tmp_path, cp):
    result = _verdict(tmp_path, _bdw([LINES[:2], LINES[2:]], cp))
    assert not result["is_in_scope"]
    assert "RECFM=V export: BDW+RDW" in result["reason"]


def test_a_long_export_cut_at_the_sample_is_refused_by_name(tmp_path):
    result = _verdict(tmp_path, _rdw(LINES * 4000, "cp037"))
    assert not result["is_in_scope"]
    assert "RECFM=V export" in result["reason"]


def test_an_ordinary_binary_keeps_the_generic_reason(tmp_path):
    result = _verdict(tmp_path, bytes(range(256)) * 8)
    assert not result["is_in_scope"]
    assert result["reason"] == "Blocked (Binary Format Detected)"


def test_a_broken_chain_keeps_the_generic_reason(tmp_path):
    result = _verdict(tmp_path, _rdw(LINES, "ascii")[:-3] + b"\x00" * 60)
    assert result["reason"] == "Blocked (Binary Format Detected)"


def test_plain_text_stays_in_scope(tmp_path):
    result = _verdict(tmp_path, ("\n".join(LINES) + "\n").encode("ascii"))
    assert result["is_in_scope"]
