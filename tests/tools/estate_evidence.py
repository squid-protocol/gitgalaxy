#!/usr/bin/env python3
"""#4054: the estate-level evidence report, rolled up from the per-program evidence records (#4048).

    python tests/tools/estate_evidence.py [ESTATE ...] [--json] [--out DIR] [--no-live]

Per program: the evidence level, the oracle, paragraph / branch coverage, the mutation score with its survivors by
triage class, the declared differences, the approval and whether the record is stale. Per estate and overall: the
programs at each level, branch- and paragraph-weighted coverage, the mutation score summed over the programs that have
one, open survivors, declared differences, approvals and stale records. It reads the committed records through
evidence.py and never writes a record or an approval. Nothing is committed from here: the output goes to stdout or to
--out (outside the repository), like the other aggregate reports (#5057).

The ladder (cumulative; a level is the highest whose conditions hold; counts always accompany it, never "proven"):

  E0 no record            the port has no evidence record
  E1 recorded             a record exists, but the port is not executed-equivalent, or it has holes (a stub or a
                          ported_unproven method), or a program it LINKs / CALLs has holes (transitively, owner
                          policy 4 of mainframe-evidence-policy.md): the case is recorded at this lower level
  E2 executed equivalent  the record's proof ran its scenarios and fault runs against the GnuCOBOL oracle and every
                          output compared equal
  E3 + coverage           ... and the proof executed every live paragraph and every branch outcome
  E4 + mutants accounted  ... and a mutation score is recorded with no untriaged survivor, and it is not stale

The oracle is GnuCOBOL plus gitgalaxy's CICS / LE / Db2 models (or, for a crucible port, the crucible's hand-written
expected logs), not IBM z/OS: every level carries the caveats of docs/language_status/oracle_assumptions.md. Approval
and staleness are columns, not rungs: a stale record keeps the level it was measured at, marked stale.

Lines are the PROCEDURE DIVISION code lines of the program's own source (comments and blank lines excluded,
copybooks not expanded), read from the pinned corpus checkout (`program_source` of the case; for a crucible port the
cics-crucible checkout). No COBOL source is committed, so a program whose checkout is absent is "not measured" and
left out of the line totals; the summary says how many programs were measured. Lines at a level are the lines of the
programs at that level or above; coverage weighted by lines uses paragraph coverage x procedure lines. Only burned
estates are reported (owner, 2026-10-09).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
import evidence as ev  # noqa: E402
from estate4_draw import BURNED_NAMES  # noqa: E402

FORMAT = "gitgalaxy-estate-evidence/1"
CRUCIBLE_ESTATE = "cics-crucible"
LEVELS = ("E0", "E1", "E2", "E3", "E4")
LEVEL_NAMES = {
    "E0": "no record",
    "E1": "recorded, not executed-equivalent or holes",
    "E2": "executed equivalent",
    "E3": "executed equivalent, full coverage",
    "E4": "executed equivalent, full coverage, mutants accounted for",
}
OPEN_SURVIVORS = ("untriaged", "case_gap", "harness_gap")
SURVIVOR_CLASSES = ("case_gap", "harness_gap", "equivalent", "unreachable", "untriaged")
FORBIDDEN_WORDS = ("proven", "verified", "guaranteed")  # the rendered text uses evidence levels instead
NOT_MEASURED_LINES = "not measured (no COBOL source is committed; needs the corpora)"
CBL_EXTS = (".cbl", ".CBL", ".cob", ".COB")


def source_path(t: ev.Target) -> Path | None:
    """The program's COBOL source in the pinned corpus checkout (or the cics-crucible checkout), or None."""
    if t.kind == "crucible":
        import cics_crucible as cc  # noqa: PLC0415 -- only a crucible row needs it

        for name in (t.program, t.program.lower()):
            for ext in CBL_EXTS:
                found = sorted(cc.crucible_path(None).glob(f"cases/*/{t.case}/src/{name}{ext}"))
                if found:
                    return found[0]
        return None
    rel = ev._case_json(t.case).get("program_source")
    if not rel:
        return None
    import mainframe_corpus as mc  # noqa: PLC0415

    path = mc.cache_root() / t.corpus.get("name", "") / rel
    return path if path.is_file() else None


