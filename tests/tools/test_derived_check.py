"""derived_check (#6731): which ledger entries a branch stales or lacks, and the refresh commands it prints.
Fingerprints, Db2-ness and the baseline are stubbed; no sweep, git or corpus needed."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derived_check as dc

FP = {"case": "a", "corpus": "b", "harness": "c", "oracle": "d"}


@pytest.fixture
def tree(monkeypatch):
    """Cases plain, db2 (Db2) and unproven (in the baseline); `now` is the tree's fingerprints per case."""
    now = {c: dict(FP) for c in ("plain", "db2", "unproven", "new")}
    monkeypatch.setattr(dc.dcl, "fingerprints", lambda case: now[case])
    monkeypatch.setattr(dc.ps, "is_db2", lambda case: case == "db2")
    monkeypatch.setattr(dc.ps, "KNOWN_UNPROVEN", {("det", "unproven"): "why"})
    return now


def entry():
    return {"inputs": dict(FP)}


def test_current_ledger_has_no_gaps(tree):
    assert dc.ledger_gaps(["plain", "db2", "unproven"], {"plain": entry(), "db2": entry()}) == ([], [])


@pytest.mark.parametrize("name", ["case", "corpus"])
def test_a_blocking_input_change_is_stale(tree, name):
    tree["plain"][name] = "moved"
    assert dc.ledger_gaps(["plain"], {"plain": entry()}) == ([("plain", [name])], [])


@pytest.mark.parametrize("name", ["harness", "oracle"])
def test_a_harness_or_oracle_change_is_left_to_the_scheduled_refresh(tree, name):
    tree["plain"][name] = "moved"
    assert dc.ledger_gaps(["plain"], {"plain": entry()}) == ([], [])


def test_db2_cases_are_skipped_like_the_pr_det_sweep(tree):
    tree["db2"]["case"] = "moved"
    assert dc.ledger_gaps(["db2"], {"db2": entry()}) == ([], [])
    assert dc.ledger_gaps(["db2"], {}) == ([], [])


def test_a_new_case_needs_an_entry_unless_listed_unproven(tree):
    assert dc.ledger_gaps(["new", "unproven"], {}) == ([], ["new"])


def test_report_names_each_record_and_one_resweep_command():
    lines = dc.report([("carddemo-x", ["port"])], [("plain", ["case"])], ["new"])
    assert lines[0].endswith("python tests/tools/evidence.py prove carddemo-x")
    assert "plain: stale (case changed)" in lines[1]
    assert "new: no entry" in lines[2]
    assert "--cases plain,new --work DIR" in lines[3] and "det_coverage_ledger.py update DIR" in lines[3]


def test_report_is_empty_when_nothing_is_stale():
    assert dc.report([], [], []) == []
