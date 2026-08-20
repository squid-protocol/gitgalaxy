# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-08-20T22:00:51.917159+00:00` |
| **Scan Duration** | `8.98s` |
| **Git Branch** | `main` |
| **Git Commit** | `6d8f5d5d853e4157f26d9e6324a4ce253cecb7ca` |
| **Git Remote** | `https://github.com/squid-protocol/gitgalaxy` |
| **Zero-Dependency Mode** | `Inactive (Full Precision)` |

## 0.5 AI THREAT AUDIT STATUS
> **✅ SECURE_NO_THREATS_DETECTED**
> XGBoost Structural Signatures model found no malicious artifacts.

## 1. SYSTEM ROLE & PHILOSOPHY
> You are a Senior Technical Storyteller and Codebase Architect. GitGalaxy has translated the non-visual architecture of this repository into measurable Structural Signatures (regex-derived counts, not an AST or compiler pass). Your job is to weave those signatures into a coherent, factual narrative about how this system is built -- its architecture, design patterns, and complexity -- not to render a verdict.
> 
> **CORE DIRECTIVES:**
> 1. **Narrate the Architecture, Don't Judge the Author:** Frame every observation as a blameless description of the system's physical reality. High Risk Exposure (e.g., Cognitive Load Exposure) describes where the architecture may be drifting into fragile territory, not developer incompetence -- it is a prompt to investigate, never a verdict.
> 2. **The Physical Reality Rule:** Base your narrative strictly on the provided Structural Signatures and the numbers derived from them. Do not hallucinate meaning, and do not restate a heuristic's raw label (e.g. a 'Logic Bomb' or 'O(2^N)' flag) as a confirmed finding of malice or a guaranteed defect -- explain what the signature actually measures, weave it into the story of the file, and let the reader draw their own conclusion.
> 3. **Risk vs. Defense:** Code is a balance. A file with high `flux` (state mutation) is risky unless balanced by `freeze_hits` (immutability). High `danger` is brittle unless wrapped in `safety`. Tell that balance as part of the narrative, not as an isolated alarm.
> 
> **THE STRUCTURAL SIGNATURE LEXICON:**
> * **Structure & Mass:** `branch` (splits), `linear` (paths), `args` (coupling), `func_start` (entry points).
> * **Risk & Volatility:** `danger` (dynamic execution), `flux` (state mutation), `graveyard` (commented-out logic), `safety_neg` (security bypasses).
> * **Architecture & Domain:** `io` (network latency), `concurrency` (async orchestration), `api` (public surface), `import` (dependencies).
> * **Defensive Guardrails:** `safety` (Error handling), `freeze_hits` (immutability), `cleanup` (state destruction).
## 2. THE 13-POINT RISK EXPOSURE ANALYSIS (EQUATIONS & CONTEXT)
> **How the SAST Engine Calculates Risk Exposure (Lower Risk 0 - Higher Risk Exposure 100%):**
> Most scores use a Sigmoid curve based on density (Hits / LOC) to prevent massive files from mathematically hiding their flaws.
> 
> 1. **Cognitive Load Exposure:** Measures the mental effort required for a developer to read and understand the file. `Density(Branches + (Flux * 2) + Async/Danger)` mitigated by `Doc Coverage`.
> 2. **Error & Exception Risk Exposure:** Measures structural integrity and resilience against runtime errors. `Net Exposure = (Danger + Safety_Neg + Flux) - (Safety + Tests + Docs)`.
> 3. **Tech Debt Exposure:** Measures the density of developer-annotated structural stress. `Density(TODOs [1x] + FIXMEs/Hacks [3x] + Empty Stubs [0.5x])`.
> 4. **Verification Risk Exposure:** Evaluates test coverage by comparing a function's structural complexity against the scope of the tests validating it.
> 5. **API Risk Exposure:** Measures the public surface area of a module. `Ratio(API Hits / Total Functions & Classes)`.
> 6. **Concurrency Risk Exposure:** Measures the density of asynchronous operations, threading, and parallel execution logic.
> 7. **State Flux Risk Exposure:** Measures the frequency of data mutation and variable reassignment.
> 8. **Commented Logic (dead code):** Measures the presence of abandoned, commented-out logic blocks.
> 9. **Spec Match Risk Exposure:** Measures how closely code aligns with formal specifications or architectural requirements.
> 10. **Stability:** Measures the recency of edits relative to the repository's entire lifespan.
> 11. **Deep Churn:** Measures the historical volatility and frequency of modification.
> 12. **Documentation Risk Exposure:** Measures the lack of structured documentation and ownership metadata.
> 13. **Indentation Consistency:** Measures formatting alignment (Tabs vs. Spaces). Provided for codebase standardization context, not a functional risk.
> 
> **--- THE SECURITY & VULNERABILITY LENS ---**
> 14. **Obfuscation & Evasion Risk:** Measures the density of obfuscated logic, packed strings, and non-standard encoding.
> 15. **Logic Bomb / Sabotage Risk:** Measures condition-heavy execution leading to destructive OS, memory, or process commands.
> 16. **Injection Surface Risk Exposure:** Measures external network/I/O input flowing directly into dynamic execution contexts (XSS, SQLi, RCE).
> 17. **Memory Corruption Risk Exposure:** Measures the density of raw pointer math and manual memory allocations (Buffer Overflows, UAF).
> 18. **Secrets Risk Exposure:** Measures the presence of hardcoded credentials exposed to logs or globals.
> 
> **--- STRUCTURAL MAGNITUDE (NOT RISK) ---**
> **19. Function Magnitude (Impact Score):** Measures the physical footprint and 'heaviness' of a specific function. `((BranchHits + 1) * (Args + 1) + (0.05 * LOC)) * 10`. This is NOT a risk score.
> **20. File Magnitude (Total Impact):** Measures the total structural impact of a file. `Sum(Function Impacts) + API + Concurrency + Flux + (LOC / 50)`. This is NOT a risk score.

