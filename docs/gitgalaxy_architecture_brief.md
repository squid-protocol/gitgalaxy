# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-08-07T12:08:03.084169+00:00` |
| **Scan Duration** | `8.79s` |
| **Git Branch** | `main` |
| **Git Commit** | `3ed0ed10eb8fc09e4b895a3a8dd28647d67bc8ee` |
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
| Total Artifacts | 746 |
| Analyzed Artifacts (Scanned) | 263 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 483 |
| Total LOC | 59047 |
| Volatility Index | 0.008 |
| % Scanned of codebase = | 35.3% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.5571 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.3293 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 2.69 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 37 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 225 | 58543 | 85.6% |
| MARKDOWN | 26 | 0 | 9.9% |
| YAML | 8 | 482 | 3.0% |
| PLAINTEXT | 3 | 0 | 1.1% |
| SHELL | 1 | 22 | 0.4% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `5.072`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| file_cluster_8 | 149 | 56.7% |
| file_cluster_13 | 59 | 22.4% |
| file_cluster_0 | 18 | 6.8% |
| file_cluster_16 | 7 | 2.7% |
| file_cluster_6 | 1 | 0.4% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 29 | 11.0% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 483*

**Composition by Extension & Reason:**
- `.md`: 344x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 41 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.yml`: 19x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 551 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `no_extension`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.json`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 61.5 | 2.3 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 96.0 | 6.5 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 100.0 | 1.6 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 3.9 | 0.0 | 0.0 |
| API Exposure | 0.0 | 8.1 | 0.2 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 27.8 | 0.3 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 6.5 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 9.8 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 11.3 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 9.1 | 0.4 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 60.9 | 3.1 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 89.1 | 2.2 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `bitbucket-pipelines.yml` (Hits: 10)
- `gitgalaxy/core/guidestar_lens.py` (Hits: 8)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **language_standards.py** (`gitgalaxy/standards/language_standards.py`) — 108 inbound connections
2. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 46 inbound connections
3. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 44 inbound connections
4. **config_resolver.py** (`gitgalaxy/standards/config_resolver.py`) — 9 inbound connections
5. **analysis_lens.py** (`gitgalaxy/standards/analysis_lens.py`) — 7 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 56 outbound dependencies
2. **test_python_strict.py** (`tests/extraction/languages/test_python_strict.py`) — 27 outbound dependencies
3. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 20 outbound dependencies
4. **test_embedded_python.py** (`tests/extraction/languages/test_embedded_python.py`) — 20 outbound dependencies
5. **test_scala.py** (`tests/extraction/languages/test_scala.py`) — 19 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_process_file_worker` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **1188.2** | LOC: 2805
- `ipc_rpc_bridges` (@ `gitgalaxy/standards/language_standards.py`) -> Impact: **416.7** | LOC: 679
- `_parse_pyproject_toml` (@ `gitgalaxy/security/manifest_parser.py`) -> Impact: **350.2** | LOC: 404
- `_resolve_target` (@ `gitgalaxy/core/network_risk_sensor.py`) -> Impact: **219.8** | LOC: 372
- `_tier_2_fingerprint_check` (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **209.7** | LOC: 394
  * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents generic files from bypassing deep-inspection. if ex...
- `_compile_regex_matrix` (@ `gitgalaxy/core/prism.py`) -> Impact: **175.7** | LOC: 396
  * *Intent:* # 4. GENERIC STRIPPER pattern = self.REGEX_MATRIX.get(family) if not pattern: # Restore mask tokens before returning if no pattern is registered code ...
- `audit` (@ `gitgalaxy/metrics/statistical_auditor.py`) -> Impact: **142.8** | LOC: 361
- `closures` (@ `gitgalaxy/standards/language_standards.py`) -> Impact: **128.7** | LOC: 493
- `extract_lineage` (@ `gitgalaxy/tools/cobol_to_cobol/cobol_dag_architect.py`) -> Impact: **106.0** | LOC: 181
  * *Intent:* """ Analyzes a COBOL program to map internal variables to external physical files. Utilizes shared IR state to mask out unreachable logic and prevent ...
- `_decode_comment_stream` (@ `gitgalaxy/core/detector.py`) -> Impact: **100.5** | LOC: 105

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `tests/extraction/languages` | 90 | 12631.82 | 3.26% | 0.0% |
| `tests/core_engine` | 16 | 1931.86 | 2.93% | 0.0% |
| `gitgalaxy` | 6 | 1735.82 | 8.61% | 0.0% |
| `gitgalaxy/standards` | 8 | 1606.14 | 9.78% | 18.52% |
| `gitgalaxy/core` | 9 | 1300.86 | 16.06% | 4.06% |
| `gitgalaxy/recorders` | 8 | 1121.76 | 20.59% | 1.81% |
| `tests/security_auditing` | 15 | 1001.6 | 2.0% | 0.0% |
| `tests/extraction` | 8 | 796.58 | 3.71% | 0.0% |
| `gitgalaxy/security` | 5 | 780.0 | 14.49% | 0.0% |
| `gitgalaxy/metrics` | 5 | 659.06 | 16.83% | 4.57% |

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

*No critical vulnerabilities or security lens thresholds breached.*

## 10.7 ECOSYSTEM SECURITY AUDITS
> **AI CONTEXT:** High-level perimeter defense metrics from the X-Ray, Supply Chain Firewall, and API Network Mapper.

### ☢️ X-Ray & 🧱 Supply Chain Firewall
- **Binary Anomalies (X-Ray):** `0` (High entropy, packed payloads, or magic byte mismatches).
- **Blacklisted Dependencies:** `0` explicitly banned packages imported.
- **Unknown Dependencies:** `1501` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **496.62**
- **Archetype:** `file_cluster_16` (Distance: 11.995 IQR)
- **Magnitude:** 396.72 | **LOC:** 744 | **CtrlFlow:** 63.0% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.9826%), Safety Score (85.0024%), Verification (80.0%)
- **Heaviest Functions:** `_compile_regex_matrix` (Impact: 175.7), `split_streams` (Impact: 45.2), `_strip_segment_comments` (Impact: 26.1)

### 2. `gitgalaxy/core/spatial_mapper.py` (PYTHON) -> Cumulative Risk: **460.8**
- **Archetype:** `file_cluster_13` (Distance: 11.242 IQR)
- **Magnitude:** 102.46 | **LOC:** 230 | **CtrlFlow:** 61.7% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.71%), Safety Score (83.7428%), Verification (80.0%)
- **Heaviest Functions:** `map_repository` (Impact: 52.1), `__init__` (Impact: 6.3), `_hash_jitter` (Impact: 4.5)

### 3. `gitgalaxy/recorders/llm_recorder.py` (PYTHON) -> Cumulative Risk: **460.15**
- **Archetype:** `file_cluster_8` (Distance: 13.325 IQR)
- **Magnitude:** 751.7 | **LOC:** 1408 | **CtrlFlow:** 85.8% | **Authorship Centralization:** 90.9%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (96.0109%), Cognitive Load (61.5445%)
- **Heaviest Functions:** `__init__` (Impact: 5.8), `_parse_threat_score` (Impact: 3.9), `generate_artifacts` (Impact: 1.4)

### 4. `gitgalaxy/tools/cobol_to_java/cobol_to_java_service_forge.py` (PYTHON) -> Cumulative Risk: **447.81**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.06 | **LOC:** 97 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `generate_service_skeleton` (Impact: 14.3), `main` (Impact: 6.3)

### 5. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **439.84**
- **Archetype:** `file_cluster_8` (Distance: 11.066 IQR)
- **Magnitude:** 243.3 | **LOC:** 536 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.3259%), Safety Score (82.0925%), Verification (80.0%)
- **Heaviest Functions:** `audit` (Impact: 142.8), `_is_dead_code` (Impact: 9.8), `_is_threat` (Impact: 9.5)

### 6. `gitgalaxy/metrics/chronometer.py` (PYTHON) -> Cumulative Risk: **428.64**
- **Archetype:** `file_cluster_13` (Distance: 11.491 IQR)
- **Magnitude:** 165.68 | **LOC:** 458 | **CtrlFlow:** 60.6% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (94.9042%), Verification (80.0%), Safety Score (65.0816%)
- **Heaviest Functions:** `_load_ignored_revs` (Impact: 74.0), `_determine_commit_bounds` (Impact: 34.6), `_initialize_history_scan` (Impact: 12.5)

### 7. `gitgalaxy/core/detector.py` (PYTHON) -> Cumulative Risk: **421.56**
- **Archetype:** `file_cluster_8` (Distance: 11.126 IQR)
- **Magnitude:** 366.44 | **LOC:** 2557 | **CtrlFlow:** 72.6% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Verification (80.0%), Churn (60.91%), Safety Score (59.5384%)
- **Heaviest Functions:** `_decode_comment_stream` (Impact: 100.5), `_extract_name` (Impact: 67.6), `_extract_documentation_tether` (Impact: 42.4)

### 8. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **417.98**
- **Archetype:** `file_cluster_8` (Distance: 12.057 IQR)
- **Magnitude:** 1422.64 | **LOC:** 3055 | **CtrlFlow:** 71.1% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Verification (80.0%), State Flux (79.3689%), Safety Score (63.071%)
- **Heaviest Functions:** `_process_file_worker` (Impact: 1188.2), `execution_timeout_failsafe` (Impact: 1.9), `_init_worker` (Impact: 1.4)

### 9. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **410.18**
- **Archetype:** `file_cluster_13` (Distance: 10.741 IQR)
- **Magnitude:** 189.4 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 50.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (97.3782%), Verification (80.0%), Safety Score (68.5044%)
- **Heaviest Functions:** `main` (Impact: 50.1), `process_payload` (Impact: 26.8), `record_dead_code` (Impact: 14.4)

### 10. `gitgalaxy/core/network_risk_sensor.py` (PYTHON) -> Cumulative Risk: **409.12**
- **Archetype:** `file_cluster_13` (Distance: 11.15 IQR)
- **Magnitude:** 263.22 | **LOC:** 442 | **CtrlFlow:** 68.1% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), Verification (80.0%), Safety Score (75.2899%), State Flux (61.6241%)
- **Heaviest Functions:** `_resolve_target` (Impact: 219.8), `_build_resolution_map` (Impact: 9.6), `__init__` (Impact: 5.3)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 12.057 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.573 IQR)
- **Top Global Matches:** file_cluster_8: 12.057, file_cluster_13: 12.185, file_cluster_7: 12.45
- **Magnitude:** 1422.64 | **LOC:** 3055 | **CtrlFlow:** 71.1% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (20.7786%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_process_file_worker` (Impact: 1188.2)
  * `execution_timeout_failsafe` (Impact: 1.9)
    * *Intent:* """ Hardware-level OS interrupt for Catastrophic Backtracking (ReDoS) protection. Registered via the...
  * `_init_worker` (Impact: 1.4)
    * *Intent:* """ raise TimeoutError("Structural Saturation (ReDoS Timeout)") def _init_worker( root_str: str, con...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 531`, `structural_boundaries: 216`, `args: 32`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 77`, `state_mutation: 182`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 3`, `import: 63`
* *Defense:* `safety: 73`, `doc: 36`, `test: 2`, `cleanup: 6`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 4.782
  * `Choke Point (Betweenness):` 0.001258 | `Ripple Effect (Closeness):` 0.01145
  * `Imports (Out-Degree: 30):` gitgalaxy.core.prism, os, gitgalaxy.tools.network_auditing.full_api_network_map, gitgalaxy.core.state_rehydrator, multiprocessing, pathlib, gitgalaxy.metrics.chronometer, gitgalaxy.recorders.sbom_recorder...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_powershell_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 983.67 | **LOC:** 479 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, sys, pytest, _strict_harness
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_objectivec_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 971.43 | **LOC:** 265 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, sys, pytest, _strict_harness
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_standards.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 964.2 | **LOC:** 12686 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `ipc_rpc_bridges` (Impact: 416.7)
  * `closures` (Impact: 128.7)
  * `r` (Impact: 18.4)
    * *Intent:* # BUG FIX (epic #813/#843): the bare capture class required the value to start # immediately with an...
  * `globals` (Impact: 15.8)
    * *Intent:* # 18. globals: Global / Shared State. Magic variables and system globals. # BUG FIX: `$$`, `$@`, `$!...
  * `serialization_parsing` (Impact: 5.1)
    * *Intent:* # --- PHASE 3: HYBRID DOMAIN SENSORS (Dockerfile Specifics) --- # CRITICAL GUARDRAIL: all four senso...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` form, inside, type, file, typing, scala.util., was, keyword....
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_tcl_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 831.22 | **LOC:** 273 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, sys, _strict_harness, pytest, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_solidity_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 802.93 | **LOC:** 273 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` legacy, gitgalaxy.standards.language_standards, pathlib, sys, pytest, _strict_harness
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 13.325 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.139 IQR)
- **Top Global Matches:** file_cluster_8: 13.325, file_cluster_17: 13.566, file_cluster_13: 13.571
- **Magnitude:** 751.7 | **LOC:** 1408 | **CtrlFlow:** 85.8% | **Authorship Centralization:** 90.9%
- **Risk Profile:** Cognitive Load (61.5445%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `__init__` (Impact: 5.8)
  * `_parse_threat_score` (Impact: 3.9)
  * `generate_artifacts` (Impact: 1.4)
  * `_build_markdown` (Impact: 1.4)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 296`, `structural_boundaries: 49`, `args: 27`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 702`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 13`, `doc: 27`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.577
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.011927
  * `Imports (Out-Degree: 0):` statistics, logging, pathlib, typing, json, sqlite3, gitgalaxy.standards, heapq...
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
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, sys, pytest, extraction._extraction_harness
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_ruby_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 645.28 | **LOC:** 249 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, sys, pytest, _strict_harness
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
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, typing, sys, _extraction_harness, pytest, only
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_yaml_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 596.6 | **LOC:** 384 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, sys, this, and, pytest, _strict_harness
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

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
  * `Imports (Out-Degree: 0):` os, logging, pathlib, json, typing, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 488.06 | **LOC:** 2075 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_git_null_byte_path_injection` (Impact: 75.8)
    * *Intent:* # When entering the context manager, return our mock instance # Mock Path.exists to pass the initial...
  * `_clean` (Impact: 68.5)
    * *Intent:* # ============================================================================== # TEST 6: THE NULL-...
  * `test_recorder_exception_survivability` (Impact: 20.1)
  * `test_sarif_ignored_paths_sanitization` (Impact: 13.7)
  * `test_delta_scanning_fallbacks` (Impact: 13.4)
    * *Intent:* # ============================================================================== # TEST 21: GIT META...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` os, pathlib, passes, concurrent.futures, yaml, unittest.mock, unittest, failure...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/test_args_extraction.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 485.04 | **LOC:** 105 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
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

### `tests/extraction/languages/test_java.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 473.26 | **LOC:** 400 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` com.example.MyClass, gitgalaxy.standards.language_standards, pathlib, typing, sys, static, java.util., statement...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 472.06 | **LOC:** 2103 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_detector_exact_loc_mapping` (Impact: 69.5)
    * *Intent:* # The AppSec multiplier adds (cascading_flux * 2). Total should be >= 3. assert res_oom["equations"]...
  * `test_detector_catastrophic_fallbacks` (Impact: 35.8)
  * `test_detector_nested_function_is_counted` (Impact: 28.7)
    * *Intent:* # forgotten_orphan and main_process (never called, name > 3 chars) both flag as orphans. assert resu...
  * `test_detector_explicit_type_override` (Impact: 22.8)
    * *Intent:* # TEST 19: HARDWARE GUILLOTINE (REGEX CATCH BLOCK) # ===============================================...
  * `test_detector_atomic_literal_shield` (Impact: 14.4)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.core.prism, gitgalaxy.core.spatial_mapper, logging, math, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, unittest.mock, pytest...
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
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, pathlib, sys, _extraction_harness, pytest
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_16` (Drift: 11.995 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 5.222 IQR)
- **Top Global Matches:** file_cluster_16: 11.995, file_cluster_8: 12.059, file_cluster_13: 12.236
- **Magnitude:** 396.72 | **LOC:** 744 | **CtrlFlow:** 63.0% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (42.2887%), Tech Debt (16.2747%)
**Top Internal Functions/Classes:**
  * `_compile_regex_matrix` (Impact: 175.7)
    * *Intent:* # 4. GENERIC STRIPPER pattern = self.REGEX_MATRIX.get(family) if not pattern: # Restore mask tokens ...
  * `split_streams` (Impact: 45.2)
  * `_strip_segment_comments` (Impact: 26.1)
    * *Intent:* # 3. Derive the documentation lines by subtracting code from the active total. # This forces mutual ...
  * `_strip_single_line_comments` (Impact: 11.1)
    * *Intent:* # 2. Modern Inline Fortran (!), COBOL (*>), and ABAP (") comments if "*>" in line: parts = line.spli...
  * `strip_callback` (Impact: 4.2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 126`, `structural_boundaries: 74`, `args: 24`, `func_start: 20`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 22`, `state_mutation: 111`, `fragile_debt: 2`
* *Architecture:* `api: 12`, `import: 4`
* *Defense:* `safety: 4`, `doc: 34`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 3.625
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.015267
  * `Imports (Out-Degree: 1):` gitgalaxy.standards.language_standards, typing, re, logging
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.126 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.296 IQR)
- **Top Global Matches:** file_cluster_8: 11.126, file_cluster_16: 11.378, file_cluster_13: 11.487
- **Magnitude:** 366.44 | **LOC:** 2557 | **CtrlFlow:** 72.6% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (20.0151%), Tech Debt (9.6922%)
**Top Internal Functions/Classes:**
  * `_decode_comment_stream` (Impact: 100.5)
  * `_extract_name` (Impact: 67.6)
    * *Intent:* # 1. Apply the shield to the ENTIRE string, preserving newline counts.
  * `_extract_documentation_tether` (Impact: 42.4)
  * `_build_indentation_safe_stream` (Impact: 7.9)
  * `index_aligned_shield` (Impact: 7.1)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 447`, `structural_boundaries: 169`, `args: 26`, `func_start: 24`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 50`, `state_mutation: 83`, `dead_code: 6`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `api: 14`, `concurrency: 1`, `import: 12`
* *Defense:* `safety: 39`, `doc: 73`, `test: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 3.455
  * `Choke Point (Betweenness):` 6.3e-05 | `Ripple Effect (Closeness):` 0.015267
  * `Imports (Out-Degree: 3):` logging, math, bisect, gitgalaxy.standards.language_standards, typing, gitgalaxy.standards.analysis_lens, tiktoken, gitgalaxy.core.spatial_correlation...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 338.86 | **LOC:** 1145 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_tier_2_fingerprint_check` (Impact: 209.7)
    * *Intent:* # DEFENSIVE GUARD: Collisions cannot be locked at Tier 1 based on extension alone. # This prevents g...
  * `_detect_hybrids` (Impact: 28.8)
  * `_calibrate_lookup_maps` (Impact: 21.9)
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
  * `Imports (Out-Degree: 0):` logging, math, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, pathlib, typing, time, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_13` (Drift: 11.15 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.794 IQR)
- **Top Global Matches:** file_cluster_13: 11.15, file_cluster_8: 11.27, file_cluster_17: 11.283
- **Magnitude:** 263.22 | **LOC:** 442 | **CtrlFlow:** 68.1% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (18.2198%), Tech Debt (10.5488%)
**Top Internal Functions/Classes:**
  * `_resolve_target` (Impact: 219.8)
  * `_build_resolution_map` (Impact: 9.6)
  * `__init__` (Impact: 5.3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 96`, `structural_boundaries: 45`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 25`, `state_mutation: 19`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 10`
* *Defense:* `safety: 21`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 5.087
  * `Choke Point (Betweenness):` 1.9e-05 | `Ripple Effect (Closeness):` 0.015267
  * `Imports (Out-Degree: 1):` logging, math, token, warnings, pathlib, typing, gitgalaxy.standards.analysis_lens, networkx...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 11.066 IQR)
- **Local Micro-Species:** `Cluster 1: Declarative Glue & Initialization` (Drift: 4.422 IQR)
- **Top Global Matches:** file_cluster_8: 11.066, file_cluster_16: 11.236, file_cluster_13: 11.282
- **Magnitude:** 243.3 | **LOC:** 536 | **CtrlFlow:** 70.2% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (39.0051%), Tech Debt (0.0%)
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.577
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.011927
  * `Imports (Out-Degree: 0):` os, statistics, logging, math, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 214.28 | **LOC:** 1405 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_signal_processor_error_risk_floor` (Impact: 70.5)
    * *Intent:* # ============================================================================== # TEST 4: ERROR RIS...
  * `test_signal_processor_concurrency_thresh` (Impact: 13.4)
  * `create_synthetic_star` (Impact: 13.3)
  * `test_signal_processor_zero_division_shie` (Impact: 5.8)
    * *Intent:* # ============================================================================== # TEST 3: ZERO-DIVI...
  * `test_signal_processor_ecosystem_native_m` (Impact: 4.4)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` os, identity, logging, gitgalaxy.recorders.sarif_recorder, json, tempfile, gitgalaxy.metrics.signal_processor, pytest...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

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
  * `Imports (Out-Degree: 0):` logging, pathlib, numpy, typing, networkx, gitgalaxy.standards.analysis_lens, pandas, xgboost...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_livecode_strict.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 196.88 | **LOC:** 643 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `Imports (Out-Degree: 0):` multiprocessing, gitgalaxy.standards.language_standards, pathlib, sys, _strict_harness, pytest, shapes, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

### Mixed-Responsibility Refactoring Targets for: file_cluster_13
- `gitgalaxy/metrics/chronometer.py` (PYTHON) | Magnitude: 165.68 | Delta: **0.011 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 63, structural_boundaries: 41, state_mutation: 35
- `gitgalaxy/core/spatial_mapper.py` (PYTHON) | Magnitude: 102.46 | Delta: **0.061 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 128, branch: 29, state_mutation: 27, encapsulation: 23
- `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) | Magnitude: 89.84 | Delta: **0.071 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 223, branch: 56, structural_boundaries: 50, state_mutation: 34
- `gitgalaxy/cobol_refractor_controller.py` (PYTHON) | Magnitude: 189.4 | Delta: **0.095 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 259, branch: 54, structural_boundaries: 52, state_mutation: 42
- `gitgalaxy/metrics/tensor_scanner.py` (PYTHON) | Magnitude: 66.94 | Delta: **0.108 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 80, structural_boundaries: 27, branch: 25, doc: 10

### Mixed-Responsibility Refactoring Targets for: file_cluster_16
- `gitgalaxy/core/prism.py` (PYTHON) | Magnitude: 396.72 | Delta: **0.064 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 398, branch: 126, state_mutation: 111, structural_boundaries: 74
- `gitgalaxy/core/spatial_correlation.py` (PYTHON) | Magnitude: 44.42 | Delta: **0.189 IQR** | Secondary Pull: `file_cluster_8`
  * Top Architectural Signatures: indent_spaces: 133, branch: 32, generics: 27, structural_boundaries: 19

### Mixed-Responsibility Refactoring Targets for: file_cluster_8
- `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) | Magnitude: 126.04 | Delta: **0.076 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 269, state_mutation: 95, branch: 41, explicit_casts: 33
- `gitgalaxy/core/state_rehydrator.py` (PYTHON) | Magnitude: 13.9 | Delta: **0.092 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 54, structural_boundaries: 14, branch: 8, doc: 8
- `gitgalaxy/core/guidestar_lens.py` (PYTHON) | Magnitude: 101.7 | Delta: **0.128 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 286, branch: 90, structural_boundaries: 53, encapsulation: 41
- `gitgalaxy/galaxyscope.py` (PYTHON) | Magnitude: 1422.64 | Delta: **0.128 IQR** | Secondary Pull: `file_cluster_13`
  * Top Architectural Signatures: indent_spaces: 1948, branch: 531, structural_boundaries: 216, state_mutation: 182
- `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) | Magnitude: 243.3 | Delta: **0.17 IQR** | Secondary Pull: `file_cluster_16`
  * Top Architectural Signatures: indent_spaces: 325, branch: 85, state_mutation: 60, structural_boundaries: 36

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **52.37%** | Cog Load: 61.5445% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 1422.64
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (90.9% isolated ownership) | Magnitude: 751.7
- `gitgalaxy/core/prism.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 396.72
- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 366.44
- `gitgalaxy/core/network_risk_sensor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 263.22

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/galaxyscope.py` -> **Severity: 0.1** (Bridge: 0.0013 * Flux: 79.3689%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.013** (Bridge: 0.0001 * Flux: 97.3782%)
- `gitgalaxy/recorders/sbom_recorder.py` -> **Severity: 0.01** (Bridge: 0.0001 * Flux: 96.9481%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.003** (Bridge: 0.0001 * Flux: 48.6304%)
- `gitgalaxy/security/security_auditor.py` -> **Severity: 0.003** (Bridge: 0.0 * Flux: 94.7128%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/language_standards.py` -> **Severity: 20.257** (Embedded: 0.4142 * Error Risk: 48.9079%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 1.911** (Embedded: 0.0409 * Error Risk: 46.7319%)
- `gitgalaxy/standards/gitgalaxy_config.py` -> **Severity: 1.814** (Embedded: 0.0323 * Error Risk: 56.2559%)
- `gitgalaxy/metrics/signal_processor.py` -> **Severity: 1.467** (Embedded: 0.0258 * Error Risk: 56.9341%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 1.398** (Embedded: 0.0239 * Error Risk: 58.6062%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/language_standards.py` -> **Severity: 2195.442** (Blast Radius: 123.154 * Doc Risk: 17.8268%)
- `gitgalaxy/standards/analysis_lens.py` -> **Severity: 343.593** (Blast Radius: 20.178 * Doc Risk: 17.0281%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 336.616** (Blast Radius: 18.826 * Doc Risk: 17.8804%)
- `scripts/update_golden_masters.sh` -> **Severity: 213.966** (Blast Radius: 2.401 * Doc Risk: 89.1154%)
- `gitgalaxy/standards/gitgalaxy_config.py` -> **Severity: 186.189** (Blast Radius: 10.413 * Doc Risk: 17.8804%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Stay in the Senior Technical Storyteller persona from Section 1. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility) woven into a cohesive narrative -- not a dry, disconnected bullet-point audit. DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective and factual, but write like you're explaining the codebase to a colleague, not filing a verdict.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
