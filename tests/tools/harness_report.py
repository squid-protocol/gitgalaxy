#!/usr/bin/env python3
"""#4493: the equivalence harness reports on itself -- how much of an estate it can test, what ran, and what stops the rest.

    python tests/tools/harness_report.py PROOF_BLOCKERS.json --out DIR [--estate NAME] [--cases-dir DIR]
    python tests/tools/harness_report.py --survey DIR [--label before ...] [--sweep SWEEP ...] --out DIR

PROOF_BLOCKERS.json is `proof_blockers.py DIR --json` (nothing is re-derived here: the gaps, cases and verdicts are its).
`--survey DIR` runs proof_blockers on a `cics_census.py survey` directory first. Writes DIR/harness_report.{md,json}.
The page is generated output: it is not committed (evidence pages are published to the `generated` branch, #5206).

The page has four parts:
  coverage      programs in the estate, with a runnable case, proven (counts and %), and the share of paragraphs and
                branches the cases' scenarios exercise (from each case's evidence.json, the `cobol_coverage` numbers)
  run status    every program: proven / differs / couldn't run / not attempted (and `ran, coverage open`), each with why
  inputs        per case: the datasets whose records are generated from a layout (`@generate`), the ones that fall back
                to shipped data, and the ones with no input (skipped); and whether the scenarios are generated
  blockers      each non-proven program is listed under exactly ONE blocker (its highest-ranked gap), phrased as the
                fix. `tests_unlocked` is exact: the scenarios of the cases of the programs for which fixing the blocker
                leaves nothing else open (a program with another gap stays blocked). `tests_touched` counts the programs
                it also blocks. Sorted by tests unlocked, so the top line is the highest-value next step.

Burned estates only (estate4_draw.BURNED_NAMES): a non-burned program is counted, never named (mainframe evidence policy).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

CASES = REPO / "tests" / "equivalence"
SCHEMA_VERSION = "1.0"

PROVEN, DIFFERS, COULDNT_RUN, NOT_ATTEMPTED, COVERAGE_OPEN = (
    "proven", "differs", "couldn't run", "not attempted", "ran, coverage open",
)  # fmt: skip
STATUSES = (PROVEN, DIFFERS, COVERAGE_OPEN, COULDNT_RUN, NOT_ATTEMPTED)


def gap_status(gap: str) -> str:
    """The run status one gap stands for."""
    if gap in ("no case",) or gap.startswith("no det port"):
        return NOT_ATTEMPTED
    if gap.startswith("scenario differs"):
        return DIFFERS
    if gap.startswith("coverage:") or gap.startswith("infeasible outcome"):
        return COVERAGE_OPEN
    return COULDNT_RUN  # known unproven, not proven in CI (Db2), fact: ..., a linked program not measured


def program_status(gaps: list[str]) -> str:
    if not gaps:
        return PROVEN
    found = {gap_status(g) for g in gaps}
    return next(s for s in (DIFFERS, COULDNT_RUN, NOT_ATTEMPTED, COVERAGE_OPEN) if s in found)


def clip(text: str, n: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def fix_for(gap: str, programs: list[str], cases: list[str], details: list[str]) -> str:
    """The gap stated as the action that unblocks it."""
    who = ", ".join(programs)
    n = len(programs)
    noun = f"{n} program{'s' if n != 1 else ''}"
    if gap == "no case":
        return f"Write an equivalence case for {noun}: {who}."
    if gap.startswith("no det port"):
        return f"Commit a det port for {noun} (their crucible case runs only the COBOL): {who}."
    if gap.startswith("known unproven"):
        why = clip("; ".join(sorted(set(details))) or gap)
        return f"Fix {gap.split(':', 1)[1].strip()} ({why}) to prove {noun}: {who} (cases: {', '.join(cases)})."
    if gap.startswith("scenario differs"):
        return f"Fix the difference `{gap.split(':', 1)[1].strip()}` between the COBOL and the Java in {noun}: {who} (cases: {', '.join(cases)})."  # fmt: skip
    if gap.startswith("not proven in CI"):
        return f"Run the Db2 lane (a det sweep with the Db2 container) so its ledger records a verdict for {noun}: {who} (cases: {', '.join(cases)})."  # fmt: skip
    if gap.startswith("fact:"):
        return (
            f"Teach the harness the runtime fact `{gap[5:].strip()}` (or state it in the case) to prove {noun}: {who}."
        )
    if gap.startswith("coverage"):
        return f"Add scenarios that reach the paragraphs / branches nothing runs in {noun}: {who} (cases: {', '.join(cases)})."  # fmt: skip
    return f"Resolve `{gap}` in {noun}: {who}."


# ---- the cases -----------------------------------------------------------------------------------------------------
def load_case(cases_dir: Path, name: str) -> dict[str, Any]:
    f = cases_dir / name / "case.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def scenario_count(case: dict[str, Any]) -> int:
    """Scenarios a case runs: the stated ones plus the generated ones (`scenario_generate.count`)."""
    return len(case.get("scenarios") or []) + int((case.get("scenario_generate") or {}).get("count") or 0)


def input_generation(case: dict[str, Any]) -> dict[str, Any]:
    """Which of the case's datasets got generated inputs, which fell back to shipped data, which have no input."""
    generated: list[dict[str, Any]] = []
    shipped: list[str] = []
    skipped: list[str] = []
    for dd, spec in sorted((case.get("datasets") or {}).items()):
        inp = spec.get("input")
        if inp == "@generate":
            g = spec.get("generate") or {}
            generated.append({"dataset": dd, "copybook": g.get("copybook", spec.get("copybook", "")),
                              "record": g.get("record", spec.get("record", "")), "records": g.get("records")})  # fmt: skip
        elif inp:
            shipped.append(dd)
        else:
            skipped.append(dd)
    out: dict[str, Any] = {"generated": generated, "shipped": shipped, "skipped": skipped}
    out["scenarios_generated"] = bool(case.get("scenario_generate"))
    return out


