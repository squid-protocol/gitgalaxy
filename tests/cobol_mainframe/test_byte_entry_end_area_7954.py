"""#7954 slice 13: the end area of a byte[] COMMAREA entry (`entry_only`) is compared, not dropped.

The generated port keeps no caBack on that entry, so the driver reads DFHCOMMAREA's own storage back (record + `beyond`)
and `caller_bytes_diff` judges it against the bytes the COBOL run left (commarea.out).
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

EQ = Path(__file__).resolve().parents[1] / "equivalence"


def _eq():
    import equivalence_cics as eq

    return eq


def _out(tmp_path, data: bytes) -> Path:
    (tmp_path / "commarea.out").write_bytes(data)
    return tmp_path


def _ev(data: bytes):
    return [{"event": "COMMAREA", "area": base64.b64encode(data).decode()}]


def test_an_entry_only_end_area_that_differs_is_reported_and_one_that_agrees_is_not(tmp_path):
    eq = _eq()
    sc = {"name": "s", "commarea_hex": "C1C2", "entry_only": True}
    assert eq.caller_bytes_diff(sc, _out(tmp_path, b"AB"), _ev(b"AX")) == {"cobol": "4142", "java": "4158"}
    assert eq.caller_bytes_diff(sc, _out(tmp_path, b"AB"), _ev(b"AB")) is None


def test_the_java_scenario_tells_the_driver_it_is_entry_only():
    eq = _eq()
    sc = {"name": "s", "commarea_hex": "C1C2", "entry_only": True}
    assert eq._java_untyped_commarea({}, sc, [])["entry_only"] is True
    assert "entry_only" not in eq._java_untyped_commarea({}, {"name": "s", "commarea_hex": "C1C2"}, [])


def test_the_driver_reads_the_end_storage_only_for_entry_only():
    src = Path(_eq().__file__).read_text(encoding="utf-8")
    assert 'sc.path("entry_only").asBoolean(false) && commarea instanceof byte[] entered' in src
    assert "static byte[] endStorage(Object program, int len)" in src


def test_each_getcompy_and_getscode_entry_only_scenario_has_bytes_past_the_record():
    for name, record in (("cbsa-getcompy", 40), ("cbsa-getscode", 6)):
        scs = json.loads((EQ / name / "case.json").read_text(encoding="utf-8"))["scenarios"]
        lens = {len(s["commarea_hex"]) // 2 for s in scs if s.get("entry_only")}
        assert any(n > record for n in lens) and any(n < record for n in lens), (name, lens)


def test_an_entry_only_end_area_in_the_regions_page_agrees_only_when_wholly_so(tmp_path):
    import base64

    eq = _eq()
    (tmp_path / "commarea.out").write_bytes(bytes.fromhex("E2C1C2"))
    sc = {"name": "s", "commarea_hex": "E2C1C2", "entry_only": True}
    case = {"data_encoding": "latin-1"}

    def ev(b):
        return [{"event": "COMMAREA", "area": base64.b64encode(b).decode()}]

    assert eq.caller_bytes_diff(sc, tmp_path, ev(bytes.fromhex("E2C1C2")), case) is None
    assert eq.caller_bytes_diff(sc, tmp_path, ev(bytes.fromhex("426562")), case) is None
    assert eq.caller_bytes_diff(sc, tmp_path, ev(bytes.fromhex("426563")), case) is not None
    assert eq.caller_bytes_diff(sc, tmp_path, ev(bytes.fromhex("426562"))) is not None
