"""#5135: the det sweep measurement maths, offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import det_sweep_measure as m

RUN = {"created_at": "2026-10-15T10:00:00Z"}


def _job(name, created, started=None, done=None, conclusion="success"):
    return {"name": name, "created_at": created, "started_at": started, "completed_at": done, "conclusion": conclusion}


def test_run_stats_counts_jobs_and_wall():
    jobs = [
        _job("plan", "2026-10-15T10:00:00Z", "2026-10-15T10:00:30Z", "2026-10-15T10:01:00Z"),
        _job("shard", "2026-10-15T10:01:00Z", "2026-10-15T10:11:00Z", "2026-10-15T10:20:00Z"),
        _job("det", "2026-10-15T10:20:00Z", "2026-10-15T10:20:10Z", "2026-10-15T10:21:00Z"),
    ]
    s = m.run_stats(RUN, jobs)
    assert s["jobs"] == 3
    assert s["det_wall_s"] == 21 * 60
    assert s["max_queue_s"] == 600
    assert s["det_green"]


def test_run_stats_none_without_completed_det():
    assert m.run_stats(RUN, [_job("plan", "2026-10-15T10:00:00Z")]) is None
    assert m.run_stats(RUN, [_job("det", "2026-10-15T10:00:00Z", conclusion="skipped")]) is None


def test_failed_det_is_counted_not_green():
    jobs = [_job("det", "2026-10-15T10:00:00Z", "2026-10-15T10:00:01Z", "2026-10-15T10:05:00Z", "failure")]
    assert m.summarize([m.run_stats(RUN, jobs)])["det_not_green"] == 1


def test_split_and_summarize():
    rows = [("2026-10-14T00:00:00Z", {"x": 1}), ("2026-10-14T21:52:10Z", {"x": 2}), ("2026-10-16T00:00:00Z", {"x": 3})]
    before, after = m.split(rows, "2026-10-14T21:52:10Z")
    assert before == [{"x": 1}] and after == [{"x": 2}, {"x": 3}]
    rs = [{"jobs": n, "det_wall_s": n * 60.0, "max_queue_s": 0.0, "det_green": True} for n in (24, 6, 12, 8)]
    out = m.summarize(rs)
    assert out["runs"] == 4 and out["jobs"]["median"] == 10 and out["det_wall_s"]["median"] == 600


def test_summarize_empty_side():
    assert m.summarize([])["jobs"] == {"median": 0.0, "p75": 0.0}


def _db2(i, name, start, done, conclusion="success"):
    return {
        "id": i,
        "name": name,
        "created_at": start,
        "started_at": start,
        "completed_at": done,
        "conclusion": conclusion,
    }


def _t(minute):
    return f"2026-10-15T10:{minute:02d}:00Z"


def test_db2_run_stats_slowest_fastest_ratio():
    jobs = [_db2(1, "db2 1/2", _t(0), _t(10)), _db2(2, "db2 2/2", _t(0), _t(15)), _job("det", _t(0), _t(0), _t(16))]
    s = m.db2_run_stats(RUN, jobs)
    assert (s["db2_jobs"], s["slowest_s"], s["fastest_s"]) == (2, 900, 600)
    assert s["ratio"] == 1.5 and s["complete"] and s["timed_out"] == 0


def test_db2_run_stats_none_without_db2_success():
    assert m.db2_run_stats(RUN, [_job("det", _t(0), _t(0), _t(1))]) is None
    assert m.db2_run_stats(RUN, [_db2(1, "db2 1/1", _t(0), _t(5), "cancelled")]) is None
    assert m.db2_run_stats(RUN, [_db2(1, "db2 1/1", _t(0), None, "skipped")]) is None


def test_db2_timeout_versus_other_failure():
    jobs = [
        _db2(1, "db2 1/3", _t(0), _t(10)),
        _db2(2, "db2 2/3", _t(0), _t(30), "cancelled"),
        _db2(3, "db2 3/3", _t(0), _t(1), "failure"),
    ]
    s = m.db2_run_stats(
        RUN,
        jobs,
        {2: ["The job exceeded the maximum execution time of 18m0s"], 3: ["Process completed with exit code 1"]},
    )
    assert s["timed_out"] == 1 and s["other_failures"] == 1 and not s["complete"]
    # a timed-out job alone still yields a row, with no shard time
    only = m.db2_run_stats(RUN, [jobs[1]], {2: [m.TIMEOUT_TEXT]})
    assert only["timed_out"] == 1 and only["slowest_s"] == 0 and only["ratio"] == 1.0


def test_db2_single_shard_ratio_is_one():
    assert m.db2_run_stats(RUN, [_db2(1, "db2 1/1", _t(0), _t(7))])["ratio"] == 1.0


def test_db2_acceptance_groups_by_shard_count_and_limits():
    def row(n, slow, fast, **kw):
        base = {
            "db2_jobs": n,
            "slowest_s": slow,
            "fastest_s": fast,
            "ratio": slow / fast,
            "timed_out": 0,
            "other_failures": 0,
            "complete": True,
        }
        return base | kw

    rows = [row(3, 900, 800), row(3, 899, 600), row(3, 700, 700, complete=False, timed_out=1), row(5, 600, 500)]
    out = m.db2_acceptance(rows)
    assert out[3]["runs"] == 2 and out[3]["over_limit"] == 1  # 900 s is over: the limit is "under 15 min"
    assert out[3]["over_ratio"] == 1 and out[3]["timeouts"] == 1
    assert out[5] == {**out[5], "runs": 1, "over_limit": 0, "over_ratio": 0, "slowest_max_s": 600}
    assert m.db2_acceptance([]) == {}
