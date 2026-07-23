# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope v6.2.0 (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-07-23T01:35:28.495530+00:00` |
| **Scan Duration** | `5.68s` |
| **Git Branch** | `main` |
| **Git Commit** | `5eff2cab256c2742aa0bb127d73106ebe70b4b43` |
| **Git Remote** | `https://github.com/squid-protocol/gitgalaxy` |
| **Zero-Dependency Mode** | `Inactive (Full Precision)` |

## 0.5 AI THREAT AUDIT STATUS
> **✅ SECURE_NO_THREATS_DETECTED**
> XGBoost Structural Signatures model found no malicious artifacts.

## 1. SYSTEM ROLE & PHILOSOPHY
> You are analyzing software architecture through the lens of GitGalaxy Static Application Security Testing (SAST). GitGalaxy translates the non-visual architecture of repositories into measurable technical metrics.
> 
> **CORE DIRECTIVES:**
> 1. **Measure Risk, Not Quality:** Do not judge. We measure Risk Exposure (e.g., Cognitive Load Exposure). Frame all insights as blameless, objective observations. High risk highlights where the architecture might be drifting into fragile territory, not developer incompetence.
> 2. **The Physical Reality Rule:** Base your analysis strictly on the provided Structural Signatures (regex hit counts). Do not hallucinate meaning.
> 3. **Risk vs. Defense:** Code is a balance. A file with high `flux` (state mutation) is risky unless balanced by `freeze_hits` (immutability). High `danger` is brittle unless wrapped in `safety`.
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
| Total Artifacts | 608 |
| Analyzed Artifacts (Scanned) | 150 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 458 |
| Total LOC | 50039 |
| Volatility Index | 0.007 |
| % Scanned of codebase = | 24.7% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.0 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | 0.0 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 0 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 0 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 117 | 49530 | 78.0% |
| MARKDOWN | 22 | 0 | 14.7% |
| YAML | 8 | 509 | 5.3% |
| PLAINTEXT | 3 | 0 | 2.0% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `6.605`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 115 | 76.7% |
| file_cluster_13 | 8 | 5.3% |
| file_cluster_6 | 1 | 0.7% |
| file_cluster_16 | 1 | 0.7% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 25 | 16.7% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 458*

**Composition by Extension & Reason:**
- `.md`: 331x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 63 LOC), 1x Excluded (Machine-Generated Source Code Signature: 34 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.yml`: 13x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 534 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.json`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 63.4 | 3.2 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 71.8 | 6.5 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 9.9 | 0.1 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 9.8 | 0.0 | 0.0 |
| API Exposure | 0.0 | 5.0 | 0.3 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 22.6 | 0.5 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 9.8 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 9.8 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 20.6 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 28.0 | 1.0 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 10.9 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 100.0 | 7.7 | 0.0 | 0.0 |
| Algorithmic DoS Exposure | 0.0 | 100.0 | 11.6 | 0.0 | 0.0 |
| Obfuscation & Evasion Surface | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Exploit Generation Surface | 0.0 | 100.0 | 14.0 | 0.0 | 0.0 |
| Weaponizable Injection Vectors | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Raw Memory Manipulation | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 14)
- `gitgalaxy/metrics/chronometer.py` (Hits: 9)
- `gitgalaxy/core/guidestar_lens.py` (Hits: 8)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These files act as core load-bearing infrastructure. Changes here carry a high risk of cascading breaks.

1. **CONTRIBUTING.md** (`CONTRIBUTING.md`) — 0 inbound connections
2. **README.md** (`README.md`) — 0 inbound connections
3. **SECURITY.md** (`SECURITY.md`) — 0 inbound connections
4. **README.md** (`gitgalaxy/README.md`) — 0 inbound connections
5. **README.md** (`gitgalaxy/core/README.md`) — 0 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 54 outbound dependencies
2. **test_dependency_extraction_strict.py** (`tests/extraction/test_dependency_extraction_strict.py`) — 23 outbound dependencies
3. **cobol_refractor_controller.py** (`gitgalaxy/cobol_refractor_controller.py`) — 17 outbound dependencies
4. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 16 outbound dependencies
5. **cobol_to_java_controller.py** (`gitgalaxy/cobol_to_java_controller.py`) — 15 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **1292.0** | LOC: 361
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **1250.6** | LOC: 764
- `_resolve_dependency_graph` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **1058.7** | LOC: 683
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> Impact: **785.0** | LOC: 181
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `test_cicd_policy_enforcement_gates` (@ `tests/core_engine/test_galaxyscope.py`) -> Impact: **661.5** | LOC: 1231
  * *Intent:* # ============================================================================== # ===================================================================...
- `_render_splicing_chart` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **656.8** | LOC: 526
- `build_dependency_graph` (@ `gitgalaxy/core/network_risk_sensor.py`) -> Impact: **521.9** | LOC: 217
- `_find_balanced_end` (@ `gitgalaxy/core/prism.py`) -> Impact: **394.2** | LOC: 169
- `build_resolution_map` (@ `gitgalaxy/security/manifest_parser.py`) -> Impact: **377.0** | LOC: 145
  * *Intent:* # Matches standard Python packages, extracting the base name and dropping version constraints (==, >=, ~) # Matches direct URI references (git, file, ...
