"""main_watch (#4859): decide() and the run selection, plus lint of the workflows that wire it."""

import re
import sys
from pathlib import Path

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


# --- the workflows ----------------------------------------------------------------------------------------------------


def read(name):
    return (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_main_watch_checks_out_main_only_and_has_reconcile():
    wf = read("main-watch.yml")
    assert re.search(r"ref:\s*main\b", wf) and "persist-credentials: false" in wf
    assert "schedule:" in wf and "reconcile" in wf and "head.sha" not in wf.replace("workflow_run.head_sha", "")


def test_post_merge_dispatches_with_the_pat():
    wf = read("post-merge.yml")
    assert "DISPATCH_TOKEN: ${{ secrets.AUTOMATION_PAT }}" in wf
    assert 'GH_TOKEN="${DISPATCH_TOKEN:-$GH_TOKEN}" gh workflow run' in wf


def test_a_cancelled_leg_says_how_long_it_ran():
    jobs = [
        {"name": "mac 3", "conclusion": "cancelled", "started_at": "2026-10-10T20:44:16Z",
         "completed_at": "2026-10-10T21:29:35Z"},
        {"name": "old", "conclusion": "cancelled"},  # no timestamps: the bare name
    ]  # fmt: skip
    assert mw.legs(jobs) == ([], ["mac 3 after 45 min", "old"])
