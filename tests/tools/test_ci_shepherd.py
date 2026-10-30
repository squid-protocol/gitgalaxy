"""ci_shepherd (#4790): one pass's decisions, against a fake GitHub -- merge when green, rerun infra once, comment once."""

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fcntl")  # the shepherd locks with flock: a Linux/macOS box tool (Windows has no fcntl)

sys.path.insert(0, str(Path(__file__).resolve().parent / "box"))
import ci_shepherd as cs  # noqa: E402


class Gh:
    """A fake `gh api` for pr_check.check, plus a recorder for the commands the shepherd runs."""

    def __init__(self):
        self.prs, self.runs, self.calls = {}, {}, []

    def pr(self, n, sha="a" * 40, state="open", mergeable=True, mstate="clean", runs=(), draft=False):
        self.prs[n] = {"number": n, "title": f"pr {n}", "state": state, "merged": state == "merged", "draft": draft,
                       "head": {"sha": sha}, "node_id": f"N{n}", "mergeable": mergeable, "mergeable_state": mstate}  # fmt: skip
        self.runs[sha] = [{"id": i, "name": name, "status": "completed" if c else "in_progress", "conclusion": c,
                           "app": {"slug": "github-actions"}} for i, (name, c) in enumerate(runs, 1)]  # fmt: skip

    required = ["det", "full-suite"]
    rules_ok = True

    def api(self, path):
        if path.endswith("/rules/branches/main"):
            if not self.rules_ok:
                raise SystemExit("gh api failed")
            return [{"type": "required_status_checks",
                     "parameters": {"required_status_checks": [{"context": c} for c in self.required]}}]  # fmt: skip
        parts = path.split("?")[0].split("/")
        if "check-runs" in parts:
            return {"check_runs": self.runs[parts[-2]]}
        if parts[-2:] == ["commits", "main"]:
            return {"sha": "m" * 40}
        if parts[-1] == "status":
            return {"statuses": []}
        if parts[-1] == "files":
            return []
        return self.prs[int(parts[-1])]

    def run(self, argv):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")


def failing(kind, run_id=99, check="full-suite"):
    return lambda n: {"number": n, "head_sha": "x", "mergeable_state": "clean",
                      "failed": [{"check": check, "conclusion": "failure", "url": "u", "run_id": run_id,
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


def test_green_draft_is_marked_ready_not_reported_as_a_failed_merge():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, draft=True, runs=[("ruff-audit", "success")])
    did = step(gh, state)
    assert any("marked ready" in d for d in did) and not any("merge failed" in d for d in did)
    assert state["queue"] == [1]  # stays queued: a later pass merges once its CI is green
    assert [c[:3] for c in gh.calls] == [["gh", "pr", "ready"]]
    gh.prs[1]["draft"] = False  # the next pass sees it ready
    did = step(gh, state)
    assert any("MERGED" in d for d in did) and state["queue"] == []
    assert ["gh", "pr", "merge"] == gh.calls[-1][:3]


def test_a_draft_that_cannot_be_marked_ready_still_reports_failure():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, draft=True, runs=[("ruff-audit", "success")])
    gh.run = lambda argv: subprocess.CompletedProcess(argv, 1, "", "boom")
    did = step(gh, state)
    assert any("merge failed" in d for d in did) and state["queue"] == [1]


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
    state["seen"]["1"]["rerun:run:99"][-1] -= cs.RETRY_GAP
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


def test_a_failure_main_has_too_gets_no_pr_note():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, runs=[("full-suite", "failure")])
    did = step(gh, state, failing("main"))
    assert any("waits for main" in d for d in did) and gh.calls == []


