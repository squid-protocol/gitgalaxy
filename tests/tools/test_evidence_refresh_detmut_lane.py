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


def test_the_lane_runs_the_moved_ports_within_a_budget_under_the_job_timeout(jobs):
    """A ledger whose det port moved stays stale until `run` records it: the lane runs them, oldest first (#5862)."""
    job = jobs["det-mutation"]
    step = next(s for s in job["steps"] if s.get("id") == "detmut")
    assert "--run-moved" in step["run"]
    budget = int(step["run"].split("--budget-min")[1].split()[0])
    assert 0 < budget <= job["timeout-minutes"] - 20  # setup, the oracle image and one case that runs past its estimate


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
    assert "--auto --squash" in auto["run"] and "shepherd:" not in auto["run"]  # #6693: own auto-merge, no label
    rehome = next(s for s in steps if s.get("name", "").startswith("Advance gitgalaxy to latest origin/main"))
    cpr = next(s for s in steps if s.get("id") == "cpr")
    assert steps.index(rehome) < steps.index(cpr) < steps.index(auto)
    hold = [s for s in steps if "needs.det-mutation.result != 'success'" in str(s.get("if", ""))]
    assert hold, "the run must fail when the ledger job failed"


def test_the_artifact_step_takes_only_ledger_json(jobs):
    step = next(s for s in jobs["refresh"]["steps"] if s.get("name", "").startswith("Put the renewed det mutation"))
    assert "! -name '*.json'" in step["run"] and "-type l" in step["run"]


def test_the_blocker_feed_failure_fails_the_run_after_the_records_are_kept(jobs):
    """#5054: a leak (or a leak scan that did not run) must turn the run red, but only at the last step."""
    steps = jobs["refresh"]["steps"]
    feed = next(s for s in steps if s.get("id") == "feed")
    assert feed.get("continue-on-error") is True and "--require-sources" in feed["run"]
    final = next(s for s in steps if s.get("name") == "Fail when a re-proof failed")
    assert "steps.feed.outcome == 'failure'" in final["if"]
    assert steps.index(final) > steps.index(feed)


def test_the_survey_includes_the_cics_crucible_clone(jobs):
    steps = jobs["refresh"]["steps"]
    survey = next(s for s in steps if s.get("id") == "survey")
    assert '--crucible "$GITHUB_WORKSPACE/cics-crucible"' in survey["run"]
    feed = next(s for s in steps if s.get("id") == "feed")
    assert '--extra-root "$GITHUB_WORKSPACE/cics-crucible"' in feed["run"]


def test_a_full_dispatch_stands_down_while_the_bot_pr_checks_run(jobs):
    """#6693: a dispatch must not force-push the full-lane bot PR while its head's checks are running."""
    lane = jobs["lane"]
    gate = next(s for s in lane["steps"] if s.get("id") == "full_gate")
    assert "!inputs.force" in gate["if"] and "auto/evidence-refresh-full" in gate["run"]
    assert 'select(.status != "completed")' in gate["run"]
    assert "full_gate.outputs.defer" in lane["outputs"]["defer"]
    assert "defer != 'true'" in jobs["db2-part"]["if"]
    for name in ("sweep", "records", "det-mutation", "refresh"):
        assert "defer != 'true'" in jobs[name]["if"], name
    on = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert "force" in on[True]["workflow_dispatch"]["inputs"]  # PyYAML reads the key `on` as True
