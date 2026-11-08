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
    known = {
        ("det", "carddemo-cardupdate"): "a known det non-proof"
    }  # explicit: the live baseline shrinks as ports are fixed
    problems = ps.verdict(results, known)
    assert len(problems) == 1 and problems[0].startswith(
        "det b: NOT PROVEN (not proven; 3 scenarios)"
    )  # cardupdate is a known det non-proof
    results["det"]["carddemo-cardupdate"] = ok
    assert ps.verdict(results, known)[-1].startswith("det carddemo-cardupdate: now proven -- update the baseline")


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
    monkeypatch.setattr(ledger, "check", lambda det, led, **kw: calls.append(1) or (["ledger problem"], []))
    monkeypatch.setattr(ps, "verdict", lambda results, base: [])
    results = {"det": {}}
    ns = dict(aggregate=[Path(".")], no_ratchet=False, update_baseline=False)
    assert ps.report(results, [], argparse.Namespace(**ns, skip_ledger_check=False)) == 1 and calls
    calls.clear()
    assert ps.report(results, [], argparse.Namespace(**ns, skip_ledger_check=True)) == 0 and not calls


def test_the_ledger_is_re_recorded_not_failed_on_stale_fingerprints(monkeypatch, capsys):
    """#5084: a harness PR leaves every entry stale on harness / oracle. the sweep must not fail on that by default; it re-records
    the entries it re-checked when asked (--record-ledger), and fails on stale ones only when asked (--strict-ledger)."""
    import argparse

    import det_coverage_ledger as ledger

    seen, written = [], []
    monkeypatch.setattr(ledger, "load", lambda **kw: {})
    monkeypatch.setattr(ledger, "check", lambda det, led, recheck=False: seen.append(recheck) or ([], []))
    monkeypatch.setattr(ledger, "build", lambda det, led: {"c": {}})
    monkeypatch.setattr(ledger, "write", lambda cases: written.append(cases) or ["c"])
    monkeypatch.setattr(ps, "verdict", lambda results, base: [])
    ns = dict(aggregate=[Path(".")], no_ratchet=False, update_baseline=False, skip_ledger_check=False)
    assert ps.report({"det": {}}, [], argparse.Namespace(**ns)) == 0 and seen == [False] and not written
    args = argparse.Namespace(**ns, strict_ledger=True, record_ledger=True)
    assert ps.report({"det": {}}, [], args) == 0 and seen == [False, True] and written == [{"c": {}}]
    assert "1 entry re-recorded" in capsys.readouterr().out


def test_durations_are_recorded_from_the_proven_seconds(tmp_path):
    """The nightly aggregate's durations (#4847): a case's seconds merge into the file; cases not swept keep theirs."""
    path = tmp_path / "durations.json"
    path.write_text('{"format": "det-sweep-durations/1", "det": {"keep": 7, "old": 5}}', encoding="utf-8")
    ps.write_durations({"old": {"seconds": 12.4}, "zero": {"seconds": 0}, "new": {"seconds": 30.6}}, path)
    assert ps.load_durations(path) == {"keep": 7.0, "old": 12.0, "new": 31.0}


def test_a_translate_error_is_named_in_the_verdict():
    """#8093: a case that died while translating said only "no coverage line"; the error must reach the CI log."""
    bad = {"proved": False, "coverage": "", "error": "ImportError: the translator needs a grammar"}
    (problem,) = ps.verdict({"det": {"x": bad}}, {})
    assert "no coverage line" in problem and "translate error: ImportError: the translator needs a grammar" in problem
    (plain,) = ps.verdict({"det": {"x": {"proved": False, "coverage": ""}}}, {})
    assert "translate error" not in plain  # the key is only read when present


def test_det_sweep_keeps_the_translate_error(tmp_path, monkeypatch):
    """#8093: det_port.py's summary row `error` is carried into the sweep result (capped), and only when set."""
    import json

    rows = [
        {"case": "a", "error": "ValueError: " + "x" * 2000, "statements": None},
        {"case": "b", "statements": 3, "translated_statements": 3, "proved": True},
    ]

    def fake_run(argv, **_kw):
        (tmp_path / "summary.json").write_text(json.dumps(rows), encoding="utf-8")

    monkeypatch.setattr(ps, "det_cases", lambda _skip: ["a", "b"])
    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    out = ps.det_sweep(tmp_path, 1, "all")
    assert out["a"]["error"].startswith("ValueError: ") and len(out["a"]["error"]) == ps.ERROR_CHARS
    assert "error" not in out["b"]


def _summary(tmp_path, rows):
    import json

    (tmp_path / "summary.json").write_text(json.dumps(rows), encoding="utf-8")


def test_only_a_slow_translate_error_is_a_retry_candidate(tmp_path):
    """#8096: a fast error is a translator bug and never retried; a slow one is the CI box."""
    _summary(tmp_path, [
        {"case": "slow", "error": "X: y", "translate_seconds": 62.0},
        {"case": "fast", "error": "X: y", "translate_seconds": 1.2},
        {"case": "ok", "translate_seconds": 90.0},
    ])  # fmt: skip
    assert ps.translate_failures(tmp_path) == ["slow"]
    assert ps.translate_failures(tmp_path / "none") == []


def test_retry_replaces_only_a_proof_and_a_second_failure_stands(tmp_path, monkeypatch):
    _summary(tmp_path, [{"case": c, "error": "X: y", "translate_seconds": 61.0} for c in ("a", "b")])
    bad = {"proved": False, "coverage": ""}
    results = {"a": dict(bad), "b": dict(bad)}
    calls = []

    def fake(work, jobs, faults, skip_db2=False, only=None):
        calls.append((work, only))
        return {"a": {"proved": True, "coverage": "proven on 1 scenario"}, "b": dict(bad)}

    monkeypatch.setattr(ps, "det_sweep", fake)
    assert ps.retry_slow_translations(results, tmp_path, 1, "all") == ["a"]
    assert calls == [(tmp_path / "retry", ["a", "b"])]
    assert results["a"]["proved"] and results["a"]["retried"] and results["b"] == bad
    assert ps.verdict({"det": {"b": results["b"]}}, {})  # still a failure
