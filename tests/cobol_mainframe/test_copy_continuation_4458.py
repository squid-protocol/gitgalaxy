"""#4458: entries that continue a COPYed record are not children of the 01 written before the COPY.

CardDemo COTRN02C: `01 CSUTLDTC-PARM.` ends with a nested group, then `COPY COCOM01Y.` (an 01 record of
its own) and `05 CDEMO-CT02-INFO ...` continuing that copied record. #4279 closed the group when the COPY
stayed on the entry's `copy_members`; once #4330 moved it to `section_copies` the closing was lost for a
COPY after the last entry of a nested group, and the continuation was counted under both records.
"""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

PROG = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CONT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 PARM-AREA.
          05 PARM-DATE.
             10 PARM-DATE-MM PIC X(2).
          05 PARM-RESULT.
             10 PARM-RESULT-MSG PIC X(61).
       COPY COMM01.
          05 CT02-INFO.
             10 CT02-TRN-FIRST PIC X(16).
             10 CT02-TRN-LAST PIC X(16).
       01 PLAIN-AREA.
          05 PLAIN-GROUP.
             10 PLAIN-A PIC X(3).
          05 PLAIN-B PIC X(4).
       COPY CHILD05.
       PROCEDURE DIVISION.
           GOBACK.
"""
COMM01 = "       01 COMM-AREA.\n          05 COMM-GEN.\n             10 COMM-FROM PIC X(8).\n"
CHILD05 = "          05 CHILD-X PIC X(5).\n"


@pytest.fixture(scope="module")
def ir(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy_continuation")
    repo = base / "estate"
    for rel, text in {"cbl/CONT.cbl": PROG, "cpy/COMM01.cpy": COMM01, "cpy/CHILD05.cpy": CHILD05}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


def _names(lay):
    return [f["name"] for f in lay["fields"] if f.get("pic")]


def test_entries_after_the_copy_are_not_the_preceding_01s(ir):
    ef = ir.files["cbl/CONT.cbl"]
    parm = next(r for r in ef.records if r.name == "PARM-AREA")
    lay = ir.record_layout(ef, parm)
    assert lay["bytes"] == 63  # 2 + 61, not + the 32 bytes of CT02-INFO
    assert _names(lay) == ["PARM-DATE-MM", "PARM-RESULT-MSG"]


def test_the_copied_record_still_carries_the_continuation(ir):
    ef = ir.files["cbl/CONT.cbl"]
    cb = ir.files["cpy/COMM01.cpy"]
    lay = ir.record_layout(cb, cb.records[0], ir._copy_extension(ef, cb) or None)
    assert lay["bytes"] == 8 + 32
    assert _names(lay) == ["COMM-FROM", "CT02-TRN-FIRST", "CT02-TRN-LAST"]


def test_a_copy_of_deeper_entries_stays_inside_the_record(ir):
    # the nearest negative: a member whose roots are 05 (not an 01) is part of the record above it
    ef = ir.files["cbl/CONT.cbl"]
    plain = next(r for r in ef.records if r.name == "PLAIN-AREA")
    lay = ir.record_layout(ef, plain)
    assert _names(lay) == ["PLAIN-A", "PLAIN-B", "CHILD-X"]
    assert lay["bytes"] == 12
