# ARCHITECTURAL_BRIEF: gitgalaxy
> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.

## 0. FORENSIC TRACEABILITY
| Metadata | Value |
|---|---|
| **Engine** | `GitGalaxy Scope vlatest (Delta Mode)` |
| **Git Remote** | `https://github.com/squid-protocol/gitgalaxy` |
| **Zero-Dependency Mode** | `Inactive (Full Precision)` |
| **File Archetype Brain** | corpus `master_db_v2.9.0.db` @ `71f3d405a2d8` · trainer `2b0cd20` · engine `unknown` · contract `92c0b8a801d69bb0` · trained `2026-09-19T12:02:33+00:00` |
| **Repo Archetype Brain** | corpus `master_db_v2.9.0.db` @ `71f3d405a2d8` · trainer `2b0cd20` · engine `unknown` · contract `7f4885b42206d553` · trained `2026-09-19T12:02:41+00:00` |

## 0.5 AI THREAT AUDIT STATUS
> **✅ SECURE_NO_THREATS_DETECTED**
> XGBoost Structural Signatures model found no malicious artifacts.

## 1. EXECUTIVE SUMMARY
- **Scope:** 485 analyzed artifact(s), 101658 LOC.
- **Load-bearing artifact:** `gitgalaxy/standards/language_standards/languages/json.py` -- 79 in-repo importer(s) depend on it. Changes here propagate furthest.
- **Top orchestrator:** `gitgalaxy/galaxyscope.py` -- pulls in 60 dependencies, the widest assembly point in the scan.
- **Heaviest artifact:** `gitgalaxy/core/detector.py` at magnitude 8615.2 (structural weight, not risk).
- **How to read this brief:** section 11 ranks artifacts by structural magnitude with a blast-radius line each; section 7 has the full dependency graph. The surface vectors in section 6 describe what is present in a file, not the probability of a defect -- Appendix A has the equations and the validation record behind that distinction.

## 1.5 SYSTEM ROLE & PHILOSOPHY
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
> *(Section 2, the structural-surface lexicon and its equations, is now **Appendix A** at the end of this brief -- the findings come first.)*

## 3. MACRO STATE
| Metric | Value |
|---|---|
| Total Artifacts | 1709 |
| Analyzed Artifacts (Scanned) | 485 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 1224 |
| Total LOC | 101658 |
| Volatility Index | 0.006 |
| % Scanned of codebase = | 28.4% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.6821 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.2766 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 1.8032 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 51 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 401 | 94352 | 82.7% |
| MARKDOWN | 32 | 0 | 6.6% |
| COBOL | 31 | 5969 | 6.4% |
| YAML | 13 | 1129 | 2.7% |
| PLAINTEXT | 4 | 0 | 0.8% |
| SHELL | 2 | 84 | 0.4% |
| JCL | 2 | 124 | 0.4% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Hub-Coupled App`
> **Architectural Drift Z-Score:** `1.796`
> **Composition Archetype:** `Hub-Coupled App` (z +1.80; from the repo's file-archetype mix)
> **File Composition:** Large Core Modules (2) 33%, Declarative / Non-Code 18%, Data / Markup / Trivial 13%, Large Core Modules (3) 7%, Parameter Forwarders Files 7%
> **ℹ️ TYPICAL INTERPRETATION:** This repository falls within standard variance (Z-Score between -1.0 and 2.0), representing a typical implementation of this archetype.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 449 | 92.6% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 36 | 7.4% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 1224*

**Composition by Extension & Reason:**
- `.snap`: 373x Excluded (Unsupported Extension: '.snap'), 218x Unsupported Format (.snap)
- `.md`: 433x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 41 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.json`: 50x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yml`: 24x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `no_extension`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Unsupported Format (.undeterminable)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 604 LOC), 1x Excluded (Saturation: Line 22 exceeds 500 chars)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csv`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.xml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 84.3 | 3.1 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 99.9 | 5.7 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 65.1 | 0.6 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 3.5 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 54.2 | 0.9 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 22.0 | 0.1 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 5.9 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 11.4 | 0.1 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 2.4 | 0.0 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 100.0 | 1.7 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) _(coverage)_ | 0.0 | 50.0 | 1.3 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

