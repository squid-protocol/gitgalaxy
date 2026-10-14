#!/usr/bin/env python3
"""#5137: how often a workflow is re-run, and why its first attempt failed.

    python tests/tools/ci_rerun_stats.py mainframe-ground-truth.yml det-sweep.yml --since 2026-10-13

Counts runs with run_attempt > 1 per workflow per UTC day (the reruns/day measure) and classifies each failed first
attempt from its failed/cancelled job and step: timeout (cancelled at the job's timeout-minutes), registry/network
(an INFRASTRUCTURE marker or a registry error is not available from the job JSON, so a Db2 start step is reported as
db2_start), ratchet, other. The classifier takes plain job dicts (the REST `jobs` shape), so it is tested offline.
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from datetime import datetime

REPO = "squid-protocol/gitgalaxy"
TIMEOUT_SLACK_S = 30  # a job cancelled this close to its cap (or over) hit timeout-minutes, not a person


def _secs(job: dict) -> float:
    try:
        a = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        b = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return 0.0
    return (b - a).total_seconds()


def classify(jobs: list[dict], timeout_minutes: dict[str, int] | None = None) -> str:
    """One cause for a failed attempt: timeout | db2_start | ratchet | other | none."""
    timeout_minutes = timeout_minutes or {}
    bad = [j for j in jobs if j.get("conclusion") in ("failure", "cancelled", "timed_out")]
    if not bad:
        return "none"
    for job in bad:
        cap = timeout_minutes.get(job.get("name", ""))
        if job.get("conclusion") == "timed_out" or (
            cap and job.get("conclusion") == "cancelled" and _secs(job) >= cap * 60 - TIMEOUT_SLACK_S
        ):
            return "timeout"
    for job in bad:
        for step in job.get("steps", []):
            if step.get("conclusion") != "failure":
                continue
            name = step.get("name", "").lower()
            if "db2" in name:
                return "db2_start"
            if "ratchet" in name:
                return "ratchet"
    return "other"


def per_day(runs: list[dict]) -> dict[str, int]:
    """Re-run attempts (run_attempt - 1) per UTC day of the run's creation."""
    out: dict[str, int] = collections.Counter()
    for run in runs:
        extra = int(run.get("run_attempt", 1)) - 1
        if extra > 0:
            out[str(run["created_at"])[:10]] += extra
    return dict(sorted(out.items()))


def _gh(path: str) -> dict:
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)  # noqa: S603, S607
    return json.loads(proc.stdout)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workflows", nargs="+")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD")
    ap.add_argument("--timeout", action="append", default=[], metavar="JOB=MIN", help="job timeout-minutes")
    args = ap.parse_args(argv)
    caps = {k: int(v) for k, v in (t.split("=") for t in args.timeout)}
    for wf in args.workflows:
        runs = _gh(f"repos/{REPO}/actions/workflows/{wf}/runs?per_page=100&created=%3E{args.since}")["workflow_runs"]
        print(f"{wf}: re-run attempts per day {per_day(runs)}")
        for run in runs:
            for attempt in range(1, int(run.get("run_attempt", 1))):
                jobs = _gh(f"repos/{REPO}/actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100")["jobs"]
                print(f"  run {run['id']} attempt {attempt}: {classify(jobs, caps)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
