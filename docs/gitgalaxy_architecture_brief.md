# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-07-17T22:27:12.798136+00:00` |
| **Scan Duration** | `6.34s` |
| **Git Branch** | `main` |
| **Git Commit** | `93074b7fb0c64bbeaee5c210d493d712d9bffdec` |
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
| Total Artifacts | 606 |
| Analyzed Artifacts (Scanned) | 148 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 458 |
| Total LOC | 48422 |
| Volatility Index | 0.007 |
| % Scanned of codebase = | 24.4% |
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
| PYTHON | 115 | 47968 | 77.7% |
| MARKDOWN | 22 | 0 | 14.9% |
| YAML | 8 | 454 | 5.4% |
| PLAINTEXT | 3 | 0 | 2.0% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `6.639`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 114 | 77.0% |
| file_cluster_13 | 7 | 4.7% |
| file_cluster_6 | 1 | 0.7% |
| file_cluster_16 | 1 | 0.7% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 25 | 16.9% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 458*

**Composition by Extension & Reason:**
- `.md`: 331x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 63 LOC), 1x Excluded (Machine-Generated Source Code Signature: 34 LOC)
- `.png`: 58x Excluded (Explicitly Denied Extension: '.png')
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.yml`: 15x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 534 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.json`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 63.4 | 2.7 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 77.8 | 5.5 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 10.1 | 0.1 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 7.8 | 0.0 | 0.0 |
| API Exposure | 0.0 | 6.2 | 0.3 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 22.6 | 0.3 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 8.2 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 9.8 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 17.4 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 24.8 | 1.1 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 9.0 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 100.0 | 6.4 | 0.0 | 0.0 |
| Algorithmic DoS Exposure | 0.0 | 100.0 | 9.8 | 0.0 | 0.0 |
| Obfuscation & Evasion Surface | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Exploit Generation Surface | 0.0 | 100.0 | 11.8 | 0.0 | 0.0 |
| Weaponizable Injection Vectors | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Raw Memory Manipulation | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `gitgalaxy/recorders/sbom_recorder.py` (Hits: 13)
- `gitgalaxy/metrics/chronometer.py` (Hits: 9)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These files act as core load-bearing infrastructure. Changes here carry a high risk of cascading breaks.

1. **CONTRIBUTING.md** (`CONTRIBUTING.md`) — 0 inbound connections
2. **README.md** (`README.md`) — 0 inbound connections
3. **SECURITY.md** (`SECURITY.md`) — 0 inbound connections
4. **README.md** (`gitgalaxy/README.md`) — 0 inbound connections
5. **README.md** (`gitgalaxy/core/README.md`) — 0 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 53 outbound dependencies
2. **test_dependency_extraction_strict.py** (`tests/extraction/test_dependency_extraction_strict.py`) — 23 outbound dependencies
3. **cobol_refractor_controller.py** (`gitgalaxy/cobol_refractor_controller.py`) — 16 outbound dependencies
4. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 16 outbound dependencies
5. **cobol_to_java_controller.py** (`gitgalaxy/cobol_to_java_controller.py`) — 15 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **1292.0** | LOC: 361
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **1225.8** | LOC: 752
- `_resolve_dependency_graph` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **1058.7** | LOC: 683
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> Impact: **785.0** | LOC: 181
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `extract_test_coverage_mapping` (@ `gitgalaxy/core/network_risk_sensor.py`) -> Impact: **686.4** | LOC: 288
- `test_cicd_policy_enforcement_gates` (@ `tests/core_engine/test_galaxyscope.py`) -> Impact: **634.8** | LOC: 1176
  * *Intent:* # ============================================================================== # ===================================================================...
