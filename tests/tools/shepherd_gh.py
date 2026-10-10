#!/usr/bin/env python3
"""Label-driven merging (#4847 item 3, #4790 leftovers): a maintainer's label on a pull request is the queue.

Run by .github/workflows/shepherd-event.yml (pull_request_target: a label was added or removed, or new commits came)
and .github/workflows/shepherd-reconcile.yml (workflow_run after CI, a cron, a manual dispatch):

    python tests/tools/shepherd_gh.py event --event-path "$GITHUB_EVENT_PATH" [--dry-run]
    python tests/tools/shepherd_gh.py reconcile [--dry-run]         # every open PR carrying a shepherd:* label
    python tests/tools/shepherd_gh.py ensure-labels                 # create or refresh the label set (idempotent)

Requests (set by a maintainer with write access):
  shepherd:merge    mark ready and enable auto-merge (squash, pinned to the head); GitHub merges once the required
                    checks on main's ruleset are green -- a label can never merge a red PR
  shepherd:hold     never auto-merge
  shepherd:matrix   dispatch full-suite-gate.yml on the PR branch; auto-merge waits for a green run on this head
  shepherd:full     det sweep plans mode=full (tests/tools/det_sweep_plan.py reads the label)
Status (set and cleared by this module only): shepherd:needs-fix, shepherd:waiting-on-main, shepherd:retrying,
  shepherd:reapprove (the bot dropped shepherd:merge on a new head; stays until a maintainer re-adds it).

Rules, all in decide() (pure: a snapshot in, actions out):
  * a request label added by someone without write access is removed, with a comment (their label, not ours);
  * a new head (synchronize) removes shepherd:merge with a comment, so a commit nobody approved never merges by
    label. The one exception is this module's own `gh pr update-branch` (it leaves a marker comment first). The
    drop sets shepherd:reapprove, which outlives the request labels, so a PR that lost its approval is findable
    (`label:shepherd:reapprove`) instead of sitting silently (#4858 waited on a dropped label, 2026-10-10);
  * "Depends on #N" in the body blocks auto-merge until #N is merged;
  * an infra/flake failure is rerun up to INFRA_RERUNS times, RETRY_GAP seconds apart (the count is run_attempt
    of the run, kept by GitHub: no local state);
  * a real failure, a merge conflict or a red matrix gets ONE digest comment per head (marker in the comment);
  * behind main and green on a labelled PR -> `gh pr update-branch`.
Nothing here checks out PR code: it reads PR metadata, check runs and job logs through the GitHub API only.
Reused: pr_check (classify, paged, gh_api, merge conventions), ci_digest (triage and the digest text).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_digest  # noqa: E402
import pr_check  # noqa: E402

REPO_SLUG = pr_check.REPO_SLUG
MERGE, HOLD, MATRIX, FULL = "shepherd:merge", "shepherd:hold", "shepherd:matrix", "shepherd:full"
NEEDS, WAITING, RETRYING = "shepherd:needs-fix", "shepherd:waiting-on-main", "shepherd:retrying"
REAPPROVE = "shepherd:reapprove"
REQUESTS = (MERGE, HOLD, MATRIX, FULL)
STATUS = (NEEDS, WAITING, RETRYING, REAPPROVE)
WRITE = {"admin", "maintain", "write"}  # the collaborator permissions that may set a request label
INFRA_RERUNS = 3  # an outage (Docker Hub 429/504, 2026-10-09) outlasts one rerun
RETRY_GAP = 15 * 60  # seconds between reruns of the same run's failed jobs
MATRIX_WORKFLOW = "full-suite-gate.yml"
DET_WORKFLOW = "det-sweep.yml"  # shepherd:full reruns its latest pull_request run (it no longer runs on label events)
DEPENDS = re.compile(r"Depends on #(\d+)", re.I)
DOCS = "docs/ci.md"
MATRIX_TEXT = {
    "none": "not run on this head yet",
    "running": "running on this head",
    "red": "failed on this head",
    "fork": "not dispatchable from a fork branch: a maintainer runs it by hand",
}

# name -> (colour, description); the description is the label's page in GitHub, so it points at docs/ci.md
LABELS: dict[str, tuple[str, str]] = {
    MERGE: ("0e8a16", f"Maintainer: merge when green (auto-merge, squash). Guide: {DOCS}"),
    HOLD: ("b60205", f"Maintainer: never auto-merge this PR. Guide: {DOCS}"),
    MATRIX: ("1d76db", f"Maintainer: run the full-suite matrix on this head first. Guide: {DOCS}"),
    FULL: ("5319e7", f"Maintainer: plan the det sweep as full, not narrowed. Guide: {DOCS}"),
    NEEDS: ("d93f0b", f"Bot: a real failure on this head; see the digest comment. Guide: {DOCS}"),
    WAITING: ("fbca04", f"Bot: the failing check fails on main too (main's to fix). Guide: {DOCS}"),
    RETRYING: ("c2e0c6", f"Bot: an infra/flake rerun is pending on this head. Guide: {DOCS}"),
    REAPPROVE: ("e99695", f"Bot: new commits dropped shepherd:merge; re-add it to merge this head. Guide: {DOCS}"),
}

Api = Callable[[str], Any]
Run = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603


def _to_epoch(stamp: str | None) -> float | None:
    if not stamp:
        return None
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def writer(permission: str | None) -> bool:
    return permission in WRITE


# --- pure decision ---------------------------------------------------------------------------------------------------


def decide(s: dict[str, Any]) -> list[dict[str, Any]]:
    """The actions for one PR. `s` is the snapshot gather() builds (see its keys there); no I/O happens here."""
    n, sha = s["number"], s["head_sha"]
    acts: list[dict[str, Any]] = []
    labels = set(s["labels"])
    ev_label, sender = s.get("event_label"), s.get("sender")
    if ev_label in REQUESTS and sender is not None and not writer(sender.get("permission")):
        labels.discard(ev_label)
        acts.append({"op": "unlabel", "label": ev_label})
        acts.append(
            {
                "op": "comment",
                "body": f"CI shepherd: `{ev_label}` was added by @{sender['login']}, who has no "
                f"write access to this repository, so it was removed. Maintainers set these labels ({DOCS}).",
            }
        )
    actors = s.get("label_actors") or {}
    for name in sorted(labels & set(REQUESTS)):  # the timeline's labeler, for labels this event did not add
        actor = actors.get(name)
        if actor is None or not writer(actor.get("permission")):
            labels.discard(name)
            who = f"@{actor['login']}" if actor and actor.get("login") else "an unknown user (no labeled event found)"
            acts.append({"op": "unlabel", "label": name})
            acts.append(
                {
                    "op": "comment",
                    "body": f"CI shepherd: `{name}` was added by {who}, who has no write access "
                    f"to this repository, so it was removed. Maintainers set these labels ({DOCS}).",
                }
            )
    if s["state"] != "open":
        return acts
    if ev_label == FULL and FULL in labels:  # a writer's (a non-writer's was removed above): the plan reads it live
        acts.append({"op": "rerun_det", "sha": s["head_sha"]})
    dropped = False
    pending = bool(s.get("pending_update"))
    if MERGE in labels and not pending and not s.get("approved") and not s.get("awaiting"):
        # the head moved since a maintainer's label, or was never approved: nothing merges the unreviewed head
        labels.discard(MERGE)
        dropped = True
        acts.append({"op": "unlabel", "label": MERGE})
        acts.append(
            {
                "op": "comment",
                "body": f"CI shepherd: the head of this PR ({sha[:12]}) is not the one a "
                f"maintainer labelled `{MERGE}` on (new commits, or never approved), so the label was removed and "
                f"nothing merges unreviewed code. Re-add the label when the new head is ready (`{REAPPROVE}` marks "
                "this PR until then).",
            }
        )
    req = labels & set(REQUESTS)

    blocked = []
    if HOLD in labels:
        blocked.append(f"{HOLD} is set")
    for d in s.get("depends_open", []):
        blocked.append(f"Depends on #{d}, which is still open")
    if MATRIX in labels and s["matrix"] != "green":
        blocked.append(f"full-suite matrix {MATRIX_TEXT.get(s['matrix'], s['matrix'])}")
    if pending and MERGE in labels:
        blocked.append("a bot update of the branch is in progress")
    if s.get("awaiting") and MERGE in labels and not pending:
        blocked.append("no approval marker yet")
        acts.append(
            {"op": "note", "msg": f"{MERGE}: awaiting approval marker; re-add the label to approve (no action)"}
        )
    if s.get("record_approval") and MERGE in labels and not s.get("carried"):
        actor = (s.get("label_actors") or {}).get(MERGE) or {}
        acts.append({"op": "approve", "sha": sha, "login": actor.get("login") or "shepherd"})
    if s.get("carried") and MERGE in labels:
        acts.append({"op": "approve", "sha": sha, "by": "carried from the bot's update"})
    want = MERGE in labels and not blocked
    if want and s["draft"]:
        acts.append({"op": "ready"})
    if want and not s["auto_merge"]:
        acts.append({"op": "automerge", "on": True, "sha": sha})
    elif not want and s["auto_merge"] and (dropped or s.get("removed") == MERGE or req):
        acts.append({"op": "automerge", "on": False})
    if MATRIX in labels and s["matrix"] == "none" and not s["head_fork"]:
        acts.append({"op": "dispatch", "ref": s["head_ref"]})

    needs: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    retrying: list[dict[str, Any]] = []
    for f in s["failed"]:
        t = f["triage"]
        if t == "main":
            waiting.append(f)
        elif t in ("infra", "flake") and f.get("run_id") is not None and f.get("attempts", 0) < INFRA_RERUNS:
            if s["now"] - (f.get("updated_at") or 0) >= RETRY_GAP:
                acts.append({"op": "rerun", "run_id": f["run_id"], "check": f["check"]})
            retrying.append(f)
        else:  # real, a dirty tree, an infra failure with its reruns used up, or no run to rerun
            needs.append(f)
    if s["mergeable_state"] == "dirty":
        needs.append({"check": "merge conflict", "triage": "dirty"})
    if s["matrix"] == "red":
        needs.append({"check": "full-suite matrix", "triage": "real"})

    if req and HOLD not in labels and s["mergeable_state"] == "behind" and not s["failed"] and not s["pending"]:
        acts.append({"op": "update_branch"})
    if req and needs and not s["digest_posted"]:
        acts.append({"op": "comment", "body": f"<!-- shepherd-digest {sha} -->\n" + s["digest_text"]})

    desired: set[str] = set()
    if req:
        if needs:
            desired.add(NEEDS)
        if waiting:
            desired.add(WAITING)
        if retrying:
            desired.add(RETRYING)
    # outlives the request labels on purpose: the drop removed the only one, and the PR must stay findable. It goes
    # when the label comes back, when a maintainer holds the PR, or when someone removes it by hand.
    if dropped or (REAPPROVE in s["labels"] and MERGE not in labels and HOLD not in labels):
        desired.add(REAPPROVE)
    present = set(s["labels"]) & set(STATUS)
    if desired != present:
        acts.append({"op": "labels", "add": sorted(desired - present), "remove": sorted(present - desired)})
    return acts


# --- gather: the snapshot, from the API ------------------------------------------------------------------------------


APPROVE_MARK = re.compile(r"<!-- shepherd:approved sha=([0-9a-f]{40}) by=([A-Za-z0-9_.-]+) -->")
UPDATE_MARK = re.compile(r"<!-- shepherd-update from=([0-9a-f]{40})(?: to=([0-9a-f]{40}))? -->")


def _attempts(api: Api, run_id: int) -> tuple[int, float | None]:
    r = api(f"repos/{REPO_SLUG}/actions/runs/{run_id}")
    return int(r.get("run_attempt") or 1) - 1, _to_epoch(r.get("updated_at"))


def _perm(api: Api, login: str) -> str | None:
    try:
        return api(f"repos/{REPO_SLUG}/collaborators/{login}/permission").get("permission")
    except SystemExit:
        return None  # unreadable: not a writer


def head_pushed_at(api: Api, sha: str) -> str | None:
    """When `sha` became a head on GitHub: its earliest check suite's created_at (ISO 8601, so strings compare)."""
    try:
        suites = pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{sha}/check-suites", "check_suites")
    except (SystemExit, KeyError, TypeError):
        return None
    stamps = sorted(x["created_at"] for x in suites if x.get("created_at"))
    return stamps[0] if stamps else None


