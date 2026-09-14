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

import math
import random
from collections import defaultdict
from collections.abc import Iterable, Iterator
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


def strongly_connected_components(index: GraphIndex) -> tuple[list[int], int]:
    """
    #3035/#3040: each node's strongly connected component id, and how many
    components there are.

    Tarjan's algorithm, run iteratively with an explicit work stack of
    (node, next out-edge position), so a long import chain cannot hit
    Python's recursion limit. Components are numbered in the order Tarjan
    completes them. That is a reverse topological order of the condensation:
    every component a component imports has a smaller id. O(N + E).
    """
    n = len(index.nodes)
    out_offsets = index.out_offsets
    out_targets = index.out_targets
    order = [-1] * n  # discovery order; -1 = not yet visited
    low = [0] * n
    on_stack = [False] * n
    component = [-1] * n
    stack: list[int] = []
    counter = 0
    count = 0
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
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component[member] = count
                    if member == node:
                        break
                count += 1
    return component, count


def nodes_in_cycles(index: GraphIndex) -> int:
    """
    #3035: how many nodes lie on a dependency cycle, i.e. sit in a strongly
    connected component of more than one node. Strict parity with
    `sum(len(c) for c in nx.strongly_connected_components(G) if len(c) > 1)`.
    """
    component, count = strongly_connected_components(index)
    sizes = [0] * count
    for c in component:
        sizes[c] += 1
    return sum(size for size in sizes if size > 1)


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


def degree_assortativity(index: GraphIndex) -> float:
    """
    #3036: degree assortativity, the Pearson correlation over every edge u -> v
    of (out-degree of u, in-degree of v). Strict parity with networkx's default
    `nx.degree_assortativity_coefficient(G)` (x="out", y="in", unweighted), with
    no numpy. networkx's routine imports numpy, which networkx does not install,
    so with networkx alone it raised and the metric was silently lost.

    Degrees are integers, so every sum is exact integer arithmetic, and the only
    rounding is the final square root and division. networkx instead sums floats
    over a normalised mixing matrix. The two agree to about 1e-15, identical at
    the 4 dp the sensor stores.

    The result is NaN, as networkx returns, when the correlation is undefined:
    there are no edges, or one of the two degrees never varies (every edge
    points at the same hub, say). O(N + E).
    """
    n = len(index.nodes)
    out_offsets, out_targets, in_offsets = index.out_offsets, index.out_targets, index.in_offsets
    in_degree = [in_offsets[v + 1] - in_offsets[v] for v in range(n)]
    edges = sum_x = sum_xx = sum_y = sum_yy = sum_xy = 0
    for u in range(n):
        start, stop = out_offsets[u], out_offsets[u + 1]
        x = stop - start  # u's out-degree: the x of each of its x edges
        if x == 0:
            continue
        ys = [in_degree[v] for v in out_targets[start:stop]]
        y_total = sum(ys)
        edges += x
        sum_x += x * x
        sum_xx += x * x * x
        sum_y += y_total
        sum_yy += sum(y * y for y in ys)
        sum_xy += x * y_total
    covariance = edges * sum_xy - sum_x * sum_y
    variance_x = edges * sum_xx - sum_x * sum_x
    variance_y = edges * sum_yy - sum_y * sum_y
    if variance_x == 0 or variance_y == 0:
        return math.nan
    return covariance / math.sqrt(variance_x * variance_y)


