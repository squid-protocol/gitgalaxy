#!/usr/bin/env python3
"""Label-driven merging (#4847 item 3, #4790 leftovers): a maintainer's label on a pull request is the queue.

Run by .github/workflows/shepherd-event.yml (pull_request_target: a label was added or removed, or new commits came)
and .github/workflows/shepherd-reconcile.yml (workflow_run after CI, a cron, a manual dispatch):

    python tests/tools/shepherd_gh.py event --event-path "$GITHUB_EVENT_PATH" [--dry-run]
    python tests/tools/shepherd_gh.py reconcile [--dry-run]         # every open PR (labels, plus the ci-gate status)
    python tests/tools/shepherd_gh.py ensure-labels                 # create or refresh the label set (idempotent)

Requests (set by a maintainer with write access):
  shepherd:merge    mark ready and enable auto-merge (squash, pinned to the head); GitHub merges once the required
                    checks on main's ruleset are green -- a label can never merge a red PR
  shepherd:hold     never auto-merge
  shepherd:matrix   dispatch full-suite-gate.yml on the PR branch; auto-merge waits for a green run on this head
  shepherd:full     det sweep plans mode=full (tests/tools/det_sweep_plan.py reads the label)
Status (set and cleared by this module only): shepherd:needs-fix, shepherd:waiting-on-main, shepherd:retrying,
  shepherd:needs-owner (auto-merge refused for good, #6061: token lacks a permission; sticky, no retry),
  shepherd:reapprove (the bot dropped shepherd:merge on a new head; stays until a maintainer re-adds it).

Rules, all in decide() (pure: a snapshot in, actions out):
  * a request label added by someone without write access is removed, with a comment (their label, not ours);
  * a new head (synchronize) removes shepherd:merge with a comment, so a commit nobody approved never merges by
    label. The one exception is a plain merge of main that leaves the PR's own change identical (clean_main_merge: a
    worker's, or one the bot made before #5134; the latter leaves a marker pair). The
    drop sets shepherd:reapprove, which outlives the request labels, so a PR that lost its approval is findable
    (`label:shepherd:reapprove`) instead of sitting silently (#4858 waited on a dropped label, 2026-10-10). The drop
    also turns the PR back into a draft and cancels the head's heavy runs (#6278 item 6): intermediate pushes run the
    cheap audits only, and re-adding the label marks it ready, which starts the full set once on the reviewed head;
  * "Depends on #N" in the body blocks auto-merge until #N is merged;
  * an infra/flake failure is rerun up to INFRA_RERUNS times, RETRY_GAP seconds apart (the count is run_attempt
    of the run, kept by GitHub: no local state), never while another run of that workflow is live on the PR's
    branch (the rerun would cancel it through the per-PR concurrency group);
  * a real failure, a merge conflict or a red matrix gets ONE digest comment per head (marker in the comment);
  * behind main is NOT acted on: the bot never updates a branch to keep it current (#5134, option A). The one exception
    (#5484, reconcile only): a PR labelled shepherd:waiting-on-main whose failing check is now green on main's newest
    commit, and whose head lacks that commit, gets main merged in ONCE (a plain merge); the label stays until a run on
    that head finishes, and a failure that survives it is `real`.
Nothing here checks out or runs PR code: it reads PR metadata, check runs and job logs through the GitHub API, and
clean_main_merge reads a few PR files through it as data (`git merge-file`, on fixed temp names).
Reused: pr_check (classify, paged, gh_api, merge conventions), ci_digest (triage and the digest text).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_digest  # noqa: E402
import flake_history  # noqa: E402
import pr_check  # noqa: E402

REPO_SLUG = pr_check.REPO_SLUG
MERGE, HOLD, MATRIX, FULL = "shepherd:merge", "shepherd:hold", "shepherd:matrix", "shepherd:full"
NEEDS, WAITING, RETRYING = "shepherd:needs-fix", "shepherd:waiting-on-main", "shepherd:retrying"
REAPPROVE = "shepherd:reapprove"
OWNER = "shepherd:needs-owner"  # #6061: auto-merge refused for good (token permission); only a person can merge
REQUESTS = (MERGE, HOLD, MATRIX, FULL)
STATUS = (NEEDS, WAITING, RETRYING, REAPPROVE, OWNER)
# GitHub's wording when the token may not touch a PR that edits workflow files, or lacks a permission: retrying cannot help
PERMANENT_REFUSAL = re.compile(
    r"without `?workflow`? scope|refusing to allow a personal access token|resource not accessible by"
    r"|must have admin rights|http 403|permission denied",
    re.I,
)
OWNER_TEXT = (
    "CI shepherd: auto-merge was refused for this PR and retrying cannot help ({why}). If it edits "
    "`.github/workflows/`, the shepherd token cannot enable auto-merge: merge it by hand, or give AUTOMATION_PAT "
    "Workflows: read and write. The shepherd will not try again while `" + OWNER + "` is set; remove the label to "
    "let it retry."
)
WRITE = {"admin", "maintain", "write"}  # the collaborator permissions that may set a request label
INFRA_RERUNS = 3  # an outage (Docker Hub 429/504, 2026-10-09) outlasts one rerun
RETRY_GAP = 15 * 60  # seconds between reruns of the same run's failed jobs
MATRIX_WORKFLOW = "full-suite-gate.yml"
# main's ruleset "main: required checks" (#4825). shepherd-reconcile.yml triggers on exactly the workflows behind these
# plus the matrix (#4935; tests/tools/test_shepherd_gh.py keeps the two in step). Change both together.
REQUIRED_CHECKS = ("det", "full-suite", "ground-truth", "mypy-audit", "ruff-audit")
# #6919: the commit status the shepherd posts on every open PR's head, so a path-filtered check (DOOM-rosetta, the call
# graph accuracy audit, ...) holds the merge once the ruleset requires it. Pending until the required checks have
# reported and nothing else runs, failure on any real failure, success otherwise. No runner waits for it.
GATE = "ci-gate"
GATE_OK = "every check that ran on this head passed"
# slow path-filtered workflows whose finish should not wait for the 20-minute cron to update the gate
GATE_TRIGGERS = ("DOOM-rosetta", "Call Graph Accuracy Audit")
ADVISORY: tuple[str, ...] = ()  # check names whose failure never holds a merge (#6919 asks about equivalence-e2e)
# #6278 item 6: the pull_request workflows that run on a draft (#5104); a drop cancels every other one on the head.
# test_workflow_draft_gate.py reads this set, so the two cannot drift.
CHEAP_ON_DRAFT = frozenset({"ruff-audit.yml", "mypy-audit.yml", "small-audits.yml", "answer-key-guard.yml"})
MERGE_READS = 20  # files clean_main_merge will read three times each (#7455 item 3); more goes to re-approval
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
    OWNER: ("b60205", f"Bot: auto-merge was refused (token permission); a maintainer merges by hand. Guide: {DOCS}"),
    REAPPROVE: ("e99695", f"Bot: new commits dropped shepherd:merge; re-add it to merge this head. Guide: {DOCS}"),
}

FLAKE_CACHE_ENV = "SHEPHERD_FLAKE_CACHE"  # where the workflow restores flake_history.json (#5398)

Api = Callable[[str], Any]
Run = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603


def learned_flakes(path: Path | None = None) -> set[str]:
    """The checks flake_history learned are flaky (#5398), read from its cache and never refreshed here: the workflow
    refreshes the cache (at most every 6 h) and keeps it across runs. No cache, no flakes: a pass never waits on a scan.
    The default is resolved here, not at definition time."""
    if path is None:
        env = os.environ.get(FLAKE_CACHE_ENV)
        path = Path(env) if env else flake_history.default_cache()
    return flake_history.learned(flake_history.load(path))


def _to_epoch(stamp: str | None) -> float | None:
    if not stamp:
        return None
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def _base_name(check: str) -> str:
    """A check's name without its matrix suffix: "full-suite (ubuntu, 3.11)" -> "full-suite"."""
    return check.rsplit(" (", 1)[0]


def writer(permission: str | None) -> bool:
    return permission in WRITE


def _gates(check: str) -> bool:
    """Whether a check's result holds the merge (#6919): not the shepherd's own jobs, not an ADVISORY check."""
    own = check == "shepherd" or check.startswith("shepherd (")  # "shepherd (label event)", its base name, a pending one
    return not own and _base_name(check) not in ADVISORY


def _names(checks: list[str]) -> str:
    text = ", ".join(sorted(set(checks)))
    return text if len(text) <= 120 else text[:117] + "..."  # a commit status description holds 140 characters


def gate_status(
    s: dict[str, Any], needs: list[dict[str, Any]], waiting: list[dict[str, Any]], retrying: list[dict[str, Any]]
) -> tuple[str, str] | None:
    """The ci-gate status for this head (#6919), from decide()'s triage; None for a closed PR."""
    if s["state"] != "open":
        return None
    failing = [_base_name(f["check"]) for f in needs if _gates(f["check"])]
    if failing:
        return "failure", "failing: " + _names(failing)
    if s["draft"]:  # #5104: a draft's heavy checks are skipped, and a skip reads as green
        return "pending", "draft: the checks run once it is ready for review"
    waits = [_base_name(f["check"]) for f in waiting + retrying if _gates(f["check"])]
    waits += [_base_name(p) for p in s.get("gate_pending", []) if _gates(p)]
    waits += s.get("required_missing", [])  # created right after a push; until then other runs may not exist yet
    if waits:
        return "pending", "waiting on: " + _names(waits)
    return "success", GATE_OK


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
                "this PR until then). Until then it is a draft and runs the cheap audits only; re-adding the label "
                "marks it ready, which starts the full set on that head.",
            }
        )
        if not s["draft"]:
            # #6278 item 6: heavy jobs on a head nobody may merge are wasted; a draft skips them (#5104) and cannot
            # merge, so no required check is weakened
            acts.append({"op": "draft", "sha": sha})
    draft = s["draft"] or dropped
    req = labels & set(REQUESTS)

    needs: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    retrying: list[dict[str, Any]] = []
    reran_runs: set[int] = set()
    # #5484: main turned green under a PR that was waiting on it. The same stale failure now triages `real`, but the head
    # has not been tested with main's fix yet: it keeps waiting (and gets main merged in) until it has.
    green = {_base_name(x) for x in s.get("main_green") or ()}
    stale = WAITING in s["labels"] and bool(s.get("main_sha")) and not s.get("contains_main")
    stale_hit = False
    for f in s["failed"]:
        t = f["triage"]
        if t == "real" and stale and _base_name(f["check"]) in green:
            t = "main"
            stale_hit = True
        if t == "main":
            waiting.append(f)
        elif t in ("infra", "flake") and f.get("run_id") is not None and f.get("attempts", 0) < INFRA_RERUNS:
            rid = f["run_id"]
            # a rerun replays the old event (draft=false): on a draft it would start the heavy jobs the draft skips;
            # nor while a newer run of the workflow is live on the PR: the rerun would cancel it (_attempts)
            if (
                not draft
                and not f.get("sibling_live")
                and rid not in reran_runs
                and s["now"] - (f.get("updated_at") or 0) >= RETRY_GAP
            ):
                acts.append({"op": "rerun", "run_id": rid, "check": f["check"]})
                reran_runs.add(rid)
            retrying.append(f)
        else:  # real, a dirty tree, an infra failure with its reruns used up, or no run to rerun
            needs.append(f)
    if s["mergeable_state"] == "dirty":
        needs.append({"check": "merge conflict", "triage": "dirty"})
    if s["matrix"] == "red":
        needs.append({"check": "full-suite matrix", "triage": "real"})

    blocked = []
    if HOLD in labels:
        blocked.append(f"{HOLD} is set")
    # #6919: a real failure of any check that gates, not only a required one, turns auto-merge off until the head is
    # green again; with the required checks alone a red path-filtered check merged (#6881, #6894, #6895)
    blocking = [_base_name(f["check"]) for f in needs if _gates(f["check"])]
    if blocking and MERGE in labels:
        blocked.append("failing: " + _names(blocking))
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
    if OWNER in labels and MERGE in labels:
        blocked.append(f"{OWNER} is set (auto-merge was refused for good)")  # #6061: no retry every pass
    want = MERGE in labels and not blocked
    if want and s["draft"]:
        # #5104: a draft head's heavy checks were skipped, and a skip reads as green. Auto-merge waits for the next pass,
        # after ready_for_review has started the real runs (shepherd-reconcile fires when they finish).
        acts.append({"op": "ready"})
    elif want and not s["auto_merge"]:
        acts.append({"op": "automerge", "on": True, "sha": sha})
    elif not want and s["auto_merge"] and (dropped or s.get("removed") == MERGE or req):
        acts.append({"op": "automerge", "on": False})
    if MATRIX in labels and s["matrix"] == "none" and not s["head_fork"]:
        acts.append({"op": "dispatch", "ref": s["head_ref"]})

    # no update_branch for a PR that is merely behind main (#5134): each push restarts its CI. The one case the bot does
    # merge main (#5484) is stale_hit above, once per main head; a conflict (dirty) stays the worker's.
    if (
        req
        and stale_hit
        and not needs
        and not s["head_fork"]
        and HOLD not in labels
        and not s.get("main_merged")
        and s["mergeable_state"] != "dirty"
    ):
        acts.append({"op": "update_main", "sha": sha, "main": s["main_sha"]})
    if req and needs and not s["digest_posted"]:
        acts.append({"op": "comment", "body": f"<!-- shepherd-digest {sha} -->\n" + s["digest_text"]})

    desired: set[str] = set()
    if OWNER in s["labels"] and MERGE in labels:
        desired.add(OWNER)  # sticky: a pass must not remove it for the next pass to add back (#6061)
    if req:
        if (
            needs and OWNER not in desired
        ):  # the owner status wins: needs-fix would flap with the shepherd's own red run
            desired.add(NEEDS)
        if waiting:
            desired.add(WAITING)
        if retrying:
            desired.add(RETRYING)
        # #5484: main's fix is in the head but no run on it has finished: not ready, not needs-fix
        if (
            WAITING in s["labels"]
            and s.get("main_merged")
            and s.get("contains_main")
            and not s["failed"]
            and (s["pending"] or s.get("no_checks"))
        ):
            desired.add(WAITING)
    # outlives the request labels on purpose: the drop removed the only one, and the PR must stay findable. It goes
    # when the label comes back, when a maintainer holds the PR, or when someone removes it by hand.
    if dropped or (REAPPROVE in s["labels"] and MERGE not in labels and HOLD not in labels):
        desired.add(REAPPROVE)
    present = set(s["labels"]) & set(STATUS)
    if desired != present:
        acts.append({"op": "labels", "add": sorted(desired - present), "remove": sorted(present - desired)})
    gate = gate_status(s, needs, waiting, retrying)
    if gate and gate != s.get("gate_now"):  # every open PR, labelled or not: a merge by hand is gated too (#6919)
        acts.append({"op": "gate", "sha": sha, "state": gate[0], "description": gate[1]})
    return acts