def gather(
    n: int, api: Api = pr_check.gh_api, event: dict[str, Any] | None = None, now: float | None = None
) -> dict[str, Any]:
    """The snapshot decide() reads for PR n. `event`: the facts of the pull_request_target payload that caused the pass
    (action, label, sender), when there was one. Reconcile passes have none.

    Approval (#4853 review): a maintainer's `shepherd:merge` is approved by a marker the bot writes itself, when the
    labeled event arrives from a writer: `<!-- shepherd:approved sha=<head> by=<login> -->`, with the head from the
    event payload (the head the maintainer labelled). Trust: only comments written by the bot's own account (the
    AUTOMATION_PAT user) count; anyone can post a comment. The newest trusted marker decides:
      * its sha is the current head -> approved;
      * the head is the bot's own update-branch result (its marker pair from=<approved> to=<head>, and the head's
        first parent is the approved commit) -> approved, carried over;
      * the bot's update is between its two markers -> pending, no decision;
      * no trusted marker at all -> awaiting (the labeled run never happened, or was dropped): no drop, quiet;
      * otherwise the head moved without approval -> the label is dropped."""
    event = event or {}
    perms: dict[str, str | None] = {}

    def perm(login: str) -> str | None:
        if login not in perms:
            perms[login] = _perm(api, login)
        return perms[login]

    pr = api(f"repos/{REPO_SLUG}/pulls/{n}")
    sha = pr["head"]["sha"]
    labels = [x["name"] for x in pr.get("labels") or []]
    head_repo = (pr["head"].get("repo") or {}).get("full_name")
    comments = pr_check.paged(api, f"repos/{REPO_SLUG}/issues/{n}/comments") if labels else []
    runs = pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{sha}/check-runs", "check_runs")
    statuses = (api(f"repos/{REPO_SLUG}/commits/{sha}/status") or {}).get("statuses", [])
    checks = pr_check.classify(runs, statuses)
    digest: dict[str, Any] = {"failed": []}
    if checks["failed"]:
        digest = ci_digest.digest(n, api)
        for f in digest["failed"]:
            if f["triage"] in ("infra", "flake") and f.get("run_id") is not None:
                f["attempts"], f["updated_at"] = _attempts(api, f["run_id"])
    # who last added each request label (the timeline; no commit ids are used)
    events = pr_check.paged(api, f"repos/{REPO_SLUG}/issues/{n}/events") if labels else []
    actors: dict[str, dict[str, Any] | None] = {}
    for name in labels:
        if name not in REQUESTS:
            continue
        last = None
        for ev in events:
            if ev.get("event") == "labeled" and (ev.get("label") or {}).get("name") == name:
                last = ev
        login = ((last or {}).get("actor") or {}).get("login")
        actors[name] = (
            {"login": login, "permission": perm(login), "at": last.get("created_at")} if last and login else None
        )
    depends_open: list[int] = []
    for d in sorted({int(x) for x in DEPENDS.findall(pr.get("body") or "")}):
        try:
            state = api(f"repos/{REPO_SLUG}/pulls/{d}")["state"]
        except SystemExit:
            state = "open"  # unreadable: treat as open, so auto-merge waits
        if state == "open":
            depends_open.append(d)
    # approval of shepherd:merge (see the docstring): only the bot's own comments are trusted
    bot = (api("user") or {}).get("login") or ""
    trusted = "\n".join(c.get("body") or "" for c in comments if bot and (c.get("user") or {}).get("login") == bot)
    if (event or {}).get("approved"):  # this pass just wrote it: a comment read right after its POST can lag behind it
        trusted += f"\n<!-- shepherd:approved sha={event['approved']} by={event.get('sender')} -->"
    approvals = APPROVE_MARK.findall(trusted)
    approved_sha = approvals[-1][0] if approvals else None
    updates = UPDATE_MARK.findall(trusted)
    frm, to = updates[-1] if updates else ("", "")
    approved = pending = carried = record = False
    m = actors.get(MERGE)
    # level-triggered (#4854): GitHub drops and reorders events (a pending run is replaced by the next; a handler can
    # start minutes late), so approval is read from state, never from which event arrived. The head was pushed when
    # GitHub created its first check suite (set by GitHub, unlike a commit date); a writer's label added after that is
    # an approval of this head, whichever pass sees it first -- that pass records the marker.
    pushed = head_pushed_at(api, sha) if MERGE in labels else None
    labelled = m.get("at") if m else None
    after_push = bool(pushed and labelled and labelled > pushed)
    if MERGE in labels and m and writer(m["permission"]) and (approved_sha == sha or after_push):
        approved = True
        record = approved_sha != sha
    elif MERGE in labels and approved_sha and m and writer(m["permission"]):
        if frm == approved_sha and to == sha:
            parents = [x["sha"] for x in api(f"repos/{REPO_SLUG}/commits/{sha}").get("parents", [])]
            carried = approved = len(parents) == 2 and parents[0] == approved_sha
        elif frm == approved_sha and not to:
            pending = True
    # no decision either way: the push time or the label time is unknown (a read failed, or the timeline lags)
    awaiting = MERGE in labels and not (approved or pending) and not (pushed and labelled)
    head_fork = head_repo != REPO_SLUG
    matrix = "none"
    matrix_url = ""
    if MATRIX in labels:
        if head_fork:
            matrix = "fork"
        else:
            runs_wd = api(f"repos/{REPO_SLUG}/actions/workflows/{MATRIX_WORKFLOW}/runs?head_sha={sha}&per_page=20")
            mine = [r for r in (runs_wd or {}).get("workflow_runs", []) if r.get("event") == "workflow_dispatch"]
            if mine:
                newest = mine[0]
                matrix_url = newest.get("html_url", "")
                if newest.get("status") != "completed":
                    matrix = "running"
                else:
                    matrix = "green" if newest.get("conclusion") == "success" else "red"
    marks_text = "\n".join(c.get("body") or "" for c in comments)
    digest_text = ci_digest.render(digest) if digest["failed"] else ""
    if matrix == "red":
        digest_text += f"\nfull-suite matrix failed on this head: {matrix_url}"
    if pr.get("mergeable_state") == "dirty":
        digest_text += (
            "\nThis PR conflicts with main, so no checks ran. Merge origin/main into it and regenerate "
            "generated files with their tools (never hand-merge them), then push."
        )
    sender = None
    if event.get("action") == "labeled" and event.get("sender"):
        sender = {"login": event["sender"], "permission": perm(event["sender"])}
    return {
        "number": n,
        "state": "merged" if pr.get("merged") else pr["state"],
        "draft": bool(pr.get("draft")),
        "head_sha": sha,
        "head_ref": pr["head"]["ref"],
        "head_fork": head_fork,
        "mergeable_state": pr.get("mergeable_state") or "unknown",
        "auto_merge": bool(pr.get("auto_merge")),
        "labels": labels,
        "depends_open": depends_open,
        "matrix": matrix,
        "label_actors": actors,
        "approved": approved,
        "record_approval": record,
        "carried": carried,
        "awaiting": awaiting,
        "pending_update": pending,
        "action": event.get("action"),
        "event_label": event.get("label") if event.get("action") == "labeled" else None,
        "removed": event.get("label") if event.get("action") == "unlabeled" else None,
        "sender": sender,
        "failed": digest["failed"],
        "pending": checks["pending"],
        "digest_text": digest_text,
        "digest_posted": f"<!-- shepherd-digest {sha} -->" in marks_text,
        "now": now if now is not None else time.time(),
    }