def betweenness_centrality(index: GraphIndex, budget: Optional[WorkBudget] = None) -> list[float]:
    """
    #3038: exact betweenness centrality, one value per node id: the share of
    shortest import paths between other files that pass through each file.

    Bit-identical to networkx's exact, unweighted `nx.betweenness_centrality(G)`
    (normalized, directed, endpoints excluded), because it mirrors networkx's
    Brandes pass step for step:
    - BFS in adjacency order, with predecessors in discovery order
    - dependencies accumulated in reverse BFS order, sources in node order
    - then the directed `1 / ((N - 1) * (N - 2))` rescale

    It replaced networkx's 100-source sample above 500 files (#3033's
    tailoring decisions). On language-crucible the sample found 11 files with
    nonzero betweenness against 41 exact, and read 14 of the exact top 20 choke
    points as 0.

    Paths are counted in hops, not weight. networkx reads `weight` as a
    distance, which made an entity import, a stronger coupling, into a longer
    path.

    A file with no outgoing import starts no path, so it is skipped as a
    source. Each source charges `budget` the edges its search scanned (once for
    the BFS, once for the accumulation) plus its reach. Worst case O(N * E). On
    the language-crucible graph (2,817 nodes, 1,354 edges) it takes 2.1 ms,
    against 1.9 s for networkx's exact call.
    """
    n = len(index.nodes)
    out_offsets, out_targets = index.out_offsets, index.out_targets
    centrality = [0.0] * n
    sigma = [0.0] * n  # shortest-path counts from the current source
    depth = [-1] * n  # -1 = not reached by the current source
    delta = [0.0] * n  # accumulated dependency on each node
    predecessors: list[list[int]] = [[] for _ in range(n)]
    for source in range(n):
        if out_offsets[source] == out_offsets[source + 1]:
            continue  # no outgoing import: no path starts here
        order = [source]  # BFS order; popped in reverse for the accumulation
        sigma[source] = 1.0
        depth[source] = 0
        scanned = 0
        position = 0
        while position < len(order):
            node = order[position]
            position += 1
            next_depth = depth[node] + 1
            node_sigma = sigma[node]
            start, stop = out_offsets[node], out_offsets[node + 1]
            scanned += stop - start
            for target in out_targets[start:stop]:
                if depth[target] < 0:
                    depth[target] = next_depth
                    order.append(target)
                if depth[target] == next_depth:
                    sigma[target] += node_sigma
                    predecessors[target].append(node)
        for node in reversed(order):
            coefficient = (1 + delta[node]) / sigma[node]
            for predecessor in predecessors[node]:
                delta[predecessor] += sigma[predecessor] * coefficient
            if node != source:
                centrality[node] += delta[node]
        for node in order:
            sigma[node] = 0.0
            depth[node] = -1
            delta[node] = 0.0
            predecessors[node] = []
        if budget is not None:
            budget.charge(2 * scanned + len(order))
    pairs = n - 1  # networkx's N: an endpoint cannot be the node a path passes through
    if pairs >= 2:
        scale = 1 / (pairs * (pairs - 1))
        centrality = [value * scale for value in centrality]
    return centrality


# ------------------------------------------------------------------------------
# #3039: Louvain modularity, a faithful port of networkx's seeded
# `louvain_communities(G.to_undirected(), seed=42)` followed by `modularity`
# (resolution 1, threshold 1e-7). It reproduces networkx's communities exactly,
# not just its modularity, by mirroring every order that decides a move:
# - the undirected neighbour order
# - the rebuilt edge order
# - the seeded shuffle of each level
# - the gain ties
# Adjacency is a list of {neighbour: weight} dicts whose key order IS networkx's
# `_adj` order.
# ------------------------------------------------------------------------------


def _undirected_weights(index: GraphIndex) -> list[dict[int, float]]:
    """
    The weighted adjacency of networkx's `G.to_undirected()` for the sensor's
    DiGraph. Edges are added source-major in out-run order. A pair that imports
    each other becomes ONE undirected edge carrying the later-added direction's
    weight. Each neighbour keeps the position of its first edge, as a dict key
    keeps its position when reassigned.
    """
    n = len(index.nodes)
    out_offsets, out_targets, out_weights = index.out_offsets, index.out_targets, index.out_weights
    adjacency: list[dict[int, float]] = [{} for _ in range(n)]
    for u in range(n):
        for edge in range(out_offsets[u], out_offsets[u + 1]):
            v, weight = out_targets[edge], out_weights[edge]
            adjacency[u][v] = weight
            adjacency[v][u] = weight
    return adjacency


def _edges_once(adjacency: list[dict[int, float]]) -> Iterator[tuple[int, int, float]]:
    """networkx's undirected `G.edges(data=True)` order: node order, each edge (self-loops too) once."""
    seen: set[int] = set()
    for a, neighbours in enumerate(adjacency):
        for b, weight in neighbours.items():
            if b not in seen:
                yield a, b, weight
        seen.add(a)


def _weighted_degree(adjacency: list[dict[int, float]], v: int) -> float:
    """networkx's weighted degree: neighbour weights summed in adjacency order, a self-loop counted twice."""
    neighbours = adjacency[v]
    return sum(neighbours.values()) + (v in neighbours and neighbours[v])


def _modularity(adjacency: list[dict[int, float]], communities: list[set[int]]) -> float:
    """networkx's `modularity(G, communities)` for an undirected weighted graph, resolution 1."""
    degree = [_weighted_degree(adjacency, v) for v in range(len(adjacency))]
    degree_sum = sum(degree)
    m = degree_sum / 2
    norm = 1 / degree_sum**2

    def contribution(community: set[int]) -> float:
        members = set(community)
        seen: set[int] = set()
        internal = []
        for u in members:
            for v, weight in adjacency[u].items():
                if v not in seen and v in members:
                    internal.append(weight)
            seen.add(u)
        community_degree = sum(degree[u] for u in members)
        return sum(internal) / m - community_degree * community_degree * norm

    return sum(map(contribution, communities))


