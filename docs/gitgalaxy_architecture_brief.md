# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope v6.2.0 (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-07-12T02:36:33.768401+00:00` |
| **Scan Duration** | `3.91s` |
| **Git Branch** | `main` |
| **Git Commit** | `6de7f788d16346c9f6382b28c8900c5cf5d55cec` |
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
| Total Artifacts | 605 |
| Analyzed Artifacts (Scanned) | 86 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 519 |
| Total LOC | 35547 |
| Volatility Index | 0.012 |
| % Scanned of codebase = | 14.2% |
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
| PYTHON | 58 | 35302 | 67.4% |
| MARKDOWN | 18 | 0 | 20.9% |
| YAML | 7 | 245 | 8.1% |
| PLAINTEXT | 3 | 0 | 3.5% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `5.826`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 59 | 68.6% |
| file_cluster_13 | 4 | 4.7% |
| file_cluster_6 | 1 | 1.2% |
| file_cluster_16 | 1 | 1.2% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 21 | 24.4% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 519*

**Composition by Extension & Reason:**
- `.md`: 337x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 63 LOC)
- `.py`: 58x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 329 LOC), 1x Excluded (Machine-Generated Source Code Signature: 505 LOC)
- `.png`: 58x Excluded (Explicitly Denied Extension: '.png')
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.yml`: 15x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.json`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 63.4 | 13.6 | 8.8 | 0.0 |
| Error & Exception Exposure | 0.0 | 78.3 | 18.9 | 5.2 | 0.0 |
| Tech Debt Exposure | 0.0 | 100.0 | 5.7 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 15.4 | 0.0 | 0.0 |
| API Exposure | 0.0 | 6.4 | 1.5 | 0.8 | 0.0 |
| Concurrency Exposure | 0.0 | 22.8 | 0.6 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 30.7 | 4.3 | 0.0 |
| Commented Logic Exposure | 0.0 | 18.6 | 0.6 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 70.1 | 100.0 | 100.0 |
| Instability Exposure | 0.0 | 20.9 | 4.9 | 0.2 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 31.5 | 36.8 | 0.0 |
| Documentation Exposure | 0.0 | 100.0 | 25.2 | 17.2 | 0.0 |
| Algorithmic DoS Exposure | 0.0 | 100.0 | 43.3 | 8.0 | 0.0 |
| Obfuscation & Evasion Surface | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Exploit Generation Surface | 0.0 | 100.0 | 42.7 | 0.0 | 0.0 |
| Weaponizable Injection Vectors | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Raw Memory Manipulation | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/standards/language_standards.py` (Hits: 37)
- `gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py` (Hits: 14)
- `gitgalaxy/galaxyscope.py` (Hits: 13)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These files act as core load-bearing infrastructure. Changes here carry a high risk of cascading breaks.

1. **CONTRIBUTING.md** (`CONTRIBUTING.md`) — 0 inbound connections
2. **README.md** (`README.md`) — 0 inbound connections
3. **SECURITY.md** (`SECURITY.md`) — 0 inbound connections
4. **cd pipeline strategy.md** (`cd pipeline strategy.md`) — 0 inbound connections
5. **README.md** (`gitgalaxy/README.md`) — 0 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 53 outbound dependencies
2. **cobol_refractor_controller.py** (`gitgalaxy/cobol_refractor_controller.py`) — 16 outbound dependencies
3. **sbom_recorder.py** (`gitgalaxy/recorders/sbom_recorder.py`) — 13 outbound dependencies
4. **vault_sentinel.py** (`gitgalaxy/tools/supply_chain_security/vault_sentinel.py`) — 13 outbound dependencies
5. **cobol_to_java_test_forge.py** (`gitgalaxy/tools/cobol_to_java/cobol_to_java_test_forge.py`) — 12 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **1292.0** | LOC: 361
- `_resolve_dependency_graph` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **1027.8** | LOC: 673
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **936.2** | LOC: 659
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> Impact: **785.0** | LOC: 181
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `extract_test_coverage_mapping` (@ `gitgalaxy/core/network_risk_sensor.py`) -> Impact: **679.2** | LOC: 285
- `_render_splicing_chart` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **594.0** | LOC: 483
- `_find_balanced_end` (@ `gitgalaxy/core/prism.py`) -> Impact: **394.2** | LOC: 169
- `slice_manifest` (@ `gitgalaxy/recorders/sbom_recorder.py`) -> Impact: **326.8** | LOC: 96
- `_scan_package_manifests` (@ `gitgalaxy/core/guidestar_lens.py`) -> Impact: **306.9** | LOC: 198
  * *Intent:* # ============================================================================== # DEEP MANIFEST INSPECTION # ========================================...
- `main` (@ `gitgalaxy/tools/network_auditing/full_api_network_map.py`) -> Impact: **220.5** | LOC: 149

## 8.5 ALGORITHMIC & DATABASE BOTTLENECKS
> Highlights the most computationally expensive and database-heavy functions across the repository.

### Highest Time Complexity (Big-O)
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> **O(2^N) [Recursive]**
- `flatten_copybooks` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> **O(2^N) [Recursive]**
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `close` (@ `gitgalaxy/cobol_refractor_controller.py`) -> **O(2^N) [Recursive]**
- `extract_test_coverage_mapping` (@ `gitgalaxy/core/network_risk_sensor.py`) -> **O(N^6)**
- `_fallback_build_graph` (@ `gitgalaxy/core/network_risk_sensor.py`) -> **O(N^6)**
  * *Intent:* # E. Articulation Points (Fragmentation Risk) try: macro_metrics["articulation_points"] = len(list(nx.articulation_points(U))) except Exception: pass ...
- `_scan_package_manifests` (@ `gitgalaxy/core/guidestar_lens.py`) -> **O(N^6)**
  * *Intent:* # ============================================================================== # DEEP MANIFEST INSPECTION # ========================================...
- `_calculate_documentation_coverage` (@ `gitgalaxy/core/guidestar_lens.py`) -> **O(N^6)**
- `_scan_gitignore_evasion` (@ `gitgalaxy/core/guidestar_lens.py`) -> **O(N^6)**
  * *Intent:* # ============================================================================== # SECURITY EVASION DETECTION def _scan_gitignore_evasion(self): """ S...
- `map_repository` (@ `gitgalaxy/core/spatial_mapper.py`) -> **O(N^6)**

### Highest Data Gravity (Database Complexity)
- `generate_build_jcl` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> DB Complexity: **34**
- `generate_rest_controller` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py`) -> DB Complexity: **34**
  * *Intent:* """Generates the API endpoints and auto-wires the Service layer."""
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **33**
- `_render_splicing_chart` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **32**
- `generate_java_entity` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py`) -> DB Complexity: **31**
- `slice_manifest` (@ `gitgalaxy/recorders/sbom_recorder.py`) -> DB Complexity: **26**
- `main` (@ `gitgalaxy/tools/network_auditing/full_api_network_map.py`) -> DB Complexity: **26**
- `main` (@ `gitgalaxy/tools/supply_chain_security/supply_chain_firewall.py`) -> DB Complexity: **23**
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> DB Complexity: **22**
- `_resolve_dependency_graph` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **21**

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `gitgalaxy` | 5 | 3247.76 | 8.95% | 2.3% |
| `gitgalaxy/core` | 8 | 3034.08 | 11.07% | 5.56% |
| `gitgalaxy/metrics` | 5 | 2502.8 | 15.52% | 0.0% |
| `gitgalaxy/recorders` | 8 | 1844.42 | 22.56% | 0.0% |
| `gitgalaxy/security` | 4 | 1011.76 | 10.82% | 0.0% |
| `gitgalaxy/standards` | 7 | 993.52 | 7.84% | 5.14% |
| `__monolith__` | 11 | 75.52 | 1.54% | 0.0% |
| `templates/azure` | 1 | 15.84 | 7.42% | 0.0% |
| `templates/bitbucket` | 1 | 15.4 | 11.92% | 0.0% |
| `templates` | 1 | 15.22 | 5.0% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_build_forge.py` -> **100.0%** Exposure
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_decoder_forge.py` -> **99.3307%** Exposure
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_agent_forge.py` -> **99.1089%** Exposure
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_service_forge.py` -> **80.9593%** Exposure
- `gitgalaxy/standards/language_standards.py` -> **28.017%** Exposure
### Highest State Flux (Mutation/Volatility)
- `gitgalaxy/recorders/llm_recorder.py` -> **100.0%** Exposure
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` -> **100.0%** Exposure
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py` -> **100.0%** Exposure
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_service_forge.py` -> **100.0%** Exposure
- `gitgalaxy/tools/cobol_to_cobol/cobol_jcl_forge.py` -> **99.9999%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_build_forge.py` -> **3** Orphaned Functions | **0** Duplicates
- `gitgalaxy/cobol_refractor_controller.py` -> **1** Orphaned Functions | **0** Duplicates
- `gitgalaxy/core/state_rehydrator.py` -> **1** Orphaned Functions | **0** Duplicates
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_agent_forge.py` -> **1** Orphaned Functions | **0** Duplicates
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_decoder_forge.py` -> **1** Orphaned Functions | **0** Duplicates

## 10.5 AI THREAT INTELLIGENCE (XGBoost)
*No files met the threshold for malicious structural signatures.*

## 10.6 WEAPONIZABLE SURFACE EXPOSURES (RULE-BASED SAST)
> Secondary Evidence: The following files tripped specific static threat signatures. Use these to explain *why* the XGBoost model flagged the files above.

### Exploit Generation Surface
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **100.0%** Exposure
- `gitgalaxy/core/prism.py` -> **100.0%** Exposure
- `gitgalaxy/metrics/chronometer.py` -> **100.0%** Exposure
### Algorithmic DoS Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **100.0%** Exposure
- `gitgalaxy/core/prism.py` -> **100.0%** Exposure
- `gitgalaxy/metrics/chronometer.py` -> **100.0%** Exposure

## 10.7 AUTONOMOUS AI VULNERABILITIES (AGENTIC RCE & PROMPT INJECTION)
> **AI CONTEXT:** Identifies untrusted data flowing into LLM context windows (Prompt Injection) and LLM outputs flowing into dynamic execution (Agentic RCE).

*No autonomous AI vulnerabilities detected.*

## 10.8 ECOSYSTEM SECURITY AUDITS
> **AI CONTEXT:** High-level perimeter defense metrics from the X-Ray, Supply Chain Firewall, and API Network Mapper.

### ☢️ X-Ray & 🧱 Supply Chain Firewall
- **Binary Anomalies (X-Ray):** `0` (High entropy, packed payloads, or magic byte mismatches).
- **Blacklisted Dependencies:** `0` explicitly banned packages imported.
- **Unknown Dependencies:** `377` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/spatial_mapper.py` (PYTHON) -> Cumulative Risk: **722.96**
- **Archetype:** `file_cluster_8` (Distance: 10.577 IQR)
- **Magnitude:** 277.4 | **LOC:** 233 | **CtrlFlow:** 64.2% | **Authorship Centralization:** 57.1%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `map_repository` (Impact: 203.4), `__init__` (Impact: 15.0), `_hash_jitter` (Impact: 8.4)

