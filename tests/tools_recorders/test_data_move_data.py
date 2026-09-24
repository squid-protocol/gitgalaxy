"""#3452: data_move_data -- field-level data movement in the master DB, byte-identical
delta restore, and a pre-#3452 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "moves3452", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
MOVES = [
    {"verb": "MOVE", "source": "CUSTNAMI", "source_kind": "item", "target": "COMM-NAME OF UPDCUST-COMMAREA",
     "corresponding": False, "source_refmod": False, "target_refmod": False, "line": 1130},
    {"verb": "MOVE", "source": "DFHCOMMAREA", "source_kind": "item", "target": "WS-COMM",
     "corresponding": False, "source_refmod": True, "target_refmod": False, "line": 212},
    {"verb": "INITIALIZE", "source": None, "source_kind": None, "target": "UPDCUST-COMMAREA",
     "corresponding": False, "source_refmod": False, "target_refmod": False, "line": 1126},
]  # fmt: skip
UNIVERSE = [{"path": "cbl/BNK1DCS.cbl", "lang_id": "cobol", "raw_imports": [], "data_moves": MOVES}]


def _record(db):
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def test_rows_are_recorded_and_restored(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    try:
        got = conn.execute(
            "SELECT verb, source, target, source_refmod, line_number FROM data_move_data ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert got == [
        ("MOVE", "CUSTNAMI", "COMM-NAME OF UPDCUST-COMMAREA", 0, 1130),
        ("MOVE", "DFHCOMMAREA", "WS-COMM", 1, 212),
        ("INITIALIZE", None, "UPDCUST-COMMAREA", 0, 1126),
    ]
    assert StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["cbl/BNK1DCS.cbl"]["data_moves"] == MOVES


def test_a_pre_3452_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE data_move_data")
    conn.commit()
    conn.close()
    assert StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["cbl/BNK1DCS.cbl"]["data_moves"] == []
