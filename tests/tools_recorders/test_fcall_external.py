# ruff: noqa: S101
"""External calls are aggregated in `fcall_external`: one row per (calling file, callee name) for every call the resolver could
not tie to a definition in the repository. `fcall_data`, the confident graph and the resolution rates are unchanged."""

import sqlite3

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "ExternalRepo",
    "git_audit": {"commit_hash": "fext1", "latest_commit_date": "2026-11-16T00:00:00Z"},
}


def _fn(name, line, calls=()):
    return {
        "name": name,
        "start_line": line,
        "calls_out_to": list(calls),
        "calls_out_qualifiers": {c: [""] for c in calls},
    }


def _files():
    return [
        {
            "path": "src/a.c",
            "lang_id": "c",
            "raw_imports": [],
            # two functions call free and memcpy (external), one also calls helper (defined in b.c)
            "functions": [_fn("one", 1, ["free", "memcpy", "helper"]), _fn("two", 9, ["free"])],
        },
        {"path": "src/b.c", "lang_id": "c", "raw_imports": [], "functions": [_fn("helper", 3, ["free"])]},
    ]


def _record(tmp_path):
    db = tmp_path / "e.db"
    files = _files()
    sites, stats = resolve_calls(files)
    keeper = RecordKeeper()
    keeper.record_mission(files, [], {}, SESSION, str(db), fcall_sites=sites, call_resolution=stats)
    return db, files, sites, stats, keeper


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_external_calls_are_aggregated_per_file_and_callee(tmp_path):
    db = _record(tmp_path)[0]
    rows = _rows(
        db,
        "SELECT f.file_path, e.callee, e.callers FROM fcall_external e JOIN file_data f ON f.id = e.src_file_id "
        "ORDER BY f.file_path, e.callee",
    )
    assert rows == [("src/a.c", "free", 2), ("src/a.c", "memcpy", 1), ("src/b.c", "free", 1)]


def test_fcall_data_and_rates_are_unchanged(tmp_path):
    db, _files_, sites, stats, _k = _record(tmp_path)
    steps = _rows(db, "SELECT callee, step FROM fcall_data")
    assert steps == [("helper", "unique")]  # no external row leaks into fcall_data
    (rate,) = _rows(db, "SELECT external, total FROM fcall_rate_data WHERE language = '*'")
    assert rate == (4, 5)  # the resolver still counts the external pairs: free x3 + memcpy, against one resolved pair
    assert sum(1 for s in sites if s["step"] == "none") == 4
    # the new table holds exactly the calls the rate table counts as external (reconciles on curl, libgit2 and prometheus)
    assert _rows(db, "SELECT SUM(callers) FROM fcall_external") == [(rate[0],)]


def test_a_rescan_of_the_same_commit_does_not_duplicate(tmp_path):
    db, files, sites, stats, keeper = _record(tmp_path)
    keeper.record_mission(files, [], {}, SESSION, str(db), fcall_sites=sites, call_resolution=stats)
    assert _rows(db, "SELECT COUNT(*) FROM fcall_external") == [(3,)]


def test_the_rows_go_with_their_file(tmp_path):
    db = _record(tmp_path)[0]
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM file_data WHERE file_path = 'src/a.c'")
        assert conn.execute("SELECT callee FROM fcall_external").fetchall() == [("free",)]
    finally:
        conn.close()


def test_a_scan_with_no_external_calls_writes_no_rows(tmp_path):
    db = tmp_path / "n.db"
    files = [_files()[1]]
    files[0] = dict(files[0], functions=[_fn("helper", 3)])
    sites, stats = resolve_calls(files)
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db), fcall_sites=sites, call_resolution=stats)
    assert _rows(db, "SELECT COUNT(*) FROM fcall_external") == [(0,)]