# --- gather: the snapshot, from the API ------------------------------------------------------------------------------


APPROVE_MARK = re.compile(r"<!-- shepherd:approved sha=([0-9a-f]{40}) by=([A-Za-z0-9_.-]+) -->")
UPDATE_MARK = re.compile(r"<!-- shepherd-update from=([0-9a-f]{40})(?: to=([0-9a-f]{40}))? -->")


def _attempts(api: Api, run_id: int) -> tuple[int, float | None, bool]:
    """(reruns used, last update, whether another run of the same workflow is queued or running on the same branch).
    2026-10-29 (#6971, #7026): a rerun joins the workflow's per-PR concurrency group, and `cancel-in-progress` then
    cancels the newer run already testing the head; its cancelled shards failed the gate jobs, which triaged infra and
    were rerun in turn. While a sibling run is live the rerun waits: that run's own result decides the check."""
    r = api(f"repos/{REPO_SLUG}/actions/runs/{run_id}")
    used, updated = int(r.get("run_attempt") or 1) - 1, _to_epoch(r.get("updated_at"))
    wid, branch = r.get("workflow_id"), r.get("head_branch")
    if not wid or not branch:
        return used, updated, False
    try:
        page = api(f"repos/{REPO_SLUG}/actions/workflows/{wid}/runs?branch={quote(branch, safe='')}&per_page=20")
    except SystemExit:
        return used, updated, False  # unreadable: rerun as before rather than hold the PR
    live = any(
        x.get("id") != run_id and x.get("status") in ("queued", "in_progress", "waiting", "pending", "requested")
        for x in (page or {}).get("workflow_runs") or []
    )
    return used, updated, live


