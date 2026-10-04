"""#4278 / #4279: where a COPY / EXEC SQL INCLUDE member lands in `record_layout`.

#4278: `EXEC SQL INCLUDE member END-EXEC` inside a record expands like COPY, and a member
that does not resolve is reported in `unexpanded` (bytes unknown) instead of being skipped
while the fields after it silently sit early.
#4279: a COPY recorded after the LAST entry deep inside a group child (an 88 under a 05, or a
15 FILLER under 05/10) whose roots are no deeper than that child closes it. The entries after
the COPY used to be threaded under the open group AND handed to the copied record -- counted
twice (carddemo COUSR02C / COTRN02C / COPAUS0C).

Each shape is one the det-port estates carry; the expected sizes are the det translator's.
One real galaxyscope scan backs every test (as test_commarea_contracts.py does).
"""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

# carddemo CSDB2RWY: `05`-level roots.
ROWS = """\
          05  WS-DB2-COMMON-VARS.
              10 WS-DISP-SQLCODE        PIC X(5).
              10 WS-DB2-CURRENT-ACTION  PIC X(72).
"""

# GenApp LGCMAREA: `03`-level roots of DFHCOMMAREA.
AREA = """\
           03 CA-REQUEST-ID            PIC X(6).
           03 CA-RETURN-CODE           PIC 9(2).
"""

# carddemo COCOM01Y: an 01-level record the program continues.
COMM = """\
       01 COMM-AREA.
          05 COMM-FROM-PGM             PIC X(8).
"""

PROG = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROGA.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
      * carddemo COTRTLIC.cbl:304 -- INCLUDE of 05 roots after a 15 FILLER.
       01  WS-INC.
         05 WS-A.
           10 WS-B.
             15 FILLER                PIC X(1) VALUE ')'.
           EXEC SQL INCLUDE ROWS END-EXEC
         05 WS-AFTER                  PIC X(2).
      * The same shape through COPY.
       01  WS-CPY.
         05 WS-C.
           10 WS-D.
             15 FILLER                PIC X(1) VALUE ')'.
           COPY ROWS.
         05 WS-AFTER2                 PIC X(2).
      * carddemo COUSR02C.cbl:35-49 -- an 01-level COPY after a 05's 88s.
       01  WS-VARIABLES.
         05 WS-PGMNAME                PIC X(8).
         05 WS-FLAG                   PIC X(1).
           88 FLAG-ON                 VALUE 'Y'.
           88 FLAG-OFF                VALUE 'N'.
       COPY COMM.
          05 COMM-PROG-INFO.
             10 COMM-PAGE             PIC 9(8).
      * A runtime member closes the record above it.
       01  DB2-IN-INTEGERS.
           03 DB2-CUST                PIC S9(9) COMP.
           EXEC SQL
             INCLUDE SQLCA
           END-EXEC.
      * A member not in the repository is a gap, not a silent skip.
       01  WS-MISSING.
           03 WS-M1                   PIC X(3).
           EXEC SQL INCLUDE NOSUCH END-EXEC.
           03 WS-M2                   PIC X(3).
       LINKAGE SECTION.
      * GenApp lgdpdb01.cbl:99 -- `01 DFHCOMMAREA.` + EXEC SQL INCLUDE.
       01  DFHCOMMAREA.
           EXEC SQL
             INCLUDE AREA
           END-EXEC.
       PROCEDURE DIVISION.
           GOBACK.
"""


@pytest.fixture(scope="module")
def layouts(tmp_path_factory):
    base = tmp_path_factory.mktemp("layout4278")
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "cpy").mkdir()
    (repo / "src" / "PROGA.cbl").write_text(PROG)
    (repo / "cpy" / "ROWS.cpy").write_text(ROWS)
    (repo / "cpy" / "AREA.cpy").write_text(AREA)
    (repo / "cpy" / "COMM.cpy").write_text(COMM)
    ir = load_galaxy_ir(scan_to_db(repo, base / "scan"))
    ef = ir.files["src/PROGA.cbl"]
    out = {it.name: ir.record_layout(ef, it) for it in ef.records if it.level == 1}
    # The copied record, continued in the program (`_find_item` -> `_copy_extension`).
    ((owner, comm, ext),) = ir._find_item(ef, "COMM-AREA", None)
    out["COMM-AREA"] = ir.record_layout(owner, comm, ext)
    return out


def _fields(layout):
    return [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]]


def test_sql_include_after_a_deep_filler_lands_at_its_roots_level(layouts):
    assert _fields(layouts["WS-INC"]) == [
        ("FILLER", 0, 1),
        ("WS-DISP-SQLCODE", 1, 5),
        ("WS-DB2-CURRENT-ACTION", 6, 72),
        ("WS-AFTER", 78, 2),
    ]
    assert layouts["WS-INC"]["bytes"] == 80
    assert layouts["WS-INC"]["unexpanded"] == []


def test_copy_after_a_deep_filler_lands_the_same_way(layouts):
    assert layouts["WS-CPY"]["bytes"] == 80
    assert [n for n, _, _ in _fields(layouts["WS-CPY"])][-1] == "WS-AFTER2"


def test_entries_continuing_a_copied_record_are_counted_once(layouts):
    # Before: WS-VARIABLES also took COMM-PROG-INFO (9 + 8 = 17 bytes).
    assert _fields(layouts["WS-VARIABLES"]) == [("WS-PGMNAME", 0, 8), ("WS-FLAG", 8, 1)]
    assert layouts["WS-VARIABLES"]["bytes"] == 9
    assert _fields(layouts["COMM-AREA"]) == [("COMM-FROM-PGM", 0, 8), ("COMM-PAGE", 8, 8)]


def test_sql_include_is_the_dfhcommarea_layout(layouts):
    assert _fields(layouts["DFHCOMMAREA"]) == [("CA-REQUEST-ID", 0, 6), ("CA-RETURN-CODE", 6, 2)]
    assert layouts["DFHCOMMAREA"]["bytes"] == 8


def test_a_runtime_member_closes_the_record_above_it(layouts):
    assert layouts["DB2-IN-INTEGERS"]["bytes"] == 4
    assert layouts["DB2-IN-INTEGERS"]["unexpanded"] == []


def test_an_unresolved_member_is_reported_not_skipped(layouts):
    assert layouts["WS-MISSING"]["unexpanded"] == ["NOSUCH"]
    assert layouts["WS-MISSING"]["bytes"] is None
