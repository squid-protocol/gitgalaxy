"""#4403: a MOVE's receiver list ended only at a COBOL verb or a period, so a following statement
that is not standard COBOL (IDMS DML `OBTAIN CALC LOAN`, estate-crucible H-0007) was read as extra
receivers. A known extension keyword now ends the list."""

import pytest

from gitgalaxy.core.data_moves import data_moves

HEAD = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  A PIC X.\n       01  LOAN-ID PIC X.\n"
    "       PROCEDURE DIVISION.\n"
)


def _targets(body: str) -> list:
    return [m["target"] for m in data_moves(HEAD + body)]


@pytest.mark.parametrize(
    "stmt",
    ["OBTAIN CALC LOAN", "FIND OWNER WITHIN SET", "GET", "STORE REC", "MODIFY REC", "ERASE REC", "CONNECT REC TO S",
     "DISCONNECT REC FROM S", "BIND RUN-UNIT", "READY AREA1", "FINISH", "COMMIT", "ROLLBACK",
     "EXHIBIT NAMED X"],
)  # fmt: skip
def test_extension_statement_ends_the_receiver_list(stmt):
    assert _targets(f"           MOVE A TO LOAN-ID\n           {stmt}\n           IF X DISPLAY 'Y'.\n") == ["LOAN-ID"]


def test_receivers_before_the_keyword_are_kept():
    assert _targets("           MOVE A TO LOAN-ID, A OBTAIN CALC LOAN.\n") == ["LOAN-ID", "A"]


def test_hyphenated_names_are_receivers():
    assert _targets("           MOVE A TO OBTAIN-FLAG FIND-KEY GET-IT.\n") == ["OBTAIN-FLAG", "FIND-KEY", "GET-IT"]


def test_qualified_and_subscripted_receivers():
    t = _targets("           MOVE A TO LOAN-ID OF REC (1) A(2:3)\n           OBTAIN CALC LOAN.\n")
    assert t == ["LOAN-ID OF REC", "A"]


def test_period_terminated_move_unchanged():
    assert _targets("           MOVE A TO LOAN-ID A.\n           OBTAIN CALC LOAN.\n") == ["LOAN-ID", "A"]
