#!/usr/bin/env python3
"""
Fresh-estate trials (#3803, #3805): the first-try proof rate on estates the system has never seen.

Per program: did the porting loop's FIRST attempt produce Java the equivalence harness proves identical
to the COBOL? The estates the tickets, generator and harness were fixed against (CardDemo, CBSA, ...) are
development data for good, and so is every estate once it has been through a trial -- a trial is a
one-shot measurement at a named, frozen system.

    python tests/tools/trial.py start <estate-id> --estate-path P --model M --backend B --work W
                                     [--ref R] [--repo-url U] [--kind public|private --label L]
                                     [--model-version V] [--exclude PROG=reason ...] [--shipped-data PROG ...]
    python tests/tools/trial.py preview <estate-id> --estate-path P --work W [--json F]   # rehearsal, no ledger
    python tests/tools/trial.py sync  <trial-id> --project W/java_h2     # (alias: attempt) import port_log.jsonl
    python tests/tools/trial.py record <trial-id> --summary run_summary.json --run B --fix PROG=cause:SHA --at ISO  # #8322
    python tests/tools/trial.py close <trial-id> [--cause PROG=cause ...] [--withdrawn REASON]
    python tests/tools/trial.py preview <estate-id> ... --page F         # also write the estate's page (#4493)
    python tests/tools/trial.py verify <trial-id> [--no-oracle]          # re-check the frozen system, read-only (#8322)
    python tests/tools/trial.py tickets <trial-id> --estate-path P --work W  # tickets at the frozen engine (#8322)
    python tests/tools/trial.py run <trial-id> --estate-path P --work W [--runs A,B]   # det port + proofs (#8322)
    python tests/tools/trial.py report [--write]                         # the page + the SVG chart + a page per estate
    python tests/tools/trial.py check                                    # ledger valid, report current (CI)

`start` refuses a development estate (every trialled estate is one), records the frozen system (engine
commit and version, the porting-rules hash, model + backend, the harness commit), runs the same scan ->
refract -> cobol-to-java path the equivalence harness builds its project with (target config h2), which
writes the porting tickets, and declares UP FRONT which programs are eligible and why every other one is
out of scope (out_of_scope_reason / ELIGIBILITY_RULES: CICS online and batch COBOL, prereg section 5; `--exclude` adds declared exclusions, at start only: the declaration is
hashed, so an exclusion added later to hide a failure fails validation).

Each program is then ported with the porting loop (gitgalaxy/tools/cobol_to_java/port_runner.py run /
prove). `sync` turns its log into attempts: one attempt per proof verdict (or per run that produced no
port), numbered from 1; stopped at the first proven one. An attempt that failed gets its CAUSE from what
happened next: a commit carrying a trailer `Trial-Cause: <ticket|generator|engine|harness> <PROGRAM>`
between the failure and the next attempt is a fix on our side (its cause, its commit); a retry with no
such commit is the model's. `close` ends the trial: a program still not proven gets its cause declared.
`close --withdrawn REASON` ends a trial whose proof phase never ran: every eligible program with no attempt
becomes `withdrawn` and is left OUT of the first-try denominator, so an unrun trial reports "not measured"
instead of publishing a 0% rate against the frozen engine. A program that does carry attempts still declares
its cause as usual, because its attempts are real measurements.

Sources: tests/cobol_mainframe/trials.json (the ledger, committed). Writes
docs/language_status/fresh_estate_trials.md and fresh_estate_trials.svg (a plain SVG, no plotting library), and
(#4493) docs/language_status/trials/<estate>.md: the equivalence harness's self-report for that trial -- coverage,
run status per program, out-of-scope reasons and blockers phrased as fixes -- built from the ledger alone. A
rehearsal (`preview --page --case PROG=CASE`) adds input generation, tests and measured coverage from the cases, and
(`--proof-blockers FILE`) the programs the translator refused or left holes in (unresolved links, missing stubs).
`start`, `sync` and `close` regenerate all of these when they save the committed ledger.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

LEDGER = REPO_ROOT / "tests" / "cobol_mainframe" / "trials.json"
PAGE = REPO_ROOT / "docs" / "language_status" / "fresh_estate_trials.md"
CHART = REPO_ROOT / "docs" / "language_status" / "fresh_estate_trials.svg"
PAGES = REPO_ROOT / "docs" / "language_status" / "trials"  # #4493: one harness-style page per trialled estate

KINDS = ("public", "private")
STATUSES = ("fresh", "development")
OUTCOMES = ("proven", "failed", "no-port", "error")
OUR_CAUSES = ("ticket", "generator", "engine", "harness")  # a fix on our side, with its commit
CAUSES = ("model", *OUR_CAUSES)
ORACLE = ("compiled", "compile-failed", "unknown")  # #8325: did cobc compile the reference (Amendment 4)
BINS = ("@1", "@2", "@3", "@4+")
# The frozen system's harness: the files the proof runs through (tests/tools/equivalence*.py and its image).
HARNESS_PATHS = ("tests/tools/equivalence.py", "tests/tools/equivalence_common.py", "tests/tools/equivalence_java.py",
                 "tests/tools/equivalence_inputs.py", "tests/tools/equivalence_cics.py",
                 "tests/tools/equivalence_cics_compare.py",  # #5274: the CICS harness's event comparison
                 "tests/tools/equivalence_cics_containers.py",  # #5274: the CICS harness's containers family
                 "tests/tools/equivalence_cics_conditions.py",  # #5274: ... and its conditions family
                 "tests/tools/equivalence_cics_faults.py",  # #5274: ... and its faults family
                 "tests/tools/equivalence_cics_filecontrol.py",  # #5274: ... and its file control family
                 "tests/tools/equivalence_cics_tempstorage.py",  # #5274: ... and its temporary storage family
                 "tests/tools/equivalence_cics_taskcontrol.py",  # #5274: ... and its task / interval control family
                 "tests/tools/equivalence_cics_counters.py",  # #5274: ... and its named counter family
                 "tests/tools/equivalence_cics_program.py",  # #5274: ... and its program control family
                 "tests/tools/equivalence_cics_storage.py",  # #5274: ... and its storage family
                 "tests/tools/equivalence_cics_system.py",  # #5274: ... and its system services family
                 "tests/tools/equivalence_cics_tdqueue.py",  # #5274: ... and its transient data family
                 "tests/tools/equivalence_cics_terminal.py",  # #5274: ... and its terminal family
                 "tests/tools/equivalence_cics_web.py",  # #5274: ... and its web family
                 "tests/tools/equivalence_cics_pointer.py",  # #5274: ... and its POINTER view family
                 "tests/tools/cobol_coverage.py",  # #4023: every COBOL run is traced through it
                 "tests/tools/equivalence_call.py",  # CALL cases
                 # #8119: the resource legs a CICS, Db2, IMS or MQ proof runs through, and the shared runners
                 "tests/tools/equivalence_db2.py", "tests/tools/equivalence_sql.py", "tests/tools/equivalence_ims.py",
                 "tests/tools/equivalence_mq.py", "tests/tools/equivalence_mvs.py",
                 "tests/tools/equivalence_binary64.py", "tests/tools/equivalence_job.py",
                 "tests/tools/equivalence_oracle.py", "tests/tools/equivalence_env.py",
                 # the C stubs each leg links: fault runs, CEE3ABD, DISPLAY (#4056), LE services, CICS, Db2, DL/I, MQI
                 "tests/equivalence/faults", "tests/equivalence/le", "tests/equivalence/cics",
                 "tests/equivalence/db2", "tests/equivalence/ims", "tests/equivalence/mq",
                 "tests/equivalence/gnucobol.Dockerfile")  # fmt: skip
# tests/tools/equivalence*.py modules no proof runs through (fnmatch patterns): the e2e planners and case selection,
# and the result cache. A pattern, not the names: change_classifier reads a module name as a ground-truth reach.
NOT_HARNESS = ("tests/tools/equivalence_e2e_*.py", "tests/tools/equivalence_cache.py")
# `Trial-Cause: generator CBACT04C` -- bounded, one trailer per line
_TRAILER = re.compile(r"^Trial-Cause:[ \t]{0,8}([a-z]{1,12})[ \t]{1,8}([A-Za-z0-9$#@_-]{1,64})[ \t]{0,8}$", re.M)
_FINAL = re.compile(
    r"^(proven@[1-9][0-9]{0,3}(\((?:[a-z]{1,12},){0,63}[a-z]{1,12}\))?|not-proven\([a-z]{1,12}\)|withdrawn|open)$"
)


# ---- git: the frozen system and the fix commits ----------------------------------------
def git(repo: Path, *args: str) -> str:
    argv = ["git", "-C", str(repo), *args]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603, S607
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def porting_rules_hash() -> tuple[str, int]:
    """(sha256 of the PORTING_RULES text + the ticket version, the ticket version): what the model was told."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES, TICKET_VERSION

    text = json.dumps({"rules": list(PORTING_RULES), "version": TICKET_VERSION}, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), TICKET_VERSION


def frozen_system(repo: Path, model: str, backend: str, model_version: str | None) -> dict[str, Any]:
    """The system a trial runs under. It must be a commit: an uncommitted engine or tool is not a named version."""
    dirty = git(repo, "status", "--porcelain", "--", *[p for p in ("gitgalaxy", "tests/tools") if (repo / p).exists()])
    if dirty:
        raise SystemExit(f"the engine has uncommitted changes -- a trial runs on a commit:\n{dirty}")
    rules_hash, ticket_version = porting_rules_hash()
    harness = git(repo, "log", "-1", "--format=%H", "--", *HARNESS_PATHS) or git(repo, "rev-parse", "HEAD")
    return {
        "engine_commit": git(repo, "rev-parse", "HEAD"),
        "engine_version": _engine_version(repo),
        "porting_rules_hash": rules_hash,
        "ticket_version": ticket_version,
        "model": model,
        "model_version": model_version or model,
        "backend": backend,
        "harness_commit": harness,
    }


def _engine_version(repo: Path) -> str:
    """The release the engine commit sits on (its last tag): the chart's facet. Untagged: the short commit."""
    argv = ["git", "-C", str(repo), "describe", "--tags", "--abbrev=0"]
    proc = subprocess.run(argv, capture_output=True, text=True,  # noqa: S603, S607
                          check=False)  # fmt: skip
    return (
        proc.stdout.strip()
        if proc.returncode == 0 and proc.stdout.strip()
        else git(repo, "rev-parse", "--short=12", "HEAD")
    )


def fix_commits(repo: Path, since: str) -> list[dict[str, Any]]:
    """Every commit after `since` carrying a Trial-Cause trailer: [{sha, at, cause, program}], oldest first."""
    out = git(repo, "log", "--reverse", "--format=%H%x1f%cI%x1f%B%x1e", f"{since}..HEAD")
    fixes = []
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        sha, at, body = rec.strip().split("\x1f", 2)
        for cause, program in _TRAILER.findall(body):
            if cause not in OUR_CAUSES:
                raise SystemExit(f"{sha[:10]}: Trial-Cause {cause!r} is not one of {OUR_CAUSES}")
            fixes.append({"sha": sha, "at": _ts(at), "cause": cause, "program": program})
    return fixes


def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).date().isoformat()


def _ts(text: str) -> _dt.datetime:
    # git and GitHub write UTC as a trailing Z, which fromisoformat accepts only from Python 3.11
    return _dt.datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)


# ---- eligibility: declared in code, applied at start ------------------------------------
def _text_of(estate: Path, files: list[str]) -> str:
    from gitgalaxy.core.source_text import read_source

    return "\n".join(read_source(estate / f).text for f in files if f and (estate / f).is_file())


# #8119: a resource call is an output channel: the CICS leg compares the task's events, the Db2 leg the SQL calls and
# tables, the IMS leg the DL/I calls, the MQ leg the MQI calls (equivalence_cics / _db2 / _ims / _mq).
_RESOURCE_CALL = re.compile(
    r"\bEXEC[ \t\n]{1,20}(?:CICS|SQL|DLI)\b|\bCALL[ \t\n]{1,20}['\"](?:CBLTDLI|AIBTDLI|MQ[A-Z]{2,8})['\"]", re.I
)
_WRITES = {"OUTPUT", "EXTEND", "I-O"}


