"""#7486: _same_commarea compares a PIC X COMMAREA field by its bytes, a numeric one by value."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402

PIC_X = {"name": "CA-X", "pic": "X(10)", "usage": "DISPLAY", "offset": 0, "bytes": 10}
PIC_9 = {"name": "CA-N", "pic": "9(10)", "usage": "DISPLAY", "offset": 0, "bytes": 10}


def _x(raw: bytes) -> object:
    return ec.decode_record(raw, [PIC_X], "cp1252", exact=True)["CA-X"]


def test_decode_record_tags_only_alphanumeric():
    assert isinstance(_x(b"0000000001"), ec.AlnumText)
    n = ec.decode_record(b"0000000001", [PIC_9], "cp1252", exact=True)["CA-N"]
    assert not isinstance(n, ec.AlnumText)


def test_pic_x_differing_bytes_are_different():
    assert not ec._same_commarea(_x(b"         1"), _x(b"0000000001"))
    assert not ec._same_commarea(_x(b"         1"), "0000000001")
    assert not ec._same_commarea("1", _x(b"0000000001"))


def test_pic_x_same_bytes_and_trailing_blanks_equal():
    assert ec._same_commarea(_x(b"AB        "), _x(b"AB        "))
    assert ec._same_commarea(_x(b"AB        "), "AB")


def test_low_values_differ_from_spaces():
    assert not ec._same_commarea(_x(b"\x00" * 10), _x(b" " * 10))


def test_numeric_still_by_value():
    assert ec._same_commarea("0000000001", "1")
    assert ec._same_commarea("1.0", "1")


def test_none_unchanged():
    assert ec._same_commarea(None, "")
    assert not ec._same_commarea(_x(b"A         "), None)


def test_compare_events_flags_pic_x_commarea():
    c = [{"event": "COMMAREA", "commarea": {"CA-X": _x(b"         1")}}]
    j = [{"event": "COMMAREA", "commarea": {"CA-X": "0000000001"}}]
    assert ec.compare_events(c, j)["diffs"]
