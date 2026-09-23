"""
#3330: function-level PageRank / fan-in / fan-out (core/function_graph.py),
built from the call resolver's confident function-to-function links only.
"""

import sqlite3

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.function_graph import attach_function_metrics, function_metrics
from gitgalaxy.recorders.record_keeper import RecordKeeper


def _fn(name, line, calls=(), synthetic=False, owner=None):
    f = {
        "name": name,
        "start_line": line,
        "calls_out_to": list(calls),
        "calls_out_qualifiers": {c: [""] for c in calls},
    }
    if synthetic:
        f["is_synthetic_slice"] = True
    if owner:
        f["parent_class_name"] = owner
    return f


def _files():
    # main -> helper -> leaf ; util -> leaf ; module-level code -> main
    # `get` is only reachable through an untyped receiver (ambiguous: no edge),
    # `Store(...)` resolves to a class (no function node: no edge).
    main = _fn("main", 1, ["helper", "Store", "get"])
    main["calls_out_qualifiers"]["get"] = ["d"]
    return [
        {
            "path": "app.py",
            "lang_id": "python",
            "functions": [_fn("<module>", 0, ["main"], synthetic=True), main, _fn("helper", 9, ["leaf"])],
        },
        {"path": "lib.py", "lang_id": "python", "functions": [_fn("leaf", 1), _fn("util", 5, ["leaf"])]},
        {
            "path": "far/store.py",
            "lang_id": "python",
            "functions": [_fn("get", 2, owner="Store")],
            "classes": [{"name": "Store", "inheritance": []}],
        },
    ]


def _metrics(files):
    sites, _ = resolve_calls(files)
    return function_metrics(files, sites)


def test_fan_in_and_fan_out_follow_confident_links_only():
    m = _metrics(_files())
    main = m[("app.py", "main", 1)]
    # fan-in: the module-level caller; fan-out: helper only (Store is a class,
    # `d.get()` is ambiguous)
    assert (main["func_fan_in"], main["func_fan_out"]) == (1, 1)
    assert m[("lib.py", "leaf", 1)]["func_fan_in"] == 2
    assert m[("far/store.py", "get", 2)]["func_fan_in"] == 0


def test_pagerank_concentrates_on_the_shared_callee():
    m = _metrics(_files())
    ranks = {k[1]: v["func_pagerank"] for k, v in m.items()}
    assert max(ranks, key=ranks.get) == "leaf"
    assert abs(sum(ranks.values()) - 1.0) < 0.2  # the synthetic caller holds the rest


def test_synthetic_slices_get_no_metrics():
    assert all(name != "<module>" for _, name, _ in _metrics(_files()))


def test_columns_are_recorded(tmp_path):
    files = _files()
    sites, stats = resolve_calls(files)
    attach_function_metrics(files, function_metrics(files, sites))
    db = tmp_path / "g.db"
    session = {"target": "G", "git_audit": {"commit_hash": "g1", "latest_commit_date": "2026-09-23T00:00:00Z"}}
    RecordKeeper().record_mission(files, [], {}, session, str(db), fcall_sites=sites)
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT func_name, func_fan_in, func_fan_out, func_pagerank > 0 FROM function_data ORDER BY func_name"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        ("get", 0, 0, 1),
        ("helper", 1, 1, 1),
        ("leaf", 2, 0, 1),
        ("main", 1, 1, 1),
        ("util", 0, 1, 1),
    ]


def test_blast_radius_query_follows_confident_links(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from function_blast_radius import blast_radius

    files = _files()
    sites, _ = resolve_calls(files)
    attach_function_metrics(files, function_metrics(files, sites))
    db = tmp_path / "g.db"
    session = {"target": "G", "git_audit": {"commit_hash": "g1", "latest_commit_date": "2026-09-23T00:00:00Z"}}
    RecordKeeper().record_mission(files, [], {}, session, str(db), fcall_sites=sites)
    # module-level code is not a function_data row, so it is not listed
    assert blast_radius(str(db), "leaf") == [
        ("app.py", "helper", 9, 1),
        ("lib.py", "util", 5, 1),
        ("app.py", "main", 1, 2),
    ]
    assert blast_radius(str(db), "main", downstream=True) == [("app.py", "helper", 9, 1), ("lib.py", "leaf", 1, 2)]
    assert blast_radius(str(db), "get") == []


def test_cobol_transfers_keep_a_paragraph_reachable():
    # #3362: a paragraph reached only by GO TO keeps its fan-in.
    main = _fn("MAIN-PARA", 1, ["SUB-PARA"], owner="P")
    main["calls_out_qualifiers"] = {}
    main["transfers_to"] = ["EXIT-PARA"]
    files = [
        {
            "path": "p.cbl",
            "lang_id": "cobol",
            "functions": [main, _fn("SUB-PARA", 5, owner="P"), _fn("EXIT-PARA", 9, owner="P")],
        }
    ]
    m = _metrics(files)
    assert m[("p.cbl", "EXIT-PARA", 9)]["func_fan_in"] == 1
    assert m[("p.cbl", "SUB-PARA", 5)]["func_fan_in"] == 1
