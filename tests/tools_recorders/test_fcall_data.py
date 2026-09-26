"""
#3328 / #3329: fcall_data, edge_data's 'fcall' kind and function_data.calls_out_qualifiers.

  1. Every (caller, callee) pair the repository defines is an fcall_data row whose
     src/dst function ids point at the function_data rows of the right functions;
     an external callee (defined nowhere) is not a row.
  2. Only confident cross-file pairs no import already covers join the
     dependency graph, as edge_kind 'fcall' (#3333).
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
    # PHP, a global-namespace language: its bare `Store(` reaches the one
    # `Store` class without an import (`unique`). In a package-scoped language
    # (Python, JS/TS, ...) it would be `unseen` instead (#3443).
    return [
        {
            "path": "app/main.php",
            "lang_id": "php",
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
        {"path": "lib/utils.php", "lang_id": "php", "raw_imports": [], "functions": [_fn("parse", 1)]},
        {
            "path": "lib/store.php",
            "lang_id": "php",
            "raw_imports": [],
            "functions": [_fn("get", 2, owner="Store")],
            "classes": [{"name": "Store", "inheritance": []}],
        },
    ]


_IMPORTS = [
    {"src": "app/main.php", "dst": "lib/utils.php", "edge_kind": "import", "weight": 1.0, "import_statements": 1}
]


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
        ("main", "Store", "unique", "lib/store.php", None, "Store"),
        ("main", "get", "receiver", "lib/store.php", "get", None),
        ("main", "helper", "file", "app/main.php", "helper", None),
        ("main", "parse", "import", "lib/utils.php", "parse", None),
    ]


def test_confident_cross_file_pairs_join_the_graph(tmp_path):
    # #3333: `Store` (unique, the class's file) is a call edge the import graph
    # lacked; `parse` is already joined by an import, so it adds nothing; the
    # ambiguous `get` and the same-file `helper` never become edges.
    from gitgalaxy.core.call_resolver import confident_file_pairs
    from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor

    files = _universe()
    for f in files:
        f.setdefault("telemetry", {})
    sites, stats = resolve_calls(files, _IMPORTS)
    pairs = confident_file_pairs(sites)
    assert pairs == {("app/main.php", "lib/utils.php"): 1, ("app/main.php", "lib/store.php"): 1}
    sensor = NetworkRiskSensor()
    imports = {("app/main.php", "lib/utils.php"): {"weight": 1.0, "import_statements": 1, "entity_imports": 0}}
    files, _ = sensor.build_dependency_graph(files, pairs, imports)
    assert sorted((e["src"], e["dst"], e["edge_kind"]) for e in sensor.dependency_edges) == [
        ("app/main.php", "lib/store.php", "fcall"),
        ("app/main.php", "lib/utils.php", "import"),
    ]
    by_path = {f["path"]: f["telemetry"] for f in files}
    assert by_path["lib/store.php"]["popularity"] == 1  # 0 on imports alone

    db = tmp_path / "f.db"
    RecordKeeper().record_mission(
        files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges, fcall_sites=sites
    )
    assert _rows(db, "SELECT edge_kind, weight, import_statements FROM edge_data ORDER BY edge_kind") == [
        ("fcall", 1.0, 1),
        ("import", 1.0, 1),
    ]


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
    assert _rows(db, "SELECT COUNT(*) FROM edge_data") == [(1,)]  # imports only: _record passes no call edges


def test_rates_are_recorded_per_language_and_repo(tmp_path):
    # #3331: external pairs are counted here even though they are not fcall_data rows
    db = tmp_path / "f.db"
    _record(db, _universe())
    _record(db, _universe())  # idempotent per snapshot
    assert _rows(
        db, 'SELECT language, scoped, "unique", ambiguous, external, total FROM fcall_rate_data ORDER BY language'
    ) == [("*", 2, 1, 1, 1, 5), ("php", 2, 1, 1, 1, 5)]


def test_brief_section_states_rates_and_caveat():
    from gitgalaxy.recorders.llm_recorder import LLMRecorder

    stats = resolve_calls(_universe(), _IMPORTS)[1]
    lines = LLMRecorder.__new__(LLMRecorder)._call_resolution_lines(stats)
    text = "\n".join(lines)
    assert lines[0].startswith("## 15. FUNCTION CALL RESOLUTION")
    assert "5 call pairs -- scoped 40.0%, unique 20.0%, ambiguous 20.0%, external 20.0%" in text
    assert "not that the choice was correct" in text
    assert "| php | 5 | 40.0% | 20.0% | 20.0% | 20.0% |" in text
    assert LLMRecorder.__new__(LLMRecorder)._call_resolution_lines({}) == []


def test_a_constructor_call_links_the_constructor_and_keeps_the_class(tmp_path):
    # #3642 follow-up: `new Store()` reaches Store's `__construct`, and the row still names the class.
    files = _universe()
    files[2]["functions"].append(_fn("__construct", 3, owner="Store"))
    db = tmp_path / "f.db"
    _record(db, files)
    rows = [r for r in _rows(db, _SITES_SQL) if r[1] == "Store"]
    assert rows == [("main", "Store", "unique", "lib/store.php", "__construct", "Store")]


def test_receiver_types_persist_and_rehydrate(tmp_path):
    db = tmp_path / "f.db"
    files = _universe()
    files[0]["functions"][0]["calls_out_receiver_types"] = {"d": "Store"}
    _record(db, files)
    assert _rows(db, "SELECT calls_out_receiver_types FROM function_data WHERE func_name = 'main'") == [
        ('{"d":"Store"}',)
    ]
    cache = StateRehydrator(str(db)).load_state("FcallRepo")["ram_cache"]
    main = [f for node in cache.values() for f in node["functions"] if f["name"] == "main"]
    assert main[0]["calls_out_receiver_types"] == {"d": "Store"}
