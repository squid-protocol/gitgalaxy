#!/usr/bin/env python3
"""#5135: det sweep jobs per run and `det` wall time, before vs after a cut-over (the 6-shard change, #5139).

    python tests/tools/det_sweep_measure.py --cut 2026-10-14T21:52:10Z --since 2026-10-10 --min-runs 10
    python tests/tools/det_sweep_measure.py db2 --since 2026-10-23 [--cut 2026-10-25T00:00:00Z]

Takes the newest `pull_request` Det Sweep runs, uses each run's last attempt, and reports per side (before/after the
cut) the median and p75 of: jobs per run, `det` wall time (latest attempt started to the `det` job completed, so queue wait counts),
and shard queue wait (job created to started). A run whose `det` job did not succeed is counted as `det_not_green`
(`det` fails on a missing case, so a green `det` means missing_cases was empty); a cancelled or skipped `det` is dropped. The maths takes plain REST dicts, so
it is tested offline.

The `db2` mode (#5882) measures the Db2 acceptance instead: per run the slowest and fastest `db2 I/N` job (start to
completion), their ratio, and db2 jobs killed by the job timeout; `db2_acceptance` groups runs by shard count and counts
the runs over the 15 min / 1.3x limits.
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


TIMEOUT_TEXT = "exceeded the maximum execution time"
DB2_LIMIT_S = 15 * 60
DB2_RATIO = 1.3


def db2_run_stats(run: dict, jobs: list[dict], annotations: dict[int, list[str]] | None = None) -> dict | None:
    """Db2 numbers for one run, or None when no db2 job succeeded or timed out (none planned, skipped, superseded).

    Only successful jobs give shard times (a cancelled one was cut short by a newer push). A job that did not succeed
    counts as `timed_out` when one of its annotation messages (`annotations`, job id -> messages) holds the runner's
    "exceeded the maximum execution time" text, else as `other_failures` when it failed."""
    annotations = annotations or {}
    db2 = [j for j in jobs if str(j.get("name", "")).startswith("db2") and j.get("completed_at")]
    ok = [j for j in db2 if j.get("conclusion") == "success"]
    hit = [
        j
        for j in db2
        if j.get("conclusion") != "success" and any(TIMEOUT_TEXT in m for m in annotations.get(j.get("id"), []))
    ]
    timed_out = len(hit)
    failed = sum(1 for j in db2 if j.get("conclusion") == "failure" and j not in hit)
    if not ok and not timed_out:
        return None
    times = [t for j in ok if (t := _gap(j.get("started_at"), j["completed_at"])) is not None]
    slowest, fastest = (max(times), min(times)) if times else (0.0, 0.0)
    return {
        "db2_jobs": len(db2),
        "ok_jobs": len(ok),
        "slowest_s": slowest,
        "fastest_s": fastest,
        "ratio": slowest / fastest if fastest > 0 else 1.0,
        "timed_out": timed_out,
        "other_failures": failed,
        "complete": len(ok) == len(db2),
    }


def db2_acceptance(rows: list[dict], limit_s: float = DB2_LIMIT_S, ratio: float = DB2_RATIO) -> dict[int, dict]:
    """Per planned shard count (db2_jobs): runs, runs with the slowest shard at or over `limit_s`, runs with the
    slowest/fastest ratio over `ratio`, timeouts, and the median/max slowest and median ratio. Only runs where every
    db2 job succeeded count toward the shard times; a timeout counts wherever it happened."""
    out: dict[int, dict] = {}
    for n in sorted({r["db2_jobs"] for r in rows}):
        group = [r for r in rows if r["db2_jobs"] == n]
        done = [r for r in group if r["complete"]]
        slow = [r["slowest_s"] for r in done]
        ratios = [r["ratio"] for r in done]
        out[n] = {
            "runs": len(done),
            "over_limit": sum(1 for v in slow if v >= limit_s),
            "over_ratio": sum(1 for v in ratios if v > ratio),
            "timeouts": sum(r["timed_out"] for r in group),
            "other_failures": sum(r["other_failures"] for r in group),
            "slowest_median_s": statistics.median(slow) if slow else 0.0,
            "slowest_max_s": max(slow) if slow else 0.0,
            "ratio_median": statistics.median(ratios) if ratios else 0.0,
        }
    return out


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


def _fmt_db2(label: str, by_shards: dict[int, dict]) -> list[str]:
    lines = [f"{label}: no run with a db2 job"] if not by_shards else []
    for n, a in by_shards.items():
        lines.append(
            f"{label}, {n} db2 jobs: {a['runs']} complete runs, slowest shard >= 15 min in {a['over_limit']} "
            f"(median {a['slowest_median_s'] / 60:.1f} min, max {a['slowest_max_s'] / 60:.1f}), ratio > 1.3 in "
            f"{a['over_ratio']} (median {a['ratio_median']:.2f}), timeouts {a['timeouts']}, other failures {a['other_failures']}"
        )
    return lines


def _runs(args: argparse.Namespace) -> list[dict]:
    runs: list[dict] = []
    for page in range(1, args.pages + 1):
        got = _gh(
            f"repos/{REPO}/actions/workflows/{args.workflow}/runs?per_page=100&page={page}"
            f"&event={args.event}&created=%3E{args.since}"
        )["workflow_runs"]
        runs += got
        if len(got) < 100:
            break
    return [r for r in runs if r.get("status") == "completed"]


def db2_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="det_sweep_measure.py db2", description="Db2 shard acceptance (#5882)")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD, oldest run to read")
    ap.add_argument("--cut", help="ISO time (UTC): report runs before and after it separately")
    ap.add_argument("--workflow", default="det-sweep.yml")
    ap.add_argument("--event", default="pull_request", help="pull_request, push or workflow_dispatch")
    ap.add_argument("--pages", type=int, default=10, help="pages of 100 runs to read (the API stops near 1000 runs)")
    args = ap.parse_args(argv)

    def one(run: dict) -> tuple[str, dict] | None:
        jobs = _gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100&filter=latest")["jobs"]
        notes: dict[int, list[str]] = {}
        for j in jobs:  # annotations only for a db2 job that did not succeed: that is where a timeout shows
            if str(j.get("name", "")).startswith("db2") and j.get("conclusion") in ("failure", "cancelled"):
                found = _gh(f"repos/{REPO}/check-runs/{j['id']}/annotations")
                notes[j["id"]] = [str(a.get("message", "")) for a in found] if isinstance(found, list) else []
        stats = db2_run_stats(run, jobs, notes)
        return (run["created_at"], stats) if stats else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        rows = [r for r in pool.map(one, _runs(args)) if r]
    if args.cut:
        before, after = split(rows, args.cut)
        sides = [("before", before), ("after", after)]
    else:
        sides = [("all", [s for _, s in rows])]
    for label, side in sides:
        print("\n".join(_fmt_db2(label, db2_acceptance(side))))
    return 0


def _fmt(name: str, s: dict) -> str:
    return (
        f"{name}: {s['runs']} runs, det_not_green {s['det_not_green']}, jobs/run median {s['jobs']['median']:g} "
        f"(p75 {s['jobs']['p75']:g}), det wall median {s['det_wall_s']['median'] / 60:.1f} min "
        f"(p75 {s['det_wall_s']['p75'] / 60:.1f}), worst queue wait median {s['max_queue_s']['median'] / 60:.1f} min"
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "db2":
        return db2_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cut", required=True, help="ISO time of the change (UTC)")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD, oldest run to read")
    ap.add_argument("--min-runs", type=int, default=10)
    ap.add_argument("--workflow", default="det-sweep.yml")
    ap.add_argument("--full-jobs", type=int, default=10, help="jobs per run that mark a full sweep")
    ap.add_argument("--pages", type=int, default=5, help="pages of 100 runs to read")
    args = ap.parse_args(argv)
    args.event = "pull_request"
    done = _runs(args)

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
