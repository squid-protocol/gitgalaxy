"""#5079 (oracle_assumptions.md X63): EXEC CICS POST, WAIT EVENT and terminal CONVERSE -- the whole class of each command.

IBM (CICS TS 6.x): POST "requests notification that a specified time has expired" through a 4-byte timer-event control area
("initialized to binary zeros"; posted: "its first byte is set to X'40' and its third byte to X'80'"), conditions EXPIRED and INVREQ
RESP2 4 / 5 / 6; WAIT EVENT ECADDR waits for that area, INVREQ RESP2 2 for a null pointer; CONVERSE (default) writes FROM to the
terminal and reads the reply INTO (TOLENGTH, MAXLENGTH, NOTRUNCATE), LENGERR the one condition. The pieces, each over the whole
class:
- the det translator over a whole program: every expiry form, SET / REQID / NAME, every CONVERSE length form; each refusal by name;
- the equivalence harness's translator: the same forms onto the stub's GGCPOST / GGCWEVT / GGCCONV, the same refusals;
- both runtimes, driven by ONE scenario table (compiled stub, compiled CicsTask) and held to the hand-traced answers of the table:
  every expiry form and range, EXPIRED, the generated REQID, WAIT on a posted / unposted / null / foreign / ended area, CANCEL of a
  POST, CONVERSE that fits, is cut, keeps the rest, has a negative or zero length, and the LUTYPE2 refusal.
(The two runtimes answering one program alike is tests/cobol_mainframe/test_post_wait_converse_e2e_5079.py.)
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests" / "tools"))
sys.path.insert(0, str(HERE.parents[1] / "tests" / "cics_crucible"))
import test_cics_runtimes as R  # noqa: E402  (bare imports: tests/ has no __init__.py, see CLAUDE.md)
import test_pointer_lane_4771 as PL  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up: no JVM start a compile

NOT_GIVEN = -999999999

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRLN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  ECB-PTR                USAGE POINTER.
       01  WS-RESP                PIC S9(08) COMP VALUE 0.
       01  WS-RESP2               PIC S9(08) COMP VALUE 0.
       01  WS-IN                  PIC X(10).
       01  WS-LEN                 PIC S9(04) COMP VALUE 0.
       01  WS-LEN4                PIC S9(08) COMP VALUE 0.
       01  WS-N                   PIC S9(04) COMP VALUE 3.
       01  WS-HH                  PIC S9(04) COMP VALUE 1.
       01  WS-REQ                 PIC X(8) VALUE 'MYREQ'.
       LINKAGE SECTION.
       01  ECB-VIEW               PIC X(4).
       PROCEDURE DIVISION.
           EXEC CICS POST INTERVAL(30) SET(ECB-PTR) RESP(WS-RESP)
           END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


def _program(command: str) -> str:
    """The program with `command` (an EXEC CICS body) in place of its POST, wrapped to fixed form."""
    wrapped = textwrap.wrap(command, 46, break_long_words=False, break_on_hyphens=False)
    return PROGRAM.replace("POST INTERVAL(30) SET(ECB-PTR) RESP(WS-RESP)", ("\n" + " " * 16).join(wrapped))


def _java(tmp_path: Path, command: str) -> tuple[list[str], str]:
    r = PL._translate(tmp_path, _program(command))
    return r.stats["holes"], r.java


# ---- the det translator over a whole program -----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("command", "call"),
    [
        ("POST SET(ECB-PTR)", 'task.post("INTERVAL", 0, null, null, null, null)'),
        ("POST INTERVAL(30) SET(ECB-PTR)", 'task.post("INTERVAL", 30, null, null, null, null)'),
        ("POST INTERVAL(WS-HH) SET(ECB-PTR)", 'task.post("INTERVAL", Cobol.num('),
        ("POST TIME(090000) SET(ECB-PTR)", 'task.post("TIME", 90000, null, null, null, null)'),
        ("POST AFTER SECONDS(30) SET(ECB-PTR)", 'task.post("AFTER", 0, null, null, 30, null)'),
        ("POST AFTER HOURS(1) MINUTES(2) SECONDS(3)", 'task.post("AFTER", 0, 1, 2, 3, null)'),
        ("POST AT HOURS(9) MINUTES(0) SET(ECB-PTR)", 'task.post("AT", 0, 9, 0, null, null)'),
        ("POST AFTER MINUTES(WS-N) REQID(WS-REQ)", 'task.post("AFTER", 0, null, Cobol.num('),
        ("POST INTERVAL(5) REQID('TMR1') SET(ECB-PTR)", 'task.post("INTERVAL", 5, null, null, null, "TMR1".strip())'),
    ],
)
def test_post_translates_whole_in_every_expiry_form(tmp_path, command, call):
    holes, java = _java(tmp_path, command)
    assert holes == [], holes
    assert call in java, call
    assert ("DetCics.setPointer(" in java) == ("SET(" in command)  # (SET only when the program names a pointer)
    # EIBREQID gets the REQID CICS generated -- only when the program gave none (IBM: "CICS generates one")
    assert ("DetCics.putPadded(" in java and "EIBREQID" in java) == ("REQID" not in command)


def test_post_raises_its_conditions_through_resp_and_handle_condition(tmp_path):
    holes, java = _java(tmp_path, "POST INTERVAL(30) SET(ECB-PTR) RESP(WS-RESP) RESP2(WS-RESP2)")
    assert holes == []
    assert "DetCics.resp(post" in java and ".resp2()" in java and "WS_RESP2" in java


@pytest.mark.parametrize(
    "command",
    [
        "WAIT EVENT ECADDR(ECB-PTR)",
        "WAIT EVENT ECADDR(ECB-PTR) NAME('TIMER')",
        "WAIT EVENT ECADDR(ECB-PTR) RESP(WS-RESP) RESP2(WS-RESP2)",
        "WAIT EVENT ECADDR(ECB-PTR) NOHANDLE",
    ],
)
def test_wait_event_translates_whole(tmp_path, command):
    holes, java = _java(tmp_path, command)
    assert holes == [], holes
    assert "task.waitEvent(DetCics.pointerValue(" in java


@pytest.mark.parametrize(
    ("command", "expect"),
    [
        ("CONVERSE FROM(WS-IN) INTO(WS-IN)", ("false);", "task.converse(")),
        ("CONVERSE FROM(WS-IN) FROMLENGTH(4) INTO(WS-IN) TOLENGTH(WS-LEN)", ("Cobol.store(", ", 4, ")),
        ("CONVERSE FROM(WS-IN) FROMFLENGTH(4) INTO(WS-IN) TOFLENGTH(WS-LEN4)", ("WS_LEN4", ", 4, ")),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) MAXLENGTH(5)", (", 5, false", "task.converse(")),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) MAXFLENGTH(5)", (", 5, false", "task.converse(")),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) MAXLENGTH(5) NOTRUNCATE", (", 5, true", "task.converse(")),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) TOLENGTH(WS-LEN) RESP(WS-RESP)", ("WS_RESP", "task.converse(")),
    ],
)
def test_converse_translates_whole_in_every_length_form(tmp_path, command, expect):
    holes, java = _java(tmp_path, command)
    assert holes == [], holes
    for fragment in expect:
        assert fragment in java, fragment


@pytest.mark.parametrize(
    ("command", "expect"),
    [
        (
            "CONVERSE FROM(WS-IN) SET(ECB-PTR) TOLENGTH(WS-LEN)",
            ("Integer.MAX_VALUE, false", "DetCics.setBlock(task, ", '"RECEIVE"'),
        ),
        ("CONVERSE FROM(WS-IN) SET(ECB-PTR) TOFLENGTH(WS-LEN4)", ("WS_LEN4", "Integer.MAX_VALUE, false")),
        (
            "CONVERSE FROM(WS-IN) FROMLENGTH(4) SET(ECB-PTR) TOLENGTH(WS-LEN) MAXLENGTH(5) NOTRUNCATE",
            (", 4, 5, true", "setBlock"),
        ),
        ("CONVERSE FROM(WS-IN) SET(ECB-PTR) TOLENGTH(WS-LEN) RESP(WS-RESP)", ("WS_RESP", "setBlock")),
    ],
)
def test_converse_set_puts_the_reply_in_a_block_as_receive_set_does(tmp_path, command, expect):
    """X58: CONVERSE SET(pointer) is RECEIVE SET's lane (same key, so the next terminal read ends it); TOLENGTH is output-only."""
    holes, java = _java(tmp_path, command)
    assert holes == [], holes
    for fragment in expect:
        assert fragment in java, fragment
    assert "DetCics.received(" not in java  # (the INTO form's store is not used)


