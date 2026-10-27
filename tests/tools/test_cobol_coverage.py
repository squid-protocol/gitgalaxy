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


def test_a_paragraph_holding_an_entry_statement_is_entered_by_it(tmp_path: Path) -> None:
    """IMS enters a DL/I program at ENTRY 'DLITCBL': GnuCOBOL traces `Entry: DLITCBL` and then the statements, with no
    Paragraph event for the unit that holds the ENTRY. That unit was entered; a program's own entry (named like its PROGRAM-ID) names no unit."""
    text = _cbl("PROGRAM-ID. T.", "PROCEDURE DIVISION.", "MAIN-PARA.", "    ENTRY 'DLITCBL'.", "    PERFORM P2.",
                "    GOBACK.", "P2.", "    DISPLAY 'X'.")  # fmt: skip
    head = b"Source: 'T.cbl'\nProgram-Id:  T\n"
    entry = head + b"Program-Id:  T                    Entry: DLITCBL                         Line:      5\n"
    body = (b"Program-Id:  T                           PERFORM                         Line:      5\n"
            b"Program-Id:  T                Paragraph: P2                              Line:      7\n"
            b"Program-Id:  T                           DISPLAY                         Line:      8\n"
            b"Program-Id:  T                           GOBACK                          Line:      6\n")  # fmt: skip
    plain = head + b"Program-Id:  T                    Entry: T                               Line:      3\n"
    got = _measure(tmp_path, text, entry + body)["paragraphs"]
    assert (got["covered"], got["live"]) == (2, 2)
    got = _measure(tmp_path, text, plain + body)["paragraphs"]
    assert (got["covered"], got["live"]) == (1, 2)  # the program's own entry is not a unit: MAIN-PARA stays unrun


def test_a_program_with_no_paragraph_is_one_unit_run_by_any_of_its_statements(tmp_path: Path) -> None:
    """COBSWAIT shape (CardDemo): statements straight after PROCEDURE DIVISION, no header. The trace has no Paragraph
    event for them, yet the unit is live (1, not 0/0 which reads as 'not measured') and entered when a statement ran."""
    text = _cbl("PROGRAM-ID. T.", "PROCEDURE DIVISION.", "    DISPLAY 'X'.", "    STOP RUN.")
    head = b"Source: 'T.cbl'\nProgram-Id:  T\n"
    entry = head + b"Program-Id:  T                    Entry: T                               Line:      3\n"
    ran = entry + b"Program-Id:  T                           DISPLAY                         Line:      3\n"
    got = _measure(tmp_path, text, ran)["paragraphs"]
    assert (got["covered"], got["live"], got["dead"], got["unread"]) == (1, 1, [], [])
    got = _measure(tmp_path, text, entry)["paragraphs"]  # entered, no statement ran
    assert (got["covered"], got["live"]) == (0, 1)


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


# ---- #4602: branch points after a transfer of control ------------------------------------------------------------
def _after(*body: str) -> list[int]:
    """The lines of the branch points set apart as unreachable in a program whose PROCEDURE DIVISION is `body`
    (line 4 on: body[0] is line 4)."""
    src = _cbl("PROGRAM-ID. T.", "PROCEDURE DIVISION.", "MAIN-PARA.", *body)
    inv = cov.inventory(Path("T.cbl"), text=src)
    return sorted(b.line for b in inv.after_transfer)


