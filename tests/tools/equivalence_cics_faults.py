"""#5274: the faults family of the CICS harness (equivalence_cics), split out of equivalence_cics.py: a scenario's
`faults` as the `CMD NAME NTH RESP RESP2` lines both runtimes read (faults.cfg, CicsTask.withFaults), IBM's conditions
and RESP2 per command (file control, SEND MAP / RECEIVE MAP / RETURN / SYNCPOINT / ROLLBACK / DELAY), the planned
ABEND forms (#6271), the ENQ fault key (#5089) and a scenario's DL/I statuses (#5233). equivalence_cics's translator and
runners call these; they reach its shared names (Unsupported, CICS_RESP) through the module at call time, so the
import works either way round."""

from __future__ import annotations

import re
from typing import Any

import equivalence_cics as ec


def enq_fault_key(resource: str | None) -> str:
    """#5089: the name an ENQ fault gives its resource -- the RESOURCE operand as written (upper case, no blanks), which
    both translators read from the same source text. At most 16 characters: the stub's fault counters key on that."""
    key = re.sub(r"\s+", "", (resource or "").upper())
    if not key or len(key) > 16 or "'" in key:
        raise ec.Unsupported(
            f"ENQ RESOURCE({resource}): a data-name of 1 to 16 characters is the name a fault gives it"
        )
    return key


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
    "LINK",  # #4648: its `program` too; LINK PGMIDERR, NOTAUTH, INVREQ, LENGERR (CICS TS, LINK "Conditions")
    "WRITEQ-TS",
    "START",
    "RETRIEVE",
    "CANCEL",
    "ENQ",  # #5089: its `resource` (the RESOURCE operand as written); ENQBUSY only, see ENQ_FAULTS
    "SEND-MAP",  # #6271 (register X71): its `map`; RECEIVE-MAP too. RETURN, SYNCPOINT and ROLLBACK name none (`-`)
    "RECEIVE-MAP",
    "SEND-TEXT",  # #6271 (X71): nameless, like RETURN
    "RETURN",
    "SYNCPOINT",
    "ROLLBACK",
    "DELAY",  # #6271 (register X72): nameless, like RETURN
)  # a file command (FILE), an INQUIRE PROGRAM (the program's name in `file`)

# #4986 (register X43): IBM's LINK conditions the region does not raise and that have no sourced abend code
LINK_REFUSED_CONDITIONS = ("ROLLEDBACK", "SYSIDERR", "TERMERR")

_FAULT_NAME = (
    "file",
    "program",
    "queue",
    "transid",
    "reqid",
    "resource",
    "map",
)  # #4049: the resource a fault names, by key

