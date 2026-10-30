"""shepherd_gh (#4847 item 3): the label rules, against decide() and a fake GitHub; plus the workflows' security lint."""

import json
import re
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import det_sweep_plan as dsp  # noqa: E402
import shepherd_gh as sg  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
NOW = 1_000_000.0
SHA = "a" * 40


def snap(**kw):
    """A quiet snapshot: an open, non-draft, clean PR with the merge label, nothing failing, no matrix."""
    s = {"number": 7, "state": "open", "draft": False, "head_sha": SHA, "head_ref": "fix/x", "head_fork": False,
         "mergeable_state": "clean", "auto_merge": False, "labels": [sg.MERGE], "depends_open": [], "matrix": "none",
         "action": None, "event_label": None, "removed": None, "sender": None, "failed": [],
         "pending": 0, "digest_text": "", "digest_posted": False, "now": NOW,
         "label_actors": {x: {"login": "joe", "permission": "admin"} for x in sg.REQUESTS},
         "approved": True, "pending_update": False, "gate_now": ("success", sg.GATE_OK)}  # fmt: skip
    s.update(kw)
    return s


def kinds(acts):
    return [a["op"] for a in acts]


def by_op(acts, op):
    return [a for a in acts if a["op"] == op]


# --- merge, hold, matrix, depends -----------------------------------------------------------------------------------


def test_merge_label_by_writer_marks_ready_and_enables_auto_merge():
    acts = sg.decide(
        snap(draft=True, action="labeled", event_label=sg.MERGE, sender={"login": "joe", "permission": "admin"})
    )
    # #5104: a draft is only marked ready; auto-merge waits until the ready_for_review runs exist, and so does the gate
    assert kinds(acts) == ["ready", "gate"]
    assert by_op(acts, "gate")[0]["state"] == "pending"
    acts = sg.decide(
        snap(draft=False, action="labeled", event_label=sg.MERGE, sender={"login": "joe", "permission": "admin"})
    )
    assert by_op(acts, "automerge")[0] == {"op": "automerge", "on": True, "sha": SHA}


def test_merge_label_by_non_writer_is_removed_with_a_comment_and_nothing_merges():
    acts = sg.decide(
        snap(
            draft=True,
            action="labeled",
            event_label=sg.MERGE,
            sender={"login": "stranger", "permission": "read"},
            labels=[sg.MERGE],
        )
    )
    assert by_op(acts, "unlabel") == [{"op": "unlabel", "label": sg.MERGE}]
    assert "stranger" in by_op(acts, "comment")[0]["body"]
    assert "ready" not in kinds(acts) and "automerge" not in kinds(acts)


def test_non_writer_status_label_is_not_vetted():
    # only the request labels are a maintainer's to set; the bot's status labels are display only
    acts = sg.decide(
        snap(labels=[sg.NEEDS], action="labeled", event_label=sg.NEEDS, sender={"login": "x", "permission": "read"})
    )
    assert "unlabel" not in kinds(acts)


def test_hold_blocks_auto_merge_and_turns_it_off():
    acts = sg.decide(snap(labels=[sg.MERGE, sg.HOLD], auto_merge=True))
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": False}]
    assert "ready" not in kinds(acts)


def test_matrix_keeps_auto_merge_off_until_green_on_this_head():
    acts = sg.decide(snap(labels=[sg.MERGE, sg.MATRIX], matrix="none", draft=True))
    assert "automerge" not in kinds(acts) and "ready" not in kinds(acts)
    assert by_op(acts, "dispatch") == [{"op": "dispatch", "ref": "fix/x"}]
    acts = sg.decide(snap(labels=[sg.MERGE, sg.MATRIX], matrix="running", auto_merge=True))
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": False}]
    assert "dispatch" not in kinds(acts)
    acts = sg.decide(snap(labels=[sg.MERGE, sg.MATRIX], matrix="green"))
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": True, "sha": SHA}]


def test_red_matrix_is_needs_fix_with_the_digest():
    acts = sg.decide(snap(labels=[sg.MERGE, sg.MATRIX], matrix="red", digest_text="matrix failed"))
    assert "automerge" not in kinds(acts)
    assert by_op(acts, "labels")[0]["add"] == [sg.NEEDS]
    assert by_op(acts, "comment")[0]["body"].startswith(f"<!-- shepherd-digest {SHA} -->")


def test_fork_branch_cannot_be_dispatched_so_matrix_waits_for_a_maintainer():
    acts = sg.decide(snap(labels=[sg.MERGE, sg.MATRIX], matrix="fork", head_fork=True))
    assert "dispatch" not in kinds(acts) and "automerge" not in kinds(acts)


def test_depends_on_an_open_pr_blocks_auto_merge():
    acts = sg.decide(snap(depends_open=[6], auto_merge=True))
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": False}]
    assert sg.decide(snap(depends_open=[])) == [{"op": "automerge", "on": True, "sha": SHA}]


def test_a_label_by_a_non_writer_seen_only_in_the_timeline_is_removed():
    # reconcile after a dropped event: no event facts, the timeline names the labeler
    actors = {sg.MERGE: {"login": "rando", "permission": "read"}}
    acts = sg.decide(snap(label_actors=actors, auto_merge=True))
    assert by_op(acts, "unlabel") == [{"op": "unlabel", "label": sg.MERGE}]
    assert "automerge" not in kinds(acts) or by_op(acts, "automerge") == [{"op": "automerge", "on": False}]
    assert "rando" in by_op(acts, "comment")[0]["body"]


def test_a_label_with_no_labeled_event_is_removed():
    acts = sg.decide(snap(label_actors={sg.MERGE: None}))
    assert by_op(acts, "unlabel") == [{"op": "unlabel", "label": sg.MERGE}]


def test_a_bot_update_in_progress_neither_drops_nor_merges():
    acts = sg.decide(snap(approved=False, pending_update=True, auto_merge=True))
    assert "unlabel" not in kinds(acts)
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": False}]


def test_removing_the_merge_label_disables_auto_merge():
    acts = sg.decide(snap(labels=[], auto_merge=True, action="unlabeled", removed=sg.MERGE))
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": False}]


def test_a_pr_without_shepherd_labels_is_left_alone():
    assert sg.decide(snap(labels=[], auto_merge=True)) == []


# --- new commits ----------------------------------------------------------------------------------------------------


def test_new_commits_drop_the_merge_label_so_an_unreviewed_head_never_merges():
    acts = sg.decide(snap(action="synchronize", auto_merge=True, approved=False))
    assert by_op(acts, "unlabel") == [{"op": "unlabel", "label": sg.MERGE}]
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": False}]
    assert "automerge" in kinds(acts) and "ready" not in kinds(acts)


def test_a_dropped_head_goes_back_to_draft_so_only_the_cheap_audits_run_on_it():
    # #6278 item 6: the heavy jobs wait for the label; a draft cannot merge, so no required check is weakened
    acts = sg.decide(snap(action="synchronize", approved=False))
    assert by_op(acts, "draft") == [{"op": "draft", "sha": SHA}]
    assert "cheap audits only" in by_op(acts, "comment")[0]["body"]
    assert "draft" not in kinds(sg.decide(snap(action="synchronize", approved=False, draft=True)))  # already one
    assert "draft" not in kinds(sg.decide(snap(action="synchronize", approved=True)))  # an approved head keeps running
    assert "draft" not in kinds(sg.decide(snap(labels=[sg.REAPPROVE])))  # only the drop itself converts


def test_relabelling_a_dropped_draft_marks_it_ready_so_the_full_set_runs_once():
    acts = sg.decide(snap(draft=True, labels=[sg.MERGE, sg.REAPPROVE], approved=True))
    assert "ready" in kinds(acts) and "draft" not in kinds(acts) and "automerge" not in kinds(acts)


def test_no_infra_rerun_on_a_draft_or_a_head_just_dropped_to_one():
    # a rerun replays the old pull_request event (draft=false) and would start the heavy jobs the draft skips
    for s in (snap(draft=True, failed=[failure("infra")]),
              snap(action="synchronize", approved=False, failed=[failure("infra")])):  # fmt: skip
        acts = sg.decide(s)
        assert "rerun" not in kinds(acts)
    assert by_op(sg.decide(snap(failed=[failure("infra")])), "rerun")  # a ready PR still gets its rerun


def test_apply_draft_converts_then_cancels_only_the_heavy_runs_still_going():
    runs = [
        {"id": 1, "name": "Det Sweep", "status": "in_progress", "path": ".github/workflows/det-sweep.yml"},
        {"id": 2, "name": "Ruff Audit", "status": "in_progress", "path": ".github/workflows/ruff-audit.yml"},
        {"id": 3, "name": "Smoke", "status": "completed", "path": ".github/workflows/smoke-test.yml"},
        {"id": 4, "name": "Ground Truth", "status": "queued", "path": ".github/workflows/mainframe-ground-truth.yml"},
    ]
    cmds = []

    def run(argv):
        cmds.append(argv)
        out = json.dumps({"workflow_runs": runs}) if argv[:2] == ["gh", "api"] else ""
        return subprocess.CompletedProcess(argv, 0, out, "")

    lines = sg.apply(7, snap(), [{"op": "draft", "sha": SHA}], run=run)
    assert cmds[0] == ["gh", "pr", "ready", "7", "-R", sg.REPO_SLUG, "--undo"]
    assert f"head_sha={SHA}&event=pull_request" in cmds[1][2]
    assert [c[3] for c in cmds if c[:3] == ["gh", "run", "cancel"]] == ["1", "4"]
    assert lines[0] == "#7 back to draft: ok" and len(lines) == 3


def test_apply_draft_reports_an_unreadable_run_list():
    def run(argv):
        return subprocess.CompletedProcess(argv, 1 if argv[:2] == ["gh", "api"] else 0, "", "boom")

    lines = sg.apply(7, snap(), [{"op": "draft", "sha": SHA}], run=run)
    assert lines == ["#7 back to draft: ok", f"#7 cancel heavy runs on {SHA[:12]}: FAILED to list runs"]


def test_a_dropped_merge_label_leaves_reapprove_so_the_pr_is_findable():
    acts = sg.decide(snap(action="synchronize", auto_merge=True, approved=False, labels=[sg.MERGE, sg.NEEDS]))
    assert by_op(acts, "labels") == [{"op": "labels", "add": [sg.REAPPROVE], "remove": [sg.NEEDS]}]
    assert sg.REAPPROVE in by_op(acts, "comment")[0]["body"]


def test_reapprove_outlives_the_request_labels_until_merge_comes_back():
    assert "labels" not in kinds(sg.decide(snap(labels=[sg.REAPPROVE])))  # no request label left: it stays
    back = sg.decide(snap(labels=[sg.MERGE, sg.REAPPROVE], approved=True))  # a maintainer re-added the label
    assert by_op(back, "labels") == [{"op": "labels", "add": [], "remove": [sg.REAPPROVE]}]
    assert by_op(back, "automerge") == [{"op": "automerge", "on": True, "sha": SHA}]


def test_hold_or_a_manual_removal_clears_reapprove():
    held = sg.decide(snap(labels=[sg.HOLD, sg.REAPPROVE]))
    assert by_op(held, "labels") == [{"op": "labels", "add": [], "remove": [sg.REAPPROVE]}]
    assert "labels" not in kinds(sg.decide(snap(labels=[])))  # removed by hand: never re-added


def test_the_bot_own_update_branch_keeps_the_label():
    acts = sg.decide(snap(action="synchronize", approved=True))
    assert "unlabel" not in kinds(acts)
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": True, "sha": SHA}]


# --- failures: reruns, digest, status labels, behind ----------------------------------------------------------------


def failure(triage, attempts=0, updated=NOW - 3600, run_id=55, check="muninn"):
    return {"check": check, "triage": triage, "run_id": run_id, "attempts": attempts, "updated_at": updated}