# --- apply: the actions, through gh ----------------------------------------------------------------------------------


def apply(n: int, s: dict[str, Any], acts: list[dict[str, Any]], run: Run = _run) -> list[str]:
    """Carry out the actions with gh. Returns one log line per action; a failed call is reported, never raised."""
    log: list[str] = []

    def gh(argv: list[str], what: str) -> None:
        r = run(argv)
        detail = "ok" if not r.returncode else "FAILED: " + (r.stderr or r.stdout).strip()[:200]
        log.append(f"#{n} {what}: {detail}")

    for a in acts:
        op = a["op"]
        if op == "unlabel":
            gh(
                ["gh", "api", "-X", "DELETE", f"repos/{REPO_SLUG}/issues/{n}/labels/{quote(a['label'], safe='')}"],
                f"unlabel {a['label']}",
            )
        elif op == "labels":
            if a["add"]:
                fields = [arg for x in a["add"] for arg in ("-f", f"labels[]={x}")]
                gh(
                    ["gh", "api", "-X", "POST", f"repos/{REPO_SLUG}/issues/{n}/labels", *fields],
                    f"add {', '.join(a['add'])}",
                )
            for x in a["remove"]:
                gh(
                    ["gh", "api", "-X", "DELETE", f"repos/{REPO_SLUG}/issues/{n}/labels/{quote(x, safe='')}"],
                    f"remove {x}",
                )
        elif op == "comment":
            gh(["gh", "api", f"repos/{REPO_SLUG}/issues/{n}/comments", "-f", f"body={a['body'][:60000]}"], "comment")
        elif op == "approve":
            gh(
                [
                    "gh",
                    "api",
                    f"repos/{REPO_SLUG}/issues/{n}/comments",
                    "-f",
                    f"body=<!-- shepherd:approved sha={a['sha']} by={a.get('login') or 'shepherd-update'} -->",
                ],
                f"approval marker for {a['sha'][:12]}",
            )
        elif op == "note":
            log.append(f"#{n} {a['msg']}")
        elif op == "ready":
            gh(["gh", "pr", "ready", str(n), "-R", REPO_SLUG], "ready for review")
        elif op == "automerge" and a["on"]:
            gh(
                ["gh", "pr", "merge", str(n), "-R", REPO_SLUG, "--auto", "--squash", "--match-head-commit", a["sha"]],
                "auto-merge on",
            )
        elif op == "automerge":
            gh(["gh", "pr", "merge", str(n), "-R", REPO_SLUG, "--disable-auto"], "auto-merge off")
        elif op == "rerun_det":
            r = run(["gh", "run", "list", "-R", REPO_SLUG, "--workflow", DET_WORKFLOW, "--commit", a["sha"],
                     "--event", "pull_request", "--limit", "1", "--json", "databaseId", "-q", ".[0].databaseId"])  # fmt: skip
            rid = (r.stdout or "").strip()
            if r.returncode or not rid.isdigit():
                log.append(f"#{n} rerun {DET_WORKFLOW}: no pull_request run found for {a['sha'][:12]}")
            else:
                gh(["gh", "run", "rerun", rid, "-R", REPO_SLUG], f"rerun {DET_WORKFLOW} (run {rid}) for {FULL}")
        elif op == "dispatch":
            gh(
                ["gh", "workflow", "run", MATRIX_WORKFLOW, "-R", REPO_SLUG, "--ref", a["ref"]],
                f"dispatch {MATRIX_WORKFLOW} on {a['ref']}",
            )
        elif op == "rerun":
            gh(
                ["gh", "run", "rerun", str(a["run_id"]), "--failed", "-R", REPO_SLUG],
                f"rerun {a['check']} (run {a['run_id']})",
            )
        elif op == "update_branch":
            # the marker first: the synchronize this push causes then keeps the labels (see decide)
            gh(
                [
                    "gh",
                    "api",
                    f"repos/{REPO_SLUG}/issues/{n}/comments",
                    "-f",
                    f"body=<!-- shepherd-update from={s['head_sha']} -->",
                ],
                "update marker",
            )
            gh(["gh", "pr", "update-branch", str(n), "-R", REPO_SLUG], "update-branch")
            # the result marker, always (a failed update records to == from): gather carries approval through this pair
            r = run(["gh", "api", f"repos/{REPO_SLUG}/pulls/{n}", "-q", ".head.sha"])
            new = r.stdout.strip() if r.returncode == 0 else ""
            if re.fullmatch(r"[0-9a-f]{40}", new):
                gh(
                    [
                        "gh",
                        "api",
                        f"repos/{REPO_SLUG}/issues/{n}/comments",
                        "-f",
                        f"body=<!-- shepherd-update from={s['head_sha']} to={new} -->",
                    ],
                    "update result marker",
                )
            else:
                log.append(f"#{n} update result marker: FAILED: could not read the new head")
    return log