- `_render_splicing_chart` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **600.3** | LOC: 487
- `_find_balanced_end` (@ `gitgalaxy/core/prism.py`) -> Impact: **394.2** | LOC: 169
- `slice_manifest` (@ `gitgalaxy/recorders/sbom_recorder.py`) -> Impact: **326.8** | LOC: 96
- `_scan_package_manifests` (@ `gitgalaxy/core/guidestar_lens.py`) -> Impact: **307.3** | LOC: 206
  * *Intent:* # ============================================================================== # galaxyscope:ignore sec_io, llm_hooks # ============================...

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
- `prism_engine` (@ `tests/core_engine/test_prism.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """Initializes the Prism with a controlled, deterministic regex matrix."""
- `main` (@ `gitgalaxy/cobol_to_java_controller.py`) -> **O(N^6)**
  * *Intent:* /** * This module intercepts unresolved COBOL calls to '{subroutine_name}'. * It allows the Spring Context to load and the AI Agent to write code * wi...
- `extract_test_coverage_mapping` (@ `gitgalaxy/core/network_risk_sensor.py`) -> **O(N^6)**

### Highest Data Gravity (Database Complexity)
- `test_cicd_policy_enforcement_gates` (@ `tests/core_engine/test_galaxyscope.py`) -> DB Complexity: **77**
  * *Intent:* # ============================================================================== # ===================================================================...
- `publish_insights` (@ `templates/bitbucket/bitbucket_insights.py`) -> DB Complexity: **37**
- `generate_build_jcl` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> DB Complexity: **34**
- `generate_rest_controller` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py`) -> DB Complexity: **34**
  * *Intent:* """Generates the API endpoints and auto-wires the Service layer."""
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **33**
- `_render_splicing_chart` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **32**
- `generate_java_entity` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py`) -> DB Complexity: **31**
- `slice_manifest` (@ `gitgalaxy/recorders/sbom_recorder.py`) -> DB Complexity: **26**
- `main` (@ `gitgalaxy/tools/network_auditing/full_api_network_map.py`) -> DB Complexity: **26**
- `main` (@ `gitgalaxy/tools/supply_chain_security/supply_chain_firewall.py`) -> DB Complexity: **23**

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `gitgalaxy` | 6 | 3914.76 | 8.84% | 0.0% |
| `gitgalaxy/core` | 8 | 3046.16 | 10.97% | 2.3% |
| `gitgalaxy/metrics` | 5 | 2503.16 | 15.36% | 0.0% |
| `tests/core_engine` | 15 | 2451.42 | 2.22% | 0.0% |
| `gitgalaxy/recorders` | 8 | 1858.7 | 22.43% | 0.0% |
| `tests/security_auditing` | 15 | 1378.84 | 2.67% | 0.0% |
| `gitgalaxy/security` | 4 | 1033.7 | 10.76% | 0.0% |
| `gitgalaxy/standards` | 7 | 993.52 | 7.84% | 5.14% |
| `tests/extraction` | 5 | 745.42 | 3.3% | 0.0% |
| `tests/cobol_mainframe` | 13 | 479.12 | 1.56% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `gitgalaxy/core/network_risk_sensor.py` -> **10.0529%** Exposure
- `gitgalaxy/core/detector.py` -> **8.3242%** Exposure
### Highest State Flux (Mutation/Volatility)
- `gitgalaxy/recorders/llm_recorder.py` -> **100.0%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **99.9879%** Exposure
- `gitgalaxy/core/prism.py` -> **99.6585%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **99.4115%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **96.5489%** Exposure

## 10.5 AI THREAT INTELLIGENCE (XGBoost)
*No files met the threshold for malicious structural signatures.*

## 10.6 WEAPONIZABLE SURFACE EXPOSURES (RULE-BASED SAST)
> Secondary Evidence: The following files tripped specific static threat signatures. Use these to explain *why* the XGBoost model flagged the files above.

### Exploit Generation Surface
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/detector.py` -> **100.0%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **100.0%** Exposure
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
- **Unknown Dependencies:** `667` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/spatial_mapper.py` (PYTHON) -> Cumulative Risk: **720.48**
- **Archetype:** `file_cluster_8` (Distance: 10.563 IQR)
- **Magnitude:** 277.4 | **LOC:** 233 | **CtrlFlow:** 64.2% | **Authorship Centralization:** 57.1%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `map_repository` (Impact: 203.4), `__init__` (Impact: 15.0), `_hash_jitter` (Impact: 8.4)

### 2. `gitgalaxy/metrics/chronometer.py` (PYTHON) -> Cumulative Risk: **698.66**
- **Archetype:** `file_cluster_8` (Distance: 10.442 IQR)
- **Magnitude:** 344.62 | **LOC:** 432 | **CtrlFlow:** 64.3% | **Authorship Centralization:** 66.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `_determine_commit_bounds` (Impact: 118.5), `_load_ignored_revs` (Impact: 49.4), `_initialize_history_scan` (Impact: 43.7)

### 3. `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) -> Cumulative Risk: **683.62**
- **Archetype:** `file_cluster_8` (Distance: 9.836 IQR)
- **Magnitude:** 580.02 | **LOC:** 342 | **CtrlFlow:** 62.3% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), Documentation (90.5655%)
- **Heaviest Functions:** `slice_manifest` (Impact: 326.8), `locate_physical_package` (Impact: 198.5), `__init__` (Impact: 9.2)

