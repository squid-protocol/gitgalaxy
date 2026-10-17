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
RESP2: the runtimes record 0 but for READ's INVREQ (25 / 26 / 28 / 42, #5092) and NOTFND (80) and LENGERR (11); IBM's
other documented values are stated in PR 6.

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

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, SYSID_REMOTE, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    EngineFacts,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    one_of,
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
_READ_REFUSED: Mapping[str, Refusal] = {"SYSID": SYSID_REMOTE}
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
# #4623 (X48), IBM, READ / READNEXT / READPREV "Conditions": DUPKEY RESP2 140 -- a record retrieved through a NONUNIQUEKEY alternate
# index with another of the same key following. The record IS delivered, so DUPKEY writes what NORMAL writes.
_DUPKEY_TEXT = "a record is retrieved through a non-unique alternate index and another with the same key follows"
_DUPREC_TEXT = "a record with the same key is already in the file"
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
        # #5042 (X58): "CICS is to supply a buffer where the record is read, and specifies the pointer reference that is to
        # contain the address of the retrieved record"
        "SET": Arg("pointer"),
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
        one_of("INTO", "SET", msg="READ needs one of INTO / SET"),
        # IBM, KEYLENGTH: "You must code KEYLENGTH if you specify GENERIC"
        requires(("GENERIC",), ("KEYLENGTH",), msg="READ GENERIC without KEYLENGTH"),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "LENGTH", "TOKEN")),
        Outcome("DUPKEY", 140, _DUPKEY_TEXT, writes=("INTO", "SET", "LENGTH", "TOKEN")),
        # #5092 (X52), IBM, EXEC CICS READ: NOTFND RESP2 80 for every READ form (plain, UPDATE, TOKEN, GTEQ, GENERIC); a READ
        # UPDATE that finds nothing holds nothing. NOTFND 81 (RBA / XRBA) and the other option-gated values are refused by name
        Outcome(
            "NOTFND",
            80,
            "An attempt to retrieve a record based on the search argument provided is unsuccessful",
        ),
        # INVREQ 25 / 42 (GENERIC KEYLENGTH >= the full key / < 0) and 26 (KEYLENGTH without GENERIC, not the key's length): both
        # runtimes answer them for a given KEYLENGTH; INVREQ 20 (READ not allowed by the file's definition) is ASSUMED never to
        # arise (X52: files.cfg has no such attribute); 40, 44, 51-53, 55-57, 59 (BDAM, CFDT, RREPL, RBA / XRBA / CONSISTENT /
        # REPEATABLE / NOSUSPEND) belong to options and files the region refuses
        Outcome(
            "INVREQ",
            25,
            "the length specified in the KEYLENGTH option is greater than or equal to the length of a full key",
            raised_by=("GENERIC", "KEYLENGTH"),
        ),
        Outcome(
            "INVREQ",
            26,
            "KEYLENGTH is specified without GENERIC and is not the length of the file's key",
            raised_by=("KEYLENGTH",),
        ),
        Outcome(
            "INVREQ",
            42,
            "the length specified in the KEYLENGTH option is less than zero",
            raised_by=("GENERIC", "KEYLENGTH"),
        ),
        Outcome("LENGERR", 11, "the record is longer than LENGTH: truncated", writes=("INTO", "LENGTH")),
        # #5092 (X52): IBM, EXEC CICS READ: a READ UPDATE without TOKEN on a file with an earlier one not yet released
        Outcome(
            "INVREQ",
            28,
            "a READ UPDATE without TOKEN while an earlier one on the file has had no REWRITE, DELETE, UNLOCK or SYNCPOINT",
            raised_by=("UPDATE",),
        ),
    ),
    runtime_refusals=(
        # IBM documents INVREQ RESP2 25 (GENERIC KEYLENGTH >= the full key) and 42 (< 0), and nothing for 0; zero is
        # refused by name, by the translator (Cics._keylength) and by the stub when the program runs
        RuntimeRefusal("a GENERIC KEYLENGTH of zero", "X22", c="READ GENERIC KEYLENGTH"),
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
        "SET": Arg(
            "pointer"
        ),  # #5042 (X58): "valid until the next READNEXT or READPREV command specifies SET for the same browse"
        "RIDFLD": Arg("area_inout"),  # the key of the record read
        "KEYLENGTH": _KEYLENGTH,
        "LENGTH": Arg("value"),  # only INTO's own length (Cics._read_length)
        **RESP_OPTIONS,
    },
    refused={**_READ_REFUSED, "UPDATE": _BROWSE_UPDATE, "TOKEN": _BROWSE_UPDATE},
    groups=(one_of("INTO", "SET", msg="{} needs one of INTO / SET"),),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "RIDFLD")),
        Outcome("DUPKEY", 140, _DUPKEY_TEXT, writes=("INTO", "SET", "RIDFLD")),
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
    groups=READNEXT.groups,
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "SET", "RIDFLD")),
        Outcome("DUPKEY", 140, _DUPKEY_TEXT, writes=("INTO", "SET", "RIDFLD")),
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
    outcomes=(_NORMAL, Outcome("DUPREC", 150, _DUPREC_TEXT)),
)

