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
  declared_difference  the oracle and IBM differ by design in a documented class (DECLARED_CLASSES, a register entry), so
               no proof can kill the mutant and it is not equivalent (owner, #5401); the triage entry also carries
               "class" and "register", and it stays in the adjusted score's denominator

    python tests/tools/mutation_scores.py build --runs DIR [DIR ...] --triage T.json --commit SHA [--out FILE]
                                                [--rejudged DIR ... --rejudged-commit SHA] [--keep-others]
    python tests/tools/mutation_scores.py retriage --triage T.json [...]   # new verdicts for committed survivors, no re-run
    python tests/tools/mutation_scores.py table [--results FILE] [--doc FILE]     # re-render the doc's table

`build` writes the compact results file (default docs/language_status/mutation_scores.json) and the table;
`table` re-renders the table between the doc's `<!-- mutation-scores -->` markers from the committed file.

#4049: `--rejudged` takes runs that judged some of the same mutants again against a strengthened case (mutation.py
--only, mutation_crucible.py --case-gaps): their verdicts replace the base runs' for those ids, and the port records
`rejudged` (the commit, how many were judged again and how many are now killed). A new input can only add kills (a
mutant killed by the old runs is still killed by them), so this equals a full re-run of the same sample.

Scores: raw = caught / (caught + survived); adjusted = caught / (caught + survived - equivalent - unreachable)
(a declared difference is subtracted from neither).
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
# #5401: the declared-difference verdict. Its count key is written only where non-zero (an always-present empty key
# would change every other port's record), and the class names the register entry that documents the difference.
DECLARED = "declared_difference"
VERDICTS = (*TRIAGE, DECLARED)
DECLARED_CLASSES = {"float-store-rounding": "C6"}  # GnuCOBOL truncates a float store, IBM rounds it
# #4047: the reason an early bulk triage gave every survivor it had not read; it is no verdict (retriage replaces it)
PLACEHOLDER = "not proven equivalent and no scenario of the case kills it"


def _key(run: dict) -> str:
    return f"{run['case']}/{run['program']}"


def check_declared(key: str, t: dict) -> None:
    """#5401: a declared difference names its class and that class's register entry, or the triage is refused."""
    if t.get("class") not in DECLARED_CLASSES or DECLARED_CLASSES[t["class"]] != t.get("register"):
        raise SystemExit(f"{key}: a declared_difference needs class (one of {sorted(DECLARED_CLASSES)}) and the "
                         f"class's register entry; got class={t.get('class')!r} register={t.get('register')!r}")


def totals(ops: dict[str, dict[str, int]]) -> dict[str, int]:
    out = {k: sum(c.get(k, 0) for c in ops.values()) for k in COUNTS}
    if n := sum(c.get(DECLARED, 0) for c in ops.values()):
        out[DECLARED] = n
    return out


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
            tv = t.get("verdict") if t.get("verdict") in VERDICTS else "untriaged"
            if tv == DECLARED:
                check_declared(f"{_key(run)}:{r['id']}", t)
            c[tv] = c.get(tv, 0) + 1
            survivors.append({"id": r["id"], "op": r["op"], "at": f"{r['file']}:{r['line']}",
                              "after": r["after"].strip()[:160], "verdict": tv, "reason": t.get("reason", ""),
                              **({"class": t["class"], "register": t["register"]} if tv == DECLARED else {})})  # fmt: skip
    total = totals(ops)
    return {"case": run["case"], "program": run["program"], "commit": commit, "seed": run.get("seed"),
            "mutants": run["mutants"], "chosen": run["chosen"], "total": total,
            "ops": {k: {n: v for n, v in c.items() if v} for k, c in sorted(ops.items())},
            "survivors": survivors}  # fmt: skip


def placeholders(results: dict) -> dict[str, int]:
    """Per `case/program`, how many survivors still carry the bulk placeholder reason instead of a reading."""
    out = {}
    for p in results["ports"]:
        n = sum(s["reason"].startswith(PLACEHOLDER) for s in p["survivors"])
        if n:
            out[f"{p['case']}/{p['program']}"] = n
    return out


def retriage_port(p: dict, triage: dict) -> int:
    """Re-apply `triage` ({<case>/<PROGRAM>:<id>: {verdict, reason}}) to one committed port entry, then recount its
    per-operator and total verdict counts from the survivors. Returns how many survivors changed."""
    changed = 0
    for s in p["survivors"]:
        t = triage.get(f"{_key(p)}:{s['id']}")
        if t and t["verdict"] in VERDICTS:
            if t["verdict"] == DECLARED:
                check_declared(f"{_key(p)}:{s['id']}", t)
            extra = {"class": t["class"], "register": t["register"]} if t["verdict"] == DECLARED else {}
            if (t["verdict"], t["reason"], extra) != (s["verdict"], s["reason"], {k: s.get(k) for k in extra}):
                s.pop("class", None)
                s.pop("register", None)
                s.update(verdict=t["verdict"], reason=t["reason"], **extra)
                changed += 1
    for c in p["ops"].values():
        for k in (*TRIAGE_ALL, DECLARED):
            c.pop(k, None)
    for s in p["survivors"]:
        c = p["ops"][s["op"]]
        c[s["verdict"]] = c.get(s["verdict"], 0) + 1
    p["total"] = totals(p["ops"])
    return changed


