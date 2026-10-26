#!/usr/bin/env python3
"""post-merge dispatch (#4825, cadence #5136): run the read-only heavy checks on main without starving PR jobs.

Run by .github/workflows/post-merge.yml (on every push to main and every 20 minutes; stdlib only; reads run metadata
through `gh api`, never runs PR code):

    python3 tests/tools/post_merge_dispatch.py [--dry-run]   # env: GH_TOKEN, DISPATCH_TOKEN (optional), GITHUB_REPOSITORY,
                                                             #      CADENCE_HOURS (default 3), WAITING_MAX (default 0)

Nothing is dispatched while any PR job is waiting for a runner. Otherwise, for each workflow in TARGETS, decide()
dispatches it on main's head SHA only when ALL of these hold:

  * it has no run on main for that SHA yet (a push and a cron tick for the same SHA dispatch once);
  * its newest non-cancelled run on main (a dispatch, the nightly schedule, or a tag-less push) started at least
    CADENCE_HOURS ago: idle at dispatch is not idle afterwards (#5136: Full Suite Gate dispatched once per main SHA
    took 15.6% of all CI minutes), so each target runs at most once per window, on the newest SHA;
  * main changed a file the workflow reads since that run's SHA (the RELEVANT patterns; for a workflow with
    `from-pr-filter`, its own `pull_request.paths`). A comparison that fails or is truncated counts as relevant.

A target whose run list cannot be read is skipped this tick (the next one retries) and the job fails at the end, so a
broken dispatcher is visible. Dispatch uses DISPATCH_TOKEN (the PAT) when set: a run created with the repo
GITHUB_TOKEN raises no `workflow_run`, so Main Watch would never see it (#4859).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
FROM_PR_FILTER = "from-pr-filter"
NOT_DOCS = ["**", "!docs/**", "!**/*.md"]
# workflow file -> the files whose change makes a new run worth having (GitHub path-filter globs, last match decides)
TARGETS: dict[str, list[str] | str] = {
    "full-suite-gate.yml": NOT_DOCS,  # #4825/#5136: the OS x Python matrix of the whole suite
    "os-smoke-grid.yml": NOT_DOCS,  # #5130
    "cics-crucible.yml": FROM_PR_FILTER,  # #5131
    "crucible-path-independence.yml": FROM_PR_FILTER,  # #6670: its job skips on a PR, so main is where it runs
    "estate-crucible.yml": FROM_PR_FILTER,
    "fact-crosscheck.yml": FROM_PR_FILTER,
    "ports-compile.yml": FROM_PR_FILTER,
    "unicode-gauntlet.yml": FROM_PR_FILTER,
    # #4599: deliberately every file -- a change outside its PR filter (aperture.py, #4569) moved every baseline once
    "tree-sitter-accuracy-audit.yml": ["**"],
}


def glob_re(pattern: str) -> re.Pattern[str]:
    """GitHub's filter glob as a regex: `**` any depth, `*` one segment, `?` one character (as workflow_inputs.py)."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def matches(path: str, patterns: list[str]) -> bool:
    """A path filter's verdict for one path: the last matching pattern decides; `!` excludes."""
    hit = False
    for p in patterns:
        neg = p.startswith("!")
        if glob_re(p[1:] if neg else p).match(path):
            hit = not neg
    return hit


def pr_paths(text: str) -> list[str]:
    """The `on.pull_request.paths` list of a workflow file, read without a YAML library (the dispatcher runs on the
    runner's bare python3). Handles the shape every target uses -- a block list of quoted strings, comments after
    them; test_post_merge_dispatch.py pins it against PyYAML for every FROM_PR_FILTER target."""
    lines, out = text.splitlines(), []
    try:
        start = lines.index("  pull_request:") + 1
    except ValueError:
        return []
    in_paths = False
    for line in lines[start:]:
        if line and not line.startswith("    "):
            break  # the next trigger, or the end of `on:`
        if line.strip() == "paths:":
            in_paths = True
            continue
        if not in_paths or line.lstrip().startswith("#") or not line.strip():
            continue
        m = re.match(r'\s+- "([^"]+)"', line)
        if not m:
            break  # the next key of pull_request
        out.append(m.group(1))
    return out


def patterns_for(workflow: str, workflows_dir: Path = WORKFLOWS) -> list[str]:
    spec = TARGETS[workflow]
    if spec == FROM_PR_FILTER:
        found = pr_paths((workflows_dir / workflow).read_text(encoding="utf-8"))
        return found or ["**"]  # no filter found: every change is relevant (fail-open)
    return list(spec)


