# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4771 (register X47): the pointer lane. GETMAIN and FREEMAIN on storage CICS acquires for the task, addressed by a
USAGE POINTER item; `SET ADDRESS OF record TO pointer` and WEB RECEIVE SET (web.py) are the other halves.

IBM (CICS TS 6.x, EXEC CICS GETMAIN / FREEMAIN): GETMAIN SET(ptr) FLENGTH(n) INITIMG(byte) sets the pointer to the
first byte of n acquired bytes, every byte the INITIMG value ("There is no default initialization": without INITIMG
the contents are undefined: a GETMAIN without it is accepted, answers LENGERR when no storage is acquired, and is refused
by name when it would acquire some); LENGERR (RESP2 1) for FLENGTH below 1 or LENGTH zero, the pointer
then set to zero; NOSTG (RESP2 2) when the request exceeds the storage available (not modelled: refused above a stated
limit). FREEMAIN DATAPOINTER(ptr) releases the storage GETMAIN returned; INVREQ RESP2 1 when it was not acquired by
GETMAIN. Task storage is released at task end."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    one_of,
    required,
)

# the largest FLENGTH accepted (IBM: bounded by DSALIMIT / EDSALIMIT, the region's, which the run does not state)
GETMAIN_LIMIT = 268435456
# LENGTH is the compatibility halfword form (IBM: "limited to 65520 bytes")
GETMAIN_LENGTH_LIMIT = 65520

_SHARED = Refusal("SHARED storage outlives the task: only the task's own storage is modelled", "X47")
_NOSUSPEND = Refusal("storage unavailable (NOSTG) is not modelled, so NOSUSPEND has nothing to decide", "X47")

GETMAIN = Command(
    key="GETMAIN",
    ibm=ibm("EXEC CICS GETMAIN", "summary-getmain"),
    status="modelled",
    register="X47",
    options={
        "SET": Arg("pointer"),
        "FLENGTH": Arg("value"),
        "LENGTH": Arg("value"),
        "INITIMG": Arg("area_in", width=1),
        # where CICS places the storage and its key do not change the bytes the program sees (ASSUMED, X47)
        "BELOW": Arg("flag"),
        "USERDATAKEY": Arg("flag"),
        "CICSDATAKEY": Arg("flag"),
        "EXECUTABLE": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "SHARED": _SHARED,
        "NOSUSPEND": _NOSUSPEND,
    },
    default_refusal=Refusal("only SET, FLENGTH / LENGTH, INITIMG and the placement flags are modelled", "X47"),
    groups=(
        required("SET", msg="GETMAIN without SET: the pointer to the storage"),
        one_of("FLENGTH", "LENGTH", msg="GETMAIN needs one of FLENGTH / LENGTH"),
        at_most_one("USERDATAKEY", "CICSDATAKEY", msg="GETMAIN with both USERDATAKEY and CICSDATAKEY"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("SET",)),
        Outcome(
            "LENGERR",
            1,
            "FLENGTH is less than 1, or LENGTH is zero (the pointer is set to zero)",
            raised_by=("FLENGTH", "LENGTH"),
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "no INITIMG and a valid length (IBM: no default initialization, the acquired contents are undefined; "
            "a length below 1 is LENGERR before any storage exists)",
            "X47",
            java="GETMAIN without INITIMG acquired storage",
        ),
        RuntimeRefusal(
            "a length above the limit the run states (IBM's NOSTG when the request exceeds the storage available; "
            "DSALIMIT / EDSALIMIT are the region's)",
            "X47",
            java="GETMAIN length beyond the limit",
            c="GETMAIN length beyond the limit",
        ),
        RuntimeRefusal(
            "INITIMG is not one byte",
            "X47",
            java="GETMAIN INITIMG is not one byte",
            c="GETMAIN INITIMG is not one byte",
        ),
    ),
)

FREEMAIN = Command(
    key="FREEMAIN",
    ibm=ibm("EXEC CICS FREEMAIN", "summary-freemain"),
    status="modelled",
    register="X47",
    # #6876 (X47): DATA(area) names the storage by the data area a SET ADDRESS OF gave it: a 01 LINKAGE record
    options={"DATAPOINTER": Arg("pointer"), "DATA": Arg("area_in"), **RESP_OPTIONS},
    default_refusal=Refusal("DATAPOINTER and DATA are the only forms modelled", "X47"),
    groups=(
        one_of("DATAPOINTER", "DATA", msg="FREEMAIN without DATAPOINTER or DATA: the storage to release"),
        at_most_one("DATAPOINTER", "DATA", msg="FREEMAIN with both DATAPOINTER and DATA"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, ""),
        Outcome("INVREQ", 1, "The storage was not acquired by GETMAIN"),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "storage already freed (IBM does not say what a second FREEMAIN returns), or storage CICS handed over with "
            "WEB RECEIVE SET (IBM does not say whether FREEMAIN is allowed)",
            "X47",
            java="FREEMAIN of storage already freed or received",
            c="FREEMAIN of storage already freed or received",
        ),
    ),
)

# #5079 (X59), IBM CICS TS, EXEC CICS ADDRESS: EIB(ptr) / COMMAREA(ptr) set a pointer to the EXEC interface block / the
# communication area. The areas CICS keeps for the system (CWA, TWA, TCTUA, ACEE) are not modelled: the region defines none.
_SYSTEM_AREA = "the {} is a system area the region does not define: not modelled"

ADDRESS = Command(
    key="ADDRESS",
    ibm=ibm("EXEC CICS ADDRESS", "summary-address"),
    status="modelled",
    register="X59",
    options={
        "EIB": Arg("pointer"),
        "COMMAREA": Arg("pointer"),
        **RESP_OPTIONS,
    },
    refused={
        "CWA": Refusal(_SYSTEM_AREA.format("common work area (CWA)"), "X59"),
        "TWA": Refusal(_SYSTEM_AREA.format("transaction work area (TWA)"), "X59"),
        "TCTUA": Refusal(_SYSTEM_AREA.format("terminal control table user area (TCTUA)"), "X59"),
        "ACEE": Refusal(_SYSTEM_AREA.format("access control environment element (ACEE)"), "X59"),
        "SET": Refusal("ADDRESS SET (the old form, a pointer to a data area's address) is not modelled", "X59"),
    },
    default_refusal=Refusal("only EIB and COMMAREA are modelled", "X59"),
    outcomes=(Outcome("NORMAL", 0, "", writes=("EIB", "COMMAREA")),),
    runtime_refusals=(
        RuntimeRefusal(
            "ADDRESS COMMAREA when the task has no COMMAREA (IBM sets the pointer to X'FF000000', which is not the COBOL "
            "NULL a pointer handle can hold)",
            "X59",
            java="ADDRESS COMMAREA with no COMMAREA",
            c="ADDRESS COMMAREA with no COMMAREA",
        ),
    ),
)

COMMANDS = (GETMAIN, FREEMAIN, ADDRESS)
