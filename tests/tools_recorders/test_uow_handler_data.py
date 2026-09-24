"""#3453: uow_handler_data -- units of work and error handling in the master DB:
one row per point / handler / check, cascade with file_data, byte-identical delta
restore, and a pre-#3453 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "uow3453", "latest_commit_date": "2026-09-24T00:00:00Z"},
}


def _r(kind, verb, line, **kw):
    row = {"kind": kind, "source": "CICS", "verb": verb, "condition": None, "target": None}
    row.update({"target_kind": None, "resp_var": None, "attributes": None, "line": line})
    row.update(kw)
    return row


ROWS = [
    _r("HANDLE_ABEND", "HANDLE ABEND", 10, target="ABEND-HANDLING", target_kind="LABEL"),
    _r("RESP_CHECK", "READ", 20, condition="NORMAL,NOTFND", resp_var="WS-RESP"),
    _r("ROLLBACK", "SYNCPOINT ROLLBACK", 30),
    _r("COMMIT", "COMMIT WORK", 40, source="SQL"),
    _r("ABEND", "ABEND", 50, condition="HBNK", attributes="NODUMP"),
]
UNIVERSE = [
    {"path": "cbl/CREACC.cbl", "lang_id": "cobol", "raw_imports": [], "uow_handlers": ROWS},
    {"path": "cbl/PLAIN.cbl", "lang_id": "cobol", "raw_imports": []},
]
SELECT = (
    "SELECT f.file_path, kind, source, verb, condition_name, target, target_kind, resp_var, attributes, line_number "
    "FROM uow_handler_data u JOIN file_data f ON u.file_id = f.id ORDER BY 1, u.id"
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


def test_every_row_is_recorded(tmp_path):
    rows = _rows(_record(tmp_path / "m.db"), SELECT)
    assert [(r[1], r[2], r[3], r[4], r[9]) for r in rows] == [
        ("HANDLE_ABEND", "CICS", "HANDLE ABEND", None, 10),
        ("RESP_CHECK", "CICS", "READ", "NORMAL,NOTFND", 20),
        ("ROLLBACK", "CICS", "SYNCPOINT ROLLBACK", None, 30),
        ("COMMIT", "SQL", "COMMIT WORK", None, 40),
        ("ABEND", "CICS", "ABEND", "HBNK", 50),
    ]


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "m.db"
    _record(db)
    _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM uow_handler_data")[0][0] == 5


def test_an_unchanged_file_keeps_its_rows_through_a_delta_scan(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/CREACC.cbl"]["uow_handlers"] == ROWS
    assert cache["cbl/PLAIN.cbl"]["uow_handlers"] == []
    delta_db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, SESSION, str(delta_db))
    assert _rows(delta_db, SELECT) == _rows(db, SELECT)


def test_a_pre_3453_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE uow_handler_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/CREACC.cbl"]["uow_handlers"] == []
