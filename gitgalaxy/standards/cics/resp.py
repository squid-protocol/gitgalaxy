# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""DFHRESP and the default abend code of an unhandled condition (#4270, cics_command_spec.md section 1.2).

PR 1: the values of today's copies, which tests/core_engine/test_cics_spec_equality.py proves equal: det/cics.py's
DFHRESP (104 names: this table) and the harness's (tests/tools/equivalence_cics.py, 101: it lacks VOLIDERR, RESIDERR
and NOSPOOL), the Java switches (DetCics.condition / resp, CicsTask.respName / abcodeFor) and the C stub's enums and
condition_abcode. The crucible's own ABEND_FOR (tests/tools/crucible_events.py) is the oracle's table, never a copy
of this one (section 6)."""

from __future__ import annotations

from collections.abc import Mapping

from gitgalaxy.standards.cics.model import Doc

RESP_DOC = Doc(
    "Response codes of EXEC CICS commands",
    "https://www.ibm.com/docs/en/cics-ts/6.x?topic=codes-response-exec-cics-commands",
)

# IBM CICS TS, RESP values (DFHRESP): the condition name -> its RESP number
DFHRESP: Mapping[str, int] = {
    "NORMAL": 0, "ERROR": 1, "RDATT": 2, "WRBRK": 3, "EOF": 4, "EODS": 5, "EOC": 6, "INBFMH": 7, "ENDINPT": 8,
    "NONVAL": 9, "NOSTART": 10, "TERMIDERR": 11, "FILENOTFOUND": 12, "DSIDERR": 12, "NOTFND": 13, "DUPREC": 14,
    "DUPKEY": 15, "INVREQ": 16, "IOERR": 17, "NOSPACE": 18, "NOTOPEN": 19, "ENDFILE": 20, "ILLOGIC": 21,
    "LENGERR": 22, "QZERO": 23, "SIGNAL": 24, "QBUSY": 25, "ITEMERR": 26, "PGMIDERR": 27, "TRANSIDERR": 28,
    "ENDDATA": 29, "INVTSREQ": 30, "EXPIRED": 31, "RETPAGE": 32, "RTEFAIL": 33, "RTESOME": 34, "TSIOERR": 35,
    "MAPFAIL": 36, "INVERRTERM": 37, "INVMPSZ": 38, "IGREQID": 39, "OVERFLOW": 40, "INVLDC": 41, "NOSTG": 42,
    "JIDERR": 43, "QIDERR": 44, "NOJBUFSP": 45, "DSSTAT": 46, "SELNERR": 47, "FUNCERR": 48, "UNEXPIN": 49,
    "NOPASSBKRD": 50, "NOPASSBKWR": 51, "SYSIDERR": 53, "ISCINVREQ": 54, "ENQBUSY": 55, "ENVDEFERR": 56,
    "IGREQCD": 57, "SESSIONERR": 58, "SYSBUSY": 59, "SESSBUSY": 60, "NOTALLOC": 61, "CBIDERR": 62,
    "INVEXITREQ": 63, "INVPARTNSET": 64, "INVPARTN": 65, "PARTNFAIL": 66, "USERIDERR": 69, "NOTAUTH": 70,
    "VOLIDERR": 71, "SUPPRESSED": 72, "RESIDERR": 75, "NOSPOOL": 80, "TERMERR": 81, "ROLLEDBACK": 82, "END": 83,
    "DISABLED": 84, "ALLOCERR": 85, "STRELERR": 86, "OPENERR": 87, "SPOLBUSY": 88, "SPOLERR": 89,
    "NODEIDERR": 90, "TASKIDERR": 91, "TCIDERR": 92, "DSNNOTFOUND": 93, "LOADING": 94, "MODELIDERR": 95,
    "OUTDESCRERR": 96, "PARTNERIDERR": 97, "PROFILEIDERR": 98, "NETNAMEIDERR": 99, "LOCKED": 100,
    "RECORDBUSY": 101, "UOWNOTFOUND": 102, "UOWLNOTFOUND": 103, "CONTAINERERR": 110,
    # (BUSY 128 / INCOMPLETE 126 are in IBM's SPI table)
    "CHANNELERR": 122, "CCSIDERR": 123, "TIMEDOUT": 124, "CODEPAGEERR": 125, "INCOMPLETE": 126,
    "APPNOTFOUND": 127, "BUSY": 128,
}  # fmt: skip

# A second name for a RESP number: the number's condition name is the other one (FILENOTFOUND, the current name;
# DSIDERR, the older one, still accepted in DFHRESP(...))
ALIASES: Mapping[str, str] = {"DSIDERR": "FILENOTFOUND"}

# RESP number -> its condition name (an alias never wins)
RESP_NAME: Mapping[int, str] = {n: c for c, n in DFHRESP.items() if c not in ALIASES}


def _abend_doc(code: str) -> Doc:
    return Doc(code, f"https://www.ibm.com/docs/en/cics-ts/6.x?topic=codes-{code.lower()}")


# The abend code CICS gives a condition nobody handles (IBM's AEIx / AEYx / AEZx abend codes; the AEIA topic), as
# both runtimes and the crucible runner have it today
CONDITION_ABEND: Mapping[str, str] = {
    "NOTFND": "AEIM",
    "LENGERR": "AEIV",
    "ITEMERR": "AEIZ",
    "QIDERR": "AEYH",
    "MAPFAIL": "AEI9",
    "ENDDATA": "AEI2",
    "PGMIDERR": "AEI0",
    "INVREQ": "AEIP",
    "CONTAINERERR": "AEZJ",  # #4270: "CONTAINERERR condition not handled"
    "CHANNELERR": "AEZV",  # "CHANNELERR condition not handled"
}
ABEND_DOCS: Mapping[str, Doc] = {code: _abend_doc(code) for code in CONDITION_ABEND.values()}


def _check() -> None:
    if len(set(RESP_NAME.values())) != len(RESP_NAME):
        raise ValueError("DFHRESP: two names for one number without an alias")
    for alias, name in ALIASES.items():
        if DFHRESP[alias] != DFHRESP[name]:
            raise ValueError(f"alias {alias} is not {name}'s number")
    unknown = [c for c in CONDITION_ABEND if c not in DFHRESP]
    if unknown:
        raise ValueError(f"CONDITION_ABEND names {unknown}, not DFHRESP conditions")


_check()
