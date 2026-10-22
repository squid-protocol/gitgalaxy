"""#5042 (oracle_assumptions.md X56 / X47): a pointer compared with another pointer, and NULL in an abbreviated relation.

IBM's relation condition lets a pointer be compared for = / NOT = with NULL or with another pointer (Enterprise COBOL for
z/OS Language Reference, "Conditional expressions"). Two pointers are equal when they address the same storage: the runtime
answers that (CicsTask.samePointer), so a record's ADDRESS OF beside the pointer it was set to is equal too, as in the
oracle. The whole input class: {pointer, BLL cell} x {=, NOT =, IS EQUAL TO ...} pointer-to-pointer, and an abbreviated
`PTR = A OR B` / `OR NULL` / `NOT = NULL`; refused by name: > < >= <= between pointers, a pointer against a non-pointer, a
table / REDEFINES-overlaid / subscripted pointer, ADDRESS OF in a condition.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_bll_cells_5119 as bll  # noqa: E402

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRCMP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  PTR-A                  USAGE POINTER.
       01  PTR-B                  USAGE POINTER.
       01  PTR-C                  USAGE POINTER.
       01  PTR-D                  USAGE POINTER.
       01  PTR-N                  USAGE POINTER.
       01  WS-IMG                 PIC X VALUE '*'.
       01  WS-OUT                 PIC X(20) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       01  A-REC                  PIC X(8).
       PROCEDURE DIVISION.
           EXEC CICS GETMAIN SET(PTR-A) FLENGTH(8)
                INITIMG(WS-IMG) END-EXEC.
           EXEC CICS GETMAIN SET(PTR-B) FLENGTH(8)
                INITIMG(WS-IMG) END-EXEC.
           SET PTR-C TO PTR-A.
           SET ADDRESS OF A-REC TO PTR-A.
           SET PTR-D TO ADDRESS OF A-REC.
           SET PTR-N TO NULL.
           IF PTR-A = PTR-B MOVE 'Y' TO WS-OUT(1:1)
              ELSE MOVE 'N' TO WS-OUT(1:1).
           IF PTR-A = PTR-C MOVE 'Y' TO WS-OUT(2:1)
              ELSE MOVE 'N' TO WS-OUT(2:1).
           IF PTR-A = PTR-D MOVE 'Y' TO WS-OUT(3:1)
              ELSE MOVE 'N' TO WS-OUT(3:1).
           IF PTR-C = PTR-D MOVE 'Y' TO WS-OUT(4:1)
              ELSE MOVE 'N' TO WS-OUT(4:1).
           IF PTR-N = PTR-B MOVE 'Y' TO WS-OUT(5:1)
              ELSE MOVE 'N' TO WS-OUT(5:1).
           IF PTR-A = PTR-B OR PTR-C MOVE 'Y' TO WS-OUT(6:1)
              ELSE MOVE 'N' TO WS-OUT(6:1).
           IF PTR-A = PTR-B OR NULL MOVE 'Y' TO WS-OUT(7:1)
              ELSE MOVE 'N' TO WS-OUT(7:1).
           IF PTR-A NOT = PTR-B MOVE 'Y' TO WS-OUT(8:1)
              ELSE MOVE 'N' TO WS-OUT(8:1).
           EXEC CICS SEND TEXT FROM(WS-OUT) LENGTH(8) ERASE
                END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""
# hand-traced (A and B are two blocks; C is A's address; D is the address of the record set onto A):
# A=B no, A=C yes, A=D yes (one storage under two handles), C=D yes, NULL=B no, A=B OR C yes (A=C), A=B OR NULL no
# (A=B, A=NULL), A NOT = B yes
SENT = "NYYYNYNY"


def _translate(tmp_path: Path, source: str, name: str = "PTRCMP"):
    return bll._translate(tmp_path, source.replace("PROGRAM-ID. PTRCMP.", f"PROGRAM-ID. {name}."))


_FIRST = "IF PTR-A = PTR-B MOVE 'Y' TO WS-OUT(1:1)"


@pytest.mark.parametrize(
    ("cond", "negated"),
    [
        ("PTR-A = PTR-B", False),
        ("PTR-A NOT = PTR-B", True),
        ("PTR-A IS EQUAL TO PTR-B", False),
        ("PTR-A IS NOT EQUAL TO PTR-B", True),
        ("PTR-A EQUAL PTR-B", False),
        ("PTR-A NOT EQUAL TO PTR-B", True),
    ],
)
def test_a_pointer_compared_with_a_pointer_is_the_runtimes_handle_equality(tmp_path, cond, negated):
    r = _translate(
        tmp_path, PROGRAM.replace("IF PTR-A = PTR-B MOVE 'Y' TO WS-OUT(1:1)", f"IF {cond} MOVE 'Y' TO WS-OUT(1:1)", 1)
    )
    assert r.stats["holes"] == [], r.stats["holes"]
    lines = [ln.strip() for ln in r.java.splitlines() if re.search(r"samePointer\(task, f\d+_PTR_A, f\d+_PTR_B", ln)]
    assert lines, r.java
    assert ("!(" in lines[0]) == negated, lines[0]


def test_every_pointer_comparison_of_the_program_translates_whole(tmp_path):
    r = _translate(tmp_path, PROGRAM)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert r.java.count("DetCics.samePointer(") >= 8


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        ("IF PTR-A > PTR-B", "only = and NOT = compare a pointer"),
        ("IF PTR-A < PTR-B", "only = and NOT = compare a pointer"),
        ("IF PTR-A >= PTR-B", "only = and NOT = compare a pointer"),
        ("IF PTR-A = WS-OUT", "a pointer compared with a non-pointer"),
        ("IF PTR-A = ZERO", "a pointer compared with a non-pointer"),
        ("IF PTR-A = ADDRESS OF A-REC", "ADDRESS OF"),
        ("IF ADDRESS OF A-REC = NULL", "ADDRESS OF"),
    ],
)
def test_what_is_not_a_pointer_test_is_refused_by_name(tmp_path, edit, why):
    r = _translate(tmp_path, PROGRAM.replace("IF PTR-A = PTR-B MOVE", edit + " MOVE", 1))
    assert r.stats["holes"], "an untranslatable condition must be a hole, never silently translated"
    assert any(re.search(why, h) for h in r.stats["holes"]), (why, r.stats["holes"])


def test_the_oracle_reads_the_same_comparisons():
    sys.path.insert(0, str(HERE.parent / "tools"))
    import equivalence_cics as ec

    text, _ = ec.translate(PROGRAM)
    assert "IF PTR-A = PTR-B OR NULL" in text and "IF PTR-A NOT = PTR-B" in text


# ---- an OS/VS COBOL BLL cell compared with another cell ---------------------------------------------------------
BLL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLLCMP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IMG                 PIC X VALUE '*'.
       01  WS-OUT                 PIC X(4) VALUE SPACES.
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(4).
       01  PARMLIST.
           02  FILLER             PIC S9(8) COMP.
           02  CELL-A             PIC S9(8) COMP.
           02  CELL-B             PIC S9(8) COMP.
           02  CELL-C             PIC S9(8) COMP.
       01  REC-A                  PIC X(8).
       01  REC-B                  PIC X(8).
       01  REC-C                  PIC X(8).
       PROCEDURE DIVISION.
           SERVICE RELOAD PARMLIST.
           EXEC CICS GETMAIN SET(CELL-A) FLENGTH(8)
                INITIMG(WS-IMG) END-EXEC.
           EXEC CICS GETMAIN SET(CELL-B) FLENGTH(8)
                INITIMG(WS-IMG) END-EXEC.
           MOVE CELL-A TO CELL-C.
           IF CELL-A = CELL-B MOVE 'Y' TO WS-OUT(1:1)
              ELSE MOVE 'N' TO WS-OUT(1:1).
           IF CELL-A = CELL-C MOVE 'Y' TO WS-OUT(2:1)
              ELSE MOVE 'N' TO WS-OUT(2:1).
           IF CELL-B NOT = CELL-C MOVE 'Y' TO WS-OUT(3:1)
              ELSE MOVE 'N' TO WS-OUT(3:1).
           EXEC CICS RETURN END-EXEC.
"""