def test_if_after_an_evaluate_whose_every_arm_transfers_is_not_counted() -> None:
    src = _cbl(
        "PROGRAM-ID. T.",  # 1
        "PROCEDURE DIVISION.",  # 2
        "MAIN-PARA.",  # 3
        "    EVALUATE TRUE",  # 4
        "      WHEN X = 1",  # 5
        "        GO TO DONE-PARA",  # 6
        "      WHEN X = 2",  # 7
        "        EXEC CICS XCTL PROGRAM('P') END-EXEC",  # 8
        "      WHEN OTHER",  # 9
        "        IF Y = 1 GO TO DONE-PARA ELSE GOBACK END-IF",  # 10
        "    END-EVALUATE",  # 11
        "    IF X = 3",  # 12
        "       DISPLAY 'NEVER'",  # 13
        "    END-IF.",  # 14
        "DONE-PARA.",  # 15
        "    IF X = 4 DISPLAY 'FOUR' END-IF",  # 16
        "    STOP RUN.",  # 17
    )
    inv = cov.inventory(Path("T.cbl"), text=src)
    assert [b.line for b in inv.after_transfer] == [12]
    assert 12 not in [b.line for b in inv.branches] and 16 in [b.line for b in inv.branches]
    s = cov.summary(inv, cov.Hits())
    assert [(u["line"], u["outcome"]) for u in s["branches"]["after_transfer"]] == [(12, "true"), (12, "false")]
    assert s["branches"]["total"] == sum(len(b.outcomes()) for b in inv.branches)
    # a run that takes one anyway is flagged, never counted
    s = cov.summary(inv, cov.Hits(outcomes={(12, "true")}))
    assert s["branches"]["after_transfer_but_taken"] == ["12:true"] and s["branches"]["covered"] == 0


def test_an_arm_that_may_fall_through_keeps_the_next_branch_point() -> None:
    evaluate = ["    EVALUATE X", "      WHEN 1", "        GO TO MAIN-PARA"]
    tail = ["    END-EVALUATE", "    IF X = 3 DISPLAY 'Y' END-IF."]
    assert _after(*evaluate, *tail) == []  # no WHEN OTHER: no arm may match
    assert _after(*evaluate, "      WHEN OTHER", "        DISPLAY 'Z'", *tail) == []  # OTHER falls through
    assert _after("    IF X = 1 GO TO MAIN-PARA END-IF", "    IF X = 2 DISPLAY 'Y' END-IF.") == []  # no ELSE
    # a conditional phrase may not run
    assert _after("    READ F AT END GO TO MAIN-PARA END-READ", "    IF X = 2 DISPLAY 'Y' END-IF.") == []
    assert _after("    READ F INVALID KEY GO TO MAIN-PARA", "    NOT INVALID KEY DISPLAY 'K' END-READ",
                  "    IF X = 2 DISPLAY 'Y' END-IF.") == []  # fmt: skip
    assert _after("    ADD 1 TO X ON SIZE ERROR GOBACK END-ADD", "    IF X = 2 DISPLAY 'Y' END-IF.") == []
    # an inline PERFORM may run no time
    assert _after("    PERFORM UNTIL X > 1 GO TO MAIN-PARA END-PERFORM", "    IF X = 2 DISPLAY 'Y' END-IF.") == []
    # GO TO ... DEPENDING ON falls through when the index is out of range
    assert _after("    GO TO MAIN-PARA DEPENDING ON X", "    IF X = 2 DISPLAY 'Y' END-IF.") == []
    # a CICS RETURN / XCTL with RESP or NOHANDLE comes back on an error
    assert _after("    EXEC CICS XCTL PROGRAM('P') RESP(R) END-EXEC", "    IF X = 2 DISPLAY 'Y' END-IF.") == []
    assert _after("    EXEC CICS RETURN NOHANDLE END-EXEC", "    IF X = 2 DISPLAY 'Y' END-IF.") == []
    # an unconditional statement does not hide the transfer after it
    assert _after("    MOVE 1 TO X", "    GO TO MAIN-PARA", "    IF X = 2 DISPLAY 'Y' END-IF.") == [6]
    # the next sentence of the same paragraph is unreachable too; the next paragraph is not
    assert _after(
        "    GOBACK.", "    IF X = 2 DISPLAY 'Y' END-IF.", "NEXT-PARA.", "    IF X = 3 DISPLAY 'Z' END-IF."
    ) == [5]
    # a COPY may bring paragraph headers
    assert _after("    GOBACK.", "    COPY 'X'.", "    IF X = 2 DISPLAY 'Y' END-IF.") == []


