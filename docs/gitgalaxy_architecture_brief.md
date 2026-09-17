# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Git Remote** | `https://github.com/squid-protocol/gitgalaxy` |
| **Zero-Dependency Mode** | `Inactive (Full Precision)` |

## 0.5 AI THREAT AUDIT STATUS
> **✅ SECURE_NO_THREATS_DETECTED**
> XGBoost Structural Signatures model found no malicious artifacts.

## 1. SYSTEM ROLE & PHILOSOPHY
> You are a Senior Technical Storyteller and Codebase Architect. GitGalaxy has translated the non-visual architecture of this repository into measurable Structural Signatures (regex-derived counts, not an AST or compiler pass). Your job is to weave those signatures into a coherent, factual narrative about how this system is built -- its architecture, design patterns, and complexity -- not to render a verdict.
> 
> **CORE DIRECTIVES:**
> 1. **Narrate the Architecture, Don't Judge the Author:** Frame every observation as a blameless description of the system's physical reality. A high Structural Surface Profile reading (formerly called Risk Exposure; e.g., Complexity Load, formerly Cognitive Load Exposure) describes where the architecture may be drifting into fragile territory, not developer incompetence -- it is a prompt to investigate, never a verdict. These are activity/content surface meters, not defect-probability estimates (gitgalaxy#2991, evidence in #2982) -- describe what is there, don't imply it predicts a bug.
> 2. **The Physical Reality Rule:** Base your narrative strictly on the provided Structural Signatures and the numbers derived from them. Do not hallucinate meaning, and do not restate a heuristic's raw label (e.g. a 'Logic Bomb' or 'O(2^N)' flag) as a confirmed finding of malice or a guaranteed defect -- explain what the signature actually measures, weave it into the story of the file, and let the reader draw their own conclusion.
> 3. **Risk vs. Defense:** Code is a balance. A file with high `flux` (state mutation) is risky unless balanced by `freeze_hits` (immutability). High `danger` is brittle unless wrapped in `safety`. Tell that balance as part of the narrative, not as an isolated alarm.
> 
> **THE STRUCTURAL SIGNATURE LEXICON:**
> * **Structure & Mass:** `branch` (splits), `linear` (paths), `args` (coupling), `func_start` (entry points).
> * **Risk & Volatility:** `danger` (dynamic execution), `flux` (state mutation), `graveyard` (commented-out logic), `safety_neg` (security bypasses).
> * **Architecture & Domain:** `io` (network latency), `concurrency` (async orchestration), `api` (public surface), `import` (dependencies).
> * **Defensive Guardrails:** `safety` (Error handling), `freeze_hits` (immutability), `cleanup` (state destruction).
## 2. THE 13-POINT STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (EQUATIONS & CONTEXT)
> **How the SAST Engine Calculates the Structural Surface Profile (Lower 0 - Higher Surface Presence 100%):**
> Most scores use a Sigmoid curve based on density (Hits / LOC) to prevent massive files from mathematically hiding their flaws. These 13 vectors are activity/content surface meters -- they describe what is present in a file, not the probability of a defect. The temporal-crucible validation record (gitgalaxy#2982, ~3,550 scanned snapshots, two repositories, pre-registered) tested the per-file-standing-risk claim to exhaustion and found it does not hold; see docs/vectors.md for the full record and gitgalaxy#2991 for the rename this drove. `risk_*` names remain the underlying column/key names for schema compatibility -- see the 'formerly' aliases below.
> 
> 1. **Complexity Load** (formerly Cognitive Load Exposure)**:** Measures the mental effort required for a developer to read and understand the file. `Density(Branches + (Flux * 2) + Async/Danger)` mitigated by `Doc Coverage`.
> 2. **Guard Balance** (formerly Error & Exception Risk Exposure)**:** Measures structural integrity and resilience against runtime errors. `Net Exposure = (Danger + Safety_Neg + Flux) - (Safety + Tests + Docs)`.
> 3. **Debt Markers** (formerly Tech Debt Exposure)**:** Measures the density of developer-annotated structural stress. `Density(TODOs [1x] + FIXMEs/Hacks [3x] + Empty Stubs [0.5x])`.
> 4. **Test Surface** (formerly Verification Risk Exposure)**:** Evaluates test coverage by comparing a function's structural complexity against the scope of the tests validating it.
> 5. **Connectivity** (formerly API Risk Exposure)**:** Measures the public surface area of a module. `Ratio(API Hits / Total Functions & Classes)`.
> 6. **Concurrency Surface** (formerly Concurrency Risk Exposure)**:** Measures the density of asynchronous operations, threading, and parallel execution logic.
> 7. **Mutation Surface** (formerly State Flux Risk Exposure)**:** Measures the frequency of data mutation and variable reassignment.
> 8. **Dead Code Surface** (formerly Commented Logic (dead code))**:** Measures the presence of abandoned, commented-out logic blocks.
> 9. **Spec Alignment** (formerly Spec Match Risk Exposure)**:** Measures how closely code aligns with formal specifications or architectural requirements.
> 10. **Historical Stability** (formerly Stability; predictive layer, promotion pending #2987)**:** Measures the recency of edits relative to the repository's entire lifespan. Part of the family the validation record actually supports as predictive -- currently ablated to zero in every scan (`GITGALAXY_DISABLE_GIT_HISTORY`, temporal-crucible#29).
> 11. **Historical Churn** (formerly Deep Churn; predictive layer, promotion pending #2987)**:** Measures the historical volatility and frequency of modification. Same predictive-layer status and ablation caveat as Historical Stability above.
> 12. **Documentation Surface** (formerly Documentation Risk Exposure)**:** Of the units extracted from a file, the weight-share a reader cannot recover from documentation -- public units count double, runtime-dynamic units count more, and a folder-level documentation umbrella shields the whole file. A ratio over units, not a density over lines; files with no extracted units have no value.
> 13. **Indentation Consistency:** Measures formatting alignment (Tabs vs. Spaces). Provided for codebase standardization context, not a functional risk.
> 
> **--- THE SECURITY & VULNERABILITY LENS ---**
> 14. **Obfuscation & Evasion Risk:** Measures the density of obfuscated logic, packed strings, and non-standard encoding.
> 15. **Logic Bomb / Sabotage Risk:** Measures condition-heavy execution leading to destructive OS, memory, or process commands.
> 16. **Injection Surface Risk Exposure:** Measures external network/I/O input flowing directly into dynamic execution contexts (XSS, SQLi, RCE).
> 17. **Memory Corruption Risk Exposure:** Measures the density of raw pointer math and manual memory allocations (Buffer Overflows, UAF).
> 18. **Credential Material** (formerly Secrets Risk Exposure)**:** Measures the presence of hardcoded credentials exposed to logs or globals.
> 
> **--- STRUCTURAL MAGNITUDE (NOT RISK) ---**
> **19. Function Magnitude (Impact Score):** Measures the physical footprint and 'heaviness' of a specific function. `((BranchHits + 1) * (Args + 1) + (0.05 * LOC)) * 10`. This is NOT a risk score.
> **20. File Magnitude (Total Impact):** Measures the total structural impact of a file. `Sum(Function Impacts) + API + Concurrency + Flux + (LOC / 50)`. This is NOT a risk score.

## 3. MACRO STATE
| Metric | Value |
|---|---|
| Total Artifacts | 1036 |
| Analyzed Artifacts (Scanned) | 419 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 617 |
| Total LOC | 89382 |
| Volatility Index | 0.002 |
| % Scanned of codebase = | 40.4% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.6721 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.3145 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 1.8193 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 45 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 373 | 88147 | 89.0% |
| MARKDOWN | 29 | 0 | 6.9% |
| YAML | 11 | 1008 | 2.6% |
| PLAINTEXT | 3 | 0 | 0.7% |
| SHELL | 2 | 84 | 0.5% |
| MAKEFILE | 1 | 143 | 0.2% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `2.272`
> **Composition Archetype:** `Hub-Coupled App` (z +0.81; from the repo's file-archetype mix)
> **File Composition:** Defensive Guards Files 28%, Declarative / Non-Code 17%, Large Core Modules 15%, Data / Markup / Trivial 13%, Tests & Verification Files 8%
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 387 | 92.4% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 32 | 7.6% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 617*

**Composition by Extension & Reason:**
- `.md`: 427x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 41 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.json`: 45x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yml`: 23x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 604 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `no_extension`: 7x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csv`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.xml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.jsonl`: 1x Excluded (Saturation: Line 1 exceeds 500 chars)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 84.3 | 3.4 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 99.9 | 6.4 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 98.8 | 0.7 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 3.8 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 54.2 | 1.0 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 23.1 | 0.2 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 6.6 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 11.6 | 0.1 | 0.0 | 0.0 |
| Spec Alignment (formerly Specification Exposure) | 0.0 | 100.0 | 6.7 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 15.0 | 0.1 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 100.0 | 2.4 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) | 0.0 | 50.0 | 1.4 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 351 | 21 | 0 | `gitgalaxy/galaxyscope.py` |
| cleanup | 16 | 7 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 561 | 24 | 0 | `gitgalaxy/core/detector.py` |
| danger | 544 | 23 | 0 | `gitgalaxy/core/detector.py` |
| concurrency | 16 | 8 | 0 | `gitgalaxy/core/graph_engine.py` |
| connectivity | 136 | 23 | 0 | `gitgalaxy/core/detector.py` |
| io | 77 | 21 | 0 | `gitgalaxy/galaxyscope.py` |
| crypto | 2 | 2 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 31 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 48 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 165 | 8 | 0 | `gitgalaxy/core/detector.py` |
| events | 252 | 17 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 5 | 3 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 362 | 27 | 0 | `gitgalaxy/core/detector.py` |
| debt | 157 | 17 | 0 | `gitgalaxy/core/detector.py` |
| mutation | 8734 | 26 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 64 | 6 | 0 | `gitgalaxy/core/detector.py` |
| credential | 2 | 2 | 0 | `gitgalaxy/core/detector.py` |
| threat | 58 | 11 | 0 | `gitgalaxy/metrics/signal_processor.py` |
| ml_ai | 0 | 0 | 0 | - |
| ui | 1 | 1 | 0 | `gitgalaxy/recorders/llm_recorder.py` |

**Relations (repo medians):**
- `guard_balance_ratio` (guards / (danger + 1)): **0.0**
- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **0.0**

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `bitbucket-pipelines.yml` (Hits: 10)
- `gitgalaxy/core/guidestar_lens.py` (Hits: 8)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 64 inbound connections
2. **json.py** (`gitgalaxy/standards/language_standards/languages/json.py`) — 62 inbound connections
3. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 49 inbound connections
4. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 47 inbound connections
5. **detector.py** (`gitgalaxy/core/detector.py`) — 44 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 60 outbound dependencies
2. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 30 outbound dependencies
3. **test_import_contract_2875.py** (`tests/extraction/languages/test_import_contract_2875.py`) — 30 outbound dependencies
4. **test_python_strict.py** (`tests/extraction/languages/test_python_strict.py`) — 27 outbound dependencies
5. **test_network_risk_sensor.py** (`tests/security_auditing/test_network_risk_sensor.py`) — 22 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1150.2** | LOC: 1308
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **890.7** | LOC: 1146
- `splice` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **415.3** | LOC: 782
- `inspect` **(Many-Argument Workhorses)** (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **353.2** | LOC: 405
- `_calculate_block_metrics` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **322.8** | LOC: 470
- `generate_report` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/audit_recorder.py`) -> Impact: **300.6** | LOC: 524
- `execute_pipeline` **(Many-Argument Workhorses)** (@ `gitgalaxy/galaxyscope.py`) -> Impact: **267.6** | LOC: 607
  * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execution Flow): The method enforces a strict chronologi...
- `calculate_risk_vector` **(Many-Argument Workhorses)** (@ `gitgalaxy/metrics/signal_processor.py`) -> Impact: **253.2** | LOC: 636
- `_slice_by_keywords` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **248.9** | LOC: 427
- `measure` **(Many-Argument Workhorses)** (@ `tests/tools/tree_sitter_accuracy_audit.py`) -> Impact: **217.8** | LOC: 477
  * *Intent:* """Runs the full pinned-corpus scan + tree-sitter diff, returns the metrics dict."""

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `tests/extraction/languages` | 109 | 14165.22 | 12.68% | 0.0% |
| `gitgalaxy/core` | 11 | 12755.14 | 36.4% | 15.59% |
| `tests/core_engine` | 38 | 7205.38 | 13.56% | 0.0% |
| `gitgalaxy/recorders` | 8 | 4607.08 | 47.42% | 4.13% |
| `gitgalaxy/metrics` | 6 | 3323.36 | 43.94% | 13.22% |
| `gitgalaxy` | 6 | 3161.8 | 32.68% | 0.0% |
| `tests/security_auditing` | 15 | 1789.56 | 12.11% | 0.0% |
| `gitgalaxy/standards` | 9 | 1757.4 | 12.68% | 6.32% |
| `gitgalaxy/security` | 5 | 1501.78 | 30.19% | 2.84% |
| `gitgalaxy/standards/language_standards/languages` | 64 | 1393.4 | 6.02% | 63.67% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `gitgalaxy/core/rule_prefilter.py` -> **98.8145%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **56.15%** Exposure
- `gitgalaxy/core/prism.py` -> **45.3591%** Exposure
- `gitgalaxy/core/detector.py` -> **27.2754%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **14.4232%** Exposure
### Highest Mutation Surface (formerly State Flux; Mutation/Volatility)
- `.claude/hooks/pytest_quiet.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/detector.py` -> **100.0%** Exposure
- `gitgalaxy/core/graph_engine.py` -> **100.0%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/core/detector.py` -> **0** Orphaned Functions | **2** Duplicates
- `gitgalaxy/core/prism.py` -> **0** Orphaned Functions | **2** Duplicates
- `gitgalaxy/metrics/archetype_classifier.py` -> **2** Orphaned Functions | **0** Duplicates

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
- **Unknown Dependencies:** `2422` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/detector.py` (PYTHON) -> Cumulative Risk: **629.05**
- **Archetype:** `file_cluster_4` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z +0.59)
- **Magnitude:** 8317.42 | **LOC:** 8748 | **CtrlFlow:** 40.8% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Churn (100.0%), Safety Score (99.5368%)
- **Heaviest Functions:** `_slice_by_braces` (Many-Argument Workhorses, Impact: 1150.2), `splice` (Many-Argument Workhorses, Impact: 415.3), `_calculate_block_metrics` (Many-Argument Workhorses, Impact: 322.8)

### 2. `gitgalaxy/recorders/llm_recorder.py` (PYTHON) -> Cumulative Risk: **604.53**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z +0.65)
- **Magnitude:** 2344.12 | **LOC:** 1599 | **CtrlFlow:** 29.1% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.917%), Cognitive Load (83.8505%)
- **Heaviest Functions:** `_build_markdown` (Many-Argument Workhorses, Impact: 890.7), `generate_artifacts` (Many-Argument Workhorses, Impact: 37.7), `_generate_sqlite_graph` (Many-Argument Workhorses, Impact: 13.4)

### 3. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **593.19**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z -0.34)
- **Magnitude:** 2617.82 | **LOC:** 3445 | **CtrlFlow:** 25.5% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.063%), Cognitive Load (84.2812%)
- **Heaviest Functions:** `execute_pipeline` (Many-Argument Workhorses, Impact: 267.6), `_process_file_worker` (Compute Cores, Impact: 137.8), `_resolve_dependency_graph` (Compute Cores, Impact: 125.7)

### 4. `gitgalaxy/metrics/signal_processor.py` (PYTHON) -> Cumulative Risk: **583.84**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z +0.33)
- **Magnitude:** 2147.68 | **LOC:** 2298 | **CtrlFlow:** 26.4% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.3191%), Verification (80.0%)
- **Heaviest Functions:** `calculate_risk_vector` (Many-Argument Workhorses, Impact: 253.2), `summarize_galaxy_metrics` (Many-Argument Workhorses, Impact: 189.3), `generate_forensic_report` (Many-Argument Workhorses, Impact: 69.5)

### 5. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **573.4**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z +1.08)
- **Magnitude:** 1929.2 | **LOC:** 1960 | **CtrlFlow:** 35.2% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.7773%), Verification (80.0%)
- **Heaviest Functions:** `_strip_single_line_comments` (Many-Argument Workhorses, Impact: 124.1), `_strip_single_line_comments_positional` (Many-Argument Workhorses, Impact: 122.2), `_mask_perl_line_positional` (Compute Cores, Impact: 75.4)

### 6. `gitgalaxy/recorders/audit_recorder.py` (PYTHON) -> Cumulative Risk: **563.81**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z -0.72)
- **Magnitude:** 659.54 | **LOC:** 635 | **CtrlFlow:** 23.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (98.7644%), Cognitive Load (82.2976%)
- **Heaviest Functions:** `generate_report` (Many-Argument Workhorses, Impact: 300.6), `descale` (Defensive Guards, Impact: 14.1), `format_label` (Compute Cores, Impact: 7.6)

### 7. `gitgalaxy/recorders/record_keeper.py` (PYTHON) -> Cumulative Risk: **556.09**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Many-Argument Workhorses Files` (z +1.49)
- **Magnitude:** 742.42 | **LOC:** 1569 | **CtrlFlow:** 26.6% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (98.5135%), Verification (80.0%)
- **Heaviest Functions:** `_classify_file_archetype` (Many-Argument Workhorses, Impact: 66.5), `record_mission` (Many-Argument Workhorses, Impact: 19.5), `_prep_file_brain` (Type Conversions, Impact: 14.1)

### 8. `gitgalaxy/core/rule_prefilter.py` (PYTHON) -> Cumulative Risk: **551.24**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z +0.21)
- **Magnitude:** 195.6 | **LOC:** 306 | **CtrlFlow:** 36.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (98.9056%), Tech Debt (98.8145%)
- **Heaviest Functions:** `_walk_seq` (Compute Cores, Impact: 39.1), `derive_literal_gate` (Many-Argument Workhorses, Impact: 33.0), `_ci_literal_is_foldsafe` (Compute Cores, Impact: 13.0)

### 9. `gitgalaxy/standards/language_lens.py` (PYTHON) -> Cumulative Risk: **535.45**
- **Archetype:** `file_cluster_4` (Distance: N/A IQR)
- **Magnitude:** 1335.3 | **LOC:** 1144 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `inspect` (Many-Argument Workhorses, Impact: 353.2), `_tier_4_heuristic_discovery` (Many-Argument Workhorses, Impact: 122.9), `_evaluate_ecosystem_gravity` (Many-Argument Workhorses, Impact: 81.6)

### 10. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **535.21**
- **Archetype:** `file_cluster_11` (Distance: N/A IQR)
- **Composition Archetype:** `Large Core Modules` (z -0.15)
- **Magnitude:** 297.82 | **LOC:** 435 | **CtrlFlow:** 18.2% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (98.1664%), Verification (80.0%)
- **Heaviest Functions:** `main` (I/O & Config Routines, Impact: 31.6), `process_payload` (Many-Argument Workhorses, Impact: 24.7), `record_dead_code` (Many-Argument Workhorses, Impact: 14.4)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 8317.42 | **LOC:** 8748 | **CtrlFlow:** 40.8% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (67.8252%), Tech Debt (27.2754%)
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1150.2)
  * `splice` **(Many-Argument Workhorses)** (Impact: 415.3)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 322.8)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 248.9)
  * `_build_brace_safe_stream` **(Many-Argument Workhorses)** (Impact: 178.4)
    * *Intent:* """ Shields string/char literals and (for C-family languages) dead #if/#else macro branches so a bra...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 1 instances
* *Amplified Cascading Flux:* 1127 instances
* *Concurrency (weighted view):* 7
* *State Mutation (weighted view):* 3559
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 1712`, `structural_boundaries: 532`, `args: 89`, `func_start: 85`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 101`, `state_mutation: 1305`, `dead_code: 56`, `planned_debt: 2`, `fragile_debt: 24`, `duplicate_logic: 2`
* *Architecture:* `api: 19`, `concurrency: 2`, `import: 17`
* *Defense:* `safety: 38`, `doc: 83`, `immutability_locks: 34`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 22.774
  * `Choke Point (Betweenness):` 0.001735 | `Ripple Effect (Closeness):` 0.100022
  * `Imports (Out-Degree: 4):` bisect, collections, exactly, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.rule_prefilter, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards...
  * `Imported By (In-Degree: 44):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 2617.82 | **LOC:** 3445 | **CtrlFlow:** 25.5% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (84.2812%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 267.6)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_process_file_worker` **(Compute Cores)** (Impact: 137.8)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `_resolve_dependency_graph` **(Compute Cores)** (Impact: 125.7)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `_calculate_risk_exposures` **(Compute Cores)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
  * `main` **(Compute Cores)** (Impact: 97.7)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Rce:* 2 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 449 instances
* *Concurrency (weighted view):* 13
* *Sec Tainted Injection (weighted view):* 2
* *State Mutation (weighted view):* 1525
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 544`, `structural_boundaries: 238`, `args: 37`, `func_start: 27`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 78`, `high_risk_execution: 2`, `state_mutation: 627`, `dead_code: 2`
* *Architecture:* `io: 13`, `api: 7`, `concurrency: 3`, `import: 62`
* *Defense:* `safety: 49`, `doc: 21`, `test: 2`, `immutability_locks: 8`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 3.886
  * `Choke Point (Betweenness):` 0.001376 | `Ripple Effect (Closeness):` 0.017012
  * `Imports (Out-Degree: 30):` B, DAG, argparse, base64, collections, concurrent.futures, copy, datetime...
  * `Imported By (In-Degree: 7):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 2344.12 | **LOC:** 1599 | **CtrlFlow:** 29.1% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (83.8505%), Tech Debt (9.2171%)
**Top Internal Functions/Classes:**
  * `_build_markdown` **(Many-Argument Workhorses)** (Impact: 890.7)
  * `generate_artifacts` **(Many-Argument Workhorses)** (Impact: 37.7)
  * `_generate_sqlite_graph` **(Many-Argument Workhorses)** (Impact: 13.4)
  * `__init__` **(Compute Cores)** (Impact: 8.2)
  * `_macro` **(Generic / Templated Code)** (Impact: 5.3)
    * *Intent:* # #3027 (and #473's contract): None = not computed -- failed, or past # its work budget. Render it a...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 405 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1335
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 342`, `structural_boundaries: 79`, `args: 33`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 32`, `state_mutation: 525`, `planned_debt: 1`, `fragile_debt: 1`
* *Architecture:* `io: 2`, `api: 3`, `concurrency: 2`, `import: 10`
* *Defense:* `safety: 9`, `doc: 15`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.308
  * `Choke Point (Betweenness):` 5e-06 | `Ripple Effect (Closeness):` 0.014474
  * `Imports (Out-Degree: 1):` collections, gitgalaxy.standards, heapq, hops, json, logging, pathlib, sqlite3...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 2220.92 | **LOC:** 5392 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_spatial_mapper_sectorization_and_monolith` **(Defensive Guards)** (Impact: 15.5)
    * *Intent:* """ Proves the engine correctly groups files into sector constellations by their parent directories,...
  * `test_detector_c_macro_dead_branch_shield` **(Defensive Guards)** (Impact: 14.7)
    * *Intent:* """ Pins that a statically-dead C preprocessor branch is not counted (#2814). `detector._blank_dead_...
  * `test_detector_c_macro_no_space_boundaries_issue_1764` **(I/O & Config Routines)** (Impact: 14.2)
    * *Intent:* """ Regression test for a bug where `#if(1)` or `#elif(0)` (valid C preprocessor syntax without a sp...
  * `test_detector_c_macro_static_truth_prunes_branches` **(Defensive Guards)** (Impact: 13.9)
    * *Intent:* """ Companion to the #1720 fix: statically-decidable #if conditions still prune the dead branch. #if...
  * `test_detector_orphan_census_excludes_synthetic_slicer_names` **(I/O & Config Routines)** (Impact: 13.1)
    * *Intent:* """ Regression test for #2547: languages sliced by Mode D (_slice_by_keywords) or Mode E (_slice_by_...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` b, gitgalaxy.core.detector, gitgalaxy.core.prism, gitgalaxy.core.spatial_correlation, gitgalaxy.core.spatial_mapper, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 2147.68 | **LOC:** 2298 | **CtrlFlow:** 26.4% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (63.2874%), Tech Debt (8.9374%)
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` **(Many-Argument Workhorses)** (Impact: 253.2)
  * `summarize_galaxy_metrics` **(Many-Argument Workhorses)** (Impact: 189.3)
    * *Intent:* # ========================================================================== # GLOBAL SYNTHESIS & 2-...
  * `generate_forensic_report` **(Many-Argument Workhorses)** (Impact: 69.5)
    * *Intent:* # -------------------------------------------------------------------------- # REPORTING UTILITIES #...
  * `_calc_verification` **(Many-Argument Workhorses)** (Impact: 57.2)
  * `_compute_snapshot_percentiles` **(Many-Argument Workhorses)** (Impact: 41.1)
    * *Intent:* """[TIER 2, gitgalaxy#2994] Snapshot percentiles -- the honest 0-100. Ranks each file's 22 Tier-1 su...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *List:* 1 instances
* *Amplified Cascading Flux:* 325 instances
* *State Mutation (weighted view):* 1115
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 370`, `structural_boundaries: 149`, `args: 49`, `func_start: 38`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 43`, `state_mutation: 465`, `dead_code: 1`, `planned_debt: 1`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 11`, `concurrency: 2`, `import: 12`
* *Defense:* `safety: 32`, `doc: 28`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 7.452
  * `Choke Point (Betweenness):` 0.00016 | `Ripple Effect (Closeness):` 0.03006
  * `Imports (Out-Degree: 2):` a, collections.abc, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math...
  * `Imported By (In-Degree: 12):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 1929.2 | **LOC:** 1960 | **CtrlFlow:** 35.2% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (45.6794%), Tech Debt (45.3591%)
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` **(Many-Argument Workhorses)** (Impact: 124.1)
    * *Intent:* """ Single-line comment stripper for the "line_exclusive" family, driven by each language's own real...
  * `_strip_single_line_comments_positional` **(Many-Argument Workhorses)** (Impact: 122.2)
    * *Intent:* """Positional sibling of `_strip_single_line_comments`: same per-line masking and carry-quote discip...
  * `_mask_perl_line_positional` **(Compute Cores)** (Impact: 75.4)
  * `_mask_perl_line` **(Compute Cores)** (Impact: 75.4)
  * `_strip_positional_comments` **(Many-Argument Workhorses)** (Impact: 59.6)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 279 instances
* *State Mutation (weighted view):* 887
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 331`, `structural_boundaries: 172`, `args: 47`, `func_start: 44`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 329`, `fragile_debt: 6`, `duplicate_logic: 2`
* *Architecture:* `api: 11`, `import: 4`
* *Defense:* `safety: 4`, `doc: 41`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 10.172
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.053828
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 21):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 1335.3 | **LOC:** 1144 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 353.2)
  * `_tier_4_heuristic_discovery` **(Many-Argument Workhorses)** (Impact: 122.9)
    * *Intent:* # ========================================================================= # THE TIER 4 HEURISTIC D...
  * `_evaluate_ecosystem_gravity` **(Many-Argument Workhorses)** (Impact: 81.6)
  * `_tier_3_lexical_scan` **(Many-Argument Workhorses)** (Impact: 61.1)
  * `_find_balanced_end` **(Many-Argument Workhorses)** (Impact: 28.7)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` contextlib, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging, math, pathlib, re, time...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 1065.62 | **LOC:** 2871 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_recorder_exception_survivability` **(Many-Argument Workhorses)** (Impact: 16.3)
    * *Intent:* # ============================================================================== # TEST 23: RECORDER...
  * `test_phase_10_manifest_paths_includes_all_supported_ecosystems` **(Many-Argument Workhorses)** (Impact: 13.4)
    * *Intent:* # ============================================================================== # TEST 33: MANIFEST...
  * `test_cicd_policy_enforcement_gates` **(Many-Argument Workhorses)** (Impact: 12.4)
    * *Intent:* # ============================================================================== # TEST 2: THE CI/CD...
  * `test_sarif_ignored_paths_sanitization` **(Compute Cores)** (Impact: 11.6)
    * *Intent:* # ============================================================================== # TEST 19: SARIF IG...
  * `test_synthetic_node_generation` **(Compute Cores)** (Impact: 11.2)
    * *Intent:* # ============================================================================== # TEST 17: SYNTHETI...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` B, Q, base64, concurrent.futures, failure, gitgalaxy.core.aperture, gitgalaxy.core.detector, gitgalaxy.core.spatial_correlation...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: N/A IQR)
- **Magnitude:** 1060.58 | **LOC:** 748 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` **(Compute Cores)** (Impact: 181.9)
  * `locate_physical_package` **(Many-Argument Workhorses)** (Impact: 129.9)
  * `_parse_pyproject_toml` **(Many-Argument Workhorses)** (Impact: 36.2)
    * *Intent:* """ Audits modern Python manifests (PEP 621 `[project] dependencies` arrays and Poetry's `[tool.poet...
  * `_parse_requirements_txt` **(Compute Cores)** (Impact: 25.2)
    * *Intent:* """ Extracts direct Python packages and flags absolute VCS/URI references. """
  * `_parse_pip_conf` **(Compute Cores)** (Impact: 23.2)
    * *Intent:* """ Audits Python configuration files (pip.conf, .pypirc) for Dependency Confusion vulnerabilities c...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/graph_engine.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_0` (Drift: 0.0 IQR)
- **Magnitude:** 943.38 | **LOC:** 783 | **CtrlFlow:** 30.0% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (38.7826%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_louvain_level` **(Many-Argument Workhorses)** (Impact: 53.1)
  * `betweenness_centrality` **(Many-Argument Workhorses)** (Impact: 29.7)
    * *Intent:* """ #3038: exact betweenness centrality, one value per node id: the share of shortest import paths b...
  * `pagerank` **(Many-Argument Workhorses)** (Impact: 27.0)
    * *Intent:* """ Weighted PageRank, one value per node id: the only PageRank the engine runs, in both modes (#302...
  * `closeness_and_path_length` **(Many-Argument Workhorses)** (Impact: 24.4)
  * `_louvain` **(Many-Argument Workhorses)** (Impact: 23.8)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 183 instances
* *State Mutation (weighted view):* 567
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 142`, `structural_boundaries: 71`, `args: 25`, `func_start: 25`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 9`, `state_mutation: 201`
* *Architecture:* `api: 16`, `import: 6`
* *Defense:* `doc: 25`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.239
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.056092
  * `Imports (Out-Degree: 0):` as, built, chain, collections, collections.abc, direction, graph, math...
  * `Imported By (In-Degree: 4):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 780.76 | **LOC:** 2117 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `create_synthetic_star` **(Many-Argument Workhorses)** (Impact: 13.3)
    * *Intent:* # ============================================================================== # SYNTHETIC GALAXY ...
  * `test_signal_processor_documentation_acceptance_pins` **(Defensive Guards)** (Impact: 10.1)
    * *Intent:* """The #2908 acceptance table, pinned exactly: the rosetta a/b/c shape (3 public units, 0 documented...
  * `test_signal_processor_small_file_scores_on_counts` **(Defensive Guards)** (Impact: 7.0)
    * *Intent:* """ #2655: the old flat 5.0 small-file floor (`loc < 15`) is gone. A file below the evidence-mass fl...
  * `test_signal_processor_unknown_language_gets_no_language_term` **(Defensive Guards)** (Impact: 6.4)
    * *Intent:* # ============================================================================== # TEST 47: TIER 3 L...
  * `test_signal_processor_minified_tripwire` **(Defensive Guards)** (Impact: 6.3)
    * *Intent:* # ============================================================================== # TEST 11: THE MINI...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` gitgalaxy.metrics.signal_processor, gitgalaxy.recorders, gitgalaxy.recorders.record_keeper, gitgalaxy.recorders.sarif_recorder, identity, json, logging, os...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/record_keeper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 742.42 | **LOC:** 1569 | **CtrlFlow:** 26.6% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (55.9746%), Tech Debt (9.4065%)
**Top Internal Functions/Classes:**
  * `_classify_file_archetype` **(Many-Argument Workhorses)** (Impact: 66.5)
    * *Intent:* """Nearest-centroid file archetype from the assembled metrics, mirroring the offline apply_file_clus...
  * `record_mission` **(Many-Argument Workhorses)** (Impact: 19.5)
  * `_prep_file_brain` **(Type Conversions)** (Impact: 14.1)
    * *Intent:* """#ENGINE-PARITY: cache the self-describing FILE archetype brain contract. The engine builds the fi...
  * `_ensure_columns` **(Defensive Guards)** (Impact: 9.3)
    * *Intent:* """DEFENSIVE GUARD: Auto-Heal Schema Drift (gitgalaxy#2994). Generalizes the guarded-ALTER precedent...
  * `__init__` **(Many-Argument Workhorses)** (Impact: 8.7)
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
* *Ai Guardrails:* 1 instances
* *Amplified Cascading Flux:* 182 instances
* *State Mutation (weighted view):* 600
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 226`, `structural_boundaries: 38`, `args: 6`, `func_start: 6`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 19`, `state_mutation: 236`, `dead_code: 2`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 8`
* *Defense:* `safety: 24`, `doc: 21`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 5.317
  * `Choke Point (Betweenness):` 3.9e-05 | `Ripple Effect (Closeness):` 0.027656
  * `Imports (Out-Degree: 2):` gitgalaxy.standards.analysis_lens, graph, json, logging, machine, math, numpy, pathlib...
  * `Imported By (In-Degree: 10):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/audit_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 659.54 | **LOC:** 635 | **CtrlFlow:** 23.9% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (82.2976%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_report` **(Many-Argument Workhorses)** (Impact: 300.6)
  * `descale` **(Defensive Guards)** (Impact: 14.1)
    * *Intent:* """Dynamically scales integers back to floats using a fixed-string check."""
  * `format_label` **(Compute Cores)** (Impact: 7.6)
    * *Intent:* """Translates raw dictionary keys into descriptive human-readable labels."""
  * `__init__` **(Compute Cores)** (Impact: 6.4)
  * `decode_galaxy` **(Parameter Forwarders)** (Impact: 1.9)
    * *Intent:* """Standalone decoding logic preserved for CLI compatibility."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 97 instances
* *State Mutation (weighted view):* 314
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 107`, `structural_boundaries: 29`, `args: 11`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 16`, `state_mutation: 120`
* *Architecture:* `io: 3`, `api: 6`, `import: 8`
* *Defense:* `safety: 12`, `doc: 5`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.944
  * `Choke Point (Betweenness):` 2e-06 | `Ripple Effect (Closeness):` 0.012591
  * `Imports (Out-Degree: 1):` argparse, gitgalaxy.standards, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 523.12 | **LOC:** 589 | **CtrlFlow:** 25.4% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (71.6401%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit` **(Many-Argument Workhorses)** (Impact: 151.5)
    * *Intent:* """Executes statistical gating to identify data-dumps and structural outliers."""
  * `__init__` **(Many-Argument Workhorses)** (Impact: 10.7)
  * `_is_dead_code` **(Defensive Guards)** (Impact: 8.0)
    * *Intent:* """Determines if an artifact is predominantly dead code or comments."""
  * `_is_threat` **(Defensive Guards)** (Impact: 7.9)
    * *Intent:* """ Determines if an artifact contains active security threat signatures. Used by the Quarantine Gua...
  * `_is_highly_blended` **(Generic / Templated Code)** (Impact: 7.6)
    * *Intent:* """Determines if a file is a Polyglot where the primary language is < 80% of the mass."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 100 instances
* *State Mutation (weighted view):* 320
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 89`, `structural_boundaries: 40`, `args: 9`, `func_start: 7`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 27`, `state_mutation: 120`
* *Architecture:* `io: 2`, `api: 3`, `import: 5`
* *Defense:* `safety: 8`, `doc: 8`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.491
  * `Choke Point (Betweenness):` 6e-06 | `Ripple Effect (Closeness):` 0.012591
  * `Imports (Out-Degree: 1):` gitgalaxy.core.spatial_correlation, logging, os, statistics, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_0` (Drift: 0.0 IQR)
- **Magnitude:** 511.52 | **LOC:** 602 | **CtrlFlow:** 28.3% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (38.939%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_target` **(Many-Argument Workhorses)** (Impact: 66.2)
  * `_network_metrics` **(Many-Argument Workhorses)** (Impact: 36.8)
  * `extract_test_coverage_mapping` **(Many-Argument Workhorses)** (Impact: 32.5)
    * *Intent:* """ Maps function calls from test files to their imported production targets. Returns a dictionary m...
  * `_resolve_edges` **(Many-Argument Workhorses)** (Impact: 21.2)
    * *Intent:* """ #2992: resolves every file's raw_imports into directed file-to-file edges, keyed (importer, impo...
  * `build_dependency_graph` **(Many-Argument Workhorses)** (Impact: 16.9)
    * *Intent:* """ Builds the directed graph and calculates multi-dimensional risk vectors. Modifies the 'telemetry...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 82 instances
* *State Mutation (weighted view):* 259
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 91`, `structural_boundaries: 72`, `args: 17`, `func_start: 17`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 29`, `state_mutation: 95`
* *Architecture:* `io: 1`, `api: 4`, `import: 9`
* *Defense:* `safety: 9`, `doc: 17`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 9.31
  * `Choke Point (Betweenness):` 0.000356 | `Ripple Effect (Closeness):` 0.07326
  * `Imports (Out-Degree: 2):` A, Text.Pandoc.Generic, collections, gitgalaxy.core.graph_engine, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, graph, logging...
  * `Imported By (In-Degree: 7):` (Excluded from Brief to save tokens)

### `tests/security_auditing/test_network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 418.24 | **LOC:** 854 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_network_ecosystem_roles` **(Defensive Guards)** (Impact: 12.7)
    * *Intent:* # ============================================================================== # TEST 3: ECOSYSTEM...
  * `test_every_graph_metric_is_computed` **(Defensive Guards)** (Impact: 11.2)
    * *Intent:* # ============================================================================== # TEST 5: ZERO-DEPE...
  * `test_network_duplicate_filename_ambiguous_import_skipped` **(Defensive Guards)** (Impact: 9.6)
    * *Intent:* # ============================================================================== # TEST 6: DUPLICATE...
  * `test_network_duplicate_filename_path_qualified_import_resolves` **(Defensive Guards)** (Impact: 9.5)
    * *Intent:* # ============================================================================== # TEST 7: DUPLICATE...
  * `test_network_exact_case_match_wins_over_folded` **(Defensive Guards)** (Impact: 9.5)
    * *Intent:* # ============================================================================== # TEST 17: EXACT-CA...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` A, Foo, Parser, Text.Pandoc.Generic, and, chain, copy, creates...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 385.22 | **LOC:** 469 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_construct_feature_matrix` **(Many-Argument Workhorses)** (Impact: 38.6)
    * *Intent:* """Reconstructs the Pandas DataFrame exactly as train_threat_model.py did."""
  * `audit_repository` **(Many-Argument Workhorses)** (Impact: 36.4)
    * *Intent:* """ Orchestrates the resolution of transitive dependency graphs and executes the XGBoost model again...
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 32.8)
    * *Intent:* """ Resolves each file's transitive fragility and Downstream Exposure. `total_upstream` counts every...
  * `__init__` **(Many-Argument Workhorses)** (Impact: 28.6)
    * *Intent:* # Updated default to the new multiclass model
  * `_or_nan` **(Type Conversions)** (Impact: 4.4)
    * *Intent:* """None ("not computed") as NaN for the feature matrix; anything else unchanged."""
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` gitgalaxy.core.graph_engine, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens, importlib, logging, pathlib, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_0` (Drift: 0.0 IQR)
- **Magnitude:** 380.34 | **LOC:** 527 | **CtrlFlow:** 25.9% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (36.9139%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `get_intent_status` **(Compute Cores)** (Impact: 22.5)
    * *Intent:* """Returns the specific Intent Lock for a given file path based on strict, pattern, or sector match....
  * `_calculate_documentation_coverage` **(Compute Cores)** (Impact: 21.4)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `__init__` **(Many-Argument Workhorses)** (Impact: 17.0)
  * `_scan_gitattributes` **(Compute Cores)** (Impact: 15.2)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `_deep_inspect_manifest` **(Defensive Guards)** (Impact: 14.2)
    * *Intent:* """Dispatches files to specific parsers based on their format."""
**Contextual Mitigations & Amplifications:**
* *Sec Io:* 1 instances
* *Amplified Cascading Flux:* 59 instances
* *State Mutation (weighted view):* 184
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 77`, `structural_boundaries: 59`, `args: 15`, `func_start: 15`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 15`, `state_mutation: 66`
* *Architecture:* `io: 8`, `api: 5`, `import: 8`
* *Defense:* `safety: 10`, `doc: 16`, `sync_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.308
  * `Choke Point (Betweenness):` 1.4e-05 | `Ripple Effect (Closeness):` 0.014474
  * `Imports (Out-Degree: 2):` fnmatch, gitgalaxy.standards.gitgalaxy_config, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 375.7 | **LOC:** 1325 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_prism_jcl_comment_stripping_details` **(Defensive Guards)** (Impact: 7.8)
    * *Intent:* """ #2610: JCL `//*` whole-line comments move to the comment stream while everything `//`-statement-...
  * `test_prism_sub_families_fix_the_standard_block_delimiter_gap` **(I/O & Config Routines)** (Impact: 5.1)
    * *Intent:* """ Regression test for #621: sqlite, lua, haskell, powershell, and perl were all classified "standa...
  * `test_prism_standard_block_c_family_unaffected_by_sub_family_split` **(Defensive Guards)** (Impact: 4.8)
    * *Intent:* """ Regression guard for #621: splitting sqlite/lua/haskell/powershell/perl out of "standard_block" ...
  * `test_prism_livecode_string_has_no_backslash_escape` **(Defensive Guards)** (Impact: 4.3)
    * *Intent:* """ #2419: LiveCode string literals have NO `\\` escapes -- `\\` is an ordinary character. The share...
  * `test_prism_issue_1532_nested_comment_stripping_preserves_line_count` **(I/O & Config Routines)** (Impact: 4.2)
    * *Intent:* """ Regression test for #1532: `_strip_nested_comments()` -- shared by every "recursive_block"/"recu...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` gitgalaxy.core.prism, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, pytest, re, time, to, unittest.mock
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/gpu_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 361.86 | **LOC:** 449 | **CtrlFlow:** 13.7% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (55.641%), Tech Debt (14.4232%)
**Top Internal Functions/Classes:**
  * `record_mission` **(Many-Argument Workhorses)** (Impact: 119.0)
  * `__init__` **(Generic / Templated Code)** (Impact: 7.6)
  * `_intern` **(Generic / Templated Code)** (Impact: 4.2)
    * *Intent:* """Minifies payload footprints by mapping repetitive strings to integer IDs."""
  * `save_minified` **(Generic / Templated Code)** (Impact: 2.5)
    * *Intent:* """Serializes with maximum JSON compression to the provided output path."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 59 instances
* *State Mutation (weighted view):* 219
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 38`, `structural_boundaries: 23`, `args: 5`, `func_start: 4`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 101`, `fragile_debt: 1`
* *Architecture:* `io: 2`, `api: 4`, `import: 7`
* *Defense:* `safety: 3`, `doc: 4`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.491
  * `Choke Point (Betweenness):` 2.5e-05 | `Ripple Effect (Closeness):` 0.012591
  * `Imports (Out-Degree: 2):` gc, gitgalaxy.standards, gitgalaxy.standards.config_resolver, json, logging, pathlib, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_livecode_strict.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 355.02 | **LOC:** 729 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `assert_linear_redos_scaling` **(Many-Argument Workhorses)** (Impact: 20.4)
    * *Intent:* """ Measures pattern.search() time at each size in `sizes` (each isolated in its own subprocess via ...
  * `test_livecode_signature_positive_and_negative` **(Defensive Guards)** (Impact: 10.4)
  * `test_livecode_dependency_capture_extracts_path` **(Defensive Guards)** (Impact: 10.1)
    * *Intent:* """ _dependency_capture is paired with `import` and must extract the exact dependency path/module st...
  * `test_livecode_class_start_dotted_module_name_regression` **(Defensive Guards)** (Impact: 6.8)
    * *Intent:* """ Regression test (Rule 11-class nested/multi-segment coverage): the name capture `["\\'a-zA-Z_]\\...
  * `_measure_scaling_point` **(Generic / Templated Code)** (Impact: 6.7)
    * *Intent:* # ============================================================================== # REDOS SCALING VER...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` _strict_harness, contract, form, gitgalaxy.standards.language_standards, multiprocessing, pathlib, pytest, re...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_perl_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 354.78 | **LOC:** 623 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_perl_args_prototype_falls_through_to_body_idiom_scan` **(Defensive Guards)** (Impact: 11.6)
    * *Intent:* """ #1607: a legacy Perl PROTOTYPE (`sub Get8u($$)`) is a sequence of bare sigils with NO commas, ev...
  * `test_perl_signature_positive_and_negative` **(Defensive Guards)** (Impact: 10.4)
  * `test_perl_branch_colon_ambiguity_and_defined_or` **(Defensive Guards)** (Impact: 8.3)
  * `test_perl_globals_magic_variable_boundary_regression` **(Defensive Guards)** (Impact: 7.8)
    * *Intent:* """ Regression test: `$$`, `$@`, `$!`, and `$?` were inside the shared trailing \\b group. Each ends...
  * `test_perl_brace_safe_stream_escaped_brace_in_regex_does_not_desync` **(I/O & Config Routines)** (Impact: 7.6)
    * *Intent:* """ #1517: an escaped `\\{`/`\\}` inside a bare `/regex/` literal (never shielded at all -- perl reg...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` _strict_harness, gitgalaxy.core.detector, gitgalaxy.standards.language_standards, pathlib, pytest, sys
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_groovy_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 349.28 | **LOC:** 890 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_groovy_func_start_paren_less_builder_call_false_positive_regression` **(Defensive Guards)** (Impact: 22.9)
    * *Intent:* """ #2558: found while investigating #2530 -- once that fix correctly excluded `button(...) { ... }`...
  * `test_groovy_func_start_statement_keyword_as_prefix_false_positive_regression` **(Defensive Guards)** (Impact: 16.3)
    * *Intent:* """ #2676: found while gathering evidence for #2558 -- branch 1 (the >=1-prefix-token branch) alread...
  * `test_groovy_signature_deep_positive_and_negative` **(Defensive Guards)** (Impact: 10.4)
  * `test_groovy_func_start_markup_builder_dsl_call_false_positive_regression` **(I/O & Config Routines)** (Impact: 9.4)
    * *Intent:* """ #2530: func_start's zero-prefix branch (needed to match a real bare constructor, `MyClass(String...
  * `test_groovy_signature_positive_and_negative` **(Defensive Guards)** (Impact: 8.3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` _strict_harness, com.example.Foo, com.example.foo.Bar, com.example.gradle.Plugin, gitgalaxy.standards.language_standards, pathlib, pytest, static...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 343.58 | **LOC:** 506 | **CtrlFlow:** 21.5% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (47.9866%), Tech Debt (14.2366%)
**Top Internal Functions/Classes:**
  * `_stream_git_log` **(Many-Argument Workhorses)** (Impact: 62.0)
  * `_determine_commit_bounds` **(Compute Cores)** (Impact: 26.1)
    * *Intent:* """ [SIGNAL 1: ABSOLUTE BOUNDARIES] Determines the project's start and end dates for temporal normal...
  * `_initialize_history_scan` **(Compute Cores)** (Impact: 16.2)
    * *Intent:* """Dispatches the survey engines to establish boundaries and churn cache."""
  * `__init__` **(Many-Argument Workhorses)** (Impact: 15.7)
  * `_scan_git_history` **(Compute Cores)** (Impact: 14.3)
    * *Intent:* """ [BOUNDED HISTORY SCAN] Streams history backwards for exactly 1 year to guarantee deep churn data...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Mitigated Danger:* 5 instances
* *Amplified Cascading Flux:* 55 instances
* *High Risk Execution (weighted view):* 1
* *State Mutation (weighted view):* 183
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 61`, `structural_boundaries: 42`, `args: 8`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `high_risk_execution: 6`, `state_mutation: 73`, `fragile_debt: 1`
* *Architecture:* `io: 8`, `api: 3`, `import: 8`
* *Defense:* `safety: 12`, `doc: 9`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 3.585
  * `Choke Point (Betweenness):` 3.4e-05 | `Ripple Effect (Closeness):` 0.014474
  * `Imports (Out-Degree: 1):` gitgalaxy.standards, gitgalaxy.standards.config_resolver, logging, os, pathlib, shutil, subprocess, time...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: 0.0 IQR)
- **Magnitude:** 337.76 | **LOC:** 360 | **CtrlFlow:** 21.8% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (55.7339%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_report` **(Many-Argument Workhorses)** (Impact: 68.0)
  * `_audit_with_cache` **(Many-Argument Workhorses)** (Impact: 45.6)
    * *Intent:* """ CACHED mode: every candidate file is hashed; verdicts are reused on hash hits and freshly comput...
  * `_audit_capped_sample` **(Many-Argument Workhorses)** (Impact: 17.2)
    * *Intent:* """ LEGACY mode (no cache configured): per-directory capped sampling (#254). Coverage is honestly di...
  * `_iter_candidate_files` **(Compute Cores)** (Impact: 11.6)
    * *Intent:* """ Yields every auditable code file in the package in RISK-PRIORITY order: entry-point-named files ...
  * `__init__` **(Many-Argument Workhorses)** (Impact: 8.2)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 51 instances
* *State Mutation (weighted view):* 168
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 52`, `structural_boundaries: 52`, `args: 7`, `func_start: 7`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 11`, `state_mutation: 66`
* *Architecture:* `io: 5`, `api: 2`, `import: 12`
* *Defense:* `safety: 2`, `doc: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.126
  * `Choke Point (Betweenness):` 3.1e-05 | `Ripple Effect (Closeness):` 0.014474
  * `Imports (Out-Degree: 4):` datetime, gitgalaxy.security.manifest_parser, gitgalaxy.security.security_lens, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_lens, gitgalaxy.standards.language_standards, json, logging...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/core/detector.py` -> Churn: **100.0%** | Cog Load: 67.8252% | Debt: 27.2754%
- `gitgalaxy/galaxyscope.py` -> Churn: **76.84%** | Cog Load: 84.2812% | Debt: 0.0%
- `gitgalaxy/metrics/signal_processor.py` -> Churn: **70.67%** | Cog Load: 63.2874% | Debt: 8.9374%
- `gitgalaxy/recorders/record_keeper.py` -> Churn: **67.24%** | Cog Load: 55.9746% | Debt: 9.4065%
- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **60.75%** | Cog Load: 83.8505% | Debt: 9.2171%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 8317.42
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2617.82
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2344.12
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2147.68
- `gitgalaxy/core/prism.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 1929.2

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/detector.py` -> **Severity: 0.173** (Bridge: 0.0017 * Flux: 100.0%)
- `gitgalaxy/galaxyscope.py` -> **Severity: 0.138** (Bridge: 0.0014 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.036** (Bridge: 0.0004 * Flux: 100.0%)
- `gitgalaxy/metrics/signal_processor.py` -> **Severity: 0.016** (Bridge: 0.0002 * Flux: 100.0%)
- `gitgalaxy/security/security_auditor.py` -> **Severity: 0.012** (Bridge: 0.0001 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `tests/extraction/languages/_strict_harness.py` -> **Severity: 12.835** (Embedded: 0.1531 * Error Risk: 83.8311%)
- `gitgalaxy/standards/language_standards/languages/json.py` -> **Severity: 12.657** (Embedded: 0.1803 * Error Risk: 70.2063%)
- `gitgalaxy/core/detector.py` -> **Severity: 9.956** (Embedded: 0.1 * Error Risk: 99.5368%)
- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 9.355** (Embedded: 0.1112 * Error Risk: 84.1131%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 8.064** (Embedded: 0.0873 * Error Risk: 92.3601%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 504.947** (Blast Radius: 10.693 * Doc Risk: 47.2222%)
- `gitgalaxy/core/detector.py` -> **Severity: 464.323** (Blast Radius: 22.774 * Doc Risk: 20.3883%)
- `tests/tools/fidelity_table.py` -> **Severity: 425.55** (Blast Radius: 5.674 * Doc Risk: 75.0%)
- `tests/tools/tri_comparison_reconcile.py` -> **Severity: 403.2** (Blast Radius: 5.04 * Doc Risk: 80.0%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 373.95** (Blast Radius: 14.958 * Doc Risk: 25.0%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Stay in the Senior Technical Storyteller persona from Section 1. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility) woven into a cohesive narrative -- not a dry, disconnected bullet-point audit. DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective and factual, but write like you're explaining the codebase to a colleague, not filing a verdict.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
