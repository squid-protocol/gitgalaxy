"""shepherd_gh (#4847 item 3): the label rules, against decide() and a fake GitHub; plus the workflows' security lint."""

import json
import re
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
         "label_actors": {x: {"login": "joe", "permission": "admin", "commit_id": SHA} for x in sg.REQUESTS},
         "approved": True, "pending_update": False}  # fmt: skip
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
    assert kinds(acts) == ["ready", "automerge"]
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
    actors = {sg.MERGE: {"login": "rando", "permission": "read", "commit_id": SHA}}
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


def test_behind_and_green_updates_the_branch_but_not_when_failing_or_held():
    assert "update_branch" in kinds(sg.decide(snap(mergeable_state="behind")))  # labelled, behind, green
    acts = sg.decide(snap(mergeable_state="behind", labels=[sg.MERGE, sg.HOLD]))
    assert "update_branch" not in kinds(acts)
    acts = sg.decide(snap(mergeable_state="behind", failed=[failure("real")]))
    assert "update_branch" not in kinds(acts)
    acts = sg.decide(snap(mergeable_state="behind", auto_merge=True))
    assert "update_branch" in kinds(acts)


def test_dirty_pr_gets_the_merge_note_once():
    acts = sg.decide(snap(mergeable_state="dirty", digest_text="merge main"))
    assert by_op(acts, "labels")[0]["add"] == [sg.NEEDS]
    assert by_op(acts, "comment")


def test_closed_pr_only_loses_its_labels_it_was_vetted_on():
    assert sg.decide(snap(state="closed", labels=[sg.MERGE], auto_merge=True)) == []


# --- apply and gather, against a fake gh -----------------------------------------------------------------------------


class Gh:
    """A fake `gh api` (for pr_check / ci_digest / gather) and a recorder for the gh commands apply() runs."""

    def __init__(self):
        self.pr = {
            "number": 7,
            "state": "open",
            "merged": False,
            "draft": True,
            "auto_merge": None,
            "head": {"sha": SHA, "ref": "fix/x", "repo": {"full_name": "squid-protocol/gitgalaxy"}},
            "labels": [{"name": sg.MERGE}],
            "body": "Depends on #6",
            "mergeable_state": "clean",
        }
        self.calls, self.cmds = [], []
        self.perm = "write"
        self.matrix_runs = []
        self.dep_state = "closed"
        # the timeline: who added each label, on which head (GitHub's commit_id at that moment)
        self.events = [
            {"event": "labeled", "label": {"name": x}, "actor": {"login": "joe"}, "commit_id": SHA}
            for x in (sg.MERGE, sg.MATRIX)
        ]
        self.comments = []  # the bot's markers live here
        self.parents = {}  # commit sha -> parent shas

    def api(self, path):
        self.calls.append(path)
        bare = path.split("?")[0]
        if re.search(r"/commits/[0-9a-f]{40}/pulls$", bare):
            return [self.pr]
        if re.fullmatch(r"repos/[^/]+/[^/]+/commits/[0-9a-f]{40}", bare):
            return {"parents": [{"sha": x} for x in self.parents.get(bare.rsplit("/", 1)[1], [])]}
        if bare.endswith("/pulls/7"):
            return self.pr
        if bare.endswith("/pulls/6"):
            return {"state": self.dep_state}
        if "/check-runs" in path:
            return {
                "check_runs": [
                    {
                        "id": 1,
                        "name": "smoke",
                        "status": "completed",
                        "conclusion": "success",
                        "app": {"slug": "github-actions"},
                    }
                ]
            }
        if bare.endswith("/status"):
            return {"statuses": []}
        if bare.endswith("/events"):
            return self.events
        if bare.endswith("/comments"):
            return self.comments
        if bare.endswith("/permission"):
            return {"permission": self.perm}
        if "/workflows/" in path:
            return {"workflow_runs": self.matrix_runs}
        raise AssertionError(f"unexpected API path {path}")

    def run(self, argv):
        self.cmds.append(argv)
        out = "d" * 40 if "-q" in argv else ""
        return subprocess.CompletedProcess(argv, 0, out, "")


