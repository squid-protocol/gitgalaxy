"""
#3449: the CICS task-control extractor (core/cics_tasks.py), run through
`extract_boundary` exactly as a scan does.

The async shapes are CBSA's credit-agency fan-out (CRECUST RUN / FETCH ANY,
CRDTAGY1..5 DELAY) and carddemo's MQ-triggered RETRIEVE, reduced to the lines
that matter; START / CANCEL / POST / WAIT are documented CICS forms. Each test
pins one decision: which commands draw a row, which operand is the target, the
token and the channel, and how a STRING-built transaction id becomes a pattern.
"""

import fnmatch
import time

from gitgalaxy.core.cics_tasks import _pic_pattern, extract_cics_tasks
from gitgalaxy.core.mainframe_boundary import extract_boundary


def _tasks(source: str, dialect: str = "cobol") -> list[dict]:
    return extract_boundary(dialect, source)["cics_tasks"]


def _one(source: str, dialect: str = "cobol") -> dict:
    rows = _tasks(source, dialect)
    assert len(rows) == 1, rows
    return rows[0]


CRECUST = (
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-CC-CNT                 PIC 9      VALUE 0.\n"
    "       01 WS-CHANNEL-NAME           PIC X(16)  VALUE SPACES.\n"
    "       01 WS-RUN-TRANSID            PIC X(4)   VALUE SPACES.\n"
    "       01 WS-CHILD-TKNS.\n"
    "          03 WS-ANY-CHILD-TKN       PIC X(16).\n"
    "          03 WS-FETCH-TKN           PIC X(16).\n"
    "       PROCEDURE DIVISION.\n"
    "           MOVE 'CIPCREDCHANN    ' TO WS-CHANNEL-NAME.\n"
    "           PERFORM VARYING WS-CC-CNT FROM 1 BY 1\n"
    "           UNTIL WS-CC-CNT > 5\n"
    "              STRING 'OCR' DELIMITED BY SIZE,\n"
    "                      WS-CC-CNT DELIMITED BY SIZE\n"
    "                 INTO WS-RUN-TRANSID\n"
    "              END-STRING\n"
    "              EXEC CICS RUN TRANSID(WS-RUN-TRANSID)\n"
    "                   CHANNEL(WS-CHANNEL-NAME)\n"
    "                   CHILD(WS-ANY-CHILD-TKN)\n"
    "                   RESP(WS-CICS-RESP)\n"
    "              END-EXEC\n"
    "           END-PERFORM.\n"
    "           EXEC CICS DELAY\n"
    "              FOR SECONDS(3)\n"
    "           END-EXEC.\n"
    "           EXEC CICS FETCH ANY(WS-FETCH-TKN)\n"
    "                CHANNEL(WS-FETCH-CHAN)\n"
    "                NOSUSPEND\n"
    "                COMPSTATUS(WS-COMPST)\n"
    "                ABCODE(WS-ABCODE)\n"
    "           END-EXEC.\n"
)


def test_run_with_a_string_built_transid_is_a_pic_sized_pattern():
    run, delay, fetch = _tasks(CRECUST)
    assert (run["verb"], run["target_kind"], run["operand"]) == ("RUN", "TRANSID", "WS-RUN-TRANSID")
    assert (run["name"], run["resolution"], run["candidates"]) == (None, "pattern", "OCR[0-9]")
    assert (run["channel"], run["token"]) == ("CIPCREDCHANN", "WS-ANY-CHILD-TKN")
    # The pattern reaches OCR1..OCR5 and never the deck's OCRA.
    assert [t for t in ("OCR1", "OCR5", "OCRA", "OCR") if fnmatch.fnmatchcase(t, run["candidates"])] == [
        "OCR1",
        "OCR5",
    ]
    assert (delay["verb"], delay["timing"]) == ("DELAY", "FOR SECONDS(3)")
    assert (fetch["verb"], fetch["token"], fetch["channel_operand"]) == ("FETCH ANY", "WS-FETCH-TKN", "WS-FETCH-CHAN")
    assert fetch["attributes"] == "NOSUSPEND COMPSTATUS(WS-COMPST) ABCODE(WS-ABCODE)"
    assert fetch["target_kind"] is None and fetch["resolution"] is None


def test_a_string_of_literals_only_resolves_to_its_one_name():
    src = "           STRING 'OC' 'R1' DELIMITED BY SIZE INTO WS-T.\n           EXEC CICS RUN TRANSID(WS-T) END-EXEC.\n"
    assert (_one(src)["name"], _one(src)["resolution"]) == ("OCR1", "string")


def test_a_non_size_delimited_or_unsized_source_is_a_star_and_all_star_is_dropped():
    src = (
        "           STRING 'AB' DELIMITED BY SIZE WS-X DELIMITED BY SPACE\n"
        "              INTO WS-T.\n"
        "           STRING WS-Y DELIMITED BY SIZE INTO WS-U.\n"
        "           EXEC CICS START TRANSID(WS-T) END-EXEC.\n"
        "           EXEC CICS START TRANSID(WS-U) END-EXEC.\n"
    )
    t, u = _tasks(src)
    assert (t["resolution"], t["candidates"]) == ("pattern", "AB*")
    assert (u["resolution"], u["candidates"]) == ("unresolved", None)


def test_a_value_or_single_move_still_wins_over_a_string():
    src = (
        "       01 WS-T PIC X(4) VALUE 'OCAC'.\n"
        "           STRING 'X' DELIMITED BY SIZE INTO WS-T.\n"
        "           EXEC CICS START TRANSID(WS-T) END-EXEC.\n"
    )
    assert (_one(src)["name"], _one(src)["resolution"]) == ("OCAC", "value")


