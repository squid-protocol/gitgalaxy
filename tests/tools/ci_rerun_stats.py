#!/usr/bin/env python3
"""#5137: how often a workflow is re-run, and why its first attempt failed.

    python tests/tools/ci_rerun_stats.py mainframe-ground-truth.yml det-sweep.yml --since 2026-10-13

Counts runs with run_attempt > 1 per workflow per UTC day (the reruns/day measure) and classifies each failed first
attempt from its failed/cancelled job and step: timeout (cancelled at the job's timeout-minutes), registry/network
(a failed Db2 start step is db2_start; when the job's log carries the INFRASTRUCTURE marker of a failed image pull it
is registry_pull, an external cause: --logs fetches that one log), ratchet, other. The classifier takes plain job dicts (the REST `jobs` shape), so it is tested offline.
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from datetime import datetime

REPO = "squid-protocol/gitgalaxy"
PULL_MARKER = "INFRASTRUCTURE (not a code defect): could not pull"  # equivalence_db2.Db2ImagePullError (#5097)
TIMEOUT_SLACK_S = 30  # a job cancelled this close to its cap (or over) hit timeout-minutes, not a person


def _secs(job: dict) -> float:
    try:
        a = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        b = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
    except (AttributeError, KeyError, TypeError, ValueError):
        return 0.0
    return (b - a).total_seconds()


def classify(
    jobs: list[dict], timeout_minutes: dict[str, int] | None = None, logs: dict[str, str] | None = None
) -> str:
    """One cause for a failed attempt: timeout | registry_pull | db2_start | ratchet | artifact_missing | test_failure | other | none.

    `logs` maps a job name to its log text; only a failed Db2 step consults it (registry_pull vs db2_start)."""
    timeout_minutes = timeout_minutes or {}
    logs = logs or {}
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
                return "registry_pull" if PULL_MARKER in logs.get(job.get("name", ""), "") else "db2_start"
            if "ratchet" in name:
                return "ratchet"
            if name.startswith("download"):
                return "artifact_missing"  # the producing job skipped or failed (#5177 publish-history)
            if "tests" in name or "pytest" in name:
                return "test_failure"  # a real failure, or main moved under a stale PR (#5173): check the test, not a retry
    return "other"


def per_day(runs: list[dict]) -> dict[str, int]:
    """Re-run attempts (run_attempt - 1) per UTC day of the run's creation."""
    out: dict[str, int] = collections.Counter()
    for run in runs:
        extra = int(run.get("run_attempt", 1)) - 1
        if extra > 0:
            out[str(run["created_at"])[:10]] += extra
    return dict(sorted(out.items()))


def step_secs(jobs: list[dict], step_name: str) -> list[float]:
    """Seconds each job spent in the step whose name contains `step_name` (the cache-hit vs cache-miss bimodality, #5142)."""
    needle = step_name.lower()
    return [
        _secs(step)
        for job in jobs
        for step in job.get("steps", [])
        if needle in step.get("name", "").lower() and step.get("conclusion") != "skipped"
    ]


def _gh_text(path: str, *flags: str) -> str:
    return subprocess.run(["gh", "api", *flags, path], capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def _gh(path: str) -> dict:
    return json.loads(_gh_text(path))


def _db2_logs(jobs: list[dict]) -> dict[str, str]:
    """Logs of the jobs whose failed step is a Db2 one (the only ones classify() reads a log for)."""
    out: dict[str, str] = {}
    for job in jobs:
        if any(
            st.get("conclusion") == "failure" and "db2" in st.get("name", "").lower() for st in job.get("steps", [])
        ):
            try:
                out[job["name"]] = _gh_text(f"repos/{REPO}/actions/jobs/{job['id']}/logs", "--allow-escape-sequences")
            except subprocess.CalledProcessError:
                out[job["name"]] = ""  # an expired log: classify() falls back to db2_start
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workflows", nargs="+")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD")
    ap.add_argument("--timeout", action="append", default=[], metavar="JOB=MIN", help="job timeout-minutes")
    ap.add_argument(
        "--step", help="also print the seconds each run's jobs spent in the step with this name (substring)"
    )
    ap.add_argument(
        "--logs", action="store_true", help="read the log of a failed Db2 step to tell a registry pull failure"
    )
    args = ap.parse_args(argv)
    caps = {k: int(v) for k, v in (t.split("=") for t in args.timeout)}
    for wf in args.workflows:
        runs = _gh(f"repos/{REPO}/actions/workflows/{wf}/runs?per_page=100&created=%3E{args.since}")["workflow_runs"]
        print(f"{wf}: re-run attempts per day {per_day(runs)}")
        for run in runs:
            for attempt in range(1, int(run.get("run_attempt", 1))):
                jobs = _gh(f"repos/{REPO}/actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100")["jobs"]
                print(
                    f"  run {run['id']} attempt {attempt}: {classify(jobs, caps, _db2_logs(jobs) if args.logs else None)}"
                )
            if args.step:
                jobs = _gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
                print(f"  run {run['id']} step '{args.step}' secs: {[round(x) for x in step_secs(jobs, args.step)]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
