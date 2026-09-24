# ==============================================================================
# GitGalaxy Core: file definitions -- FILE-CONTROL clauses and VSAM defines (#3455)
#
# PURPOSE:
# dataset_data (#3201) records that a program's SELECT is ASSIGNed to a DD and
# which OPEN modes it uses. Nothing recorded HOW the file is organised or keyed,
# and nothing recorded the VSAM cluster the DD points at, so a migration could
# not check that a program's RECORD KEY is the cluster's key. Two per-file facts:
#
#   COBOL  one row per FILE-CONTROL `SELECT` (file_control_data):
#          organization  INDEXED | RELATIVE | SEQUENTIAL | LINE SEQUENTIAL (as
#                        written; None when the clause is absent -- COBOL's
#                        default, SEQUENTIAL, is the reader's to apply)
#          access_mode   SEQUENTIAL | RANDOM | DYNAMIC
#          record_key / relative_key / file_status (the data-names)
#          alternate_keys  comma-joined, `+DUP` marking WITH DUPLICATES
#          fd_copies     the COPY members inside the file's FD entry -- where its
#                        record (and so its keys) live when not in the program
#   JCL    one row per IDCAMS DEFINE CLUSTER / ALTERNATEINDEX / PATH in an
#          in-stream SYSIN (vsam_define_data):
#          kind CLUSTER | AIX | PATH, name, organization (INDEXED / NUMBERED /
#          NONINDEXED / LINEAR), key_length / key_offset (KEYS(l o)),
#          record_avg / record_max (RECORDSIZE(a m)), related (an AIX's RELATE
#          base, a PATH's PATHENTRY), unique_key (AIX UNIQUEKEY / NONUNIQUEKEY),
#          upgrade (AIX UPGRADE / NOUPGRADE), step (the EXEC step).
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. Resolving a key data-name to its byte offset and
#     length in the FD record, following the DD to its dataset and on to the
#     cluster, and comparing the two keys is the reader's
#     (GalaxyIR.vsam_files), like every other cross-file join.
#   - DEFINE GENERATIONDATAGROUP is job-flow (#3451), not here. IDCAMS control
#     statements in a separate member (not in-stream) are not read.
#   - Names are kept as written: a symbolic `&HLQ..X` cluster name is not
#     substituted here.
#   - Bounded: FILE-CONTROL is cut at the next division / section; a SELECT at
#     its period; an IDCAMS command at its last continuation line, capped.
# ==============================================================================
import bisect
import re
from typing import Any, Callable, Optional

from gitgalaxy.core.db2_declare_table import _blank_sequence_fields

_FILE_CONTROL = re.compile(r"(?<![A-Z0-9-])FILE-CONTROL[ \t]{0,20}\.", re.I)
_WS = r"[ \t\n]{1,200}"
_FC_END = re.compile(r"(?<![A-Z0-9-])(?:I-O-CONTROL|DATA" + _WS + "DIVISION|PROCEDURE" + _WS + "DIVISION)", re.I)
_SELECT = re.compile(r"(?<![A-Z0-9-])SELECT(?![A-Z0-9-])", re.I)
_TOKEN = re.compile(r"'[^'\n]{0,120}'|\"[^\"\n]{0,120}\"|[A-Z0-9][A-Z0-9-]{0,62}|\.", re.I)
_FC_LIMIT = 200000
_SELECT_LIMIT = 4000
_ORGS = ("INDEXED", "RELATIVE", "SEQUENTIAL")
_NOISE = {"IS", "ARE", "MODE", "KEY", "TO"}


