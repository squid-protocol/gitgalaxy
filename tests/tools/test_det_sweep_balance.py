"""#5048: every det-sweep shard cuts its slice from the SAME durations, so a case is proven in exactly one shard.

Run 38589264737: one shard's durations cache restore missed, it fell back to the committed file, cut different
slices than its neighbours and `carddemo-readcust` was proven in two shards (the ratchet's duplicate check, rightly,
failed the merge). The plan job now chooses the durations once and every shard downloads that artifact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import proof_sweep as ps  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "det-sweep.yml"
CASES = [f"case-{i:02d}" for i in range(41)]


def _jobs():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _uses(job, prefix):
    return [s for s in job["steps"] if str(s.get("uses", "")).startswith(prefix)]


def _sharded_jobs():
    jobs = {
        n: j
        for n, j in _jobs().items()
        if any("proof_sweep.py" in s.get("run", "") and "--shard" in s["run"] for s in j["steps"])
    }
    assert set(jobs) == {"db2", "shard"}, "a new sharded job: give it the plan's durations too"
    return jobs


def test_no_sharded_job_restores_durations_from_its_own_cache():
    for name, job in _sharded_jobs().items():
        for step in _uses(job, "actions/cache"):
            assert "det-durations" not in json.dumps(step), f"{name}: balances by its own cache restore"


def test_every_sharded_job_balances_by_the_plan_artifact():
    for name, job in _sharded_jobs().items():
        assert "plan" in (job["needs"] if isinstance(job["needs"], list) else [job["needs"]])
        steps = job["steps"]
        dl = [
            i
            for i, s in enumerate(steps)
            if str(s.get("uses", "")).startswith("actions/download-artifact") and s["with"]["name"] == "det-durations"
        ]
        run = [i for i, s in enumerate(steps) if "proof_sweep.py" in s.get("run", "") and "--shard" in s["run"]]
        assert dl, f"{name}: does not download the plan's durations"
        assert "continue-on-error" not in steps[dl[0]], f"{name}: a failed download must fail, not fall back"
        copy = [i for i, s in enumerate(steps) if "det_sweep_durations.json" in s.get("run", "") and i < min(run)]
        assert copy and dl[0] < copy[0] < min(run), f"{name}: durations must be in place before the sweep"


def test_the_plan_job_chooses_and_uploads_the_durations_once():
    plan = _jobs()["plan"]
    up = [s for s in _uses(plan, "actions/upload-artifact") if s["with"]["name"] == "det-durations"]
    assert up and up[0]["with"]["if-no-files-found"] == "error"
    assert any("det-durations-" in json.dumps(s) for s in _uses(plan, "actions/cache/restore"))


DURATIONS = [
    {},
    {c: float(1 + (i * 7) % 23) for i, c in enumerate(CASES)},
    {c: float(1 + (i * 5) % 11) for i, c in enumerate(CASES[:20])},  # stale: half the cases unknown
]


@pytest.mark.parametrize("dur", DURATIONS)
@pytest.mark.parametrize("n", [1, 2, 3, 4, 7, 20])
def test_one_durations_input_partitions_every_case_exactly_once(dur, n):
    slices = [ps.shard_cases(CASES, (i, n), dur) for i in range(1, n + 1)]
    flat = [c for s in slices for c in s]
    assert sorted(flat) == sorted(CASES) and len(flat) == len(set(flat))
    assert slices == [ps.shard_cases(CASES, (i, n), dict(dur)) for i in range(1, n + 1)]  # a re-run cuts the same


def test_different_durations_per_shard_is_the_hazard():
    """Documents why the input must be shared: shards fed different files can both claim a case."""
    n = 20
    mixed = [ps.shard_cases(CASES, (i, n), DURATIONS[1] if i != 12 else {}) for i in range(1, n + 1)]
    flat = [c for s in mixed for c in s]
    assert len(flat) != len(set(flat)) or sorted(flat) != sorted(CASES)


def test_a_rerun_shard_overwrites_its_sweep_json_and_merges_without_a_duplicate(tmp_path):
    """The retry/re-run path: a shard re-run in the same work dir rewrites sweep.json (write_text, not append)."""
    src = Path(ps.__file__).read_text(encoding="utf-8")
    assert '(args.work / "sweep.json").write_text(' in src and '"sweep.json", "a"' not in src
    shard = tmp_path / "shard-1"
    shard.mkdir()
    for _ in range(2):  # the same shard's results written twice
        (shard / "sweep.json").write_text(json.dumps({"det": {"a": {"proved": True}}}), encoding="utf-8")
    other = tmp_path / "shard-2"
    other.mkdir()
    (other / "sweep.json").write_text(json.dumps({"det": {"b": {"proved": True}}}), encoding="utf-8")
    assert sorted(ps.merge_sweeps([shard, other])["det"]) == ["a", "b"]
    assert ps.merge_sweeps([shard, shard])["det"] == {"a": {"proved": True}}  # an identical repeat merges once (#5107)
    disagree = tmp_path / "shard-3"
    disagree.mkdir()
    (disagree / "sweep.json").write_text(json.dumps({"det": {"a": {"proved": False}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="in two shards with conflicting results"):  # a real conflict still raises
        ps.merge_sweeps([shard, disagree])


def test_the_committed_durations_balance_the_db2_split():
    """#5882: Evidence Refresh's Db2 parts split by the committed file (pinned, #5114), so a stale file unbalances them:
    the Db2 cases it measures stay within the plan's unmeasured allowance and plan within MAX_RATIO at every count."""
    import ci_shard_plan as sp
    import db2_shard_plan as dsp
    import det_sweep_plan as dsw

    durations = dsw.load_durations()
    assert durations
    names = [n for n, c in dsw.case_dirs().items() if dsw.is_db2(c)]
    sp.check_measured([n for n in names if n not in durations], len(names), "Db2 case")
    for n in range(2, dsw.DB2_MAX_SHARDS + 1):
        check = dsp.plan_check(names, durations, n)
        assert check["warning"] is None, f"{n} shards: {check['warning']}"
