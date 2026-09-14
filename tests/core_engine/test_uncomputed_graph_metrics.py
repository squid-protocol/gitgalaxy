"""
#3027: a graph metric that was not computed is None -- never a 0.0 placeholder
that every consumer reads as a measurement -- and zero-dependency mode computes
PageRank natively instead of skipping it.
"""

import random
import sqlite3
from unittest.mock import patch

import pytest

from gitgalaxy.core.network_risk_sensor import HAS_NETWORKX, NetworkRiskSensor, _pagerank
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.recorders.record_keeper import RecordKeeper

NO_NETWORKX = patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False)
PAGERANK_FAMILY = ("pagerank_score", "normalized_blast_radius", "systemic_threat_vector")


GRAPH = [
    ("src/app.py", ["src/lib.py", ("src/lib.py", "h"), "src/util.py"]),  # a repeat + an entity import
    ("src/lib.py", ["src/util.py", "src/cycle.py"]),
    ("src/cycle.py", ["src/lib.py"]),  # a cycle
    ("src/util.py", []),  # dangling
    ("src/island.py", []),  # isolated
]


def _files():
    """A fresh copy per build (the sensor mutates its input), each with a distinct risk vector."""
    n_risk = len(NetworkRiskSensor().RISK_SCHEMA)
    return [
        {"path": path, "lang_id": "python", "raw_imports": list(imports), "risk_vector": [10.0 * (i + 1)] * n_risk}
        for i, (path, imports) in enumerate(GRAPH)
    ]


def _metrics(files):
    return {f["path"]: f["telemetry"]["network_metrics"] for f in files}


def _random_graph(seed, n=60, m=150):
    rng = random.Random(seed)
    nodes = [f"n{i}.py" for i in range(n)]
    edges = {}
    while len(edges) < m:
        src, dst = rng.sample(nodes, 2)
        edges[(src, dst)] = rng.choice([1.0, 1.5, 2.5])
    return nodes, [(s, d, w) for (s, d), w in edges.items()]


# ==============================================================================
# NATIVE PAGERANK
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX as the reference")
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_native_pagerank_matches_networkx(seed):
    import networkx as nx

    nodes, edges = _random_graph(seed)
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_weighted_edges_from(edges)

    reference = nx.pagerank(graph, weight="weight")
    ours = _pagerank(nodes, edges)

    assert max(abs(ours[n] - reference[n]) for n in nodes) < 1e-12
    # The sensor stores 6 dp: the two modes must agree at the precision recorded.
    assert {n: round(ours[n], 6) for n in nodes} == {n: round(reference[n], 6) for n in nodes}


def test_native_pagerank_edge_cases():
    assert _pagerank([], []) == {}
    assert _pagerank(["a.py", "b.py"], []) == pytest.approx({"a.py": 0.5, "b.py": 0.5})
    with pytest.raises(RuntimeError):
        _pagerank(["a", "b", "c"], [("a", "b", 1.0), ("b", "c", 1.0)], max_iter=1)


# ==============================================================================
# SENSOR: identical PageRank family in both modes, None for the rest
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX for the full-precision side")
def test_zero_dependency_pagerank_family_matches_networkx():
    full = _metrics(NetworkRiskSensor().build_dependency_graph(_files())[0])
    with NO_NETWORKX:
        zero = _metrics(NetworkRiskSensor().build_dependency_graph(_files())[0])

    for path, full_metrics in full.items():
        assert {k: zero[path][k] for k in PAGERANK_FAMILY} == {k: full_metrics[k] for k in PAGERANK_FAMILY}, path
        assert zero[path]["normalized_blast_radius"] is not None
        assert zero[path]["betweenness_score"] is None, path
        assert zero[path]["closeness_score"] is None, path


@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_closeness_skipped_for_scale_is_none_not_zero():
    """Above 1,500 nodes closeness is bypassed: that is "not computed", not 0.0."""
    files = [
        {"path": f"f{i}.py", "lang_id": "python", "raw_imports": [f"f{i + 1}.py"] if i < 1500 else []}
        for i in range(1501)
    ]
    metrics = _metrics(NetworkRiskSensor().build_dependency_graph(files)[0])
    assert all(m["closeness_score"] is None for m in metrics.values())
    assert all(m["pagerank_score"] is not None for m in metrics.values())


# ==============================================================================
# RECORDER: zero-dependency scans keep the native PageRank (NULL only if uncomputed)
# ==============================================================================
def test_zero_dependency_db_records_native_pagerank(tmp_path):
    with NO_NETWORKX:
        files, macro = NetworkRiskSensor().build_dependency_graph(_files())
    db = tmp_path / "zero.db"
    session = {"target": "t", "git_audit": {"commit_hash": "c"}, "zero_dependency_mode": True}

    RecordKeeper().record_mission(files, [], {"network_macro": macro}, session, str(db))

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT pagerank_score, normalized_blast_radius, betweenness_score, closeness_score, producer_ratio "
        "FROM file_data"
    ).fetchall()
    repo = conn.execute("SELECT network_modularity, is_zero_dependency_mode FROM repo_data").fetchone()
    conn.close()

    assert rows and all(pr is not None and blast is not None for pr, blast, *_ in rows)
    assert all(btw is None and close is None for _, _, btw, close, _ in rows)
    assert all(ratio is not None for *_, ratio in rows)  # exact since #3024, no longer NULLed
    assert repo == (None, 1)


# ==============================================================================
# LLM BRIEF: n/a, never 0.0
# ==============================================================================
def _brief(network_macro):
    mock_schemas = {"RISK_SCHEMA": ["tech_debt"], "SIGNAL_SCHEMA": ["io"], "EXPOSURE_LABELS": {}}
    with patch("gitgalaxy.recorders.llm_recorder.config.RECORDING_SCHEMAS", mock_schemas):
        recorder = LLMRecorder()
    session = {"engine": "t", "target": "t", "git_audit": {}, "zero_dependency_mode": False}
    return recorder._build_markdown([], [], {"network_macro": network_macro}, session, {})


def test_brief_macro_table_renders_uncomputed_as_na():
    md = _brief(
        dict.fromkeys(["modularity", "assortativity", "cyclic_density", "avg_path_length", "articulation_points"])
    )
    assert "MACRO-NETWORK TOPOLOGY" in md
    assert md.count("n/a (not computed)") == 5
    assert "| Modularity | 0.0 |" not in md
    assert "| Cyclic Density | 0.0% |" not in md


def test_brief_macro_table_still_renders_real_values():
    md = _brief(
        {
            "modularity": 0.8,
            "assortativity": -0.1,
            "cyclic_density": 0.25,
            "avg_path_length": 2.5,
            "articulation_points": 3,
        }
    )
    assert "| Modularity | 0.8 |" in md
    assert "| Cyclic Density | 25.0% |" in md
    assert "| Articulation Pts | 3 |" in md
    assert "n/a (not computed)" not in md
