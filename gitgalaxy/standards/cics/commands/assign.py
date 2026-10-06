# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 slice 3 (#4582): ASSIGN, its stated facts and per-option results, register X19."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.commands.shared import NOT_MODELLED, REMOTE, RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import Arg, Command, Fact, Impl, Outcome, Refusal, RuntimeRefusal


def _x19(why: str) -> Refusal:
    return Refusal(why, "X19")


_SCREEN_SIZES = _x19("default / alternate screen sizes: only the one screen the region defines is modelled")
# det/cics.py _ASSIGN_REFUSED_WHY, word for word
ASSIGN_REFUSED: Mapping[str, Refusal] = {
    "OPID": _x19("the operator's RACF identification: the region has no security and no signed-on operator"),
    "OPCLASS": _x19("the operator's RACF classes: the region has no security and no signed-on operator"),
    "OPSECURITY": _x19("the operator's RACF security keys: the region has no security"),
    "USERNAME": _x19("the user's RACF name: the region has no security"),
    "NETNAME": _x19("the terminal's VTAM LU name: the harness's terminal has no network name"),
    "TERMCODE": _x19("the terminal's device type and model code: the harness's terminal is no catalogued device"),
    "FCI": _x19("the facility control indicator's codes for a task with no terminal are not decided here"),
    "DEFSCRNHT": _SCREEN_SIZES,
    "DEFSCRNWD": _SCREEN_SIZES,
    "ALTSCRNHT": _SCREEN_SIZES,
    "ALTSCRNWD": _SCREEN_SIZES,
    "TWALENG": _x19("the transaction work area is not modelled"),
    "TCTUALENG": _x19("the terminal control table user area is not modelled"),
    "CWALENG": _x19("the common work area is not modelled"),
    "TASKPRIORITY": _x19("task priority is not modelled (one task runs at a time)"),
    "RETURNPROG": _x19("where control returns at the end of a program (an XCTL chain's LINK level) is not modelled"),
    "PRINSYSID": _x19(REMOTE),
    "QNAME": _x19("transient-data trigger-level tasks are not modelled"),
}

# the options whose data comes from the task's terminal: INVREQ RESP2 5 without one
TERMINAL_OPTIONS = ("FACILITY", "SCRNHT", "SCRNWD")
_OUTPUTS = ("APPLID", "SYSID", "ABCODE", "PROGRAM", "INVOKINGPROG", "CHANNEL", "STARTCODE", "USERID",
            *TERMINAL_OPTIONS)  # fmt: skip

ASSIGN = Command(
    key="ASSIGN",
    ibm=ibm("EXEC CICS ASSIGN", "summary-assign"),
    status="modelled",
    register="X19",
    options={
        "APPLID": Arg("area_out", width=8),
        "SYSID": Arg("area_out", width=4),
        "ABCODE": Arg("area_out", width=4),
        "PROGRAM": Arg("area_out", width=8),
        "INVOKINGPROG": Arg("area_out", width=8),
        "CHANNEL": Arg("area_out", width=16),  # #4270 slice 1: blanks without a current channel
        "STARTCODE": Arg("area_out", width=2),
        "USERID": Arg("area_out", width=8),
        "FACILITY": Arg("area_out", width=4),
        "SCRNHT": Arg("area_out", width=2, binary=True),
        "SCRNWD": Arg("area_out", width=2, binary=True),
        **RESP_OPTIONS,
    },
    refused=ASSIGN_REFUSED,
    default_refusal=NOT_MODELLED,
    outcomes=(
        Outcome("NORMAL", 0, "", writes=_OUTPUTS),
        # X19: no data area is written on INVREQ, the other options' included
        Outcome(
            "INVREQ",
            5,
            "The task is not associated with a terminal; or the task has no principal facility",
            raised_by=TERMINAL_OPTIONS,
        ),
    ),
    facts=(
        Fact(
            "startcode",
            java="withStartcode",
            env="GGCICS_STARTCODE",
            region_default=None,
            options=("STARTCODE",),
            values=("TD", "S", "SD"),
        ),
        Fact("userid", java="withUserid", env="GGCICS_USERID", region_default="CICSUSER", options=("USERID",)),
        Fact("facility", java=None, env="GGCICS_FACILITY", region_default=None, options=("FACILITY",)),
        Fact("screen", java="withScreen", env="GGCICS_SCREEN", region_default="24 80", options=("SCRNHT", "SCRNWD")),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "ASSIGN STARTCODE in a RUN TRANSID child task: IBM lists no code for one",
            "X19",
            java="ASSIGN STARTCODE in a RUN TRANSID child task (IBM lists no code for one)",
            c="ASSIGN STARTCODE in a RUN TRANSID child task: IBM lists no code for it",
        ),
        RuntimeRefusal(
            "a fact nobody stated for the task (STARTCODE, USERID, SCRNHT / SCRNWD; FACILITY on the stub)",
            "X19",
            java=": how the task was started is not stated (withStartcode)",
            c="ASSIGN %s: not stated for this task",
        ),
    ),
    state=("terminal", "handle_table"),
    impl=Impl(translator="Cics.assign", java="assignTerminalResp", c="GGCASGN", harness="_handle"),
)

COMMANDS = (ASSIGN,)
