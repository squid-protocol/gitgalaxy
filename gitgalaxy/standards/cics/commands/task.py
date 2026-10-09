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
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    EngineFacts,
    Fact,
    Outcome,
    Refusal,
    RuntimeRefusal,
    one_of,
    required,
)

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
    register="X30",
    options={
        "COUNTER": Arg("name", width=16),
        "POOL": Arg("name", width=8),
        "VALUE": Arg("area_out", width=4),
        "RESP": RESP_OPTIONS["RESP"],
        "RESP2": RESP_OPTIONS["RESP2"],
        **_NOHANDLE,
    },
    groups=(required("VALUE", msg="GET COUNTER without VALUE"),),
    # X30: IBM's GET COUNTER page lists no NOTFND; "Named counter not found" is INVREQ RESP2 201
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("VALUE",)),
        Outcome("INVREQ", 201, "Named counter not found"),
        Outcome("INVREQ", 403, "POOL contains invalid characters or embedded spaces"),
        Outcome("INVREQ", 404, "COUNTER contains invalid characters or embedded spaces"),
    ),
    state=("handle_table",),
)

# #4415 slice 2, register X29: QUERY COUNTER reads a named counter's value without changing it. IBM (EXEC CICS QUERY COUNTER
# and QUERY DCOUNTER): INVREQ RESP2 201 "Named counter not found", LENGERR (RESP2 1-3) for a value beyond a fullword
# (refused by name: the region's counters are fullwords); MINIMUM / MAXIMUM (the counter's limits are not stated by the
# run) and NOSUSPEND (BUSY needs a coupling facility) are refused
QUERY_COUNTER = Command(
    key="QUERY COUNTER",
    ibm=ibm("EXEC CICS QUERY COUNTER and QUERY DCOUNTER", "summary-query-counter-query-dcounter"),
    status="modelled",
    register="X29",
    options={
        "COUNTER": Arg("name", width=16),
        "POOL": Arg("name", width=8),
        "VALUE": Arg("area_out", width=4),
        "RESP": RESP_OPTIONS["RESP"],
        "RESP2": RESP_OPTIONS["RESP2"],
        **_NOHANDLE,
    },
    default_refusal=Refusal("only the counter's value is modelled (the region states no limits)", "X29"),
    groups=(required("VALUE", msg="QUERY COUNTER without VALUE"),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("VALUE",)),
        Outcome("INVREQ", 201, "Named counter not found"),
        Outcome("INVREQ", 403, "POOL contains invalid characters or embedded spaces"),
        Outcome("INVREQ", 404, "COUNTER contains invalid characters or embedded spaces"),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a counter value beyond a fullword: IBM's LENGERR (RESP2 1-3) returns the low-order 32 bits, not modelled",
            "X29",
            java="QUERY COUNTER of a value beyond a fullword",
            c="QUERY COUNTER of a value beyond a fullword",
        ),
    ),
    state=("handle_table",),
)

# #4270 named counters, register X30. IBM (EXEC CICS DEFINE COUNTER and DEFINE DCOUNTER): VALUE "If you omit both the VALUE
# and MINIMUM parameters, the named counter is created with an initial value of zero"; INVREQ RESP2 202 "Duplicate counter
# name. A named counter of this name already exists" (the page lists no DUPREC), 403 / 404 / 406. MINIMUM / MAXIMUM (the
# default limits are "low-values" / "high values", whose signed reading IBM does not state), NOSUSPEND (BUSY needs a coupling
# facility structure) and DCOUNTER (unsigned doublewords) are refused; so is a VALUE below zero (at run time).
DEFINE_COUNTER = Command(
    key="DEFINE COUNTER",
    ibm=ibm("EXEC CICS DEFINE COUNTER and DEFINE DCOUNTER", "summary-define-counter-define-dcounter"),
    status="modelled",
    register="X30",
    options={
        "COUNTER": Arg("name", width=16),
        "POOL": Arg("name", width=8),
        "VALUE": Arg("value"),
        "RESP": RESP_OPTIONS["RESP"],
        "RESP2": RESP_OPTIONS["RESP2"],
        **_NOHANDLE,
    },
    default_refusal=Refusal(
        "only a fullword counter with the default limits is modelled (the region states none)", "X30"
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 202, "Duplicate counter name. A named counter of this name already exists"),
        Outcome("INVREQ", 403, "POOL contains invalid characters or embedded spaces"),
        Outcome("INVREQ", 404, "COUNTER contains invalid characters or embedded spaces"),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a VALUE below zero: the default minimum is low-values and IBM does not state how it reads as a signed value",
            "X30",
            java="DEFINE COUNTER with a VALUE below zero",
            c="DEFINE COUNTER with a VALUE below zero",
        ),
        RuntimeRefusal(
            "a counter name of blanks only: IBM states the character rules, not an empty name",
            "X30",
            java="a named counter with a blank name",
            c="a named counter with a blank name",
        ),
    ),
    state=("handle_table",),
)

