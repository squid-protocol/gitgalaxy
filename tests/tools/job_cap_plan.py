#!/usr/bin/env python3
"""A job's `timeout-minutes` from its own measured wall time, for the workflows that have one fixed cap (#8701).

    python tests/tools/job_cap_plan.py --workflow tri-comparison-history.yml --job tri-comparison-history \\
        --floor 15 --ceiling 45 --fallback 30 [--step-margin 12] --github-output "$GITHUB_OUTPUT"

Reads the latest `--runs` completed runs of the workflow, takes the wall minutes of the named job in each, and plans
`cap = ceil(worst x HEADROOM)` clamped to [floor, ceiling]. It writes `cap=<minutes>` (and `step_cap=<cap - margin>`
with --step-margin) for a plan job to expose, which the job reads as
`timeout-minutes: ${{ fromJSON(needs.plan.outputs.cap || '<fallback>') }}`.

What counts as an observation:
  * every successful run's job;
  * a job that was stopped at its cap (wall within CUT_SLACK of the cap it ran under) UNLESS the step it was in is a
    setup step (install, fetch, checkout, cache, download ...): a hung `apt-get` is not slow work, and widening the
    window for it only lets the hang last longer (2026-11-23: tri-comparison's two 30-minute stops were both
    "Install universal-ctags" hung for ~29 minutes, while a normal run takes under 11).
A job that was cancelled for a newer push is neither: its wall is short.

With fewer than MIN_OBS observations, or when the runs cannot be read, nothing is written: the workflow's literal
fallback applies. The planner never fails the workflow, and exits 0 either way.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import ci_rerun_stats  # noqa: E402

HEADROOM = 1.3
MIN_OBS = 5
RUNS = 30
CUT_SLACK_MIN = 1.0  # a job that ended this close to its cap was stopped by it
# a stopped job whose running step looks like setup is a hang (or an outage), not evidence the work needs longer
SETUP_STEP_RE = re.compile(
    r"(?i)\b(install|set ?up|checkout|fetch|download|clone|cache|restore|pull|apt|pip|npm|docker)\b"
)


def wall_minutes(job: dict[str, Any]) -> float:
    return ci_rerun_stats._secs(job) / 60


def stopped_step(job: dict[str, Any]) -> str:
    """Name of the step a stopped job was in: the first cancelled step, else the last one that started."""
    steps = job.get("steps") or []
    for step in steps:
        if step.get("conclusion") == "cancelled":
            return str(step.get("name", ""))
    started = [s for s in steps if s.get("started_at")]
    return str(started[-1].get("name", "")) if started else ""


def observations(jobs: list[dict[str, Any]], job_name: str, fallback_cap: float) -> tuple[list[float], list[str]]:
    """(wall minutes that count, notes on the stops that do not), for the jobs named `job_name`."""
    walls: list[float] = []
    notes: list[str] = []
    for job in jobs:
        name = str(job.get("name", ""))
        if not (name == job_name or name.startswith(f"{job_name} (")) or not job.get("completed_at"):
            continue  # a matrix job reports its legs as `<name> (<matrix values>)`
        minutes = wall_minutes(job)
        if job.get("conclusion") == "success":
            walls.append(minutes)
        elif job.get("conclusion") in ("cancelled", "failure", "timed_out") and minutes >= fallback_cap - CUT_SLACK_MIN:
            step = stopped_step(job)
            if SETUP_STEP_RE.search(step):
                notes.append(f"stopped at {minutes:.1f} min in setup step '{step}': a hang, not counted")
            else:
                walls.append(minutes)  # stopped mid-work: the work needs at least this long
    return walls, notes


def plan_cap(
    walls: list[float], floor: int, ceiling: int, headroom: float = HEADROOM, min_obs: int = MIN_OBS
) -> int | None:
    """worst x headroom, clamped to [floor, ceiling]; None when there are too few observations to plan from."""
    if len(walls) < min_obs:
        return None
    return int(min(ceiling, max(floor, math.ceil(max(walls) * headroom))))


def load_jobs(workflow: str, runs: int = RUNS) -> list[dict[str, Any]]:
    listing = ci_rerun_stats._gh(
        f"repos/{ci_rerun_stats.REPO}/actions/workflows/{workflow}/runs?status=completed&per_page={runs}"
    )["workflow_runs"]
    jobs: list[dict[str, Any]] = []
    for run in listing[:runs]:
        try:  # one run whose jobs cannot be read (a transient 502) is skipped, not a reason to drop the whole history
            jobs += ci_rerun_stats._gh(f"repos/{ci_rerun_stats.REPO}/actions/runs/{run['id']}/jobs?per_page=100")[
                "jobs"
            ]
        except (subprocess.CalledProcessError, ValueError, KeyError):
            print(f"job_cap_plan: run {run.get('id')} skipped (jobs unreadable)", file=sys.stderr)
    return jobs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--job", required=True, help="the job's `name` as the Actions API reports it")
    ap.add_argument("--floor", type=int, required=True)
    ap.add_argument("--ceiling", type=int, required=True)
    ap.add_argument("--fallback", type=int, required=True, help="the literal cap the workflow uses without a plan")
    ap.add_argument("--step-margin", type=int, default=0, help="also write step_cap = cap - this many minutes")
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--github-output")
    args = ap.parse_args(argv)
    try:
        walls, notes = observations(load_jobs(args.workflow, args.runs), args.job, args.fallback)
    except Exception as e:  # the plan must never fail the workflow: any read failure means the fallback
        print(
            f"job_cap_plan: history unavailable ({type(e).__name__}); using the literal {args.fallback} min",
            file=sys.stderr,
        )
        return 0
    for note in notes:
        print(f"job_cap_plan: {note}", file=sys.stderr)
    cap = plan_cap(walls, args.floor, args.ceiling)
    if cap is None:
        print(
            f"job_cap_plan: {len(walls)} observation(s) of {args.job} (< {MIN_OBS}); using the literal {args.fallback} min"
        )
        return 0
    worst = max(walls)
    print(f"job_cap_plan: {args.job}: {len(walls)} runs, worst {worst:.1f} min x {HEADROOM} -> cap {cap} min "
          f"(floor {args.floor}, ceiling {args.ceiling}, literal {args.fallback})")  # fmt: skip
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"cap={cap}\n")
            if args.step_margin:
                fh.write(f"step_cap={max(1, cap - args.step_margin)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