def test_infra_failure_is_rerun_once_the_gap_has_passed():
    acts = sg.decide(snap(failed=[failure("infra")], pending=0))
    assert by_op(acts, "rerun") == [{"op": "rerun", "run_id": 55, "check": "muninn"}]
    assert by_op(acts, "labels")[0]["add"] == [sg.RETRYING]
    assert "comment" not in kinds(acts)


def test_infra_failure_inside_the_gap_waits_without_a_rerun():
    acts = sg.decide(snap(failed=[failure("flake", updated=NOW - 60)]))
    assert "rerun" not in kinds(acts)
    assert by_op(acts, "labels")[0]["add"] == [sg.RETRYING]


def test_infra_failure_waits_without_a_rerun_while_a_newer_run_of_its_workflow_is_live():
    # #6971 / #7026: the rerun would join the per-PR concurrency group and cancel the newer run testing the head
    f = {**failure("infra"), "sibling_live": True}
    acts = sg.decide(snap(failed=[f], pending=0))
    assert "rerun" not in kinds(acts)
    assert by_op(acts, "labels")[0]["add"] == [sg.RETRYING]  # still retrying, not needs-fix
    assert "comment" not in kinds(acts)


def _rerun_api(siblings, run=None):
    run = {"run_attempt": 1, "updated_at": "2026-10-10T19:00:00Z", "workflow_id": 77, "head_branch": "churn/1-x",
           **(run or {})}  # fmt: skip
    seen = []

    def api(path):
        seen.append(path)
        if bare_is(path, "/actions/runs/500"):
            return run
        if bare_is(path, "/actions/workflows/77/runs"):
            return {"workflow_runs": [{"id": 500, "status": "completed"}, *siblings]}
        raise AssertionError(path)

    return api, seen


@pytest.mark.parametrize(
    ("siblings", "live"),
    [
        ([{"id": 501, "status": "in_progress"}], True),
        ([{"id": 501, "status": "queued"}], True),
        ([{"id": 501, "status": "completed"}], False),  # finished: the rerun cancels nothing
        ([], False),
    ],
)
def test_attempts_reports_a_live_sibling_run_of_the_same_workflow_on_the_branch(siblings, live):
    api, seen = _rerun_api(siblings)
    assert sg._attempts(api, 500) == (0, sg._to_epoch("2026-10-10T19:00:00Z"), live)
    assert "branch=churn%2F1-x" in seen[1]


def test_attempts_without_a_workflow_id_asks_nothing_more():
    api, seen = _rerun_api([], run={"workflow_id": None})
    assert sg._attempts(api, 500)[2] is False and len(seen) == 1


def test_infra_failure_after_three_reruns_is_needs_fix_with_one_digest():
    acts = sg.decide(snap(failed=[failure("infra", attempts=3)], digest_text="muninn: rate limit"))
    assert "rerun" not in kinds(acts)
    assert by_op(acts, "labels")[0]["add"] == [sg.NEEDS]
    assert len(by_op(acts, "comment")) == 1


def test_one_digest_comment_per_head():
    acts = sg.decide(snap(failed=[{"check": "det", "triage": "real"}], digest_text="x", digest_posted=True))
    assert "comment" not in kinds(acts)
    assert by_op(sg.decide(snap(failed=[{"check": "det", "triage": "real"}], digest_text="x")), "comment")


def test_failure_on_main_is_waiting_on_main_and_posts_no_digest():
    acts = sg.decide(snap(failed=[{"check": "det", "triage": "main"}]))
    assert "comment" not in kinds(acts)
    assert by_op(acts, "labels")[0] == {"op": "labels", "add": [sg.WAITING], "remove": []}


def test_status_labels_swap_and_stale_ones_go():
    acts = sg.decide(snap(labels=[sg.MERGE, sg.NEEDS, sg.RETRYING], failed=[failure("flake", updated=NOW - 1)]))
    assert by_op(acts, "labels") == [{"op": "labels", "add": [], "remove": [sg.NEEDS]}]


def test_status_labels_clear_when_no_request_label_is_left():
    acts = sg.decide(snap(labels=[sg.NEEDS], failed=[]))
    assert by_op(acts, "labels") == [{"op": "labels", "add": [], "remove": [sg.NEEDS]}]


def test_behind_main_is_never_acted_on_whatever_the_state():
    """#5134 (option A): a push restarts CI, so the bot never updates a branch just because it is behind."""
    for extra in ({}, {"labels": [sg.MERGE, sg.HOLD]}, {"failed": [failure("real")]}, {"auto_merge": True},
                  {"labels": []}):  # fmt: skip
        acts = sg.decide(snap(mergeable_state="behind", **extra))
        assert "update_branch" not in kinds(acts), extra


def test_dirty_pr_gets_the_merge_note_once():
    acts = sg.decide(snap(mergeable_state="dirty", digest_text="merge main"))
    assert by_op(acts, "labels")[0]["add"] == [sg.NEEDS]
    assert by_op(acts, "comment")


def test_closed_pr_only_loses_its_labels_it_was_vetted_on():
    assert sg.decide(snap(state="closed", labels=[sg.MERGE], auto_merge=True)) == []


# --- apply and gather, against a fake gh -----------------------------------------------------------------------------


BOT = "shepherd-bot"


def bot_comment(body, user=BOT):
    return {"body": body, "user": {"login": user}}


class Gh:
    """A fake `gh api` (for pr_check / ci_digest / gather) and a recorder for the gh commands apply() runs."""

    def __init__(self):
        self.pr = {
            "number": 7,
            "state": "open",
            "merged": False,
            "draft": False,
            "auto_merge": None,
            "head": {"sha": SHA, "ref": "fix/x", "repo": {"full_name": "squid-protocol/gitgalaxy"}},
            "labels": [{"name": sg.MERGE}],
            "body": "Depends on #6",
            "mergeable_state": "clean",
            "base": {"ref": "main"},
        }
        self.calls, self.cmds, self.gql = [], [], []
        self.perm = "write"
        self.me = BOT  # the account `gh api user` reads
        self.matrix_runs = []
        self.dep_state = "closed"
        # the timeline: who added each label
        self.events = [
            {"event": "labeled", "label": {"name": x}, "actor": {"login": "joe"}, "created_at": "2026-10-10T19:00:00Z"}
            for x in (sg.MERGE, sg.MATRIX)
        ]
        # the bot's own comments: the approval marker of the labelled head, written by the bot's account (BOT)
        self.comments = [bot_comment(f"<!-- shepherd:approved sha={SHA} by=joe -->")]
        self.parents = {}  # commit sha -> parent shas
        self.compare = {}  # (base, head) -> the compare response; an absent pair is an unreadable compare
        self.pushed_at = "2026-10-10T19:59:00Z"  # when the head became the head (its first check suite)
        url = f"https://github.com/{sg.REPO_SLUG}/actions/runs/9/job/1"
        self.runs = [{"id": 1, "name": "smoke", "status": "completed", "conclusion": "success", "html_url": url,
                      "details_url": url, "app": {"slug": "github-actions"}}]  # fmt: skip
        self.statuses = []
        self.more_open = False  # the open-PR listing has a second page
        self.main_runs = []  # the check runs on main's tip (MAIN)

    def api(self, path):
        self.calls.append(path)
        bare = path.split("?")[0]
        if path == "user":
            return {"login": self.me}
        if bare.endswith("/pulls") and "state=open" in path:
            return [self.pr] if "page=1" in path else []
        if bare.endswith("/commits/main"):
            return {"sha": MAIN, "parents": [{"sha": x} for x in self.parents.get(MAIN, [])]}
        if bare.endswith(f"/commits/{MAIN}/check-runs"):
            return {"check_runs": self.main_runs}
        if re.search(r"/commits/[0-9a-f]{40}/pulls$", bare):
            return [self.pr]
        if re.fullmatch(r"repos/[^/]+/[^/]+/commits/[0-9a-f]{40}", bare):
            return {"parents": [{"sha": x} for x in self.parents.get(bare.rsplit("/", 1)[1], [])]}
        if m := re.search(r"/compare/([^/]+)\.\.\.([0-9a-f]{40})$", bare):
            if (m[1], m[2]) not in self.compare:
                raise SystemExit("gh api compare failed")
            return self.compare[(m[1], m[2])]
        if bare.endswith(("/pulls/7", "/pulls/8")):
            return self.pr
        if bare.endswith("/pulls/6"):
            return {"state": self.dep_state}
        if "/check-runs" in path:
            return {"check_runs": self.runs}
        if bare.endswith("/status"):
            return {"statuses": self.statuses}
        if bare.endswith("/check-suites"):
            return {"check_suites": [{"created_at": self.pushed_at}] if self.pushed_at else []}
        if bare.endswith("/events"):
            return self.events
        if bare.endswith("/comments"):
            return self.comments
        if bare.endswith("/permission"):
            return {"permission": self.perm}
        if "/workflows/" in path:
            return {"workflow_runs": self.matrix_runs}
        raise AssertionError(f"unexpected API path {path}")

    def graphql(self, query, variables):
        """The same state as the REST fake, answered as the query asks (#6534): one PR, a batch (`p<N>` aliases), the
        open labelled PRs, or main's tip."""
        self.gql.append(variables)
        if query == sg.PR_QUERY:
            assert variables["n"] == 7
            return self._wrap(self._pull())
        if query == sg.LABELLED_QUERY:
            nodes = [{"number": 7, "labels": {"totalCount": len(self.pr["labels"]), "nodes": self.pr["labels"]}}]
            return {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": self.more_open}, "nodes": nodes}}}
        if query == sg.ci_digest.MAIN_QUERY:
            return {"repository": {"ref": {"target": self._tip()}}}
        nums = [int(x) for x in re.findall(r"p(\d+): pullRequest", query)]
        assert query == sg.batch_query(nums)
        return {"repository": {f"p{n}": {**self._pull(), "number": n} for n in nums}}

    def _tip(self):
        """main's tip as the main query answers it: the runs of `main_runs`, one suite per app."""
        suites = {}
        for r in self.main_runs:
            suites.setdefault(r["app"]["slug"], []).append({
                "databaseId": r["id"], "name": r["name"], "status": r["status"].upper(),
                "conclusion": r["conclusion"].upper() if r["conclusion"] else None,
                "detailsUrl": r["details_url"], "url": r["html_url"],
            })  # fmt: skip
        nodes = [{"createdAt": None, "app": {"slug": k}, "checkRuns": {"totalCount": len(v), "nodes": v}}
                 for k, v in suites.items()]  # fmt: skip
        return {"oid": MAIN, "parents": {"nodes": [{"oid": x} for x in self.parents.get(MAIN, [])]},
                "checkSuites": {"totalCount": len(nodes), "nodes": nodes}}  # fmt: skip

    @staticmethod
    def _wrap(pull):
        return {"rateLimit": {"cost": 1}, "repository": {"pullRequest": pull}}

    def _pull(self):
        pr = self.pr

        def who(login):
            return {"__typename": "Bot", "login": login[:-5]} if login.endswith("[bot]") else {"__typename": "User",
                                                                                                "login": login}  # fmt: skip

        def conn(nodes, count="totalCount"):
            return {count: len(nodes), "nodes": nodes}

        suites = {}
        for r in self.runs:
            suites.setdefault(r["app"]["slug"], []).append({
                "databaseId": r["id"], "name": r["name"], "status": r["status"].upper(),
                "conclusion": r["conclusion"].upper() if r["conclusion"] else None,
                "detailsUrl": r["details_url"], "url": r["html_url"],
            })  # fmt: skip
        suites = [{"createdAt": self.pushed_at, "app": {"slug": k}, "checkRuns": conn(v)} for k, v in suites.items()]
        if not suites and self.pushed_at:
            suites = [{"createdAt": self.pushed_at, "app": {"slug": "github-actions"}, "checkRuns": conn([])}]
        head_repo = pr["head"].get("repo")
        return {
            **{
                "number": pr["number"], "state": "OPEN" if pr["state"] == "open" else "CLOSED",
                "merged": pr["merged"], "isDraft": pr["draft"], "body": pr["body"],
                "mergeStateStatus": pr["mergeable_state"].upper(), "headRefOid": pr["head"]["sha"],
                "headRefName": pr["head"]["ref"], "baseRefName": pr["base"]["ref"],
                "headRepository": {"nameWithOwner": head_repo["full_name"]} if head_repo else None,
                "autoMergeRequest": pr["auto_merge"],
                "labels": conn([{"name": x["name"]} for x in pr["labels"]]),
                "comments": conn([{"author": who(c["user"]["login"]), "body": c["body"]} for c in self.comments]),
                "timelineItems": conn([
                    {"actor": who(e["actor"]["login"]), "createdAt": e.get("created_at"), "label": e["label"]}
                    for e in self.events if e["event"] == "labeled"
                ], "filteredCount"),
                "commits": {"nodes": [{"commit": {
                    "oid": pr["head"]["sha"],
                    "status": {"contexts": [{"context": x["context"], "state": x["state"].upper(),
                                             "description": x.get("description")}
                                            for x in self.statuses]} if self.statuses else None,
                    "checkSuites": conn(suites),
                }}]},
            }
        }  # fmt: skip

    def run(self, argv):
        self.cmds.append(argv)
        if len(argv) > 2 and "/statuses/" in argv[2]:  # a commit status the module posted: the next read sees it
            f = dict(a.split("=", 1) for a in argv[3:] if "=" in a)
            self.statuses = [x for x in self.statuses if x["context"] != f["context"]] + [
                {"context": f["context"], "state": f["state"], "description": f["description"]}
            ]
        for arg in argv:  # a comment the module posted: the bot's account wrote it
            if arg.startswith("body="):
                self.comments.append(bot_comment(arg[len("body=") :]))
        out = "d" * 40 if "-q" in argv else ""
        return subprocess.CompletedProcess(argv, 0, out, "")


def no_gate(lines):
    """The log lines without the ci-gate status posts (#6919), for tests about the labels and auto-merge."""
    return [x for x in lines if f"#7 {sg.GATE} " not in x]


def merged_by(gh):
    return any(c[:3] == ["gh", "pr", "merge"] and "--auto" in c for c in gh.cmds)


def test_reconcile_after_an_unapproved_push_drops_the_label_and_never_merges():
    # no synchronize event was seen: the head moved from the labelled commit (A) to B with no bot marker
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "b" * 40
    gh.parents = {"b" * 40: ["a" * 40, "c" * 40]}  # the marker names A; B came from nowhere the bot knows
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines)
    ready = [c for c in gh.cmds if c[:3] == ["gh", "pr", "ready"]]
    assert not merged_by(gh) and ready == [["gh", "pr", "ready", "7", "-R", sg.REPO_SLUG, "--undo"]]  # back to draft


