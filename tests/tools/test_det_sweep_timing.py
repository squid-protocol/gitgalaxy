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
    assert (a["cases"], a["planned_s"], a["case_s"], a["setup_s"], a["sweep_s"], a["job_s"]) == (2, 1600, 1600, 200, 400, 600)
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
