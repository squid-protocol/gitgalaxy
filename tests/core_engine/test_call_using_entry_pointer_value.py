"""`SET routine TO ENTRY 'X'` is a procedure-pointer assignment, not an ENTRY statement.

dbb-mortgage-application epscsmrd.cbl (lines 304, 2991, 3525) carries `SET ROUTINE TO ENTRY 'EPSCSMRF'`. The engine's
call_using reader and the answer key's own reader both took each for an `ENTRY 'X'` entry point, so they agreed with each
other and the ledger stayed quiet; the blind reviewers did not list them (round 2 of the COBOL review)."""

from gitgalaxy.core.call_using import entry_points


def _rows(src: str) -> list[tuple[str, str | None, int]]:
    return [(r["kind"], r["entry_name"], r["line"]) for r in entry_points(src)]


def test_set_to_entry_is_not_an_entry_statement():
    src = "\n".join(
        [
            "       PROCEDURE DIVISION.",
            "       MAIN-PARA.",
            "           SET ROUTINE TO ENTRY 'EPSCSMRF'",
            "           SET TOKEN TO ADDRESS OF ERROR-RESPONSE",
            "           GOBACK.",
        ]
    )
    assert _rows(src) == [("PROCEDURE", None, 1)]


def test_a_real_entry_statement_is_still_an_entry_point():
    src = "\n".join(
        [
            "       PROCEDURE DIVISION.",
            "           GOBACK.",
            "       ENTRY 'REAL' USING A B.",
            "           GOBACK.",
        ]
    )
    assert _rows(src) == [("PROCEDURE", None, 1), ("ENTRY", "REAL", 3)]


def test_the_pointer_form_split_over_two_lines_is_also_not_an_entry():
    src = "\n".join(
        [
            "       PROCEDURE DIVISION.",
            "           SET ROUTINE-PTR",
            "            TO ENTRY 'EPSCSMRE'",
            "           GOBACK.",
        ]
    )
    assert _rows(src) == [("PROCEDURE", None, 1)]