def test_reconcile_keeps_the_label_through_the_bot_update_branch():
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "b" * 40
    gh.parents = {"b" * 40: [SHA, "c" * 40]}  # the bot's merge of main on the labelled head
    gh.comments.append(bot_comment(f"<!-- shepherd-update from={SHA} to={'b' * 40} -->"))
    lines = sg.process(7, gh.api, gh.run, None)
    assert not any("unlabel" in x for x in lines)
    assert merged_by(gh)


def test_a_push_after_the_bot_update_is_not_carried():
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "d" * 40  # a force-push: a merge commit on the approved head, not the bot's
    gh.parents = {"d" * 40: [SHA, "c" * 40]}
    gh.comments.append(bot_comment(f"<!-- shepherd-update from={SHA} to={'b' * 40} -->"))
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)


def test_a_bot_update_without_its_result_marker_is_pending_not_approved():
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "b" * 40
    gh.comments.append(bot_comment(f"<!-- shepherd-update from={SHA} -->"))
    lines = sg.process(7, gh.api, gh.run, None)
    assert not any("unlabel" in x for x in lines) and not merged_by(gh)


def test_approval_comes_from_the_labeled_event_payload_head():
    gh = Gh()
    gh.dep_state = "closed"
    gh.comments = []  # the labeled run has not approved anything yet
    lines = sg.process(7, gh.api, gh.run, {"action": "labeled", "label": sg.MERGE, "sender": "joe", "head": SHA})
    assert lines[0].startswith("#7 approval marker for aaaaaaaaaaaa: ok")
    assert any(f"shepherd:approved sha={SHA} by=joe" in c["body"] for c in gh.comments)
    assert merged_by(gh)


def test_the_approval_this_pass_wrote_counts_even_before_the_api_returns_it():
    """Seen on #4854: the comment list read right after the marker's POST did not hold it yet, so the newest marker
    read back was the previous head's and the label was dropped as unapproved."""
    gh = Gh()
    gh.dep_state = "closed"
    old = "c" * 40
    gh.comments = [bot_comment(f"<!-- shepherd:approved sha={old} by=joe -->")]  # an earlier head's approval
    visible = list(gh.comments)
    real_run = gh.run

    def lagging_run(argv):  # the POST lands, but the next read of the comments does not show it yet
        r = real_run(argv)
        gh.comments, gh.posted = visible, gh.comments
        return r

    lines = sg.process(7, gh.api, lagging_run, {"action": "labeled", "label": sg.MERGE, "sender": "joe", "head": SHA})
    assert lines[0].startswith("#7 approval marker for aaaaaaaaaaaa: ok")
    assert merged_by(gh) and not any("label was removed" in ln for ln in lines)


def test_a_marker_written_by_someone_else_is_ignored():
    gh = Gh()
    gh.dep_state = "closed"
    gh.comments = [bot_comment(f"<!-- shepherd:approved sha={SHA} by=joe -->", user="mallory")]
    lines = sg.process(7, gh.api, gh.run, None)  # the label predates the head, and mallory's marker counts for nothing
    assert not merged_by(gh) and any("unlabel shepherd:merge" in x for x in lines)


def test_no_marker_yet_is_quiet_no_drop_no_merge():
    gh = Gh()
    gh.dep_state = "closed"
    gh.comments = []
    gh.pushed_at = None  # #4854: only an unknown push (or label) time leaves it undecided
    lines = no_gate(sg.process(7, gh.api, gh.run, None))
    assert not any("unlabel" in x for x in lines) and not merged_by(gh)
    assert lines == ["#7 shepherd:merge: awaiting approval marker; re-add the label to approve (no action)"]
    assert not any(c[:3] == ["gh", "api", f"repos/{sg.REPO_SLUG}/issues/7/labels/shepherd%3Amerge"] for c in gh.cmds)


def test_reconcile_drops_a_label_added_by_a_non_writer_in_the_timeline():
    gh = Gh()
    gh.dep_state = "closed"
    gh.events = [{"event": "labeled", "label": {"name": sg.MERGE}, "actor": {"login": "rando"}}]
    gh.perm = "read"
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)


# --- the learned-flake set (#5398) ----------------------------------------------------------------------------------


def _cache(tmp_path, rescues=3, failed=0):
    path = tmp_path / "flake_history.json"
    path.write_text(json.dumps({"repo": sg.REPO_SLUG, "days": {"2026-10-17": {"det-db2 (1)": [rescues, failed, {}]}}}))
    return path


def test_learned_flakes_reads_the_cache_and_never_scans(tmp_path):
    assert sg.learned_flakes(_cache(tmp_path)) == {"det-db2 (1)"}
    assert sg.learned_flakes(_cache(tmp_path, rescues=1)) == set()  # too few rescues to learn
    assert sg.learned_flakes(tmp_path / "missing.json") == set()  # no cache, no flakes
    (tmp_path / "bad.json").write_text("{not json")
    assert sg.learned_flakes(tmp_path / "bad.json") == set()


def test_learned_flakes_default_comes_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv(sg.FLAKE_CACHE_ENV, str(_cache(tmp_path)))
    assert sg.learned_flakes() == {"det-db2 (1)"}


def _failing_api(gh, attempt):
    """gh's API with one failed, github-actions check `det-db2 (1)` (run 500, job 600) on run attempt `attempt`."""
    url = f"https://github.com/{sg.REPO_SLUG}/actions/runs/500/job/600"
    run = {"id": 1, "name": "det-db2 (1)", "status": "completed", "conclusion": "failure", "html_url": url,
           "details_url": url, "app": {"slug": "github-actions"}}  # fmt: skip

    def api(path):
        if "/check-runs" in path:
            return {"check_runs": [run]}
        if bare_is(path, "/actions/jobs/600"):
            return {"run_attempt": attempt}
        if bare_is(path, "/actions/runs/500"):
            return {"run_attempt": attempt, "updated_at": "2026-10-10T19:00:00Z"}
        return gh.api(path)

    return api


def bare_is(path, tail):
    return path.split("?")[0].endswith(tail)


@pytest.mark.parametrize(
    ("attempt", "flaky", "triage"),
    [
        (1, {"det-db2 (1)"}, "flake"),  # a learned flake's first failure gets its rerun
        (2, {"det-db2 (1)"}, "real"),  # failed again on the rerun: a fixer's
        (1, {"other"}, "real"),  # not learned
        (1, None, "real"),  # no cache
    ],
)
def test_a_learned_flaky_checks_first_failure_is_triaged_flake_in_the_reconcile_path(
    monkeypatch, attempt, flaky, triage
):
    real = sg.ci_digest.digest  # the real triage, with the log fetch and main's failures stubbed out
    monkeypatch.setattr(
        sg.ci_digest, "digest",
        lambda n, api, on_main=None, flaky=None, **kw: real(n, api, logs=lambda _id: "Error: boom\n", on_main=set(), flaky=flaky, **kw),
    )  # fmt: skip
    gh = Gh()
    gh.dep_state = "closed"
    s = sg.gather(7, _failing_api(gh, attempt), None, now=NOW, flaky=flaky)
    assert [f["triage"] for f in s["failed"]] == [triage]


def test_main_computes_the_learned_set_once_per_pass(monkeypatch, tmp_path):
    gh = Gh()
    got = []
    monkeypatch.setattr(sg, "open_prs", lambda api, *a: [7, 8])
    monkeypatch.setattr(sg.ci_digest, "main_tip", lambda api, graphql=None: None)
    monkeypatch.setattr(sg, "_graphql_prs", lambda graphql, numbers: {})
    monkeypatch.setattr(sg.ci_digest, "main_failures", lambda api, **k: set())
    monkeypatch.setattr(sg.ci_digest, "main_green", lambda api, **k: ("", set()))
    monkeypatch.setattr(
        sg,
        "process",
        lambda n, api, run, event, dry, on_main=None, flaky=None, main=None, **kw: got.append(flaky) or [],
    )
    calls = []
    monkeypatch.setattr(sg, "learned_flakes", lambda path=None: calls.append(path) or {"x"})
    sg.main(["reconcile", "--flake-cache", str(tmp_path / "c.json")], api=gh.api, run=gh.run)
    assert calls == [tmp_path / "c.json"] and got == [{"x"}, {"x"}]


def test_prs_for_head_selects_the_open_labelled_pr_of_that_commit():
    gh = Gh()
    assert sg.prs_for_head(gh.api, "e" * 40) == [7]
    with pytest.raises(SystemExit):
        sg.prs_for_head(gh.api, "not-a-sha")


