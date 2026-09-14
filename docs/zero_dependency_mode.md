# Zero-Dependency Mode

`pip install gitgalaxy` installs **nothing else**. For teams where every third-party package is a supply-chain review, that is the point: the engine runs on the Python standard library alone. A handful of measurements do need optional engines, though. When any of them is missing, the scan runs in **Zero-Dependency Mode**. This page lists, field by field, what that costs, so you can tell which numbers you can trust.

**Short version:** every structural signal, dependency edge and in/out-degree count is measured **exactly as in full precision**. What you lose is PageRank-family graph math, token counts, ML threat classification and YAML config parsing. Values those engines never computed show as **NULL in the SQLite DB**, but as **`0` / `0.0` in the other outputs**. Those zeros are placeholders, not measurements (tracked in #3027).

## Getting full precision

```bash
pip install "gitgalaxy[full]"      # networkx, tiktoken, xgboost, pandas, numpy, pyyaml
```

Or add only the engines whose outputs you need (table below). Each is independent: a missing package only costs the rows under its heading. One exception is the SQLite DB's global NULLing (see [Caveats](#caveats-in-the-current-release)).

## What each optional package provides

### `networkx`: graph centrality and topology

| Output | With networkx | Without |
|---|---|---|
| In/out degree: `popularity`, `internal_dependency_links`, `dependency_density`, "Popularity Rank", "Direct Downstream" | distinct neighbouring files | **identical** (same resolved edges, counted linearly; #3024) |
| `producer_ratio`, `ecosystem_role` | from degree | **identical** values (NULL in the DB, see caveats) |
| `edge_data` table (the edge list) | ✓ | **identical** |
| Total upstream/downstream reach (audit JSON §8) | graph descendants/ancestors | same numbers from a pure-Python BFS (can differ by 1 on files inside a cycle, or right at the 500-node cap) |
| `pagerank_score`, `normalized_blast_radius`, `betweenness_score`, `closeness_score` | computed | **not computed**: NULL in the DB, `0.0` elsewhere |
| `systemic_threat_vector` | per-risk vector | `[]` |
| Repo topology: `network_modularity`, `_assortativity`, `_cyclic_density`, `_avg_path_length`, `_articulation_points` | computed | **not computed**: NULL in the DB; the LLM brief §3.5 table shows `0` |

Knock-on effects without networkx:
- `--max-systemic-threat` **is skipped with a warning**, because it multiplies by blast radius. Before this release it silently could never fail.
- The agent-guardrail `requires_hitl` flag (keyed on blast radius) can never fire.
- The composition archetype classifier sees zero PageRank features, so the file and repo composition archetypes can differ from a full-precision scan.
- LLM brief §13.8 (systemic bottlenecks) is omitted. The brief's AI-topology note can wrongly say "Containment (Low Risk)" (#3027).

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
| DB `ai_threat_class` / `ai_threat_confidence` / `is_malware` | `'Safe'` / `0.0` / `0` (placeholders) |
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

These are known gaps between the rule "unavailable means NULL" and today's behaviour. Each has an open issue:

- **Placeholder zeros outside the DB** (#3027). The networkx metrics above read as `0.0` in the audit/GPU JSON and the LLM brief, rather than as absent.
- **The DB NULLs on the global flag, not per package** (#3028). If *any* optional package is missing, the DB NULLs every networkx column and `ai_threat_score`. So a scan missing only `pyyaml` also discards real PageRank and ML scores in the DB, and `producer_ratio` / `ecosystem_role` are NULLed even though they are exact. `pandas` / `numpy` are also reported under the `xgboost` name.
- Snapshots recorded **before #3024** have zero-dependency degree values that counted import *statements*, not distinct files. They read higher wherever one file imported the same target more than once.

## For contributors

Zero-dependency output is pinned by its own golden master, `tests/golden_master_zero_dep_audit.json`, checked by the `crucible-audit (zero-dependency)` CI job. `python tests/tools/crucible_check.py` verifies both modes locally. When you add a feature that needs an optional package, add its row here and to the console banner in `galaxyscope.py`.
