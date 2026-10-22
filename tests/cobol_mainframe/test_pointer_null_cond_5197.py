"""#5197 (oracle_assumptions.md X56 / X47): a pointer or a BLL cell compared with NULL (a BLL cell with ZERO too).

IBM's relation condition lets a pointer be compared only for = / NOT = (with NULL or another pointer); an OS/VS COBOL BLL
cell is a fullword, so `IF cell = ZERO` is its test for no address, and IBM's conversion to VS COBOL II makes the cell a
POINTER, so ZERO becomes NULL. The det translator reads a pointer's NULL as the handle zero (X47: all-zero bytes). The whole
input class: {pointer, BLL cell} x {NULL, ZERO} x {=, NOT =, IS EQUAL TO} x both operand orders translate; every other
relation (a pointer against ZERO, > < >=, NULL against NULL, a table or REDEFINES pointer, a subscripted one, a secondary
cell) is refused by name, and NULL is still no operand of arithmetic or MOVE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

PTR = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRNUL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  USERPTR                USAGE POINTER.
       01  P2                     USAGE POINTER.
       01  WS-IMG                 PIC X VALUE '*'.
       01  WS-OUT                 PIC X(4) VALUE SPACES.
       LINKAGE SECTION.
       01  USER-REC               PIC X(8).
       PROCEDURE DIVISION.
           EXEC CICS GETMAIN SET(USERPTR) FLENGTH(8)
                INITIMG(WS-IMG) END-EXEC.
           IF USERPTR = NULL
               MOVE 'NULL' TO WS-OUT
           ELSE
               MOVE 'SOME' TO WS-OUT
           END-IF.
           EXEC CICS RETURN END-EXEC.
"""
CONDITION = "IF USERPTR = NULL"

BLL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLLNUL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-IMG                 PIC X VALUE '*'.
       01  WS-OUT                 PIC X(4) VALUE SPACES.
       LINKAGE SECTION.
       01  PARMLIST.
           02  FILLER             PIC S9(8) COMP.
           02  USERPTR            PIC S9(8) COMP.
           02  USERPTR1           PIC S9(8) COMP.
       01  USER-REC.
           02  UFIELD             PIC X(5000).
       PROCEDURE DIVISION.
           EXEC CICS GETMAIN SET(USERPTR) FLENGTH(5000)
                INITIMG(WS-IMG) END-EXEC.
           ADD 4096, USERPTR GIVING USERPTR1.
           SERVICE RELOAD USER-REC.
           IF USERPTR = ZERO
               MOVE 'NULL' TO WS-OUT
           ELSE
               MOVE 'SOME' TO WS-OUT
           END-IF.
           EXEC CICS RETURN END-EXEC.
