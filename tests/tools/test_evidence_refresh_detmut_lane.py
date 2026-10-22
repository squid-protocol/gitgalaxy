"""#5862: the nightly Evidence Refresh renews stale det_mutation ledgers (`det_mutation.py refresh`), so `current` holds
without a PR per port. The class: a ledger stale on an input fingerprint that nothing refreshes on a schedule. These
tests pin the wiring: the job exists, its ledgers reach the bot PR, a wrong claim blocks auto-merge, a moved port only warns.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "evidence-refresh.yml"
LEDGER_GLOB = "tests/equivalence/det_mutation/*.json"


@pytest.fixture(scope="module")
def jobs():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def steps_text(job):
    return "\n".join(str(s.get("run", "")) + str(s.get("uses", "")) for s in job["steps"])


def test_the_job_refreshes_the_ledgers_on_the_pinned_commit(jobs):
    job = jobs["det-mutation"]
    assert job["needs"] == "lane" and "defer != 'true'" in job["if"]
    assert "timeout-minutes" in job
    assert "det_mutation.py refresh" in steps_text(job)
    checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ needs.lane.outputs.sha }}"


def test_a_moved_port_warns_and_any_other_failure_fails_the_job(jobs):
    job = jobs["det-mutation"]
    step = next(s for s in job["steps"] if s.get("id") == "detmut")
    assert step.get("continue-on-error") is True
    assert "-eq 2" in step["run"] and "::warning" in step["run"] and 'exit "$rc"' in step["run"]
    assert any(s.get("if") == "steps.detmut.outcome == 'failure'" for s in job["steps"])


def test_the_ledgers_reach_the_refresh_job_and_the_bot_pr(jobs):
    assert "det-mutation" in jobs["refresh"]["needs"]
    take = next(s for s in jobs["refresh"]["steps"] if s.get("id") == "detmut_in")
    assert take["with"]["name"] == "refresh-detmut"
    assert "tests/equivalence/det_mutation" in steps_text(jobs["refresh"])
    assert any(s.get("name") == "Keep the renewed ledgers" and s["with"]["name"] == "refresh-detmut" for s in jobs["det-mutation"]["steps"])  # fmt: skip
    cpr = next(s for s in jobs["refresh"]["steps"] if s.get("id") == "cpr")
    assert LEDGER_GLOB in cpr["with"]["add-paths"].split()


def test_a_failed_ledger_job_blocks_auto_merge(jobs):
    steps = jobs["refresh"]["steps"]
    auto = next(s for s in steps if s.get("name", "").startswith("Enable squash auto-merge"))
    assert "needs.det-mutation.result == 'success'" in auto["if"]
    hold = [s for s in steps if "needs.det-mutation.result != 'success'" in str(s.get("if", ""))]
    assert hold, "the run must fail when the ledger job failed"


def test_the_artifact_step_takes_only_ledger_json(jobs):
    step = next(s for s in jobs["refresh"]["steps"] if s.get("name", "").startswith("Put the renewed det mutation"))
    assert "! -name '*.json'" in step["run"] and "-type l" in step["run"]
