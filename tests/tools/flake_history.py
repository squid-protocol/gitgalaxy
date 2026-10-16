#!/usr/bin/env python3
"""Learned flakes: CI jobs that failed, then passed when the same workflow run was rerun (same head SHA).

    python tests/tools/flake_history.py                  # the last 14 days, ranked
    python tests/tools/flake_history.py --json           # the same, machine-readable
    python tests/tools/flake_history.py --refresh-only   # update the cache, print nothing (ci_shepherd runs this)
    python tests/tools/flake_history.py --file-issues    # open one cleanup issue per learned-flaky job (once)

A job is *learned flaky* when, in the window, it passed on a rerun at least MIN_RESCUES times and at least MIN_RATE
of its reruns passed (80%: on 2026-10-16 a 50% bar also caught `det` 13/7 and `full-suite` 7/6, broad required jobs whose
reruns pass because the timing flake sits in one of thousands of tests, not because the job is flaky). ci_shepherd hands that set to ci_digest, which triages a FIRST-attempt failure of such a check
as `flake` (one rerun) instead of `real`; if it fails again on the rerun it is `real` (digest, fixer) as before.

GitHub keeps the evidence: a rerun run has run_attempt > 1, and `jobs?filter=all` lists every attempt's jobs. Cost:
the run listing in 2-hour windows (a listing stops at 1,000 runs) plus one jobs call per rerun run. Finished days are
cached and only today and yesterday are refetched, so a refresh is about a hundred calls on a 3,000-run day.

In GitGalaxy, ci_rerun_stats.py (#5137, beside this file) classifies WHY each first attempt failed (timeout,
registry_pull, db2_start, ratchet, test_failure, ...). When it is importable, every job here carries those causes:
ci_rerun_stats is the per-workflow diagnostic, this is the repo-wide learned list. Without it causes are left out.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from squid_bot import pr_check
except ImportError:
    import pr_check  # noqa: E402

try:
    import ci_rerun_stats  # GitGalaxy's first-attempt cause classifier (#5137)
except ImportError:
    ci_rerun_stats = None

REPO_SLUG = pr_check.REPO_SLUG
DAYS = 14
REFRESH_DAYS = 2  # today and yesterday can still change
WINDOW_H = 2
MIN_RESCUES = 2
MIN_RATE = 0.8
ISSUE_TITLE = "Flaky CI job: {name}"


def cause(job: dict[str, Any]) -> str | None:
    """Why this failed attempt failed, by ci_rerun_stats' classifier (None where it is not available)."""
    return ci_rerun_stats.classify([job]) if ci_rerun_stats else None


def rerun_verdicts(jobs: list[dict[str, Any]]) -> dict[str, tuple[bool, str | None]]:
    """{job name: (passed on its latest attempt, why its first failed attempt failed)} for the jobs of one run that
    FAILED on an earlier attempt. A job whose latest attempt was cancelled or skipped says nothing and is left out."""
    by: dict[str, list[dict[str, Any]]] = {}
    for j in jobs:
        by.setdefault(j["name"], []).append(j)
    out: dict[str, bool] = {}
    for name, js in by.items():
        js.sort(key=lambda j: j.get("run_attempt") or 1)
        last = js[-1]
        failed = [j for j in js[:-1] if j.get("conclusion") == "failure"]
        if failed and last.get("conclusion") in ("success", "failure"):
            out[name] = (last["conclusion"] == "success", cause(failed[0]))
    return out


def day_reruns(api: pr_check.Api, day: str) -> dict[str, list[Any]]:
    """{job name: [passed on a rerun, failed again, {first-attempt cause: count}]} for the runs created on `day` (UTC)
    that were rerun."""
    out: dict[str, list[Any]] = {}
    for h in range(0, 24, WINDOW_H):
        span = f"{day}T{h:02d}:00:00Z..{day}T{h + WINDOW_H - 1:02d}:59:59Z"
        for r in pr_check.paged(api, f"repos/{REPO_SLUG}/actions/runs?created={span}", "workflow_runs"):
            if (r.get("run_attempt") or 1) < 2 or r.get("status") != "completed":
                continue
            jobs = pr_check.paged(api, f"repos/{REPO_SLUG}/actions/runs/{r['id']}/jobs?filter=all", "jobs")
            for name, (passed, why) in rerun_verdicts(jobs).items():
                row = out.setdefault(name, [0, 0, {}])
                row[0 if passed else 1] += 1
                if why:
                    row[2][why] = row[2].get(why, 0) + 1
    return out


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def refresh(api: pr_check.Api, path: Path, today: date | None = None, days: int = DAYS) -> dict[str, Any]:
    """Fetch the days missing from the cache at `path` (and the recent ones again), drop the rest, save it."""
    today = today or datetime.now(timezone.utc).date()
    cache = load(path)
    if cache.get("repo") != REPO_SLUG:
        cache = {"repo": REPO_SLUG, "days": {}}
    window = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    for i, d in enumerate(window):
        if d not in cache["days"] or i < REFRESH_DAYS:
            cache["days"][d] = day_reruns(api, d)
    cache["days"] = {d: v for d, v in cache["days"].items() if d in window}
    cache["updated"] = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return cache


