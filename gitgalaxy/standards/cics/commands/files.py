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
RESP2: the runtimes record 0 but for READ's LENGERR (11); IBM's documented values are stated in PR 6."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, SET_POINTER, SYSID_REMOTE, ibm
from gitgalaxy.standards.cics.model import Arg, Command, EngineFacts, Outcome, Refusal

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
        "EQUAL": Arg("flag"),  # READ's default
        "KEYLENGTH": _KEYLENGTH,
        # #4436: the most the program takes; set to the record's length
        "LENGTH": Arg("area_inout", width=2, binary=True, inout_unless_literal=True),
        **RESP_OPTIONS,
    },
    refused=_READ_REFUSED,
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "LENGTH")),
        _NOTFND,
        Outcome("LENGERR", 11, "the record is longer than LENGTH: truncated", writes=("INTO", "LENGTH")),
    ),
)

READNEXT = _file(
    "READNEXT",
    "EXEC CICS READNEXT",
    "read",
    options={
        **_FILE,
        "INTO": Arg("area_out"),
        "RIDFLD": Arg("area_inout"),  # the key of the record read
        "KEYLENGTH": _KEYLENGTH,
        "LENGTH": Arg("value"),  # only INTO's own length (Cics._read_length)
        **RESP_OPTIONS,
    },
    refused=_READ_REFUSED,
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
    options=READNEXT.options,
    refused=_READ_REFUSED,
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
    options={**_NAME_ONLY, "FROM": Arg("area_in"), "LENGTH": Arg("value"), **RESP_OPTIONS},
    refused=_REMOTE,
    outcomes=(_NORMAL, Outcome("INVREQ", None, "no READ UPDATE holds a record of the file")),
)

DELETE = _file(
    "DELETE",
    "EXEC CICS DELETE",
    "delete",
    options={**_FILE, "RIDFLD": Arg("area_in"), "KEYLENGTH": _KEYLENGTH, **RESP_OPTIONS},
    refused=_REMOTE,
    outcomes=(_NORMAL, _NOTFND, Outcome("INVREQ", None, "no RIDFLD, and no READ UPDATE holds a record")),
)

COMMANDS = (READ, READNEXT, READPREV, STARTBR, ENDBR, WRITE, REWRITE, DELETE)
