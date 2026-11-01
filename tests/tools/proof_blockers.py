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
  not proven in CI: Db2    a Db2 case with no sweep row and no readable det-sweep ledger entry (#5075: the Db2
                           lanes -- det-sweep's `db2` job, #4901, and the nightly Evidence Refresh `db2` job, #4733 --
                           write an entry only for a case their sweep proved, #4758; a case / corpus change since makes
                           it unreadable)
  no det port (crucible)   its crucible case runs the COBOL, but no det port of it is committed
  coverage: ...            the proof leaves live paragraphs (and with --branches, branch outcomes) no scenario runs:
                           translated code no proof judged. The outcomes a case states no input can reach
                           (tests/equivalence/infeasible_outcomes/<case>.json, #4602) are taken out of its branch total and
                           printed; one the proof reached is the gap `infeasible outcome reached`
  fact: NAME               a runtime fact the case would need and no harness states: an EIB field neither runtime
                           sets (EIBCPOSN, EIBFN, ...: both sides read zero; EIBRCODE unless every file control fault the case plans states an "rcode", X64, z/OS does not; EIBTASKN and EIBDS only under a
                           crucible case: the equivalence harness states them, oracle_assumptions X21, X64), an ASSIGN option
                           whose fact an equivalence case cannot state yet (STARTCODE unless every scenario states it, #5077;
                           FACILITY / TERMCHK unless every scenario states a "termid", #5126;
                           USERID unless every scenario states a "userid", SCRNHT / SCRNWD unless every one states a
                           "screen" and a termid, #5126; X19), ASSIGN APPLID / SYSID with a case stating no "region"

Verdicts come from, in order: the sweeps given with --sweep (`proof_sweep.py --det-only --work DIR`: DIR/sweep.json,
and DIR/det/<case>/proof/report.json for the diff kind), else main's CI ratchet -- a non-Db2 case not in
det_sweep_baseline.json is proven, because CI's det-sweep fails on any that is not; a Db2 case not in it is proven
when its det-sweep ledger entry is readable (the Db2 lanes' recorded verdict, above). Coverage comes from the sweep's
coverage line, else the committed det-sweep ledger (tests/equivalence/det_sweep_coverage/<case>.json,
det_coverage_ledger.py) while no BLOCKING input (case, corpus) changed -- #5075: an entry stale on harness / oracle
only is the last measurement (#4730), whose counts CI's det-sweep compares exactly on every sweep of the case; such
entries are counted in the report's sources -- else the case's evidence record (the COBOL side's coverage of the same
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
# #5126 (X64): EIBDS too -- a file control command sets it to its file on both sides (the stub's driver moves it; the
# det port does in a program that reads it), so an equivalence case proves what the program does with it. The crucible
# runner's committed ports predate that, so a crucible case's program keeps the gap.
CASE_STATED_EIB = frozenset(EIB_FACTS) | {"EIBDS"}
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

# #5077: a whole COBOL word -- not the front of a hyphenated user name (EIBRCODE-NICE) or a literal's text ('EIBFN: ')
_DEBUGGING_MODE = re.compile(r"\bWITH\s+DEBUGGING\s+MODE\b", re.IGNORECASE)
_EIB = re.compile(r"(?<![A-Z0-9_-])EIB[A-Z0-9]+(?![A-Z0-9_-])")
LINKED_NOT_MEASURED = "coverage: not measured for a LINKed program"  # #4270
_COV = re.compile(r"(\d+)/(\d+) paragraphs and (\d+)/(\d+) branches")
_CRUCIBLE_PATH = re.compile(r"(?:^|/)cases/[^/]+/([^/]+)/src/([^/]+)\.(?:cbl|cob|cobol)$", re.I)


# ---- what a proof runs ------------------------------------------------------------------------------------------
@dataclass
class Run:
    """One proof subject that runs a program: an equivalence case, or a crucible case's det port."""

    kind: str  # "equivalence" | "crucible"
    case: str
    role: str = "program"  # "program" | "linked"
    program: str = ""  # #5084: a linked run's PROGRAM name (its counts are the case's `linked` entry of that name)
    db2: bool = False
    region: bool = False
    startcode: bool = False  # #5077: every scenario of the case states a STARTCODE (the case's, or its own)
    termid: bool = (
        False  # #5126: every scenario states a terminal (ASSIGN FACILITY / TERMCHK: $GGCICS_FACILITY, withTermid)
    )
    userid: bool = False  # #5126: every scenario states a "userid" (ASSIGN USERID)
    screen: bool = False  # #5126: every scenario states a "screen" and a termid (ASSIGN SCRNHT / SCRNWD)
    rcode: bool = False  # #5126 (X64): every file control fault of the case states an "rcode" (EIBRCODE)
    gaps: set[str] = field(default_factory=set)
    detail: dict[str, str] = field(default_factory=dict)  # gap -> a longer note (the baseline's why, the diff)
    infeasible: list[str] = field(default_factory=list)  # #4602: stated infeasible outcomes taken out of the total
    verdict: str = ""  # #5075: "ledger" when the det verdict is the det-sweep ledger's (a Db2 case, no sweep row)
    stale_coverage: list[str] = field(default_factory=list)  # #5075: the ledger inputs changed since its coverage


# the commands whose planned fault may state an "rcode" (equivalence_cics_faults.FILE_FAULT_COMMANDS; a test pins the twin)
FILE_RCODE_COMMANDS = frozenset({"READ", "READNEXT", "READPREV", "STARTBR", "ENDBR", "WRITE", "REWRITE", "DELETE"})


def states_rcode(scens: list[dict[str, Any]]) -> bool:
    """#5126 (X64): does the case state EIBRCODE? True when it plans at least one file control fault and every such
    fault with a response other than NORMAL states an `rcode` (the 6 bytes, a scenario fact: no IBM table is copied).
    One fault without it leaves the field as the program last saw it on that path, so the gap stays."""
    faults = [
        f
        for sc in scens
        for f in sc.get("faults") or []
        if str(f.get("cmd", "")).upper() in FILE_RCODE_COMMANDS and str(f.get("resp", "")).upper() != "NORMAL"
    ]
    return bool(faults) and all(f.get("rcode") for f in faults)


def case_states(case: dict[str, Any]) -> dict[str, bool]:
    """The runtime facts an equivalence case states in every scenario (the case's value is each scenario's default):
    the `Run` flags startcode / termid / userid / screen / rcode (#5077, #5126)."""
    scens = case.get("scenarios") or []
    termid = bool(scens) and all(sc.get("termid", case.get("termid")) is not None for sc in scens)
    return {
        "startcode": bool(scens) and all(sc.get("startcode", case.get("startcode")) for sc in scens),
        "termid": termid,
        "userid": bool(scens) and all(sc.get("userid", case.get("userid")) for sc in scens),
        "screen": termid and all(sc.get("screen", case.get("screen")) for sc in scens),
        "rcode": states_rcode(scens),
    }


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
        states = case_states(case)
        out[(case["corpus"], _norm(case["program_source"]))].append(
            Run(
                "equivalence",
                f.parent.name,
                db2=db2,
                region=region,
                **states,
            )  # fmt: skip
        )
        for extra in case.get("programs", []):  # LINKed programs: det_port.py translates them the same way
            out[(case["corpus"], _norm(extra["program_source"]))].append(
                Run(
                    "equivalence",
                    f.parent.name,
                    role="linked",
                    db2=db2,
                    region=region,
                    **states,
                    program=str(extra.get("program", "")).upper(),
                )
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
            cj = root / "det" / case / "proof" / "cobol" / "coverage.json"
            if out[case].get("uncovered") is None and cj.is_file():  # a sweep from before #4602 kept it here
                out[case]["uncovered"] = json.loads(cj.read_text(encoding="utf-8"))["branches"]["uncovered"]
    return out


def coverage_of(line: str) -> tuple[int, int, int, int] | None:
    """A proof's coverage line -> (paragraphs covered, live, branches covered, total)."""
    m = _COV.search(line or "")
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


_LEDGERS: dict[tuple, dict[str, Any]] = {}


def _ledger() -> dict[str, Any]:
    """det_coverage_ledger.load(), read again only when a file of the ledger changed (name, size, mtime): a report
    build asks once a program (~165 a build), and each read parsed every entry (#5882). Its readers here only read it."""
    import det_coverage_ledger as dcl

    d = dcl.LEDGER_DIR
    key = (id(dcl.load), str(d),  # (a test's own load or directory is read as itself)
           tuple((f.name, f.stat().st_size, f.stat().st_mtime_ns) for f in sorted(d.glob("*.json"))) if d.is_dir() else ())  # fmt: skip
    if key not in _LEDGERS:
        _LEDGERS.clear()
        _LEDGERS[key] = dcl.load()
    return _LEDGERS[key]


def ledger_readings(cases: list[str] | None = None, cases_dir: Path = CASES) -> dict[str, Any]:
    """#5075: case -> its det-sweep ledger entry as a reader may take it (det_coverage_ledger.last_coverage):
    [paragraphs covered, live, branches covered, total] while current; {"coverage": [...], "stale_inputs": [...],
    "stale_since": sha|None} while stale on SCHEDULED inputs only (harness / oracle: the last measurement, #4730);
    None for no entry or a BLOCKING change (case, corpus: it describes another program). An entry exists only while
    the last sweep of its case proved it (#4758), so a readable one is also the case's det verdict."""
    import det_coverage_ledger as dcl

    if cases_dir != CASES:  # a fixture tree: fingerprints are the repo's
        return {}
    ledger = _ledger()
    out: dict[str, Any] = {}
    for case in sorted(ledger) if cases is None else cases:
        last = dcl.last_coverage(case, ledger)
        if last is None or last["blocking"]:
            out[case] = None
        elif not last["stale_inputs"]:
            out[case] = list(last["coverage"])
        else:
            out[case] = {"coverage": list(last["coverage"]), "stale_inputs": list(last["stale_inputs"]),
                         "stale_since": last["measured_at"]}  # fmt: skip
    return out


def ledger_linked(cases: list[str] | None = None, cases_dir: Path = CASES) -> dict[str, dict[str, Any]]:
    """#5084: case -> the LINKed / CALLed programs' counts of its ledger entry ({PROGRAM: counts}), apart from the
    reading (ledger_readings) so a current entry stays a list: fresh and stale are told apart by the reading's shape
    alone. Cases with no entry, a BLOCKING change (it describes another program) or no counts are left out."""
    import det_coverage_ledger as dcl

    if cases_dir != CASES:
        return {}
    ledger = _ledger()
    out: dict[str, dict[str, Any]] = {}
    for case in sorted(ledger) if cases is None else cases:
        last = dcl.last_coverage(case, ledger)
        if last is not None and not last["blocking"] and last.get("linked"):
            out[case] = dict(last["linked"])
    return out


def linked_cov(counts: dict[str, Any]) -> tuple[int, int, int, int]:
    p, b = counts["paragraphs"], counts["branches"]
    return p["covered"], p["live"], b["covered"], b["total"]


def linked_counts_of(row: dict[str, Any] | None, from_ledger: dict[str, Any] | None) -> dict[str, Any]:
    """#5084: the LINKed / CALLed programs' counts of a case: the sweep row's (this run), else the ledger's (ledger_linked)."""
    if row and row.get("linked"):
        return dict(row["linked"])
    return dict(from_ledger or {})


def reading_coverage(reading: Any) -> tuple[tuple[int, int, int, int] | None, list[str]]:
    """A ledger reading (ledger_readings) -> (its coverage, the inputs it is stale on)."""
    if isinstance(reading, dict):
        return tuple(reading["coverage"]), list(reading.get("stale_inputs") or [])  # type: ignore[return-value]
    return (tuple(reading), []) if reading else (None, [])  # type: ignore[return-value]


def ledger_coverage(case: str, cases_dir: Path = CASES) -> tuple[int, int, int, int] | None:
    """The det sweep's coverage of the case from the committed ledger (det_coverage_ledger.py), while it is fresh."""
    import det_coverage_ledger as dcl

    if cases_dir != CASES:  # a fixture tree: fingerprints are the repo's
        return None
    return dcl.fresh_coverage(case, _ledger())


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


COBC_NO_COMPILE = "cobc: does not compile"


def last_line(text: str) -> str:
    """The last non-empty line of cobc's stderr: its final diagnostic."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def judge_equivalence(run: Run, det_baseline: dict[str, dict[str, Any]], sweeps: dict[str, dict[str, Any]],
                      branches: bool, cases_dir: Path = CASES, ledger: dict[str, Any] | None = None,
                      linked_ledger: dict[str, dict[str, Any]] | None = None) -> None:  # fmt: skip
    """Fill run.gaps for an equivalence case's det port. `ledger`: ledger_readings() (#5075), read for a Db2 case's
    verdict and for coverage; None (evidence_report, which applies its own measured ledger) reads only a current
    entry's coverage and leaves every Db2 case with no sweep row "not proven in CI"."""
    row = sweeps.get(run.case)
    reading = (ledger or {}).get(run.case)
    base = det_baseline.get(run.case)
    if row is not None and row.get("cobol_compile_failed"):  # #4493: cobc refused the COBOL; no scenario ran
        run.gaps.add(COBC_NO_COMPILE)
        run.detail[COBC_NO_COMPILE] = last_line(row.get("cobc_stderr", ""))
        return  # no scenario ran: nothing else (coverage, holes, linked counts) can be read off this case
    elif row is not None and not row.get("proved"):
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
        if reading is None:
            run.gaps.add("not proven in CI: Db2 case (no sweep row, no readable det-sweep ledger entry)")
        else:
            run.verdict = "ledger"
    if row is not None:
        t, _, s = str(row.get("translated", "")).partition("/")
        if t.isdigit() and s.isdigit() and int(t) < int(s):
            run.gaps.add("holes in the case's det port")
    counts = linked_counts_of(
        row, (linked_ledger or {}).get(run.case)
    )  # #5084: {PROGRAM: counts} of the programs the case LINKs / CALLs
    if run.role == "linked":  # the case's coverage line is its main program's (#4270): never inherit it
        mine = counts.get(run.program)
        if mine is None:
            run.gaps.add(LINKED_NOT_MEASURED)
            run.detail[LINKED_NOT_MEASURED] = (
                "the case's coverage line is its main program's; the LINKed program has no count of its own"
            )
        else:
            coverage_gaps(run, linked_cov(mine), branches)
        return
    for name, mine in sorted(counts.items()):  # a caller is not proven while a callee has holes (owner rule, #5084)
        pc, pl, bc, bt = linked_cov(mine)
        if pc < pl:
            g = f"coverage: LINKed program {name} has live paragraphs no scenario runs"
            run.gaps.add(g)
            run.detail[g] = f"{pc}/{pl} paragraphs"
        if branches and bc < bt:
            g = f"coverage: LINKed program {name} has branch outcomes no scenario runs"
            run.gaps.add(g)
            run.detail[g] = f"{bc}/{bt} branches"
    cov = coverage_of(row.get("coverage", "")) if row else None
    uncovered = row.get("uncovered") if cov else None
    checked = uncovered is not None  # a sweep that kept no uncovered list cannot show a claim holds
    if cov is None:  # counts only: CI's det-sweep checks the claims
        if ledger is None:
            cov, checked = ledger_coverage(run.case, cases_dir), True
        else:
            (cov, run.stale_coverage), checked = reading_coverage(reading), True
    if cov is None:
        cov, uncovered = evidence_coverage(run.case, cases_dir), evidence_uncovered(run.case, cases_dir)
        checked = uncovered is not None
    if checked:
        cov = stated_infeasible(run, cov, uncovered, cases_dir)
    coverage_gaps(run, cov, branches)


def evidence_uncovered(case: str, cases_dir: Path = CASES) -> list[dict[str, Any]] | None:
    f = cases_dir / case / "evidence.json"
    if not f.is_file():
        return None
    import infeasible_outcomes as io

    uncovered = (json.loads(f.read_text(encoding="utf-8")).get("coverage") or {}).get("uncovered_branches")
    if uncovered is None:
        return None
    # A record names no uncovered paragraphs, so it cannot show a stated paragraph claim reached: leave those entries
    # open, as the ledger-count path does (CI's det-sweep `check` holds them on a real sweep).
    stated = io.load(cases_dir / io.LEDGER.name).get(case, [])
    return [*uncovered, *(io.PARAGRAPH_MARK + e["unit"] for e in stated if io.is_paragraph(e))]


def stated_infeasible(run: Run, cov: tuple[int, int, int, int] | None, uncovered: list[Any] | None,
                      cases_dir: Path = CASES) -> tuple[int, int, int, int] | None:  # fmt: skip
    """#4602: the case's stated infeasible outcomes (tests/equivalence/infeasible_outcomes/<case>.json) out of its branch
    total, listed in run.infeasible; one the proof reached refutes the claim and is a gap."""
    import infeasible_outcomes as io

    ledger = io.load(cases_dir / io.LEDGER.name)
    cov, taken, reached = io.adjust(run.case, cov, uncovered, ledger)
    run.infeasible = taken
    if reached:
        g = "infeasible outcome reached (the stated claim is wrong)"
        run.gaps.add(g)
        run.detail[g] = ", ".join(reached)
    return cov


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
def code_only(text: str) -> str:
    """The program with every non-code span blanked, length-preserving, line structure kept: string literals
    (including one continued onto the next line: a column-7 hyphen in fixed format, a next line opening with the
    quote in free format) and `*>` floating comment tails. Comment lines (column 7 `*` or `/`; free `*>`) are left
    for `cc.fixed_format_text` to drop. A column-7 `D` line (free: `>>D`) is a comment unless the source has an
    active `WITH DEBUGGING MODE` (IBM), so it is blanked too. #5089: one rule for every fact keyword, per line
    format (`cc.source_lines`: fixed, variable, free, `>>SOURCE FORMAT` switches followed)."""
    srcs = cc.source_lines(text)

    def is_comment(fmt: str, ln: str) -> bool:
        if fmt == "free":
            return ln.lstrip().startswith("*>")
        return len(ln) <= 6 or ln[6] in "*/"

    def is_debug(fmt: str, ln: str) -> bool:
        if fmt == "free":
            return ln.lstrip()[:3].upper() == ">>D"
        return len(ln) > 6 and ln[6] in "Dd"

    debugging = any(
        not is_comment(f, ln)
        and not is_debug(f, ln)
        and _DEBUGGING_MODE.search((ln if f != "fixed" else ln[:72]).split("*>")[0])
        for f, ln in srcs
    )
    out, quote = [], ""
    for fmt, ln in srcs:
        if is_comment(fmt, ln) or (is_debug(fmt, ln) and not debugging):
            blank = is_debug(fmt, ln) and not is_comment(fmt, ln)
            out.append(" " * len(ln) if blank and fmt == "free" else ln[:7] + " " * (len(ln) - 7) if blank else ln)
            quote = ""
            continue
        free = fmt == "free"
        code = list(ln if fmt != "fixed" else ln[:72])
        i = 0 if free else 7
        if quote:
            if not free and ln[6] != "-":
                quote = ""
            else:  # the continuation's first quote reopens the literal; the blanks before it are padding
                while i < len(code) and code[i] == " ":
                    i += 1
                if i < len(code) and code[i] == quote:
                    code[i] = " "
                    i += 1
                else:
                    quote = ""
        while i < len(code):
            ch = code[i]
            if quote:
                if ch == quote:
                    quote = ""
                code[i] = " "
            elif ch in "'\"":
                quote = ch
                code[i] = " "
            elif ch == "*" and code[i + 1 : i + 2] == [">"]:
                code[i:] = " " * (len(code) - i)
                break
            i += 1
        out.append("".join(code) + (ln[72:] if fmt == "fixed" else ""))
    return "\n".join(out)


def facts_needed(text: str) -> dict[str, set[str]]:
    """The runtime facts a program reads, by kind: `eib` (EIB fields no harness states), `assign_task` (ASSIGN
    options an equivalence case cannot state yet), `assign_region` (ASSIGN APPLID / SYSID). Names only."""
    plain = code_only(text)
    code = cc.fixed_format_text(plain)
    eib = {m for m in _EIB.findall(code) if m in EIB_FIELDS and m not in STATED_EIB}
    task, region = set(), set()
    for cmd in cc.commands(plain):
        opts = cc.options_of(cmd, ["ASSIGN"])
        for o in opts or ():
            if o in ASSIGN_TASK_FACTS:
                task.add(ASSIGN_TASK_FACTS[o])
            elif o in ASSIGN_REGION_FACTS:
                region.add(o)
    return {"eib": eib, "assign_task": task, "assign_region": region}


def unstated_facts(facts: dict[str, set[str]], run: Run | None) -> dict[str, list[str]]:
    """The EIB fields (`eib`) and ASSIGN task facts (`assign_task`) a program reads that no harness states under one
    proof subject (None: no case yet -- what a new case would need that no case can state). #5126: one rule for the
    gap lists and the evidence report."""
    case_states = run is None or run.kind == "equivalence"  # a new equivalence case would state them too
    eib = sorted(
        e
        for e in facts.get("eib", ())
        if not (case_states and e in CASE_STATED_EIB)
        and not (e == "EIBRCODE" and run is not None and run.kind == "equivalence" and run.rcode)  # it states it
    )
    task: list[str] = []
    if case_states:
        task = sorted(
            f
            for f in facts.get("assign_task", ())
            if not (f == "STARTCODE" and run is not None and run.startcode)  # #5077: the case states it
            and not (f == "FACILITY" and run is not None and run.termid)  # #5126: its "termid" is the facility
            and not (f == "USERID" and run is not None and run.userid)  # #5126: the case states it
            and not (f == "SCRNHT/SCRNWD" and run is not None and run.screen)
        )
    return {"eib": eib, "assign_task": task}


def fact_gaps(facts: dict[str, set[str]], run: Run | None) -> set[str]:
    """The fact gaps of a program under one proof subject (see `unstated_facts`)."""
    left = unstated_facts(facts, run)
    out = {f"fact: {e} (no harness states it)" for e in left["eib"]}
    out |= {f"fact: ASSIGN {f} (no equivalence case states it)" for f in left["assign_task"]}
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
                   det_baseline: dict[str, dict[str, Any]] | None = None,
                   ledger: dict[str, Any] | None = None) -> dict[str, Any]:  # fmt: skip
    """The proof-level ranking over the WHOLE programs of a survey (`rows`: cics_census.load_surveys). `ledger`:
    ledger_readings() of the cases (default: the committed ledger, read once)."""
    sweeps = sweeps or {}
    det_baseline = load_det_baseline() if det_baseline is None else det_baseline
    eq = equivalence_runs(cases_dir)
    if ledger is None:
        ledger = ledger_readings(sorted({r.case for v in eq.values() for r in v}), cases_dir)
    linked_ledger = ledger_linked(sorted({r.case for v in eq.values() for r in v}), cases_dir)
    for runs in eq.values():
        for r in runs:
            judge_equivalence(r, det_baseline, sweeps, branches, cases_dir, ledger, linked_ledger)
    cru = crucible_runs(crucible_dir, branches) if (crucible_dir / "baseline.json").is_file() else {}
    burned = cc.burned_names()
    progs: dict[tuple[str, str], tuple[bool, set[str]]] = {}
    subjects: dict[tuple[str, str], dict[str, Any]] = {}
    skipped_not_cics = unreadable = 0
    untranslated: list[dict[str, Any]] = []
    for key, row in sorted(rows.items()):
        text = read_text(roots, *key)
        if not cc.whole(row):  # #4493 classes 4 / 5: refused or holey, so no proof subject yet; the page says why
            if not only_cics or (text is not None and cc.commands(text)):
                entry = {"corpus": key[0], "program": key[1], "burned": cc.is_burned(key[0], burned),
                         "classes": sorted(cc.gap_classes(row))}  # fmt: skip
                if str(row.get("error", "")).startswith("Copy"):  # #4468: the class drops the member's name; keep it
                    entry["error"] = " ".join(str(row["error"]).split())[:300]
                untranslated.append(entry)
            continue
        unreadable += text is None
        if only_cics and text is not None and not cc.commands(text):
            skipped_not_cics += 1
            continue
        facts = facts_needed(text) if text is not None else {}
        gaps, run = program_gaps(key, eq, cru, facts)
        progs[key] = (cc.is_burned(key[0], burned), gaps)
        subjects[key] = {"case": run.case if run else None, "kind": run.kind if run else None,
                         "detail": {g: run.detail[g] for g in gaps if run and g in run.detail},
                         "infeasible": list(run.infeasible) if run else [],
                         "verdict": run.verdict if run and run.kind == "equivalence" else "",
                         "stale_coverage": list(run.stale_coverage) if run and run.kind == "equivalence" else []}  # fmt: skip
    estate = {k: v for k, v in progs.items() if not is_crucible(k[0])}
    res = rank(estate)
    res["crucible"] = rank({k: v for k, v in progs.items() if is_crucible(k[0])})
    res["scope"] = "programs with an EXEC CICS command" if only_cics else "every surveyed program"
    res["not_cics"] = skipped_not_cics
    res["unreadable"] = unreadable
    if untranslated:  # only when non-empty: an always-present empty key breaks exact-equality tests
        res["untranslated"] = untranslated
    mains = {r.case: r for v in eq.values() for r in v if r.role == "program"}
    res["sources"] = {"sweeps": len(sweeps), "equivalence_cases": len({r.case for v in eq.values() for r in v}),
                      "crucible_programs": len(cru),
                      "ledger_verdicts": sorted(c for c, r in mains.items() if r.verdict == "ledger"),
                      "stale_ledger_coverage": sorted(c for c, r in mains.items() if r.stale_coverage)}  # fmt: skip
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
    if src.get("ledger_verdicts"):
        print(
            f"Db2 cases proven by the det-sweep ledger (the Db2 lanes' last sweep, #4758): {len(src['ledger_verdicts'])}"
        )
    if src.get("stale_ledger_coverage"):
        print(f"cases whose coverage is the ledger's last measurement, stale on harness / oracle only (#4730): "
              f"{len(src['stale_ledger_coverage'])}")  # fmt: skip
    if res.get("unreadable"):
        print(f"programs whose source was not found (facts not read): {res['unreadable']}")
    print()
    print_ranking(res, top)
    proven = [p for p in res["programs"] if not p["gaps"] and not is_crucible(p["corpus"])]
    if proven:
        print("\nproven: " + ", ".join(f"{Path(p['program']).stem} ({p['case']})" for p in proven))
    stated = [p for p in res["programs"] if p.get("infeasible")]
    if stated:  # #4602: assumptions of the proof, always shown
        print(
            "\nstated infeasible outcomes, taken out of the branch totals (tests/equivalence/infeasible_outcomes/<case>.json):"
        )
        for p in stated:
            print(f"  {Path(p['program']).stem} ({p['case']}): {', '.join(p['infeasible'])}")
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