def test_a_non_required_infra_failure_stops_blocking_once_its_reruns_are_used_up(monkeypatch):
    gh, state, clock = Gh(), {"queue": [1], "after": {}, "seen": {}}, [1000.0]
    monkeypatch.setattr(cs, "now", lambda: clock[0])
    gh.pr(1, runs=[("muninn", "failure"), ("det", "success")])
    for _ in range(cs.INFRA_RETRIES):
        step(gh, state, failing("infra", check="muninn"))
        clock[0] += cs.RETRY_GAP
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in gh.calls)  # still rerunning
    did = step(gh, state, failing("infra", check="muninn"))
    assert any("MERGED past non-required infra" in d for d in did) and state["queue"] == []


def test_a_required_or_real_failure_or_unknown_rules_never_merges_past(monkeypatch):
    for check, kind, rules_ok in (("full-suite", "infra", True), ("muninn", "real", True), ("muninn", "infra", False)):
        gh, state, clock = Gh(), {"queue": [1], "after": {}, "seen": {}}, [1000.0]
        gh.rules_ok = rules_ok
        monkeypatch.setattr(cs, "now", lambda: clock[0])
        gh.pr(1, runs=[(check, "failure")])
        for _ in range(cs.INFRA_RETRIES + 2):
            step(gh, state, failing(kind, check=check))
            clock[0] += cs.RETRY_GAP
        assert not any(c[:3] == ["gh", "pr", "merge"] for c in gh.calls), (check, kind, rules_ok)


def test_run_keeps_watching_an_empty_queue_unless_told(tmp_path, monkeypatch):
    """2026-10-09: the shepherd exited on an empty queue, so a PR queued minutes later sat green and unmerged."""
    monkeypatch.setattr(cs, "STATE", tmp_path / "s.json")
    sleeps = []
    monkeypatch.setattr(cs.time, "sleep", lambda s: (sleeps.append(s), (_ for _ in ()).throw(KeyboardInterrupt))[1])
    monkeypatch.setattr(cs, "step", lambda state, api=None, **kw: [])
    assert cs.main(["run", "--exit-when-empty"]) == 0 and sleeps == []
    try:
        cs.main(["run", "--every", "5"])
    except KeyboardInterrupt:
        pass
    assert sleeps == [5]  # an empty queue: it slept and would pass again


def test_a_green_pr_behind_main_is_never_updated_by_the_shepherd():
    """#5134: a push to a ready PR restarts its CI; being behind main is no reason for one."""
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, mstate="behind", runs=[("ruff-audit", "success")])
    did = step(gh, state)
    assert any(d.startswith("#1 behind main, not updated") for d in did), did
    step(gh, state)
    assert gh.calls == [] and state["queue"] == [1]


def test_a_behind_pr_is_not_updated_pending_or_failed_either():
    for runs, fail in ((("ruff-audit", None),), None), ((("full-suite", "failure"),), failing("real")):
        gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
        gh.pr(1, mstate="behind", runs=list(runs))
        step(gh, state, *([fail] if fail else []))
        assert not any(c[:3] == ["gh", "pr", "update-branch"] for c in gh.calls)


def test_a_cancelled_non_required_matrix_leg_is_rerun_once_and_logged(monkeypatch):
    """#4790 / PR #4837 (2026-10-10): two CANCELLED `full-suite-matrix (macos-...)` legs were never rerun and the pass
    logged nothing. The check name holds a ` (` of its own, which the digest used to cut at the first one."""
    gh, state, clock = Gh(), {"queue": [1], "after": {}, "seen": {}}, [1000.0]
    monkeypatch.setattr(cs, "now", lambda: clock[0])
    gh.pr(1, mstate="unstable", runs=[("full-suite-matrix (macos-14)", "cancelled"),
                                     ("full-suite-matrix (ubuntu)", "success")])  # fmt: skip
    for r in gh.runs["a" * 40]:
        r["details_url"] = f"https://github.com/squid-protocol/gitgalaxy/actions/runs/{100 + r['id']}/job/{r['id']}"
    gh.runs["m" * 40] = []  # main's newest commit: nothing failing there
    digest = lambda n: cs.ci_digest.digest(n, gh.api, logs=lambda job: "")  # noqa: E731
    did = cs.step(state, gh.api, gh.run, digest, settle=0)
    reruns = [c for c in gh.calls if c[:3] == ["gh", "run", "rerun"]]
    assert reruns == [["gh", "run", "rerun", "101", "--failed", "-R", cs.REPO_SLUG]]
    assert any("rerun full-suite-matrix (macos-14) (infra): ok" in d for d in did), did
    # the next pass, inside RETRY_GAP: a log line, no second rerun
    clock[0] += 60
    did = cs.step(state, gh.api, gh.run, digest, settle=0)
    assert len([c for c in gh.calls if c[:3] == ["gh", "run", "rerun"]]) == 1
    assert any(d.startswith("#1 blocked: full-suite-matrix (macos-14) (infra) -- no action:") for d in did), did


