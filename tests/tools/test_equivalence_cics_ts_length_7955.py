"""#7955: a WRITEQ TS item's byte length is compared when both sides record it, so a port that writes one trailing
blank more (LENGTH 13 -> 14) is a difference, which the blank-trimmed data compare could not see."""

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec
import equivalence_cics_tempstorage as ts


def _ev(length, data="LOG RECORD"):
    ev = {"event": "WRITEQ-TS", "queue": "PCLOG", "data": data, "resp": "NORMAL", "item": 1}
    if length is not None:
        ev["length"] = length
    return ev


def _fields(out):
    return [b["field"] for d in out["diffs"] for b in d.get("fields", [])]


@pytest.mark.parametrize("cobol, java", [(13, 13), (13, None), (None, 14), (None, None)])
def test_equal_or_absent_lengths_are_no_difference(cobol, java):
    assert ec.compare_events([_ev(cobol)], [_ev(java)])["diffs"] == []


def test_a_longer_item_with_the_same_trimmed_text_is_a_difference():
    assert _fields(ec.compare_events([_ev(13)], [_ev(14)])) == ["length"]


def test_the_cobol_side_records_the_byte_length_of_a_normal_write():
    kv = {"queue": b"PCLOG".hex(), "resp": "0", "item": "1"}
    assert ts.cobol_ts(kv, b"abc  ", "ascii")["length"] == 5
    assert "length" not in ts.cobol_ts({**kv, "resp": "2"}, b"", "ascii")


def test_the_java_side_records_the_raw_byte_length():
    from gitgalaxy.tools.cobol_to_java.det.cics import REGION_PAGE

    raw = "abc ".encode(REGION_PAGE)
    out = ts.java_ts_as_compared(
        {"event": "WRITEQ-TS", "queue": "Q", "resp": "NORMAL", "item": 1, "data": base64.b64encode(raw).decode()}
    )
    assert out["length"] == 4
