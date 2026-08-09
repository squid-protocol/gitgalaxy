# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
# ==============================================================================
import logging
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS

HAS_NETWORKX = False
try:
    import networkx as nx
    from networkx.algorithms import community

    HAS_NETWORKX = True
except ImportError:
    pass


class NetworkRiskSensor:
    """
    The GitGalaxy Network Risk Sensor (Graph Topology & Blast Radius).

    PURPOSE: Ingests the flat list of parsed files, wires them into a Directed Graph (DAG)
    using raw_imports, and calculates Ecosystem Roles, PageRank, and
    Vector-Weighted Systemic Threats.
    """

    def __init__(self, parent_logger: Optional[logging.Logger] = None):
        self.logger = parent_logger.getChild("network_sensor") if parent_logger else logging.getLogger("network_sensor")
        self.RISK_SCHEMA = RECORDING_SCHEMAS.get("RISK_SCHEMA", [])

    def _build_resolution_map(self, files: list[dict[str, Any]]) -> dict[str, list[str]]:
        """
        Maps each lookup key (full path, filename, stem) to ALL candidate file
        paths sharing that key — never silently overwrites on duplicate
        filenames. Full-path keys are always unambiguous; name/stem keys may
        resolve to multiple candidates in monorepos with duplicate filenames
        across directories.
        """
        resolution_map: dict[str, list[str]] = defaultdict(list)
        for f in files:
            path = f.get("path", "")
            if not path:
                continue
            name = f.get("name", Path(path).name)
            stem = Path(path).stem

            resolution_map[path].append(path)
            if name:
                resolution_map[name].append(path)
            if stem:
                resolution_map[stem].append(path)

        return resolution_map

    def _resolve_target(self, target_token: str, resolution_map: dict[str, list[str]], curr_path: str) -> Optional[str]:
        """
        Resolves an import token to a single file path, refusing to guess when
        genuinely ambiguous rather than silently misattributing an edge.
        """
        token_as_path = target_token.replace(".", "/").replace("\\", "/")

        # Stage 1: direct key lookup — handles full-path, bare-filename, and
        # bare-stem tokens that match a stored key exactly.
        candidates = resolution_map.get(target_token)

        # Stage 1b: compound tokens (e.g. "service_b/utils" or "pkg.utils")
        # are never stored as map keys directly — resolution_map only holds
        # full paths, bare filenames, and bare stems. Fall back to the
        # token's final path component so there's something to disambiguate
        # against in Stage 2.
        if not candidates:
            bare_component = token_as_path.rsplit("/", 1)[-1]
            candidates = resolution_map.get(bare_component)

        if not candidates:
            return None

        candidates = list(dict.fromkeys(candidates))  # de-dupe, preserve order
        if len(candidates) == 1:
            return candidates[0]

        # Stage 2: multiple files share this name/stem — disambiguate using
        # any path context already present in the token, comparing against
        # each candidate's path with its extension stripped.
        path_matches = [
            c for c in candidates if str(Path(c).with_suffix("")).replace("\\", "/").endswith(token_as_path)
        ]
        if len(path_matches) == 1:
            return path_matches[0]

        # Still ambiguous — skip rather than misattribute.
        self.logger.debug(
            f"Ambiguous import token '{target_token}' matches {len(candidates)} "
            f"files {candidates}; skipping edge from '{curr_path}'."
        )
        return None

    def extract_test_coverage_mapping(self, files: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """
        Maps function calls from test files to their imported production targets.
        Returns a dictionary mapping: production_file_path -> { production_function_name: [test_function_data] }

        DEFENSIVE DESIGN: Traditional code coverage only checks if a line was executed.
        By mapping outbound AST calls from tests to production targets, we can calculate
        the exact architectural "Dependency Blast Radius" of untested functions.
        """
        coverage_map: dict[str, dict[str, list[dict[str, Any]]]] = {}
        resolution_map = self._build_resolution_map(files)

        # 2. Identify Test Files and extract their outgoing invocations
        for f in files:
            path = f.get("path", "")
            low_path = path.lower()

            # Structural heuristic for test files
            is_test = any(x in low_path for x in ["/test/", "/tests/", "test_", "_test", ".spec.", ".test."])
            if not is_test:
                continue

            # Identify which production files this test file imports
            target_paths = set()
            for imp in f.get("raw_imports", []):
                target_token = imp[0] if isinstance(imp, tuple) and len(imp) == 2 else imp
                target_path = self._resolve_target(target_token, resolution_map, path)

                if target_path and target_path != path:
                    target_paths.add(target_path)

            if not target_paths:
                continue

            # Map each test function's payload to the production functions it calls
            for test_func in f.get("functions", []):
                calls_out = test_func.get("calls_out_to", [])
                if not calls_out:
                    continue

                target_count = len(calls_out)
                test_payload = {
                    "impact": test_func.get("impact", 0.0),
                    "target_count": target_count,
                    "test_hits": test_func.get("hit_vector", {}).get("test", 0),
                    "test_skip_hits": test_func.get("hit_vector", {}).get("test_skip", 0),
                    "decorators": test_func.get("hit_vector", {}).get("decorators", 0),
                }

                for target_path in target_paths:
                    if target_path not in coverage_map:
                        coverage_map[target_path] = {}

                    for called_func_name in calls_out:
                        if called_func_name not in coverage_map[target_path]:
                            coverage_map[target_path][called_func_name] = []
                        coverage_map[target_path][called_func_name].append(test_payload)

        return coverage_map

    def build_dependency_graph(self, parsed_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Builds the directed graph and calculates multi-dimensional risk vectors.
        Modifies the 'telemetry' dictionary of each file in place.
        """
        if not HAS_NETWORKX:
            return self._fallback_build_graph(parsed_files)

        self.logger.info(f"Network Risk Sensor: Initializing Directed Graph for {len(parsed_files)} nodes...")

        G = nx.DiGraph()

        # 1. Build the Resolution Map (Fast Path Lookup)
        resolution_map = self._build_resolution_map(parsed_files)
        for f in parsed_files:
            path = f.get("path", "")

            # Add Node with Vector
            G.add_node(
                path,
                risk_vector=f.get("risk_vector", [0.0] * len(self.RISK_SCHEMA)),
            )

        # 2. Wire the Edges (File-to-File Level 1 & Entity Level 2)
        for f in parsed_files:
            curr_path = f.get("path", "")
            raw_imports = f.get("raw_imports", [])

            for imp in raw_imports:
                # Check if it's a Level 2 Tuple (Entity Import) or Level 1 String
                if isinstance(imp, tuple) and len(imp) == 2:
                    target_token, entity = imp
                else:
                    target_token = imp
                    entity = None

                target_path = self._resolve_target(target_token, resolution_map, curr_path)
                if target_path and target_path != curr_path:
                    # Edge weight can be increased if specific entities are highly coupled
                    weight = 1.5 if entity else 1.0
                    if G.has_edge(curr_path, target_path):
                        G[curr_path][target_path]["weight"] += weight
                    else:
                        G.add_edge(curr_path, target_path, weight=weight)

        # =========================================================================
        # 3. NETWORK MATHEMATICS (Dependency Blast Radius & Centrality)
        # DEFENSIVE DESIGN: Centrality algorithms (Betweenness/Closeness) scale non-linearly
        # at O(V^3). For massive monolithic repositories (>1500 nodes), we MUST implement
        # strict sampling or bypasses, otherwise the CI/CD pipeline will hit a timeout deadlock.
        # PageRank is safe as it uses iterative convergence.
        # =========================================================================
        try:
            pagerank = nx.pagerank(G, weight="weight")

            # Force a maximum sample size of 100 nodes for any graph > 500 nodes.
            # seed is fixed because k triggers *approximate* betweenness via random
            # node sampling -- unseeded, two scans of an unchanged repo can pick a
            # completely different sample and report different bottleneck files.
            k_val = min(len(G.nodes()), 100) if len(G.nodes()) > 500 else None
            betweenness = nx.betweenness_centrality(G, k=k_val, weight="weight", seed=42 if k_val is not None else None)

            # Closeness Centrality has no built-in sampling. Hard bypass at 1500 nodes.
            if len(G.nodes()) > 1500:
                self.logger.debug("Graph too massive for exact Closeness Centrality. Bypassing.")
                closeness = dict.fromkeys(G.nodes(), 0.0)
            else:
                closeness = nx.closeness_centrality(G)

        except Exception as e:
            self.logger.warning(f"Network math failed to converge, defaulting to 0: {e}")
            pagerank = dict.fromkeys(G.nodes(), 0.0)
            betweenness = dict.fromkeys(G.nodes(), 0.0)
            closeness = dict.fromkeys(G.nodes(), 0.0)

        in_degrees = dict(G.in_degree())
        out_degrees = dict(G.out_degree())

        # 4. Vector Cross-Multiplication & Bottleneck Identification
        for f in parsed_files:
            path = f.get("path", "")
            if path not in G:
                continue

            pr_score = pagerank.get(path, 0.0)
            in_d = in_degrees.get(path, 0)
            out_d = out_degrees.get(path, 0)

            # --- Ecosystem Role Ratio ---
            total_edges = in_d + out_d
            if total_edges == 0:
                ecosystem_role = "Isolated/Orphan"
                producer_ratio = 0.0
            else:
                producer_ratio = in_d / total_edges
                if producer_ratio > 0.8:
                    ecosystem_role = "Pure Producer (Foundation)"
                elif producer_ratio < 0.2:
                    ecosystem_role = "Pure Consumer (Orchestrator)"
                else:
                    ecosystem_role = "Transceiver (Middle-Tier)"

            # --- Multi-Dimensional Systemic Threat Vector ---
            # PageRank is usually a tiny decimal (e.g., 0.0005). We normalize it
            # by multiplying by 1000 to make the scale human/LLM readable.
            pr_normalized = pr_score * 1000
            local_risk_vector = f.get("risk_vector", [0.0] * len(self.RISK_SCHEMA))

            # Systemic Threat = Dependency Blast Radius * Local Vulnerability Severity
            systemic_threat_vector = [
                round(pr_normalized * (local_risk / 100.0), 3) for local_risk in local_risk_vector
            ]

            # 5. Write Telemetry Back to the File Node
            if "telemetry" not in f:
                f["telemetry"] = {}

            f["telemetry"]["network_metrics"] = {
                "pagerank_score": round(pr_score, 6),
                "normalized_blast_radius": round(pr_normalized, 3),
                "betweenness_score": round(betweenness.get(path, 0.0), 6),
                "closeness_score": round(closeness.get(path, 0.0), 6),
                "in_degree": in_d,
                "out_degree": out_d,
                "producer_ratio": round(producer_ratio, 3),
                "ecosystem_role": ecosystem_role,
                "systemic_threat_vector": systemic_threat_vector,
            }

            # Overwrite the old "popularity" integer with the strict directed in_degree
            f["telemetry"]["popularity"] = in_d

        # =========================================================================
        # 6. MACRO-ECOSYSTEM TOPOLOGY (Repo-Level Health & Resilience)
        # =========================================================================
        # #473: these default to None, not 0.0/0 -- same "explicitly missing,
        # not a specific observation" convention record_keeper.py already uses
        # for zero_dependency_mode's pagerank/ai_score/etc (see #429's mypy
        # session 3). A 0.0 modularity is a real, meaningful score (no
        # community structure); collapsing "computation failed or was
        # skipped" into that same value made a silent failure indistinguishable
        # from a genuine measurement. Consumers (record_keeper.py,
        # llm_recorder.py) must not paper over None with their own 0.0
        # fallback, or this fix is undone one hop downstream.
        macro_metrics: dict[str, Optional[float]] = {
            "modularity": None,
            "assortativity": None,
            "cyclic_density": None,
            "avg_path_length": None,
            "articulation_points": None,
        }

        if len(G) > 0:
            try:
                U = G.to_undirected()

                # A. Modularity (Spaghetti vs Microservice)
                try:
                    if len(U) > 5000:
                        self.logger.debug("Graph too massive for Modularity. Leaving unset (None).")
                    else:
                        # Attempt Louvain (blazing fast), fallback to Greedy (slow)
                        # seed is fixed so repeated scans of an unchanged repo
                        # report the same modularity and Critical Files list
                        # instead of a different randomized partition each run.
                        try:
                            communities = community.louvain_communities(U, seed=42)
                        except AttributeError:
                            communities = community.greedy_modularity_communities(U)

                        macro_metrics["modularity"] = round(community.modularity(U, communities), 4)
                except Exception as e:
                    self.logger.debug(f"Modularity computation failed, leaving unset (None): {e}")

                # B. Assortativity (Resiliency)
                try:
                    import warnings

                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        assort = nx.degree_assortativity_coefficient(G)
                    macro_metrics["assortativity"] = round(assort, 4) if not math.isnan(assort) else 0.0
                except Exception as e:
                    self.logger.debug(f"Assortativity computation failed, leaving unset (None): {e}")

                # C. Cyclic Density (Circular Dependencies / Dependency Loops)
                try:
                    sccs = list(nx.strongly_connected_components(G))
                    nodes_in_cycles = sum(len(c) for c in sccs if len(c) > 1)
                    macro_metrics["cyclic_density"] = round(nodes_in_cycles / len(G), 4)
                except Exception as e:
                    self.logger.debug(f"Cyclic density computation failed, leaving unset (None): {e}")

                # D. Average Shortest Path (Coupling Distance)
                try:
                    if len(U) > 5000:
                        self.logger.debug("Graph too massive for Avg Path Length. Leaving unset (None).")
                    else:
                        largest_cc = max(nx.connected_components(U), key=len)
                        subgraph = U.subgraph(largest_cc)
                        macro_metrics["avg_path_length"] = round(nx.average_shortest_path_length(subgraph), 4)
                except Exception as e:
                    self.logger.debug(f"Avg shortest path computation failed, leaving unset (None): {e}")

                # E. Articulation Points (Fragmentation Risk)
                try:
                    macro_metrics["articulation_points"] = len(list(nx.articulation_points(U)))
                except Exception as e:
                    self.logger.debug(f"Articulation points computation failed, leaving unset (None): {e}")

            except Exception as e:
                self.logger.warning(f"Macro network math failed: {e}")

        self.logger.info("Network Risk Sensor: Vector Mathematics & Graph Topology Complete.")
        return parsed_files, macro_metrics

    def _fallback_build_graph(self, parsed_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self.logger.warning(
            "[!] 'networkx' not found. Operating in Zero-Dependency Mode. Using linear counting for Ecosystem Roles."
        )

        resolution_map = self._build_resolution_map(parsed_files)

        in_degrees = {f.get("path", ""): 0 for f in parsed_files}
        out_degrees = {f.get("path", ""): 0 for f in parsed_files}

        for f in parsed_files:
            curr_path = f.get("path", "")
            for imp in f.get("raw_imports", []):
                target_token = imp[0] if isinstance(imp, tuple) and len(imp) == 2 else imp
                target_path = self._resolve_target(target_token, resolution_map, curr_path)
                if target_path and target_path != curr_path:
                    out_degrees[curr_path] = out_degrees.get(curr_path, 0) + 1
                    in_degrees[target_path] = in_degrees.get(target_path, 0) + 1

        for f in parsed_files:
            path = f.get("path", "")
            in_d = in_degrees.get(path, 0)
            out_d = out_degrees.get(path, 0)

            total_edges = in_d + out_d
            if total_edges == 0:
                ecosystem_role = "Isolated/Orphan"
                producer_ratio = 0.0
            else:
                producer_ratio = in_d / total_edges
                if producer_ratio > 0.8:
                    ecosystem_role = "Pure Producer (Foundation)"
                elif producer_ratio < 0.2:
                    ecosystem_role = "Pure Consumer (Orchestrator)"
                else:
                    ecosystem_role = "Transceiver (Middle-Tier)"

            if "telemetry" not in f:
                f["telemetry"] = {}
            f["telemetry"]["network_metrics"] = {
                "pagerank_score": 0.0,
                "normalized_blast_radius": 0.0,
                "betweenness_score": 0.0,
                "closeness_score": 0.0,
                "in_degree": in_d,
                "out_degree": out_d,
                "producer_ratio": round(producer_ratio, 3),
                "ecosystem_role": ecosystem_role,
                "systemic_threat_vector": [],
            }
            f["telemetry"]["popularity"] = in_d

        # #473: None, not 0.0/0 -- zero-dependency mode means these were never
        # attempted at all (networkx isn't installed), not measured as zero.
        # Same convention as the real-computation path above.
        macro_metrics: dict[str, Optional[float]] = {
            "modularity": None,
            "assortativity": None,
            "cyclic_density": None,
            "avg_path_length": None,
            "articulation_points": None,
        }
        return parsed_files, macro_metrics