def test_a_perform_of_a_paragraph_that_never_returns_transfers() -> None:
    sends = ["SEND-TEXT.", "    EXEC CICS SEND TEXT FROM(M) END-EXEC", "    EXEC CICS RETURN END-EXEC.", "SEND-TEXT-EXIT.",
             "    EXIT."]  # fmt: skip
    assert _after("    PERFORM SEND-TEXT THRU SEND-TEXT-EXIT", "    IF X = 2 DISPLAY 'Y' END-IF.", *sends) == [5]
    assert _after("    PERFORM SEND-TEXT", "    IF X = 2 DISPLAY 'Y' END-IF.", *sends) == [5]
    # it may run no time
    assert _after("    PERFORM SEND-TEXT UNTIL X = 1", "    IF X = 2 DISPLAY 'Y' END-IF.", *sends) == []
    assert _after("    PERFORM SEND-TEXT THRU SEND-TEXT-EXIT X TIMES", "    IF X = 2 DISPLAY 'Y' END-IF.", *sends) == []
    # a paragraph a GO TO leaves may still come back through the end of the range
    goes = ["SEND-TEXT.", "    GO TO SEND-TEXT-EXIT.", "SEND-TEXT-EXIT.", "    EXIT."]
    assert _after("    PERFORM SEND-TEXT THRU SEND-TEXT-EXIT", "    IF X = 2 DISPLAY 'Y' END-IF.", *goes) == []
    # a HANDLE label that may come back makes no paragraph absorbing: a raised condition goes there
    handle = ["    EXEC CICS HANDLE ABEND LABEL(ON-ABEND) END-EXEC", "    PERFORM SEND-TEXT",
              "    IF X = 2 DISPLAY 'Y' END-IF."]  # fmt: skip
    assert _after(*handle, *sends, "ON-ABEND.", "    DISPLAY 'A'.") == []
    assert _after(*handle, *sends, "ON-ABEND.", "    EXEC CICS ABEND ABCODE('X') END-EXEC.") == [6]


def test_a_go_to_into_a_paragraph_that_only_returns_transfers() -> None:
    """#4621: SEND-SCREEN ends in GO TO RETURN-TO-CICS, which only RETURNs: PERFORM SEND-SCREEN never comes back."""
    perf = ["    PERFORM SEND-SCREEN", "    IF X = 2 DISPLAY 'Y' END-IF."]
    ret = ["RETURN-TO-CICS.", "    EXEC CICS RETURN END-EXEC."]
    send = ["SEND-SCREEN.", "    EXEC CICS SEND TEXT FROM(M) END-EXEC", "    GO TO RETURN-TO-CICS."]
    assert _after(*perf, *send, *ret) == [5]
    # a target that falls through into the next paragraph is no way out of the program
    fall = ["RETURN-TO-CICS.", "    DISPLAY 'A'.", "NEXT-PARA.", "    DISPLAY 'B'."]
    assert _after(*perf, *send, *fall) == []
    # one of several targets that may come back
    assert (
        _after(*perf, "SEND-SCREEN.", "    GO TO RETURN-TO-CICS NEXT-PARA.", *ret, "NEXT-PARA.", "    DISPLAY 'B'.")
        == []
    )
    # a GO TO DEPENDING ON may fall through
    dep = ["SEND-SCREEN.", "    GO TO RETURN-TO-CICS DEPENDING ON X."]
    assert _after(*perf, *dep, *ret) == []
    # a chain: the target itself ends in a GO TO into a returning paragraph
    chain = ["MID.", "    GO TO RETURN-TO-CICS."]
    assert _after(*perf, "SEND-SCREEN.", "    GO TO MID.", *chain, *ret) == [5]


def test_an_equal_size_rewritten_block_is_paired_by_similarity() -> None:
    """#4620: four EXEC lines rewritten into four unlike lines are not the same lines."""
    original = _cbl(
        "PROCEDURE DIVISION.",  # 1
        "A.",  # 2
        "    EXEC CICS INQUIRE PROGRAM(WS-PGM)",  # 3
        "         NOHANDLE",  # 4
        "         RESP(WS-RESP)",  # 5
        "    END-EXEC",  # 6
        "    GOBACK.",  # 7
    )
    compiled = _cbl(
        "PROCEDURE DIVISION.",  # 1
        "A.",  # 2
        "    MOVE 'P' TO GG-NAME",  # 3
        "    CALL 'GGCINQ' USING GG-CICS",  # 4
        "    MOVE GG-RESP TO WS-RESP",  # 5
        "    MOVE 0 TO GG-X",  # 6
        "    GOBACK.",  # 7
    )
    lines = cov.LineMap(original, compiled)
    assert all(lines.get(n) is not None and lines.get(n)[1] is False for n in (3, 4, 5, 6))
    assert 3 not in lines.exact and 6 not in lines.exact