def process(n: int, api: Api, run: Run, event: dict[str, Any] | None = None, dry_run: bool = False) -> list[str]:
    event = event or {}
    lines: list[str] = []
    sender, head = event.get("sender"), event.get("head")
    # the approval: a writer's labeled event names the head the maintainer labelled (the payload's head sha)
    if (
        event.get("action") == "labeled"
        and event.get("label") == MERGE
        and sender
        and head
        and not dry_run
        and writer(_perm(api, sender))
    ):
        r = run(
            [
                "gh",
                "api",
                f"repos/{REPO_SLUG}/issues/{n}/comments",
                "-f",
                f"body=<!-- shepherd:approved sha={head} by={sender} -->",
            ]
        )
        lines.append(f"#{n} approval marker for {head[:12]}: " + ("ok" if not r.returncode
                     else "FAILED: " + (r.stderr or r.stdout).strip()[:200]))  # fmt: skip
        if r.returncode:
            return lines  # no approval, so no auto-merge
        event = {**event, "approved": head}  # gather must not depend on reading back the comment it just posted
    try:
        s = gather(n, api, event)
    except SystemExit as e:  # one PR's failed read must not stop the others
        return lines + [f"#{n} skipped: {e}"]
    acts = decide(s)
    if not acts:
        return lines + [f"#{n} no action (labels: {', '.join(s['labels']) or 'none'})"]
    if dry_run:
        return lines + [f"#{n} would: {json.dumps(acts)}"]
    return lines + apply(n, s, acts, run)


