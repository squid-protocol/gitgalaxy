#!/usr/bin/env python3
"""#4602: branch outcomes no input can reach, stated per equivalence case -- reviewed, never hidden.

The strict bar (proof_blockers.py --branches) asks every counted branch outcome of a program to run. Some cannot:
a guard every caller has already satisfied, a WHEN on a constant table or a bounded loop index. cobol_coverage.py
sets apart only what control flow alone shows (after a GO TO / XCTL / RETURN ...: `after_transfer`); a data-flow
fact like these is stated here instead, by a person, with its reason:

    tests/equivalence/infeasible_outcomes.json
    {"format": "infeasible-outcomes/1", "issue": "#4602", "about": ...,
     "cases": {CASE: [{"unit": PARAGRAPH, "line": N, "kind": "IF"|"EVALUATE", "outcome": "true"|"false"|"WHEN@N"|
                       "OTHER"|"none", "family": "G"|"C"|"R", "reason": WHY NO INPUT REACHES IT, citing the COBOL}]}}

`line` is the original program's line (the case's program_source), as cobol_coverage reports it. The entries are
assumptions of the proof, the same standing as the `unreachable` verdict in docs/language_status/mutation_scores.json:
proposed by whoever finds them, reviewed by the owner in the PR that adds them, shown in the evidence report as stated
assumptions (`stated(case)`).

How they are used:
  - proof_blockers.py subtracts a case's entries from its branch total when the proof left them uncovered, and prints
    them; an entry the proof COVERED refutes the claim and is a gap of its own ("infeasible outcome reached").
  - proof_sweep.py fails a sweep whose proof of a case reached one of the case's entries (`check`): the claim was
    wrong, and the entry goes, with what it was learned from.

    python tests/tools/infeasible_outcomes.py show [CASE ...]       # the entries, as the PR table
    python tests/tools/infeasible_outcomes.py check SWEEP [SWEEP ...] # against proof_sweep.py --det-only work dirs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
CASES = REPO / "tests" / "equivalence"
LEDGER = CASES / "infeasible_outcomes.json"
FORMAT = "infeasible-outcomes/1"
FIELDS = ("unit", "line", "kind", "outcome", "family", "reason")
FAMILIES = {
    "G": "a guard every caller has already satisfied (data flow)",
    "C": "a test of a constant: a copybook VALUE never written, a table built once, a loop index with fixed bounds",
    "R": "a response the command never raises (IBM's documented conditions; the reason cites the page)",
}


def load(path: Path = LEDGER) -> dict[str, list[dict[str, Any]]]:
    return json.loads(path.read_text(encoding="utf-8")).get("cases", {}) if path.is_file() else {}


def key(entry: dict[str, Any]) -> str:
    """`unit:line:outcome`, the form #4602 names an entry by."""
    return f"{entry['unit']}:{entry['line']}:{entry['outcome']}"


def stated(case: str, path: Path = LEDGER) -> list[dict[str, Any]]:
    """The case's infeasible outcomes, each {unit, line, kind, outcome, family, reason, key}: for a report that shows
    them as stated assumptions of the proof (tests/tools/evidence_report.py)."""
    return [dict(e, key=key(e)) for e in load(path).get(case, [])]


def problems_in(ledger: dict[str, list[dict[str, Any]]], cases_dir: Path = CASES) -> list[str]:
    """What is wrong with the ledger itself: an unknown case, a missing field, a duplicate, an empty reason."""
    out = []
    for case, entries in sorted(ledger.items()):
        if not (cases_dir / case / "case.json").is_file():
            out.append(f"infeasible outcomes: {case}: no such case")
        seen = set()
        for e in entries:
            missing = [f for f in FIELDS if e.get(f) in (None, "")]
            if missing:
                out.append(f"infeasible outcomes: {case}: an entry lacks {', '.join(missing)}: {e}")
                continue
            if e["family"] not in FAMILIES:
                out.append(f"infeasible outcomes: {case}: {key(e)}: unknown family {e['family']!r}")
            if (e["line"], e["outcome"]) in seen:
                out.append(f"infeasible outcomes: {case}: {key(e)} listed twice")
            seen.add((e["line"], e["outcome"]))
    return out


