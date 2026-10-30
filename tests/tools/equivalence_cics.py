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

import functools
import json
import re
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any
from collections.abc import Iterator

import cobol_coverage as cov  # #4023
import equivalence_common as common
import equivalence_cics_conditions as cics_conditions  # #5274: the conditions / handlers family
import equivalence_cics_containers as cics_containers  # #5274: the channels / containers family
import equivalence_cics_faults as cics_faults  # #5274: the fault-injection planner
import equivalence_cics_filecontrol as cics_filecontrol  # #5274: the file control family
import equivalence_cics_taskcontrol as cics_taskcontrol  # #5274: the task / interval control family
import equivalence_cics_tempstorage as cics_tempstorage  # #5274: the temporary storage family
import equivalence_cics_web as cics_web  # #5274: the web / HTTP / TCP/IP family
import equivalence_db2
import equivalence_ims  # #5278
import equivalence_inputs  # #3804
import equivalence_mq  # #4892
import equivalence_oracle
import equivalence_sql

from gitgalaxy.standards.cics.commands import COMMANDS as SPEC
from gitgalaxy.standards.cics.eib import EIB_FACTS, TASKN_MAX
from gitgalaxy.standards.cics.commands import whole_refusal
from gitgalaxy.standards.cics.commands.shared import BOTH_FORMS, NEEDS_ARGUMENT
from gitgalaxy.standards.cics.commands.terminal import MAP_OPTIONS
from gitgalaxy.standards.cics.model import GroupKind
from gitgalaxy.standards.cics.resp import DFHRESP as SPEC_DFHRESP
from gitgalaxy.tools.cobol_to_java.det.cvda import CVDA  # #4415: DFHVALUE(name), IBM's CVDA numbers

handler_labels = cics_conditions.handler_labels
check_child_faults = cics_faults.check_child_faults
fault_lines = cics_faults.fault_lines  # public names the tests and the runners reach through this module
dli_fault_lines = cics_faults.dli_fault_lines
enq_fault_key = cics_faults.enq_fault_key
FAULT_COMMANDS = cics_faults.FAULT_COMMANDS
UI_FAULT_CONDITIONS = cics_faults.UI_FAULT_CONDITIONS
FILE_FAULT_CONDITIONS = cics_faults.FILE_FAULT_CONDITIONS
LINK_REFUSED_CONDITIONS = cics_faults.LINK_REFUSED_CONDITIONS
ts_seed = cics_tempstorage.ts_seed  # public names the tests and the compare step reach through this module
java_ts_as_compared = cics_tempstorage.java_ts_as_compared
java_start_as_compared = cics_taskcontrol.java_start_as_compared
java_retrieve_as_compared = cics_taskcontrol.java_retrieve_as_compared
_cobol_retrieve = cics_taskcontrol._cobol_retrieve  # (the unit test reads it through this module)
http_peers = cics_web.http_peers  # public names the tests and the runners reach through this module
http_peers_cfg = cics_web.http_peers_cfg
http_request = cics_web.http_request
http_request_cfg = cics_web.http_request_cfg
tcpip = cics_web.tcpip
tcpip_cfg = cics_web.tcpip_cfg
_cobol_web = cics_web._cobol_web  # (the unit tests read the event readers through this module)
_cobol_web_open = cics_web._cobol_web_open
_cobol_web_send = cics_web._cobol_web_send
_cobol_web_header = cics_web._cobol_web_header
STUB = common.CASES / "cics"
LE_MODELS = common.CASES / "le"  # Language Environment service models (CEEDAYS) a CALLed subprogram may use

# The documented CICS response codes (DFHRESP) the translator replaces by number: the CICS command spec's
# (gitgalaxy/standards/cics, #4270 spec PR 3), the det translator's own table.
DFHRESP: dict[str, int] = dict(SPEC_DFHRESP)

_EXEC = re.compile(r"\bEXEC\s+(?:CICS|DLI)\b", re.I)
_DLI_TAG = "\0DLI "  # (#5278) an EXEC DLI block's body, as _exec_blocks yields it
_END_EXEC = re.compile(r"\bEND-EXEC\b", re.I)
_DFHRESP = re.compile(r"\bDFHRESP\s*\(\s*([A-Z0-9]+)\s*\)", re.I)
_DFHVALUE = re.compile(r"\bDFHVALUE\s*\(\s*([A-Z0-9]+)\s*\)", re.I)  # #4415: a CVDA, the number IBM gives it
_AREA_B = " " * 11  # columns 1-11: sequence area, indicator, Area A


class Unsupported(Exception):
    """A CICS command, or option, the harness does not model yet. `features` names each one
    (`LINK`, `READQ TS`, `HANDLE CONDITION`, `READ GENERIC`, ...) so a caller can count them
    (#3989: the CICS crucible runner reports cells as `unsupported: <feature>`)."""

    def __init__(self, message: str, features: list[str] | None = None) -> None:
        super().__init__(message)
        self.features = list(features) if features else [message]


# ---- #4270 spec PR 3: options, refusals and their reasons from the CICS command spec -------------------------------
# A command's options are its spec entry's (gitgalaxy/standards/cics), the det translator's own: the stub refuses
# every option the translator refuses, by name and with the same message (SPEC[key].refusal_message) -- an allow-list,
# so an option in neither of the entry's tables (a typo, an IBM option nobody modelled) is refused, never ignored.
# On top of that, the few options the translator honours and the stub runtime does not model yet are refused as the
# stub's own (_stub_only). The feature names (`READ GENERIC`, `START SYSID`, ...) are the harness's, as before.


def _check_spec(key: str, opts: dict[str, str | None], words: tuple[str, ...], features: Any = None) -> None:
    """Refuse the options of `opts` (the verb words `words` aside) that command `key`'s spec entry does not honour,
    as the translator does. `features(bad)` names them (default: `KEY OPTION` each)."""
    bad = [o for o in opts if o not in words and o not in SPEC[key].options]
    if bad:
        raise Unsupported(SPEC[key].refusal_message(bad), features(bad) if features else [f"{key} {o}" for o in bad])


def _rule(key: str, kind: GroupKind, option: str, *parts: str) -> str:
    """The message of command `key`'s option rule (its spec Group), as the translator words it."""
    return SPEC[key].group(kind, option).msg.format(*parts)


def _one_of(key: str, opts: dict[str, str | None], name: str, alt: str) -> str | None:
    """LENGTH / FLENGTH (MAXLENGTH / MAXFLENGTH): the argument of either form, None when neither is given; both
    refused, as the translator refuses them (its _one_of)."""
    if name in opts and alt in opts:
        raise Unsupported(BOTH_FORMS.format(name, alt), [key])
    return opts.get(name) or opts.get(alt)


def _stub_only(feature: str) -> Unsupported:
    """An option the det translator honours and the stub runtime (tests/equivalence/cics/ggcics.c) does not model."""
    return Unsupported(f"{feature}: not modelled by the stub runtime", [feature])


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


def _map_abend(labels: list[str] | None) -> list[str]:
    """#4270 (X31): after SEND MAP / RECEIVE MAP, the ABM0 abend the stub raises for a map its mapset does not hold
    (GGCSMAP / GGCRECV): the HANDLE ABEND exit's label, or leave the program (GG-GOTO -1); else it falls through."""
    return _transfer(labels) + ["IF GG-GOTO < 0", "    GOBACK", "END-IF"]


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


def urimaps(case: dict[str, Any], sc: dict[str, Any]) -> list[list[str]] | None:
    """#4270 zECS (X32): the URIMAP definitions installed in the region, in the order INQUIRE URIMAP's browse returns
    them -- the scenario's "urimaps", else the case's: [[NAME, TRANSACTION ("" for none), PATH], ...], stated on both
    sides as the cics-crucible runner states a case CSD's (the stub's $GGCICS_URIMAPS, CicsTask.withUrimaps).
    Unstated, None: both runtimes refuse INQUIRE URIMAP by name."""
    defs = sc.get("urimaps", case.get("urimaps"))
    if defs is None:
        return None
    ok = isinstance(defs, list) and all(
        isinstance(d, list) and len(d) == 3 and all(isinstance(x, str) for x in d)
        and d[0] and d[2] and not any(c.isspace() for x in d for c in x) and len(d[0]) <= 8 and len(d[1]) <= 4
        for d in defs)  # fmt: skip
    if not ok:
        raise Unsupported(f'scenario {sc.get("name")}: "urimaps" lists [NAME (1-8), TRANSACTION (0-4), PATH] '
                          "without blanks", ["INQUIRE URIMAP"])  # fmt: skip
    return defs


def mapsets_env(case: dict[str, Any]) -> str:
    """#4270 (X31) / #5076: the case's "maps" ({MAP: {"mapset": MAPSET}}, as a cics-crucible case states them) as the stub's
    $GGCICS_MAPSETS (`MAPSET=MAP,MAP;MAPSET=MAP`), so a SEND MAP / RECEIVE MAP for a map its mapset does not hold abends
    ABM0 on the COBOL side as the det port's translation already does (BNK1CCS's CLEAR: SEND MAP('BNK1CCM'), the
    mapset's name). Unstated, a mapset is not checked."""
    held: dict[str, list[str]] = {}
    for m, spec in sorted(case["maps"].items()):
        held.setdefault(spec["mapset"], []).append(m)
    return ";".join(f"{ms}={','.join(maps)}" for ms, maps in sorted(held.items()))


def doctemplates(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, str] | None:
    """#4769 zECS (X33): the DOCTEMPLATE definitions installed in the region -- the scenario's "doctemplates", else the
    case's: {NAME (1-48, no blanks): the text the template yields}, stated on both sides (the stub's
    $GGCICS_DOCTEMPLATES, CicsTask.withDoctemplates). A case states each template's text as the document holds it
    (the definition's APPENDCRLF / TYPE applied). Unstated, None: both runtimes refuse a DOCUMENT CREATE TEMPLATE."""
    defs = sc.get("doctemplates", case.get("doctemplates"))
    if defs is None:
        return None
    ok = isinstance(defs, dict) and all(
        isinstance(n, str) and isinstance(t, str) and 0 < len(n) <= 48 and not any(c.isspace() for c in n)
        for n, t in defs.items())  # fmt: skip
    if not ok:
        raise Unsupported(f'scenario {sc.get("name")}: "doctemplates" maps a template name (1-48, no blanks) to its '
                          "text", ["DOCUMENT CREATE"])  # fmt: skip
    return defs


_SCENARIO_CLOCK = re.compile(r"\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\.\d\d")


def scenario_clock(case: dict[str, Any], sc: dict[str, Any]) -> str:
    """#4622: the task's clock ("2026/10/01 10:30:15.00", COB_CURRENT_DATE's form) -- the scenario's "clock", else the
    case's: a program that reads FUNCTION CURRENT-DATE (CORPT00C's month wrap in December) needs a date the case's
    one never is. Stated on both sides: the COBOL task's COB_CURRENT_DATE / $GGCICS_NOW, the Java task's withClock."""
    clock = sc.get("clock", case["clock"])
    if not isinstance(clock, str) or not _SCENARIO_CLOCK.fullmatch(clock):
        raise Unsupported(f'scenario {sc.get("name")}: "clock" is "YYYY/MM/DD hh:mm:ss.cc" (got {clock!r})')
    return clock


_TOD = re.compile(r"[0-9A-Fa-f]{32}")


def scenario_tod(case: dict[str, Any], sc: dict[str, Any]) -> str | None:
    """#5945 (register X47): the 16 bytes CALL ZUIDSTCK returns, 32 hex digits -- the scenario's "tod", else the case's, else
    unstated (None: both runtimes then refuse the CALL). A fact the run states on both sides ($GGC_ZUIDSTCK_TOD for the
    stub task, Zuidstck.state for the port), never the clock."""
    tod = sc.get("tod", case.get("tod"))
    if tod is not None and not (isinstance(tod, str) and _TOD.fullmatch(tod)):
        raise Unsupported(f'scenario {sc.get("name")}: "tod" is 32 hexadecimal digits (got {tod!r})')
    return tod


def case_states_tod(case: dict[str, Any]) -> bool:
    return "tod" in case or any("tod" in sc for sc in case["scenarios"])


def clock_iso(case: dict[str, Any], sc: dict[str, Any] | None = None) -> str:
    """#4270: the case's clock ("2026/10/01 10:30:15.00") as the stub's $GGCICS_NOW (2026-10-01T10:30:15): the
    moment a START's expiry and a CANCEL's "not expired" count from, as CicsTask counts them from the same clock.
    #4622: the scenario's, when it states one."""
    day, _, time = (scenario_clock(case, sc) if sc is not None else case["clock"]).partition(" ")
    return day.replace("/", "-") + "T" + time.split(".")[0]


def task_number(case: dict[str, Any], sc: dict[str, Any]) -> int:
    """#4270: EIBTASKN, the task's number -- a fact of the run the harness states on both sides ($GGCICS_TASKN,
    CicsTask.withTaskNumber; oracle_assumptions.md X21): the scenario's "taskn", else the case's, else the spec's
    default (0, the value C12's RANDOM seed assumes). Never z/OS's: CICS assigns it."""
    n = sc.get("taskn", case.get("taskn", int(EIB_FACTS["EIBTASKN"].region_default or 0)))
    if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= TASKN_MAX:
        raise Unsupported(f'scenario {sc.get("name")}: "taskn" {n!r} is not a task number (0 to {TASKN_MAX})')
    return n


UCTRANST_NAMES = ("UCTRAN", "NOUCTRAN", "TRANIDONLY")
ORIGIN_KEYS = ("applid", "userid", "facilname", "networkid", "faciltype")


def terminal_facts(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any]:
    """#4270 (CBSA's BMS front ends): the task's terminal, stated on both sides as the cics-crucible runner states it --
    "termid" (EIBTRMID and the principal facility: $EIBIN, $GGCICS_FACILITY and terminals.cfg / CicsTask.withTermid;
    RETURN IMMEDIATE, register X27), "uctranst" (its TYPETERM's UCTRAN as INQUIRE TERMINAL UCTRANST answers it:
    $GGCICS_UCTRANST / withUctranst, X26) and "origin" (the task's origin data, {applid, userid, facilname,
    networkid, faciltype}: $GGCICS_ORIGIN / withOrigin, X29), plus "userid" (ASSIGN USERID: $GGCICS_USERID /
    withUserid) and "screen" ([rows, columns], ASSIGN SCRNHT / SCRNWD: $GGCICS_SCREEN / withScreen; needs a termid;
    X19), each present only when stated (#5126). The scenario's, else the case's; unstated, None, and
    the commands that read them are refused by both runtimes, as before."""
    out: dict[str, Any] = {k: sc.get(k, case.get(k)) for k in ("termid", "uctranst", "origin")}
    t = out["termid"]
    if t is not None and (not isinstance(t, str) or not 1 <= len(t) <= 4 or not t.strip() or "," in t or " " in t):
        raise Unsupported(f'scenario {sc.get("name")}: "termid" {t!r} is not a terminal name (1 to 4 characters)')
    if out["uctranst"] is not None and (t is None or out["uctranst"] not in UCTRANST_NAMES):
        raise Unsupported(f'scenario {sc.get("name")}: "uctranst" is one of {", ".join(UCTRANST_NAMES)}, of a '
                          'stated "termid"')  # fmt: skip
    for k in ("userid", "screen"):  # #5126: only when stated (an always-present empty key breaks exact-equality tests)
        if sc.get(k, case.get(k)) is not None:
            out[k] = sc.get(k, case.get(k))
    u = out.get("userid")
    if u is not None and (not isinstance(u, str) or not 1 <= len(u) <= 8 or not u.strip() or "," in u or " " in u):
        raise Unsupported(f'scenario {sc.get("name")}: "userid" {u!r} is not a user ID (1 to 8 characters)')
    scr = out.get("screen")
    if scr is not None and (not isinstance(scr, list) or len(scr) != 2
                            or not all(type(n) is int and n > 0 for n in scr) or t is None):  # fmt: skip
        raise Unsupported(
            f'scenario {sc.get("name")}: "screen" is [rows, columns], positive ints, of a stated "termid"'
        )
    o = out["origin"]
    if o is not None and (not isinstance(o, dict) or sorted(o) != sorted(ORIGIN_KEYS)
                          or any(not isinstance(o[k], str) or "," in o[k] or not o[k] for k in ORIGIN_KEYS)):  # fmt: skip
        raise Unsupported(f'scenario {sc.get("name")}: "origin" is {{{", ".join(ORIGIN_KEYS)}}}, each a name')
    return out


def task_facts(case: dict[str, Any], sc: dict[str, Any]) -> tuple[str | None, str | None]:
    """#4270 (GenApp LGICVS01, a terminal transaction): how the task was started and what the operator typed -- facts
    of the run stated on both sides as the cics-crucible runner states them (ASSIGN STARTCODE: $GGCICS_STARTCODE /
    CicsTask.withStartcode, oracle_assumptions.md X19; an unformatted RECEIVE's input: terminal.in /
    CicsTask.withTerminalInput). The scenario's "startcode" / "terminal", else the case's; unstated, None (the stub
    and CicsTask refuse ASSIGN STARTCODE, and a RECEIVE gets nothing)."""
    code = sc.get("startcode", case.get("startcode"))
    values = next(f for f in SPEC["ASSIGN"].facts if f.name == "startcode").values
    if code is not None and code not in values:
        raise Unsupported(f'scenario {sc.get("name")}: "startcode" {code!r} is not one of {", ".join(values)}')
    text = sc.get("terminal", case.get("terminal"))
    if text is not None and not isinstance(text, str):
        raise Unsupported(f'scenario {sc.get("name")}: "terminal" is the text typed, a string')
    return code, text


def _region_page() -> str:
    """The JDK name of the region's default code page (CCSID 037), the det port's DetCics.region default (#4528)."""
    from gitgalaxy.tools.cobol_to_java.det.cics import region_page

    return region_page(None)


def _past_from(length: str | None, area: str | None, what: str) -> list[str]:
    """A PUT / GET CONTAINER whose LENGTH runs past its item: CICS takes the bytes that follow the item in storage,
    which GnuCOBOL lays out unlike IBM's compiler -- the run stops (98, "not modelled") rather than write bytes no
    oracle here can vouch for. (A WRITEQ past FROM is padded instead, `_write_from`, X6.)"""
    if not length or not area or _literal(area):
        return []
    return [f"IF GG-LEN > LENGTH OF {area}",
            f"    DISPLAY '{what} LENGTH > FROM: not modelled'",
            "    MOVE 98 TO RETURN-CODE", "    STOP RUN", "END-IF"]  # fmt: skip


def _move_to_padq(area: str) -> list[str]:
    """The MOVE of a FROM item into GG-PADQ, on two lines when a long item name would push it past column 72."""
    one = f"    MOVE {area} TO GG-PADQ(1:LENGTH OF {area})"
    return (
        [one] if len(_AREA_B) + len(one) + 4 <= 72 else [f"    MOVE {area}", f"        TO GG-PADQ(1:LENGTH OF {area})"]
    )


# X6: the stub's line on the padded path (_write_from), so a proof can name X6 for the task that ran it; outputs()
# takes it out of the task's DISPLAY log (the Java side prints no such line)
X6_PADDED_SAID = "GG-X6 PADDED "


def _write_from(length: str | None, area: str, what: str, call: list[str]) -> list[str]:
    """X6 (ASSUMED, owner 2026-10-21): a WRITEQ whose LENGTH runs past its FROM item writes FROM's bytes then SPACES to
    LENGTH. IBM takes the bytes that follow the item in storage (undefined); GnuCOBOL's layout differs, so the fill is
    the one both sides agree on (DetCics.padded). The record goes through GG-PADQ (a record is at most 32767 bytes);
    a stated LENGTH over that is refused at run time, as before."""
    if not length or _literal(area):
        return call
    return [f"IF GG-LEN > LENGTH OF {area}",
            "    IF GG-LEN > LENGTH OF GG-PADQ",
            f"        DISPLAY '{what} LENGTH > FROM: not modelled'",
            "        MOVE 98 TO RETURN-CODE", "        STOP RUN", "    END-IF",
            f"    DISPLAY '{X6_PADDED_SAID}{what}'",
            "    MOVE SPACES TO GG-PADQ",
            *_move_to_padq(area),
            *["    " + ln for ln in call[:-1] + [call[-1].replace(f"BY REFERENCE {area}", "BY REFERENCE GG-PADQ")]],
            "ELSE", *["    " + ln for ln in call], "END-IF"]  # fmt: skip


