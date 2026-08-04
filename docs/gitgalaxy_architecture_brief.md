# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-08-04T14:14:05.683629+00:00` |
| **Scan Duration** | `10.02s` |
| **Git Branch** | `main` |
| **Git Commit** | `0110b293fcaa52846a23356e8a25f16c932144f0` |
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
| Total Artifacts | 700 |
| Analyzed Artifacts (Scanned) | 224 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 476 |
| Total LOC | 57032 |
| Volatility Index | 0.018 |
| % Scanned of codebase = | 32.0% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.6298 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.3378 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 2.8129 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 36 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 180 | 56528 | 80.4% |
| MARKDOWN | 29 | 0 | 12.9% |
| YAML | 8 | 482 | 3.6% |
| PLAINTEXT | 6 | 0 | 2.7% |
| SHELL | 1 | 22 | 0.4% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `4.935`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 128 | 57.1% |
| file_cluster_13 | 34 | 15.2% |
| file_cluster_0 | 19 | 8.5% |
| file_cluster_16 | 7 | 3.1% |
| file_cluster_6 | 1 | 0.4% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 35 | 15.6% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 476*

**Composition by Extension & Reason:**
- `.md`: 337x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 63 LOC), 1x Excluded (Machine-Generated Source Code Signature: 34 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.yml`: 19x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 4x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 551 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.json`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 62.6 | 3.0 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 76.7 | 5.1 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 100.0 | 2.0 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 6.1 | 0.0 | 0.0 |
| API Exposure | 0.0 | 8.1 | 0.2 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 26.5 | 0.4 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 8.0 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 9.8 | 0.2 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 15.6 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 34.6 | 1.2 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 81.1 | 7.1 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 100.0 | 5.0 | 0.0 | 0.0 |
| Algorithmic DoS Exposure | 0.0 | 100.0 | 8.4 | 0.0 | 0.0 |
| Obfuscation & Evasion Surface | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Exploit Generation Surface | 0.0 | 100.0 | 8.9 | 0.0 | 0.0 |
| Weaponizable Injection Vectors | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Raw Memory Manipulation | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `bitbucket-pipelines.yml` (Hits: 10)
- `gitgalaxy/core/guidestar_lens.py` (Hits: 8)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **language_standards.py** (`gitgalaxy/standards/language_standards.py`) — 61 inbound connections
2. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 44 inbound connections
3. **config_resolver.py** (`gitgalaxy/standards/config_resolver.py`) — 9 inbound connections
4. **analysis_lens.py** (`gitgalaxy/standards/analysis_lens.py`) — 7 inbound connections
5. **gitgalaxy_config.py** (`gitgalaxy/standards/gitgalaxy_config.py`) — 6 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 56 outbound dependencies
2. **test_language_standards_strict.py** (`tests/core_engine/test_language_standards_strict.py`) — 38 outbound dependencies
3. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 20 outbound dependencies
4. **test_embedded_python.py** (`tests/extraction/languages/test_embedded_python.py`) — 20 outbound dependencies
5. **test_scala.py** (`tests/extraction/languages/test_scala.py`) — 19 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_process_file_worker` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **7419.7** | LOC: 2794
- `ipc_rpc_bridges` (@ `gitgalaxy/standards/language_standards.py`) -> Impact: **1913.2** | LOC: 679
- `_resolve_target` (@ `gitgalaxy/core/network_risk_sensor.py`) -> Impact: **1734.9** | LOC: 405
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **1026.0** | LOC: 361
- `foo` (@ `tests/core_engine/test_language_standards_strict.py`) -> Impact: **806.5** | LOC: 1249
  * *Intent:* # sanity: all still match their real positive cases after the sweep assert ZIG_RULES["func_start"].search("pub fn main() void {") assert ZIG_RULES["cl...
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> Impact: **688.0** | LOC: 181
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `_tier_2_fingerprint_check` (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **684.7** | LOC: 394
  * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents generic files from bypassing deep-inspection. if ex...
- `_compile_regex_matrix` (@ `gitgalaxy/core/prism.py`) -> Impact: **565.4** | LOC: 396
  * *Intent:* # 4. GENERIC STRIPPER pattern = self.REGEX_MATRIX.get(family) if not pattern: # Restore mask tokens before returning if no pattern is registered code ...
- `closures` (@ `gitgalaxy/standards/language_standards.py`) -> Impact: **514.6** | LOC: 493
- `slice_manifest` (@ `gitgalaxy/security/manifest_parser.py`) -> Impact: **505.6** | LOC: 173

## 8.5 ALGORITHMIC & DATABASE BOTTLENECKS
> Highlights the most computationally expensive and database-heavy functions across the repository.

### Highest Time Complexity (Big-O)
- `_resolve_target` (@ `gitgalaxy/core/network_risk_sensor.py`) -> **O(2^N) [Recursive]**
- `_process_file_worker` (@ `gitgalaxy/galaxyscope.py`) -> **O(2^N) [Recursive]**
- `_load_ignored_revs` (@ `gitgalaxy/metrics/chronometer.py`) -> **O(2^N) [Recursive]**
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> **O(2^N) [Recursive]**
- `flatten_copybooks` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> **O(2^N) [Recursive]**
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `main` (@ `gitgalaxy/tools/supply_chain_security/vault_sentinel.py`) -> **O(2^N) [Recursive]**
- `simulate_delta_parser` (@ `tests/core_engine/test_delta_scanner.py`) -> **O(2^N) [Recursive]**
  * *Intent:* """ A DRY helper method that exactly mirrors the Git Diff parser from galaxyscope.py to test its physical routing logic. """
- `mock_pipeline_state` (@ `tests/tools_recorders/test_record_keeper.py`) -> **O(2^N) [Recursive]**
- `ipc_rpc_bridges` (@ `gitgalaxy/standards/language_standards.py`) -> **O(2^N) [Recursive]**

### Highest Data Gravity (Database Complexity)
- `_process_file_worker` (@ `gitgalaxy/galaxyscope.py`) -> DB Complexity: **121**
- `foo` (@ `tests/core_engine/test_language_standards_strict.py`) -> DB Complexity: **107**
  * *Intent:* # sanity: all still match their real positive cases after the sweep assert ZIG_RULES["func_start"].search("pub fn main() void {") assert ZIG_RULES["cl...
- `test_git_null_byte_path_injection` (@ `tests/core_engine/test_galaxyscope.py`) -> DB Complexity: **50**
  * *Intent:* # When entering the context manager, return our mock instance # Mock Path.exists to pass the initial validation check with patch("gitgalaxy.galaxyscop...
- `generate_build_jcl` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py`) -> DB Complexity: **34**
- `generate_rest_controller` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py`) -> DB Complexity: **34**
  * *Intent:* """Generates the API endpoints and auto-wires the Service layer."""
- `publish_insights` (@ `templates/bitbucket/bitbucket_insights.py`) -> DB Complexity: **34**
- `slice_manifest` (@ `gitgalaxy/security/manifest_parser.py`) -> DB Complexity: **32**
- `generate_java_entity` (@ `gitgalaxy/tools/cobol_to_java/cobol_to_java_spring_forge.py`) -> DB Complexity: **31**
- `main` (@ `gitgalaxy/tools/network_auditing/full_api_network_map.py`) -> DB Complexity: **26**
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> DB Complexity: **22**

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `gitgalaxy` | 6 | 8326.4 | 8.61% | 0.0% |
| `tests/core_engine` | 16 | 7015.96 | 2.88% | 0.0% |
| `tests/extraction/languages` | 44 | 4896.21 | 3.03% | 0.0% |
| `gitgalaxy/standards` | 8 | 4198.64 | 9.66% | 18.59% |
| `gitgalaxy/core` | 9 | 4142.26 | 14.97% | 4.05% |
| `gitgalaxy/metrics` | 5 | 2205.44 | 16.84% | 4.55% |
| `tests/security_auditing` | 16 | 1688.24 | 1.98% | 0.0% |
| `gitgalaxy/security` | 5 | 1511.46 | 12.13% | 0.0% |
| `gitgalaxy/recorders` | 8 | 1334.18 | 21.02% | 1.81% |
| `tests/extraction` | 7 | 1115.44 | 4.24% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `scripts/update_golden_masters.sh` -> **99.956%** Exposure
- `action.yml` -> **99.876%** Exposure
- `bitbucket-pipelines.yml` -> **99.4071%** Exposure
- `gitgalaxy/core/prism.py` -> **16.2747%** Exposure
- `gitgalaxy/metrics/chronometer.py` -> **14.7229%** Exposure
### Highest State Flux (Mutation/Volatility)
- `gitgalaxy/recorders/llm_recorder.py` -> **100.0%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **99.9989%** Exposure
- `gitgalaxy/core/prism.py` -> **99.9826%** Exposure
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

### Exploit Generation Surface
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/detector.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
- `gitgalaxy/core/network_risk_sensor.py` -> **100.0%** Exposure
### Algorithmic DoS Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
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
- **Unknown Dependencies:** `1196` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/spatial_mapper.py` (PYTHON) -> Cumulative Risk: **743.27**
- **Archetype:** `file_cluster_13` (Distance: 11.441 IQR)
- **Magnitude:** 254.06 | **LOC:** 230 | **CtrlFlow:** 61.7% | **Authorship Centralization:** 53.8%
- **Primary Risk Drivers:** Spec Match (100.0%), Documentation (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%)
- **Heaviest Functions:** `map_repository` (Impact: 189.1), `__init__` (Impact: 11.5), `_hash_jitter` (Impact: 8.6)