- `slice_manifest` (@ `gitgalaxy/security/manifest_parser.py`) -> Impact: **327.1** | LOC: 102
  * *Intent:* # NEW: # Filenames UniversalManifestSlicer.slice_manifest() below knows how to parse # into an actual dependency list. This is the single source of tr...

## 8.5 ALGORITHMIC & DATABASE BOTTLENECKS
> Highlights the most computationally expensive and database-heavy functions across the repository.

### Highest Time Complexity (Big-O)
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> **O(2^N) [Recursive]**
- `flatten_copybooks` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> **O(2^N) [Recursive]**
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `simulate_delta_parser` (@ `tests/core_engine/test_delta_scanner.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ A DRY helper method that exactly mirrors the Git Diff parser from galaxyscope.py to test its physical routing logic. """ added, modified, deleted ...
- `parser` (@ `tests/core_engine/test_manifest_parser.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """Provides a fresh ManifestParser instance with a silenced logger for clean test output."""
- `deep_compare` (@ `tests/golden_diff.py`) -> **O(2^N) [Recursive]**
- `close` (@ `gitgalaxy/cobol_refractor_controller.py`) -> **O(2^N) [Recursive]**
- `close` (@ `gitgalaxy/security/dependency_audit_cache.py`) -> **O(2^N) [Recursive]**
- `prism_engine` (@ `tests/core_engine/test_prism.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """Initializes the Prism with a controlled, deterministic regex matrix."""
- `commit` (@ `gitgalaxy/security/dependency_audit_cache.py`) -> **O(2^N) [Recursive]**

### Highest Data Gravity (Database Complexity)
- `test_cicd_policy_enforcement_gates` (@ `tests/core_engine/test_galaxyscope.py`) -> DB Complexity: **77**
  * *Intent:* # ============================================================================== # ===================================================================...
- `generate_build_jcl` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> DB Complexity: **34**
- `generate_rest_controller` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py`) -> DB Complexity: **34**
  * *Intent:* """Generates the API endpoints and auto-wires the Service layer."""
- `publish_insights` (@ `templates/bitbucket/bitbucket_insights.py`) -> DB Complexity: **34**
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **33**
- `_render_splicing_chart` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **32**
- `generate_java_entity` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py`) -> DB Complexity: **31**
- `slice_manifest` (@ `gitgalaxy/security/manifest_parser.py`) -> DB Complexity: **26**
  * *Intent:* # NEW: # Filenames UniversalManifestSlicer.slice_manifest() below knows how to parse # into an actual dependency list. This is the single source of tr...
- `main` (@ `gitgalaxy/tools/network_auditing/full_api_network_map.py`) -> DB Complexity: **26**
- `main` (@ `gitgalaxy/tools/supply_chain_security/supply_chain_firewall.py`) -> DB Complexity: **23**

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `gitgalaxy` | 6 | 4018.5 | 8.9% | 0.0% |
| `gitgalaxy/core` | 8 | 3012.9 | 12.35% | 2.24% |
| `gitgalaxy/metrics` | 5 | 2503.16 | 15.36% | 0.0% |
| `tests/core_engine` | 15 | 2493.6 | 2.23% | 0.0% |
| `gitgalaxy/security` | 5 | 1700.16 | 11.67% | 0.0% |
| `gitgalaxy/recorders` | 8 | 1597.4 | 20.96% | 0.0% |
| `tests/security_auditing` | 16 | 1527.12 | 2.63% | 0.0% |
| `gitgalaxy/standards` | 7 | 993.74 | 7.85% | 5.14% |
| `tests/extraction` | 5 | 745.42 | 3.3% | 0.0% |
| `tests/cobol_mainframe` | 13 | 483.12 | 1.56% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `gitgalaxy/core/network_risk_sensor.py` -> **9.8694%** Exposure
- `gitgalaxy/core/detector.py` -> **8.0425%** Exposure
### Highest State Flux (Mutation/Volatility)
- `gitgalaxy/recorders/llm_recorder.py` -> **100.0%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **99.9879%** Exposure
- `gitgalaxy/core/prism.py` -> **99.67%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **99.4115%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **96.3163%** Exposure

## 10.5 AI THREAT INTELLIGENCE (XGBoost)
*No files met the threshold for malicious structural signatures.*

## 10.6 WEAPONIZABLE SURFACE EXPOSURES (RULE-BASED SAST)
> Secondary Evidence: The following files tripped specific static threat signatures. Use these to explain *why* the XGBoost model flagged the files above.

### Exploit Generation Surface
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **100.0%** Exposure
- `gitgalaxy/core/detector.py` -> **100.0%** Exposure
### Algorithmic DoS Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **100.0%** Exposure
- `gitgalaxy/core/prism.py` -> **100.0%** Exposure

## 10.7 AUTONOMOUS AI VULNERABILITIES (AGENTIC RCE & PROMPT INJECTION)
> **AI CONTEXT:** Identifies untrusted data flowing into LLM context windows (Prompt Injection) and LLM outputs flowing into dynamic execution (Agentic RCE).

*No autonomous AI vulnerabilities detected.*

## 10.8 ECOSYSTEM SECURITY AUDITS
> **AI CONTEXT:** High-level perimeter defense metrics from the X-Ray, Supply Chain Firewall, and API Network Mapper.

### ☢️ X-Ray & 🧱 Supply Chain Firewall
- **Binary Anomalies (X-Ray):** `0` (High entropy, packed payloads, or magic byte mismatches).
- **Blacklisted Dependencies:** `0` explicitly banned packages imported.
- **Unknown Dependencies:** `694` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/spatial_mapper.py` (PYTHON) -> Cumulative Risk: **717.23**
- **Archetype:** `file_cluster_8` (Distance: 10.526 IQR)
- **Magnitude:** 277.4 | **LOC:** 233 | **CtrlFlow:** 64.2% | **Authorship Centralization:** 57.1%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `map_repository` (Impact: 203.4), `__init__` (Impact: 15.0), `_hash_jitter` (Impact: 8.4)

### 2. `gitgalaxy/metrics/chronometer.py` (PYTHON) -> Cumulative Risk: **696.66**
- **Archetype:** `file_cluster_8` (Distance: 10.463 IQR)
- **Magnitude:** 344.62 | **LOC:** 432 | **CtrlFlow:** 64.3% | **Authorship Centralization:** 60.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `_determine_commit_bounds` (Impact: 118.5), `_load_ignored_revs` (Impact: 49.4), `_initialize_history_scan` (Impact: 43.7)

### 3. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **678.89**
- **Archetype:** `file_cluster_8` (Distance: 10.214 IQR)
- **Magnitude:** 1448.56 | **LOC:** 536 | **CtrlFlow:** 72.2% | **Authorship Centralization:** 57.1%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (94.7624%)
- **Heaviest Functions:** `audit` (Impact: 1292.0), `_is_threat` (Impact: 30.9), `_is_dead_code` (Impact: 26.1)

### 4. `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) -> Cumulative Risk: **675.02**
- **Archetype:** `file_cluster_8` (Distance: 9.704 IQR)
- **Magnitude:** 318.72 | **LOC:** 360 | **CtrlFlow:** 51.7% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (93.846%)
- **Heaviest Functions:** `_audit_with_cache` (Impact: 160.8), `_audit_capped_sample` (Impact: 48.4), `_iter_candidate_files` (Impact: 32.0)

### 5. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **667.26**
- **Archetype:** `file_cluster_8` (Distance: 11.542 IQR)
- **Magnitude:** 3259.28 | **LOC:** 2771 | **CtrlFlow:** 70.9% | **Authorship Centralization:** 52.9%
- **Primary Risk Drivers:** Spec Match (100.0%), Churn (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `execute_pipeline` (Impact: 1250.6), `_resolve_dependency_graph` (Impact: 1058.7), `_render_splicing_chart` (Impact: 656.8)

### 6. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **666.2**
- **Archetype:** `file_cluster_8` (Distance: 10.86 IQR)
- **Magnitude:** 1051.82 | **LOC:** 628 | **CtrlFlow:** 63.3% | **Authorship Centralization:** 66.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.67%)
- **Heaviest Functions:** `_find_balanced_end` (Impact: 394.2), `_compile_regex_matrix` (Impact: 192.5), `split_streams` (Impact: 137.1)

### 7. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **657.0**
- **Archetype:** `file_cluster_8` (Distance: 10.24 IQR)
- **Magnitude:** 403.88 | **LOC:** 434 | **CtrlFlow:** 52.9% | **Authorship Centralization:** 55.6%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (96.3163%)
- **Heaviest Functions:** `main` (Impact: 129.7), `process_payload` (Impact: 80.2), `record_dead_code` (Impact: 41.2)

### 8. `gitgalaxy/core/network_risk_sensor.py` (PYTHON) -> Cumulative Risk: **642.47**
- **Archetype:** `file_cluster_8` (Distance: 9.962 IQR)
- **Magnitude:** 697.24 | **LOC:** 446 | **CtrlFlow:** 72.3% | **Authorship Centralization:** 71.4%
- **Primary Risk Drivers:** Spec Match (100.0%), Logic Bomb (99.9997%), Algorithmic Dos (99.9996%), Verification (80.0%)
- **Heaviest Functions:** `build_dependency_graph` (Impact: 521.9), `_fallback_build_graph` (Impact: 111.0), `_build_resolution_map` (Impact: 25.9)

### 9. `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` (PYTHON) -> Cumulative Risk: **637.03**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.34 | **LOC:** 214 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `flatten_copybooks` (Impact: 184.3), `generate_build_jcl` (Impact: 34.5), `main` (Impact: 23.0)

### 10. `gitgalaxy/recorders/sarif_recorder.py` (PYTHON) -> Cumulative Risk: **632.46**
- **Archetype:** `file_cluster_8` (Distance: 8.933 IQR)
- **Magnitude:** 147.5 | **LOC:** 218 | **CtrlFlow:** 70.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (99.9842%), Logic Bomb (99.9788%), State Flux (84.6591%)
- **Heaviest Functions:** `_build_rules_taxonomy` (Impact: 62.7), `_build_dependency_notifications` (Impact: 34.3), `_build_location` (Impact: 12.8)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.542 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.473 IQR)
- **Top Global Matches:** file_cluster_8: 11.542, file_cluster_13: 11.768, file_cluster_7: 11.999
- **Magnitude:** 3259.28 | **LOC:** 2771 | **CtrlFlow:** 70.9% | **Authorship Centralization:** 52.9%
- **Algorithmic:** O(N^6) | **DB Complexity:** 33
- **Risk Profile:** Cognitive Load (21.3728%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `execute_pipeline` (Impact: 1250.6 | O(N^6) | DB: 33)
  * `_resolve_dependency_graph` (Impact: 1058.7 | O(N^6) | DB: 22)
  * `_render_splicing_chart` (Impact: 656.8 | O(N^6) | DB: 32)
  * `_render_file_speed_chart` (Impact: 18.6 | O(N^3))
    * *Intent:* """ if self.temp_dir and Path(self.temp_dir).exists(): try: shutil.rmtree(self.temp_dir) except Exce...
  * `__init__` (Impact: 1.8 | O(N^2))
    * *Intent:* # ============================================================================== # GitGalaxy Phase 3...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 592`, `structural_boundaries: 243`, `args: 29`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 78`, `state_mutation: 218`
* *Architecture:* `io: 14`, `api: 6`, `concurrency: 4`, `import: 65`
* *Defense:* `safety: 69`, `doc: 36`, `test: 2`, `sync_locks: 1`, `immutability_locks: 1`, `cleanup: 6`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.metrics.signal_processor, gitgalaxy.recorders.sarif_recorder, datetime, gitgalaxy.recorders.sbom_recorder, gitgalaxy.security.security_auditor, gitgalaxy.tools.ai_guardrails.ai_appsec_sensor, gitgalaxy.tools.supply_chain_security.supply_chain_firewall, copy...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.214 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.137 IQR)
- **Top Global Matches:** file_cluster_8: 10.214, file_cluster_16: 10.535, file_cluster_13: 10.641
- **Magnitude:** 1448.56 | **LOC:** 536 | **CtrlFlow:** 72.2% | **Authorship Centralization:** 57.1%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 22
- **Risk Profile:** Cognitive Load (34.1149%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit` (Impact: 1292.0 | O(2^N) | DB: 22)
  * `_is_threat` (Impact: 30.9 | O(N^4))
    * *Intent:* # Preserve Phase 1 Telemetry for SBOM Traceability "failed_claim": artifact.get("lang_id", "unknown"...
  * `_is_dead_code` (Impact: 26.1 | O(N^4))
  * `_is_highly_blended` (Impact: 20.7 | O(N^4))
  * `_format_for_exclusion` (Impact: 9.7 | O(N^3))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 109`, `structural_boundaries: 42`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 26`, `state_mutation: 56`
* *Architecture:* `io: 2`, `api: 3`, `import: 5`
* *Defense:* `safety: 10`, `doc: 14`, `sync_locks: 4`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, os, logging, statistics, math
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.86 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.932 IQR)
- **Top Global Matches:** file_cluster_8: 10.86, file_cluster_16: 10.939, file_cluster_7: 11.195
- **Magnitude:** 1051.82 | **LOC:** 628 | **CtrlFlow:** 63.3% | **Authorship Centralization:** 66.7%
- **Algorithmic:** O(N^6) | **DB Complexity:** 11
- **Risk Profile:** Cognitive Load (22.0154%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_find_balanced_end` (Impact: 394.2 | O(N^6) | DB: 11)
  * `_compile_regex_matrix` (Impact: 192.5 | O(N^6) | DB: 1)
    * *Intent:* # 4. GENERIC STRIPPER pattern = self.REGEX_MATRIX.get(family) if not pattern: # Restore mask tokens ...
  * `split_streams` (Impact: 137.1 | O(N^5) | DB: 3)
    * *Intent:* # Phase 6.1 Handshake Registry (Synchronized securely via Language Standards) for trigger_config in ...
  * `_partition_embedded_languages` (Impact: 136.6 | O(N^6) | DB: 4)
  * `_strip_segment_comments` (Impact: 64.4 | O(N^4) | DB: 7)
    * *Intent:* # 3. Derive the documentation lines by subtracting code from the active total. # This forces mutual ...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 131`, `structural_boundaries: 76`, `args: 23`, `func_start: 19`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 96`
* *Architecture:* `api: 12`, `import: 4`
* *Defense:* `safety: 5`, `doc: 32`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, gitgalaxy.standards.language_standards, re, logging
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 1008.12 | **LOC:** 391 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `build_resolution_map` (Impact: 377.0 | O(N^6) | DB: 12)
    * *Intent:* # Matches standard Python packages, extracting the base name and dropping version constraints (==, >...
  * `slice_manifest` (Impact: 327.1 | O(N^6) | DB: 26)
    * *Intent:* # NEW: # Filenames UniversalManifestSlicer.slice_manifest() below knows how to parse # into an actua...
  * `locate_physical_package` (Impact: 253.8 | O(N^6) | DB: 6)
    * *Intent:* # Extract artifactId and version from XML blocks deps_raw = re.findall( r"<dependency>.*?<artifactId...
  * `__init__` (Impact: 14.4 | O(N^3) | DB: 3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, os, logging, json, pathlib, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.614 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.003 IQR)
- **Top Global Matches:** file_cluster_8: 11.614, file_cluster_13: 11.959, file_cluster_16: 12.013
- **Magnitude:** 795.44 | **LOC:** 1504 | **CtrlFlow:** 87.7% | **Authorship Centralization:** 66.7%
- **Algorithmic:** O(N^3) | **DB Complexity:** 4
- **Risk Profile:** Cognitive Load (63.3513%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 11.0 | O(N^3) | DB: 4)
  * `_parse_threat_score` (Impact: 7.3 | O(N^3))
  * `generate_artifacts` (Impact: 1.9 | O(N^2))
  * `_build_markdown` (Impact: 1.9 | O(N^2))
  * `_generate_sqlite_graph` (Impact: 1.9 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 327`, `structural_boundaries: 46`, `args: 31`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 731`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 14`, `doc: 26`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, sqlite3, collections, gitgalaxy.standards, logging, pathlib, json, statistics...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 739.1 | **LOC:** 1397 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_cicd_policy_enforcement_gates` (Impact: 661.5 | O(N^5) | DB: 77)
    * *Intent:* # ============================================================================== # =================...
  * `setUp` (Impact: 4.2 | O(N^3) | DB: 1)
    * *Intent:* """Creates a dummy configuration for the Orchestrator."""
  * `test_phantom_file_race_condition` (Impact: 3.5 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` failure, concurrent.futures, os, tempfile, unittest.mock, passes, logging, pathlib...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.962 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.154 IQR)
- **Top Global Matches:** file_cluster_8: 9.962, file_cluster_13: 10.231, file_cluster_16: 10.303
- **Magnitude:** 697.24 | **LOC:** 446 | **CtrlFlow:** 72.3% | **Authorship Centralization:** 71.4%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (18.2396%), Tech Debt (9.8694%)
**Top Internal Functions/Classes:**
  * `build_dependency_graph` (Impact: 521.9 | O(N^6) | DB: 1)
  * `_fallback_build_graph` (Impact: 111.0 | O(N^5))
  * `_build_resolution_map` (Impact: 25.9 | O(N^4) | DB: 3)
  * `__init__` (Impact: 7.9 | O(N^2) | DB: 2)
  * `_resolve_target` (Impact: 1.6 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 125`, `structural_boundaries: 48`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 29`, `state_mutation: 17`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 5`, `import: 10`
* *Defense:* `safety: 21`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, collections, networkx, logging, pathlib, gitgalaxy.standards.analysis_lens, networkx.algorithms, token...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.806 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.593 IQR)
- **Top Global Matches:** file_cluster_8: 9.806, file_cluster_13: 10.14, file_cluster_7: 10.19
- **Magnitude:** 653.72 | **LOC:** 504 | **CtrlFlow:** 64.6% | **Authorship Centralization:** 66.7%
- **Algorithmic:** O(N^6) | **DB Complexity:** 16
- **Risk Profile:** Cognitive Load (9.173%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_scan_package_manifests` (Impact: 307.3 | O(N^6) | DB: 16)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `get_intent_status` (Impact: 97.8 | O(N^5))
  * `_calculate_documentation_coverage` (Impact: 87.3 | O(N^6) | DB: 3)
    * *Intent:* # galaxyscope:ignore sec_io, llm_hooks # DOCUMENTATION COVERAGE MAP # ==============================...
  * `_scan_gitignore_evasion` (Impact: 56.7 | O(N^6) | DB: 3)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `_inject_intent_lock` (Impact: 35.5 | O(N^3))
**Contextual Mitigations & Amplifications:**
* *Sec Io:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 104`, `structural_boundaries: 57`, `args: 15`, `func_start: 15`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 17`, `state_mutation: 15`
* *Architecture:* `io: 8`, `api: 6`, `import: 8`
* *Defense:* `safety: 17`, `doc: 32`, `sync_locks: 4`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, os, logging, json, pathlib, fnmatch, re, gitgalaxy.standards.gitgalaxy_config
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 589.2 | **LOC:** 412 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit_repository` (Impact: 173.2 | O(N^6))
  * `_resolve_dependency_graph` (Impact: 168.8 | O(N^6) | DB: 3)
  * `__init__` (Impact: 100.2 | O(N^6) | DB: 8)
  * `_construct_feature_matrix` (Impact: 96.4 | O(N^6) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` collections, numpy, xgboost, networkx, logging, pathlib, gitgalaxy.standards.analysis_lens, pandas
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.919 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.713 IQR)
- **Top Global Matches:** file_cluster_8: 8.919, file_cluster_16: 9.389, file_cluster_7: 9.5
- **Magnitude:** 526.28 | **LOC:** 2498 | **CtrlFlow:** 76.1% | **Authorship Centralization:** 53.8%
- **Algorithmic:** O(N^6) | **DB Complexity:** 1
- **Risk Profile:** Cognitive Load (16.0887%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_rank_list` (Impact: 75.5 | O(N^5))
  * `_get_context_multipliers` (Impact: 57.0 | O(N^4) | DB: 1)
  * `_get_locational_multipliers` (Impact: 43.5 | O(N^5))
    * *Intent:* # 4. Generate rankings using ONLY the masked `active_files` list report = { "exposures": {}, "file_i...
  * `_generate_function_rankings` (Impact: 42.9 | O(N^6) | DB: 1)
  * `get_cumulative_risk` (Impact: 26.4 | O(N^4))
    * *Intent:* # -------------------------------------------------------------------------- # REPORTING UTILITIES #...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 488`, `structural_boundaries: 153`, `args: 44`, `func_start: 36`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 40`, `high_risk_execution: 3`, `state_mutation: 101`
* *Architecture:* `io: 1`, `api: 9`, `concurrency: 2`, `import: 8`
* *Defense:* `safety: 76`, `doc: 50`, `sync_locks: 1`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, os, gitgalaxy.standards, logging, statistics, re, math
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_standards.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 495.46 | **LOC:** 10500 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` keyword., java.util., path, re, inside, type
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 441.52 | **LOC:** 1673 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_detector_regex_execution_catch_bloc` (Impact: 54.5 | O(N^3))
  * `test_spatial_mapper_sectorization_and_mo` (Impact: 27.2 | O(N^2))
    * *Intent:* # SPATIAL MAPPER: 3D SPATIAL GEOMETRY & MAPPING # ==================================================...
  * `test_detector_terminator_cleaving` (Impact: 18.8 | O(N^3))
  * `test_detector_catastrophic_fallbacks` (Impact: 15.7 | O(N^3))
    * *Intent:* """ opt_detector = StructuralExtractor("c", MOCK_LANG_DEFS) code = ( "void vulnerable_rce() { system...
  * `test_detector_global_dust_and_unterminat` (Impact: 14.7 | O(N^2) | DB: 2)
    * *Intent:* # ============================================================================== # TEST 25: MULTI-LI...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` with, unittest.mock, logging, re, gitgalaxy.core.spatial_mapper, pytest, math, gitgalaxy.core.detector
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.24 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.904 IQR)
- **Top Global Matches:** file_cluster_8: 10.24, file_cluster_13: 10.272, file_cluster_7: 10.7
- **Magnitude:** 403.88 | **LOC:** 434 | **CtrlFlow:** 52.9% | **Authorship Centralization:** 55.6%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 13
- **Risk Profile:** Cognitive Load (18.7079%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 129.7 | O(N^4) | DB: 13)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `process_payload` (Impact: 80.2 | O(N^4))
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `record_dead_code` (Impact: 41.2 | O(N^5) | DB: 2)
  * `get_dead_paras` (Impact: 22.2 | O(N^4) | DB: 2)
  * `get_orphaned_vars` (Impact: 22.2 | O(N^4) | DB: 2)
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 63`, `structural_boundaries: 56`, `args: 10`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 5`, `state_mutation: 48`
* *Architecture:* `io: 4`, `api: 9`, `import: 18`
* *Defense:* `safety: 4`, `doc: 10`, `cleanup: 3`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.tools.cobol_to_cobol.cobol_microservice_slicer, typing, sqlite3, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge, argparse, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor, json, pathlib...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 358.96 | **LOC:** 1609 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_signal_processor_minified_tripwire` (Impact: 90.0 | O(N^3) | DB: 4)
  * `test_sarif_exact_loc_injection` (Impact: 19.4 | O(N^4) | DB: 10)
  * `test_signal_processor_report_fallback` (Impact: 15.6 | O(N^3))
  * `test_signal_processor_sigmoid_overflow` (Impact: 12.2 | O(N^2))
    * *Intent:* # ============================================================================== # =================...
  * `test_signal_processor_math_overflow_shie` (Impact: 11.3 | O(N^3))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.metrics.signal_processor, os, tempfile, gitgalaxy.recorders.sarif_recorder, json, pytest
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.463 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.523 IQR)
- **Top Global Matches:** file_cluster_8: 10.463, file_cluster_13: 10.629, file_cluster_16: 10.846
- **Magnitude:** 344.62 | **LOC:** 432 | **CtrlFlow:** 64.3% | **Authorship Centralization:** 60.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 13
- **Risk Profile:** Cognitive Load (14.1444%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_determine_commit_bounds` (Impact: 118.5 | O(N^6) | DB: 13)
  * `_load_ignored_revs` (Impact: 49.4 | O(N^6) | DB: 3)
  * `_initialize_history_scan` (Impact: 43.7 | O(N^5) | DB: 2)
  * `_scan_git_history` (Impact: 33.6 | O(N^4))
  * `_survey_filesystem_mtimes` (Impact: 21.3 | O(N^5) | DB: 6)
    * *Intent:* # ================================================================== # DEFENSIVE ARCHITECTURE: Zombi...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 72`, `structural_boundaries: 40`, `args: 8`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `high_risk_execution: 2`, `state_mutation: 34`
* *Architecture:* `io: 9`, `api: 4`, `import: 7`
* *Defense:* `safety: 20`, `doc: 18`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, os, gitgalaxy.standards, time, logging, pathlib, subprocess
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_to_java_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.186 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.092 IQR)
- **Top Global Matches:** file_cluster_8: 8.186, file_cluster_13: 8.808, file_cluster_7: 8.864
- **Magnitude:** 335.86 | **LOC:** 336 | **CtrlFlow:** 57.8% | **Authorship Centralization:** 60.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 6
- **Risk Profile:** Cognitive Load (8.2911%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 301.7 | O(N^6) | DB: 6)
    * *Intent:* /** * This module intercepts unresolved COBOL calls to '{subroutine_name}'. * It allows the Spring C...
  * `build_spring_boot_scaffold` (Impact: 11.6 | O(N^3))
    * *Intent:* """Creates the standard Spring Boot directory architecture."""
  * `format_java_header` (Impact: 9.6 | O(N^2))
  * `generate_mock_service` (Impact: 3.7 | O(N^1))
**Contextual Mitigations & Amplifications:**
* *Sec Io:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 59`, `structural_boundaries: 43`, `args: 4`, `func_start: 4`
* *Risk/State:* `safety_bypasses: 3`
* *Architecture:* `io: 3`, `api: 4`, `import: 12`
* *Defense:* `safety: 6`, `doc: 8`, `test: 3`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` org.slf4j.Logger, gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge, gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge, org.slf4j.LoggerFactory, argparse, shutil, gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge, gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.704 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.195 IQR)
- **Top Global Matches:** file_cluster_8: 9.704, file_cluster_13: 9.816, file_cluster_7: 10.166
- **Magnitude:** 318.72 | **LOC:** 360 | **CtrlFlow:** 51.7% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 5
- **Risk Profile:** Cognitive Load (17.7048%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_audit_with_cache` (Impact: 160.8 | O(N^6) | DB: 2)
  * `_audit_capped_sample` (Impact: 48.4 | O(N^5) | DB: 4)
  * `_iter_candidate_files` (Impact: 32.0 | O(N^5) | DB: 4)
    * *Intent:* # Filenames that typically execute on import/install — the highest-value # audit targets, since real...
  * `_scan_single_file` (Impact: 29.2 | O(N^4) | DB: 5)
  * `generate_report` (Impact: 1.9 | O(N^2))
    * *Intent:* # Max cache-MISS files freshly scanned per package per run (None = # unlimited). Hashing always cove...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 61`, `structural_boundaries: 57`, `args: 7`, `func_start: 7`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `state_mutation: 36`
* *Architecture:* `io: 5`, `api: 3`, `import: 12`
* *Defense:* `safety: 4`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, uuid, os, gitgalaxy.standards.language_lens, logging, json, datetime, pathlib...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.179 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.046 IQR)
- **Top Global Matches:** file_cluster_8: 9.179, file_cluster_16: 9.652, file_cluster_7: 9.689
- **Magnitude:** 292.04 | **LOC:** 2300 | **CtrlFlow:** 74.5% | **Authorship Centralization:** 60.0%
- **Algorithmic:** O(N^4) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (22.7455%), Tech Debt (8.0425%)
**Top Internal Functions/Classes:**
  * `_classify_function` (Impact: 124.5 | O(N^4))
  * `get_token_mass` (Impact: 8.7 | O(N^2))
    * *Intent:* """Calculates context window footprint. Returns None if tiktoken is missing to prevent dataset poiso...
  * `get_mode` (Impact: 8.3 | O(N^2))
  * `get_config` (Impact: 7.3 | O(N^3))
  * `splice` (Impact: 1.9 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 473`, `structural_boundaries: 162`, `args: 22`, `func_start: 20`, `class_start: 4`
* *Risk/State:* `safety_bypasses: 45`, `state_mutation: 94`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `api: 13`, `concurrency: 1`, `import: 10`
* *Defense:* `safety: 40`, `doc: 63`, `test: 2`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, collections, time, logging, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, re, bisect...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/spatial_mapper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.526 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.868 IQR)
- **Top Global Matches:** file_cluster_8: 10.526, file_cluster_13: 10.571, file_cluster_16: 10.669
- **Magnitude:** 277.4 | **LOC:** 233 | **CtrlFlow:** 64.2% | **Authorship Centralization:** 57.1%
- **Algorithmic:** O(N^6) | **DB Complexity:** 9
- **Risk Profile:** Cognitive Load (17.1826%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `map_repository` (Impact: 203.4 | O(N^6) | DB: 7)
  * `__init__` (Impact: 15.0 | O(N^3) | DB: 9)
  * `_hash_jitter` (Impact: 8.4 | O(N^3))
  * `_get_magnitude` (Impact: 8.3 | O(N^3))
  * `_calculate_spatial_clearance` (Impact: 2.9 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 34`, `structural_boundaries: 19`, `args: 6`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 8`, `state_mutation: 32`, `dead_code: 1`
* *Architecture:* `api: 4`, `import: 4`
* *Defense:* `safety: 1`, `doc: 10`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.667
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` hashlib, typing, math, logging
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/security_auditing/test_supply_chain_firewall.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 273.46 | **LOC:** 609 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_directory_execution_and_globbing` (Impact: 19.9 | O(N^5))
  * `test_strict_mode_enforcement` (Impact: 19.8 | O(N^6))
    * *Intent:* # ============================================================================== # TEST 4: Strict Po...
  * `test_behavioral_threat_evaluation` (Impact: 19.8 | O(N^6))
  * `test_directory_group_schema_parsing` (Impact: 19.8 | O(N^5))
  * `test_tuple_import_handling` (Impact: 19.7 | O(N^6))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` bypassed, gitgalaxy.metrics.signal_processor, policy, unittest.mock, json, pathlib, was, gitgalaxy.tools.supply_chain_security.supply_chain_firewall...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 269.48 | **LOC:** 1115 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_tier_2_fingerprint_check` (Impact: 92.3 | O(N^6) | DB: 1)
    * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents g...
  * `_calibrate_lookup_maps` (Impact: 79.9 | O(N^6))
  * `_tier_1_metadata_lock` (Impact: 16.6 | O(N^3))
  * `inspect` (Impact: 1.9 | O(N^2))
  * `__init__` (Impact: 1.8 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, time, logging, pathlib, gitgalaxy.standards.language_standards, re, gitgalaxy.standards.gitgalaxy_config, math
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/test_function_extraction_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 214.6 | **LOC:** 549 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_positive_function_extraction` (Impact: 79.6 | O(N^5))
    * *Intent:* """ Proves that valid function signatures are caught, and the regex isolates EXACTLY the function na...
  * `test_pathological_function_extraction` (Impact: 74.2 | O(N^5))
  * `test_negative_function_extraction` (Impact: 35.4 | O(N^4))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/test_dependency_extraction_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 204.68 | **LOC:** 463 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_positive_dependency_extraction` (Impact: 84.7 | O(N^5))
    * *Intent:* """ Proves that valid import signatures are caught, and the regex isolates EXACTLY the module/file p...
  * `test_pathological_dependency_extraction` (Impact: 68.9 | O(N^5))
  * `test_negative_dependency_extraction` (Impact: 35.4 | O(N^4))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` mypack.myclass, type, qualified, fmt, cats.effect.IO, numpy, static, gitgalaxy.engine...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/test_class_extraction_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 200.88 | **LOC:** 371 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_positive_class_extraction` (Impact: 79.4 | O(N^5))
    * *Intent:* """ Proves that valid class/entity signatures are caught, and the regex isolates EXACTLY the entity ...
  * `test_pathological_class_extraction` (Impact: 74.2 | O(N^5))
  * `test_negative_class_extraction` (Impact: 35.4 | O(N^4))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/analysis_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 180.6 | **LOC:** 8360 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `get_policy` (Impact: 3.1 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 403.88 | Delta: **0.032 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 287, branch: 63, structural_boundaries: 56, state_mutation: 48
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 277.4 | Delta: **0.045 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 153, branch: 34, state_mutation: 32, encapsulation: 23
- `gitgalaxy/core/prism.py` (PYTHON) | Magnitude: 1051.82 | Delta: **0.079 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 450, branch: 131, state_mutation: 96, structural_boundaries: 76
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 318.72 | Delta: **0.112 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 257, branch: 61, structural_boundaries: 57, state_mutation: 36
- `gitgalaxy/metrics/chronometer.py` (PYTHON) | Magnitude: 344.62 | Delta: **0.166 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 300, branch: 72, structural_boundaries: 40, state_mutation: 34

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **70.17%** | Cog Load: 63.3513% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/recorders/sbom_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 318.72
- `gitgalaxy/recorders/sarif_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 147.5

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/core/spatial_mapper.py` -> **Severity: 666.7** (Blast Radius: 6.667 * Doc Risk: 100.0%)
- `gitgalaxy/metrics/chronometer.py` -> **Severity: 666.7** (Blast Radius: 6.667 * Doc Risk: 100.0%)
- `gitgalaxy/metrics/tensor_scanner.py` -> **Severity: 666.7** (Blast Radius: 6.667 * Doc Risk: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` -> **Severity: 666.7** (Blast Radius: 6.667 * Doc Risk: 100.0%)
- `gitgalaxy/tools/network_auditing/full_api_network_map.py` -> **Severity: 661.731** (Blast Radius: 6.667 * Doc Risk: 99.2547%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Act as a Principal Staff Engineer. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility). DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective, practical, and direct.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
