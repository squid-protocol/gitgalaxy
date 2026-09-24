"""
#3447: the IBM MQ call extractor (core/mq_calls.py), run through
`extract_boundary` exactly as a scan does. The shapes are CardDemo's
COACCT01 (named handles copied from a shared MQ-HOBJ, sequence-numbered lines)
and COPAUA0C (qualified descriptors, a trigger-named input queue, MQPUT1 to the
requester's reply-to queue), reduced to the lines that matter.
"""

import time

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.mq_calls import extract_mq_calls


def _calls(source: str) -> list[tuple]:
    return [
        (r["verb"], r["direction"], r["queue"], r["resolution"], r["handle"], r["open_line"])
        for r in extract_boundary("cobol", source)["mq_calls"]
    ]


COACCT = (
    "       01 REPLY-QUEUE-NAME     PIC X(48) VALUE SPACES.\n"  # 1
    "       PROCEDURE DIVISION.\n"  # 2
    "           EXEC CICS RETRIEVE INTO(MQTM) END-EXEC\n"  # 3
    "           MOVE MQTM-QNAME TO INPUT-QUEUE-NAME\n"  # 4
    "           MOVE 'CARD.DEMO.REPLY.ACCT' TO REPLY-QUEUE-NAME.\n"  # 5
    "       2300-OPEN-INPUT-QUEUE.\n"  # 6
    "           MOVE INPUT-QUEUE-NAME TO MQOD-OBJECTNAME\n"  # 7
    "           COMPUTE MQ-OPTIONS = MQOO-INPUT-SHARED\n"  # 8
    "                              + MQOO-FAIL-IF-QUIESCING\n"  # 9
    "           CALL 'MQOPEN' USING QMGR-HANDLE-CONN\n"  # 10
    "                               MQ-OBJECT-DESCRIPTOR\n"  # 11
    "                               MQ-OPTIONS MQ-HOBJ\n"  # 12
    "                               MQ-CONDITION-CODE MQ-REASON-CODE\n"  # 13
    "           MOVE MQ-HOBJ TO INPUT-QUEUE-HANDLE.\n"  # 14
    "       2400-OPEN-OUTPUT-QUEUE.\n"  # 15
    "           MOVE REPLY-QUEUE-NAME TO MQOD-OBJECTNAME\n"  # 16
    "           COMPUTE MQ-OPTIONS = MQOO-OUTPUT\n"  # 17
    "           CALL 'MQOPEN' USING QMGR-HANDLE-CONN MQ-OBJECT-DESCRIPTOR\n"  # 18
    "                               MQ-OPTIONS MQ-HOBJ MQ-CC MQ-RC\n"  # 19
    "           MOVE MQ-HOBJ TO OUTPUT-QUEUE-HANDLE.\n"  # 20
    "       3000-GET-REQUEST.\n"  # 21
    "           MOVE INPUT-QUEUE-HANDLE TO MQ-HOBJ\n"  # 22
    "           COMPUTE MQGMO-OPTIONS = MQGMO-SYNCPOINT + MQGMO-WAIT\n"  # 23
    "           CALL 'MQGET' USING MQ-HCONN MQ-HOBJ MQ-MD MQ-GMO\n"  # 24
    "                MQ-BUFFER-LENGTH MQ-BUFFER MQ-DATA-LENGTH MQ-CC MQ-RC.\n"  # 25
    "       4100-PUT-REPLY.\n"  # 26
    "           CALL 'MQPUT' USING MQ-HCONN OUTPUT-QUEUE-HANDLE MQ-MD\n"  # 27
    "                MQ-PMO MQ-BUFFER-LENGTH MQ-BUFFER MQ-CC MQ-RC.\n"  # 28
    "           DISPLAY 'CALL MQPUT FAILED'.\n"  # 29
    "           CALL 'MQCLOSE' USING MQ-HCONN INPUT-QUEUE-HANDLE\n"  # 30
    "                MQ-CLOSE-OPTIONS MQ-CC MQ-RC.\n"  # 31
)


