# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Target Path** | `/home/runner/work/gitgalaxy/gitgalaxy` |
| **Timestamp** | `2026-08-28T18:51:54.195945+00:00` |
| **Scan Duration** | `7.55s` |
| **Git Branch** | `main` |
| **Git Commit** | `7a591bd6769ad6710fa45872208dc477801c7d62` |
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
| Total Artifacts | 848 |
| Analyzed Artifacts (Scanned) | 283 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 565 |
| Total LOC | 61496 |
| Volatility Index | 0.007 |
| % Scanned of codebase = | 33.4% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.7412 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.347 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 4.322 | Hops between files. Lower = Tighter coupling. |
| Articulation Pts | 46 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 243 | 60980 | 85.9% |
| MARKDOWN | 28 | 0 | 9.9% |
| YAML | 8 | 494 | 2.8% |
| PLAINTEXT | 3 | 0 | 1.1% |
| SHELL | 1 | 22 | 0.4% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Cluster 3`
> **Architectural Drift Z-Score:** `2.272`
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 252 | 89.0% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 31 | 11.0% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 565*

**Composition by Extension & Reason:**
- `.md`: 380x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 41 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.json`: 43x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yml`: 24x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `no_extension`: 7x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Monolithic Amalgamation: 102786 LOC exceeds safe regex boundaries)
- `.py`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 551 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csv`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. RISK EXPOSURE ANALYSIS (0-100%)
| Risk Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Cognitive Load Exposure | 0.0 | 74.3 | 2.1 | 0.0 | 0.0 |
| Error & Exception Exposure | 0.0 | 95.9 | 6.1 | 0.0 | 0.0 |
| Tech Debt Exposure | 0.0 | 100.0 | 0.9 | 0.0 | 0.0 |
| Testing Exposure | 0.0 | 80.0 | 4.6 | 0.0 | 0.0 |
| API Exposure | 0.0 | 8.1 | 0.2 | 0.0 | 0.0 |
| Concurrency Exposure | 0.0 | 27.9 | 0.3 | 0.0 | 0.0 |
| State Flux Exposure | 0.0 | 100.0 | 6.1 | 0.0 | 0.0 |
| Commented Logic Exposure | 0.0 | 10.8 | 0.1 | 0.0 | 0.0 |
| Specification Exposure | 0.0 | 100.0 | 10.5 | 0.0 | 0.0 |
| Instability Exposure | 0.0 | 17.0 | 0.7 | 0.0 | 0.0 |
| Volatility Exposure | 0.0 | 100.0 | 2.2 | 0.0 | 0.0 |
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
3. **detector.py** (`gitgalaxy/core/detector.py`) — 17 inbound connections
4. **config_resolver.py** (`gitgalaxy/standards/config_resolver.py`) — 9 inbound connections
5. **gitgalaxy_config.py** (`gitgalaxy/standards/gitgalaxy_config.py`) — 9 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 56 outbound dependencies
2. **test_python_strict.py** (`tests/extraction/languages/test_python_strict.py`) — 27 outbound dependencies
3. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 20 outbound dependencies
4. **test_embedded_python.py** (`tests/extraction/languages/test_embedded_python.py`) — 20 outbound dependencies
5. **test_python.py** (`tests/extraction/languages/test_python.py`) — 19 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_slice_by_braces` (@ `gitgalaxy/core/detector.py`) -> Impact: **974.0** | LOC: 1118
- `_build_markdown` (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **766.8** | LOC: 996
- `inspect` (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **353.4** | LOC: 407
- `_calculate_block_metrics` (@ `gitgalaxy/core/detector.py`) -> Impact: **325.6** | LOC: 455
- `execute_pipeline` (@ `gitgalaxy/galaxyscope.py`) -> Impact: **287.5** | LOC: 588
  * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execution Flow): The method enforces a strict chronologi...
- `generate_report` (@ `gitgalaxy/recorders/audit_recorder.py`) -> Impact: **275.7** | LOC: 480
- `calculate_risk_vector` (@ `gitgalaxy/metrics/signal_processor.py`) -> Impact: **254.0** | LOC: 607
- `splice` (@ `gitgalaxy/core/detector.py`) -> Impact: **240.5** | LOC: 418
- `slice_manifest` (@ `gitgalaxy/security/manifest_parser.py`) -> Impact: **211.6** | LOC: 272
- `measure` (@ `tests/tools/tree_sitter_accuracy_audit.py`) -> Impact: **198.1** | LOC: 428
  * *Intent:* """Runs the full pinned-corpus scan + tree-sitter diff, returns the metrics dict."""

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Cog Load | Avg Debt |
|---|---|---|---|---|
| `tests/extraction/languages` | 92 | 6732.52 | 3.43% | 0.0% |
| `gitgalaxy/core` | 9 | 5130.56 | 14.38% | 7.83% |
| `gitgalaxy/recorders` | 8 | 2563.8 | 23.54% | 3.1% |
| `tests/core_engine` | 22 | 2563.48 | 3.07% | 0.0% |
| `gitgalaxy/metrics` | 5 | 1639.88 | 16.41% | 4.56% |
| `gitgalaxy` | 6 | 1532.08 | 8.8% | 0.0% |
| `gitgalaxy/standards` | 7 | 1170.36 | 5.26% | 6.81% |
| `tests/security_auditing` | 15 | 977.56 | 1.99% | 0.0% |
| `gitgalaxy/security` | 5 | 846.48 | 11.93% | 0.0% |
| `tests` | 8 | 545.48 | 7.45% | 0.0% |

## 10. TARGETED RISK VECTORS (Top 5 by Exposure)
### Highest Tech Debt (Fragile/Planned)
- `scripts/update_golden_masters.sh` -> **99.956%** Exposure
- `gitgalaxy/core/prism.py` -> **30.0494%** Exposure
- `gitgalaxy/core/detector.py` -> **29.9142%** Exposure
- `gitgalaxy/metrics/chronometer.py` -> **14.7229%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **14.4553%** Exposure
### Highest State Flux (Mutation/Volatility)
- `gitgalaxy/recorders/llm_recorder.py` -> **100.0%** Exposure
- `gitgalaxy/recorders/gpu_recorder.py` -> **99.9989%** Exposure
- `gitgalaxy/core/prism.py` -> **99.9507%** Exposure
- `gitgalaxy/core/spatial_mapper.py` -> **99.8822%** Exposure
- `bitbucket-pipelines.yml` -> **99.6681%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/core/detector.py` -> **0** Orphaned Functions | **2** Duplicates
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
- **Unknown Dependencies:** `1637` packages imported that bypass the Zero-Trust whitelist.

