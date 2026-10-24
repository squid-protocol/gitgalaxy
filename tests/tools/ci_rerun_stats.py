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
WAIT_FAILED_MARKER = "the background Db2 start did not bring up GGDB"  # det-sweep.yml's wait step (#5601): its log then holds the docker tail
# (substring, cause) in precedence order, matched against a log that carries WAIT_FAILED_MARKER
DB2_START_CAUSES = (
    ("No space left on device", "db2_start_disk"),
    ("No such container", "db2_start_not_created"),
    (" Exited (", "db2_start_exited"),  # `docker ps -a` shows the container stopped
)
TIMEOUT_SLACK_S = 30  # a job cancelled this close to its cap (or over) hit timeout-minutes, not a person


def _secs(job: dict) -> float:
    try:
        a = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        b = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
    except (AttributeError, KeyError, TypeError, ValueError):
        return 0.0
    return (b - a).total_seconds()


def is_gate(job: dict) -> bool:
    """An aggregator job (`needs: [...]`, `if: always()`): every failed step of it only says a job it gates did not pass."""
    failed = [st.get("name", "").lower() for st in job.get("steps", []) if st.get("conclusion") == "failure"]
    return bool(failed) and all("passed" in n for n in failed)


def scope_jobs(job: dict, attempt_jobs: list[dict]) -> list[dict]:
    """The jobs to classify a failed `job` by: itself, or for a gate itself plus the other jobs of its attempt (#5605)."""
    if not is_gate(job):
        return [job]
    same = [j for j in attempt_jobs if j is not job and j.get("run_attempt") == job.get("run_attempt")]
    return [job, *same]


def db2_start_cause(log: str) -> str:
    """Why a Db2 start failed, read from the docker state and log tail the det-sweep wait step prints (#5601).

    db2_start_disk | db2_start_not_created | db2_start_exited | db2_start_setup_incomplete (container up, first-start
    setup never finished: a slow start) | db2_start (no tail in the log: expired, empty, or another step's log)."""
    if PULL_MARKER in log:
        return "registry_pull"
    if WAIT_FAILED_MARKER not in log:
        return "db2_start"
    for needle, cause in DB2_START_CAUSES:
        if needle in log:
            return cause
    return "db2_start" if "Setup has completed" in log else "db2_start_setup_incomplete"


def classify(
    jobs: list[dict], timeout_minutes: dict[str, int] | None = None, logs: dict[str, str] | None = None
) -> str:
    """One cause for a failed attempt: timeout | superseded | registry_pull | db2_start (or a db2_start_* sub-cause) | ratchet | artifact_missing | test_failure | other | none.

    `logs` maps a job name to its log text; only a failed Db2 step consults it (registry_pull vs db2_start, see db2_start_cause)."""
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
    gated = [j for j in bad if not is_gate(j)]
    if gated != bad and gated and all(j.get("conclusion") == "cancelled" for j in gated):
        return "superseded"  # a gate failed because its parts were cancelled early: a newer push, not a flake (#5605)
    for job in bad:
        for step in job.get("steps", []):
            if step.get("conclusion") != "failure":
                continue
            name = step.get("name", "").lower()
            if "db2" in name:
                return db2_start_cause(logs.get(job.get("name", ""), ""))
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


def has_failed_db2_step(job: dict) -> bool:
    return any(st.get("conclusion") == "failure" and "db2" in st.get("name", "").lower() for st in job.get("steps", []))


def job_log(job: dict) -> str:
    """The log of one job ("" when it has expired: classify() then falls back to db2_start)."""
    try:
        return _gh_text(f"repos/{REPO}/actions/jobs/{job['id']}/logs", "--allow-escape-sequences")
    except subprocess.CalledProcessError:
        return ""


def _db2_logs(jobs: list[dict]) -> dict[str, str]:
    """Logs of the jobs whose failed step is a Db2 one (the only ones classify() reads a log for)."""
    return {job["name"]: job_log(job) for job in jobs if has_failed_db2_step(job)}


def workflow_runs(wf: str, since: str, limit: int = 20) -> list[dict]:
    """Every run of `wf` created after `since`: pages of 100 until a short one (a single page missed the older ones)."""
    out: list[dict] = []
    for page in range(1, limit + 1):
        path = f"repos/{REPO}/actions/workflows/{wf}/runs?per_page=100&page={page}&created=%3E{since}"
        got = _gh(path)["workflow_runs"]
        out += got
        if len(got) < 100:
            break
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
        runs = workflow_runs(wf, args.since)
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
