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

from gitgalaxy.standards.cics.commands.shared import BOTH_FORMS, REMOTE, RESP_OPTIONS, ibm
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

# #4950: the characters IBM allows in the name of a channel RUN TRANSID / START hands on (EXEC CICS RUN TRANSID,
# CHANNEL: "The acceptable characters are A-Z a-z 0-9 $ @ # . / - _ % & ? ! : | " = \xac , ; < >. Leading and embedded
# blank characters are not permitted"), as both runtimes check them: any other is CHANNELERR RESP2 1
CHANNEL_NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789" + '$@#./-_%&?!:|"=\xac,;<>'
_CHANNEL_ERR = Outcome(
    "CHANNELERR", 1, "the channel name contains an incorrect character or combination", raised_by=("CHANNEL",)
)
_BOTH_BAD = RuntimeRefusal(
    "a transaction not defined together with an incorrect CHANNEL name: which condition IBM raises first is not documented",
    "X18",
    java="of a transaction not defined, with ",
    c="of a transaction not defined, with an incorrect CHANNEL name",
)
_DFH_CHANNEL = RuntimeRefusal(
    "a channel whose name starts DFH: CICS's own (DFHTRANSACTION, the transaction channel) is not modelled",
    "X18",
    java="whose name starts DFH",
    c="a channel named DFH",
)
# START CHANNEL's form (IBM, EXEC CICS START CHANNEL): no expiry, no data options, no REQID
_NOT_WITH_CHANNEL = ("FROM", "LENGTH", "FLENGTH", "INTERVAL", "TIME", "AFTER", "AT", "HOURS", "MINUTES", "SECONDS",
                     "REQID", *("RTRANSID", "RTERMID", "QUEUE"))  # fmt: skip
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
        "CHANNEL": Arg("name", width=16),  # #4950: START CHANNEL, the started task's copy of a channel
        **RESP_OPTIONS,
    },
    refused={
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
        at_most_one("LENGTH", "FLENGTH", msg=BOTH_FORMS),
        requires(("LENGTH", "FLENGTH"), any_of=("FROM",), msg="START LENGTH without FROM"),
        *(at_most_one("CHANNEL", o, msg="START CHANNEL with {}: not START CHANNEL's form") for o in _NOT_WITH_CHANNEL),
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
        _CHANNEL_ERR,
    ),
    runtime_refusals=(
        _DFH_CHANNEL,
        _BOTH_BAD,
        RuntimeRefusal(
            "START CHANNEL naming a channel not in the program's scope (IBM does not say it is created)",
            "X18",
            java=") of a channel not in the ",
            c="START CHANNEL of a channel not in the program's scope",
        ),
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
        # #5042 (X58): "the pointer reference to be set to the address of the retrieved data"; "If you use SET you must also
        # include LENGTH", a data area ("the data area is set to the length of the data")
        "SET": Arg("pointer"),
        # "On completion of the retrieval operation, the data area is set to the original length of the data"
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        "FLENGTH": Arg("area_inout", width=4, binary=True, inout_unless_literal=True),
        "RTRANSID": Arg("area_out", width=4),
        "RTERMID": Arg("area_out", width=4),
        "QUEUE": Arg("area_out", width=8),
        **RESP_OPTIONS,
    },
    refused={
        "WAIT": Refusal(
            "a RETRIEVE waiting for START data still to expire is not modelled (one task runs at a time)", "X18"
        ),
    },
    groups=(
        at_most_one("LENGTH", "FLENGTH", msg=BOTH_FORMS),
        # INTO, unless the command asks only for RTRANSID / RTERMID / QUEUE (and then no LENGTH)
        requires(("LENGTH", "FLENGTH"), any_of=("INTO", "SET"), msg="RETRIEVE without INTO"),
        at_most_one("INTO", "SET", msg="RETRIEVE: INTO and SET are alternatives"),
        requires(
            ("SET",),
            any_of=("LENGTH", "FLENGTH"),
            msg='RETRIEVE SET without LENGTH (IBM: "If you use SET you must also include LENGTH")',
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "LENGTH", "FLENGTH", *_DATA_OPTIONS)),
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

