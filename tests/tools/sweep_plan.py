#!/usr/bin/env python3
"""Whether a pull request needs the extraction ReDoS sweeps (the "Plan the ReDoS sweeps" step of smoke-test.yml, #5166).

    python tests/tools/sweep_plan.py [--event pull_request] [--base origin/main] [--files FILE ...] [--labels L,L] [--github-output PATH]
    python tests/tools/sweep_plan.py --pr-files LIST --pr-file-count N ...   # the PR's own file list (the workflow)
    python tests/tools/sweep_plan.py --replay 50                              # how many recent merged PRs would have skipped

The sweeps are the tests under tests/extraction/ that tests/conftest.py marks `redos_sweep` (the name has `redos` or
`linear_on_pathological`): about 18 of the 19 minutes of that directory. A pull request that changes nothing they read
deselects them (mode "none": the full-suite parts run `-m "not golden_crucible and not redos_sweep"`); `full-suite` still
runs and reports. Every event that is not a pull_request (main push, nightly, manual), the `shepherd:full` label, and an
unreadable or empty diff are "full".

The sweeps read the engine (gitgalaxy/, minus ENGINE_NON_INPUTS: the parts outside their import closure), the
extraction tests and their harness, the suite's own config and the dependency pins, so this is an ALLOW-list of what they provably do not read, not a list of what they do: a file that
matches nothing is an input (as ground_truth_plan.py, #5164). INPUTS win over NON_INPUTS. Stdlib only: the step runs
before anything is installed.

Prints JSON {mode, reason, inputs}; with --github-output appends mode=none|full.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FULL_LABEL = "shepherd:full"

# fnmatch: `*` also crosses `/`. Checked first: these are inputs even where a NON_INPUTS pattern would match.
INPUTS = (
    "gitgalaxy/*",  # the engine and its registries (also its READMEs)
    "tests/extraction/*",  # the sweeps and their harness
    "tests/conftest.py",  # the marker hook
    "pyproject.toml",  # markers, addopts, pytest / ruff config
    "requirements*.txt",
    "ci/requirements/*",  # the pinned test environment
    ".github/workflows/smoke-test.yml",  # the step itself
    ".github/workflows/full-suite-gate.yml",  # the matrix runs the same marker
    "tests/tools/sweep_plan.py",
    "tests/tools/test_sweep_plan.py",
)

# Parts of gitgalaxy/ that the sweeps provably do not import: none of these is in the (static, function-level imports
# included) import closure of tests/extraction, which test_sweep_plan.py recomputes. They win over INPUTS' `gitgalaxy/*`.
# A directory with any module in that closure (core/, metrics/, recorders/, security/, standards/ ...) stays an input.
ENGINE_NON_INPUTS = (
    "gitgalaxy/tools/cobol_to_java/*",  # the deterministic COBOL -> Java translator, its runtime and copybooks
    "gitgalaxy/tools/terabyte_log_scanning/*",
    "gitgalaxy/standards/cics/*",  # the CICS command spec
    "gitgalaxy/cobol_to_java_controller.py",
    "gitgalaxy/cobol_refractor_controller.py",
)

# What the sweeps do not read. Anything matching neither list is an input.
NON_INPUTS = (
    "docs/*",
    "*.md",  # minus the engine's READMEs (INPUTS)
    ".claude/*",
    ".github/*",  # minus the two workflows above: the other workflows, issue templates, dependabot
    "tests/cobol_mainframe/*",
    "tests/equivalence/*",
    "tests/tools/*",  # minus the sweep planner above; the sweeps import none of these (test_sweep_plan guards it)
)


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def is_input(path: str) -> bool:
    """True unless `path` is provably something the sweeps do not read (when in doubt, an input)."""
    if matches(path, ENGINE_NON_INPUTS):
        return False
    return matches(path, INPUTS) or not matches(path, NON_INPUTS)


def plan(files: list[str], event: str, labels: list[str] | None = None) -> dict:
    full = {"mode": "full", "inputs": []}
    if event != "pull_request":
        return {**full, "reason": f"{event}: always the full sweep"}
    if FULL_LABEL in (labels or []):
        return {**full, "reason": f"labelled {FULL_LABEL}: the full sweep on request"}
    if not files:
        return {**full, "reason": "no changed files found (the diff is unreadable or empty)"}
    inputs = sorted(f for f in files if is_input(f))
    if inputs:
        return {
            "mode": "full",
            "reason": f"{len(inputs)} changed file(s) are sweep inputs, first: {inputs[0]}",
            "inputs": inputs[:20],
        }
    return {"mode": "none", "reason": "no changed file is a sweep input (NON_INPUTS)", "inputs": []}


def changed_files(base: str) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def pr_files(path: Path, count: str) -> list[str]:
    """#5882: the changed files from the pull request's own list (`gh api --paginate repos/R/pulls/N/files --jq '.[] |
    {filename, previous_filename}'`, one object a line), so the step needs no git history. A renamed file counts
    under both names. A list that is not the whole of the PR's `count` files (a failed call; the API stops at 3000)
    cannot tell what changed."""
    try:
        rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError) as e:
        raise RuntimeError(f"the PR's file list is unreadable: {e}") from e
    if not count.strip().isdigit() or len(rows) != int(count):
        raise RuntimeError(f"the PR's file list has {len(rows)} of {count.strip() or '?'} files")
    return sorted({n for r in rows for n in (r.get("filename"), r.get("previous_filename")) if n})


def sweep_seconds(durations: dict[str, float]) -> float:
    """Serial seconds of the tests tests/conftest.py marks `redos_sweep`, from a pytest-split durations file
    ({nodeid: seconds}): under tests/extraction, the function name (parameters dropped) has `redos` or
    `linear_on_pathological`."""
    total = 0.0
    for nodeid, secs in durations.items():
        path, _, name = nodeid.partition("::")
        name = name.rsplit("::", 1)[-1].split("[", 1)[0]
        if path.startswith("tests/extraction/") and ("redos" in name or "linear_on_pathological" in name):
            total += secs
    return total


def replay(prs: list[dict], durations: dict[str, float]) -> dict:
    """#5166: of the pull requests in `prs` (`gh pr list --json number,files`), how many plan "none". A PR whose `files`
    list holds 100 entries may be cut short by gh: it counts as full (when in doubt, run)."""
    skipped = []
    for pr in prs:
        files = [f["path"] for f in pr.get("files") or [] if f.get("path")]
        if len(files) < 100 and plan(files, "pull_request")["mode"] == "none":
            skipped.append(pr["number"])
    per_run = sweep_seconds(durations)
    return {
        "prs": len(prs),
        "skipped": len(skipped),
        "share": round(len(skipped) / len(prs), 3) if prs else 0.0,
        "sweep_serial_seconds_per_run": round(per_run, 1),
        "serial_minutes_saved": round(len(skipped) * per_run / 60, 1),
        "skipped_prs": skipped,
    }


def run_replay(n: int) -> dict:
    proc = subprocess.run(
        ["gh", "pr", "list", "--state", "merged", "-L", str(n), "--json", "number,files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr list failed")
    durations = json.loads((REPO_ROOT / ".test_durations").read_text(encoding="utf-8"))
    return replay(json.loads(proc.stdout), durations)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="pull_request")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*", help="the changed files, instead of git diff --name-only BASE...HEAD")
    ap.add_argument("--pr-files", type=Path, help="the PR's file list (see pr_files), instead of git diff")
    ap.add_argument("--pr-file-count", default="", help="the PR's changed_files: the list must hold exactly this many")
    ap.add_argument("--labels", default="", help="the PR's labels, comma-separated (read live by the step)")
    ap.add_argument("--github-output", type=Path, help="append mode=none|full for later steps")
    ap.add_argument(
        "--replay", type=int, metavar="N", help="plan the last N merged PRs (needs gh) and report the skip share"
    )
    args = ap.parse_args()
    if args.replay:
        try:
            print(json.dumps(run_replay(args.replay), indent=1))
        except (RuntimeError, OSError, ValueError) as e:
            print(f"replay failed: {e}", file=sys.stderr)
            return 1
        return 0
    labels = [x for x in args.labels.split(",") if x]
    try:
        if args.pr_files is not None and args.event == "pull_request":
            files = pr_files(args.pr_files, args.pr_file_count)
        else:
            files = (
                args.files
                if args.files is not None
                else (changed_files(args.base) if args.event == "pull_request" else [])
            )
        p = plan(files, args.event, labels)
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "reason": f"cannot diff ({e})", "inputs": []}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
