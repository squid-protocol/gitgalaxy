"""#5859: the HLASM + EXEC CICS front end (det/hlasm.py) lowers a command-level CICS assembler program to COBOL, per
instruction as the z/Architecture Principles of Operation (SA22-7832) defines it, and refuses by name anything outside
its subset. ZECSNC (burned estate zecs) lowers; ZECS002 stays refused, naming its first construct outside the subset."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # the det parser; the ground-truth CI job has no translator extra

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import hlasm  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402

DATA = [
    "DFHEISTG DSECT",
    "W_A      DS    CL4",
    "W_B      DS    CL4",
    "W_C      DS    CL1",
    "W_H      DS    H",
    "W_F      DS    F",
    "W_G      DS    0CL6",
    "W_G1     DS    CL2",
    "W_G2     DS    CL4",
    "W_GLEN   EQU   *-W_G",
]
REGS = ["R2       EQU   2", "R10      EQU   10", "R11      EQU   11", "R12      EQU   12", "R14      EQU   14"]


def _asm(*code: str, data: tuple[str, ...] = ()) -> str:
    entry = "PROG     DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11"
    return "\n".join([*DATA, *data, entry, *code, *REGS, "         END   PROG"]) + "\n"


def lower(*code: str, data: tuple[str, ...] = ()) -> str:
    return hlasm.lower_text(_asm(*code, data=data), "T.asm")


def _branch(setter: str, mask: str) -> str:
    out = lower(setter, f"         BC    {mask},DONE", "DONE     DS    0H", "         EXEC CICS RETURN")
    m = re.search(r"IF (.*)\n\s+GO TO DONE", out)
    return m.group(1) if m else "CONTINUE" if "CONTINUE" in out else "GO TO" if "GO TO DONE" in out else ""


@pytest.mark.parametrize(
    ("setter", "mask", "cond"),
    [
        ("CLC   W_A,W_B", "B'1000'", "W-A = W-B"),  # CC 0 (equal)
        ("CLC   W_A,W_B", "B'0111'", "W-A NOT = W-B"),  # CC 1, 2 (CC 3 cannot follow CLC)
        ("CLI   W_C,C'Y'", "B'1000'", "W-C = 'Y'"),
        ("CLI   W_C,X'40'", "B'0111'", "W-C NOT = X'40'"),
        ("CH    R2,W_H", "B'1000'", "HL-R2 = W-H"),  # arithmetic: CC 1 low, CC 2 high
        ("CH    R2,W_H", "B'0100'", "HL-R2 < W-H"),
        ("CH    R2,W_H", "B'0010'", "HL-R2 > W-H"),
        ("CH    R2,W_H", "B'1100'", "HL-R2 <= W-H"),
        ("CH    R2,W_H", "B'1010'", "HL-R2 >= W-H"),
        ("CH    R2,W_H", "B'0110'", "HL-R2 NOT = W-H"),
        ("OC    W_F,W_F", "B'1000'", "W-F = 0"),  # OC X,X: CC 0 zero, CC 1 nonzero
        ("OC    W_F,W_F", "B'0111'", "W-F NOT = 0"),
        ("CLC   W_A,W_B", "B'1111'", "GO TO"),
        ("CLC   W_A,W_B", "B'0000'", "CONTINUE"),
    ],
)
def test_each_condition_code_outcome_against_each_mask(setter, mask, cond):
    assert _branch(f"         {setter}", mask) == cond


@pytest.mark.parametrize("mask", ["B'0100'", "B'0010'", "B'1100'"])
def test_a_logical_compare_read_as_high_or_low_is_refused_for_ebcdic_collating(mask):
    with pytest.raises(hlasm.Refused, match="EBCDIC collating"):
        _branch("         CLC   W_A,W_B", mask)


def test_a_conditional_branch_not_directly_after_its_setter_is_refused():
    with pytest.raises(hlasm.Refused, match="not directly after"):
        lower("         CLC   W_A,W_B", "         LA    R2,1", "         BC    B'1000',D", "D        DS    0H")


def test_sth_stores_the_low_halfword_signed():
    out = lower("         LA    R2,1", "         STH   R2,W_H", "         EXEC CICS RETURN")
    assert "FUNCTION MOD(HL-R2 + 32768, 65536) - 32768" in out
    # the expression is the POPS rule (bits 48-63 read as a signed halfword) over the whole fullword range
    for v, want in [(5, 5), (-1, -1), (32767, 32767), (32768, -32768), (-32769, 32767), (65536 + 7, 7)]:
        assert (v + 32768) % 65536 - 32768 == want


def test_mvc_displacement_and_explicit_length_are_reference_modification():
    out = lower("         MVC   W_A+1(2),W_B", "         MVC   W_G2,W_A", "         EXEC CICS RETURN")
    assert "MOVE W-B(1:2)\n             TO W-A(2:2)" in out
    assert "MOVE W-A\n             TO W-G2" in out


@pytest.mark.parametrize(
    ("code", "why"),
    [
        ("         MVC   W_G1,W_G", "overlapping MVC"),
        ("         MVC   W_A,W_C", "past its source symbol"),
        ("         MVC   W_A(2),W_H", "binary fields"),
        ("         IC    R2,W_C", "instruction IC"),
        ("         SR    R2,R2", "instruction SR"),
        ("         ST    R12,W_F", "reserved register 12"),
        ("         LA    R2,W_A", "LA of an address"),
        ("         MVC   W_A,=C'ABCD'", "MVC W_A"),
    ],
)
def test_outside_the_subset_is_refused_by_name(code, why):
    with pytest.raises(hlasm.Refused, match=re.escape(why)):
        lower(code, "         EXEC CICS RETURN")


def test_storage_keeps_hlasm_alignment_overlays_and_equ_lengths():
    out = lower(
        "         LA    R2,W_GLEN",
        "         EXEC CICS RETURN",
        data=("W_X      DS    0CL8", "W_X1     DS    CL1", "W_X2     DS    F"),
    )
    assert "       01  W-G.\n           05  W-G1 PIC X(2).\n           05  W-G2 PIC X(4)." in out
    assert "MOVE 6 TO HL-R2" in out  # W_GLEN EQU *-W_G
    # W_X starts at 22: F aligns W_X2 to 24, and the skipped byte is a FILLER so the group keeps HLASM offsets
    assert "05  W-X1 PIC X(1).\n           05  FILLER PIC X(1).\n           05  W-X2 PIC S9(9) COMP-5." in out
    with pytest.raises(hlasm.Refused, match="not covered exactly"):
        lower("         EXEC CICS RETURN", data=("W_Y      DS    0CL3", "W_Y1     DS    CL2", "W_Y2     DS    CL2"))


def test_bas_and_bcr_are_return_ids_and_every_paragraph_is_one_sentence():
    out = lower(
        "         BAS   R14,SUB",
        "         EXEC CICS RETURN",
        "SUB      DS    0H",
        "         BCR   B'1111',R14",
    )
    assert "MOVE 1 TO HL-R14\n           GO TO SUB.\n       HL-RET-1." in out
    assert "GO TO\n               HL-RET-1\n               DEPENDING ON HL-R14" in out
    assert "ABEND ABCODE('ASRA') NODUMP END-EXEC." in out  # a return id no BAS stored: a program check
    proc = out.split("PROCEDURE DIVISION.\n", 1)[1].splitlines()
    for i, line in enumerate(proc):  # each paragraph header follows a closed sentence
        if re.fullmatch(r"       [A-Z0-9-]+\.", line) and i:
            last = next(t for t in reversed(proc[:i]) if not t.startswith("      *"))
            assert last.endswith("."), (line, last)


def test_exec_cics_operands_name_the_lowered_fields():
    out = lower("         EXEC  CICS SEND FROM(W_A) LENGTH(4) ERASE", "         EXEC CICS RETURN")
    assert (
        "EXEC CICS\n               SEND\n               FROM(W-A)\n               LENGTH(4)\n               ERASE END-EXEC"
        in out
    )
    with pytest.raises(hlasm.Refused, match="EXEC CICS operand NOPE"):
        lower("         EXEC  CICS SEND FROM(NOPE) LENGTH(4)")


def test_the_service_stub_marks_the_program_as_a_cics_task():
    stub = hlasm.service_stub("ZECSNC", "com.example.port")
    assert "runTask(CicsTask" in stub and "package com.example.port.service;" in stub


ZECS = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora")) / "zecs" / "Source"


@pytest.mark.skipif(not (ZECS / "ZECSNC.asm").is_file(), reason="zecs corpus not fetched (mainframe_corpus.py fetch)")
def test_zecsnc_lowers_and_zecs002_is_refused_by_name():
    nc = (ZECS / "ZECSNC.asm").read_text(encoding="latin-1").splitlines()
    lowered = SRC.assembler_lowered(nc, str(ZECS / "ZECSNC.asm"))
    assert lowered is not nc and any("PROGRAM-ID. ZECSNC." in t for t in lowered)
    z2 = ZECS / "ZECS002.asm"
    with pytest.raises(
        SRC.MacroLevelCics, match=r"ZECS002\.asm:\d+: CICS Assembler not supported \(DFHEIENT.*DC 08XL01"
    ):
        SRC.assembler_lowered(z2.read_text(encoding="latin-1").splitlines(), str(z2))