def outcome_set(uncovered: Iterable[Any]) -> set[tuple[int, str]]:
    """(line, outcome) from a coverage summary's `uncovered` list ({line, outcome, ...}) or "line:outcome" strings."""
    out = set()
    for u in uncovered:
        if isinstance(u, str):
            ln, _, o = u.partition(":")
            out.add((int(ln), o))
        else:
            out.add((int(u["line"]), str(u["outcome"])))
    return out


def adjust(case: str, cov: tuple[int, int, int, int] | None, uncovered: Iterable[Any] | None,
           ledger: dict[str, list[dict[str, Any]]] | None = None) -> tuple[tuple[int, int, int, int] | None, list[str], list[str]]:  # fmt: skip
    """(coverage with the case's stated outcomes taken out of the branch total, the keys taken out, the keys the
    proof reached -- refuted claims). `uncovered` is the proof's uncovered outcomes; None when only counts are known
    (the committed det-sweep ledger, which CI's det-sweep holds to `check`): every entry is then taken as uncovered."""
    entries = (load() if ledger is None else ledger).get(case, [])
    if cov is None or not entries:
        return cov, [], []
    pc, pl, bc, bt = cov
    if uncovered is None:
        return (pc, pl, bc, bt - len(entries)), [key(e) for e in entries], []
    open_ = outcome_set(uncovered)
    out = [key(e) for e in entries if (int(e["line"]), e["outcome"]) in open_]
    reached = [key(e) for e in entries if (int(e["line"]), e["outcome"]) not in open_]
    return (pc, pl, bc, bt - len(out)), out, reached


def check(det: dict[str, dict[str, Any]], ledger: dict[str, list[dict[str, Any]]] | None = None) -> tuple[list[str], list[str]]:  # fmt: skip
    """(problems, warnings) of a det sweep's rows (proof_sweep.py: each proven row's `uncovered`) against the
    ledger: a stated outcome the proof reached (or that is no counted outcome of the program) fails."""
    problems: list[str] = problems_in(load()) if ledger is None else []  # the committed ledger's own form
    ledger = load() if ledger is None else ledger
    warnings: list[str] = []
    for case, row in sorted(det.items()):
        entries = ledger.get(case)
        if not entries or not row.get("proved"):
            continue
        if row.get("uncovered") is None:
            warnings.append(f"infeasible outcomes: {case}: the sweep kept no uncovered outcomes; claims not checked")
            continue
        open_ = outcome_set(row["uncovered"])
        for e in entries:
            if (int(e["line"]), e["outcome"]) not in open_:
                problems.append(f"infeasible outcomes: {case}: {key(e)} is stated infeasible, but the proof reached it "
                                f"(or it is no counted outcome): the claim is wrong -- remove the entry from "
                                f"{LEDGER.relative_to(REPO)} and say why in the PR")  # fmt: skip
    return problems, warnings


def table(cases: list[str] | None = None) -> str:
    """The entries as a Markdown table (the PR body's review table)."""
    rows = ["| case | paragraph:line | outcome | family | why no input reaches it |", "|---|---|---|---|---|"]
    for case, entries in sorted(load().items()):
        if cases and case not in cases:
            continue
        for e in entries:
            rows.append(f"| {case} | {e['unit']}:{e['line']} | {e['kind']} {e['outcome']} | {e['family']} | "
                        f"{e['reason']} |")  # fmt: skip
    return "\n".join(rows)


def _sweep_rows(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        f = d / "sweep.json" if d.is_dir() else d
        for case, row in json.loads(f.read_text(encoding="utf-8")).get("det", {}).items():
            if row.get("uncovered") is None:
                cj = f.parent / "det" / case / "proof" / "cobol" / "coverage.json"
                if cj.is_file():
                    row = dict(row, uncovered=json.loads(cj.read_text(encoding="utf-8"))["branches"]["uncovered"])
            out[case] = row
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("cases", nargs="*")
    c = sub.add_parser("check")
    c.add_argument("sweeps", type=Path, nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "show":
        print(table(args.cases or None))
        return 0
    problems, warnings = check(_sweep_rows(args.sweeps))
    for w in warnings:
        print(f"warning: {w}")
    for p in problems:
        print(p)
    print("infeasible outcomes: " + ("FAIL" if problems else "ok"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
