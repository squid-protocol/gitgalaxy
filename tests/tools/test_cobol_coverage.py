"""#4023: COBOL paragraph and branch coverage from a GnuCOBOL -ftraceall trace (tests/tools/cobol_coverage.py)."""

from __future__ import annotations

from pathlib import Path

import cobol_coverage as cov


def _cbl(*lines: str) -> str:
    """Fixed format: each line after a blank sequence area and indicator (column 8 on)."""
    return "\n".join(("       " + x) if x else "" for x in lines) + "\n"


# Area A (a unit header) is column 8; Area B statements are indented four more.
PROGRAM = _cbl(
    "IDENTIFICATION DIVISION.",  # 1
    "PROGRAM-ID. T.",  # 2
    "DATA DIVISION.",  # 3
    "WORKING-STORAGE SECTION.",  # 4
    "01 X PIC 9 VALUE 1.",  # 5
    "PROCEDURE DIVISION.",  # 6
    "MAIN-SECTION SECTION.",  # 7
    "P1.",  # 8
    "    IF X = 1",  # 9
    "       CONTINUE",  # 10
    "    ELSE",  # 11
    "       DISPLAY 'NO'",  # 12
    "    END-IF",  # 13
    "    IF X = 2 DISPLAY 'TWO' END-IF",  # 14
    "    EVALUATE X",  # 15
    "      WHEN 1",  # 16
    "      WHEN 3",  # 17
    "        DISPLAY 'ONE'",  # 18
    "      WHEN OTHER",  # 19
    "        DISPLAY 'OTHER'",  # 20
    "    END-EVALUATE",  # 21
    "    PERFORM P2",  # 22
    "    IF X = 1 NEXT SENTENCE ELSE DISPLAY 'Q'.",  # 23
    "    GO TO P3.",  # 24
    "P2.",  # 25
    "    MOVE 1 TO X.",  # 26
    "P3.",  # 27
    "    STOP RUN.",  # 28
    "P4.",  # 29
    "    DISPLAY 'DEAD'.",  # 30
)

# What GnuCOBOL 3.1.2 wrote for PROGRAM (cobc -std=ibm -ftraceall; COB_SET_TRACE=Y), verbatim.
TRACE = b"""Source: 'T.cbl'
Program-Id:  T
Program-Id:  T                    Entry: T                               Line:      6
Program-Id:  T                  Section: MAIN-SECTION                    Line:      7
Program-Id:  T                Paragraph: P1                              Line:      8
Program-Id:  T                           IF                              Line:      9
Program-Id:  T                           CONTINUE                        Line:     10
Program-Id:  T                           IF                              Line:     14
Program-Id:  T                           EVALUATE                        Line:     15
Program-Id:  T                           DISPLAY                         Line:     18
Program-Id:  T                           PERFORM                         Line:     22
Program-Id:  T                Paragraph: P2                              Line:     25
Program-Id:  T                           MOVE                            Line:     26
Program-Id:  T                           IF                              Line:     23
Program-Id:  T                           NEXT SENTENCE                   Line:     23
Program-Id:  T                Paragraph: L$0                             Line:     23
Program-Id:  T                           GO TO                           Line:     24
Program-Id:  T                Paragraph: P3                              Line:     27
Program-Id:  T                           STOP RUN                        Line:     28
"""


def _measure(tmp_path: Path, text: str = PROGRAM, trace: bytes = TRACE, compiled: str | None = None) -> dict:
    src = tmp_path / "T.cbl"
    src.write_text(text, encoding="ascii")
    (tmp_path / "trace.txt").write_bytes(trace)
    return cov.run_coverage(src, text, compiled, [tmp_path / "trace.txt"], "T.cbl", tmp_path)


def test_branch_points_arms_and_their_first_statements() -> None:
    branches, stmts = cov.branch_points(PROGRAM)
    got = {(b.kind, b.line): ([(a.outcome, a.first) for a in b.arms], b.fallthrough) for b in branches}
    assert got == {
        ("IF", 9): ([("true", (10, "CONTINUE")), ("false", (12, "DISPLAY"))], None),
        ("IF", 14): ([("true", (14, "DISPLAY"))], "false"),
        # WHEN 1 WHEN 3: one arm; no fall-through outcome, there is a WHEN OTHER
        ("EVALUATE", 15): ([("WHEN@16", (18, "DISPLAY")), ("OTHER", (20, "DISPLAY"))], None),
        ("IF", 23): ([("true", (23, "NEXT")), ("false", (23, "DISPLAY"))], None),
    }
    assert stmts[(23, "IF")] == 1


def test_nesting_else_pairing_period_and_exec() -> None:
    text = _cbl(
        "PROCEDURE DIVISION.",  # 1
        "A.",  # 2
        "    IF X IF Y MOVE 1 TO Z ELSE MOVE 2 TO Z",  # 3: the first ELSE is the inner IF's
        "    ELSE",  # 4
        "       EXEC CICS RETURN END-EXEC",  # 5: IF inside EXEC is not a statement of ours
        "    IF W",  # 6
        "       DISPLAY 'W'.",  # 7: the period closes the IF
        "    EVALUATE TRUE WHEN A = 1 CONTINUE END-EVALUATE.",  # 8: no OTHER -> a `none` outcome
    )
    branches, _ = cov.branch_points(text)
    got = {(b.kind, b.line): ([(a.outcome, a.first) for a in b.arms], b.fallthrough) for b in branches}
    inner, outer = [b for b in branches if b.kind == "IF" and b.line == 3]  # the inner one closes first
    assert [(a.outcome, a.first) for a in outer.arms] == [("true", (3, "IF")), ("false", (5, "EXEC"))]
    assert [a.first for a in inner.arms] == [(3, "MOVE"), (3, "MOVE")]
    assert got[("IF", 6)] == ([("true", (7, "DISPLAY"))], "false")
    assert got[("EVALUATE", 8)] == ([("WHEN@8", (8, "CONTINUE"))], "none")