# --- entry points ----------------------------------------------------------------------------------------------------


def event_facts(path: Path) -> tuple[int, dict[str, Any]]:
    """The PR number and the facts decide() needs, from a pull_request_target payload. Read as data: nothing in it is
    interpolated into a command (the label name is passed as one argv element, the sender's login into the API path)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    pr = payload.get("pull_request") or {}
    number = pr.get("number")
    if not isinstance(number, int):
        raise SystemExit("the event has no pull request number")
    facts: dict[str, Any] = {"action": payload.get("action"), "before": payload.get("before")}
    label = (payload.get("label") or {}).get("name")
    if isinstance(label, str):
        facts["label"] = label
    head = (pr.get("head") or {}).get("sha")
    if isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40}", head):
        facts["head"] = head
    login = (payload.get("sender") or {}).get("login")
    if isinstance(login, str) and re.fullmatch(r"[A-Za-z0-9-]+", login):
        facts["sender"] = login
    return number, facts


def prs_for_head(api: Api, sha: str) -> list[int]:
    """The open labelled PRs whose head is `sha` (a workflow_run's head: only its PRs need a pass)."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        raise SystemExit(f"not a commit sha: {sha!r}")
    prs = pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{sha}/pulls")
    return [
        p["number"]
        for p in prs
        if p.get("state") == "open" and any(x["name"] in REQUESTS + STATUS for x in p.get("labels") or [])
    ]


def open_labelled(api: Api) -> list[int]:
    prs = pr_check.paged(api, f"repos/{REPO_SLUG}/pulls?state=open")
    return [p["number"] for p in prs if any(x["name"] in REQUESTS + STATUS for x in p.get("labels") or [])]


def ensure_labels(run: Run = _run) -> list[str]:
    out = []
    for name, (colour, desc) in LABELS.items():
        r = run(["gh", "label", "create", name, "-R", REPO_SLUG, "--color", colour, "--description", desc, "--force"])
        out.append(f"{name}: {'ok' if not r.returncode else (r.stderr or r.stdout).strip()[:200]}")
    return out


def main(argv: list[str] | None = None, api: Api = pr_check.gh_api, run: Run = _run) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("event")
    e.add_argument("--event-path", type=Path, required=True)
    e.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("reconcile")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--head-sha", help="only the PRs whose head is this commit (a workflow_run's head_sha)")
    sub.add_parser("ensure-labels")
    args = ap.parse_args(argv)
    if args.cmd == "ensure-labels":
        lines = ensure_labels(run)
    elif args.cmd == "event":
        number, facts = event_facts(args.event_path)
        lines = process(number, api, run, facts, args.dry_run)
    else:
        lines = []
        for n in prs_for_head(api, args.head_sha) if args.head_sha else open_labelled(api):
            lines += process(n, api, run, None, args.dry_run)
    for line in lines:
        print(line)
    return 1 if any("FAILED" in x for x in lines) else 0


if __name__ == "__main__":
    sys.exit(main())
