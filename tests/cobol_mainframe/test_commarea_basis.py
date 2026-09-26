"""#3688: which layout a CICS program's COMMAREA is built from.

A resolved caller's record used to outrank the program's own LINKAGE DFHCOMMAREA
unconditionally. That is right for CardDemo's opaque `PIC X OCCURS ... DEPENDING ON
EIBCALEN` areas, and wrong when the program declares a CONCRETE layout the callers
disagree with (CBSA BNK1UAC / UPDACC) or pass at an unknown width (GENAPP lg*vs01). Now:

- the caller record matches the declaration  -> caller_record (unchanged);
- it is a coarser view of it (same bytes, some  -> the declaration, no conflict
  fields kept as one PIC X block)
- it disagrees (length / field shape)           -> the declaration + a conflict per caller
- its width is unknown                          -> the declaration + a conflict per caller
- the declaration is opaque or a coarser view   -> caller_record (unchanged)
"""

import json
import shutil
import sys
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import commarea_alternative_todos


def _callee(name: str, linkage: str) -> str:
    return f"""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. {name}.
       DATA DIVISION.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
{linkage}       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""


def _caller(name: str, target: str, storage: str, record: str, section: str = "WORKING-STORAGE") -> str:
    return f"""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. {name}.
       DATA DIVISION.
       {section} SECTION.
{storage}       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS LINK PROGRAM('{target}') COMMAREA({record}) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


DECLARED = """\
           05 LK-ID           PIC 9(4).
           05 LK-NAME         PIC X(4).
           05 LK-CODE         PIC X(4).
"""  # 12 bytes, 3 fields

FILES = {
    # the caller's record matches the declaration field for field
    "cbl/MATCHED.cbl": _callee("MATCHED", DECLARED),
    "cbl/CMATCH.cbl": _caller("CMATCH", "MATCHED", "       01  WS-M.\n           05 M-ID    PIC 9(4).\n"
                              "           05 M-NAME  PIC X(4).\n           05 M-CODE  PIC X(4).\n", "WS-M"),
    # the caller passes a shorter record: a conflict
    "cbl/CLASH.cbl": _callee("CLASH", DECLARED),
    "cbl/CCLASH.cbl": _caller("CCLASH", "CLASH", "       01  WS-S.\n           05 S-ID    PIC 9(4).\n"
                              "           05 S-NAME  PIC X(6).\n", "WS-S"),
    # the caller keeps the name + code as one 8-byte block: compatible
    "cbl/COARSE.cbl": _callee("COARSE", DECLARED),
    "cbl/CCOARSE.cbl": _caller("CCOARSE", "COARSE", "       01  WS-C.\n           05 C-ID    PIC 9(4).\n"
                               "           05 C-REST  PIC X(8).\n", "WS-C"),
    # the callee declares the coarser view; the caller's finer layout stands
    "cbl/FINE.cbl": _callee("FINE", "           05 F-ID    PIC 9(4).\n           05 F-REST  PIC X(8).\n"),
    "cbl/CFINE.cbl": _caller("CFINE", "FINE", "       01  WS-F.\n           05 G-ID    PIC 9(4).\n"
                             "           05 G-NAME  PIC X(4).\n           05 G-CODE  PIC X(4).\n", "WS-F"),
    # the caller passes its own variable-length area: width unknown
    "cbl/UNKNOWN.cbl": _callee("UNKNOWN", DECLARED),
    "cbl/CUNKNOWN.cbl": _caller("CUNKNOWN", "UNKNOWN", "       01  DFHCOMMAREA.\n           05 U-BYTE  PIC X OCCURS 1 TO 100\n"
                                "                              DEPENDING ON EIBCALEN.\n", "DFHCOMMAREA", "LINKAGE"),
    # an opaque declaration: the callers define the layout
    "cbl/OPAQUE.cbl": _callee("OPAQUE", "           05 O-BYTE  PIC X OCCURS 1 TO 32767\n"
                              "                         DEPENDING ON EIBCALEN.\n"),
    "cbl/COPAQUE.cbl": _caller("COPAQUE", "OPAQUE", "       01  WS-O.\n           05 O-ID    PIC 9(4).\n"
                               "           05 O-NAME  PIC X(6).\n", "WS-O"),
}  # fmt: skip


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("commarea_basis")
    repo = base / "estate"
    for rel, text in FILES.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