def test_coverage_of_a_run(tmp_path: Path) -> None:
    s = _measure(tmp_path)
    p, b = s["paragraphs"], s["branches"]
    assert (p["covered"], p["live"], p["dead"]) == (4, 4, ["P4"])  # MAIN-SECTION, P1, P2, P3; P4 is unreachable
    assert (b["covered"], b["total"]) == (4, 8)
    assert {(u["line"], u["outcome"]) for u in b["uncovered"]} == {(9, "false"), (14, "true"), (15, "OTHER"),
                                                                   (23, "false")}  # fmt: skip
    assert p["unread"] == [] and p["dead_but_executed"] == []  # L$0 is GnuCOBOL's own, not a unit
    assert cov.claim(s, 3) == "proven on 3 scenarios, covering 4/4 paragraphs and 4/8 branches"
    assert cov.covers(s, 1) == "1 run covers 4/4 paragraphs and 4/8 branches"


def test_a_dead_unit_entered_and_a_unit_the_engine_cannot_read_are_reported(tmp_path: Path) -> None:
    extra = (b"Program-Id:  T                Paragraph: P4                              Line:     29\n"
             b"Program-Id:  T                Paragraph: NOT-A-UNIT                      Line:     30\n")  # fmt: skip
    p = _measure(tmp_path, trace=TRACE + extra)["paragraphs"]
    assert p["dead_but_executed"] == ["P4"]
    assert p["unread"] == ["NOT-A-UNIT"]
    assert p["covered"] == 4  # neither is counted


def test_gnucobol_when_events_are_not_the_arm(tmp_path: Path) -> None:
    """GnuCOBOL traces some WHENs as statements; the arm is the first real statement after them."""
    trace = TRACE.replace(
        b"Program-Id:  T                           DISPLAY                         Line:     18\n",
        b"Program-Id:  T                           WHEN                            Line:     16\n"
        b"Program-Id:  T                           DISPLAY                         Line:     18\n",
    )
    assert _measure(tmp_path, trace=trace)["branches"]["covered"] == 4


def test_a_translated_program_maps_back_to_the_original(tmp_path: Path) -> None:
    """The CICS harness's shape: an EXEC CICS expanded into several lines, a condition rewritten in place."""
    original = _cbl(
        "PROGRAM-ID. T.",  # 1
        "PROCEDURE DIVISION.",  # 2
        "A.",  # 3
        "    EXEC CICS RECEIVE MAP('M') RESP(WS-RESP)",  # 4
        "    END-EXEC",  # 5
        "    IF WS-RESP NOT = DFHRESP(NORMAL) OR NAMEL = 0",  # 6
        "       DISPLAY 'BAD'",  # 7
        "    END-IF",  # 8
        "    GOBACK.",  # 9
    )
    compiled = _cbl(
        "PROGRAM-ID. T.",  # 1
        "PROCEDURE DIVISION.",  # 2
        "A.",  # 3
        "    MOVE 'M' TO GG-MAP",  # 4
        "    CALL 'GGCRECV' USING GG-CICS",  # 5
        "    IF GG-RESP NOT = 0",  # 6: the translator's own IF
        "       MOVE GG-RESP TO WS-RESP",  # 7
        "    END-IF",  # 8
        "    IF WS-RESP NOT = 0 OR NAMEL = 0",  # 9: the original IF, its condition rewritten
        "       DISPLAY 'BAD'",  # 10
        "    END-IF",  # 11
        "    GOBACK.",  # 12
    )
    lines = cov.LineMap(original, compiled)
    assert lines.get(9) == (6, True) and lines.get(10) == (7, True)
    assert lines.get(4) == (4, False)  # the EXEC's expansion stands for the EXEC
    trace = b"".join(
        b"Program-Id:  T                           %-32s Line: %6d\n" % (verb, n)
        for verb, n in [(b"MOVE", 4), (b"CALL", 5), (b"IF", 6), (b"IF", 9), (b"DISPLAY", 10), (b"GOBACK", 12)]
    )
    s = _measure(tmp_path, original, trace, compiled)
    b = s["branches"]
    assert (b["covered"], b["total"]) == (1, 2)  # the translator's IF at 6 is not the program's
    assert b["uncovered"][0]["outcome"] == "false"


def test_a_line_that_cannot_be_told_apart_is_not_counted() -> None:
    inv = cov.inventory(Path("none.cbl"), text=_cbl("PROGRAM-ID. U.", "PROCEDURE DIVISION.", "A.",
                                                    "    IF X MOVE 1 TO Y ELSE MOVE 2 TO Y END-IF",
                                                    "    GOBACK."))  # fmt: skip
    assert inv.branches == [] and inv.unresolvable[0]["line"] == 4


def test_read_trace_names_programs_and_sources() -> None:
    events = cov.read_trace(TRACE)
    assert events[0].kind == "Entry" and events[0].program == "T" and events[0].source == "T.cbl"
    assert [e.name for e in events if e.kind == "stmt"][-2:] == ["GO TO", "STOP RUN"]
