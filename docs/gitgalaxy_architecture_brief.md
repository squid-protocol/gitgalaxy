# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-07-25T19:29:30.095450+00:00` |
| **Scan Duration** | `6.41s` |
| **Git Branch** | `main` |
| **Git Commit** | `50165ac90a1a21a7163de1341cb8c59e8a73291a` |
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
| Total Artifacts | 624 |
| Analyzed Artifacts (Scanned) | 160 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 464 |
| Total LOC | 42484 |
| Volatility Index | 0.013 |
| % Scanned of codebase = | 25.6% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.6231 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.1676 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 2.853 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 35 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 127 | 42003 | 79.4% |
| MARKDOWN | 22 | 0 | 13.8% |
| YAML | 8 | 481 | 5.0% |
| PLAINTEXT | 3 | 0 | 1.9% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `5.417`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 101 | 63.1% |
| file_cluster_13 | 23 | 14.4% |
| file_cluster_16 | 6 | 3.8% |
| file_cluster_0 | 4 | 2.5% |
| file_cluster_6 | 1 | 0.6% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 25 | 15.6% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 464*

**Composition by Extension & Reason:**
- `.md`: 331x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 63 LOC), 1x Excluded (Machine-Generated Source Code Signature: 34 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.yml`: 17x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 550 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `.json`: 4x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 63.4 | 3.4 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 78.8 | 6.6 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 14.8 | 0.4 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 8.5 | 0.0 | 0.0 |
| API Exposure | 0.0 | 8.1 | 0.3 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 23.5 | 0.5 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 9.9 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 9.8 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 18.2 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 29.5 | 1.0 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 10.4 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 100.0 | 5.3 | 0.0 | 0.0 |
| Algorithmic DoS Exposure | 0.0 | 100.0 | 12.2 | 0.0 | 0.0 |
| Obfuscation & Evasion Surface | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Exploit Generation Surface | 0.0 | 100.0 | 12.9 | 0.0 | 0.0 |
| Weaponizable Injection Vectors | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Raw Memory Manipulation | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `gitgalaxy/core/guidestar_lens.py` (Hits: 8)
- `gitgalaxy/metrics/chronometer.py` (Hits: 8)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These files act as core load-bearing infrastructure. Changes here carry a high risk of cascading breaks.

1. **language_standards.py** (`gitgalaxy/standards/language_standards.py`) — 15 inbound connections
2. **config_resolver.py** (`gitgalaxy/standards/config_resolver.py`) — 9 inbound connections
3. **analysis_lens.py** (`gitgalaxy/standards/analysis_lens.py`) — 7 inbound connections
4. **signal_processor.py** (`gitgalaxy/metrics/signal_processor.py`) — 5 inbound connections
5. **security_auditor.py** (`gitgalaxy/security/security_auditor.py`) — 5 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 56 outbound dependencies
2. **test_dependency_extraction_strict.py** (`tests/extraction/test_dependency_extraction_strict.py`) — 23 outbound dependencies
3. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 20 outbound dependencies
4. **cobol_refractor_controller.py** (`gitgalaxy/cobol_refractor_controller.py`) — 17 outbound dependencies
5. **cobol_to_java_controller.py** (`gitgalaxy/cobol_to_java_controller.py`) — 15 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **2148.3** | LOC: 1622
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **1026.0** | LOC: 361
- `main` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **819.8** | LOC: 391
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> Impact: **688.0** | LOC: 181
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `_process_file_worker` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **611.9** | LOC: 478
- `test_git_null_byte_path_injection` (@ `tests/core_engine/test_galaxyscope.py`) -> Impact: **606.9** | LOC: 1641
  * *Intent:* # Mock Path.exists to pass the initial validation check with patch("gitgalaxy.galaxyscope.Path.exists", return_value=True): try: scope._prepare_target...
- `draw_ascii_histogram` (@ `gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py`) -> Impact: **555.4** | LOC: 197
  * *Intent:* """ Draws a dynamically scaled ASCII histogram. If the dataset is massive, it filters to show only the highest volume spikes to prevent terminal flood...
- `_tier_2_fingerprint_check` (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **533.6** | LOC: 312
  * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents generic files from bypassing deep-inspection. if ex...
- `draw_ascii_histogram` (@ `gitgalaxy/tools/terabyte_log_scanning/pii_leak_hunter.py`) -> Impact: **504.8** | LOC: 155
- `_load_ignored_revs` (@ `gitgalaxy/metrics/chronometer.py`) -> Impact: **447.9** | LOC: 229

## 8.5 ALGORITHMIC & DATABASE BOTTLENECKS
> Highlights the most computationally expensive and database-heavy functions across the repository.

### Highest Time Complexity (Big-O)
- `_load_ignored_revs` (@ `gitgalaxy/metrics/chronometer.py`) -> **O(2^N) [Recursive]**
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> **O(2^N) [Recursive]**
- `main` (@ `gitgalaxy/galaxyscope.py`) -> **O(2^N) [Recursive]**
- `_find_balanced_end` (@ `gitgalaxy/standards/language_lens.py`) -> **O(2^N) [Recursive]**
- `flatten_copybooks` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> **O(2^N) [Recursive]**
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `parse_jcl_intent` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_jcl_auditor.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """Parses a JCL file to extract its raw execution and dataset allocation intent."""
- `resolve_copybooks` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_graveyard_finder.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ Recursively hunts for COBOL 'COPY' statements and injects the contents of the target .cpy file directly into the memory string to ensure accurate ...
- `draw_ascii_histogram` (@ `gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ Draws a dynamically scaled ASCII histogram. If the dataset is massive, it filters to show only the highest volume spikes to prevent terminal flood...
- `draw_ascii_histogram` (@ `gitgalaxy/tools/terabyte_log_scanning/pii_leak_hunter.py`) -> **O(2^N) [Recursive]**

### Highest Data Gravity (Database Complexity)
- `test_git_null_byte_path_injection` (@ `tests/core_engine/test_galaxyscope.py`) -> DB Complexity: **111**
  * *Intent:* # Mock Path.exists to pass the initial validation check with patch("gitgalaxy.galaxyscope.Path.exists", return_value=True): try: scope._prepare_target...
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **52**
- `publish_insights` (@ `templates/bitbucket/bitbucket_insights.py`) -> DB Complexity: **43**
- `draw_ascii_histogram` (@ `gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py`) -> DB Complexity: **39**
  * *Intent:* """ Draws a dynamically scaled ASCII histogram. If the dataset is massive, it filters to show only the highest volume spikes to prevent terminal flood...
- `generate_build_jcl` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> DB Complexity: **34**
- `generate_rest_controller` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py`) -> DB Complexity: **34**
  * *Intent:* """Generates the API endpoints and auto-wires the Service layer."""
- `generate_java_entity` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py`) -> DB Complexity: **31**
- `slice_manifest` (@ `gitgalaxy/security/manifest_parser.py`) -> DB Complexity: **26**
  * *Intent:* # NEW: # Filenames UniversalManifestSlicer.slice_manifest() below knows how to parse # into an actual dependency list. This is the single source of tr...
- `main` (@ `gitgalaxy/tools/network_auditing/full_api_network_map.py`) -> DB Complexity: **26**
- `main` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **23**

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `gitgalaxy` | 6 | 4607.48 | 11.0% | 0.0% |
| `gitgalaxy/metrics` | 5 | 3148.58 | 16.84% | 2.97% |
| `tests/core_engine` | 17 | 2541.02 | 2.7% | 0.0% |
| `gitgalaxy/core` | 9 | 2290.16 | 13.94% | 3.41% |
| `gitgalaxy/standards` | 8 | 2034.16 | 7.81% | 10.18% |
| `gitgalaxy/recorders` | 8 | 1555.6 | 21.51% | 1.79% |
| `tests/security_auditing` | 16 | 1420.2 | 1.93% | 0.0% |
| `tests/extraction` | 5 | 1373.14 | 2.93% | 0.0% |
| `gitgalaxy/security` | 5 | 1302.74 | 12.52% | 0.0% |
| `tests` | 6 | 783.98 | 7.98% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `gitgalaxy/metrics/chronometer.py` -> **14.8284%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **14.3599%** Exposure
- `gitgalaxy/core/prism.py` -> **12.3056%** Exposure
- `gitgalaxy/core/network_risk_sensor.py` -> **10.3095%** Exposure
- `gitgalaxy/core/detector.py` -> **8.0967%** Exposure
### Highest State Flux (Mutation/Volatility)
- `gitgalaxy/recorders/llm_recorder.py` -> **100.0%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **99.9986%** Exposure
- `gitgalaxy/core/prism.py` -> **99.9538%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **99.804%** Exposure
- `gitgalaxy/metrics/statistical_auditor.py` -> **99.2406%** Exposure

## 10.5 AI THREAT INTELLIGENCE (XGBoost)
*No files met the threshold for malicious structural signatures.*

## 10.6 WEAPONIZABLE SURFACE EXPOSURES (RULE-BASED SAST)
> Secondary Evidence: The following files tripped specific static threat signatures. Use these to explain *why* the XGBoost model flagged the files above.

### Exploit Generation Surface
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/prism.py` -> **100.0%** Exposure
- `gitgalaxy/core/spatial_correlation.py` -> **100.0%** Exposure
### Algorithmic DoS Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/prism.py` -> **100.0%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **100.0%** Exposure

## 10.7 AUTONOMOUS AI VULNERABILITIES (AGENTIC RCE & PROMPT INJECTION)
> **AI CONTEXT:** Identifies untrusted data flowing into LLM context windows (Prompt Injection) and LLM outputs flowing into dynamic execution (Agentic RCE).

*No autonomous AI vulnerabilities detected.*

## 10.8 ECOSYSTEM SECURITY AUDITS
> **AI CONTEXT:** High-level perimeter defense metrics from the X-Ray, Supply Chain Firewall, and API Network Mapper.

### ☢️ X-Ray & 🧱 Supply Chain Firewall
- **Binary Anomalies (X-Ray):** `0` (High entropy, packed payloads, or magic byte mismatches).
- **Blacklisted Dependencies:** `0` explicitly banned packages imported.
- **Unknown Dependencies:** `767` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/spatial_mapper.py` (PYTHON) -> Cumulative Risk: **736.92**
- **Archetype:** `file_cluster_13` (Distance: 11.387 IQR)
- **Magnitude:** 257.28 | **LOC:** 233 | **CtrlFlow:** 61.7% | **Authorship Centralization:** 44.4%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.804%)
- **Heaviest Functions:** `map_repository` (Impact: 189.4), `__init__` (Impact: 11.5), `_hash_jitter` (Impact: 8.4)

### 2. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **684.15**
- **Archetype:** `file_cluster_8` (Distance: 11.204 IQR)
- **Magnitude:** 1175.2 | **LOC:** 536 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 57.1%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.2406%)
- **Heaviest Functions:** `audit` (Impact: 1026.0), `_is_dead_code` (Impact: 26.1), `_is_threat` (Impact: 25.9)

### 3. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **679.1**
- **Archetype:** `file_cluster_8` (Distance: 12.58 IQR)
- **Magnitude:** 3819.16 | **LOC:** 2990 | **CtrlFlow:** 71.2% | **Authorship Centralization:** 61.9%
- **Primary Risk Drivers:** Spec Match (100.0%), Churn (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `execute_pipeline` (Impact: 2148.3), `main` (Impact: 819.8), `_process_file_worker` (Impact: 611.9)

### 4. `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` (PYTHON) -> Cumulative Risk: **667.08**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.37 | **LOC:** 214 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `flatten_copybooks` (Impact: 184.3), `generate_build_jcl` (Impact: 34.5), `main` (Impact: 23.0)

### 5. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **659.83**
- **Archetype:** `file_cluster_13` (Distance: 10.971 IQR)
- **Magnitude:** 474.42 | **LOC:** 434 | **CtrlFlow:** 50.0% | **Authorship Centralization:** 55.6%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (98.0037%)
- **Heaviest Functions:** `main` (Impact: 225.2), `process_payload` (Impact: 59.8), `record_dead_code` (Impact: 41.2)

### 6. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **655.38**
- **Archetype:** `file_cluster_16` (Distance: 11.839 IQR)
- **Magnitude:** 757.26 | **LOC:** 663 | **CtrlFlow:** 61.5% | **Authorship Centralization:** 50.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.9538%)
- **Heaviest Functions:** `_compile_regex_matrix` (Impact: 321.3), `split_streams` (Impact: 125.2), `_strip_nested_comments` (Impact: 109.7)

### 7. `gitgalaxy/metrics/chronometer.py` (PYTHON) -> Cumulative Risk: **645.07**
- **Archetype:** `file_cluster_8` (Distance: 11.61 IQR)
- **Magnitude:** 637.92 | **LOC:** 448 | **CtrlFlow:** 62.6% | **Authorship Centralization:** 54.5%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (94.5995%)
- **Heaviest Functions:** `_load_ignored_revs` (Impact: 447.9), `_initialize_history_scan` (Impact: 144.9), `__init__` (Impact: 1.8)

### 8. `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) -> Cumulative Risk: **638.44**
- **Archetype:** `file_cluster_13` (Distance: 10.558 IQR)
- **Magnitude:** 283.6 | **LOC:** 360 | **CtrlFlow:** 51.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (96.3267%)
- **Heaviest Functions:** `_audit_capped_sample` (Impact: 176.9), `_iter_candidate_files` (Impact: 32.0), `_scan_single_file` (Impact: 29.2)

### 9. `gitgalaxy/recorders/sarif_recorder.py` (PYTHON) -> Cumulative Risk: **630.51**
- **Archetype:** `file_cluster_8` (Distance: 9.889 IQR)
- **Magnitude:** 136.72 | **LOC:** 222 | **CtrlFlow:** 67.3% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (99.9929%), Logic Bomb (99.99%), State Flux (89.8285%)
- **Heaviest Functions:** `_build_rules_taxonomy` (Impact: 58.3), `_build_dependency_notifications` (Impact: 34.3), `__init__` (Impact: 9.2)

### 10. `gitgalaxy/metrics/tensor_scanner.py` (PYTHON) -> Cumulative Risk: **621.32**
- **Archetype:** `file_cluster_13` (Distance: 9.505 IQR)
- **Magnitude:** 145.84 | **LOC:** 160 | **CtrlFlow:** 48.1% | **Authorship Centralization:** 60.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (99.9999%), Logic Bomb (99.4575%)
- **Heaviest Functions:** `_parse_gguf` (Impact: 54.1), `_parse_safetensors` (Impact: 33.6), `audit_model` (Impact: 27.1)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 12.58 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.571 IQR)
- **Top Global Matches:** file_cluster_8: 12.58, file_cluster_13: 12.696, file_cluster_7: 12.963
- **Magnitude:** 3819.16 | **LOC:** 2990 | **CtrlFlow:** 71.2% | **Authorship Centralization:** 61.9%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 52
- **Risk Profile:** Cognitive Load (34.0548%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `execute_pipeline` (Impact: 2148.3 | O(N^6) | DB: 52)
  * `main` (Impact: 819.8 | O(2^N) | DB: 23)
  * `_process_file_worker` (Impact: 611.9 | O(N^6) | DB: 13)
  * `execution_timeout_failsafe` (Impact: 1.9 | O(N^1))
    * *Intent:* """ Hardware-level OS interrupt for Catastrophic Backtracking (ReDoS) protection. Registered via the...
  * `execute_incremental_scan` (Impact: 1.9 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 521`, `structural_boundaries: 211`, `args: 32`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 77`, `state_mutation: 184`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 3`, `import: 65`
* *Defense:* `safety: 72`, `doc: 36`, `test: 1`, `cleanup: 6`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 8.507
  * `Choke Point (Betweenness):` 0.003423 | `Ripple Effect (Closeness):` 0.018868
  * `Imports (Out-Degree: 30):` concurrent.futures, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics.chronometer, gitgalaxy.tools.network_auditing.full_api_network_map, pathlib, gitgalaxy.metrics.signal_processor, gitgalaxy.standards.analysis_lens, graphs...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.173 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.756 IQR)
- **Top Global Matches:** file_cluster_8: 11.173, file_cluster_16: 11.526, file_cluster_7: 11.629
- **Magnitude:** 1179.1 | **LOC:** 2489 | **CtrlFlow:** 76.1% | **Authorship Centralization:** 65.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (16.5924%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_forensic_report` (Impact: 287.1 | O(N^6) | DB: 3)
  * `_calc_injection_surface` (Impact: 109.5 | O(N^4))
  * `_rank_list` (Impact: 75.5 | O(N^5))
  * `_calc_safety` (Impact: 65.6 | O(N^4))
  * `_calc_secrets_risk` (Impact: 61.0 | O(N^3))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 443`, `structural_boundaries: 139`, `args: 44`, `func_start: 36`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 44`, `state_mutation: 92`
* *Architecture:* `io: 1`, `api: 12`, `concurrency: 2`, `import: 8`
* *Defense:* `safety: 72`, `doc: 50`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 10.878
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.036592
  * `Imports (Out-Degree: 0):` statistics, typing, logging, gitgalaxy.standards, math, os, re
  * `Imported By (In-Degree: 5):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.204 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.352 IQR)
- **Top Global Matches:** file_cluster_8: 11.204, file_cluster_16: 11.375, file_cluster_13: 11.429
- **Magnitude:** 1175.2 | **LOC:** 536 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 57.1%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 22
- **Risk Profile:** Cognitive Load (39.0051%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit` (Impact: 1026.0 | O(2^N) | DB: 22)
  * `_is_dead_code` (Impact: 26.1 | O(N^4))
  * `_is_threat` (Impact: 25.9 | O(N^4))
    * *Intent:* # Preserve Phase 1 Telemetry for SBOM Traceability "failed_claim": artifact.get("lang_id", "unknown"...
  * `_is_highly_blended` (Impact: 20.7 | O(N^4))
  * `_format_for_exclusion` (Impact: 5.2 | O(N^3))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 85`, `structural_boundaries: 36`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 26`, `state_mutation: 60`
* *Architecture:* `io: 2`, `api: 3`, `import: 5`
* *Defense:* `safety: 9`, `doc: 14`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.143
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019654
  * `Imports (Out-Degree: 0):` statistics, typing, logging, os, math
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 1113.08 | **LOC:** 1136 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_tier_2_fingerprint_check` (Impact: 533.6 | O(N^6) | DB: 1)
    * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents g...
  * `_find_balanced_end` (Impact: 398.9 | O(2^N) | DB: 2)
  * `_calibrate_lookup_maps` (Impact: 73.8 | O(N^6))
  * `_tier_1_metadata_lock` (Impact: 16.6 | O(N^3))
  * `_capture_raw_signal` (Impact: 15.4 | O(N^4) | DB: 3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, gitgalaxy.standards.gitgalaxy_config, pathlib, logging, math, time, re, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/test_dependency_extraction_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 938.32 | **LOC:** 463 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` std.core, type, UIKit, url, java.util., numpy, mypack.myclass, os...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.044 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.188 IQR)
- **Top Global Matches:** file_cluster_8: 11.044, file_cluster_16: 11.352, file_cluster_7: 11.444
- **Magnitude:** 860.98 | **LOC:** 2295 | **CtrlFlow:** 73.9% | **Authorship Centralization:** 53.8%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (13.3127%), Tech Debt (8.0967%)
**Top Internal Functions/Classes:**
  * `_decode_comment_stream` (Impact: 338.7 | O(N^6) | DB: 3)
  * `_extract_documentation_tether` (Impact: 142.3 | O(N^6) | DB: 3)
  * `_classify_function` (Impact: 124.5 | O(N^4))
  * `_extract_name` (Impact: 96.6 | O(N^5))
  * `index_aligned_shield` (Impact: 14.0 | O(N^3))
    * *Intent:* """The Master Routing Dispatcher: Directs the structural signal into the correct integration mode.""...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 413`, `structural_boundaries: 146`, `args: 21`, `func_start: 20`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 54`, `state_mutation: 86`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `api: 14`, `concurrency: 1`, `import: 11`
* *Defense:* `safety: 39`, `doc: 65`, `test: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 7.235
  * `Choke Point (Betweenness):` 0.000212 | `Ripple Effect (Closeness):` 0.025157
  * `Imports (Out-Degree: 3):` typing, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens, logging, bisect, math, time, re...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 13.369 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.036 IQR)
- **Top Global Matches:** file_cluster_8: 13.369, file_cluster_13: 13.662, file_cluster_11: 13.702
- **Magnitude:** 815.88 | **LOC:** 1507 | **CtrlFlow:** 87.5% | **Authorship Centralization:** 58.8%
- **Algorithmic:** O(N^3) | **DB Complexity:** 4
- **Risk Profile:** Cognitive Load (63.3646%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 11.0 | O(N^3) | DB: 4)
  * `_parse_threat_score` (Impact: 7.3 | O(N^3))
  * `generate_artifacts` (Impact: 1.9 | O(N^2))
  * `_build_markdown` (Impact: 1.9 | O(N^2))
  * `_generate_sqlite_graph` (Impact: 1.9 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 323`, `structural_boundaries: 46`, `args: 31`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 753`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 13`, `doc: 26`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.143
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019654
  * `Imports (Out-Degree: 0):` sqlite3, statistics, typing, pathlib, json, logging, gitgalaxy.standards, collections...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 772.2 | **LOC:** 2019 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_git_null_byte_path_injection` (Impact: 606.9 | O(N^5) | DB: 111)
    * *Intent:* # Mock Path.exists to pass the initial validation check with patch("gitgalaxy.galaxyscope.Path.exist...
  * `test_cicd_policy_enforcement_gates` (Impact: 31.9 | O(N^5))
    * *Intent:* # ============================================================================== # =================...
  * `test_orchestrator_zip_bomb_rejection` (Impact: 16.4 | O(N^4))
  * `test_empty_galaxy_survival` (Impact: 9.1 | O(N^3))
    * *Intent:* # ============================================================================== # TEST 3: THE EMPTY...
  * `setUp` (Impact: 4.0 | O(N^3) | DB: 1)
    * *Intent:* """Creates a dummy configuration for the Orchestrator."""
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` concurrent.futures, pathlib, gitgalaxy.standards.analysis_lens, failure, subprocess, os, gitgalaxy.standards, tempfile...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_16` (Drift: 11.839 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.159 IQR)
- **Top Global Matches:** file_cluster_16: 11.839, file_cluster_8: 11.905, file_cluster_13: 12.103
- **Magnitude:** 757.26 | **LOC:** 663 | **CtrlFlow:** 61.5% | **Authorship Centralization:** 50.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 8
- **Risk Profile:** Cognitive Load (27.7039%), Tech Debt (12.3056%)
**Top Internal Functions/Classes:**
  * `_compile_regex_matrix` (Impact: 321.3 | O(N^6) | DB: 6)
    * *Intent:* # 4. GENERIC STRIPPER pattern = self.REGEX_MATRIX.get(family) if not pattern: # Restore mask tokens ...
  * `split_streams` (Impact: 125.2 | O(N^5) | DB: 3)
    * *Intent:* # Phase 6.1 Handshake Registry (Synchronized securely via Language Standards)
  * `_strip_nested_comments` (Impact: 109.7 | O(N^4) | DB: 8)
  * `_strip_segment_comments` (Impact: 59.1 | O(N^4) | DB: 7)
    * *Intent:* # 3. Derive the documentation lines by subtracting code from the active total. # This forces mutual ...
  * `_strip_single_line_comments` (Impact: 26.7 | O(N^4) | DB: 3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 110`, `structural_boundaries: 69`, `args: 23`, `func_start: 19`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 94`, `fragile_debt: 1`
* *Architecture:* `api: 12`, `import: 4`
* *Defense:* `safety: 4`, `doc: 32`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 5.723
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019654
  * `Imports (Out-Degree: 1):` gitgalaxy.standards.language_standards, re, typing, logging
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 676.86 | **LOC:** 393 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` (Impact: 299.1 | O(N^6) | DB: 26)
    * *Intent:* # NEW: # Filenames UniversalManifestSlicer.slice_manifest() below knows how to parse # into an actua...
  * `_parse_package_lock` (Impact: 142.3 | O(N^6) | DB: 6)
  * `_parse_pip_conf` (Impact: 71.1 | O(N^6) | DB: 3)
  * `_parse_package_json` (Impact: 67.5 | O(N^5) | DB: 3)
  * `build_resolution_map` (Impact: 48.5 | O(N^5))
    * *Intent:* # Matches standard Python packages, extracting the base name and dropping version constraints (==, >...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, pathlib, json, logging, os, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.61 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.901 IQR)
- **Top Global Matches:** file_cluster_8: 11.61, file_cluster_13: 11.641, file_cluster_16: 11.883
- **Magnitude:** 637.92 | **LOC:** 448 | **CtrlFlow:** 62.6% | **Authorship Centralization:** 54.5%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 14
- **Risk Profile:** Cognitive Load (14.3523%), Tech Debt (14.8284%)
**Top Internal Functions/Classes:**
  * `_load_ignored_revs` (Impact: 447.9 | O(2^N) | DB: 12)
  * `_initialize_history_scan` (Impact: 144.9 | O(N^6) | DB: 14)
  * `__init__` (Impact: 1.8 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 62`, `structural_boundaries: 37`, `args: 8`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `high_risk_execution: 1`, `state_mutation: 35`, `fragile_debt: 1`
* *Architecture:* `io: 8`, `api: 3`, `import: 7`
* *Defense:* `safety: 17`, `doc: 18`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 8.143
  * `Choke Point (Betweenness):` 4e-05 | `Ripple Effect (Closeness):` 0.019654
  * `Imports (Out-Degree: 1):` typing, pathlib, gitgalaxy.standards.config_resolver, logging, os, gitgalaxy.standards, time, subprocess
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 527.56 | **LOC:** 419 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` (Impact: 162.7 | O(N^6) | DB: 3)
  * `audit_repository` (Impact: 124.5 | O(N^6))
  * `__init__` (Impact: 100.2 | O(N^6) | DB: 8)
  * `_construct_feature_matrix` (Impact: 90.4 | O(N^6) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` numpy, pathlib, gitgalaxy.standards.analysis_lens, logging, collections, pandas, networkx, xgboost
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 10.971 IQR)
- **Local Micro-Species:** `Cluster 3: Data Pipelines & I/O Operations` (Drift: 5.129 IQR)
- **Top Global Matches:** file_cluster_13: 10.971, file_cluster_8: 11.078, file_cluster_7: 11.472
- **Magnitude:** 474.42 | **LOC:** 434 | **CtrlFlow:** 50.0% | **Authorship Centralization:** 55.6%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 12
- **Risk Profile:** Cognitive Load (19.4865%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 225.2 | O(2^N) | DB: 12)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `process_payload` (Impact: 59.8 | O(N^4))
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `record_dead_code` (Impact: 41.2 | O(N^5) | DB: 2)
  * `get_dead_paras` (Impact: 22.2 | O(N^4) | DB: 2)
  * `get_orphaned_vars` (Impact: 22.2 | O(N^4) | DB: 2)
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 54`, `structural_boundaries: 54`, `args: 10`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 5`, `state_mutation: 45`
* *Architecture:* `io: 4`, `api: 9`, `import: 18`
* *Defense:* `safety: 4`, `doc: 10`, `cleanup: 3`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 7.902
  * `Choke Point (Betweenness):` 0.000358 | `Ripple Effect (Closeness):` 0.006289
  * `Imports (Out-Degree: 9):` gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect, sqlite3, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge, gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor, argparse, gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge, typing...
  * `Imported By (In-Degree: 1):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 425.6 | **LOC:** 1785 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_detector_prose_and_empty_bypass` (Impact: 36.3 | O(N^3))
  * `test_detector_c_macro_dead_branch_shield` (Impact: 29.4 | O(N^2))
  * `test_detector_exfiltration_check_does_no` (Impact: 28.5 | O(N^3) | DB: 8)
  * `test_spatial_mapper_sectorization_and_mo` (Impact: 27.2 | O(N^2))
    * *Intent:* # 2. TimeoutError -> Hardware Guillotine drops cleanly with patch.object( opt_detector, "_partition_...
  * `calculate_fibonacci` (Impact: 22.1 | O(2^N))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, unittest.mock, logging, math, gitgalaxy.core.detector, with, re, gitgalaxy.core.spatial_mapper
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/dead_key_audit.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 391.26 | **LOC:** 376 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `visit_Call` (Impact: 104.3 | O(N^6))
    * *Intent:* """ if not isinstance(node, ast.JoinedStr) or not node.values: return None first = node.values[0] if...
  * `run_ci_check` (Impact: 78.3 | O(2^N))
  * `visit_Subscript` (Impact: 26.6 | O(N^4))
    * *Intent:* # signal_processor.py._get_locational_multipliers() writes # active_multipliers[signal_key] = multip...
  * `find_dead_keys` (Impact: 21.4 | O(N^3))
  * `iter_python_files` (Impact: 20.3 | O(N^4))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, argparse, pathlib, json, ast, sys
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/config_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 357.14 | **LOC:** 316 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_load_yaml_section` (Impact: 206.7 | O(2^N) | DB: 3)
    * *Intent:* # Shouldn't happen for real gitgalaxy_config.py values, but degrade
  * `_merge_value` (Impact: 74.6 | O(N^5))
  * `_get_default` (Impact: 20.4 | O(N^3))
  * `_merge_collection` (Impact: 18.9 | O(N^2) | DB: 1)
    * *Intent:* # `_values` itself -- safe against recursion. try: return self._values[name] except KeyError as exc:...
  * `__getattr__` (Impact: 7.3 | O(N^3))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, logging, gitgalaxy.standards, yaml, dataclasses, copy, __future__
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 356.6 | **LOC:** 1708 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_sarif_exact_loc_injection` (Impact: 19.4 | O(N^4) | DB: 10)
  * `test_signal_processor_report_fallback` (Impact: 11.8 | O(N^3))
    * *Intent:* # Should execute smoothly without raising a KeyError, TypeError, or IndexError report = processor.ge...
  * `test_signal_processor_math_overflow_shie` (Impact: 11.1 | O(N^3))
  * `test_signal_processor_doc_and_secrets_ch` (Impact: 9.0 | O(N^3) | DB: 2)
  * `test_signal_processor_zero_division_shie` (Impact: 8.4 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, gitgalaxy.metrics.signal_processor, json, which, os, tempfile, gitgalaxy.recorders.sarif_recorder, identity
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_standards.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 356.42 | **LOC:** 10573 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` typing, path, java.util., type, re, keyword., inside
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_to_java_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.79 IQR)
- **Local Micro-Species:** `Cluster 3: Data Pipelines & I/O Operations` (Drift: 5.187 IQR)
- **Top Global Matches:** file_cluster_8: 8.79, file_cluster_13: 9.242, file_cluster_7: 9.388
- **Magnitude:** 298.58 | **LOC:** 336 | **CtrlFlow:** 55.3% | **Authorship Centralization:** 60.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 6
- **Risk Profile:** Cognitive Load (7.4886%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 265.3 | O(N^6) | DB: 6)
    * *Intent:* /**
  * `build_spring_boot_scaffold` (Impact: 11.6 | O(N^3))
    * *Intent:* """Creates the standard Spring Boot directory architecture."""
  * `format_java_header` (Impact: 9.6 | O(N^2))
  * `generate_mock_service` (Impact: 3.7 | O(N^1))
**Contextual Mitigations & Amplifications:**
* *Sec Io:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 47`, `structural_boundaries: 38`, `args: 4`, `func_start: 4`
* *Risk/State:* `safety_bypasses: 3`
* *Architecture:* `io: 3`, `api: 4`, `import: 12`
* *Defense:* `safety: 6`, `doc: 8`, `test: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 4.271
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 6):` gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge, argparse, pathlib, gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge, json, gitgalaxy.licensing, org.springframework.stereotype.Service, sys...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 10.558 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.406 IQR)
- **Top Global Matches:** file_cluster_13: 10.558, file_cluster_8: 10.616, file_cluster_16: 10.968
- **Magnitude:** 283.6 | **LOC:** 360 | **CtrlFlow:** 51.9% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 6
- **Risk Profile:** Cognitive Load (18.2286%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_audit_capped_sample` (Impact: 176.9 | O(N^6) | DB: 6)
  * `_iter_candidate_files` (Impact: 32.0 | O(N^5) | DB: 4)
    * *Intent:* # Filenames that typically execute on import/install — the highest-value # audit targets, since real...
  * `_scan_single_file` (Impact: 29.2 | O(N^4) | DB: 5)
  * `generate_report` (Impact: 1.9 | O(N^2))
    * *Intent:* # Max cache-MISS files freshly scanned per package per run (None = # unlimited). Hashing always cove...
  * `__init__` (Impact: 1.8 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 54`, `structural_boundaries: 50`, `args: 7`, `func_start: 7`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 12`, `state_mutation: 34`
* *Architecture:* `io: 5`, `api: 3`, `import: 12`
* *Defense:* `safety: 4`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 9.958
  * `Choke Point (Betweenness):` 0.000318 | `Ripple Effect (Closeness):` 0.025157
  * `Imports (Out-Degree: 4):` typing, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.security.manifest_parser, gitgalaxy.standards.language_lens, pathlib, json, logging, os...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/security_auditing/test_supply_chain_firewall.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 274.48 | **LOC:** 673 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_strict_mode_enforcement` (Impact: 110.1 | O(N^6) | DB: 6)
    * *Intent:* # Simulate an npm alias: "safe-utils": "npm:malicious-core@1.0" # Namespaced to the current director...
  * `test_network_weighting_disabled_by_defau` (Impact: 48.4 | O(N^6) | DB: 3)
  * `test_density_dilution_fix_for_build_scri` (Impact: 19.3 | O(N^6))
  * `test_memory_corruption_detection` (Impact: 19.3 | O(N^6))
  * `test_directory_group_schema_parsing` (Impact: 17.0 | O(N^5))
    * *Intent:* # ============================================================================== # TEST 13: ISSUES #...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` pytest, pathlib, gitgalaxy.metrics.signal_processor, json, unittest.mock, gitgalaxy.standards.config_resolver, was, gitgalaxy.tools.supply_chain_security.supply_chain_firewall...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/spatial_mapper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 11.387 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.224 IQR)
- **Top Global Matches:** file_cluster_13: 11.387, file_cluster_16: 11.434, file_cluster_8: 11.498
- **Magnitude:** 257.28 | **LOC:** 233 | **CtrlFlow:** 61.7% | **Authorship Centralization:** 44.4%
- **Algorithmic:** O(N^6) | **DB Complexity:** 9
- **Risk Profile:** Cognitive Load (31.5879%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `map_repository` (Impact: 189.4 | O(N^6) | DB: 7)
  * `__init__` (Impact: 11.5 | O(N^3) | DB: 9)
  * `_hash_jitter` (Impact: 8.4 | O(N^3))
  * `_get_magnitude` (Impact: 8.3 | O(N^3))
  * `_calculate_spatial_clearance` (Impact: 2.9 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 29`, `structural_boundaries: 18`, `args: 6`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 9`, `state_mutation: 30`, `dead_code: 1`
* *Architecture:* `api: 4`, `import: 4`
* *Defense:* `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 6.328
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019654
  * `Imports (Out-Degree: 0):` typing, logging, math, hashlib
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.026 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.919 IQR)
- **Top Global Matches:** file_cluster_8: 11.026, file_cluster_13: 11.165, file_cluster_16: 11.329
- **Magnitude:** 252.3 | **LOC:** 511 | **CtrlFlow:** 62.9% | **Authorship Centralization:** 54.5%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (11.9704%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_calculate_documentation_coverage` (Impact: 87.5 | O(N^6) | DB: 3)
    * *Intent:* # galaxyscope:ignore sec_io, llm_hooks # DOCUMENTATION COVERAGE MAP # ==============================...
  * `_scan_gitattributes` (Impact: 68.9 | O(N^6) | DB: 3)
  * `_scan_gitignore_evasion` (Impact: 50.2 | O(N^6) | DB: 3)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `_extract_execution_triggers` (Impact: 13.8 | O(N^4))
**Contextual Mitigations & Amplifications:**
* *Sec Io:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 90`, `structural_boundaries: 53`, `args: 15`, `func_start: 15`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 18`, `state_mutation: 22`
* *Architecture:* `io: 8`, `api: 4`, `import: 8`
* *Defense:* `safety: 16`, `doc: 32`, `sync_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 8.143
  * `Choke Point (Betweenness):` 4e-05 | `Ripple Effect (Closeness):` 0.019654
  * `Imports (Out-Degree: 1):` typing, gitgalaxy.standards.gitgalaxy_config, pathlib, json, logging, os, fnmatch, re
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/extraction/test_function_extraction_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 212.54 | **LOC:** 549 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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

### `templates/bitbucket/bitbucket_insights.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 204.26 | **LOC:** 139 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `publish_insights` (Impact: 198.3 | O(2^N) | DB: 43)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` urllib.error, json, os, sys, urllib.request
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_13
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 257.28 | Delta: **0.047 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 134, state_mutation: 30, branch: 29, encapsulation: 23
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 283.6 | Delta: **0.058 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 227, branch: 54, structural_boundaries: 50, state_mutation: 34
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 474.42 | Delta: **0.107 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 54, structural_boundaries: 54, state_mutation: 45
- `gitgalaxy/metrics/tensor_scanner.py` (PYTHON) | Magnitude: 145.84 | Delta: **0.112 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 80, structural_boundaries: 27, branch: 25, doc: 10

### Mixed-Responsibility Refactoring Targets for: file_cluster_16
- `gitgalaxy/core/prism.py` (PYTHON) | Magnitude: 757.26 | Delta: **0.066 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 365, branch: 110, state_mutation: 94, structural_boundaries: 69
- `gitgalaxy/core/spatial_correlation.py` (PYTHON) | Magnitude: 62.4 | Delta: **0.184 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 133, branch: 32, generics: 27, structural_boundaries: 17

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/metrics/chronometer.py` (PYTHON) | Magnitude: 637.92 | Delta: **0.031 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 258, branch: 62, structural_boundaries: 37, state_mutation: 35
- `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) | Magnitude: 144.5 | Delta: **0.101 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 272, state_mutation: 95, branch: 41, explicit_casts: 33
- `gitgalaxy/galaxyscope.py` (PYTHON) | Magnitude: 3819.16 | Delta: **0.116 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 1899, branch: 521, structural_boundaries: 211, state_mutation: 184
- `gitgalaxy/core/guidestar_lens.py` (PYTHON) | Magnitude: 252.3 | Delta: **0.139 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 286, branch: 90, structural_boundaries: 53, encapsulation: 41
- `gitgalaxy/core/network_risk_sensor.py` (PYTHON) | Magnitude: 64.34 | Delta: **0.146 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 287, branch: 113, structural_boundaries: 45, safety_bypasses: 29

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **69.5%** | Cog Load: 63.3646% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/recorders/sbom_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 283.6
- `gitgalaxy/recorders/sarif_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 136.72
- `gitgalaxy/core/spatial_correlation.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 62.4

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/galaxyscope.py` -> **Severity: 0.272** (Bridge: 0.0034 * Flux: 79.5587%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.035** (Bridge: 0.0004 * Flux: 98.0037%)
- `gitgalaxy/recorders/sbom_recorder.py` -> **Severity: 0.031** (Bridge: 0.0003 * Flux: 96.3267%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.011** (Bridge: 0.0002 * Flux: 50.8203%)
- `gitgalaxy/security/security_auditor.py` -> **Severity: 0.009** (Bridge: 0.0001 * Flux: 95.3321%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 5.391** (Embedded: 0.0674 * Error Risk: 80.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 2.429** (Embedded: 0.0308 * Error Risk: 78.8215%)
- `gitgalaxy/recorders/sarif_recorder.py` -> **Severity: 1.588** (Embedded: 0.0252 * Error Risk: 63.1325%)
- `gitgalaxy/recorders/llm_recorder.py` -> **Severity: 1.526** (Embedded: 0.0197 * Error Risk: 77.6388%)
- `gitgalaxy/tools/ai_guardrails/ai_appsec_sensor.py` -> **Severity: 1.526** (Embedded: 0.0197 * Error Risk: 77.619%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 1961.553** (Blast Radius: 33.494 * Doc Risk: 58.5643%)
- `gitgalaxy/metrics/tensor_scanner.py` -> **Severity: 814.3** (Blast Radius: 8.143 * Doc Risk: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` -> **Severity: 790.2** (Blast Radius: 7.902 * Doc Risk: 100.0%)
- `gitgalaxy/tools/network_auditing/full_api_network_map.py` -> **Severity: 772.669** (Blast Radius: 8.143 * Doc Risk: 94.8875%)
- `gitgalaxy/standards/language_standards.py` -> **Severity: 752.808** (Blast Radius: 47.989 * Doc Risk: 15.6871%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Act as a Principal Staff Engineer. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility). DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective, practical, and direct.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
