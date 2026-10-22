"""The test-time ratchet's logic (#5166 part B): 15 s fail / 10 s warn, 2.5x baseline rule, shrink-only update, budget."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import time_ratchet as tr  # noqa: E402


_REAL_REMEASURE = tr.remeasure


@pytest.fixture(autouse=True)
def _no_real_rerun(monkeypatch):
    """check re-runs an over-limit test (#5955); a fake nodeid must not start pytest."""
    monkeypatch.setattr(tr, "remeasure", lambda nodeid: None)


def test_an_unmarked_test_fails_only_over_fifteen_seconds():
    assert tr.check_tests({"a": 15.0}, {}) == []
    assert len(tr.check_tests({"a": 15.01}, {})) == 1


def test_a_test_between_ten_and_fifteen_seconds_is_a_warning_not_a_failure():
    assert tr.check_tests({"a": 14.9}, {}) == []
    assert tr.tests_over_threshold({"a": 10.0, "b": 10.01, "c": 14.9}, {}) == [("c", 14.9), ("b", 10.01)]


def test_a_slow_marker_or_a_baseline_entry_excuses_it():
    assert tr.check_tests({"a": 50.0}, {}, {"a": "scans 40 repos"}) == []
    assert tr.check_tests({"a": 50.0}, {"a": 40.0}) == []
    assert tr.tests_over_threshold({"a": 50.0, "b": 50.0}, {"a": 40.0}, {"b": "why"}) == []


def test_a_baselined_test_fails_past_two_and_a_half_times_its_time():
    assert tr.check_tests({"a": 100.0}, {"a": 40.0}) == []
    assert len(tr.check_tests({"a": 100.1}, {"a": 40.0})) == 1


def test_a_baselined_test_the_run_did_not_execute_is_ignored():
    assert tr.check_tests({"b": 1.0}, {"a": 40.0}) == []


def test_slow_marker_does_not_lift_the_two_x_rule_on_a_baselined_test():
    assert len(tr.check_tests({"a": 101.0}, {"a": 40.0}, {"a": "why"})) == 1


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


def test_check_writes_warnings_to_the_job_summary_and_passes(tmp_path, monkeypatch, capsys):
    _baseline(tmp_path, monkeypatch, {}, 100.0)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert tr.main(["check", "--times", _times(tmp_path, {"warned": 12.0, "fast": 1.0})]) == 0
    assert "WARN warned" in capsys.readouterr().out
    assert "`warned`: 12.0s" in summary.read_text()


def test_over_lists_the_tests_over_ten_seconds_and_fails_only_when_enforced(tmp_path, monkeypatch, capsys):
    _baseline(tmp_path, monkeypatch, {}, 100.0)
    times = _times(tmp_path, {"slowish": 12.0, "fast": 1.0})
    assert tr.main(["over", "--times", times]) == 0
    assert "slowish" in capsys.readouterr().out
    assert tr.main(["over", "--times", times, "--enforce"]) == 1
    assert tr.main(["over", "--times", _times(tmp_path, {"fast": 1.0}, name="f.json"), "--enforce"]) == 0


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


def test_slow_marks_are_read_from_the_test_source_for_the_committed_durations(tmp_path):
    (tmp_path / "t_a.py").write_text(
        "import pytest\n"
        "@pytest.mark.slow(reason='r')\n"
        "def test_marked(): pass\n"
        "def test_plain(): pass\n"
        "@pytest.mark.slow(reason='r')\n"
        "class TestK:\n"
        "    def test_in(self): pass\n",
        encoding="utf-8",
    )
    (tmp_path / "t_m.py").write_text(
        "import pytest\npytestmark = pytest.mark.slow(reason='r')\ndef test_x(): pass\n", encoding="utf-8"
    )
    ids = [
        "t_a.py::test_marked[p1]",
        "t_a.py::test_plain",
        "t_a.py::TestK::test_in",
        "t_m.py::test_x",
        "gone.py::test_y",
    ]
    assert sorted(tr.slow_marks_from_source(ids, tmp_path)) == [
        "t_a.py::TestK::test_in",
        "t_a.py::test_marked[p1]",
        "t_m.py::test_x",
    ]


def _confirm(seconds, again, baseline=None, slow=None):
    return tr.confirm_over_limit(seconds, baseline or {}, slow or {}, measure=lambda n: again[n])


def test_over_then_under_passes_with_a_note():
    failures, notes = _confirm({"a": 20.0}, {"a": 4.0})
    assert failures == []
    assert len(notes) == 1 and "a: 20.0s" in notes[0] and "4.0s" in notes[0]


def test_over_then_over_fails_on_the_remeasured_time():
    failures, notes = _confirm({"a": 20.0}, {"a": 16.0})
    assert notes == [] and len(failures) == 1 and "16.0s" in failures[0]


def test_a_baselined_test_is_remeasured_against_its_two_and_a_half_x_limit():
    assert _confirm({"a": 120.0}, {"a": 90.0}, {"a": 40.0})[0] == []
    assert len(_confirm({"a": 120.0}, {"a": 101.0}, {"a": 40.0})[0]) == 1


def test_tests_under_the_limit_or_excused_are_never_remeasured():
    def boom(nodeid):
        raise AssertionError(f"re-ran {nodeid}")

    seconds = {"fast": 14.9, "marked": 50.0, "baselined": 80.0}
    assert tr.confirm_over_limit(seconds, {"baselined": 40.0}, {"marked": "why"}, measure=boom) == ([], [])


def test_a_test_that_cannot_be_retimed_keeps_its_failure():
    failures, notes = tr.confirm_over_limit({"a": 20.0}, {}, {}, measure=lambda n: None)
    assert notes == [] and len(failures) == 1 and "20.0s" in failures[0]


def test_each_over_limit_test_is_judged_on_its_own_remeasure():
    failures, notes = _confirm({"a": 20.0, "b": 30.0, "c": 1.0}, {"a": 2.0, "b": 30.0})
    assert [f.split(":")[0] for f in failures] == ["b"] and len(notes) == 1


def test_check_passes_when_the_remeasure_is_under_and_fails_when_it_is_over(tmp_path, monkeypatch):
    _baseline(tmp_path, monkeypatch, {}, 100.0)
    times = _times(tmp_path, {"a": 30.0})
    monkeypatch.setattr(tr, "remeasure", lambda nodeid: 3.0)
    assert tr.main(["check", "--times", times]) == 0
    monkeypatch.setattr(tr, "remeasure", lambda nodeid: 31.0)
    assert tr.main(["check", "--times", times]) == 1


def test_no_remeasure_keeps_the_single_timing_verdict(tmp_path, monkeypatch):
    _baseline(tmp_path, monkeypatch, {}, 100.0)
    monkeypatch.setattr(tr, "remeasure", lambda nodeid: 3.0)
    assert tr.main(["check", "--no-remeasure", "--times", _times(tmp_path, {"a": 30.0})]) == 1


def test_remeasure_times_one_real_test():
    nodeid = "tests/tools/test_time_ratchet.py::test_budget_delta_and_shrink"
    seconds = _REAL_REMEASURE(nodeid)
    assert seconds is not None and 0 <= seconds < 30
    assert _REAL_REMEASURE("tests/tools/test_time_ratchet.py::no_such_test") is None
