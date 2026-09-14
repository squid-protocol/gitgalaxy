# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
# ==============================================================================
"""
The native graph engine (#3033): one integer-indexed CSR view of the resolved
import graph, built once per scan, that every graph metric reads instead of a
networkx DiGraph of string nodes and per-edge attribute dicts. Standard library
only, so every install computes the same numbers.

networkx is not a runtime dependency of anything here. It survives only as the
test-time oracle in tests/tools/graph_parity.py, which every algorithm in this
module must match: networkx's own call where GitGalaxy keeps its definition, or
networkx computing the tailored definition where #3033 chose a different one.
"""

from collections.abc import Iterable
from operator import mul, sub, truediv
from typing import Optional


def _bucket(keys: list[int], n: int) -> tuple[list[int], list[int]]:
    """
    Stable counting sort of edge ids by `keys` (each edge's src or dst node id):
    CSR offsets (length n + 1) and the edge ids in bucket order. Stable, so every
    node's run keeps input edge order. O(n + E).
    """
    offsets = [0] * (n + 1)
    for key in keys:
        offsets[key + 1] += 1
    for i in range(n):
        offsets[i + 1] += offsets[i]
    cursor = offsets[:n]
    order = [0] * len(keys)
    for edge, key in enumerate(keys):
        order[cursor[key]] = edge
        cursor[key] += 1
    return offsets, order


class GraphIndex:
    """
    #3034: compressed sparse row (CSR) adjacency of a directed, weighted graph.

    Node ids are positions in `nodes`: input order, a repeated node keeping its
    first position. Node v's outgoing edges are
    `out_targets[out_offsets[v]:out_offsets[v + 1]]` (with `out_weights` beside
    them) and its incoming edges `in_sources[in_offsets[v]:in_offsets[v + 1]]`
    (with `in_weights`). Each run keeps input edge order, so an algorithm that
    folds a node's edges sums them in the same order as a dict-of-lists built
    from the same edge list.

    Edges are distinct (src, dst) pairs between listed nodes, as
    NetworkRiskSensor._resolve_edges produces them; an endpoint that is not a
    node raises KeyError.
    """

    __slots__ = (
        "edge_count",
        "in_offsets",
        "in_sources",
        "in_weights",
        "node_id",
        "nodes",
        "out_offsets",
        "out_targets",
        "out_weight",
        "out_weights",
    )

    def __init__(self, nodes: Iterable[str], edges: Iterable[tuple[str, str, float]]) -> None:
        self.nodes: list[str] = list(dict.fromkeys(nodes))
        self.node_id: dict[str, int] = {node: i for i, node in enumerate(self.nodes)}
        n = len(self.nodes)

        src: list[int] = []
        dst: list[int] = []
        weight: list[float] = []
        for src_node, dst_node, edge_weight in edges:
            src.append(self.node_id[src_node])
            dst.append(self.node_id[dst_node])
            weight.append(edge_weight)
        self.edge_count = len(src)

        self.out_offsets, by_src = _bucket(src, n)
        self.out_targets = [dst[e] for e in by_src]
        self.out_weights = [weight[e] for e in by_src]
        self.in_offsets, by_dst = _bucket(dst, n)
        self.in_sources = [src[e] for e in by_dst]
        self.in_weights = [weight[e] for e in by_dst]

        # Total outgoing weight per node, accumulated in input edge order.
        self.out_weight = [0.0] * n
        for s, w in zip(src, weight):
            self.out_weight[s] += w


class WorkBudgetExceeded(Exception):
    """A graph algorithm spent its WorkBudget; its metric is not computed (None)."""


class WorkBudget:
    """
    #3034: the deterministic replacement for node-count cutoffs such as
    "no closeness above 1,500 files". An algorithm charges the elementary
    operations it performs (edges scanned, sources run), or an upper bound such
    as V * (V + E) before it starts, and stops once the total passes `limit`.

    It counts work, never wall-clock time. A timer would compute a metric on a
    fast runner and skip it on a slow one, and the golden masters would flake. A
    metric that exhausts its budget is None, never 0.0 (#3027).
    """

    __slots__ = ("limit", "spent")

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.spent = 0

    def charge(self, units: int) -> None:
        """Records `units` of work; raises WorkBudgetExceeded once the total passes the limit."""
        self.spent += units
        if self.spent > self.limit:
            raise WorkBudgetExceeded(f"spent {self.spent} of a {self.limit}-unit work budget")


