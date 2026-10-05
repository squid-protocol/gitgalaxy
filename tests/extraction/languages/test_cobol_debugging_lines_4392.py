"""#4392: a fixed-format line with `D` in column 7 is a debugging line. Without `WITH DEBUGGING MODE`
on SOURCE-COMPUTER the compiler reads it as a comment, so it neither starts nor extends a unit (CBSA
BANKDATA.cbl CDW010 ran to its trailing `D    DISPLAY` lines, 1407-1436 instead of 1407-1433). With
the mode on it is code, as before."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _program(mode: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DBG.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        f"{mode}"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC X.\n"
        "       PROCEDURE DIVISION.\n"
        "       A-PARA.\n"
        "           MOVE 'A' TO WS-A.\n"
        "      D    DISPLAY 'A-PARA ' WS-A.\n"
        "      D    DISPLAY 'DONE'.\n"
        "       B-PARA.\n"
        "           GOBACK.\n"
    )


OFF = "      *SOURCE-COMPUTER. IBM-370 WITH DEBUGGING MODE.\n"  # commented out, as in BANKDATA
ON = "       SOURCE-COMPUTER. IBM-370 WITH DEBUGGING MODE.\n"


def _extents(src: str) -> dict:
    st = _PRISM.split_streams(src, "cobol")
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, "cobol"),
    )
    return {f["name"]: (f["start_line"], f["end_line"]) for f in out["functions"] if f["name"] != "__global_context__"}


def test_debugging_lines_are_comments_without_debugging_mode():
    assert _extents(_program(OFF))["A-PARA"] == (10, 11)
    assert "DISPLAY" not in _PRISM.split_streams(_program(OFF), "cobol")["code_stream"]


def test_debugging_lines_are_code_with_debugging_mode():
    assert _extents(_program(ON))["A-PARA"] == (10, 13)
    assert "DISPLAY" in _PRISM.split_streams(_program(ON), "cobol")["code_stream"]


def test_a_data_name_in_column_7_is_not_a_debugging_indicator():
    # cobol-check COPYR001.CBL:4 -- code from column 1, so columns 1-6 are no sequence area
    src = "01  A.\n  02  B    PIC S99.\n  02  D    PIC S9999 OCCURS 1 TO 52 TIMES\n      DEPENDING ON B OF A.\n"
    assert "  02  D    PIC" in _PRISM.split_streams(src, "cobol")["code_stream"]
