"""#5859: the HLASM + EXEC CICS front end (det/hlasm.py) lowers a command-level CICS assembler program to COBOL, per
instruction as the z/Architecture Principles of Operation (SA22-7832) defines it, and refuses by name anything outside
its subset. ZECSNC and ZECS002 (burned estate zecs) lower; slice 3b is the address model (a register holding an address)."""

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
REGS = [
    "R2       EQU   2",
    "R3       EQU   3",
    "R4       EQU   4",
    "R5       EQU   5",
    "R6       EQU   6",
    "R10      EQU   10",
    "R11      EQU   11",
    "R12      EQU   12",
    "R14      EQU   14",
]


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
        ("         ICM   R2,1,W_C", "instruction ICM"),
        ("         SR    R2,R14", "only SR Rn,Rn"),
        ("         XC    W_A,W_B", "only XC X,X"),
        ("         XC    W_H,W_H", "XC on binary fields"),
        ("         MVC   W_A,=C'AB'", "MVC W_A"),
        ("         BCT   R2,NOWHERE", "branch target NOWHERE"),
        ("         ST    R12,W_F", "reserved register 12"),
        ("         LA    R2,W_H", "binary field W_H"),
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


def test_duplicated_c_and_x_storage_is_one_field_of_n_elements():
    out = lower(
        "         EXEC CICS RETURN",
        data=("W_D1     DS    4CL2", "W_D2     DS    3XL1", "W_D3     DS    1CL3", "W_D4     DS    CL1"),
    )
    assert "W-D1 PIC X(8)." in out and "W-D2 PIC X(3)." in out and "W-D3 PIC X(3)." in out
    csect = "\n".join(
        [
            *DATA,
            "PROG     DFHEIENT CODEREG=(R12),DATAREG=R10,EIBREG=R11",
            "         LTORG",
            "EIGHT_40 DC    08XL01'40'",
            "ASC_20   DC    3XL02'2021'",
            "CHARS    DC    2CL3'AB'",
            *REGS,
            "         END   PROG",
        ]
    )
    out = hlasm.lower_text(csect + "\n", "T.asm")
    assert "PIC X(8)\n" in out and "VALUE X'4040404040404040'." in out
    assert "VALUE X'202120212021'." in out  # each copy is the element, so the pair repeats
    assert "PIC X(6)" in out and "VALUE 'AB AB '." in out


@pytest.mark.parametrize("data", ["W_H2     DS    2H", "W_F2     DS    2F", "W_D8     DS    2D"])
def test_duplicated_binary_storage_is_refused(data):
    with pytest.raises(hlasm.Refused, match="DS 2"):
        lower("         EXEC CICS RETURN", data=(data,))


def test_sr_xc_bct_and_the_literal_pool_move():
    out = lower(
        "         SR    R2,R2",
        "         XC    W_A,W_A",
        "         XC    W_G+2(2),W_G+2",
        "         MVC   W_A,=C'ab''c'",
        "LOOP     DS    0H",
        "         BCT   R2,LOOP",
        "         EXEC CICS RETURN",
    )
    assert "MOVE 0 TO HL-R2" in out
    assert "MOVE LOW-VALUES TO W-A\n" in out
    assert "MOVE LOW-VALUES TO W-G(3:2)" in out
    assert "MOVE 'ab''c'\n             TO W-A" in out
    assert "FUNCTION MOD(HL-R2 - 1 + 2147483648, 4294967296)\n               - 2147483648" in out
    assert "IF HL-R2 NOT = 0\n               GO TO LOOP" in out


def test_a_conditional_branch_after_sr_xc_or_bct_is_refused():
    for setter in ("SR    R2,R2", "XC    W_A,W_A", "BCT   R2,DONE"):
        with pytest.raises(hlasm.Refused):
            _branch(f"         {setter}", "B'1000'")


ZECS = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora")) / "zecs" / "Source"