def test_gather_and_process_for_a_labelled_event_marks_ready_and_enables_auto_merge():
    # #5104: a draft's heavy checks are skipped (green); the first pass only marks it ready, the next enables auto-merge
    gh = Gh()
    gh.pr["draft"] = True
    gh.dep_state = "closed"  # #6 merged: no block
    lines = no_gate(sg.process(7, gh.api, gh.run, {"action": "labeled", "label": sg.MERGE, "sender": "joe"}))
    assert lines == ["#7 ready for review: ok"]
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in gh.cmds)
    gh.pr["draft"] = False  # what `gh pr ready` did
    gh.cmds.clear()
    lines = no_gate(sg.process(7, gh.api, gh.run, None))
    assert lines == ["#7 auto-merge on: ok"]
    assert not any(c[:3] == ["gh", "pr", "ready"] for c in gh.cmds)
    merge = next(c for c in gh.cmds if c[:3] == ["gh", "pr", "merge"])
    assert "--auto" in merge and "--match-head-commit" in merge and merge[merge.index("--match-head-commit") + 1] == SHA
    assert f"repos/squid-protocol/gitgalaxy/collaborators/joe/permission" in gh.calls


def test_gather_blocks_on_an_open_dependency_and_on_a_read_only_labeler():
    gh = Gh()
    gh.dep_state = "open"
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in sg.process(7, gh.api, gh.run, {"action": "synchronize"}))
    gh = Gh()
    gh.perm = "read"
    lines = sg.process(7, gh.api, gh.run, {"action": "labeled", "label": sg.MERGE, "sender": "rando"})
    assert any("unlabel" in x for x in lines)
    assert not any(c[:3] == ["gh", "pr", "ready"] for c in gh.cmds)


def test_gather_reads_the_matrix_on_the_head_and_dispatches_only_when_none_ran():
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["labels"] = [{"name": sg.MERGE}, {"name": sg.MATRIX}]
    sg.process(7, gh.api, gh.run, {"action": "labeled", "label": sg.MATRIX, "sender": "joe"})
    assert ["gh", "workflow", "run", sg.MATRIX_WORKFLOW, "-R", sg.REPO_SLUG, "--ref", "fix/x"] in gh.cmds
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in gh.cmds)
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["labels"] = [{"name": sg.MERGE}, {"name": sg.MATRIX}]
    gh.matrix_runs = [{"event": "workflow_dispatch", "status": "completed", "conclusion": "success", "html_url": "u"}]
    sg.process(7, gh.api, gh.run, {"action": "labeled", "label": sg.MATRIX, "sender": "joe"})
    assert not any(c[:2] == ["gh", "workflow"] for c in gh.cmds)
    assert any(c[:3] == ["gh", "pr", "merge"] and "--auto" in c for c in gh.cmds)


def test_apply_has_no_update_branch_op_any_more():
    cmds = []

    def run(argv):
        cmds.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    sg.apply(7, snap(mergeable_state="behind", head_sha="b" * 40), [{"op": "update_branch"}], run=run)
    assert cmds == []


def test_event_facts_read_the_payload_as_data(tmp_path):
    p = tmp_path / "event.json"
    p.write_text(
        json.dumps(
            {
                "action": "labeled",
                "pull_request": {"number": 7},
                "label": {"name": "shepherd:merge"},
                "sender": {"login": "joe"},
            }
        )
    )
    assert sg.event_facts(p) == (7, {"action": "labeled", "before": None, "label": "shepherd:merge", "sender": "joe"})
    p.write_text(
        json.dumps(
            {"action": "synchronize", "pull_request": {"number": 7}, "before": "c" * 40, "sender": {"login": "a b; rm"}}
        )
    )
    assert "sender" not in sg.event_facts(p)[1]  # a login that is not a GitHub login is not used


def test_failed_gh_call_is_reported_not_raised():
    s = snap()
    lines = sg.apply(7, s, [{"op": "ready"}], run=lambda argv: subprocess.CompletedProcess(argv, 1, "", "boom"))
    assert lines == ["#7 ready for review: FAILED: boom"]


def test_rerun_refused_already_running_is_logged_as_skipped():
    s = snap()

    def run_already_running(argv):
        return subprocess.CompletedProcess(argv, 1, "", "The workflow run is already running.")

    lines = sg.apply(7, s, [{"op": "rerun", "run_id": 55, "check": "muninn"}], run=run_already_running)
    assert lines == ["#7 rerun muninn (run 55): skipped (already running)"]


def test_rerun_refused_already_running_in_stdout_is_logged_as_skipped():
    s = snap()

    def run_already_running(argv):
        return subprocess.CompletedProcess(argv, 1, "HTTP 409: already running\n", "")

    lines = sg.apply(7, s, [{"op": "rerun", "run_id": 55, "check": "muninn"}], run=run_already_running)
    assert lines == ["#7 rerun muninn (run 55): skipped (already running)"]


def test_rerun_failure_other_error_is_logged_as_failed():
    s = snap()

    def run_failed(argv):
        return subprocess.CompletedProcess(argv, 1, "", "HTTP 500: Internal Server Error")

    lines = sg.apply(7, s, [{"op": "rerun", "run_id": 55, "check": "muninn"}], run=run_failed)
    assert lines == ["#7 rerun muninn (run 55): FAILED: HTTP 500: Internal Server Error"]


def test_rerun_det_refused_already_running_is_logged_as_skipped():
    s = snap()

    def run_dispatch(argv):
        if argv[:3] == ["gh", "run", "list"]:
            return subprocess.CompletedProcess(argv, 0, "42\n", "")
        if argv[:3] == ["gh", "run", "rerun"]:
            return subprocess.CompletedProcess(argv, 1, "", "workflow run is already running")
        return subprocess.CompletedProcess(argv, 0, "", "")

    lines = sg.apply(7, s, [{"op": "rerun_det", "sha": SHA}], run=run_dispatch)
    assert lines == [f"#7 rerun {sg.DET_WORKFLOW} (run 42) for {sg.FULL}: skipped (already running)"]


def test_rerun_det_failure_other_error_is_logged_as_failed():
    s = snap()

    def run_dispatch(argv):
        if argv[:3] == ["gh", "run", "list"]:
            return subprocess.CompletedProcess(argv, 0, "42\n", "")
        if argv[:3] == ["gh", "run", "rerun"]:
            return subprocess.CompletedProcess(argv, 1, "", "HTTP 404: Not Found")
        return subprocess.CompletedProcess(argv, 0, "", "")

    lines = sg.apply(7, s, [{"op": "rerun_det", "sha": SHA}], run=run_dispatch)
    assert lines == [f"#7 rerun {sg.DET_WORKFLOW} (run 42) for {sg.FULL}: FAILED: HTTP 404: Not Found"]


def test_reconcile_exit_code_zero_when_rerun_skipped_already_running(monkeypatch):
    monkeypatch.setattr(sg, "open_prs", lambda api, *a: [7])
    monkeypatch.setattr(sg.ci_digest, "main_tip", lambda api, graphql=None: None)
    monkeypatch.setattr(sg, "_graphql_prs", lambda graphql, numbers: {})
    monkeypatch.setattr(
        sg, "process", lambda n, api, run, ev, dry_run, **kw: ["#7 rerun muninn (run 55): skipped (already running)"]
    )
    assert sg.main(["reconcile"]) == 0


def test_reconcile_exit_code_one_when_action_failed(monkeypatch):
    monkeypatch.setattr(sg, "open_prs", lambda api, *a: [7])
    monkeypatch.setattr(sg.ci_digest, "main_tip", lambda api, graphql=None: None)
    monkeypatch.setattr(sg, "_graphql_prs", lambda graphql, numbers: {})
    monkeypatch.setattr(
        sg, "process", lambda n, api, run, ev, dry_run, **kw: ["#7 rerun muninn (run 55): FAILED: server error"]
    )
    assert sg.main(["reconcile"]) == 1


# --- #6534: gather() through one GraphQL query, the pass cache, conditional REST ----------------------------------------

PER_PR_READS = ("/pulls/7", "/issues/7/comments", "/issues/7/events", "/check-runs", "/status", "/check-suites")


def _failing(gh):
    url = f"https://github.com/{sg.REPO_SLUG}/actions/runs/500/job/600"
    gh.runs = [{"id": 2, "name": "det-db2 (1)", "status": "completed", "conclusion": "failure", "html_url": url,
                "details_url": url, "app": {"slug": "github-actions"}}]  # fmt: skip


def _set(**kw):
    return lambda gh: [setattr(gh, k, v) for k, v in kw.items()]


def _pr(**kw):
    return lambda gh: gh.pr.update(kw)


STATES = {
    "approved head": lambda gh: None,
    "non-writer labeller": lambda gh: _set(
        perm="read",
        events=[
            {
                "event": "labeled",
                "label": {"name": sg.MERGE},
                "actor": {"login": "rando"},
                "created_at": "2026-10-10T19:00:00Z",
            }
        ],
    )(gh),
    "unapproved push": lambda gh: (gh.pr["head"].update(sha="b" * 40), _set(parents={"b" * 40: [SHA, "c" * 40]})(gh)),
    "bot update carried": lambda gh: (
        gh.pr["head"].update(sha="b" * 40),
        _set(parents={"b" * 40: [SHA, "c" * 40]})(gh),
        gh.comments.append(bot_comment(f"<!-- shepherd-update from={SHA} to={'b' * 40} -->")),
    ),
    "bot update pending": lambda gh: (
        gh.pr["head"].update(sha="b" * 40),
        gh.comments.append(bot_comment(f"<!-- shepherd-update from={SHA} -->")),
    ),
    "app-account comment": lambda gh: gh.comments.append(bot_comment("hi", user="github-actions[bot]")),
    "bot is an app account": lambda gh: _set(
        me="github-actions[bot]",
        comments=[bot_comment(f"<!-- shepherd:approved sha={SHA} by=joe -->", user="github-actions[bot]")],
    )(gh),
    "failing check": _failing,
    "failing check also failing on main": _failing,  # with on_main below
    "pending check": lambda gh: gh.runs.append(
        {**gh.runs[0], "id": 3, "name": "slow", "status": "in_progress", "conclusion": None}
    ),
    "failing status": _set(statuses=[{"context": "ci/legacy", "state": "failure"}]),
    "pending status": _set(statuses=[{"context": "ci/legacy", "state": "pending"}]),
    "dirty": _pr(mergeable_state="dirty"),
    "draft": _pr(draft=True),
    "auto-merge on": _pr(auto_merge={"enabledAt": "2026-10-10T19:00:00Z"}),
    "fork": lambda gh: gh.pr["head"].update(repo={"full_name": "someone/gitgalaxy"}),
    "deleted head repo": lambda gh: gh.pr["head"].update(repo=None),
    "no labels": _pr(labels=[]),
    "hold": _pr(labels=[{"name": sg.MERGE}, {"name": sg.HOLD}]),
    "closed": _pr(state="closed"),
    "merged": _pr(state="closed", merged=True),
    "no check suites": _set(runs=[], pushed_at=None),
    "no push time": _set(pushed_at=None, comments=[]),
}


@pytest.fixture
def stub_logs(monkeypatch):
    real = sg.ci_digest.digest
    monkeypatch.setattr(
        sg.ci_digest, "digest", lambda n, api, **kw: real(n, api, logs=lambda _id: "Error: boom\n", **kw)
    )


@pytest.mark.parametrize("state", sorted(STATES))
def test_gather_reads_the_same_snapshot_through_graphql_and_decides_the_same(state, stub_logs):
    def snapshot(graphql):
        gh = Gh()
        STATES[state](gh)
        on_main = {"det-db2 (1)"} if "on main" in state else set()
        main = ("f" * 40, set())
        return gh, sg.gather(
            7, gh.api, None, now=NOW, on_main=on_main, flaky=set(), main=main, graphql=graphql and gh.graphql
        )

    _, rest = snapshot(False)
    gh, via = snapshot(True)
    assert via == rest and sg.decide(via) == sg.decide(rest)
    assert len(gh.gql) == 1 and f"repos/{sg.REPO_SLUG}/pulls/7" not in gh.calls  # it did read through GraphQL


