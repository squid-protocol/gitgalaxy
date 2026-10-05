"""#4305: inline PERFORM forms name no paragraph, yet calls_out read the word after PERFORM as a
callee: `PERFORM WS-N TIMES` / `PERFORM 3 TIMES` gave `WS-N` / `3`, `PERFORM FOREVER` `FOREVER`,
`PERFORM TEST BEFORE|AFTER` (WITH omitted) `TEST`, and `EXIT PERFORM [CYCLE]` the next word
(`END-IF`, `CYCLE`). Out-of-line `PERFORM PARA-X 3 TIMES` still calls PARA-X (estate-crucible H-0006)."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

P = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
SRC = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. REPRO3.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-I                   PIC 9(4) COMP VALUE 0.
       01  WS-N                   PIC 9(4) COMP VALUE 3.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM WS-N TIMES
              ADD 1 TO WS-I
           END-PERFORM
           PERFORM 3 TIMES
              ADD 1 TO WS-I
           END-PERFORM
           PERFORM FOREVER
              ADD 1 TO WS-I
              IF WS-I > 50 EXIT PERFORM END-IF
              IF WS-I > 60 EXIT PERFORM CYCLE END-IF
           END-PERFORM
           PERFORM WITH TEST AFTER VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > 2
              DISPLAY WS-I
           END-PERFORM
           PERFORM TEST BEFORE UNTIL WS-I > 9
              ADD 1 TO WS-I
           END-PERFORM
           PERFORM WORK-PARA WITH TEST AFTER UNTIL WS-I > 20
           PERFORM WORK-PARA 3 TIMES
           PERFORM TIMES-PARA WS-N TIMES
           PERFORM WORK-PARA THRU WORK-EXIT
           CALL 'CBLTDLI' USING WS-I
           STOP RUN.
       WORK-PARA.
           ADD 1 TO WS-I.
       TIMES-PARA.
           EXIT.
       WORK-EXIT.
           EXIT.
"""


def test_inline_perform_forms_draw_no_callee():
    st = P.split_streams(SRC, "cobol")
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=SRC,
        positional_comment_stream=P.split_positional_comment_stream(SRC, "cobol"),
    )
    calls = {f["name"]: f["calls_out_to"] for f in out["functions"]}
    # WORK-PARA (WITH TEST AFTER, and `3 TIMES` out of line) and TIMES-PARA (`WS-N TIMES` out of
    # line) are real; CBLTDLI is a real CALL.
    assert calls["MAIN-PARA"] == ["WORK-PARA", "TIMES-PARA", "CBLTDLI"]