@pytest.mark.skipif(not (ZECS / "ZECSNC.asm").is_file(), reason="zecs corpus not fetched (mainframe_corpus.py fetch)")
def test_zecsnc_and_zecs002_lower():
    for name, prog in (("ZECSNC", "ZECSNC"), ("ZECS002", "ZECS002")):
        path = ZECS / f"{name}.asm"
        lowered = SRC.assembler_lowered(path.read_text(encoding="latin-1").splitlines(), str(path))
        assert any(f"PROGRAM-ID. {prog}." in line for line in lowered)
        assert all(len(line.rstrip()) <= 72 for line in lowered)


# ---- slice 3b: the address model (a register holding an address) -------------------------------------------------------
ADDR = ("W_TAB    DS    CL256", "W_BUF    DS    CL8")
ASRA = "EXEC CICS ABEND ABCODE('ASRA') NODUMP END-EXEC"


def addr(*code: str) -> str:
    return lower(*code, "         EXEC CICS RETURN", data=ADDR)


def test_la_of_a_symbol_is_region_times_65536_plus_offset_and_with_a_displacement_stays_below_2_31():
    out = addr("         LA    R3,W_BUF", "         LA    R4,W_TAB+3", "         LA    R3,5(,R3)")
    assert "MOVE 65536 TO HL-R3" in out  # the first symbol whose address is taken is region 1
    assert "MOVE 131075 TO HL-R4" in out  # region 2, offset 3
    assert "FUNCTION MOD(HL-R3 + 5, 2147483648)" in out


def test_a_dereference_selects_the_region_checks_the_range_and_abends_asra_outside():
    out = addr("         LA    R3,W_BUF", "         CLI   0(R3),C':'", "         BC    B'1000',D", "D        DS    0H")
    assert "DIVIDE HL-R3 BY 65536 GIVING HL-RG REMAINDER HL-OF" in out
    assert "WHEN 1\n                   IF HL-OF < 0 OR HL-OF > 7" in out  # W_BUF is 8 bytes
    assert "MOVE W-BUF(HL-OF + 1:1) TO HL-B" in out
    assert "IF HL-B = X'7A'" in out  # C':' is the EBCDIC byte 7A, not ASCII 3A
    assert out.count(ASRA) == 2  # past the end, and WHEN OTHER


def test_mvc_one_byte_through_registers_both_forms_and_the_explicit_length_one():
    for dst in ("0(R3)", "1(,R3)", "0(1,R3)"):
        out = addr("         LA    R3,W_BUF", f"         MVC   {dst},W_C")
        assert "MOVE W-C TO HL-B" in out and "MOVE HL-B\n                         TO W-BUF(HL-OF + 1:1)" in out
        assert out.count(ASRA) == 2
    with pytest.raises(hlasm.Refused, match="only one byte through a register"):
        addr("         LA    R3,W_BUF", "         MVC   0(2,R3),W_C")


def test_ic_replaces_only_the_low_eight_bits_and_an_indexed_table_byte_is_a_bounded_offset():
    out = addr(
        "         LA    R3,W_BUF", "         LA    R5,0", "         IC    R5,0(R3)", "         IC    R5,W_TAB(R5)"
    )
    assert out.count("HL-R5 - FUNCTION MOD(HL-R5, 256) + HL-N") == 2
    assert "COMPUTE HL-OF = 0 + HL-R5" in out and "HL-OF > 255" in out and "MOVE W-TAB(HL-OF + 1:1) TO HL-B" in out


@pytest.mark.parametrize(
    ("mask", "bytes_taken"),
    [("B'1111'", [1, 2, 3, 4]), ("B'0111'", [2, 3, 4]), ("B'0100'", [2]), ("B'0110'", [2, 3]), ("B'1000'", [1])],
)
def test_stcm_stores_the_selected_bytes_side_by_side_high_byte_first(mask, bytes_taken):
    out = addr("         LA    R5,0", f"         STCM  R5,{mask},W_BUF")
    picks = re.findall(r"MOVE HL-BUF\((\d):1\) TO HL-OUT\((\d):1\)", out)
    assert [(int(a), int(b)) for a, b in picks] == [(i, n + 1) for n, i in enumerate(bytes_taken)]
    assert f"MOVE HL-OUT(1:{len(bytes_taken)})\n             TO W-BUF(1:{len(bytes_taken)})" in out


