"""flake_history: which CI jobs failed and then passed on a rerun of the same run, learned from GitHub's attempts."""

import subprocess
from datetime import date

import flake_history as fh


def job(name, attempt, conclusion):
    return {"name": name, "run_attempt": attempt, "conclusion": conclusion}


def test_rerun_verdicts_keep_only_jobs_that_failed_before_their_latest_attempt():
    jobs = [
        job("smoke", 1, "failure"),
        job("smoke", 2, "success"),  # rescued
        job("suite 2/3", 1, "failure"),
        job("suite 2/3", 2, "failure"),  # failed again
        job("lint", 1, "success"),  # never failed: no evidence
        job("muninn", 1, "failure"),
        job("muninn", 2, "cancelled"),
    ]  # latest attempt says nothing
    assert {k: v[0] for k, v in fh.rerun_verdicts(jobs).items()} == {"smoke": True, "suite 2/3": False}


def test_each_flaky_job_carries_why_its_first_attempt_failed(monkeypatch):
    class Stats:
        @staticmethod
        def classify(jobs, logs=None):
            return "registry_pull" if jobs[0]["name"].startswith("db2") else "test_failure"

        @staticmethod
        def scope_jobs(j, _attempt_jobs):
            return [j]

    monkeypatch.setattr(fh, "ci_rerun_stats", Stats)
    v = fh.rerun_verdicts([job("db2 1/4", 1, "failure"), job("db2 1/4", 2, "success")])
    assert v == {"db2 1/4": (True, "registry_pull")}
    data = {
        "days": {
            "d1": {"db2 1/4": [2, 0, {"registry_pull": 2}]},
            "d2": {"db2 1/4": [1, 0, {"db2_start": 1}]},
            "d3": {"old": [3, 0]},
        }
    }  # a cache row from before causes were kept
    rows = {r["job"]: r for r in fh.tally(data)}
    assert rows["db2 1/4"]["causes"] == {"registry_pull": 2, "db2_start": 1} and rows["old"]["causes"] == {}


def test_refresh_caches_finished_days_and_tally_learns_only_repeat_rescues(tmp_path):
    calls = []

    def api(path):
        calls.append(path)
        if "/actions/runs?created=" in path:
            day = path.split("created=")[1][:10]
            return {
                "workflow_runs": [{"id": int(day[-2:]), "run_attempt": 2, "status": "completed"}]
                if "T00:" in path
                else []
            }
        return {
            "jobs": [
                job("smoke", 1, "failure"),
                job("smoke", 2, "success"),
                job("suite", 1, "failure"),
                job("suite", 2, "failure"),
            ]
        }

    cache = tmp_path / "f.json"
    fh.refresh(api, cache, today=date(2026, 10, 16), days=3)
    first = len(calls)
    data = fh.refresh(api, cache, today=date(2026, 10, 16), days=3)
    assert len(calls) - first < first  # the finished day came from the cache
    rows = {r["job"]: r for r in fh.tally(data)}
    assert rows["smoke"]["passed_on_rerun"] == 3 and rows["smoke"]["learned_flaky"]
    assert not fh.tally({"days": {"d": {"det": [13, 7]}}})[0]["learned_flaky"]  # 65%: under the 80% bar (2026-10-16)
    assert rows["suite"]["failed_again"] == 3 and not rows["suite"]["learned_flaky"]
    assert fh.learned(data) == {"smoke"}
    one = {"days": {"2026-10-16": {"smoke": [1, 0]}}}
    assert fh.learned(one) == set()  # one rescue is not a pattern


def test_file_issues_skips_a_job_that_already_has_an_open_issue():
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        out = "Flaky CI job: smoke\n" if argv[:3] == ["gh", "issue", "list"] and "smoke" in argv[-5] else ""
        return subprocess.CompletedProcess(argv, 0, out, "")

    rows = [
        {"job": "smoke", "passed_on_rerun": 3, "failed_again": 0, "learned_flaky": True},
        {"job": "det", "passed_on_rerun": 2, "failed_again": 1, "learned_flaky": True},
        {"job": "suite", "passed_on_rerun": 0, "failed_again": 4, "learned_flaky": False},
    ]
    fh.file_issues(rows, run)
    created = [c for c in calls if c[:3] == ["gh", "issue", "create"]]
    assert [c[c.index("--title") + 1] for c in created] == ["Flaky CI job: det"]


def test_default_cache_follows_ci_shepherd_state_and_needs_no_squid_bot(monkeypatch, tmp_path):
    monkeypatch.setenv("CI_SHEPHERD_STATE", str(tmp_path / "ci_shepherd.json"))
    assert fh.default_cache() == tmp_path / "flake_history.json"
    monkeypatch.delenv("CI_SHEPHERD_STATE")
    assert fh.default_cache().parts[-3:] == (".cache", "gitgalaxy", "flake_history.json")


