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
- **Scope:** 1280 analyzed artifact(s), 248910 LOC.
- **Load-bearing artifact:** `gitgalaxy/core/detector.py` -- 105 in-repo importer(s) depend on it. Changes here propagate furthest.
- **Top orchestrator:** `gitgalaxy/galaxyscope.py` -- pulls in 68 dependencies, the widest assembly point in the scan.
- **Heaviest artifact:** `gitgalaxy/core/detector.py` at magnitude 10971.2 (structural weight, not risk).
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
| Total Artifacts | 3783 |
| Analyzed Artifacts (Scanned) | 1280 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 2503 |
| Total LOC | 248910 |
| Volatility Index | 0.009 |
| % Scanned of codebase = | 33.8% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.7378 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.1931 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 1.2% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 3.1535 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 141 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 857 | 197499 | 67.0% |
| PLAINTEXT | 96 | 0 | 7.5% |
| JAVA | 86 | 26378 | 6.7% |
| COBOL | 83 | 12783 | 6.5% |
| YAML | 48 | 3675 | 3.8% |
| MARKDOWN | 45 | 0 | 3.5% |
| PLI | 10 | 1425 | 0.8% |
| SHELL | 8 | 256 | 0.6% |
| BMS | 8 | 1471 | 0.6% |
| C | 8 | 2364 | 0.6% |
| CSD | 7 | 1138 | 0.5% |
| SQLITE | 6 | 839 | 0.5% |
| JCL | 5 | 365 | 0.4% |
| HLASM | 3 | 446 | 0.2% |
| DB2_SQL | 3 | 94 | 0.2% |
| BINARY_THREAT | 3 | 3 | 0.2% |
| DOCKERFILE | 2 | 16 | 0.2% |
| XML | 1 | 0 | 0.1% |
| JAVASCRIPT | 1 | 158 | 0.1% |

## 4.1 SOURCE ENCODINGS
| Encoding | Decode | Files |
|---|---|---|
| utf-8 | utf-8 | 1277 |
| unknown | unknown | 3 |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Hub-Coupled App`
> **Architectural Drift Z-Score:** `2.016`
> **Composition Archetype:** `Hub-Coupled App` (z +2.02; from the repo's file-archetype mix)
> **File Composition:** Large Core Modules (2) 33%, Data / Markup / Trivial 18%, Large Core Modules (3) 13%, Declarative / Non-Code 10%, Generic / Templated Code Files 6%
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 1136 | 88.8% |
| Unknown | 3 | 0.2% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 141 | 11.0% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 2503*

**Composition by Extension & Reason:**
- `.snap`: 693x Excluded (Unsupported Extension: '.snap'), 381x Unsupported Format (.snap)
- `.json`: 700x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.md`: 526x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 464 LOC)
- `no_extension`: 71x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 3x Unsupported Format (.undeterminable)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 680 LOC), 1x Excluded (Machine-Generated Source Code Signature: 357 LOC)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.java`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.csv`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.jsonl`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Saturation: Line 1 exceeds 500 chars)
- `.yaml`: 1x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 85.4 | 3.2 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 100.0 | 5.7 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 97.1 | 0.4 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 3.5 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 55.0 | 0.8 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 18.9 | 0.1 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 5.7 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 25.3 | 0.1 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 2.3 | 0.0 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 87.0 | 1.0 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) _(coverage)_ | 0.0 | 100.0 | 1.2 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

> `Doc Surface (formerly Documentation Exposure)` is **documentation coverage, not a fragility driver**. It is reported for context beside program length, and is deliberately excluded from the ranked-file drivers in this brief: it measures the share of a file's unit weight a reader cannot recover from documentation, so on a codebase that documents little it sits near ceiling everywhere and describes the repo rather than distinguishing files within it.
> `Spec Alignment (formerly Specification Exposure)` was **not measured** on this scan and is therefore absent above rather than reported as 0 (which would assert full alignment). Enable it with `--spec-alignment` if this codebase uses the corresponding convention.

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 782 | 49 | 0 | `gitgalaxy/recorders/record_keeper.py` |
| cleanup | 24 | 10 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 1577 | 64 | 0 | `gitgalaxy/core/detector.py` |
| danger | 1312 | 62 | 0 | `gitgalaxy/core/detector.py` |
| concurrency | 34 | 11 | 0 | `gitgalaxy/core/detector.py` |
| connectivity | 307 | 62 | 0 | `gitgalaxy/core/detector.py` |
| io | 152 | 32 | 0 | `.claude/hooks/session-start.sh` |
| crypto | 3 | 3 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 35 | 5 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 50 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 437 | 40 | 0 | `gitgalaxy/core/detector.py` |
| events | 284 | 21 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 6 | 4 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 776 | 68 | 0 | `gitgalaxy/core/detector.py` |
| debt | 199 | 24 | 0 | `gitgalaxy/cobol_to_java_controller.py` |
| mutation | 15296 | 66 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 74 | 11 | 0 | `gitgalaxy/core/detector.py` |
| credential | 3 | 2 | 0 | `gitgalaxy/core/detector.py` |
| threat | 88 | 13 | 0 | `gitgalaxy/core/rule_prefilter.py` |
| ml_ai | 0 | 0 | 0 | - |
| ui | 1 | 1 | 0 | `gitgalaxy/recorders/llm_recorder.py` |

**Relations (repo medians):**
- `guard_balance_ratio` (guards / (danger + 1)): **0.0**
- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **0.0**

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `.claude/hooks/session-start.sh` (Hits: 45)
- `scripts/setup_java_toolchain.sh` (Hits: 17)
- `gitgalaxy/galaxyscope.py` (Hits: 13)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **detector.py** (`gitgalaxy/core/detector.py`) — 105 inbound connections
2. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 75 inbound connections
3. **source_text.py** (`gitgalaxy/core/source_text.py`) — 73 inbound connections
4. **_strict_harness.py** (`tests/extraction/languages/_strict_harness.py`) — 70 inbound connections
5. **galaxy_ir.py** (`gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py`) — 62 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 68 outbound dependencies
2. **BANK.csd** (`tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/etc/install/base/installjcl/BANK.csd`) — 54 outbound dependencies
3. **test_ai_ml_import_anchor_4150.py** (`tests/extraction/languages/test_ai_ml_import_anchor_4150.py`) — 50 outbound dependencies
4. **test_llm_api_anchor_4137.py** (`tests/extraction/languages/test_llm_api_anchor_4137.py`) — 37 outbound dependencies
5. **Cbact04cService.java** (`tests/equivalence/carddemo-intcalc/port/service/Cbact04cService.java`) — 37 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1304.0** | LOC: 1369
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **924.6** | LOC: 1093
- `_translate` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_java/det/program.py`) -> Impact: **858.3** | LOC: 608
- `score` **(Many-Argument Workhorses)** (@ `tests/tools/cobol_answer_key.py`) -> Impact: **745.4** | LOC: 748
- `_mainframe_facts_lines` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **532.0** | LOC: 421
  * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These are the named mainframe relations/schemas the per-fi...