### 2. `gitgalaxy/metrics/chronometer.py` (PYTHON) -> Cumulative Risk: **695.93**
- **Archetype:** `file_cluster_8` (Distance: 10.416 IQR)
- **Magnitude:** 344.52 | **LOC:** 420 | **CtrlFlow:** 64.3% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `_determine_commit_bounds` (Impact: 118.5), `_load_ignored_revs` (Impact: 49.4), `_initialize_history_scan` (Impact: 43.7)

### 3. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **686.48**
- **Archetype:** `file_cluster_8` (Distance: 10.113 IQR)
- **Magnitude:** 1448.46 | **LOC:** 524 | **CtrlFlow:** 72.2% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (95.068%)
- **Heaviest Functions:** `audit` (Impact: 1292.0), `_is_threat` (Impact: 30.9), `_is_dead_code` (Impact: 26.1)

### 4. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **673.27**
- **Archetype:** `file_cluster_8` (Distance: 10.072 IQR)
- **Magnitude:** 386.72 | **LOC:** 410 | **CtrlFlow:** 54.5% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `main` (Impact: 129.7), `process_payload` (Impact: 80.0), `record_dead_code` (Impact: 34.5)

### 5. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **671.87**
- **Archetype:** `file_cluster_8` (Distance: 11.329 IQR)
- **Magnitude:** 2841.92 | **LOC:** 2578 | **CtrlFlow:** 69.3% | **Authorship Centralization:** 77.4%
- **Primary Risk Drivers:** Spec Match (100.0%), Churn (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `_resolve_dependency_graph` (Impact: 1027.8), `execute_pipeline` (Impact: 936.2), `_render_splicing_chart` (Impact: 594.0)

### 6. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **670.53**
- **Archetype:** `file_cluster_8` (Distance: 10.811 IQR)
- **Magnitude:** 1064.16 | **LOC:** 629 | **CtrlFlow:** 63.6% | **Authorship Centralization:** 85.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.6585%)
- **Heaviest Functions:** `_find_balanced_end` (Impact: 394.2), `_compile_regex_matrix` (Impact: 204.8), `split_streams` (Impact: 137.1)

