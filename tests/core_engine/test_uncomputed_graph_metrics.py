"""
#3027: a graph metric that was not computed is None -- never a 0.0 placeholder
that every consumer reads as a measurement -- and zero-dependency mode computes
PageRank natively instead of skipping it.
"""

import sqlite3
from unittest.mock import patch

import pytest

from gitgalaxy.core.network_risk_sensor import HAS_NETWORKX, NetworkRiskSensor
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


# The native PageRank itself, and its networkx parity, are tested in test_graph_engine.py (#3034).


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
        # #3037/#3038: betweenness and closeness are native too, so identical in both modes.
        assert zero[path]["betweenness_score"] is not None, path
        assert zero[path]["betweenness_score"] == full_metrics["betweenness_score"], path
        assert zero[path]["closeness_score"] is not None, path
        assert zero[path]["closeness_score"] == full_metrics["closeness_score"], path


@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX for the full-precision side")
def test_full_precision_runs_the_native_pagerank_not_networkx():
    """
    One implementation in both modes: full precision must never call nx.pagerank
    (a version-dependent, numpy/scipy-backed routine networkx does not install),
    and both modes must produce the SAME floats, not just the same rounding.
    """
    with patch("networkx.pagerank", side_effect=AssertionError("nx.pagerank must not be called")):
        full_files, _ = NetworkRiskSensor().build_dependency_graph(_files())
    with NO_NETWORKX:
        zero_files, _ = NetworkRiskSensor().build_dependency_graph(_files())

    full, zero = _metrics(full_files), _metrics(zero_files)
    for path in full:
        for key in PAGERANK_FAMILY:
            assert full[path][key] == zero[path][key], (path, key)
        assert full[path]["pagerank_score"] is not None


def _chain(n):
    """f0 imports f1 imports ... f(n-1): the longest paths a graph of n files can have."""
    return [
        {"path": f"f{i}.py", "lang_id": "python", "raw_imports": [f"f{i + 1}.py"] if i < n - 1 else []}
        for i in range(n)
    ]


@pytest.mark.parametrize("networkx_present", [True, False])
def test_path_metrics_are_computed_above_the_old_node_cutoffs(networkx_present):
    """
    #3037: closeness used to be skipped above 1,500 files, and path length above
    5,000. Both are now computed at every size and in both modes, bounded only by
    the work budget. The long chain here also shows the search is iterative.
    """
    if networkx_present and not HAS_NETWORKX:
        pytest.skip("Requires NetworkX")
    n = 1501
    with patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", networkx_present and HAS_NETWORKX):
        files, macro = NetworkRiskSensor().build_dependency_graph(_chain(n))
    metrics = _metrics(files)

    # The chain's end is reached by f(i) at n-1-i hops: closeness = (r/h) * (r/(n-1)).
    r = n - 1
    assert metrics[f"f{n - 1}.py"]["closeness_score"] == round((r / (r * (r + 1) // 2)) * (r / (n - 1)), 6)
    assert metrics["f0.py"]["closeness_score"] == 0.0  # nothing imports it: measured, not skipped
    # Every ordered pair i < j is reachable at j - i hops: the mean is (n + 1) / 3.
    assert macro["avg_path_length"] == round((n + 1) / 3, 4)


def test_path_metrics_past_the_work_budget_are_none_not_zero():
    """A graph too large for the budget leaves closeness and path length "not computed", never 0.0."""
    with patch("gitgalaxy.core.network_risk_sensor.PATH_METRICS_WORK_BUDGET", 100):
        files, macro = NetworkRiskSensor().build_dependency_graph(_chain(50))
    metrics = _metrics(files)
    assert all(m["closeness_score"] is None for m in metrics.values())
    assert macro["avg_path_length"] is None
    assert all(m["pagerank_score"] is not None for m in metrics.values())


def test_path_length_of_a_graph_without_imports_is_none():
    """No file imports another: there is no reachable pair to average over, so None."""
    files, macro = NetworkRiskSensor().build_dependency_graph(
        [{"path": f"f{i}.py", "lang_id": "python", "raw_imports": []} for i in range(3)]
    )
    assert macro["avg_path_length"] is None
    assert all(m["closeness_score"] == 0.0 for m in _metrics(files).values())


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
    assert all(btw is not None and close is not None for _, _, btw, close, _ in rows)  # native: #3037, #3038
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