# ---- each refusal, by name -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("command", "why"),
    [
        ("POST INTERVAL(5) TIME(090000)", "POST INTERVAL and TIME: one expiry option"),
        ("POST AFTER SECONDS(5) INTERVAL(5)", "one expiry option"),
        ("POST AFTER", "HOURS / MINUTES / SECONDS go with AFTER / AT"),
        ("POST HOURS(1) SET(ECB-PTR)", "HOURS / MINUTES / SECONDS go with AFTER / AT"),
        ("POST INTERVAL(5) SYSID('ABCD')", "option not modelled"),
        ("POST INTERVAL(5) SET(WS-RESP)", "not a plain USAGE POINTER"),
        ("WAIT EVENT", "WAIT EVENT without ECADDR"),
        ("WAIT EVENT ECADDR(WS-RESP)", "not a plain USAGE POINTER"),
        ("WAIT EVENT ECADDR(ECB-PTR) ECBLIST(ECB-PTR)", "option not modelled"),
        ("CONVERSE FROM(WS-IN) SET(ECB-PTR)", "CONVERSE SET without TOLENGTH(data-area)"),
        ("CONVERSE FROM(WS-IN) SET(ECB-PTR) TOLENGTH(4)", "CONVERSE SET without TOLENGTH(data-area)"),
        ("CONVERSE FROM(WS-IN) SET(ECB-PTR) TOFLENGTH(4)", "CONVERSE SET without TOLENGTH(data-area)"),
        ("CONVERSE FROM(WS-IN) SET(WS-RESP) TOLENGTH(WS-LEN)", "not a plain USAGE POINTER"),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) SET(ECB-PTR) TOLENGTH(WS-LEN)", "CONVERSE without INTO"),
        (
            "CONVERSE FROM(WS-IN) SET(ECB-PTR) TOLENGTH(WS-LEN) CONVID('C1')",
            "a conversation with a partner transaction",
        ),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) CONVID('C1')", "a conversation with a partner transaction"),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) STATE(WS-LEN)", "a conversation with a partner transaction"),
        ("CONVERSE ATTACHID('A1') INTO(WS-IN)", "a conversation with a partner transaction"),
        ("CONVERSE INTO(WS-IN)", "CONVERSE without FROM"),
        ("CONVERSE FROM(WS-IN)", "CONVERSE without INTO"),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) MAXLENGTH(2) MAXFLENGTH(2)", "together"),
        ("CONVERSE FROM(WS-IN) INTO(WS-IN) TOLENGTH(WS-LEN) TOFLENGTH(WS-LEN4)", "together"),
        ("CONVERSE FROM(WS-IN) FROMLENGTH(1) FROMFLENGTH(1) INTO(WS-IN)", "together"),
    ],
)
def test_what_the_commands_cannot_model_is_refused_by_name(tmp_path, command, why):
    holes, _java_text = _java(tmp_path, command)
    assert any(why in h for h in holes), (why, holes)


