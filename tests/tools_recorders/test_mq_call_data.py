"""#3447: mq_call_data -- IBM MQ calls in the master DB: one row per call,
cascade with file_data, byte-identical delta restore, and a pre-#3447 baseline
restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "mq3447", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
CALLS = [
    {
        "verb": "MQOPEN",
        "direction": "put",
        "operand": "REPLY-QUEUE-NAME",
        "queue": "CARD.DEMO.REPLY.ACCT",
        "resolution": "move",
        "candidates": None,
        "handle": "MQ-HOBJ",
        "open_line": None,
        "options": "MQOO-OUTPUT",
        "line": 267,
    },
    {
        "verb": "MQPUT",
        "direction": "put",
        "operand": "REPLY-QUEUE-NAME",
        "queue": "CARD.DEMO.REPLY.ACCT",
        "resolution": "move",
        "candidates": None,
        "handle": "OUTPUT-QUEUE-HANDLE",
        "open_line": 267,
        "options": "MQPMO-SYNCPOINT",
        "line": 479,
    },
    {
        "verb": "MQGET",
        "direction": "get",
        "operand": "INPUT-QUEUE-NAME",
        "queue": None,
        "resolution": "trigger",
        "candidates": None,
        "handle": "INPUT-QUEUE-HANDLE",
        "open_line": 233,
        "options": None,
        "line": 352,
    },
]
UNIVERSE = [
    {"path": "cbl/COACCT01.cbl", "lang_id": "cobol", "raw_imports": [], "mq_calls": CALLS},
    {"path": "cbl/PLAIN.cbl", "lang_id": "cobol", "raw_imports": []},
]
SELECT = (
    "SELECT f.file_path, verb, direction, queue_operand, queue_name, queue_resolution, queue_candidates, "
    "handle, open_line, options, line_number FROM mq_call_data q JOIN file_data f ON q.file_id = f.id ORDER BY 1, q.id"
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


def test_every_call_is_recorded(tmp_path):
    rows = _rows(_record(tmp_path / "m.db"), SELECT)
    assert [(r[1], r[4], r[5], r[7], r[8], r[10]) for r in rows] == [
        ("MQOPEN", "CARD.DEMO.REPLY.ACCT", "move", "MQ-HOBJ", None, 267),
        ("MQPUT", "CARD.DEMO.REPLY.ACCT", "move", "OUTPUT-QUEUE-HANDLE", 267, 479),
        ("MQGET", None, "trigger", "INPUT-QUEUE-HANDLE", 233, 352),
    ]


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "m.db"
    _record(db)
    _record(db)
    assert _rows(db, "SELECT COUNT(*) FROM mq_call_data")[0][0] == 3


def test_an_unchanged_file_keeps_its_calls_through_a_delta_scan(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/COACCT01.cbl"]["mq_calls"] == CALLS
    assert cache["cbl/PLAIN.cbl"]["mq_calls"] == []
    delta_db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, SESSION, str(delta_db))
    assert _rows(delta_db, SELECT) == _rows(db, SELECT)


def test_a_pre_3447_baseline_rehydrates_with_no_calls(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE mq_call_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/COACCT01.cbl"]["mq_calls"] == []
