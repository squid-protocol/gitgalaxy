#!/usr/bin/env python3
"""How evenly the three `full-suite part k/3` jobs of smoke-test.yml split the suite (#5133).

    python tests/tools/ci_part_balance.py RUN_ID [RUN_ID ...]
    python tests/tools/ci_part_balance.py --latest 8 [--event push]

Per run: each part's minutes (job start to end), max/min, and whether it is within the 1.2 target (the issue's "about
20%"). A run with a part missing, unfinished or not successful is listed as skipped, not averaged. Run this on main push
runs after the first completed nightly (its `test-durations-<run id>` cache is what they restore) and compare with the 8
runs recorded in docs/ci.md. Needs the `gh` CLI. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime

TARGET = 1.2
REPO = "squid-protocol/gitgalaxy"
_PART = re.compile(r"^full-suite part (\d+)/(\d+)$")


def _seconds(job: dict) -> float | None:
    start, end = job.get("started_at"), job.get("completed_at")
    if not start or not end:
        return None
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def part_seconds(jobs: list[dict]) -> dict[int, float] | None:
    """{part: seconds} when every part of the split finished successfully, else None."""
    found: dict[int, float] = {}
    count = 0
    for job in jobs:
        m = _PART.match(str(job.get("name", "")))
        if not m:
            continue
        count = int(m.group(2))
        secs = _seconds(job)
        if job.get("conclusion") != "success" or secs is None:
            return None
        found[int(m.group(1))] = secs
    return found if count and len(found) == count else None


def within_target(parts: dict[int, float]) -> bool:
    """Written as a product, not a ratio, so the exact boundary is not misjudged in floats."""
    return max(parts.values()) <= min(parts.values()) * TARGET


def summarize(runs: dict[str, list[dict]]) -> tuple[list[str], list[str]]:
    """(table lines, skipped run ids) for {run id: jobs}."""
    lines = ["run          parts (min)        max/min  within 1.2"]
    ratios: list[float] = []
    slowest: list[float] = []
    skipped: list[str] = []
    for run, jobs in runs.items():
        parts = part_seconds(jobs)
        if parts is None:
            skipped.append(run)
            continue
        ratio = max(parts.values()) / min(parts.values())
        ratios.append(ratio)
        slowest.append(max(parts.values()) / 60)
        cells = " / ".join(f"{parts[k] / 60:.1f}" for k in sorted(parts))
        lines.append(f"{run:<12} {cells:<18} {ratio:7.2f}  {'yes' if within_target(parts) else 'no'}")
    if ratios:
        ok = sum(1 for r in ratios if r <= TARGET)
        lines.append(
            f"{len(ratios)} runs: max/min {min(ratios):.2f}-{max(ratios):.2f}, median {statistics.median(ratios):.2f}; "
            f"{ok} within {TARGET}; slowest part mean {statistics.mean(slowest):.1f} min"
        )
    else:
        lines.append("no run had all parts finished successfully")
    return lines, skipped


def _gh(path: str) -> dict:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True).stdout  # noqa: S603, S607
    return json.loads(out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", nargs="*", help="smoke-test.yml run ids")
    ap.add_argument("--latest", type=int, help="the newest N completed runs instead of listed ids")
    ap.add_argument("--event", default="push")
    args = ap.parse_args(argv)
    ids = list(args.runs)
    if args.latest:
        listing = _gh(
            f"repos/{REPO}/actions/workflows/smoke-test.yml/runs?event={args.event}&status=completed&per_page=100"
        )
        ids += [str(r["id"]) for r in listing["workflow_runs"] if r["conclusion"] == "success"][: args.latest]
    if not ids:
        ap.error("give run ids or --latest N")
    runs = {i: _gh(f"repos/{REPO}/actions/runs/{i}/jobs?per_page=100")["jobs"] for i in ids}
    lines, skipped = summarize(runs)
    print("\n".join(lines))
    if skipped:
        print("skipped (a part missing, unfinished or not successful): " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
