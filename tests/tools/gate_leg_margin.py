#!/usr/bin/env python3
"""#8701: how close each Full Suite Gate leg's "Full Suite" step finishes to its step cap, over scheduled runs.

    python tests/tools/gate_leg_margin.py [--runs 5] [--min-margin 3] [--os windows]

The gate's caps are planner-written (`${{ matrix.timeout }}`), so ci_cap_headroom skips them. This reads the leg name
`full-suite-matrix (os, py, part, splits[, even], timeout, step_timeout)` of the latest completed scheduled runs, takes
the wall minutes of the step named `Full Suite ...` (the job wall when that step is missing), and reports, per leg
(os, python, part), the worst wall against its step cap. Exit 1 when any leg is within `--min-margin` minutes of its
cap (a leg cut at its cap has a negative margin) or when fewer than `--runs` scheduled runs had a measured leg (a leg that never ran its tests to the end is not one): the check is
unconfirmed until the nightlies have run.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import ci_rerun_stats  # noqa: E402

WORKFLOW = "full-suite-gate.yml"
LEG = re.compile(r"^full-suite-matrix \((?P<args>[^)]*)\)$")
STEP_PREFIX = "Full Suite ("
CUT_SLACK_S = 60  # a step ending this close to its cap was cut by it


def parse_leg(name: str) -> dict | None:
    """The leg of a job name, or None for another job: os, python, part, splits, timeout, step_timeout (minutes)."""
    m = LEG.match(name)
    if not m:
        return None
    parts = [p.strip() for p in m.group("args").split(",")]
    if len(parts) < 6 or not all(p.isdigit() for p in parts[2:4] + parts[-2:]):
        return None
    return {
        "os": parts[0],
        "python": parts[1],
        "part": int(parts[2]),
        "splits": int(parts[3]),
        "timeout": int(parts[-2]),
        "step_timeout": int(parts[-1]),
    }


def full_suite_step(job: dict) -> dict | None:
    for step in job.get("steps") or []:
        if str(step.get("name", "")).startswith(STEP_PREFIX):
            return step
    return None


def is_measured(job: dict, leg: dict) -> bool:
    """True when the leg's `Full Suite` step ran its tests to the end or was cut at its cap.

    A leg that never reached the step, or whose step failed early (an install or import error, a cancelled run) has a
    short wall that says nothing about margin, so it is not an observation (#8701).
    """
    step = full_suite_step(job)
    if step is None or step.get("conclusion") == "skipped":
        return False
    if step.get("conclusion") == "success":
        return True
    return ci_rerun_stats._secs(step) >= leg["step_timeout"] * 60 - CUT_SLACK_S


def step_minutes(job: dict) -> float:
    """Wall minutes of the job's `Full Suite (...)` step, else of the whole job."""
    for step in job.get("steps") or []:
        if str(step.get("name", "")).startswith(STEP_PREFIX):
            return ci_rerun_stats._secs(step) / 60
    return ci_rerun_stats._secs(job) / 60


def margins(jobs_by_run: list[list[dict]], os_prefix: str = "") -> dict[tuple, tuple[int, float, int]]:
    """(os, python, part) -> (step cap, wall minutes of the tightest run, runs seen) over the runs' completed jobs."""
    rows: dict[tuple, tuple[int, float, int]] = {}
    for jobs in jobs_by_run:
        for job in jobs:
            leg = parse_leg(job.get("name", ""))
            if not leg or not leg["os"].startswith(os_prefix) or not job.get("completed_at"):
                continue
            if job.get("conclusion") == "skipped" or not is_measured(job, leg):
                continue
            key = (leg["os"], leg["python"], leg["part"])
            cap, wall, seen = rows.get(key, (leg["step_timeout"], 0.0, 0))
            this = (leg["step_timeout"], step_minutes(job))
            # the tightest observation, each judged against the cap of its own run (the plan moves between runs)
            if seen == 0 or this[0] - this[1] < cap - wall:
                cap, wall = this
            rows[key] = (cap, wall, seen + 1)
    return rows


def measured_runs(jobs_by_run: list[list[dict]], os_prefix: str = "") -> int:
    """Runs with at least one measured leg: only those count toward the required scheduled runs."""
    n = 0
    for jobs in jobs_by_run:
        for job in jobs:
            leg = parse_leg(job.get("name", ""))
            if leg and leg["os"].startswith(os_prefix) and job.get("completed_at") and is_measured(job, leg):
                n += 1
                break
    return n


def tight(rows: dict[tuple, tuple[int, float, int]], min_margin: float) -> list[tuple]:
    """Legs whose cap is under `min_margin` minutes over the worst wall (compared against the bound, not a ratio)."""
    return sorted(k for k, (cap, wall, _n) in rows.items() if cap < wall + min_margin)


def scheduled_jobs(n_runs: int, since: str = "") -> list[list[dict]]:
    runs = ci_rerun_stats._gh(
        f"repos/{ci_rerun_stats.REPO}/actions/workflows/{WORKFLOW}/runs?event=schedule&status=completed&per_page={n_runs}"
        + (f"&created=%3E{since}" if since else "")
    )["workflow_runs"]
    return [
        ci_rerun_stats._gh(f"repos/{ci_rerun_stats.REPO}/actions/runs/{r['id']}/jobs?per_page=100")["jobs"]
        for r in runs[:n_runs]
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=5, help="scheduled runs required and sampled")
    ap.add_argument("--min-margin", type=float, default=3.0, help="minutes a leg must finish under its step cap")
    ap.add_argument("--os", default="windows", help="leg os prefix to check ('' for every leg)")
    ap.add_argument(
        "--since",
        default="",
        help="YYYY-MM-DD: only runs created after it (e.g. 2026-11-22, the day #8975 raised the caps)",
    )
    args = ap.parse_args(argv)
    by_run = scheduled_jobs(args.runs, args.since)
    rows = margins(by_run, args.os)
    flagged = set(tight(rows, args.min_margin))
    for key, (cap, wall, seen) in sorted(rows.items()):
        mark = "  TIGHT" if key in flagged else ""
        print(
            f"{key[0]} {key[1]} part {key[2]}: step cap {cap} min, tightest {wall:.1f} min, margin {cap - wall:.1f} min, {seen} runs{mark}"
        )
    used = measured_runs(by_run, args.os)
    short = used < args.runs
    if short:
        print(f"UNCONFIRMED: {used} of {args.runs} scheduled runs measured ({len(by_run)} sampled)")
    return 1 if flagged or short or not rows else 0


if __name__ == "__main__":
    sys.exit(main())
