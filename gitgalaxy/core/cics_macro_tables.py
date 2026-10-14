# ==============================================================================
# GitGalaxy Core: CICS resource macro tables (DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST) (#5120)
#
# PURPOSE:
# Before CEDA / the CSD, a CICS region's resources were assembled into macro
# tables, and a region can still load some of them (SIT FCT=, DCT=, TST=). The
# resource facts a CSD deck declares -- FILE -> DSNAME, TRANSACTION -> PROGRAM,
# TDQUEUE -> DDNAME -- are in those tables too, as assembler macro statements.
# This reader lifts them into the SAME row shape `mainframe_boundary._csd_resources`
# produces, so the macro and CSD definitions land in one `csd_resource_data` table
# and merge into one resource map (GalaxyIR.resource_map), conflicts named.
#
# Each row also names its provenance: `source` = "MACRO", `macro_table` (the
# assembled table, `DFHFCT` + its `TYPE=INITIAL,SUFFIX=` suffix, so DFHFCT01) and
# `line` (the macro statement's first line). A CSD row has no `source` key; the
# recorder stores it as "CSD". `attributes` is the statement's operand text, then,
# after ` => `, the operands the macro spells differently from RDO restated under
# their RDO attribute name (RECORDFORMAT / BLOCKFORMAT / PRINTCONTROL /
# TRANSID / TRIGGERLEVEL / RECOVERY ...), so nothing a macro states is lost.
#
# IBM SOURCES (the syntax here is read from these, not from memory):
#   [RDG]  CICS Transaction Server for OS/390 Release 3, "CICS Resource Definition
#          Guide", SC33-1684-30 (CICS TS 1.3). Chapter 13 "Resource definition with
#          macros": DFHDCT p.368-385 (TYPE=SDSCI p.375, EXTRA p.377, INDIRECT p.379,
#          INTRA p.380-383, REMOTE p.383), DFHFCT p.391-403 (TYPE=FILE p.392,
#          TYPE=REMOTE p.401), DFHTST p.482-488. Chapter 16 "Attribute cross-reference
#          tables" p.530-535 (macro operand -> RDO attribute, notes 1 and 7).
#   [MIG]  CICS for MVS/ESA Migration Guide, Version 4 Release 1, GC33-1162-04,
#          ch.3 "Resource definition (macro) changes": the DFHPCT / DFHPPT macros are
#          not shipped in CICS/ESA 4.1 (not supported since the introduction of
#          CICS/ESA); CICS/ESA 4.1 installs only BDAM files from an FCT.
#   [APAR] IBM APAR II05097 (CICS/MVS 1.7 -> CICS/ESA 3.1.1 migration):
#          `DFHPPT TYPE=ENTRY,MAPSET=name` and `DFHPPT TYPE=ENTRY,PROGRAM=name`.
#   The CICS/VS and CICS/ESA 3.x "Resource Definition (Macro)" manuals themselves
#   were NOT retrievable; where a statement below rests on [MIG] / [APAR] / a
#   retained-spelling note instead of a syntax table, it is marked ASSUMED.
#
# MACRO -> RESOURCE:
#
#   DFHFCT TYPE=FILE,FILE=      FILE     DSNAME=, RECFORM=(UNDEFINED|VARIABLE|FIXED,..)
#          [TYPE=DATASET,DATASET= is the retained pre-CICS/ESA spelling, "exactly the same"
#          [RDG p.391, p.402]]            -> U / V / F, KEYLEN=, LRECL= -> record_size [RDG p.531]
#   DFHFCT TYPE=REMOTE,FILE=    FILE     KEYLEN=, LRECL=; SYSIDNT= / RMTNAME= ride in `attributes`
#   DFHPCT TYPE=ENTRY           TRANSACTION  TRANSID=, PROGRAM=                     (ASSUMED, [MIG])
#   DFHPPT TYPE=ENTRY           PROGRAM | MAPSET | PARTITIONSET
#                               by which of PROGRAM= / MAPSET= / PARTITIONSET= (PARTSET=) names it
#                               ([APAR] for PROGRAM= and MAPSET=; PARTITIONSET=/PARTSET= ASSUMED)
#   DFHDCT TYPE=INTRA|EXTRA|INDIRECT|REMOTE  DESTID=   TDQUEUE  (queue_type = the TYPE)
#          INTRA:    TRANSID= -> transid; TRIGLEV= (default 1 when TRANSID= is coded) ->
#                    TRIGGERLEVEL in `attributes` [RDG p.383, ch.16]
#          EXTRA:    DSCNAME= -> ddname; LENGTH= -> record_size; the SDSCI of that DSCNAME
#                    supplies RECFORM / RECSIZE (below). A DESTID of more than four
#                    characters is truncated on the right [RDG p.378].
#          INDIRECT: INDDEST= rides in `attributes` (RDO INDIRECTNAME)
#          REMOTE:   SYSIDNT= / RMTNAME= in `attributes`; LENGTH= -> record_size
#          TYPE=SDSCI,DSCNAME=  not a row: it is the DCB of the EXTRA entries naming it.
#            RECFORM = FIXUNB FIXBLK VARUNB VARBLK, each with the A (ASA) or M (machine)
#            control-character suffix [RDG p.376] -> record_format FIXED / VARIABLE (the CSD
#            TDQUEUE RECORDFORMAT spelling), BLOCKFORMAT BLOCKED / UNBLOCKED and
#            PRINTCONTROL ASA / MACHINE in `attributes` [RDG p.534 note 7]; RECSIZE= ->
#            record_size. SDSCI has NO DSNAME operand: the dataset is the JCL DD named
#            DSCNAME, so dsname is never lifted here. RECFORM=UNDEFINED is not in [RDG]
#            (ASSUMED from the CICS/ESA reviewer note): record_format None, text kept.
#   DFHTST TYPE=RECOVERY|ENTRY|LOCAL|REMOTE|SECURITY  DATAID=  TSMODEL  (name = the prefix,
#          RDO PREFIX [RDG p.531]); one row per DATAID string. TYPE=ENTRY is "retained for
#          compatibility ... exactly the same as TYPE=RECOVERY" [RDG p.484]. RECOVERY(YES) /
#          SECURITY(YES) / REMOTESYSTEM / REMOTEPREFIX in `attributes`.
#
#   REFUSED (read nothing rather than guess): FCT `RECSIZE=` (not an FCT operand; the
#   record length is LRECL); DATAID=() (the "any other queue" null, it names no prefix);
#   DFHTST TYPE=SHARED (a pool, not a model); TYPE=INITIAL / FINAL / GROUP (assembly
#   control and CSD-migration statements, not resources); a TYPE= or RECFORM word the
#   manual does not list; DFHSIT / DFHSRT / DFHJCT / DFHTCT / DFHMCT.
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. Joining a macro FILE to its JCL dataset, and
#     comparing it with the same resource in a CSD, is the reader's job
#     (GalaxyIR.cics_file_datasets / resource_map / resource_conflicts).
#   - Assembler continuation: a non-blank column 72 continues the statement on the
#     next line, resuming at column 16; `*` in column 1 is a comment. Reused from
#     ims_gen, bounded per statement.
# ==============================================================================
import re
from typing import Any

