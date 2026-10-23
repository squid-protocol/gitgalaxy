# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 spec PR 2: queues -- WRITEQ TD, WRITEQ TS / READQ TS (det/cics.py Cics.command, Cics.ts_queue), each item the
program's own bytes in the region's code page (#4528). #5079, register X57: READQ TD / DELETEQ TD on an intrapartition
queue (a first-in first-out queue the task's own WRITEQ TDs fill).

A refused option shows no reason but SYSID's and READQ TD SET's (the reasons the old global table gave them). MAIN /
AUXILIARY say where CICS keeps an item, not what it holds; NOSUSPEND: one task, a queue never waits."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, SYSID_REMOTE, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    EngineFacts,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    one_of,
    required,
    requires,
)

_QUEUE = {"TS": Arg("flag"), "QUEUE": Arg("name", width=16), "QNAME": Arg("name", width=16)}
_NO_QUEUE = "{} TS without QUEUE / QNAME"  # (det/cics.py Cics.ts_queue)
_QIDERR = Outcome("QIDERR", None, "the queue does not exist")

WRITEQ_TD = Command(
    key="WRITEQ TD",
    ibm=ibm("EXEC CICS WRITEQ TD", "summary-writeq-td"),
    status="modelled",
    options={"QUEUE": Arg("name", width=4), "FROM": Arg("area_in"), "LENGTH": Arg("value"), **RESP_OPTIONS},
    refused={"SYSID": SYSID_REMOTE},
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("QIDERR", None, "the CSD does not define the queue"),
        Outcome("NOTOPEN", None, "an extrapartition queue is closed"),  # #5168 (X61)
        Outcome("DISABLED", None, "SET TDQUEUE ENABLESTATUS(DISABLED) left the queue disabled"),  # #5168 round 5 (X66)
        Outcome("INVREQ", None, "an extrapartition queue is open for input"),
    ),
    state=("handle_table",),
    engine=EngineFacts(resource="QUEUE", access="write"),
)

WRITEQ_TS = Command(
    key="WRITEQ TS",
    ibm=ibm("EXEC CICS WRITEQ TS", "summary-writeq-ts"),
    status="modelled",
    options={
        **_QUEUE,
        "FROM": Arg("area_in"),
        "LENGTH": Arg("value"),
        "ITEM": Arg("area_inout", width=2, binary=True),  # the item written (REWRITE: the item replaced)
        "NUMITEMS": Arg("area_out", width=2, binary=True),
        "REWRITE": Arg("flag"),
        "MAIN": Arg("flag"),
        "AUXILIARY": Arg("flag"),
        "NOSUSPEND": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={"SYSID": SYSID_REMOTE},
    groups=(one_of("QUEUE", "QNAME", msg=_NO_QUEUE.format("WRITEQ")),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("ITEM", "NUMITEMS")),
        _QIDERR,
        Outcome("ITEMERR", None, "REWRITE of an item outside the queue"),
        Outcome("LENGERR", None, "LENGTH is outside 1-32763"),
    ),
    state=("handle_table",),
    engine=EngineFacts(resource="QUEUE", access="write"),
)

READQ_TS = Command(
    key="READQ TS",
    ibm=ibm("EXEC CICS READQ TS", "summary-readq-ts"),
    status="modelled",
    options={
        **_QUEUE,
        "INTO": Arg("area_out"),
        "SET": Arg(
            "pointer"
        ),  # #5042 (X58): "valid until the next READQ TS command or the end of task"; LENGTH "must be specified"
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        "ITEM": Arg("area_inout", width=2, binary=True),
        "NUMITEMS": Arg("area_out", width=2, binary=True),
        "NEXT": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={"SYSID": SYSID_REMOTE},
    groups=(
        one_of("QUEUE", "QNAME", msg=_NO_QUEUE.format("READQ")),
        at_most_one("INTO", "SET", msg="READQ TS: INTO and SET are alternatives"),
        requires(
            ("SET",),
            any_of=("LENGTH",),
            msg='READQ TS SET without LENGTH (IBM: "If you specify the SET option, the LENGTH must be specified")',
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "LENGTH", "ITEM", "NUMITEMS")),
        _QIDERR,
        Outcome("ITEMERR", None, "the item is outside the queue (NEXT: past its end)"),
        Outcome("LENGERR", None, "the item is longer than LENGTH: truncated", writes=("INTO", "LENGTH")),
    ),
    state=("handle_table",),
    engine=EngineFacts(resource="QUEUE", access="read"),
)

