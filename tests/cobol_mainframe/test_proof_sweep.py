"""proof_sweep.py: a sweep is as expected when every case is proven but the ones not proven on purpose."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import proof_sweep as ps  # noqa: E402


def test_unexpected_failures_and_stale_entries_are_named():
    ok = {"proved": True, "coverage": "proven on 3 scenarios"}
    bad = {"proved": False, "coverage": "not proven; 3 scenarios"}
    results = {"det": {"a": ok, "carddemo-cardupdate": bad, "b": bad}, "model": {"carddemo-cardupdate": ok}}
    problems = ps.verdict(results)
    assert problems == ["det b: NOT PROVEN (not proven; 3 scenarios)"]  # cardupdate is a known det non-proof
    results["det"]["carddemo-cardupdate"] = ok
    assert "det carddemo-cardupdate: now proven -- remove it from KNOWN_UNPROVEN" in ps.verdict(results)


def test_every_known_entry_names_a_case_and_a_reason():
    for (sweep, case), why in ps.KNOWN_UNPROVEN.items():
        assert sweep in ("det", "model") and (ps.CASES / case / "case.json").is_file() and len(why) > 20
