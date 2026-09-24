"""#3496: web_service_data -- web-services assistant steps in the master DB (the
`transaction` field is the column transaction_id: TRANSACTION is an SQL keyword),
byte-identical delta restore, and a pre-#3496 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "ws3496", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
ROWS = [
    {"assistant": "DFHLS2WS", "direction": "provider", "program": "LGICUS01", "uri": "GENAPP/LGICUS01",
     "request": "SOAIC01", "response": "SOAIC01", "interface": "COMMAREA", "container": None,
     "binding": "x.wsbind", "document": "x.wsdl", "transaction": "CPIH", "line": 13},
]  # fmt: skip
UNIVERSE = [{"path": "cntl/wsaic01.jcl", "lang_id": "jcl", "raw_imports": [], "web_services": ROWS}]


def _record(db):
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def test_rows_are_recorded_and_restored(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    try:
        got = conn.execute("SELECT program, uri, transaction_id, line_number FROM web_service_data").fetchall()
    finally:
        conn.close()
    assert got == [("LGICUS01", "GENAPP/LGICUS01", "CPIH", 13)]
    assert StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["cntl/wsaic01.jcl"]["web_services"] == ROWS


def test_a_pre_3496_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE web_service_data")
    conn.commit()
    conn.close()
    assert StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["cntl/wsaic01.jcl"]["web_services"] == []
