"""#3450: dli_call_data -- IMS DL/I calls in the master DB, byte-identical delta
restore, and a pre-#3450 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "dli3450", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
_BLANK = {"interface": None, "function": None, "function_operand": None, "pcb": None, "io_area": None,
          "segments": None, "ssas": None, "where": None, "psb": None, "line": 0}  # fmt: skip
CALLS = [
    dict(_BLANK, interface="EXEC", function="GU", pcb="PAUT-PCB-NUM", io_area="SUMM", segments="PAUTSUM0",
         where="ACCNTID = PA-ACCT-ID", line=973),
    dict(_BLANK, interface="CALL", function_operand="FUNC-GU", pcb="PAUTBPCB", io_area="SUMM", ssas="ROOT-QUAL-SSA",
         line=296),
]  # fmt: skip
UNIVERSE = [{"path": "cbl/PAUDBLOD.CBL", "lang_id": "cobol", "raw_imports": [], "dli_calls": CALLS}]


def _record(db):
    RecordKeeper().record_mission([dict(f) for f in UNIVERSE], [], {}, SESSION, str(db))
    return db


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_rows_are_recorded_and_restored(tmp_path):
    db = _record(tmp_path / "m.db")
    assert _rows(
        db, "SELECT interface, function, function_operand, segments, ssas, where_text FROM dli_call_data ORDER BY id"
    ) == [
        ("EXEC", "GU", None, "PAUTSUM0", None, "ACCNTID = PA-ACCT-ID"),
        ("CALL", None, "FUNC-GU", None, "ROOT-QUAL-SSA", None),
    ]
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/PAUDBLOD.CBL"]["dli_calls"] == CALLS


def test_a_pre_3450_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE dli_call_data")
    conn.commit()
    conn.close()
    assert StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]["cbl/PAUDBLOD.CBL"]["dli_calls"] == []
