"""#7434: the stub's READ / REWRITE / UNLOCK lines are events of the COBOL side as CicsTask records them, so a port
that records them (HCUNLK, #7569) pairs event for event."""

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec
import equivalence_cics_filecontrol as fc

REC = b"K002BRAVO   0020"
HEX = REC.hex().upper()


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def test_the_verbs_are_the_three_events():
    assert fc.FILE_EVENT_VERBS == {"READ", "REWRITE", "UNLOCK"}


@pytest.mark.parametrize(
    ("verb", "kv", "data", "want"),
    [
        (
            "READ",
            {"file": "HCUF", "resp": "0", "upd": "1", "len": "16"},
            REC,
            {"event": "READ", "file": "HCUF", "resp": "NORMAL", "update": True, "length": 16, "data": HEX},
        ),
        (
            "READ",
            {"file": "HCUF", "resp": "22", "len": "16", "resp2": "11"},
            b"",
            {"event": "READ", "file": "HCUF", "resp": "LENGERR", "length": 16, "resp2": 11},
        ),
        (
            "READ",
            {"file": "HCUF", "resp": "13", "resp2": "80"},
            b"",
            {"event": "READ", "file": "HCUF", "resp": "NOTFND", "resp2": 80},
        ),
        (
            "REWRITE",
            {"file": "HCUF", "resp": "0"},
            REC,
            {"event": "REWRITE", "file": "HCUF", "resp": "NORMAL", "data": HEX},
        ),
        (
            "REWRITE",
            {"file": "HCUF", "resp": "16", "resp2": "30"},
            REC,
            {"event": "REWRITE", "file": "HCUF", "resp": "INVREQ", "resp2": 30, "data": HEX},
        ),
        ("UNLOCK", {"file": "HCUF", "resp": "0"}, b"", {"event": "UNLOCK", "file": "HCUF", "resp": "NORMAL"}),
        (
            "UNLOCK",
            {"file": "NOFILE", "resp": str(ec.DFHRESP["FILENOTFOUND"]), "resp2": "1"},
            b"",
            {"event": "UNLOCK", "file": "NOFILE", "resp": "DSIDERR", "resp2": 1},
        ),
    ],
)
def test_the_stub_line_is_the_event_and_the_java_event_normalizes_to_it(verb, kv, data, want):
    assert fc.cobol_file_event(verb, kv, data) == want
    java = {k: v for k, v in want.items() if k != "data"}
    if data:
        java["data"] = _b64(data)
    assert fc.java_file_event_as_compared(java) == want
    assert ec.compare_events([want], [fc.java_file_event_as_compared(java)])["diffs"] == []


def test_every_verb_projects_in_the_order_the_stub_logged_it():
    res = {
        "events": ["READ file=HCUF", "UNLOCK file=HCUF", "REWRITE file=HCUF"],
        "screens": [],
        "text": [],
        "fileevents": [fc.cobol_file_event(v, {"file": "HCUF"}, b"") for v in ("READ", "UNLOCK", "REWRITE")],
    }
    assert [e["event"] for e in ec.cobol_events(res)] == ["READ", "UNLOCK", "REWRITE"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("resp2", 99), ("length", 8), ("data", "00"), ("update", None), ("file", "OTHER"), ("resp", "INVREQ")],
)
def test_a_difference_in_any_compared_field_is_a_diff(field, value):
    c = fc.cobol_file_event("READ", {"file": "HCUF", "resp": "0", "upd": "1", "len": "16"}, REC)
    j = {**c, field: value}
    assert [d["fields"][0]["field"] for d in ec.compare_events([c], [j])["diffs"]] == [field]


def test_a_verb_the_port_records_none_of_is_not_paired():
    """genapp-lgicvs01's GTEQ READ is not an event on the Java side yet: the stub's READ must not shift the rest."""
    read = fc.cobol_file_event("READ", {"file": "HCUF"}, REC)
    send = {"event": "SEND-TEXT", "text": "X"}
    assert ec.compare_events([read, send], [send])["diffs"] == []


def test_a_verb_the_port_records_is_compared_in_full():
    unlock = fc.cobol_file_event("UNLOCK", {"file": "HCUF"}, b"")
    assert ec.compare_events([unlock, unlock], [unlock])["diffs"]
    assert ec.compare_events([unlock], [unlock, unlock])["diffs"]