### 7. `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) -> Cumulative Risk: **667.69**
- **Archetype:** `file_cluster_8` (Distance: 9.788 IQR)
- **Magnitude:** 579.96 | **LOC:** 335 | **CtrlFlow:** 62.3% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), Documentation (91.4841%)
- **Heaviest Functions:** `slice_manifest` (Impact: 326.8), `locate_physical_package` (Impact: 198.5), `__init__` (Impact: 9.2)

### 8. `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` (PYTHON) -> Cumulative Risk: **638.72**
- **Archetype:** `file_cluster_8` (Distance: 11.3 IQR)
- **Magnitude:** 0.34 | **LOC:** 214 | **CtrlFlow:** 58.0% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%)
- **Heaviest Functions:** `flatten_copybooks` (Impact: 184.3), `generate_build_jcl` (Impact: 34.5), `main` (Impact: 23.0)

### 9. `gitgalaxy/tools/ai_guardrails/ai_appsec_sensor.py` (PYTHON) -> Cumulative Risk: **630.99**
- **Archetype:** `file_cluster_8` (Distance: 10.014 IQR)
- **Magnitude:** 0.15 | **LOC:** 84 | **CtrlFlow:** 78.1% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), State Flux (99.1542%), Logic Bomb (98.2806%)
- **Heaviest Functions:** `hunt_threats` (Impact: 122.8), `__init__` (Impact: 7.9)