from gitgalaxy.core.ims_gen import _first, _operands, _statements

_TABLES = ("DFHFCT", "DFHPCT", "DFHPPT", "DFHDCT", "DFHTST")
_GATE = re.compile(r"\bDFH(?:FCT|PCT|PPT|DCT|TST)\b", re.I)
# FCT RECFORM's first element [RDG p.392]; the RDO FILE RECORDFORMAT is U | V | F [RDG p.532].
_FCT_RECFORM = {"UNDEFINED": "U", "VARIABLE": "V", "FIXED": "F"}
# SDSCI RECFORM [RDG p.376]: base word -> (RECORDFORMAT, BLOCKFORMAT); suffix -> PRINTCONTROL.
_SDSCI_BASE = {
    "FIXUNB": ("FIXED", "UNBLOCKED"),
    "FIXBLK": ("FIXED", "BLOCKED"),
    "VARUNB": ("VARIABLE", "UNBLOCKED"),
    "VARBLK": ("VARIABLE", "BLOCKED"),
}
_SDSCI_CONTROL = {"": None, "A": "ASA", "M": "MACHINE"}
_TST_TYPES = frozenset({"LOCAL", "REMOTE", "RECOVERY", "SECURITY", "ENTRY"})
_TRIGLEV_MAX = 32767  # [RDG p.383]
_RDO_SEP = " => "


