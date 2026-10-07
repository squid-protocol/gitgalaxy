#!/usr/bin/env python3
"""One call for a pull request's merge readiness (#4270): state, checks, files touched -- and, with --merge, the merge.

    python tests/tools/pr_check.py N            # report; exit 0 when ready to merge, 1 otherwise
    python tests/tools/pr_check.py N --merge    # `gh pr ready` + `gh pr merge --squash`, ONLY when everything is green
    python tests/tools/pr_check.py N --json

Four REST calls through `gh api` (gh pr view / edit / issue view fail on this repo's Projects-classic GraphQL): the pull
request (mergeable state, draft, head SHA), the head SHA's check runs and its combined commit status (paginated at
100), and the files touched. No polling: run it again later.

Checks are grouped by outcome. Per check name the newest run decides, with ONE exception: a CANCELLED run is ignored
when a run of the same name on the same SHA succeeded (a superseded duplicate, e.g. the label events of a fresh PR),
and the report says so; a skipped run after a success does not hide it either. A skipped / neutral run is never a
failure. Anything queued or in progress is pending.

Files are listed with flags on the ones a reviewer must look at: ratchet, baseline, golden, evidence and ledger
paths, and tests/crucible_pins.toml (a pin bump belongs in its own PR).

--merge marks a draft ready and squash-merges only when: the PR is open, GitHub says it is mergeable (not dirty /
behind / blocked), no check failed and none is pending. Otherwise it exits 1 with the reasons and merges nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from collections.abc import Callable
from typing import Any

REPO_SLUG = "squid-protocol/gitgalaxy"
FLAGGED = re.compile(r"ratchet|baseline|golden|evidence|ledger", re.I)
PIN_FILE = "tests/crucible_pins.toml"
OK = {"success"}
NEUTRAL = {"skipped", "neutral"}
BAD = {"failure", "timed_out", "action_required", "startup_failure", "stale"}
NOT_MERGEABLE = {"dirty": "merge conflicts with the base branch", "behind": "behind the base branch",
                 "blocked": "blocked by a required review or check", "draft": None, "unknown": None}  # fmt: skip

Api = Callable[[str], Any]


def gh_api(path: str) -> Any:
    """`gh api PATH` as JSON."""
    res = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if res.returncode:
        raise SystemExit(f"gh api {path} failed: {res.stderr.strip()[:300]}")
    return json.loads(res.stdout or "null")


def paged(api: Api, path: str, key: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Every item of a per_page=100 listing (`key`: the list inside the response object)."""
    out: list[dict[str, Any]] = []
    for page in range(1, limit + 1):
        sep = "&" if "?" in path else "?"
        doc = api(f"{path}{sep}per_page=100&page={page}")
        items = doc.get(key, []) if key else doc
        out += items
        if len(items) < 100:
            break
    return out


def classify(runs: list[dict[str, Any]], statuses: list[dict[str, Any]]) -> dict[str, Any]:
    """{passed, failed, pending, neutral, ignored} -- names, one verdict per check name; `ignored` explains each
    cancelled run left out because a same-name run on the SHA succeeded."""
    by: dict[str, list[dict[str, Any]]] = {}
    for r in sorted(runs, key=lambda r: r.get("id", 0)):
        by.setdefault(r["name"], []).append(r)
    out: dict[str, list[str]] = {"passed": [], "failed": [], "pending": [], "neutral": [], "ignored": []}
    for name, rs in sorted(by.items()):
        succeeded = any(r.get("conclusion") == "success" for r in rs)
        cancelled = [r for r in rs if r.get("conclusion") == "cancelled"]
        skipped = [r for r in rs if r.get("conclusion") in NEUTRAL]
        if succeeded and cancelled:
            out["ignored"].append(f"{name}: {len(cancelled)} cancelled run(s) ignored -- a same-name run on this SHA "
                                  f"succeeded")  # fmt: skip
        # the newest run that says something: not a cancelled duplicate of a success, not a skipped event run
        live = [r for r in rs if not (succeeded and r.get("conclusion") == "cancelled")]
        deciding = [r for r in live if r.get("conclusion") not in NEUTRAL] or live
        if succeeded and skipped and deciding[-1].get("conclusion") == "success" and rs[-1] in skipped:
            out["ignored"].append(f"{name}: {len(skipped)} skipped run(s) after the successful one (event runs that "
                                  f"do not audit) ignored")  # fmt: skip
        newest = deciding[-1]
        if newest.get("status") != "completed":
            out["pending"].append(f"{name} ({newest.get('status')})")
        elif newest.get("conclusion") in OK:
            out["passed"].append(name)
        elif newest.get("conclusion") in NEUTRAL:
            out["neutral"].append(f"{name} ({newest['conclusion']})")
        else:
            out["failed"].append(f"{name} ({newest.get('conclusion')})")
    for st in statuses:  # the classic commit statuses (one per context, newest first)
        ctx, state = st["context"], st["state"]
        bucket = {"success": "passed", "pending": "pending"}.get(state, "failed")
        out[bucket].append(ctx if bucket == "passed" else f"{ctx} ({state})")
    return out


def flag(path: str) -> str | None:
    if path == PIN_FILE:
        return "crucible PIN (a pin bump is its own PR)"
    m = FLAGGED.search(path)
    return m.group(0).lower() if m else None


