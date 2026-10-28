#!/usr/bin/env python3
"""One call for a pull request's merge readiness (#4270): state, checks, files touched -- and, with --merge, the merge.

    python tests/tools/pr_check.py N            # report; exit 0 when ready to merge, 1 otherwise
    python tests/tools/pr_check.py N --merge    # `gh pr ready` + `gh pr merge --squash`, ONLY when everything is green
    python tests/tools/pr_check.py N --json
    python tests/tools/pr_check.py N --digest   # also: per failed check, its triage, error lines and local repro (ci_digest.py)

One GraphQL query (REST fallback, #6534), else four REST calls through `gh api` (gh pr view / edit / issue view fail on this repo's Projects-classic GraphQL): the pull
request (mergeable state, draft, head SHA), the head SHA's check runs and its combined commit status (paginated at
100), and the files touched. No polling: run it again later.

Checks are grouped by outcome. Per check name the newest run decides, with ONE exception: a CANCELLED run is ignored
when a run of the same name on the same SHA succeeded (a superseded duplicate, e.g. the label events of a fresh PR),
and the report says so; a skipped run after a success does not hide it either. A skipped / neutral run is never a
failure. Anything queued or in progress is pending.

Files are listed with flags on the ones a reviewer must look at: ratchet, baseline, golden, evidence and ledger
paths, and tests/crucible_pins.toml (a pin bump belongs in its own PR).

--merge squash-merges only when: the PR is open, GitHub says it is mergeable (not dirty /
behind / blocked), no check failed and none is pending. Otherwise it exits 1 with the reasons and merges nothing.
A draft is only marked ready, never merged in the same call (#5104): a draft head's heavy workflows are skipped, and a
skipped check reads as green, so its CI starts on `ready_for_review` and a second `--merge` merges once that is green.
"""

from __future__ import annotations

import argparse
import hashlib
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


GraphQL = Callable[[str, dict[str, Any]], Any]


def gh_graphql(query: str, variables: dict[str, Any]) -> Any:
    """`gh api graphql` as the response's `data` (#6534: GraphQL has its own 5,000-points/h quota, apart from REST's).
    Ints go as -F (typed), everything else as -f (a string). A failed call or any `errors` raises SystemExit."""
    argv = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        argv += ["-F" if isinstance(v, int) else "-f", f"{k}={v}"]
    res = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603
    doc = json.loads(res.stdout or "null") if res.stdout.strip().startswith("{") else None
    if res.returncode or not doc or doc.get("errors") or not doc.get("data"):
        raise SystemExit(f"gh api graphql failed: {(res.stderr or res.stdout).strip()[:300]}")
    return doc["data"]


class Truncated(ValueError):
    """A GraphQL list came back shorter than its totalCount."""


def whole(conn: dict[str, Any], count: str = "totalCount") -> list[dict[str, Any]]:
    """A GraphQL connection's nodes, or Truncated when GitHub holds more than came back."""
    nodes = conn["nodes"]
    if conn[count] > len(nodes):
        raise Truncated
    return nodes


# the check suites of a commit with their runs, as one GraphQL selection (shared by the PR and main reads, #6534)
SUITES_SELECTION = """checkSuites(first: 100) { totalCount nodes { createdAt app { slug }
          checkRuns(first: 100) { totalCount nodes { databaseId name status conclusion detailsUrl url } } } }"""


