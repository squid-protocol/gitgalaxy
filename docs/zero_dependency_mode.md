# Zero-Dependency Mode

`pip install gitgalaxy` installs **nothing else**. For teams where every third-party package is a supply-chain review, that is the point: the engine runs on the Python standard library alone. A handful of measurements do need optional engines, though. When any of them is missing, the scan runs in **Zero-Dependency Mode**. This page lists, field by field, what that costs, so you can tell which numbers you can trust.

**Short version:**
- **Identical to full precision:** every structural signal, dependency edge, in/out-degree count, and **PageRank / blast radius**. PageRank is computed natively, with no networkx.
- **What you lose:** betweenness/closeness and the repo-topology metrics, token counts, ML threat classification, and YAML config parsing.
- **How missing metrics show up:** a metric that was not computed is **absent**: `None` in telemetry, NULL in the SQLite DB, `n/a` in the LLM brief. It is never a placeholder `0`. The one remaining exception is the ML placeholders described below (#3028).

## Getting full precision

```bash
pip install "gitgalaxy[full]"      # networkx, tiktoken, xgboost, pandas, numpy, pyyaml
```

Or add only the engines whose outputs you need (table below). Each is independent: a missing package only costs the rows under its heading. The one exception is `ai_threat_score` (see [Caveats](#caveats-in-the-current-release)).

## What each optional package provides

### `networkx`: betweenness, closeness and repo topology

| Output | With networkx | Without |
|---|---|---|
| In/out degree: `popularity`, `internal_dependency_links`, `dependency_density`, "Popularity Rank", "Direct Downstream" | distinct neighbouring files | **identical** (same resolved edges, counted linearly; #3024) |
| `producer_ratio`, `ecosystem_role` | from degree | **identical** |
| `edge_data` table (the edge list) | ✓ | **identical** |
| `pagerank_score`, `normalized_blast_radius`, `systemic_threat_vector` | native PageRank | **identical**: both modes run the same pure-Python PageRank on the same inputs (#3027), so the values cannot differ by mode or by networkx version |
| Total upstream/downstream reach (audit JSON §8) | graph descendants/ancestors | same numbers from a pure-Python BFS (can differ by 1 on files inside a cycle, or right at the 500-node cap) |
| `betweenness_score`, `closeness_score` | computed | **not computed**: `None` / NULL / `n/a` |
| Repo topology: `network_modularity`, `_assortativity`, `_cyclic_density`, `_avg_path_length`, `_articulation_points` | computed | **not computed**: `None` / NULL; LLM brief §3.5 shows `n/a (not computed)` |

Because PageRank is computed in both modes, `--max-systemic-threat`, the agent-guardrail `requires_hitl` flag, the composition archetypes, and the brief's "undocumented critical path" ranking and blast-radius insights all work exactly as with networkx.

Without betweenness/closeness:
- The "cascading state mutation" and "fragile dependency chain" bottleneck rankings are **empty**, not filled with zero-score files.
- The AI-topology "Cognitive Choke Point" insight is skipped.

**Even with networkx**, closeness is not computed above 1,500 files, or when the centrality computation fails. It is then `None` / NULL / `n/a` too, and the "fragile dependency chain" ranking is empty. `network_assortativity` also needs `numpy`: networkx declares no dependencies of its own, but its assortativity routine imports numpy, so with networkx alone assortativity is `None`.

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

## For contributors

Zero-dependency output is pinned by its own golden master, `tests/golden_master_zero_dep_audit.json`, checked by the `crucible-audit (zero-dependency)` CI job. `python tests/tools/crucible_check.py` verifies both modes locally. When you add a feature that needs an optional package, add its row here and to the console banner in `galaxyscope.py`. Record a metric you could not compute as `None`, never a placeholder `0`.