### 2. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **681.28**
- **Archetype:** `file_cluster_8` (Distance: 11.285 IQR)
- **Magnitude:** 1175.2 | **LOC:** 536 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 55.6%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.3259%)
- **Heaviest Functions:** `audit` (Impact: 1026.0), `_is_dead_code` (Impact: 26.1), `_is_threat` (Impact: 25.9)

### 3. `gitgalaxy/metrics/chronometer.py` (PYTHON) -> Cumulative Risk: **671.66**
- **Archetype:** `file_cluster_13` (Distance: 11.727 IQR)
- **Magnitude:** 639.08 | **LOC:** 458 | **CtrlFlow:** 60.6% | **Authorship Centralization:** 64.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (94.9042%)
- **Heaviest Functions:** `_load_ignored_revs` (Impact: 448.1), `_determine_commit_bounds` (Impact: 112.5), `_initialize_history_scan` (Impact: 33.3)

### 4. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **668.9**
- **Archetype:** `file_cluster_16` (Distance: 12.169 IQR)
- **Magnitude:** 909.92 | **LOC:** 744 | **CtrlFlow:** 63.0% | **Authorship Centralization:** 71.4%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (99.9826%)
- **Heaviest Functions:** `_compile_regex_matrix` (Impact: 565.4), `split_streams` (Impact: 125.2), `_strip_segment_comments` (Impact: 59.7)

