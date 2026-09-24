"""#3451: job_flow_data -- JCL job flow in the master DB: one row per JOB / STEP /
DD, byte-identical delta restore, and a pre-#3451 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "jf3451", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
_BLANK = {
    "kind": None,
    "name": None,
    "step_ordinal": None,
    "step_name": None,
    "program": None,
    "proc": None,
    "cond": None,
    "if_cond": None,
    "in_proc": None,
    "dd_name": None,
    "dsn": None,
    "disp": None,
    "generation": None,
    "line": 0,
}
FLOW = [
    dict(_BLANK, kind="JOB", name="COMBTRAN", cond="(8,LT)", line=1),
    dict(_BLANK, kind="STEP", step_ordinal=1, step_name="STEP10", program="SORT", cond="(4,LT)", line=10),
    dict(_BLANK, kind="DD", step_name="STEP10", dd_name="SORTOUT", dsn="APP.C", disp="NEW", generation="+1", line=13),
]
UNIVERSE = [{"path": "jcl/COMBTRAN.jcl", "lang_id": "jcl", "raw_imports": [], "job_flow": FLOW}]


def _record(db):
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_rows_are_recorded(tmp_path):
    db = _record(tmp_path / "m.db")
    assert _rows(
        db, "SELECT kind, job_name, step_ordinal, program, cond, dsn, disp, generation FROM job_flow_data ORDER BY id"
    ) == [
        ("JOB", "COMBTRAN", None, None, "(8,LT)", None, None, None),
        ("STEP", None, 1, "SORT", "(4,LT)", None, None, None),
        ("DD", None, None, None, None, "APP.C", "NEW", "+1"),
    ]


def test_an_unchanged_file_keeps_its_rows_through_a_delta_scan(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["jcl/COMBTRAN.jcl"]["job_flow"] == FLOW
    delta_db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, SESSION, str(delta_db))
    sql = "SELECT * FROM job_flow_data ORDER BY id"
    assert [r[4:] for r in _rows(delta_db, sql)] == [r[4:] for r in _rows(db, sql)]


def test_a_pre_3451_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE job_flow_data")
    conn.commit()
    conn.close()
    assert StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["jcl/COMBTRAN.jcl"]["job_flow"] == []
