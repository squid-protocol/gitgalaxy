"""
#3034: the parity and benchmark harness for the native graph engine
(gitgalaxy/core/graph_engine.py).

networkx is the ORACLE here, never a runtime dependency. Every native metric is
registered in METRICS with the networkx call it must match and the precision the
engine stores it at. Each metric has an oracle mode:

- "strict": networkx's own call, for a metric whose definition GitGalaxy keeps
  (PageRank, SCC, articulation points, assortativity, Louvain).
- "tailored": networkx computing the definition GitGalaxy chose instead, per the
  tailoring decisions on #3033. Examples: exact unweighted betweenness instead of
  100-source sampling, and path length over directed reachable pairs.

Used two ways:
- tests/core_engine/test_graph_engine.py checks every metric on seeded random graphs.
- As a CLI, it checks parity on a real scan's graph (a galaxyscope DB's edge_data
  table) and benchmarks native against networkx, warm, best of --repeat runs:

      python tests/tools/graph_parity.py --db <scan>_galaxy_master.db

  It exits 1 if any metric disagrees with its oracle.
"""

import argparse
import random
import sqlite3
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from gitgalaxy.core.graph_engine import GraphIndex, closeness_and_path_length, pagerank

try:
    import networkx as nx
except ImportError:  # the oracle is optional; tests skip without it
    nx = None

Edge = tuple[str, str, float]

# Weights _resolve_edges produces: 1.0 per plain import plus 1.5 per entity import, summed.
EDGE_WEIGHTS = (1.0, 1.5, 2.0, 2.5, 3.0)


@dataclass(frozen=True)
class Metric:
    """A native metric, the networkx oracle it must match, and the decimal places the engine stores."""

    oracle_mode: str  # "strict" or "tailored"
    native: Callable[[GraphIndex], Any]  # dict {node: value} for per-node metrics, else a scalar
    oracle: Callable[[Any], Any]  # same shape, computed by networkx on the equivalent nx.DiGraph
    places: int


def _reachable_pair_path_length(graph: Any) -> Optional[float]:
    """#3037's tailored definition: mean hops over every ordered pair (A, B) where A reaches B; None if none."""
    hops = pairs = 0
    for source in graph:
        for target, distance in nx.single_source_shortest_path_length(graph, source).items():
            if target != source:
                hops += distance
                pairs += 1
    return hops / pairs if pairs else None


METRICS: dict[str, Metric] = {
    "pagerank": Metric(
        oracle_mode="strict",
        native=lambda index: dict(zip(index.nodes, pagerank(index))),
        oracle=lambda graph: nx.pagerank(graph, weight="weight"),
        places=6,  # pagerank_score is stored at 6 dp
    ),
    "closeness": Metric(
        oracle_mode="strict",
        native=lambda index: dict(zip(index.nodes, closeness_and_path_length(index)[0])),
        oracle=lambda graph: nx.closeness_centrality(graph),
        places=6,  # closeness_score
    ),
    "avg_path_length": Metric(
        oracle_mode="tailored",  # networkx's own call is the largest undirected component
        native=lambda index: closeness_and_path_length(index)[1],
        oracle=_reachable_pair_path_length,
        places=4,  # repo_data.network_avg_path_length
    ),
}


def random_graph(seed: int) -> tuple[list[str], list[Edge]]:
    """
    A seeded random directed graph shaped like an import graph: distinct (src, dst)
    pairs, no self-loops, and the sensor's edge weights. The size and density vary
    with the seed, so cycles, dangling nodes, isolated nodes, the single-node graph
    and the edgeless graph all come up.
    """
    rng = random.Random(seed)
    n = rng.randint(1, 80)
    nodes = [f"n{i}.py" for i in range(n)]
    m = rng.randint(0, min(n * (n - 1), 3 * n))
    edges: dict[tuple[str, str], float] = {}
    while len(edges) < m:
        src, dst = rng.sample(nodes, 2)
        edges[(src, dst)] = rng.choice(EDGE_WEIGHTS)
    return nodes, [(src, dst, weight) for (src, dst), weight in edges.items()]


