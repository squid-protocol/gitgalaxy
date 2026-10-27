"""#5919 slice 4: the Db2 shard model's measured setup and predicted ratio (db2_shard_plan.py) and det_sweep_plan's use."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import db2_shard_plan as d2  # noqa: E402
import det_sweep_plan as plan  # noqa: E402

FALLBACK = 420.0


def _row(setup, kind="db2", proven=5):
    return {"kind": kind, "setup_s": setup, "proven": proven}


@pytest.mark.parametrize(
    ("rows", "want"),
    [
        ([], FALLBACK),  # nothing measured
        ([_row(200), _row(210)], FALLBACK),  # fewer than MIN_ROWS
        ([_row(None), _row(None), _row(None)], FALLBACK),  # killed before the sweep
        ([_row(200), _row(220), _row(240), _row(900, proven=0)], 220.0),  # a shard that proved nothing is ignored
        ([_row(200), _row(220), _row(240), _row(100, kind="shard")], 220.0),  # another kind is ignored
        ([_row(10), _row(20), _row(30)], FALLBACK * d2.CLAMP[0]),  # clamped below
        ([_row(5000), _row(6000), _row(7000)], FALLBACK * d2.CLAMP[1]),  # clamped above
    ],
)
def test_measured_setup_median_clamp_and_fallback(rows, want):
    assert d2.measured_setup_s(rows, "db2", FALLBACK) == want


@pytest.mark.parametrize(
    ("weight", "n", "want"),
    [({}, 3, None), ({"a": 5.0}, 1, None), ({"a": 5.0}, 2, None), ({"a": 10.0, "b": 10.0}, 2, 1.0),
     ({"a": 30.0, "b": 10.0}, 2, 3.0)],
)  # fmt: skip
def test_predicted_ratio(weight, n, want):
    assert d2.predicted_ratio(weight, n) == want


def test_ratio_warning_only_over_the_limit():
    assert d2.ratio_warning(None) is None and d2.ratio_warning(1.3) is None
    assert "1.31x" in d2.ratio_warning(1.31)


def test_plan_check_balanced_and_lopsided():
    even = {f"c{i}": 100.0 for i in range(8)}
    assert d2.plan_check(even, even, 4) == {"ratio": 1.0, "warning": None}
    lop = {"big": 1000.0, "s1": 10.0, "s2": 10.0}
    assert d2.plan_check(lop, lop, 3)["warning"]


def _timing_dir(root: Path, name: str, setup: int, kind: str = "db2") -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "timing.json").write_text(
        json.dumps(
            {"kind": kind, "shard": "1/2", "marks": {"job_start": 1000, "sweep_start": 1000 + setup, "sweep_end": 2000}}
        ),
        encoding="utf-8",
    )
    (d / "sweep.json").write_text(json.dumps({"det": {"c": {"seconds": 5}}}), encoding="utf-8")


def test_timing_artifacts_set_the_setup_and_a_shorter_setup_never_adds_shards(tmp_path):
    for i, s in enumerate((200, 220, 240)):
        _timing_dir(tmp_path, f"s{i}", s)
    assert plan.db2_setup_from([]) is None
    measured = plan.db2_setup_from([tmp_path])
    assert measured == 220.0 < plan.DB2_SETUP_S
    names = [f"d{i:03d}" for i in range(40)]
    p, dur = {"mode": "narrow", "cases": [], "db2_cases": names}, {c: 200.0 for c in names}
    typed = plan.db2_shards_for(p, durations=dur)
    fast = plan.db2_shards_for(p, durations=dur, setup_s=measured)
    assert len(fast) <= len(typed)
    p["db2_matrix"], p["matrix"] = fast, []
    assert plan.timeouts_for(p, dur, measured)["db2_timeout"] <= plan.timeouts_for(p, dur)["db2_timeout"]


def test_unreadable_timing_keeps_the_typed_setup(tmp_path):
    assert plan.db2_setup_from([tmp_path]) == plan.DB2_SETUP_S


def test_evidence_plan_takes_the_measured_setup(tmp_path):
    dur = plan.load_durations()
    assert dur
    base = plan.evidence_plan(dur)
    cheap = plan.evidence_plan(dur, db2_setup_s=plan.DB2_SETUP_S * d2.CLAMP[0])
    assert len(cheap["db2_parts"]) <= len(base["db2_parts"]) and cheap["db2_timeout"] <= base["db2_timeout"]


def test_emit_adds_the_predicted_ratio_only_with_a_db2_matrix(tmp_path, capsys):
    names = [f"d{i:03d}" for i in range(40)]
    dur = {c: 200.0 for c in names}
    p = {"mode": "narrow", "cases": [], "db2_cases": names}
    plan.emit(p, None, dur)
    assert 1.0 <= p["db2_ratio"] <= plan.MAX_RATIO
    none = {"mode": "narrow", "cases": [], "db2_cases": []}
    plan.emit(none, None, dur)
    assert "db2_ratio" not in none
    capsys.readouterr()