# #4415 slice 2, register X29. IBM (EXEC CICS DELETEQ TS) lists INVREQ (the queue "was created by CICS internal code,
# or the queue name is all binary zeroes"), ISCINVREQ, LOCKED, NOTAUTH, QIDERR ("the queue can't be found") and
# SYSIDERR, and no RESP2 value for any of them (so 0). Here: one task, local queues, no security, no recoverable queue.
DELETEQ_TS = Command(
    key="DELETEQ TS",
    ibm=ibm("EXEC CICS DELETEQ TS", "summary-deleteq-ts"),
    status="modelled",
    register="X29",
    options={**_QUEUE, **RESP_OPTIONS},
    refused={"SYSID": SYSID_REMOTE},
    groups=(one_of("QUEUE", "QNAME", msg=_NO_QUEUE.format("DELETEQ")),),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        _QIDERR,
        Outcome("INVREQ", None, "the queue name is all binary zeros (IBM lists no RESP2)"),
    ),
    state=("handle_table",),
    engine=EngineFacts(resource="QUEUE", access="delete"),
)

# #5079, register X57. IBM (EXEC CICS READQ TD): a destructive read ("the record is no longer available"); QZERO (23) for an
# empty queue, QIDERR (44) for a queue CICS cannot find, LENGERR (22) for a record longer than LENGTH (truncated), or a
# LENGTH below zero (the queue is then not read) or of zero (the record is still read and lost), LENGTH set to the record's
# own length. An extrapartition queue (READQ: NOTOPEN / IOERR / INVREQ for one opened for output) is refused at run time.
READQ_TD = Command(
    key="READQ TD",
    ibm=ibm("EXEC CICS READQ TD", "summary-readq-td"),
    status="modelled",
    register="X57",
    options={
        "QUEUE": Arg("name", width=4),
        "INTO": Arg("area_out"),
        "SET": Arg("pointer"),  # #5168: "valid until the next READQ TD or the end of the task"
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        "NOSUSPEND": Arg("flag"),  # #5168: QBUSY only as a planned READQ-TD fault (X61)
        **RESP_OPTIONS,
    },
    refused={"SYSID": SYSID_REMOTE},
    groups=(
        required("QUEUE", msg="READQ TD without QUEUE"),
        one_of("INTO", "SET", msg="READQ TD without INTO"),
        at_most_one("INTO", "SET", msg="READQ TD: INTO and SET are alternatives"),
        requires(("SET",), any_of=("LENGTH",), msg="READQ TD SET without LENGTH (the record's length goes there)"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "LENGTH")),
        Outcome("QZERO", None, "the queue is empty"),
        Outcome("QIDERR", None, "the CSD does not define the queue"),
        Outcome("NOTOPEN", None, "an extrapartition queue is closed"),
        Outcome("DISABLED", None, "SET TDQUEUE ENABLESTATUS(DISABLED) left the queue disabled"),  # #5168 round 5 (X66)
        Outcome("INVREQ", None, "an extrapartition queue is open for output"),
        Outcome(
            "LENGERR",
            None,
            "the record is longer than LENGTH (truncated, and lost), or LENGTH is below zero",
            writes=("INTO", "LENGTH"),
        ),
    ),
    state=("handle_table",),
    engine=EngineFacts(resource="QUEUE", access="read"),
)

# #5079, register X57. IBM (EXEC CICS DELETEQ TD): all the data of an intrapartition queue; INVREQ (16) for an
# extrapartition queue, QIDERR (44) for one CICS cannot find. LOCKED / NOTAUTH / ISCINVREQ / SYSIDERR do not arise here.
DELETEQ_TD = Command(
    key="DELETEQ TD",
    ibm=ibm("EXEC CICS DELETEQ TD", "summary-deleteq-td"),
    status="modelled",
    register="X57",
    options={"QUEUE": Arg("name", width=4), **RESP_OPTIONS},
    refused={"SYSID": SYSID_REMOTE},
    groups=(required("QUEUE", msg="DELETEQ TD without QUEUE"),),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("QIDERR", None, "the CSD does not define the queue"),
        Outcome("DISABLED", None, "SET TDQUEUE ENABLESTATUS(DISABLED) left the queue disabled"),  # #5168 round 5 (X66)
        Outcome("INVREQ", None, "the queue is extrapartition"),
    ),
    state=("handle_table",),
    engine=EngineFacts(resource="QUEUE", access="delete"),
)