def scan_graph(db_path: str) -> tuple[list[str], list[Edge]]:
    """A real scan's import graph from a galaxyscope DB: file_data rows in id order, edge_data edges (#2992)."""
    conn = sqlite3.connect(db_path)
    try:
        path_of = dict(conn.execute("SELECT id, file_path FROM file_data ORDER BY id"))
        edges = [
            (path_of[src], path_of[dst], weight)
            for src, dst, weight in conn.execute("SELECT src_file_id, dst_file_id, weight FROM edge_data ORDER BY id")
        ]
    finally:
        conn.close()
    return list(path_of.values()), edges


def to_networkx(nodes: list[str], edges: list[Edge]) -> Any:
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_weighted_edges_from(edges)
    return graph


@dataclass(frozen=True)
class Parity:
    equal: bool  # equal at the stored precision (and on the same keys / both None)
    max_abs_diff: Optional[float]  # None when the values are not both numeric


def compare(native: Any, oracle: Any, places: int) -> Parity:
    """Parity at `places` decimals for a scalar or a {node: value} dict; None only equals None."""
    if isinstance(native, dict) or isinstance(oracle, dict):
        if not (isinstance(native, dict) and isinstance(oracle, dict)) or native.keys() != oracle.keys():
            return Parity(False, None)
        results = [compare(native[key], oracle[key], places) for key in native]
        diffs = [r.max_abs_diff for r in results if r.max_abs_diff is not None]
        return Parity(all(r.equal for r in results), max(diffs, default=0.0))
    if native is None or oracle is None:
        return Parity(native is None and oracle is None, None)
    return Parity(round(native, places) == round(oracle, places), abs(native - oracle))


def check(metric: Metric, nodes: list[str], edges: list[Edge]) -> Parity:
    return compare(metric.native(GraphIndex(nodes, edges)), metric.oracle(to_networkx(nodes, edges)), metric.places)


def _best_ms(fn: Callable[[], Any], repeat: int) -> float:
    fn()  # warm: first-call imports (networkx's scipy backend) are not the algorithm's cost
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best * 1000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="a galaxyscope *_galaxy_master.db with an edge_data table")
    parser.add_argument("--repeat", type=int, default=15, help="timed runs per measurement (best is reported)")
    parser.add_argument("--metric", choices=sorted(METRICS), action="append", help="default: every metric")
    args = parser.parse_args()
    if nx is None:
        print("networkx is the oracle: pip install networkx", file=sys.stderr)
        return 2

    nodes, edges = scan_graph(args.db)
    index_ms = _best_ms(lambda: GraphIndex(nodes, edges), args.repeat)
    print(f"graph: V={len(nodes)} E={len(edges)}  index build {index_ms:.2f} ms\n")
    print(f"{'metric':<16} {'oracle':<9} {'parity':<7} {'max |diff|':>11} {'native ms':>10} {'networkx ms':>12}")

    index = GraphIndex(nodes, edges)
    graph = to_networkx(nodes, edges)
    failed = False
    for name in args.metric or sorted(METRICS):
        metric = METRICS[name]
        parity = compare(metric.native(index), metric.oracle(graph), metric.places)
        failed |= not parity.equal
        diff = "n/a" if parity.max_abs_diff is None else f"{parity.max_abs_diff:.1e}"
        native_ms = _best_ms(lambda: metric.native(index), args.repeat)
        oracle_ms = _best_ms(lambda: metric.oracle(graph), args.repeat)
        print(
            f"{name:<16} {metric.oracle_mode:<9} {'OK' if parity.equal else 'FAIL':<7} {diff:>11} "
            f"{native_ms:>10.2f} {oracle_ms:>12.2f}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
