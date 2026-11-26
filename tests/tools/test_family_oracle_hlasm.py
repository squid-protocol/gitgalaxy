"""HLASM keyword-family oracle (#8863): CSECT / macro units read through the translator's assembler statement reader."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import family_oracle as fo  # noqa: E402
import family_oracle_hlasm as fh  # noqa: E402


def _card(label: str, op: str, operands: str = "") -> str:
    return f"{label:<8} {op:<5} {operands}".rstrip() + "\n"


def _unit(body: str, name: str = "PROG"):
    src = _card(name, "CSECT") + "".join(
        _card("", *(ln.split(None, 1) if " " in ln.strip() else [ln.strip()])) for ln in body.strip().splitlines()
    )
    oracle = fh.get_oracle()
    index = oracle.index(src + _card("", "END"))
    stmts = next((v for (nm, _ln), v in index.items() if nm == name), None)
    assert stmts is not None, "the section was not indexed"
    return oracle.count(stmts)[0]


def test_conditional_branches_count_and_calls_jumps_returns_do_not():
    n = _unit(
        "BE L1\nBNZR 14\nJNE L2\nBC 8,L3\nBCR 7,14\nBAS 14,SUB\nB L4\nBR 14\nBALR 14,15\nBC 15,L5\nBCR 15,14\nBC 0,L6"
    )
    assert n["branch"] == 5


def test_a_symbolic_mask_is_a_real_test():
    assert _unit("BC MASK,L1")["branch"] == 1


def test_counting_and_index_loops_and_compare_and_branch():
    n = _unit("BCT 5,LOOP\nBXLE 1,2,LOOP\nCIJ 5,0,8,L1\nCLRJ 1,2,6,L2\nBRCT 4,L3")
    assert n["branch"] == 5


def test_bctr_with_register_zero_is_a_decrement_not_a_branch():
    assert _unit("BCTR 5,0")["branch"] == 0
    assert _unit("BCTR 5,6")["branch"] == 1


def test_io_cics_sql_dli_call_and_access_methods_and_close_is_not_io():
    n = _unit(
        "EXEC CICS READ FILE('F') INTO(A)\n"
        "EXEC CICS WRITEQ TS QUEUE('Q') FROM(A)\n"
        "EXEC SQL SELECT A INTO :B FROM T\n"
        "EXEC DLI GU SEGMENT(X)\n"
        "CALL ASMTDLI,(GU,PCB)\n"
        "OPEN (INFILE,INPUT)\n"
        "GET INFILE,REC\n"
        "PUT OUTFILE,REC\n"
        "CLOSE (INFILE)"
    )
    assert n["io"] == 8


def test_exec_sql_include_declare_whenever_and_other_cics_are_not_io():
    n = _unit(
        "EXEC SQL INCLUDE SQLCA\nEXEC SQL DECLARE C1 CURSOR FOR SELECT 1\nEXEC SQL WHENEVER NOT FOUND GO TO X\n"
        "EXEC CICS LINK PROGRAM('P')\nEXEC CICS RETURN"
    )
    assert n["io"] == 0


def test_print_cast_and_bailout():
    n = _unit(
        "WTO 'HI'\nWTOR 'Q',R,8,ECB\nCVB 1,D\nCVD 1,D\nPACK D,Z\nUNPK Z,D\nABEND 1\nEXEC CICS ABEND ABCODE('ABCD')"
    )
    assert (n["print"], n["cast"], n["bailout"]) == (2, 4, 2)


def test_a_macro_prototype_is_a_unit_and_a_section_inside_it_is_not():
    src = (
        "         MACRO\n"
        "&L       MYMAC &P\n"
        "         BE    DONE\n"
        "         MEND\n" + _card("PROG", "CSECT") + _card("", "BNE", "X") + _card("", "END")
    )
    index = fh.get_oracle().index(src)
    names = {nm for nm, _ in index}
    assert names == {"MYMAC", "PROG"}
    assert index[("MYMAC", 1)] is index[("MYMAC", 2)]  # the MACRO card and the prototype line reach the same unit
    assert fh.get_oracle().count(index[("MYMAC", 2)])[0]["branch"] == 1
    assert fh.get_oracle().count(index[("PROG", 5)])[0]["branch"] == 1


def test_comments_and_statements_before_the_first_section_are_not_counted():
    src = "* BE comment\n" + _card("", "BE", "X") + _card("PROG", "CSECT") + "* BNE\n" + _card("", "END")
    index = fh.get_oracle().index(src)
    assert fh.get_oracle().count(index[("PROG", 3)])[0].get("branch", 0) == 0


def test_a_refused_source_indexes_to_nothing():
    bad = _card("PROG", "CSECT") + "   garbage text here".ljust(71) + "X\nTEXT IN COL 5 CONTINUES\n"
    assert fh.get_oracle().index(bad) == {}


def test_dispatch_families_and_sweep_registration():
    import family_oracle_sweep as sweep

    assert fo.get_oracle("hlasm") is fh.get_oracle()
    assert [f.column for f in fh.FAMILIES] == [
        "struct_branch",
        "arch_io",
        "state_print_hits",
        "state_cast_hits",
        "state_bailout_hits",
    ]
    assert all(f.rule for f in fh.FAMILIES)
    assert "hlasm" in sweep.languages()