## 3. MACRO STATE
| Metric | Value |
|---|---|
| Total Artifacts | 821 |
| Analyzed Artifacts (Scanned) | 280 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 541 |
| Total LOC | 59393 |
| Volatility Index | 0.007 |
| % Scanned of codebase = | 34.1% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.7414 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.3527 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 4.2989 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 45 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 241 | 58888 | 86.1% |
| MARKDOWN | 27 | 0 | 9.6% |
| YAML | 8 | 483 | 2.9% |
| PLAINTEXT | 3 | 0 | 1.1% |
| SHELL | 1 | 22 | 0.4% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `4.876`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 150 | 53.6% |
| file_cluster_13 | 68 | 24.3% |
| file_cluster_0 | 21 | 7.5% |
| file_cluster_16 | 8 | 2.9% |
| file_cluster_17 | 2 | 0.7% |
| file_cluster_6 | 1 | 0.4% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 30 | 10.7% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 541*

**Composition by Extension & Reason:**
- `.md`: 362x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 41 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.json`: 40x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yml`: 22x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 551 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csv`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 61.4 | 2.1 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 96.0 | 6.1 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 100.0 | 1.6 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 3.7 | 0.0 | 0.0 |
| API Exposure | 0.0 | 8.1 | 0.2 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 27.8 | 0.3 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 6.1 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 11.2 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 10.6 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 13.0 | 0.6 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 2.3 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 89.1 | 2.0 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `bitbucket-pipelines.yml` (Hits: 10)
- `gitgalaxy/core/guidestar_lens.py` (Hits: 8)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 48 inbound connections
2. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 45 inbound connections
3. **detector.py** (`gitgalaxy/core/detector.py`) — 14 inbound connections
4. **config_resolver.py** (`gitgalaxy/standards/config_resolver.py`) — 9 inbound connections
5. **gitgalaxy_config.py** (`gitgalaxy/standards/gitgalaxy_config.py`) — 9 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 56 outbound dependencies
2. **test_python_strict.py** (`tests/extraction/languages/test_python_strict.py`) — 27 outbound dependencies
3. **test_embedded_python.py** (`tests/extraction/languages/test_embedded_python.py`) — 20 outbound dependencies
4. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 19 outbound dependencies
5. **test_scala.py** (`tests/extraction/languages/test_scala.py`) — 19 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_process_file_worker` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **1205.8** | LOC: 2835
- `_get_node_name` (@ `tests/tools/tree_sitter_accuracy_audit.py`) -> Impact: **1116.7** | LOC: 2173
- `_parse_pyproject_toml` (@ `gitgalaxy/security/manifest_parser.py`) -> Impact: **350.2** | LOC: 404
- `_count_haskell_pattern_list` (@ `gitgalaxy/core/detector.py`) -> Impact: **279.4** | LOC: 635
- `_calc_indentation_style` (@ `gitgalaxy/metrics/signal_processor.py`) -> Impact: **275.9** | LOC: 737
- `_resolve_target` (@ `gitgalaxy/core/network_risk_sensor.py`) -> Impact: **219.8** | LOC: 372
- `_tier_2_fingerprint_check` (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **214.1** | LOC: 401
  * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents generic files from bypassing deep-inspection. if ex...
- `test_detector_exact_loc_mapping` (@ `tests/core_engine/test_detector.py`) -> Impact: **182.5** | LOC: 463
  * *Intent:* # ============================================================================== # TEST 43: SPATIAL MAPPER MISSING KEYS # ============================...
- `_git_archive_extract` (@ `tests/ast_accuracy_audit.py`) -> Impact: **164.5** | LOC: 346
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **142.8** | LOC: 362

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `tests/extraction/languages` | 92 | 13208.95 | 3.33% | 0.0% |
| `tests/core_engine` | 22 | 2388.84 | 2.82% | 0.0% |
| `gitgalaxy` | 6 | 1754.78 | 8.62% | 0.0% |
| `gitgalaxy/core` | 9 | 1569.16 | 15.56% | 6.59% |
| `gitgalaxy/recorders` | 8 | 1128.64 | 20.65% | 3.3% |
| `tests/security_auditing` | 15 | 986.5 | 1.99% | 0.0% |
| `gitgalaxy/metrics` | 5 | 921.48 | 18.93% | 4.56% |
| `gitgalaxy/security` | 5 | 780.0 | 14.49% | 0.0% |
| `gitgalaxy/standards` | 7 | 646.66 | 6.8% | 6.81% |
| `tests` | 8 | 509.18 | 7.45% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `scripts/update_golden_masters.sh` -> **99.956%** Exposure
- `action.yml` -> **99.876%** Exposure
- `bitbucket-pipelines.yml` -> **99.4071%** Exposure
- `gitgalaxy/core/prism.py` -> **30.1712%** Exposure
- `gitgalaxy/core/detector.py` -> **18.5548%** Exposure
### Highest State Flux (Mutation/Volatility)
- `gitgalaxy/recorders/llm_recorder.py` -> **100.0%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **99.9992%** Exposure
- `gitgalaxy/core/prism.py` -> **99.9586%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **99.71%** Exposure
- `bitbucket-pipelines.yml` -> **99.6681%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `action.yml` -> **0** Orphaned Functions | **2** Duplicates
- `bitbucket-pipelines.yml` -> **0** Orphaned Functions | **2** Duplicates
- `scripts/update_golden_masters.sh` -> **1** Orphaned Functions | **0** Duplicates

## 10.5 AI THREAT INTELLIGENCE (XGBoost)
*No files met the threshold for malicious structural signatures.*

## 10.6 WEAPONIZABLE SURFACE EXPOSURES (RULE-BASED SAST)
> Secondary Evidence: The following files tripped specific static threat signatures. Use these to explain *why* the XGBoost model flagged the files above.

*No critical vulnerabilities or security lens thresholds breached.*

## 10.7 ECOSYSTEM SECURITY AUDITS
> **AI CONTEXT:** High-level perimeter defense metrics from the X-Ray, Supply Chain Firewall, and API Network Mapper.

### ☢️ X-Ray & 🧱 Supply Chain Firewall
- **Binary Anomalies (X-Ray):** `0` (High entropy, packed payloads, or magic byte mismatches).
- **Blacklisted Dependencies:** `0` explicitly banned packages imported.
- **Unknown Dependencies:** `1621` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **500.05**
- **Archetype:** `file_cluster_16` (Distance: 11.97 IQR)
- **Magnitude:** 442.74 | **LOC:** 1144 | **CtrlFlow:** 67.1% | **Authorship Centralization:** 92.3%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.9586%), Safety Score (82.165%), Verification (80.0%)
- **Heaviest Functions:** `_strip_single_line_comments` (Impact: 120.2), `_find_balanced_end` (Impact: 111.6), `_partition_embedded_languages` (Impact: 39.6)