def pagerank(index: GraphIndex, alpha: float = 0.85, max_iter: int = 100, tol: float = 1.0e-6) -> list[float]:
    """
    Weighted PageRank, one value per node id: the only PageRank the engine runs,
    in both modes (#3027; see NetworkRiskSensor._native_pagerank for why not
    nx.pagerank).

    Mirrors nx.pagerank's defaults and conventions:
    - alpha 0.85, uniform start and teleport
    - a dangling node's mass is spread uniformly
    - out-weights are normalised per node
    - converged once the L1 change is below N * tol; RuntimeError after max_iter

    #3034 moved it onto the CSR index without changing a single float operation
    or its order: each incoming share is still `x[u] * w / out_weight[u]`, summed
    per node in edge order, then `alpha * inflow + dangling_share + teleport`.
    The result is bit-identical to the dict-of-lists version it replaced, so
    neither golden master moved. The speed comes from running every per-edge and
    per-node pass as a C-level `map` over flat lists: 2.1 ms on the
    language-crucible graph (2,817 nodes, 1,354 edges), vs 7.0 ms before and
    3.1 ms for nx.pagerank (scipy), warm. O(max_iter * (N + E)).
    """
    n = len(index.nodes)
    if n == 0:
        return []
    out_weight = index.out_weight
    in_offsets = index.in_offsets
    in_sources = index.in_sources
    in_weights = index.in_weights

    source_out_weight = [out_weight[u] for u in in_sources]
    receivers = [v for v in range(n) if in_offsets[v + 1] > in_offsets[v]]
    runs = [slice(in_offsets[v], in_offsets[v + 1]) for v in receivers]
    dangling = [v for v in range(n) if out_weight[v] == 0.0]
    teleport = (1.0 - alpha) / n

    x = [1.0 / n] * n
    for _ in range(max_iter):
        dangling_share = alpha * sum(map(x.__getitem__, dangling)) / n
        shares = list(map(truediv, map(mul, map(x.__getitem__, in_sources), in_weights), source_out_weight))
        # A node nothing imports receives only the dangling share and the teleport.
        x_next = [dangling_share + teleport] * n
        for v, inflow in zip(receivers, map(sum, map(shares.__getitem__, runs))):
            x_next[v] = alpha * inflow + dangling_share + teleport
        err = sum(map(abs, map(sub, x_next, x)))
        x = x_next
        if err < n * tol:
            return x
    raise RuntimeError(f"pagerank failed to converge in {max_iter} iterations")


def closeness_and_path_length(
    index: GraphIndex, budget: Optional[WorkBudget] = None
) -> tuple[list[float], Optional[float]]:
    """
    #3037: both hop-count path metrics come from ONE breadth-first search per node
    over the reversed graph (each node's incoming runs), since both need the same
    distances. Edge weight plays no part: it is a PageRank strength, and
    networkx's weighted paths would read it as distance, which is backwards
    (#3033).

    - **Closeness**, one value per node id: networkx's directed closeness,
      exactly (strict parity with `nx.closeness_centrality(G)`). It measures
      distance TO a node, i.e. how directly the files that transitively import
      it reach it. With r such files at summed hop count h, closeness is
      `(r / h) * (r / (N - 1))`, the Wasserman-Faust form networkx applies
      (wf_improved=True). It is 0.0 when nothing reaches the node.
    - **Average path length**: the mean hop count over every ordered pair (A, B)
      where A transitively imports B, across all files. It is None when no file
      imports another.
      - This replaces the mean over the largest UNDIRECTED component (#3033's
        tailoring decisions). That version ignored import direction and covered
        22.5% of the language-crucible files.
      - Each pair is counted once, from B's search, so both sums are exact
        integers.

    Each node's search charges `budget` the incoming edges it scanned, plus one
    for the node itself. A graph too large to finish raises WorkBudgetExceeded
    instead of stalling the scan. Worst case O(N * (N + E)), but an import
    graph's searches are short. On the language-crucible graph (2,817 nodes,
    1,354 edges), both metrics together take 1.7 ms warm. The comparisons:
    - 12.9 ms for nx.closeness_centrality
    - about 1.2 s for the undirected path length it replaced, which was
      skipped above 5,000 files
    """
    n = len(index.nodes)
    in_offsets = index.in_offsets
    in_sources = index.in_sources
    closeness = [0.0] * n
    total_hops = 0
    total_pairs = 0
    depth_of = [-1] * n  # -1 = not reached by the current search
    for target in range(n):
        depth_of[target] = 0
        reached = [target]
        frontier = [target]
        depth = 0
        hops = 0
        scanned = 1
        while frontier:
            depth += 1
            next_frontier = []
            for node in frontier:
                start, stop = in_offsets[node], in_offsets[node + 1]
                scanned += stop - start
                for importer in in_sources[start:stop]:
                    if depth_of[importer] < 0:
                        depth_of[importer] = depth
                        next_frontier.append(importer)
            hops += depth * len(next_frontier)
            reached += next_frontier
            frontier = next_frontier
        for node in reached:
            depth_of[node] = -1
        if budget is not None:
            budget.charge(scanned)

        importers = len(reached) - 1
        if hops > 0 and n > 1:
            closeness[target] = (importers / hops) * (importers / (n - 1))
        total_hops += hops
        total_pairs += importers
    return closeness, (total_hops / total_pairs if total_pairs else None)


