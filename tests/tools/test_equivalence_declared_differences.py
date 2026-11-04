"""#7646 slice 3: a case's `declared_differences` and the comparator's COMP-5 byte reversal (register C7)."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_common as common


def _field(name, offset, nbytes, pic, usage):
    return {"name": name, "offset": offset, "bytes": nbytes, "pic": pic, "usage": usage}


# one record: S9(4) 2 bytes, S9(9) 4 bytes, S9(17) 8 bytes, a COMP (big-endian on both) S9(4), 2 bytes
FIELDS = [
    _field("H", 0, 2, "S9(4)", "COMP-5"),
    _field("W", 2, 4, "S9(9)", "COMP-5"),
    _field("D", 6, 8, "S9(17)", "COMP-5"),
    _field("B", 14, 2, "S9(4)", "COMP"),
]
VALUES = [(-2, 32767, 1), (1234, -1, 123456789012345678), (0, 0, 0), (-9999, 2147483647, -5)]


def _record(h, w, d, b, order):
    return struct.pack(order + "hiq", h, w, d) + struct.pack(">h", b)


def _both(h, w, d, b=7):
    """(the oracle's record: little-endian COMP-5; the port's: z/OS big-endian COMP-5)."""
    return _record(h, w, d, b, "<"), _record(h, w, d, b, ">")


@pytest.mark.parametrize("h,w,d", VALUES)
def test_reversal_makes_the_zos_port_equal_the_oracle_for_every_comp5_width(h, w, d):
    cobol, java = _both(h, w, d)
    plain = common.diff_records(cobol, java, 16, FIELDS)
    declared = common.diff_records(cobol, java, 16, FIELDS, oracle_comp5_reversed=True)
    assert declared["equal"] == 1 and not declared["diffs"]
    if (h, w, d) != (0, 0, 0):  # without the declaration the bytes differ: never silently equal
        assert plain["diffs"], "an undeclared byte-order difference must stay a difference"


def test_reversal_covers_only_what_is_declared_and_never_a_real_value_difference():
    cobol, java = _both(5, 6, 7)
    other = _record(5, 6, 8, 7, ">")  # D differs in value
    d = common.diff_records(cobol, other, 16, FIELDS, oracle_comp5_reversed=True)
    assert [f["field"] for f in d["diffs"][0]["fields"]] == ["D"]
    # a COMP field is big-endian on both: reversing it would be wrong, and the comparator does not
    cobol_b = _record(5, 6, 7, 0x0102, "<")
    java_b = _record(5, 6, 7, 0x0201, ">")
    d = common.diff_records(cobol_b, java_b, 16, FIELDS, oracle_comp5_reversed=True)
    assert [f["field"] for f in d["diffs"][0]["fields"]] == ["B"]
    # the port holding the OLD little-endian image is not equal under the declaration
    d = common.diff_records(cobol, cobol, 16, FIELDS, oracle_comp5_reversed=True)
    assert d["diffs"]


def test_a_one_byte_field_and_other_usages_are_not_reversed():
    assert common.comp5_zos_view(b"\x01", "COMP-5", 1) == b"\x01"
    assert common.comp5_zos_view(b"\x01\x02", "COMP", 2) == b"\x01\x02"
    assert common.comp5_zos_view(b"\x01\x02", "COMPUTATIONAL-5", 2) == b"\x02\x01"
    assert common.comp5_zos_view(b"12", "DISPLAY", 2) == b"12"
    assert common.comp5_zos_view(b"12", None, 2) == b"12"


def test_declared_differences_names_its_kinds_and_refuses_the_rest():
    assert common.declared_differences({"name": "x"}) == []
    assert common.declared_differences({"declared_differences": ["comp5_byte_order"]}) == ["comp5_byte_order"]
    rec = common.declared_difference_records({"declared_differences": ["comp5_byte_order"]})
    assert [(r["kind"], r["difference"]) for r in rec] == [("declared", "comp5_byte_order")]
    for bad in (["comp5"], ["comp5_byte_order", "comp5_byte_order"], "comp5_byte_order", [1]):
        with pytest.raises(SystemExit, match="declared"):
            common.declared_differences({"name": "x", "declared_differences": bad})


# --- sibling comparators (#7646 slice 4): variable records and CALL group items ---

V_FIELDS = FIELDS[:2]  # 6 bytes: H (2) and W (4)


def _varseq(*recs):
    return b"".join(len(r).to_bytes(2, "big") + b"\x00\x00" + r for r in recs)


def test_diff_varseq_reverses_the_oracle_side_per_record_layout_only_when_declared():
    lo, be = struct.pack("<hi", -2, 70000), struct.pack(">hi", -2, 70000)
    cobol, java = _varseq(lo, lo), _varseq(be, be)
    layouts = {6: V_FIELDS}
    declared = common.diff_varseq(cobol, java, layouts, oracle_comp5_reversed=True)
    assert declared["equal"] == 2 and not declared["diffs"]
    undeclared = common.diff_varseq(cobol, java, layouts)  # exactly as before: the bytes differ
    assert undeclared["equal"] == 0 and len(undeclared["diffs"]) == 2
    assert common.diff_varseq(cobol, java, layouts, "cp037", "latin-1") == undeclared
    # a real value difference still differs; a length with no layout is compared byte for byte
    other = _varseq(struct.pack(">hi", -2, 70001), be)
    d = common.diff_varseq(cobol, other, layouts, oracle_comp5_reversed=True)
    assert d["equal"] == 1 and [f["field"] for f in d["diffs"][0]["fields"]] == ["W"]
    assert common.diff_varseq(cobol, java, {}, oracle_comp5_reversed=True)["diffs"]


def test_a_redefines_over_one_comp5_field_is_reversed_once():
    fields = [_field("A", 0, 2, "S9(4)", "COMP-5"), _field("A-R", 0, 2, "S9(4)", "COMP-5")]
    assert common.comp5_zos_record(b"\x34\x12", fields) == b"\x12\x34"
    d = common.diff_records(b"\x34\x12", b"\x12\x34", 2, fields, oracle_comp5_reversed=True)
    assert d["equal"] == 1


def _call_fixture(tmp_path):
    ec = pytest.importorskip("equivalence_call")
    layout = [_field("H", 0, 2, "S9(4)", "COMP-5"), _field("W", 2, 4, "S9(9)", "COMP-5")]
    u = {"name": "ITEM", "size": 6, "record": {"copybook": "x.cpy"}}
    return ec, layout, u


def test_compare_item_reverses_the_oracle_item_on_the_area_and_the_dto_paths(tmp_path, monkeypatch):
    ec, layout, u = _call_fixture(tmp_path)
    monkeypatch.setattr(ec, "item_layout", lambda *a, **k: layout)
    lo, be = struct.pack("<hi", -2, 70000), struct.pack(">hi", -2, 70000)
    case = {"name": "c"}
    props = {"H": ("h", "S"), "W": ("w", "S")}
    # area path (the port's bytes)
    bad, _ = ec.compare_item(case, tmp_path, u, lo, None, be, props, "latin-1", True)
    assert bad == []
    bad, _ = ec.compare_item(case, tmp_path, u, lo, None, be, props, "latin-1")
    assert bad, "undeclared: the byte-order difference stays a difference"
    # DTO path: the oracle's little-endian bytes decode to the right values only when declared
    dto = {"h": -2, "w": 70000}
    bad, _ = ec.compare_item(case, tmp_path, u, lo, dto, None, props, "latin-1", True)
    assert bad == []
    bad, _ = ec.compare_item(case, tmp_path, u, lo, dto, None, props, "latin-1")
    assert bad
    bad, _ = ec.compare_item(case, tmp_path, u, lo, {"h": -2, "w": 70001}, None, props, "latin-1", True)
    assert [b["field"] for b in bad] == ["ITEM.W"]


# --- cics file comparator (#7646 slice 5) ---


def _files_fixture(tmp_path, monkeypatch, left, right):
    ecx = pytest.importorskip("equivalence_cics")
    layout = [_field("H", 0, 2, "S9(4)", "COMP-5"), _field("W", 2, 4, "S9(9)", "COMP-5")]
    monkeypatch.setattr(ecx.common, "layout_fields", lambda *a, **k: layout)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "s.F.out").write_bytes(right)
    f = [{"base": "F", "reclen": 6, "key_offset": 0, "key_length": 2}]
    return ecx, f


def _run(ecx, tmp_path, f, left, extra):
    case = {"name": "c", "datasets": {"F": {"copybook": "x.cpy"}}, **extra}
    return ecx.compare_files(case, tmp_path, f, {"F": left}, tmp_path / "out", "s")


def test_compare_files_reverses_the_oracle_records_only_when_declared(tmp_path, monkeypatch):
    lo, be = struct.pack("<hi", 1, 70000), struct.pack(">hi", 1, 70000)
    ecx, f = _files_fixture(tmp_path, monkeypatch, lo, be)
    assert _run(ecx, tmp_path, f, lo, {"declared_differences": ["comp5_byte_order"]}) == {}
    assert "F" in _run(ecx, tmp_path, f, lo, {})  # undeclared: exactly as before, a difference
    # a port that kept the oracle's little-endian image is NOT equal under the declaration (raw equality is not a pass)
    (tmp_path / "out" / "s.F.out").write_bytes(lo)
    assert "F" in _run(ecx, tmp_path, f, lo, {"declared_differences": ["comp5_byte_order"]})
    assert _run(ecx, tmp_path, f, lo, {}) == {}
    # a real value difference still differs
    (tmp_path / "out" / "s.F.out").write_bytes(struct.pack(">hi", 1, 70001))
    d = _run(ecx, tmp_path, f, lo, {"declared_differences": ["comp5_byte_order"]})
    assert [x["field"] for x in d["F"]["diffs"][0]["fields"]] == ["W"]


# --- IMS database comparators (#7646 slice 6) ---


def _ims_case(extra):
    return {"ims": {"dbd": [], "psb": "", "segments": {"R": {"copybook": "r.cpy"}}, "gsam": {"G": {"copybook": "g.cpy"}}},
            **extra}  # fmt: skip


def _ims(monkeypatch, dbd):
    ei = pytest.importorskip("equivalence_ims")
    layout = [_field("H", 0, 2, "S9(4)", "COMP-5"), _field("W", 2, 4, "S9(9)", "COMP-5")]
    monkeypatch.setattr(ei.common, "layout_fields", lambda *a, **k: layout)
    monkeypatch.setattr(ei, "dbd_definitions", lambda c, corpus: {"X": dbd})
    return ei


@pytest.mark.parametrize("gsam", [False, True])
def test_diff_db_and_diff_gsam_reverse_the_oracle_records_only_when_declared(tmp_path, monkeypatch, gsam):
    lo, be = struct.pack("<hi", 1, 70000), struct.pack(">hi", 1, 70000)
    if gsam:
        ei = _ims(monkeypatch, {"gsam": 6, "segments": []})
        pack = lambda b: b  # noqa: E731
        name = "G"
    else:
        ei = _ims(monkeypatch, {"segments": [{"name": "R", "bytes": 6}]})
        pack = lambda b: b"R       " + b  # noqa: E731
        name = "X"

    def run(oracle, port, extra):
        case = _ims_case(extra)
        if gsam:
            return ei.diff_gsam(case, tmp_path, name, 6, pack(oracle), pack(port))
        return ei.diff_db(case, tmp_path, name, pack(oracle), pack(port))

    decl = {"declared_differences": ["comp5_byte_order"]}
    assert run(lo, be, decl)["diffs"] == []
    assert run(lo, be, {})["diffs"]  # undeclared: exactly as before, a difference
    # a port that kept the oracle's little-endian image is NOT equal under the declaration
    assert run(lo, lo, decl)["diffs"]
    assert run(lo, lo, {})["diffs"] == []
    # a real value difference still differs, on the one field
    d = run(lo, struct.pack(">hi", 1, 70001), decl)["diffs"][0]["diffs"]
    assert [x["field"] for x in d[0]["fields"]] == ["W"]