### 2. `gitgalaxy/core/detector.py` (PYTHON) -> Cumulative Risk: **483.45**
- **Archetype:** `file_cluster_8` (Distance: 12.676 IQR)
- **Magnitude:** 591.72 | **LOC:** 5010 | **CtrlFlow:** 75.7% | **Authorship Centralization:** 90.5%
- **Primary Risk Drivers:** Spec Match (100.0%), Churn (100.0%), Verification (80.0%), Safety Score (59.9217%)
- **Heaviest Functions:** `_count_haskell_pattern_list` (Impact: 279.4), `_resolve_class_start_match` (Impact: 31.8), `_count_haskell_type_arrows` (Impact: 20.1)

### 3. `gitgalaxy/recorders/llm_recorder.py` (PYTHON) -> Cumulative Risk: **458.08**
- **Archetype:** `file_cluster_8` (Distance: 13.251 IQR)
- **Magnitude:** 753.72 | **LOC:** 1407 | **CtrlFlow:** 85.9% | **Authorship Centralization:** 87.5%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (96.0314%), Cognitive Load (61.3945%)
- **Heaviest Functions:** `__init__` (Impact: 5.8), `_parse_threat_score` (Impact: 3.9), `generate_artifacts` (Impact: 1.4)

### 4. `gitgalaxy/tools/cobol_to_java/cobol_to_java_service_forge.py` (PYTHON) -> Cumulative Risk: **447.81**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.06 | **LOC:** 97 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `generate_service_skeleton` (Impact: 14.3), `main` (Impact: 6.3)

