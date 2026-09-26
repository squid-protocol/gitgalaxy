"""
The mainframe ground-truth ledger: every place the engine or the forge disagrees
with a hand-verified answer key, each one explained, owned by an issue, and gated.

`cobol_answer_key.py score` measures the engine master DB and the refraction
("forge") tools against tests/cobol_mainframe/answer_key/, one (program, value)
pair at a time. That score used to be a table someone had to remember to run; a
precision drop could sit on main unnoticed. This tool pins it.

tests/cobol_mainframe/ground_truth_ledger.json records, per keyed corpus:

  scoreboard   P/R counts per field and side, plus whether the field's truth is
               `validated` or still a `draft` (see TRUTH FLAGS below)
  mismatches   one entry per disagreeing pair --
                 "<side> | <field> | <program> | <value> | fp|fn"  ->  cause
               fp = the side reported a value the key does not have,
               fn = the key has a value the side missed
  causes       cause -> {"kind": "defect"|"deliberate", "issue": N, "summary": "..."}.
               A `defect` is something to fix, owned by the issue that fixes it. A
               `deliberate` difference is by design (the side does not claim what
               the key measures); its issue is the one recording that decision.
               The report counts the two apart, so deliberate entries never read
               as accuracy lost, and a defect can't hide as a deliberate one
               without a reviewer seeing the kind change.

CHECK (what CI runs) fails when:
  - a mismatch is not in the ledger                   (a regression, or an unexplained delta)
  - a ledger entry no longer reproduces               (an improvement: ratchet it in with `update`)
  - an entry is UNTRIAGED or names an unknown cause
  - a cause has no issue, no valid kind, or no entry uses it
  - the scoreboard differs from the measured counts
Corpora without an answer key are reported as pending and do not gate.

    python tests/tools/ground_truth_ledger.py check [--summary out.md] [--history]
    python tests/tools/ground_truth_ledger.py update          # re-measure; keeps causes, new entries UNTRIAGED
    python tests/tools/ground_truth_ledger.py assign CAUSE 'PATTERN' ... [--kind defect|deliberate --issue N --summary TEXT]
    python tests/tools/ground_truth_ledger.py list [--untriaged] [--corpus NAME]

PATTERN is an fnmatch glob over "<corpus> :: <entry>", e.g.
    'cics-banking-sample-application-cbsa :: engine | dead* | fp'

The corpora must be fetched first: `mainframe_corpus.py fetch`. Scans are cached
per engine state, so a re-run on an unchanged engine only re-scores (seconds).

TRUTH TIERS. Each scoreboard field is labelled with the weakest verification tier
behind it: `sample_verified` < `llm_verified` < `cross_verified` < `human_signed`
(cobol_answer_key.TIERS; `sample_verified` = a blind census of a stratified SAMPLE,
for sections too large to read whole -- cross_verify_sections.py `lineage`),
or `draft` when a section's own sign-off flag (TRUTH_FLAGS) is not yet set -- this
tool's own reading, not truth. Every tier gates: a mismatch against draft truth
still means the engine's output changed and someone must say why. The label only
decides how strongly a number may be quoted.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mainframe_corpus as mc  # noqa: E402

REPO_ROOT = mc.REPO_ROOT
LEDGER = REPO_ROOT / "tests" / "cobol_mainframe" / "ground_truth_ledger.json"
HISTORY = REPO_ROOT / "docs" / "self_scan" / "ground_truth_history.jsonl"
UNTRIAGED = "UNTRIAGED"
KINDS = ("defect", "deliberate")
SIDES = ("engine", "forge")

# field -> (key section, per-entry sign-off flag). Fields not listed are backed by
# the program blocks' `verification.status`, which test_key_integrity requires to
# be `validated`.
TRUTH_FLAGS: dict[str, tuple[str, str]] = {
    "record fields": ("programs", "records_validated"),
    "entry transactions": ("programs", "transactions_validated"),
    "PL/I record fields": ("pli_programs", "records_validated"),
    "DB2 table columns": ("sql_tables", "sql_tables_validated"),
    "DB2 table access": ("sql_access", "sql_access_validated"),
    "BMS screen fields": ("bms_maps", "fields_validated"),
    "JCL resolved DSNs": ("jcl_jobs", "dsns_validated"),
    "CSD resources": ("csd_decks", "resources_validated"),
    "CICS resources": ("cics_resources", "cics_validated"),
    "CICS task control": ("cics_tasks", "cics_tasks_validated"),
    "async children": ("cics_tasks", "cics_tasks_validated"),
    "job submissions": ("job_submissions", "submissions_validated"),
    "MQ calls": ("mq_calls", "mq_validated"),
    "units of work and handlers": ("uow_handlers", "uow_validated"),
    "TD trigger starts": ("tdq_triggers", "tdq_triggers_validated"),
    "file control": ("file_control", "file_control_validated"),
    "VSAM defines": ("vsam_defines", "vsam_validated"),
    "JCL job flow": ("job_flow", "jobflow_validated"),
    "CALL USING": ("call_using", "call_using_validated"),
    "DL/I calls": ("dli_calls", "dli_validated"),
    "IMS segment access": ("dli_calls", "dli_validated"),
    "IMS definitions": ("ims_gen", "ims_gen_validated"),
    "IMS access check": ("ims_gen", "ims_gen_validated"),
    "data moves": ("data_moves", "data_moves_validated"),
    "MOVE truncation": ("data_moves", "data_moves_validated"),
    "symbolic maps": ("symbolic_maps", "symbolic_validated"),
    "copybook layouts": ("copybook_layouts", "layouts_validated"),
    "PL/I layouts": ("pli_layouts", "pli_layouts_validated"),
    "CICS RIDFLD": ("cics_ridflds", "ridflds_validated"),
    "refmod spans": ("refmod_spans", "refmods_validated"),
    "dynamic call targets": ("dynamic_targets", "dynamic_validated"),
    "web services": ("web_services", "web_validated"),
    "JCICS": ("jcics", "jcics_validated"),
    "PL/I call sites": ("pli_calls", "pli_calls_validated"),
    "PL/I data moves": ("pli_moves", "pli_moves_validated"),
    "file I/O moves": ("io_moves", "io_moves_validated"),
}


TIERS = (
    "sample_verified",
    "llm_verified",
    "cross_verified",
    "human_signed",
)  # == cobol_answer_key.TIERS, weakest first


def _weakest(tiers: list[str]) -> str:
    return min(tiers, key=TIERS.index) if tiers else "draft"


def truth_tier(key: dict[str, Any], field: str) -> str:
    """The weakest verification tier behind `field` (see cobol_answer_key.TIERS), or
    `draft` when any entry backing it is not signed off."""
    if field not in TRUTH_FLAGS:
        vs = [p["verification"] for p in key["programs"].values()]
        if not vs or any(v["status"] != "validated" for v in vs):
            return "draft"
        return _weakest([v.get("tier", "llm_verified") for v in vs])
    section, flag = TRUTH_FLAGS[field]
    entries = list(key.get(section, {}).values())
    if not entries or any(e.get(flag) is not True for e in entries):
        return "draft"
    # A section sign-off flag carries no tier of its own: it inherits the entry's
    # verification tier when present, else the one-model floor -- unless the flag
    # names its own (`<flag>_tier`, #3575: program records signed by a SAMPLED census
    # while the program block itself is cross_verified).
    return _weakest(
        [e.get(f"{flag}_tier") or (e.get("verification") or {}).get("tier", "llm_verified") for e in entries]
    )


def entry_key(side: str, field: str, pair: list[str], kind: str) -> str:
    return f"{side} | {field} | {pair[0]} | {pair[1]} | {kind}"


def measure(corpus: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """(scoreboard, mismatch entry keys) for one keyed corpus at the current engine."""
    result, _md = mc.score(corpus)
    key = json.loads((REPO_ROOT / corpus["answer_key"]).read_text(encoding="utf-8"))
    board: dict[str, Any] = {}
    entries: set[str] = set()
    for field, sides in result["fields"].items():
        row: dict[str, Any] = {"truth": truth_tier(key, field)}
        for side in SIDES:
            s = sides.get(side)
            if s is None:
                row[side] = None
                continue
            row[side] = {"tp": s["tp"], "got": s["got"], "truth": s["truth"]}
            for kind in ("fp", "fn"):
                entries.update(entry_key(side, field, pair, kind) for pair in s[kind])
        board[field] = row
    return board, entries


def keyed(corpora: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in corpora if c.get("answer_key")]


def load_ledger(path: Path = LEDGER) -> dict[str, Any]:
    if not path.is_file():
        return {"causes": {}, "corpora": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_ledger(ledger: dict[str, Any], path: Path = LEDGER) -> None:
    ledger = {"about": ABOUT, **{k: v for k, v in ledger.items() if k != "about"}}
    # write_bytes: LF on every OS
    path.write_bytes((json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode())


ABOUT = (
    "Mainframe ground-truth ledger (tests/tools/ground_truth_ledger.py). Every engine/forge "
    "disagreement with a hand-verified answer key, keyed '<side> | <field> | <program> | <value> | fp|fn' "
    "-> cause; every cause has a kind (defect|deliberate) and names its owning issue. CI fails on an unlisted mismatch, a listed one that no "
    "longer reproduces, an UNTRIAGED entry, a cause without an issue, or a stale scoreboard. Re-measure "
    "with `update`, triage with `assign`."
)


def _pr(s: Optional[dict[str, int]]) -> str:
    if s is None:
        return "n/a"
    return f"P {s['tp']}/{s['got']} · R {s['tp']}/{s['truth']}"


def check(
    ledger: dict[str, Any], measured: dict[str, tuple[dict[str, Any], set[str]]], pending: list[str]
) -> tuple[list[str], str]:
    """(violations, markdown report). `measured` maps corpus name -> measure()."""
    problems: list[str] = []
    causes = ledger.get("causes", {})
    used: set[str] = set()
    md = ["## Mainframe ground truth", ""]
    for name, (board, entries) in measured.items():
        rec = ledger.get("corpora", {}).get(name, {"scoreboard": {}, "mismatches": {}})
        listed = rec.get("mismatches", {})
        new = sorted(entries - listed.keys())
        fixed = sorted(listed.keys() - entries)
        for e in new:
            problems.append(f"{name}: NEW mismatch (regression or unexplained): {e}")
        for e in fixed:
            problems.append(f"{name}: no longer reproduces (ratchet it in with `update`): {e}")
        for e, cause in sorted(listed.items()):
            if e not in entries:
                continue
            used.add(cause)
            if cause == UNTRIAGED:
                problems.append(f"{name}: UNTRIAGED: {e}")
            elif cause not in causes:
                problems.append(f"{name}: unknown cause {cause!r}: {e}")
        if rec.get("scoreboard") != board:
            problems.append(f"{name}: scoreboard differs from the measured counts (run `update`)")

        md += [f"### {name}", "", "| field | truth | engine | forge |", "|---|---|---|---|"]
        prev = rec.get("scoreboard", {})
        for field, row in board.items():
            cells = []
            for side in SIDES:
                cell = _pr(row[side])
                before = (prev.get(field) or {}).get(side)
                if before != row[side] and prev:
                    cell += f" (was {_pr(before)})"
                cells.append(cell)
            md.append(f"| {field} | {row['truth']} | {cells[0]} | {cells[1]} |")
        md.append("")
        by_cause: dict[str, int] = {}
        for e in entries & listed.keys():
            by_cause[listed[e]] = by_cause.get(listed[e], 0) + 1
        if by_cause:
            md += ["| cause | kind | issue | mismatches |", "|---|---|---|---|"]
            for cause, n in sorted(by_cause.items(), key=lambda kv: -kv[1]):
                meta = causes.get(cause, {})
                issue = meta.get("issue")
                md.append(f"| `{cause}` | {meta.get('kind', '—')} | {f'#{issue}' if issue else '—'} | {n} |")
            defects = sum(n for c, n in by_cause.items() if causes.get(c, {}).get("kind") == "defect")
            md += ["", f"{defects} of {sum(by_cause.values())} mismatches are open defects."]
            md.append("")
        if new or fixed:
            md.append(f"**{len(new)} new, {len(fixed)} no longer reproducing.**")
            md += ["", "```", *[f"+ {e}" for e in new[:50]], *[f"- {e}" for e in fixed[:50]], "```", ""]
    for cause, meta in sorted(causes.items()):
        if not meta.get("issue"):
            problems.append(f"cause {cause!r} has no owning issue")
        if meta.get("kind") not in KINDS:
            problems.append(f"cause {cause!r} has kind {meta.get('kind')!r}, expected one of {KINDS}")
        if cause not in used:
            problems.append(f"cause {cause!r} is used by no mismatch (remove it)")
    if pending:
        md += [f"Pending (no answer key yet, not gated): {', '.join(pending)}", ""]
    md.append(f"**{len(problems)} ledger violation(s).**" if problems else "Ledger clean.")
    return problems, "\n".join(md) + "\n"


def update(ledger: dict[str, Any], measured: dict[str, tuple[dict[str, Any], set[str]]]) -> dict[str, int]:
    """Re-measure in place: keep each surviving entry's cause, add new ones UNTRIAGED,
    drop fixed ones and causes nothing uses any more. Returns counts."""
    counts = {"added": 0, "removed": 0}
    corpora = ledger.setdefault("corpora", {})
    for name, (board, entries) in measured.items():
        rec = corpora.setdefault(name, {})
        old = rec.get("mismatches", {})
        counts["added"] += len(entries - old.keys())
        counts["removed"] += len(old.keys() - entries)
        rec["scoreboard"] = board
        rec["mismatches"] = {e: old.get(e, UNTRIAGED) for e in sorted(entries)}
    for name in list(corpora):
        if name not in measured:
            del corpora[name]
    used = {c for rec in corpora.values() for c in rec["mismatches"].values()}
    ledger["causes"] = {c: m for c, m in ledger.get("causes", {}).items() if c in used}
    return counts


def assign(
    ledger: dict[str, Any],
    cause: str,
    patterns: list[str],
    issue: Optional[int] = None,
    summary: Optional[str] = None,
    kind: Optional[str] = None,
) -> int:
    causes = ledger.setdefault("causes", {})
    if issue is not None or summary is not None or kind is not None:
        meta = causes.setdefault(cause, {})
        for k, v in (("issue", issue), ("summary", summary), ("kind", kind)):
            if v is not None:
                meta[k] = v
    elif cause not in causes and cause != UNTRIAGED:
        sys.exit(f"unknown cause {cause!r}; create it with --kind K --issue N --summary TEXT")
    n = 0
    for name, rec in ledger.get("corpora", {}).items():
        for e in rec["mismatches"]:
            if any(fnmatch.fnmatchcase(f"{name} :: {e}", p) for p in patterns):
                rec["mismatches"][e] = cause
                n += 1
    return n


def _commit() -> str:
    try:
        return subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def history_rows(measured: dict[str, tuple[dict[str, Any], set[str]]]) -> list[dict[str, Any]]:
    rows = []
    for name, (board, _entries) in measured.items():
        for field, row in board.items():
            for side in SIDES:
                if row[side] is not None:
                    rows.append({"corpus": name, "field": field, "side": side, "truth_tier": row["truth"], **row[side]})
    return rows


def append_history(rows: list[dict[str, Any]], path: Path = HISTORY) -> bool:
    """Appends one batch unless it equals the last one (so a push that moves no
    number writes nothing). Returns whether it wrote."""
    last: list[dict[str, Any]] = []
    if path.is_file():
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines:
            stamp = lines[-1]["commit"]
            last = [{k: v for k, v in r.items() if k not in ("date", "commit")} for r in lines if r["commit"] == stamp]
    if last == rows:
        return False
    meta = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "commit": _commit()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        for r in rows:
            fh.write((json.dumps({**meta, **r}, sort_keys=True) + "\n").encode())
    return True


def measure_all(names: list[str]) -> tuple[dict[str, tuple[dict[str, Any], set[str]]], list[str]]:
    corpora = mc.select(names)
    pending = [c["name"] for c in corpora if not c.get("answer_key")]
    return {c["name"]: measure(c) for c in keyed(corpora)}, pending


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--summary", type=Path, help="write the markdown report here (e.g. $GITHUB_STEP_SUMMARY)")
    c.add_argument("--history", action="store_true", help=f"append the scoreboard to {HISTORY.relative_to(REPO_ROOT)}")
    sub.add_parser("update")
    a = sub.add_parser("assign")
    a.add_argument("cause")
    a.add_argument("patterns", nargs="+")
    a.add_argument("--issue", type=int)
    a.add_argument("--summary")
    a.add_argument("--kind", choices=KINDS)
    ls = sub.add_parser("list")
    ls.add_argument("--untriaged", action="store_true")
    ls.add_argument("--corpus")
    args = ap.parse_args()

    ledger = load_ledger()
    if args.cmd == "assign":
        n = assign(ledger, args.cause, args.patterns, args.issue, args.summary, args.kind)
        save_ledger(ledger)
        print(f"assigned {n} entr{'y' if n == 1 else 'ies'} to {args.cause}")
        return 0
    if args.cmd == "list":
        for name, rec in ledger.get("corpora", {}).items():
            if args.corpus and name != args.corpus:
                continue
            for e, cause in rec["mismatches"].items():
                if not args.untriaged or cause == UNTRIAGED:
                    print(f"{name} :: {e}  ->  {cause}")
        return 0

    measured, pending = measure_all([])
    if args.cmd == "update":
        counts = update(ledger, measured)
        save_ledger(ledger)
        untriaged = sum(v == UNTRIAGED for r in ledger["corpora"].values() for v in r["mismatches"].values())
        print(f"ledger updated: +{counts['added']} -{counts['removed']}, {untriaged} untriaged")
        return 0

    problems, md = check(ledger, measured, pending)
    print(md)
    for p in problems:
        print(f"::error title=Ground-truth ledger::{p}" if os.environ.get("GITHUB_ACTIONS") else f"FAIL {p}")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as fh:
            fh.write(md)
    if args.history and not problems:
        wrote = append_history(history_rows(measured))
        print("history appended" if wrote else "history unchanged")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
