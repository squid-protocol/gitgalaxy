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
    python tests/tools/trial.py sync  <trial-id> --project W/java_h2     # (alias: attempt) import port_log.jsonl
    python tests/tools/trial.py close <trial-id> [--cause PROG=cause ...]
    python tests/tools/trial.py report [--write]                         # the page + the SVG chart
    python tests/tools/trial.py check                                    # ledger valid, report current (CI)

`start` refuses a development estate (every trialled estate is one), records the frozen system (engine
commit and version, the porting-rules hash, model + backend, the harness commit), runs the same scan ->
refract -> cobol-to-java path the equivalence harness builds its project with (target config h2), which
writes the porting tickets, and declares UP FRONT which programs are eligible and why every other one is
out of scope (ELIGIBILITY_RULES; `--exclude` adds declared exclusions, at start only: the declaration is
hashed, so an exclusion added later to hide a failure fails validation).

Each program is then ported with the porting loop (gitgalaxy/tools/cobol_to_java/port_runner.py run /
prove). `sync` turns its log into attempts: one attempt per proof verdict (or per run that produced no
port), numbered from 1; stopped at the first proven one. An attempt that failed gets its CAUSE from what
happened next: a commit carrying a trailer `Trial-Cause: <ticket|generator|engine|harness> <PROGRAM>`
between the failure and the next attempt is a fix on our side (its cause, its commit); a retry with no
such commit is the model's. `close` ends the trial: a program still not proven gets its cause declared.

Sources: tests/cobol_mainframe/trials.json (the ledger, committed). Writes
docs/language_status/fresh_estate_trials.md and fresh_estate_trials.svg (a plain SVG, no plotting library).
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
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

LEDGER = REPO_ROOT / "tests" / "cobol_mainframe" / "trials.json"
PAGE = REPO_ROOT / "docs" / "language_status" / "fresh_estate_trials.md"
CHART = REPO_ROOT / "docs" / "language_status" / "fresh_estate_trials.svg"

KINDS = ("public", "private")
STATUSES = ("fresh", "development")
OUTCOMES = ("proven", "failed", "no-port", "error")
OUR_CAUSES = ("ticket", "generator", "engine", "harness")  # a fix on our side, with its commit
CAUSES = ("model", *OUR_CAUSES)
BINS = ("@1", "@2", "@3", "@4+")
# The frozen system's harness: the files the proof runs through (tests/tools/equivalence*.py and its image).
HARNESS_PATHS = ("tests/tools/equivalence.py", "tests/tools/equivalence_common.py", "tests/tools/equivalence_java.py",
                 "tests/tools/equivalence_inputs.py", "tests/tools/equivalence_cics.py",
                 "tests/tools/cobol_coverage.py",  # #4023: every COBOL run is traced through it
                 "tests/equivalence/faults/ggfault.c", "tests/equivalence/faults/ggabend.c",  # fault runs, CEE3ABD
                 "tests/equivalence/faults/ggdisplay.c",  # #4056: DISPLAY as IBM writes it
                 "tests/tools/equivalence_call.py", "tests/equivalence/le/ceedays.c",  # CALL cases, LE services
                 "tests/equivalence/gnucobol.Dockerfile")  # fmt: skip
