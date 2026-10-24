"""#5604: the workflow's waits on the background Db2 start must outlast what they wait for."""

import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import det_sweep_plan as plan  # noqa: E402
import equivalence_db2 as d  # noqa: E402

PULL_TIMEOUT_S = 1800  # equivalence_db2.pull_image's per-attempt docker pull timeout
START_ATTEMPTS = 2  # _ensure_container: one start, one replace


def _steps():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8"))
    return [s for job in wf["jobs"].values() for s in job.get("steps", [])]


def _first_db_wait_s(run: str) -> int:
    loop = re.search(r"seq 1 (\d+)\)", run)
    nap = re.search(r"^\s*sleep (\d+)\s*$", run, re.M)
    assert loop and nap, "wait loop not found"
    return int(loop.group(1)) * int(nap.group(1))


def _prewarm_pull_wait_s(run: str) -> int:
    m = re.search(r"pulled = .*?for _ in range\((\d+)\):.*?time\.sleep\((\d+)\)", run, re.S)
    assert m, "prewarm pull-done wait not found"
    return int(m.group(1)) * int(m.group(2))


def _run_of(marker: str) -> str:
    found = [s["run"] for s in _steps() if marker in s.get("run", "") or marker in s.get("name", "")]
    assert len(found) == 1
    return found[0]


def test_first_db_wait_outlasts_both_start_attempts():
    run = _run_of("Wait for the first Db2 database")
    assert _first_db_wait_s(run) >= START_ATTEMPTS * d.READY_POLLS * 10


def test_prewarm_pull_wait_covers_one_pull_attempt():
    assert _prewarm_pull_wait_s(_run_of("db2_prewarm.py")) >= PULL_TIMEOUT_S


@pytest.mark.parametrize(("polls", "ok"), [(120, False), (539, False), (540, True)])
def test_parser_sees_the_old_bound(polls, ok):
    run = f"for _ in $(seq 1 {polls}); do\n  sleep 5\ndone"
    assert (_first_db_wait_s(run) >= START_ATTEMPTS * d.READY_POLLS * 10 + 300) is ok


def test_planner_wait_constant_is_the_workflows_wait():
    assert plan.DB2_WAIT_S == _first_db_wait_s(_run_of("Wait for the first Db2 database"))


def _db2_plan(n_cases: int, n_shards: int, per_case_s: float):
    names = [f"d{i:03d}" for i in range(n_cases)]
    p = {
        "mode": "narrow",
        "cases": [],
        "db2_cases": names,
        "matrix": [],
        "db2_matrix": [f"{i}/{n_shards}" for i in range(1, n_shards + 1)],
    }
    return p, {c: per_case_s for c in names}


@pytest.mark.parametrize(
    ("n_cases", "n_shards", "per_case_s"), [(1, 1, 10.0), (4, 1, 200.0), (40, 2, 200.0), (200, 6, 600.0)]
)
def test_db2_timeout_covers_the_wait_and_the_slowest_sweep(n_cases, n_shards, per_case_s):
    p, dur = _db2_plan(n_cases, n_shards, per_case_s)
    t = plan.timeouts_for(p, dur)["db2_timeout"]
    sweep_s = -(-n_cases // n_shards) * per_case_s / plan.PROOF_JOBS
    assert t * 60 >= plan.SHARD_SETUP_S + plan.DB2_WAIT_S + min(
        sweep_s, (plan.DB2_TIMEOUT_CEILING * 60 - plan.DB2_WAIT_S) / 1.5
    )
    assert plan.DB2_TIMEOUT_FLOOR <= t <= plan.DB2_TIMEOUT_CEILING


def test_db2_timeout_without_durations_still_outlasts_the_wait():
    p, _ = _db2_plan(3, 1, 1.0)
    assert plan.timeouts_for(p, None)["db2_timeout"] * 60 >= plan.SHARD_SETUP_S + plan.DB2_WAIT_S


def test_real_plan_db2_timeout_outlasts_the_wait():
    dur = plan.load_durations()
    full = {"mode": "full", "cases": "all", "db2_cases": "all"}
    full["matrix"], full["db2_matrix"] = [f"{i}/6" for i in range(1, 7)], plan.db2_shards_for(full, durations=dur)
    assert plan.timeouts_for(full, dur)["db2_timeout"] * 60 >= plan.SHARD_SETUP_S + plan.DB2_WAIT_S


def test_db2_job_timeout_fallback_outlasts_the_wait_and_a_target_sweep():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8"))
    fallback = re.search(r"db2_timeout\s*\|\|\s*'(\d+)'", wf["jobs"]["db2"]["timeout-minutes"])
    assert fallback, "db2 timeout fallback not found"
    wait_s = _first_db_wait_s(_run_of("Wait for the first Db2 database"))
    assert int(fallback.group(1)) * 60 >= plan.SHARD_SETUP_S + wait_s + plan.DB2_TARGET_S