def test_wait_external_and_waitcics_stay_name_only_with_the_x63_reason(tmp_path):
    for command in ("WAIT EXTERNAL ECBLIST(ECB-PTR) NUMEVENTS(1)", "WAITCICS ECBLIST(ECB-PTR) NUMEVENTS(1)"):
        holes, _java_text = _java(tmp_path, command)
        assert any("other than a POST's timer-event control area" in h for h in holes), holes


def test_the_register_entry_cites_each_ibm_page_and_the_spec_points_at_it():
    from gitgalaxy.standards.cics.commands import COMMANDS

    register = (HERE.parents[1] / "docs/language_status/register/X63.md").read_text(encoding="utf-8")
    for key in ("POST", "WAIT EVENT", "CONVERSE"):
        assert COMMANDS[key].status == "modelled" and COMMANDS[key].register == "X63", key
        assert COMMANDS[key].ibm.url in register, key
    for key in ("WAIT EXTERNAL", "WAITCICS"):
        assert COMMANDS[key].status == "refused" and COMMANDS[key].register == "X63", key
    for key in ("SEND PAGE", "PURGE MESSAGE"):  # (still refused: the BMS logical message)
        assert COMMANDS[key].status == "refused" and COMMANDS[key].register == "X59", key


# ---- the equivalence harness's translator --------------------------------------------------------------------------------------
def _ec():
    import equivalence_cics as ec

    return ec


