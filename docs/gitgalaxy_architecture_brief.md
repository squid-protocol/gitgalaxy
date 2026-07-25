# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-07-25T20:30:13.434532+00:00` |
| **Scan Duration** | `4.61s` |
| **Git Branch** | `main` |
| **Git Commit** | `f1cacf038cadb7c271d5d94d4f88d2ea99ab41af` |
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
| Total Artifacts | 627 |
| Analyzed Artifacts (Scanned) | 161 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 466 |
| Total LOC | 42721 |
| Volatility Index | 0.012 |
| % Scanned of codebase = | 25.7% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.6242 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.1676 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 2.853 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 35 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 128 | 42240 | 79.5% |
| MARKDOWN | 22 | 0 | 13.7% |
| YAML | 8 | 481 | 5.0% |
| PLAINTEXT | 3 | 0 | 1.9% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `5.436`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 102 | 63.4% |
| file_cluster_13 | 23 | 14.3% |
| file_cluster_16 | 6 | 3.7% |
| file_cluster_0 | 4 | 2.5% |
| file_cluster_6 | 1 | 0.6% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 25 | 15.5% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 466*

**Composition by Extension & Reason:**
- `.md`: 331x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 63 LOC), 1x Excluded (Machine-Generated Source Code Signature: 34 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.yml`: 18x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 551 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `.json`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 63.3 | 3.4 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 80.0 | 6.6 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 14.8 | 0.4 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 9.0 | 0.0 | 0.0 |
| API Exposure | 0.0 | 8.1 | 0.3 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 23.5 | 0.5 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 9.8 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 9.7 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 18.0 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 29.6 | 0.7 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 10.7 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 100.0 | 5.4 | 0.0 | 0.0 |
| Algorithmic DoS Exposure | 0.0 | 100.0 | 12.1 | 0.0 | 0.0 |
| Obfuscation & Evasion Surface | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Exploit Generation Surface | 0.0 | 100.0 | 13.5 | 0.0 | 0.0 |
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

- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **2143.0** | LOC: 1638
- `_resolve_target` (@ `gitgalaxy/core/network_risk_sensor.py`) -> Impact: **1785.9** | LOC: 396
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **1026.0** | LOC: 361
- `main` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **869.5** | LOC: 415
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> Impact: **688.0** | LOC: 181
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `_process_file_worker` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **611.9** | LOC: 477
- `test_git_null_byte_path_injection` (@ `tests/core_engine/test_galaxyscope.py`) -> Impact: **606.9** | LOC: 1641
  * *Intent:* # Mock Path.exists to pass the initial validation check with patch("gitgalaxy.galaxyscope.Path.exists", return_value=True): try: scope._prepare_target...
- `draw_ascii_histogram` (@ `gitgalaxy/tools/terabyte_log_scanning/terabyte_log_scanner.py`) -> Impact: **555.4** | LOC: 197
  * *Intent:* """ Draws a dynamically scaled ASCII histogram. If the dataset is massive, it filters to show only the highest volume spikes to prevent terminal flood...
- `_tier_2_fingerprint_check` (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **533.6** | LOC: 312
  * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents generic files from bypassing deep-inspection. if ex...
- `draw_ascii_histogram` (@ `gitgalaxy/tools/terabyte_log_scanning/pii_leak_hunter.py`) -> Impact: **504.8** | LOC: 155

## 8.5 ALGORITHMIC & DATABASE BOTTLENECKS
> Highlights the most computationally expensive and database-heavy functions across the repository.

### Highest Time Complexity (Big-O)
- `_resolve_target` (@ `gitgalaxy/core/network_risk_sensor.py`) -> **O(2^N) [Recursive]**
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
- `main` (@ `gitgalaxy/tools/network_auditing/full_api_network_map.py`) -> DB Complexity: **26**
- `main` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **23**

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `gitgalaxy` | 6 | 4647.6 | 10.65% | 0.0% |
| `gitgalaxy/core` | 9 | 4071.6 | 13.84% | 3.42% |
| `gitgalaxy/metrics` | 5 | 3148.72 | 16.83% | 2.96% |
| `tests/core_engine` | 17 | 2541.02 | 2.7% | 0.0% |
| `gitgalaxy/standards` | 8 | 2034.2 | 7.89% | 10.37% |
| `gitgalaxy/recorders` | 8 | 1571.02 | 21.42% | 1.79% |
| `tests/security_auditing` | 16 | 1420.2 | 1.93% | 0.0% |
| `tests/extraction` | 5 | 1373.14 | 2.93% | 0.0% |
| `gitgalaxy/security` | 5 | 1301.54 | 12.07% | 0.0% |
| `tests` | 7 | 918.62 | 7.48% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `gitgalaxy/metrics/chronometer.py` -> **14.7929%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **14.3599%** Exposure
- `gitgalaxy/core/prism.py` -> **12.3056%** Exposure
- `gitgalaxy/core/network_risk_sensor.py` -> **10.3413%** Exposure
- `gitgalaxy/core/detector.py` -> **8.0952%** Exposure
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
- `gitgalaxy/core/network_risk_sensor.py` -> **100.0%** Exposure
- `gitgalaxy/core/prism.py` -> **100.0%** Exposure
### Algorithmic DoS Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/network_risk_sensor.py` -> **100.0%** Exposure
- `gitgalaxy/core/prism.py` -> **100.0%** Exposure

## 10.7 AUTONOMOUS AI VULNERABILITIES (AGENTIC RCE & PROMPT INJECTION)
> **AI CONTEXT:** Identifies untrusted data flowing into LLM context windows (Prompt Injection) and LLM outputs flowing into dynamic execution (Agentic RCE).

*No autonomous AI vulnerabilities detected.*

## 10.8 ECOSYSTEM SECURITY AUDITS
> **AI CONTEXT:** High-level perimeter defense metrics from the X-Ray, Supply Chain Firewall, and API Network Mapper.

### ☢️ X-Ray & 🧱 Supply Chain Firewall
- **Binary Anomalies (X-Ray):** `0` (High entropy, packed payloads, or magic byte mismatches).
- **Blacklisted Dependencies:** `0` explicitly banned packages imported.
- **Unknown Dependencies:** `781` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/spatial_mapper.py` (PYTHON) -> Cumulative Risk: **737.2**
- **Archetype:** `file_cluster_13` (Distance: 11.406 IQR)
- **Magnitude:** 257.28 | **LOC:** 235 | **CtrlFlow:** 61.7% | **Authorship Centralization:** 40.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.804%)
- **Heaviest Functions:** `map_repository` (Impact: 189.4), `__init__` (Impact: 11.5), `_hash_jitter` (Impact: 8.4)

### 2. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **684.83**
- **Archetype:** `file_cluster_8` (Distance: 11.277 IQR)
- **Magnitude:** 1175.2 | **LOC:** 536 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 55.6%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.2406%)
- **Heaviest Functions:** `audit` (Impact: 1026.0), `_is_dead_code` (Impact: 26.1), `_is_threat` (Impact: 25.9)

### 3. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **675.48**
- **Archetype:** `file_cluster_8` (Distance: 12.538 IQR)
- **Magnitude:** 3862.36 | **LOC:** 3035 | **CtrlFlow:** 71.4% | **Authorship Centralization:** 62.5%
- **Primary Risk Drivers:** Spec Match (100.0%), Churn (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `execute_pipeline` (Impact: 2143.0), `main` (Impact: 869.5), `_process_file_worker` (Impact: 611.9)

### 4. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **662.66**
- **Archetype:** `file_cluster_13` (Distance: 10.961 IQR)
- **Magnitude:** 471.4 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 63.6%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (97.0538%)
- **Heaviest Functions:** `main` (Impact: 225.2), `process_payload` (Impact: 59.8), `record_dead_code` (Impact: 41.2)

### 5. `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` (PYTHON) -> Cumulative Risk: **660.71**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.37 | **LOC:** 215 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `flatten_copybooks` (Impact: 184.3), `generate_build_jcl` (Impact: 34.5), `main` (Impact: 23.0)

### 6. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **657.13**
- **Archetype:** `file_cluster_16` (Distance: 11.855 IQR)
- **Magnitude:** 757.26 | **LOC:** 664 | **CtrlFlow:** 61.5% | **Authorship Centralization:** 53.8%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.9538%)
- **Heaviest Functions:** `_compile_regex_matrix` (Impact: 321.3), `split_streams` (Impact: 125.2), `_strip_nested_comments` (Impact: 109.7)

### 7. `gitgalaxy/standards/config_resolver.py` (PYTHON) -> Cumulative Risk: **652.83**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 356.52 | **LOC:** 305 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `_load_yaml_section` (Impact: 206.6), `_merge_value` (Impact: 74.3), `_get_default` (Impact: 20.4)

### 8. `gitgalaxy/metrics/chronometer.py` (PYTHON) -> Cumulative Risk: **646.59**
- **Archetype:** `file_cluster_8` (Distance: 11.675 IQR)
- **Magnitude:** 638.04 | **LOC:** 450 | **CtrlFlow:** 62.0% | **Authorship Centralization:** 53.8%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (94.4979%)
- **Heaviest Functions:** `_load_ignored_revs` (Impact: 448.0), `_initialize_history_scan` (Impact: 144.9), `__init__` (Impact: 1.8)

### 9. `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) -> Cumulative Risk: **641.07**
- **Archetype:** `file_cluster_13` (Distance: 10.626 IQR)
- **Magnitude:** 283.32 | **LOC:** 351 | **CtrlFlow:** 51.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (97.0328%)
- **Heaviest Functions:** `_audit_capped_sample` (Impact: 176.8), `_iter_candidate_files` (Impact: 32.0), `_scan_single_file` (Impact: 29.2)

