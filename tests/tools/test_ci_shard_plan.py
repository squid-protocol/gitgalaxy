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
    assert plan.TIMEOUT_FLOOR <= t["db2_timeout"] <= plan.TIMEOUT_CEILING and t["timeout"] == plan.DEFAULT_TIMEOUT


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
        "timeout": plan.DEFAULT_TIMEOUT, "db2_timeout": plan.DEFAULT_TIMEOUT}  # fmt: skip


def test_the_committed_durations_size_a_full_sweep_within_the_pool():
    """The real Db2 cases on disk, with the committed durations: the full sweep plans (no PlanError) inside the cap."""
    dur = plan.load_durations()
    assert dur
    full = {"mode": "full", "cases": "all", "db2_cases": "all"}
    m = plan.db2_shards_for(full, durations=dur)
    assert 1 <= len(m) <= plan.DB2_MAX_SHARDS
    full["matrix"], full["db2_matrix"] = [f"{i}/6" for i in range(1, 7)], m
    t = plan.timeouts_for(full, dur)
    assert all(plan.TIMEOUT_FLOOR <= v <= plan.TIMEOUT_CEILING for v in t.values())