def test_queues_resolve_through_the_descriptor_and_handles_find_their_open():
    assert _calls(COACCT) == [
        ("MQOPEN", "get", None, "trigger", "MQ-HOBJ", None),
        ("MQOPEN", "put", "CARD.DEMO.REPLY.ACCT", "move", "MQ-HOBJ", None),
        ("MQGET", "get", None, "trigger", "INPUT-QUEUE-HANDLE", 10),
        ("MQPUT", "put", "CARD.DEMO.REPLY.ACCT", "move", "OUTPUT-QUEUE-HANDLE", 18),
        ("MQCLOSE", None, None, "trigger", "INPUT-QUEUE-HANDLE", 10),
    ]
    rows = extract_boundary("cobol", COACCT)["mq_calls"]
    assert rows[0]["options"] == "MQOO-INPUT-SHARED MQOO-FAIL-IF-QUIESCING"
    assert rows[2]["options"] == "MQGMO-SYNCPOINT MQGMO-WAIT"


def test_sequence_numbered_source_reads_the_same():
    # CardDemo's COACCT01 numbers cols 1-6 and 73-80 (`019200 ... 01328707`), and
    # the cols 73-80 tag used to end the CALL's operand list.
    numbered = "\n".join(f"{n:06d}{line[6:]:<66}{1328700 + n:08d}" for n, line in enumerate(COACCT.splitlines(), 1))
    assert _calls(numbered + "\n") == _calls(COACCT)


def test_qualified_descriptors_and_mqput1_to_the_reply_to_queue():
    src = (
        "           MOVE MQTM-QNAME TO WS-REQUEST-QNAME\n"
        "           MOVE WS-REQUEST-QNAME TO MQOD-OBJECTNAME OF MQM-OD-REQUEST\n"
        "           COMPUTE WS-OPTIONS = MQOO-INPUT-SHARED\n"
        "           CALL 'MQOPEN' USING W01-HCONN MQM-OD-REQUEST WS-OPTIONS\n"
        "                W01-HOBJ-REQUEST WS-CC WS-RC END-CALL\n"
        "           CALL 'MQGET' USING W01-HCONN W01-HOBJ-REQUEST MQM-MD\n"
        "                MQM-GMO LEN BUF DLEN WS-CC WS-RC END-CALL\n"
        "           MOVE MQMD-REPLYTOQ OF MQM-MD-REQUEST\n"
        "                TO WS-REPLY-QNAME\n"
        "           MOVE WS-REPLY-QNAME TO MQOD-OBJECTNAME OF MQM-OD-REPLY\n"
        "           CALL 'MQPUT1' USING W02-HCONN MQM-OD-REPLY MQM-MD-REPLY\n"
        "                MQM-PMO LEN BUF WS-CC WS-RC END-CALL\n"
    )
    assert _calls(src) == [
        ("MQOPEN", "get", None, "trigger", "W01-HOBJ-REQUEST", None),
        ("MQGET", "get", None, "trigger", "W01-HOBJ-REQUEST", 4),
        ("MQPUT1", "put", None, "reply_to", None, None),
    ]


def test_literal_value_and_ambiguous_queue_names():
    src = (
        "       01 WS-Q PIC X(48) VALUE 'APP.IN'.\n"
        "           MOVE 'A.ONE' TO WS-X\n"
        "           MOVE 'A.TWO' TO WS-X\n"
        "           MOVE 'LIT.Q' TO MQOD-OBJECTNAME\n"
        "           CALL 'MQPUT1' USING H OD MD PMO L B CC RC\n"
        "           MOVE WS-Q TO MQOD-OBJECTNAME\n"
        "           CALL 'MQPUT1' USING H OD MD PMO L B CC RC\n"
        "           MOVE WS-X TO MQOD-OBJECTNAME\n"
        "           CALL 'MQPUT1' USING H OD MD PMO L B CC RC\n"
        "           CALL 'MQGET' USING H UNKNOWN-HANDLE MD GMO L B DL CC RC\n"
    )
    rows = extract_boundary("cobol", src)["mq_calls"]
    got = [(r["queue"], r["resolution"], r["candidates"]) for r in rows]
    assert got == [
        ("LIT.Q", "literal", None),
        ("APP.IN", "value", None),
        (None, "ambiguous", "A.ONE,A.TWO"),
        (None, "unresolved", None),
    ]


def test_no_mq_calls_draw_nothing_and_the_scan_is_bounded():
    assert _calls("           CALL 'CBLTDLI' USING GU PCB.\n") == []
    src = "           CALL 'MQPUT' USING " + "A " * 20000 + "\n" + "MOVE X TO Y " * 20000
    started = time.perf_counter()
    extract_mq_calls(src)
    assert time.perf_counter() - started < 5.0