def test_the_harness_calls_the_stubs_entry_points():
    ec = _ec()
    out = ec.translate_command("POST AFTER SECONDS(30) SET(P) REQID('T1') RESP(R)")
    assert out[0] == "MOVE 'AFTER' TO GG-FLAGS" and "MOVE 'T1' TO GG-QNAME" in out
    assert "MOVE 30 TO GG-SECS" in out and "MOVE -999999999 TO GG-HOURS" in out
    assert out[out.index("CALL 'GGCPOST' USING GG-CICS") + 1] == "    BY REFERENCE P"
    assert "    MOVE GG-NAME1 TO EIBREQID" not in out  # (the program named a REQID)
    no_reqid = ec.translate_command("POST INTERVAL(45) SET(P)")
    assert "MOVE 45 TO GG-NUM" in no_reqid and "    MOVE GG-NAME1 TO EIBREQID" in no_reqid
    no_set = ec.translate_command("POST TIME(090000)")
    assert no_set[no_set.index("CALL 'GGCPOST' USING GG-CICS") + 1] == "    BY REFERENCE GG-PTR"
    wait = ec.translate_command("WAIT EVENT ECADDR(P) NAME('X') RESP(R)")
    assert wait[:2] == ["CALL 'GGCWEVT' USING GG-CICS", "    BY REFERENCE P"] and "MOVE GG-RESP TO R" in wait
    conv = ec.translate_command("CONVERSE FROM(A) FROMLENGTH(4) INTO(B) TOLENGTH(L) MAXLENGTH(9) NOTRUNCATE")
    assert conv[:2] == ["MOVE 'NOTRUNCATE' TO GG-FLAGS", "MOVE 9 TO GG-LEN"]
    assert conv[conv.index("CALL 'GGCCONV' USING GG-CICS") + 1 :][:3] == ["    BY REFERENCE A", "    BY VALUE 4",
                                                                           "    BY REFERENCE B"]  # fmt: skip
    assert "IF GG-LEN >= 0 AND (GG-RESP = 0 OR GG-RESP = 22)" in conv and "    MOVE GG-LEN TO L" in conv
    plain = ec.translate_command("CONVERSE FROM(A) INTO(B)")
    assert "MOVE LENGTH OF B TO GG-LEN" in plain and "    BY VALUE LENGTH OF A" in plain
    assert not any("MOVE GG-LEN TO" in line for line in plain)  # (no TOLENGTH: nothing to set)


@pytest.mark.parametrize(
    "text",
    [
        "POST INTERVAL(5) TIME(090000)",
        "POST AFTER",
        "POST HOURS(1)",
        "POST INTERVAL(5) SYSID('ABCD')",
        "POST INTERVAL(5) SET(A(1))",
        "WAIT EVENT",
        "WAIT EVENT ECADDR(A OF B)",
        "WAIT EVENT ECADDR(P) ECBLIST(P)",
        "CONVERSE FROM(A) SET(P)",
        "CONVERSE FROM(A) INTO(B) CONVID('C1')",
        "CONVERSE INTO(B)",
        "CONVERSE FROM(A)",
        "CONVERSE FROM(A) INTO(B) MAXLENGTH(1) MAXFLENGTH(1)",
        "CONVERSE FROM(A) INTO(B) TOLENGTH(L) TOFLENGTH(L)",
        "CONVERSE FROM(A) FROMLENGTH(1) FROMFLENGTH(1) INTO(B)",
    ],
)
def test_the_harness_refuses_what_the_translator_refuses(text):
    with pytest.raises(_ec().Unsupported):
        _ec().translate_command(text)


def test_the_harness_reads_a_cancel_the_stub_logged_as_cicstask_records_it():
    ec = _ec()
    res = {"screens": [], "text": [], "events": ["CANCEL reqid=TMR1 resp=13", "CANCEL reqid=TMR2 resp=0"], "return": {}}
    assert ec.cobol_events(res) == [{"event": "CANCEL", "reqid": "TMR1", "resp": "NOTFND"},
                                    {"event": "CANCEL", "reqid": "TMR2", "resp": "NORMAL"}]  # fmt: skip


# ---- both runtimes, one scenario table ------------------------------------------------------------------------------------------
# Each scenario: (name, terminal input or None, LUTYPE2?, ops, the lines both runtimes print). The answers are IBM's, hand-traced
# (the module docstring); `post` ops are (label, how, hhmmss, hours, minutes, seconds, reqid) at the stated clock 10:00:00.
# A line is `label resp/resp2 reqid` for a POST, `label resp/resp2` for a WAIT EVENT, `label resp` for a CANCEL / START,
# `label area=hex` for the 4 bytes, `label ptr=null|set` for the pointer, and `label resp length data=text` for a CONVERSE;
# a refusal ends the scenario with its message.
ENDED = "WAIT EVENT on a timer-event control area a later POST, CANCEL, START or DELAY ended: not modelled"
FOREIGN = "WAIT EVENT on an address that is no POST's timer-event control area: not modelled"
LU2 = "CONVERSE on an LUTYPE2 terminal (the reply would raise EOC, which IBM does not list for CONVERSE): not modelled"
NG = None  # an hours / minutes / seconds the program did not give


def _post(label, how, hhmmss=0, h=NG, m=NG, s=NG, reqid=None):
    return ("post", label, how, hhmmss, h, m, s, reqid)