### 5. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **656.62**
- **Archetype:** `file_cluster_13` (Distance: 10.982 IQR)
- **Magnitude:** 358.6 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 58.3%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), State Flux (97.3782%)
- **Heaviest Functions:** `main` (Impact: 112.4), `process_payload` (Impact: 59.8), `record_dead_code` (Impact: 41.2)

### 6. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **656.55**
- **Archetype:** `file_cluster_8` (Distance: 12.536 IQR)
- **Magnitude:** 7653.96 | **LOC:** 3044 | **CtrlFlow:** 70.9% | **Authorship Centralization:** 71.2%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), Churn (81.07%)
- **Heaviest Functions:** `_process_file_worker` (Impact: 7419.7), `execution_timeout_failsafe` (Impact: 1.9), `_init_worker` (Impact: 1.4)

### 7. `gitgalaxy/standards/config_resolver.py` (PYTHON) -> Cumulative Risk: **649.76**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 185.02 | **LOC:** 305 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `_merge_value` (Impact: 74.3), `_load_yaml_section` (Impact: 32.9), `_get_default` (Impact: 20.4)

### 8. `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` (PYTHON) -> Cumulative Risk: **635.53**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.34 | **LOC:** 215 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `flatten_copybooks` (Impact: 184.3), `generate_build_jcl` (Impact: 34.5), `main` (Impact: 23.0)

### 9. `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) -> Cumulative Risk: **629.18**
- **Archetype:** `file_cluster_13` (Distance: 10.61 IQR)
- **Magnitude:** 196.62 | **LOC:** 351 | **CtrlFlow:** 51.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Logic Bomb (100.0%), Algorithmic Dos (99.9999%), State Flux (97.3595%)
- **Heaviest Functions:** `_audit_with_cache` (Impact: 151.3), `generate_report` (Impact: 1.9), `__init__` (Impact: 1.8)

