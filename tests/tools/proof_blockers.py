#!/usr/bin/env python3
"""#4270: the blocker ranking one level up -- for each program the det translator takes WHOLE, what stops it being
PROVEN equivalent, ranked by the programs each gap would make proven.

    python tests/tools/proof_blockers.py DIR [--label main ...] [--sweep SWEEP_DIR ...] [--all-programs]
                                         [--branches] [--top N] [--json]

DIR is a `cics_census.py survey` directory (DIR/<label>-*/survey.json; `survey --baseline` prints the cached one).
A program translated whole is PROVEN when a proof runs it and leaves nothing open. Every program that is not gets
one or more gap classes:

  no case                  no equivalence case (tests/equivalence/*/case.json: its program or a LINKed one in
                           "programs") and no cics-crucible case with a committed det port runs it
  known unproven: ISSUE    the case's det port is listed in tests/equivalence/det_sweep_baseline.json (its cause)
  scenario differs: KIND   a sweep proved the case's det port unequal: KIND is the first diff's event and field root
                           (`RETURN commarea`), or `java side failed`; a crucible java-ported cell in
                           tests/cics_crucible/baseline.json with its reason, specifics stripped
  not proven in CI: Db2    a Db2 case: CI's det-sweep runs --skip-db2, so only a local sweep (--sweep) proves it
  no det port (crucible)   its crucible case runs the COBOL, but no det port of it is committed
  coverage: ...            the proof leaves live paragraphs (and with --branches, branch outcomes) no scenario runs:
                           translated code no proof judged
  fact: NAME               a runtime fact the case would need and no harness states: an EIB field neither runtime
                           sets (EIBCPOSN, EIBRCODE, ...: both sides read zero, z/OS does not; EIBTASKN only under a
                           crucible case: the equivalence harness states it, oracle_assumptions X21), an ASSIGN option
                           whose fact an equivalence case cannot state yet (STARTCODE, USERID, FACILITY, SCRNHT /
                           SCRNWD: refused at run time, X19), ASSIGN APPLID / SYSID with a case stating no "region"

Verdicts come from, in order: the sweeps given with --sweep (`proof_sweep.py --det-only --work DIR`: DIR/sweep.json,
and DIR/det/<case>/proof/report.json for the diff kind), else main's CI ratchet -- a non-Db2 case not in
det_sweep_baseline.json is proven, because CI's det-sweep fails on any that is not. Coverage comes from the sweep's
coverage line, else the committed det-sweep ledger (tests/equivalence/det_sweep_coverage.json, det_coverage_ledger.py: while
its fingerprints match the tree), else the case's evidence record (the COBOL side's coverage of the same
scenarios). Crucible programs (a surveyed corpus named *crucible*, path cases/<trap>/<case>/src/<PROGRAM>.cbl) take their verdicts from
tests/cics_crucible/{baseline,coverage}.json and the ports under tests/cics_crucible/ports.

When several cases run one program, the one with the fewest gaps speaks for it. The ranking is cics_census.py
blockers' one level up: `only` = programs for which the gap is the only one left (burned / non-burned), `one_away` =
programs it leaves one gap from proven, `touched` = all with it. Totals: translated whole N, proven M.

Census programs (the non-burned clones) are read as cics_census reads them -- EXEC CICS names and EIB field names,
counts only; nothing from them is printed but corpus and program names, as in `cics_census.py blockers`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import cics_census as cc  # noqa: E402
from gitgalaxy.standards.cics.eib import EIB_FACTS  # noqa: E402

CASES = REPO / "tests" / "equivalence"
DET_BASELINE = CASES / "det_sweep_baseline.json"
CRUCIBLE = REPO / "tests" / "cics_crucible"

# The EIB fields a harness states for a task: the driver moves TRNID / DATE / TIME / AID / CALEN / TRMID in
# (equivalence_cics.cics_driver / task_driver), and every command sets RESP / RESP2. Every other DFHEIBLK field
# (tests/equivalence/cics/DFHEIBLK.cpy) is INITIALIZEd to zero / spaces on both sides -- equal, but not z/OS's value.
STATED_EIB = frozenset({"EIBTIME", "EIBDATE", "EIBTRNID", "EIBTRMID", "EIBCALEN", "EIBAID", "EIBRESP", "EIBRESP2"})
# #4270: the EIB fields that are a stated fact of the run (the CICS spec's EIB_FACTS: EIBTASKN, $GGCICS_TASKN /
# CicsTask.withTaskNumber). The equivalence harness states them for every task (a case's or scenario's "taskn", else
# the spec's default); the crucible runner does not yet, so a crucible case's program still has the gap.
CASE_STATED_EIB = frozenset(EIB_FACTS)
EIB_FIELDS = frozenset({
    "EIBTIME", "EIBDATE", "EIBTRNID", "EIBTASKN", "EIBTRMID", "EIBCPOSN", "EIBCALEN", "EIBAID", "EIBFN", "EIBRCODE",
    "EIBDS", "EIBREQID", "EIBRSRCE", "EIBSYNC", "EIBFREE", "EIBRECV", "EIBSEND", "EIBATT", "EIBEOC", "EIBFMH",
    "EIBCOMPL", "EIBSIG", "EIBCONF", "EIBERR", "EIBERRCD", "EIBSYNRB", "EIBNODAT", "EIBRESP", "EIBRESP2", "EIBRLDBK",
})  # fmt: skip
# ASSIGN options whose fact the crucible runner states ($GGCICS_STARTCODE / USERID / FACILITY / SCREEN) and the
# equivalence harness does not yet: the stub refuses them at run time ("ASSIGN X: not stated for this task", X19).
ASSIGN_TASK_FACTS = {"STARTCODE": "STARTCODE", "USERID": "USERID", "FACILITY": "FACILITY", "TERMCHK": "FACILITY",
                     "SCRNHT": "SCRNHT/SCRNWD", "SCRNWD": "SCRNHT/SCRNWD"}  # fmt: skip
ASSIGN_REGION_FACTS = ("APPLID", "SYSID")  # stated by a case's "region"

_EIB = re.compile(r"\bEIB[A-Z0-9]+\b")
_COV = re.compile(r"(\d+)/(\d+) paragraphs and (\d+)/(\d+) branches")
_CRUCIBLE_PATH = re.compile(r"(?:^|/)cases/[^/]+/([^/]+)/src/([^/]+)\.(?:cbl|cob|cobol)$", re.I)


# ---- what a proof runs ------------------------------------------------------------------------------------------
@dataclass
class Run:
    """One proof subject that runs a program: an equivalence case, or a crucible case's det port."""

    kind: str  # "equivalence" | "crucible"
    case: str
    role: str = "program"  # "program" | "linked"
    db2: bool = False
    region: bool = False
    gaps: set[str] = field(default_factory=set)
    detail: dict[str, str] = field(default_factory=dict)  # gap -> a longer note (the baseline's why, the diff)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def equivalence_runs(cases_dir: Path = CASES) -> dict[tuple[str, str], list[Run]]:
    """(corpus, program path lower-cased) -> the equivalence cases whose det proof runs it."""
    out: dict[tuple[str, str], list[Run]] = defaultdict(list)
    for f in sorted(cases_dir.glob("*/case.json")):
        case = json.loads(f.read_text(encoding="utf-8"))
        if "corpus" not in case or "program_source" not in case:
            continue
        db2, region = "db2" in case, bool((case.get("region") or {}).get("applid"))
        out[(case["corpus"], _norm(case["program_source"]))].append(
            Run("equivalence", f.parent.name, db2=db2, region=region)
        )
        for extra in case.get("programs", []):  # LINKed programs: det_port.py translates them the same way
            out[(case["corpus"], _norm(extra["program_source"]))].append(
                Run("equivalence", f.parent.name, role="linked", db2=db2, region=region)
            )
    return out


