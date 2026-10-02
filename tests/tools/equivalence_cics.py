"""
#3754: CICS online programs in the equivalence harness -- the COBOL side.

A CICS program cannot run under GnuCOBOL as written: EXEC CICS needs a translator and a
runtime. This module is both, for the harness:

* `translate` rewrites each EXEC CICS block into CALLs to a stub runtime
  (tests/equivalence/cics/ggcics.c), per command the way IBM's translator does -- it
  knows commands, never programs. DFHRESP(x) becomes its number; the EIB is an EXTERNAL
  block (tests/equivalence/cics/DFHEIBLK.cpy) the driver fills; the COMMAREA arrives
  through LINKAGE as CICS passes it; RETURN / XCTL / ABEND end the task. A command the
  translator does not know is an error naming it, never a silent skip.
* `stub_files` builds the stub's file table from the ENGINE's facts, not a hand-written
  list: each CICS file the program uses (cics_file_lineage) -> its CSD DSNAME -> the
  IDCAMS DEFINE that keys it (a PATH through its AIX to the base cluster's records).
* `run_cobol_cics` runs each scenario of a case -- a COMMAREA, the key pressed (EIBAID),
  the map input -- as one task, and returns what it did: every event in order, each
  screen it sent (field by field), the COMMAREA and TRANSID it returned, the program it
  XCTLed to.

Scenario outputs are decoded through the copybook layouts (equivalence.layout_fields),
so the Java side can be compared field by field (see equivalence_java).
"""

from __future__ import annotations

import json
import re
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from collections.abc import Iterator

import cobol_coverage as cov  # #4023
import equivalence_common as common
import equivalence_db2
import equivalence_sql

STUB = common.CASES / "cics"
LE_MODELS = common.CASES / "le"  # Language Environment service models (CEEDAYS) a CALLed subprogram may use

# The documented CICS response codes (DFHRESP) the translator replaces by number.
DFHRESP = {
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
    "SUPPRESSED": 72, "TERMERR": 81, "ROLLEDBACK": 82, "END": 83, "DISABLED": 84, "ALLOCERR": 85,
    "STRELERR": 86, "OPENERR": 87, "SPOLBUSY": 88, "SPOLERR": 89, "NODEIDERR": 90, "TASKIDERR": 91,
    "TCIDERR": 92, "DSNNOTFOUND": 93, "LOADING": 94, "MODELIDERR": 95, "OUTDESCRERR": 96, "PARTNERIDERR": 97,
    "PROFILEIDERR": 98, "NETNAMEIDERR": 99, "LOCKED": 100, "RECORDBUSY": 101, "UOWNOTFOUND": 102,
    "UOWLNOTFOUND": 103, "CHANNELERR": 122, "CCSIDERR": 123, "TIMEDOUT": 124, "CODEPAGEERR": 125,
    "INCOMPLETE": 126, "APPNOTFOUND": 127, "BUSY": 128,
}  # fmt: skip

_EXEC = re.compile(r"\bEXEC\s+CICS\b", re.I)
_END_EXEC = re.compile(r"\bEND-EXEC\b", re.I)
_DFHRESP = re.compile(r"\bDFHRESP\s*\(\s*([A-Z0-9]+)\s*\)", re.I)
_AREA_B = " " * 11  # columns 1-11: sequence area, indicator, Area A


class Unsupported(Exception):
    """A CICS command, or option, the harness does not model yet. `features` names each one
    (`LINK`, `READQ TS`, `HANDLE CONDITION`, `READ GENERIC`, ...) so a caller can count them
    (#3989: the CICS crucible runner reports cells as `unsupported: <feature>`)."""

    def __init__(self, message: str, features: list[str] | None = None) -> None:
        super().__init__(message)
        self.features = list(features) if features else [message]


# #3989: the second word that makes a command a different feature (READQ TS vs READQ TD).
_SUBVERBS = {"TS", "TD", "CONDITION", "AID", "ABEND", "HANDLE", "MAP", "TEXT", "CONTROL", "CHILD", "ANY"}


def _feature(pairs: list[tuple[str, str | None]]) -> str:
    """The command a body is, as a feature name: `LINK`, `READQ TS`, `HANDLE CONDITION`,
    `RECEIVE` (terminal input) vs `RECEIVE MAP`, `ASSIGN ABCODE`."""
    verb = pairs[0][0]
    second = pairs[1][0] if len(pairs) > 1 else None
    if verb == "ASSIGN" and second:
        return f"ASSIGN {second}"
    if verb == "RECEIVE":
        return "RECEIVE MAP" if any(n == "MAP" for n, _ in pairs) else "RECEIVE"
    return f"{verb} {second}" if second in _SUBVERBS else verb


