"""
#3344: sql_table_data -- DB2 `EXEC SQL DECLARE <table> TABLE (...)` columns in
the master DB.

These pin the properties the design turns on:
  1. Columns ride on each file's own `sql_tables` payload (a per-file fact, like
     record_layouts), and every column becomes a row with its full shape.
  2. The table cascade-deletes with file_data, so a re-record of the same
     snapshot does not accumulate duplicate rows.
  3. A delta scan restores an unchanged file's columns byte-identically, and a
     baseline written before the table existed restores nothing (no error).
"""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "db2344", "latest_commit_date": "2026-09-23T00:00:00Z"},
}

# CBSA's ACCDB2.cpy shape (first three columns) as the extractor emits it.
ACCDB2_COLUMNS = [
    {
        "table": "ACCOUNT",
        "table_line": 7,
        "colno": 1,
        "name": "ACCOUNT_EYECATCHER",
        "sql_type": "CHAR",
        "length": 4,
        "scale": None,
        "nullable": True,
        "attributes": None,
        "line": 8,
    },
    {
        "table": "ACCOUNT",
        "table_line": 7,
        "colno": 2,
        "name": "ACCOUNT_SORTCODE",
        "sql_type": "CHAR",
        "length": 6,
        "scale": None,
        "nullable": False,
        "attributes": "NOT NULL",
        "line": 10,
    },
    {
        "table": "ACCOUNT",
        "table_line": 7,
        "colno": 3,
        "name": "ACCOUNT_INTEREST_RATE",
        "sql_type": "DECIMAL",
        "length": 4,
        "scale": 2,
        "nullable": True,
        "attributes": None,
        "line": 13,
    },
]

UNIVERSE = [
    {"path": "src/base/cobol_copy/ACCDB2.cpy", "lang_id": "cobol", "raw_imports": [], "sql_tables": ACCDB2_COLUMNS},
    {"path": "src/base/cobol_copy/EMPTY.cpy", "lang_id": "cobol", "raw_imports": []},
]


def _record(db):
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_every_column_becomes_a_row_with_its_shape(tmp_path):
    db = _record(tmp_path / "m.db")
    rows = _rows(
        db,
        """
        SELECT table_name, table_line, colno, column_name, sql_type, length, scale, nullable, attributes, line_number
        FROM sql_table_data st JOIN file_data f ON st.file_id = f.id
        WHERE f.file_path = 'src/base/cobol_copy/ACCDB2.cpy' ORDER BY st.colno
        """,
    )
    assert rows == [
        ("ACCOUNT", 7, 1, "ACCOUNT_EYECATCHER", "CHAR", 4, None, 1, None, 8),
        ("ACCOUNT", 7, 2, "ACCOUNT_SORTCODE", "CHAR", 6, None, 0, "NOT NULL", 10),
        ("ACCOUNT", 7, 3, "ACCOUNT_INTEREST_RATE", "DECIMAL", 4, 2, 1, None, 13),
    ]


def test_a_file_with_no_declarations_records_none(tmp_path):
    db = _record(tmp_path / "m.db")
    (count,) = _rows(
        db,
        "SELECT COUNT(*) FROM sql_table_data st JOIN file_data f ON st.file_id = f.id "
        "WHERE f.file_path = 'src/base/cobol_copy/EMPTY.cpy'",
    )[0]
    assert count == 0


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "m.db"
    _record(db)
    _record(db)
    (total,) = _rows(db, "SELECT COUNT(*) FROM sql_table_data")[0]
    assert total == 3


def test_an_unchanged_file_keeps_its_columns_through_a_delta_scan(tmp_path):
    """Restored payload == extracted payload, so a full and an incremental scan write
    the same sql_table_data rows (the fact-channel byte-identical rule)."""
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["src/base/cobol_copy/ACCDB2.cpy"]["sql_tables"] == ACCDB2_COLUMNS
    assert cache["src/base/cobol_copy/EMPTY.cpy"]["sql_tables"] == []

    # Re-record from the restored payload (what an incremental scan does for an
    # unchanged file): identical rows, excluding the autoincrement id.
    select = (
        "SELECT f.file_path, table_name, table_line, colno, column_name, sql_type, length, scale, nullable, "
        "attributes, line_number FROM sql_table_data st JOIN file_data f ON st.file_id = f.id ORDER BY 1, 4"
    )
    full = _rows(db, select)
    delta_db = tmp_path / "delta.db"
    restored = [dict(node, path=path) for path, node in cache.items()]
    RecordKeeper().record_mission(restored, [], {}, SESSION, str(delta_db))
    assert _rows(delta_db, select) == full


def test_a_pre_3344_baseline_rehydrates_with_no_columns(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE sql_table_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["src/base/cobol_copy/ACCDB2.cpy"]["sql_tables"] == []