def load_det_baseline(path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = path or DET_BASELINE
    return json.loads(path.read_text(encoding="utf-8")).get("det", {}) if path.is_file() else {}


def load_sweeps(dirs: list[Path]) -> dict[str, dict[str, Any]]:
    """case -> its det sweep row (proved, coverage, translated) plus `report` (the proof's report.json path)."""
    out: dict[str, dict[str, Any]] = {}
    for d in dirs:
        f = d / "sweep.json" if d.is_dir() else d
        root = f.parent
        for case, row in json.loads(f.read_text(encoding="utf-8")).get("det", {}).items():
            rep = root / "det" / case / "proof" / "report.json"
            out[case] = dict(row, report=str(rep) if rep.is_file() else None)
    return out


def coverage_of(line: str) -> tuple[int, int, int, int] | None:
    """A proof's coverage line -> (paragraphs covered, live, branches covered, total)."""
    m = _COV.search(line or "")
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def ledger_coverage(case: str, cases_dir: Path = CASES) -> tuple[int, int, int, int] | None:
    """The det sweep's coverage of the case from the committed ledger (det_coverage_ledger.py), while it is fresh."""
    import det_coverage_ledger as dcl

    if cases_dir != CASES:  # a fixture tree: fingerprints are the repo's
        return None
    return dcl.fresh_coverage(case, dcl.load())


def evidence_coverage(case: str, cases_dir: Path = CASES) -> tuple[int, int, int, int] | None:
    f = cases_dir / case / "evidence.json"
    if not f.is_file():
        return None
    cov = json.loads(f.read_text(encoding="utf-8")).get("coverage") or {}
    p, b = cov.get("paragraphs") or {}, cov.get("branches") or {}
    if "live" not in p:
        return None
    return p.get("covered", 0), p["live"], b.get("covered", 0), b.get("total", 0)


def diff_kind(report: str | None) -> str:
    """The first differing scenario's event kind and field root (`RETURN commarea`), from a proof's report.json."""
    if not report:
        return "not proven (no report kept)"
    rep = json.loads(Path(report).read_text(encoding="utf-8"))
    if rep.get("java_failed"):
        return "java side failed"
    for out in (rep.get("outputs") or {}).values():
        for d in out.get("diffs") or []:
            fields = d.get("fields") or [{}]
            root = re.split(r"[.\[]", str(fields[0].get("field", "")) or "?")[0]
            return f"{d.get('kind') or d.get('event') or 'output'} {root}".strip()
    return "not proven (no diff recorded)"


def judge_equivalence(run: Run, det_baseline: dict[str, dict[str, Any]], sweeps: dict[str, dict[str, Any]],
                      branches: bool, cases_dir: Path = CASES) -> None:  # fmt: skip
    """Fill run.gaps for an equivalence case's det port."""
    row = sweeps.get(run.case)
    base = det_baseline.get(run.case)
    if row is not None and not row.get("proved"):
        if base is not None:
            g = f"known unproven: {base.get('issue') or 'no issue'}"
            run.gaps.add(g)
            run.detail[g] = f"{base.get('why', '')} [sweep: {diff_kind(row.get('report'))}]"
        else:
            g = f"scenario differs: {diff_kind(row.get('report'))}"
            run.gaps.add(g)
    elif row is None and base is not None:
        g = f"known unproven: {base.get('issue') or 'no issue'}"
        run.gaps.add(g)
        run.detail[g] = base.get("why", "")
    elif row is None and run.db2:
        run.gaps.add("not proven in CI: Db2 case (det-sweep runs --skip-db2)")
    if row is not None:
        t, _, s = str(row.get("translated", "")).partition("/")
        if t.isdigit() and s.isdigit() and int(t) < int(s):
            run.gaps.add("holes in the case's det port")
    cov = coverage_of(row.get("coverage", "")) if row else None
    cov = cov or ledger_coverage(run.case, cases_dir) or evidence_coverage(run.case, cases_dir)
    coverage_gaps(run, cov, branches)


def coverage_gaps(run: Run, cov: tuple[int, int, int, int] | None, branches: bool) -> None:
    if cov is None:
        if not any(g.startswith(("known unproven", "scenario differs", "not proven")) for g in run.gaps):
            run.gaps.add("coverage: unknown (no sweep, no evidence record)")
        return
    pc, pl, bc, bt = cov
    if pc < pl:
        g = "coverage: live paragraphs no scenario runs"
        run.gaps.add(g)
        run.detail[g] = f"{pc}/{pl} paragraphs"
    if branches and bc < bt:
        g = "coverage: branch outcomes no scenario runs"
        run.gaps.add(g)
        run.detail[g] = f"{bc}/{bt} branches"


def cell_kind(reason: str) -> str:
    """A crucible cell's failure reason without its task, event number, literals and numbers: the kind of diff."""
    why = re.sub(r"^task \d+ \([^)]*\)(?: event \d+)?:\s*", "", reason)
    why = re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", why)
    return re.sub(r"\b\d+\b", "N", why).strip()


def crucible_runs(crucible_dir: Path = CRUCIBLE, branches: bool = False) -> dict[tuple[str, str], Run]:
    """(crucible case, PROGRAM) -> its det port's proof subject, judged from the committed baseline / coverage."""
    cells = json.loads((crucible_dir / "baseline.json").read_text(encoding="utf-8")).get("cells", {})
    cov = json.loads((crucible_dir / "coverage.json").read_text(encoding="utf-8")).get("programs", {})
    ports = crucible_dir / "ports"
    out: dict[tuple[str, str], Run] = {}
    for key, prog in cov.items():
        case, _, name = key.partition("/")
        run = Run("crucible", case)
        if not (ports / case / name).is_dir():
            run.gaps.add("no det port (crucible)")
        for cell, v in cells.items():
            c, _, rest = cell.partition("/")
            if c == case and rest.endswith("/java-ported") and "no det port (crucible)" not in run.gaps:
                g = "scenario differs: " + cell_kind(v.get("reason", ""))
                run.gaps.add(g[:110])
        scen = (prog.get("scenarios") or {}).values()
        units = {u for s in scen for u in s.get("units", [])}
        outcomes = {o for s in scen for o in s.get("outcomes", [])}
        if not run.gaps:
            coverage_gaps(run, (len(units), prog.get("live", 0), len(outcomes), prog.get("outcomes", 0)), branches)
        out[(case, name.upper())] = run
    return out


# ---- runtime facts ----------------------------------------------------------------------------------------------
def facts_needed(text: str) -> dict[str, set[str]]:
    """The runtime facts a program reads, by kind: `eib` (EIB fields no harness states), `assign_task` (ASSIGN
    options an equivalence case cannot state yet), `assign_region` (ASSIGN APPLID / SYSID). Names only."""
    code = cc.fixed_format_text(text)
    eib = {m for m in _EIB.findall(code) if m in EIB_FIELDS and m not in STATED_EIB}
    task, region = set(), set()
    for cmd in cc.commands(text):
        opts = cc.options_of(cmd, ["ASSIGN"])
        for o in opts or ():
            if o in ASSIGN_TASK_FACTS:
                task.add(ASSIGN_TASK_FACTS[o])
            elif o in ASSIGN_REGION_FACTS:
                region.add(o)
    return {"eib": eib, "assign_task": task, "assign_region": region}


def fact_gaps(facts: dict[str, set[str]], run: Run | None) -> set[str]:
    """The fact gaps of a program under one proof subject (None: no case yet -- what a new case would need that no
    case can state)."""
    case_states = run is None or run.kind == "equivalence"  # a new equivalence case would state them too
    out = {
        f"fact: {e} (no harness states it)" for e in facts.get("eib", ()) if not (case_states and e in CASE_STATED_EIB)
    }
    if case_states:
        out |= {f"fact: ASSIGN {f} (no equivalence case states it)" for f in facts.get("assign_task", ())}
    if run is not None and run.kind == "equivalence" and facts.get("assign_region") and not run.region:
        out.add("fact: ASSIGN APPLID/SYSID (the case states no region)")
    return out


# ---- the ranking ------------------------------------------------------------------------------------------------
def program_gaps(key: tuple[str, str], eq: dict[tuple[str, str], list[Run]], cru: dict[tuple[str, str], Run],
                 facts: dict[str, set[str]]) -> tuple[set[str], Run | None]:  # fmt: skip
    """The gaps of one whole program: those of the proof subject with the fewest, or {"no case"}."""
    corpus, prog = key
    runs = list(eq.get((corpus, _norm(prog)), []))
    m = _CRUCIBLE_PATH.search(prog.replace("\\", "/"))
    if is_crucible(corpus) and m and (m.group(1), m.group(2).upper()) in cru:
        runs.append(cru[(m.group(1), m.group(2).upper())])
    if not runs:
        return {"no case"} | fact_gaps(facts, None), None
    scored = [(r.gaps | fact_gaps(facts, r), r) for r in runs]
    scored.sort(key=lambda t: (len(t[0]), t[1].role != "program", t[1].case))
    return scored[0]


def rank(progs: dict[tuple[str, str], tuple[bool, set[str]]]) -> dict[str, Any]:
    """`progs`: (corpus, program) -> (burned, gaps). The same statistics as cics_census.blockers, for proofs."""
    stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hist: dict[int, int] = defaultdict(int)
    for b, gaps in progs.values():
        hist[len(gaps)] += 1
        tag = "burned" if b else "non_burned"
        for g in gaps:
            st = stats[g]
            st["touched"] += 1
            st[f"touched_{tag}"] += 1
            if len(gaps) <= 2:
                which = "only" if len(gaps) == 1 else "one_away"
                st[which] += 1
                st[f"{which}_{tag}"] += 1
    keys = ("only", "only_burned", "only_non_burned", "one_away", "one_away_burned", "one_away_non_burned",
            "touched", "touched_burned", "touched_non_burned")  # fmt: skip
    ranked: list[dict[str, Any]] = [{"gap": g, **{k: st.get(k, 0) for k in keys}} for g, st in stats.items()]
    ranked.sort(key=lambda d: (-d["only"], -d["only_non_burned"], -d["one_away"], -d["touched"], d["gap"]))
    nb = [k for k, (b, _) in progs.items() if not b]
    return {
        "whole": len(progs),
        "whole_non_burned": len(nb),
        "proven": sum(not g for _, g in progs.values()),
        "proven_non_burned": sum(not progs[k][1] for k in nb),
        "histogram": {str(n): hist[n] for n in sorted(hist)},
        "gaps": ranked,
    }


def is_crucible(corpus: str) -> bool:
    """A surveyed cics-crucible clone: our own benchmark, ranked apart from the estates (neither burned nor not)."""
    return "crucible" in corpus.lower()


def read_text(roots: list[Path], corpus: str, program: str) -> str | None:
    from gitgalaxy.core.source_text import read_source

    for root in roots:
        p = root / corpus / program
        if p.is_file():
            try:
                return read_source(p).text
            except OSError:
                return None
    return None


def proof_blockers(rows: dict[tuple[str, str], dict[str, Any]], roots: list[Path], *, only_cics: bool = True,
                   sweeps: dict[str, dict[str, Any]] | None = None, branches: bool = False,
                   cases_dir: Path = CASES, crucible_dir: Path = CRUCIBLE,
                   det_baseline: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:  # fmt: skip
    """The proof-level ranking over the WHOLE programs of a survey (`rows`: cics_census.load_surveys)."""
    sweeps = sweeps or {}
    det_baseline = load_det_baseline() if det_baseline is None else det_baseline
    eq = equivalence_runs(cases_dir)
    for runs in eq.values():
        for r in runs:
            judge_equivalence(r, det_baseline, sweeps, branches, cases_dir)
    cru = crucible_runs(crucible_dir, branches) if (crucible_dir / "baseline.json").is_file() else {}
    burned = cc.burned_names()
    progs: dict[tuple[str, str], tuple[bool, set[str]]] = {}
    subjects: dict[tuple[str, str], dict[str, Any]] = {}
    skipped_not_cics = unreadable = 0
    for key, row in sorted(rows.items()):
        if not cc.whole(row):
            continue
        text = read_text(roots, *key)
        unreadable += text is None
        if only_cics and text is not None and not cc.commands(text):
            skipped_not_cics += 1
            continue
        facts = facts_needed(text) if text is not None else {}
        gaps, run = program_gaps(key, eq, cru, facts)
        progs[key] = (cc.is_burned(key[0], burned), gaps)
        subjects[key] = {"case": run.case if run else None, "kind": run.kind if run else None,
                         "detail": {g: run.detail[g] for g in gaps if run and g in run.detail}}  # fmt: skip
    estate = {k: v for k, v in progs.items() if not is_crucible(k[0])}
    res = rank(estate)
    res["crucible"] = rank({k: v for k, v in progs.items() if is_crucible(k[0])})
    res["scope"] = "programs with an EXEC CICS command" if only_cics else "every surveyed program"
    res["not_cics"] = skipped_not_cics
    res["unreadable"] = unreadable
    res["sources"] = {"sweeps": len(sweeps), "equivalence_cases": len({r.case for v in eq.values() for r in v}),
                      "crucible_programs": len(cru)}  # fmt: skip
    res["programs"] = [
        {"corpus": k[0], "program": k[1], "burned": b, "gaps": sorted(g), **subjects[k]}
        for k, (b, g) in sorted(progs.items(), key=lambda kv: (len(kv[1][1]), kv[1][0], kv[0]))
    ]
    return res


def print_ranking(r: dict[str, Any], top: int, split: bool = True) -> None:
    hdr = f"{'only gap (B/NB)':>16} {'one away (B/NB)':>16}" if split else f"{'only gap':>8} {'one away':>8}"
    print(f"{hdr} {'touched':>8}  proof gap")
    for g in r["gaps"][: top or None]:
        if split:
            print(f"{g['only']:>6} ({g['only_burned']:>2}/{g['only_non_burned']:>2}) {g['one_away']:>6} "
                  f"({g['one_away_burned']:>2}/{g['one_away_non_burned']:>2}) {g['touched']:>8}  {g['gap'][:110]}")  # fmt: skip
        else:
            print(f"{g['only']:>8} {g['one_away']:>8} {g['touched']:>8}  {g['gap'][:110]}")


def print_report(res: dict[str, Any], top: int, label: str) -> None:
    print(f"# proof blockers in {label}: {res['scope']} translated WHOLE")
    print(f"estates: translated whole {res['whole']} (non-burned {res['whole_non_burned']}); proven {res['proven']} "
          f"(non-burned {res['proven_non_burned']})")  # fmt: skip
    print("distinct proof gaps per program: " + ", ".join(f"{n}: {c}" for n, c in res["histogram"].items()))
    src = res["sources"]
    print(f"sources: {src['sweeps']} swept cases, {src['equivalence_cases']} equivalence cases, "
          f"{src['crucible_programs']} crucible programs" + ("" if src["sweeps"] else
          "; no --sweep: non-Db2 cases outside det_sweep_baseline.json taken as proven by main's CI ratchet"))  # fmt: skip
    if res.get("unreadable"):
        print(f"programs whose source was not found (facts not read): {res['unreadable']}")
    print()
    print_ranking(res, top)
    proven = [p for p in res["programs"] if not p["gaps"] and not is_crucible(p["corpus"])]
    if proven:
        print("\nproven: " + ", ".join(f"{Path(p['program']).stem} ({p['case']})" for p in proven))
    cru = res["crucible"]
    if cru["whole"]:
        print(f"\n## cics-crucible (surveyed clone): translated whole {cru['whole']}, proven {cru['proven']}")
        print_ranking(cru, top, split=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="a cics_census.py survey directory (DIR/<label>-*/survey.json)")
    ap.add_argument("--label", nargs="+", default=["before"], help="the survey run prefix(es) (default: before)")
    ap.add_argument("--sweep", type=Path, nargs="*", default=[], help="proof_sweep.py --det-only work directories "
                    "(or sweep.json files): their verdicts and coverage replace main's CI ratchet")  # fmt: skip
    ap.add_argument("--branches", action="store_true", help="count uncovered branch outcomes as a gap too")
    ap.add_argument("--all-programs", action="store_true", help="every whole program, not only the CICS ones")
    ap.add_argument("--corpora", type=Path, help="the burned / local corpora root (as cics_census.py)")
    ap.add_argument("--census-corpora", type=Path, help=f"the census clones (default: ${cc.CENSUS_ENV})")
    ap.add_argument("--no-census", action="store_true", help="read no census clone (their facts stay unread)")
    ap.add_argument("--extra-root", type=Path, nargs="*", default=[], help="more corpora roots to read sources from "
                    "(e.g. the directory holding a surveyed cics-crucible clone)")  # fmt: skip
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for label in args.label:
        rows.update(cc.load_surveys(args.dir, label))
    if not rows:
        raise SystemExit(f"no {'/'.join(args.label)}-*/survey.json under {args.dir} (run `cics_census.py survey "
                         f"--out {args.dir} --label ...` first)")  # fmt: skip
    roots = [cc.mainframe_root(args.corpora)]
    census = cc.census_root(args.census_corpora, required=False) if not args.no_census else None
    roots += ([census] if census else []) + list(args.extra_root)
    res = proof_blockers(rows, roots, only_cics=not args.all_programs, sweeps=load_sweeps(args.sweep),
                         branches=args.branches, cases_dir=CASES, crucible_dir=CRUCIBLE)  # fmt: skip
    if args.json:
        print(json.dumps(res, indent=1))
    else:
        print_report(res, args.top, f"{args.dir}/{'+'.join(args.label)}-*")
    return 0


if __name__ == "__main__":
    sys.exit(main())
