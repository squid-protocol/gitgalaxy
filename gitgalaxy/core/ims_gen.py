# ==============================================================================
# GitGalaxy Core: IMS PSB / DBD generation sources and IMS regions (#3477)
#
# PURPOSE:
# #3450 records every DL/I call and the segment it touches, but not WHICH IMS
# database a segment lives in, nor whether the program's PSB lets it touch it.
# Those answers are in the PSB and DBD generation sources -- assembler macro
# members (`.psb` / `.dbd`, scanned as hlasm) -- and in the JCL that runs an IMS
# program (`EXEC PGM=DFSRRC00,PARM='DLI,program,psb'`). One row per statement:
#
#   kind     from                         name        parent    lifted
#   PSBGEN   PSBGEN PSBNAME=              the PSB     -         lang
#   PCB      <label> PCB TYPE=DB|GSAM|TP  the label   -         dbd_name, procopt, pcb_type
#   SENSEG   SENSEG NAME=,PARENT=         segment     parent    procopt (a SENSEG's own)
#   DBD      DBD NAME=,ACCESS=            the DBD     -         access
#   SEGM     SEGM NAME=,PARENT=,BYTES=    segment     parent    bytes
#   FIELD    FIELD NAME=(n,SEQ,U),START=  field       segment   start, bytes, seq
#   LCHILD   LCHILD NAME=(seg,dbd)        segment     segment   dbd_name (the paired DBD)
#   REGION   JCL DFSRRC00 PARM=           program     -         region (DLI/BMP/...), psb_name
#
# Each row also keeps `attributes`, the statement's operand text.
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. A SENSEG or SEGM belongs to the PCB / DBD above
#     it in its file (`owner`). Joining a program to its PSB (REGION, or an EXEC
#     DLI SCHD PSB), a PSB's PCBs to DBDs, and checking each DL/I segment access
#     against the PCB's SENSEGs and PROCOPT is the reader's
#     (GalaxyIR.ims_psbs / ims_databases / ims_access_check).
#   - Assembler continuation: a non-blank column 72 continues the statement on
#     the next line, resuming at column 16. `*` in column 1 is a comment. Bounded
#     per statement.
# ==============================================================================
import re
from typing import Any, Optional

_MACROS = frozenset({"PSBGEN", "PCB", "SENSEG", "DBD", "SEGM", "FIELD", "LCHILD", "DATASET"})
_STMT = re.compile(r"^([A-Z@#$][A-Z0-9@#$]{0,7})?[ \t]+([A-Z]{2,8})(?:[ \t]+(.*))?$", re.I)
_STATEMENT_LIMIT = 4000
_REGION_PARM = re.compile(r"PARM=\(?'?([^')]{0,200})'?\)?", re.I)


def _operands(text: str) -> dict[str, str]:
    """The KEY=value operands of one macro operand field (up to the first blank)."""
    field = text.split(" ", 1)[0]
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(field):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(field[start:i])
            start = i + 1
    parts.append(field[start:])
    keyed = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            keyed[k.strip().upper()] = v.strip()
    return keyed


def _first(value: Optional[str]) -> Optional[str]:
    """`(PAUTSUM0,)` / `((PAUTSUM0,))` / `PAUTSUM0` -> `PAUTSUM0`."""
    if not value:
        return None
    v = value.strip().lstrip("(").split(",")[0].strip("() ")
    return v.upper() or None


def _statements(code_stream: str) -> list[tuple[int, str, str, str]]:
    """(line, label, operation, operands) with column-72 continuations joined."""
    out: list[tuple[int, str, str, str]] = []
    lines = code_stream.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.startswith("*") or raw.startswith(".*"):
            i += 1
            continue
        start = i
        text = raw[:71].rstrip()
        # Continued while column 72 is non-blank; the next line resumes at column 16.
        while len(lines[i]) > 71 and lines[i][71] != " " and i + 1 < len(lines) and len(text) < _STATEMENT_LIMIT:
            i += 1
            text += lines[i][15:71].rstrip()
        i += 1
        m = _STMT.match(text)
        if m:
            out.append((start + 1, (m.group(1) or "").upper(), m.group(2).upper(), (m.group(3) or "").strip()))
    return out


