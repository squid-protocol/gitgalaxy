"""#8412: raw EBCDIC with no declared code page is named, not silently decoded as cp1252 garbage.

Fixtures are authored: invented COBOL / JCL text encoded with the EBCDIC pages Python (and
`ebcdic_codecs`) carries. The sniff is a hint; the engine still never switches code page by itself.
"""

import pytest

from gitgalaxy.core.source_text import decode_source, looks_like_ebcdic, read_source
from gitgalaxy.recorders.llm_recorder import LLMRecorder

COBOL = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. PLUMB01.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-COUNT        PIC 9(4) VALUE ZERO.\n"
    "       PROCEDURE DIVISION.\n"
    "           ADD 1 TO WS-COUNT.\n"
    "           GOBACK.\n"
)
JCL = "//PLUMBJ1  JOB (ACCT),'INVENTED',CLASS=A\n//STEP1    EXEC PGM=PLUMB01\n//SYSOUT   DD SYSOUT=*\n"


def _fb80(text: str, cp: str) -> bytes:
    return b"".join(line.ljust(80).encode(cp) for line in text.splitlines())


def _nel(text: str, cp: str) -> bytes:
    return text.replace("\n", "\x15").encode(cp)


@pytest.mark.parametrize("cp", ["cp037", "cp500", "cp1047", "cp273"])
@pytest.mark.parametrize("layout", [_fb80, _nel], ids=["fb80", "nel"])
@pytest.mark.parametrize("text", [COBOL, JCL], ids=["cobol", "jcl"])
def test_undeclared_ebcdic_is_named(text, layout, cp):
    data = layout(text, cp)
    src = decode_source(data)
    assert src.how in ("cp1252-fallback", "latin-1-fallback")  # still a guess: the finding is the point
    assert src.ebcdic_undeclared
    assert looks_like_ebcdic(data)


@pytest.mark.parametrize("cp", ["cp037", "cp1047"])
def test_declared_ebcdic_is_not_flagged(cp):
    src = decode_source(_nel(COBOL, cp), declared=cp)
    assert src.how == "declared" and not src.ebcdic_undeclared
    # a declaration that does not fit still falls to the guess, but the author did declare: no finding
    assert not decode_source(_nel(COBOL, cp), declared="cp1252").ebcdic_undeclared


@pytest.mark.parametrize(
    "data",
    [
        COBOL.encode("ascii"),
        COBOL.encode("utf-8"),
        COBOL.replace("PLUMB01", "PLUMBÉ1").encode("cp1252"),
        ("# Größe für Übermaß: Äpfel, Öle, Müller, Straße, Grüße, schön, überprüfen\n" * 4).encode("latin-1"),
        ("# 日本語のコメントです。これは説明です。\n" * 6).encode("shift_jis"),
        b"@@@@@@@@@@@@@@@@@@@@@@@@",
        bytes(range(256)) * 4,
        b"\xc1\xc2\xc3",  # too short to say
        b"",
    ],
    ids=["ascii", "utf8", "cp1252", "latin1-accents", "shift-jis", "at-signs", "all-bytes", "short", "empty"],
)
def test_ordinary_text_and_binary_are_not_flagged(data):
    assert not decode_source(data).ebcdic_undeclared


def test_the_flag_survives_read_source_newline_folding(tmp_path):
    f = tmp_path / "plumb01.cbl"
    f.write_bytes(_fb80(COBOL, "cp037") + b"\r\n")  # a stray CRLF forces the universal-newline path
    assert read_source(f).ebcdic_undeclared


def test_the_report_names_the_declaration_to_make():
    parsed = [
        {"path": f"src/m{i}.cbl", "source_encoding": "cp1252", "source_decode": "cp1252-fallback", "ebcdic_undeclared": True}
        for i in range(7)
    ] + [{"path": "src/plain.cbl", "source_encoding": "cp1252", "source_decode": "cp1252-fallback"}]  # fmt: skip
    text = "\n".join(LLMRecorder()._source_encoding_lines(parsed))
    assert "UNDECLARED EBCDIC: 7 file(s)" in text
    assert "`--source-encoding cp037`" in text
    assert "`src/m0.cbl`" in text and "and 2 more" in text and "plain.cbl" not in text


def test_no_finding_line_without_ebcdic():
    parsed = [{"path": "a.c", "source_encoding": "cp1252", "source_decode": "cp1252-fallback"}]
    assert "EBCDIC" not in "\n".join(LLMRecorder()._source_encoding_lines(parsed))
