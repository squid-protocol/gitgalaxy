# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""Signal-coverage floor over the committed golden masters (#4108)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import signal_coverage  # noqa: E402


@pytest.mark.parametrize("fixture", signal_coverage.FIXTURES)
def test_no_signal_lost_its_golden_coverage(fixture):
    _, counts = signal_coverage.coverage(signal_coverage.REPO_ROOT / fixture)
    found = signal_coverage.problems(counts, signal_coverage.load_baseline(), signal_coverage.load_thin())
    assert not found, "\n".join(found)


def test_every_baselined_zero_has_a_reason():
    for label, reason in signal_coverage.load_baseline().items():
        assert reason.strip(), label


def test_problems_flags_both_directions():
    base = {"Gone Quiet": "corpus gap"}
    assert signal_coverage.problems({"Fires": 3, "Gone Quiet": 0}, base) == []
    lost = signal_coverage.problems({"Fires": 0, "Gone Quiet": 0}, base)
    assert len(lost) == 1 and "'Fires' now fires on no crucible file" in lost[0]
    gained = signal_coverage.problems({"Fires": 3, "Gone Quiet": 2}, base)
    assert len(gained) == 1 and "remove it from" in gained[0]


def test_thin_signal_below_its_floor_fails_and_at_floor_passes():
    thin = {"Barely There": 3}
    assert signal_coverage.problems({"Barely There": 3}, {}, thin) == []
    assert signal_coverage.problems({"Barely There": 9}, {}, thin) == []
    dropped = signal_coverage.problems({"Barely There": 1}, {}, thin)
    assert len(dropped) == 1 and "thin-coverage floor of 3" in dropped[0]
    # zero is the other gate's business: a thin signal at zero is reported there, not twice
    lost = signal_coverage.problems({"Barely There": 0}, {}, thin)
    assert len(lost) == 1 and "fires on no crucible file" in lost[0]


def test_thin_floors_take_the_lowest_fixture_and_never_lower():
    counts = [{"A": 4, "B": 30, "C": 2, "D": 0}, {"A": 6, "B": 31, "C": 2, "D": 5}]
    floors = signal_coverage.thin_floors(counts, {"E": 7, "C": 5})
    assert floors == {"A": 4, "C": 5, "E": 7}  # B is not thin, D is zero in one fixture, C keeps its higher floor


def test_every_thin_floor_is_a_positive_int_and_the_signal_is_reported():
    thin = signal_coverage.load_thin()
    assert thin
    for fixture in signal_coverage.FIXTURES:
        _, counts = signal_coverage.coverage(signal_coverage.REPO_ROOT / fixture)
        for label, floor in thin.items():
            assert isinstance(floor, int) and not isinstance(floor, bool) and floor > 0, label
            assert label in counts, f"{label!r} thin floor names a signal the golden no longer reports"
