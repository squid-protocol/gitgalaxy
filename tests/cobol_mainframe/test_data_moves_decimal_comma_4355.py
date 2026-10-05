"""#4355: under DECIMAL-POINT IS COMMA a numeric literal is written `0,5`. data_moves tokenized it
as `0` `,` `5`, so `MOVE 0,5 TO T-WERT (2)` drew no row (estate-crucible ZINSBER.cbl:26, H-0043).
The literal is one token in such a program; a separator comma (followed by a space) still separates,
and a program without the clause is read as before."""

from gitgalaxy.core.data_moves import data_moves

HEAD = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. ZINSBER.\n       ENVIRONMENT DIVISION.\n"
    "       CONFIGURATION SECTION.\n       SPECIAL-NAMES.\n           DECIMAL-POINT IS COMMA.\n"
    "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01  T-WERT PIC 9V9 OCCURS 3.\n"
    "       01  A PIC 9V99.\n       01  B PIC 9V99.\n       PROCEDURE DIVISION.\n"
)
BODY = "           MOVE 0,5 TO T-WERT (2)\n           MOVE 1,25 TO A, B\n           MOVE A TO B.\n"


def _rows(src: str) -> list:
    return [(m["verb"], m["source"], m["source_kind"], m["target"]) for m in data_moves(src)]


def test_a_decimal_comma_literal_is_one_source():
    rows = _rows(HEAD + BODY)
    assert rows[0][:3] == ("MOVE", "0,5", "literal") and rows[0][3].startswith("T-WERT")
    # `, ` after the literal is a separator: both targets still get the move
    assert [r[3] for r in rows if r[1] == "1,25"] == ["A", "B"]
    assert ("MOVE", "A", "item", "B") in rows


def test_without_the_clause_a_comma_still_separates():
    plain = HEAD.replace("           DECIMAL-POINT IS COMMA.\n", "")
    assert not any(r[1] in ("0,5", "1,25") for r in _rows(plain + BODY))
