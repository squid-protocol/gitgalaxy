# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 slice 2 (#4578): interval control -- START / RETRIEVE / CANCEL -- and RUN TRANSID, register X18.

The order in which START's out-of-range checks run is behaviour (X18 ASSUMED), not a table: it stays code in both
runtimes, and the crucible proves it (cics_command_spec.md section 2.3)."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import POINTER, REMOTE, RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    EngineFacts,
    Impl,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    required,
    requires,
)

_TRANSID = Arg("name", width=4)
_DATA_OPTIONS = ("RTRANSID", "RTERMID", "QUEUE")  # the values a started task RETRIEVEs

START = Command(
    key="START",
    ibm=ibm("EXEC CICS START", "summary-start"),
    status="modelled",
    register="X18",
    event="START",
    options={
        "TRANSID": _TRANSID,
        "TERMID": Arg("name", width=4),
        "REQID": Arg("name", width=8),
        "FROM": Arg("area_in"),
        "LENGTH": Arg("value"),
        "FLENGTH": Arg("value"),
        "INTERVAL": Arg("hhmmss"),  # none of INTERVAL / TIME / AFTER / AT: INTERVAL(0)
        "TIME": Arg("hhmmss"),
        "AFTER": Arg("flag"),
        "AT": Arg("flag"),
        "HOURS": Arg("value"),
        "MINUTES": Arg("value"),
        "SECONDS": Arg("value"),
        "PROTECT": Arg("flag"),
        "RTRANSID": Arg("name", width=4),
        "RTERMID": Arg("name", width=4),
        "QUEUE": Arg("name", width=8),
        **RESP_OPTIONS,
    },
    refused={
        "CHANNEL": Refusal(
            "START CHANNEL: a started task's channel is not modelled (no corpus program uses it)", "X18", whole=True
        ),
        "SYSID": Refusal(REMOTE, "X18"),
        "NOCHECK": Refusal(
            "less error checking for a START on a remote system is not modelled (no corpus program uses it)", "X18"
        ),
        "USERID": Refusal("a started task's user (surrogate security) is not modelled", "X18"),
        "ATTACH": Refusal("a START that keeps its data after RETRIEVE is not modelled", "X18"),
        "BREXIT": Refusal("the 3270 bridge is not modelled", "X18"),
        "FMH": Refusal("function management headers are not modelled", "X18"),
    },
    groups=(
        required("TRANSID", msg="START without TRANSID"),
        at_most_one("INTERVAL", "TIME", "AFTER", "AT", msg="START {}: one expiry option"),
        requires(
            ("HOURS", "MINUTES", "SECONDS"),
            any_of=("AFTER", "AT"),
            both_ways=True,
            msg="START {} {}: HOURS / MINUTES / SECONDS go with AFTER / AT",
        ),
        at_most_one("LENGTH", "FLENGTH", msg="{} and {} together"),
        requires(("LENGTH", "FLENGTH"), any_of=("FROM",), msg="START LENGTH without FROM"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 4, "hours out of range (HOURS, or INTERVAL / TIME's hh)"),
        Outcome("INVREQ", 5, "minutes out of range (MINUTES, or mm)"),
        Outcome("INVREQ", 6, "seconds out of range (SECONDS, or ss)"),
        Outcome("LENGERR", None, "LENGTH is not greater than zero, or past 32763"),
        Outcome("TRANSIDERR", None, "the transaction is not defined"),
        Outcome("TERMIDERR", None, "the terminal is not defined"),
        Outcome(
            "IOERR",
            None,
            "A START operation uses a REQID name that exists. This condition occurs only when the FROM option is also"
            " used",
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a REQID that exists, reused other than as this task's own with FROM",
            "X18",
            java=" of a request that exists",
            c="START REQID(%s) of a request that exists, %s",
        ),
        RuntimeRefusal("a LENGTH past FROM's end (X6)", "X18", java="START LENGTH "),
    ),
    state=("interval_requests", "virtual_clock", "handle_table"),
    engine=EngineFacts(task_verb="START", target_option="TRANSID", handle_option="REQID", channel_option="TRANSID"),
    impl=Impl(translator="Cics.start", java="startRequest", c="GGCSTRT", harness="_interval_command"),
)