def test_a_condition_rewritten_in_place_stays_exact_in_an_equal_size_block() -> None:
    """#4620: `IF X NOT= DFHRESP(NORMAL)` -> `IF X NOT= 0` is the same IF though the lines differ a lot."""
    original = _cbl(
        "A.", "    IF WS-RESP NOT= DFHRESP(NORMAL) OR WS-OTHER-FLAG = DFHRESP(NORMAL)", "       GOBACK", "    END-IF."
    )
    compiled = _cbl("A.", "    IF WS-RESP NOT= 0 OR WS-OTHER-FLAG = 0", "       GOBACK", "    END-IF.")
    lines = cov.LineMap(original, compiled)
    assert lines.get(2) == (2, True) and 2 in lines.exact


def _seq(*lines: str) -> str:
    """Fixed format with a 6-digit sequence number and columns 73-80 numbered, as CardDemo's app-vsam-mq is."""
    return "\n".join(f"{n * 100 + 100:06d} " + x.ljust(65) + f"{n + 1:08d}" for n, x in enumerate(lines)) + "\n"


def _expanded(original: str, expansion: list[str], first: int, last: int) -> str:
    """The harness's output: original lines first..last (1-based) replaced by `expansion` (unnumbered), the rest kept."""
    rows = original.split("\n")
    return "\n".join(rows[: first - 1] + ["           " + x for x in expansion] + rows[last:])


RETRIEVE = [
    "MOVE 'INTO' TO GG-FLAGS", "MOVE LENGTH OF MQTM TO GG-LEN", "CALL 'GGCRTRV' USING GG-CICS",
    "    BY REFERENCE MQTM", "MOVE GG-RESP TO EIBRESP", "MOVE GG-RESP2 TO EIBRESP2",
]  # fmt: skip


def test_the_if_after_an_expanded_exec_maps_to_its_own_line_not_the_exec_whatever_the_sequence_area() -> None:
    """#6072: the sequence numbers and the padding made `EXEC CICS RETRIEVE` and the IF after it look alike (CODATE01
    145 -> 140); a condition rewritten (DFHRESP(NORMAL) -> 0) in a block of unequal size paired with nothing (COPAUA0C 237)."""
    body = [
        "A.", "    EXEC CICS RETRIEVE", "      INTO(MQTM)", "      NOHANDLE", "    END-EXEC",
        "    IF EIBRESP = DFHRESP(NORMAL)", "       MOVE 1 TO X", "    END-IF", "    GOBACK.",
    ]  # fmt: skip
    for original in (_seq(*body), _cbl(*body)):  # numbered and plain
        compiled = _expanded(original, RETRIEVE, 2, 5).replace("DFHRESP(NORMAL)", "0")
        lines = cov.LineMap(original, compiled)
        n = len(RETRIEVE)
        assert [lines.get(2 + k) for k in range(n)] == [(2, False)] * n  # the expansion stands for the EXEC
        assert lines.get(2 + n) == (6, True) and lines.get(3 + n) == (7, True)
        assert lines.exact == {1, 6, 7, 8, 9, 10}  # (10: the closing blank)


def test_a_line_inside_an_exec_is_never_the_same_line_as_a_compiled_one() -> None:
    """#6072: `LENGTH (LENGTH OF X)` inside a DLI / SQL call and the compiled `BY VALUE LENGTH OF X` are not one line."""
    original = _cbl(
        "A.", "    EXEC DLI GU", "      LENGTH (LENGTH OF REC)", "      INTO (REC)", "    END-EXEC", "    GOBACK."
    )
    compiled = _cbl("A.", "    MOVE 'GU' TO GG-FUNC", "    CALL 'GGCDLI' USING GG-CICS", "        BY VALUE LENGTH OF REC",
                    "        BY REFERENCE REC", "    GOBACK.")  # fmt: skip
    lines = cov.LineMap(original, compiled)
    assert lines.exact == {1, 6, 7}  # (7: the closing blank)
    assert all(lines.get(n) == (2, False) for n in (2, 3, 4, 5))