RANGE_CASES = [  # (op, resp, resp2): IBM's POST "Conditions": INVREQ RESP2 4 hours, 5 minutes, 6 seconds out of range
    (_post("i0", "INTERVAL", 0), 0, 0),
    (_post("i1", "INTERVAL", 995959), 0, 0),
    (_post("i2", "INTERVAL", 250000), 0, 0),  # hours run to 99
    (_post("i3", "INTERVAL", 1000000), 16, 4),
    (_post("i4", "INTERVAL", 6000), 16, 5),  # 00:60:00
    (_post("i5", "INTERVAL", 60), 16, 6),  # 00:00:60
    (_post("i6", "INTERVAL", -1), 16, 4),
    (_post("a1", "AFTER", h=99, m=59, s=59), 0, 0),
    (_post("a2", "AFTER", h=0, m=0, s=0), 0, 0),
    (_post("a3", "AFTER", h=100), 16, 4),
    (_post("a4", "AFTER", m=5999), 0, 0),  # alone, MINUTES runs to 5999
    (_post("a5", "AFTER", m=6000), 16, 5),
    (_post("a6", "AFTER", s=359999), 0, 0),  # alone, SECONDS runs to 359999
    (_post("a7", "AFTER", s=360000), 16, 6),
    (_post("a8", "AFTER", h=1, m=60), 16, 5),  # with another, MINUTES stops at 59
    (_post("a9", "AFTER", h=1, s=60), 16, 6),
    (_post("a10", "AFTER", h=1, m=1, s=1), 0, 0),
]
TIME_CASES = [  # clock 10:00:00 -- a time already past is EXPIRED, one at the clock or later is not, hours above 23: the next day
    (_post("t1", "TIME", 90000), 31, 0),
    (_post("t2", "TIME", 100000), 0, 0),
    (_post("t3", "TIME", 100001), 0, 0),
    (_post("t4", "TIME", 235959), 0, 0),
    (_post("t5", "TIME", 240000), 0, 0),
    (_post("t6", "TIME", 1000000), 16, 4),
    (_post("t7", "TIME", 6000), 16, 5),
    (_post("t8", "AT", h=9, m=0, s=0), 31, 0),
    (_post("t9", "AT", h=10, m=0, s=0), 0, 0),
    (_post("t10", "AT", h=25, m=0, s=0), 0, 0),
    (_post("t11", "AT", h=0, m=0, s=1), 31, 0),
]


def _range_lines(cases):
    # (a POST that raised a condition shows `-` for its reqid: nothing was made; the generated ones count from POST0001)
    out, n = [], 0
    for op, resp, resp2 in cases:
        if resp == 0:
            n += 1
        out.append(f"{op[1]} {resp}/{resp2} " + (f"POST{n:04d}" if resp == 0 else "-"))
    return out


