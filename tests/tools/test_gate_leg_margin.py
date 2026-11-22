# ruff: noqa: S101, E402, I001
"""#8701: the gate-leg margin check reads leg caps from job names and flags a leg within 3 min of its step cap (offline)."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))

import gate_leg_margin as glm


def _t(minutes: float) -> str:
    s = int(minutes * 60)
    return f"2026-11-21T{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}Z"


def _job(name: str, step_min: float | None, job_min: float = 30, conclusion: str = "success") -> dict:
    steps = []
    if step_min is not None:
        steps = [
            {"name": "Install dependencies", "started_at": _t(0), "completed_at": _t(5)},
            {
                "name": "Full Suite (x, Python 3.12)",
                "started_at": _t(5),
                "completed_at": _t(5 + step_min),
                "conclusion": conclusion,
            },
        ]
    return {"name": name, "conclusion": conclusion, "started_at": _t(0), "completed_at": _t(job_min), "steps": steps}


W312 = "full-suite-matrix (windows-latest, 3.12, 1, 3, true, 33, 30)"
W311 = "full-suite-matrix (windows-latest, 3.11, 2, 3, 28, 25)"
UBU = "full-suite-matrix (ubuntu-latest, 3.11, 1, 2, 24, 21)"


def test_parse_leg_with_and_without_the_even_flag():
    assert glm.parse_leg(W312) == {
        "os": "windows-latest", "python": "3.12", "part": 1, "splits": 3, "timeout": 33, "step_timeout": 30,
    }  # fmt: skip
    assert glm.parse_leg(W311)["step_timeout"] == 25
    assert glm.parse_leg("matrix") is None
    assert glm.parse_leg("full-suite-matrix (a, b)") is None


def test_the_step_wall_is_used_not_the_job_wall_and_job_wall_is_the_fallback():
    assert glm.step_minutes(_job(W312, 20, job_min=29)) == 20
    assert glm.step_minutes(_job(W312, None, job_min=27)) == 27


def test_a_margin_of_exactly_the_minimum_is_not_tight():
    rows = glm.margins([[_job(W312, 27)]], "windows")  # cap 30, wall 27
    assert glm.tight(rows, 3) == []
    rows = glm.margins([[_job(W312, 27.5)]], "windows")
    assert glm.tight(rows, 3) == [("windows-latest", "3.12", 1)]


def test_a_leg_cut_at_its_cap_is_tight_and_worst_over_runs_counts():
    cut = _job(W311, 25, conclusion="cancelled")
    rows = glm.margins([[_job(W311, 10)], [cut]], "windows")
    assert rows[("windows-latest", "3.11", 2)] == (25, 25.0, 2)
    assert glm.tight(rows, 3) == [("windows-latest", "3.11", 2)]


def test_only_the_selected_os_is_checked_and_skipped_legs_are_ignored():
    rows = glm.margins([[_job(UBU, 20), _job(W311, 5, conclusion="skipped")]], "windows")
    assert rows == {}
    assert ("ubuntu-latest", "3.11", 1) in glm.margins([[_job(UBU, 20)]], "")


def test_fewer_than_the_required_scheduled_runs_is_unconfirmed(monkeypatch, capsys):
    monkeypatch.setattr(glm, "scheduled_jobs", lambda *_a: [[_job(W312, 10)]])
    assert glm.main(["--runs", "5"]) == 1
    assert "UNCONFIRMED: 1 of 5 scheduled runs measured" in capsys.readouterr().out
    monkeypatch.setattr(glm, "scheduled_jobs", lambda *_a: [[_job(W312, 10)]] * 5)
    assert glm.main(["--runs", "5"]) == 0


def test_each_observation_is_judged_against_its_own_runs_cap():
    old = _job("full-suite-matrix (windows-latest, 3.12, 1, 2, true, 28, 25)", 24)  # margin 1 under the old plan
    new = _job(W312, 20)  # margin 10 under the new cap
    rows = glm.margins([[new], [old]], "windows")
    assert rows[("windows-latest", "3.12", 1)] == (25, 24.0, 2)
    assert glm.margins([[new]], "windows")[("windows-latest", "3.12", 1)] == (30, 20.0, 1)


def test_a_leg_that_failed_early_or_never_reached_the_step_is_not_an_observation():
    early = _job(W312, 1, conclusion="failure")  # e.g. an import error at collection
    no_step = _job(W312, None, job_min=27)
    assert glm.margins([[early, no_step]], "windows") == {}
    assert glm.measured_runs([[early, no_step]], "windows") == 0


def test_a_step_cut_at_its_cap_is_an_observation_and_unmeasured_runs_do_not_count(monkeypatch, capsys):
    cut = _job(W312, 30, conclusion="cancelled")
    assert glm.margins([[cut]], "windows")[("windows-latest", "3.12", 1)] == (30, 30.0, 1)
    early = _job(W312, 1, conclusion="failure")
    monkeypatch.setattr(glm, "scheduled_jobs", lambda *_a: [[_job(W312, 10)]] * 3 + [[early]] * 2)
    assert glm.main(["--runs", "5"]) == 1
    assert "UNCONFIRMED: 3 of 5 scheduled runs measured (5 sampled)" in capsys.readouterr().out
