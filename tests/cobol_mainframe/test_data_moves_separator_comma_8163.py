"""#8163: a separator comma between an operand and the keyword after it (`MOVE A, TO B`, `WRITE R, FROM X`,
`ACCEPT X, FROM DATE`) dropped the whole statement from data_moves (example-health-apis HCIMDB01:243)."""

import pytest

from gitgalaxy.core.data_moves import data_moves

HEAD = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  A PIC X.\n       01  B PIC X.\n       01  C PIC X.\n"
    "       PROCEDURE DIVISION.\n"
)


def _rows(body: str) -> list:
    return [(m["verb"], m["source"], m["target"]) for m in data_moves(HEAD + body)]


@pytest.mark.parametrize("sep", [" ", ", ", ",\n                  "])
def test_move_with_or_without_a_comma_before_to(sep):
    rows = _rows(f"           MOVE A{sep}TO B C.\n" if "," not in sep else f"           MOVE A{sep}TO B, C.\n")
    assert ("MOVE", "A", "B") in rows and ("MOVE", "A", "C") in rows


def test_move_qualified_subscripted_target_after_comma():
    rows = _rows("           MOVE A, TO B OF C (1)\n           MOVE A TO B.\n")
    assert len([r for r in rows if r[0] == "MOVE"]) == 2


def test_write_and_accept_with_comma():
    rows = _rows("           WRITE B, FROM A.\n           ACCEPT B, FROM DATE.\n")
    assert ("WRITE", "A", "B") in rows
    assert any(r[0] == "ACCEPT" and r[2] == "B" for r in rows)
