# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 spec PR 2: program control -- LINK / XCTL / RETURN (#4270 channels: LINK / XCTL CHANNEL), ABEND and HANDLE
ABEND, and LOAD / RELEASE (engine-only: the translator refuses them whole; cics_command_spec.md section 5).

A refused option shows no reason but LINK's SYSID (the reason the old global table gave it) and RETURN CHANNEL."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, SYSID_REMOTE, ibm
from gitgalaxy.standards.cics.model import Arg, Command, EngineFacts, Outcome, Refusal, at_most_one

_PROGRAM = Arg("name", width=8)
# "LINK CHANNEL with COMMAREA / LENGTH: one or the other" (det/cics.py Cics.command)
_ONE_OR_THE_OTHER = "{} CHANNEL with COMMAREA / LENGTH: one or the other"
_TRANSFER_OUTCOMES = (
    Outcome("NORMAL", 0, ""),
    Outcome("LENGERR", 11, "LENGTH is below zero or past 32763"),
    Outcome("PGMIDERR", 1, "the program is not defined"),
)


def _transfer(key: str, extra: dict[str, Arg] | None = None, **kw) -> Command:
    extra = extra or {}
    msg = _ONE_OR_THE_OTHER.format(key)
    return Command(
        key=key,
        ibm=ibm(f"EXEC CICS {key}", "summary-" + key.lower()),
        status="modelled",
        options={
            "PROGRAM": _PROGRAM,
            "COMMAREA": Arg("area_inout"),
            "LENGTH": Arg("value"),
            "CHANNEL": Arg("name", width=16),
            **RESP_OPTIONS,
            **extra,
        },
        groups=(at_most_one("CHANNEL", "COMMAREA", msg=msg), at_most_one("CHANNEL", "LENGTH", msg=msg)),
        outcomes=_TRANSFER_OUTCOMES,
        state=("channel_scope", "handle_table"),
        engine=EngineFacts(channel_option="PROGRAM"),
        **kw,
    )


# #4270 (X27): SYNCONRETURN "is only applicable to remote links, it is ignored if the link is local" (IBM, EXEC CICS
# LINK); every program of the modelled region is local, so it is accepted and changes nothing
LINK = _transfer("LINK", extra={"SYNCONRETURN": Arg("flag")}, refused={"SYSID": SYSID_REMOTE}, register="X27")
XCTL = _transfer("XCTL")

RETURN = Command(
    key="RETURN",
    ibm=ibm("EXEC CICS RETURN", "summary-return"),
    status="modelled",
    register="X27",
    # control never comes back from a RETURN, so a RESP area it does not write is never read after it
    # #4270 (X27): IMMEDIATE attaches TRANSID's task at once, ahead of any terminal input (IBM, EXEC CICS RETURN); with
    # it the command can fail (INVREQ RESP2 1 / 2, LENGERR RESP2 11), so RESP is read after it
    options={
        "TRANSID": Arg("name", width=4),
        "COMMAREA": Arg("area_in"),
        "LENGTH": Arg("value"),
        "IMMEDIATE": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "CHANNEL": Refusal(
            "RETURN CHANNEL: the next task's channel is not modelled (no corpus program uses it)", whole=True
        ),
    },
    outcomes=(
        Outcome("NORMAL", 0, "control returns to CICS or the linking program"),
        Outcome("INVREQ", 1, "the task is not associated with a terminal", raised_by=("IMMEDIATE",)),
        Outcome("INVREQ", 2, "IMMEDIATE below the highest logical level", raised_by=("IMMEDIATE",)),
        Outcome("LENGERR", 11, "the COMMAREA length is below 0 or past 32763", raised_by=("IMMEDIATE",)),
    ),
    state=("channel_scope",),
    engine=EngineFacts(channel_option="TRANSID"),
)

ABEND = Command(
    key="ABEND",
    ibm=ibm("EXEC CICS ABEND", "summary-abend"),
    status="modelled",
    # NODUMP: a dump is no state the program or its caller sees
    options={"ABCODE": Arg("name", width=4), "CANCEL": Arg("flag"), "NODUMP": Arg("flag")},
    outcomes=(Outcome("NORMAL", 0, "never: the task abends (to a HANDLE ABEND exit unless CANCEL)"),),
)

HANDLE_ABEND = Command(
    key="HANDLE ABEND",
    ibm=ibm("EXEC CICS HANDLE ABEND", "summary-handle-abend"),
    status="modelled",
    # PROGRAM is accepted here and refused by Cics.command ("HANDLE ABEND PROGRAM"); NOHANDLE where the translation
    # raises no condition anyway (no RESP: its area would not be written)
    options={
        "LABEL": Arg("label"),
        "CANCEL": Arg("flag"),
        "RESET": Arg("flag"),
        "PROGRAM": _PROGRAM,
        "NOHANDLE": Arg("flag"),
    },
    outcomes=(Outcome("NORMAL", 0, ""),),
)

# engine-only (cics_command_spec.md section 5): the engine's LOAD edge waits for PR 8b, after the blind trial
_LOAD_WHY = "a program or table loaded into storage and addressed by a pointer is not modelled"

LOAD = Command(
    key="LOAD",
    ibm=ibm("EXEC CICS LOAD", "summary-load"),
    status="engine-only",
    why=_LOAD_WHY,
    options={
        "PROGRAM": _PROGRAM,
        "SET": Arg("pointer"),
        "LENGTH": Arg("area_out", width=2, binary=True),
        "FLENGTH": Arg("area_out", width=4, binary=True),
        "ENTRY": Arg("pointer"),
        "HOLD": Arg("flag"),
        **RESP_OPTIONS,
    },
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("PGMIDERR", None, "the program is not defined, or cannot be loaded"),
    ),
    engine=EngineFacts(edge="load", target_option="PROGRAM"),
)

RELEASE = Command(
    key="RELEASE",
    ibm=ibm("EXEC CICS RELEASE", "summary-release"),
    status="engine-only",
    why="releasing a LOADed program or table: " + _LOAD_WHY,
    options={"PROGRAM": _PROGRAM, **RESP_OPTIONS},
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("PGMIDERR", None, "the program is not defined"),
        Outcome("INVREQ", None, "the program was not LOADed by this task (HOLD aside)"),
    ),
    engine=EngineFacts(edge="load", target_option="PROGRAM"),
)

COMMANDS = (LINK, XCTL, RETURN, ABEND, HANDLE_ABEND, LOAD, RELEASE)