## 11. CUMULATIVE RISK HITLIST (Top 10 Highest Risk Files)
> Cumulative Risk is the sum of all individual risk exposures. These files represent the highest multi-dimensional technical debt and architectural fragility.

### 1. `gitgalaxy/recorders/llm_recorder.py` (PYTHON) -> Cumulative Risk: **545.19**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 1564.86 | **LOC:** 1407 | **CtrlFlow:** 85.9% | **Authorship Centralization:** 87.5%
- **Primary Risk Drivers:** State Flux (100.0%), Spec Match (100.0%), Safety Score (95.9289%), Verification (80.0%)
- **Heaviest Functions:** `_build_markdown` (Impact: 766.8), `generate_artifacts` (Impact: 43.4), `_generate_sqlite_graph` (Impact: 16.0)

### 2. `gitgalaxy/core/prism.py` (PYTHON) -> Cumulative Risk: **498.05**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 732.38 | **LOC:** 1165 | **CtrlFlow:** 67.0% | **Authorship Centralization:** 93.3%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.9507%), Safety Score (81.8657%), Verification (80.0%)
- **Heaviest Functions:** `_strip_single_line_comments` (Impact: 124.1), `_mask_perl_line` (Impact: 75.4), `_compile_regex_matrix` (Impact: 57.6)

### 3. `gitgalaxy/core/detector.py` (PYTHON) -> Cumulative Risk: **491.11**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 3684.48 | **LOC:** 5833 | **CtrlFlow:** 77.1% | **Authorship Centralization:** 93.1%
- **Primary Risk Drivers:** Spec Match (100.0%), Churn (100.0%), Verification (80.0%), Safety Score (60.691%)
- **Heaviest Functions:** `_slice_by_braces` (Impact: 974.0), `_calculate_block_metrics` (Impact: 325.6), `splice` (Impact: 240.5)

### 4. `gitgalaxy/recorders/gpu_recorder.py` (PYTHON) -> Cumulative Risk: **472.03**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 246.34 | **LOC:** 441 | **CtrlFlow:** 65.1% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (99.9989%), Safety Score (90.1135%), Verification (80.0%)
- **Heaviest Functions:** `record_mission` (Impact: 121.9), `__init__` (Impact: 7.2), `save_minified` (Impact: 6.5)

### 5. `gitgalaxy/tools/cobol_to_java/cobol_to_java_service_forge.py` (PYTHON) -> Cumulative Risk: **447.81**
- **Archetype:** `Unknown Archetype` (Distance: N/A IQR)
- **Magnitude:** 0.05 | **LOC:** 97 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Primary Risk Drivers:** None
- **Heaviest Functions:** `generate_service_skeleton` (Impact: 14.2), `main` (Impact: 4.2)

### 6. `gitgalaxy/metrics/statistical_auditor.py` (PYTHON) -> Cumulative Risk: **447.4**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 263.42 | **LOC:** 579 | **CtrlFlow:** 71.7% | **Authorship Centralization:** 75.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (98.817%), Verification (80.0%), Safety Score (79.685%)
- **Heaviest Functions:** `audit` (Impact: 154.9), `__init__` (Impact: 10.7), `_is_dead_code` (Impact: 9.7)