### 10. `gitgalaxy/recorders/sarif_recorder.py` (PYTHON) -> Cumulative Risk: **634.52**
- **Archetype:** `file_cluster_8` (Distance: 9.783 IQR)
- **Magnitude:** 154.32 | **LOC:** 238 | **CtrlFlow:** 67.3% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Logic Bomb (100.0%), Algorithmic Dos (99.9997%), State Flux (85.8014%)
- **Heaviest Functions:** `_build_rules_taxonomy` (Impact: 70.1), `_build_dependency_notifications` (Impact: 39.9), `__init__` (Impact: 9.2)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 12.538 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.51 IQR)
- **Top Global Matches:** file_cluster_8: 12.538, file_cluster_13: 12.675, file_cluster_7: 12.925
- **Magnitude:** 3862.36 | **LOC:** 3035 | **CtrlFlow:** 71.4% | **Authorship Centralization:** 62.5%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 52
- **Risk Profile:** Cognitive Load (32.9932%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `execute_pipeline` (Impact: 2143.0 | O(N^6) | DB: 52)
  * `main` (Impact: 869.5 | O(2^N) | DB: 23)
  * `_process_file_worker` (Impact: 611.9 | O(N^6) | DB: 13)
  * `execution_timeout_failsafe` (Impact: 1.9 | O(N^1))
    * *Intent:* """ Hardware-level OS interrupt for Catastrophic Backtracking (ReDoS) protection. Registered via the...
  * `execute_incremental_scan` (Impact: 1.9 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 524`, `structural_boundaries: 210`, `args: 32`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 77`, `state_mutation: 182`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 3`, `import: 63`
* *Defense:* `safety: 72`, `doc: 36`, `test: 1`, `cleanup: 6`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 8.471
  * `Choke Point (Betweenness):` 0.003381 | `Ripple Effect (Closeness):` 0.01875
  * `Imports (Out-Degree: 30):` gitgalaxy.security.security_auditor, typing, tempfile, multiprocessing, re, time, gitgalaxy.core.prism, pathlib...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.002 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.439 IQR)
- **Top Global Matches:** file_cluster_8: 11.002, file_cluster_13: 11.065, file_cluster_16: 11.159
- **Magnitude:** 1848.58 | **LOC:** 466 | **CtrlFlow:** 70.8% | **Authorship Centralization:** 54.5%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (19.5013%), Tech Debt (10.3413%)
**Top Internal Functions/Classes:**
  * `_resolve_target` (Impact: 1785.9 | O(2^N) | DB: 2)
  * `_build_resolution_map` (Impact: 25.9 | O(N^4) | DB: 3)
  * `__init__` (Impact: 7.9 | O(N^2) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 109`, `structural_boundaries: 45`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 30`, `state_mutation: 19`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 10`
* *Defense:* `safety: 21`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 10.82
  * `Choke Point (Betweenness):` 7.2e-05 | `Ripple Effect (Closeness):` 0.030625
  * `Imports (Out-Degree: 1):` typing, logging, pathlib, math, networkx, networkx.algorithms, token, warnings...
  * `Imported By (In-Degree: 4):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.189 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 3.76 IQR)
- **Top Global Matches:** file_cluster_8: 11.189, file_cluster_16: 11.541, file_cluster_7: 11.645
- **Magnitude:** 1179.12 | **LOC:** 2487 | **CtrlFlow:** 76.2% | **Authorship Centralization:** 66.7%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (16.6319%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_forensic_report` (Impact: 287.1 | O(N^6) | DB: 3)
  * `_calc_injection_surface` (Impact: 109.6 | O(N^4))
  * `_rank_list` (Impact: 75.5 | O(N^5))
  * `_calc_safety` (Impact: 65.6 | O(N^4))
  * `_calc_secrets_risk` (Impact: 61.0 | O(N^3))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 443`, `structural_boundaries: 138`, `args: 44`, `func_start: 36`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 44`, `state_mutation: 92`
* *Architecture:* `io: 1`, `api: 12`, `concurrency: 2`, `import: 8`
* *Defense:* `safety: 72`, `doc: 50`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 10.832
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.036364
  * `Imports (Out-Degree: 0):` statistics, typing, logging, re, math, gitgalaxy.standards, os
  * `Imported By (In-Degree: 5):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.277 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.372 IQR)
- **Top Global Matches:** file_cluster_8: 11.277, file_cluster_16: 11.443, file_cluster_13: 11.496
- **Magnitude:** 1175.2 | **LOC:** 536 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 55.6%
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
* *Structure:* `branch: 85`, `structural_boundaries: 36`, `args: 8`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 26`, `state_mutation: 60`
* *Architecture:* `io: 2`, `api: 3`, `import: 5`
* *Defense:* `safety: 9`, `doc: 14`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.108
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019531
  * `Imports (Out-Degree: 0):` statistics, typing, logging, math, os
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 1113.12 | **LOC:** 1139 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` typing, logging, re, time, pathlib, math, gitgalaxy.standards.language_standards, gitgalaxy.standards.gitgalaxy_config
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
  * `Imports (Out-Degree: 0):` java.util., UIKit, formatting, gitgalaxy.engine, Foundation, mypack.myclass, gitgalaxy.standards.language_standards, os...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.024 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.186 IQR)
- **Top Global Matches:** file_cluster_8: 11.024, file_cluster_16: 11.335, file_cluster_7: 11.426
- **Magnitude:** 858.16 | **LOC:** 2300 | **CtrlFlow:** 73.6% | **Authorship Centralization:** 55.6%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (13.1111%), Tech Debt (8.0952%)
**Top Internal Functions/Classes:**
  * `_decode_comment_stream` (Impact: 338.7 | O(N^6) | DB: 3)
  * `_extract_documentation_tether` (Impact: 142.4 | O(N^6) | DB: 2)
  * `_classify_function` (Impact: 124.5 | O(N^4))
  * `_extract_name` (Impact: 96.6 | O(N^5))
  * `index_aligned_shield` (Impact: 14.0 | O(N^3))
    * *Intent:* """The Master Routing Dispatcher: Directs the structural signal into the correct integration mode.""...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 413`, `structural_boundaries: 148`, `args: 21`, `func_start: 20`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 54`, `state_mutation: 83`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `api: 14`, `concurrency: 1`, `import: 12`
* *Defense:* `safety: 39`, `doc: 65`, `test: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 7.205
  * `Choke Point (Betweenness):` 0.00021 | `Ripple Effect (Closeness):` 0.025
  * `Imports (Out-Degree: 3):` typing, logging, re, time, bisect, math, gitgalaxy.standards.language_standards, gitgalaxy.core.spatial_correlation...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 13.369 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.032 IQR)
- **Top Global Matches:** file_cluster_8: 13.369, file_cluster_13: 13.664, file_cluster_11: 13.705
- **Magnitude:** 813.98 | **LOC:** 1513 | **CtrlFlow:** 87.5% | **Authorship Centralization:** 55.6%
- **Algorithmic:** O(N^3) | **DB Complexity:** 4
- **Risk Profile:** Cognitive Load (63.306%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 11.0 | O(N^3) | DB: 4)
  * `_parse_threat_score` (Impact: 7.3 | O(N^3))
  * `generate_artifacts` (Impact: 1.9 | O(N^2))
  * `_build_markdown` (Impact: 1.9 | O(N^2))
  * `_generate_sqlite_graph` (Impact: 1.9 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 322`, `structural_boundaries: 46`, `args: 31`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 751`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 13`, `doc: 26`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.108
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019531
  * `Imports (Out-Degree: 0):` statistics, typing, logging, json, pathlib, heapq, gitgalaxy.standards, collections...
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
  * `Imports (Out-Degree: 0):` tempfile, re, pathlib, gitgalaxy.standards, must, or, os, name...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_16` (Drift: 11.855 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.159 IQR)
- **Top Global Matches:** file_cluster_16: 11.855, file_cluster_8: 11.921, file_cluster_13: 12.119
- **Magnitude:** 757.26 | **LOC:** 664 | **CtrlFlow:** 61.5% | **Authorship Centralization:** 53.8%
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 5.698
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019531
  * `Imports (Out-Degree: 1):` gitgalaxy.standards.language_standards, re, typing, logging
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 676.96 | **LOC:** 398 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` (Impact: 299.1 | O(N^6) | DB: 26)
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
  * `Imports (Out-Degree: 0):` typing, logging, json, re, pathlib, os
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.675 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.923 IQR)
- **Top Global Matches:** file_cluster_8: 11.675, file_cluster_13: 11.701, file_cluster_16: 11.921
- **Magnitude:** 638.04 | **LOC:** 450 | **CtrlFlow:** 62.0% | **Authorship Centralization:** 53.8%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 14
- **Risk Profile:** Cognitive Load (14.2723%), Tech Debt (14.7929%)
**Top Internal Functions/Classes:**
  * `_load_ignored_revs` (Impact: 448.0 | O(2^N) | DB: 12)
  * `_initialize_history_scan` (Impact: 144.9 | O(N^6) | DB: 14)
  * `__init__` (Impact: 1.8 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 62`, `structural_boundaries: 38`, `args: 8`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `high_risk_execution: 1`, `state_mutation: 35`, `fragile_debt: 1`
* *Architecture:* `io: 8`, `api: 3`, `import: 7`
* *Defense:* `safety: 18`, `doc: 18`, `test: 1`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 8.108
  * `Choke Point (Betweenness):` 3.9e-05 | `Ripple Effect (Closeness):` 0.019531
  * `Imports (Out-Degree: 1):` typing, logging, time, pathlib, subprocess, gitgalaxy.standards.config_resolver, gitgalaxy.standards, os
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 528.52 | **LOC:** 433 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` (Impact: 162.7 | O(N^6) | DB: 3)
  * `audit_repository` (Impact: 125.2 | O(N^6))
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
  * `Imports (Out-Degree: 0):` logging, pandas, pathlib, networkx, collections, gitgalaxy.standards.analysis_lens, xgboost, numpy
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 10.961 IQR)
- **Local Micro-Species:** `Cluster 3: Data Pipelines & I/O Operations` (Drift: 5.121 IQR)
- **Top Global Matches:** file_cluster_13: 10.961, file_cluster_8: 11.05, file_cluster_7: 11.444
- **Magnitude:** 471.4 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 63.6%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 12
- **Risk Profile:** Cognitive Load (18.3929%), Tech Debt (0.0%)
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
* *Structure:* `branch: 54`, `structural_boundaries: 52`, `args: 10`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 6`, `state_mutation: 42`
* *Architecture:* `io: 4`, `api: 9`, `import: 17`
* *Defense:* `safety: 4`, `doc: 10`, `cleanup: 3`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 7.868
  * `Choke Point (Betweenness):` 0.000354 | `Ripple Effect (Closeness):` 0.00625
  * `Imports (Out-Degree: 9):` typing, gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge, argparse, sys, datetime, json, gitgalaxy.tools.cobol_to_cobol.cobol_microservice_slicer, gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge...
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
  * `Imports (Out-Degree: 0):` pytest, logging, re, gitgalaxy.core.spatial_mapper, math, with, unittest.mock, gitgalaxy.core.detector
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
  * `Imports (Out-Degree: 0):` typing, argparse, sys, ast, json, pathlib
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_standards.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 357.06 | **LOC:** 10599 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` typing, java.util., path, re, keyword., type, inside
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
  * `Imports (Out-Degree: 0):` pytest, tempfile, json, gitgalaxy.recorders.sarif_recorder, os, gitgalaxy.metrics.signal_processor, identity, which
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/config_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 356.52 | **LOC:** 305 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_load_yaml_section` (Impact: 206.6 | O(2^N) | DB: 3)
  * `_merge_value` (Impact: 74.3 | O(N^5))
  * `_get_default` (Impact: 20.4 | O(N^3))
  * `_merge_collection` (Impact: 18.9 | O(N^2) | DB: 1)
    * *Intent:* # Only called when normal attribute lookup fails, i.e. never for # `_values` itself -- safe against ...
  * `__getattr__` (Impact: 7.3 | O(N^3))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` typing, logging, yaml, gitgalaxy.standards, copy, dataclasses, __future__
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_to_java_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.869 IQR)
- **Local Micro-Species:** `Cluster 3: Data Pipelines & I/O Operations` (Drift: 5.187 IQR)
- **Top Global Matches:** file_cluster_8: 8.869, file_cluster_13: 9.316, file_cluster_7: 9.462
- **Magnitude:** 298.58 | **LOC:** 338 | **CtrlFlow:** 55.3% | **Authorship Centralization:** 50.0%
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
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 4.253
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 6):` gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge, gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge, argparse, sys, shutil, json, org.slf4j.LoggerFactory, gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 10.626 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.468 IQR)
- **Top Global Matches:** file_cluster_13: 10.626, file_cluster_8: 10.712, file_cluster_16: 11.04
- **Magnitude:** 283.32 | **LOC:** 351 | **CtrlFlow:** 51.9% | **Authorship Centralization:** 100.0%
- **Algorithmic:** O(N^6) | **DB Complexity:** 6
- **Risk Profile:** Cognitive Load (18.8879%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_audit_capped_sample` (Impact: 176.8 | O(N^6) | DB: 6)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 9.916
  * `Choke Point (Betweenness):` 0.000314 | `Ripple Effect (Closeness):` 0.025
  * `Imports (Out-Degree: 4):` typing, gitgalaxy.security.manifest_parser, logging, datetime, json, gitgalaxy.security.security_lens, pathlib, gitgalaxy.standards.language_standards...
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
  * `Imports (Out-Degree: 0):` pytest, bypassed, gitgalaxy.metrics.signal_processor, sys, json, yaml, pathlib, was...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/spatial_mapper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 11.406 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.224 IQR)
