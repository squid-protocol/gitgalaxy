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
    found = signal_coverage.problems(counts, signal_coverage.load_baseline())
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