def tally(cache: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per job over the cached window, the most rescued first."""
    sums: dict[str, list[Any]] = {}
    for per_job in (cache.get("days") or {}).values():
        for name, row in per_job.items():
            s = sums.setdefault(name, [0, 0, {}])
            s[0] += row[0]
            s[1] += row[1]
            for why, k in (row[2] if len(row) > 2 else {}).items():
                s[2][why] = s[2].get(why, 0) + k
    rows = []
    for name, (passed, failed, causes) in sums.items():
        rate = passed / (passed + failed)
        rows.append({"job": name, "passed_on_rerun": passed, "failed_again": failed, "rerun_pass_rate": round(rate, 2),
                     "learned_flaky": passed >= MIN_RESCUES and rate >= MIN_RATE,
                     "causes": dict(sorted(causes.items(), key=lambda kv: -kv[1]))})  # fmt: skip
    return sorted(rows, key=lambda r: (-r["passed_on_rerun"], -r["failed_again"], r["job"]))


def learned(cache: dict[str, Any]) -> set[str]:
    return {r["job"] for r in tally(cache) if r["learned_flaky"]}


def file_issues(rows: list[dict[str, Any]], run: Any = subprocess.run) -> list[str]:
    """One open issue per learned-flaky job; a job that already has an open issue (same title) gets none."""
    out = []
    for r in rows:
        if not r["learned_flaky"]:
            continue
        title = ISSUE_TITLE.format(name=r["job"])
        found = run(["gh", "issue", "list", "-R", REPO_SLUG, "--state", "open", "--search", f'"{title}" in:title',
                     "--json", "title", "--jq", ".[].title"], capture_output=True, text=True, check=False)  # fmt: skip
        if title in found.stdout.splitlines():
            continue
        why = ", ".join(f"{k} {v}" for k, v in (r.get("causes") or {}).items())
        body = (f"`{r['job']}` failed and then passed on a rerun of the same run {r['passed_on_rerun']} time(s) in the "
                f"last {DAYS} days (failed again: {r['failed_again']})"
                + (f"; first-attempt causes (ci_rerun_stats): {why}" if why else "")
                + ". The CI shepherd now reruns its first failure once instead of calling it real. Find the "
                "nondeterminism (timing under load, ordering, network, registry) and close this when the job stops "
                "needing reruns.")  # fmt: skip
        res = run(["gh", "issue", "create", "-R", REPO_SLUG, "--title", title, "--body", body],
                  capture_output=True, text=True, check=False)  # fmt: skip
        out.append(f"{title}: {res.stdout.strip() or res.stderr.strip()[:200]}")
    return out


def default_cache() -> Path:
    try:
        from squid_bot.config import get_state_path

        return get_state_path().parent / "flake_history.json"
    except Exception:  # noqa: BLE001 (GitGalaxy has no squid_bot.config)
        return Path("/tmp/squid-bot/state/flake_history.json")  # noqa: S108


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache", type=Path, default=default_cache())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--refresh-only", action="store_true")
    ap.add_argument("--no-refresh", action="store_true", help="report from the cache without calling GitHub")
    ap.add_argument("--file-issues", action="store_true", help="open one issue per learned-flaky job (writes to GitHub)")
    a = ap.parse_args(argv)
    cache = load(a.cache) if a.no_refresh else refresh(pr_check.gh_api, a.cache)
    if a.refresh_only:
        return 0
    rows = tally(cache)
    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        print(f"Reruns of the last {len(cache.get('days') or {})} days (learned flaky: >= {MIN_RESCUES} passes, "
              f">= {MIN_RATE:.0%} of reruns passed)")  # fmt: skip
        for r in rows:
            mark = "FLAKY " if r["learned_flaky"] else "      "
            why = ", ".join(f"{k} {v}" for k, v in r["causes"].items())
            print(f"  {mark}{r['job']}: passed on rerun {r['passed_on_rerun']}, failed again {r['failed_again']}"
                  + (f" ({why})" if why else ""))
        if not rows:
            print("  no reruns")
    if a.file_issues:
        for line in file_issues(rows):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
