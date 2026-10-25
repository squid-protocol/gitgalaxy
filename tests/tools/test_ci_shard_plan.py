"""#5919: shard counts and job timeouts from measured durations (ci_shard_plan.py), and det_sweep_plan's use of them
for the Db2 shards."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import ci_shard_plan as sp  # noqa: E402
import det_sweep_plan as plan  # noqa: E402
import proof_sweep as ps  # noqa: E402


def _w(n: int, secs: float = 100.0) -> dict[str, float]:
    return {f"c{i:03d}": secs for i in range(n)}


def test_no_work_no_shards():
    assert sp.shards_for({}, 400, 4, 900, 6) == 0


def test_one_case_is_one_shard():
    assert sp.shards_for(_w(1), 400, 4, 900, 6) == 1


def test_boundary_work_exactly_fits_one_shard():
    # setup 400 + 8 cases x 250 s / 4 jobs = 900 s: fits; one more case does not
    assert sp.shards_for(_w(8, 250), 400, 4, 900, 6) == 1
    assert sp.shards_for(_w(9, 250), 400, 4, 900, 6) == 2


def test_cap_holds_when_nothing_fits():
    assert sp.shards_for(_w(500, 600), 400, 4, 900, 6) == 6
    assert sp.shards_for(_w(500, 600), 400, 4, 900, 1) == 1
    assert sp.shards_for(_w(500, 600), 400, 4, 900, 0) == 1  # a cap below 1 is 1


def test_setup_over_target_caps_out_rather_than_looping():
    assert sp.shards_for(_w(10), 2000, 4, 900, 6) == 6


def test_never_more_shards_than_cases():
    assert sp.shards_for(_w(2, 5000), 400, 4, 900, 6) == 2


def test_setup_cost_trades_against_shard_count():
    # the same work needs more shards when each shard starts slower
    w = _w(40, 100)
    assert sp.shards_for(w, 100, 4, 900, 20) < sp.shards_for(w, 600, 4, 900, 20)


def test_growth_needs_no_edit_and_stays_balanced():
    """45 -> 70 -> 140 Db2 cases: the count follows the work (up to the cap) and the slowest/fastest shard stays <= 1.3."""
    prev = 0
    for n in (45, 70, 140):
        durations = {f"case{i:03d}": 60.0 + (i * 37 % 200) for i in range(n)}
        w, missing = sp.weights(durations, durations)
        assert missing == []
        k = sp.shards_for(w, plan.DB2_SETUP_S, plan.PROOF_JOBS, plan.DB2_TARGET_S, 20)
        assert k >= prev
        prev = k
        shards = ps.split_cases(sorted(durations), k, durations)
        loads = [sum(durations[c] for c in s) for s in shards]
        assert max(loads) / min(loads) <= 1.3


def test_timeout_is_margin_over_the_slowest_shard_between_floor_and_ceiling():
    w = _w(8, 250)  # one shard: 400 + 500 s planned
    assert sp.timeout_minutes(w, 1, 400, 4, 5, 90) == 23  # 900 s x 1.5 = 22.5 min, rounded up
    assert sp.timeout_minutes(w, 1, 400, 4, 40, 90) == 40  # the floor
    assert sp.timeout_minutes(w, 1, 400, 4, 5, 10) == 10  # the ceiling
    assert sp.timeout_minutes({}, 0, 400, 4, 25, 45) == 25  # no cases: the floor


def test_weights_fill_unmeasured_with_the_median():
    w, missing = sp.weights(["a", "b", "c", "d"], {"a": 10, "b": 30, "c": 20})
    assert missing == ["d"] and w["d"] == 20.0
    w, missing = sp.weights(["a", "b"], {})
    assert missing == ["a", "b"] and w == {"a": 1.0, "b": 1.0}


@pytest.mark.parametrize(("missing", "total", "fails"), [
    (0, 70, False), (2, 5, False),  # the grace allowance, even when it is over the fraction
    (3, 70, False), (17, 70, False), (18, 70, True), (31, 70, True),  # the 31-of-70 of #5882
])  # fmt: skip
def test_unmeasured_fails_loudly_past_the_grace(missing, total, fails):
    names = [f"c{i}" for i in range(missing)]
    if fails:
        with pytest.raises(sp.PlanError, match="no measured duration"):
            sp.check_measured(names, total)
    else:
        sp.check_measured(names, total)


def test_headroom_plans_below_the_target_and_adds_a_shard_at_the_boundary():
    # 400 + 8 x 250 / 4 = 900 s fits the target exactly, but not 80% of it
    assert sp.shards_for(_w(8, 250), 400, 4, 900, 6, headroom=1.0) == 1
    assert sp.shards_for(_w(8, 250), 400, 4, 900, 6, headroom=sp.HEADROOM) == 2
    assert sp.shards_for(_w(500, 600), 400, 4, 900, 6, headroom=sp.HEADROOM) == 6  # the cap still holds


def test_a_long_case_bounds_its_shard_however_many_jobs_there_are():
    w = {**_w(7, 100), "pole": 432.0}
    assert sp.shard_seconds(w, 1, 0, 4) == 432.0  # 1132 s / 4 jobs = 283 s, but the pole alone is 432 s
    assert sp.shard_seconds(w, 2, 100, 4) == 100 + 432.0
    # a long pole that alone busts the target cannot be split: more shards do not help, the cap holds
    assert sp.shards_for({"pole": 2000.0, **_w(3)}, 0, 4, 900, 6) == 4
    assert sp.timeout_minutes(w, 1, 0, 4, 1, 99, margin=1.0) == 8  # ceil(432 / 60)


def test_the_pole_is_placed_alone_first_so_it_does_not_share_with_an_even_load():
    w = {**_w(12, 100), "pole": 432.0}
    loads = sp._shard_loads(w, 3)
    assert sum(c == 432.0 for _, c in loads) == 1 and min(x[0] for x in loads) >= 400  # no shard is starved by it


def test_pool_cap_shrinks_under_queue_pressure():
    assert sp.pool_cap(6, None) == 6 and sp.pool_cap(6, 8) == 6
    assert sp.pool_cap(6, 9) == 3 and sp.pool_cap(1, 99) == 1


def _db2_plan(n: int) -> tuple[dict, dict[str, float]]:
    names = [f"d{i:03d}" for i in range(n)]
    return {"mode": "narrow", "cases": [], "db2_cases": names}, {c: 200.0 for c in names}


def test_db2_shards_follow_the_measured_work_and_timeout_follows_the_shards():
    p, dur = _db2_plan(4)
    assert plan.db2_shards_for(p, durations=dur) == ["1/1"]
    p, dur = _db2_plan(40)  # 8000 s over 4 jobs: > 1 shard at 420 s setup
    m = plan.db2_shards_for(p, durations=dur)
    assert 1 < len(m) <= plan.DB2_MAX_SHARDS and m[-1] == f"{len(m)}/{len(m)}"
    p["db2_matrix"], p["matrix"] = m, []
    t = plan.timeouts_for(p, dur)
    assert (
        plan.DB2_TIMEOUT_FLOOR <= t["db2_timeout"] <= plan.DB2_TIMEOUT_CEILING and t["timeout"] == plan.DEFAULT_TIMEOUT
    )


def test_db2_plan_aims_below_the_budget_and_every_shard_fits_the_headroom_target():
    p, dur = _db2_plan(24)  # 24 x 200 s
    m = plan.db2_shards_for(p, durations=dur)
    n = len(m)
    w, _ = sp.weights(p["db2_cases"], dur)
    assert sp.shard_seconds(w, n, plan.DB2_SETUP_S, plan.PROOF_JOBS) <= plan.DB2_TARGET_S * plan.DB2_HEADROOM
    assert (
        n == 1 or sp.shard_seconds(w, n - 1, plan.DB2_SETUP_S, plan.PROOF_JOBS) > plan.DB2_TARGET_S * plan.DB2_HEADROOM
    )


def test_db2_shards_busy_queue_halves_the_cap():
    p, dur = _db2_plan(400)
    assert len(plan.db2_shards_for(p, durations=dur)) == plan.DB2_MAX_SHARDS
    assert len(plan.db2_shards_for(p, durations=dur, waiting=99)) == plan.DB2_MAX_SHARDS // 2


def test_db2_plan_with_unmeasured_cases_fails_and_nothing_to_prove_is_no_shards():
    p, dur = _db2_plan(10)
    with pytest.raises(sp.PlanError):
        plan.db2_shards_for(p, durations={})
    assert plan.db2_shards_for({"mode": "narrow", "db2_cases": []}, durations={}) == []
    assert plan.db2_shards_for({"mode": "ports", "db2_cases": ["x"]}, durations={}) == []


def test_no_durations_keeps_the_count_based_plan_and_default_timeouts():
    p, _ = _db2_plan(13)
    assert plan.db2_shards_for(p) == ["1/3", "2/3", "3/3"]
    assert plan.timeouts_for({**p, "matrix": [], "db2_matrix": ["1/1"]}, None) == {
        "timeout": plan.DEFAULT_TIMEOUT, "db2_timeout": plan.DB2_TIMEOUT_FLOOR}  # fmt: skip


def test_the_committed_durations_size_a_full_sweep_within_the_pool():
    """The real Db2 cases on disk, with the committed durations: the full sweep plans (no PlanError) inside the cap."""
    dur = plan.load_durations()
    assert dur
    full = {"mode": "full", "cases": "all", "db2_cases": "all"}
    m = plan.db2_shards_for(full, durations=dur)
    assert 1 <= len(m) <= plan.DB2_MAX_SHARDS
    w, _ = sp.weights(plan.db2_names(full), dur)  # every planned shard under the target with headroom, or the cap
    n = len(m)
    assert n == plan.DB2_MAX_SHARDS or (
        sp.shard_seconds(w, n, plan.DB2_SETUP_S, plan.PROOF_JOBS) <= plan.DB2_TARGET_S * plan.DB2_HEADROOM
    )
    full["matrix"], full["db2_matrix"] = [f"{i}/6" for i in range(1, 7)], m
    t = plan.timeouts_for(full, dur)
    assert plan.TIMEOUT_FLOOR <= t["timeout"] <= plan.TIMEOUT_CEILING
    assert plan.DB2_TIMEOUT_FLOOR <= t["db2_timeout"] <= plan.DB2_TIMEOUT_CEILING


def _workflow(name: str) -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def test_det_sweep_jobs_take_their_timeout_from_the_plan_after_the_durations_are_chosen():
    jobs = _workflow("det-sweep.yml")["jobs"]
    assert "needs.plan.outputs.timeout" in str(jobs["shard"]["timeout-minutes"])
    assert "needs.plan.outputs.db2_timeout" in str(jobs["db2"]["timeout-minutes"])
    assert {"timeout", "db2_timeout"} <= set(jobs["plan"]["outputs"])
    steps = [s.get("name", "") for s in jobs["plan"]["steps"]]
    sizing = [i for i, n in enumerate(steps) if n.startswith(("Plan the sweep", "Plan from the port diff"))]
    merges = [i for i, n in enumerate(steps) if n.startswith(("Choose the durations", "Merge the Db2 durations"))]
    assert len(merges) == 2 and max(merges) < min(sizing)


def test_evidence_refresh_lane_checks_out_what_the_planner_reads(tmp_path):
    import json
    import shutil
    import subprocess

    steps = _workflow("evidence-refresh.yml")["jobs"]["lane"]["steps"]
    (co,) = [s for s in steps if "sparse-checkout" in (s.get("with") or {})]
    paths = co["with"]["sparse-checkout"].split()
    assert "tests/tools/ci_shard_plan.py" in paths and "tests/equivalence/det_sweep_durations.json" in paths
    for rel in paths:  # copy exactly the sparse tree (the case.json glob included)
        for src in ROOT.glob(rel):
            dst = tmp_path / src.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
    out = subprocess.run(
        [sys.executable, "-I", str(tmp_path / "tests" / "tools" / "det_sweep_plan.py"), "--db2-full-matrix"],
        capture_output=True, text=True, check=True, cwd=tmp_path,
    ).stdout  # fmt: skip
    parts = json.loads(out)
    assert 1 <= len(parts) <= plan.DB2_MAX_SHARDS


def _real_db2_durations() -> dict[str, float]:
    """db2_shards_for names the Db2 cases of the repo on disk; measure them so only the tmp tree under test is in question."""
    return {n: 100.0 for n in plan.case_dirs()}


def _evidence_cases(tmp_path, n_det, n_db2, n_records):
    for i in range(n_det + n_db2):
        d = tmp_path / f"case{i:03d}"
        d.mkdir()
        (d / "case.json").write_text('{"db2": true}' if i >= n_det else "{}", encoding="utf-8")
    for i in range(n_records):
        (tmp_path / f"rec{i:04d}").mkdir()
        (tmp_path / f"rec{i:04d}" / "evidence.json").write_text("{}", encoding="utf-8")


def test_evidence_plan_without_durations_keeps_the_old_shape(tmp_path):
    _evidence_cases(tmp_path, 4, 2, 3)
    ep = plan.evidence_plan(None, cases_dir=tmp_path)
    assert ep["db2_parts"][-1] == "records" and len(ep["sweep_matrix"]) == 4 and len(ep["records_matrix"]) == 6
    assert ep["sweep_timeout"] == ep["records_timeout"] == ep["db2_timeout"] == 90


@pytest.mark.parametrize("n_records", [0, 1, 10, 40, 80, 400])
def test_evidence_records_shards_follow_the_count_up_to_the_cap(tmp_path, n_records):
    _evidence_cases(tmp_path, 2, 0, n_records)
    durations = {f"case{i:03d}": 100.0 for i in range(2)} | _real_db2_durations()
    ep = plan.evidence_plan(durations, cases_dir=tmp_path)
    k = len(ep["records_matrix"])
    if n_records == 0:
        assert k == 6 and ep["records_timeout"] == 90  # nothing to size from: the fallback matrix, not an empty one
        return
    else:
        assert 1 <= k <= plan.EVIDENCE_RECORDS_MAX_SHARDS
    if n_records >= 80:
        assert k == plan.EVIDENCE_RECORDS_MAX_SHARDS
    assert 25 <= ep["records_timeout"] <= plan.EVIDENCE_CEILING


def test_evidence_plan_sweep_grows_with_the_work_and_busy_pool_halves_the_cap(tmp_path):
    _evidence_cases(tmp_path, 120, 0, 0)
    durations = {f"case{i:03d}": 300.0 for i in range(120)} | _real_db2_durations()
    calm = plan.evidence_plan(durations, cases_dir=tmp_path)
    busy = plan.evidence_plan(durations, waiting=sp.BUSY_ABOVE + 1, cases_dir=tmp_path)
    assert len(calm["sweep_matrix"]) == plan.EVIDENCE_SWEEP_MAX_SHARDS
    assert len(busy["sweep_matrix"]) == max(1, plan.EVIDENCE_SWEEP_MAX_SHARDS // 2)


def test_evidence_plan_fails_loudly_on_unmeasured_cases(tmp_path):
    _evidence_cases(tmp_path, 20, 0, 0)
    with pytest.raises(sp.PlanError):
        plan.evidence_plan({"case000": 50.0} | _real_db2_durations(), cases_dir=tmp_path)


def test_evidence_refresh_shard_jobs_are_planned_not_typed():
    jobs = _workflow("evidence-refresh.yml")["jobs"]
    outs = jobs["lane"]["outputs"]
    for job, key in (("db2-part", "db2"), ("sweep", "sweep"), ("records", "records")):
        assert f"needs.lane.outputs.{key}_timeout" in str(jobs[job]["timeout-minutes"])
        matrix = jobs[job]["strategy"]["matrix"]
        assert all(isinstance(v, str) and "fromJSON" in v for v in matrix.values())
        assert f"{key}_timeout" in outs
    assert {"sweep_matrix", "records_matrix", "db2_parts"} <= set(outs)


def test_evidence_plan_runs_from_the_lane_sparse_tree(tmp_path):
    import json
    import shutil
    import subprocess

    steps = _workflow("evidence-refresh.yml")["jobs"]["lane"]["steps"]
    (co,) = [s for s in steps if "sparse-checkout" in (s.get("with") or {})]
    for rel in co["with"]["sparse-checkout"].split():
        for src in ROOT.glob(rel):
            dst = tmp_path / src.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
    out = tmp_path / "gh_output"
    subprocess.run(
        [sys.executable, "-I", str(tmp_path / "tests" / "tools" / "det_sweep_plan.py"), "--evidence-plan",
         "--github-output", str(out)],
        capture_output=True, text=True, check=True, cwd=tmp_path,
    )  # fmt: skip
    kv = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    lane_outs = _workflow("evidence-refresh.yml")["jobs"]["lane"]["outputs"]
    assert set(kv) == {k for k, v in lane_outs.items() if "steps.db2parts" in v}
    assert json.loads(kv["records_matrix"])[0].startswith("1/")
    assert 25 <= int(json.loads(kv["sweep_timeout"])) <= plan.EVIDENCE_CEILING
