"""#5882: the det sweep's shard telemetry -- shard.json (planned), timing.json (phases), the det job's report -- and the
Db2 durations Evidence Refresh records for det-sweep's plan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import det_sweep_timing as t  # noqa: E402
import proof_sweep as ps  # noqa: E402


def _epochs(tmp: Path, **marks: int) -> dict[str, Path]:
    out = {}
    for name, v in marks.items():
        (tmp / name).write_text(f"{v}\n", encoding="utf-8")
        out[name] = tmp / name
    return out


def _shard(d: Path, shard: str, kind: str, marks: dict[str, int], seconds: dict[str, float], unmeasured=()):
    d.mkdir(parents=True)
    files = _epochs(d, **marks)
    files["sweep_end"] = d / "never-written" if "sweep_end" not in marks else files["sweep_end"]
    (d / "timing.json").write_text(json.dumps(t.record(kind, shard, files)), encoding="utf-8")
    (d / "shard.json").write_text(json.dumps({"shard": shard, "cases": sorted(seconds),
                                              "planned_seconds": round(sum(seconds.values())),
                                              "unmeasured": list(unmeasured)}), encoding="utf-8")  # fmt: skip
    (d / "sweep.json").write_text(json.dumps({"det": {c: {"proved": True, "seconds": s} for c, s in seconds.items()}}))


def test_record_reads_each_mark_and_leaves_a_missing_one_null(tmp_path):
    marks = _epochs(tmp_path, job_start=100, sweep_start=160)
    marks["sweep_end"] = tmp_path / "missing"
    (tmp_path / "pre.json").write_text(json.dumps({"start": 110, "container": 80.0, "databases": {"GGDB": 82.0}}))
    r = t.record("db2", "1/6", marks, tmp_path / "pre.json")
    assert r["marks"] == {"job_start": 100, "sweep_start": 160, "sweep_end": None}
    assert r["db2"]["databases"] == {"GGDB": 82.0}
    assert t.record("db2", "1/6", marks, tmp_path / "no-prewarm.json")["db2"] is None


def test_report_rows_planned_against_measured_and_warns_on_imbalance_and_budget(tmp_path):
    _shard(tmp_path / "a", "1/2", "db2", {"job_start": 0, "sweep_start": 200, "sweep_end": 600}, {"x": 900, "y": 700})
    _shard(tmp_path / "b", "2/2", "db2", {"job_start": 0, "sweep_start": 200, "sweep_end": 1000}, {"z": 3000},
           unmeasured=["z"])  # fmt: skip
    rows = [t.row(d) for d in t._shard_dirs([tmp_path])]
    a, b = sorted(rows, key=lambda r: r["shard"])
    assert (a["cases"], a["planned_s"], a["case_s"], a["setup_s"], a["sweep_s"], a["job_s"]) == (
        2,
        1600,
        1600,
        200,
        400,
        600,
    )
    assert a["slowest"] == [(900, "x"), (700, "y")] and b["unmeasured"] == 1
    lines, warnings = t.report(rows)
    assert any("| db2 | 2/2 | 1 | 1 | 1 |" in ln for ln in lines)
    assert any("2.00x" in w and "2/2" in w for w in warnings)  # 800 s vs 400 s
    assert any("over the 15 min budget" in w for w in warnings)  # 1000 s


def test_a_killed_shard_is_named_not_dropped(tmp_path):
    _shard(tmp_path / "k", "3/6", "db2", {"job_start": 0, "sweep_start": 300}, {"slow": 1})
    (tmp_path / "k" / "sweep.json").unlink()  # killed by the timeout: no sweep.json
    (row,) = [t.row(d) for d in t._shard_dirs([tmp_path])]
    assert row["sweep_s"] is None and row["cases"] == 1
    assert any("no sweep end" in w for w in t.report([row])[1])


def test_report_takes_a_lone_artifact_extracted_straight_into_its_path(tmp_path):
    _shard(tmp_path / "db2-shards", "1/1", "db2", {"job_start": 0, "sweep_start": 1, "sweep_end": 2}, {"x": 1})
    assert t._shard_dirs([tmp_path / "db2-shards", tmp_path / "absent"]) == [tmp_path / "db2-shards"]


def test_merge_durations_overlays_src_and_keeps_the_rest(tmp_path):
    dst = tmp_path / "d.json"
    dst.write_text(json.dumps({"format": "det-sweep-durations/1", "det": {"a": 10, "b": 20}}))
    src = tmp_path / "s.json"
    src.write_text(json.dumps({"det": {"b": 99, "c": 5}}))
    assert t.merge_durations(src, dst) == 2
    assert json.loads(dst.read_text())["det"] == {"a": 10, "b": 99, "c": 5}
    assert t.merge_durations(tmp_path / "none.json", dst) == 0


def test_shard_plan_matches_the_split_and_names_the_unmeasured():
    cases = [f"c{i}" for i in range(9)]
    durations = {c: float(i + 1) for i, c in enumerate(cases[:6])}
    plans = [ps.shard_plan(cases, (i, 3), durations) for i in (1, 2, 3)]
    assert [p["cases"] for p in plans] == ps.split_cases(cases, 3, durations)
    assert sorted(c for p in plans for c in p["unmeasured"]) == ["c6", "c7", "c8"]
    median = sorted(durations.values())[3]
    assert sum(p["planned_seconds"] for p in plans) == round(sum(durations.values()) + 3 * median)


def test_every_db2_case_has_a_committed_duration_but_the_newest():
    """#5882: 31 of 70 Db2 cases had none, so the db2 shards were split by the median (1.7x apart). A case added since
    the last measurement may lack one until Evidence Refresh's nightly records it; more than a few means it stopped."""
    missing = [c for c in ps.det_cases(only_db2=True) if c not in ps.load_durations()]
    assert len(missing) <= 5, missing


