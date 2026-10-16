"""flake_history: which CI jobs failed and then passed on a rerun of the same run, learned from GitHub's attempts."""

import subprocess
from datetime import date

try:
    from squid_bot import flake_history as fh
except ImportError:  # GitGalaxy: tests/tools on the path
    import flake_history as fh


def job(name, attempt, conclusion):
    return {"name": name, "run_attempt": attempt, "conclusion": conclusion}


def test_rerun_verdicts_keep_only_jobs_that_failed_before_their_latest_attempt():
    jobs = [job("smoke", 1, "failure"), job("smoke", 2, "success"),  # rescued
            job("suite 2/3", 1, "failure"), job("suite 2/3", 2, "failure"),  # failed again
            job("lint", 1, "success"),  # never failed: no evidence
            job("muninn", 1, "failure"), job("muninn", 2, "cancelled")]  # latest attempt says nothing
    assert {k: v[0] for k, v in fh.rerun_verdicts(jobs).items()} == {"smoke": True, "suite 2/3": False}


def test_each_flaky_job_carries_why_its_first_attempt_failed(monkeypatch):
    class Stats:
        @staticmethod
        def classify(jobs):
            return "registry_pull" if jobs[0]["name"].startswith("db2") else "test_failure"

    monkeypatch.setattr(fh, "ci_rerun_stats", Stats)
    v = fh.rerun_verdicts([job("db2 1/4", 1, "failure"), job("db2 1/4", 2, "success")])
    assert v == {"db2 1/4": (True, "registry_pull")}
    data = {"days": {"d1": {"db2 1/4": [2, 0, {"registry_pull": 2}]}, "d2": {"db2 1/4": [1, 0, {"db2_start": 1}]},
                     "d3": {"old": [3, 0]}}}  # a cache row from before causes were kept
    rows = {r["job"]: r for r in fh.tally(data)}
    assert rows["db2 1/4"]["causes"] == {"registry_pull": 2, "db2_start": 1} and rows["old"]["causes"] == {}


def test_refresh_caches_finished_days_and_tally_learns_only_repeat_rescues(tmp_path):
    calls = []

    def api(path):
        calls.append(path)
        if "/actions/runs?created=" in path:
            day = path.split("created=")[1][:10]
            return {"workflow_runs": [{"id": int(day[-2:]), "run_attempt": 2, "status": "completed"}] if "T00:" in path else []}
        return {"jobs": [job("smoke", 1, "failure"), job("smoke", 2, "success"),
                         job("suite", 1, "failure"), job("suite", 2, "failure")]}

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

    rows = [{"job": "smoke", "passed_on_rerun": 3, "failed_again": 0, "learned_flaky": True},
            {"job": "det", "passed_on_rerun": 2, "failed_again": 1, "learned_flaky": True},
            {"job": "suite", "passed_on_rerun": 0, "failed_again": 4, "learned_flaky": False}]
    fh.file_issues(rows, run)
    created = [c for c in calls if c[:3] == ["gh", "issue", "create"]]
    assert [c[c.index("--title") + 1] for c in created] == ["Flaky CI job: det"]
