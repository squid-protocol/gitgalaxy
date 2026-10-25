#!/usr/bin/env python3
"""#5156: how close each workflow job's fixed `timeout-minutes` cap sits to its measured wall time.

    python tests/tools/ci_cap_headroom.py --since 2026-10-10 [--workflow det-sweep.yml ...]

Reads every job's literal `timeout-minutes` from .github/workflows, takes the worst wall time of that job over the
successful runs created after `--since`, and flags a job whose cap is under MIN_HEADROOM x that wall time (the
shard-planned caps, written as `${{ ... }}`, are the planner's and are skipped). A job with no sampled run is listed
as unsampled, not as fine. Exit 1 when any job is tight.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import ci_rerun_stats  # noqa: E402

WORKFLOWS = TOOLS.parents[1] / ".github" / "workflows"
MIN_HEADROOM = 1.5
CUT_SHARE = 0.95
CUT_MAX = 1.05
DEEP_FACTOR = 4  # a job with no sample is looked for again over this many times more runs


def literal_caps(workflow_text: str) -> dict[str, int]:
    """Job display name -> literal job-level timeout-minutes (an expression cap is the planner's: left out)."""
    caps: dict[str, int] = {}
    for key, job in ((yaml.safe_load(workflow_text) or {}).get("jobs") or {}).items():
        cap = job.get("timeout-minutes") if isinstance(job, dict) else None
        if isinstance(cap, int) and not isinstance(cap, bool):
            caps[str(job.get("name", key))] = cap
    return caps


def cap_for(job_name: str, caps: dict[str, int]) -> tuple[str, int] | None:
    """The (declared name, cap) a run's job belongs to: exact, else the longest declared name the run name starts with
    (a matrix leg is `name (axis, ...)`)."""
    if job_name in caps:
        return job_name, caps[job_name]
    best = [n for n in caps if "${{" not in n and job_name.startswith(n + " (")]
    best += [
        n for n in caps if "${{" in n and job_name.startswith(n.split("${{")[0])
    ]  # a templated name: its literal prefix
    if best:
        n = max(best, key=len)
        return n, caps[n]
    return None


def headroom(jobs: list[dict], caps: dict[str, int]) -> dict[str, tuple[int, float, float]]:
    """Declared job name -> (cap minutes, worst wall minutes, cap / worst) over the completed successful `jobs`."""
    worst: dict[str, float] = {}
    for job in jobs:
        if job.get("conclusion") != "success":
            continue
        hit = cap_for(job.get("name", ""), caps)
        if hit:
            worst[hit[0]] = max(worst.get(hit[0], 0.0), ci_rerun_stats._secs(job) / 60)
    return {n: (caps[n], w, caps[n] / w if w else float("inf")) for n, w in worst.items()}


def cut_at_cap(jobs: list[dict], caps: dict[str, int]) -> dict[str, tuple[float, int]]:
    """Declared job name -> (longest wall minutes, job id) of a cancelled job that ran to its cap (CUT_SHARE to CUT_MAX).

    A candidate only: a re-push cancels a job too, so `stopped_by_cap` confirms it from the job's annotation."""
    cut: dict[str, tuple[float, int]] = {}
    for job in jobs:
        hit = cap_for(job.get("name", ""), caps)
        if job.get("conclusion") not in ("cancelled", "timed_out") or not hit:
            continue
        wall = ci_rerun_stats._secs(job) / 60
        if hit[1] * CUT_SHARE <= wall <= hit[1] * CUT_MAX and wall >= cut.get(hit[0], (0.0, 0))[0]:
            cut[hit[0]] = (wall, int(job.get("id", 0)))
    return cut


def stopped_by_cap(job_id: int) -> bool:
    """True when GitHub's annotation on the job says it hit its maximum execution time."""
    notes = ci_rerun_stats._gh(f"repos/{ci_rerun_stats.REPO}/check-runs/{job_id}/annotations")
    return any("exceeded the maximum execution time" in str(n.get("message", "")) for n in notes)


def tight(rows: dict[str, tuple[int, float, float]], minimum: float = MIN_HEADROOM) -> list[str]:
    """Names whose cap is under `minimum` x the worst wall time (compared against the scaled bound, not a ratio)."""
    return sorted(n for n, (cap, wall, _r) in rows.items() if cap < wall * minimum)


def sample_jobs(workflow: str, since: str, max_runs: int) -> tuple[list[dict], list[dict]]:
    """The jobs of the latest `max_runs` successful runs, plus cancelled ones (a run cut at a cap is not successful)."""
    runs: list[dict] = []
    for status in ("success", "cancelled"):
        runs += ci_rerun_stats._gh(
            f"repos/{ci_rerun_stats.REPO}/actions/workflows/{workflow}/runs"
            f"?status={status}&per_page={max_runs}&created=%3E{since}"
        )["workflow_runs"]
    jobs: list[dict] = []
    for run in runs:
        jobs += ci_rerun_stats._gh(f"repos/{ci_rerun_stats.REPO}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
    return jobs, runs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", required=True, help="YYYY-MM-DD")
    ap.add_argument("--workflow", action="append", default=[], help="a workflow file name (default: all)")
    ap.add_argument("--max-runs", type=int, default=8, help="successful runs sampled per workflow")
    args = ap.parse_args(argv)
    files = sorted(WORKFLOWS / w for w in args.workflow) if args.workflow else sorted(WORKFLOWS.glob("*.yml"))
    bad = 0
    for path in files:
        caps = literal_caps(path.read_text(encoding="utf-8"))
        if not caps:
            continue
        jobs, runs = sample_jobs(path.name, args.since, args.max_runs)
        rows = headroom(jobs, caps)
        if set(caps) - set(rows) and args.max_runs * DEEP_FACTOR <= 100:
            jobs, runs = sample_jobs(path.name, args.since, args.max_runs * DEEP_FACTOR)
            rows = headroom(jobs, caps)
        for name, (wall, job_id) in sorted(cut_at_cap(jobs, caps).items()):
            if stopped_by_cap(job_id):
                print(f"{path.name}: {name}: cap {caps[name]} min, a run was stopped at {wall:.1f} min  TIGHT")
                bad += 1
        flagged = set(tight(rows))
        for name, (cap, wall, ratio) in sorted(rows.items()):
            print(
                f"{path.name}: {name}: cap {cap} min, worst {wall:.1f} min, {ratio:.1f}x{'  TIGHT' if name in flagged else ''}"
            )
        for name in sorted(set(caps) - set(rows)):
            print(f"{path.name}: {name}: cap {caps[name]} min, unsampled ({len(runs)} runs)")
        bad += len(flagged)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