- **Top Global Matches:** file_cluster_13: 11.406, file_cluster_16: 11.453, file_cluster_8: 11.518
- **Magnitude:** 257.28 | **LOC:** 235 | **CtrlFlow:** 61.7% | **Authorship Centralization:** 40.0%
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 6.301
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.019531
  * `Imports (Out-Degree: 0):` hashlib, typing, math, logging
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.045 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.919 IQR)
- **Top Global Matches:** file_cluster_8: 11.045, file_cluster_13: 11.183, file_cluster_16: 11.347
- **Magnitude:** 252.3 | **LOC:** 512 | **CtrlFlow:** 62.9% | **Authorship Centralization:** 50.0%
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 8.108
  * `Choke Point (Betweenness):` 3.9e-05 | `Ripple Effect (Closeness):` 0.019531
  * `Imports (Out-Degree: 1):` typing, logging, json, re, pathlib, os, fnmatch, gitgalaxy.standards.gitgalaxy_config
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

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_13
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 257.28 | Delta: **0.047 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 134, state_mutation: 30, branch: 29, encapsulation: 23
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 283.32 | Delta: **0.086 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 218, branch: 54, structural_boundaries: 50, state_mutation: 34
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 471.4 | Delta: **0.089 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 54, structural_boundaries: 52, state_mutation: 42
- `gitgalaxy/metrics/tensor_scanner.py` (PYTHON) | Magnitude: 145.84 | Delta: **0.112 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 80, structural_boundaries: 27, branch: 25, doc: 10

