# ruff: noqa: S101
"""#5133: the full-suite part balance reader counts only runs whose three parts all finished."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import ci_part_balance as cpb  # noqa: E402


def job(k, minutes, conclusion="success", of=3, finished=True):
    end = f"2026-10-25T10:{minutes:02d}:00+00:00" if finished else None
    return {
        "name": f"full-suite part {k}/{of}",
        "conclusion": conclusion,
        "started_at": "2026-10-25T10:00:00+00:00",
        "completed_at": end,
    }


def test_equal_parts_are_within_target():
    parts = cpb.part_seconds([job(1, 5), job(2, 5), job(3, 5)])
    assert parts == {1: 300.0, 2: 300.0, 3: 300.0}
    assert cpb.within_target(parts)


def test_skewed_parts_are_not():
    assert not cpb.within_target(cpb.part_seconds([job(1, 12), job(2, 5), job(3, 4)]))


def test_the_exact_boundary_is_within():
    assert cpb.within_target({1: 100.0, 2: 120.0, 3: 110.0})
    assert not cpb.within_target({1: 100.0, 2: 120.01, 3: 110.0})


@pytest.mark.parametrize(
    "jobs",
    [
        [job(1, 5), job(2, 5)],
        [job(1, 5), job(2, 5), job(3, 5, conclusion="cancelled")],
        [job(1, 5), job(2, 5), job(3, 5, finished=False)],
        [{"name": "other", "conclusion": "success"}],
        [],
    ],
)
def test_a_run_without_all_parts_finished_is_none(jobs):
    assert cpb.part_seconds(jobs) is None


def test_summary_skips_bad_runs_and_reports_the_rest():
    lines, skipped = cpb.summarize(
        {"1": [job(1, 5), job(2, 5), job(3, 6)], "2": [job(1, 5), job(2, 5)], "3": [job(1, 10), job(2, 5), job(3, 5)]}
    )
    assert skipped == ["2"]
    assert lines[0].startswith("run ")
    assert "2 runs" in lines[-1] and "1 within 1.2" in lines[-1]


def test_summary_with_no_usable_run_says_so():
    lines, skipped = cpb.summarize({"9": []})
    assert skipped == ["9"] and "no run" in lines[-1]