yaml = pytest.importorskip("yaml")


def test_both_shard_kinds_ship_their_timing_and_det_reports_it():
    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8"))["jobs"]
    for job in ("shard", "db2"):
        steps = jobs[job]["steps"]
        assert "date +%s" in steps[0]["run"], f"{job}: the job's start is its first step"
        assert any("det_sweep_timing.py record" in s.get("run", "") and s.get("if") == "always()" for s in steps)
        (keep,) = [s for s in steps if s.get("name") == "Keep this shard's results"]
        assert "timing.json" in keep["with"]["path"] and "shard.json" in keep["with"]["path"]
    det = jobs["det"]["steps"]
    assert any("det_sweep_timing.py report" in s.get("run", "") for s in det)
    assert any((s.get("with") or {}).get("name") == "det-sweep-timing" for s in det)


def test_report_sums_each_phase_over_a_kinds_cases(tmp_path):
    _shard(tmp_path / "a", "1/1", "db2", {"job_start": 0, "sweep_start": 1, "sweep_end": 2}, {"x": 100, "y": 50})
    sweep = json.loads((tmp_path / "a" / "sweep.json").read_text())
    sweep["det"]["x"]["phases"] = {"java_maven": {"seconds": 60, "count": 1}, "db2_clp": {"seconds": 5, "count": 9}}
    sweep["det"]["y"]["phases"] = {"java_maven": {"seconds": 30, "count": 1}}
    (tmp_path / "a" / "sweep.json").write_text(json.dumps(sweep))
    (row,) = [t.row(d) for d in t._shard_dirs([tmp_path])]
    assert row["phases"] == {"java_maven": 90, "db2_clp": 5}
    lines, _ = t.report([row])  # one shard: no ratio, still the phases
    assert any("java_maven 90 s (60%)" in ln for ln in lines)


def test_phase_timer_sums_and_writes_phases_json(tmp_path, monkeypatch):
    import equivalence_common as common

    monkeypatch.setattr(common, "PHASES", {})
    for _ in range(2):
        with common.phase("db2_clp"):
            pass
    with pytest.raises(ValueError), common.phase("java_maven"):  # a failing step is still timed
        raise ValueError
    common.write_phases(tmp_path)
    data = json.loads((tmp_path / "phases.json").read_text())
    assert data["db2_clp"]["count"] == 2 and data["java_maven"]["count"] == 1