# #5044 (register X49, extends #4623's X48): the conditions a file command may be planned with, per command, and the RESP2
# IBM gives each (CICS TS 6.x, each command's "Conditions"; the syntax line's list and the RESP2 values checked against
# the raw pages of READ, READNEXT, READPREV, WRITE, REWRITE, DELETE, STARTBR, ENDBR). A condition is planned only on a
# command IBM lists it for, with a RESP2 IBM gives it there and a local VSAM file can reach (the RLS, BDAM, data-table and
# coupling-facility values are refused). One value: the default; several (INVREQ, LENGERR): the scenario names one.
_BROWSE = ("READNEXT", "READPREV")
_FILE_CMDS = ("READ", "READNEXT", "READPREV", "STARTBR", "ENDBR", "WRITE", "REWRITE", "DELETE")
_READS = ("READ", *_BROWSE)
FILE_FAULT_CONDITIONS: dict[str, dict[str, tuple[int, ...]]] = {
    "FILENOTFOUND": dict.fromkeys(_FILE_CMDS, (1,)),
    "NOTAUTH": dict.fromkeys(_FILE_CMDS, (101,)),
    # READNEXT / READPREV / REWRITE: IBM adds "the browse in progress is terminated", which neither runtime models (below)
    "ILLOGIC": dict.fromkeys(("READ", "STARTBR", "ENDBR", "WRITE", "DELETE"), (110,)),
    "IOERR": dict.fromkeys(_FILE_CMDS, (120,)),
    # remote files: planned like IOERR, an injection (the case states what the program sees, the region needs no remote
    # system). SYSIDERR 130 "SYSID is neither the local system nor a known remote system, or the link is closed" (131 / 132
    # are coupling-facility data tables); ISCINVREQ 70 "the remote system reported a failure that is no known condition"
    "SYSIDERR": dict.fromkeys(_FILE_CMDS, (130,)),
    "ISCINVREQ": dict.fromkeys(_FILE_CMDS, (70,)),
    # NOTFND 80 (READ/READNEXT/READPREV/STARTBR: no record matches the search argument); REWRITE's 80 is the data-table
    # case only, WRITE / ENDBR do not list it
    "NOTFND": dict.fromkeys((*_READS, "STARTBR", "DELETE"), (80,)),
    "ENDFILE": dict.fromkeys(_BROWSE, (90,)),
    "DISABLED": dict.fromkeys(("READ", "WRITE", "DELETE", "STARTBR"), (50,)),
    "NOTOPEN": dict.fromkeys(
        ("READ", "WRITE", "DELETE", "STARTBR"), (60,)
    ),  # not REWRITE / READNEXT / READPREV / ENDBR
    "NOSPACE": dict.fromkeys(("WRITE", "REWRITE"), (100,)),  # READ's 100 is an RLS-only case
    "LOCKED": dict.fromkeys((*_READS, "WRITE", "REWRITE", "DELETE"), (106,)),
    "DUPKEY": dict.fromkeys(_READS, (140,)),  # #4623
    "DUPREC": dict.fromkeys(("WRITE", "REWRITE"), (150,)),  # #4623
    "LENGERR": {
        **dict.fromkeys(_READS, (10, 11, 13)),
        **dict.fromkeys(("WRITE", "REWRITE"), (10, 12, 14)),
    },
    "INVREQ": {
        "READ": (20, 25, 26, 28, 42),
        "READNEXT": (20, 25, 26, 34, 37, 42),
        "READPREV": (20, 24, 26, 37, 41),
        "STARTBR": (20, 25, 26, 33, 42),
        "ENDBR": (35,),
        "WRITE": (20, 23, 26),
        "REWRITE": (30, 47),
        "DELETE": (20, 21, 22, 25, 26, 31, 42, 47),
    },
}
# IBM lists these for file commands but they belong to data tables (LOADING, CHANGED, SUPPRESSED) and RLS (RECORDBUSY,
# NOSUSPEND), which no case defines: refused by name (X49)
FILE_FAULT_REFUSED = ("LOADING", "RECORDBUSY", "CHANGED", "SUPPRESSED")
# IBM lists DUPKEY (RESP2 140) for DELETE too but does not say whether the record is deleted: refused by name (X48).
DUP_KEY_REFUSED = {("DELETE", "DUPKEY"): "register X48"}
FILE_FAULT_UNMODELLED = {
    ("READNEXT", "ILLOGIC"),
    ("READPREV", "ILLOGIC"),
    ("REWRITE", "ILLOGIC"),
}  # X49: ends the browse
FILE_FAULT_COMMANDS = _FILE_CMDS
# #5168 (X61): READQ TD's IOERR ("an input/output error ... the data record in error is skipped"; IBM states no RESP2), planned on
# an open extrapartition input queue; and QBUSY (no RESP2 either), "a logically recoverable intrapartition queue that another task is
# writing to or deleting from, and no committed records remain", which needs a second task, so the plan states it. IBM's other
# READQ TD conditions follow from the queue and the call (NOTOPEN, INVREQ, QZERO, LENGERR, QIDERR, DISABLED): no plan names them.
TD_READ_FAULTS = ("IOERR", "QBUSY")
TD_READ_COMMAND = (
    "READQ-TD"  # not in FAULT_COMMANDS: the strengthening loop plans from that list, with a NOTAUTH it cannot give here
)


