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

import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

import equivalence as eq

STUB = eq.CASES / "cics"

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
    """A CICS command, or option, the harness does not model yet."""


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


def _resp(opts: dict[str, str | None], can_fail: bool) -> list[str]:
    """After a command: the EIB's RESP fields, the program's RESP / RESP2, or -- when it
    tests neither and does not say NOHANDLE -- CICS's default: an unhandled condition abends."""
    lines = ["MOVE GG-RESP TO EIBRESP", "MOVE GG-RESP2 TO EIBRESP2"]
    if opts.get("RESP"):
        lines.append(f"MOVE GG-RESP TO {opts['RESP']}")
    if opts.get("RESP2"):
        lines.append(f"MOVE GG-RESP2 TO {opts['RESP2']}")
    if can_fail and not opts.get("RESP") and "NOHANDLE" not in opts:
        lines += ["IF GG-RESP NOT = 0", "    CALL 'GGCUNHD' USING GG-CICS", "    GOBACK", "END-IF"]
    return lines


def _literal(value: str) -> str | None:
    m = re.fullmatch(r"'([^']*)'|\"([^\"]*)\"", value or "")
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None


def translate_command(body: str) -> list[str]:
    """One EXEC CICS body -> the COBOL statements that replace it."""
    pairs = _options(body)
    if not pairs:
        raise Unsupported("empty EXEC CICS")
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
        return ([name(file, "GG-NAME1")]
                + _call("GGCREAD", [f"BY REFERENCE {ridfld}", f"BY VALUE {keylen}", f"BY REFERENCE {into}",
                                    f"BY VALUE LENGTH OF {into}"])
                + _resp(opts, can_fail=True))  # fmt: skip
    if verb == "RECEIVE" and "MAP" in opts:
        into = opts.get("INTO") or (f"{_literal(opts['MAP'])}I" if _literal(opts["MAP"]) else None)
        if not into:
            raise Unsupported("RECEIVE MAP(data-name) without INTO")
        return ([name(opts["MAP"], "GG-NAME1"), name(opts.get("MAPSET") or opts["MAP"], "GG-NAME2")]
                + _call("GGCRECV", [f"BY REFERENCE {into}", f"BY VALUE LENGTH OF {into}"])
                + _resp(opts, can_fail=True))  # fmt: skip
    if verb == "SEND" and "MAP" in opts:
        lines = [name(opts["MAP"], "GG-NAME1"), name(opts.get("MAPSET") or opts["MAP"], "GG-NAME2")]
        mapflags = [n for n, _v in pairs[1:] if n in ("ERASE", "ERASEAUP", "MAPONLY", "DATAONLY", "CURSOR",
                                                       "FREEKB", "ALARM", "FRSET", "PRINT")]  # fmt: skip
        lines.append(f"MOVE '{' '.join(mapflags)[:40]}' TO GG-FLAGS" if mapflags else "MOVE SPACES TO GG-FLAGS")
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
        entry = "GGCRETN" if verb == "RETURN" else "GGCXCTL"
        return [name(target, "GG-NAME1")] + _call(entry, args) + ["GOBACK"]
    if verb == "ABEND":
        return [name(opts.get("ABCODE"), "GG-NAME1")] + _call("GGCABND", []) + ["GOBACK"]
    if verb == "HANDLE" and len(pairs) > 1 and pairs[1][0] == "ABEND":
        what = " ".join(f"{n} {v}" if v else n for n, v in pairs[2:]) or "RESET"
        return [f"MOVE '{what[:40]}' TO GG-FLAGS"] + _call("GGCHABN", [])
    raise Unsupported(" ".join(n for n, _ in pairs[:2]))


def translate(source: str) -> tuple[str, bool]:
    """A fixed-format CICS program -> (the program the stub runtime runs, whether it takes a
    COMMAREA through LINKAGE). Raises Unsupported naming each command it cannot model."""
    lines = source.splitlines()
    out: list[str] = []
    problems: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        code = line[7:72] if len(line) > 7 else ""
        if len(line) > 6 and line[6] in "*/" or not _EXEC.search(code):
            out.append(line)
            i += 1
            continue
        start = _EXEC.search(code)
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
        body, suffix = body[: end.start()], body[end.end() :]
        if prefix.strip():
            out.append(line[:7] + prefix.rstrip())
        try:
            stmts = translate_command(body)
        except Unsupported as e:
            problems.append(f"line {i + 1}: EXEC CICS {e}")
            stmts = []
        for s in stmts:
            if len(_AREA_B) + len(s) > 72:
                raise Unsupported(f"line {i + 1}: generated statement too long: {s}")
            out.append(_AREA_B + s)
        if suffix.strip():
            out.append(_AREA_B + suffix.strip())
        i = j + 1
    if problems:
        raise Unsupported("; ".join(problems))
    text = "\n".join(_DFHRESP.sub(lambda m: str(DFHRESP[m.group(1).upper()]), ln) for ln in out) + "\n"
    has_commarea = bool(re.search(r"^.{6} +01\s+DFHCOMMAREA\b", text, re.M | re.I))
    text = re.sub(r"^(.{6} +WORKING-STORAGE\s+SECTION\.[^\n]*\n)", r"\1       COPY DFHEIBLK.\n", text,
                  count=1, flags=re.M | re.I)  # fmt: skip
    if "COPY DFHEIBLK" not in text:
        raise Unsupported("no WORKING-STORAGE SECTION to hold the EIB")
    if has_commarea:
        text, n = re.subn(r"^(.{6} +PROCEDURE\s+DIVISION)\s*\.", r"\1 USING DFHCOMMAREA.", text, count=1,
                          flags=re.M | re.I)  # fmt: skip
        if n != 1:
            raise Unsupported("PROCEDURE DIVISION header not found (or already has USING)")
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
              "    CALL 'GGCEND' USING GG-CICS", "    STOP RUN."]  # fmt: skip
    assert all(len(ln) <= 65 for ln in lines), [ln for ln in lines if len(ln) > 65]
    return "".join("       " + ln + "\n" for ln in lines)


