"""#4266 follow-up: SYNCHRONIZED slack bytes between the occurrences of a table.

IBM Enterprise COBOL, "Slack bytes within records" (SYNCHRONIZED clause):
https://www.ibm.com/docs/en/cobol-zos/6.4?topic=clause-slack-bytes-within-records
For a group with OCCURS that holds aligned items, the compiler takes the group's size (with the slack
inside it), divides by the largest boundary m any elementary item in it needs, and when the remainder r
is not zero adds m - r slack bytes at the end of each occurrence, so every occurrence begins at the same
relative position as the first. The slack is part of the group's length.
"""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SYNCTAB.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  TBL.
           05  T-HEAD              PIC X.
           05  T-ROW               OCCURS 3.
               10  R-FLAG          PIC X.
               10  R-FLT           COMP-2 SYNC.
               10  R-CODE          PIC X(3).
           05  T-TAIL              PIC X.
       01  HALVES.
           05  H-ROW               OCCURS 2.
               10  H-NUM           PIC S9(4) COMP SYNC.
               10  H-CH            PIC X.
       01  PLAIN.
           05  P-ROW               OCCURS 3.
               10  P-FLAG          PIC X.
               10  P-FLT           COMP-2.
               10  P-CODE          PIC X(3).
       PROCEDURE DIVISION.
           GOBACK.
"""


@pytest.fixture(scope="module")
def ir(tmp_path_factory):
    base = tmp_path_factory.mktemp("sync_table_4266")
    (base / "repo").mkdir()
    (base / "repo" / "SYNCTAB.cbl").write_text(PROGRAM, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(base / "repo", base / "scan"))


def _layout(ir, name):
    ef = ir.files["SYNCTAB.cbl"]
    return ir.record_layout(ef, next(it for it in ef.records if it.name == name))


def _fields(layout):
    return [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]]


def test_an_occurrence_is_padded_to_the_largest_boundary_in_it(ir):
    layout = _layout(ir, "TBL")
    # one occurrence: R-FLAG at 1, 6 slack, R-FLT at 8, R-CODE at 16 -> 18 bytes, padded to 24 (m = 8)
    assert _fields(layout) == [
        ("T-HEAD", 0, 1), ("R-FLAG", 1, 1), ("R-FLT", 8, 8), ("R-CODE", 16, 3), ("T-TAIL", 73, 1)]  # fmt: skip
    assert layout["bytes"] == 74  # 56 before the slack between occurrences


def test_a_halfword_table_is_padded_to_two(ir):
    layout = _layout(ir, "HALVES")
    assert _fields(layout) == [("H-NUM", 0, 2), ("H-CH", 2, 1)]  # 3 bytes an occurrence, padded to 4
    assert layout["bytes"] == 8


def test_a_table_without_sync_is_not_padded(ir):
    assert _layout(ir, "PLAIN")["bytes"] == 3 * 12


def test_storage_spans_agree_with_the_layout(ir):
    ef = ir.files["SYNCTAB.cbl"]
    spans = ir._storage_spans(ef)
    items = {it.name: it for it in ef.data_items}
    root = next(it for it in ef.records if it.name == "TBL")
    assert spans[id(root)][2] == 74
    row = spans[id(items["T-ROW"])]
    assert (row[1], row[2], row[3]) == (1, 72, 24)  # one occurrence is 24 bytes
    assert spans[id(items["R-FLT"])][1] == 8
    assert spans[id(items["T-TAIL"])][1] == 73
    assert spans[id(next(it for it in ef.records if it.name == "HALVES"))][2] == 8
