#!/usr/bin/env python3
"""main-watch (#4825, #4859): one `ci-red-main` issue per workflow that fails on main; closed when it next succeeds.

Run by .github/workflows/main-watch.yml:

    python tests/tools/main_watch.py event [--dry-run]        # a watched run completed (env: WF, CONCLUSION, RUN_ID, ...)
    python tests/tools/main_watch.py reconcile [--dry-run]    # every open ci-red-main issue, from the run list

`event` reacts to one `workflow_run`. `reconcile` is the safety net for events GitHub never delivered: a run created
with the repo GITHUB_TOKEN (post-merge.yml's dispatch of the Full Suite Gate) raises no `workflow_run` (#4859). For each
open issue it looks at the latest completed, non-cancelled run of that workflow on main and comments or closes.

Rules, all in decide() (pure: a snapshot in, actions out):
  * failure, no open issue -> open one;  failure, open issue -> one "Failed again" comment per run (the run's URL in
    the issue's body or comments means it was already reported, so the event path and reconcile never double-post);
  * success with an open issue -> comment and close, but only for a run that finished after the issue was opened;
  * a failure with cancelled legs says so, and one with NO failed leg (only cancelled ones) says that it is not a
    verdict on the code.
Nothing here checks out or runs pull-request code: it reads run metadata through the GitHub API.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any

LABEL = "ci-red-main"
PREFIX = "main is red: "
EVENTS = ("push", "schedule", "workflow_dispatch")
FAILED_JOB = ("failure", "timed_out")


def title_of(wf: str) -> str:
    return f"{PREFIX}{wf}"


def legs_note(failed: list[str], cancelled: list[str]) -> str:
    """Words for a failure's legs ('' when no leg was cancelled or none are known)."""
    if not cancelled:
        return ""
    if not failed:
        return (
            f"\n\nNo job failed on its own: {len(cancelled)} were cancelled ({', '.join(cancelled[:8])}), "
            "so this is not a verdict on the code, unless a leg ran into its job time limit (a hang: compare the run "
            "times with the job's timeout-minutes). Otherwise rerun the cancelled legs."
        )
    return (
        f"\n\n{len(failed)} job(s) failed ({', '.join(failed[:8])}); {len(cancelled)} more were cancelled "
        f"({', '.join(cancelled[:8])}); those say nothing about the code unless one ran into its job time limit (a hang)."
    )


def decide(s: dict[str, Any]) -> list[dict[str, Any]]:
    """snapshot -> actions. s: wf, conclusion, event, sha, run_url, via ('event'|'reconcile'), failed, cancelled,
    issue (None | {number, text}), after_issue (the run finished after the issue was opened)."""
    wf, url, sha, ev = s["wf"], s["run_url"], s["sha"][:12], s["event"]
    issue = s.get("issue")
    if issue and url in issue["text"]:
        return []  # this run was already reported on the issue
    via = " (found by reconcile)" if s.get("via") == "reconcile" else ""
    if s["conclusion"] == "failure":
        note = legs_note(s.get("failed", []), s.get("cancelled", []))
        if issue:
            return [
                {
                    "op": "comment",
                    "number": issue["number"],
                    "body": f"Failed again ({ev}) at `{sha}`: {url}{via}{note}",
                }
            ]
        body = (
            f"**{wf}** failed on main ({ev}) at `{sha}`: {url}{note}\n\n"
            "Diagnose with the CI digest's local repro (`python tests/tools/ci_digest.py` works on a PR; for main, "
            f"open the run).\nThis issue closes itself when {wf} next succeeds on main (main-watch.yml, #4825)."
        )
        return [{"op": "create", "title": title_of(wf), "body": body}]
    if s["conclusion"] == "success" and issue and s.get("after_issue", True):
        return [{"op": "close", "number": issue["number"], "body": f"Green again ({ev}) at `{sha}`: {url}{via}"}]
    return []


