#!/usr/bin/env python3
"""#4602: branch outcomes no input can reach, stated per equivalence case -- reviewed, never hidden.

The strict bar (proof_blockers.py --branches) asks every counted branch outcome of a program to run. Some cannot:
a guard every caller has already satisfied, a WHEN on a constant table or a bounded loop index. cobol_coverage.py
sets apart only what control flow alone shows (after a GO TO / XCTL / RETURN ...: `after_transfer`); a data-flow
fact like these is stated here instead, by a person, with its reason:

    tests/equivalence/infeasible_outcomes/<CASE>.json     (one file per case: ladder slices stop conflicting, #6072)
    {"format": "infeasible-outcomes/2", "case": CASE,
     "entries": [{"unit": PARAGRAPH, "line": N, "kind": "IF"|"EVALUATE", "outcome": "true"|"false"|"WHEN@N"|
                  "OTHER"|"none", "family": "G"|"C"|"R", "reason": WHY NO INPUT REACHES IT, citing the COBOL}]}

A whole paragraph no input enters is stated the same way, kind "PARAGRAPH", outcome "entered" (`line` optional): it
leaves the live-paragraph total as a branch entry leaves the branch total, and the proof entering it refutes it.
`load()` still reads the old single file ({"cases": {CASE: [...]}}) when one sits beside the directory (tests, scratch).

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
    python tests/tools/infeasible_outcomes.py add CASE (--line N --arm OUTCOME | --paragraph NAME) --family G|C|R --reason WHY
                                                                    # [--unit P --kind IF]: written sorted; unit / kind
                                                                    # come from the case's evidence.json when it lists the outcome
    python tests/tools/infeasible_outcomes.py check SWEEP [SWEEP ...] # against proof_sweep.py --det-only work dirs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from collections.abc import Iterable

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
CASES = REPO / "tests" / "equivalence"
LEDGER = CASES / "infeasible_outcomes"
FORMAT = "infeasible-outcomes/2"
PARAGRAPH = "PARAGRAPH"  # the kind of an entry that states a whole paragraph (outcome "entered")
FIELDS = ("unit", "line", "kind", "outcome", "family", "reason")
PARAGRAPH_FIELDS = ("unit", "kind", "outcome", "family", "reason")  # a paragraph entry's line is optional
FAMILIES = {
    "G": "a guard every caller has already satisfied (data flow)",
    "C": "a test of a constant: a copybook VALUE never written, a table built once, a loop index with fixed bounds",
    "R": "a response the command never raises (IBM's documented conditions; the reason cites the page)",
    "U": "undefined by IBM: reachable only through an out-of-range subscript or reference modification without SSRANGE "
    "(IBM leaves the result undefined, GnuCOBOL refuses; owner ruling 2026-10-29). Netted from the bar like the others, "
    "but reported by name with counts as its own class, never as proven or as infeasible",
}
UNDEFINED = "U"  # the family of an 'undefined by IBM' outcome


def load(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """case -> entries: the per-case files of directory `path` (default LEDGER), plus the old single file
    `<path>.json` when one sits beside it."""
    path = LEDGER if path is None else path
    out: dict[str, list[dict[str, Any]]] = {}
    legacy = path.with_name(path.name + ".json")
    if legacy.is_file():
        out.update(json.loads(legacy.read_text(encoding="utf-8")).get("cases", {}))
    if path.is_dir():
        for f in sorted(path.glob("*.json")):
            out[f.stem] = json.loads(f.read_text(encoding="utf-8")).get("entries", [])
    return out


def is_undefined(entry: dict[str, Any]) -> bool:
    """An 'undefined by IBM' outcome (family U): a class of its own, not an infeasible one."""
    return entry.get("family") == UNDEFINED


def split_undefined(keys: Iterable[str], entries: Iterable[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(the keys that are infeasible, the keys that are undefined by IBM) of `keys`, by the family of their entries."""
    und = {key(e) for e in entries if is_undefined(e)}
    ks = list(keys)
    return [k for k in ks if k not in und], [k for k in ks if k in und]


def is_paragraph(entry: dict[str, Any]) -> bool:
    return entry.get("kind") == PARAGRAPH


def key(entry: dict[str, Any]) -> str:
    """`unit:line:outcome`, the form #4602 names an entry by (`unit:paragraph` for a whole paragraph)."""
    if is_paragraph(entry):
        return f"{entry['unit']}:paragraph"
    return f"{entry['unit']}:{entry['line']}:{entry['outcome']}"


def sort_key(entry: dict[str, Any]) -> tuple[int, str, str]:
    return int(entry.get("line") or 0), entry["unit"], entry["outcome"]