def _td_command(verb: str, opts: dict[str, str | None], labels: list[str] | None = None) -> list[str]:
    """#5079 (X57): READQ TD / DELETEQ TD -> GGCRDTD / GGCDLTD (the queue in GG-QNAME). READQ's LENGTH is in-out, as READ's:
    in, the most INTO takes; out, the record's length, on NORMAL and LENGERR."""
    feature = f"{verb} TD"
    _check_spec(feature, opts, (verb, "TD"), lambda bad: [f"{feature} {bad[0]}"])
    queue = opts.get("QUEUE")
    if not queue:
        raise Unsupported(f"{feature} without QUEUE", [feature])
    lines = [f"MOVE {queue} TO GG-QNAME"]
    if verb == "DELETEQ":
        return lines + _call("GGCDLTD", []) + _resp(opts, True, labels)
    into, length = opts.get("INTO"), opts.get("LENGTH")
    if (
        "NOSUSPEND" in opts
    ):  # #5168 (X61): the stub reads (and clears) it: a planned QBUSY needs NOSUSPEND, else IBM suspends
        lines.append("MOVE 'TDNOSUSPEND' TO GG-FLAGS")
    if opts.get(
        "SET"
    ):  # #5168 (X61): SET(pointer) LENGTH(data-area) -> GGCRDTS, the record as a new block (X58's lane)
        if into:
            raise Unsupported(_rule(feature, "at_most_one", "INTO"), [feature])
        if not length or re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()):
            raise Unsupported(_rule(feature, "requires", "SET"), [feature])
        return (lines + _call("GGCRDTS", [f"BY REFERENCE {_pointer(feature, opts['SET'])}"])
                + ["IF GG-RESP = 0", f"    MOVE GG-LEN TO {length}", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
    if not into:
        raise Unsupported(f"{feature} without INTO", [feature])
    settable = bool(length) and re.fullmatch(r"(?is)\d+|LENGTH\s+OF\s+.+", length.strip()) is None
    after = ["IF GG-RESP = 0 OR GG-RESP = 22", f"    MOVE GG-LEN TO {length}", "END-IF"] if settable else []
    lines.append(f"MOVE {length or f'LENGTH OF {into}'} TO GG-LEN")
    return (lines + _call("GGCRDTD", [f"BY REFERENCE {into}", f"BY VALUE LENGTH OF {into}"])
            + after + _resp(opts, True, labels))  # fmt: skip


def _pointer(key: str, text: str | None) -> str:
    """#4771 (X47): the USAGE POINTER item an option names: a plain data name (GnuCOBOL's own compile refuses a name that is no
    pointer; a subscripted or qualified one is refused here, as the translator refuses it)."""
    if not text or re.fullmatch(r"(?is)\s*[A-Z][A-Z0-9-]*\s*", text) is None:
        raise Unsupported(f"{key}: a pointer is a plain data name: not modelled", [key])
    return text.strip()


def _getmain(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4771 (register X47): GETMAIN SET(ptr) FLENGTH / LENGTH INITIMG(area) -> GGCGETM (length in GG-NUM, GG-FLAGS SHORT for the
    LENGTH form; the stub sets the pointer, to zero under LENGERR). The option rules as the det translator's."""
    key = "GETMAIN"
    _check_spec(key, opts, ("GETMAIN",), lambda bad: [f"{key} {o}" for o in bad])
    if not opts.get("SET"):
        raise Unsupported(_rule(key, "required", "SET"), [key])
    if ("FLENGTH" in opts) == ("LENGTH" in opts):
        raise Unsupported(_rule(key, "one_of", "FLENGTH"), [key])
    if not opts.get("INITIMG"):
        raise Unsupported(_rule(key, "required", "INITIMG"), [key])
    if "USERDATAKEY" in opts and "CICSDATAKEY" in opts:
        raise Unsupported(_rule(key, "at_most_one", "USERDATAKEY"), [key])
    form = "FLENGTH" if "FLENGTH" in opts else "LENGTH"
    if not opts.get(form):
        raise Unsupported(NEEDS_ARGUMENT, [key])
    if _literal(opts["INITIMG"]) is not None or re.fullmatch(r"(?is)\s*[A-Z][A-Z0-9-]*\s*", opts["INITIMG"]) is None:
        raise Unsupported("GETMAIN INITIMG as a literal: a data area is the COBOL form", [key])
    img = opts["INITIMG"].strip()
    lines = [
        f"MOVE {opts[form]} TO GG-NUM",
        "MOVE 'SHORT' TO GG-FLAGS" if form == "LENGTH" else "MOVE SPACES TO GG-FLAGS",
    ]
    args = [f"BY REFERENCE {_pointer(key, opts['SET'])}", f"BY REFERENCE {img}", f"BY VALUE LENGTH OF {img}"]
    return lines + _call("GGCGETM", args) + _resp(opts, True, labels)


def _address(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#5079 (register X59): ADDRESS EIB(ptr) / COMMAREA(ptr) -> GGCADDR, which sets the pointer to the address of the EIB /
    the program's DFHCOMMAREA (NORMAL: the command has no condition). A task with no COMMAREA (EIBCALEN 0) is refused by the
    stub: IBM's X'FF000000' is no COBOL NULL, and a LINKAGE item that was not passed is no area to name, so the area given
    then is the pointer itself. The option rules as the det translator's."""
    key = "ADDRESS"
    _check_spec(key, opts, ("ADDRESS",), lambda bad: [f"{key} {o}" for o in bad])
    if not (opts.get("EIB") or opts.get("COMMAREA")):
        raise Unsupported("ADDRESS without EIB or COMMAREA: the pointer to set", [key])
    lines: list[str] = []
    if opts.get("EIB"):
        lines += ["MOVE SPACES TO GG-FLAGS"]
        lines += _call("GGCADDR", [f"BY REFERENCE {_pointer(key, opts['EIB'])}", "BY REFERENCE DFHEIBLK"])
    if opts.get("COMMAREA"):
        ptr = _pointer(key, opts["COMMAREA"])
        lines += ["MOVE EIBCALEN TO GG-NUM", "MOVE 'COMMAREA' TO GG-FLAGS", "IF EIBCALEN = 0"]
        lines += [f"    {ln}" for ln in _call("GGCADDR", [f"BY REFERENCE {ptr}", f"BY REFERENCE {ptr}"])]
        lines += ["ELSE"]
        lines += [f"    {ln}" for ln in _call("GGCADDR", [f"BY REFERENCE {ptr}", "BY REFERENCE DFHCOMMAREA"])]
        lines += ["END-IF"]
    return lines + _resp(opts, False, labels)


def _freemain(opts: dict[str, str | None], labels: list[str] | None) -> list[str]:
    """#4771 (register X47): FREEMAIN DATAPOINTER(ptr) -> GGCFREM, DATA(record) -> GGCFRED (#6876); INVREQ RESP2 1 for an address GETMAIN did not return."""
    key = "FREEMAIN"
    _check_spec(key, opts, ("FREEMAIN",), lambda bad: [f"{key} {o}" for o in bad])
    if opts.get("DATA") and opts.get("DATAPOINTER"):
        raise Unsupported(_rule(key, "at_most_one", "DATAPOINTER"), [key])
    if opts.get("DATA"):  # #6876: the 01 LINKAGE record's address is the storage; GnuCOBOL passes it BY REFERENCE
        if re.fullmatch(r"(?is)\s*[A-Z][A-Z0-9-]*\s*", opts["DATA"]) is None:
            raise Unsupported("FREEMAIN DATA: a data area is the COBOL form", [key])
        return _call("GGCFRED", [f"BY REFERENCE {opts['DATA'].strip()}"]) + _resp(opts, True, labels)
    if not opts.get("DATAPOINTER"):
        raise Unsupported(_rule(key, "one_of", "DATAPOINTER"), [key])
    return _call("GGCFREM", [f"BY REFERENCE {_pointer(key, opts['DATAPOINTER'])}"]) + _resp(opts, True, labels)


# #5126 (X64): the file control commands set EIBDS, "the symbolic identifier of the last data set referred to in a file
# control request" (IBM, EIB fields); every other EIB resource field stays unmodelled.
EIBDS_VERBS = frozenset({"READ", "READNEXT", "READPREV", "RESETBR", "STARTBR", "ENDBR", "WRITE", "REWRITE", "DELETE",
                         "UNLOCK"})  # fmt: skip


def translate_command(
    body: str,
    labels: list[str] | None = None,
    handle_aid: bool = False,
    eibds: bool = False,
    eibrcode: bool = False,
) -> list[str]:
    """One EXEC CICS body -> the COBOL statements that replace it. `eibds`: the program reads EIBDS, so a file control
    command leads with `MOVE <file> TO EIBDS` (#5126, X64) -- set before the command runs, so a failed request leaves
    its file named, as the request "referred to" it. `eibrcode`: the program reads EIBRCODE, so a file control command
    calls GGCRCOD right after the EIB's RESP fields are set (before a condition's GO TO), which puts the `rcode` a
    scenario's planned condition states into EIBRCODE (#5126, X64). See _translate_command for the rest."""
    lines = _translate_command(body, labels, handle_aid)
    if not (eibds or eibrcode):
        return lines
    pairs = _options(body)
    opts = dict(pairs)
    file = opts.get("FILE") or opts.get("DATASET")
    if not (pairs and pairs[0][0] in EIBDS_VERBS and file):
        return lines
    if eibrcode and "MOVE GG-RESP2 TO EIBRESP2" in lines:
        at = lines.index("MOVE GG-RESP2 TO EIBRESP2") + 1
        lines = [*lines[:at], "CALL 'GGCRCOD' USING GG-CICS EIBRCODE", *lines[at:]]
    return [f"MOVE {file} TO EIBDS", *lines] if eibds else lines


def _reads_eib_word(word: str, lines: list[str]) -> bool:
    """Does the source name an EIB field outside a comment line and a literal -- a whole word, not the front of a
    hyphenated user name (EIBDS-X)?"""
    pat = re.compile(rf"(?<![A-Z0-9-]){word}(?![A-Z0-9-])")
    code = (ln[7:72].upper() for ln in lines if len(ln) > 6 and ln[6] not in "*/")
    return any(pat.search(re.sub(r"'[^']*'|\"[^\"]*\"", "''", ln)) for ln in code)


def reads_eibds(lines: list[str]) -> bool:
    """#5126 (X64): does the source name EIBDS? (The det port's scan is `det.cics.reads_eibds`: the same words, over
    statements.)"""
    return _reads_eib_word("EIBDS", lines)


def reads_eibrcode(lines: list[str]) -> bool:
    """#5126 (X64): does the source name EIBRCODE (the same whole-word rule as EIBDS)?"""
    return _reads_eib_word("EIBRCODE", lines)


def _translate_command(body: str, labels: list[str] | None = None, handle_aid: bool = False) -> list[str]:
    """One EXEC CICS body -> the COBOL statements that replace it. `labels` are the program's HANDLE
    labels (handler_labels), which a condition or abend exit GOes TO (#4003); by default, this
    command's own. `handle_aid`: the program issues HANDLE AID, so its input commands consult it (#4007)."""
    pairs = _options(body)
    if not pairs:
        raise Unsupported("empty EXEC CICS")
    labels = cics_conditions.handler_labels([body]) if labels is None else labels
    opts = dict(pairs)
    verb = pairs[0][0]
    flags = [n for n, v in pairs[1:] if v is None and n not in ("NOHANDLE",)]

    def name(operand: str | None, into: str) -> str:
        return f"MOVE {operand} TO {into}" if operand else f"MOVE SPACES TO {into}"

    if verb in cics_filecontrol.FILE_VERBS:  # #5274: the file control family
        lines = cics_filecontrol.file_command(verb, opts, labels)
        if lines is not None:
            if (
                labels and verb != "UNLOCK"
            ):  # #6271 (X70): a planned abend went to the HANDLE ABEND exit, or ends the task
                return ["MOVE 0 TO GG-GOTO", *lines, *_map_abend(labels)]
            return lines
    if verb == "GGSQLAB":  # #6271 (X73): the harness's own marker after a Db2 statement planned to abend AD2Z
        return ["MOVE 0 TO GG-GOTO", f"MOVE {opts['NAME']} TO GG-FLAGS", *_call("GGCSQLAB", []), *_map_abend(labels)]
    if verb == "DELAY":  # #4950: the wait at which RUN children are dispatched (GGCDLAY)
        return cics_taskcontrol._delay(opts, labels)
    if verb == "POST":  # #5079 (X63): a timer-event control area
        return cics_taskcontrol._post(opts, labels)
    if verb == "WAIT" and "EVENT" in opts and opts["EVENT"] is None:
        return cics_taskcontrol._wait_event(opts, labels)
    if verb == "CONVERSE":
        return cics_taskcontrol._converse(opts, labels)
    if verb in ("ENQ", "DEQ"):
        # one task in the region: nothing else holds the resource (ENQ / DEQ NORMAL), and a task takes no time
        # (EIBTIME / ASKTIME stay as dispatched; oracle_assumptions.md X4)
        _check_spec(verb, opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        if verb == "ENQ":  # #5089: GGCENQ -- NORMAL, or the ENQBUSY a scenario plans (faults, name = the RESOURCE text)
            key = enq_fault_key(opts.get("RESOURCE"))
            flag = "MOVE 'NOSUSPEND' TO GG-NAME1" if "NOSUSPEND" in opts else "MOVE SPACES TO GG-NAME1"
            given = ("L" if opts.get("LENGTH") else "") + ("M" if opts.get("MAXLIFETIME") else "")  # X60: GG-NAME2
            ops = [f"MOVE {opts['LENGTH']} TO GG-LEN"] if opts.get("LENGTH") else []
            ops += [f"MOVE {opts['MAXLIFETIME']} TO GG-NUM"] if opts.get("MAXLIFETIME") else []
            ops.append(f"MOVE '{given}' TO GG-NAME2" if given else "MOVE SPACES TO GG-NAME2")
            return [f"MOVE '{key}' TO GG-FLAGS", flag, *ops] + _call("GGCENQ", []) + _resp(opts, True, labels)
        return ["MOVE 0 TO GG-RESP", "MOVE 0 TO GG-RESP2"] + _resp(opts, False, labels)
    if verb == "GET" and ("COUNTER" in opts or "DCOUNTER" in opts):  # a named counter (IBM CICS TS, GET COUNTER)
        _check_spec("GET COUNTER", opts, (verb,), lambda bad: ["GET COUNTER"])
        if not opts.get("VALUE"):
            raise Unsupported(_rule("GET COUNTER", "required", "VALUE"), ["GET COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise Unsupported(_rule("GET COUNTER", "one_of", "COUNTER"), ["GET COUNTER"])
        for o in ("VALUE", "INCREMENT", "COMPAREMIN", "COMPAREMAX"):
            # (#5039: a bound is read from its bytes, so a number written in place is no area either)
            if opts.get(o) and (_literal(opts[o]) or (o.startswith("COMPARE") and re.fullmatch(r"[+-]?\d+", opts[o]))):
                kind = "DCOUNTER" if "DCOUNTER" in opts else "COUNTER"
                raise Unsupported(f"{kind} {o} as a literal: a data area is the COBOL form", ["GET COUNTER"])
        full = "COUNTER" in opts  # #5039 (X50): the fullword form
        inc = opts.get("INCREMENT") or "GG-NAME2"
        head = ([name(opts.get("COUNTER") or opts["DCOUNTER"], "GG-QNAME"), name(opts.get("POOL") or "' '", "GG-NAME1")]
                + ([] if opts.get("INCREMENT") else ["MOVE X'0000000000000001' TO GG-NAME2"]))  # fmt: skip
        areas = [f"BY REFERENCE {opts['VALUE']}", f"BY VALUE LENGTH OF {opts['VALUE']}",
                 f"BY REFERENCE {inc}", f"BY VALUE LENGTH OF {inc}", f"BY VALUE {1 if 'WRAP' in opts else 0}"]  # fmt: skip
        if "REDUCE" in opts or opts.get("COMPAREMIN") or opts.get("COMPAREMAX"):
            # #5039 (X53): REDUCE and the bounds (an area each, length 0: not given)
            areas.append(f"BY VALUE {1 if 'REDUCE' in opts else 0}")
            for o in ("COMPAREMIN", "COMPAREMAX"):
                v = opts.get(o)
                areas += (
                    [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
                )
            return head + _call("GGCGCNX" if full else "GGCGDCX", areas) + _resp(opts, True, labels)
        # #5039 (X50): GET COUNTER fullword form with INCREMENT and WRAP; #4767 (X30): GET DCOUNTER, the doubleword form: the stub
        # writes VALUE (8 bytes) and reads INCREMENT (an area; 1 when not given, through GG-NAME2's 8 bytes); #4770 (X45): WRAP
        # acts at DEFINE DCOUNTER's limits
        return head + _call("GGCGCNT" if full else "GGCGDCN", areas) + _resp(opts, True, labels)
    if verb in ("REWIND", "UPDATE") and {"COUNTER", "DCOUNTER"} & set(opts):  # #5039 (X53): REWIND / UPDATE COUNTER
        _check_spec(f"{verb} COUNTER", opts, (verb,), lambda bad: [f"{verb} COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise Unsupported(_rule(f"{verb} COUNTER", "one_of", "COUNTER"), [f"{verb} COUNTER"])
        head = [name(opts.get("COUNTER") or opts["DCOUNTER"], "GG-QNAME"), name(opts.get("POOL") or "' '", "GG-NAME1")]
        full = "COUNTER" in opts
        o = "INCREMENT" if verb == "REWIND" else "VALUE"
        v = opts.get(o)
        if verb == "UPDATE" and not v:
            raise Unsupported(_rule("UPDATE COUNTER", "required", "VALUE"), ["UPDATE COUNTER"])
        if v and (_literal(v) or re.fullmatch(r"[+-]?\d+", v)):
            raise Unsupported(
                f"{'COUNTER' if full else 'DCOUNTER'} {o} as a literal: a data area is the COBOL form",
                [f"{verb} COUNTER"],
            )
        fn = {"REWIND": ("GGCRCNT", "GGCRDCN"), "UPDATE": ("GGCUCNT", "GGCUDCN")}[verb][0 if full else 1]
        areas = [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
        return head + _call(fn, areas) + _resp(opts, True, labels)
    if verb == "QUERY" and (
        "COUNTER" in opts or "DCOUNTER" in opts
    ):  # #4415 slice 2 (X29): a named counter's value, unchanged
        _check_spec("QUERY COUNTER", opts, (verb,), lambda bad: ["QUERY COUNTER"])
        if not opts.get("VALUE"):
            raise Unsupported(_rule("QUERY COUNTER", "required", "VALUE"), ["QUERY COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise Unsupported(_rule("QUERY COUNTER", "one_of", "COUNTER"), ["QUERY COUNTER"])
        if "DCOUNTER" in opts:  # #4770 (X45): value and limits, unsigned doublewords in 8-byte areas
            return ([name(opts["DCOUNTER"], "GG-QNAME"), name(opts.get("POOL") or "' '", "GG-NAME1")]
                    + _call("GGCQDCN", _dcounter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM")))
                    + _resp(opts, True, labels))  # fmt: skip
        return ([name(opts["COUNTER"], "GG-QNAME"), name(opts.get("POOL") or "' '", "GG-NAME1")]
                + _call("GGCQCNT", _counter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM"))[1])
                + _resp(opts, True, labels))  # fmt: skip
    if verb in ("DEFINE", "DELETE") and (
        {"COUNTER", "DCOUNTER"} & set(opts)
    ):  # #4270 (X30): DEFINE / DELETE COUNTER -> GGCDCNT / GGCXCNT
        _check_spec(f"{verb} COUNTER", opts, (verb,), lambda bad: [f"{verb} COUNTER"])
        if ("COUNTER" in opts) == ("DCOUNTER" in opts):
            raise Unsupported(_rule(f"{verb} COUNTER", "one_of", "COUNTER"), [f"{verb} COUNTER"])
        if verb == "DEFINE" and opts.get("MINIMUM") and not opts.get("VALUE"):
            why = next(
                g.msg for g in SPEC["DEFINE COUNTER"].groups if g.kind == "requires" and "VALUE" in (g.any_of or ())
            )
            raise Unsupported(why, ["DEFINE COUNTER"])
        head = [name(opts.get("COUNTER") or opts["DCOUNTER"], "GG-QNAME"), name(opts.get("POOL") or "' '", "GG-NAME1")]
        if verb == "DELETE":
            return head + _call("GGCXCNT", []) + _resp(opts, True, labels)
        if "DCOUNTER" in opts:  # #4770 (X45): VALUE / MINIMUM / MAXIMUM, each an 8-byte area (length 0: omitted)
            return (
                head
                + _call("GGCDDCN", _dcounter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM")))
                + _resp(opts, True, labels)
            )
        staged, areas = _counter_areas(opts, ("VALUE", "MINIMUM", "MAXIMUM"), ("VALUE", "MINIMUM", "MAXIMUM"))
        return head + staged + _call("GGCDCNT", areas) + _resp(opts, True, labels)
    if verb == "ASKTIME":  # the task's clock; a task takes no time, so EIBDATE / EIBTIME stay as dispatched
        _check_spec("ASKTIME", opts, (verb,))
        if not opts.get("ABSTIME"):
            return ["CONTINUE"]
        return ["MOVE FUNCTION CURRENT-DATE(1:8) TO GG-YMD", "MOVE FUNCTION CURRENT-DATE(9:8) TO GG-HMSC",
                f"COMPUTE {opts['ABSTIME']} =", "    (FUNCTION INTEGER-OF-DATE(GG-DATE8)",
                "    - FUNCTION INTEGER-OF-DATE(19000101)) * 86400000",
                "    + GG-HH * 3600000 + GG-MI * 60000", "    + GG-SS * 1000 + GG-CS * 10"]  # fmt: skip
    if verb == "FORMATTIME":
        out = _formattime(opts)
        return out + _resp(opts, True, labels) if opts.get("RESP") or opts.get("RESP2") else out
    if verb == "SYNCPOINT":
        _check_spec("SYNCPOINT", opts, (verb,))
        mode = "MOVE 'ROLLBACK' TO GG-FLAGS" if "ROLLBACK" in opts else "MOVE SPACES TO GG-FLAGS"
        return [mode] + _call("GGCSYNC", []) + _resp(opts, False, labels)
    if verb == "INQUIRE" and "PROGRAM" in opts:  # #4023 follow-up: is the program installed (COMEN01C's option check)
        _check_spec("INQUIRE PROGRAM", opts, (verb,), lambda bad: ["INQUIRE PROGRAM"])
        if not opts["PROGRAM"]:
            raise Unsupported(NEEDS_ARGUMENT, ["INQUIRE PROGRAM"])
        if "STATUS" in opts and not opts["STATUS"]:
            raise Unsupported(NEEDS_ARGUMENT, ["INQUIRE PROGRAM"])
        status = (["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['STATUS']}", "END-IF"]
                  if opts.get("STATUS") else [])  # #4768 (X34): the definition's CVDA, on NORMAL only  # fmt: skip
        return [name(opts["PROGRAM"], "GG-NAME1")] + _call("GGCINQP", []) + status + _resp(opts, True, labels)
    if verb == "BIF" and "DEEDIT" in opts:  # #4415 slice 1 (X26): FIELD edited in place, in the region's EBCDIC page
        _check_spec("BIF DEEDIT", opts, ("BIF", "DEEDIT"), lambda bad: ["BIF DEEDIT"])
        if not opts.get("FIELD"):
            raise Unsupported(_rule("BIF DEEDIT", "required", "FIELD"), ["BIF DEEDIT"])
        field = opts["FIELD"]
        return ([f"MOVE {opts.get('LENGTH') or f'LENGTH OF {field}'} TO GG-NUM"]
                + _call("GGCDEED", [f"BY REFERENCE {field}", f"BY VALUE LENGTH OF {field}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "INQUIRE" and "ASSOCIATION" in opts:  # #4415 slice 2 (X29): the task's own origin data
        _check_spec("INQUIRE ASSOCIATION", opts, (verb,), lambda bad: ["INQUIRE ASSOCIATION"])
        if not opts["ASSOCIATION"] or opts["ASSOCIATION"].strip().upper() != "EIBTASKN":
            raise Unsupported(
                f"INQUIRE ASSOCIATION({opts['ASSOCIATION']}): only the task's own number, EIBTASKN, is "
                "modelled (IBM gives no representation for the 4 bytes)",
                ["INQUIRE ASSOCIATION"],
            )
        wanted = [o for o in ("ODAPPLID", "ODUSERID", "ODFACILNAME", "ODNETWORKID", "ODFACILTYPE") if opts.get(o)]
        if not wanted:  # IBM's INVREQ RESP2 2 ("specified with no arguments") is ambiguous about ASSOCIATION alone
            raise Unsupported(
                "INQUIRE ASSOCIATION without an origin option: IBM's INVREQ RESP2 2 does not say whether "
                "ASSOCIATION alone is none: not modelled",
                ["INQUIRE ASSOCIATION"],
            )
        lines = []
        for o in wanted:
            lines += [f"MOVE '{o}' TO GG-FLAGS"] + _call("GGCINQA", [])
            lines.append(f"MOVE GG-NUM TO {opts[o]}" if o == "ODFACILTYPE" else f"MOVE GG-NAME1 TO {opts[o]}")
        return lines + _resp(opts, False, labels)
    if (verb == "WEB PARSE" or (verb == "WEB" and "PARSE" in opts)) and "URL" in opts:  # #4767 (X36): WEB PARSE URL
        return cics_web._web_parse(opts, labels)
    if verb == "WEB SEND" or (verb == "WEB" and "SEND" in opts):  # #4767 (X37): the server's response
        return cics_web._web_send(opts, labels)
    if verb == "WEB EXTRACT" or (verb == "WEB" and "EXTRACT" in opts):  # #4767 (X38): the server reads its request
        return cics_web._web_extract(opts, labels)
    if verb == "EXTRACT" and "WEB" in opts:  # #4972 (X38): the same, IBM's synonym
        return cics_web._web_extract(opts, labels, "EXTRACT WEB")
    if verb == "EXTRACT" and "TCPIP" in opts:  # #4972 (X38): the connection the task was started on
        return cics_web._extract_tcpip(opts, labels)
    if verb == "WEB RECEIVE" or (verb == "WEB" and "RECEIVE" in opts):
        return cics_web._web_receive(opts, labels)
    if verb == "GETMAIN":  # #4771 (X47): task storage addressed by a pointer
        return _getmain(opts, labels)
    if verb == "FREEMAIN":
        return _freemain(opts, labels)
    if verb == "ADDRESS":  # #5079 (X59): a pointer to the EIB / the COMMAREA
        return _address(opts, labels)
    if verb == "WEB" and "RETRIEVE" in opts:  # #4941 (X41): the document of the last WEB SEND
        return cics_web._web_retrieve(opts, labels)
    if verb == "WEB" and "HTTPHEADER" in opts and ({"READ", "WRITE"} & set(opts)):
        return cics_web._web_header("READ" if "READ" in opts else "WRITE", opts, labels)
    if (
        verb == "WEB"
        and ({"READ", "STARTBROWSE", "READNEXT", "ENDBROWSE"} & set(opts))
        and any(k in opts for k in cics_web._WEB_KIND)
    ):
        return cics_web._web_forms(
            next(f for f in ("READ", "STARTBROWSE", "READNEXT", "ENDBROWSE") if f in opts), opts, labels
        )
    if verb == "WEB" and ({"OPEN", "CONVERSE", "CLOSE"} & set(opts)):  # #4767 zECS (X35): CICS web support, client
        return cics_web._web(opts, labels)
    if verb == "DOCUMENT" and ({"CREATE", "RETRIEVE"} & set(opts)):  # #4769 zECS (X33): the document handler
        form = "CREATE" if "CREATE" in opts else "RETRIEVE"
        key = f"DOCUMENT {form}"
        _check_spec(key, opts, (verb, form), lambda bad: [f"{key} {o}" for o in bad])
        tok = opts.get("DOCTOKEN")
        if not tok:
            raise Unsupported(_rule(key, "required", "DOCTOKEN"), [key])
        for o in ("DOCTOKEN", "TEXT", "BINARY", "INTO"):  # (IBM's COBOL form takes a data area)
            if opts.get(o) and _literal(opts[o]):
                raise Unsupported(f"{key} {o} as a literal: a data area is the COBOL form", [key])
        tokarg = [f"BY REFERENCE {tok}", f"BY VALUE LENGTH OF {tok}"]
        if form == "CREATE":
            given = [o for o in ("TEXT", "BINARY", "TEMPLATE") if o in opts]
            if len(given) > 1:
                raise Unsupported(_rule(key, "at_most_one", "TEXT"), [key])
            for o in ("TEXT", "BINARY"):
                if o in opts and "LENGTH" not in opts:
                    raise Unsupported(_rule(key, "requires", "TEXT"), [key])
            if "LENGTH" in opts and not ({"TEXT", "BINARY"} & set(opts)):
                raise Unsupported(_rule(key, "requires", "LENGTH"), [key])
            if "TEXT" in opts or "BINARY" in opts:
                area = opts["TEXT"] if "TEXT" in opts else opts["BINARY"]
                lines = [f"MOVE {opts['LENGTH']} TO GG-LEN", "MOVE 'DATA' TO GG-FLAGS"]
                src = [f"BY REFERENCE {area}", f"BY VALUE LENGTH OF {area}"]
            elif "TEMPLATE" in opts:
                t = opts["TEMPLATE"]
                lit = _literal(t)
                lines = ["MOVE 'TEMPLATE' TO GG-FLAGS"]
                src = [f"BY REFERENCE {t}", f"BY VALUE {len(lit) if lit is not None else f'LENGTH OF {t}'}"]
            else:
                lines = ["MOVE 'EMPTY' TO GG-FLAGS"]
                src = tokarg[:1] + ["BY VALUE 0"]
            return lines + _call("GGCDOCC", src + tokarg) + _resp(opts, True, labels)
        for o in ("INTO", "MAXLENGTH", "DATAONLY"):
            if o not in opts:
                raise Unsupported(_rule(key, "required", o), [key])
        after = []
        if opts.get("LENGTH"):  # (LENGTH is set on NORMAL and on the truncating LENGERR, RESP2 2, only)
            after = ["IF GG-RESP = 0 OR (GG-RESP = 22 AND GG-RESP2 = 2)", f"    MOVE GG-LEN TO {opts['LENGTH']}",
                     "END-IF"]  # fmt: skip
        return ([f"MOVE {opts['MAXLENGTH']} TO GG-LEN"]
                + _call("GGCDOCR", tokarg + [f"BY REFERENCE {opts['INTO']}", f"BY VALUE LENGTH OF {opts['INTO']}"])
                + after + _resp(opts, True, labels))  # fmt: skip
    if verb == "INQUIRE" and "URIMAP" in opts:  # #4270 zECS (X32): the browse of the installed URIMAP definitions
        _check_spec("INQUIRE URIMAP", opts, (verb,), lambda bad: [f"INQUIRE URIMAP {o}" for o in bad])
        form = [f for f in ("START", "NEXT", "END") if f in opts]
        if len(form) > 1:
            raise Unsupported(_rule("INQUIRE URIMAP", "at_most_one", "START"), ["INQUIRE URIMAP"])
        if not form:  # #4768 (X34): the direct form, URIMAP(name) -- NOTFND RESP2 3 when it is not installed
            if not opts.get("URIMAP"):
                raise Unsupported(_rule("INQUIRE URIMAP", "required", "URIMAP"), ["INQUIRE URIMAP"])
            outs = [o for o in ("PATH", "TRANSACTION") if opts.get(o)]
            lines = [name(opts["URIMAP"], "GG-NAME1"), "MOVE 'DIRECT' TO GG-FLAGS"] + _call("GGCURIB", [])
        else:
            outs = [o for o in ("URIMAP", "PATH", "TRANSACTION") if opts.get(o)]
            if form[0] != "NEXT" and outs:
                raise Unsupported(f"INQUIRE URIMAP {form[0]} {outs[0]}: a browse {form[0]} returns no definition",
                                  ["INQUIRE URIMAP"])  # fmt: skip
            lines = [f"MOVE '{form[0]}' TO GG-FLAGS"] + _call("GGCURIB", [])
        if outs:
            lines.append("IF GG-RESP = 0")
            for o in outs:
                lines += [f"    MOVE '{o}' TO GG-FLAGS"] + [
                    f"    {ln}" for ln in _call("GGCURIP", [f"BY REFERENCE {opts[o]}", f"BY VALUE LENGTH OF {opts[o]}"])
                ]
            lines.append("END-IF")
        return lines + _resp(opts, True, labels)
    # #5859 (X32): GGCVER -- the verdict a scenario states for the USERID
    if verb == "VERIFY" and not ({"PHRASE", "TOKEN"} & set(opts)):
        _check_spec("VERIFY PASSWORD", opts, (verb,), lambda bad: [f"VERIFY PASSWORD {bad[0]}"])
        for need in ("USERID", "PASSWORD"):
            if not opts.get(need):
                raise Unsupported(f"VERIFY PASSWORD without {need}", ["VERIFY PASSWORD"])
        user = opts["USERID"]
        return (_call("GGCVER", [f"BY REFERENCE {user}", f"BY VALUE LENGTH OF {user}"])
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "VERIFY":
        raise _stub_only("VERIFY PHRASE / VERIFY TOKEN")
    if verb == "WRITE" and "OPERATOR" in opts:  # #4270 zECS (X32): a plain message to the console
        _check_spec("WRITE OPERATOR", opts, (verb, "OPERATOR"))
        text = opts.get("TEXT")
        if not text:
            raise Unsupported(_rule("WRITE OPERATOR", "required", "TEXT"), ["WRITE OPERATOR"])
        if _literal(text):  # (IBM's COBOL form takes a data area)
            raise Unsupported("WRITE OPERATOR TEXT as a literal: a data area is the COBOL form", ["WRITE OPERATOR"])
        if ("ROUTECODES" in opts) != ("NUMROUTES" in opts):  # (the rule goes both ways)
            raise Unsupported(_rule("WRITE OPERATOR", "requires", "ROUTECODES"), ["WRITE OPERATOR"])
        if not any(o in opts for o in ("TEXTLENGTH", "ROUTECODES")):
            return ([f"MOVE LENGTH OF {text} TO GG-LEN"] + _call("GGCWTO", [f"BY REFERENCE {text}"])
                    + _resp(opts, True, labels))  # fmt: skip
        # #5859 (X32): TEXTLENGTH is GG-LEN, ROUTECODES / NUMROUTES the routes area and GG-NUM; GG-FLAGS says which were given
        # (EVENTUAL changes nothing observable). The areas' sizes go by value; the flags are cleared after the call.
        flags = " ".join(f for f, o in (("TEXTLENGTH", "TEXTLENGTH"), ("ROUTES", "ROUTECODES")) if o in opts)
        routes = opts.get("ROUTECODES") or text
        lines = [
            f"MOVE {opts['TEXTLENGTH']} TO GG-LEN" if opts.get("TEXTLENGTH") else f"MOVE LENGTH OF {text} TO GG-LEN"
        ]
        if opts.get("NUMROUTES"):
            lines.append(f"MOVE {opts['NUMROUTES']} TO GG-NUM")
        lines.append(f"MOVE '{flags}' TO GG-FLAGS")
        lines += _call("GGCWTO", [f"BY REFERENCE {text}", f"BY VALUE LENGTH OF {text}", f"BY REFERENCE {routes}",
                                  f"BY VALUE LENGTH OF {routes}"])  # fmt: skip
        return lines + ["MOVE SPACES TO GG-FLAGS"] + _resp(opts, True, labels)
    if verb in ("INQUIRE", "SET") and "TDQUEUE" in opts:  # #5168 round 3 (X61): an extrapartition queue's open state
        key = f"{verb} TDQUEUE"
        _check_spec(key, opts, (verb,), lambda bad: [key])
        if not opts.get("TDQUEUE"):
            raise Unsupported(_rule(key, "required", "TDQUEUE"), [key])
        queue = name(opts["TDQUEUE"], "GG-QNAME")
        if verb == "SET":
            given = [o for o in ("OPENSTATUS", "ENABLESTATUS", "TRIGGERLEVEL") if opts.get(o)]
            if not given:
                raise Unsupported(_rule(key, "requires", "TDQUEUE"), [key])
            if len(given) > 1:  # #5168 round 5 (X66): one state per command
                raise Unsupported(f"SET TDQUEUE with {' and '.join(given)} together", [key])
            if opts.get("TRIGGERLEVEL"):  # #5168 round 7 (X66): the level in GG-NUM
                return ([queue, f"MOVE {opts['TRIGGERLEVEL']} TO GG-NUM"] + _call("GGCSTDT", [])
                        + _resp(opts, True, labels))  # fmt: skip
            if opts.get("ENABLESTATUS"):
                return ([queue, f"MOVE {opts['ENABLESTATUS']} TO GG-NUM"] + _call("GGCSTDE", [])
                        + _resp(opts, True, labels))  # fmt: skip
            return [queue, f"MOVE {opts['OPENSTATUS']} TO GG-NUM"] + _call("GGCSTDQ", []) + _resp(opts, True, labels)
        wanted = [
            o for o in ("OPENSTATUS", "TYPE", "ENABLESTATUS", "TRIGGERLEVEL", "RECOVSTATUS", "TRANSID") if opts.get(o)
        ]
        if not wanted:
            raise Unsupported(_rule(key, "requires", "TDQUEUE"), [key])
        # #5168 round 6 (X66): TRIGGERLEVEL, RECOVSTATUS and TRANSID come back in the otherwise unused GG-HOURS, GG-MINS, GG-RTRAN
        field = {"OPENSTATUS": "GG-NUM", "TYPE": "GG-LEN", "ENABLESTATUS": "GG-ITEM", "TRIGGERLEVEL": "GG-HOURS",
                 "RECOVSTATUS": "GG-MINS", "TRANSID": "GG-RTRAN"}  # fmt: skip
        return ([queue, f"MOVE '{' '.join(wanted)}' TO GG-FLAGS"] + _call("GGCITDQ", []) + ["IF GG-RESP = 0"]
                + [f"    MOVE {field[o]} TO {opts[o]}" for o in wanted]
                + ["END-IF"] + _resp(opts, True, labels))  # fmt: skip
    if verb in ("INQUIRE", "SET") and "TERMINAL" in opts:  # #4415 slice 1 (X26): the terminal's UCTRANST CVDA
        key = f"{verb} TERMINAL"
        _check_spec(key, opts, (verb,), lambda bad: [key])
        if not opts.get("TERMINAL"):
            raise Unsupported(_rule(key, "required", "TERMINAL"), [key])
        if not opts.get("UCTRANST"):
            raise Unsupported(f"{key} without UCTRANST", [key])
        if verb == "SET":
            return ([name(opts["TERMINAL"], "GG-NAME1"), f"MOVE {opts['UCTRANST']} TO GG-NUM"]
                    + _call("GGCSETT", []) + _resp(opts, True, labels))  # fmt: skip
        return ([name(opts["TERMINAL"], "GG-NAME1")] + _call("GGCINQT", [])
                + ["IF GG-RESP = 0", f"    MOVE GG-NUM TO {opts['UCTRANST']}", "END-IF"]
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "RECEIVE" and "MAP" in opts:
        _check_spec("RECEIVE MAP", opts, (verb,))
        into = opts.get("INTO") or (f"{_literal(opts['MAP'])}I" if _literal(opts["MAP"]) else None)
        if not into:
            raise Unsupported("RECEIVE MAP(data-name) without INTO")
        return ([name(opts["MAP"], "GG-NAME1"), name(opts.get("MAPSET") or opts["MAP"], "GG-NAME2")]
                + _call("GGCRECV", [f"BY REFERENCE {into}", f"BY VALUE LENGTH OF {into}"])
                + _map_abend(labels)
                + cics_conditions.input_resp(opts, labels, handle_aid))  # fmt: skip
    if verb == "RECEIVE":  # #4005: terminal input, unformatted (SPEC 5: the step's `text`)
        _check_spec("RECEIVE", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        into, setp = opts.get("INTO"), opts.get("SET")
        # LENGTH / FLENGTH is in-out: in, the most INTO takes (unless MAXLENGTH / MAXFLENGTH says so);
        # out, the length of the data. COBOL may omit it: the translator supplies LENGTH OF INTO.
        length = _one_of("RECEIVE", opts, "LENGTH", "FLENGTH")
        most = _one_of("RECEIVE", opts, "MAXLENGTH", "MAXFLENGTH")
        flags = "MOVE 'NOTRUNCATE' TO GG-FLAGS" if "NOTRUNCATE" in opts else "MOVE SPACES TO GG-FLAGS"  # #4413
        if setp:  # #4413: SET(ADDRESS OF record), MAXLENGTH and LENGTH(data-area) required (det/cics.py says why)
            m = re.fullmatch(r"ADDRESS\s+OF\s+([A-Z0-9-]+)", setp, re.I)
            if into or not most or not length:
                raise Unsupported("RECEIVE SET without MAXLENGTH and LENGTH", ["RECEIVE SET"])
            if not m:  # #5042 (X58): SET(pointer) -> GGCRECP, the data in a new block the pointer addresses
                return ([flags, f"MOVE {most} TO GG-LEN"] + _call("GGCRECP", [f"BY REFERENCE {_pointer('RECEIVE', setp)}"])
                        + [f"MOVE GG-LEN TO {length}"] + cics_conditions.input_resp(opts, labels, handle_aid))  # fmt: skip
            return ([flags, f"MOVE {most} TO GG-LEN"] + _call("GGCRECS", ["BY REFERENCE GG-PTR"])
                    + [f"SET ADDRESS OF {m.group(1)} TO GG-PTR", f"MOVE GG-LEN TO {length}"]
                    + cics_conditions.input_resp(opts, labels, handle_aid))  # fmt: skip
        if not into:
            raise Unsupported(_rule("RECEIVE", "one_of", "INTO"), ["RECEIVE"])
        limit = most or length or f"LENGTH OF {into}"
        lines = [flags, f"MOVE {limit} TO GG-LEN"] + _call("GGCRECT", [f"BY REFERENCE {into}"])
        if length:
            lines.append(f"MOVE GG-LEN TO {length}")
        return lines + cics_conditions.input_resp(opts, labels, handle_aid)
    if verb == "WRITEQ" and "TD" in opts:  # transient data: a record on an extrapartition / intrapartition queue
        _check_spec("WRITEQ TD", opts, (verb, "TD"), lambda bad: [f"WRITEQ TD {bad[0]}"])
        queue, frm = opts.get("QUEUE"), opts.get("FROM")
        if not (queue and frm):
            raise Unsupported("WRITEQ TD without QUEUE / FROM", ["WRITEQ TD"])
        return ([name(queue, "GG-QNAME"), f"MOVE {opts.get('LENGTH') or 'LENGTH OF ' + frm} TO GG-LEN"]
                + _write_from(opts.get("LENGTH"), frm, "WRITEQ TD", _call("GGCWRTD", [f"BY REFERENCE {frm}"]))
                + _resp(opts, True, labels))  # fmt: skip
    if verb in ("READQ", "DELETEQ") and "TD" in opts:  # #5079 (X57): transient data, intrapartition
        return _td_command(verb, opts, labels)
    if verb == "DELETEQ" and "TD" not in opts:  # #4415 slice 2 (X29): the whole TS queue
        return cics_tempstorage.delete_queue(opts, labels)
    if verb in ("READQ", "WRITEQ") and "TD" not in opts:  # #4002: temporary storage (TS is the default)
        return cics_tempstorage.ts_command(verb, opts, labels)
    if verb == "SEND" and "MAP" in opts:
        _check_spec("SEND MAP", opts, (verb,))
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
        return lines + _call("GGCSMAP", args) + _map_abend(labels) + _resp(opts, can_fail=False)
    if verb == "SEND" and "CONTROL" in opts:  # #4413: device controls; CURSOR's value in GG-LEN, -1: none
        _check_spec("SEND CONTROL", opts, (verb, "CONTROL"), lambda bad: ["SEND CONTROL"])
        if "CURSOR" in opts and not opts["CURSOR"]:
            raise Unsupported("SEND CONTROL CURSOR without a value", ["SEND CONTROL"])
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
        _check_spec("SEND TEXT", opts, (verb, "TEXT"))  # (a deny-list until spec PR 3: an unknown option was ignored)
        kind = ["TEXT"] if "TEXT" in opts else ["DATA"]
        textflags = " ".join(kind + [n for n in flags if n in ("ERASE", "FREEKB", "ALARM", "WAIT", "LAST")])
        return ([f"MOVE '{textflags[:40]}' TO GG-FLAGS"]
                + _call("GGCSTXT", [f"BY REFERENCE {src}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {src}'}"])
                + _resp(opts, can_fail=False))  # fmt: skip
    if verb in ("RETURN", "XCTL"):
        if verb == "XCTL" and not opts.get("PROGRAM"):
            raise Unsupported("XCTL without PROGRAM")
        _check_spec(verb, opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        if verb == "RETURN" and "CHANNEL" in opts:  # #5005 (X17): the next task's current channel (GGCRETC)
            if not opts.get("TRANSID") or {"COMMAREA", "LENGTH", "IMMEDIATE"} & opts.keys():
                raise Unsupported(_rule("RETURN", "at_most_one", "CHANNEL"), ["RETURN CHANNEL"])
            return ([name(opts["TRANSID"], "GG-NAME1"), f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
                    + _call("GGCRETC", ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])
                    + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
        if verb == "XCTL" and opts.get("CHANNEL"):  # #4270: the target's current channel (GGCXCTL)
            if "COMMAREA" in opts or "LENGTH" in opts:
                raise Unsupported(_rule("XCTL", "at_most_one", "CHANNEL"), ["XCTL CHANNEL"])
            return ([name(opts["PROGRAM"], "GG-NAME1"), "MOVE 0 TO GG-ITEM", "MOVE 'CHANNEL' TO GG-FLAGS",
                     f"MOVE {opts['CHANNEL']} TO GG-CHAN"]
                    + _call("GGCXCTL", ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])
                    + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
        target = opts.get("TRANSID") if verb == "RETURN" else opts.get("PROGRAM")
        area = opts.get("COMMAREA")
        args = ([f"BY REFERENCE {area}", f"BY VALUE {opts.get('LENGTH') or f'LENGTH OF {area}'}"] if area
                else ["BY REFERENCE GG-FLAGS", "BY VALUE 0"])  # fmt: skip
        if verb == "RETURN" and "IMMEDIATE" in opts:  # #4270 (X27): the next task attached at once; can fail (GGCRETI)
            if not target:
                raise Unsupported("RETURN IMMEDIATE without TRANSID: IBM does not say what it attaches (not modelled)",
                                  ["RETURN IMMEDIATE"])  # fmt: skip
            return ([name(target, "GG-NAME1"), f"MOVE {1 if area else 0} TO GG-ITEM"]
                    + _call("GGCRETI", args) + ["IF GG-RESP = 0", "    GOBACK", "END-IF"]
                    + _resp(opts, True, labels))  # fmt: skip
        if verb == "RETURN" and opts.get("TRANSID") and opts.get("RESP"):  # #6271 (X71): a planned fault fails it
            return ([name(target, "GG-NAME1"), "MOVE 2 TO GG-ITEM"] + _call("GGCRETN", args)
                    + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
        if verb == "RETURN":
            return [name(target, "GG-NAME1")] + _call("GGCRETN", args) + ["GOBACK"]
        # #4008: a failed XCTL (LENGERR, PGMIDERR) leaves control here, through the condition handling
        return ([name(target, "GG-NAME1"), f"MOVE {1 if area else 0} TO GG-ITEM", "MOVE SPACES TO GG-FLAGS"]
                + _call("GGCXCTL", args)
                + ["IF GG-RESP = 0", "    GOBACK", "END-IF"] + _resp(opts, True, labels))  # fmt: skip
    if verb == "RUN":  # #4270 slice 2: RUN TRANSID CHILD (#4884: CHANNEL)
        return cics_taskcontrol._run_transid(opts, labels)
    if verb == "FETCH" and ("ANY" in opts) != ("CHILD" in opts):  # #4884, #4950
        return cics_taskcontrol._fetch_child("FETCH ANY" if "ANY" in opts else "FETCH CHILD", opts, labels)
    if verb == "FREE" and "CHILD" in opts:  # #4950
        return cics_taskcontrol._free_child(opts, labels)
    if verb in ("START", "RETRIEVE", "CANCEL"):  # #4006: interval control
        return cics_taskcontrol._interval_command(verb, opts, labels)
    if verb == "LINK":  # #4004: a new level runs the program on the caller's own COMMAREA storage
        _check_spec("LINK", opts, (verb,), lambda bad: [f"{verb} {bad[0]}"])
        if not opts.get("PROGRAM"):
            raise Unsupported("LINK without PROGRAM", ["LINK"])
        if "CHANNEL" in opts and not opts["CHANNEL"]:
            raise Unsupported(NEEDS_ARGUMENT, ["LINK CHANNEL"])
        if "CHANNEL" in opts and ("COMMAREA" in opts or "LENGTH" in opts):
            raise Unsupported(_rule("LINK", "at_most_one", "CHANNEL"), ["LINK CHANNEL"])
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
                + _map_abend(labels)  # #6271 (X70): a planned abend at the LINK went to the exit, or ended the task
                + ["IF GG-RESP = 0", f"    CALL 'GGCRUN' USING {ref}", "    CALL 'GGCLRET' USING GG-CICS"]
                + [f"    {ln}" for ln in _transfer(labels)]
                + ["    IF GG-GOTO < 0", "        GOBACK", "    END-IF", "END-IF"]
                + _resp(opts, True, labels))  # fmt: skip
    if verb == "ABEND":  # #4003: an exit at this level takes it by GO TO; else the program is left
        _check_spec("ABEND", opts, (verb,))
        return ([name(opts.get("ABCODE"), "GG-NAME1"), "MOVE 'CANCEL' TO GG-FLAGS" if "CANCEL" in opts else "MOVE SPACES TO GG-FLAGS"]
                + _call("GGCABND", []) + _transfer(labels) + ["GOBACK"])  # fmt: skip
    if (
        (verb in ("HANDLE", "IGNORE") and len(pairs) > 1 and pairs[1][0] in ("CONDITION", "ABEND", "AID"))
        or (verb in ("PUSH", "POP") and len(pairs) > 1 and pairs[1][0] == "HANDLE")
        or verb == "ASSIGN"
    ):
        return cics_conditions.handle(pairs, labels)  # fmt: skip
    if verb in ("PUT", "GET", "DELETE") and "CONTAINER" in opts:  # #4270
        return cics_containers._container_command(verb, opts, labels)
    if (
        verb in ("PUT64", "GET64") and "CONTAINER" in opts
    ):  # #5005 (X17): the base command; SET (64-bit pointer) refused
        if "SET" in opts:
            raise Unsupported(SPEC[f"{verb} CONTAINER"].refusal_message(["SET"]), [f"{verb} CONTAINER SET"])
        return cics_containers._container_command(verb[:3], {o: v for o, v in opts.items() if o != verb}, labels)
    if verb in ("MOVE", "STARTBROWSE", "GETNEXT", "ENDBROWSE") and "CONTAINER" in opts:  # #4951
        return cics_containers._container_browse_command(verb, opts, labels)
    if verb in ("DELETE", "QUERY") and "CHANNEL" in opts and "CONTAINER" not in opts:  # #5005
        return cics_containers._channel_command(verb, opts, labels)
    raise Unsupported(_whole_message(pairs), [_feature(pairs)])


def _whole_message(pairs: list[tuple[str, str | None]]) -> str:
    """A command the stub does not model, refused whole with the translator's message: its name-only (or
    engine-only) spec entry's reason when it is a CICS application command the spec lists. The verb words are
    read as det/cics.py's parse_exec reads them: the leading bare names, at most two, a map option aside."""
    words: list[str] = []
    for n, v in pairs:
        if v is not None or len(words) == 2 or (words and (n in MAP_OPTIONS or n == "NOTRUNCATE")):
            break
        words.append(n)
    verb = " ".join(words)
    rest = [n for n, _v in pairs[len(words) :]]
    key = f"{verb} COUNTER" if verb != "GET" and {"COUNTER", "DCOUNTER"} & set(rest) else verb
    known = whole_refusal(key, verb, rest[0] if rest else None)
    return known.whole_message(verb) if known is not None else f"EXEC CICS {verb} not modelled"


def _dcounter_areas(opts: dict[str, str | None], names: tuple[str, ...]) -> list[str]:
    """#4770 (X45): the doubleword areas of a DCOUNTER command as (area, length) pairs, `BY VALUE 0` for one the command omits;
    a literal is refused (the stub reads and writes the area's bytes: a data area is the COBOL form)."""
    out: list[str] = []
    for o in names:
        v = opts.get(o)
        if v and (_literal(v) or re.fullmatch(r"[+-]?\d+", v)):
            raise Unsupported(f"DCOUNTER {o} as a literal: a data area is the COBOL form", ["DEFINE COUNTER"])
        out += [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
    return out


def _counter_areas(
    opts: dict[str, str | None], names: tuple[str, ...], literals: tuple[str, ...] = ()
) -> tuple[list[str], list[str]]:
    """#5039 (X50): the fullword areas of a COUNTER command as (area, length) pairs, `BY VALUE 0` for one the command omits,
    with the lines that stage a numeric literal. A command that WRITES an area (QUERY) takes a data area only; DEFINE
    reads its VALUE / MINIMUM / MAXIMUM (`literals`), so a decimal literal is staged big-endian in GG-FLAGS (the stub reads
    the bytes as IBM's fullword binary), as before X50 gave it a literal VALUE through GG-NUM."""
    out: list[str] = []
    pre: list[str] = []
    for n, o in enumerate(names):
        v = opts.get(o)
        if v and (_literal(v) or re.fullmatch(r"[+-]?\d+", v)):
            if o not in literals or not re.fullmatch(r"[+-]?\d+", v):
                raise Unsupported(f"COUNTER {o} as a literal: a data area is the COBOL form", ["DEFINE COUNTER"])
            slot = f"GG-FLAGS({4 * n + 1}:4)"
            pre.append(f"MOVE X'{int(v) & 0xFFFFFFFF:08X}' TO {slot}")
            v = slot
        out += [f"BY REFERENCE {v}", f"BY VALUE LENGTH OF {v}"] if v else ["BY REFERENCE GG-NAME2", "BY VALUE 0"]
    return pre, out


# the det translator's system members (register L4: CEEIGZCT, a GitGalaxy-written stand-in)
DET_COPY = Path(__file__).resolve().parents[2] / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "copy"


def _in_literal(code: str, pos: int) -> bool:
    """Whether `pos` of a source line's code area falls inside a quoted literal (' or ", doubled to escape)."""
    quote = None
    for ch in code[:pos]:
        if quote is None and ch in "'\"":
            quote = ch
        elif ch == quote:
            quote = None  # (a doubled quote closes and reopens: the same state at the next character)
    return quote is not None


def _exec_blocks(lines: list[str]) -> Iterator[tuple[int, int, str, str, str]]:
    """Each EXEC CICS block of a fixed-format program: (first line, last line, the code before
    it, its body, the code after END-EXEC)."""
    i = 0
    while i < len(lines):
        line = lines[i]
        code = line[7:72] if len(line) > 7 else ""
        # (#4950: not inside a literal -- CBSA CRECUST DISPLAYs 'EXEC CICS FETCH ANY failed. RESP=')
        start = next((m for m in _EXEC.finditer(code) if not _in_literal(code, m.start())), None)
        if (
            len(line) > 6 and line[6] in "*/dD"
        ) or not start:  # (#4950: a debugging line is a comment, as cobc reads it)
            i += 1
            continue
        prefix, body, j = code[: start.start()], code[start.end() :], i
        if start.group(0).split()[1].upper() == "DLI":
            body = _DLI_TAG + body
        while not _END_EXEC.search(body):
            j += 1
            if j >= len(lines):
                raise Unsupported(f"EXEC CICS at line {i + 1} has no END-EXEC")
            nxt = lines[j]
            if len(nxt) > 6 and nxt[6] in "*/dD":
                continue
            if len(nxt) > 6 and nxt[6] == "-":
                raise Unsupported(f"continuation line inside EXEC CICS at line {j + 1}")
            body += " " + (nxt[7:72] if len(nxt) > 7 else "")
        end = _END_EXEC.search(body)
        assert end is not None
        yield i, j, prefix, body[: end.start()], body[end.end() :]
        i = j + 1


def _numbered(ln: str) -> str:
    """DFHRESP(x) / DFHVALUE(x) replaced by their numbers in the line's code area only, padded back to column 72 when
    columns 73-80 hold a sequence number (#4892: CardDemo app-vsam-mq numbers its lines there), so it stays there."""
    head, tail = ln[:72], ln[72:]
    new = _DFHVALUE.sub(
        lambda m: str(CVDA[m.group(1).upper()]), _DFHRESP.sub(lambda m: str(DFHRESP[m.group(1).upper()]), head)
    )
    return (new.ljust(72) if tail and new != head else new) + tail


_DIB = "       01  DIB.\n           05 FILLER   PIC XX.\n           05 DIBSTAT  PIC XX.\n"

# X6: the record a WRITEQ past its FROM item writes (_write_from); only a program that has such a WRITEQ gets it
_PADQ = "       01  GG-PADQ PIC X(32767).\n"


DLI_CALL = re.compile(r"\bEXEC\s+DLI\b", re.I)
# #5233 (register I5): the CALL interfaces to DL/I. Under CICS only EXEC DLI is modelled; no burned program CALLs these.
DLI_CALL_INTERFACE = re.compile(r"\bCALL\s+['\"](CBLTDLI|AIBTDLI|CEETDLI)['\"]", re.I)


def refuse_dli_call_interface(source: str) -> None:
    """Refuse by name a CICS program that CALLs CBLTDLI / AIBTDLI / CEETDLI (the UIB-addressed PCB list is not modelled)."""
    code = "\n".join(ln[6:72] for ln in source.splitlines() if len(ln) > 6 and ln[6] not in "*/")
    m = DLI_CALL_INTERFACE.search(code)
    if m:
        raise Unsupported(
            f"CALL '{m.group(1).upper()}' under CICS: only EXEC DLI is modelled (register I5)", ["CALL DLI"]
        )


def dli_stage(case: dict[str, Any], corpus: Path, dest: Path, sc: dict[str, Any] | None = None) -> list[str]:
    """#5278: the stated databases of a case whose program issues EXEC DLI -- dbd.cfg, psb.cfg and each seed, into
    `dest` (the stub reads them from the scenario's directory, the port from gitgalaxy.dli.dir). The DBDs' names.
    #6072: a scenario's `ims_seed` adds segments to the seed for its own task."""
    try:
        dbds, pcbs = equivalence_ims.definitions(case, corpus, cics=True)
        equivalence_ims.check_seed_names(sc, dbds)  # #6967
        dest.mkdir(parents=True, exist_ok=True)
        dbd_cfg, psb_cfg = equivalence_ims.config(dbds, pcbs)
        (dest / "dbd.cfg").write_text(dbd_cfg, encoding="ascii")
        (dest / "psb.cfg").write_text(psb_cfg, encoding="ascii")
        for name, db in dbds.items():
            (dest / f"seed.{name}").write_bytes(equivalence_ims.seed(case, corpus, name, db, sc))
    except equivalence_ims.Unsupported as e:
        raise Unsupported(f"EXEC DLI: {e}", ["EXEC DLI"]) from e
    return list(dbds)


def _dli_operand(text: str, what: str) -> str:
    """An integer operand of an EXEC DLI command, `BY VALUE`: a literal or a data name."""
    t = text.strip()
    if re.fullmatch(r"[0-9]+", t) or re.fullmatch(r"[A-Za-z0-9-]+", t):
        return f"BY VALUE {t}"
    if re.fullmatch(r"LENGTH\s+OF\s+[A-Za-z0-9-]+", t, re.I):
        return f"BY VALUE {' '.join(t.split()).upper()}"
    raise Unsupported(f"EXEC DLI {what}({text}): a literal or a data name expected", ["EXEC DLI"])


def translate_dli(body: str) -> list[str]:
    """One EXEC DLI command (#5278, register I5) -> the CALLs of ggdli.c's EXEC entry points (GGDLISCHD, GGDLITERM,
    GGDLIX), DIBSTAT answered. The forms are the ones DetDli models; any other is refused by name."""
    from gitgalaxy.tools.cobol_to_java.det import dli
    from gitgalaxy.tools.cobol_to_java.det.gen import Untranslatable

    text = body.strip()
    verb = (text.split() or [""])[0].upper()
    try:
        if verb == "SCHD":
            m = dli._SCHD.fullmatch(text)
            if m is None:
                raise Unsupported(
                    "EXEC DLI SCHD: only PSB(name), PSB('name') or PSB((area)) with NODHABEND", ["EXEC DLI"]
                )
            return [f"CALL 'GGDLISCHD' USING BY REFERENCE DIBSTAT BY VALUE {1 if m.group('nodh') else 0}"]
        if verb == "TERM":
            if text.split()[1:]:
                raise Unsupported("EXEC DLI TERM: no option is modelled", ["EXEC DLI"])
            return ["CALL 'GGDLITERM' USING BY REFERENCE DIBSTAT"]
        if verb not in (*dli._GETS, *dli._PUTS):
            raise Unsupported(f"EXEC DLI {verb}: not modelled (register I5)", ["EXEC DLI"])
        cl = dli._clauses(re.sub(r"(?is)^\s*USING\b", "", text[len(verb) :]))
    except Untranslatable as e:
        raise Unsupported(str(e), ["EXEC DLI"]) from None
    names = [k for k, _ in cl]
    get = verb in dli._GETS
    allowed = {"PCB", "SEGMENT", "WHERE", "INTO"} if get else {"PCB", "SEGMENT", "FROM"}
    if verb == "ISRT":
        allowed |= {"WHERE", "SEGLENGTH"}
    area = "INTO" if get else "FROM"
    if (bad := [k for k in names if k not in allowed]) or names[:1] != ["PCB"] or names.count(area) != 1:
        raise Unsupported(f"EXEC DLI {verb} {bad[0] if bad else ''}: PCB(n) first and one {area}(area); only "
                          f"{', '.join(sorted(allowed))} are modelled", ["EXEC DLI"])  # fmt: skip
    ssas: list[tuple[str, str, str, str]] = []  # (segment, field, operator, value text)
    for k, v in cl:
        if k == "SEGMENT":
            if not re.fullmatch(dli._ID + r"{1,8}", v, re.I):
                raise Unsupported(f"EXEC DLI {verb}: SEGMENT({v}) is not a segment name", ["EXEC DLI"])
            ssas.append((v.upper(), "", "", ""))
        elif k == "WHERE":
            w = dli._WHERE.fullmatch(v)
            if not ssas or ssas[-1][1] or w is None or w.group("op").upper() not in dli._OPS:
                raise Unsupported(f"EXEC DLI {verb}: WHERE({v}): one `field op value` after its SEGMENT", ["EXEC DLI"])
            ssas[-1] = (ssas[-1][0], w.group("f").upper(), dli._OPS[w.group("op").upper()], w.group("v"))
    if not get and (not ssas or (verb != "ISRT" and len(ssas) != 1)):
        raise Unsupported(f"EXEC DLI {verb}: SEGMENT(s) expected, once for REPL and DLET", ["EXEC DLI"])
    if len(ssas) > 3:
        raise Unsupported(f"EXEC DLI {verb}: more than 3 SEGMENTs", ["EXEC DLI"])
    clause = dict(cl)
    seglen = _dli_operand(clause["SEGLENGTH"], "SEGLENGTH") if "SEGLENGTH" in clause else "BY VALUE -1"
    io = clause[area].strip()
    if not re.fullmatch(r"[A-Za-z0-9-]*[A-Za-z][A-Za-z0-9-]*(?:\s*\([^()]*\))?", io):
        raise Unsupported(f"EXEC DLI {verb}: {area}({io}): a data name expected", ["EXEC DLI"])
    out = ["CALL 'GGDLIX' USING BY REFERENCE DIBSTAT", f"    BY CONTENT '{verb:<4}'",
           f"    {_dli_operand(clause['PCB'], 'PCB')}", f"    BY REFERENCE {io}", f"    {seglen}"]  # fmt: skip
    for seg, fld, op, val in ssas:
        out.append(f"    BY CONTENT '{seg:<8}{fld:<8}{op:<2}'")
        if not fld:
            out += ["    BY REFERENCE DIBSTAT", "    BY VALUE 0"]
        elif re.fullmatch(r"[A-Za-z0-9-]*[A-Za-z][A-Za-z0-9-]*", val):
            out += [f"    BY REFERENCE {val}", f"    BY VALUE LENGTH OF {val}"]
        else:
            raise Unsupported(f"EXEC DLI {verb}: WHERE value {val}: a data name expected (as the port)", ["EXEC DLI"])
    return out


def translate(source: str, copy_dirs: list[Path] | None = None) -> tuple[str, bool]:
    """A fixed-format CICS program -> (the program the stub runtime runs, whether it takes a
    COMMAREA through LINKAGE). Raises Unsupported naming each command it cannot model. #5119 (X56): an OS/VS COBOL
    program's BLL cells and SERVICE RELOAD are lowered first, as the det translator lowers them (det/bll.py; its
    COPY members found in `copy_dirs`), so GnuCOBOL runs the program the port was translated from."""
    from gitgalaxy.tools.cobol_to_java.det import bll, hlasm

    if re.search(
        r"(?mi)^\S+\s+DFHEIENT\b", source
    ):  # #5859: a command-level CICS assembler program, lowered to COBOL as det does
        try:
            source = hlasm.lower_text(source, "program.asm")
        except hlasm.Refused as e:
            raise Unsupported(str(e), ["HLASM"]) from None
    try:
        source = bll.lower_text(source, copy_dirs or [])
    except bll.Refused as e:
        raise Unsupported(str(e), ["BLL cells"]) from None
    lines = source.splitlines()
    if any(
        len(ln) > 6 and ln[6] not in "*/" and re.search(r"(?i)\bWITH\s+DEBUGGING\s+MODE\b", ln[7:72]) for ln in lines
    ):
        raise Unsupported("WITH DEBUGGING MODE: debugging lines compiled as code (not modelled)", ["DEBUGGING MODE"])
    blocks = list(_exec_blocks(lines))
    cics_bodies = [b[3] for b in blocks if not b[3].startswith(_DLI_TAG)]
    labels = cics_conditions.handler_labels(cics_bodies)  # #4003: what GG-GOTO indexes, program-wide
    handle_aid = any(re.match(r"\s*HANDLE\s+AID\b", b_, re.I) for b_ in cics_bodies)  # #4007
    eibds = reads_eibds(lines)  # #5126 (X64)
    eibrcode = reads_eibrcode(lines)  # #5126 (X64)
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
            if body.startswith(_DLI_TAG):
                stmts = translate_dli(body[len(_DLI_TAG) :])
            else:
                stmts = translate_command(body, labels, handle_aid, eibds, eibrcode)
        except Unsupported as e:
            msg = str(e)  # (a whole command's refusal names it already: "EXEC CICS GETMAIN not modelled (...)")
            problems.append(f"line {i + 1}: {msg if msg.startswith('EXEC ') else f'EXEC CICS {msg}'}")
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
    for name in sorted({m.group(1).upper() for ln in out for m in _DFHVALUE.finditer(ln)} - set(CVDA)):
        problems.append(f"DFHVALUE({name}) is not a documented CVDA")  # #4415: refused by name, as the translator does
        features.append(f"DFHVALUE({name})")
    if problems:
        raise Unsupported("; ".join(problems), features)
    text = "\n".join(_numbered(ln) for ln in out) + "\n"
    # the COMMAREA: an 01 DFHCOMMAREA, or a copybook's record renamed to it (CBSA's COPY INQACC REPLACING
    # INQACC-COMMAREA BY DFHCOMMAREA)
    has_commarea = bool(
        re.search(r"^.{6} +01\s+DFHCOMMAREA\b", text, re.M | re.I)
        or re.search(r"^.{6} +COPY\s+\S+\s+REPLACING\b[^.]*\bBY\s+DFHCOMMAREA\b", text, re.M | re.I)
    )
    dib = _DIB if any(b[3].startswith(_DLI_TAG) for b in blocks) else ""  # (#5278: IBM's DIB, only DIBSTAT supplied)
    pad = _PADQ if "GG-PADQ" in text else ""
    text = re.sub(r"^(.{6} +WORKING-STORAGE\s+SECTION\.[^\n]*\n)", r"\1       COPY DFHEIBLK.\n" + dib + pad, text,
                  count=1, flags=re.M | re.I)  # fmt: skip
    if "COPY DFHEIBLK" not in text:
        raise Unsupported("no WORKING-STORAGE SECTION to hold the EIB")
    if not has_commarea and "BY REFERENCE DFHCOMMAREA" in text:  # #5079 (X59): ADDRESS COMMAREA needs the record
        raise Unsupported("ADDRESS COMMAREA in a program with no LINKAGE 01 DFHCOMMAREA: no record to address",
                          ["ADDRESS COMMAREA"])  # fmt: skip
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


def cics_driver(program: str, has_commarea: bool, children: bool = False) -> str:
    """Runs one task: the EIB from $EIBIN (TRANSID, AID name, date, time) and EIBTASKN from the stub
    ($GGCICS_TASKN, #4270), the COMMAREA
    from the stub (its length is EIBCALEN), then the program, then GGCEND. #4950 `children`: the case runs RUN
    TRANSID children, each this task re-run by the stub (GGCCHLD names the child's program, which GGCRUN runs)."""
    aid_names = [ln.split()[1] for ln in (STUB / "DFHAID.cpy").read_text().splitlines() if " PIC " in ln]
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. EQCICSDR.", "ENVIRONMENT DIVISION.",
             "INPUT-OUTPUT SECTION.", "FILE-CONTROL.",
             "    SELECT EIB-IN ASSIGN TO EIBIN ORGANIZATION LINE SEQUENTIAL.",
             "DATA DIVISION.", "FILE SECTION.", "FD  EIB-IN.", "01  EIB-LINE.",
             "    05 IN-TRNID PIC X(4).", "    05 FILLER   PIC X.", "    05 IN-AID   PIC X(8).",
             "    05 FILLER   PIC X.", "    05 IN-DATE  PIC 9(7).", "    05 FILLER   PIC X.",
             "    05 IN-TIME  PIC 9(7).", "    05 FILLER   PIC X.", "    05 IN-TRMID PIC X(4).",
             "WORKING-STORAGE SECTION.", "COPY DFHEIBLK.", "COPY DFHAID.",
             "01  WS-CA  PIC X(32767).", "01  WS-LEN PIC S9(9) COMP-5.",
             "01  WS-PTR USAGE POINTER.", "LINKAGE SECTION.", "01  LK-CA  PIC X(32767).",
             "PROCEDURE DIVISION.",
             "    OPEN INPUT EIB-IN", "    READ EIB-IN", "    CLOSE EIB-IN",
             "    INITIALIZE DFHEIBLK GG-CICS",
             "    MOVE IN-TRNID TO EIBTRNID", "    MOVE IN-DATE TO EIBDATE", "    MOVE IN-TIME TO EIBTIME",
             "    MOVE IN-TRMID TO EIBTRMID",
             "    CALL 'GGCTASKN' USING GG-CICS", "    MOVE GG-NUM TO EIBTASKN",
             "    MOVE 0 TO GG-NUM",
             "    EVALUATE IN-AID"]  # fmt: skip
    lines += [f"        WHEN '{n}' MOVE {n} TO EIBAID" for n in aid_names]
    # #4270 (X23): GGCAREA moves a COMMAREA of a stated length (commarea.exact) to exactly that many bytes before a
    # guard page, and leaves any other where it is (WS-CA)
    lines += ["    END-EVALUATE", "    MOVE LOW-VALUES TO WS-CA",
              "    CALL 'GGCLOAD' USING WS-CA BY VALUE LENGTH OF WS-CA", "        RETURNING WS-LEN",
              "    MOVE WS-LEN TO EIBCALEN",
              ]  # fmt: skip
    task = ["    CALL 'GGCCHIN' USING GG-CICS", "    SET WS-PTR TO ADDRESS OF WS-CA",
            "    CALL 'GGCAREA' USING WS-PTR BY VALUE WS-LEN",
            "    SET ADDRESS OF LK-CA TO WS-PTR",
            f"    CALL '{program}'" + (" USING LK-CA" if has_commarea else ""),
            "    CALL 'GGCAOUT' USING LK-CA BY VALUE WS-LEN"]  # fmt: skip
    if children:  # #4950: a RUN TRANSID child runs its own program, through the dispatcher
        lines += ["    CALL 'GGCCHLD' USING GG-CICS", "    IF GG-ITEM = 1", "        MOVE 0 TO GG-LEN",
                  "        CALL 'GGCTASK' USING GG-CICS", "        CALL 'GGCCHIN' USING GG-CICS",
                  "        CALL 'GGCRUN' USING WS-CA", "    ELSE",
                  *("    " + ln for ln in task), "    END-IF"]  # fmt: skip
    else:
        lines += task
    lines += ["    CALL 'GGCEND' USING GG-CICS", "    STOP RUN."]
    assert all(len(ln) <= 65 for ln in lines), [ln for ln in lines if len(ln) > 65]
    return "".join("       " + ln + "\n" for ln in lines)


def task_driver() -> str:
    """#4004: the driver of a task on the stub, one process per task: the EIB from $EIBIN (TRANSID, AID
    name, date, time, the first program, the terminal), EIBTASKN from the stub ($GGCICS_TASKN,
    #4270), the COMMAREA from the stub (its length is
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
             "    CALL 'GGCTASKN' USING GG-CICS", "    MOVE GG-NUM TO EIBTASKN",
             "    MOVE 0 TO GG-NUM",
             "    EVALUATE IN-AID"]  # fmt: skip
    lines += [f"        WHEN '{n}' MOVE {n} TO EIBAID" for n in aid_names]
    lines += ["    END-EVALUATE", "    MOVE LOW-VALUES TO WS-CA",
              "    CALL 'GGCLOAD' USING WS-CA BY VALUE LENGTH OF WS-CA", "        RETURNING WS-LEN",
              "    MOVE WS-LEN TO EIBCALEN", "    MOVE IN-PROG TO GG-NAME1", "    MOVE WS-LEN TO GG-LEN",
              "    CALL 'GGCTASK' USING GG-CICS", "    CALL 'GGCCHIN' USING GG-CICS",
              "    CALL 'GGCRUN' USING WS-CA", "    CALL 'GGCAOUT' USING WS-CA BY VALUE WS-LEN",
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
def _case_csd(file: str, datasets: dict[str, Any] | None) -> dict[str, Any] | None:
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


def case_runtime_files(datasets: dict[str, Any] | None) -> list[dict[str, Any]]:
    """#4771: a CICS file the program names at run time (zECS: `ZC` + EIBTRNID(3:2) + `FILE` / `KEY`), so no CSD DEFINE
    FILE of the engine's facts carries its name. The case's dataset of that file name states it with its `why`:
    `"runtime_file": {"key_offset", "key_length", "reclen", "why"}` -- the IDCAMS job's KEYS and RECORDSIZE, as `vsam` is
    for a named dataset. Only the COBOL leg binds it: the generated project stores no file the program does not name."""
    out = []
    for name, spec in sorted((datasets or {}).items()):
        rf = (spec or {}).get("runtime_file")
        if rf is None:
            continue
        if (
            not re.fullmatch(r"[A-Z0-9]{1,8}", name)
            or not all(isinstance(rf.get(k), int) for k in ("key_offset", "key_length", "reclen"))
            or not rf.get("why")
            or set(rf) - {"key_offset", "key_length", "reclen", "why"}
        ):
            raise Unsupported(
                f"dataset {name}: a case's runtime_file states key_offset, key_length, reclen and why (a CICS file name "
                f"of at most 8 upper-case characters): {rf}"
            )
        out.append({"file": name, "dsname": name, "base": name, "key_offset": rf["key_offset"],
                    "key_length": rf["key_length"], "reclen": rf["reclen"],
                    "via": ["the case's runtime_file"], "runtime": True})  # fmt: skip
    return out


_INSTALL_SYMBOL = re.compile(r"@([A-Za-z0-9_#$-]+)@")


def install_symbols(spec: Any) -> dict[str, str]:
    """#5089: the install symbols a case states (`"install_symbols": {"values": {"ECS_HLQ": "ZECS", ...}, "why": ...}`),
    as upper-case name -> value. zECS-style estates ship dataset names with placeholders (`@ecs_hlq@.ZCEXPIRE.
    @environment@`) that an install job fills in; the harness never guesses them -- the case states each one, with
    the reason (a deployment fact, as `csd` and `recovery` are). Absent: none. Anything else is refused by name."""
    if spec is None:
        return {}
    values = spec.get("values") if isinstance(spec, dict) else None
    if (
        not isinstance(values, dict)
        or not values
        or not spec.get("why")
        or set(spec) - {"values", "why"}
        or not all(
            isinstance(k, str) and re.fullmatch(r"[A-Za-z0-9_#$-]+", k)
            and isinstance(v, str) and re.fullmatch(r"[A-Z0-9#$-]{1,8}(\.[A-Z0-9#$-]{1,8})*", v)
            for k, v in values.items()
        )
    ):  # fmt: skip
        raise Unsupported(
            '"install_symbols": {"values": {SYMBOL: VALUE (a dataset qualifier, upper case)}, "why": ...}'
        )
    out = {k.upper(): v for k, v in values.items()}
    if len(out) != len(values):
        raise Unsupported(f'"install_symbols" states a symbol twice (names are not case-sensitive): {sorted(values)}')
    return out


def substitute_install_symbols(name: str, symbols: dict[str, str]) -> str:
    """#5089: `name` (upper-cased) with each `@SYMBOL@` the case states replaced; a symbol it does not state stays in
    the name and is refused by the caller (never guessed)."""
    return _INSTALL_SYMBOL.sub(lambda m: symbols.get(m.group(1).upper(), m.group(0)), name.upper())


def _cfg_file_name(case: dict[str, Any], f: dict[str, Any]) -> str:
    """The name the stub's files.cfg gives a CICS file: the CSD's template (`ZC@ID@KEY`) with the case's install symbols
    resolved (`ZC01KEY`), the name the program's FILE option holds at run time; unchanged without a stated symbol."""
    symbols = install_symbols(case.get("install_symbols"))
    return substitute_install_symbols(f["file"], symbols) if symbols else f["file"]


def stub_files(
    ir: Any,
    program_file: str,
    datasets: dict[str, Any] | None = None,
    symbols: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Each CICS file the program uses: {file, dsname, base (the cluster whose records it
    reads), key_offset, key_length, reclen, via}, from the engine's facts -- the CSD
    DEFINE FILE's DSNAME, then the IDCAMS DEFINE that keys it: a CLUSTER's KEYS, or a
    PATH -> its AIX's KEYS over the AIX's base cluster. Where the facts lack the KEYS or the
    RECORDSIZE (GenApp's adef121.jcl gives both inside the DATA(...) component), the case's
    dataset may state them ("vsam": {"key_offset", "key_length", "reclen"}); the facts win.
    #5089: `symbols` (install_symbols(case["install_symbols"])) resolve the `@NAME@` placeholders of a dataset name,
    on the CSD and the IDCAMS side alike; a placeholder the case does not state is refused, never guessed. An IDCAMS
    job the engine does not read as a define (zECS ships `ZCEXPIRE.idcams`, not JCL) is stated by the case's dataset
    of the resolved name (`vsam`, with its KEYS and RECORDSIZE)."""
    symbols = symbols or {}
    defines: dict[str, Any] = {}
    for f in ir.files.values():
        for d in f.vsam_defines:
            if d.name:
                defines.setdefault(substitute_install_symbols(d.name, symbols), d)
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
        if symbols:
            dsn = substitute_install_symbols(dsn, symbols)
            if _INSTALL_SYMBOL.search(dsn):
                raise Unsupported(
                    f"CICS file {e['name']}: the dataset name {dsn} holds an install symbol the case does not state"
                )
        d, via = defines.get(dsn), []
        if d is not None and d.kind == "PATH":
            via.append(f"PATH {d.name}")
            d = defines.get((d.related or "").upper())
        stated_vsam = ((datasets or {}).get(dsn) or {}).get("vsam")
        # #5089: a name resolved through the install symbols takes the case's stated vsam, also when the engine now
        # reads the IDCAMS job as a define (its name keeps the placeholders, so its base would not be the dataset's)
        if (d is None or stated_vsam) and symbols and dsn != defs[0]["dsname"].upper():
            vsam = stated_vsam or {}
            if not all(isinstance(vsam.get(k), int) for k in ("key_offset", "key_length", "reclen")) or not vsam.get(
                "why"
            ):
                raise Unsupported(
                    f"CICS file {e['name']}: no IDCAMS DEFINE for {dsn}; the case's dataset {dsn} states "
                    "vsam {key_offset, key_length, reclen, why} (the IDCAMS job's KEYS and RECORDSIZE)"
                )
            if (defs[0].get("record_format") or "").upper() == "V" and vsam.get("variable") is not True:
                raise Unsupported(  # the stub keeps fixed-length records: a V file is stood in for only when stated
                    f"CICS file {e['name']}: {dsn} is a variable-length file (RECORDFORMAT(V)); the stub keeps fixed-"
                    'length records, so the case\'s vsam must say "variable": true -- every record of the file is the '
                    "one length the program writes and reads, stated as reclen (IBM returns each record at its own length)"
                )
            out.append({"file": e["name"], "dsname": dsn, "base": dsn, "key_offset": vsam["key_offset"],
                        "key_length": vsam["key_length"], "reclen": vsam["reclen"],
                        "via": ["the case's install_symbols", "the case's vsam"]})  # fmt: skip
            continue
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
        base = substitute_install_symbols(d.name, symbols)  # #5089: the define's name with the case's install symbols
        stated = ((datasets or {}).get(base) or {}).get("vsam") or {}
        if key is d and (d.organization or "").upper() == "NONINDEXED":  # #4213: an ESDS: no key, browsed by RBA
            reclen = d.record_max if d.record_max is not None else stated.get("reclen")
            if reclen is None or (d.record_avg is not None and d.record_avg != reclen):
                raise Unsupported(f"CICS file {e['name']}: ESDS {d.name} without fixed-length records (RECORDSIZE)")
            out.append({"file": e["name"], "dsname": dsn, "base": base, "key_offset": 0, "key_length": 0,
                        "reclen": reclen, "via": via, "organization": "ESDS"})  # fmt: skip
            continue
        koff = key.key_offset if key.key_offset is not None else stated.get("key_offset")
        klen = key.key_length if key.key_length is not None else stated.get("key_length")
        reclen = d.record_max if d.record_max is not None else stated.get("reclen")
        if (defs[0].get("record_format") or "").upper() == "V" and stated.get("variable") is True:
            reclen = stated.get("reclen", reclen)  # #5089: a V file's records are all the one length the case states
        if koff is None or klen is None or reclen is None:
            raise Unsupported(f"CICS file {e['name']}: {key.name}'s KEYS or {d.name}'s RECORDSIZE is not in the facts")
        out.append({"file": e["name"], "dsname": dsn, "base": base, "key_offset": koff,
                    "key_length": klen, "reclen": reclen, "via": via})  # fmt: skip
    for f in out:
        # #5089: a CSD file name written with an install symbol (zECS: ZC@ID@FILE) is the resolved name at run time
        # (the program opens ZC01FILE), so the stub's files.cfg must carry that name or every READ is FILENOTFOUND
        f["file"] = substitute_install_symbols(f["file"], symbols)
    out += [r for r in case_runtime_files(datasets) if r["file"] not in {f["file"] for f in out}]
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
    if (usage or "").upper() == "POINTER" and not pic:
        # #4270 (C9): only NULL can be given -- binary zeros, on both sides; an address names storage neither side has
        if value is None or str(value).strip() in ("", common.POINTER_NULL):
            return bytes(nbytes)
        raise ValueError(
            f"a POINTER can only be given as {common.POINTER_NULL!r} (an address is not portable): {value!r}"
        )
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


def commarea_record(fields: list[dict[str, Any]], values: dict[str, Any], enc: str) -> bytes:
    """#4765: a scenario's COMMAREA, the whole record -- every occurrence of a table (`fields`: commarea_fields(...,
    occurrences=True)), each field not named INITIALIZEd, as INITIALIZE does a group's every occurrence. A value named
    as the DTO names it (COMM-EYE: an OCCURS group's field, listed once) is the first occurrence's (COMM-EYE(1))."""
    first = {f["base"]: f["name"] for f in fields if f.get("subscripts") and all(k == 1 for k in f["subscripts"])}
    width = {f["name"]: f["bytes"] for f in fields}
    named = {first.get(k, k): v for k, v in raw_commarea_bytes(values).items()}
    for k, v in named.items():
        if isinstance(v, bytes) and k in width and len(v) != width[k]:
            raise ValueError(f"COMMAREA {k}: hex is {len(v)} bytes, the field is {width[k]}")
    return encode_record(fields, named, b"init", enc)


def raw_commarea_bytes(values: dict[str, Any]) -> dict[str, Any]:
    """#6072: a COMMAREA value `{"hex": "F1F2..."}` is the field's raw bytes -- storage no PICTURE can say, such as
    letters in a PIC 9 field for an IS NUMERIC false arm. Every other value is returned as stated."""
    return {k: bytes.fromhex(v["hex"]) if isinstance(v, dict) and set(v) == {"hex"} else v for k, v in values.items()}


def raw_names_of(sc: dict[str, Any]) -> set[str]:
    """#6072: the scenario's COMMAREA fields stated as raw bytes (none when it has no COMMAREA)."""
    return raw_commarea_names(sc["commarea"]) if sc.get("commarea") is not None else set()


def raw_commarea_names(values: dict[str, Any]) -> set[str]:
    """#6072: the COMMAREA fields a scenario states as raw bytes."""
    return {k for k, v in values.items() if isinstance(v, dict) and set(v) == {"hex"}}


def decode_record(data: bytes, fields: list[dict[str, Any]], enc: str = common.DEFAULT_DATA_ENCODING,
                  keep_nulls: bool = False, exact: bool = False, unnamed: bool = False) -> dict[str, str]:  # fmt: skip
    """{field name: value as text} -- numeric fields as exact decimals, text with trailing
    spaces and nulls dropped (a screen shows neither). #3815: text and zoned bytes read in `enc`.
    `keep_nulls`: a text ending in LOW-VALUES kept whole -- a COMMAREA handed to the Java side, whose DTO codec pads
    with spaces: COTRTLIC's unfetched rows are LOW-VALUES, and the program protects exactly those.
    `exact` (#4635): a text keeps its LOW-VALUES -- only the trailing spaces are dropped -- so a field the task left
    LOW-VALUES and one it left spaces are different values, as they are to the next program (`IF X = SPACES OR
    LOW-VALUES` exists because they differ). For the COMMAREA a task returns; a screen still shows neither.
    #4765: a layout with every occurrence (layout_fields(..., occurrences=True)) is read by `data`'s own OCCURS
    DEPENDING ON counts (common.active_fields): an occurrence past its table's count is not part of the record.
    #4778 `unnamed`: a FILLER too, as its bytes (hex), keyed by where it lies (FILLER@217): a COMMAREA's FILLER is its
    caller's storage, which holds what the program left there (CBSA's CUSTCTRL DFHCOMMAREA ends in 217 bytes of it).
    Read so on both sides only when both are bytes: a DTO has no property for it (compare_events: `commarea_dto`)."""
    out = {}
    for f in common.active_fields(data, fields, enc):
        if f["name"] == "FILLER":  # unnamed: no DTO property holds it, and several would share one key
            raw = data[f["offset"] : f["offset"] + f["bytes"]]
            if unnamed and len(raw) == f["bytes"]:
                out[f"FILLER@{f['offset']}"] = raw.hex().upper()
            continue
        raw = data[f["offset"] : f["offset"] + f["bytes"]]
        if len(raw) < f["bytes"]:
            continue
        v = common.decode_field(raw, f["pic"], f["usage"], common.sign_page(enc), f.get("sign_separate", False),
                                enc)  # fmt: skip
        if v == common.POINTER_NULL and f["usage"] == "POINTER":
            # #4270 (C9): NULL is what the Java DTO carries as null (DetCics.pointerOut): absent, as `_same` reads it
            out[f["name"]] = None
        elif not isinstance(v, str):
            out[f["name"]] = str(v)
        else:
            if exact:
                out[f["name"]] = v.rstrip(" ")
            else:
                out[f["name"]] = v if keep_nulls and v.rstrip(" ").endswith("\x00") else v.rstrip(" \x00")
    return out


def justified(text: str, width: int, justify: str) -> str:
    """#5082 (X54): what BMS leaves in an input field whose DFHMDF says JUSTIFY=(LEFT|RIGHT[,BLANK|ZERO]) (IBM CICS TS,
    DFHMDF): the text typed, without its trailing blanks, at the left or right end of the field, the rest filled with
    blanks or zeros. The DFHMDF's JUSTIFY only: a field with none is the text as typed, as before."""
    typed = text.rstrip(" ")
    fill = "0" if "ZERO" in justify else " "
    if "RIGHT" in justify:
        return typed[-width:].rjust(width, fill)
    return typed[:width].ljust(width, fill)


@functools.lru_cache(maxsize=256)
def bms_justify(corpus: Path, map_name: str) -> dict[str, str]:
    """{symbolic input field (<name>I): its DFHMDF JUSTIFY, "RIGHT,ZERO"} of a map, from the corpus's BMS sources (the
    engine's own reading of them, gitgalaxy.core.bms_screen_fields); a map with no JUSTIFY field gives {}."""
    from gitgalaxy.core.bms_screen_fields import bms_screen_fields
    from gitgalaxy.core.source_text import read_source
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_screen_forge import _justify

    out: dict[str, str] = {}
    for p in sorted(corpus.rglob("*.bms")):
        if ".git" in p.parts:
            continue
        rows = bms_screen_fields(read_source(p).text)
        maps = {r["ordinal"] for r in rows if r["kind"] == "map" and (r["name"] or "").upper() == map_name.upper()}
        for r in rows:
            if r["kind"] == "field" and r["parent_ordinal"] in maps and r["name"] and _justify(r):
                out[r["name"].upper() + "I"] = _justify(r)
    return out


def map_input(fields: list[dict[str, Any]], values: dict[str, str], enc: str = common.DEFAULT_DATA_ENCODING,
              justify: dict[str, str] | None = None) -> bytes:  # fmt: skip
    """A RECEIVE MAP input area: nulls everywhere, and for each field the user typed in
    ({"ACCTSIDI": "00000000011"}) its data and its length (<name>L). `justify` (#5082): the fields whose DFHMDF
    says JUSTIFY, by symbolic name: their data is as BMS justifies it; the length is that of the text typed."""
    typed: dict[str, Any] = {}
    width = {f["name"]: f["bytes"] for f in fields}
    for field, text in values.items():
        if "(" in field:  # #5076: the Java side's typed values are keyed by the BMS name, not by a subscript
            raise Unsupported(f"RECEIVE MAP: {field} -- typing into one occurrence of a repeated field is not "
                              "modelled", ["BMS OCCURS input"])  # fmt: skip
        placed = (
            justified(text, width[field], justify[field]) if justify and field in justify and field in width else text
        )
        typed[field] = placed.encode(enc)  # what was typed, whatever the field's PICIN
        typed[field[:-1] + "L"] = len(text.rstrip())
    return encode_record(fields, typed, b"\x00", enc)


# FORMATTIME's date forms (IBM CICS TS, EXEC CICS FORMATTIME): the parts in order, and the separator's default
_DATE_FORMS = {"YYYYMMDD": ("GG-Y", "GG-M", "GG-D"), "MMDDYYYY": ("GG-M", "GG-D", "GG-Y"),
               "DDMMYYYY": ("GG-D", "GG-M", "GG-Y"), "YYMMDD": ("GG-Y(3:2)", "GG-M", "GG-D"),
               "MMDDYY": ("GG-M", "GG-D", "GG-Y(3:2)"), "DDMMYY": ("GG-D", "GG-M", "GG-Y(3:2)"),
               "YYDDD": ("GG-Y(3:2)", "GG-DOY"), "YYYYDDD": ("GG-Y", "GG-DOY"),
               "YYDDMM": ("GG-Y(3:2)", "GG-D", "GG-M"), "YYYYDDMM": ("GG-Y", "GG-D", "GG-M")}  # fmt: skip
# #4415 slice 3 (X46): the binary forms, each the COBOL expression of IBM's value (DAYCOUNT: 1 January 1900 is day 1;
# DAYOFWEEK: Sunday=0; GG-DAYS 0 is a Monday)
_NUMBER_FORMS = {"DAYCOUNT": "GG-DAYS + 1", "DAYOFMONTH": "GG-D", "DAYOFWEEK": "FUNCTION MOD(GG-DAYS + 1, 7)",
                 "MONTHOFYEAR": "GG-M", "YEAR": "GG-Y", "MILLISECONDS": "FUNCTION MOD({t}, 1000)"}  # fmt: skip


def _formattime(opts: dict[str, str]) -> list[str]:
    """FORMATTIME ABSTIME(t) [date forms] [DATESEP] [TIME] [TIMESEP], in COBOL: t split into the day number since
    1900-01-01 and the milliseconds into the day. DATESEP / TIMESEP without a value are '/' and ':'; absent, none."""
    _check_spec("FORMATTIME", opts, ("FORMATTIME",), lambda bad: ["FORMATTIME"])
    if not opts.get("ABSTIME"):
        raise Unsupported("FORMATTIME without ABSTIME", ["FORMATTIME"])
    t = opts["ABSTIME"]
    lines = [f"COMPUTE GG-DAYS = {t} / 86400000", f"COMPUTE GG-REM = {t} - GG-DAYS * 86400000",
             "COMPUTE GG-DATE8 = FUNCTION DATE-OF-INTEGER(GG-DAYS",
             "    + FUNCTION INTEGER-OF-DATE(19000101))",
             "COMPUTE GG-DOY = FUNCTION INTEGER-OF-DATE(GG-DATE8)",
             "    - FUNCTION INTEGER-OF-DATE(GG-Y * 10000 + 101) + 1",
             "COMPUTE GG-HH = GG-REM / 3600000", "COMPUTE GG-MI = (GG-REM - GG-HH * 3600000) / 60000",
             "COMPUTE GG-SS = (GG-REM - GG-HH * 3600000", "    - GG-MI * 60000) / 1000"]  # fmt: skip

    def sep(option: str, default: str) -> str | None:
        if option not in opts:
            return None
        return opts[option] or f"'{default}'"

    def build(parts: tuple[str, ...], separator: str | None, target: str) -> list[str]:
        pieces = []
        for i, p in enumerate(parts):
            if i and separator:
                pieces.append(separator)
            pieces.append(p)
        width = sum({"GG-Y": 4, "GG-DOY": 3}.get(p, 2) for p in parts) + (len(parts) - 1 if separator else 0)
        return (["MOVE SPACES TO GG-OUT", "STRING " + " ".join(pieces), "    DELIMITED BY SIZE INTO GG-OUT"]
                + [f"MOVE GG-OUT(1:{width}) TO {target}(1:{width})"])  # fmt: skip

    body: list[str] = []
    for form, parts in _DATE_FORMS.items():
        if opts.get(form):
            body += build(parts, sep("DATESEP", "/"), opts[form])
    for form, expr in _NUMBER_FORMS.items():
        if opts.get(form):
            body += [f"COMPUTE {opts[form]} = {expr.format(t=t)}"]
    if opts.get("TIME"):
        body += build(("GG-HH", "GG-MI", "GG-SS"), sep("TIMESEP", ":"), opts["TIME"])
    # #4737 (X28): IBM, INVREQ RESP2 1 "The ABSTIME value is less than zero or not in packed-decimal format": with RESP /
    # RESP2 nothing is formatted and the condition is the program's; without them INVREQ's handling is not modelled
    # (refused, as CicsTask refuses it)
    if not opts.get("RESP") and not opts.get("RESP2"):
        return [f"IF {t} < 0", "    DISPLAY 'FORMATTIME ABSTIME < 0 NO RESP: not modelled'",
                "    MOVE 98 TO RETURN-CODE", "    STOP RUN", "END-IF"] + lines + body  # fmt: skip
    return (["MOVE 0 TO GG-RESP", "MOVE 0 TO GG-RESP2", f"IF {t} < 0", "    MOVE 16 TO GG-RESP",
             "    MOVE 1 TO GG-RESP2", "ELSE"] + [f"    {ln}" for ln in lines + body] + ["END-IF"])  # fmt: skip


# ---- running a case -------------------------------------------------------------------
def csd_programs(corpus: Path, case: dict[str, Any]) -> list[str] | None:
    """The programs the case's CSD (its "csd": a DFHCSDUP listing in the corpus) defines, or None: every program
    is defined. With autoinstall off, an XCTL / LINK / INQUIRE of any other is PGMIDERR (CardDemo's admin menu
    lists COTRTLIC / COTRTUPC, which its base CSD does not define: 'This option is not installed ...')."""
    if not case.get("csd"):
        return None
    text = (corpus / case["csd"]).read_text(encoding="latin-1")
    return sorted(set(re.findall(r"DEFINE\s+PROGRAM\(([A-Z0-9@#$]{1,8})\)", text)))


def csd_tdqueues(corpus: Path, case: dict[str, Any]) -> list[str] | None:
    """The transient-data queues the case's CSD defines (DEFINE TDQUEUE), or None: every queue is defined."""
    types = csd_tdqueue_types(corpus, case)
    return None if types is None else sorted(types)


def csd_tdqueue_types(corpus: Path, case: dict[str, Any]) -> dict[str, str] | None:
    """#5079 (X57): each queue the CSD defines and its TYPE (INTRA, EXTRA, INDIRECT, REMOTE; "" when the definition
    states none), or None: every queue is defined. A queue defined twice keeps its last TYPE."""
    if not case.get("csd"):
        return None
    text = (corpus / case["csd"]).read_text(encoding="latin-1")
    out: dict[str, str] = {}
    for m in re.finditer(r"DEFINE\s+TDQUEUE\(([A-Z0-9@#$]{1,4})\)(.*?)(?=\bDEFINE\b|\Z)", text, re.S):
        kind = re.search(r"\bTYPE\(\s*([A-Z]+)\s*\)", m.group(2))
        out[m.group(1)] = kind.group(1) if kind else ""
    return out


_TD_ATTRS = ("RECOVSTATUS", "TYPEFILE", "OPENTIME", "INDIRECTNAME", "TRIGGERLEVEL", "TRANSID")


def csd_tdqueue_attrs(corpus: Path, case: dict[str, Any]) -> dict[str, dict[str, str]]:
    """#5168 (X61): the attributes of each DEFINE TDQUEUE beyond its TYPE that decide what a transient-data command does
    (RECOVSTATUS, TYPEFILE, OPENTIME, INDIRECTNAME, TRIGGERLEVEL, TRANSID), only those the definition states; a queue defined
    twice keeps its last. Empty when the case has no CSD."""
    if not case.get("csd"):
        return {}
    text = (corpus / case["csd"]).read_text(encoding="latin-1")
    out: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"DEFINE\s+TDQUEUE\(([A-Z0-9@#$]{1,4})\)(.*?)(?=\bDEFINE\b|\Z)", text, re.S):
        found = {k: v.upper() for k in _TD_ATTRS if (a := re.search(rf"\b{k}\(\s*([A-Z0-9@#$]+)\s*\)", m.group(2)))
                 for v in [a.group(1)]}  # fmt: skip
        out[m.group(1)] = found
    return {q: a for q, a in out.items() if a}


def td_seed(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, list[str]]:
    """#5168 (X61): the transient-data queues' records when the task starts ({"QUEUE": [record text, ...]}), the scenario's "td",
    else the case's: an intrapartition queue's, or an open extrapartition input queue's data set. Text the data's encoding holds
    whole (the stub gets its bytes in that encoding, CicsTask the text); a character the page lacks is refused."""
    seed = sc.get("td", case.get("td")) or {}
    enc = common.data_encoding(case)
    for q, items in seed.items():
        if not (0 < len(q) <= 4 and q.isascii() and isinstance(items, list) and all(isinstance(i, str) for i in items)):
            raise Unsupported(
                f'scenario {sc.get("name")}: "td" maps a queue name (1-4, ASCII) to a list of record texts'
            )
        for i in items:
            try:
                whole = i.encode(enc).decode(enc) == i
            except UnicodeError:
                whole = False
            if not whole:
                raise Unsupported(f'scenario {sc.get("name")}: "td" record {i!r} does not round-trip through {enc}')
    return seed


def commarea_fields(corpus: Path, case: dict[str, Any], occurrences: bool = False) -> list[dict[str, Any]]:
    """The COMMAREA layout: the case's (copybook, record) segments laid end to end. A segment in a program's
    own source (CardDemo's COUSR02C: COPY COCOM01Y then its own 05 items in the same 01) finds the COPY
    members in the case's copy_dirs. #4765 `occurrences`: every occurrence of an OCCURS item a field of its own
    (layout_fields): the layout a COMMAREA a task leaves is READ by, so a table is compared whole; without it, the
    layout a scenario's COMMAREA is built from (its fields as the DTO names them)."""
    if "commarea" not in case:
        raise Unsupported('the case does not describe its COMMAREA: "commarea": {"segments": [...]}, or "commarea": '
                          "null for a program that takes none", ["COMMAREA"])  # fmt: skip
    if case["commarea"] is None:  # #4270: the program takes no COMMAREA (an empty LINKAGE SECTION): EIBCALEN 0
        return []
    if not case["commarea"].get("segments"):
        raise Unsupported('"commarea": {"segments": []} describes nothing: "commarea": null for a program that takes '
                          "none", ["COMMAREA"])  # fmt: skip
    out, at = [], 0
    for seg in case["commarea"]["segments"]:
        src = corpus / seg["copybook"]
        dirs = [src.parent, *(corpus / d for d in case.get("copy_dirs", [])), corpus]
        fields = common.layout_fields(corpus, seg["copybook"], seg["record"], dirs, occurrences)
        out += [dict(f, offset=f["offset"] + at) for f in fields]
        at += max(f["offset"] + f["bytes"] for f in fields)
    return out


def commarea_length(sc: dict[str, Any], ca_fields: list[dict[str, Any]]) -> int | None:
    """#4270 (oracle_assumptions.md X23): a scenario's stated EIBCALEN, `"commarea_length": N` -- the caller passed
    the first N bytes of the COMMAREA record and no more (GenApp's `IF EIBCALEN < 91`, its '98' "COMMAREA too short"
    returns). Both sides give the program exactly N bytes: the stub's guard page (GGCAREA) and the det port's
    DFHCOMMAREA (CicsTask.withExactCommarea) stop a reference past them, judged up to it. None when not stated.
    #4049: 0 is EIBCALEN 0 with the COMMAREA record present (a program that tests EIBCALEN first, COSGN00C, takes its
    first-entry branch; one that touches DFHCOMMAREA is stopped at the reference, as for any shorter length)."""
    n = sc.get("commarea_length")
    if n is None:
        return None
    whole = max((f["offset"] + f["bytes"] for f in ca_fields), default=0)
    if sc.get("commarea") is None or not ca_fields:
        raise Unsupported(f"scenario {sc['name']}: a commarea_length with no COMMAREA", ["COMMAREA"])
    if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= whole:
        raise Unsupported(f"scenario {sc['name']}: commarea_length {n!r} is not a length of the {whole}-byte COMMAREA "
                          "(0 to its length)", ["COMMAREA"])  # fmt: skip
    return n


def untyped_commarea(case: dict[str, Any], sc: dict[str, Any], ca_fields: list[dict[str, Any]]) -> bytes | None:
    """#5859 (ZECSNC, an HLASM program: its DSECT is no copybook, so the case has `"commarea": null` and no layout): a
    scenario's `"commarea_hex": "<hex>"` is the exact bytes the caller passed (in the case's data page, as the stub
    reads them; the port gets them in the region's), so EIBCALEN is their count -- the
    shorter, longer or exact lengths a program tests EIBCALEN against. Both sides get those bytes and no more
    (commarea.exact / CicsTask(..., byte[], length)). None when the scenario states none; refused by name when it is
    not hex, is empty (EIBCALEN 0 is the absence of the key), or mixes with a typed COMMAREA."""
    raw = sc.get("commarea_hex")
    if raw is None:
        return None
    name = sc.get("name")
    if ca_fields or case.get("commarea") is not None:
        raise Unsupported(f'scenario {name}: "commarea_hex" is for a case with "commarea": null (no layout); '
                          'a typed COMMAREA states "commarea" / "commarea_length"', ["COMMAREA"])  # fmt: skip
    if sc.get("commarea") is not None or sc.get("commarea_length") is not None:
        raise Unsupported(f'scenario {name}: "commarea_hex" with "commarea" / "commarea_length"', ["COMMAREA"])
    if not isinstance(raw, str) or not raw or not re.fullmatch(r"(?:[0-9A-Fa-f]{2})+", raw):
        raise Unsupported(f'scenario {name}: "commarea_hex" is a non-empty string of hex byte pairs (EIBCALEN 0: '
                          "state no COMMAREA)", ["COMMAREA"])  # fmt: skip
    return bytes.fromhex(raw)


# #4950 (X18): the characters IBM's PUT CONTAINER page allows in a channel / container name ("A-Z a-z 0-9 $ @ # / % ?
# ! : | " = , ; > . - and _"). RUN TRANSID's page also lists & < and the not sign, PUT CONTAINER's does not: the pages
# disagree, so the harness refuses them, as both runtimes do (ggcics.c, the forge's NAME_CHARS)
_CICS_NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "abcdefghijklmnopqrstuvwxyz" + "0123456789" + '$@#/%?!:|"=,;>.-_'


def _cics_name_problem(name: Any) -> str | None:
    """Why `name` is not a channel / container name the harness hands both runtimes, or None when it is."""
    if not isinstance(name, str) or not 1 <= len(name) <= 16:
        return "a name of 1 to 16 characters"
    for ch in name:
        if ch in "&<\u00ac":
            return (f"character {ch!r}: IBM's RUN TRANSID page allows it, its PUT CONTAINER page does not "
                    "(the pages disagree, so it is refused)")  # fmt: skip
        if ch not in _CICS_NAME_CHARS:
            return f"character {ch!r}, outside IBM's set (A-Z a-z 0-9 $ @ # / % ? ! : | \" = , ; > . - _; no blank)"
    return None


def scenario_channel(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any] | None:
    """#4270 (oracle_assumptions.md X24): the channel a scenario's task starts with -- `"channel": {"name": N,
    "containers": {C: {"text": T | "hex": H, "datatype": "BIT" | "CHAR"}}}`, what a RUN TRANSID CHANNEL parent or a
    LINK CHANNEL caller passed (the async credit-card services' MYCHANNEL / INPUTCONTAINER). Both sides make it the
    first program's current channel. Text is in the case's data page; the data type defaults to BIT, as PUT
    CONTAINER's does. {"name", "containers": [{"name", "data": bytes, "bit"}]}, None when not stated."""
    ch = sc.get("channel")
    if ch is None:
        return None
    where = f"scenario {sc['name']}: channel"
    if not isinstance(ch, dict):
        raise Unsupported(f"{where}: an object with a name", ["CHANNEL"])
    problem = _cics_name_problem(ch.get("name", ""))
    if problem:
        raise Unsupported(f"{where} name {ch.get('name')!r}: {problem}", ["CHANNEL"])
    out = []
    for name, spec in (ch.get("containers") or {}).items():
        problem = _cics_name_problem(name)
        if problem:
            raise Unsupported(f"{where} container {name!r}: {problem}", ["CHANNEL"])
        if not isinstance(spec, dict) or ("text" in spec) == ("hex" in spec):
            raise Unsupported(f"{where} container {name!r}: one of text / hex", ["CHANNEL"])
        if spec.get("datatype", "BIT") not in ("BIT", "CHAR"):
            raise Unsupported(f"{where} container {name}: datatype BIT or CHAR", ["CHANNEL"])
        data = spec["text"].encode(common.data_encoding(case)) if "text" in spec else bytes.fromhex(spec["hex"])
        out.append({"name": name, "data": data, "bit": spec.get("datatype", "BIT") == "BIT"})
    return {"name": ch["name"], "containers": out}


def _channel_json(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, Any] | None:
    """The scenario's channel (scenario_channel) as the generated Java test reads it: each container's bytes in hex."""
    chan = scenario_channel(case, sc)
    if chan is None:
        return None
    return {"name": chan["name"], "containers": [{"name": k["name"], "hex": k["data"].hex().upper(), "bit": k["bit"]}
                                                 for k in chan["containers"]]}  # fmt: skip


def case_child_programs(case: dict[str, Any]) -> dict[str, str]:
    """#4950: the program each transaction a RUN TRANSID child may run runs (`"child_programs": {TRANSID: PROGRAM}`, a
    deployment fact the case states, as the CSD's TRANSACTION definitions give it); each program one of the case's
    "programs". Absent, none: a child the parent's wait would dispatch is refused (both runtimes)."""
    kids = case.get("child_programs")
    if kids is None:
        return {}
    programs = {x["program"].upper() for x in case.get("programs", [])}
    if not isinstance(kids, dict) or not all(
        isinstance(t, str) and re.fullmatch(r"[A-Z0-9@#$]{1,4}", t) and isinstance(p, str) and p.upper() in programs
        for t, p in kids.items()
    ):
        raise Unsupported('"child_programs": {TRANSID: PROGRAM}, each program one of the case\'s "programs"',
                          ["RUN TRANSID"])  # fmt: skip
    return {t: p.upper() for t, p in kids.items()}


# #4950 (X18, R1): what a RUN TRANSID child may not do -- a region resource the stub keeps no event of; the rest
# (files, queues, START, a terminal) both runtimes refuse at the command
_CHILD_STATIC = re.compile(
    r"(?is)\bEXEC\s+(?:SQL\b|CICS\s+(?:ENQ|DEQ|(?:GET|UPDATE|DELETE|DEFINE|QUERY|REWIND)\s+D?COUNTER)\b)"
)


_CHILD_ENQ = re.compile(r"(?is)\bEXEC\s+CICS\s+(ENQ|DEQ)\b(.*?)\bEND-EXEC")


def _task_private_enq(source: str, body: str) -> bool:
    """#5089: an ENQ / DEQ that no other task can contend for -- RESOURCE names a data area (no LENGTH: IBM then serialises on
    the area's ADDRESS, "it is the location (address) of the data area in storage that matters, not its contents") that the
    program declares in its own WORKING-STORAGE, which every task has its own copy of. Such a resource is held by this task
    alone whatever else runs, so the command is unobservable: no event, no order against a parent or a sibling."""
    m = re.search(r"(?is)\bRESOURCE\s*\(\s*([A-Z0-9][A-Z0-9-]*)\s*\)", body)
    if not m or re.search(r"(?i)\bLENGTH\s*\(", body):
        return False
    ws = re.split(r"(?im)^.{6} +LINKAGE\s+SECTION\.", source, maxsplit=1)[0]
    ws = re.split(r"(?im)^.{6} +WORKING-STORAGE\s+SECTION\.", ws, maxsplit=1)
    return len(ws) == 2 and bool(re.search(rf"(?im)^.{{6}} +\d{{1,2}}\s+{re.escape(m.group(1))}(?=[\s.])", ws[1]))


def child_region_resource(source: str) -> str | None:
    """#4950 (X18, R1) / #5089: the first statement of a RUN TRANSID child's program that holds a region resource with no
    event of its own (SQL, a counter, an ENQ / DEQ another task could contend for), as its text; None when there is none."""
    private = {m.start(): _task_private_enq(source, m.group(2)) for m in _CHILD_ENQ.finditer(source)}
    for m in _CHILD_STATIC.finditer(source):
        if not private.get(m.start()):
            return m.group(0)
    return None


def case_transactions(case: dict[str, Any]) -> list[str]:
    """#4270: the transactions the case's region defines (`"transactions": [...]`, a deployment fact the case states:
    RUN TRANSID / START of any other is TRANSIDERR); absent, every transaction is defined, as before."""
    tx = case.get("transactions")
    if not isinstance(tx, list) or not all(isinstance(t, str) and re.fullmatch(r"[A-Z0-9@#$]{1,4}", t) for t in tx):
        raise Unsupported('"transactions": a list of 1- to 4-character transaction ids', ["TRANSACTIONS"])
    return sorted(set(tx))


def task_containers(path: Path) -> dict[str, Any] | None:
    """#4270 (X24): the stub's containers.out (GGCEND: the first program's current channel at task end, `CHANNEL N`
    then `NAME HEX` per container) as the CONTAINERS event compares it; None when the task had no current channel."""
    if not path.is_file():
        return None
    lines = path.read_text(encoding="ascii").splitlines()
    containers = {}
    for ln in lines[1:]:
        name, _, data = ln.partition(" ")
        containers[name] = data.strip().upper()
    return {"channel": lines[0].split(" ", 1)[1].strip(), "containers": containers}


def screen_fields(corpus: Path, case: dict[str, Any], map_name: str, side: str) -> list[dict[str, Any]]:
    scr = case["screens"][map_name]
    return screen_layout(corpus, str(common.case_path(corpus, scr["copybook"])), scr[side])


def screen_layout(corpus: Path, copybook: str, record: str) -> list[dict[str, Any]]:
    """A symbolic map's layout (one side's record), as a screen is compared: every occurrence of a repeated field
    (BMS OCCURS=, an OCCURS in its symbolic map) is a field of its own, named by its subscript (ACCOUNTO(3)), as a
    COMMAREA's (#4765) is -- a compare that read only the first would call a differing second occurrence equal
    (#4778, #5076). `screen_key` gives each its screen name. An OCCURS DEPENDING ON in a map is refused by name: a
    generated symbolic map has none, and which occurrences a screen holds would be a guess."""
    fields = common.layout_fields(corpus, copybook, record, occurrences=True)
    if any(f.get("odo") for f in fields):
        raise Unsupported(f"{record} ({copybook}): a symbolic map with OCCURS DEPENDING ON -- which occurrences the "
                          "screen holds is not stated", ["BMS OCCURS DEPENDING ON"])  # fmt: skip
    return fields


def screen_key(f: dict[str, Any]) -> tuple[str, str]:
    """(screen name, kind letter) of a symbolic-map field: ACCOUNTO(3) -> ("ACCOUNT.3", "O"), COMPANYO -> ("COMPANY",
    "O"). The name is the BMS field's, the occurrence after a dot, as the generated screen's screenValues() keys it."""
    base = f.get("base") or f["name"]
    return base[:-1] + "".join(f".{k}" for k in f.get("subscripts") or []), base[-1:]


# #4023 follow-up: the conditions a scenario may inject, by name -> their DFHRESP numbers (the spec's, #4270 spec PR 3)
CICS_RESP = {c: DFHRESP[c] for c in ("NORMAL", "FILENOTFOUND", "NOTFND", "DUPREC", "DUPKEY", "INVREQ", "IOERR", "NOSPACE",
                                     "NOTOPEN", "ILLOGIC", "LENGERR", "PGMIDERR", "NOTAUTH", "DISABLED", "LOADING",
                                     "ENDFILE", "TERMIDERR", "ITEMERR", "TRANSIDERR", "QIDERR", "SYSIDERR",
                                     "ISCINVREQ", "LOCKED", "ENQBUSY", "QBUSY", "INVMPSZ", "TSIOERR", "EXPIRED", "USERIDERR")}  # fmt: skip


def case_file_records(case: dict[str, Any], corpus: Path, spec: dict[str, Any], reclen: int, enc: str) -> bytes:
    """A CICS file's records: its dataset's `input`, then (#4049) the records of `append` -- a case's own file of
    records added after the corpus's (the test-strengthening loop's new accounts, customers ...)."""
    data = common._fixed(common._input_path(case, corpus, spec["input"]), reclen, enc)
    if spec.get("append"):
        data += common._fixed(common._input_path(case, corpus, spec["append"]), reclen, enc)
    return data


def scenario_datasets(case: dict[str, Any], sc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """#4622: the datasets this scenario's task starts with that differ from the case's -- the scenario's "datasets",
    {DD: {"input": path, "append": path}} (a path as in the case's own dataset, `@case/...` included), each DD's spec
    the case's with those keys replaced. A file the corpus has one card per account of cannot show a page that ends
    on the file's last record; the scenario then states a file that does. Unstated, {} (the case's files)."""
    out: dict[str, dict[str, Any]] = {}
    for dd, over in (sc.get("datasets") or {}).items():
        base = (case.get("datasets") or {}).get(dd)
        if base is None or not isinstance(over, dict) or not set(over) <= {"input", "append"}:
            raise Unsupported(f'scenario {sc.get("name")}: "datasets" overrides a dataset of the case ({dd!r}) with '
                              '{"input": path, "append": path}')  # fmt: skip
        if base.get("input") == "@generate":
            raise Unsupported(
                f"scenario {sc.get('name')}: {dd} is generated (`@generate`), so no scenario file replaces it"
            )
        out[dd] = {**{k: v for k, v in base.items() if k != "append"}, **over}
    return out


def stage_scenario_inputs(case: dict[str, Any], corpus: Path, files: list[dict[str, Any]], inputs: Path) -> None:
    """#4622: the Java side's input of each file a scenario states its own records for (`inputs/<DD>.<scenario>.in`),
    built from those stated records: the bytes the COBOL task started with. #6839 (row A): it was copied from the
    COBOL scenario's files/ copy, which is that task's working file -- the stub updates it in place, so after the
    COBOL run it held the task's end state (a DELETE already done, a WRITE already there) and the Java task started
    from another file (ZECS001's DELETE of a stored key answered 204; ZECS000's expiry scenarios ran on files the
    COBOL task had already pruned)."""
    enc = common.data_encoding(case)
    reclens = {f["base"]: f["reclen"] for f in files}
    for sc in case["scenarios"]:
        for base, over in scenario_datasets(case, sc).items():
            data = case_file_records(case, corpus, over, reclens[base], enc)
            (inputs / f"{base}.{sc['name']}.in").write_bytes(data)


def sql_first_id(table: str) -> int:
    """#4270: the first GG-SQL-ID (PIC 9(4)) of the next program's statements in a task's shared table: the next
    hundred after the ids already taken. A range per program by its place in "programs" (1000 x its index) ran past
    9999 at the tenth program (GenApp's LGTESTP1 LINKs twelve), and the id MOVEd into 9(4) lost its high digit."""
    ids = [int(ln.split()[1]) for ln in table.splitlines() if ln.startswith("S ")]
    return (max(ids, default=0) // 100 + 1) * 100


RECOVER: dict[str, Any] = {}  # #4173: a COBOL work area -> its coverage recomputed for the tasks judged


def run_cobol_cics(case: dict[str, Any], corpus: Path, work: Path, files: list[dict[str, Any]],
                   keep: frozenset[str] = frozenset()) -> dict[str, Any]:  # fmt: skip
    """Translate, compile and run each scenario; {scenario: its outputs} (see `outputs`)."""
    work.mkdir(parents=True, exist_ok=True)
    src = work / "src"
    src.mkdir(exist_ok=True)
    common.stage_copybooks(case, corpus, src)
    for p in STUB.iterdir():
        shutil.copy(p, src / p.name)
    if not (src / "CEEIGZCT.cpy").exists():  # #4950: the det translator's LE stand-in, where the estate has none (L4)
        shutil.copy(DET_COPY / "CEEIGZCT.cpy", src / "CEEIGZCT.cpy")
    shutil.copy(common.CASES / "faults" / "ggdisplay.c", src / "ggdisplay.c")  # #4635: DISPLAY as IBM writes it
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
        source = mark_sql_abends(case, source, table, case["program"])
        if not keep:  # #5882: a second pass keeps the first's tables (each task resets them first, identities too):
            equivalence_db2.create(case, corpus)  # what its tasks find is what they found after the first pass's
        (work / "stmts.txt").write_text(table, encoding="latin-1")
        (work / "reset.sql").write_text(equivalence_db2.reset_script(case, corpus), encoding="latin-1")
        shutil.copy(equivalence_db2.STUB, src / "ggsql.c")
        shutil.copy(equivalence_db2.RUNNER, src / "ggsqlrun.c")
        for t in db2.get("compare", []):
            names = equivalence_db2.columns(t)
            dumps.append((t, equivalence_db2.dump_query(t, names), names))
    text, has_commarea = translate(source, [src])
    (src / "PROGRAM.cbl").write_text(text, encoding=staged)
    (src / "EQCICSDR.cbl").write_text(cics_driver(case["program"], has_commarea), encoding="ascii")
    (work / "files.cfg").write_text("".join(
        f"{_cfg_file_name(case, f)} /work/files/{f['base']} {f['reclen']} {f['key_offset']} {f['key_length']}{_cfg_flags(case, f)}\n"
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
    ca_fields = commarea_fields(corpus, case, occurrences=True)  # #4765: the whole record, every occurrence
    # The COBOL programs the program CALLs (COTRN02C -> CSUTLDTC), as they are, and the LE service models
    # (tests/equivalence/le: CEEDAYS) they may call in turn.
    subs = []
    linked_programs_cov: list[dict[str, Any]] = []  # #5084: each program the task CALLs / LINKs, for its coverage
    for rel in case.get("subprograms", []):
        sub_text, _ = common.read_program(case, corpus / rel)
        name = Path(rel).stem.upper()
        (src / f"SUB{name}.cbl").write_text(common.compile_options(case, sub_text)[0], encoding=staged)
        subs.append(f"src/SUB{name}.cbl")
        linked_programs_cov.append({"name": name, "source": corpus / rel, "original": sub_text,
                                    "compiled": common.compile_options(case, sub_text)[0],
                                    "compiled_name": f"SUB{name}.cbl"})  # fmt: skip
    # (#4950: or the program itself CALLs one -- CBSA CRECUST's CEEDAYS / CEELOCT; #5076: or a program it LINKs in the
    # task does, BNK1CCS -> CRECUST)
    le_call = re.compile(
        r"(?i)\bCALL\s+['\"]CEE|\bCOPY\s+CSDB2RPY\b|\bDSNTIAC\b|\bZUIDSTCK\b"
    )  # #5858: DSNTIAC's model too; #5945: ZUIDSTCK's
    calls_le = le_call.search(source) or any(
        le_call.search(common.read_program(case, corpus / extra["program_source"])[0])
        for extra in case.get("programs", [])
    )
    for model in sorted(LE_MODELS.glob("*.c")) if subs or calls_le else []:
        shutil.copy(model, src / model.name)
        subs.append(f"src/{model.name}")
    refuse_dli_call_interface(source)
    if DLI_CALL.search(source):  # #5278 (register I5): the DL/I model, its databases stated in the case's "ims"
        if not case.get("ims"):
            raise Unsupported('EXEC DLI in a case with no "ims" section', ["EXEC DLI"])
        shutil.copy(equivalence_ims.STUB, src / "ggdli.c")
        subs.append("src/ggdli.c")
    if equivalence_mq.MQ_CALL.search(source):  # #4892 (register W): the MQ model, and the stand-ins the estate lacks
        shutil.copy(equivalence_mq.MODEL, src / equivalence_mq.MODEL.name)
        subs.append(f"src/{equivalence_mq.MODEL.name}")
        for name in equivalence_mq.STAND_INS:
            if not (src / f"{name}.cpy").exists():
                shutil.copy(DET_COPY / f"{name}.cpy", src / f"{name}.cpy")
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
            stmts_file = work / "stmts.txt"
            have = stmts_file.read_text(encoding="latin-1")
            first = sql_first_id(have)
            try:
                x_source, x_table = equivalence_sql.precompile(x_source, x_dirs, corpus / extra["program_source"],
                                                               first_id=first, program=extra["program"])  # fmt: skip
            except equivalence_sql.Unsupported as e:
                raise Unsupported(f"{extra['program']}: EXEC SQL: {e}", ["EXEC SQL"]) from e
            x_source = mark_sql_abends(case, x_source, x_table, extra["program"])
            if any(int(ln.split()[1]) > 9999 for ln in x_table.splitlines() if ln.startswith("S ")):
                raise Unsupported(f"{extra['program']}: EXEC SQL: the task's statements outnumber GG-SQL-ID's 4 digits")
            ours = {ln.split()[5] for ln in have.splitlines() if ln.startswith("S ") and ln.split()[5] != "-"}
            theirs = {ln.split()[5] for ln in x_table.splitlines() if ln.startswith("S ") and ln.split()[5] != "-"}
            if ours & theirs:
                raise Unsupported(f"{extra['program']}: cursor {sorted(ours & theirs)[0]} declared by two programs")
            stmts_file.write_text(have + x_table, encoding="latin-1")
        if extra["program"].upper() in case_child_programs(case).values() and child_region_resource(x_source):
            what = " ".join(child_region_resource(x_source).split()[1:]).upper()
            raise Unsupported(f"{extra['program']}: a RUN TRANSID child's {what} (a region resource): its order "
                              "against its parent's and its siblings' commands is not modelled", ["RUN TRANSID"])  # fmt: skip
        x_translated, x_ca = translate(x_source, [src])
        name = extra["program"].upper()
        (src / f"{name}.cbl").write_text(x_translated, encoding=staged)
        subs.append(f"src/{name}.cbl")
        linked[name] = x_ca
        linked_programs_cov.append({"name": name, "source": corpus / extra["program_source"], "original": x_text,
                                    "compiled": x_translated, "compiled_name": f"{name}.cbl"})  # fmt: skip
    if case_child_programs(case):  # #4950: a RUN TRANSID child runs its program through the dispatcher
        (src / "EQCICSDR.cbl").write_text(cics_driver(case["program"], has_commarea, True), encoding="ascii")
    if "CALL 'GGCRUN'" in text or linked:  # a LINK: the level's dispatcher, running the case's other programs
        (src / "GGCRUN.cbl").write_text(task_dispatcher(linked), encoding="ascii")
        subs.append("src/GGCRUN.cbl")
    common.comp5_layout_guard(src)  # #4751: a 1- or 2-digit COMP-5 is one byte in GnuCOBOL, a halfword on z/OS (C16)
    common.stage_zero_length_conf(case, src)  # X8: a case that lets a zero-length reference modification through
    compile_task = (
        f"cobc -x -std=ibm -fsign=EBCDIC -fstatic-call {cov.TRACE_FLAG} {''.join(f + ' ' for f in option_flags)}"
        f"-I /work/src -o task src/EQCICSDR.cbl src/PROGRAM.cbl {''.join(s + ' ' for s in subs)}src/ggcics.c"
    )
    if db2:
        compile_task += f" src/ggsql.c {equivalence_db2.COBOL_LINK}"
    script = [
        "set -e",
        "cd /work",
        compile_task,
        "gcc -shared -fPIC -O2 -o /work/ggdisplay.so src/ggdisplay.c -ldl",
    ]  # #4635 (as batch, #4056)
    if db2:
        script.append(f"gcc -O2 -o ggsqlrun src/ggsqlrun.c {equivalence_db2.COBOL_LINK}")
    programs = csd_programs(corpus, case)
    tdqueues = csd_tdqueue_types(corpus, case)
    if "'APPLID' TO GG-NAME2" in text or "'SYSID' TO GG-NAME2" in text:
        if not (case.get("region") or {}).get("applid") or not case["region"].get("sysid"):
            raise Unsupported('ASSIGN APPLID / SYSID: the case states no region ("region": {"applid", "sysid"})')
    sql_table = (work / "stmts.txt").read_text(encoding="latin-1") if db2 else ""
    for sc in case["scenarios"]:  # #4173: each task's SQL faults resolved to the statements they name
        if sc.get("sql_faults") and not db2:
            raise Unsupported(f'scenario {sc["name"]}: SQL faults in a case with no "db2" section')
        sc["sql_plan"] = sql_fault_plan(case, sc, sql_table) if sc.get("sql_faults") else []
    # #5882: `keep` names the tasks a first pass (#4173) already ran in this `work`: their directories (outputs, traces,
    # logs) are kept and they are not run again -- each task runs alone (its own files, the tables reset first, its own
    # clock and task number), so a second run of it is the first one again. Only the new tasks (the derived SQL-fault
    # ones) are staged and run; the binary is compiled and the tables created as before. Every other directory starts
    # afresh (the logs append).
    if keep:
        for d in (work / "scenarios").glob("*"):
            if d.name not in keep:
                shutil.rmtree(d, ignore_errors=True)
    else:
        shutil.rmtree(work / "scenarios", ignore_errors=True)
    for sc in case["scenarios"]:
        if sc["name"] in keep:
            continue
        d = work / "scenarios" / sc["name"]
        (d / "out").mkdir(parents=True, exist_ok=True)
        # each task its own copy of the files: what it writes is its own, and is compared (file updates)
        shutil.copytree(work / "files", d / "files", dirs_exist_ok=True)
        for f in files:  # #4622: a file this scenario states its own records for
            over = scenario_datasets(case, sc).get(f["base"])
            if over is not None:
                (d / "files" / f["base"]).write_bytes(case_file_records(case, corpus, over, f["reclen"], enc))
        (d / "files.cfg").write_text("".join(
            f"{_cfg_file_name(case, f)} /work/scenarios/{sc['name']}/files/{f['base']} {f['reclen']} {f['key_offset']} "
            f"{f['key_length']}{_cfg_flags(case, f)}\n" for f in files
        ), encoding="ascii")  # fmt: skip
        raw_area = untyped_commarea(case, sc, ca_fields)
        if raw_area is not None:  # #5859: the caller's bytes as stated; the stub gives the program exactly these
            (d / "commarea.exact").write_text(f"{len(raw_area)}\n", encoding="ascii")
            (d / "commarea.in").write_bytes(raw_area)
        elif sc.get("commarea") is not None:
            if not ca_fields:
                raise Unsupported(f'scenario {sc["name"]}: a COMMAREA, in a case whose program takes none ("commarea": '
                                  "null)", ["COMMAREA"])  # fmt: skip
            area = commarea_record(ca_fields, sc["commarea"], enc)
            calen = commarea_length(sc, ca_fields)
            if calen is not None:  # #4270 (X23): the stub gives the program exactly those bytes (GGCAREA)
                area = area[:calen]
                (d / "commarea.exact").write_text(f"{calen}\n", encoding="ascii")
            (d / "commarea.in").write_bytes(area)
        chan = scenario_channel(case, sc)
        if chan is not None:  # #4270 (X24): the channel the task starts with (GGCCHIN)
            (d / "channel.cfg").write_text(f"{chan['name']}\n" + "".join(
                f"{k['name']} {'BIT' if k['bit'] else 'CHAR'} {k['data'].hex().upper() or '-'}\n"
                for k in chan["containers"]), encoding="ascii")  # fmt: skip
        if case.get("transactions") is not None:  # #4270: the CSD's transactions (RUN TRANSID / START's TRANSIDERR)
            (d / "transactions.cfg").write_text("".join(f"{t}\n" for t in case_transactions(case)), encoding="ascii")
        if case_child_programs(case):  # #4950: the program a RUN TRANSID child runs
            (d / "childprogs.cfg").write_text("".join(f"{t} {p}\n" for t, p in case_child_programs(case).items()),
                                              encoding="ascii")  # fmt: skip
        if urimaps(case, sc) is not None:  # #4270 zECS (X32): INQUIRE URIMAP's installed definitions
            (d / "urimaps.cfg").write_text("".join(f"{n} {tr or '-'} {pa}\n" for n, tr, pa in urimaps(case, sc)),
                                           encoding="ascii")  # fmt: skip
        if http_peers(case, sc) is not None:  # #4767 zECS (X35): the HTTP servers the task can reach
            (d / "http.cfg").write_text(http_peers_cfg(http_peers(case, sc), enc), encoding="ascii")
        if http_request(case, sc) is not None:  # #4767 zECS (X37): the request the task serves
            (d / "webreq.cfg").write_text(http_request_cfg(http_request(case, sc), enc), encoding="ascii")
        if tcpip(case, sc) is not None:  # #4972 (X38): the connection the task was started on
            (d / "tcpip.cfg").write_text(tcpip_cfg(tcpip(case, sc), enc), encoding="ascii")
        if doctemplates(case, sc) is not None:  # #4769 zECS (X33): DOCUMENT CREATE TEMPLATE's installed definitions
            (d / "doctemplates.cfg").write_text("".join(f"{n} {t.encode(enc).hex().upper() or '-'}\n"
                                                        for n, t in doctemplates(case, sc).items()), encoding="ascii")  # fmt: skip
        for i, data in enumerate(equivalence_mq.start_data(case, sc, enc), 1):  # #4892: the data it was started with
            (d / f"retrieve_{i:03d}.bin").write_bytes(data)
        if DLI_CALL.search(source):  # #5278: the databases (the stub's $GGCICS_DIR)
            dli_stage(case, corpus, d, sc)
        if equivalence_mq.state(case, sc) is not None:  # #4892 (W): the queue manager its MQI calls reach
            (d / "mq.cfg").write_text(equivalence_mq.cfg(equivalence_mq.state(case, sc), enc), encoding="ascii")
        if task_facts(case, sc)[1] is not None:  # #4270: what the operator typed (an unformatted RECEIVE)
            (d / "terminal.in").write_bytes(task_facts(case, sc)[1].encode(enc))
        for q, items in cics_tempstorage.ts_seed(case, sc).items():  # #4270: the TS queues the task starts with
            qdir = d / "ts" / q.encode("ascii").hex().upper()
            qdir.mkdir(parents=True, exist_ok=True)
            for i, item in enumerate(items, 1):
                (qdir / f"{i:06d}.bin").write_bytes(item.encode(enc))
        for m, typed in (sc.get("receive") or {}).items():
            (d / f"receive_{m}.bin").write_bytes(
                map_input(screen_fields(corpus, case, m, "input"), typed, enc, bms_justify(corpus, m))
            )
        if programs is not None:  # the CSD's programs; absent, every program is defined
            (d / "programs.cfg").write_text("".join(f"{p}\n" for p in programs), encoding="ascii")
        if tdqueues is not None:  # the CSD's transient-data queues; absent, every queue is defined
            # (#5079, X57: `NAME TYPE`; the stub reads INTRA, EXTRA, and any other TYPE as a queue it does not model)
            tdattrs = csd_tdqueue_attrs(
                corpus, case
            )  # #5168 (X61): and its other attributes, KEY=VALUE words after the TYPE
            (d / "tdqueues.cfg").write_text(
                "".join(f"{q} {tdqueues[q] or '-'}" + "".join(f" {k}={v}" for k, v in tdattrs.get(q, {}).items()) + "\n"
                        for q in sorted(tdqueues)), encoding="ascii")  # fmt: skip
        for q, recs in td_seed(case, sc).items():  # #5168 (X61): the TD queues the task starts with
            qdir = d / "ts" / ("td-" + q.encode("ascii").hex().upper())
            qdir.mkdir(parents=True, exist_ok=True)
            for i, rec in enumerate(recs, 1):
                (qdir / f"{i:06d}.bin").write_bytes(rec.encode(enc))
        if _counters(
            case, sc
        ):  # named counters the region has (POOL/NAME: value); absent ones are INVREQ RESP2 201 (X30)
            (d / "counters.cfg").write_text("".join(f"{k.split('/')[0] or '-'} {k.split('/')[1]} {v}\n"
                                                    for k, v in _counters(case, sc).items()), encoding="ascii")  # fmt: skip
        if case.get("region"):  # ASSIGN APPLID / SYSID: the region's identity, a deployment fact the case states
            (d / "region.cfg").write_text(f"APPLID {case['region']['applid']}\nSYSID {case['region']['sysid']}\n",
                                          encoding="ascii")  # fmt: skip
        if sc.get("faults") or sc.get("sql_abend_plan"):  # #4023 follow-up: the stub's injected conditions
            check_child_faults(case, sc)  # #6967
            (d / "faults.cfg").write_text(
                "".join(x + "\n" for x in fault_lines(sc)), encoding="latin-1"
            )  # #5859 userid_hex
        if sc.get("dli_faults"):  # #5233: the DL/I stub's planned statuses
            (d / "dlifaults.cfg").write_text("".join(x + "\n" for x in dli_fault_lines(case, sc)), encoding="ascii")
        if sc.get("sql_plan"):  # #4173: the SQL stub's planned faults (resolved by sql_fault_plan)
            (d / "sqlfaults.cfg").write_text("".join(x + "\n" for x in sc["sql_plan"]), encoding="ascii")
        date, _, time = scenario_clock(case, sc).partition(" ")  # #4622: the scenario's clock, else the case's
        y, mo, dd = date.split("/")
        eib_date = f"{int(y) - 1900:03d}{_day_of_year(int(y), int(mo), int(dd)):03d}"[-7:].rjust(7, "0")
        eib_time = "0" + time.replace(":", "")[:6]
        term = terminal_facts(case, sc)  # #4270: the task's terminal, when the case states one
        (d / "eib.in").write_text(f"{case['transid']:<4} {sc.get('aid', 'DFHENTER'):<8} {eib_date} {eib_time} "
                                  f"{term['termid'] or '':<4}\n", encoding="ascii")  # fmt: skip
        if term["termid"]:  # the region's terminals: the task's own (START / INQUIRE / SET TERMINAL's TERMIDERR)
            (d / "terminals.cfg").write_text(f"{term['termid']}\n", encoding="ascii")
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
        dlienv = (
            f"GGDLI_FAULTS={rel}/dlifaults.cfg GGDLI_FAULTS_LOG={rel}/out/faults.txt " if sc.get("dli_faults") else ""
        )
        script.append(f"set +e; {cov.trace_env(f'{rel}/{cov.TRACE_NAME}')}{dlienv}GGCICS_DIR={rel} GGCICS_OUT={rel}/out EIBIN={rel}/eib.in "
                      f"GGCICS_TASKN={task_number(case, sc)} LD_PRELOAD=/work/ggdisplay.so "
                      + (f"GGCICS_STARTCODE={task_facts(case, sc)[0]} " if task_facts(case, sc)[0] else "")
                      + (f"GGCICS_FACILITY={term['termid']} " if term["termid"] else "")
                      + (f"GGCICS_UCTRANST={term['uctranst']} " if term["uctranst"] else "")
                      + (f"GGCICS_USERID={term['userid']} " if term.get("userid") else "")  # #5126
                      + (f"GGCICS_SCREEN='{term['screen'][0]} {term['screen'][1]}' " if term.get("screen") else "")
                      + (f"GGCICS_ORIGIN={','.join(term['origin'][k] for k in ORIGIN_KEYS)} " if term["origin"] else "")
                      + (f"GGCICS_URIMAPS={rel}/urimaps.cfg " if urimaps(case, sc) is not None else "")
                      + (f"GGCICS_MAPSETS='{mapsets_env(case)}' " if case.get("maps") else "")
                      + (f"GGCICS_DOCTEMPLATES={rel}/doctemplates.cfg " if doctemplates(case, sc) is not None else "")
                      + (f"GGCICS_HTTP={rel}/http.cfg " if http_peers(case, sc) is not None else "")
                      + (f"GGCICS_WEBREQ={rel}/webreq.cfg " if http_request(case, sc) is not None else "")
                      + (f"GGCICS_TCPIP={rel}/tcpip.cfg " if tcpip(case, sc) is not None else "")
                      + (f"GGC_ZUIDSTCK_TOD={scenario_tod(case, sc)} " if scenario_tod(case, sc) else "")
                      + f"{sqlenv}COB_CURRENT_DATE='{scenario_clock(case, sc)}' GGCICS_NOW={clock_iso(case, sc)} ./task > {rel}/stdout.txt 2>&1; "
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
    overruns: list[str] = []  # #4449 (X8)
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
        if said.is_file() and (overrun := common.bound_violation(said.read_bytes())):  # #4449 (X8)
            why = f"drives an item past its bounds ({overrun}); register X8"
            if sc.get("derived") or sc["name"] in case.get("bounds_refused", {}):
                # a case names each scenario it knowingly leaves unjudged here, with the reason (X8): refused by
                # name, reported as refused, never proven
                refused[sc["name"]] = why
                continue
            overruns.append(f"scenario {sc['name']}: {why}")
            continue
        if (
            rc.is_file()
            and rc.read_text().strip() == "1"
            and said.is_file()
            and PERFORM_DEPTH in said.read_text(encoding="latin-1")
        ):
            sc["prefix_x6"] = PERFORM_DEPTH  # C20: the recursive PERFORM's stack check: judged up to it, as X6
            continue
        if rc.is_file() and rc.read_text().strip() == "98" and said.is_file():
            x6 = judged_refusal(said.read_text(encoding="latin-1"))
            if x6:  # owner decision on #4607 (X6): judged up to the refused WRITEQ (LENGTH > 32767 only since #6573), derived or not -- what ran before
                sc["prefix_x6"] = x6  # it counts (its coverage too); its end state is not compared
                continue
            why = next((ln for ln in said.read_text(encoding="latin-1").splitlines() if "not modelled" in ln), None)
            if why and sc.get("derived"):
                refused[sc["name"]] = why.strip()
                continue
            if why:
                raise Unsupported(f"scenario {sc['name']}: {why.strip()}", ["MODEL"])
    if overruns:  # every one at once, so a case is fixed in one pass
        raise Unsupported("; ".join(overruns) + '; if the program does it on purpose, name each scenario in the '
                          'case\'s "bounds_refused" with the reason', ["BOUNDS"])  # fmt: skip
    (work / "refused.json").write_text(json.dumps(refused, indent=1) + "\n", encoding="utf-8")
    kept = [sc for sc in case["scenarios"] if sc["name"] not in refused]

    # #4023: how much of the program the scenarios execute, together (work/coverage.json)
    def coverage(names: list[str]) -> None:  # (again after the Java side, without tasks it could not judge: #4173)
        cov.write_run_coverage(work / "coverage.json", extras=linked_programs_cov, source=corpus / case["program_source"],
                               original=program, compiled=text, copybooks=corpus, encoding=staged,
                               traces=[work / "scenarios" / n / cov.TRACE_NAME for n in names],
                               compiled_name="PROGRAM.cbl")  # fmt: skip

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
    """A scenario's `sql_faults` as both sides read them: `PROGRAM LINE NTH SQLCODE SQLSTATE [TOKEN [SQLERRD3]]`
    (ggsql.c's $GGSQL_FAULTS, DetSql.withFaults). A fault names its statement by `line` (and `program`, the case's own by
    default), or by `table` and `verb` (every statement of that kind on that table). A fault may declare `sqlerrmc`
    (one token, no blanks, up to 70 characters) and `sqlerrd3` (#5561): what the SQLCA carries for a program that
    reads them (BANKDATA's `SQLERRMC(1:SQLERRML)`, its SQLERRD(3) reason-code arms); undeclared, both are empty."""
    stmts = sql_statements(table)
    out = []
    abends: list[str] = []
    for f in sc.get("sql_faults") or []:
        code = int(f["sqlcode"])
        if f.get("abend") is not None:
            abends.append(_sql_abend_line(case, sc, f, code, table))
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
        extra = ""
        if f.get("sqlerrmc") or f.get("sqlerrd3"):
            token = str(f.get("sqlerrmc") or "-")
            if not re.fullmatch(r"\S{1,70}", token):
                raise Unsupported(f"scenario {sc['name']}: SQL fault {f}: sqlerrmc is one token of 1-70 characters")
            extra = f" {token} {int(f.get('sqlerrd3', 0))}"
        out += [f"{x['program']} {x['line']} {nth} {code} {state}{extra}" for x in hits]
    sc["sql_abend_plan"] = abends
    return out


# #6271 (register X73): IBM's AD2Z -- a Db2 deadlock or timeout the CICS-Db2 attach answers with a failed syncpoint rollback
# (DFHDB2070), then the task abends AD2Z. A scenario's sql_fault may add `"abend": "AD2Z"` to a -911 fault on a statement it
# names by `line`; the statement fails as planned and a `SQL PROGRAM:LINE NTH -1 0 AD2Z` line (faults.cfg) abends the task.
# AD2R (the attached TCB that processes the Db2 request abended) and AD2X (the task and thread TCB in an invalid state) are
# the attach's other task abends, outside AD2Z's rollback arm: the statement fails as planned (any SQLCODE, ASSUMED).
SQL_ABEND_CODES = ("AD2Z", "AD2R", "AD2X")


def _sql_abend_line(case: dict[str, Any], sc: dict[str, Any], f: dict[str, Any], code: int, table: str) -> str:
    where = f"scenario {sc['name']}: SQL fault {f}"
    if (
        f["abend"] not in SQL_ABEND_CODES
        or (f["abend"] == "AD2Z" and code != -911)
        or "line" not in f
        or f.get("table")
        or f.get("verb")
    ):
        raise Unsupported(
            f"{where}: an abend is planned as {'/'.join(SQL_ABEND_CODES)} on a fault naming its statement by line, AD2Z "
            "on a -911 one (register X73: no other SQLCODE, code or table/verb selection is sourced)"
        )
    program = str(f.get("program") or case["program"]).upper()
    if not any(x["program"] == program and x["line"] == int(f["line"]) for x in sql_statements(table)):
        raise Unsupported(f"{where} names no statement of {program}")
    nth = "*" if f.get("nth", 1) == "*" else int(f.get("nth", 1))
    return f"SQL {program}:{int(f['line'])} {nth} -1 0 {f['abend']}"


def mark_sql_abends(case: dict[str, Any], source: str, table: str, program: str) -> str:
    """#6271 (X73): `EXEC CICS GGSQLAB NAME('PROGRAM:LINE') END-EXEC` after the precompiled call of each statement a scenario
    plans an AD2Z abend for, before the RETURN-CODE restore and the WHENEVER tests (the order det/sql.py checks in)."""
    sites = {
        (str(f.get("program") or case["program"]).upper(), int(f["line"]))
        for sc in case["scenarios"]
        for f in sc.get("sql_faults") or []
        if f.get("abend") is not None and "line" in f
    }
    sids = {
        x["sid"]: x["line"]
        for x in sql_statements(table)
        if x["program"] == program.upper() and (x["program"], x["line"]) in sites
    }
    if not sids:
        return source
    if not re.search(r"\bHANDLE\s+ABEND\b", source, re.I):
        raise Unsupported(
            f"{program}: an AD2Z abend is planned but the program has no HANDLE ABEND (register X73, refused)"
        )
    out, sid = [], None
    for ln in source.split("\n"):
        m = re.match(r"\s+MOVE (\d{4}) TO GG-SQL-ID\s*$", ln)
        if m:
            sid = sids.get(int(m.group(1)))
        elif sid is not None and re.match(r"\s+MOVE GG-SQL-RC TO RETURN-CODE", ln):
            out.append(f"           EXEC CICS GGSQLAB NAME('{program.upper()}:{sid}') END-EXEC")
            sid = None
        out.append(ln)
    return "\n".join(out)


# The fault each executed statement is given when the harness enumerates them: the failure the statement's own
# kind meets in practice -- a duplicate key for an INSERT, no row for a SELECT INTO, a timeout (the statement rolled
# back, the unit of work kept: -913, not -911's rollback) for the rest. COMMIT, CLOSE and SET :H = VALUES have none.
def default_fault(stmt: dict[str, Any]) -> int | None:
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
        for prog, line in zip(lines[::2], lines[1::2], strict=False):  # reason: length may differ
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


RESP_NAMES = {n: name for name, n in DFHRESP.items()}  # #4607: the stub logs a RESP by number, CicsTask by name


X6_WRITEQ = re.compile(r"WRITEQ T[SD] LENGTH > FROM: not modelled")
# #4270 (X23): the stub's guard page after a COMMAREA of a stated length (GGCAREA): a reference past EIBCALEN
X23_PAST = re.compile(r"COMMAREA past EIBCALEN: not modelled")


def x6_writeq_refusal(said: str) -> str | None:
    """Owner decision on #4607 (X6): the stub's stop at a WRITEQ TS / TD whose LENGTH is over the pad record's 32767
    bytes (`_write_from`; a LENGTH past FROM alone is padded), the one "not modelled" stop a task is judged up to -- its line, or None for any other (START / PUT CONTAINER past
    FROM, an LE model: those still refuse the task)."""
    m = X6_WRITEQ.search(said)
    return m.group(0) if m else None


def judged_refusal(said: str) -> str | None:
    """The stub's stops a task is judged up to: a WRITEQ past FROM (X6) or, in a scenario with a stated COMMAREA
    length, a reference past EIBCALEN (#4270, X23) -- its line, or None for any other "not modelled" stop."""
    m = X23_PAST.search(said)
    return x6_writeq_refusal(said) or (m.group(0) if m else None)


def _cobol_read(verb: str, kv: dict[str, str], data: bytes, enc: str) -> dict[str, Any]:
    """#4270 (GenApp LGICVS01): a READQ TS / terminal RECEIVE the stub logged (`queue` the name's bytes in hex, `item`
    a number or NEXT, `resp` by number; the bytes read in the event's blob) as CicsTask records it: {queue, item,
    resp, data} / {resp, data}, the data as text in the data's page (none when nothing was read)."""
    resp = RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))
    text = common._decode_text(data, enc) if resp in ("NORMAL", "LENGERR") else None
    if resp in ("NORMAL", "LENGERR") and text is None:
        text = f"<undecodable {data!r} in {enc}>"
    if verb == "RECEIVE":
        return {"event": verb, "resp": resp, "data": text}
    name = bytes.fromhex(kv.get("queue", ""))
    if (
        verb == "READQ-TD"
    ):  # #5079 (X57): CicsTask.readqTd records {queue, resp, data}: a transient-data queue has no items
        return {"event": verb, "queue": (common._decode_text(name, enc) or name.hex()).rstrip(" \x00"),
                "resp": resp, "data": text}  # fmt: skip
    item = kv.get("item", "")
    return {"event": verb, "queue": (common._decode_text(name, enc) or name.hex()).rstrip(" \x00"),
            "item": int(item) if item.isdigit() else item, "resp": resp, "data": text}  # fmt: skip


def java_read_as_compared(e: dict[str, Any]) -> dict[str, Any]:
    """#4270: CicsTask's READQ-TS event as the comparison reads it: the item's bytes (base64 in the JSON) are in the
    region's page (#4528: DetCics.region, CCSID 037 by default), compared as text; none when nothing was read."""
    import base64

    from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

    data = e.get("data")
    if not isinstance(data, str):
        return e
    raw = base64.b64decode(data)
    try:
        return {**e, "data": raw.decode(REGION_PAGE)}
    except UnicodeDecodeError:
        return {**e, "data": f"<undecodable {raw!r} in {REGION_PAGE}>"}


def channel_copy(path: Path) -> dict[str, Any]:
    """#4950: a channel the stub saved in channel.cfg's format (save_channel) as CicsTask records a copy: {name,
    containers: {NAME: HEX}}."""
    lines = path.read_text(encoding="ascii").splitlines()
    return {"name": lines[0].strip(),
            "containers": {w[0]: "" if w[2] == "-" else w[2].upper() for w in (ln.split() for ln in lines[1:])}}  # fmt: skip


# the SEND TEXT options the COBOL translation passes to the stub (GG-FLAGS holds 40 characters); the Java side records
# every TEXT_OPTIONS flag, so it is compared on these only (PRINT, INVITE, DEFRESP, STRFIELD are not forwarded)
TEXT_OPTIONS_FORWARDED = ("ERASE", "FREEKB", "ALARM", "WAIT", "LAST")


def _text_options(args: str) -> list[str]:
    """#5401: a SEND-TEXT line's options, sorted, without the stub's TEXT / DATA kind marker."""
    return sorted(o for o in args.partition("opts=")[2].split() if o not in ("TEXT", "DATA"))


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
    said = out.parent / "stdout.txt"  # #4635: what the task DISPLAYed (the job log), as IBM writes it
    res["sysout"] = said.read_bytes() if said.is_file() else b""
    padded = [ln for ln in res["sysout"].split(b"\n") if ln.startswith(X6_PADDED_SAID.encode("ascii"))]
    if padded:  # X6: a WRITEQ past FROM written padded -- the stub's line, not the task's own DISPLAY
        res["x6_padded"] = [ln.decode("ascii").removeprefix(X6_PADDED_SAID).strip() for ln in padded]
        res["sysout"] = b"\n".join(ln for ln in res["sysout"].split(b"\n") if ln not in padded)
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
            keys = {f["name"]: screen_key(f) for f in fields}  # #5076: an OCCURS field's every occurrence, ACCOUNT.3
            res["screens"].append({"map": kv["map"], **({"mapset": kv["mapset"]} if "mapset" in kv else {}),
                                   "fields": {keys[k][0]: v for k, v in vals.items() if keys[k][1] == "O"},
                                   "subfields": map_subfields(corpus, case, kv["map"], data, enc),
                                   "options": sorted(args.partition("opts=")[2].split()),
                                   "cursor": None if kv.get("cursor", "-1") == "-1" else int(kv["cursor"])})  # fmt: skip
        elif verb == "SEND-TEXT":
            text = common._decode_text(data, enc)  # #3815: not text in the page -> the bytes shown, never dropped
            res["text"].append(f"<undecodable {data!r} in {enc}>" if text is None else text.rstrip(" \x00"))
            res.setdefault("text_options", []).append(_text_options(args))
        # the task's own (a LINK level's: no); a RETURN IMMEDIATE that failed (it has a resp, #4270) went on in the program
        elif verb in ("RETURN", "XCTL") and int(kv.get("level", "1")) <= 1 and not (verb == "RETURN" and "resp" in kv):
            key = "transid" if verb == "RETURN" else "program"
            if data and not ca_fields:  # #4270: nothing to read it by -- refused, never compared as empty
                raise Unsupported(f"{verb} with a COMMAREA, in a case that describes none (\"commarea\": null)",
                                  ["COMMAREA"])  # fmt: skip
            ca = decode_record(data, ca_fields, enc, exact=True, unnamed=True) if data else None
            res[verb.lower()] = {key: kv.get(key, ""), "commarea": ca}
        elif verb == "ABEND":
            res["abend"] = args
        elif verb == "WRITEQ-TD":  # a record as text in the data page
            if kv.get("resp", "0") == "0":
                text = common._decode_text(data, enc)
                res.setdefault("td", []).append(f"<undecodable {data!r} in {enc}>" if text is None else text)
        elif verb == "WRITE-OPERATOR":  # #4270 zECS (X32): the console message, as text in the data's page
            text = common._decode_text(data, enc)
            res.setdefault("operator", []).append(f"<undecodable {data!r} in {enc}>" if text is None else text)
        elif verb == "WEB-CONVERSE":  # #4767 (X35): the request the program sent, as CicsTask records it
            res.setdefault("web", []).append(cics_web._cobol_web(kv, data, enc))
        elif verb == "WEB-OPEN":  # #4767 (X35): the connection opened, as CicsTask records it
            res.setdefault("webopen", []).append(cics_web._cobol_web_open(kv, enc))
        elif verb == "WEB-CLOSE":  # #4767 (X35): the session closed, as CicsTask.webClose records it
            res.setdefault("webclose", []).append({"resp": int(kv["resp"]), "resp2": int(kv["resp2"])})
        elif verb == "WEB-SEND":  # #4767 (X37): the response the program sent, as CicsTask records it
            res.setdefault("websend", []).append(cics_web._cobol_web_send(kv, data, enc))
        elif verb == "WEB-HEADER":  # #4767 (X38): a response header the program wrote
            res.setdefault("webheader", []).append(_cobol_web_header(kv, enc))
        elif verb == "WEB-RECEIVE":  # #4767 (X38): the request body the program read, as CicsTask records it
            res.setdefault("webreceive", []).append(cics_web._cobol_web_receive(kv, data, enc))
        elif verb == "WRITEQ-TS":  # #4607: as CicsTask records it (queue, data, resp, item)
            res.setdefault("ts", []).append(cics_tempstorage.cobol_ts(kv, data, enc))
        elif verb in ("READQ-TS", "READQ-TD", "RECEIVE"):  # #4270 (GenApp LGICVS01): as CicsTask records them
            res.setdefault("reads", []).append(_cobol_read(verb, kv, data, enc))
        elif verb == "START":  # #4270 (GenApp LGWEBST5): as CicsTask records it
            res.setdefault("starts", []).append(cics_taskcontrol._cobol_start(kv, data, enc))
            if "channel" in kv:  # #4950: START CHANNEL -- the copy the started task gets (NNN.channel)
                res["starts"][-1]["channel"] = channel_copy(out / f"{seq}.channel")
        elif verb == "RETRIEVE":  # #5089: as CicsTask.retrieve records it
            res.setdefault("retrieves", []).append(cics_taskcontrol._cobol_retrieve(kv, data, enc))
        elif verb in equivalence_mq.EVENTS:  # #4892: an MQI call, as QueueManager records it
            res.setdefault("mq", []).append(equivalence_mq.cobol_event(verb, kv, data))
        elif verb == "CHILD":  # #4950: a RUN TRANSID child the task's wait dispatched -- what it did, in its directory
            res.setdefault("children", []).append(outputs(out / kv["dir"] / "out", case, corpus, []))
    res["containers"] = task_containers(out / "containers.out")  # #4270 (X24): the current channel's, at task end
    res["mq_queues"] = equivalence_mq.queues_left(out / "mq.out")  # #4892: the queues the task left
    dli = {p.stem: p.read_bytes() for p in sorted(out.glob("*.out")) if (out.parent / f"seed.{p.stem}").is_file()}
    if dli or any(out.parent.glob("seed.*")):  # #5278: the databases the task left (the stub's exit dump), by DBD;
        res["dli"] = dli  # none when it never scheduled the PSB: the port's DetDli.leave dumps nothing then either
    left = out / "commarea.out"  # a LINKed program's result: the COMMAREA it left (ggcics GGCAOUT)
    res["linked_commarea"] = (
        decode_record(left.read_bytes(), ca_fields, enc, exact=True, unnamed=True)
        if left.is_file() and left.stat().st_size
        else None
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
    cleared: the mainframe's bytes are not known, so nothing is claimed about them). #5233: X'40' too -- DFHBMUNP, the
    EBCDIC space, which the port's side (java_subfields) cannot tell from a cleared byte, so neither side claims it."""
    out: dict[str, dict[str, int]] = {}
    scr = case["screens"][map_name]
    layouts = [screen_layout(corpus, str(common.case_path(corpus, scr["copybook"])), scr[side])
               for side in ("input", "output")]  # fmt: skip
    data_names = {screen_key(f)[0] for f in layouts[1] if screen_key(f)[1] == "O"}
    space = " ".encode(enc)
    for f in (x for layout in layouts for x in layout):
        name, kind = screen_key(f)  # #5076: ACCOUNT.3 for ACCOUNTA(3)
        if name not in data_names or f["offset"] + f["bytes"] > len(data):
            continue
        raw = data[f["offset"] : f["offset"] + f["bytes"]]
        if kind == "L" and f["bytes"] == 2 and int.from_bytes(raw, "big", signed=True) == -1:
            out.setdefault(name, {})["length"] = -1
        elif kind in _SUBFIELDS and f["bytes"] == 1 and raw not in (b"\x00", space, b"\x40"):
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
# a table field has a second comment line ("// OCCURS 20 TIMES") between its PICTURE comment and the property (#5233)
_DTO_FIELD = re.compile(r"^\s*//\s*(.+?)\n(?:\s*//[^\n]*\n)?\s*private\s+([\w.<>]+)\s+(\w+);", re.M)


def java_class_file(src: Path, name: str, context: Path | None = None) -> Path | None:
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


def dto_shape(src: Path, cls: str, context: Path | None = None) -> dict[str, Any]:
    """A generated DTO's properties: {java name: COBOL field name} for a field, {java name:
    (DTO class, its shape)} for a part (a composite COMMAREA's segments), from the comment each
    property carries (`// CDEMO-FROM-TRANID: PIC X(04), offset 0 ...`). `cls` is a qualified name
    or a simple one resolved from `context` (java_class_file); a part's class is resolved from
    the DTO that declares it."""
    path = java_class_file(src, cls, context)
    if path is None:
        raise LookupError(f"no generated class {cls} under {src}")
    return _dto_file_shape(src, path)


class TableField(str):
    """#5233: the COBOL name of a DTO property that is a List (an OCCURS table of scalars). The port's input carries it
    in the area's bytes (`tabled`), never as JSON: a scalar there is not a list."""


def _dto_file_shape(src: Path, path: Path) -> dict[str, Any]:
    shape: dict[str, Any] = {}
    for comment, jtype, var in _DTO_FIELD.findall(path.read_text(encoding="utf-8")):
        part = java_class_file(src, jtype, path) if " -> " in comment else None
        if part is not None:
            shape[var] = (part.stem, _dto_file_shape(src, part))
        elif ":" in comment:
            name = comment.split(":", 1)[0].strip()
            shape[var] = TableField(name) if jtype.startswith("List<") else name
    return shape


def to_java(values: dict[str, Any], shape: dict[str, Any], text: frozenset[str] = frozenset()) -> dict[str, Any]:
    """{COBOL name: value} -> the DTO's JSON (numbers as numbers, text as the program holds it). A field in `text`
    (an alphanumeric PICTURE) stays text even when it reads as a number: CardDemo's selected transaction id
    '0000000000683580' (PIC X(16)) reached the port as 683580."""
    out: dict[str, Any] = {}
    for var, spec in shape.items():
        if isinstance(spec, tuple):
            out[var] = to_java(values, spec[1], text)
        elif spec in values and not isinstance(spec, TableField):
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


def commarea_class(case: dict[str, Any], src: Path, svc_file: Path) -> str | None:
    """The COMMAREA DTO the task carries: the one the service's handleTransaction takes -- or, for a program that
    receives none and only builds one (CardDemo's sign-on, COSGN00C: it tests EIBCALEN, then XCTLs with
    CARDDEMO-COMMAREA), the generated DTO of the case's first COMMAREA record. None for a case whose program takes no
    COMMAREA at all (`"commarea": null`, #4270: the async credit-card services, whose det service is handleLink())."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

    svc_text = svc_file.read_text(encoding="utf-8")
    m = re.search(r"handleTransaction\(String transid, (\w+) request\)", svc_text) or re.search(
        r"handleLink\((\w+) request\)", svc_text
    )  # a LINKed program (CBSA): its contract COMMAREA DTO
    if m and m.group(1) == "Object":  # #5859: an HLASM program's facade (hlasm.service_stub) types no COMMAREA
        return None
    if m:
        return m.group(1)
    if "commarea" in case and case["commarea"] is None:  # #4270: a program that takes none (handleLink()): no DTO
        return None
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
        Object linkedArea;  // #4803: the LINK's COMMAREA read through the linked program's own DTO, when that is another class
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
            if (t == null || !p.equals(linkedProgram) || (area(t) != ca && linkedArea != ca)) {
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
                if (m == null && commarea == null) {  // #4270: a program that takes no COMMAREA: handleLink()
                    m = method(service, "handleLink", 0);
                }
                if (m == null) {
                    runTask(service);
                    return;
                }
                if (commarea == null && m.getParameterCount() == 1
                        && m.getParameterTypes()[0].getSimpleName().endsWith("ChannelIn")) {
                    // #4270: a channel program's handleLink takes its channel as a DTO, not a task: no task facade
                    // (#4343) can carry the scenario's task, so it runs through runTask, and `entries` says so
                    entry(program, "runTask (a channel program: handleLink(" + m.getParameterTypes()[0].getSimpleName()
                            + ") is no task facade, #4343)");
                    started = true;
                    call(method(service, "runTask", 1), service, scenario);
                    ended = true;
                    return;
                }
                if (commarea != null && !m.getParameterTypes()[0].isInstance(commarea)) {
                    throw new FacadeRefused("handleLink of " + program + " takes a " + m.getParameterTypes()[0].getName()
                            + ", the scenario's COMMAREA is a " + commarea.getClass().getName());
                }
                linked = scenario;
                linkedProgram = program;
                entry(program, "handleLink");
                Object got = m.getParameterCount() == 0 ? call(m, service) : call(m, service, commarea);
                if (linked != null) {
                    throw new FacadeRefused("handleLink of " + program + " did not run its task in the region");
                }
                if (m.getReturnType() != void.class && got != commarea) {
                    throw new FacadeRefused("handleLink of " + program
                            + " answered a COMMAREA other than the one passed to it by reference");
                }
                return;
            }
            Method one = facade(service, "handleTransaction", 1, false);
            Method two = facade(service, "handleTransaction", 2, false);
            Method oneB = facade(service, "handleTransaction", 2, true);
            Method twoB = facade(service, "handleTransaction", 3, true);
            if (one == null && two == null && oneB == null && twoB == null) {
                runTask(service);
                return;
            }
            top = scenario;
            Method used;
            Object got;
            boolean carriesBytes = false;
            // #4965: the byte-carrying overload when the service has one (no bytes of a previous task in: the
            // scenario's COMMAREA is the DTO), else the DTO one
            if (commarea == null && oneB != null) {
                used = oneB;
                carriesBytes = true;
                entry(program, "handleTransaction");
                got = call(oneB, service, scenario.transid(), null);
            } else if (twoB != null && (commarea == null || twoB.getParameterTypes()[1].isInstance(commarea))) {
                used = twoB;
                carriesBytes = true;
                entry(program, "handleTransaction");
                // #5233: the bytes the scenario's task starts with (a table's later occurrences are only there), not none
                got = call(twoB, service, scenario.transid(), commarea, scenario.linkAreaView());
            } else if (commarea == null && one != null) {
                used = one;
                entry(program, "handleTransaction");
                got = call(one, service, scenario.transid());
            } else if (two != null && (commarea == null || two.getParameterTypes()[1].isInstance(commarea))) {
                used = two;
                entry(program, "handleTransaction");
                got = call(two, service, scenario.transid(), commarea);
            } else {
                throw new FacadeRefused("handleTransaction of " + program + " cannot take the COMMAREA ("
                        + commarea.getClass().getName() + ") the task starts with");
            }
            if (top != null) {
                throw new FacadeRefused("handleTransaction of " + program + " did not run its task in the region");
            }
            if (used.getReturnType() != void.class && !answered(got, scenario, used.getReturnType(), service)) {
                throw new FacadeRefused("handleTransaction of " + program
                        + " answered a COMMAREA other than the one its RETURN passes on");
            }
            if (carriesBytes) {
                Method accessor = null;
                for (Method m : service.getClass().getMethods()) {
                    if (m.getName().equals("lastAnswerBytes") && m.getParameterCount() == 0) {
                        accessor = m;
                    }
                }
                if (accessor == null) {
                    throw new FacadeRefused("handleTransaction (bytes) of " + program + " has no lastAnswerBytes()");
                }
                // #4965: the bytes the byte-carrying overload answers are the ones its task's RETURN passed on
                if (!java.util.Arrays.equals((byte[]) call(accessor, service), scenario.returnedBytes())) {
                    throw new FacadeRefused("lastAnswerBytes() of " + program
                            + " is not the bytes its RETURN passes on");
                }
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
            if (ca == null && m.getParameterTypes()[0].getSimpleName().endsWith("ChannelIn")) {
                // #4270 (async SEQPNT): a LINK CHANNEL to a channel program, as start() enters one -- its handleLink
                // takes the channel as a DTO, not a task: no task facade (#4343) can carry the LINK's level, so it
                // runs through runTask, and `entries` says so
                entry(p, "runTask (a channel program: handleLink(" + m.getParameterTypes()[0].getSimpleName()
                        + ") is no task facade, #4343)");
                call(method(service, "runTask", 1), service, task);
                return;
            }
            Object passed = ca;
            if (ca != null && !m.getParameterTypes()[0].isInstance(ca)) {
                // #4803: LINK passes bytes. A caller's COMMAREA of another DTO class (EPSCMORT's EPSMTCOM, EPSCSMRT's own
                // DFHCOMMAREA) is read through the linked program's DTO by layout, as CicsTask.returned does for a RETURN;
                // the program still runs on the task's own area, so what it changes the caller sees. No layout, or fewer
                // bytes than the target's record: refused, never guessed.
                passed = convertLayout(p, ca, m.getParameterTypes()[0]);
            }
            Object outerArea = linkedArea;
            CicsTask outer = linked;
            String outerProgram = linkedProgram;
            linked = task;
            linkedProgram = p;
            linkedArea = passed;
            entry(p, "handleLink");
            try {
                call(m, service, passed);
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
            linkedArea = outerArea;
        }

        /** #4803: `ca` read through `type` by layout (toCommarea -> fromCommarea), or a refusal by name. */
        Object convertLayout(String p, Object ca, Class<?> type) {
            String why = "handleLink of " + p + " takes a " + type.getName() + ", the LINK passed a "
                    + ca.getClass().getName();
            try {
                Method to = ca.getClass().getMethod("toCommarea");
                Method from = type.getMethod("fromCommarea", byte[].class);
                if (to.getReturnType() != byte[].class || !java.lang.reflect.Modifier.isStatic(from.getModifiers())) {
                    throw new FacadeRefused(why + " (no layout converts one into the other)");
                }
                return from.invoke(null, (Object) to.invoke(ca));
            } catch (NoSuchMethodException e) {
                throw new FacadeRefused(why + " (no layout converts one into the other)");
            } catch (java.lang.reflect.InvocationTargetException e) {
                throw new FacadeRefused(why + ": " + e.getCause());
            } catch (IllegalAccessException e) {
                throw new FacadeRefused(why + ": " + e);
            }
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
    static boolean answered(Object got, CicsTask task, Class<?> type, Object service) {
        Object raw = task.returned(Object.class);
        if (got == raw) {
            return true;
        }
        if (raw instanceof byte[] wide && got != null && service != null && !(got instanceof byte[])
                && java.util.Arrays.stream(got.getClass().getMethods()).noneMatch(m -> m.getName().equals("fromCommarea"))) {
            // #5089: a DTO with no layout (a POINTER, a LENGTH that differs from the record) is read through the
            // program's own codec; written back, it must give the bytes the RETURN passed, over the span both define
            try {
                return (Boolean) service.getClass().getMethod("wideSame", byte[].class, Object.class).invoke(service, wide, got);
            } catch (ReflectiveOperationException | RuntimeException e) {
                return false;
            }
        }
        if (raw instanceof byte[] wide && got != null && got.getClass() == type) {
            // #4695: a RETURN with a LENGTH past the DTO passes the COMMAREA as bytes (the region's EBCDIC); the facade
            // answers its own DTO, those bytes read through its layout in the port's page -- never a different record
            try {
                java.nio.charset.Charset page = (java.nio.charset.Charset) Class.forName("__PKG__.entity.vsam.CobolRecords")
                        .getMethod("charset").invoke(null);
                byte[] text = new String(wide, java.nio.charset.Charset.forName("IBM037")).getBytes(page);
                Method bytes = type.getMethod("toCommarea");
                Object expected = type.getMethod("fromCommarea", byte[].class).invoke(null, (Object) text);
                return java.util.Arrays.equals((byte[]) bytes.invoke(got), (byte[]) bytes.invoke(expected));
            } catch (ReflectiveOperationException | RuntimeException e) {
                return false;
            }
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

    /** #4965: the overload of `name` with `params` parameters that does (bytes) or does not end in the raw
     *  COMMAREA bytes (byte[]): `handleTransaction(String, byte[])` is not the DTO-less `(String, T)`. */
    static Method facade(Object service, String name, int params, boolean bytes) {
        for (Method m : service.getClass().getMethods()) {
            if (m.getName().equals(name) && m.getParameterCount() == params
                    && (m.getParameterTypes()[params - 1] == byte[].class) == bytes) {
                return m;
            }
        }
        return null;
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
                          programs: list[str] | None = None, tdqueues: dict[str, str] | None = None,
                          tdattrs: dict[str, dict[str, str]] | None = None) -> str:  # fmt: skip
    """EquivalenceRunTest for a CICS case: the files loaded through their entities' codecs, then
    each scenario (in/scenarios.json) run as a CicsTask through the service's runTask, its events
    written to out/<scenario>.json -- a screen as its screenValues(), a COMMAREA as its DTO."""
    import equivalence_java as ej

    pkg = ej.PKG
    # #5945: the scenario's stated TOD for CALL ZUIDSTCK (only a case that states one carries the driver lines)
    tod_stmt = '            stateTod(sc.has("tod") ? sc.get("tod").asText() : null);\n' if case_states_tod(case) else ""
    tod_helper = (
        f"""    /** #5945 (X47): the scenario's TOD, or none, for the port's ZUIDSTCK stand-in (the stub's $GGC_ZUIDSTCK_TOD). */
    static void stateTod(String hex) {{
        try {{
            Class.forName("{pkg}.cobolrt.le.Zuidstck").getMethod("state", String.class).invoke(null, hex);
        }} catch (ReflectiveOperationException e) {{
            throw new IllegalStateException("a stated TOD for a port with no cobolrt.le.Zuidstck", e);
        }}
    }}

"""
        if case_states_tod(case)
        else ""
    )
    svc = ej._service_class(case["program"])
    var = svc[0].lower() + svc[1:]
    ca = commarea_class(case, src, next(src.rglob(f"{svc}.java")))
    commarea_java = ("null" if ca is None else 'sc.get("commarea").isNull() ? null\n                    : '
                     f'json.treeToValue(sc.get("commarea"), {pkg}.dto.contract.{ca}.class)')  # fmt: skip
    screens = {m: _generated_class(src, rf'String MAP = "{m}";') for m in case["screens"]}
    # The estate has the CICS exception package only when some program throws or handles one (UowForge): IBM DBB
    # MortgageApplication's do not, so nothing there can throw CicsAbendException and the test catches none.
    has_abend = any(src.rglob("exception/CicsAbendException.java"))
    abend_import = f"import {pkg}.exception.CicsAbendException;\n" if has_abend else ""
    # #4270: an estate with no BMS map (the async credit-card example) has no screen view models to convert
    has_screens = any(src.rglob("dto/screen/ScreenModel.java"))
    screen_import = f"import {pkg}.dto.screen.ScreenModel;\n" if has_screens else ""
    screen_copy = ("                if (copy.get(\"screen\") instanceof ScreenModel s) {\n"
                   "                    copy.put(\"screen\", s.screenValues());\n"
                   "                }\n") if has_screens else ""  # fmt: skip
    by_base = {f["base"]: f for f in files}
    region = case.get("region") or {}
    region_java = f'"{region["applid"]}", "{region["sysid"]}"' if region.get("applid") else "null, null"
    csd_java = ""
    if tdqueues is not None:  # the CSD's transient-data queues: a WRITEQ TD to any other is QIDERR
        names = ", ".join(f'"{q}"' for q in sorted(tdqueues))
        csd_java += f"            task.withTdQueues(java.util.Set.of({names}));\n"
        kinds = ", ".join(f'"{q}", "{tdqueues[q]}"' for q in sorted(tdqueues) if tdqueues[q])
        # #5079 (X57): each queue's TYPE (none stated: ""), which decides what READQ TD / DELETEQ TD do
        csd_java += f"            task.withTdQueueTypes(java.util.Map.of({kinds}));\n"
        if tdattrs:  # #5168 (X61): the other attributes that decide what READQ / WRITEQ / DELETEQ TD do
            flat = ", ".join(f'"{q}", "{k}", "{v}"' for q in sorted(tdattrs) for k, v in tdattrs[q].items())
            csd_java += f"            task.withTdQueueAttributes({flat});\n"
    extras = [x["program"].upper() for x in case.get("programs", [])]
    runs = "".join(
        f'                    if ("{p}".equals(program)) {{ if (facades) {{ region.enter("{p}", t, {_svc_var(p)}); }} '
        f"else {{ {_svc_var(p)}.runTask(t); }} return; }}\n"
        for p in extras
    )  # the case's other programs (a LINK's target), each through its service (#4449: java-facade: its handleLink)
    transactions = case_transactions(case) if case.get("transactions") is not None else None
    if programs is not None or extras or transactions is not None:  # the CSD's programs: an XCTL / LINK / INQUIRE
        # of any other is PGMIDERR; #4270: its transactions (a RUN TRANSID / START of any other is TRANSIDERR)
        defined = (f"java.util.Set.of({', '.join(f'{chr(34)}{p}{chr(34)}' for p in programs)}).contains(program)"
                   if programs is not None else "true")  # fmt: skip
        tx_java = ("" if transactions is None else "                public boolean transaction(String transid) { "
                   f"return java.util.Set.of({', '.join(f'{chr(34)}{t}{chr(34)}' for t in transactions)})"
                   ".contains(transid); }\n")  # fmt: skip
        kids = case_child_programs(case)  # #4950: the program a RUN TRANSID child runs
        tx_java += ("" if not kids else "                public String program(String transid) { return "
                    f"java.util.Map.ofEntries({', '.join(f'java.util.Map.entry({chr(34)}{t}{chr(34)}, {chr(34)}{p}{chr(34)})' for t, p in kids.items())})"
                    ".get(transid); }\n")  # fmt: skip
        csd_java += (f"            task.withPrograms(new CicsTask.Programs() {{\n"
                     f"                public boolean defined(String program) {{ return {defined}; }}\n"
                     f"{tx_java}"
                     f"                public void run(String program, CicsTask t) {{\n"
                     f"{runs}"
                     f'                    throw new NotRun(program);  // #4173: the task ends here (NOPROGRAM)\n'
                     f"                }}\n"
                     f"            }});")  # fmt: skip
    fields, loads, dumps = [], [], []
    for dsn, spec in case.get("datasets", {}).items():
        if by_base[dsn].get("runtime"):  # #4771: stated for the COBOL leg; the project stores no file named at run time
            continue
        if by_base[dsn].get("organization") == "ESDS":  # #4213: the region's ESDS, on the task (CicsTask.withEsds)
            f = by_base[dsn]
            csd_java += (
                f'            task.withEsds("{f["file"]}", {f["reclen"]}, records(sc, "{dsn}", {f["reclen"]}));\n'
            )
            dumps.append(f'            dump(sc.get("name").asText() + ".{dsn}.out", task.esdsRecords("{f["file"]}"));')
            continue
        ent = spec["entity"]
        repo = f"{ent[0].lower()}{ent[1:]}Repository"
        fields.append(f"    @Autowired {pkg}.repository.vsam.{ent}Repository {repo};")
        loads.append(
            f"            {repo}.deleteAll();\n"
            f'            load(sc, "{dsn}", {by_base[dsn]["reclen"]}, {pkg}.entity.vsam.{ent}::fromRecord, {repo});'
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
    # #4270 (CBSA CREACC): SYNCPOINT ROLLBACK ends the task's Db2 unit of work there and then -- its changes undone on
    # the task's connection -- and the task's later SQL is a new unit of work, committed when the task ends, as the
    # COBOL side's Db2 does it (an abend still backs out only what came after). Marking the whole transaction
    # rollback-only lost the SQL a caller ran after a LINKed program's rollback (INQACCCU -> CREACC's INSERTs).
    db2_rollback_now = ("try { org.springframework.jdbc.datasource.DataSourceUtils.getConnection(db2Jdbc.getJdbcTemplate()"
                        ".getDataSource()).rollback(); } catch (java.sql.SQLException e) { throw new "
                        "IllegalStateException(e); } ") if db2 else ""  # fmt: skip
    abend_catch = (" catch (CicsAbendException e) {\n                    status.setRollbackOnly();\n"
                   f"                    {db2_rollback}task.abend(e.getAbcode());\n                }}")  # fmt: skip
    abend_catch = abend_catch if has_abend else ""
    db2_end = "\n            });" if db2 else ""
    recv = [f'            if (r.has("{m}")) received.put("{m}", {pkg}.dto.screen.{cls}.fromValues('
            f'json.convertValue(r.get("{m}"), new TypeReference<Map<String, String>>() {{ }})));'
            for m, cls in screens.items()]  # fmt: skip
    facade_java = FACADE_JAVA.replace("__PKG__", pkg)  # #4695: the page a facade's bytes answer is read in
    return f"""package {pkg};

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import {pkg}.cics.CicsTask;
{screen_import}{abend_import}import java.io.IOException;
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
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.data.jpa.repository.JpaRepository;

/** #3754: the CICS equivalence run of {case["program"]} ({case["name"]}) -- generated by tests/tools/equivalence_cics.py. */
@SpringBootTest(properties = {{"spring.jpa.show-sql=false", "gitgalaxy.clock={ej._clock(case)}"}})
@DirtiesContext  // --one-jvm: the facade run is this class again in the session JVM, on a context of its own
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

    /** #5089 (register Q3): the task's file unit of work. IBM: SYNCPOINT ROLLBACK ends it and the task's next
     *  recoverable change starts a new one, committed when the task ends -- restart() backs the file changes out
     *  and begins that next one. An abend or a refusal marks the CURRENT one rollback-only. */
    static final class Uow {{
        private final org.springframework.transaction.PlatformTransactionManager tm;
        private org.springframework.transaction.TransactionStatus st;

        Uow(org.springframework.transaction.PlatformTransactionManager tm) {{
            this.tm = tm;
            this.st = tm.getTransaction(new org.springframework.transaction.support.DefaultTransactionDefinition());
        }}

        void setRollbackOnly() {{
            st.setRollbackOnly();
        }}

        void restart() {{
            tm.rollback(st);
            st = tm.getTransaction(new org.springframework.transaction.support.DefaultTransactionDefinition());
        }}

        void end() {{
            if (st.isRollbackOnly()) {{
                tm.rollback(st);
            }} else {{
                tm.commit(st);
            }}
        }}

        void abort() {{
            if (!st.isCompleted()) {{
                tm.rollback(st);
            }}
        }}
    }}

    private void fileUnit(java.util.function.Consumer<Uow> body) {{
        Uow unit = new Uow(transactions);
        try {{
            body.accept(unit);
        }} catch (RuntimeException | Error e) {{
            unit.abort();
            throw e;
        }}
        unit.end();
    }}

    /** #4173: a LINK to a program the case does not run ends the task there, as the COBOL side's stub does
     *  (NOPROGRAM) -- only a derived SQL-fault task reaches one; it is judged up to that LINK. */
    static final class NotRun extends RuntimeException {{
        NotRun(String program) {{
            super("the case does not run " + program);
        }}
    }}

    /** #4173: the task's SQL fault plan, through the det runtime's DetSql (its statements' executions counted
     *  afresh): false when a fault is planned and the port has no DetSql to take it (the task is then not run). */
    /** #4892: the task's queue manager (cobolrt.cics.DetMq, the stub's ggmq.c), from the scenario's mq.cfg. */
    static void mqAttach(CicsTask task, Path cfg) {{
        try {{
            Class.forName("{pkg}.cobolrt.cics.DetMq").getMethod("attach", CicsTask.class, Path.class).invoke(null, task, cfg);
        }} catch (ReflectiveOperationException e) {{
            throw new IllegalStateException("a queue manager for a port with no cobolrt.mq", e);
        }}
    }}

{tod_helper}    /** #5278: a new task on the stated databases (cobolrt.dli.DetDli, the stub's ggdli.c): nothing scheduled, nothing read yet. */
    static void dliReset(Path dir, JsonNode plan, Path log) {{
        System.setProperty("gitgalaxy.dli.dir", dir.toString());
        System.clearProperty("gitgalaxy.faults.plan");  // #5233: this task's planned statuses (DetDli reads `# DLI F NTH ST` lines)
        System.clearProperty("gitgalaxy.faults.log");
        if (plan != null && plan.size() > 0) {{
            try {{
                Path file = log.resolveSibling(log.getFileName() + ".dliplan");
                List<String> lines = new ArrayList<>();
                plan.forEach(x -> lines.add("# DLI " + x.asText()));
                Files.write(file, lines);
                System.setProperty("gitgalaxy.faults.plan", file.toString());
                System.setProperty("gitgalaxy.faults.log", log.toString());
            }} catch (java.io.IOException e) {{
                throw new java.io.UncheckedIOException(e);
            }}
        }}
        try {{
            Class.forName("{pkg}.cobolrt.dli.DetDli").getMethod("reset").invoke(null);
        }} catch (ReflectiveOperationException e) {{
            throw new IllegalStateException("a DL/I runtime for a port with no cobolrt.dli", e);
        }}
    }}

    /** #5278: each database as the port leaves it (DetDli.leave), by DBD name, in hex -- the stub's exit dump. */
    static Map<String, String> dliLeft(Path to, JsonNode dbs) {{
        Map<String, String> left = new LinkedHashMap<>();
        try {{
            Files.createDirectories(to);
            System.setProperty("gitgalaxy.dli.out", to.toString());
            Class.forName("{pkg}.cobolrt.dli.DetDli").getMethod("leave").invoke(null);
            for (JsonNode n : dbs) {{
                Path f = to.resolve(n.asText() + ".out");
                if (Files.exists(f)) {{
                    left.put(n.asText(), java.util.HexFormat.of().withUpperCase().formatHex(Files.readAllBytes(f)));
                }}
            }}
        }} catch (ReflectiveOperationException | java.io.IOException e) {{
            throw new IllegalStateException(e);
        }}
        return left;
    }}

    /** #4892: the queues the task left (null: it had no queue manager), its normal end committing it. */
    static Object mqEnd(CicsTask task) {{
        try {{
            return Class.forName("{pkg}.cobolrt.cics.DetMq").getMethod("end", CicsTask.class).invoke(null, task);
        }} catch (ClassNotFoundException e) {{
            return null;
        }} catch (ReflectiveOperationException e) {{
            throw new IllegalStateException(e);
        }}
    }}

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
            Object commarea = {commarea_java};
            if (sc.hasNonNull("commarea_hex")) {{  // #5859: an untyped COMMAREA (HLASM): the caller's bytes, EIBCALEN their count
                commarea = java.util.HexFormat.of().parseHex(sc.get("commarea_hex").asText());
            }}
            // #4270 (X23): a stated COMMAREA length (EIBCALEN) shorter than the record: the area is that long
            Integer calen = sc.path("commarea_length").isInt() ? Integer.valueOf(sc.get("commarea_length").asInt())
                    : sc.path("untyped_length").isInt() ? Integer.valueOf(sc.get("untyped_length").asInt()) : null;
            Map<String, Object> received = new LinkedHashMap<>();
            JsonNode r = sc.get("receive");
{chr(10).join(recv)}
            // #4635: what the port DISPLAYs (the generated Sysout appends to this task's own file), compared to the stub's
            Path sysout = out.resolve(sc.get("name").asText() + ".sysout");
            Files.deleteIfExists(sysout);
            System.setProperty("gitgalaxy.sysout", sysout.toString());
{tod_stmt}            CicsTask task = new CicsTask("{case["transid"]}", sc.get("aid").asText(), commarea, calen, received)
                    .withClock(java.time.LocalDateTime.parse(sc.path("clock").asText("{ej._clock(case)}")))  // EIBTIME / ASKTIME: the scenario's clock, else the case's
                    .withRegion({region_java})  // ASSIGN APPLID / SYSID
                    .withProgram("{case["program"]}")  // the task's first program (a LINK's INVOKINGPROG)
                    .withCounters(counters(sc))  // GET COUNTER: the region's named counters
                    .withTaskNumber(sc.get("taskn").asLong())  // EIBTASKN: the task's number, as the stub's $GGCICS_TASKN
                    // #4270: ASSIGN STARTCODE and an unformatted RECEIVE's input, as the stub's ($GGCICS_STARTCODE, terminal.in)
                    .withStartcode(sc.get("startcode").isNull() ? null : sc.get("startcode").asText())
                    .withTerminalInput(sc.get("terminal").isNull() ? null : sc.get("terminal").asText())
                    // #4270: the task's terminal and origin data, as the stub's ($GGCICS_FACILITY, _UCTRANST, _ORIGIN)
                    .withTermidIfStated(sc.get("termid").isNull() ? null : sc.get("termid").asText())  // #5126: unstated is refused, as the stub
                    .withUctranst(sc.get("uctranst").isNull() ? null : sc.get("uctranst").asText())
                    .withTempStorage(tempStorage(sc))  // #4270: the TS queues the task starts with, as the stub's
                    // RECOVERY(NONE) files: their changes made outside the unit of work, so they survive a backout
                    .withNonRecoverable(java.util.Set.of({", ".join(f'"{x}"' for x in non_recoverable_files(case, files))}),
                            change -> {{
                                org.springframework.transaction.support.TransactionTemplate t =
                                        new org.springframework.transaction.support.TransactionTemplate(transactions);
                                t.setPropagationBehavior(org.springframework.transaction.TransactionDefinition.PROPAGATION_REQUIRES_NEW);
                                t.executeWithoutResult(s -> change.run());
                            }});
            if (sc.hasNonNull("start_data")) {{  // #4892: the data the task was started with, as the stub's retrieve_NNN.bin
                List<byte[]> started = new ArrayList<>();
                sc.get("start_data").forEach(x -> started.add(java.util.HexFormat.of().parseHex(x.asText())));
                task.withRetrieveData(started);
            }}
            if (sc.hasNonNull("mq")) {{  // #4892 (W): the queue manager its MQI calls reach, as the stub's mq.cfg
                mqAttach(task, in.resolve(sc.get("mq").asText()));
            }}
            if (sc.hasNonNull("dli")) {{  // #5278 (I5): the databases EXEC DLI reaches, afresh for each task
                dliReset(in.resolve(sc.get("dli").get("dir").asText()), sc.path("dli_faults"),
                        out.resolve(sc.get("name").asText() + ".faults"));
            }}
            if (sc.hasNonNull("urimaps")) {{  // #4270 zECS (X32): INQUIRE URIMAP's installed definitions, as the stub's
                java.util.List<String[]> defs = new java.util.ArrayList<>();
                sc.get("urimaps").forEach(u -> defs.add(new String[] {{u.get(0).asText(), u.get(1).asText(),
                        u.get(2).asText()}}));
                task.withUrimaps(defs);
            }}
            if (sc.hasNonNull("doctemplates")) {{  // #4769 zECS (X33): DOCUMENT CREATE TEMPLATE's installed definitions
                java.util.Map<String, String> templates = new java.util.LinkedHashMap<>();
                sc.get("doctemplates").fields().forEachRemaining(e -> templates.put(e.getKey(), e.getValue().asText()));
                task.withDoctemplates(templates);
            }}
            if (sc.hasNonNull("http_request")) {{  // #4767 zECS (X37): the request the task serves
                JsonNode q = sc.get("http_request");
                java.util.List<String[]> headers = new java.util.ArrayList<>();
                for (JsonNode h : q.get("headers")) {{
                    headers.add(new String[] {{h.get(0).asText(), h.get(1).asText()}});
                }}
                task.withHttpRequest(new CicsTask.HttpRequest(q.get("scheme").asText(), q.get("host").asText(),
                        q.get("port").asInt(), q.get("method").asText(), q.get("version").asText(),
                        q.get("path").asText(), q.get("query").asText(), headers,
                        q.hasNonNull("mediatype") ? q.get("mediatype").asText() : null,
                        q.hasNonNull("body") ? q.get("body").asText() : null));
            }}
            if (sc.hasNonNull("tcpip")) {{  // #4972 (X38): the connection the task was started on
                JsonNode q = sc.get("tcpip");
                task.withTcpip(new CicsTask.Tcpip(q.get("client_addr").asText(),
                        q.hasNonNull("client_name") ? q.get("client_name").asText() : null, q.get("server_addr").asText(),
                        q.hasNonNull("server_name") ? q.get("server_name").asText() : null, q.get("port").asInt(),
                        q.get("ssl_type").asText()));
            }}
            if (sc.hasNonNull("http_peers")) {{  // #4767 zECS (X35): the HTTP servers the task can reach
                java.util.List<CicsTask.HttpPeer> peers = new java.util.ArrayList<>();
                for (JsonNode p : sc.get("http_peers")) {{
                    java.util.List<CicsTask.HttpExchange> xs = new java.util.ArrayList<>();
                    for (JsonNode x : p.get("exchanges")) {{
                        xs.add(new CicsTask.HttpExchange(x.get("method").asText(), x.get("path").asText(),
                                x.get("query").asText(), x.get("status").asInt(), x.get("statustext").asText(),
                                x.get("mediatype").asText(), x.get("body").asText()));
                    }}
                    peers.add(new CicsTask.HttpPeer(p.get("scheme").asText(), p.get("host").asText(), p.get("port").asInt(),
                            p.hasNonNull("urimap") ? p.get("urimap").asText() : null,
                            p.hasNonNull("path") ? p.get("path").asText() : null, xs));
                }}
                task.withHttpPeers(peers);
            }}
            if (calen != null) {{
                task.withExactCommarea();
            }}
            if (sc.hasNonNull("userid")) task.withUserid(sc.get("userid").asText());  // #5126 (X19): ASSIGN USERID
            if (sc.hasNonNull("screen")) task.withScreen(sc.get("screen").get(0).asInt(), sc.get("screen").get(1).asInt());
            if (sc.hasNonNull("origin")) {{  // #4270 (X29): INQUIRE ASSOCIATION -- the origin data the case states
                JsonNode o = sc.get("origin");
                task.withOrigin(o.get("applid").asText(), o.get("userid").asText(), o.get("facilname").asText(),
                        o.get("networkid").asText(), o.get("faciltype").asText());
            }}
            // #4765: a LINKed task's COMMAREA bytes too, by reference (a caller's LINK passes both): a port that takes
            // them (task.linkArea()) leaves its result there, every occurrence of a table included
            byte[] area = sc.hasNonNull("area") ? java.util.HexFormat.of().parseHex(sc.get("area").asText()) : null;
            if (area != null) {{
                task.withLinkArea(area);
            }}
            if (sc.hasNonNull("channel")) {{  // #4270 (X24): the channel the task starts with, its current channel
                CicsTask.Channel channel = new CicsTask.Channel(sc.get("channel").get("name").asText());
                for (JsonNode k : sc.get("channel").get("containers")) {{
                    channel.with(k.get("name").asText(), java.util.HexFormat.of().parseHex(k.get("hex").asText()),
                            k.get("bit").asBoolean());
                }}
                task.withChannel(channel);
            }}
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
            {db2_begin}fileUnit(status -> {{
                task.onRollback(() -> {{ status.restart(); {db2_rollback_now}}});
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
                    // statement) is not judged -- recorded, never passed; any other failure stays a failure.
                    // #4607 x X6: a WRITEQ whose LENGTH is over 32767 (DetCics.PastFrom) ends the task there,
                    // as the stub stops it: judged up to it (equivalence_cics.x6_judged)
                    boolean x6 = "PastFrom".equals(e.getClass().getSimpleName())
                            || "PerformDepthExceeded".equals(e.getClass().getSimpleName());
                    if (!x6 && (!sc.path("derived").asBoolean() || !"Hole".equals(e.getClass().getSimpleName()))) {{
                        throw e;
                    }}
                    try {{
                        Files.writeString(out.resolve(sc.get("name").asText() + (x6 ? ".x6" : ".hole")),
                                String.valueOf(e.getMessage()));
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
                if (sc.path("raw_commarea").asBoolean() && "RETURN".equals(e.get("event")) && e.get("commarea") != null
                        && task.returnedBytes() != null) {{  // #6072: the bytes the RETURN passed, a DTO holds a long
                    copy.put("area", java.util.Base64.getEncoder().encodeToString(task.returnedBytes()));
                }}
{screen_copy}                events.add(copy);
            }}
            if (task.currentChannel() != null) {{  // #4270 (X24): the containers left on the task's current channel
                Map<String, Object> left = new LinkedHashMap<>();
                left.put("event", "CONTAINERS");
                left.put("channel", task.currentChannel().name());
                Map<String, String> data = new LinkedHashMap<>();
                task.currentChannel().containers().forEach((k, v) -> data.put(k, java.util.HexFormat.of().withUpperCase().formatHex(v)));
                left.put("containers", data);
                events.add(left);
            }}
            Object mqLeft = sc.hasNonNull("mq") ? mqEnd(task) : null;
            if (mqLeft != null) {{  // #4892: the queues the task left, as the stub's mq.out
                Map<String, Object> left = new LinkedHashMap<>();
                left.put("event", "MQ-QUEUES");
                left.put("queues", mqLeft);
                events.add(left);
            }}
            if (sc.hasNonNull("dli")) {{  // #5278: the databases the task left, by DBD, as the stub's exit dump
                Map<String, Object> left = new LinkedHashMap<>();
                left.put("event", "DLI-DBS");
                left.put("dbs", dliLeft(out.resolve(sc.get("name").asText() + ".dli"), sc.get("dli").get("dbs")));
                events.add(left);
            }}
            if (commarea != null) {{  // a LINKed program's result: the COMMAREA it leaves (equivalence_cics.linked_result)
                Map<String, Object> left = new LinkedHashMap<>();
                left.put("event", "COMMAREA");
                left.put("commarea", commarea);
                if (area != null && task.linkAreaTaken()) {{  // #4765: what the port left in the bytes it took
                    left.put("area", java.util.Base64.getEncoder().encodeToString(area));
                }}
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
{facade_java}
    /** #4270: the scenario's TS queues, each item's text in the region's code page (DetCics.region). */
    static CicsTask.TempStorage tempStorage(JsonNode sc) {{
        CicsTask.TempStorage ts = new CicsTask.TempStorage();
        Charset region = Charset.forName(System.getProperty("gitgalaxy.cics.charset", "{_region_page()}"));
        sc.path("ts").fields().forEachRemaining(q -> {{
            List<byte[]> items = new ArrayList<>();
            q.getValue().forEach(i -> items.add(i.asText().getBytes(region)));
            ts.seed(q.getKey(), items);
        }});
        sc.path("td").fields().forEachRemaining(q -> {{  // #5168 (X61): the TD queues' records
            List<String> records = new ArrayList<>();
            q.getValue().forEach(i -> records.add(i.asText()));
            ts.seedTd(q.getKey(), records);
        }});
        return ts;
    }}

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
    List<byte[]> records(JsonNode sc, String dd, int reclen) throws IOException {{
        byte[] data = Files.readAllBytes(input(sc, dd));
        List<byte[]> rows = new ArrayList<>();
        for (int i = 0; i + reclen <= data.length; i += reclen) {{
            rows.add(java.util.Arrays.copyOfRange(data, i, i + reclen));
        }}
        return rows;
    }}

    /** #4622: the dataset as the scenario starts with it: its own file (`DD.scenario.in`) when it states one. */
    Path input(JsonNode sc, String dd) {{
        Path own = in.resolve(dd + "." + sc.get("name").asText() + ".in");
        return Files.exists(own) ? own : in.resolve(dd + ".in");
    }}

    <E> void load(JsonNode sc, String dd, int reclen, BiFunction<byte[], Charset, E> fromRecord, JpaRepository<E, ?> repo)
            throws IOException {{
        byte[] data = Files.readAllBytes(input(sc, dd));
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


def no_service_programs(case: dict[str, Any], src: Path) -> list[str]:
    """The case's other programs (`"programs"`) whose service class is not in the project under `src`."""
    import equivalence_java as ej

    return [x["program"].upper() for x in case.get("programs", [])
            if not any(src.rglob(f"{ej._service_class(x['program'])}.java"))]  # fmt: skip


def sql_unjudged(plan: list[str], seams: set[str]) -> str:
    """The reason a scenario's SQL faults cannot be injected on the Java side ("" when they can): every fault
    names its statement's program (`PROGRAM LINE NTH SQLCODE SQLSTATE`), and that program's Java needs the seam."""
    missing = sorted({line.split()[0] for line in plan if line.split() and line.split()[0] not in seams})
    if not missing:
        return ""
    return f"no SQL fault hook in {', '.join(missing)} (its Java does not reach Db2 through cobolrt.sql.DetSql)"


def run_java_cics(case: dict[str, Any], corpus: Path, work: Path, cobol_work: Path, files: list[dict[str, Any]],
                  port: bool = True, port_dir: Path | None = None,
                  facade: dict[str, Any] | None = None,
                  one_jvm: bool = False) -> dict[str, list[dict[str, Any]]]:  # fmt: skip
    """The generated project runs every scenario as a CicsTask; {scenario: its events}, each
    COMMAREA mapped back to COBOL field names through the DTO's own comments.

    #4449: with `facade` (a dict to fill) the same project runs every scenario once more, the java-facade side: the
    task entered through the program's deployed entry point (handleTransaction, or handleLink for a LINKed program;
    a LINK target the case runs through its handleLink) with the scenario's region joined. `facade` gets `events`
    ({scenario: events}, as above), `entries` ({scenario: [{program, method}]}), `refused` ({scenario: why}) and
    `out` (the run's output directory); or `error` when that run itself fails.
    #4047: `one_jvm` runs the tasks and the facade run in one session JVM (a Db2 case keeps a JVM each)."""
    import json

    import equivalence_java as ej

    project = ej.prepare_project(case, corpus, work, "", port, port_dir)
    src = project / "src/main/java"
    absent = no_service_programs(case, src)
    if absent:  # #5126: the forge writes no service for these (HLASM), so the test would not compile: refuse by name
        raise RuntimeError(f"{', '.join(absent)}: a program the case LINKs to has no generated service and no port "
                           "(run it through its det port, `det_port.py run`)")  # fmt: skip
    svc = ej._service_class(case["program"])
    svc_file = next(src.rglob(f"{svc}.java"))
    ca_cls = commarea_class(case, src, svc_file)
    shape = (
        dto_shape(src, ca_cls, svc_file) if ca_cls else {}
    )  # #4011: the class the service imports, not any of that name
    seams = sql_seam_programs(case, src)  # #4173 x #4188: whose Java can take an injected SQL fault
    test = project / "src/test/java" / ej.PKG_DIR / "EquivalenceRunTest.java"
    test.write_text(
        cics_equivalence_test(
            case,
            src,
            files,
            csd_programs(corpus, case),
            csd_tdqueue_types(corpus, case),
            csd_tdqueue_attrs(corpus, case),
        ),
        encoding="utf-8",
    )
    inputs = work / "in"
    inputs.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy(cobol_work / "files" / f["base"], inputs / f"{f['base']}.in")
    stage_scenario_inputs(case, corpus, files, inputs)
    ca_fields = commarea_fields(corpus, case)  # as the DTO lists them: an OCCURS group's fields once
    ca_read = commarea_fields(corpus, case, occurrences=True)  # #4765: the whole record, every occurrence
    scenarios = []
    for sc in case["scenarios"]:
        ca, area = None, None
        if sc.get("commarea") is not None:  # the very COMMAREA the COBOL task started with, as the DTO
            enc = common.data_encoding(case)  # #3815
            raw_names = raw_commarea_names(
                sc["commarea"]
            )  # #6072: bytes the DTO cannot hold; the port gets them as `area`
            dto_ca = {k: v for k, v in sc["commarea"].items() if k not in raw_names}
            values = decode_record(commarea_record(ca_read, dto_ca, enc), ca_fields, enc, keep_nulls=True)
            # a value the DTO has no field for would reach the port as nothing at all: the case must name the
            # COMMAREA as the contract DTO's record does
            # #5233: a table's later occurrence (CDEMO-CPVS-AUTH-KEYS(3)) is the DTO's list property, set by the bytes
            tables = {n for n in _leaves(shape).values() if isinstance(n, TableField)}
            tabled = {k for k in sc["commarea"] if re.sub(r"\(\d+\)$", "", k) in tables}
            lost = sorted({k for k in sc["commarea"] if re.sub(r"\(\d+\)$", "", k) not in shape_names(shape)})
            if lost:
                raise Unsupported(f"scenario {sc['name']}: the COMMAREA DTO {ca_cls} has no field for {lost} -- "
                                  f"describe the COMMAREA with the record the DTO is generated from")  # fmt: skip
            ca = to_java(values, shape, alphanumeric(ca_fields))
            if (case.get("linked") or tabled or raw_names) and not sc.get(
                "dto_entry"
            ):  # #4765: the very bytes the COBOL task was LINKed with (CicsTask.withLinkArea)
                # #5863: a scenario with "dto_entry" gives the port the DTO alone -- the bytes would overwrite every
                # field the typed entry (in_) maps, and hide a defect there; the COBOL side still runs the same record
                area = commarea_record(ca_read, sc["commarea"], enc).hex().upper()
        # A typed field is named as the symbolic map names its input (ACCTSIDI); a screen view model
        # keys it by the BMS field (ACCTSID), as screenValues() / fromValues() do.
        receive = {
            m: {f.removesuffix("I"): v for f, v in typed.items()} for m, typed in (sc.get("receive") or {}).items()
        }
        scenarios.append({"name": sc["name"], "aid": sc.get("aid", "DFHENTER").removeprefix("DFH"),
                          "commarea": ca, "area": area, **({"raw_commarea": True} if raw_names_of(sc) else {}), "receive": receive, "faults": fault_lines(sc), "sql_faults": sc.get("sql_plan", []),
                          "dli_faults": dli_fault_lines(case, sc),
                          "sql_unjudged": sql_unjudged(sc.get("sql_plan", []), seams),
                          "derived": bool(sc.get("derived")), "commarea_length": commarea_length(sc, ca_read),
                          **_java_untyped_commarea(case, sc, ca_read),
                          "channel": _channel_json(case, sc),
                          "counters": _counters(case, sc), "taskn": task_number(case, sc),
                          "startcode": task_facts(case, sc)[0], "terminal": task_facts(case, sc)[1],
                          **terminal_facts(case, sc),
                          **({"clock": ej._clock({**case, "clock": scenario_clock(case, sc)})} if "clock" in sc else {}),
                          **({"tod": scenario_tod(case, sc)} if scenario_tod(case, sc) else {}),
                          "ts": cics_tempstorage.ts_seed(case, sc), "urimaps": urimaps(case, sc),
                          **({"td": td_seed(case, sc)} if td_seed(case, sc) else {}),
                          "doctemplates": doctemplates(case, sc), "http_peers": http_peers(case, sc),
                          "http_request": http_request(case, sc), "tcpip": tcpip(case, sc),
                          **_java_mq(case, sc, inputs, len(scenarios)), **_java_dli(case, corpus, inputs, sc)})  # fmt: skip
    (inputs / "scenarios.json").write_text(json.dumps(scenarios, indent=1), encoding="utf-8")
    props = ej.data_charset_arg(case)
    if case.get("db2"):  # the seed and the dump queries, and the harness's Db2
        (inputs / "db2reset.sql").write_text(equivalence_db2.reset_script(case, corpus), encoding="latin-1")
        (inputs / "db2dumps.txt").write_text("".join(
            f"{t}\t{'|'.join(n)}\t{equivalence_db2.dump_query(t, n)}\n"
            for t, n in ((t, equivalence_db2.columns(t)) for t in case["db2"].get("compare", []))), encoding="latin-1")  # fmt: skip
        props = f"{props} {equivalence_db2.java_props(case)}"
    import equivalence_call

    sessions = equivalence_call.sessions_for(case, project, one_jvm)
    try:
        out = ej.run_maven(project, work, inputs, props=props, session=sessions.get() if sessions else None)
        result = _java_events(case, out, shape, ca_read)
        if facade is not None:  # #4449: the java-facade side, the same project and inputs
            _run_facade(ej, project, work, inputs, props, sessions, case, shape, ca_read, facade)
        return result
    finally:
        if sessions:
            sessions.close()


def _java_untyped_commarea(case: dict[str, Any], sc: dict[str, Any], ca_fields: list[dict[str, Any]]) -> dict[str, Any]:
    """#5859: an untyped COMMAREA for the Java side: the stated bytes are in the case's data page (what the stub's
    commarea.in holds), the port's are in the region's (CCSID 037), as for a START's data (_java_mq); its length is EIBCALEN."""
    from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

    raw = untyped_commarea(case, sc, ca_fields)
    if raw is None:
        return {}
    page = raw.decode(common.data_encoding(case)).encode(REGION_PAGE)
    return {"commarea_hex": page.hex().upper(), "untyped_length": len(page)}


def _run_facade(ej: Any, project: Path, work: Path, inputs: Path, props: str, sessions: Any, case: dict[str, Any],
                shape: Any, ca_read: Any, facade: dict[str, Any]) -> None:  # fmt: skip
    """#4449: the facade run into `facade` (`error` when the run itself fails)."""
    try:
        fout = ej.run_maven(project, work / "facade", inputs, props=f"{props} -Dequivalence.facades=true",
                            session=sessions.get() if sessions else None)  # fmt: skip
    except RuntimeError as e:
        facade["error"] = str(e)
        return
    facade["out"] = fout
    facade["events"] = _java_events(case, fout, shape, ca_read)
    facade["entries"], facade["refused"] = {}, {}
    for sc in case["scenarios"]:
        ent, why = fout / f"{sc['name']}.entries.json", fout / f"{sc['name']}.refused"
        facade["entries"][sc["name"]] = json.loads(ent.read_text(encoding="utf-8")) if ent.is_file() else []
        if why.is_file():
            facade["refused"][sc["name"]] = why.read_text(encoding="utf-8")


def _java_dli(case: dict[str, Any], corpus: Path, inputs: Path, sc: dict[str, Any]) -> dict[str, Any]:
    """#5278: a case whose program issues EXEC DLI: the databases' directory (the very files the stub reads) and their names."""
    if not case.get("ims") or not DLI_CALL.search(common.read_program(case, corpus / case["program_source"])[0]):
        return {}
    where = f"dli-{sc['name']}" if sc.get("ims_seed") else "dli"  # #6072: a scenario's own seed, its own directory
    return {"dli": {"dir": where, "dbs": dli_stage(case, corpus, inputs / where, sc)}}


def _java_mq(case: dict[str, Any], sc: dict[str, Any], inputs: Path, n: int) -> dict[str, Any]:
    """#4892: the scenario's start data (hex, in the region's page: CicsTask.withRetrieveData, as the stub's
    retrieve_NNN.bin) and its queue manager's mq.cfg (the stub's very file, under the runner's inputs); none: no key."""
    from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

    enc, out = common.data_encoding(case), {}
    data = equivalence_mq.start_data(case, sc, enc)
    if data:
        out["start_data"] = [d.decode(enc).encode(REGION_PAGE).hex().upper() for d in data]
    st = equivalence_mq.state(case, sc)
    if st is not None:
        (inputs / f"mq_{n}.cfg").write_text(equivalence_mq.cfg(st, enc), encoding="ascii")
        out["mq"] = f"mq_{n}.cfg"
    return out


def java_commarea(value: Any, shape: dict[str, Any], ca_fields: list[dict[str, Any]], enc: str) -> dict[str, Any]:
    """A Java event's COMMAREA by COBOL field names: a DTO's JSON through its shape (from_java) -- or, #4679, a
    byte[] (Jackson writes it base64): the LENGTH bytes a RETURN / XCTL with a LENGTH past the DTO passed
    (DetCics.commareaOut), in the region's code page (CCSID 037). Those are read as the COBOL side's are: in the case's
    data page, by the case's COMMAREA layout (decode_record), so bytes past the layout are not compared on either side --
    and, as the COBOL side's RETURN area is since #4635, `exact`: LOW-VALUES kept apart from spaces."""
    if isinstance(value, str):
        import base64

        from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

        data = base64.b64decode(value).decode(REGION_PAGE).encode(enc)
        if not ca_fields:  # nothing to read it by -- refused, never compared as empty (as the COBOL side's)
            raise Unsupported(
                'a COMMAREA passed as bytes, in a case that describes none ("commarea": null)', ["COMMAREA"]
            )
        return decode_record(data, ca_fields, enc, exact=True, unnamed=True)
    return first_occurrences(from_java(value, shape), ca_fields)


def first_occurrences(values: dict[str, Any], fields: list[dict[str, Any]]) -> dict[str, Any]:
    """#4765: a DTO's values by the layout's names. A generated DTO lists an OCCURS group's fields once ("Fields
    inside an OCCURS group appear once"), at the first occurrence: COMM-ACC-TYPE is COMM-ACC-TYPE(1) of a layout with
    every occurrence. The others it does not carry, so they are absent -- compared, never assumed equal."""
    first = {f["base"]: f["name"] for f in fields if f.get("subscripts") and all(k == 1 for k in f["subscripts"])}
    out: dict[str, Any] = {}
    for k, v in values.items():
        name = first.get(k, k)
        if isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v):  # #5233: a table of scalars
            out.update({re.sub(r"\(1\)$", f"({i})", name): x for i, x in enumerate(v, 1)})
        else:
            out[name] = v
    return out


def java_area(area: str, ca_fields: list[dict[str, Any]], enc: str) -> dict[str, Any]:
    """#4765: the COMMAREA a LINKed task left, as its bytes -- the area the runner passed by reference
    (CicsTask.withLinkArea) when the port took it (task.linkArea(): a det port, whose DFHCOMMAREA is those bytes) --
    read by the case's COMMAREA layout, every occurrence of a table, as the COBOL side's (commarea.out) is."""
    import base64

    if not ca_fields:
        raise Unsupported('a COMMAREA passed as bytes, in a case that describes none ("commarea": null)', ["COMMAREA"])
    return decode_record(base64.b64decode(area), ca_fields, enc, exact=True, unnamed=True)


def _java_events(case: dict[str, Any], out: Path, shape: dict[str, Any],
                 ca_fields: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:  # fmt: skip
    """{scenario: the events the Java run wrote to out/<scenario>.json}, each COMMAREA by COBOL field names."""
    import json

    enc = common.data_encoding(case)

    def child(e: dict[str, Any]) -> None:  # #4950: a RUN TRANSID child's events, as a task's (no COMMAREA)
        for x in e.get("events") or []:
            if x.get("event") == "CHILD":
                child(x)
            elif "commarea" in x:
                x["commarea"] = None

    result = {}
    for sc in case["scenarios"]:
        f = out / f"{sc['name']}.json"
        events = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
        for e in events:
            if e.get("event") == "CHILD":
                child(e)
            if e.get("event") == "LINK":  # #4173: the target's DTO as issued, before it is mapped to this program's
                e["link_area"] = e.get("commarea")
            if e.get("event") == "WRITEQ-TS":  # #4607: the item's bytes as text
                e.update(cics_tempstorage.java_ts_as_compared(e))
            if e.get("event") == "READQ-TS":  # #4270: the item's bytes as text
                e.update(java_read_as_compared(e))
            if e.get("event") == "START":  # #4270: the FROM data's bytes as text
                e.update(cics_taskcontrol.java_start_as_compared(e))
            if e.get("event") == "RETRIEVE":  # #5089: the data's bytes as text
                e.update(cics_taskcontrol.java_retrieve_as_compared(e))
            xctl_bytes = (
                e.get("event") == "XCTL" and e.get("area") is not None and bool(ca_fields)
                and isinstance(e.get("commarea"), dict) and not set(e["commarea"]) <= set(shape)
            )  # fmt: skip
            # #6072: an XCTL area of another program's DTO (ZECS001 -> ZECS003), not this program's shape: its bytes
            if xctl_bytes or (
                e.get("event") in ("COMMAREA", "RETURN") and e.get("area") is not None
            ):  # #4765: the bytes the port left
                # #6072: a RETURN too, when the scenario states raw COMMAREA bytes (its DTO holds a number for them)
                if (
                    e.get("event") == "COMMAREA" and sc.get("dto_entry") and isinstance(e.get("commarea"), dict)
                ):  # #5863: the DTO too (compare_events)
                    e["dto"] = java_commarea(e["commarea"], shape, ca_fields or [], enc)
                e["commarea"] = java_area(e.pop("area"), ca_fields or [], enc)
            elif e.get("event") == "COMMAREA" and isinstance(e.get("commarea"), str) and not ca_fields:
                pass  # #5859: an untyped COMMAREA's end storage: linked_result drops it for a program not LINKed to, as the stub's
            elif "commarea" in e:
                if isinstance(e["commarea"], dict):  # #4778: a DTO -- no property holds a FILLER (compare_events)
                    e["commarea_dto"] = True
                e["commarea"] = (
                    java_commarea(e["commarea"], shape, ca_fields or [], enc) if e["commarea"] is not None else None
                )
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
            fields = common.layout_fields(corpus, spec["copybook"], spec.get("record"), dirs, occurrences=True)  # #4765
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
            # (#4635: a text field the harness left all LOW-VALUES, now that a COMMAREA keeps its LOW-VALUES apart
            # from spaces, is the same undefined storage)
            undefined |= {k for k, v in ca.items()
                          if isinstance(v, str) and re.fullmatch(r"<invalid b'(\\x00)+'>|\x00+", v)}  # fmt: skip
            # #4778: a FILLER's bytes (decode_record `unnamed`), all LOW-VALUES: the same undefined storage
            undefined |= {k for k, v in ca.items() if k.startswith("FILLER@") and re.fullmatch(r"(00)+", v or "")}
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
        for k in ("text", "data"):  # a WRITEQ record that carries the clock (X6: LGAPDB01's CICA line past its FROM)
            if isinstance(e.get(k), str):
                v = _CLOCK.sub(lambda m: "<clock>" if _from_clock(m.group()) else m.group(), e[k])
                if v != e[k]:
                    counter[0] += 1
                    e = {**e, k: v}
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
    text_options = iter(res.get("text_options", []))
    queued = iter(res.get("ts", []))
    operator = iter(res.get("operator", []))
    reads = iter(res.get("reads", []))  # #4270: READQ TS / terminal RECEIVE
    starts = iter(res.get("starts", []))  # #4270: START
    retrieves = iter(res.get("retrieves", []))  # #5089: RETRIEVE
    mq_calls = iter(res.get("mq", []))  # #4892: MQI calls
    webs = iter(res.get("web", []))  # #4767 (X35): WEB CONVERSE
    webopens = iter(res.get("webopen", []))  # #4767 (X35): WEB OPEN
    webcloses = iter(res.get("webclose", []))  # #4767 (X35): WEB CLOSE
    websends = iter(res.get("websend", []))  # #4767 (X37): WEB SEND
    webheaders = iter(res.get("webheader", []))  # #4767 (X38): WEB WRITE HTTPHEADER
    webreceives = iter(res.get("webreceive", []))  # #4767 (X38): WEB RECEIVE
    children = iter(res.get("children", []))  # #4950: RUN TRANSID children
    for line in res["events"]:
        verb, _, args = line.partition(" ")
        if verb == "SEND-MAP":
            s = next(screens)
            out.append({"event": "SEND-MAP", "map": s["map"], **({"mapset": s["mapset"]} if "mapset" in s else {}), "screen": s["fields"], "subfields": s["subfields"],
                        "options": s["options"], "cursor": s["cursor"]})  # fmt: skip
        elif verb == "SEND-TEXT":  # #5401: its options too, as CicsTask.sendText records them
            out.append({"event": "SEND-TEXT", "text": next(texts), "options": next(text_options, [])})
        elif verb == "SEND-CONTROL":  # #4270: CicsTask.sendControl records it -- its options and CURSOR's offset
            cur = int((re.search(r"\bcursor=(-?\d+)", args) or [None, "-1"])[1])
            out.append({"event": "SEND-CONTROL", "options": args.partition("opts=")[2].split(),
                        "cursor": cur if cur >= 0 else None})  # fmt: skip
        elif verb in ("SYNCPOINT", "SYNCPOINT-ROLLBACK"):  # file updates: CicsTask.syncpoint / rollback record them
            out.append({"event": verb})
        elif verb == "WRITEQ-TD":  # CicsTask.writeqTd records the queue and the record's text
            queue = re.search(r"\bqueue=(\S*)", args).group(1)
            resp = re.search(r"\bresp=(\S*)", args).group(1)
            out.append({"event": "WRITEQ-TD", "queue": queue, "text": next(records) if resp == "0" else None})
        # #5859 (X32): as CicsTask.verifyPassword records it -- the USERID and the verdict
        elif verb == "VERIFY-PASSWORD":
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append(
                {
                    "event": "VERIFY-PASSWORD",
                    "userid": kv["userid"],
                    "resp": RESP_NAMES.get(int(kv["resp"]), kv["resp"]),
                }
            )
        elif verb == "WRITE-OPERATOR":  # #4270 zECS (X32): CicsTask.writeOperator records the text
            out.append({"event": "WRITE-OPERATOR", "text": next(operator)})
        elif verb == "WEB-CONVERSE":  # #4767 (X35): CicsTask.webConverse records the request sent
            out.append({"event": "WEB-CONVERSE", **next(webs)})
        elif verb == "WEB-OPEN":  # #4767 (X35): CicsTask.webOpenHost / webOpenUrimap record the connection
            out.append({"event": "WEB-OPEN", **next(webopens)})
        elif verb == "WEB-CLOSE":  # #4767 (X35): CicsTask.webClose records the session closed
            out.append({"event": "WEB-CLOSE", **next(webcloses)})
        elif verb == "WEB-SEND":  # #4767 (X37): CicsTask.webSend records the response sent
            out.append({"event": "WEB-SEND", **next(websends)})
        elif verb == "WEB-HEADER":  # #4767 (X38): CicsTask.webWriteHeader records the header written
            out.append({"event": "WEB-HEADER", **next(webheaders)})
        elif verb == "WEB-RECEIVE":  # #4767 (X38): CicsTask.webReceive records the body read
            out.append({"event": "WEB-RECEIVE", **next(webreceives)})
        elif verb == "WRITEQ-TS":  # #4607: CicsTask.writeqTs records it (queue, data, resp, item)
            out.append({"event": "WRITEQ-TS", **next(queued)})
        elif verb in ("READQ-TS", "READQ-TD", "RECEIVE"):  # #4270: CicsTask records them (queue, item, resp, data)
            out.append(next(reads))
        elif verb == "START":  # #4270 (GenApp LGWEBST5): CicsTask.start records it
            out.append({"event": "START", **next(starts)})
        elif verb == "RETRIEVE":  # #5089: CicsTask.retrieve records it
            out.append({"event": "RETRIEVE", **next(retrieves)})
        elif verb in equivalence_mq.EVENTS:  # #4892
            out.append(next(mq_calls))
        elif verb == "RECEIVE-MAP":  # #4009: CicsTask.receive records it too
            mapset = re.search(r"\bmapset=(\S*)", args)  # #5862: the mapset too, as CicsTask.receive records it
            out.append({"event": "RECEIVE-MAP", "map": re.search(r"\bmap=(\S*)", args).group(1),
                        **({"mapset": mapset.group(1)} if mapset else {})})  # fmt: skip
        elif verb == "RETURN":
            lvl = re.search(r"\blevel=(\d+)", args)
            if "resp=" in args:  # #4270: a RETURN IMMEDIATE that failed (INVREQ / LENGERR): CicsTask.returnImmediate
                kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
                out.append(
                    {
                        "event": "RETURN",
                        "level": int(kv["level"]),
                        "immediate": True,
                        "transid": kv["transid"],
                        "resp": RESP_NAMES.get(int(kv["resp"]), kv["resp"]),
                        "resp2": int(kv["resp2"]),
                    }
                )
            elif lvl and int(lvl.group(1)) > 1:  # a LINKed program's RETURN: back to its caller, no COMMAREA of its own
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
        elif (
            verb == "ENQ"
        ):  # #5089 (X60): an ENQ the scenario planned busy: CicsTask.enq records it (the others record none)
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            e = {"event": "ENQ", "resource": kv["resource"], "resp": RESP_NAMES.get(int(kv["resp"]), kv["resp"])}
            if "resp2" in kv:  # X60: LENGERR 1 / INVREQ 2 from the operands (a planned ENQBUSY states none)
                e["resp2"] = int(kv["resp2"])
            out.append(e)
        elif verb == "CANCEL":  # #5079 (X63): as CicsTask.cancel records it -- the REQID and the condition
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append({"event": "CANCEL", "reqid": kv.get("reqid", ""),
                        "resp": RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))})  # fmt: skip
        elif verb == "RUN":  # #4270: RUN TRANSID CHILD, as CicsTask.runTransid records it (the child is not run here)
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            resp = RESP_NAMES.get(int(kv.get("resp", "0")), kv.get("resp", ""))
            out.append({"event": "RUN", "transid": kv.get("transid", ""), "resp": resp})
        elif verb == "FETCH":  # #4884, #4950: as CicsTask.fetch records it (on NORMAL: the child and what it left)
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            e = {"event": "FETCH", "resp": RESP_NAMES.get(int(kv["resp"]), kv["resp"]), "resp2": int(kv["resp2"])}
            if "child" in kv:
                e.update({"child": kv["child"], "compstatus": kv["compstatus"],
                          "abcode": None if kv["abcode"] == "-" else kv["abcode"],
                          "channel": None if kv["channel"] == "-" else kv["channel"]})  # fmt: skip
            out.append(e)
        elif verb == "FREE-CHILD":  # #4950: as CicsTask.freeChild records it
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append({"event": "FREE-CHILD", "resp": RESP_NAMES.get(int(kv["resp"]), kv["resp"]),
                        "resp2": int(kv["resp2"])})  # fmt: skip
        elif verb == "CHILD":  # #4950: a RUN TRANSID child the task's wait dispatched, its events as a whole
            kv = dict(a.split("=", 1) for a in args.split() if "=" in a)
            out.append({"event": "CHILD", "child": kv["child"], "transid": kv["transid"],
                        "events": cobol_events(next(children))})  # fmt: skip
    if res.get("containers") is not None:  # #4270 (X24): the containers the task leaves on its current channel
        out.append({"event": "CONTAINERS", **res["containers"]})
    if res.get("mq_queues") is not None:  # #4892: the queues the task leaves (its normal end commits it)
        out.append({"event": "MQ-QUEUES", "queues": res["mq_queues"]})
    if res.get("dli") is not None:  # #5278: the databases the task leaves, each in hierarchic sequence
        out.append({"event": "DLI-DBS", "dbs": {k: v.hex().upper() for k, v in res["dli"].items()}})
    if res.get("linked_commarea") is not None:
        out.append({"event": "COMMAREA", "commarea": res["linked_commarea"]})
    return out


def _link_as_compared(e: dict[str, Any]) -> dict[str, Any]:
    """A LINK event as both sides compare it: its target (the Java side's also carries its COMMAREA and RESP)."""
    if e.get("event") == "LINK":
        return {"event": "LINK", "program": e.get("program") or e.get("target")}
    return e


_STATE_EVENTS = frozenset({"COMMAREA", "CONTAINERS", "DLI-DBS", "MQ-QUEUES"})  # end-state snapshots, not commands


def executed_commands(events: list[dict[str, Any]]) -> list[str]:
    """#5229: the distinct stub verbs the COBOL task executed (the oracle side, before any judging mask), sorted."""
    return sorted({e["event"] for e in events if e.get("event") and e["event"] not in _STATE_EVENTS})


def linked_result(case: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A LINKed program's events (`"linked": true` in the case): its result is the COMMAREA it leaves in its caller's
    storage, compared as a last COMMAREA event -- unless the task abended (no caller sees it then). Any other
    program's final COMMAREA storage is not observable (a terminal task's RETURN COMMAREA is), so it is dropped."""
    abended = any(e.get("event") == "ABEND" for e in events)
    keep = case.get("linked") and not abended
    # #4270 (X24): the containers left on the task's current channel are its result to whoever passed the channel
    # (a LINK CHANNEL caller, a FETCH CHILD parent) -- unless the task abended, as the COMMAREA
    return [_link_as_compared(e) for e in events
            if (e.get("event") != "COMMAREA" or keep) and (e.get("event") != "CONTAINERS" or not abended)]  # fmt: skip


def _same(a: Any, b: Any) -> bool:
    """Equal as the task means it: decimals exactly, text ignoring trailing blanks, absent == empty."""
    if a is None or b is None:
        return str(a or "").rstrip() == str(b or "").rstrip()
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except ArithmeticError:
        return str(a).rstrip(" \x00") == str(b).rstrip(" \x00")


def _same_commarea(a: Any, b: Any) -> bool:
    """#4635: a COMMAREA field as the next program reads it -- like `_same`, except that LOW-VALUES are not blanks:
    only trailing spaces are dropped, so X'00' bytes and spaces differ."""
    if a is None or b is None or isinstance(a, (int, float)) or isinstance(b, (int, float)):
        return _same(a, b)
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except ArithmeticError:
        return str(a).rstrip(" ") == str(b).rstrip(" ")


def compare_task_sysout(cobol: bytes, java_file: Path, enc: str) -> dict[str, Any]:
    """#4635: what the task DISPLAYed on each side, line by line (equivalence_common.compare_sysout, as a batch
    step's SYSOUT is, #4056). The Java side wrote nothing when the port never DISPLAYs: an empty log."""
    return common.compare_sysout(cobol, java_file.read_bytes() if java_file.is_file() else b"", enc)


def compare_events(cobol: list[dict[str, Any]], java: list[dict[str, Any]]) -> dict[str, Any]:
    """Events paired in order; per pair, every differing field. {events, equal, diffs}, and #4778 `not_compared`:
    a COMMAREA's FILLER bytes (decode_record `unnamed`) when the Java side gave back a DTO, which has no property for
    them -- listed with that reason, never counted equal."""
    diffs, equal, not_compared = [], 0, {}
    for n in range(max(len(cobol), len(java))):
        c = cobol[n] if n < len(cobol) else None
        j = java[n] if n < len(java) else None
        if c is None or j is None or c["event"] != j["event"]:
            diffs.append({"event": n + 1, "cobol": c and c["event"], "java": j and j["event"]})
            continue
        bad = []
        for key in ("map", "transid", "program", "text", "abcode", "queue", "data", "resp", "item", "resource"):
            if key in c and not _same(c[key], j.get(key)):
                bad.append({"field": key, "cobol": c[key], "java": j.get(key)})
        if "mapset" in c and c["mapset"] != j.get("mapset"):  # #5862: the MAPSET of a SEND / RECEIVE MAP
            bad.append({"field": "mapset", "cobol": c["mapset"], "java": j.get("mapset")})
        if c["event"] == "START":  # #4270: what CicsTask.start records besides the transid and RESP, both ways
            for key in ("termid", "interval", "time", "reqid", "protect", "resp2", "expires", "from",
                        "rtransid", "rtermid", "queue", "channel"):  # fmt: skip
                if (key in c or key in j) and not _same(c.get(key), j.get(key)):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-CONVERSE":  # #4767 (X35): the request each side sent, both ways
            for key in ("host", "method", "path", "query", "mediatype", "body", "resp2"):  # (exactly: blanks are sent)
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-OPEN":  # #4767 (X35): the connection each side opened, both ways
            for key in ("host", "scheme", "resp2"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-CLOSE" and c.get("resp2") != j.get("resp2"):  # #4767 (X35): NOTOPEN 27 or normal
            bad.append({"field": "resp2", "cobol": c.get("resp2"), "java": j.get("resp2")})
        if c["event"] == "WEB-HEADER":  # #4767 (X38): the response header each side wrote, both ways
            for key in ("name", "value", "resp2"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-RECEIVE":  # #4767 (X38): the body each side read and its media type, both ways
            for key in ("mediatype", "body", "resp", "resp2"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "WEB-SEND":  # #4767 (X37): the response each side sent, both ways
            for key in ("status", "statustext", "mediatype", "body", "action", "resp2"):  # (exactly: blanks are sent)
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] in (*equivalence_mq.EVENTS, "MQ-QUEUES"):  # #4892: the MQI call's outcome, the queues left
            bad += equivalence_mq.compare(c, j)
        if c["event"] == "CONTAINERS":  # #4270 (X24): the channel's name and every container's bytes, both ways
            if c.get("channel") != j.get("channel"):
                bad.append({"field": "channel", "cobol": c.get("channel"), "java": j.get("channel")})
            cc, jc = c.get("containers") or {}, j.get("containers") or {}
            for name in sorted(set(cc) | set(jc)):
                if cc.get(name) != jc.get(name):
                    bad.append({"field": f"containers.{name}", "cobol": cc.get(name), "java": jc.get(name)})
        for part in ("screen", "commarea"):
            cv, jv = c.get(part) or {}, j.get(part) or {}
            same = _same_commarea if part == "commarea" else _same
            for name in cv:
                if part == "commarea" and name.startswith("FILLER@") and j.get("commarea_dto"):
                    not_compared[f"commarea.{name}"] = UNNAMED_IN_A_DTO
                    continue
                if not same(cv[name], jv.get(name)):
                    bad.append({"field": f"{part}.{name}", "cobol": cv[name], "java": jv.get(name)})
        for name, value in (j.get("dto") or {}).items():  # #5863: a LINKed port's DTO too, beside the bytes it left
            if name in (c.get("commarea") or {}) and not _same_commarea(c["commarea"][name], value):
                bad.append({"field": f"commarea.dto.{name}", "cobol": c["commarea"][name], "java": value})
        if c["event"] == "SEND-TEXT" and "options" in c:  # #5401: the options the translation forwards, both ways
            java_options = sorted(o for o in j.get("options") or [] if o in TEXT_OPTIONS_FORWARDED)
            if c["options"] != java_options:
                bad.append({"field": "options", "cobol": c["options"], "java": java_options})
        if c["event"] == "SEND-CONTROL":  # #4270: ERASE / FREEKB / ALARM ... and the cursor, as the crucible compares
            if sorted(c.get("options") or []) != sorted(j.get("options") or []):
                bad.append({"field": "options", "cobol": c.get("options"), "java": j.get("options")})
            if c.get("cursor") != j.get("cursor"):
                bad.append({"field": "cursor", "cobol": c.get("cursor"), "java": j.get("cursor")})
        if c["event"] == "SEND-MAP" and "subfields" in c:  # #4053: attributes, colour, highlight, cursor, options
            cs, js = c["subfields"], java_subfields(j.get("subfields"))
            for name in sorted(set(cs) | set(js)):
                if cs.get(name, {}) != js.get(name, {}):
                    bad.append({"field": f"subfields.{name}", "cobol": cs.get(name, {}), "java": js.get(name, {})})
            if sorted(c.get("options") or []) != sorted(j.get("options") or []):
                bad.append({"field": "options", "cobol": c.get("options"), "java": j.get("options")})
            if c.get("cursor") != j.get("cursor"):
                bad.append({"field": "cursor", "cobol": c.get("cursor"), "java": j.get("cursor")})
        if c["event"] in ("FETCH", "FREE-CHILD"):  # #4950: the child fetched and what it left, both ways
            for key in ("resp2", "child", "compstatus", "abcode", "channel"):
                if (key in c or key in j) and c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
        if c["event"] == "CHILD":  # #4950: a RUN TRANSID child's own events, compared as a task's
            for key in ("child", "transid"):
                if c.get(key) != j.get(key):
                    bad.append({"field": key, "cobol": c.get(key), "java": j.get(key)})
            sub = compare_events(c.get("events") or [], [_link_as_compared(x) for x in j.get("events") or []])  # #6967
            if sub["diffs"]:
                bad.append({"field": "events", "cobol": sub["diffs"], "java": None})
        if bad:
            diffs.append({"event": n + 1, "kind": c["event"], "fields": bad})
        else:
            equal += 1
    out = {"events": max(len(cobol), len(java)), "equal": equal, "diffs": diffs}
    if not_compared:
        out["not_compared"] = not_compared
    return out


UNNAMED_IN_A_DTO = ("a FILLER: the Java side gave back the COMMAREA as a DTO, which has no property for it (a port "
                    "that gives back the bytes -- a det port LINKed with them, or a COMMAREA past its DTO -- has it "
                    "compared)")  # fmt: skip


def report_markdown(case: dict[str, Any], report: dict[str, Any]) -> str:
    about = (
        f"Case `{case['name']}`: {case['corpus']} `{case['program_source']}`, transaction {case['transid']}, "
        f"clock `{case['clock']}`. Each scenario is one task; its events (SEND MAP, SEND TEXT, RETURN, "
        "XCTL, ABEND) are paired in order and compared field by field -- screen DATA fields and every "
        "COMMAREA field; a SEND MAP also its attribute, colour and highlight bytes, cursor and options "
        "(X'00' and X'40' are not claimed)."
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
    for name, d in report["outputs"].items():
        so = d.get("sysout") or {}
        if so.get("diffs"):  # #4635: the task's DISPLAY output
            lines += ["", f"## {name}: DISPLAY output differs", "", "| line | COBOL | Java |", "|---|---|---|"]
            lines += [f"| {x['line']} | `{x['cobol']}` | `{x['java']}` |" for x in so["diffs"]]
    return "\n".join(lines) + "\n"


def feedback_md(case: dict[str, Any], report: dict[str, Any], limit: int = 6) -> str:
    """#4023 follow-up: the proof's findings for the porting loop's next attempt -- per scenario that is not equal,
    its inputs (COMMAREA, key, screen input, injected conditions) and the first differing events, field by field."""
    out: list[str] = []
    for sc in case["scenarios"]:
        o = report["outputs"].get(sc["name"])
        fired = (o or {}).get("fired")
        bad_fired = bool(sc.get("faults") or sc.get("dli_faults")) and (
            not fired or not fired["cobol"] or fired["cobol"] != fired["java"]
        )
        files = {n: f for n, f in (o or {}).get("files", {}).items() if f["equal"] != f["records"]}
        sql = (o or {}).get("sql") or {}
        sql_bad = sql.get("equal") != sql.get("statements")
        sysout_bad = bool((o or {}).get("sysout", {}).get("differing"))  # #4635
        if o is None or (o["equal"] == o["records"] and not bad_fired and not files and not sql_bad
                         and not sysout_bad):  # fmt: skip
            continue
        out += [f"### Scenario {sc['name']}: {o['equal']}/{o['records']} events equal", "",
                f"Key {sc.get('aid', 'DFHENTER')}; COMMAREA {json.dumps(sc.get('commarea'))}; "
                f"screen input {json.dumps(sc.get('receive'))}"
                + (f"; injected {json.dumps(sc['faults'])}" if sc.get("faults") else "")
                + (f"; DL/I {json.dumps(sc['dli_faults'])}" if sc.get("dli_faults") else ""), ""]  # fmt: skip
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
        if sysout_bad:  # #4635: what the task DISPLAYed
            out.append(f"- DISPLAY output: {o['sysout']['differing']} line(s) differ")
            out += [
                f"  - line {x['line']}: COBOL `{x['cobol']}`, Java `{x['java']}`" for x in o["sysout"]["diffs"][:limit]
            ]
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


PERFORM_DEPTH = "stack overflow, possible PERFORM depth exceeded"
PERFORM_DEPTH_JUDGED = ("the stack check of a recursive PERFORM (C20: IBM leaves it unpredictable; both sides stop at "
                        "libcob's 255 nested PERFORMs) -- what the task did before it is compared, its end state is not")  # fmt: skip
X6_JUDGED = ("the refused WRITEQ (X6: its LENGTH is over 32767, past the pad record; a LENGTH past FROM alone is written padded, #6573; not settled on z/OS, #4050) -- what the task did "
             "before it is compared, its end state (files, tables, the COMMAREA it leaves) is not")  # fmt: skip
X23_JUDGED = ("the refused reference past EIBCALEN (X23: a COMMAREA of a stated length; z/OS shows whatever storage "
              "follows it) -- what the task did before it is compared, its end state (files, tables, the COMMAREA it "
              "leaves) is not")  # fmt: skip


def judged_to(x6: dict[str, Any]) -> str:
    """The report's `judged_to` for a task stopped at a refusal (x6_judged): X6's words, or X23's."""
    return {"X23": X23_JUDGED, "C20": PERFORM_DEPTH_JUDGED}.get(x6.get("assumes"), X6_JUDGED)


def x6_judged(sc: dict[str, Any], java_out: Path, cev: list[dict[str, Any]],
              jev: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:  # fmt: skip
    """Owner decision on #4607 (X6): a task either side stopped at a WRITEQ whose LENGTH is over 32767 (X6; padded below that) -- the stub
    (`prefix_x6`, run_cobol_cics) or the Java side (`<scenario>.x6`: DetCics.PastFrom) -- is judged up to that
    WRITEQ, as #4173 judges a task up to a LINK not run: both sides' events without the COMMAREA left, and `ok` only
    when BOTH sides refused there. None for a task neither side stopped."""
    f = java_out / f"{sc['name']}.x6"
    java = f.read_text(encoding="utf-8").strip() if f.is_file() else None
    if not sc.get("prefix_x6") and java is None:
        return cev, jev, None
    end = ("COMMAREA", "CONTAINERS")  # the end state, not compared for a task judged up to a refusal
    left = [e for e in cev if e.get("event") not in end], [e for e in jev if e.get("event") not in end]
    cobol = sc.get("prefix_x6")

    def kind(said: str | None) -> str | None:  # #4270: which refusal -- both sides must have stopped at the same one
        return None if not said else "C20" if PERFORM_DEPTH in said else "X23" if "EIBCALEN" in said else "X6"

    return left[0], left[1], {"cobol": cobol, "java": java, "ok": bool(cobol and java) and kind(cobol) == kind(java),
                              "assumes": kind(cobol) or kind(java)}  # fmt: skip


def _fired(log: Path, encoding: str = "utf-8") -> list[str]:
    # #5859 userid_hex: the COBOL stub writes the USERID's raw bytes (latin-1); Java writes the same chars as UTF-8.
    # Split on "\n" only: str.splitlines also breaks at \x85, which an EBCDIC byte can be.
    return sorted(x for x in log.read_text(encoding=encoding).split("\n") if x.strip()) if log.is_file() else []


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
        cev, jev, x6 = x6_judged(sc, out, cev, jev)
        cev, jev = mask_absent_commarea(sc, cev, jev, [0])
        d = compare_events(cev, jev)
        o: dict[str, Any] = {"equal": d["equal"], "records": d["events"], "diffs": d["diffs"], "java": jev,
                             "entries": facade["entries"].get(name, []),
                             **({"not_compared": d["not_compared"]} if d.get("not_compared") else {})}  # fmt: skip
        ok = d["equal"] == d["events"]
        if x6:
            o["judged_to"], o["x6"] = judged_to(x6), x6
            ok &= x6["ok"]
        why = facade["refused"].get(name)
        if why:
            o["refused"] = why
            ok = False
        if sc.get("prefix_link"):
            area = _link_area(case, res, facade["events"].get(name, []), sc["prefix_link"])
            if area.get("equal") is False:
                o["link_area"] = area
                ok = False
        if sc.get("faults") or sc.get("sql_plan") or sc.get("dli_faults"):
            fired = {"cobol": _fired(cobol_work / "scenarios" / name / "out" / "faults.txt", "latin-1"),
                     "java": _fired(out / f"{name}.faults")}  # fmt: skip
            o["fired"] = fired
            ok &= bool(fired["cobol"]) and fired["cobol"] == fired["java"]
        if not sc.get("prefix_link") and not x6:
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
             cobol_only: bool = False, sql_faults: str = "auto", facades: bool = False,
             one_jvm: bool = False) -> int:  # fmt: skip
    """A CICS case end to end: facts -> stub files, the COBOL tasks, the Java tasks, the report.

    #4449: `facades` (with a port) runs the java-facade side too -- every scenario again, entered through the
    program's deployed entry point -- and the case is proven only when both sides are (report `facade`)."""
    import json

    import equivalence_cache

    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    ir = load_galaxy_ir(equivalence_cache.scan_db(corpus, work / "scan"))  # (once per corpus and engine)
    symbols = install_symbols(case.get("install_symbols"))  # #5089: stated, never guessed
    files = stub_files(ir, case["program_source"], case.get("datasets"), symbols)
    for extra in case.get("programs", []):  # the programs the task LINKs to use files of their own
        files += [f for f in stub_files(ir, extra["program_source"], case.get("datasets"), symbols)
                  if f["file"] not in {x["file"] for x in files}]  # fmt: skip
    case = equivalence_inputs.prepare_cics_case(case, corpus, files)  # #3804: generated files and scenarios
    # #4173: SQL faults -- `auto` adds a task per SQL statement the tasks executed (enumerated_sql_faults), each run
    # on both sides; `declared` runs only the scenarios' own sql_faults; `none` drops those too
    if sql_faults == "none":
        case = {**case, "scenarios": [{**sc, "sql_faults": []} for sc in case["scenarios"]]}
    with common.phase("cobol_cics"):  # #5882
        cobol = run_cobol_cics(case, corpus, work / "cobol", files)
    if case.get("db2") and sql_faults == "auto":
        derived = enumerated_sql_faults(case, work / "cobol")
        if derived:
            ran = frozenset(sc["name"] for sc in case["scenarios"])  # #5882: run once, in the first pass
            case = {**case, "scenarios": [*case["scenarios"], *derived]}
            with common.phase("cobol_cics_sql_faults"):  # only the derived fault tasks
                cobol = run_cobol_cics(case, corpus, work / "cobol", files, keep=ran)
    refused = json.loads((work / "cobol" / "refused.json").read_text(encoding="utf-8"))
    for name, why in refused.items():
        print(f"{case['program']} {name}: not run -- {why}")
    case = {**case, "scenarios": [sc for sc in case["scenarios"] if sc["name"] not in refused]}
    if cobol_only:
        for name, res in cobol.items():
            print(f"{name}: " + "; ".join(res["events"]))
        return 0
    try:
        facade: dict[str, Any] | None = {} if facades and port else None
        with common.phase("java_cics"):  # #5882: holds java_generate and java_maven
            java = run_java_cics(case, corpus, work / "java", work / "cobol", files, port, port_dir, facade, one_jvm)
    except RuntimeError as e:  # the port does not compile, or its run fails: the loop's feedback, not a crash
        common.write_java_failure(case, work, str(e))
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
        ran = cobol_events(res)
        cev = mask_clock_events(case, linked_result(case, ran), clock)
        jev = mask_clock_events(case, linked_result(case, java.get(name, [])), clock)
        sc = next(x for x in case["scenarios"] if x["name"] == name)
        if sc.get("prefix_link"):  # #4173: a fault task that LINKs to a program the case does not run -- both
            cev, jev = _to_link(cev, sc["prefix_link"]), _to_link(jev, sc["prefix_link"])  # sides judged up to it
        cev, jev, x6 = x6_judged(sc, work / "java" / "out", cev, jev)
        undefined = [0]  # COMMAREA fields a task with no COMMAREA copied from nowhere (X12)
        cev, jev = mask_absent_commarea(sc, cev, jev, undefined)
        d = compare_events(cev, jev)
        report["outputs"][name] = {"equal": d["equal"], "records": d["events"], "diffs": d["diffs"],
                                   "cobol": cev, "java": jev,
                                   **({"not_compared": d["not_compared"]} if d.get("not_compared") else {})}  # fmt: skip
        if executed_commands(ran):  # #5229: only when non-empty (python-test-traps.md)
            report["outputs"][name]["commands"] = executed_commands(ran)
        ok &= d["equal"] == d["events"]
        if case.get("sysout", True) and not (sc.get("prefix_link") or x6 or sc.get("prefix_x6")):
            # #4635: the task's DISPLAY output, as batch proofs compare SYSOUT (#4056); a task judged up to a point
            # it did not reach (a LINK not run, a refused WRITEQ) is not: its log stops where the oracle's does not
            s = compare_task_sysout(
                res.get("sysout", b""), work / "java" / "out" / f"{name}.sysout", common.data_encoding(case)
            )
            report["outputs"][name]["sysout"] = s
            if s["compared"] and s["differing"]:
                ok = False
                print(f"{case['program']} {name}: DISPLAY output differs on {s['differing']} line(s): {s['diffs'][:3]}")
        if sc.get("derived"):
            report["outputs"][name]["sql_faults"] = sc["sql_plan"]
        if res.get("x6_padded"):  # X6 (ASSUMED): the task ran on through a WRITEQ past FROM, padded on both sides
            report["outputs"][name]["x6_padded"] = res["x6_padded"]
        if x6:
            report["outputs"][name]["judged_to"], report["outputs"][name]["x6"] = judged_to(x6), x6
            if not x6["ok"]:
                ok = False
                print(f"{case['program']} {name}: only one side refused ({x6['assumes']}): {x6}")
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
        if sc.get("faults") or sc.get("sql_plan") or sc.get("dli_faults"):
            fired = {"cobol": _fired(work / "cobol" / "scenarios" / name / "out" / "faults.txt", "latin-1"),
                     "java": _fired(work / "java" / "out" / f"{name}.faults")}  # fmt: skip
            report["outputs"][name]["fired"] = fired
            if not fired["cobol"] or fired["cobol"] != fired["java"]:
                ok = False
                print(f"{case['program']} {name}: faults fired differ or none fired: {fired}")
        print(f"{case['program']} {name}: {d['equal']}/{d['events']} events equal")
        for x in d["diffs"][:6]:
            print(f"   event {x['event']}: {x.get('fields', [])[:3] or (x.get('cobol'), x.get('java'))}")
        end_state = not sc.get("prefix_link") and not x6
        changed = {} if not end_state else compare_files(case, corpus, files, res.get("files", {}),
                                                         work / "java" / "out", name)  # fmt: skip
        if end_state:
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
