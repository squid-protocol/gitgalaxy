"""CBACT01C's new ground (carddemo-readacct): variable-length records (oracle_assumptions.md F3), the scoped zoned
sign tolerance (C10) and the COBDATFT library routine (A1) -- the harness's framing and comparison, the det
translator's reading of an FD's RECORD VARYING clause, and the runtime routine it calls."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests" / "tools"), str(ROOT)]
import equivalence as eq  # noqa: E402
import equivalence_common as ec  # noqa: E402


def frame(*records: bytes) -> bytes:
    return b"".join(len(r).to_bytes(2, "big") + b"\0\0" + r for r in records)


def test_variable_records_split_as_gnucobol_frames_them():
    assert ec.split_varseq(frame(b"A" * 12, b"B" * 39)) == [b"A" * 12, b"B" * 39]
    assert ec.split_varseq(b"") == []
    with pytest.raises(ValueError, match="header"):
        ec.split_varseq(b"\x00\x0c\x01\x00" + b"A" * 12)  # the two bytes after the length are not zero
    with pytest.raises(ValueError, match="claims"):
        ec.split_varseq(b"\x00\x50\x00\x00" + b"A" * 12)  # a length past the end of the data


def test_variable_records_compare_by_length_and_content():
    same = ec.diff_varseq(frame(b"A" * 12), frame(b"A" * 12), {})
    assert same["records"] == 1 and not same["diffs"]
    longer = ec.diff_varseq(frame(b"A" * 12), frame(b"A" * 13), {})
    assert longer["diffs"][0]["fields"][0]["field"] == "(record length)"
    padded = ec.diff_varseq(frame(b"A" * 12), b"A" * 80, {})  # an unframed 80-byte record: a framing error
    assert "framing" in padded["diffs"][0]
    missing = ec.diff_varseq(frame(b"A" * 12, b"B" * 39), frame(b"A" * 12), {})
    assert missing["diffs"] == [{"record": 2, "missing": "java"}]


def test_c10_takes_only_an_unsigned_digit_against_its_positive_overpunch():
    a, b, n = eq.accept_unsigned_positive(b"000", b"00{")  # INITIALIZE's F zone against z/OS's preferred C
    assert (a, b, n) == (b"00{", b"00{", 1)
    assert eq.accept_unsigned_positive(b"5", b"E")[2] == 1
    for left, right in ((b"5", b"N"), (b"5", b"F"), (b"0", b"}"), (b"5", b"6")):  # negative, other digit, other value
        a, b, n = eq.accept_unsigned_positive(left, right)
        assert n == 0 and a != b
    assert eq.accept_unsigned_positive(b"00", b"0")[2] == 0  # lengths differ: left alone


def test_the_translator_reads_record_varying_and_recording_mode_v(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det import source as SRC

    src = "\n".join([
        "       IDENTIFICATION DIVISION.", "       PROGRAM-ID. VB.", "       ENVIRONMENT DIVISION.",
        "       INPUT-OUTPUT SECTION.", "       FILE-CONTROL.", "           SELECT VBFILE ASSIGN TO VBRCFILE.",
        "           SELECT FBFILE ASSIGN TO OUTFILE.", "       DATA DIVISION.", "       FILE SECTION.",
        "       FD  VBFILE", "           RECORDING MODE IS V",
        "           RECORD IS VARYING IN SIZE FROM 10 TO 80",  # within column 72: fixed format ignores 73-80
        "               DEPENDING ON WS-RECD-LEN.",
        "       01  VB-REC PIC X(80).", "       FD  FBFILE.", "       01  FB-REC PIC X(107).",
        "       WORKING-STORAGE SECTION.", "       01  WS-RECD-LEN PIC 9(4) COMP.", "       PROCEDURE DIVISION.",
        "           GOBACK.",
    ]) + "\n"  # fmt: skip
    (tmp_path / "VB.cbl").write_text(src, encoding="ascii")
    fds = P.fd_entries(SRC.program_lines(tmp_path / "VB.cbl", []))
    assert fds["VBFILE"] == {"varying": {"min": 10, "max": 80, "depending": "WS-RECD-LEN"}, "mode_v": True}
    assert fds["FBFILE"] == {"varying": None, "mode_v": False}


def test_cobdatft_is_a_runtime_library_call():
    from gitgalaxy.tools.cobol_to_java.det import gen as G

    assert G.LIBRARY["COBDATFT"] == ("__PACKAGE__.cobolrt.le.Cobdatft.call", 1)
    rt = ROOT / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt" / "le" / "Cobdatft.java"
    assert "oracle_assumptions.md A1" in rt.read_text(encoding="utf-8")