def test_the_graphql_path_makes_none_of_the_per_pr_rest_reads():
    gh = Gh()
    sg.gather(7, gh.api, None, now=NOW, on_main=set(), flaky=set(), graphql=gh.graphql)
    assert len(gh.gql) == 1
    assert not [p for p in gh.calls if any(r in p.split("?")[0] for r in PER_PR_READS)]
    rest = Gh()
    sg.gather(7, rest.api, None, now=NOW, on_main=set(), flaky=set())
    assert {r for r in PER_PR_READS for p in rest.calls if r in p} == set(PER_PR_READS)


def _cut(conn):
    def edit(doc):
        c = doc["repository"]["pullRequest"]
        for k in conn[:-1]:
            c = c[k]
        c[conn[-1]] = 1000  # more on GitHub than came back

    return edit


def _fail(doc):
    raise SystemExit("gh api graphql failed")


@pytest.mark.parametrize(
    "edit",
    [
        _cut(("comments", "totalCount")),
        _cut(("timelineItems", "filteredCount")),
        _cut(("labels", "totalCount")),
        _fail,
        lambda doc: doc["repository"].update(pullRequest=None),
        lambda doc: doc["repository"].update(pullRequest={"number": 7}),
    ],
    ids=["comments cut", "timeline cut", "labels cut", "gh fails", "no pull", "fields missing"],
)
def test_an_incomplete_or_failed_query_reads_the_pr_through_rest(edit):
    gh = Gh()

    def broken(q, v):
        doc = gh.graphql(q, v)
        edit(doc)
        return doc

    s = sg.gather(7, gh.api, None, now=NOW, on_main=set(), flaky=set(), graphql=broken)
    assert f"repos/{sg.REPO_SLUG}/pulls/7" in gh.calls
    assert s == sg.gather(7, Gh().api, None, now=NOW, on_main=set(), flaky=set())


def test_cut_check_runs_and_a_moved_head_read_through_rest():
    gh = Gh()
    doc = gh.graphql(sg.PR_QUERY, {"n": 7})
    doc["repository"]["pullRequest"]["commits"]["nodes"][0]["commit"]["checkSuites"]["nodes"][0]["checkRuns"][
        "totalCount"
    ] = 101
    assert sg._graphql_pr(lambda q, v: doc, 7) is None
    doc = gh.graphql(sg.PR_QUERY, {"n": 7})
    doc["repository"]["pullRequest"]["commits"]["nodes"][0]["commit"]["oid"] = "e" * 40
    assert sg._graphql_pr(lambda q, v: doc, 7) is None


def test_an_unknown_merge_state_is_read_through_rest_so_a_dirty_pr_is_not_missed():
    gh = Gh()
    doc = gh.graphql(sg.PR_QUERY, {"n": 7})
    doc["repository"]["pullRequest"]["mergeStateStatus"] = "UNKNOWN"
    gh.pr["mergeable_state"] = "dirty"
    s = sg.gather(7, gh.api, None, now=NOW, on_main=set(), flaky=set(), graphql=lambda q, v: doc)
    assert s["mergeable_state"] == "dirty"
    assert [p for p in gh.calls if "/issues/7/comments" in p or "/check-runs" in p] == []  # the rest came from GraphQL


def test_a_reconcile_pass_reads_each_pr_with_one_query(monkeypatch):
    def reads(graphql):
        gh = Gh()
        monkeypatch.setattr(sg, "open_prs", lambda api, *a: [7, 7, 7])
        monkeypatch.setattr(sg.ci_digest, "main_tip", lambda api, graphql=None: None)
        monkeypatch.setattr(sg.ci_digest, "main_failures", lambda api, **k: set())
        monkeypatch.setattr(sg.ci_digest, "main_green", lambda api, **k: ("f" * 40, set()))
        sg.main(["reconcile", "--dry-run"], api=gh.api, run=gh.run, graphql=graphql and gh.graphql)
        return gh

    before, after = reads(None), reads(True)
    assert len(after.gql) == 1 and len(after.calls) < len(before.calls) - 3 * 5
    assert not [p for p in after.calls if any(r in p.split("?")[0] for r in PER_PR_READS)]


def test_a_batch_reads_several_prs_per_query_and_gather_gives_the_rest_dict():
    gh = Gh()
    nums = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    got = sg._graphql_prs(gh.graphql, nums)
    assert set(got) == set(nums) and len(gh.gql) == 3  # 5 + 5 + 2 PRs per query
    assert [g["pr"]["number"] for g in got.values()] == nums
    rest = sg.gather(7, Gh().api, None, now=NOW, on_main=set(), flaky=set())
    s = sg.gather(7, gh.api, None, now=NOW, on_main=set(), flaky=set(), prefetched=got)
    assert s == rest and sg.decide(s) == sg.decide(rest)
    assert not [p for p in gh.calls if any(r in p.split("?")[0] for r in PER_PR_READS)]


@pytest.mark.parametrize(
    "edit",
    [
        lambda doc, n: doc.pop(f"p{n}"),
        lambda doc, n: doc.update({f"p{n}": None}),
        lambda doc, n: doc[f"p{n}"]["comments"].update(totalCount=1000),
        lambda doc, n: doc[f"p{n}"]["labels"].update(totalCount=1000),
        lambda doc, n: doc[f"p{n}"].pop("commits"),
    ],
    ids=["missing", "null", "comments cut", "labels cut", "fields missing"],
)
def test_a_pr_cut_short_in_a_batch_alone_reads_through_rest(edit):
    gh = Gh()

    def broken(q, v):
        doc = gh.graphql(q, v)
        edit(doc["repository"], 8)
        return doc

    got = sg._graphql_prs(broken, [7, 8])
    assert got[7] is not None and got[8] is None
    s = sg.gather(8, gh.api, None, now=NOW, on_main=set(), flaky=set(), prefetched=got)
    assert f"repos/{sg.REPO_SLUG}/pulls/8" in gh.calls and s["number"] == 8


def test_a_failed_batch_maps_every_pr_to_rest():
    def fail(q, v):
        raise SystemExit("gh api graphql failed")

    assert sg._graphql_prs(fail, [7, 8, 9]) == {7: None, 8: None, 9: None}


def test_a_pr_the_batch_answered_none_is_not_asked_again_by_gather():
    gh = Gh()
    sg.gather(7, gh.api, None, now=NOW, on_main=set(), flaky=set(), graphql=gh.graphql, prefetched={7: None})
    assert gh.gql == [] and f"repos/{sg.REPO_SLUG}/pulls/7" in gh.calls


def test_open_labelled_reads_one_query_and_matches_rest():
    gh = Gh()
    assert sg.open_labelled(gh.api, gh.graphql) == sg.open_labelled(Gh().api) == [7]
    assert len(gh.gql) == 1 and not [p for p in gh.calls if "pulls?state=open" in p]
    gh.pr["labels"] = [{"name": "bug"}]  # no request or status label: not a shepherd PR
    assert sg.open_labelled(gh.api, gh.graphql) == []


def test_open_labelled_falls_back_to_rest_when_the_listing_is_cut_or_fails():
    gh = Gh()
    gh.more_open = True
    assert sg.open_labelled(gh.api, gh.graphql) == [7] and any("pulls?state=open" in p for p in gh.calls)
    gh = Gh()

    def label_cut(q, v):
        doc = gh.graphql(q, v)
        doc["repository"]["pullRequests"]["nodes"][0]["labels"]["totalCount"] = 1000
        return doc

    assert sg.open_labelled(gh.api, label_cut) == [7] and any("pulls?state=open" in p for p in gh.calls)

    def fail(q, v):
        raise SystemExit("x")

    assert sg.open_labelled(gh.api, fail) == [7]


def test_a_whole_reconcile_pass_reads_its_listing_main_and_prs_through_graphql():
    def pass_over(graphql):
        gh = Gh()
        gh.main_runs = [dict(gh.runs[0], id=5, name="det"), dict(gh.runs[0], id=6, name="ruff", conclusion="failure")]
        sg.main(["reconcile", "--dry-run"], api=gh.api, run=gh.run, graphql=graphql and gh.graphql)
        return gh

    rest, gql = pass_over(None), pass_over(True)
    assert len(gql.gql) == 3  # the listing, main's tip, one batch
    for gone in ("pulls?state=open", "commits/main", f"commits/{MAIN}/check-runs"):
        assert not [p for p in gql.calls if gone in p] and [p for p in rest.calls if gone in p]
    assert len(gql.calls) < len(rest.calls) - 6


def test_pass_cache_shares_only_what_this_pass_cannot_see_change():
    base = f"repos/{sg.REPO_SLUG}"
    docs = {
        f"{base}/commits/{SHA}": {"parents": []},
        f"{base}/commits/{SHA}/check-runs?per_page=100&page=1": {"check_runs": [{"status": "completed"}]},
        f"{base}/commits/{'b' * 40}/check-runs?per_page=100&page=1": {"check_runs": [{"status": "in_progress"}]},
        f"{base}/actions/runs/5": {"status": "completed"},
        f"{base}/actions/runs/6": {"status": "queued"},
        f"{base}/pulls/7": {"state": "open"},
    }
    calls = []
    api = sg.pr_check.pass_cache(lambda p: calls.append(p) or docs[p])
    for p in [*docs, *docs]:
        assert api(p) == docs[p]
    assert sorted(calls) == sorted([*docs, *[p for p in docs if "b" * 40 in p or "runs/6" in p or "pulls" in p]])


def test_conditional_api_sends_the_kept_etag_and_a_304_returns_the_kept_body(tmp_path):
    argvs = []

    def run(argv):
        argvs.append(argv)
        if 'If-None-Match: W/"e1"' in argv:
            return subprocess.CompletedProcess(argv, 1, 'HTTP/2.0 304 Not Modified\nEtag: W/"e1"\n\n', "")
        return subprocess.CompletedProcess(argv, 0, 'HTTP/2.0 200 OK\r\nETag: W/"e1"\r\n\r\n{"n": 1}', "")

    api = sg.pr_check.conditional_api(tmp_path / "store", run)
    assert api("repos/x/y/pulls/1") == {"n": 1} and "-H" not in argvs[0]
    assert api("repos/x/y/pulls/1") == {"n": 1} and argvs[1][3:5] == ["-H", 'If-None-Match: W/"e1"']
    fail = sg.pr_check.conditional_api(tmp_path / "other", lambda a: subprocess.CompletedProcess(a, 1, "", "HTTP 404"))
    with pytest.raises(SystemExit):
        fail("repos/x/y/pulls/2")


def test_a_restored_store_serves_the_next_pass_by_304_and_survives_bad_entries(tmp_path):
    store = tmp_path / "store"
    seen = []

    def run(argv):
        seen.append("304" if "-H" in argv else "200")
        if "-H" in argv:
            return subprocess.CompletedProcess(argv, 1, 'HTTP/2.0 304 Not Modified\nETag: "a"\n\n', "")
        return subprocess.CompletedProcess(argv, 0, 'HTTP/2.0 200 OK\nETag: "a"\n\n[1]', "")

    assert sg.pr_check.conditional_api(store, run)("repos/x/y/pulls/1") == [1]  # pass 1: cold
    assert sg.pr_check.conditional_api(store, run)("repos/x/y/pulls/1") == [1]  # pass 2: a restored store
    assert seen == ["200", "304"] and not list(store.glob("*.tmp"))
    (entry,) = store.glob("*.json")
    for bad in ("{torn", '{"body": [1]}', "[]"):  # corrupt, no etag, wrong shape: a plain read
        entry.write_text(bad, encoding="utf-8")
        assert sg.pr_check.conditional_api(store, run)("repos/x/y/pulls/1") == [1]
        assert seen[-1] == "200"
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")  # an unwritable store (a file, not a dir): still a plain read
    assert sg.pr_check.conditional_api(blocker / "s", run)("repos/x/y/pulls/1") == [1]


