"""#7455: an aggregate gate ends `cancelled` in a cancelled run, without ever letting unproven code through.

Two facts make `!cancelled()` safe, and these tests hold both. The gate's `if:` is exactly `!cancelled()` plus the draft
clause, because any other false `if:` is a `skipped` job, which reads as green. And a `cancelled` input in a LIVE run (a
job that hit `timeout-minutes`: `cancelled()` stays false, so the gate runs) still fails the gate's own shell.
What GitHub does on a real cancel is in docs/ci.md, "A cancelled run ends `cancelled`".
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_digest as cd
import pr_check
import shepherd_gh as sg

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
GATE_IF = "${{ !cancelled() && (github.event_name != 'pull_request' || github.event.pull_request.draft == false) }}"
GATES = {
    "smoke-test.yml": "full-suite",
    "mainframe-ground-truth.yml": "ground-truth",
    "det-sweep.yml": "det",
    "equivalence-e2e.yml": "equivalence-e2e",
    "cics-crucible.yml": "crucible",
}
# `always()` jobs that are no aggregate: each is one audit that runs after a failed plan. They finish `success` in a
# cancelled run (a wasted runner, no false red) and are not required checks.
AUDITS = {
    ("call-graph-accuracy-audit.yml", "call-graph-accuracy-audit"),
    ("detection-accuracy-audit.yml", "detection-accuracy-audit"),
    ("graph-accuracy-audit.yml", "graph-accuracy-audit"),
    ("tree-sitter-accuracy-audit.yml", "tree-sitter-accuracy-audit"),
    ("tri-comparison-audit.yml", "tri-comparison-audit"),
}
needs_linux_bash = pytest.mark.skipif(sys.platform != "linux", reason="the gate steps are bash for the Linux runners")


def _jobs(workflow: str) -> dict:
    return yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))["jobs"]


def _run(workflow: str, step: str) -> str:
    job = _jobs(workflow)[GATES[workflow]]
    return next(s for s in job["steps"] if s.get("name") == step)["run"]


def _passes(script: str, tmp_path: Path, **env: str) -> bool:
    """A gate step's shell, as GitHub runs it (bash -e), in an empty directory (no shard reported) with no network."""
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"), **env}
    script = "gh() { return 1; }\n" + script
    return subprocess.run(["bash", "-e", "-c", script], env=env, cwd=tmp_path, capture_output=True).returncode == 0


@pytest.mark.parametrize("workflow, gate", GATES.items(), ids=GATES.values())
def test_a_gate_leaves_only_a_cancel_and_a_draft_out(workflow, gate):
    assert _jobs(workflow)[gate]["if"] == GATE_IF
    assert "continue-on-error" not in _jobs(workflow)[gate]


def test_no_pull_request_job_runs_on_into_a_cancelled_run_to_fail_it():
    found = set()
    for f in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        if "pull_request" in (doc.get("on", doc.get(True)) or {}):
            found |= {(f.name, k) for k, j in doc["jobs"].items() if "always()" in str(j.get("if", ""))}
    assert found == AUDITS, "a job-level always() fails on a cancelled run: use !cancelled() (docs/ci.md, #7455)"


@needs_linux_bash
@pytest.mark.parametrize("result", ["cancelled", "failure", ""])
def test_ground_truth_fails_on_parts_that_did_not_pass_in_a_live_run(tmp_path, result):
    script = _run("mainframe-ground-truth.yml", "Every part passed")
    assert not _passes(script, tmp_path, WARM="success", PARTS=result, SKIP="", MODE="full", PLANNED_WARM="true")
    assert not _passes(script, tmp_path, WARM=result, PARTS="success", SKIP="", MODE="full", PLANNED_WARM="true")
    assert _passes(script, tmp_path, WARM="success", PARTS="success", SKIP="", MODE="full", PLANNED_WARM="true")


@needs_linux_bash
@pytest.mark.parametrize("result", ["cancelled", "failure", ""])
def test_equivalence_e2e_fails_on_jobs_that_did_not_pass_in_a_live_run(tmp_path, result):
    script = _run("equivalence-e2e.yml", "Every shard passed, or the plan proved none was needed")
    base = {
        "PLAN": "run",
        "DB2_PLAN": "run",
        "PLAN_RESULT": "success",
        "SKIP": "",
        "SHARDS": "success",
        "DB2": "success",
    }
    for key in ("PLAN_RESULT", "SHARDS", "DB2"):
        assert not _passes(script, tmp_path, **{**base, key: result})
    assert _passes(script, tmp_path, **base)


@needs_linux_bash
def test_det_fails_on_a_cancelled_plan_or_a_shard_that_never_reported(tmp_path):
    script = _run("det-sweep.yml", "Apply the ratchet to the merged sweep")
    base = {"MODE": "full", "CASES": "", "DB2_CASES": "", "EVENT": "pull_request", "REF": "refs/pull/1/merge"}
    assert not _passes(script, tmp_path, **base, PLAN_RESULT="cancelled", SHARDS="0", DB2_SHARDS="0")
    # a timed-out shard uploaded nothing: its result is not read, the missing sweep.json fails the check
    assert not _passes(script, tmp_path, **base, PLAN_RESULT="success", SHARDS="2", DB2_SHARDS="0")
    assert not _passes(script, tmp_path, **base, PLAN_RESULT="success", SHARDS="0", DB2_SHARDS="2")
    assert _passes(script, tmp_path, **base, PLAN_RESULT="success", SHARDS="0", DB2_SHARDS="0")


@needs_linux_bash
@pytest.mark.parametrize(
    "measure, runner_tests", [("cancelled", "success"), ("success", "cancelled"), ("skipped", "success")]
)
def test_crucible_fails_on_jobs_that_did_not_pass_in_a_live_run(tmp_path, measure, runner_tests):
    raw = _run("cics-crucible.yml", "Fail unless every shard and the runner tests passed")

    def script(m, r):
        return raw.replace("${{ needs.measure.result }}", m).replace("${{ needs.runner-tests.result }}", r)

    assert not _passes(script(measure, runner_tests), tmp_path)
    assert _passes(script("success", "success"), tmp_path)


def _check(name, conclusion, id_=1):
    return {"id": id_, "name": name, "status": "completed", "conclusion": conclusion}


@pytest.mark.parametrize("check", [*sg.REQUIRED_CHECKS, "equivalence-e2e", "crucible"])
def test_a_cancelled_gate_never_reads_as_passed_and_triages_as_a_rerun(check):
    verdict = pr_check.classify([_check(check, "cancelled")], [])
    assert verdict["failed"] == [f"{check} (cancelled)"] and not verdict["passed"] and not verdict["neutral"]
    assert cd.triage("cancelled", "", [], "clean", {"tests": [], "cases": []}) == "infra"


def test_a_cancelled_required_check_holds_ci_gate_until_a_run_proves_the_head():
    state = {"state": "open", "draft": False}
    retry = [{"check": "full-suite", "triage": "infra"}]
    assert sg.gate_status(state, [], [], retry)[0] == "pending"
    assert sg.gate_status(state, retry, [], [])[0] == "failure"  # reruns used up: needs-fix, still not green
