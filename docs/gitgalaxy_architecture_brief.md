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
- **Scope:** 879 analyzed artifact(s), 180131 LOC.
- **Load-bearing artifact:** `gitgalaxy/core/detector.py` -- 85 in-repo importer(s) depend on it. Changes here propagate furthest.
- **Top orchestrator:** `gitgalaxy/galaxyscope.py` -- pulls in 65 dependencies, the widest assembly point in the scan.
- **Heaviest artifact:** `gitgalaxy/core/detector.py` at magnitude 10445.94 (structural weight, not risk).
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
| Total Artifacts | 2958 |
| Analyzed Artifacts (Scanned) | 879 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 2079 |
| Total LOC | 180131 |
| Volatility Index | 0.013 |
| % Scanned of codebase = | 29.7% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.7167 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.2112 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 0.6% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 3.1678 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 99 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 694 | 162465 | 79.0% |
| COBOL | 51 | 8709 | 5.8% |
| YAML | 45 | 3240 | 5.1% |
| MARKDOWN | 38 | 0 | 4.3% |
| PLAINTEXT | 13 | 0 | 1.5% |
| PLI | 10 | 1425 | 1.1% |
| BMS | 6 | 1322 | 0.7% |
| CSD | 5 | 1133 | 0.6% |
| JCL | 5 | 365 | 0.6% |
| SHELL | 4 | 201 | 0.5% |
| HLASM | 3 | 446 | 0.3% |
| JAVA | 2 | 505 | 0.2% |
| C | 1 | 159 | 0.1% |
| DOCKERFILE | 1 | 3 | 0.1% |
| JAVASCRIPT | 1 | 158 | 0.1% |

## 4.1 SOURCE ENCODINGS
All 879 parsed files are UTF-8.

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Hub-Coupled App`
> **Architectural Drift Z-Score:** `1.693`
> **Composition Archetype:** `Hub-Coupled App` (z +1.69; from the repo's file-archetype mix)
> **File Composition:** Large Core Modules (2) 37%, Data / Markup / Trivial 14%, Declarative / Non-Code 11%, Large Core Modules (3) 10%, Generic / Templated Code Files 7%
> **ℹ️ TYPICAL INTERPRETATION:** This repository falls within standard variance (Z-Score between -1.0 and 2.0), representing a typical implementation of this archetype.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 828 | 94.2% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 51 | 5.8% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 2079*

**Composition by Extension & Reason:**
- `.snap`: 635x Excluded (Unsupported Extension: '.snap'), 336x Unsupported Format (.snap)
- `.json`: 520x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.md`: 449x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 350 LOC)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `no_extension`: 16x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 2x Unsupported Format (.undeterminable)
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 601 LOC), 1x Excluded (Machine-Generated Source Code Signature: 349 LOC)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csv`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.jsonl`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Saturation: Line 1 exceeds 500 chars)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.xml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 85.2 | 4.3 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 100.0 | 7.4 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 97.1 | 0.6 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 4.4 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 54.9 | 1.0 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 18.8 | 0.1 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 7.5 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 25.3 | 0.1 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 2.2 | 0.1 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 91.0 | 2.3 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) _(coverage)_ | 0.0 | 100.0 | 1.6 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

> `Doc Surface (formerly Documentation Exposure)` is **documentation coverage, not a fragility driver**. It is reported for context beside program length, and is deliberately excluded from the ranked-file drivers in this brief: it measures the share of a file's unit weight a reader cannot recover from documentation, so on a codebase that documents little it sits near ceiling everywhere and describes the repo rather than distinguishing files within it.
> `Spec Alignment (formerly Specification Exposure)` was **not measured** on this scan and is therefore absent above rather than reported as 0 (which would assert full alignment). Enable it with `--spec-alignment` if this codebase uses the corresponding convention.

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 736 | 47 | 0 | `gitgalaxy/recorders/record_keeper.py` |
| cleanup | 24 | 10 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 1438 | 60 | 0 | `gitgalaxy/core/detector.py` |
| danger | 1230 | 59 | 0 | `gitgalaxy/core/detector.py` |
| concurrency | 29 | 10 | 0 | `gitgalaxy/core/detector.py` |
| connectivity | 272 | 58 | 0 | `gitgalaxy/core/detector.py` |
| io | 145 | 29 | 0 | `.claude/hooks/session-start.sh` |
| crypto | 3 | 3 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 35 | 5 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 50 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 416 | 37 | 0 | `gitgalaxy/core/detector.py` |
| events | 281 | 21 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 6 | 4 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 715 | 64 | 0 | `gitgalaxy/core/detector.py` |
| debt | 201 | 24 | 0 | `gitgalaxy/cobol_to_java_controller.py` |
| mutation | 14520 | 63 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 78 | 12 | 0 | `gitgalaxy/core/detector.py` |
| credential | 3 | 2 | 0 | `gitgalaxy/core/detector.py` |
| threat | 86 | 13 | 0 | `gitgalaxy/metrics/signal_processor.py` |
| ml_ai | 0 | 0 | 0 | - |
| ui | 1 | 1 | 0 | `gitgalaxy/recorders/llm_recorder.py` |

**Relations (repo medians):**
- `guard_balance_ratio` (guards / (danger + 1)): **0.0**
- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **0.0**

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `.claude/hooks/session-start.sh` (Hits: 45)
- `scripts/setup_java_toolchain.sh` (Hits: 17)
- `gitgalaxy/galaxyscope.py` (Hits: 12)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **detector.py** (`gitgalaxy/core/detector.py`) — 85 inbound connections
2. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 72 inbound connections
3. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 69 inbound connections
4. **source_text.py** (`gitgalaxy/core/source_text.py`) — 59 inbound connections
5. **_extraction_harness.py** (`tests/extraction/_extraction_harness.py`) — 51 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 65 outbound dependencies
2. **BANK.csd** (`tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/etc/install/base/installjcl/BANK.csd`) — 54 outbound dependencies
3. **Cbact04cService.java** (`tests/equivalence/carddemo-intcalc/port/service/Cbact04cService.java`) — 33 outbound dependencies
4. **test_import_contract_2875.py** (`tests/extraction/languages/test_import_contract_2875.py`) — 29 outbound dependencies
5. **mainframe_boundary.py** (`gitgalaxy/core/mainframe_boundary.py`) — 27 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1178.2** | LOC: 1339
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **944.0** | LOC: 1119
- `score` **(Many-Argument Workhorses)** (@ `tests/tools/cobol_answer_key.py`) -> Impact: **666.1** | LOC: 683
- `_mainframe_facts_lines` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **532.0** | LOC: 421
  * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These are the named mainframe relations/schemas the per-fi...
