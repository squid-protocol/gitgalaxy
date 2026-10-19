"""#5649 slice 1: the engine lays records out the way the translator needs them.

1. A POINTER's width is a parameter of GalaxyIR.record_layout: z/OS's 4 bytes (LP(32)) by default, the
   translator's 8 (GnuCOBOL x86-64, oracle register C9) when its storage is what a layout is compared with.
   IBM Enterprise COBOL, "USAGE POINTER phrase": a pointer data item is 4 bytes under LP(32); SYNC aligns
   it on a fullword. Under SYNC the boundary follows the width.
2. A `COPY` of a system member the estate does not ship, where GitGalaxy writes a stand-in (CMQ*: register
   W1, CEEIGZCT: L4), is laid out from that stand-in -- the same text the translator falls back on -- and
   the layout says so (`stand_ins`). A copybook the repository holds always wins over a stand-in.
"""

import pytest

from gitgalaxy.core.copy_libraries import STAND_IN_DIR, stand_in_registers, stand_in_text
from gitgalaxy.standards.mq import LENGTHS, STAND_INS
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import ZOS_POINTER_BYTES, load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.det.cics import POINTER_BYTES

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRMQ.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-REC.
           05  WS-A               PIC X(4).
           05  WS-B               PIC S9(4) COMP.
           05  WS-P               POINTER.
           05  WS-C               PIC X.
       01  WS-SYNC.
           05  S-A                PIC X.
           05  S-P                POINTER SYNC.
       01  MQM-OD.
           COPY CMQODV.
       01  MQM-MD.
           COPY CMQMDV.
       01  OWN-GMO.
           COPY CMQGMOV.
       PROCEDURE DIVISION.
           GOBACK.
"""
# the estate's own CMQGMOV: shorter than the stand-in, and it must win
OWN_CMQGMOV = """\
           10  MQGMO.
               15  MQGMO-STRUCID      PIC X(4).
               15  MQGMO-VERSION      PIC S9(9) BINARY.
"""


@pytest.fixture(scope="module")
def ir(tmp_path_factory):
    base = tmp_path_factory.mktemp("pointer_stand_ins_5649")
    (base / "repo").mkdir()
    (base / "repo" / "PTRMQ.cbl").write_text(PROGRAM, encoding="utf-8")
    (base / "repo" / "CMQGMOV.cpy").write_text(OWN_CMQGMOV, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(base / "repo", base / "scan"))


def _layout(ir, name, **kw):
    ef = ir.files["PTRMQ.cbl"]
    return ir.record_layout(ef, next(it for it in ef.records if it.name == name), **kw)


def _fields(layout):
    return [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]]


def test_a_pointer_is_four_bytes_by_default_and_the_callers_width_when_given(ir):
    assert ZOS_POINTER_BYTES == 4 and POINTER_BYTES == 8
    assert _fields(_layout(ir, "WS-REC")) == [("WS-A", 0, 4), ("WS-B", 4, 2), ("WS-P", 6, 4), ("WS-C", 10, 1)]
    wide = _layout(ir, "WS-REC", pointer_bytes=POINTER_BYTES)
    assert _fields(wide) == [("WS-A", 0, 4), ("WS-B", 4, 2), ("WS-P", 6, 8), ("WS-C", 14, 1)]
    assert wide["bytes"] == 15


def test_a_synchronized_pointer_aligns_on_its_own_width(ir):
    assert _fields(_layout(ir, "WS-SYNC")) == [("S-A", 0, 1), ("S-P", 4, 4)]
    assert _fields(_layout(ir, "WS-SYNC", pointer_bytes=8)) == [("S-A", 0, 1), ("S-P", 8, 8)]


@pytest.mark.parametrize("record, member", [("MQM-OD", "CMQODV"), ("MQM-MD", "CMQMDV")])
def test_an_unshipped_mq_copybook_is_laid_out_from_its_stand_in(ir, record, member):
    layout = _layout(ir, record)
    assert layout["bytes"] == LENGTHS[member]  # IBM's documented version-1 length
    assert layout["unexpanded"] == [] and layout["stand_ins"] == [f"stand-in#{member}"]


def test_the_estates_own_copybook_wins_over_the_stand_in(ir):
    layout = _layout(ir, "OWN-GMO")
    assert layout["copybooks"] == ["CMQGMOV.cpy"] and "stand_ins" not in layout
    assert layout["bytes"] == 8


def test_a_record_with_no_stand_in_keeps_its_old_shape(ir):
    assert "stand_ins" not in _layout(ir, "WS-REC")


def test_every_registered_stand_in_is_shipped_and_comment_free():
    registers = stand_in_registers()
    assert set(STAND_INS) | {"CEEIGZCT"} == set(registers)
    for member in registers:
        assert (STAND_IN_DIR / f"{member}.cpy").is_file()
        assert "GitGalaxy-written" not in stand_in_text(member)  # the comment block is blanked
    assert stand_in_text("DFHAID") is None  # shipped for the translator, but not a register stand-in