def latest_verdicts(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """workflow name -> its newest completed non-cancelled main run (push/schedule/dispatch, success or failure)."""
    out: dict[str, dict[str, Any]] = {}
    for r in runs:
        if (
            r.get("head_branch") != "main"
            or r.get("event") not in EVENTS
            or r.get("conclusion") not in ("success", "failure")
        ):
            continue
        if r["name"] not in out or r["id"] > out[r["name"]]["id"]:
            out[r["name"]] = r
    return out


def _minutes(job: dict[str, Any]) -> int | None:
    try:
        start, end = (datetime.fromisoformat(job[k].replace("Z", "+00:00")) for k in ("started_at", "completed_at"))
    except (KeyError, TypeError, AttributeError, ValueError):
        return None
    return int((end - start).total_seconds() // 60)


def legs(jobs: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(failed, cancelled) job names. A cancelled leg carries its run time: a job that hit its `timeout-minutes` is
    reported as cancelled too, and "after 45 min" is what tells a hang from a superseded run (#4840)."""
    failed = [j["name"] for j in jobs if j.get("conclusion") in FAILED_JOB]
    cancelled = []
    for j in jobs:
        if j.get("conclusion") == "cancelled":
            m = _minutes(j)
            cancelled.append(j["name"] if m is None else f"{j['name']} after {m} min")
    return failed, cancelled


# --- GitHub I/O -----------------------------------------------------------------------------------------------------


def gh(*args: str) -> Any:
    res = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if res.returncode:
        raise SystemExit(f"gh {' '.join(args)[:120]} failed: {res.stderr.strip()[:300]}")
    return json.loads(res.stdout) if res.stdout.strip() else None


def paged(path: str, key: str | None = None, limit: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, limit + 1):
        doc = gh("api", f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        items = doc.get(key, []) if key else doc
        out += items
        if len(items) < 100:
            break
    return out


def apply(repo: str, acts: list[dict[str, Any]], dry: bool) -> None:
    for a in acts:
        print(json.dumps(a))
        if dry:
            continue
        if a["op"] == "create":
            subprocess.run(  # noqa: S603
                ["gh", "label", "create", LABEL, "--repo", repo, "--color", "B60205", "--description",
                 "A check failing on main (opened/closed by main-watch.yml, #4825)"],  # noqa: S607
                capture_output=True, check=False,
            )  # fmt: skip
            gh(
                "api",
                f"repos/{repo}/issues",
                "-f",
                f"title={a['title']}",
                "-f",
                f"body={a['body']}",
                "-f",
                f"labels[]={LABEL}",
            )
        else:
            gh("api", f"repos/{repo}/issues/{a['number']}/comments", "-f", f"body={a['body']}")
            if a["op"] == "close":
                gh(
                    "api",
                    "-X",
                    "PATCH",
                    f"repos/{repo}/issues/{a['number']}",
                    "-f",
                    "state=closed",
                    "-f",
                    "state_reason=completed",
                )


def open_issues(repo: str) -> dict[str, dict[str, Any]]:
    """title -> issue (the oldest), for open ci-red-main issues."""
    out: dict[str, dict[str, Any]] = {}
    for i in paged(f"repos/{repo}/issues?labels={LABEL}&state=open"):
        if "pull_request" not in i:
            out.setdefault(i["title"], i)
    return out


def issue_text(repo: str, issue: dict[str, Any]) -> dict[str, Any]:
    comments = paged(f"repos/{repo}/issues/{issue['number']}/comments")
    text = (issue.get("body") or "") + "\n" + "\n".join(c.get("body") or "" for c in comments)
    return {"number": issue["number"], "text": text}


def run_legs(repo: str, run_id: int) -> tuple[list[str], list[str]]:
    return legs(paged(f"repos/{repo}/actions/runs/{run_id}/jobs?filter=latest", "jobs", limit=2))


def cmd_event(repo: str, dry: bool) -> None:
    env = os.environ
    issues = open_issues(repo)
    wf = env["WF"]
    snap: dict[str, Any] = {
        "wf": wf, "conclusion": env["CONCLUSION"], "event": env["EVENT"], "sha": env["SHA"], "run_url": env["RUN_URL"],
        "via": "event", "failed": [], "cancelled": [], "after_issue": True, "issue": None,
    }  # fmt: skip
    if env["CONCLUSION"] == "failure" and env.get("RUN_ID"):
        snap["failed"], snap["cancelled"] = run_legs(repo, int(env["RUN_ID"]))
    if title_of(wf) in issues:
        snap["issue"] = issue_text(repo, issues[title_of(wf)])
    apply(repo, decide(snap), dry)


def cmd_reconcile(repo: str, dry: bool) -> None:
    issues = {t: i for t, i in open_issues(repo).items() if t.startswith(PREFIX)}
    if not issues:
        print("no open ci-red-main issue")
        return
    runs = paged(f"repos/{repo}/actions/runs?branch=main&status=completed&exclude_pull_requests=true", "workflow_runs")
    verdicts = latest_verdicts(runs)
    for title, issue in issues.items():
        run = verdicts.get(title[len(PREFIX) :])
        if not run:
            print(f"{title}: no completed non-cancelled main run in the last {len(runs)} runs")
            continue
        snap: dict[str, Any] = {
            "wf": run["name"], "conclusion": run["conclusion"], "event": run["event"], "sha": run["head_sha"],
            "run_url": run["html_url"], "via": "reconcile", "failed": [], "cancelled": [],
            "after_issue": run["updated_at"] > issue["created_at"], "issue": issue_text(repo, issue),
        }  # fmt: skip
        if run["conclusion"] == "failure":
            snap["failed"], snap["cancelled"] = run_legs(repo, run["id"])
        apply(repo, decide(snap), dry)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("event", "reconcile"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repo", default=os.environ.get("REPO", "squid-protocol/gitgalaxy"))
    a = ap.parse_args()
    (cmd_event if a.cmd == "event" else cmd_reconcile)(a.repo, a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