def merged_by(gh):
    return any(c[:3] == ["gh", "pr", "merge"] and "--auto" in c for c in gh.cmds)


def test_reconcile_after_an_unapproved_push_drops_the_label_and_never_merges():
    # no synchronize event was seen: the head moved from the labelled commit (A) to B with no bot marker
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "b" * 40
    gh.parents = {"b" * 40: ["a" * 40, "c" * 40]}
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines)
    assert not merged_by(gh) and not any(c[:3] == ["gh", "pr", "ready"] for c in gh.cmds)


def test_reconcile_keeps_the_label_through_the_bot_update_branch():
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "b" * 40
    gh.parents = {"b" * 40: [SHA, "c" * 40]}  # the bot's merge of main on the labelled head
    gh.comments = [{"body": f"<!-- shepherd-update from={SHA} to={'b' * 40} -->"}]
    lines = sg.process(7, gh.api, gh.run, None)
    assert not any("unlabel" in x for x in lines)
    assert merged_by(gh)


def test_a_push_after_the_bot_update_is_not_carried():
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "d" * 40  # a force-push: a merge commit on the approved head, not the bot's
    gh.parents = {"d" * 40: [SHA, "c" * 40]}
    gh.comments = [{"body": f"<!-- shepherd-update from={SHA} to={'b' * 40} -->"}]
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)


def test_a_bot_update_without_its_result_marker_is_pending_not_approved():
    gh = Gh()
    gh.dep_state = "closed"
    gh.pr["head"]["sha"] = "b" * 40
    gh.comments = [{"body": f"<!-- shepherd-update from={SHA} -->"}]
    lines = sg.process(7, gh.api, gh.run, None)
    assert not any("unlabel" in x for x in lines) and not merged_by(gh)


def test_reconcile_drops_a_label_added_by_a_non_writer_in_the_timeline():
    gh = Gh()
    gh.dep_state = "closed"
    gh.events = [{"event": "labeled", "label": {"name": sg.MERGE}, "actor": {"login": "rando"}, "commit_id": SHA}]
    gh.perm = "read"
    lines = sg.process(7, gh.api, gh.run, None)
    assert any("unlabel" in x for x in lines) and not merged_by(gh)


def test_prs_for_head_selects_the_open_labelled_pr_of_that_commit():
    gh = Gh()
    assert sg.prs_for_head(gh.api, "e" * 40) == [7]
    with pytest.raises(SystemExit):
        sg.prs_for_head(gh.api, "not-a-sha")


def test_gather_and_process_for_a_labelled_event_marks_ready_and_enables_auto_merge():
    gh = Gh()
    gh.dep_state = "closed"  # #6 merged: no block
    lines = sg.process(7, gh.api, gh.run, {"action": "labeled", "label": sg.MERGE, "sender": "joe"})
    assert lines == ["#7 ready for review: ok", "#7 auto-merge on: ok"]
    assert any(c[:3] == ["gh", "pr", "ready"] for c in gh.cmds)
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


def test_update_branch_writes_the_marker_pair_around_the_push():
    s = snap(mergeable_state="behind", head_sha="b" * 40)
    log_cmds = []

    def run(argv):
        log_cmds.append(argv)
        return subprocess.CompletedProcess(argv, 0, "d" * 40 if "-q" in argv else "", "")

    lines = sg.apply(7, s, [{"op": "update_branch"}], run=run)
    assert "shepherd-update from=" + "b" * 40 in " ".join(log_cmds[0])
    assert log_cmds[1][:4] == ["gh", "pr", "update-branch", "7"]
    assert "shepherd-update from=" + "b" * 40 + " to=" + "d" * 40 in " ".join(log_cmds[3])
    assert all(line.endswith("ok") for line in lines)


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