### 4. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **681.59**
- **Archetype:** `file_cluster_8` (Distance: 10.188 IQR)
- **Magnitude:** 1448.56 | **LOC:** 536 | **CtrlFlow:** 72.2% | **Authorship Centralization:** 66.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (94.7624%)
- **Heaviest Functions:** `audit` (Impact: 1292.0), `_is_threat` (Impact: 30.9), `_is_dead_code` (Impact: 26.1)

### 5. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **671.03**
- **Archetype:** `file_cluster_8` (Distance: 11.493 IQR)
- **Magnitude:** 3171.46 | **LOC:** 2688 | **CtrlFlow:** 70.6% | **Authorship Centralization:** 54.5%
- **Primary Risk Drivers:** Spec Match (100.0%), Churn (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `execute_pipeline` (Impact: 1225.8), `_resolve_dependency_graph` (Impact: 1058.7), `_render_splicing_chart` (Impact: 600.3)

### 6. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **670.07**
- **Archetype:** `file_cluster_8` (Distance: 10.811 IQR)
- **Magnitude:** 1064.16 | **LOC:** 630 | **CtrlFlow:** 63.6% | **Authorship Centralization:** 85.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.6585%)
- **Heaviest Functions:** `_find_balanced_end` (Impact: 394.2), `_compile_regex_matrix` (Impact: 204.8), `split_streams` (Impact: 137.1)

### 7. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **655.9**
- **Archetype:** `file_cluster_8` (Distance: 10.14 IQR)
- **Magnitude:** 388.3 | **LOC:** 429 | **CtrlFlow:** 54.5% | **Authorship Centralization:** 57.1%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (96.5489%)
- **Heaviest Functions:** `main` (Impact: 129.7), `process_payload` (Impact: 80.2), `record_dead_code` (Impact: 34.5)

### 8. `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` (PYTHON) -> Cumulative Risk: **636.64**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.34 | **LOC:** 214 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `flatten_copybooks` (Impact: 184.3), `generate_build_jcl` (Impact: 34.5), `main` (Impact: 23.0)

### 9. `gitgalaxy/recorders/sarif_recorder.py` (PYTHON) -> Cumulative Risk: **634.39**
- **Archetype:** `file_cluster_8` (Distance: 8.884 IQR)
- **Magnitude:** 147.5 | **LOC:** 218 | **CtrlFlow:** 70.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (99.9842%), Logic Bomb (99.9788%), State Flux (84.6591%)
- **Heaviest Functions:** `_build_rules_taxonomy` (Impact: 62.7), `_build_dependency_notifications` (Impact: 34.3), `_build_location` (Impact: 12.8)

