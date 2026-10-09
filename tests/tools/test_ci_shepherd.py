"""ci_shepherd (#4790): one pass's decisions, against a fake GitHub -- merge when green, rerun infra once, comment once."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "box"))
import ci_shepherd as cs  # noqa: E402


class Gh:
    """A fake `gh api` for pr_check.check, plus a recorder for the commands the shepherd runs."""

    def __init__(self):
        self.prs, self.runs, self.calls = {}, {}, []

    def pr(self, n, sha="a" * 40, state="open", mergeable=True, mstate="clean", runs=()):
        self.prs[n] = {"number": n, "title": f"pr {n}", "state": state, "merged": state == "merged", "draft": True,
                       "head": {"sha": sha}, "node_id": f"N{n}", "mergeable": mergeable, "mergeable_state": mstate}  # fmt: skip
        self.runs[sha] = [{"id": i, "name": name, "status": "completed" if c else "in_progress", "conclusion": c,
                           "app": {"slug": "github-actions"}} for i, (name, c) in enumerate(runs, 1)]  # fmt: skip

    def api(self, path):
        parts = path.split("?")[0].split("/")
        if "check-runs" in parts:
            return {"check_runs": self.runs[parts[-2]]}
        if parts[-1] == "status":
            return {"statuses": []}
        if parts[-1] == "files":
            return []
        return self.prs[int(parts[-1])]

    def run(self, argv):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")


def failing(kind, run_id=99):
    return lambda n: {"number": n, "head_sha": "x", "mergeable_state": "clean",
                      "failed": [{"check": "full-suite", "conclusion": "failure", "url": "u", "run_id": run_id,
                                  "job_id": 1, "triage": kind, "repro": "pytest t", "errors": ["E"], "tail": ["t"],
                                  "tests": [], "cases": [], "more_errors": 0}]}  # fmt: skip


def step(gh, state, digest=None):
    return cs.step(state, gh.api, gh.run, digest or (lambda n: {"failed": []}), settle=0)


def test_green_pr_is_merged_and_leaves_the_queue():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, runs=[("ruff-audit", "success")])
    did = step(gh, state)
    assert any("MERGED" in d for d in did) and state["queue"] == []
    assert ["gh", "pr", "merge"] == gh.calls[-1][:3]


def test_pending_pr_waits_and_merged_pr_leaves():
    gh, state = Gh(), {"queue": [1, 2], "after": {}, "seen": {}}
    gh.pr(1, runs=[("ruff-audit", None)])
    gh.pr(2, state="merged", sha="b" * 40)
    did = step(gh, state)
    assert "#1 waiting: 1 pending" in did and state["queue"] == [1] and gh.calls == []


def test_infra_failure_is_rerun_up_to_three_times_spaced_out(monkeypatch):
    gh, state, clock = Gh(), {"queue": [1], "after": {}, "seen": {}}, [1000.0]
    monkeypatch.setattr(cs, "now", lambda: clock[0])
    gh.pr(1, runs=[("full-suite", "failure")])

    def reruns():
        return [c for c in gh.calls if c[:3] == ["gh", "run", "rerun"]]

    step(gh, state, failing("infra"))
    step(gh, state, failing("infra"))  # too soon after the first
    assert reruns() == [["gh", "run", "rerun", "99", "--failed", "-R", cs.REPO_SLUG]]
    for _ in range(4):
        clock[0] += cs.RETRY_GAP
        step(gh, state, failing("infra"))
    assert len(reruns()) == cs.INFRA_RETRIES


def test_a_flake_is_rerun_once():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, runs=[("full-suite", "failure")])
    step(gh, state, failing("flake"))
    state["seen"]["1"]["rerun:full-suite"][-1] -= cs.RETRY_GAP
    step(gh, state, failing("flake"))
    assert len([c for c in gh.calls if c[:3] == ["gh", "run", "rerun"]]) == 1


def test_real_failure_is_commented_once_per_head_and_again_after_a_push():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, runs=[("full-suite", "failure")])
    step(gh, state, failing("real"))
    step(gh, state, failing("real"))
    comments = [c for c in gh.calls if c[:2] == ["gh", "api"] and c[2].endswith("/comments")]
    assert len(comments) == 1 and "repro: pytest t" in comments[0][-1]
    gh.pr(1, sha="c" * 40, runs=[("full-suite", "failure")])  # a new push
    step(gh, state, failing("real"))
    assert len([c for c in gh.calls if c[:2] == ["gh", "api"]]) == 2


def test_dirty_pr_gets_one_note():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, mergeable=False, mstate="dirty", runs=[("squid", "action_required")])
    step(gh, state, failing("dirty", run_id=None))
    step(gh, state, failing("dirty", run_id=None))
    notes = [c for c in gh.calls if c[:2] == ["gh", "api"]]
    assert len(notes) == 1 and "Merge `origin/main`" in notes[0][-1]
    assert not any(c[:3] == ["gh", "run", "rerun"] for c in gh.calls)


def test_a_stacked_pr_waits_for_its_base():
    gh, state = Gh(), {"queue": [1, 2], "after": {"2": 1}, "seen": {}}
    gh.pr(1, runs=[("ruff-audit", None)])
    gh.pr(2, sha="b" * 40, runs=[("ruff-audit", "success")])
    assert "#2 waits for #1" in step(gh, state) and state["queue"] == [1, 2]


def test_one_run_at_a_time(tmp_path, monkeypatch):
    import fcntl

    monkeypatch.setattr(cs, "STATE", tmp_path / "s.json")
    with open(tmp_path / "s.run.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert cs.main(["run", "--once"]) == 1
    assert cs.main(["add", "5", "6", "--after", "5"]) == 0
    assert cs.load(tmp_path / "s.json")["queue"] == [5, 6]