def check(n: int, api: Api = gh_api) -> dict[str, Any]:
    pr = api(f"repos/{REPO_SLUG}/pulls/{n}")
    sha = pr["head"]["sha"]
    runs = paged(api, f"repos/{REPO_SLUG}/commits/{sha}/check-runs", "check_runs")
    status = api(f"repos/{REPO_SLUG}/commits/{sha}/status")
    files = paged(api, f"repos/{REPO_SLUG}/pulls/{n}/files", limit=30)
    checks = classify(runs, status.get("statuses", []) if status else [])
    reasons = []
    if pr["state"] != "open" or pr.get("merged"):
        reasons.append("merged already" if pr.get("merged") else f"the PR is {pr['state']}")
    if pr.get("mergeable") is False:
        reasons.append(f"not mergeable ({pr.get('mergeable_state')}: "
                       f"{NOT_MERGEABLE.get(pr.get('mergeable_state') or '') or 'see the PR'})")  # fmt: skip
    elif pr.get("mergeable") is None and pr["state"] == "open":
        reasons.append("GitHub has not computed mergeability yet: run again in a minute")
    elif pr.get("mergeable_state") in ("dirty", "behind", "blocked"):
        reasons.append(f"mergeable_state {pr['mergeable_state']}: {NOT_MERGEABLE[pr['mergeable_state']]}")
    if checks["failed"]:
        reasons.append(f"{len(checks['failed'])} check(s) failed: {', '.join(checks['failed'])}")
    if checks["pending"]:
        reasons.append(f"{len(checks['pending'])} check(s) pending: {', '.join(checks['pending'])}")
    if not runs and not checks["passed"]:
        reasons.append("no checks have run on the head SHA")
    return {
        "number": n, "title": pr.get("title"), "state": "merged" if pr.get("merged") else pr["state"],
        "draft": bool(pr.get("draft")), "head_sha": sha, "node_id": pr.get("node_id"),
        "mergeable": pr.get("mergeable"), "mergeable_state": pr.get("mergeable_state"), "checks": checks,
        "files": [{"path": f["filename"], "status": f["status"], "additions": f.get("additions", 0),
                   "deletions": f.get("deletions", 0), "flag": flag(f["filename"])} for f in files],
        "ready": not reasons, "reasons": reasons,
    }  # fmt: skip


def report(res: dict[str, Any]) -> str:
    c = res["checks"]
    out = [f"PR #{res['number']}: {res['title']}",
           f"state {res['state']}, draft {str(res['draft']).lower()}, head {res['head_sha'][:12]}, mergeable "
           f"{res['mergeable']} ({res['mergeable_state']})",
           f"checks: {len(c['passed'])} passed, {len(c['failed'])} failed, {len(c['pending'])} pending, "
           f"{len(c['neutral'])} skipped/neutral"]  # fmt: skip
    for key in ("failed", "pending"):
        out += [f"  {key.upper()}: {x}" for x in c[key]]
    out += [f"  ignored: {x}" for x in c["ignored"]]
    flagged = [f for f in res["files"] if f["flag"]]
    out.append(f"files: {len(res['files'])} ({sum(f['additions'] for f in res['files'])}+ / "
               f"{sum(f['deletions'] for f in res['files'])}-), {len(flagged)} flagged")  # fmt: skip
    out += [f"  FLAG {f['flag']:<10} {f['path']}" for f in flagged]
    out.append("READY to merge" if res["ready"] else "NOT ready: " + "; ".join(res["reasons"]))
    return "\n".join(out)


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603


def merge(res: dict[str, Any], run: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None) -> list[str]:
    """Mark ready (when draft) and squash-merge, pinned to the checked head SHA. Returns the errors (empty: merged)."""
    run = run or _run
    n = str(res["number"])
    if res["draft"]:
        r = run(["gh", "pr", "ready", n, "-R", REPO_SLUG])
        if r.returncode:  # gh's GraphQL path can fail on this repo: the mutation directly
            q = "mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{isDraft}}}"
            r = run(["gh", "api", "graphql", "-f", f"query={q}", "-f", f"id={res['node_id']}"])
            if r.returncode:
                return [f"could not mark #{n} ready: {r.stderr.strip()[:300]}"]
    r = run(["gh", "pr", "merge", n, "-R", REPO_SLUG, "--squash", "--match-head-commit", res["head_sha"]])
    return [f"gh pr merge failed: {(r.stderr or r.stdout).strip()[:300]}"] if r.returncode else []


def sync_pins(run: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None) -> str:
    """The merged PR moved a crucible pin: `crucible_pins.py sync` the shared checkouts (it takes golden-lock itself).
    Returns the text to print; a failure is reported, never raised -- the merge already happened."""
    run = run or _run
    r = run([sys.executable, str(Path(__file__).resolve().parent / "crucible_pins.py"), "sync"])
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode:
        return (f"WARNING: {PIN_FILE} changed but `crucible_pins.py sync` failed (exit {r.returncode}); "
                f"the merge stands. Run it by hand.\n{out}")  # fmt: skip
    return f"{PIN_FILE} changed: synced the shared crucible checkouts\n{out}"


def main(argv: list[str] | None = None, api: Api = gh_api) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("number", type=int)
    ap.add_argument("--merge", action="store_true", help="mark ready + squash-merge, only when everything is green")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = check(args.number, api)
    print(json.dumps(res, indent=1) if args.json else report(res))
    if not args.merge:
        return 0 if res["ready"] else 1
    if not res["ready"]:
        print(f"not merging #{args.number}: " + "; ".join(res["reasons"]), file=sys.stderr)
        return 1
    errors = merge(res)
    for e in errors:
        print(e, file=sys.stderr)
    if not errors:
        print(f"merged #{args.number} (squash, head {res['head_sha'][:12]})")
        if any(f["path"] == PIN_FILE for f in res["files"]):
            print(sync_pins())
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