def _select_rows(text: str, line_of: Callable[[int], int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fc in _FILE_CONTROL.finditer(text):
        end = _FC_END.search(text, fc.end())
        region_end = min(end.start() if end else len(text), fc.end() + _FC_LIMIT)
        starts = [m.start() for m in _SELECT.finditer(text, fc.end(), region_end)]
        for i, start in enumerate(starts):
            stop = min(starts[i + 1] if i + 1 < len(starts) else region_end, start + _SELECT_LIMIT)
            toks: list[str] = []
            for t in _TOKEN.finditer(text, start, stop):
                if t.group(0) == ".":
                    break
                toks.append(t.group(0))
            rows.append(_one_select([t.upper() if t[0] not in "'\"" else t for t in toks[1:]], line_of(start)))
    return rows


def _one_select(toks: list[str], line: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "select_name": None,
        "assign": None,
        "organization": None,
        "access_mode": None,
        "record_key": None,
        "alternate_keys": None,
        "relative_key": None,
        "file_status": None,
        "line": line,
    }
    alternates: list[str] = []
    i = 0
    if toks and toks[0] == "OPTIONAL":
        i = 1
    if i < len(toks):
        row["select_name"] = toks[i]
        i += 1

    def after(j: int) -> tuple[Optional[str], int]:
        """The next word after the clause words at j, skipping IS / MODE / KEY / TO."""
        while j < len(toks) and toks[j] in _NOISE:
            j += 1
        return (toks[j] if j < len(toks) else None), j + 1

    while i < len(toks):
        t = toks[i]
        if t == "ASSIGN":
            j = i + 1
            while j < len(toks) and toks[j] in ("TO", "USING"):
                j += 1
            if j < len(toks):
                row["assign"] = toks[j].strip("'\"")
            i = j + 1
        elif t == "ORGANIZATION":
            value, i = after(i + 1)
            if value == "LINE" and i < len(toks) and toks[i] == "SEQUENTIAL":
                value, i = "LINE SEQUENTIAL", i + 1
            row["organization"] = value
        elif t in _ORGS and row["organization"] is None and toks[i - 1] not in ("MODE", "IS", "ACCESS"):
            row["organization"] = t
            i += 1
        elif t == "ACCESS":
            row["access_mode"], i = after(i + 1)
        elif t == "ALTERNATE":
            j = i + 1
            if j < len(toks) and toks[j] == "RECORD":
                j += 1
            name, i = after(j)
            dup = False
            if i < len(toks) and toks[i] == "WITH":
                i += 1
            if i < len(toks) and toks[i] == "DUPLICATES":
                dup, i = True, i + 1
            if name:
                alternates.append(name + ("+DUP" if dup else ""))
        elif t == "RECORD" and (i + 1 < len(toks) and toks[i + 1] in ("KEY", "IS")):
            row["record_key"], i = after(i + 1)
        elif t == "RELATIVE" and (i + 1 < len(toks) and toks[i + 1] in ("KEY", "IS")):
            row["relative_key"], i = after(i + 1)
        elif t == "STATUS":
            row["file_status"], i = after(i + 1)
        else:
            i += 1
    row["alternate_keys"] = ",".join(alternates) or None
    return row


# ---- IDCAMS (JCL in-stream SYSIN) ---------------------------------------------
_IDCAMS_VERBS = re.compile(
    r"^[ \t]*(DEFINE|DEF|DELETE|DEL|LISTCAT|LISTC|REPRO|PRINT|ALTER|VERIFY|IF|SET|EXPORT|IMPORT|BLDINDEX|BIX)(?![A-Z0-9-])",
    re.I,
)
_DEFINE_KINDS = {
    "CLUSTER": "CLUSTER",
    "CL": "CLUSTER",
    "ALTERNATEINDEX": "AIX",
    "AIX": "AIX",
    "PATH": "PATH",
}
_PARAM = re.compile(r"[A-Z][A-Z0-9-]{0,40}", re.I)
_COMMAND_LIMIT = 6000


def _balanced(text: str, open_at: int) -> int:
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def _params(text: str) -> list[tuple[str, Optional[str]]]:
    """Top-level `KEYWORD(value)` / `KEYWORD` pairs of one IDCAMS parameter list."""
    out: list[tuple[str, Optional[str]]] = []
    i = 0
    while i < len(text):
        m = _PARAM.search(text, i)
        if not m:
            break
        j = m.end()
        while j < len(text) and text[j] in " \t\n":
            j += 1
        if j < len(text) and text[j] == "(":
            close = _balanced(text, j)
            out.append((m.group(0).upper(), " ".join(text[j + 1 : close].split())))
            i = close + 1
        else:
            out.append((m.group(0).upper(), None))
            i = m.end()
    return out


def _pair(value: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    nums = re.findall(r"[0-9]{1,9}", value or "")
    return (int(nums[0]) if nums else None), (int(nums[1]) if len(nums) > 1 else None)


def _define_row(kind: str, body: str, step: Optional[str], line: int) -> dict[str, Any]:
    top = _params(body)
    # CLUSTER( ... ) DATA( ... ) INDEX( ... ): the object's own block comes first.
    own = next((v for k, v in top if k in _DEFINE_KINDS and v is not None), None)
    params = dict(_params(own or "")) if own is not None else dict(top)
    org = next((w for w in ("INDEXED", "NUMBERED", "NONINDEXED", "LINEAR") if w in params), None)
    if kind == "CLUSTER" and org is None and ("IXD" in params):
        org = "INDEXED"
    key_len, key_off = _pair(params.get("KEYS"))
    rec_avg, rec_max = _pair(params.get("RECORDSIZE") or params.get("RECSZ"))
    related = params.get("RELATE") or params.get("PATHENTRY") or params.get("PENT")
    unique = (
        "UNIQUE"
        if "UNIQUEKEY" in params or "UNQK" in params
        else ("NONUNIQUE" if "NONUNIQUEKEY" in params or "NUNQK" in params else None)
    )
    upgrade = (
        "UPGRADE"
        if "UPGRADE" in params or "UPG" in params
        else ("NOUPGRADE" if "NOUPGRADE" in params or "NUPG" in params else None)
    )
    return {
        "kind": kind,
        "name": (params.get("NAME") or "").upper() or None,
        "organization": org,
        "key_length": key_len,
        "key_offset": key_off,
        "record_avg": rec_avg,
        "record_max": rec_max,
        "related": related.upper() if related else None,
        "unique_key": unique if kind == "AIX" else None,
        "upgrade": upgrade if kind == "AIX" else None,
        "step": step,
        "line": line,
    }


def jcl_vsam_defines(code_stream: str) -> list[dict[str, Any]]:
    """Every IDCAMS DEFINE CLUSTER / AIX / PATH in a JCL file's in-stream data."""
    if not code_stream or "DEF" not in code_stream.upper():
        return []
    lines = code_stream.split("\n")
    rows: list[dict[str, Any]] = []
    step: Optional[str] = None
    i = 0
    while i < len(lines):
        raw = lines[i]
        if raw.startswith("//"):
            m = re.match(r"^//([A-Z0-9@#$]{1,8})[ \t]+EXEC(?![A-Z0-9])", raw, re.I)
            if m:
                step = m.group(1).upper()
            i += 1
            continue
        head = _IDCAMS_VERBS.match(raw)
        if not head or head.group(1).upper() not in ("DEFINE", "DEF"):
            i += 1
            continue
        start = i
        parts: list[str] = []
        size = 0
        while i < len(lines) and size < _COMMAND_LIMIT:
            body = lines[i][:72].rstrip()
            if i > start and (body.startswith("//") or body.startswith("/*") or _IDCAMS_VERBS.match(body)):
                break
            # IDCAMS comments /* ... */ inside a command are dropped.
            body = re.sub(r"/\*.*?\*/", " ", body)
            cont = body.endswith("-") or body.endswith("+")
            parts.append(body[:-1] if cont else body)
            size += len(body)
            i += 1
            if not cont:
                break
        text = " ".join(parts)
        m = re.match(r"^[ \t]*DEF(?:INE)?[ \t]+([A-Z]+)", text, re.I)
        kind = _DEFINE_KINDS.get(m.group(1).upper()) if m else None
        if kind and m:
            rows.append(_define_row(kind, text[m.end() - len(m.group(1)) :], step, start + 1))
    return rows


_FD = re.compile(r"(?<![A-Z0-9-])[FS]D[ \t\n]{1,200}([A-Z0-9][A-Z0-9-]{0,62})", re.I)
_FD_END = re.compile(
    r"(?<![A-Z0-9-])(?:[FS]D[ \t\n]|WORKING-STORAGE|LOCAL-STORAGE|LINKAGE[ \t\n]{1,200}SECTION|PROCEDURE[ \t\n]{1,200}DIVISION)",
    re.I,
)
_COPY = re.compile(r"(?<![A-Z0-9-])COPY[ \t\n]{1,200}['\"]?([A-Z0-9@#$][A-Z0-9@#$-]{0,30})", re.I)
_FD_LIMIT = 20000


def _fd_copies(text: str) -> dict[str, str]:
    """FD / SD name -> the COPY members inside its entry (its record may be all copybook:
    `FD CUSTOMER-INPUT. COPY CVCUS01Y.`), comma-joined in source order."""
    out: dict[str, str] = {}
    for m in _FD.finditer(text):
        end = _FD_END.search(text, m.end())
        region = text[m.end() : min(end.start() if end else len(text), m.end() + _FD_LIMIT)]
        members = [c.group(1).upper() for c in _COPY.finditer(region)]
        if members:
            out.setdefault(m.group(1).upper(), ",".join(dict.fromkeys(members)))
    return out


def cobol_file_control(code_stream: str) -> list[dict[str, Any]]:
    """Every FILE-CONTROL SELECT of one COBOL file with its organisation, access
    mode and keys (see the module header)."""
    if not code_stream or "FILE-CONTROL" not in code_stream.upper():
        return []
    text = _blank_sequence_fields(code_stream, "cobol")
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    rows = _select_rows(text, lambda off: bisect.bisect_left(newlines, off) + 1)
    copies = _fd_copies(text)
    for r in rows:
        r["fd_copies"] = copies.get((r["select_name"] or "").upper())
    return [r for r in rows if r["select_name"]]
