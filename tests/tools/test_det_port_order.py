"""#5882: det_port.py proves a shard's cases longest first (a long case started last idles the other workers)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import det_port  # noqa: E402
import proof_sweep  # noqa: E402


def test_the_longest_recorded_case_is_proven_first(monkeypatch):
    monkeypatch.setattr(proof_sweep, "load_durations", lambda: {"a": 10.0, "b": 300.0, "c": 50.0, "d": 50.0})
    assert det_port.proof_order(["a", "b", "c", "d"]) == ["b", "c", "d", "a"]  # ties by name


def test_an_unmeasured_case_weighs_the_median(monkeypatch):
    monkeypatch.setattr(proof_sweep, "load_durations", lambda: {"a": 10.0, "b": 300.0, "c": 50.0})
    assert det_port.proof_order(["new", "a", "b", "c"]) == ["b", "c", "new", "a"]