def test_no_squid_bot_reference_in_the_shepherd_tools():
    from pathlib import Path

    tools = Path(__file__).resolve().parent
    banned = "squid" + "_bot"
    for p in [*tools.glob("*.py"), *(tools / "box").glob("*.py")]:
        if p.name == Path(__file__).name:
            continue
        assert banned not in p.read_text(encoding="utf-8"), p.name


def test_a_refresh_out_of_time_keeps_its_days_stays_stale_and_the_next_one_carries_on(tmp_path, monkeypatch):
    """2026-10-20: a cold 14-day fetch never fit the reconcile step's timeout, saved nothing, and every pass restarted."""
    fetched = []
    monkeypatch.setattr(fh, "day_reruns", lambda api, d: fetched.append(d) or {"smoke": [1, 0, {}]})
    clock = iter(range(0, 1000, 100)).__next__  # every clock() call is 100 s later
    cache = tmp_path / "f.json"
    data = fh.refresh(None, cache, today=date(2026, 10, 20), days=5, budget_s=350, clock=clock)
    assert fetched == ["2026-10-20", "2026-10-19", "2026-10-18"]  # missing days, newest first, until the budget
    saved = fh.load(cache)
    assert sorted(saved["days"]) == ["2026-10-18", "2026-10-19", "2026-10-20"] and "updated" not in saved
    assert data["days"] == saved["days"]
    fetched.clear()
    clock = iter(range(0, 1000, 100)).__next__
    data = fh.refresh(None, cache, today=date(2026, 10, 20), days=5, budget_s=350, clock=clock)
    # the two still-missing days first, then today again; yesterday is left for the next pass
    assert fetched == ["2026-10-17", "2026-10-16", "2026-10-20"] and "updated" not in fh.load(cache)
    fetched.clear()
    data = fh.refresh(
        None, cache, today=date(2026, 10, 20), days=5, budget_s=350, clock=iter(range(0, 1000, 100)).__next__
    )
    assert fetched == ["2026-10-20", "2026-10-19"]  # warm: only today and yesterday, inside the budget
    assert fh.load(cache)["updated"] and len(data["days"]) == 5


def test_a_killed_refresh_keeps_every_finished_day(tmp_path, monkeypatch):
    def day(api, d):
        if d == "2026-10-18":
            raise TimeoutError("the step's timeout")
        return {"det": [0, 1, {}]}

    monkeypatch.setattr(fh, "day_reruns", day)
    cache = tmp_path / "f.json"
    try:
        fh.refresh(None, cache, today=date(2026, 10, 20), days=4)
    except TimeoutError:
        pass
    assert sorted(fh.load(cache)["days"]) == ["2026-10-19", "2026-10-20"]
    assert "updated" not in fh.load(cache)


def test_a_failed_db2_step_whose_log_shows_a_pull_failure_is_registry_pull_not_db2_start():  # #5603
    failed = {
        **job("db2 1/4", 1, "failure"),
        "id": 7,
        "steps": [{"name": "Wait for the first Db2 database", "conclusion": "failure"}],
    }
    jobs = [failed, job("db2 1/4", 2, "success")]
    asked = []

    def log(j):
        asked.append(j["id"])
        return "x " + fh.ci_rerun_stats.PULL_MARKER

    assert fh.rerun_verdicts(jobs, log) == {"db2 1/4": (True, "registry_pull")}
    assert fh.rerun_verdicts(jobs) == {"db2 1/4": (True, "db2_start")}  # no log reader: the old reading
    assert asked == [7]  # one log, for the failed Db2 job only


def _steps(*pairs):
    return [{"name": n, "conclusion": c} for n, c in pairs]


def test_a_gate_job_is_attributed_to_the_part_that_failed():
    jobs = [
        {**job("ground-truth", 1, "failure"), "steps": _steps(("Every part passed", "failure"))},
        {**job("part 4/4", 1, "failure"), "steps": _steps(("Per-test time ratchet (#5166)", "failure"))},
        job("ground-truth", 2, "success"),
    ]
    assert fh.rerun_verdicts(jobs)["ground-truth"] == (True, "ratchet")


def test_a_rerun_of_a_superseded_run_is_not_counted_as_a_rescue():
    def api(path):
        if "/actions/runs?created=" in path:
            return {"workflow_runs": [{"id": 1, "run_attempt": 2, "status": "completed"}] if "T00:" in path else []}
        return {
            "jobs": [
                {**job("ground-truth", 1, "failure"), "steps": _steps(("Every part passed", "failure"))},
                job("plan", 1, "cancelled"),
                job("ground-truth", 2, "success"),
            ]
        }

    assert fh.day_reruns(api, "2026-10-16") == {}
