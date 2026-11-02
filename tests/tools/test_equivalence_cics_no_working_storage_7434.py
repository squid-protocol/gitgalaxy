"""#7434: a program with no WORKING-STORAGE SECTION (a LOAD target that only RETURNs) still gets the EIB."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec


def _src(*lines):
    return "\n".join("       " + ln for ln in lines) + "\n"


BARE = _src(
    "IDENTIFICATION DIVISION.",
    "PROGRAM-ID. BARE.",
    "PROCEDURE DIVISION.",
    "MAIN-PARA.",
    "    EXEC CICS RETURN END-EXEC.",
)
LINKAGE_ONLY = _src(
    "IDENTIFICATION DIVISION.", "PROGRAM-ID. LKONLY.", "DATA DIVISION.", "LINKAGE SECTION.",
    "01  DFHCOMMAREA PIC X(4).", "PROCEDURE DIVISION.", "MAIN-PARA.", "    EXEC CICS RETURN END-EXEC.",
)  # fmt: skip
WITH_WS = _src(
    "IDENTIFICATION DIVISION.", "PROGRAM-ID. HASWS.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
    "01  X PIC X.", "PROCEDURE DIVISION.", "MAIN-PARA.", "    EXEC CICS RETURN END-EXEC.",
)  # fmt: skip


@pytest.mark.parametrize("source", [BARE, LINKAGE_ONLY, WITH_WS])
def test_every_data_division_shape_gets_one_eib_ahead_of_the_procedure(source):
    text, _ = ec.translate(source)
    assert text.count("COPY DFHEIBLK") == 1
    assert text.count("DATA DIVISION") == 1
    assert text.count("WORKING-STORAGE SECTION") == 1
    assert text.index("WORKING-STORAGE SECTION") < text.index("COPY DFHEIBLK") < text.index("PROCEDURE DIVISION")
    if "LINKAGE SECTION" in text:
        assert text.index("COPY DFHEIBLK") < text.index("LINKAGE SECTION")


def test_a_program_with_no_procedure_division_is_still_refused_by_name():
    with pytest.raises(ec.Unsupported, match="no WORKING-STORAGE SECTION"):
        ec.translate(_src("IDENTIFICATION DIVISION.", "PROGRAM-ID. NOPROC."))
