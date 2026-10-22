"""#5648: a doubled quote inside a literal (`'it''s'`) ended the token early, so the MOVE drew no row. The class:
doubled apostrophe, doubled double-quote, and the hexadecimal / national / DBCS / boolean prefixed forms."""

import pytest

from gitgalaxy.core.data_moves import data_moves


def _pairs(body: str) -> list[tuple[str, str]]:
    src = "       PROCEDURE DIVISION.\n" + "".join(f"           {line}\n" for line in body.splitlines())
    return [(m["source"], m["target"]) for m in data_moves(src)]


@pytest.mark.parametrize(
    "literal",
    [
        "'it''s'",
        '"say ""hi"""',
        "''''",
        '""""',
        "'a''''b'",
        "X'C1C2'",
        "x'00'",
        "N'ab'",
        'N"ab"',
        "G'ab'",
        "Z'ab'",
        "NX'4142'",
        "BX'41'",
        "GX'4142'",
        "B'1010'",
        "N'it''s'",
        '"it\'s"',
        "'say \"hi\"'",
    ],
)
def test_every_quote_form_is_one_literal_source(literal):
    assert _pairs(f"MOVE {literal} TO WS-A.") == [(literal, "WS-A")]


def test_a_doubled_quote_does_not_swallow_the_next_statement():
    assert _pairs("MOVE 'it''s' TO WS-A\nMOVE 2 TO WS-B.") == [("'it''s'", "WS-A"), ("2", "WS-B")]


def test_all_with_a_doubled_quote_literal():
    assert _pairs("MOVE ALL 'a''b' TO WS-A.") == [("ALL 'a''b'", "WS-A")]


def test_a_word_that_starts_like_a_prefix_stays_a_name():
    assert _pairs("MOVE XB TO WS-A\nMOVE BX-1 TO WS-B.") == [("XB", "WS-A"), ("BX-1", "WS-B")]
