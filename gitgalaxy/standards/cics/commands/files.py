# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 spec PR 2: file control -- READ / READNEXT / READPREV / STARTBR / ENDBR / WRITE / REWRITE / DELETE (#4411
OPTIONS, #4436 READ LENGTH), on a KSDS by key and an ESDS by RBA (det/cics.py Cics.read / file_update / _rba).

RBA / RRN / XRBA are accepted by OPTIONS and then refused or browsed in Cics._rba (a hole by name there). A refused
option shows no reason but SYSID's and a read's SET (the reasons the old global table gave them, true here too).
RESP2: the runtimes record 0 but for READ's LENGERR (11) and the GTEQ / GENERIC search's NOTFND (80); IBM's documented
values are stated in PR 6.

#4270 READ GTEQ / GENERIC (oracle_assumptions.md X22), IBM CICS TS, EXEC CICS READ
(https://www.ibm.com/docs/en/cics-ts/6.x?topic=summary-read):
- GENERIC: "specifies that the search key is a generic key whose length is specified in the KEYLENGTH option" -- the
  first KEYLENGTH bytes of RIDFLD; KEYLENGTH is honoured only as a known length shorter than the file's key and above
  zero (INVREQ RESP2 25: "the length specified in the KEYLENGTH option is greater than or equal to the length of a full
  key"; 42: "less than zero"; zero: undocumented) -- else refused by name.
- GTEQ: "if the search for a record that has the same key (complete or generic) as that specified in the RIDFLD option
  is unsuccessful, the first record that has a greater key is retrieved"; EQUAL: "satisfied only by a record having
  the same key (complete or generic)". Of several records with the generic key, the first in key order.
- NOTFND RESP2 80: "An attempt to retrieve a record based on the search argument provided is unsuccessful" (no record
  with the key, or with GTEQ none greater: past the end of the file).
- READ does not update RIDFLD (IBM documents that for READNEXT / READPREV only); READ UPDATE holds the record found.
- Key order: that of the browse (STARTBR), the runtimes' (oracle_assumptions.md D1)."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, SET_POINTER, SYSID_REMOTE, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    EngineFacts,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    requires,
)

# FILE / DATASET: the file's name (1-8 characters); RBA / RRN / XRBA: how RIDFLD addresses the record
_FILE: Mapping[str, Arg] = {
    "DATASET": Arg("name", width=8),
    "FILE": Arg("name", width=8),
    "RBA": Arg("flag"),
    "RRN": Arg("flag"),
    "XRBA": Arg("flag"),
}
_NAME_ONLY = {"DATASET": _FILE["DATASET"], "FILE": _FILE["FILE"]}
# KEYLENGTH: honoured only as the file's full key (Cics._keylength); a shorter one is refused there
_KEYLENGTH = Arg("value")
_REMOTE: Mapping[str, Refusal] = {"SYSID": SYSID_REMOTE}
_READ_REFUSED: Mapping[str, Refusal] = {"SYSID": SYSID_REMOTE, "SET": SET_POINTER}
# #5078 (X52): IBM lets READNEXT / READPREV take UPDATE (and TOKEN) -- a browse for update, "valid only for files accessed in RLS mode"
_BROWSE_UPDATE = Refusal(
    "a browse for update (READNEXT / READPREV UPDATE [TOKEN]) is not modelled: the region has no RLS", "X52"
)
_TOKEN_IN = Arg("value")  # a fullword the READ UPDATE TOKEN returned
_INVREQ_TOKEN = Outcome(
    "INVREQ",
    47,
    "a token whose value cannot be matched against any token in use for an existing read for UPDATE",
    raised_by=("TOKEN",),
)
_NORMAL = Outcome("NORMAL", 0, "")
_NOTFND = Outcome("NOTFND", None, "the record is not found")
_INVREQ_NO_BROWSE = Outcome("INVREQ", None, "no browse of the file was started")


def _file(key: str, title: str, access: str, **kw) -> Command:
    return Command(
        key=key,
        ibm=ibm(title, "summary-" + key.lower()),
        status="modelled",
        engine=EngineFacts(resource="FILE", access=access),
        state=("handle_table",),
        **kw,
    )


READ = _file(
    "READ",
    "EXEC CICS READ",
    "read",
    register="X14",  # READ ... INTO LENGTH (#4436)
    options={
        **_FILE,
        "INTO": Arg("area_out"),
        "RIDFLD": Arg("area_in"),
        "UPDATE": Arg("flag"),
        # #5078 (X52): "a unique identifier for this READ UPDATE request" (a fullword out); "If you specify TOKEN it implies update"
        "TOKEN": Arg("area_out", width=4, binary=True),
        "EQUAL": Arg("flag"),  # READ's default
        # #4270: GTEQ / GENERIC (a KSDS by key; GenApp LGICVS01, LGIPVS01) -- see _READ_SEARCH below
        "GTEQ": Arg("flag"),
        "GENERIC": Arg("flag"),
        "KEYLENGTH": _KEYLENGTH,
        # #4436: the most the program takes; set to the record's length
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        **RESP_OPTIONS,
    },
    refused=_READ_REFUSED,
    groups=(
        # IBM's syntax diagram: EQUAL | GTEQ, one of them (EQUAL the default)
        at_most_one("EQUAL", "GTEQ", msg="READ {} and {} together"),
        # IBM, KEYLENGTH: "You must code KEYLENGTH if you specify GENERIC"
        requires(("GENERIC",), ("KEYLENGTH",), msg="READ GENERIC without KEYLENGTH"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "LENGTH", "TOKEN")),
        _NOTFND,
        # #4270: the GTEQ / GENERIC search states IBM's RESP2 (the full-key READ still records 0, until spec PR 6)
        Outcome(
            "NOTFND",
            80,
            "An attempt to retrieve a record based on the search argument provided is unsuccessful",
            raised_by=("GTEQ", "GENERIC"),
        ),
        Outcome("LENGERR", 11, "the record is longer than LENGTH: truncated", writes=("INTO", "LENGTH")),
    ),
    runtime_refusals=(
        # IBM documents INVREQ RESP2 25 (GENERIC KEYLENGTH >= the full key) and 42 (< 0), and nothing for 0; the
        # translator refuses such a KEYLENGTH by name (Cics._keylength), the stub when the program runs
        RuntimeRefusal(
            "a GENERIC KEYLENGTH not shorter than the key, or not above zero", "X22", c="READ GENERIC KEYLENGTH"
        ),
    ),
)

