#!/usr/bin/env python3
"""#4628: mutation testing of the DET ports, and every survivor accounted for (evidence level L5, #4601).

The evidence ladder's L5 (owner decision on #4601, 2026-10-07) is "L4 + every surviving mutant accounted for":
`tests/tools/mutation.py` (#4047) run on the deterministic translator's port of a case -- the same operators, fast
mode and seeded sample -- and each mutant the proof does not kill either killed by a strengthened scenario or stated
`equivalent` / `unreachable` with its reason, reviewed by the owner (the #4602 pattern).

    python tests/tools/det_mutation.py run CASE [CASE ...] --work DIR [--sample 150] [--seed 0] [--jobs 3]
    python tests/tools/det_mutation.py record CASE RUN_DIR PORT_DIR      # a mutation.py run dir -> the ledger
    python tests/tools/det_mutation.py refresh [CASE ...] --work DIR     # the generator moved: is the port the same?
    python tests/tools/det_mutation.py check                             # the ledgers' form and the claims
    python tests/tools/det_mutation.py table [CASE ...]                  # per program, as the PR table
    python tests/tools/det_mutation.py survivors [CASE ...]              # the survivors and their stated verdicts
    python tests/tools/det_mutation.py state CASE TRIAGE.json            # {id: {verdict, reason}} -> the list

Two committed files:

  tests/equivalence/det_mutation.json -- written only by `run` / `record` / `refresh`: per case the run's counts,
    every judged mutant's verdict, the survivors in full, and the fingerprints of what the score depends on: the det
    port's own files (`port`), the case, the corpus pin, the harness and the oracle (tests/tools/evidence.py's), and
    the Java generator (`generator`), the cheap stand-in for the port: a reader cannot translate. An entry is
    trusted only while every fingerprint matches the tree; stale or missing is unknown (`status` returns None).
    When only the generator moved, `refresh` translates the case again and, when the port is byte-identical,
    renews the generator fingerprint (no mutant re-run).

  tests/equivalence/det_mutation_survivors.json -- written by a person: per case, a surviving mutant (by id, with
    the Java line before / after) and its verdict, `equivalent` (the change cannot alter anything the program
    shows: an initial value overwritten before use, a pad the field's width truncates) or `unreachable` (no input
    gets there: an entry point the case's kind never calls is out of scope already; this is code after a transfer,
    a guard every path has satisfied), and the reason. Proposed in the PR, reviewed by the owner.

    A run that KILLS a stated mutant fails (`record` exits 1 and `check` fails): the claim was wrong, the entry goes.

Scope (`SCOPE`): a det port's service file carries every entry point the translator writes; the ones the case's kind
never calls (a CICS program's runProgram / runBatch) are left out before sampling and counted as out of scope.
The cobolrt runtime is never mutated (tests/cobol_mainframe/test_cobolrt.py checks it against GnuCOBOL).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

CASES = REPO / "tests" / "equivalence"
LEDGER = CASES / "det_mutation.json"
SURVIVORS = CASES / "det_mutation_survivors.json"
FORMAT = "det-mutation/1"
SURVIVORS_FORMAT = "det-mutation-survivors/1"
INPUTS = ("port", "generator", "case", "corpus", "harness", "oracle")
VERDICTS = {
    "equivalent": "the change cannot alter anything the program shows (output, screen, files, COMMAREA, abend)",
    "unreachable": "no input of the program reaches the changed code",
    # triaged but NOT accounted for: the survivor is a real weakness of the proof, kept with what would kill it
    "harness-gap": "the change alters behaviour the proof runs but does not compare (open: the harness must)",
    "case-gap": "an input the case lacks would kill it (open: strengthen the case)",
}
ACCOUNTED = ("equivalent", "unreachable")
FILES = "service/*.java"  # the translated program(s); never the cobolrt runtime
# entry points the case's kind never calls: their mutants are out of scope (not sampled, not scored)
SCOPE = {"cics": ("runProgram", "runBatch", "dd"), "batch": ("runTask", "handleTransaction", "handleLink"),
         "call": ("runTask", "handleTransaction", "handleLink", "runBatch", "dd")}  # fmt: skip
ABOUT = ("#4628: mutation testing of each det port (tests/tools/mutation.py on `det_port.py run --translate-only`'s "
         "port, fast mode, seeded sample), written only by tests/tools/det_mutation.py. An entry is trusted only while "
         "its fingerprints match the tree; stale or missing is unknown. Survivors are accounted for in "
         "det_mutation_survivors.json (reviewed).")  # fmt: skip
SURVIVORS_ABOUT = ("#4628: each surviving det-port mutant stated `equivalent` or `unreachable`, with the Java change and "
                   "why it cannot alter observable behaviour; proposed in a PR, reviewed by the owner. A run that kills a "
                   "stated mutant fails (the claim was wrong). Ids are mutation.py's; before / after are the Java line.")  # fmt: skip


# ---- the det port and its fingerprints ------------------------------------------------------------------------------
def port_sha(port: Path) -> str:
    """sha256 over the det port's .java files (path \\0 bytes \\0, sorted): the port the mutants were cut from."""
    h = hashlib.sha256()
    for f in sorted(port.rglob("*.java")):
        h.update(f.relative_to(port).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def fingerprints(case: str) -> dict[str, str]:
    """The case's input fingerprints in the tree now, but `port` (the det port is not committed: `port_sha`)."""
    import evidence as ev  # (git-backed: only when a ledger is written / read)

    now = ev.compute_inputs(ev.equivalence_target(case))
    return {name: now[name]["sha256"] for name in INPUTS if name != "port"}


def stale(entry: dict[str, Any], now: dict[str, str]) -> list[str]:
    """The inputs (but `port`, which `refresh` checks by translating) whose fingerprint differs from the tree's."""
    return [n for n in INPUTS if n != "port" and (entry.get("inputs") or {}).get(n) != now.get(n)]


def case_kind(case: str) -> str:
    return str(json.loads((CASES / case / "case.json").read_text(encoding="utf-8")).get("kind", "batch"))


def member_spans(text: str, names: tuple[str, ...]) -> list[tuple[int, int]]:
    """(first line, last line), 1-based, of each class member named in `names` (a method: its signature to its
    closing brace)."""
    import mutation as mu

    mask, _ = mu.code_mask(text)
    spans = []
    for m in re.finditer(r"(?m)^    (?:public|private|protected)[^;{=\n]*?\b(\w+)\(", text):
        if m.group(1) not in names:
            continue
        open_at = next((k for k in range(m.end(), len(text)) if mask[k] and text[k] == "{"), None)
        if open_at is None:
            continue
        depth, end = 0, None
        for k in range(open_at, len(text)):
            if not mask[k]:
                continue
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            if depth == 0:
                end = k
                break
        if end is not None:
            spans.append((text.count("\n", 0, m.start()) + 1, text.count("\n", 0, end) + 1))
    return spans


def scope_filter(kind: str, port: Path) -> Callable[[list[Any]], list[Any]]:
    """mutation.run's `select`: drops the mutants inside the entry points `kind` never calls."""
    names = SCOPE.get(kind, ())
    spans = {f.relative_to(port).as_posix(): member_spans(f.read_text(encoding="utf-8"), names)
             for f in port.glob(FILES)}  # fmt: skip

    def select(mutants: list[Any]) -> list[Any]:
        return [m for m in mutants if not any(a <= m.line <= b for a, b in spans.get(m.file, []))]

    return select


# ---- the ledgers -----------------------------------------------------------------------------------------------------
def load(path: Path = LEDGER) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")).get("cases", {}) if path.is_file() else {}


def load_survivors(path: Path = SURVIVORS) -> dict[str, list[dict[str, Any]]]:
    return json.loads(path.read_text(encoding="utf-8")).get("cases", {}) if path.is_file() else {}


def write(cases: dict[str, dict[str, Any]], path: Path = LEDGER) -> None:
    body = {"format": FORMAT, "issue": "#4628", "about": ABOUT, "cases": dict(sorted(cases.items()))}
    path.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")


def stated(case: str, survivors: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, dict[str, Any]]:
    """The case's stated survivors, by mutant id."""
    return {e["id"]: e for e in (load_survivors() if survivors is None else survivors).get(case, [])}


def entry_from_run(case: str, run: dict[str, Any], port: Path, out_of_scope: int) -> dict[str, Any]:
    """A ledger entry from mutation.py's mutation.json (`run`) for the det port `port`."""
    import evidence as ev

    results = run["results"]
    by = {v: [r for r in results if r["verdict"] == v] for v in ("killed", "timeout", "survived", "stillborn",
                                                                  "error", "pending")}  # fmt: skip
    return {
        "program": run.get("program"),
        "commit": ev.harness_commit(),
        "date": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "mode": run.get("mode"),
        "seed": run.get("seed"),
        "mutants": run["mutants"],
        "out_of_scope": out_of_scope,
        "chosen": run["chosen"],
        "coverage": run.get("coverage"),
        "counts": {v: len(rs) for v, rs in by.items()},
        "killed": sorted(r["id"] for r in by["killed"] + by["timeout"]),
        "stillborn": sorted(r["id"] for r in by["stillborn"]),
        "survived": [{k: r[k] for k in ("id", "op", "file", "line", "before", "after")} for r in by["survived"]],
        "inputs": {"port": port_sha(port), **fingerprints(case)},
    }


def refuted(case: str, entry: dict[str, Any], survivors: dict[str, list[dict[str, Any]]] | None = None) -> list[str]:
    """The stated `equivalent` / `unreachable` mutants of `case` the entry's run killed: wrong claims. (A killed
    `case-gap` / `harness-gap` entry is the gap closed: its entry is simply removed.)"""
    killed = set(entry.get("killed", []))
    return sorted(i for i, e in stated(case, survivors).items() if i in killed and e.get("verdict") in ACCOUNTED)


def account(case: str, entry: dict[str, Any], survivors: dict[str, list[dict[str, Any]]] | None = None
            ) -> tuple[list[str], list[str]]:  # fmt: skip
    """(accounted, unaccounted) survivor ids of the entry: a survivor is accounted for by a stated `equivalent` /
    `unreachable` entry with its id and the same Java line before / after (a `harness-gap` / `case-gap` entry is
    triaged, not accounted for)."""
    st = stated(case, survivors)
    ok, open_ = [], []
    for s in entry.get("survived", []):
        e = st.get(s["id"])
        same = e and e.get("before") == s["before"] and e.get("after") == s["after"]
        (ok if same and e["verdict"] in ACCOUNTED else open_).append(s["id"])
    return ok, open_


def summary(case: str, entry: dict[str, Any], survivors: dict[str, list[dict[str, Any]]] | None = None
            ) -> dict[str, Any]:  # fmt: skip
    c = entry["counts"]
    caught = c.get("killed", 0) + c.get("timeout", 0)
    survived = c.get("survived", 0)
    ok, open_ = account(case, entry, survivors)
    judged = caught + survived
    return {"case": case, "program": entry.get("program"), "score": round(caught / judged, 4) if judged else None,
            "killed": caught, "survived": survived, "stillborn": c.get("stillborn", 0), "error": c.get("error", 0),
            "pending": c.get("pending", 0), "accounted": len(ok), "unaccounted": len(open_),
            "chosen": entry.get("chosen"), "mutants": entry.get("mutants"), "seed": entry.get("seed"),
            "refuted": refuted(case, entry, survivors),
            "l5": bool(judged) and not open_ and not c.get("pending") and not c.get("error")
                  and not refuted(case, entry, survivors)}  # fmt: skip


def status(case: str, program: str | None = None) -> dict[str, Any] | None:
    """The evidence report's L5 hook (#4603): the case's det-port mutation result while its ledger entry is fresh,
    else None (missing, stale, or for another program). Keys: score (caught / judged, 0-1), killed (killed +
    timeout), survived, stillborn, accounted / unaccounted (survivors with / without a reviewed verdict), chosen /
    mutants / seed (the sample), refuted (stated mutants the run killed), and l5: every survivor accounted for, no
    error, no refuted claim."""
    entry = load().get(case)
    if not entry or not (CASES / case / "case.json").is_file():
        return None
    if program and entry.get("program") and str(entry["program"]).upper() != program.upper():
        return None
    try:
        if stale(entry, fingerprints(case)):
            return None
    except (RuntimeError, KeyError, OSError):
        return None
    return summary(case, entry)


def describe(s: dict[str, Any] | None) -> str:
    """One line for a report: the raw score beside the accounting (the owner's rule: the raw score always shows)."""
    if s is None:
        return "not measured (no fresh det_mutation.json entry)"
    score = f"{100 * s['score']:.0f}%" if s["score"] is not None else "n/a"
    acc = (f"every survivor accounted for ({s['accounted']})" if s["l5"]
           else f"{s['unaccounted']} of {s['survived']} survivors unaccounted"
           + (f", {len(s['refuted'])} stated claims refuted" if s["refuted"] else ""))  # fmt: skip
    return (f"raw {score} ({s['killed']}/{s['killed'] + s['survived']} caught; {s['chosen']} of {s['mutants']} "
            f"mutants, seed {s['seed']}); {acc}")  # fmt: skip


# ---- the checks ------------------------------------------------------------------------------------------------------
def _tracked(path: Path) -> bool:
    return subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", str(path)],  # noqa: S603, S607
                          capture_output=True, check=False).returncode == 0  # fmt: skip