REWRITE = _file(
    "REWRITE",
    "EXEC CICS REWRITE",
    "update",
    options={**_NAME_ONLY, "FROM": Arg("area_in"), "LENGTH": Arg("value"), "TOKEN": _TOKEN_IN, **RESP_OPTIONS},
    refused=_REMOTE,
    outcomes=(
        _NORMAL,
        Outcome("DUPREC", 150, _DUPREC_TEXT),
        Outcome("INVREQ", 30, "no READ UPDATE without a token holds a record of the file"),
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
        # IBM: NOTFND RESP2 80 is the only NOTFND value, for the keyed and the generic delete alike (both runtimes record it)
        Outcome("NOTFND", 80, "An attempt to delete a record based on the search argument provided is unsuccessful"),
        Outcome("INVREQ", 31, "no RIDFLD, and no READ UPDATE without a token holds a record"),
        # #5092 (X22), IBM, EXEC CICS DELETE: INVREQ 21 a file that refers to a VSAM ESDS, 22 a generic delete of a file that
        # is not a KSDS, 25 / 42 a GENERIC KEYLENGTH not shorter than the key / below zero, 26 a KEYLENGTH without GENERIC
        # that is not the key's length. Nothing is deleted. 20, 27, 44, 51, 55-57 and 59 belong to options and files the
        # region refuses or does not have (X22)
        Outcome("INVREQ", 21, "DELETE is issued for a file that refers to a VSAM ESDS"),
        Outcome("INVREQ", 22, "a generic delete is issued for a file that is not a VSAM KSDS", raised_by=("GENERIC",)),
        Outcome(
            "INVREQ",
            25,
            "the length specified in the KEYLENGTH option is greater than or equal to the length of a full key",
            raised_by=("GENERIC", "KEYLENGTH"),
        ),
        Outcome(
            "INVREQ",
            26,
            "KEYLENGTH is specified without GENERIC and is not the length of the file's key",
            raised_by=("KEYLENGTH",),
        ),
        Outcome(
            "INVREQ",
            42,
            "the length specified in the KEYLENGTH option is less than zero",
            raised_by=("GENERIC", "KEYLENGTH"),
        ),
        _INVREQ_TOKEN,
    ),
    runtime_refusals=(RuntimeRefusal("a GENERIC KEYLENGTH of zero", "X22", c="DELETE GENERIC KEYLENGTH"),),
)

# #5078 (X52), IBM CICS TS, EXEC CICS UNLOCK: releases the exclusive control a READ UPDATE took. TOKEN "associates the UNLOCK
# with an earlier READ ... that used UPDATE"; a token matching none in use is INVREQ RESP2 47. UNLOCK without TOKEN (the
# file's held record, #5079) releases the tokenless hold of the file; IBM: with none held "no action is taken and a NORMAL
# response is returned". The WRITE MASSINSERT a tokenless UNLOCK may also match is not modelled (WRITE has no MASSINSERT option: refused).
UNLOCK = _file(
    "UNLOCK",
    "EXEC CICS UNLOCK",
    "unlock",
    register="X52",
    options={**_NAME_ONLY, "TOKEN": _TOKEN_IN, **RESP_OPTIONS},
    refused=_REMOTE,
    outcomes=(_NORMAL, _INVREQ_TOKEN),
)

COMMANDS = (READ, READNEXT, READPREV, STARTBR, ENDBR, WRITE, REWRITE, DELETE, UNLOCK)