def retriage(triage: dict, out: Path | None = None) -> int:
    """Apply `triage` to the committed results file without re-running a mutant (the verdicts are judgements about
    survivors already measured), then re-render the table and refresh the evidence records. Unknown keys fail."""
    out = out or RESULTS
    results = json.loads(out.read_text(encoding="utf-8"))
    known = {f"{_key(p)}:{s['id']}" for p in results["ports"] for s in p["survivors"]}
    if missing := sorted(set(triage) - known):
        raise SystemExit(f"triage keys that are no survivor of {out}: {missing[:5]}")
    changed = sum(retriage_port(p, triage) for p in results["ports"])
    out.write_text(json.dumps(results, indent=None, separators=(",", ":")).replace(',{"case"', ',\n{"case"')
                   + "\n", encoding="utf-8")  # fmt: skip
    if out.resolve() == RESULTS.resolve():
        import evidence

        print(f"evidence records: mutation refreshed for {len(evidence.refresh_mutation())}")
        evidence.write_pages()
        render(results, DOC)
    return changed


def scores(t: dict) -> tuple[int, int, int]:
    """(caught, judged raw, judged without equivalent and unreachable)."""
    judged = t["killed"] + t["survived"]
    return t["killed"], judged, judged - t["equivalent"] - t["unreachable"]


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def operator_matrix(results: dict) -> str:
    """Per port, per operator: caught / judged (raw). `-` where the port has no judged mutant of that operator."""
    ops = sorted({op for p in results["ports"] for op in p["ops"]})
    rows = ["| port | " + " | ".join(ops) + " |", "|---|" + "---|" * len(ops)]
    for p in results["ports"]:
        cells = []
        for op in ops:
            c = p["ops"].get(op, {})
            judged = c.get("killed", 0) + c.get("survived", 0)
            cells.append(f"{c.get('killed', 0)}/{judged}" if judged else "-")
        rows.append(f"| {p['program']} ({p['case'].removeprefix('crucible:')}) | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def survivor_cells(t: dict) -> str:
    """The survivors column: the five counts, then `+ N declared difference(s)` only where a port has one (#5401)."""
    cells = " / ".join(str(t[k]) for k in TRIAGE_ALL)
    return cells + (f" + {t[DECLARED]} declared" if t.get(DECLARED) else "")


def table(results: dict) -> str:
    header = (
        "| port | harness | mutants run / all | raw score | without equivalent + unreachable "
        "| survivors: case gap / harness gap / equivalent / unreachable / untriaged |"
    )
    rows = [header, "|---|---|---|---|---|---|"]
    groups: dict[str, dict[str, int]] = {}
    for p in results["ports"]:
        t = p["total"]
        caught, raw, adj = scores(t)
        harness = "crucible" if p["case"].startswith("crucible:") else "equivalence"
        name = f"{p['program']} ({p['case'].removeprefix('crucible:')})"
        rows.append(f"| {name} | {harness} | {p['chosen']}/{p['mutants']} | {_pct(caught, raw)} | {_pct(caught, adj)} "
                    f"| {survivor_cells(t)} |")  # fmt: skip
        g = groups.setdefault(harness, dict.fromkeys(COUNTS, 0))
        for k in (*COUNTS, DECLARED):
            g[k] = g.get(k, 0) + t.get(k, 0)
    est: dict[str, int] = dict.fromkeys(COUNTS, 0)
    for g in groups.values():
        for k in (*COUNTS, DECLARED):
            est[k] = est.get(k, 0) + g.get(k, 0)
    for name, t in [*sorted(groups.items()), ("**estate**", est)]:
        caught, raw, adj = scores(t)
        rows.append(f"| **all {name.strip('*')}** | | {t['killed'] + t['survived'] + t['stillborn']} run "
                    f"| **{_pct(caught, raw)}** | **{_pct(caught, adj)}** "
                    f"| {survivor_cells(t)} |")  # fmt: skip
    ops: dict[str, dict[str, int]] = {}
    for p in results["ports"]:
        for op, c in p["ops"].items():
            o = ops.setdefault(op, dict.fromkeys(COUNTS, 0))
            for k, v in c.items():
                o[k] = o.get(k, 0) + v
    rows += ["", "| operator | caught / judged | without equivalent + unreachable |", "|---|---|---|"]
    for op, t in sorted(ops.items()):
        caught, raw, adj = scores(t)
        rows.append(f"| {op} | {_pct(caught, raw)} | {_pct(caught, adj)} |")
    rows += ["", operator_matrix(results)]
    return "\n".join(rows)


def render(results: dict, doc: Path) -> None:
    text = doc.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{doc}: no {BEGIN} ... {END} markers")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    doc.write_text(f"{head}{BEGIN}\n{table(results)}\n{END}{tail}", encoding="utf-8")


def load_triage(paths: list[Path]) -> dict:
    """Survivor verdicts from triage maps and/or earlier results files (their survivors' verdicts); later wins."""
    out: dict = {}
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        if "ports" in data:
            data = {f"{q['case']}/{q['program']}:{s['id']}": {k: s[k] for k in ("verdict", "reason", "class", "register") if k in s}
                    for q in data["ports"] for s in q["survivors"] if s["verdict"] in VERDICTS}  # fmt: skip
        out.update(data)
    return out


def runs_in(d: Path) -> list[Path]:
    return [d / "mutation.json"] if (d / "mutation.json").exists() else sorted(d.glob("*/*/mutation.json"))


def build_scores(runs_dirs: list[Path], triage: dict, commit: str, out: Path | None = None,
                 keep_others: bool = False, rejudged: list[Path] | None = None,
                 rejudged_commit: str | None = None) -> dict:  # fmt: skip
    """Write the results file from the run directories; into the committed file, also refresh every evidence record's
    `mutation` and the pages (#4048: `mutation.py run --record` and `mutation_crucible.py run --record` call this)."""
    out = out or RESULTS
    runs = [json.loads(p.read_text(encoding="utf-8")) for d in runs_dirs for p in runs_in(d)]
    again: dict[str, dict] = {}
    for d in rejudged or []:
        for p in runs_in(d):
            r = json.loads(p.read_text(encoding="utf-8"))
            again.setdefault(_key(r), {}).update({x["id"]: x for x in r["results"]})
    ports = []
    for r in runs:
        redo = again.get(_key(r), {})
        if redo:
            r = {**r, "results": [redo.get(x["id"], x) for x in r["results"]]}
        entry = port_entry(r, triage, commit)
        if redo:
            entry["rejudged"] = {"commit": rejudged_commit, "issue": "#4049", "mutants": len(redo),
                                 "killed": sum(x["verdict"] in ("killed", "timeout") for x in redo.values())}  # fmt: skip
        ports.append(entry)
    if keep_others and out.exists():
        done = {(q["case"], q["program"]) for q in ports}
        ports += [q for q in json.loads(out.read_text(encoding="utf-8"))["ports"]
                  if (q["case"], q["program"]) not in done]  # fmt: skip
    results = {"format": "gitgalaxy-mutation-scores/1", "issue": "#4047",
               "ports": sorted(ports, key=lambda p: (p["case"].startswith("crucible:"), p["case"], p["program"]))}  # fmt: skip
    out.write_text(json.dumps(results, indent=None, separators=(",", ":")).replace(',{"case"', ',\n{"case"')
                   + "\n", encoding="utf-8")  # fmt: skip
    if out.resolve() == RESULTS.resolve():  # #4048: each port's evidence record carries its score
        import evidence

        print(f"evidence records: mutation refreshed for {len(evidence.refresh_mutation())}")
        evidence.write_pages()
    return results


def record_run(work: Path, triage_files: list[Path] | None = None) -> None:
    """`--record` of a mutation runner: the run in `work` becomes its port's committed score and evidence record.
    The committed file's own survivor verdicts carry over (a re-run keeps the triage); `triage_files` add to them."""
    import subprocess

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()
    triage = load_triage([*([RESULTS] if RESULTS.exists() else []), *(triage_files or [])])
    build_scores([work], triage, commit, RESULTS, keep_others=True)
    render(json.loads(RESULTS.read_text(encoding="utf-8")), DOC)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--runs", nargs="+", type=Path, required=True)
    b.add_argument("--triage", type=Path, nargs="*", default=[], help="triage files, or an earlier results file")
    b.add_argument("--commit", required=True, help="the gitgalaxy commit the mutants ran on")
    b.add_argument("--out", type=Path, default=RESULTS)
    b.add_argument("--doc", type=Path, default=DOC)
    b.add_argument("--keep-others", action="store_true", help="keep --out's entries for ports these runs do not cover")
    b.add_argument("--rejudged", nargs="*", type=Path, default=[], help="#4049: runs judging some mutants again")
    b.add_argument("--rejudged-commit", help="the gitgalaxy commit the --rejudged runs ran on")
    r = sub.add_parser("retriage", help="apply triage maps to the committed results (no mutant is re-run)")
    r.add_argument("--triage", type=Path, nargs="+", required=True)
    t = sub.add_parser("table")
    t.add_argument("--results", type=Path, default=RESULTS)
    t.add_argument("--doc", type=Path, default=DOC)
    args = ap.parse_args(argv)
    if args.cmd == "retriage":
        print(f"{retriage(load_triage(args.triage))} survivors re-triaged")
        return 0
    if args.cmd == "build":
        results = build_scores(args.runs, load_triage(args.triage), args.commit, args.out, args.keep_others,
                               args.rejudged, args.rejudged_commit)  # fmt: skip
    else:
        results = json.loads(args.results.read_text(encoding="utf-8"))
    render(results, args.doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
