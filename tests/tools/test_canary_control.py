"""#7155 part 2: the canary catalog is safe and names real gates, and the opener refuses anything but a canary/ branch."""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import canary_control as cc  # noqa: E402
import gate_controls as gc  # noqa: E402

WORKFLOW = TOOLS.parents[1] / ".github" / "workflows" / "canary-control.yml"


def test_the_shipped_catalog_is_safe_and_names_real_gates():
    assert cc.problems() == []


def test_each_unsafe_shape_is_named():
    bad = (
        cc.Defect("wf", ".github/workflows/x.yml", "", ("mypy-audit",), "w"),
        cc.Defect("up", "../outside.py", "", ("mypy-audit",), "w"),
        cc.Defect("exists", "tests/tools/canary_control.py", "", ("mypy-audit",), "w"),
        cc.Defect("ghost", "gitgalaxy/new_canary_x.py", "", ("no-such-gate",), "w"),
        cc.Defect("none", "gitgalaxy/new_canary_y.py", "", (), "w"),
        cc.Defect("pub", "tools/publish.yml", "", ("mypy-audit",), "w"),
    )
    out = cc.problems(bad)
    for key, word in (
        ("wf:", "workflow"),
        ("up:", "leaves"),
        ("exists:", "already exists"),
        ("ghost:", "no gate named"),
        ("none:", "no gate to go red"),
        ("pub:", "workflow"),
    ):
        assert any(p.startswith(key) and word in p for p in out), (key, out)
    twice = (cc.DEFECTS[0], cc.DEFECTS[0])
    assert any("planted twice" in p for p in cc.problems(twice))


def test_the_plan_lists_every_gate_that_must_go_red_once():
    p = cc.plan()
    assert p["must_go_red"] == sorted(set(p["must_go_red"]))
    assert {g for d in cc.DEFECTS for g in d.red} == set(p["must_go_red"])
    assert {g.name for g in gc.GATES} >= set(p["must_go_red"])


def test_the_pr_body_carries_a_parseable_expectation_and_a_do_not_merge_note():
    body = cc.pr_body()
    m = re.search(rf"<!-- {cc.MARKER} (\{{.*\}}) -->", body)
    assert m and json.loads(m.group(1)) == cc.plan()
    assert "do not merge" in body


def test_a_non_canary_branch_is_refused_and_a_dry_run_changes_nothing(capsys, monkeypatch):
    monkeypatch.setattr(cc.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran a command")))
    assert cc.open_pr("feature/x") == 2
    assert cc.open_pr("main", dry_run=True) == 2
    assert cc.open_pr("canary/20261122T0000Z", dry_run=True) == 0
    assert "must_go_red" in capsys.readouterr().out


def test_branch_names_are_canary_prefixed():
    assert cc.branch_name(datetime(2026, 11, 22, 3, 17, tzinfo=UTC)) == "canary/20261122T0317Z"


def test_plant_writes_only_the_catalog_files(tmp_path):
    paths = cc.plant(tmp_path)
    assert paths == [d.path for d in cc.DEFECTS]
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file()) == sorted(paths)


def test_the_workflow_only_opens_a_pr_never_merges_and_has_no_pr_trigger():
    text = WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    on = doc.get(True) or doc.get("on")
    assert set(on) == {"schedule", "workflow_dispatch"}
    assert "merge" not in re.sub(r"#.*", "", text).lower().replace("never merge", "")
    assert "shepherd:" not in text
    assert doc["permissions"] == {"contents": "read"}


def _run(name, conclusion="success", status="completed"):
    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-11-22T03:20:00Z",
        "completed_at": "2026-11-22T03:22:05Z",
    }


HOUR = cc.timedelta(hours=1)


def test_every_red_gate_has_a_check_and_the_clean_pr_expects_nothing():
    assert {g for d in cc.DEFECTS for g in d.red} <= set(cc.CHECK_OF)
    assert cc.problems((cc.CLEAN,), clean=True) == []
    assert cc.plan((cc.CLEAN,))["kind"] == "clean" and cc.plan((cc.CLEAN,))["must_go_red"] == []