def epoch(stamp: str) -> float:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def decide(
    sha: str,
    now: float,
    cadence_s: float,
    runs: list[dict[str, Any]],
    patterns: list[str],
    changed_since: Callable[[str], list[str] | None],
) -> tuple[bool, str]:
    """-> (dispatch?, reason). runs: the workflow's recent runs on branch main (any event); changed_since(base) lists
    the files changed from base to sha, or None when that is unknown (an error, a truncated or diverged comparison)."""
    runs = [r for r in runs if r.get("event") != "pull_request"]
    if any(r.get("head_sha") == sha for r in runs):
        return False, f"already has a run for {sha[:12]}"
    counted = [r for r in runs if r.get("conclusion") != "cancelled"]
    if not counted:
        return True, "no earlier run on main"
    last = max(counted, key=lambda r: epoch(r["created_at"]))
    age = now - epoch(last["created_at"])
    if age < cadence_s:
        return False, f"cadence: its last run on main ({last.get('event')}) started {age / 3600:.1f} h ago"
    changed = changed_since(last["head_sha"])
    if changed is None:
        return True, f"cannot tell what changed since {last['head_sha'][:12]}: running it"
    hit = next((f for f in changed if matches(f, patterns)), None)
    if hit is None:
        return False, f"no file it reads changed since {last['head_sha'][:12]} ({len(changed)} changed)"
    return True, f"{hit} (and {len(changed) - 1} more) changed since {last['head_sha'][:12]}"


# --- GitHub I/O -----------------------------------------------------------------------------------------------------


def gh(path: str) -> Any:
    res = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if res.returncode:
        raise RuntimeError(f"gh api {path[:100]} failed: {res.stderr.strip()[:200]}")
    return json.loads(res.stdout)


def waiting_pr_jobs(repo: str) -> int:
    """Queued PR runs, plus queued jobs inside PR runs that are in progress."""
    n = len(gh(f"repos/{repo}/actions/runs?event=pull_request&status=queued&per_page=100")["workflow_runs"])
    for run in gh(f"repos/{repo}/actions/runs?event=pull_request&status=in_progress&per_page=100")["workflow_runs"]:
        jobs = gh(f"repos/{repo}/actions/runs/{run['id']}/jobs?filter=latest&per_page=100")["jobs"]
        n += sum(1 for j in jobs if j.get("status") == "queued")
    return n


def changed_files(repo: str, base: str, head: str) -> list[str] | None:
    try:
        doc = gh(f"repos/{repo}/compare/{base}...{head}")
    except RuntimeError as exc:
        print(f"  compare failed: {exc}")
        return None
    files = doc.get("files")
    if doc.get("status") not in ("ahead", "identical") or files is None or len(files) >= 300:
        return None  # diverged (main was rewritten), or the API's 300-file cap: assume relevant
    return [f["filename"] for f in files] + [f["previous_filename"] for f in files if f.get("previous_filename")]


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv[1:]  # decide and print, dispatch nothing (still ignores the waiting PR jobs' verdict)
    repo = os.environ["GITHUB_REPOSITORY"]
    cadence_s = float(os.environ.get("CADENCE_HOURS") or 3) * 3600
    sha = gh(f"repos/{repo}/branches/main")["commit"]["sha"]
    print(f"main is at {sha}; cadence {cadence_s / 3600:g} h")
    waiting = waiting_pr_jobs(repo)
    waiting_max = int(os.environ.get("WAITING_MAX") or 0)
    print(f"PR jobs waiting for a runner: {waiting} (max {waiting_max})")
    if waiting > waiting_max and not dry:
        print("Deferring: PR checks are waiting for runners.")
        return 0
    errors = 0
    for wf in TARGETS:
        try:
            runs = gh(f"repos/{repo}/actions/workflows/{wf}/runs?branch=main&per_page=30")["workflow_runs"]
            go, reason = decide(
                sha, time.time(), cadence_s, runs, patterns_for(wf), lambda base: changed_files(repo, base, sha)
            )
        except Exception as exc:  # one broken target must not stop the others  # noqa: BLE001
            print(f"{wf}: skipped this tick, error: {exc}")
            errors += 1
            continue
        print(f"{wf}: {'dispatch' if go else 'skip'} -- {reason}")
        if go and not dry:
            env = dict(os.environ, GH_TOKEN=os.environ.get("DISPATCH_TOKEN") or os.environ.get("GH_TOKEN", ""))
            res = subprocess.run(  # noqa: S603
                ["gh", "workflow", "run", wf, "--repo", repo, "--ref", "main"],  # noqa: S607
                env=env,
                check=False,
            )
            errors += res.returncode != 0
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