DELETE_COUNTER = Command(
    key="DELETE COUNTER",
    ibm=ibm("EXEC CICS DELETE COUNTER and DELETE DCOUNTER", "summary-delete-counter-delete-dcounter"),
    status="modelled",
    register="X30",
    options={
        "COUNTER": Arg("name", width=16),
        "POOL": Arg("name", width=8),
        "RESP": RESP_OPTIONS["RESP"],
        "RESP2": RESP_OPTIONS["RESP2"],
        **_NOHANDLE,
    },
    default_refusal=Refusal("only a fullword counter is modelled", "X30"),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 201, "Named counter not found"),
        Outcome("INVREQ", 403, "POOL contains invalid characters or embedded spaces"),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a counter name of blanks only: IBM states the character rules, not an empty name",
            "X30",
            java="a named counter with a blank name",
            c="a named counter with a blank name",
        ),
    ),
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

# #4415 slice 2, register X29: INQUIRE ASSOCIATION, the origin data of the task's own association data (CBSA BNK1CRA). IBM
# (CICS SPI command INQUIRE ASSOCIATION) lists TASKIDERR RESP2 1 (the task is not found), NOTAUTH RESP2 100 and INVREQ
# RESP2 2 ("The command was specified with no arguments": a command with no origin option is refused, the sentence does
# not say whether ASSOCIATION alone is "no arguments"). Only the task's own number (EIBTASKN) is modelled: the task
# exists, no security is checked, and a task number the region does not state is refused. The five origin values are
# facts whoever runs the task states: IBM's pages do not say what a terminal-started task's origin holds
_OD_AREA = Arg("area_out", width=8)
_ORIGIN_OPTIONS = ("ODAPPLID", "ODUSERID", "ODFACILNAME", "ODNETWORKID", "ODFACILTYPE")
INQUIRE_ASSOCIATION = Command(
    key="INQUIRE ASSOCIATION",
    ibm=ibm("CICS SPI command INQUIRE ASSOCIATION", "commands-inquire-association"),
    status="modelled",
    register="X29",
    options={
        "ASSOCIATION": Arg("value"),  # EIBTASKN only (Cics.command): IBM gives no representation for the 4 bytes
        "ODAPPLID": _OD_AREA,
        "ODUSERID": _OD_AREA,
        "ODFACILNAME": _OD_AREA,
        "ODNETWORKID": _OD_AREA,
        "ODFACILTYPE": Arg("area_out", width=4, binary=True),  # a CVDA (DFHVALUE name numbers: det/cvda.py)
        **RESP_OPTIONS,
    },
    default_refusal=Refusal(
        "only the origin data of the association is modelled (no corpus program asks for more)", "X29"
    ),
    groups=(required("ASSOCIATION", msg="INQUIRE ASSOCIATION without ASSOCIATION"),),
    outcomes=(Outcome("NORMAL", 0, "", writes=_ORIGIN_OPTIONS),),
    facts=(
        Fact(
            "origin",
            java="withOrigin",
            env="GGCICS_ORIGIN",
            region_default=None,
            options=_ORIGIN_OPTIONS,
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "the task's origin data is not stated for the task",
            "X29",
            java="the task's origin data is not stated (withOrigin)",
            c="INQUIRE ASSOCIATION: the origin data is not stated for this task",
        ),
    ),
    state=("handle_table",),
)

