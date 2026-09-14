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

from gitgalaxy.core.network_risk_sensor import HAS_NETWORKX, NetworkRiskSensor
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
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_digraph_mode_publishes_edges_matching_degrees():
    sensor = NetworkRiskSensor()
    files = _build(sensor)

    assert sensor.dependency_edges == EXPECTED_EDGES
    for f in files:
        nm = f["telemetry"]["network_metrics"]
        # DiGraph degree counts distinct neighbours: one per edge row.
        assert nm["out_degree"] == sum(e["src"] == f["path"] for e in sensor.dependency_edges)
        assert nm["in_degree"] == sum(e["dst"] == f["path"] for e in sensor.dependency_edges)


@patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False)
def test_zero_dependency_mode_publishes_the_same_edges():
    sensor = NetworkRiskSensor()
    files = _build(sensor)

    assert sensor.dependency_edges == EXPECTED_EDGES
    for f in files:
        nm = f["telemetry"]["network_metrics"]
        # #3024: distinct neighbours, one per edge row -- the DiGraph's meaning.
        assert nm["out_degree"] == sum(e["src"] == f["path"] for e in sensor.dependency_edges)
        assert nm["in_degree"] == sum(e["dst"] == f["path"] for e in sensor.dependency_edges)


@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_degree_family_is_identical_in_both_modes():
    """
    #3024: the degree-derived fields must not depend on whether networkx is
    installed. src/app.py imports src/lib.py twice -- the case that used to
    read out_degree 3 in zero-dependency mode against 2 with networkx.
    """
    degree_keys = ("in_degree", "out_degree", "producer_ratio", "ecosystem_role")

    full = {f["path"]: f for f in _build(NetworkRiskSensor())}
    with patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False):
        zero = {f["path"]: f for f in _build(NetworkRiskSensor())}

    assert zero["src/app.py"]["telemetry"]["network_metrics"]["out_degree"] == 2
    for path, f in full.items():
        fnm, znm = f["telemetry"]["network_metrics"], zero[path]["telemetry"]["network_metrics"]
        assert {k: znm[k] for k in degree_keys} == {k: fnm[k] for k in degree_keys}, path
        assert zero[path]["telemetry"]["popularity"] == f["telemetry"]["popularity"], path


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
    # Per file, the rows reconcile with the node summaries already in file_data.
    mismatches = conn.execute("""
        SELECT f.file_path, f.internal_dependency_links, f.popularity,
               (SELECT COUNT(*) FROM edge_data e WHERE e.src_file_id = f.id),
               (SELECT COUNT(*) FROM edge_data e WHERE e.dst_file_id = f.id)
        FROM file_data f
    """).fetchall()
    conn.close()
    if HAS_NETWORKX:
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
