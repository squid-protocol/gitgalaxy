"""
#3313 step 3: wrapper_data and file_data.wrapper_facts in the master DB.

  1. The resolved wrappers become wrapper_data rows on their DEFINING file.
  2. Each file's raw wrapper_facts is persisted, and the rehydrator restores it,
     so a delta scan re-resolves exactly: resolving the restored facts gives
     the same rows as the full scan (the #3220 raw_imports precedent).
  3. The table cascade-deletes with file_data: re-recording a snapshot does not
     duplicate rows.
"""

import sqlite3

from gitgalaxy.core.wrapper_resolver import resolve_wrappers
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "WrapperRepo",
    "git_audit": {"commit_hash": "w3313", "latest_commit_date": "2026-09-23T00:00:00Z"},
}


def _cand(name, hits=(), callees=(), loc=5, branches=0):
    return {
        "name": name,
        "loc": loc,
        "branches": branches,
        "aligned": True,
        "method": False,
        "hits": list(hits),
        "callees": list(callees),
    }


def _universe():
    return [
        {
            "path": "wrf/wrapper.F",
            "lang_id": "fortran",
            "raw_imports": [],
            "wrapper_facts": {
                "defined": {"wrf_error_fatal": 1},
                "candidates": [_cand("wrf_error_fatal", ["debug_prints", "panics_and_aborts"])],
                "calls": {},
                "macros": [],
            },
        },
        {
            "path": "wrf/caller.F",
            "lang_id": "fortran",
            "raw_imports": [],
            "wrapper_facts": {
                "defined": {"init_domain": 1},
                "candidates": [],
                "calls": {"wrf_error_fatal": 3},
                "macros": [],
            },
        },
        {"path": "wrf/plain.F", "lang_id": "fortran", "raw_imports": []},
    ]


def _record(db, files):
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), wrappers=resolve_wrappers(files))


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_resolved_wrappers_land_on_their_defining_file(tmp_path):
    db = tmp_path / "w.db"
    _record(db, _universe())
    assert _rows(
        db,
        "SELECT fd.file_path, w.wrapper_name, w.kind, w.rule, w.via, w.call_sites, w.calling_files "
        "FROM wrapper_data w JOIN file_data fd ON fd.id = w.file_id ORDER BY w.rule",
    ) == [
        ("wrf/wrapper.F", "wrf_error_fatal", "function", "debug_prints", "primitive", 3, 1),
        ("wrf/wrapper.F", "wrf_error_fatal", "function", "panics_and_aborts", "primitive", 3, 1),
    ]


def test_a_file_without_facts_stores_null(tmp_path):
    db = tmp_path / "w.db"
    _record(db, _universe())
    assert _rows(db, "SELECT wrapper_facts FROM file_data WHERE file_path = 'wrf/plain.F'") == [(None,)]


def test_re_recording_the_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "w.db"
    for _ in range(2):
        _record(db, _universe())
    assert _rows(db, "SELECT COUNT(*) FROM wrapper_data") == [(2,)]


def test_a_delta_scan_re_resolves_to_the_same_rows(tmp_path):
    """An unchanged file is never re-parsed: its wrapper_facts must come back from
    the DB, or its wrappers (and every call site in it) drop out of the next
    scan's resolution."""
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    db = tmp_path / "w.db"
    files = _universe()
    _record(db, files)
    cache = StateRehydrator(str(db)).load_state("WrapperRepo")["ram_cache"]
    restored = [{"path": path, **node} for path, node in sorted(cache.items())]
    assert resolve_wrappers(restored) == resolve_wrappers(files)
    assert cache["wrf/plain.F"]["wrapper_facts"] is None


def test_a_caller_predating_the_channel_writes_no_wrapper_rows(tmp_path):
    db = tmp_path / "w.db"
    RecordKeeper().record_mission(_universe(), [], {}, SESSION, str(db))
    assert _rows(db, "SELECT COUNT(*) FROM wrapper_data") == [(0,)]
