"""#7954: the COMMAREA a LINK passes (its LENGTH and bytes) is compared when both sides give the bytes, so a port that
marshals one field wrong before LINK ABNDPROC (the CRDTAGY4 survivors) is a difference, not a pass."""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _link(program="ABNDPROC", area=b"A" * 8, length=None):
    ev = {"event": "LINK", "program": program}
    if area is not None:
        ev["area"] = _b64(area)
        ev["length"] = len(area) if length is None else length
    return ev


def _fields(out):
    return [b["field"] for d in out["diffs"] for b in d.get("fields", [])]


def test_equal_areas_are_no_difference():
    assert ec.compare_events([_link()], [_link()])["diffs"] == []


def test_one_differing_byte_is_a_difference():
    out = ec.compare_events([_link()], [_link(area=b"A" * 7 + b"B")])
    assert _fields(out) == ["area"]


def test_a_different_length_is_a_difference():
    assert "length" in _fields(ec.compare_events([_link()], [_link(length=9)]))


def test_a_side_without_the_bytes_claims_nothing():
    assert ec.compare_events([_link()], [_link(area=None)])["diffs"] == []
    assert ec.compare_events([_link(area=None)], [_link()])["diffs"] == []


def test_the_target_is_still_compared():
    assert _fields(ec.compare_events([_link()], [_link("OTHERPGM")])) == ["program"]


def test_links_are_paired_in_order():
    cobol = [_link(area=b"1" * 4), _link(area=b"2" * 4)]
    assert ec.compare_events(cobol, [_link(area=b"1" * 4), _link(area=b"2" * 4)])["diffs"] == []
    assert _fields(ec.compare_events(cobol, [_link(area=b"2" * 4), _link(area=b"1" * 4)])) == ["area", "area"]


def test_the_java_link_event_keeps_its_bytes_and_drops_the_dto_snapshot():
    java = {"event": "LINK", "target": "ABNDPROC", "length": 4, "commarea": {"x": 1}, "resp": "NORMAL",
            "area": _b64(b"abcd")}  # fmt: skip
    assert ec._link_as_compared(java) == {"event": "LINK", "program": "ABNDPROC", "length": 4, "area": _b64(b"abcd")}
    del java["area"]
    assert ec._link_as_compared(java) == {"event": "LINK", "program": "ABNDPROC"}


def test_the_cobol_side_records_length_and_bytes_in_stub_order():
    res = {"screens": [], "text": [], "events": ["LINK pgm=P target=ABNDPROC len=4 area=1 resp=0 resp2=0",
                                                  "LINK pgm=P target=OTHER len=2 area=1 resp=0 resp2=0"],
           "links": [{"target": "ABNDPROC", "data": b"abcd"}, {"target": "OTHER", "data": b"zz"}]}  # fmt: skip
    ev = ec.cobol_events(res)
    assert [(e["program"], e["length"], e["area"]) for e in ev] == [
        ("ABNDPROC", 4, _b64(b"abcd")),
        ("OTHER", 2, _b64(b"zz")),
    ]


def test_a_link_with_no_area_keeps_only_its_target():
    res = {"screens": [], "text": [], "events": ["LINK pgm=P target=ABNDPROC len=0 area=0 resp=0 resp2=0"], "links": []}
    assert ec.cobol_events(res) == [{"event": "LINK", "program": "ABNDPROC"}]


def test_a_db2_timestamp_and_a_buffer_past_the_cobol_area_are_no_difference():
    """GenApp's LGAPDB01 / LGUPDB01 pass CURRENT TIMESTAMP (the legs run seconds apart) and the port's buffer is larger."""
    cobol = b"ID01" + b"2026-11-24-09.04.49.531614" + b"TAIL"
    java = b"ID01" + b"2026-11-24-09.05.08.123984" + b"TAIL" + b"\x00" * 64
    assert ec.compare_events([_link(area=cobol)], [_link(area=java, length=len(cobol))])["diffs"] == []
    other = b"ID02" + b"2026-11-24-09.05.08.123984" + b"TAIL"
    assert _fields(ec.compare_events([_link(area=cobol)], [_link(area=other)])) == ["area"]


def test_bytes_the_cobol_program_never_wrote_are_not_compared():
    """The stub's untouched storage is NUL where a port's DTO default is a space (CBSA BNK1CAC's trailing group)."""
    cobol = b"ABCD" + b"\x00" * 4
    assert ec.compare_events([_link(area=cobol)], [_link(area=b"ABCD" + b" " * 4)])["diffs"] == []
    assert _fields(ec.compare_events([_link(area=cobol)], [_link(area=b"ABXD    ")])) == ["area"]


def test_a_signed_zoned_last_digit_spelt_as_an_overpunch_is_the_same_byte():
    assert ec.compare_events([_link(area=b"00000")], [_link(area=b"0000{")])["diffs"] == []
    assert ec.compare_events([_link(area=b"00005")], [_link(area=b"0000E")])["diffs"] == []
    assert _fields(ec.compare_events([_link(area=b"00005")], [_link(area=b"0000F")])) == ["area"]


def test_a_port_passing_its_whole_buffer_states_no_length_but_a_near_miss_does():
    assert ec.compare_events([_link(area=b"A" * 20)], [_link(area=b"A" * 20 + b" " * 7250)])["diffs"] == []
    assert _fields(ec.compare_events([_link(area=b"A" * 20)], [_link(area=b"A" * 20 + b" ")])) == ["length"]


def test_a_short_port_area_differs_only_where_cobol_wrote_the_missing_bytes():
    assert ec.compare_events([_link(area=b"AB\x00\x00")], [_link(area=b"AB", length=4)])["diffs"] == []
    assert _fields(ec.compare_events([_link(area=b"ABCD")], [_link(area=b"AB", length=4)])) == ["area"]
