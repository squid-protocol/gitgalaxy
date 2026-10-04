"""#4301 / #4283: a COBOL paragraph or PL/I procedure is not cut at its last
line-leading GOBACK / EXIT / RETURN. Those are statements there -- conditional,
mid-body loop exits, or even the first word of the unit's own name -- so the cut
dropped every PERFORM / CALL edge after them. A unit runs to the next unit header,
or to its structural end (COBOL `END PROGRAM` / next program header, PL/I
`END name;`). Assembly keeps its terminator cut."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _units(lang: str, src: str) -> dict:
    st = _PRISM.split_streams(src, lang)
    out = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, lang),
    )
    return {f["name"]: f for f in out["functions"]}


# The issue's REPRO1.cbl, verbatim.
_REPRO1 = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. REPRO1.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-FLAG                PIC X VALUE 'N'.
       01  WS-I                   PIC 9(4) COMP VALUE 0.
       PROCEDURE DIVISION.
           PERFORM ENTRY-TARGET
           PERFORM MAIN-PARA
           GOBACK.
       MAIN-PARA.
           IF WS-FLAG = 'Y'
              GOBACK
           END-IF
           PERFORM AFTER-GOBACK-TARGET
           CALL 'SUBPGM1'
           PERFORM RETURN-TO-MENU
           PERFORM LOOP-PARA.
       RETURN-TO-MENU.
           MOVE 'Y' TO WS-FLAG
           PERFORM IN-RETURN-PARA-TARGET.
       LOOP-PARA.
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > 5
              IF WS-I = 3
                 EXIT PERFORM
              END-IF
              DISPLAY WS-I
           END-PERFORM
           PERFORM AFTER-EXIT-PERFORM-TARGET
           PERFORM TEST AFTER VARYING WS-I FROM 1 BY 1
                   UNTIL WS-I > 2
              DISPLAY WS-I
           END-PERFORM.
       ENTRY-TARGET.
           DISPLAY 'E'.
       AFTER-GOBACK-TARGET.
           DISPLAY 'A'.
       IN-RETURN-PARA-TARGET.
           DISPLAY 'R'.
       AFTER-EXIT-PERFORM-TARGET.
           DISPLAY 'X'.
"""


def test_conditional_goback_does_not_end_the_paragraph():
    main = _units("cobol", _REPRO1)["MAIN-PARA"]
    assert (main["start_line"], main["end_line"]) == (11, 18)
    assert main["calls_out_to"] == ["AFTER-GOBACK-TARGET", "SUBPGM1", "RETURN-TO-MENU", "LOOP-PARA"]


def test_paragraph_named_return_is_not_cut_at_its_own_header():
    para = _units("cobol", _REPRO1)["RETURN-TO-MENU"]
    assert (para["start_line"], para["end_line"]) == (19, 21)
    assert para["calls_out_to"] == ["IN-RETURN-PARA-TARGET"]


def test_exit_perform_does_not_end_the_paragraph():
    loop = _units("cobol", _REPRO1)["LOOP-PARA"]
    assert (loop["start_line"], loop["end_line"]) == (22, 33)
    assert "AFTER-EXIT-PERFORM-TARGET" in loop["calls_out_to"]


def test_cics_return_inside_if_does_not_end_the_paragraph():
    # cics-banking-sample-application-cbsa BNK1CAC.cbl A010: `RETURN TRANSID(...)` on
    # its own line of an EXEC CICS inside an IF, then more PERFORMs.
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CICSRET.
       PROCEDURE DIVISION.
       A010.
           IF EIBCALEN = ZERO
              EXEC CICS
                 RETURN TRANSID('OCAC')
              END-EXEC
           END-IF
           PERFORM POPULATE-TIME-DATE
           PERFORM ABEND-THIS-TASK.
       POPULATE-TIME-DATE.
           DISPLAY 'T'.
       ABEND-THIS-TASK.
           EXIT PARAGRAPH
           DISPLAY 'A'.
"""
    units = _units("cobol", src)
    assert units["A010"]["calls_out_to"] == ["POPULATE-TIME-DATE", "ABEND-THIS-TASK"]
    assert units["A010"]["end_line"] == 11
    # EXIT PARAGRAPH mid-body: the DISPLAY after it is still the paragraph's.
    assert units["ABEND-THIS-TASK"]["end_line"] == 16


def test_last_paragraph_stops_at_end_program_and_next_program_header():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. FIRST.
       PROCEDURE DIVISION.
       FIRST-MAIN.
           PERFORM FIRST-SUB
           GOBACK.
       FIRST-SUB.
           DISPLAY 'F'.
       END PROGRAM FIRST.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SECOND.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-X                   PIC X.
       PROCEDURE DIVISION.
       SECOND-MAIN.
           DISPLAY 'S'
           GOBACK.
       END PROGRAM SECOND.
"""
    units = _units("cobol", src)
    assert (units["FIRST-MAIN"]["start_line"], units["FIRST-MAIN"]["end_line"]) == (4, 6)
    assert (units["FIRST-SUB"]["start_line"], units["FIRST-SUB"]["end_line"]) == (7, 8)
    assert (units["SECOND-MAIN"]["start_line"], units["SECOND-MAIN"]["end_line"]) == (16, 18)


def test_nested_program_header_ends_the_outer_paragraph():
    # No END PROGRAM before the nested program: its IDENTIFICATION DIVISION is the end.
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. OUTER.
       PROCEDURE DIVISION.
       OUTER-MAIN.
           CALL 'INNER'
           GOBACK.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INNER.
       PROCEDURE DIVISION.
       INNER-MAIN.
           GOBACK.
       END PROGRAM INNER.
       END PROGRAM OUTER.
"""
    units = _units("cobol", src)
    assert (units["OUTER-MAIN"]["start_line"], units["OUTER-MAIN"]["end_line"]) == (4, 6)
    assert (units["INNER-MAIN"]["start_line"], units["INNER-MAIN"]["end_line"]) == (10, 11)


def test_a_hyphenated_end_name_is_not_a_program_end():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY 'END PROGRAM'
           PERFORM END-PROGRAM-RTN
           GOBACK.
       END-PROGRAM-RTN.
           DISPLAY 'X'.
"""
    units = _units("cobol", src)
    assert units["MAIN-PARA"]["end_line"] == 7
    assert units["MAIN-PARA"]["calls_out_to"] == ["END-PROGRAM-RTN"]


def test_pli_else_return_does_not_end_the_procedure():
    # navikt/DSF R0010422.pli KONTROLL_AV_INPUT: `ELSE RETURN;` then `CALL SEND_MAP;`;
    # the procedure ends at its own labelled END, not at the next header.
    src = """ R001B1: PROC OPTIONS(MAIN);
   CALL KONTROLL;
 KONTROLL: PROC;
     IF A = B THEN
        X = 1;
     ELSE
        RETURN;
     CALL SEND_MAP;
  END KONTROLL;
 SEND_MAP: PROC;
     X = 2;
  END SEND_MAP;
 END R001B1;
"""
    units = _units("pli", src)
    assert (units["KONTROLL"]["start_line"], units["KONTROLL"]["end_line"]) == (3, 9)
    assert units["KONTROLL"]["calls_out_to"] == ["SEND_MAP"]
    assert (units["SEND_MAP"]["start_line"], units["SEND_MAP"]["end_line"]) == (10, 12)


def test_assembly_keeps_its_terminator_cut():
    src = """foo:
    mov eax, 1
    ret
    db 0
bar:
    ret
"""
    foo = _units("assembly", src)["foo"]
    assert (foo["start_line"], foo["end_line"]) == (1, 3)
