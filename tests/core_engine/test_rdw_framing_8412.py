"""#8412: RECFM=V exports (RDW / BDW+RDW length prefixes) are detected by structure, in EBCDIC and ASCII.

Authored fixtures: invented COBOL lines framed the way a variable-length download frames them. The sniff
never decodes; plain text, fixed-block EBCDIC and ordinary binary must not trip it.
"""

import pytest

from gitgalaxy.core.source_text import rdw_framing

LINES = [
    "       IDENTIFICATION DIVISION.",
    "       PROGRAM-ID. PLUMB02.",
    "       PROCEDURE DIVISION.",
    "           ADD 1 TO WS-COUNT.",
    "           GOBACK.",
]


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


@pytest.mark.parametrize("cp", ["cp037", "cp1047", "ascii", "cp1252"])
def test_rdw_records_are_named(cp):
    assert rdw_framing(_rdw(LINES, cp)) == "rdw"


@pytest.mark.parametrize("cp", ["cp037", "cp500", "ascii"])
def test_blocked_bdw_plus_rdw_is_named(cp):
    assert rdw_framing(_bdw([LINES[:2], LINES[2:]], cp)) == "bdw+rdw"
    assert rdw_framing(_bdw([LINES], cp)) == "bdw+rdw"  # a single block is a file too


def test_a_long_export_cut_at_the_sample_is_still_named():
    data = _rdw(LINES * 4000, "cp037")
    assert len(data) > 65536
    assert rdw_framing(data) == "rdw"
    assert rdw_framing(_bdw([LINES * 20] * 400, "cp037")) == "bdw+rdw"


def test_empty_records_chain():
    rec = b"\x00\x04\x00\x00"
    assert rdw_framing(rec * 4 + _rdw(LINES[:1], "ascii")) == "rdw"


@pytest.mark.parametrize(
    "data",
    [
        ("\n".join(LINES) + "\n").encode("ascii"),
        "".join(line.ljust(80) for line in LINES).encode("cp037"),  # fixed-block EBCDIC
        ("\n".join(LINES) + "\n").replace("\n", "\x15").encode("cp037"),
        ("\n".join(LINES * 50)).encode("utf-16"),
        bytes(range(256)) * 8,
        b"\x00" * 64,
        b"",
        b"\x00\x08\x00\x00",
        _rdw(LINES, "ascii")[:-3] + b"X" * 40,  # a chain that breaks mid-file
        _rdw(LINES[:2], "ascii"),  # two records are not enough evidence
    ],
    ids=["ascii", "fb80", "nel", "utf16", "all-bytes", "zeros", "empty", "short", "broken", "two-records"],
)
def test_other_files_are_not_named(data):
    assert rdw_framing(data) is None