# ---- the stub's files, from the engine's facts ----------------------------------------
def stub_files(ir: Any, program_file: str) -> list[dict[str, Any]]:
    """Each CICS file the program uses: {file, dsname, base (the cluster whose records it
    reads), key_offset, key_length, reclen, via}, from the engine's facts -- the CSD
    DEFINE FILE's DSNAME, then the IDCAMS DEFINE that keys it: a CLUSTER's KEYS, or a
    PATH -> its AIX's KEYS over the AIX's base cluster."""
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
        if d is None:
            raise Unsupported(f"CICS file {e['name']}: no IDCAMS DEFINE for {dsn}")
        key = d
        if d.kind == "AIX":
            via.append(f"AIX {d.name}")
            d = defines.get((d.related or "").upper())
            if d is None:
                raise Unsupported(f"CICS file {e['name']}: AIX {key.name} has no base cluster define")
        out.append({"file": e["name"], "dsname": dsn, "base": d.name.upper(), "key_offset": key.key_offset,
                    "key_length": key.key_length, "reclen": d.record_max, "via": via})  # fmt: skip
    return sorted(out, key=lambda f: f["file"])


# ---- field values <-> bytes -----------------------------------------------------------
def encode_field(value: Any, pic: str | None, usage: str | None, nbytes: int) -> bytes:
    """A value as the field stores it (the inverse of equivalence.decode_field)."""
    num = eq._pic_numeric(pic) if pic else None
    if num is None:
        return str(value).encode("latin-1")[:nbytes].ljust(nbytes, b" ")
    signed, digits, scale = num
    n = int((Decimal(str(value)) * (Decimal(10) ** scale)).to_integral_value())
    u = (usage or "DISPLAY").upper()
    if u in ("COMP-3", "PACKED-DECIMAL", "COMPUTATIONAL-3"):
        body = f"{abs(n):0{nbytes * 2 - 1}d}"[-(nbytes * 2 - 1) :]
        return bytes.fromhex(body + ("d" if n < 0 else ("c" if signed else "f")))
    if u in ("COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"):
        return n.to_bytes(nbytes, "big", signed=signed)
    text = f"{abs(n):0{digits}d}"[-digits:]
    if signed:
        last = int(text[-1])
        text = text[:-1] + ("}JKLMNOPQR"[last] if n < 0 else "{ABCDEFGHI"[last])
    return text.encode("latin-1")


def encode_record(fields: list[dict[str, Any]], values: dict[str, Any], fill: bytes) -> bytes:
    """A record from {field name: value}; every field not named is `fill` (for a COMMAREA,
    INITIALIZE's spaces / zeros; for map input, the nulls CICS leaves in an untouched field)."""
    size = max((f["offset"] + f["bytes"] for f in fields), default=0)
    rec = bytearray(size)
    names = {f["name"] for f in fields}
    unknown = sorted(set(values) - names)
    if unknown:
        raise ValueError(f"no such field(s): {', '.join(unknown)}")
    for f in fields:
        sl = slice(f["offset"], f["offset"] + f["bytes"])
        if isinstance(values.get(f["name"]), bytes):  # already the field's bytes
            rec[sl] = values[f["name"]][: f["bytes"]].ljust(f["bytes"], b" ")
        elif f["name"] in values:
            rec[sl] = encode_field(values[f["name"]], f["pic"], f["usage"], f["bytes"])
        elif fill == b"init":
            num = eq._pic_numeric(f["pic"]) if f["pic"] else None
            rec[sl] = encode_field(0 if num else "", f["pic"], f["usage"], f["bytes"])
        else:
            rec[sl] = fill * f["bytes"]
    return bytes(rec)


def decode_record(data: bytes, fields: list[dict[str, Any]]) -> dict[str, str]:
    """{field name: value as text} -- numeric fields as exact decimals, text with trailing
    spaces and nulls dropped (a screen shows neither)."""
    out = {}
    for f in fields:
        raw = data[f["offset"] : f["offset"] + f["bytes"]]
        if len(raw) < f["bytes"]:
            continue
        v = eq.decode_field(raw, f["pic"], f["usage"])
        out[f["name"]] = str(v) if not isinstance(v, str) else v.rstrip(" \x00")
    return out


