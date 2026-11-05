"""#7646 slice 5: the CICS oracle's COMMAREA (RETURN / XCTL and a LINKed result) is read as z/OS holds COMP-5 when the
case declares comp5_byte_order (register C7); an undeclared case reads the bytes exactly as before."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.importorskip("tree_sitter_language_pack")
import equivalence_cics as ec

FIELDS = [
    {"name": "H", "offset": 0, "bytes": 2, "pic": "S9(4)", "usage": "COMP-5"},
    {"name": "W", "offset": 2, "bytes": 4, "pic": "S9(9)", "usage": "COMP-5"},
    {"name": "D", "offset": 6, "bytes": 8, "pic": "S9(17)", "usage": "COMP-5"},
    {"name": "B", "offset": 14, "bytes": 2, "pic": "S9(4)", "usage": "COMP"},
]
DECLARED = {"name": "c", "declared_differences": ["comp5_byte_order"]}
VALUES = [(-2, 70000, 123456789012345678), (32767, -1, -5), (0, 0, 0)]


def _oracle(h, w, d):
    return struct.pack("<hiq", h, w, d) + struct.pack(">h", 7)  # cobc: COMP-5 native little-endian, COMP big-endian


@pytest.mark.parametrize("h,w,d", VALUES)
def test_declared_oracle_commarea_decodes_to_the_values_for_every_comp5_width(h, w, d):
    data = _oracle(h, w, d)
    view = ec.oracle_commarea(data, FIELDS, DECLARED)
    got = ec.decode_record(view, FIELDS, exact=True)
    assert got == {"H": str(h), "W": str(w), "D": str(d), "B": "7"}  # COMP is untouched


def test_an_undeclared_case_and_an_empty_layout_read_the_bytes_as_before():
    data = _oracle(-2, 70000, 5)
    assert ec.oracle_commarea(data, FIELDS, {"name": "c"}) is data
    assert ec.oracle_commarea(data, [], DECLARED) is data
    assert ec.decode_record(data, FIELDS, exact=True)["W"] != "70000"  # the old read, unreversed


def _task(tmp_path, data):
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("1 RETURN transid=ABCD level=1\n", encoding="latin-1")
    (out / "1.bin").write_bytes(data)
    (out / "commarea.out").write_bytes(data)
    return out


def test_outputs_reads_return_and_linked_commarea_through_the_declared_reversal(tmp_path):
    data = _oracle(-2, 70000, 5)
    out = _task(tmp_path, data)
    want = {"H": "-2", "W": "70000", "D": "5", "B": "7"}
    res = ec.outputs(out, DECLARED, tmp_path, FIELDS)
    assert res["return"]["commarea"] == want
    assert res["linked_commarea"] == want
    res = ec.outputs(out, {"name": "c"}, tmp_path, FIELDS)
    assert res["return"]["commarea"]["W"] != "70000" and res["linked_commarea"]["W"] != "70000"
