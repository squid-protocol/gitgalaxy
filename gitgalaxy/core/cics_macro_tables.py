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
#          TYPE=REMOTE p.401), DFHTCT p.437-475 (TYPE=INITIAL p.441, TYPE=REGION p.473,
#          TYPE=TERMINAL p.474, TYPE=REMOTE p.474-475), DFHTST p.482-488. Chapter 16
#          "Attribute cross-reference tables" p.529-535 (macro operand -> RDO attribute,
#          notes 1 and 7), Chapter 17 "Migrating the TCT to the CSD file" p.551-553.
#   [MIG]  CICS for MVS/ESA Migration Guide, Version 4 Release 1, GC33-1162-04,
#          ch.3 "Resource definition (macro) changes": the DFHPCT / DFHPPT macros are
#          not shipped in CICS/ESA 4.1 (not supported since the introduction of
#          CICS/ESA); CICS/ESA 4.1 installs only BDAM files from an FCT.
#   [VSE]  CICS Transaction Server for VSE/ESA Release 1, "Resource Definition
#          Guide", SC33-1653-05. Chapter 29 "JCT -- journal control table" Table 41
#          p.270-273 (`DFHJCT TYPE=ENTRY,JFILEID={SYSTEM|nn},BUFSIZE=,...,JTYPE=
#          {TAPE1|TAPE2|DISK1|DISK2|SMF},JOUROPT=`), Chapter 33 "Sequential devices
#          method 2 -- DFHTCT TYPE=GPENTRY" p.297 (`TRMIDNT=xxxx`, `GPBLKSZ=`, `GPTYPE=`,
#          `LININL=`), Appendix C "Keyword cross-reference tables" p.347-356
#          (macro operand -> RDO attribute for DFHPCT, DFHPPT, DFHFCT, DFHDCT, DFHTCT,
#          DFHTST), Appendix E "Migrating the PCT to the CSD" p.365-370 (DFHPCT
#          TYPE=INITIAL|ENTRY|GROUP|PROFILE|OPTGRP|FINAL), Appendix F "Migrating the
#          PPT to the CSD" p.371-374 (`PROGRAM=name` without `USAGE=MAP` -> PROGRAM;
#          `PROGRAM=name` with `USAGE=MAP` and no non-ASSEMBLER `PGMLANG=` -> MAPSET,
#          with `USAGE(TRANSIENT)`; `MAPSET=name` -> MAPSET; `PARTSET=name` ->
#          PARTITIONSET).
#   [SPRM] CICS/VS System Programmer's Reference Manual, SH20-1043-6 (Seventh Edition,
#          March 1975): DFHDCT p.86-103 (`TYPE=SDSCI` `RECFORM=FIXUNB|FIXBLK|VARUNB|VARBLK`
#          with optional `A`/`M`, p.95-96), DFHPCT p.104-107 (`TYPE=INITIAL|ENTRY|FINAL`,
#          `TRANSID=`, `TRNPRTY=`, `TRANSEC=`, `TWASIZE=`, `PROGRAM=`, `TPURGE=`,
#          `SPURGE=`, `COMPAT=`), DFHPPT p.108-109 (`TYPE=INITIAL|ENTRY|FINAL`,
#          `PROGRAM=`, `PGMLANG=ASSEMBLER|COBOL|PL/I`, `RES=YES|NO`, `RELOAD=YES|NO`).
#   [APAR] IBM APAR II05097 (CICS/MVS 1.7 -> CICS/ESA 3.1.1 migration):
#          `DFHPPT TYPE=ENTRY,MAPSET=name` and `DFHPPT TYPE=ENTRY,PROGRAM=name`.
#   [TS]   IBM CICS TS 5.x "Reference: system management / resources / macros" pages (#5154):
#          DFHSRT TYPE=SYSTEM|USER (ibm.com/docs SSGMCP_5.3.0 .../macros/srt/system.html),
#          DFHTCT TYPE=REMOTE (SSGMCP_5.4.0 reference/resources/macros/tct/remote.html: ACCMETH,
#          SYSIDNT, TRMIDNT, TRMTYPE, RMTNAME; TYPE=TERMINAL operands are valid on a home-region
#          REMOTE), DFHMCT TYPE=EMP (SSGMCP_5.4.0 .../macros/mct/emp.html: ID, CLASS=PERFORM, ...),
#          DFHSIT TYPE=CSECT|DSECT (SSGMCP_5.5.0 configuring/cics/dfha2_specify_dfhsit_macroparms.html),
#          DFHSIT SUFFIX= (SSGMCP_5.4.0 reference/sit/dfha2_suffix.html: "Any one or two characters (other
#          than NO and DY) are valid", "specify the SUFFIX parameter in the SIT only"; the table is
#          DFHSIT + suffix and a start-up SIT=xx picks it), the table-name and suffix rules
#          (SSGMCP_5.5.0 configuring/resources/dfha4ta.html: six fixed characters + a two-character
#          suffix, FCT=MY loads DFHFCTMY), DFHMCT TYPE=RECORD (SSGMCP_5.5.0 .../macros/mct/record.html:
#          CLASS=PERFORM, EXCLUDE=, INCLUDE= select performance fields; no operand names a resource),
#          DFHTCT sequential devices (SSGMCP_5.5.0 .../macros/tct/seq.html: TYPE=SDSCI carries DSCNAME=
#          and DDNAME=, TYPE=LINE names them in ISADSCN= / OSADSCN=, the DD statement is named by DDNAME)
#          and DFHJCT's JFILEID ("supported for compatibility purposes only", SSGMCP_5.3.0 application
#          programming "Recovery and journaling", dfhp3_recov_journaling.html).
#
# MACRO -> RESOURCE:
#
#   DFHFCT TYPE=FILE,FILE=      FILE     DSNAME=, RECFORM=(UNDEFINED|VARIABLE|FIXED,..)
#          [TYPE=DATASET,DATASET= is the retained pre-CICS/ESA spelling, "exactly the same"
#          [RDG p.391, p.402]]            -> U / V / F, KEYLEN=, LRECL= -> record_size [RDG p.531]
#   DFHFCT TYPE=REMOTE,FILE=    FILE     KEYLEN=, LRECL=; SYSIDNT= / RMTNAME= -> REMOTESYSTEM /
#                               REMOTENAME in `attributes` [RDG p.532-533]
#   DFHPCT TYPE=ENTRY           TRANSACTION  TRANSID=, PROGRAM=; RDO attribute restatements from
#                               [SPRM p.104-106] and [VSE p.347-351, p.365-368] (PRIORITY,
#                               REMOTESYSTEM, REMOTENAME, PARTITIONSET, INDOUBT)
#   DFHPPT TYPE=ENTRY           PROGRAM | MAPSET | PARTITIONSET [SPRM p.108-109, VSE p.348-350, p.372]
#                               `PROGRAM=name` -> PROGRAM (or MAPSET with `USAGE(TRANSIENT)` when
#                               `USAGE=MAP` is coded without a non-ASSEMBLER `PGMLANG=` [VSE p.372]);
#                               `MAPSET=name` -> MAPSET; `PARTSET=name` -> PARTITIONSET ([VSE p.349,
#                               p.372]; `PARTITIONSET=` is accepted as an ASSUMED alias). `PGMLANG=`,
#                               `RES=YES|NO`, `PGMSTAT=` restated as `LANGUAGE`, `RESIDENT`, `STATUS`.
#   DFHDCT TYPE=INTRA|EXTRA|INDIRECT|REMOTE  DESTID=   TDQUEUE  (queue_type = the TYPE)
#          INTRA:    TRANSID= -> transid; TRIGLEV= (default 1 when TRANSID= is coded) ->
#                    TRIGGERLEVEL in `attributes` [RDG p.383, ch.16]
#          EXTRA:    DSCNAME= -> ddname; LENGTH= -> record_size; the SDSCI of that DSCNAME
#                    supplies RECFORM / RECSIZE (below). A DESTID of more than four
#                    characters is truncated on the right [RDG p.378].
#          INDIRECT: INDDEST= -> INDIRECTNAME in `attributes` [RDG p.379, p.531]
#          REMOTE:   SYSIDNT= / RMTNAME= -> REMOTESYSTEM / REMOTENAME in `attributes` [RDG p.532-533];
#                    LENGTH= -> record_size
#          TYPE=SDSCI,DSCNAME=  not a row: it is the DCB of the EXTRA entries naming it.
#            RECFORM = FIXUNB FIXBLK VARUNB VARBLK, each with the A (ASA) or M (machine)
#            control-character suffix [RDG p.376, SPRM p.95-96] -> record_format FIXED / VARIABLE
#            (the CSD TDQUEUE RECORDFORMAT spelling), BLOCKFORMAT BLOCKED / UNBLOCKED and
#            PRINTCONTROL ASA / MACHINE in `attributes` [RDG p.534 note 7]; RECSIZE= ->
#            record_size. SDSCI has NO DSNAME operand: the dataset is the JCL DD named
#            DSCNAME, so dsname is never lifted here. RECFORM=UNDEFINED is outside both
#            [RDG p.376] and [SPRM p.95-96]: record_format None, text kept.
#   DFHTST TYPE=RECOVERY|ENTRY|LOCAL|REMOTE|SECURITY  DATAID=  TSMODEL  (name = the prefix,
#          RDO PREFIX [RDG p.531]); one row per DATAID string. TYPE=ENTRY is "retained for
#          compatibility ... exactly the same as TYPE=RECOVERY" [RDG p.484]. RECOVERY(YES) /
#          SECURITY(YES) / REMOTESYSTEM / REMOTEPREFIX in `attributes`.
#
#   DFHSRT TYPE=SYSTEM|USER,ABCODE=(..),RECOVER=YES   SRT  one row per code, named as MVS names it
#          (Sxxx three hex digits / Unnnn decimal) [TS]. RECOVER=NO or no RECOVER REMOVES the codes
#          [TS]: that is not a definition, so no row. (The operand is ABCODE, not CODE.)
#   DFHJCT TYPE=ENTRY,JFILEID=SYSTEM|nn   JOURNAL  [VSE ch.29 Table 41, p.270-272]: `JFILEID=SYSTEM`
#          (system log) or decimal `nn` (1-99 user journal; 01-99 accepted); `JTYPE=`, `BUFSIZE=`,
#          `JOUROPT=` stay in `attributes`.
#   DFHTCT TYPE=TERMINAL|REMOTE|GPENTRY,TRMIDNT=  TERMINAL [TS, RDG p.473-475, VSE p.297];
#          `TYPE=REGION,SYSIDNT={ssss|LOCAL}` sets the region for subsequent `TYPE=TERMINAL`
#          entries ("Remote terminals, method 1", [RDG Table 74 p.473-474, p.551]); `SYSIDNT=`
#          (when not `LOCAL` and not the home region's `TYPE=INITIAL,SYSIDNT=`) and `RMTNAME=` are
#          restated as `REMOTESYSTEM` / `REMOTENAME` [RDG p.532-533, p.551].
#          TYPE=SYSTEM,SYSIDNT=  CONNECTION [TS, RDG p.529, p.553]; `ACCMETH=` restated as
#          `ACCESSMETHOD(IRC|VTAM|INDIRECT|XM)`.
#   DFHMCT TYPE=EMP,CLASS=PERFORM,ID=  MONITORPOINT (a user event monitoring point; it has no CSD
#          counterpart; ID is `number`, `(PP,number)` or `entryname.number`, kept as written) [TS].
#   DFHSIT TYPE=CSECT|DSECT  SIT  one row, named as IBM names the table: DFHSIT + SUFFIX= (one or two
#          characters, not NO or DY [TS]; a SUFFIX outside that names nothing and the row is DFHSIT),
#          `macro_table` the same. SUFFIX is confirmed, not ASSUMED. The system initialization
#          parameters, including the table suffixes it selects (FCT=, DCT=, SRT=, GRPLIST=, ...), ride
#          in `attributes`; they are not expanded to rows (REFUSED): a SIT parameter names the table or
#          list a start-up loads, which the SIT= / SYSIN override can change, and no source tree states.
#   JCL: a job with an assembler step (PGM=ASMA90|IEV90|IEUASM|ASMAHL|ASMBLR) or DFHAUPLE carries the
#          tables as in-stream SYSIN; mainframe_boundary reads them through the same function, and
#          the row's `line` is the line in the job. A SYSIN that is a separate member is that member's:
#          `GalaxyIR.job_macro_tables` joins the member's tables to the job step (#5154).
#   CEDA / CEMT runtime state is REFUSED: installed state is not in a source tree (register entry).
#
#   REFUSED (read nothing rather than guess): FCT `RECSIZE=` (not an FCT operand; the
#   record length is LRECL); DATAID=() (the "any other queue" null, it names no prefix);
#   DFHTST TYPE=SHARED (a pool, not a model); TYPE=INITIAL / FINAL / GROUP (assembly
#   control and CSD-migration statements, not resources); a TYPE= or RECFORM word the
#   manual does not list; DFHTCT TYPE=LINE / SDSCI (sequential-device plumbing: SDSCI is the DD of the
#   simulated device and LINE joins two SDSCIs by ISADSCN= / OSADSCN= [TS]; the terminal it serves is
#   the TYPE=TERMINAL row); DFHMCT TYPE=RECORD (selects
#   performance fields, names no resource [TS]); DFHJCT TYPE=INITIAL / FINAL.
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

