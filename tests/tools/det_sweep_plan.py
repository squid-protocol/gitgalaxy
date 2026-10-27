#!/usr/bin/env python3
"""Which det-sweep cases a change needs proven, and on how many runners (the "plan" job of det-sweep.yml, #4463).

    python tests/tools/det_sweep_plan.py [--event pull_request] [--base origin/main] [--files FILE ...] [--github-output PATH]

A pull request that changes no det input (DET_INPUTS: docs, other engine code ...) proves nothing (mode "none"; #4825,
so the workflow can run -- and report its required `det` check -- on every PR). One that changes only files under
tests/equivalence/<case>/ re-proves those cases (and the cases that
take that case's port: `port_from`, `uses_ports`, transitively); so does one changing a case's coverage-ledger file,
tests/equivalence/det_sweep_coverage/<case>.json (#4789: the sweep of that case is what checks the entry), or its
tests/equivalence/infeasible_outcomes/<case>.json (#6072). A change to the translator + runtime (det/) or the generator (GENERATOR: the forges that write the
project) is judged by the port diff (mode "ports", then --ports; #4814, #4847). #5885: a shared file is narrowed
to the cases it can move -- the baseline and infeasible_outcomes.json to the cases whose entries changed (KEYED), the
corpora pin to the cases on a corpus whose pin changed, a harness / oracle file to the cases that use its component
(evidence.COMPONENTS, #4731); the mutation scores are no input at all. Anything else -- the harness / oracle core, the
det tools, the workflow, a file straight under tests/equivalence/, a case directory with no case.json (a case added
or removed), an unreadable diff or side -- is a full sweep, as is every event that is not a pull request (nightly,
manual: the backstop for a narrowing that missed). When in doubt, full. Stdlib only: the job runs before anything is
installed.

#6278: on a pull request the Db2 half of a plan that went full for a reason outside the Db2 area (a harness-core file, an
oracle Dockerfile: change_classifier.db2_area) is dropped; the non-Db2 sweep and every other event are unchanged.

Prints JSON {mode, cases, shards, matrix, db2_cases, db2_shards, db2_matrix, reason}: `cases` is "all" or the names;
`matrix` the shard labels "I/N". The Db2 cases (a "db2" section in case.json) are split off into `db2_cases` (#4901):
the PR's `db2` job proves the ones the change moves, on runners of their own that start IBM's Db2 container, in
parallel with the shards; a full sweep proves all of them (the nightly leaves them to Evidence Refresh's Db2 job).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = REPO_ROOT / "tests" / "equivalence"
MAX_SHARDS = 6  # runners at most (#5135: not 20 that queue behind the 20-job pool); #5919: durations size the count below it, and without them a full sweep takes 6, a narrow plan one per PER_SHARD cases
PER_SHARD = 3  # narrow: about this many cases per runner
# #4901: the Db2 cases run on their own runners (each starts IBM's Db2 container, minutes), in parallel with the shards
# #5882: a full sweep's Db2 runners scale with the Db2 cases (a fixed 4 timed shards out at 70 cases): one per
# DB2_FULL_PER_SHARD, at most DB2_MAX_SHARDS (6 shards + 6 Db2 + plan + det fit the 20-job pool, #5135). Evidence
# Refresh's Db2 job takes the same count (--db2-full-matrix).
DB2_MAX_SHARDS = 6
DB2_FULL_PER_SHARD = 12  # full: ~12 Db2 cases per runner (~8 min proving at --jobs 4, plus the Db2 start)
DB2_PER_SHARD = 6  # narrow: about this many Db2 cases per runner (a Db2 start is paid per runner)
# #5919: with the measured durations the Db2 shard count and every shard job's timeout come from ci_shard_plan: the fewest
# Db2 runners (at most DB2_MAX_SHARDS, the cap) whose slowest fits DB2_TARGET_S, the Db2 start (DB2_SETUP_S, paid per
# runner) included; a timeout is the slowest planned shard x 1.5 between the floor and the ceiling. The *_PER_SHARD
# counts above are the fallback when no durations are given.
DB2_SETUP_S = 420  # job start, checkout, Db2 container + databases (~6 min, #5882) before the first proof
DB2_TARGET_S = 15 * 60  # a Db2 job, start to sweep end (det_sweep_timing.BUDGET_SECONDS)
# #5882: plan to this share of DB2_TARGET_S: case seconds move 30-50% run to run, so a plan that just fits the budget missed
# it in 3 runs of 4 (docs/agents/det-sweep-db2-acceptance.md); the price is about one more Db2 runner per full sweep.
DB2_HEADROOM = 0.8
SHARD_SETUP_S = 300  # a non-Db2 shard: checkout, install, the GnuCOBOL image
SHARD_TARGET_S = 10 * 60  # #5919: a non-Db2 shard, start to sweep end (the fewest runners that fit)
MAX_RATIO = 1.3  # planned slowest / fastest shard (det_sweep_timing.MAX_RATIO)
PROOF_JOBS = 4  # proof_sweep.py --jobs: cases proven at once in a shard
TIMEOUT_FLOOR, TIMEOUT_CEILING = 25, 45  # minutes
DEFAULT_TIMEOUT = 30  # minutes, when there are no durations to size from
# #5604: a Db2 job may sit in det-sweep.yml's "Wait for the first Db2 database" (660 x 5 s) before its first proof, so its
# timeout is that wait + checkout + the proving, not the 25..45 min band of a job without the wait.
DB2_WAIT_S = 3300  # #5601: the workflow wait (test_db2_wait_bound pins it)
DB2_TIMEOUT_FLOOR = -(-(SHARD_SETUP_S + DB2_WAIT_S + DB2_TARGET_S) // 60)  # minutes: the wait plus a target-sized sweep
DB2_TIMEOUT_CEILING = 90
# #5919: Evidence Refresh's own jobs (--evidence-plan). Its 20-job share: sweep + records + Db2 parts (6) + lane, refresh,
# det-mutation. Records are re-proved one at a time (evidence.py has no --jobs); the stale list is unknowable in the lane
# job's sparse checkout, so every evidence.json counts, at RECORD_S each (2002-2579 s for ~40 records, sequential).
EVIDENCE_SWEEP_MAX_SHARDS = 5
EVIDENCE_RECORDS_MAX_SHARDS = 5
EVIDENCE_TARGET_S = 10 * 60  # the sweep and records ran ~11 min a shard on 4 and 6 shards: aim there
EVIDENCE_CEILING = 60  # minutes
RECORD_S = 57.0
DURATIONS = CASES / "det_sweep_durations.json"
IGNORED = {"tests/equivalence/det_sweep_durations.json"}  # only balances shards, never a verdict
# #5885: the mutation scores and their survivors (det_mutation.py, evidence_report.py): no det proof reads them
IGNORED_DIRS = ("tests/equivalence/det_mutation/", "tests/equivalence/det_mutation_survivors/")
# #4814: a change confined to these is judged by what it does to the generated ports: `det_port.py check` translates
# every case at the base and at HEAD and names the ports that differ; only those (and their dependents) are proven.
# Only the translator + runtime -- everything a port's bytes come from. Anything else that can move a verdict without
# moving a byte (the harness, proof_reach.py, the oracle) stays a full sweep.
PORT_DIFF = "gitgalaxy/tools/cobol_to_java/det/"
# #4847: the GENERATOR -- the forges that write the project a port is translated into and proven in (the service stub
# the translator fills, the DTOs, entities, repositories, facades). Its output is what `det_port.py check` compares
# (the port, plus the generated classes the port names: `generated/`), so a generator change is judged by the same
# port diff as a translator change. An explicit list, not a glob: the build / test / compare forges, the agent,
# proof_reach.py, port_runner.py and the guardrail can move a verdict without moving a generated byte, so they stay a
# full sweep.
_G = "gitgalaxy/tools/cobol_to_java/cobol_to_java_"
GENERATOR = tuple(
    f"{_G}{n}.py"
    for n in (
        "api_contract_forge", "batch_forge", "call_forge", "common", "db2_forge", "decoder_forge", "messaging_forge",
        "names", "repository_forge", "screen_forge", "service_forge", "skeleton_forges", "spring_forge",
        "transaction_forge", "uow_forge",
    )
)  # fmt: skip
# #5274: the transaction forge's CicsTask family, split out of it
GENERATOR += ("gitgalaxy/tools/cobol_to_java/cics_task_containers.py",
              "gitgalaxy/tools/cobol_to_java/cics_task_filecontrol.py",  # #5448 split it out too (#5885)
              "gitgalaxy/tools/cobol_to_java/cics_task_taskcontrol.py",
              "gitgalaxy/tools/cobol_to_java/cics_task_web.py",
              "gitgalaxy/tools/cobol_to_java/cics_task_tdqueues.py",
              "gitgalaxy/tools/cobol_to_java/cics_task_tsqueues.py",
              "gitgalaxy/tools/cobol_to_java/cics_task_time.py",
              "gitgalaxy/tools/cobol_to_java/cics_task_conditions.py",
              "gitgalaxy/tools/cobol_to_java/cics_task_faults.py")  # fmt: skip


def port_diff_input(path: str) -> bool:
    """A file whose effect on the proofs is its effect on the generated ports: translator + runtime, or a forge."""
    return path.startswith(PORT_DIFF) or path in GENERATOR


# What a det proof reads (#4825: moved here from det-sweep.yml's trigger, so the workflow runs -- and reports `det` --
# on every PR). A PR that changes none of these proves nothing (mode "none"). fnmatch: `*` also crosses `/`.
DET_INPUTS = (
    "gitgalaxy/tools/cobol_to_java/*",
    "tests/tools/det_port.py",
    "tests/tools/det_parity.py",
    "tests/tools/proof_sweep.py",
    "tests/tools/det_sweep_plan.py",
    "tests/tools/equivalence*.py",
    # #6782: the coverage counter and a module equivalence.py imports move proof numbers like the harness does; a PR
    # touching them planned "none" (#6772), so the ledgers it moved were never re-swept
    "tests/tools/cobol_coverage.py",
    "tests/tools/le_out_size.py",
    "tests/tools/java_target_matrix.py",
    "tests/tools/mainframe_corpus.py",
    "tests/equivalence/*",
    "tests/cobol_mainframe/corpora.json",
    ".github/workflows/det-sweep.yml",
)


def det_input(path: str) -> bool:
    return (not path.endswith(".md") and not path.startswith(IGNORED_DIRS)
            and any(fnmatch.fnmatch(path, p) for p in DET_INPUTS))  # fmt: skip


# #4789: <case>.json, the det-sweep coverage ledger's entry of a case
LEDGER_DIR = "tests/equivalence/det_sweep_coverage/"
INFEASIBLE_DIR = "tests/equivalence/infeasible_outcomes/"  # #6072: one file per case, <case>.json


def case_dirs(cases_dir: Path = CASES) -> dict[str, dict]:
    return {p.parent.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(cases_dir.glob("*/case.json"))}


def is_db2(case: dict) -> bool:
    return "db2" in case


def dependents(changed: set[str], cases: dict[str, dict]) -> set[str]:
    """`changed` and every case that takes a changed case's port (port_from / uses_ports), transitively."""
    out = set(changed)
    while True:
        more = {
            n
            for n, c in cases.items()
            if n not in out and (c.get("port_from") in out or set(c.get("uses_ports", [])) & out)
        }
        if not more:
            return out
        out |= more


