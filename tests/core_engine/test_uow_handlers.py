"""
#3453: units of work and error handling (core/uow_handlers.py), run through
`extract_boundary` exactly as a scan does. Shapes from CBSA (HANDLE ABEND
LABEL, SYNCPOINT ROLLBACK, ABEND ABCODE NODUMP, EXEC SQL COMMIT WORK) and
CardDemo (HANDLE CONDITION PGMIDERR, RESP fields tested or never tested).
"""

import time

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.uow_handlers import extract_uow_handlers


def _rows(source: str) -> list[tuple]:
    return [
        (r["kind"], r["verb"], r["condition"], r["target"], r["target_kind"], r["resp_var"], r["line"])
        for r in extract_boundary("cobol", source)["uow_handlers"]
    ]


def test_commit_rollback_and_abend_handling():
    src = (
        "       01 WS-ABCODE PIC X(4) VALUE 'HBNK'.\n"  # 1
        "       PROCEDURE DIVISION.\n"  # 2
        "       P010.\n"  # 3
        "           EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING) END-EXEC.\n"  # 4
        "           EXEC CICS SYNCPOINT END-EXEC.\n"  # 5
        "           EXEC CICS SYNCPOINT ROLLBACK END-EXEC.\n"  # 6
        "           EXEC SQL\n"  # 7
        "              COMMIT WORK\n"  # 8
        "           END-EXEC.\n"  # 9
        "           EXEC CICS ABEND ABCODE(WS-ABCODE) NODUMP CANCEL END-EXEC.\n"  # 10
        "           EXEC CICS ABEND ABCODE('PLOP') END-EXEC.\n"  # 11
        "           EXEC CICS HANDLE ABEND CANCEL END-EXEC.\n"  # 12
    )
    assert _rows(src) == [
        ("HANDLE_ABEND", "HANDLE ABEND", None, "ABEND-HANDLING", "LABEL", None, 4),
        ("COMMIT", "SYNCPOINT", None, None, None, None, 5),
        ("ROLLBACK", "SYNCPOINT ROLLBACK", None, None, None, None, 6),
        ("COMMIT", "COMMIT WORK", None, None, None, None, 7),
        ("ABEND", "ABEND", "HBNK", None, None, None, 10),
        ("ABEND", "ABEND", "PLOP", None, None, None, 11),
        ("HANDLE_ABEND", "HANDLE ABEND", None, None, "CANCEL", None, 12),
    ]
    rows = extract_boundary("cobol", src)["uow_handlers"]
    assert rows[4]["attributes"] == "NODUMP CANCEL" and rows[3]["source"] == "SQL"


def test_handle_condition_ignore_and_aid_pairs():
    src = (
        "           EXEC CICS HANDLE CONDITION PGMIDERR(PGMIDERR-ERR-PARA)\n"
        "                NOTFND(NOT-FOUND) LENGERR END-EXEC.\n"
        "           EXEC CICS IGNORE CONDITION MAPFAIL END-EXEC.\n"
        "           EXEC CICS HANDLE AID PF3(RETURN-TO-MENU) END-EXEC.\n"
        "           EXEC CICS PUSH HANDLE END-EXEC.\n"
    )
    assert [r[:5] for r in _rows(src)] == [
        ("HANDLE_CONDITION", "HANDLE CONDITION", "PGMIDERR", "PGMIDERR-ERR-PARA", "LABEL"),
        ("HANDLE_CONDITION", "HANDLE CONDITION", "NOTFND", "NOT-FOUND", "LABEL"),
        ("HANDLE_CONDITION", "HANDLE CONDITION", "LENGERR", None, "DEFAULT"),
        ("IGNORE_CONDITION", "IGNORE CONDITION", "MAPFAIL", None, None),
        ("HANDLE_AID", "HANDLE AID", "PF3", "RETURN-TO-MENU", "LABEL"),
        ("PUSH_HANDLE", "PUSH HANDLE", None, None, None),
    ]


def test_resp_checks_are_tied_to_their_command():
    src = (
        "       READ-CUST.\n"  # 1
        "           EXEC CICS READ FILE('CUSTOMER') INTO(REC)\n"  # 2
        "                RESP(WS-RESP) END-EXEC.\n"  # 3
        "           EVALUATE WS-RESP\n"  # 4
        "             WHEN DFHRESP(NORMAL) CONTINUE\n"  # 5
        "             WHEN DFHRESP(NOTFND)\n"  # 6
        "               EXEC CICS LINK PROGRAM('ABNDPROC') END-EXEC\n"  # 7
        "             WHEN OTHER CONTINUE\n"  # 8
        "           END-EVALUATE.\n"  # 9
        "           EXEC CICS RECEIVE MAP('M1') INTO(X) RESP(WS-RESP)\n"  # 10
        "           END-EXEC.\n"  # 11
        "       NEXT-PARA.\n"  # 12
        "           IF WS-RESP = DFHRESP(MAPFAIL) CONTINUE END-IF.\n"  # 13
        "           EXEC CICS RETRIEVE INTO(MQTM) NOHANDLE END-EXEC\n"  # 14
        "           IF EIBRESP = DFHRESP(NORMAL) CONTINUE END-IF.\n"  # 15
    )
    checks = [(r[1], r[2], r[5], r[6]) for r in _rows(src) if r[0] == "RESP_CHECK"]
    # The LINK sets no RESP, so it neither ends READ's window nor is checked;
    # RECEIVE's field is only tested past a paragraph header, so it is untested.
    assert checks == [
        ("READ", "NORMAL,NOTFND", "WS-RESP", 2),
        ("RECEIVE", None, "WS-RESP", 10),
        ("RETRIEVE", "NORMAL", "EIBRESP", 14),
    ]


def test_literals_and_non_uow_code_draw_nothing():
    src = "           DISPLAY 'EXEC CICS SYNCPOINT'.\n           MOVE 'COMMIT' TO X.\n"
    assert _rows(src) == []


def test_numbered_source_reads_the_same():
    src = (
        "       P1.\n"
        "           EXEC CICS READ FILE('F') INTO(R) RESP(WS-RESP)\n"
        "           END-EXEC\n"
        "           IF WS-RESP NOT = DFHRESP(NORMAL)\n"
        "              EXEC CICS SYNCPOINT ROLLBACK END-EXEC\n"
        "           END-IF.\n"
    )
    numbered = "\n".join(f"{n:06d}{line[6:]:<66}{n:08d}" for n, line in enumerate(src.splitlines(), 1)) + "\n"
    assert _rows(numbered) == _rows(src)


def test_the_resp_window_is_bounded():
    src = "           EXEC CICS READ FILE('F') RESP(V) END-EXEC\n" * 3000 + "MOVE V TO X " * 20000
    started = time.perf_counter()
    extract_uow_handlers(src)
    assert time.perf_counter() - started < 10.0
