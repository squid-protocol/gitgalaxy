# ruff: noqa: S101
"""#8863: the COBOL oracle (family_oracle_cobol.py) reads each paragraph through the translator's statement parser.

Each case is one paragraph; the counts pin the readings written in the oracle's docstring (a bare PERFORM is a call, an OTHER arm is a branch, CLOSE is
cleanup's, an exception phrase is a handler). The scored numbers on a real estate are in tests/family_validity_baseline.json.
"""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parents[1]))
sys.path.insert(0, str(TOOLS))

pytest.importorskip("tree_sitter_language_pack", reason="the translator extra is not installed")
import family_oracle as fo  # noqa: E402
import family_oracle_cobol as co  # noqa: E402

HEAD = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  A PIC 9(4).
       01  B PIC 9(4).
       01  I PIC 9(4).
       01  F-STATUS PIC XX.
       PROCEDURE DIVISION.
"""


def _paragraph(body: str, name: str = "P1"):
    src = HEAD + f"       {name}.\n" + "".join(f"           {ln}\n" for ln in body.strip().splitlines()) + "           STOP RUN.\n"
    oracle = co.get_oracle()
    index = oracle.index(src)
    para = next((p for (nm, _ln), p in index.items() if nm == name), None)
    assert para is not None, "the paragraph was not indexed"
    return oracle.count(para)[0]


def test_if_and_evaluate_arms_are_branches_other_included():
    n = _paragraph(
        """
IF A > 1
    MOVE 1 TO B
ELSE
    MOVE 2 TO B
END-IF
EVALUATE A
    WHEN 1 MOVE 1 TO B
    WHEN 2 MOVE 2 TO B
    WHEN OTHER MOVE 3 TO B
END-EVALUATE
"""
    )
    assert n["branch"] == 4


def test_a_bare_perform_is_a_call_a_loop_is_a_branch():
    n = _paragraph(
        """
PERFORM P2
PERFORM UNTIL A > 3
    ADD 1 TO A
END-PERFORM
"""
    )
    assert n["branch"] == 1


def test_and_or_are_counted_as_short_circuit():
    n = _paragraph(
        """
IF A > 1 AND B > 1 OR I = 0
    MOVE 1 TO B
END-IF
"""
    )
    assert n["short_circuit"] == 2 and n["branch"] == 1


def test_display_is_a_print():
    assert _paragraph("DISPLAY 'HELLO'\nDISPLAY A")["print"] == 2


def test_file_verbs_are_io_and_close_is_not():
    n = _paragraph(
        """
OPEN INPUT INFILE
READ INFILE
CLOSE INFILE
"""
    )
    assert n["io"] == 2


def test_an_exception_phrase_is_not_a_branch():
    n = _paragraph(
        """
READ INFILE
    AT END MOVE 1 TO A
END-READ
"""
    )
    assert n["io"] == 1 and n["branch"] == 0


def test_the_index_is_keyed_by_name_and_line_and_a_refusal_is_empty():
    oracle = co.get_oracle()
    index = oracle.index(HEAD + "       P1.\n           STOP RUN.\n")
    assert any(nm == "P1" for nm, _ in index)
    assert oracle.index("this is not cobol at all") == {}


def test_the_dispatch_and_families():
    oracle = fo.get_oracle("cobol")
    assert oracle is co.get_oracle()
    assert [f.rule for f in oracle.families] == ["branch", "debug_prints", "io"]
