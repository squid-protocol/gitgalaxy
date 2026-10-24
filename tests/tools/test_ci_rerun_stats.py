"""#5137: tests/tools/ci_rerun_stats.py and the timeout pin on the Mainframe Ground Truth job."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_rerun_stats as s

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _job(name, conclusion, secs=60, steps=()):
    return {
        "name": name,
        "conclusion": conclusion,
        "started_at": "2026-10-14T14:00:00Z",
        "completed_at": f"2026-10-14T14:{secs // 60:02d}:{secs % 60:02d}Z",
        "steps": [{"name": n, "conclusion": c} for n, c in steps],
    }


CASES = [
    ([_job("ground-truth", "cancelled", 20 * 60 + 15)], "timeout"),
    ([_job("ground-truth", "cancelled", 5 * 60)], "other"),  # cancelled early: a person or a newer push
    ([_job("x", "timed_out")], "timeout"),
    ([_job("db2 3/4", "failure", steps=[("Wait for the background Db2 start", "failure")])], "db2_start"),
    ([_job("det", "failure", steps=[("Apply the ratchet to the merged sweep", "failure")])], "ratchet"),
    ([_job("det", "failure", steps=[("Run tests", "failure")])], "test_failure"),
    ([_job("det", "failure", steps=[("Build the port", "failure")])], "other"),
    ([_job("p", "failure", steps=[("Download the history", "failure")])], "artifact_missing"),
    ([_job("p", "failure", steps=[("Full-corpus differential and answer-key tests", "failure")])], "test_failure"),
    ([_job("p", "failure", steps=[("Run pytest", "failure")])], "test_failure"),
    ([_job("det", "success")], "none"),
    ([], "none"),
]


@pytest.mark.parametrize(("jobs", "want"), CASES)
def test_classify(jobs, want):
    assert s.classify(jobs, {"ground-truth": 20}) == want


def test_step_secs_picks_the_named_step_and_skips_skipped():
    def j(steps):
        return {
            "steps": [{"name": n, "conclusion": "success", "started_at": a, "completed_at": b} for n, a, b in steps]
        }

    jobs = [
        j([("Is the generated Java unchanged? (pull requests)", "2026-10-14T14:00:00Z", "2026-10-14T14:03:20Z")]),
        j(
            [
                ("Is the generated Java unchanged?", "2026-10-14T14:00:00Z", "2026-10-14T14:00:45Z"),
                ("Other", "2026-10-14T14:00:00Z", "2026-10-14T14:09:00Z"),
            ]
        ),
    ]
    jobs.append({"steps": [{"name": "Is the generated Java unchanged?", "conclusion": "skipped"}]})
    assert s.step_secs(jobs, "generated java unchanged") == [200.0, 45.0]
    assert s.step_secs([], "x") == []
    running = {"steps": [{"name": "x", "conclusion": None, "started_at": "2026-10-14T14:00:00Z", "completed_at": None}]}
    assert s.step_secs([running], "x") == [0.0]  # an unfinished step is 0, not a crash


_DB2 = _job("db2 4/4", "failure", steps=[("Wait for the background Db2 start", "failure")])


@pytest.mark.parametrize(
    ("logs", "want"),
    [
        ({"db2 4/4": f"Db2ImagePullError: {s.PULL_MARKER} the pinned Db2 image"}, "registry_pull"),
        ({"db2 4/4": "Db2 did not become ready"}, "db2_start"),  # a start failure that is not a pull
        ({"other job": s.PULL_MARKER}, "db2_start"),  # the marker is in a different job's log
        ({}, "db2_start"),
        (None, "db2_start"),
    ],
)
def test_pull_marker_in_the_failed_jobs_log(logs, want):
    assert s.classify([_DB2], logs=logs) == want


def test_log_never_overrides_a_timeout_or_a_non_db2_step():
    marker = {"ground-truth": s.PULL_MARKER, "det": s.PULL_MARKER}
    assert s.classify([_job("ground-truth", "cancelled", 20 * 60 + 15)], {"ground-truth": 20}, marker) == "timeout"
    assert s.classify([_job("det", "failure", steps=[("Run tests", "failure")])], logs=marker) == "test_failure"


def test_db2_logs_reads_only_failed_db2_steps(monkeypatch):
    calls = []

    def fake_gh(path, *_flags):
        calls.append(path)
        return "log text"

    monkeypatch.setattr(s, "_gh_text", fake_gh)
    ok = {"id": 1, "name": "shard 1/6", "steps": [{"name": "Run tests", "conclusion": "failure"}]}
    bad = {"id": 2, **_DB2}
    assert s._db2_logs([ok, bad]) == {"db2 4/4": "log text"}
    assert calls == [f"repos/{s.REPO}/actions/jobs/2/logs"]


def test_cap_unknown_is_not_a_timeout():
    assert s.classify([_job("ground-truth", "cancelled", 20 * 60 + 15)]) == "other"


def test_per_day_counts_extra_attempts_only():
    runs = [
        {"created_at": "2026-10-13T23:59:00Z", "run_attempt": 1},
        {"created_at": "2026-10-14T01:00:00Z", "run_attempt": 3},
        {"created_at": "2026-10-14T09:00:00Z", "run_attempt": 2},
    ]
    assert s.per_day(runs) == {"2026-10-14": 3}
    assert s.per_day([]) == {}


def test_ground_truth_job_has_headroom_over_slow_runners():
    text = (WORKFLOWS / "mainframe-ground-truth.yml").read_text(encoding="utf-8")
    # #5133: the work is in the parts; `ground-truth` itself only aggregates them
    job = text.split("\n  ground-truth-part:\n", 1)[1].split("\n  publish-history:", 1)[0]
    cap = int(re.search(r"timeout-minutes:\s*(\d+)", job).group(1))
    assert cap >= 30, "#5137: slow runners took 20+ min; a 20 min cap cancelled the job at 99% of pytest"
    assert "--durations=" in job


def test_workflow_runs_pages_until_a_short_page(monkeypatch):  # #5603
    pages = {1: 100, 2: 100, 3: 7}
    seen = []

    def fake_gh(path):
        n = int(re.search(r"&page=(\d+)", path).group(1))
        seen.append(n)
        return {"workflow_runs": [{"id": i} for i in range(pages[n])]}

    monkeypatch.setattr(s, "_gh", fake_gh)
    assert len(s.workflow_runs("det-sweep.yml", "2026-10-09")) == 207
    assert seen == [1, 2, 3]


GATE = ("Every part passed", "failure")


def _gate(attempt=1):
    j = _job("ground-truth", "failure", 3, steps=[("Set up job", "success"), GATE])
    return {**j, "run_attempt": attempt}


def _sib(name, conclusion, steps=(), attempt=1, secs=1):
    return {**_job(name, conclusion, secs, steps), "run_attempt": attempt}


def test_a_gate_is_told_apart_from_a_job_with_a_real_failed_step():
    assert s.is_gate(_gate())
    assert not s.is_gate(_job("det", "failure", steps=[("Run tests", "failure")]))
    assert not s.is_gate(_job("det", "failure"))  # no failed step: not a gate


def test_a_gate_takes_the_cause_of_the_failed_parts_of_its_attempt():
    part = _sib("part 4/4", "failure", [("Per-test time ratchet (#5166)", "failure")])
    other_attempt = _sib("part 1/4", "failure", [("Run pytest", "failure")], attempt=2)
    gate = _gate()
    scope = s.scope_jobs(gate, [gate, part, other_attempt])
    assert [j["name"] for j in scope] == ["ground-truth", "part 4/4"]
    assert s.classify(scope) == "ratchet"
    assert s.classify([_gate()]) == "other"  # alone, a gate says nothing


def test_a_non_gate_is_classified_by_itself_only():
    job = _job("det", "failure", steps=[("Build the port", "failure")])
    assert s.scope_jobs(job, [_sib("x", "failure", [("Run tests", "failure")])]) == [job]


def test_a_gate_failing_over_cancelled_parts_is_superseded_not_other():
    parts = [_sib("plan", "cancelled"), _sib("part 1/2", "cancelled")]
    assert s.classify(s.scope_jobs(_gate(), parts)) == "superseded"


def test_cancelled_parts_at_their_timeout_are_still_a_timeout():
    parts = [_sib("part 1/2", "cancelled", secs=20 * 60 + 5)]
    assert s.classify(s.scope_jobs(_gate(), parts), {"part 1/2": 20}) == "timeout"


def test_a_real_failed_part_beside_a_cancelled_one_is_not_superseded():
    parts = [_sib("part 1/2", "cancelled"), _sib("part 2/2", "failure", [("Run pytest", "failure")])]
    assert s.classify(s.scope_jobs(_gate(), parts)) == "test_failure"


_WAIT = f"##[error]Db2::{s.WAIT_FAILED_MARKER}"


@pytest.mark.parametrize(
    ("log", "want"),
    [
        (f"gitgalaxy-db2 Exited (1) 3 minutes ago\n{_WAIT}", "db2_start_exited"),
        (f"Error response from daemon: No such container: gitgalaxy-db2\n{_WAIT}", "db2_start_not_created"),
        (f"tee: write error: No space left on device\ngitgalaxy-db2 Exited (1) ago\n{_WAIT}", "db2_start_disk"),
        (f"gitgalaxy-db2 Up 14 minutes\n(*) Setting up instance\n{_WAIT}", "db2_start_setup_incomplete"),
        (f"gitgalaxy-db2 Up 14 minutes\nSetup has completed.\n{_WAIT}", "db2_start"),
        ("gitgalaxy-db2 Exited (1) ago", "db2_start"),  # no wait-step marker: another step's log, never sub-classified
        ("", "db2_start"),
        (f"{s.PULL_MARKER}\n{_WAIT}\nExited (", "registry_pull"),
    ],
)
def test_db2_start_cause_reads_the_docker_tail(log, want):
    assert s.db2_start_cause(log) == want
    assert s.classify([_DB2], logs={"db2 4/4": log}) == want