def source_lines(path: Path | None) -> dict[str, int] | None:
    """{procedure, total} code lines of one COBOL source (comments / blanks excluded), None when it is unavailable."""
    if path is None or not path.is_file():
        return None
    import cobol_coverage as cc  # noqa: PLC0415 -- imports gitgalaxy; only a lines roll-up needs it

    from gitgalaxy.core.source_text import read_source  # noqa: PLC0415 -- same reason

    text = read_source(path).text
    free = bool(cc._FREE.search(text))
    total = sum(1 for x in text.split("\n") if x.strip() and not cc._is_comment(x.rstrip("\r"), free))
    return {"procedure": sum(1 for _, code in cc._code_lines(text) if code.strip(" .")), "total": total}


def estate_of(t: ev.Target) -> str:
    return CRUCIBLE_ESTATE if t.kind == "crucible" else t.corpus.get("name", "")


def reportable(estate: str) -> bool:
    return estate == CRUCIBLE_ESTATE or estate.lower() in BURNED_NAMES


def _ratio(text: str | None) -> tuple[int, int] | None:
    if not text or "/" not in text:
        return None
    a, _, b = text.partition("/")
    return int(a), int(b)


def callees(t: ev.Target, by_program: dict[tuple[str, str], list[ev.Target]]) -> list[str]:
    """The keys of the other ports a program's proof LINKs / CALLs into: the case's `programs` (an equivalence case),
    or the sibling programs of the same case (a crucible port: the proof lays every sibling)."""
    if t.kind == "crucible":
        base = ev.CRUCIBLE_PORTS / t.case
        return sorted(f"crucible:{t.case}/{p.name}" for p in base.iterdir()
                      if p.is_dir() and p.name != t.program and (p / "overlay").is_dir())  # fmt: skip
    data = ev._case_json(t.case)
    out: list[str] = []
    for extra in data.get("programs", []):
        found = [o for o in by_program.get((t.corpus.get("name", ""), extra["program"].upper()), []) if o.key != t.key]
        out += [o.key for o in found] or [f"program:{extra['program'].upper()}"]  # no record of its own: unmeasured
    return sorted(set(out))


def own_holes(rec: dict[str, Any]) -> int:
    counts = (rec.get("reach") or {}).get("counts") or {}
    return int(counts.get("stub", 0)) + int(counts.get("ported_unproven", 0))


def reaches_holes(key: str, rows: dict[str, dict[str, Any]], links: dict[str, list[str]]) -> list[str]:
    """The programs (this one's callees, transitively) that have holes or no executed-equivalent record."""
    bad, seen, todo = [], {key}, list(links.get(key, []))
    while todo:
        k = todo.pop()
        if k in seen:
            continue
        seen.add(k)
        r = rows.get(k)
        if r is None or r["executed_equivalent"] is not True or r["holes"]:
            bad.append(k)
        todo += links.get(k, [])
    return sorted(bad)


def row_of(t: ev.Target, rec: dict[str, Any] | None, st: dict[str, Any]) -> dict[str, Any]:
    """One program's record, flattened. No level yet: that needs the callees' rows."""
    row: dict[str, Any] = {"key": t.key, "program": t.program, "case": t.case, "kind": t.kind, "estate": estate_of(t),
                           "record": ev.rel_path(t.record) if t.record.is_file() else None}  # fmt: skip
    if rec is None:
        return {**row, "has_record": False, "executed_equivalent": None, "holes": 0, "stale": [], "approval": None,
                "differences": 0, "coverage": None, "mutation": None, "oracle": None, "proof": None,
                "status": "no-record", "reasons": []}  # fmt: skip
    proof = rec.get("proof") or {}
    cov = rec.get("coverage")
    mut = rec.get("mutation")
    ap = st["approved"]
    reach = (rec.get("reach") or {}).get("counts") or {}
    mutation = None
    if mut:
        raw, adj = _ratio(mut.get("score_raw")), _ratio(mut.get("score_adjusted"))
        surv = {k: int((mut.get("survivors") or {}).get(k, 0)) for k in SURVIVOR_CLASSES}
        mutation = {"killed": raw[0] if raw else 0, "judged": raw[1] if raw else 0,
                    "adjusted_judged": adj[1] if adj else 0, "survivors": surv,
                    "open_survivors": sum(surv[k] for k in OPEN_SURVIVORS), "stillborn": int(mut.get("stillborn", 0)),
                    "stale": st["sections"].get("mutation"), "commit": mut.get("commit")}  # fmt: skip
    return {
        **row,
        **({"lines": src} if (src := source_lines(source_path(t))) else {}),
        "has_record": True,
        "executed_equivalent": proof.get("verdict") == "proven",
        "proof": {
            "runs": proof.get("runs"),
            "fault_runs": proof.get("fault_runs"),
            "at": proof.get("at"),
            "harness_commit": proof.get("harness_commit"),
        },  # fmt: skip
        "oracle": (rec.get("oracle") or {}).get("kind"),
        "holes": own_holes(rec),
        "reach": {k: int(reach.get(k, 0)) for k in ("stub", "left_as_generated", "ported_unproven", "det_helper")},
        "coverage": None
        if not cov
        else {
            "paragraphs": [cov["paragraphs"]["covered"], cov["paragraphs"]["live"]],
            "branches": [cov["branches"]["covered"], cov["branches"]["total"]],
            "uncovered_branches": len(cov.get("uncovered_branches") or []),
        },  # fmt: skip
        "mutation": mutation,
        "differences": len(rec.get("differences") or []),
        "approval": None
        if not ap
        else {
            "by": ap["by"],
            "at": ap["at"][:10],
            "decision": ap["decision"],
            "purpose": ap.get("for"),
            "current": ap["current"],
        },  # fmt: skip
        "stale": list(st["stale"]),
        "status": st["status"],
        "reasons": list(st["reasons"]),
    }