def test_a_pass_that_would_be_silent_logs_the_pr_state(monkeypatch):
    """Every queued PR gets a line per pass, a behind one included."""
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, mstate="behind", runs=[("ruff-audit", "success")])
    step(gh, state)
    did = step(gh, state)
    assert did and did[0].startswith("#1 behind main, not updated"), did


def test_matrix_legs_of_one_run_share_one_rerun_and_one_budget():
    gh, state = Gh(), {"queue": [1], "after": {}, "seen": {}}
    gh.pr(1, runs=[("full-suite (1/2)", "failure"), ("full-suite (2/2)", "failure")])
    two_legs = failing("infra")

    def digest(n):
        d = two_legs(n)
        d["failed"] = [{**d["failed"][0], "check": f"full-suite ({i}/2)"} for i in (1, 2)]
        return d

    did = step(gh, state, digest)
    assert [c[:4] for c in gh.calls if c[:3] == ["gh", "run", "rerun"]] == [["gh", "run", "rerun", "99"]]
    assert any("shared run 99" in d for d in did)
    assert len(state["seen"]["1"]["rerun:run:99"]) == 1


def test_fixer_waits_for_a_green_box_but_the_digest_posts_at_once(monkeypatch, tmp_path):
    gh, state, verdict, started = Gh(), {"queue": [1], "after": {}, "seen": {}}, ["RED"], []
    gh.pr(1, runs=[("full-suite", "failure")])
    monkeypatch.setenv("CI_SHEPHERD_FIXER", "fix-it")
    monkeypatch.setattr(cs, "STATE", tmp_path / "shepherd.json")
    monkeypatch.setattr(cs, "box_verdict", lambda: verdict[0])
    monkeypatch.setattr(cs.subprocess, "Popen", lambda argv, **kw: started.append(argv))
    did = step(gh, state, failing("real"))
    assert any("digest posted" in d for d in did) and any("fixer deferred: box is RED" in d for d in did)
    assert started == []
    verdict[0] = "GREEN"
    did = step(gh, state, failing("real"))
    assert len(started) == 1 and started[0][:2] == ["fix-it", "1"]
    assert not any("digest posted" in d for d in did)  # the comment is not repeated
    step(gh, state, failing("real"))
    assert len(started) == 1  # one fixer per head
    assert [e["event"] for e in state["ledger"]] == ["real_failure", "fixer_deferred", "fixer_started"]


def test_main_failures_keeps_the_last_known_verdict_while_main_tip_is_still_running():
    ci_digest = cs.ci_digest

    def run(name, conclusion=None):
        return {"id": 1, "name": name, "status": "completed" if conclusion else "in_progress", "conclusion": conclusion}

    docs = {
        "main": {"sha": "t", "parents": [{"sha": "p"}]},
        "t/check-runs": {"check_runs": [run("lint", "success"), run("full-suite")]},
        "p": {"sha": "p", "parents": []},
        "p/check-runs": {"check_runs": [run("lint", "failure"), run("full-suite", "failure")]},
    }

    def api(path):
        return docs[path.split("/commits/", 1)[1].split("?")[0]]

    assert ci_digest.main_failures(api) == {"full-suite"}  # lint passed on the tip: the tip's verdict wins


