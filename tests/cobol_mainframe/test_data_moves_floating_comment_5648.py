"""#5648: data_moves cut a line at the first `*>`, so a literal that holds `*>` lost the rest of its line (the
MOVE's target). It reads the comment through core.cobol_preprocessor.free_code, as the translator does."""

from gitgalaxy.core.data_moves import data_moves

SRC = """\
       PROCEDURE DIVISION.
           MOVE '*>' TO WS-A
           MOVE "a *> b" TO WS-B *> MOVE 'x' TO WS-NOT
           MOVE 1 TO WS-D *> a real comment
           MOVE 2 TO WS-E.
"""


def test_a_literal_holding_the_comment_marker_is_not_a_comment():
    assert [(m["source"], m["target"]) for m in data_moves(SRC)] == [
        ("'*>'", "WS-A"),
        ('"a *> b"', "WS-B"),
        ("1", "WS-D"),
        ("2", "WS-E"),
    ]