def map_input(fields: list[dict[str, Any]], values: dict[str, str]) -> bytes:
    """A RECEIVE MAP input area: nulls everywhere, and for each field the user typed in
    ({"ACCTSIDI": "00000000011"}) its data and its length (<name>L)."""
    typed: dict[str, Any] = {}
    for field, text in values.items():
        typed[field] = text.encode("latin-1")  # what was typed, whatever the field's PICIN
        typed[field[:-1] + "L"] = len(text.rstrip())
    return encode_record(fields, typed, b"\x00")


# ---- running a case -------------------------------------------------------------------
def commarea_fields(corpus: Path, case: dict[str, Any]) -> list[dict[str, Any]]:
    """The COMMAREA layout: the case's (copybook, record) segments laid end to end."""
    out, at = [], 0
    for seg in case["commarea"]["segments"]:
        fields = eq.layout_fields(corpus, seg["copybook"], seg["record"])
        out += [dict(f, offset=f["offset"] + at) for f in fields]
        at += max(f["offset"] + f["bytes"] for f in fields)
    return out


def screen_fields(corpus: Path, case: dict[str, Any], map_name: str, side: str) -> list[dict[str, Any]]:
    scr = case["screens"][map_name]
    return eq.layout_fields(corpus, scr["copybook"], scr[side])


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
    text, has_commarea = translate((corpus / case["program_source"]).read_text(encoding="latin-1"))
    (src / "PROGRAM.cbl").write_text(text, encoding="latin-1")
    (src / "EQCICSDR.cbl").write_text(cics_driver(case["program"], has_commarea), encoding="ascii")
    (work / "files.cfg").write_text("".join(
        f"{f['file']} /work/files/{f['base']} {f['reclen']} {f['key_offset']} {f['key_length']}\n" for f in files
    ), encoding="ascii")  # fmt: skip
    (work / "files").mkdir(exist_ok=True)
    for f in files:
        spec = case["datasets"].get(f["base"])
        if spec is None:
            raise Unsupported(f"the case gives no data for {f['base']} (CICS file {f['file']})")
        (work / "files" / f["base"]).write_bytes(eq._fixed(eq._input_path(case, corpus, spec["input"]), f["reclen"]))
    ca_fields = commarea_fields(corpus, case)
    script = ["set -e", "cd /work",
              "cobc -x -std=ibm -fsign=EBCDIC -fstatic-call -I /work/src -o task src/EQCICSDR.cbl "
              "src/PROGRAM.cbl src/ggcics.c"]  # fmt: skip
    date, _, time = case["clock"].partition(" ")
    for sc in case["scenarios"]:
        d = work / "scenarios" / sc["name"]
        (d / "out").mkdir(parents=True, exist_ok=True)
        shutil.copy(work / "files.cfg", d / "files.cfg")
        if sc.get("commarea") is not None:
            (d / "commarea.in").write_bytes(encode_record(ca_fields, sc["commarea"], b"init"))
        for m, typed in (sc.get("receive") or {}).items():
            (d / f"receive_{m}.bin").write_bytes(map_input(screen_fields(corpus, case, m, "input"), typed))
        y, mo, dd = date.split("/")
        eib_date = f"{int(y) - 1900:03d}{_day_of_year(int(y), int(mo), int(dd)):03d}"[-7:].rjust(7, "0")
        eib_time = "0" + time.replace(":", "")[:6]
        (d / "eib.in").write_text(f"{case['transid']:<4} {sc.get('aid', 'DFHENTER'):<8} {eib_date} {eib_time}\n",
                                  encoding="ascii")  # fmt: skip
        rel = f"/work/scenarios/{sc['name']}"
        script.append(f"set +e; GGCICS_DIR={rel} GGCICS_OUT={rel}/out EIBIN={rel}/eib.in "
                      f"COB_CURRENT_DATE='{case['clock']}' ./task > {rel}/stdout.txt 2>&1; "
                      f"echo $? > {rel}/rc; set -e")  # fmt: skip
    (work / "run.sh").write_text("\n".join(script) + "\n", encoding="ascii")
    proc = subprocess.run(  # noqa: S603 -- fixed argv, a local image
        ["docker", "run", "--rm", "-v", f"{work}:/work", eq.IMAGE, "bash", "/work/run.sh"],  # noqa: S607
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"COBOL side failed:\n{proc.stdout}\n{proc.stderr}")
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
            vals = decode_record(data, fields)
            res["screens"].append({"map": kv["map"], "fields": {k[:-1]: v for k, v in vals.items() if k.endswith("O")}})
        elif verb == "SEND-TEXT":
            res["text"].append(data.decode("latin-1").rstrip(" \x00"))
        elif verb in ("RETURN", "XCTL"):
            key = "transid" if verb == "RETURN" else "program"
            res[verb.lower()] = {key: kv.get(key, ""), "commarea": decode_record(data, ca_fields) if data else None}
        elif verb == "ABEND":
            res["abend"] = args
    return res