# #4950 (X18, ASSUMED): the region's scheduler. A RUN child is dispatched at its parent's next wait -- a DELAY, or a FETCH
# that waits -- in RUN order, and runs until it ends or waits before its parent resumes (one quasi-reentrant TCB: a
# task keeps control until it waits). A task takes no processor time (X4): a child completes at its dispatch plus its
# own DELAYs; the parent's clock moves by its DELAYs and its waits. #5089: the rule holds at every level -- a child
# that RUNs children of its own dispatches them at its own waits, on its own clock (a grandchild completes at its
# parent's dispatch time plus its own DELAYs, and the child at its parent's plus its own waits). A completion at the very instant the parent resumes
# from a wait of its own is a tie IBM does not order: a FETCH whose answer turns on it is refused.
_CHILD_RUNS = RuntimeRefusal(
    "a RUN TRANSID child's transaction whose program the case does not run", "X18", java="child transaction ",
    c="child transaction %s: its program is not one the case runs",
)  # fmt: skip
_CHILD_RESOURCE = RuntimeRefusal(
    "a dispatched child task's command on a region resource or a terminal (a file, a queue, a START, a counter, SQL ...):"
    " its order against its parent's and its siblings' is not modelled (the harness refuses the ones with no event)",
    "X18",
    java="a RUN TRANSID child's ",
    c="a RUN TRANSID child's %.*s",
)
_CHILD_RECOVERED = RuntimeRefusal(
    "a child that went on after an abend (HANDLE ABEND): its completion status is not documented",
    "X18",
    java="a RUN TRANSID child that went on after an abend",
    c="a RUN TRANSID child that went on after an abend",
)
_CHILD_TIE = RuntimeRefusal(
    "a FETCH whose answer turns on a child completing at the instant its parent resumed from a wait (a tie)",
    "X18",
    java="completing at the instant its parent resumed",
    c="completing at the instant its parent resumed",
)

RUN = Command(
    key="RUN",
    ibm=ibm("EXEC CICS RUN TRANSID", "summary-run-transid"),
    status="modelled",
    register="X18",
    event="RUN",
    options={
        "TRANSID": _TRANSID,
        "CHILD": Arg("area_out", width=16),
        "CHANNEL": Arg("name", width=16),  # the child's copy of the channel, made when RUN is issued
        **RESP_OPTIONS,
    },
    refused={},
    groups=(
        required("TRANSID", msg="RUN without TRANSID / CHILD"),
        required("CHILD", msg="RUN without TRANSID / CHILD"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("CHILD",)),
        Outcome("TRANSIDERR", 1, "the transaction is not defined"),
        _CHANNEL_ERR,
    ),
    runtime_refusals=(
        _DFH_CHANNEL,
        RuntimeRefusal(
            "a RUN TRANSID in a task 3 generations below the issuing task (a great-great-grandchild): a child may RUN "
            "children of its own, to the depth the harness states (IBM states none)",
            "X18",
            java="RUN TRANSID in a RUN TRANSID child task",
            c="RUN TRANSID in a RUN TRANSID child task",
        ),
        _BOTH_BAD,
        _CHILD_RUNS,
        _CHILD_RESOURCE,
    ),
    state=("child_tasks", "handle_table", "channel_scope"),
    engine=EngineFacts(task_verb="RUN", target_option="TRANSID", handle_option="CHILD", channel_option="TRANSID"),
    impl=Impl(translator="Cics.run_transid", java="runTransid", c="GGCRUNT", harness="_run_transid"),
)

