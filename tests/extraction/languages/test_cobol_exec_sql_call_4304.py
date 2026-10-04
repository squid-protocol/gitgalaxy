"""#4304: `EXEC SQL CALL proc` is a DB2 stored-procedure call, not a COBOL CALL. Both COBOL CALL
readers -- mainframe_boundary's call sites (call_site_data) and the calls_out rule
(calls_out_to) -- scanned EXEC blocks too, so `EXEC SQL CALL MYSCHEMA.GETCUST (:WS-A)` became a
dynamic CALL of `MYSCHEMA` and `EXEC SQL CALL UPDPROC END-EXEC` one of `UPDPROC`. A CALL inside
any EXEC ... END-EXEC block now belongs to that block; sql_statement_data keeps recording it."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

REPRO7 = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REPRO7.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-A                   PIC X(4).
       01  WS-PGM                 PIC X(8) VALUE 'SUBPGM'.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC SQL
               CALL MYSCHEMA.GETCUST (:WS-A)
           END-EXEC
           EXEC SQL CALL UPDPROC END-EXEC
           CALL 'REALSUB' USING WS-A
           EXEC CICS LINK PROGRAM('CICSPGM') END-EXEC
           CALL WS-PGM
           PERFORM WORK-PARA
           STOP RUN.
       WORK-PARA.
           EXEC SQL
               CALL NOEND
           CALL 'AFTERSUB'
           EXEC SQL COMMIT END-EXEC
           GOBACK.
"""


def _streams(src: str) -> dict:
    return _PRISM.split_streams(src, "cobol")


def test_boundary_records_no_cobol_call_inside_exec_sql():
    b = extract_boundary("cobol", _streams(REPRO7)["code_stream"])
    assert sorted((c["verb"], c["operand"]) for c in b["calls"]) == [
        ("CALL", "AFTERSUB"),
        # malformed: an EXEC SQL with no END-EXEC before the next EXEC is not a block, so nothing of
        # it is masked (the pre-#4304 reading) -- a lost END-EXEC never hides the CALLs after it
        ("CALL", "NOEND"),
        ("CALL", "REALSUB"),
        ("CALL", "WS-PGM"),
        ("LINK", "CICSPGM"),
    ]
    assert [s["verb"] for s in b["sql_statements"]][:2] == ["CALL", "CALL"]


def test_calls_out_skips_exec_blocks():
    st = _streams(REPRO7)
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=REPRO7,
        positional_comment_stream=_PRISM.split_positional_comment_stream(REPRO7, "cobol"),
    )
    calls = {f["name"]: f["calls_out_to"] for f in out["functions"] if f["name"] != "__global_context__"}
    assert calls["MAIN-PARA"] == ["REALSUB", "WS-PGM", "WORK-PARA"]
    assert "MYSCHEMA" not in calls["MAIN-PARA"] and "UPDPROC" not in calls["MAIN-PARA"]
    assert "AFTERSUB" in calls["WORK-PARA"]
