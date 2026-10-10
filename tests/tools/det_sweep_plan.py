#!/usr/bin/env python3
"""Which det-sweep cases a change needs proven, and on how many runners (the "plan" job of det-sweep.yml, #4463).

    python tests/tools/det_sweep_plan.py [--event pull_request] [--base origin/main] [--files FILE ...] [--github-output PATH]

A pull request that changes no det input (DET_INPUTS: docs, other engine code ...) proves nothing (mode "none"; #4825,
so the workflow can run -- and report its required `det` check -- on every PR). One that changes only files under
tests/equivalence/<case>/ re-proves those cases (and the cases that
take that case's port: `port_from`, `uses_ports`, transitively); so does one changing a case's coverage-ledger file,
tests/equivalence/det_sweep_coverage/<case>.json (#4789: the sweep of that case is what checks the entry). Anything
else -- the translator, the harness, the tools, the corpora pin, the workflow, the baseline, a file straight under
tests/equivalence/, a case directory with no case.json (a case added or removed), an unreadable diff -- is a full
sweep, as is every event that is not a pull request (nightly, manual). When in doubt, full. Stdlib only: the job runs
before anything is installed.

Prints JSON {mode, cases, shards, matrix, reason}: `cases` is "all" or the names; `matrix` the shard labels "I/N".
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = REPO_ROOT / "tests" / "equivalence"
MAX_SHARDS = 20  # full sweep: runners (#4814: work-sized; a narrow plan starts one per PER_SHARD cases)
PER_SHARD = 3  # narrow: about this many cases per runner
IGNORED = {"tests/equivalence/det_sweep_durations.json"}  # only balances shards, never a verdict
# #4814: a change confined to these is judged by what it does to the generated ports: `det_port.py check` translates
# every case at the base and at HEAD and names the ports that differ; only those (and their dependents) are proven.
# Only the translator + runtime -- everything a port's bytes come from. Anything else that can move a verdict without
# moving a byte (the harness, proof_reach.py, the oracle) stays a full sweep.
PORT_DIFF = "gitgalaxy/tools/cobol_to_java/det/"

# What a det proof reads (#4825: moved here from det-sweep.yml's trigger, so the workflow runs -- and reports `det` --
# on every PR). A PR that changes none of these proves nothing (mode "none"). fnmatch: `*` also crosses `/`.
DET_INPUTS = (
    "gitgalaxy/tools/cobol_to_java/*",
    "tests/tools/det_port.py",
    "tests/tools/det_parity.py",
    "tests/tools/proof_sweep.py",
    "tests/tools/det_sweep_plan.py",
    "tests/tools/equivalence*.py",
    "tests/tools/mainframe_corpus.py",
    "tests/equivalence/*",
    "tests/cobol_mainframe/corpora.json",
    ".github/workflows/det-sweep.yml",
)


def det_input(path: str) -> bool:
    return not path.endswith(".md") and any(fnmatch.fnmatch(path, p) for p in DET_INPUTS)


# #4789: <case>.json, the det-sweep coverage ledger's entry of a case
LEDGER_DIR = "tests/equivalence/det_sweep_coverage/"


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


FULL_LABEL = "shepherd:full"  # #4847: a maintainer's request for the full sweep on a pull request (docs/ci.md)


def labels_from_event(path: Path) -> list[str]:
    """The pull request's label names from the event payload (GITHUB_EVENT_PATH); [] when there is none."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [x.get("name", "") for x in (payload.get("pull_request") or {}).get("labels") or []]