@pytest.mark.parametrize(
    ("spelling", "lowered"),
    [
        ("CELL-A = CELL-B", "CELL-A = CELL-B"),
        ("CELL-A NOT = CELL-B", "CELL-A NOT = CELL-B"),
        ("CELL-A IS EQUAL TO CELL-B", "CELL-A = CELL-B"),
        ("CELL-A IS NOT EQUAL TO CELL-B", "CELL-A NOT = CELL-B"),
    ],
)
def test_a_bll_cell_compared_with_a_cell_is_a_pointer_comparison(tmp_path, spelling, lowered):
    source = BLL.replace("IF CELL-A = CELL-B", f"IF {spelling}", 1)
    r = bll._translate(tmp_path, source)
    assert r.stats["holes"] == [], r.stats["holes"]
    assert "DetCics.samePointer(" in r.java
    assert any(ln.startswith(f"IF {lowered}") for ln in bll._lowered(tmp_path, source)), lowered


def test_a_bll_cell_compared_with_a_non_cell_is_still_used_as_a_number(tmp_path):
    with pytest.raises(Exception, match="used as a number"):
        bll._translate(tmp_path, BLL.replace("IF CELL-A = CELL-B", "IF CELL-A = WS-OUT", 1))


# ---- end to end -------------------------------------------------------------------------------------------------
_E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")


@_E2E
def test_pointer_comparisons_are_proven_against_gnucobol(tmp_path):
    """GnuCOBOL and the det port SEND the hand-traced answers: two blocks differ, a copy and a record's ADDRESS OF equal."""
    bll._prove(tmp_path, "PTRCMP", PROGRAM, SENT)
