"""#4892: the IBM MQ calls (MQI) GitGalaxy models, the one list the det translator (det/mq.py) and the model tests
(tests/cobol_mainframe/test_det_mq.py) read. The models are tests/equivalence/mq/ggmq.c (the oracle's) and
det/cobolrt/mq/QueueManager.java (the port's); the register's W family records what they assume and refuse.

IBM is the reference: "IBM MQ: MQI calls" (https://www.ibm.com/docs/en/ibm-mq/9.3?topic=reference-calls) for each
call's parameters, and "Reason codes" (https://www.ibm.com/docs/en/ibm-mq/9.3?topic=codes-reason) for each code."""

from __future__ import annotations

# call -> its parameters, in order (IBM's names); every one is passed BY REFERENCE
CALLS: dict[str, tuple[str, ...]] = {
    "MQOPEN": ("Hconn", "ObjDesc", "Options", "Hobj", "CompCode", "Reason"),
    "MQCLOSE": ("Hconn", "Hobj", "Options", "CompCode", "Reason"),
    "MQGET": ("Hconn", "Hobj", "MsgDesc", "GetMsgOpts", "BufferLength", "Buffer", "DataLength", "CompCode", "Reason"),
    "MQPUT": ("Hconn", "Hobj", "MsgDesc", "PutMsgOpts", "BufferLength", "Buffer", "CompCode", "Reason"),
    "MQPUT1": ("Hconn", "ObjDesc", "MsgDesc", "PutMsgOpts", "BufferLength", "Buffer", "CompCode", "Reason"),
}

# the MQLONG parameters (MQHCONN / MQHOBJ / MQLONG): a fullword binary item, big-endian on z/OS and in GnuCOBOL's
# BINARY under -std=ibm -- a COMP-5 item is native on the oracle (little-endian), so it is refused (det/mq.py)
MQLONG = frozenset({"Hconn", "Hobj", "Options", "CompCode", "Reason", "BufferLength", "DataLength"})

# the MQI calls not modelled, each refused by name (a translation hole; the oracle has no symbol for them)
UNMODELLED: dict[str, str] = {
    "MQCONN": "batch MQ: a connection of its own (W6)",
    "MQCONNX": "batch MQ: a connection of its own (W6)",
    "MQDISC": "batch MQ: a connection of its own (W6)",
    "MQBEGIN": "a unit of work of MQ's own (W5: the CICS task's is modelled)",
    "MQCMIT": "a unit of work of MQ's own (W5: the CICS task's is modelled)",
    "MQBACK": "a unit of work of MQ's own (W5: the CICS task's is modelled)",
    "MQINQ": "object attributes (MQINQ / MQSET)",
    "MQSET": "object attributes (MQINQ / MQSET)",
    "MQSUB": "publish / subscribe",
    "MQSUBRQ": "publish / subscribe",
    "MQCB": "asynchronous consumption",
    "MQCTL": "asynchronous consumption",
    "MQSTAT": "asynchronous put status",
    "MQCRTMH": "message handles and properties",
    "MQDLTMH": "message handles and properties",
    "MQSETMP": "message handles and properties",
    "MQINQMP": "message handles and properties",
    "MQDLTMP": "message handles and properties",
    "MQMHBUF": "message handles and properties",
    "MQBUFMH": "message handles and properties",
}

# the completion and reason codes the models return (IBM MQ "Reason codes"); anything else is a refusal
COMPLETION = {"MQCC_OK": 0, "MQCC_WARNING": 1, "MQCC_FAILED": 2}
REASONS = {
    0: "MQRC_NONE",
    2005: "MQRC_BUFFER_LENGTH_ERROR",
    2019: "MQRC_HOBJ_ERROR",
    2033: "MQRC_NO_MSG_AVAILABLE",
    2037: "MQRC_NOT_OPEN_FOR_INPUT",
    2039: "MQRC_NOT_OPEN_FOR_OUTPUT",
    2046: "MQRC_OPTIONS_ERROR",
    2079: "MQRC_TRUNCATED_MSG_ACCEPTED",
    2080: "MQRC_TRUNCATED_MSG_FAILED",
    2085: "MQRC_UNKNOWN_OBJECT_NAME",
}
WARNINGS = frozenset({2079, 2080})  # MQCC_WARNING; every other non-zero reason here is MQCC_FAILED

# IBM's documented lengths of the structures the stand-in copybooks declare (version 1 each: det/copy/CMQ*.cpy)
LENGTHS = {"CMQODV": 168, "CMQMDV": 324, "CMQGMOV": 72, "CMQPMOV": 128, "CMQTML": 684}
# the stand-ins GitGalaxy writes (never IBM's members): shipped only with the model behind them (owner, 2026-10-11)
STAND_INS = ("CMQV", "CMQODV", "CMQMDV", "CMQGMOV", "CMQPMOV", "CMQTML")