- `_calculate_block_metrics` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **503.2** | LOC: 546
- `splice` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **477.5** | LOC: 838
- `load_galaxy_ir` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py`) -> Impact: **448.2** | LOC: 720
  * *Intent:* """Loads the latest snapshot of one repo from a master DB, opened read-only."""
- `inspect` **(Many-Argument Workhorses)** (@ `gitgalaxy/standards/language_lens.py`) -> Impact: **391.8** | LOC: 455
- `generate_report` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/audit_recorder.py`) -> Impact: **364.6** | LOC: 572
- `execute_pipeline` **(Many-Argument Workhorses)** (@ `gitgalaxy/galaxyscope.py`) -> Impact: **269.0** | LOC: 669
  * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execution Flow): The method enforces a strict chronologi...

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `gitgalaxy/core` | 46 | 27525.62 | 51.33% | 5.6% |
| `tests/extraction/languages` | 130 | 15358.7 | 12.77% | 0.0% |
| `tests/core_engine` | 93 | 11315.68 | 13.37% | 0.0% |
| `tests/cobol_mainframe` | 85 | 8432.02 | 15.51% | 0.0% |
| `gitgalaxy/recorders` | 8 | 6867.7 | 46.79% | 4.01% |
| `gitgalaxy` | 6 | 4031.94 | 36.94% | 1.6% |
| `gitgalaxy/metrics` | 7 | 3547.06 | 45.97% | 14.14% |
| `tests/tools_recorders` | 42 | 2708.1 | 11.46% | 0.0% |
| `gitgalaxy/standards` | 10 | 2359.32 | 16.43% | 5.68% |
| `tests/security_auditing` | 18 | 2208.0 | 11.58% | 0.0% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `.github/ISSUE_TEMPLATE/parsing_discrepancy.yml` -> **97.0688%** Exposure
- `gitgalaxy/core/ebcdic_dbcs.py` -> **88.1655%** Exposure
- `gitgalaxy/core/rule_prefilter.py` -> **65.1355%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **49.5567%** Exposure
- `gitgalaxy/core/prism.py` -> **45.0559%** Exposure
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
- `gitgalaxy/core/ebcdic_dbcs.py` -> **0** Orphaned Functions | **2** Duplicates
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
- **Unknown Dependencies:** `4954` packages imported that bypass the Zero-Trust whitelist.

## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)
> Ranked by Structural Magnitude: the file's structural weight and centralization within the system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not the vector percentages, is the actionable part.

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 10445.94 | **LOC:** 10332 | **CtrlFlow:** 43.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **85** in-repo importer(s); it depends on **17**; blast radius 21.068; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (86.1%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 19.9275% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1178.2)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 503.2)
  * `splice` **(Many-Argument Workhorses)** (Impact: 477.5)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 254.5)
  * `_slice_by_indentation` **(Many-Argument Workhorses)** (Impact: 251.2)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 3 instances
