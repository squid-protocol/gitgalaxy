"""#4404: every unit (paragraph / section / main-line block) of a multi-program source names its
owning program (`EngineUnit.program`), derived in GalaxyIR as #4245 does for data items. A
one-program source keeps `program=None`, and PROGRAM-ID itself is still not a unit (#4203)."""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from scan_server import scan_to_db

ONE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONE.
       PROCEDURE DIVISION.
       MAIN-PARA.
           GOBACK.
"""

SIBLINGS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ALPHA.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM SHARED-PARA.
           GOBACK.
       SHARED-PARA.
           DISPLAY 'A'.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BETA.
       PROCEDURE DIVISION.
       SHARED-PARA.
           DISPLAY 'B'.
           GOBACK.
       END PROGRAM BETA.
       END PROGRAM ALPHA.
"""


@pytest.fixture(scope="module")
def ir(tmp_path_factory):
    root = tmp_path_factory.mktemp("units_4404")
    repo = root / "estate"
    (repo / "cbl").mkdir(parents=True)
    for rel, text in {
        "cbl/ONE.cbl": ONE,
        "cbl/SIBLINGS.cbl": SIBLINGS,
    }.items():
        (repo / rel).write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, root / "scan"))


def test_a_multi_program_source_names_the_owner_of_every_unit(ir):
    units = ir.files["cbl/SIBLINGS.cbl"].units
    assert [(u.name, u.start_line, u.program) for u in units] == [
        ("MAIN-PARA", 4, "ALPHA"),
        ("SHARED-PARA", 7, "ALPHA"),
        ("SHARED-PARA", 12, "BETA"),
    ]


def test_same_named_paragraphs_of_sibling_programs_have_distinct_owners(ir):
    shared = [u.program for u in ir.files["cbl/SIBLINGS.cbl"].units if u.name == "SHARED-PARA"]
    assert shared == ["ALPHA", "BETA"]


def test_a_one_program_source_is_unchanged(ir):
    units = ir.files["cbl/ONE.cbl"].units
    assert units
    assert {u.program for u in units} == {None}