READNEXT = _file(
    "READNEXT",
    "EXEC CICS READNEXT",
    "read",
    register="X52",  # UPDATE / TOKEN refused (#5078)
    options={
        **_FILE,
        "INTO": Arg("area_out"),
        "RIDFLD": Arg("area_inout"),  # the key of the record read
        "KEYLENGTH": _KEYLENGTH,
        "LENGTH": Arg("value"),  # only INTO's own length (Cics._read_length)
        **RESP_OPTIONS,
    },
    refused={**_READ_REFUSED, "UPDATE": _BROWSE_UPDATE, "TOKEN": _BROWSE_UPDATE},
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "RIDFLD")),
        Outcome("ENDFILE", None, "the end of the file is reached"),
        _INVREQ_NO_BROWSE,
    ),
)

READPREV = _file(
    "READPREV",
    "EXEC CICS READPREV",
    "read",
    register="X52",
    options=READNEXT.options,
    refused=READNEXT.refused,
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "RIDFLD")),
        Outcome("ENDFILE", None, "the start of the file is reached"),
        _INVREQ_NO_BROWSE,
    ),
)

STARTBR = _file(
    "STARTBR",
    "EXEC CICS STARTBR",
    "browse",
    options={
        **_FILE,
        "RIDFLD": Arg("area_in"),
        "EQUAL": Arg("flag"),
        "GTEQ": Arg("flag"),  # STARTBR's default
        "KEYLENGTH": _KEYLENGTH,
        **RESP_OPTIONS,
    },
    refused=_REMOTE,
    outcomes=(_NORMAL, _NOTFND, Outcome("INVREQ", None, "a browse of the file is already started")),
)