def write_case(case: str, entries: list[dict[str, Any]], directory: Path | None = None) -> Path:
    """The case's file, entries sorted, one line per field (stable diffs)."""
    directory = LEDGER if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    f = directory / f"{case}.json"
    body = {"format": FORMAT, "case": case, "entries": sorted(entries, key=sort_key)}
    f.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return f


def stated(case: str, path: Path = LEDGER) -> list[dict[str, Any]]:
    """The case's infeasible outcomes, each {unit, line, kind, outcome, family, reason, key} (a PARAGRAPH entry may have
    no `line`; test `is_paragraph` before reading it): for a report that shows
    them as stated assumptions of the proof (tests/tools/evidence_report.py)."""
    return [dict(e, key=key(e)) for e in load(path).get(case, [])]


def problems_in(ledger: dict[str, list[dict[str, Any]]], cases_dir: Path = CASES) -> list[str]:
    """What is wrong with the ledger itself: an unknown case, a missing field, a duplicate, an empty reason."""
    out = []
    for case, entries in sorted(ledger.items()):
        if not entries:
            out.append(f"infeasible outcomes: {case}: no entries (remove the file)")
        if not (cases_dir / case / "case.json").is_file():
            out.append(f"infeasible outcomes: {case}: no such case")
        seen = set()
        for e in entries:
            missing = [f for f in (PARAGRAPH_FIELDS if is_paragraph(e) else FIELDS) if e.get(f) in (None, "")]
            if missing:
                out.append(f"infeasible outcomes: {case}: an entry lacks {', '.join(missing)}: {e}")
                continue
            if e["family"] not in FAMILIES:
                out.append(f"infeasible outcomes: {case}: {key(e)}: unknown family {e['family']!r}")
            if key(e) in seen:
                out.append(f"infeasible outcomes: {case}: {key(e)} listed twice")
            seen.add(key(e))
    return out


PARAGRAPH_MARK = "paragraph:"


def outcome_set(uncovered: Iterable[Any]) -> set[tuple[int, str]]:
    """(line, outcome) from a coverage summary's `uncovered` list ({line, outcome, ...}) or "line:outcome" strings;
    the "paragraph:NAME" strings of `uncovered_of` are no outcome and are skipped."""
    out = set()
    for u in uncovered:
        if isinstance(u, str):
            if u.startswith(PARAGRAPH_MARK):
                continue
            ln, _, o = u.partition(":")
            out.add((int(ln), o))
        elif "outcome" in u:
            out.add((int(u["line"]), str(u["outcome"])))
    return out


def paragraph_set(uncovered: Iterable[Any]) -> set[str]:
    """The names of the uncovered paragraphs in an `uncovered` list ("paragraph:NAME" strings, or {name, line})."""
    out = set()
    for u in uncovered:
        if isinstance(u, str) and u.startswith(PARAGRAPH_MARK):
            out.add(u[len(PARAGRAPH_MARK) :])
        elif isinstance(u, dict) and "name" in u and "outcome" not in u:
            out.add(str(u["name"]))
    return out


def uncovered_of(coverage: dict[str, Any]) -> list[str]:
    """What a proof's coverage.json left uncovered: "line:outcome" for each branch outcome, "paragraph:NAME" for each
    live paragraph no run entered (the sweep rows' `uncovered`)."""
    out = [f"{u['line']}:{u['outcome']}" for u in coverage["branches"]["uncovered"]]
    out += [PARAGRAPH_MARK + u["name"] for u in (coverage.get("paragraphs") or {}).get("uncovered") or []]
    return out


def is_open(e: dict[str, Any], open_: set[tuple[int, str]], paragraphs: set[str]) -> bool:
    """Did the proof leave this entry's outcome (or paragraph) uncovered?"""
    if is_paragraph(e):
        return e["unit"] in paragraphs
    return (int(e["line"]), e["outcome"]) in open_


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
        np = sum(1 for e in entries if is_paragraph(e))
        return (pc, pl - np, bc, bt - (len(entries) - np)), [key(e) for e in entries], []
    open_, paras = outcome_set(uncovered), paragraph_set(uncovered)
    out = [e for e in entries if is_open(e, open_, paras)]
    reached = [key(e) for e in entries if not is_open(e, open_, paras)]
    np = sum(1 for e in out if is_paragraph(e))
    return (pc, pl - np, bc, bt - (len(out) - np)), [key(e) for e in out], reached


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
        open_, paras = outcome_set(row["uncovered"]), paragraph_set(row["uncovered"])
        for e in entries:
            if not is_open(e, open_, paras):
                problems.append(f"infeasible outcomes: {case}: {key(e)} is stated infeasible, but the proof reached it "
                                f"(or it is no counted outcome): the claim is wrong -- remove the entry from "
                                f"{LEDGER.relative_to(REPO)}/{case}.json and say why in the PR")  # fmt: skip
    return problems, warnings


