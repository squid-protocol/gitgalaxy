"""#4525: a group's USAGE applies to every elementary item under it that has no USAGE of its own
(IBM Enterprise COBOL, COBOL 2002). The engine read `item.usage` from the item alone, so CardDemo
CBSTM03A's `01 COMP-VARIABLES COMP.` (4 x `PIC S9(4)`) came back 16 bytes, 4 each, against 8 bytes,
2 each, and `01 COMP3-VARIABLES COMP-3.` + `05 WS-TOTAL-AMT PIC S9(9)V99` 11 bytes against 6.

The extractor resolves it within a source (record_data.usage); a COPY member's items learn the usage
of the group they are COPYed under in GalaxyIR (record_layout and the storage spans). One real scan
backs the layout tests."""

import os
from pathlib import Path

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

# CardDemo app/cbl/CBSTM03A.CBL:59-65, verbatim.
CBSTM03A = """\
       01  COMP-VARIABLES          COMP.
           05  CR-CNT              PIC S9(4) VALUE 0.
           05  TR-CNT              PIC S9(4) VALUE 0.
           05  CR-JMP              PIC S9(4) VALUE 0.
           05  TR-JMP              PIC S9(4) VALUE 0.
       01  COMP3-VARIABLES         COMP-3.
           05  WS-TOTAL-AMT        PIC S9(9)V99 VALUE 0.
"""

PROG = (
    """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. GRPUSAGE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
"""
    + CBSTM03A
    + """\
      * A POINTER group: its members have no PIC and no USAGE of their own.
       01  PTRS                    USAGE IS POINTER.
           05  P1.
           05  P2.
      * A nested group's own USAGE overrides the outer one; an item's own USAGE wins;
      * REDEFINES and OCCURS members inherit; an 88 takes no storage.
       01  MIXED                   COMP.
           05  M-BIN               PIC S9(9).
               88  M-ZERO          VALUE 0.
           05  M-PACKED-GRP        COMP-3.
               10  M-PK1           PIC S9(5).
               10  M-PK2           PIC S9(7)V99.
           05  M-DISP              PIC 9(4) DISPLAY.
           05  M-TAB               OCCURS 3 TIMES.
               10  M-T             PIC 9(4).
           05  M-ALIAS REDEFINES M-TAB.
               10  M-A             PIC 9(8).
           05  M-SUB.
               10  M-S             PIC 9(18).
           05  M-ZONED-GRP         DISPLAY.
               10  M-Z             PIC 9(3).
       77  LONE                    PIC S9(4).
      * A COPY member under a COMP-3 group.
       01  COPIED-GRP              COMP-3.
           COPY PKMEMBER.
       PROCEDURE DIVISION.
           GOBACK.
"""
)

PKMEMBER = """\
           05  CP-AMT              PIC S9(7)V99.
           05  CP-QTY              PIC S9(3).
"""


def _usages(src: str) -> dict:
    return {r["name"]: r["usage"] for r in extract_boundary("cobol", src)["records"]}


def test_extractor_records_the_inherited_usage():
    u = _usages(PROG)
    assert [u[n] for n in ("CR-CNT", "TR-CNT", "CR-JMP", "TR-JMP")] == ["COMP"] * 4
    assert u["WS-TOTAL-AMT"] == "COMP-3"
    assert u["P1"] == u["P2"] == "POINTER"
    assert u["M-BIN"] == "COMP"
    assert u["M-PK1"] == u["M-PK2"] == "COMP-3"  # the nested group's own USAGE
    assert u["M-DISP"] == "DISPLAY"  # the item's own USAGE
    assert u["M-T"] == u["M-A"] == u["M-S"] == "COMP"  # OCCURS / REDEFINES / nested plain group
    assert u["M-Z"] is None  # an inherited DISPLAY is the default: not recorded, but it stops the COMP
    assert u["M-ZERO"] is None  # a condition has no storage: no usage rides on it
    assert u["LONE"] is None  # a 77 belongs to no group


