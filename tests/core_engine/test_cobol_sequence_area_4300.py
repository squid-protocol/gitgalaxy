"""#4300: the numbered sequence area (cols 1-6) of a fixed-format COBOL line is not program
text. A verb whose operand starts on the next line read that line's sequence number as the
operand: `PERFORM` / `000900     INIT-PARA` recorded the callee `000900`, a split CALL left no
call_site_data row, and a split COPY recorded the import `000600`. Prism now blanks the area
of fixed lines (and a debug line's col-7 `D` behind an all-digit area) for every COBOL rule
and reader; free-format lines are left alone."""

from __future__ import annotations

from gitgalaxy.core.cobol_source_format import FIXED, FREE, blank_sequence_area
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

# The issue's REPRO4.cbl / REPRO5.cbl, verbatim.
_REPRO4 = """000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. REPRO4.
000300 DATA DIVISION.
000400 WORKING-STORAGE SECTION.
000500 01  WS-PGM                 PIC X(8) VALUE 'SUBPGM2'.
000600 PROCEDURE DIVISION.
000700 MAIN-PARA.
000800     PERFORM
000900         INIT-PARA
001000     CALL
001100         'SUBPGM1'
001200     CALL
001300         WS-PGM
001400     STOP RUN.
001500 INIT-PARA.
001600     DISPLAY 'I'.
"""

_REPRO5 = """000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. REPRO5.
000300 DATA DIVISION.
000400 WORKING-STORAGE SECTION.
000500     COPY
000600         CPYA.
000700 PROCEDURE DIVISION.
000800 MAIN-PARA.
000900     IF CPYA-FLAG = 'Y' GO TO
001000         END-PARA.
001100     STOP RUN.
001200 END-PARA.
001300     STOP RUN.
"""


def _code(src: str) -> str:
    return _PRISM.split_streams(src, "cobol")["code_stream"]


def _units(src: str) -> dict:
    st = _PRISM.split_streams(src, "cobol")
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"], comment_stream=st["comment_stream"], raw_content=src
    )
    return {f["name"]: f for f in out["functions"]}


def test_split_perform_and_call_read_the_real_operand():
    assert _units(_REPRO4)["MAIN-PARA"]["calls_out_to"] == ["INIT-PARA", "SUBPGM1", "WS-PGM"]


def test_split_call_produces_call_site_rows():
    calls = extract_boundary("cobol", _code(_REPRO4))["calls"]
    assert [(c["verb"], c["operand"], c["form"]) for c in calls] == [
        ("CALL", "SUBPGM1", "literal"),
        ("CALL", "WS-PGM", "identifier"),
    ]


def test_split_go_to_and_copy_read_the_real_operand():
    assert _units(_REPRO5)["MAIN-PARA"]["transfers_to"] == ["END-PARA"]
    assert LANGUAGE_DEFINITIONS["cobol"]["rules"]["_dependency_capture"].findall(_code(_REPRO5)) == ["CPYA"]


def test_debug_line_operand_and_paragraph():
    # NIST DB1024.2.cbl:638-642: the operand sits on a `D` debug line, and a debug line
    # opens a paragraph whose name follows the indicator directly.
    src = """000100 IDENTIFICATION DIVISION.
000200 PROGRAM-ID. DB1024.
000300 PROCEDURE DIVISION.
063700 DEBUG-LINE-TEST-03.
063900     PERFORM
064000D        PASS.  GO TO DEBUG-LINE-WRITE-03.
064100DDEBUG-LINE-TEST-03-A.    PERFORM
064200                             FAIL.
064300                             GO TO DEBUG-LINE-WRITE-03.
064400 DEBUG-LINE-WRITE-03.
064500     DISPLAY 'W'.
064600 PASS.
064700     DISPLAY 'P'.
064800 FAIL.
064900     DISPLAY 'F'.
"""
    units = _units(src)
    assert units["DEBUG-LINE-TEST-03"]["calls_out_to"] == ["PASS"]
    assert units["DEBUG-LINE-TEST-03-A"]["calls_out_to"] == ["FAIL"]
    assert units["DEBUG-LINE-TEST-03-A"]["start_line"] == 7


def test_blanking_keeps_offsets_and_only_touches_numbered_fixed_lines():
    text = "\n".join(
        [
            "000100     PERFORM",  # numbered: blanked
            "AB0110-        'CONTINUED'",  # alphanumeric area with a digit, continuation kept
            "064000D        PASS.",  # debug line: area and indicator blanked
            "   02  DELTA    PIC S9999.",  # not a sequence area (spaces, a level number)
            "       MOVE A TO B.",  # unnumbered
            "000200",  # a numbered blank line
        ]
    )
    out = blank_sequence_area(text, [FIXED] * 6)
    assert out.split("\n") == [
        "           PERFORM",
        "      -        'CONTINUED'",
        "               PASS.",
        "   02  DELTA    PIC S9999.",
        "       MOVE A TO B.",
        "      ",
    ]
    assert len(out) == len(text)


def test_free_format_lines_are_left_alone():
    text = "PARA01 SECTION.\n000100 MOVE A TO B."
    assert blank_sequence_area(text, [FREE, FREE]) == text


def test_a_line_of_only_sequence_fields_is_blank_not_code_or_doc():
    src = "000100 IDENTIFICATION DIVISION.\n000200\n000300*A COMMENT.\n" + " " * 72 + "340000\n"
    streams = _PRISM.split_streams(src, "cobol")
    assert (streams["coding_loc"], streams["doc_loc"]) == (1, 1)