# #5885: shared files keyed by case: a change to some entries is proven by sweeping those cases (the sweep checks a
# case's baseline entry and its infeasible-outcome claims; infeasible_outcomes.check reads the whole file's form on
# every det run). {path: (the top-level sections keyed by case, the ones that only describe)}; any other top-level
# change, an unknown case key or an unreadable side is a full sweep.
KEYED = {
    "tests/equivalence/det_sweep_baseline.json": (("det", "model"), ("about",)),
    "tests/equivalence/infeasible_outcomes.json": (("cases",), ("about", "issue", "families")),  # families: below
}
CORPORA = "tests/cobol_mainframe/corpora.json"


def _json(text: str | None) -> dict | None:
    try:
        value = json.loads(text) if text is not None else None
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def keyed_cases(path: str, base: str | None, head: str | None, cases: dict[str, dict]) -> set[str] | None:
    """#5885: the cases whose entries of KEYED file `path` differ between the base and HEAD texts, or None (full)."""
    old, new = _json(base), _json(head)
    if old is None or new is None:
        return None
    sections, prose = KEYED[path]
    if any(old.get(k) != new.get(k) for k in set(old) | set(new) if k not in sections and k not in prose):
        return None
    out: set[str] = set()
    for sec in sections:
        a, b = old.get(sec) or {}, new.get(sec) or {}
        out |= {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    if path.endswith("infeasible_outcomes.json") and old.get("families") != new.get("families"):
        fa, fb = old.get("families") or {}, new.get("families") or {}
        moved = {k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k)}  # a family's text: the cases that cite it
        for side in (old, new):
            out |= {c for c, es in (side.get("cases") or {}).items() if any(e.get("family") in moved for e in es)}
    return out if out <= set(cases) else None