def test_a_case_takes_only_a_database_marked_ready(tmp_path, monkeypatch):
    """#5882: CI starts the sweep once GGDB is up; a database the background start is still creating is never taken."""
    pytest.importorskip("fcntl")  # the Db2 pool and container locks are flock: Linux-only (no Db2 on Windows, #5933)
    import equivalence_db2 as d

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(d.POOL_ENV, "3")
    ready = tmp_path / "ready"
    ready.mkdir()
    (ready / "GGDB1.ready").touch()
    monkeypatch.setenv(d.READY_ENV, str(ready))
    monkeypatch.setattr(d, "_LOCK", None)
    monkeypatch.setattr(d, "DATABASE", d.DATABASE0)
    d.hold_lock(timeout=0)
    assert d.DATABASE == "GGDB1"
    monkeypatch.setattr(d, "_LOCK", None)
    with pytest.raises(d.Db2PoolTimeoutError):  # GGDB1 held by this process's first lock, the others not ready
        d.hold_lock(timeout=0)
    monkeypatch.delenv(d.READY_ENV)
    assert d._ready("GGDB2")  # unset (a local run): every pool database


def test_the_db2_shard_waits_only_for_the_first_database():
    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8"))["jobs"]
    run = "\n".join(s.get("run", "") for s in jobs["db2"]["steps"])
    assert "GITGALAXY_DB2_READY_DIR=" in run and '.ready").touch()' in run
    (wait,) = [s for s in jobs["db2"]["steps"] if s.get("name") == "Wait for the first Db2 database"]
    assert "GGDB.ready" in wait["run"]


def test_the_db2_shard_wait_outlasts_the_harness_start_and_its_retry():
    """#5601: the wait for GGDB failed the step (cause db2_start) while the harness was still in its retry of a stuck start."""
    import re

    import equivalence_db2 as d

    jobs = yaml.safe_load((ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8"))["jobs"]
    (wait,) = [s for s in jobs["db2"]["steps"] if s.get("name") == "Wait for the first Db2 database"]
    polls = int(re.search(r"seq 1 (\d+)", wait["run"]).group(1))
    seconds = polls * int(re.search(r"sleep (\d+)", wait["run"]).group(1))
    assert seconds >= d.LOAD_WAIT + 2 * d.READY_POLLS * 10, seconds


def test_a_container_that_passed_the_full_check_is_not_checked_again(tmp_path, monkeypatch):
    """#5882: the ready mark (container id, start time, COBOL image id) skips the full check in a later process; a
    restarted container (another start time) does not match and is checked in full."""
    pytest.importorskip("fcntl")  # the Db2 pool and container locks are flock: Linux-only (no Db2 on Windows, #5933)
    import equivalence_db2 as d

    state = {"start": "2026-10-21T10:00:00Z"}
    calls = []

    def docker(*args, check=True, timeout=600, inp=None):
        calls.append(args[0])
        if args[0] == "inspect":
            return f"abc {state['start']} true\n"
        if args[0] == "images":
            return "img1\n"
        raise AssertionError(f"the full check ran: docker {args}")

    monkeypatch.setattr(d, "READY_MARK", tmp_path / "ready")
    monkeypatch.setattr(d, "_docker", docker)
    monkeypatch.setattr(d, "_CONTAINER_READY", False)
    (tmp_path / "ready").write_text("abc 2026-10-21T10:00:00Z img1\n")
    d._ensure_container()
    assert d._CONTAINER_READY and calls == ["inspect", "images"]
    monkeypatch.setattr(d, "_CONTAINER_READY", False)
    state["start"] = "2026-10-21T11:00:00Z"  # restarted: the full check (here: the fake's AssertionError)
    with pytest.raises(AssertionError, match="full check ran"):
        d._ensure_container()


def test_the_restored_durations_are_merged_over_the_committed_ones_never_copied():
    """#5882: run 39647808867's plan copied the nightly cache (no Db2 case in it) over the committed file and lost every
    seeded Db2 duration: 5-6 unmeasured cases a db2 shard, sweeps 382-770 s."""
    text = (ROOT / ".github" / "workflows" / "det-sweep.yml").read_text(encoding="utf-8")
    assert "cp durations-cache/det_sweep_durations.json" not in text
    assert (
        text.count(
            "merge-durations durations-cache/det_sweep_durations.json tests/equivalence/det_sweep_durations.json"
        )
        == 2
    )