"""
BLL_CONDITION = "IF USERPTR = ZERO"

# every spelling of the test, both operand orders: (condition text, negated)
SPELLINGS = [
    (f"{subject} {op} {obj}", neg)
    for obj in ("NULL", "NULLS")
    for subject, op, neg in [
        ("PTR", "=", False),
        ("PTR", "NOT =", True),
        ("PTR", "IS EQUAL TO", False),
        ("PTR", "IS NOT EQUAL TO", True),
        ("PTR", "EQUAL", False),
        ("PTR", "NOT EQUAL TO", True),
    ]  # fmt: skip
] + [
    (f"NULL {op} PTR", neg)
    for op, neg in [("=", False), ("NOT =", True), ("IS EQUAL TO", False), ("IS NOT EQUAL TO", True)]
]


def _translate(tmp_path: Path, source: str, name: str = "PTRNUL"):
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / f"{name}.cbl").write_text(source, encoding="utf-8")
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True, exist_ok=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    stub = f"package com.x.service;\nimport com.x.cics.CicsTask;\npublic class {name.title()}Service {{\n" \
           "    public void runTask(CicsTask task) {}\n}\n"  # fmt: skip
    return P.translate(tmp_path / f"{name}.cbl", [], stub, "com.x", {}, tmp_path / "proj")


def _java_test(r) -> str:
    lines = [ln.strip() for ln in r.java.splitlines() if "compareFigurative(" in ln and "LOW_VALUES" in ln]
    assert len(lines) == 1, lines
    return lines[0]


@pytest.mark.parametrize(("cond", "negated"), SPELLINGS)
def test_a_pointer_compared_with_null_translates_whole(tmp_path, cond, negated):
    r = _translate(tmp_path, PTR.replace(CONDITION, "IF " + cond.replace("PTR", "USERPTR")))
    assert r.stats["holes"] == [], r.stats["holes"]
    line = _java_test(r)
    assert "Cobol.compareFigurative(f" in line and "USERPTR" in line.upper() + r.java.upper()
    assert ("!(" in line) == negated, line


@pytest.mark.parametrize(("cond", "negated"), SPELLINGS)
def test_a_bll_cell_compared_with_zero_or_null_is_the_pointer_test(tmp_path, cond, negated):
    for nil in ("NULL", "ZERO", "ZEROS", "ZEROES", "LOW-VALUE", "LOW-VALUES"):
        c = cond.replace("PTR", "USERPTR").replace("NULLS", nil).replace("NULL", nil)
        (tmp_path / nil).mkdir()
        r = _translate(tmp_path / nil, BLL.replace(BLL_CONDITION, "IF " + c), "BLLNUL")
        assert r.stats["holes"] == [], (c, r.stats["holes"])
        assert ("!(" in _java_test(r)) == negated, c


def test_the_test_is_the_handles_all_zero_bytes(tmp_path):
    """The test is the handle's all-zero bytes: a freshly GETMAINed pointer is not NULL, a NULLed one is."""
    r = _translate(tmp_path, PTR)
    assert "Figurative.LOW_VALUES, CS) == 0" in r.java


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        (
            "IF USERPTR = LOW-VALUES",
            "a pointer compared with a non-pointer",
        ),  # (#5042: only a BLL cell reads it as NULL)
        ("IF USERPTR = ZERO", "a pointer compared with a non-pointer"),  # IBM: a pointer is no number
        ("IF USERPTR > NULL", "only = and NOT ="),
        ("IF USERPTR < NULL", "only = and NOT ="),
        ("IF USERPTR >= NULL", "only = and NOT ="),
        ("IF NULL = NULL", "NULL compared with NULL"),
        ("IF WS-OUT = NULL", "not a plain USAGE POINTER"),
        ("IF USERPTR(1) = NULL", "not a plain pointer"),
        ("IF NULL", "NULL"),
    ],
)
def test_what_is_not_a_pointer_test_is_refused_by_name(tmp_path, edit, why):
    r = _translate(tmp_path, PTR.replace(CONDITION, edit))
    assert r.stats["holes"], "an untranslatable condition must be a hole, never silently translated"
    assert any(__import__("re").search(why, h) for h in r.stats["holes"]), (why, r.stats["holes"])


def test_null_is_still_no_operand_of_arithmetic_or_move(tmp_path):
    for stmt in ("MOVE NULL TO WS-OUT.", "ADD NULL TO WS-OUT."):
        r = _translate(
            tmp_path, PTR.replace("EXEC CICS RETURN END-EXEC.", stmt + "\n           EXEC CICS RETURN END-EXEC.")
        )
        assert r.stats["holes"], stmt


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        ("IF USERPTR1 = LOW-VALUES", "secondary cell"),
        ("IF USERPTR1 = ZERO", "secondary cell"),  # a long record's secondary cell holds no address of its own
        ("IF USERPTR > ZERO", "used as a number"),
        ("IF USERPTR NOT < ZERO", "used as a number"),
    ],
)
def test_a_bll_cell_compared_any_other_way_is_still_refused(tmp_path, edit, why):
    from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: F401

    with pytest.raises(Exception, match=why):
        _translate(tmp_path, BLL.replace(BLL_CONDITION, edit), "BLLNUL")


def test_the_oracle_reads_the_same_lowered_test():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cics as ec

    text, _ = ec.translate(BLL.replace(BLL_CONDITION, "IF ZERO NOT = USERPTR"))
    assert "IF USERPTR NOT = NULL" in text and "USAGE POINTER" in text
    text, _ = ec.translate(PTR)
    assert "IF USERPTR = NULL" in text
