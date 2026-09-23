"""
#3328 / #3329: fcall_data, edge_data's 'fcall' kind and function_data.calls_out_qualifiers.

  1. Every (caller, callee) pair the repository defines is an fcall_data row whose
     src/dst function ids point at the function_data rows of the right functions;
     an external callee (defined nowhere) is not a row.
  2. The fcall_file_edges view aggregates only confident cross-file pairs, and
     edge_data holds only the import edges (#2992's reconciliation is untouched).
  3. calls_out_qualifiers is persisted, and the rehydrator restores it together
     with start_line, so a delta scan re-resolves to the same rows.
  4. Re-recording a snapshot does not duplicate rows.
"""

import sqlite3

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper

SESSION = {
    "target": "FcallRepo",
    "git_audit": {"commit_hash": "f3328", "latest_commit_date": "2026-09-23T00:00:00Z"},
}


def _fn(name, line, calls=(), quals=None, owner=None):
    f = {"name": name, "start_line": line, "calls_out_to": list(calls), "calls_out_qualifiers": quals or {}}
    if owner:
        f["parent_class_name"] = owner
    return f


def _universe():
    return [
        {
            "path": "app/main.py",
            "lang_id": "python",
            "raw_imports": [],
            "functions": [
                _fn(
                    "main",
                    1,
                    ["parse", "Store", "helper", "print", "get"],
                    {
                        "parse": ["utils"],
                        "Store": [""],
                        "helper": [""],
                        "print": [""],
                        "get": ["d"],
                    },
                ),
                _fn("helper", 9),
            ],
        },
        {"path": "lib/utils.py", "lang_id": "python", "raw_imports": [], "functions": [_fn("parse", 1)]},
        {
            "path": "lib/store.py",
            "lang_id": "python",
            "raw_imports": [],
            "functions": [_fn("get", 2, owner="Store")],
            "classes": [{"name": "Store", "inheritance": []}],
        },
    ]


_IMPORTS = [{"src": "app/main.py", "dst": "lib/utils.py", "edge_kind": "import", "weight": 1.0, "import_statements": 1}]


def _record(db, files):
    sites, stats = resolve_calls(files, _IMPORTS)
    RecordKeeper().record_mission(
        files, [], {}, SESSION, str(db), dependency_edges=_IMPORTS, fcall_sites=sites, call_resolution=stats
    )


def _rows(db, sql):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


_SITES_SQL = """
    SELECT sf.func_name, f.callee, f.step, df.file_path, dfn.func_name, dc.class_name
    FROM fcall_data f
    JOIN function_data sf ON sf.id = f.src_func_id
    LEFT JOIN file_data df ON df.id = f.dst_file_id
    LEFT JOIN function_data dfn ON dfn.id = f.dst_func_id
    LEFT JOIN class_data dc ON dc.id = f.dst_class_id
    ORDER BY f.callee
"""


def test_every_pair_is_a_row_with_the_right_ids(tmp_path):
    db = tmp_path / "f.db"
    _record(db, _universe())
    assert _rows(db, _SITES_SQL) == [
        ("main", "Store", "unique", "lib/store.py", None, "Store"),
        ("main", "get", "receiver", "lib/store.py", "get", None),
        ("main", "helper", "file", "app/main.py", "helper", None),
        ("main", "parse", "import", "lib/utils.py", "parse", None),
    ]


def test_file_view_holds_only_confident_cross_file_pairs(tmp_path):
    db = tmp_path / "f.db"
    _record(db, _universe())
    got = _rows(
        db,
        "SELECT s.file_path, d.file_path, v.calling_pairs FROM fcall_file_edges v "
        "JOIN file_data s ON s.id = v.src_file_id JOIN file_data d ON d.id = v.dst_file_id "
        "ORDER BY d.file_path",
    )
    # the ambiguous `get` (lib/store.py's method) and the same-file `helper` are
    # not in it; `Store` (unique, the class) and `parse` (import) are
    assert got == [("app/main.py", "lib/store.py", 1), ("app/main.py", "lib/utils.py", 1)]
    assert _rows(db, "SELECT edge_kind, COUNT(*) FROM edge_data GROUP BY edge_kind") == [("import", 1)]


def test_qualifiers_persist_and_rehydrate_to_the_same_resolution(tmp_path):
    db = tmp_path / "f.db"
    files = _universe()
    _record(db, files)
    assert _rows(db, "SELECT calls_out_qualifiers FROM function_data WHERE func_name = 'main'") == [
        ('["utils","","","","d"]',)
    ]
    cache = StateRehydrator(str(db)).load_state("FcallRepo")["ram_cache"]
    restored = [{"path": path, **node} for path, node in sorted(cache.items())]

    def key(rows):
        return sorted((r["src_path"], r["callee"], r["step"], r["dst_path"], r["dst_name"]) for r in rows)

    assert key(resolve_calls(restored, _IMPORTS)[0]) == key(resolve_calls(files, _IMPORTS)[0])


def test_rerecording_a_snapshot_does_not_duplicate(tmp_path):
    db = tmp_path / "f.db"
    _record(db, _universe())
    _record(db, _universe())
    assert _rows(db, "SELECT COUNT(*) FROM fcall_data") == [(4,)]
    assert _rows(db, "SELECT COUNT(*) FROM edge_data") == [(1,)]


def test_rates_are_recorded_per_language_and_repo(tmp_path):
    # #3331: external pairs are counted here even though they are not fcall_data rows
    db = tmp_path / "f.db"
    _record(db, _universe())
    _record(db, _universe())  # idempotent per snapshot
    assert _rows(
        db, 'SELECT language, scoped, "unique", ambiguous, external, total FROM fcall_rate_data ORDER BY language'
    ) == [("*", 2, 1, 1, 1, 5), ("python", 2, 1, 1, 1, 5)]


def test_brief_section_states_rates_and_caveat():
    from gitgalaxy.recorders.llm_recorder import LLMRecorder

    stats = resolve_calls(_universe(), _IMPORTS)[1]
    lines = LLMRecorder.__new__(LLMRecorder)._call_resolution_lines(stats)
    text = "\n".join(lines)
    assert lines[0].startswith("## 15. FUNCTION CALL RESOLUTION")
    assert "5 call pairs -- scoped 40.0%, unique 20.0%, ambiguous 20.0%, external 20.0%" in text
    assert "not that the choice was correct" in text
    assert "| python | 5 | 40.0% | 20.0% | 20.0% | 20.0% |" in text
    assert LLMRecorder.__new__(LLMRecorder)._call_resolution_lines({}) == []