# #4270 zECS, register X32: INQUIRE URIMAP's browse (START / NEXT / END) and WRITE OPERATOR, the two commands that stop zECS's
# ZECSPLT. IBM (CICS SPI command INQUIRE URIMAP; "Browsing resource definitions"): the browse lists "all the URIMAP
# definitions installed in the region"; END RESP2 2 "There are no more resource definitions of this type"; ILLOGIC RESP2 1
# "a START command when a browse of this resource type is already in progress" (the page words a NEXT or END with no browse
# as ILLOGIC too, with no RESP2 of its own: refused at run time). URIMAP returns the 8-character name, PATH 255 characters,
# TRANSACTION 4. IBM states neither the browse order nor the padding of a short value nor what a data area holds after END:
# the order is a fact whoever runs the task states (the installed definitions, in the region's order), a value is padded
# with blanks, and the areas are left alone on any condition. The direct form (URIMAP(name) without a browse option, NOTFND
# RESP2 3) and every other attribute (HOST, SCHEME, USAGE ...) are refused: no corpus program asks for them
INQUIRE_URIMAP = Command(
    key="INQUIRE URIMAP",
    ibm=ibm("CICS SPI command INQUIRE URIMAP", "commands-inquire-urimap"),
    status="modelled",
    register="X32",
    options={
        "URIMAP": Arg("area_out", width=8),
        "PATH": Arg("area_out", width=255),
        "TRANSACTION": Arg("area_out", width=4),
        "START": Arg("flag"),
        "NEXT": Arg("flag"),
        "END": Arg("flag"),
        **RESP_OPTIONS,
    },
    default_refusal=Refusal(
        "only the URIMAP's name, PATH and TRANSACTION are modelled (no corpus program asks for more)", "X32"
    ),
    groups=(
        one_of("START", "NEXT", "END", msg="INQUIRE URIMAP without START, NEXT or END: only the browse is modelled"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("URIMAP", "PATH", "TRANSACTION")),
        Outcome(
            "ILLOGIC", 1, "a START when a browse of this resource type is already in progress", raised_by=("START",)
        ),
        Outcome("END", 2, "There are no more resource definitions of this type", raised_by=("NEXT",)),
    ),
    facts=(
        Fact(
            "urimaps",
            java="withUrimaps",
            env="GGCICS_URIMAPS",
            region_default=None,
            options=("URIMAP", "PATH", "TRANSACTION"),
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "the installed URIMAP definitions are not stated for the task",
            "X32",
            java="the installed URIMAP definitions are not stated (withUrimaps)",
            c="INQUIRE URIMAP: the installed URIMAP definitions are not stated for this task",
        ),
        RuntimeRefusal(
            "a NEXT or END with no browse started: IBM's ILLOGIC page gives that case no RESP2 of its own",
            "X32",
            java="INQUIRE URIMAP NEXT or END with no browse started",
            c="INQUIRE URIMAP NEXT or END with no browse started",
        ),
    ),
    state=("handle_table",),
)

# WRITE OPERATOR (EXEC CICS WRITE OPERATOR): a message to the system console; TEXTLENGTH "is required only for C and C++"
# (a COBOL program names a data area, whose length is the text's). IBM's INVREQ RESP2 1-8 are for values the program gives
# (TEXTLENGTH, NUMROUTES, ROUTECODES, MAXLENGTH, TIMEOUT, ACTION, CONSNAME), none of which is modelled; ERROR (the MVS WTO
# failed) cannot arise in this region. A text IBM reformats (DFHnnnn / DFHaannnn: a CICS message) or splits into lines (over
# 113 characters) is refused: only the plain single-line message is modelled
WRITE_OPERATOR = Command(
    key="WRITE OPERATOR",
    ibm=ibm("EXEC CICS WRITE OPERATOR", "summary-write-operator"),
    status="modelled",
    register="X32",
    options={"TEXT": Arg("area_in"), **RESP_OPTIONS},
    default_refusal=Refusal(
        "only the plain message to the console is modelled (no routing, reply, action or console name)", "X32"
    ),
    groups=(required("TEXT", msg="WRITE OPERATOR without TEXT"),),
    outcomes=(Outcome("NORMAL", 0, ""),),
    runtime_refusals=(
        RuntimeRefusal(
            "a text over 113 characters, or one that begins DFHnnnn / DFHaannnn: IBM reformats it, not modelled",
            "X32",
            java="WRITE OPERATOR text IBM reformats",
            c="WRITE OPERATOR text IBM reformats",
        ),
    ),
    state=("handle_table",),
)

COMMANDS = (
    ENQ,
    DEQ,
    DELAY,
    GET_COUNTER,
    QUERY_COUNTER,
    DEFINE_COUNTER,
    DELETE_COUNTER,
    ASKTIME,
    FORMATTIME,
    INQUIRE_PROGRAM,
    SYNCPOINT,
    SYNCPOINT_ROLLBACK,
    BIF_DEEDIT,
    INQUIRE_TERMINAL,
    SET_TERMINAL,
    INQUIRE_ASSOCIATION,
    INQUIRE_URIMAP,
    WRITE_OPERATOR,
)