### 10. `gitgalaxy/core/network_risk_sensor.py` (PYTHON) -> Cumulative Risk: **628.53**
- **Archetype:** `file_cluster_13` (Distance: 11.29 IQR)
- **Magnitude:** 1797.52 | **LOC:** 475 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 66.7%
- **Primary Risk Drivers:** Spec Match (100.0%), Algorithmic Dos (100.0%), Logic Bomb (100.0%), Verification (80.0%)
- **Heaviest Functions:** `_resolve_target` (Impact: 1734.9), `_build_resolution_map` (Impact: 25.9), `__init__` (Impact: 7.9)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 12.536 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.579 IQR)
- **Top Global Matches:** file_cluster_8: 12.536, file_cluster_13: 12.651, file_cluster_7: 12.913
- **Magnitude:** 7653.96 | **LOC:** 3044 | **CtrlFlow:** 70.9% | **Authorship Centralization:** 71.2%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 121
- **Risk Profile:** Cognitive Load (20.7687%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_process_file_worker` (Impact: 7419.7 | O(2^N) | DB: 121)
  * `execution_timeout_failsafe` (Impact: 1.9 | O(N^1))
    * *Intent:* """ Hardware-level OS interrupt for Catastrophic Backtracking (ReDoS) protection. Registered via the...
  * `_init_worker` (Impact: 1.4 | O(N^1))
    * *Intent:* """ raise TimeoutError("Structural Saturation (ReDoS Timeout)") def _init_worker( root_str: str, con...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 527`, `structural_boundaries: 216`, `args: 32`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 77`, `state_mutation: 182`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 3`, `import: 63`
* *Defense:* `safety: 73`, `doc: 36`, `test: 2`, `cleanup: 6`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 5.908
  * `Choke Point (Betweenness):` 0.001737 | `Ripple Effect (Closeness):` 0.013453
  * `Imports (Out-Degree: 30):` gitgalaxy.recorders.llm_recorder, signal, re, logging, zipfile, gitgalaxy.recorders.audit_recorder, importlib.util, gitgalaxy.standards.language_lens...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_language_standards_strict.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 4440.42 | **LOC:** 14665 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `foo` (Impact: 806.5 | O(2^N) | DB: 107)
    * *Intent:* # sanity: all still match their real positive cases after the sweep assert ZIG_RULES["func_start"].s...
  * `assert_redos_immune` (Impact: 461.3 | O(2^N) | DB: 1)
  * `test_cpp_macro_multiline_spiral` (Impact: 329.6 | O(N^5) | DB: 20)
  * `test_livecode_ownership_comment_style_co` (Impact: 322.0 | O(N^3) | DB: 4)
  * `test_dart_test_vs_regex_execution_no_fal` (Impact: 278.7 | O(N^3) | DB: 14)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` Foundation, re, and, mypackage.MyClass, os.path, ulab, Yesod, ccall...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_standards.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 2861.26 | **LOC:** 12644 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `ipc_rpc_bridges` (Impact: 1913.2 | O(2^N) | DB: 3)
  * `closures` (Impact: 514.6 | O(2^N))
  * `globals` (Impact: 35.2 | O(N^4))
    * *Intent:* # 18. globals: Global / Shared State. Magic variables and system globals. # BUG FIX: `$$`, `$@`, `$!...
  * `serialization_parsing` (Impact: 12.6 | O(N^4))
    * *Intent:* # --- PHASE 3: HYBRID DOMAIN SENSORS (Dockerfile Specifics) --- # CRITICAL GUARDRAIL: all four senso...
  * `time_date_logic` (Impact: 12.6 | O(N^4))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` scala.util.chaining., typing, re, java.util., path, keyword., inside, was...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 11.29 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.767 IQR)
- **Top Global Matches:** file_cluster_13: 11.29, file_cluster_17: 11.353, file_cluster_8: 11.38
- **Magnitude:** 1797.52 | **LOC:** 475 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 66.7%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (19.1343%), Tech Debt (10.3739%)
**Top Internal Functions/Classes:**
  * `_resolve_target` (Impact: 1734.9 | O(2^N) | DB: 2)
  * `_build_resolution_map` (Impact: 25.9 | O(N^4) | DB: 3)
  * `__init__` (Impact: 7.9 | O(N^2) | DB: 2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 106`, `structural_boundaries: 45`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 25`, `state_mutation: 19`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 10`
* *Defense:* `safety: 21`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 7.546
  * `Choke Point (Betweenness):` 3.7e-05 | `Ripple Effect (Closeness):` 0.021973
  * `Imports (Out-Degree: 1):` networkx, math, typing, networkx.algorithms, collections, logging, warnings, gitgalaxy.standards.analysis_lens...
  * `Imported By (In-Degree: 4):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.285 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.422 IQR)
- **Top Global Matches:** file_cluster_8: 11.285, file_cluster_16: 11.45, file_cluster_13: 11.491
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 5.655
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.014013
  * `Imports (Out-Degree: 0):` math, typing, logging, os, statistics
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 940.26 | **LOC:** 1145 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_tier_2_fingerprint_check` (Impact: 684.7 | O(N^6) | DB: 5)
    * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents g...
  * `_detect_hybrids` (Impact: 93.8 | O(N^6) | DB: 2)
  * `_calibrate_lookup_maps` (Impact: 73.8 | O(N^6))
  * `_tier_1_metadata_lock` (Impact: 16.6 | O(N^3))
  * `inspect` (Impact: 1.9 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` math, re, typing, gitgalaxy.standards.gitgalaxy_config, logging, time, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_16` (Drift: 12.169 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.222 IQR)
- **Top Global Matches:** file_cluster_16: 12.169, file_cluster_8: 12.233, file_cluster_13: 12.405
- **Magnitude:** 909.92 | **LOC:** 744 | **CtrlFlow:** 63.0% | **Authorship Centralization:** 71.4%
- **Algorithmic:** O(N^6) | **DB Complexity:** 20
- **Risk Profile:** Cognitive Load (30.5115%), Tech Debt (16.2747%)
**Top Internal Functions/Classes:**
  * `_compile_regex_matrix` (Impact: 565.4 | O(N^6) | DB: 20)
    * *Intent:* # 4. GENERIC STRIPPER pattern = self.REGEX_MATRIX.get(family) if not pattern: # Restore mask tokens ...
  * `split_streams` (Impact: 125.2 | O(N^5) | DB: 3)
  * `_strip_segment_comments` (Impact: 59.7 | O(N^4) | DB: 7)
    * *Intent:* # 3. Derive the documentation lines by subtracting code from the active total. # This forces mutual ...
  * `_strip_single_line_comments` (Impact: 26.7 | O(N^4) | DB: 3)
    * *Intent:* # 2. Modern Inline Fortran (!), COBOL (*>), and ABAP (") comments if "*>" in line: parts = line.spli...
  * `__init__` (Impact: 1.8 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 126`, `structural_boundaries: 74`, `args: 24`, `func_start: 20`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 22`, `state_mutation: 111`, `fragile_debt: 2`
* *Architecture:* `api: 12`, `import: 4`
* *Defense:* `safety: 4`, `doc: 34`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.478
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.017937
  * `Imports (Out-Degree: 1):` typing, logging, gitgalaxy.standards.language_standards, re
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 886.86 | **LOC:** 398 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` (Impact: 505.6 | O(N^6) | DB: 32)
  * `_parse_requirements_txt` (Impact: 170.3 | O(N^6) | DB: 6)
    * *Intent:* # DEFENSIVE GUARD: Registry Spoofing # If the resolved URL points to a non-standard domain or a dire...
  * `_parse_package_json` (Impact: 67.5 | O(N^5) | DB: 3)
  * `_parse_package_lock` (Impact: 49.1 | O(N^5) | DB: 3)
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
  * `Imports (Out-Degree: 0):` re, typing, logging, json, os, pathlib
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.163 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.254 IQR)
- **Top Global Matches:** file_cluster_8: 11.163, file_cluster_16: 11.47, file_cluster_7: 11.559
- **Magnitude:** 833.98 | **LOC:** 2405 | **CtrlFlow:** 73.7% | **Authorship Centralization:** 67.6%
- **Algorithmic:** O(N^6) | **DB Complexity:** 3
- **Risk Profile:** Cognitive Load (21.1046%), Tech Debt (9.779%)
**Top Internal Functions/Classes:**
  * `_decode_comment_stream` (Impact: 338.7 | O(N^6) | DB: 3)
  * `_extract_name` (Impact: 192.3 | O(N^5))
  * `_extract_documentation_tether` (Impact: 142.4 | O(N^6) | DB: 2)
  * `index_aligned_shield` (Impact: 14.0 | O(N^3))
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `get_token_mass` (Impact: 9.4 | O(N^2))
    * *Intent:* """Calculates context window footprint. Returns None if tiktoken is missing to prevent dataset poiso...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 426`, `structural_boundaries: 152`, `args: 22`, `func_start: 20`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 51`, `state_mutation: 86`, `dead_code: 1`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `api: 14`, `concurrency: 1`, `import: 12`
* *Defense:* `safety: 39`, `doc: 65`, `test: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.268
  * `Choke Point (Betweenness):` 8.8e-05 | `Ripple Effect (Closeness):` 0.017937
  * `Imports (Out-Degree: 3):` math, re, typing, tiktoken, logging, collections, bisect, time...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 806.46 | **LOC:** 2075 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_git_null_byte_path_injection` (Impact: 183.2 | O(N^5) | DB: 50)
    * *Intent:* # When entering the context manager, return our mock instance # Mock Path.exists to pass the initial...
  * `test_recorder_exception_survivability` (Impact: 47.1 | O(N^4))
  * `test_yaml_typo_in_gitgalaxy_config_key_a` (Impact: 37.1 | O(N^5) | DB: 7)
  * `test_sarif_ignored_rules_purging` (Impact: 33.2 | O(N^5))
    * *Intent:* # Verify the logger caught the specific recorder failures log_calls = [call[0][0] for call in mock_l...
  * `test_cicd_policy_enforcement_gates` (Impact: 32.2 | O(N^5))
    * *Intent:* # ============================================================================== # =================...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` or, re, logging, must, gitgalaxy.standards, unittest, name, gitgalaxy.galaxyscope...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 13.467 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.168 IQR)
- **Top Global Matches:** file_cluster_8: 13.467, file_cluster_17: 13.729, file_cluster_13: 13.743
- **Magnitude:** 805.88 | **LOC:** 1505 | **CtrlFlow:** 87.4% | **Authorship Centralization:** 60.9%
- **Algorithmic:** O(N^3) | **DB Complexity:** 4
- **Risk Profile:** Cognitive Load (62.5918%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 11.0 | O(N^3) | DB: 4)
  * `_parse_threat_score` (Impact: 7.3 | O(N^3))
  * `generate_artifacts` (Impact: 1.9 | O(N^2))
  * `_build_markdown` (Impact: 1.9 | O(N^2))
  * `_generate_sqlite_graph` (Impact: 1.9 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 319`, `structural_boundaries: 46`, `args: 30`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 743`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 13`, `doc: 27`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 5.655
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.014013
  * `Imports (Out-Degree: 0):` sqlite3, typing, logging, collections, json, gitgalaxy.standards, statistics, pathlib...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_yacc.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 678.9 | **LOC:** 92 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` extraction._extraction_harness, pytest, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 11.727 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.08 IQR)
- **Top Global Matches:** file_cluster_13: 11.727, file_cluster_8: 11.741, file_cluster_16: 11.984
- **Magnitude:** 639.08 | **LOC:** 458 | **CtrlFlow:** 60.6% | **Authorship Centralization:** 64.7%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 12
- **Risk Profile:** Cognitive Load (14.2661%), Tech Debt (14.7229%)
**Top Internal Functions/Classes:**
  * `_load_ignored_revs` (Impact: 448.1 | O(2^N) | DB: 12)
  * `_determine_commit_bounds` (Impact: 112.5 | O(N^6) | DB: 12)
  * `_initialize_history_scan` (Impact: 33.3 | O(N^5) | DB: 2)
  * `__init__` (Impact: 1.8 | O(N^2))
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 63`, `structural_boundaries: 41`, `args: 8`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `high_risk_execution: 1`, `state_mutation: 35`, `fragile_debt: 1`
* *Architecture:* `io: 8`, `api: 3`, `import: 8`
* *Defense:* `safety: 18`, `doc: 18`, `test: 1`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 5.655
  * `Choke Point (Betweenness):` 2e-05 | `Ripple Effect (Closeness):` 0.014013
  * `Imports (Out-Degree: 1):` typing, logging, gitgalaxy.standards, os, time, gitgalaxy.standards.config_resolver, subprocess, pathlib...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_makefile.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 608.25 | **LOC:** 331 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` typing, only, _extraction_harness, pytest, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 537.78 | **LOC:** 2013 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_detector_exact_loc_mapping` (Impact: 99.8 | O(N^2))
  * `test_detector_prose_and_empty_bypass` (Impact: 34.2 | O(N^3))
  * `test_spatial_mapper_sectorization_and_mo` (Impact: 27.2 | O(N^2))
    * *Intent:* # 2. TimeoutError -> Hardware Guillotine drops cleanly with patch.object( opt_detector, "_partition_...
  * `calculate_fibonacci` (Impact: 22.1 | O(2^N))
  * `test_detector_atomic_literal_shield` (Impact: 19.6 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.core.detector, math, re, gitgalaxy.standards.gitgalaxy_config, logging, pytest, gitgalaxy.core.spatial_mapper, gitgalaxy.core.prism...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 528.54 | **LOC:** 434 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` networkx, typing, numpy, collections, logging, gitgalaxy.standards.analysis_lens, pathlib, pandas...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/test_args_extraction_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 485.04 | **LOC:** 105 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pytest
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_java.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 473.26 | **LOC:** 400 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` java.util.List, statement, typing, only, _extraction_harness, java.util., com.example.MyClass, ......
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_scheme.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 451.31 | **LOC:** 135 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` _extraction_harness, pytest, sys, pathlib, gitgalaxy.standards.language_standards
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/dead_key_audit.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 405.36 | **LOC:** 371 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `visit_Call` (Impact: 104.3 | O(N^6))
    * *Intent:* """ if not isinstance(node, ast.JoinedStr) or not node.values: return None first = node.values[0] if...
  * `run_ci_check` (Impact: 92.4 | O(2^N) | DB: 3)
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
  * `Imports (Out-Degree: 0):` typing, ast, argparse, json, sys, pathlib
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 10.982 IQR)
- **Local Micro-Species:** `Cluster 3: Data Pipelines & I/O Operations` (Drift: 5.105 IQR)
- **Top Global Matches:** file_cluster_13: 10.982, file_cluster_8: 11.079, file_cluster_7: 11.473
- **Magnitude:** 358.6 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 58.3%
- **Algorithmic:** O(2^N) [Recursive] | **DB Complexity:** 12
- **Risk Profile:** Cognitive Load (18.3929%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 112.4 | O(N^4) | DB: 12)
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
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 5.487
  * `Choke Point (Betweenness):` 0.000182 | `Ripple Effect (Closeness):` 0.004484
  * `Imports (Out-Degree: 9):` gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge, sqlite3, gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge, typing, gitgalaxy.tools.cobol_to_cobol.cobol_lexical_patcher, gitgalaxy.tools.cobol_to_cobol.cobol_microservice_slicer, gitgalaxy.tools.cobol_to_cobol.cobol_system_limits_reporter...
  * `Imported By (In-Degree: 1):` (Excluded from Brief to save tokens)

### `tests/security_auditing/test_supply_chain_firewall.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 311.66 | **LOC:** 765 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_yaml_config_flag_actually_changes_s` (Impact: 38.2 | O(N^6) | DB: 3)
  * `test_behavioral_threat_evaluation` (Impact: 19.5 | O(N^6))
  * `test_tuple_import_handling` (Impact: 19.4 | O(N^6))
    * *Intent:* # ============================================================================== # TEST 10: THE ALLO...
  * `test_behavioral_threat_evaluation_strips` (Impact: 19.3 | O(N^6))
  * `test_density_dilution_fix_for_build_scri` (Impact: 19.3 | O(N^6))
    * *Intent:* # ============================================================================== # TEST 13: ISSUES #...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.metrics.signal_processor, multiprocessing, bypassed, json, pytest, policy, gitgalaxy.tools.supply_chain_security.supply_chain_firewall, gitgalaxy.standards.config_resolver...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_to_java_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 8.899 IQR)
- **Local Micro-Species:** `Cluster 3: Data Pipelines & I/O Operations` (Drift: 5.187 IQR)
- **Top Global Matches:** file_cluster_8: 8.899, file_cluster_13: 9.344, file_cluster_7: 9.491
- **Magnitude:** 298.58 | **LOC:** 338 | **CtrlFlow:** 55.3% | **Authorship Centralization:** 42.9%
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
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 2.966
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 6):` gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge, org.springframework.stereotype.Service, gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge, json, argparse, gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge, gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge, org.slf4j.LoggerFactory...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 290.32 | **LOC:** 1702 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Algorithmic:** O(N) | **DB Complexity:** 0
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_signal_processor_error_risk_floor` (Impact: 107.2 | O(N^3) | DB: 6)
    * *Intent:* # ============================================================================== # TEST 4: ERROR RIS...
  * `test_signal_processor_concurrency_thresh` (Impact: 24.0 | O(N^4) | DB: 10)
    * *Intent:* # ============================================================================== # TEST 49: CONCURRE...
  * `create_synthetic_star` (Impact: 23.9 | O(N^3) | DB: 1)
  * `test_signal_processor_zero_division_shie` (Impact: 8.4 | O(N^2))
    * *Intent:* # ============================================================================== # TEST 3: ZERO-DIVI...
  * `test_signal_processor_external_test_cove` (Impact: 6.8 | O(N^4))
    * *Intent:* # If it didn't crash, the _get_tier fallback successfully returned "tier3" and pulled the correct ph...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` identity, gitgalaxy.metrics.signal_processor, json, pytest, which, os, gitgalaxy.recorders.sarif_recorder, tempfile
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/spatial_mapper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 11.441 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.369 IQR)
- **Top Global Matches:** file_cluster_13: 11.441, file_cluster_16: 11.504, file_cluster_8: 11.59
- **Magnitude:** 254.06 | **LOC:** 230 | **CtrlFlow:** 61.7% | **Authorship Centralization:** 53.8%
- **Algorithmic:** O(N^6) | **DB Complexity:** 9
- **Risk Profile:** Cognitive Load (30.5977%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `map_repository` (Impact: 189.1 | O(N^6) | DB: 6)
  * `__init__` (Impact: 11.5 | O(N^3) | DB: 9)
  * `_hash_jitter` (Impact: 8.6 | O(N^3))
  * `_get_magnitude` (Impact: 8.3 | O(N^3))
  * `_calculate_spatial_clearance` (Impact: 2.9 | O(N^2))
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 29`, `structural_boundaries: 18`, `args: 6`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 9`, `state_mutation: 27`, `dead_code: 1`
* *Architecture:* `api: 4`, `import: 4`
* *Defense:* `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 3.638
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.014013
  * `Imports (Out-Degree: 0):` logging, hashlib, typing, math
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_13
- `gitgalaxy/metrics/chronometer.py` (PYTHON) | Magnitude: 639.08 | Delta: **0.014 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 63, structural_boundaries: 41, state_mutation: 35
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 254.06 | Delta: **0.063 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 128, branch: 29, state_mutation: 27, encapsulation: 23
- `gitgalaxy/core/network_risk_sensor.py` (PYTHON) | Magnitude: 1797.52 | Delta: **0.063 IQR** | Secondary Pull: `file_cluster_17`
  * Top Architectural Signatures: indent_spaces: 281, branch: 106, structural_boundaries: 45, safety_bypasses: 25
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 196.62 | Delta: **0.089 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 218, branch: 54, structural_boundaries: 50, state_mutation: 34
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 358.6 | Delta: **0.097 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 54, structural_boundaries: 52, state_mutation: 42

### Mixed-Responsibility Refactoring Targets for: file_cluster_16
- `gitgalaxy/core/prism.py` (PYTHON) | Magnitude: 909.92 | Delta: **0.064 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 398, branch: 126, state_mutation: 111, structural_boundaries: 74
- `gitgalaxy/core/spatial_correlation.py` (PYTHON) | Magnitude: 62.42 | Delta: **0.187 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 133, branch: 32, generics: 27, structural_boundaries: 19

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) | Magnitude: 144.34 | Delta: **0.073 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 269, state_mutation: 95, branch: 41, explicit_casts: 33
- `gitgalaxy/core/state_rehydrator.py` (PYTHON) | Magnitude: 20.0 | Delta: **0.088 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 54, structural_boundaries: 14, branch: 8, doc: 8
- `gitgalaxy/galaxyscope.py` (PYTHON) | Magnitude: 7653.96 | Delta: **0.115 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 1939, branch: 527, structural_boundaries: 216, state_mutation: 182
- `gitgalaxy/core/guidestar_lens.py` (PYTHON) | Magnitude: 252.3 | Delta: **0.122 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 286, branch: 90, structural_boundaries: 53, encapsulation: 41
- `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) | Magnitude: 1175.2 | Delta: **0.165 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 325, branch: 85, state_mutation: 60, structural_boundaries: 36

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **65.39%** | Cog Load: 62.5918% | Debt: 0.0%
- `action.yml` -> Churn: **54.32%** | Cog Load: 9.3427% | Debt: 99.876%
- `bitbucket-pipelines.yml` -> Churn: **52.5%** | Cog Load: 35.9722% | Debt: 99.4071%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/recorders/sbom_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 196.62
- `gitgalaxy/core/spatial_correlation.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 62.42

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/galaxyscope.py` -> **Severity: 0.138** (Bridge: 0.0017 * Flux: 79.6351%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.018** (Bridge: 0.0002 * Flux: 97.3782%)
- `gitgalaxy/recorders/sbom_recorder.py` -> **Severity: 0.016** (Bridge: 0.0002 * Flux: 97.3595%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.005** (Bridge: 0.0001 * Flux: 52.7609%)
- `gitgalaxy/security/security_auditor.py` -> **Severity: 0.004** (Bridge: 0.0 * Flux: 94.7128%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 3.844** (Embedded: 0.048 * Error Risk: 80.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 1.603** (Embedded: 0.022 * Error Risk: 72.9553%)
- `gitgalaxy/standards/language_standards.py` -> **Severity: 1.341** (Embedded: 0.2773 * Error Risk: 4.8377%)
- `gitgalaxy/recorders/sarif_recorder.py` -> **Severity: 1.133** (Embedded: 0.0179 * Error Risk: 63.1492%)
- `gitgalaxy/tools/ai_guardrails/ai_appsec_sensor.py` -> **Severity: 1.121** (Embedded: 0.014 * Error Risk: 80.0%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 2325.7** (Blast Radius: 23.257 * Doc Risk: 100.0%)
- `gitgalaxy/standards/language_standards.py` -> **Severity: 1602.818** (Blast Radius: 92.034 * Doc Risk: 17.4155%)
- `gitgalaxy/metrics/tensor_scanner.py` -> **Severity: 565.5** (Blast Radius: 5.655 * Doc Risk: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/cobol_compiler_forge.py` -> **Severity: 548.7** (Blast Radius: 5.487 * Doc Risk: 100.0%)
- `gitgalaxy/tools/network_auditing/full_api_network_map.py` -> **Severity: 532.967** (Blast Radius: 5.655 * Doc Risk: 94.247%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Act as a Principal Staff Engineer. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility). DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective, practical, and direct.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
