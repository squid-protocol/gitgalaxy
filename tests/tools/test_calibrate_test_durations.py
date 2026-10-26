# ruff: noqa: S101
"""#5133: the nightly parts' durations are scaled to the part's pytest wall before they are merged."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import calibrate_test_durations as ctd  # noqa: E402
import merge_test_durations as mtd  # noqa: E402


def test_the_sum_becomes_the_wall_and_the_weights_keep_their_ratio():
    out = ctd.calibrate({"a::t": 30.0, "b::t": 10.0}, 20.0)
    assert out == {"a::t": 15.0, "b::t": 5.0}


@pytest.mark.parametrize("wall", [0, -3, float("nan")])
def test_a_wall_that_is_not_positive_is_refused(wall):
    with pytest.raises(ValueError, match="wall"):
        ctd.calibrate({"a::t": 1.0}, wall)


def test_a_part_with_no_seconds_is_refused():
    with pytest.raises(ValueError, match="no recorded"):
        ctd.calibrate({}, 10.0)


def test_main_reads_both_file_shapes_and_the_output_merges(tmp_path):
    plain, times, out1, out2 = (tmp_path / n for n in ("p.json", "t.json", "o1.json", "o2.json"))
    plain.write_text(json.dumps({"a::t": 2.0, "b::t": 2.0}), encoding="utf-8")
    times.write_text(json.dumps({"seconds": {"c::t": 9.0}, "slow": {}}), encoding="utf-8")
    assert ctd.main([str(plain), str(out1), "--wall", "8", "--jobs", "1"]) == 0
    assert ctd.main([str(times), str(out2), "--wall", "3", "--jobs", "1"]) == 0
    merged = mtd.merge([json.loads(out1.read_text()), json.loads(out2.read_text())])
    assert merged == {"a::t": 4.0, "b::t": 4.0, "c::t": 3.0}


def test_main_refuses_a_file_that_is_not_an_object(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1]", encoding="utf-8")
    with pytest.raises(SystemExit):
        ctd.main([str(bad), str(tmp_path / "o.json"), "--wall", "5"])


def test_the_nightly_workflow_calibrates_after_pytest_with_the_wall_it_wrote():
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "smoke-test.yml").read_text(encoding="utf-8"))
    steps = doc["jobs"]["full-suite-part"]["steps"]
    names = [str(s.get("name", "")) for s in steps]
    at_pytest = next(i for i, n in enumerate(names) if n.startswith("Golden Record Integration Test"))
    at_cal = next(i for i, n in enumerate(names) if n.startswith("Keep this part's durations"))
    assert at_cal > at_pytest
    cal = steps[at_cal]
    assert cal["if"] == "github.event_name == 'schedule' && success()"
    assert "calibrate_test_durations.py" in cal["run"]
    assert "pytest-wall-part-${{ matrix.group }}.txt" in cal["run"]
    assert "pytest-wall-part-$GROUP.txt" in steps[at_pytest]["run"]
    assert "durations-part-${{ matrix.group }}.json" in cal["run"]  # the name the upload step and the merge job read


def test_jobs_scale_the_sum_to_serial_seconds_and_main_defaults_to_the_planners_jobs(tmp_path):
    # 2026-10-26: scaled to the bare wall, the cache was a third of the serial seconds suite_shard_plan divides by JOBS
    import suite_shard_plan

    assert ctd.calibrate({"a::t": 30.0, "b::t": 10.0}, 20.0, jobs=3) == {"a::t": 45.0, "b::t": 15.0}
    src, out = tmp_path / "p.json", tmp_path / "o.json"
    src.write_text(json.dumps({"a::t": 1.0, "b::t": 3.0}), encoding="utf-8")
    assert ctd.main([str(src), str(out), "--wall", "10"]) == 0
    assert sum(json.loads(out.read_text()).values()) == pytest.approx(10.0 * suite_shard_plan.JOBS)
