"""#4302: statements between `PROCEDURE DIVISION.` and the first paragraph or
section header (a batch program's main line) are a calls-only `__global_context__`
bucket per PROCEDURE DIVISION -- Python's module-level shape -- so their PERFORM /
CALL / GO TO edges are recorded. The bucket is a synthetic slice: it is never in
the function population and carries no weight."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.function_population import population_functions
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _functions(src: str) -> list[dict]:
    st = _PRISM.split_streams(src, "cobol")
    out = StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=src,
        positional_comment_stream=_PRISM.split_positional_comment_stream(src, "cobol"),
    )
    return out["functions"]


def _entries(src: str) -> list[dict]:
    return [f for f in _functions(src) if f["name"] == "__global_context__"]


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


def test_repro_entry_code_records_its_performs():
    (entry,) = _entries(_REPRO1)
    assert entry["calls_out_to"] == ["ENTRY-TARGET", "MAIN-PARA"]
    assert (entry["start_line"], entry["end_line"]) == (7, 10)


def test_entry_bucket_is_a_weightless_synthetic_slice():
    functions = _functions(_REPRO1)
    (entry,) = [f for f in functions if f["name"] == "__global_context__"]
    assert entry["is_synthetic_slice"] and entry["calls_only"]
    assert entry["magnitude"] == entry["impact"] == 0.0
    assert entry not in population_functions(functions)
    # The real paragraphs are untouched.
    assert len(population_functions(functions)) == 7


def test_batch_main_line_with_inline_perform():
    # carddemo CBACT01C.cbl:70-91: open, inline PERFORM UNTIL loop, close, GOBACK.
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CBACT01C.
       PROCEDURE DIVISION.
           DISPLAY 'START OF EXECUTION OF PROGRAM CBACT01C'.
           PERFORM 0000-ACCTFILE-OPEN.
           PERFORM UNTIL END-OF-FILE = 'Y'
               IF  END-OF-FILE = 'N'
                   PERFORM 1000-ACCTFILE-GET-NEXT
               END-IF
           END-PERFORM.
           PERFORM 9000-ACCTFILE-CLOSE.
           GOBACK.
       1000-ACCTFILE-GET-NEXT.
           READ ACCTFILE-FILE.
       0000-ACCTFILE-OPEN.
           OPEN INPUT ACCTFILE-FILE.
       9000-ACCTFILE-CLOSE.
           CLOSE ACCTFILE-FILE.
"""
    (entry,) = _entries(src)
    assert entry["calls_out_to"] == ["0000-ACCTFILE-OPEN", "1000-ACCTFILE-GET-NEXT", "9000-ACCTFILE-CLOSE"]


def test_using_header_over_several_lines_and_go_to():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUBP.
       DATA DIVISION.
       LINKAGE SECTION.
       01  LK-A                   PIC X.
       01  LK-B                   PIC X.
       PROCEDURE DIVISION USING LK-A
                                LK-B.
           CALL 'HELPER' USING LK-A
           GO TO DONE-PARA.
       DONE-PARA.
           GOBACK.
"""
    (entry,) = _entries(src)
    assert entry["calls_out_to"] == ["HELPER"]
    assert entry["transfers_to"] == ["DONE-PARA"]
    assert entry["start_line"] == 7


def test_one_bucket_per_procedure_division_in_sibling_and_nested_programs():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. FIRST.
       PROCEDURE DIVISION.
           PERFORM FIRST-SUB
           CALL 'INNER'
           GOBACK.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INNER.
       PROCEDURE DIVISION.
           PERFORM INNER-SUB
           GOBACK.
       INNER-SUB.
           DISPLAY 'I'.
       END PROGRAM INNER.
       FIRST-SUB.
           DISPLAY 'F'.
       END PROGRAM FIRST.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SECOND.
       PROCEDURE DIVISION.
           PERFORM SECOND-SUB
           STOP RUN.
       SECOND-SUB.
           DISPLAY 'S'.
       END PROGRAM SECOND.
"""
    entries = sorted(_entries(src), key=lambda f: f["start_line"])
    assert [(e["start_line"], e["end_line"], e["calls_out_to"]) for e in entries] == [
        (3, 6, ["FIRST-SUB", "INNER"]),  # stops at the nested program's header
        (9, 11, ["INNER-SUB"]),
        (20, 22, ["SECOND-SUB"]),
    ]


def test_no_bucket_without_entry_code_or_without_edges():
    paragraph_first = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM SUB-PARA
           STOP RUN.
       SUB-PARA.
           DISPLAY 'S'.
"""
    declaratives = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. D.
       PROCEDURE DIVISION.
       DECLARATIVES.
       ERR-SEC SECTION.
           USE AFTER ERROR PROCEDURE ON INFILE.
       END DECLARATIVES.
       MAIN-SEC SECTION.
           STOP RUN.
"""
    no_edges = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. N.
       PROCEDURE DIVISION.
           DISPLAY 'HELLO'
           STOP RUN.
"""
    assert _entries(paragraph_first) == []
    assert _entries(declaratives) == []
    assert _entries(no_edges) == []
