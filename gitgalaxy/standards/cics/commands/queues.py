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
program's own bytes in the region's code page (#4528).

A refused option shows no reason but SYSID's and READQ TS SET's (the reasons the old global table gave them). MAIN /
AUXILIARY say where CICS keeps an item, not what it holds; NOSUSPEND: one task, a queue never waits."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, SET_POINTER, SYSID_REMOTE, ibm
from gitgalaxy.standards.cics.model import Arg, Command, EngineFacts, Outcome, one_of

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

COMMANDS = (WRITEQ_TD, WRITEQ_TS, READQ_TS)
