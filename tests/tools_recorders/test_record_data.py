"""
#3246: record_data -- the DATA DIVISION item tree + FD record layouts in the
master DB.

These pin the properties the design turns on:
  1. Record layouts ride on each file's own `record_layouts` payload (a per-file
     fact, like dataset_bindings), and every item becomes a row.
  2. The tree survives the round trip: `ordinal`/`parent_ordinal` are stored as
     given, so a reader rebuilds the 01/05/10 nesting.
  3. The table cascade-deletes with file_data, so a re-record of the same
     snapshot does not accumulate duplicate rows.
"""

import sqlite3

from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "cb0101", "latest_commit_date": "2026-09-20T00:00:00Z"},
}

# One program with a small WORKING-STORAGE tree and one FD record, as the
# extractor emits it (flat, source order, parent_ordinal from a level stack).
UNIVERSE = [
    {
        "path": "COBOL/ACCT.cbl",
        "lang_id": "cobol",
        "raw_imports": [],
        "classes": [{"name": "ACCT"}],
        "record_layouts": [
            {
                "section": "FILE",
                "fd_name": "ACCTFILE",
                "ordinal": 0,
                "parent_ordinal": None,
                "level": 1,
                "name": "ACCT-REC",
                "pic": None,
                "usage": None,
                "occurs_min": None,
                "occurs_max": None,
                "occurs_depending_on": None,
                "redefines": None,
                "value": None,
                "line": 10,
            },
            {
                "section": "FILE",
                "fd_name": "ACCTFILE",
                "ordinal": 1,
                "parent_ordinal": 0,
                "level": 5,
                "name": "ACCT-ID",
                "pic": "9(11)",
                "usage": None,
                "occurs_min": None,
                "occurs_max": None,
                "occurs_depending_on": None,
                "redefines": None,
                "value": None,
                "line": 11,
            },
            {
                "section": "WORKING-STORAGE",
                "fd_name": None,
                "ordinal": 2,
                "parent_ordinal": None,
                "level": 1,
                "name": "WS-BAL",
                "pic": "S9(10)V99",
                "usage": "COMP-3",
                "occurs_min": 3,
                "occurs_max": 3,
                "occurs_depending_on": None,
                "redefines": None,
                "value": None,
                "line": 20,
            },
        ],
    },
    {"path": "COPYBOOK/EMPTY.cpy", "lang_id": "cobol", "raw_imports": []},
]


def _record(tmp_path):
    db = tmp_path / "mainframe.db"
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_every_item_becomes_a_row_with_its_clauses(tmp_path):
    db = _record(tmp_path)
    rows = _rows(
        db,
        """
        SELECT item_name, level_number, section, fd_name, pic, usage, occurs_max
        FROM record_data rd JOIN file_data f ON rd.file_id = f.id
        WHERE f.file_path = 'COBOL/ACCT.cbl' ORDER BY rd.ordinal
        """,
    )
    assert rows == [
        ("ACCT-REC", 1, "FILE", "ACCTFILE", None, None, None),
        ("ACCT-ID", 5, "FILE", "ACCTFILE", "9(11)", None, None),
        ("WS-BAL", 1, "WORKING-STORAGE", None, "S9(10)V99", "COMP-3", 3),
    ]


def test_parent_ordinal_round_trips_for_the_tree(tmp_path):
    db = _record(tmp_path)
    rows = _rows(
        db,
        "SELECT item_name, ordinal, parent_ordinal FROM record_data rd "
        "JOIN file_data f ON rd.file_id = f.id WHERE f.file_path = 'COBOL/ACCT.cbl' ORDER BY rd.ordinal",
    )
    parents = {name: parent for name, _o, parent in rows}
    assert parents["ACCT-REC"] is None  # a root
    assert parents["ACCT-ID"] == 0  # under ACCT-REC
    assert parents["WS-BAL"] is None  # a separate root


def test_a_file_with_no_layouts_records_none(tmp_path):
    db = _record(tmp_path)
    (count,) = _rows(
        db,
        "SELECT COUNT(*) FROM record_data rd JOIN file_data f ON rd.file_id = f.id "
        "WHERE f.file_path = 'COPYBOOK/EMPTY.cpy'",
    )[0]
    assert count == 0


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    """The idempotent wipe cascades through file_data's FK, so a second scan of the
    same snapshot leaves exactly one row per item, not two."""
    db = tmp_path / "mainframe.db"
    for _ in range(2):
        RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    (total,) = _rows(db, "SELECT COUNT(*) FROM record_data")[0]
    assert total == 3
