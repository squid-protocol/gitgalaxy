#!/usr/bin/env python3
"""#4493: the equivalence harness reports on itself -- how much of an estate it can test, what ran, and what stops the rest.

    python tests/tools/harness_report.py PROOF_BLOCKERS.json --out DIR [--estate NAME] [--cases-dir DIR]
    python tests/tools/harness_report.py --survey DIR [--label before ...] [--sweep SWEEP ...] --out DIR

PROOF_BLOCKERS.json is `proof_blockers.py DIR --json` (nothing is re-derived here: the gaps, cases and verdicts are its).
`--survey DIR` runs proof_blockers on a `cics_census.py survey` directory first. Writes DIR/harness_report.{md,json}.
The page is generated output: it is not committed. evidence-refresh.yml builds it nightly after its survey (`--survey`)
and publishes it to the `generated` branch under docs/language_status/harness/ (#4493).

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
import re
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
    if gap == "cobc: does not compile":
        why = clip("; ".join(sorted(set(details))) or "no diagnostic recorded")
        return f"Make the COBOL of {noun} compile under cobc ({why}; fix the source, a copybook or the compile options): {who} (cases: {', '.join(cases)})."  # fmt: skip
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


# Issue classes 1 (qualified names, formats a PICTURE cannot say) and 3 (cross-record business rules) are left
# unclassified on purpose: the burned `@generate` records hold no duplicate field name and every case states its
# rules (`digits`, `date`, `values`, single-field `from`), so no burned program needs a cause for them (checked
# 2026-10-18; test_burned_generated_inputs_need_no_class_1_or_3_cause). When one does, add its cause to
# record_cause / FIX_LAYOUT and that test's guard moves with it.
# ---- what stops an input being generated (#4493 blocker classes 1 and 2) --------------------------------------------
FIX_LAYOUT = {
    "redefines": "State a hand rule for the field that selects the REDEFINES alternative (the generator fills the first)",
    "renames": "Extend the layout model to RENAMES (#4266)",
    "sync": "Extend the layout model to SYNC (#4266)",
    "unresolved copy": "Connect the unresolved COPY member (or the COPY ... REPLACING)",
    "no layout": "Name a record the copybook holds",
    "not read": "Provide the corpus checkout so the layout can be read",
}
NON_VSAM_FIX = {
    "db2": "Provide DDL or sample rows for the Db2 tables (generated rows cover only some programs)",
    "mq": "Add an MQ queue model for the input messages (no generated MQ inputs yet)",
    "ims": "Add IMS segment inputs (not generated yet)",
    "recfm v": "Add variable-length (RECFM V) record generation",
    "gdg": "Add generation-data-group inputs",
}
_REDEF = re.compile(r"\bREDEFINES\b", re.I)
_SYNC = re.compile(r"\bSYNC(?:HRONIZED)?\b", re.I)
_LEVEL66 = re.compile(r"^.{6}\s*66\s", re.M)
_RECORD_START = re.compile(r"^.{6}\s*(?:01|77)\s")


def _record_text(text: str, record: str) -> str:
    """The lines of one 01 record: from its header to the next 01/77 (the whole text when it is not found)."""
    lines = text.splitlines()
    head = re.compile(rf"^.{{6}}\s*01\s+{re.escape(record)}\b", re.I) if record else _RECORD_START
    start = next((i for i, ln in enumerate(lines) if head.match(ln)), 0)
    end = next((i for i in range(start + 1, len(lines)) if _RECORD_START.match(lines[i])), len(lines))
    return "\n".join(lines[start:end])


_SELECTOR_NAME = re.compile(r"(?:^|-)(?:TYPE|CODE|ID|REQUEST|FLAG|IND|KIND|STATUS|SW|SWITCH)(?:-|$)")


def redefines_choices(items: list[dict[str, Any]], record: str = "") -> list[str]:
    """REDEFINES alternatives that another field selects, one line each: `TARGET -> ALT1/ALT2 (selector SEL)`.

    Chosen means a group alternative (a different layout over the target's bytes) or 2+ items over one target; a
    same-bytes elementary re-view (X(8) read as 9(8)) and a FILLER are not: the first alternative the generator fills
    already holds them. The selector is the nearest preceding sibling that owns 88-level values, else one whose name
    says it is a code (`(selector not found)` when none)."""
    roots = [i for i in items if i["parent"] is None and i["level"] not in (66, 88)]
    root = next((r for r in roots if r["name"] == record), None) if record else None
    root = root or next((r for r in roots if not r.get("redefines")), None)
    if root is None:
        return []
    later = [r["line"] for r in roots if r["line"] > root["line"]]
    inside = [i for i in items if root["line"] <= i["line"] < (min(later) if later else 1 << 30)]
    has88 = {i["parent"] for i in inside if i["level"] == 88}
    has_kids = {i["parent"] for i in inside if i["level"] not in (66, 88)}
    by_target: dict[str, list[dict[str, Any]]] = {}
    for i in inside:
        if i.get("redefines") and i["level"] not in (66, 88) and i["name"] != "FILLER":
            by_target.setdefault(i["redefines"], []).append(i)
    out = []
    for target, alts in sorted(by_target.items()):
        if len(alts) < 2 and not any(a["ordinal"] in has_kids and not a.get("pic") for a in alts):
            continue
        t = next((i for i in inside if i["name"] == target and not i.get("redefines")), None)
        sibs = [i for i in inside if t and i["parent"] == t["parent"] and i["line"] < t["line"] and i["level"] != 88]
        sibs = [i for i in sibs if not i.get("redefines") and i["ordinal"] not in has_kids]
        pick = next((i for i in reversed(sibs) if i["ordinal"] in has88), None) or next(
            (i for i in reversed(sibs) if _SELECTOR_NAME.search(i["name"])), None
        )
        sel = f"selector {pick['name']}" if pick else "selector not found"
        out.append(f"{target} -> {'/'.join(a['name'] for a in alts)} ({sel})")
    return out


def copy_dirs(base: Path, case: dict[str, Any], cpy: str) -> list[Path]:
    """Where a COPY inside the record resolves, as the generator reads it (#5233): the file's own directory, the case's
    `copy_dirs`, then the corpus."""
    return [(base / cpy).parent, *(base / d for d in case.get("copy_dirs", [])), base]


def record_limit(roots: list[Path], case: dict[str, Any], dataset: str) -> tuple[str, str]:
    """(cause, symbols) of one generated record's layout limit: a key of FIX_LAYOUT or "", and the names involved."""
    gen = case["datasets"][dataset].get("generate") or {}
    corpus = case.get("corpus", "")
    base = next((r / corpus for r in roots if (r / corpus).is_dir()), None)
    cpy = gen.get("copybook") or case["datasets"][dataset].get("copybook", "")
    if base is None or not (base / cpy).is_file():
        return "not read", ""
    import equivalence_common as common

    record = gen.get("record") or case["datasets"][dataset].get("record") or None
    try:
        common.layout_fields(base, cpy, record, copy_dirs=copy_dirs(base, case, cpy))
    except common.LayoutError as e:
        return ("no layout" if "no record" in str(e) else "unresolved copy"), ""
    from gitgalaxy.core.source_text import read_source

    text = _record_text(read_source(base / cpy).text, record or "")
    if _LEVEL66.search(text):
        return "renames", ""
    if _SYNC.search(text):
        return "sync", ""
    if _REDEF.search(text) and not gen.get("fields"):  # a case that states field rules has chosen what to fill
        import cobol_answer_key as ak

        path = base / cpy
        lines = common._expanded_lines(path, copy_dirs(base, case, cpy), [])
        items = list(ak._data_items(ak.Source(path, list(enumerate(lines, 1)))))
        if chosen := redefines_choices(items, record or ""):
            return "redefines", "; ".join(chosen)
    return "", ""


def record_cause(roots: list[Path], case: dict[str, Any], dataset: str) -> str:
    """Why one generated record's layout is limited: a key of FIX_LAYOUT, or "" when nothing applies."""
    return record_limit(roots, case, dataset)[0]


def non_vsam_kinds(case: dict[str, Any]) -> list[str]:
    """The inputs of a case that are not fixed-length data a layout generates: Db2 rows, MQ, IMS, RECFM V, GDGs."""
    kinds = {k for k in ("db2", "mq", "ims") if case.get(k) is not None}
    for dd, spec in (case.get("datasets") or {}).items():
        if str(spec.get("record_format", "")).upper().startswith("V"):
            kinds.add("recfm v")
        if spec.get("gdg") or re.search(r"\(\+?-?\d+\)", dd):
            kinds.add("gdg")
    return sorted(kinds)


def input_blockers(
    rows: list[dict[str, Any]], inputs: dict[str, dict[str, Any]], tests: dict[str, int]
) -> list[dict[str, Any]]:
    """Input-generation limits grouped by cause, stated as the fix, with the programs and tests they sit under."""
    by: dict[str, dict[str, Any]] = {}
    for c, i in inputs.items():
        found = [
            (
                r["cause"],
                f"{r['dataset']} ({r['record'] or r['copybook']})" + (f": {r['symbols']}" if r.get("symbols") else ""),
            )
            for r in i.get("records", [])
            if r["cause"]
        ]
        found += [(k, "case input") for k in i.get("non_vsam", [])]
        for cause, what in found:
            b = by.setdefault(cause, {"cases": set(), "items": [], "programs": set()})
            b["cases"].add(c)
            b["items"].append(f"{c}: {what}")
            b["programs"].update(r["program"] for r in rows if r["case"] == c)
    out = []
    for cause, b in by.items():
        cases = sorted(b["cases"])
        fix = FIX_LAYOUT.get(cause) or NON_VSAM_FIX[cause]
        out.append({"cause": cause, "fix": f"{fix}: {len(b['items'])} input(s) in {', '.join(cases)}.",
                    "items": sorted(b["items"]), "cases": cases, "programs": sorted(b["programs"]),
                    "tests_held": sum(tests.get(c, 0) for c in cases)})  # fmt: skip
    return sorted(out, key=lambda b: (-b["tests_held"], b["cause"]))


LINK_FIX = "Connect the unresolved or ambiguous COPY member(s) so the programs translate whole: {names}"
STUB_FIX = "Model or stub the runtime service the translator leaves a hole for: {names}"


def untranslated_cause(klass: str) -> str:
    """The #4493 blocker class of one translation gap class (`cics_census.gap_classes`): `unresolved link` (class 4:
    a COPY member the engine did not connect), `no stub` (class 5: a CICS / Db2 / IMS service nothing models),
    `refused` (the translator refuses the construct by name) or `hole` (an unmodelled statement)."""
    if klass.startswith(("missing copybook", "refused: CopyUnresolved")):  # CopyUnresolved: #4468
        return "unresolved link"
    if klass.startswith("refused:"):
        return "refused"
    if klass.startswith(("EXEC CICS", "EXEC SQL", "EXEC DLI", "CALL CBLTDLI")):
        return "no stub"
    return "hole"


_COPY_NAME = re.compile(r"\bCOPY\s+([A-Z0-9@#$_-]+)", re.I)


def unresolved_detail(p: dict[str, Any]) -> str:
    """` [COPY NAME: why]` for a program refused over a COPY member (the gap class of a CopyUnresolved refusal drops
    the name), from the survey row's error; empty when the row carries none."""
    err = p.get("error") or ""
    m = _COPY_NAME.search(err)
    if not err.startswith("Copy") or not m:
        return ""
    why = err.split(f"COPY {m.group(1)}", 1)[-1].lstrip(": ").strip()
    return f" [COPY {m.group(1).upper()}{': ' + clip(why, 120) if why else ''}]"


def untranslated_blockers(res: dict[str, Any]) -> list[dict[str, Any]]:
    """Programs the translator refused or left holes in, which have no proof subject, grouped by cause (each program
    under ONE cause: its first class) and stated as the fix. Burned, non-crucible programs only. No case exists to
    unlock, so the count is the programs that would become provable subjects."""
    from proof_blockers import is_crucible

    by: dict[str, dict[str, Any]] = {}
    for p in res.get("untranslated", []):
        if is_crucible(p["corpus"]) or not p.get("burned") or not p["classes"]:
            continue
        cause = untranslated_cause(p["classes"][0])
        b = by.setdefault(cause, {"programs": set(), "items": set()})
        b["programs"].add(p["program"])
        b["items"].add(f"{p['program']}: {'; '.join(p['classes'])}{unresolved_detail(p)}")
    out = []
    for cause, b in by.items():
        names = sorted(b["programs"])
        fix = {"unresolved link": LINK_FIX, "no stub": STUB_FIX}.get(
            cause,
            "Teach the translator the construct it "
            + ("refuses" if cause == "refused" else "leaves a hole for")
            + ": {names}",
        )
        out.append({"cause": cause, "fix": fix.format(names=", ".join(names)) + ".",
                    "programs": names, "items": sorted(b["items"])})  # fmt: skip
    return sorted(out, key=lambda b: (-len(b["programs"]), b["cause"]))


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
def build(
    res: dict[str, Any], estate: str = "estate", cases_dir: Path = CASES, roots: list[Path] | None = None
) -> dict[str, Any]:
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
    for c, i in inputs.items():  # only when non-empty: an always-present empty key breaks exact-equality tests
        if i["generated"]:
            i["records"] = []
            for g in i["generated"]:
                cause, symbols = record_limit(roots or [], cases[c], g["dataset"])
                i["records"].append(g | {"cause": cause} | ({"symbols": symbols} if symbols else {}))
        if kinds := non_vsam_kinds(cases[c]):
            i["non_vsam"] = kinds
    rep = {
        "schema_version": SCHEMA_VERSION, "estate": estate, "scope": res.get("scope", ""),
        "coverage": coverage, "status_counts": statuses, "programs": rows, "inputs": inputs, "blockers": blockers,
        "not_listed": {"non_burned_programs": len([p for p in progs if not p.get("burned")]),
                       "note": "non-burned census programs are counted, never named (mainframe evidence policy)"},
    }  # fmt: skip
    if in_blockers := input_blockers(rows, inputs, tests):
        rep["input_blockers"] = in_blockers
    if untranslated := untranslated_blockers(res):
        rep["untranslated"] = untranslated
    return rep


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
    if rep.get("input_blockers"):
        out += ["", "### Input-generation blockers (highest value first)", ""]
        for n, b in enumerate(rep["input_blockers"], 1):
            out.append(f"{n}. {b['fix']} Holds back {b['tests_held']} tests across {len(b['programs'])} programs.")
            out += [f"   - {it}" for it in b["items"]]
    if rep.get("untranslated"):
        out += ["", "## Programs with no translation yet (no case can run them)", ""]
        for n, b in enumerate(rep["untranslated"], 1):
            out.append(f"{n}. {b['fix']} Frees {len(b['programs'])} programs to get a case.")
            out += [f"   - {it}" for it in b["items"]]
    nl = rep["not_listed"]
    out += ["", f"Not listed: {nl['non_burned_programs']} non-burned programs ({nl['note']}).", ""]
    return "\n".join(out)


def write_report(
    res: dict[str, Any], out: Path, estate: str = "estate", cases_dir: Path = CASES, roots: list[Path] | None = None
) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    rep = build(res, estate, cases_dir, roots)
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
    roots: list[Path] = []
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
        raise SystemExit(2)  # ap.error exits; CodeQL cannot see it
    if not roots:  # a PROOF_BLOCKERS.json run still reads the layouts when the corpora are here
        import cics_census as cc

        try:
            roots = [cc.mainframe_root(None)]
        except (SystemExit, OSError):
            roots = []
    for p in write_report(res, args.out, args.estate, args.cases_dir, roots).values():
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
