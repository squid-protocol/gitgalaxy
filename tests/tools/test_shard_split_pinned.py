"""#5114: a CI shard never picks its own durations. The class: sharded jobs that each restored "the newest" durations
cache when they started, so a cache save between two shards' starts gave them different slices (a case or test proven
twice or not at all). The split is chosen once (a plan/durations job, or the committed file at one pinned commit).
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def load(name):
    return yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text(encoding="utf-8"))


def restore_steps(job):
    return [
        s
        for s in job.get("steps", [])
        if "cache/restore" in s.get("uses", "") or s.get("uses", "").startswith("actions/cache@")
    ]


def durations_restores():
    """(workflow, job id, job, step) for every cache restore whose key or path names durations."""
    found = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for jid, job in (yaml.safe_load(wf.read_text(encoding="utf-8")).get("jobs") or {}).items():
            for step in restore_steps(job):
                w = step.get("with") or {}
                if "durations" in f"{w.get('key', '')} {w.get('path', '')}":
                    found.append((wf.stem, jid, job, step))
    return found


def test_no_matrix_job_restores_the_newest_durations_itself():
    bad = [
        f"{wf}:{jid}"
        for wf, jid, job, step in durations_restores()
        if (job.get("strategy") or {}).get("matrix") and "restore-keys" in (step.get("with") or {})
    ]
    assert not bad, f"a sharded job picks its own durations (restore-keys): {bad}"


def test_the_restore_that_picks_the_newest_runs_once_per_workflow_run():
    pickers = [(wf, jid) for wf, jid, job, step in durations_restores() if "restore-keys" in (step.get("with") or {})]
    # det-sweep `det` is the single nightly merge job (not a shard): it extends the newest file, then saves it
    assert sorted(pickers) == [("det-sweep", "det"), ("det-sweep", "plan"), ("smoke-test", "durations")]


@pytest.mark.parametrize("job", ["shard", "db2"])
def test_det_sweep_shards_balance_by_the_plans_durations_artifact(job):
    jobs = load("det-sweep")["jobs"]
    assert "plan" in jobs[job]["needs"] or jobs[job]["needs"] == "plan"
    steps = jobs[job]["steps"]
    assert any(s.get("with", {}).get("name") == "det-durations" for s in steps)
    assert not [s for s in restore_steps(jobs[job]) if "durations" in str(s.get("with") or {})]


def test_evidence_refresh_shards_read_no_durations_cache():
    assert not [t for t in durations_restores() if t[0] == "evidence-refresh"]


def test_smoke_test_parts_restore_the_exact_key_the_durations_job_chose():
    jobs = load("smoke-test")["jobs"]
    part = jobs["full-suite-part"]
    assert "durations" in part["needs"]
    (step,) = [s for s in restore_steps(part) if "durations" in str(s.get("with"))]
    w = step["with"]
    assert "restore-keys" not in w
    assert w["key"] == "${{ needs.durations.outputs.key }}"
    assert jobs["durations"]["outputs"]["key"]
    # a missing key must not fail or skip the part: it falls back to the committed .test_durations
    assert "needs.durations.outputs.key" in step["if"]
    assert "!cancelled()" in part["if"]