_FETCH_OPTIONS = {
    "CHANNEL": Arg("area_out", width=16),
    "ABCODE": Arg("area_out", width=4),
    "COMPSTATUS": Arg("cvda"),
    "NOSUSPEND": Arg("flag"),
    "TIMEOUT": Arg("value"),
}
_FETCH_WRITES = ("CHANNEL", "ABCODE", "COMPSTATUS")
_FETCH_TIMEOUT = RuntimeRefusal(
    "a TIMEOUT below 0 or past 4080000 milliseconds (IBM's FETCH ANY and FETCH CHILD pages give different maximums)",
    "X18",
    java="FETCH TIMEOUT(",
    c="FETCH TIMEOUT(%d)",
)
_NO_REPLY = RuntimeRefusal(
    "FETCH CHANNEL of a child that left no current channel (IBM does not say what CHANNEL gets)",
    "X18",
    java="FETCH CHANNEL of a child that left no current channel",
    c="FETCH CHANNEL of a child that left no current channel",
)
FETCH_ANY = Command(
    key="FETCH ANY",
    ibm=ibm("EXEC CICS FETCH ANY", "summary-fetch-any"),
    status="modelled",
    register="X18",
    event="FETCH",
    options={"ANY": Arg("area_out", width=16), **_FETCH_OPTIONS, **RESP_OPTIONS},
    refused={},
    groups=(
        required("ANY", msg="FETCH ANY without ANY"),
        at_most_one("NOSUSPEND", "TIMEOUT", msg="FETCH {} and {} together"),
    ),
    outcomes=(
        Outcome(
            "NORMAL",
            0,
            "an unfetched child has completed (the first to complete; RUN order on a tie)",
            writes=("ANY", *_FETCH_WRITES),
        ),
        Outcome("NOTFINISHED", 52, "NOSUSPEND was specified, but there were no completed children to fetch"),
        Outcome("NOTFINISHED", 53, "No children have completed within the interval specified by the TIMEOUT option"),
        Outcome("NOTFND", 1, "No unfetched children were found"),
        Outcome("INVREQ", 52, "the parent has no children"),
    ),
    runtime_refusals=(_FETCH_TIMEOUT, _CHILD_TIE, _CHILD_RUNS, _CHILD_RECOVERED, _NO_REPLY),
    state=("child_tasks", "handle_table", "channel_scope"),
    impl=Impl(translator="Cics.fetch", java="fetch", c="GGCFETCH", harness="_fetch_child"),
)

FETCH_CHILD = Command(
    key="FETCH CHILD",
    ibm=ibm("EXEC CICS FETCH CHILD", "summary-fetch-child"),
    status="modelled",
    register="X18",
    event="FETCH",
    options={"CHILD": Arg("area_in", width=16), **_FETCH_OPTIONS, **RESP_OPTIONS},
    refused={},
    groups=(
        required("CHILD", msg="FETCH CHILD without CHILD"),
        at_most_one("NOSUSPEND", "TIMEOUT", msg="FETCH {} and {} together"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "the child has completed", writes=_FETCH_WRITES),
        Outcome("NOTFINISHED", 52, "NOSUSPEND was specified, but the child is not yet complete"),
        Outcome("NOTFINISHED", 53, "The child has not completed within the interval specified by the TIMEOUT option"),
        Outcome("INVREQ", 50, "CHILD is not a valid child token, or the child task has already been freed"),
        Outcome("INVREQ", 51, "The channel of the child has already been fetched"),
    ),
    runtime_refusals=(
        _FETCH_TIMEOUT,
        _CHILD_TIE,
        _CHILD_RUNS,
        _CHILD_RECOVERED,
        _NO_REPLY,
        RuntimeRefusal(
            "a second FETCH of a child, but for its channel fetched again (INVREQ 51): IBM does not say what it answers",
            "X18",
            java="FETCH CHILD of a child already fetched",
            c="FETCH CHILD of a child already fetched",
        ),
    ),
    state=("child_tasks", "handle_table", "channel_scope"),
    impl=Impl(translator="Cics.fetch", java="fetch", c="GGCFETCH", harness="_fetch_child"),
)

