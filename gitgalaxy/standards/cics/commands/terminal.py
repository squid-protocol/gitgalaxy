# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 spec PR 2: BMS maps and terminal control without a map -- SEND MAP / RECEIVE MAP (det/cics.py
Cics.send_map / receive_map) and SEND CONTROL / RECEIVE (#4413, Cics.send_control / receive).

A refused option shows no reason but SET's (the reason the old global table gave it)."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import BOTH_FORMS, RESP_OPTIONS, SET_POINTER, ibm
from gitgalaxy.standards.cics.model import Arg, Command, EngineFacts, Outcome, at_most_one, one_of

# SEND MAP's device controls and output options passed on as flags (det/cics.py parse_exec: never a verb word)
MAP_OPTIONS = ("ERASE", "ERASEAUP", "FREEKB", "ALARM", "CURSOR", "FRSET", "MAPONLY", "DATAONLY", "PRINT", "LAST",
               "WAIT", "ACCUM", "PAGING", "TERMINAL", "NLEOM", "FORMFEED")  # fmt: skip
# #4413: SEND CONTROL's device controls (IBM's minimum-BMS options; PRINT, FORMFEED, ALTERNATE / DEFAULT and the
# partition / LDC / ACCUM / PAGING ones are refused)
SEND_CONTROL_OPTIONS = ("ERASE", "ERASEAUP", "FREEKB", "ALARM", "CURSOR", "FRSET")

_MAP = {"MAP": Arg("name", width=7), "MAPSET": Arg("name", width=8)}

SEND_MAP = Command(
    key="SEND MAP",
    ibm=ibm("EXEC CICS SEND MAP", "summary-send-map"),
    status="modelled",
    options={**_MAP, "FROM": Arg("area_in"), **{o: Arg("flag") for o in MAP_OPTIONS}, **RESP_OPTIONS},
    refused={"SET": SET_POINTER},
    outcomes=(Outcome("NORMAL", 0, ""),),
    state=("terminal",),
    engine=EngineFacts(resource="MAP", access="write"),
)

RECEIVE_MAP = Command(
    key="RECEIVE MAP",
    ibm=ibm("EXEC CICS RECEIVE MAP", "summary-receive-map"),
    status="modelled",
    options={**_MAP, "INTO": Arg("area_out"), **RESP_OPTIONS},
    refused={"SET": SET_POINTER},
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO",)),
        Outcome("MAPFAIL", None, "the operator sent no data for the map"),
    ),
    state=("terminal", "handle_table"),
    engine=EngineFacts(resource="MAP", access="read"),
)

SEND_CONTROL = Command(
    key="SEND CONTROL",
    ibm=ibm("EXEC CICS SEND CONTROL", "summary-send-control"),
    status="modelled",
    register="X15",
    # CURSOR: with a value, a halfword offset; without one it is refused in Cics.send_control
    options={**{o: Arg("flag") for o in SEND_CONTROL_OPTIONS}, "CURSOR": Arg("value"), **RESP_OPTIONS},
    refused={"SET": SET_POINTER},
    outcomes=(Outcome("NORMAL", 0, "none of its conditions arises for the task's plain terminal"),),
    state=("terminal",),
)

RECEIVE = Command(
    key="RECEIVE",
    ibm=ibm("EXEC CICS RECEIVE (3270 logical)", "summary-receive-3270-logical"),
    status="modelled",
    register="X15",
    options={
        "INTO": Arg("area_out"),
        "SET": Arg("pointer"),  # SET(ADDRESS OF a LINKAGE 01 record) only (Cics.receive)
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        "FLENGTH": Arg("area_inout", width=4, binary=True, inout_unless_literal=True),
        "MAXLENGTH": Arg("value"),
        "MAXFLENGTH": Arg("value"),
        "NOTRUNCATE": Arg("flag"),
        **RESP_OPTIONS,
    },
    groups=(
        one_of("INTO", "SET", msg="RECEIVE needs one of INTO / SET"),
        at_most_one("LENGTH", "FLENGTH", msg=BOTH_FORMS),
        at_most_one("MAXLENGTH", "MAXFLENGTH", msg=BOTH_FORMS),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "LENGTH", "FLENGTH")),
        Outcome(
            "LENGERR",
            None,
            "the input is longer than the most taken: truncated",
            writes=("INTO", "SET", "LENGTH", "FLENGTH"),
        ),
        Outcome("EOC", None, "an LUTYPE2 terminal's input ends its chain (ignored by default)"),
    ),
    state=("terminal", "handle_table"),
)

COMMANDS = (SEND_MAP, RECEIVE_MAP, SEND_CONTROL, RECEIVE)