def problems_in_survivors(survivors: dict[str, list[dict[str, Any]]]) -> list[str]:
    out = []
    for case, entries in sorted(survivors.items()):
        if not (CASES / case / "case.json").is_file():
            out.append(f"det mutation survivors: {case}: no such case")
        seen = set()
        for e in entries:
            missing = [
                f for f in ("id", "op", "line", "before", "after", "verdict", "reason") if e.get(f) in (None, "")
            ]
            if missing:
                out.append(f"det mutation survivors: {case}: an entry lacks {', '.join(missing)}: {e.get('id')}")
                continue
            if e["verdict"] not in VERDICTS:
                out.append(f"det mutation survivors: {case}: {e['id']}: unknown verdict {e['verdict']!r}")
            if e["id"] in seen:
                out.append(f"det mutation survivors: {case}: {e['id']} listed twice")
            seen.add(e["id"])
    return out


def check(ledger: dict[str, dict[str, Any]] | None = None, survivors: dict[str, list[dict[str, Any]]] | None = None,
          tracked: bool = True) -> tuple[list[str], list[str]]:  # fmt: skip
    """(problems, warnings): the files committed, the survivor list's form, and every stated claim against the
    ledger: a stated mutant the ledger's run killed fails; one the run did not judge (another sample, a changed
    port) warns."""
    ledger = load() if ledger is None else ledger
    survivors = load_survivors() if survivors is None else survivors
    problems: list[str] = []
    warnings: list[str] = []
    if tracked:
        problems += [f"det mutation: {f.name} is not a committed file (git-ignored?)" for f in (LEDGER, SURVIVORS)
                     if not f.is_file() or not _tracked(f)]  # fmt: skip
    problems += problems_in_survivors(survivors)
    for case in sorted(ledger):
        if not (CASES / case / "case.json").is_file():
            problems.append(f"det mutation: {case}: no such case any more")
    for case, entries in sorted(survivors.items()):
        entry = ledger.get(case)
        if entry is None:
            warnings.append(f"det mutation survivors: {case}: stated, but no run in the ledger")
            continue
        for i in refuted(case, entry, survivors):
            problems.append(f"det mutation survivors: {case}: {i} is stated {stated(case, survivors)[i]['verdict']}, "
                            f"but the run killed it: the claim is wrong -- remove the entry and say why in the PR")  # fmt: skip
        judged = {s["id"]: s for s in entry.get("survived", [])}
        for e in entries:
            s = judged.get(e["id"])
            if s is None and e["id"] in entry.get("killed", []) and e.get("verdict") not in ACCOUNTED:
                warnings.append(f"det mutation survivors: {case}: {e['id']} ({e['verdict']}) is killed now: drop it")
            elif s is None and e["id"] not in entry.get("killed", []):
                warnings.append(f"det mutation survivors: {case}: {e['id']} not judged by the ledger's run")
            elif s is not None and (s["before"], s["after"]) != (e["before"], e["after"]):
                problems.append(f"det mutation survivors: {case}: {e['id']}: the stated line differs from the run's")
    return problems, warnings


