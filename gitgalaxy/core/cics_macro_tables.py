# ==============================================================================
# GitGalaxy Core: CICS resource macro tables (DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST) (#5120)
#
# PURPOSE:
# Before CEDA / the CSD, a CICS region's resources were assembled into macro
# tables, and a region can still load them (SIT FCT=, PCT=, PPT=, DCT=, TST=).
# The resource facts a CSD deck declares -- FILE -> DSNAME, TRANSACTION -> PROGRAM,
# TDQUEUE -> DDNAME -- are in those tables too, as assembler macro statements. This
# reader lifts them into the SAME row shape `mainframe_boundary._csd_resources`
# produces, so the macro and CSD definitions land in one `csd_resource_data` table
# and merge into one resource map (GalaxyIR.resource_map), conflicts named.
#
# Each row also names its provenance: `source` = "MACRO", `macro_table` (the
# assembled table, `DFHFCT` + its `TYPE=INITIAL,SUFFIX=` suffix, so DFHFCT01) and
# `line` (the macro statement's first line). A CSD row has no `source` key; the
# recorder stores it as "CSD".
#
# MACRO -> RESOURCE (IBM "CICS Resource Definition Guide", macro-table appendix --
# the DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST macro reference):
#
#   DFHFCT TYPE=DATASET|REMOTE  DATASET=     FILE      DSNAME=, RECFORM=, KEYLEN=, RECSIZE=
#   DFHPCT TYPE=ENTRY           TRANSID=     TRANSACTION  PROGRAM=
#   DFHPPT TYPE=ENTRY           PROGRAM=     PROGRAM   (PGMLANG=, RES= ride in `attributes`)
#   DFHDCT TYPE=INTRA|EXTRA|INDIRECT|REMOTE  DESTID=  TDQUEUE  (queue_type)
#          TYPE=SDSCI           DSCNAME=     not a row: its DSNAME / RECFORM / RECSIZE are
#                                            folded into the EXTRA entry naming it by DSCNAME=
#          (an EXTRA entry's `ddname` is its DSCNAME, the SDSCI's DD name)
#   DFHTST TYPE=LOCAL|REMOTE|RECOVERY|SECURITY|ENTRY   DATAID=  TSMODEL (one row per prefix)
#
#   TYPE=INITIAL / TYPE=FINAL / TYPE=GROUP rows are not resources and are skipped.
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. Joining a macro FILE to its JCL dataset, and
#     comparing it with the same resource in a CSD, is the reader's job
#     (GalaxyIR.cics_file_datasets / resource_map / resource_conflicts).
#   - Assembler continuation: a non-blank column 72 continues the statement on the
#     next line, resuming at column 16; `*` in column 1 is a comment. Reused from
#     ims_gen, bounded per statement.
#   - Not read: DFHSIT / DFHSRT / DFHJCT / DFHTCT / DFHMCT tables, and a PPT entry
#     cannot tell a program from a mapset (the PPT holds both), so every PPT entry
#     is a PROGRAM row.
# ==============================================================================
import re
from typing import Any

from gitgalaxy.core.ims_gen import _first, _operands, _statements

_TABLES = ("DFHFCT", "DFHPCT", "DFHPPT", "DFHDCT", "DFHTST")
_GATE = re.compile(r"\bDFH(?:FCT|PCT|PPT|DCT|TST)\b", re.I)
_RECFORM = {"VARIABLE": "V", "FIXED": "F", "UNDEFINED": "U", "V": "V", "F": "F", "U": "U"}
_TST_TYPES = frozenset({"LOCAL", "REMOTE", "RECOVERY", "SECURITY", "ENTRY"})


def _name(value: str | None) -> str | None:
    """A name-valued operand: first element of a list, unquoted, upper-cased, or None."""
    return (_first(value) or "").strip("'\"").upper() or None


def _int(value: str | None) -> int | None:
    value = (value or "").strip().strip("()'\"").split(",")[0].strip()
    return int(value) if value.isdigit() and len(value) <= 9 else None


def _recform(value: str | None) -> str | None:
    """`(VARIABLE,BLOCKED)` / `FIXED` -> V / F / U; an unrecognised word is dropped."""
    return _RECFORM.get((_first(value) or "").strip("'\"").upper())


