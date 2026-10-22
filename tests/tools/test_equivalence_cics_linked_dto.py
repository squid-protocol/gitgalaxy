"""#5863: a LINKed port that took the link-area bytes is compared on the DTO it gave back as well (`dto` on its COMMAREA
event), so a dropped or misplaced fill_ write-back is a difference, not hidden behind the bytes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec


def _fields(diffs):
    return [b["field"] for d in diffs for b in d.get("fields", [])]


def _compare(java_commarea, dto):
    cobol = [{"event": "COMMAREA", "commarea": {"COMPANY-NAME": "CICS Bank"}}]
    java = [{"event": "COMMAREA", "commarea": java_commarea, "dto": dto}]
    return ec.compare_events(cobol, java)


def test_a_dto_that_matches_the_bytes_is_equal():
    out = _compare({"COMPANY-NAME": "CICS Bank"}, {"COMPANY-NAME": "CICS Bank      "})
    assert out["diffs"] == [] and out["equal"] == 1


def test_a_dto_that_differs_from_the_cobol_commarea_is_a_difference_though_the_bytes_agree():
    out = _compare({"COMPANY-NAME": "CICS Bank"}, {"COMPANY-NAME": "XXXX Bank"})
    assert _fields(out["diffs"]) == ["commarea.dto.COMPANY-NAME"]


def test_a_dto_without_the_field_is_not_compared_for_it():
    out = _compare({"COMPANY-NAME": "CICS Bank"}, {"OTHER": "x"})
    assert out["diffs"] == []


def test_no_dto_is_the_old_comparison():
    out = _compare({"COMPANY-NAME": "CICS Bank"}, None)
    assert out["diffs"] == []
