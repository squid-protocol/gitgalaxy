"""#3446: sql_statement_data -- embedded SQL statements in the master DB: one row
per (statement, table), cascade with file_data, byte-identical delta restore, and
a pre-#3446 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "sql3446", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
STMTS = [
    {
        "ordinal": 1,
        "verb": "DECLARE CURSOR",
        "table": "ACCOUNT",
        "access": "read",
        "cursor": "ACC-CURSOR",
        "host_variables": "HV-SORT",
        "line": 66,
        "statement": "DECLARE ACC-CURSOR CURSOR FOR SELECT * FROM ACCOUNT ORDER BY :HV-SORT",  # #3618
    },
    {
        "ordinal": 2,
        "verb": "OPEN",
        "table": None,
        "access": None,
        "cursor": "ACC-CURSOR",
        "host_variables": None,
        "line": 270,
        "statement": "OPEN ACC-CURSOR",
    },
    {
        "ordinal": 3,
        "verb": "INSERT",
        "table": "PROCTRAN",
        "access": "insert",
        "cursor": None,
        "host_variables": "HV-A,HV-B",
        "line": 900,
        "statement": "INSERT INTO PROCTRAN VALUES (:HV-A, :HV-B)",
    },
]
UNIVERSE = [
    {"path": "src/INQACC.cbl", "lang_id": "cobol", "raw_imports": [], "sql_statements": STMTS},
    {"path": "src/PLAIN.cbl", "lang_id": "cobol", "raw_imports": []},
]
SELECT = (
    "SELECT f.file_path, stmt_ordinal, verb, table_name, access, cursor_name, host_variables, line_number "
    "FROM sql_statement_data s JOIN file_data f ON s.file_id = f.id ORDER BY 1, 2, s.id"
)


def _record(db):
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_every_statement_row_is_recorded(tmp_path):
    assert _rows(_record(tmp_path / "m.db"), SELECT) == [
        ("src/INQACC.cbl", 1, "DECLARE CURSOR", "ACCOUNT", "read", "ACC-CURSOR", "HV-SORT", 66),
        ("src/INQACC.cbl", 2, "OPEN", None, None, "ACC-CURSOR", None, 270),
        ("src/INQACC.cbl", 3, "INSERT", "PROCTRAN", "insert", None, "HV-A,HV-B", 900),
    ]


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "m.db"
    _record(db)
    _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM sql_statement_data")[0][0] == 3


def test_an_unchanged_file_keeps_its_statements_through_a_delta_scan(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["src/INQACC.cbl"]["sql_statements"] == STMTS
    assert cache["src/PLAIN.cbl"]["sql_statements"] == []
    delta_db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, SESSION, str(delta_db))
    assert _rows(delta_db, SELECT) == _rows(db, SELECT)


def test_a_pre_3446_baseline_rehydrates_with_no_statements(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE sql_statement_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["src/INQACC.cbl"]["sql_statements"] == []
