"""#7845 (C7): the CICS oracle's CONTAINERS end state is read as z/OS holds COMP-5 when the case declares
comp5_byte_order and lays the container out (`container_layouts`); anything else is read exactly as before."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.importorskip("tree_sitter_language_pack")
import equivalence_cics as ec

FIELDS = [
    {"name": "T", "offset": 0, "bytes": 2, "pic": "X(2)", "usage": None},
    {"name": "H", "offset": 2, "bytes": 2, "pic": "S9(4)", "usage": "COMP-5"},
    {"name": "W", "offset": 4, "bytes": 4, "pic": "S9(9)", "usage": "COMP-5"},
    {"name": "D", "offset": 8, "bytes": 8, "pic": "S9(17)", "usage": "COMP-5"},
    {"name": "B", "offset": 16, "bytes": 2, "pic": "S9(4)", "usage": "COMP"},
]
DECLARED = {"name": "c", "declared_differences": ["comp5_byte_order"]}
VALUES = [(-2, 70000, 123456789012345678), (32767, -1, -5), (0, 0, 0)]


def _oracle(h, w, d):  # cobc: COMP-5 little-endian, COMP big-endian
    return b"AB" + struct.pack("<hiq", h, w, d) + struct.pack(">h", 7)


@pytest.mark.parametrize("h,w,d", VALUES)
def test_declared_container_is_reversed_to_the_z_os_image_for_every_comp5_width(h, w, d):
    left = {"channel": "CH", "containers": {"C": _oracle(h, w, d).hex().upper()}}
    got = ec.oracle_containers(left, {"C": FIELDS}, DECLARED)
    assert bytes.fromhex(got["containers"]["C"]) == b"AB" + struct.pack(">hiq", h, w, d) + struct.pack(">h", 7)


def test_undeclared_unlisted_and_empty_containers_are_unchanged():
    left = {"channel": "CH", "containers": {"C": _oracle(1, 2, 3).hex().upper(), "E": ""}}
    assert ec.oracle_containers(left, {"C": FIELDS}, {"name": "c"}) is left
    assert ec.oracle_containers(left, {}, DECLARED) is left
    got = ec.oracle_containers(left, {"C": FIELDS}, DECLARED)
    assert got["containers"]["E"] == ""
    other = ec.oracle_containers(left, {"X": FIELDS}, DECLARED)
    assert other["containers"] == left["containers"]
    assert ec.oracle_containers(None, {"C": FIELDS}, DECLARED) is None


def test_a_layout_without_segments_is_refused_by_name(tmp_path):
    with pytest.raises(ec.Unsupported, match="describes no segments"):
        ec.container_fields(tmp_path, {"container_layouts": {"C": {"segments": []}}})
    assert ec.container_fields(tmp_path, {}) == {}


def test_a_start_channel_copy_is_reversed_like_the_end_state_container(tmp_path):
    # the copy START CHANNEL hands the started task: {name, containers} read from the stub's channel file
    (tmp_path / "1.channel").write_text(f"CH\nC 18 {_oracle(-2, 70000, 5).hex().upper()}\nE 0 -\n", encoding="ascii")
    copy = ec.channel_copy(tmp_path / "1.channel")
    got = ec.oracle_containers(copy, {"C": FIELDS}, DECLARED)
    assert got["name"] == "CH"
    assert bytes.fromhex(got["containers"]["C"]) == b"AB" + struct.pack(">hiq", -2, 70000, 5) + struct.pack(">h", 7)
    assert got["containers"]["E"] == ""