- `_calculate_block_metrics` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **518.1** | LOC: 555
- `splice` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **477.5** | LOC: 838
- `load_galaxy_ir` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py`) -> Impact: **476.1** | LOC: 758
  * *Intent:* """Loads the latest snapshot of one repo from a master DB, opened read-only."""
- `run` **(Many-Argument Workhorses)** (@ `tests/tools/strengthen.py`) -> Impact: **403.8** | LOC: 170
  * *Intent:* # ---- the loop ------------------------------------------------------------------------------------------------
- `translate_command` **(Many-Argument Workhorses)** (@ `tests/tools/equivalence_cics.py`) -> Impact: **401.8** | LOC: 236
  * *Intent:* """One EXEC CICS body -> the COBOL statements that replace it. `labels` are the program's HANDLE labels (handler_labels), which a condition or abend e...

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `gitgalaxy/core` | 50 | 29764.66 | 50.37% | 4.83% |
| `tests/extraction/languages` | 144 | 15975.14 | 12.9% | 0.0% |
| `tests/cobol_mainframe` | 144 | 13835.3 | 15.88% | 0.0% |
| `tests/core_engine` | 104 | 12404.82 | 13.3% | 0.0% |
| `gitgalaxy/recorders` | 8 | 6822.26 | 46.78% | 4.0% |
| `gitgalaxy` | 5 | 4184.06 | 43.99% | 1.92% |
| `gitgalaxy/metrics` | 7 | 3917.68 | 45.75% | 10.89% |
| `tests` | 26 | 2921.66 | 16.84% | 0.0% |
| `tests/cobol_mainframe/port_invariance/aws-mainframe-modernization-carddemo/java` | 7 | 2774.18 | 37.99% | 0.0% |
| `tests/tools_recorders` | 42 | 2729.74 | 11.44% | 0.0% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `.github/ISSUE_TEMPLATE/parsing_discrepancy.yml` -> **97.0688%** Exposure
- `gitgalaxy/core/ebcdic_dbcs.py` -> **88.1655%** Exposure
- `gitgalaxy/core/rule_prefilter.py` -> **65.1355%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **53.2847%** Exposure
- `gitgalaxy/core/prism.py` -> **43.0304%** Exposure
### Highest Mutation Surface (formerly State Flux; Mutation/Volatility)
- `.claude/hooks/pytest_quiet.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/bms_screen_fields.py` -> **100.0%** Exposure
- `gitgalaxy/core/bms_symbolic.py` -> **100.0%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/core/mainframe_boundary.py` -> **0** Orphaned Functions | **11** Duplicates
- `gitgalaxy/metrics/archetype_classifier.py` -> **4** Orphaned Functions | **0** Duplicates
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
- **Unknown Dependencies:** `7701` packages imported that bypass the Zero-Trust whitelist.

## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)
> Ranked by Structural Magnitude: the file's structural weight and centralization within the system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not the vector percentages, is the actionable part.

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 10971.2 | **LOC:** 10685 | **CtrlFlow:** 43.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **105** in-repo importer(s); it depends on **19**; blast radius 18.1; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (87.0%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 19.7917% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1304.0)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 518.1)
  * `splice` **(Many-Argument Workhorses)** (Impact: 477.5)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 254.5)
  * `_slice_by_indentation` **(Many-Argument Workhorses)** (Impact: 251.2)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 3 instances
