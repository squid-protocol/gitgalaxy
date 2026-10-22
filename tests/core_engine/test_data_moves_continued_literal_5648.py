"""#5648: a fixed-format continued line (`-` in column 7) was read as a minus sign, so a MOVE whose literal (or
operands) ran onto a continuation line drew no row. The class: a literal split at column 72, a doubled quote and
a `*>` inside the continued part, a chain of continuations, a comment line between, a non-literal continuation,
the line numbers after it, and the other reader of the same text (relation_facts). Free format has no indicator."""

import pytest

from gitgalaxy.core.data_moves import data_moves
from gitgalaxy.core.relation_facts import relation_facts

_HEAD = "       PROCEDURE DIVISION."


def _fixed(code: str) -> str:
    return " " * 7 + code


def _first(text: str) -> str:
    """A fixed-format line filled to column 72 (a literal opened on it runs to the margin)."""
    return _fixed(text).ljust(72)


def _program(*lines: str) -> str:
    return "\n".join([_HEAD, *lines]) + "\n"


def _cont(text: str) -> str:
    return "      -    " + text


def _pairs(src: str) -> list[tuple[str, str, int]]:
    return [(m["source"], m["target"], m["line"]) for m in data_moves(src)]


def test_literal_continued_onto_next_line_is_one_source():
    src = _program(_first("MOVE 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"), _cont("'BBB' TO WS-X."))
    assert _pairs(src) == [("'" + "A" * 59 + "BBB'", "WS-X", 2)]


def test_short_first_line_pads_the_literal_to_column_72():
    # the first line stops before column 72: its trailing blanks are part of the literal (IBM LR, Continuation)
    src = _program(_fixed("MOVE 'AB"), _cont("'CD' TO WS-X."))
    ((source, target, _),) = _pairs(src)
    assert source == "'AB" + " " * (72 - 7 - len("MOVE 'AB")) + "CD'"
    assert target == "WS-X"


def test_doubled_quote_in_the_continued_part():
    src = _program(
        _first("MOVE 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"), _cont("'B''C' TO WS-X.")
    )
    assert [(s, t) for s, t, _ in _pairs(src)] == [("'" + "A" * 59 + "B''C'", "WS-X")]


def test_comment_marker_and_period_inside_the_continued_literal_do_not_end_the_statement():
    src = _program(
        _first("MOVE 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
        _cont("'B*>C. MOVE 1 TO WS-Z' TO WS-X."),
    )
    assert [(s, t) for s, t, _ in _pairs(src)] == [("'" + "A" * 59 + "B*>C. MOVE 1 TO WS-Z'", "WS-X")]


def test_literal_continued_twice_and_a_comment_line_between():
    src = _program(
        _first("MOVE 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
        "      *    a comment between the lines",
        _cont("'" + "B" * 60).ljust(72),
        _cont("'CC' TO WS-X."),
    )
    ((source, target, line),) = _pairs(src)
    assert source == "'" + "A" * 59 + "B" * 60 + "CC'"
    assert (target, line) == ("WS-X", 2)


def test_non_literal_continuation_joins_after_a_space():
    src = _program(_first("MOVE WS-A"), _cont("TO WS-X."))
    assert [(s, t) for s, t, _ in _pairs(src)] == [("WS-A", "WS-X")]


def test_target_list_continued():
    src = _program(_first("MOVE 1 TO WS-X"), _cont("WS-Y."))
    assert [(s, t) for s, t, _ in _pairs(src)] == [("1", "WS-X"), ("1", "WS-Y")]


def test_lines_after_the_continuation_keep_their_numbers():
    src = _program(
        _first("MOVE 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
        _cont("'B' TO WS-X."),
        _fixed("MOVE 1 TO WS-Y."),
    )
    assert [(t, line) for _, t, line in _pairs(src)] == [("WS-X", 2), ("WS-Y", 4)]


def test_free_format_dash_in_column_7_is_not_a_continuation():
    src = ">>SOURCE FORMAT FREE\nPROCEDURE DIVISION.\nMOVE 'A' TO WS-X\n- 1 TO WS-Y.\n"
    assert [(s, t) for s, t, _ in _pairs(src)] == [("'A'", "WS-X")]


@pytest.mark.parametrize("prefix", ["", "X", "N", "NX"])
def test_prefixed_literal_continued(prefix):
    src = _program(_first(f"MOVE {prefix}'" + "A" * (59 - len(prefix))), _cont("'BB' TO WS-X."))
    ((source, _, _),) = _pairs(src)
    assert source == prefix + "'" + "A" * (59 - len(prefix)) + "BB'"


def test_relation_condition_with_a_continued_literal():
    src = _program(
        _first("IF WS-X = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"), _cont("'BBB' DISPLAY 'Q' END-IF.")
    )
    (row,) = relation_facts(src)
    assert row["right"] == "'" + "A" * 54 + "BBB'"
    assert row["right_class"] == "alphanumeric"
