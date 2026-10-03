#!/usr/bin/env python3
r"""
#4047: the committed mutation scores of the proven ports, and the table in docs/language_status/mutation_testing.md.

Inputs: the run directories of `mutation.py run` (one case each: DIR/mutation.json) and of `mutation_crucible.py run`
(DIR/<case>/<PROG>/mutation.json), and a triage file: every survivor's verdict, keyed `<case>/<PROGRAM>:<mutant id>`:

    {"carddemo-dateutil/CSUTLDTC:4b23a4fffb": {"verdict": "unreachable", "reason": "..."}, ...}

A survivor's verdict is one of
  case_gap     no run of the case exercises the change; a new input (#4049) could kill it
  harness_gap  a run exercises it but the proof does not compare the output it changes (filed as an issue)
  equivalent   the change cannot alter any output (the reason says why)
  unreachable  dead code: no input reaches it, given the program's own data or the oracle's limits (with evidence)

    python tests/tools/mutation_scores.py build --runs DIR [DIR ...] --triage T.json --commit SHA [--out FILE]
    python tests/tools/mutation_scores.py table [--results FILE] [--doc FILE]     # re-render the doc's table

`build` writes the compact results file (default docs/language_status/mutation_scores.json) and the table;
`table` re-renders the table between the doc's `<!-- mutation-scores -->` markers from the committed file.

Scores: raw = caught / (caught + survived); adjusted = caught / (caught + survived - equivalent - unreachable).
Stillborn mutants (javac refused them) count for nothing. A timeout counts as caught.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
RESULTS = REPO / "docs" / "language_status" / "mutation_scores.json"
DOC = REPO / "docs" / "language_status" / "mutation_testing.md"
BEGIN, END = "<!-- mutation-scores -->", "<!-- /mutation-scores -->"
TRIAGE = ("case_gap", "harness_gap", "equivalent", "unreachable")
TRIAGE_ALL = (*TRIAGE, "untriaged")
COUNTS = ("killed", "survived", "stillborn", *TRIAGE_ALL)


def _key(run: dict) -> str:
    return f"{run['case']}/{run['program']}"


def port_entry(run: dict, triage: dict, commit: str) -> dict:
    """One port's compact record: per-operator counts and every survivor with its verdict."""
    ops: dict[str, dict[str, int]] = {}
    survivors = []
    for r in run["results"]:
        c = ops.setdefault(r["op"], dict.fromkeys(COUNTS, 0))
        v = r["verdict"]
        if v in ("killed", "timeout"):
            c["killed"] += 1
        elif v == "stillborn":
            c["stillborn"] += 1
        elif v == "survived":
            c["survived"] += 1
            t = triage.get(f"{_key(run)}:{r['id']}", {})
            tv = t.get("verdict") if t.get("verdict") in TRIAGE else "untriaged"
            c[tv] += 1
            survivors.append({"id": r["id"], "op": r["op"], "at": f"{r['file']}:{r['line']}",
                              "after": r["after"].strip()[:160], "verdict": tv, "reason": t.get("reason", "")})  # fmt: skip
    total = {k: sum(c[k] for c in ops.values()) for k in COUNTS}
    return {"case": run["case"], "program": run["program"], "commit": commit, "seed": run.get("seed"),
            "mutants": run["mutants"], "chosen": run["chosen"], "total": total,
            "ops": {k: {n: v for n, v in c.items() if v} for k, c in sorted(ops.items())},
            "survivors": survivors}  # fmt: skip


def scores(t: dict) -> tuple[int, int, int]:
    """(caught, judged raw, judged without equivalent and unreachable)."""
    judged = t["killed"] + t["survived"]
    return t["killed"], judged, judged - t["equivalent"] - t["unreachable"]


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def table(results: dict) -> str:
    rows = ["| port | harness | mutants run / all | raw score | without equivalent + unreachable "
            "| survivors: case gap / harness gap / equivalent / unreachable / untriaged |",
            "|---|---|---|---|---|---|"]  # fmt: skip
    groups: dict[str, dict[str, int]] = {}
    for p in results["ports"]:
        t = p["total"]
        caught, raw, adj = scores(t)
        harness = "crucible" if p["case"].startswith("crucible:") else "equivalence"
        name = f"{p['program']} ({p['case'].removeprefix('crucible:')})"
        rows.append(f"| {name} | {harness} | {p['chosen']}/{p['mutants']} | {_pct(caught, raw)} | {_pct(caught, adj)} "
                    f"| {' / '.join(str(t[k]) for k in TRIAGE_ALL)} |")  # fmt: skip
        g = groups.setdefault(harness, dict.fromkeys(COUNTS, 0))
        for k in COUNTS:
            g[k] += t[k]
    est = dict.fromkeys(COUNTS, 0)
    for g in groups.values():
        for k in COUNTS:
            est[k] += g[k]
    for name, t in [*sorted(groups.items()), ("**estate**", est)]:
        caught, raw, adj = scores(t)
        rows.append(f"| **all {name.strip('*')}** | | {t['killed'] + t['survived'] + t['stillborn']} run "
                    f"| **{_pct(caught, raw)}** | **{_pct(caught, adj)}** "
                    f"| {' / '.join(str(t[k]) for k in TRIAGE_ALL)} |")  # fmt: skip
    ops: dict[str, dict[str, int]] = {}
    for p in results["ports"]:
        for op, c in p["ops"].items():
            o = ops.setdefault(op, dict.fromkeys(COUNTS, 0))
            for k, v in c.items():
                o[k] += v
    rows += ["", "| operator | caught / judged | without equivalent + unreachable |", "|---|---|---|"]
    for op, t in sorted(ops.items()):
        caught, raw, adj = scores(t)
        rows.append(f"| {op} | {_pct(caught, raw)} | {_pct(caught, adj)} |")
    return "\n".join(rows)


def render(results: dict, doc: Path) -> None:
    text = doc.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{doc}: no {BEGIN} ... {END} markers")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    doc.write_text(f"{head}{BEGIN}\n{table(results)}\n{END}{tail}", encoding="utf-8")


def runs_in(d: Path) -> list[Path]:
    return [d / "mutation.json"] if (d / "mutation.json").exists() else sorted(d.glob("*/*/mutation.json"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--runs", nargs="+", type=Path, required=True)
    b.add_argument("--triage", type=Path)
    b.add_argument("--commit", required=True, help="the gitgalaxy commit the mutants ran on")
    b.add_argument("--out", type=Path, default=RESULTS)
    b.add_argument("--doc", type=Path, default=DOC)
    t = sub.add_parser("table")
    t.add_argument("--results", type=Path, default=RESULTS)
    t.add_argument("--doc", type=Path, default=DOC)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        triage = json.loads(args.triage.read_text(encoding="utf-8")) if args.triage else {}
        runs = [json.loads(p.read_text(encoding="utf-8")) for d in args.runs for p in runs_in(d)]
        ports = [port_entry(r, triage, args.commit) for r in runs]
        results = {"format": "gitgalaxy-mutation-scores/1", "issue": "#4047",
                   "ports": sorted(ports, key=lambda p: (p["case"].startswith("crucible:"), p["case"], p["program"]))}  # fmt: skip
        args.out.write_text(json.dumps(results, indent=None, separators=(",", ":")).replace(',{"case"', ',\n{"case"')
                            + "\n", encoding="utf-8")  # fmt: skip
    else:
        results = json.loads(args.results.read_text(encoding="utf-8"))
    render(results, args.doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
