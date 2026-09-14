# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
# ==============================================================================
import logging
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.core.graph_engine import (
    GraphIndex,
    WorkBudget,
    WorkBudgetExceeded,
    articulation_point_count,
    closeness_and_path_length,
    degree_assortativity,
    nodes_in_cycles,
    pagerank,
)
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# #2540: languages whose import/module references resolve case-insensitively
# (fortran `USE A` binds a.f90, cobol `COPY A.` binds a.cpy, haskell's
# necessarily-capitalized `import A` may live in a.hs). Declared per-language
# via the "case_insensitive_imports" flag on each language DEFINITION;
# resolution for every other language stays strictly case-sensitive.
CASE_INSENSITIVE_IMPORT_LANGS = frozenset(
    lang_id for lang_id, definition in LANGUAGE_DEFINITIONS.items() if definition.get("case_insensitive_imports")
)

# #2668: leading relative-path markers are path syntax, not part of the
# imported target's name -- "./b.sh" and "../lib/helper.js" name b.sh and
# lib/helper.js. Anchored and bounded by the input's own length; no
# backtracking risk (single non-overlapping alternative, fixed-width group).
LEADING_RELATIVE_MARKER = re.compile(r"^(?:\.{1,2}/)+")

# #3037: the deterministic work budget for the hop-count path metrics (closeness
# and average path length), counted in incoming edges scanned across every file's
# breadth-first search. 50M is about 3 s of pure-Python search; past it both
# metrics are None ("not computed"), never 0.0. It replaced node-count cutoffs --
# closeness above 1,500 files, path length above 5,000 -- that skipped the
# 2,817-file language-crucible graph, whose searches take under 2 ms.
PATH_METRICS_WORK_BUDGET = 50_000_000