### 10. `gitgalaxy/recorders/sarif_recorder.py` (PYTHON) -> Cumulative Risk: **608.58**
- **Archetype:** `file_cluster_8` (Distance: 8.753 IQR)
- **Magnitude:** 134.26 | **LOC:** 206 | **CtrlFlow:** 66.0% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (99.9881%), Logic Bomb (99.9839%), State Flux (86.6419%)
- **Heaviest Functions:** `_build_rules_taxonomy` (Impact: 49.6), `_build_dependency_notifications` (Impact: 34.3), `_build_location` (Impact: 12.8)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.329 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.555 IQR)
- **Top Global Matches:** file_cluster_8: 11.329, file_cluster_13: 11.537, file_cluster_7: 11.787
- **Magnitude:** 2841.92 | **LOC:** 2578 | **CtrlFlow:** 69.3% | **Authorship Centralization:** 77.4%
- **Algorithmic:** O(N^6) | **DB Complexity:** 33
- **Risk Profile:** Cognitive Load (20.7406%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` (Impact: 1027.8 | O(N^6) | DB: 21)
  * `execute_pipeline` (Impact: 936.2 | O(N^6) | DB: 33)
  * `_render_splicing_chart` (Impact: 594.0 | O(N^6) | DB: 32)
  * `_render_file_speed_chart` (Impact: 18.6 | O(N^3))
    * *Intent:* """ if self.temp_dir and Path(self.temp_dir).exists(): try: shutil.rmtree(self.temp_dir) except Exce...
  * `__init__` (Impact: 1.8 | O(N^2))
    * *Intent:* # ============================================================================== # GitGalaxy Phase 3...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 515`, `structural_boundaries: 228`, `args: 29`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 72`, `state_mutation: 212`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 4`, `import: 64`
* *Defense:* `safety: 61`, `doc: 36`, `test: 2`, `sync_locks: 1`, `immutability_locks: 1`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` collections, gitgalaxy.recorders.record_keeper, shutil, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.core.detector, gitgalaxy.tools.ai_guardrails.ai_appsec_sensor, logging, importlib...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.113 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.152 IQR)
- **Top Global Matches:** file_cluster_8: 10.113, file_cluster_16: 10.43, file_cluster_13: 10.536
- **Magnitude:** 1448.46 | **LOC:** 524 | **CtrlFlow:** 72.2% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 22
- **Risk Profile:** Cognitive Load (34.5741%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit` (Impact: 1292.0 | O(2^N) | DB: 22)
  * `_is_threat` (Impact: 30.9 | O(N^4))
    * *Intent:* # Preserve Phase 1 Telemetry for SBOM Traceability "failed_claim": artifact.get("lang_id", "unknown"...
  * `_is_dead_code` (Impact: 26.1 | O(N^4))
  * `_is_highly_blended` (Impact: 20.7 | O(N^4))
  * `_format_for_exclusion` (Impact: 9.7 | O(N^3))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 109`, `structural_boundaries: 42`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 26`, `state_mutation: 56`
* *Architecture:* `io: 2`, `api: 3`, `import: 5`
* *Defense:* `safety: 10`, `doc: 14`, `sync_locks: 4`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` statistics, os, logging, math, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.811 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.937 IQR)
- **Top Global Matches:** file_cluster_8: 10.811, file_cluster_16: 10.892, file_cluster_7: 11.149
- **Magnitude:** 1064.16 | **LOC:** 629 | **CtrlFlow:** 63.6% | **Authorship Centralization:** 85.7%
- **Algorithmic:** O(N^6) | **DB Complexity:** 11
- **Risk Profile:** Cognitive Load (22.08%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_find_balanced_end` (Impact: 394.2 | O(N^6) | DB: 11)
  * `_compile_regex_matrix` (Impact: 204.8 | O(N^6) | DB: 1)
    * *Intent:* # 4. GENERIC STRIPPER pattern = self.REGEX_MATRIX.get(family) if not pattern: # Restore mask tokens ...
  * `split_streams` (Impact: 137.1 | O(N^5) | DB: 3)
    * *Intent:* # Phase 6.1 Handshake Registry (Synchronized securely via Language Standards) for trigger_config in ...
  * `_partition_embedded_languages` (Impact: 136.6 | O(N^6) | DB: 4)
  * `_strip_segment_comments` (Impact: 64.4 | O(N^4) | DB: 7)
    * *Intent:* # 3. Derive the documentation lines by subtracting code from the active total. # This forces mutual ...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 133`, `structural_boundaries: 76`, `args: 23`, `func_start: 19`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 96`
* *Architecture:* `api: 12`, `import: 4`
* *Defense:* `safety: 5`, `doc: 32`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` re, gitgalaxy.standards.language_standards, typing, logging
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.41 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.685 IQR)
- **Top Global Matches:** file_cluster_8: 9.41, file_cluster_13: 9.891, file_cluster_16: 9.981
- **Magnitude:** 864.12 | **LOC:** 399 | **CtrlFlow:** 77.6% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 2
- **Risk Profile:** Cognitive Load (17.939%), Tech Debt (10.079%)
**Top Internal Functions/Classes:**
  * `extract_test_coverage_mapping` (Impact: 679.2 | O(N^6) | DB: 2)
  * `_fallback_build_graph` (Impact: 157.6 | O(N^6))
    * *Intent:* # E. Articulation Points (Fragmentation Risk) try: macro_metrics["articulation_points"] = len(list(n...
  * `__init__` (Impact: 7.9 | O(N^2) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 118`, `structural_boundaries: 34`, `args: 4`, `func_start: 4`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 8`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 5`, `import: 7`
* *Defense:* `safety: 21`, `doc: 6`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.analysis_lens, pathlib, networkx.algorithms, networkx, logging, math, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.582 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.015 IQR)
- **Top Global Matches:** file_cluster_8: 11.582, file_cluster_13: 11.921, file_cluster_16: 11.976
- **Magnitude:** 795.1 | **LOC:** 1468 | **CtrlFlow:** 87.7% | **Authorship Centralization:** 90.9%
- **Algorithmic:** O(N^3) | **DB Complexity:** 4
- **Risk Profile:** Cognitive Load (63.4007%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 11.0 | O(N^3) | DB: 4)
  * `_parse_threat_score` (Impact: 7.3 | O(N^3))
  * `generate_artifacts` (Impact: 1.9 | O(N^2))
  * `_build_markdown` (Impact: 1.9 | O(N^2))
  * `_generate_sqlite_graph` (Impact: 1.9 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 327`, `structural_boundaries: 46`, `args: 31`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 731`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 14`, `doc: 26`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` collections, heapq, statistics, gitgalaxy.standards, json, logging, pathlib, typing...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.765 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.658 IQR)