def test_a_learned_flake_gets_one_rerun_on_its_first_attempt_only():
    ci_digest = cs.ci_digest
    attempt = [1]

    def api(path):
        if path.endswith("/commits/main"):
            return {"sha": "m", "parents": []}
        if "/commits/m/check-runs" in path:
            return {"check_runs": []}
        if "/check-runs" in path:
            return {
                "check_runs": [
                    {
                        "id": 1,
                        "name": "smoke",
                        "status": "completed",
                        "conclusion": "failure",
                        "details_url": "https://github.com/o/r/actions/runs/7/job/8",
                    }
                ]
            }
        if "/actions/jobs/8" in path:
            return {"run_attempt": attempt[0]}
        return {"head": {"sha": "h"}, "mergeable_state": "clean"}

    def triage(flaky):
        return ci_digest.digest(1, api, logs=lambda i: "FAILED tests/t.py::test_x", flaky=flaky)["failed"][0]["triage"]

    assert triage(set()) == "real"
    assert triage({"smoke"}) == "flake"
    attempt[0] = 2  # the rerun failed too: real
    assert triage({"smoke"}) == "real"


def test_one_fixer_per_pass_and_the_pr_others_wait_on_goes_first(monkeypatch, tmp_path):
    gh, started = Gh(), []
    state = {"queue": [1, 2, 3], "after": {"3": 2}, "seen": {}}
    for n in (1, 2):
        gh.pr(n, sha=str(n) * 40, runs=[("full-suite", "failure")])
    gh.pr(3, sha="3" * 40, runs=[("full-suite", None)])  # #3 waits on #2 (--after): #2 is the most useful fix
    monkeypatch.setenv("CI_SHEPHERD_FIXER", "fix-it")
    monkeypatch.setattr(cs, "STATE", tmp_path / "shepherd.json")
    reads = []
    monkeypatch.setattr(cs, "box_verdict", lambda: reads.append(1) or "GREEN")
    monkeypatch.setattr(cs.subprocess, "Popen", lambda argv, **kw: started.append(argv[1]))
    did = step(gh, state, failing("real"))
    assert started == ["2"] and len(reads) == 1
    assert any("#1 fixer queued" in d for d in did)
    step(gh, state, failing("real"))
    assert started == ["2", "1"]


def test_a_stale_flake_cache_is_refreshed_in_the_background_at_most_hourly(monkeypatch, tmp_path):
    spawned = []
    monkeypatch.setattr(cs, "STATE", tmp_path / "shepherd.json")
    monkeypatch.setattr(cs.subprocess, "Popen", lambda argv, **kw: spawned.append(argv))
    state = {}
    assert cs.learned_flakes(state, t=100_000.0) == set()
    assert cs.learned_flakes(state, t=100_600.0) == set()
    assert len(spawned) == 1 and "--refresh-only" in spawned[0]
    (tmp_path / "flake_history.json").write_text('{"updated": 100700, "days": {"d": {"smoke": [2, 0]}}}')
    assert cs.learned_flakes(state, t=110_000.0) == {"smoke"} and len(spawned) == 1


def test_box_verdict_reads_gitgalaxy_box_status(monkeypatch):
    import box_status

    if not Path("/proc/meminfo").exists():
        pytest.skip("no /proc/meminfo")
    monkeypatch.setattr(box_status, "snapshot", lambda sample=0.1: {"verdict": "RED"})
    assert cs.box_verdict() == "RED"


def _main_tip_graphql(failed_names, seen):
    nodes = [{"databaseId": i, "name": n, "status": "COMPLETED", "conclusion": "FAILURE", "detailsUrl": "u", "url": "u"}
             for i, n in enumerate(failed_names, 1)]  # fmt: skip
    suite = {
        "createdAt": None,
        "app": {"slug": "github-actions"},
        "checkRuns": {"totalCount": len(nodes), "nodes": nodes},
    }
    tip = {"oid": "m" * 40, "parents": {"nodes": []}, "checkSuites": {"totalCount": 1, "nodes": [suite]}}

    def graphql(query, variables):
        seen.append(query)
        return {"repository": {"ref": {"target": tip}}}

    return graphql