def _file_fault_resp2(sc: dict[str, Any], f: dict[str, Any], cmd: str, resp2: int) -> int:
    """#4623 / #5044: a file command's planned condition against IBM's list for the command; the RESP2 it carries."""
    resp = f["resp"]
    where = f"scenario {sc.get('name')}: fault {f}"
    if (cmd, resp) in DUP_KEY_REFUSED:
        raise ec.Unsupported(
            f"{where}: IBM lists {resp} for {cmd} but not whether the record is deleted ({DUP_KEY_REFUSED[(cmd, resp)]}, refused)"
        )
    if resp in FILE_FAULT_REFUSED:
        raise ec.Unsupported(
            f"{where}: {resp} is IBM-documented for {cmd} but it is a data-table or RLS condition and no case defines either "
            "(register X49, refused)"
        )
    if (cmd, resp) in FILE_FAULT_UNMODELLED:
        raise ec.Unsupported(
            f"{where}: IBM's {resp} on {cmd} also terminates the browse in progress, which the runtimes do not model "
            "(register X49, refused)"
        )
    cmds = FILE_FAULT_CONDITIONS.get(resp, {})
    if cmd not in cmds:
        listed = "/".join(cmds)
        raise ec.Unsupported(
            f"{where}: IBM documents {resp} for {listed}, not {cmd}"
            if listed
            else f"{where}: {resp} is not a condition IBM lists for {cmd} (register X49, refused)"
        )
    ibm = cmds[cmd]
    if resp2 == 0:  # not given
        if len(ibm) > 1:
            raise ec.Unsupported(f"{where}: IBM gives {resp} on {cmd} RESP2 {'/'.join(map(str, ibm))}: name one")
        return ibm[0]
    if resp2 not in ibm:
        raise ec.Unsupported(f"{where}: IBM's {resp} on {cmd} has RESP2 {'/'.join(map(str, ibm))}, not {resp2}")
    return resp2


# #6271 (register X70): the abend codes IBM documents for a VSAM RLS file control request -- AFCR (the RLS server is
# unavailable), AFCS (an RLS access to a file with no SMSVSAM), AFCT (an RLS timeout) -- a scenario may plant on a file
# command: the task abends with the code (cause "system") and a HANDLE ABEND exit gets control. AFCC (an internal logic
# error in the file control request module DFHFCFR) is the code outside the RLS storm-drain family: a program's
# `EVALUATE ABCODE` none arm. No other code is sourced.
FILE_ABEND_CODES = ("AFCR", "AFCS", "AFCT", "AFCC")


def _abend_fault_line(sc: dict[str, Any], f: dict[str, Any], cmd: str) -> str:
    """One `{"cmd", "file", "resp": "ABEND", "abcode", "nth"}` fault as the `CMD NAME NTH -1 0 ABCODE` line both sides read."""
    where = f"scenario {sc['name']}: fault {f}"
    if cmd not in (*FILE_FAULT_COMMANDS, "LINK") or f.get("abcode") not in FILE_ABEND_CODES or f.get("resp2"):
        raise ec.Unsupported(
            f"{where}: an ABEND is planned on a file control command ({'/'.join(FILE_FAULT_COMMANDS)}) or a LINK "
            f"with abcode {'/'.join(FILE_ABEND_CODES)} and no resp2 (register X70: no other command or code is sourced)"
        )
    nth = "*" if f.get("nth", 1) == "*" else int(f.get("nth", 1))
    name = next((f[k] for k in _FAULT_NAME if f.get(k)), None)
    if not name:
        raise ec.Unsupported(f"{where} names no {'/'.join(_FAULT_NAME)}")
    return f"{cmd} {name} {nth} -1 0 {f['abcode']}"


