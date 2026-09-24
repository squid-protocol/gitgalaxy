# ==============================================================================
# GitGalaxy Core: Function Graph Metrics (#3330, Epic #3265 step 3)
#
# The call resolver (core/call_resolver.py, #3328) links each function's callee
# names to definitions. This module turns its CONFIDENT function-to-function
# links into a directed graph and gives every function three new numbers:
#
#   func_pagerank  -- PageRank over the call graph: how much of the codebase's
#                     control flow ends up in this function.
#   func_fan_in    -- distinct functions that call it.
#   func_fan_out   -- distinct functions it calls.
#
# The transitive blast radius (everything upstream of a function) is a QUERY,
# not a column: tests/tools/function_blast_radius.py / the recursive CTE in
# docs/function_call_graph.md. graph_engine.reach_counts computes it for every
# node at once with bitsets, which is O(N^2) bits -- it exceeded any sane work
# budget on every real repository measured (cpython's 93k functions,
# elasticsearch's 305k), so a column would have been NULL almost everywhere.
#
# WHAT IS AN EDGE (decided by the #3327 contract and #3328):
#   - only scoped/unique resolutions (class, qualified, file, import, unique);
#     an ambiguous pair (unseen, nearest, receiver, tie) is never an edge, so a common
#     name cannot pool fan-in onto whichever definition happened to be nearest;
#   - only function targets: a constructor call that resolved to a class has no
#     function node to land on;
#   - unweighted and deduplicated, with no self-loop (recursion is dropped).
# Module-level code (a synthetic top-level slice) is a caller node: it gives
# its callees fan-in and PageRank, but has no function_data row to receive them.
#
# Same native graph engine as the file graph (core/graph_engine.py): no
# networkx, identical numbers in every mode. Nothing here feeds a risk score or
# a file-level column -- #3333 decides whether it ever should.
# ==============================================================================
from typing import Any, Optional

from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS
from gitgalaxy.core.graph_engine import GraphIndex, pagerank

FunctionKey = tuple[str, str, int]  # (path, name, start_line)


def _node(path: str, name: str, line: int) -> str:
    return f"{path}\x00{name}\x00{line}"


def function_metrics(
    parsed_files: list[dict[str, Any]],
    fcall_sites: list[dict[str, Any]],
) -> dict[FunctionKey, dict[str, Any]]:
    """Every real function's three metrics, keyed by (path, name, start_line)."""
    nodes: list[str] = []
    keys: dict[str, FunctionKey] = {}
    for f in parsed_files:
        path = f.get("path", "")
        for func in f.get("functions", []) or []:
            name = str(func.get("name") or "")
            line = int(func.get("start_line", 0) or 0)
            node = _node(path, name, line)
            nodes.append(node)
            if not func.get("is_synthetic_slice"):
                keys.setdefault(node, (path, name, line))

    known = set(nodes)
    edges: dict[tuple[str, str], None] = {}
    for s in fcall_sites:
        if s.get("resolution") not in CONFIDENT_RESOLUTIONS or s.get("dst_kind") != "function":
            continue
        src = _node(s.get("src_path", ""), str(s.get("src_name") or ""), int(s.get("src_line") or 0))
        dst = _node(s.get("dst_path") or "", str(s.get("dst_name") or ""), int(s.get("dst_line") or 0))
        if src != dst and src in known and dst in known:
            edges.setdefault((src, dst), None)

    if not keys:
        return {}
    index = GraphIndex(nodes, ((a, b, 1.0) for a, b in edges))
    try:
        ranks: Optional[list[float]] = pagerank(index)
    except RuntimeError:
        ranks = None

    out: dict[FunctionKey, dict[str, Any]] = {}
    for node, key in keys.items():
        v = index.node_id[node]
        out[key] = {
            "func_pagerank": ranks[v] if ranks is not None else None,
            "func_fan_in": index.in_offsets[v + 1] - index.in_offsets[v],
            "func_fan_out": index.out_offsets[v + 1] - index.out_offsets[v],
        }
    return out


def attach_function_metrics(parsed_files: list[dict[str, Any]], metrics: dict[FunctionKey, dict[str, Any]]) -> None:
    """Hang each function's metrics on its own dict for the recorders."""
    for f in parsed_files:
        path = f.get("path", "")
        for func in f.get("functions", []) or []:
            m = metrics.get((path, str(func.get("name") or ""), int(func.get("start_line", 0) or 0)))
            if m is not None:
                func.update(m)
