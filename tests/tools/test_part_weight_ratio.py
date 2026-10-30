# ruff: noqa: S101
"""#5162: the per-part actual/weight reader scores only ids both files hold and reads both file shapes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import part_weight_ratio as pwr  # noqa: E402


def test_ratio_uses_shared_ids_and_counts_the_unweighted():
    got = pwr.ratio({"a": 3.0, "b": 1.0, "new": 9.0}, {"a": 2.0, "b": 2.0, "gone": 50.0})
    assert got == (1.0, 2, 1)


def test_nothing_shared_or_zero_weight_is_none():
    assert pwr.ratio({"a": 1.0}, {"b": 1.0}) is None
    assert pwr.ratio({"a": 1.0}, {"a": 0.0}) is None


def test_read_parts_pairs_the_files_and_reads_both_shapes(tmp_path: Path):
    (tmp_path / "test-times-part-1").mkdir()
    d = tmp_path / "test-times-part-1"
    (d / "times-part-1.json").write_text(json.dumps({"seconds": {"a": 4.0}, "slow": {}}), encoding="utf-8")
    (d / "restored-durations-part-1.json").write_text(json.dumps({"a": 2.0}), encoding="utf-8")
    (d / "times-part-2.json").write_text(json.dumps({"seconds": {"a": 1.0}}), encoding="utf-8")  # no weights beside it
    assert pwr.read_parts(tmp_path) == {1: (2.0, 1, 0)}


def test_summarize_reports_mean_and_spread_per_part():
    lines = pwr.summarize({"r1": {1: (0.5, 10, 2)}, "r2": {1: (0.7, 10, 0)}})
    assert lines[-1] == "part 1: mean 0.60, stdev 0.10 over 2 runs"
    assert pwr.summarize({})[-1].startswith("no run had")