def place(row: dict[str, Any], callee_holes: list[str]) -> None:
    """Set row['level'] and row['why'] (what kept it from the next rung)."""
    why: list[str] = []
    if not row["has_record"]:
        row["level"], row["why"] = "E0", ["no evidence record"]
        return
    level = "E1"
    if not row["executed_equivalent"]:
        why.append("the proof did not compare equal on every scenario" if row["proof"]["runs"] else "never run")
    elif row["holes"]:
        why.append(f"{row['holes']} hole(s) in the port itself (stub or ported_unproven method)")
    elif callee_holes:
        why.append(f"a program it LINKs or CALLs has holes or no executed-equivalent record: {', '.join(callee_holes)}")
    else:
        level = "E2"
        cov = row["coverage"]
        if not cov:
            why.append("coverage not recorded")
        elif cov["paragraphs"][0] < cov["paragraphs"][1] or cov["branches"][0] < cov["branches"][1]:
            why.append(f"coverage short: {cov['paragraphs'][0]}/{cov['paragraphs'][1]} paragraphs, "
                       f"{cov['branches'][0]}/{cov['branches'][1]} branch outcomes")  # fmt: skip
        else:
            level = "E3"
            m = row["mutation"]
            if not m:
                why.append("no mutation score recorded")
            elif m["survivors"]["untriaged"]:
                why.append(f"{m['survivors']['untriaged']} untriaged surviving mutant(s)")
            elif m["stale"]:
                why.append(f"mutation score {m['stale']}")
            else:
                level = "E4"
    row["level"], row["why"] = level, why
    row["level_current"] = not row["stale"]