### 5. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **439.1**
- **Archetype:** `file_cluster_8` (Distance: 11.061 IQR)
- **Magnitude:** 243.32 | **LOC:** 537 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.311%), Safety Score (82.0287%), Verification (80.0%)
- **Heaviest Functions:** `audit` (Impact: 142.8), `_is_dead_code` (Impact: 9.8), `_is_threat` (Impact: 9.5)

### 6. `gitgalaxy/metrics/signal_processor.py` (PYTHON) -> Cumulative Risk: **423.77**
- **Archetype:** `file_cluster_8` (Distance: 11.091 IQR)
- **Magnitude:** 435.02 | **LOC:** 2043 | **CtrlFlow:** 74.4% | **Authorship Centralization:** 81.8%
- **Primary Risk Drivers:** Spec Match (100.0%), Verification (80.0%), Safety Score (56.575%), Churn (55.93%)
- **Heaviest Functions:** `_calc_indentation_style` (Impact: 275.9), `_normalize_temporal_metrics` (Impact: 13.7), `_calc_ownership_entropy` (Impact: 9.7)

### 7. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **422.72**
- **Archetype:** `file_cluster_8` (Distance: 12.064 IQR)
- **Magnitude:** 1441.6 | **LOC:** 3085 | **CtrlFlow:** 71.4% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Verification (80.0%), State Flux (79.1636%), Safety Score (62.8962%)
- **Heaviest Functions:** `_process_file_worker` (Impact: 1205.8), `execution_timeout_failsafe` (Impact: 1.9), `_init_worker` (Impact: 1.4)

### 8. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **409.05**
- **Archetype:** `file_cluster_13` (Distance: 10.697 IQR)
- **Magnitude:** 189.4 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (97.3782%), Verification (80.0%), Safety Score (68.5044%)
- **Heaviest Functions:** `main` (Impact: 50.1), `process_payload` (Impact: 26.8), `record_dead_code` (Impact: 14.4)

### 9. `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) -> Cumulative Risk: **394.22**
- **Archetype:** `file_cluster_8` (Distance: 11.638 IQR)
- **Magnitude:** 128.04 | **LOC:** 441 | **CtrlFlow:** 65.1% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.9992%), Safety Score (90.3802%), Cognitive Load (46.8693%)
- **Heaviest Functions:** `__init__` (Impact: 7.2), `save_minified` (Impact: 6.6), `_intern` (Impact: 4.3)

### 10. `gitgalaxy/core/network_risk_sensor.py` (PYTHON) -> Cumulative Risk: **392.38**
- **Archetype:** `file_cluster_13` (Distance: 11.0 IQR)
- **Magnitude:** 260.22 | **LOC:** 442 | **CtrlFlow:** 68.1% | **Authorship Centralization:** 66.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Verification (80.0%), Safety Score (73.4783%), State Flux (50.9709%)
- **Heaviest Functions:** `_resolve_target` (Impact: 219.8), `_build_resolution_map` (Impact: 9.6), `__init__` (Impact: 5.3)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 12.064 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.572 IQR)
- **Top Global Matches:** file_cluster_8: 12.064, file_cluster_13: 12.195, file_cluster_7: 12.457
- **Magnitude:** 1441.6 | **LOC:** 3085 | **CtrlFlow:** 71.4% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (20.8603%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_process_file_worker` (Impact: 1205.8)
  * `execution_timeout_failsafe` (Impact: 1.9)
    * *Intent:* """ Hardware-level OS interrupt for Catastrophic Backtracking (ReDoS) protection. Registered via the...
  * `_init_worker` (Impact: 1.4)
    * *Intent:* """ raise TimeoutError("Structural Saturation (ReDoS Timeout)") def _init_worker( root_str: str, con...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 539`, `structural_boundaries: 216`, `args: 32`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 77`, `state_mutation: 183`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 3`, `import: 63`
* *Defense:* `safety: 74`, `doc: 36`, `test: 2`, `cleanup: 6`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 4.458
  * `Choke Point (Betweenness):` 0.00107 | `Ripple Effect (Closeness):` 0.010753
  * `Imports (Out-Degree: 29):` signal, time, gitgalaxy.core.aperture, gitgalaxy.recorders.gpu_recorder, copy, gitgalaxy.standards.analysis_lens, gitgalaxy.core.detector, gitgalaxy.core.spatial_correlation...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_powershell_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 983.67 | **LOC:** 478 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, pytest, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_objectivec_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 971.43 | **LOC:** 264 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, pytest, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_tcl_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 831.22 | **LOC:** 272 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, pytest, sys, pathlib, gitgalaxy.standards.language_standards, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_solidity_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 802.93 | **LOC:** 272 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, pytest, legacy, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 13.251 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.146 IQR)
