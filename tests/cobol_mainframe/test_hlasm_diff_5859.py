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
    assert len(cases) >= 60
    for name, code in cases.items():
        text = D.lowered(code)
        assert text is not None and "STOP RUN." in text and "RETURN END-EXEC" not in text, name
        assert D.interpret(code), name


def test_the_cases_cover_each_instruction_family():
    names = " ".join(D.cases())
    for family in ("la-", "sll-", "sldl-", "sr-", "bct-", "sth-", "ch-"):
        assert family in names


@pytest.mark.skipif(D.available() is not None, reason=D.available() or "")
def test_interpreter_and_lowered_cobol_agree_per_instruction():
    assert D.differences() == []
