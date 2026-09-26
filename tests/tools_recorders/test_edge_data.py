"""
#2992: the dependency graph's edge list, persisted as the edge_data table.

The network sensor builds the full file-to-file import graph every scan but the
DB used to keep only per-node summaries of it (popularity, pagerank_score,
internal_dependency_links), so no neighbourhood hypothesis was testable from a
scan. These tests pin the two halves: the sensor publishes exactly the edges its
degrees were computed from (in both graph modes), and record_keeper persists
them keyed to file_data, accounting for any edge it cannot key.
"""

import copy
import sqlite3
from unittest.mock import patch

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.recorders.record_keeper import RecordKeeper

UNIVERSE = [
    {
        "path": "src/app.py",
        "lang_id": "python",
        # lib twice (once in the entity form), util once, one capture that
        # resolves to nothing in the scan.
        "raw_imports": ["src/lib.py", ("src/lib.py", "helper"), "src/util.py", "missing_pkg"],
    },
    {"path": "src/lib.py", "lang_id": "python", "raw_imports": ["src/util.py"]},
    {"path": "src/util.py", "lang_id": "python", "raw_imports": ["src/util.py"]},  # self-import: never an edge
    {"path": "src/island.py", "lang_id": "python", "raw_imports": []},
]

EXPECTED_EDGES = [
    {
        "src": "src/app.py",
        "dst": "src/lib.py",
        "edge_kind": "import",
        "weight": 2.5,
        "import_statements": 2,
        "entity_imports": 1,
    },
    {
        "src": "src/app.py",
        "dst": "src/util.py",
        "edge_kind": "import",
        "weight": 1.0,
        "import_statements": 1,
        "entity_imports": 0,
    },
    {
        "src": "src/lib.py",
        "dst": "src/util.py",
        "edge_kind": "import",
        "weight": 1.0,
        "import_statements": 1,
        "entity_imports": 0,
    },
]

SESSION = {"target": "EdgeRepo", "git_audit": {"commit_hash": "c0ffee", "latest_commit_date": "2026-09-14T00:00:00Z"}}


def _build(sensor):
    files, _ = sensor.build_dependency_graph(copy.deepcopy(UNIVERSE))
    return files