def test_prune_api_store_drops_old_temp_and_excess_entries(tmp_path):
    for i in range(4):
        (tmp_path / f"{i}.json").write_text("{}", encoding="utf-8")
        os.utime(tmp_path / f"{i}.json", (1000 + i, 1000 + i))
    (tmp_path / "x.tmp").write_text("{", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("", encoding="utf-8")
    assert sg.pr_check.prune_api_store(tmp_path, max_age_s=100, max_entries=2, now=1102.5) == 4
    assert sorted(p.name for p in tmp_path.iterdir()) == ["3.json", "keep.txt"]  # 2.json is >100 s old, 0/1 too
    assert sg.pr_check.prune_api_store(tmp_path / "missing") == 0


def test_digest_reuses_the_pr_and_check_runs_it_is_given():
    gh = Gh()
    _failing(gh)
    sg.ci_digest.digest(7, gh.api, logs=lambda _id: "", on_main=set(), flaky=set(), pr=gh.pr, runs=gh.runs)
    assert not [p for p in gh.calls if "/pulls/7" in p or "/check-runs" in p]


# --- labels and the det planner -------------------------------------------------------------------------------------


def test_labels_are_described_with_a_pointer_to_the_guide_and_fit_github():
    assert set(sg.LABELS) == set(sg.REQUESTS) | set(sg.STATUS)
    for name, (colour, desc) in sg.LABELS.items():
        assert len(desc) <= 100 and sg.DOCS in desc, name
        assert len(colour) == 6


def test_shepherd_full_label_plans_a_full_det_sweep():
    cases = {"alpha": {"port_from": None}}
    narrow = dsp.plan(["tests/equivalence/alpha/case.json"], "pull_request", cases, [])
    assert narrow["mode"] == "narrow"
    full = dsp.plan(["tests/equivalence/alpha/case.json"], "pull_request", cases, [sg.FULL])
    assert (full["mode"], full["cases"]) == ("full", "all")


def test_labels_from_event_reads_the_pull_request_labels(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"pull_request": {"labels": [{"name": "shepherd:full"}, {"name": "docs"}]}}))
    assert dsp.labels_from_event(p) == ["shepherd:full", "docs"]
    assert dsp.labels_from_event(tmp_path / "missing.json") == []


# --- the workflows: the security rules, as a lint -------------------------------------------------------------------

WORKFLOWS = [REPO / ".github" / "workflows" / n for n in ("shepherd-event.yml", "shepherd-reconcile.yml")]


def _steps(doc):
    for job in doc["jobs"].values():
        yield from job.get("steps", [])


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_shepherd_workflow_follows_the_security_rules(path):
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    on = doc.get(True, doc.get("on"))
    assert "pull_request" not in on, "the PAT must never run for a fork's pull_request"
    assert doc["permissions"] == {}, "top-level permissions are empty; each job grants its own"
    for step in _steps(doc):
        run = step.get("run", "")
        assert "${{" not in run, f"{path.name}: no expression reaches a run: script ({step.get('name')})"
        uses = step.get("uses", "")
        if uses:
            assert "@" in uses and len(uses.split("@", 1)[1].split()[0]) == 40, f"{uses} is not pinned to a SHA"
        if uses.startswith("actions/checkout"):
            ref = str(step.get("with", {}).get("ref", ""))
            assert ref == "main", "a shepherd job checks out main only"
            assert step["with"].get("persist-credentials") is False
    if "pull_request_target" in on:
        assert set(on["pull_request_target"]["types"]) <= {"labeled", "unlabeled", "synchronize"}


def test_shepherd_full_by_a_writer_reruns_the_det_sweep_and_status_labels_do_not():
    """#4854: det-sweep no longer runs on label events (the shepherd's own status labels had cancelled the required
    `det` sweep, over and over); a maintainer's shepherd:full reruns the latest sweep, whose plan reads it live."""
    acts = sg.decide(
        snap(labels=[sg.FULL], action="labeled", event_label=sg.FULL, sender={"login": "joe", "permission": "admin"})
    )
    assert by_op(acts, "rerun_det") == [{"op": "rerun_det", "sha": SHA}]
    acts = sg.decide(
        snap(labels=[sg.FULL], action="labeled", event_label=sg.FULL, sender={"login": "x", "permission": "read"})
    )
    assert not by_op(acts, "rerun_det")  # a non-writer's label is removed, nothing reruns
    assert not by_op(sg.decide(snap(labels=[sg.RETRYING], action="labeled", event_label=sg.RETRYING)), "rerun_det")


def test_det_sweep_does_not_run_on_label_events_and_reads_labels_live():
    wf = (Path(__file__).resolve().parents[2] / ".github/workflows/det-sweep.yml").read_text(encoding="utf-8")
    types = re.search(r"types: \[([^\]]*)\]", wf).group(1)
    assert "labeled" not in types and "unlabeled" not in types
    assert '--labels "$labels"' in wf and "issues/$PR/labels" in wf


def test_plan_labels_option_overrides_the_event(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dsp, "case_dirs", lambda: {"alpha": {"port_from": None}})
    monkeypatch.setattr(
        sys,
        "argv",
        ["det_sweep_plan.py", "--files", "tests/equivalence/alpha/case.json", "--labels", "docs,shepherd:full"],
    )
    dsp.main()
    assert json.loads(capsys.readouterr().out)["mode"] == "full"


# --- level-triggered approval (#4854: events are dropped and reordered) -----------------------------------------------

OLD = "c" * 40


def _relabelled(gh, labelled_at):
    """The head moved after an earlier approval (OLD); a writer's shepherd:merge was (re)added at `labelled_at`."""
    gh.dep_state = "closed"
    gh.comments = [bot_comment(f"<!-- shepherd:approved sha={OLD} by=joe -->")]
    gh.events = [
        {"event": "labeled", "label": {"name": sg.MERGE}, "actor": {"login": "joe"}, "created_at": labelled_at}
    ]


def test_a_label_added_after_the_push_approves_the_head_whichever_event_runs():
    """#4854: the label was added while the slow synchronize pass was still running; that pass (and any later one,
    the labeled event's own run having been dropped) must approve the new head, not remove the label."""
    for event in (None, {"action": "synchronize"}, {"action": "unlabeled", "label": sg.RETRYING}):
        gh = Gh()
        _relabelled(gh, "2026-10-10T20:00:52Z")
        lines = sg.process(7, gh.api, gh.run, event)
        assert merged_by(gh), (event, lines)
        assert any(f"shepherd:approved sha={SHA} by=joe" in c["body"] for c in gh.comments)  # recorded
        assert not any("label was removed" in ln for ln in lines)


def test_a_label_from_before_the_push_does_not_approve_the_new_head():
    gh = Gh()
    _relabelled(gh, "2026-10-10T19:58:00Z")  # before pushed_at: it approved the previous head
    lines = sg.process(7, gh.api, gh.run, None)
    assert not merged_by(gh) and any("unlabel shepherd:merge" in ln for ln in lines), lines


def test_an_unknown_push_time_decides_nothing():
    gh = Gh()
    _relabelled(gh, "2026-10-10T20:00:52Z")
    gh.pushed_at = None  # the check suites could not be read
    lines = sg.process(7, gh.api, gh.run, None)
    assert not merged_by(gh) and not any("unlabel shepherd:merge" in ln for ln in lines), lines


def test_a_non_writers_label_after_the_push_approves_nothing():
    gh = Gh()
    _relabelled(gh, "2026-10-10T20:00:52Z")
    gh.perm = "read"
    sg.process(7, gh.api, gh.run, None)
    assert not merged_by(gh) and not any(f"sha={SHA}" in c["body"] for c in gh.comments)


def test_the_event_workflow_has_no_concurrency_group():
    wf = (Path(__file__).resolve().parents[2] / ".github/workflows/shepherd-event.yml").read_text(encoding="utf-8")
    assert not re.search(r"^concurrency:", wf, re.M)  # a group keeps one pending run and cancels the rest


def test_reconcile_triggers_on_the_required_checks_workflows_and_the_matrix_only():
    # #4935: 25 workflow_run triggers made 204 runs a day (63% cancelled or skipped); a pass on any other workflow
    # changes nothing the next required check's pass (or the cron) would not do
    yaml = pytest.importorskip("yaml")
    wf_dir = REPO / ".github" / "workflows"
    names = {}
    for f in wf_dir.glob("*.yml"):
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        for job_id, job in (doc.get("jobs") or {}).items():
            for ctx in (job_id, job.get("name")):
                if ctx in sg.REQUIRED_CHECKS:
                    names.setdefault(ctx, set()).add(doc["name"])
    assert set(names) == set(sg.REQUIRED_CHECKS), f"no workflow defines {set(sg.REQUIRED_CHECKS) - set(names)}"
    matrix = yaml.safe_load((wf_dir / sg.MATRIX_WORKFLOW).read_text(encoding="utf-8"))["name"]
    rec = yaml.safe_load((wf_dir / "shepherd-reconcile.yml").read_text(encoding="utf-8"))
    on = rec.get("on", rec.get(True))
    # #6919: plus the slow gated workflows, so the ci-gate status turns green when they finish, not at the next cron
    gated = set().union(*names.values()) | {matrix} | set(sg.GATE_TRIGGERS)
    assert set(on["workflow_run"]["workflows"]) == gated
    titles = {yaml.safe_load(f.read_text(encoding="utf-8")).get("name") for f in wf_dir.glob("*.yml")}
    assert set(sg.GATE_TRIGGERS) <= titles, "a GATE_TRIGGERS entry names no workflow"
    assert on["workflow_run"]["branches-ignore"] == ["main"]
    assert "schedule" in on  # the cron still covers every other check and the rerun gap


def test_every_reconcile_pass_covers_all_labelled_prs():
    # a cancelled pending pass (one pending run per concurrency group) must not drop a PR until the cron
    rec = (REPO / ".github" / "workflows" / "shepherd-reconcile.yml").read_text(encoding="utf-8")
    assert "--head-sha" not in rec


def _merge_of_main(gh, files_merge, files_main, files_pr=(("pr.py", "modified", "p1"),), main_status="behind"):
    """A PR whose approved head is SHA and whose new head B is a merge of main commit M into it."""
    b, m = "b" * 40, "e" * 40
    gh.pr["head"]["sha"] = b
    gh.parents = {b: [SHA, m]}
    f = lambda rows: {"files": [{"filename": n, "status": s, "sha": h} for n, s, h in rows]}  # noqa: E731
    gh.compare = {
        ("main", m): {"status": main_status},
        (SHA, b): f(files_merge),
        (SHA, m): f(files_main),
        (m, SHA): f(files_pr),
    }


def test_a_clean_merge_of_main_keeps_the_approval_and_the_label():
    gh = Gh()
    main_change = (("lib.py", "modified", "m1"),)
    _merge_of_main(gh, main_change, main_change)
    lines = sg.process(7, gh.api, gh.run, None)
    assert not any("unlabel" in x for x in lines)
    assert not any(sg.REAPPROVE in " ".join(c) for c in gh.cmds)
    assert any("approval marker for bbbbbbbbbbbb" in x for x in lines)
    assert merged_by(gh)


def test_a_merge_of_main_with_extra_changes_goes_to_reapproval():
    gh = Gh()
    _merge_of_main(gh, (("lib.py", "modified", "m1"), ("evil.py", "added", "x1")), (("lib.py", "modified", "m1"),))
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)
    assert any(sg.REAPPROVE in " ".join(c) for c in gh.cmds)


def test_a_merge_that_resolved_a_conflict_in_a_file_the_pr_changed_goes_to_reapproval():
    gh = Gh()
    same = (("pr.py", "modified", "m1"),)
    _merge_of_main(gh, same, same)  # main and the PR both touch pr.py: not a plain merge we can judge
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)


def test_a_merge_whose_other_parent_is_not_on_main_goes_to_reapproval():
    gh = Gh()
    same = (("lib.py", "modified", "m1"),)
    _merge_of_main(gh, same, same, main_status="diverged")
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)


