"""2026-11-23 (#8701): the weekly CI cap report runs the two tight-cap tools nobody ran, and a red one reaches Main Watch."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _doc(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _on(doc: dict) -> dict:
    return doc.get("on") or doc.get(True)  # YAML 1.1 reads a bare `on` as True


def test_the_report_runs_both_tools_and_stays_red_when_either_finds_a_tight_cap():
    steps = _doc("ci-cap-report.yml")["jobs"]["cap-report"]["steps"]
    runs = "\n".join(str(s.get("run", "")) for s in steps)
    assert "tests/tools/ci_cap_headroom.py" in runs and "tests/tools/gate_leg_margin.py" in runs
    tools = [s for s in steps if "ci_cap_headroom" in str(s.get("run")) or "gate_leg_margin" in str(s.get("run"))]
    assert all(s.get("continue-on-error") for s in tools), "one tool's finding must not hide the other's"
    last = steps[-1]
    assert "steps.literal.outcome" in last["if"] and "steps.gate.outcome" in last["if"] and "exit 1" in last["run"]


def test_the_report_runs_weekly_and_by_hand_and_main_watch_opens_an_issue_when_it_is_red():
    doc = _doc("ci-cap-report.yml")
    assert doc["name"] == "CI cap report" and set(_on(doc)) == {"schedule", "workflow_dispatch"}
    assert "CI cap report" in _on(_doc("main-watch.yml"))["workflow_run"]["workflows"]


def test_the_report_actions_are_pinned_to_a_commit_and_it_reads_only():
    doc = _doc("ci-cap-report.yml")
    assert doc["permissions"] == {"contents": "read", "actions": "read"}
    for step in doc["jobs"]["cap-report"]["steps"]:
        if "uses" in step:
            assert re.search(r"@[0-9a-f]{40}$", step["uses"]), step["uses"]