_TABLES = ("DFHFCT", "DFHPCT", "DFHPPT", "DFHDCT", "DFHTST", "DFHSIT", "DFHSRT", "DFHJCT", "DFHTCT", "DFHMCT")
_GATE = re.compile(r"\bDFH(?:FCT|PCT|PPT|DCT|TST|SIT|SRT|JCT|TCT|MCT)\b", re.I)
_SRT_SYSTEM_CODE = re.compile(r"[0-9A-F]{3}\Z")  # TYPE=SYSTEM: "three hexadecimal digits" [CICS TS 5.3 DFHSRT]
_SRT_USER_CODE = re.compile(r"[0-9]{1,4}\Z")  # TYPE=USER: "a decimal number (nnnn)"
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
_PCT_DTB = {"YES": "BACKOUT", "YES,NO": "COMMIT", "YES,WAIT": "WAIT"}  # [VSE p.348, p.367]
_TCT_ACCMETH = {"INDIRECT": "INDIRECT", "IRC": "IRC", "VTAM": "VTAM", "IRC,XM": "XM"}  # [RDG p.529]
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
        rdo += [
            f"{k}({v})"
            for k, v in (("REMOTESYSTEM", _name(keyed.get("SYSIDNT"))), ("REMOTENAME", _name(keyed.get("RMTNAME"))))
            if v
        ]
    elif kind == "INDIRECT":
        if ind := _name(keyed.get("INDDEST") or keyed.get("INDEST")):
            rdo.append(f"INDIRECTNAME({ind})")
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