@pytest.fixture(scope="module")
def interfaces(scanned):
    return load_galaxy_ir(scanned[1]).program_interfaces()


def _basis(interfaces, prog):
    ca = interfaces[f"cbl/{prog}.cbl"]["commarea"]
    return ca["basis"], ca["record"], ca["bytes"]


def test_a_matching_caller_record_stands(interfaces):
    assert _basis(interfaces, "MATCHED") == ("caller_record", "WS-M", 12)


def test_a_disagreeing_caller_yields_to_the_declaration_as_a_conflict(interfaces):
    ca = interfaces["cbl/CLASH.cbl"]["commarea"]
    assert (ca["basis"], ca["record"], ca["bytes"]) == ("dfhcommarea", "DFHCOMMAREA", 12)
    (alt,) = ca["alternatives"]
    assert (alt["record"], alt["bytes"]) == ("WS-S", 10)
    assert [m["kind"] for m in alt["mismatches"]] == ["length", "shape"]
    assert ca["sources"][0]["caller"] == "cbl/CCLASH.cbl"  # the site is still named


def test_a_coarser_caller_view_is_compatible(interfaces):
    ca = interfaces["cbl/COARSE.cbl"]["commarea"]
    assert (ca["basis"], ca["bytes"]) == ("dfhcommarea", 12)  # the declaration has the detail
    assert ca["alternatives"][0] | {"sources": None} == {"record": "WS-C", "file": "cbl/CCOARSE.cbl", "bytes": 12,
                                                         "sources": None, "mismatches": [], "view": "coarser"}  # fmt: skip
    assert commarea_alternative_todos(ca) == []  # nothing to settle


def test_a_coarser_declaration_keeps_the_finer_caller_record(interfaces):
    assert _basis(interfaces, "FINE") == ("caller_record", "WS-F", 12)


def test_a_caller_of_unknown_width_yields_to_the_declaration(interfaces):
    ca = interfaces["cbl/UNKNOWN.cbl"]["commarea"]
    assert (ca["basis"], ca["bytes"]) == ("dfhcommarea", 12)
    (todo,) = commarea_alternative_todos(ca)
    assert "has no known width" in todo and "declared DFHCOMMAREA (12 bytes) is used" in todo


def test_an_opaque_declaration_leaves_the_callers_record(interfaces):
    assert _basis(interfaces, "OPAQUE") == ("caller_record", "WS-O", 10)


def test_the_java_and_the_worklist_carry_the_conflict(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    src = java / "src/main/java/com/gitgalaxy/modernized"
    clash = (src / "controller/ClashController.java").read_text(encoding="utf-8")
    assert "disagrees with this program's declared DFHCOMMAREA (12 bytes: 10 vs 12 bytes;" in clash
    coarse = (src / "controller/CoarseController.java").read_text(encoding="utf-8")
    assert "TODO" not in coarse.split("@RestController")[0]  # compatible: no conflict in the class doc
    ccoarse = (src / "service/CcoarseService.java").read_text(encoding="utf-8")
    assert "this site passes" not in ccoarse  # nor at the call site
    worklist = json.loads((java / "migration_worklist.json").read_text(encoding="utf-8"))
    kinds = {(i["category"], i["program"]) for i in worklist["items"] if i["file"].endswith("Controller.java")}
    assert ("commarea-mismatch", "cbl/CLASH.cbl") in kinds  # a conflict for a person to settle
    assert ("missing-layout", "cbl/UNKNOWN.cbl") in kinds  # the caller's width is the missing fact
