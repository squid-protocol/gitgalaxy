# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 spec PR 2: the handle table -- HANDLE CONDITION, IGNORE CONDITION, HANDLE AID, PUSH / POP HANDLE (#4414,
det/cics.py Cics.conditions / handle_aid_ / push_pop), register X16.

HANDLE / IGNORE CONDITION and HANDLE AID have open options: each option is a condition (DFHRESP, never NORMAL) or an
attention key, checked by the command's own handler with its own message, never by the option table."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import Arg, Command, Outcome
from gitgalaxy.standards.cics.resp import DFHRESP

# #4414: the keys HANDLE AID names (IBM, EXEC CICS HANDLE AID), as the equivalence harness's stub has them
AID_KEYS = frozenset(["ANYKEY", "ENTER", "CLEAR", "CLRPARTN", "LIGHTPEN", "OPERID", "TRIGGER", "PA1", "PA2", "PA3"]
                     + [f"PF{n}" for n in range(1, 25)])  # fmt: skip
_CONDITIONS = tuple(c for c in DFHRESP if c != "NORMAL")
_NORMAL = Outcome("NORMAL", 0, "")

HANDLE_CONDITION = Command(
    key="HANDLE CONDITION",
    ibm=ibm("EXEC CICS HANDLE CONDITION", "summary-handle-condition"),
    status="modelled",
    register="X16",
    open_options=True,
    options={c: Arg("label") for c in _CONDITIONS},  # a condition with no label: its handler removed
    outcomes=(_NORMAL,),
    state=("handle_table",),
)

IGNORE_CONDITION = Command(
    key="IGNORE CONDITION",
    ibm=ibm("EXEC CICS IGNORE CONDITION", "summary-ignore-condition"),
    status="modelled",
    register="X16",
    open_options=True,
    options={c: Arg("flag") for c in _CONDITIONS},  # (IGNORE CONDITION ERROR: refused by Cics.conditions, X16)
    outcomes=(_NORMAL,),
    state=("handle_table",),
)

HANDLE_AID = Command(
    key="HANDLE AID",
    ibm=ibm("EXEC CICS HANDLE AID", "summary-handle-aid"),
    status="modelled",
    register="X16",
    open_options=True,
    options={k: Arg("label") for k in sorted(AID_KEYS)},  # no RESP / NOHANDLE: HANDLE AID raises no condition here
    outcomes=(_NORMAL,),
    state=("terminal", "handle_table"),
)

PUSH_HANDLE = Command(
    key="PUSH HANDLE",
    ibm=ibm("EXEC CICS PUSH HANDLE", "summary-push-handle"),
    status="modelled",
    register="X16",
    options=dict(RESP_OPTIONS),
    outcomes=(_NORMAL,),
    state=("handle_table",),
)

POP_HANDLE = Command(
    key="POP HANDLE",
    ibm=ibm("EXEC CICS POP HANDLE", "summary-pop-handle"),
    status="modelled",
    register="X16",
    options=dict(RESP_OPTIONS),
    outcomes=(_NORMAL, Outcome("INVREQ", None, "no PUSH HANDLE is outstanding")),
    state=("handle_table",),
)

COMMANDS = (HANDLE_CONDITION, IGNORE_CONDITION, HANDLE_AID, PUSH_HANDLE, POP_HANDLE)