def case_coverage(cases_dir: Path, name: str) -> dict[str, int] | None:
    f = cases_dir / name / "evidence.json"
    if not f.is_file():
        return None
    cov = json.loads(f.read_text(encoding="utf-8")).get("coverage") or {}
    para, br = cov.get("paragraphs") or {}, cov.get("branches") or {}
    if not para and not br:
        return None
    return {"paragraphs_covered": int(para.get("covered", 0)), "paragraphs_live": int(para.get("live", 0)),
            "branches_covered": int(br.get("covered", 0)), "branches_total": int(br.get("total", 0))}  # fmt: skip


def pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


# ---- the report ----------------------------------------------------------------------------------------------------
def build(res: dict[str, Any], estate: str = "estate", cases_dir: Path = CASES) -> dict[str, Any]:
    """The report data from `proof_blockers`' result. Burned, non-crucible programs only; others are counted."""
    from proof_blockers import is_crucible

    progs = [p for p in res.get("programs", []) if not is_crucible(p["corpus"])]
    named = [p for p in progs if p.get("burned")]
    case_names = sorted({p["case"] for p in named if p.get("case")})
    cases = {c: load_case(cases_dir, c) for c in case_names}
    tests = {c: scenario_count(cases[c]) for c in case_names}
    rank = {g["gap"]: i for i, g in enumerate(res.get("gaps", []))}

    statuses = dict.fromkeys(STATUSES, 0)
    rows = []
    for p in named:
        gaps = list(p["gaps"])
        st = program_status(gaps)
        statuses[st] += 1
        rows.append({
            "corpus": p["corpus"], "program": p["program"], "case": p.get("case"), "status": st, "gaps": gaps,
            "reasons": {g: p.get("detail", {}).get(g, "") for g in gaps}, "tests": tests.get(p.get("case") or "", 0),
        })  # fmt: skip

    # one blocker per non-proven program: its highest-ranked gap
    owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["gaps"]:
            primary = min(r["gaps"], key=lambda g: (rank.get(g, len(rank)), g))
            r["blocker"] = primary
            owner[primary].append(r)
    blockers = []
    for gap, members in owner.items():
        only = [r for r in members if r["gaps"] == [gap]]
        also = sorted(r["program"] for r in rows if gap in r["gaps"] and r.get("blocker") != gap)
        unlocked_cases = sorted({r["case"] for r in only if r["case"]})
        names = sorted(r["program"] for r in members)
        case_list = sorted({r["case"] for r in members if r["case"]})
        details = [d for r in members for g, d in r["reasons"].items() if g == gap and d]
        blockers.append({
            "gap": gap, "fix": fix_for(gap, names, case_list, details), "programs": names, "cases": case_list,
            "programs_unlocked": len(only), "tests_unlocked": sum(tests.get(c, 0) for c in unlocked_cases),
            "programs_also_blocked": also,
            "then_needs": {r["program"]: [g for g in r["gaps"] if g != gap] for r in members if len(r["gaps"]) > 1},
        })  # fmt: skip
    blockers.sort(key=lambda b: (-b["tests_unlocked"], -b["programs_unlocked"], -len(b["programs"]), b["gap"]))

    cov = [c for c in (case_coverage(cases_dir, n) for n in case_names) if c]
    sums = {k: sum(c[k] for c in cov) for k in ("paragraphs_covered", "paragraphs_live", "branches_covered", "branches_total")}  # fmt: skip
    with_case = sum(1 for r in rows if r["case"])
    total = len(rows)
    coverage = {
        "programs": total, "with_case": with_case, "with_case_pct": pct(with_case, total),
        "proven": statuses[PROVEN], "proven_pct": pct(statuses[PROVEN], total),
        "paragraphs": {"covered": sums["paragraphs_covered"], "live": sums["paragraphs_live"],
                       "pct": pct(sums["paragraphs_covered"], sums["paragraphs_live"])},
        "branches": {"covered": sums["branches_covered"], "total": sums["branches_total"],
                     "pct": pct(sums["branches_covered"], sums["branches_total"])},
        "cases_measured": len(cov), "cases": len(case_names),
    }  # fmt: skip
    inputs = {c: input_generation(cases[c]) | {"tests": tests[c]} for c in case_names}
    return {
        "schema_version": SCHEMA_VERSION, "estate": estate, "scope": res.get("scope", ""),
        "coverage": coverage, "status_counts": statuses, "programs": rows, "inputs": inputs, "blockers": blockers,
        "not_listed": {"non_burned_programs": len([p for p in progs if not p.get("burned")]),
                       "note": "non-burned census programs are counted, never named (mainframe evidence policy)"},
    }  # fmt: skip


