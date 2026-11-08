#!/usr/bin/env python3
"""Whether a pull request needs the Mainframe Ground Truth proof (the "plan" job of mainframe-ground-truth.yml, #5164).

    python tests/tools/ground_truth_plan.py [--event pull_request] [--base origin/main] [--files FILE ...] [--github-output PATH]

`ground-truth` is a required check, so its workflow cannot take a path filter (a filtered-out required check never
reports). Instead it always starts and reports, and this planner decides how much it proves, as det_sweep_plan.py does
for `det` (#4825): a pull request whose every changed file is a NON_INPUT (docs, .claude/, churn / shepherd tooling,
workflows the job does not read, test directories it does not run ...) proves nothing (mode "none"); anything else is
"full". A pull request of only det_mutation / det_mutation_survivors JSON is mode "select" (#7963): only the
tests/cobol_mainframe/ files that read that data run (`mutation_readers`), one part, no ledger gate. Every event that is not a pull_request (main push, nightly, manual) is full, as is an unreadable or empty diff.

The job reads the whole engine (gitgalaxy/), the answer keys, the corpora pins, the tests and the tools they import, so
this is an ALLOW-list of what it provably does not read, not a list of what it does: a file that matches nothing is an
input. INPUTS win over NON_INPUTS. tests/tools/test_ground_truth_plan.py checks that no NON_INPUT tool is referenced,
transitively, by tests/cobol_mainframe/ or the ledger tool. Stdlib only: the job runs before anything is installed.

Prints JSON {mode, reason, inputs}; with --github-output appends mode=none|select|full, and tests=<files> in select mode.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

DOCS = "docs/"

# fnmatch: `*` also crosses `/`. Checked first: these are inputs even where a NON_INPUTS pattern would match.
INPUTS = (
    "gitgalaxy/*",  # the engine, the registries, the forges (also its READMEs)
    "tests/cobol_mainframe/*",  # the tests, the answer keys, the ledger, the corpora pins
    "tests/equivalence/*",  # the det cases the tests read
    "docs/self_scan/ground_truth_history.jsonl",
    ".github/workflows/mainframe-ground-truth.yml",
    "tests/tools/ci_retry.sh",  # the workflow wraps its pip installs in it (#5048)
    # workflows a test reads (test_db2_odbc_pin); the other workflows are only named in comments
    ".github/workflows/det-sweep.yml",
    ".github/workflows/evidence-refresh.yml",
    # tests/tools modules a cobol_mainframe test imports (bare), named as tests
    "tests/tools/test_blocker_report.py",  # test_blocker_leak_burned_5054.py collects its leak scan (#5054)
    "tests/tools/test_cics_spec_status.py",
    "tests/tools/test_evidence_report.py",
    "tests/tools/test_generated_docs.py",
    "tests/tools/test_maven_exe_4939.py",
)

# What the job does not read. Anything matching neither list is an input.
NON_INPUTS = (
    "docs/*",  # minus the INPUTS above and the docs/ files the job's code names (is_input asks the classifier)
    "*.md",  # minus the INPUTS above (gitgalaxy/, tests/cobol_mainframe/)
    ".claude/*",
    ".github/*",  # minus the workflows above; issue templates, dependabot, the other workflows
    # churn / shepherd / CI-digest tooling (never imported by the job's tests; the guard test proves it)
    "tests/tools/box/*",
    "tests/tools/shepherd_gh.py",
    "tests/tools/ci_rerun_stats.py",
    "tests/tools/ci_job_summary.py",
    "tests/tools/contract_pr_check.py",
    "tests/tools/pin_ci_requirements.sh",
    "tests/tools/workflow_inputs.py",
    "tests/tools/main_watch.py",
    "tests/tools/post_merge_dispatch.py",
    "tests/tools/test_*.py",  # tests/tools is not run by this job; minus the four modules INPUTS names
    # test directories the job does not run or import
    "tests/extraction/*",
    "tests/core_engine/*",
    "tests/golden_master_audit/*",
    "tests/golden_master_zero_dep_audit/*",
    "tests/security_auditing/*",
    "tests/tools_recorders/*",
    "tests/unicode_gauntlet/*",
)


MUTATION_DATA = (
    "tests/equivalence/det_mutation/",
    "tests/equivalence/det_mutation_survivors/",
)  # the data a select PR carries
_TOKEN = re.compile(r"det_mutation|mutation_survivors|mutation_scores|survivors")


def _text(p: Path) -> str:
    """Lossless read for a name search; stdlib-only (the plan job runs before anything is installed): latin-1 never fails."""
    data = p.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def mutation_readers(root: Path = REPO_ROOT) -> list[str]:
    """The tests/cobol_mainframe/ test files that read the mutation data: they name it, or import a tests/tools module that does.

    One level of import (a module that names the data), not the transitive closure: that closure is 144 of 449 files because
    every case test imports `equivalence`, which does not read the data. Residual risk: a test that reaches the data only
    through a module that imports one of those; main's push and nightly runs are always full, so it is caught there."""
    tools = {p.stem: _text(p) for p in (root / "tests/tools").glob("*.py")}
    named = [s for s, t in tools.items() if not s.startswith("test_") and _TOKEN.search(t)]
    importers = [
        re.compile(rf"(?m)^\s*(?:import|from)\s+{re.escape(s)}\b|\bimport\s+[\w, ]*\b{re.escape(s)}\b") for s in named
    ]
    out = []
    for p in sorted((root / "tests/cobol_mainframe").glob("test_*.py")):
        text = _text(p)
        if _TOKEN.search(text) or any(rx.search(text) for rx in importers):
            out.append(p.relative_to(root).as_posix())
    return out