def test_evaluate_when_rewrites_pair_in_equal_and_unequal_blocks() -> None:
    for extra in ([], ["MOVE 0 TO GG-X"]):  # the compiled block as long as the original, and longer
        original = _cbl("A.", "    EVALUATE EIBRESP", "       WHEN DFHRESP(NORMAL)", "          MOVE 1 TO X",
                        "       WHEN DFHRESP(NOTFND)", "          MOVE 2 TO X", "    END-EVALUATE", "    GOBACK.")  # fmt: skip
        compiled = _cbl("A.", *extra, "    EVALUATE EIBRESP", "       WHEN 0", "          MOVE 1 TO X",
                        "       WHEN 13", "          MOVE 2 TO X", "    END-EVALUATE", "    GOBACK.")  # fmt: skip
        k = len(extra)
        lines = cov.LineMap(original, compiled)
        assert {lines.get(n + k) for n in (2, 3, 5)} == {(2, True), (3, True), (5, True)}


def test_a_free_format_or_identical_program_maps_as_before() -> None:
    free = "A.\n  IF X = 1\n    DISPLAY 'A'\n  END-IF.\n"
    assert cov.LineMap(free, free).map == {n: (n, True) for n in range(1, 6)}
    lines = cov.LineMap(free, "A.\n  MOVE 0 TO GG\n  IF X = 1\n    DISPLAY 'A'\n  END-IF.\n")
    assert lines.get(2) is None or lines.get(2)[1] is False
    assert lines.get(3) == (2, True) and lines.get(4) == (3, True)


# #6072: GnuCOBOL 3 (cobc -std=ibm -ftraceall) does not count the newlines between a sentence's period and a redundant
# one ("warning: ignoring redundant ."), so every traced line after it reads that many lines early, until a COPY
# resyncs the count. Each shape below was compiled and run in gitgalaxy-gnucobol:3; the pairs are (compiled line, the
# line the trace gave it).
_HEAD = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. T.", "       PROCEDURE DIVISION.", "       MAIN-PARA."]
_REDUNDANT = {
    "blank lines": (["PERFORM P1.", "", "    .", "", "DISPLAY 'A'", "DISPLAY 'B'", "GOBACK.", "P1.", "DISPLAY 'P'."],
                    [(5, 5), (9, 7), (10, 8), (11, 9), (13, 11)]),
    "an adjacent line": (["PERFORM P1.", "    .", "DISPLAY 'A'", "DISPLAY 'B'", "GOBACK."], [(7, 6), (8, 7), (9, 8)]),
    "an inline comment": (["PERFORM P1.", "*> c", "    .", "DISPLAY 'A'", "GOBACK."], [(8, 6), (9, 7)]),
    "a fixed-format comment": (["PERFORM P1.", "      * c", "    .", "DISPLAY 'A'", "GOBACK."], [(8, 6), (9, 7)]),
    "the same line": (["PERFORM P1. .", "", "DISPLAY 'A'", "GOBACK."], [(7, 7), (8, 8)]),
    "a chain of periods": (["PERFORM P1.", "", "    .", "", "    .", "DISPLAY 'A'", "GOBACK."], [(10, 6), (11, 7)]),
    "two, the second ending a sentence": (["PERFORM P1.", "", "", "    .", "DISPLAY 'A'", "DISPLAY 'B'", "",
                                           "    .", "", "DISPLAY 'C'", "GOBACK."], [(9, 6), (10, 7), (14, 11)]),
    "a period inside a literal": (["DISPLAY 'Z'.", "    .", "DISPLAY 'Q'.", "", "   . DISPLAY 'A'",
                                   "MOVE 'X. .' TO RETURN-CODE", "DISPLAY 'B'", "GOBACK."],
                                  [(5, 5), (7, 6), (10, 7), (11, 8), (12, 9)]),
    "a COPY after it": (["DISPLAY 'Z'.", "", "    .", "DISPLAY 'Q'", "COPY CPY.", "DISPLAY 'B'", "GOBACK."],
                        [(8, 6), (10, 10), (11, 11)]),
}  # fmt: skip