def _louvain_level(
    adjacency: list[dict[int, float]],
    members: Optional[list[set[int]]],
    m: float,
    partition: list[set[int]],
    rng: random.Random,
    budget: Optional[WorkBudget],
) -> tuple[list[set[int]], list[set[int]], bool]:
    """
    One call of networkx's `_one_level` (undirected, resolution 1), move for
    move. `partition` holds original node ids per community. `members[u]` is the
    original ids an aggregate node stands for; it is None at the first level.
    Each sweep over the nodes charges `budget` the neighbour entries it reads.
    """
    k = len(adjacency)
    node2com = list(range(k))
    inner = [{u} for u in range(k)]
    degrees = [_weighted_degree(adjacency, u) for u in range(k)]
    stot = list(degrees)
    neighbours = [{v: w for v, w in adjacency[u].items() if v != u} for u in range(k)]
    sweep_cost = k + sum(map(len, neighbours))
    order = list(range(k))
    rng.shuffle(order)
    moves = 1
    improvement = False
    while moves > 0:
        if budget is not None:
            budget.charge(sweep_cost)
        moves = 0
        for u in order:
            best_gain = 0.0
            best_com = node2com[u]
            weights2com: defaultdict[int, float] = defaultdict(float)
            for v, weight in neighbours[u].items():
                weights2com[node2com[v]] += weight
            degree = degrees[u]
            stot[best_com] -= degree
            # Reading u's own community inserts it LAST when no neighbour shares
            # it, exactly as networkx's defaultdict does. That orders the gain
            # ties below.
            remove_cost = -weights2com[best_com] / m + (stot[best_com] * degree) / (2 * m**2)
            for com, weight in weights2com.items():
                gain = remove_cost + weight / m - (stot[com] * degree) / (2 * m**2)
                if gain > best_gain:
                    best_gain = gain
                    best_com = com
            stot[best_com] += degree
            if best_com != node2com[u]:
                moved = members[u] if members is not None else {u}
                partition[node2com[u]].difference_update(moved)
                inner[node2com[u]].remove(u)
                partition[best_com].update(moved)
                inner[best_com].add(u)
                improvement = True
                moves += 1
                node2com[u] = best_com
    return [c for c in partition if c], [c for c in inner if c], improvement


def _aggregate(
    adjacency: list[dict[int, float]], members: Optional[list[set[int]]], inner: list[set[int]]
) -> tuple[list[dict[int, float]], list[set[int]]]:
    """networkx's `_gen_graph`: one node per community, edge weights summed in edge order."""
    node2com: dict[int, int] = {}
    new_members = []
    for i, part in enumerate(inner):
        nodes: set[int] = set()
        for node in part:
            node2com[node] = i
            nodes.update(members[node] if members is not None else {node})
        new_members.append(nodes)
    aggregated: list[dict[int, float]] = [{} for _ in range(len(inner))]
    for a, b, weight in _edges_once(adjacency):
        c1, c2 = node2com[a], node2com[b]
        total = weight + aggregated[c1].get(c2, 0)
        aggregated[c1][c2] = total
        aggregated[c2][c1] = total
    return aggregated, new_members


def _louvain(
    undirected: list[dict[int, float]], seed: int, threshold: float, budget: Optional[WorkBudget]
) -> list[set[int]]:
    """networkx's `louvain_partitions` loop, returning its last yielded partition."""
    n = len(undirected)
    if not any(undirected):  # nx.is_empty: no edges
        return [{v} for v in range(n)]
    rng = random.Random(seed)  # noqa: S311 -- networkx's py_random_state(int): a seeded shuffle, not security
    adjacency: list[dict[int, float]] = [{} for _ in range(n)]
    for a, b, weight in _edges_once(undirected):  # louvain_partitions' add_weighted_edges_from(G.edges())
        adjacency[a][b] = weight
        adjacency[b][a] = weight
    m = sum(_weighted_degree(adjacency, v) for v in range(n)) / 2
    partition = [{v} for v in range(n)]
    mod = _modularity(undirected, partition)
    members: Optional[list[set[int]]] = None
    partition, inner, _ = _louvain_level(adjacency, members, m, partition, rng, budget)
    improvement = True
    communities = partition
    while improvement:
        communities = [c.copy() for c in partition]
        new_mod = _modularity(adjacency, inner)
        if new_mod - mod <= threshold:
            break
        mod = new_mod
        adjacency, members = _aggregate(adjacency, members, inner)
        partition, inner, improvement = _louvain_level(adjacency, members, m, partition, rng, budget)
    return communities


