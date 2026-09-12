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
> 12. **Documentation Risk Exposure:** Of the units extracted from a file, the weight-share a reader cannot recover from documentation -- public units count double, runtime-dynamic units count more, and a folder-level documentation umbrella shields the whole file. A ratio over units, not a density over lines; files with no extracted units have no value.
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
| Total Artifacts | 993 |
| Analyzed Artifacts (Scanned) | 391 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 602 |
| Total LOC | 82283 |
| Volatility Index | 0.005 |
| % Scanned of codebase = | 39.4% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.6808 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.3349 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 4.2031 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 43 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 346 | 81048 | 88.5% |
| MARKDOWN | 28 | 0 | 7.2% |
| YAML | 11 | 1008 | 2.8% |
| PLAINTEXT | 3 | 0 | 0.8% |
| SHELL | 2 | 84 | 0.5% |
| MAKEFILE | 1 | 143 | 0.3% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `2.272`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 360 | 92.1% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 31 | 7.9% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 602*

**Composition by Extension & Reason:**
- `.md`: 417x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 41 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.json`: 43x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yml`: 23x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 602 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `no_extension`: 7x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csv`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 83.7 | 3.3 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 99.9 | 6.1 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 41.6 | 0.4 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 3.2 | 0.0 | 0.0 |
| API Exposure | 0.0 | 53.9 | 1.0 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 24.5 | 0.2 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 6.2 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 11.7 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 6.4 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 20.6 | 0.2 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 1.8 | 0.0 | 0.0 |
| Documentation Exposure | 0.0 | 50.0 | 1.6 | 0.0 | 0.0 |
| Hardcoded Payload Artifacts | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `bitbucket-pipelines.yml` (Hits: 10)
- `gitgalaxy/core/guidestar_lens.py` (Hits: 8)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 60 inbound connections
2. **json.py** (`gitgalaxy/standards/language_standards/languages/json.py`) — 58 inbound connections
3. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 46 inbound connections
4. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 44 inbound connections
5. **detector.py** (`gitgalaxy/core/detector.py`) — 38 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 59 outbound dependencies
2. **test_import_contract_2875.py** (`tests/extraction/languages/test_import_contract_2875.py`) — 30 outbound dependencies
3. **test_python_strict.py** (`tests/extraction/languages/test_python_strict.py`) — 27 outbound dependencies
4. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 26 outbound dependencies
5. **test_embedded_python.py** (`tests/extraction/languages/test_embedded_python.py`) — 20 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_slice_by_braces` (@ `gitgalaxy/core/detector.py`) -> Impact: **1150.2** | LOC: 1308
- `_build_markdown` (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **782.2** | LOC: 1039
- `splice` (@ `gitgalaxy/core/detector.py`) -> Impact: **389.6** | LOC: 720
- `inspect` (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **353.2** | LOC: 405
- `_calculate_block_metrics` (@ `gitgalaxy/core/detector.py`) -> Impact: **322.8** | LOC: 470
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **275.5** | LOC: 590
  * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execution Flow): The method enforces a strict chronologi...
- `generate_report` (@ `gitgalaxy/recorders/audit_recorder.py`) -> Impact: **270.7** | LOC: 492
- `calculate_risk_vector` (@ `gitgalaxy/metrics/signal_processor.py`) -> Impact: **255.1** | LOC: 630
- `_slice_by_keywords` (@ `gitgalaxy/core/detector.py`) -> Impact: **248.9** | LOC: 427
- `measure` (@ `tests/tools/tree_sitter_accuracy_audit.py`) -> Impact: **217.8** | LOC: 477
  * *Intent:* """Runs the full pinned-corpus scan + tree-sitter diff, returns the metrics dict."""

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `tests/extraction/languages` | 104 | 13393.88 | 12.66% | 0.0% |
| `gitgalaxy/core` | 9 | 11411.44 | 37.2% | 8.85% |
| `tests/core_engine` | 31 | 6363.56 | 12.66% | 0.0% |
| `gitgalaxy/recorders` | 8 | 4026.72 | 47.23% | 3.06% |
| `gitgalaxy` | 6 | 3133.18 | 30.16% | 0.0% |
| `gitgalaxy/metrics` | 5 | 3048.84 | 44.01% | 4.47% |
| `gitgalaxy/standards` | 8 | 1755.0 | 14.29% | 7.15% |
| `tests/security_auditing` | 15 | 1713.26 | 11.91% | 0.0% |
| `gitgalaxy/security` | 5 | 1541.92 | 30.79% | 2.74% |
| `gitgalaxy/standards/language_standards/languages` | 59 | 1251.12 | 6.22% | 68.16% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `gitgalaxy/core/prism.py` -> **41.6262%** Exposure
- `gitgalaxy/core/detector.py` -> **28.2105%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **14.4553%** Exposure
- `gitgalaxy/metrics/chronometer.py` -> **14.2366%** Exposure
- `gitgalaxy/recorders/record_keeper.py` -> **10.0189%** Exposure
### Highest State Flux (Mutation/Volatility)
- `.claude/hooks/pytest_quiet.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/detector.py` -> **100.0%** Exposure
- `gitgalaxy/core/guidestar_lens.py` -> **100.0%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/core/detector.py` -> **0** Orphaned Functions | **2** Duplicates
- `gitgalaxy/core/prism.py` -> **0** Orphaned Functions | **2** Duplicates

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
- **Unknown Dependencies:** `2199` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/core/detector.py` (PYTHON) -> Cumulative Risk: **631.17**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 8079.72 | **LOC:** 8418 | **CtrlFlow:** 40.9% | **Authorship Centralization:** 94.9%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Churn (100.0%), Safety Score (99.5233%)
- **Heaviest Functions:** `_slice_by_braces` (Impact: 1150.2), `splice` (Impact: 389.6), `_calculate_block_metrics` (Impact: 322.8)

### 2. `gitgalaxy/recorders/llm_recorder.py` (PYTHON) -> Cumulative Risk: **587.32**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 2084.1 | **LOC:** 1450 | **CtrlFlow:** 27.9% | **Authorship Centralization:** 87.5%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.9093%), Cognitive Load (83.731%)
- **Heaviest Functions:** `_build_markdown` (Impact: 782.2), `generate_artifacts` (Impact: 37.7), `_generate_sqlite_graph` (Impact: 13.4)

### 3. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **567.31**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 1876.64 | **LOC:** 1883 | **CtrlFlow:** 35.7% | **Authorship Centralization:** 96.7%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.7976%), Verification (80.0%)
- **Heaviest Functions:** `_strip_single_line_comments` (Impact: 124.1), `_strip_single_line_comments_positional` (Impact: 122.2), `_mask_perl_line_positional` (Impact: 75.4)

### 4. `gitgalaxy/metrics/signal_processor.py` (PYTHON) -> Cumulative Risk: **566.25**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 2058.68 | **LOC:** 2133 | **CtrlFlow:** 25.6% | **Authorship Centralization:** 86.7%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.2557%), Verification (80.0%)
- **Heaviest Functions:** `calculate_risk_vector` (Impact: 255.1), `summarize_galaxy_metrics` (Impact: 193.3), `generate_forensic_report` (Impact: 69.1)

### 5. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **560.87**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 2589.18 | **LOC:** 3349 | **CtrlFlow:** 25.7% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.0788%), Verification (80.0%)
- **Heaviest Functions:** `execute_pipeline` (Impact: 275.5), `_process_file_worker` (Impact: 135.8), `_resolve_dependency_graph` (Impact: 121.7)

### 6. `gitgalaxy/recorders/audit_recorder.py` (PYTHON) -> Cumulative Risk: **549.0**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 598.62 | **LOC:** 593 | **CtrlFlow:** 23.0% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (98.5087%), Cognitive Load (81.3204%)
- **Heaviest Functions:** `generate_report` (Impact: 270.7), `descale` (Impact: 14.1), `format_label` (Impact: 7.6)

### 7. `gitgalaxy/standards/language_lens.py` (PYTHON) -> Cumulative Risk: **537.6**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 1335.3 | **LOC:** 1144 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `inspect` (Impact: 353.2), `_tier_4_heuristic_discovery` (Impact: 122.9), `_evaluate_ecosystem_gravity` (Impact: 81.6)

### 8. `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) -> Cumulative Risk: **533.39**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 360.44 | **LOC:** 441 | **CtrlFlow:** 13.7% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (99.6164%), Verification (80.0%)
- **Heaviest Functions:** `record_mission` (Impact: 119.0), `__init__` (Impact: 7.2), `_intern` (Impact: 4.2)

### 9. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **530.96**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 297.82 | **LOC:** 435 | **CtrlFlow:** 18.2% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (98.1664%), Verification (80.0%)
- **Heaviest Functions:** `main` (Impact: 31.6), `process_payload` (Impact: 24.7), `record_dead_code` (Impact: 14.4)

### 10. `gitgalaxy/security/security_auditor.py` (PYTHON) -> Cumulative Risk: **526.52**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 425.28 | **LOC:** 472 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `_resolve_dependency_graph` (Impact: 50.2), `audit_repository` (Impact: 36.2), `_construct_feature_matrix` (Impact: 35.0)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 8079.72 | **LOC:** 8418 | **CtrlFlow:** 40.9% | **Authorship Centralization:** 94.9%
- **Risk Profile:** Cognitive Load (67.759%), Tech Debt (28.2105%)
**Top Internal Functions/Classes:**
  * `_slice_by_braces` (Impact: 1150.2)
  * `splice` (Impact: 389.6)
  * `_calculate_block_metrics` (Impact: 322.8)
  * `_slice_by_keywords` (Impact: 248.9)
  * `_build_brace_safe_stream` (Impact: 178.4)
    * *Intent:* """ Shields string/char literals and (for C-family languages) dead #if/#else macro branches so a bra...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 1 instances
* *Amplified Cascading Flux:* 1090 instances
* *Concurrency (weighted view):* 7
* *State Mutation (weighted view):* 3446
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 1667`, `structural_boundaries: 510`, `args: 85`, `func_start: 81`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 94`, `state_mutation: 1266`, `dead_code: 55`, `planned_debt: 2`, `fragile_debt: 24`, `duplicate_logic: 2`
* *Architecture:* `api: 19`, `concurrency: 2`, `import: 15`
* *Defense:* `safety: 37`, `doc: 81`, `immutability_locks: 34`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 22.623
  * `Choke Point (Betweenness):` 0.000891 | `Ripple Effect (Closeness):` 0.091172
  * `Imports (Out-Degree: 3):` bisect, collections, exactly, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, hashlib...
  * `Imported By (In-Degree: 38):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 2589.18 | **LOC:** 3349 | **CtrlFlow:** 25.7% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (69.1714%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `execute_pipeline` (Impact: 275.5)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_process_file_worker` (Impact: 135.8)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `_resolve_dependency_graph` (Impact: 121.7)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `_calculate_risk_exposures` (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
  * `main` (Impact: 90.8)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Rce:* 2 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 443 instances
* *Concurrency (weighted view):* 13
* *Sec Tainted Injection (weighted view):* 2
* *State Mutation (weighted view):* 1503
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 540`, `structural_boundaries: 233`, `args: 35`, `func_start: 25`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 79`, `high_risk_execution: 2`, `state_mutation: 617`, `dead_code: 1`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 3`, `import: 62`
* *Defense:* `safety: 49`, `doc: 20`, `test: 2`, `immutability_locks: 8`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 3.46
  * `Choke Point (Betweenness):` 0.001173 | `Ripple Effect (Closeness):` 0.013187
  * `Imports (Out-Degree: 30):` B, DAG, argparse, collections, concurrent.futures, copy, datetime, fan...
  * `Imported By (In-Degree: 5):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 2220.94 | **LOC:** 5392 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_spatial_mapper_sectorization_and_monolith` (Impact: 15.5)
    * *Intent:* """ Proves the engine correctly groups files into sector constellations by their parent directories,...
  * `test_detector_c_macro_dead_branch_shield` (Impact: 14.7)
    * *Intent:* """ Pins that a statically-dead C preprocessor branch is not counted (#2814). `detector._blank_dead_...
  * `test_detector_c_macro_no_space_boundaries_issue_1764` (Impact: 14.2)
    * *Intent:* """ Regression test for a bug where `#if(1)` or `#elif(0)` (valid C preprocessor syntax without a sp...
  * `test_detector_c_macro_static_truth_prunes_branches` (Impact: 13.9)
    * *Intent:* """ Companion to the #1720 fix: statically-decidable #if conditions still prune the dead branch. #if...
  * `test_detector_orphan_census_excludes_synthetic_slicer_names` (Impact: 13.1)
    * *Intent:* """ Regression test for #2547: languages sliced by Mode D (_slice_by_keywords) or Mode E (_slice_by_...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` b, gitgalaxy.core.detector, gitgalaxy.core.prism, gitgalaxy.core.spatial_correlation, gitgalaxy.core.spatial_mapper, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 2084.1 | **LOC:** 1450 | **CtrlFlow:** 27.9% | **Authorship Centralization:** 87.5%
- **Risk Profile:** Cognitive Load (83.731%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_build_markdown` (Impact: 782.2)
  * `generate_artifacts` (Impact: 37.7)
  * `_generate_sqlite_graph` (Impact: 13.4)
  * `__init__` (Impact: 5.8)
  * `_outbound` (Impact: 4.4)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 363 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1202
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 300`, `structural_boundaries: 64`, `args: 28`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 476`
* *Architecture:* `io: 2`, `api: 3`, `concurrency: 2`, `import: 10`
* *Defense:* `safety: 9`, `doc: 13`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.108
  * `Choke Point (Betweenness):` 2e-06 | `Ripple Effect (Closeness):` 0.01094
  * `Imports (Out-Degree: 1):` collections, gitgalaxy.standards, heapq, json, logging, pathlib, sqlite3, statistics...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 2058.68 | **LOC:** 2133 | **CtrlFlow:** 25.6% | **Authorship Centralization:** 86.7%
- **Risk Profile:** Cognitive Load (63.7708%), Tech Debt (8.112%)
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` (Impact: 255.1)
  * `summarize_galaxy_metrics` (Impact: 193.3)
    * *Intent:* # ========================================================================== # GLOBAL SYNTHESIS & 2-...
  * `generate_forensic_report` (Impact: 69.1)
    * *Intent:* # -------------------------------------------------------------------------- # REPORTING UTILITIES #...
  * `_calc_verification` (Impact: 57.2)
  * `_calc_secrets_risk` (Impact: 26.9)
    * *Intent:* """ Calculates Secrets Risk Exposure (Credential Exposure). Looks for hardcoded credentials. Trusts ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *List:* 1 instances
* *Amplified Cascading Flux:* 315 instances
* *State Mutation (weighted view):* 1083
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 352`, `structural_boundaries: 138`, `args: 43`, `func_start: 35`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 41`, `state_mutation: 453`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 9`, `concurrency: 2`, `import: 11`
* *Defense:* `safety: 34`, `doc: 26`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.28
  * `Choke Point (Betweenness):` 0.000184 | `Ripple Effect (Closeness):` 0.031258
  * `Imports (Out-Degree: 2):` a, collections.abc, gitgalaxy.core.spatial_correlation, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math, os...
  * `Imported By (In-Degree: 12):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 1876.64 | **LOC:** 1883 | **CtrlFlow:** 35.7% | **Authorship Centralization:** 96.7%
- **Risk Profile:** Cognitive Load (44.3675%), Tech Debt (41.6262%)
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` (Impact: 124.1)
    * *Intent:* """ Single-line comment stripper for the "line_exclusive" family, driven by each language's own real...
  * `_strip_single_line_comments_positional` (Impact: 122.2)
    * *Intent:* """Positional sibling of `_strip_single_line_comments`: same per-line masking and carry-quote discip...
  * `_mask_perl_line_positional` (Impact: 75.4)
  * `_mask_perl_line` (Impact: 75.4)
  * `_compile_regex_matrix` (Impact: 59.5)
    * *Intent:* """Safely pre-compiles the standard regex matrix based on dynamic config lengths."""
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 271 instances
* *State Mutation (weighted view):* 863
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 322`, `structural_boundaries: 171`, `args: 47`, `func_start: 44`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 321`, `fragile_debt: 5`, `duplicate_logic: 2`
* *Architecture:* `api: 11`, `import: 4`
* *Defense:* `safety: 4`, `doc: 41`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.452
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.037987
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 14):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 1335.3 | **LOC:** 1144 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `inspect` (Impact: 353.2)
  * `_tier_4_heuristic_discovery` (Impact: 122.9)
    * *Intent:* # ========================================================================= # THE TIER 4 HEURISTIC D...
  * `_evaluate_ecosystem_gravity` (Impact: 81.6)
  * `_tier_3_lexical_scan` (Impact: 61.1)
  * `_find_balanced_end` (Impact: 28.7)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` contextlib, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging, math, pathlib, re, time...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 1060.58 | **LOC:** 748 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` (Impact: 181.9)
  * `locate_physical_package` (Impact: 129.9)
  * `_parse_pyproject_toml` (Impact: 36.2)
    * *Intent:* """ Audits modern Python manifests (PEP 621 `[project] dependencies` arrays and Poetry's `[tool.poet...
  * `_parse_requirements_txt` (Impact: 25.2)
    * *Intent:* """ Extracts direct Python packages and flags absolute VCS/URI references. """
  * `_parse_pip_conf` (Impact: 23.2)
    * *Intent:* """ Audits Python configuration files (pip.conf, .pypirc) for Dependency Confusion vulnerabilities c...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 1019.58 | **LOC:** 2707 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_recorder_exception_survivability` (Impact: 16.3)
    * *Intent:* # ============================================================================== # TEST 23: RECORDER...
  * `test_phase_10_manifest_paths_includes_all_supported_ecosystems` (Impact: 13.4)
    * *Intent:* # ============================================================================== # TEST 33: MANIFEST...
  * `test_cicd_policy_enforcement_gates` (Impact: 12.4)
    * *Intent:* # ============================================================================== # TEST 2: THE CI/CD...
  * `test_sarif_ignored_paths_sanitization` (Impact: 11.6)
    * *Intent:* # ============================================================================== # TEST 19: SARIF IG...
  * `test_synthetic_node_generation` (Impact: 11.2)
    * *Intent:* # ============================================================================== # TEST 17: SYNTHETI...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` B, Q, concurrent.futures, failure, gitgalaxy.core.aperture, gitgalaxy.core.detector, gitgalaxy.core.spatial_correlation, gitgalaxy.galaxyscope...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 621.9 | **LOC:** 1744 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `create_synthetic_star` (Impact: 13.3)
    * *Intent:* # ============================================================================== # SYNTHETIC GALAXY ...
  * `test_signal_processor_documentation_acceptance_pins` (Impact: 9.2)
    * *Intent:* """The #2908 acceptance table, pinned exactly: the rosetta a/b/c shape (3 public units, 0 documented...
  * `test_signal_processor_small_file_scores_on_counts` (Impact: 7.0)
    * *Intent:* """ #2655: the old flat 5.0 small-file floor (`loc < 15`) is gone. A file below the evidence-mass fl...
  * `test_signal_processor_unknown_language_gets_no_language_term` (Impact: 6.4)
    * *Intent:* # ============================================================================== # TEST 47: TIER 3 L...
  * `test_signal_processor_minified_tripwire` (Impact: 6.3)
    * *Intent:* # ============================================================================== # TEST 11: THE MINI...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.metrics.signal_processor, gitgalaxy.recorders.sarif_recorder, identity, json, logging, os, pytest, tempfile...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 600.8 | **LOC:** 593 | **CtrlFlow:** 31.0% | **Authorship Centralization:** 66.7%
- **Risk Profile:** Cognitive Load (60.8194%), Tech Debt (9.8118%)
**Top Internal Functions/Classes:**
  * `build_dependency_graph` (Impact: 83.6)
    * *Intent:* """ Builds the directed graph and calculates multi-dimensional risk vectors. Modifies the 'telemetry...
  * `_resolve_target` (Impact: 61.1)
  * `_fallback_build_graph` (Impact: 34.5)
  * `extract_test_coverage_mapping` (Impact: 32.5)
    * *Intent:* """ Maps function calls from test files to their imported production targets. Returns a dictionary m...
  * `_build_folded_resolution_map` (Impact: 12.0)
    * *Intent:* """ #2540: derives per-language lowercase-keyed views of the resolution keys so imports from case-in...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 109 instances
* *State Mutation (weighted view):* 343
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 110`, `structural_boundaries: 61`, `args: 9`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 28`, `state_mutation: 125`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 11`
* *Defense:* `safety: 14`, `doc: 8`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 9.355
  * `Choke Point (Betweenness):` 9e-06 | `Ripple Effect (Closeness):` 0.061074
  * `Imports (Out-Degree: 1):` A, Text.Pandoc.Generic, collections, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, logging, math, networkx...
  * `Imported By (In-Degree: 4):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/audit_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 598.62 | **LOC:** 593 | **CtrlFlow:** 23.0% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (81.3204%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_report` (Impact: 270.7)
  * `descale` (Impact: 14.1)
    * *Intent:* """Dynamically scales integers back to floats using a fixed-string check."""
  * `format_label` (Impact: 7.6)
    * *Intent:* """Translates raw dictionary keys into descriptive human-readable labels."""
  * `__init__` (Impact: 5.9)
  * `decode_galaxy` (Impact: 1.9)
    * *Intent:* """Standalone decoding logic preserved for CLI compatibility."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 87 instances
* *State Mutation (weighted view):* 284
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 97`, `structural_boundaries: 29`, `args: 10`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 15`, `state_mutation: 110`
* *Architecture:* `io: 3`, `api: 6`, `import: 8`
* *Defense:* `safety: 12`, `doc: 5`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.108
  * `Choke Point (Betweenness):` 2e-06 | `Ripple Effect (Closeness):` 0.01094
  * `Imports (Out-Degree: 1):` argparse, gitgalaxy.standards, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 523.12 | **LOC:** 589 | **CtrlFlow:** 25.4% | **Authorship Centralization:** 83.3%
- **Risk Profile:** Cognitive Load (71.6401%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit` (Impact: 151.5)
    * *Intent:* """Executes statistical gating to identify data-dumps and structural outliers."""
  * `__init__` (Impact: 10.7)
  * `_is_dead_code` (Impact: 8.0)
    * *Intent:* """Determines if an artifact is predominantly dead code or comments."""
  * `_is_threat` (Impact: 7.9)
    * *Intent:* """ Determines if an artifact contains active security threat signatures. Used by the Quarantine Gua...
  * `_is_highly_blended` (Impact: 7.6)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.708
  * `Choke Point (Betweenness):` 7e-06 | `Ripple Effect (Closeness):` 0.01094
  * `Imports (Out-Degree: 1):` gitgalaxy.core.spatial_correlation, logging, os, statistics, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/record_keeper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 487.62 | **LOC:** 1186 | **CtrlFlow:** 23.3% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (54.2628%), Tech Debt (10.0189%)
**Top Internal Functions/Classes:**
  * `record_mission` (Impact: 9.5)
  * `__init__` (Impact: 8.7)
  * `_is_already_renamed` (Impact: 3.3)
    * *Intent:* """#2806: is this ALTER ... RENAME COLUMN failure the benign already-done one? A fresh database is c...
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
* *Ai Guardrails:* 1 instances
* *Amplified Cascading Flux:* 134 instances
* *State Mutation (weighted view):* 449
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 153`, `structural_boundaries: 26`, `args: 3`, `func_start: 3`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 9`, `state_mutation: 181`, `dead_code: 1`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 7`
* *Defense:* `safety: 20`, `doc: 16`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.107
  * `Choke Point (Betweenness):` 3.5e-05 | `Ripple Effect (Closeness):` 0.016026
  * `Imports (Out-Degree: 2):` gitgalaxy.standards.analysis_lens, json, logging, machine, numpy, pathlib, sqlite3, statistics...
  * `Imported By (In-Degree: 5):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 425.28 | **LOC:** 472 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` (Impact: 50.2)
    * *Intent:* """ Resolves transitive fragility and Downstream Exposure using C-optimized traversals (NetworkX) if...
  * `audit_repository` (Impact: 36.2)
    * *Intent:* """ Orchestrates the resolution of transitive dependency graphs and executes the XGBoost model again...
  * `_construct_feature_matrix` (Impact: 35.0)
    * *Intent:* """Reconstructs the Pandas DataFrame exactly as train_threat_model.py did."""
  * `__init__` (Impact: 28.2)
    * *Intent:* # Updated default to the new multiclass model
  * `get_nth_degree` (Impact: 10.6)
    * *Intent:* """BFS using collections.deque for O(1) popping."""
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` collections, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens, logging, networkx, numpy, pandas, pathlib...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 380.34 | **LOC:** 527 | **CtrlFlow:** 25.9% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (36.9139%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `get_intent_status` (Impact: 22.5)
    * *Intent:* """Returns the specific Intent Lock for a given file path based on strict, pattern, or sector match....
  * `_calculate_documentation_coverage` (Impact: 21.4)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `__init__` (Impact: 17.0)
  * `_scan_gitattributes` (Impact: 15.2)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `_deep_inspect_manifest` (Impact: 14.2)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.508
  * `Choke Point (Betweenness):` 1.5e-05 | `Ripple Effect (Closeness):` 0.012981
  * `Imports (Out-Degree: 2):` fnmatch, gitgalaxy.standards.gitgalaxy_config, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/security_auditing/test_network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 379.02 | **LOC:** 852 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_network_ecosystem_roles` (Impact: 12.7)
    * *Intent:* # ============================================================================== # TEST 3: ECOSYSTEM...
  * `test_network_duplicate_filename_ambiguous_import_skipped` (Impact: 9.6)
    * *Intent:* # ============================================================================== # TEST 6: DUPLICATE...
  * `test_network_duplicate_filename_path_qualified_import_resolves` (Impact: 9.5)
    * *Intent:* # ============================================================================== # TEST 7: DUPLICATE...
  * `test_network_exact_case_match_wins_over_folded` (Impact: 9.5)
    * *Intent:* # ============================================================================== # TEST 17: EXACT-CA...
  * `test_network_duplicate_filename_fallback_mode` (Impact: 9.4)
    * *Intent:* # ============================================================================== # TEST 8: DUPLICATE...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` A, Foo, Parser, Text.Pandoc.Generic, and, chain, copy, creates...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 375.7 | **LOC:** 1325 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_prism_jcl_comment_stripping_details` (Impact: 7.8)
    * *Intent:* """ #2610: JCL `//*` whole-line comments move to the comment stream while everything `//`-statement-...
  * `test_prism_sub_families_fix_the_standard_block_delimiter_gap` (Impact: 5.1)
    * *Intent:* """ Regression test for #621: sqlite, lua, haskell, powershell, and perl were all classified "standa...
  * `test_prism_standard_block_c_family_unaffected_by_sub_family_split` (Impact: 4.8)
    * *Intent:* """ Regression guard for #621: splitting sqlite/lua/haskell/powershell/perl out of "standard_block" ...
  * `test_prism_livecode_string_has_no_backslash_escape` (Impact: 4.3)
    * *Intent:* """ #2419: LiveCode string literals have NO `\\` escapes -- `\\` is an ordinary character. The share...
  * `test_prism_issue_1532_nested_comment_stripping_preserves_line_count` (Impact: 4.2)
    * *Intent:* """ Regression test for #1532: `_strip_nested_comments()` -- shared by every "recursive_block"/"recu...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.core.prism, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, pytest, re, time, to, unittest.mock
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/gpu_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 360.44 | **LOC:** 441 | **CtrlFlow:** 13.7% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (55.6507%), Tech Debt (14.4553%)
**Top Internal Functions/Classes:**
  * `record_mission` (Impact: 119.0)
  * `__init__` (Impact: 7.2)
  * `_intern` (Impact: 4.2)
    * *Intent:* """Minifies payload footprints by mapping repetitive strings to integer IDs."""
  * `save_minified` (Impact: 2.5)
    * *Intent:* """Serializes with maximum JSON compression to the provided output path."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 59 instances
* *State Mutation (weighted view):* 218
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 38`, `structural_boundaries: 23`, `args: 5`, `func_start: 4`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 100`, `fragile_debt: 1`
* *Architecture:* `io: 2`, `api: 4`, `import: 7`
* *Defense:* `safety: 3`, `doc: 4`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.708
  * `Choke Point (Betweenness):` 2.8e-05 | `Ripple Effect (Closeness):` 0.01094
  * `Imports (Out-Degree: 2):` gc, gitgalaxy.standards, gitgalaxy.standards.config_resolver, json, logging, pathlib, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_livecode_strict.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 355.02 | **LOC:** 729 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `assert_linear_redos_scaling` (Impact: 20.4)
    * *Intent:* """ Measures pattern.search() time at each size in `sizes` (each isolated in its own subprocess via ...
  * `test_livecode_signature_positive_and_negative` (Impact: 10.4)
  * `test_livecode_dependency_capture_extracts_path` (Impact: 10.1)
    * *Intent:* """ _dependency_capture is paired with `import` and must extract the exact dependency path/module st...
  * `test_livecode_class_start_dotted_module_name_regression` (Impact: 6.8)
    * *Intent:* """ Regression test (Rule 11-class nested/multi-segment coverage): the name capture `["\\'a-zA-Z_]\\...
  * `_measure_scaling_point` (Impact: 6.7)
    * *Intent:* # ============================================================================== # REDOS SCALING VER...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, contract, form, gitgalaxy.standards.language_standards, multiprocessing, pathlib, pytest, re...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_perl_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 354.78 | **LOC:** 623 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_perl_args_prototype_falls_through_to_body_idiom_scan` (Impact: 11.6)
    * *Intent:* """ #1607: a legacy Perl PROTOTYPE (`sub Get8u($$)`) is a sequence of bare sigils with NO commas, ev...
  * `test_perl_signature_positive_and_negative` (Impact: 10.4)
  * `test_perl_branch_colon_ambiguity_and_defined_or` (Impact: 8.3)
  * `test_perl_globals_magic_variable_boundary_regression` (Impact: 7.8)
    * *Intent:* """ Regression test: `$$`, `$@`, `$!`, and `$?` were inside the shared trailing \\b group. Each ends...
  * `test_perl_brace_safe_stream_escaped_brace_in_regex_does_not_desync` (Impact: 7.6)
    * *Intent:* """ #1517: an escaped `\\{`/`\\}` inside a bare `/regex/` literal (never shielded at all -- perl reg...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, gitgalaxy.core.detector, gitgalaxy.standards.language_standards, pathlib, pytest, sys
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_groovy_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 349.28 | **LOC:** 890 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_groovy_func_start_paren_less_builder_call_false_positive_regression` (Impact: 22.9)
    * *Intent:* """ #2558: found while investigating #2530 -- once that fix correctly excluded `button(...) { ... }`...
  * `test_groovy_func_start_statement_keyword_as_prefix_false_positive_regression` (Impact: 16.3)
    * *Intent:* """ #2676: found while gathering evidence for #2558 -- branch 1 (the >=1-prefix-token branch) alread...
  * `test_groovy_signature_deep_positive_and_negative` (Impact: 10.4)
  * `test_groovy_func_start_markup_builder_dsl_call_false_positive_regression` (Impact: 9.4)
    * *Intent:* """ #2530: func_start's zero-prefix branch (needed to match a real bare constructor, `MyClass(String...
  * `test_groovy_signature_positive_and_negative` (Impact: 8.3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, com.example.Foo, com.example.foo.Bar, com.example.gradle.Plugin, gitgalaxy.standards.language_standards, pathlib, pytest, static...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 343.58 | **LOC:** 506 | **CtrlFlow:** 21.5% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (47.9866%), Tech Debt (14.2366%)
**Top Internal Functions/Classes:**
  * `_stream_git_log` (Impact: 62.0)
  * `_determine_commit_bounds` (Impact: 26.1)
    * *Intent:* """ [SIGNAL 1: ABSOLUTE BOUNDARIES] Determines the project's start and end dates for temporal normal...
  * `_initialize_history_scan` (Impact: 16.2)
    * *Intent:* """Dispatches the survey engines to establish boundaries and churn cache."""
  * `__init__` (Impact: 15.7)
  * `_scan_git_history` (Impact: 14.3)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 3.907
  * `Choke Point (Betweenness):` 4e-05 | `Ripple Effect (Closeness):` 0.012981
  * `Imports (Out-Degree: 1):` gitgalaxy.standards, gitgalaxy.standards.config_resolver, logging, os, pathlib, shutil, subprocess, time...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 337.76 | **LOC:** 360 | **CtrlFlow:** 21.8% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (55.7339%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_report` (Impact: 68.0)
  * `_audit_with_cache` (Impact: 45.6)
    * *Intent:* """ CACHED mode: every candidate file is hashed; verdicts are reused on hash hits and freshly comput...
  * `_audit_capped_sample` (Impact: 17.2)
    * *Intent:* """ LEGACY mode (no cache configured): per-directory capped sampling (#254). Coverage is honestly di...
  * `_iter_candidate_files` (Impact: 11.6)
    * *Intent:* """ Yields every auditable code file in the package in RISK-PRIORITY order: entry-point-named files ...
  * `__init__` (Impact: 8.2)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.308
  * `Choke Point (Betweenness):` 3.5e-05 | `Ripple Effect (Closeness):` 0.012981
  * `Imports (Out-Degree: 4):` datetime, gitgalaxy.security.manifest_parser, gitgalaxy.security.security_lens, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_lens, gitgalaxy.standards.language_standards, json, logging...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_jcl_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 319.86 | **LOC:** 861 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_jcl_args_parm_continuation_line_regression` (Impact: 10.9)
    * *Intent:* """ Regression test for #2482: the `args` regex only ever saw `PARM=` when it sat on the EXEC statem...
  * `test_jcl_signature_positive_and_negative` (Impact: 10.3)
  * `test_jcl_cross_line_false_match_regression` (Impact: 10.1)
    * *Intent:* """ Regression test for a real, shared bug across five rules (structural_boundaries, func_start, cla...
  * `test_jcl_cond_safety_vs_bypass_partition` (Impact: 6.4)
    * *Intent:* """ #2610: the two COND= rules partition by semantics, not by keyword -- a plain RC test is safety o...
  * `test_jcl_sync_locks_only_the_exclusive_enq_dispositions` (Impact: 6.1)
    * *Intent:* """ #2733: DISP=OLD/MOD request an exclusive system ENQ on the dataset; DISP=SHR and DISP=NEW do not...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, gitgalaxy.core.detector, gitgalaxy.core.prism, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, pathlib, pytest, re...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/core/detector.py` -> Churn: **100.0%** | Cog Load: 67.759% | Debt: 28.2105%
- `gitgalaxy/galaxyscope.py` -> Churn: **60.98%** | Cog Load: 69.1714% | Debt: 0.0%
- `gitgalaxy/metrics/signal_processor.py` -> Churn: **54.7%** | Cog Load: 63.7708% | Debt: 8.112%
- `gitgalaxy/recorders/record_keeper.py` -> Churn: **53.42%** | Cog Load: 54.2628% | Debt: 10.0189%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (94.9% isolated ownership) | Magnitude: 8079.72
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2589.18
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (87.5% isolated ownership) | Magnitude: 2084.1
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (86.7% isolated ownership) | Magnitude: 2058.68
- `gitgalaxy/core/prism.py` -> **Joe Esquibel** (96.7% isolated ownership) | Magnitude: 1876.64

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/galaxyscope.py` -> **Severity: 0.117** (Bridge: 0.0012 * Flux: 100.0%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.089** (Bridge: 0.0009 * Flux: 100.0%)
- `gitgalaxy/metrics/signal_processor.py` -> **Severity: 0.018** (Bridge: 0.0002 * Flux: 100.0%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 0.012** (Bridge: 0.0001 * Flux: 99.6316%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.007** (Bridge: 0.0001 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `tests/extraction/languages/_strict_harness.py` -> **Severity: 12.897** (Embedded: 0.1538 * Error Risk: 83.8311%)
- `gitgalaxy/standards/language_standards/languages/json.py` -> **Severity: 11.054** (Embedded: 0.1574 * Error Risk: 70.2063%)
- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 9.087** (Embedded: 0.108 * Error Risk: 84.1131%)
- `gitgalaxy/core/detector.py` -> **Severity: 9.074** (Embedded: 0.0912 * Error Risk: 99.5233%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 7.62** (Embedded: 0.0827 * Error Risk: 92.1826%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/config_resolver.py` -> **Severity: 549.855** (Blast Radius: 11.644 * Doc Risk: 47.2222%)
- `gitgalaxy/core/detector.py` -> **Severity: 473.237** (Blast Radius: 22.623 * Doc Risk: 20.9184%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 451.325** (Blast Radius: 18.053 * Doc Risk: 25.0%)
- `tests/tools/tri_comparison_reconcile.py` -> **Severity: 442.0** (Blast Radius: 5.525 * Doc Risk: 80.0%)
- `tests/tools/fidelity_table.py` -> **Severity: 414.6** (Blast Radius: 5.528 * Doc Risk: 75.0%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Stay in the Senior Technical Storyteller persona from Section 1. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility) woven into a cohesive narrative -- not a dry, disconnected bullet-point audit. DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective and factual, but write like you're explaining the codebase to a colleague, not filing a verdict.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