def _without_extension(path_str: str) -> str:
    """
    Drops a trailing file extension from a slash-separated token, leaving
    everything else untouched. Hand-rolled rather than
    `PurePosixPath.with_suffix("")` because import tokens are arbitrary
    captured text: `.`, `..` and `` all reach here and all raise from
    pathlib. A leading dot is a hidden-file marker, not an extension.
    """
    name = path_str.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    if dot <= 0:
        return path_str
    return path_str[: len(path_str) - (len(name) - dot)]


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
        # #2992: the resolved edge list of the most recent build_dependency_graph
        # call. The graph is discarded once its degree/centrality math is done;
        # this is the only copy that survives it, and record_keeper persists it
        # as the edge_data table. Deliberately not written into file telemetry
        # or the returned macro metrics -- both reach the audit/GPU JSON exports.
        self.dependency_edges: list[dict[str, Any]] = []

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

    def _build_folded_resolution_map(self, files: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
        """
        #2540: derives per-language lowercase-keyed views of the resolution
        keys so imports from case-insensitive-resolution languages (fortran,
        cobol, haskell — see CASE_INSENSITIVE_IMPORT_LANGS) can fall back to a
        case-folded lookup. Kept separate from the exact-case map so
        case-sensitive languages never gain cross-case resolution, and so
        exact-case matches always win first even for the folding languages.

        Folding is a property of the *importing* language's resolution rules,
        so each language's folded view holds only that language's own files —
        haskell's `import Text.Pandoc.Generic` must not fold onto a go file
        named generic.go just because the stems collide case-insensitively.
        (The exact-case stages keep their long-standing language-agnostic
        stem matching; only the folded fallback is scoped.)
        """
        folded_maps: dict[str, dict[str, list[str]]] = {}
        for f in files:
            lang = str(f.get("lang_id", "")).lower()
            if lang not in CASE_INSENSITIVE_IMPORT_LANGS:
                continue
            path = f.get("path", "")
            if not path:
                continue
            lang_map = folded_maps.setdefault(lang, defaultdict(list))
            name = f.get("name", Path(path).name)
            stem = Path(path).stem
            lang_map[path.lower()].append(path)
            if name:
                lang_map[name.lower()].append(path)
            if stem:
                lang_map[stem.lower()].append(path)
        return folded_maps

    def _resolve_target(
        self,
        target_token: str,
        resolution_map: dict[str, list[str]],
        curr_path: str,
        folded_maps: Optional[dict[str, dict[str, list[str]]]] = None,
        fold_lang: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolves an import token to a single file path, refusing to guess when
        genuinely ambiguous rather than silently misattributing an edge.

        When `fold_lang` is set (the importing file's language resolves
        imports case-insensitively, #2540) and no exact-case key matches, the
        lookup retries against that language's own folded map with a
        lowercased token. Exact matches always win first, so mixed-case repos
        keep their precise edges.
        """
        # The historical form: every dot becomes a separator, which is what
        # lets a package-style token ("pkg.utils") find utils.py.
        token_as_path = target_token.replace(".", "/").replace("\\", "/")
        bare_component = token_as_path.rsplit("/", 1)[-1]

        # #2668: that rewrite also shreds a relative import that carries its
        # own extension — "./b.sh" becomes "//b/sh", so the lookup key is the
        # *extension* ("sh"), nothing resolves, and shell/powershell/yaml/
        # javascript built no edges at all despite reporting dependency_links.
        # Read the token as a literal path first (leading "./" / "../"
        # stripped, dots left alone) and keep the dot rewrite as the last
        # fallback, so every token that resolved before still resolves the
        # same way — the path forms are only *tried* when they differ from
        # the token itself, i.e. exactly for relative and compound paths.
        literal_path = LEADING_RELATIVE_MARKER.sub("", target_token.replace("\\", "/"))
        literal_cmp = _without_extension(literal_path)

        # (lookup key, path context to disambiguate with in Stage 2), in
        # priority order and de-duplicated: exact token, literal relative
        # path, that path's final component, then the dot-rewritten
        # component. A key is compared against candidate paths with their
        # extension stripped, so the token's own extension comes off too.
        # A dict de-dupes by key with the first (highest-priority) context
        # winning, and preserves insertion order.
        lookup_forms: dict[str, str] = {}
        lookup_forms.setdefault(target_token, token_as_path)
        for form in (literal_path, literal_path.rsplit("/", 1)[-1]):
            if form and form != target_token:
                lookup_forms.setdefault(form, literal_cmp)
        lookup_forms.setdefault(bare_component, token_as_path)

        folded_hit = False
        match_cmp = token_as_path
        candidates = None

        # Stage 1: direct key lookup — handles full-path, bare-filename and
        # bare-stem tokens that match a stored key exactly (first form), the
        # #2668 literal-path forms next, and finally Stage 1b: compound
        # tokens (e.g. "service_b/utils" or "pkg.utils") are never stored as
        # map keys directly — resolution_map only holds full paths, bare
        # filenames and bare stems — so the dot-rewritten final component is
        # the last resort, giving Stage 2 something to disambiguate against.
        for key, cmp_context in lookup_forms.items():
            candidates = resolution_map.get(key)
            if candidates:
                match_cmp = cmp_context
                break

        # Stage 1c (#2540): case-insensitive-resolution languages retry the
        # same lookups case-folded, only after every exact-case form
        # misses — fortran `USE A` -> a.f90, cobol `COPY A.` -> a.cpy,
        # haskell `import A` -> a.hs. Scoped to the importing language's own
        # files so folding never invents a cross-language edge.
        if not candidates and fold_lang and folded_maps is not None:
            lang_map = folded_maps.get(fold_lang)
            if lang_map:
                folded_hit = True
                for key, cmp_context in lookup_forms.items():
                    candidates = lang_map.get(key.lower())
                    if candidates:
                        match_cmp = cmp_context
                        break

        if not candidates:
            return None

        candidates = list(dict.fromkeys(candidates))  # de-dupe, preserve order
        if len(candidates) == 1:
            return candidates[0]

        # Stage 2: multiple files share this name/stem — disambiguate using
        # any path context already present in the token, comparing against
        # each candidate's path with its extension stripped. A case-folded
        # hit compares case-folded here too, for consistency with Stage 1c.
        cmp_token = match_cmp.lower() if folded_hit else match_cmp
        path_matches = [
            c
            for c in candidates
            if (
                str(Path(c).with_suffix("")).replace("\\", "/").lower()
                if folded_hit
                else str(Path(c).with_suffix("")).replace("\\", "/")
            ).endswith(cmp_token)
        ]
        if len(path_matches) == 1:
            return path_matches[0]

        # Still ambiguous — skip rather than misattribute.
        self.logger.debug(
            f"Ambiguous import token '{target_token}' matches {len(candidates)} "
            f"files {candidates}; skipping edge from '{curr_path}'."
        )
        return None

    @staticmethod
    def _fold_lang(f: dict[str, Any]) -> Optional[str]:
        """#2540: the file's language id if it resolves import targets case-insensitively, else None."""
        lang = str(f.get("lang_id", "")).lower()
        return lang if lang in CASE_INSENSITIVE_IMPORT_LANGS else None

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
        folded_maps = self._build_folded_resolution_map(files)

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
                target_path = self._resolve_target(
                    target_token, resolution_map, path, folded_maps=folded_maps, fold_lang=self._fold_lang(f)
                )

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

    def _resolve_edges(self, parsed_files: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        """
        #2992: resolves every file's raw_imports into directed file-to-file
        edges, keyed (importer, imported) in first-occurrence order. Repeated
        imports of the same target collapse into one edge that keeps count:
        `import_statements` (resolved captures), `entity_imports` (the Level 2
        tuple form among them) and `weight` (1.0 per plain import, 1.5 per
        entity import, summed in capture order -- the exact float the DiGraph
        accumulated before this was factored out).

        The single resolver behind both graph builders, so the persisted edge
        list cannot drift from the degrees and pagerank computed off it.
        """
        resolution_map = self._build_resolution_map(parsed_files)
        folded_maps = self._build_folded_resolution_map(parsed_files)
        edges: dict[tuple[str, str], dict[str, Any]] = {}

        for f in parsed_files:
            curr_path = f.get("path", "")
            fold_lang = self._fold_lang(f)

            for imp in f.get("raw_imports", []):
                # Check if it's a Level 2 Tuple (Entity Import) or Level 1 String
                if isinstance(imp, tuple) and len(imp) == 2:
                    target_token, entity = imp
                else:
                    target_token = imp
                    entity = None

                target_path = self._resolve_target(
                    target_token, resolution_map, curr_path, folded_maps=folded_maps, fold_lang=fold_lang
                )
                if target_path and target_path != curr_path:
                    edge = edges.setdefault(
                        (curr_path, target_path), {"weight": 0.0, "import_statements": 0, "entity_imports": 0}
                    )
                    # Edge weight can be increased if specific entities are highly coupled
                    edge["weight"] += 1.5 if entity else 1.0
                    edge["import_statements"] += 1
                    if entity:
                        edge["entity_imports"] += 1

        return edges

    def _publish_edges(self, edges: dict[tuple[str, str], dict[str, Any]]) -> None:
        """#2992: exposes the resolved edges as `self.dependency_edges` for the recorder."""
        self.dependency_edges = [
            {"src": src, "dst": dst, "edge_kind": "import", **attrs} for (src, dst), attrs in edges.items()
        ]

    def _network_metrics(
        self,
        f: dict[str, Any],
        pr_score: Optional[float],
        betweenness: Optional[float],
        closeness: Optional[float],
        in_d: int,
        out_d: int,
    ) -> dict[str, Any]:
        """
        One file's `network_metrics`, shared by both graph builders. #3027: a
        metric that was not computed (no networkx for betweenness, closeness
        past its #3037 work budget, a failed computation) is None, never
        a 0.0 placeholder -- a 0.0 reads as a measurement and every consumer drew
        conclusions from it (a "Containment (Low Risk)" verdict, zero-score
        bottleneck rankings, zeroed archetype features).
        """
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
        # Systemic Threat = Dependency Blast Radius * Local Vulnerability Severity
        pagerank_score: Optional[float] = None
        blast_radius: Optional[float] = None
        systemic_threat_vector: Optional[list[float]] = None
        if pr_score is not None:
            pr_normalized = pr_score * 1000
            local_risk_vector = f.get("risk_vector", [0.0] * len(self.RISK_SCHEMA))
            pagerank_score = round(pr_score, 6)
            blast_radius = round(pr_normalized, 3)
            systemic_threat_vector = [
                round(pr_normalized * (local_risk / 100.0), 3) for local_risk in local_risk_vector
            ]

        return {
            "pagerank_score": pagerank_score,
            "normalized_blast_radius": blast_radius,
            "betweenness_score": None if betweenness is None else round(betweenness, 6),
            "closeness_score": None if closeness is None else round(closeness, 6),
            "in_degree": in_d,
            "out_degree": out_d,
            "producer_ratio": round(producer_ratio, 3),
            "ecosystem_role": ecosystem_role,
            "systemic_threat_vector": systemic_threat_vector,
        }

    @staticmethod
    def _graph_index(parsed_files: list[dict[str, Any]], edges: dict[tuple[str, str], dict[str, Any]]) -> GraphIndex:
        """
        #3034: the CSR index every native graph metric reads, built once per scan
        from the resolved edges: files in scan order, edges in first-occurrence
        order, each edge weighted as the DiGraph's.
        """
        return GraphIndex(
            (f.get("path", "") for f in parsed_files),
            ((src, dst, attrs["weight"]) for (src, dst), attrs in edges.items()),
        )

    def _native_pagerank(self, index: GraphIndex) -> dict[str, float]:
        """
        #3027: the ONE PageRank both graph builders use, fed the same index
        (file order, first-occurrence edge order), so the two modes produce
        the same floats, not merely the same rounded values. Full precision used to
        call nx.pagerank, which in networkx 3.x dispatches to a numpy/scipy backend
        that networkx itself does not install -- with networkx alone it raised and
        every file's PageRank was silently lost -- and whose implementation can
        change between networkx releases. One implementation means no mode split
        and no installed version can move the numbers. Empty on failure, so every
        file reads None ("not computed"), never 0.0.
        """
        try:
            return dict(zip(index.nodes, pagerank(index)))
        except Exception as e:
            self.logger.warning(f"PageRank failed to converge, leaving it unset (None): {e}")
            return {}

    def _path_metrics(self, index: GraphIndex) -> tuple[dict[str, Optional[float]], Optional[float]]:
        """
        #3037: per-file closeness and the repo's average path length, from one
        native search in both modes (see graph_engine.closeness_and_path_length),
        so the two modes produce the same values. Computed at every graph size;
        past PATH_METRICS_WORK_BUDGET both are None ("not computed"), never 0.0.
        """
        try:
            closeness, avg_path_length = closeness_and_path_length(index, WorkBudget(PATH_METRICS_WORK_BUDGET))
        except WorkBudgetExceeded as e:
            self.logger.info(f"Closeness / avg path length past their work budget, leaving them unset (None): {e}")
            return dict.fromkeys(index.nodes), None
        return dict(zip(index.nodes, closeness)), avg_path_length

    @staticmethod
    def _topology_metrics(index: GraphIndex) -> dict[str, Optional[float]]:
        """
        The native repo-topology metrics, in both modes. Each is O(N + E), so no
        work budget is needed. All are None for a graph with no files, as the
        networkx path left them.
        - #3035: cyclic density (the share of files on a dependency cycle) and
          the articulation-point count
        - #3036: degree assortativity. An undefined correlation (no edges, or a
          degree that never varies) is 0.0: the value stored when networkx
          returned NaN.
        """
        n = len(index.nodes)
        if n == 0:
            return {"assortativity": None, "cyclic_density": None, "articulation_points": None}
        assortativity = degree_assortativity(index)
        return {
            "assortativity": 0.0 if math.isnan(assortativity) else round(assortativity, 4),
            "cyclic_density": round(nodes_in_cycles(index) / n, 4),
            "articulation_points": articulation_point_count(index),
        }

    def build_dependency_graph(self, parsed_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Builds the directed graph and calculates multi-dimensional risk vectors.
        Modifies the 'telemetry' dictionary of each file in place, and leaves
        the resolved edge list on `self.dependency_edges` (#2992).
        """
        if not HAS_NETWORKX:
            return self._fallback_build_graph(parsed_files)

        self.logger.info(f"Network Risk Sensor: Initializing Directed Graph for {len(parsed_files)} nodes...")

        G = nx.DiGraph()

        # 1. Add every file as a node, edges or not
        for f in parsed_files:
            path = f.get("path", "")

            # Add Node with Vector
            G.add_node(
                path,
                risk_vector=f.get("risk_vector", [0.0] * len(self.RISK_SCHEMA)),
            )

        # 2. Wire the Edges (File-to-File Level 1 & Entity Level 2)
        edges = self._resolve_edges(parsed_files)
        for (src, dst), attrs in edges.items():
            G.add_edge(src, dst, weight=attrs["weight"])
        self._publish_edges(edges)

        # =========================================================================
        # 3. NETWORK MATHEMATICS (Dependency Blast Radius & Centrality)
        # DEFENSIVE DESIGN: networkx's betweenness scales non-linearly, so above
        # 500 nodes it is sampled, otherwise the CI/CD pipeline would hit a
        # timeout deadlock.
        # =========================================================================
        # PageRank, closeness, avg path length and every repo-topology metric
        # but modularity are native in BOTH modes (see _native_pagerank,
        # _path_metrics, _topology_metrics), computed outside the networkx block
        # so a centrality failure can't take them down.
        index = self._graph_index(parsed_files, edges)
        pagerank = self._native_pagerank(index)
        closeness, avg_path_length = self._path_metrics(index)
        topology = self._topology_metrics(index)

        try:
            # Force a maximum sample size of 100 nodes for any graph > 500 nodes.
            # seed is fixed because k triggers *approximate* betweenness via random
            # node sampling -- unseeded, two scans of an unchanged repo can pick a
            # completely different sample and report different bottleneck files.
            k_val = min(len(G.nodes()), 100) if len(G.nodes()) > 500 else None
            betweenness = nx.betweenness_centrality(G, k=k_val, weight="weight", seed=42 if k_val is not None else None)
        except Exception as e:
            self.logger.warning(f"Centrality math failed, leaving betweenness unset (None): {e}")
            betweenness = dict.fromkeys(G.nodes())

        in_degrees = dict(G.in_degree())
        out_degrees = dict(G.out_degree())

        # 4. Vector Cross-Multiplication & Bottleneck Identification
        for f in parsed_files:
            path = f.get("path", "")
            if path not in G:
                continue

            in_d = in_degrees.get(path, 0)
            out_d = out_degrees.get(path, 0)

            # 5. Write Telemetry Back to the File Node
            if "telemetry" not in f:
                f["telemetry"] = {}

            f["telemetry"]["network_metrics"] = self._network_metrics(
                f, pagerank.get(path), betweenness.get(path), closeness.get(path), in_d, out_d
            )

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
            # #3036: native (see _topology_metrics).
            "assortativity": topology["assortativity"],
            # #3035: native (see _topology_metrics).
            "cyclic_density": topology["cyclic_density"],
            # #3037: native, mean hops over directed reachable pairs (see _path_metrics).
            "avg_path_length": None if avg_path_length is None else round(avg_path_length, 4),
            "articulation_points": topology["articulation_points"],
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

                # B-E. Assortativity, cyclic density, avg path length and
                # articulation points are native (#3035-#3037), set above.

            except Exception as e:
                self.logger.warning(f"Macro network math failed: {e}")

        self.logger.info("Network Risk Sensor: Vector Mathematics & Graph Topology Complete.")
        return parsed_files, macro_metrics

    def _fallback_build_graph(self, parsed_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        self.logger.warning(
            "[!] 'networkx' not found. Operating in Zero-Dependency Mode: degree counts, PageRank, closeness, avg path "
            "length, assortativity, cyclic density and articulation points are computed natively; betweenness and "
            "modularity are not computed (None)."
        )

        in_degrees = {f.get("path", ""): 0 for f in parsed_files}
        out_degrees = {f.get("path", ""): 0 for f in parsed_files}

        # Linear counting over the same resolved edges the DiGraph path wires,
        # one per edge -- i.e. distinct neighbours, exactly what the DiGraph's
        # in_degree/out_degree report. #3024: this used to add each edge's
        # import_statements instead, so a file importing the same target twice
        # read out_degree 2 here and 1 with networkx installed, and popularity,
        # internal_dependency_links, producer_ratio and ecosystem_role all
        # depended on which optional engines were installed. Degree is one of
        # the few network measurements this mode can compute exactly, so it
        # must mean the same thing in both modes.
        edges = self._resolve_edges(parsed_files)
        for src, dst in edges:
            out_degrees[src] = out_degrees.get(src, 0) + 1
            in_degrees[dst] = in_degrees.get(dst, 0) + 1
        self._publish_edges(edges)

        # #3027/#3035-#3037: the same native PageRank, closeness, avg path
        # length, assortativity, cyclic density and articulation points the
        # DiGraph path uses -- they need nothing but the edge list. Betweenness
        # stays None until it is native too (#3038).
        index = self._graph_index(parsed_files, edges)
        pagerank = self._native_pagerank(index)
        closeness, avg_path_length = self._path_metrics(index)
        topology = self._topology_metrics(index)

        for f in parsed_files:
            path = f.get("path", "")
            if "telemetry" not in f:
                f["telemetry"] = {}
            f["telemetry"]["network_metrics"] = self._network_metrics(
                f, pagerank.get(path), None, closeness.get(path), in_degrees.get(path, 0), out_degrees.get(path, 0)
            )
            f["telemetry"]["popularity"] = in_degrees.get(path, 0)

        # #473: None, not 0.0/0 -- zero-dependency mode means these were never
        # attempted at all (networkx isn't installed), not measured as zero.
        # Same convention as the real-computation path above.
        macro_metrics: dict[str, Optional[float]] = {
            "modularity": None,
            "assortativity": topology["assortativity"],
            "cyclic_density": topology["cyclic_density"],
            "avg_path_length": None if avg_path_length is None else round(avg_path_length, 4),
            "articulation_points": topology["articulation_points"],
        }
        return parsed_files, macro_metrics
