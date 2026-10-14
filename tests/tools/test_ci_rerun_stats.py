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
    ([_job("det", "failure", steps=[("Run tests", "failure")])], "other"),
    ([_job("det", "success")], "none"),
    ([], "none"),
]


@pytest.mark.parametrize(("jobs", "want"), CASES)
def test_classify(jobs, want):
    assert s.classify(jobs, {"ground-truth": 20}) == want


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
    job = text.split("\n  ground-truth:\n", 1)[1].split("\n  publish-history:", 1)[0]
    cap = int(re.search(r"timeout-minutes:\s*(\d+)", job).group(1))
    assert cap >= 30, "#5137: slow runners took 20+ min; a 20 min cap cancelled the job at 99% of pytest"
    assert "--durations=" in job
