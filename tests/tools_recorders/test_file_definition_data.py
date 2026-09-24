"""#3455: file_control_data / vsam_define_data -- file definitions in the master
DB: one row per SELECT / IDCAMS define, cascade with file_data, byte-identical
delta restore, and a pre-#3455 baseline restores nothing."""

import sqlite3

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "MainframeRepo",
    "git_audit": {"commit_hash": "fd3455", "latest_commit_date": "2026-09-24T00:00:00Z"},
}
SELECTS = [
    {
        "select_name": "XREF-FILE",
        "assign": "XREFFILE",
        "organization": "INDEXED",
        "access_mode": "RANDOM",
        "record_key": "FD-XREF-CARD-NUM",
        "alternate_keys": "FD-XREF-ACCT-ID+DUP",
        "relative_key": None,
        "file_status": "XREFFILE-STATUS",
        "fd_copies": "CVACT03Y",
        "line": 34,
    }
]
DEFINES = [
    {
        "kind": "AIX",
        "name": "X.AIX",
        "organization": None,
        "key_length": 11,
        "key_offset": 25,
        "record_avg": 50,
        "record_max": 50,
        "related": "X.KSDS",
        "unique_key": "NONUNIQUE",
        "upgrade": "UPGRADE",
        "step": "STEP20",
        "line": 72,
    }
]
UNIVERSE = [
    {"path": "cbl/CBACT04C.cbl", "lang_id": "cobol", "raw_imports": [], "file_control": SELECTS},
    {"path": "jcl/XREFFILE.jcl", "lang_id": "jcl", "raw_imports": [], "vsam_defines": DEFINES},
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


def test_rows_are_recorded(tmp_path):
    db = _record(tmp_path / "m.db")
    assert _rows(db, "SELECT select_name, alternate_keys, fd_copies, line_number FROM file_control_data") == [
        ("XREF-FILE", "FD-XREF-ACCT-ID+DUP", "CVACT03Y", 34)
    ]
    assert _rows(db, "SELECT kind, cluster_name, key_length, key_offset, related FROM vsam_define_data") == [
        ("AIX", "X.AIX", 11, 25, "X.KSDS")
    ]


def test_an_unchanged_file_keeps_its_rows_through_a_delta_scan(tmp_path):
    db = _record(tmp_path / "m.db")
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/CBACT04C.cbl"]["file_control"] == SELECTS
    assert cache["jcl/XREFFILE.jcl"]["vsam_defines"] == DEFINES
    assert cache["jcl/XREFFILE.jcl"]["file_control"] == []
    delta_db = tmp_path / "delta.db"
    RecordKeeper().record_mission([dict(n, path=p) for p, n in cache.items()], [], {}, SESSION, str(delta_db))
    for table in ("file_control_data", "vsam_define_data"):
        sql = f"SELECT * FROM {table} ORDER BY id"
        assert [r[4:] for r in _rows(delta_db, sql)] == [r[4:] for r in _rows(db, sql)]


def test_a_pre_3455_baseline_rehydrates_with_no_rows(tmp_path):
    db = _record(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE file_control_data")
    conn.execute("DROP TABLE vsam_define_data")
    conn.commit()
    conn.close()
    cache = StateRehydrator(str(db)).load_state("MainframeRepo")["ram_cache"]
    assert cache["cbl/CBACT04C.cbl"]["file_control"] == [] and cache["jcl/XREFFILE.jcl"]["vsam_defines"] == []