def test_a_gate_that_went_red_is_red_with_its_seconds():
    expect = {"must_go_red": ["mypy-audit", "full-suite"]}
    runs = [_run("mypy-audit", "failure"), _run("full-suite part 2/4", "failure"), _run("full-suite part 1/4")]
    r = cc.evaluate(expect, runs, age=5 * HOUR)
    assert [x["verdict"] for x in r["rows"]] == ["red", "red"]
    assert r["rows"][0]["seconds"] == 125 and r["misses"] == [] and r["settled"]


def test_a_green_skipped_or_absent_gate_is_a_miss_once_settled():
    expect = {"must_go_red": ["mypy-audit", "doc-refs-audit", "full-suite"]}
    runs = [_run("mypy-audit"), _run("doc-refs-audit", "skipped")]
    r = cc.evaluate(expect, runs, age=cc.MAX_AGE)
    assert r["misses"] == ["mypy-audit", "doc-refs-audit", "full-suite"]
    assert not cc.evaluate(expect, runs, age=HOUR)["misses"] == r["misses"]  # a missing run is pending while young


def test_an_unfinished_check_leaves_the_pr_open_until_it_is_old():
    expect = {"must_go_red": ["mypy-audit"]}
    runs = [_run("mypy-audit", None, "in_progress")]
    assert cc.evaluate(expect, runs, age=HOUR)["settled"] is False
    old = cc.evaluate(expect, runs, age=cc.MAX_AGE)
    assert old["settled"] and old["misses"] == ["mypy-audit"]


def test_the_name_match_is_not_a_loose_substring():
    expect = {"must_go_red": ["mypy-audit"]}
    r = cc.evaluate(expect, [_run("mypy-audit-extra", "failure")], age=cc.MAX_AGE)
    assert r["misses"] == ["mypy-audit"]


def test_a_red_check_on_the_clean_pr_is_a_false_alarm_but_the_hold_is_not():
    expect = {"kind": "clean", "must_go_red": []}
    r = cc.evaluate(expect, [_run("ruff-audit", "failure"), _run("ci-gate", "failure"), _run("det")], age=5 * HOUR)
    assert r["false_alarms"] == ["ruff-audit"]
    assert "False alarms" in cc.render(r) and "ruff-audit" in cc.render(r)


def test_settle_skips_a_pr_that_is_not_a_marked_canary(monkeypatch):
    monkeypatch.setattr(cc, "_gh", lambda *a, **k: (_ for _ in ()).throw(AssertionError("touched a PR")))
    base = {"number": 1, "createdAt": "2026-11-22T03:00:00Z", "headRefOid": "abc"}
    assert cc.settle({**base, "headRefName": "feature/x", "body": cc.pr_body()}) == "skipped"


def test_a_canary_pr_without_its_marker_is_closed_with_a_comment(monkeypatch):
    calls = []
    monkeypatch.setattr(cc, "_gh", _fake_gh(calls, []))
    pr = {"number": 3, "headRefName": "canary/x", "headRefOid": "abc", "createdAt": "2026-11-22T03:00:00Z", "body": "x"}
    assert cc.settle(pr) == "closed"
    assert [c[:2] for c in calls] == [("pr", "comment"), ("pr", "close")]
    calls.clear()
    assert cc.settle(pr, dry_run=True) == "dry-run" and calls == []


def _orphan_gh(calls, refs, delete_rc=0):
    class R:
        def __init__(self, rc=0, out=""):
            self.returncode, self.stdout, self.stderr = rc, out, "boom"

    def gh(*args, check=True):
        calls.append(args)
        if args[0] == "api" and "DELETE" in args:
            return R(delete_rc)
        if args[0] == "api":
            return R(out="\n".join(refs))
        return R()

    return gh


