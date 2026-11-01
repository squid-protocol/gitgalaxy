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
from gitgalaxy.standards.cics.model import (
    Abend,
    Arg,
    Command,
    EngineFacts,
    Impl,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    one_of,
    required,
)

# SEND MAP's device controls and output options passed on as flags (det/cics.py parse_exec: never a verb word)
MAP_OPTIONS = ("ERASE", "ERASEAUP", "FREEKB", "ALARM", "CURSOR", "FRSET", "MAPONLY", "DATAONLY", "PRINT", "LAST",
               "WAIT", "ACCUM", "PAGING", "TERMINAL", "NLEOM", "FORMFEED")  # fmt: skip
# #4413: SEND CONTROL's device controls (IBM's minimum-BMS options; PRINT, FORMFEED, ALTERNATE / DEFAULT and the
# partition / LDC / ACCUM / PAGING ones are refused)
SEND_CONTROL_OPTIONS = ("ERASE", "ERASEAUP", "FREEKB", "ALARM", "CURSOR", "FRSET")

_MAP = {"MAP": Arg("name", width=7), "MAPSET": Arg("name", width=8)}

# #5079 (X59): SEND MAP's output disposition and printer options that the one 3270 display cannot honour. They stay in
# MAP_OPTIONS (the parser must read them as flags, never as verb words) but are refused by name, as SEND TEXT refuses
# them (X20): ACCUM / PAGING build a BMS logical message that nothing sends until SEND PAGE, so passing them on as a
# plain send would put a map on the screen that IBM keeps back
_MAP_LOGICAL = "a BMS logical message (ACCUM / PAGING, completed by SEND PAGE) is not modelled"
_MAP_PRINTER = "printer formatting: the region's terminal is a 3270 display"
MAP_REFUSED_OPTIONS = {
    "ACCUM": Refusal(_MAP_LOGICAL),
    "PAGING": Refusal("output kept in temporary storage for terminal paging (CSPG): " + _MAP_LOGICAL),
    "NLEOM": Refusal(_MAP_PRINTER),
    "FORMFEED": Refusal(_MAP_PRINTER),
}

# #4270 (X31): IBM CICS TS, abend code ABM0 -- "The map specified for a basic mapping support (BMS) request could not be
# located." System action: "The transaction is abnormally terminated with a CICS transaction dump." A map is found only
# inside its own mapset (MAPSET defaults to the MAP name), so a map the mapset does not hold is this abend. SEND MAP's and
# RECEIVE MAP's condition lists name no condition for it, so RESP / RESP2 / HANDLE CONDITION do not see it
MAP_NOT_FOUND = Abend(
    "ABM0", "the map is not one of the mapset's maps (MAPSET omitted: the mapset is named like the map)"
)

SEND_MAP = Command(
    key="SEND MAP",
    ibm=ibm("EXEC CICS SEND MAP", "summary-send-map"),
    status="modelled",
    options={
        **_MAP,
        "FROM": Arg("area_in"),
        **{o: Arg("flag") for o in MAP_OPTIONS if o not in MAP_REFUSED_OPTIONS},
        **RESP_OPTIONS,
    },
    refused={"SET": SET_POINTER, **MAP_REFUSED_OPTIONS},
    outcomes=(Outcome("NORMAL", 0, ""),),
    abends=(MAP_NOT_FOUND,),
    state=("terminal",),
    register="X31",
    engine=EngineFacts(resource="MAP", access="write"),
)

RECEIVE_MAP = Command(
    key="RECEIVE MAP",
    ibm=ibm("EXEC CICS RECEIVE MAP", "summary-receive-map"),
    status="modelled",
    # #4737 (X28): ASIS -- IBM: "lowercase characters in the 3270 input data stream are not translated to uppercase". The
    # region delivers the operator's input as typed, so ASIS changes nothing
    # #4415 (X29): TERMINAL -- IBM: "specifies that input data is to be read from the terminal that originated the
    # transaction". The region's task has that one terminal, which every RECEIVE MAP reads, so it changes nothing
    options={**_MAP, "INTO": Arg("area_out"), "ASIS": Arg("flag"), "TERMINAL": Arg("flag"), **RESP_OPTIONS},
    refused={"SET": SET_POINTER},
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO",)),
        Outcome("MAPFAIL", None, "the operator sent no data for the map"),
    ),
    abends=(MAP_NOT_FOUND,),
    state=("terminal", "handle_table"),
    register="X31",
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
        "SET": Arg("pointer"),  # SET(ADDRESS OF a LINKAGE 01 record), or a plain USAGE POINTER item (#5042, X58)
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

# #5079 (X63): CONVERSE (default), the terminal form -- the data written to the terminal (what a plain SEND records), then what a
# RECEIVE reads (INTO, or SET(pointer) as RECEIVE SET, X58). The APPC / MRO conversation forms (CONVID, STATE, ATTACHID, STRFIELD ...) are refused.
_CONVERSE_APPC = Refusal(
    "a conversation with a partner transaction (APPC / distributed program link: CONVID, STATE, ATTACHID, STRFIELD ...) is"
    " not modelled: only the terminal form is",
    "X63",
)
CONVERSE = Command(
    key="CONVERSE",
    ibm=ibm("EXEC CICS CONVERSE (default)", "summary-converse-default"),
    status="modelled",
    register="X63",
    options={
        "FROM": Arg("area_in"),
        "FROMLENGTH": Arg("value"),
        "FROMFLENGTH": Arg("value"),
        "INTO": Arg("area_out"),
        "SET": Arg("pointer"),  # the reply in a task-storage block (X58); the stub models it too (GGCCONS, #7371)
        "TOLENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        "TOFLENGTH": Arg("area_inout", width=4, binary=True, inout_unless_literal=True),
        "MAXLENGTH": Arg("value"),
        "MAXFLENGTH": Arg("value"),
        "NOTRUNCATE": Arg("flag"),
        **RESP_OPTIONS,
    },
    default_refusal=_CONVERSE_APPC,
    groups=(
        required("FROM", msg="CONVERSE without FROM: the data written to the terminal"),
        one_of("INTO", "SET", msg="CONVERSE without INTO or SET: the reply read from the terminal"),
        at_most_one("FROMLENGTH", "FROMFLENGTH", msg=BOTH_FORMS),
        at_most_one("TOLENGTH", "TOFLENGTH", msg=BOTH_FORMS),
        at_most_one("MAXLENGTH", "MAXFLENGTH", msg=BOTH_FORMS),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "TOLENGTH", "TOFLENGTH")),
        Outcome(
            "LENGERR",
            None,
            "the reply is longer than the most taken (truncated), or a length is out of range",
            writes=("INTO", "SET", "TOLENGTH", "TOFLENGTH"),
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "CONVERSE on an LUTYPE2 terminal: IBM lists no EOC for it, and the reply's last byte ends the chain there",
            "X63",
            java="CONVERSE on an LUTYPE2 terminal",
            c="CONVERSE on an LUTYPE2 terminal",
        ),
    ),
    state=("terminal", "handle_table"),
    impl=Impl(translator="Cics.converse", java="converse", c="GGCCONV", harness="_converse"),
)

COMMANDS = (SEND_MAP, RECEIVE_MAP, SEND_CONTROL, RECEIVE, CONVERSE)
