"""#3448: job_submit_data -- job-submission evidence in the master DB: one row per
card / INTRDR DD, cascade with file_data, byte-identical delta restore, and a
pre-#3448 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "job3448", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
COBOL = [
    {"kind": "JOB", "step": None, "name": "TRNRPT00", "target_kind": None, "target": None, "line": 84},
    {"kind": "EXEC", "step": "STEP10", "name": None, "target_kind": "PROC", "target": "TRANREPT", "line": 94},
]
JCL = [{"kind": "INTRDR", "step": "STEP01", "name": "SYSUT2", "target_kind": "DSN", "target": "LIB(J2)", "line": 18}]
UNIVERSE = [
    {"path": "cbl/CORPT00C.cbl", "lang_id": "cobol", "raw_imports": [], "job_submits": COBOL},
    {"path": "jcl/INTRDRJ1.jcl", "lang_id": "jcl", "raw_imports": [], "job_submits": JCL},
    {"path": "cbl/PLAIN.cbl", "lang_id": "cobol", "raw_imports": []},
]
SELECT = (
    "SELECT f.file_path, kind, step_name, submit_name, target_kind, target, line_number "
    "FROM job_submit_data j JOIN file_data f ON j.file_id = f.id ORDER BY 1, j.id"
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
    assert _rows(_record(tmp_path / "m.db"), SELECT) == [
        ("cbl/CORPT00C.cbl", "JOB", None, "TRNRPT00", None, None, 84),
        ("cbl/CORPT00C.cbl", "EXEC", "STEP10", None, "PROC", "TRANREPT", 94),
        ("jcl/INTRDRJ1.jcl", "INTRDR", "STEP01", "SYSUT2", "DSN", "LIB(J2)", 18),
    ]


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "m.db"
    _record(db)
    _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM job_submit_data")[0][0] == 3


def test_an_unchanged_file_keeps_its_rows_through_a_delta_scan(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/CORPT00C.cbl"]["job_submits"] == COBOL
    assert cache["jcl/INTRDRJ1.jcl"]["job_submits"] == JCL
    assert cache["cbl/PLAIN.cbl"]["job_submits"] == []
    delta_db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, SESSION, str(delta_db))
    assert _rows(delta_db, SELECT) == _rows(db, SELECT)


def test_a_pre_3448_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE job_submit_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/CORPT00C.cbl"]["job_submits"] == []
