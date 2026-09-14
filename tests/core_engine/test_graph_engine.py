"""
#3034: the native graph engine's CSR index, work budget and PageRank, plus the
networkx parity harness every native graph metric is checked with.
"""

import math
import os
import sqlite3
import sys

import pytest

from gitgalaxy.core import graph_engine
from gitgalaxy.core.graph_engine import GraphIndex, WorkBudget, WorkBudgetExceeded, pagerank

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import graph_parity  # noqa: E402

needs_oracle = pytest.mark.skipif(graph_parity.nx is None, reason="networkx is the parity oracle")


# ==============================================================================
# CSR INDEX
# ==============================================================================
def test_index_layout_keeps_node_and_edge_order():
    index = GraphIndex(
        ["a", "b", "c", "a", "d"],  # a repeated node keeps its first position
        [("b", "a", 1.0), ("c", "a", 1.5), ("a", "c", 2.0), ("b", "c", 1.0)],
    )

    assert index.nodes == ["a", "b", "c", "d"]
    assert index.node_id == {"a": 0, "b": 1, "c": 2, "d": 3}
    assert index.edge_count == 4
    # out runs: a -> [c]; b -> [a, c] (input edge order); c -> [a]; d -> []
    assert index.out_offsets == [0, 1, 3, 4, 4]
    assert index.out_targets == [2, 0, 2, 0]
    assert index.out_weights == [2.0, 1.0, 1.0, 1.5]
    # in runs: a <- [b, c]; b <- []; c <- [a, b]; d <- []
    assert index.in_offsets == [0, 2, 2, 4, 4]
    assert index.in_sources == [1, 2, 0, 1]
    assert index.in_weights == [1.0, 1.5, 2.0, 1.0]
    assert index.out_weight == [2.0, 2.0, 1.5, 0.0]


def test_index_of_empty_graph():
    index = GraphIndex([], [])
    assert (index.nodes, index.edge_count, index.out_offsets, index.in_offsets) == ([], 0, [0], [0])


def test_index_rejects_an_edge_to_an_unlisted_node():
    with pytest.raises(KeyError):
        GraphIndex(["a"], [("a", "b", 1.0)])


# ==============================================================================
# WORK BUDGET
# ==============================================================================
def test_work_budget_allows_up_to_the_limit_and_raises_past_it():
    budget = WorkBudget(10)
    budget.charge(4)
    budget.charge(6)  # exactly at the limit is allowed
    assert budget.spent == 10
    with pytest.raises(WorkBudgetExceeded):
        budget.charge(1)


# ==============================================================================
# PAGERANK
# ==============================================================================
def _dict_of_lists_pagerank(nodes, edges, alpha=0.85, max_iter=100, tol=1.0e-6):
    """The #3027 implementation #3034 replaced, kept as the bit-identity reference."""
    n = len(nodes)
    out_weight = dict.fromkeys(nodes, 0.0)
    incoming = {node: [] for node in nodes}
    for src, dst, weight in edges:
        out_weight[src] += weight
        incoming[dst].append((src, weight))
    dangling = [node for node in nodes if out_weight[node] == 0.0]
    x = dict.fromkeys(nodes, 1.0 / n)
    for _ in range(max_iter):
        dangling_share = alpha * sum(x[node] for node in dangling) / n
        teleport = (1.0 - alpha) / n
        x_next = {
            v: alpha * sum(x[u] * w / out_weight[u] for u, w in incoming[v]) + dangling_share + teleport for v in nodes
        }
        err = sum(abs(x_next[node] - x[node]) for node in nodes)
        x = x_next
        if err < n * tol:
            return [x[node] for node in nodes]
    raise RuntimeError


@pytest.mark.parametrize("seed", range(25))
def test_pagerank_is_bit_identical_to_the_implementation_it_replaced(seed):
    """Same float operations in the same order: the golden masters must not move (#3034)."""
    nodes, edges = graph_parity.random_graph(seed)
    assert pagerank(GraphIndex(nodes, edges)) == _dict_of_lists_pagerank(nodes, edges)


def test_pagerank_edge_cases():
    assert pagerank(GraphIndex([], [])) == []
    assert pagerank(GraphIndex(["a.py", "b.py"], [])) == pytest.approx([0.5, 0.5])
    with pytest.raises(RuntimeError):
        pagerank(GraphIndex(["a", "b", "c"], [("a", "b", 1.0), ("b", "c", 1.0)]), max_iter=1)


# ==============================================================================
# PARITY HARNESS: every registered native metric against its networkx oracle
# ==============================================================================
@needs_oracle
@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("name", sorted(graph_parity.METRICS))
def test_native_metric_matches_networkx_oracle(name, seed):
    metric = graph_parity.METRICS[name]
    nodes, edges = graph_parity.random_graph(seed)
    parity = graph_parity.check(metric, nodes, edges)
    assert parity.equal, (name, metric.oracle_mode, seed, parity)