# #5168 round 3, register X61. IBM (CICS TS 6.x, SET TDQUEUE): OPENSTATUS (extrapartition queues only) says whether the data set "is
# to be opened" (OPEN) or "closed" (CLOSED); QIDERR RESP2 1, INVREQ RESP2 8 (an invalid CVDA), 9 (OPENSTATUS for an intrapartition
# queue), 16 (the JCL DDNAME not found: taken as found). Round 5 (X66): ENABLESTATUS (ENABLED / DISABLED) makes READQ, WRITEQ and
# DELETEQ TD answer DISABLED (84); INVREQ RESP2 10 is an invalid CVDA. Round 7 (X66): TRIGGERLEVEL(n) of an intrapartition queue
# overrides the definition's value (0 turns automatic task initiation off). ATIFACILITY, ATITERMID and the rest are not modelled.
_TDQUEUE_REST = Refusal("only an extrapartition queue's open state and a queue's availability are modelled", "X66")
SET_TDQUEUE = Command(
    key="SET TDQUEUE",
    ibm=ibm("CICS SPI command SET TDQUEUE", "commands-set-tdqueue"),
    status="modelled",
    register="X66",
    options={
        "TDQUEUE": Arg("name", width=4),
        "OPENSTATUS": Arg("cvda"),
        "ENABLESTATUS": Arg("cvda"),
        "TRIGGERLEVEL": Arg("value"),  # #5168 round 7 (X66)
        **RESP_OPTIONS,
    },
    default_refusal=_TDQUEUE_REST,
    groups=(
        required("TDQUEUE", msg="SET TDQUEUE without TDQUEUE"),
        requires(
            ("TDQUEUE",),
            any_of=("OPENSTATUS", "ENABLESTATUS", "TRIGGERLEVEL"),
            msg="SET TDQUEUE without OPENSTATUS, ENABLESTATUS or TRIGGERLEVEL",
        ),
        at_most_one(
            "OPENSTATUS",
            "ENABLESTATUS",
            "TRIGGERLEVEL",
            msg="SET TDQUEUE: OPENSTATUS, ENABLESTATUS and TRIGGERLEVEL together are not modelled",
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("QIDERR", 1, "The queue cannot be found"),
        Outcome("INVREQ", 8, "OPENSTATUS has an invalid CVDA value", raised_by=("OPENSTATUS",)),
        Outcome("INVREQ", 9, "OPENSTATUS was specified for an intrapartition queue", raised_by=("OPENSTATUS",)),
        Outcome("INVREQ", 10, "ENABLESTATUS has an invalid CVDA value", raised_by=("ENABLESTATUS",)),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "SET TRIGGERLEVEL of a queue that is not intrapartition (IBM: intrapartition only; names no condition), or below zero",
            "X66",
            java="SET TDQUEUE TRIGGERLEVEL of a queue that is not intrapartition, or below zero",
            c="SET TDQUEUE TRIGGERLEVEL of a queue that is not intrapartition, or below zero",
        ),
        RuntimeRefusal(
            "an invalid ENABLESTATUS CVDA on a queue the CSD does not define: IBM does not order QIDERR and INVREQ RESP2 10",
            "X66",
            java="SET TDQUEUE ENABLESTATUS with an invalid CVDA on a queue the CSD does not define",
            c="SET TDQUEUE ENABLESTATUS with an invalid CVDA on a queue the CSD does not define",
        ),
        RuntimeRefusal(
            "SET ENABLESTATUS of an INDIRECT or REMOTE queue: a command reaches the target",
            "X66",
            java="SET TDQUEUE ENABLESTATUS of an INDIRECT or REMOTE queue",
            c="SET TDQUEUE ENABLESTATUS of an INDIRECT or REMOTE queue",
        ),
        RuntimeRefusal(
            "SET OPENSTATUS of an INDIRECT or REMOTE queue: IBM names only intrapartition",
            "X61",
            java="SET TDQUEUE OPENSTATUS of an INDIRECT or REMOTE queue",
            c="SET TDQUEUE OPENSTATUS of an INDIRECT or REMOTE queue",
        ),
        RuntimeRefusal(
            "an invalid OPENSTATUS CVDA on a queue that is not extrapartition: IBM does not order the conditions",
            "X61",
            java="SET TDQUEUE OPENSTATUS with an invalid CVDA on a queue that is not extrapartition",
            c="SET TDQUEUE OPENSTATUS with an invalid CVDA on a queue that is not extrapartition",
        ),
        RuntimeRefusal(
            "OPENSTATUS(OPEN) of an extrapartition queue with no TYPEFILE INPUT / OUTPUT",
            "X61",
            java="SET TDQUEUE OPENSTATUS(OPEN) of an extrapartition queue with no TYPEFILE",
            c="SET TDQUEUE OPENSTATUS(OPEN) of an extrapartition queue with no TYPEFILE",
        ),
        RuntimeRefusal(
            "OPENSTATUS(OPEN) of an input queue that has been read: reopening restarts the data set",
            "X61",
            java="SET TDQUEUE OPENSTATUS(OPEN) of an input queue that has been read",
            c="SET TDQUEUE OPENSTATUS(OPEN) of an input queue that has been read",
        ),
    ),
    state=("handle_table",),
)