def _p(v: float | None) -> str:
    return "n/a" if v is None else f"{v}%"


def markdown(rep: dict[str, Any]) -> str:
    c = rep["coverage"]
    out = [f"# Equivalence harness report -- {rep['estate']}", "",
           "Generated by `tests/tools/harness_report.py` (#4493); regenerated on every run, nothing here is hand-maintained.", "",
           "## Coverage", "",
           f"- Programs in the estate: {c['programs']} ({rep['scope']})",
           f"- With a runnable case: {c['with_case']} ({_p(c['with_case_pct'])})",
           f"- Proven: {c['proven']} ({_p(c['proven_pct'])})",
           (
               f"- Paragraphs exercised: {c['paragraphs']['covered']}/{c['paragraphs']['live']} ({_p(c['paragraphs']['pct'])}),"
               f" branches: {c['branches']['covered']}/{c['branches']['total']} ({_p(c['branches']['pct'])})"
               f" -- {c['cases_measured']} of {c['cases']} cases have a coverage record"
           ), ""]  # fmt: skip
    out += ["## Blockers (highest value first)", ""]
    if not rep["blockers"]:
        out += ["None: every program is proven.", ""]
    for i, b in enumerate(rep["blockers"], 1):
        out.append(f"{i}. {b['fix']} Unlocks {b['tests_unlocked']} tests across {b['programs_unlocked']} programs"
                   f" ({len(b['programs'])} listed here).")  # fmt: skip
        for prog, rest in b["then_needs"].items():
            out.append(f"   `{prog}` also needs: {clip('; '.join(rest))}")
        if b["programs_also_blocked"]:
            out.append(f"   Also blocks, under another blocker: {', '.join(b['programs_also_blocked'])}.")
    out += ["", "## Run status per program", "", "| program | case | status | why |", "|---|---|---|---|"]
    for r in rep["programs"]:
        why = "; ".join(f"{g}" + (f" ({d})" if d else "") for g, d in r["reasons"].items()) or "-"
        out.append(f"| `{r['corpus']}` / `{r['program']}` | {r['case'] or '-'} | {r['status']} | {why} |")
    out += [
        "",
        "Counts: " + ", ".join(f"{s} {n}" for s, n in rep["status_counts"].items()),
        "",
        "## Input generation",
        "",
    ]
    if not rep["inputs"]:
        out.append("No case.")
    else:
        out += ["| case | generated from a layout | shipped data | no input (skipped) | scenarios generated |",
                "|---|---|---|---|---|"]  # fmt: skip
    for name, i in rep["inputs"].items():
        gen = ", ".join(f"{g['dataset']} ({g['record'] or g['copybook']})" for g in i["generated"]) or "-"
        out.append(f"| {name} | {gen} | {', '.join(i['shipped']) or '-'} | {', '.join(i['skipped']) or '-'} |"
                   f" {'yes' if i['scenarios_generated'] else 'no'} |")  # fmt: skip
    nl = rep["not_listed"]
    out += ["", f"Not listed: {nl['non_burned_programs']} non-burned programs ({nl['note']}).", ""]
    return "\n".join(out)


def write_report(res: dict[str, Any], out: Path, estate: str = "estate", cases_dir: Path = CASES) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    rep = build(res, estate, cases_dir)
    paths = {"json": out / "harness_report.json", "md": out / "harness_report.md"}
    paths["json"].write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    paths["md"].write_text(markdown(rep), encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", type=Path, help="proof_blockers.py --json output")
    ap.add_argument("--survey", type=Path, help="a cics_census.py survey directory: run proof_blockers on it")
    ap.add_argument("--label", nargs="+", default=["before"])
    ap.add_argument("--sweep", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--estate", default="burned estates")
    ap.add_argument("--cases-dir", type=Path, default=CASES)
    args = ap.parse_args(argv)
    if args.survey:
        import cics_census as cc
        import proof_blockers as pb

        rows: dict[tuple[str, str], dict[str, Any]] = {}
        for label in args.label:
            rows.update(cc.load_surveys(args.survey, label))
        if not rows:
            raise SystemExit(f"no {'/'.join(args.label)}-*/survey.json under {args.survey}")
        roots = [cc.mainframe_root(None)]
        res = pb.proof_blockers(rows, roots, sweeps=pb.load_sweeps(args.sweep), cases_dir=args.cases_dir)
    elif args.input:
        res = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        ap.error("give PROOF_BLOCKERS.json or --survey DIR")
    for p in write_report(res, args.out, args.estate, args.cases_dir).values():
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
