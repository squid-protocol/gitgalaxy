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
- **Scope:** 709 analyzed artifact(s), 154839 LOC.
- **Load-bearing artifact:** `gitgalaxy/standards/language_standards/languages/json.py` -- 124 in-repo importer(s) depend on it. Changes here propagate furthest.
- **Top orchestrator:** `gitgalaxy/galaxyscope.py` -- pulls in 76 dependencies, the widest assembly point in the scan.
- **Heaviest artifact:** `gitgalaxy/core/detector.py` at magnitude 9782.66 (structural weight, not risk).
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
| Total Artifacts | 2791 |
| Analyzed Artifacts (Scanned) | 709 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 2082 |
| Total LOC | 154839 |
| Volatility Index | 0.013 |
| % Scanned of codebase = | 25.4% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.6909 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.2168 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.0% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 3.1011 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 72 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 590 | 141638 | 83.2% |
| COBOL | 43 | 8398 | 6.1% |
| MARKDOWN | 36 | 0 | 5.1% |
| YAML | 13 | 1129 | 1.8% |
| PLI | 8 | 1411 | 1.1% |
| BMS | 6 | 1322 | 0.8% |
| PLAINTEXT | 4 | 0 | 0.6% |
| JCL | 4 | 359 | 0.6% |
| SHELL | 3 | 140 | 0.4% |
| HLASM | 2 | 442 | 0.3% |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Hub-Coupled App`
> **Architectural Drift Z-Score:** `1.568`
> **Composition Archetype:** `Hub-Coupled App` (z +1.57; from the repo's file-archetype mix)
> **File Composition:** Large Core Modules (2) 37%, Declarative / Non-Code 13%, Data / Markup / Trivial 10%, Large Core Modules (3) 10%, Generic / Templated Code Files 7%
> **ℹ️ TYPICAL INTERPRETATION:** This repository falls within standard variance (Z-Score between -1.0 and 2.0), representing a typical implementation of this archetype.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 669 | 94.4% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 40 | 5.6% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 2082*

**Composition by Extension & Reason:**
- `.snap`: 635x Excluded (Unsupported Extension: '.snap'), 336x Unsupported Format (.snap)
- `.json`: 498x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.md`: 445x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 350 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.yml`: 31x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `no_extension`: 13x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Unsupported Format (.undeterminable)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 599 LOC), 1x Excluded (Machine-Generated Source Code Signature: 349 LOC)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csd`: 2x Excluded (Unsupported Extension: '.csd'), 1x Excluded (Unsupported Extension: '.CSD')
- `.csv`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.jsonl`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Saturation: Line 1 exceeds 500 chars)
- `.svg`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 85.2 | 4.6 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 100.0 | 7.9 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 65.1 | 0.5 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 5.1 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 54.2 | 0.9 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 19.1 | 0.1 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 8.1 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 25.3 | 0.1 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 0.9 | 0.0 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 86.4 | 2.1 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) _(coverage)_ | 0.0 | 100.0 | 1.7 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

> `Doc Surface (formerly Documentation Exposure)` is **documentation coverage, not a fragility driver**. It is reported for context beside program length, and is deliberately excluded from the ranked-file drivers in this brief: it measures the share of a file's unit weight a reader cannot recover from documentation, so on a codebase that documents little it sits near ceiling everywhere and describes the repo rather than distinguishing files within it.
> `Spec Alignment (formerly Specification Exposure)` was **not measured** on this scan and is therefore absent above rather than reported as 0 (which would assert full alignment). Enable it with `--spec-alignment` if this codebase uses the corresponding convention.

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 688 | 43 | 0 | `gitgalaxy/recorders/record_keeper.py` |
| cleanup | 23 | 9 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 1249 | 53 | 0 | `gitgalaxy/core/detector.py` |
| danger | 1113 | 51 | 0 | `gitgalaxy/galaxyscope.py` |
| concurrency | 21 | 10 | 0 | `gitgalaxy/core/detector.py` |
| connectivity | 226 | 51 | 0 | `gitgalaxy/core/detector.py` |
| io | 101 | 25 | 0 | `scripts/setup_java_toolchain.sh` |
| crypto | 3 | 3 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 33 | 4 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 50 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 372 | 32 | 0 | `gitgalaxy/core/detector.py` |
| events | 278 | 20 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 5 | 3 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 638 | 55 | 0 | `gitgalaxy/core/detector.py` |
| debt | 189 | 19 | 0 | `gitgalaxy/cobol_to_java_controller.py` |
| mutation | 13534 | 55 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 75 | 12 | 0 | `gitgalaxy/core/detector.py` |
| credential | 2 | 2 | 0 | `gitgalaxy/core/detector.py` |
| threat | 84 | 13 | 0 | `gitgalaxy/metrics/signal_processor.py` |
| ml_ai | 0 | 0 | 0 | - |
| ui | 1 | 1 | 0 | `gitgalaxy/recorders/llm_recorder.py` |

**Relations (repo medians):**
- `guard_balance_ratio` (guards / (danger + 1)): **0.0**
- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **0.0**

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `scripts/setup_java_toolchain.sh` (Hits: 17)
- `gitgalaxy/galaxyscope.py` (Hits: 13)
- `bitbucket-pipelines.yml` (Hits: 10)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **json.py** (`gitgalaxy/standards/language_standards/languages/json.py`) — 124 inbound connections
2. **detector.py** (`gitgalaxy/core/detector.py`) — 72 inbound connections
3. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 69 inbound connections
4. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 68 inbound connections
5. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 49 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 76 outbound dependencies
2. **import_graph_accuracy.py** (`tests/tools/import_graph_accuracy.py`) — 46 outbound dependencies
3. **cobol_to_java_messaging_forge.py** (`gitgalaxy/tools/cobol_to_java/cobol_to_java_messaging_forge.py`) — 41 outbound dependencies
4. **network_risk_sensor.py** (`gitgalaxy/core/network_risk_sensor.py`) — 36 outbound dependencies
5. **test_galaxyscope.py** (`tests/core_engine/test_galaxyscope.py`) — 33 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1164.5** | LOC: 1330
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **943.9** | LOC: 1117
- `score` **(Many-Argument Workhorses)** (@ `tests/tools/cobol_answer_key.py`) -> Impact: **653.2** | LOC: 664
- `_mainframe_facts_lines` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **508.6** | LOC: 404
  * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These are the named mainframe relations/schemas the per-fi...
- `splice` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **477.5** | LOC: 838
- `_calculate_block_metrics` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **473.3** | LOC: 525
- `load_galaxy_ir` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py`) -> Impact: **384.0** | LOC: 648
  * *Intent:* """Loads the latest snapshot of one repo from a master DB, opened read-only."""