def louvain_communities(index: GraphIndex, seed: int = 42, budget: Optional[WorkBudget] = None) -> list[set[int]]:
    """
    #3039: seeded Louvain communities of the undirected import graph, as sets of
    node ids. It returns the same communities, in the same order, as
    `nx.community.louvain_communities(G.to_undirected(), seed=seed)`.
    """
    return _louvain(_undirected_weights(index), seed, 1e-7, budget)


def louvain_modularity(index: GraphIndex, seed: int = 42, budget: Optional[WorkBudget] = None) -> Optional[float]:
    """
    #3039: the modularity of the seeded Louvain partition: the engine's
    `network_modularity`. Strict parity with networkx's
    `modularity(U, louvain_communities(U, seed=42))` for `U = G.to_undirected()`.
    On language-crucible it gives the same 1,989 communities and a
    bit-identical 0.8150048644056641, in 116 ms vs 207 ms.

    None when no file imports another: networkx divides by zero there, and the
    sensor recorded None. Worst case near-linear per level, bounded by `budget`.
    """
    undirected = _undirected_weights(index)
    if not any(undirected):
        return None
    return _modularity(undirected, _louvain(undirected, seed, 1e-7, budget))


_bit_count = getattr(int, "bit_count", None)  # Python >= 3.10; the package supports 3.9


def _popcount(bits: int) -> int:
    """The number of set bits in a Python int."""
    return _bit_count(bits) if _bit_count is not None else bin(bits).count("1")


def reach_counts(index: GraphIndex, budget: Optional[WorkBudget] = None) -> tuple[list[int], list[int]]:
    """
    #3040: for every node, how many other nodes it reaches (its descendants:
    the files it depends on, directly or transitively) and how many reach it
    (its ancestors). Exact, with no cap.

    Equal to `len(nx.descendants(G, v))` / `len(nx.ancestors(G, v))`, which
    never count v itself, not even on a cycle.

    How it works:
    - Each strongly connected component is condensed to one node.
    - Each component's reachable node set is a Python-int bitset: the OR of its
      successor components' members and reach, built in Tarjan's completion
      order, so successors come first.
    - Ancestors are the same, over predecessors, in reverse order.
    - A node's count is its component's reach plus the rest of its own
      component.

    Every OR charges `budget` the 64-bit words it touches. A bitset is as long
    as its highest node id, so on a huge, deeply layered graph the sets can
    grow to O(N^2) bits in total. The budget turns that into
    WorkBudgetExceeded instead of an out-of-memory scan.

    On the language-crucible graph (2,817 nodes, 1,354 edges) this takes
    4.6 ms, vs 16.3 ms for networkx's per-node descendants and ancestors.
    """
    n = len(index.nodes)
    component, count = strongly_connected_components(index)
    members = [0] * count
    size = [0] * count
    for v in range(n):
        members[component[v]] |= 1 << v
        size[component[v]] += 1
    successors: list[set[int]] = [set() for _ in range(count)]
    predecessors: list[set[int]] = [set() for _ in range(count)]
    out_offsets, out_targets = index.out_offsets, index.out_targets
    for u in range(n):
        for target in out_targets[out_offsets[u] : out_offsets[u + 1]]:
            cu, ct = component[u], component[target]
            if cu != ct:
                successors[cu].add(ct)
                predecessors[ct].add(cu)

    def close(order: range, neighbours: list[set[int]]) -> list[int]:
        reach = [0] * count
        for c in order:
            bits = 0
            for d in neighbours[c]:
                if budget is not None:
                    budget.charge((members[d].bit_length() + reach[d].bit_length()) // 64 + 1)
                bits |= members[d] | reach[d]
            reach[c] = bits
        return reach

    reaches = close(range(count), successors)  # completion order: successors first
    reached_by = close(range(count - 1, -1, -1), predecessors)  # reverse: predecessors first
    descendants = [_popcount(reaches[component[v]]) + size[component[v]] - 1 for v in range(n)]
    ancestors = [_popcount(reached_by[component[v]]) + size[component[v]] - 1 for v in range(n)]
    return descendants, ancestors
