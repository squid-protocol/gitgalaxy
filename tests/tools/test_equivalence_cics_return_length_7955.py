"""#7955: a RETURN's LENGTH (the next task's EIBCALEN) is compared when both sides record it, so a port that returns a
COMMAREA of another length is a difference. A side with no length (a plain RETURN, an older port) is not compared."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec


def _ret(length, commarea="S"):
    ev = {"event": "RETURN", "transid": "HX01", "commarea": {"WS-CA": commarea}}
    if length is not None:
        ev["length"] = length
    return ev


def _fields(out):
    return [b["field"] for d in out["diffs"] for b in d.get("fields", [])]


@pytest.mark.parametrize("cobol, java", [(1, 1), (1, None), (None, 2), (None, None), (4, 4)])
def test_equal_or_absent_lengths_are_no_difference(cobol, java):
    assert ec.compare_events([_ret(cobol)], [_ret(java)])["diffs"] == []


@pytest.mark.parametrize("cobol, java", [(1, 2), (2, 1), (0, 1), (1, "2")])
def test_a_different_length_is_a_difference(cobol, java):
    out = ec.compare_events([_ret(cobol)], [_ret(java)])
    assert _fields(out) == ["length"]


def test_the_stub_len_is_read_into_the_cobol_event():
    res = {
        "events": ["RETURN level=1 transid=HX01 len=3"],
        "screens": [],
        "text": [],
        "return": {"transid": "HX01", "commarea": {"WS-CA": "S"}},
    }
    assert ec.cobol_events(res) == [_ret(3)]


def test_a_return_with_no_commarea_records_no_length():
    res = {"events": ["RETURN level=1 transid= len=0"], "screens": [], "text": [], "return": {"transid": "", "commarea": None}}
    assert "length" not in ec.cobol_events(res)[0]