def _pct_rdo(keyed: dict[str, str]) -> list[str]:
    """DFHPCT TYPE=ENTRY operands spelled differently in RDO -> their RDO attribute restatement [VSE p.347-351, p.367]."""
    rdo: list[str] = []
    if (prio := _int(keyed.get("TRNPRTY"))) is not None and 0 <= prio <= 255:
        rdo.append(f"PRIORITY({prio})")
    for op_name, rdo_name in (("SYSIDNT", "REMOTESYSTEM"), ("RMTNAME", "REMOTENAME"), ("PARTSET", "PARTITIONSET")):
        if val := _name(keyed.get(op_name)):
            rdo.append(f"{rdo_name}({val})")
    dtb = ",".join(p.strip("() '\"").upper() for p in (keyed.get("DTB") or "").split(",") if p.strip("() '\""))
    if indoubt := _PCT_DTB.get(dtb):
        rdo.append(f"INDOUBT({indoubt})")
    return rdo


def _ppt_rows(line: int, text: str, keyed: dict[str, str], table: str) -> list[dict[str, Any]]:
    """DFHPPT TYPE=ENTRY -> PROGRAM | MAPSET | PARTITIONSET [SPRM p.108-109, VSE p.348-350, p.372].

    `PROGRAM=name` with `USAGE=MAP` (unless `PGMLANG` names a language other than ASSEMBLER) defines
    a MAPSET with `USAGE(TRANSIENT)` [VSE p.372]; `PARTSET=name` defines a PARTITIONSET [VSE p.349,
    p.372] (`PARTITIONSET=` is accepted as an ASSUMED alias).
    """
    usage_map = _name(keyed.get("USAGE")) == "MAP"
    lang = _name(keyed.get("PGMLANG"))
    res = _name(keyed.get("RES"))
    stat = _name(keyed.get("PGMSTAT"))
    out: list[dict[str, Any]] = []
    for operand, rtype in (
        ("PROGRAM", "MAPSET" if usage_map and lang in (None, "ASSEMBLER") else "PROGRAM"),
        ("MAPSET", "MAPSET"),
        ("PARTITIONSET", "PARTITIONSET"),
        ("PARTSET", "PARTITIONSET"),
    ):
        name = _name(keyed.get(operand))
        if not name:
            continue
        rdo: list[str] = []
        if rtype == "PROGRAM" and lang:
            rdo.append(f"LANGUAGE({lang})")
        if res == "YES" or (rtype == "PROGRAM" and res == "NO"):
            rdo.append(f"RESIDENT({res})")
        if stat:
            rdo.append(f"STATUS({stat})")
        if usage_map:
            rdo.append("USAGE(TRANSIENT)")
        out.append(_row(rtype, name, table, line, text, rdo, program=name if rtype == "PROGRAM" else None))
    return out


