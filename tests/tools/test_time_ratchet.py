"""The test-time ratchet's logic (#5166 part B): 10 s gate, 2x baseline rule, shrink-only update, suite budget."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import time_ratchet as tr  # noqa: E402


def test_a_test_over_ten_seconds_fails_at_the_boundary_only():
    assert tr.check_tests({"a": 10.0}, {}) == []
    assert len(tr.check_tests({"a": 10.01}, {})) == 1


def test_a_slow_marker_or_a_baseline_entry_excuses_it():
    assert tr.check_tests({"a": 50.0}, {}, {"a": "scans 40 repos"}) == []
    assert tr.check_tests({"a": 50.0}, {"a": 40.0}) == []


def test_a_baselined_test_fails_past_twice_its_time():
    assert tr.check_tests({"a": 80.0}, {"a": 40.0}) == []
    assert len(tr.check_tests({"a": 80.1}, {"a": 40.0})) == 1


def test_a_baselined_test_the_run_did_not_execute_is_ignored():
    assert tr.check_tests({"b": 1.0}, {"a": 40.0}) == []


def test_slow_marker_does_not_lift_the_two_x_rule_on_a_baselined_test():
    assert len(tr.check_tests({"a": 90.0}, {"a": 40.0}, {"a": "why"})) == 1


def test_update_only_lowers_and_never_adds_or_raises():
    base = {"a": 40.0, "b": 20.0, "c": 15.0}
    new = tr.shrink_tests(base, {"a": 30.0, "b": 99.0, "c": 9.0, "d": 500.0})
    assert new == {"a": 30.0, "b": 20.0}


def test_budget_delta_and_shrink():
    assert tr.budget_delta(110.0, 100.0) == pytest.approx(0.10)
    assert tr.shrink_budget(100.0, 90.0) == 90.0
    assert tr.shrink_budget(100.0, 130.0) == 100.0


def _times(tmp_path, seconds, slow=None, name="t.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"seconds": seconds, "slow": slow or {}}))
    return str(p)


def _baseline(tmp_path, monkeypatch, tests, budget):
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps({"suite_budget_s": budget, "tests": tests}))
    monkeypatch.setattr(tr, "BASELINE", p)
    return p


def test_budget_is_report_only_unless_enforced(tmp_path, monkeypatch):
    _baseline(tmp_path, monkeypatch, {}, 100.0)
    over = _times(tmp_path, {"a": 111.0})
    assert tr.main(["budget", "--times", over]) == 0
    assert tr.main(["budget", "--times", over, "--enforce"]) == 1
    assert tr.main(["budget", "--times", _times(tmp_path, {"a": 110.0}, name="u.json"), "--enforce"]) == 0


def test_budget_sums_the_parts_and_refuses_nothing(tmp_path, monkeypatch):
    _baseline(tmp_path, monkeypatch, {}, 100.0)
    parts = [_times(tmp_path, {"a": 60.0}, name="1.json"), _times(tmp_path, {"b": 60.0}, name="2.json")]
    assert tr.main(["budget", "--times", *parts, "--enforce"]) == 1
    assert tr.main(["budget", "--times", _times(tmp_path, {}, name="e.json")]) == 2


def test_check_reads_slow_reasons_from_the_times_file(tmp_path, monkeypatch):
    _baseline(tmp_path, monkeypatch, {}, 100.0)
    assert tr.main(["check", "--times", _times(tmp_path, {"a": 30.0})]) == 1
    assert tr.main(["check", "--times", _times(tmp_path, {"a": 30.0}, {"a": "why"}, "s.json")]) == 0


def test_update_command_writes_a_shrunk_baseline(tmp_path, monkeypatch):
    p = _baseline(tmp_path, monkeypatch, {"a": 40.0, "b": 20.0}, 100.0)
    assert tr.main(["update", "--times", _times(tmp_path, {"a": 12.0, "b": 5.0, "c": 99.0})]) == 0
    data = json.loads(p.read_text())
    assert data["tests"] == {"a": 12.0} and data["suite_budget_s"] == 100.0


def test_the_committed_baseline_is_well_formed():
    base = tr.load_baseline(Path(__file__).resolve().parents[1] / "test_time_baseline.json")
    assert base["suite_budget_s"] > 0
    assert base["tests"] and all(v > tr.THRESHOLD_S for v in base["tests"].values())


def test_the_evidence_components_file_is_not_in_the_suite_time(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"tests/cobol_mainframe/test_evidence_components.py::t": 99.0, "x": 1.0}))
    assert tr.load_times(p)[0] == {"x": 1.0}