def _files(api: Api, base: str, head: str) -> dict[str, tuple[Any, ...]] | None:
    """{path: (status, blob sha, old path, patch)} of the three-dot compare base...head, or None when it cannot be trusted
    (an unreadable compare, or a file list GitHub may have truncated at 300 files)."""
    try:
        files = pr_check.paged(api, f"repos/{REPO_SLUG}/compare/{base}...{head}", "files", limit=3)
    except SystemExit:
        return None
    if len(files) >= 300:
        return None
    return {
        f["filename"]: (f.get("status", ""), f.get("sha", ""), f.get("previous_filename"), f.get("patch"))
        for f in files
    }


def _blob(api: Api, path: str, ref: str) -> bytes | None:
    """A file's bytes at `ref`, as data. None when it cannot be read: missing, or over the contents API's 1 MB."""
    try:
        doc = api(f"repos/{REPO_SLUG}/contents/{quote(path, safe='/')}?ref={ref}")
        return base64.b64decode(doc["content"]) if doc.get("encoding") == "base64" else None
    except (SystemExit, AttributeError, KeyError, TypeError, ValueError):
        return None


def _is_clean_merge(api: Api, path: str, base: str, ours: str, theirs: str, want: str) -> bool:
    """Whether blob `want` is byte for byte the clean three-way merge of `path` (#7455 item 3). `git merge-file` only reads
    the three files as text under fixed names: no PR code runs, and the path never reaches the filesystem."""
    texts = [_blob(api, path, ref) for ref in (base, ours, theirs)]
    if texts[0] is None or texts[1] is None or texts[2] is None:
        return False
    merged = texts[1]
    # main changed the file too; when it did not, the PR's own bytes are the merge (binary too)
    if texts[0] != texts[2]:
        with tempfile.TemporaryDirectory() as tmp:
            names = [os.path.join(tmp, x) for x in ("base", "ours", "theirs")]
            for name, text in zip(names, texts, strict=True):
                Path(name).write_bytes(text)
            if _run(["git", "merge-file", "-q", names[1], names[0], names[2]]).returncode:
                return False  # a conflict (the count), or a binary file: the hand-resolved merge is a new change
            merged = Path(names[1]).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(merged) + merged, usedforsecurity=False).hexdigest() == want