> `Doc Surface (formerly Documentation Exposure)` is **documentation coverage, not a fragility driver**. It is reported for context beside program length, and is deliberately excluded from the ranked-file drivers in this brief: it measures the share of a file's unit weight a reader cannot recover from documentation, so on a codebase that documents little it sits near ceiling everywhere and describes the repo rather than distinguishing files within it.
> `Spec Alignment (formerly Specification Exposure)` was **not measured** on this scan and is therefore absent above rather than reported as 0 (which would assert full alignment). Enable it with `--spec-alignment` if this codebase uses the corresponding convention.

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 387 | 22 | 0 | `gitgalaxy/recorders/record_keeper.py` |
| cleanup | 16 | 7 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 621 | 25 | 0 | `gitgalaxy/core/detector.py` |
| danger | 611 | 24 | 0 | `gitgalaxy/core/detector.py` |
| concurrency | 17 | 9 | 0 | `gitgalaxy/core/graph_engine.py` |
| connectivity | 143 | 24 | 0 | `gitgalaxy/core/detector.py` |
| io | 78 | 21 | 0 | `gitgalaxy/galaxyscope.py` |
| crypto | 3 | 3 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 31 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 48 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 170 | 9 | 0 | `gitgalaxy/core/detector.py` |
| events | 258 | 18 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 5 | 3 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 391 | 28 | 0 | `gitgalaxy/core/detector.py` |
| debt | 163 | 17 | 0 | `gitgalaxy/core/detector.py` |
| mutation | 9109 | 27 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 66 | 7 | 0 | `gitgalaxy/core/detector.py` |
| credential | 2 | 2 | 0 | `gitgalaxy/core/detector.py` |
| threat | 74 | 11 | 0 | `gitgalaxy/metrics/signal_processor.py` |
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

