#!/usr/bin/env python3
"""#4601: the purchaser-facing evidence report -- per estate, a row per program, filled only from tool outputs.

    python tests/tools/evidence_report.py ESTATE [ESTATE ...] | --all [--out DIR]
                                          [--baseline [--sha SHA] [--root DIR] | --survey DIR [--label before]]
                                          [--sweep SWEEP_DIR ...] [--corpora DIR] [--census-corpora DIR]
                                          [--bar-paragraphs PCT] [--bar-branches PCT]
    python tests/tools/evidence_report.py --refresh            # rebuild the committed reports (no corpora needed)
    python tests/tools/evidence_report.py --check [--live]     # exit 1 when a committed report is not current
    python tests/tools/evidence_report.py --deltas [--live]    # Markdown: the level changes a refresh would make (exit 0)

A purchaser asks "how sure are you, and of what?". This report answers with LEVELS and the numbers under them, never
a yes / no: the oracle is GnuCOBOL plus the gitgalaxy CICS stub and models, not IBM z/OS, so every result carries the
caveats of docs/language_status/oracle_assumptions.md. Each program gets the highest level whose conditions hold
(cumulative; the bars are parameters, printed in the report):

  L0 inventoried               the program is in the estate's survey
  L1 translated whole          the det translator leaves no hole and does not refuse it (cics_census.py survey)
  L2 executed equivalent       a case runs it and the case's det port is equal on every scenario: main's CI det-sweep
                               ratchet (det_sweep_baseline.json) for a non-Db2 case; for a Db2 case a local
                               proof_sweep.py --sweep, else the Db2 sweep that last wrote its det-sweep coverage ledger
                               entry (#4758: the scheduled evidence refresh's Db2 job; the ledger holds proven cases
                               only), stale like its coverage (#4730). The case's #4048 evidence record is a reported
                               column, not a gate
  L3 + paragraph coverage      the det proof's scenarios execute >= the paragraph bar (default 100) of the live
                               paragraphs: the --sweep coverage line, else the det-sweep coverage ledger
                               (tests/equivalence/det_sweep_coverage.json, #4606) while its entry is fresh
  L4 + branch coverage         ... and >= the branch bar (default 100) of the branch outcomes NET of the case's
                               reviewed infeasible outcomes (tests/equivalence/infeasible_outcomes.json, #4602), listed
                               per program as stated assumptions; raw and net numbers both printed
  L5 + mutants accounted for   every surviving mutant of the det port accounted for (#4628: not built yet, so no
                               program is placed at L5; the report says "not yet measured")

Oracle backing is a separate per-program column, not a rung: per CICS command, spec entry full / name-only, a
hand-traced cics-crucible case both runtimes agree with; DIFFERS assumptions reached: not measured.

Sections (per program): translation, executed equivalence, coverage, oracle backing, assumptions relied on, residual
risk; per estate: the level histogram and totals (a burned estate is labelled as one: its ports were developed
against it), the #4514 migration dimensions not measured, reproducibility (translator commit, pins, oracle image,
the commands to regenerate the report and re-run every proof).

Sources (imported, not re-parsed): cics_census (survey rows, gap classes, holes), proof_blockers (which cases run a
program, the det verdict from det_sweep_baseline.json / a sweep, runtime facts), evidence (records and their computed
status), cics_spec_status (spec keys of a program's commands, entry kinds, X-register entries, crucible cases per
command), tests/cics_crucible/baseline.json (which runtime disagrees with a crucible case), oracle_assumptions.md's
summary table (statuses). #4493's JSON replaces the direct reads once it exists. This tool never writes an evidence
record or an approval.

What needs corpora (the survey row, the program's commands and runtime facts) or a sweep is MEASURED once and frozen
into report.json's `measured` block, with the evidence records' computed status and the coverage ledger's fresh
entries at build time; everything else is recomputed from the repo. So `--refresh` rebuilds every committed report
without corpora, and `--check` (tests/tools/test_evidence_report.py; CI runs this, owner decision on #4601) fails
when a committed report is not what the repo makes now. `--check --live` / `--refresh --live` also recompute the
records' status and the ledger's freshness (a harness, oracle or generator change stales every record; the
scheduled evidence-refresh job re-proves them and runs `--refresh --live`).

Only burned estates are committed (docs/language_status/evidence_report/<estate>/report.{md,json}). A non-burned
estate's report is written only with --out outside the repository: census repos never have anything but counts
committed. The rendered text never calls a program or estate "proven", "verified" or "guaranteed" (tested); text
quoted from other tools is reworded to this report's vocabulary.

A level whose coverage is the ledger's last measurement, stale on a SCHEDULED input (harness / oracle), is kept and marked
(`L3*`, #4730); stale on a BLOCKING input (case, corpus) it drops as before. `--check --live` (the release gate) fails
while any level is stale; `--deltas` reports stale vs current.

report.json (`gitgalaxy-evidence-report/1`): {format, estate, burned, bars, levels, oracle, not_measured, measured,
summary, programs: [{program, level, level_current, stale_since, stale_inputs, next, translation, equivalence, coverage, oracle_backing, assumptions,
residual, options}], assumptions_named, reproducibility, options}; validate() checks the shape. #4708: `options`
(per program and per estate) holds the effective compile / runtime options and where each came from (found at
<file>:<line> vs assumed), plus the declared option differences; a report committed before it has neither.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import cics_census as cc  # noqa: E402
import cics_spec_status as css  # noqa: E402
import evidence as ev  # noqa: E402
import proof_blockers as pb  # noqa: E402
from gitgalaxy.core.compiler_options import SEMANTIC_OPTIONS, compiler_options, parse_options  # noqa: E402
from gitgalaxy.core.estate_options import counts as estate_counts  # noqa: E402
from gitgalaxy.core.estate_options import effective_options, load_estate  # noqa: E402

FORMAT = "gitgalaxy-evidence-report/1"
OUT = REPO / "docs" / "language_status" / "evidence_report"
REGISTER = REPO / "docs" / "language_status" / "oracle_assumptions.md"
CRUCIBLE_BASELINE = REPO / "tests" / "cics_crucible" / "baseline.json"
CRUCIBLE_PIN = REPO / "tests" / "_cics_crucible_pin.py"
PIN_MANIFEST = REPO / "tests" / "crucible_pins.toml"  # #4597
DOCKERFILE = REPO / "tests" / "equivalence" / "gnucobol.Dockerfile"
CORPORA = REPO / "tests" / "cobol_mainframe" / "corpora.json"
DEFAULT_BARS = {"paragraphs": 100.0, "branches": 100.0}  # owner decision on #4601: strict
# #4602: an owner-reviewed per-case list of infeasible branch outcomes, which the bars will be taken net of once it lands
MUTATION = "not yet measured (#4628)"  # det-port mutation: the L5 hook
LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5"]

# #4514 (the whole-migration epic): each part adds a section here when it is built; until then, not measured.
NOT_MEASURED = [
    {
        "dimension": "data",
        "what": "data migration: VSAM / Db2 / sequential data converted and reconciled",
        "issue": "#4514",
    },
    {
        "dimension": "JCL streams",
        "what": "the batch job streams that run the programs (steps, utilities, restart)",
        "issue": "#4514",
    },
    {
        "dimension": "interfaces",
        "what": "the estate's external interfaces (MQ, files exchanged, web services, other systems)",
        "issue": "#4514",
    },
    {"dimension": "performance", "what": "throughput, latency and batch windows", "issue": "#4514"},
    {"dimension": "security", "what": "RACF / CICS security, user and transaction authorisation", "issue": "#4514"},
    {"dimension": "cutover", "what": "the switch-over plan: parallel run, fallback, data freeze", "issue": "#4514"},
]

_FORBIDDEN = re.compile(r"\b(proven|verified|guaranteed)\b", re.I)
_REWORD = {"proven": "shown equal", "verified": "checked", "guaranteed": "assured"}


def neutral(text: str) -> str:
    """Text quoted from another tool, in this report's vocabulary (no "proven" / "verified" / "guaranteed")."""
    return _FORBIDDEN.sub(lambda m: _REWORD[m.group(1).lower()], str(text))


def pct(n: int | None, d: int | None) -> float | None:
    return round(100.0 * n / d, 1) if n is not None and d else None


# ---- repo-derived inputs -----------------------------------------------------------------------------------------
def register(path: Path = REGISTER) -> dict[str, dict[str, str]]:
    """oracle_assumptions.md's summary table: id -> {area, entry, status} (the register's own words)."""
    out = {}
    for m in re.finditer(r"^\| ([A-Z]\d+) \| ([^|]*) \| (.*) \| ([^|]*) \| ([^|]*) \|$", path.read_text("utf-8"), re.M):
        out[m.group(1)] = {
            "area": m.group(2).strip(),
            "entry": neutral(m.group(3).strip()),
            "status": neutral(m.group(4).strip()),
        }
    return out


def crucible_disagreements(path: Path = CRUCIBLE_BASELINE) -> dict[str, set[str]]:
    """crucible case -> the sides with a cell that does not pass (the ratchet ledger: every cell not listed passes)."""
    out: dict[str, set[str]] = {}
    for cell in json.loads(path.read_text("utf-8")).get("cells", {}):
        case, _, rest = cell.partition("/")
        out.setdefault(case, set()).add(rest.rsplit("/", 1)[-1])
    return out


def oracle_pin(path: Path = DOCKERFILE) -> dict[str, str]:
    text = path.read_text("utf-8")
    arg = dict(re.findall(r'^ARG (\w+)="?([^"\n]*)"?$', text, re.M))
    return {"base_image": arg.get("BASE", ""), "package": arg.get("GNUCOBOL", ""), "compiler": arg.get("COBC", "")}


