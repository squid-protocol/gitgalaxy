"""#3449: cics_task_data -- CICS task control in the master DB: one row per
command, cascade with file_data, byte-identical delta restore, and a pre-#3449
baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "task3449", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
TASKS = [
    {
        "verb": "RUN",
        "target_kind": "TRANSID",
        "operand": "WS-RUN-TRANSID",
        "name": None,
        "resolution": "pattern",
        "candidates": "OCR[0-9]",
        "channel_operand": "WS-CHANNEL-NAME",
        "channel": "CIPCREDCHANN",
        "token": "WS-ANY-CHILD-TKN",
        "record_clause": None,
        "record": None,
        "timing": None,
        "attributes": None,
        "line": 582,
    },
    {
        "verb": "DELAY",
        "target_kind": None,
        "operand": None,
        "name": None,
        "resolution": None,
        "candidates": None,
        "channel_operand": None,
        "channel": None,
        "token": None,
        "record_clause": None,
        "record": None,
        "timing": "FOR SECONDS(3)",
        "attributes": None,
        "line": 623,
    },
    {
        "verb": "FETCH ANY",
        "target_kind": None,
        "operand": None,
        "name": None,
        "resolution": None,
        "candidates": None,
        "channel_operand": "WS-FETCH-CHAN",
        "channel": None,
        "token": "WS-FETCH-TKN",
        "record_clause": None,
        "record": None,
        "timing": None,
        "attributes": "NOSUSPEND COMPSTATUS(WS-COMPST)",
        "line": 639,
    },
]
UNIVERSE = [
    {"path": "src/CRECUST.cbl", "lang_id": "cobol", "raw_imports": [], "cics_tasks": TASKS},
    {"path": "src/PLAIN.cbl", "lang_id": "cobol", "raw_imports": []},
]
SELECT = (
    "SELECT f.file_path, verb, target_kind, target_operand, target_name, target_resolution, target_candidates, "
    "channel_operand, channel_name, token, record_clause, record_name, timing, attributes, line_number "
    "FROM cics_task_data t JOIN file_data f ON t.file_id = f.id ORDER BY 1, t.id"
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


def test_every_task_row_is_recorded(tmp_path):
    rows = _rows(_record(tmp_path / "m.db"), SELECT)
    assert [r[:3] + r[5:7] + r[9:10] + r[-2:] for r in rows] == [
        ("src/CRECUST.cbl", "RUN", "TRANSID", "pattern", "OCR[0-9]", "WS-ANY-CHILD-TKN", None, 582),
        ("src/CRECUST.cbl", "DELAY", None, None, None, None, None, 623),
        ("src/CRECUST.cbl", "FETCH ANY", None, None, None, "WS-FETCH-TKN", "NOSUSPEND COMPSTATUS(WS-COMPST)", 639),
    ]
    assert rows[0][8] == "CIPCREDCHANN" and rows[1][12] == "FOR SECONDS(3)"


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "m.db"
    _record(db)
    _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM cics_task_data")[0][0] == 3


def test_an_unchanged_file_keeps_its_tasks_through_a_delta_scan(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["src/CRECUST.cbl"]["cics_tasks"] == TASKS
    assert cache["src/PLAIN.cbl"]["cics_tasks"] == []
    delta_db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, SESSION, str(delta_db))
    assert _rows(delta_db, SELECT) == _rows(db, SELECT)


def test_a_pre_3449_baseline_rehydrates_with_no_tasks(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE cics_task_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["src/CRECUST.cbl"]["cics_tasks"] == []