# ---- running ---------------------------------------------------------------------------------------------------------
def translate(cases: list[str], work: Path) -> Path:
    """The det ports of `cases`, translated by this checkout (det_port.py run --translate-only) under work/det."""
    det = work / "det"
    argv = [sys.executable, str(TOOLS / "det_port.py"), "run", *cases, "--translate-only", "--work", str(det)]
    subprocess.run(argv, cwd=REPO, check=True)  # noqa: S603
    return det


def record(case: str, run_dir: Path, port: Path) -> int:
    """Write the case's ledger entry from a mutation.py run directory; 1 when the run killed a stated mutant."""
    import mutation as mu

    run = json.loads((run_dir / "mutation.json").read_text(encoding="utf-8"))
    every = mu.all_mutants(port, set(mu.OPERATORS), FILES)
    in_scope = scope_filter(case_kind(case), port)(every)
    entry = entry_from_run(case, run, port, len(every) - len(in_scope))
    import fcntl  # (POSIX; two runs recording at once must not lose an entry)
    import tempfile

    with (Path(tempfile.gettempdir()) / "gitgalaxy-det-mutation.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cases = {c: e for c, e in load().items() if (CASES / c / "case.json").is_file()}
        cases[case] = entry
        write(cases)
    s = summary(case, entry)
    print(_row(s))
    for i in s["refuted"]:
        print(f"{case}: {i} is stated {stated(case)[i]['verdict']} but this run killed it: the claim is wrong")
    return 1 if s["refuted"] else 0


def run(cases: list[str], work: Path, sample: int | None, seed: int, jobs: int, full: bool) -> int:
    import mutation as mu

    det = translate(cases, work)
    rc = 0
    for case in cases:
        port = det / case / "port"
        if not port.is_dir():
            print(f"{case}: no det port (translation failed: see {det / 'summary.json'})")
            rc = 1
            continue
        mu.run(case, work / case, jobs, sample, seed, set(mu.OPERATORS), None, False, full, port=port, files=FILES,
               select=scope_filter(case_kind(case), port))  # fmt: skip
        rc |= record(case, work / case, port)
    return rc


def refresh(cases: list[str], work: Path) -> int:
    """For each entry stale on the generator only: translate again; the same port bytes renew the fingerprint."""
    ledger = load()
    todo = []
    for case in cases or sorted(ledger):
        entry = ledger.get(case)
        if entry and stale(entry, fingerprints(case)) == ["generator"]:
            todo.append(case)
    if not todo:
        print("det mutation: nothing stale on the generator alone")
        return 0
    det = translate(todo, work)
    rc = 0
    for case in todo:
        port = det / case / "port"
        if port.is_dir() and port_sha(port) == ledger[case]["inputs"]["port"]:
            ledger[case]["inputs"]["generator"] = fingerprints(case)["generator"]
            print(f"{case}: the det port is unchanged: fingerprint renewed")
        else:
            print(f"{case}: the det port changed: re-run (det_mutation.py run {case} --work DIR)")
            rc = 1
    write(ledger)
    return rc


def state(case: str, triage: dict[str, dict[str, str]]) -> int:
    """Write verdicts for the case's surviving mutants into the survivor list, the Java line before / after taken
    from the ledger's run (an id the run did not see survive is refused)."""
    survived = {s["id"]: s for s in (load().get(case) or {}).get("survived", [])}
    unknown = sorted(set(triage) - set(survived))
    if unknown:
        raise SystemExit(f"{case}: not survivors of the ledger's run: {', '.join(unknown)}")
    all_ = load_survivors()
    mine = {e["id"]: e for e in all_.get(case, [])}
    for i, t in triage.items():
        s = survived[i]
        mine[i] = {"id": i, "op": s["op"], "line": s["line"], "before": s["before"], "after": s["after"],
                   "verdict": t["verdict"], "reason": t["reason"]}  # fmt: skip
    all_[case] = sorted(mine.values(), key=lambda e: (e["line"], e["id"]))
    problems = problems_in_survivors({case: all_[case]})
    if problems:
        raise SystemExit("\n".join(problems))
    body = {"format": SURVIVORS_FORMAT, "issue": "#4628", "about": SURVIVORS_ABOUT, "verdicts": VERDICTS,
            "cases": dict(sorted(all_.items()))}  # fmt: skip
    SURVIVORS.write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    s = summary(case, load()[case])
    print(_row(s))
    return 0


# ---- tables ----------------------------------------------------------------------------------------------------------
def _row(s: dict[str, Any]) -> str:
    score = f"{100 * s['score']:.0f}%" if s["score"] is not None else "n/a"
    return (f"| {s['program']} ({s['case']}) | {s['chosen']}/{s['mutants']} (seed {s['seed']}) | {s['killed']} | "
            f"{s['survived']} | {s['stillborn']} | {s['accounted']} | {s['unaccounted']} | "
            f"{s['killed']}/{s['killed'] + s['survived']} ({score}) | {'yes' if s['l5'] else 'no'} |")  # fmt: skip


def table(cases: list[str] | None = None) -> str:
    rows = [("| program (case) | mutants run / in scope | killed | survived | stillborn | stated equivalent / "
             "unreachable | unaccounted | raw score | L5 |"), "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for case, entry in sorted(load().items()):
        if not cases or case in cases:
            rows.append(_row(summary(case, entry)))
    return "\n".join(rows)


def survivors_table(cases: list[str] | None = None) -> str:
    rows = ["| case | mutant | op | Java line, before -> after | verdict | why |", "|---|---|---|---|---|---|"]
    for case, entry in sorted(load().items()):
        if cases and case not in cases:
            continue
        st = stated(case)
        for s in entry.get("survived", []):
            e = st.get(s["id"], {})
            before, after = (x.replace("|", "\\|") for x in (s["before"], s["after"]))
            rows.append(f"| {case} | `{s['id']}` | {s['op']} | {s['line']}: `{before}` -> `{after}` | "
                        f"{e.get('verdict', '**open**')} | {e.get('reason', '')} |")  # fmt: skip
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("cases", nargs="+")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--sample", type=int, default=150, help="mutants per port (default 150; 0: all)")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--jobs", type=int, default=3)
    r.add_argument("--full", action="store_true", help="prove each mutant from scratch (mutation.py --full)")
    rec = sub.add_parser("record")
    rec.add_argument("case")
    rec.add_argument("run_dir", type=Path)
    rec.add_argument("port", type=Path)
    rf = sub.add_parser("refresh")
    rf.add_argument("cases", nargs="*")
    rf.add_argument("--work", type=Path, required=True)
    sub.add_parser("check")
    t = sub.add_parser("table")
    t.add_argument("cases", nargs="*")
    st = sub.add_parser("state")
    st.add_argument("case")
    st.add_argument("triage", type=Path, help="a JSON file {mutant id: {verdict, reason}}")
    sv = sub.add_parser("survivors")
    sv.add_argument("cases", nargs="*")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        return run(args.cases, args.work, args.sample or None, args.seed, args.jobs, args.full)
    if args.cmd == "record":
        return record(args.case, args.run_dir, args.port)
    if args.cmd == "refresh":
        return refresh(args.cases, args.work)
    if args.cmd == "table":
        print(table(args.cases or None))
        return 0
    if args.cmd == "state":
        return state(args.case, json.loads(args.triage.read_text(encoding="utf-8")))
    if args.cmd == "survivors":
        print(survivors_table(args.cases or None))
        return 0
    problems, warnings = check()
    for w in warnings:
        print(f"warning: {w}")
    for p in problems:
        print(p)
    print("det mutation: ok" if not problems else f"det mutation: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