def corpus_cases(base: str | None, head: str | None, cases: dict[str, dict]) -> set[str] | None:
    """#5885: the cases on a corpus whose pin (tests/cobol_mainframe/corpora.json) changed, or None (full)."""
    old, new = _json(base), _json(head)
    if old is None or new is None or {k: v for k, v in old.items() if k != "corpora"} != {
            k: v for k, v in new.items() if k != "corpora"}:  # fmt: skip
        return None
    try:
        a = {c["name"]: c for c in old["corpora"]}
        b = {c["name"]: c for c in new["corpora"]}
    except (KeyError, TypeError):
        return None
    moved = {n for n in set(a) | set(b) if a.get(n) != b.get(n)}
    return {n for n, c in cases.items() if c.get("corpus") in moved}


def component_cases(path: str, cases: dict[str, dict]) -> set[str] | None:
    """#5885: the cases that use the harness / oracle component `path` belongs to, by the component map the evidence
    records are fingerprinted with (evidence.COMPONENTS, #4731: e.g. the Db2 layer is linked into Db2 cases only);
    None when `path` is no harness / oracle file, or lies in `<input>:core` (every case uses it)."""
    import evidence  # noqa: PLC0415 -- stdlib only, like this planner; read only when a harness / oracle file changed

    if path in evidence.HARNESS:
        name = "harness"
    elif any(path == p or fnmatch.fnmatchcase(path, p) for p in evidence.ORACLE):
        name = "oracle"
    else:
        return None
    comp = next((c for c in evidence.COMPONENTS if c.input == name
                 and any(path == p or fnmatch.fnmatchcase(path, p) for p in c.paths)), None)  # fmt: skip
    if comp is None:
        return None
    return {
        n
        for n, c in cases.items()
        if comp.uses(evidence.Use(c.get("kind", "batch"), is_db2(c), bool(c.get("programs")), ims="ims" in c))
    }


