"""#5648: the translator reads a source-format directive with core.cobol_source_format.directive_format (one rule for
the scanner and the translator); VARIABLE is refused by name. Our own fixtures only."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402

LONG = "MOVE 1 TO " + "X" * 70 + "."  # 80 columns: cut at 72 in fixed format, whole in free


def _texts(raw: list[str]) -> list[str]:
    return [ln.text for ln in SRC.logical_lines(raw, "P.cbl")]


@pytest.mark.parametrize(
    "to_free",
    ["      >>SOURCE FORMAT FREE", "      >>SOURCE FORMAT IS FREE", "      >>SOURCE FREE", "      >>FORMAT FREE", "       >>SOURCE FORMAT FREE",
     'ABC123 >>SOURCE FORMAT FREE', '      $SET SOURCEFORMAT"FREE"'],
)  # fmt: skip
def test_every_spelling_switches_to_free_and_back(to_free):
    got = _texts(["       MOVE A TO B.", to_free, LONG, "      >>SOURCE FORMAT FIXED", "       MOVE C TO D."])
    assert got == ["MOVE A TO B.", LONG, "MOVE C TO D."]


def test_fixed_format_still_cuts_at_column_72():
    assert _texts(["       " + LONG])[0] == LONG[:65]


def test_a_directive_in_a_comment_line_switches_nothing():
    got = _texts(["      *>>SOURCE FORMAT FREE", "       " + LONG])
    assert got == [LONG[:65]]


def test_variable_format_is_refused_by_name():
    with pytest.raises(SRC.SourceFormatRefused, match="VARIABLE"):
        SRC.logical_lines(["      >>SOURCE FORMAT IS VARIABLE", "       MOVE A TO B."], "P.cbl")
