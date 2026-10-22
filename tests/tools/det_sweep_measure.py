#!/usr/bin/env python3
"""#5135: det sweep jobs per run and `det` wall time, before vs after a cut-over (the 6-shard change, #5139).

    python tests/tools/det_sweep_measure.py --cut 2026-10-14T21:52:10Z --since 2026-10-10 --min-runs 10

Takes the newest `pull_request` Det Sweep runs, uses each run's last attempt, and reports per side (before/after the
cut) the median and p75 of: jobs per run, `det` wall time (latest attempt started to the `det` job completed, so queue wait counts),
and shard queue wait (job created to started). A run whose `det` job did not succeed is counted as `det_not_green`
(`det` fails on a missing case, so a green `det` means missing_cases was empty); a cancelled or skipped `det` is dropped. The maths takes plain REST dicts, so
it is tested offline.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import subprocess
import sys
from datetime import datetime

REPO = "squid-protocol/gitgalaxy"


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _gap(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    return (_ts(b) - _ts(a)).total_seconds()


def run_stats(run: dict, jobs: list[dict]) -> dict | None:
    """Per-run numbers, or None when there is no completed `det` job (still running, skipped, cancelled)."""
    det = next(
        (
            j
            for j in jobs
            if j.get("name") == "det" and j.get("completed_at") and j.get("conclusion") in ("success", "failure")
        ),
        None,
    )
    if det is None:
        return None
    queues = [q for j in jobs if (q := _gap(j.get("created_at"), j.get("started_at"))) is not None]
    return {
        "jobs": len(jobs),
        "det_wall_s": _gap(run.get("run_started_at") or run["created_at"], det["completed_at"]),
        "max_queue_s": max(queues) if queues else 0.0,
        "det_green": det.get("conclusion") == "success",
    }


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, round(pct * (len(ordered) - 1)))]


def summarize(rows: list[dict]) -> dict:
    """Median and p75 of each measure over `rows` (run_stats results), plus how many `det` jobs were not green."""
    out: dict = {"runs": len(rows), "det_not_green": sum(1 for r in rows if not r["det_green"])}
    for key in ("jobs", "det_wall_s", "max_queue_s"):
        vals = [r[key] for r in rows]
        out[key] = {"median": statistics.median(vals) if vals else 0.0, "p75": percentile(vals, 0.75)}
    return out


def split(rows: list[tuple[str, dict]], cut: str) -> tuple[list[dict], list[dict]]:
    """(before, after) by run creation time against `cut`; rows are (created_at, run_stats)."""
    c = _ts(cut)
    before = [s for t, s in rows if _ts(t) < c]
    after = [s for t, s in rows if _ts(t) >= c]
    return before, after


def _gh(path: str) -> dict:
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)  # noqa: S603, S607
    return json.loads(proc.stdout)


def _fmt(name: str, s: dict) -> str:
    return (
        f"{name}: {s['runs']} runs, det_not_green {s['det_not_green']}, jobs/run median {s['jobs']['median']:g} "
        f"(p75 {s['jobs']['p75']:g}), det wall median {s['det_wall_s']['median'] / 60:.1f} min "
        f"(p75 {s['det_wall_s']['p75'] / 60:.1f}), worst queue wait median {s['max_queue_s']['median'] / 60:.1f} min"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cut", required=True, help="ISO time of the change (UTC)")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD, oldest run to read")
    ap.add_argument("--min-runs", type=int, default=10)
    ap.add_argument("--workflow", default="det-sweep.yml")
    ap.add_argument("--full-jobs", type=int, default=10, help="jobs per run that mark a full sweep")
    ap.add_argument("--pages", type=int, default=5, help="pages of 100 runs to read")
    args = ap.parse_args(argv)
    runs: list[dict] = []
    for page in range(1, args.pages + 1):
        got = _gh(
            f"repos/{REPO}/actions/workflows/{args.workflow}/runs?per_page=100&page={page}"
            f"&event=pull_request&created=%3E{args.since}"
        )["workflow_runs"]
        runs += got
        if len(got) < 100:
            break
    done = [r for r in runs if r.get("status") == "completed"]

    def one(run: dict) -> tuple[str, dict] | None:
        jobs = _gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100&filter=latest")["jobs"]
        stats = run_stats(run, jobs)
        return (run["created_at"], stats) if stats else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        rows = [r for r in pool.map(one, done) if r]
    before, after = split(rows, args.cut)
    print(_fmt("before", summarize(before)))
    print(_fmt("after", summarize(after)))
    # a narrow plan (a few cases) starts one shard per PER_SHARD cases; a full sweep is the run the cut-over was for
    full = args.full_jobs
    print(_fmt(f"before, >={full} jobs", summarize([r for r in before if r["jobs"] >= full])))
    print(_fmt(f"after, >={full} jobs", summarize([r for r in after if r["jobs"] >= full])))
    short = [n for n, side in (("before", before), ("after", after)) if len(side) < args.min_runs]
    if short:
        print(f"fewer than {args.min_runs} runs on: {', '.join(short)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