def _same_modes(graphql: pr_check.GraphQL | None, a: str, b: str, paths: list[str]) -> bool:
    """Whether every path has one file mode at commits a and b. Only a mode change to a file the PR already changes
    needs this: no compare shows it (a mode-only change elsewhere is a row of its own). Paths go as query variables, so
    a file name cannot change the query; a path missing at either commit is an error, so False."""
    if not paths:
        return True
    if graphql is None:
        return False
    owner, name = REPO_SLUG.split("/")
    args = "".join(f",$p{i}:String!" for i in range(len(paths)))
    fields = " ".join(f"f{i}:file(path:$p{i}){{mode}}" for i in range(len(paths)))
    query = (
        f"query($owner:String!,$name:String!,$a:GitObjectID!,$b:GitObjectID!{args})"
        "{repository(owner:$owner,name:$name){a:object(oid:$a){...F} b:object(oid:$b){...F}}}"
        f" fragment F on Commit{{{fields}}}"
    )
    try:
        variables = {"owner": owner, "name": name, "a": a, "b": b} | {f"p{i}": p for i, p in enumerate(paths)}
        repo = graphql(query, variables)
        modes = repo["repository"]["a"]
        return len(modes) == len(paths) and None not in modes.values() and modes == repo["repository"]["b"]
    except (SystemExit, AttributeError, KeyError, TypeError):
        return False


def clean_main_merge(
    api: Api, approved: str, head: str, base_ref: str, graphql: pr_check.GraphQL | None = None
) -> bool:
    """True only when `head` is a plain merge of main into the approved head and the PR's own change did not move.

    Parents are exactly (approved head, a commit already on main), in either order. Against that commit, head's diff
    (the whole of what head adds to main, so an evil merge's extra change is in it) must name the same files as the
    approved diff. Each file has the same status, blob and patch, or (main touched the file too, #7455 item 3) head's
    blob is byte for byte the clean three-way merge. `git patch-id` is not used: it ignores whitespace and hunk position.
    A conflict resolution is therefore a change. Anything else, or any read that fails, is False: the new head then
    goes to re-approval (#4948, #4966 waited on this, 2026-10-12). Every file's mode must match too (_same_modes)."""
    try:
        parents = [x["sha"] for x in api(f"repos/{REPO_SLUG}/commits/{head}").get("parents", [])]
        if len(parents) != 2 or approved not in parents:
            return False
        other = parents[1] if parents[0] == approved else parents[0]
        if (api(f"repos/{REPO_SLUG}/compare/{quote(base_ref, safe='')}...{other}") or {}).get("status") not in (
            "behind",
            "identical",
        ):
            return False  # the other parent is not already on main
        mine = _files(api, other, approved)  # the approved patch, from its merge base with main
        now = _files(api, other, head)  # the same patch on the new head: all that head adds to that main commit
        if not mine or now is None or set(mine) != set(now):
            return False
        # a file with no patch (binary, too large) may hide a change of main's that head undid: read it
        unseen = [f for f in mine if mine[f][3] is None and mine[f][0] not in ("added", "removed")]
        moved = sorted({f for f in mine if mine[f] != now[f]} | set(unseen))
        if len(moved) > MERGE_READS or any(mine[f][0] != "modified" or now[f][0] != "modified" for f in moved):
            return False  # a rename, an add or a delete on both sides is a merge no one can call plain
        base = api(f"repos/{REPO_SLUG}/compare/{other}...{approved}")["merge_base_commit"]["sha"] if moved else ""
    except (SystemExit, AttributeError, KeyError, TypeError):
        return False
    kept = [f for f in now if now[f][0] != "removed"]
    return all(_is_clean_merge(api, f, base, approved, other, now[f][1]) for f in moved) and _same_modes(
        graphql, approved, head, kept
    )


TRUSTED_BOTS_ENV = "SHEPHERD_TRUSTED_BOTS"


