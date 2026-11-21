"""#5862: a map's MAPSET name is compared, both ways, on RECEIVE MAP and SEND MAP (mutant 74b4bb8c3a of billpay)."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec


def _screen(**extra):
    return {"map": "M", "fields": {}, "subfields": {}, "options": [], "cursor": None, **extra}


def _fields(diffs):
    return [b["field"] for d in diffs for b in d.get("fields", [])]


def test_receive_map_keeps_its_mapset():
    ev = ec.cobol_events({"screens": [], "text": [], "events": ["RECEIVE-MAP map=M mapset=S resp=0"]})
    assert ev == [{"event": "RECEIVE-MAP", "map": "M", "mapset": "S"}]


def test_receive_map_without_a_mapset_states_none():
    ev = ec.cobol_events({"screens": [], "text": [], "events": ["RECEIVE-MAP map=M resp=0"]})
    assert ev == [{"event": "RECEIVE-MAP", "map": "M"}]


def test_send_map_keeps_its_mapset():
    res = {"screens": [_screen(mapset="S")], "text": [], "events": ["SEND-MAP map=M mapset=S"]}
    assert ec.cobol_events(res)[0]["mapset"] == "S"
    res = {"screens": [_screen()], "text": [], "events": ["SEND-MAP map=M"]}
    assert "mapset" not in ec.cobol_events(res)[0]


def test_a_different_mapset_is_a_difference_and_the_same_one_is_not():
    for event in ("RECEIVE-MAP", "SEND-MAP"):
        cobol = [{"event": event, "map": "M", "mapset": "COBIL00"}]
        same = ec.compare_events(cobol, [{"event": event, "map": "M", "mapset": "COBIL00"}])
        mutant = ec.compare_events(cobol, [{"event": event, "map": "M", "mapset": "XOBIL00"}])
        assert "mapset" not in str(same)
        assert "mapset" in str(mutant)
        # a COBOL side that states no mapset compares nothing
        assert "mapset" not in str(
            ec.compare_events([{"event": event, "map": "M"}], [{"event": event, "map": "M", "mapset": "X"}])
        )


def test_no_committed_port_receives_a_map_without_its_mapset():
    """#5991: CicsTask.receive(map, Class) records mapset=null, where COBOL states the MAPSET."""
    root = Path(__file__).resolve().parents[1]
    receive = re.compile(r"\.receive\(\s*[^,()]+,\s*[A-Za-z_][\w.]*\.class\b")
    bad = [
        f"{p.relative_to(root)}: {m.group(0)}"
        for base in ("equivalence", "cics_crucible")
        for p in sorted((root / base).rglob("*.java"))
        for m in receive.finditer(p.read_text(encoding="utf-8"))
    ]
    assert bad == []


def _sent(**sub):
    return {"event": "SEND-MAP", "map": "M", "screen": {}, "subfields": {"F": sub}, "options": [], "cursor": None}


def test_7955_nul_and_space_attribute_bytes_are_different_values():
    """#7955: X'00' and X'40' in a map's attribute / colour / highlight byte are values, on both sides."""
    for key in ("attr", "color", "hilight"):
        assert ec.java_subfields({"F": {key: 0}}) == {"F": {key: 0}}
        assert ec.java_subfields({"F": {key: 0x40}}) == {"F": {key: 0x40}}
        assert ec.java_subfields({"F": {key: 0xF2}}) == {"F": {key: 0xF2}}
        nul = {"event": "SEND-MAP", "map": "M", "screen": {}, "subfields": {"F": {key: 0}}, "options": []}
        java = _sent(**{key: 0x40})
        assert "subfields.F" in str(ec.compare_events([nul], [java]))
        assert "subfields.F" not in str(ec.compare_events([nul], [_sent(**{key: 0})]))


def test_7955_map_data_nul_is_not_a_blank():
    cobol = [
        {"event": "SEND-MAP", "map": "M", "screen": {"F": ec.AlnumText("\x00\x00")}, "subfields": {}, "options": []}
    ]
    blank = [{"event": "SEND-MAP", "map": "M", "screen": {"F": "  "}, "subfields": {}, "options": []}]
    assert "screen.F" in str(ec.compare_events(cobol, blank))
    assert "screen.F" not in str(ec.compare_events(blank, blank))


def test_7955_maponly_sends_no_symbolic_map_bytes():
    cobol = [{"event": "SEND-MAP", "map": "M", "screen": {}, "subfields": {}, "options": ["MAPONLY"]}]
    java = [
        {"event": "SEND-MAP", "map": "M", "screen": None, "subfields": {"F": {"attr": 0x40}}, "options": ["MAPONLY"]}
    ]
    assert "subfields" not in str(ec.compare_events(cobol, java))
