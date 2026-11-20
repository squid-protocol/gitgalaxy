"""main_watch (#4859): decide() and the run selection, plus lint of the workflows that wire it."""

import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import main_watch as mw  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
URL = "https://github.com/x/y/actions/runs/101"
WF = "Full Suite Gate (All OS x Python)"


def snap(**kw):
    s = {"wf": WF, "conclusion": "failure", "event": "workflow_dispatch", "sha": "a" * 40, "run_url": URL,
         "via": "event", "failed": [], "cancelled": [], "after_issue": True, "issue": None}  # fmt: skip
    s.update(kw)
    return s


def issue(text="old"):
    return {"number": 4840, "text": text}


def test_failure_without_issue_opens_one():
    (a,) = mw.decide(snap())
    assert a["op"] == "create" and a["title"] == f"main is red: {WF}" and URL in a["body"]


def test_failure_with_issue_comments_once_per_run():
    (a,) = mw.decide(snap(issue=issue()))
    assert a["op"] == "comment" and a["number"] == 4840 and a["body"].startswith("Failed again (workflow_dispatch)")
    assert mw.decide(snap(issue=issue(f"opened for {URL}"))) == []  # already reported (event path or reconcile)


def test_success_closes_only_after_the_issue_was_opened():
    (a,) = mw.decide(snap(conclusion="success", issue=issue()))
    assert a["op"] == "close" and "Green again" in a["body"]
    assert mw.decide(snap(conclusion="success", issue=issue(), after_issue=False)) == []
    assert mw.decide(snap(conclusion="success")) == []  # nothing open: nothing to do


def test_success_already_reported_is_not_closed_twice():
    assert mw.decide(snap(conclusion="success", issue=issue(URL))) == []


def test_reconcile_says_so_in_the_comment():
    (a,) = mw.decide(snap(issue=issue(), via="reconcile"))
    assert "found by reconcile" in a["body"]


def test_cancelled_legs_are_distinguished():
    (a,) = mw.decide(snap(issue=issue(), failed=["m (win, 3.10)"], cancelled=["m (mac, 3.12)"]))
    assert "1 job(s) failed" in a["body"] and "1 more were cancelled" in a["body"]
    (b,) = mw.decide(snap(issue=issue(), cancelled=["m (mac, 3.12)", "m (mac, 3.10)"]))
    assert "No job failed on its own" in b["body"] and "not a verdict on the code" in b["body"]
    (c,) = mw.decide(snap(issue=issue(), failed=["m"]))
    assert "cancelled" not in c["body"]


def test_legs_split_jobs():
    jobs = [{"name": "a", "conclusion": "failure"}, {"name": "b", "conclusion": "timed_out"},
            {"name": "c", "conclusion": "cancelled"}, {"name": "d", "conclusion": "success"}]  # fmt: skip
    assert mw.legs(jobs) == (["a", "b"], ["c"])


def run(i, name=WF, conclusion="failure", event="schedule", branch="main"):
    return {"id": i, "name": name, "conclusion": conclusion, "event": event, "head_branch": branch}


def test_latest_verdicts_skips_cancelled_prs_and_other_branches():
    runs = [run(5, conclusion="cancelled"), run(4, conclusion="success"), run(3), run(9, branch="x"),
            run(8, event="pull_request"), run(7, name="Other", conclusion="success")]  # fmt: skip
    v = mw.latest_verdicts(runs)
    assert v[WF]["id"] == 4 and v["Other"]["id"] == 7


def test_latest_verdicts_takes_newest_by_id():
    assert mw.latest_verdicts([run(1, conclusion="success"), run(2)])[WF]["conclusion"] == "failure"


# --- infra reruns and re-verify -------------------------------------------------------------------------------------

LOST = "The hosted runner lost communication with the server. Anything in your workflow that terminates it..."


def test_infra_loss_is_read_from_the_annotations():
    assert mw.infra_loss(["x", LOST]) and mw.infra_loss(["The runner has received a shutdown signal."])
    assert not mw.infra_loss(["Process completed with exit code 1."]) and not mw.infra_loss([])


def test_rerun_only_when_every_failed_job_lost_its_runner_on_a_first_attempt():
    lost, real = ("det-mutation (3)", [LOST]), ("refresh", ["Process completed with exit code 1."])
    assert mw.rerun_wanted(1, [lost]) and mw.rerun_wanted(1, [lost, ("det-mutation (2)", [LOST])])
    assert not mw.rerun_wanted(1, [lost, real])  # one real failure: a person looks
    assert not mw.rerun_wanted(2, [lost])  # never a second retry
    assert not mw.rerun_wanted(1, [])  # only cancelled legs: nothing to rerun