def trusted_bots(api: Api) -> set[str]:
    """The accounts whose approval markers count. promoter-bot#64 (2026-10-24): the shepherd moves from AUTOMATION_PAT
    to a GitHub App (its own API quota), and an App's installation token cannot read `user`; its comments come from
    `<app>[bot]`. #6694: SHEPHERD_TRUSTED_BOTS may still name the PAT's account (the workflows did while markers it
    wrote were on open PRs; none are now), but only `[bot]` logins are trusted from it, so a marker from a human or
    PAT account never counts. Without the variable, the token's own account, as before (local runs)."""
    if names := {x.strip() for x in os.environ.get(TRUSTED_BOTS_ENV, "").split(",") if x.strip()}:
        return {x for x in names if x.endswith("[bot]")}
    try:
        login = (api("user") or {}).get("login")
    except SystemExit:
        return set()
    return {login} if login else set()


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


# #6534: the per-PR reads of gather() in one GraphQL query (its own points quota, not REST's 5,000/h). Every list is
# fetched whole or not used: a connection longer than what came back sends the PR down the REST path.
PR_FIELDS = pr_check.PR_FIELDS
PR_QUERY = (
    "query($owner: String!, $name: String!, $n: Int!) {\n  rateLimit { cost }\n  repository(owner: $owner, name: $name) {\n"
    "    pullRequest(number: $n) {" + PR_FIELDS + "    }\n  }\n}"
)
BATCH = 5  # PRs per query: a PR_FIELDS read is ~3 points; five keep a query well inside GitHub's node limit


def batch_query(numbers: list[int]) -> str:
    """One query for several PRs: each is the alias `p<N>` of the same PR_FIELDS selection."""
    pulls = "".join(f"    p{n}: pullRequest(number: {int(n)}) {{{PR_FIELDS}    }}\n" for n in numbers)
    return f"query($owner: String!, $name: String!) {{\n  rateLimit {{ cost }}\n  repository(owner: $owner, name: $name) {{\n{pulls}  }}\n}}"


LABELLED_QUERY = """
query($owner: String!, $name: String!) {
  rateLimit { cost }
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage }
      nodes { number labels(first: 100) { totalCount nodes { name } } }
    }
  }
}"""


Truncated = pr_check.Truncated
_whole = pr_check.whole


def _login(who: dict[str, Any] | None) -> dict[str, Any] | None:
    """REST's user object: an app's account reads `name[bot]` there, bare `name` in GraphQL."""
    if not who:
        return None
    return {"login": who["login"] + ("[bot]" if who.get("__typename") == "Bot" else "")}


def graphql_reads(p: dict[str, Any]) -> dict[str, Any]:
    """The REST shapes gather() reads (the pull, its comments, the head's check runs, statuses, labeled events and push
    time), from one PR_QUERY pullRequest. KeyError / TypeError / Truncated when anything is missing or cut short."""
    commit = p["commits"]["nodes"][0]["commit"]
    if commit["oid"] != p["headRefOid"]:
        raise Truncated  # the head moved between the two fields
    suites = _whole(commit["checkSuites"])
    runs = pr_check.runs_from_suites(suites)
    stamps = sorted(s["createdAt"] for s in suites if s.get("createdAt"))
    pr = {
        "number": p["number"],
        "state": "open" if p["state"] == "OPEN" else "closed",
        "merged": bool(p["merged"]),
        "draft": bool(p["isDraft"]),
        "body": p["body"],
        "mergeable_state": (p["mergeStateStatus"] or "unknown").lower(),
        "auto_merge": p["autoMergeRequest"],
        "head": {
            "sha": p["headRefOid"],
            "ref": p["headRefName"],
            "repo": {"full_name": p["headRepository"]["nameWithOwner"]} if p["headRepository"] else None,
        },
        "base": {"ref": p["baseRefName"]},
        "labels": [{"name": x["name"]} for x in _whole(p["labels"])],
    }
    return {
        "pr": pr,
        "comments": [{"body": c["body"], "user": _login(c["author"])} for c in _whole(p["comments"])],
        "runs": runs,
        "statuses": [
            {"context": c["context"], "state": c["state"].lower(), "description": c.get("description")}
            for c in ((commit.get("status") or {}).get("contexts") or [])
        ],
        "events": [
            {
                "event": "labeled",
                "label": {"name": e["label"]["name"]},
                "actor": _login(e["actor"]),
                "created_at": e["createdAt"],
            }
            for e in _whole(p["timelineItems"], "filteredCount")  # totalCount counts every item type
        ],
        "pushed": stamps[0] if stamps else None,
    }


def _graphql_pr(graphql: pr_check.GraphQL, n: int) -> dict[str, Any] | None:
    """graphql_reads for PR n, or None (the REST path) when the query fails or any list is incomplete."""
    owner, name = REPO_SLUG.split("/")
    try:
        return graphql_reads(graphql(PR_QUERY, {"owner": owner, "name": name, "n": n})["repository"]["pullRequest"])
    except (SystemExit, KeyError, TypeError, IndexError, AttributeError, ValueError):
        return None


def _graphql_prs(graphql: pr_check.GraphQL, numbers: list[int]) -> dict[int, dict[str, Any] | None]:
    """graphql_reads for each PR in `numbers`, BATCH of them per query. A PR whose part is missing, null or incomplete
    (or whose batch failed) maps to None: gather() reads that one through REST."""
    owner, name = REPO_SLUG.split("/")
    out: dict[int, dict[str, Any] | None] = {}
    for i in range(0, len(numbers), BATCH):
        chunk = list(dict.fromkeys(numbers[i : i + BATCH]))
        try:
            repo = graphql(batch_query(chunk), {"owner": owner, "name": name})["repository"]
        except (SystemExit, KeyError, TypeError, AttributeError, ValueError):
            repo = {}
        for n in chunk:
            try:
                out[n] = graphql_reads(repo[f"p{n}"])
            except (KeyError, TypeError, IndexError, AttributeError, ValueError):
                out[n] = None
    return out