- **Top Global Matches:** file_cluster_8: 9.765, file_cluster_13: 10.075, file_cluster_7: 10.147
- **Magnitude:** 652.66 | **LOC:** 476 | **CtrlFlow:** 64.6% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 16
- **Risk Profile:** Cognitive Load (9.6022%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_scan_package_manifests` (Impact: 306.9 | O(N^6) | DB: 16)
    * *Intent:* # ============================================================================== # DEEP MANIFEST INS...
  * `get_intent_status` (Impact: 97.8 | O(N^5))
  * `_calculate_documentation_coverage` (Impact: 87.3 | O(N^6) | DB: 3)
  * `_scan_gitignore_evasion` (Impact: 56.5 | O(N^6) | DB: 3)
    * *Intent:* # ============================================================================== # SECURITY EVASION ...
  * `_inject_intent_lock` (Impact: 35.5 | O(N^3))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 104`, `structural_boundaries: 57`, `args: 15`, `func_start: 15`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 17`, `state_mutation: 15`
* *Architecture:* `io: 8`, `api: 6`, `import: 8`
* *Defense:* `safety: 17`, `doc: 32`, `sync_locks: 4`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` fnmatch, gitgalaxy.standards.gitgalaxy_config, re, os, logging, pathlib, typing, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.788 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.92 IQR)
- **Top Global Matches:** file_cluster_8: 9.788, file_cluster_13: 9.79, file_cluster_16: 10.292
- **Magnitude:** 579.96 | **LOC:** 335 | **CtrlFlow:** 62.3% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 26
- **Risk Profile:** Cognitive Load (29.9025%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` (Impact: 326.8 | O(N^6) | DB: 26)
  * `locate_physical_package` (Impact: 198.5 | O(N^6) | DB: 6)
  * `__init__` (Impact: 9.2 | O(N^2) | DB: 2)
  * `generate_report` (Impact: 1.8 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 99`, `structural_boundaries: 60`, `args: 4`, `func_start: 4`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 11`, `state_mutation: 31`
* *Architecture:* `io: 13`, `api: 7`, `import: 13`
* *Defense:* `safety: 6`, `doc: 6`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` uuid, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, datetime, gitgalaxy.security.security_lens, gitgalaxy.standards.gitgalaxy_config, re, os...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.139 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.9 IQR)
- **Top Global Matches:** file_cluster_8: 10.139, file_cluster_13: 10.448, file_cluster_7: 10.633
- **Magnitude:** 567.26 | **LOC:** 399 | **CtrlFlow:** 67.3% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 8
- **Risk Profile:** Cognitive Load (19.1666%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` (Impact: 168.8 | O(N^6) | DB: 3)
  * `audit_repository` (Impact: 151.5 | O(N^6))
  * `__init__` (Impact: 100.2 | O(N^6) | DB: 8)
  * `_construct_feature_matrix` (Impact: 96.4 | O(N^6) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 76`, `structural_boundaries: 37`, `args: 5`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 9`, `state_mutation: 39`
* *Architecture:* `io: 1`, `api: 5`, `import: 8`
* *Defense:* `safety: 13`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` collections, gitgalaxy.standards.analysis_lens, numpy, xgboost, networkx, pandas, logging, pathlib
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.801 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.724 IQR)
- **Top Global Matches:** file_cluster_8: 8.801, file_cluster_16: 9.276, file_cluster_7: 9.391
- **Magnitude:** 526.18 | **LOC:** 2489 | **CtrlFlow:** 76.1% | **Authorship Centralization:** 87.5%
- **Algorithmic:** O(N^6) | **DB Complexity:** 1
- **Risk Profile:** Cognitive Load (16.1301%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_rank_list` (Impact: 75.5 | O(N^5))
  * `_get_context_multipliers` (Impact: 57.0 | O(N^4) | DB: 1)
  * `_get_locational_multipliers` (Impact: 43.5 | O(N^5))
    * *Intent:* # 4. Generate rankings using ONLY the masked `active_files` list report = { "exposures": {}, "file_i...
  * `_generate_function_rankings` (Impact: 42.9 | O(N^6) | DB: 1)
  * `get_cumulative_risk` (Impact: 26.4 | O(N^4))
    * *Intent:* # -------------------------------------------------------------------------- # REPORTING UTILITIES #...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 488`, `structural_boundaries: 153`, `args: 44`, `func_start: 36`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 40`, `high_risk_execution: 3`, `state_mutation: 101`
* *Architecture:* `io: 1`, `api: 9`, `concurrency: 2`, `import: 8`
* *Defense:* `safety: 76`, `doc: 50`, `sync_locks: 1`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` statistics, gitgalaxy.standards, re, os, logging, math, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_standards.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.075 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.832 IQR)
- **Top Global Matches:** file_cluster_8: 9.075, file_cluster_0: 9.741, file_cluster_1: 9.743
- **Magnitude:** 495.46 | **LOC:** 10499 | **CtrlFlow:** 76.9% | **Authorship Centralization:** 85.7%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (13.7481%), Tech Debt (28.017%)
**Contextual Mitigations & Amplifications:**
* *Sec Hardcoded Secrets:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 2363`, `structural_boundaries: 709`, `args: 3`
* *Risk/State:* `safety_bypasses: 111`, `high_risk_execution: 23`, `state_mutation: 133`, `dead_code: 5`, `planned_debt: 64`, `fragile_debt: 87`
* *Architecture:* `io: 37`, `api: 21`, `concurrency: 117`, `import: 29`
* *Defense:* `safety: 1274`, `doc: 38`, `test: 73`, `sync_locks: 110`, `immutability_locks: 50`, `cleanup: 58`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` inside, keyword., re, java.util., path, type
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.354 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.708 IQR)
- **Top Global Matches:** file_cluster_8: 9.354, file_cluster_13: 9.541, file_cluster_16: 9.728
- **Magnitude:** 428.46 | **LOC:** 176 | **CtrlFlow:** 70.0% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (19.1164%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_parse_requirements_txt` (Impact: 113.2 | O(N^6) | DB: 3)
    * *Intent:* # DEFENSIVE GUARD: Registry Spoofing # If the resolved URL points to a non-standard domain or a dire...
  * `_parse_pip_conf` (Impact: 99.1 | O(N^6) | DB: 3)
  * `_parse_package_json` (Impact: 79.5 | O(N^5) | DB: 3)
  * `_parse_package_lock` (Impact: 55.1 | O(N^5) | DB: 3)
  * `build_resolution_map` (Impact: 53.7 | O(N^5))
    * *Intent:* # Matches standard Python packages, extracting the base name and dropping version constraints (==, >...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 63`, `structural_boundaries: 27`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 3`, `state_mutation: 7`
* *Architecture:* `io: 5`, `api: 4`, `import: 4`
* *Defense:* `safety: 3`, `doc: 12`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` re, pathlib, logging, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.072 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.835 IQR)
- **Top Global Matches:** file_cluster_8: 10.072, file_cluster_13: 10.142, file_cluster_7: 10.54
- **Magnitude:** 386.72 | **LOC:** 410 | **CtrlFlow:** 54.5% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 13
- **Risk Profile:** Cognitive Load (19.0029%), Tech Debt (11.5079%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 129.7 | O(N^4) | DB: 13)
    * *Intent:* # ============================================================================== # MAIN ORCHESTRATIO...
  * `process_payload` (Impact: 80.0 | O(N^4))
    * *Intent:* # ============================================================================== # THE PROCESSING PI...
  * `record_dead_code` (Impact: 34.5 | O(N^5) | DB: 2)
  * `calibrate_ir_medium` (Impact: 18.9 | O(N^2))
    * *Intent:* # ============================================================================== # THE SCALE SENSOR ...
  * `get_dead_paras` (Impact: 17.8 | O(N^4) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 60`, `structural_boundaries: 50`, `args: 10`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 3`, `state_mutation: 48`, `orphaned_logic: 1`
* *Architecture:* `io: 4`, `api: 8`, `import: 16`
* *Defense:* `safety: 4`, `doc: 10`, `cleanup: 3`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder, gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge, argparse, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor, datetime, gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge, gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect, gitgalaxy.tools.cobol_to_cobol.cobol_system_limits_reporter...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.416 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.551 IQR)
- **Top Global Matches:** file_cluster_8: 10.416, file_cluster_13: 10.572, file_cluster_16: 10.792
- **Magnitude:** 344.52 | **LOC:** 420 | **CtrlFlow:** 64.3% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 13
- **Risk Profile:** Cognitive Load (14.2686%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_determine_commit_bounds` (Impact: 118.5 | O(N^6) | DB: 13)
  * `_load_ignored_revs` (Impact: 49.4 | O(N^6) | DB: 3)
  * `_initialize_history_scan` (Impact: 43.7 | O(N^5) | DB: 2)
  * `_scan_git_history` (Impact: 33.6 | O(N^4))
  * `_survey_filesystem_mtimes` (Impact: 21.3 | O(N^5) | DB: 6)
    * *Intent:* # ================================================================== # DEFENSIVE ARCHITECTURE: Zombi...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 72`, `structural_boundaries: 40`, `args: 8`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `high_risk_execution: 2`, `state_mutation: 34`
* *Architecture:* `io: 9`, `api: 4`, `import: 7`
* *Defense:* `safety: 20`, `doc: 18`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards, os, logging, time, pathlib, subprocess, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/spatial_mapper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.577 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.868 IQR)
- **Top Global Matches:** file_cluster_8: 10.577, file_cluster_13: 10.622, file_cluster_16: 10.719
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` math, typing, logging, hashlib
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.216 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.988 IQR)
- **Top Global Matches:** file_cluster_8: 8.216, file_cluster_16: 8.654, file_cluster_7: 8.842
- **Magnitude:** 269.48 | **LOC:** 1114 | **CtrlFlow:** 72.8% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 1
- **Risk Profile:** Cognitive Load (25.7957%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_tier_2_fingerprint_check` (Impact: 92.3 | O(N^6) | DB: 1)
    * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents g...
  * `_calibrate_lookup_maps` (Impact: 79.9 | O(N^6))
  * `_tier_1_metadata_lock` (Impact: 16.6 | O(N^3))
  * `inspect` (Impact: 1.9 | O(N^2))
  * `__init__` (Impact: 1.8 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 283`, `structural_boundaries: 106`, `args: 17`, `func_start: 13`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 29`, `state_mutation: 46`
* *Architecture:* `io: 2`, `api: 6`, `import: 9`
* *Defense:* `safety: 14`, `doc: 24`, `sync_locks: 2`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, gitgalaxy.standards.gitgalaxy_config, re, logging, time, math, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/analysis_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 6.106 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.52 IQR)
- **Top Global Matches:** file_cluster_8: 6.106, file_cluster_7: 7.195, file_cluster_1: 7.256
- **Magnitude:** 180.6 | **LOC:** 8359 | **CtrlFlow:** 77.1% | **Authorship Centralization:** 88.9%
- **Algorithmic:** O(N^2) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (5.0198%), Tech Debt (7.9736%)
**Top Internal Functions/Classes:**
  * `get_policy` (Impact: 3.1 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec Hardcoded Secrets:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 111`, `structural_boundaries: 33`, `args: 1`, `func_start: 1`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 1`, `high_risk_execution: 1`, `state_mutation: 7`, `dead_code: 1`, `planned_debt: 2`, `fragile_debt: 2`
* *Architecture:* `api: 3`, `concurrency: 1`, `import: 1`
* *Defense:* `safety: 1`, `doc: 7`, `test: 4`, `sync_locks: 3`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/tensor_scanner.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.388 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.563 IQR)
- **Top Global Matches:** file_cluster_8: 8.388, file_cluster_13: 8.572, file_cluster_16: 8.695
- **Magnitude:** 168.96 | **LOC:** 151 | **CtrlFlow:** 51.7% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^5) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (7.6461%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_parse_gguf` (Impact: 71.4 | O(N^4) | DB: 3)
  * `_parse_safetensors` (Impact: 38.8 | O(N^5) | DB: 3)
  * `audit_model` (Impact: 27.1 | O(N^5))
  * `_format_params` (Impact: 14.4 | O(N^3))
  * `__init__` (Impact: 7.9 | O(N^2) | DB: 1)
    * *Intent:* """ def __init__(self, parent_logger: logging.Logger = None): self.logger = parent_logger.getChild("...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 30`, `structural_boundaries: 28`, `args: 5`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 5`, `state_mutation: 3`
* *Architecture:* `io: 3`, `api: 4`, `import: 6`
* *Defense:* `safety: 2`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pathlib, struct, logging, math, typing, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/gpu_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.498 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.724 IQR)
- **Top Global Matches:** file_cluster_8: 10.498, file_cluster_13: 10.692, file_cluster_16: 10.734
- **Magnitude:** 149.54 | **LOC:** 403 | **CtrlFlow:** 66.2% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^4) | **DB Complexity:** 5
- **Risk Profile:** Cognitive Load (41.6737%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `save_minified` (Impact: 17.4 | O(N^4) | DB: 3)
  * `__init__` (Impact: 10.2 | O(N^2) | DB: 5)
  * `_intern` (Impact: 8.3 | O(N^3) | DB: 1)
  * `record_mission` (Impact: 2.0 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 47`, `structural_boundaries: 24`, `args: 5`, `func_start: 4`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 18`, `state_mutation: 99`
* *Architecture:* `io: 2`, `api: 6`, `import: 7`
* *Defense:* `safety: 7`, `doc: 8`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards, logging, pathlib, typing, gc, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.121 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.947 IQR)
- **Top Global Matches:** file_cluster_8: 9.121, file_cluster_16: 9.434, file_cluster_7: 9.564
- **Magnitude:** 136.16 | **LOC:** 2232 | **CtrlFlow:** 70.0% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^3) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (12.1875%), Tech Debt (8.3425%)
**Top Internal Functions/Classes:**
  * `get_token_mass` (Impact: 8.5 | O(N^2))
    * *Intent:* """Calculates context window footprint. Returns None if tiktoken is missing to prevent dataset poiso...
  * `get_mode` (Impact: 8.3 | O(N^2))
  * `get_config` (Impact: 7.3 | O(N^3))
  * `splice` (Impact: 1.9 | O(N^2))
  * `__init__` (Impact: 1.8 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 285`, `structural_boundaries: 122`, `args: 16`, `func_start: 15`, `class_start: 4`
* *Risk/State:* `safety_bypasses: 28`, `state_mutation: 75`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 14`, `import: 10`
* *Defense:* `safety: 28`, `doc: 60`, `test: 1`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` collections, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, re, bisect, logging, time, math...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/sarif_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.753 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.197 IQR)
- **Top Global Matches:** file_cluster_8: 8.753, file_cluster_16: 9.037, file_cluster_13: 9.179
- **Magnitude:** 134.26 | **LOC:** 206 | **CtrlFlow:** 66.0% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^5) | **DB Complexity:** 2
- **Risk Profile:** Cognitive Load (14.5282%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_build_rules_taxonomy` (Impact: 49.6 | O(N^4))
    * *Intent:* """ Maps GitGalaxy's internal rule IDs to standardized descriptions. This provides enterprise dashbo...
  * `_build_dependency_notifications` (Impact: 34.3 | O(N^5) | DB: 1)
  * `_build_location` (Impact: 12.8 | O(N^5))
  * `__init__` (Impact: 9.2 | O(N^2) | DB: 2)
  * `generate_report` (Impact: 1.8 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 31`, `structural_boundaries: 16`, `args: 5`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 9`, `high_risk_execution: 2`, `state_mutation: 19`
* *Architecture:* `io: 1`, `api: 4`, `import: 3`
* *Defense:* `safety: 2`, `doc: 8`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, logging, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/audit_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.332 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.221 IQR)
- **Top Global Matches:** file_cluster_8: 8.332, file_cluster_13: 8.97, file_cluster_7: 8.975
- **Magnitude:** 102.28 | **LOC:** 582 | **CtrlFlow:** 80.0% | **Authorship Centralization:** 88.9%
- **Algorithmic:** O(N^3) | **DB Complexity:** 5
- **Risk Profile:** Cognitive Load (15.9983%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `descale` (Impact: 27.5 | O(N^3))
  * `format_label` (Impact: 14.6 | O(N^3))
    * *Intent:* # PERFORMANCE OPTIMIZATION: Pre-cache all labels to avoid regex overhead on the hot path self._label...
  * `__init__` (Impact: 8.5 | O(N^2) | DB: 5)
  * `generate_report` (Impact: 1.9 | O(N^2))
  * `decode_galaxy` (Impact: 1.9 | O(N^1))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 124`, `structural_boundaries: 31`, `args: 8`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 15`, `state_mutation: 29`
* *Architecture:* `io: 3`, `api: 9`, `import: 8`
* *Defense:* `safety: 17`, `doc: 10`, `sync_locks: 1`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` argparse, gitgalaxy.standards, re, os, logging, pathlib, typing, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/record_keeper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 7.989 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.677 IQR)
- **Top Global Matches:** file_cluster_8: 7.989, file_cluster_7: 8.566, file_cluster_1: 8.698
- **Magnitude:** 67.46 | **LOC:** 876 | **CtrlFlow:** 90.3% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^3) | **DB Complexity:** 4
- **Risk Profile:** Cognitive Load (9.9378%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 13.9 | O(N^3) | DB: 4)
  * `record_mission` (Impact: 1.9 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 130`, `structural_boundaries: 14`, `args: 2`, `func_start: 2`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 6`, `state_mutation: 36`
* *Architecture:* `io: 1`, `api: 4`, `import: 7`
* *Defense:* `safety: 3`, `doc: 28`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.analysis_lens, statistics, sqlite3, logging, pathlib, typing, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/gitgalaxy_config.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 4.969 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.335 IQR)
- **Top Global Matches:** file_cluster_8: 4.969, file_cluster_7: 6.316, file_cluster_1: 6.363
- **Magnitude:** 27.68 | **LOC:** 620 | **CtrlFlow:** 76.0% | **Authorship Centralization:** 87.5%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (5.3469%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 19`, `structural_boundaries: 6`
* *Risk/State:* `state_mutation: 1`
* *Architecture:* `io: 1`
* *Defense:* `safety: 1`, `doc: 2`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` None
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/state_rehydrator.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.063 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.355 IQR)
- **Top Global Matches:** file_cluster_8: 9.063, file_cluster_13: 9.459, file_cluster_7: 9.501
- **Magnitude:** 23.36 | **LOC:** 161 | **CtrlFlow:** 45.2% | **Authorship Centralization:** 60.0%
- **Algorithmic:** O(N^3) | **DB Complexity:** 1
- **Risk Profile:** Cognitive Load (4.5521%), Tech Debt (26.0439%)
**Top Internal Functions/Classes:**
  * `load_latest_state` (Impact: 14.6 | O(N^3))
  * `__init__` (Impact: 2.7 | O(N^2) | DB: 1)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 14`, `structural_boundaries: 17`, `args: 3`, `func_start: 3`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 4`, `state_mutation: 1`, `orphaned_logic: 1`
