"""LENGTH OF a subscripted table element is the length of ONE element, not of the table (#5076).

IBM Enterprise COBOL 6.4 Language Reference (SC27-8713-03), "LENGTH special register" / LENGTH OF: "the length of the
data item referenced": a subscripted reference names one occurrence. zECS's ECS001 loops `PERFORM VARYING I FROM LENGTH
OF TERM-LINES(1) BY -1` over a 24 x 80 screen: 80, where the det port read 1920 and walked off the end of its
byte[1920]. Both spellings (the PERFORM's VARYING and an arithmetic use) go through the same two generators, and an
unsubscripted table (an item with OCCURS, named whole) keeps its whole length.

The codegen tests need no Docker (a translation only)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA = [
    "01 SCREEN.",
    "   05 LINES OCCURS 24 TIMES PIC X(80).",
    "01 WIDE.",
    "   05 CELLS OCCURS 6 TIMES.",
    "      10 CELL-A PIC X(3).",
    "      10 CELL-B PIC 9(2).",
    "01 N PIC 9(6).",
    "01 I PIC 9(4) COMP.",
]


def _translate(tmp_path: Path, proc: list[str]) -> str:
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. LENOF.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", *(f"       {x}" for x in DATA), "       PROCEDURE DIVISION.",
           *(f"           {x}" for x in proc), "           GOBACK."]  # fmt: skip
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "lenof.cbl").write_text("\n".join(src) + "\n")
    project = tmp_path / "project"
    project.mkdir()
    r = P.translate(tmp_path / "lenof.cbl", [], "public class LenofService {\n}\n", "p", None, project)
    assert not r.stats["holes"], r.stats["holes"]
    return r.java


@pytest.mark.parametrize(
    ("stmt", "length"),
    [
        ("MOVE LENGTH OF LINES(1) TO N", 80),  # one screen line, not 24 of them
        ("MOVE LENGTH OF LINES(24) TO N", 80),
        ("MOVE LENGTH OF CELLS(2) TO N", 5),  # a group element: its two items
        ("MOVE LENGTH OF CELL-A(3) TO N", 3),
        ("MOVE LENGTH OF CELL-B(6) TO N", 2),
    ],
)
def test_subscripted_element_is_one_occurrence(tmp_path, stmt, length):
    java = _translate(tmp_path, [stmt])
    assert f"BigDecimal.valueOf({length})" in java, java


@pytest.mark.parametrize(
    ("stmt", "length"),
    [
        ("MOVE LENGTH OF SCREEN TO N", 1920),  # the group: every line
        ("MOVE LENGTH OF WIDE TO N", 30),
    ],
)
def test_group_name_is_the_whole_table(tmp_path, stmt, length):
    java = _translate(tmp_path, [stmt])
    assert f"BigDecimal.valueOf({length})" in java, java


def test_perform_varying_from_length_of_element(tmp_path):
    # the ECS001 shape: the start of a backward scan is one line's length
    java = _translate(tmp_path, ["PERFORM VARYING I FROM LENGTH OF LINES(1) BY -1 UNTIL I < 1", "   CONTINUE",
                                 "END-PERFORM"])  # fmt: skip
    assert "BigDecimal.valueOf(80)" in java, java
    assert "BigDecimal.valueOf(1920)" not in java, java