- **Top Global Matches:** file_cluster_8: 13.251, file_cluster_13: 13.5, file_cluster_17: 13.504
- **Magnitude:** 753.72 | **LOC:** 1407 | **CtrlFlow:** 85.9% | **Authorship Centralization:** 87.5%
- **Risk Profile:** Cognitive Load (61.3945%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 5.8)
  * `_parse_threat_score` (Impact: 3.9)
  * `generate_artifacts` (Impact: 1.4)
  * `_build_markdown` (Impact: 1.4)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 293`, `structural_boundaries: 48`, `args: 27`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 704`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 13`, `doc: 27`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.272
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.011201
  * `Imports (Out-Degree: 0):` gitgalaxy.standards, logging, heapq, sqlite3, json, collections, typing, pathlib...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_yacc.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 678.9 | **LOC:** 92 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, sys, extraction._extraction_harness, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_ruby_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 645.28 | **LOC:** 248 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, pytest, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 630.52 | **LOC:** 3332 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_detector_exact_loc_mapping` (Impact: 182.5)
    * *Intent:* # ============================================================================== # TEST 43: SPATIAL ...
  * `test_detector_prose_and_empty_bypass` (Impact: 22.1)
    * *Intent:* """ val1 = spatial_mapper._hash_jitter("auth_service", 100.0) val2 = spatial_mapper._hash_jitter("au...
  * `test_detector_atomic_literal_shield` (Impact: 21.1)
  * `test_detector_c_macro_else_branch_is_sca` (Impact: 18.8)
  * `test_spatial_mapper_sectorization_and_mo` (Impact: 18.6)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, gitgalaxy.core.spatial_mapper, pytest, gitgalaxy.core.detector, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.core.prism, unittest.mock, gitgalaxy.standards.language_standards...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_makefile.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 608.25 | **LOC:** 331 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, only, typing, _extraction_harness, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_yaml_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 596.6 | **LOC:** 383 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` this, _strict_harness, pytest, and, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 12.676 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.304 IQR)
- **Top Global Matches:** file_cluster_8: 12.676, file_cluster_16: 12.864, file_cluster_13: 12.891
- **Magnitude:** 591.72 | **LOC:** 5010 | **CtrlFlow:** 75.7% | **Authorship Centralization:** 90.5%
- **Risk Profile:** Cognitive Load (29.3507%), Tech Debt (18.5548%)
**Top Internal Functions/Classes:**
  * `_count_haskell_pattern_list` (Impact: 279.4)
  * `_resolve_class_start_match` (Impact: 31.8)
  * `_count_haskell_type_arrows` (Impact: 20.1)
  * `_count_shell_positional_max` (Impact: 16.2)
  * `get_token_mass` (Impact: 6.4)
    * *Intent:* """Calculates context window footprint. Returns None if tiktoken is missing to prevent dataset poiso...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 952`, `structural_boundaries: 305`, `args: 42`, `func_start: 41`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 63`, `state_mutation: 158`, `dead_code: 30`, `planned_debt: 1`, `fragile_debt: 17`