def build(keys: list[str] | None = None, live: bool = True) -> dict[str, Any]:
    all_targets = ev.targets()
    refused = sorted({estate_of(t) for t in all_targets if not reportable(estate_of(t))})
    targets = [t for t in all_targets if reportable(estate_of(t))]
    by_program: dict[tuple[str, str], list[ev.Target]] = {}
    for t in targets:
        if t.kind != "crucible":
            by_program.setdefault((t.corpus.get("name", ""), t.program), []).append(t)
    rows: dict[str, dict[str, Any]] = {}
    links: dict[str, list[str]] = {}
    for t in targets:
        rec = ev.load(t)
        rows[t.key] = row_of(t, rec, ev.status(rec, t, live=live))
        links[t.key] = callees(t, by_program)
    for k, r in rows.items():
        bad = reaches_holes(k, rows, links)
        r["callees"] = links[k]
        place(r, bad)
    chosen = [r for r in rows.values() if not keys or r["estate"] in keys]
    estates: dict[str, list[dict[str, Any]]] = {}
    for r in sorted(chosen, key=lambda r: (r["estate"], r["key"])):
        estates.setdefault(r["estate"], []).append(r)
    return {
        "format": FORMAT,
        "ladder": LEVEL_NAMES,
        "live": live,
        "lines": "see each summary: procedure code lines where the corpus checkout is present, else not measured",
        "refused_estates": refused,
        "summary": summarise(chosen),
        "estates": {e: {"summary": summarise(rs), "programs": rs} for e, rs in estates.items()},
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    levels = Counter(r["level"] for r in rows)
    para, br = [0, 0], [0, 0]
    killed = judged = adj = stillborn = 0
    surv: Counter[str] = Counter()
    open_surv = 0
    for r in rows:
        if r["coverage"]:
            para[0] += r["coverage"]["paragraphs"][0]
            para[1] += r["coverage"]["paragraphs"][1]
            br[0] += r["coverage"]["branches"][0]
            br[1] += r["coverage"]["branches"][1]
        m = r["mutation"]
        if m:
            killed += m["killed"]
            judged += m["judged"]
            adj += m["adjusted_judged"]
            stillborn += m["stillborn"]
            surv.update(m["survivors"])
            open_surv += m["open_survivors"]
    n = len(rows)
    measured = [r for r in rows if r.get("lines")]
    lines = {
        "programs_measured": len(measured),
        "procedure": sum(r["lines"]["procedure"] for r in measured),
        "total": sum(r["lines"]["total"] for r in measured),
        "at_or_above": {
            lv: sum(r["lines"]["procedure"] for r in measured if r["level"] in LEVELS[LEVELS.index(lv) :])
            for lv in LEVELS[2:]
        },
        "paragraph_weighted": [  # covered / live paragraphs, each program weighted by its procedure lines
            round(sum(r["lines"]["procedure"] * r["coverage"]["paragraphs"][0] / r["coverage"]["paragraphs"][1]
                      for r in measured if r["coverage"] and r["coverage"]["paragraphs"][1])),
            sum(r["lines"]["procedure"] for r in measured if r["coverage"] and r["coverage"]["paragraphs"][1]),
        ],
    }  # fmt: skip
    return {
        "programs": n,
        "levels": {lv: levels.get(lv, 0) for lv in LEVELS},
        "at_or_above_e2": sum(levels.get(lv, 0) for lv in LEVELS[2:]),
        "stale_records": sum(1 for r in rows if r["has_record"] and r["stale"]),
        "stale_mutation_scores": sum(1 for r in rows if r["mutation"] and r["mutation"]["stale"]),
        "approved_current": sum(
            1 for r in rows if r["approval"] and r["approval"]["current"] and r["approval"]["decision"] == "approved"
        ),  # fmt: skip
        "declared_differences": sum(r["differences"] for r in rows),
        "holes": sum(r["holes"] for r in rows),
        "paragraphs": para,
        "branches": br,
        "mutation": {
            "programs_measured": sum(1 for r in rows if r["mutation"]),
            "killed": killed,
            "judged": judged,
            "adjusted_judged": adj,
            "stillborn": stillborn,
            "survivors": {k: surv.get(k, 0) for k in SURVIVOR_CLASSES},
            "open_survivors": open_surv,
        },  # fmt: skip
        "lines": lines if measured else NOT_MEASURED_LINES,
    }


# ---- rendering -----------------------------------------------------------------------------------------------------


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else "n/a"


def _lines_summary(ln: Any, programs: int) -> str:
    if isinstance(ln, str):
        return f"- Lines: {ln}."
    up = ln["at_or_above"]
    return (
        f"- Lines (PROCEDURE DIVISION code lines, copybooks not expanded; {ln['programs_measured']} of {programs} "
        f"programs measured): {ln['procedure']} ({ln['total']} code lines in all); in programs at E2+ "
        f"{_pct(up['E2'], ln['procedure'])}, E3+ {_pct(up['E3'], ln['procedure'])}, "
        f"E4 {_pct(up['E4'], ln['procedure'])}; paragraph coverage weighted by lines "
        f"{_pct(*ln['paragraph_weighted'])}."
    )


def _summary_lines(s: dict[str, Any]) -> list[str]:
    m = s["mutation"]
    lv = s["levels"]
    return [
        f"- Programs: {s['programs']}; at {', '.join(f'{k} {lv[k]}' for k in LEVELS)}; "
        f"executed equivalent or above (E2+): {_pct(s['at_or_above_e2'], s['programs'])}.",
        f"- Coverage over the programs with a record: paragraphs {_pct(*s['paragraphs'])}, "
        f"branch outcomes {_pct(*s['branches'])}.",
        f"- Mutation: {m['programs_measured']} program(s) measured, killed {_pct(m['killed'], m['judged'])} raw "
        f"(adjusted for equivalent / unreachable survivors: {_pct(m['killed'], m['adjusted_judged'])}); "
        f"survivors {', '.join(f'{k} {v}' for k, v in m['survivors'].items())}; open survivors {m['open_survivors']}.",
        f"- Holes (stub / ported_unproven methods): {s['holes']}. Declared differences: {s['declared_differences']}.",
        f"- Approved and current: {s['approved_current']}. Stale records: {s['stale_records']} "
        f"(stale mutation scores: {s['stale_mutation_scores']}).",
        _lines_summary(s["lines"], s["programs"]),
    ]


def _cell(r: dict[str, Any]) -> list[str]:
    cov, m, ap = r["coverage"], r["mutation"], r["approval"]
    proof = r["proof"] or {}
    return [
        r["program"],
        r["case"],
        str(r["lines"]["procedure"]) if r.get("lines") else "-",
        r["level"] + ("" if r.get("level_current", True) else " (stale)"),
        f"{proof.get('runs', '-')} runs / {proof.get('fault_runs', '-')} fault" if proof else "-",
        r["oracle"] or "-",
        f"{cov['paragraphs'][0]}/{cov['paragraphs'][1]} / {cov['branches'][0]}/{cov['branches'][1]}" if cov else "-",
        f"{m['killed']}/{m['judged']}, open {m['open_survivors']}" if m else "-",
        str(r["differences"]),
        f"{ap['decision']} by {ap['by']} ({ap['at']}){'' if ap['current'] else ', earlier version'}" if ap else "-",
        "; ".join(r["why"]) or "-",
    ]


def render(rep: dict[str, Any]) -> str:
    out = ["# Estate evidence report", "",
           "Rolled up from the per-program evidence records (#4048, #4054). A level is evidence, not a verdict: the "
           "oracle is GnuCOBOL plus gitgalaxy's CICS / LE / Db2 models (a crucible port: hand-written expected logs), "
           "not IBM z/OS. See docs/language_status/oracle_assumptions.md.", "", "## Ladder", ""]  # fmt: skip
    out += [f"- **{lv}** {name}" for lv, name in rep["ladder"].items()]
    out += ["", "## All reported estates", ""] + _summary_lines(rep["summary"])
    for estate, e in rep["estates"].items():
        out += ["", f"## {estate}", ""] + _summary_lines(e["summary"])
        out += ["", "| program | case | lines | level | proof | oracle | coverage (para / branch) | mutation | differences | approval | "
                "what stops the next level |", "|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        out += ["| " + " | ".join(c.replace("|", "/") for c in _cell(r)) + " |" for r in e["programs"]]
    if rep["refused_estates"]:
        out += ["", "## Not reported", "",
                "Estates with a record that are not burned estates (owner policy, 2026-10-09): "
                + ", ".join(rep["refused_estates"]) + "."]  # fmt: skip
    return _scrub("\n".join(out) + "\n")


def _scrub(text: str) -> str:
    """The report words levels, never verdicts: the status strings evidence.py puts in a record's reasons are reworded
    (identifiers such as `ported_unproven` stay as they are)."""
    for old, new in (("proven, approved", "executed equivalent, approved"),
                     ("proven, unapproved", "executed equivalent, unapproved"),
                     ("not-proven", "not executed-equivalent"), ("never proven", "never run"),
                     ("the proof failed", "the proof did not compare equal"), ("proven", "run")):  # fmt: skip
        text = re.sub(rf"(?<![\w_]){re.escape(old)}(?![\w_])", new, text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("estates", nargs="*", help="only these estates (corpus names; cics-crucible)")
    ap.add_argument("--json", action="store_true", help="print the JSON report instead of Markdown")
    ap.add_argument("--out", type=Path, help="write report.md and report.json here (outside the repository)")
    ap.add_argument("--no-live", action="store_true", help="judge each record alone, no comparison with the tree")
    args = ap.parse_args(argv)
    rep = build(args.estates or None, live=not args.no_live)
    if args.estates and not rep["estates"]:
        print("no such reported estate", file=sys.stderr)
        return 2
    if args.out:
        out = args.out.resolve()
        if out.is_relative_to(ev.REPO_ROOT):
            print("--out must be outside the repository (nothing is committed from here)", file=sys.stderr)
            return 2
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        (out / "report.md").write_text(render(rep), encoding="utf-8")
        return 0
    print(json.dumps(rep, indent=1, sort_keys=True) if args.json else render(rep), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
