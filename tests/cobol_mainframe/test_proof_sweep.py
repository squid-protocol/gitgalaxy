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


def test_db2_only_and_skip_db2_split_the_det_cases():
    """#4733: Evidence Refresh's Db2 job sweeps exactly the cases the det-sweep workflow leaves out."""
    every, plain, db2 = ps.det_cases(), ps.det_cases(skip_db2=True), ps.det_cases(only_db2=True)
    assert db2 and plain
    assert set(plain) | set(db2) == set(every) and not set(plain) & set(db2)
    assert all(ps.is_db2(c) for c in db2) and not any(ps.is_db2(c) for c in plain)


def test_skip_ledger_check_leaves_the_ledger_out_of_the_aggregate_ratchet(monkeypatch, capsys):
    """#4744: Evidence Refresh aggregates its shards BEFORE it rewrites the coverage ledger, so the ledger check (CI's
    det sweep, where the ledger must already hold the coverage) must be skippable; everything else stays."""
    import argparse

    import det_coverage_ledger as ledger

    calls = []
    monkeypatch.setattr(ledger, "check", lambda det, led: calls.append(1) or (["ledger problem"], []))
    monkeypatch.setattr(ps, "verdict", lambda results, base: [])
    results = {"det": {}}
    ns = dict(aggregate=[Path(".")], no_ratchet=False, update_baseline=False)
    assert ps.report(results, [], argparse.Namespace(**ns, skip_ledger_check=False)) == 1 and calls
    calls.clear()
    assert ps.report(results, [], argparse.Namespace(**ns, skip_ledger_check=True)) == 0 and not calls


def test_durations_are_recorded_from_the_proven_seconds(tmp_path):
    """The nightly aggregate's durations (#4847): a case's seconds merge into the file; cases not swept keep theirs."""
    path = tmp_path / "durations.json"
    path.write_text('{"format": "det-sweep-durations/1", "det": {"keep": 7, "old": 5}}', encoding="utf-8")
    ps.write_durations({"old": {"seconds": 12.4}, "zero": {"seconds": 0}, "new": {"seconds": 30.6}}, path)
    assert ps.load_durations(path) == {"keep": 7.0, "old": 12.0, "new": 31.0}