# #6271 (register X71): the conditions a terminal or unit-of-work command may be planned with, per command, and the RESP2
# values IBM gives each (CICS TS 6.x, the "Conditions" of SEND MAP, RECEIVE MAP, RETURN, SYNCPOINT). () = IBM states no
# RESP2 (one is not planned); several values: the scenario names one. Every other condition IBM lists for these commands
# needs a device, partition, BMS paging, a remote system or a PLT stage no case models: refused by name (X71).
UI_FAULT_CONDITIONS: dict[str, dict[str, tuple[int, ...]]] = {
    "SEND-MAP": {"INVMPSZ": (), "TSIOERR": (), "INVREQ": (200,)},
    "RECEIVE-MAP": {"INVMPSZ": (), "INVREQ": ()},
    # SEND TEXT (IBM's Conditions of -send-text): TSIOERR; INVREQ RESP2 200 (the other INVREQ causes state no RESP2); LENGERR
    # (LENGTH out of range) names none. SEND CONTROL (same conditions minus LENGERR) is refused (X71)
    "SEND-TEXT": {"TSIOERR": (), "INVREQ": (200,), "LENGERR": ()},
    "RETURN": {"INVREQ": (1, 2, 4, 200), "LENGERR": (11, 26, 27)},
    "SYNCPOINT": {"INVREQ": (200,)},
    "ROLLBACK": {"INVREQ": (200,)},
    # #6271 (X72): DELAY -- EXPIRED (a TIME already past; no RESP2) and INVREQ RESP2 4 / 5 / 6 / 22 (hours / minutes / seconds /
    # milliseconds out of range). IBM's NORMAL RESP2 23 (cancelled by another task) needs a second task: refused (X72)
    "DELAY": {"EXPIRED": (), "INVREQ": (4, 5, 6, 22)},
}
UI_NAMELESS = ("RETURN", "SYNCPOINT", "ROLLBACK", "DELAY", "SEND-TEXT")


def _ui_fault_resp2(sc: dict[str, Any], f: dict[str, Any], cmd: str, resp2: int) -> int:
    """The RESP2 of a SEND MAP / RECEIVE MAP / RETURN / SYNCPOINT fault, or ec.Unsupported naming register X71."""
    where = f"scenario {sc['name']}: fault {f}"
    reg = "X72" if cmd == "DELAY" else "X71"
    ibm = UI_FAULT_CONDITIONS[cmd].get(f["resp"])
    if ibm is None:
        listed = "/".join(UI_FAULT_CONDITIONS[cmd])
        raise ec.Unsupported(
            f"{where}: {f['resp']} is not planned on {cmd}; planned: {listed} (register {reg}, refused)"
        )
    if not ibm:
        if resp2:
            raise ec.Unsupported(f"{where}: IBM states no RESP2 for {f['resp']} on {cmd} (register {reg}): name none")
        return 0
    if resp2 == 0 and len(ibm) == 1:
        return ibm[0]
    if resp2 not in ibm:
        raise ec.Unsupported(
            f"{where}: IBM's {f['resp']} on {cmd} has RESP2 {'/'.join(map(str, ibm))}: name one ({reg})"
        )
    return resp2