SCENARIOS = [
    ("range", None, False, [op for op, *_ in RANGE_CASES], _range_lines(RANGE_CASES)),
    ("time", None, False, [op for op, *_ in TIME_CASES], _range_lines(TIME_CASES)),
    (
        "interval",
        None,
        False,
        [
            _post("p1", "INTERVAL", 30, reqid="TMR1"),
            ("area", "a1", "p1"),
            ("wait", "w1", "p1"),
            ("area", "a2", "p1"),
            ("wait", "w2", "p1"),
            ("cancel", "c1", "TMR1"),
        ],
        ["p1 0/0 TMR1", "a1 area=00000000", "w1 0/0", "a2 area=40008000", "w2 0/0", "c1 13"],
    ),
    (
        "interval_zero",
        None,
        False,
        [_post("p1", "INTERVAL", 0, reqid="Z"), ("cancel", "c1", "Z"), ("wait", "w1", "p1"), ("area", "a1", "p1")],
        ["p1 0/0 Z", "c1 13", "w1 0/0", "a1 area=40008000"],
    ),
    (
        "cancel_unexpired",
        None,
        False,
        [_post("p1", "AFTER", m=2, reqid="TMR2"), ("cancel", "c1", "TMR2"), ("cancel", "c2", "TMR2")],
        ["p1 0/0 TMR2", "c1 0", "c2 13"],
    ),
    (
        "generated_reqid",
        None,
        False,
        [_post("p1", "INTERVAL", 5), _post("p2", "INTERVAL", 5), ("wait", "w2", "p2"), ("area", "a2", "p2")],
        ["p1 0/0 POST0001", "p2 0/0 POST0002", "w2 0/0", "a2 area=40008000"],
    ),
    (
        "expired_leaves_the_pointer",
        None,
        False,
        [_post("p1", "TIME", 90000, reqid="E1"), ("ptr", "q1", "p1"), ("cancel", "c1", "E1")],
        ["p1 31/0 -", "q1 ptr=null", "c1 13"],
    ),
    (
        "wait_null",
        None,
        False,
        [("wait", "w1", "null")],
        ["w1 16/2"],
    ),
    ("wait_foreign", None, False, [("wait", "w1", "foreign")], [FOREIGN]),
    (
        "second_post_ends_the_first",
        None,
        False,
        [_post("p1", "INTERVAL", 5), _post("p2", "INTERVAL", 5), ("wait", "w2", "p2"), ("wait", "w1", "p1")],
        ["p1 0/0 POST0001", "p2 0/0 POST0002", "w2 0/0", ENDED],
    ),
    (
        "cancel_ends",
        None,
        False,
        [_post("p1", "INTERVAL", 5, reqid="T"), ("cancel", "c1", "T"), ("wait", "w1", "p1")],
        ["p1 0/0 T", "c1 0", ENDED],
    ),
    (
        "delay_ends",
        None,
        False,
        [_post("p1", "INTERVAL", 5), ("delay",), ("wait", "w1", "p1")],
        ["p1 0/0 POST0001", ENDED],
    ),
    (
        "start_ends",
        None,
        False,
        [_post("p1", "INTERVAL", 5), ("start", "s1"), ("wait", "w1", "p1")],
        ["p1 0/0 POST0001", "s1 0", ENDED],
    ),
    (
        "a_failed_post_ends_nothing",
        None,
        False,
        [_post("p1", "INTERVAL", 5), _post("p2", "INTERVAL", 60), _post("p3", "TIME", 90000), ("wait", "w1", "p1")],
        ["p1 0/0 POST0001", "p2 16/6 -", "p3 31/0 -", "w1 0/0"],
    ),
    (
        "converse_fits",
        "OK",
        False,
        [("converse", "c1", "HELLO!", 6, 6, False)],
        ["c1 0 2 data=OK"],
    ),
    (
        "converse_cut",
        "ABCDEFGHIJ",
        False,
        [("converse", "c1", "HELLO!", 6, 6, False)],
        ["c1 22 10 data=ABCDEF"],
    ),
    (
        "converse_notruncate_keeps_the_rest",
        "ABCDEFGHIJ",
        False,
        [("converse", "c1", "HELLO!", 6, 6, True), ("converse", "c2", "AGAIN!", 6, 6, True)],
        ["c1 0 6 data=ABCDEF", "c2 0 4 data=GHIJ"],
    ),
    (
        "converse_sends_only_fromlength",
        "OK",
        False,
        [("converse", "c1", "HELLO!", 3, 6, False)],
        ["c1 0 2 data=OK"],
    ),
    (
        "converse_negative_fromlength",
        "OK",
        False,
        [("converse", "c1", "HELLO!", -1, 6, False)],
        ["c1 22 -1 data=-"],
    ),
    (
        "converse_zero_and_negative_max_are_zero",
        "AB",
        False,
        [("converse", "c1", "HELLO!", 6, 0, False)],
        ["c1 22 2 data="],
    ),
    (
        "converse_negative_max",
        "AB",
        False,
        [("converse", "c1", "HELLO!", 6, -3, False)],
        ["c1 22 2 data="],
    ),
    ("converse_no_input", None, False, [("converse", "c1", "HELLO!", 6, 6, False)], ["c1 0 0 data="]),
    ("converse_lutype2", "OK", True, [("converse", "c1", "HELLO!", 6, 6, False)], [LU2]),
]


