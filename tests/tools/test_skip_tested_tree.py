"""skip_tested_tree (#4935): the push-run skip decision over the whole input class, and the snapshot against a fake gh."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skip_tested_tree as st  # noqa: E402

TREE, SHA, PARENT, HEAD = "t" * 40, "m" * 40, "p" * 40, "h" * 40


def snap(**kw):
    s = {
        "event": "push", "ref": st.MAIN_REF, "sha": SHA, "parents": 1, "tree": TREE,
        "pr": {"head_tree": TREE, "merge_sha": SHA, "base": "main"}, "parent_in_head": True,
        "runs": [{"id": 5, "event": "pull_request", "status": "completed", "conclusion": "success"}],
    }  # fmt: skip
    s.update(kw)
    return s


def run(rid, conclusion, status="completed", event="pull_request"):
    return {"id": rid, "event": event, "status": status, "conclusion": conclusion}


def test_equal_tree_and_green_pr_run_skips():
    skip, why = st.decide(snap())
    assert skip and "passed in PR run 5" in why


@pytest.mark.parametrize("runs", [
    [run(5, "failure")], [run(5, "cancelled")], [run(5, None, "in_progress")], [run(5, "skipped")],
    [], [run(5, "success", event="push")],
    [run(5, "success"), run(6, "failure")],  # a newer red re-run beats an older green
])  # fmt: skip
def test_pr_run_not_green_runs(runs):
    assert not st.decide(snap(runs=runs))[0]


def test_older_red_then_newer_green_skips():
    assert st.decide(snap(runs=[run(4, "failure"), run(5, "success")]))[0]


@pytest.mark.parametrize("kw", [
    {"pr": {"head_tree": "x" * 40, "merge_sha": SHA, "base": "main"}},  # tree differs (the PR was behind main)
    {"parent_in_head": False},  # head lacks main's previous commit
    {"parent_in_head": None},
    {"parents": 2},  # a merge commit
    {"parents": 0},
    {"pr": None},  # direct push
    {"pr": {"head_tree": TREE, "merge_sha": "z" * 40, "base": "main"}},
    {"pr": {"head_tree": TREE, "merge_sha": SHA, "base": "v6-dev"}},  # a PR into another base proved nothing about main
    {"pr": {"head_tree": TREE, "merge_sha": SHA}},  # base unknown
    {"ref": "refs/heads/other"},
])  # fmt: skip
def test_tree_or_history_mismatch_runs(kw):
    assert not st.decide(snap(**kw))[0]


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch", "pull_request"])
def test_never_skips_other_events(event):
    assert not st.decide(snap(event=event))[0]


class FakeGh:
    def __init__(self, parents=1, head_tree=TREE, status="ahead", runs=(), pulls=None):
        self.calls = []
        self.parents, self.head_tree, self.status, self.runs = parents, head_tree, status, list(runs)
        self.pulls = (
            pulls
            if pulls is not None
            else [{"merged_at": "t", "merge_commit_sha": SHA, "head": {"sha": HEAD}, "base": {"ref": "main"}}]
        )

    def __call__(self, path):
        self.calls.append(path)
        if path.endswith(f"commits/{SHA}"):
            return {"parents": [{"sha": PARENT}] * self.parents, "commit": {"tree": {"sha": TREE}}}
        if "/pulls" in path:
            return self.pulls
        if path.endswith(f"commits/{HEAD}"):
            return {"commit": {"tree": {"sha": self.head_tree}}}
        if "/compare/" in path:
            return {"status": self.status}
        if "/actions/workflows/" in path:
            return {"workflow_runs": self.runs}
        raise AssertionError(path)


ENV = {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": st.MAIN_REF, "GITHUB_SHA": SHA}


def decide_with(monkeypatch, fake, env=ENV):
    monkeypatch.setattr(st, "gh", fake)
    return st.decide(st.snapshot("o/r", "wf.yml", env))


def test_snapshot_squash_of_green_up_to_date_pr_skips(monkeypatch):
    skip, _ = decide_with(monkeypatch, FakeGh(runs=[run(9, "success")]))
    assert skip


def test_snapshot_behind_pr_runs_without_asking_for_runs(monkeypatch):
    fake = FakeGh(status="diverged", runs=[run(9, "success")])
    assert not decide_with(monkeypatch, fake)[0]
    assert not any("/actions/" in c for c in fake.calls)


def test_snapshot_merge_commit_and_two_prs_run(monkeypatch):
    assert not decide_with(monkeypatch, FakeGh(parents=2, runs=[run(9, "success")]))[0]
    two = [{"merged_at": "t", "merge_commit_sha": SHA, "head": {"sha": HEAD}, "base": {"ref": "main"}}] * 2
    assert not decide_with(monkeypatch, FakeGh(pulls=two, runs=[run(9, "success")]))[0]


def test_snapshot_non_push_makes_no_api_call(monkeypatch):
    fake = FakeGh()
    assert not decide_with(monkeypatch, fake, {**ENV, "GITHUB_EVENT_NAME": "schedule"})[0]
    assert fake.calls == []


def test_api_error_fails_open(monkeypatch, tmp_path, capsys):
    def boom(path):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(st, "gh", boom)
    out = tmp_path / "out"
    for k, v in {**ENV, "GITHUB_REPOSITORY": "o/r", "GITHUB_OUTPUT": str(out)}.items():
        monkeypatch.setenv(k, v)
    assert st.main(["x", "wf.yml"]) == 0
    assert out.read_text() == "skip=false\ndefer=false\nbase=\n"


def test_paths_filtered_pr_has_no_run_so_the_push_runs(monkeypatch):
    """#4964: the PR's `paths` filter skipped the workflow (no run on the head) but the push filter matches on main (or
    there is none, tree-sitter-accuracy-audit): an absent PR run is never a proof, whatever else is equal. A run from
    another workflow or another event on the same head does not count either."""
    fake = FakeGh(runs=[])
    skip, why = decide_with(monkeypatch, fake)
    assert not skip and "paths filter" in why
    assert any("/actions/workflows/wf.yml/runs?head_sha=" in c and "event=pull_request" in c for c in fake.calls)
    assert not decide_with(monkeypatch, FakeGh(runs=[run(9, "success", event="push")]))[0]
    assert not decide_with(monkeypatch, FakeGh(runs=[run(9, "skipped")]))[0]


# ---------------------------------------------------------------- hourly cadence for the heavy main suites (2026-11-03)
NOW = 1_800_000_000.0


def mrun(rid, mins_ago, conclusion="success", status="completed", event="push", sha=None):
    stamp = st.datetime.fromtimestamp(NOW - mins_ago * 60, tz=st.timezone.utc).isoformat().replace("+00:00", "Z")
    return {"id": rid, "event": event, "status": status, "conclusion": conclusion, "run_started_at": stamp,
            "head_sha": sha or f"{rid:040d}"}


def test_a_real_run_inside_the_window_defers_and_names_its_base():
    late, why, base = st.defer([mrun(1, 200), mrun(2, 25)], run_id=9, now=NOW, cadence_s=3600)
    assert late and "25 min ago" in why and base == f"{2:040d}"


@pytest.mark.parametrize("runs,late", [
    ([mrun(1, 61)], False),  # last checked over an hour ago: run it
    ([mrun(1, 5, "cancelled")], False),  # a deferred (cancelled) run checked nothing
    ([mrun(1, 5, "failure")], True),  # a red run is a real check too
    ([mrun(1, 90, None, "in_progress")], True),  # one at a time, however long it has run
    ([mrun(1, 5, event="pull_request")], False),  # PR runs never count
    ([mrun(1, 70), mrun(2, 10, event="schedule")], True),  # the nightly counts
    ([], False),
])  # fmt: skip
def test_cadence_counts_only_real_main_runs(runs, late):
    assert st.defer(runs, run_id=9, now=NOW, cadence_s=3600)[0] is late


def test_a_rerun_of_a_deferred_run_does_not_defer_on_itself():
    assert not st.defer([mrun(9, 3, None, "in_progress"), mrun(1, 80)], run_id=9, now=NOW, cadence_s=3600)[0]


def test_main_writes_defer_and_base_only_for_a_push_with_a_cadence(monkeypatch, tmp_path):
    out = tmp_path / "out"
    monkeypatch.setattr(st, "decide", lambda s: (False, "tree differs"))
    monkeypatch.setattr(st, "snapshot", lambda repo, wf, env: {})
    monkeypatch.setattr(st, "gh", lambda path: {"workflow_runs": [mrun(1, 10)]})
    monkeypatch.setattr(st.time, "time", lambda: NOW)
    env = {"GITHUB_REPOSITORY": "o/r", "GITHUB_EVENT_NAME": "push", "GITHUB_REF": st.MAIN_REF, "GITHUB_RUN_ID": "9",
           "GITHUB_OUTPUT": str(out), "CADENCE_HOURS": "1"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert st.main(["x", "smoke-test.yml"]) == 0
    assert out.read_text().splitlines() == ["skip=false", "defer=true", f"base={1:040d}"]
    out.write_text("")
    monkeypatch.delenv("CADENCE_HOURS")
    st.main(["x", "java-compile.yml"])
    assert out.read_text().splitlines() == ["skip=false", "defer=false", "base="]
    out.write_text("")
    monkeypatch.setenv("CADENCE_HOURS", "1")
    monkeypatch.setattr(st, "gh", lambda path: (_ for _ in ()).throw(RuntimeError("503")))
    st.main(["x", "smoke-test.yml"])
    assert out.read_text().splitlines()[1] == "defer=false"  # fail-open
