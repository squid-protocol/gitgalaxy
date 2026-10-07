"""#4266: SYNCHRONIZED, JUSTIFIED, BLANK WHEN ZERO and 66 RENAMES in the layout model.

The extractor had no handling of any of them: a SYNC binary item was laid out with no slack bytes
before it, so every offset after it (and the record's length) was short, and a 66 RENAMES entry
was attached to the item above it with no storage. Now:
- the COBOL record extractor records `sync`, `justified`, `blank_when_zero` and a 66 entry's
  `renames` (presence-keyed, like sign_separate);
- record_data carries them as columns, healed into old tables; the rehydrator restores them;
- GalaxyIR puts slack bytes before a SYNC item (record_layout and the storage spans: IBM Enterprise
  COBOL's SYNCHRONIZED clause, the record doubleword-aligned), and lays a RENAMES entry out as the
  byte range it names, so a MOVE from / to it resolves in data_flows like any other item.
A DB written before the columns existed still loads, with no slack bytes and no RENAMES ranges.
"""

import shutil
import sqlite3

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SYNCREN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  UNSYNCED.
           05  U-FLAG              PIC X.
           05  U-HALF              PIC S9(4) COMP.
           05  U-NAME              PIC X(3).
           05  U-FULL              PIC S9(9) COMP.
           05  U-DBL               PIC S9(18) COMP.
           05  U-FLT               COMP-2.
       01  SYNCED.
           05  S-FLAG              PIC X.
           05  S-HALF              PIC S9(4) COMP SYNC.
           05  S-NAME              PIC X(3).
           05  S-FULL              PIC S9(9) BINARY SYNCHRONIZED LEFT.
           05  S-DBL               PIC S9(18) COMP-5 Sync.
           05  S-FLT               COMP-2 SYNC.
           05  S-TEXT              PIC X(3) SYNC.
           05  S-LAST              PIC 9.
       01  NESTED                  COMP.
           05  N-A                 PIC XX DISPLAY.
           05  N-GRP.
               10  N-B             PIC X DISPLAY.
               10  N-C             PIC S9(4) SYNC.
                   88  N-C-ZERO    VALUE 0.
       01  WS-SYNC-FLAG            PIC X VALUE 'SYNC'.
       01  CUSTOMER.
           05  CUST-ID             PIC X(6) JUSTIFIED RIGHT.
           05  CUST-NAME           PIC X(10) JUST.
           05  CUST-BAL            PIC 9(5) BLANK WHEN ZERO.
           05  CUST-LIMIT          PIC 9(5) BLANK ZEROES.
           05  CUST-ZIP            PIC X(5).
       66  CUST-KEY                RENAMES CUST-ID THRU CUST-NAME.
       66  CUST-AMOUNTS            RENAMES CUST-BAL THROUGH CUST-LIMIT.
       66  CUST-POSTAL             RENAMES CUST-ZIP IN CUSTOMER.
       01  WS-KEY                  PIC X(16).
       01  WS-AMOUNTS              PIC X(10).
       PROCEDURE DIVISION.
           MOVE CUST-KEY TO WS-KEY.
           MOVE WS-AMOUNTS TO CUST-AMOUNTS.
           MOVE CUST-POSTAL OF CUSTOMER TO WS-KEY.
           GOBACK.
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("sync_renames_4266")
    (base / "repo").mkdir()
    (base / "repo" / "SYNCREN.cbl").write_text(PROGRAM, encoding="utf-8")
    return scan_to_db(base / "repo", base / "scan")


def _rows():
    return {r["name"]: r for r in extract_boundary("cobol", PROGRAM)["records"]}


def test_the_extractor_records_the_clauses():
    rows = _rows()
    assert rows["S-HALF"]["sync"] == "SYNC"
    assert rows["S-FULL"]["sync"] == "SYNC LEFT"
    assert rows["S-DBL"]["sync"] == "SYNC"  # lower case, and the period right after the clause
    assert rows["S-FLT"]["sync"] == "SYNC"
    assert rows["N-C"]["sync"] == "SYNC"
    assert rows["CUST-ID"]["justified"] is True and rows["CUST-NAME"]["justified"] is True
    assert rows["CUST-BAL"]["blank_when_zero"] is True and rows["CUST-LIMIT"]["blank_when_zero"] is True
    # presence-keyed: an entry without a clause keeps its pre-#4266 shape
    for name in ("U-HALF", "S-FLAG", "WS-SYNC-FLAG", "CUST-ZIP"):
        assert not {"sync", "justified", "blank_when_zero", "renames"} & set(rows[name]), name


def test_the_extractor_records_renames_ranges():
    rows = _rows()
    assert rows["CUST-KEY"]["renames"] == "CUST-ID THRU CUST-NAME"
    assert rows["CUST-AMOUNTS"]["renames"] == "CUST-BAL THRU CUST-LIMIT"  # THROUGH spelled THRU
    assert rows["CUST-POSTAL"]["renames"] == "CUST-ZIP OF CUSTOMER"  # IN read as OF
    assert rows["CUST-KEY"]["redefines"] is None  # RENAMES is not a REDEFINES


def _layout(ir, name):
    ef = ir.files["SYNCREN.cbl"]
    return ir.record_layout(ef, next(it for it in ef.records if it.name == name))


def _fields(layout):
    return [(f["name"], f["offset"], f["bytes"]) for f in layout["fields"]]