FREE_CHILD = Command(
    key="FREE CHILD",
    ibm=ibm("EXEC CICS FREE CHILD", "summary-free-child"),
    status="modelled",
    register="X18",
    event="FREE-CHILD",
    options={"CHILD": Arg("area_in", width=16), **RESP_OPTIONS},
    refused={},
    groups=(required("CHILD", msg="FREE CHILD without CHILD"),),
    runtime_refusals=(
        RuntimeRefusal(
            "FREE CHILD of a child already fetched (IBM does not say)",
            "X18",
            java="FREE CHILD of a child already fetched",
            c="FREE CHILD of a child already fetched",
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "the token is freed: a later FETCH CHILD of it is INVREQ, FETCH ANY skips it"),
        Outcome("INVREQ", 50, "CHILD is not a valid child token, or the child task has already been freed"),
    ),
    state=("child_tasks", "handle_table"),
    impl=Impl(translator="Cics.free_child", java="freeChild", c="GGCFREE", harness="_free_child"),
)

# #5079 (X63): POST and WAIT EVENT -- a timer-event control area on the stated clock. A task takes no time (X4), so the area is
# posted only by a WAIT EVENT, which runs the clock to the expiry, or by a CANCEL of the POST.
_POST_ENDED = RuntimeRefusal(
    "a WAIT EVENT on an area a later POST, CANCEL, local START or DELAY of the task ended (IBM: its result is unpredictable)",
    "X63",
    java="a later POST, CANCEL, START or DELAY ended",
    c="a later POST, CANCEL, START or DELAY ended",
)
_NOT_A_POST = RuntimeRefusal(
    "a WAIT EVENT on an address that is no POST's timer-event control area (an ECB of another kind is not modelled)",
    "X63",
    java="no POST's timer-event control area",
    c="no POST's timer-event control area",
)

POST = Command(
    key="POST",
    ibm=ibm("EXEC CICS POST", "summary-post"),
    status="modelled",
    register="X63",
    options={
        "INTERVAL": Arg("hhmmss"),  # none of INTERVAL / TIME / AFTER / AT: INTERVAL(0)
        "TIME": Arg("hhmmss"),
        "AFTER": Arg("flag"),
        "AT": Arg("flag"),
        "HOURS": Arg("value"),
        "MINUTES": Arg("value"),
        "SECONDS": Arg("value"),
        "SET": Arg("pointer"),
        "REQID": Arg("name", width=8),
        **RESP_OPTIONS,
    },
    groups=(
        at_most_one("INTERVAL", "TIME", "AFTER", "AT", msg="POST {}: one expiry option"),
        requires(
            ("HOURS", "MINUTES", "SECONDS"),
            any_of=("AFTER", "AT"),
            both_ways=True,
            msg="POST {} {}: HOURS / MINUTES / SECONDS go with AFTER / AT",
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 4, "hours out of range (HOURS, or INTERVAL / TIME's hh)"),
        Outcome("INVREQ", 5, "minutes out of range (MINUTES, or mm)"),
        Outcome("INVREQ", 6, "seconds out of range (SECONDS, or ss)"),
        Outcome("EXPIRED", None, "the specified time has already passed when the command is issued"),
    ),
    state=("interval_requests", "virtual_clock", "handle_table"),
    impl=Impl(translator="Cics.post", java="post", c="GGCPOST", harness="_post"),
)

WAIT_EVENT = Command(
    key="WAIT EVENT",
    ibm=ibm("EXEC CICS WAIT EVENT", "summary-wait-event"),
    status="modelled",
    register="X63",
    # NAME only labels the suspended task (SUSPENDVALUE / HVALUE of INQUIRE TASK): it changes nothing here
    options={"ECADDR": Arg("pointer"), "NAME": Arg("name", width=8), **RESP_OPTIONS},
    groups=(required("ECADDR", msg="WAIT EVENT without ECADDR"),),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 2, "the ECB address is a null pointer"),
    ),
    runtime_refusals=(_NOT_A_POST, _POST_ENDED),
    state=("interval_requests", "virtual_clock", "handle_table"),
    impl=Impl(translator="Cics.wait_event", java="waitEvent", c="GGCWEVT", harness="_wait_event"),
)