* *Amplified Cascading Flux:* 1412 instances
* *Concurrency (weighted view):* 21
* *State Mutation (weighted view):* 4441
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 2210`, `structural_boundaries: 673`, `args: 126`, `func_start: 119`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 146`, `state_mutation: 1617`, `dead_code: 57`, `planned_debt: 2`, `fragile_debt: 25`, `duplicate_logic: 2`
* *Architecture:* `api: 21`, `concurrency: 6`, `import: 21`
* *Defense:* `safety: 49`, `doc: 115`, `immutability_locks: 44`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 21.068
  * `Choke Point (Betweenness):` 0.004369 | `Ripple Effect (Closeness):` 0.093502
  * `Imports (Out-Degree: 6):` bisect, collections, functools, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.rule_prefilter, gitgalaxy.core.spatial_correlation, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards...
  * `Imported By (In-Degree: 85):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 3852.68 | **LOC:** 2414 | **CtrlFlow:** 41.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **11** in-repo importer(s); it depends on **14**; blast radius 2.323; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Complexity Load (formerly Cognitive Load) (83.9%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 31.8182% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_build_markdown` **(Many-Argument Workhorses)** (Impact: 944.0)
  * `_mainframe_facts_lines` **(Many-Argument Workhorses)** (Impact: 532.0)
    * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These ar...
  * `_executive_summary_lines` **(Stateful Encapsulated Methods)** (Impact: 58.0)
  * `generate_artifacts` **(Many-Argument Workhorses)** (Impact: 42.2)
  * `_source_encoding_lines` **(Stateful Encapsulated Methods)** (Impact: 36.8)
    * *Intent:* """#3813: how the parsed files' bytes became text. One line when every file is UTF-8; otherwise a ta...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 604 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1947
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 734`, `structural_boundaries: 144`, `args: 56`, `func_start: 24`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 80`, `state_mutation: 739`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 2`, `import: 13`
* *Defense:* `safety: 17`, `doc: 25`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.323
  * `Choke Point (Betweenness):` 5.1e-05 | `Ripple Effect (Closeness):` 0.022273
  * `Imports (Out-Degree: 3):` collections, gitgalaxy.core.call_resolver, gitgalaxy.core.compiler_options, gitgalaxy.standards, heapq, hops, json, logging...
  * `Imported By (In-Degree: 11):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3026.16 | **LOC:** 4092 | **CtrlFlow:** 25.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **19** in-repo importer(s); it depends on **65**; blast radius 4.296; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.1%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (88.2%), Complexity Load (formerly Cognitive Load) (82.7%)
- **Documentation Coverage:** 22.5% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 269.0)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_process_file_worker` **(Many-Argument Workhorses)** (Impact: 151.5)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 142.6)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `main` **(I/O & Config Routines)** (Impact: 108.7)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
  * `_calculate_risk_exposures` **(Many-Argument Workhorses)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 495 instances
* *Concurrency (weighted view):* 17
* *State Mutation (weighted view):* 1705
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 637`, `structural_boundaries: 298`, `args: 53`, `func_start: 41`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 131`, `high_risk_execution: 2`, `state_mutation: 715`, `dead_code: 1`
* *Architecture:* `io: 12`, `api: 12`, `concurrency: 7`, `import: 76`
* *Defense:* `safety: 56`, `doc: 30`, `test: 2`, `immutability_locks: 9`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.296
  * `Choke Point (Betweenness):` 0.003014 | `Ripple Effect (Closeness):` 0.023511
  * `Imports (Out-Degree: 39):` argparse, collections, concurrent.futures, copy, datetime, functools, gitgalaxy.core.aperture, gitgalaxy.core.call_resolver...
  * `Imported By (In-Degree: 19):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/mainframe_boundary.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2555.42 | **LOC:** 2337 | **CtrlFlow:** 42.7% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **38** in-repo importer(s); it depends on **27**; blast radius 11.987; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (91.0%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 11.5385% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_cobol_records` **(Many-Argument Workhorses)** (Impact: 147.9)
    * *Intent:* """The DATA DIVISION item tree and FD record layouts of one COBOL file (#3246). #3911: `decimal_comm...
  * `_cobol_calls` **(Many-Argument Workhorses)** (Impact: 143.3)
    * *Intent:* """Every COBOL invocation site: `CALL`, and CICS `LINK`/`XCTL PROGRAM(...)`. `cics_only` (#3495) rea...
  * `_pli_item_attributes` **(Compute Cores)** (Impact: 72.8)
    * *Intent:* """The record_data fields of one item from its attribute tokens, or None when the declaration is not...
  * `_pli_records` **(Stateful Encapsulated Methods)** (Impact: 56.5)
    * *Intent:* """The DECLAREd data items of one PL/I file as a record tree (#3250). Same flat, source-ordered shap...
  * `_jcl_boundary` **(Compute Cores)** (Impact: 49.0)
    * *Intent:* """JCL `EXEC PGM=` steps and the `DD` statements that bind a ddname to a dataset. #3345: alongside t...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 411 instances
* *State Mutation (weighted view):* 1314
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 615`, `structural_boundaries: 255`, `args: 72`, `func_start: 64`
* *Risk/State:* `safety_bypasses: 85`, `state_mutation: 492`, `dead_code: 2`, `duplicate_logic: 11`
* *Architecture:* `api: 1`, `import: 27`
* *Defense:* `safety: 3`, `doc: 51`, `immutability_locks: 4`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 11.987
  * `Choke Point (Betweenness):` 0.007704 | `Ripple Effect (Closeness):` 0.096834
  * `Imports (Out-Degree: 23):` bisect, gitgalaxy.core.bms_screen_fields, gitgalaxy.core.call_using, gitgalaxy.core.cics_resources, gitgalaxy.core.cics_tasks, gitgalaxy.core.compiler_options, gitgalaxy.core.data_moves, gitgalaxy.core.db2_declare_table...
  * `Imported By (In-Degree: 38):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 2349.62 | **LOC:** 5614 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
- **Blast Radius:** changing it is visible to **13** in-repo importer(s); it depends on **11**; blast radius 2.893; role: Pure Producer (Foundation)
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 2.893
  * `Choke Point (Betweenness):` 8.4e-05 | `Ripple Effect (Closeness):` 0.022732
  * `Imports (Out-Degree: 3):` collections.abc, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math, os...
  * `Imported By (In-Degree: 13):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 1951.6 | **LOC:** 1977 | **CtrlFlow:** 35.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **40** in-repo importer(s); it depends on **4**; blast radius 6.577; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (45.9%)
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
* *Amplified Cascading Flux:* 283 instances
* *State Mutation (weighted view):* 898
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 335`, `structural_boundaries: 173`, `args: 47`, `func_start: 44`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 332`, `fragile_debt: 6`, `duplicate_logic: 2`
* *Architecture:* `api: 11`, `import: 4`
* *Defense:* `safety: 4`, `doc: 41`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 6.577
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.049094
  * `Imports (Out-Degree: 0):` gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 40):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1641.5 | **LOC:** 1555 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **10**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 391.8)
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
  * `Imports (Out-Degree: 0):` contextlib, gitgalaxy.core.source_text, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging, math, pathlib, re...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1499.12 | **LOC:** 1359 | **CtrlFlow:** 42.9% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **13** in-repo importer(s); it depends on **16**; blast radius 5.967; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (58.8%)
- **Documentation Coverage:** 18.9189% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_by_name` **(Many-Argument Workhorses)** (Impact: 137.6)
  * `_resolve_target` **(Many-Argument Workhorses)** (Impact: 132.7)
  * `build_dependency_graph` **(Many-Argument Workhorses)** (Impact: 68.8)
  * `_resolve_path_mirror` **(Many-Argument Workhorses)** (Impact: 63.3)
  * `_resolve_from_importer_dir` **(Many-Argument Workhorses)** (Impact: 55.2)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 194 instances
* *State Mutation (weighted view):* 607
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 322`, `structural_boundaries: 159`, `args: 34`, `func_start: 33`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 39`, `high_risk_execution: 1`, `state_mutation: 219`, `dead_code: 3`
* *Architecture:* `io: 5`, `api: 5`, `import: 14`
* *Defense:* `safety: 12`, `doc: 33`, `immutability_locks: 8`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 5.967
  * `Choke Point (Betweenness):` 0.00397 | `Ripple Effect (Closeness):` 0.072815
  * `Imports (Out-Degree: 5):` collections, gitgalaxy.core.graph_engine, gitgalaxy.core.invocation_resolver, gitgalaxy.core.path_proximity, gitgalaxy.core.unicode_paths, gitgalaxy.standards.analysis_lens, gitgalaxy.standards.language_standards, graph...
  * `Imported By (In-Degree: 13):` (Excluded from Brief to save tokens)

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

### `gitgalaxy/core/call_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 1216.0 | **LOC:** 1139 | **CtrlFlow:** 44.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **10** in-repo importer(s); it depends on **3**; blast radius 8.129; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.8%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (58.8%)
- **Documentation Coverage:** 23.5849% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `resolve_calls` **(Many-Argument Workhorses)** (Impact: 184.5)
  * `_resolve_one` **(Many-Argument Workhorses)** (Impact: 120.5)
  * `_visible_receiver` **(Stateful Encapsulated Methods)** (Impact: 37.2)
    * *Intent:* """An untyped receiver (`x.save()`): confident only when exactly ONE visible class defines the metho...
  * `_constructor_of` **(Stateful Encapsulated Methods)** (Impact: 31.2)
    * *Intent:* """The constructor method of class definition `cls`, if the scan extracted one. One in the class's o...
  * `_index` **(Type Conversions)** (Impact: 29.3)
    * *Intent:* """(link group, name key) -> every definition of that name, in scan order. Functions and classes sha...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 141 instances
* *State Mutation (weighted view):* 456
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 333`, `structural_boundaries: 150`, `args: 47`, `func_start: 41`, `class_start: 4`
* *Risk/State:* `safety_bypasses: 35`, `high_risk_execution: 2`, `state_mutation: 174`, `dead_code: 2`
* *Architecture:* `io: 1`, `api: 12`, `import: 3`
* *Defense:* `safety: 4`, `doc: 27`, `immutability_locks: 18`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.129
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.044525
  * `Imports (Out-Degree: 0):` collections, posixpath, typing
  * `Imported By (In-Degree: 10):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1165.92 | **LOC:** 3054 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **25**
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
  * `Imports (Out-Degree: 0):` B, Q, base64, concurrent.futures, failure, gitgalaxy.core.aperture, gitgalaxy.core.detector, gitgalaxy.core.spatial_correlation...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/audit_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 1105.24 | **LOC:** 1134 | **CtrlFlow:** 25.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **7** in-repo importer(s); it depends on **8**; blast radius 1.627; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (96.9%), Complexity Load (formerly Cognitive Load) (85.1%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 25.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `generate_report` **(Many-Argument Workhorses)** (Impact: 364.6)
  * `_mainframe_facts_block` **(Many-Argument Workhorses)** (Impact: 187.4)
    * *Intent:* """The Named System Facts for one file (#3200/#3201/#3246/#3250/#3344/#3356), or {} if none. The for...
  * `descale` **(Defensive Guards)** (Impact: 14.1)
    * *Intent:* """Dynamically scales integers back to floats using a fixed-string check."""
  * `_completeness_block` **(Stateful Encapsulated Methods)** (Impact: 8.3)
    * *Intent:* """#3506: GalaxyIR.completeness() in the audit's labelled style -- the score, each channel's resolve...
  * `format_label` **(Generic / Templated Code)** (Impact: 7.6)
    * *Intent:* """Translates raw dictionary keys into descriptive human-readable labels."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 154 instances
* *State Mutation (weighted view):* 486
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 221`, `structural_boundaries: 35`, `args: 14`, `func_start: 8`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 17`, `state_mutation: 178`
* *Architecture:* `io: 3`, `api: 7`, `import: 8`
* *Defense:* `safety: 12`, `doc: 7`, `sync_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 1.627
  * `Choke Point (Betweenness):` 1.3e-05 | `Ripple Effect (Closeness):` 0.019182
  * `Imports (Out-Degree: 1):` argparse, gitgalaxy.standards, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 7):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1062.58 | **LOC:** 750 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
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
  * `Imports (Out-Degree: 0):` gitgalaxy.core.source_text, json, logging, os, pathlib, re, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/record_keeper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1046.24 | **LOC:** 3979 | **CtrlFlow:** 20.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **40** in-repo importer(s); it depends on **9**; blast radius 8.948; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (91.1%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (90.1%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 17.6471% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_classify_file_archetype` **(Many-Argument Workhorses)** (Impact: 52.6)
    * *Intent:* """Nearest-centroid file archetype from the assembled metrics, mirroring the offline apply_file_clus...
  * `_prep_file_brain` **(Stateful Encapsulated Methods)** (Impact: 36.2)
    * *Intent:* """#ENGINE-PARITY: cache the self-describing FILE archetype brain contract. The engine builds the fi...
  * `record_mission` **(Many-Argument Workhorses)** (Impact: 28.1)
  * `_insert_per_file_child` **(Many-Argument Workhorses)** (Impact: 20.8)
  * `_file_feature_kind` **(Stateful Encapsulated Methods)** (Impact: 13.4)
    * *Intent:* """Which value source feeds this FEATURE_NAME, or None if the engine has none."""
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
* *Ai Guardrails:* 1 instances
* *Amplified Cascading Flux:* 241 instances
* *State Mutation (weighted view):* 779
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 418`, `structural_boundaries: 74`, `args: 38`, `func_start: 15`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 33`, `state_mutation: 297`, `dead_code: 5`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 4`, `import: 9`
* *Defense:* `safety: 30`, `doc: 63`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 8.948
  * `Choke Point (Betweenness):` 6.8e-05 | `Ripple Effect (Closeness):` 0.048348
  * `Imports (Out-Degree: 2):` gitgalaxy.core.call_resolver, gitgalaxy.standards.analysis_lens, json, logging, math, pathlib, sqlite3, statistics...
  * `Imported By (In-Degree: 40):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/graph_engine.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_5` (Drift: 0.0 IQR)
- **Magnitude:** 943.38 | **LOC:** 783 | **CtrlFlow:** 30.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** changing it is visible to **5** in-repo importer(s); it depends on **6**; blast radius 2.979; role: Pure Producer (Foundation)
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 2.979
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.054594
  * `Imports (Out-Degree: 0):` collections, collections.abc, math, operator, random, typing
  * `Imported By (In-Degree: 5):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 782.8 | **LOC:** 2140 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **9**
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
  * `Imports (Out-Degree: 0):` gitgalaxy.metrics.signal_processor, gitgalaxy.recorders, gitgalaxy.recorders.record_keeper, gitgalaxy.recorders.sarif_recorder, json, logging, os, pytest...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cobol_mainframe/refraction_excerpts/aws-mainframe-modernization-carddemo/app/cbl/COCRDLIC.cbl` (COBOL | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 718.66 | **LOC:** 1460 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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

### `gitgalaxy/core/data_moves.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 666.94 | **LOC:** 481 | **CtrlFlow:** 53.5% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **4** in-repo importer(s); it depends on **4**; blast radius 1.646; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (71.5%)
- **Documentation Coverage:** 21.0526% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_rows_of` **(Compute Cores)** (Impact: 141.2)
    * *Intent:* """(source operand or None, target operand, corresponding) pairs of one statement."""
  * `rounding_facts` **(Compute Cores)** (Impact: 54.8)
    * *Intent:* """#3825: every arithmetic statement that rounds or guards its size: {verb, line, targets: [{target,...
  * `operand` **(Compute Cores)** (Impact: 51.0)
    * *Intent:* """(text, kind, refmod) of the operand at the cursor, advancing past it, or None (cursor unmoved) wh...
  * `data_moves` **(Defensive Guards)** (Impact: 34.4)
    * *Intent:* """Every source -> target pair of the data-moving statements of one COBOL file."""
  * `expression_items` **(Compute Cores)** (Impact: 15.1)
    * *Intent:* """Every data name of an arithmetic expression (FUNCTION names skipped, a function's arguments kept)...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 98 instances
* *State Mutation (weighted view):* 311
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 199`, `structural_boundaries: 65`, `args: 11`, `func_start: 11`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 18`, `state_mutation: 115`
* *Architecture:* `api: 8`, `import: 4`
* *Defense:* `safety: 2`, `doc: 7`, `immutability_locks: 17`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 1.646
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.077191
  * `Imports (Out-Degree: 0):` bisect, gitgalaxy.core.db2_declare_table, re, typing
  * `Imported By (In-Degree: 4):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/src/base/cobol_src/BNK1CAC.cbl` (COBOL | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 615.62 | **LOC:** 1300 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **3**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `ED010` **(I/O & Config Routines)** (Impact: 53.7)
  * `CAD010` **(I/O & Config Routines)** (Impact: 25.0)
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

### `gitgalaxy/cobol_refractor_controller.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 589.48 | **LOC:** 670 | **CtrlFlow:** 25.7% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **25** in-repo importer(s); it depends on **23**; blast radius 4.044; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.9%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (61.6%)
- **Documentation Coverage:** 38.6364% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `process_payload` **(Many-Argument Workhorses)** (Impact: 98.0)
  * `main` **(I/O & Config Routines)** (Impact: 66.0)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `calibrate_ir_medium` **(Many-Argument Workhorses)** (Impact: 17.3)
    * *Intent:* # ============================================================================== # galaxyscope:ignor...
  * `engine_ir_dump` **(Type Conversions)** (Impact: 15.3)
    * *Intent:* """#3623: the IR dump of a program the COBOL passes do not read (PL/I), from the engine's facts: the...
  * `record_dead_code` **(Many-Argument Workhorses)** (Impact: 14.4)
**Contextual Mitigations & Amplifications:**
* *Sec Db Hooks:* 1 instances
* *Amplified Cascading Flux:* 98 instances
* *Api Near Db Sink:* 2 instances
* *State Mutation (weighted view):* 311
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 118`, `structural_boundaries: 78`, `args: 15`, `func_start: 13`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 9`, `high_risk_execution: 3`, `state_mutation: 115`
* *Architecture:* `io: 5`, `api: 10`, `import: 23`
* *Defense:* `safety: 3`, `doc: 8`, `cleanup: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.044
  * `Choke Point (Betweenness):` 0.000524 | `Ripple Effect (Closeness):` 0.028804
  * `Imports (Out-Degree: 14):` argparse, collections, datetime, gitgalaxy.core.source_text, gitgalaxy.core.unicode_paths, gitgalaxy.licensing, gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge, gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect...
  * `Imported By (In-Degree: 25):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/src/base/cobol_src/BANKDATA.cbl` (COBOL | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_11` (Drift: N/A IQR)
- **Magnitude:** 581.18 | **LOC:** 1464 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `DBR010` **(I/O & Config Routines)** (Impact: 31.7)
  * `PA010` **(I/O & Config Routines)** (Impact: 15.0)
  * `GOD010` **(I/O & Config Routines)** (Impact: 5.1)
  * `A010` **(I/O & Config Routines)** (Impact: 4.8)
  * `DA010` **(I/O & Config Routines)** (Impact: 3.9)
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
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **5**; blast radius 1.082; role: Transceiver (Middle-Tier)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.082
  * `Choke Point (Betweenness):` 1e-06 | `Ripple Effect (Closeness):` 0.016044
  * `Imports (Out-Degree: 1):` gitgalaxy.core.spatial_correlation, logging, os, statistics, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/test_cobol_answer_key.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 525.76 | **LOC:** 1562 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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

### `gitgalaxy/core/file_control.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 511.22 | **LOC:** 348 | **CtrlFlow:** 54.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **2** in-repo importer(s); it depends on **5**; blast radius 1.205; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (71.8%)
- **Documentation Coverage:** 19.2308% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_one_select` **(Compute Cores)** (Impact: 86.9)
  * `_define_row` **(Stateful Encapsulated Methods)** (Impact: 80.0)
  * `jcl_vsam_defines` **(Compute Cores)** (Impact: 38.9)
    * *Intent:* """Every IDCAMS DEFINE CLUSTER / AIX / PATH in a JCL file's in-stream data."""
  * `_select_rows` **(Stateful Encapsulated Methods)** (Impact: 23.3)
  * `cobol_file_control` **(Generic / Templated Code)** (Impact: 13.3)
    * *Intent:* """Every FILE-CONTROL SELECT of one COBOL file with its organisation, access mode and keys (see the ...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 67 instances
* *State Mutation (weighted view):* 214
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 147`, `structural_boundaries: 37`, `args: 11`, `func_start: 10`
* *Risk/State:* `safety_bypasses: 16`, `state_mutation: 80`
* *Architecture:* `api: 3`, `import: 5`
* *Defense:* `doc: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.205
  * `Choke Point (Betweenness):` 1e-06 | `Ripple Effect (Closeness):` 0.073467
  * `Imports (Out-Degree: 1):` bisect, gitgalaxy.core.db2_declare_table, gitgalaxy.standards.language_standards.identifiers, re, typing
  * `Imported By (In-Degree: 2):` (Excluded from Brief to save tokens)

## 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 12.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/core/mainframe_boundary.py` -> Churn: **91.0%** | Cog Load: 54.6884% | Debt: 36.4264%
- `gitgalaxy/galaxyscope.py` -> Churn: **88.18%** | Cog Load: 82.7068% | Debt: 0.0%
- `gitgalaxy/core/detector.py` -> Churn: **86.12%** | Cog Load: 66.7168% | Debt: 22.9446%
- `gitgalaxy/cobol_to_java_controller.py` -> Churn: **75.8%** | Cog Load: 78.0913% | Debt: 9.6134%
- `gitgalaxy/recorders/audit_recorder.py` -> Churn: **72.45%** | Cog Load: 85.1118% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 10445.94
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3852.68
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3026.16
- `gitgalaxy/core/mainframe_boundary.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2555.42
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2144.46

## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 0.77** (Bridge: 0.0077 * Flux: 100.0%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.437** (Bridge: 0.0044 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.397** (Bridge: 0.004 * Flux: 100.0%)
- `gitgalaxy/core/invocation_resolver.py` -> **Severity: 0.355** (Bridge: 0.0035 * Flux: 100.0%)
- `gitgalaxy/galaxyscope.py` -> **Severity: 0.301** (Bridge: 0.003 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 14.956** (Embedded: 0.1506 * Error Risk: 99.2943%)
- `gitgalaxy/core/source_text.py` -> **Severity: 12.434** (Embedded: 0.131 * Error Risk: 94.9407%)
- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 10.274** (Embedded: 0.1155 * Error Risk: 88.9176%)
- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 9.667** (Embedded: 0.0968 * Error Risk: 99.833%)
- `gitgalaxy/core/unicode_paths.py` -> **Severity: 9.544** (Embedded: 0.1104 * Error Risk: 86.4295%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 1513.76** (Blast Radius: 37.844 * Doc Risk: 40.0%)
- `gitgalaxy/core/ebcdic_codecs.py` -> **Severity: 772.616** (Blast Radius: 22.32 * Doc Risk: 34.6154%)
- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 661.541** (Blast Radius: 16.171 * Doc Risk: 40.9091%)
- `gitgalaxy/core/detector.py` -> **Severity: 419.833** (Blast Radius: 21.068 * Doc Risk: 19.9275%)
- `tests/tools/tri_comparison_reconcile.py` -> **Severity: 350.64** (Blast Radius: 4.383 * Doc Risk: 80.0%)

## 13. MAINFRAME SYSTEM FACTS (Named Relations & Record Layouts)
> **AI CONTEXT:** Named mainframe relations the structural signal counts flatten -- the call graph (`CALL`/CICS `LINK`·`XCTL`/JCL `EXEC PGM=`), the dataset boundary (`SELECT…ASSIGN` + `OPEN` modes, JCL `DD`→dataset), and record layouts (COBOL DATA DIVISION items, PL/I `DECLARE`d structures). BMS screen maps (every field's position, length and attributes, `screen_field_data`) are the 3270 UI surface. These are the schema of the system: use them to trace which program runs which, which dataset a job binds, and the shape of the records that flow between them. Extracted by the engine (`core/mainframe_boundary.py`) and carried in the master DB (`call_site_data`/`dataset_data`/`record_data`); resolution to files is redone per scan.

- **Coverage:** `76` files carry mainframe facts -- `77` call sites, `62` dataset bindings, `2755` record items.

- **DB2 schemas:** `15` columns of `EXEC SQL DECLARE ... TABLE` (inline or DCLGEN members), full shape in `sql_table_data`.

- **DB2 table access:** `22` embedded SQL statements touching `7` tables (SELECT/INSERT/UPDATE/DELETE, cursors, host variables) in `sql_statement_data`; the program x table read/write matrix is `GalaxyIR.sql_table_access()`.

- **CICS resources:** `249` CSD `DEFINE` records (FILE→DSNAME, TDQUEUE, DB2TRAN→DB2ENTRY→PLAN, MAPSET, LIBRARY, ...), full attributes in `csd_resource_data`.

- **CICS operations:** `77` EXEC CICS operations naming a resource (`2` CONTAINER, `19` FILE, `49` MAP, `3` QUEUE, `4` WEB); verb, direction, VALUE-resolved name and INTO/FROM record in `cics_resource_data`.

- **CICS task control:** `2` commands (`1` DELAY, `1` START); child transid (or its STRING-built pattern), channel, CHILD/REQID token and timing in `cics_task_data`.

### `tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/src/base/cobol_src/BANKDATA.cbl` (COBOL)
- **Calls:** `CALL CEEGMT`, `CALL CEEDATM`
- **Datasets:** `VSAM(OUTPUT)`
- **Record layouts (186 items):** `TITLE-ALPHABET (37)`, `HOST-ACCOUNT-ROW (33)`, `TIME-DATA (13)`, `WS-CURRENT-DATE-DATA (11)`, `CUSTOMER-RECORD-STRUCTURE⟵CUSTOMER-FILE (4)`, `HOST-CONTROL-ROW (4)`, `DISP-LOT (3)`, `CUSTOMER-VSAM-STATUS (3)`, `PARM-BUFFER (3)`, `FORENAMES (2)`, `STREET-NAME-TREES (2)`, `STREET-NAME-ROADS (2)` … (+61 more)
- **DB2 table access:** `CONTROL (insert/delete)`, `ACCOUNT (insert/delete)`
- **Keyed files:** `CUSTOMER-FILE INDEXED/RANDOM key CUSTOMER-KEY`
- **Data moves:** 402 (ADD 9, COMPUTE 23, DIVIDE 4, INITIALIZE 1, MOVE 333, STRING 28, UNSTRING 4); most-fed items `CUSTOMER-ADDRESS`, `CUSTOMER-NAME`, `HV-CONTROL-NAME`, `DISP-SQLCD`, `FORENAMES-PTR`, `WS-SQLCODE-DISPLAY`
- **Unit of work:** `3` commit / `0` rollback points; handlers none; `0/0` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/aws-mainframe-modernization-carddemo/app/cpy-bms/COCRDLI.CPY` (COBOL)
- **Record layouts (544 items):** `CCRDLIAI (272)`, `CCRDLIAO (272)`

### `tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/src/base/cobol_src/BNK1CAC.cbl` (COBOL)
- **Calls:** `RETURN TRANSID OMEN`, `RETURN TRANSID OCAC`, `LINK WS-ABEND-PGM`, `LINK CREACC`
- **COMMAREA passed:** `RETURN TRANSID OCAC ← WS-COMM-AREA LENGTH(32)`, `LINK ABNDPROC ← ABNDINFO-REC`, `LINK CREACC ← SUBPGM-PARMS`
- **Record layouts (98 items):** `SUBPGM-PARMS (16)`, `DATE-REFORMED (10)`, `WS-FAIL-INFO (8)`, `WS-ORIG-DATE-GRP (6)`, `WS-ORIG-DATE-GRP-X (6)`, `WS-TIME-DATA (6)`, `FLAGS (5)`, `WS-COMM-AREA (5)`, `DFHCOMMAREA (5)`, `COMM-DOB-SPLIT (4)`, `MORE-STRING-CONVS (4)`, `WS-CICS-WORK-AREA (3)` … (+17 more)
- **CICS operations:** `MAP BNK1CA (read/write)`
- **Compiler options:** `TRUNC(STD)`
- **Data moves:** 315 (ADD 2, COMPUTE 2, INITIALIZE 16, MOVE 191, STRING 102, SUBTRACT 2); most-fed items `ABND-TIME`, `ABND-FREEFORM`, `ABND-DATE`, `ABND-RESP2CODE`, `ABND-RESPCODE`, `ABND-TASKNO-KEY`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `7/8` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/aws-mainframe-modernization-carddemo/app/cbl/COCRDLIC.cbl` (COBOL)
- **Calls:** `XCTL LIT-MENUPGM`, `XCTL CCARD-NEXT-PROG`, `RETURN TRANSID LIT-THISTRANID`
- **COMMAREA passed:** `XCTL COMEN01C ← CARDDEMO-COMMAREA`, `XCTL CCARD-NEXT-PROG ← CARDDEMO-COMMAREA`, `RETURN TRANSID CCLI ← WS-COMMAREA LENGTH(LENGTH OF WS-COMMAREA)`
- **Record layouts (129 items):** `WS-MISC-STORAGE (79)`, `WS-THIS-PROGCOMMAREA (27)`, `WS-CONSTANTS (20)`, `DFHCOMMAREA (2)`, `WS-COMMAREA (1)`
- **CICS operations:** `MAP CCRDLIA (read/write)`, `FILE CARDDAT (browse/read)`
- **Data moves:** 237 (ADD 3, COMPUTE 1, INITIALIZE 8, MOVE 222, SUBTRACT 3); most-fed items `CDEMO-LAST-MAP`, `CDEMO-FROM-PROGRAM`, `CDEMO-LAST-MAPSET`, `WS-EDIT-SELECT`, `CDEMO-FROM-TRANID`, `CCARD-NEXT-MAP`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `4/8` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/cics-genapp/base/src/ssmap.bms` (BMS)
- **Screen maps:** `SSMAPC1 (12 named / 41 fields)`, `SSMAPP1 (15 named / 52 fields)`, `SSMAPP2 (13 named / 45 fields)`, `SSMAPP3 (12 named / 42 fields)`, `SSMAPP4 (22 named / 66 fields)`, `SSMAPP5 (10 named / 33 fields)`

### `tests/cobol_mainframe/refraction_excerpts/aws-mainframe-modernization-carddemo/app/cbl/CORPT00C.cbl` (COBOL)
- **Calls:** `RETURN TRANSID WS-TRANID`, `CALL CSUTLDTC`, `XCTL CDEMO-TO-PROGRAM`
- **COMMAREA passed:** `RETURN TRANSID CR00 ← CARDDEMO-COMMAREA`, `XCTL CDEMO-TO-PROGRAM ← CARDDEMO-COMMAREA`
- **Record layouts (81 items):** `WS-VARIABLES (40)`, `JOB-DATA (31)`, `CSUTLDTC-PARM (8)`, `DFHCOMMAREA (2)`
- **CICS operations:** `QUEUE JOBS (write)`, `MAP CORPT0A (read/write)`
- **Job submission:** `JOB TRNRPT00`, `EXEC PROC=TRANREPT`
- **Data moves:** 162 (ADD 2, COMPUTE 7, INITIALIZE 11, MOVE 134, STRING 8); most-fed items `WS-MESSAGE`, `WS-NUM-99`, `PARM-END-DATE-1`, `PARM-END-DATE-2`, `PARM-START-DATE-1`, `PARM-START-DATE-2`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `1/2` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/zopeneditor-sample/multiroot/sam/SAM1.cbl` (COBOL)
- **Calls:** `CALL SAM2`
- **Datasets:** `CUSTFILE(INPUT)`, `CUSTOUT(OUTPUT)`, `TRANFILE(INPUT)`, `CUSTRPT(OUTPUT)`
- **Record layouts (121 items):** `REPORT-TOTALS (17)`, `WS-FIELDS (15)`, `RPT-HEADER1 (14)`, `SYSTEM-DATE-AND-TIME (10)`, `RPT-STATS-DETAIL (9)`, `RPT-CRUNCH-RECORD (7)`, `MSG-TRAN-SCALE-1 (5)`, `MSG-TRAN-SCALE-2 (5)`, `RPT-STATS-CUST-DETAIL (5)`, `ERR-MSG-BAD-TRAN (4)`, `ERR-MSG-BAD-TRAN-2 (4)`, `RPT-TRAN-DETAIL1 (4)` … (+7 more)
- **Data moves:** 124 (ACCEPT 4, ADD 11, COMPUTE 12, INITIALIZE 1, MOVE 75, WRITE 21); most-fed items `REPORT-RECORD`, `RPT-NUM-TRAN-ERR`, `ERR-MSG-DATA2`, `RPT-NUM-CUST`, `RPT-NUM-TRAN-PROC`, `RPT-NUM-TRANS`

### `tests/cobol_mainframe/refraction_excerpts/cics-genapp/base/src/lgipdb01.cbl` (COBOL)
- **Calls:** `LINK LGSTSQ`
- **COMMAREA passed:** `LINK LGSTSQ ← ERROR-MSG LENGTH(LENGTH OF ERROR-MSG)`, `LINK LGSTSQ ← CA-ERROR-MSG LENGTH(LENGTH OF CA-ERROR-MSG)`
- **Record layouts (75 items):** `DB2-OUT-INTEGERS (28)`, `ERROR-MSG (13)`, `WS-HEADER (8)`, `TSAREA (7)`, `DB2-IN-INTEGERS (4)`, `CA-ERROR-MSG (3)`, `WS-COMMAREA-LENGTHS (3)`, `ABS-TIME (1)`, `TIME1 (1)`, `DATE1 (1)`, `MINUS-ONE (1)`, `END-POLICY-POS (1)` … (+4 more)
- **DB2 table access:** `POLICY (read)`, `COMMERCIAL (read)`, `ENDOWMENT (read)`, `HOUSE (read)`, `MOTOR (read)`
- **Data moves:** 146 (ADD 13, INITIALIZE 11, MOVE 122); most-fed items `WS-REQUIRED-CA-LEN`, `CA-POLICY-COMMON`, `CA-COMMERCIAL`, `DB2-B-CRIMEPERIL`, `DB2-B-CRIMEPREMIUM`, `DB2-B-FIREPERIL`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `0/0` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/aws-mainframe-modernization-carddemo/app/cpy-bms/CORPT00.CPY` (COBOL)
- **Record layouts (208 items):** `CORPT0AI (104)`, `CORPT0AO (104)`

### `tests/cobol_mainframe/refraction_excerpts/zopeneditor-sample/COBOL/SAM1.cbl` (COBOL)
- **Calls:** `CALL SAM2`
- **Datasets:** `CUSTFILE(INPUT)`, `CUSTOUT(OUTPUT)`, `TRANFILE(INPUT)`, `CUSTRPT(OUTPUT)`
- **Record layouts (104 items):** `REPORT-TOTALS (15)`, `WS-FIELDS (15)`, `RPT-HEADER1 (14)`, `SYSTEM-DATE-AND-TIME (10)`, `RPT-STATS-DETAIL (9)`, `MSG-TRAN-SCALE-1 (5)`, `MSG-TRAN-SCALE-2 (5)`, `ERR-MSG-BAD-TRAN (4)`, `ERR-MSG-BAD-TRAN-2 (4)`, `RPT-TRAN-DETAIL1 (4)`, `RPT-STATS-HDR2 (4)`, `RPT-STATS-HDR3 (4)` … (+4 more)
- **Data moves:** 93 (ACCEPT 4, ADD 7, COMPUTE 7, MOVE 60, WRITE 15); most-fed items `REPORT-RECORD`, `ERR-MSG-DATA2`, `RPT-NUM-TRAN-ERR`, `RPT-NUM-TRAN-PROC`, `RPT-NUM-TRANS`, `CSTOUT-CONTACT-REC`

### `tests/cobol_mainframe/refraction_excerpts/zopeneditor-sample/COBOL/SAM1LIB.cbl` (COBOL)
- **Calls:** `CALL SAM2`
- **Datasets:** `CUSTFILE(INPUT)`, `CUSTOUT(OUTPUT)`, `TRANFILE(INPUT)`, `CUSTRPT(OUTPUT)`
- **Record layouts (79 items):** `WS-FIELDS (15)`, `RPT-HEADER1 (14)`, `RPT-STATS-DETAIL (9)`, `MSG-TRAN-SCALE-1 (5)`, `MSG-TRAN-SCALE-2 (5)`, `ERR-MSG-BAD-TRAN (4)`, `ERR-MSG-BAD-TRAN-2 (4)`, `RPT-TRAN-DETAIL1 (4)`, `RPT-STATS-HDR2 (4)`, `RPT-STATS-HDR3 (4)`, `RPT-STATS-HDR4 (4)`, `WORK-VARIABLES (3)` … (+2 more)
- **Data moves:** 93 (ACCEPT 4, ADD 7, COMPUTE 7, MOVE 60, WRITE 15); most-fed items `REPORT-RECORD`, `ERR-MSG-DATA2`, `RPT-NUM-TRAN-ERR`, `RPT-NUM-TRAN-PROC`, `RPT-NUM-TRANS`, `CSTOUT-CONTACT-REC`

### `tests/cobol_mainframe/refraction_excerpts/dsf/src/R0010301.pli` (PLI)
- **Calls:** `XCTL R0010420`, `XCTL R0010426`, `XCTL R0010101`, `RETURN TRANSID TRANSKODE`, `LINK K410C002`
- **COMMAREA passed:** `XCTL R0010420 ← KOM_OMR`, `XCTL R0010426 ← KOM_OMR`, `XCTL R0010101 ← KOM_OMR`, `RETURN TRANSID TRANSKODE ← KOM_OMR`, `LINK K410C002 ← ACF2_KOM_PRG`
- **Record layouts (18 items):** `W01_IDENT_DEF (3)`, `COMMAREA_PEKER (1)`, `IDENT_PEKER (1)`, `BMSMAPBR (1)`, `IDENT_BIT (1)`, `W01_CICSINFO (1)`, `W01_CICS_NAVN (1)`, `W01_PSB_NAVN (1)`, `W01_BRUKER_ID (1)`, `W01_CICSINDEX (1)`, `W01_TERMINAL (1)`, `W01_ROLLE (1)` … (+4 more)
- **CICS operations:** `MAP S001013 (read/write)`, `MAP S001015 (write)`, `MAP S001014 (write)`, `MAP S001I04 (write)`, `MAP S00101E (write)`, `MAP S001I01 (write)`, `MAP S001481 (write)`, `MAP S001181 (write)`, `MAP S001230 (write)`, `MAP S001151 (write)`, `MAP S0010R (write)`, `MAP S001012 (write)`
- **Data moves:** 137 (ASSIGN 137); most-fed items `KOM_OMR.PCB_UIB_PEKER`, `S001013O.CICS_INFOO`, `S001013O.FUNKSJONSKODEO`, `ACF2_KOM_PRG.I_FUNKSJON`, `ATK_KOM_PTR`, `DIV_PARAM_OMR.ATK_ROLLE`
- **Unit of work:** `0` commit / `0` rollback points; handlers `ERROR->FEILBEH`; `0/0` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/aws-mainframe-modernization-carddemo/app/cbl/CBACT01C.cbl` (COBOL)
- **Calls:** `CALL COBDATFT`, `CALL CEE3ABD`
- **Datasets:** `ACCTFILE(INPUT)`, `OUTFILE(OUTPUT)`, `ARRYFILE(OUTPUT)`, `VBRCFILE(OUTPUT)`
- **Record layouts (66 items):** `OUT-ACCT-REC⟵OUT-FILE (12)`, `ARR-ARRAY-REC⟵ARRY-FILE (6)`, `WS-ACCT-REISSUE-DATE (6)`, `VBRC-REC2 (5)`, `FD-ACCTFILE-REC⟵ACCTFILE-FILE (3)`, `ACCTFILE-STATUS (3)`, `OUTFILE-STATUS (3)`, `ARRYFILE-STATUS (3)`, `VBRCFILE-STATUS (3)`, `IO-STATUS (3)`, `TWO-BYTES-ALPHA (3)`, `IO-STATUS-04 (3)` … (+9 more)
- **Keyed files:** `ACCTFILE-FILE INDEXED/SEQUENTIAL key FD-ACCT-ID`
- **Data moves:** 74 (ADD 4, INITIALIZE 2, MOVE 66, READ 1, SUBTRACT 1); most-fed items `IO-STATUS`, `ARR-ACCT-CURR-BAL`, `IO-STATUS-04`, `VBR-REC`, `APPL-RESULT`, `ARR-ACCT-ID`

### `tests/cobol_mainframe/refraction_excerpts/cics-genapp/base/src/lgtestp1.cbl` (COBOL)
- **Calls:** `LINK LGIPOL01`, `LINK LGAPOL01`, `LINK LGDPOL01`, `LINK LGUPOL01`, `RETURN TRANSID SSP1`
- **COMMAREA passed:** `LINK LGIPOL01 ← COMM-AREA LENGTH(32500)`, `LINK LGAPOL01 ← COMM-AREA LENGTH(32500)`, `LINK LGDPOL01 ← COMM-AREA LENGTH(32500)`, `LINK LGUPOL01 ← COMM-AREA LENGTH(32500)`, `RETURN TRANSID SSP1 ← COMM-AREA`
- **Record layouts (2 items):** `MSGEND (1)`, `COMM-AREA (1)`
- **CICS operations:** `MAP SSMAPP1 (read/write)`
- **Data moves:** 101 (INITIALIZE 7, MOVE 94); most-fed items `CA-CUSTOMER-NUM`, `CA-POLICY-NUM`, `CA-EXPIRY-DATE`, `CA-ISSUE-DATE`, `CA-M-ACCIDENTS`, `CA-M-CC`
- **Unit of work:** `0` commit / `2` rollback points; handlers `MAPFAIL->ENDIT`; `0/0` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/zecs/Source/ECS001.cbl` (COBOL)
- **Record layouts (34 items):** `CICS-MSG (6)`, `CICS-MSG2 (6)`, `INPUT-PARMS (3)`, `TERM-DATA (2)`, `URIMAP-NAME (1)`, `SESSION-TOKEN (1)`, `ECS-KEY (1)`, `ECS-KEY-LEN (1)`, `TERM-DATA-LEN (1)`, `BODY-DATA (1)`, `BODY-DATA-LEN (1)`, `ECS-DATA (1)` … (+9 more)
- **CICS operations:** `WEB ECS001 (open)`, `WEB PATH-NAME? (converse)`, `WEB ? (close)`
- **Data moves:** 61 (ADD 3, MOVE 51, STRING 2, SUBTRACT 1, UNSTRING 4); most-fed items `TERM-LINES`, `CICS-MSG-RESP`, `CICS-MSG-RESP2`, `BODY-DATA`, `CICS-MSG-CODE`, `CICS-MSG-STATUS`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `5/7` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/zopeneditor-sample/PLI/PSAM1.pli` (PLI)
- **Calls:** `CALL PSAM2`
- **Record layouts (61 items):** `SYSTEM_DATE_AND_TIME (10)`, `TRAN_RECORD (8)`, `HDR2 (3)`, `HDR3 (3)`, `DUMP_FINDER (1)`, `TRAN_COMMENT (1)`, `TRAN_RECORD_ALL (1)`, `TRANFILE_EOF (1)`, `CUSTFILE_EOF (1)`, `TRAN_OK_FLAG (1)`, `NUM_TRANFILE_RECS (1)`, `NUM_TRAN_ERRORS (1)` … (+29 more)
- **Data moves:** 35 (ASSIGN 35); most-fed items `NUMB_11`, `NUM_TRANSACTIONS`, `NUMA_11`, `NUM_PRINT_COMPLETED`, `NUMA_7V2`, `NUMB_7V2`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `0/0` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/etc/install/base/installjcl/BANK.csd` (CSD)
- **CSD resources:** `DB2CONN x1`, `DB2ENTRY x1`, `DB2TRAN x11`, `ENQMODEL x1`, `FILE x2`, `MAPSET x10`, `PIPELINE x1`, `PROGRAM x54`, `TCPIPSERVICE x2`, `TRANSACTION x17`
- **CICS bindings:** `FILE CUSTOMER→CBSA.CICSBSA.CUSTOMER`, `FILE ABNDFILE→CBSA.CICSBSA.ABNDFILE`, `DB2CONN DBCG→CBSA`, `DB2ENTRY HBANK→CBSA`, `DB2TRAN BKB2→HBANK`, `DB2TRAN HBNK→HBANK`, `DB2TRAN OB2B→HBANK`, `DB2TRAN OCAC→HBANK`, `DB2TRAN OCCA→HBANK`, `DB2TRAN OCCS→HBANK`, `DB2TRAN OCRA→HBANK`, `DB2TRAN ODAC→HBANK` … (+3)

### `tests/cobol_mainframe/refraction_excerpts/dsf/src/R001TK62.pli` (PLI)
- **Calls:** `XCTL PROGRAM_ID`
- **COMMAREA passed:** `XCTL PROGRAM_ID ← KOM_OMR`
- **Record layouts (35 items):** `SPLITT (10)`, `SAMMEN (10)`, `BMSMAPBR (1)`, `COMMAREA_PEKER (1)`, `ONKODE (1)`, `CURSOR_POS (1)`, `ONK (1)`, `FEIL (1)`, `FEILKODE (1)`, `TELLER (1)`, `FATAL_FEIL (1)`, `TK_FINNES (1)` … (+5 more)
- **CICS operations:** `FILE HISTOR (browse/read)`, `MAP S001021 (read/write)`
- **Data moves:** 40 (ASSIGN 40); most-fed items `S001021O.MELDING3O`, `TELLER`, `S001021O.FRA_TKNAVNO`, `S001021O.FRA_TKNRO`, `S001021O.FRA_TKNR_DATOO`, `S001021O.TIL_TKNAVNO`
- **Unit of work:** `0` commit / `1` rollback points; handlers `ERROR->FEILBEH`, `ENDFILE->SLUTT_FIL`; `0/0` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/cics-genapp/base/src/lgcmarea.cpy` (COBOL)
- **Record layouts (85 items):** `CA-POLICY-REQUEST (64)`, `CA-CUSTOMER-REQUEST (12)`, `CA-CUSTSECR-REQUEST (5)`, `CA-REQUEST-ID (1)`, `CA-RETURN-CODE (1)`, `CA-CUSTOMER-NUM (1)`, `CA-REQUEST-SPECIFIC (1)`

### `tests/cobol_mainframe/refraction_excerpts/cics-genapp/base/src/lgpolicy.cpy` (COBOL)
- **Record layouts (85 items):** `DB2-COMMERCIAL (17)`, `WS-POLICY-LENGTHS (14)`, `DB2-CUSTOMER (10)`, `DB2-POLICY (10)`, `DB2-ENDOWMENT (10)`, `DB2-MOTOR (10)`, `DB2-HOUSE (7)`, `DB2-CLAIM (7)`

*(+56 more files with mainframe facts; full detail in `record_data`/`call_site_data`/`dataset_data`.)*

- **Mainframe skeleton completeness:** 60% (mean channel ratio; channel table in the audit report, section 7). Top missing inputs: application programs (source or load-module list) (69 gaps); BMS map sources (28 gaps); JCL and PROC libraries (7 gaps).

## 14. PROJECT IDIOM WRAPPERS (Hidden Literal Vocabulary)
> **AI CONTEXT:** Project-local helpers that wrap a literal primitive (print, abort, allocation). Their call sites are NOT in the literal signal counts above -- read a low `debug_prints`/`panics_and_aborts`/`memory_alloc` count together with this list. Full detail in `wrapper_data`.

- **`debug_prints`:** 133 literal sites + 6 sites through wrappers = 139
- **`panics_and_aborts`:** 59 literal sites + 4 sites through wrappers = 63

- `_check_codec` (function, panics_and_aborts, primitive): 2 call sites in 1 files -- `tests/tools/equivalence_common.py`
- `_tool` (function, panics_and_aborts, primitive): 2 call sites in 1 files -- `tests/tools/pr_gates.py`
- `_warn_malformed` (function, debug_prints, primitive): 2 call sites in 1 files -- `tests/tools/tri_comparison_ledger.py`
- `run_blurbs` (function, debug_prints, primitive): 1 call sites in 1 files -- `tests/tools/tree_sitter_accuracy_audit.py`
- `run_chart` (function, debug_prints, primitive): 1 call sites in 1 files -- `tests/tools/tree_sitter_accuracy_audit.py`
- `write_current_baseline` (function, debug_prints, primitive): 1 call sites in 1 files -- `tests/mypy_audit.py`
- `write_current_baseline` (function, debug_prints, primitive): 1 call sites in 1 files -- `tests/ruff_audit.py`

## 15. FUNCTION CALL RESOLUTION (Call Graph Confidence)
> **AI CONTEXT:** Each function's callee names, linked to the definition they most plausibly mean. *scoped* = same class/file, an imported file, or a class-qualified call; *unique* = the only definition in the repository; *ambiguous* = several candidates or an untyped receiver (never a graph edge); *external* = defined nowhere here (built-ins, packages). A high scoped/unique share means the resolver made a confident choice, not that the choice was correct; resolution accuracy is measured separately (gitgalaxy#3332). Detail in `fcall_data` / `fcall_rate_data`.

- **Repository:** 36191 call pairs -- scoped 29.2%, unique 0.0%, ambiguous 6.0%, external 64.8%

| Language | Pairs | Scoped | Unique | Ambiguous | External |
|---|---|---|---|---|---|
| python | 35489 | 29.0% | 0.0% | 6.2% | 64.9% |
| java | 325 | 10.2% | 0.0% | 0.3% | 89.5% |
| cobol | 212 | 92.9% | 0.5% | 1.4% | 5.2% |
| javascript | 85 | 11.8% | 0.0% | 0.0% | 88.2% |
| c | 56 | 39.3% | 0.0% | 0.0% | 60.7% |
| pli | 13 | 84.6% | 15.4% | 0.0% | 0.0% |
| jcl | 11 | 0.0% | 0.0% | 0.0% | 100.0% |

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
