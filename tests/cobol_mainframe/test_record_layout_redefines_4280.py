"""#4280: a REDEFINES wider than the item it overlays widens the shared storage. The record's
size is the max of the target and all its overlays, in `record_layout` and in the storage
spans the data-move reader uses. Before, an overlay was skipped outright, so carddemo
COADM02Y came back 272 bytes against the det translator's 407 and CORPT00C's JOB-DATA 1,360
against 80,000. One real scan backs every test."""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

PROG = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REDEF.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
      * carddemo COADM02Y: 2 rows of data, a 3-row OCCURS overlay.
       01  MENU-OPTIONS.
         05 OPT-COUNT                 PIC 9(02) VALUE 2.
         05 OPT-DATA.
           10 FILLER                  PIC X(10) VALUE 'ONE'.
           10 FILLER                  PIC X(10) VALUE 'TWO'.
         05 OPT-TABLE REDEFINES OPT-DATA.
           10 OPT-ROW OCCURS 3 TIMES  PIC X(10).
         05 OPT-TAIL                  PIC X(01).
      * carddemo CORPT00C JOB-DATA: the overlay is the whole record.
       01  JOB-DATA.
         02 JOB-DATA-1.
           05 FILLER                  PIC X(80) VALUE '//JOB'.
         02 JOB-DATA-2 REDEFINES JOB-DATA-1.
           05 JOB-LINES OCCURS 100 TIMES PIC X(80).
      * A narrower overlay changes nothing; of several overlays the widest wins.
       01  NARROW.
         05 N-DATE                    PIC X(10).
         05 N-PARTS REDEFINES N-DATE.
           10 N-YYYY                  PIC X(4).
         05 N-WIDE-1 REDEFINES N-DATE PIC X(12).
         05 N-WIDE-2 REDEFINES N-DATE PIC X(15).
         05 N-NEXT                    PIC X(2).
       PROCEDURE DIVISION.
           GOBACK.
"""


@pytest.fixture(scope="module")
def ir_and_file(tmp_path_factory):
    base = tmp_path_factory.mktemp("redef4280")
    (base / "repo").mkdir()
    (base / "repo" / "REDEF.cbl").write_text(PROG)
    ir = load_galaxy_ir(scan_to_db(base / "repo", base / "scan"))
    return ir, ir.files["REDEF.cbl"]


def _layout(ir_and_file, name):
    ir, ef = ir_and_file
    return ir.record_layout(ef, next(it for it in ef.records if it.name == name))


def test_a_wider_overlay_widens_the_record(ir_and_file):
    layout = _layout(ir_and_file, "MENU-OPTIONS")
    assert layout["bytes"] == 2 + 30 + 1
    # The overlay's fields are not listed; the field after it sits past the wider overlay.
    assert [(f["name"], f["offset"]) for f in layout["fields"]][-1] == ("OPT-TAIL", 32)


def test_an_overlay_of_the_whole_record(ir_and_file):
    assert _layout(ir_and_file, "JOB-DATA")["bytes"] == 8000


def test_narrow_and_several_overlays(ir_and_file):
    layout = _layout(ir_and_file, "NARROW")
    assert layout["bytes"] == 15 + 2
    assert [(f["name"], f["offset"]) for f in layout["fields"]] == [("N-DATE", 0), ("N-NEXT", 15)]


def test_storage_spans_agree(ir_and_file):
    ir, ef = ir_and_file
    spans = ir._storage_spans(ef)
    for name, size in (("MENU-OPTIONS", 33), ("JOB-DATA", 8000), ("NARROW", 17)):
        root = next(it for it in ef.records if it.name == name)
        assert spans[id(root)][2] == size
    tail = next(it for it in ef.data_items if it.name == "OPT-TAIL")
    assert spans[id(tail)][1] == 32