def runs_from_suites(suites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """REST's check-run dicts from a SUITES_SELECTION's suites (Truncated when a suite's runs are cut short)."""
    runs = []
    for suite in suites:
        slug = (suite.get("app") or {}).get("slug")
        for r in whole(suite["checkRuns"]):
            runs.append({
                "id": r["databaseId"], "name": r["name"], "status": r["status"].lower(),
                "conclusion": r["conclusion"].lower() if r["conclusion"] else None, "app": {"slug": slug},
                "details_url": r["detailsUrl"], "html_url": r["detailsUrl"] if slug == "github-actions" else r["url"],
            })  # fmt: skip
    return runs


# the per-PR reads of the shepherd's gather() as one selection (#6534): every list is fetched whole or not used
PR_FIELDS = """
      number state merged isDraft body mergeStateStatus headRefOid headRefName baseRefName
      headRepository { nameWithOwner }
      autoMergeRequest { enabledAt }
      labels(first: 100) { totalCount nodes { name } }
      comments(last: 100) { totalCount nodes { author { __typename login } body } }
      timelineItems(itemTypes: [LABELED_EVENT], last: 100) {
        filteredCount nodes { ... on LabeledEvent { actor { __typename login } createdAt label { name } } }
      }
      commits(last: 1) { nodes { commit { oid
        status { contexts { context state description } }
        @@SUITES@@
      } } }
"""
PR_FIELDS = PR_FIELDS.replace("@@SUITES@@", SUITES_SELECTION)
# what check() reads: the pull, its head's runs and statuses, and the files touched (first 100; more goes to REST)
CHECK_FIELDS = """
      id number title state merged isDraft mergeable mergeStateStatus headRefOid
      files(first: 100) { totalCount nodes { path additions deletions changeType } }
      commits(last: 1) { nodes { commit { oid
        status { contexts { context state description } }
        @@SUITES@@
      } } }
""".replace("@@SUITES@@", SUITES_SELECTION)
CHECK_QUERY = (
    "query($owner: String!, $name: String!, $n: Int!) {\n  rateLimit { cost }\n  repository(owner: $owner, name: $name) {\n"
    "    pullRequest(number: $n) {" + CHECK_FIELDS + "    }\n  }\n}"
)
MERGEABLE = {"MERGEABLE": True, "CONFLICTING": False}
CHANGE_STATUS = {"ADDED": "added", "MODIFIED": "modified", "REMOVED": "removed", "RENAMED": "renamed",
                 "COPIED": "copied", "CHANGED": "changed"}  # fmt: skip


def graphql_check_reads(p: dict[str, Any]) -> dict[str, Any]:
    """check()'s REST shapes (pull, runs, statuses, files) from one CHECK_QUERY pullRequest. KeyError / TypeError /
    Truncated when anything is missing or cut short; Truncated too when mergeability is still UNKNOWN (the REST read
    asks GitHub to compute it, GraphQL does not: a dirty PR must not pass for clean)."""
    commit = p["commits"]["nodes"][0]["commit"]
    if commit["oid"] != p["headRefOid"] or p["mergeable"] == "UNKNOWN" or p["mergeStateStatus"] == "UNKNOWN":
        raise Truncated
    pr = {
        "number": p["number"], "title": p["title"], "state": "open" if p["state"] == "OPEN" else "closed",
        "merged": bool(p["merged"]), "draft": bool(p["isDraft"]), "mergeable": MERGEABLE[p["mergeable"]],
        "mergeable_state": p["mergeStateStatus"].lower(), "node_id": p["id"], "head": {"sha": p["headRefOid"]},
    }  # fmt: skip
    return {
        "pr": pr,
        "runs": runs_from_suites(whole(commit["checkSuites"])),
        "statuses": [{"context": c["context"], "state": c["state"].lower()}
                     for c in ((commit.get("status") or {}).get("contexts") or [])],
        "files": [{"filename": f["path"], "status": CHANGE_STATUS[f["changeType"]], "additions": f["additions"],
                   "deletions": f["deletions"]} for f in whole(p["files"])],
    }  # fmt: skip


def _graphql_check(graphql: GraphQL, n: int) -> dict[str, Any] | None:
    """graphql_check_reads for PR n, or None (the REST path) when the query fails or anything is incomplete."""
    owner, name = REPO_SLUG.split("/")
    try:
        data = graphql(CHECK_QUERY, {"owner": owner, "name": name, "n": n})
        return graphql_check_reads(data["repository"]["pullRequest"])
    except (SystemExit, KeyError, TypeError, IndexError, AttributeError, ValueError):
        return None


SHA_PATH = re.compile(r"^repos/[^/]+/[^/]+/commits/[0-9a-f]{40}$")  # a commit by sha: its parents never change
RUNS_PATH = re.compile(r"^repos/[^/]+/[^/]+/commits/[0-9a-f]{40}/check-runs\?")
RUN_PATH = re.compile(r"^repos/[^/]+/[^/]+/actions/runs/\d+$")


def pass_cache(api: Api) -> Api:
    """`api` with the reads one pass may share (#6534): a commit by sha, a sha's check runs once every one is completed,
    a workflow run once completed. For ONE pass only: a completed run can still be re-run, so only a commit's parents
    would be safe to keep longer."""
    memo: dict[str, Any] = {}

    def done(path: str, doc: Any) -> bool:
        if SHA_PATH.match(path):
            return True
        if RUNS_PATH.match(path):
            return all(r.get("status") == "completed" for r in (doc or {}).get("check_runs", []))
        return bool(RUN_PATH.match(path)) and (doc or {}).get("status") == "completed"

    def cached(path: str) -> Any:
        if path in memo:
            return memo[path]
        doc = api(path)
        if done(path, doc):
            memo[path] = doc
        return doc

    return cached


HEAD = re.compile(r"\A(HTTP/\S+ (\d{3})[^\n]*\n.*?)\r?\n\r?\n", re.S)


def conditional_api(store: Path, run: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None) -> Api:
    """gh_api with conditional requests (#6534): each GET sends the ETag it got last time as If-None-Match, and a 304
    (which does not count against the REST quota) returns the body kept under `store`. A read with no ETag yet, or
    a store that cannot be written, is a plain read."""
    run = run or (lambda argv: subprocess.run(argv, capture_output=True, text=True, check=False))  # noqa: S603

    def api(path: str) -> Any:
        file = store / (hashlib.sha256(path.encode()).hexdigest()[:32] + ".json")
        try:
            kept = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            kept = None
        argv = ["gh", "api", "-i", path]
        if kept and kept.get("etag"):
            argv[3:3] = ["-H", f"If-None-Match: {kept['etag']}"]
        res = run(argv)
        m = HEAD.match(res.stdout or "")
        if kept and m and m[2] == "304":
            return kept["body"]
        if res.returncode or not m:
            raise SystemExit(f"gh api {path} failed: {res.stderr.strip()[:300]}")
        body = json.loads(res.stdout[m.end() :] or "null")
        etag = re.search(r"^etag:\s*(.+?)\s*$", m[1], re.I | re.M)
        if etag:
            try:
                store.mkdir(parents=True, exist_ok=True)
                tmp = file.with_suffix(".tmp")  # atomic: a cache saved mid-write never holds a torn entry
                tmp.write_text(json.dumps({"etag": etag[1], "body": body}), encoding="utf-8")
                tmp.replace(file)
            except OSError:
                pass  # no store: the next read is plain
        return body

    return api


def prune_api_store(
    store: Path, max_age_s: float = 7 * 86400, max_entries: int = 2000, now: float | None = None
) -> int:
    """Keep a conditional-read store that persists across passes small (#6534): drop entries older than `max_age_s`
    (a 304 rewrites nothing, so an entry's mtime is the last time its body changed), leftover temp files, then the
    oldest beyond `max_entries`. Returns how many were removed; a missing or unreadable store removes none."""
    import time

    now = time.time() if now is None else now
    try:
        files = [(f.stat().st_mtime, f) for f in store.iterdir() if f.suffix in (".json", ".tmp")]
    except OSError:
        return 0
    files.sort(key=lambda t: t[0], reverse=True)
    entries = [(m, f) for m, f in files if f.suffix == ".json"]
    drop = [f for m, f in files if f.suffix == ".tmp"] + [
        f for i, (m, f) in enumerate(entries) if now - m > max_age_s or i >= max_entries
    ]
    removed = 0
    for f in drop:
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed


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


def failed_names(runs: list[dict[str, Any]]) -> set[str]:
    """The check names classify() calls failed. classify's verdict reads `NAME (conclusion)`, and a name can hold
    parentheses itself (a matrix leg: `full-suite-matrix (macos-14)`), so cut at the LAST ` (` (#4790: cutting at the
    first one made a cancelled matrix leg vanish from the digest, so the shepherd never reran it)."""
    return {x.rsplit(" (", 1)[0] for x in classify(runs, [])["failed"]}


def flag(path: str) -> str | None:
    if path == PIN_FILE:
        return "crucible PIN (a pin bump is its own PR)"
    m = FLAGGED.search(path)
    return m.group(0).lower() if m else None


def check(n: int, api: Api = gh_api, graphql: GraphQL | None = None) -> dict[str, Any]:
    """`graphql` (#6534): the four reads come from one CHECK_QUERY; None, or a query that fails or comes back
    incomplete (over 100 files or runs, mergeability UNKNOWN), reads them through REST."""
    got = _graphql_check(graphql, n) if graphql else None
    if got:
        pr, runs, files, statuses = got["pr"], got["runs"], got["files"], got["statuses"]
    else:
        pr = api(f"repos/{REPO_SLUG}/pulls/{n}")
        runs = paged(api, f"repos/{REPO_SLUG}/commits/{pr['head']['sha']}/check-runs", "check_runs")
        status = api(f"repos/{REPO_SLUG}/commits/{pr['head']['sha']}/status")
        files = paged(api, f"repos/{REPO_SLUG}/pulls/{n}/files", limit=30)
        statuses = status.get("statuses", []) if status else []
    sha = pr["head"]["sha"]
    checks = classify(runs, statuses)
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


DRAFT_READY_NOTE = "was a draft: marked ready, not merged"


def draft_marked_ready(errors: list[str]) -> bool:
    """`merge`'s only non-failure return: the draft was marked ready and its CI starts (#5104). Not an error."""
    return len(errors) == 1 and DRAFT_READY_NOTE in errors[0]


def merge(res: dict[str, Any], run: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None) -> list[str]:
    """Squash-merge, pinned to the checked head SHA. A draft is marked ready and NOT merged (#5104): its heavy checks were
    skipped (a skip reads as green), so the merge waits for the CI that `ready_for_review` starts. Returns the errors."""
    run = run or _run
    n = str(res["number"])
    if res["draft"]:
        r = run(["gh", "pr", "ready", n, "-R", REPO_SLUG])
        if r.returncode:  # gh's GraphQL path can fail on this repo: the mutation directly
            q = "mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id}){pullRequest{isDraft}}}"
            r = run(["gh", "api", "graphql", "-f", f"query={q}", "-f", f"id={res['node_id']}"])
            if r.returncode:
                return [f"could not mark #{n} ready: {r.stderr.strip()[:300]}"]
        return [f"#{n} {DRAFT_READY_NOTE}. Its CI starts now; run --merge again when it is green"]
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
    ap.add_argument(
        "--merge",
        action="store_true",
        help="squash-merge, only when everything is green (a draft is only marked ready; run again when its CI is green)",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--digest", action="store_true", help="also print each failed check's digest (ci_digest.py)")
    args = ap.parse_args(argv)
    res = check(args.number, api, gh_graphql if api is gh_api else None)
    print(json.dumps(res, indent=1) if args.json else report(res))
    if args.digest and res["checks"]["failed"]:
        import ci_digest  # noqa: PLC0415 -- fetches job logs; only when asked

        print("\n" + ci_digest.render(ci_digest.digest(args.number, api)))
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
