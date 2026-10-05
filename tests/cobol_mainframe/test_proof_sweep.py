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
    assert len(problems) == 1 and problems[0].startswith(
        "det b: NOT PROVEN (not proven; 3 scenarios)"
    )  # cardupdate is a known det non-proof
    results["det"]["carddemo-cardupdate"] = ok
    assert ps.verdict(results)[-1].startswith("det carddemo-cardupdate: now proven -- update the baseline")


def test_every_known_entry_names_a_case_and_a_reason():
    for (sweep, case), why in ps.KNOWN_UNPROVEN.items():
        assert sweep in ("det", "model") and (ps.CASES / case / "case.json").is_file() and len(why) > 20


def test_skip_db2_leaves_out_exactly_the_db2_cases():
    """#4463: CI's det-sweep workflow runs without IBM's Db2 container (--skip-db2)."""
    assert ps.is_db2("genapp-lgupdb01") and not ps.is_db2("carddemo-menu")


def test_baseline_is_a_two_way_ratchet():
    """#4463: a det port not proven because of #4465's facade stubs is baselined; a new failure and a stale entry both fail."""
    ok = {"proved": True, "coverage": "proven on 3 scenarios"}
    bad = {"proved": False, "coverage": "NOT PROVEN (proven on 3 scenarios)"}
    base = {("det", "carddemo-menu"): "facade stub (#4465)"}
    assert ps.verdict({"det": {"carddemo-menu": bad, "a": ok}}, base) == []
    new = ps.verdict({"det": {"carddemo-menu": bad, "b": bad}}, base)
    assert len(new) == 1 and new[0].startswith("det b: NOT PROVEN") and "det_sweep_baseline.json" in new[0]
    stale = ps.verdict({"det": {"carddemo-menu": ok}}, base)
    assert len(stale) == 1 and "now proven" in stale[0] and "--update-baseline" in stale[0]


def test_update_baseline_only_drops_entries_that_now_prove(tmp_path):
    path = tmp_path / "b.json"
    path.write_text('{"det": {"x": {"issue": "#1", "why": "w"}, "y": {"issue": null, "why": "w"}}}')
    ok, bad = {"proved": True, "coverage": ""}, {"proved": False, "coverage": ""}
    assert ps.prune_baseline({"det": {"x": ok, "y": bad, "z": ok}}, path) == ["det x"]
    assert list(ps.load_baseline(path)) == [("det", "y")]