def crucible_pins() -> dict[str, str]:
    """The crucible pin manifest (#4597): crucible name -> pinned ref."""
    import tomllib

    if not PIN_MANIFEST.is_file():
        m = re.search(r'^PINNED_REF = "(.*)"', CRUCIBLE_PIN.read_text("utf-8"), re.M)
        return {"cics": m.group(1) if m else ""}
    return {k: v.get("ref", "") for k, v in sorted(tomllib.loads(PIN_MANIFEST.read_text("utf-8")).items())}


def corpus_ref(estate: str) -> str:
    return next((c["ref"] for c in json.loads(CORPORA.read_text("utf-8"))["corpora"] if c["name"] == estate), "")


# ---- measuring: what needs corpora or a sweep (frozen into report.json) ------------------------------------------
def measure(
    estate: str,
    rows: dict[tuple[str, str], dict[str, Any]],
    roots: list[Path],
    survey: dict[str, Any],
    sweeps: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """The estate's survey rows, each program's spec keys and runtime facts (read from its source, names only), the
    sweep verdicts used, and the evidence records' computed status now."""
    progs = []
    for (corpus, program), r in sorted(rows.items()):
        if corpus != estate:
            continue
        text = pb.read_text(roots, corpus, program)
        facts = pb.facts_needed(text) if text is not None else {}
        progs.append(
            {
                "program": program,
                "row": {k: r[k] for k in ("statements", "translated", "holes", "error", "kind") if k in r},
                "source_read": text is not None,
                "commands": sorted(css.program_keys(text)) if text is not None else [],
                "facts": {k: sorted(v) for k, v in facts.items()},
                "cards": compiler_options(text) if text is not None else [],  # #4708: the program's own CBL / PROCESS
            }
        )
    used = {r.case for runs in pb.equivalence_runs().values() for r in runs}
    swept = {
        c: {
            "proved": bool(s.get("proved")),
            "coverage": s.get("coverage", ""),
            "translated": s.get("translated", ""),
            "first_diff": neutral(pb.diff_kind(s.get("report"))),
            "uncovered": s.get("uncovered"),
        }
        for c, s in sweeps.items()
        if c in used
    }
    return {
        "survey": survey,
        "programs": progs,
        "sweeps": dict(sorted(swept.items())),
        "record_status": record_status(),
        "det_coverage": det_coverage(),
    }


def record_commit(case: str) -> str | None:
    """The commit the case's evidence record was proven at (its proof's harness_commit), a fallback for a ledger entry
    written before entries carried `measured_at`."""
    rec = ev.load(ev.equivalence_target(case))
    sha = ((rec or {}).get("proof") or {}).get("harness_commit") or ""
    return sha.split("+")[0] or None


def det_coverage() -> dict[str, Any]:
    """case -> the det sweep's coverage from the committed ledger (det_coverage_ledger.py, #4606 / #4730):
    [paragraphs covered, live, branches covered, total] while the entry is current;
    {"coverage": [...], "stale_inputs": [...], "stale_since": sha|None} while it is stale on SCHEDULED inputs only
    (harness / oracle: the last measurement, not re-checked); None (no entry, or a BLOCKING input -- case / corpus --
    changed, so it describes another program)."""
    import det_coverage_ledger as dcl

    ledger = dcl.load()
    used = sorted({r.case for runs in pb.equivalence_runs().values() for r in runs})
    out: dict[str, Any] = {}
    for case in used:
        last = dcl.last_coverage(case, ledger)
        if last is None or last["blocking"]:
            out[case] = None
        elif not last["stale_inputs"]:
            out[case] = list(last["coverage"])
        else:
            out[case] = {
                "coverage": list(last["coverage"]),
                "stale_inputs": list(last["stale_inputs"]),
                "stale_since": last["measured_at"] or record_commit(case),
            }
    return out


def record_status() -> dict[str, dict[str, Any]]:
    """case -> the evidence record's computed status (evidence.status, live: the tree now)."""
    out = {}
    for t in ev.targets():
        if t.kind == "crucible":
            continue
        st = ev.status(ev.load(t), t)
        out[t.case] = {"status": neutral(st["status"]), "stale": list(st["stale"])}
    return dict(sorted(out.items()))


# ---- building: everything else, from the repo --------------------------------------------------------------------
NOT_IN_CI = "not proven in CI"  # proof_blockers.judge_equivalence's gap for a Db2 case with no sweep row
LEDGER_VERDICT = (
    "Db2 det sweep, as the det-sweep coverage ledger last recorded it (tests/equivalence/det_sweep_coverage.json)"
)


def ledger_verdicts(eq: dict[Any, list[pb.Run]], ledger: dict[str, Any]) -> set[str]:
    """#4758: the Db2 cases whose det verdict is the ledger's. CI's per-PR det-sweep skips Db2 cases; the scheduled
    evidence refresh sweeps them in its `db2` job and `det_coverage_ledger.py update` writes an entry ONLY for a case
    that sweep proved equal on every scenario. So a Db2 case with no sweep row and no det_sweep_baseline.json entry
    whose ledger entry is readable (det_coverage(): current, or stale on a scheduled input only) takes "equal" from it,
    and its level is marked stale with that entry's coverage (#4730) -- a push refresh, which skips Db2, keeps it
    instead of reverting it to "not run". A blocking change (case, corpus) makes the entry unknown: "not run" again.
    Drops the "not proven in CI" gap of those runs."""
    out = set()
    for runs in eq.values():
        for run in runs:
            if ledger.get(run.case) is None:
                continue
            gone = {g for g in run.gaps if g.startswith(NOT_IN_CI)}
            if gone:
                run.gaps -= gone
                out.add(run.case)
    return out


def det_state(run: pb.Run, swept: dict[str, Any], ledgered: frozenset[str] | set[str] = frozenset()) -> dict[str, Any]:
    """The det port's verdict on one case, in this report's words."""
    gaps = sorted(g for g in run.gaps if not g.startswith("coverage:"))
    if not gaps:
        if run.case in swept:
            src = "local sweep (proof_sweep.py --det-only)"
        elif run.case in ledgered:
            src = LEDGER_VERDICT
        else:
            src = "CI det-sweep ratchet on main"
        return {"state": "equal", "source": src}
    out: dict[str, Any] = {"state": "not equal", "why": []}
    for g in gaps:
        if g.startswith("known unproven"):
            issue = g.split(":", 1)[1].strip()
            out["why"].append(
                f"ledgered as differing in det_sweep_baseline.json ({issue}): {neutral(run.detail.get(g, ''))}"
            )
        elif g.startswith("scenario differs"):
            kind = swept.get(run.case, {}).get("first_diff") or neutral(g.split(":", 1)[1].strip())
            out["why"].append(f"a scenario differs (first diff: {kind})")
        elif g.startswith("not proven in CI"):
            out["state"] = "not run"
            out["why"].append(
                "a Db2 case: CI's det-sweep skips Db2 cases, no local sweep was given and the det-sweep coverage "
                "ledger holds no current entry for it"
            )
        else:
            out["why"].append(neutral(g))
    return out


def record_summary(case: str, status: dict[str, Any] | None) -> dict[str, Any] | None:
    t = ev.equivalence_target(case)
    rec = ev.load(t)
    if rec is None:
        return None
    p = rec.get("proof") or {}
    outs = p.get("outputs") or {}
    fc = p.get("facade") or {}
    img = (rec.get("oracle") or {}).get("image") or {}
    cov = rec.get("coverage") or {}
    st = status or {"status": "not measured", "stale": []}
    return {
        "status_at_build": st["status"],
        "stale_inputs": st["stale"],
        "verdict": "all equal" if p.get("verdict") == "proven" else ("none" if not p else "not equal"),
        "runs": p.get("runs"),
        "fault_runs": p.get("fault_runs"),
        "scenarios": len(outs),
        "scenarios_equal": sum((o.get("equal") or 0) == (o.get("records") or 0) for o in outs.values()),
        "records_compared": sum(o.get("records") or 0 for o in outs.values()),
        "records_equal": sum(o.get("equal") or 0 for o in outs.values()),
        "java_failed": bool(p.get("java_failed")),
        "facade": {"runs": fc.get("runs"), "passed": fc.get("passed")} if fc else None,
        "db2": t.db2,
        "option_differences": [
            d for d in rec.get("differences") or [] if isinstance(d, dict) and d.get("kind") == "option"
        ],
        "oracle_image": img.get("id"),
        "oracle_matches_pin": img.get("matches_pin"),
        "coverage": {
            "paragraphs": cov.get("paragraphs"),
            "branches": cov.get("branches"),
            "uncovered_branches": [
                f"line {b['line']} {b['kind']} {b['outcome']} ({b['unit']})"
                for b in cov.get("uncovered_branches") or []
            ],
        }
        if cov
        else None,
    }


def case_scenarios(case: str) -> int | None:
    scen = ev._case_json(case).get("scenarios")
    return len(scen) if isinstance(scen, list) else None


def coverage_of(case: dict[str, Any] | None, swept: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    """Paragraph / branch coverage of the case's det proof: a local sweep's coverage line, else the det-sweep coverage
    ledger (fresh entries only). The evidence record's coverage is not used: the record is reported, not a gate."""
    out: dict[str, Any] = {
        "source": None,
        "paragraphs": None,
        "branches": None,
        "paragraph_pct": None,
        "branch_pct": None,
        "branches_net": None,
        "branch_net_pct": None,
        "infeasible_stated": [],
        "infeasible_netted": [],
        "infeasible_refuted": [],
        "uncovered_branches": [],
        "uncovered_paragraphs": "not recorded",
        "current": True,  # #4730: False = the numbers are the last measurement, stale on `stale_inputs`
        "stale_inputs": [],
        "stale_since": None,
    }
    # #4270: a case's coverage is its main program's, never a LINKed one's
    if case is None or case.get("role") == "linked":
        return out
    import infeasible_outcomes as io

    out["infeasible_stated"] = [
        {k: e[k] for k in ("key", "unit", "line", "kind", "outcome", "family", "reason")}
        for e in io.stated(case["case"])
    ]
    for e in out["infeasible_stated"]:
        e["reason"] = neutral(e["reason"])
    row = swept.get(case["case"], {})
    line = pb.coverage_of(row.get("coverage", ""))
    uncovered = row.get("uncovered") if line else None
    led = ledger.get(case["case"])
    if isinstance(led, dict):  # #4730: the last measurement, stale on a scheduled input
        out["current"], out["stale_inputs"], out["stale_since"] = (
            False,
            list(led["stale_inputs"]),
            led.get("stale_since"),
        )
        led = led["coverage"]
    if line:
        out["source"] = "local sweep coverage line"
        out["current"], out["stale_inputs"], out["stale_since"] = True, [], None
    elif led:
        out["source"] = "det-sweep coverage ledger (tests/equivalence/det_sweep_coverage.json)"
        line = tuple(led)
    else:
        return out
    out["paragraphs"] = {"covered": line[0], "live": line[1]}
    out["branches"] = {"covered": line[2], "total": line[3]}
    out["paragraph_pct"] = pct(out["paragraphs"]["covered"], out["paragraphs"]["live"])
    out["branch_pct"] = pct(out["branches"]["covered"], out["branches"]["total"])
    net, netted, refuted = io.adjust(case["case"], tuple(line), uncovered)  # type: ignore[arg-type]
    if net is not None:
        out["branches_net"] = {"covered": net[2], "total": net[3]}
        out["branch_net_pct"] = pct(net[2], net[3]) if net[3] else 100.0
    out["infeasible_netted"], out["infeasible_refuted"] = netted, refuted
    return out


def backing(commands: list[str], crucible: dict[str, list[str]], disagree: dict[str, set[str]]) -> list[dict[str, Any]]:
    cmds = css.spec()
    out = []
    for key in commands:
        c = cmds.get(key)
        entry = css.entry_kind(c) if c is not None else "no spec entry"
        cases = []
        for case in crucible.get(key, []):
            bad = disagree.get(case, set())
            cases.append(
                {"case": case, "stub_agrees": "cobol-stub" not in bad, "java_agrees": "java-ported" not in bad}
            )
        backed = entry == "full" and any(x["stub_agrees"] and x["java_agrees"] for x in cases)
        out.append(
            {
                "command": key,
                "spec_entry": entry,
                "crucible_cases": cases,
                "backed": backed,
                "registers": css.registers(c) if c is not None else [],
                "facts_stated": [f.name for f in c.facts] if c is not None else [],
            }
        )
    return out


def level_of(p: dict[str, Any], bars: dict[str, float]) -> tuple[str, list[str]]:
    """(the highest level whose conditions hold, what the next level needs)."""
    t, eq, cov = p["translation"], p["equivalence"], p["coverage"]
    if not t["whole"]:
        why = "refused whole by the translator" if t["refused"] else f"{t['hole_count']} holes left"
        return "L0", [f"translated whole ({why})"]
    case = eq["chosen"]
    if case is None:
        return "L1", ["an equivalence case that runs it"]
    if case["det"]["state"] != "equal":
        return "L1", ["its det port equal on every scenario of " + case["case"] + ": " + "; ".join(case["det"]["why"])]
    if cov["paragraph_pct"] is None and case.get("role") == "linked":
        why = "coverage not measured for a LINKed program: the case's coverage is its main program's"
        return "L2", [f"paragraph coverage >= {bars['paragraphs']} ({why})"]
    if cov["paragraph_pct"] is None:
        why = "coverage not measured: no fresh det-sweep ledger entry and no local sweep"
        return "L2", [f"paragraph coverage >= {bars['paragraphs']} ({why})"]
    if cov["paragraph_pct"] < bars["paragraphs"]:
        return "L2", [f"paragraph coverage >= {bars['paragraphs']} (now {cov['paragraph_pct']})"]
    if cov["infeasible_refuted"]:
        return "L3", [f"no refuted infeasible-outcome claim (reached: {', '.join(cov['infeasible_refuted'])})"]
    if cov["branch_net_pct"] is None or cov["branch_net_pct"] < bars["branches"]:
        why = f"now {cov['branch_pct']} raw, {cov['branch_net_pct']} net of the reviewed infeasible outcomes"
        return "L3", [f"branch coverage >= {bars['branches']} net ({why})"]
    return "L4", [f"every surviving mutant of the det port accounted for: {MUTATION}"]


# ---- options (#4708) ---------------------------------------------------------------------------------------------
# The options that change a program's RESULTS (SEMANTIC_OPTIONS: ARITH, INTDATE, NUMPROC, TRUNC, YEARWINDOW), plus the
# ones that change how its data is read. The rest of a PARM (LIST, MAP, XREF ...) changes no result and is not listed.
RESULT_OPTIONS = (*SEMANTIC_OPTIONS, "CODEPAGE", "DECIMAL-POINT", "NSYMBOL")
OPTION_SECTIONS = ("le", "db2", "cics")


def _provenance(source: str | None) -> str:
    return "assumed" if not source or str(source).startswith("assumed:") else "found"


def _card_text(cards: list[dict[str, Any]]) -> str:
    """The program's CBL cards as source text (what EffectiveOptions.values / .deviations read the cards from)."""
    return "\n".join(f"       CBL {c['written']}" for c in cards)


def program_options(case: dict[str, Any] | None, estate: str, program: str, cards: list[dict[str, Any]],
                    differences: list[dict[str, Any]] | None = None) -> dict[str, Any]:  # fmt: skip
    """#4708: one program's effective options -- the resolver's answer (gitgalaxy.core.estate_options) plus its own
    CBL / PROCESS cards -- each result-changing option with its value, origin and provenance."""
    case = case or {"corpus": estate}
    eff = effective_options(case, program=program)
    text = _card_text(cards)
    values = eff.values(text)
    on_card = {c["option"]: c for c in cards}
    case_opts = {o for t in case.get("compiler_options") or [] for o, _v, _w in parse_options(t)}
    rows = []
    for option in RESULT_OPTIONS:
        if option not in values and option not in on_card:
            continue
        if option in on_card:
            origin, source = "program card", f"{program}:{on_card[option]['line']}"
        elif option in case_opts:
            origin, source = "case compiler_options", "assumed: owner decision (the case's compiler_options)"
        elif option in eff.sources:
            origin, source = "estate options file", eff.sources[option]
        else:
            origin, source = "IBM default", "assumed: IBM default"
        rows.append({"option": option, "value": values.get(option), "origin": origin, "source": source,
                     "provenance": _provenance(source)})  # fmt: skip
    return {
        "estate_file": eff.estate is not None,
        "compiler": {k: v for k, v in eff.compiler.items()},
        "values": rows,
        "found": sum(r["provenance"] == "found" for r in rows),
        "assumed": sum(r["provenance"] == "assumed" for r in rows),
        "deviations": [
            {**d, "source": d["source"] or None, "note": "declared in the estate options file (applied_value)"}
            for d in eff.deviations(text)
        ],
        "record_differences": [
            {
                "option": d.get("option"),
                "declared": d.get("declared"),
                "applied": d.get("applied"),
                "note": neutral(d.get("note", "")),
            }
            for d in differences or []
        ],  # fmt: skip
    }


def estate_options(estate: str, progs: list[dict[str, Any]]) -> dict[str, Any]:
    """#4708: the estate-level options table -- compiler product / version, the PARM defaults, how many values the
    estate options file found in the corpus vs assumed, and the same count over the programs' result-changing options."""
    data = load_estate(estate)
    po = [p["options"] for p in progs]
    out: dict[str, Any] = {
        "estate_file": f"tests/equivalence/estate_options/{estate}.json" if data else None,
        "programs_found": sum(o["found"] for o in po),
        "programs_assumed": sum(o["assumed"] for o in po),
        "programs_with_deviation": sum(bool(o["deviations"] or o["record_differences"]) for o in po),
    }
    if not data:
        return out | {"compiler": None, "installation_defaults": [], "parm_default": [], "parm_programs": [],
                      "counts": None, "sections": {}}  # fmt: skip

    def entry(name: str, e: dict[str, Any]) -> dict[str, Any]:
        src = str(e.get("source"))
        return {"option": name, "value": e.get("value"), "applied_value": e.get("applied_value"), "source": src,
                "provenance": _provenance(src)}  # fmt: skip

    comp = data.get("compiler") or {}
    return out | {
        "compiler": {k: entry(k, comp[k]) for k in ("product", "version") if k in comp},
        "installation_defaults": [entry(k, v) for k, v in sorted((comp.get("installation_defaults") or {}).items())],
        "parm_default": [entry(e["option"], e) for e in (data.get("parm") or {}).get("default") or []],
        "parm_programs": sorted((data.get("parm") or {}).get("programs") or {}),
        "counts": estate_counts(data),
        "sections": {s: estate_counts({s: data.get(s) or {}}) for s in OPTION_SECTIONS},
    }


def build_program(m: dict[str, Any], estate: str, ctx: dict[str, Any]) -> dict[str, Any]:
    r, prog = m["row"], m["program"]
    whole = cc.whole(r)
    classes = sorted(cc.gap_classes(r)) if not whole else []
    translation = {
        "statements": r.get("statements"),
        "translated": r.get("translated"),
        "hole_count": len(r.get("holes") or []),
        "holes": [neutral(h) for h in cc.holes(r)],
        "whole": whole,
        "refused": neutral(cc.error_key(r["error"])) if "error" in r else None,
        "gap_classes": [neutral(g) for g in classes],
        "source_defects": [neutral(g) for g in classes if "source defect" in g.lower()],
    }
    runs = ctx["eq"].get((estate, pb._norm(prog)), [])
    cases = [
        {
            "case": run.case,
            "role": run.role,
            "db2": run.db2,
            "det": det_state(run, ctx["swept"], ctx["ledgered"]),
            "case_scenarios": case_scenarios(run.case),
            "record": record_summary(run.case, ctx["status"].get(run.case)),
        }
        for run in runs
    ]
    facts = m.get("facts") or {}
    p: dict[str, Any] = {
        "program": prog,
        "translation": translation,
        "oracle_backing": backing(m.get("commands", []), ctx["crucible"], ctx["disagree"]),
    }
    best: tuple[Any, ...] | None = None
    candidates: list[dict[str, Any] | None] = [*cases] or [None]
    for c in candidates:
        p["equivalence"] = {"cases": cases, "chosen": c}
        p["coverage"] = coverage_of(c, ctx["swept"], ctx["ledger"])
        lvl, nxt = level_of(p, ctx["bars"])
        key = (
            LEVELS.index(lvl),
            c is not None and c["role"] == "program",
            p["coverage"]["source"] is not None,
            c is not None and c["record"] is not None,
            -len(nxt),
        )
        if best is None or key > best[0]:
            best = (key, c, lvl, nxt, p["coverage"])
    if best is None:  # pragma: no cover -- the loop runs at least once
        raise RuntimeError("no candidate")
    _, chosen, lvl, nxt, cov = best
    p["equivalence"] = {"cases": cases, "chosen": chosen}
    p["coverage"] = cov
    p["level"], p["next"] = lvl, nxt
    # #4730: a level that rests on the ledger's last measurement (stale on a scheduled input) is shown, marked stale;
    # L0 / L1 do not read coverage, so they are always current. #4758: a Db2 case's det verdict read from the ledger
    # is that same measurement, so an L2 resting on it (a LINKed program, no coverage of its own) is stale with it.
    stale_in, stale_at = [], None
    if lvl not in ("L0", "L1"):
        led = ctx["ledger"].get(chosen["case"]) if chosen else None
        if cov["source"] is not None and not cov["current"]:
            stale_in, stale_at = list(cov["stale_inputs"]), cov["stale_since"]
        elif chosen and chosen["det"].get("source") == LEDGER_VERDICT and isinstance(led, dict):
            stale_in, stale_at = list(led["stale_inputs"]), led.get("stale_since")
    p["level_current"] = not stale_in
    p["stale_inputs"] = stale_in
    p["stale_since"] = stale_at
    # #4628: the det port's mutation score is the L5 hook. docs/language_status/mutation_scores.json covers the
    # model / hand ports only, so it is deliberately left out here (it says nothing about the det port).
    p["mutation"] = {"det_port": MUTATION}
    regs = sorted({x for b in p["oracle_backing"] for x in b["registers"]}, key=lambda x: int(x[1:]))
    region = bool(chosen and ev._case_json(chosen["case"]).get("region", {}).get("applid"))
    unstated = [f"EIB field {e} (both runtimes read zero; z/OS does not)" for e in facts.get("eib", [])]
    unstated += [f"ASSIGN {f} (no equivalence case states it)" for f in facts.get("assign_task", [])]
    if facts.get("assign_region") and not region:
        unstated.append("ASSIGN " + "/".join(facts["assign_region"]) + " (the case states no region)")
    chosen_case = ev._case_json(chosen["case"]) if chosen else None
    p["options"] = program_options(
        chosen_case,
        estate,
        prog,
        m.get("cards") or [],
        (chosen["record"] or {}).get("option_differences") if chosen and chosen["record"] else None,
    )
    p["assumptions"] = {
        "named_by_commands": [
            {"id": x, **ctx["register"].get(x, {"status": "no register row", "area": "", "entry": ""})} for x in regs
        ],
        "facts_stated": sorted({f for b in p["oracle_backing"] for f in b["facts_stated"]}),
        "facts_unstated": unstated,
        "reach": "not measured",
        "source_read": m.get("source_read", False),
    }
    risky = [a["id"] for a in p["assumptions"]["named_by_commands"] if re.search(r"ASSUMED|DIFFERS", a["status"])]
    p["residual"] = {
        "holes": translation["hole_count"],
        "refused": translation["refused"],
        "paragraphs_unrun": (cov["paragraphs"]["live"] - cov["paragraphs"]["covered"]) if cov["paragraphs"] else None,
        "branch_outcomes_unrun": (cov["branches"]["total"] - cov["branches"]["covered"]) if cov["branches"] else None,
        "facts_unstated": len(unstated),
        "assumed_or_differs_named": risky,
        "commands_not_backed": [b["command"] for b in p["oracle_backing"] if not b["backed"]],
        "commands": len(p["oracle_backing"]),
        "commands_backed": sum(b["backed"] for b in p["oracle_backing"]),
    }
    return p


def build(measured: dict[str, Any], estate: str, bars: dict[str, float], *, live: bool = False,
          now: tuple[Any, Any] | None = None) -> dict[str, Any]:  # fmt: skip
    """The report of one estate from its measured block and the repo (live: the records' status recomputed now)."""
    swept = measured.get("sweeps", {})
    status, ledger = (now or (record_status(), det_coverage())) if live else (
        measured.get("record_status", {}), measured.get("det_coverage", {}))  # fmt: skip
    eq = pb.equivalence_runs()
    sweeps = {c: {**s, "report": None} for c, s in swept.items()}
    det_base = pb.load_det_baseline()
    for runs in eq.values():
        for run in runs:
            pb.judge_equivalence(run, det_base, sweeps, True)
    ledgered = ledger_verdicts(eq, ledger)
    data = css.load_data()
    ctx = {
        "eq": eq,
        "swept": swept,
        "status": status,
        "ledger": ledger,
        "ledgered": ledgered,
        "bars": bars,
        "crucible": data.get("crucible", {}),
        "disagree": crucible_disagreements(),
        "register": register(),
    }
    progs = [build_program(m, estate, ctx) for m in measured["programs"]]
    progs.sort(key=lambda p: (-LEVELS.index(p["level"]), p["program"]))
    hist = Counter(p["level"] for p in progs)
    hist_stale = Counter(p["level"] for p in progs if not p["level_current"])
    named = sorted(
        {a["id"] for p in progs for a in p["assumptions"]["named_by_commands"]}, key=lambda x: (x[0], int(x[1:]))
    )
    images = sorted(
        {
            c["record"]["oracle_image"]
            for p in progs
            for c in p["equivalence"]["cases"]
            if c["record"] and c["record"]["oracle_image"]
        }
    )
    pin = oracle_pin()
    burned = cc.is_burned(estate)
    report = {
        "format": FORMAT,
        "estate": estate,
        "burned": burned,
        "bars": bars,
        "levels": level_table(bars),
        "oracle": {
            "what": "GnuCOBOL plus the gitgalaxy CICS stub and models (CICS, Db2 precompiler, Language "
            "Environment, DISPLAY), not IBM z/OS",
            **pin,
        },
        "not_measured": NOT_MEASURED,
        "mutation": MUTATION,
        "measured": measured,
        "summary": {
            "programs": len(progs),
            "histogram": {lv: hist.get(lv, 0) for lv in LEVELS},  # last measured, stale ones included (#4730)
            "histogram_stale": {lv: hist_stale.get(lv, 0) for lv in LEVELS},  # of which awaiting a re-check
            "levels_stale": sum(hist_stale.values()),
            "translated_whole": sum(p["translation"]["whole"] for p in progs),
            "refused_whole": sum(bool(p["translation"]["refused"]) for p in progs),
            "holes": sum(p["translation"]["hole_count"] for p in progs),
            "with_case": sum(bool(p["equivalence"]["cases"]) for p in progs),
            "with_record": sum(
                bool(p["equivalence"]["chosen"] and p["equivalence"]["chosen"]["record"]) for p in progs
            ),
            "records_current": sum(
                bool(
                    p["equivalence"]["chosen"]
                    and p["equivalence"]["chosen"]["record"]
                    and not p["equivalence"]["chosen"]["record"]["stale_inputs"]
                )
                for p in progs
            ),
            "det_equal": sum(
                bool(p["equivalence"]["chosen"] and p["equivalence"]["chosen"]["det"]["state"] == "equal")
                for p in progs
            ),
            "cics_programs": sum(bool(p["oracle_backing"]) for p in progs),
            "source_unread": sum(not m.get("source_read") for m in measured["programs"]),
        },
        "programs": progs,
        "options": estate_options(estate, progs),
        "assumptions_named": [
            {"id": x, **ctx["register"].get(x, {"status": "no register row", "area": "", "entry": ""})} for x in named
        ],
        "reproducibility": {
            "translator_commit": measured["survey"].get("sha"),
            "survey": measured["survey"],
            "corpus_ref": corpus_ref(estate),
            "crucible_pins": crucible_pins(),
            "crucible_baseline_ref": json.loads(CRUCIBLE_BASELINE.read_text("utf-8")).get("crucible_ref"),
            "crucible_cases_measured_at": (data.get("crucible_measured") or {}).get("ref"),
            "pin_manifest": "tests/crucible_pins.toml" if PIN_MANIFEST.is_file() else "not on this branch (#4597)",
            "oracle_base_image": pin["base_image"],
            "oracle_images_of_records": images,
            "record_status_from": "evidence.py status, recomputed now" if live else "evidence.py status at build time",
            "coverage_from": "det-sweep coverage ledger freshness recomputed now"
            if live
            else "det-sweep coverage ledger, freshness at build time",
            "commands": commands(estate, progs, measured),
        },
    }
    return report


def level_table(bars: dict[str, float]) -> list[dict[str, str]]:
    return [
        {"level": "L0", "name": "inventoried", "condition": "the program is in the estate's survey"},
        {
            "level": "L1",
            "name": "translated whole",
            "condition": "the det translator leaves no hole and does not refuse it",
        },
        {
            "level": "L2",
            "name": "executed equivalent",
            "condition": "a case runs it and the case's det port is equal on every scenario (CI's det-sweep ratchet on "
            "main; a Db2 case by a local sweep or the scheduled Db2 sweep's coverage ledger entry); the case's evidence "
            "record is reported, not required",
        },
        {
            "level": "L3",
            "name": "paragraph coverage",
            "condition": f"L2, and the scenarios execute >= {bars['paragraphs']} percent of its live paragraphs",
        },
        {
            "level": "L4",
            "name": "branch coverage",
            "condition": f"L3, and >= {bars['branches']} percent of its branch outcomes, net of the case's reviewed "
            "infeasible outcomes (listed under its assumptions)",
        },
        {
            "level": "L5",
            "name": "mutants accounted for",
            "condition": f"L4, and every surviving mutant of the det port accounted for: {MUTATION}",
        },
    ]


def commands(estate: str, progs: list[dict[str, Any]], measured: dict[str, Any]) -> list[str]:
    sha = measured["survey"].get("sha") or "SHA"
    cases = sorted({c["case"] for p in progs for c in p["equivalence"]["cases"]})
    db2 = sorted({c["case"] for p in progs for c in p["equivalence"]["cases"] if c["db2"]})
    recs = sorted({c["case"] for p in progs for c in p["equivalence"]["cases"] if c["record"]})
    out = [
        f"python tests/tools/cics_census.py survey --baseline --sha {sha}",
        f"python tests/tools/evidence_report.py {estate} --baseline --sha {sha}",
        "python tests/tools/evidence_report.py --refresh",
    ]
    if cases:
        out.append(
            f"python tests/tools/proof_sweep.py --det-only --work DIR --cases {','.join(cases)}"
            + ("" if not db2 else f"  # Db2 cases ({len(db2)}) need the Db2 container")
        )
    if recs:
        out.append(f"python tests/tools/evidence.py prove {' '.join(recs)}")
    out.append("python tests/tools/cics_crucible.py  # the hand-traced CICS cases, at the crucible pin")
    return out


# ---- validation --------------------------------------------------------------------------------------------------
def validate(rep: dict[str, Any], strict: bool = False) -> list[str]:
    """The shape. A report committed before #4730 has no level_current / stale_* / histogram_stale (every level then
    was current) until the evidence-refresh bot regenerates it; strict (a freshly built report) requires them."""
    errs = []
    need = (
        "format",
        "estate",
        "burned",
        "bars",
        "levels",
        "oracle",
        "not_measured",
        "measured",
        "summary",
        "programs",
        "assumptions_named",
        "reproducibility",
    )
    errs += [f"missing `{k}`" for k in need if k not in rep]
    if rep.get("format") != FORMAT:
        errs.append(f"format is {rep.get('format')!r}, not {FORMAT!r}")
    for i, p in enumerate(rep.get("programs", [])):
        for k in (
            "program",
            "level",
            "next",
            "translation",
            "equivalence",
            "coverage",
            "oracle_backing",
            "assumptions",
            "residual",
        ):
            if k not in p:
                errs.append(f"programs[{i}].{k} missing")
        if p.get("level") not in LEVELS:
            errs.append(f"programs[{i}].level {p.get('level')!r}")
        if "level_current" not in p and not strict:
            continue
        if not isinstance(p.get("level_current"), bool):
            errs.append(f"programs[{i}].level_current {p.get('level_current')!r}")
        elif "stale_since" not in p or "stale_inputs" not in p:
            errs.append(f"programs[{i}]: stale_since / stale_inputs missing")
        elif p["level_current"] and (p.get("stale_inputs") or p.get("stale_since")):
            errs.append(f"programs[{i}]: a current level names stale inputs")
        elif not p["level_current"] and not p.get("stale_inputs"):
            errs.append(f"programs[{i}]: a stale level names no stale inputs")
    # #4708: a report committed before the options section has none until the evidence-refresh bot regenerates it
    if "options" not in rep:
        if strict:
            errs.append("missing `options`")
    else:
        errs += option_errors(rep["options"], "options", ("estate_file", "programs_found", "programs_assumed"))
    for i, p in enumerate(rep.get("programs", [])):
        if "options" not in p:
            if strict:
                errs.append(f"programs[{i}].options missing")
            continue
        errs += option_errors(p["options"], f"programs[{i}].options", ("values", "found", "assumed", "deviations"))
        for r in p["options"].get("values", []):
            if r.get("provenance") not in ("found", "assumed"):
                errs.append(f"programs[{i}].options {r.get('option')}: provenance {r.get('provenance')!r}")
            elif r["provenance"] != _provenance(r.get("source")):
                errs.append(f"programs[{i}].options {r.get('option')}: provenance disagrees with source")
        o = p["options"]
        if o.get("found", 0) + o.get("assumed", 0) != len(o.get("values", [])):
            errs.append(f"programs[{i}].options: found + assumed is not the number of values")
    for k in ("survey", "programs", "sweeps", "record_status", "det_coverage"):
        if k not in rep.get("measured", {}):
            errs.append(f"measured.{k} missing")
    hs = rep.get("summary", {}).get("histogram_stale")
    if hs is None:
        if strict:
            errs.append("summary.histogram_stale missing")
    elif sum(hs.values()) != sum(not p.get("level_current", True) for p in rep.get("programs", [])):
        errs.append("summary.histogram_stale disagrees with the programs")
    return errs


def option_errors(o: Any, where: str, keys: tuple[str, ...]) -> list[str]:
    if not isinstance(o, dict):
        return [f"{where} is not an object"]
    return [f"{where}.{k} missing" for k in keys if k not in o]


# ---- rendering ---------------------------------------------------------------------------------------------------
def _n(x: Any) -> str:
    return "—" if x is None else str(x)


def lvl(p: dict[str, Any]) -> str:
    """A program's level as printed: `L3*` when it is the last measurement, stale (#4730)."""
    return p["level"] + ("" if p.get("level_current", True) else "*")


def stale_counts(s: dict[str, Any]) -> dict[str, int]:
    """summary.histogram_stale; a report committed before #4730 has none (every level was current)."""
    return s.get("histogram_stale") or dict.fromkeys(LEVELS, 0)


def cell(n: int, k: int) -> str:
    """A histogram cell: the count, with how many of them await a re-check."""
    return f"{n} ({k} stale)" if k else str(n)


def stale_note(p: dict[str, Any]) -> str:
    since = f"`{p['stale_since'][:12]}`" if p["stale_since"] else "a commit not recorded"
    return f"stale since {since} ({', '.join(p['stale_inputs'])})"


def plus(s: dict[str, Any], lv: str, key: str = "histogram") -> int:
    """Programs at lv or above."""
    return sum(n for k, n in s[key].items() if LEVELS.index(k) >= LEVELS.index(lv))


def _frac(d: dict[str, int] | None, a: str, b: str, p: float | None) -> str:
    return "not measured" if not d else f"{d[a]}/{d[b]} ({_n(p)}%)"


def option_text(r: dict[str, Any]) -> str:
    v = r["value"]
    return f"{r['option']}({v})" if v not in (None, "") else str(r["option"])


def option_marker(r: dict[str, Any]) -> str:
    return f"found at {r['source']}" if r["provenance"] == "found" else str(r["source"])


def options_lines(o: dict[str, Any]) -> list[str]:
    """The per-program options line (#4708): result-changing options, each with where its value came from."""
    comp = o.get("compiler") or {}
    head = " ".join(str(comp[k]) for k in ("product", "version") if comp.get(k))
    out = [
        "- **Options in force** (compile options that change results"
        + (f"; {head}" if head else "")
        + f"; {o['found']} found, {o['assumed']} assumed): "
        + ("; ".join(f"{option_text(r)} [{option_marker(r)}]" for r in o["values"]) or "none")
    ]
    for d in o["deviations"]:
        out.append(
            f"  - **Declared option difference:** {d['option']} is {d['declared']} in the estate, applied as "
            f"{d['applied']} ({d['source'] or 'no source'})"
        )
    for d in o["record_differences"]:
        out.append(
            f"  - **Declared option difference (evidence record):** {d['option']} {d['declared']} applied as "
            f"{d['applied']}: {d['note']}"
        )
    return out


def estate_options_lines(o: dict[str, Any]) -> list[str]:
    """The estate-level options table (#4708)."""
    out = ["## Options the estate compiles and runs under", ""]
    if not o["estate_file"]:
        return out + [
            "No estate options file: every option is IBM's default (assumed). "
            f"Programs: {o['programs_found']} option values found, {o['programs_assumed']} assumed.",
            "",
        ]
    c, comp = o["counts"], o["compiler"]
    out += [
        f"From `{o['estate_file']}`: {c['found']} values found in the corpus, {c['assumed']} assumed "
        f"(IBM default, owner decision, or not stated in the corpus). Over the programs' result-changing options: "
        f"{o['programs_found']} found, {o['programs_assumed']} assumed; programs with a declared option difference: "
        f"{o['programs_with_deviation']}.",
        "",
        "| item | value | provenance | source |",
        "|---|---|---|---|",
    ]
    rows = [*comp.values(), *o["installation_defaults"], *o["parm_default"]]
    for r, kind in zip(
        rows, ["compiler"] * len(comp) + ["installation default"] * len(o["installation_defaults"])
        + ["PARM"] * len(o["parm_default"]), strict=True,
    ):  # fmt: skip
        v = option_text(r) if kind != "compiler" else f"{r['option']}: {r['value']}"
        if r.get("applied_value") is not None:
            v += f" (applied as {r['applied_value']}: declared difference)"
        out.append(f"| {kind} | {v} | {r['provenance']} | {r['source']} |")
    if o["parm_programs"]:
        out.append(f"| programs with their own PARM | {', '.join(o['parm_programs'])} | | |")
    out += ["", "| runtime section | found | assumed |", "|---|---|---|"]
    out += [f"| {s.upper()} | {n['found']} | {n['assumed']} |" for s, n in o["sections"].items()]
    return out + [""]


def preface(rep: dict[str, Any]) -> list[str]:
    o, bars = rep["oracle"], rep["bars"]
    out = [
        "## How to read this report",
        "",
        (
            f"**What the oracle is.** Every equivalence result here compares the Java with the COBOL program run by "
            f"{o['what']}: the pinned compiler `{o['compiler']}` (package `{o['package']}`, base image `{o['base_image']}`). "
            "Where that oracle may differ from z/OS is written down in [oracle_assumptions.md](../../oracle_assumptions.md); "
            'each program lists the entries its CICS commands name. A result reads "executed equivalent on N scenarios '
            'against GnuCOBOL + the gitgalaxy CICS stub", with those assumptions -- never a statement about z/OS.'
        ),
        "",
        (
            "**What a level means.** Each program gets the highest level whose conditions hold; levels are cumulative and "
            "the numbers under a level are always shown. The coverage bars are parameters of this report "
            f"(paragraphs {bars['paragraphs']}%, branches {bars['branches']}% net of the reviewed infeasible outcomes "
            "each program lists as stated assumptions). Oracle backing per CICS command is a separate column, not a "
            f"level. Det-port mutation (the top level): {rep['mutation']}. The evidence record of a program's case (the committed hand or "
            "model port's proof) is reported beside each program, and is not a condition of any level."
        ),
        "",
        (
            "**Stale levels (`L3*`).** A level marked `*` is the program's LAST MEASURED level, shown because the "
            "measurement it rests on was made against an earlier harness or oracle: the det-sweep coverage ledger "
            "entry's input fingerprints no longer match the tree on a scheduled input (harness, oracle). It means "
            '"measured against the previous harness, not yet re-checked", not "regressed"; the program table names '
            "`stale since <commit>` (the commit the level was last measured at) and the changed inputs, and the scheduled "
            "re-sweep makes it current again. A change to the program itself (its port, case, corpus pin, declared "
            "differences or options) is not shown as stale: the level drops, as the old measurement no longer describes "
            "it. A stale level is never a current one: the summary counts them apart, and the release gate "
            "(`evidence_report.py --check --live`) fails while any program's level is stale."
        ),
        "",
        (
            "**Options.** A result holds under the compile and runtime options it was produced with, so each program "
            "lists the options that change results (TRUNC, NUMPROC, ARITH, INTDATE, CODEPAGE ...) as the resolver "
            "(`gitgalaxy/core/estate_options.py`) applies them: IBM defaults, overridden by the estate's compile PARM, "
            "overridden by the program's own CBL / PROCESS cards. Each value says where it came from: `found at "
            "<file>:<line>` in the corpus, or `assumed: IBM default` / `assumed: owner decision` / `assumed: not "
            "stated in the corpus`. A **declared option difference** is an option the estate uses that the "
            "proof does not run under (for example TRUNC(OPT) run as TRUNC(STD)): the level holds under the applied "
            "option, not the declared one. The estate-level table gives the compiler product and version, the PARM "
            "defaults, and how many values were found versus assumed."
        ),
        "",
        "| level | name | condition |",
        "|---|---|---|",
    ]
    out += [f"| {lv['level']} | {lv['name']} | {lv['condition']} |" for lv in rep["levels"]]
    out += [
        "",
        (
            "**What is not measured.** Holes, unrun paragraphs and branch outcomes, unstated runtime facts and the "
            "ASSUMED / DIFFERS entries a program's commands name are listed per program. Which register entries a "
            "program actually reaches is not measured. These migration dimensions are not measured at all:"
        ),
        "",
    ]
    out += [f"- **{d['dimension']}** ({d['issue']}): {d['what']}" for d in rep["not_measured"]]
    return out


def render(rep: dict[str, Any]) -> str:
    s = rep["summary"]
    sv = rep["measured"]["survey"]
    out = [
        f"# Evidence report: {rep['estate']}",
        "",
        "<!-- generated by tests/tools/evidence_report.py; do not edit (the evidence-refresh bot regenerates it on main) -->",
        "",
    ]
    if rep["burned"]:
        out += [
            (
                "> **Burned estate.** Its ports and the translator were developed against this estate, so its numbers "
                "describe a development estate, not a blind one."
            ),
            "",
        ]
    else:
        out += ["> **Non-burned estate.** Nothing was developed against it.", ""]
    out += [
        (
            f"Translation measured by `cics_census.py survey` at translator commit `{_n(sv.get('sha'))}` "
            f"({_n(sv.get('scope'))}); evidence record status: {rep['reproducibility']['record_status_from']}; "
            f"coverage: {rep['reproducibility']['coverage_from']}."
        ),
        "",
    ]
    out += preface(rep)
    out += ["", "## Summary", "", "| level | programs | of which stale (awaiting re-check) |", "|---|---|---|"]
    out += [f"| {lv} | {n} | {stale_counts(s)[lv]} |" for lv, n in s["histogram"].items()]
    out += [
        "",
        f"- current levels: {s['programs'] - sum(stale_counts(s).values())}; stale (`*`, last measured): "
        f"{sum(stale_counts(s).values())}",
        "- "
        + "; ".join(
            f"{lv}+: {plus(s, lv)} ({plus({**s, 'histogram_stale': stale_counts(s)}, lv, 'histogram_stale')} awaiting re-check)"
            for lv in ("L2", "L3", "L4")
        ),
    ]
    out += [
        "",
        (
            f"- programs: {s['programs']} (with an EXEC CICS command: {s['cics_programs']}; source not read: "
            f"{s['source_unread']})"
        ),
        f"- translated whole: {s['translated_whole']}; refused whole: {s['refused_whole']}; holes left: {s['holes']}",
        (
            f"- with an equivalence case: {s['with_case']}; det port equal on its case: {s['det_equal']}; with an "
            f"evidence record: {s['with_record']}; record current at build: {s['records_current']}"
        ),
        "",
    ]
    if "options" in rep:
        out += estate_options_lines(rep["options"])
    out += [
        "## Programs",
        "",
        (
            "| program | level | translated / statements | holes | case | det port | scenarios | record | paragraphs | "
            "branches (raw) | branches (net of infeasible) | det-port mutation | CICS commands oracle-backed |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in rep["programs"]:
        t, c, cov = p["translation"], p["equivalence"]["chosen"], p["coverage"]
        rec = c["record"] if c else None
        rs = p["residual"]
        out.append(
            f"| {p['program']} | {lvl(p)} | "
            + ("refused" if t["refused"] else f"{_n(t['translated'])}/{_n(t['statements'])}")
            + f" | {t['hole_count']} | {c['case'] if c else '—'} | {c['det']['state'] if c else '—'} | "
            f"{(rec['scenarios'] if rec else c['case_scenarios']) if c else '—'} | "
            f"{(rec['status_at_build'] if rec else 'none') if c else '—'} | "
            f"{_frac(cov['paragraphs'], 'covered', 'live', cov['paragraph_pct'])} | "
            f"{_frac(cov['branches'], 'covered', 'total', cov['branch_pct'])} | "
            f"{_frac(cov['branches_net'], 'covered', 'total', cov['branch_net_pct'])} | "
            f"{p['mutation']['det_port']} | "
            + (f"{rs['commands_backed']}/{rs['commands']}" if rs["commands"] else "—")
            + " |"
        )
    out += ["", "## Per program", ""]
    for p in rep["programs"]:
        out += program_section(p)
    out += [
        "## Assumptions the estate's CICS commands name",
        "",
        (
            "From the spec entries of the commands the programs use, with the register's status. Which of them a "
            "program's scenarios reach is not measured."
        ),
        "",
        "| id | area | status | entry |",
        "|---|---|---|---|",
    ]
    out += [f"| {a['id']} | {a['area']} | {a['status']} | {a['entry']} |" for a in rep["assumptions_named"]]
    rp = rep["reproducibility"]
    out += [
        "",
        "## Reproducibility",
        "",
        f"- translator commit (the survey's): `{_n(rp['translator_commit'])}`",
        f"- corpus pin: `{rep['estate']}` at `{_n(rp['corpus_ref'] or None)}`",
        (
            "- crucible pins: "
            + ", ".join(f"{k} `{v}`" for k, v in rp["crucible_pins"].items())
            + f"; cics crucible baseline measured at `{_n(rp['crucible_baseline_ref'])}`;"
            f" crucible cases per command measured at `{_n(rp['crucible_cases_measured_at'])}`"
        ),
        f"- crucible pin manifest: {rp['pin_manifest']}",
        f"- oracle base image: `{rp['oracle_base_image']}`",
        "- oracle images the evidence records ran on: "
        + (", ".join(f"`{i}`" for i in rp["oracle_images_of_records"]) or "none"),
        "",
        "Regenerate this report and re-run its proofs:",
        "",
        "```sh",
        *rp["commands"],
        "```",
        "",
    ]
    return "\n".join(out)


def program_section(p: dict[str, Any]) -> list[str]:
    t, eq, cov, a, rs = p["translation"], p["equivalence"], p["coverage"], p["assumptions"], p["residual"]
    out = [f"### {p['program']} -- {lvl(p)}", ""]
    if not p.get("level_current", True):
        out += [f"- **Stale level:** {p['level']} is the last measurement, {stale_note(p)}; not yet re-checked", ""]
    if p["level"] not in ("L0", "L1"):
        ch = eq["chosen"]
        out.append(
            "- **Executed equivalent** on "
            + (f"the {ch['case_scenarios']} scenarios" if ch["case_scenarios"] is not None else "the batch runs")
            + f" of {ch['case']} against GnuCOBOL + "
            f"the gitgalaxy CICS stub (det port: {ch['det']['source']}), given the assumptions below"
        )
    out.append("- **Next level needs:** " + "; ".join(p["next"]))
    if t["refused"]:
        out.append(f"- **Translation:** refused whole: {t['refused']}")
    else:
        out.append(
            f"- **Translation:** {_n(t['translated'])}/{_n(t['statements'])} statements, "
            f"{t['hole_count']} holes; whole: {'yes' if t['whole'] else 'no'}"
        )
        out += [f"  - hole: {h}" for h in t["holes"]]
    if t["source_defects"]:
        out.append("  - named source defects: " + "; ".join(t["source_defects"]))
    if "options" in p:
        out += options_lines(p["options"])
    if not eq["cases"]:
        out.append("- **Executed equivalence:** no equivalence case runs it")
    for c in eq["cases"]:
        rec = c["record"]
        d = c["det"]
        line = (
            f"- **Executed equivalence** ({c['case']}, {c['role']}{', Db2' if c['db2'] else ''}"
            f"{', the case this report judges' if c == eq['chosen'] else ''}): det port "
            f"{d['state']}" + (f" ({d['source']})" if "source" in d else f" ({'; '.join(d['why'])})")
        )
        out.append(line)
        if rec:
            out.append(
                f"  - evidence record (the case's committed port): {rec['status_at_build']}"
                + (f" (stale on {', '.join(rec['stale_inputs'])})" if rec["stale_inputs"] else "")
                + f"; its proof: {rec['verdict']}, {rec['scenarios_equal']}/{rec['scenarios']} scenarios equal, "
                f"{rec['records_equal']}/{rec['records_compared']} records equal, {_n(rec['runs'])} runs "
                f"({_n(rec['fault_runs'])} fault runs)"
                + (", java side failed" if rec["java_failed"] else "")
                + (
                    f"; through its deployed entry points {rec['facade']['passed']}/{rec['facade']['runs']}"
                    if rec["facade"]
                    else ""
                )
            )
        else:
            out.append(f"  - evidence record: none ({_n(c['case_scenarios'])} scenarios in case.json)")
    if cov["source"]:
        out.append(
            f"- **Coverage** ({cov['source']}): paragraphs "
            f"{_frac(cov['paragraphs'], 'covered', 'live', cov['paragraph_pct'])}, branch outcomes "
            f"{_frac(cov['branches'], 'covered', 'total', cov['branch_pct'])} raw, "
            f"{_frac(cov['branches_net'], 'covered', 'total', cov['branch_net_pct'])} net of "
            f"{len(cov['infeasible_netted'])} stated infeasible; unrun paragraphs by name: "
            f"{cov['uncovered_paragraphs']}"
        )
        if cov["infeasible_refuted"]:
            out.append("  - stated infeasible but reached (a refuted claim): " + ", ".join(cov["infeasible_refuted"]))
        out += [f"  - branch outcome no scenario runs: {b}" for b in cov["uncovered_branches"]]
    else:
        out.append("- **Coverage:** not measured")
    if p["oracle_backing"]:
        out += [
            (
                "- **Oracle backing** (a column, not a level; per CICS command; DIFFERS assumptions reached: not "
                "measured):"
            ),
            "",
            "  | command | spec entry | hand-traced crucible cases (stub / Java runtime agree) | backed |",
            "  |---|---|---|---|",
        ]
        for b in p["oracle_backing"]:
            cases = (
                ", ".join(
                    f"{x['case']} ({'yes' if x['stub_agrees'] else 'no'} / {'yes' if x['java_agrees'] else 'no'})"
                    for x in b["crucible_cases"]
                )
                or "none"
            )
            out.append(f"  | {b['command']} | {b['spec_entry']} | {cases} | {'yes' if b['backed'] else 'no'} |")
        out.append("")
    else:
        out.append(
            "- **Oracle backing:** no EXEC CICS command" + ("" if a["source_read"] else " found (source not read)")
        )
    named = ", ".join(f"{x['id']} ({x['status']})" for x in a["named_by_commands"]) or "none"
    out.append(f"- **Assumptions relied on:** named by its commands' spec entries: {named}; reach: {a['reach']}")
    if a["facts_stated"]:
        out.append("  - runtime facts the harness states for its commands: " + ", ".join(a["facts_stated"]))
    out += [f"  - runtime fact no harness states: {f}" for f in a["facts_unstated"]]
    out += [
        f"  - stated infeasible branch outcome (reviewed claim, family {e['family']}): {e['key']} ({e['kind']}) -- "
        f"{e['reason']}"
        for e in cov["infeasible_stated"]
    ]
    out.append(f"- **Det-port mutation:** {p['mutation']['det_port']}")
    risk = [
        f"{rs['holes']} holes" if rs["holes"] else None,
        f"refused whole ({rs['refused']})" if rs["refused"] else None,
        f"{rs['paragraphs_unrun']} live paragraphs unrun" if rs["paragraphs_unrun"] else None,
        f"{rs['branch_outcomes_unrun']} branch outcomes unrun" if rs["branch_outcomes_unrun"] else None,
        "coverage not measured" if rs["paragraphs_unrun"] is None and t["whole"] else None,
        f"{rs['facts_unstated']} unstated runtime facts" if rs["facts_unstated"] else None,
        ("ASSUMED / DIFFERS entries named: " + ", ".join(rs["assumed_or_differs_named"]))
        if rs["assumed_or_differs_named"]
        else None,
        ("commands without oracle backing: " + ", ".join(rs["commands_not_backed"]))
        if rs["commands_not_backed"]
        else None,
    ]
    out.append(
        "- **Residual risk:** "
        + ("; ".join(x for x in risk if x) or "none listed beyond the estate-wide items")
        + "; assumption reach and the migration dimensions above: not measured"
    )
    out.append("")
    return out


def render_index(reports: list[dict[str, Any]]) -> str:
    out = [
        "# Evidence reports",
        "",
        "<!-- generated by tests/tools/evidence_report.py; do not edit (the evidence-refresh bot regenerates it on main) -->",
        "",
        (
            'Per estate, a level per program (see any report\'s "How to read this report"). Only burned estates are '
            "committed here; a non-burned estate's report is written outside the repository."
        ),
        "",
        "## How this stays current",
        "",
        "These files are derived output. A feature PR does not commit them: the Evidence Refresh workflow "
        "(`.github/workflows/evidence-refresh.yml`) regenerates them on every push to main (and nightly) through an "
        "auto-merged bot PR from `auto/evidence-refresh`, and skips the PR when nothing changed. Per-PR CI only prints "
        "the level changes a PR would cause in its job summary (`evidence_report.py --deltas --live`; advisory, never a "
        "failure). A release tag is gated on `evidence_report.py --check --live` being clean AND on every level being "
        "current: a `(k stale)` cell is a level last measured against an earlier harness or oracle (marked `*` in the "
        "report), kept instead of counted as 0, and it fails the gate until the scheduled re-sweep refreshes it. The schema check "
        "(`test_committed_report_validates`), the evidence-record staleness check and the det-sweep baseline stay "
        "blocking in every PR; a PR still re-runs the proof of a record it makes stale.",
        "",
    ]
    for burned, title in ((True, "Burned estates (ports developed against them)"), (False, "Non-burned estates")):
        rs = [r for r in reports if r["burned"] == burned]
        out += [f"## {title}", ""]
        if not rs:
            out += ["none committed", ""]
            continue
        out += ["| estate | programs | " + " | ".join(LEVELS) + " |", "|---|---|" + "---|" * len(LEVELS)]
        for r in rs:
            h = r["summary"]["histogram"]
            out.append(
                f"| [{r['estate']}]({r['estate']}/report.md) | {r['summary']['programs']} | "
                + " | ".join(cell(h[lv], stale_counts(r["summary"])[lv]) for lv in LEVELS)
                + " |"
            )
        tot = {lv: sum(r["summary"]["histogram"][lv] for r in rs) for lv in LEVELS}
        tot_stale = {lv: sum(stale_counts(r["summary"])[lv] for r in rs) for lv in LEVELS}
        out.append(
            f"| total | {sum(r['summary']['programs'] for r in rs)} | "
            + " | ".join(cell(tot[lv], tot_stale[lv]) for lv in LEVELS)
            + " |"
        )
        out.append("")
    return "\n".join(out)


def dumps(rep: dict[str, Any]) -> str:
    return json.dumps(rep, indent=1, sort_keys=True) + "\n"


# ---- the committed reports ---------------------------------------------------------------------------------------
def committed() -> dict[str, dict[str, Any]]:
    return {f.parent.name: json.loads(f.read_text("utf-8")) for f in sorted(OUT.glob("*/report.json"))}


def expected(live: bool = False, built: Any = None) -> dict[Path, str]:
    """Every committed file as the repo makes it now, from the committed measured blocks."""
    reps = []
    out: dict[Path, str] = {}
    for estate, _old, rep in built if built is not None else rebuilt(live):
        reps.append(rep)
        out[OUT / estate / "report.json"] = dumps(rep)
        out[OUT / estate / "report.md"] = render(rep)
    out[OUT / "README.md"] = render_index(reps)
    return out


def rebuilt(live: bool = False) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """(estate, committed report, report as the repo makes it now) -- built once, a live build is slow."""
    now = (record_status(), det_coverage()) if live else None  # once for every estate
    return [(e, old, build(old["measured"], e, old["bars"], live=live, now=now)) for e, old in committed().items()]


def level_deltas(live: bool = False, built: Any = None) -> list[tuple[str, str, str, str]]:
    """(estate, program, committed level, level now) for every program whose level a refresh would change (#4703);
    a stale level is printed `L3*` (#4730)."""
    out: list[tuple[str, str, str, str]] = []
    for estate, old, new in built if built is not None else rebuilt(live):
        was = {
            p["program"]: lvl({"level_current": True, **p}) for p in old["programs"]
        }  # reports before #4730: current
        now = {p["program"]: lvl(p) for p in new["programs"]}
        for prog in sorted(set(was) | set(now)):
            if was.get(prog) != now.get(prog):
                out.append((estate, prog, was.get(prog, "(new)"), now.get(prog, "(gone)")))
    return out


def stale_levels(live: bool = False, built: Any = None) -> list[tuple[str, str, str, str, str]]:
    """(estate, program, level, stale since, stale inputs) of every program whose level is stale now (#4730)."""
    out = []
    for estate, _old, new in built if built is not None else rebuilt(live):
        for p in new["programs"]:
            if not p["level_current"]:
                out.append(
                    (estate, p["program"], p["level"], p["stale_since"] or "not recorded", ", ".join(p["stale_inputs"]))
                )
    return out


def deltas_markdown(live: bool = False) -> str:
    """The advisory view of a PR (#4703): committed reports are refreshed by the bot on main, so a PR is never failed
    for them; this says what the refresh after its merge will change."""
    built = rebuilt(live)
    rows = level_deltas(live, built)
    stale = [p for p, text in expected(live, built).items() if not p.is_file() or p.read_text("utf-8") != text]
    lines = ["## Evidence report (advisory)", ""]
    sl = stale_levels(live, built)
    now = [new["summary"] for _e, _old, new in built]
    n = sum(s["programs"] for s in now)
    lines += [
        f"Levels now: {n - len(sl)} current, {len(sl)} stale (last measured, awaiting a re-check; the release gate "
        + ("fails" if sl else "would pass on levels")
        + "). "
        + "; ".join(
            f"{lv}+: {sum(plus(s, lv) for s in now)} ({sum(plus(s, lv, 'histogram_stale') for s in now)} stale)"
            for lv in ("L3", "L4")
        ),
        "",
    ]
    if sl:
        lines += ["| estate | program | stale level | stale since | stale inputs |", "|---|---|---|---|---|"]
        lines += [f"| {e} | {p} | {lv}* | {sha[:12]} | {ins} |" for e, p, lv, sha, ins in sl] + [""]
    if not stale:
        lines.append("The committed reports are current.")
    else:
        lines.append(
            f"{len(stale)} committed report file(s) differ from what the repo makes now. The evidence-refresh bot "
            "regenerates them on main after merge; this PR does not commit them."
        )
    if rows:
        lines += [
            "",
            "(`*` = stale: the last measured level.)",
            "",
            "| estate | program | level now | level after refresh |",
            "|---|---|---|---|",
        ]
        lines += [f"| {e} | {p} | {a} | {b} |" for e, p, a, b in rows]
    elif stale:
        lines += ["", "No program changes level."]
    return "\n".join(lines) + "\n"


def write(files: dict[Path, str]) -> None:
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _rel(p: Path) -> str:
    return p.resolve().relative_to(REPO).as_posix() if inside_repo(p) else str(p)


def inside_repo(p: Path) -> bool:
    try:
        p.resolve().relative_to(REPO)
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("estates", nargs="*", help="estate (corpus) names, as the survey names them")
    ap.add_argument("--all", action="store_true", help="every burned estate of the survey (with --out: every estate)")
    ap.add_argument("--out", type=Path, help=f"write ESTATE/report.* here (default {_rel(OUT)}: burned only)")
    ap.add_argument("--baseline", action="store_true", help="the cached survey of --sha (default origin/main)")
    ap.add_argument("--sha", help="the baseline commit (default: origin/main)")
    ap.add_argument("--root", type=Path, help="the baseline cache root (as cics_census.py)")
    ap.add_argument("--survey", type=Path, help="a cics_census.py survey directory instead of the baseline")
    ap.add_argument("--label", default="before")
    ap.add_argument("--sweep", type=Path, nargs="*", default=[], help="proof_sweep.py --det-only work directories")
    ap.add_argument("--corpora", type=Path)
    ap.add_argument("--census-corpora", type=Path)
    ap.add_argument("--bar-paragraphs", type=float, default=DEFAULT_BARS["paragraphs"])
    ap.add_argument("--bar-branches", type=float, default=DEFAULT_BARS["branches"])
    ap.add_argument("--refresh", action="store_true", help="rebuild the committed reports from their measured blocks")
    ap.add_argument("--check", action="store_true", help="exit 1 when a committed report is not current")
    ap.add_argument(
        "--deltas", action="store_true", help="print the level changes a refresh would make; exit 0 (#4703)"
    )
    ap.add_argument("--live", action="store_true", help="--check / --refresh: recompute the records' status now")
    args = ap.parse_args(argv)

    if args.deltas:
        print(deltas_markdown(args.live), end="")
        return 0
    if args.check:
        stale_failed = False
        built = rebuilt(args.live)
        want = expected(args.live, built)
        bad = [p for p, text in want.items() if not p.is_file() or p.read_text("utf-8") != text]
        extra = [p for p in OUT.glob("*/*") if p.is_file() and p not in want]
        if args.live:  # #4730: the release gate never quotes a stale level as current
            for e, prog, lv, sha, ins in stale_levels(True, built):
                print(
                    f"stale level: {e}/{prog} {lv}* (stale since {sha[:12]}: {ins}) -- re-sweep, then --refresh --live",
                    file=sys.stderr,
                )
                stale_failed = True
        for p in bad + extra:
            print(
                f"not current: {_rel(p)} -- run python tests/tools/evidence_report.py --refresh"
                + (" --live" if args.live else ""),
                file=sys.stderr,
            )
        return 1 if bad or extra or stale_failed else 0
    if args.refresh:
        files = expected(args.live)
        write(files)
        print(f"refreshed {len(files)} files under {_rel(OUT)}")
        return 0

    if args.survey:
        rows = cc.load_surveys(args.survey, args.label)
        survey = {"sha": None, "scope": f"survey {args.label}-*", "label": args.label}
    else:
        d = cc.baseline_dir(args)
        rows = cc.load_surveys(d, "before")
        meta = json.loads((d / "meta.json").read_text("utf-8"))
        survey = {"sha": meta["sha"], "scope": meta.get("scope"), "label": "before"}
    if not rows:
        raise SystemExit("no survey rows: run `cics_census.py survey --baseline` (or pass --survey DIR)")
    in_survey = sorted({c for c, _ in rows})
    estates = in_survey if args.all else args.estates
    if args.all and args.out is None:
        estates = [e for e in estates if cc.is_burned(e)]
    if not estates:
        raise SystemExit(f"which estate? one of: {', '.join(in_survey)} (or --all)")
    out_dir = args.out or OUT
    for e in estates:
        if e not in in_survey:
            raise SystemExit(f"{e}: not in the survey (it has {', '.join(in_survey)})")
        if not cc.is_burned(e) and inside_repo(out_dir):
            raise SystemExit(
                f"{e} is not a burned estate: nothing but counts from it is committed -- pass --out DIR "
                "outside the repository"
            )
    roots = [cc.mainframe_root(args.corpora)]
    census = cc.census_root(args.census_corpora, required=False)
    roots += [census] if census else []
    sweeps = pb.load_sweeps(args.sweep)
    bars = {"paragraphs": args.bar_paragraphs, "branches": args.bar_branches}
    for e in estates:
        measured = measure(e, rows, roots, survey, sweeps)
        rep = build(measured, e, bars)
        errs = validate(rep, strict=True)
        if errs:
            raise SystemExit(f"{e}: the report does not validate: {errs}")
        write({out_dir / e / "report.json": dumps(rep), out_dir / e / "report.md": render(rep)})
        h, hs = rep["summary"]["histogram"], stale_counts(rep["summary"])
        print(
            f"{e}: {rep['summary']['programs']} programs, "
            + ", ".join(f"{lv} {cell(n, hs[lv])}" for lv, n in h.items())
        )
    if out_dir.resolve() == OUT.resolve():
        write({OUT / "README.md": render_index(list(committed().values()))})
    return 0


if __name__ == "__main__":
    sys.exit(main())