def test_an_unreadable_compare_falls_back_to_reapproval():
    gh = Gh()
    same = (("lib.py", "modified", "m1"),)
    _merge_of_main(gh, same, same)
    del gh.compare[(SHA, "e" * 40)]
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)


def test_an_ordinary_new_commit_goes_to_reapproval():
    gh = Gh()
    gh.pr["head"]["sha"] = "b" * 40
    gh.parents = {"b" * 40: [SHA]}  # one parent: a plain commit on the approved head
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)
    assert any(sg.REAPPROVE in " ".join(c) for c in gh.cmds)


def test_failed_matrix_legs_of_one_run_get_one_rerun():
    legs = [failure("infra", check="muninn (1/2)"), failure("infra", check="muninn (2/2)")]
    acts = sg.decide(snap(failed=legs, pending=0))
    assert by_op(acts, "rerun") == [{"op": "rerun", "run_id": 55, "check": "muninn (1/2)"}]


# --- #5398: the learned-flake cache in the workflows ------------------------------------------------------------------

CACHE_FILE = "flake-cache/flake_history.json"


def _workflow(name):
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((REPO / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    return doc, list(_steps(doc))


@pytest.mark.parametrize("name", ["shepherd-event.yml", "shepherd-reconcile.yml"])
def test_the_shepherd_workflows_restore_the_flake_cache_and_pass_it(name):
    doc, steps = _workflow(name)
    restore = [
        s
        for s in steps
        if s.get("uses", "").startswith("actions/cache/restore@") and s["with"]["path"] == "flake-cache"
    ]
    assert len(restore) == 1
    w = restore[0]["with"]
    assert w["key"] == "flake-history-${{ github.run_id }}" and w["restore-keys"].strip() == "flake-history-"
    assert w["path"] == "flake-cache"
    shepherd = [s for s in steps if "shepherd_gh.py" in s.get("run", "") and "ensure-labels" not in s["run"]]
    assert len(shepherd) == 1 and f"--flake-cache {CACHE_FILE}" in shepherd[0]["run"]
    assert steps.index(restore[0]) < steps.index(shepherd[0])


def test_only_the_flake_history_workflow_refreshes_and_saves_the_cache():
    """2026-10-20: a workflow_run reconcile pass gets a read-only cache token, so a refresh there was never saved and
    every pass refetched for 12 min. The scheduled flake-history.yml (own group) is the one writer."""
    _, steps = _workflow("shepherd-reconcile.yml")
    assert not [s for s in steps if "cache/save" in s.get("uses", "") and s["with"]["path"] == "flake-cache"]
    assert not [s for s in steps if "--refresh-only" in s.get("run", "")]
    doc, steps = _workflow("flake-history.yml")
    assert doc["concurrency"]["group"] == "flake-history" and doc["concurrency"]["cancel-in-progress"] is False
    assert "schedule" in doc[True] and "workflow_dispatch" in doc[True]  # yaml reads `on:` as True
    restore = [s for s in steps if s.get("uses", "").startswith("actions/cache/restore@")]
    refresh = [s for s in steps if "--refresh-only" in s.get("run", "")]
    save = [s for s in steps if s.get("uses", "").startswith("actions/cache/save@")]
    assert len(restore) == len(refresh) == len(save) == 1
    assert steps.index(restore[0]) < steps.index(refresh[0]) < steps.index(save[0])
    r = refresh[0]
    assert f"--cache {CACHE_FILE}" in r["run"]
    budget = int(r["run"].split("--budget-s ")[1].split()[0])
    assert budget + 4 * 60 <= r["timeout-minutes"] * 60  # the day in flight (~2 min) ends before the step's timeout
    job = next(iter(doc["jobs"].values()))
    assert job["timeout-minutes"] > r["timeout-minutes"]
    assert save[0]["with"]["key"] == "flake-history-${{ github.run_id }}" and save[0]["with"]["path"] == "flake-cache"
    assert save[0]["if"].startswith("always()")


def test_the_event_workflow_only_restores_the_flake_cache():
    # short job, no concurrency group: overlapping saves/refreshes would collide, flake-history.yml owns the cache
    _, steps = _workflow("shepherd-event.yml")
    assert not [s for s in steps if "cache/save" in s.get("uses", "") or "--refresh-only" in s.get("run", "")]


# --- #6534: the conditional-read store (SHEPHERD_API_CACHE) in the workflows -------------------------------------------


@pytest.mark.parametrize("name", ["shepherd-event.yml", "shepherd-reconcile.yml"])
def test_the_shepherd_workflows_restore_the_api_cache_before_the_pass(name):
    _, steps = _workflow(name)
    restore = [
        s for s in steps if s.get("uses", "").startswith("actions/cache/restore@") and s["with"]["path"] == "api-cache"
    ]
    assert len(restore) == 1
    assert restore[0]["with"]["key"] == "shepherd-api-${{ github.run_id }}"
    assert restore[0]["with"]["restore-keys"].strip() == "shepherd-api-"
    shepherd = [s for s in steps if "shepherd_gh.py" in s.get("run", "") and "ensure-labels" not in s["run"]]
    assert len(shepherd) == 1 and shepherd[0]["env"]["SHEPHERD_API_CACHE"] == "api-cache"
    assert steps.index(restore[0]) < steps.index(shepherd[0])


def test_only_a_pass_whose_token_can_write_saves_the_api_cache():
    """A workflow_run token is read-only for the cache: the save is skipped there and the cron / dispatch passes write."""
    _, steps = _workflow("shepherd-reconcile.yml")
    save = [s for s in steps if s.get("uses", "").startswith("actions/cache/save@")]
    assert len(save) == 1 and save[0]["with"]["path"] == "api-cache"
    assert save[0]["with"]["key"] == "shepherd-api-${{ github.run_id }}"
    assert "github.event_name != 'workflow_run'" in save[0]["if"] and save[0]["if"].startswith("always()")
    shepherd = [s for s in steps if "shepherd_gh.py" in s.get("run", "") and "ensure-labels" not in s["run"]]
    assert steps.index(shepherd[0]) < steps.index(save[0])
    _, steps = _workflow("shepherd-event.yml")
    assert not [s for s in steps if s.get("uses", "").startswith("actions/cache/save@")]


# --- #5484: main turned green under a PR that was waiting on it ------------------------------------------------------

MAIN = "9" * 40


def waiting(**kw):
    """A PR waiting on main whose `det` failure now triages real, main being green on det and the head lacking main."""
    base = {"labels": [sg.MERGE, sg.WAITING], "failed": [{"check": "det", "triage": "real"}], "main_sha": MAIN,
            "main_green": ["det", "full-suite"], "contains_main": False, "main_merged": False}  # fmt: skip
    base.update(kw)
    return snap(**base)


def test_main_still_red_waits_without_an_update():  # (a)
    acts = sg.decide(waiting(failed=[{"check": "det", "triage": "main"}], main_green=[]))
    assert "update_main" not in kinds(acts) and "comment" not in kinds(acts)
    assert "labels" not in kinds(acts)  # waiting-on-main already there


def test_main_green_and_head_predates_the_fix_merges_main_and_keeps_waiting():  # (b)
    acts = sg.decide(waiting())
    assert by_op(acts, "update_main") == [{"op": "update_main", "sha": SHA, "main": MAIN}]
    assert "comment" not in kinds(acts) and "labels" not in kinds(acts)


def test_matrix_suffix_of_a_check_name_still_matches_main_green():
    acts = sg.decide(waiting(failed=[{"check": "full-suite (ubuntu, 3.11)", "triage": "real"}]))
    assert by_op(acts, "update_main")


def test_after_the_update_the_same_check_failing_is_needs_fix():  # (c)
    acts = sg.decide(waiting(contains_main=True, main_merged=True, digest_text="det failed"))
    assert "update_main" not in kinds(acts)
    assert by_op(acts, "labels")[0] == {"op": "labels", "add": [sg.NEEDS], "remove": [sg.WAITING]}
    assert len(by_op(acts, "comment")) == 1


def test_a_conflicting_waiting_pr_gets_no_update_and_needs_fix():  # (d)
    acts = sg.decide(waiting(mergeable_state="dirty"))
    assert "update_main" not in kinds(acts)
    assert sg.NEEDS in by_op(acts, "labels")[0]["add"]


def test_a_pr_only_behind_main_with_no_main_failure_is_not_updated():  # (e)
    for extra in ({}, {"labels": [sg.MERGE, sg.WAITING]}, {"failed": [failure("real")]}):
        acts = sg.decide(
            snap(mergeable_state="behind", main_sha=MAIN, main_green=["det"], contains_main=False, **extra)
        )
        assert "update_main" not in kinds(acts), extra


def test_a_real_failure_on_a_pr_that_was_not_waiting_is_not_reinterpreted():
    acts = sg.decide(waiting(labels=[sg.MERGE]))
    assert "update_main" not in kinds(acts)
    assert sg.NEEDS in by_op(acts, "labels")[0]["add"]


def test_a_check_not_green_on_main_stays_real():
    acts = sg.decide(waiting(main_green=["full-suite"]))
    assert "update_main" not in kinds(acts)
    assert sg.NEEDS in by_op(acts, "labels")[0]["add"]


def test_no_update_for_hold_fork_or_a_main_already_merged_once():
    for extra in ({"labels": [sg.MERGE, sg.WAITING, sg.HOLD]}, {"head_fork": True}, {"main_merged": True}):
        assert "update_main" not in kinds(sg.decide(waiting(**extra))), extra


def test_a_pass_without_a_main_snapshot_never_updates():
    s = waiting()
    for k in ("main_sha", "main_green", "contains_main", "main_merged"):
        del s[k]
    assert "update_main" not in kinds(sg.decide(s))


def test_waiting_is_kept_while_the_head_with_the_fix_is_still_being_tested():
    for extra in ({"pending": 3}, {"no_checks": True}):
        acts = sg.decide(waiting(failed=[], contains_main=True, main_merged=True, **extra))
        assert "labels" not in kinds(acts), extra
    acts = sg.decide(waiting(failed=[], contains_main=True, main_merged=True))  # its run finished green
    assert by_op(acts, "labels")[0] == {"op": "labels", "add": [], "remove": [sg.WAITING]}


def test_apply_merges_main_with_a_marker_pair_and_one_log_line():
    gh = Gh()
    log = sg.apply(7, snap(), [{"op": "update_main", "sha": SHA, "main": MAIN}], run=gh.run)
    assert [c for c in gh.cmds if "PUT" in c][0][-2:] == ["-f", f"expected_head_sha={SHA}"]
    bodies = [c[-1] for c in gh.cmds if c[-1].startswith("body=")]
    assert f"<!-- shepherd-main-merge main={MAIN} -->" in bodies[0] and f"from={SHA} -->" in bodies[0]
    assert bodies[1] == f"body=<!-- shepherd-update from={SHA} to={'d' * 40} -->"
    assert log == [f"#7 merged main {MAIN[:12]} into {SHA[:12]} -> {'d' * 12}"]


def test_apply_failed_update_closes_the_marker_pair_and_reports():
    gh = Gh()
    run = lambda argv: (  # noqa: E731
        subprocess.CompletedProcess(argv, 1, "", "conflict") if "PUT" in argv else gh.run(argv)
    )
    log = sg.apply(7, snap(), [{"op": "update_main", "sha": SHA, "main": MAIN}], run=run)
    assert "FAILED" in log[0] and "conflict" in log[0]
    assert gh.cmds[-1][-1] == f"body=<!-- shepherd-update from={SHA} to={SHA} -->"


def _waiting_gh(gh, compare_status):
    gh.pr["labels"] = [{"name": sg.MERGE}, {"name": sg.WAITING}]
    gh.compare[(MAIN, SHA)] = {"status": compare_status}


def test_gather_reads_whether_the_head_has_main_and_whether_it_was_merged_once():
    gh = Gh()
    _waiting_gh(gh, "diverged")
    s = sg.gather(7, gh.api, main=(MAIN, {"det"}))
    assert (s["main_sha"], s["main_green"], s["contains_main"], s["main_merged"]) == (MAIN, ["det"], False, False)
    gh.comments.append(bot_comment(f"<!-- shepherd-main-merge main={MAIN} -->"))
    assert sg.gather(7, gh.api, main=(MAIN, {"det"}))["main_merged"] is True
    gh.compare[(MAIN, SHA)] = {"status": "ahead"}
    assert sg.gather(7, gh.api, main=(MAIN, {"det"}))["contains_main"] is True
    assert "main_sha" not in sg.gather(7, gh.api)  # an event pass has no main snapshot


def test_the_bot_main_merge_keeps_the_merge_label_approval():
    gh = Gh()
    _waiting_gh(gh, "behind")
    new = "d" * 40
    gh.parents[new] = [SHA, MAIN]
    gh.pr["head"]["sha"] = new
    gh.comments.append(bot_comment(f"<!-- shepherd-update from={SHA} to={new} -->"))
    s = sg.gather(7, gh.api, main=(MAIN, {"det"}))
    assert s["carried"] and s["approved"]
    assert not any(a["op"] == "unlabel" and a["label"] == sg.MERGE for a in sg.decide(s))


def test_main_green_lists_the_checks_green_on_main_s_tip(monkeypatch):
    import ci_digest

    def check(name, conclusion):
        return {
            "id": 1,
            "name": name,
            "status": "completed",
            "conclusion": conclusion,
            "app": {"slug": "github-actions"},
        }

    def api(path):
        if path.endswith("/commits/main"):
            return {"sha": MAIN}
        return {"check_runs": [check("det", "success"), check("ruff-audit", "failure"), check("mypy-audit", None)]}

    sha, green = ci_digest.main_green(api)
    assert sha == MAIN and "det" in green and "ruff-audit" not in green
    assert ci_digest.main_green(lambda p: (_ for _ in ()).throw(SystemExit("x"))) == ("", set())


# --- #6061: a permanent auto-merge refusal (the #5950 sequence) ----------------------------------------------------

REFUSAL = (
    "GraphQL: Pull request refusing to allow a Personal Access Token to create or update workflow "
    "`.github/workflows/det-sweep.yml` without `workflow` scope (enablePullRequestAutoMerge)"
)


def _replay(passes, own_red):
    """Run decide + apply for each pass against a fake PR whose labels and calls are recorded; auto-merge is refused."""
    labels, calls = [sg.MERGE], []

    def run(argv):
        calls.append(argv)
        if argv[:3] == ["gh", "pr", "merge"]:
            return subprocess.CompletedProcess(argv, 1, "", REFUSAL)
        if "POST" in argv and any(x.startswith("labels[]=") for x in argv):
            labels.extend(x.split("=", 1)[1] for x in argv if x.startswith("labels[]="))
        return subprocess.CompletedProcess(argv, 0, "", "")

    logs = []
    for _ in range(passes):
        # after the first pass the shepherd's own run is red on the head: it reads as a real failure
        failed = [failure("real", check="shepherd")] if own_red and len(calls) else []
        s = snap(labels=list(labels), failed=failed, digest_posted=True)
        logs += sg.apply(7, s, sg.decide(s), run=run)
    return labels, calls, logs


def test_a_permanent_refusal_is_labelled_once_commented_once_and_not_a_failure():
    labels, calls, logs = _replay(1, own_red=False)
    assert labels == [sg.MERGE, sg.OWNER]
    comments = [c for c in calls if any("/comments" in x for x in c)]
    assert len(comments) == 1 and "AUTOMATION_PAT" in " ".join(comments[0])
    assert not any("FAILED" in x for x in logs)


def test_the_5950_sequence_has_no_label_churn_and_no_retry_after_the_refusal():
    labels, calls, logs = _replay(6, own_red=True)
    merges = [c for c in calls if c[:3] == ["gh", "pr", "merge"]]
    assert len(merges) == 1  # never retried while the owner status is set
    assert not any(c for c in calls if "DELETE" in c)  # no status label removed...
    assert labels == [sg.MERGE, sg.OWNER]  # ...and needs-fix never added
    api = [c for c in calls if c[:2] == ["gh", "api"] and "/statuses/" not in c[2]]
    assert len(api) == 2  # one label add, one comment: nothing else, in 6 passes
    assert len([c for c in calls if c[:2] == ["gh", "api"] and "/statuses/" in c[2]]) <= 1  # the gate, once
    assert not any("FAILED" in x for x in logs)


def test_another_apply_failure_is_still_reported_failed():
    run = lambda argv: subprocess.CompletedProcess(argv, 1, "", "HTTP 502 bad gateway")  # noqa: E731
    acts = [{"op": "automerge", "on": True, "sha": SHA}]
    assert "FAILED" in sg.apply(7, snap(), acts, run=run)[0]


def test_the_owner_status_goes_when_the_merge_request_goes():
    acts = sg.decide(snap(labels=[sg.OWNER]))
    assert by_op(acts, "labels") == [{"op": "labels", "add": [], "remove": [sg.OWNER]}]


def test_reconcile_pass_reads_the_bot_login_and_each_permission_once():
    """#64: the shepherd shares the account's 5,000/h API quota; a pass re-read both for every PR."""
    calls = []

    def api(path, *a, **kw):
        calls.append(path)
        return {"login": "bot", "permission": "write", "number": len(calls)}

    cached = sg.pass_cached(api)
    perm = f"repos/{sg.REPO_SLUG}/collaborators/alice/permission"
    for _ in range(3):
        assert cached("user")["login"] == "bot"
        assert cached(perm)["permission"] == "write"
        cached(f"repos/{sg.REPO_SLUG}/pulls/7")
    assert calls.count("user") == 1 and calls.count(perm) == 1
    assert calls.count(f"repos/{sg.REPO_SLUG}/pulls/7") == 3  # everything else is read fresh


def test_trusted_bots_come_from_the_workflow_then_the_tokens_own_account(monkeypatch):
    """promoter-bot#64: under the squid-shepherd App the token cannot read `user`; its markers come from
    squid-shepherd[bot], and the PAT account's markers on open PRs must keep counting during the switch."""

    def no_user(path, *a, **kw):
        raise SystemExit("user: Resource not accessible by integration")

    monkeypatch.setenv(sg.TRUSTED_BOTS_ENV, "squid-shepherd[bot], squid-protocol")
    assert sg.trusted_bots(no_user) == {"squid-shepherd[bot]", "squid-protocol"}
    monkeypatch.delenv(sg.TRUSTED_BOTS_ENV)
    assert sg.trusted_bots(lambda path, *a, **kw: {"login": "squid-protocol"}) == {
        "squid-protocol"
    }  # the PAT, as before
    assert sg.trusted_bots(no_user) == set()  # nothing trusted: no marker counts (never everyone)


# --- ci-gate and auto-merge on red (#6919) ----------------------------------------------------------------------------


def gate_of(acts):
    got = by_op(acts, "gate")
    return (got[0]["state"], got[0]["description"]) if got else None


def test_a_red_path_filtered_check_turns_auto_merge_off_and_fails_the_gate():
    """#6881/#6894/#6895 merged with DOOM-rosetta red: only the required checks held the merge."""
    acts = sg.decide(snap(auto_merge=True, failed=[failure("real", check="shard 2 (1666363 LOC)")]))
    assert by_op(acts, "automerge") == [{"op": "automerge", "on": False}]
    assert gate_of(acts) == ("failure", "failing: shard 2")
    acts = sg.decide(snap(failed=[failure("real", check="call-graph-accuracy-audit")]))
    assert "automerge" not in kinds(acts)  # never turned on while red


def test_the_shepherd_own_red_run_neither_blocks_nor_fails_the_gate():
    acts = sg.decide(snap(failed=[failure("real", check="shepherd (label event)")]))
    assert by_op(acts, "automerge")[0]["on"] is True and gate_of(acts) is None


def test_the_gate_posts_only_when_it_changes():
    assert gate_of(sg.decide(snap())) is None  # already green on this head
    assert gate_of(sg.decide(snap(gate_now=None))) == ("success", sg.GATE_OK)
    assert gate_of(sg.decide(snap(gate_now=("pending", "waiting on: det")))) == ("success", sg.GATE_OK)


def test_the_gate_waits_on_running_checks_missing_required_ones_and_reruns():
    # the shepherd's own queued job is not waited on (it is the job deciding)
    acts = sg.decide(snap(gate_pending=["DOOM-rosetta shard 1 (queued)", "shepherd (label event) (in_progress)"]))
    assert gate_of(acts) == ("pending", "waiting on: DOOM-rosetta shard 1")
    assert gate_of(sg.decide(snap(required_missing=["det", "full-suite"]))) == (
        "pending",
        "waiting on: det, full-suite",
    )
    assert gate_of(sg.decide(snap(failed=[failure("flake", updated=NOW - 60)])))[0] == "pending"
    assert gate_of(sg.decide(snap(failed=[{"check": "det", "triage": "main"}])))[0] == "pending"
    assert gate_of(sg.decide(snap(draft=True, labels=[])))[0] == "pending"  # #5104: a draft's skips read as green


def test_every_open_pr_gets_the_gate_and_a_closed_one_none():
    acts = sg.decide(snap(labels=[], failed=[failure("real", check="det")]))
    assert gate_of(acts) == ("failure", "failing: det") and "automerge" not in kinds(acts)
    assert sg.decide(snap(state="closed", labels=[], gate_now=None)) == []


def test_a_long_failing_list_fits_a_commit_status():
    names = [f"check-{i:02d}-with-a-long-name" for i in range(12)]
    state, text = gate_of(sg.decide(snap(failed=[failure("real", check=x) for x in names])))
    assert state == "failure" and len(text) <= 140 and text.endswith("...")


def test_gather_leaves_its_own_status_out_and_finds_missing_required_checks():
    gh = Gh()
    gh.dep_state = "closed"
    gh.statuses = [{"context": sg.GATE, "state": "pending", "description": "waiting on: det"}]
    s = sg.gather(7, gh.api, None, now=NOW, on_main=set(), flaky=set())
    assert s["gate_now"] == ("pending", "waiting on: det") and s["gate_pending"] == []
    assert s["required_missing"] == list(sg.REQUIRED_CHECKS)  # the fake head has only "smoke"
    url = gh.runs[0]["html_url"]
    gh.runs = [{"id": i, "name": c, "status": "completed", "conclusion": "success", "html_url": url, "details_url": url,
                "app": {"slug": "github-actions"}} for i, c in enumerate(sg.REQUIRED_CHECKS, 2)]  # fmt: skip
    lines = sg.process(7, gh.api, gh.run, None)
    assert f"#7 {sg.GATE} success: {sg.GATE_OK}: ok" in lines
    assert gh.statuses == [{"context": sg.GATE, "state": "success", "description": sg.GATE_OK}]
    assert not [x for x in sg.process(7, gh.api, gh.run, None) if sg.GATE in x]  # posted once


def test_apply_posts_the_gate_as_a_commit_status_on_the_head():
    gh = Gh()
    sg.apply(7, snap(), [{"op": "gate", "sha": SHA, "state": "failure", "description": "failing: det"}], run=gh.run)
    argv = gh.cmds[0]
    assert argv[:3] == ["gh", "api", f"repos/{sg.REPO_SLUG}/statuses/{SHA}"]
    assert {"state=failure", f"context={sg.GATE}", "description=failing: det"} <= set(argv)


def test_open_prs_lists_unlabelled_prs_too():
    gh = Gh()
    gh.pr["labels"] = []
    assert sg.open_labelled(gh.api) == [] and sg.open_prs(gh.api) == [7] and sg.open_prs(gh.api, gh.graphql) == [7]