def nodes_in_cycles(index: GraphIndex) -> int:
    """
    #3035: how many nodes lie on a dependency cycle, i.e. sit in a strongly
    connected component of more than one node. Strict parity with
    `sum(len(c) for c in nx.strongly_connected_components(G) if len(c) > 1)`.

    Tarjan's algorithm, run iteratively with an explicit work stack of
    (node, next out-edge position), so a long import chain cannot hit
    Python's recursion limit. O(N + E).
    """
    n = len(index.nodes)
    out_offsets = index.out_offsets
    out_targets = index.out_targets
    order = [-1] * n  # discovery order; -1 = not yet visited
    low = [0] * n
    on_stack = [False] * n
    stack: list[int] = []
    counter = 0
    in_cycles = 0
    for root in range(n):
        if order[root] != -1:
            continue
        order[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = True
        work = [(root, out_offsets[root])]
        while work:
            node, edge = work[-1]
            if edge < out_offsets[node + 1]:
                work[-1] = (node, edge + 1)
                target = out_targets[edge]
                if order[target] == -1:
                    order[target] = low[target] = counter
                    counter += 1
                    stack.append(target)
                    on_stack[target] = True
                    work.append((target, out_offsets[target]))
                elif on_stack[target] and order[target] < low[node]:
                    low[node] = order[target]
                continue
            work.pop()
            if work:
                caller = work[-1][0]
                if low[node] < low[caller]:
                    low[caller] = low[node]
            if low[node] == order[node]:  # node roots a component: pop it
                size = 0
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    size += 1
                    if member == node:
                        break
                if size > 1:
                    in_cycles += size
    return in_cycles


def _undirected_neighbors(index: GraphIndex) -> list[list[int]]:
    """Each node's distinct neighbours, direction ignored: the adjacency of networkx's `G.to_undirected()`."""
    out_offsets, out_targets = index.out_offsets, index.out_targets
    in_offsets, in_sources = index.in_offsets, index.in_sources
    return [
        list(
            dict.fromkeys(
                out_targets[out_offsets[v] : out_offsets[v + 1]] + in_sources[in_offsets[v] : in_offsets[v + 1]]
            )
        )
        for v in range(len(index.nodes))
    ]


def articulation_point_count(index: GraphIndex) -> int:
    """
    #3035: how many files are articulation points of the undirected import graph:
    removing one disconnects files that were connected. Strict parity with
    `len(list(nx.articulation_points(G.to_undirected())))`.

    This is Hopcroft-Tarjan low-link, run iteratively with an explicit stack of
    (node, parent, next neighbour position), so it never recurses. The parent is
    skipped as a node, not as an edge, so a file pair importing each other forms
    one undirected edge, exactly as in `G.to_undirected()`. O(N + E).
    """
    neighbors = _undirected_neighbors(index)
    n = len(neighbors)
    disc = [-1] * n  # discovery time; -1 = not yet visited
    low = [0] * n
    is_cut = [False] * n
    clock = 0
    for root in range(n):
        if disc[root] != -1:
            continue
        disc[root] = low[root] = clock
        clock += 1
        root_children = 0
        work = [(root, -1, 0)]
        while work:
            node, parent, position = work[-1]
            adjacent = neighbors[node]
            if position < len(adjacent):
                work[-1] = (node, parent, position + 1)
                other = adjacent[position]
                if disc[other] == -1:
                    disc[other] = low[other] = clock
                    clock += 1
                    if node == root:
                        root_children += 1
                    work.append((other, node, 0))
                elif other != parent and disc[other] < low[node]:
                    low[node] = disc[other]
                continue
            work.pop()
            if work:
                caller = work[-1][0]
                if low[node] < low[caller]:
                    low[caller] = low[node]
                if caller != root and low[node] >= disc[caller]:
                    is_cut[caller] = True
        if root_children > 1:  # a DFS root is a cut vertex only with two or more subtrees
            is_cut[root] = True
    return sum(is_cut)