def _row(resource_type: str, name: str | None, table: str, line: int, text: str, **lifted: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "resource_type": resource_type,
        "name": name,
        "group": None,
        "dsname": None,
        "ddname": None,
        "record_format": None,
        "key_length": None,
        "record_size": None,
        "queue_type": None,
        "plan": None,
        "db2_entry": None,
        "transid": None,
        "program": None,
        "attributes": " ".join(text.split()) or None,
        "line": line,
        "source": "MACRO",
        "macro_table": table,
    }
    row.update(lifted)
    return row


def cics_macro_table_resources(code_stream: str) -> list[dict[str, Any]]:
    """Every resource a DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST macro statement defines."""
    if not code_stream or not _GATE.search(code_stream):
        return []
    statements = [s for s in _statements(code_stream) if s[2] in _TABLES]
    if not statements:
        return []
    # A table's suffix comes from its TYPE=INITIAL (DFHFCT TYPE=INITIAL,SUFFIX=01).
    suffix: dict[str, str] = {}
    sdsci: dict[str, dict[str, str]] = {}
    for _line, _label, op, text in statements:
        keyed = _operands(text)
        kind = (keyed.get("TYPE") or "").upper()
        if kind == "INITIAL" and keyed.get("SUFFIX"):
            suffix.setdefault(op, keyed["SUFFIX"].strip("'\"").upper())
        elif op == "DFHDCT" and kind == "SDSCI" and keyed.get("DSCNAME"):
            sdsci.setdefault(keyed["DSCNAME"].strip("'\"").upper(), keyed)
    rows: list[dict[str, Any]] = []
    for line, _label, op, text in statements:
        keyed = _operands(text)
        kind = (keyed.get("TYPE") or "").upper()
        table = op + suffix.get(op, "")
        if op == "DFHFCT" and kind in ("DATASET", "REMOTE"):
            name = _name(keyed.get("DATASET"))
            if name:
                rows.append(
                    _row(
                        "FILE",
                        name,
                        table,
                        line,
                        text,
                        dsname=_name(keyed.get("DSNAME")),
                        record_format=_recform(keyed.get("RECFORM")),
                        key_length=_int(keyed.get("KEYLEN")),
                        record_size=_int(keyed.get("RECSIZE")),
                    )
                )
        elif op == "DFHPCT" and kind == "ENTRY":
            name = _name(keyed.get("TRANSID"))
            if name:
                rows.append(
                    _row("TRANSACTION", name, table, line, text, transid=name, program=_name(keyed.get("PROGRAM")))
                )
        elif op == "DFHPPT" and kind == "ENTRY":
            name = _name(keyed.get("PROGRAM"))
            if name:
                rows.append(_row("PROGRAM", name, table, line, text, program=name))
        elif op == "DFHDCT" and kind in ("INTRA", "EXTRA", "INDIRECT", "REMOTE"):
            name = _name(keyed.get("DESTID"))
            if not name:
                continue
            extra: dict[str, Any] = {"queue_type": kind}
            if kind == "EXTRA":
                dsc = (keyed.get("DSCNAME") or "").strip("'\"").upper()
                if dsc:
                    extra["ddname"] = dsc
                    detail = sdsci.get(dsc, {})
                    extra.update(
                        dsname=_name(detail.get("DSNAME")),
                        # Spelled as the CSD TDQUEUE RECORDFORMAT is (FIXED / VARIABLE), so the
                        # two sources compare; a FILE's V / F / U is the CSD FILE spelling.
                        record_format=_name(detail.get("RECFORM")),
                        record_size=_int(detail.get("RECSIZE")),
                    )
            rows.append(_row("TDQUEUE", name, table, line, text, **extra))
        elif op == "DFHTST" and kind in _TST_TYPES:
            # DATAID=(PFX1,PFX2) names several prefixes: one TSMODEL row each.
            raw = (keyed.get("DATAID") or "").strip()
            prefixes = [p.strip("() '\"").upper() for p in raw.split(",")]
            rows.extend(_row("TSMODEL", prefix, table, line, text) for prefix in prefixes if prefix)
    return rows
