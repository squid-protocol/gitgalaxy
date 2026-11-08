#!/usr/bin/env python3
"""Runner-minutes per pull request over a time window, split docs-only vs engine-touching PRs (#6278 re-measure).

    python tests/tools/pr_runner_cost.py --since 2026-10-28T03:50Z --until 2026-10-29T03:50Z

Method of the CI notes entry "Re-measured after slices 1-6": every `pull_request` workflow run created in the window, runner-min =
each job's minutes rounded up (GitHub bills per started minute), summed over the latest attempt of each run, grouped by head
branch. A run "did no work" when every job was skipped (or it has none). A branch is `record-only` when every file is on the #7963 fast-lane allowlist (`change_classifier.docs_only`;
`--prs N...` measures chosen PRs, compare with #7944's 30-40 runner-min); `docs-only` when every file of its PR
is prose / a test-read doc / agent config by `change_classifier.area`, else `code`; a branch with no readable PR is `unknown`
and never counted as docs-only. Needs `gh`. `summarize` is pure (the tests feed it rows).
"""

from __future__ import annotations

import argparse
import fnmatch
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
    """`record-only` (the #7963 fast-lane allowlist), `mutation-lane` (mutation data only), `docs-only`, `code`, or `unknown` (no file list: never cheap)."""
    if not files:
        return "unknown"
    if change_classifier.docs_only(files):
        return "record-only"
    if on_lane(files, MUTATION_GLOBS):
        return "mutation-lane"  # det_mutation data only (#8031): its own bucket, not "code"
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
    for kind in ("record-only", "docs-only", "code", "unknown"):
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


LANE_PR = 7968  # the PR that made the fast lane; only PRs merged after it ran under it
MUTATION_LANE_PR = 8031  # #8031 put mutation-data-only PRs on the lane (E2E shards skipped, suite selected)
MUTATION_GLOBS = ("tests/equivalence/det_mutation/*.json", "tests/equivalence/det_mutation_survivors/*.json")


def pick_lane_prs(prs: list[dict], n: int) -> list[int]:
    """The first `n` PR numbers the lane serves, oldest first: record-only files above #LANE_PR, or mutation-data-only
    files (`MUTATION_GLOBS`) above #MUTATION_LANE_PR (a mutation-data PR before #8031 ran the full lane)."""
    chosen = []
    for p in prs:
        files = p.get("files") or []
        record = p["number"] > LANE_PR and kind_of(files) == "record-only"
        if record or (p["number"] > MUTATION_LANE_PR and on_lane(files, MUTATION_GLOBS)):
            chosen.append(p["number"])
    return sorted(chosen)[:n]


def pick_record_only(prs: list[dict], n: int, after: int = LANE_PR) -> list[int]:
    """The first `n` PR numbers above `after` whose files are all record-only, oldest first (rows: number, files)."""
    chosen = [p["number"] for p in prs if p["number"] > after and kind_of(p.get("files") or []) == "record-only"]
    return sorted(chosen)[:n]


def near_misses(prs: list[dict], after: int = LANE_PR) -> dict[int, list[str]]:
    """PRs above `after` that touch a record file but also carry others: number -> the files that kept the full lane."""
    out: dict[int, list[str]] = {}
    for p in prs:
        files = p.get("files") or []
        if p["number"] <= after or not files or kind_of(files) == "record-only":
            continue
        rest = [f for f in files if not change_classifier.docs_only([f])]
        if len(rest) < len(files):
            out[p["number"]] = rest
    return out


def next_record_only(n: int, lane: bool = False) -> list[int]:
    """Merged PRs after the lane that are record-only (needs `gh`); fewer than `n` means the sample is not there yet.
    With `lane`, also the mutation-data-only PRs after #8031 (`pick_lane_prs`)."""
    out = _gh(
        f"repos/{REPO}/pulls?state=closed&per_page=100&sort=updated&direction=desc",
        "-q",
        ".[]|select(.merged_at)|.number",
    )
    nums = [int(x) for x in out.split() if int(x) > LANE_PR]
    rows = []
    for num in nums:
        files = _gh("--paginate", f"repos/{REPO}/pulls/{num}/files?per_page=100", "-q", ".[].filename").split()
        rows.append({"number": num, "files": files})
    miss = near_misses(rows)
    listing = ", ".join(f"#{k} (+{len(v)} other)" for k, v in sorted(miss.items())) or "none"
    print(f"{len(rows)} PRs merged after #{LANE_PR}; near-misses (record file plus others): {listing}", file=sys.stderr)
    return pick_lane_prs(rows, n) if lane else pick_record_only(rows, n)