- `inspect` **(Many-Argument Workhorses)** (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **382.4** | LOC: 447
- `generate_report` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/audit_recorder.py`) -> Impact: **358.4** | LOC: 567
- `execute_pipeline` **(Many-Argument Workhorses)** (@ `gitgalaxy/galaxyscope.py`) -> Impact: **269.1** | LOC: 671
  * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execution Flow): The method enforces a strict chronologi...

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `gitgalaxy/core` | 39 | 24941.3 | 51.61% | 4.55% |
| `tests/extraction/languages` | 125 | 15123.12 | 12.58% | 0.0% |
| `tests/core_engine` | 83 | 10277.64 | 12.41% | 0.0% |
| `gitgalaxy/recorders` | 8 | 6677.68 | 46.86% | 4.02% |
| `tests/cobol_mainframe` | 49 | 5363.5 | 12.92% | 0.0% |
| `gitgalaxy` | 6 | 3736.66 | 36.35% | 1.63% |
| `gitgalaxy/metrics` | 7 | 3546.68 | 45.95% | 14.15% |
| `tests/tools_recorders` | 42 | 2612.06 | 11.41% | 0.0% |
| `gitgalaxy/standards` | 10 | 2313.04 | 16.48% | 5.68% |
| `tests/security_auditing` | 16 | 1993.8 | 11.62% | 0.0% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `gitgalaxy/core/rule_prefilter.py` -> **65.1355%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **49.5567%** Exposure
- `gitgalaxy/core/prism.py` -> **45.2374%** Exposure
- `gitgalaxy/core/mainframe_boundary.py` -> **42.6289%** Exposure
- `gitgalaxy/metrics/archetype_parity.py` -> **26.3198%** Exposure
### Highest Mutation Surface (formerly State Flux; Mutation/Volatility)
- `.claude/hooks/pytest_quiet.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/bms_screen_fields.py` -> **100.0%** Exposure
- `gitgalaxy/core/bms_symbolic.py` -> **100.0%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/core/mainframe_boundary.py` -> **0** Orphaned Functions | **11** Duplicates
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
- **Unknown Dependencies:** `4068` packages imported that bypass the Zero-Trust whitelist.

## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)
> Ranked by Structural Magnitude: the file's structural weight and centralization within the system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not the vector percentages, is the actionable part.

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 9782.66 | **LOC:** 9848 | **CtrlFlow:** 42.5% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **72** in-repo importer(s); it depends on **19**; blast radius 23.229; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (67.4%)
- **Documentation Coverage:** 20.7317% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1164.5)
  * `splice` **(Many-Argument Workhorses)** (Impact: 477.5)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 473.3)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 254.5)
  * `_build_brace_safe_stream` **(Many-Argument Workhorses)** (Impact: 178.4)
    * *Intent:* """ Shields string/char literals and (for C-family languages) dead #if/#else macro branches so a bra...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 3 instances
* *Amplified Cascading Flux:* 1321 instances
* *Concurrency (weighted view):* 19
* *State Mutation (weighted view):* 4160
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 2042`, `structural_boundaries: 618`, `args: 111`, `func_start: 106`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 126`, `state_mutation: 1518`, `dead_code: 56`, `planned_debt: 2`, `fragile_debt: 25`, `duplicate_logic: 2`
* *Architecture:* `api: 20`, `concurrency: 4`, `import: 20`
* *Defense:* `safety: 45`, `doc: 102`, `immutability_locks: 42`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 23.229
  * `Choke Point (Betweenness):` 0.005103 | `Ripple Effect (Closeness):` 0.100948
  * `Imports (Out-Degree: 5):` bisect, collections, exactly, functools, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.rule_prefilter, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens...
  * `Imported By (In-Degree: 72):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 3735.26 | **LOC:** 2346 | **CtrlFlow:** 41.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **9** in-repo importer(s); it depends on **13**; blast radius 2.259; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Complexity Load (formerly Cognitive Load) (84.0%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 32.8125% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_build_markdown` **(Many-Argument Workhorses)** (Impact: 943.9)
  * `_mainframe_facts_lines` **(Many-Argument Workhorses)** (Impact: 508.6)
    * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These ar...
  * `_executive_summary_lines` **(Stateful Encapsulated Methods)** (Impact: 58.0)
  * `generate_artifacts` **(Many-Argument Workhorses)** (Impact: 42.2)
  * `_idiom_wrapper_lines` **(Stateful Encapsulated Methods)** (Impact: 36.6)
    * *Intent:* """Project-local idiom wrappers (#3313 step 3) -- ABSENT unless one resolved. A literal rule counts ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 586 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1891
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 702`, `structural_boundaries: 132`, `args: 53`, `func_start: 23`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 78`, `state_mutation: 719`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 2`, `import: 11`
* *Defense:* `safety: 17`, `doc: 24`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 2.259
  * `Choke Point (Betweenness):` 2.1e-05 | `Ripple Effect (Closeness):` 0.02227
  * `Imports (Out-Degree: 2):` collections, gitgalaxy.core.call_resolver, gitgalaxy.standards, heapq, hops, json, logging, pathlib...
  * `Imported By (In-Degree: 9):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 2883.92 | **LOC:** 3905 | **CtrlFlow:** 25.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **16** in-repo importer(s); it depends on **76**; blast radius 4.834; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.2%), Complexity Load (formerly Cognitive Load) (83.1%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 18.0851% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 269.1)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 142.6)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `_process_file_worker` **(Many-Argument Workhorses)** (Impact: 141.1)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `_calculate_risk_exposures` **(Many-Argument Workhorses)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
  * `main` **(I/O & Config Routines)** (Impact: 102.9)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 481 instances