FULL_LABEL = "shepherd:full"  # #4847: a maintainer's request for the full sweep on a pull request (docs/ci.md)


def labels_from_event(path: Path) -> list[str]:
    """The pull request's label names from the event payload (GITHUB_EVENT_PATH); [] when there is none."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [x.get("name", "") for x in (payload.get("pull_request") or {}).get("labels") or []]


def _plan(
    files: list[str],
    event: str,
    cases: dict[str, dict],
    labels: list[str] | None = None,
    texts: Callable[[str], tuple[str | None, str | None]] | None = None,
) -> dict:
    """The plan for `files` (repo-relative, as git prints them) on `event`, given the pull request's `labels`;
    `texts(path)` is (the file at the merge base, at HEAD), None for a side that is absent or unreadable."""
    # #4901: a full sweep proves every Db2 case too, except in the nightly (Evidence Refresh's Db2 job runs then)
    full = {"mode": "full", "cases": "all", "db2_cases": [] if event == "schedule" else "all"}
    if event != "pull_request":
        return {**full, "reason": f"{event}: always a full sweep"}
    if FULL_LABEL in (labels or []):
        return {**full, "reason": f"labelled {FULL_LABEL}: a full sweep on request"}
    files = [f for f in files if f not in IGNORED and det_input(f)]
    if not files:
        return {
            "mode": "none",
            "cases": [],
            "db2_cases": [],
            "reason": "no changed file is a det-sweep input (DET_INPUTS)",
        }
    touched: set[str] = set()
    why: list[str] = []  # #5885: the shared files narrowed to the cases they move
    translator = sorted(f for f in files if port_diff_input(f))
    for f in files:
        if port_diff_input(f):
            continue
        if f.startswith(LEDGER_DIR) and f.endswith(".json") and f[len(LEDGER_DIR) : -5] in cases:
            touched.add(f[len(LEDGER_DIR) : -5])  # #4789: a case's ledger entry is checked by sweeping that case
            continue
        if f.startswith(INFEASIBLE_DIR) and f.endswith(".json") and f[len(INFEASIBLE_DIR) : -5] in cases:
            touched.add(f[len(INFEASIBLE_DIR) : -5])  # #6072: a case's stated outcomes are checked by sweeping it
            continue
        if f in KEYED or f == CORPORA:
            got = None
            if texts is not None:
                got = keyed_cases(f, *texts(f), cases) if f in KEYED else corpus_cases(*texts(f), cases)
            if got is None:
                return {**full, "reason": f"{f}: not narrowed to the entries it changes (unreadable, or outside them)"}
            touched |= got
            why.append(f"{f} ({len(got)} case(s))")
            continue
        if (got := component_cases(f, cases)) is not None:
            if set(cases) <= got:
                return {**full, "reason": f"{f}: its component is used by every case"}
            touched |= got
            why.append(f"{f} ({len(got)} case(s) use its component)")
            continue
        parts = f.split("/")
        if len(parts) < 4 or parts[:2] != ["tests", "equivalence"] or parts[2] not in cases:
            return {**full, "reason": f"{f} is not inside one existing case directory"}
        touched.add(parts[2])
    if translator:  # the port diff decides (the workflow runs det_port.py check, then --ports)
        return {
            "mode": "ports",
            "cases": sorted(touched),
            "db2_cases": [],  # not final: --ports decides
            "reason": f"translator / generator changed ({len(translator)} file(s)): prove the ports it changes",
        }
    affected = sorted(dependents(touched, cases))
    runnable = [c for c in affected if not is_db2(cases[c])]
    db2 = [c for c in affected if is_db2(cases[c])]  # #4901: proven by the db2 job
    return {"mode": "narrow", "cases": runnable, "db2_cases": db2,
            "reason": (f"shared files narrowed: {'; '.join(why)}; " if why else "")
                      + f"only case files changed: {', '.join(sorted(touched)) or 'none'}"
                      + (f" (+ dependents {', '.join(sorted(set(affected) - touched))})" if set(affected) - touched else "")}  # fmt: skip


def plan(
    files: list[str],
    event: str,
    cases: dict[str, dict],
    labels: list[str] | None = None,
    texts: Callable[[str], tuple[str | None, str | None]] | None = None,
) -> dict:
    """_plan(), then #6278: on a pull request the Db2 runners (each starts IBM's Db2 container, ~17% of PR runner minutes)
    run only when a changed file is in the Db2 area (change_classifier.db2_area) or a Db2 case moved. A plan that went
    full for another reason (a harness core file, an unplaceable file) keeps its non-Db2 sweep and drops the Db2 half;
    the nightly, a manual run and the `shepherd:full` label still prove every Db2 case."""
    p = _plan(files, event, cases, labels, texts)
    if event != "pull_request" or FULL_LABEL in (labels or []) or p["db2_cases"] != "all" or not files:
        return p  # an empty diff is "cannot tell": keep it full
    import change_classifier  # noqa: PLC0415 -- Evidence Refresh's sparse checkout holds this planner alone

    names = [n for n, c in cases.items() if is_db2(c)]
    if any(change_classifier.db2_area(f, names) for f in files):
        return p
    return {**p, "db2_cases": [], "reason": p["reason"] + "; no changed file is in the Db2 area: no Db2 shard"}


def narrow_by_ports(check: Path, touched: list[str], cases: dict[str, dict]) -> dict:
    """#4814: the plan after `det_port.py check`: the ports that differ from the base, the touched cases, and their
    dependents. A missing or unreadable check is a full sweep (when in doubt, full)."""
    try:
        rows = json.loads(check.read_text(encoding="utf-8"))
        moved = {r["case"] for r in rows if r.get("status") != "unchanged"}
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {
            "mode": "full",
            "cases": "all",
            "db2_cases": "all",
            "reason": f"no usable port diff ({e}): a full sweep",
        }
    affected = sorted(dependents(moved | set(touched), cases) & set(cases))
    runnable = [c for c in affected if not is_db2(cases[c])]
    db2 = [c for c in affected if is_db2(cases[c])]
    return {"mode": "narrow", "cases": runnable, "carried": len(cases) - len(affected),
            "db2_cases": db2,
            "reason": f"port diff: {len(moved)} port(s) changed of {len(rows)}; "
                      f"{len(cases) - len(affected)} case(s) carried forward unchanged"}  # fmt: skip


def shards_for(p: dict, durations: dict[str, float] | None = None, waiting: int | None = None) -> list[str]:
    """The runner labels for a plan, none for no cases. With `durations` (#5919): the fewest runners whose slowest fits
    SHARD_TARGET_S, at most MAX_SHARDS (halved while PR jobs queue), then fewer while the planned slowest/fastest ratio
    is over MAX_RATIO; the plan fails (PlanError) when too many cases are unmeasured. Without: MAX_SHARDS for a full
    sweep, one per PER_SHARD cases when narrow."""
    if p["mode"] == "ports":
        return []  # not final: --ports turns it into a narrow (or full) plan
    if durations is not None:
        names = sorted(n for n, c in case_dirs().items() if not is_db2(c)) if p["cases"] == "all" else list(p["cases"])
        n = _sized_shards(names, durations, waiting)
    elif p["mode"] == "full":
        n = MAX_SHARDS
    else:
        n = min(MAX_SHARDS, -(-len(p["cases"]) // PER_SHARD))
    return [f"{i}/{n}" for i in range(1, n + 1)]


def _loads(weight: dict[str, float], n: int) -> list[float]:
    """Planned seconds in each of `n` shards, longest case first into the lightest (what proof_sweep does)."""
    loads = [0.0] * max(1, n)
    for w in sorted(weight.values(), reverse=True):
        loads[loads.index(min(loads))] += w
    return loads


def planned_ratio(weight: dict[str, float], n: int) -> float | None:
    """Slowest / fastest shard's planned work for `n` shards; None for fewer than two, or an idle shard."""
    if n < 2 or not weight:
        return None
    loads = _loads(weight, n)
    return max(loads) / min(loads) if min(loads) > 0 else None


def _sized_shards(names: list[str], durations: dict[str, float], waiting: int | None) -> int:
    """The non-Db2 shard count for `names`: the target-fitting count (ci_shard_plan), reduced until the planned ratio is
    within MAX_RATIO (a smaller count balances better; one shard always does)."""
    shard_plan = _shard_plan()
    w, missing = shard_plan.weights(names, durations)
    shard_plan.check_measured(missing, len(w))
    n = shard_plan.shards_for(w, SHARD_SETUP_S, PROOF_JOBS, SHARD_TARGET_S, shard_plan.pool_cap(MAX_SHARDS, waiting))
    while n > 1 and (planned_ratio(w, n) or 0.0) > MAX_RATIO:
        n -= 1
    return n


def _shard_plan():
    """ci_shard_plan, imported when durations size a plan: Evidence Refresh's sparse checkout carries only this file."""
    import ci_shard_plan  # noqa: PLC0415 -- stdlib only, like this planner

    return ci_shard_plan


def load_durations(path: Path = DURATIONS) -> dict[str, float] | None:
    """{case: seconds} of the durations file's "det" section; None when the file is missing or unreadable."""
    try:
        return {k: float(v) for k, v in json.loads(path.read_text(encoding="utf-8")).get("det", {}).items()}
    except (OSError, ValueError, AttributeError):
        return None


def db2_names(p: dict) -> list[str]:
    return sorted(n for n, c in case_dirs().items() if is_db2(c)) if p["db2_cases"] == "all" else list(p["db2_cases"])


def db2_shards_for(p: dict, n_db2: int | None = None, durations: dict[str, float] | None = None,
                   waiting: int | None = None, setup_s: float | None = None) -> list[str]:  # fmt: skip
    """The Db2 runner labels "I/N". With `durations` (#5919): the fewest runners whose slowest fits DB2_TARGET_S, at most
    DB2_MAX_SHARDS (halved while PR jobs queue); the plan fails (PlanError) when too many cases are unmeasured. Without:
    one per DB2_FULL_PER_SHARD of the `n_db2` Db2 cases (default: the cases on disk) for a full sweep, one per
    DB2_PER_SHARD cases when narrow, at most DB2_MAX_SHARDS; none for none. `setup_s` (db2_shard_plan.measured_setup_s)
    replaces DB2_SETUP_S."""
    if p["mode"] == "ports" or not p["db2_cases"]:
        return []
    if durations is not None:
        shard_plan = _shard_plan()
        w, missing = shard_plan.weights(db2_names(p), durations)
        shard_plan.check_measured(missing, len(w), "Db2 case")
        n = shard_plan.shards_for(
            w,
            DB2_SETUP_S if setup_s is None else setup_s,
            PROOF_JOBS,
            DB2_TARGET_S,
            shard_plan.pool_cap(DB2_MAX_SHARDS, waiting),
            DB2_HEADROOM,
        )
        return [f"{i}/{n}" for i in range(1, n + 1)]
    if p["db2_cases"] == "all":
        if n_db2 is None:
            n_db2 = sum(is_db2(c) for c in case_dirs().values())
        n = -(-n_db2 // DB2_FULL_PER_SHARD)
    else:
        n = -(-len(p["db2_cases"]) // DB2_PER_SHARD)
    n = max(1, min(DB2_MAX_SHARDS, n))
    return [f"{i}/{n}" for i in range(1, n + 1)]


def timeouts_for(p: dict, durations: dict[str, float] | None, db2_setup_s: float | None = None) -> dict[str, int]:
    """#5919: the `timeout` (non-Db2 shard) and `db2_timeout` job minutes, from the slowest planned shard of the plan's
    matrices; DEFAULT_TIMEOUT for a kind with no durations or no shards."""
    out = {"timeout": DEFAULT_TIMEOUT, "db2_timeout": DB2_TIMEOUT_FLOOR}
    if durations is None:
        return out
    cases = case_dirs()
    sets = (("timeout", "matrix", SHARD_SETUP_S, [n for n, c in cases.items() if not is_db2(c)]
             if p["cases"] == "all" else list(p["cases"])),
            ("db2_timeout", "db2_matrix", DB2_SETUP_S if db2_setup_s is None else db2_setup_s, db2_names(p) if p["db2_cases"] else []))  # fmt: skip
    for key, matrix, setup, names in sets:
        n = len(p.get(matrix) or [])
        if n and names:
            shard_plan = _shard_plan()
            w, _ = shard_plan.weights(names, durations)
            if key == "db2_timeout":
                proving = shard_plan.shard_seconds(w, n, 0, PROOF_JOBS)  # the long pole included
                planned = SHARD_SETUP_S + DB2_WAIT_S + proving * shard_plan.MARGIN
                out[key] = max(DB2_TIMEOUT_FLOOR, min(DB2_TIMEOUT_CEILING, math.ceil(planned / 60)))
            else:
                out[key] = shard_plan.timeout_minutes(w, n, setup, PROOF_JOBS, TIMEOUT_FLOOR, TIMEOUT_CEILING)
    return out


def evidence_plan(
    durations: dict[str, float] | None,
    waiting: int | None = None,
    cases_dir: Path | None = None,
    db2_setup_s: float | None = None,
) -> dict:
    """#5919: Evidence Refresh's matrices and job timeouts, emitted by its `lane` job: `db2_parts` (the Db2 sweep parts plus
    "records"), `sweep_matrix` (the non-Db2 det cases), `records_matrix`, and `db2_timeout` / `sweep_timeout` /
    `records_timeout` in minutes. Without durations the counts fall back to the old fixed ones and every timeout to 90."""
    cdir = cases_dir or CASES
    cases = case_dirs(cdir)
    n_records = sum(1 for d in cdir.iterdir() if (d / "evidence.json").is_file())
    full = {"mode": "full", "cases": "all", "db2_cases": "all"}
    db2 = db2_shards_for(full, durations=durations, waiting=waiting, setup_s=db2_setup_s)
    out = {"db2_parts": [*db2, "records"], "sweep_matrix": [f"{i}/4" for i in range(1, 5)],
           "records_matrix": [f"{i}/6" for i in range(1, 7)], "db2_timeout": 90, "sweep_timeout": 90,
           "records_timeout": 90}  # fmt: skip
    if durations is None:
        return out
    sp = _shard_plan()
    db2_names_ = sorted(n for n, c in cases.items() if is_db2(c))
    w, _ = sp.weights(db2_names_, durations)
    db2_min = (
        sp.timeout_minutes(
            w,
            len(db2),
            DB2_SETUP_S if db2_setup_s is None else db2_setup_s,
            PROOF_JOBS,
            TIMEOUT_FLOOR,
            EVIDENCE_CEILING,
        )
        if db2
        else 0
    )
    names = sorted(n for n, c in cases.items() if not is_db2(c))
    w, missing = sp.weights(names, durations)
    sp.check_measured(missing, len(w))
    k = sp.shards_for(w, SHARD_SETUP_S, PROOF_JOBS, EVIDENCE_TARGET_S, sp.pool_cap(EVIDENCE_SWEEP_MAX_SHARDS, waiting))
    if k:
        out["sweep_matrix"] = [f"{i}/{k}" for i in range(1, k + 1)]
        out["sweep_timeout"] = sp.timeout_minutes(w, k, SHARD_SETUP_S, PROOF_JOBS, TIMEOUT_FLOOR, EVIDENCE_CEILING)
    rw = {f"r{i:04d}": RECORD_S for i in range(n_records)}
    r = sp.shards_for(rw, SHARD_SETUP_S, 1, EVIDENCE_TARGET_S, sp.pool_cap(EVIDENCE_RECORDS_MAX_SHARDS, waiting))
    if r:
        out["records_matrix"] = [f"{i}/{r}" for i in range(1, r + 1)]
        out["records_timeout"] = sp.timeout_minutes(rw, r, SHARD_SETUP_S, 1, TIMEOUT_FLOOR, EVIDENCE_CEILING)
    # the records part rides the Db2 matrix: one runner with Db2 up, re-proving the stale Db2 records
    out["db2_timeout"] = max(db2_min, out["records_timeout"])
    return out


def file_texts(base: str) -> Callable[[str], tuple[str | None, str | None]]:
    """#5885: path -> (the file at the merge base of `base` and HEAD, at HEAD); None for a side git cannot give."""

    def git_show(rev: str, path: str) -> str | None:
        proc = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=REPO_ROOT,  # noqa: S603, S607
                              capture_output=True, text=True, check=False)  # fmt: skip
        return proc.stdout if proc.returncode == 0 else None

    mb = subprocess.run(["git", "merge-base", base, "HEAD"], cwd=REPO_ROOT,  # noqa: S603, S607
                        capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
    return lambda path: (git_show(mb, path) if mb else None, git_show("HEAD", path))


def changed_files(base: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=REPO_ROOT,  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="pull_request")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*", help="the changed files, instead of git diff --name-only BASE...HEAD")
    ap.add_argument("--github-output", type=Path, help="append mode / cases / matrix / shards for later jobs")
    ap.add_argument("--ports", type=Path, help="#4814: det_port.py check's check.json -- plan from the port diff")
    ap.add_argument("--touched", default="", help="with --ports: case directories the PR changed (comma-separated)")
    ap.add_argument(
        "--labels-from-event",
        type=Path,
        nargs="?",
        const=Path(os.environ.get("GITHUB_EVENT_PATH", "")),
        help="read the PR's labels (shepherd:full forces a full sweep) from this event payload",
    )
    ap.add_argument(
        "--labels", help="the PR's labels, comma-separated, read live when the job runs (a rerun sees a new one)"
    )
    ap.add_argument("--durations", type=Path, default=DURATIONS,
                    help="#5919: the durations file the shard counts and timeouts are sized from (missing: counts only)")  # fmt: skip
    ap.add_argument("--waiting", type=int, help="#5919: queued PR jobs (halves the Db2 shard cap past ci_shard_plan.BUSY_ABOVE)")  # fmt: skip
    ap.add_argument("--db2-full-matrix", action="store_true",
                    help="#5882: print only a full sweep's Db2 runner labels as JSON (Evidence Refresh's Db2 parts)")  # fmt: skip
    ap.add_argument("--evidence-plan", action="store_true",
                    help="#5919: Evidence Refresh's matrices and timeouts (JSON on stdout; keys to --github-output)")  # fmt: skip
    ap.add_argument("--timing", type=Path, nargs="*", default=[],
                    help="#5919: shard timing artifacts (det_sweep_timing record) whose median setup replaces DB2_SETUP_S")  # fmt: skip
    args = ap.parse_args()
    setup_s = db2_setup_from(args.timing)
    if args.evidence_plan:
        ep = evidence_plan(load_durations(args.durations), args.waiting, db2_setup_s=setup_s)
        print(json.dumps(ep))
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as fh:
                for k, v in ep.items():
                    fh.write(f"{k}={json.dumps(v)}\n")
        return 0
    if args.db2_full_matrix:
        print(
            json.dumps(
                db2_shards_for(
                    {"mode": "full", "db2_cases": "all"},
                    durations=load_durations(args.durations),
                    waiting=args.waiting,
                    setup_s=setup_s,
                )
            )
        )
        return 0
    labels = labels_from_event(args.labels_from_event) if args.labels_from_event else []
    if args.labels is not None:
        labels = [x for x in args.labels.split(",") if x]
    cases = case_dirs()
    if args.ports:
        p = narrow_by_ports(args.ports, [c for c in args.touched.split(",") if c], cases)
        return emit(p, args.github_output, load_durations(args.durations), args.waiting, setup_s)
    try:
        files = args.files if args.files is not None else changed_files(args.base)
        p = plan(files, args.event, cases, labels, file_texts(args.base)) if files or args.event != "pull_request" else {
            "mode": "full", "cases": "all", "db2_cases": "all", "reason": "no changed files found (the diff is unreadable or empty)"}  # fmt: skip
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "cases": "all", "db2_cases": "all", "reason": f"cannot diff ({e})"}
    return emit(p, args.github_output, load_durations(args.durations), args.waiting, setup_s)


def db2_setup_from(timing_paths: list[Path]) -> float | None:
    """The Db2 runners' measured setup seconds from shard timing artifacts (db2_shard_plan.measured_setup_s); None without
    any, so the plan keeps DB2_SETUP_S. Imported here: Evidence Refresh's sparse checkout does not carry the module."""
    if not timing_paths:
        return None
    import db2_shard_plan  # noqa: PLC0415 -- stdlib only, like this planner

    return db2_shard_plan.measured_setup_s(db2_shard_plan.timing_rows(timing_paths), "db2", DB2_SETUP_S)


def emit(p: dict, github_output: Path | None, durations: dict[str, float] | None = None,
         waiting: int | None = None, db2_setup_s: float | None = None) -> int:  # fmt: skip
    p["matrix"] = shards_for(p, durations, waiting)
    if durations is not None and len(p["matrix"]) > 1:
        names = [n for n, c in case_dirs().items() if not is_db2(c)] if p["cases"] == "all" else list(p["cases"])
        ratio = planned_ratio(_shard_plan().weights(names, durations)[0], len(p["matrix"]))
        p["ratio"] = None if ratio is None else round(ratio, 3)
    p["shards"] = len(p["matrix"])
    p["db2_matrix"] = db2_shards_for(
        p, durations=durations, waiting=waiting, setup_s=db2_setup_s
    )  # a full sweep counts the Db2 cases on disk
    p["db2_shards"] = len(p["db2_matrix"])
    p.update(timeouts_for(p, durations, db2_setup_s))  # #5919: the shard jobs' timeout-minutes, emitted by the plan
    if durations is not None and p["db2_matrix"]:
        try:
            import db2_shard_plan  # noqa: PLC0415 -- the predicted slowest/fastest ratio (#5882: within 1.3x)
        except ImportError:  # a sparse checkout without it plans as before
            db2_shard_plan = None
        if db2_shard_plan:
            check = db2_shard_plan.plan_check(db2_names(p), durations, len(p["db2_matrix"]))
            p["db2_ratio"] = check["ratio"]
            if check["warning"]:
                print(f"::warning::{check['warning']}", file=sys.stderr)
    print(json.dumps(p, indent=1))
    if github_output:
        with github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\n")
            fh.write(f"cases={'all' if p['cases'] == 'all' else ','.join(p['cases'])}\n")
            fh.write(f"matrix={json.dumps(p['matrix'])}\n")
            fh.write(f"shards={p['shards']}\n")
            fh.write(f"db2_cases={'all' if p['db2_cases'] == 'all' else ','.join(p['db2_cases'])}\n")
            fh.write(f"db2_matrix={json.dumps(p['db2_matrix'])}\n")
            fh.write(f"db2_shards={p['db2_shards']}\n")
            fh.write(f"timeout={p['timeout']}\ndb2_timeout={p['db2_timeout']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
