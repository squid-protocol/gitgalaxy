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
import equivalence_inputs  # #3804
import equivalence_oracle
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
    "UOWLNOTFOUND": 103, "CONTAINERERR": 110, "CHANNELERR": 122, "CCSIDERR": 123, "TIMEDOUT": 124, "CODEPAGEERR": 125,
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
    NOHANDLE"; NOHANDLE: "no action is to be taken for any condition or attention identifier (AID)")."""
    if opts.get("RESP") or "NOHANDLE" in opts:
        return []
    return (["IF GG-RESP = 0", "    MOVE EIBAID TO GG-NAME1", "    CALL 'GGCAID' USING GG-CICS"]
            + [f"    {ln}" for ln in _transfer(labels)] + ["END-IF"])  # fmt: skip


def _input_resp(opts: dict[str, str | None], labels: list[str], handle_aid: bool) -> list[str]:
    """#4414: an input command's outcome (_resp) and, in a program that issues HANDLE AID, its AID (_aid). Which
    CICS acts on first when the command also raised a condition and a HANDLE AID label applies to the key is not
    documented: GGCAID, called first with the condition, records AID-REFUSED for the driver to refuse."""
    if not handle_aid:
        return _resp(opts, True, labels)
    first = ([] if opts.get("RESP") or "NOHANDLE" in opts
             else ["IF GG-RESP NOT = 0", "    MOVE EIBAID TO GG-NAME1", "    CALL 'GGCAID' USING GG-CICS", "END-IF"])  # fmt: skip
    return first + _resp(opts, True, labels) + _aid(opts, labels)


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
        # #4270 slice 3: STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD, from what the runner states (GGCASGN)
        known = ("ABCODE", "APPLID", "SYSID", "PROGRAM", "INVOKINGPROG", "CHANNEL", "STARTCODE", "USERID", "FACILITY",
                 "SCRNHT", "SCRNWD")  # fmt: skip
        other = [n for n, _v in asked if n not in known]
        if other or not asked or not all(v for _n, v in asked):
            raise Unsupported(
                f"ASSIGN {' '.join(other) or 'without a target'}", [f"ASSIGN {n}" for n in other or ["?"]]
            )
        lines: list[str] = []
        for n, target in asked:
            if n == "CHANNEL":  # #4270: the current channel's name, blanks without one (GGCASCH)
                lines += _call("GGCASCH", []) + [f"MOVE GG-CHAN TO {target}"]
                continue
            if n in ("SCRNHT", "SCRNWD"):  # a halfword, in GG-NUM
                lines += [f"MOVE '{n}' TO GG-NAME2"] + _call("GGCASGN", []) + [f"MOVE GG-NUM TO {target}"]
                continue
            width = {"ABCODE": 4, "APPLID": 8, "SYSID": 4, "PROGRAM": 8, "INVOKINGPROG": 8, "STARTCODE": 2,
                     "USERID": 8, "FACILITY": 4}[n]  # fmt: skip
            lines += ["MOVE SPACES TO GG-NAME2" if n == "ABCODE" else f"MOVE '{n[:8]}' TO GG-NAME2"] + _call(
                "GGCASGN", []
            )
            lines.append(f"MOVE GG-NAME1(1:{width}) TO {target}")
        if not any(n in ("FACILITY", "SCRNHT", "SCRNWD") for n, _v in asked):
            return lines + _resp(opts, False)
        # INVREQ RESP2 5 for a task with no terminal, and then no data area written (register X19)
        check = ["MOVE 'TERMCHK' TO GG-NAME2"] + _call("GGCASGN", [])
        return (check + ["IF GG-RESP = 0"] + [f"    {ln}" for ln in lines] + ["    MOVE 0 TO GG-RESP GG-RESP2", "END-IF"]
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "HANDLE" and kind == "AID":  # #4007
        lines = []
        for key, label in pairs[2:]:
            if key not in AID_KEYS:
                raise Unsupported(f"HANDLE AID {key}: not an attention key", ["HANDLE AID"])
            index = labels.index(label.upper()) + 1 if label else -1  # #4414: -1 deactivated (GGCAID)
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
        if verb == "IGNORE" and cond == "ERROR":  # #4414: IBM does not say whether ERROR's action can be to ignore
            raise Unsupported("IGNORE CONDITION ERROR: not documented", ["IGNORE CONDITION ERROR"])
        index = -1 if verb == "IGNORE" else (labels.index(label.upper()) + 1 if label else 0)
        lines += [f"MOVE {DFHRESP[cond]} TO GG-NUM", f"MOVE {index} TO GG-ITEM"] + _call("GGCHCND", [])
    return lines


def _literal(value: str) -> str | None:
    m = re.fullmatch(r"'([^']*)'|\"([^\"]*)\"", value or "")
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None


def _cfg_flags(case: dict[str, Any], f: dict[str, Any]) -> str:
    """files.cfg's sixth column: the file's flags, comma-separated -- NONE (RECOVERY(NONE)) and ESDS (#4213)."""
    flags = (["NONE"] if _recovery(case, f) else []) + (["ESDS"] if f.get("organization") == "ESDS" else [])
    return " " + ",".join(flags) if flags else ""


def _recovery(case: dict[str, Any], f: dict[str, Any]) -> str:
    """files.cfg's sixth column: " NONE" for a file whose dataset the case says the CSD defines RECOVERY(NONE)
    (`"recovery": "NONE"`, a deployment fact with its `why`): CICS does not back out its changes."""
    spec = case.get("datasets", {}).get(f["base"]) or {}
    return " NONE" if str(spec.get("recovery", "")).upper() == "NONE" else ""


def non_recoverable_files(case: dict[str, Any], files: list[dict[str, Any]]) -> list[str]:
    """The CICS files whose changes survive a backout (RECOVERY(NONE))."""
    return sorted({f["file"] for f in files if _recovery(case, f)})


def _counters(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, int]:
    """The named counters a scenario's region has ("POOL/NAME": the next value): the scenario's, else the case's."""
    return dict(sc["counters"] if "counters" in sc else case.get("counters") or {})


def _past_from(length: str | None, area: str | None, what: str) -> list[str]:
    """A write whose LENGTH runs past its FROM item (GenApp's LGSTSQ): CICS takes the bytes that follow the item in
    storage, which GnuCOBOL lays out unlike IBM's compiler -- the run stops (98, "not modelled", oracle_assumptions.md
    X6) rather than write bytes no oracle here can vouch for."""
    if not length or not area or _literal(area):
        return []
    return [f"IF GG-LEN > LENGTH OF {area}",
            f"    DISPLAY '{what} LENGTH > FROM: not modelled'",
            "    MOVE 98 TO RETURN-CODE", "    STOP RUN", "END-IF"]  # fmt: skip


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
        lines += _past_from(length, area, "WRITEQ TS") + _call("GGCWRTQ", [f"BY REFERENCE {area}"])
        if item and not rewrite:
            after += ["IF GG-RESP = 0", f"    MOVE GG-ITEM TO {item}", "END-IF"]
    if num:
        after += ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {num}", "END-IF"]
    return lines + after + _resp(opts, True, labels)


def _run_transid(opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4270 slice 2: RUN TRANSID(x) CHILD(area) -> GGCRUNT (the child is an event; the runner's scheduler runs it
    once this task has ended). CHANNEL (the child's copy of a channel) is refused, as is any option IBM's RUN TRANSID
    lists beyond TRANSID / CHILD."""
    bad = [o for o in opts if o not in ("RUN", "TRANSID", "CHILD", "RESP", "RESP2", "NOHANDLE")]
    if bad or not opts.get("TRANSID") or not opts.get("CHILD"):
        raise Unsupported(f"RUN {' '.join(bad) or 'without TRANSID / CHILD'}", [f"RUN {o}" for o in bad] or ["RUN"])
    return (
        [f"MOVE {opts['TRANSID']} TO GG-NAME1"]
        + _call("GGCRUNT", [f"BY REFERENCE {opts['CHILD']}"])
        + _resp(opts, True, labels)
    )


def _interval_command(verb: str, opts: dict[str, str | None], labels: list[str]) -> list[str]:
    """#4006: START -> GGCSTRT (the request is an event; the runner's scheduler dispatches it), RETRIEVE
    -> GGCRTRV (LENGTH in-out, set back on NORMAL / LENGERR), CANCEL REQID -> GGCCNCL. #4270: AFTER / AT HOURS /
    MINUTES / SECONDS (GG-HOURS / GG-MINS / GG-SECS, -999999999 when not given) and the data options RTRANSID /
    RTERMID / QUEUE (GG-RTRAN / GG-RTERM / GG-RQUEUE, named in GG-FLAGS) on both."""
    refused = {"START": ("SYSID", "USERID", "CHANNEL", "NOCHECK", "ATTACH", "BREXIT", "FMH"),
               "RETRIEVE": ("SET", "WAIT"),
               "CANCEL": ("TRANSID", "SYSID", "ACTIVITY", "ACQACTIVITY", "ACQPROCESS")}[verb]  # fmt: skip
    bad = [o for o in refused if o in opts]
    if bad:
        raise Unsupported(f"{verb} {' '.join(bad)}", [f"{verb} {o}" for o in bad])
    named = [o for o in ("RTRANSID", "RTERMID", "QUEUE") if o in opts]
    if any(not opts.get(o) for o in named):
        raise Unsupported(f"{verb} {' '.join(named)} without a value", [f"{verb} {o}" for o in named])
    data_in = {"RTRANSID": "GG-RTRAN", "RTERMID": "GG-RTERM", "QUEUE": "GG-RQUEUE"}
    if verb == "START":
        if not opts.get("TRANSID"):
            raise Unsupported("START without TRANSID", ["START"])
        whens = [w for w in ("INTERVAL", "TIME", "AFTER", "AT") if w in opts]
        if len(whens) > 1:
            raise Unsupported(f"START {' and '.join(whens)}", ["START " + " ".join(whens)])
        when = whens[0] if whens else "INTERVAL"
        hms = [o for o in ("HOURS", "MINUTES", "SECONDS") if o in opts]
        if (when in ("AFTER", "AT")) != bool(hms) or any(not opts.get(o) for o in hms):
            raise Unsupported(f"START {when} {' '.join(hms)}", [f"START {when}"])
        area = opts.get("FROM")
        flags = " ".join([when] + (["PROTECT"] if "PROTECT" in opts else []) + named)
        length = opts.get("LENGTH") or opts.get("FLENGTH") or (f"LENGTH OF {area}" if area else "0")
        lines = [f"MOVE {opts['TRANSID']} TO GG-NAME1",
                 f"MOVE {opts['TERMID']} TO GG-NAME2" if opts.get("TERMID") else "MOVE SPACES TO GG-NAME2",
                 f"MOVE {opts['REQID']} TO GG-QNAME" if opts.get("REQID") else "MOVE SPACES TO GG-QNAME",
                 f"MOVE {opts.get(when) or 0} TO GG-NUM",  # (AFTER / AT: GG-HOURS ...)
                 f"MOVE '{flags}' TO GG-FLAGS", f"MOVE {length} TO GG-LEN",
                 f"MOVE {1 if area else 0} TO GG-ITEM"]  # fmt: skip
        if hms:
            lines += [f"MOVE {opts.get(o) or -999999999} TO {f}"
                      for o, f in (("HOURS", "GG-HOURS"), ("MINUTES", "GG-MINS"), ("SECONDS", "GG-SECS"))]  # fmt: skip
        lines += [f"MOVE {opts[o]} TO {data_in[o]}" for o in named]
        lines += _past_from(opts.get("LENGTH") or opts.get("FLENGTH"), area, "START")
        return lines + _call("GGCSTRT", [f"BY REFERENCE {area or 'GG-FLAGS'}"]) + _resp(opts, True, labels)
    if verb == "RETRIEVE":
        into = opts.get("INTO")
        length = opts.get("LENGTH") or opts.get("FLENGTH")
        if not into and (not named or length):
            raise Unsupported("RETRIEVE without INTO", ["RETRIEVE"])
        flags = " ".join((["INTO"] if into else []) + named)
        lines = [f"MOVE '{flags}' TO GG-FLAGS", f"MOVE {length or (f'LENGTH OF {into}' if into else '0')} TO GG-LEN"]
        lines += _call("GGCRTRV", [f"BY REFERENCE {into or 'GG-FLAGS'}"])
        if length:
            lines += ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"]
        if named:
            lines += [
                "IF GG-RESP = 0 OR GG-RESP = 22",
                *[f"    MOVE {data_in[o]} TO {opts[o]}" for o in named],
                "END-IF",
            ]
        return lines + _resp(opts, True, labels)
    if not opts.get("REQID"):
        raise Unsupported("CANCEL without REQID", ["CANCEL without REQID"])
    return [f"MOVE {opts['REQID']} TO GG-QNAME"] + _call("GGCCNCL", []) + _resp(opts, True, labels)


# #4270 slice 4: SEND TEXT options the stub does not model (a BMS logical message, printer formatting, partitions)
_SEND_TEXT_REFUSED = frozenset(
    "ACCUM PAGING SET REQID HEADER TRAILER JUSTIFY JUSFIRST JUSLAST NLEOM FORMFEED HONEOM L40 L64 L80 LDC OUTPARTN "
    "ACTPARTN MSR FMHPARM DEFAULT ALTERNATE".split()
)


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
        for bad in ("GENERIC", "GTEQ", "SET", "SYSID", "RBA", "XRBA", "RRN", "TOKEN"):
            if bad in opts:
                raise Unsupported(f"READ {bad}")
        file, into, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("INTO"), opts.get("RIDFLD")
        if not (file and into and ridfld):
            raise Unsupported("READ without FILE / INTO / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        update = "MOVE 'UPDATE' TO GG-FLAGS" if "UPDATE" in opts else "MOVE SPACES TO GG-FLAGS"  # holds the record
        # #4436: LENGTH is in-out (IBM, EXEC CICS READ): in, the most INTO takes (a longer record is truncated, with
        # LENGERR); out, the record's length, on NORMAL and LENGERR. Without it, LENGTH OF INTO (as the translator
        # supplies it). A literal / LENGTH OF is set in a temporary no one reads.
        length = opts.get("LENGTH")
        settable = bool(length) and re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()) is None
        after = ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"] if settable else []
        return ([name(file, "GG-NAME1"), update, f"MOVE {length or f'LENGTH OF {into}'} TO GG-LEN"]
                + _call("GGCREAD", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {into}",
                                    f"BY VALUE LENGTH OF {into}"])
                + after + _resp(opts, True, labels))  # fmt: skip
    if verb == "WRITE" and {"FILE", "DATASET"} & set(opts):
        for bad in ("MASSINSERT", "SYSID", "RBA", "XRBA", "RRN"):
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
    if verb == "STARTBR":  # browse (CardDemo's lists): one browse per file, full keys -- or an ESDS's RBAs (#4213)
        rba = "RBA" in opts
        for bad in ("GENERIC", "REQID", "SYSID", "RRN", "XRBA", "DEBKEY", "DEBREC") + (
            ("GTEQ", "KEYLENGTH") if rba else ()
        ):
            if bad in opts:
                raise Unsupported(f"STARTBR {'RBA ' if rba else ''}{bad}")
        file, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("RIDFLD")
        if not (file and ridfld):
            raise Unsupported("STARTBR without FILE / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        # GTEQ is a keyed browse's default; EQUAL "is the default for a direct ESDS browse" (IBM, STARTBR), and GTEQ
        # "is not valid for directly browsing an ESDS"
        mode = ("MOVE 'EQUAL RBA' TO GG-FLAGS" if rba else
                "MOVE 'EQUAL' TO GG-FLAGS" if "EQUAL" in opts else "MOVE SPACES TO GG-FLAGS")  # fmt: skip
        return ([name(file, "GG-NAME1"), mode] + _call("GGCSTBR", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb in ("READNEXT", "READPREV"):
        rba = "RBA" in opts  # #4213: every READNEXT / READPREV of an RBA browse says RBA too
        for bad in ("GENERIC", "REQID", "SYSID", "RRN", "XRBA", "SET", "UPDATE", "TOKEN", "NOSUSPEND") + (
            ("KEYLENGTH",) if rba else ()
        ):
            if bad in opts:
                raise Unsupported(f"{verb} {'RBA ' if rba else ''}{bad}")
        file, into, ridfld = opts.get("FILE") or opts.get("DATASET"), opts.get("INTO"), opts.get("RIDFLD")
        if not (file and into and ridfld):
            raise Unsupported(f"{verb} without FILE / INTO / RIDFLD")
        keylen = opts.get("KEYLENGTH") or f"LENGTH OF {ridfld}"
        stub = "GGCRDNX" if verb == "READNEXT" else "GGCRDPV"
        return ([name(file, "GG-NAME1"), "MOVE 'RBA' TO GG-FLAGS" if rba else "MOVE SPACES TO GG-FLAGS"]
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
        for bad in ("GENERIC", "REQID", "SYSID", "RBA", "XRBA", "RRN", "TOKEN", "NOSUSPEND", "NUMREC"):
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
    if verb in ("ENQ", "DEQ", "DELAY"):
        # one task in the region: nothing else holds the resource (ENQ / DEQ NORMAL), and a task takes no time, a
        # DELAY included (EIBTIME / ASKTIME stay as dispatched; oracle_assumptions.md X4)
        allowed = {"ENQ": {"RESOURCE", "LENGTH", "NOSUSPEND", "TASK", "UOW", "MAXLIFETIME"},
                   "DEQ": {"RESOURCE", "LENGTH", "TASK", "UOW", "MAXLIFETIME"},
                   "DELAY": {"FOR", "INTERVAL", "TIME", "HOURS", "MINUTES", "SECONDS", "MILLISECS"}}[verb]  # fmt: skip
        bad = [o for o in opts if o not in allowed | {verb, "RESP", "RESP2", "NOHANDLE"}]
        if bad:
            raise Unsupported(f"{verb} {' '.join(bad)}", [f"{verb} {bad[0]}"])
        return ["MOVE 0 TO GG-RESP", "MOVE 0 TO GG-RESP2"] + _resp(opts, False, labels)
    if verb == "GET" and "COUNTER" in opts:  # a named counter (IBM CICS TS, GET COUNTER): its value, then +1
        bad = [o for o in opts if o not in ("GET", "COUNTER", "POOL", "VALUE", "RESP", "NOHANDLE")]
        if bad or not opts.get("VALUE"):
            raise Unsupported(f"GET COUNTER {' '.join(bad) or 'without VALUE'}", ["GET COUNTER"])
        return ([name(opts["COUNTER"], "GG-QNAME"), name(opts.get("POOL") or "' '", "GG-NAME1")]
                + _call("GGCGCNT", []) + ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['VALUE']}", "END-IF"]
                + _resp(opts, True, labels))  # fmt: skip
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
                + _input_resp(opts, labels, handle_aid))  # fmt: skip
    if verb == "RECEIVE":  # #4005: terminal input, unformatted (SPEC 5: the step's `text`)
        for bad in ("BUFFER", "ASIS", "PARTN", "SESSION", "CONVID", "LDC"):
            if bad in opts:
                raise Unsupported(f"RECEIVE {bad}", [f"RECEIVE {bad}"])
        into, setp = opts.get("INTO"), opts.get("SET")
        # LENGTH / FLENGTH is in-out: in, the most INTO takes (unless MAXLENGTH / MAXFLENGTH says so);
        # out, the length of the data. COBOL may omit it: the translator supplies LENGTH OF INTO.
        length = opts.get("LENGTH") or opts.get("FLENGTH")
        most = opts.get("MAXLENGTH") or opts.get("MAXFLENGTH")
        flags = "MOVE 'NOTRUNCATE' TO GG-FLAGS" if "NOTRUNCATE" in opts else "MOVE SPACES TO GG-FLAGS"  # #4413
        if setp:  # #4413: SET(ADDRESS OF record), MAXLENGTH and LENGTH(data-area) required (det/cics.py says why)
            m = re.fullmatch(r"ADDRESS\s+OF\s+([A-Z0-9-]+)", setp, re.I)
            if into or not m or not most or not length:
                raise Unsupported("RECEIVE SET other than ADDRESS OF with MAXLENGTH and LENGTH", ["RECEIVE SET"])
            return ([flags, f"MOVE {most} TO GG-LEN"] + _call("GGCRECS", ["BY REFERENCE GG-PTR"])
                    + [f"SET ADDRESS OF {m.group(1)} TO GG-PTR", f"MOVE GG-LEN TO {length}"]
                    + _input_resp(opts, labels, handle_aid))  # fmt: skip
        if not into:
            raise Unsupported("RECEIVE without INTO", ["RECEIVE"])
        limit = most or length or f"LENGTH OF {into}"
        lines = [flags, f"MOVE {limit} TO GG-LEN"] + _call("GGCRECT", [f"BY REFERENCE {into}"])
        if length:
            lines.append(f"MOVE GG-LEN TO {length}")
        return lines + _input_resp(opts, labels, handle_aid)
    if verb == "WRITEQ" and "TD" in opts:  # transient data: a record on an extrapartition / intrapartition queue
        for bad in ("SYSID",):
            if bad in opts:
                raise Unsupported(f"WRITEQ TD {bad}", [f"WRITEQ TD {bad}"])
        queue, frm = opts.get("QUEUE"), opts.get("FROM")
        if not (queue and frm):
            raise Unsupported("WRITEQ TD without QUEUE / FROM", ["WRITEQ TD"])
        return ([name(queue, "GG-QNAME"), f"MOVE {opts.get('LENGTH') or 'LENGTH OF ' + frm} TO GG-LEN"]
                + _past_from(opts.get("LENGTH"), frm, "WRITEQ TD")
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
    if verb == "SEND" and "CONTROL" in opts:  # #4413: device controls; CURSOR's value in GG-LEN, -1: none
        bad = [o for o in opts if o not in ("SEND", "CONTROL", "ERASE", "ERASEAUP", "FREEKB", "ALARM", "FRSET",
                                            "CURSOR", "RESP", "RESP2", "NOHANDLE")]  # fmt: skip
        if bad or ("CURSOR" in opts and not opts["CURSOR"]):
            raise Unsupported(f"SEND CONTROL {' '.join(bad) or 'CURSOR without a value'}", ["SEND CONTROL"])
        ctl = sorted(o for o in opts if o in ("ERASE", "ERASEAUP", "FREEKB", "ALARM", "FRSET", "CURSOR"))
        return ([f"MOVE '{' '.join(ctl)[:40]}' TO GG-FLAGS" if ctl else "MOVE SPACES TO GG-FLAGS",
                 f"MOVE {opts.get('CURSOR') or '-1'} TO GG-LEN"]
                + _call("GGCSCTL", []) + _resp(opts, can_fail=False))  # fmt: skip
    if verb == "SEND" and ("TEXT" in opts or "FROM" in opts) and "CONTROL" not in opts:
        src = opts.get("FROM")
        if not src:
            raise Unsupported("SEND TEXT without FROM")
        # #4270 slice 4: TERMINAL, the default output disposition (the principal facility), changes nothing; the
        # full-BMS / printer / partition options are refused by name, as the det port refuses them (register X20)
        bad = [o for o in opts if o in _SEND_TEXT_REFUSED]
        if bad:
            raise Unsupported(f"SEND TEXT {' '.join(bad)}", [f"SEND TEXT {o}" for o in bad])
        kind = ["TEXT"] if "TEXT" in opts else ["DATA"]
        textflags = " ".join(kind + [n for n in flags if n in ("ERASE", "FREEKB", "ALARM", "WAIT", "LAST")])
        return ([f"MOVE '{textflags[:40]}' TO GG-FLAGS"]
                + _call("GGCSTXT", [f"BY REFERENCE {src}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {src}'}"])
                + _resp(opts, can_fail=False))  # fmt: skip
    if verb in ("RETURN", "XCTL"):
        if verb == "XCTL" and not opts.get("PROGRAM"):
            raise Unsupported("XCTL without PROGRAM")
        for bad in ("INPUTMSG", "IMMEDIATE", "ENDACTIVITY") + (("CHANNEL",) if verb == "RETURN" else ()):
            if bad in opts:
                raise Unsupported(f"{verb} {bad}")
        if verb == "XCTL" and opts.get("CHANNEL"):  # #4270: the target's current channel (GGCXCTL)
            if opts.get("COMMAREA"):
                raise Unsupported("XCTL CHANNEL with COMMAREA", ["XCTL CHANNEL"])
            return ([name(opts["PROGRAM"], "GG-NAME1"), "MOVE 0 TO GG-ITEM", "MOVE 'CHANNEL' TO GG-FLAGS",
                     f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
                    + _call("GGCXCTL", ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])
                    + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
        target = opts.get("TRANSID") if verb == "RETURN" else opts.get("PROGRAM")
        area = opts.get("COMMAREA")
        args = ([f"BY REFERENCE {area}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {area}'}"] if area
                else ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])  # fmt: skip
        if verb == "RETURN":
            return [name(target, "GG-NAME1")] + _call("GGCRETN", args) + ["GOBACK"]
        # #4008: a failed XCTL (LENGERR, PGMIDERR) leaves control here, through the condition handling
        return ([name(target, "GG-NAME1"), f"MOVE {1 if area else 0} TO GG-ITEM", "MOVE SPACES TO GG-FLAGS"]
                + _call("GGCXCTL", args)
                + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
    if verb == "RUN":  # #4270 slice 2: RUN TRANSID CHILD (a channel copy and FETCH: later)
        return _run_transid(opts, labels)
    if verb in ("START", "RETRIEVE", "CANCEL"):  # #4006: interval control
        return _interval_command(verb, opts, labels)
    if verb == "LINK":  # #4004: a new level runs the program on the caller's own COMMAREA storage
        for bad in ("SYSID", "TRANSID", "SYNCONRETURN", "INPUTMSG", "INPUTMSGLEN", "DATALENGTH"):
            if bad in opts:
                raise Unsupported(f"LINK {bad}", [f"LINK {bad}"])
        if not opts.get("PROGRAM"):
            raise Unsupported("LINK without PROGRAM", ["LINK"])
        if "CHANNEL" in opts and (opts.get("COMMAREA") or not opts["CHANNEL"]):
            raise Unsupported("LINK CHANNEL with COMMAREA", ["LINK CHANNEL"])
        area = opts.get("COMMAREA")
        # #4270: CHANNEL -- the callee's current channel (GGCLINK)
        chan = (
            ["MOVE 'CHANNEL' TO GG-FLAGS", f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
            if opts.get("CHANNEL")
            else ["MOVE SPACES TO GG-FLAGS"]
        )
        length = opts.get("LENGTH") or opts.get("FLENGTH") or (f"LENGTH OF {area}" if area else "0")
        ref = area or "GG-FLAGS"
        return ([name(opts["PROGRAM"], "GG-NAME1"), f"MOVE {length} TO GG-LEN", f"MOVE {1 if area else 0} TO GG-ITEM"]
                + chan + _call("GGCLINK", [f"BY REFERENCE {ref}"])
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
    if verb in ("PUT", "GET", "DELETE") and "CONTAINER" in opts:  # #4270
        return _container_command(verb, opts, labels)
    raise Unsupported(" ".join(n for n, _ in pairs[:2]), [_feature(pairs)])


_CONTAINER_OPTIONS = {
    "PUT": {"CONTAINER", "CHANNEL", "FROM", "FLENGTH", "BIT", "CHAR", "DATATYPE", "APPEND"},
    "GET": {"CONTAINER", "CHANNEL", "INTO", "FLENGTH", "NODATA"},
    "DELETE": {"CONTAINER", "CHANNEL"},
}


def _container_command(verb: str, opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4270: PUT / GET / DELETE CONTAINER -> GGCPUTC / GGCGETC / GGCDELC. The container's name in GG-QNAME, the
    channel's in GG-CHAN (GG-FLAGS 'CHANNEL'; none: the current channel), the data type, APPEND and NODATA in
    GG-FLAGS, FLENGTH in GG-LEN (PUT: the bytes FROM gives; GET: the most INTO takes, then the container's length,
    set back on NORMAL / LENGERR). The CCSID options (code-page conversion), SET (a pointer), BYTEOFFSET and PREPEND
    are refused, as det/cics.py refuses them; so is an FLENGTH past FROM / INTO (storage GnuCOBOL lays out unlike
    IBM's compiler)."""
    feature = f"{verb} CONTAINER"
    bad = sorted(o for o in opts if o not in _CONTAINER_OPTIONS[verb] | {verb, "RESP", "RESP2", "NOHANDLE"})
    if bad or not opts.get("CONTAINER"):
        raise Unsupported(f"{feature} {' '.join(bad) or 'without a name'}", [f"{feature} {o}" for o in bad or ["?"]])
    flags = ["CHANNEL"] if opts.get("CHANNEL") else []
    lines = [f"MOVE {opts['CONTAINER']} TO GG-QNAME",
             f"MOVE {opts['CHANNEL']} TO GG-CHAN" if opts.get("CHANNEL") else "MOVE SPACES TO GG-CHAN"]  # fmt: skip
    if verb == "DELETE":
        return (
            lines
            + [f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS"]
            + _call("GGCDELC", [])
            + _resp(opts, True, labels)
        )
    flength = opts.get("FLENGTH")
    if verb == "PUT":
        frm = opts.get("FROM")
        if not frm:
            raise Unsupported("PUT CONTAINER without FROM", [feature])
        types = [t for t in ("BIT", "CHAR") if t in opts]
        if opts.get("DATATYPE"):
            m = re.fullmatch(r"\s*DFHVALUE\s*\(\s*(BIT|CHAR)\s*\)\s*", opts["DATATYPE"], re.I)
            if m is None:
                raise Unsupported(f"PUT CONTAINER DATATYPE({opts['DATATYPE']})", [f"{feature} DATATYPE"])
            types.append(m.group(1).upper())
        if len(types) > 1:
            raise Unsupported("PUT CONTAINER with two data types", [feature])
        flags += types + (["APPEND"] if "APPEND" in opts else [])
        return (lines + [f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS",
                         f"MOVE {flength or f'LENGTH OF {frm}'} TO GG-LEN"]
                + _past_from(flength, frm, "PUT CONTAINER") + _call("GGCPUTC", [f"BY REFERENCE {frm}"])
                + _resp(opts, True, labels))  # fmt: skip
    into, nodata = opts.get("INTO"), "NODATA" in opts
    if bool(into) == nodata:
        raise Unsupported("GET CONTAINER needs one of INTO / NODATA", [feature])
    flags += ["NODATA"] if nodata else []
    settable = bool(flength) and re.fullmatch(r"(?is)[+-]?\d+|LENGTH\s+OF\s+.+", flength.strip()) is None
    lines += [
        f"MOVE '{' '.join(flags)}' TO GG-FLAGS" if flags else "MOVE SPACES TO GG-FLAGS",
        "MOVE 0 TO GG-LEN" if nodata else f"MOVE {flength or f'LENGTH OF {into}'} TO GG-LEN",
    ]
    if into and flength:
        lines += _past_from(flength, into, "GET CONTAINER")
    lines += _call("GGCGETC", [f"BY REFERENCE {into or 'GG-FLAGS'}"])
    if settable:
        lines += ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {flength}", "END-IF"]
    return lines + _resp(opts, True, labels)


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
    # the COMMAREA: an 01 DFHCOMMAREA, or a copybook's record renamed to it (CBSA's COPY INQACC REPLACING
    # INQACC-COMMAREA BY DFHCOMMAREA)
    has_commarea = bool(
        re.search(r"^.{6} +01\s+DFHCOMMAREA\b", text, re.M | re.I)
        or re.search(r"^.{6} +COPY\s+\S+\s+REPLACING\b[^.]*\bBY\s+DFHCOMMAREA\b", text, re.M | re.I)
    )
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
def _case_csd(file: str, datasets: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """#4213: a CICS file the estate defines nowhere (no CSD DEFINE FILE, no IDCAMS DEFINE: IBM DBB MortgageApplication
    ships neither for EPSMORTF), stated by the case's dataset of that name as a deployment fact with its `why`:
    `"csd": {"organization": "ESDS", "reclen": N, "why": ...}`. Only an ESDS of fixed-length records is stated so."""
    spec = ((datasets or {}).get(file.upper()) or {}).get("csd")
    if spec is None:
        return None
    if (
        str(spec.get("organization", "")).upper() != "ESDS"
        or not isinstance(spec.get("reclen"), int)
        or not spec.get("why")
    ):
        raise Unsupported(f"CICS file {file}: a case's csd states an ESDS, its reclen and why ({spec})")
    return {"file": file.upper(), "dsname": file.upper(), "base": file.upper(), "key_offset": 0, "key_length": 0,
            "reclen": spec["reclen"], "via": ["the case's csd"], "organization": "ESDS"}  # fmt: skip


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
            stated = _case_csd(e["name"], datasets)
            if stated is None:
                raise Unsupported(f"CICS file {e['name']}: no CSD DEFINE FILE with a DSNAME")
            out.append(stated)
            continue
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
        if key is d and (d.organization or "").upper() == "NONINDEXED":  # #4213: an ESDS: no key, browsed by RBA
            reclen = d.record_max if d.record_max is not None else stated.get("reclen")
            if reclen is None or (d.record_avg is not None and d.record_avg != reclen):
                raise Unsupported(f"CICS file {e['name']}: ESDS {d.name} without fixed-length records (RECORDSIZE)")
            out.append({"file": e["name"], "dsname": dsn, "base": d.name.upper(), "key_offset": 0, "key_length": 0,
                        "reclen": reclen, "via": via, "organization": "ESDS"})  # fmt: skip
            continue
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
        if f["name"] == "FILLER":  # unnamed: no DTO property holds it, and several would share one key
            continue
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
    return common.layout_fields(corpus, str(common.case_path(corpus, scr["copybook"])), scr[side])


# #4023 follow-up: the conditions a scenario may inject, by name -> their DFHRESP numbers (IBM CICS "RESP values")
CICS_RESP = {"NORMAL": 0, "FILENOTFOUND": 12, "NOTFND": 13, "DUPREC": 14, "INVREQ": 16, "IOERR": 17, "NOSPACE": 18,
             "NOTOPEN": 19, "ILLOGIC": 21, "LENGERR": 22, "PGMIDERR": 27, "NOTAUTH": 70, "DISABLED": 84,
             "LOADING": 94, "ENDFILE": 20, "TERMIDERR": 11, "ITEMERR": 26, "TRANSIDERR": 28, "QIDERR": 44,
             "SYSIDERR": 53, "ISCINVREQ": 54, "LOCKED": 100}  # fmt: skip


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
    # #4049: the program-control, temporary-storage and interval-control commands. A plan names the resource the
    # command names -- XCTL its `program`, WRITEQ-TS its `queue`, START its `transid`, CANCEL its `reqid` --
    # and RETRIEVE, which names none, `-`. Plan only a condition IBM documents for the command (CICS TS, the
    # command's "Conditions"): XCTL PGMIDERR (RESP2 3: the program could not be loaded), NOTAUTH (101), INVREQ;
    # WRITEQ TS INVREQ, IOERR (RESP2 5), NOSPACE (only with NOSUSPEND), NOTAUTH (101), LOCKED; START INVREQ,
    # IOERR, NOTAUTH (7), TRANSIDERR, TERMIDERR, SYSIDERR (1); RETRIEVE ENDDATA, ENVDEFERR, INVREQ, IOERR,
    # LENGERR; CANCEL NOTFND, NOTAUTH, ISCINVREQ, SYSIDERR (CANCEL has no INVREQ).
    "XCTL",
    "WRITEQ-TS",
    "START",
    "RETRIEVE",
    "CANCEL",
)  # a file command (FILE), an INQUIRE PROGRAM (the program's name in `file`)

_FAULT_NAME = ("file", "program", "queue", "transid", "reqid")  # #4049: the resource a fault names, by key


def case_file_records(case: dict[str, Any], corpus: Path, spec: dict[str, Any], reclen: int, enc: str) -> bytes:
    """A CICS file's records: its dataset's `input`, then (#4049) the records of `append` -- a case's own file of
    records added after the corpus's (the test-strengthening loop's new accounts, customers ...)."""
    data = common._fixed(common._input_path(case, corpus, spec["input"]), reclen, enc)
    if spec.get("append"):
        data += common._fixed(common._input_path(case, corpus, spec["append"]), reclen, enc)
    return data


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
        name = "-" if cmd == "RETRIEVE" else next((f[k] for k in _FAULT_NAME if f.get(k)), None)
        if not name:
            raise Unsupported(f"scenario {sc['name']}: fault {f} names no {'/'.join(_FAULT_NAME)}")
        out.append(f"{cmd} {name} {nth} {CICS_RESP[f['resp']]} {int(f.get('resp2', 0))}")
    return out


RECOVER: dict[str, Any] = {}  # #4173: a COBOL work area -> its coverage recomputed for the tasks judged


def run_cobol_cics(case: dict[str, Any], corpus: Path, work: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    """Translate, compile and run each scenario; {scenario: its outputs} (see `outputs`)."""
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    common.stage_copybooks(case, corpus, src)
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
            source, table = equivalence_sql.precompile(
                source, dirs, corpus / case["program_source"], program=case["program"]
            )
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
        f"{f['file']} /work/files/{f['base']} {f['reclen']} {f['key_offset']} {f['key_length']}{_cfg_flags(case, f)}\n"
        for f in files
    ), encoding="ascii")  # fmt: skip
    (work / "files").mkdir(exist_ok=True)
    generated = equivalence_inputs.generate_inputs(case, corpus)  # #3804: `@generate` files, from their layouts
    for f in files:
        spec = case.get("datasets", {}).get(f["base"])
        if spec is None:
            raise Unsupported(f"the case gives no data for {f['base']} (CICS file {f['file']})")
        data = (
            generated[f["base"]] if f["base"] in generated else case_file_records(case, corpus, spec, f["reclen"], enc)
        )
        (work / "files" / f["base"]).write_bytes(data)
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
    # the programs the task may LINK to (a case's "programs": GenApp's LGUPDB01 -> LGUPVS01, LGSTSQ), translated as
    # the program is; a LINK to any other is refused after the run (NOPROGRAM, below)
    linked: dict[str, bool] = {}
    for extra in case.get("programs", []):
        x_text, _ = common.read_program(case, corpus / extra["program_source"])
        x_source, _ = common.compile_options(case, x_text)
        if re.search(r"\bEXEC\s+SQL\b", x_source, re.I):  # its statements join the task's table, ids of its own
            if not db2:
                raise Unsupported(f'{extra["program"]}: EXEC SQL in a case with no "db2" section')
            x_dirs = [corpus / d for d in [*case.get("copy_dirs", []), *db2.get("include_dirs", [])]]
            try:
                x_source, x_table = equivalence_sql.precompile(x_source, x_dirs, corpus / extra["program_source"],
                                                               first_id=1000 * (len(linked) + 1),
                                                               program=extra["program"])  # fmt: skip
            except equivalence_sql.Unsupported as e:
                raise Unsupported(f"{extra['program']}: EXEC SQL: {e}", ["EXEC SQL"]) from e
            stmts_file = work / "stmts.txt"
            have = stmts_file.read_text(encoding="latin-1")
            ours = {ln.split()[5] for ln in have.splitlines() if ln.startswith("S ") and ln.split()[5] != "-"}
            theirs = {ln.split()[5] for ln in x_table.splitlines() if ln.startswith("S ") and ln.split()[5] != "-"}
            if ours & theirs:
                raise Unsupported(f"{extra['program']}: cursor {sorted(ours & theirs)[0]} declared by two programs")
            stmts_file.write_text(have + x_table, encoding="latin-1")
        x_translated, x_ca = translate(x_source)
        name = extra["program"].upper()
        (src / f"{name}.cbl").write_text(x_translated, encoding=staged)
        subs.append(f"src/{name}.cbl")
        linked[name] = x_ca
    if "CALL 'GGCRUN'" in text or linked:  # a LINK: the level's dispatcher, running the case's other programs
        (src / "GGCRUN.cbl").write_text(task_dispatcher(linked), encoding="ascii")
        subs.append("src/GGCRUN.cbl")
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
    sql_table = (work / "stmts.txt").read_text(encoding="latin-1") if db2 else ""
    for sc in case["scenarios"]:  # #4173: each task's SQL faults resolved to the statements they name
        if sc.get("sql_faults") and not db2:
            raise Unsupported(f'scenario {sc["name"]}: SQL faults in a case with no "db2" section')
        sc["sql_plan"] = sql_fault_plan(case, sc, sql_table) if sc.get("sql_faults") else []
    shutil.rmtree(work / "scenarios", ignore_errors=True)  # a second pass (#4173) starts afresh: the logs append
    for sc in case["scenarios"]:
        d = work / "scenarios" / sc["name"]
        (d / "out").mkdir(parents=True, exist_ok=True)
        # each task its own copy of the files: what it writes is its own, and is compared (file updates)
        shutil.copytree(work / "files", d / "files", dirs_exist_ok=True)
        (d / "files.cfg").write_text("".join(
            f"{f['file']} /work/scenarios/{sc['name']}/files/{f['base']} {f['reclen']} {f['key_offset']} "
            f"{f['key_length']}{_cfg_flags(case, f)}\n" for f in files
        ), encoding="ascii")  # fmt: skip
        if sc.get("commarea") is not None:
            (d / "commarea.in").write_bytes(encode_record(ca_fields, sc["commarea"], b"init", enc))
        for m, typed in (sc.get("receive") or {}).items():
            (d / f"receive_{m}.bin").write_bytes(map_input(screen_fields(corpus, case, m, "input"), typed, enc))
        if programs is not None:  # the CSD's programs; absent, every program is defined
            (d / "programs.cfg").write_text("".join(f"{p}\n" for p in programs), encoding="ascii")
        if tdqueues is not None:  # the CSD's transient-data queues; absent, every queue is defined
            (d / "tdqueues.cfg").write_text("".join(f"{q}\n" for q in tdqueues), encoding="ascii")
        if _counters(case, sc):  # named counters the region has (POOL/NAME: value); absent ones are NOTFND
            (d / "counters.cfg").write_text("".join(f"{k.split('/')[0] or '-'} {k.split('/')[1]} {v}\n"
                                                    for k, v in _counters(case, sc).items()), encoding="ascii")  # fmt: skip
        if case.get("region"):  # ASSIGN APPLID / SYSID: the region's identity, a deployment fact the case states
            (d / "region.cfg").write_text(f"APPLID {case['region']['applid']}\nSYSID {case['region']['sysid']}\n",
                                          encoding="ascii")  # fmt: skip
        if sc.get("faults"):  # #4023 follow-up: the stub's injected conditions
            (d / "faults.cfg").write_text("".join(x + "\n" for x in fault_lines(sc)), encoding="ascii")
        if sc.get("sql_plan"):  # #4173: the SQL stub's planned faults (resolved by sql_fault_plan)
            (d / "sqlfaults.cfg").write_text("".join(x + "\n" for x in sc["sql_plan"]), encoding="ascii")
        y, mo, dd = date.split("/")
        eib_date = f"{int(y) - 1900:03d}{_day_of_year(int(y), int(mo), int(dd)):03d}"[-7:].rjust(7, "0")
        eib_time = "0" + time.replace(":", "")[:6]
        (d / "eib.in").write_text(f"{case['transid']:<4} {sc.get('aid', 'DFHENTER'):<8} {eib_date} {eib_time}\n",
                                  encoding="ascii")  # fmt: skip
        rel = f"/work/scenarios/{sc['name']}"
        sqlenv = equivalence_db2.cobol_env("/work/stmts.txt") if db2 else ""
        if db2:  # #4173: each statement the task runs traced; its planned SQL faults, the ones that fire logged
            # #4507: and what Db2 answered each one (equivalence_db2.cobol_outcomes)
            sqlenv += (
                f"GGSQL_TRACE={rel}/sqltrace.txt GGSQL_OUTCOMES={rel}/sqlout.txt GGSQL_FAULTS_LOG={rel}/out/faults.txt "
                + (f"GGSQL_FAULTS={rel}/sqlfaults.cfg " if sc.get("sql_plan") else "")
            )
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
    refused: dict[str, str] = {}  # #4173: a derived SQL-fault task that reaches what is not modelled: that task only
    for sc in case["scenarios"]:  # a LINK reached: the program it names is not run here (no port of it)
        log = work / "scenarios" / sc["name"] / "out" / "events.txt"
        hit = re.search(r"\bNOPROGRAM\b.*?\btarget=(\S*)", log.read_text(encoding="latin-1")) if log.is_file() else None
        if hit and sc.get("derived"):  # #4173: judged up to that LINK only (prefix), its end state not compared
            sc["prefix_link"] = hit.group(1)
            continue
        if hit:
            raise Unsupported(f"scenario {sc['name']}: LINK PROGRAM({hit.group(1)}) -- the case runs one program",
                              ["LINK"])  # fmt: skip
        # a library model (tests/equivalence/le) that stops rather than guess (exit 98, "... not modelled"): the
        # scenario reaches behaviour the oracle cannot judge -- refused by name, never reported as a difference
        rc = work / "scenarios" / sc["name"] / "rc"
        said = work / "scenarios" / sc["name"] / "stdout.txt"
        if rc.is_file() and rc.read_text().strip() == "98" and said.is_file():
            why = next((ln for ln in said.read_text(encoding="latin-1").splitlines() if "not modelled" in ln), None)
            if why and sc.get("derived"):
                refused[sc["name"]] = why.strip()
                continue
            if why:
                raise Unsupported(f"scenario {sc['name']}: {why.strip()}", ["MODEL"])
    (work / "refused.json").write_text(json.dumps(refused, indent=1) + "\n", encoding="utf-8")
    kept = [sc for sc in case["scenarios"] if sc["name"] not in refused]

    # #4023: how much of the program the scenarios execute, together (work/coverage.json)
    def coverage(names: list[str]) -> None:  # (again after the Java side, without tasks it could not judge: #4173)
        cov.write_run_coverage(work / "coverage.json", source=corpus / case["program_source"], original=program,
                               compiled=text, traces=[work / "scenarios" / n / cov.TRACE_NAME for n in names],
                               compiled_name="PROGRAM.cbl", copybooks=corpus, encoding=staged)  # fmt: skip

    coverage([sc["name"] for sc in kept])
    RECOVER[str(work)] = coverage
    return {sc["name"]: outputs(work / "scenarios" / sc["name"] / "out", case, corpus, ca_fields)
            for sc in kept}  # fmt: skip


# ---- #4173: SQL faults -------------------------------------------------------------------------------------------
# The SQLSTATE a fault's SQLCODE carries when the case gives none (IBM Db2 for z/OS Codes)
SQLSTATES = {100: "02000", -803: "23505", -305: "22002", -911: "40001", -913: "57033", -904: "57011", -530: "23503",
             -532: "23504", -180: "22007", -181: "22007", -302: "22001", -501: "24501", -502: "24502"}  # fmt: skip


def sql_statements(table: str) -> list[dict[str, Any]]:
    """The statement table's statements (equivalence_sql: S / Q lines): sid, kind, cursor, program, line, sql."""
    out: list[dict[str, Any]] = []
    for ln in table.splitlines():
        if ln.startswith("S "):
            f = ln.split()
            out.append({"sid": int(f[1]), "kind": f[2], "cursor": f[5], "program": f[6] if len(f) > 6 else "-",
                        "line": int(f[7]) if len(f) > 7 else 0, "sql": ""})  # fmt: skip
        elif ln.startswith("Q ") and out:
            out[-1]["sql"] = ln[2:]
    return out


def sql_fault_plan(case: dict[str, Any], sc: dict[str, Any], table: str) -> list[str]:
    """A scenario's `sql_faults` as both sides read them: `PROGRAM LINE NTH SQLCODE SQLSTATE` (ggsql.c's
    $GGSQL_FAULTS, DetSql.withFaults). A fault names its statement by `line` (and `program`, the case's own by
    default), or by `table` and `verb` (every statement of that kind on that table)."""
    stmts = sql_statements(table)
    out = []
    for f in sc.get("sql_faults") or []:
        code = int(f["sqlcode"])
        state = str(f.get("sqlstate") or SQLSTATES.get(code, ""))
        if not re.fullmatch(r"[0-9A-Z]{5}", state):
            raise Unsupported(f"scenario {sc['name']}: SQL fault {f}: no SQLSTATE for SQLCODE {code} -- give one")
        nth = "*" if f.get("nth", 1) == "*" else int(f.get("nth", 1))
        program = str(f.get("program") or case["program"]).upper()
        if "line" in f:
            hits = [x for x in stmts if x["program"] == program and x["line"] == int(f["line"])]
        else:
            verb, table_name = str(f.get("verb", "")).upper(), str(f.get("table", "")).upper()
            hits = [x for x in stmts if x["program"] == program and x["sql"].upper().split()[:1] == [verb]
                    and re.search(rf"\b{re.escape(table_name)}\b", x["sql"].upper())]  # fmt: skip
        if not hits:
            raise Unsupported(f"scenario {sc['name']}: SQL fault {f} names no statement of {program}")
        out += [f"{x['program']} {x['line']} {nth} {code} {state}" for x in hits]
    return out


# The fault each executed statement is given when the harness enumerates them: the failure the statement's own
# kind meets in practice -- a duplicate key for an INSERT, no row for a SELECT INTO, a timeout (the statement rolled
# back, the unit of work kept: -913, not -911's rollback) for the rest. COMMIT, CLOSE and SET :H = VALUES have none.
def default_fault(stmt: dict[str, Any]) -> Optional[int]:
    verb = (stmt["sql"].upper().split() or [""])[0]
    if stmt["kind"] == "EXEC":
        return -803 if verb == "INSERT" else -913 if verb in ("UPDATE", "DELETE", "MERGE") else None
    if stmt["kind"] == "SELECT1":
        return None if verb == "VALUES" else 100
    if stmt["kind"] in ("OPEN", "FETCH"):
        return -913
    return None


def enumerated_sql_faults(case: dict[str, Any], work: Path) -> list[dict[str, Any]]:
    """#4173: one more task per SQL statement the case's tasks executed -- the first task that executed it, its first
    execution failing with default_fault's SQLCODE (bounded: one per statement)."""
    table = (work / "stmts.txt").read_text(encoding="latin-1") if (work / "stmts.txt").is_file() else ""
    stmts = {(x["program"], x["line"]): x for x in sql_statements(table)}
    seen: set[tuple[str, int]] = set()
    derived = []
    for sc in case["scenarios"]:
        trace = work / "scenarios" / sc["name"] / "sqltrace.txt"
        lines = trace.read_text(encoding="ascii").split() if trace.is_file() else []
        for prog, line in zip(lines[::2], lines[1::2]):
            key = (prog, int(line))
            if key in seen or key not in stmts:
                continue
            seen.add(key)
            code = default_fault(stmts[key])
            if code is None:
                continue
            fault = {"program": prog, "line": int(line), "nth": 1, "sqlcode": code}
            derived.append({**sc, "name": f"{sc['name']}--sql-{prog.lower()}-{line}", "derived": True,
                            "faults": [], "sql_faults": [fault],
                            "why": f"#4173: {sc['name']} with its first {stmts[key]['kind']} at {prog} line {line} "
                                   f"failing (SQLCODE {code})"})  # fmt: skip
    return derived


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
    sqlout = out.parent / "sqlout.txt"  # #4507: what Db2 answered each statement the task ran
    res["sql"] = sqlout.read_text(encoding="latin-1") if sqlout.is_file() else ""
    log = out / "events.txt"
    for line in log.read_text(encoding="latin-1").splitlines() if log.is_file() else []:
        seq, _, rest = line.partition(" ")
        verb, _, args = rest.partition(" ")
        kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
        res["events"].append(rest)
        blob = out / f"{seq}.bin"
        data = blob.read_bytes() if blob.is_file() else b""
        if verb == "LINK":  # #4173: the area as issued (a prefix-judged task compares it at a LINK not run)
            res.setdefault("links", []).append({"target": kv.get("target", ""), "data": data})
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
        elif verb in ("RETURN", "XCTL") and int(kv.get("level", "1")) <= 1:  # the task's own (a LINK level's: no)
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
    layouts = [common.layout_fields(corpus, str(common.case_path(corpus, scr["copybook"])), scr[side])
               for side in ("input", "output")]  # fmt: skip
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


# #4449: the java-facade side's region (the CICS crucible's, #4343, for the equivalence harness's one-task scenarios).
FACADE_JAVA = """    /** #4449: a facade did not run the scenario's task the way its deployed entry point must. */
    static final class FacadeRefused extends RuntimeException {
        FacadeRefused(String message) {
            super(message);
        }
    }

    /** #4449: the scenario's region, joined while the program's facade runs (-Dequivalence.facades=true). It hands
     *  handleTransaction the very task the scenario built (its COMMAREA, key, screen input, files, faults), or
     *  handleLink the level a LINK makes, and refuses any other: a facade that builds a task of its own, runs
     *  another program, or never runs its task here is not running the path the scenario proves. A LINKed program
     *  (a case's `"linked": true`) is entered by handleLink, any other by handleTransaction; a service with neither
     *  runs through runTask, and `entries` says so. */
    static final class FacadeRegion implements CicsTask.Region {
        final CicsTask scenario;
        final Object commarea;
        final String program;
        final boolean linkedEntry;
        final List<Map<String, Object>> entries = new ArrayList<>();
        CicsTask top;  // the scenario's task, until handleTransaction asks the region for it
        CicsTask linked;  // the level a LINK runs, until handleLink asks for it
        String linkedProgram;
        boolean started;  // the scenario's first program began ...
        boolean ended;  // ... and returned normally
        String refused;

        FacadeRegion(CicsTask scenario, Object commarea, String program, boolean linkedEntry) {
            this.scenario = scenario;
            this.commarea = commarea;
            this.program = program;
            this.linkedEntry = linkedEntry;
        }

        @Override
        public CicsTask transaction(String transid, Object ca) {
            CicsTask t = top;
            if (t == null || !t.transid().equals(transid) || ca != commarea) {
                throw new FacadeRefused("a facade asked the region for a task of " + transid
                        + " that is not the one the scenario starts");
            }
            top = null;
            return t;
        }

        @Override
        public CicsTask linked(String p, Object ca) {
            CicsTask t = linked;
            if (t == null || !p.equals(linkedProgram) || area(t) != ca) {
                throw new FacadeRefused("a facade asked the region for a level of " + p
                        + " that is not the LINK the scenario made");
            }
            linked = null;
            return t;
        }

        @Override
        public void run(CicsTask task, String p, Consumer<CicsTask> self) {
            if (task == scenario && !started) {
                if (!p.equals(program)) {
                    throw new FacadeRefused("the facade of " + program + " ran program " + p);
                }
                started = true;
                self.accept(task);
                ended = true;
                return;
            }
            self.accept(task);
        }

        /** The scenario's program, entered through its facade. */
        void start(Object service) {
            if (linkedEntry) {
                Method m = method(service, "handleLink", 1);
                if (m == null) {
                    runTask(service);
                    return;
                }
                if (commarea != null && !m.getParameterTypes()[0].isInstance(commarea)) {
                    throw new FacadeRefused("handleLink of " + program + " takes a " + m.getParameterTypes()[0].getName()
                            + ", the scenario's COMMAREA is a " + commarea.getClass().getName());
                }
                linked = scenario;
                linkedProgram = program;
                entry(program, "handleLink");
                Object got = call(m, service, commarea);
                if (linked != null) {
                    throw new FacadeRefused("handleLink of " + program + " did not run its task in the region");
                }
                if (m.getReturnType() != void.class && got != commarea) {
                    throw new FacadeRefused("handleLink of " + program
                            + " answered a COMMAREA other than the one passed to it by reference");
                }
                return;
            }
            Method one = method(service, "handleTransaction", 1);
            Method two = method(service, "handleTransaction", 2);
            if (one == null && two == null) {
                runTask(service);
                return;
            }
            top = scenario;
            entry(program, "handleTransaction");
            Method used;
            Object got;
            if (commarea == null && one != null) {
                used = one;
                got = call(one, service, scenario.transid());
            } else if (two != null && (commarea == null || two.getParameterTypes()[1].isInstance(commarea))) {
                used = two;
                got = call(two, service, scenario.transid(), commarea);
            } else {
                throw new FacadeRefused("handleTransaction of " + program + " cannot take the COMMAREA ("
                        + commarea.getClass().getName() + ") the task starts with");
            }
            if (top != null) {
                throw new FacadeRefused("handleTransaction of " + program + " did not run its task in the region");
            }
            if (used.getReturnType() != void.class && !answered(got, scenario, used.getReturnType())) {
                throw new FacadeRefused("handleTransaction of " + program
                        + " answered a COMMAREA other than the one its RETURN passes on");
            }
        }

        /** A service with no facade: the scenario through its runTask, as the runTask side runs it. */
        void runTask(Object service) {
            entry(program, "runTask");
            started = true;
            call(method(service, "runTask", 1), service, scenario);
            ended = true;
        }

        /** A program the task LINKs to (the case's `programs`), through its service's handleLink (else runTask). */
        void enter(String p, CicsTask task, Object service) {
            Method m = method(service, "handleLink", 1);
            if (m == null) {
                entry(p, "runTask");
                call(method(service, "runTask", 1), service, task);
                return;
            }
            Object ca = area(task);
            if (ca != null && !m.getParameterTypes()[0].isInstance(ca)) {
                throw new FacadeRefused("handleLink of " + p + " takes a " + m.getParameterTypes()[0].getName()
                        + ", the LINK passed a " + ca.getClass().getName());
            }
            CicsTask outer = linked;
            String outerProgram = linkedProgram;
            linked = task;
            linkedProgram = p;
            entry(p, "handleLink");
            try {
                call(m, service, ca);
            } catch (RuntimeException e) {
                if (linked == task && !(e instanceof FacadeRefused)) {  // it never asked the region for its level
                    throw new FacadeRefused("handleLink of " + p + " threw before it ran its level: " + e);
                }
                throw e;
            }
            if (linked == task) {
                throw new FacadeRefused("handleLink of " + p + " did not run its task in the region");
            }
            linked = outer;
            linkedProgram = outerProgram;
        }

        void entry(String p, String method) {
            Map<String, Object> e = new LinkedHashMap<>();
            e.put("program", p);
            e.put("method", method);
            if (!entries.contains(e)) {
                entries.add(e);
            }
        }

        /** Calls a facade: what the program throws (an abend, a condition) is thrown as itself; what the facade
         *  throws before the scenario's task ran (a task of its own failing) or after its program returned normally
         *  (e.g. task.returned(..) refusing the COMMAREA) is a refusal. */
        Object call(Method m, Object service, Object... args) {
            try {
                return m.invoke(service, args);
            } catch (InvocationTargetException e) {
                Throwable cause = e.getCause();
                if ((!started || ended) && !(cause instanceof FacadeRefused)) {
                    throw new FacadeRefused(m.getName() + " of " + program + " threw "
                            + (started ? "after its task ended: " : "before it ran the scenario's task: ") + cause);
                }
                throw cause instanceof RuntimeException r ? r : new IllegalStateException(cause);
            } catch (IllegalAccessException e) {
                throw new IllegalStateException(e);
            }
        }
    }

    /** Whether a facade answered the COMMAREA its task's RETURN passed on: that very object -- or, where the facade
     *  answers its own DTO and the task RETURNed another record (#4449), those bytes read through it (task.returned):
     *  a fresh object of the facade's type, laid out as the same bytes. */
    static boolean answered(Object got, CicsTask task, Class<?> type) {
        Object raw = task.returned(Object.class);
        if (got == raw) {
            return true;
        }
        if (raw == null || got == null || type.isInstance(raw) || got.getClass() != type) {
            return false;
        }
        try {
            Method bytes = type.getMethod("toCommarea");
            return java.util.Arrays.equals((byte[]) bytes.invoke(got), (byte[]) bytes.invoke(task.returned(type)));
        } catch (ReflectiveOperationException | RuntimeException e) {
            return false;
        }
    }

    static Object area(CicsTask task) {
        return task.hasCommarea() ? task.commarea(Object.class) : null;
    }

    /** The service's public method `name` taking `params` parameters (the deployed bean: a proxy's too), or null. */
    static Method method(Object service, String name, int params) {
        for (Method m : service.getClass().getMethods()) {
            if (m.getName().equals(name) && m.getParameterCount() == params) {
                return m;
            }
        }
        return null;
    }
"""


def _svc_var(program: str) -> str:
    """The test's field for a program's service (a LINK target the case runs)."""
    import equivalence_java as ej

    s = ej._service_class(program)
    return "linked" + s


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
    # The estate has the CICS exception package only when some program throws or handles one (UowForge): IBM DBB
    # MortgageApplication's do not, so nothing there can throw CicsAbendException and the test catches none.
    has_abend = any(src.rglob("exception/CicsAbendException.java"))
    abend_import = f"import {pkg}.exception.CicsAbendException;\n" if has_abend else ""
    by_base = {f["base"]: f for f in files}
    region = case.get("region") or {}
    region_java = f'"{region["applid"]}", "{region["sysid"]}"' if region.get("applid") else "null, null"
    csd_java = ""
    if tdqueues is not None:  # the CSD's transient-data queues: a WRITEQ TD to any other is QIDERR
        names = ", ".join(f'"{q}"' for q in tdqueues)
        csd_java += f"            task.withTdQueues(java.util.Set.of({names}));\n"
    extras = [x["program"].upper() for x in case.get("programs", [])]
    runs = "".join(
        f'                    if ("{p}".equals(program)) {{ if (facades) {{ region.enter("{p}", t, {_svc_var(p)}); }} '
        f"else {{ {_svc_var(p)}.runTask(t); }} return; }}\n"
        for p in extras
    )  # the case's other programs (a LINK's target), each through its service (#4449: java-facade: its handleLink)
    if programs is not None or extras:  # the CSD's programs: an XCTL / LINK / INQUIRE of any other is PGMIDERR
        defined = (f"java.util.Set.of({', '.join(f'{chr(34)}{p}{chr(34)}' for p in programs)}).contains(program)"
                   if programs is not None else "true")  # fmt: skip
        csd_java += (f"            task.withPrograms(new CicsTask.Programs() {{\n"
                     f"                public boolean defined(String program) {{ return {defined}; }}\n"
                     f"                public void run(String program, CicsTask t) {{\n"
                     f"{runs}"
                     f'                    throw new NotRun(program);  // #4173: the task ends here (NOPROGRAM)\n'
                     f"                }}\n"
                     f"            }});")  # fmt: skip
    fields, loads, dumps = [], [], []
    for dsn, spec in case.get("datasets", {}).items():
        if by_base[dsn].get("organization") == "ESDS":  # #4213: the region's ESDS, on the task (CicsTask.withEsds)
            f = by_base[dsn]
            csd_java += f'            task.withEsds("{f["file"]}", {f["reclen"]}, records("{dsn}", {f["reclen"]}));\n'
            dumps.append(f'            dump(sc.get("name").asText() + ".{dsn}.out", task.esdsRecords("{f["file"]}"));')
            continue
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
    # #4507: the task's statements logged as Db2 answered them (EquivalenceDb2Config), the reset and dumps not
    db2_reset = ('            db2Reset();\n            System.setProperty("gitgalaxy.db2.sqllog", '
                 'out.resolve(sc.get("name").asText() + ".sqlout").toString());') if db2 else ""  # fmt: skip
    db2_dump = ('            System.clearProperty("gitgalaxy.db2.sqllog");\n'
                '            db2Dump(sc.get("name").asText());') if db2 else ""  # fmt: skip
    db2_methods = DB2_JAVA if db2 else ""
    # a Db2 case: the task's SQL is one Db2 unit of work (one connection, as the task's Db2 thread under CICS):
    # committed when the task ends, rolled back with its files by SYNCPOINT ROLLBACK or an abend
    db2_begin = ("new org.springframework.transaction.support.TransactionTemplate(new org.springframework.jdbc."
                 "datasource.DataSourceTransactionManager(db2Jdbc.getJdbcTemplate().getDataSource()))"
                 ".executeWithoutResult(db2Status -> {\n            ") if db2 else ""  # fmt: skip
    db2_rollback = "db2Status.setRollbackOnly(); " if db2 else ""
    abend_catch = (" catch (CicsAbendException e) {\n                    status.setRollbackOnly();\n"
                   f"                    {db2_rollback}task.abend(e.getAbcode());\n                }}")  # fmt: skip
    abend_catch = abend_catch if has_abend else ""
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
{abend_import}import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;
import java.util.function.Consumer;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
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
    // #4449: java-facade -- each task entered through the program's deployed entry point (FacadeRegion)
    final boolean facades = Boolean.getBoolean("equivalence.facades");

    @Autowired {pkg}.service.{svc} {var};
{"".join(f"    @Autowired {pkg}.service.{ej._service_class(p)} {_svc_var(p)};{chr(10)}" for p in extras)}
{chr(10).join(fields)}

    @Autowired org.springframework.transaction.PlatformTransactionManager transactions;

    /** #4173: a LINK to a program the case does not run ends the task there, as the COBOL side's stub does
     *  (NOPROGRAM) -- only a derived SQL-fault task reaches one; it is judged up to that LINK. */
    static final class NotRun extends RuntimeException {{
        NotRun(String program) {{
            super("the case does not run " + program);
        }}
    }}

    /** #4173: the task's SQL fault plan, through the det runtime's DetSql (its statements' executions counted
     *  afresh): false when a fault is planned and the port has no DetSql to take it (the task is then not run). */
    static boolean sqlFaultPlan(List<String> plan, Path log) {{
        try {{
            Class.forName("{pkg}.cobolrt.sql.DetSql").getMethod("withFaults", List.class, Path.class)
                    .invoke(null, plan, log);
            return true;
        }} catch (ClassNotFoundException e) {{
            return plan.isEmpty();
        }} catch (ReflectiveOperationException e) {{
            throw new IllegalStateException(e);
        }}
    }}

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
                    .withRegion({region_java})  // ASSIGN APPLID / SYSID
                    .withProgram("{case["program"]}")  // the task's first program (a LINK's INVOKINGPROG)
                    .withCounters(counters(sc))  // GET COUNTER: the region's named counters
                    // RECOVERY(NONE) files: their changes made outside the unit of work, so they survive a backout
                    .withNonRecoverable(java.util.Set.of({", ".join(f'"{x}"' for x in non_recoverable_files(case, files))}),
                            change -> {{
                                org.springframework.transaction.support.TransactionTemplate t =
                                        new org.springframework.transaction.support.TransactionTemplate(transactions);
                                t.setPropagationBehavior(org.springframework.transaction.TransactionDefinition.PROPAGATION_REQUIRES_NEW);
                                t.executeWithoutResult(s -> change.run());
                            }});
            FacadeRegion region = new FacadeRegion(task, commarea, "{case["program"]}", {"true" if case.get("linked") else "false"});
{csd_java}
            List<String> faults = new ArrayList<>();  // #4023 follow-up: the scenario's injected conditions
            sc.path("faults").forEach(f -> faults.add(f.asText()));
            if (!faults.isEmpty()) {{
                task.withFaults(faults, out.resolve(sc.get("name").asText() + ".faults"));
            }}
            List<String> sqlFaults = new ArrayList<>();  // #4173: the scenario's SQL faults (every task starts afresh)
            sc.path("sql_faults").forEach(f -> sqlFaults.add(f.asText()));
            if (!sc.path("sql_unjudged").asText("").isEmpty()) {{  // a faulted statement's program has no seam
                Files.writeString(out.resolve(sc.get("name").asText() + ".hole"), sc.get("sql_unjudged").asText());
                continue;  // not judged: recorded, never run unfaulted
            }}
            if (!sqlFaultPlan(sqlFaults, out.resolve(sc.get("name").asText() + ".faults"))) {{
                Files.writeString(out.resolve(sc.get("name").asText() + ".hole"),
                        "this port has no SQL fault hook (cobolrt.sql.DetSql)");
                continue;  // not judged: recorded, never run unfaulted
            }}
            // one unit of work: a SYNCPOINT ROLLBACK, or an abend that ends the task, backs its changes out
            {db2_begin}new org.springframework.transaction.support.TransactionTemplate(transactions).executeWithoutResult(status -> {{
                task.onRollback(() -> {{ status.setRollbackOnly(); {db2_rollback}}});
                try {{
                    if (facades) {{
                        try (CicsTask.Joined joined = CicsTask.join(region)) {{
                            region.start({var});
                        }}
                    }} else {{
                        {var}.runTask(task);
                    }}
                }} catch (NotRun e) {{
                    // #4173: the LINKed program is not run here; the task's events end at its LINK
                }}{abend_catch} catch (FacadeRefused e) {{
                    region.refused = e.getMessage();  // #4449: the facade did not run the scenario's task as deployed
                    status.setRollbackOnly();  // what it threw would end the unit of work
                    {db2_rollback}
                }} catch (RuntimeException e) {{
                    // #4173: a derived SQL-fault task that reaches a det port's named hole (an untranslated
                    // statement) is not judged -- recorded, never passed; any other failure stays a failure
                    if (!sc.path("derived").asBoolean() || !"Hole".equals(e.getClass().getSimpleName())) {{
                        throw e;
                    }}
                    try {{
                        Files.writeString(out.resolve(sc.get("name").asText() + ".hole"), String.valueOf(e.getMessage()));
                    }} catch (IOException io) {{
                        throw new java.io.UncheckedIOException(io);
                    }}
                    status.setRollbackOnly();
                    {db2_rollback}
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
            if (facades) {{  // #4449: the entry points the task ran by, and a facade's refusal
                json.writeValue(out.resolve(sc.get("name").asText() + ".entries.json").toFile(), region.entries);
                if (region.refused != null) {{
                    Files.writeString(out.resolve(sc.get("name").asText() + ".refused"), region.refused);
                }}
            }}
        }}
    }}

{db2_methods}
{FACADE_JAVA}
    static java.util.Map<String, Long> counters(JsonNode sc) {{
        java.util.Map<String, Long> out = new java.util.HashMap<>();
        sc.path("counters").fields().forEachRemaining(e -> out.put(e.getKey(), e.getValue().asLong()));
        return out;
    }}

    void dump(String name, List<byte[]> records) throws IOException {{
        try (var o = Files.newOutputStream(out.resolve(name))) {{
            for (byte[] r : records) {{
                o.write(r);
            }}
        }}
    }}

    /** #4213: a dataset's records, as loaded, each `reclen` bytes (an ESDS: in arrival order). */
    List<byte[]> records(String dd, int reclen) throws IOException {{
        byte[] data = Files.readAllBytes(in.resolve(dd + ".in"));
        List<byte[]> rows = new ArrayList<>();
        for (int i = 0; i + reclen <= data.length; i += reclen) {{
            rows.add(java.util.Arrays.copyOfRange(data, i, i + reclen));
        }}
        return rows;
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


def sql_seam_programs(case: dict[str, Any], src: Path) -> set[str]:
    """#4173 x #4188: the task's programs whose Java can take an injected SQL fault -- those that reach Db2
    through cobolrt's DetSql (det ports). A model port reaches Db2 its own way and has no seam, even when a
    det-ported program it LINKs to puts DetSql on the classpath."""
    import equivalence_java as ej

    out = set()
    for prog in [case["program"], *[str(p.get("program", "")) for p in case.get("programs") or []]]:
        if not prog:
            continue
        hits = list(src.rglob(f"{ej._service_class(prog)}.java"))
        if any(b"DetSql." in h.read_bytes() for h in hits):
            out.add(prog.upper())
    return out


def sql_unjudged(plan: list[str], seams: set[str]) -> str:
    """The reason a scenario's SQL faults cannot be injected on the Java side ("" when they can): every fault
    names its statement's program (`PROGRAM LINE NTH SQLCODE SQLSTATE`), and that program's Java needs the seam."""
    missing = sorted({line.split()[0] for line in plan if line.split() and line.split()[0] not in seams})
    if not missing:
        return ""
    return f"no SQL fault hook in {', '.join(missing)} (its Java does not reach Db2 through cobolrt.sql.DetSql)"


def run_java_cics(case: dict[str, Any], corpus: Path, work: Path, cobol_work: Path, files: list[dict[str, Any]],
                  port: bool = True, port_dir: Path | None = None,
                  facade: Optional[dict[str, Any]] = None) -> dict[str, list[dict[str, Any]]]:  # fmt: skip
    """The generated project runs every scenario as a CicsTask; {scenario: its events}, each
    COMMAREA mapped back to COBOL field names through the DTO's own comments.

    #4449: with `facade` (a dict to fill) the same project runs every scenario once more, the java-facade side: the
    task entered through the program's deployed entry point (handleTransaction, or handleLink for a LINKed program;
    a LINK target the case runs through its handleLink) with the scenario's region joined. `facade` gets `events`
    ({scenario: events}, as above), `entries` ({scenario: [{program, method}]}), `refused` ({scenario: why}) and
    `out` (the run's output directory); or `error` when that run itself fails."""
    import json

    import equivalence_java as ej

    project = ej.prepare_project(case, corpus, work, "", port, port_dir)
    src = project / "src/main/java"
    svc = ej._service_class(case["program"])
    svc_file = next(src.rglob(f"{svc}.java"))
    ca_cls = commarea_class(case, src, svc_file)
    shape = dto_shape(src, ca_cls, svc_file)  # #4011: the class the service imports, not any of that name
    seams = sql_seam_programs(case, src)  # #4173 x #4188: whose Java can take an injected SQL fault
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
                          "commarea": ca, "receive": receive, "faults": fault_lines(sc), "sql_faults": sc.get("sql_plan", []),
                          "sql_unjudged": sql_unjudged(sc.get("sql_plan", []), seams),
                          "derived": bool(sc.get("derived")),
                          "counters": _counters(case, sc)})  # fmt: skip
    (inputs / "scenarios.json").write_text(json.dumps(scenarios, indent=1), encoding="utf-8")
    props = ej.data_charset_arg(case)
    if case.get("db2"):  # the seed and the dump queries, and the harness's Db2
        (inputs / "db2reset.sql").write_text(equivalence_db2.reset_script(case, corpus), encoding="latin-1")
        (inputs / "db2dumps.txt").write_text("".join(
            f"{t}\t{'|'.join(n)}\t{equivalence_db2.dump_query(t, n)}\n"
            for t, n in ((t, equivalence_db2.columns(t)) for t in case["db2"].get("compare", []))), encoding="latin-1")  # fmt: skip
        props = f"{props} {equivalence_db2.java_props(case)}"
    out = ej.run_maven(project, work, inputs, props=props)
    result = _java_events(case, out, shape)
    if facade is not None:  # #4449: the java-facade side, the same project and inputs
        try:
            fout = ej.run_maven(project, work / "facade", inputs, props=f"{props} -Dequivalence.facades=true")
        except RuntimeError as e:
            facade["error"] = str(e)
            return result
        facade["out"] = fout
        facade["events"] = _java_events(case, fout, shape)
        facade["entries"], facade["refused"] = {}, {}
        for sc in case["scenarios"]:
            ent, why = fout / f"{sc['name']}.entries.json", fout / f"{sc['name']}.refused"
            facade["entries"][sc["name"]] = json.loads(ent.read_text(encoding="utf-8")) if ent.is_file() else []
            if why.is_file():
                facade["refused"][sc["name"]] = why.read_text(encoding="utf-8")
    return result


def _java_events(case: dict[str, Any], out: Path, shape: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """{scenario: the events the Java run wrote to out/<scenario>.json}, each COMMAREA by COBOL field names."""
    import json

    result = {}
    for sc in case["scenarios"]:
        f = out / f"{sc['name']}.json"
        events = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
        for e in events:
            if e.get("event") == "LINK":  # #4173: the target's DTO as issued, before it is mapped to this program's
                e["link_area"] = e.get("commarea")
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
            if f.get("organization") == "ESDS":  # #4213: an ESDS's order is its records' RBAs: data, kept
                return data
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


# A case's "clock_fields" ({"db2": ["SCHEMA.TABLE.COLUMN"], "commarea": ["CA-LASTCHANGED"]}): values the program takes
# from the system clock (Db2's CURRENT TIMESTAMP: GenApp's LGUPDB01). The two runs happen at different moments, so
# such a value is compared as what it is -- a timestamp the run wrote (well formed, within the last day) -- not by
# its digits; a value from the seed or the scenario is still compared exactly. Every masked value is counted.
_CLOCK = re.compile(r"\d{4}-\d\d-\d\d-\d\d\.\d\d\.\d\d\.\d{6}")


def _from_clock(value: str) -> bool:
    import datetime

    v = value.strip()
    if not _CLOCK.fullmatch(v):
        return False
    when = datetime.datetime.strptime(v, "%Y-%m-%d-%H.%M.%S.%f")
    return abs((datetime.datetime.now() - when).total_seconds()) < 86400


def mask_clock_dump(case: dict[str, Any], table: str, dump: bytes, counter: list[int]) -> bytes:
    """A table dump with its clock columns' run-written values replaced by <clock>."""
    cols = {c.rsplit(".", 1)[1].upper() for c in (case.get("clock_fields") or {}).get("db2", [])
            if c.rsplit(".", 1)[0].upper() == table.upper()}  # fmt: skip
    if not cols or not dump:
        return dump
    lines = dump.decode("latin-1").split("\n")
    names = lines[0].split("|")
    at = [i for i, n in enumerate(names) if n.upper() in cols]
    for k in range(1, len(lines)):
        vals = lines[k].split("|")
        for i in at:
            if i < len(vals) and _from_clock(vals[i].strip("[]")):
                vals[i] = "[<clock>]"
                counter[0] += 1
        lines[k] = "|".join(vals)
    return "\n".join(lines).encode("latin-1")


def mask_absent_commarea(sc: dict[str, Any], cev: list[dict[str, Any]], jev: list[dict[str, Any]],
                         counter: list[int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:  # fmt: skip
    """A task that starts with no COMMAREA (EIBCALEN 0) but MOVEs DFHCOMMAREA anyway (IBM DBB EPSCMORT does, before
    it tests EIBCALEN) copies storage it was never given -- on z/OS, undefined (oracle_assumptions.md X12). The
    harness gives LOW-VALUES there, which a numeric field holds only if nothing set it (a MOVE leaves digits, never
    X'00'); the Java DTO's number cannot be invalid. Such a field -- COBOL's value all LOW-VALUES in a COMMAREA the
    task returns, in a scenario with no COMMAREA -- is undefined, so it is left out on both sides and counted."""
    if sc.get("commarea") is not None:
        return cev, jev
    undefined = set()
    for e in cev:
        ca = e.get("commarea")
        if isinstance(ca, dict):
            undefined |= {k for k, v in ca.items() if isinstance(v, str) and re.fullmatch(r"<invalid b'(\\x00)+'>", v)}
    if not undefined:
        return cev, jev

    def drop(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for e in events:
            ca = e.get("commarea")
            if isinstance(ca, dict) and undefined & set(ca):
                e = {**e, "commarea": {k: v for k, v in ca.items() if k not in undefined}}
            out.append(e)
        return out

    counter[0] += len(undefined)
    return drop(cev), drop(jev)


def mask_clock_events(case: dict[str, Any], events: list[dict[str, Any]], counter: list[int]) -> list[dict[str, Any]]:
    """Events with the clock COMMAREA fields' run-written values replaced by <clock>."""
    fields = []  # (name, start, length): a field, or a slice of one (`CA-REQUEST-SPECIFIC(31:26)`, 1-based)
    for f in (case.get("clock_fields") or {}).get("commarea", []):
        m = re.fullmatch(r"([A-Z0-9-]+)\((\d+):(\d+)\)", f.upper())
        fields.append((m.group(1), int(m.group(2)) - 1, int(m.group(3))) if m else (f.upper(), None, None))
    if not fields:
        return events
    out = []
    for e in events:
        ca = e.get("commarea")
        if isinstance(ca, dict):
            ca = dict(ca)
            for name, start, length in fields:
                v = ca.get(name)
                if not isinstance(v, str):
                    continue
                if start is None and _from_clock(v):
                    ca[name] = "<clock>"
                    counter[0] += 1
                elif start is not None and _from_clock(v[start : start + length]):
                    ca[name] = v[:start] + "<clock>".ljust(length) + v[start + length :]
                    counter[0] += 1
            e = {**e, "commarea": ca}
        out.append(e)
    return out


def compare_db2(case: dict[str, Any], cobol: dict[str, bytes], java_out: Path, scenario: str,
                counter: list[int] | None = None) -> dict[str, Any]:  # fmt: skip
    """A Db2 case: per compared table, what the task left there on each side -- only the tables that differ."""

    out = {}
    counter = counter if counter is not None else [0]
    for t in (case.get("db2") or {}).get("compare", []):
        right = java_out / f"{scenario}.DB2_{t}.out"
        left_b = mask_clock_dump(case, t, cobol.get(t, b""), counter)
        right_b = mask_clock_dump(case, t, right.read_bytes() if right.is_file() else b"", counter)
        d = equivalence_db2.diff_dump(left_b, right_b)
        if d["diffs"]:
            out[f"DB2 {t}"] = d
    return out


def compare_sql(case: dict[str, Any], sc: dict[str, Any], res: dict[str, Any], java_out: Path) -> dict[str, Any] | None:
    """#4507: a case with "compare_sql" (its db2 section): the statements each side ran and what Db2 answered them
    (equivalence_db2.compare_outcomes), or None -- not asked, or a task judged only up to a LINK or run with planned
    SQL faults (the injected answers are compared as fired faults)."""
    if not (case.get("db2") or {}).get("compare_sql") or sc.get("prefix_link") or sc.get("sql_plan"):
        return None
    jfile = java_out / f"{sc['name']}.sqlout"
    java = equivalence_db2.java_outcomes(jfile.read_text(encoding="latin-1") if jfile.is_file() else "")
    return equivalence_db2.compare_outcomes(equivalence_db2.cobol_outcomes(res.get("sql", "")), java)


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
            lvl = re.search(r"\blevel=(\d+)", args)
            if lvl and int(lvl.group(1)) > 1:  # a LINKed program's RETURN: back to its caller, no COMMAREA of its own
                out.append({"event": "RETURN", "transid": None, "commarea": None})
            else:
                out.append({"event": "RETURN", "transid": res["return"]["transid"] or None,
                            "commarea": res["return"]["commarea"]})  # fmt: skip
        elif verb == "XCTL":
            out.append({"event": "XCTL", "program": res["xctl"]["program"], "commarea": res["xctl"]["commarea"]})
        elif verb == "LINK":  # a LINK the case runs (its "programs"): compared by its target (what the target did is
            # compared through its own events, the files, tables and the COMMAREA it leaves)
            out.append({"event": "LINK", "program": re.search(r"\btarget=(\S*)", args).group(1)})
        elif verb == "ABEND":
            m = re.search(r"\babcode=(\S*)", args)
            out.append({"event": "ABEND", "abcode": m.group(1) if m else ""})
    if res.get("linked_commarea") is not None:
        out.append({"event": "COMMAREA", "commarea": res["linked_commarea"]})
    return out


def _link_as_compared(e: dict[str, Any]) -> dict[str, Any]:
    """A LINK event as both sides compare it: its target (the Java side's also carries its COMMAREA and RESP)."""
    if e.get("event") == "LINK":
        return {"event": "LINK", "program": e.get("program") or e.get("target")}
    return e


def linked_result(case: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A LINKed program's events (`"linked": true` in the case): its result is the COMMAREA it leaves in its caller's
    storage, compared as a last COMMAREA event -- unless the task abended (no caller sees it then). Any other
    program's final COMMAREA storage is not observable (a terminal task's RETURN COMMAREA is), so it is dropped."""
    keep = case.get("linked") and not any(e.get("event") == "ABEND" for e in events)
    return [_link_as_compared(e) for e in events if e.get("event") != "COMMAREA" or keep]


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
             ]  # fmt: skip
    gen = report.get("db2_generated")
    if gen:  # #4507
        lines += ["Db2 rows generated from the tables' declarations (equivalence_db2.generate_rows): "
                  + ", ".join(f"{t} {n}" for t, n in gen.items()), ""]  # fmt: skip
    if any(
        "sql" in d for d in report["outputs"].values()
    ):  # #4507: what Db2 answered each side, statement by statement
        lines += [
            "| scenario | events equal | total | SQL statements answered alike | total |",
            "|---|---|---|---|---|",
        ]
        for name, d in report["outputs"].items():
            q = d.get("sql") or {}
            lines.append(
                f"| {name} | {d['equal']} | {d['records']} | {q.get('equal', '-')} | {q.get('statements', '-')} |"
            )
    else:
        lines += ["| scenario | events equal | total |", "|---|---|---|"]
        for name, d in report["outputs"].items():
            lines.append(f"| {name} | {d['equal']} | {d['records']} |")
    fc = report.get("facade")
    if fc is not None:  # #4449
        lines += ["", "## Through the deployed entry points (java-facade, #4449)", "",
                  "Every scenario once more, entered through the program's Spring facade with the scenario's task "
                  "handed to it through the joined region.", ""]  # fmt: skip
        if fc.get("error"):
            lines += ["The java-facade run failed:", "", "```", fc["error"][-3000:], "```"]
        else:
            lines += ["| scenario | events equal | total | entered by | verdict |", "|---|---|---|---|---|"]
            for name, d in fc["outputs"].items():
                by = ", ".join(f"{e['program']}.{e['method']}" for e in d.get("entries", []))
                verdict = "pass" if d["pass"] else ("refused: " + d["refused"] if d.get("refused") else "differs")
                lines.append(f"| {name} | {d['equal']} | {d['records']} | {by} | {verdict} |")
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
        files = {n: f for n, f in (o or {}).get("files", {}).items() if f["equal"] != f["records"]}
        sql = (o or {}).get("sql") or {}
        sql_bad = sql.get("equal") != sql.get("statements")
        if o is None or (o["equal"] == o["records"] and not bad_fired and not files and not sql_bad):
            continue
        out += [f"### Scenario {sc['name']}: {o['equal']}/{o['records']} events equal", "",
                f"Key {sc.get('aid', 'DFHENTER')}; COMMAREA {json.dumps(sc.get('commarea'))}; "
                f"screen input {json.dumps(sc.get('receive'))}"
                + (f"; injected {json.dumps(sc['faults'])}" if sc.get("faults") else ""), ""]  # fmt: skip
        if bad_fired:
            out += [f"Injected conditions fired: COBOL {fired and fired['cobol']}, Java {fired and fired['java']}", ""]
        # a file or Db2 table the scenario left different (a LINKed program's writes too), not only its events
        for name, f in files.items():
            out.append(f"- {name}: {f['equal']}/{f['records']} records equal")
            for d in f.get("diffs", [])[:limit]:
                if "missing" in d:
                    out.append(f"  - record {d['record']}: missing on the {d['missing']} side")
                for fd in d.get("fields", [])[:10]:
                    out.append(f"  - record {d['record']} {fd['field']}: COBOL `{fd['cobol']}`, Java `{fd['java']}`")
        if sql_bad:  # #4507: what Db2 answered the two sides' statements
            out.append(f"- SQL: {sql['equal']}/{sql['statements']} statements answered alike")
            for d in sql["diffs"][:limit]:
                if "missing" in d:
                    out.append(f"  - statement {d['statement']}: missing on the {d['missing']} side "
                               f"(COBOL `{d['cobol']}`, Java `{d['java']}`)")  # fmt: skip
                for fd in d.get("fields", []):
                    out.append(
                        f"  - statement {d['statement']} {fd['field']}: COBOL `{fd['cobol']}`, Java `{fd['java']}`"
                    )
        for x in o["diffs"][:limit]:
            if "fields" not in x:
                out.append(f"- event {x['event']}: COBOL `{x.get('cobol')}`, Java `{x.get('java')}`")
            for fd in x.get("fields", [])[:10]:
                out.append(
                    f"- event {x['event']} ({x.get('kind')}) {fd['field']}: COBOL `{fd['cobol']}`, Java `{fd['java']}`"
                )
        out.append("")
    fc = report.get("facade") or {}
    if fc.get("error"):  # #4449: the java-facade side
        out += ["### Through the deployed entry point (java-facade): the run failed", "", fc["error"][-1500:], ""]
    for name, o in (fc.get("outputs") or {}).items():
        if o.get("pass"):
            continue
        out += [f"### Scenario {name}, through the deployed entry point (java-facade): {o['equal']}/{o['records']} "
                "events equal", ""]  # fmt: skip
        if o.get("refused"):
            out.append(f"- the facade refused: {o['refused']}")
        for x in o["diffs"][:limit]:
            if "fields" not in x:
                out.append(f"- event {x['event']}: COBOL `{x.get('cobol')}`, Java `{x.get('java')}`")
            for fd in x.get("fields", [])[:10]:
                out.append(f"- event {x['event']} ({x.get('kind')}) {fd['field']}: COBOL `{fd['cobol']}`, "
                           f"Java `{fd['java']}`")  # fmt: skip
        for fname, f in (o.get("files") or {}).items():
            out.append(f"- {fname}: {f['equal']}/{f['records']} records equal")
        out.append("")
    return "\n".join(out).strip()


def _link_area(case: dict[str, Any], res: dict[str, Any], java: list[dict[str, Any]], program: str) -> dict[str, Any]:
    """#4173: the COMMAREA a prefix-judged task LINKs to `program`, both sides: the COBOL bytes (as the stub logged
    the LINK, LENGTH bytes) as text in the data's encoding, the Java target DTO's text fields in order, the same
    length. A DTO with a typed (non-text) field is not compared here -- said so, never passed."""
    c = next((x for x in res.get("links", []) if x["target"].strip().upper() == program.upper()), None)
    j = next((e for e in java if e.get("event") == "LINK"
              and str(e.get("target", e.get("program", ""))).strip().upper() == program.upper()), None)  # fmt: skip
    if c is None or j is None:
        return {"equal": False, "why": f"no LINK to {program} on the {'COBOL' if c is None else 'Java'} side"}
    if j.get("area") is not None:  # the port passed the area's bytes (a det port): compared byte for byte
        import base64

        jb = base64.b64decode(j["area"])
        enc = common.data_encoding(case)
        return {"equal": jb == c["data"], "length": len(c["data"]), "compared": "bytes",
                "cobol": common._decode_text(c["data"], enc), "java": common._decode_text(jb, enc)}  # fmt: skip
    dto = j.get("link_area")
    values = list(dto.values()) if isinstance(dto, dict) else []
    if not values or not all(isinstance(v, str) for v in values):
        return {"equal": None, "why": "the target's DTO has typed fields: the area is not compared as text"}
    n = len(c["data"])
    ctext = (common._decode_text(c["data"], common.data_encoding(case)) or "").rstrip(" \x00")
    jtext = "".join(values)[:n].rstrip(" \x00")
    return {"equal": ctext == jtext, "length": n, "cobol": ctext, "java": jtext}


def _to_link(events: list[dict[str, Any]], program: str) -> list[dict[str, Any]]:
    """#4173: the events up to and including the first LINK to `program` (a program the case does not run)."""
    for i, e in enumerate(events):
        if e.get("event") == "LINK" and str(e.get("program", "")).strip().upper() == program.upper():
            return events[: i + 1]
    return events


def _fired(log: Path) -> list[str]:
    return sorted(x for x in log.read_text(encoding="ascii").splitlines() if x.strip()) if log.is_file() else []


FACADE_WHY = ("#4449: the scenario once more through the program's deployed entry point (its Spring facade), the "
              "task the scenario builds handed to it through the joined region")  # fmt: skip


def judge_facade(case: dict[str, Any], corpus: Path, files: list[dict[str, Any]], cobol: dict[str, Any],
                 facade: dict[str, Any], refused: dict[str, str], cobol_work: Path) -> dict[str, Any]:  # fmt: skip
    """#4449: the java-facade side against the same COBOL tasks as the runTask side, compared the same way (events,
    files, tables, injected faults); a facade's refusal (FacadeRegion) fails its scenario. `entry_points`: per
    facade method of the case's program, the passing scenarios that entered by it (report `entries`)."""
    if "error" in facade:
        print(f"{case['program']} java-facade: the run failed -- {facade['error'].splitlines()[0]}")
        return {"proven": False, "error": facade["error"], "outputs": {}, "entry_points": []}
    out: Path = facade["out"]
    outputs: dict[str, Any] = {}
    by_method: dict[str, list[str]] = {}
    ok_all = True
    for name, res in cobol.items():
        if name in refused:
            continue
        sc = next(x for x in case["scenarios"] if x["name"] == name)
        clock = [0]
        cev = mask_clock_events(case, linked_result(case, cobol_events(res)), clock)
        jev = mask_clock_events(case, linked_result(case, facade["events"].get(name, [])), clock)
        if sc.get("prefix_link"):
            cev, jev = _to_link(cev, sc["prefix_link"]), _to_link(jev, sc["prefix_link"])
        cev, jev = mask_absent_commarea(sc, cev, jev, [0])
        d = compare_events(cev, jev)
        o: dict[str, Any] = {"equal": d["equal"], "records": d["events"], "diffs": d["diffs"], "java": jev,
                             "entries": facade["entries"].get(name, [])}  # fmt: skip
        ok = d["equal"] == d["events"]
        why = facade["refused"].get(name)
        if why:
            o["refused"] = why
            ok = False
        if sc.get("prefix_link"):
            area = _link_area(case, res, facade["events"].get(name, []), sc["prefix_link"])
            if area.get("equal") is False:
                o["link_area"] = area
                ok = False
        if sc.get("faults") or sc.get("sql_plan"):
            fired = {"cobol": _fired(cobol_work / "scenarios" / name / "out" / "faults.txt"),
                     "java": _fired(out / f"{name}.faults")}  # fmt: skip
            o["fired"] = fired
            ok &= bool(fired["cobol"]) and fired["cobol"] == fired["java"]
        if not sc.get("prefix_link"):
            changed = compare_files(case, corpus, files, res.get("files", {}), out, name)
            changed.update(compare_db2(case, res.get("db2", {}), out, name, clock))
            if changed:
                o["files"] = changed
                ok = False
        o["pass"] = ok
        ok_all &= ok
        outputs[name] = o
        print(
            f"{case['program']} {name} [java-facade]: {d['equal']}/{d['events']} events equal"
            + (f"; REFUSED: {why}" if why else "")
            + ("" if ok or why or d["equal"] != d["events"] else "; differs")
        )
        if ok:
            for e in o["entries"]:
                if e.get("program") == case["program"] and e.get("method") != "runTask":
                    by_method.setdefault(e["method"], []).append(name)
    return {"proven": ok_all, "outputs": outputs,
            "entry_points": [{"method": m, "why": FACADE_WHY, "scenarios": sorted(sids)}
                             for m, sids in sorted(by_method.items())]}  # fmt: skip


def run_case(case: dict[str, Any], corpus: Path, work: Path, port: bool = True, port_dir: Path | None = None,
             cobol_only: bool = False, sql_faults: str = "auto", facades: bool = False) -> int:  # fmt: skip
    """A CICS case end to end: facts -> stub files, the COBOL tasks, the Java tasks, the report.

    #4449: `facades` (with a port) runs the java-facade side too -- every scenario again, entered through the
    program's deployed entry point -- and the case is proven only when both sides are (report `facade`)."""
    import json

    import equivalence_cache
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    ir = load_galaxy_ir(equivalence_cache.scan_db(corpus, work / "scan"))  # (once per corpus and engine)
    files = stub_files(ir, case["program_source"], case.get("datasets"))
    for extra in case.get("programs", []):  # the programs the task LINKs to use files of their own
        files += [f for f in stub_files(ir, extra["program_source"], case.get("datasets"))
                  if f["file"] not in {x["file"] for x in files}]  # fmt: skip
    case = equivalence_inputs.prepare_cics_case(case, corpus, files)  # #3804: generated files and scenarios
    # #4173: SQL faults -- `auto` adds a task per SQL statement the tasks executed (enumerated_sql_faults), each run
    # on both sides; `declared` runs only the scenarios' own sql_faults; `none` drops those too
    if sql_faults == "none":
        case = {**case, "scenarios": [{**sc, "sql_faults": []} for sc in case["scenarios"]]}
    cobol = run_cobol_cics(case, corpus, work / "cobol", files)
    if case.get("db2") and sql_faults == "auto":
        derived = enumerated_sql_faults(case, work / "cobol")
        if derived:
            case = {**case, "scenarios": [*case["scenarios"], *derived]}
            cobol = run_cobol_cics(case, corpus, work / "cobol", files)
    refused = json.loads((work / "cobol" / "refused.json").read_text(encoding="utf-8"))
    for name, why in refused.items():
        print(f"{case['program']} {name}: not run -- {why}")
    case = {**case, "scenarios": [sc for sc in case["scenarios"] if sc["name"] not in refused]}
    if cobol_only:
        for name, res in cobol.items():
            print(f"{name}: " + "; ".join(res["events"]))
        return 0
    try:
        facade: Optional[dict[str, Any]] = {} if facades and port else None
        java = run_java_cics(case, corpus, work / "java", work / "cobol", files, port, port_dir, facade)
    except RuntimeError as e:  # the port does not compile, or its run fails: the loop's feedback, not a crash
        failed = common.java_failure_report(case, work, str(e))
        (work / "report.json").write_text(json.dumps(failed, indent=2) + "\n", encoding="utf-8")
        print(f"{case['program']}: the Java side failed -- see {work / 'report.json'}")
        return 1
    for sc in [x for x in case["scenarios"] if x.get("derived")]:  # #4173: a fault task that reached a named hole
        hole = work / "java" / "out" / f"{sc['name']}.hole"
        if hole.is_file():
            said = hole.read_text(encoding="utf-8")
            refused[sc["name"]] = (
                said if "no SQL fault hook" in said else f"the port reaches a named hole on this path ({said})"
            )
            print(f"{case['program']} {sc['name']}: not judged -- {refused[sc['name']]}")
    case = {**case, "scenarios": [sc for sc in case["scenarios"] if sc["name"] not in refused]}
    if len(cobol) != len(case["scenarios"]) and str(work / "cobol") in RECOVER:  # coverage of the judged tasks only
        RECOVER[str(work / "cobol")]([sc["name"] for sc in case["scenarios"]])
    cobol = {k: v for k, v in cobol.items() if k not in refused}
    report: dict[str, Any] = {"case": case["name"], "program": case["program"], "kind": "cics", "files": files,
                              "java": "ported" if port else "generated", "outputs": {},
                              "refused": refused}  # fmt: skip
    import equivalence_java as ej

    linked = work / "java" / ej.LINKED_FILE
    if linked.is_file():  # #4188: where each LINKed program's Java came from
        report["linked_programs"] = json.loads(linked.read_text(encoding="utf-8"))
    ok = True
    for name, res in cobol.items():
        clock = [0]  # the clock fields masked in this scenario (a case's "clock_fields")
        cev = mask_clock_events(case, linked_result(case, cobol_events(res)), clock)
        jev = mask_clock_events(case, linked_result(case, java.get(name, [])), clock)
        sc = next(x for x in case["scenarios"] if x["name"] == name)
        if sc.get("prefix_link"):  # #4173: a fault task that LINKs to a program the case does not run -- both
            cev, jev = _to_link(cev, sc["prefix_link"]), _to_link(jev, sc["prefix_link"])  # sides judged up to it
        undefined = [0]  # COMMAREA fields a task with no COMMAREA copied from nowhere (X12)
        cev, jev = mask_absent_commarea(sc, cev, jev, undefined)
        d = compare_events(cev, jev)
        report["outputs"][name] = {"equal": d["equal"], "records": d["events"], "diffs": d["diffs"],
                                   "cobol": cev, "java": jev}  # fmt: skip
        ok &= d["equal"] == d["events"]
        if sc.get("derived"):
            report["outputs"][name]["sql_faults"] = sc["sql_plan"]
        if sc.get("prefix_link"):
            report["outputs"][name]["judged_to"] = (
                f"LINK PROGRAM({sc['prefix_link']}) (not run: its end state is not compared)"
            )
            area = _link_area(case, res, java.get(name, []), sc["prefix_link"])
            report["outputs"][name]["link_area"] = area
            if area.get("equal") is False:
                ok = False
                print(f"{case['program']} {name}: the COMMAREA LINKed to {sc['prefix_link']} differs: {area}")
        # #4023 follow-up (#4173: SQL faults too): the same injected conditions fired on both sides, and at least one
        if sc.get("faults") or sc.get("sql_plan"):
            fired = {"cobol": _fired(work / "cobol" / "scenarios" / name / "out" / "faults.txt"),
                     "java": _fired(work / "java" / "out" / f"{name}.faults")}  # fmt: skip
            report["outputs"][name]["fired"] = fired
            if not fired["cobol"] or fired["cobol"] != fired["java"]:
                ok = False
                print(f"{case['program']} {name}: faults fired differ or none fired: {fired}")
        print(f"{case['program']} {name}: {d['equal']}/{d['events']} events equal")
        for x in d["diffs"][:6]:
            print(f"   event {x['event']}: {x.get('fields', [])[:3] or (x.get('cobol'), x.get('java'))}")
        changed = {} if sc.get("prefix_link") else compare_files(case, corpus, files, res.get("files", {}),
                                                                  work / "java" / "out", name)  # fmt: skip
        if not sc.get("prefix_link"):
            changed.update(compare_db2(case, res.get("db2", {}), work / "java" / "out", name, clock))
        sql = compare_sql(case, sc, res, work / "java" / "out")  # #4507: what Db2 answered each side
        if sql is not None:
            report["outputs"][name]["sql"] = sql
            if sql["equal"] != sql["statements"]:
                ok = False
                print(f"{case['program']} {name}: {sql['equal']}/{sql['statements']} SQL statements answered alike")
        if clock[0]:
            report["outputs"][name]["clock_masked"] = clock[0]
        if undefined[0]:
            report["outputs"][name]["undefined_commarea_fields"] = undefined[0]
        if changed:  # file updates: what the task left in a file differs
            report["outputs"][name]["files"] = changed
            ok = False
            for base, fd in changed.items():
                print(f"{case['program']} {name}: file {base}: {fd['equal']}/{fd['records']} records equal")
    report["proven"] = ok
    if (case.get("db2") or {}).get("seed") == "@generate":  # #4507: the rows each table started every task with
        rows, _ = equivalence_db2.generate_rows(case, corpus)
        report["db2_generated"] = {t: sum(1 for x, _ in rows if x == t) for t in dict.fromkeys(x for x, _ in rows)}
    if facade is not None:  # #4449: proven through runTask AND through the deployed entry points
        report["facade"] = judge_facade(case, corpus, files, cobol, facade, refused, work / "cobol")
        report["proven"] = ok and report["facade"]["proven"]
    report["oracle"] = equivalence_oracle.for_case(case)  # #4309: which GnuCOBOL produced the expected outputs
    report["feedback"] = feedback_md(case, report) if not report["proven"] else ""
    covered = work / "cobol" / "coverage.json"  # #4023
    report["coverage"] = json.loads(covered.read_text(encoding="utf-8")) if covered.is_file() else None
    if report["coverage"] and "error" in report["coverage"]:
        report["coverage"] = None
    (work / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    (work / "report.md").write_text(report_markdown(case, report), encoding="utf-8")
    if report["coverage"]:
        print(f"{case['program']} COBOL coverage: {cov.headline(report['coverage'], len(cobol), ok, 'scenario')}")
    print(f"report: {work / 'report.json'}")
    return 0 if report["proven"] else 1