def plan(files: list[str], event: str, cases: dict[str, dict], labels: list[str] | None = None) -> dict:
    """The plan for `files` (repo-relative, as git prints them) on `event`, given the pull request's `labels`."""
    full = {"mode": "full", "cases": "all"}
    if event != "pull_request":
        return {**full, "reason": f"{event}: always a full sweep"}
    if FULL_LABEL in (labels or []):
        return {**full, "reason": f"labelled {FULL_LABEL}: a full sweep on request"}
    files = [f for f in files if f not in IGNORED and det_input(f)]
    if not files:
        return {"mode": "none", "cases": [], "reason": "no changed file is a det-sweep input (DET_INPUTS)"}
    touched: set[str] = set()
    translator = sorted(f for f in files if f.startswith(PORT_DIFF))
    for f in files:
        if f.startswith(PORT_DIFF):
            continue
        if f.startswith(LEDGER_DIR) and f.endswith(".json") and f[len(LEDGER_DIR) : -5] in cases:
            touched.add(f[len(LEDGER_DIR) : -5])  # #4789: a case's ledger entry is checked by sweeping that case
            continue
        parts = f.split("/")
        if len(parts) < 4 or parts[:2] != ["tests", "equivalence"] or parts[2] not in cases:
            return {**full, "reason": f"{f} is not inside one existing case directory"}
        touched.add(parts[2])
    if translator:  # the port diff decides (the workflow runs det_port.py check, then --ports)
        return {
            "mode": "ports",
            "cases": sorted(touched),
            "reason": f"translator changed ({len(translator)} file(s)): prove the ports it changes",
        }
    affected = sorted(dependents(touched, cases))
    runnable = [c for c in affected if not is_db2(cases[c])]  # (the sweep is --skip-db2)
    return {"mode": "narrow", "cases": runnable,
            "reason": f"only case files changed: {', '.join(sorted(touched)) or 'none'}"
                      + (f" (+ dependents {', '.join(sorted(set(affected) - touched))})" if set(affected) - touched else "")}  # fmt: skip


def narrow_by_ports(check: Path, touched: list[str], cases: dict[str, dict]) -> dict:
    """#4814: the plan after `det_port.py check`: the ports that differ from the base, the touched cases, and their
    dependents. A missing or unreadable check is a full sweep (when in doubt, full)."""
    try:
        rows = json.loads(check.read_text(encoding="utf-8"))
        moved = {r["case"] for r in rows if r.get("status") != "unchanged"}
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {"mode": "full", "cases": "all", "reason": f"no usable port diff ({e}): a full sweep"}
    affected = sorted(dependents(moved | set(touched), cases) & set(cases))
    runnable = [c for c in affected if not is_db2(cases[c])]
    db2 = [c for c in affected if is_db2(cases[c])]
    return {"mode": "narrow", "cases": runnable, "carried": len(cases) - len(affected),
            "db2_not_swept": db2,
            "reason": f"port diff: {len(moved)} port(s) changed of {len(rows)}; "
                      f"{len(cases) - len(affected)} case(s) carried forward unchanged"}  # fmt: skip


def shards_for(p: dict) -> list[str]:
    """The runner labels for a plan: MAX_SHARDS for a full sweep, one per PER_SHARD cases when narrow, none for no cases."""
    if p["mode"] == "ports":
        return []  # not final: --ports turns it into a narrow (or full) plan
    if p["mode"] == "full":
        n = MAX_SHARDS
    else:
        n = min(MAX_SHARDS, -(-len(p["cases"]) // PER_SHARD))
    return [f"{i}/{n}" for i in range(1, n + 1)]


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
    args = ap.parse_args()
    labels = labels_from_event(args.labels_from_event) if args.labels_from_event else []
    if args.labels is not None:
        labels = [x for x in args.labels.split(",") if x]
    cases = case_dirs()
    if args.ports:
        p = narrow_by_ports(args.ports, [c for c in args.touched.split(",") if c], cases)
        return emit(p, args.github_output)
    try:
        files = args.files if args.files is not None else changed_files(args.base)
        p = plan(files, args.event, cases, labels) if files or args.event != "pull_request" else {
            "mode": "full", "cases": "all", "reason": "no changed files found (the diff is unreadable or empty)"}  # fmt: skip
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "cases": "all", "reason": f"cannot diff ({e})"}
    return emit(p, args.github_output)


def emit(p: dict, github_output: Path | None) -> int:
    p["matrix"] = shards_for(p)
    p["shards"] = len(p["matrix"])
    print(json.dumps(p, indent=1))
    if github_output:
        with github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\n")
            fh.write(f"cases={'all' if p['cases'] == 'all' else ','.join(p['cases'])}\n")
            fh.write(f"matrix={json.dumps(p['matrix'])}\n")
            fh.write(f"shards={p['shards']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