def test_an_unsynced_record_has_no_slack(scanned):
    layout = _layout(load_galaxy_ir(scanned), "UNSYNCED")
    assert _fields(layout) == [
        ("U-FLAG", 0, 1), ("U-HALF", 1, 2), ("U-NAME", 3, 3), ("U-FULL", 6, 4), ("U-DBL", 10, 8), ("U-FLT", 18, 8)]  # fmt: skip
    assert layout["bytes"] == 26


def test_a_synced_record_takes_its_slack_bytes(scanned):
    layout = _layout(load_galaxy_ir(scanned), "SYNCED")
    assert _fields(layout) == [
        ("S-FLAG", 0, 1),
        ("S-HALF", 2, 2),  # halfword: 1 slack byte
        ("S-NAME", 4, 3),
        ("S-FULL", 8, 4),  # fullword: 1 slack byte
        ("S-DBL", 12, 8),  # an 8-byte binary is fullword-aligned (IBM): none
        ("S-FLT", 24, 8),  # COMP-2 is doubleword-aligned: 4 slack bytes
        ("S-TEXT", 32, 3),  # SYNC on a DISPLAY item adds none
        ("S-LAST", 35, 1),
    ]
    assert layout["bytes"] == 36  # 30 without the slack: the synced record is longer


def test_slack_is_counted_from_the_record_and_inside_the_group(scanned):
    ir = load_galaxy_ir(scanned)
    layout = _layout(ir, "NESTED")
    assert _fields(layout) == [("N-A", 0, 2), ("N-B", 2, 1), ("N-C", 4, 2)]  # N-C's usage is NESTED's COMP
    assert layout["bytes"] == 6
    ef = ir.files["SYNCREN.cbl"]
    spans = ir._storage_spans(ef)
    grp = next(it for it in ef.data_items if it.name == "N-GRP")
    assert spans[id(grp)][1:3] == (2, 4)  # the slack byte belongs to the group holding the item


def test_storage_spans_agree_with_the_layout(scanned):
    ir = load_galaxy_ir(scanned)
    ef = ir.files["SYNCREN.cbl"]
    spans = ir._storage_spans(ef)
    for name, size in (("UNSYNCED", 26), ("SYNCED", 36), ("NESTED", 6), ("CUSTOMER", 31)):
        root = next(it for it in ef.records if it.name == name)
        assert spans[id(root)][2] == size, name
    for name, offset in (("S-HALF", 2), ("S-FULL", 8), ("S-DBL", 12), ("S-FLT", 24), ("S-LAST", 35)):
        item = next(it for it in ef.data_items if it.name == name)
        assert spans[id(item)][1] == offset, name


def test_the_ir_keeps_the_clauses(scanned):
    ef = load_galaxy_ir(scanned).files["SYNCREN.cbl"]
    items = {it.name: it for it in ef.data_items}
    assert items["S-FULL"].sync == "SYNC LEFT" and items["U-FULL"].sync is None
    assert items["CUST-ID"].justified and not items["CUST-ZIP"].justified
    assert items["CUST-BAL"].blank_when_zero and not items["CUST-ID"].blank_when_zero
    assert items["CUST-KEY"].renames == "CUST-ID THRU CUST-NAME"


def test_renames_entries_are_byte_ranges(scanned):
    ir = load_galaxy_ir(scanned)
    ef = ir.files["SYNCREN.cbl"]
    spans = ir._storage_spans(ef)
    items = {it.name: it for it in ef.data_items}
    assert spans[id(items["CUST-KEY"])][1:3] == (0, 16)  # CUST-ID (6) through CUST-NAME (10)
    assert spans[id(items["CUST-AMOUNTS"])][1:3] == (16, 10)
    assert spans[id(items["CUST-POSTAL"])][1:3] == (26, 5)
    assert spans[id(items["CUST-KEY"])][0] == spans[id(items["CUSTOMER"])][0]  # in the record it follows


def test_a_move_through_a_renames_entry_resolves(scanned):
    flows = {(f["source"], f["target"]): f for f in load_galaxy_ir(scanned).data_flows()}
    key = flows[("CUST-KEY", "WS-KEY")]
    assert key["status"] == "resolved"
    assert (key["source_span"]["record"], key["source_span"]["offset"], key["source_span"]["bytes"]) == (
        "CUSTOMER", 0, 16)  # fmt: skip
    assert key["truncates"] is False
    amounts = flows[("WS-AMOUNTS", "CUST-AMOUNTS")]
    assert amounts["status"] == "resolved"
    assert (amounts["target_span"]["offset"], amounts["target_span"]["bytes"]) == (16, 10)
    postal = flows[("CUST-POSTAL OF CUSTOMER", "WS-KEY")]  # qualified by its record
    assert postal["status"] == "resolved"
    assert (postal["source_span"]["offset"], postal["source_span"]["bytes"]) == (26, 5)


def test_a_pre_4266_db_loads_with_no_slack_and_no_renames(scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(scanned, old)
    with sqlite3.connect(old) as conn:
        for column in ("sync", "justified", "blank_when_zero", "renames"):
            conn.execute(f"ALTER TABLE record_data DROP COLUMN {column}")
    ir = load_galaxy_ir(old)
    assert _layout(ir, "SYNCED")["bytes"] == 30
    ef = ir.files["SYNCREN.cbl"]
    key = next(it for it in ef.data_items if it.name == "CUST-KEY")
    assert key.renames is None and id(key) not in ir._storage_spans(ef)
