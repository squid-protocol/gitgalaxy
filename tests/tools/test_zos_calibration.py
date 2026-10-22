"""The z/OS-calibrated marker (#4702 Part 2): ledger shape, register page, evidence report."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence_report as er
import register

REC = {
    "date": "2026-11-01",
    "compiler": "Enterprise COBOL 6.4",
    "options": "ZONEDATA(PFD)",
    "probe": "c11-nondigit-1",
    "observed": "not NUMERIC",
    "verdict": "differs",
}


def _ledger(tmp_path, results):
    p = tmp_path / "zos.json"
    p.write_text(json.dumps({"results": results}), encoding="utf-8")
    return p


def test_committed_ledger_is_valid_and_empty():
    assert register.ZOS_LEDGER.exists()
    assert register.zos_calibrated() == set()
    assert register.check() == []


def test_missing_ledger_means_nothing_calibrated(tmp_path):
    assert register.zos_calibrated(tmp_path / "none.json") == set()


def test_only_recorded_ids_are_calibrated(tmp_path):
    p = _ledger(tmp_path, {"C11": [REC], "C2": []})
    assert register.zos_calibrated(p) == {"C11"}
    assert register.zos_problems({"C11", "C2"}, p) == []


def test_ledger_problems(tmp_path):
    bad = dict(REC, verdict="proven")
    missing = {k: v for k, v in REC.items() if k != "probe"}
    p = _ledger(tmp_path, {"C11": [bad, missing], "ZZ9": [REC]})
    problems = register.zos_problems({"C11"}, p)
    assert any("ZZ9 is not a register entry" in x for x in problems)
    assert any("verdict 'proven'" in x for x in problems)
    assert any("lacks probe" in x for x in problems)


def test_page_states_the_count(monkeypatch, tmp_path):
    page = register.render()
    assert "### z/OS calibration" in page
    assert "none: the IBM side stays as the entry states it" in page
    monkeypatch.setattr(register, "ZOS_LEDGER", _ledger(tmp_path, {"C11": [REC]}))
    assert "have a measured z/OS result: C11." in register.render()


def test_report_line_counts_rows():
    rows = [{"id": "C11", "zos_calibrated": True}, {"id": "C2"}]
    assert er.zos_line(rows) == "z/OS-calibrated: 1 of 2 named assumptions"
    assert er.zos_line(rows[1:]) == "z/OS-calibrated: 0 of 1 named assumptions (none measured on z/OS)"