@pytest.fixture(scope="module")
def ir_and_file(tmp_path_factory):
    base = tmp_path_factory.mktemp("grpusage4525")
    (base / "repo").mkdir()
    (base / "repo" / "GRPUSAGE.cbl").write_text(PROG)
    (base / "repo" / "PKMEMBER.cpy").write_text(PKMEMBER)
    ir = load_galaxy_ir(scan_to_db(base / "repo", base / "scan"))
    return ir, ir.files["GRPUSAGE.cbl"]


def _layout(ir_and_file, name):
    ir, ef = ir_and_file
    return ir.record_layout(ef, next(it for it in ef.records if it.name == name))


def _fields(layout):
    return [(f["name"], f["offset"], f["bytes"], f["class"]) for f in layout["fields"]]


def test_cbstm03a_comp_variables(ir_and_file):
    layout = _layout(ir_and_file, "COMP-VARIABLES")
    assert layout["bytes"] == 8
    assert _fields(layout) == [
        ("CR-CNT", 0, 2, "B"),
        ("TR-CNT", 2, 2, "B"),
        ("CR-JMP", 4, 2, "B"),
        ("TR-JMP", 6, 2, "B"),
    ]


def test_cbstm03a_ws_total_amt(ir_and_file):
    layout = _layout(ir_and_file, "COMP3-VARIABLES")
    assert layout["bytes"] == 6
    assert _fields(layout) == [("WS-TOTAL-AMT", 0, 6, "P")]


def test_pointer_group(ir_and_file):
    layout = _layout(ir_and_file, "PTRS")
    assert layout["bytes"] == 8
    assert _fields(layout) == [("P1", 0, 4, "A"), ("P2", 4, 4, "A")]


def test_nested_override_own_usage_occurs_redefines(ir_and_file):
    layout = _layout(ir_and_file, "MIXED")
    assert _fields(layout) == [
        ("M-BIN", 0, 4, "B"),
        ("M-PK1", 4, 3, "P"),
        ("M-PK2", 7, 5, "P"),
        ("M-DISP", 12, 4, "9"),
        ("M-T", 16, 2, "B"),  # one occurrence listed; the 3 x 2-byte table (6) outruns its 4-byte REDEFINES
        ("M-S", 22, 8, "B"),
        ("M-Z", 30, 3, "9"),  # the nested DISPLAY group overrides the outer COMP
    ]
    assert layout["bytes"] == 33


def test_a_77_is_unchanged(ir_and_file):
    assert _layout(ir_and_file, "LONE")["bytes"] == 4


def test_copy_member_under_a_comp3_group(ir_and_file):
    layout = _layout(ir_and_file, "COPIED-GRP")
    assert _fields(layout) == [("CP-AMT", 0, 5, "P"), ("CP-QTY", 5, 2, "P")]
    assert layout["bytes"] == 7
    assert {f["usage"] for f in layout["fields"]} == {"COMP-3"}


def test_storage_spans_agree(ir_and_file):
    ir, ef = ir_and_file
    spans = ir._storage_spans(ef)
    for name, size in (("COMP-VARIABLES", 8), ("COMP3-VARIABLES", 6), ("PTRS", 8), ("MIXED", 33), ("COPIED-GRP", 7)):
        root = next(it for it in ef.records if it.name == name)
        assert spans[id(root)][2] == size, name


def _carddemo() -> Path:
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA") or str(
        Path(__file__).resolve().parents[2] / ".mainframe_corpora"
    )
    return Path(root) / "aws-mainframe-modernization-carddemo" / "app" / "cbl" / "CBSTM03A.CBL"


@pytest.mark.skipif(not _carddemo().is_file(), reason="CardDemo corpus not present")
def test_real_cbstm03a(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "CBSTM03A.CBL").write_bytes(_carddemo().read_bytes())
    ir = load_galaxy_ir(scan_to_db(tmp_path / "repo", tmp_path / "scan"))
    ef = ir.files["CBSTM03A.CBL"]

    def layout(name):
        return ir.record_layout(ef, next(it for it in ef.records if it.name == name))

    comp = layout("COMP-VARIABLES")
    assert comp["bytes"] == 8 and [f["bytes"] for f in comp["fields"]] == [2, 2, 2, 2]
    assert layout("COMP3-VARIABLES")["bytes"] == 6
