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
