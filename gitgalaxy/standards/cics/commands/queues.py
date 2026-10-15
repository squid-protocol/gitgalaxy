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

A refused option shows no reason but SYSID's and READQ TS SET's (the reasons the old global table gave them). MAIN /
AUXILIARY say where CICS keeps an item, not what it holds; NOSUSPEND: one task, a queue never waits."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, SET_POINTER, SYSID_REMOTE, ibm
from gitgalaxy.standards.cics.model import Arg, Command, EngineFacts, Outcome, Refusal, one_of, required

_QUEUE = {"TS": Arg("flag"), "QUEUE": Arg("name", width=16), "QNAME": Arg("name", width=16)}
_NO_QUEUE = "{} TS without QUEUE / QNAME"  # (det/cics.py Cics.ts_queue)
_QIDERR = Outcome("QIDERR", None, "the queue does not exist")

WRITEQ_TD = Command(
    key="WRITEQ TD",
    ibm=ibm("EXEC CICS WRITEQ TD", "summary-writeq-td"),
    status="modelled",
    options={"QUEUE": Arg("name", width=4), "FROM": Arg("area_in"), "LENGTH": Arg("value"), **RESP_OPTIONS},
    refused={"SYSID": SYSID_REMOTE},
    outcomes=(Outcome("NORMAL", 0, ""), Outcome("QIDERR", None, "the CSD does not define the queue")),
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
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        "ITEM": Arg("area_inout", width=2, binary=True),
        "NUMITEMS": Arg("area_out", width=2, binary=True),
        "NEXT": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={"SYSID": SYSID_REMOTE, "SET": SET_POINTER},
    groups=(one_of("QUEUE", "QNAME", msg=_NO_QUEUE.format("READQ")),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "LENGTH", "ITEM", "NUMITEMS")),
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

_TD_NOSUSPEND = Refusal(
    "a queue another task is writing (QBUSY, a wait) is not modelled: one task, a queue never waits", "X57"
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
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        **RESP_OPTIONS,
    },
    refused={"SYSID": SYSID_REMOTE, "SET": SET_POINTER, "NOSUSPEND": _TD_NOSUSPEND},
    groups=(required("QUEUE", msg="READQ TD without QUEUE"), required("INTO", msg="READQ TD without INTO")),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "LENGTH")),
        Outcome("QZERO", None, "the queue is empty"),
        Outcome("QIDERR", None, "the CSD does not define the queue"),
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
# extrapartition queue, QIDERR (44) for one CICS cannot find. LOCKED / DISABLED / NOTAUTH / ISCINVREQ / SYSIDERR do not arise here.
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
        Outcome("INVREQ", None, "the queue is extrapartition"),
    ),
    state=("handle_table",),
    engine=EngineFacts(resource="QUEUE", access="delete"),
)

COMMANDS = (WRITEQ_TD, WRITEQ_TS, READQ_TS, DELETEQ_TS, READQ_TD, DELETEQ_TD)