def _pass_with_default_digest(monkeypatch, graphql, rest_calls):
    """One pass over three failing PRs through the shepherd's own digest; returns main_failures' answers."""
    ci_digest = cs.ci_digest
    asked = []
    monkeypatch.setattr(
        ci_digest, "digest", lambda n, api, on_main, flaky, graphql=None: asked.append(on_main) or {"failed": []}
    )
    gh = Gh()
    state = {"queue": [1, 2, 3], "after": {}, "seen": {}, "events": []}
    for n in (1, 2, 3):
        gh.pr(n, sha=str(n) * 40, mstate="dirty", mergeable=False)

    def counting(path):
        rest_calls.append(path)
        return gh.api(path)

    cs.step(state, counting, gh.run, settle=0, graphql=graphql)
    return asked


def test_main_failures_is_read_once_per_pass_through_graphql_and_never_by_rest(monkeypatch):
    seen, rest = [], []
    asked = _pass_with_default_digest(monkeypatch, _main_tip_graphql(["ruff"], seen), rest)
    main_reads = [q for q in seen if q is not cs.pr_check.CHECK_QUERY]
    assert asked == [{"ruff"}] * 3 and len(main_reads) == 1  # one main query for the pass, shared by all three PRs
    assert not [p for p in rest if "/commits/main" in p or p.endswith("/check-runs") and "m" * 40 in p]


def test_a_failing_graphql_read_falls_back_to_rest_with_the_same_answer(monkeypatch):
    def broken(query, variables):
        raise SystemExit("gh api failed")

    gh = Gh()
    gh.runs["m" * 40] = [{"id": 1, "name": "ruff", "status": "completed", "conclusion": "failure"}]
    assert cs.ci_digest.main_failures(gh.api, graphql=broken) == {"ruff"} == cs.ci_digest.main_failures(gh.api)
    rest = []
    asked = _pass_with_default_digest(monkeypatch, broken, rest)
    assert len(asked) == 3 and all(isinstance(a, set) for a in asked)
    assert sum(p.endswith("/commits/main") for p in rest) == 1  # REST read once for the pass, not once per PR


def _check_graphql(gh, seen):
    """A fake GraphQL for pr_check.CHECK_QUERY built from the same Gh fixture the REST fake serves."""

    def graphql(query, variables):
        seen.append(query)
        p, n = None, variables.get("n")
        if query is cs.pr_check.CHECK_QUERY:
            p = gh.prs[n]
            nodes = [{"databaseId": r["id"], "name": r["name"], "status": r["status"].upper(),
                      "conclusion": (r["conclusion"] or "").upper() or None, "detailsUrl": "u", "url": "u"}
                     for r in gh.runs[p["head"]["sha"]]]  # fmt: skip
            suite = {"createdAt": None, "app": {"slug": "github-actions"},
                     "checkRuns": {"totalCount": len(nodes), "nodes": nodes}}  # fmt: skip
            commit = {"oid": p["head"]["sha"], "status": None,
                      "checkSuites": {"totalCount": 1, "nodes": [suite]}}  # fmt: skip
            return {"repository": {"pullRequest": {
                "id": p["node_id"], "number": n, "title": p["title"], "state": p["state"].upper(),
                "merged": p["merged"], "isDraft": p["draft"], "mergeable": "MERGEABLE" if p["mergeable"] else "CONFLICTING",
                "mergeStateStatus": p["mergeable_state"].upper(), "headRefOid": p["head"]["sha"],
                "files": {"totalCount": 0, "nodes": []}, "commits": {"nodes": [{"commit": commit}]}}}}  # fmt: skip
        raise SystemExit("gh api failed")

    return graphql