def _name(value: str | None) -> str | None:
    """A name-valued operand: first element of a list, unquoted, upper-cased, or None."""
    return (_first(value) or "").strip("'\"").upper() or None


def _int(value: str | None) -> int | None:
    value = (value or "").strip().strip("()'\"").split(",")[0].strip()
    return int(value) if value.isdigit() and len(value) <= 9 else None


def _fct_recform(value: str | None) -> str | None:
    """`(VARIABLE,BLOCKED)` / `FIXED` -> V / F / U; a word the manual does not list is dropped."""
    return _FCT_RECFORM.get((_first(value) or "").strip("'\"").upper())


def sdsci_recform(value: str | None) -> tuple[str | None, str | None, str | None]:
    """A DFHDCT SDSCI RECFORM word -> (RECORDFORMAT, BLOCKFORMAT, PRINTCONTROL), each None when unstated.

    FIXUNB / FIXBLK / VARUNB / VARBLK, each optionally suffixed A (ASA control
    characters) or M (machine). A word outside that set -- UNDEFINED included -- maps to
    all None: nothing is claimed for it.
    """
    word = (value or "").strip().strip("()'\"").upper()
    base, suffix = word[:6], word[6:]
    if base in _SDSCI_BASE and suffix in _SDSCI_CONTROL:
        record, block = _SDSCI_BASE[base]
        return record, block, _SDSCI_CONTROL[suffix]
    return None, None, None


def _row(
    resource_type: str,
    name: str | None,
    table: str,
    line: int,
    text: str,
    rdo: list[str] | None = None,
    **lifted: Any,
) -> dict[str, Any]:
    attributes = " ".join(text.split())
    if rdo:
        attributes += _RDO_SEP + " ".join(rdo)
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
        "attributes": attributes or None,
        "line": line,
        "source": "MACRO",
        "macro_table": table,
    }
    row.update(lifted)
    return row


def _type_of(keyed: dict[str, str]) -> str:
    """The TYPE= keyword; `TYPE=(INITIAL,MIGRATE)` reads as INITIAL."""
    return (_first(keyed.get("TYPE")) or "").upper()