def _edges_by_path(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT s.file_path, d.file_path, e.edge_kind, e.weight, e.import_statements, e.entity_imports
        FROM edge_data e
        JOIN file_data s ON s.id = e.src_file_id
        JOIN file_data d ON d.id = e.dst_file_id
        ORDER BY e.id
    """).fetchall()
    conn.close()
    return rows


@pytest.fixture
def keeper():
    return RecordKeeper()


# ==============================================================================
# SENSOR: the published edge list is the graph the degrees came from
# ==============================================================================
def test_published_edges_match_the_degrees():
    """
    The published edge list is exactly the graph the degrees came from: degree
    counts distinct neighbours, one per edge row (#3024). src/app.py imports
    src/lib.py twice -- the case that once read out_degree 3 instead of 2.
    """
    sensor = NetworkRiskSensor()
    files = _build(sensor)

    assert sensor.dependency_edges == EXPECTED_EDGES
    for f in files:
        nm = f["telemetry"]["network_metrics"]
        assert nm["out_degree"] == sum(e["src"] == f["path"] for e in sensor.dependency_edges)
        assert nm["in_degree"] == sum(e["dst"] == f["path"] for e in sensor.dependency_edges)
        assert f["telemetry"]["popularity"] == nm["in_degree"]
    assert {f["path"]: f for f in files}["src/app.py"]["telemetry"]["network_metrics"]["out_degree"] == 2


def test_a_later_build_replaces_the_edge_list():
    """Delta mode rebuilds on the same sensor instance: no stale edges may survive."""
    sensor = NetworkRiskSensor()
    _build(sensor)
    sensor.build_dependency_graph([{"path": "only.py", "lang_id": "python", "raw_imports": []}])
    assert sensor.dependency_edges == []


# ==============================================================================
# RECORDER: edge_data keyed to file_data
# ==============================================================================
def test_edges_persist_keyed_to_file_data(keeper, tmp_path):
    sensor = NetworkRiskSensor()
    files = _build(sensor)
    db = tmp_path / "edges.db"

    keeper.record_mission(files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges)

    assert _edges_by_path(db) == [
        (e["src"], e["dst"], e["edge_kind"], e["weight"], e["import_statements"], e["entity_imports"])
        for e in EXPECTED_EDGES
    ]

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT DISTINCT repo_name, commit_hash FROM edge_data").fetchall() == [("EdgeRepo", "c0ffee")]
    assert conn.execute("SELECT network_edges_unrecorded FROM repo_data").fetchone() == (0,)
    # Per file, the rows reconcile with the node summaries already in file_data:
    # distinct neighbours over every edge kind. #3333 added 'fcall' (a confident
    # call into a file the caller does not import) and #3237 the mainframe
    # 'call'/'exec' edges, both only where no other edge joins the pair, so a
    # neighbour is one edge in the graph. edge_data may hold a pair twice -- an
    # import and a CALL between the same two files -- hence DISTINCT.
    mismatches = conn.execute("""
        SELECT f.file_path, f.internal_dependency_links, f.popularity,
               (SELECT COUNT(DISTINCT e.dst_file_id) FROM edge_data e WHERE e.src_file_id = f.id),
               (SELECT COUNT(DISTINCT e.src_file_id) FROM edge_data e WHERE e.dst_file_id = f.id)
        FROM file_data f
    """).fetchall()
    conn.close()
    for path, links, popularity, out_rows, in_rows in mismatches:
        assert (links, popularity) == (out_rows, in_rows), path


def test_edge_to_a_relegated_file_is_counted_not_recorded(keeper, tmp_path):
    """The statistical audit can relegate a graph node after the graph is built."""
    sensor = NetworkRiskSensor()
    files = _build(sensor)
    recorded = [f for f in files if f["path"] != "src/util.py"]
    db = tmp_path / "relegated.db"

    keeper.record_mission(recorded, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges)

    assert [(src, dst) for src, dst, *_ in _edges_by_path(db)] == [("src/app.py", "src/lib.py")]
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT network_edges_unrecorded FROM repo_data").fetchone() == (2,)
    conn.close()


def test_rerecording_a_commit_does_not_duplicate_edges(keeper, tmp_path):
    sensor = NetworkRiskSensor()
    files = _build(sensor)
    db = tmp_path / "twice.db"

    keeper.record_mission(files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges)
    keeper.record_mission(files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges)

    assert len(_edges_by_path(db)) == len(EXPECTED_EDGES)
    conn = sqlite3.connect(db)
    # No orphan rows pointing at the first run's (deleted) file ids either.
    assert conn.execute("SELECT COUNT(*) FROM edge_data").fetchone() == (len(EXPECTED_EDGES),)
    conn.close()


def test_snapshots_of_two_commits_keep_their_own_edges(keeper, tmp_path):
    sensor = NetworkRiskSensor()
    files = _build(sensor)
    db = tmp_path / "history.db"
    later = {**SESSION, "git_audit": {**SESSION["git_audit"], "commit_hash": "beef"}}

    keeper.record_mission(files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges)
    keeper.record_mission(files, [], {}, later, str(db), dependency_edges=sensor.dependency_edges[:1])

    conn = sqlite3.connect(db)
    counts = conn.execute("SELECT commit_hash, COUNT(*) FROM edge_data GROUP BY commit_hash ORDER BY 1").fetchall()
    # Every edge's endpoints belong to its own snapshot's file_data rows.
    cross = conn.execute("""
        SELECT COUNT(*) FROM edge_data e
        JOIN file_data s ON s.id = e.src_file_id
        JOIN file_data d ON d.id = e.dst_file_id
        WHERE s.commit_hash != e.commit_hash OR d.commit_hash != e.commit_hash
    """).fetchone()
    conn.close()
    assert counts == [("beef", 1), ("c0ffee", len(EXPECTED_EDGES))]
    assert cross == (0,)


def test_no_edge_list_writes_no_rows_and_a_null_count(keeper, tmp_path):
    sensor = NetworkRiskSensor()
    files = _build(sensor)
    db = tmp_path / "none.db"

    keeper.record_mission(files, [], {}, SESSION, str(db))

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM edge_data").fetchone() == (0,)
    assert conn.execute("SELECT network_edges_unrecorded FROM repo_data").fetchone() == (None,)
    conn.close()


def test_pre_2992_database_is_healed(keeper, tmp_path):
    """A DB written before #2992 has neither edge_data nor the repo_data column."""
    sensor = NetworkRiskSensor()
    files = _build(sensor)
    db = tmp_path / "legacy.db"
    keeper.record_mission(files, [], {}, SESSION, str(db))
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE edge_data")
    conn.execute("ALTER TABLE repo_data DROP COLUMN network_edges_unrecorded")
    conn.commit()
    conn.close()

    keeper.record_mission(files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges)

    assert len(_edges_by_path(db)) == len(EXPECTED_EDGES)


# ==============================================================================
# #3237: the mainframe call graph is in the dependency graph
# ==============================================================================
INVOCATIONS = [
    # app already imports lib: the CALL adds no second graph edge, only its edge_data row.
    {"src": "src/app.py", "dst": "src/lib.py", "edge_kind": "call", "weight": 1.0, "call_sites": 1},
    # island reaches util only by invocation: a new edge, at CALL_EDGE_WEIGHT, whatever its site count.
    {"src": "src/island.py", "dst": "src/util.py", "edge_kind": "exec", "weight": 3.0, "call_sites": 3},
]


def test_an_invocation_joins_the_graph_where_nothing_else_does(keeper, tmp_path):
    sensor = NetworkRiskSensor()
    files, _ = sensor.build_dependency_graph(copy.deepcopy(UNIVERSE), invocation_edges=INVOCATIONS)
    by_path = {f["path"]: f["telemetry"] for f in files}
    assert by_path["src/island.py"]["network_metrics"]["out_degree"] == 1
    assert by_path["src/util.py"]["popularity"] == 3  # app, lib and now island
    assert by_path["src/app.py"]["network_metrics"]["out_degree"] == 2  # lib is still one neighbour
    # The recorder writes the invocations from the resolver's own list, so they are not re-published.
    assert sensor.dependency_edges == EXPECTED_EDGES

    db = tmp_path / "calls.db"
    keeper.record_mission(
        files, [], {}, SESSION, str(db), dependency_edges=sensor.dependency_edges, invocation_edges=INVOCATIONS
    )
    rows = _edges_by_path(db)
    assert ("src/island.py", "src/util.py", "exec", 3.0, 3, 0) in rows and len(rows) == 5
    conn = sqlite3.connect(db)
    for path, links, popularity, out_n, in_n in conn.execute("""
        SELECT f.file_path, f.internal_dependency_links, f.popularity,
               (SELECT COUNT(DISTINCT e.dst_file_id) FROM edge_data e WHERE e.src_file_id = f.id),
               (SELECT COUNT(DISTINCT e.src_file_id) FROM edge_data e WHERE e.dst_file_id = f.id)
        FROM file_data f
    """):
        assert (links, popularity) == (out_n, in_n), path
    conn.close()
