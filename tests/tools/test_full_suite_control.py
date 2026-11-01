"""#7155: `full-suite` can fail. These run the required check's own shell from smoke-test.yml, so they can't drift from it."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "smoke-test.yml"
JOBS = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]

# The summary step is bash for the ubuntu runners. On a Windows runner `bash` is the WSL launcher, which drops the env the
# step reads (PARTS/SKIP/PLAN), so the shell tests fail or pass vacuously there (#7312); same skip as test_ci_retry.py.
needs_linux_bash = pytest.mark.skipif(sys.platform != "linux", reason="the summary step is bash for the Linux runners")


def _summary_step() -> dict:
    return next(s for s in JOBS["full-suite"]["steps"] if s.get("name") == "Every part of the suite passed")


def _pytest_step() -> dict:
    return next(s for s in JOBS["full-suite-part"]["steps"] if "Pytest" in str(s.get("name")))


def _passes(parts: str, skip: str = "", plan: str = "full") -> bool:
    """The summary step's shell under GitHub's default for `run:` (bash -e), with these job results."""
    env = {**os.environ, "PARTS": parts, "SKIP": skip, "PLAN": plan}
    return subprocess.run(["bash", "-e", "-c", _summary_step()["run"]], env=env, capture_output=True).returncode == 0


@needs_linux_bash
@pytest.mark.parametrize("parts", ["failure", "cancelled", ""])
@pytest.mark.parametrize("skip, plan", [("", "full"), ("true", "full"), ("", "skip"), ("true", "skip")])
def test_a_part_that_did_not_pass_fails_the_check_whatever_the_skip_proofs_say(parts, skip, plan):
    assert not _passes(parts, skip, plan)


@needs_linux_bash
@pytest.mark.parametrize("plan", ["full", "select", ""])
def test_skipped_parts_fail_without_a_proof_the_tree_is_green(plan):
    assert not _passes("skipped", "", plan)  # a suite that never ran can't read as a pass


@needs_linux_bash
def test_the_three_ways_to_pass():
    assert _passes("success")
    assert _passes("skipped", skip="true")  # the gate proved this tree green on the PR (#4935)
    assert _passes("skipped", plan="skip")  # the plan proved only prose changed (#6278)


def test_the_summary_always_reports_and_reads_the_parts():
    job = JOBS["full-suite"]
    assert "always()" in job["if"]  # without it a failed part skips the summary, and a skipped check can read as green
    assert "full-suite-part" in job["needs"]
    assert _summary_step()["env"]["PARTS"] == "${{ needs.full-suite-part.result }}"
    assert "continue-on-error" not in job and "continue-on-error" not in _summary_step()


def test_a_failing_pytest_fails_its_part():
    step, part = _pytest_step(), JOBS["full-suite-part"]
    assert "continue-on-error" not in step and "continue-on-error" not in part
    assert "shell" not in step  # GitHub's default stops on the first failing command
    lines = [ln.strip() for ln in step["run"].splitlines() if ln.strip().startswith("pytest ")]
    assert len(lines) == 1, "one pytest command, or this control needs a second look"
    assert "|" not in lines[0], "a pipe or || would hide pytest's exit code"