def test_a_retried_failure_says_so_in_the_issue():
    (a,) = mw.decide(snap(retry=True))
    assert a["op"] == "create" and "lost its runner" in a["body"] and "rerun once" in a["body"]
    (b,) = mw.decide(snap())
    assert "lost its runner" not in b["body"]


def test_reconcile_reads_the_workflows_own_runs_not_a_window_of_all_main_runs(monkeypatch):
    """#8572: the nightly's green run was invisible in the newest 300 runs of main, so its issue never closed."""
    asked, applied = [], []

    def fake_paged(path, key=None, limit=3):
        asked.append(path)
        if path.endswith("/actions/workflows"):
            return [{"name": WF, "id": 77}]
        return [{"id": 9, "name": WF, "conclusion": "success", "event": "schedule", "head_branch": "main",
                 "head_sha": "b" * 40, "html_url": URL, "updated_at": "2026-11-18T13:00:00Z"}]  # fmt: skip

    monkeypatch.setattr(mw, "paged", fake_paged)
    monkeypatch.setattr(
        mw, "open_issues", lambda repo: {f"main is red: {WF}": {"number": 8572, "created_at": "2026-11-17T14:00:00Z"}}
    )
    monkeypatch.setattr(mw, "issue_text", lambda repo, i: {"number": i["number"], "text": "old"})
    monkeypatch.setattr(mw, "apply", lambda repo, acts, dry: applied.extend(acts))
    mw.cmd_reconcile("x/y", True)
    assert any("/actions/workflows/77/runs?branch=main" in p for p in asked)
    assert [a["op"] for a in applied] == ["close"] and applied[0]["number"] == 8572


NOW = "2026-11-18T12:00:00+00:00"


def red(updated="2026-11-18T01:00:00Z", conclusion="failure"):
    return {"conclusion": conclusion, "updated_at": updated}


def test_reverify_is_due_for_an_old_red_with_newer_commits():
    assert mw.reverify_due(NOW, red(), 5, False, "") is None


@pytest.mark.parametrize(
    ("run", "ahead", "active", "text", "why"),
    [
        (red(conclusion="success"), 5, False, "", "green"),
        (red("2026-11-18T10:00:00Z"), 5, False, "", "under 4 h"),
        (red(), 0, False, "", "no new commit"),
        (red(), 5, True, "", "already queued"),
        (red(), 5, False, f"x {mw.REVERIFY_MARK}2026-11-18T05:00:00+00:00 -->", "within 12 h"),
    ],
)  # fmt: skip
def test_reverify_waits(run, ahead, active, text, why):
    assert why in mw.reverify_due(NOW, run, ahead, active, text)


def test_an_old_reverify_marker_does_not_block_another():
    assert mw.reverify_due(NOW, red(), 1, False, f"{mw.REVERIFY_MARK}2026-11-17T12:00:00+00:00 -->") is None


# --- the workflows ----------------------------------------------------------------------------------------------------