* *Architecture:* `api: 15`, `concurrency: 1`, `import: 14`
* *Defense:* `safety: 40`, `doc: 107`, `test: 2`, `immutability_locks: 7`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 14.261
  * `Choke Point (Betweenness):` 0.000327 | `Ripple Effect (Closeness):` 0.051792
  * `Imports (Out-Degree: 2):` tiktoken, logging, time, gitgalaxy.standards.analysis_lens, collections, typing, hashlib, gitgalaxy.core.spatial_correlation...
  * `Imported By (In-Degree: 14):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 511.1 | **LOC:** 748 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_parse_pyproject_toml` (Impact: 350.2)
  * `_parse_requirements_txt` (Impact: 50.4)
    * *Intent:* # DEFENSIVE GUARD: Registry Spoofing # If the resolved URL points to a non-standard domain or a dire...
  * `_parse_package_json` (Impact: 23.4)
  * `build_resolution_map` (Impact: 22.8)
    * *Intent:* # Matches standard Python packages, extracting the base name and dropping version constraints (==, >...
  * `_parse_package_lock` (Impact: 17.1)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, os, typing, pathlib, re, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 484.04 | **LOC:** 2103 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_git_null_byte_path_injection` (Impact: 76.0)
    * *Intent:* # When entering the context manager, return our mock instance # Mock Path.exists to pass the initial...
  * `_clean` (Impact: 68.7)
    * *Intent:* # ============================================================================== # TEST 6: THE NULL-...
  * `test_recorder_exception_survivability` (Impact: 20.1)
  * `test_sarif_ignored_paths_sanitization` (Impact: 13.7)
    * *Intent:* # Mock sys.argv to target a project named "chameleon_project" test_args = ["galaxyscope", "/fake/cha...
  * `test_delta_scanning_fallbacks` (Impact: 13.5)
    * *Intent:* # ============================================================================== # TEST 21: GIT META...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.core.aperture, passes, gitgalaxy.standards.analysis_lens, gitgalaxy.galaxyscope, pathlib, failure, logging, must...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_java.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 474.82 | **LOC:** 403 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` java.util.List, java.util., ..., pytest, static, only, typing, _extraction_harness...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_scheme.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 451.31 | **LOC:** 135 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, _extraction_harness, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_16` (Drift: 11.97 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.161 IQR)
- **Top Global Matches:** file_cluster_16: 11.97, file_cluster_8: 11.982, file_cluster_7: 12.235
- **Magnitude:** 442.74 | **LOC:** 1144 | **CtrlFlow:** 67.1% | **Authorship Centralization:** 92.3%
- **Risk Profile:** Cognitive Load (29.5806%), Tech Debt (30.1712%)
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` (Impact: 120.2)
  * `_find_balanced_end` (Impact: 111.6)
  * `_partition_embedded_languages` (Impact: 39.6)
    * *Intent:* # deferred to the later per-family comment stripper) so whichever # construct actually starts first ...
  * `_strip_php_string_mass` (Impact: 2.5)
    * *Intent:* # Using re.DOTALL ensures [\s\S] matches newlines correctly. The # triple-quote ones (not stripped s...
  * `capture_lit` (Impact: 2.2)
    * *Intent:* # Using re.DOTALL ensures [\s\S] matches newlines correctly. The # plain-string and comment alternat...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 192`, `structural_boundaries: 94`, `args: 26`, `func_start: 23`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 24`, `state_mutation: 144`, `fragile_debt: 6`
* *Architecture:* `api: 10`, `import: 4`
* *Defense:* `safety: 4`, `doc: 44`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 10.614
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.030978
  * `Imports (Out-Degree: 0):` typing, logging, gitgalaxy.standards.language_standards, re
  * `Imported By (In-Degree: 8):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.091 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.993 IQR)
- **Top Global Matches:** file_cluster_8: 11.091, file_cluster_16: 11.38, file_cluster_7: 11.514
- **Magnitude:** 435.02 | **LOC:** 2043 | **CtrlFlow:** 74.4% | **Authorship Centralization:** 81.8%
- **Risk Profile:** Cognitive Load (27.9566%), Tech Debt (8.1016%)
**Top Internal Functions/Classes:**
  * `_calc_indentation_style` (Impact: 275.9)
  * `_normalize_temporal_metrics` (Impact: 13.7)
  * `_calc_ownership_entropy` (Impact: 9.7)
  * `_calc_raw_temporal_signals` (Impact: 6.4)
  * `__init__` (Impact: 1.2)
    * *Intent:* # ========================================================================== # Dynamically inherited...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 360`, `structural_boundaries: 124`, `args: 39`, `func_start: 31`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 41`, `state_mutation: 88`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 9`, `concurrency: 2`, `import: 8`