RETRIEVE = Command(
    key="RETRIEVE",
    ibm=ibm("EXEC CICS RETRIEVE", "summary-retrieve"),
    status="modelled",
    register="X18",
    event="RETRIEVE",
    options={
        "INTO": Arg("area_out"),
        # "On completion of the retrieval operation, the data area is set to the original length of the data"
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        "FLENGTH": Arg("area_inout", width=4, binary=True, inout_unless_literal=True),
        "RTRANSID": Arg("area_out", width=4),
        "RTERMID": Arg("area_out", width=4),
        "QUEUE": Arg("area_out", width=8),
        **RESP_OPTIONS,
    },
    refused={
        "SET": Refusal(POINTER, "X18"),
        "WAIT": Refusal(
            "a RETRIEVE waiting for START data still to expire is not modelled (one task runs at a time)", "X18"
        ),
    },
    groups=(
        at_most_one("LENGTH", "FLENGTH", msg="{} and {} together"),
        # INTO, unless the command asks only for RTRANSID / RTERMID / QUEUE (and then no LENGTH)
        requires(("LENGTH", "FLENGTH"), any_of=("INTO",), msg="RETRIEVE without INTO"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "LENGTH", "FLENGTH", *_DATA_OPTIONS)),
        Outcome(
            "LENGERR",
            None,
            "the data is longer than INTO takes: truncated",
            writes=("INTO", "LENGTH", "FLENGTH", *_DATA_OPTIONS),
        ),
        Outcome("ENDDATA", None, "no data record is left (also for a task no START started)"),
        Outcome(
            "ENVDEFERR",
            None,
            "a RETRIEVE command specifies an option not specified by the corresponding START command",
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a RETRIEVE in a RUN TRANSID child task",
            "X18",
            java="RETRIEVE in a RUN TRANSID child task: not documented",
            c="RETRIEVE in a RUN TRANSID child task: not documented",
        ),
        RuntimeRefusal(
            "a RETRIEVE after ENVDEFERR: whether the record was used up",
            "X18",
            java="RETRIEVE after ENVDEFERR: whether the record is still there is ",
            c="RETRIEVE after ENVDEFERR: whether the record is still there is not documented",
        ),
        RuntimeRefusal(
            "RETRIEVE INTO for a record whose START gave no FROM: whether that is ENVDEFERR",
            "X18",
            java="RETRIEVE INTO the record of a START with no FROM: whether that ",
            c="RETRIEVE INTO the record of a START with no FROM: whether that is ENVDEFERR is not documented",
        ),
    ),
    state=("interval_requests", "handle_table"),
    engine=EngineFacts(task_verb="RETRIEVE"),
    impl=Impl(translator="Cics.retrieve", java="retrieve", c="GGCRTRV", harness="_interval_command"),
)

_CANCEL_ONLY_REQID = Refusal("CANCEL of a TRANSID / an activity: only CANCEL REQID is modelled", "X18", whole=True)
CANCEL = Command(
    key="CANCEL",
    ibm=ibm("EXEC CICS CANCEL", "summary-cancel"),
    status="modelled",
    register="X18",
    event="CANCEL",
    options={"REQID": Arg("name", width=8), **RESP_OPTIONS},
    refused=dict.fromkeys(("TRANSID", "SYSID", "ACTIVITY", "ACQACTIVITY", "ACQPROCESS"), _CANCEL_ONLY_REQID),
    default_refusal=_CANCEL_ONLY_REQID,
    groups=(required("REQID", msg="CANCEL without REQID: only CANCEL REQID is modelled"),),
    outcomes=(
        Outcome("NORMAL", 0, "the request has not expired: it is cancelled"),
        Outcome("NOTFND", None, "fails to match an unexpired interval control command"),
    ),
    state=("interval_requests", "virtual_clock", "handle_table"),
    engine=EngineFacts(task_verb="CANCEL", target_option="TRANSID", handle_option="REQID"),
    impl=Impl(translator="Cics.cancel", java="cancel", c="GGCCNCL", harness="_interval_command"),
)

RUN = Command(
    key="RUN",
    ibm=ibm("EXEC CICS RUN TRANSID", "summary-run-transid"),
    status="modelled",
    register="X18",
    event="RUN",
    options={"TRANSID": _TRANSID, "CHILD": Arg("area_out", width=16), **RESP_OPTIONS},
    refused={
        "CHANNEL": Refusal(
            "RUN CHANNEL: the child task's copy of the channel is not modelled (#4270: a later slice)",
            "X18",
            whole=True,
        ),
    },
    groups=(
        required("TRANSID", msg="RUN without TRANSID / CHILD"),
        required("CHILD", msg="RUN without TRANSID / CHILD"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("CHILD",)),
        Outcome("TRANSIDERR", 1, "the transaction is not defined"),
    ),
    state=("child_tasks", "handle_table"),
    engine=EngineFacts(task_verb="RUN", target_option="TRANSID", handle_option="CHILD", channel_option="TRANSID"),
    impl=Impl(translator="Cics.run_transid", java="runTransid", c="GGCRUNT", harness="_run_transid"),
)

COMMANDS = (START, RETRIEVE, CANCEL, RUN)
