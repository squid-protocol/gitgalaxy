# Zero-Dependency Mode

`pip install gitgalaxy` installs **nothing else**. For teams where every third-party package is a supply-chain review, that is the point: the engine runs on the Python standard library alone. A handful of measurements do need optional engines, though. When any of them is missing, the scan runs in **Zero-Dependency Mode**. This page lists, field by field, what that costs, so you can tell which numbers you can trust.

**Short version:**
- **Identical to full precision:** every structural signal, dependency edge, in/out-degree count, **PageRank / blast radius**, **closeness**, **average path length**, **cyclic density**, **articulation points**, **assortativity**, **betweenness** and **modularity**. These are computed natively, with no networkx.
- **What you lose:** token counts, ML threat classification, and YAML config parsing.
- **How missing metrics show up:** a metric that was not computed is **absent**: `None` in telemetry, NULL in the SQLite DB, `n/a` in the LLM brief. It is never a placeholder `0`. The one remaining exception is the ML placeholders described below (#3028).

## Getting full precision

```bash
pip install "gitgalaxy[full]"      # networkx, tiktoken, xgboost, pandas, numpy, pyyaml
```

Or add only the engines whose outputs you need (table below). Each is independent: a missing package only costs the rows under its heading. The one exception is `ai_threat_score` (see [Caveats](#caveats-in-the-current-release)).

## What each optional package provides

### `networkx`: nothing, since #3039

| Output | With networkx | Without |
|---|---|---|
| In/out degree: `popularity`, `internal_dependency_links`, `dependency_density`, "Popularity Rank", "Direct Downstream" | distinct neighbouring files | **identical** (same resolved edges, counted linearly; #3024) |
| `producer_ratio`, `ecosystem_role` | from degree | **identical** |
| `edge_data` table (the edge list) | ✓ | **identical** |
| `pagerank_score`, `normalized_blast_radius`, `systemic_threat_vector` | native PageRank | **identical**: both modes run the same pure-Python PageRank on the same inputs (#3027), so the values cannot differ by mode or by networkx version |
| Total upstream/downstream reach (audit JSON §8) | graph descendants/ancestors | same numbers from a pure-Python BFS (can differ by 1 on files inside a cycle, or right at the 500-node cap) |
| `closeness_score`, `network_avg_path_length` | native | **identical**: both modes run the same native breadth-first search (#3037) |
| `network_cyclic_density`, `network_articulation_points` | native | **identical**: both modes run the same native depth-first searches (#3035) |
| `network_assortativity` | native | **identical**: both modes run the same native single pass over the edges (#3036), which needs no numpy |
| `betweenness_score` | native | **identical**: both modes run the same exact native search (#3038) |
| `network_modularity` | native | **identical**: both modes run the same port of networkx's seeded Louvain (#3039) |

Since #3039 every graph metric is native, so a scan without networkx loses nothing on the graph side. #3041 removes networkx from the runtime.

Because every centrality is computed in both modes, these all work exactly as with networkx:
- `--max-systemic-threat` and the agent-guardrail `requires_hitl` flag
- the composition archetypes
- the brief's "undocumented critical path", "fragile dependency chain" and "cascading state mutation" rankings
- its blast-radius insights and the AI-topology "Cognitive Choke Point" insight

**In both modes**, betweenness, closeness, average path length and modularity are computed at every repository size. The only limit is a deterministic work budget: 50 million edge scans per search, which counts work, never time. Past it, the metric is `None` / NULL / `n/a`, and the ranking built on it is empty. An import graph stays far below the budget: language-crucible's 2,817 files take about 2 ms per search.

**Average path length changed meaning in #3037.**
- **Now:** the mean number of import hops from a file to each file it transitively depends on, over every such (importer, dependency) pair in the repository.
- **Before:** the mean shortest path in the largest *undirected* component. That ignored import direction and covered only 22.5% of language-crucible's files. It was also skipped above 5,000 files.
- The two are not comparable. Language-crucible reads 1.36 now vs 7.07 before. #3033 measured the self-scan at 1.71 vs 4.19.

**Betweenness changed meaning in #3038.**
- **Now:** exact, with every file as a source, and shortest paths counted in import hops.
- **Before:** above 500 files, networkx sampled 100 seeded sources. In every size of graph it read each edge's weight as a distance, so an entity import, a stronger coupling, counted as a longer path.
- On language-crucible the sample found 11 files with nonzero betweenness against 41 exact, and read 14 of the exact top 20 choke points as 0. Above 500 files the old and new values are not comparable; below that they differ only where an entity import changed a shortest path.

### `tiktoken`: token counts

| Output | Without |
|---|---|
| `token_mass`, `financial_read_cost` (file level), `function_data.token_mass` | NULL (never estimated) |
| Agent-guardrail `is_agentic_black_hole` / `agentic_isolation_risk` (token mass > 8000) | can never fire (reads 0) |

### `xgboost` + `pandas` + `numpy`: ML threat classification

They are loaded together, so a missing one disables all three.

| Output | Without |
|---|---|
| ML threat inference | **skipped** |
| DB `ai_threat_class` / `ai_threat_confidence` / `is_malware` | `'Safe'` / `0.0` / `0` (placeholders, #3028) |
| DB `ai_threat_score` | NULL |
| Audit JSON "Infected Files Detected", GPU JSON `ai_threats`, SARIF ML results | 0 / none |
| `--fail-on-malware` | can never fire |

Rule-based threat detection is unaffected: hardcoded secrets, `--fail-on-secrets`, and the `threat_*` signal columns are regex signals.

### `pyyaml`: YAML configuration

| Output | Without |
|---|---|
| `--config` / `.galaxyscope.yaml` | **ignored** with a warning, so every setting falls back to its default |
| YAML (`.yaml`/`.yml`) OpenAPI/Swagger specs | not parsed, so `audit_shadow_apis` reads 0 |

## Telling which mode a scan ran in

| Output | Marker |
|---|---|
| Console | a boxed `ZERO-DEPENDENCY MODE ACTIVE` banner at start listing what each missing package costs, plus a note at the end |
| SQLite DB | `repo_data.is_zero_dependency_mode = 1` |
| Audit JSON | "Zero-Dependency Mode Active" and "Missing Dependencies" |
| GPU JSON | `meta.zero_dependency_mode`, `meta.missing_dependencies` |
| SARIF | notification `GG-SYS-ZERO-DEP` |
| CycloneDX SBOM | property `gitgalaxy:zero_dependency_mode` |
| LLM brief | §0 "Zero-Dependency Mode" row and a banner naming the missing packages |

## Caveats in the current release

- **ML placeholders and the global flag (#3028).**
  - Without the ML engines, the DB's `ai_threat_class` / `ai_threat_confidence` / `is_malware` read as `'Safe'` / `0.0` / `0`, not NULL.
  - `ai_threat_score` is NULLed whenever *any* optional package is missing, even when xgboost ran.
  - `pandas` / `numpy` are reported under the `xgboost` name.
  - (The network columns used to be NULLed the same way; since #3027 they are recorded exactly as computed.)
- **Older snapshots:**
  - Recorded before **#3024**: zero-dependency degree values counted import *statements*, not distinct files, so they read higher wherever one file imported the same target more than once.
  - Recorded before **#3027**: zero-dependency PageRank / blast radius were `0.0` placeholders (NULL in the DB), and closeness above 1,500 files was `0.0` in every mode.
  - Recorded before **#3037**:
    - closeness was NULL in zero-dependency mode, and NULL above 1,500 files in every mode
    - `network_avg_path_length` meant the undirected largest-component distance (see above), so it is not comparable with later snapshots
  - Recorded before **#3035**: zero-dependency `network_cyclic_density` / `network_articulation_points` were NULL. The definitions did not change, so later values compare directly with full-precision history.
  - Recorded before **#3036**: `network_assortativity` was NULL in zero-dependency mode, and also NULL when networkx was installed without numpy. The definition did not change.
  - Recorded before **#3038**: `betweenness_score` was NULL in zero-dependency mode, and sampled and weighted above 500 files in every mode (see above).
  - Recorded before **#3039**: `network_modularity` was NULL in zero-dependency mode, and NULL above 5,000 files in every mode. The definition did not change.

## For contributors

Zero-dependency output is pinned by its own golden master, `tests/golden_master_zero_dep_audit.json`, checked by the `crucible-audit (zero-dependency)` CI job. `python tests/tools/crucible_check.py` verifies both modes locally. When you add a feature that needs an optional package, add its row here and to the console banner in `galaxyscope.py`. Record a metric you could not compute as `None`, never a placeholder `0`.
