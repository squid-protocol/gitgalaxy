"""
#3347: screen_field_data -- BMS mapset/map/field layouts in the master DB.

These pin the properties the design turns on:
  1. Screen fields ride on each file's own `screen_fields` payload (a per-file
     fact, like record_layouts), and every macro statement becomes a row.
  2. The tree survives the round trip: `ordinal`/`parent_ordinal` are stored as
     given, so a reader rebuilds mapset -> map -> field.
  3. The table cascade-deletes with file_data, so a re-record of the same
     snapshot does not accumulate duplicate rows.
  4. A delta scan restores an unchanged map's rows exactly (#3246's rule).
"""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.audit_recorder import AuditRecorder
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "cb0101", "latest_commit_date": "2026-09-20T00:00:00Z"},
}


def _row(kind, ordinal, parent, name, line, **cols):
    base = {
        "kind": kind,
        "ordinal": ordinal,
        "parent_ordinal": parent,
        "name": name,
        "pos_line": None,
        "pos_column": None,
        "length": None,
        "attrb": None,
        "picin": None,
        "picout": None,
        "initial": None,
        "occurs": None,
        "attributes": None,
        "line": line,
    }
    base.update(cols)
    return base


# cics-banking-sample-application-cbsa BNK1ACC.bms, abridged, as the extractor
# emits it: a mapset, one map, an unnamed literal, an OCCURS field and a PICOUT one.
MAP_FILE = {
    "path": "bms_src/BNK1ACC.bms",
    "lang_id": "bms",
    "raw_imports": [],
    "screen_fields": [
        _row("mapset", 0, None, "BNK1ACC", 20, attributes="TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL"),
        _row("map", 1, 0, "BNK1AC", 24, attributes="SIZE=(24,80),COLUMN=1,LINE=1"),
        _row("field", 2, 1, None, 26, pos_line=1, pos_column=1, length=7, attrb="PROT,NORM", initial="BNK1AC "),
        _row(
            "field",
            3,
            1,
            "ACCOUNT",
            47,
            pos_line=9,
            pos_column=1,
            length=79,
            attrb="NORM,PROT,FSET,ASKIP",
            occurs=10,
            attributes="COLOR=NEUTRAL",
        ),
        _row("field", 4, 1, "INTRT", 61, pos_line=11, pos_column=20, length=7, picout="9999.99"),
    ],
}
UNIVERSE = [MAP_FILE, {"path": "COBOL/EMPTY.cbl", "lang_id": "cobol", "raw_imports": []}]


def _record(db, universe=UNIVERSE):
    RecordKeeper().record_mission([dict(f) for f in universe], [], {}, SESSION, str(db))


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_every_statement_becomes_a_row_with_its_columns(tmp_path):
    db = tmp_path / "mainframe.db"
    _record(db)
    rows = _rows(
        db,
        "SELECT kind, field_name, pos_line, pos_column, length, attrb, picout, initial_value, occurs, attributes "
        "FROM screen_field_data sf JOIN file_data f ON sf.file_id = f.id "
        "WHERE f.file_path = 'bms_src/BNK1ACC.bms' ORDER BY sf.ordinal",
    )
    assert rows == [
        ("mapset", "BNK1ACC", None, None, None, None, None, None, None, "TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL"),
        ("map", "BNK1AC", None, None, None, None, None, None, None, "SIZE=(24,80),COLUMN=1,LINE=1"),
        ("field", None, 1, 1, 7, "PROT,NORM", None, "BNK1AC ", None, None),
        ("field", "ACCOUNT", 9, 1, 79, "NORM,PROT,FSET,ASKIP", None, None, 10, "COLOR=NEUTRAL"),
        ("field", "INTRT", 11, 20, 7, None, "9999.99", None, None, None),
    ]


def test_parent_ordinal_round_trips_for_the_tree(tmp_path):
    db = tmp_path / "mainframe.db"
    _record(db)
    rows = _rows(db, "SELECT ordinal, parent_ordinal FROM screen_field_data ORDER BY ordinal")
    assert rows == [(0, None), (1, 0), (2, 1), (3, 1), (4, 1)]


def test_a_file_with_no_screen_fields_records_none(tmp_path):
    db = tmp_path / "mainframe.db"
    _record(db)
    (count,) = _rows(
        db,
        "SELECT COUNT(*) FROM screen_field_data sf JOIN file_data f ON sf.file_id = f.id "
        "WHERE f.file_path = 'COBOL/EMPTY.cbl'",
    )[0]
    assert count == 0


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "mainframe.db"
    for _ in range(2):
        _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM screen_field_data")[0][0] == 5


def test_an_unchanged_map_keeps_its_fields_through_a_delta_scan(tmp_path):
    """The rehydrator restores every column under the extractor's own payload keys,
    so a full and an incremental scan write byte-identical rows."""
    db = tmp_path / "mainframe.db"
    _record(db)
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["bms_src/BNK1ACC.bms"]["screen_fields"] == MAP_FILE["screen_fields"]
    assert cache["COBOL/EMPTY.cbl"]["screen_fields"] == []

    # Re-record from the restored payload (what a delta scan does for an
    # unchanged file): the table is identical apart from the autoincrement ids
    # (the row's own and its file_data row's, both redrawn on delete+reinsert).
    before = _rows(db, "SELECT * FROM screen_field_data ORDER BY ordinal")
    restored = [dict(MAP_FILE, screen_fields=cache["bms_src/BNK1ACC.bms"]["screen_fields"]), UNIVERSE[1]]
    _record(db, restored)
    after = _rows(db, "SELECT * FROM screen_field_data ORDER BY ordinal")
    assert [r[1:3] + r[4:] for r in after] == [r[1:3] + r[4:] for r in before]


def test_a_baseline_without_the_table_still_rehydrates(tmp_path):
    db = tmp_path / "mainframe.db"
    _record(db)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE screen_field_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["bms_src/BNK1ACC.bms"]["screen_fields"] == []


def test_the_audit_report_carries_every_row():
    block = AuditRecorder()._mainframe_facts_block(MAP_FILE)
    rows = block["Screen Fields"]
    assert len(rows) == 5
    assert rows[3] == {
        "Kind": "field",
        "Name": "ACCOUNT",
        "POS Line": 9,
        "POS Column": 1,
        "Length": 79,
        "ATTRB": "NORM,PROT,FSET,ASKIP",
        "PICIN": None,
        "PICOUT": None,
        "Initial": None,
        "Occurs": 10,
        "Attributes": "COLOR=NEUTRAL",
        "Ordinal": 3,
        "Parent Ordinal": 1,
        "Line": 47,
    }
    # A file with no screen fields gets no key at all.
    assert "Screen Fields" not in AuditRecorder()._mainframe_facts_block({"path": "x.cbl"})


def test_the_llm_brief_summarises_each_map():
    lines = LLMRecorder()._mainframe_facts_lines([MAP_FILE])
    assert "- **Screen maps:** `BNK1AC (2 named / 3 fields)`" in lines
    assert LLMRecorder()._mainframe_facts_lines([{"path": "x.cbl", "screen_fields": []}]) == []