1. **json.py** (`gitgalaxy/standards/language_standards/languages/json.py`) — 79 inbound connections
2. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 64 inbound connections
3. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 50 inbound connections
4. **detector.py** (`gitgalaxy/core/detector.py`) — 48 inbound connections
5. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 47 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 60 outbound dependencies
2. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 30 outbound dependencies
3. **test_import_contract_2875.py** (`tests/extraction/languages/test_import_contract_2875.py`) — 30 outbound dependencies
4. **test_python_strict.py** (`tests/extraction/languages/test_python_strict.py`) — 27 outbound dependencies
5. **test_network_risk_sensor.py** (`tests/security_auditing/test_network_risk_sensor.py`) — 22 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1155.8** | LOC: 1315
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **838.0** | LOC: 1097
- `splice` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **477.1** | LOC: 830
- `inspect` **(Many-Argument Workhorses)** (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **382.4** | LOC: 447
- `_calculate_block_metrics` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **322.8** | LOC: 470
- `generate_report` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/audit_recorder.py`) -> Impact: **300.6** | LOC: 524
- `execute_pipeline` **(Many-Argument Workhorses)** (@ `gitgalaxy/galaxyscope.py`) -> Impact: **265.4** | LOC: 632
  * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execution Flow): The method enforces a strict chronologi...
- `calculate_risk_vector` **(Many-Argument Workhorses)** (@ `gitgalaxy/metrics/signal_processor.py`) -> Impact: **258.2** | LOC: 647
- `_slice_by_keywords` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **248.9** | LOC: 427
- `measure` **(Many-Argument Workhorses)** (@ `tests/tools/tree_sitter_accuracy_audit.py`) -> Impact: **217.8** | LOC: 477
  * *Intent:* """Runs the full pinned-corpus scan + tree-sitter diff, returns the metrics dict."""

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `tests/extraction/languages` | 109 | 14196.06 | 12.71% | 0.0% |
| `gitgalaxy/core` | 11 | 13366.24 | 37.63% | 12.45% |
| `tests/core_engine` | 44 | 7781.86 | 13.82% | 0.0% |
| `gitgalaxy/recorders` | 8 | 4859.64 | 47.18% | 4.22% |
| `gitgalaxy/metrics` | 7 | 3498.68 | 45.58% | 14.15% |
| `gitgalaxy` | 6 | 3308.9 | 32.84% | 0.0% |
| `gitgalaxy/standards` | 9 | 2028.06 | 12.46% | 6.31% |
| `tests/security_auditing` | 15 | 1789.56 | 12.11% | 0.0% |
| `gitgalaxy/security` | 7 | 1649.56 | 38.17% | 2.03% |
| `gitgalaxy/standards/language_standards/languages` | 64 | 1409.26 | 5.92% | 63.38% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `gitgalaxy/core/rule_prefilter.py` -> **65.1355%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **49.5567%** Exposure
- `gitgalaxy/core/prism.py` -> **45.3591%** Exposure
- `gitgalaxy/core/detector.py` -> **26.419%** Exposure
- `gitgalaxy/metrics/archetype_parity.py` -> **26.3198%** Exposure
### Highest Mutation Surface (formerly State Flux; Mutation/Volatility)
- `.claude/hooks/pytest_quiet.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/detector.py` -> **100.0%** Exposure
- `gitgalaxy/core/graph_engine.py` -> **100.0%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/metrics/archetype_classifier.py` -> **3** Orphaned Functions | **0** Duplicates
- `gitgalaxy/core/detector.py` -> **0** Orphaned Functions | **2** Duplicates
- `gitgalaxy/core/prism.py` -> **0** Orphaned Functions | **2** Duplicates
- `gitgalaxy/metrics/archetype_parity.py` -> **1** Orphaned Functions | **0** Duplicates

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
- **Unknown Dependencies:** `2715` packages imported that bypass the Zero-Trust whitelist.

## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)
> Ranked by Structural Magnitude: the file's structural weight and centralization within the system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not the vector percentages, is the actionable part.

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 8615.2 | **LOC:** 8997 | **CtrlFlow:** 41.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **48** in-repo importer(s); it depends on **18**; blast radius 22.71; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (100.0%), Guard Balance (formerly Safety Score) (99.5%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 21.4953% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1155.8)
  * `splice` **(Many-Argument Workhorses)** (Impact: 477.1)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 322.8)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 248.9)
  * `_build_brace_safe_stream` **(Many-Argument Workhorses)** (Impact: 178.4)
    * *Intent:* """ Shields string/char literals and (for C-family languages) dead #if/#else macro branches so a bra...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 1 instances
* *Amplified Cascading Flux:* 1167 instances
* *Concurrency (weighted view):* 7
* *State Mutation (weighted view):* 3681
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 1776`, `structural_boundaries: 547`, `args: 93`, `func_start: 89`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 101`, `state_mutation: 1347`, `dead_code: 56`, `planned_debt: 2`, `fragile_debt: 24`, `duplicate_logic: 2`
* *Architecture:* `api: 19`, `concurrency: 2`, `import: 19`
* *Defense:* `safety: 38`, `doc: 87`, `immutability_locks: 35`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 22.71
  * `Choke Point (Betweenness):` 0.001396 | `Ripple Effect (Closeness):` 0.094737
  * `Imports (Out-Degree: 4):` bisect, collections, exactly, functools, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.rule_prefilter, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens...
  * `Imported By (In-Degree: 48):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 2628.58 | **LOC:** 3516 | **CtrlFlow:** 25.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **8** in-repo importer(s); it depends on **60**; blast radius 3.862; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.0%), Complexity Load (formerly Cognitive Load) (84.3%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 20.7317% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 265.4)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_process_file_worker` **(Many-Argument Workhorses)** (Impact: 137.8)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `_resolve_dependency_graph` **(Compute Cores)** (Impact: 125.7)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `_calculate_risk_exposures` **(Many-Argument Workhorses)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
  * `main` **(I/O & Config Routines)** (Impact: 102.9)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 451 instances
* *Concurrency (weighted view):* 13
* *State Mutation (weighted view):* 1531
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 546`, `structural_boundaries: 241`, `args: 38`, `func_start: 27`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 79`, `high_risk_execution: 2`, `state_mutation: 629`, `dead_code: 2`
* *Architecture:* `io: 13`, `api: 7`, `concurrency: 3`, `import: 62`
* *Defense:* `safety: 48`, `doc: 21`, `test: 2`, `immutability_locks: 8`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 3.862
  * `Choke Point (Betweenness):` 0.001171 | `Ripple Effect (Closeness):` 0.016736
  * `Imports (Out-Degree: 30):` B, DAG, argparse, base64, collections, concurrent.futures, copy, datetime...
  * `Imported By (In-Degree: 8):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2506.42 | **LOC:** 1816 | **CtrlFlow:** 30.3% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **4** in-repo importer(s); it depends on **12**; blast radius 2.501; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Complexity Load (formerly Cognitive Load) (81.3%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 35.4167% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_build_markdown` **(Many-Argument Workhorses)** (Impact: 838.0)
  * `_executive_summary_lines` **(Stateful Encapsulated Methods)** (Impact: 58.0)
  * `generate_artifacts` **(Many-Argument Workhorses)** (Impact: 37.7)
  * `_lexicon_lines` **(Compute Cores)** (Impact: 33.9)
    * *Intent:* """The vector lexicon and the non-predictive disclaimer (#3113). Was section 2, ~75 lines of formula...
  * `_blast_radius_sentence` **(Stateful Encapsulated Methods)** (Impact: 26.0)
    * *Intent:* """What a change to this file would reach, in words (#3113). The brief already computed every number...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 423 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1394
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 390`, `structural_boundaries: 106`, `args: 41`, `func_start: 16`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 45`, `state_mutation: 548`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `io: 2`, `api: 3`, `concurrency: 2`, `import: 10`
* *Defense:* `safety: 17`, `doc: 20`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.501
  * `Choke Point (Betweenness):` 8e-06 | `Ripple Effect (Closeness):` 0.015181
  * `Imports (Out-Degree: 1):` collections, gitgalaxy.standards, heapq, hops, json, logging, pathlib, sqlite3...
  * `Imported By (In-Degree: 4):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 2220.92 | **LOC:** 5392 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **12**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_spatial_mapper_sectorization_and_monolith` **(Defensive Guards)** (Impact: 15.5)
    * *Intent:* """ Proves the engine correctly groups files into sector constellations by their parent directories,...
  * `test_detector_c_macro_dead_branch_shield` **(Defensive Guards)** (Impact: 14.7)
    * *Intent:* """ Pins that a statically-dead C preprocessor branch is not counted (#2814). `detector._blank_dead_...
  * `test_detector_c_macro_no_space_boundaries_issue_1764` **(Defensive Guards)** (Impact: 14.2)
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
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 2138.16 | **LOC:** 2321 | **CtrlFlow:** 26.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **13** in-repo importer(s); it depends on **12**; blast radius 6.986; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.4%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (64.6%)
- **Documentation Coverage:** 29.661% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` **(Many-Argument Workhorses)** (Impact: 258.2)
  * `summarize_galaxy_metrics` **(Many-Argument Workhorses)** (Impact: 191.6)
    * *Intent:* # ========================================================================== # GLOBAL SYNTHESIS & 2-...
  * `generate_forensic_report` **(Many-Argument Workhorses)** (Impact: 60.7)
    * *Intent:* # -------------------------------------------------------------------------- # REPORTING UTILITIES #...
  * `_calc_verification` **(Many-Argument Workhorses)** (Impact: 57.2)
  * `_compute_snapshot_percentiles` **(Stateful Encapsulated Methods)** (Impact: 41.1)
    * *Intent:* """[TIER 2, gitgalaxy#2994] Snapshot percentiles -- the honest 0-100. Ranks each file's 22 Tier-1 su...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *List:* 1 instances
* *Amplified Cascading Flux:* 324 instances
* *State Mutation (weighted view):* 1114
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 368`, `structural_boundaries: 146`, `args: 48`, `func_start: 37`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 44`, `state_mutation: 466`, `dead_code: 1`, `planned_debt: 1`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 10`, `concurrency: 2`, `import: 12`
* *Defense:* `safety: 30`, `doc: 28`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 6.986
  * `Choke Point (Betweenness):` 0.000132 | `Ripple Effect (Closeness):` 0.028687
  * `Imports (Out-Degree: 2):` a, collections.abc, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math...
  * `Imported By (In-Degree: 13):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 1929.2 | **LOC:** 1960 | **CtrlFlow:** 35.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **21** in-repo importer(s); it depends on **4**; blast radius 9.1; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (58.0%)
- **Documentation Coverage:** 21.1538% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` **(Many-Argument Workhorses)** (Impact: 124.1)
    * *Intent:* """ Single-line comment stripper for the "line_exclusive" family, driven by each language's own real...
  * `_strip_single_line_comments_positional` **(Many-Argument Workhorses)** (Impact: 122.2)
    * *Intent:* """Positional sibling of `_strip_single_line_comments`: same per-line masking and carry-quote discip...
  * `_mask_perl_line_positional` **(Many-Argument Workhorses)** (Impact: 75.4)
  * `_mask_perl_line` **(Many-Argument Workhorses)** (Impact: 75.4)
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 9.1
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.048913
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 21):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1595.24 | **LOC:** 1496 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **9**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 382.4)
  * `_tier_4_heuristic_discovery` **(Many-Argument Workhorses)** (Impact: 146.2)
    * *Intent:* # ========================================================================= # THE TIER 4 HEURISTIC D...
  * `_evaluate_ecosystem_gravity` **(Many-Argument Workhorses)** (Impact: 90.0)
  * `_tier_3_lexical_scan` **(Many-Argument Workhorses)** (Impact: 61.1)
  * `_resolve_by_sibling_content` **(Many-Argument Workhorses)** (Impact: 37.0)
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
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1094.58 | **LOC:** 2929 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **30**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_recorder_exception_survivability` **(Many-Argument Workhorses)** (Impact: 16.3)
    * *Intent:* # ============================================================================== # TEST 23: RECORDER...
  * `test_phase_10_manifest_paths_includes_all_supported_ecosystems` **(Many-Argument Workhorses)** (Impact: 13.4)
    * *Intent:* # ============================================================================== # TEST 33: MANIFEST...
  * `test_cicd_policy_enforcement_gates` **(Many-Argument Workhorses)** (Impact: 12.4)
    * *Intent:* # ============================================================================== # TEST 2: THE CI/CD...
  * `test_sarif_ignored_paths_sanitization` **(Compute Cores)** (Impact: 11.6)
    * *Intent:* # ============================================================================== # TEST 19: SARIF IG...
  * `test_synthetic_node_generation` **(Many-Argument Workhorses)** (Impact: 11.2)
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
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1060.58 | **LOC:** 748 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **6**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `slice_manifest` **(Compute Cores)** (Impact: 181.9)
  * `locate_physical_package` **(Many-Argument Workhorses)** (Impact: 129.9)
  * `_parse_pyproject_toml` **(Many-Argument Workhorses)** (Impact: 36.2)
    * *Intent:* """ Audits modern Python manifests (PEP 621 `[project] dependencies` arrays and Poetry's `[tool.poet...
  * `_parse_requirements_txt` **(Stateful Encapsulated Methods)** (Impact: 25.2)
    * *Intent:* """ Extracts direct Python packages and flags absolute VCS/URI references. """
  * `_parse_pip_conf` **(Stateful Encapsulated Methods)** (Impact: 23.2)
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
- **Global Archetype:** `file_cluster_5` (Drift: 0.0 IQR)
- **Magnitude:** 943.38 | **LOC:** 783 | **CtrlFlow:** 30.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** changing it is visible to **4** in-repo importer(s); it depends on **13**; blast radius 7.445; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (38.8%)
- **Documentation Coverage:** 14.4737% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_louvain_level` **(Many-Argument Workhorses)** (Impact: 53.1)
  * `betweenness_centrality` **(Many-Argument Workhorses)** (Impact: 29.7)
    * *Intent:* """ #3038: exact betweenness centrality, one value per node id: the share of shortest import paths b...
  * `pagerank` **(Many-Argument Workhorses)** (Impact: 27.0)
    * *Intent:* """ Weighted PageRank, one value per node id: the only PageRank the engine runs, in both modes (#302...
  * `closeness_and_path_length` **(Many-Argument Workhorses)** (Impact: 24.4)
  * `_louvain` **(Stateful Encapsulated Methods)** (Impact: 23.8)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 183 instances
* *State Mutation (weighted view):* 567
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 142`, `structural_boundaries: 71`, `args: 25`, `func_start: 25`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 9`, `state_mutation: 201`
* *Architecture:* `api: 16`, `import: 6`
* *Defense:* `doc: 25`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 7.445
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.051886
  * `Imports (Out-Degree: 0):` as, built, chain, collections, collections.abc, direction, graph, math...
  * `Imported By (In-Degree: 4):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/record_keeper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 832.68 | **LOC:** 1748 | **CtrlFlow:** 28.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **13** in-repo importer(s); it depends on **16**; blast radius 6.097; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.6%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (83.0%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 22.7273% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_classify_file_archetype` **(Many-Argument Workhorses)** (Impact: 52.6)
    * *Intent:* """Nearest-centroid file archetype from the assembled metrics, mirroring the offline apply_file_clus...
  * `_prep_file_brain` **(Stateful Encapsulated Methods)** (Impact: 36.2)
    * *Intent:* """#ENGINE-PARITY: cache the self-describing FILE archetype brain contract. The engine builds the fi...
  * `record_mission` **(Many-Argument Workhorses)** (Impact: 19.5)
  * `_file_feature_kind` **(Stateful Encapsulated Methods)** (Impact: 13.4)
    * *Intent:* """Which value source feeds this FEATURE_NAME, or None if the engine has none."""
  * `_ordered_raw_imports` **(Stateful Encapsulated Methods)** (Impact: 10.5)
    * *Intent:* """`raw_imports` as a deterministic JSON-safe list (#3220, ordering per #3227). Entries are import s...
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
* *Ai Guardrails:* 1 instances
* *Amplified Cascading Flux:* 197 instances
* *State Mutation (weighted view):* 651
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 259`, `structural_boundaries: 50`, `args: 10`, `func_start: 9`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 23`, `state_mutation: 257`, `dead_code: 2`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 8`
* *Defense:* `safety: 26`, `doc: 23`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 6.097
  * `Choke Point (Betweenness):` 4e-05 | `Ripple Effect (Closeness):` 0.030372
  * `Imports (Out-Degree: 2):` gitgalaxy.standards.analysis_lens, graph, json, logging, machine, math, numpy, or...
  * `Imported By (In-Degree: 13):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 782.8 | **LOC:** 2140 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **11**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
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

### `tests/cobol_mainframe/refraction_excerpts/aws-mainframe-modernization-carddemo/app/cbl/COCRDLIC.cbl` (COBOL | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 735.86 | **LOC:** 1460 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **11**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `0000-MAIN` **(I/O & Config Routines)** (Impact: 38.2)
  * `9000-READ-FORWARD` **(I/O & Config Routines)** (Impact: 28.9)
  * `1250-SETUP-ARRAY-ATTRIBS` **(I/O & Config Routines)** (Impact: 27.2)
  * `9100-READ-BACKWARDS` **(I/O & Config Routines)** (Impact: 19.4)
  * `1300-SETUP-SCREEN-ATTRS` **(I/O & Config Routines)** (Impact: 18.6)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` COCOM01Y, COCRDLI, COTTL01Y, CSDAT01Y, CSMSG01Y, CSSTRPFY, CSUSR01Y, CVACT02Y...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/audit_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 659.54 | **LOC:** 635 | **CtrlFlow:** 23.9% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **8**; blast radius 1.707; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.8%), Complexity Load (formerly Cognitive Load) (82.3%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 25.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `generate_report` **(Many-Argument Workhorses)** (Impact: 300.6)
  * `descale` **(Defensive Guards)** (Impact: 14.1)
    * *Intent:* """Dynamically scales integers back to floats using a fixed-string check."""
  * `format_label` **(Generic / Templated Code)** (Impact: 7.6)
    * *Intent:* """Translates raw dictionary keys into descriptive human-readable labels."""
  * `__init__` **(Stateful Encapsulated Methods)** (Impact: 6.4)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.707
  * `Choke Point (Betweenness):` 2e-06 | `Ripple Effect (Closeness):` 0.011905
  * `Imports (Out-Degree: 1):` argparse, gitgalaxy.standards, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/src/base/cobol_src/BNK1CAC.cbl` (COBOL | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 616.92 | **LOC:** 1300 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **3**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `ED010` **(I/O & Config Routines)** (Impact: 53.7)
  * `CAD010` **(I/O & Config Routines)** (Impact: 26.3)
  * `A010` **(I/O & Config Routines)** (Impact: 16.4)
  * `SM010` **(I/O & Config Routines)** (Impact: 13.5)
  * `RM010` **(I/O & Config Routines)** (Impact: 4.0)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` ABNDINFO, BNK1CAM, DFHAID
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/src/base/cobol_src/BANKDATA.cbl` (COBOL | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 597.18 | **LOC:** 1464 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `DBR010` **(I/O & Config Routines)** (Impact: 31.7)
  * `HV-ACCOUNT-ACTUAL-BALANCE` **(I/O & Config Routines)** (Impact: 11.2)
  * `ACCOUNT-OVERDRAFT-COUNT` **(I/O & Config Routines)** (Impact: 6.5)
  * `PA010` **(I/O & Config Routines)** (Impact: 4.5)
  * `CUSTOMER-BIRTH-YEAR` **(I/O & Config Routines)** (Impact: 4.4)
    * *Intent:* * FUNCTION RANDOM) +
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` ACCDB2, ACCTCTRL, CONTDB2, CUSTCTRL, CUSTOMER, SORTCODE, SQLCA
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/statistical_auditor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 523.12 | **LOC:** 589 | **CtrlFlow:** 25.4% | **Authorship Centralization:** 0.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **5**; blast radius 2.184; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (71.6%)
- **Documentation Coverage:** 11.1111% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `audit` **(Many-Argument Workhorses)** (Impact: 151.5)
    * *Intent:* """Executes statistical gating to identify data-dumps and structural outliers."""
  * `__init__` **(Many-Argument Workhorses)** (Impact: 10.7)
  * `_is_dead_code` **(Stateful Encapsulated Methods)** (Impact: 8.0)
    * *Intent:* """Determines if an artifact is predominantly dead code or comments."""
  * `_is_threat` **(Stateful Encapsulated Methods)** (Impact: 7.9)
    * *Intent:* """ Determines if an artifact contains active security threat signatures. Used by the Quarantine Gua...
  * `_is_highly_blended` **(Stateful Encapsulated Methods)** (Impact: 7.6)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.184
  * `Choke Point (Betweenness):` 4e-06 | `Ripple Effect (Closeness):` 0.011905
  * `Imports (Out-Degree: 1):` gitgalaxy.core.spatial_correlation, logging, os, statistics, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 511.52 | **LOC:** 602 | **CtrlFlow:** 28.3% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **7** in-repo importer(s); it depends on **16**; blast radius 8.741; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.7%), Complexity Load (formerly Cognitive Load) (38.9%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (25.0%)
- **Documentation Coverage:** 10.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_target` **(Many-Argument Workhorses)** (Impact: 66.2)
  * `_network_metrics` **(Many-Argument Workhorses)** (Impact: 36.8)
  * `extract_test_coverage_mapping` **(Many-Argument Workhorses)** (Impact: 32.5)
    * *Intent:* """ Maps function calls from test files to their imported production targets. Returns a dictionary m...
  * `_resolve_edges` **(Stateful Encapsulated Methods)** (Impact: 21.2)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 8.741
  * `Choke Point (Betweenness):` 0.000284 | `Ripple Effect (Closeness):` 0.068387
  * `Imports (Out-Degree: 2):` A, Text.Pandoc.Generic, collections, gitgalaxy.core.graph_engine, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, graph, logging...
  * `Imported By (In-Degree: 7):` (Excluded from Brief to save tokens)

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 447.8 | **LOC:** 578 | **CtrlFlow:** 21.8% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **19**; blast radius 2.074; role: Pure Consumer (Orchestrator)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.6%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (58.0%)
- **Documentation Coverage:** 42.5% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `process_payload` **(Many-Argument Workhorses)** (Impact: 57.8)
  * `main` **(I/O & Config Routines)** (Impact: 49.3)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `calibrate_ir_medium` **(Many-Argument Workhorses)** (Impact: 17.2)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `record_dead_code` **(Many-Argument Workhorses)** (Impact: 14.4)
  * `_output_keys` **(Stateful Encapsulated Methods)** (Impact: 9.4)
    * *Intent:* """Each program's name in the clean room's flat output directories and in the IR state: its stem whe...
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
* *Amplified Cascading Flux:* 75 instances
* *Api Near Db Sink:* 2 instances
* *State Mutation (weighted view):* 244
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 85`, `structural_boundaries: 66`, `args: 14`, `func_start: 12`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 8`, `high_risk_execution: 3`, `state_mutation: 94`
* *Architecture:* `io: 5`, `api: 9`, `import: 19`
* *Defense:* `safety: 3`, `doc: 7`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 2.074
  * `Choke Point (Betweenness):` 8.6e-05 | `Ripple Effect (Closeness):` 0.004132
  * `Imports (Out-Degree: 11):` argparse, collections, datetime, gitgalaxy.licensing, gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge, gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect, gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder, gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/rule_prefilter.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 439.26 | **LOC:** 634 | **CtrlFlow:** 40.3% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **6** in-repo importer(s); it depends on **7**; blast radius 7.887; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.6%), Test Surface (formerly Verification) (80.0%), Debt Markers (formerly Tech Debt) (65.1%)
- **Documentation Coverage:** 7.8947% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_walk_line_local` **(Many-Argument Workhorses)** (Impact: 62.8)
    * *Intent:* """Whitelist walk proving no node of `seq` can consume or anchor past a line boundary. Raises _NotLi...
  * `_walk_seq` **(Stateful Encapsulated Methods)** (Impact: 47.3)
    * *Intent:* """Collect every candidate requirement in a concatenation sequence. A match of the sequence matches ...
  * `derive_literal_gate` **(Many-Argument Workhorses)** (Impact: 41.6)
  * `derive_line_literals` **(Defensive Guards)** (Impact: 17.5)
    * *Intent:* """The per-line analogue of derive_literal_gate: a one-of literal set such that a line containing no...
  * `_in_set_can_match_nl` **(Stateful Encapsulated Methods)** (Impact: 16.7)
    * *Intent:* """Can this IN character set match '\\n'? Unknown items raise."""
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 62 instances
* *State Mutation (weighted view):* 187
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 116`, `structural_boundaries: 62`, `args: 17`, `func_start: 13`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 19`, `state_mutation: 63`, `planned_debt: 2`, `fragile_debt: 5`
* *Architecture:* `api: 6`, `import: 4`
* *Defense:* `safety: 13`, `doc: 15`, `immutability_locks: 9`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 7.887
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.06211
  * `Imports (Out-Degree: 0):` every, path, re, sre_constants, sre_parse, typing, works
  * `Imported By (In-Degree: 6):` (Excluded from Brief to save tokens)

### `tests/security_auditing/test_network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 418.24 | **LOC:** 854 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **22**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
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
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 385.22 | **LOC:** 469 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **8**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_construct_feature_matrix` **(Many-Argument Workhorses)** (Impact: 38.6)
    * *Intent:* """Reconstructs the Pandas DataFrame exactly as train_threat_model.py did."""
  * `audit_repository` **(Many-Argument Workhorses)** (Impact: 36.4)
    * *Intent:* """ Orchestrates the resolution of transitive dependency graphs and executes the XGBoost model again...
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 32.8)
    * *Intent:* """ Resolves each file's transitive fragility and Downstream Exposure. `total_upstream` counts every...
  * `__init__` **(Many-Argument Workhorses)** (Impact: 28.6)
    * *Intent:* # Updated default to the new multiclass model
  * `_or_nan` **(Encapsulated Accessors)** (Impact: 4.4)
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
- **Global Archetype:** `file_cluster_5` (Drift: 0.0 IQR)
- **Magnitude:** 380.34 | **LOC:** 527 | **CtrlFlow:** 25.9% | **Authorship Centralization:** 0.0%
- **Blast Radius:** changing it is visible to **3** in-repo importer(s); it depends on **8**; blast radius 2.025; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.1%), Complexity Load (formerly Cognitive Load) (36.9%), Connectivity (formerly Api Exposure) (10.1%)
- **Documentation Coverage:** 5.2632% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `get_intent_status` **(Compute Cores)** (Impact: 22.5)
    * *Intent:* """Returns the specific Intent Lock for a given file path based on strict, pattern, or sector match....
  * `_calculate_documentation_coverage` **(Stateful Encapsulated Methods)** (Impact: 21.4)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `__init__` **(Many-Argument Workhorses)** (Impact: 17.0)
  * `_scan_gitattributes` **(Stateful Encapsulated Methods)** (Impact: 15.2)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `_deep_inspect_manifest` **(Stateful Encapsulated Methods)** (Impact: 14.2)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.025
  * `Choke Point (Betweenness):` 1e-05 | `Ripple Effect (Closeness):` 0.013524
  * `Imports (Out-Degree: 2):` fnmatch, gitgalaxy.standards.gitgalaxy_config, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 3):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 375.7 | **LOC:** 1325 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **8**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
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
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 361.86 | **LOC:** 449 | **CtrlFlow:** 13.7% | **Authorship Centralization:** 0.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **7**; blast radius 2.184; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (55.6%)
- **Documentation Coverage:** 31.25% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `record_mission` **(Many-Argument Workhorses)** (Impact: 119.0)
  * `__init__` **(Generic / Templated Code)** (Impact: 7.6)
  * `_intern` **(Encapsulated Accessors)** (Impact: 4.2)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.184
  * `Choke Point (Betweenness):` 1.9e-05 | `Ripple Effect (Closeness):` 0.011905
  * `Imports (Out-Degree: 2):` gc, gitgalaxy.standards, gitgalaxy.standards.config_resolver, json, logging, pathlib, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

## 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 12.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/core/detector.py` -> Churn: **100.0%** | Cog Load: 67.6312% | Debt: 26.419%
- `gitgalaxy/recorders/record_keeper.py` -> Churn: **83.05%** | Cog Load: 56.6301% | Debt: 9.2593%
- `gitgalaxy/galaxyscope.py` -> Churn: **70.18%** | Cog Load: 84.3126% | Debt: 0.0%
- `gitgalaxy/metrics/signal_processor.py` -> Churn: **64.62%** | Cog Load: 63.6064% | Debt: 8.9543%
- `gitgalaxy/cobol_refractor_controller.py` -> Churn: **58.05%** | Cog Load: 57.8559% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 8615.2
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2628.58
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2506.42
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2138.16
- `gitgalaxy/core/prism.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 1929.2

## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/detector.py` -> **Severity: 0.14** (Bridge: 0.0014 * Flux: 100.0%)
- `gitgalaxy/galaxyscope.py` -> **Severity: 0.117** (Bridge: 0.0012 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.028** (Bridge: 0.0003 * Flux: 100.0%)
- `gitgalaxy/metrics/signal_processor.py` -> **Severity: 0.013** (Bridge: 0.0001 * Flux: 100.0%)
- `gitgalaxy/cobol_refractor_controller.py` -> **Severity: 0.009** (Bridge: 0.0001 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/language_standards/languages/json.py` -> **Severity: 13.41** (Embedded: 0.191 * Error Risk: 70.2063%)
- `tests/extraction/languages/_strict_harness.py` -> **Severity: 11.085** (Embedded: 0.1322 * Error Risk: 83.8311%)
- `gitgalaxy/core/detector.py` -> **Severity: 9.43** (Embedded: 0.0947 * Error Risk: 99.5433%)
- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 8.243** (Embedded: 0.098 * Error Risk: 84.1131%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 7.534** (Embedded: 0.0816 * Error Risk: 92.3601%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/core/detector.py` -> **Severity: 488.158** (Blast Radius: 22.71 * Doc Risk: 21.4953%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 442.141** (Blast Radius: 9.363 * Doc Risk: 47.2222%)
- `tests/tools/fidelity_table.py` -> **Severity: 386.625** (Blast Radius: 5.155 * Doc Risk: 75.0%)
- `tests/tools/tri_comparison_reconcile.py` -> **Severity: 351.36** (Blast Radius: 4.392 * Doc Risk: 80.0%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 347.3** (Blast Radius: 13.892 * Doc Risk: 25.0%)

## APPENDIX A. STRUCTURAL SURFACE LEXICON (EQUATIONS & CONTEXT)
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

## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)
> **CRITICAL TONE DIRECTIVE:** Stay in the Senior Technical Storyteller persona from Section 1. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility) woven into a cohesive narrative -- not a dry, disconnected bullet-point audit. DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective and factual, but write like you're explaining the codebase to a colleague, not filing a verdict.
> **When the user asks for an architectural review, structure your response using these directives:**
> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal.
> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports).
> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats.
> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with high Structural Magnitude combined with a wide Blast Radius, severe Z-Scores (Architectural Drift), or extreme spikes in individual surface vectors (like Mutation Surface or Complexity Load). Do NOT sum the surface vectors together or treat any total of them as a score -- they are independently scaled meters in different units (#3112). Ignore normal, healthy code.
> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture.
