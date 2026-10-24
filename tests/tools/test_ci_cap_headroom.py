# ruff: noqa: S101, E402, I001
"""#5156: the cap-headroom survey classifies fixed timeout caps against measured job wall time (offline)."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))

import ci_cap_headroom as chr_


def _job(name: str, minutes: float, conclusion: str = "success") -> dict:
    return {
        "name": name,
        "conclusion": conclusion,
        "started_at": "2026-10-20T00:00:00Z",
        "completed_at": f"2026-10-20T{int(minutes) // 60:02d}:{int(minutes) % 60:02d}:00Z",
    }


WORKFLOW = """
jobs:
  fixed:
    timeout-minutes: 10
  named:
    name: Named job
    timeout-minutes: 20
  planned:
    timeout-minutes: ${{ fromJSON(needs.plan.outputs.timeout) }}
  uncapped:
    runs-on: x
"""


def test_literal_caps_skip_planner_expressions_and_uncapped_jobs():
    assert chr_.literal_caps(WORKFLOW) == {"fixed": 10, "Named job": 20}


def test_cap_for_matches_exact_and_matrix_suffix_longest_first():
    caps = {"leg": 10, "leg (a)": 30}
    assert chr_.cap_for("leg", caps) == ("leg", 10)
    assert chr_.cap_for("leg (x, y)", caps) == ("leg", 10)
    assert chr_.cap_for("leg (a) (b)", caps) == ("leg (a)", 30)
    assert chr_.cap_for("other", caps) is None


def test_headroom_flags_only_caps_under_the_minimum_ratio():
    caps = {"tight": 10, "ok": 30, "edge": 15}
    jobs = [
        _job("tight", 9),
        _job("tight", 4),
        _job("ok", 10),
        _job("edge", 10),  # 15 == 10 * 1.5: exactly the minimum, not tight
        _job("ok", 59, "failure"),  # a failed run says nothing about healthy wall time
    ]
    rows = chr_.headroom(jobs, caps)
    assert rows["tight"][:2] == (10, 9.0)
    assert rows["ok"][1] == 10.0
    assert chr_.tight(rows) == ["tight"]


def test_a_job_without_a_successful_run_is_absent_not_fine():
    assert chr_.headroom([_job("a", 5, "cancelled")], {"a": 10}) == {}


def test_every_workflow_cap_is_a_positive_int_or_an_expression():
    for path in sorted(chr_.WORKFLOWS.glob("*.yml")):
        for key, job in (yaml.safe_load(path.read_text(encoding="utf-8")).get("jobs") or {}).items():
            cap = job.get("timeout-minutes") if isinstance(job, dict) else None
            assert cap is None or (isinstance(cap, int) and cap > 0) or "${{" in str(cap), (path.name, key, cap)