* *Amplified Cascading Flux:* 1492 instances
* *Concurrency (weighted view):* 21
* *State Mutation (weighted view):* 4691
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 2326`, `structural_boundaries: 694`, `args: 132`, `func_start: 124`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 155`, `state_mutation: 1707`, `dead_code: 50`, `planned_debt: 2`, `fragile_debt: 25`
* *Architecture:* `api: 22`, `concurrency: 6`, `import: 23`
* *Defense:* `safety: 51`, `doc: 121`, `immutability_locks: 52`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 18.1
  * `Choke Point (Betweenness):` 0.002852 | `Ripple Effect (Closeness):` 0.078256
  * `Imports (Out-Degree: 8):` bisect, collections, functools, gitgalaxy.core.cobol_source_format, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.prism, gitgalaxy.core.rule_prefilter, gitgalaxy.core.spatial_correlation...
  * `Imported By (In-Degree: 105):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 3800.76 | **LOC:** 2389 | **CtrlFlow:** 41.9% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **11** in-repo importer(s); it depends on **16**; blast radius 1.652; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Complexity Load (formerly Cognitive Load) (83.7%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 31.8182% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_build_markdown` **(Many-Argument Workhorses)** (Impact: 924.6)
  * `_mainframe_facts_lines` **(Many-Argument Workhorses)** (Impact: 532.0)
    * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These ar...
  * `_executive_summary_lines` **(Stateful Encapsulated Methods)** (Impact: 58.0)
  * `generate_artifacts` **(Many-Argument Workhorses)** (Impact: 42.2)
  * `_source_encoding_lines` **(Stateful Encapsulated Methods)** (Impact: 36.8)
    * *Intent:* """#3813: how the parsed files' bytes became text. One line when every file is UTF-8; otherwise a ta...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 593 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1915
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 728`, `structural_boundaries: 147`, `args: 55`, `func_start: 24`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 79`, `state_mutation: 729`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `io: 2`, `api: 4`, `concurrency: 2`, `import: 15`
* *Defense:* `safety: 17`, `doc: 25`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.652
  * `Choke Point (Betweenness):` 4e-05 | `Ripple Effect (Closeness):` 0.015689
  * `Imports (Out-Degree: 5):` collections, gitgalaxy.core.call_resolver, gitgalaxy.core.compiler_options, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.standards, heapq, hops...
  * `Imported By (In-Degree: 11):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3172.54 | **LOC:** 4233 | **CtrlFlow:** 25.9% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **20** in-repo importer(s); it depends on **68**; blast radius 3.061; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.2%), Complexity Load (formerly Cognitive Load) (80.8%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 20.1493% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 272.8)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_process_file_worker` **(Many-Argument Workhorses)** (Impact: 155.4)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 142.6)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `main` **(I/O & Config Routines)** (Impact: 112.3)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
  * `_calculate_risk_exposures` **(Many-Argument Workhorses)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 518 instances
* *Concurrency (weighted view):* 17
* *State Mutation (weighted view):* 1776
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 673`, `structural_boundaries: 317`, `args: 56`, `func_start: 44`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 142`, `high_risk_execution: 2`, `state_mutation: 740`, `dead_code: 1`
* *Architecture:* `io: 13`, `api: 14`, `concurrency: 7`, `import: 78`
* *Defense:* `safety: 59`, `doc: 37`, `test: 2`, `immutability_locks: 10`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 3.061
  * `Choke Point (Betweenness):` 0.001535 | `Ripple Effect (Closeness):` 0.016711
  * `Imports (Out-Degree: 41):` argparse, collections, concurrent.futures, copy, datetime, extraction, functools, gitgalaxy.core.aperture...
  * `Imported By (In-Degree: 20):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/mainframe_boundary.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2850.82 | **LOC:** 2654 | **CtrlFlow:** 41.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **49** in-repo importer(s); it depends on **28**; blast radius 11.219; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (81.0%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 10.9589% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_cobol_records` **(Many-Argument Workhorses)** (Impact: 200.7)
    * *Intent:* """The DATA DIVISION item tree and FD record layouts of one COBOL file (#3246). #3911: `decimal_comm...
  * `_cobol_calls` **(Stateful Encapsulated Methods)** (Impact: 159.8)
    * *Intent:* """Every COBOL invocation site: `CALL`, and CICS `LINK`/`XCTL PROGRAM(...)`. `cics_only` (#3495) rea...
  * `_pli_item_attributes` **(Compute Cores)** (Impact: 72.8)
    * *Intent:* """The record_data fields of one item from its attribute tokens, or None when the declaration is not...
  * `_pli_records` **(Stateful Encapsulated Methods)** (Impact: 56.5)
    * *Intent:* """The DECLAREd data items of one PL/I file as a record tree (#3250). Same flat, source-ordered shap...
  * `_jcl_boundary` **(Compute Cores)** (Impact: 49.0)
    * *Intent:* """JCL `EXEC PGM=` steps and the `DD` statements that bind a ddname to a dataset. #3345: alongside t...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 457 instances
* *State Mutation (weighted view):* 1455
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 689`, `structural_boundaries: 279`, `args: 79`, `func_start: 71`
* *Risk/State:* `safety_bypasses: 90`, `state_mutation: 541`, `dead_code: 2`, `duplicate_logic: 11`
* *Architecture:* `api: 2`, `import: 28`
* *Defense:* `safety: 3`, `doc: 57`, `immutability_locks: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 11.219
  * `Choke Point (Betweenness):` 0.00486 | `Ripple Effect (Closeness):` 0.089963
  * `Imports (Out-Degree: 23):` bisect, gitgalaxy.core.bms_screen_fields, gitgalaxy.core.call_using, gitgalaxy.core.cics_resources, gitgalaxy.core.cics_tasks, gitgalaxy.core.compiler_options, gitgalaxy.core.data_moves, gitgalaxy.core.db2_declare_table...
  * `Imported By (In-Degree: 49):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 2453.22 | **LOC:** 5873 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **12**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_detector_c_macro_elif_chain_function_liveness` **(I/O & Config Routines)** (Impact: 16.7)
    * *Intent:* """ #1720: each `#elif` starts a new condition for the rest of its chain. A statically false branch ...
  * `test_spatial_mapper_sectorization_and_monolith` **(Defensive Guards)** (Impact: 15.5)
    * *Intent:* """ Proves the engine correctly groups files into sector constellations by their parent directories,...
  * `test_detector_c_macro_dead_branch_shield` **(Defensive Guards)** (Impact: 14.7)
    * *Intent:* """ Pins that a statically-dead C preprocessor branch is not counted (#2814). `detector._blank_dead_...
  * `test_detector_c_macro_nested_blocks_inside_dead_region_stay_dead` **(I/O & Config Routines)** (Impact: 13.8)
    * *Intent:* """ #1720: inside a dead region everything stays dead until the enclosing block's `#endif`, whatever...
  * `test_detector_c_macro_directive_keywords_are_whole_words` **(I/O & Config Routines)** (Impact: 13.4)
    * *Intent:* """ #1720: directives are recognised by whole keyword. `#if(0)` (no space), `# if` (blanks after `#`...
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

### `tests/equivalence/cics/ggcics.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 2448.66 | **LOC:** 1770 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **6**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `browse_read` **(Many-Argument Workhorses)** (Impact: 127.5)
    * *Intent:* /* READNEXT (dir 1) / READPREV (dir -1) FILE(name1) INTO RIDFLD. */
  * `rba_read` **(Many-Argument Workhorses)** (Impact: 101.3)
    * *Intent:* /* READNEXT (dir 1) / READPREV (dir -1) ... RBA: GG-FLAGS 'RBA'; the browse is an RBA browse. */
  * `GGCSTRT` **(Compute Cores)** (Impact: 58.0)
    * *Intent:* /* START TRANSID(name1) [TERMID(name2)] [REQID(qname)] INTERVAL(hhmmss) | TIME(hhmmss) (GG-NUM, * GG...
  * `GGCDELT` **(Many-Argument Workhorses)** (Impact: 54.4)
    * *Intent:* /* DELETE FILE(name1) [RIDFLD]: the record with that key, or (no RIDFLD: GG-FLAGS 'HELD') the one a ...
  * `pick` **(Stateful Encapsulated Methods)** (Impact: 48.7)
    * *Intent:* /* The record whose key is the least key > `key` (strict), >= (or_equal), or the greatest < `key` (b...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` direct.h, stdio.h, stdlib.h, string.h, stat.h, time.h
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 2126.82 | **LOC:** 2275 | **CtrlFlow:** 27.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **13** in-repo importer(s); it depends on **12**; blast radius 2.119; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.5%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (63.4%)
- **Documentation Coverage:** 29.3103% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` **(Many-Argument Workhorses)** (Impact: 254.0)
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
* *State Mutation (weighted view):* 1108
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 367`, `structural_boundaries: 147`, `args: 48`, `func_start: 37`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 44`, `state_mutation: 460`, `dead_code: 1`, `planned_debt: 1`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 10`, `concurrency: 2`, `import: 13`
* *Defense:* `safety: 29`, `doc: 28`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.119
  * `Choke Point (Betweenness):` 3.9e-05 | `Ripple Effect (Closeness):` 0.016667
  * `Imports (Out-Degree: 4):` collections.abc, gitgalaxy.core.function_population, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math...
  * `Imported By (In-Degree: 13):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 2018.3 | **LOC:** 2058 | **CtrlFlow:** 35.7% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **52** in-repo importer(s); it depends on **5**; blast radius 7.489; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (49.4%)
- **Documentation Coverage:** 20.7547% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` **(Many-Argument Workhorses)** (Impact: 124.1)
    * *Intent:* """ Single-line comment stripper for the "line_exclusive" family, driven by each language's own real...
  * `_strip_single_line_comments_positional` **(Many-Argument Workhorses)** (Impact: 122.2)
    * *Intent:* """Positional sibling of `_strip_single_line_comments`: same per-line masking and carry-quote discip...
  * `_strip_positional_comments` **(Many-Argument Workhorses)** (Impact: 97.5)
  * `_mask_perl_line_positional` **(Many-Argument Workhorses)** (Impact: 75.4)
  * `_mask_perl_line` **(Many-Argument Workhorses)** (Impact: 75.4)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 290 instances
* *State Mutation (weighted view):* 924
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 350`, `structural_boundaries: 178`, `args: 48`, `func_start: 45`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 344`, `fragile_debt: 6`, `duplicate_logic: 2`
* *Architecture:* `api: 11`, `import: 5`
* *Defense:* `safety: 4`, `doc: 42`, `immutability_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 7.489
  * `Choke Point (Betweenness):` 3.2e-05 | `Ripple Effect (Closeness):` 0.067631
  * `Imports (Out-Degree: 1):` gitgalaxy.core.cobol_source_format, gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 52):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1979.02 | **LOC:** 1617 | **CtrlFlow:** 46.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **17** in-repo importer(s); it depends on **18**; blast radius 4.442; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (59.7%)
- **Documentation Coverage:** 22.9167% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_target` **(Many-Argument Workhorses)** (Impact: 207.6)
  * `_resolve_by_name` **(Many-Argument Workhorses)** (Impact: 156.2)
  * `_resolve_in_libraries` **(Many-Argument Workhorses)** (Impact: 87.8)
  * `_resolve_edges` **(Many-Argument Workhorses)** (Impact: 70.3)
    * *Intent:* """ #2992: resolves every file's raw_imports into directed file-to-file edges, keyed (importer, impo...
  * `build_dependency_graph` **(Many-Argument Workhorses)** (Impact: 68.8)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 243 instances
* *State Mutation (weighted view):* 756
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 432`, `structural_boundaries: 196`, `args: 42`, `func_start: 41`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 52`, `high_risk_execution: 1`, `state_mutation: 270`, `dead_code: 4`
* *Architecture:* `io: 5`, `api: 8`, `import: 16`
* *Defense:* `safety: 14`, `doc: 37`, `immutability_locks: 8`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.442
  * `Choke Point (Betweenness):` 0.002544 | `Ripple Effect (Closeness):` 0.0605
  * `Imports (Out-Degree: 7):` collections, gitgalaxy.core.copy_libraries, gitgalaxy.core.graph_engine, gitgalaxy.core.invocation_resolver, gitgalaxy.core.package_self_reference, gitgalaxy.core.path_proximity, gitgalaxy.core.unicode_paths, gitgalaxy.standards.analysis_lens...
  * `Imported By (In-Degree: 17):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1641.62 | **LOC:** 1555 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **9**
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
  * `Imports (Out-Degree: 0):` gitgalaxy.core.source_text, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging, math, pathlib, re, time...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/call_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 1383.22 | **LOC:** 1232 | **CtrlFlow:** 45.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **11** in-repo importer(s); it depends on **3**; blast radius 4.079; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.7%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (55.2%)
- **Documentation Coverage:** 21.9298% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `resolve_calls` **(Many-Argument Workhorses)** (Impact: 216.0)
  * `_resolve_one` **(Many-Argument Workhorses)** (Impact: 169.6)
  * `_visible_receiver` **(Stateful Encapsulated Methods)** (Impact: 37.2)
    * *Intent:* """An untyped receiver (`x.save()`): confident only when exactly ONE visible class defines the metho...
  * `_index` **(Type Conversions)** (Impact: 32.9)
    * *Intent:* """(link group, name key) -> every definition of that name, in scan order. Functions and classes sha...
  * `_constructor_of` **(Stateful Encapsulated Methods)** (Impact: 31.2)
    * *Intent:* """The constructor method of class definition `cls`, if the scan extracted one. One in the class's o...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 153 instances
* *State Mutation (weighted view):* 490
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 369`, `structural_boundaries: 164`, `args: 51`, `func_start: 44`, `class_start: 4`
* *Risk/State:* `safety_bypasses: 37`, `high_risk_execution: 2`, `state_mutation: 184`, `dead_code: 4`
* *Architecture:* `io: 1`, `api: 13`, `import: 3`
* *Defense:* `safety: 4`, `doc: 30`, `immutability_locks: 18`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.079
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.031403
  * `Imports (Out-Degree: 0):` collections, posixpath, typing
  * `Imported By (In-Degree: 11):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/test_galaxy_ir.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1275.72 | **LOC:** 2371 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
- **Magnitude:** 1164.34 | **LOC:** 3061 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1096.44 | **LOC:** 1157 | **CtrlFlow:** 24.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **7** in-repo importer(s); it depends on **10**; blast radius 1.156; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (96.9%), Complexity Load (formerly Cognitive Load) (85.4%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 26.4706% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `generate_report` **(Many-Argument Workhorses)** (Impact: 349.6)
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
* *State Mutation (weighted view):* 487
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 219`, `structural_boundaries: 41`, `args: 15`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 18`, `state_mutation: 179`
* *Architecture:* `io: 3`, `api: 7`, `import: 10`
* *Defense:* `safety: 10`, `doc: 7`, `sync_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.156
  * `Choke Point (Betweenness):` 1.9e-05 | `Ripple Effect (Closeness):` 0.013628
  * `Imports (Out-Degree: 3):` argparse, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.standards, json, logging, os, pathlib...
  * `Imported By (In-Degree: 7):` (Excluded from Brief to save tokens)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1062.78 | **LOC:** 753 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `slice_manifest` **(Compute Cores)** (Impact: 181.9)
  * `locate_physical_package` **(Many-Argument Workhorses)** (Impact: 130.1)
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
- **Magnitude:** 1060.5 | **LOC:** 4043 | **CtrlFlow:** 20.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **41** in-repo importer(s); it depends on **12**; blast radius 6.476; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (91.0%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (67.4%)
- **Documentation Coverage:** 15.7895% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_classify_file_archetype_detail` **(Many-Argument Workhorses)** (Impact: 52.9)
    * *Intent:* """``(name, distance, fingerprint)``: the nearest archetype, the Euclidean distance to its centroid ...
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
* *State Mutation (weighted view):* 785
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 425`, `structural_boundaries: 83`, `args: 39`, `func_start: 16`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 303`, `dead_code: 5`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 5`, `import: 12`
* *Defense:* `safety: 31`, `doc: 64`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 6.476
  * `Choke Point (Betweenness):` 0.000136 | `Ripple Effect (Closeness):` 0.03371
  * `Imports (Out-Degree: 5):` gitgalaxy.core.call_resolver, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.metrics.archetype_parity, gitgalaxy.standards.analysis_lens, json, logging, math...
  * `Imported By (In-Degree: 41):` (Excluded from Brief to save tokens)

### `tests/equivalence/carddemo-cardlist/port/service/CocrdlicService.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 1021.04 | **LOC:** 1002 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **24**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `sendMap` **(Many-Argument Workhorses)** (Impact: 80.9)
    * *Intent:* // ------------------------------------------------------------------ 1000-SEND-MAP
  * `runTask` **(Compute Cores)** (Impact: 55.4)
    * *Intent:* /** One pseudo-conversational task of this program (#3754): paragraph 0000-MAIN through COMMON-RETUR...
  * `copyCommarea` **(Stateful Encapsulated Methods)** (Impact: 47.7)
  * `readForward` **(Many-Argument Workhorses)** (Impact: 32.4)
    * *Intent:* // ------------------------------------------------------------------ 9000-READ-FORWARD /** Returns ...
  * `storePfKey` **(Stateful Encapsulated Methods)** (Impact: 23.4)
    * *Intent:* // ------------------------------------------------------------------ YYYY-STORE-PFKEY
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` com.gitgalaxy.modernized.cics.CicsTask, com.gitgalaxy.modernized.dto.contract.CarddemoCommarea, com.gitgalaxy.modernized.dto.contract.CocrdlicCommarea, com.gitgalaxy.modernized.dto.contract.CocrdlicWsThisProgcommarea, com.gitgalaxy.modernized.dto.screen.CcrdliaScreen, com.gitgalaxy.modernized.entity.vsam.CardRecord, com.gitgalaxy.modernized.entity.vsam.CobolRecords, com.gitgalaxy.modernized.repository.vsam.CardRecordRepository...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/equivalence/db2/ggsql.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 971.0 | **LOC:** 558 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGSQL` **(Many-Argument Workhorses)** (Impact: 181.5)
    * *Intent:* /* ---- the entry ----------------------------------------------------------------------------------...
  * `num_store` **(Many-Argument Workhorses)** (Impact: 94.8)
    * *Intent:* /* decimal text into a numeric host variable; -304 when the integer part does not fit, 0 when stored...
  * `num_text` **(Stateful Encapsulated Methods)** (Impact: 58.0)
    * *Intent:* /* a numeric host variable's value as decimal text ("-123.45"); 0 when its bytes are no number */
  * `fetch_into` **(Many-Argument Workhorses)** (Impact: 40.5)
  * `injected` **(Stateful Encapsulated Methods)** (Impact: 39.6)
    * *Intent:* /* ---- #4173: SQL faults --------------------------------------------------------------------------...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` ctype.h, sqlca.h, sqlcli1.h, stdarg.h, stdio.h, stdlib.h, string.h
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/graph_engine.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_5` (Drift: 0.0 IQR)
- **Magnitude:** 943.38 | **LOC:** 783 | **CtrlFlow:** 30.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** changing it is visible to **6** in-repo importer(s); it depends on **6**; blast radius 2.118; role: Pure Producer (Foundation)
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 2.118
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.04548
  * `Imports (Out-Degree: 0):` collections, collections.abc, math, operator, random, typing
  * `Imported By (In-Degree: 6):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/port_invariance/aws-mainframe-modernization-carddemo/java/Cousr03cService.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 842.96 | **LOC:** 1714 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **26**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `in_Cousr03cCarddemoCommarea` **(Compute Cores)** (Impact: 93.3)
  * `runTask` **(Defensive Guards)** (Impact: 67.8)
    * *Intent:* /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
  * `run` **(Stateful Encapsulated Methods)** (Impact: 37.6)
  * `p0` **(I/O & Config Routines)** (Impact: 23.9)
    * *Intent:* /** MAIN-PARA. */
  * `p5` **(I/O & Config Routines)** (Impact: 17.4)
    * *Intent:* /** RECEIVE-USRDEL-SCREEN. */
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` com.gitgalaxy.modernized.batch.CobolAbend, com.gitgalaxy.modernized.batch.CobolFiles, com.gitgalaxy.modernized.batch.DatasetResolver, com.gitgalaxy.modernized.batch.Dd, com.gitgalaxy.modernized.batch.MainframeClock, com.gitgalaxy.modernized.batch.Sysout, com.gitgalaxy.modernized.cics.CicsTask, com.gitgalaxy.modernized.cobolrt.Cobol...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/core_engine/test_signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_2` (Drift: N/A IQR)
- **Magnitude:** 799.64 | **LOC:** 2139 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `test_record_keeper_classifies_file_archetype_from_self_describing_brain` **(Defensive Guards)** (Impact: 6.6)
    * *Intent:* """record_keeper._classify_file_archetype builds the vector in FEATURE_NAMES order from the file's m...
  * `test_signal_processor_unknown_language_gets_no_language_term` **(Defensive Guards)** (Impact: 6.4)
    * *Intent:* # ============================================================================== # TEST 47: TIER 3 L...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` gitgalaxy.metrics, gitgalaxy.metrics.signal_processor, gitgalaxy.recorders, gitgalaxy.recorders.record_keeper, gitgalaxy.recorders.sarif_recorder, json, logging, math...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cobol_mainframe/port_invariance/aws-mainframe-modernization-carddemo/java/Cousr01cService.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 785.54 | **LOC:** 1643 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **26**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `in_CarddemoCommarea` **(Stateful Encapsulated Methods)** (Impact: 69.0)
  * `runTask` **(Defensive Guards)** (Impact: 67.8)
    * *Intent:* /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
  * `run` **(Stateful Encapsulated Methods)** (Impact: 31.8)
  * `p4` **(I/O & Config Routines)** (Impact: 18.5)
    * *Intent:* /** RECEIVE-USRADD-SCREEN. */
  * `perform` **(Stateful Encapsulated Methods)** (Impact: 17.3)
    * *Intent:* /** PERFORM from THRU thru. When control falls off the end of a paragraph, the innermost active PERF...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` com.gitgalaxy.modernized.batch.CobolAbend, com.gitgalaxy.modernized.batch.CobolFiles, com.gitgalaxy.modernized.batch.DatasetResolver, com.gitgalaxy.modernized.batch.Dd, com.gitgalaxy.modernized.batch.MainframeClock, com.gitgalaxy.modernized.batch.Sysout, com.gitgalaxy.modernized.cics.CicsTask, com.gitgalaxy.modernized.cobolrt.Cobol...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cics_crucible/test_cics_crucible_runner.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 784.38 | **LOC:** 1048 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **16**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_strengthened_scenarios_join_their_case_with_their_derived_logs` **(Defensive Guards)** (Impact: 25.0)
  * `run_one` **(Compute Cores)** (Impact: 18.8)
  * `test_a_facade_proof_needs_both_paths_and_names_the_facades_it_entered_by` **(Defensive Guards)** (Impact: 15.4)
    * *Intent:* """#4343: with the java-facade side, a scenario is proven only when it passes through runTask AND th...
  * `test_a_proof_reports_per_scenario_and_feeds_back_the_first_divergence` **(Defensive Guards)** (Impact: 15.2)
  * `_actual_from_expected` **(Stateful Encapsulated Methods)** (Impact: 13.6)
    * *Intent:* """The actual log a perfect stub would record for the fixture (areas as runtime bytes)."""
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` _cics_crucible_pin, cics_bms, cics_crucible, cics_crucible_compare, copy, datetime, decimal, equivalence_cics...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cobol_mainframe/port_invariance/cics-banking-sample-application-cbsa/java/DbcrfunService.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 773.2 | **LOC:** 1668 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **28**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `run` **(Compute Cores)** (Impact: 75.0)
  * `in_AbndprocAbndinfoRec` **(Stateful Encapsulated Methods)** (Impact: 52.9)
  * `in_Bnk1craSubpgmParms` **(Stateful Encapsulated Methods)** (Impact: 52.9)
  * `p10` **(I/O & Config Routines)** (Impact: 27.9)
    * *Intent:* /** WTPD010. */
  * `p19` **(I/O & Config Routines)** (Impact: 25.9)
    * *Intent:* /** AH010. */
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` com.gitgalaxy.modernized.batch.CobolAbend, com.gitgalaxy.modernized.batch.CobolFiles, com.gitgalaxy.modernized.batch.DatasetResolver, com.gitgalaxy.modernized.batch.Dd, com.gitgalaxy.modernized.batch.MainframeClock, com.gitgalaxy.modernized.batch.Sysout, com.gitgalaxy.modernized.cics.CicsTask, com.gitgalaxy.modernized.cobolrt.Cobol...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cobol_mainframe/port_invariance/cics-banking-sample-application-cbsa/java/InqaccService.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 753.44 | **LOC:** 1811 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **27**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `run` **(Compute Cores)** (Impact: 83.6)
  * `in_InqaccCommarea` **(Stateful Encapsulated Methods)** (Impact: 57.0)
  * `in_AbndprocAbndinfoRec` **(Stateful Encapsulated Methods)** (Impact: 52.9)
  * `p16` **(I/O & Config Routines)** (Impact: 35.5)
    * *Intent:* /** AH010. */
  * `p4` **(I/O & Config Routines)** (Impact: 32.3)
    * *Intent:* /** RAD010. */
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` com.gitgalaxy.modernized.batch.CobolAbend, com.gitgalaxy.modernized.batch.CobolFiles, com.gitgalaxy.modernized.batch.DatasetResolver, com.gitgalaxy.modernized.batch.Dd, com.gitgalaxy.modernized.batch.MainframeClock, com.gitgalaxy.modernized.batch.Sysout, com.gitgalaxy.modernized.cics.CicsTask, com.gitgalaxy.modernized.cobolrt.Cobol...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

## 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 12.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/core/detector.py` -> Churn: **86.96%** | Cog Load: 66.6189% | Debt: 14.5669%
- `gitgalaxy/core/mainframe_boundary.py` -> Churn: **81.0%** | Cog Load: 55.3087% | Debt: 30.3781%
- `gitgalaxy/galaxyscope.py` -> Churn: **63.82%** | Cog Load: 80.7597% | Debt: 0.0%
- `gitgalaxy/core/network_risk_sensor.py` -> Churn: **59.73%** | Cog Load: 52.958% | Debt: 0.0%
- `gitgalaxy/metrics/signal_processor.py` -> Churn: **54.99%** | Cog Load: 63.4182% | Debt: 9.0005%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 10971.2
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3800.76
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3172.54
- `gitgalaxy/core/mainframe_boundary.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2850.82
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2126.82

## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 0.486** (Bridge: 0.0049 * Flux: 100.0%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.285** (Bridge: 0.0029 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.254** (Bridge: 0.0025 * Flux: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py` -> **Severity: 0.214** (Bridge: 0.0021 * Flux: 100.0%)
- `gitgalaxy/core/invocation_resolver.py` -> **Severity: 0.196** (Bridge: 0.002 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 13.038** (Embedded: 0.1313 * Error Risk: 99.3102%)
- `gitgalaxy/core/source_text.py` -> **Severity: 12.391** (Embedded: 0.1305 * Error Risk: 94.9407%)
- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 9.319** (Embedded: 0.0944 * Error Risk: 98.6853%)
- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 8.975** (Embedded: 0.09 * Error Risk: 99.766%)
- `gitgalaxy/core/compiler_options.py` -> **Severity: 8.74** (Embedded: 0.088 * Error Risk: 99.3555%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 2003.4** (Blast Radius: 20.034 * Doc Risk: 100.0%)
- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 1202.114** (Blast Radius: 29.385 * Doc Risk: 40.9091%)
- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 1131.48** (Blast Radius: 28.287 * Doc Risk: 40.0%)
- `gitgalaxy/tools/cobol_to_java/det/cobolrt/Field.java` -> **Severity: 378.8** (Blast Radius: 5.682 * Doc Risk: 66.6667%)
- `gitgalaxy/core/detector.py` -> **Severity: 358.23** (Blast Radius: 18.1 * Doc Risk: 19.7917%)

## 13. MAINFRAME SYSTEM FACTS (Named Relations & Record Layouts)
> **AI CONTEXT:** Named mainframe relations the structural signal counts flatten -- the call graph (`CALL`/CICS `LINK`·`XCTL`/JCL `EXEC PGM=`), the dataset boundary (`SELECT…ASSIGN` + `OPEN` modes, JCL `DD`→dataset), and record layouts (COBOL DATA DIVISION items, PL/I `DECLARE`d structures). BMS screen maps (every field's position, length and attributes, `screen_field_data`) are the 3270 UI surface. These are the schema of the system: use them to trace which program runs which, which dataset a job binds, and the shape of the records that flow between them. Extracted by the engine (`core/mainframe_boundary.py`) and carried in the master DB (`call_site_data`/`dataset_data`/`record_data`); resolution to files is redone per scan.

- **Coverage:** `112` files carry mainframe facts -- `107` call sites, `71` dataset bindings, `3680` record items.

- **DB2 schemas:** `16` columns of `EXEC SQL DECLARE ... TABLE` (inline or DCLGEN members), full shape in `sql_table_data`.

- **DB2 table access:** `34` embedded SQL statements touching `10` tables (SELECT/INSERT/UPDATE/DELETE, cursors, host variables) in `sql_statement_data`; the program x table read/write matrix is `GalaxyIR.sql_table_access()`.

- **CICS resources:** `254` CSD `DEFINE` records (FILE→DSNAME, TDQUEUE, DB2TRAN→DB2ENTRY→PLAN, MAPSET, LIBRARY, ...), full attributes in `csd_resource_data`.

- **CICS operations:** `102` EXEC CICS operations naming a resource (`2` CONTAINER, `29` FILE, `60` MAP, `7` QUEUE, `4` WEB); verb, direction, VALUE-resolved name and INTO/FROM record in `cics_resource_data`.

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

### `tests/cobol_mainframe/port_invariance/cics-banking-sample-application-cbsa/cobol/INQACC.cbl` (COBOL)
- **Calls:** `LINK WS-ABEND-PGM`
- **COMMAREA passed:** `LINK ABNDPROC ← ABNDINFO-REC`
- **Record layouts (90 items):** `RETURNED-DATA (14)`, `HOST-ACCOUNT-ROW (13)`, `NCS-ACC-NO-STUFF (8)`, `DB2-DATE-REFORMAT (6)`, `WS-ORIG-DATE-GRP (6)`, `WS-ORIG-DATE-GRP-X (6)`, `WS-TIME-DATA (6)`, `WS-CICS-WORK-AREA (3)`, `DATA-STORE-TYPE (3)`, `ACCOUNT-KY (3)`, `ACCOUNT-KY2 (3)`, `EXIT-BROWSE-LOOP (1)` … (+18 more)
- **DB2 table access:** `ACCOUNT (read)`
- **Data moves:** 191 (INITIALIZE 9, MOVE 123, STRING 59); most-fed items `ABND-TIME`, `ABND-FREEFORM`, `ABND-DATE`, `ABND-RESP2CODE`, `ABND-RESPCODE`, `ABND-TASKNO-KEY`
- **Unit of work:** `0` commit / `1` rollback points; handlers `ABEND->ABEND-HANDLING`; `1/1` RESP results tested

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

### `tests/cobol_mainframe/port_invariance/cics-banking-sample-application-cbsa/cobol/DBCRFUN.cbl` (COBOL)
- **Calls:** `LINK WS-ABEND-PGM`
- **COMMAREA passed:** `LINK ABNDPROC ← ABNDINFO-REC`
- **Record layouts (88 items):** `HOST-ACCOUNT-ROW (14)`, `HOST-PROCTRAN-ROW (10)`, `WS-PASSED-DATA (7)`, `DB2-DATE-REFORMAT (6)`, `WS-ORIG-DATE-GRP (6)`, `WS-ORIG-DATE-GRP-X (6)`, `WS-TIME-DATA (6)`, `DATA-STORE-TYPE (4)`, `WS-CICS-WORK-AREA (3)`, `DESIRED-ACC-KEY (3)`, `SYSIDERR-RETRY (1)`, `FILE-RETRY (1)` … (+21 more)
- **DB2 table access:** `ACCOUNT (read/update)`, `PROCTRAN (insert)`
- **Compiler options:** `TRUNC(STD)`
- **Data moves:** 102 (COMPUTE 6, INITIALIZE 4, MOVE 66, STRING 26); most-fed items `ABND-TIME`, `ABND-FREEFORM`, `SQLCODE-DISPLAY`, `ABND-DATE`, `ABND-RESP2CODE`, `ABND-RESPCODE`
- **Unit of work:** `0` commit / `2` rollback points; handlers `ABEND->ABEND-HANDLING`; `2/2` RESP results tested

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

### `tests/cobol_mainframe/port_invariance/aws-mainframe-modernization-carddemo/cobol/CBTRN01C.cbl` (COBOL)
- **Calls:** `CALL CEE3ABD`
- **Datasets:** `DALYTRAN(INPUT)`, `CUSTFILE(INPUT)`, `XREFFILE(INPUT)`, `CARDFILE(INPUT)`, `ACCTFILE(INPUT)`, `TRANFILE(INPUT)`
- **Record layouts (55 items):** `FD-TRAN-RECORD⟵DALYTRAN-FILE (3)`, `FD-CUSTFILE-REC⟵CUSTOMER-FILE (3)`, `FD-XREFFILE-REC⟵XREF-FILE (3)`, `FD-CARDFILE-REC⟵CARD-FILE (3)`, `FD-ACCTFILE-REC⟵ACCOUNT-FILE (3)`, `FD-TRANFILE-REC⟵TRANSACT-FILE (3)`, `DALYTRAN-STATUS (3)`, `CUSTFILE-STATUS (3)`, `XREFFILE-STATUS (3)`, `CARDFILE-STATUS (3)`, `ACCTFILE-STATUS (3)`, `TRANFILE-STATUS (3)` … (+9 more)
- **Keyed files:** `CUSTOMER-FILE INDEXED/RANDOM key FD-CUST-ID`, `XREF-FILE INDEXED/RANDOM key FD-XREF-CARD-NUM`, `CARD-FILE INDEXED/RANDOM key FD-CARD-NUM`, `ACCOUNT-FILE INDEXED/RANDOM key FD-ACCT-ID`, `TRANSACT-FILE INDEXED/RANDOM key FD-TRANS-ID`
- **Data moves:** 78 (ADD 12, MOVE 63, READ 3); most-fed items `IO-STATUS`, `IO-STATUS-04`, `ACCT-ID`, `FD-ACCT-ID`, `FD-XREF-CARD-NUM`, `IO-STATUS-0403`

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

### `tests/cobol_mainframe/port_invariance/aws-mainframe-modernization-carddemo/cobol/COUSR03C.cbl` (COBOL)
- **Calls:** `RETURN TRANSID WS-TRANID`, `XCTL CDEMO-TO-PROGRAM`
- **COMMAREA passed:** `RETURN TRANSID CU03 ← CARDDEMO-COMMAREA`, `XCTL CDEMO-TO-PROGRAM ← CARDDEMO-COMMAREA`
- **Record layouts (24 items):** `WS-VARIABLES (22)`, `DFHCOMMAREA (2)`
- **CICS operations:** `MAP COUSR3A (read/write)`, `FILE USRSEC (delete/read)`
- **Data moves:** 71 (MOVE 68, STRING 3); most-fed items `ERRMSGC OF COUSR3AO`, `SEC-USR-ID`, `WS-MESSAGE`, `CARDDEMO-COMMAREA`, `CDEMO-FROM-PROGRAM`, `CDEMO-FROM-TRANID`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `2/3` RESP results tested

### `tests/cobol_mainframe/port_invariance/cics-banking-sample-application-cbsa/cobol/UPDCUST.cbl` (COBOL)
- **Record layouts (58 items):** `WS-PASSED-DATA (7)`, `DB2-DATE-REFORMAT (6)`, `WS-ORIG-DATE-GRP (6)`, `WS-ORIG-DATE-GRP-X (6)`, `WS-TIME-DATA (6)`, `WS-SORT-DIV (4)`, `WS-CICS-WORK-AREA (3)`, `DESIRED-CUST-KEY (3)`, `CUSTOMER-KY (3)`, `SYSIDERR-RETRY (1)`, `WS-CUST-DATA (1)`, `WS-EIBTASKN12 (1)` … (+11 more)
- **CICS operations:** `FILE CUSTOMER (read/update)`
- **Compiler options:** `TRUNC(STD)`
- **Data moves:** 40 (MOVE 39, UNSTRING 1); most-fed items `COMM-SCODE`, `CUSTOMER-ADDRESS OF WS-CUST-DATA`, `CUSTOMER-NAME OF WS-CUST-DATA`, `COMM-ADDR`, `COMM-CREDIT-SCORE`, `COMM-CS-REVIEW-DATE`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `2/2` RESP results tested

*(+92 more files with mainframe facts; full detail in `record_data`/`call_site_data`/`dataset_data`.)*

- **Mainframe skeleton completeness:** 59% (mean channel ratio; channel table in the audit report, section 7). Top missing inputs: application programs (source or load-module list) (67 gaps); BMS map sources (32 gaps); JCL and PROC libraries (12 gaps).

## 14. PROJECT IDIOM WRAPPERS (Hidden Literal Vocabulary)
> **AI CONTEXT:** Project-local helpers that wrap a literal primitive (print, abort, allocation). Their call sites are NOT in the literal signal counts above -- read a low `debug_prints`/`panics_and_aborts`/`memory_alloc` count together with this list. Full detail in `wrapper_data`.

- **`debug_prints`:** 133 literal sites + 20 sites through wrappers = 153
- **`memory_alloc`:** 0 literal sites + 2 sites through wrappers = 2
- **`panics_and_aborts`:** 64 literal sites + 38 sites through wrappers = 102

- `abend` (function, panics_and_aborts, primitive): 7 call sites in 1 files -- `tests/equivalence/carddemo-trnrpt/port/service/Cbtrn03cService.java`
- `refuse` (function, debug_prints, primitive): 6 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `refuse` (function, panics_and_aborts, primitive): 6 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `fail` (function, panics_and_aborts, primitive): 4 call sites in 1 files -- `tests/equivalence/carddemo-dailyval/port/service/Cbtrn01cService.java`
- `abendProgram` (function, panics_and_aborts, primitive): 3 call sites in 1 files -- `tests/equivalence/carddemo-readcard/port/service/Cbact02cService.java`
- `abendProgram` (function, panics_and_aborts, primitive): 3 call sites in 1 files -- `tests/equivalence/carddemo-readcust/port/service/Cbcus01cService.java`
- `abendProgram` (function, panics_and_aborts, primitive): 3 call sites in 1 files -- `tests/equivalence/carddemo-readxref/port/service/Cbact03cService.java`
- `fail` (function, debug_prints, primitive): 3 call sites in 1 files -- `tests/equivalence/db2/ggsqlrun.c`
- `fail` (function, panics_and_aborts, primitive): 3 call sites in 1 files -- `tests/equivalence/db2/ggsqlrun.c`
- `refuse` (function, debug_prints, primitive): 3 call sites in 1 files -- `tests/equivalence/le/cobdatft.c`
- `refuse` (function, panics_and_aborts, primitive): 3 call sites in 1 files -- `tests/equivalence/le/cobdatft.c`
- `_check_codec` (function, panics_and_aborts, primitive): 2 call sites in 1 files -- `tests/tools/equivalence_common.py`
*(+9 more in `wrapper_data`.)*

## 15. FUNCTION CALL RESOLUTION (Call Graph Confidence)
> **AI CONTEXT:** Each function's callee names, linked to the definition they most plausibly mean. *scoped* = same class/file, an imported file, or a class-qualified call; *unique* = the only definition in the repository; *ambiguous* = several candidates or an untyped receiver (never a graph edge); *external* = defined nowhere here (built-ins, packages). A high scoped/unique share means the resolver made a confident choice, not that the choice was correct; resolution accuracy is measured separately (gitgalaxy#3332). Detail in `fcall_data` / `fcall_rate_data`.

- **Repository:** 58790 call pairs -- scoped 29.2%, unique 0.0%, ambiguous 8.9%, external 61.9%

| Language | Pairs | Scoped | Unique | Ambiguous | External |
|---|---|---|---|---|---|
| python | 48541 | 28.9% | 0.0% | 7.9% | 63.2% |
| java | 9175 | 28.0% | 0.2% | 15.3% | 56.6% |
| c | 617 | 35.7% | 0.0% | 0.0% | 64.3% |
| cobol | 348 | 94.0% | 0.9% | 0.9% | 4.3% |
| javascript | 85 | 11.8% | 0.0% | 0.0% | 88.2% |
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