def _queue_pass(graphql):
    """One pass over three PRs (one open and failing, one pending, one merged); returns (REST paths, did)."""
    gh, rest = Gh(), []
    gh.pr(1, sha="1" * 40, mstate="dirty", mergeable=False, runs=[("det", "success")])
    gh.pr(2, sha="2" * 40, mstate="blocked", runs=[("det", None)])
    gh.pr(3, sha="3" * 40, state="closed", mstate="clean")
    state = {"queue": [1, 2, 3], "after": {}, "seen": {}, "events": []}

    def counting(path):
        rest.append(path)
        return gh.api(path)

    did = cs.step(state, counting, gh.run, lambda n: {"failed": []}, settle=0,
                  graphql=graphql(gh) if graphql else None)  # fmt: skip
    return rest, did


def test_the_per_pr_state_read_is_one_graphql_query_not_four_rest_calls():
    before, did_before = _queue_pass(None)
    seen = []
    after, did_after = _queue_pass(lambda gh: _check_graphql(gh, seen))
    check_reads = [
        p for p in after if "/pulls/" in p or "/commits/" in p and "/check-runs" in p or p.endswith("/status")
    ]
    assert not check_reads and len(seen) == 3  # one query per queued PR
    assert len(before) - len(after) >= 3 * 3  # REST: pull + runs + status + files per PR, none left
    assert did_after == did_before  # decide() and its rules see the same reads


def test_a_failing_graphql_check_read_falls_back_to_rest_with_the_same_decisions():
    def broken(gh):
        def graphql(query, variables):
            raise SystemExit("gh api failed")

        return graphql

    rest_plain, did_plain = _queue_pass(None)
    rest_broken, did_broken = _queue_pass(broken)
    assert did_broken == did_plain and sorted(rest_broken) == sorted(rest_plain)


def test_the_default_digest_reads_through_graphql_too(monkeypatch):
    got = []
    monkeypatch.setattr(cs.ci_digest, "main_failures", lambda api, graphql=None: set())
    monkeypatch.setattr(cs.ci_digest, "digest", lambda n, api, **kw: got.append(kw["graphql"]) or {"failed": []})
    gh = Gh()
    gh.pr(1, mstate="blocked", runs=[("det", "failure")])
    sentinel = _check_graphql(gh, [])
    cs.step({"queue": [1], "after": {}, "seen": {}, "events": []}, gh.api, gh.run, settle=0, graphql=sentinel)
    assert got and all(g is sentinel for g in got)


def test_run_reads_through_one_conditional_pass_cache_and_prunes_the_store(tmp_path, monkeypatch):
    """#6534: each pass gets the ETag + finished-SHA api, and the persistent store is pruned after the pass."""
    monkeypatch.setattr(cs, "STATE", tmp_path / "s.json")
    monkeypatch.setattr(cs, "API_CACHE", tmp_path / "store")
    seen, pruned = [], []
    monkeypatch.setattr(cs, "step", lambda state, api=None, **kw: seen.append(api) or [])
    monkeypatch.setattr(cs.pr_check, "prune_api_store", lambda store: pruned.append(store))
    assert cs.main(["run", "--once"]) == 0
    assert callable(seen[0]) and seen[0] is not cs.pr_check.gh_api and pruned == [tmp_path / "store"]


def test_pass_api_sends_if_none_match_and_shares_finished_commits(tmp_path, monkeypatch):
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, 'HTTP/2.0 200 OK\netag: "e1"\n\n{"sha": "x"}', "")

    monkeypatch.setattr(cs.pr_check.subprocess, "run", run)
    path = "repos/o/r/commits/" + "a" * 40
    api = cs.pass_api(tmp_path)
    assert api(path) == api(path) == {"sha": "x"} and len(calls) == 1  # a commit by sha is read once per pass
    cs.pass_api(tmp_path)(path)  # the next pass: conditional on the stored ETag
    assert 'If-None-Match: "e1"' in calls[-1]