# `Trial-Cause: generator CBACT04C` -- bounded, one trailer per line
_TRAILER = re.compile(r"^Trial-Cause:[ \t]{0,8}([a-z]{1,12})[ \t]{1,8}([A-Za-z0-9$#@_-]{1,64})[ \t]{0,8}$", re.M)
_FINAL = re.compile(
    r"^(proven@[1-9][0-9]{0,3}(\((?:[a-z]{1,12},){0,63}[a-z]{1,12}\))?|not-proven\([a-z]{1,12}\)|open)$"
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


def frozen_system(repo: Path, model: str, backend: str, model_version: Optional[str]) -> dict[str, Any]:
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


_CICS = re.compile(r"\bEXEC[ \t\n]{1,20}CICS\b", re.I)
_SQL = re.compile(r"\bEXEC[ \t\n]{1,20}SQL\b", re.I)
_IMS = re.compile(r"\bEXEC[ \t\n]{1,20}DLI\b|\b(?:CBLTDLI|AIBTDLI)\b", re.I)
_MQ = re.compile(r"\bCALL[ \t\n]{1,20}['\"]MQ[A-Z]{2,8}['\"]", re.I)
_WRITES = {"OUTPUT", "EXTEND", "I-O"}


def _sections(skeleton: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return (skeleton.get("sections", {}).get(name) or {}).get("facts") or []


def out_of_scope_reason(skeleton: dict[str, Any], text: str, shipped: bool) -> Optional[str]:
    """Why the equivalence harness cannot run a program (None: eligible). The batch harness runs a COBOL
    program under GnuCOBOL with a driver, loads its input files (generated from their copybook layouts,
    #3804, or shipped) and compares its output files record by record -- so the program must be batch COBOL
    with no database, IMS or MQ side, write at least one file, and have a record layout for every input."""
    for rule, reason in ELIGIBILITY_RULES:
        if rule(skeleton, text, shipped):
            return reason
    return None


def _not_cobol(sk: dict[str, Any], _t: str, _s: bool) -> bool:
    return (sk.get("program", {}).get("language") or "").lower() != "cobol"


def _no_output(sk: dict[str, Any], _t: str, _s: bool) -> bool:
    return not any(_WRITES & set(d.get("modes") or []) for d in _sections(sk, "datasets"))


def _input_without_layout(sk: dict[str, Any], _t: str, shipped: bool) -> bool:
    if shipped:
        return False
    reads = {d.get("internal_name") for d in _sections(sk, "datasets") if {"INPUT", "I-O"} & set(d.get("modes") or [])}
    return any(fc.get("select_name") in reads and not fc.get("fd_copies") for fc in _sections(sk, "file_control"))


ELIGIBILITY_RULES = (
    (_not_cobol, "not COBOL: the harness compiles the program with GnuCOBOL"),
    (lambda _k, t, _s: bool(_CICS.search(t)), "online (EXEC CICS): the batch harness does not run CICS tasks"),
    (lambda _k, t, _s: bool(_SQL.search(t)), "DB2 (EXEC SQL): the harness has no database side"),
    (lambda _k, t, _s: bool(_IMS.search(t)), "IMS (DL/I): the harness has no IMS side"),
    (lambda _k, t, _s: bool(_MQ.search(t)), "MQ calls: the harness has no queue manager"),
    (_no_output, "writes no file: the harness has no output records to compare"),
    (_input_without_layout, "an input file with no copybook record layout: its records cannot be generated (#3804)"),
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
            sk, _text_of(estate, [prog.get("file"), *prog.get("copybooks", [])]), key in shipped
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


def _estate(ledger: dict[str, Any], estate_id: str) -> Optional[dict[str, Any]]:
    return next((e for e in ledger["estates"] if e["id"] == estate_id), None)


def _trial(ledger: dict[str, Any], trial_id: str) -> dict[str, Any]:
    t = next((t for t in ledger["trials"] if t["id"] == trial_id), None)
    if t is None:
        raise SystemExit(f"no trial {trial_id}")
    return t


def final_of(attempts: list[dict[str, Any]], closed_cause: Optional[str] = None) -> str:
    """proven@N (with the causes of the failures before it) | not-proven(cause) | open."""
    for a in attempts:
        if a["outcome"] == "proven":
            causes = [str(b["cause"]) for b in attempts[: a["n"] - 1]]
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
    errors = []
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
            if a.get("cause") is not None and a.get("cause") not in CAUSES:
                errors.append(f"{key} attempt {a.get('n')}: cause must be one of {CAUSES} or null")
            if a.get("outcome") == "proven" and a.get("cause") is not None:
                errors.append(f"{key} attempt {a.get('n')}: a proven attempt has no failure cause")
            if bool(a.get("fix_commit")) != (a.get("cause") in OUR_CAUSES):
                errors.append(f"{key} attempt {a.get('n')}: a fix commit goes with a cause on our side, and only there")
        if any(a["outcome"] == "proven" for a in attempts[:-1]):
            errors.append(f"{key}: attempts stop at the first proven one")
        if any(a.get("cause") is None for a in attempts[:-1]):
            errors.append(f"{key}: every failed attempt before the last carries its cause")
        final = str(p.get("final"))
        if not _FINAL.match(final):
            errors.append(f"{key}: final must be proven@N | not-proven(cause) | open")
        elif final.startswith("not-proven"):
            if final[len("not-proven(") : -1] not in CAUSES or not t.get("closed"):
                errors.append(f"{key}: not-proven(cause) needs a known cause and a closed trial")
        elif final != final_of(attempts):
            errors.append(f"{key}: final {final} does not follow from its attempts ({final_of(attempts)})")
        if t.get("closed") and final == "open":
            errors.append(f"{key}: a closed trial leaves no program open")
    return errors


# ---- start -----------------------------------------------------------------------------
def _parse_pairs(items: Optional[list[str]], what: str) -> dict[str, str]:
    out = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise SystemExit(f"{what} takes PROGRAM=value, not {item!r}")
        out[key.strip()] = value.strip()
    return out


def _estate_git(path: Path, *args: str) -> Optional[str]:
    argv = ["git", "-C", str(path), *args]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603, S607
    return proc.stdout.strip() or None if proc.returncode == 0 else None


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

    import java_target_matrix as jtm  # the path the equivalence harness builds its project with

    work = opts.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    clean = jtm.refactor(path, work, scan=True)
    project = jtm.generate(clean, "h2", jtm.MATRIX["h2"], work)
    eligible, out = declare(clean, project, path, excludes, set(opts.shipped_data or []))
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
    print(f"{trial_id}: {opts.estate} at engine {system['engine_version']} ({system['engine_commit'][:10]}), "
          f"{len(eligible)} eligible, {len(out)} out of scope; tickets in {project / 'ai_agent_jobs'}")  # fmt: skip
    print(f"  eligible: {', '.join(eligible) or '(none)'}")
    print(f"  per program: python -m gitgalaxy.tools.cobol_to_java.port_runner run {project} --ticket PROG "
          f"--backend {opts.backend} --model {opts.model} ...; then `port_runner prove` (the equivalence harness); "
          f"then python tests/tools/trial.py sync {trial_id} --project {project}")  # fmt: skip
    return 0


# ---- sync: the porting loop's log -> attempts ----------------------------------------------
def attempts_from_log(events: list[dict[str, Any]], key: str, fixes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One attempt per proof verdict (or per run that produced no port), in log order, stopped at the first
    proven. A proposed port superseded by another run before any proof is an `error` attempt (never proved).
    A failed attempt's cause: the last Trial-Cause commit for this program between its verdict and the next
    attempt's start (ours, with the commit), else `model` when another attempt followed, else still null."""
    raw: list[dict[str, Any]] = []  # {outcome, began, at, model}
    pending: Optional[dict[str, Any]] = None
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
                        "at": at, "model": base.get("model")})  # fmt: skip
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
            elif i + 1 < len(raw):
                cause = "model"
        out.append({"n": i + 1, "outcome": r["outcome"], "cause": cause, "fix_commit": commit, "at": r["at"],
                    "model": r["model"]})  # fmt: skip
    return out


def sync(trial: dict[str, Any], events: list[dict[str, Any]], fixes: list[dict[str, Any]]) -> dict[str, int]:
    """Import the log into the trial (idempotent). Attempts already recorded never change -- only a null
    cause may be filled in once the next attempt or a fix arrives. {program: attempts} of what changed."""
    if trial.get("closed"):
        raise SystemExit(f"{trial['id']} is closed")
    changed = {}
    for key, p in trial["programs"].items():
        new = attempts_from_log(events, key, fixes)
        for old, now in zip(p["attempts"], new):
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


def cmd_sync(opts: argparse.Namespace) -> int:
    from gitgalaxy.tools.cobol_to_java import port_runner

    ledger = load(opts.ledger)
    trial = _trial(ledger, opts.trial)
    changed = sync(
        trial, port_runner.events(opts.project.resolve()), fix_commits(opts.repo, trial["system"]["engine_commit"])
    )
    problems = validate(ledger)
    if problems:
        raise SystemExit("the ledger would be invalid:\n  " + "\n  ".join(problems))
    save(ledger, opts.ledger)
    for key in trial["programs"]:
        print(f"  {key}: {trial['programs'][key]['final']}" + ("  (updated)" if key in changed else ""))
    return 0


def close(trial: dict[str, Any], causes: dict[str, str]) -> None:
    for key, p in trial["programs"].items():
        if p["final"] != "open":
            continue
        last = p["attempts"][-1]["cause"] if p["attempts"] else None
        cause = causes.get(key) or last
        if cause not in CAUSES:
            raise SystemExit(f"{key} is not proven: declare its cause with --cause {key}=<{'|'.join(CAUSES)}>")
        p["final"] = f"not-proven({cause})"
    trial["closed"] = _today()


def cmd_close(opts: argparse.Namespace) -> int:
    ledger = load(opts.ledger)
    close(_trial(ledger, opts.trial), _parse_pairs(opts.cause, "--cause"))
    problems = validate(ledger)
    if problems:
        raise SystemExit("the ledger would be invalid:\n  " + "\n  ".join(problems))
    save(ledger, opts.ledger)
    print(f"{opts.trial}: closed")
    return 0


# ---- report ----------------------------------------------------------------------------
def _bin(final: str) -> Optional[str]:
    """The histogram bin of a final state (None: still open)."""
    if final.startswith("proven@"):
        n = int(re.split(r"[@(]", final)[1])
        return BINS[min(n, 4) - 1]
    if final.startswith("not-proven("):
        return "not proven: " + final[len("not-proven(") : -1]
    return None


COLUMNS = (*BINS, *[f"not proven: {c}" for c in CAUSES])


def _counted(trial: dict[str, Any], p: dict[str, Any]) -> bool:
    """A program counts toward the rate once its first attempt has a verdict, or its trial is closed."""
    return bool(p["attempts"]) or bool(trial.get("closed"))


def summary(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per engine version (in trial order): trials, estates, first-try proven / counted, and the bins."""
    out: dict[str, dict[str, Any]] = {}
    for t in ledger["trials"]:
        v = out.setdefault(t["system"]["engine_version"], {"trials": [], "estates": [], "first": 0, "counted": 0,
                                                           "open": 0, "bins": {}})  # fmt: skip
        v["trials"].append(t["id"])
        if t["estate"] not in v["estates"]:
            v["estates"].append(t["estate"])
        for p in t["programs"].values():
            b = _bin(p["final"])
            if _counted(t, p):
                v["counted"] += 1
                v["first"] += p["final"] == "proven@1"
            if b is None:
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
    rate = f"{100 * v['first'] / v['counted']:.0f}%" if v["counted"] else "-"
    n = len(v["estates"])
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
           "first attempt has a verdict (and every program of a closed trial).", "",
           *[f"- {c}" for c in CAVEATS], "", "![attempts to proof](fresh_estate_trials.svg)", "",
           "## Trials", ""]  # fmt: skip
    if not ledger["trials"]:
        out += ["No trial yet."]
    else:
        out += ["| trial | estate | kind | started | closed | engine | model | eligible | out of scope | "
                + " | ".join(COLUMNS) + " | open |",
                "|" + "---|" * (9 + len(COLUMNS) + 1)]  # fmt: skip
        for t in ledger["trials"]:
            bins: dict[str, int] = {}
            for p in t["programs"].values():
                b = _bin(p["final"]) or "open"
                bins[b] = bins.get(b, 0) + 1
            kind = (_estate(ledger, t["estate"]) or {}).get("kind", "?")
            sysm = t["system"]
            out.append(f"| {t['id']} | {_name(ledger, t['estate'])} | {kind} | {t['started']} | "
                       f"{t.get('closed') or '-'} | {sysm['engine_version']} | "
                       f"{sysm['model_version']} ({sysm['backend']}) | "
                       f"{len(t['eligible'])} | {len(t['out_of_scope'])} | "
                       + " | ".join(str(bins.get(c, 0)) for c in (*COLUMNS, "open")) + " |")  # fmt: skip
        out += ["", "## Programs", "", "| trial | program | final | attempts (outcome/cause) |", "|---|---|---|---|"]
        for t in ledger["trials"]:
            for key, p in sorted(t["programs"].items()):
                steps = ", ".join(f"{a['n']}:{a['outcome']}" + (f"/{a['cause']}" if a["cause"] else "")
                                  + (f" {a['fix_commit'][:10]}" if a["fix_commit"] else "")
                                  for a in p["attempts"])  # fmt: skip
                out.append(f"| {t['id']} | {key} | {p['final']} | {steps or '-'} |")
            for key, reason in sorted(t["out_of_scope"].items()):
                out.append(f"| {t['id']} | {key} | out-of-scope({reason.replace('|', '/')}) | - |")
    out += ["", "## Estates", "", "| estate | kind | status | repo @ ref | trialled by |", "|---|---|---|---|---|"]
    for e in ledger["estates"]:
        where = f"{e['repo']} @ {e['ref'][:12]}" if e["kind"] == "public" else "(private)"
        out.append(
            f"| {_name(ledger, e['id'])} | {e['kind']} | {e['status']} | {where} | {e.get('trialled_by') or '-'} |"
        )
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


# ---- CLI -------------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
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
    sy = sub.add_parser("sync", aliases=["attempt"], help="import the porting loop's log as attempts")
    sy.add_argument("trial")
    sy.add_argument("--project", type=Path, required=True, help="the trial's generated project (port_log.jsonl)")
    cl = sub.add_parser("close", help="end a trial: a program not proven gets its cause")
    cl.add_argument("trial")
    cl.add_argument("--cause", action="append", help=f"PROGRAM=cause ({'|'.join(CAUSES)})")
    rp = sub.add_parser("report")
    rp.add_argument("--write", action="store_true")
    sub.add_parser("check")
    opts = ap.parse_args(argv)
    if opts.cmd == "start":
        return cmd_start(opts)
    if opts.cmd in ("sync", "attempt"):
        return cmd_sync(opts)
    if opts.cmd == "close":
        return cmd_close(opts)
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
            print(f"wrote {PAGE.relative_to(REPO_ROOT)} and {CHART.relative_to(REPO_ROOT)}")
        else:
            sys.stdout.write(page)
        return 0
    for path, text in ((PAGE, page), (CHART, svg)):
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            print(f"{path.relative_to(REPO_ROOT)} is stale: run `python tests/tools/trial.py report --write`")
            return 1
    print("trial ledger: valid, report up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