def gather(
    n: int,
    api: Api = pr_check.gh_api,
    event: dict[str, Any] | None = None,
    now: float | None = None,
    on_main: set[str] | None = None,
    flaky: set[str] | None = None,
    main: tuple[str, set[str]] | None = None,
    graphql: pr_check.GraphQL | None = None,
    prefetched: dict[int, dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """The snapshot decide() reads for PR n. `event`: the facts of the pull_request_target payload that caused the pass
    (action, label, sender), when there was one. Reconcile passes have none.
    `main`: (main's newest sha, the checks green on it) from ci_digest.main_green -- reconcile passes only (#5484); with
    it a PR labelled shepherd:waiting-on-main also gets contains_main, main_merged and main_green/main_sha.

    Approval (#4853 review): a maintainer's `shepherd:merge` is approved by a marker the bot writes itself, when the
    labeled event arrives from a writer: `<!-- shepherd:approved sha=<head> by=<login> -->`, with the head from the
    event payload (the head the maintainer labelled). Trust: only comments written by the bot's own account (the
    accounts in SHEPHERD_TRUSTED_BOTS, else the token's own) count; anyone can post a comment. The newest trusted marker decides:
      * its sha is the current head -> approved;
      * the head is the bot's own update-branch result (its marker pair from=<approved> to=<head>, and the head's
        first parent is the approved commit) -> approved, carried over;
      * the head is a plain merge of main into the approved head that left the PR's own change identical
        (clean_main_merge) -> approved, carried over; any other new head is not;
      * the bot's update is between its two markers -> pending, no decision;
      * no trusted marker at all -> awaiting (the labeled run never happened, or was dropped): no drop, quiet;
      * otherwise the head moved without approval -> the label is dropped.
    `graphql` (#6534): the PR, comments, head checks, labeled events and push time come from one PR_QUERY instead of
    six REST reads; None, or a query that fails or comes back incomplete, reads them through REST.
    `prefetched`: _graphql_prs' answer for a whole pass (several PRs per query); an entry that is None reads through REST."""
    event = event or {}
    if prefetched is not None and n in prefetched:
        got = prefetched[n]
    else:
        got = _graphql_pr(graphql, n) if graphql else None
    perms: dict[str, str | None] = {}

    def perm(login: str) -> str | None:
        if login not in perms:
            perms[login] = _perm(api, login)
        return perms[login]

    if got and got["pr"]["mergeable_state"] == "unknown":
        # GraphQL reports UNKNOWN until something asks GitHub to compute it; the REST read does, and a dirty PR
        # must not pass for clean. A head that moved in between leaves the rest of the record stale: REST for all.
        rest = api(f"repos/{REPO_SLUG}/pulls/{n}")
        got = {**got, "pr": rest} if rest["head"]["sha"] == got["pr"]["head"]["sha"] else None
        pr = rest
    else:
        pr = got["pr"] if got else api(f"repos/{REPO_SLUG}/pulls/{n}")
    sha = pr["head"]["sha"]
    labels = [x["name"] for x in pr.get("labels") or []]
    head_repo = (pr["head"].get("repo") or {}).get("full_name")
    comments = (
        (got["comments"] if got else pr_check.paged(api, f"repos/{REPO_SLUG}/issues/{n}/comments")) if labels else []
    )
    runs = got["runs"] if got else pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{sha}/check-runs", "check_runs")
    statuses = got["statuses"] if got else (api(f"repos/{REPO_SLUG}/commits/{sha}/status") or {}).get("statuses", [])
    # #6919: the shepherd's own ci-gate status is its output, never an input (a pending gate would wait on itself)
    own = [st for st in statuses if st.get("context") == GATE]
    gate_now = (own[0]["state"], own[0].get("description") or "") if own else None
    statuses = [st for st in statuses if st.get("context") != GATE]
    checks = pr_check.classify(runs, statuses)
    reported = {r.get("name") for r in runs}
    digest: dict[str, Any] = {"failed": []}
    if checks["failed"]:
        digest = ci_digest.digest(n, api, on_main=on_main, flaky=flaky, pr=pr, runs=runs)
        attempts_by_run: dict[int, tuple[int, float | None, bool]] = {}
        for f in digest["failed"]:
            if f["triage"] in ("infra", "flake") and f.get("run_id") is not None:
                rid = f["run_id"]
                if rid not in attempts_by_run:
                    attempts_by_run[rid] = _attempts(api, rid)
                f["attempts"], f["updated_at"], f["sibling_live"] = attempts_by_run[rid]
    # who last added each request label (the timeline; no commit ids are used)
    events = (got["events"] if got else pr_check.paged(api, f"repos/{REPO_SLUG}/issues/{n}/events")) if labels else []
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
    bots = trusted_bots(api)
    trusted = "\n".join(c.get("body") or "" for c in comments if (c.get("user") or {}).get("login") in bots)
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
    pushed = (got["pushed"] if got else head_pushed_at(api, sha)) if MERGE in labels else None
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
        else:  # someone else's plain merge of main (the web "update branch", a local `git merge`): same approval
            base_ref = (pr.get("base") or {}).get("ref") or "main"
            carried = approved = clean_main_merge(api, approved_sha, sha, base_ref, graphql)
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
    main_facts: dict[str, Any] = {}
    if main and main[0] and WAITING in labels:
        try:
            cmp_status = (api(f"repos/{REPO_SLUG}/compare/{main[0]}...{sha}") or {}).get("status")
        except SystemExit:
            cmp_status = None
        if cmp_status in ("ahead", "identical"):
            contains = True
        elif cmp_status in ("behind", "diverged"):
            contains = False
        else:
            contains = True  # unreadable: assume nothing to merge
        main_facts = {
            "main_sha": main[0],
            "main_green": sorted(main[1]),
            "contains_main": contains,
            "main_merged": f"<!-- shepherd-main-merge main={main[0]} -->" in trusted,
            "no_checks": not runs,
        }
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
        "gate_pending": checks["pending"],
        "required_missing": [c for c in REQUIRED_CHECKS if c not in reported],
        "gate_now": gate_now,
        "digest_text": digest_text,
        "digest_posted": f"<!-- shepherd-digest {sha} -->" in marks_text,
        "now": now if now is not None else time.time(),
        **main_facts,
    }


# --- apply: the actions, through gh ----------------------------------------------------------------------------------


def apply(n: int, s: dict[str, Any], acts: list[dict[str, Any]], run: Run = _run) -> list[str]:
    """Carry out the actions with gh. Returns one log line per action; a failed call is reported, never raised."""
    log: list[str] = []

    def refused(argv: list[str], what: str) -> None:
        """Auto-merge on: a permanent permission refusal is labelled once and commented once, not reported FAILED."""
        r = run(argv)
        err = (r.stderr or r.stdout or "").strip()
        if r.returncode and PERMANENT_REFUSAL.search(err):
            why = err.replace("`", "'")[:200]
            body = OWNER_TEXT.format(why=why)
            lab = ["gh", "api", "-X", "POST", f"repos/{REPO_SLUG}/issues/{n}/labels", "-f", f"labels[]={OWNER}"]
            cmt = ["gh", "api", f"repos/{REPO_SLUG}/issues/{n}/comments", "-f", f"body={body}"]
            if not run(lab).returncode:
                run(cmt)  # the label is the once-guard: decide() stops asking while it is set
            log.append(f"#{n} {what}: refused for good, labelled {OWNER}: {why}")
        else:
            log.append(f"#{n} {what}: " + ("ok" if not r.returncode else "FAILED: " + err[:200]))

    def gh(argv: list[str], what: str) -> None:
        r = run(argv)
        err = (r.stderr or r.stdout or "").strip()
        if not r.returncode:
            detail = "ok"
        elif (what.startswith("rerun") or (len(argv) >= 3 and argv[:3] == ["gh", "run", "rerun"])) and (
            "already running" in f"{r.stderr or ''} {r.stdout or ''}".lower()
        ):
            detail = "skipped (already running)"
        else:
            detail = "FAILED: " + err[:200]
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
        elif op == "draft":
            gh(["gh", "pr", "ready", str(n), "-R", REPO_SLUG, "--undo"], "back to draft")
            r = run(
                ["gh", "api", f"repos/{REPO_SLUG}/actions/runs?head_sha={a['sha']}&event=pull_request&per_page=100"]
            )
            try:
                runs = None if r.returncode else json.loads(r.stdout or "{}").get("workflow_runs", [])
            except ValueError:
                runs = None
            if runs is None:
                log.append(f"#{n} cancel heavy runs on {a['sha'][:12]}: FAILED to list runs")
            for x in runs or []:
                if x.get("status") == "completed" or (x.get("path") or "").rsplit("/", 1)[-1] in CHEAP_ON_DRAFT:
                    continue
                gh(["gh", "run", "cancel", str(x["id"]), "-R", REPO_SLUG], f"cancel {x.get('name')} (run {x['id']})")
        elif op == "automerge" and a["on"]:
            refused(
                ["gh", "pr", "merge", str(n), "-R", REPO_SLUG, "--auto", "--squash", "--match-head-commit", a["sha"]],
                "auto-merge on",
            )
        elif op == "automerge":
            gh(["gh", "pr", "merge", str(n), "-R", REPO_SLUG, "--disable-auto"], "auto-merge off")
        elif op == "gate":
            gh(
                [
                    "gh", "api", f"repos/{REPO_SLUG}/statuses/{a['sha']}", "-f", f"state={a['state']}",
                    "-f", f"context={GATE}", "-f", f"description={a['description']}",
                    "-f", f"target_url=https://github.com/{REPO_SLUG}/pull/{n}/checks",
                ],
                f"{GATE} {a['state']}: {a['description']}",
            )  # fmt: skip
        elif op == "update_main":
            old, main_sha = a["sha"], a["main"]
            r = run(["gh", "api", f"repos/{REPO_SLUG}/issues/{n}/comments", "-f",
                     f"body=<!-- shepherd-main-merge main={main_sha} -->\n<!-- shepherd-update from={old} -->"])  # fmt: skip
            if r.returncode:
                log.append(f"#{n} merge main: FAILED (claim marker): " + (r.stderr or r.stdout).strip()[:200])
                continue
            r = run(
                [
                    "gh",
                    "api",
                    "-X",
                    "PUT",
                    f"repos/{REPO_SLUG}/pulls/{n}/update-branch",
                    "-f",
                    f"expected_head_sha={old}",
                ]
            )
            new = old
            if not r.returncode:
                g = run(["gh", "api", f"repos/{REPO_SLUG}/pulls/{n}", "-q", ".head.sha"])
                got = (g.stdout or "").strip()
                new = got if re.fullmatch(r"[0-9a-f]{40}", got) else old
            run(["gh", "api", f"repos/{REPO_SLUG}/issues/{n}/comments", "-f",
                 f"body=<!-- shepherd-update from={old} to={new} -->"])  # fmt: skip
            if r.returncode:
                log.append(
                    f"#{n} merge main {main_sha[:12]} into {old[:12]}: FAILED: " + (r.stderr or r.stdout).strip()[:200]
                )
            else:
                log.append(f"#{n} merged main {main_sha[:12]} into {old[:12]} -> {new[:12]}")
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
    return log


def process(
    n: int,
    api: Api,
    run: Run,
    event: dict[str, Any] | None = None,
    dry_run: bool = False,
    on_main: set[str] | None = None,
    flaky: set[str] | None = None,
    main: tuple[str, set[str]] | None = None,
    graphql: pr_check.GraphQL | None = None,
    prefetched: dict[int, dict[str, Any] | None] | None = None,
) -> list[str]:
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
        s = gather(n, api, event, on_main=on_main, flaky=flaky, main=main, graphql=graphql, prefetched=prefetched)
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


def open_labelled(api: Api, graphql: pr_check.GraphQL | None = None) -> list[int]:
    """The open PRs carrying a request or status label: one GraphQL read (#6534), the REST listing when it fails or is
    cut short (more than 100 open PRs, or a PR with more than 100 labels)."""
    if graphql:
        owner, name = REPO_SLUG.split("/")
        try:
            conn = graphql(LABELLED_QUERY, {"owner": owner, "name": name})["repository"]["pullRequests"]
            if conn["pageInfo"]["hasNextPage"]:
                raise pr_check.Truncated
            return [
                p["number"] for p in conn["nodes"] if any(x["name"] in REQUESTS + STATUS for x in _whole(p["labels"]))
            ]
        except (SystemExit, KeyError, TypeError, AttributeError, ValueError):
            pass
    prs = pr_check.paged(api, f"repos/{REPO_SLUG}/pulls?state=open")
    return [p["number"] for p in prs if any(x["name"] in REQUESTS + STATUS for x in p.get("labels") or [])]


def open_prs(api: Api, graphql: pr_check.GraphQL | None = None) -> list[int]:
    """Every open PR (#6919: each gets a ci-gate status, labelled or not): one GraphQL read, REST when it fails."""
    if graphql:
        owner, name = REPO_SLUG.split("/")
        try:
            conn = graphql(LABELLED_QUERY, {"owner": owner, "name": name})["repository"]["pullRequests"]
            if conn["pageInfo"]["hasNextPage"]:
                raise pr_check.Truncated
            return [p["number"] for p in conn["nodes"]]
        except (SystemExit, KeyError, TypeError, AttributeError, ValueError):
            pass
    return [p["number"] for p in pr_check.paged(api, f"repos/{REPO_SLUG}/pulls?state=open")]


def ensure_labels(run: Run = _run) -> list[str]:
    out = []
    for name, (colour, desc) in LABELS.items():
        r = run(["gh", "label", "create", name, "-R", REPO_SLUG, "--color", colour, "--description", desc, "--force"])
        out.append(f"{name}: {'ok' if not r.returncode else (r.stderr or r.stdout).strip()[:200]}")
    return out


API_CACHE_ENV = "SHEPHERD_API_CACHE"  # #6534: a directory for conditional (ETag) REST reads; unset, reads are plain


PASS_CACHED = re.compile(r"^(user|repos/[^/]+/[^/]+/collaborators/[^/]+/permission)$")


def pass_cached(api: Api) -> Api:
    """One reconcile pass reads the bot's own login and each labeller's permission for EVERY PR, though neither can
    change within the pass: memoise those two reads for the pass (#64, 2026-10-24: the shepherd shares the account's
    5,000/h API quota with the fleet and failed 25 times in a day when it ran out)."""
    memo: dict[str, Any] = {}

    def cached(path: str, *a: Any, **kw: Any) -> Any:
        if not PASS_CACHED.match(path):
            return api(path, *a, **kw)
        if path not in memo:
            memo[path] = api(path, *a, **kw)
        return memo[path]

    return cached


def main(
    argv: list[str] | None = None, api: Api = pr_check.gh_api, run: Run = _run, graphql: pr_check.GraphQL | None = None
) -> int:
    """`graphql`: defaults to `gh api graphql` when `api` is the real gh (a fake api never reaches the real GraphQL)."""
    if api is pr_check.gh_api:
        graphql = graphql or pr_check.gh_graphql
        if os.environ.get(API_CACHE_ENV):
            api = pr_check.conditional_api(Path(os.environ[API_CACHE_ENV]))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("event")
    e.add_argument("--event-path", type=Path, required=True)
    e.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("reconcile")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--head-sha", help="only the PRs whose head is this commit (a workflow_run's head_sha)")
    sub.add_parser("ensure-labels")
    for cmd in (e, r):
        cmd.add_argument("--flake-cache", type=Path, help=f"flake_history.json (default: ${FLAKE_CACHE_ENV})")
    args = ap.parse_args(argv)
    if args.cmd == "ensure-labels":
        lines = ensure_labels(run)
    elif args.cmd == "event":
        number, facts = event_facts(args.event_path)
        lines = process(number, api, run, facts, args.dry_run, flaky=learned_flakes(args.flake_cache), graphql=graphql)
    else:
        lines = []
        api = pass_cached(pr_check.pass_cache(api))  # #6534: plus the finished SHAs' reads
        flaky = learned_flakes(args.flake_cache)  # once per pass
        prs = prs_for_head(api, args.head_sha) if args.head_sha else open_prs(api, graphql)
        tip = ci_digest.main_tip(api, graphql)  # one read of main's tip for both below
        on_main = ci_digest.main_failures(api, graphql=graphql, tip=tip) if len(prs) > 1 else None
        main_state = ci_digest.main_green(api, graphql=graphql, tip=tip)  # #5484: only a reconcile merges main
        prefetched = _graphql_prs(graphql, prs) if graphql else None  # #6534: several PRs per query
        for n in prs:
            lines += process(
                n, api, run, None, args.dry_run, on_main=on_main, flaky=flaky, main=main_state, graphql=graphql,
                prefetched=prefetched,
            )  # fmt: skip
    if os.environ.get(API_CACHE_ENV):
        pr_check.prune_api_store(Path(os.environ[API_CACHE_ENV]))  # #6534: the saved store stays small
    for line in lines:
        print(line)
    return 1 if any("FAILED" in x for x in lines) else 0


if __name__ == "__main__":
    sys.exit(main())