def test_stcm_through_a_register_address_and_a_zero_mask_refusal():
    out = addr("         LA    R3,W_BUF", "         LA    R5,0", "         STCM  R5,B'0100',0(R3)")
    assert "TO W-BUF(HL-OF + 1:1)" in out
    with pytest.raises(hlasm.Refused, match="STCM mask"):
        addr("         LA    R5,0", "         STCM  R5,B'0000',W_BUF")


def test_tr_translates_each_byte_through_the_256_byte_table():
    out = addr("         LA    R3,W_BUF", "         TR    0(2,R3),W_TAB")
    assert out.count("MOVE W-TAB(HL-N + 1:1)") == 2  # one per byte, the table indexed by the byte value
    assert "MOVE W-BUF(HL-OF + 1:1) TO HL-LO" in out and "HL-OF > 6" in out  # two bytes must fit in the 8
    with pytest.raises(hlasm.Refused, match="shorter than 256"):
        addr("         TR    W_BUF,W_BUF")


def test_sll_is_a_wrapping_32_bit_left_shift():
    out = addr("         LA    R2,1", "         SLL   R2,31", "         SLL   R2,0", "         SLL   R2,32")
    assert "FUNCTION MOD(HL-R2, 2) * 2147483648" in out  # only the low 32-k bits survive
    assert out.count("- 2147483648") == 1 and "MOVE 0 TO HL-R2" in out
    for v, k, want in [(1, 31, -(2**31)), (3, 31, -(2**31)), (-1, 4, -16), (0x40000000, 1, -(2**31)), (5, 2, 20)]:
        assert ((v % 2 ** (32 - k)) * 2**k + 2**31) % 2**32 - 2**31 == want  # the emitted arithmetic


def test_sldl_shifts_the_even_odd_pair_as_one_64_bit_value():
    out = addr("         LA    R4,1", "         LA    R5,3", "         SLDL  R4,4")
    assert "DIVIDE HL-T BY 268435456 GIVING HL-X REMAINDER HL-Y" in out  # the odd register's top 4 bits move across
    assert "HL-Y * 16" in out and "FUNCTION MOD(HL-U, 268435456) * 16 + HL-X" in out
    for even, odd, k in [(1, 0xF0000003, 4), (0x7FFFFFFF, 0xFFFFFFFF, 1), (0, 0x80000000, 31)]:
        pair = ((even << 32) | odd) << k & (2**64 - 1)  # POPS: the 64-bit pair shifted left, zeros in
        m = 2 ** (32 - k)
        want_even = (even % m) * 2**k + odd // m
        want_odd = (odd % m) * 2**k
        assert (want_even << 32) | want_odd == pair
    with pytest.raises(hlasm.Refused, match="not an even register"):
        addr("         SLDL  R3,4")


@pytest.mark.parametrize(
    ("code", "why"),
    [
        (("         LA    R3,W_BUF", "         A     R3,W_F"), "instruction A"),
        (("         LA    R3,W_BUF", "         LA    R2,4096(,R3)"), "displacement"),
        (("         LA    R3,W_BUF", "         MVC   0(R3),W_H"), "byte of W_H"),
        (("         LA    R3,W_F", "         CLI   0(R3),C'A'"), "binary field"),
        (
            ("         LA    R3,W_BUF", "         CLI   0(R3),C'AB'", "         BC    B'1000',D", "D        DS    0H"),
            "CLI",
        ),
    ],
)
def test_the_address_model_refuses_what_it_cannot_prove(code, why):
    with pytest.raises(hlasm.Refused, match=why):
        addr(*code)


def test_a_line_past_column_72_is_refused_rather_than_truncated():
    name = "W_" + "L" * 28
    with pytest.raises(hlasm.Refused, match="column 72"):
        lower(
            "         LA    R3," + name,
            "         CLI   0(R3),C'A'",
            "         EXEC CICS RETURN",
            data=(f"{name} DS CL4",),
        )