* *Architecture:* `io: 1`, `api: 3`, `import: 3`
* *Defense:* `safety: 7`, `doc: 14`, `test: 3`, `cleanup: 3`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pathlib, typing, sqlite3
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `muninn.yml` (YAML | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 4.57 IQR)
- **Top Global Matches:** file_cluster_8: 4.57, file_cluster_7: 6.309, file_cluster_1: 6.377
- **Magnitude:** 16.58 | **LOC:** 81 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 75.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 11.628
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` None
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_13
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py` (PYTHON) | Magnitude: 0.37 | Delta: **0.123 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 174, state_mutation: 85, branch: 64, structural_boundaries: 36
- `gitgalaxy/tools/cobol_to_cobol/cobol_etl_unpacker.py` (PYTHON) | Magnitude: 0.28 | Delta: **0.137 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 133, branch: 50, structural_boundaries: 34, state_mutation: 13
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py` (PYTHON) | Magnitude: 0.21 | Delta: **0.249 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 107, state_mutation: 88, branch: 29, structural_boundaries: 23
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_service_forge.py` (PYTHON) | Magnitude: 0.07 | Delta: **0.484 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 52, state_mutation: 33, structural_boundaries: 26, branch: 14

### Mixed-Responsibility Refactoring Targets for: file_cluster_16
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_build_forge.py` (PYTHON) | Magnitude: 0.01 | Delta: **0.065 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: doc: 12, structural_boundaries: 6, indent_spaces: 6, branch: 5

### Mixed-Responsibility Refactoring Targets for: file_cluster_6
- `gitgalaxy/tools/cobol_to_java/cobol_to_java_agent_forge.py` (PYTHON) | Magnitude: 0.04 | Delta: **0.112 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 35, branch: 12, structural_boundaries: 5, safety_bypasses: 3

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 579.96 | Delta: **0.002 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 262, branch: 99, structural_boundaries: 60, state_mutation: 31
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 277.4 | Delta: **0.045 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 153, branch: 34, state_mutation: 32, encapsulation: 23
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` (PYTHON) | Magnitude: 0.34 | Delta: **0.049 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 138, state_mutation: 75, branch: 29, structural_boundaries: 21
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 386.72 | Delta: **0.07 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 285, branch: 60, structural_boundaries: 50, state_mutation: 48
- `gitgalaxy/tools/ai_guardrails/ai_appsec_sensor.py` (PYTHON) | Magnitude: 0.15 | Delta: **0.079 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 48, branch: 25, state_mutation: 12, structural_boundaries: 7

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **71.7%** | Cog Load: 63.4007% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/metrics/statistical_auditor.py` -> **squid-protocol** (100.0% isolated ownership) | Magnitude: 1448.46
- `gitgalaxy/core/prism.py` -> **squid-protocol** (85.7% isolated ownership) | Magnitude: 1064.16
- `gitgalaxy/core/network_risk_sensor.py` -> **squid-protocol** (100.0% isolated ownership) | Magnitude: 864.12
- `gitgalaxy/recorders/llm_recorder.py` -> **squid-protocol** (90.9% isolated ownership) | Magnitude: 795.1
- `gitgalaxy/core/guidestar_lens.py` -> **squid-protocol** (100.0% isolated ownership) | Magnitude: 652.66

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 1162.8** (Blast Radius: 11.628 * Doc Risk: 100.0%)
- `gitgalaxy/core/spatial_mapper.py` -> **Severity: 1162.8** (Blast Radius: 11.628 * Doc Risk: 100.0%)
- `gitgalaxy/metrics/chronometer.py` -> **Severity: 1162.8** (Blast Radius: 11.628 * Doc Risk: 100.0%)
- `gitgalaxy/metrics/tensor_scanner.py` -> **Severity: 1162.8** (Blast Radius: 11.628 * Doc Risk: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` -> **Severity: 1162.8** (Blast Radius: 11.628 * Doc Risk: 100.0%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Act as a Principal Staff Engineer. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility). DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective, practical, and direct.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
