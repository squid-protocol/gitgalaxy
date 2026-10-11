"""#4874: a floating `*>` comment in fixed-format source is a comment (IBM Enterprise COBOL 6, GnuCOBOL -std=ibm), also
inside a condition; inside a literal it is data. The det translator reads the program as if the comment were not there."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402

HEAD = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        "01 A PIC X.", "01 D0 PIC 9(3).", "PROCEDURE DIVISION.", "P1."]  # fmt: skip


def _fixed(lines: list[str]) -> list[str]:
    return ["       " + t for t in lines]


def _proc(body: list[str]):
    return S.parse(SRC.logical_lines(_fixed(HEAD + body), "t.cbl"))


def _kinds(proc):
    return [s.kind for p in proc.paragraphs for s in S.walk(p.body)]


def _cond_ok(stmt):
    c = stmt.data["cond"]
    assert not (isinstance(c, tuple) and c[0] == "UNPARSED"), c


@pytest.mark.parametrize(
    "cond",
    [
        ["IF D0 < 3 *> hi"],
        ["IF D0 NOT < 3 *> hi"],
        ["IF D0 NOT *> c", "    < 3"],
        ["IF D0 NOT", "    < 3 *> c"],
        ["IF D0 NOT *> don't", "    LESS *> it's", "    THAN 3"],
        ["IF D0 > 1 AND *> c", "    D0 < 9"],
        ["IF D0 > 1 AND *> c", "    < 9"],
        ["IF D0 > 1 OR *> c", "    NOT *> d", "    < 2"],
        ["IF D0 > 1 AND NOT *> c", "    = 5"],
        ["IF D0 > 1 *> a", "    AND D0 < 9 *> b"],
        ["IF D0 = 1 *> a *> b"],
    ],
)
def test_a_floating_comment_inside_a_condition_is_ignored(cond):
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc([f"    {cond[0]}", *[f"    {x}" for x in cond[1:]], "        DISPLAY 'Y' *> shown",
                  "    END-IF.", "    GOBACK."])  # fmt: skip
    stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
    assert [s.kind for s in stmts] == ["IF", "DISPLAY", "GOBACK"], cond
    _cond_ok(stmts[0])


def test_a_floating_comment_in_evaluate_when_and_perform_until_is_ignored():
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc([
        "    EVALUATE TRUE *> e",
        "        WHEN D0 NOT *> c",
        "            < 3 *> d",
        "            DISPLAY 'Y'",
        "        WHEN OTHER *> o",
        "            DISPLAY 'N'",
        "    END-EVALUATE",
        "    PERFORM UNTIL D0 NOT *> c",
        "        < 9 *> d",
        "        ADD 1 TO D0 *> a",
        "    END-PERFORM.",
        "    GOBACK.",
    ])  # fmt: skip
    assert _kinds(proc) == ["EVALUATE", "DISPLAY", "DISPLAY", "PERFORM", "ARITH", "GOBACK"]


def test_a_comment_after_a_statement_and_a_comment_only_line_are_ignored():
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc(["    MOVE 'X' TO A *> note", "    *> a line of its own", "    GOBACK."])
    assert _kinds(proc) == ["MOVE", "GOBACK"]


def test_comment_indicator_inside_a_literal_is_kept():
    lines = SRC.logical_lines(
        _fixed(["MOVE 'a *> b' TO A *> c", 'DISPLAY "x*>y" *> z', "DISPLAY 'it''s *>' *> q"]), "t"
    )
    assert [ln.text.strip() for ln in lines] == ["MOVE 'a *> b' TO A", 'DISPLAY "x*>y"', "DISPLAY 'it''s *>'"]


def test_a_literal_holding_the_indicator_translates_with_its_content():
    pytest.importorskip("tree_sitter_language_pack")
    proc = _proc(["    IF A = '*>' *> real comment", "        DISPLAY 'a *> b' *> c", "    END-IF.", "    GOBACK."])
    stmts = [s for p in proc.paragraphs for s in S.walk(p.body)]
    assert [s.kind for s in stmts] == ["IF", "DISPLAY", "GOBACK"]
    assert "*>" in repr(stmts[0].data["cond"]) and "*>" in repr(stmts[1].data)


def test_a_continued_literal_keeps_its_indicator_and_loses_a_comment_after_it():
    pad = "X" * 56
    raw = _fixed([f"DISPLAY '{pad}*> "])
    raw[0] = raw[0][:72].ljust(72)
    raw.append("      -    \"tail *> more' *> gone".replace('"', "'"))
    lines = SRC.logical_lines(raw, "t")
    assert len(lines) == 1 and "*> more'" in lines[0].text and "gone" not in lines[0].text