def _c_main() -> str:
    def stmt(op) -> str:
        kind = op[0]
        if kind == "post":
            _, label, how, num, h, m, s, reqid = op
            g = lambda v: NOT_GIVEN if v is NG else v  # noqa: E731
            return (
                f'    nm(c.qname, 16, "{reqid or ""}"); fl("{how}"); c.num = {num}; c.hours = {g(h)}; c.mins = {g(m)}; '
                f"c.secs = {g(s)}; a_{label} = NULL; GGCPOST(&c, &a_{label});\n"
                f'    printf("{label} %d/%d %s\\n", c.resp, c.resp2, c.resp == 0 ? tr(c.name1) : "-");'
            )
        if kind == "wait":
            _, label, target = op
            area = {"null": "NULL", "foreign": "junk"}.get(target, f"a_{target}")
            return f'    x = {area}; GGCWEVT(&c, &x); printf("{label} %d/%d\\n", c.resp, c.resp2);'
        if kind == "area":
            return f'    printf("{op[1]} area=%s\\n", hex4(a_{op[2]}));'
        if kind == "ptr":
            return f'    printf("{op[1]} ptr=%s\\n", a_{op[2]} ? "set" : "null");'
        if kind == "cancel":
            return f'    nm(c.qname, 16, "{op[2]}"); GGCCNCL(&c); printf("{op[1]} %d\\n", c.resp);'
        if kind == "delay":
            return '    fl("INTERVAL"); c.num = 1; GGCDLAY(&c);'
        if kind == "start":
            return (
                f'    nm(c.name1, 8, "TRN1"); nm(c.name2, 8, ""); nm(c.qname, 16, ""); fl("INTERVAL"); c.num = 0; c.item = 0; '
                f'c.len = 0; GGCSTRT(&c, c.flags); printf("{op[1]} %d\\n", c.resp);'
            )
        _, label, text, fromlen, most, nt = op
        return (
            f"    memset(into, ' ', sizeof into); fl(\"{'NOTRUNCATE' if nt else ''}\"); c.len = {most}; "
            f'GGCCONV(&c, "{text}", {fromlen}, into);\n'
            f'    printf("{label} %d %d data=", c.resp, c.len); '
            f"if (c.len >= 0) for (int i = 0; i < c.len && i < (c.len < {max(most, 0)} ? c.len : {max(most, 0)}); i++) "
            f"putchar(into[i]); else putchar('-'); putchar(10);"
        )

    labels = sorted({op[1] for _n, _t, _l, ops, _e in SCENARIOS for op in ops if op[0] == "post"})
    cases = "\n".join(
        f'    if (strcmp(argv[1], "{name}") == 0) {{\n' + "\n".join(stmt(op) for op in ops) + "\n    return 0;\n    }"
        for name, _t, _l, ops, _e in SCENARIOS
    )
    decls = "".join(f"    void *a_{label} = NULL;\n" for label in labels)
    return (
        r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCPOST(gg_cics *c, void **slot);
int GGCWEVT(gg_cics *c, void **slot);
int GGCCNCL(gg_cics *c);
int GGCDLAY(gg_cics *c);
int GGCSTRT(gg_cics *c, char *from);
int GGCCONV(gg_cics *c, char *from, int fromlen, char *into);
static gg_cics c;
static char junk[4];
static void fl(const char *s) { memset(c.flags, ' ', 40); memcpy(c.flags, s, strlen(s)); }
static void nm(char *d, int n, const char *s) { memset(d, ' ', (size_t)n); memcpy(d, s, strlen(s)); }
static const char *tr(const char *name1) {
    static char b[9];
    memcpy(b, name1, 8);
    b[8] = 0;
    for (int i = 7; i >= 0 && b[i] == ' '; i--) b[i] = 0;
    return b;
}
static const char *hex4(void *p) {
    static char b[9];
    for (int i = 0; i < 4; i++) sprintf(b + 2 * i, "%02X", ((unsigned char *)p)[i]);
    return b;
}
int main(int argc, char **argv) {
    char into[64];
    void *x;
"""
        + decls
        + r"""    memset(&c, 0, sizeof c);
"""
        + cases
        + "\n    return 1;\n}\n"
    )


def _java_main() -> str:
    num = 'String num(String r) { switch (r) { case "NORMAL": return "0"; case "NOTFND": return "13"; case "INVREQ": return "16"; '
    num += 'case "LENGERR": return "22"; case "EXPIRED": return "31"; default: return r; } }'

    def stmt(op) -> str:
        kind = op[0]
        if kind == "post":
            _, label, how, n, h, m, s, reqid = op
            j = lambda v: "null" if v is NG else str(v)  # noqa: E731
            r = f'{{"{reqid}"}}' if False else (f'"{reqid}"' if reqid else "null")
            return (
                f'            p_{label} = t.post("{how}", {n}, {j(h)}, {j(m)}, {j(s)}, {r});\n'
                f'            out("{label} " + num(p_{label}.resp()) + "/" + p_{label}.resp2() + " " + '
                f'(p_{label}.handle() != 0 ? p_{label}.reqid() : "-"));'
            )
        if kind == "wait":
            _, label, target = op
            handle = {"null": "0L", "foreign": "987654L"}.get(target, f"p_{target}.handle()")
            return f'            w = t.waitEvent({handle}); out("{label} " + w[0] + "/" + w[1]);'
        if kind == "area":
            return f'            out("{op[1]} area=" + hex(t, p_{op[2]}.handle()));'
        if kind == "ptr":
            return f'            out("{op[1]} ptr=" + (p_{op[2]}.handle() != 0 ? "set" : "null"));'
        if kind == "cancel":
            return f'            out("{op[1]} " + num(t.cancel("{op[2]}")));'
        if kind == "delay":
            return '            t.delay(1000, "DELAY");'
        if kind == "start":
            return f'            out("{op[1]} " + num(t.start("TRN1", null, 0, null, null, false).resp()));'
        _, label, text, fromlen, most, nt = op
        return (
            f'            rc = t.converse("{text}".substring(0, Math.min({len(text)}, Math.max({fromlen}, 0))), {fromlen}, '
            f"{most}, {str(nt).lower()});\n"
            f'            out("{label} " + num(rc.resp()) + " " + rc.length() + " data=" + (rc.data() == null ? "-" : rc.data()));'
        )

    labels = sorted({op[1] for _n, _t, _l, ops, _e in SCENARIOS for op in ops if op[0] == "post"})
    body = []
    for name, term, lu2, ops, _e in SCENARIOS:
        setup = ""
        if term is not None:
            setup += f'.withTerminalInput("{term}")'
        if lu2:
            setup += ".withEndOfChain(true)"
        body.append(
            f'        out("== {name}");\n        try {{\n'
            f'            CicsTask t = new CicsTask("ZC01", "ENTER", null, null).withClock(NOW){setup};\n'
            + "\n".join(stmt(op) for op in ops)
            + "\n        } catch (UnsupportedOperationException e) {\n            out(e.getMessage());\n        }"
        )
    decls = "".join(f"        CicsTask.PostResult p_{label} = null;\n" for label in labels)
    return (
        """
import java.time.LocalDateTime;
import t.cics.CicsTask;
public class Main {
    static final LocalDateTime NOW = LocalDateTime.of(2026, 10, 14, 10, 0, 0);
    static void out(String s) { System.out.println(s); }
    static String hex(CicsTask t, long h) {
        byte[] b = t.storageAt(h, 4);
        return String.format("%02X%02X%02X%02X", b[0] & 255, b[1] & 255, b[2] & 255, b[3] & 255);
    }
    static """
        + num
        + """
    public static void main(String[] a) {
        int[] w;
        CicsTask.Received rc;
"""
        + decls
        + "\n".join(body).replace("            CicsTask t =", "            CicsTask t =")
        + "\n    }\n}\n"
    )


def _javac() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


@pytest.fixture(scope="module")
def stub_exe(tmp_path_factory):
    if R.CC is None:
        pytest.skip("needs a C compiler")
    return R._stub(tmp_path_factory.mktemp("stub"), _c_main())


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_the_stub_answers_each_scenario(stub_exe, tmp_path, scenario):
    name, terminal, lu2, _ops, expected = scenario
    work = tmp_path / "w"
    (work / "out").mkdir(parents=True)
    if terminal is not None:
        (work / "terminal.in").write_bytes(terminal.encode("ascii"))
    env = {
        **R._stub_base_env(),
        "GGCICS_DIR": str(work),
        "GGCICS_OUT": str(work / "out"),
        "GGCICS_NOW": "2026-10-14T10:00:00",
    }
    if lu2:
        env["GGCICS_LU2"] = "1"
    run = subprocess.run([str(stub_exe), name], env=env, capture_output=True, text=True, check=False)  # noqa: S603
    assert run.stdout.splitlines() == expected, (run.stdout, run.stderr)
    assert run.returncode == (98 if expected[-1].endswith(": not modelled") else 0)


def test_the_stub_records_a_converse_as_a_send_then_a_receive(stub_exe, tmp_path):
    """CONVERSE writes FROM to the terminal -- the event a plain SEND records, `len` the FROMLENGTH -- then reads the reply, as RECEIVE."""
    work = tmp_path / "w"
    (work / "out").mkdir(parents=True)
    (work / "terminal.in").write_bytes(b"OK")
    env = {
        **R._stub_base_env(),
        "GGCICS_DIR": str(work),
        "GGCICS_OUT": str(work / "out"),
        "GGCICS_NOW": "2026-10-14T10:00:00",
    }
    subprocess.run(
        [str(stub_exe), "converse_sends_only_fromlength"], env=env, capture_output=True, text=True, check=True
    )  # noqa: S603
    events = (work / "out" / "events.txt").read_text().splitlines()
    assert [e.split(" ", 1)[1].replace(" pgm=", "") for e in events] == [
        "SEND-TEXT len=3 opts=DATA",
        "RECEIVE resp=0 len=2 copied=2",
    ]
    assert (work / "out" / "001.bin").read_bytes() == b"HEL"  # (the first FROMLENGTH bytes)


@pytest.mark.skipif(_javac() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_port_answers_each_scenario_as_the_stub_does(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA
    from gitgalaxy.tools.cobol_to_java.det import program as P

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = _java_main()
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _javac()
    assert jdk is not None
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),  # noqa: S603
                            *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    got: dict[str, list[str]] = {}
    for line in out:
        if line.startswith("== "):
            got[line[3:]] = current = []
        else:
            current.append(line)
    assert {name: lines for name, lines in got.items()} == {s[0]: s[4] for s in SCENARIOS}