### 10. `gitgalaxy/tools/ai_guardrails/ai_appsec_sensor.py` (PYTHON) -> Cumulative Risk: **626.37**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.15 | **LOC:** 84 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `hunt_threats` (Impact: 122.8), `__init__` (Impact: 7.9)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.493 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.495 IQR)
- **Top Global Matches:** file_cluster_8: 11.493, file_cluster_13: 11.714, file_cluster_7: 11.95
- **Magnitude:** 3171.46 | **LOC:** 2688 | **CtrlFlow:** 70.6% | **Authorship Centralization:** 54.5%
- **Algorithmic:** O(N^6) | **DB Complexity:** 33
- **Risk Profile:** Cognitive Load (21.3095%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `execute_pipeline` (Impact: 1225.8 | O(N^6) | DB: 33)
  * `_resolve_dependency_graph` (Impact: 1058.7 | O(N^6) | DB: 22)
  * `_render_splicing_chart` (Impact: 600.3 | O(N^6) | DB: 32)
  * `_render_file_speed_chart` (Impact: 18.6 | O(N^3))
    * *Intent:* """ if self.temp_dir and Path(self.temp_dir).exists(): try: shutil.rmtree(self.temp_dir) except Exce...
  * `__init__` (Impact: 1.8 | O(N^2))
    * *Intent:* # ============================================================================== # GitGalaxy Phase 3...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 568`, `structural_boundaries: 236`, `args: 29`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 76`, `state_mutation: 213`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 4`, `import: 64`
* *Defense:* `safety: 67`, `doc: 36`, `test: 2`, `sync_locks: 1`, `immutability_locks: 1`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` sys, gitgalaxy.core.network_risk_sensor, gitgalaxy.recorders.sbom_recorder, gitgalaxy.core.aperture, gitgalaxy.standards.language_standards, is, gitgalaxy.tools.ai_guardrails.dev_agent_firewall, gitgalaxy.tools.network_auditing.full_api_network_map...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.188 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.137 IQR)
- **Top Global Matches:** file_cluster_8: 10.188, file_cluster_16: 10.509, file_cluster_13: 10.615
- **Magnitude:** 1448.56 | **LOC:** 536 | **CtrlFlow:** 72.2% | **Authorship Centralization:** 66.7%
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, os, math, statistics, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.811 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.937 IQR)
- **Top Global Matches:** file_cluster_8: 10.811, file_cluster_16: 10.892, file_cluster_7: 11.149
- **Magnitude:** 1064.16 | **LOC:** 630 | **CtrlFlow:** 63.6% | **Authorship Centralization:** 85.7%
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` re, gitgalaxy.standards.language_standards, logging, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.521 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.701 IQR)
- **Top Global Matches:** file_cluster_8: 9.521, file_cluster_13: 9.963, file_cluster_16: 10.087
- **Magnitude:** 871.38 | **LOC:** 403 | **CtrlFlow:** 77.3% | **Authorship Centralization:** 83.3%
- **Algorithmic:** O(N^6) | **DB Complexity:** 2
- **Risk Profile:** Cognitive Load (17.9231%), Tech Debt (10.0529%)
**Top Internal Functions/Classes:**
  * `extract_test_coverage_mapping` (Impact: 686.4 | O(N^6) | DB: 2)
  * `_fallback_build_graph` (Impact: 157.6 | O(N^6))
    * *Intent:* # E. Articulation Points (Fragmentation Risk) try: macro_metrics["articulation_points"] = len(list(n...
  * `__init__` (Impact: 7.9 | O(N^2) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 119`, `structural_boundaries: 35`, `args: 4`, `func_start: 4`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 8`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 5`, `import: 8`
* *Defense:* `safety: 21`, `doc: 6`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` networkx, logging, warnings, gitgalaxy.standards.analysis_lens, math, pathlib, networkx.algorithms, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.583 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.003 IQR)
- **Top Global Matches:** file_cluster_8: 11.583, file_cluster_13: 11.929, file_cluster_16: 11.983
- **Magnitude:** 795.44 | **LOC:** 1504 | **CtrlFlow:** 87.7% | **Authorship Centralization:** 76.9%
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, sqlite3, json, heapq, collections, pathlib, statistics, gitgalaxy.standards...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 710.44 | **LOC:** 1334 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_cicd_policy_enforcement_gates` (Impact: 634.8 | O(N^5) | DB: 77)
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
  * `Imports (Out-Degree: 0):` sys, logging, gitgalaxy.core.aperture, passes, gitgalaxy.galaxyscope, failure, subprocess, os...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.782 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.593 IQR)
- **Top Global Matches:** file_cluster_8: 9.782, file_cluster_13: 10.116, file_cluster_7: 10.167
- **Magnitude:** 653.72 | **LOC:** 504 | **CtrlFlow:** 64.6% | **Authorship Centralization:** 75.0%
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.gitgalaxy_config, logging, os, json, re, fnmatch, pathlib, typing
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
  * `Imports (Out-Degree: 0):` networkx, logging, pandas, xgboost, gitgalaxy.standards.analysis_lens, collections, pathlib, numpy
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 9.836 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.905 IQR)
- **Top Global Matches:** file_cluster_8: 9.836, file_cluster_13: 9.846, file_cluster_16: 10.343
- **Magnitude:** 580.02 | **LOC:** 342 | **CtrlFlow:** 62.3% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 26
- **Risk Profile:** Cognitive Load (29.4848%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` (Impact: 326.8 | O(N^6) | DB: 26)
  * `locate_physical_package` (Impact: 198.5 | O(N^6) | DB: 6)
  * `__init__` (Impact: 9.2 | O(N^2) | DB: 2)
  * `generate_report` (Impact: 1.8 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 99`, `structural_boundaries: 60`, `args: 4`, `func_start: 4`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 11`, `state_mutation: 31`
* *Architecture:* `io: 13`, `api: 7`, `import: 13`
* *Defense:* `safety: 6`, `doc: 6`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.gitgalaxy_config, datetime, logging, gitgalaxy.standards.language_standards, os, json, re, gitgalaxy.standards.analysis_lens...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.874 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.713 IQR)
- **Top Global Matches:** file_cluster_8: 8.874, file_cluster_16: 9.347, file_cluster_7: 9.459
- **Magnitude:** 526.28 | **LOC:** 2498 | **CtrlFlow:** 76.1% | **Authorship Centralization:** 63.6%
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, os, re, math, statistics, gitgalaxy.standards, typing
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
  * `Imports (Out-Degree: 0):` keyword., path, re, type, inside, java.util.
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 453.92 | **LOC:** 1541 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` pytest, logging, with, re, math, gitgalaxy.core.detector, unittest.mock, gitgalaxy.core.spatial_mapper
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 428.46 | **LOC:** 177 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_parse_requirements_txt` (Impact: 113.2 | O(N^6) | DB: 3)
    * *Intent:* # DEFENSIVE GUARD: Registry Spoofing # If the resolved URL points to a non-standard domain or a dire...
  * `_parse_pip_conf` (Impact: 99.1 | O(N^6) | DB: 3)
  * `_parse_package_json` (Impact: 79.5 | O(N^5) | DB: 3)
  * `_parse_package_lock` (Impact: 55.1 | O(N^5) | DB: 3)
  * `build_resolution_map` (Impact: 53.7 | O(N^5))
    * *Intent:* # Matches standard Python packages, extracting the base name and dropping version constraints (==, >...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` re, logging, pathlib, json
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.14 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.796 IQR)
- **Top Global Matches:** file_cluster_8: 10.14, file_cluster_13: 10.227, file_cluster_7: 10.607
- **Magnitude:** 388.3 | **LOC:** 429 | **CtrlFlow:** 54.5% | **Authorship Centralization:** 57.1%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 13
- **Risk Profile:** Cognitive Load (18.4501%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 129.7 | O(N^4) | DB: 13)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `process_payload` (Impact: 80.2 | O(N^4))
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `record_dead_code` (Impact: 34.5 | O(N^5) | DB: 2)
  * `calibrate_ir_medium` (Impact: 18.9 | O(N^2))
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `get_dead_paras` (Impact: 17.8 | O(N^4) | DB: 2)
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 60`, `structural_boundaries: 50`, `args: 10`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 3`, `state_mutation: 48`
* *Architecture:* `io: 4`, `api: 9`, `import: 16`
* *Defense:* `safety: 4`, `doc: 10`, `cleanup: 3`
* *Network Topology:*
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` sys, datetime, gitgalaxy.tools.cobol_to_cobol.cobol_system_limits_reporter, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge, gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder, sqlite3, gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect, gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge...
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
  * `Imports (Out-Degree: 0):` pytest, gitgalaxy.recorders.sarif_recorder, os, json, gitgalaxy.metrics.signal_processor, tempfile
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.442 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.523 IQR)
- **Top Global Matches:** file_cluster_8: 10.442, file_cluster_13: 10.608, file_cluster_16: 10.825
- **Magnitude:** 344.62 | **LOC:** 432 | **CtrlFlow:** 64.3% | **Authorship Centralization:** 66.7%
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` logging, subprocess, os, time, pathlib, gitgalaxy.standards, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_to_java_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.218 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.092 IQR)
- **Top Global Matches:** file_cluster_8: 8.218, file_cluster_13: 8.838, file_cluster_7: 8.893
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` sys, gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge, org.slf4j.LoggerFactory, org.slf4j.Logger, gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge, gitgalaxy.tools.cobol_to_java.cobol_to_java_service_forge, json, gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/spatial_mapper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 10.563 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.868 IQR)
- **Top Global Matches:** file_cluster_8: 10.563, file_cluster_13: 10.608, file_cluster_16: 10.705
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
  * `Ecosystem Role:` Isolated/Orphan | `Dependency Blast Radius (PageRank):` 6.757
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` hashlib, math, logging, typing
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
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.gitgalaxy_config, logging, gitgalaxy.standards.language_standards, re, time, math, pathlib, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/security_auditing/test_supply_chain_firewall.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 245.28 | **LOC:** 470 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_directory_execution_and_globbing` (Impact: 19.9 | O(N^5))
  * `test_strict_mode_enforcement` (Impact: 19.8 | O(N^6))
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
  * `Imports (Out-Degree: 0):` sys, pytest, gitgalaxy.tools.supply_chain_security.supply_chain_firewall, was, json, policy, pathlib, unittest.mock...
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
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pytest
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
  * `Imports (Out-Degree: 0):` machine, gitgalaxy.standards.language_standards, cats.effect.IO, gitgalaxy.engine, std.core, formatting, java.util.List, java.util....
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
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pytest
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

### `tests/core_engine/test_delta_scanner.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 169.34 | **LOC:** 134 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `simulate_delta_parser` (Impact: 139.5 | O(2^N) | DB: 5)
    * *Intent:* """ A DRY helper method that exactly mirrors the Git Diff parser from galaxyscope.py to test its phy...
  * `test_git_type_mutation_anomaly` (Impact: 3.2 | O(N^2))
  * `test_git_unmerged_conflict_state` (Impact: 3.0 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` unittest.mock, unittest
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 580.02 | Delta: **0.01 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 262, branch: 99, structural_boundaries: 60, state_mutation: 31
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 277.4 | Delta: **0.045 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 153, branch: 34, state_mutation: 32, encapsulation: 23
- `gitgalaxy/core/prism.py` (PYTHON) | Magnitude: 1064.16 | Delta: **0.081 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 452, branch: 133, state_mutation: 96, structural_boundaries: 76
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 388.3 | Delta: **0.087 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 285, branch: 60, structural_boundaries: 50, state_mutation: 48
- `gitgalaxy/metrics/chronometer.py` (PYTHON) | Magnitude: 344.62 | Delta: **0.166 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 300, branch: 72, structural_boundaries: 40, state_mutation: 34

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **69.33%** | Cog Load: 63.3513% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/prism.py` -> **squid-protocol** (85.7% isolated ownership) | Magnitude: 1064.16
- `gitgalaxy/core/network_risk_sensor.py` -> **squid-protocol** (83.3% isolated ownership) | Magnitude: 871.38
- `gitgalaxy/recorders/sbom_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 580.02
- `gitgalaxy/recorders/sarif_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 147.5

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/core/spatial_mapper.py` -> **Severity: 675.7** (Blast Radius: 6.757 * Doc Risk: 100.0%)
- `gitgalaxy/metrics/chronometer.py` -> **Severity: 675.7** (Blast Radius: 6.757 * Doc Risk: 100.0%)
- `gitgalaxy/metrics/tensor_scanner.py` -> **Severity: 675.7** (Blast Radius: 6.757 * Doc Risk: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` -> **Severity: 675.7** (Blast Radius: 6.757 * Doc Risk: 100.0%)
- `templates/bitbucket/bitbucket_insights.py` -> **Severity: 675.621** (Blast Radius: 6.757 * Doc Risk: 99.9883%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Act as a Principal Staff Engineer. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility). DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective, practical, and direct.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