def _jfileid(value: str | None) -> str | None:
    """DFHJCT JFILEID= -> `SYSTEM` or a 1-2 digit journal identifier (`01`-`99`) [VSE Table 41, p.270-271]."""
    name = _name(value)
    if name == "SYSTEM" or (name and name.isdigit() and 1 <= len(name) <= 2 and 1 <= int(name) <= 99):
        return name
    return None


def _sit_suffix(value: str | None) -> str:
    """DFHSIT SUFFIX= -> its one or two characters, or "" (any other value is not a SUFFIX) [TS dfha2_suffix]."""
    text = (_first(value) or "").strip("'\"").upper()
    return text if 1 <= len(text) <= 2 and text not in ("NO", "DY") else ""


def _emp_id(value: str | None) -> str | None:
    """DFHMCT ID= -> `entryname.number`: `180` / `(PP,3)` / `BANK.180` [CICS TS 5.4 DFHMCT TYPE=EMP].

    The default entry name is USER; `(PP,n)` is "equivalent to ID 199 + n" (n 1-56); a user
    number is 1-255 (1-199 user, 200-255 IBM). Anything else names nothing.
    """
    text = (value or "").strip().strip("'\"").upper()
    pp = re.fullmatch(r"\(PP,(\d{1,2})\)", text)
    if pp and 1 <= int(pp.group(1)) <= 56:
        return f"USER.{199 + int(pp.group(1))}"
    entry, _, number = text.strip("()").rpartition(".")
    if not number.isdigit() or not 1 <= int(number) <= 255 or (entry and not entry.isalnum()):
        return None
    return f"{entry or 'USER'}.{int(number)}"