def mutation_data_only(files: list[str]) -> bool:
    return bool(files) and all(f.startswith(MUTATION_DATA) and f.endswith(".json") for f in files)


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def is_input(path: str) -> bool:
    """True unless `path` is provably something the ground-truth job does not read (when in doubt, an input).

    A docs/ file is an input only when code the job runs names it (change_classifier.py, #6278): the register,
    oracle_assumptions.md, the rule catalogue and the self_scan ledgers a tool reads are; zos_probes.json and unread prose
    are not. (Before, only docs/language_status/ asked; the rest of docs/ was skipped even where a reader opened it.) A tests/tools module nothing the job runs names is not either. Every other skip is
    the NON_INPUTS list, as before."""
    if matches(path, INPUTS):
        return True
    if path.startswith(DOCS):
        return change_classifier.read_by_ground_truth(path)
    if path.startswith("tests/tools/") and not matches(path, NON_INPUTS):
        return change_classifier.runs_in_ground_truth(path)  # a tool nothing the job runs names (ladder_refresh.py)
    return not matches(path, NON_INPUTS)


def plan(files: list[str], event: str) -> dict:
    if event == "merge_group":  # the merge queue re-checks only repo-wide guards (suite_select_plan.MERGE_GUARDS)
        return {"mode": "none", "reason": "merge queue: the PR's own run checked the ground truth", "inputs": []}
    if event != "pull_request":
        return {"mode": "full", "reason": f"{event}: always the full check", "inputs": []}
    if change_classifier.docs_only(files):  # #7963: registers / history lines carry no code the proof reads
        return {"mode": "none", "reason": "docs-only record PR (change_classifier.DOCS_ONLY_RECORDS)", "inputs": []}
    if mutation_data_only(files):  # #7963: the readers are the only tests the data can move
        tests = mutation_readers()
        if tests:
            return {
                "mode": "select",
                "reason": f"mutation data only: {len(tests)} reader test file(s), no ledger gate",
                "inputs": [],
                "tests": tests,
            }
    inputs = sorted(f for f in files if is_input(f))
    if not files:
        return {"mode": "full", "reason": "no changed files found (the diff is unreadable or empty)", "inputs": []}
    if inputs:
        return {
            "mode": "full",
            "reason": f"{len(inputs)} changed file(s) are ground-truth inputs, first: {inputs[0]}",
            "inputs": inputs[:20],
        }
    return {"mode": "none", "reason": "no changed file is a ground-truth input (NON_INPUTS)", "inputs": []}


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
    ap.add_argument("--github-output", type=Path, help="append mode=none|full for later jobs")
    args = ap.parse_args()
    try:
        files = (
            args.files if args.files is not None else (changed_files(args.base) if args.event == "pull_request" else [])
        )
        p = plan(files, args.event)
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "reason": f"cannot diff ({e})", "inputs": []}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\n")
            if p.get("tests"):
                fh.write(f"tests={' '.join(p['tests'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
