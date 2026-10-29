"""#5859 slice 6: the independent POPS interpreter and the lowered COBOL (GnuCOBOL, pinned oracle image) leave the same
registers after each subset instruction, over boundary operands (tests/tools/hlasm_diff.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import hlasm_diff as D  # noqa: E402


def test_every_case_lowers_interprets_and_rewrites_to_a_displaying_program():
    cases = D.cases()
    assert len(cases) >= 170
    for name, code in cases.items():
        text = D.lowered(code, name)
        assert text is not None and "STOP RUN." in text and "RETURN END-EXEC" not in text, name
        assert D.interpret(code, name), name


def test_the_cases_cover_each_instruction_family():
    names = " ".join(D.cases())
    for family in (
        "la-",
        "sll-",
        "sldl-",
        "sr-",
        "bct-",
        "sth-",
        "ch-",
        "mvc-",
        "xc-",
        "oc-",
        "clc-",
        "cli-",
        "stcm-",
        "ic-",
        "tr-",
        "bas-",
        "bcr-",
        "bc-mask-",
        "stl-",
    ):
        assert family in names


def test_the_byte_cases_observe_every_byte_of_their_fields():
    for name in D.BYTES:
        keys = [k for k in D.interpret(D.cases()[name], name) if "[" in k]
        assert len(keys) == 8 * len(D.BYTES[name]), name
    assert set(D.cases()) >= D.RAW


def test_a_high_or_low_branch_after_clc_or_cli_is_refused_by_name():
    """EBCDIC collating is not ASCII's, so the lowering refuses what the differential could not compare."""
    for op, operands in (("CLC", "W_B,W_C"), ("CLI", "W_B,X'40'")):
        for mask in (4, 2):
            code = [
                "         XC    W_B,W_B",
                f"         {op}   {operands}",
                f"         BC    {mask},T",
                "T        DS    0H",
            ]
            with pytest.raises(D.hlasm.Refused, match="high / low"):
                D.lowered(code)


def test_the_bytes_of_a_stored_fullword_are_not_observable():
    """The lowering holds F as COMP-5, so a byte access would see the other byte order: each is refused by name."""
    store = ["         LA    R2,1", "         ST    R2,W_F"]
    for line in (
        "         MVC   W_C(4),W_F",
        "         STCM  R2,15,W_F",
        "         IC    R3,W_F",
        "         MVC   W_F,W_B",
    ):
        with pytest.raises(D.hlasm.Refused, match="binary fields|byte of W_F"):
            D.lowered([*store, line])
    clc = [*store, "         CLC   W_B(4),W_F", "         BC    8,T", "T        DS    0H"]
    with pytest.raises(D.hlasm.Refused, match="CLC"):
        D.lowered(clc)


def test_a_conditional_bcr_is_refused_by_name():
    code = ["         LA    R5,1", "         BAS   R14,SUB", "         B     DONE", "SUB      DS    0H",
            "         BCR   8,R14", "DONE     DS    0H"]  # fmt: skip
    with pytest.raises(D.hlasm.Refused, match="conditional BCR"):
        D.lowered(code)


@pytest.mark.slow(reason="one cobc container compiles and runs ~180 lowered snippets (about 12 s locally)")
@pytest.mark.skipif(D.available() is not None, reason=D.available() or "")
def test_interpreter_and_lowered_cobol_agree_per_instruction():
    assert D.differences() == []