def test_cycle_and_cut_searches_never_recurse():
    """#3035: a 5,000-file cycle and chain run the iterative searches far past the recursion limit."""
    names = [f"f{i}" for i in range(5000)]
    chain = [(names[i], names[i + 1], 1.0) for i in range(4999)]
    ring = GraphIndex(names, [*chain, (names[-1], names[0], 1.0)])
    line = GraphIndex(names, chain)
    assert (graph_engine.nodes_in_cycles(ring), graph_engine.articulation_point_count(ring)) == (5000, 0)
    assert (graph_engine.nodes_in_cycles(line), graph_engine.articulation_point_count(line)) == (0, 4998)


def test_mutual_import_is_one_undirected_edge():
    """#3035: a <-> b is one undirected edge, as in G.to_undirected(), so in a - b - c only b is a cut vertex."""
    index = GraphIndex(["a", "b", "c"], [("a", "b", 1.0), ("b", "a", 1.0), ("b", "c", 1.0)])
    assert graph_engine.nodes_in_cycles(index) == 2
    assert graph_engine.articulation_point_count(index) == 1


def test_assortativity_is_nan_where_undefined():
    """#3036: no edges, or a degree that never varies, leaves the correlation undefined: NaN, as in networkx."""
    assert math.isnan(graph_engine.degree_assortativity(GraphIndex(["a", "b"], [])))
    hub = GraphIndex(["h", "a", "b"], [("a", "h", 1.0), ("b", "h", 1.0)])
    assert math.isnan(graph_engine.degree_assortativity(hub))


@needs_oracle
@pytest.mark.parametrize("seed", range(25))
def test_betweenness_is_bit_identical_to_networkx_exact(seed):
    """#3038 mirrors networkx's Brandes step for step: identical floats, not merely 6-dp equal."""
    nodes, edges = graph_parity.random_graph(seed)
    reference = graph_parity.nx.betweenness_centrality(graph_parity.to_networkx(nodes, edges))
    assert graph_engine.betweenness_centrality(GraphIndex(nodes, edges)) == [reference[v] for v in nodes]


def test_betweenness_stops_at_its_work_budget():
    names = [f"f{i}" for i in range(50)]
    index = GraphIndex(names, [(names[i], names[i + 1], 1.0) for i in range(49)])
    with pytest.raises(WorkBudgetExceeded):
        graph_engine.betweenness_centrality(index, WorkBudget(100))


@needs_oracle
@pytest.mark.parametrize("seed", range(25))
def test_louvain_communities_are_identical_to_networkx(seed):
    """#3039 is a faithful port: the same communities, in the same order, not merely the same modularity."""
    nodes, edges = graph_parity.random_graph(seed)
    index = GraphIndex(nodes, edges)
    undirected = graph_parity.to_networkx(nodes, edges).to_undirected()
    reference = graph_parity.nx.algorithms.community.louvain_communities(undirected, seed=42)
    ours = graph_engine.louvain_communities(index)
    assert [{index.nodes[v] for v in community} for community in ours] == reference


def test_louvain_modularity_edge_cases():
    """No imports: networkx divides by zero and the engine records None. A budget too small raises."""
    assert graph_engine.louvain_modularity(GraphIndex(["a", "b"], [])) is None
    assert graph_engine.louvain_modularity(GraphIndex([], [])) is None
    names = [f"f{i}" for i in range(30)]
    ring = GraphIndex(names, [(names[i], names[(i + 1) % 30], 1.0) for i in range(30)])
    with pytest.raises(WorkBudgetExceeded):
        graph_engine.louvain_modularity(ring, budget=WorkBudget(10))


def test_every_metric_declares_an_oracle_mode():
    assert {m.oracle_mode for m in graph_parity.METRICS.values()} <= {"strict", "tailored"}


def test_harness_catches_a_disagreement():
    """The harness must not be vacuous: a value off in the stored precision fails."""
    assert graph_parity.compare({"a": 0.1234561}, {"a": 0.1234571}, 6).equal is False
    assert graph_parity.compare({"a": 0.1234561}, {"a": 0.12345612}, 6).equal is True
    assert graph_parity.compare({"a": 1.0}, {"b": 1.0}, 6).equal is False  # different nodes
    assert graph_parity.compare(None, 0.0, 4).equal is False  # "not computed" is not 0.0
    assert graph_parity.compare(None, None, 4).equal is True


def test_scan_graph_reads_a_galaxyscope_db(tmp_path):
    db = tmp_path / "scan.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE file_data (id INTEGER PRIMARY KEY, file_path TEXT)")
    conn.execute(
        "CREATE TABLE edge_data (id INTEGER PRIMARY KEY, src_file_id INTEGER, dst_file_id INTEGER, weight REAL)"
    )
    conn.executemany("INSERT INTO file_data VALUES (?, ?)", [(1, "a.py"), (2, "b.py"), (3, "c.py")])
    conn.executemany("INSERT INTO edge_data VALUES (?, ?, ?, ?)", [(1, 3, 1, 1.5), (2, 1, 2, 1.0)])
    conn.commit()
    conn.close()

    assert graph_parity.scan_graph(str(db)) == (
        ["a.py", "b.py", "c.py"],
        [("c.py", "a.py", 1.5), ("a.py", "b.py", 1.0)],
    )