def ims_gen_macros(code_stream: str) -> list[dict[str, Any]]:
    """Every PSBGEN / DBDGEN macro statement of one assembler source."""
    if not code_stream:
        return []
    upper = code_stream.upper()
    if not any(w in upper for w in ("PSBGEN", "DBDGEN", " PCB ", " SEGM ", " SENSEG ")):
        return []
    rows: list[dict[str, Any]] = []
    owner: Optional[str] = None
    segment: Optional[str] = None
    dbd: Optional[str] = None
    for line, label, op, text in _statements(code_stream):
        if op not in _MACROS:
            continue
        keyed = _operands(text)
        row: dict[str, Any] = {
            "kind": op,
            "name": None,
            "parent": None,
            "owner": None,
            "dbd_name": None,
            "procopt": None,
            "pcb_type": None,
            "access": None,
            "bytes": None,
            "start": None,
            "psb_name": None,
            "program": None,
            "attributes": " ".join(text.split()) or None,
            "line": line,
        }
        if op == "PCB":
            owner = label or keyed.get("PCBNAME", "").upper() or f"PCB@{line}"
            row.update(
                name=owner,
                pcb_type=(keyed.get("TYPE") or "").upper() or None,
                dbd_name=(keyed.get("DBDNAME") or keyed.get("NAME") or "").upper() or None,
                procopt=(keyed.get("PROCOPT") or "").upper() or None,
            )
        elif op == "SENSEG":
            row.update(
                name=_first(keyed.get("NAME")),
                parent=_first(keyed.get("PARENT")),
                owner=owner,
                procopt=(keyed.get("PROCOPT") or "").upper() or None,
            )
        elif op == "PSBGEN":
            row.update(name=(keyed.get("PSBNAME") or "").upper() or None)
        elif op == "DBD":
            dbd = (keyed.get("NAME") or "").upper() or None
            row.update(name=dbd, access=_first(keyed.get("ACCESS")))
        elif op == "SEGM":
            segment = _first(keyed.get("NAME"))
            row.update(
                name=segment,
                parent=_first(keyed.get("PARENT")),
                owner=dbd,
                bytes=int(keyed["BYTES"].split(",")[0].strip("()"))
                if keyed.get("BYTES", "").strip("()").split(",")[0].isdigit()
                else None,
            )
        elif op == "FIELD":
            name = keyed.get("NAME") or ""
            row.update(
                name=_first(name),
                parent=segment,
                owner=dbd,
                access="SEQ" if ",SEQ" in name.upper() else None,
                start=int(keyed["START"]) if keyed.get("START", "").isdigit() else None,
                bytes=int(keyed["BYTES"]) if keyed.get("BYTES", "").isdigit() else None,
            )
        elif op == "LCHILD":
            inner = (keyed.get("NAME") or "").strip("()").split(",")
            row.update(
                name=inner[0].strip().upper() or None,
                parent=segment,
                owner=dbd,
                dbd_name=inner[1].strip().upper() if len(inner) > 1 and inner[1].strip() else None,
            )
        elif op == "DATASET":
            row.update(name=(keyed.get("DD1") or "").upper() or None, owner=dbd)
        rows.append(row)
    return rows


def jcl_ims_regions(statements: list[tuple[int, str, str, str]]) -> list[dict[str, Any]]:
    """IMS region steps in a JCL file (`EXEC PGM=DFSRRC00,PARM='DLI,PGM,PSB,...'`),
    from mainframe_boundary._jcl_statements: region type, program and PSB."""
    rows: list[dict[str, Any]] = []
    for line, _name, op, operands in statements:
        if op != "EXEC" or not re.search(r"PGM=DFSRRC00\b", operands, re.I):
            continue
        m = _REGION_PARM.search(operands)
        if not m:
            continue
        parts = [p.strip().upper() for p in m.group(1).split(",")]
        region = parts[0] if parts else None
        program = parts[1] if len(parts) > 1 and parts[1] else None
        psb = parts[2] if len(parts) > 2 and parts[2] else None
        rows.append(
            {
                "kind": "REGION",
                "name": program,
                "parent": None,
                "owner": None,
                "dbd_name": None,
                "procopt": None,
                "pcb_type": None,
                "access": region,
                "bytes": None,
                "start": None,
                "psb_name": psb,
                "program": program,
                "attributes": m.group(0),
                "line": line,
            }
        )
    return rows