* *Concurrency (weighted view):* 13
* *State Mutation (weighted view):* 1652
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 603`, `structural_boundaries: 272`, `args: 44`, `func_start: 32`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 121`, `high_risk_execution: 2`, `state_mutation: 690`, `dead_code: 2`
* *Architecture:* `io: 13`, `api: 8`, `concurrency: 3`, `import: 70`
* *Defense:* `safety: 53`, `doc: 26`, `test: 2`, `immutability_locks: 9`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.834
  * `Choke Point (Betweenness):` 0.00264 | `Ripple Effect (Closeness):` 0.02438
  * `Imports (Out-Degree: 37):` , B, DAG, a, argparse, b, base64, collections...
  * `Imported By (In-Degree: 16):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/mainframe_boundary.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2269.72 | **LOC:** 2104 | **CtrlFlow:** 42.8% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **31** in-repo importer(s); it depends on **23**; blast radius 15.087; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (86.4%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 11.9048% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_cobol_calls` **(Many-Argument Workhorses)** (Impact: 143.3)
    * *Intent:* """Every COBOL invocation site: `CALL`, and CICS `LINK`/`XCTL PROGRAM(...)`. `cics_only` (#3495) rea...
  * `_cobol_records` **(Stateful Encapsulated Methods)** (Impact: 86.6)
    * *Intent:* """The DATA DIVISION item tree and FD record layouts of one COBOL file (#3246). Each entry is a flat...
  * `_pli_item_attributes` **(Compute Cores)** (Impact: 72.8)
    * *Intent:* """The record_data fields of one item from its attribute tokens, or None when the declaration is not...
  * `_jcl_boundary` **(Compute Cores)** (Impact: 49.0)
    * *Intent:* """JCL `EXEC PGM=` steps and the `DD` statements that bind a ddname to a dataset. #3345: alongside t...
  * `_pli_items` **(Compute Cores)** (Impact: 39.2)
    * *Intent:* """Split one DECLARE body into (offset, level, name, dims, attribute tokens) items. A factored decla...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 366 instances
* *State Mutation (weighted view):* 1173
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 544`, `structural_boundaries: 236`, `args: 68`, `func_start: 62`
* *Risk/State:* `safety_bypasses: 80`, `state_mutation: 441`, `dead_code: 2`, `duplicate_logic: 11`
* *Architecture:* `api: 1`, `import: 23`
* *Defense:* `safety: 3`, `doc: 49`, `immutability_locks: 3`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 15.087
  * `Choke Point (Betweenness):` 0.007749 | `Ripple Effect (Closeness):` 0.088325
  * `Imports (Out-Degree: 19):` bisect, gitgalaxy.core.bms_screen_fields, gitgalaxy.core.call_using, gitgalaxy.core.cics_resources, gitgalaxy.core.cics_tasks, gitgalaxy.core.data_moves, gitgalaxy.core.db2_declare_table, gitgalaxy.core.db2_sql_statements...
  * `Imported By (In-Degree: 31):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 2265.76 | **LOC:** 5471 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
- **Magnitude:** 2144.46 | **LOC:** 2322 | **CtrlFlow:** 26.8% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **13** in-repo importer(s); it depends on **12**; blast radius 4.265; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.4%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (63.7%)
- **Documentation Coverage:** 29.661% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` **(Many-Argument Workhorses)** (Impact: 262.7)
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
* *Structure:* `branch: 371`, `structural_boundaries: 146`, `args: 48`, `func_start: 37`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 44`, `state_mutation: 466`, `dead_code: 1`, `planned_debt: 1`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 10`, `concurrency: 2`, `import: 12`
* *Defense:* `safety: 30`, `doc: 28`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.265
  * `Choke Point (Betweenness):` 9.3e-05 | `Ripple Effect (Closeness):` 0.025338
  * `Imports (Out-Degree: 2):` a, collections.abc, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math...
  * `Imported By (In-Degree: 13):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 1944.14 | **LOC:** 1967 | **CtrlFlow:** 35.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **32** in-repo importer(s); it depends on **4**; blast radius 7.349; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (45.8%)
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
* *Amplified Cascading Flux:* 282 instances
* *State Mutation (weighted view):* 895
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 333`, `structural_boundaries: 172`, `args: 47`, `func_start: 44`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 331`, `fragile_debt: 6`, `duplicate_logic: 2`
* *Architecture:* `api: 11`, `import: 4`
* *Defense:* `safety: 4`, `doc: 41`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 7.349
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.052074
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 32):` (Excluded from Brief to save tokens)

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

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1338.7 | **LOC:** 1217 | **CtrlFlow:** 41.3% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **11** in-repo importer(s); it depends on **36**; blast radius 7.269; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (46.4%)
- **Documentation Coverage:** 18.5714% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_target` **(Many-Argument Workhorses)** (Impact: 126.2)
  * `_resolve_by_name` **(Many-Argument Workhorses)** (Impact: 112.5)
  * `_resolve_path_mirror` **(Many-Argument Workhorses)** (Impact: 63.3)
  * `_resolve_from_importer_dir` **(Many-Argument Workhorses)** (Impact: 55.2)
  * `_resolve_package_module` **(Many-Argument Workhorses)** (Impact: 51.4)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 178 instances
* *State Mutation (weighted view):* 557
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 279`, `structural_boundaries: 142`, `args: 32`, `func_start: 31`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 37`, `state_mutation: 201`, `dead_code: 2`
* *Architecture:* `io: 1`, `api: 5`, `import: 12`
* *Defense:* `safety: 10`, `doc: 31`, `immutability_locks: 8`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 7.269
  * `Choke Point (Betweenness):` 0.004598 | `Ripple Effect (Closeness):` 0.076069
  * `Imports (Out-Degree: 4):` , A, Text.Pandoc.Generic, X, already, and, collections, covers...
  * `Imported By (In-Degree: 11):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/test_galaxy_ir.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1252.1 | **LOC:** 2315 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **9**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_container` **(Stateful Encapsulated Methods)** (Impact: 14.0)
  * `test_remote_programs_calls_and_function_shipping` **(Defensive Guards)** (Impact: 12.0)
  * `test_a_pre_3356_db_loads_with_no_csd_resources` **(Defensive Guards)** (Impact: 9.2)
  * `test_async_tasks_joins_children_containers_fetches_and_retrieves` **(Defensive Guards)** (Impact: 9.2)
  * `test_cics_file_lineage_joins_program_file_ops_to_the_csd_dataset` **(Defensive Guards)** (Impact: 8.8)
    * *Intent:* """Program -> EXEC CICS FILE -> #3356's cics_file_datasets() row (DSNAME, JCL bindings, batch progra...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` com.ibm.cics.server.Program, gitgalaxy.cobol_refractor_controller, gitgalaxy.tools.cobol_to_cobol.galaxy_ir, os, pathlib, pytest, shutil, sqlite3...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1165.92 | **LOC:** 3054 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **33**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_recorder_exception_survivability` **(Many-Argument Workhorses)** (Impact: 16.3)
    * *Intent:* # ============================================================================== # TEST 23: RECORDER...
  * `test_phase_10_manifest_paths_includes_all_supported_ecosystems` **(Many-Argument Workhorses)** (Impact: 13.4)
    * *Intent:* # ============================================================================== # TEST 33: MANIFEST...
  * `test_cicd_policy_enforcement_gates` **(Many-Argument Workhorses)** (Impact: 12.4)
    * *Intent:* # ============================================================================== # TEST 2: THE CI/CD...
  * `test_delta_scanning_fallbacks` **(Many-Argument Workhorses)** (Impact: 12.0)
    * *Intent:* # ============================================================================== # TEST 24: DELTA SC...
  * `test_sarif_ignored_paths_sanitization` **(Compute Cores)** (Impact: 11.6)
    * *Intent:* # ============================================================================== # TEST 19: SARIF IG...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` , B, Q, base64, concurrent.futures, failure, gitgalaxy.core.aperture, gitgalaxy.core.detector...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/audit_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 1068.96 | **LOC:** 1105 | **CtrlFlow:** 24.8% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **7** in-repo importer(s); it depends on **8**; blast radius 1.762; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (96.8%), Complexity Load (formerly Cognitive Load) (84.9%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 25.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `generate_report` **(Many-Argument Workhorses)** (Impact: 358.4)
  * `_mainframe_facts_block` **(Many-Argument Workhorses)** (Impact: 175.8)
    * *Intent:* """The Named System Facts for one file (#3200/#3201/#3246/#3250/#3344/#3356), or {} if none. The for...
  * `descale` **(Defensive Guards)** (Impact: 14.1)
    * *Intent:* """Dynamically scales integers back to floats using a fixed-string check."""
  * `_completeness_block` **(Stateful Encapsulated Methods)** (Impact: 8.3)
    * *Intent:* """#3506: GalaxyIR.completeness() in the audit's labelled style -- the score, each channel's resolve...
  * `format_label` **(Generic / Templated Code)** (Impact: 7.6)
    * *Intent:* """Translates raw dictionary keys into descriptive human-readable labels."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 148 instances
* *State Mutation (weighted view):* 468
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 213`, `structural_boundaries: 35`, `args: 14`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 17`, `state_mutation: 172`
* *Architecture:* `io: 3`, `api: 7`, `import: 8`
* *Defense:* `safety: 12`, `doc: 7`, `sync_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 1.762
  * `Choke Point (Betweenness):` 7e-06 | `Ripple Effect (Closeness):` 0.020105
  * `Imports (Out-Degree: 1):` argparse, gitgalaxy.standards, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 7):` (Excluded from Brief to save tokens)

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

### `gitgalaxy/recorders/record_keeper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1009.92 | **LOC:** 3808 | **CtrlFlow:** 20.0% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **38** in-repo importer(s); it depends on **20**; blast radius 10.786; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (91.5%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (83.4%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 21.4286% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_classify_file_archetype` **(Many-Argument Workhorses)** (Impact: 52.6)
    * *Intent:* """Nearest-centroid file archetype from the assembled metrics, mirroring the offline apply_file_clus...
  * `_prep_file_brain` **(Stateful Encapsulated Methods)** (Impact: 36.2)
    * *Intent:* """#ENGINE-PARITY: cache the self-describing FILE archetype brain contract. The engine builds the fi...
  * `record_mission` **(Many-Argument Workhorses)** (Impact: 28.0)
  * `_insert_per_file_child` **(Many-Argument Workhorses)** (Impact: 20.8)
  * `_file_feature_kind` **(Stateful Encapsulated Methods)** (Impact: 13.4)
    * *Intent:* """Which value source feeds this FEATURE_NAME, or None if the engine has none."""
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
* *Ai Guardrails:* 1 instances
* *Amplified Cascading Flux:* 237 instances
* *State Mutation (weighted view):* 765
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 397`, `structural_boundaries: 67`, `args: 33`, `func_start: 12`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 32`, `state_mutation: 291`, `dead_code: 4`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 9`
* *Defense:* `safety: 30`, `doc: 58`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 10.786
  * `Choke Point (Betweenness):` 0.000162 | `Ripple Effect (Closeness):` 0.05709
  * `Imports (Out-Degree: 3):` already, gitgalaxy.core.call_resolver, gitgalaxy.standards.analysis_lens, graph, json, logging, machine, math...
  * `Imported By (In-Degree: 38):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/call_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 992.28 | **LOC:** 958 | **CtrlFlow:** 40.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **10** in-repo importer(s); it depends on **16**; blast radius 8.396; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.9%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (53.1%)
- **Documentation Coverage:** 25.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_one` **(Many-Argument Workhorses)** (Impact: 120.5)
  * `resolve_calls` **(Many-Argument Workhorses)** (Impact: 90.5)
  * `_visible_receiver` **(Stateful Encapsulated Methods)** (Impact: 37.2)
    * *Intent:* """An untyped receiver (`x.save()`): confident only when exactly ONE visible class defines the metho...
  * `_constructor_of` **(Stateful Encapsulated Methods)** (Impact: 31.2)
    * *Intent:* """The constructor method of class definition `cls`, if the scan extracted one. One in the class's o...
  * `_index` **(Stateful Encapsulated Methods)** (Impact: 24.3)
    * *Intent:* """(link group, name key) -> every definition of that name, in scan order. Functions and classes sha...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 119 instances
* *State Mutation (weighted view):* 386
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 255`, `structural_boundaries: 138`, `args: 42`, `func_start: 38`, `class_start: 4`
* *Risk/State:* `safety_bypasses: 33`, `high_risk_execution: 2`, `state_mutation: 148`, `dead_code: 1`
* *Architecture:* `io: 1`, `api: 12`, `import: 3`
* *Defense:* `safety: 4`, `doc: 24`, `immutability_locks: 15`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.396
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.048377
  * `Imports (Out-Degree: 0):` .param_functions, NetworkRiskSensor.dependency_edges, already, and, barrels, collections, fastapi, graph...
  * `Imported By (In-Degree: 10):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/graph_engine.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_5` (Drift: 0.0 IQR)
- **Magnitude:** 943.38 | **LOC:** 783 | **CtrlFlow:** 30.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** changing it is visible to **5** in-repo importer(s); it depends on **13**; blast radius 4.268; role: Pure Producer (Foundation)
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.268
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.057242
  * `Imports (Out-Degree: 0):` as, built, chain, collections, collections.abc, direction, graph, math...
  * `Imported By (In-Degree: 5):` (Excluded from Brief to save tokens)

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
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 561.32 | **LOC:** 637 | **CtrlFlow:** 26.7% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **10**; blast radius 1.36; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (73.8%)
- **Documentation Coverage:** 13.6364% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `audit` **(Many-Argument Workhorses)** (Impact: 168.5)
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
* *Amplified Cascading Flux:* 104 instances
* *State Mutation (weighted view):* 337
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 99`, `structural_boundaries: 44`, `args: 10`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 29`, `state_mutation: 129`
* *Architecture:* `io: 2`, `api: 3`, `import: 5`
* *Defense:* `safety: 8`, `doc: 8`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.36
  * `Choke Point (Betweenness):` 2e-06 | `Ripple Effect (Closeness):` 0.015623
  * `Imports (Out-Degree: 1):` .app, at, gitgalaxy.core.spatial_correlation, logging, manifest, os, plus, statements...
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/data_moves.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 547.92 | **LOC:** 406 | **CtrlFlow:** 52.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **4**; blast radius 1.541; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.5%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (71.1%)
- **Documentation Coverage:** 23.5294% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_rows_of` **(Compute Cores)** (Impact: 141.2)
    * *Intent:* """(source operand or None, target operand, corresponding) pairs of one statement."""
  * `operand` **(Compute Cores)** (Impact: 51.0)
    * *Intent:* """(text, kind, refmod) of the operand at the cursor, advancing past it, or None (cursor unmoved) wh...
  * `data_moves` **(Defensive Guards)** (Impact: 34.4)
    * *Intent:* """Every source -> target pair of the data-moving statements of one COBOL file."""
  * `expression_items` **(Compute Cores)** (Impact: 15.1)
    * *Intent:* """Every data name of an arithmetic expression (FUNCTION names skipped, a function's arguments kept)...
  * `_skip_parens` **(Stateful Encapsulated Methods)** (Impact: 12.2)
    * *Intent:* """Skip one balanced ( ... ) group; True when it is a reference modifier."""
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 78 instances
* *State Mutation (weighted view):* 249
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 163`, `structural_boundaries: 59`, `args: 10`, `func_start: 10`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 14`, `state_mutation: 93`
* *Architecture:* `api: 7`, `import: 4`
* *Defense:* `safety: 2`, `doc: 6`, `immutability_locks: 16`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 1.541
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.067546
  * `Imports (Out-Degree: 0):` bisect, gitgalaxy.core.db2_declare_table, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/test_cobol_answer_key.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 499.24 | **LOC:** 1482 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **12**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_key_integrity` **(Defensive Guards)** (Impact: 21.2)
  * `test_draft_readers_never_import_the_parsers_they_grade` **(Type Conversions)** (Impact: 8.4)
    * *Intent:* """Independence: the key is only evidence if its reader shares no code with the engine or the forge....
  * `test_data_items_reads_the_record_layout_independently` **(Defensive Guards)** (Impact: 7.1)
    * *Intent:* """#3246: the key's own DATA DIVISION reader -- nesting, PIC, COMP-3, OCCURS, REDEFINES and a group ...
  * `test_bms_reader_reads_the_raw_file_independently` **(Defensive Guards)** (Impact: 6.6)
    * *Intent:* # ============================================================================== # #3347: BMS screen...
  * `test_job_submission_reader_is_independent` **(Generic / Templated Code)** (Impact: 6.3)
    * *Intent:* """#3448: the key's own join -- a WRITEQ TD to an extrapartition queue is a submission only with a J...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` cobol_answer_key, com.ibm.cics.server.KSDS, cross_verify, gitgalaxy.tools.cobol_to_cobol.galaxy_ir, json, mainframe_corpus, pathlib, pytest...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/cics_resources.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_3` (Drift: 0.0 IQR)
- **Magnitude:** 493.96 | **LOC:** 424 | **CtrlFlow:** 39.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **5** in-repo importer(s); it depends on **3**; blast radius 4.997; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.0%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (65.8%)
- **Documentation Coverage:** 34.6154% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `extract_cics_resources` **(Many-Argument Workhorses)** (Impact: 111.8)
  * `_row` **(Many-Argument Workhorses)** (Impact: 61.0)
  * `_two_word_spec` **(Stateful Encapsulated Methods)** (Impact: 32.9)
  * `cobol_move_literals` **(Type Conversions)** (Impact: 32.8)
    * *Intent:* """Data-name -> every distinct literal it can be MOVEd (same file): `MOVE 'LIT' TO name`, and (#3578...
  * `_resolver` **(Generic / Templated Code)** (Impact: 20.3)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 49 instances
* *State Mutation (weighted view):* 169
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 115`, `structural_boundaries: 44`, `args: 9`, `func_start: 9`
* *Risk/State:* `safety_bypasses: 10`, `state_mutation: 71`
* *Architecture:* `io: 1`, `api: 4`, `import: 3`
* *Defense:* `doc: 6`, `immutability_locks: 5`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.997
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.069292
  * `Imports (Out-Degree: 0):` bisect, re, typing
  * `Imported By (In-Degree: 5):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/file_control.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 492.1 | **LOC:** 310 | **CtrlFlow:** 59.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **4**; blast radius 1.637; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (69.3%)
- **Documentation Coverage:** 19.2308% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_define_row` **(Stateful Encapsulated Methods)** (Impact: 80.0)
  * `_one_select` **(Compute Cores)** (Impact: 72.6)
  * `jcl_vsam_defines` **(Compute Cores)** (Impact: 38.8)
    * *Intent:* """Every IDCAMS DEFINE CLUSTER / AIX / PATH in a JCL file's in-stream data."""
  * `_select_rows` **(Stateful Encapsulated Methods)** (Impact: 23.3)
  * `cobol_file_control` **(Generic / Templated Code)** (Impact: 13.3)
    * *Intent:* """Every FILE-CONTROL SELECT of one COBOL file with its organisation, access mode and keys (see the ...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 66 instances
* *State Mutation (weighted view):* 210
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 139`, `structural_boundaries: 35`, `args: 11`, `func_start: 10`
* *Risk/State:* `safety_bypasses: 16`, `state_mutation: 78`
* *Architecture:* `api: 3`, `import: 4`
* *Defense:* `doc: 5`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 1.637
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.067461
  * `Imports (Out-Degree: 0):` bisect, gitgalaxy.core.db2_declare_table, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

## 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 12.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/core/mainframe_boundary.py` -> Churn: **86.44%** | Cog Load: 52.0524% | Debt: 42.6289%
- `gitgalaxy/galaxyscope.py` -> Churn: **78.14%** | Cog Load: 83.139% | Debt: 0.0%
- `gitgalaxy/recorders/audit_recorder.py` -> Churn: **74.01%** | Cog Load: 84.8511% | Debt: 0.0%
- `gitgalaxy/recorders/llm_recorder.py` -> Churn: **69.19%** | Cog Load: 83.9816% | Debt: 9.3995%
- `gitgalaxy/cobol_to_java_controller.py` -> Churn: **66.44%** | Cog Load: 76.96% | Debt: 9.7637%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 9782.66
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3735.26
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2883.92
- `gitgalaxy/core/mainframe_boundary.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2269.72
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2144.46

## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 0.775** (Bridge: 0.0077 * Flux: 100.0%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.51** (Bridge: 0.0051 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.46** (Bridge: 0.0046 * Flux: 100.0%)
- `gitgalaxy/core/invocation_resolver.py` -> **Severity: 0.419** (Bridge: 0.0042 * Flux: 100.0%)
- `gitgalaxy/galaxyscope.py` -> **Severity: 0.264** (Bridge: 0.0026 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 22.504** (Embedded: 0.2497 * Error Risk: 90.1421%)
- `gitgalaxy/standards/language_standards/languages/json.py` -> **Severity: 15.577** (Embedded: 0.2219 * Error Risk: 70.2063%)
- `gitgalaxy/core/detector.py` -> **Severity: 10.054** (Embedded: 0.1009 * Error Risk: 99.5983%)
- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 8.819** (Embedded: 0.0883 * Error Risk: 99.8517%)
- `tests/extraction/languages/_strict_harness.py` -> **Severity: 8.158** (Embedded: 0.0973 * Error Risk: 83.8311%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/core/detector.py` -> **Severity: 481.577** (Blast Radius: 23.229 * Doc Risk: 20.7317%)
- `tests/tools/tri_comparison_reconcile.py` -> **Severity: 285.76** (Blast Radius: 3.572 * Doc Risk: 80.0%)
- `tests/tools/mainframe_corpus.py` -> **Severity: 285.285** (Blast Radius: 4.531 * Doc Risk: 62.963%)
- `gitgalaxy/standards/config_resolver.py` -> **Severity: 273.464** (Blast Radius: 5.791 * Doc Risk: 47.2222%)
- `gitgalaxy/core/spatial_correlation.py` -> **Severity: 238.05** (Blast Radius: 9.522 * Doc Risk: 25.0%)

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
