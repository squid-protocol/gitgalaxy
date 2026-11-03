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


def test_the_verbs_are_the_three_events_and_the_browse():
    assert fc.FILE_EVENT_VERBS == {"READ", "REWRITE", "UNLOCK", "STARTBR", "READNEXT", "READPREV", "ENDBR"}


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


K030 = b"K030"
K030_HEX = K030.hex().upper()
BROWSE = [
    (
        "STARTBR",
        {"file": "HCRS", "rid": K030_HEX, "resp": "0", "mode": "GTEQ"},
        b"",
        {"event": "STARTBR", "file": "HCRS", "resp": "NORMAL", "ridfld": K030_HEX, "mode": "GTEQ"},
    ),
    (
        "STARTBR",
        {"file": "HCRS", "rid": K030_HEX, "resp": "13", "mode": "EQUAL", "resp2": "80"},
        b"",
        {"event": "STARTBR", "file": "HCRS", "resp": "NOTFND", "ridfld": K030_HEX, "mode": "EQUAL", "resp2": 80},
    ),
    (
        "READNEXT",
        {"file": "HCRS", "rid": K030_HEX, "resp": "0", "set": "1"},
        REC,
        {"event": "READNEXT", "file": "HCRS", "resp": "NORMAL", "ridfld": K030_HEX, "set": True, "data": HEX},
    ),
    (
        "READNEXT",
        {"file": "HCRS", "rid": K030_HEX, "resp": "0", "len": "16"},
        REC,
        {"event": "READNEXT", "file": "HCRS", "resp": "NORMAL", "ridfld": K030_HEX, "length": 16, "data": HEX},
    ),
    (
        "READPREV",
        {"file": "HCRS", "rid": K030_HEX, "resp": "20", "resp2": "90"},
        b"",
        {"event": "READPREV", "file": "HCRS", "resp": "ENDFILE", "ridfld": K030_HEX, "resp2": 90},
    ),
    ("ENDBR", {"file": "HCRS", "resp": "0"}, b"", {"event": "ENDBR", "file": "HCRS", "resp": "NORMAL"}),
    (
        "ENDBR",
        {"file": "HCRS", "resp": "16", "resp2": "35"},
        b"",
        {"event": "ENDBR", "file": "HCRS", "resp": "INVREQ", "resp2": 35},
    ),
]


@pytest.mark.parametrize(("verb", "kv", "data", "want"), BROWSE, ids=[f"{b[0]}-{i}" for i, b in enumerate(BROWSE)])
def test_a_browse_stub_line_is_the_event_and_the_java_event_normalizes_to_it(verb, kv, data, want):
    if verb == "READPREV":  # ENDFILE: the stub names the code number; RESP_NAMES gives the name
        kv = {**kv, "resp": str(ec.DFHRESP["ENDFILE"])}
    if verb == "ENDBR" and "resp2" in kv:
        kv = {**kv, "resp": str(ec.DFHRESP["INVREQ"])}
    if verb == "STARTBR" and kv["resp"] == "13":
        kv = {**kv, "resp": str(ec.DFHRESP["NOTFND"])}
    assert fc.cobol_file_event(verb, kv, data) == want
    java = {k: v for k, v in want.items() if k not in ("data", "ridfld")}
    if "ridfld" in want:  # in the program's page, like data
        java["ridfld"] = _b64(K030)
    if data:
        java["data"] = _b64(data)
    assert fc.java_file_event_as_compared(java) == want
    assert ec.compare_events([want], [fc.java_file_event_as_compared(java)])["diffs"] == []


@pytest.mark.parametrize("field", ["ridfld", "mode", "set"])
def test_a_difference_in_a_browse_field_is_a_diff(field):
    c = fc.cobol_file_event("STARTBR", {"file": "HCRS", "rid": K030_HEX, "resp": "0", "mode": "GTEQ", "set": "1"}, b"")
    j = {**c, field: "00" if field == "ridfld" else "EQUAL" if field == "mode" else None}
    assert [d["fields"][0]["field"] for d in ec.compare_events([c], [j])["diffs"]] == [field]


def test_a_browse_that_skips_a_record_is_a_diff():
    """The reported SET(ADDRESS OF) symptom: F1=K020, F3=K040, F5=ENDFILE -- every other record. The sequence the
    stub logs (K010 K020 ... ) must not pair with a Java sequence that steps over one."""

    def read(key: bytes):
        return fc.cobol_file_event("READNEXT", {"file": "HCRS", "rid": key.hex(), "resp": "0", "set": "1"}, REC)

    stub = [read(k) for k in (b"K010", b"K020", b"K030")]
    skipping = [read(k) for k in (b"K010", b"K030", b"K050")]
    assert ec.compare_events(stub, stub)["diffs"] == []
    assert len(ec.compare_events(stub, skipping)["diffs"]) == 2


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
