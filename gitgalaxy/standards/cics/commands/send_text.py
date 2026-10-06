# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 slice 4 (#4583): SEND TEXT, TERMINAL the default disposition, register X20.

The region's terminal is one 24 x 80 3270 display (cics-crucible SPEC 2), and a BMS logical message (ACCUM / PAGING /
SET, then SEND PAGE) is not modelled."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.commands.shared import NOT_MODELLED, RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import Arg, Command, Impl, Outcome, Refusal


def _x20(why: str) -> Refusal:
    return Refusal(why, "X20")


_LOGICAL_MESSAGE = "a BMS logical message (ACCUM / PAGING, completed by SEND PAGE) is not modelled"
_PRINTER = _x20("printer formatting: the region's terminal is a 3270 display")
_PARTITION = _x20("partitions / logical device codes: the region's terminal is one unpartitioned display")
_SCREEN_SIZE = _x20("the default / alternate screen size: only the one screen the region defines is modelled")
_JUSTIFY = _x20("the line a text block starts on in a page: " + _LOGICAL_MESSAGE)
# det/cics.py _SEND_TEXT_REFUSED_WHY, word for word
SEND_TEXT_REFUSED: Mapping[str, Refusal] = {
    "ACCUM": _x20(_LOGICAL_MESSAGE),
    "PAGING": _x20("output kept in temporary storage for terminal paging (CSPG): " + _LOGICAL_MESSAGE),
    "SET": _x20(
        "the formatted pages returned to the program (RETPAGE) are not modelled: only the TERMINAL disposition"
    ),
    "REQID": _x20("a logical message's temporary-storage prefix: " + _LOGICAL_MESSAGE),
    "HEADER": _x20("page headers: " + _LOGICAL_MESSAGE),
    "TRAILER": _x20("page trailers: " + _LOGICAL_MESSAGE),
    "JUSTIFY": _JUSTIFY,
    "JUSFIRST": _JUSTIFY,
    "JUSLAST": _JUSTIFY,
    "NLEOM": _PRINTER,
    "FORMFEED": _PRINTER,
    "HONEOM": _PRINTER,
    "L40": _PRINTER,
    "L64": _PRINTER,
    "L80": _PRINTER,
    "LDC": _PARTITION,
    "OUTPARTN": _PARTITION,
    "ACTPARTN": _PARTITION,
    "MSR": _x20("magnetic slot reader control is not modelled"),
    "FMHPARM": _x20("function management headers are not modelled"),
    "DEFAULT": _SCREEN_SIZE,
    "ALTERNATE": _SCREEN_SIZE,
}

# the device-control options SEND TEXT passes on (det/cics.py TEXT_OPTIONS); CURSOR / CTLCHAR with a value are
# refused in Cics.command ("its value is not modelled")
TEXT_OPTIONS = ("ERASE", "FREEKB", "ALARM", "CURSOR", "PRINT", "LAST", "WAIT", "INVITE", "DEFRESP", "STRFIELD",
                "CTLCHAR")  # fmt: skip

SEND_TEXT = Command(
    key="SEND TEXT",
    ibm=ibm("EXEC CICS SEND TEXT", "summary-send-text"),
    status="modelled",
    register="X20",
    event="SEND-TEXT",
    options={
        "FROM": Arg("area_in"),
        "LENGTH": Arg("value"),  # omitted: FROM's length
        # "TERMINAL is the default value that you get if you do not specify another disposition": no code of its own
        "TERMINAL": Arg("flag"),
        **{o: Arg("flag") for o in TEXT_OPTIONS},
        **RESP_OPTIONS,
    },
    refused=SEND_TEXT_REFUSED,
    default_refusal=NOT_MODELLED,
    outcomes=(Outcome("NORMAL", 0, ""),),
    state=("terminal",),
    impl=Impl(translator="Cics.command", java="sendText", c="GGCSTXT", harness="translate_command"),
)

COMMANDS = (SEND_TEXT,)
