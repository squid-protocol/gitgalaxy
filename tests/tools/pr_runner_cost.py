#!/usr/bin/env python3
"""Runner-minutes per pull request over a time window, split docs-only vs engine-touching PRs (#6278 re-measure).

    python tests/tools/pr_runner_cost.py --since 2026-10-28T03:50Z --until 2026-10-29T03:50Z

Method of the CI notes entry "Re-measured after slices 1-6": every `pull_request` workflow run created in the window, runner-min =
each job's minutes rounded up (GitHub bills per started minute), summed over the latest attempt of each run, grouped by head
branch. A run "did no work" when every job was skipped (or it has none). A branch is `docs-only` when every file of its PR
is prose / a test-read doc / agent config by `change_classifier.area`, else `code`; a branch with no readable PR is `unknown`
and never counted as docs-only. Needs `gh`. `summarize` is pure (the tests feed it rows).
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402

REPO = "squid-protocol/gitgalaxy"
DOCS_AREAS = ("prose", "test-read-doc", "agent-config")


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def job_minutes(job: dict) -> int:
    """Billed minutes of one job: started to completed, rounded up; a skipped or unfinished job costs 0."""
    if job.get("conclusion") in (None, "skipped") or not job.get("started_at") or not job.get("completed_at"):
        return 0
    secs = (_ts(job["completed_at"]) - _ts(job["started_at"])).total_seconds()
    return max(1, math.ceil(secs / 60)) if secs > 0 else 0


def kind_of(files: list[str] | None, refs: dict | None = None) -> str:
    """`docs-only`, `code`, or `unknown` (no file list: never assumed cheap)."""
    if not files:
        return "unknown"
    refs = change_classifier.load() if refs is None else refs
    return "docs-only" if all(change_classifier.area(f, refs) in DOCS_AREAS for f in files) else "code"


def summarize(runs: list[dict], kinds: dict[str, str]) -> dict:
    """`runs`: {branch, workflow, jobs: [job dicts]}. `kinds`: branch -> kind_of(). Totals overall and per kind."""
    per_branch: dict[str, int] = defaultdict(int)
    workflows: dict[str, int] = defaultdict(int)
    idle = 0
    for r in runs:
        mins = sum(job_minutes(j) for j in r.get("jobs") or [])
        per_branch[r["branch"]] += mins
        workflows[r["workflow"]] += mins
        idle += mins == 0
    out: dict = {
        "runs": len(runs),
        "idle_runs": idle,
        "branches": len(per_branch),
        "runner_min": sum(per_branch.values()),
    }
    out["per_branch"] = round(out["runner_min"] / len(per_branch), 1) if per_branch else 0.0
    by_kind: dict[str, dict] = {}
    for kind in ("docs-only", "code", "unknown"):
        mins = [m for b, m in per_branch.items() if kinds.get(b, "unknown") == kind]
        if mins:
            by_kind[kind] = {
                "branches": len(mins),
                "runner_min": sum(mins),
                "per_branch": round(sum(mins) / len(mins), 1),
            }
    out["by_kind"] = by_kind
    out["top_workflows"] = sorted(workflows.items(), key=lambda kv: -kv[1])[:10]
    return out


def _gh(*args: str) -> str:
    proc = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh api failed")
    return proc.stdout


def _pr_of_branch(branch: str) -> int:
    out = _gh(f"repos/{REPO}/pulls?state=all&per_page=1&head={REPO.split('/')[0]}:{branch}", "-q", ".[0].number // 0")
    return int(out.strip() or 0)


def fetch(since: str, until: str) -> tuple[list[dict], dict[str, str]]:
    q = ".workflow_runs[]|{id,workflow:.name,branch:.head_branch,pr:(.pull_requests[0].number // 0)}"
    url = f"repos/{REPO}/actions/runs?event=pull_request&per_page=100&created={since}..{until}"
    runs = [json.loads(ln) for ln in _gh("--paginate", url, "-q", q).splitlines() if ln.strip()]
    for r in runs:
        jq = ".jobs[]|{conclusion,started_at,completed_at}"
        jobs = _gh("--paginate", f"repos/{REPO}/actions/runs/{r['id']}/jobs?filter=latest&per_page=100", "-q", jq)
        r["jobs"] = [json.loads(ln) for ln in jobs.splitlines() if ln.strip()]
    refs = change_classifier.load()
    kinds: dict[str, str] = {}
    for r in runs:
        if r["branch"] in kinds:
            continue
        pr = r["pr"] or _pr_of_branch(r["branch"])  # a run's pull_requests list is often empty
        files = (
            _gh("--paginate", f"repos/{REPO}/pulls/{pr}/files?per_page=100", "-q", ".[].filename").split() if pr else []
        )
        kinds[r["branch"]] = kind_of(files, refs)
    return runs, kinds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", required=True, help="window start, e.g. 2026-10-28T03:50Z")
    ap.add_argument("--until", required=True, help="window end")
    args = ap.parse_args()
    try:
        runs, kinds = fetch(args.since, args.until)
    except RuntimeError as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summarize(runs, kinds), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