# #5079 (X63): WAIT EXTERNAL / WAITCICS -- wait for an MVS-format ECB of the program's own. ECBLIST addresses a list of ECB
# addresses held in task storage (8-byte handles, as a POINTER table); a block's first byte X'40' is "posted" (ASSUMED: IBM names
# no bit). Nothing else runs to post one, so a list with no posted ECB is refused (it would wait forever).
_NOT_POSTED = RuntimeRefusal(
    "a WAIT on an ECB list with no posted ECB (nothing else runs to post one: the task would wait forever)",
    "X63",
    java="no ECB in the list is posted",
    c="no ECB in the list is posted",
)
_ECB_UNKNOWN = RuntimeRefusal(
    "a WAIT on an ECB list that is no task-storage block holding NUMEVENTS handles, or names an address no block holds",
    "X63",
    java="the ECB list or an ECB in it is no task storage",
    c="the ECB list or an ECB in it is no task storage",
)
_WAITCICS_NULL = RuntimeRefusal(
    "WAITCICS with a null ECBLIST (IBM gives RESP2 2 to WAIT EXTERNAL only)",
    "X63",
    java="WAITCICS with a null ECBLIST",
    c="WAITCICS with a null ECBLIST",
)
_ECB_OUTCOMES = (
    Outcome("NORMAL", 0, "an ECB in the list is posted: the task is not suspended"),
    Outcome("INVREQ", 3, "NUMEVENTS is not positive"),
    Outcome("INVREQ", 5, "no valid ECB in the list (every address is null)"),
)
_ECB_OPTIONS = {
    "ECBLIST": Arg("pointer"),
    "NUMEVENTS": Arg("value"),
    "NAME": Arg("name", width=8),  # labels the suspended task only
    "PURGEABLE": Arg("flag"),  # no DTIMOUT / task purge arises on the stated clock: both change nothing here
    "NOTPURGEABLE": Arg("flag"),
    **RESP_OPTIONS,
}

WAIT_EXTERNAL = Command(
    key="WAIT EXTERNAL",
    ibm=ibm("EXEC CICS WAIT EXTERNAL", "summary-wait-external"),
    status="modelled",
    register="X63",
    options=dict(_ECB_OPTIONS),
    groups=(
        required("ECBLIST", msg="WAIT EXTERNAL without ECBLIST"),
        required("NUMEVENTS", msg="WAIT EXTERNAL without NUMEVENTS"),
        at_most_one("PURGEABLE", "NOTPURGEABLE", msg="WAIT EXTERNAL: PURGEABLE and NOTPURGEABLE"),
    ),
    outcomes=(*_ECB_OUTCOMES, Outcome("INVREQ", 2, "the ECBLIST address is a null pointer")),
    runtime_refusals=(_ECB_UNKNOWN, _NOT_POSTED),
    state=("handle_table",),
)

WAITCICS = Command(
    key="WAITCICS",
    ibm=ibm("EXEC CICS WAITCICS", "summary-waitcics"),
    status="modelled",
    register="X63",
    options=dict(_ECB_OPTIONS),
    groups=(
        required("ECBLIST", msg="WAITCICS without ECBLIST"),
        required("NUMEVENTS", msg="WAITCICS without NUMEVENTS"),
        at_most_one("PURGEABLE", "NOTPURGEABLE", msg="WAITCICS: PURGEABLE and NOTPURGEABLE"),
    ),
    outcomes=_ECB_OUTCOMES,
    runtime_refusals=(_WAITCICS_NULL, _ECB_UNKNOWN, _NOT_POSTED),
    state=("handle_table",),
)

COMMANDS = (START, RETRIEVE, CANCEL, RUN, FETCH_ANY, FETCH_CHILD, FREE_CHILD, POST, WAIT_EVENT, WAIT_EXTERNAL, WAITCICS)
