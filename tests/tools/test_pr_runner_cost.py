"""#6278 re-measure tool: runner-min rounding, idle runs, and the docs-only / code split."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier as cc  # noqa: E402
import pr_runner_cost as rc  # noqa: E402


def job(start, end, conclusion="success"):
    return {"conclusion": conclusion, "started_at": f"2026-10-28T{start}Z", "completed_at": f"2026-10-28T{end}Z"}


def test_a_started_minute_is_billed():
    assert rc.job_minutes(job("03:00:00", "03:00:20")) == 1
    assert rc.job_minutes(job("03:00:00", "03:01:00")) == 1
    assert rc.job_minutes(job("03:00:00", "03:01:01")) == 2


def test_skipped_and_unfinished_jobs_cost_nothing():
    assert rc.job_minutes(job("03:00:00", "03:09:00", "skipped")) == 0
    assert rc.job_minutes({"conclusion": None, "started_at": None, "completed_at": None}) == 0


def test_summarize_counts_idle_runs_and_groups_by_branch_and_kind():
    runs = [
        {"branch": "a", "workflow": "Smoke", "jobs": [job("03:00:00", "03:10:00"), job("03:00:00", "03:02:30")]},
        {"branch": "a", "workflow": "Ruff", "jobs": [job("03:00:00", "03:00:10", "skipped")]},
        {"branch": "b", "workflow": "Ruff", "jobs": [job("03:00:00", "03:00:40")]},
        {"branch": "c", "workflow": "Ruff", "jobs": []},
    ]
    s = rc.summarize(runs, {"a": "code", "b": "docs-only"})
    assert (s["runs"], s["idle_runs"], s["branches"], s["runner_min"]) == (4, 2, 3, 14)
    assert s["by_kind"]["code"] == {"branches": 1, "runner_min": 13, "per_branch": 13.0}
    assert s["by_kind"]["docs-only"]["runner_min"] == 1
    assert s["by_kind"]["unknown"]["branches"] == 1  # a branch with no kind is never docs-only
    assert s["top_workflows"][0] == ("Smoke", 13)


def test_kind_of_never_calls_an_unreadable_pr_docs_only():
    refs = cc.load()
    assert rc.kind_of(None, refs) == "unknown" and rc.kind_of([], refs) == "unknown"
    assert rc.kind_of(["README.md", ".claude/rules/ci-workflows.md"], refs) == "docs-only"
    assert rc.kind_of(["README.md", "gitgalaxy/galaxyscope.py"], refs) == "code"
    assert rc.kind_of(["tests/tools/test_zos_probes.py"], refs) == "code"


def test_empty_window():
    assert rc.summarize([], {})["per_branch"] == 0.0