def fault_lines(sc: dict[str, Any]) -> list[str]:
    """A scenario's `faults` as both sides read them: `CMD NAME NTH RESP RESP2` (faults.cfg, CicsTask.withFaults) --
    NAME the file a READ names, or the program an INQUIRE PROGRAM names."""
    out = []
    for f in sc.get("faults") or []:
        cmd = f.get("cmd", "READ")
        if f.get("resp") == "ABEND":  # #6271 (register X70): the task abends instead of a condition
            out.append(_abend_fault_line(sc, f, cmd))
            continue
        if cmd == "SEND-CONTROL":  # #6271 (register X71): IBM lists its conditions, no burned program codes RESP on it
            raise ec.Unsupported(
                f"scenario {sc['name']}: fault {f}: SEND CONTROL is not planned: every burned caller codes it with no RESP "
                "and IBM does not describe the abend a failure would take, so no failure arm exists to reach (register X71, refused)"
            )
        if cmd == "LINK" and f.get("resp") in LINK_REFUSED_CONDITIONS:  # #4986 (register X43)
            raise ec.Unsupported(
                f"scenario {sc['name']}: fault {f}: LINK {f['resp']} is IBM-documented but the region never raises it "
                "and no abend code is sourced for it (register X43, refused)"
            )
        refused_file = (
            cmd in FILE_FAULT_COMMANDS and f.get("resp") in FILE_FAULT_REFUSED
        )  # named in X49, not just unknown
        if (cmd not in FAULT_COMMANDS and cmd != TD_READ_COMMAND) or (
            f.get("resp") not in ec.CICS_RESP and not refused_file
        ):
            raise ec.Unsupported(
                f"scenario {sc['name']}: fault {f} ({'/'.join((*FAULT_COMMANDS, TD_READ_COMMAND))} with a ec.CICS_RESP condition)"
            )
        resp2 = int(f.get("resp2", 0))
        if cmd == TD_READ_COMMAND and (f["resp"] not in TD_READ_FAULTS or resp2):
            raise ec.Unsupported(
                f"scenario {sc['name']}: fault {f}: READQ TD is planned with {'/'.join(TD_READ_FAULTS)} and no RESP2 only "
                "(IBM states none; the other conditions follow from the queue, register X61, refused)"
            )
        if cmd in UI_FAULT_CONDITIONS:
            resp2 = _ui_fault_resp2(sc, f, cmd, resp2)
        elif cmd in FILE_FAULT_COMMANDS:
            resp2 = _file_fault_resp2(sc, f, cmd, resp2)
        elif f["resp"] in ("DUPKEY", "DUPREC"):  # #4623: the duplicate-key pair is a file condition only
            listed = "/".join(FILE_FAULT_CONDITIONS[f["resp"]])
            raise ec.Unsupported(f"scenario {sc['name']}: fault {f}: IBM documents {f['resp']} for {listed}, not {cmd}")
        if (cmd == "ENQ") != (
            f["resp"] == "ENQBUSY"
        ):  # #5089 (register X60): IBM lists ENQBUSY for ENQ only, and ENQ's others
            raise ec.Unsupported(  # (INVREQ, LENGERR) the program's own operands raise, not a plan
                f"scenario {sc['name']}: fault {f}: ENQ is planned with ENQBUSY only (IBM lists no other condition a region "
                "raises for it), and ENQBUSY is no other command's (register X60, refused)"
            )
        if cmd == "ENQ":
            if resp2:
                raise ec.Unsupported(
                    f"scenario {sc['name']}: fault {f}: IBM states no RESP2 for ENQBUSY (register X60): name none"
                )
            f = {**f, "resource": enq_fault_key(f.get("resource"))}
        nth = "*" if f.get("nth", 1) == "*" else int(f.get("nth", 1))
        name = "-" if cmd == "RETRIEVE" or cmd in UI_NAMELESS else next((f[k] for k in _FAULT_NAME if f.get(k)), None)
        if not name:
            raise ec.Unsupported(f"scenario {sc['name']}: fault {f} names no {'/'.join(_FAULT_NAME)}")
        out.append(f"{cmd} {name} {nth} {ec.CICS_RESP[f['resp']]} {resp2}")
    return [*out, *sc.get("sql_abend_plan", [])]  # #6271 (X73): the Db2 statements planned to abend AD2Z


# #5233 (register I5): the DL/I statuses a CICS scenario may plan on an EXEC DLI command -- the batch run's (#5857) on the
# database calls, and SCHD's TC (IBM: a PSB already scheduled, the one SCHD status the model derives). CHKP is a BMP call.
DLI_SCHD_STATUSES = ("TC",)


def dli_fault_lines(case: dict[str, Any], sc: dict[str, Any]) -> list[str]:
    """A scenario's `dli_faults` [{"op", "nth", "status"}] as ggdli.c reads them (`FUNCTION NTH STATUS`) and DetDli
    (`# DLI FUNCTION NTH STATUS`, minus the `# DLI `). A planned call is not performed: DIBSTAT answers the status."""
    import equivalence  # noqa: PLC0415 -- it imports this module

    plan = sc.get("dli_faults") or []
    if plan and not case.get("ims"):
        raise ec.Unsupported(f'scenario {sc.get("name")}: dli_faults in a case with no "ims" section', ["EXEC DLI"])
    ops = ("SCHD", *(o for o in equivalence.DLI_FAULT_FUNCTIONS if o != "CHKP"))
    out = []
    for f in plan:
        op, status, nth = f.get("op"), str(f.get("status")), f.get("nth", 1)
        ok = status in (DLI_SCHD_STATUSES if op == "SCHD" else equivalence.DLI_FAULT_STATUSES)
        if op not in ops or not ok or not (nth == "*" or (isinstance(nth, int) and nth >= 1)):
            raise ec.Unsupported(
                f"scenario {sc.get('name')}: dli_fault {f}: op {'/'.join(ops)} (SCHD: {'/'.join(DLI_SCHD_STATUSES)}; "
                f"else {'/'.join(equivalence.DLI_FAULT_STATUSES)}), nth >= 1 or *"
            )
        out.append(f"{op} {nth} {status}")
    return out
