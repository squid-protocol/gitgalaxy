# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""History-dependent and spec-alignment equations against a scripted git
history (#4107). See tests/history_golden.py; re-bless with
``python tests/history_golden.py --bless`` and explain the change in the PR."""

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history_golden  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


@pytest.fixture(scope="module")
def snapshot():
    return history_golden.current_snapshot()


def test_history_equations_match_the_golden(snapshot):
    expected = json.loads(history_golden.BASELINE_PATH.read_text(encoding="utf-8"))
    drift = history_golden.diff(expected, snapshot)
    assert not drift, "history golden drifted (re-bless only if intended):\n" + "\n".join(drift)


def test_the_pinned_clock_excludes_the_out_of_window_commit(snapshot):
    """engine/core.py has 7 commits; one is dated > 1 year before the pinned now."""
    assert snapshot["engine/core.py"]["Architectural Profile / Raw Churn Frequency"] == 6.0


def test_history_fields_are_not_ablated(snapshot):
    """The point of this fixture: these are constant in the crucible golden."""
    entropies = {v["Architectural Profile / Ownership Entropy"] for v in snapshot.values()}
    assert len(entropies) > 1
    assert any(v["Vulnerability & Risk Exposures / Specification Exposure"] != "100.0%" for v in snapshot.values())


def test_since_arg_pins_only_when_set(monkeypatch):
    from gitgalaxy.metrics import chronometer

    monkeypatch.delenv(chronometer.HISTORY_NOW_ENV, raising=False)
    assert chronometer._since_arg() == "--since=1.year"
    monkeypatch.setenv(chronometer.HISTORY_NOW_ENV, "1000000000")
    assert chronometer._since_arg() == f"--since=@{1000000000 - 365 * 24 * 3600}"
    monkeypatch.setenv(chronometer.HISTORY_NOW_ENV, "not-a-number")
    assert chronometer._since_arg() == "--since=1.year"
