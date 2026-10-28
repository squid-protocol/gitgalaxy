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
from typing import Any

_MACROS = frozenset({"PSBGEN", "PCB", "SENSEG", "DBD", "SEGM", "FIELD", "LCHILD", "DATASET"})
_STMT = re.compile(r"^([.&]?[A-Z@#$][A-Z0-9@#$_.]*)?[ \t]+([A-Z]{2,8})(?:[ \t]+(.*))?$", re.I)
_STATEMENT_LIMIT = 4000
_REGION_PARM = re.compile(r"PARM=\(?'?([^')]{0,200})'?\)?", re.I)


def _operand_prefix(segment: str, quote: str | None, depth: int) -> tuple[str, str | None, int]:
    """The operand prefix of one physical line segment (before any unquoted, top-level remark space)."""
    for i, ch in enumerate(segment):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch in " \t" and depth == 0:
            return segment[:i], quote, depth
    return segment, quote, depth


def _operands(text: str) -> dict[str, str]:
    """The KEY=value operands of one macro operand field (up to the first unquoted, top-level blank)."""
    field, _, _ = _operand_prefix(text, None, 0)
    parts, depth, start = [], 0, 0
    quote: str | None = None
    for i, ch in enumerate(field):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
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


def _first(value: str | None) -> str | None:
    """`(PAUTSUM0,)` / `((PAUTSUM0,))` / `PAUTSUM0` -> `PAUTSUM0`."""
    if not value:
        return None
    v = value.strip().lstrip("(").split(",")[0].strip("() ")
    return v.upper() or None


def _statements(code_stream: str) -> list[tuple[int, str, str, str]]:
    """(line, label, operation, operands) with column-72 continuations joined.

    Per HLASM Language Reference (SC26-4940-05) ch.2 "Continuation lines" (p.15) and
    ch.8 "Alternative formats for a macro instruction" (p.296):
    1. A non-space character in column 72 continues the statement on the next line,
       starting in column 16.
    2. Columns 1-15 of a continuation line must be spaces; if an operand on a
       continuation line begins after column 16 (column 16 is blank) outside a
       continued quoted string, the assembler treats that line and any following
       continuation lines as remarks.
    3. In the alternative macro format, each continued line may carry remarks after
       its trailing comma (separated by one or more spaces); only the operand prefix
       of each continued line is joined into the macro operand list.
    """
    out: list[tuple[int, str, str, str]] = []
    lines = code_stream.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.startswith("*") or raw.startswith(".*"):
            i += 1
            continue
        start = i
        first_body = raw[:71].rstrip()
        m = _STMT.match(first_body)
        if not m:
            while len(lines[i]) > 71 and lines[i][71] != " " and i + 1 < len(lines):
                i += 1
            i += 1
            continue
        label = (m.group(1) or "").upper()
        op = m.group(2).upper()
        first_ops = (m.group(3) or "").strip()
        has_cont = len(lines[i]) > 71 and lines[i][71] != " " and i + 1 < len(lines)
        if not has_cont:
            out.append((start + 1, label, op, first_ops))
            i += 1
            continue
        op_text, quote, depth = _operand_prefix(first_ops, None, 0)
        remark_only = False
        while len(lines[i]) > 71 and lines[i][71] != " " and i + 1 < len(lines) and len(op_text) < _STATEMENT_LIMIT:
            i += 1
            cont = lines[i]
            if remark_only:
                continue
            # Columns 1-15 must be spaces; if column 16 is also blank (outside a continued quote),
            # HLASM takes this line and any following continuation lines as remarks [SC26-4940-05 p.15, p.296].
            if len(cont) <= 15 or cont[:15].strip() or (quote is None and cont[15:16] in ("", " ", "\t")):
                remark_only = True
                continue
            seg = cont[15:71] if quote else cont[15:71].rstrip()
            piece, quote, depth = _operand_prefix(seg, quote, depth)
            op_text += piece
        i += 1
        out.append((start + 1, label, op, op_text))
    return out


def ims_gen_macros(code_stream: str) -> list[dict[str, Any]]:
    """Every PSBGEN / DBDGEN macro statement of one assembler source."""
    if not code_stream:
        return []
    upper = code_stream.upper()
    if not any(w in upper for w in ("PSBGEN", "DBDGEN", " PCB ", " SEGM ", " SENSEG ")):
        return []
    rows: list[dict[str, Any]] = []
    owner: str | None = None
    segment: str | None = None
    dbd: str | None = None
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
