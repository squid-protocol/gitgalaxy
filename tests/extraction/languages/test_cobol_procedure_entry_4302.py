"""#4302 / #7170: the statements between `PROCEDURE DIVISION.` and the first paragraph
or section header (a program's main line) are one unit per PROCEDURE DIVISION, so their
PERFORM / CALL / GO TO edges are recorded (#4302).

#7170: that unit is a real function, named after the program's PROGRAM-ID, with
`def_shape` "main_line": measured like a paragraph (from its header, `loc` the physical
span, args from the header's USING list), in the function population with its own
weight, kept even without edges, never an orphan, and never a call-resolution target.
Before, it was a calls-only `__global_context__` bucket with no size or complexity, so a
program that does its work before its first paragraph (or has none) was invisible to
every per-function view. Without a PROGRAM-ID to name it, it stays that bucket."""

from gitgalaxy.core import call_resolver
from gitgalaxy.core.detector import COBOL_MAIN_LINE_SHAPE, StructuralExtractor
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
    return [f for f in _functions(src) if f.get("def_shape") == COBOL_MAIN_LINE_SHAPE]


# The #4302 issue's REPRO1.cbl, verbatim.
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


def test_repro_main_line_records_its_performs_under_the_program_name():
    (entry,) = _entries(_REPRO1)
    assert entry["name"] == "REPRO1"
    assert entry["calls_out_to"] == ["ENTRY-TARGET", "MAIN-PARA"]
    # from the PROCEDURE DIVISION header to GOBACK, physical span like a paragraph
    assert (entry["start_line"], entry["end_line"], entry["loc"]) == (7, 10, 4)


def test_main_line_is_a_weighted_member_of_the_population():
    functions = _functions(_REPRO1)
    (entry,) = _entries(_REPRO1)
    assert not entry.get("is_synthetic_slice") and not entry.get("calls_only")
    assert entry["impact"] > 0.0
    assert entry in population_functions(functions)
    # The seven real paragraphs are untouched; no __global_context__ bucket is left.
    assert len(population_functions(functions)) == 8
    assert not [f for f in functions if f["name"] == "__global_context__"]


def test_main_line_is_never_an_orphan_or_a_duplicate():
    (entry,) = _entries(_REPRO1)
    assert entry["usage_status"] == 0


def test_program_with_no_paragraphs_is_one_unit_with_its_complexity():
    # acherm/agentic-chessengine-cobol-codex src/eval.cob's shape: all the work before any paragraph.
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. NOPARAS.
       PROCEDURE DIVISION.
           DISPLAY "HELLO"
           IF 1 = 1
               DISPLAY "YES"
           END-IF
           GOBACK.
"""
    (entry,) = _entries(src)
    assert entry["name"] == "NOPARAS"
    assert (entry["start_line"], entry["end_line"]) == (3, 8)
    assert entry["branch_count"] >= 1  # the IF


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
    assert entry["name"] == "CBACT01C"
    assert entry["calls_out_to"] == ["0000-ACCTFILE-OPEN", "1000-ACCTFILE-GET-NEXT", "9000-ACCTFILE-CLOSE"]
    assert entry["branch_count"] > 0  # the PERFORM UNTIL loop and its IF now count


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
    assert (entry["start_line"], entry["end_line"]) == (7, 10)


def test_main_line_args_are_the_procedure_division_using_list_only():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUBQ.
       PROCEDURE DIVISION USING LK-A LK-B.
           CALL 'HELPER' USING LK-A LK-B LK-C
           GOBACK.
"""
    (entry,) = _entries(src)
    # the program's two parameters; the CALL's three operands are not the main line's own
    assert entry["args"] == 2


def test_one_main_line_per_procedure_division_in_sibling_and_nested_programs():
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
    assert [(e["name"], e["start_line"], e["end_line"], e["calls_out_to"]) for e in entries] == [
        ("FIRST", 3, 6, ["FIRST-SUB", "INNER"]),  # stops at the nested program's header
        ("INNER", 9, 11, ["INNER-SUB"]),
        ("SECOND", 20, 22, ["SECOND-SUB"]),
    ]


def test_quoted_program_id_names_the_main_line():
    src = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. 'QUOTED'.
       PROCEDURE DIVISION.
           DISPLAY 'Q'
           GOBACK.
"""
    (entry,) = _entries(src)
    assert entry["name"] == "QUOTED"


def test_no_main_line_without_entry_code():
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
    assert _entries(paragraph_first) == []
    assert _entries(declaratives) == []
    # and neither grows a bucket of the old kind
    assert not [f for f in _functions(paragraph_first) if f["name"] == "__global_context__"]


def test_main_line_without_edges_is_kept():
    no_edges = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. N.
       PROCEDURE DIVISION.
           DISPLAY 'HELLO'
           STOP RUN.
"""
    (entry,) = _entries(no_edges)
    assert (entry["name"], entry["calls_out_to"]) == ("N", [])


def test_without_a_program_id_the_main_line_stays_a_calls_only_bucket():
    src = """       PROCEDURE DIVISION.
           PERFORM ONLY-PARA
           GOBACK.
       ONLY-PARA.
           DISPLAY 'O'.
"""
    functions = _functions(src)
    assert _entries(src) == []
    (bucket,) = [f for f in functions if f["name"] == "__global_context__"]
    assert bucket["calls_only"] and bucket["calls_out_to"] == ["ONLY-PARA"]


def test_main_line_is_not_a_call_resolution_target():
    # CALLER performs a paragraph named like CALLEE's program: it must not land on CALLEE's main line.
    caller = {"path": "a.cbl", "lang_id": "cobol", "functions": [{"name": "CALLEE", "start_line": 9}]}
    callee = {"path": "b.cbl", "lang_id": "cobol",
              "functions": [{"name": "CALLEE", "start_line": 3, "def_shape": COBOL_MAIN_LINE_SHAPE}]}  # fmt: skip
    index = call_resolver._index([caller, callee])
    paths = {d.path for bucket in index.values() for d in bucket.defs}
    assert paths == {"a.cbl"}