def _options(text: str) -> list[tuple[str, str | None]]:
    """EXEC CICS body -> [(OPTION, value or None)], values paren-balanced and quote-aware."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        m = re.match(r"[A-Z0-9-]+", text[i:], re.I)
        if not m:
            raise Unsupported(f"cannot read EXEC CICS options at {text[i : i + 30]!r}")
        name, i = m.group(0).upper(), i + m.end()
        while i < n and text[i].isspace():
            i += 1
        value = None
        if i < n and text[i] == "(":
            depth, j, quote = 0, i, None
            while j < n:
                c = text[j]
                if quote:
                    quote = None if c == quote else quote
                elif c in "'\"":
                    quote = c
                elif c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            value, i = " ".join(text[i + 1 : j].split()), j + 1
        out.append((name, value))
    return out


def _call(entry: str, args: list[str]) -> list[str]:
    """`CALL 'entry' USING GG-CICS args...`, one argument per line (they can be long)."""
    return [f"CALL '{entry}' USING GG-CICS"] + [f"    {a}" for a in args]


def _transfer(labels: list[str] | None) -> list[str]:
    """#4003: GO TO the label the stub chose (GG-GOTO, 1-based into the program's HANDLE labels),
    the way IBM's translator follows a HANDLE with GO TO ... DEPENDING ON DFHEIGDI; any other value
    falls through."""
    if not labels:
        return []
    return ["GO TO"] + [f"    {label}" for label in labels] + ["    DEPENDING ON GG-GOTO"]


def _resp(opts: dict[str, str | None], can_fail: bool, labels: list[str] | None = None) -> list[str]:
    """After a command: the EIB's RESP fields, the program's RESP / RESP2, or -- when it tests
    neither and does not say NOHANDLE (which suspend every HANDLE, IBM: "The HANDLE CONDITION
    command is temporarily deactivated by the NOHANDLE or RESP option") -- the condition's
    handling (#4003, GGCCOND): IGNOREd, a HANDLE CONDITION label or the ERROR label (a GO TO), or
    the default action, an abend (whose exit may be a label here; GG-GOTO -1 leaves the program)."""
    lines = ["MOVE GG-RESP TO EIBRESP", "MOVE GG-RESP2 TO EIBRESP2"]
    if opts.get("RESP"):
        lines.append(f"MOVE GG-RESP TO {opts['RESP']}")
    if opts.get("RESP2"):
        lines.append(f"MOVE GG-RESP2 TO {opts['RESP2']}")
    if can_fail and not opts.get("RESP") and "NOHANDLE" not in opts:
        lines += (["IF GG-RESP NOT = 0", "    CALL 'GGCCOND' USING GG-CICS"]
                  + [f"    {ln}" for ln in _transfer(labels)]
                  + ["    IF GG-GOTO < 0", "        GOBACK", "    END-IF", "END-IF"])  # fmt: skip
    return lines


# #4007: the keys HANDLE AID names (IBM, EXEC CICS HANDLE AID).
AID_KEYS = frozenset(["ANYKEY", "ENTER", "CLEAR", "CLRPARTN", "LIGHTPEN", "OPERID", "TRIGGER", "PA1", "PA2", "PA3"]
                     + [f"PF{n}" for n in range(1, 25)])  # fmt: skip


def _aid(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4007: after an input command (RECEIVE MAP, terminal RECEIVE) that completed normally, HANDLE AID's
    label for the key pressed -- unless RESP or NOHANDLE suspends the handlers (IBM, RESP: "RESP implies
    NOHANDLE"). A condition the command raised is handled first (_resp); which one wins when both apply is
    not documented, and the crucible never has both."""
    if opts.get("RESP") or "NOHANDLE" in opts:
        return []
    return (["IF GG-RESP = 0", "    MOVE EIBAID TO GG-NAME1", "    CALL 'GGCAID' USING GG-CICS"]
            + [f"    {ln}" for ln in _transfer(labels)] + ["END-IF"])  # fmt: skip


# #4003: the commands whose options name the labels a program's handlers transfer to.
_HANDLE_KINDS = ("CONDITION", "ABEND", "AID")


def handler_labels(bodies: list[str]) -> list[str]:
    """Every label a program's HANDLE CONDITION / HANDLE ABEND LABEL / HANDLE AID names, in first-use
    order: GG-GOTO numbers them from 1."""
    out: list[str] = []
    for body in bodies:
        try:
            pairs = _options(body)
        except Unsupported:
            continue
        if len(pairs) < 2 or pairs[0][0] != "HANDLE" or pairs[1][0] not in _HANDLE_KINDS:
            continue
        for opt, value in pairs[2:]:
            if value and not (pairs[1][0] == "ABEND" and opt != "LABEL"):
                label = value.upper()
                if label not in out:
                    out.append(label)
    return out


def _handle(pairs: list[tuple[str, str | None]], labels: list[str]) -> list[str]:
    """#4003: HANDLE CONDITION / IGNORE CONDITION / HANDLE ABEND / PUSH / POP HANDLE / ASSIGN ABCODE."""
    verb, kind = pairs[0][0], pairs[1][0] if len(pairs) > 1 else None
    opts = dict(pairs)
    if verb in ("PUSH", "POP") and kind == "HANDLE":
        return _call("GGCPUSH" if verb == "PUSH" else "GGCPOP", []) + _resp(opts, True, labels)
    if verb == "ASSIGN":  # ABCODE (#4003); APPLID / SYSID: the region's identity, from the case's "region";
        # PROGRAM: the name of the program running (IBM CICS TS, ASSIGN: "the name of the current program")
        asked = [(n, v) for n, v in pairs[1:] if n not in ("RESP", "RESP2", "NOHANDLE")]
        other = [n for n, _v in asked if n not in ("ABCODE", "APPLID", "SYSID", "PROGRAM")]
        if other or not asked or not all(v for _n, v in asked):
            raise Unsupported(
                f"ASSIGN {' '.join(other) or 'without a target'}", [f"ASSIGN {n}" for n in other or ["?"]]
            )
        lines: list[str] = []
        for n, target in asked:
            width = {"ABCODE": 4, "APPLID": 8, "SYSID": 4, "PROGRAM": 8}[n]
            lines += ["MOVE SPACES TO GG-NAME2" if n == "ABCODE" else f"MOVE '{n}' TO GG-NAME2"] + _call("GGCASGN", [])
            lines.append(f"MOVE GG-NAME1(1:{width}) TO {target}")
        return lines + _resp(opts, False)
    if verb == "HANDLE" and kind == "AID":  # #4007
        lines = []
        for key, label in pairs[2:]:
            if key not in AID_KEYS:
                raise Unsupported(f"HANDLE AID {key}: not an attention key", ["HANDLE AID"])
            index = labels.index(label.upper()) + 1 if label else 0
            lines += [f"MOVE '{key}' TO GG-NAME1", f"MOVE {index} TO GG-ITEM"] + _call("GGCHAID", [])
        return lines
    if kind == "ABEND":
        if "PROGRAM" in opts:
            raise Unsupported("HANDLE ABEND PROGRAM", ["HANDLE ABEND PROGRAM"])
        label = opts.get("LABEL")
        if label:
            return ["MOVE 'LABEL' TO GG-NAME2", f"MOVE {labels.index(label.upper()) + 1} TO GG-ITEM",
                    f"MOVE '{label.upper()[:30]}' TO GG-FLAGS"] + _call("GGCHABN", [])  # fmt: skip
        return [f"MOVE '{'CANCEL' if 'CANCEL' in opts else 'RESET'}' TO GG-NAME2"] + _call("GGCHABN", [])
    lines: list[str] = []
    for cond, label in pairs[2:]:
        if cond not in DFHRESP or cond == "NORMAL":
            raise Unsupported(f"{verb} CONDITION {cond}: not a documented condition", [f"{verb} CONDITION"])
        index = -1 if verb == "IGNORE" else (labels.index(label.upper()) + 1 if label else 0)
        lines += [f"MOVE {DFHRESP[cond]} TO GG-NUM", f"MOVE {index} TO GG-ITEM"] + _call("GGCHCND", [])
    return lines


def _literal(value: str) -> str | None:
    m = re.fullmatch(r"'([^']*)'|\"([^\"]*)\"", value or "")
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None


def _ts_command(verb: str, opts: dict[str, str | None], labels: list[str] | None = None) -> list[str]:
    """#4002: READQ TS / WRITEQ TS -> GGCREADQ / GGCWRTQ. LENGTH is in-out on READQ (the most INTO
    takes; then the item's length, set on NORMAL and LENGERR only: IBM documents it for neither
    ITEMERR nor QIDERR). ITEM is a value on READQ (NEXT: 0) and on WRITEQ REWRITE, a data area WRITEQ
    sets otherwise; NUMITEMS is set on NORMAL."""
    feature = f"{verb} TS"
    for bad in ("SET", "SYSID"):
        if bad in opts:
            raise Unsupported(f"{feature} {bad}", [f"{feature} {bad}"])
    queue = opts.get("QUEUE") or opts.get("QNAME")
    area = opts.get("INTO") if verb == "READQ" else opts.get("FROM")
    if not queue or not area:
        raise Unsupported(f"{feature} without QUEUE / {'INTO' if verb == 'READQ' else 'FROM'}", [feature])
    length, item, num = opts.get("LENGTH") or opts.get("FLENGTH"), opts.get("ITEM"), opts.get("NUMITEMS")
    lines = [f"MOVE {queue} TO GG-QNAME", f"MOVE {length or f'LENGTH OF {area}'} TO GG-LEN"]
    after = []
    if verb == "READQ":
        lines.append(f"MOVE {item} TO GG-ITEM" if item and "NEXT" not in opts else "MOVE 0 TO GG-ITEM")
        lines += _call("GGCREADQ", [f"BY REFERENCE {area}"])
        if length:
            after += ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"]
    else:
        rewrite = "REWRITE" in opts
        if rewrite and not item:
            raise Unsupported(f"{feature} REWRITE without ITEM", [feature])
        lines += [f"MOVE {item if rewrite else 0} TO GG-ITEM",
                  "MOVE 'REWRITE' TO GG-FLAGS" if rewrite else "MOVE SPACES TO GG-FLAGS"]  # fmt: skip
        lines += _call("GGCWRTQ", [f"BY REFERENCE {area}"])
        if item and not rewrite:
            after += ["IF GG-RESP = 0", f"    MOVE GG-ITEM TO {item}", "END-IF"]
    if num:
        after += ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {num}", "END-IF"]
    return lines + after + _resp(opts, True, labels)


def _interval_command(verb: str, opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4006: START -> GGCSTRT (the request is an event; the runner's scheduler dispatches it), RETRIEVE
    -> GGCRTRV (LENGTH in-out, set back on NORMAL / LENGERR), CANCEL REQID -> GGCCNCL."""
    refused = {"START": ("AFTER", "AT", "HOURS", "MINUTES", "SECONDS", "RTRANSID", "RTERMID", "QUEUE", "SYSID",
                         "USERID", "CHANNEL", "NOCHECK", "ATTACH", "BREXIT"),
               "RETRIEVE": ("SET", "RTRANSID", "RTERMID", "QUEUE", "WAIT"),
               "CANCEL": ("TRANSID", "SYSID", "ACTIVITY", "ACQACTIVITY", "ACQPROCESS")}[verb]  # fmt: skip
    bad = [o for o in refused if o in opts]
    if bad:
        raise Unsupported(f"{verb} {' '.join(bad)}", [f"{verb} {o}" for o in bad])
    if verb == "START":
        if not opts.get("TRANSID"):
            raise Unsupported("START without TRANSID", ["START"])
        area = opts.get("FROM")
        when = "TIME" if opts.get("TIME") is not None else "INTERVAL"
        flags = " ".join([when] + (["PROTECT"] if "PROTECT" in opts else []))
        length = opts.get("LENGTH") or opts.get("FLENGTH") or (f"LENGTH OF {area}" if area else "0")
        lines = [f"MOVE {opts['TRANSID']} TO GG-NAME1",
                 f"MOVE {opts['TERMID']} TO GG-NAME2" if opts.get("TERMID") else "MOVE SPACES TO GG-NAME2",
                 f"MOVE {opts['REQID']} TO GG-QNAME" if opts.get("REQID") else "MOVE SPACES TO GG-QNAME",
                 f"MOVE {opts.get(when) or 0} TO GG-NUM", f"MOVE '{flags}' TO GG-FLAGS", f"MOVE {length} TO GG-LEN",
                 f"MOVE {1 if area else 0} TO GG-ITEM"]  # fmt: skip
        return lines + _call("GGCSTRT", [f"BY REFERENCE {area or 'GG-FLAGS'}"]) + _resp(opts, True, labels)
    if verb == "RETRIEVE":
        into = opts.get("INTO")
        if not into:
            raise Unsupported("RETRIEVE without INTO", ["RETRIEVE"])
        length = opts.get("LENGTH") or opts.get("FLENGTH")
        lines = [f"MOVE {length or f'LENGTH OF {into}'} TO GG-LEN"] + _call("GGCRTRV", [f"BY REFERENCE {into}"])
        if length:
            lines += ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"]
        return lines + _resp(opts, True, labels)
    if not opts.get("REQID"):
        raise Unsupported("CANCEL without REQID", ["CANCEL without REQID"])
    return [f"MOVE {opts['REQID']} TO GG-QNAME"] + _call("GGCCNCL", []) + _resp(opts, True, labels)


def translate_command(body: str, labels: list[str] | None = None, handle_aid: bool = False) -> list[str]:
    """One EXEC CICS body -> the COBOL statements that replace it. `labels` are the program's HANDLE
    labels (handler_labels), which a condition or abend exit GOes TO (#4003); by default, this
    command's own. `handle_aid`: the program issues HANDLE AID, so its input commands consult it (#4007)."""
    pairs = _options(body)
    if not pairs:
        raise Unsupported("empty EXEC CICS")
    labels = handler_labels([body]) if labels is None else labels
    opts = dict(pairs)
    verb = pairs[0][0]
    flags = [n for n, v in pairs[1:] if v is None and n not in ("NOHANDLE",)]

    def name(operand: str | None, into: str) -> str:
        return f"MOVE {operand} TO {into}" if operand else f"MOVE SPACES TO {into}"

    if verb == "READ":
        for bad in ("GENERIC", "GTEQ", "SET", "SYSID", "RBA", "RRN", "TOKEN"):
            if bad in opts:
                raise Unsupported(f"READ {bad}")
        file, into, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("INTO"), opts.get("RIDFLD")
        if not (file and into and ridfld):
            raise Unsupported("READ without FILE / INTO / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        update = "MOVE 'UPDATE' TO GG-FLAGS" if "UPDATE" in opts else "MOVE SPACES TO GG-FLAGS"  # holds the record
        return ([name(file, "GG-NAME1"), update]
                + _call("GGCREAD", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {into}",
                                    f"BY VALUE LENGTH OF {into}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "WRITE" and {"FILE", "DATASET"} & set(opts):
        for bad in ("MASSINSERT", "SYSID", "RBA", "RRN"):
            if bad in opts:
                raise Unsupported(f"WRITE {bad}")
        file, frm, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("FROM"), opts.get("RIDFLD")
        if not (file and frm and ridfld):
            raise Unsupported("WRITE without FILE / FROM / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        return ([name(file, "GG-NAME1")]
                + _call("GGCWRIT", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {frm}",
                                    f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {frm}'}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "REWRITE" and ({"FILE", "DATASET"} & set(opts)):
        for bad in ("SYSID", "TOKEN"):
            if bad in opts:
                raise Unsupported(f"REWRITE {bad}")
        file, frm = opts.get("FILE") or opts.get("DATASET"), opts.get("FROM")
        if not (file and frm):
            raise Unsupported("REWRITE without FILE / FROM")
        length = opts.get("LENGTH") or f"LENGTH OF {frm}"  # LENGTH bytes from FROM's first, as CICS reads them
        return ([name(file, "GG-NAME1")] + _call("GGCREWR", [f"BY REFERENCE {frm}", f"BY VALUE {length}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "STARTBR":  # browse (CardDemo's lists): one browse per file, full keys
        for bad in ("GENERIC", "REQID", "SYSID", "RBA", "RRN", "XRBA", "DEBKEY", "DEBREC"):
            if bad in opts:
                raise Unsupported(f"STARTBR {bad}")
        file, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("RIDFLD")
        if not (file and ridfld):
            raise Unsupported("STARTBR without FILE / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        mode = "MOVE 'EQUAL' TO GG-FLAGS" if "EQUAL" in opts else "MOVE SPACES TO GG-FLAGS"  # GTEQ is the default
        return ([name(file, "GG-NAME1"), mode] + _call("GGCSTBR", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb in ("READNEXT", "READPREV"):
        for bad in ("GENERIC", "REQID", "SYSID", "RBA", "RRN", "XRBA", "SET", "UPDATE", "TOKEN", "NOSUSPEND"):
            if bad in opts:
                raise Unsupported(f"{verb} {bad}")
        file, into, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("INTO"), opts.get("RIDFLD")
        if not (file and into and ridfld):
            raise Unsupported(f"{verb} without FILE / INTO / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        stub = "GGCRDNX" if verb == "READNEXT" else "GGCRDPV"
        return ([name(file, "GG-NAME1")]
                + _call(stub, [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {into}",
                               f"BY VALUE LENGTH OF {into}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "ENDBR":
        for bad in ("REQID", "SYSID"):
            if bad in opts:
                raise Unsupported(f"ENDBR {bad}")
        file = opts.get("FILE") or opts.get("DATASET")
        if not file:
            raise Unsupported("ENDBR without FILE")
        return [name(file, "GG-NAME1")] + _call("GGCENBR", []) + _resp(opts, True, labels)
    if verb == "DELETE" and ({"FILE", "DATASET"} & set(opts)):
        for bad in ("GENERIC", "REQID", "SYSID", "RBA", "RRN", "TOKEN", "NOSUSPEND", "NUMREC"):
            if bad in opts:
                raise Unsupported(f"DELETE {bad}")
        file, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("RIDFLD")
        if ridfld:  # the record with that key
            keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
            args = [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}"]
            mode = "MOVE SPACES TO GG-FLAGS"
        else:  # the record a READ UPDATE holds
            args, mode = ["BY REFERENCE GG-FLAGS", "BY VALUE 0"], "MOVE 'HELD' TO GG-FLAGS"
        return [name(file, "GG-NAME1"), mode] + _call("GGCDELT", args) + _resp(opts, True, labels)
    if verb == "ASKTIME":  # the task's clock; a task takes no time, so EIBDATE / EIBTIME stay as dispatched
        if not opts.get("ABSTIME"):
            return ["CONTINUE"]
        return ["MOVE FUNCTION CURRENT-DATE(1:8) TO GG-YMD", "MOVE FUNCTION CURRENT-DATE(9:8) TO GG-HMSC",
                f"COMPUTE {opts['ABSTIME']} =", "    (FUNCTION INTEGER-OF-DATE(GG-DATE8)",
                "    - FUNCTION INTEGER-OF-DATE(19000101)) * 86400000",
                "    + GG-HH * 3600000 + GG-MI * 60000", "    + GG-SS * 1000 + GG-CS * 10"]  # fmt: skip
    if verb == "FORMATTIME":
        return _formattime(opts)
    if verb == "SYNCPOINT":
        mode = "MOVE 'ROLLBACK' TO GG-FLAGS" if "ROLLBACK" in opts else "MOVE SPACES TO GG-FLAGS"
        return [mode] + _call("GGCSYNC", []) + _resp(opts, False, labels)
    if verb == "INQUIRE" and "PROGRAM" in opts:  # #4023 follow-up: is the program installed (COMEN01C's option check)
        extra = sorted(set(opts) - {"INQUIRE", "PROGRAM", "NOHANDLE", "RESP", "RESP2"})
        if extra or not opts["PROGRAM"]:
            raise Unsupported(f"INQUIRE PROGRAM {' '.join(extra) or 'without a name'}", ["INQUIRE PROGRAM"])
        return [name(opts["PROGRAM"], "GG-NAME1")] + _call("GGCINQP", []) + _resp(opts, True, labels)
    if verb == "RECEIVE" and "MAP" in opts:
        into = opts.get("INTO") or (f"{_literal(opts['MAP'])}I" if _literal(opts["MAP"]) else None)
        if not into:
            raise Unsupported("RECEIVE MAP(data-name) without INTO")
        return ([name(opts["MAP"], "GG-NAME1"), name(opts.get("MAPSET") or opts["MAP"], "GG-NAME2")]
                + _call("GGCRECV", [f"BY REFERENCE {into}", f"BY VALUE LENGTH OF {into}"])
                + _resp(opts, True, labels) + (_aid(opts, labels) if handle_aid else []))  # fmt: skip
    if verb == "RECEIVE":  # #4005: terminal input, unformatted (SPEC 5: the step's `text`)
        for bad in ("SET", "NOTRUNCATE", "BUFFER", "PARTN", "SESSION", "CONVID", "LDC"):
            if bad in opts:
                raise Unsupported(f"RECEIVE {bad}", [f"RECEIVE {bad}"])
        into = opts.get("INTO")
        if not into:
            raise Unsupported("RECEIVE without INTO", ["RECEIVE"])
        # LENGTH / FLENGTH is in-out: in, the most INTO takes (unless MAXLENGTH / MAXFLENGTH says so);
        # out, the length of the data. COBOL may omit it: the translator supplies LENGTH OF INTO.
        length = opts.get("LENGTH") or opts.get("FLENGTH")
        limit = opts.get("MAXLENGTH") or opts.get("MAXFLENGTH") or length or f"LENGTH OF {into}"
        lines = [f"MOVE {limit} TO GG-LEN"] + _call("GGCRECT", [f"BY REFERENCE {into}"])
        if length:
            lines.append(f"MOVE GG-LEN TO {length}")
        return lines + _resp(opts, True, labels) + (_aid(opts, labels) if handle_aid else [])
    if verb == "WRITEQ" and "TD" in opts:  # transient data: a record on an extrapartition / intrapartition queue
        for bad in ("SYSID",):
            if bad in opts:
                raise Unsupported(f"WRITEQ TD {bad}", [f"WRITEQ TD {bad}"])
        queue, frm = opts.get("QUEUE"), opts.get("FROM")
        if not (queue and frm):
            raise Unsupported("WRITEQ TD without QUEUE / FROM", ["WRITEQ TD"])
        return ([name(queue, "GG-QNAME"), f"MOVE {opts.get('LENGTH') or 'LENGTH OF ' + frm} TO GG-LEN"]
                + _call("GGCWRTD", [f"BY REFERENCE {frm}"]) + _resp(opts, True, labels))  # fmt: skip
    if verb in ("READQ", "WRITEQ") and "TD" not in opts:  # #4002: temporary storage (TS is the default)
        return _ts_command(verb, opts, labels)
    if verb == "SEND" and "MAP" in opts:
        lines = [name(opts["MAP"], "GG-NAME1"), name(opts.get("MAPSET") or opts["MAP"], "GG-NAME2")]
        mapflags = [n for n, _v in pairs[1:] if n in ("ERASE", "ERASEAUP", "MAPONLY", "DATAONLY", "CURSOR",
                                                       "FREEKB", "ALARM", "FRSET", "PRINT")]  # fmt: skip
        lines.append(f"MOVE '{' '.join(mapflags)[:40]}' TO GG-FLAGS" if mapflags else "MOVE SPACES TO GG-FLAGS")
        lines.append(f"MOVE {opts.get('CURSOR') or '-1'} TO GG-LEN")  # #4001: CURSOR(n); -1: none given
        if "MAPONLY" in opts:
            args = ["BY REFERENCE GG-FLAGS", "BY VALUE 0"]
        else:
            src = opts.get("FROM") or (f"{_literal(opts['MAP'])}O" if _literal(opts["MAP"]) else None)
            if not src:
                raise Unsupported("SEND MAP(data-name) without FROM")
            args = [f"BY REFERENCE {src}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {src}'}"]
        return lines + _call("GGCSMAP", args) + _resp(opts, can_fail=False)
    if verb == "SEND" and ("TEXT" in opts or "FROM" in opts) and "CONTROL" not in opts:
        src = opts.get("FROM")
        if not src:
            raise Unsupported("SEND TEXT without FROM")
        kind = ["TEXT"] if "TEXT" in opts else ["DATA"]
        textflags = " ".join(kind + [n for n in flags if n in ("ERASE", "FREEKB", "ALARM", "WAIT", "LAST")])
        return ([f"MOVE '{textflags[:40]}' TO GG-FLAGS"]
                + _call("GGCSTXT", [f"BY REFERENCE {src}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {src}'}"])
                + _resp(opts, can_fail=False))  # fmt: skip
    if verb in ("RETURN", "XCTL"):
        if verb == "XCTL" and not opts.get("PROGRAM"):
            raise Unsupported("XCTL without PROGRAM")
        for bad in ("CHANNEL", "INPUTMSG", "IMMEDIATE", "ENDACTIVITY"):
            if bad in opts:
                raise Unsupported(f"{verb} {bad}")
        target = opts.get("TRANSID") if verb == "RETURN" else opts.get("PROGRAM")
        area = opts.get("COMMAREA")
        args = ([f"BY REFERENCE {area}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {area}'}"] if area
                else ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])  # fmt: skip
        if verb == "RETURN":
            return [name(target, "GG-NAME1")] + _call("GGCRETN", args) + ["GOBACK"]
        # #4008: a failed XCTL (LENGERR, PGMIDERR) leaves control here, through the condition handling
        return ([name(target, "GG-NAME1"), f"MOVE {1 if area else 0} TO GG-ITEM"] + _call("GGCXCTL", args)
                + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
    if verb in ("START", "RETRIEVE", "CANCEL"):  # #4006: interval control
        return _interval_command(verb, opts, labels)
    if verb == "LINK":  # #4004: a new level runs the program on the caller's own COMMAREA storage
        for bad in ("SYSID", "TRANSID", "SYNCONRETURN", "CHANNEL", "INPUTMSG", "INPUTMSGLEN", "DATALENGTH"):
            if bad in opts:
                raise Unsupported(f"LINK {bad}", [f"LINK {bad}"])
        if not opts.get("PROGRAM"):
            raise Unsupported("LINK without PROGRAM", ["LINK"])
        area = opts.get("COMMAREA")
        length = opts.get("LENGTH") or opts.get("FLENGTH") or (f"LENGTH OF {area}" if area else "0")
        ref = area or "GG-FLAGS"
        return ([name(opts["PROGRAM"], "GG-NAME1"), f"MOVE {length} TO GG-LEN", f"MOVE {1 if area else 0} TO GG-ITEM"]
                + _call("GGCLINK", [f"BY REFERENCE {ref}"])
                + ["IF GG-RESP = 0", f"    CALL 'GGCRUN' USING {ref}", "    CALL 'GGCLRET' USING GG-CICS"]
                + [f"    {ln}" for ln in _transfer(labels)]
                + ["    IF GG-GOTO < 0", "        GOBACK", "    END-IF", "END-IF"]
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "ABEND":  # #4003: an exit at this level takes it by GO TO; else the program is left
        return ([name(opts.get("ABCODE"), "GG-NAME1"), "MOVE 'CANCEL' TO GG-FLAGS" if "CANCEL" in opts else "MOVE SPACES TO GG-FLAGS"]
                + _call("GGCABND", []) + _transfer(labels) + ["GOBACK"])  # fmt: skip
    if (
        (verb in ("HANDLE", "IGNORE") and len(pairs) > 1 and pairs[1][0] in ("CONDITION", "ABEND", "AID"))
        or (verb in ("PUSH", "POP") and len(pairs) > 1 and pairs[1][0] == "HANDLE")
        or verb == "ASSIGN"
    ):
        return _handle(pairs, labels)  # fmt: skip
    raise Unsupported(" ".join(n for n, _ in pairs[:2]), [_feature(pairs)])


def _exec_blocks(lines: list[str]) -> Iterator[tuple[int, int, str, str, str]]:
    """Each EXEC CICS block of a fixed-format program: (first line, last line, the code before
    it, its body, the code after END-EXEC)."""
    i = 0
    while i < len(lines):
        line = lines[i]
        code = line[7:72] if len(line) > 7 else ""
        start = _EXEC.search(code)
        if (len(line) > 6 and line[6] in "*/") or not start:
            i += 1
            continue
        prefix, body, j = code[: start.start()], code[start.end() :], i
        while not _END_EXEC.search(body):
            j += 1
            if j >= len(lines):
                raise Unsupported(f"EXEC CICS at line {i + 1} has no END-EXEC")
            nxt = lines[j]
            if len(nxt) > 6 and nxt[6] in "*/":
                continue
            if len(nxt) > 6 and nxt[6] == "-":
                raise Unsupported(f"continuation line inside EXEC CICS at line {j + 1}")
            body += " " + (nxt[7:72] if len(nxt) > 7 else "")
        end = _END_EXEC.search(body)
        assert end is not None
        yield i, j, prefix, body[: end.start()], body[end.end() :]
        i = j + 1


def translate(source: str) -> tuple[str, bool]:
    """A fixed-format CICS program -> (the program the stub runtime runs, whether it takes a
    COMMAREA through LINKAGE). Raises Unsupported naming each command it cannot model."""
    lines = source.splitlines()
    blocks = list(_exec_blocks(lines))
    labels = handler_labels([b[3] for b in blocks])  # #4003: what GG-GOTO indexes, program-wide
    handle_aid = any(re.match(r"\s*HANDLE\s+AID\b", b[3], re.I) for b in blocks)  # #4007
    out: list[str] = []
    problems: list[str] = []
    features: list[str] = []
    at = 0
    for i, j, prefix, body, suffix in blocks:
        out += lines[at:i]
        at = j + 1
        line = lines[i]
        if prefix.strip():
            out.append(line[:7] + prefix.rstrip())
        try:
            stmts = translate_command(body, labels, handle_aid)
        except Unsupported as e:
            problems.append(f"line {i + 1}: EXEC CICS {e}")
            features += [f for f in e.features if f not in features]
            stmts = []
        for s in stmts:
            if len(_AREA_B) + len(s) > 72:
                raise Unsupported(f"line {i + 1}: generated statement too long: {s}")
            out.append(_AREA_B + s)
        if suffix.strip():
            out.append(_AREA_B + suffix.strip())
    out += lines[at:]
    unknown = sorted({m.group(1).upper() for ln in out for m in _DFHRESP.finditer(ln)} - set(DFHRESP))
    for name in unknown:  # #3989: refused by name, never a KeyError
        problems.append(f"DFHRESP({name}) is not a documented condition")
        features.append(f"DFHRESP({name})")
    if problems:
        raise Unsupported("; ".join(problems), features)
    text = "\n".join(_DFHRESP.sub(lambda m: str(DFHRESP[m.group(1).upper()]), ln) for ln in out) + "\n"
    has_commarea = bool(re.search(r"^.{6} +01\s+DFHCOMMAREA\b", text, re.M | re.I))
    text = re.sub(r"^(.{6} +WORKING-STORAGE\s+SECTION\.[^\n]*\n)", r"\1       COPY DFHEIBLK.\n", text,
                  count=1, flags=re.M | re.I)  # fmt: skip
    if "COPY DFHEIBLK" not in text:
        raise Unsupported("no WORKING-STORAGE SECTION to hold the EIB")
    already = re.search(r"^.{6} +PROCEDURE\s+DIVISION\s+USING\s+DFHCOMMAREA\s*\.", text, re.M | re.I)
    if has_commarea and not already:  # (CBSA's ABNDPROC codes USING DFHCOMMAREA itself, as CICS allows)
        text, n = re.subn(r"^(.{6} +PROCEDURE\s+DIVISION)\s*\.", r"\1 USING DFHCOMMAREA.", text, count=1,
                          flags=re.M | re.I)  # fmt: skip
        if n != 1:
            raise Unsupported("PROCEDURE DIVISION header not found (or already has USING)")
    # #4003: the program names itself to the stub as it starts (the level's program, for an abend exit)
    pid = re.search(r"^.{6} +PROGRAM-ID\.?\s+['\"]?([A-Z0-9#@$-]+)", text, re.M | re.I)
    if pid is None:
        raise Unsupported("no PROGRAM-ID")
    if re.search(r"^.{6} +DECLARATIVES\s*\.", text, re.M | re.I):
        raise Unsupported("DECLARATIVES", ["DECLARATIVES"])
    entry = f"{_AREA_B}MOVE '{pid.group(1).upper()[:8]}' TO GG-NAME1\n{_AREA_B}CALL 'GGCPENT' USING GG-CICS.\n"
    text, n = re.subn(r"^(.{6} +PROCEDURE\s+DIVISION\b[^.\n]*\.[^\n]*\n)", lambda m: m.group(1) + entry, text,
                      count=1, flags=re.M | re.I)  # fmt: skip
    if n != 1:
        raise Unsupported("PROCEDURE DIVISION header not on one line")
    return text, has_commarea


def cics_driver(program: str, has_commarea: bool) -> str:
    """Runs one task: the EIB from $EIBIN (TRANSID, AID name, date, time), the COMMAREA
    from the stub (its length is EIBCALEN), then the program, then GGCEND."""
    aid_names = [ln.split()[1] for ln in (STUB / "DFHAID.cpy").read_text().splitlines() if " PIC " in ln]
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. EQCICSDR.", "ENVIRONMENT DIVISION.",
             "INPUT-OUTPUT SECTION.", "FILE-CONTROL.",
             "    SELECT EIB-IN ASSIGN TO EIBIN ORGANIZATION LINE SEQUENTIAL.",
             "DATA DIVISION.", "FILE SECTION.", "FD  EIB-IN.", "01  EIB-LINE.",
             "    05 IN-TRNID PIC X(4).", "    05 FILLER   PIC X.", "    05 IN-AID   PIC X(8).",
             "    05 FILLER   PIC X.", "    05 IN-DATE  PIC 9(7).", "    05 FILLER   PIC X.",
             "    05 IN-TIME  PIC 9(7).",
             "WORKING-STORAGE SECTION.", "COPY DFHEIBLK.", "COPY DFHAID.",
             "01  WS-CA  PIC X(32767).", "01  WS-LEN PIC S9(9) COMP-5.",
             "PROCEDURE DIVISION.",
             "    OPEN INPUT EIB-IN", "    READ EIB-IN", "    CLOSE EIB-IN",
             "    INITIALIZE DFHEIBLK GG-CICS",
             "    MOVE IN-TRNID TO EIBTRNID", "    MOVE IN-DATE TO EIBDATE", "    MOVE IN-TIME TO EIBTIME",
             "    EVALUATE IN-AID"]  # fmt: skip
    lines += [f"        WHEN '{n}' MOVE {n} TO EIBAID" for n in aid_names]
    lines += ["    END-EVALUATE", "    MOVE LOW-VALUES TO WS-CA",
              "    CALL 'GGCLOAD' USING WS-CA BY VALUE LENGTH OF WS-CA", "        RETURNING WS-LEN",
              "    MOVE WS-LEN TO EIBCALEN",
              f"    CALL '{program}'" + (" USING WS-CA" if has_commarea else ""),
              "    CALL 'GGCAOUT' USING WS-CA BY VALUE WS-LEN",
              "    CALL 'GGCEND' USING GG-CICS", "    STOP RUN."]  # fmt: skip
    assert all(len(ln) <= 65 for ln in lines), [ln for ln in lines if len(ln) > 65]
    return "".join("       " + ln + "\n" for ln in lines)


def task_driver() -> str:
    """#4004: the driver of a task on the stub, one process per task: the EIB from $EIBIN (TRANSID, AID
    name, date, time, the first program, the terminal), the COMMAREA from the stub (its length is
    EIBCALEN), then GGCRUN (task_dispatcher) runs the program and whatever it XCTLs to."""
    aid_names = [ln.split()[1] for ln in (STUB / "DFHAID.cpy").read_text().splitlines() if " PIC " in ln]
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. GGTASK.", "ENVIRONMENT DIVISION.",
             "INPUT-OUTPUT SECTION.", "FILE-CONTROL.",
             "    SELECT EIB-IN ASSIGN TO EIBIN ORGANIZATION LINE SEQUENTIAL.",
             "DATA DIVISION.", "FILE SECTION.", "FD  EIB-IN.", "01  EIB-LINE.",
             "    05 IN-TRNID PIC X(4).", "    05 FILLER   PIC X.", "    05 IN-AID   PIC X(8).",
             "    05 FILLER   PIC X.", "    05 IN-DATE  PIC 9(7).", "    05 FILLER   PIC X.",
             "    05 IN-TIME  PIC 9(7).", "    05 FILLER   PIC X.", "    05 IN-PROG  PIC X(8).",
             "    05 FILLER   PIC X.", "    05 IN-TRMID PIC X(4).",
             "WORKING-STORAGE SECTION.", "COPY DFHEIBLK.", "COPY DFHAID.",
             "01  WS-CA  PIC X(32767).", "01  WS-LEN PIC S9(9) COMP-5.",
             "PROCEDURE DIVISION.",
             "    OPEN INPUT EIB-IN", "    READ EIB-IN", "    CLOSE EIB-IN",
             "    INITIALIZE DFHEIBLK GG-CICS",
             "    MOVE IN-TRNID TO EIBTRNID", "    MOVE IN-DATE TO EIBDATE", "    MOVE IN-TIME TO EIBTIME",
             "    MOVE IN-TRMID TO EIBTRMID",
             "    EVALUATE IN-AID"]  # fmt: skip
    lines += [f"        WHEN '{n}' MOVE {n} TO EIBAID" for n in aid_names]
    lines += ["    END-EVALUATE", "    MOVE LOW-VALUES TO WS-CA",
              "    CALL 'GGCLOAD' USING WS-CA BY VALUE LENGTH OF WS-CA", "        RETURNING WS-LEN",
              "    MOVE WS-LEN TO EIBCALEN", "    MOVE IN-PROG TO GG-NAME1", "    MOVE WS-LEN TO GG-LEN",
              "    CALL 'GGCTASK' USING GG-CICS", "    CALL 'GGCRUN' USING WS-CA",
              "    CALL 'GGCAOUT' USING WS-CA BY VALUE WS-LEN",
              "    CALL 'GGCEND' USING GG-CICS", "    STOP RUN."]  # fmt: skip
    assert all(len(ln) <= 65 for ln in lines), [ln for ln in lines if len(ln) > 65]
    return "".join("       " + ln + "\n" for ln in lines)


def task_dispatcher(programs: dict[str, bool]) -> str:
    """#4004: GGCRUN, the case's dispatcher: at one program level (the task's, or a LINK's), run the
    program the stub names (GGCNEXT) on the level's COMMAREA -- the caller's own storage for a LINK,
    a copy for an XCTL -- with EIBCALEN set, then any program it XCTLs to. RECURSIVE, since a LINK
    CALLs it again; each program is CANCELed after its run, so that the next run starts with fresh
    WORKING-STORAGE, as a new CICS program instance does. `programs`: {name: takes a COMMAREA}."""
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. GGCRUN RECURSIVE.", "DATA DIVISION.",
             "WORKING-STORAGE SECTION.", "COPY DFHEIBLK.", "LOCAL-STORAGE SECTION.",
             "01  LS-CALEN   PIC S9(4) COMP.", "01  LS-PTR     USAGE POINTER.", "01  LS-PROG    PIC X(8).",
             "LINKAGE SECTION.", "01  LK-AREA    PIC X(32767).", "01  LK-X       PIC X(32767).",
             "PROCEDURE DIVISION USING LK-AREA.",
             "    MOVE EIBCALEN TO LS-CALEN",
             "    PERFORM WITH TEST AFTER UNTIL GG-ITEM = 0",
             "      SET LS-PTR TO ADDRESS OF LK-AREA",
             "      CALL 'GGCNEXT' USING GG-CICS LS-PTR",
             "      IF GG-ITEM NOT = 0",
             "        MOVE GG-LEN TO EIBCALEN",
             "        MOVE GG-NAME1 TO LS-PROG",
             "        SET ADDRESS OF LK-X TO LS-PTR",
             "        EVALUATE LS-PROG"]  # fmt: skip
    for prog, takes in sorted(programs.items()):
        lines += [f"          WHEN '{prog}'", f"            CALL '{prog}'" + (" USING LK-X" if takes else ""),
                  f"            CANCEL '{prog}'"]  # fmt: skip
    if programs:
        lines += ["          WHEN OTHER", "            CALL 'GGCNOPG' USING GG-CICS", "        END-EVALUATE"]
    else:  # no program to run (the equivalence harness's one-program case): GnuCOBOL wants a WHEN before OTHER
        lines[-1] = "        CALL 'GGCNOPG' USING GG-CICS"
    lines += ["        CALL 'GGCPEND' USING GG-CICS", "        MOVE 1 TO GG-ITEM", "      END-IF",
              "    END-PERFORM", "    MOVE LS-CALEN TO EIBCALEN", "    GOBACK."]  # fmt: skip
    assert all(len(ln) <= 65 for ln in lines), [ln for ln in lines if len(ln) > 65]
    return "".join("       " + ln + "\n" for ln in lines)


# ---- the stub's files, from the engine's facts ----------------------------------------
def stub_files(ir: Any, program_file: str, datasets: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Each CICS file the program uses: {file, dsname, base (the cluster whose records it
    reads), key_offset, key_length, reclen, via}, from the engine's facts -- the CSD
    DEFINE FILE's DSNAME, then the IDCAMS DEFINE that keys it: a CLUSTER's KEYS, or a
    PATH -> its AIX's KEYS over the AIX's base cluster. Where the facts lack the KEYS or the
    RECORDSIZE (GenApp's adef121.jcl gives both inside the DATA(...) component), the case's
    dataset may state them ("vsam": {"key_offset", "key_length", "reclen"}); the facts win."""
    defines: dict[str, Any] = {}
    for f in ir.files.values():
        for d in f.vsam_defines:
            if d.name:
                defines.setdefault(d.name.upper(), d)
    out = []
    for e in ir.cics_file_lineage():
        if e["program"] != program_file:
            continue
        defs = [d for d in e["definitions"] if d.get("dsname")]
        if not defs:
            raise Unsupported(f"CICS file {e['name']}: no CSD DEFINE FILE with a DSNAME")
        dsn = defs[0]["dsname"].upper()
        d, via = defines.get(dsn), []
        if d is not None and d.kind == "PATH":
            via.append(f"PATH {d.name}")
            d = defines.get((d.related or "").upper())
        if d is None:  # #3656: the engine's candidate join of an IDCAMS name written with installation symbols
            st = next((x for x in ir.vsam_stores() if (x.get("dataset") or "").upper() == dsn and x.get("defined")
                       and (x.get("defined_by") or {}).get("match") == "symbolic"), None)  # fmt: skip
            if st is None or None in (st["key_offset"], st["key_length"], st["record_max"]):
                raise Unsupported(f"CICS file {e['name']}: no IDCAMS DEFINE for {dsn}")
            out.append({"file": e["name"], "dsname": dsn, "base": dsn, "key_offset": st["key_offset"],
                        "key_length": st["key_length"], "reclen": st["record_max"],
                        "via": [f"symbolic {st['defined_by'].get('pattern')}"]})  # fmt: skip
            continue
        key = d
        if d.kind == "AIX":
            via.append(f"AIX {d.name}")
            d = defines.get((d.related or "").upper())
            if d is None:
                raise Unsupported(f"CICS file {e['name']}: AIX {key.name} has no base cluster define")
        stated = ((datasets or {}).get(d.name.upper()) or {}).get("vsam") or {}
        koff = key.key_offset if key.key_offset is not None else stated.get("key_offset")
        klen = key.key_length if key.key_length is not None else stated.get("key_length")
        reclen = d.record_max if d.record_max is not None else stated.get("reclen")
        if koff is None or klen is None or reclen is None:
            raise Unsupported(f"CICS file {e['name']}: {key.name}'s KEYS or {d.name}'s RECORDSIZE is not in the facts")
        out.append({"file": e["name"], "dsname": dsn, "base": d.name.upper(), "key_offset": koff,
                    "key_length": klen, "reclen": reclen, "via": via})  # fmt: skip
    return sorted(out, key=lambda f: f["file"])


# ---- field values <-> bytes -----------------------------------------------------------
def encode_field(
    value: Any,
    pic: str | None,
    usage: str | None,
    nbytes: int,
    enc: str = common.DEFAULT_DATA_ENCODING,
    sign_separate: bool = False,
    sign_leading: bool = True,
) -> bytes:
    """A value as the field stores it (the inverse of equivalence.decode_field); #3815: text in `enc`.
    SIGN LEADING / TRAILING SEPARATE: the digits and a `+` / `-` byte of its own at that end."""
    num = common._pic_numeric(pic) if pic else None
    if num is None:
        return common.text_bytes(str(value), nbytes, enc)
    signed, digits, scale = num
    n = int((Decimal(str(value)) * (Decimal(10) ** scale)).to_integral_value())
    u = (usage or "DISPLAY").upper()
    if u in ("COMP-3", "PACKED-DECIMAL", "COMPUTATIONAL-3"):
        body = f"{abs(n):0{nbytes * 2 - 1}d}"[-(nbytes * 2 - 1) :]
        return bytes.fromhex(body + ("d" if n < 0 else ("c" if signed else "f")))
    if u in ("COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"):
        return n.to_bytes(nbytes, "big", signed=signed)
    text = f"{abs(n):0{digits}d}"[-digits:]
    if sign_separate:
        mark = "-" if n < 0 else "+"
        return (mark + text if sign_leading else text + mark).encode(enc)
    if signed:
        last = int(text[-1])
        pos, neg = common.zoned_sign_characters(common.sign_page(enc))  # cp037: `{ABCDEFGHI` / `}JKLMNOPQR`
        text = text[:-1] + (neg[last] if n < 0 else pos[last])
    return text.encode(enc)


def encode_record(
    fields: list[dict[str, Any]], values: dict[str, Any], fill: bytes, enc: str = common.DEFAULT_DATA_ENCODING
) -> bytes:
    """A record from {field name: value}; every field not named is `fill` (for a COMMAREA,
    INITIALIZE's spaces / zeros; for map input, the nulls CICS leaves in an untouched field). #3815: in `enc`."""
    size = max((f["offset"] + f["bytes"] for f in fields), default=0)
    rec = bytearray(size)
    names = {f["name"] for f in fields}
    unknown = sorted(set(values) - names)
    if unknown:
        raise ValueError(f"no such field(s): {', '.join(unknown)}")
    for f in fields:
        sl = slice(f["offset"], f["offset"] + f["bytes"])
        if isinstance(values.get(f["name"]), bytes):  # already the field's bytes
            rec[sl] = values[f["name"]][: f["bytes"]].ljust(f["bytes"], " ".encode(enc))
        elif f["name"] in values:
            rec[sl] = encode_field(values[f["name"]], f["pic"], f["usage"], f["bytes"], enc,
                                   f.get("sign_separate", False), f.get("sign_leading", True))  # fmt: skip
        elif fill == b"init":
            num = common._pic_numeric(f["pic"]) if f["pic"] else None
            rec[sl] = encode_field(0 if num else "", f["pic"], f["usage"], f["bytes"], enc,
                                   f.get("sign_separate", False), f.get("sign_leading", True))  # fmt: skip
        else:
            rec[sl] = fill * f["bytes"]
    return bytes(rec)


def decode_record(data: bytes, fields: list[dict[str, Any]], enc: str = common.DEFAULT_DATA_ENCODING,
                  keep_nulls: bool = False) -> dict[str, str]:  # fmt: skip
    """{field name: value as text} -- numeric fields as exact decimals, text with trailing
    spaces and nulls dropped (a screen shows neither). #3815: text and zoned bytes read in `enc`.
    `keep_nulls`: a text ending in LOW-VALUES kept whole -- a COMMAREA handed to the Java side, whose DTO codec pads
    with spaces: COTRTLIC's unfetched rows are LOW-VALUES, and the program protects exactly those."""
    out = {}
    for f in fields:
        raw = data[f["offset"] : f["offset"] + f["bytes"]]
        if len(raw) < f["bytes"]:
            continue
        v = common.decode_field(raw, f["pic"], f["usage"], common.sign_page(enc), f.get("sign_separate", False),
                                enc)  # fmt: skip
        if not isinstance(v, str):
            out[f["name"]] = str(v)
        else:
            out[f["name"]] = v if keep_nulls and v.rstrip(" ").endswith("\x00") else v.rstrip(" \x00")
    return out


def map_input(fields: list[dict[str, Any]], values: dict[str, str], enc: str = common.DEFAULT_DATA_ENCODING) -> bytes:
    """A RECEIVE MAP input area: nulls everywhere, and for each field the user typed in
    ({"ACCTSIDI": "00000000011"}) its data and its length (<name>L)."""
    typed: dict[str, Any] = {}
    for field, text in values.items():
        typed[field] = text.encode(enc)  # what was typed, whatever the field's PICIN
        typed[field[:-1] + "L"] = len(text.rstrip())
    return encode_record(fields, typed, b"\x00", enc)


# FORMATTIME's date forms (IBM CICS TS, EXEC CICS FORMATTIME): the parts in order, and the separator's default
_DATE_FORMS = {"YYYYMMDD": ("GG-Y", "GG-M", "GG-D"), "MMDDYYYY": ("GG-M", "GG-D", "GG-Y"),
               "DDMMYYYY": ("GG-D", "GG-M", "GG-Y"), "YYMMDD": ("GG-Y(3:2)", "GG-M", "GG-D"),
               "MMDDYY": ("GG-M", "GG-D", "GG-Y(3:2)"), "DDMMYY": ("GG-D", "GG-M", "GG-Y(3:2)")}  # fmt: skip


def _formattime(opts: dict[str, str]) -> list[str]:
    """FORMATTIME ABSTIME(t) [date forms] [DATESEP] [TIME] [TIMESEP], in COBOL: t split into the day number since
    1900-01-01 and the milliseconds into the day. DATESEP / TIMESEP without a value are '/' and ':'; absent, none."""
    supported = {"FORMATTIME", "ABSTIME", "DATESEP", "TIME", "TIMESEP", *_DATE_FORMS}
    extra = sorted(set(opts) - supported - {"NOHANDLE", "RESP", "RESP2"})
    if extra or not opts.get("ABSTIME"):
        raise Unsupported(f"FORMATTIME {' '.join(extra) or 'without ABSTIME'}", ["FORMATTIME"])
    t = opts["ABSTIME"]
    lines = [f"COMPUTE GG-DAYS = {t} / 86400000", f"COMPUTE GG-REM = {t} - GG-DAYS * 86400000",
             "COMPUTE GG-DATE8 = FUNCTION DATE-OF-INTEGER(GG-DAYS",
             "    + FUNCTION INTEGER-OF-DATE(19000101))",
             "COMPUTE GG-HH = GG-REM / 3600000", "COMPUTE GG-MI = (GG-REM - GG-HH * 3600000) / 60000",
             "COMPUTE GG-SS = (GG-REM - GG-HH * 3600000", "    - GG-MI * 60000) / 1000"]  # fmt: skip

    def sep(option: str, default: str) -> Optional[str]:
        if option not in opts:
            return None
        return opts[option] or f"'{default}'"

    def build(parts: tuple[str, ...], separator: Optional[str], target: str) -> list[str]:
        pieces = []
        for i, p in enumerate(parts):
            if i and separator:
                pieces.append(separator)
            pieces.append(p)
        width = sum(4 if p == "GG-Y" else 2 for p in parts) + (len(parts) - 1 if separator else 0)
        return (["MOVE SPACES TO GG-OUT", "STRING " + " ".join(pieces), "    DELIMITED BY SIZE INTO GG-OUT"]
                + [f"MOVE GG-OUT(1:{width}) TO {target}(1:{width})"])  # fmt: skip

    for form, parts in _DATE_FORMS.items():
        if opts.get(form):
            lines += build(parts, sep("DATESEP", "/"), opts[form])
    if opts.get("TIME"):
        lines += build(("GG-HH", "GG-MI", "GG-SS"), sep("TIMESEP", ":"), opts["TIME"])
    return lines


# ---- running a case -------------------------------------------------------------------
def csd_programs(corpus: Path, case: dict[str, Any]) -> Optional[list[str]]:
    """The programs the case's CSD (its "csd": a DFHCSDUP listing in the corpus) defines, or None: every program
    is defined. With autoinstall off, an XCTL / LINK / INQUIRE of any other is PGMIDERR (CardDemo's admin menu
    lists COTRTLIC / COTRTUPC, which its base CSD does not define: 'This option is not installed ...')."""
    if not case.get("csd"):
        return None
    text = (corpus / case["csd"]).read_text(encoding="latin-1")
    return sorted(set(re.findall(r"DEFINE\s+PROGRAM\(([A-Z0-9@#$]{1,8})\)", text)))


def csd_tdqueues(corpus: Path, case: dict[str, Any]) -> Optional[list[str]]:
    """The transient-data queues the case's CSD defines (DEFINE TDQUEUE), or None: every queue is defined."""
    if not case.get("csd"):
        return None
    text = (corpus / case["csd"]).read_text(encoding="latin-1")
    return sorted(set(re.findall(r"DEFINE\s+TDQUEUE\(([A-Z0-9@#$]{1,4})\)", text)))


def commarea_fields(corpus: Path, case: dict[str, Any]) -> list[dict[str, Any]]:
    """The COMMAREA layout: the case's (copybook, record) segments laid end to end. A segment in a program's
    own source (CardDemo's COUSR02C: COPY COCOM01Y then its own 05 items in the same 01) finds the COPY
    members in the case's copy_dirs."""
    out, at = [], 0
    for seg in case["commarea"]["segments"]:
        src = corpus / seg["copybook"]
        dirs = [src.parent, *(corpus / d for d in case.get("copy_dirs", [])), corpus]
        fields = common.layout_fields(corpus, seg["copybook"], seg["record"], dirs)
        out += [dict(f, offset=f["offset"] + at) for f in fields]
        at += max(f["offset"] + f["bytes"] for f in fields)
    return out


def screen_fields(corpus: Path, case: dict[str, Any], map_name: str, side: str) -> list[dict[str, Any]]:
    scr = case["screens"][map_name]
    return common.layout_fields(corpus, scr["copybook"], scr[side])


# #4023 follow-up: the conditions a scenario may inject, by name -> their DFHRESP numbers (IBM CICS "RESP values")
CICS_RESP = {"NORMAL": 0, "FILENOTFOUND": 12, "NOTFND": 13, "DUPREC": 14, "INVREQ": 16, "IOERR": 17, "NOSPACE": 18,
             "NOTOPEN": 19, "ILLOGIC": 21, "LENGERR": 22, "PGMIDERR": 27, "NOTAUTH": 70, "DISABLED": 84,
             "LOADING": 94, "ENDFILE": 20}  # fmt: skip


FAULT_COMMANDS = (
    "READ",
    "INQUIRE",
    "WRITE",
    "REWRITE",
    "STARTBR",
    "READNEXT",
    "READPREV",
    "ENDBR",
    "DELETE",
    "WRITEQ-TD",
)  # a file command (FILE), an INQUIRE PROGRAM (the program's name in `file`)


def fault_lines(sc: dict[str, Any]) -> list[str]:
    """A scenario's `faults` as both sides read them: `CMD NAME NTH RESP RESP2` (faults.cfg, CicsTask.withFaults) --
    NAME the file a READ names, or the program an INQUIRE PROGRAM names."""
    out = []
    for f in sc.get("faults") or []:
        cmd = f.get("cmd", "READ")
        if cmd not in FAULT_COMMANDS or f.get("resp") not in CICS_RESP:
            raise Unsupported(
                f"scenario {sc['name']}: fault {f} ({'/'.join(FAULT_COMMANDS)} with a CICS_RESP condition)"
            )
        nth = "*" if f.get("nth", 1) == "*" else int(f.get("nth", 1))
        out.append(f"{cmd} {f.get('file') or f.get('program')} {nth} {CICS_RESP[f['resp']]} {int(f.get('resp2', 0))}")
    return out


def run_cobol_cics(case: dict[str, Any], corpus: Path, work: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    """Translate, compile and run each scenario; {scenario: its outputs} (see `outputs`)."""
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    for cpy in case.get("copy_dirs", []):
        for p in (corpus / cpy).iterdir():
            if p.is_file():
                shutil.copy(p, src / p.name)
                shutil.copy(p, src / (p.stem.upper() + ".cpy"))  # COPY COACTVW finds COACTVW.CPY
    for p in STUB.iterdir():
        shutil.copy(p, src / p.name)
    # #3828: the program's CBL / PROCESS cards and the case's `compiler_options` become cobc flags
    common.require_ascii_runtime(case)  # #3815: an EBCDIC data page cannot run under GnuCOBOL
    enc = common.data_encoding(case)
    # #3815: read by the engine's ladder (or the declared page), staged in the encoding it was read in
    program, staged = common.read_program(case, corpus / case["program_source"])
    source, option_flags = common.compile_options(case, program)
    db2 = case.get("db2")
    dumps: list[tuple[str, str, list[str]]] = []
    if db2:  # a Db2 program: its EXEC SQL precompiled into calls of the SQL stub, before the EXEC CICS translation
        dirs = [corpus / d for d in [*case.get("copy_dirs", []), *db2.get("include_dirs", [])]]
        try:
            source, table = equivalence_sql.precompile(source, dirs, corpus / case["program_source"])
        except equivalence_sql.Unsupported as e:
            raise Unsupported(f"EXEC SQL: {e}", ["EXEC SQL"]) from e
        equivalence_db2.create(case, corpus)
        (work / "stmts.txt").write_text(table, encoding="latin-1")
        (work / "reset.sql").write_text(equivalence_db2.reset_script(case, corpus), encoding="latin-1")
        shutil.copy(equivalence_db2.STUB, src / "ggsql.c")
        shutil.copy(equivalence_db2.RUNNER, src / "ggsqlrun.c")
        for t in db2.get("compare", []):
            names = equivalence_db2.columns(t)
            dumps.append((t, equivalence_db2.dump_query(t, names), names))
    text, has_commarea = translate(source)
    (src / "PROGRAM.cbl").write_text(text, encoding=staged)
    (src / "EQCICSDR.cbl").write_text(cics_driver(case["program"], has_commarea), encoding="ascii")
    (work / "files.cfg").write_text("".join(
        f"{f['file']} /work/files/{f['base']} {f['reclen']} {f['key_offset']} {f['key_length']}\n" for f in files
    ), encoding="ascii")  # fmt: skip
    (work / "files").mkdir(exist_ok=True)
    for f in files:
        spec = case.get("datasets", {}).get(f["base"])
        if spec is None:
            raise Unsupported(f"the case gives no data for {f['base']} (CICS file {f['file']})")
        (work / "files" / f["base"]).write_bytes(
            common._fixed(common._input_path(case, corpus, spec["input"]), f["reclen"], enc)
        )
    ca_fields = commarea_fields(corpus, case)
    # The COBOL programs the program CALLs (COTRN02C -> CSUTLDTC), as they are, and the LE service models
    # (tests/equivalence/le: CEEDAYS) they may call in turn.
    subs = []
    for rel in case.get("subprograms", []):
        sub_text, _ = common.read_program(case, corpus / rel)
        name = Path(rel).stem.upper()
        (src / f"SUB{name}.cbl").write_text(common.compile_options(case, sub_text)[0], encoding=staged)
        subs.append(f"src/SUB{name}.cbl")
    for model in sorted(LE_MODELS.glob("*.c")) if subs else []:
        shutil.copy(model, src / model.name)
        subs.append(f"src/{model.name}")
    if "CALL 'GGCRUN'" in text:  # a LINK: the level's dispatcher, with no program to run -- the case runs one
        (src / "GGCRUN.cbl").write_text(task_dispatcher({}), encoding="ascii")  # program; a LINK the case
        subs.append("src/GGCRUN.cbl")  # reaches is refused after the run (NOPROGRAM, below)
    compile_task = (
        f"cobc -x -std=ibm -fsign=EBCDIC -fstatic-call {cov.TRACE_FLAG} {''.join(f + ' ' for f in option_flags)}"
        f"-I /work/src -o task src/EQCICSDR.cbl src/PROGRAM.cbl {''.join(s + ' ' for s in subs)}src/ggcics.c"
    )
    if db2:
        compile_task += f" src/ggsql.c {equivalence_db2.COBOL_LINK}"
    script = ["set -e", "cd /work", compile_task]
    if db2:
        script.append(f"gcc -O2 -o ggsqlrun src/ggsqlrun.c {equivalence_db2.COBOL_LINK}")
    date, _, time = case["clock"].partition(" ")
    programs = csd_programs(corpus, case)
    tdqueues = csd_tdqueues(corpus, case)
    if "'APPLID' TO GG-NAME2" in text or "'SYSID' TO GG-NAME2" in text:
        if not (case.get("region") or {}).get("applid") or not case["region"].get("sysid"):
            raise Unsupported('ASSIGN APPLID / SYSID: the case states no region ("region": {"applid", "sysid"})')
    for sc in case["scenarios"]:
        d = work / "scenarios" / sc["name"]
        (d / "out").mkdir(parents=True, exist_ok=True)
        # each task its own copy of the files: what it writes is its own, and is compared (file updates)
        shutil.copytree(work / "files", d / "files", dirs_exist_ok=True)
        (d / "files.cfg").write_text("".join(
            f"{f['file']} /work/scenarios/{sc['name']}/files/{f['base']} {f['reclen']} {f['key_offset']} "
            f"{f['key_length']}\n" for f in files
        ), encoding="ascii")  # fmt: skip
        if sc.get("commarea") is not None:
            (d / "commarea.in").write_bytes(encode_record(ca_fields, sc["commarea"], b"init", enc))
        for m, typed in (sc.get("receive") or {}).items():
            (d / f"receive_{m}.bin").write_bytes(map_input(screen_fields(corpus, case, m, "input"), typed, enc))
        if programs is not None:  # the CSD's programs; absent, every program is defined
            (d / "programs.cfg").write_text("".join(f"{p}\n" for p in programs), encoding="ascii")
        if tdqueues is not None:  # the CSD's transient-data queues; absent, every queue is defined
            (d / "tdqueues.cfg").write_text("".join(f"{q}\n" for q in tdqueues), encoding="ascii")
        if case.get("region"):  # ASSIGN APPLID / SYSID: the region's identity, a deployment fact the case states
            (d / "region.cfg").write_text(f"APPLID {case['region']['applid']}\nSYSID {case['region']['sysid']}\n",
                                          encoding="ascii")  # fmt: skip
        if sc.get("faults"):  # #4023 follow-up: the stub's injected conditions
            (d / "faults.cfg").write_text("".join(x + "\n" for x in fault_lines(sc)), encoding="ascii")
        y, mo, dd = date.split("/")
        eib_date = f"{int(y) - 1900:03d}{_day_of_year(int(y), int(mo), int(dd)):03d}"[-7:].rjust(7, "0")
        eib_time = "0" + time.replace(":", "")[:6]
        (d / "eib.in").write_text(f"{case['transid']:<4} {sc.get('aid', 'DFHENTER'):<8} {eib_date} {eib_time}\n",
                                  encoding="ascii")  # fmt: skip
        rel = f"/work/scenarios/{sc['name']}"
        sqlenv = equivalence_db2.cobol_env("/work/stmts.txt") if db2 else ""
        if db2:  # the tables as the seed has them, for this task
            script.append(f"{sqlenv}./ggsqlrun -f /work/reset.sql")
        script.append(f"set +e; {cov.trace_env(f'{rel}/{cov.TRACE_NAME}')}GGCICS_DIR={rel} GGCICS_OUT={rel}/out EIBIN={rel}/eib.in "
                      f"{sqlenv}COB_CURRENT_DATE='{case['clock']}' ./task > {rel}/stdout.txt 2>&1; "
                      f"echo $? > {rel}/rc; set -e")  # fmt: skip
        if db2:  # what the task left in each compared table
            script.append(f"mkdir -p {rel}/db2")
            for t, query, names in dumps:
                script.append(f"{{ echo '{'|'.join(names)}'; {sqlenv}./ggsqlrun -q \"{query}\"; }} > {rel}/db2/{t}")
    (work / "run.sh").write_text("\n".join(script) + "\n", encoding="ascii")
    proc = (common.run_cobol_step(work, equivalence_db2.COBOL_IMAGE, tuple(equivalence_db2.cobol_docker_args(case)))
            if db2 else common.run_cobol_step(work))  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"COBOL side failed:\n{proc.stdout}\n{proc.stderr}")
    for sc in case["scenarios"]:  # a LINK reached: the program it names is not run here (no port of it)
        log = work / "scenarios" / sc["name"] / "out" / "events.txt"
        hit = re.search(r"\bNOPROGRAM\b.*?\btarget=(\S*)", log.read_text(encoding="latin-1")) if log.is_file() else None
        if hit:
            raise Unsupported(f"scenario {sc['name']}: LINK PROGRAM({hit.group(1)}) -- the case runs one program",
                              ["LINK"])  # fmt: skip
        # a library model (tests/equivalence/le) that stops rather than guess (exit 98, "... not modelled"): the
        # scenario reaches behaviour the oracle cannot judge -- refused by name, never reported as a difference
        rc = work / "scenarios" / sc["name"] / "rc"
        said = work / "scenarios" / sc["name"] / "stdout.txt"
        if rc.is_file() and rc.read_text().strip() == "98" and said.is_file():
            why = next((ln for ln in said.read_text(encoding="latin-1").splitlines() if "not modelled" in ln), None)
            if why:
                raise Unsupported(f"scenario {sc['name']}: {why.strip()}", ["MODEL"])
    # #4023: how much of the program the scenarios execute, together (work/coverage.json)
    cov.write_run_coverage(work / "coverage.json", source=corpus / case["program_source"], original=program,
                           compiled=text, traces=[work / "scenarios" / sc["name"] / cov.TRACE_NAME for sc in case["scenarios"]],
                           compiled_name="PROGRAM.cbl", copybooks=corpus, encoding=staged)  # fmt: skip
    return {sc["name"]: outputs(work / "scenarios" / sc["name"] / "out", case, corpus, ca_fields)
            for sc in case["scenarios"]}  # fmt: skip


def _day_of_year(y: int, m: int, d: int) -> int:
    import datetime

    return datetime.date(y, m, d).timetuple().tm_yday


def outputs(out: Path, case: dict[str, Any], corpus: Path, ca_fields: list[dict[str, Any]]) -> dict[str, Any]:
    """A task's outputs from the stub's log: `events` (every command, in order), `screens`
    ([{map, fields}] per SEND MAP, data fields only: <name>O -> <name>), `text` (SEND TEXT),
    `return` ({transid, commarea fields}), `xctl` ({program, commarea fields}), `abend`."""
    res: dict[str, Any] = {"events": [], "screens": [], "text": [], "return": None, "xctl": None, "abend": None}
    enc = common.data_encoding(case)  # #3815: the areas' page; the stub's own log is ASCII, read losslessly
    files = out.parent / "files"  # what the task left in its own copy of each file (file updates)
    res["files"] = {p.name: p.read_bytes() for p in sorted(files.iterdir())
                    if p.is_file() and not p.name.endswith(".uow")} if files.is_dir() else {}  # fmt: skip
    db2 = out.parent / "db2"  # a Db2 case: what the task left in each compared table
    res["db2"] = {p.name: p.read_bytes() for p in sorted(db2.iterdir()) if p.is_file()} if db2.is_dir() else {}
    log = out / "events.txt"
    for line in log.read_text(encoding="latin-1").splitlines() if log.is_file() else []:
        seq, _, rest = line.partition(" ")
        verb, _, args = rest.partition(" ")
        kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
        res["events"].append(rest)
        blob = out / f"{seq}.bin"
        data = blob.read_bytes() if blob.is_file() else b""
        if verb == "SEND-MAP":
            fields = screen_fields(corpus, case, kv["map"], "output")
            vals = decode_record(data, fields, enc)
            res["screens"].append({"map": kv["map"], "fields": {k[:-1]: v for k, v in vals.items() if k.endswith("O")},
                                   "subfields": map_subfields(corpus, case, kv["map"], data, enc),
                                   "options": sorted(args.partition("opts=")[2].split()),
                                   "cursor": None if kv.get("cursor", "-1") == "-1" else int(kv["cursor"])})  # fmt: skip
        elif verb == "SEND-TEXT":
            text = common._decode_text(data, enc)  # #3815: not text in the page -> the bytes shown, never dropped
            res["text"].append(f"<undecodable {data!r} in {enc}>" if text is None else text.rstrip(" \x00"))
        elif verb in ("RETURN", "XCTL"):
            key = "transid" if verb == "RETURN" else "program"
            ca = decode_record(data, ca_fields, enc) if data else None
            res[verb.lower()] = {key: kv.get(key, ""), "commarea": ca}
        elif verb == "ABEND":
            res["abend"] = args
        elif verb == "WRITEQ-TD":  # a transient-data record, as text in the data's page
            text = common._decode_text(data, enc)
            res.setdefault("td", []).append(f"<undecodable {data!r} in {enc}>" if text is None else text)
    left = out / "commarea.out"  # a LINKed program's result: the COMMAREA it left (ggcics GGCAOUT)
    res["linked_commarea"] = (
        decode_record(left.read_bytes(), ca_fields, enc) if left.is_file() and left.stat().st_size else None
    )
    return res


# #4053: the symbolic map's subfields besides the data -- what the screen shows besides its text
# <f>F and <f>A are one byte (A REDEFINES F, under a FILLER the layout does not name): the attribute
_SUBFIELDS = {"A": "attr", "F": "attr", "C": "color", "H": "hilight"}


def map_subfields(
    corpus: Path, case: dict[str, Any], map_name: str, data: bytes, enc: str
) -> dict[str, dict[str, int]]:
    """The subfields a SEND MAP's symbolic map holds, as CicsTask.MapSubfields records them: per field (the BMS
    name), the attribute byte (<f>A), extended colour (<f>C) and highlight (<f>H) as their byte values, and length
    -1 (<f>L: the cursor goes there). The harness's DFHBMSCA (tests/equivalence/cics) holds the EBCDIC bytes
    themselves (DFHRED is X'F2'), so the byte is the value. Not set, and not compared: X'00' -- the LOW-VALUES a
    program clears its map with, which BMS reads as "the map's own" -- and a space, which is never a BMS value
    here but WORKING-STORAGE GnuCOBOL initialised to spaces where IBM leaves it undefined (a map the program never
    cleared: the mainframe's bytes are not known, so nothing is claimed about them)."""
    out: dict[str, dict[str, int]] = {}
    scr = case["screens"][map_name]
    layouts = [common.layout_fields(corpus, scr["copybook"], scr[side]) for side in ("input", "output")]
    data_names = {f["name"][:-1] for f in layouts[1] if f["name"].endswith("O")}
    space = " ".encode(enc)
    for f in (x for layout in layouts for x in layout):
        name, kind = f["name"][:-1], f["name"][-1:]
        if name not in data_names or f["offset"] + f["bytes"] > len(data):
            continue
        raw = data[f["offset"] : f["offset"] + f["bytes"]]
        if kind == "L" and f["bytes"] == 2 and int.from_bytes(raw, "big", signed=True) == -1:
            out.setdefault(name, {})["length"] = -1
        elif kind in _SUBFIELDS and f["bytes"] == 1 and raw not in (b"\x00", space):
            out.setdefault(name, {})[_SUBFIELDS[kind]] = raw[0]
    return out


def java_subfields(sub: Any) -> dict[str, dict[str, int]]:
    """CicsTask's recorded subfields in the same terms: the set ones only (X'00' and an EBCDIC space are not set,
    as on the COBOL side), length only as -1."""
    out: dict[str, dict[str, int]] = {}
    for name, vals in (sub or {}).items():
        for key, v in (vals or {}).items():
            if v is None or (key == "length" and v != -1) or (key != "length" and int(v) & 0xFF in (0x00, 0x40)):
                continue
            out.setdefault(name, {})[key] = int(v) if key == "length" else int(v) & 0xFF
    return out


# ---- the Java side --------------------------------------------------------------------
_DTO_FIELD = re.compile(r"^\s*//\s*(.+?)\n\s*private\s+([\w.<>]+)\s+(\w+);", re.M)


def java_class_file(src: Path, name: str, context: Optional[Path] = None) -> Optional[Path]:
    """The source file of a generated class (#4011): by its path when `name` is qualified
    (`pkg.dto.contract.PcwizWsState`); a simple name as Java resolves it from `context` (the file
    that names it: its single-type imports, its own package, then its on-demand imports); else
    the only class of that name under `src`. None when there is no such class. Two or more
    candidates with nothing to choose between them raise LookupError: a simple-name lookup that
    picks one (entity/PcwizWsState over dto/contract/PcwizWsState) maps the COMMAREA wrong."""
    if "." in name:
        path = src / (name.replace(".", "/") + ".java")
        return path if path.is_file() else None
    if context is not None:
        text = context.read_text(encoding="utf-8")
        single = re.search(rf"^\s*import\s+([\w.]+)\.{re.escape(name)}\s*;", text, re.M)
        if single:
            return java_class_file(src, f"{single.group(1)}.{name}")
        if (context.parent / f"{name}.java").is_file():
            return context.parent / f"{name}.java"
        for pkg in re.findall(r"^\s*import\s+([\w.]+)\.\*\s*;", text, re.M):
            found = java_class_file(src, f"{pkg}.{name}")
            if found:
                return found
    cands = sorted(src.rglob(f"{name}.java"))
    if len(cands) > 1:
        where = ", ".join(p.relative_to(src).as_posix() for p in cands)
        raise LookupError(f"class {name} is ambiguous ({where}): name it by its package")
    return cands[0] if cands else None


def dto_shape(src: Path, cls: str, context: Optional[Path] = None) -> dict[str, Any]:
    """A generated DTO's properties: {java name: COBOL field name} for a field, {java name:
    (DTO class, its shape)} for a part (a composite COMMAREA's segments), from the comment each
    property carries (`// CDEMO-FROM-TRANID: PIC X(04), offset 0 ...`). `cls` is a qualified name
    or a simple one resolved from `context` (java_class_file); a part's class is resolved from
    the DTO that declares it."""
    path = java_class_file(src, cls, context)
    if path is None:
        raise LookupError(f"no generated class {cls} under {src}")
    return _dto_file_shape(src, path)


def _dto_file_shape(src: Path, path: Path) -> dict[str, Any]:
    shape: dict[str, Any] = {}
    for comment, jtype, var in _DTO_FIELD.findall(path.read_text(encoding="utf-8")):
        part = java_class_file(src, jtype, path) if " -> " in comment else None
        if part is not None:
            shape[var] = (part.stem, _dto_file_shape(src, part))
        elif ":" in comment:
            shape[var] = comment.split(":", 1)[0].strip()
    return shape


def to_java(values: dict[str, Any], shape: dict[str, Any], text: frozenset[str] = frozenset()) -> dict[str, Any]:
    """{COBOL name: value} -> the DTO's JSON (numbers as numbers, text as the program holds it). A field in `text`
    (an alphanumeric PICTURE) stays text even when it reads as a number: CardDemo's selected transaction id
    '0000000000683580' (PIC X(16)) reached the port as 683580."""
    out: dict[str, Any] = {}
    for var, spec in shape.items():
        if isinstance(spec, tuple):
            out[var] = to_java(values, spec[1], text)
        elif spec in values:
            v = values[spec]
            if spec in text:
                out[var] = v
                continue
            try:
                d = Decimal(v)
                out[var] = int(d) if d == d.to_integral_value() else float(d)
            except (ArithmeticError, ValueError, TypeError):
                out[var] = v
    return out


def shape_names(shape: dict[str, Any]) -> set[str]:
    """The COBOL names a DTO shape carries (its nested groups' too)."""
    out: set[str] = set()
    for spec in shape.values():
        if isinstance(spec, tuple):
            out |= shape_names(spec[1])
        else:
            out.add(spec)
    return out


def alphanumeric(fields: list[dict[str, Any]]) -> frozenset[str]:
    """The fields whose PICTURE holds text (X / A), not a number."""
    # the PICTURE's symbols only: X(09) is text -- the 9 in its repetition count is not a digit position
    return frozenset(f["name"] for f in fields
                     if f.get("pic") and not re.search(r"[9SVP]", re.sub(r"\(\d+\)", "", f["pic"].upper())))  # fmt: skip


def _leaves(shape: dict[str, Any]) -> dict[str, str]:
    """{java leaf name: COBOL field name} over the whole shape, parts included."""
    out: dict[str, str] = {}
    for var, spec in shape.items():
        out.update(_leaves(spec[1]) if isinstance(spec, tuple) else {var: spec})
    return out


def from_java(obj: dict[str, Any] | None, shape: dict[str, Any]) -> dict[str, Any]:
    """The DTO's JSON -> {COBOL name: value}. The object may be the whole COMMAREA or one of its
    parts (an XCTL passes only CARDDEMO-COMMAREA), so leaves are matched wherever they sit."""
    names = _leaves(shape)
    out: dict[str, Any] = {}

    def walk(o: Any) -> None:
        for k, v in (o or {}).items():
            if isinstance(v, dict):
                walk(v)
            elif k in names:
                out[names[k]] = v

    walk(obj)
    return out


def _generated_class(src: Path, pattern: str) -> str:
    for p in sorted(src.rglob("*.java")):
        if re.search(pattern, p.read_text(encoding="utf-8")):
            return p.stem
    raise RuntimeError(f"no generated class matches {pattern!r}")


def commarea_class(case: dict[str, Any], src: Path, svc_file: Path) -> str:
    """The COMMAREA DTO the task carries: the one the service's handleTransaction takes -- or, for a program that
    receives none and only builds one (CardDemo's sign-on, COSGN00C: it tests EIBCALEN, then XCTLs with
    CARDDEMO-COMMAREA), the generated DTO of the case's first COMMAREA record."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

    svc_text = svc_file.read_text(encoding="utf-8")
    m = re.search(r"handleTransaction\(String transid, (\w+) request\)", svc_text) or re.search(
        r"handleLink\((\w+) request\)", svc_text
    )  # a LINKed program (CBSA): its contract COMMAREA DTO
    if m:
        return m.group(1)
    record = case["commarea"]["segments"][0]["record"]
    name = java_class_base(record)
    if not any(src.rglob(f"{name}.java")):
        raise Unsupported(f"no generated COMMAREA class {name} for {record}")
    return name


DB2_JAVA = """    @Autowired org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate db2Jdbc;  // EquivalenceDb2Config

    java.sql.Connection db2() throws java.sql.SQLException {
        return java.sql.DriverManager.getConnection(System.getProperty("gitgalaxy.db2.url"),
            System.getProperty("gitgalaxy.db2.user"), System.getProperty("gitgalaxy.db2.password"));
    }

    void db2Reset() throws IOException {
        String script = Files.readString(in.resolve("db2reset.sql"), StandardCharsets.ISO_8859_1);
        try (var c = db2(); var st = c.createStatement()) {
            c.setAutoCommit(false);
            StringBuilder one = new StringBuilder();
            boolean quote = false;
            for (char ch : (script + ";").toCharArray()) {
                if (ch == '\\'') quote = !quote;
                if (ch == ';' && !quote) {
                    if (!one.toString().isBlank()) st.execute(one.toString());
                    one.setLength(0);
                } else {
                    one.append(ch);
                }
            }
            c.commit();
        } catch (java.sql.SQLException e) {
            throw new IOException(e);
        }
    }

    void db2Dump(String scenario) throws IOException {
        for (String line : Files.readAllLines(in.resolve("db2dumps.txt"), StandardCharsets.ISO_8859_1)) {
            String[] p = line.split("\\t", 3);
            StringBuilder o = new StringBuilder(p[1]).append('\\n');
            try (var c = db2(); var st = c.createStatement(); var rs = st.executeQuery(p[2])) {
                while (rs.next()) {
                    String v = rs.getString(1);
                    o.append(v == null ? "NULL" : v).append('\\n');
                }
            } catch (java.sql.SQLException e) {
                throw new IOException(e);
            }
            Files.writeString(out.resolve(scenario + ".DB2_" + p[0] + ".out"), o.toString(), StandardCharsets.ISO_8859_1);
        }
    }
"""


def cics_equivalence_test(case: dict[str, Any], src: Path, files: list[dict[str, Any]],
                          programs: Optional[list[str]] = None, tdqueues: Optional[list[str]] = None) -> str:  # fmt: skip
    """EquivalenceRunTest for a CICS case: the files loaded through their entities' codecs, then
    each scenario (in/scenarios.json) run as a CicsTask through the service's runTask, its events
    written to out/<scenario>.json -- a screen as its screenValues(), a COMMAREA as its DTO."""
    import equivalence_java as ej

    pkg = ej.PKG
    svc = ej._service_class(case["program"])
    var = svc[0].lower() + svc[1:]
    ca = commarea_class(case, src, next(src.rglob(f"{svc}.java")))
    screens = {m: _generated_class(src, rf'String MAP = "{m}";') for m in case["screens"]}
    by_base = {f["base"]: f for f in files}
    region = case.get("region") or {}
    region_java = f'"{region["applid"]}", "{region["sysid"]}"' if region.get("applid") else "null, null"
    csd_java = ""
    if tdqueues is not None:  # the CSD's transient-data queues: a WRITEQ TD to any other is QIDERR
        names = ", ".join(f'"{q}"' for q in tdqueues)
        csd_java += f"            task.withTdQueues(java.util.Set.of({names}));\n"
    if programs is not None:  # the CSD's programs: an XCTL / LINK / INQUIRE of any other is PGMIDERR
        names = ", ".join(f'"{p}"' for p in programs)
        csd_java = (f"            task.withPrograms(new CicsTask.Programs() {{\n"
                    f"                final java.util.Set<String> defined = java.util.Set.of({names});\n"
                    f"                public boolean defined(String program) {{ return defined.contains(program); }}\n"
                    f"                public void run(String program, CicsTask t) {{\n"
                    f'                    throw new UnsupportedOperationException("the equivalence harness runs one program");\n'
                    f"                }}\n"
                    f"            }});")  # fmt: skip
    fields, loads, dumps = [], [], []
    for dsn, spec in case.get("datasets", {}).items():
        ent = spec["entity"]
        repo = f"{ent[0].lower()}{ent[1:]}Repository"
        fields.append(f"    @Autowired {pkg}.repository.vsam.{ent}Repository {repo};")
        loads.append(
            f"            {repo}.deleteAll();\n"
            f'            load("{dsn}", {by_base[dsn]["reclen"]}, {pkg}.entity.vsam.{ent}::fromRecord, {repo});'
        )
        dumps.append(f'            dump(sc.get("name").asText() + ".{dsn}.out", {repo}.findAll().stream()'
                     f'.map(row -> row.toRecord(TEXT)).toList());')  # fmt: skip
    # a Db2 case: the tables reset to the seed before each task (in/db2reset.sql), each compared table dumped after
    # it (in/db2dumps.txt: table TAB query), on the database the COBOL side ran on (equivalence_db2)
    db2 = bool(case.get("db2"))
    db2_reset = "            db2Reset();" if db2 else ""
    db2_dump = '            db2Dump(sc.get("name").asText());' if db2 else ""
    db2_methods = DB2_JAVA if db2 else ""
    # a Db2 case: the task's SQL is one Db2 unit of work (one connection, as the task's Db2 thread under CICS):
    # committed when the task ends, rolled back with its files by SYNCPOINT ROLLBACK or an abend
    db2_begin = ("new org.springframework.transaction.support.TransactionTemplate(new org.springframework.jdbc."
                 "datasource.DataSourceTransactionManager(db2Jdbc.getJdbcTemplate().getDataSource()))"
                 ".executeWithoutResult(db2Status -> {\n            ") if db2 else ""  # fmt: skip
    db2_rollback = "db2Status.setRollbackOnly(); " if db2 else ""
    db2_end = "\n            });" if db2 else ""
    recv = [f'            if (r.has("{m}")) received.put("{m}", {pkg}.dto.screen.{cls}.fromValues('
            f'json.convertValue(r.get("{m}"), new TypeReference<Map<String, String>>() {{ }})));'
            for m, cls in screens.items()]  # fmt: skip
    return f"""package {pkg};

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import {pkg}.cics.CicsTask;
import {pkg}.dto.screen.ScreenModel;
import {pkg}.exception.CicsAbendException;
import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.jpa.repository.JpaRepository;

/** #3754: the CICS equivalence run of {case["program"]} ({case["name"]}) -- generated by tests/tools/equivalence_cics.py. */
@SpringBootTest(properties = {{"spring.jpa.show-sql=false", "gitgalaxy.clock={ej._clock(case)}"}})
class EquivalenceRunTest {{

    static final Charset TEXT = {common.java_charset(common.data_encoding(case))};
    final Path in = Path.of(System.getProperty("equivalence.in"));
    final Path out = Path.of(System.getProperty("equivalence.out"));
    final ObjectMapper json = new ObjectMapper().findAndRegisterModules();

    @Autowired {pkg}.service.{svc} {var};
{chr(10).join(fields)}

    @Autowired org.springframework.transaction.PlatformTransactionManager transactions;

    @Test
    void run() throws IOException {{
        for (JsonNode sc : json.readTree(in.resolve("scenarios.json").toFile())) {{
            // each task starts from the files as loaded, and what it leaves is compared (file updates)
{chr(10).join(loads)}
{db2_reset}
            Object commarea = sc.get("commarea").isNull() ? null
                    : json.treeToValue(sc.get("commarea"), {pkg}.dto.contract.{ca}.class);
            Map<String, Object> received = new LinkedHashMap<>();
            JsonNode r = sc.get("receive");
{chr(10).join(recv)}
            CicsTask task = new CicsTask("{case["transid"]}", sc.get("aid").asText(), commarea, received)
                    .withClock(java.time.LocalDateTime.parse("{ej._clock(case)}"))  // EIBTIME / ASKTIME: the case's clock
                    .withRegion({region_java});  // ASSIGN APPLID / SYSID
{csd_java}
            List<String> faults = new ArrayList<>();  // #4023 follow-up: the scenario's injected conditions
            sc.path("faults").forEach(f -> faults.add(f.asText()));
            if (!faults.isEmpty()) {{
                task.withFaults(faults, out.resolve(sc.get("name").asText() + ".faults"));
            }}
            // one unit of work: a SYNCPOINT ROLLBACK, or an abend that ends the task, backs its changes out
            {db2_begin}new org.springframework.transaction.support.TransactionTemplate(transactions).executeWithoutResult(status -> {{
                task.onRollback(() -> {{ status.setRollbackOnly(); {db2_rollback}}});
                try {{
                    {var}.runTask(task);
                }} catch (CicsAbendException e) {{
                    status.setRollbackOnly();
                    {db2_rollback}task.abend(e.getAbcode());
                }}
            }});{db2_end}
{chr(10).join(dumps)}
{db2_dump}
            List<Map<String, Object>> events = new ArrayList<>();
            for (Map<String, Object> e : task.events()) {{
                Map<String, Object> copy = new LinkedHashMap<>(e);
                if (copy.get("screen") instanceof ScreenModel s) {{
                    copy.put("screen", s.screenValues());
                }}
                events.add(copy);
            }}
            if (commarea != null) {{  // a LINKed program's result: the COMMAREA it leaves (equivalence_cics.linked_result)
                Map<String, Object> left = new LinkedHashMap<>();
                left.put("event", "COMMAREA");
                left.put("commarea", commarea);
                events.add(left);
            }}
            json.writeValue(out.resolve(sc.get("name").asText() + ".json").toFile(), events);
        }}
    }}

{db2_methods}
    void dump(String name, List<byte[]> records) throws IOException {{
        try (var o = Files.newOutputStream(out.resolve(name))) {{
            for (byte[] r : records) {{
                o.write(r);
            }}
        }}
    }}

    <E> void load(String dd, int reclen, BiFunction<byte[], Charset, E> fromRecord, JpaRepository<E, ?> repo)
            throws IOException {{
        byte[] data = Files.readAllBytes(in.resolve(dd + ".in"));
        List<E> rows = new ArrayList<>();
        for (int i = 0; i + reclen <= data.length; i += reclen) {{
            rows.add(fromRecord.apply(java.util.Arrays.copyOfRange(data, i, i + reclen), TEXT));
        }}
        repo.saveAll(rows);
    }}
}}
"""


def run_java_cics(case: dict[str, Any], corpus: Path, work: Path, cobol_work: Path, files: list[dict[str, Any]],
                  port: bool = True, port_dir: Path | None = None) -> dict[str, list[dict[str, Any]]]:  # fmt: skip
    """The generated project runs every scenario as a CicsTask; {scenario: its events}, each
    COMMAREA mapped back to COBOL field names through the DTO's own comments."""
    import json

    import equivalence_java as ej

    project = ej.prepare_project(case, corpus, work, "", port, port_dir)
    src = project / "src/main/java"
    svc = ej._service_class(case["program"])
    svc_file = next(src.rglob(f"{svc}.java"))
    ca_cls = commarea_class(case, src, svc_file)
    shape = dto_shape(src, ca_cls, svc_file)  # #4011: the class the service imports, not any of that name
    test = project / "src/test/java" / ej.PKG_DIR / "EquivalenceRunTest.java"
    test.write_text(
        cics_equivalence_test(case, src, files, csd_programs(corpus, case), csd_tdqueues(corpus, case)),
        encoding="utf-8",
    )
    inputs = work / "in"
    inputs.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(cobol_work / "files" / f["base"], inputs / f"{f['base']}.in")
    ca_fields = commarea_fields(corpus, case)
    scenarios = []
    for sc in case["scenarios"]:
        ca = None
        if sc.get("commarea") is not None:  # the very COMMAREA the COBOL task started with, as the DTO
            enc = common.data_encoding(case)  # #3815
            values = decode_record(
                encode_record(ca_fields, sc["commarea"], b"init", enc), ca_fields, enc, keep_nulls=True
            )
            # a value the DTO has no field for would reach the port as nothing at all: the case must name the
            # COMMAREA as the contract DTO's record does
            lost = sorted(set(sc["commarea"]) - shape_names(shape))
            if lost:
                raise Unsupported(f"scenario {sc['name']}: the COMMAREA DTO {ca_cls} has no field for {lost} -- "
                                  f"describe the COMMAREA with the record the DTO is generated from")  # fmt: skip
            ca = to_java(values, shape, alphanumeric(ca_fields))
        # A typed field is named as the symbolic map names its input (ACCTSIDI); a screen view model
        # keys it by the BMS field (ACCTSID), as screenValues() / fromValues() do.
        receive = {
            m: {f.removesuffix("I"): v for f, v in typed.items()} for m, typed in (sc.get("receive") or {}).items()
        }
        scenarios.append({"name": sc["name"], "aid": sc.get("aid", "DFHENTER").removeprefix("DFH"),
                          "commarea": ca, "receive": receive, "faults": fault_lines(sc)})  # fmt: skip
    (inputs / "scenarios.json").write_text(json.dumps(scenarios, indent=1), encoding="utf-8")
    props = ej.data_charset_arg(case)
    if case.get("db2"):  # the seed and the dump queries, and the harness's Db2
        (inputs / "db2reset.sql").write_text(equivalence_db2.reset_script(case, corpus), encoding="latin-1")
        (inputs / "db2dumps.txt").write_text("".join(
            f"{t}\t{'|'.join(n)}\t{equivalence_db2.dump_query(t, n)}\n"
            for t, n in ((t, equivalence_db2.columns(t)) for t in case["db2"].get("compare", []))), encoding="latin-1")  # fmt: skip
        props = f"{props} {equivalence_db2.java_props(case)}"
    out = ej.run_maven(project, work, inputs, props=props)
    result = {}
    for sc in case["scenarios"]:
        f = out / f"{sc['name']}.json"
        events = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
        for e in events:
            if "commarea" in e:
                e["commarea"] = from_java(e["commarea"], shape) if e["commarea"] is not None else None
        result[sc["name"]] = events
    return result


# ---- the comparison -------------------------------------------------------------------
def compare_files(case: dict[str, Any], corpus: Path, files: list[dict[str, Any]], cobol: dict[str, bytes],
                  java_out: Path, scenario: str) -> dict[str, dict[str, Any]]:  # fmt: skip
    """File updates: per file, what the task left on each side, both in key order; only the files that differ.
    A file's layout (its dataset's copybook, when the case names one) names the differing fields."""
    out: dict[str, dict[str, Any]] = {}
    enc = common.data_encoding(case)
    for f in files:
        base, reclen = f["base"], f["reclen"]
        left = cobol.get(base, b"")
        right_file = java_out / f"{scenario}.{base}.out"
        right = right_file.read_bytes() if right_file.is_file() else b""

        def by_key(data: bytes) -> bytes:
            recs = [data[i : i + reclen] for i in range(0, len(data) - reclen + 1, reclen)]
            return b"".join(sorted(recs, key=lambda r: r[f["key_offset"] : f["key_offset"] + f["key_length"]]))

        left, right = by_key(left), by_key(right)
        if left == right:
            continue
        spec = case.get("datasets", {}).get(base, {})
        fields = []
        if spec.get("copybook"):  # the COPY members of a record in a program's own source: the case's copy_dirs
            src = corpus / spec["copybook"]
            dirs = [src.parent, *(corpus / d for d in case.get("copy_dirs", [])), corpus]
            fields = common.layout_fields(corpus, spec["copybook"], spec.get("record"), dirs)
        out[base] = common.diff_records(left, right, reclen, fields, case.get("code_page", "cp037"), enc)
    return out


def compare_db2(case: dict[str, Any], cobol: dict[str, bytes], java_out: Path, scenario: str) -> dict[str, Any]:
    """A Db2 case: per compared table, what the task left there on each side -- only the tables that differ."""

    out = {}
    for t in (case.get("db2") or {}).get("compare", []):
        right = java_out / f"{scenario}.DB2_{t}.out"
        d = equivalence_db2.diff_dump(cobol.get(t, b""), right.read_bytes() if right.is_file() else b"")
        if d["diffs"]:
            out[f"DB2 {t}"] = d
    return out


def cobol_events(res: dict[str, Any]) -> list[dict[str, Any]]:
    """The COBOL task's outputs as the event list CicsTask records."""
    out: list[dict[str, Any]] = []
    screens, texts, records = iter(res["screens"]), iter(res["text"]), iter(res.get("td", []))
    for line in res["events"]:
        verb, _, args = line.partition(" ")
        if verb == "SEND-MAP":
            s = next(screens)
            out.append({"event": "SEND-MAP", "map": s["map"], "screen": s["fields"], "subfields": s["subfields"],
                        "options": s["options"], "cursor": s["cursor"]})  # fmt: skip
        elif verb == "SEND-TEXT":
            out.append({"event": "SEND-TEXT", "text": next(texts)})
        elif verb in ("SYNCPOINT", "SYNCPOINT-ROLLBACK"):  # file updates: CicsTask.syncpoint / rollback record them
            out.append({"event": verb})
        elif verb == "WRITEQ-TD":  # CicsTask.writeqTd records the queue and the record's text
            queue = re.search(r"\bqueue=(\S*)", args).group(1)
            resp = re.search(r"\bresp=(\S*)", args).group(1)
            out.append({"event": "WRITEQ-TD", "queue": queue, "text": next(records) if resp == "0" else None})
        elif verb == "RECEIVE-MAP":  # #4009: CicsTask.receive records it too
            out.append({"event": "RECEIVE-MAP", "map": re.search(r"\bmap=(\S*)", args).group(1)})
        elif verb == "RETURN":
            out.append({"event": "RETURN", "transid": res["return"]["transid"] or None,
                        "commarea": res["return"]["commarea"]})  # fmt: skip
        elif verb == "XCTL":
            out.append({"event": "XCTL", "program": res["xctl"]["program"], "commarea": res["xctl"]["commarea"]})
        elif verb == "ABEND":
            m = re.search(r"\babcode=(\S*)", args)
            out.append({"event": "ABEND", "abcode": m.group(1) if m else ""})
    if res.get("linked_commarea") is not None:
        out.append({"event": "COMMAREA", "commarea": res["linked_commarea"]})
    return out


def linked_result(case: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A LINKed program's events (`"linked": true` in the case): its result is the COMMAREA it leaves in its caller's
    storage, compared as a last COMMAREA event -- unless the task abended (no caller sees it then). Any other
    program's final COMMAREA storage is not observable (a terminal task's RETURN COMMAREA is), so it is dropped."""
    keep = case.get("linked") and not any(e.get("event") == "ABEND" for e in events)
    return [e for e in events if e.get("event") != "COMMAREA" or keep]


def _same(a: Any, b: Any) -> bool:
    """Equal as the task means it: decimals exactly, text ignoring trailing blanks, absent == empty."""
    if a is None or b is None:
        return str(a or "").rstrip() == str(b or "").rstrip()
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except ArithmeticError:
        return str(a).rstrip(" \x00") == str(b).rstrip(" \x00")


def compare_events(cobol: list[dict[str, Any]], java: list[dict[str, Any]]) -> dict[str, Any]:
    """Events paired in order; per pair, every differing field. {events, equal, diffs}."""
    diffs, equal = [], 0
    for n in range(max(len(cobol), len(java))):
        c = cobol[n] if n < len(cobol) else None
        j = java[n] if n < len(java) else None
        if c is None or j is None or c["event"] != j["event"]:
            diffs.append({"event": n + 1, "cobol": c and c["event"], "java": j and j["event"]})
            continue
        bad = []
        for key in ("map", "transid", "program", "text", "abcode", "queue"):
            if key in c and not _same(c[key], j.get(key)):
                bad.append({"field": key, "cobol": c[key], "java": j.get(key)})
        for part in ("screen", "commarea"):
            cv, jv = c.get(part) or {}, j.get(part) or {}
            for name in cv:
                if not _same(cv[name], jv.get(name)):
                    bad.append({"field": f"{part}.{name}", "cobol": cv[name], "java": jv.get(name)})
        if c["event"] == "SEND-MAP" and "subfields" in c:  # #4053: attributes, colour, highlight, cursor, options
            cs, js = c["subfields"], java_subfields(j.get("subfields"))
            for name in sorted(set(cs) | set(js)):
                if cs.get(name, {}) != js.get(name, {}):
                    bad.append({"field": f"subfields.{name}", "cobol": cs.get(name, {}), "java": js.get(name, {})})
            if sorted(c.get("options") or []) != sorted(j.get("options") or []):
                bad.append({"field": "options", "cobol": c.get("options"), "java": j.get("options")})
            if c.get("cursor") != j.get("cursor"):
                bad.append({"field": "cursor", "cobol": c.get("cursor"), "java": j.get("cursor")})
        if bad:
            diffs.append({"event": n + 1, "kind": c["event"], "fields": bad})
        else:
            equal += 1
    return {"events": max(len(cobol), len(java)), "equal": equal, "diffs": diffs}


def report_markdown(case: dict[str, Any], report: dict[str, Any]) -> str:
    about = (
        f"Case `{case['name']}`: {case['corpus']} `{case['program_source']}`, transaction {case['transid']}, "
        f"clock `{case['clock']}`. Each scenario is one task; its events (SEND MAP, SEND TEXT, RETURN, "
        "XCTL, ABEND) are paired in order and compared field by field -- screen DATA fields and every "
        "COMMAREA field (attribute bytes are not compared)."
    )
    lines = [f"# {case['program']} -- COBOL vs Java ({report['java']}), CICS", "", about, "",
             "Stub files, from the engine's facts: " + "; ".join(
                 f"`{f['file']}` -> {f['base']} key {f['key_length']}@{f['key_offset']}"
                 + (f" via {', '.join(f['via'])}" if f["via"] else "") for f in report["files"]), "",
             "| scenario | events equal | total |", "|---|---|---|"]  # fmt: skip
    for name, d in report["outputs"].items():
        lines.append(f"| {name} | {d['equal']} | {d['records']} |")
    lines += cov.report_lines(report.get("coverage"), len(report["outputs"]), report.get("proven", False), "scenario")
    for name, d in report["outputs"].items():
        if d["diffs"]:
            lines += ["", f"## {name}: differences", "", "| event | field | COBOL | Java |", "|---|---|---|---|"]
            for x in d["diffs"][:200]:
                if "fields" not in x:
                    lines.append(f"| {x['event']} | (event) | `{x['cobol']}` | `{x['java']}` |")
                for fd in x.get("fields", []):
                    lines.append(f"| {x['event']} ({x['kind']}) | {fd['field']} | `{fd['cobol']}` | `{fd['java']}` |")
    return "\n".join(lines) + "\n"


def feedback_md(case: dict[str, Any], report: dict[str, Any], limit: int = 6) -> str:
    """#4023 follow-up: the proof's findings for the porting loop's next attempt -- per scenario that is not equal,
    its inputs (COMMAREA, key, screen input, injected conditions) and the first differing events, field by field."""
    out: list[str] = []
    for sc in case["scenarios"]:
        o = report["outputs"].get(sc["name"])
        fired = (o or {}).get("fired")
        bad_fired = bool(sc.get("faults")) and (not fired or not fired["cobol"] or fired["cobol"] != fired["java"])
        if o is None or (o["equal"] == o["records"] and not bad_fired):
            continue
        out += [f"### Scenario {sc['name']}: {o['equal']}/{o['records']} events equal", "",
                f"Key {sc.get('aid', 'DFHENTER')}; COMMAREA {json.dumps(sc.get('commarea'))}; "
                f"screen input {json.dumps(sc.get('receive'))}"
                + (f"; injected {json.dumps(sc['faults'])}" if sc.get("faults") else ""), ""]  # fmt: skip
        if bad_fired:
            out += [f"Injected conditions fired: COBOL {fired and fired['cobol']}, Java {fired and fired['java']}", ""]
        for x in o["diffs"][:limit]:
            if "fields" not in x:
                out.append(f"- event {x['event']}: COBOL `{x.get('cobol')}`, Java `{x.get('java')}`")
            for fd in x.get("fields", [])[:10]:
                out.append(
                    f"- event {x['event']} ({x.get('kind')}) {fd['field']}: COBOL `{fd['cobol']}`, Java `{fd['java']}`"
                )
        out.append("")
    return "\n".join(out).strip()


def _fired(log: Path) -> list[str]:
    return sorted(x for x in log.read_text(encoding="ascii").splitlines() if x.strip()) if log.is_file() else []


def run_case(case: dict[str, Any], corpus: Path, work: Path, port: bool = True, port_dir: Path | None = None,
             cobol_only: bool = False) -> int:  # fmt: skip
    """A CICS case end to end: facts -> stub files, the COBOL tasks, the Java tasks, the report."""
    import json

    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

    ir = load_galaxy_ir(scan_to_db(corpus, work / "scan"))
    files = stub_files(ir, case["program_source"], case.get("datasets"))
    cobol = run_cobol_cics(case, corpus, work / "cobol", files)
    if cobol_only:
        for name, res in cobol.items():
            print(f"{name}: " + "; ".join(res["events"]))
        return 0
    try:
        java = run_java_cics(case, corpus, work / "java", work / "cobol", files, port, port_dir)
    except RuntimeError as e:  # the port does not compile, or its run fails: the loop's feedback, not a crash
        failed = common.java_failure_report(case, work, str(e))
        (work / "report.json").write_text(json.dumps(failed, indent=2) + "\n", encoding="utf-8")
        print(f"{case['program']}: the Java side failed -- see {work / 'report.json'}")
        return 1
    report: dict[str, Any] = {"case": case["name"], "program": case["program"], "kind": "cics", "files": files,
                              "java": "ported" if port else "generated", "outputs": {}}  # fmt: skip
    ok = True
    for name, res in cobol.items():
        cev, jev = linked_result(case, cobol_events(res)), linked_result(case, java.get(name, []))
        d = compare_events(cev, jev)
        report["outputs"][name] = {"equal": d["equal"], "records": d["events"], "diffs": d["diffs"],
                                   "cobol": cev, "java": jev}  # fmt: skip
        ok &= d["equal"] == d["events"]
        sc = next(x for x in case["scenarios"] if x["name"] == name)
        if sc.get("faults"):  # #4023 follow-up: the same injected conditions fired on both sides, and at least one
            fired = {"cobol": _fired(work / "cobol" / "scenarios" / name / "out" / "faults.txt"),
                     "java": _fired(work / "java" / "out" / f"{name}.faults")}  # fmt: skip
            report["outputs"][name]["fired"] = fired
            if not fired["cobol"] or fired["cobol"] != fired["java"]:
                ok = False
                print(f"{case['program']} {name}: faults fired differ or none fired: {fired}")
        print(f"{case['program']} {name}: {d['equal']}/{d['events']} events equal")
        for x in d["diffs"][:6]:
            print(f"   event {x['event']}: {x.get('fields', [])[:3] or (x.get('cobol'), x.get('java'))}")
        changed = compare_files(case, corpus, files, res.get("files", {}), work / "java" / "out", name)
        changed.update(compare_db2(case, res.get("db2", {}), work / "java" / "out", name))
        if changed:  # file updates: what the task left in a file differs
            report["outputs"][name]["files"] = changed
            ok = False
            for base, fd in changed.items():
                print(f"{case['program']} {name}: file {base}: {fd['equal']}/{fd['records']} records equal")
    report["proven"] = ok
    report["feedback"] = feedback_md(case, report) if not ok else ""
    covered = work / "cobol" / "coverage.json"  # #4023
    report["coverage"] = json.loads(covered.read_text(encoding="utf-8")) if covered.is_file() else None
    if report["coverage"] and "error" in report["coverage"]:
        report["coverage"] = None
    (work / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    (work / "report.md").write_text(report_markdown(case, report), encoding="utf-8")
    if report["coverage"]:
        print(f"{case['program']} COBOL coverage: {cov.headline(report['coverage'], len(cobol), ok, 'scenario')}")
    print(f"report: {work / 'report.json'}")
    return 0 if ok else 1
