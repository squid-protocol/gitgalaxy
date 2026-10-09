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
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = REPO_ROOT / "tests" / "equivalence"
MAX_SHARDS = 6  # full sweep: runners
PER_SHARD = 3  # narrow: about this many cases per runner
IGNORED = {"tests/equivalence/det_sweep_durations.json"}  # only balances shards, never a verdict
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


def plan(files: list[str], event: str, cases: dict[str, dict]) -> dict:
    """The plan for `files` (repo-relative, as git prints them) on `event`."""
    full = {"mode": "full", "cases": "all"}
    if event != "pull_request":
        return {**full, "reason": f"{event}: always a full sweep"}
    files = [f for f in files if f not in IGNORED and det_input(f)]
    if not files:
        return {"mode": "none", "cases": [], "reason": "no changed file is a det-sweep input (DET_INPUTS)"}
    touched: set[str] = set()
    for f in files:
        if f.startswith(LEDGER_DIR) and f.endswith(".json") and f[len(LEDGER_DIR) : -5] in cases:
            touched.add(f[len(LEDGER_DIR) : -5])  # #4789: a case's ledger entry is checked by sweeping that case
            continue
        parts = f.split("/")
        if len(parts) < 4 or parts[:2] != ["tests", "equivalence"] or parts[2] not in cases:
            return {**full, "reason": f"{f} is not inside one existing case directory"}
        touched.add(parts[2])
    affected = sorted(dependents(touched, cases))
    runnable = [c for c in affected if not is_db2(cases[c])]  # (the sweep is --skip-db2)
    return {"mode": "narrow", "cases": runnable,
            "reason": f"only case files changed: {', '.join(sorted(touched)) or 'none'}"
                      + (f" (+ dependents {', '.join(sorted(set(affected) - touched))})" if set(affected) - touched else "")}  # fmt: skip


def shards_for(p: dict) -> list[str]:
    """The runner labels for a plan: MAX_SHARDS for a full sweep, one per PER_SHARD cases when narrow, none for no cases."""
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
    args = ap.parse_args()
    cases = case_dirs()
    try:
        files = args.files if args.files is not None else changed_files(args.base)
        p = plan(files, args.event, cases) if files or args.event != "pull_request" else {
            "mode": "full", "cases": "all", "reason": "no changed files found (the diff is unreadable or empty)"}  # fmt: skip
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "cases": "all", "reason": f"cannot diff ({e})"}
    p["matrix"] = shards_for(p)
    p["shards"] = len(p["matrix"])
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\n")
            fh.write(f"cases={'all' if p['cases'] == 'all' else ','.join(p['cases'])}\n")
            fh.write(f"matrix={json.dumps(p['matrix'])}\n")
            fh.write(f"shards={p['shards']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