# IBM (INQUIRE TDQUEUE): OPENSTATUS (extrapartition queues only) is OPEN / CLOSED, or CLOSING / OPENING (never reached: one task),
# NOTAPPLIC "the queue is not extrapartition"; TYPE is EXTRA / INDIRECT / INTRA / REMOTE; QIDERR RESP2 1. No INVREQ is documented.
INQUIRE_TDQUEUE = Command(
    key="INQUIRE TDQUEUE",
    ibm=ibm("CICS SPI command INQUIRE TDQUEUE", "commands-inquire-tdqueue"),
    status="modelled",
    register="X66",
    options={
        "TDQUEUE": Arg("name", width=4),
        "OPENSTATUS": Arg("area_out", width=4, binary=True),
        "TYPE": Arg("area_out", width=4, binary=True),
        "ENABLESTATUS": Arg("area_out", width=4, binary=True),
        "TRIGGERLEVEL": Arg("area_out", width=4, binary=True),  # #5168 round 6 (X66)
        "RECOVSTATUS": Arg("area_out", width=4, binary=True),
        "TRANSID": Arg("area_out", width=4),
        **RESP_OPTIONS,
    },
    default_refusal=_TDQUEUE_REST,
    groups=(
        required("TDQUEUE", msg="INQUIRE TDQUEUE without TDQUEUE"),
        requires(
            ("TDQUEUE",),
            any_of=("OPENSTATUS", "TYPE", "ENABLESTATUS", "TRIGGERLEVEL", "RECOVSTATUS", "TRANSID"),
            msg="INQUIRE TDQUEUE without OPENSTATUS, TYPE, ENABLESTATUS, TRIGGERLEVEL, RECOVSTATUS or TRANSID",
        ),
    ),
    outcomes=(
        Outcome(
            "NORMAL", 0, "", writes=("OPENSTATUS", "TYPE", "ENABLESTATUS", "TRIGGERLEVEL", "RECOVSTATUS", "TRANSID")
        ),
        Outcome("QIDERR", 1, "The named queue cannot be found"),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a queue with no TYPE stated",
            "X61",
            java="INQUIRE TDQUEUE of a queue with no TYPE stated",
            c="INQUIRE TDQUEUE of a queue with no TYPE stated",
        ),
        RuntimeRefusal(
            "TRIGGERLEVEL / TRANSID of a queue that is not intrapartition: IBM names no value",
            "X66",
            java="INQUIRE TDQUEUE TRIGGERLEVEL / TRANSID of a queue that is not intrapartition",
            c="INQUIRE TDQUEUE TRIGGERLEVEL / TRANSID of a queue that is not intrapartition",
        ),
    ),
    state=("handle_table",),
)

COMMANDS = (WRITEQ_TD, WRITEQ_TS, READQ_TS, DELETEQ_TS, READQ_TD, DELETEQ_TD, SET_TDQUEUE, INQUIRE_TDQUEUE)
