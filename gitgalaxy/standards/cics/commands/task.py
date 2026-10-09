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
from gitgalaxy.standards.cics.model import Arg, Command, EngineFacts, Fact, Outcome, Refusal, RuntimeRefusal, required

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
    # #4737: ABSTIME is optional (IBM: ASKTIME "updates the date (EIBDATE) and ... time-of-day clock (EIBTIME) fields in the
    # EIB", which the region keeps as dispatched, X4); NOHANDLE has no condition to suppress: ASKTIME lists none
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
        **RESP_OPTIONS,
    },
    # #4737 (register X28): IBM lists INVREQ RESP2 1 "The ABSTIME value is less than zero or not in packed-decimal
    # format" and RESP2 2 (invalid STRINGFORMAT CVDA; STRINGFORMAT is not an option here, so it is refused by name).
    # "Not packed-decimal" is the declared storage's business (the port reads ABSTIME by its declared usage)
    outcomes=(
        Outcome("NORMAL", 0, "", writes=(*DATE_FORMS, "TIME")),
        Outcome("INVREQ", 1, "ABSTIME is less than zero"),
    ),
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

# #4415 slice 1, register X26. IBM (EXEC CICS BIF DEEDIT) lists LENGERR "if the LENGTH value is less than 1" and no
# RESP2 value; what it leaves out is refused by name at run time (a field with no digit left, a character beyond 7-bit
# ASCII, a LENGTH past the field)
BIF_DEEDIT = Command(
    key="BIF DEEDIT",
    ibm=ibm("EXEC CICS BIF DEEDIT", "summary-bif-deedit"),
    status="modelled",
    register="X26",
    options={"FIELD": Arg("area_inout"), "LENGTH": Arg("value"), **RESP_OPTIONS},
    groups=(required("FIELD", msg="BIF DEEDIT without FIELD"),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("FIELD",)),
        Outcome("LENGERR", None, "The LENGTH value is less than 1 (IBM lists no RESP2)"),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a field with no digit left: IBM does not say what it becomes",
            "X26",
            java="BIF DEEDIT of a field with no digit left",
            c="BIF DEEDIT of a field with no digit left",
        ),
        RuntimeRefusal(
            "a character beyond 7-bit ASCII in the field",
            "X26",
            java="beyond 7-bit ASCII:",
            c="BIF DEEDIT of a byte beyond 7-bit ASCII",
        ),
    ),
)

# #4415 slice 1, register X26: the one terminal the task has. The terminal's UCTRANST is a fact whoever runs the task
# states (from the TYPETERM's UCTRAN); SET changes the task's view; a terminal RECEIVE after a SET is refused
_TERMINAL_REST = Refusal("only the terminal's translation state is modelled (no corpus program asks for more)", "X26")
INQUIRE_TERMINAL = Command(
    key="INQUIRE TERMINAL",
    ibm=ibm("CICS SPI command INQUIRE TERMINAL", "commands-inquire-terminal"),
    status="modelled",
    register="X26",
    options={"TERMINAL": Arg("name", width=4), "UCTRANST": Arg("area_out", width=4, binary=True), **RESP_OPTIONS},
    default_refusal=_TERMINAL_REST,
    groups=(required("TERMINAL", msg="INQUIRE TERMINAL without TERMINAL"),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("UCTRANST",)),
        Outcome("TERMIDERR", 1, "The named terminal cannot be found"),
    ),
    facts=(
        Fact(
            "uctranst",
            java="withUctranst",
            env="GGCICS_UCTRANST",
            region_default=None,
            options=("UCTRANST",),
            values=("UCTRAN", "NOUCTRAN", "TRANIDONLY"),
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "the terminal's UCTRANST is not stated for the task",
            "X26",
            java="the terminal's UCTRANST is not stated (withUctranst)",
            c="INQUIRE TERMINAL UCTRANST: not stated for this task",
        ),
        RuntimeRefusal(
            "the UCTRANST of a terminal other than the task's",
            "X26",
            java="not the task's terminal",
            c="UCTRANST of a terminal other than the task's",
        ),
    ),
    state=("terminal", "handle_table"),
)

SET_TERMINAL = Command(
    key="SET TERMINAL",
    ibm=ibm("CICS SPI command SET TERMINAL", "commands-set-terminal"),
    status="modelled",
    register="X26",
    options={"TERMINAL": Arg("name", width=4), "UCTRANST": Arg("cvda"), **RESP_OPTIONS},
    default_refusal=_TERMINAL_REST,
    groups=(required("TERMINAL", msg="SET TERMINAL without TERMINAL"),),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 43, "Invalid UCTRANST CVDA", raised_by=("UCTRANST",)),
        Outcome("TERMIDERR", 23, "The named terminal cannot be found"),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a terminal RECEIVE after SET TERMINAL UCTRANST: IBM does not say when the change takes effect",
            "X26",
            java="a terminal RECEIVE after SET TERMINAL UCTRANST",
            c="a terminal RECEIVE after SET TERMINAL UCTRANST",
        ),
    ),
    state=("terminal", "handle_table"),
)

COMMANDS = (
    ENQ,
    DEQ,
    DELAY,
    GET_COUNTER,
    ASKTIME,
    FORMATTIME,
    INQUIRE_PROGRAM,
    SYNCPOINT,
    SYNCPOINT_ROLLBACK,
    BIF_DEEDIT,
    INQUIRE_TERMINAL,
    SET_TERMINAL,
)