* *Defense:* `safety: 54`, `doc: 40`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 7.61
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.024194
  * `Imports (Out-Degree: 0):` gitgalaxy.standards, logging, os, typing, re, math, statistics
  * `Imported By (In-Degree: 6):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 343.14 | **LOC:** 1152 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_tier_2_fingerprint_check` (Impact: 214.1)
    * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents g...
  * `_detect_hybrids` (Impact: 28.8)
  * `_calibrate_lookup_maps` (Impact: 21.8)
  * `_tier_1_metadata_lock` (Impact: 8.6)
  * `inspect` (Impact: 1.4)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, time, gitgalaxy.standards.gitgalaxy_config, typing, pathlib, gitgalaxy.standards.language_standards, re, math...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_abap.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 314.9 | **LOC:** 190 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, _extraction_harness, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 262.76 | **LOC:** 1597 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_signal_processor_doc_and_secrets_by` (Impact: 53.3)
    * *Intent:* # Standard cognitive load should be 0.0, and the file impact forced to 1.0
  * `test_signal_processor_concurrency_thresh` (Impact: 13.5)
  * `create_synthetic_star` (Impact: 13.3)
  * `test_signal_processor_minified_tripwire` (Impact: 7.8)
  * `test_signal_processor_zero_division_shie` (Impact: 5.8)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, os, pytest, gitgalaxy.metrics.signal_processor, tempfile, gitgalaxy.recorders.sarif_recorder, which, identity...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 11.0 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.802 IQR)
- **Top Global Matches:** file_cluster_13: 11.0, file_cluster_8: 11.099, file_cluster_17: 11.114
- **Magnitude:** 260.22 | **LOC:** 442 | **CtrlFlow:** 68.1% | **Authorship Centralization:** 66.7%
- **Risk Profile:** Cognitive Load (17.0768%), Tech Debt (10.5488%)
**Top Internal Functions/Classes:**
  * `_resolve_target` (Impact: 219.8)
  * `_build_resolution_map` (Impact: 9.6)
  * `__init__` (Impact: 5.3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 96`, `structural_boundaries: 45`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 24`, `state_mutation: 16`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 10`
* *Defense:* `safety: 21`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.748
  * `Choke Point (Betweenness):` 1.7e-05 | `Ripple Effect (Closeness):` 0.014337
  * `Imports (Out-Degree: 1):` logging, warnings, gitgalaxy.standards.analysis_lens, collections, token, typing, networkx, networkx.algorithms...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.061 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.417 IQR)
