"""#5648: the fixed-form row wrapper lives in core.cobol_source_format; the translator holds no copy."""

from __future__ import annotations

import inspect

import pytest

from gitgalaxy.core.cobol_source_format import (
    CONTINUATION_LEAD,
    FIXED_LEAD,
    TEXT_END,
    TEXT_WIDTH,
    join_wrapped,
    wrap_fixed,
)


def test_constants_are_columns_8_to_72():
    assert TEXT_END - len(FIXED_LEAD) == TEXT_WIDTH
    assert len(CONTINUATION_LEAD) == 9


@pytest.mark.parametrize(
    "text",
    [
        "MOVE A TO B " * 12,
        "DISPLAY '" + "X" * 100 + "'",  # a literal running past column 72
        'DISPLAY "' + "Q" * 56 + '""' + "Z" * 30 + '"',  # a doubled quote at column 72
        "A" * 150,  # no space to split at
    ],
)
def test_no_row_passes_column_72_and_a_continued_literal_joins_again(text):
    rows = wrap_fixed(text)
    assert all(len(r) <= TEXT_END for r in rows)
    assert len(rows) > 1
    assert rows[0].startswith(FIXED_LEAD)
    assert all(r.startswith("      -") or r.startswith(FIXED_LEAD) for r in rows[1:])
    joined = join_wrapped("\n".join(rows))
    assert "\n      -" not in joined


def test_literal_continuation_resumes_with_the_quote():
    rows = wrap_fixed("DISPLAY '" + "X" * 100 + "'")
    assert rows[1].startswith(CONTINUATION_LEAD + "'")


def test_translator_holds_no_copy():
    from gitgalaxy.tools.cobol_to_java.det import source

    assert not hasattr(source, "_wrap")
    assert not hasattr(source, "_CONTINUED")
    assert "def wrap_fixed" not in inspect.getsource(source)