def _redundant(body: list[str]) -> str:
    return "\n".join(_HEAD + [x if not x or x.startswith("      *") else "           " + x for x in body]) + "\n"


def test_a_redundant_period_shifts_the_traced_lines_as_gnucobol_counts_them() -> None:
    for shape, (body, pairs) in _REDUNDANT.items():
        text = _redundant(body)
        for lines in (
            cov.LineMap(text),
            cov.LineMap(text, text),
            cov.LineMap(text.replace("PROGRAM-ID. T.", "PROGRAM-ID. U."), text),
        ):
            for compiled, traced in pairs:
                assert lines.get(traced) == (compiled, True), (shape, compiled, traced)


def test_a_redundant_period_in_the_data_division_or_free_format_shifts_the_trace_too() -> None:
    data = _HEAD[:2] + ["       DATA DIVISION.", "       WORKING-STORAGE SECTION.", "       01 X PIC X.", "",
                        "           .", "       PROCEDURE DIVISION.", "       MAIN-PARA.", "           DISPLAY 'A'",
                        "           GOBACK."]  # fmt: skip
    assert cov.LineMap("\n".join(data) + "\n").get(8) == (10, True)
    free = 'IDENTIFICATION DIVISION.\nPROGRAM-ID. T.\nPROCEDURE DIVISION.\nMAIN-PARA.\nDISPLAY "Z".\n\n*> c\n.\nDISPLAY "A"\nGOBACK.\n'
    lines = cov.LineMap(free)
    assert (lines.get(5), lines.get(6), lines.get(7)) == ((5, True), (9, True), (10, True))


def test_a_program_with_no_redundant_period_keeps_the_traced_lines() -> None:
    """Decimal points, periods in literals, a period ending an unterminated sentence; a `.` in the sequence area of a
    short fixed line (CBSA BNK1DCS: no token); a lone `.` after a COPY ... REPLACING's period (CardDemo COACTUPC, whose
    traces show no shift: the COPY's end resyncs the count)."""
    for body in (["MOVE 1.5 TO X.", "DISPLAY 'A. B'.", "", "DISPLAY 'C'", "    .", "GOBACK."],
                 ["MOVE 1 TO X.", "", "", "DISPLAY 'C'", "GOBACK."],
                 ["COPY CPY REPLACING ==A== BY ==B== .", "    .", "DISPLAY 'C'", "GOBACK."]):  # fmt: skip
        text = _redundant(body)
        if not body[1]:
            text = text.replace("\n\n\n", "\n.\n\n", 1)
        lines = cov.LineMap(text)
        assert all(lines.get(n) == (n, True) for n in range(1, len(body) + 5)), body


def test_an_evaluate_after_a_redundant_period_gets_its_arm(tmp_path: Path) -> None:
    """COACCT01's shape: `PERFORM 8000-TERMINATION.`, a blank line, a lone `.`; the EVALUATE after it is traced two
    lines early, so its WHEN arm was read as a run of nothing (6/33)."""
    text = _cbl("PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.", "01 X PIC 9 VALUE 1.",
                "PROCEDURE DIVISION.", "MAIN-PARA.", "    PERFORM P1.", "", "         .", "    EVALUATE X",
                "      WHEN 1", "        DISPLAY 'ONE'", "      WHEN OTHER", "        DISPLAY 'OTHER'",
                "    END-EVALUATE", "    GOBACK.", "P1.", "    CONTINUE.")  # fmt: skip
    trace = (b"Source: 'T.cbl'\nProgram-Id:  T\n"
             b"Program-Id:  T                    Entry: T                               Line:      5\n"
             b"Program-Id:  T                Paragraph: MAIN-PARA                       Line:      6\n"
             b"Program-Id:  T                           PERFORM                         Line:      7\n"
             b"Program-Id:  T                Paragraph: P1                              Line:     15\n"
             b"Program-Id:  T                           CONTINUE                        Line:     16\n"
             b"Program-Id:  T                           EVALUATE                        Line:      8\n"
             b"Program-Id:  T                           DISPLAY                         Line:     10\n"
             b"Program-Id:  T                           GOBACK                          Line:     14\n")  # fmt: skip
    b = _measure(tmp_path, text, trace)["branches"]
    assert (b["covered"], b["total"]) == (1, 2)
    assert [(u["line"], u["outcome"]) for u in b["uncovered"]] == [(10, "OTHER")]


