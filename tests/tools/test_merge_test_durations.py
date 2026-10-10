"""merge_test_durations.py: the parts' pytest-split durations merge into one file (#4847)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import merge_test_durations as mtd  # noqa: E402


def test_union_of_disjoint_parts_is_sorted():
    assert mtd.merge([{"b::t": 2.0}, {"a::t": 1.5}]) == {"a::t": 1.5, "b::t": 2.0}


def test_same_nodeid_with_the_same_seconds_is_fine_but_not_different_ones():
    assert mtd.merge([{"a::t": 1.0}, {"a::t": 1.0}]) == {"a::t": 1.0}
    with pytest.raises(ValueError, match="a::t"):
        mtd.merge([{"a::t": 1.0}, {"a::t": 3.0}])


def test_main_writes_the_merged_file(tmp_path):
    p1, p2, out = tmp_path / "p1.json", tmp_path / "p2.json", tmp_path / "out.json"
    p1.write_text(json.dumps({"x::one": 0.5}), encoding="utf-8")
    p2.write_text(json.dumps({"x::two": 4.0}), encoding="utf-8")
    assert mtd.main([str(out), str(p1), str(p2)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"x::one": 0.5, "x::two": 4.0}


def test_main_refuses_a_file_that_is_not_a_durations_object(tmp_path):
    bad, out = tmp_path / "bad.json", tmp_path / "out.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(SystemExit):
        mtd.main([str(out), str(bad)])
    assert not out.exists()