def _srt_rows(line: int, text: str, keyed: dict[str, str], kind: str, table: str) -> list[dict[str, Any]]:
    """DFHSRT TYPE=SYSTEM|USER: one SRT row per intercepted abend code, only for RECOVER=YES.

    RECOVER=NO, or no RECOVER, "removes" the codes from the SRT: that is not a definition,
    so it yields nothing. A code that is not three hex digits (SYSTEM) or a decimal number
    (USER) is dropped. The row is named as the MVS code is: Sxxx / Unnnn.
    """
    if (_first(keyed.get("RECOVER")) or "") != "YES":
        return []
    shape, prefix = (_SRT_SYSTEM_CODE, "S") if kind == "SYSTEM" else (_SRT_USER_CODE, "U")
    codes = [c.strip("() '\"").upper() for c in (keyed.get("ABCODE") or "").split(",")]
    return [_row("SRT", prefix + code, table, line, text, ["RECOVER(YES)"]) for code in codes if shape.match(code)]


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
    tct_home: str | None = None
    for _line, _label, op, text in statements:
        keyed = _operands(text)
        kind = _type_of(keyed)
        if kind == "INITIAL" and keyed.get("SUFFIX"):
            suffix.setdefault(op, keyed["SUFFIX"].strip("'\"").upper())
        if op == "DFHTCT" and kind == "INITIAL" and keyed.get("SYSIDNT") and tct_home is None:
            tct_home = _name(keyed.get("SYSIDNT"))
        elif op == "DFHDCT" and kind == "SDSCI" and keyed.get("DSCNAME"):
            sdsci.setdefault(keyed["DSCNAME"].strip("'\"").upper(), keyed)
    rows: list[dict[str, Any]] = []
    tct_region: str | None = None
    for line, _label, op, text in statements:
        keyed = _operands(text)
        kind = _type_of(keyed)
        table = op + suffix.get(op, "")
        if op == "DFHFCT" and kind in ("FILE", "DATASET", "REMOTE"):
            # DATASET= / TYPE=DATASET: "retained for compatibility ... exactly the same" [RDG p.391, p.402]
            name = _name(keyed.get("FILE") or keyed.get("DATASET"))
            if name:
                rdo = (
                    [
                        f"{k}({v})"
                        for k, v in (
                            ("REMOTESYSTEM", _name(keyed.get("SYSIDNT"))),
                            ("REMOTENAME", _name(keyed.get("RMTNAME"))),
                        )
                        if v
                    ]
                    if kind == "REMOTE"
                    else []
                )
                rows.append(
                    _row(
                        "FILE",
                        name,
                        table,
                        line,
                        text,
                        rdo,
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
                    _row(
                        "TRANSACTION",
                        name,
                        table,
                        line,
                        text,
                        _pct_rdo(keyed),
                        transid=name,
                        program=_name(keyed.get("PROGRAM")),
                    )
                )
        elif op == "DFHPPT" and kind == "ENTRY":
            rows.extend(_ppt_rows(line, text, keyed, table))
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
        elif op == "DFHSRT" and kind in ("SYSTEM", "USER"):
            rows.extend(_srt_rows(line, text, keyed, kind, table))
        elif op == "DFHJCT" and kind == "ENTRY":
            name = _jfileid(keyed.get("JFILEID"))
            if name:
                rows.append(_row("JOURNAL", name, table, line, text))
        elif op == "DFHTCT" and kind == "REGION":
            # Remote terminals, method 1 [RDG Table 74 p.473-474, p.551]: SYSIDNT=LOCAL or the
            # home region's SYSIDNT resets subsequent TYPE=TERMINAL macros to the local region.
            reg = _name(keyed.get("SYSIDNT"))
            tct_region = None if reg in (None, "LOCAL", tct_home) else reg
        elif op == "DFHTCT" and kind in ("TERMINAL", "REMOTE", "GPENTRY"):
            name = _name(keyed.get("TRMIDNT"))
            if name:
                sysid = _name(keyed.get("SYSIDNT")) or (tct_region if kind == "TERMINAL" else None)
                remote_sys = None if sysid in (None, "LOCAL", tct_home) else sysid
                rdo = [
                    f"{k}({v})"
                    for k, v in (("REMOTESYSTEM", remote_sys), ("REMOTENAME", _name(keyed.get("RMTNAME"))))
                    if v
                ]
                rows.append(_row("TERMINAL", name, table, line, text, rdo))
        elif op == "DFHTCT" and kind == "SYSTEM":
            name = _name(keyed.get("SYSIDNT"))
            if name:
                accm = ",".join(
                    p.strip("() '\"").upper() for p in (keyed.get("ACCMETH") or "").split(",") if p.strip("() '\"")
                )
                rdo = [f"ACCESSMETHOD({m})"] if (m := _TCT_ACCMETH.get(accm)) else []
                rows.append(_row("CONNECTION", name, table, line, text, rdo))
        elif op == "DFHMCT" and kind == "EMP":
            name = _emp_id(keyed.get("ID"))
            if name:
                rows.append(_row("MONITORPOINT", name, table, line, text))
        elif op == "DFHSIT" and kind in ("CSECT", "DSECT"):
            # One row per table; the table-selection operands (FCT=, DCT=, ...) ride in `attributes`.
            suffix_ = _sit_suffix(keyed.get("SUFFIX"))
            rows.append(_row("SIT", "DFHSIT" + suffix_, "DFHSIT" + suffix_, line, text))
    return rows
