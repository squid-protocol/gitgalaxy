# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 spec PR 2: the rest of OPTIONS -- ENQ / DEQ / DELAY (one task in the region: nothing waits, a task takes no
time), GET COUNTER, ASKTIME / FORMATTIME, INQUIRE PROGRAM, SYNCPOINT [ROLLBACK] (#4437: NORMAL, the only outcome in
this region, register X3)."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import Arg, Command, EngineFacts, Outcome, required

_NORMAL = Outcome("NORMAL", 0, "")
_NOHANDLE = {"NOHANDLE": Arg("flag")}
# FORMATTIME's date forms (det/cics.py Cics.command)
DATE_FORMS = ("YYYYMMDD", "MMDDYYYY", "DDMMYYYY", "YYMMDD", "MMDDYY", "DDMMYY")
_RESOURCE = {
    "RESOURCE": Arg("area_in"),
    "LENGTH": Arg("value"),
    "TASK": Arg("flag"),
    "UOW": Arg("flag"),
    "MAXLIFETIME": Arg("cvda"),
}

ENQ = Command(
    key="ENQ",
    ibm=ibm("EXEC CICS ENQ", "summary-enq"),
    status="modelled",
    options={**_RESOURCE, "NOSUSPEND": Arg("flag"), **RESP_OPTIONS},
    outcomes=(Outcome("NORMAL", 0, "one task in the region: the resource is never held by another"),),
    engine=EngineFacts(task_verb="ENQ", target_option="RESOURCE"),
)

DEQ = Command(
    key="DEQ",
    ibm=ibm("EXEC CICS DEQ", "summary-deq"),
    status="modelled",
    options={**_RESOURCE, **RESP_OPTIONS},
    outcomes=(_NORMAL,),
    engine=EngineFacts(task_verb="DEQ", target_option="RESOURCE"),
)

DELAY = Command(
    key="DELAY",
    ibm=ibm("EXEC CICS DELAY", "summary-delay"),
    status="modelled",
    options={
        "FOR": Arg("flag"),
        "INTERVAL": Arg("hhmmss"),
        "TIME": Arg("hhmmss"),
        "HOURS": Arg("value"),
        "MINUTES": Arg("value"),
        "SECONDS": Arg("value"),
        "MILLISECS": Arg("value"),
        **RESP_OPTIONS,
    },
    outcomes=(Outcome("NORMAL", 0, "a task takes no time: the delay ends at once"),),
    engine=EngineFacts(task_verb="DELAY", handle_option="REQID"),
)

GET_COUNTER = Command(
    key="GET COUNTER",
    ibm=ibm("EXEC CICS GET COUNTER and GET DCOUNTER", "summary-get-counter-get-dcounter"),
    status="modelled",
    options={
        "COUNTER": Arg("name", width=16),
        "POOL": Arg("name", width=8),
        "VALUE": Arg("area_out", width=4),
        "RESP": RESP_OPTIONS["RESP"],
        **_NOHANDLE,
    },
    groups=(required("VALUE", msg="GET COUNTER without VALUE"),),
    outcomes=(Outcome("NORMAL", 0, "", writes=("VALUE",)), Outcome("NOTFND", None, "the counter is not defined")),
    state=("handle_table",),
)

ASKTIME = Command(
    key="ASKTIME",
    ibm=ibm("EXEC CICS ASKTIME", "summary-asktime"),
    status="modelled",
    options={"ABSTIME": Arg("area_out", width=8), **_NOHANDLE},
    outcomes=(Outcome("NORMAL", 0, "", writes=("ABSTIME",)),),
    state=("virtual_clock",),
)

FORMATTIME = Command(
    key="FORMATTIME",
    ibm=ibm("EXEC CICS FORMATTIME", "summary-formattime"),
    status="modelled",
    options={
        "ABSTIME": Arg("area_in", width=8),
        **{f: Arg("area_out") for f in DATE_FORMS},
        "TIME": Arg("area_out", width=6),
        "DATESEP": Arg("value"),  # no value: IBM's default '/'
        "TIMESEP": Arg("value"),  # no value: IBM's default ':'
        **_NOHANDLE,
    },
    outcomes=(Outcome("NORMAL", 0, "", writes=(*DATE_FORMS, "TIME")),),
)

INQUIRE_PROGRAM = Command(
    key="INQUIRE PROGRAM",
    ibm=ibm("CICS SPI command INQUIRE PROGRAM", "commands-inquire-program"),
    status="modelled",
    options={"PROGRAM": Arg("name", width=8), **RESP_OPTIONS},
    outcomes=(_NORMAL, Outcome("PGMIDERR", None, "the program is not defined")),
    state=("handle_table",),
)

# #4437: RESP / RESP2 written NORMAL (Cics.command). IBM's conditions do not arise in the region the port runs in:
# INVREQ (RESP2 200) needs a program LINKed from a remote system without SYNCONRETURN -- CicsTask refuses a SYNCPOINT
# in a program LINKed from outside the region -- or one defined EXECUTIONSET(DPLSUBSET), which the region does not
# model (oracle_assumptions.md X3); ROLLEDBACK (commit only) needs a remote system that cannot commit
SYNCPOINT = Command(
    key="SYNCPOINT",
    ibm=ibm("EXEC CICS SYNCPOINT", "summary-syncpoint"),
    status="modelled",
    register="X3",
    options={"ROLLBACK": Arg("flag"), **RESP_OPTIONS},
    outcomes=(Outcome("NORMAL", 0, "INVREQ / ROLLEDBACK need a remote system, which the region does not have"),),
)

SYNCPOINT_ROLLBACK = Command(
    key="SYNCPOINT ROLLBACK",
    ibm=ibm("EXEC CICS SYNCPOINT ROLLBACK", "summary-syncpoint-rollback"),
    status="modelled",
    register="X3",
    options=dict(RESP_OPTIONS),
    outcomes=(_NORMAL,),
)

COMMANDS = (ENQ, DEQ, DELAY, GET_COUNTER, ASKTIME, FORMATTIME, INQUIRE_PROGRAM, SYNCPOINT, SYNCPOINT_ROLLBACK)
