"""#4330: the extractor puts every COPY between an entry and the next level number on that entry
(`copy_members`); it cannot see the members' own levels. A member whose first data entry is an 01
(or 77) begins a record of its own (a level-01 entry in copied text begins a new record), so it is
not the entry's. GalaxyIR settles that once the COPY edges resolve, and moves such members -- and
any later member of a run that does not resolve -- to `EngineFile.section_copies`."""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

CPYFOLD = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CPYFOLD.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-AREA.
           COPY CPYAREA.
           COPY CPYREC.
       01  WS-LINK.
           COPY CPYAREA.
           COPY DFHAID.
           COPY NOTHERE.
       01  WS-GAP.
           COPY NOTHERE.
           COPY CPYAREA.
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE SPACES TO AREA-NAME REC-KEY
           GOBACK.
"""
CPYAREA = "           05  AREA-NAME          PIC X(20).\n           05  AREA-CODE          PIC 9(4).\n"
CPYREC = "       01  REC-RECORD.\n           05  REC-KEY            PIC X(8).\n           05  REC-DATA           PIC X(40).\n"


@pytest.fixture(scope="module")
def ir(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy_own_01")
    repo = base / "estate"
    for rel, text in {"cbl/CPYFOLD.cbl": CPYFOLD, "cpy/CPYAREA.cpy": CPYAREA, "cpy/CPYREC.cpy": CPYREC}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


def _root(ir, name):
    ef = ir.files["cbl/CPYFOLD.cbl"]
    return ef, next(r for r in ef.records if r.name == name)


def test_a_member_opening_its_own_01_is_not_the_entrys(ir):
    ef, root = _root(ir, "WS-AREA")
    assert root.copy_members == "CPYAREA"
    layout = ir.record_layout(ef, root)
    assert layout["bytes"] == 24
    assert [f["name"] for f in layout["fields"] if f.get("name") != "WS-AREA"] == ["AREA-NAME", "AREA-CODE"]


def test_unresolved_members_after_the_first_are_section_level(ir):
    # CUSTINQ shape: a resolved 05-level member, then a runtime (DFHAID) and a missing member
    ef, root = _root(ir, "WS-LINK")
    assert root.copy_members == "CPYAREA"
    assert ir.record_layout(ef, root)["bytes"] == 24
    assert ef.section_copies.count("CPYREC") == 1 and {"DFHAID", "NOTHERE"} <= set(ef.section_copies)


def test_a_first_unresolved_member_stays_a_gap_of_the_entry(ir):
    # the reader does not guess: the first member stays (the layout reports it unexpanded)
    ef, root = _root(ir, "WS-GAP")
    assert root.copy_members == "NOTHERE,CPYAREA"
    assert ir.record_layout(ef, root)["bytes"] is None
