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
    # det-sweep `det` is the single nightly merge job (not a shard): it extends the newest file, then saves it; the plan
    # picks the newest of each namespace (#5882: the Db2 cases' own, which Evidence Refresh's single `db2` merge job extends)
    assert sorted(pickers) == [("det-sweep", "det"), ("det-sweep", "det"), ("det-sweep", "plan"), ("det-sweep", "plan"),
                               ("evidence-refresh", "db2"), ("smoke-test", "durations")]  # fmt: skip


@pytest.mark.parametrize("job", ["shard", "db2"])
def test_det_sweep_shards_balance_by_the_plans_durations_artifact(job):
    jobs = load("det-sweep")["jobs"]
    assert "plan" in jobs[job]["needs"] or jobs[job]["needs"] == "plan"
    steps = jobs[job]["steps"]
    assert any(s.get("with", {}).get("name") == "det-durations" for s in steps)
    assert not [s for s in restore_steps(jobs[job]) if "durations" in str(s.get("with") or {})]


def test_evidence_refresh_shards_read_no_durations_cache():
    """#5114: Evidence Refresh's shards balance by the committed file at the pinned commit. Its one durations restore is
    the `db2` merge job's (#5882), which writes the Db2 cases' seconds and never balances anything."""
    found = [(jid, step) for wf, jid, job, step in durations_restores() if wf == "evidence-refresh"]
    assert [jid for jid, _ in found] == ["db2"]
    assert not (load("evidence-refresh")["jobs"]["db2"].get("strategy") or {}).get("matrix")
    assert found[0][1]["with"]["restore-keys"].strip() == "det-db2-durations-"


def test_the_db2_durations_namespace_is_not_a_prefix_match_of_the_main_one():
    """#5882: restore-keys match by prefix, so `det-durations-` would also restore a `det-durations-db2-...` entry."""
    keys = {str((step.get("with") or {}).get("restore-keys", "")).strip() for *_, step in durations_restores()}
    assert "det-db2-durations-" in keys and "det-durations-" in keys
    assert not "det-db2-durations-".startswith("det-durations-")


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


def test_a_manual_full_sweep_on_main_records_the_db2_durations():
    """#5882: the det job restores, extends and saves the Db2 durations only for a dispatch on main (a cache saved on a
    branch or PR ref is read by no one), and only a full Db2 sweep writes them (a partial list would record a subset)."""
    steps = load("det-sweep")["jobs"]["det"]["steps"]
    restore = [s for s in restore_steps({"steps": steps}) if "det-db2-durations-" in str(s.get("with"))]
    save = [s for s in steps if "cache/save" in s.get("uses", "") and "det-db2-durations-" in str(s.get("with"))]
    assert len(restore) == len(save) == 1
    for step in (restore[0], save[0]):
        assert "workflow_dispatch" in step["if"] and "refs/heads/main" in step["if"]
    assert restore[0]["with"]["restore-keys"].strip() == "det-db2-durations-"
    assert save[0]["with"]["key"].startswith("det-db2-durations-") and save[0]["with"]["path"] == "durations-db2"
    run = next(s for s in steps if s.get("id") == "aggregate")["run"]
    assert '[ "$DB2_CASES" = "all" ]' in run and "--durations durations-db2/det_sweep_durations.json" in run