def _sections(skeleton: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return (skeleton.get("sections", {}).get(name) or {}).get("facts") or []


def out_of_scope_reason(skeleton: dict[str, Any], text: str, shipped: bool, members: set[str] | None = None
                        ) -> str | None:  # fmt: skip
    """Why the equivalence harness cannot run a program (None: eligible). The harness runs a COBOL program under
    GnuCOBOL, batch with a driver or online as a CICS task (the CICS leg), with the Db2, IMS and MQ legs behind
    EXEC SQL, DL/I and MQI calls (pre-registration section 5: CICS online and batch COBOL, #8119). It loads the
    input files (generated from their copybook layouts, #3804, or shipped) and compares every output: files record
    by record, SYSOUT (#4056), RETURN-CODE, the abend (CEE3ABD) and the CICS / SQL / DL/I / MQI calls. So the
    program must be COBOL, have its whole source in the estate (`members`: every COPY / EXEC SQL INCLUDE member is
    an estate file or one the translator ships), have an output channel, and a record layout for every input
    file (a COPY in its FD, or an inline 01 record)."""
    if _not_cobol(skeleton, text, shipped):
        return ELIGIBILITY_RULES[0][1]
    missing = _missing_member(text, members) if members is not None else None
    if missing:
        return f"source missing from the repo: COPY member {missing} is not in the estate"
    for rule, reason in ELIGIBILITY_RULES[1:]:
        if rule(skeleton, text, shipped):
            return reason
    return None


def shipped_members() -> set[str]:
    """The members the translator ships (det/copy): the system members and the register stand-ins (#5649)."""
    from gitgalaxy.core.copy_libraries import SYSTEM_MEMBERS, stand_in_registers

    return {*SYSTEM_MEMBERS, *stand_in_registers()}


_MAPSET = re.compile(r"^([A-Z0-9@#$][A-Z0-9@#$_-]{0,7})[ \t]{1,20}DFHMSD\b", re.I | re.M)


def estate_members(estate: Path) -> set[str]:
    """Every member name a COPY can reach in the estate: each file's stem (any extension, any case) and each BMS
    mapset's label (its symbolic map), plus the members the translator ships."""
    from gitgalaxy.core.source_text import read_source

    names = set(shipped_members())
    for f in estate.rglob("*"):
        if ".git" in f.relative_to(estate).parts or not f.is_file():
            continue
        names.add(f.name.split(".", 1)[0].upper())
        if f.suffix.lower() == ".bms":
            names |= {m.upper() for m in _MAPSET.findall(read_source(f).text)}
    return names


def _code(text: str) -> str:
    """`text` without fixed-format comment lines and trailing `*>` comments."""
    lines = (ln for ln in text.splitlines() if ln[6:7] not in ("*", "/") and not ln.lstrip().startswith("*>"))
    return "\n".join(ln.split("*>", 1)[0] for ln in lines)


def _missing_member(text: str, members: set[str]) -> str | None:
    """The first COPY / EXEC SQL INCLUDE member of `text` (the program and the copybooks the scan found) that is
    not in `members`, or None. A COPY inside a comment is not one."""
    from gitgalaxy.core.cobol_preprocessor import COPY_OR_INCLUDE_HEAD

    names = sorted({m.group(1).upper() for m in COPY_OR_INCLUDE_HEAD.finditer(_code(text))} - members)
    return names[0] if names else None


def _not_cobol(sk: dict[str, Any], _t: str, _s: bool) -> bool:
    return (sk.get("program", {}).get("language") or "").lower() != "cobol"


_PROCEDURE = re.compile(r"\bPROCEDURE[ \t\n]{1,20}DIVISION\b", re.I)
_DISPLAY_STMT = re.compile(r"(?<![\w-])DISPLAY(?![\w-])", re.I)


def _procedure_body(text: str) -> str:
    """The PROCEDURE DIVISION's code: fixed-format comment lines and trailing `*>` comments removed."""
    body = _code(text)
    m = _PROCEDURE.search(body)
    return body[m.end() :] if m else ""


_RETURN_CODE_SET = re.compile(r"(?<![\w-])(?:TO|GIVING|COMPUTE)[ \t\n]{1,20}RETURN-CODE(?![\w-])", re.I)


def _displays(text: str) -> bool:
    """Whether the PROCEDURE DIVISION holds a DISPLAY statement (SYSOUT is a proved channel, #4056). The data
    division's USAGE DISPLAY clause, comment lines and DISPLAY-... names are not statements."""
    return bool(_DISPLAY_STMT.search(_procedure_body(text)))


def _sets_return_code(text: str) -> bool:
    """Whether the PROCEDURE DIVISION sets RETURN-CODE (MOVE/ADD ... TO, COMPUTE, ... GIVING): the harness
    compares the step's RETURN-CODE as an output (equivalence.py), so a program whose result is its return code
    has a channel. A bare read of RETURN-CODE, a comment or a string-free name like DISPLAY-RETURN-CODE is not."""
    return bool(_RETURN_CODE_SET.search(_procedure_body(text)))


_ABEND_CALL = re.compile(r"(?<![\w-])CALL[ \t\n]{1,20}['\"]CEE3ABD['\"]", re.I)


def _abends(text: str) -> bool:
    """Whether the PROCEDURE DIVISION CALLs the CEE3ABD abend stub: the harness records the abend (ABEND Unnnn)
    and a proof needs the same abend on both sides (equivalence.py), so it is an output channel. A comment, a
    data-division mention, a variable CALL target or another abend routine (no stub) is not."""
    return bool(_ABEND_CALL.search(_procedure_body(text)))


def _resource_calls(text: str) -> bool:
    """Whether the PROCEDURE DIVISION holds an EXEC CICS, EXEC SQL or EXEC DLI block, or CALLs DL/I (CBLTDLI,
    AIBTDLI) or an MQI verb (#8119): each leg compares those calls, so they are an output channel. One in a comment
    or the data division is not."""
    return bool(_RESOURCE_CALL.search(_procedure_body(text)))


def _no_output(sk: dict[str, Any], t: str, _s: bool) -> bool:
    if any(_WRITES & set(d.get("modes") or []) for d in _sections(sk, "datasets")):
        return False
    return not (_displays(t) or _sets_return_code(t) or _abends(t) or _resource_calls(t))


_FD_ENTRY = re.compile(r"(?<![\w-])FD[ \t\n]{1,20}([A-Z0-9][A-Z0-9-]*)", re.I)
_FD_END = re.compile(
    r"(?<![\w-])(?:[FS]D[ \t\n]|WORKING-STORAGE|LOCAL-STORAGE|LINKAGE[ \t\n]{1,20}SECTION|PROCEDURE[ \t\n]{1,20}DIVISION)",
    re.I,
)
_RECORD_01 = re.compile(r"(?<![\w-])01[ \t\n]{1,20}[A-Z0-9]", re.I)
_PIC = re.compile(r"(?<![\w-])PIC(?:TURE)?(?![\w-])", re.I)


def _fd_inline_records(text: str) -> set[str]:
    """Names of the files whose FD describes its record in the program itself: an 01 with at least one PICTURE
    item (equivalence_common.layout_fields reads such a layout from the program source, #3804). Comment lines
    are ignored; an FD with no 01, or no PICTURE, is not a layout."""
    code = _code(text)
    out = set()
    for m in _FD_ENTRY.finditer(code):
        end = _FD_END.search(code, m.end())
        region = code[m.end() : end.start() if end else len(code)]
        if _RECORD_01.search(region) and _PIC.search(region):
            out.add(m.group(1).upper())
    return out


def _input_without_layout(sk: dict[str, Any], t: str, shipped: bool) -> bool:
    if shipped:
        return False
    reads = {d.get("internal_name") for d in _sections(sk, "datasets") if {"INPUT", "I-O"} & set(d.get("modes") or [])}
    inline = _fd_inline_records(t)
    return any(
        fc.get("select_name") in reads and not fc.get("fd_copies") and str(fc.get("select_name")).upper() not in inline
        for fc in _sections(sk, "file_control")
    )


ELIGIBILITY_RULES = (
    (_not_cobol, "not COBOL: the harness compiles the program with GnuCOBOL"),
    # (#8119: the source-missing rule runs second, in out_of_scope_reason: it needs the estate's members)
    (
        _no_output,
        "writes no file, DISPLAYs nothing, sets no RETURN-CODE, does not abend and makes no CICS, SQL, DL/I or MQ "
        "call: the harness has no output to compare",
    ),
    (
        _input_without_layout,
        "an input file whose FD holds no record layout (neither a COPY nor an inline 01 with PICTURE items): its records cannot be generated (#3804)",
    ),
)


def declaration_hash(eligible: list[str], out_of_scope: dict[str, str]) -> str:
    """The up-front declaration's fingerprint: any later change to either list fails validation."""
    text = json.dumps({"eligible": sorted(eligible), "out_of_scope": out_of_scope}, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def declare(clean: Path, project: Path, estate: Path, excludes: dict[str, str], shipped: set[str]
            ) -> tuple[list[str], dict[str, str]]:  # fmt: skip
    """(eligible programs, {program: out-of-scope reason}) for every program the scan found."""
    tickets = {p.name[: -len("_port_ticket.json")] for p in (project / "ai_agent_jobs").glob("*_port_ticket.json")}
    skeletons = {p.name[: -len("_skeleton.json")]: p for p in (clean / "06_skeleton").glob("*_skeleton.json")}
    unknown = sorted(set(excludes) - set(skeletons) - tickets)
    if unknown:
        raise SystemExit(f"--exclude names programs the scan did not find: {unknown}")
    eligible, out = [], {}
    members = estate_members(estate)
    for key in sorted(set(skeletons) | tickets):
        if key in excludes:
            out[key] = f"declared: {excludes[key]}"
            continue
        if key not in tickets:
            out[key] = "no porting ticket: no business logic to port"
            continue
        sk = json.loads(skeletons[key].read_text(encoding="utf-8")) if key in skeletons else {}
        prog = sk.get("program", {})
        reason = out_of_scope_reason(
            sk, _text_of(estate, [prog.get("file"), *prog.get("copybooks", [])]), key in shipped, members
        )
        if reason:
            out[key] = reason
        else:
            eligible.append(key)
    return eligible, out


# ---- the ledger ------------------------------------------------------------------------
def load(path: Path = LEDGER) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(ledger: dict[str, Any], path: Path = LEDGER) -> None:
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _estate(ledger: dict[str, Any], estate_id: str) -> dict[str, Any] | None:
    return next((e for e in ledger["estates"] if e["id"] == estate_id), None)


def _trial(ledger: dict[str, Any], trial_id: str) -> dict[str, Any]:
    t = next((t for t in ledger["trials"] if t["id"] == trial_id), None)
    if t is None:
        raise SystemExit(f"no trial {trial_id}")
    return t


def final_of(attempts: list[dict[str, Any]], closed_cause: str | None = None) -> str:
    """proven@N (with the causes of the failures before it) | not-proven(cause) | open."""
    for a in attempts:
        if a["outcome"] == "proven":
            causes = [str(b["cause"] or "oracle") for b in attempts[: a["n"] - 1]]  # #8325: no cause = oracle
            return f"proven@{a['n']}" + (f"({','.join(causes)})" if causes else "")
    return f"not-proven({closed_cause})" if closed_cause else "open"


def validate(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not ledger.get("about"):
        errors.append("the ledger needs its `about`")
    ids = [e.get("id") for e in ledger.get("estates", [])]
    if len(ids) != len(set(ids)):
        errors.append("duplicate estate ids")
    for e in ledger.get("estates", []):
        where = e.get("id", "?")
        if e.get("kind") not in KINDS:
            errors.append(f"{where}: kind must be one of {KINDS}")
        if e.get("status") not in STATUSES:
            errors.append(f"{where}: status must be one of {STATUSES}")
        if e.get("kind") == "public" and not (e.get("repo") and e.get("ref")):
            errors.append(f"{where}: a public estate records its repo and ref")
        if e.get("kind") == "private" and (any(k in e for k in ("repo", "ref", "path")) or not e.get("label")):
            errors.append(f"{where}: a private estate carries an anonymised label only (no repo / ref / path)")
    trial_ids = [t.get("id") for t in ledger.get("trials", [])]
    if len(trial_ids) != len(set(trial_ids)):
        errors.append("duplicate trial ids")
    for t in ledger.get("trials", []):
        errors += [f"{t.get('id', '?')}: {m}" for m in _validate_trial(ledger, t)]
    return errors


_SYSTEM_KEYS = ("engine_commit", "engine_version", "porting_rules_hash", "ticket_version", "model", "model_version",
                "backend", "harness_commit")  # fmt: skip


def _validate_trial(ledger: dict[str, Any], t: dict[str, Any]) -> list[str]:
    errors = _validate_harness(t)
    estate = _estate(ledger, t.get("estate", ""))
    if estate is None:
        errors.append(f"unknown estate {t.get('estate')}")
    elif estate["status"] != "development":
        errors.append("a trialled estate is development for good")
    missing = [k for k in _SYSTEM_KEYS if t.get("system", {}).get(k) in (None, "")]
    if missing:
        errors.append(f"the frozen system is missing {missing}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(t.get("started"))):
        errors.append("started is a date YYYY-MM-DD")
    if "withdrawn" in t and not (isinstance(t.get("withdrawn"), str) and t["withdrawn"].strip()):
        errors.append("withdrawn is the one-line reason the trial's proof phase never ran")
    if t.get("withdrawn") and not t.get("closed"):
        errors.append("a withdrawn trial is closed")
    eligible, out = t.get("eligible", []), t.get("out_of_scope", {})
    if eligible != sorted(set(eligible)):
        errors.append("eligible is a sorted list of distinct programs")
    if set(eligible) & set(out):
        errors.append(f"eligible and out of scope at once: {sorted(set(eligible) & set(out))}")
    if any(not r for r in out.values()):
        errors.append("every out-of-scope program needs its reason")
    if t.get("declared") != declaration_hash(eligible, out):
        errors.append("eligibility changed after start: programs are declared eligible or out of scope UP FRONT "
                      "(trial start --exclude), never later")  # fmt: skip
    programs = t.get("programs", {})
    if set(programs) != set(eligible):
        errors.append("`programs` must hold exactly the eligible programs")
    for key, p in programs.items():
        attempts = p.get("attempts", [])
        if [a.get("n") for a in attempts] != list(range(1, len(attempts) + 1)):
            errors.append(f"{key}: attempts are numbered 1, 2, 3 ...")
        for a in attempts:
            if a.get("outcome") not in OUTCOMES:
                errors.append(f"{key} attempt {a.get('n')}: outcome must be one of {OUTCOMES}")
            if a.get("oracle") is not None and a.get("oracle") not in ORACLE:
                errors.append(f"{key} attempt {a.get('n')}: oracle must be one of {ORACLE}")
            if a.get("cause") is not None and a.get("cause") not in CAUSES:
                errors.append(f"{key} attempt {a.get('n')}: cause must be one of {CAUSES} or null")
            if a.get("outcome") == "proven" and a.get("cause") is not None:
                errors.append(f"{key} attempt {a.get('n')}: a proven attempt has no failure cause")
            if bool(a.get("fix_commit")) != (a.get("cause") in OUR_CAUSES):
                errors.append(f"{key} attempt {a.get('n')}: a fix commit goes with a cause on our side, and only there")
        if any(a["outcome"] == "proven" for a in attempts[:-1]):
            errors.append(f"{key}: attempts stop at the first proven one")
        if any(a.get("cause") is None and a.get("oracle") != "compile-failed" for a in attempts[:-1]):
            errors.append(f"{key}: every failed attempt before the last carries its cause")
        final = str(p.get("final"))
        if not _FINAL.match(final):
            errors.append(f"{key}: final must be proven@N | not-proven(cause) | withdrawn | open")
        elif final.startswith("not-proven"):
            if final[len("not-proven(") : -1] not in CAUSES or not t.get("closed"):
                errors.append(f"{key}: not-proven(cause) needs a known cause and a closed trial")
        elif final == "withdrawn":
            if not t.get("withdrawn") or not t.get("closed"):
                errors.append(f"{key}: withdrawn needs a withdrawn, closed trial (close --withdrawn REASON)")
            if attempts:
                errors.append(f"{key}: withdrawn is only for a program with no attempt; declare its cause instead")
        elif final != final_of(attempts):
            errors.append(f"{key}: final {final} does not follow from its attempts ({final_of(attempts)})")
        if t.get("closed") and final == "open":
            errors.append(f"{key}: a closed trial leaves no program open")
    return errors


# ---- start -----------------------------------------------------------------------------
def _parse_pairs(items: list[str] | None, what: str) -> dict[str, str]:
    out = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise SystemExit(f"{what} takes PROGRAM=value, not {item!r}")
        out[key.strip()] = value.strip()
    return out


def _estate_git(path: Path, *args: str) -> str | None:
    argv = ["git", "-C", str(path), *args]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603, S607
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def scan_and_declare(
    path: Path, work: Path, excludes: dict[str, str], shipped: set[str]
) -> tuple[Path, list[str], dict[str, str]]:
    """Scan, refract and convert an estate (the harness's path, target h2), then declare eligibility.

    Returns (the generated project, eligible programs, {program: out-of-scope reason})."""
    import java_target_matrix as jtm  # the path the equivalence harness builds its project with

    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    clean = jtm.refactor(path, work, scan=True)
    project = jtm.generate(clean, "h2", jtm.MATRIX["h2"], work)
    eligible, out = declare(clean, project, path, excludes, shipped)
    return project, eligible, out


def cmd_preview(opts: argparse.Namespace) -> int:
    """A rehearsal of the declaration step: reads nothing from, and writes nothing to, the ledger.

    Any estate is accepted (a development estate included): nothing here counts as first-try, and the
    estate's status does not change. Prints the up-front declaration a `start` would record."""
    excludes = _parse_pairs(opts.exclude, "--exclude")
    _project, eligible, out = scan_and_declare(
        opts.estate_path.resolve(), opts.work, excludes, set(opts.shipped_data or [])
    )
    reasons: dict[str, int] = {}
    for why in out.values():
        reasons[why] = reasons.get(why, 0) + 1
    print(f"preview of {opts.estate} (rehearsal: no ledger entry, never first-try)")
    print(f"  eligible: {len(eligible)}  out of scope: {len(out)}  programs: {len(eligible) + len(out)}")
    for why, n in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  out of scope x{n}: {why}")
    if opts.page:
        rehearsal = {"estate": opts.estate, "eligible": eligible, "out_of_scope": out,
                     "programs": {k: {"attempts": [], "final": "open"} for k in eligible}}  # fmt: skip
        roots: list[Path] = []
        try:  # the burned corpora, when they are on this box: the record layouts are read from them
            import cics_census as cc

            roots = [cc.mainframe_root(None)]
        except (SystemExit, OSError):
            roots = []
        facts = case_facts(_parse_pairs(opts.case, "--case"), opts.cases_dir, roots)
        untranslated: list[dict[str, Any]] = []
        if opts.proof_blockers:
            import harness_report as hr

            res = json.loads(opts.proof_blockers.read_text(encoding="utf-8"))
            untranslated = hr.untranslated_blockers(res)
        opts.page.write_text(
            trial_page(
                {"estates": [], "trials": []}, rehearsal, rehearsal=True, facts=facts, untranslated=untranslated
            ),
            encoding="utf-8",
        )
    if opts.json:
        opts.json.write_text(
            json.dumps({"estate": opts.estate, "eligible": eligible, "out_of_scope": out}, indent=1, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    return 0


def cmd_start(opts: argparse.Namespace) -> int:
    ledger = load(opts.ledger)
    estate = _estate(ledger, opts.estate)
    if estate is not None and estate["status"] == "development":
        why = f"trialled in {estate['trialled_by']}" if estate.get("trialled_by") else "development data"
        raise SystemExit(f"{opts.estate} is a development estate ({why}): its programs never count as first-try")
    path = opts.estate_path.resolve()
    if estate is None:
        kind = opts.kind
        estate = {"id": opts.estate, "kind": kind, "status": "fresh"}
        if kind == "public":
            estate["repo"] = opts.repo_url or _estate_git(path, "remote", "get-url", "origin")
            estate["ref"] = opts.ref or _estate_git(path, "rev-parse", "HEAD")
            if not (estate["repo"] and estate["ref"]):
                raise SystemExit("a public estate needs --repo-url and --ref (not a git checkout)")
        else:
            if not opts.label:
                raise SystemExit("a private estate needs --label (an anonymised name; nothing else is recorded)")
            estate["label"] = opts.label
        ledger["estates"].append(estate)
    elif opts.ref and estate.get("ref") and opts.ref != estate["ref"]:
        raise SystemExit(f"{opts.estate} is recorded at ref {estate['ref']}, not {opts.ref}")
    excludes = _parse_pairs(opts.exclude, "--exclude")
    system = frozen_system(opts.repo, opts.model, opts.backend, opts.model_version)

    project, eligible, out = scan_and_declare(path, opts.work, excludes, set(opts.shipped_data or []))
    trial_id = f"trial-{len(ledger['trials']) + 1:03d}"
    ledger["trials"].append({
        "id": trial_id,
        "estate": opts.estate,
        "started": _today(),
        "closed": None,
        "system": system,
        "eligible": eligible,
        "out_of_scope": out,
        "declared": declaration_hash(eligible, out),
        "programs": {k: {"attempts": [], "final": "open"} for k in eligible},
    })  # fmt: skip
    # #3803: the estate joins the development set for good -- the moment it is seen, not when it is proven
    estate["status"] = "development"
    estate["trialled_by"] = trial_id
    problems = validate(ledger)
    if problems:
        raise SystemExit("the trial would leave the ledger invalid:\n  " + "\n  ".join(problems))
    save(ledger, opts.ledger)
    refresh_outputs(ledger, opts.ledger)
    print(f"{trial_id}: {opts.estate} at engine {system['engine_version']} ({system['engine_commit'][:10]}), "
          f"{len(eligible)} eligible, {len(out)} out of scope; tickets in {project / 'ai_agent_jobs'}")  # fmt: skip
    print(f"  eligible: {', '.join(eligible) or '(none)'}")
    print(f"  per program: python -m gitgalaxy.tools.cobol_to_java.port_runner run {project} --ticket PROG "
          f"--backend {opts.backend} --model {opts.model} ...; then `port_runner prove` (the equivalence harness); "
          f"then python tests/tools/trial.py sync {trial_id} --project {project}")  # fmt: skip
    return 0


def refresh_outputs(ledger: dict[str, Any], ledger_path: Path) -> int:
    """#4493: regenerate the trials page, its chart and every estate page after the committed ledger changes, so the
    page is part of start / sync / close and `check` never fails on a forgotten `report --write`. Another ledger
    (a rehearsal, a test) writes nothing into the repo's docs. Returns the number of estate pages written."""
    if ledger_path.resolve() != LEDGER.resolve():
        return 0
    PAGE.write_text(render(ledger), encoding="utf-8")
    CHART.write_text(render_svg(ledger), encoding="utf-8")
    return len(write_pages(ledger))


# ---- sync: the porting loop's log -> attempts ----------------------------------------------
def attempts_from_log(events: list[dict[str, Any]], key: str, fixes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One attempt per proof verdict (or per run that produced no port), in log order, stopped at the first
    proven. A proposed port superseded by another run before any proof is an `error` attempt (never proved).
    A failed attempt's cause: the last Trial-Cause commit for this program between its verdict and the next
    attempt's start (ours, with the commit), else `model` when another attempt followed, else still null."""
    raw: list[dict[str, Any]] = []  # {outcome, began, at, model}
    pending: dict[str, Any] | None = None
    for e in events:
        if e.get("ticket") != key:
            continue
        ev, at = e.get("event"), e.get("at")
        if ev in ("proposed", "no-port"):
            if pending is not None:  # proposed, never proved, and run again
                raw.append({**pending, "outcome": "error", "at": pending["began"]})
            began = e.get("started") or at
            pending = None
            if ev == "no-port":
                raw.append({"outcome": "error" if e.get("error") else "no-port", "began": began, "at": at,
                            "model": e.get("model")})  # fmt: skip
            else:
                pending = {"began": began, "model": e.get("model")}
        elif ev in ("proven", "proof-failed"):
            base = pending or (raw[-1] if raw else {"began": at, "model": None})
            raw.append({"outcome": "proven" if ev == "proven" else "failed", "began": base["began"] if pending else at,
                        "at": at, "model": base.get("model"),
                        **({"oracle": e["oracle"]} if e.get("oracle") else {})})  # fmt: skip
            pending = None
        if raw and raw[-1]["outcome"] == "proven":
            break
    out = []
    for i, r in enumerate(raw):
        cause, commit = None, None
        if r["outcome"] != "proven":
            end = _ts(raw[i + 1]["began"]) if i + 1 < len(raw) else None
            mine = [
                f for f in fixes if f["program"] == key and _ts(r["at"]) <= f["at"] and (end is None or f["at"] <= end)
            ]
            if mine:
                cause, commit = mine[-1]["cause"], mine[-1]["sha"]
            elif i + 1 < len(raw) and r.get("oracle") != "compile-failed":
                cause = "model"  # an oracle that did not compile is nobody's model failure (#8325)
        out.append({"n": i + 1, "outcome": r["outcome"], "cause": cause, "fix_commit": commit, "at": r["at"],
                    "model": r["model"], **({"oracle": r["oracle"]} if r.get("oracle") else {})})  # fmt: skip
    return out


def sync(trial: dict[str, Any], events: list[dict[str, Any]], fixes: list[dict[str, Any]]) -> dict[str, int]:
    """Import the log into the trial (idempotent). Attempts already recorded never change -- only a null
    cause may be filled in once the next attempt or a fix arrives. {program: attempts} of what changed."""
    if trial.get("closed"):
        raise SystemExit(f"{trial['id']} is closed")
    changed = {}
    for key, p in trial["programs"].items():
        new = attempts_from_log(events, key, fixes)
        for old, now in zip(p["attempts"], new, strict=False):  # reason: length may differ
            same = all(old[k] == now[k] for k in ("n", "outcome", "at"))
            if not same or (
                old["cause"] is not None and (old["cause"], old["fix_commit"]) != (now["cause"], now["fix_commit"])
            ):
                raise SystemExit(f"{trial['id']} {key}: the log no longer gives recorded attempt {old['n']} -- "
                                 "a recorded attempt is never rewritten")  # fmt: skip
        if len(new) < len(p["attempts"]):
            raise SystemExit(f"{trial['id']} {key}: the log has fewer attempts than the ledger (another project?)")
        if new != p["attempts"]:
            changed[key] = len(new)
        p["attempts"], p["final"] = new, final_of(new)
    stray = sorted({e.get("ticket") for e in events} - set(trial["programs"]) - {None})
    if stray:
        print(f"note: the log has attempts for programs outside the trial's eligible set: {stray}")
    return changed


def attach_harness(trial: dict[str, Any], cases: dict[str, str], proof_blockers: Path | None) -> None:
    """#4493: record the cases and the untranslated-program blockers the trial's page reports, so the committed page
    carries what a rehearsal page does. Names and case references only (no estate code). The `harness` key is added
    only when non-empty; a later call replaces what it names."""
    if not cases and not proof_blockers:
        return
    block = dict(trial.get("harness", {}))
    if cases:
        block["cases"] = {**block.get("cases", {}), **cases}
    if proof_blockers:
        import harness_report as hr

        res = json.loads(proof_blockers.read_text(encoding="utf-8"))
        if untranslated := hr.untranslated_blockers(res):
            block["untranslated"] = untranslated
        else:
            block.pop("untranslated", None)
    if block:
        trial["harness"] = block
    else:
        trial.pop("harness", None)


def _validate_harness(t: dict[str, Any]) -> list[str]:
    block = t.get("harness")
    if block is None:
        return []
    if not isinstance(block, dict) or not block or set(block) - {"cases", "untranslated"}:
        return ["harness holds `cases` and/or `untranslated`, and is absent when empty"]
    errors = []
    cases = block.get("cases", {})
    if not isinstance(cases, dict) or ("cases" in block and not cases):
        errors.append("harness.cases is a non-empty {program: case}")
    else:
        stray = sorted(set(cases) - set(t.get("eligible", [])))
        if stray:
            errors.append(f"harness.cases names programs that are not eligible: {stray}")
        if any(not isinstance(v, str) or not v for v in cases.values()):
            errors.append("harness.cases values are case names")
    untr = block.get("untranslated", [])
    if not isinstance(untr, list) or ("untranslated" in block and not untr):
        errors.append("harness.untranslated is a non-empty list")
    elif any(not isinstance(b, dict) or not {"fix", "programs", "items"} <= set(b) for b in untr):
        errors.append("harness.untranslated entries carry fix, programs and items")
    return errors


def cmd_sync(opts: argparse.Namespace) -> int:
    from gitgalaxy.tools.cobol_to_java import port_runner

    ledger = load(opts.ledger)
    trial = _trial(ledger, opts.trial)
    attach_harness(trial, _parse_pairs(opts.case, "--case"), opts.proof_blockers)
    changed = sync(
        trial, port_runner.events(opts.project.resolve()), fix_commits(opts.repo, trial["system"]["engine_commit"])
    )
    problems = validate(ledger)
    if problems:
        raise SystemExit("the ledger would be invalid:\n  " + "\n  ".join(problems))
    save(ledger, opts.ledger)
    refresh_outputs(ledger, opts.ledger)
    for key in trial["programs"]:
        print(f"  {key}: {trial['programs'][key]['final']}" + ("  (updated)" if key in changed else ""))
    return 0


def record_run(
    trial: dict[str, Any], run: dict[str, Any], fixes: dict[str, tuple[str, str]], at: str
) -> dict[str, int]:
    """#8322: book a measured run whose port log was not kept. `run` is one run of a `trial.py run` summary;
    `fixes` is {program: (cause, full fix sha)} for each program the run did not prove, whose later proof (the
    post-fix rerun) is attempt 2. Attempt 1 is the run's verdict and is never rewritten. {program: attempts}."""
    if trial.get("closed"):
        raise SystemExit(f"{trial['id']} is closed")
    stray = sorted(set(run["programs"]) ^ set(trial["programs"]))
    if stray:
        raise SystemExit(f"the run and the trial disagree on the eligible programs: {stray}")
    extra = sorted(set(fixes) - {k for k, r in run["programs"].items() if r["state"] != "proven"})
    if extra:
        raise SystemExit(f"--fix names programs the run proved: {extra}")
    changed = {}
    for key, res in run["programs"].items():
        first = {"n": 1, "at": at, "model": None, "oracle": res["oracle"]}
        if res["state"] == "proven":
            attempts = [{**first, "outcome": "proven", "cause": None, "fix_commit": None}]
        elif res["state"] == "not-proven" and key in fixes:
            cause, sha = fixes[key]
            attempts = [{**first, "outcome": "failed", "cause": cause, "fix_commit": sha},
                        {**first, "n": 2, "outcome": "proven", "cause": None, "fix_commit": None}]  # fmt: skip
        else:
            raise SystemExit(f"{key}: state {res['state']} needs a judged failure and a --fix to be recorded")
        old = trial["programs"][key]["attempts"]
        if old and old != attempts:
            raise SystemExit(f"{trial['id']} {key}: a recorded attempt is never rewritten")
        if old != attempts:
            changed[key] = len(attempts)
        trial["programs"][key]["attempts"] = attempts
        trial["programs"][key]["final"] = final_of(attempts)
    return changed


def cmd_record(opts: argparse.Namespace) -> int:
    ledger = load(opts.ledger)
    trial = _trial(ledger, opts.trial)
    summary_doc = json.loads(opts.summary.read_text(encoding="utf-8"))
    if opts.run == "A" or opts.run not in summary_doc["runs"]:
        raise SystemExit("only the measuring run (B) is ledger data; run A is reported beside it, never booked")
    if summary_doc.get("engine_commit") != trial["system"]["engine_commit"]:
        raise SystemExit("the run was not made at the trial's frozen engine")
    fixes = {}
    for prog, spec in _parse_pairs(opts.fix, "--fix").items():
        cause, _, sha = spec.partition(":")
        if cause not in OUR_CAUSES or not sha:
            raise SystemExit(f"--fix takes PROGRAM=<{'|'.join(OUR_CAUSES)}>:SHA, not {prog}={spec}")
        full = git(opts.repo, "rev-parse", "--verify", f"{sha}^{{commit}}")
        frozen = trial["system"]["engine_commit"]
        if subprocess.run(["git", "-C", str(opts.repo), "merge-base", "--is-ancestor", frozen, full],  # noqa: S603, S607
                          check=False).returncode != 0 or full == frozen:  # fmt: skip
            raise SystemExit(f"{prog}: fix {sha} is not a commit after the frozen engine")
        fixes[prog] = (cause, full)
    changed = record_run(trial, summary_doc["runs"][opts.run], fixes, opts.at)
    problems = validate(ledger)
    if problems:
        raise SystemExit("the ledger would be invalid:\n  " + "\n  ".join(problems))
    save(ledger, opts.ledger)
    refresh_outputs(ledger, opts.ledger)
    for key, p in trial["programs"].items():
        print(f"  {key}: {p['final']}" + ("  (updated)" if key in changed else ""))
    return 0


def close(trial: dict[str, Any], causes: dict[str, str], withdrawn: str | None = None) -> None:
    """End a trial. With `withdrawn`, a program that was never attempted becomes `withdrawn` rather than
    not-proven: an unrun proof phase leaves the first-try rate UNMEASURED instead of publishing a 0%."""
    if withdrawn:
        trial["withdrawn"] = withdrawn
    for key, p in trial["programs"].items():
        if p["final"] != "open":
            continue
        if withdrawn and not p["attempts"]:
            p["final"] = "withdrawn"
            continue
        last = p["attempts"][-1]["cause"] if p["attempts"] else None
        cause = causes.get(key) or last
        if cause not in CAUSES:
            raise SystemExit(f"{key} is not proven: declare its cause with --cause {key}=<{'|'.join(CAUSES)}>")
        p["final"] = f"not-proven({cause})"
    trial["closed"] = _today()


def cmd_close(opts: argparse.Namespace) -> int:
    ledger = load(opts.ledger)
    attach_harness(_trial(ledger, opts.trial), _parse_pairs(opts.case, "--case"), opts.proof_blockers)
    close(_trial(ledger, opts.trial), _parse_pairs(opts.cause, "--cause"), opts.withdrawn)
    problems = validate(ledger)
    if problems:
        raise SystemExit("the ledger would be invalid:\n  " + "\n  ".join(problems))
    save(ledger, opts.ledger)
    refresh_outputs(ledger, opts.ledger)
    print(f"{opts.trial}: closed" + (" (withdrawn: its proof phase never ran)" if opts.withdrawn else ""))
    return 0


# ---- report ----------------------------------------------------------------------------
def _bin(final: str) -> str | None:
    """The histogram bin of a final state (None: still open)."""
    if final.startswith("proven@"):
        n = int(re.split(r"[@(]", final)[1])
        return BINS[min(n, 4) - 1]
    if final.startswith("not-proven("):
        return "not proven: " + final[len("not-proven(") : -1]
    return None


COLUMNS = (*BINS, *[f"not proven: {c}" for c in CAUSES])


def _counted(trial: dict[str, Any], p: dict[str, Any]) -> bool:
    """A program counts toward the rate once its first attempt has a verdict, or its trial is closed.

    A withdrawn program never counts: its proof was never attempted, so it is unmeasured, not a failure."""
    if p["final"] == "withdrawn":
        return False
    return bool(p["attempts"]) or bool(trial.get("closed"))


def summary(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per engine version (in trial order): trials, estates, first-try proven / counted, and the bins."""
    out: dict[str, dict[str, Any]] = {}
    for t in ledger["trials"]:
        v = out.setdefault(t["system"]["engine_version"], {"trials": [], "estates": [], "first": 0, "counted": 0,
                                                           "open": 0, "withdrawn": 0, "bins": {}})  # fmt: skip
        v["trials"].append(t["id"])
        if t["estate"] not in v["estates"]:
            v["estates"].append(t["estate"])
        for p in t["programs"].values():
            b = _bin(p["final"])
            if _counted(t, p):
                v["counted"] += 1
                v["first"] += p["final"] == "proven@1"
            if p["final"] == "withdrawn":
                v["withdrawn"] += 1
            elif b is None:
                v["open"] += 1
            else:
                v["bins"].setdefault(b, {}).setdefault(t["estate"], 0)
                v["bins"][b][t["estate"]] += 1
    return out


def headline(ledger: dict[str, Any]) -> str:
    s = summary(ledger)
    if not s:
        return "first-try proof rate: no trial yet (0 fresh estates trialled)"
    ver, v = list(s.items())[-1]
    n = len(v["estates"])
    if not v["counted"]:
        why = " (proof phase withdrawn)" if v["withdrawn"] else ""
        return f"first-try proof rate: not measured{why} on {n} fresh estates at engine {ver}"
    rate = f"{100 * v['first'] / v['counted']:.0f}%"
    return f"first-try proof rate: {v['first']}/{v['counted']} ({rate}) on {n} fresh estates at engine {ver}"


def fixes_per_estate(ledger: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Per trialled estate: failed attempts by cause -- ours (ticket / generator / engine / harness) vs the model's."""
    out: dict[str, dict[str, int]] = {}
    for t in ledger["trials"]:
        row = out.setdefault(t["estate"], dict.fromkeys(CAUSES, 0))
        for p in t["programs"].values():
            for a in p["attempts"]:
                if a["cause"]:
                    row[a["cause"]] += 1
    return out


# ---- the per-estate page (#4493) ---------------------------------------------------------
_BLOCKER_FIX = {
    "ticket": "Fix the porting ticket (its instructions or context) for",
    "generator": "Fix the Java generator for",
    "engine": "Fix the engine's extraction for",
    "harness": "Fix or extend the equivalence harness so it can run",
    "model": "Retry with the model, or declare the cause on",
    "undiagnosed": "Attempt and diagnose",
}


def program_state(p: dict[str, Any]) -> tuple[str, str | None]:
    """(run status, cause) of one eligible program: proven / differs / couldn't run / not attempted / withdrawn."""
    final = p["final"]
    if final.startswith("proven@"):
        return "proven", None
    if final == "withdrawn":
        return "withdrawn", None
    last = p["attempts"][-1] if p["attempts"] else None
    if final.startswith("not-proven("):
        cause = final[len("not-proven(") : -1]
    else:
        cause = last["cause"] if last else None
    if last is None:
        return "not attempted", cause
    if last.get("oracle") == "compile-failed":  # the oracle never ran: not a difference (#8325)
        return "couldn't run", cause
    return ("differs" if last["outcome"] == "failed" else "couldn't run"), cause


def _oracle(p: dict[str, Any]) -> str:
    """#8325: the oracle's compile status at the program's latest attempt that recorded one ('-' before any)."""
    seen = [a["oracle"] for a in p["attempts"] if a.get("oracle")]
    return seen[-1] if seen else "-"


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "-"


def case_facts(
    cases: dict[str, str] | None, cases_dir: Path | None, roots: list[Path] | None = None
) -> dict[str, dict[str, Any]]:
    """{program: tests, input generation, coverage} for the programs that have an equivalence case (#4493).

    The harness report's own readers, so a trial page and the estate page can't disagree. Case JSON only; no estate
    code is read. A program with no case is absent: its numbers stay 'not measured'. With corpus `roots`, each generated
    record's layout limit is read too (`inputs.records`); the keys are present only when non-empty."""
    if not cases:
        return {}
    import harness_report as hr

    root = cases_dir or hr.CASES
    out: dict[str, dict[str, Any]] = {}
    for prog, name in sorted(cases.items()):
        case = hr.load_case(root, name)
        if case:
            inputs = hr.input_generation(case)
            if roots is not None and inputs["generated"]:
                inputs["records"] = [
                    g | {"cause": c} | ({"symbols": sy} if sy else {})
                    for g in inputs["generated"]
                    for c, sy in [hr.record_limit(roots, case, g["dataset"])]
                ]
            if kinds := hr.non_vsam_kinds(case):
                inputs["non_vsam"] = kinds
            out[prog] = {"case": name, "tests": hr.scenario_count(case), "inputs": inputs,
                         "coverage": hr.case_coverage(root, name)}  # fmt: skip
    return out


def trial_blockers(trial: dict[str, Any], facts: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Each non-proven program under exactly ONE cause, sorted by tests unlocked (when cases are known), then by
    programs held back."""
    by: dict[str, list[str]] = {}
    for key, p in sorted(trial["programs"].items()):
        status, cause = program_state(p)
        if status != "proven":
            by.setdefault(cause or "undiagnosed", []).append(key)
    rows = [{"cause": c, "programs": ps} for c, ps in by.items()]
    tests = {k: f["tests"] for k, f in (facts or {}).items()}
    for r in rows:
        if tests:
            r["tests_unlocked"] = sum(tests.get(k, 0) for k in r["programs"])
    rows.sort(key=lambda r: (-r.get("tests_unlocked", 0), -len(r["programs"]), r["cause"]))
    return rows


def trial_page(
    ledger: dict[str, Any],
    trial: dict[str, Any],
    rehearsal: bool = False,
    facts: dict[str, dict[str, Any]] | None = None,
    untranslated: list[dict[str, Any]] | None = None,
) -> str:
    """The harness's self-report for one trial, from the ledger alone (no estate code is read).

    A rehearsal (`preview --page`) has a declaration but no attempts: every eligible program is not attempted."""
    name = _name(ledger, trial["estate"])
    elig, oos = trial["eligible"], trial["out_of_scope"]
    states = {k: program_state(trial["programs"][k]) for k in elig}
    counts: dict[str, int] = {}
    for status, _c in states.values():
        counts[status] = counts.get(status, 0) + 1
    total = len(elig) + len(oos)
    proven = counts.get("proven", 0)
    head = f"# Equivalence harness report: {name}" + (" (rehearsal)" if rehearsal else f" ({trial['id']})")
    how = ("A rehearsal from `trial.py preview`: no ledger entry, never first-try." if rehearsal else
           "Generated by `python tests/tools/trial.py report --write` from `tests/cobol_mainframe/trials.json`.")  # fmt: skip
    facts = {k: f for k, f in (facts or {}).items() if k in elig}
    cov = [f["coverage"] for f in facts.values() if f["coverage"]]
    if cov:
        para = (sum(c["paragraphs_covered"] for c in cov), sum(c["paragraphs_live"] for c in cov))
        br = (sum(c["branches_covered"] for c in cov), sum(c["branches_total"] for c in cov))
        measured = (f"paragraphs {para[0]} of {para[1]} ({_pct(*para)}), branches {br[0]} of {br[1]} ({_pct(*br)}) "
                    f"exercised, over {len(cov)} program{'s' if len(cov) != 1 else ''} with a measured case")  # fmt: skip
    else:
        measured = "paragraphs and branches exercised: not measured here (a trial estate has no cobol_coverage run)"
    out = [head, "", how, "Do not edit by hand.", "", *[f"- {c}" for c in CAVEATS], "", "## Coverage", ""]
    out += [f"- programs in the estate: {total}",
            f"- eligible (declared up front): {len(elig)} ({_pct(len(elig), total)})",
            f"- out of scope: {len(oos)} ({_pct(len(oos), total)})",
            f"- proven: {proven} of {len(elig)} eligible ({_pct(proven, len(elig))})",
            f"- {measured}",
            "", "## Run status", ""]  # fmt: skip
    out += [
        f"- {st}: {counts.get(st, 0)}" for st in ("proven", "differs", "couldn't run", "not attempted", "withdrawn")
    ]
    out += ["", "| program | status | oracle | final | attempts (outcome/cause) |", "|---|---|---|---|---|"]
    for key in sorted(elig):
        p = trial["programs"][key]
        steps = ", ".join(f"{a['n']}:{a['outcome']}" + (f"/{a['cause']}" if a["cause"] else "") for a in p["attempts"])
        out.append(f"| {key} | {states[key][0]} | {_oracle(p)} | {p['final']} | {steps or '-'} |")
    if facts:
        out += ["", "## Input generation", "", "| program | case | tests | generated | shipped data | no input |",
                "|---|---|---|---|---|---|"]  # fmt: skip
        for key in sorted(facts):
            f, i = facts[key], facts[key]["inputs"]
            gen = ", ".join(f"{g['dataset']} ({g['record'] or g['copybook'] or '?'})" for g in i["generated"])
            out.append(f"| {key} | {f['case']} | {f['tests']} | {gen or '-'} | {', '.join(i['shipped']) or '-'} "
                       f"| {', '.join(i['skipped']) or '-'} |")  # fmt: skip
        missing = sorted(set(elig) - set(facts))
        if missing:
            out.append("")
            out.append(f"No equivalence case yet (inputs not measured): {', '.join(missing)}.")
        import harness_report as hr

        rows = [{"program": k, "case": f["case"]} for k, f in facts.items()]
        limits = hr.input_blockers(rows, {f["case"]: f["inputs"] for f in facts.values()},
                                   {f["case"]: f["tests"] for f in facts.values()})  # fmt: skip
        if limits:
            out += ["", "## Input-generation limits (what stops a test being generated)", ""]
            for n, b in enumerate(limits, 1):
                out.append(f"{n}. {b['fix']} Holds back {b['tests_held']} tests across {len(b['programs'])} programs.")
                out += [f"   - {it}" for it in b["items"]]
    if untranslated:  # #4493 classes 4 / 5: unresolved links, missing stubs, refused or holey programs
        out += ["", "## Programs with no translation yet (no case can run them)", ""]
        for n, b in enumerate(untranslated, 1):
            out.append(f"{n}. {b['fix']} Frees {len(b['programs'])} programs to get a case.")
            out += [f"   - {it}" for it in b["items"]]
    out += ["", "## Out of scope (declared at start)", ""]
    by_reason: dict[str, list[str]] = {}
    for key, why in sorted(oos.items()):
        by_reason.setdefault(why.replace("|", "/"), []).append(key)
    if not by_reason:
        out.append("None.")
    for why, ps in sorted(by_reason.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append(f"- {why} ({len(ps)}): {', '.join(ps)}")
    out += ["", "## Blockers, stated as fixes (most programs held back first)", ""]
    blockers = trial_blockers(trial, facts)
    if not blockers:
        out.append("None: every eligible program is proven.")
    for n, b in enumerate(blockers, 1):
        ps = b["programs"]
        unlocks = f"{len(ps)}" + (f" programs, {b['tests_unlocked']} tests" if "tests_unlocked" in b else "")
        out.append(f"{n}. {_BLOCKER_FIX[b['cause']]} {len(ps)} program{'s' if len(ps) != 1 else ''}: {', '.join(ps)} "
                   f"(cause: {b['cause']}; unlocks {unlocks}).")  # fmt: skip
    return "\n".join(out) + "\n"


def page_path(name: str) -> Path:
    return PAGES / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', name)}.md"


def trial_pages(ledger: dict[str, Any], cases_dir: Path | None = None) -> dict[str, str]:
    """{file name: text} for the latest trial of each estate; a trial's `harness` block adds its cases' facts."""
    latest = {t["estate"]: t for t in ledger["trials"]}
    out = {}
    for e, t in latest.items():
        h = t.get("harness", {})
        facts = case_facts(h.get("cases"), cases_dir) if h.get("cases") else None
        out[page_path(_name(ledger, e)).name] = trial_page(ledger, t, facts=facts, untranslated=h.get("untranslated"))
    return out


def stale_pages(ledger: dict[str, Any], pages_dir: Path | None = None) -> list[str]:
    """The pages that are missing, stale or orphaned (a page for no trial)."""
    want = trial_pages(ledger)
    root = pages_dir or PAGES
    stale = [
        n for n, text in want.items() if not (root / n).is_file() or (root / n).read_text(encoding="utf-8") != text
    ]
    if root.is_dir():
        stale += [p.name for p in sorted(root.glob("*.md")) if p.name not in want]
    return stale


def write_pages(ledger: dict[str, Any], pages_dir: Path | None = None) -> list[Path]:
    root = pages_dir or PAGES
    for old in root.glob("*.md") if root.is_dir() else []:
        old.unlink()
    out = []
    for name, text in trial_pages(ledger).items():
        root.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
        out.append(root / name)
    return out


def _name(ledger: dict[str, Any], estate_id: str) -> str:
    e = _estate(ledger, estate_id) or {}
    return str(e.get("label") or estate_id) if e.get("kind") == "private" else estate_id


CAVEATS = (
    "Public code may be in a model's training data; only private estates escape that.",
    "Eligibility is declared up front, at trial start, so 'out of scope' cannot hide a failure.",
)


def render(ledger: dict[str, Any]) -> str:
    out = ["# Fresh-estate trials -- the first-try proof rate", "",
           "Generated by `python tests/tools/trial.py report --write` from `tests/cobol_mainframe/trials.json`.",
           "Do not edit by hand. `check` (in CI) fails when this page or the chart is stale.", "",
           f"**{headline(ledger)}**", "",
           "Per program: did the porting loop's FIRST attempt produce Java the equivalence harness proves",
           "identical to the COBOL? A trial freezes the system (engine commit, porting rules, model, harness),",
           "takes an estate the system has never seen, and iterates each eligible program to a proof. Each",
           "failed attempt carries its cause: the model's (a retry, same system) or ours (a fix commit with a",
           "`Trial-Cause:` trailer: ticket, generator, engine, harness). A trialled estate is development data",
           "for good: its numbers stay here but never count as first-try again. The rate counts programs whose",
           "first attempt has a verdict (and every program of a closed trial). A WITHDRAWN trial's proof phase",
           "never ran: its programs were never attempted, so they are left out of the rate rather than counted",
           "as failures, and the rate reads 'not measured'.", "",
           *[f"- {c}" for c in CAVEATS], "", "![attempts to proof](fresh_estate_trials.svg)", "",
           "## Trials", ""]  # fmt: skip
    if not ledger["trials"]:
        out += ["No trial yet."]
    else:
        out += ["| trial | estate | kind | started | closed | engine | model | eligible | out of scope | "
                + " | ".join(COLUMNS) + " | withdrawn | open |",
                "|" + "---|" * (9 + len(COLUMNS) + 2)]  # fmt: skip
        for t in ledger["trials"]:
            bins: dict[str, int] = {}
            for p in t["programs"].values():
                b = _bin(p["final"]) or ("withdrawn" if p["final"] == "withdrawn" else "open")
                bins[b] = bins.get(b, 0) + 1
            kind = (_estate(ledger, t["estate"]) or {}).get("kind", "?")
            sysm = t["system"]
            out.append(f"| {t['id']} | {_name(ledger, t['estate'])} | {kind} | {t['started']} | "
                       f"{t.get('closed') or '-'} | {sysm['engine_version']} | "
                       f"{sysm['model_version']} ({sysm['backend']}) | "
                       f"{len(t['eligible'])} | {len(t['out_of_scope'])} | "
                       + " | ".join(str(bins.get(c, 0)) for c in (*COLUMNS, "withdrawn", "open")) + " |")  # fmt: skip
        out += [
            "",
            "## Programs",
            "",
            "| trial | program | oracle | final | attempts (outcome/cause) |",
            "|---|---|---|---|---|",
        ]
        for t in ledger["trials"]:
            for key, p in sorted(t["programs"].items()):
                steps = ", ".join(f"{a['n']}:{a['outcome']}" + (f"/{a['cause']}" if a["cause"] else "")
                                  + (f" {a['fix_commit'][:10]}" if a["fix_commit"] else "")
                                  for a in p["attempts"])  # fmt: skip
                out.append(f"| {t['id']} | {key} | {_oracle(p)} | {p['final']} | {steps or '-'} |")
            for key, reason in sorted(t["out_of_scope"].items()):
                out.append(f"| {t['id']} | {key} | - | out-of-scope({reason.replace('|', '/')}) | - |")
    out += ["", "## Estates", "", "| estate | kind | status | repo @ ref | trialled by |", "|---|---|---|---|---|"]
    for e in ledger["estates"]:
        where = f"{e['repo']} @ {e['ref'][:12]}" if e["kind"] == "public" else "(private)"
        by = e.get("trialled_by") or "-"
        if any(t["id"] == by for t in ledger["trials"]):
            by = f"[{by}](trials/{page_path(_name(ledger, e['id'])).name})"
        out.append(f"| {_name(ledger, e['id'])} | {e['kind']} | {e['status']} | {where} | {by} |")
    return "\n".join(out) + "\n"


# The repo's chart palette (tri_comparison_chart.py; the dataviz reference order), assigned to estates in
# trial order, never cycled: a ninth estate folds into "other".
_ESTATE_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
_OTHER = "#9a9a95"
# fixes: ours as one blue ramp (a cause each), the model's in the neutral grey
_CAUSE_COLORS = {
    "ticket": "#0d4a8f",
    "generator": "#2a78d6",
    "engine": "#6ea6e8",
    "harness": "#b3d0f2",
    "model": _OTHER,
}


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_svg(ledger: dict[str, Any]) -> str:
    s = summary(ledger)
    estates = list(dict.fromkeys(t["estate"] for t in ledger["trials"]))
    color = {e: (_ESTATE_COLORS[i] if i < len(_ESTATE_COLORS) else _OTHER) for i, e in enumerate(estates)}
    facets = list(s.items()) or [("(no trial yet)", {"bins": {}, "open": 0})]
    col_w, left = 60, 56
    facet_w = col_w * len(COLUMNS) + 24
    width = max(760, left + facet_w * len(facets) + 24)
    top, plot_h = 96, 180
    fixes = fixes_per_estate(ledger)
    fix_rows = max(len(fixes), 1)
    panel2 = top + plot_h + 110
    height = panel2 + 40 + fix_rows * 26 + 40 + 16 * (len(CAVEATS) + 1)
    peak = max([sum(v.values()) for _, f in facets for v in f["bins"].values()] + [1])
    step = max(1, -(-peak // 4))
    ymax = step * 4
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
         'font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
         "<style>.t{font-size:15px;font-weight:600;fill:#0b0b0b}.s{font-size:11px;fill:#52514e}"
         ".h{font-size:10.5px;font-weight:600;fill:#0b0b0b}.a{font-size:9px;fill:#706f6a}"
         ".l{font-size:10px;fill:#0b0b0b}.c{font-size:10px;fill:#52514e;font-style:italic}</style>",
         f'<rect width="{width}" height="{height}" fill="#fcfcfb"/>',
         f'<text x="16" y="26" class="t">{_esc(headline(ledger))}</text>',
         '<text x="16" y="44" class="s">Programs by the attempt that proved them (or why not), coloured by estate, '
         'one panel per engine version.</text>']  # fmt: skip
    lx = 16
    for e in estates or []:
        p.append(f'<rect x="{lx}" y="58" width="12" height="8" rx="2" fill="{color[e]}"/>')
        p.append(f'<text x="{lx + 16}" y="66" class="l">{_esc(_name(ledger, e))}</text>')
        lx += 28 + 6 * len(_name(ledger, e))
    for fi, (ver, f) in enumerate(facets):
        x0 = left + fi * facet_w
        p.append(f'<text x="{x0 + (facet_w - 24) / 2:.0f}" y="{top - 10}" class="h" text-anchor="middle">'
                 f"engine {_esc(ver)}" + (f" ({f['open']} open)" if f.get("open") else "") + "</text>")  # fmt: skip
        for k in range(5):
            y = top + plot_h - plot_h * k / 4
            p.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + facet_w - 24}" y2="{y:.1f}" stroke="#eeede9"/>')
            if fi == 0:
                p.append(f'<text x="{x0 - 6}" y="{y + 3:.1f}" class="a" text-anchor="end">{step * k}</text>')
        for ci, col in enumerate(COLUMNS):
            cx = x0 + ci * col_w
            y = top + plot_h
            for e in estates:
                n = f["bins"].get(col, {}).get(e, 0)
                if not n:
                    continue
                h = plot_h * n / ymax
                y -= h
                p.append(f'<rect x="{cx + 8}" y="{y:.1f}" width="{col_w - 16}" height="{max(h - 2, 1):.1f}" rx="2" '
                         f'fill="{color[e]}"><title>{_esc(_name(ledger, e))}: {n} {_esc(col)}</title>'
                         "</rect>")  # fmt: skip
            total = sum(f["bins"].get(col, {}).values())
            if total:
                p.append(f'<text x="{cx + col_w / 2}" y="{y - 4:.1f}" class="a" text-anchor="middle">{total}</text>')
            label = col.replace("not proven: ", "✗ ")
            p.append(f'<text x="{cx + col_w / 2}" y="{top + plot_h + 14}" class="a" text-anchor="middle">'
                     f"{_esc(label)}</text>")  # fmt: skip
        p.append(f'<text x="{x0 + 2 * col_w}" y="{top + plot_h + 30}" class="a" text-anchor="middle">'
                 "proven at attempt</text>")  # fmt: skip
        p.append(f'<text x="{x0 + 6.5 * col_w}" y="{top + plot_h + 30}" class="a" text-anchor="middle">'
                 "not proven, by cause</text>")  # fmt: skip
    p.append(f'<text x="16" y="{panel2}" class="h">Failed attempts per estate: fixes on our side (by cause) vs the '
             "model's retries</text>")  # fmt: skip
    lx = 16
    for c in (*OUR_CAUSES, "model"):
        who = "model" if c == "model" else f"ours: {c}"
        p.append(f'<rect x="{lx}" y="{panel2 + 10}" width="12" height="8" rx="2" fill="{_CAUSE_COLORS[c]}"/>')
        p.append(f'<text x="{lx + 16}" y="{panel2 + 18}" class="l">{who}</text>')
        lx += 30 + 6 * len(who)
    peak2 = max([sum(r.values()) for r in fixes.values()] + [1])
    bar_x, bar_w = 260, width - 400
    y = panel2 + 36
    if not fixes:
        p.append(f'<text x="16" y="{y + 12}" class="c">no trial yet</text>')
    for e, row in fixes.items():
        p.append(f'<text x="{bar_x - 8}" y="{y + 12}" class="l" text-anchor="end">{_esc(_name(ledger, e))}</text>')
        x = float(bar_x)
        for c in (*OUR_CAUSES, "model"):
            if row[c]:
                w = bar_w * row[c] / peak2
                p.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="16" rx="2" '
                         f'fill="{_CAUSE_COLORS[c]}"><title>{_esc(_name(ledger, e))}: {row[c]} {c}</title>'
                         "</rect>")  # fmt: skip
                x += w
        ours = sum(row[c] for c in OUR_CAUSES)
        p.append(f'<text x="{x + 6:.1f}" y="{y + 12}" class="a">{ours} ours, {row["model"]} model</text>')
        y += 26
    y += 20
    for c in CAVEATS:
        p.append(f'<text x="16" y="{y}" class="c">{_esc(c)}</text>')
        y += 16
    p.append("</svg>")
    return "\n".join(p) + "\n"


# ---- verify: the frozen system, re-checked ---------------------------------------------
TICKET_SOURCE = "gitgalaxy/tools/cobol_to_java/cobol_to_java_port_tickets.py"


def _git_ok(repo: Path, *args: str) -> bool:
    argv = ["git", "-C", str(repo), *args]
    return subprocess.run(argv, capture_output=True, check=False).returncode == 0  # noqa: S603


def verify_frozen(
    t: dict[str, Any],
    repo: Path,
    oracle: dict[str, Any] | None = None,
    rules: str | None = None,
    rebuilt: dict[str, Any] | None = None,
) -> list[tuple[str, bool, str]]:
    """Re-compute each fact a trial froze: [(check, ok, detail)]. Reads only; `oracle` is an
    equivalence_oracle fingerprint (None: not checked), `rules` the porting-rules hash (default: computed)."""
    sysd = t.get("system", {})
    out: list[tuple[str, bool, str]] = []
    for key in ("engine_commit", "harness_commit"):
        sha = str(sysd.get(key, ""))
        out.append((key, bool(sha) and _git_ok(repo, "cat-file", "-e", f"{sha}^{{commit}}"), sha[:12]))
    engine = str(sysd.get("engine_commit", ""))
    out.append(("engine_is_ancestor_of_head", _git_ok(repo, "merge-base", "--is-ancestor", engine, "HEAD"), ""))
    untouched = _git_ok(repo, "diff", "--quiet", engine, "--", TICKET_SOURCE)
    out.append(("ticket_source_unchanged_since_freeze", untouched, TICKET_SOURCE))
    have = rules if rules is not None else porting_rules_hash()[0]
    want = sysd.get("porting_rules_hash")
    out.append(("porting_rules_hash", have == want, f"computes {have[:12]}, frozen {str(want)[:12]}"))
    eligible, oos = t.get("eligible", []), t.get("out_of_scope", {})
    declared = declaration_hash(eligible, oos) == t.get("declared")
    out.append(("declaration_hash", declared, f"{len(eligible)} eligible, {len(oos)} out of scope"))
    if oracle is not None:
        why = "; ".join(oracle.get("mismatches", [])) or f"cobc {oracle.get('cobc')}"
        out.append(("oracle_matches_pin", bool(oracle.get("matches_pin")), why))
    if rebuilt is not None:  # #8322: the Dockerfile builds the same oracle the proofs ran on
        drift = list(rebuilt.get("mismatches", []))
        if oracle is not None:
            drift += [f"{k}: rebuild {rebuilt.get(k)!r}, local {oracle.get(k)!r}" for k in ("cobc", "gnucobol3")
                      if rebuilt.get(k) != oracle.get(k)]  # fmt: skip
        out.append(
            (
                "oracle_rebuild_reproduces",
                not drift and bool(rebuilt.get("matches_pin")),
                "; ".join(drift) or f"cobc {rebuilt.get('cobc')}, gnucobol3 {rebuilt.get('gnucobol3')}",
            )
        )
    return out


def cmd_verify(opts: argparse.Namespace) -> int:
    """Read-only: nothing is written to the ledger or the pages."""
    ledger = load(opts.ledger)
    found = [t for t in ledger.get("trials", []) if t.get("id") == opts.trial]
    if not found:
        print(f"no trial {opts.trial}")
        return 1
    oracle = None
    if not opts.no_oracle:
        import equivalence_oracle as eo

        try:
            oracle = eo.fingerprint()
        except (RuntimeError, OSError) as exc:  # no docker, no image: a failed check, never a skipped one
            oracle = {"matches_pin": False, "mismatches": [str(exc)]}
    rebuilt = None
    if opts.rebuild_oracle:
        import equivalence_oracle as eo

        try:
            rebuilt = eo.rebuild()
        except (RuntimeError, OSError) as exc:  # a failed build is a failed check
            rebuilt = {"matches_pin": False, "mismatches": [str(exc)]}
    results = verify_frozen(found[0], opts.repo, oracle, rebuilt=rebuilt)
    for name, ok, detail in results:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    return 0 if all(ok for _n, ok, _d in results) else 1


def check_regenerated(
    t: dict[str, Any], preview: dict[str, Any], rules: str, tickets: set[str], estate_ref: str | None, ref: str | None
) -> list[tuple[str, bool, str]]:
    """Judge a ticket regeneration run at the frozen engine: [(check, ok, detail)]. Pure; reads nothing."""
    eligible, oos = t.get("eligible", []), t.get("out_of_scope", {})
    again = declaration_hash(preview.get("eligible", []), preview.get("out_of_scope", {}))
    missing = sorted(set(eligible) - tickets)
    want = t.get("system", {}).get("porting_rules_hash")
    return [
        ("estate_at_pinned_ref", bool(ref) and estate_ref == ref, f"estate {str(estate_ref)[:12]}, pinned {str(ref)[:12]}"),
        ("declaration_reproduces", again == t.get("declared"), f"{len(preview.get('eligible', []))} eligible"),
        ("frozen_rules_hash", rules == want, f"frozen engine computes {rules[:12]}, frozen {str(want)[:12]}"),
        ("every_eligible_program_has_a_ticket", not missing, f"missing {missing}" if missing else f"{len(eligible)} tickets"),
    ]  # fmt: skip


_RULES_SNIPPET = (
    "import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + '/tests/tools'); "
    "import trial; print(trial.porting_rules_hash()[0])"
)


def _frozen_env(tree: Path) -> dict[str, str]:
    """The environment for a run inside the frozen tree: PYTHONPATH is the tree alone, never the preset main checkout."""
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(tree)
    return env


def _in_frozen(tree: Path, *argv: str) -> str:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, *argv], capture_output=True, text=True, check=False, cwd=tree, env=_frozen_env(tree)
    )
    if proc.returncode != 0:
        raise SystemExit(f"{' '.join(argv[:2])} failed in the frozen tree: {proc.stderr.strip()[-600:]}")
    return proc.stdout.strip()


def cmd_tickets(opts: argparse.Namespace) -> int:
    """Regenerate the trial's tickets with the FROZEN engine (a detached worktree of its commit), then check them.

    Writes only under --work (the worktree, the project, tickets_manifest.json); the ledger and pages are untouched."""
    ledger = load(opts.ledger)
    found = [t for t in ledger.get("trials", []) if t.get("id") == opts.trial]
    if not found:
        print(f"no trial {opts.trial}")
        return 1
    t = found[0]
    sha = str(t["system"]["engine_commit"])
    estate = _estate(ledger, t["estate"]) or {}
    work = opts.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    tree = work / "frozen-engine"
    stale = sorted(p.name for p in work.iterdir() if p != tree)
    if stale:  # the frozen engine's refractor copies the estate into --work and does not overwrite
        raise SystemExit(f"--work must be empty (or hold only frozen-engine); found {stale}")
    if not tree.exists():
        git(opts.repo, "worktree", "add", "--detach", str(tree), sha)
    if git(tree, "rev-parse", "HEAD") != sha or git(tree, "status", "--porcelain"):
        raise SystemExit(f"{tree} is not a clean checkout of the frozen engine {sha[:12]}")
    rules = _in_frozen(tree, "-I", "-c", _RULES_SNIPPET, str(tree))
    out_json = work / "declaration.json"
    _in_frozen(tree, "tests/tools/trial.py", "preview", t["estate"], "--estate-path", str(opts.estate_path),
               "--work", str(work), "--json", str(out_json))  # fmt: skip
    preview = json.loads(out_json.read_text(encoding="utf-8"))
    jobs = work / "java_h2" / "ai_agent_jobs"
    names = {p.name[: -len("_port_ticket.json")]: p for p in jobs.glob("*_port_ticket.json")}
    results = check_regenerated(
        t, preview, rules, set(names), _estate_git(opts.estate_path.resolve(), "rev-parse", "HEAD"), estate.get("ref")
    )
    for name, ok, detail in results:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    ok_all = all(ok for _n, ok, _d in results)
    if ok_all:
        manifest = {"trial": t["id"], "engine_commit": sha, "porting_rules_hash": rules,
                    "tickets": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in sorted(names.items())}}  # fmt: skip
        (work / "tickets_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
        print(f"tickets in {jobs}; manifest {work / 'tickets_manifest.json'}")
    return 0 if ok_all else 1


# ---- the proof run (#8322): det port in the frozen engine, proved under each instrument ----------------------
ERROR_PATH_ONLY = frozenset({"HCPRESTW", "HCTRESTW", "HCMRESTW"})  # prereg Amendment 4: error-path cases only
RUNS = {"A": "the frozen harness", "B": "the harness at current main"}


def case_map(corpus: str, cases_dir: Path | None = None) -> dict[str, str]:
    """{program: case name} for the cases of one corpus (a program with two cases is refused: the run would guess)."""
    root = cases_dir or REPO_ROOT / "tests" / "equivalence"
    out: dict[str, str] = {}
    for f in sorted(root.glob("*/case.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        if c.get("corpus") != corpus:
            continue
        if c["program"] in out:
            raise SystemExit(f"{c['program']} has two cases ({out[c['program']]}, {f.parent.name})")
        out[c["program"]] = f.parent.name
    return out


def inlined_by_harness(case: dict[str, Any], corpus: Path) -> bool:
    """Whether `inline_exec_copies` (#8217) changes the program's compiled text: the programs a harness without it
    judges against a different reference (Amendment 4's 18 of 28), measured, never listed by hand."""
    import tempfile

    import equivalence_cics as ec
    import equivalence_common as common

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp)
        common.stage_copybooks(case, corpus, src)
        text, _enc = common.read_program(case, corpus / case["program_source"])
        return ec.inline_exec_copies(text, src).strip() != text.strip()


def build_instrument(repo: Path, tree: Path, harness_commit: str | None) -> Path:
    """A detached worktree of `repo`'s HEAD to prove under. With `harness_commit`, every HARNESS_PATHS entry is
    restored to that commit (one it did not have is removed): the frozen harness, with the cases as they are."""
    if tree.exists():
        return tree
    git(repo, "worktree", "add", "--detach", str(tree), "HEAD")
    if harness_commit:
        for rel in HARNESS_PATHS:
            git(tree, "rm", "-rq", "--ignore-unmatch", "--", rel)
            if git(tree, "ls-tree", harness_commit, "--", rel):
                git(tree, "checkout", harness_commit, "--", rel)
    return tree


def summarize_run(
    events: list[dict[str, Any]], eligible: list[str], flagged: frozenset[str] = frozenset()
) -> dict[str, Any]:
    """One run's first-attempt verdicts, decomposed (Amendment 4): proven / not proven (the oracle compiled) /
    not judged (it did not: cause `harness`, reason oracle-compile-failed, or no-report when the harness stopped first) / flagged (`flagged` programs whose oracle compiled anyway: a wrong
    reference passes a wrong port as readily as it fails one, so counted in neither) / no-port / unknown oracle.
    Pure. Only a program's FIRST verdict counts: attempt 1 is the measurement."""
    rows: dict[str, dict[str, Any]] = {}
    for key in eligible:
        mine = [e for e in events if e.get("ticket") == key]
        verdict = next((e for e in mine if e.get("event") in ("proven", "proof-failed")), None)
        proposed = next((e for e in mine if e.get("event") == "proposed"), None)
        row: dict[str, Any] = {}
        if key in ERROR_PATH_ONLY:
            row["scope"] = "error-path-only"
        holes = ((proposed or {}).get("translation") or {}).get("holes")
        if holes:
            row["holes"] = holes
        if verdict is None:
            row["state"] = "no-port"
        else:
            oracle = verdict.get("oracle") or "unknown"
            row["oracle"] = oracle
            row["outcome"] = "proven" if verdict["event"] == "proven" else "failed"
            if oracle == "compile-failed":
                row["state"], row["cause"], row["reason"] = "not-judged", "harness", "oracle-compile-failed"
            elif oracle == "unknown" and row["outcome"] == "failed":
                # the proof command exited non-zero and wrote no report: the harness stopped before any verdict
                row["state"], row["cause"], row["reason"] = "not-judged", "harness", "no-report"
            elif oracle == "unknown":
                row["state"] = "unknown-oracle"
            elif key in flagged:
                row["state"] = "flagged"
            else:
                row["state"] = "proven" if row["outcome"] == "proven" else "not-proven"
        rows[key] = row
    states = ("proven", "not-proven", "not-judged", "flagged", "no-port", "unknown-oracle")
    counts = {s: sum(1 for r in rows.values() if r["state"] == s) for s in states}
    return {"programs": rows, "counts": counts, "eligible": len(eligible)}


def _verdict_count(project: Path, key: str) -> int:
    from gitgalaxy.tools.cobol_to_java import port_runner

    return sum(1 for e in port_runner.events(project) if e.get("ticket") == key
               and e.get("event") in ("proven", "proof-failed"))  # fmt: skip


def cmd_run(opts: argparse.Namespace) -> int:
    """The det translator's first attempt per eligible program, at the FROZEN engine, then proved under Run A
    (the frozen harness) and Run B (the harness at HEAD), each on its own copy of the project so no log holds
    two verdicts of one attempt. Resumable: a program with a verdict in a run is not proved again there."""
    import os
    import shutil

    from gitgalaxy.tools.cobol_to_java import port_runner

    ledger = load(opts.ledger)
    t = _trial(ledger, opts.trial)
    work = opts.work.resolve()
    backend = getattr(opts, "backend", "det")
    suffix = "" if backend == "det" else f"_{backend}"
    if backend != "det":
        # the model leg spends money and is only a first-try measurement of the REGISTERED system: refuse before any call
        reg = t["system"]
        if reg.get("backend") != backend or not reg.get("model"):
            raise SystemExit(f"{t['id']} is registered with backend {reg.get('backend')!r}, not {backend!r}")
        if not os.environ.get(opts.api_key_env):
            raise SystemExit(f"the {backend} leg needs ${opts.api_key_env} (a key and spend only the owner grants)")
    tree, base_project = work / "frozen-engine", work / "java_h2"
    project = work / f"java_h2{suffix}"
    if not (tree / ".git").exists() or not (base_project / "ai_agent_jobs").is_dir():
        raise SystemExit(f"{work}: run `trial.py tickets {opts.trial}` first (frozen-engine, java_h2)")
    if git(tree, "rev-parse", "HEAD") != t["system"]["engine_commit"] or git(tree, "status", "--porcelain"):
        raise SystemExit(f"{tree} is not a clean checkout of the frozen engine")
    estate = opts.estate_path.resolve()
    cases = case_map(t["estate"])
    missing = [k for k in t["eligible"] if k not in cases]
    if missing:
        raise SystemExit(f"no equivalence case for {missing}")
    import equivalence as eq
    import mainframe_corpus as mc

    (entry,) = mc.select([t["estate"]])
    corpus = mc.require_clone(entry)
    flagged = frozenset(k for k in t["eligible"] if inlined_by_harness(eq.load_case(cases[k]), corpus))
    print(f"harness-inlined programs (oracle differs without #8217): {len(flagged)}")
    if backend != "det" and not project.exists():
        # the tickets only: the det leg's port log and attempts must not be read as this leg's
        shutil.copytree(base_project, project, symlinks=True, ignore=shutil.ignore_patterns("ports"))
    # 1. propose: the frozen engine's translator (det: once, deterministic; a model: attempt 1, no feedback)
    for key in t["eligible"]:
        if any(e.get("ticket") == key for e in port_runner.events(project)):
            continue
        argv = [sys.executable, "-m", "gitgalaxy.tools.cobol_to_java.port_runner", "run", str(project), "--ticket", key,
                "--backend", backend]  # fmt: skip
        if backend == "det":
            argv += ["--source-root", str(estate)]
        else:
            argv += ["--model", t["system"]["model"], "--api-key-env", opts.api_key_env]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=tree, env=_frozen_env(tree))  # noqa: S603
        print((proc.stdout or proc.stderr).strip().splitlines()[-1:] or [key])
    # 2. prove, per run, on a copy
    summary: dict[str, Any] = {"trial": t["id"], "engine_commit": t["system"]["engine_commit"], "backend": backend,
                               "harness_inlined": sorted(flagged), "runs": {}}  # fmt: skip
    for run in opts.runs:
        rproj = work / f"run{run}{suffix}"
        if not rproj.exists():
            shutil.copytree(project, rproj, symlinks=True)
        inst = build_instrument(
            opts.repo, work / f"instrument-{run}", t["system"]["harness_commit"] if run == "A" else None
        )
        for key in t["eligible"]:
            if _verdict_count(rproj, key) or not any(e.get("ticket") == key and e.get("event") == "proposed"
                                                      for e in port_runner.events(rproj)):  # fmt: skip
                continue
            cmd = (f"env PYTHONPATH={inst} {sys.executable} {inst}/tests/tools/equivalence.py run {cases[key]} "
                   "--port {port_dir} --keep {report_dir}")  # fmt: skip
            argv = [sys.executable, "-m", "gitgalaxy.tools.cobol_to_java.port_runner", "prove", str(rproj), "--ticket", key,
                    "--command", cmd]  # fmt: skip
            proc = subprocess.run(argv, capture_output=True, text=True, check=False, cwd=REPO_ROOT,  # noqa: S603
                                  env={**os.environ, "PYTHONPATH": str(REPO_ROOT)})  # fmt: skip
            print(f"[{run}] {(proc.stdout or proc.stderr).strip().splitlines()[:1]}")
        summary["runs"][run] = {"instrument": RUNS[run], **summarize_run(
            port_runner.events(rproj), t["eligible"], flagged if run == "A" else frozenset())}  # fmt: skip
    (work / f"run_summary{suffix}.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    for run, r in summary["runs"].items():
        print(f"Run {run} ({r['instrument']}): {r['counts']}")
    return 0


# ---- CLI -------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", type=Path, default=LEDGER, help=argparse.SUPPRESS)
    ap.add_argument("--repo", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)  # the engine's git checkout
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("start", help="freeze the system, generate the tickets, declare eligibility")
    st.add_argument("estate")
    st.add_argument("--estate-path", type=Path, required=True)
    st.add_argument("--work", type=Path, required=True, help="where the clean room and the Java project go")
    st.add_argument("--model", required=True)
    st.add_argument("--model-version", help="the model's exact version string (default: --model)")
    st.add_argument("--backend", required=True, choices=("openai", "anthropic", "command", "manual"))
    st.add_argument("--kind", choices=KINDS, default="public")
    st.add_argument("--repo-url", help="a public estate's repository (default: its git origin)")
    st.add_argument("--ref", help="a public estate's commit (default: its git HEAD)")
    st.add_argument("--label", help="a private estate's anonymised label")
    st.add_argument("--exclude", action="append", help="PROGRAM=reason: a declared exclusion (at start only)")
    st.add_argument("--shipped-data", action="append", help="PROGRAM whose input data the estate ships")
    pv = sub.add_parser("preview", help="rehearse the declaration on any estate (burned included); writes no ledger")
    pv.add_argument("estate")
    pv.add_argument("--estate-path", type=Path, required=True)
    pv.add_argument("--work", type=Path, required=True)
    pv.add_argument("--exclude", action="append", help="PROGRAM=reason")
    pv.add_argument("--shipped-data", action="append", help="PROGRAM whose input data the estate ships")
    pv.add_argument("--json", type=Path, help="also write the declaration here")
    pv.add_argument("--page", type=Path, help="also write the estate's harness page (a rehearsal) here")
    pv.add_argument("--case", action="append", help="PROGRAM=CASE: its equivalence case, for the page's inputs/tests")
    pv.add_argument(
        "--proof-blockers", type=Path, help="proof_blockers.py --json output: adds the untranslated programs"
    )
    pv.add_argument("--cases-dir", type=Path, help="where the cases live (default tests/equivalence)")
    sy = sub.add_parser("sync", aliases=["attempt"], help="import the porting loop's log as attempts")
    sy.add_argument("trial")
    sy.add_argument("--project", type=Path, required=True, help="the trial's generated project (port_log.jsonl)")
    cl_help = "PROGRAM=CASE: its equivalence case, for the page's inputs/tests/coverage (kept in the ledger)"
    pb_help = "proof_blockers.py --json: the programs with no translation yet, for the page"
    sy.add_argument("--case", action="append", help=cl_help)
    sy.add_argument("--proof-blockers", type=Path, help=pb_help)
    rc = sub.add_parser("record", help="book a measured run whose port log was not kept (run B, with its fix commits)")
    rc.add_argument("trial")
    rc.add_argument("--summary", type=Path, required=True, help="the run's run_summary.json")
    rc.add_argument("--run", default="B")
    rc.add_argument(
        "--fix", action="append", help="PROGRAM=cause:SHA, the commit that fixed a program run B did not prove"
    )
    rc.add_argument("--at", required=True, help="when the run was made (ISO 8601)")
    cl = sub.add_parser("close", help="end a trial: a program not proven gets its cause")
    cl.add_argument("trial")
    cl.add_argument("--cause", action="append", help=f"PROGRAM=cause ({'|'.join(CAUSES)})")
    cl.add_argument("--withdrawn", metavar="REASON",
                    help="end a trial whose proof phase never ran: a program with no attempt is withdrawn and "
                         "left out of the first-try denominator, instead of counting as a failure")  # fmt: skip
    cl.add_argument("--case", action="append", help=cl_help)
    cl.add_argument("--proof-blockers", type=Path, help=pb_help)
    rp = sub.add_parser("report")
    rp.add_argument("--write", action="store_true")
    sub.add_parser("check")
    vf = sub.add_parser("verify", help="re-check a trial's frozen system (read-only)")
    vf.add_argument("trial")
    vf.add_argument("--no-oracle", action="store_true", help="skip the oracle image check (no docker)")
    vf.add_argument(
        "--rebuild-oracle",
        action="store_true",
        help="also build the oracle Dockerfile fresh (docker, network) and compare it with the local image",
    )
    tk = sub.add_parser("tickets", help="regenerate a trial's tickets at its frozen engine and check them")
    tk.add_argument("trial")
    tk.add_argument("--estate-path", type=Path, required=True)
    tk.add_argument("--work", type=Path, required=True, help="holds the frozen-engine worktree and the project")
    rn = sub.add_parser("run", help="det port per eligible program at the frozen engine, proved under Run A and Run B")
    rn.add_argument("trial")
    rn.add_argument("--estate-path", type=Path, required=True)
    rn.add_argument("--work", type=Path, required=True, help="the `tickets` work dir (frozen-engine, java_h2)")
    rn.add_argument("--runs", default="A,B", type=lambda v: [x for x in v.split(",") if x in RUNS],
                    help="which runs to prove: A (frozen harness), B (current main), default A,B")  # fmt: skip
    rn.add_argument("--backend", choices=("det", "anthropic"), default="det",
                    help="det (default) or the registered model leg, det-then-model: needs the key and spend")  # fmt: skip
    rn.add_argument("--api-key-env", default="ANTHROPIC_API_KEY", help="the NAME of the variable holding the key")
    opts = ap.parse_args(argv)
    if opts.cmd == "run":
        return cmd_run(opts)
    if opts.cmd == "start":
        return cmd_start(opts)
    if opts.cmd == "preview":
        return cmd_preview(opts)
    if opts.cmd in ("sync", "attempt"):
        return cmd_sync(opts)
    if opts.cmd == "record":
        return cmd_record(opts)
    if opts.cmd == "close":
        return cmd_close(opts)
    if opts.cmd == "verify":
        return cmd_verify(opts)
    if opts.cmd == "tickets":
        return cmd_tickets(opts)
    ledger = load(opts.ledger)
    errors = validate(ledger)
    if errors:
        print("trials.json is invalid:\n  " + "\n  ".join(errors))
        return 1
    page, svg = render(ledger), render_svg(ledger)
    if opts.cmd == "report":
        if opts.write:
            PAGE.write_text(page, encoding="utf-8")
            CHART.write_text(svg, encoding="utf-8")
            n = len(write_pages(ledger))
            print(f"wrote {PAGE.relative_to(REPO_ROOT)}, {CHART.relative_to(REPO_ROOT)} and {n} estate pages")
        else:
            sys.stdout.write(page)
        return 0
    for path, text in ((PAGE, page), (CHART, svg)):
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            print(f"{path.relative_to(REPO_ROOT)} is stale: run `python tests/tools/trial.py report --write`")
            return 1
    if stale := stale_pages(ledger):
        print(f"estate pages stale ({', '.join(stale)}): run `python tests/tools/trial.py report --write`")
        return 1
    print("trial ledger: valid, report up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