# ---- #5084: the programs a case LINKs / CALLs ---------------------------------------------------------------------
def test_write_run_coverage_measures_the_linked_programs_over_the_same_trace(tmp_path: Path) -> None:
    main = _cbl("PROGRAM-ID. MAINP.", "PROCEDURE DIVISION.", "A.", "    GOBACK.")
    callee = _cbl(
        "PROGRAM-ID. SUBP.", "PROCEDURE DIVISION.", "B.", "    PERFORM C", "    GOBACK.", "C.", "    CONTINUE."
    )
    trace = (
        b"Program-Id:  MAINP   Entry: MAINP   Line: 2\nProgram-Id:  MAINP   Paragraph: A   Line: 3\n"
        b"Program-Id:  SUBP   Entry: SUBP   Line: 2\nProgram-Id:  SUBP   Paragraph: B   Line: 3\n"
    )
    t = tmp_path / "trace.txt"
    t.write_bytes(trace)
    extras = [{"name": "SUBP", "source": tmp_path / "SUBP.cbl", "original": callee, "compiled": callee,
               "compiled_name": "SUBP.cbl"},
              {"name": "BAD", "source": tmp_path / "BAD.cbl", "original": None, "compiled": None,
               "compiled_name": "BAD.cbl"}]  # fmt: skip
    out = tmp_path / "coverage.json"
    s = cov.write_run_coverage(out, extras=extras, source=tmp_path / "MAINP.cbl", original=main, compiled=None,
                               traces=[t], compiled_name="MAINP.cbl")  # fmt: skip
    assert s["paragraphs"]["covered"] == s["paragraphs"]["live"] == 1  # the main program's numbers are its own
    sub = s["linked"]["SUBP"]
    assert (sub["paragraphs"]["covered"], sub["paragraphs"]["live"]) == (1, 2)  # C never ran: a hole
    assert "error" in s["linked"]["BAD"]  # unmeasurable: recorded as unknown, the run goes on
    assert "linked" not in cov.write_run_coverage(out, source=tmp_path / "MAINP.cbl", original=main, compiled=None,
                                                  traces=[t], compiled_name="MAINP.cbl")  # fmt: skip


def test_a_case_run_reads_branches_against_the_staged_text_not_the_original(tmp_path):
    """#6072: the harness stages a lowered program (the PSA -> TCB -> TIOT walk, A2) with lines added before its IFs;
    the trace names the staged text's lines, so the line map must be built from that text (CBSTM03A read 0/46)."""
    import equivalence

    corpus, run = tmp_path / "corpus", tmp_path / "run"
    (run / "src").mkdir(parents=True)
    corpus.mkdir()
    (corpus / "t.cbl").write_text(PROGRAM, encoding="latin-1")
    lowered = PROGRAM.replace("    IF X = 1\n", '    CALL "GGSTUB"\n    CALL "GGSTUB"\n    IF X = 1\n', 1)
    (run / "src" / "PROGRAM.cbl").write_text(lowered, encoding="latin-1")
    shifted = TRACE.decode().replace("Line:      9", "Line:     11").replace("Line:     10", "Line:     12")
    for n in range(14, 24):  # every later line moves down by the two inserted
        shifted = shifted.replace(f"Line:     {n}\n", f"Line:     {n + 2}\n")
    trace = run / "trace.txt"
    trace.write_text(shifted.replace("Source: 'T.cbl'", "Source: 'src/PROGRAM.cbl'"), encoding="latin-1")
    out = tmp_path / "coverage.json"
    got = equivalence.cobol_coverage({"program_source": "t.cbl", "program": "T"}, corpus, [trace], out)
    assert got is not None
    unlowered = cov.run_coverage(corpus / "t.cbl", PROGRAM, PROGRAM, [trace], "PROGRAM.cbl", None, "latin-1")
    assert got["branches"]["covered"] > unlowered["branches"]["covered"] == 0