def _dct_row(line: int, text: str, keyed: dict[str, str], kind: str, table: str, sdsci: dict[str, dict[str, str]]):
    name = _name(keyed.get("DESTID"))
    if not name:
        return None
    rdo: list[str] = []
    extra: dict[str, Any] = {"queue_type": kind}
    if kind == "EXTRA":
        name = name[:4]  # "truncated on the right" [RDG p.378]
        dsc = (keyed.get("DSCNAME") or "").strip("'\"").upper()
        extra["record_size"] = _int(keyed.get("LENGTH"))
        if dsc:
            extra["ddname"] = dsc
            detail = sdsci.get(dsc, {})
            record, block, control = sdsci_recform(detail.get("RECFORM"))
            extra["record_format"] = record
            if (size := _int(detail.get("RECSIZE"))) is not None:
                extra["record_size"] = size
            rdo += [
                f"{k}({v})"
                for k, v in (("RECORDFORMAT", record), ("BLOCKFORMAT", block), ("PRINTCONTROL", control))
                if v
            ]
            if detail.get("RECFORM") and record is None:
                rdo.append(f"RECFORM({detail['RECFORM'].strip('()').upper()})")
    elif kind == "REMOTE":
        extra["record_size"] = _int(keyed.get("LENGTH"))
    elif kind == "INTRA":
        transid = _name(keyed.get("TRANSID"))
        trigger = _int(keyed.get("TRIGLEV"))
        if trigger is not None and trigger > _TRIGLEV_MAX:
            trigger = None
        if trigger is None and transid:
            trigger = 1  # "If you code the TRANSID operand, TRIGLEV defaults to 1" [RDG p.383]
        extra["transid"] = transid
        rdo += ([f"TRANSID({transid})"] if transid else []) + (
            [f"TRIGGERLEVEL({trigger})"] if trigger is not None else []
        )
    return _row("TDQUEUE", name, table, line, text, rdo, **extra)


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
        kind = _type_of(keyed)
        if kind == "INITIAL" and keyed.get("SUFFIX"):
            suffix.setdefault(op, keyed["SUFFIX"].strip("'\"").upper())
        elif op == "DFHDCT" and kind == "SDSCI" and keyed.get("DSCNAME"):
            sdsci.setdefault(keyed["DSCNAME"].strip("'\"").upper(), keyed)
    rows: list[dict[str, Any]] = []
    for line, _label, op, text in statements:
        keyed = _operands(text)
        kind = _type_of(keyed)
        table = op + suffix.get(op, "")
        if op == "DFHFCT" and kind in ("FILE", "DATASET", "REMOTE"):
            # DATASET= / TYPE=DATASET: "retained for compatibility ... exactly the same" [RDG p.391, p.402]
            name = _name(keyed.get("FILE") or keyed.get("DATASET"))
            if name:
                rows.append(
                    _row(
                        "FILE",
                        name,
                        table,
                        line,
                        text,
                        dsname=_name(keyed.get("DSNAME")),
                        record_format=_fct_recform(keyed.get("RECFORM")),
                        key_length=_int(keyed.get("KEYLEN")),
                        record_size=_int(keyed.get("LRECL")),
                    )
                )
        elif op == "DFHPCT" and kind == "ENTRY":
            name = _name(keyed.get("TRANSID"))
            if name:
                rows.append(
                    _row("TRANSACTION", name, table, line, text, transid=name, program=_name(keyed.get("PROGRAM")))
                )
        elif op == "DFHPPT" and kind == "ENTRY":
            for operand, rtype in (
                ("PROGRAM", "PROGRAM"),
                ("MAPSET", "MAPSET"),
                ("PARTITIONSET", "PARTITIONSET"),
                ("PARTSET", "PARTITIONSET"),
            ):
                name = _name(keyed.get(operand))
                if name:
                    rows.append(_row(rtype, name, table, line, text, program=name if rtype == "PROGRAM" else None))
        elif op == "DFHDCT" and kind in ("INTRA", "EXTRA", "INDIRECT", "REMOTE"):
            row = _dct_row(line, text, keyed, kind, table, sdsci)
            if row:
                rows.append(row)
        elif op == "DFHTST" and kind in _TST_TYPES:
            # DATAID=(PFX1,PFX2) names several prefixes: one TSMODEL row each; the null
            # DATAID=() names none and is refused.
            rdo = {"RECOVERY": ["RECOVERY(YES)"], "ENTRY": ["RECOVERY(YES)"], "SECURITY": ["SECURITY(YES)"]}.get(
                kind, []
            )
            if kind == "REMOTE":
                rdo = [
                    f"{k}({v})"
                    for k, v in (
                        ("REMOTESYSTEM", _name(keyed.get("SYSIDNT"))),
                        ("REMOTEPREFIX", _name(keyed.get("RMTNAME"))),
                    )
                    if v
                ]
            prefixes = [p.strip("() '\"").upper() for p in (keyed.get("DATAID") or "").strip().split(",")]
            rows.extend(_row("TSMODEL", prefix, table, line, text, rdo) for prefix in prefixes if prefix)
    return rows
