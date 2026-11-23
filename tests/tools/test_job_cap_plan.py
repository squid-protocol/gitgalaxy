"""2026-11-23 (#8701): job caps planned from measured wall time (job_cap_plan.py) for tri-comparison-audit/-history,
graph-accuracy-audit and evidence-refresh's det-mutation, and the ctags-install hang that stopped two tri-comparison runs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import ci_cap_headroom  # noqa: E402
import job_cap_plan as jcp  # noqa: E402

yaml = pytest.importorskip("yaml")
WORKFLOWS = ROOT / ".github" / "workflows"


def _job(name: str, minutes: float, conclusion: str = "success", step: str | None = None) -> dict:
    """A completed Actions job of `minutes` wall; a stopped one carries the step it was in."""
    secs = round(minutes * 60)
    end = f"2026-11-20T{secs // 3600:02d}:{secs % 3600 // 60:02d}:{secs % 60:02d}Z"
    steps = [
        {
            "name": "Set up job",
            "conclusion": "success",
            "started_at": "2026-11-20T00:00:00Z",
            "completed_at": "2026-11-20T00:00:05Z",
        }
    ]
    if step:
        steps.append(
            {"name": step, "conclusion": "cancelled", "started_at": "2026-11-20T00:00:05Z", "completed_at": end}
        )
    return {
        "name": name,
        "conclusion": conclusion,
        "started_at": "2026-11-20T00:00:00Z",
        "completed_at": end,
        "steps": steps,
    }


def test_a_cap_is_the_worst_wall_x_headroom_clamped_and_needs_enough_runs():
    walls = [6.0, 8.2, 7.0, 7.5, 6.5]
    assert jcp.plan_cap(walls, floor=5, ceiling=45) == 11  # 8.2 x 1.3 = 10.7
    assert jcp.plan_cap(walls, floor=15, ceiling=45) == 15  # floor
    assert jcp.plan_cap([30.0] * 5, floor=15, ceiling=35) == 35  # ceiling
    assert jcp.plan_cap(walls[:4], floor=5, ceiling=45) is None  # < MIN_OBS: the literal stays


def test_a_job_hung_in_a_setup_step_is_not_evidence_the_work_needs_longer():
    # the 2026-11-23 shape: tri-comparison ran 30.3 min under a 30-min cap, all of it in the ctags install; normal runs ~3 min
    jobs = [_job("tri-comparison-audit", m) for m in (2.5, 3.1, 3.2, 2.9, 3.0)]
    jobs.append(
        _job("tri-comparison-audit", 30.3, "cancelled", step="Install universal-ctags and verify it's the real thing")
    )
    walls, notes = jcp.observations(jobs, "tri-comparison-audit", fallback_cap=30)
    assert max(walls) == 3.2 and len(notes) == 1 and "hang" in notes[0] and "universal-ctags" in notes[0]
    assert (
        jcp.plan_cap(walls, floor=15, ceiling=45) == 15
    )  # not 40: widening the window would only let a hang last longer


def test_a_job_stopped_mid_work_counts_so_a_slow_job_raises_its_own_cap():
    jobs = [_job("graph-accuracy-audit", 20.0) for _ in range(4)]
    jobs.append(_job("graph-accuracy-audit", 24.5, "cancelled", step="Run the gates"))
    walls, notes = jcp.observations(jobs, "graph-accuracy-audit", fallback_cap=25)
    assert max(walls) == 24.5 and not notes
    assert jcp.plan_cap(walls, floor=20, ceiling=45) == 32


def test_a_run_cancelled_for_a_newer_push_and_other_jobs_never_count():
    jobs = [
        _job("tri-comparison-audit", 2.0, "cancelled", step="Run the audit"),
        _job("plan", 40.0),
        _job("other", 99.0),
    ]
    assert jcp.observations(jobs, "tri-comparison-audit", fallback_cap=30) == ([], [])


def test_matrix_legs_of_a_job_are_its_observations():
    jobs = [_job(f"det-mutation ({i}/3)", m) for i, m in ((1, 100.0), (2, 124.7), (3, 90.0))]
    jobs.append(_job("det-mutation-report", 500.0))
    walls, _ = jcp.observations(jobs, "det-mutation", fallback_cap=150)
    assert sorted(walls) == [90.0, 100.0, 124.7]


def test_the_planner_writes_the_cap_and_step_cap_and_never_fails_the_workflow(monkeypatch, tmp_path, capsys):
    out = tmp_path / "out"
    jobs = [_job("det-mutation (1/3)", m) for m in (100.0, 110.0, 124.7, 120.0, 118.0)]
    monkeypatch.setattr(jcp, "load_jobs", lambda _wf, _runs=30: jobs)
    argv = ["--workflow", "evidence-refresh.yml", "--job", "det-mutation", "--floor", "150", "--ceiling", "240",
            "--fallback", "150", "--step-margin", "12", "--github-output", str(out)]  # fmt: skip
    assert jcp.main(argv) == 0
    assert out.read_text().split() == ["cap=163", "step_cap=151"]  # 124.7 x 1.3, and the job's cap - 12
    # too few runs: nothing written, the workflow's literal applies
    out.write_text("")
    monkeypatch.setattr(jcp, "load_jobs", lambda _wf, _runs=30: jobs[:2])
    assert jcp.main(argv) == 0 and out.read_text() == ""

    # history that cannot be read at all: still exit 0, nothing written
    def boom(_wf, _runs=30):
        raise OSError("gh unreachable")

    monkeypatch.setattr(jcp, "load_jobs", boom)
    assert jcp.main(argv) == 0 and out.read_text() == ""
    assert "history unavailable" in capsys.readouterr().err


def test_one_unreadable_run_is_skipped_not_the_whole_history(monkeypatch, capsys):
    import subprocess

    def gh(path):
        if path.endswith("/runs?status=completed&per_page=3"):
            return {"workflow_runs": [{"id": 1}, {"id": 2}, {"id": 3}]}
        if "/runs/2/" in path:
            raise subprocess.CalledProcessError(1, "gh")  # a transient 502
        return {"jobs": [_job("x", 5.0)]}

    monkeypatch.setattr(jcp.ci_rerun_stats, "_gh", gh)
    assert len(jcp.load_jobs("wf.yml", runs=3)) == 2 and "run 2 skipped" in capsys.readouterr().err


# the four workflows: planned cap, the old literal as the fallback, the plan job able to read runs
PLANNED = {
    "tri-comparison-audit.yml": ("plan", "tri-comparison-audit", "30", "needs.plan.outputs.cap"),
    "tri-comparison-history.yml": ("plan", "tri-comparison-history", "30", "needs.plan.outputs.cap"),
    "graph-accuracy-audit.yml": ("plan", "graph-accuracy-audit", "25", "needs.plan.outputs.cap"),
    "evidence-refresh.yml": ("lane", "det-mutation", "150", "needs.lane.outputs.det_mutation_cap"),
}


@pytest.mark.parametrize("name", sorted(PLANNED))
def test_the_cap_is_planned_with_the_old_literal_as_the_fallback_and_the_planner_can_read_runs(name):
    planner, job, literal, ref = PLANNED[name]
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert doc["jobs"][job]["timeout-minutes"] == f"${{{{ fromJSON({ref} || '{literal}') }}}}"
    assert doc["jobs"][planner]["permissions"]["actions"] == "read"
    steps = doc["jobs"][planner]["steps"]
    cap = next(s for s in steps if "job_cap_plan.py" in str(s.get("run")))
    assert cap["continue-on-error"] is True, "a planner failure must fall back to the literal, never fail the workflow"
    assert f"--workflow {name}" in cap["run"] and f"--job {job}" in cap["run"] and f"--fallback {literal}" in cap["run"]


def test_planned_caps_are_the_planners_so_the_weekly_report_no_longer_lists_them_as_tight():
    for name, (_, job, _, _) in PLANNED.items():
        assert job not in ci_cap_headroom.literal_caps((WORKFLOWS / name).read_text(encoding="utf-8")), name


def test_det_mutation_keeps_its_own_budget_inside_the_planned_cap_and_the_step_cap_follows_it():
    text = (WORKFLOWS / "evidence-refresh.yml").read_text(encoding="utf-8")
    assert "--floor 150" in text and "--budget-min 130" in text  # the budget ends the work before even the floor cap
    assert "fromJSON(needs.lane.outputs.det_mutation_step_cap || '138')" in text
    sparse = text.split("Checkout the plan tool and the cases")[1].split("- name:")[0]
    assert "tests/tools/job_cap_plan.py" in sparse and "tests/tools/ci_rerun_stats.py" in sparse


@pytest.mark.parametrize("name", ["tri-comparison-audit.yml", "tri-comparison-history.yml", "doom-rosetta.yml"])
def test_the_ctags_install_cannot_hang_for_the_whole_job(name):
    """Both 30-min stops were this step hung for ~29 min: ci_retry retries a failed attempt, never a hung one."""
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    steps = [
        s for j in doc["jobs"].values() for s in j.get("steps", []) if "Install universal-ctags" in str(s.get("name"))
    ]
    assert steps, name
    for step in steps:
        assert step["timeout-minutes"] <= 12
        m = re.search(r"ci_retry\.sh (\d+) (\d+) -- timeout -k (\d+) (\d+) bash -c", step["run"])
        assert m, "each attempt must be bounded by `timeout`, or ci_retry waits on a hung apt-get"
        attempts, backoff, _kill, per_try = (int(x) for x in m.groups())
        assert attempts * per_try + backoff * (attempts * (attempts - 1) // 2) < step["timeout-minutes"] * 60