### 7. `gitgalaxy/galaxyscope.py` (PYTHON) -> Cumulative Risk: **435.42**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 1270.2 | **LOC:** 3113 | **CtrlFlow:** 71.3% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (82.9593%), Verification (80.0%), Safety Score (63.4032%)
- **Heaviest Functions:** `execute_pipeline` (Impact: 287.5), `_process_file_worker` (Impact: 147.6), `_resolve_dependency_graph` (Impact: 102.5)

### 8. `gitgalaxy/recorders/sbom_recorder.py` (PYTHON) -> Cumulative Risk: **413.31**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 214.34 | **LOC:** 359 | **CtrlFlow:** 52.8% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (96.9481%), Verification (80.0%), Safety Score (74.9749%)
- **Heaviest Functions:** `generate_report` (Impact: 73.2), `_audit_with_cache` (Impact: 45.6), `_audit_capped_sample` (Impact: 17.2)

### 9. `gitgalaxy/cobol_refractor_controller.py` (PYTHON) -> Cumulative Risk: **411.36**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 170.7 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 100.0%
- **Primary Risk Drivers:** Spec Match (100.0%), State Flux (97.3782%), Verification (80.0%), Safety Score (68.5044%)
- **Heaviest Functions:** `main` (Impact: 32.5), `process_payload` (Impact: 26.7), `record_dead_code` (Impact: 14.4)

### 10. `gitgalaxy/metrics/signal_processor.py` (PYTHON) -> Cumulative Risk: **407.23**
- **Archetype:** `Unclassified` (Distance: N/A IQR)
- **Magnitude:** 1098.92 | **LOC:** 2043 | **CtrlFlow:** 74.4% | **Authorship Centralization:** 81.8%
- **Primary Risk Drivers:** Spec Match (100.0%), Verification (80.0%), Safety Score (56.4193%), State Flux (54.3735%)
- **Heaviest Functions:** `calculate_risk_vector` (Impact: 254.0), `summarize_galaxy_metrics` (Impact: 197.3), `generate_forensic_report` (Impact: 69.1)

## 12. SCANNED ARTIFACTS HITLIST (Top 25 Heaviest Files)
> *Note: 'Magnitude' represents the file's total Structural Magnitude and impact within the system. It is independent of its Risk Profile. High magnitude implies high structural importance and centralization.*

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 3684.48 | **LOC:** 5833 | **CtrlFlow:** 77.1% | **Authorship Centralization:** 93.1%
- **Risk Profile:** Cognitive Load (20.3327%), Tech Debt (29.9142%)
**Top Internal Functions/Classes:**
  * `_slice_by_braces` (Impact: 974.0)
  * `_calculate_block_metrics` (Impact: 325.6)
  * `splice` (Impact: 240.5)
  * `_build_brace_safe_stream` (Impact: 166.7)
    * *Intent:* """ Shields string/char literals and (for C-family languages) dead #if/#else macro branches so a bra...
  * `_slice_by_indentation` (Impact: 160.7)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 1223`, `structural_boundaries: 363`, `args: 55`, `func_start: 53`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 77`, `state_mutation: 205`, `dead_code: 32`, `planned_debt: 1`, `fragile_debt: 19`, `duplicate_logic: 2`
* *Architecture:* `api: 19`, `concurrency: 2`, `import: 14`
* *Defense:* `safety: 47`, `doc: 116`, `test: 2`, `immutability_locks: 8`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 16.785
  * `Choke Point (Betweenness):` 0.000395 | `Ripple Effect (Closeness):` 0.061671
  * `Imports (Out-Degree: 2):` bisect, collections, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, hashlib, logging, math...
  * `Imported By (In-Degree: 17):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 1564.86 | **LOC:** 1407 | **CtrlFlow:** 85.9% | **Authorship Centralization:** 87.5%
- **Risk Profile:** Cognitive Load (74.3268%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_build_markdown` (Impact: 766.8)
  * `generate_artifacts` (Impact: 43.4)
  * `_generate_sqlite_graph` (Impact: 16.0)
  * `__init__` (Impact: 5.8)
  * `_parse_threat_score` (Impact: 3.8)
    * *Intent:* """Safely extracts and converts the AI threat score string to a float."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 299`, `structural_boundaries: 49`, `args: 27`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 31`, `state_mutation: 692`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 12`, `import: 10`