- **Top Global Matches:** file_cluster_8: 11.061, file_cluster_16: 11.232, file_cluster_13: 11.278
- **Magnitude:** 243.32 | **LOC:** 537 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (38.9127%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit` (Impact: 142.8)
  * `_is_dead_code` (Impact: 9.8)
  * `_is_threat` (Impact: 9.5)
    * *Intent:* # Preserve Phase 1 Telemetry for SBOM Traceability "failed_claim": artifact.get("lang_id", "unknown"...
  * `_is_highly_blended` (Impact: 7.6)
  * `_format_for_exclusion` (Impact: 2.8)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 85`, `structural_boundaries: 36`, `args: 8`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 26`, `state_mutation: 60`
* *Architecture:* `io: 2`, `api: 3`, `import: 5`
* *Defense:* `safety: 9`, `doc: 14`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.272
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.011201
  * `Imports (Out-Degree: 0):` logging, os, typing, math, statistics
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 210.74 | **LOC:** 434 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` (Impact: 50.1)
  * `audit_repository` (Impact: 40.1)
  * `__init__` (Impact: 30.2)
  * `_construct_feature_matrix` (Impact: 29.7)
  * `get_nth_degree` (Impact: 10.6)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, gitgalaxy.standards.analysis_lens, collections, xgboost, pandas, typing, networkx, pathlib...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_livecode_strict.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 196.88 | **LOC:** 642 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_livecode_ownership_comment_style_co` (Impact: 42.0)
  * `test_livecode_dependency_capture_extract` (Impact: 16.4)
  * `test_livecode_do_alternative_trailing_bo` (Impact: 10.5)
    * *Intent:* """ pattern = LIVECODE_RULES["io"] assert pattern.search('post "action=" & tAction to url tURL'), "c...
  * `test_livecode_signature_positive_and_neg` (Impact: 10.4)
    * *Intent:* # --- DEEP ADVERSARIAL CASES: structural_boundaries --- ("structural_boundaries", "visual effect", "...
  * `test_livecode_state_mutation_multiword_e` (Impact: 9.3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, pytest, multiprocessing, sys, shapes, pathlib, gitgalaxy.standards.language_standards, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_13
- `gitgalaxy/metrics/chronometer.py` (PYTHON) | Magnitude: 165.68 | Delta: **0.005 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 63, structural_boundaries: 41, state_mutation: 35
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 102.46 | Delta: **0.057 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 128, branch: 29, state_mutation: 27, encapsulation: 23
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 89.84 | Delta: **0.069 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 223, branch: 56, structural_boundaries: 50, state_mutation: 34
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 189.4 | Delta: **0.093 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 54, structural_boundaries: 52, state_mutation: 42
- `gitgalaxy/core/network_risk_sensor.py` (PYTHON) | Magnitude: 260.22 | Delta: **0.099 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 266, branch: 96, structural_boundaries: 45, safety_bypasses: 24

### Mixed-Responsibility Refactoring Targets for: file_cluster_16
- `gitgalaxy/core/prism.py` (PYTHON) | Magnitude: 442.74 | Delta: **0.012 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 562, branch: 192, state_mutation: 144, structural_boundaries: 94
- `gitgalaxy/core/spatial_correlation.py` (PYTHON) | Magnitude: 44.42 | Delta: **0.189 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 133, branch: 32, generics: 27, structural_boundaries: 19

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) | Magnitude: 128.04 | Delta: **0.076 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 269, state_mutation: 97, branch: 41, structural_boundaries: 22
- `gitgalaxy/core/state_rehydrator.py` (PYTHON) | Magnitude: 13.9 | Delta: **0.097 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 54, structural_boundaries: 14, branch: 8, doc: 8
- `gitgalaxy/galaxyscope.py` (PYTHON) | Magnitude: 1441.6 | Delta: **0.131 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 1966, branch: 539, structural_boundaries: 216, state_mutation: 183
- `gitgalaxy/core/guidestar_lens.py` (PYTHON) | Magnitude: 101.7 | Delta: **0.132 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 286, branch: 90, structural_boundaries: 53, encapsulation: 41
- `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) | Magnitude: 243.32 | Delta: **0.171 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 326, branch: 85, state_mutation: 60, structural_boundaries: 36

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 1441.6
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (87.5% isolated ownership) | Magnitude: 753.72
- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (90.5% isolated ownership) | Magnitude: 591.72
- `gitgalaxy/core/prism.py` -> **Joe Esquibel** (92.3% isolated ownership) | Magnitude: 442.74
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (81.8% isolated ownership) | Magnitude: 435.02

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/galaxyscope.py` -> **Severity: 0.085** (Bridge: 0.0011 * Flux: 79.1636%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.017** (Bridge: 0.0003 * Flux: 52.5125%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.011** (Bridge: 0.0001 * Flux: 97.3782%)
- `gitgalaxy/recorders/sbom_recorder.py` -> **Severity: 0.006** (Bridge: 0.0001 * Flux: 96.9481%)
- `gitgalaxy/security/security_auditor.py` -> **Severity: 0.003** (Bridge: 0.0 * Flux: 94.7128%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/core/detector.py` -> **Severity: 3.103** (Embedded: 0.0518 * Error Risk: 59.9217%)
- `gitgalaxy/core/prism.py` -> **Severity: 2.545** (Embedded: 0.031 * Error Risk: 82.165%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 2.438** (Embedded: 0.0416 * Error Risk: 58.6062%)
- `gitgalaxy/standards/gitgalaxy_config.py` -> **Severity: 2.232** (Embedded: 0.0399 * Error Risk: 55.9468%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 1.795** (Embedded: 0.0384 * Error Risk: 46.7319%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/analysis_lens.py` -> **Severity: 410.907** (Blast Radius: 23.98 * Doc Risk: 17.1354%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 370.839** (Blast Radius: 20.74 * Doc Risk: 17.8804%)
- `gitgalaxy/standards/gitgalaxy_config.py` -> **Severity: 291.647** (Blast Radius: 16.311 * Doc Risk: 17.8804%)
- `gitgalaxy/core/detector.py` -> **Severity: 246.918** (Blast Radius: 14.261 * Doc Risk: 17.3142%)
- `scripts/update_golden_masters.sh` -> **Severity: 199.529** (Blast Radius: 2.239 * Doc Risk: 89.1154%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Stay in the Senior Technical Storyteller persona from Section 1. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility) woven into a cohesive narrative -- not a dry, disconnected bullet-point audit. DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective and factual, but write like you're explaining the codebase to a colleague, not filing a verdict.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