def test_an_orphan_canary_branch_is_deleted_and_an_open_prs_branch_is_kept(monkeypatch):
    calls = []
    refs = ["refs/heads/canary/old", "refs/heads/canary/live", "refs/heads/canaryx/no"]
    monkeypatch.setattr(cc, "_gh", _orphan_gh(calls, refs))
    assert cc.sweep_orphans({"canary/live"}) == ["orphan-deleted"]
    deletes = [c for c in calls if "DELETE" in c]
    assert len(deletes) == 1 and deletes[0][-1].endswith("heads/canary/old")


def test_a_dry_run_sweep_deletes_nothing_and_a_failed_delete_raises_an_issue(monkeypatch):
    calls = []
    monkeypatch.setattr(cc, "_gh", _orphan_gh(calls, ["refs/heads/canary/old"]))
    assert cc.sweep_orphans(set(), dry_run=True) == ["orphan:canary/old"]
    assert not any("DELETE" in c for c in calls)
    calls.clear()
    monkeypatch.setattr(cc, "_gh", _orphan_gh(calls, ["refs/heads/canary/old"], delete_rc=1))
    assert cc.sweep_orphans(set()) == ["orphan-delete-failed"]
    assert any(c[:2] == ("issue", "create") and "priority: high" in c for c in calls)


def test_results_exits_nonzero_when_an_orphan_cannot_be_deleted(monkeypatch, capsys):
    calls = []
    out = _orphan_gh(calls, ["refs/heads/canary/old"], delete_rc=1)

    def gh(*args, check=True):
        r = out(*args, check=check)
        if args[:2] == ("pr", "list"):
            r.stdout = "[]"
        return r

    monkeypatch.setattr(cc, "_gh", gh)
    assert cc.results() == 1


def _fake_gh(calls, runs, close_rc=0):
    class R:
        def __init__(self, rc=0, out=""):
            self.returncode, self.stdout, self.stderr = rc, out, "boom"

    def gh(*args, check=True):
        calls.append(args)
        if args[0] == "api":
            return R(out="\n".join(json.dumps(r) for r in runs))
        return R(close_rc if args[:2] == ("pr", "close") else 0)

    return gh


def test_settle_comments_raises_the_miss_issue_then_closes_and_deletes(monkeypatch):
    calls = []
    monkeypatch.setattr(cc, "_gh", _fake_gh(calls, [_run("mypy-audit")]))
    pr = {
        "number": 7,
        "headRefName": "canary/x",
        "headRefOid": "abc",
        "createdAt": "2020-01-01T00:00:00Z",
        "body": cc.pr_body(),
    }
    assert cc.settle(pr) == "closed"
    kinds = [c[:2] for c in calls]
    assert ("pr", "comment") in kinds and ("issue", "create") in kinds
    issue = next(c for c in calls if c[:2] == ("issue", "create"))
    assert "priority: high" in issue
    assert ("pr", "close", "7", "--delete-branch") == next(c for c in calls if c[:2] == ("pr", "close"))
    assert not any("merge" in c or "edit" in c for c in calls)


def test_a_close_that_fails_raises_an_issue_and_a_nonzero_exit(monkeypatch):
    calls = []
    monkeypatch.setattr(cc, "_gh", _fake_gh(calls, [_run("mypy-audit", "failure")], close_rc=1))
    body = cc.pr_body((cc.DEFECTS[2],))
    pr = {
        "number": 8,
        "headRefName": "canary/x",
        "headRefOid": "abc",
        "createdAt": "2020-01-01T00:00:00Z",
        "body": body,
    }
    assert cc.settle(pr) == "close-failed"
    assert any(c[:2] == ("issue", "create") and "did not close" in c[3] for c in calls)


def test_the_tool_and_workflow_never_merge_or_label():
    src = Path(cc.__file__).read_text(encoding="utf-8")
    assert '"merge"' not in src and '"--add-label"' not in src
    text = WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    assert set(doc["jobs"]) == {"open", "results"}
    assert doc["permissions"] == {"contents": "read"}