* *Defense:* `safety: 13`, `doc: 27`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.183
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.011082
  * `Imports (Out-Degree: 0):` collections, gitgalaxy.standards, heapq, json, logging, pathlib, sqlite3, statistics...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 1270.2 | **LOC:** 3113 | **CtrlFlow:** 71.3% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (21.8904%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `execute_pipeline` (Impact: 287.5)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_process_file_worker` (Impact: 147.6)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `_resolve_dependency_graph` (Impact: 102.5)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `main` (Impact: 95.8)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
  * `_calculate_risk_exposures` (Impact: 93.4)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 545`, `structural_boundaries: 219`, `args: 33`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 77`, `state_mutation: 197`
* *Architecture:* `io: 13`, `api: 6`, `concurrency: 3`, `import: 63`
* *Defense:* `safety: 75`, `doc: 36`, `test: 2`, `cleanup: 6`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 4.064
  * `Choke Point (Betweenness):` 0.001035 | `Ripple Effect (Closeness):` 0.010638
  * `Imports (Out-Degree: 29):` DAG, argparse, collections, concurrent.futures, copy, datetime, gitgalaxy.core.aperture, gitgalaxy.core.detector...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 1098.92 | **LOC:** 2043 | **CtrlFlow:** 74.4% | **Authorship Centralization:** 81.8%
- **Risk Profile:** Cognitive Load (16.9428%), Tech Debt (8.1016%)
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` (Impact: 254.0)
  * `summarize_galaxy_metrics` (Impact: 197.3)
    * *Intent:* # ========================================================================== # GLOBAL SYNTHESIS & 2-...
  * `generate_forensic_report` (Impact: 69.1)
    * *Intent:* # -------------------------------------------------------------------------- # REPORTING UTILITIES #...
  * `_calc_verification` (Impact: 60.6)
  * `_calc_documentation` (Impact: 34.6)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 360`, `structural_boundaries: 124`, `args: 39`, `func_start: 31`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 41`, `state_mutation: 86`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 12`, `concurrency: 2`, `import: 8`
* *Defense:* `safety: 54`, `doc: 40`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.076
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.026112
  * `Imports (Out-Degree: 0):` gitgalaxy.standards, logging, math, os, re, statistics, typing
  * `Imported By (In-Degree: 7):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 853.74 | **LOC:** 1152 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `inspect` (Impact: 353.4)
  * `_tier_4_heuristic_discovery` (Impact: 125.4)
    * *Intent:* # ========================================================================= # THE TIER 4 HEURISTIC D...
  * `_evaluate_ecosystem_gravity` (Impact: 83.9)
  * `_tier_3_lexical_scan` (Impact: 63.6)
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

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 732.38 | **LOC:** 1165 | **CtrlFlow:** 67.0% | **Authorship Centralization:** 93.3%
- **Risk Profile:** Cognitive Load (29.185%), Tech Debt (30.0494%)
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` (Impact: 124.1)
    * *Intent:* """ Single-line comment stripper for the "line_exclusive" family, driven by each language's own real...
  * `_mask_perl_line` (Impact: 75.4)
  * `_compile_regex_matrix` (Impact: 57.6)
    * *Intent:* """Safely pre-compiles the standard regex matrix based on dynamic config lengths."""
  * `split_streams` (Impact: 45.1)
    * *Intent:* """Decouples the file into mutually exclusive components (Executable Payload vs Documentation Surfac...
  * `_partition_embedded_languages` (Impact: 39.5)
    * *Intent:* """Splits content into language segments based on embedded language triggers."""
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 193`, `structural_boundaries: 95`, `args: 26`, `func_start: 23`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 24`, `state_mutation: 142`, `fragile_debt: 6`
* *Architecture:* `api: 11`, `import: 4`
* *Defense:* `safety: 4`, `doc: 44`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 10.406
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.030648
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 8):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 654.44 | **LOC:** 3499 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_spatial_mapper_sectorization_and_monolith` (Impact: 15.5)
    * *Intent:* """ Proves the engine correctly groups files into sector constellations by their parent directories,...
  * `test_detector_c_macro_no_space_boundaries_issue_1764` (Impact: 14.2)
    * *Intent:* """ Regression test for a bug where `#if(1)` or `#elif(0)` (valid C preprocessor syntax without a sp...
  * `test_detector_c_macro_static_truth_prunes_branches` (Impact: 13.9)
    * *Intent:* """ Companion to the #1720 fix: statically-decidable #if conditions still prune the dead branch. #if...
  * `test_detector_defensive_catch_blocks` (Impact: 9.9)
    * *Intent:* # ============================================================================== # TEST 36: DEFENSIV...
  * `test_slice_by_braces_c_preprocessor_conditional_edge_cases_1837_review` (Impact: 8.6)
    * *Intent:* """ Adversarial cases surfaced during independent review of #1837's fix: the re-slice-after-the-last...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` gitgalaxy.core.detector, gitgalaxy.core.prism, gitgalaxy.core.spatial_mapper, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging, math, pytest...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 577.28 | **LOC:** 748 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `slice_manifest` (Impact: 211.6)
  * `locate_physical_package` (Impact: 132.2)
  * `_parse_pyproject_toml` (Impact: 38.2)
    * *Intent:* """ Audits modern Python manifests (PEP 621 `[project] dependencies` arrays and Poetry's `[tool.poet...
  * `_parse_requirements_txt` (Impact: 27.2)
    * *Intent:* """ Extracts direct Python packages and flags absolute VCS/URI references. """
  * `_parse_pip_conf` (Impact: 25.2)
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
- **Magnitude:** 509.74 | **LOC:** 2151 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_recorder_exception_survivability` (Impact: 20.3)
    * *Intent:* # ============================================================================== # TEST 23: RECORDER...
  * `test_phase_10_manifest_paths_includes_all_supported_ecosystems` (Impact: 16.0)
    * *Intent:* # ============================================================================== # TEST 33: MANIFEST...
  * `test_delta_scanning_fallbacks` (Impact: 13.6)
    * *Intent:* # ============================================================================== # TEST 24: DELTA SC...
  * `test_yaml_typo_in_gitgalaxy_config_key_aborts_run` (Impact: 13.5)
    * *Intent:* """ #332's hard-error decision: a typo'd gitgalaxy_config.py-style key (e.g. STRICT_IMPORT_MDOE) mus...
  * `test_yaml_configuration_and_cli_priority` (Impact: 12.8)
    * *Intent:* # ============================================================================== # TEST 7: YAML CONF...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` concurrent.futures, failure, gitgalaxy.core.aperture, gitgalaxy.galaxyscope, gitgalaxy.metrics.signal_processor, gitgalaxy.standards, gitgalaxy.standards.analysis_lens, logging...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/audit_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 347.52 | **LOC:** 581 | **CtrlFlow:** 78.0% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (23.222%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_report` (Impact: 275.7)
  * `descale` (Impact: 14.1)
    * *Intent:* """Dynamically scales integers back to floats using a fixed-string check."""
  * `format_label` (Impact: 7.6)
    * *Intent:* """Translates raw dictionary keys into descriptive human-readable labels."""
  * `__init__` (Impact: 5.9)
  * `decode_galaxy` (Impact: 1.9)
    * *Intent:* """Standalone decoding logic preserved for CLI compatibility."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 99`, `structural_boundaries: 28`, `args: 10`, `func_start: 5`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 15`, `state_mutation: 25`
* *Architecture:* `io: 3`, `api: 9`, `import: 8`
* *Defense:* `safety: 16`, `doc: 10`, `sync_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.183
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.011082
  * `Imports (Out-Degree: 0):` argparse, gitgalaxy.standards, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 295.26 | **LOC:** 1597 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `create_synthetic_star` (Impact: 13.3)
    * *Intent:* # ============================================================================== # SYNTHETIC GALAXY ...
  * `test_signal_processor_minified_tripwire` (Impact: 8.0)
    * *Intent:* # ============================================================================== # TEST 11: THE MINI...
  * `test_sarif_exact_loc_injection` (Impact: 6.2)
    * *Intent:* # ============================================================================== # TEST 51: SARIF EX...
  * `test_signal_processor_report_fallback` (Impact: 5.4)
    * *Intent:* # ============================================================================== # TEST 42: REPORT G...
  * `test_function_archetype_classified_when_model_matches_live_dims` (Impact: 5.2)
    * *Intent:* """ With a model that actually matches the 5-dim live vector, the shared classifier should still cla...
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

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 263.42 | **LOC:** 579 | **CtrlFlow:** 71.7% | **Authorship Centralization:** 75.0%
- **Risk Profile:** Cognitive Load (37.3162%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `audit` (Impact: 154.9)
    * *Intent:* """Executes statistical gating to identify data-dumps and structural outliers."""
  * `__init__` (Impact: 10.7)
  * `_is_dead_code` (Impact: 9.7)
    * *Intent:* """Determines if an artifact is predominantly dead code or comments."""
  * `_is_threat` (Impact: 9.7)
    * *Intent:* """ Determines if an artifact contains active security threat signatures. Used by the Quarantine Gua...
  * `_is_highly_blended` (Impact: 7.6)
    * *Intent:* """Determines if a file is a Polyglot where the primary language is < 80% of the mass."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 91`, `structural_boundaries: 36`, `args: 8`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 25`, `state_mutation: 58`
* *Architecture:* `io: 2`, `api: 3`, `import: 4`
* *Defense:* `safety: 10`, `doc: 14`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.183
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.011082
  * `Imports (Out-Degree: 0):` logging, os, statistics, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/gpu_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 246.34 | **LOC:** 441 | **CtrlFlow:** 65.1% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (45.8368%), Tech Debt (14.4553%)
**Top Internal Functions/Classes:**
  * `record_mission` (Impact: 121.9)
  * `__init__` (Impact: 7.2)
  * `save_minified` (Impact: 6.5)
    * *Intent:* """Serializes with maximum JSON compression to the provided output path."""
  * `_intern` (Impact: 4.2)
    * *Intent:* """Minifies payload footprints by mapping repetitive strings to integer IDs."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 41`, `structural_boundaries: 22`, `args: 5`, `func_start: 4`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 95`, `fragile_debt: 1`
* *Architecture:* `io: 2`, `api: 6`, `import: 7`
* *Defense:* `safety: 5`, `doc: 8`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.183
  * `Choke Point (Betweenness):` 1.3e-05 | `Ripple Effect (Closeness):` 0.011082
  * `Imports (Out-Degree: 1):` gc, gitgalaxy.standards, gitgalaxy.standards.config_resolver, json, logging, pathlib, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/guidestar_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 242.0 | **LOC:** 512 | **CtrlFlow:** 62.9% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (11.9704%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_calculate_documentation_coverage` (Impact: 22.8)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `get_intent_status` (Impact: 22.5)
    * *Intent:* """Returns the specific Intent Lock for a given file path based on strict, pattern, or sector match....
  * `_deep_inspect_manifest` (Impact: 18.7)
    * *Intent:* """Dispatches files to specific parsers based on their format."""
  * `_scan_gitattributes` (Impact: 18.0)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `_parse_package_json` (Impact: 17.0)
    * *Intent:* """Extracts 'main', 'bin', and 'scripts' from Node/JS manifests."""
**Contextual Mitigations & Amplifications:**
* *Sec Io:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 90`, `structural_boundaries: 53`, `args: 15`, `func_start: 15`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 15`, `state_mutation: 22`
* *Architecture:* `io: 8`, `api: 7`, `import: 8`
* *Defense:* `safety: 16`, `doc: 32`, `sync_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.183
  * `Choke Point (Betweenness):` 1.3e-05 | `Ripple Effect (Closeness):` 0.011082
  * `Imports (Out-Degree: 1):` fnmatch, gitgalaxy.standards.gitgalaxy_config, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 226.22 | **LOC:** 442 | **CtrlFlow:** 67.6% | **Authorship Centralization:** 66.7%
- **Risk Profile:** Cognitive Load (17.0768%), Tech Debt (10.5488%)
**Top Internal Functions/Classes:**
  * `build_dependency_graph` (Impact: 99.1)
    * *Intent:* """ Builds the directed graph and calculates multi-dimensional risk vectors. Modifies the 'telemetry...
  * `_fallback_build_graph` (Impact: 34.3)
  * `extract_test_coverage_mapping` (Impact: 32.4)
    * *Intent:* """ Maps function calls from test files to their imported production targets. Returns a dictionary m...
  * `_resolve_target` (Impact: 17.8)
    * *Intent:* """ Resolves an import token to a single file path, refusing to guess when genuinely ambiguous rathe...
  * `_build_resolution_map` (Impact: 9.8)
    * *Intent:* """ Maps each lookup key (full path, filename, stem) to ALL candidate file paths sharing that key — ...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 96`, `structural_boundaries: 46`, `args: 6`, `func_start: 6`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 24`, `state_mutation: 16`, `dead_code: 1`, `planned_debt: 1`
* *Architecture:* `io: 1`, `api: 6`, `import: 10`
* *Defense:* `safety: 21`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.649
  * `Choke Point (Betweenness):` 1.7e-05 | `Ripple Effect (Closeness):` 0.014184
  * `Imports (Out-Degree: 1):` collections, gitgalaxy.standards.analysis_lens, logging, math, networkx, networkx.algorithms, pathlib, token...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/sbom_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 214.34 | **LOC:** 359 | **CtrlFlow:** 52.8% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (18.8906%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `generate_report` (Impact: 73.2)
  * `_audit_with_cache` (Impact: 45.6)
    * *Intent:* """ CACHED mode: every candidate file is hashed; verdicts are reused on hash hits and freshly comput...
  * `_audit_capped_sample` (Impact: 17.2)
    * *Intent:* """ LEGACY mode (no cache configured): per-directory capped sampling (#254). Coverage is honestly di...
  * `_scan_single_file` (Impact: 12.4)
    * *Intent:* """Runs the security lens + language detector on one file. Returns (is_spoof, notes) or None if the ...
  * `_iter_candidate_files` (Impact: 11.5)
    * *Intent:* """ Yields every auditable code file in the package in RISK-PRIORITY order: entry-point-named files ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 56`, `structural_boundaries: 50`, `args: 7`, `func_start: 7`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 12`, `state_mutation: 34`
* *Architecture:* `io: 5`, `api: 3`, `import: 12`
* *Defense:* `safety: 4`, `doc: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.183
  * `Choke Point (Betweenness):` 6.3e-05 | `Ripple Effect (Closeness):` 0.014184
  * `Imports (Out-Degree: 3):` datetime, gitgalaxy.security.manifest_parser, gitgalaxy.security.security_lens, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_lens, gitgalaxy.standards.language_standards, json, logging...
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/security_auditor.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 210.94 | **LOC:** 434 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` (Impact: 50.2)
    * *Intent:* """ Resolves transitive fragility and Downstream Exposure using C-optimized traversals (NetworkX) if...
  * `audit_repository` (Impact: 40.2)
    * *Intent:* """ Orchestrates the resolution of transitive dependency graphs and executes the XGBoost model again...
  * `__init__` (Impact: 30.2)
    * *Intent:* # Updated default to the new multiclass model
  * `_construct_feature_matrix` (Impact: 29.7)
    * *Intent:* """Reconstructs the Pandas DataFrame exactly as train_threat_model.py did."""
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
  * `Imports (Out-Degree: 0):` collections, gitgalaxy.standards.analysis_lens, logging, networkx, numpy, pandas, pathlib, typing...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/chronometer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 199.88 | **LOC:** 458 | **CtrlFlow:** 60.6% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (13.5203%), Tech Debt (14.7229%)
**Top Internal Functions/Classes:**
  * `_stream_git_log` (Impact: 67.6)
  * `_determine_commit_bounds` (Impact: 29.0)
    * *Intent:* """ [SIGNAL 1: ABSOLUTE BOUNDARIES] Determines the project's start and end dates for temporal normal...
  * `__init__` (Impact: 15.7)
  * `_load_ignored_revs` (Impact: 10.7)
    * *Intent:* """Loads non-functional cosmetic commits to filter out of the churn math."""
  * `_initialize_history_scan` (Impact: 10.5)
    * *Intent:* """Dispatches the survey engines to establish boundaries and churn cache."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 63`, `structural_boundaries: 41`, `args: 8`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 13`, `high_risk_execution: 1`, `state_mutation: 35`, `fragile_debt: 1`
* *Architecture:* `io: 8`, `api: 4`, `import: 8`
* *Defense:* `safety: 18`, `doc: 18`, `test: 1`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.183
  * `Choke Point (Betweenness):` 1.3e-05 | `Ripple Effect (Closeness):` 0.011082
  * `Imports (Out-Degree: 1):` gitgalaxy.standards, gitgalaxy.standards.config_resolver, logging, os, pathlib, shutil, subprocess, time...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/extraction/languages/test_ada_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 198.08 | **LOC:** 436 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_ada_signature_positive_and_negative` (Impact: 10.3)
  * `test_ada_caret_anchored_rules_all_set_multiline_flag` (Impact: 8.8)
    * *Intent:* # ============================================================================== # TEST 6: RE.M COMP...
  * `test_ada_redos_immunity_sweep` (Impact: 8.0)
    * *Intent:* # ============================================================================== # TEST 8: REDOS ADV...
  * `test_ada_lexical_family_is_correctly_wired_not_just_labeled` (Impact: 7.1)
    * *Intent:* # ============================================================================== # TEST 3: LEXICAL-F...
  * `test_ada_attribute_forms_match_realistic_attached_syntax` (Impact: 5.5)
    * *Intent:* # ============================================================================== # TEST 4: SYMBOLIC-...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, gitgalaxy.core.prism, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, incorrectly, pathlib, pytest, re...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_livecode_strict.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 179.2 | **LOC:** 682 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `assert_linear_redos_scaling` (Impact: 20.4)
    * *Intent:* """ Measures pattern.search() time at each size in `sizes` (each isolated in its own subprocess via ...
  * `test_livecode_signature_positive_and_negative` (Impact: 10.4)
  * `test_livecode_dependency_capture_extracts_path` (Impact: 9.9)
    * *Intent:* """ _dependency_capture is paired with `import` and must extract the exact dependency path/module st...
  * `_measure_scaling_point` (Impact: 6.7)
    * *Intent:* # ============================================================================== # REDOS SCALING VER...
  * `test_livecode_state_mutation_multiword_expression_regression` (Impact: 6.0)
    * *Intent:* """ Regression test: put/add/subtract's source-expression matcher used `[^ \\t\\n]+?`, which exclude...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, gitgalaxy.standards.language_standards, multiprocessing, pathlib, pytest, re, shapes, sys
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unclassified` (Drift: 0.0 IQR)
- **Local Micro-Species:** `Unclassified` (Drift: 0.0 IQR)
- **Magnitude:** 170.7 | **LOC:** 434 | **CtrlFlow:** 50.9% | **Authorship Centralization:** 100.0%
- **Risk Profile:** Cognitive Load (18.3929%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `main` (Impact: 32.5)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `process_payload` (Impact: 26.7)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `record_dead_code` (Impact: 14.4)
  * `calibrate_ir_medium` (Impact: 12.9)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `get_dead_paras` (Impact: 9.2)
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 54`, `structural_boundaries: 52`, `args: 10`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 6`, `state_mutation: 42`
* *Architecture:* `io: 4`, `api: 9`, `import: 17`
* *Defense:* `safety: 4`, `doc: 10`, `cleanup: 3`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 4.064
  * `Choke Point (Betweenness):` 0.000114 | `Ripple Effect (Closeness):` 0.003546
  * `Imports (Out-Degree: 9):` argparse, datetime, gitgalaxy.licensing, gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge, gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect, gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge...
  * `Imported By (In-Degree: 1):` (Excluded from Brief to save tokens)

### `tests/ast_accuracy_audit.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 167.0 | **LOC:** 452 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `measure` (Impact: 38.4)
    * *Intent:* """Runs the full pinned-corpus scan + `ast` diff, returns the metrics dict (see module docstring).""...
  * `_print_report` (Impact: 16.5)
  * `run_ci_check` (Impact: 14.7)
  * `_regressions` (Impact: 10.9)
  * `run_full_report` (Impact: 9.2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` argparse, ast, io, json, os, pathlib, shutil, sqlite3...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_perl_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 164.1 | **LOC:** 566 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_perl_args_prototype_falls_through_to_body_idiom_scan` (Impact: 11.6)
    * *Intent:* """ #1607: a legacy Perl PROTOTYPE (`sub Get8u($$)`) is a sequence of bare sigils with NO commas, ev...
  * `test_perl_signature_positive_and_negative` (Impact: 10.4)
  * `test_perl_args_anonymous_and_qualified_signatures` (Impact: 9.5)
  * `test_perl_branch_colon_ambiguity_and_defined_or` (Impact: 8.3)
  * `test_perl_globals_magic_variable_boundary_regression` (Impact: 7.8)
    * *Intent:* """ Regression test: `$$`, `$@`, `$!`, and `$?` were inside the shared trailing \\b group. Each ends...
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

### `gitgalaxy/standards/analysis_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 163.48 | **LOC:** 8288 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `get_policy` (Impact: 1.6)
    * *Intent:* """Returns the specific threat thresholds based on the deployment mode."""
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` X, re, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/extraction/languages/test_html_strict.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `Unknown Archetype` (Drift: N/A IQR)
- **Magnitude:** 163.16 | **LOC:** 645 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Risk Profile:** Cognitive Load (0.0%), Tech Debt (0.0%)
**Top Internal Functions/Classes:**
  * `test_html_star_ngif_leading_boundary_regression` (Impact: 12.0)
    * *Intent:* """ Regression test for a real bug: `branch`'s `*ngIf` (Angular's structural directive) was inside t...
  * `test_html_single_quote_bug_reproduces_on_old_double_quote_only_patterns` (Impact: 11.3)
    * *Intent:* # NOTE: this test was originally grouped under a shared "cross-language sweep" # section in tests/co...
  * `test_html_signature_positive_and_negative` (Impact: 10.3)
  * `test_html_signature_adversarial` (Impact: 10.3)
  * `test_html_signature_deep` (Impact: 10.3)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` 0.0
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 0):` _strict_harness, gitgalaxy.standards.language_standards, pathlib, pytest, re, sys
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 13. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 13.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (93.1% isolated ownership) | Magnitude: 3684.48
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (87.5% isolated ownership) | Magnitude: 1564.86
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 1270.2
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (81.8% isolated ownership) | Magnitude: 1098.92
- `gitgalaxy/core/prism.py` -> **Joe Esquibel** (93.3% isolated ownership) | Magnitude: 732.38

## 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/galaxyscope.py` -> **Severity: 0.086** (Bridge: 0.001 * Flux: 82.9593%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.023** (Bridge: 0.0004 * Flux: 56.9871%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.011** (Bridge: 0.0001 * Flux: 97.3782%)
- `gitgalaxy/recorders/sbom_recorder.py` -> **Severity: 0.006** (Bridge: 0.0001 * Flux: 96.9481%)
- `gitgalaxy/security/security_auditor.py` -> **Severity: 0.003** (Bridge: 0.0 * Flux: 94.7128%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/core/detector.py` -> **Severity: 3.743** (Embedded: 0.0617 * Error Risk: 60.691%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 2.721** (Embedded: 0.0464 * Error Risk: 58.6062%)
- `gitgalaxy/core/prism.py` -> **Severity: 2.509** (Embedded: 0.0306 * Error Risk: 81.8657%)
- `gitgalaxy/standards/gitgalaxy_config.py` -> **Severity: 2.208** (Embedded: 0.0395 * Error Risk: 55.9468%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 1.776** (Embedded: 0.038 * Error Risk: 46.7319%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/analysis_lens.py` -> **Severity: 435.71** (Blast Radius: 24.368 * Doc Risk: 17.8804%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 363.222** (Blast Radius: 20.314 * Doc Risk: 17.8804%)
- `gitgalaxy/core/detector.py` -> **Severity: 293.221** (Blast Radius: 16.785 * Doc Risk: 17.4692%)
- `gitgalaxy/standards/gitgalaxy_config.py` -> **Severity: 285.639** (Blast Radius: 15.975 * Doc Risk: 17.8804%)
- `scripts/update_golden_masters.sh` -> **Severity: 195.787** (Blast Radius: 2.197 * Doc Risk: 89.1154%)

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Stay in the Senior Technical Storyteller persona from Section 1. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility) woven into a cohesive narrative -- not a dry, disconnected bullet-point audit. DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective and factual, but write like you're explaining the codebase to a colleague, not filing a verdict.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with massive Cumulative Risk, severe Z-Scores (Architectural Drift), or extreme spikes in individual risk vectors (like State Flux or Cognitive Load). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