ENDBR = _file(
    "ENDBR",
    "EXEC CICS ENDBR",
    "browse",
    options={**_NAME_ONLY, **RESP_OPTIONS},
    refused=_REMOTE,
    outcomes=(_NORMAL, _INVREQ_NO_BROWSE),
)

WRITE = _file(
    "WRITE",
    "EXEC CICS WRITE",
    "write",
    options={
        **_FILE,
        "FROM": Arg("area_in"),
        "RIDFLD": Arg("area_in"),
        "LENGTH": Arg("value"),
        "KEYLENGTH": _KEYLENGTH,
        **RESP_OPTIONS,
    },
    refused=_REMOTE,
    outcomes=(_NORMAL, Outcome("DUPREC", None, "a record with the same key is already in the file")),
)

REWRITE = _file(
    "REWRITE",
    "EXEC CICS REWRITE",
    "update",
    options={**_NAME_ONLY, "FROM": Arg("area_in"), "LENGTH": Arg("value"), "TOKEN": _TOKEN_IN, **RESP_OPTIONS},
    refused=_REMOTE,
    outcomes=(
        _NORMAL,
        Outcome("INVREQ", None, "no READ UPDATE holds a record of the file"),
        _INVREQ_TOKEN,
    ),
    register="X52",
)

# #4771 (zECS ZECS003): DELETE GENERIC (IBM, EXEC CICS DELETE): GENERIC "Specifies that the search key is a generic key
# with a length specified in the KEYLENGTH option"; KEYLENGTH "must be specified if GENERIC is specified", RIDFLD too; every
# record whose key has "the same starting characters (generic key)" is deleted; NOTFND RESP2 80 when none; INVREQ RESP2 25
# (KEYLENGTH not shorter than the full key) and 42 (below zero) are refused by name, as READ GENERIC's (X22). NUMREC (the
# count) stays refused: no corpus program asks for it
DELETE = _file(
    "DELETE",
    "EXEC CICS DELETE",
    "delete",
    register="X22",
    options={
        **_FILE,
        "RIDFLD": Arg("area_in"),
        "KEYLENGTH": _KEYLENGTH,
        "GENERIC": Arg("flag"),
        "TOKEN": _TOKEN_IN,  # #5078 (X52): the record that READ UPDATE TOKEN returned the token for
        **RESP_OPTIONS,
    },
    refused=_REMOTE,
    groups=(
        at_most_one("GENERIC", "TOKEN", msg="DELETE {} and {} together"),
        at_most_one("RIDFLD", "TOKEN", msg="DELETE {} and {} together (IBM does not say)"),
        requires(("GENERIC",), ("KEYLENGTH",), msg="DELETE GENERIC without KEYLENGTH"),
        requires(("GENERIC",), ("RIDFLD",), msg="DELETE GENERIC without RIDFLD"),
    ),
    outcomes=(
        _NORMAL,
        _NOTFND,
        Outcome(
            "NOTFND",
            80,
            "An attempt to delete a record based on the search argument provided is unsuccessful",
            raised_by=("GENERIC",),
        ),
        Outcome("INVREQ", None, "no RIDFLD, and no READ UPDATE holds a record"),
        _INVREQ_TOKEN,
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a GENERIC KEYLENGTH not shorter than the key, or not above zero",
            "X22",
            c="DELETE GENERIC KEYLENGTH",
        ),
    ),
)

# #5078 (X52), IBM CICS TS, EXEC CICS UNLOCK: releases the exclusive control a READ UPDATE took. TOKEN "associates the UNLOCK
# with an earlier READ ... that used UPDATE"; a token matching none in use is INVREQ RESP2 47. UNLOCK without TOKEN (the
# file's held record) is refused at translation, #5079.
UNLOCK = _file(
    "UNLOCK",
    "EXEC CICS UNLOCK",
    "update",
    register="X52",
    options={**_NAME_ONLY, "TOKEN": _TOKEN_IN, **RESP_OPTIONS},
    refused=_REMOTE,
    outcomes=(_NORMAL, _INVREQ_TOKEN),
)

COMMANDS = (READ, READNEXT, READPREV, STARTBR, ENDBR, WRITE, REWRITE, DELETE, UNLOCK)