def read(name):
    return (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_main_watch_checks_out_main_only_and_has_reconcile():
    wf = read("main-watch.yml")
    assert re.search(r"ref:\s*main\b", wf) and "persist-credentials: false" in wf
    assert "schedule:" in wf and "reconcile" in wf and "head.sha" not in wf.replace("workflow_run.head_sha", "")


def test_post_merge_dispatches_with_a_token_whose_runs_trigger():
    """A dispatch with the workflow's own GITHUB_TOKEN starts no run; the squid-shepherd App's token does, with the PAT
    as the fallback when the mint fails (promoter-bot#64: the App has its own API quota)."""
    wf = read("post-merge.yml")
    assert "DISPATCH_TOKEN: ${{ steps.app-token.outputs.token || secrets.AUTOMATION_PAT }}" in wf
    assert "run: python3 tests/tools/post_merge_dispatch.py" in wf  # #5136: the dispatch rule moved into the script
    script = (REPO / "tests" / "tools" / "post_merge_dispatch.py").read_text(encoding="utf-8")
    assert 'GH_TOKEN=os.environ.get("DISPATCH_TOKEN")' in script and '"gh", "workflow", "run"' in script


def test_a_cancelled_leg_says_how_long_it_ran():
    jobs = [
        {"name": "mac 3", "conclusion": "cancelled", "started_at": "2026-10-10T20:44:16Z",
         "completed_at": "2026-10-10T21:29:35Z"},
        {"name": "old", "conclusion": "cancelled"},  # no timestamps: the bare name
    ]  # fmt: skip
    assert mw.legs(jobs) == ([], ["mac 3 after 45 min", "old"])


def test_a_cancelled_leg_with_no_steps_never_got_a_runner_8673():
    jobs = [
        {"name": "mac", "conclusion": "cancelled", "started_at": "2026-11-19T14:11:06Z",
         "completed_at": "2026-11-19T14:26:07Z", "steps": []},
        {"name": "hung", "conclusion": "cancelled", "started_at": "2026-11-19T14:11:06Z",
         "completed_at": "2026-11-19T14:26:07Z", "steps": [{"name": "x", "conclusion": "cancelled"}]},
        {"name": "old", "conclusion": "cancelled"},  # no steps key: unknown, not claimed
    ]  # fmt: skip
    _, cancelled = mw.legs(jobs)
    assert cancelled == ["mac after 15 min" + mw.NO_RUNNER, "hung after 15 min", "old"]
    only = mw.legs_note([], cancelled[:1])
    assert "never got a runner" in only and "rerun" in only and "hang:" not in only
    assert "a hang: compare" in mw.legs_note([], cancelled)  # mixed: the hang caveat stays
    assert "a hang: compare" in mw.legs_note([], cancelled[1:2])
    assert "never got a runner" in mw.legs_note(["f"], cancelled[:1])  # failed + starved: names the leg


def test_main_watch_may_rerun_and_dispatch():
    """The rerun (event path) and the dispatch (reconcile) both need actions: write; the rerun reads the attempt."""
    wf = read("main-watch.yml")
    assert wf.count("actions: write") == 2 and "actions: read" not in wf
    assert "RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt }}" in wf


def _on(doc):
    return doc.get("on", doc.get(True)) or {}  # PyYAML reads the bare key `on` as True


def _runs_on_main(trigger):
    """True when the workflow's `on:` block can produce a run whose head branch is main."""
    if "schedule" in trigger or "workflow_dispatch" in trigger:
        return True
    push = trigger.get("push")
    if push is None:
        return False
    branches = (push or {}).get("branches")
    if branches is None:
        return not (push or {}).get("tags")  # tags-only push never runs on the main branch
    return "main" in branches


def test_every_watched_workflow_exists_and_runs_on_main():
    """Main Watch must not subscribe to a workflow that cannot complete on main (each such event is a wasted run)."""
    yaml = pytest.importorskip("yaml")
    by_name = {}
    for p in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        by_name[doc.get("name", p.stem)] = (p.name, doc)
    watched = _on(yaml.safe_load(read("main-watch.yml")))["workflow_run"]["workflows"]
    assert watched, "main-watch.yml lists no workflows"
    assert len(watched) == len(set(watched)), "a workflow is listed twice"
    for name in watched:
        assert name in by_name, f"{name!r} is not the `name:` of any workflow file"
        fname, doc = by_name[name]
        assert _runs_on_main(_on(doc)), f"{fname} ({name!r}) never runs on main (no main push, schedule or dispatch)"
        assert "workflow_run" not in _on(doc), f"{fname} is itself a workflow_run consumer: Main Watch would loop"


def test_a_never_acquired_cancelled_leg_is_a_runner_loss_8673(monkeypatch):
    notacq = "The job was not acquired by Runner of type hosted even after multiple attempts"
    assert mw.infra_loss([notacq])
    jobs = [
        {"id": 1, "name": "mac 3.11", "conclusion": "cancelled"},
        {"id": 2, "name": "hang", "conclusion": "cancelled"},
        {"id": 3, "name": "ok", "conclusion": "success"},
        {"id": 4, "name": "real", "conclusion": "failure"},
    ]
    notes = {
        1: [notacq],
        2: ["The job exceeded the maximum execution time"],
        4: ["Process completed with exit code 1."],
    }
    monkeypatch.setattr(mw, "paged", lambda *a, **k: jobs)
    monkeypatch.setattr(mw, "gh", lambda *a: [{"message": m} for m in notes[int(a[1].split("/")[4])]])
    got = mw.failed_jobs("x/y", 5)
    assert [n for n, _ in got] == ["mac 3.11", "real"]  # the hang is not a runner loss
    assert not mw.rerun_wanted(1, got)  # a real failure beside it: a person looks
    assert mw.rerun_wanted(1, got[:1])
    assert not mw.rerun_wanted(1, [])