### Mixed-Responsibility Refactoring Targets for: file_cluster_16
- `gitgalaxy/core/prism.py` (PYTHON) | Magnitude: 757.26 | Delta: **0.066 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 365, branch: 110, state_mutation: 94, structural_boundaries: 69
- `gitgalaxy/core/spatial_correlation.py` (PYTHON) | Magnitude: 62.42 | Delta: **0.186 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 133, branch: 32, generics: 27, structural_boundaries: 19

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/metrics/chronometer.py` (PYTHON) | Magnitude: 638.04 | Delta: **0.026 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 259, branch: 62, structural_boundaries: 38, state_mutation: 35
- `gitgalaxy/core/network_risk_sensor.py` (PYTHON) | Magnitude: 1848.58 | Delta: **0.063 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 284, branch: 109, structural_boundaries: 45, safety_bypasses: 30
- `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) | Magnitude: 144.5 | Delta: **0.081 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 272, state_mutation: 95, branch: 41, explicit_casts: 33
- `gitgalaxy/galaxyscope.py` (PYTHON) | Magnitude: 3862.36 | Delta: **0.137 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 1940, branch: 524, structural_boundaries: 210, state_mutation: 182
- `gitgalaxy/core/guidestar_lens.py` (PYTHON) | Magnitude: 252.3 | Delta: **0.138 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 286, branch: 90, structural_boundaries: 53, encapsulation: 41

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **70.54%** | Cog Load: 63.306% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/recorders/sbom_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 283.32
- `gitgalaxy/recorders/sarif_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 154.32
- `gitgalaxy/core/spatial_correlation.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 62.42

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/galaxyscope.py` -> **Severity: 0.262** (Bridge: 0.0034 * Flux: 77.6198%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.034** (Bridge: 0.0004 * Flux: 97.0538%)
- `gitgalaxy/recorders/sbom_recorder.py` -> **Severity: 0.03** (Bridge: 0.0003 * Flux: 97.0328%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.01** (Bridge: 0.0002 * Flux: 48.5336%)
- `gitgalaxy/security/security_auditor.py` -> **Severity: 0.009** (Bridge: 0.0001 * Flux: 94.1735%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 5.357** (Embedded: 0.067 * Error Risk: 80.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 2.45** (Embedded: 0.0306 * Error Risk: 80.0%)
- `gitgalaxy/recorders/sarif_recorder.py` -> **Severity: 1.579** (Embedded: 0.025 * Error Risk: 63.1492%)
- `gitgalaxy/tools/ai_guardrails/ai_appsec_sensor.py` -> **Severity: 1.562** (Embedded: 0.0195 * Error Risk: 80.0%)
- `gitgalaxy/recorders/llm_recorder.py` -> **Severity: 1.507** (Embedded: 0.0195 * Error Risk: 77.1416%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 3335.1** (Blast Radius: 33.351 * Doc Risk: 100.0%)
- `gitgalaxy/metrics/tensor_scanner.py` -> **Severity: 810.8** (Blast Radius: 8.108 * Doc Risk: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` -> **Severity: 786.8** (Blast Radius: 7.868 * Doc Risk: 100.0%)
- `gitgalaxy/standards/language_standards.py` -> **Severity: 740.495** (Blast Radius: 47.785 * Doc Risk: 15.4964%)
- `gitgalaxy/tools/network_auditing/full_api_network_map.py` -> **Severity: 726.722** (Blast Radius: 8.108 * Doc Risk: 89.6302%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Act as a Principal Staff Engineer. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility). DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective, practical, and direct.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