def fetch_prs(numbers: list[int]) -> tuple[list[dict], dict[str, str]]:
    """Runs of each PR's head branch (any window) and the branch -> kind map: the per-PR measure of #7963."""
    runs: list[dict] = []
    kinds: dict[str, str] = {}
    refs = change_classifier.load()
    for pr in numbers:
        branch = _gh(f"repos/{REPO}/pulls/{pr}", "-q", ".head.ref").strip()
        files = _gh("--paginate", f"repos/{REPO}/pulls/{pr}/files?per_page=100", "-q", ".[].filename").split()
        kinds[branch] = kind_of(files, refs)
        url = f"repos/{REPO}/actions/runs?event=pull_request&per_page=100&branch={branch}"
        for ln in _gh("--paginate", url, "-q", ".workflow_runs[]|{id,workflow:.name,branch:.head_branch}").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            jq = ".jobs[]|{conclusion,started_at,completed_at}"
            jobs = _gh("--paginate", f"repos/{REPO}/actions/runs/{r['id']}/jobs?filter=latest&per_page=100", "-q", jq)
            r["jobs"] = [json.loads(x) for x in jobs.splitlines() if x.strip()]
            runs.append(r)
    return runs, kinds


def on_lane(files: list[str], also: tuple[str, ...] = ()) -> bool:
    """True when every file is a shipped record path or matches one of the candidate `also` globs (empty list: false)."""
    return bool(files) and all(
        change_classifier.is_docs_record(f) or any(fnmatch.fnmatchcase(f, g) for g in also) for f in files
    )


def branch_minutes(runs: list[dict]) -> dict[str, int]:
    """Runner-min per head branch (the same rounding as `summarize`)."""
    out: dict[str, int] = defaultdict(int)
    for r in runs:
        out[r["branch"]] += sum(job_minutes(j) for j in r.get("jobs") or [])
    return dict(out)


def replay(rows: list[dict], also: tuple[str, ...], after: int = LANE_PR) -> dict:
    """Counterfactual lane over merged PRs above `after` (rows: number, files, runner_min): what the shipped allowlist
    moved, and what the candidate `also` globs would add. A PR with no runner_min counts as unpriced."""
    cands = [r for r in rows if r["number"] > after]
    shipped = [r for r in cands if on_lane(r.get("files") or [])]
    wider = [r for r in cands if on_lane(r.get("files") or [], also) and r not in shipped]

    def price(rs: list[dict]) -> dict:
        priced = [r["runner_min"] for r in rs if r.get("runner_min") is not None]
        return {"prs": [r["number"] for r in rs], "runner_min": sum(priced), "unpriced": len(rs) - len(priced)}

    return {"merged_after_lane": len(cands), "shipped_allowlist": price(shipped), "added_by_also": price(wider)}


def replay_rows(limit: int) -> list[dict]:
    """The last `limit` closed PRs above the lane PR that merged, each with files and head-branch runner-min (needs `gh`)."""
    q = ".[]|select(.merged_at)|[.number,.head.ref]|@tsv"
    out = _gh(f"repos/{REPO}/pulls?state=closed&per_page={limit}&sort=updated&direction=desc", "-q", q)
    rows = []
    for ln in out.splitlines():
        num, _, branch = ln.partition("\t")
        if not num.isdigit() or int(num) <= LANE_PR:
            continue
        files = _gh("--paginate", f"repos/{REPO}/pulls/{num}/files?per_page=100", "-q", ".[].filename").split()
        runs, _ = fetch_prs([int(num)])
        rows.append(
            {"number": int(num), "files": files, "runner_min": branch_minutes(runs).get(branch) if runs else None}
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="window start, e.g. 2026-10-28T03:50Z")
    ap.add_argument("--until", help="window end")
    ap.add_argument("--prs", type=int, nargs="+", help="measure these PRs' head-branch runs instead of a window")
    ap.add_argument(
        "--next-record-only", type=int, metavar="N", help=f"measure the first N record-only PRs after #{LANE_PR}"
    )
    ap.add_argument(
        "--lane",
        action="store_true",
        help=f"with --next-record-only: also count mutation-data-only PRs after #{MUTATION_LANE_PR}",
    )
    ap.add_argument("--replay", type=int, metavar="N", help="replay the lane over the last N closed PRs after the lane")
    ap.add_argument("--also", nargs="*", default=[], help="with --replay: extra candidate globs to price")
    args = ap.parse_args()
    if args.replay:
        try:
            print(json.dumps(replay(replay_rows(args.replay), tuple(args.also)), indent=1))
        except RuntimeError as e:
            print(f"fetch failed: {e}", file=sys.stderr)
            return 1
        return 0
    if not args.prs and not args.next_record_only and not (args.since and args.until):
        ap.error("give --since and --until, --prs, or --next-record-only")
    try:
        if args.next_record_only:
            args.prs = next_record_only(args.next_record_only, args.lane)
            print(
                f"{'lane' if args.lane else 'record-only'} PRs after #{LANE_PR}: {len(args.prs)} of {args.next_record_only} wanted: {args.prs}"
                " (a partial sample is measured as is)",
                file=sys.stderr,
            )
            if not args.prs:
                return 1
        runs, kinds = fetch_prs(args.prs) if args.prs else fetch(args.since, args.until)
    except RuntimeError as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1
    out = summarize(runs, kinds)
    if args.prs:
        out["baseline_7944_runner_min"] = "30-40 (~23 jobs)"
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