def table(cases: list[str] | None = None) -> str:
    """The entries as a Markdown table (the PR body's review table)."""
    rows = [
        "| case | paragraph:line | outcome | family (U = undefined by IBM) | why no input reaches it |",
        "|---|---|---|---|---|",
    ]
    for case, entries in sorted(load().items()):
        if cases and case not in cases:
            continue
        for e in entries:
            where = e["unit"] if is_paragraph(e) else f"{e['unit']}:{e['line']}"
            rows.append(f"| {case} | {where} | {e['kind']} {e['outcome']} | {e['family']} | "
                        f"{e['reason']} |")  # fmt: skip
    return "\n".join(rows)


def evidence_branch(case: str, line: int, arm: str, cases_dir: Path = CASES) -> dict[str, Any] | None:
    """The case's recorded uncovered branch at `line` with outcome `arm` (evidence.json), for its unit and kind."""
    f = cases_dir / case / "evidence.json"
    if not f.is_file():
        return None
    for b in (json.loads(f.read_text(encoding="utf-8")).get("coverage") or {}).get("uncovered_branches") or []:
        if int(b["line"]) == line and b["outcome"] == arm:
            return b
    return None


def add(case: str, *, family: str, reason: str, line: int | None = None, arm: str | None = None,
        paragraph: str | None = None, unit: str | None = None, kind: str | None = None,
        cases_dir: Path = CASES, directory: Path | None = None) -> dict[str, Any]:  # fmt: skip
    """Add one entry to the case's file (written sorted); a bad or duplicate entry raises ValueError."""
    if not (cases_dir / case / "case.json").is_file():
        raise ValueError(f"no such case: {case}")
    if (paragraph is None) == (line is None or arm is None):
        raise ValueError("give --paragraph NAME, or --line N with --arm OUTCOME")
    if paragraph is not None:
        entry = {"unit": paragraph, "kind": PARAGRAPH, "outcome": "entered", "family": family, "reason": reason}
        if line is not None:
            entry["line"] = line
    else:
        assert line is not None and arm is not None
        found = evidence_branch(case, line, arm, cases_dir)
        unit, kind = unit or (found or {}).get("unit"), kind or (found or {}).get("kind")
        if not unit or not kind:
            raise ValueError(
                f"{case} line {line} {arm}: not in its evidence.json uncovered branches; give --unit and --kind"
            )
        entry = {"unit": unit, "line": line, "kind": kind, "outcome": arm, "family": family, "reason": reason}
    directory = LEDGER if directory is None else directory
    entries = load(directory).get(case, []) + [entry]
    problems = problems_in({case: entries}, cases_dir)
    if problems:
        raise ValueError("; ".join(problems))
    write_case(case, entries, directory)
    return entry


def _sweep_rows(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        f = d / "sweep.json" if d.is_dir() else d
        for case, row in json.loads(f.read_text(encoding="utf-8")).get("det", {}).items():
            if row.get("uncovered") is None:
                cj = f.parent / "det" / case / "proof" / "cobol" / "coverage.json"
                if cj.is_file():
                    row = dict(row, uncovered=uncovered_of(json.loads(cj.read_text(encoding="utf-8"))))
            out[case] = row
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("cases", nargs="*")
    c = sub.add_parser("check")
    c.add_argument("sweeps", type=Path, nargs="+")
    a = sub.add_parser("add", help="state one branch outcome or paragraph no input reaches")
    a.add_argument("case")
    a.add_argument("--line", type=int)
    a.add_argument("--arm", help="the outcome: true | false | WHEN@N | OTHER | none")
    a.add_argument("--paragraph", help="a whole paragraph no input enters")
    a.add_argument("--unit")
    a.add_argument("--kind")
    a.add_argument("--family", required=True, choices=sorted(FAMILIES))
    a.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "add":
        try:
            e = add(args.case, family=args.family, reason=args.reason, line=args.line, arm=args.arm,
                    paragraph=args.paragraph, unit=args.unit, kind=args.kind)  # fmt: skip
        except ValueError as err:
            print(f"infeasible outcomes: {err}")
            return 1
        print(f"added {key(e)} to {LEDGER.relative_to(REPO)}/{args.case}.json")
        return 0
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