def test_moved_literals_and_a_string_pattern_are_candidates_together():
    src = (
        "           MOVE 'OCAC' TO WS-T.\n"
        "           STRING 'OCR' DELIMITED BY SIZE WS-N DELIMITED BY SIZE\n"
        "              INTO WS-T.\n"
        "       01 WS-N PIC 99.\n"
        "           EXEC CICS RUN TRANSID(WS-T) CHILD(TK) END-EXEC.\n"
    )
    row = _one(src)
    assert (row["resolution"], row["candidates"]) == ("pattern", "OCAC,OCR[0-9][0-9]")


def test_pic_widths():
    assert _pic_pattern("9") == "[0-9]"
    assert _pic_pattern("S9(2)") == "[0-9][0-9]"
    assert _pic_pattern("X(3)") == "???"
    assert _pic_pattern("XX") == "??"
    assert _pic_pattern("9V9") == "*"
    assert _pic_pattern("Z9") == "*"
    assert _pic_pattern(None) == "*"


def test_start_with_from_reqid_interval_and_channel():
    row = _one(
        "           EXEC CICS START TRANSID('OCUP')\n"
        "                FROM(WS-REQUEST) LENGTH(80)\n"
        "                INTERVAL(0010) REQID(WS-REQ)\n"
        "                TERMID(EIBTRMID)\n"
        "           END-EXEC.\n"
    )
    assert (row["verb"], row["name"], row["resolution"]) == ("START", "OCUP", "literal")
    assert (row["record_clause"], row["record"], row["token"]) == ("FROM", "WS-REQUEST", "WS-REQ")
    assert row["timing"] == "INTERVAL(0010)"
    assert row["attributes"] == "LENGTH(80) TERMID(EIBTRMID)"


def test_retrieve_cancel_post_wait_and_attach():
    rows = _tasks(
        "           EXEC CICS RETRIEVE INTO(MQTM) NOHANDLE END-EXEC.\n"
        "           EXEC CICS CANCEL REQID(WS-REQ) TRANSID('OCUP') END-EXEC.\n"
        "           EXEC CICS POST AFTER SECONDS(5) SET(WS-ECB-PTR) END-EXEC.\n"
        "           EXEC CICS WAIT EVENT ECADDR(WS-ECB-PTR) END-EXEC.\n"
        "           EXEC CICS WAITCICS ECBLIST(WS-LIST) NUMEVENTS(2) END-EXEC.\n"
        "           EXEC CICS START ATTACH TRANSID('ABCD') FROM(X) END-EXEC.\n"
        "           EXEC CICS FREE CHILD(WS-TKN) END-EXEC.\n"
        "           EXEC CICS FETCH CHILD(WS-TKN) CHANNEL(WS-CH) END-EXEC.\n"
    )
    got = [(r["verb"], r["name"], r["token"], r["record"], r["timing"], r["attributes"]) for r in rows]
    assert got == [
        ("RETRIEVE", None, None, "MQTM", None, None),
        ("CANCEL", "OCUP", "WS-REQ", None, None, None),
        ("POST", None, None, "WS-ECB-PTR", "AFTER SECONDS(5)", None),
        ("WAIT EVENT", None, None, None, None, "ECADDR(WS-ECB-PTR)"),
        ("WAITCICS", None, None, None, None, "ECBLIST(WS-LIST) NUMEVENTS(2)"),
        ("START ATTACH", "ABCD", None, "X", None, None),
        ("FREE CHILD", None, "WS-TKN", None, None, None),
        ("FETCH CHILD", None, "WS-TKN", None, None, None),
    ]


def test_enq_deq_target_the_resource():
    enq, deq = _tasks(
        "       01 WS-LOCK PIC X(8) VALUE 'CBSACUST'.\n"
        "           EXEC CICS ENQ RESOURCE(WS-LOCK) LENGTH(8) NOSUSPEND END-EXEC.\n"
        "           EXEC CICS DEQ RESOURCE(WS-LOCK) LENGTH(8) END-EXEC.\n"
    )
    assert (enq["verb"], enq["target_kind"], enq["name"], enq["resolution"]) == ("ENQ", "RESOURCE", "CBSACUST", "value")
    assert enq["attributes"] == "LENGTH(8) NOSUSPEND" and deq["verb"] == "DEQ"


def test_non_task_commands_and_literal_commands_draw_nothing():
    src = (
        "           EXEC CICS RETURN TRANSID('OCAC') END-EXEC.\n"
        "           EXEC CICS LINK PROGRAM('X') END-EXEC.\n"
        "           EXEC CICS WAIT TERMINAL END-EXEC.\n"
        "           EXEC CICS STARTBR FILE('F') RIDFLD(K) END-EXEC.\n"
        "           DISPLAY 'EXEC CICS FETCH ANY failed. RESP='.\n"
    )
    assert _tasks(src) == []


def test_pli_statements_end_at_semicolon():
    row = _one("  EXEC CICS START TRANSID('PLI1') FROM(REQ);\n  X = 1;\n", "pli")
    assert (row["verb"], row["name"], row["record"]) == ("START", "PLI1", "REQ")


def test_the_string_reader_and_blocks_are_bounded():
    unterminated = "           STRING 'A' " + "WS-X DELIMITED BY SIZE " * 5000 + "\n"
    openers = "           EXEC CICS RUN TRANSID(X)\n" * 5000
    started = time.perf_counter()
    extract_cics_tasks(unterminated + openers)
    assert time.perf_counter() - started < 5.0
