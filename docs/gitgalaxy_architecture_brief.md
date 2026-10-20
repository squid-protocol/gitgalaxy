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
- **Scope:** 2055 analyzed artifact(s), 365313 LOC.
- **Load-bearing artifact:** `gitgalaxy/core/detector.py` -- 120 in-repo importer(s) depend on it. Changes here propagate furthest.
- **Top orchestrator:** `gitgalaxy/galaxyscope.py` -- pulls in 77 dependencies, the widest assembly point in the scan.
- **Heaviest artifact:** `gitgalaxy/core/detector.py` at magnitude 11448.64 (structural weight, not risk).
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
| Total Artifacts | 5280 |
| Analyzed Artifacts (Scanned) | 2055 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 3225 |
| Total LOC | 365313 |
| Volatility Index | 0.004 |
| % Scanned of codebase = | 38.9% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.7225 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.1809 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 2.7% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 3.2833 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 192 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 1280 | 289097 | 62.3% |
| PLAINTEXT | 219 | 0 | 10.7% |
| JAVA | 167 | 39863 | 8.1% |
| COBOL | 107 | 14210 | 5.2% |
| YAML | 59 | 5910 | 2.9% |
| MARKDOWN | 50 | 0 | 2.4% |
| HLASM | 30 | 651 | 1.5% |
| BINARY_THREAT | 28 | 28 | 1.4% |
| SQLITE | 25 | 2653 | 1.2% |
| C | 15 | 7694 | 0.7% |
| M4 | 13 | 32 | 0.6% |
| JCL | 13 | 449 | 0.6% |
| SHELL | 12 | 350 | 0.6% |
| PLI | 10 | 1425 | 0.5% |
| CSD | 8 | 1155 | 0.4% |
| BMS | 8 | 1471 | 0.4% |
| DB2_SQL | 6 | 110 | 0.3% |
| DOCKERFILE | 2 | 17 | 0.1% |
| CSV | 1 | 40 | 0.0% |
| XML | 1 | 0 | 0.0% |
| JAVASCRIPT | 1 | 158 | 0.0% |

## 4.1 SOURCE ENCODINGS
| Encoding | Decode | Files |
|---|---|---|
| utf-8 | utf-8 | 2027 |
| unknown | unknown | 28 |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Hub-Coupled Monorepo`
> **Architectural Drift Z-Score:** `3.607`
> **Composition Archetype:** `Hub-Coupled Monorepo` (z +3.61; from the repo's file-archetype mix)
> **File Composition:** Large Core Modules (2) 34%, Data / Markup / Trivial 22%, Large Core Modules (3) 12%, Declarative / Non-Code 8%, Encapsulated Accessors Files 6%
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 1758 | 85.5% |
| Unknown | 28 | 1.4% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 269 | 13.1% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 3225*

**Composition by Extension & Reason:**
- `.snap`: 777x Excluded (Unsupported Extension: '.snap'), 425x Unsupported Format (.snap)
- `.json`: 1034x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.md`: 668x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 467 LOC)
- `no_extension`: 160x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 3x Unsupported Format (.undeterminable)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.txt`: 1x Excluded (Machine-Generated Source Code Signature: 204 LOC), 1x Excluded (Machine-Generated Source Code Signature: 164 LOC), 1x Excluded (Machine-Generated Source Code Signature: 603 LOC)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 357 LOC), 1x Excluded (Saturation: Line 46 exceeds 500 chars)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.java`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.jsonl`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Saturation: Line 1 exceeds 500 chars)
- `.csv`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.css`: 3x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 85.5 | 2.4 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 100.0 | 4.3 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 97.1 | 0.3 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 2.7 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 61.7 | 0.7 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 100.0 | 0.1 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 4.3 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 86.9 | 0.1 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 6.6 | 0.1 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 63.3 | 1.0 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) _(coverage)_ | 0.0 | 100.0 | 0.9 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

> `Doc Surface (formerly Documentation Exposure)` is **documentation coverage, not a fragility driver**. It is reported for context beside program length, and is deliberately excluded from the ranked-file drivers in this brief: it measures the share of a file's unit weight a reader cannot recover from documentation, so on a codebase that documents little it sits near ceiling everywhere and describes the repo rather than distinguishing files within it.
> `Spec Alignment (formerly Specification Exposure)` was **not measured** on this scan and is therefore absent above rather than reported as 0 (which would assert full alignment). Enable it with `--spec-alignment` if this codebase uses the corresponding convention.

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 858 | 59 | 0 | `gitgalaxy/recorders/record_keeper.py` |
| cleanup | 25 | 11 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 1921 | 76 | 0 | `gitgalaxy/core/detector.py` |
| danger | 1497 | 75 | 0 | `gitgalaxy/core/detector.py` |
| concurrency | 48 | 14 | 0 | `gitgalaxy/core/detector.py` |
| connectivity | 403 | 75 | 0 | `gitgalaxy/core/detector.py` |
| io | 187 | 40 | 0 | `.claude/hooks/session-start.sh` |
| crypto | 3 | 3 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 38 | 5 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 50 | 3 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 527 | 49 | 0 | `gitgalaxy/core/detector.py` |
| events | 305 | 23 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 6 | 4 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 923 | 81 | 0 | `gitgalaxy/core/detector.py` |
| debt | 209 | 25 | 0 | `gitgalaxy/cobol_to_java_controller.py` |
| mutation | 17335 | 79 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 80 | 12 | 0 | `gitgalaxy/core/detector.py` |
| credential | 5 | 3 | 0 | `gitgalaxy/core/detector.py` |
| threat | 103 | 15 | 0 | `gitgalaxy/core/rule_prefilter.py` |
| ml_ai | 0 | 0 | 0 | - |
| ui | 1 | 1 | 0 | `gitgalaxy/recorders/llm_recorder.py` |

**Relations (repo medians):**
- `guard_balance_ratio` (guards / (danger + 1)): **0.0**
- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **0.0**

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `.claude/hooks/session-start.sh` (Hits: 45)
- `scripts/setup_java_toolchain.sh` (Hits: 17)
- `gitgalaxy/core/prefetch.py` (Hits: 16)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **detector.py** (`gitgalaxy/core/detector.py`) — 120 inbound connections
2. **source_text.py** (`gitgalaxy/core/source_text.py`) — 106 inbound connections
3. **__init__.py** (`gitgalaxy/tools/cobol_to_java/det/__init__.py`) — 105 inbound connections
4. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 80 inbound connections
5. **galaxy_ir.py** (`gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py`) — 78 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 77 outbound dependencies
2. **test_ai_ml_import_anchor_4150.py** (`tests/extraction/languages/test_ai_ml_import_anchor_4150.py`) — 69 outbound dependencies
3. **README.md** (`gitgalaxy/tools/cobol_to_java/README.md`) — 56 outbound dependencies
4. **BANK.csd** (`tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/etc/install/base/installjcl/BANK.csd`) — 54 outbound dependencies
5. **equivalence_cics.py** (`tests/tools/equivalence_cics.py`) — 38 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_translate` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_java/det/program.py`) -> Impact: **1399.5** | LOC: 802
- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1374.9** | LOC: 1411
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **924.6** | LOC: 1093
- `_translate_command` **(Many-Argument Workhorses)** (@ `tests/tools/equivalence_cics.py`) -> Impact: **758.2** | LOC: 485
  * *Intent:* """One EXEC CICS body -> the COBOL statements that replace it. `labels` are the program's HANDLE labels (handler_labels), which a condition or abend e...
- `Name the Db2 image cache entry (` **(Many-Argument Workhorses)** (@ `.github/workflows/det-sweep.yml`) -> Impact: **746.1** | LOC: 497
  * *Intent:* # #5262: the pinned image comes from actions/cache (key = its digest) so no shard asks icr.io; only main saves # (below), a pull request restores main...
- `score` **(Many-Argument Workhorses)** (@ `tests/tools/cobol_answer_key.py`) -> Impact: **745.4** | LOC: 748
- `Load or pull the pinned Db2 image in the background (` **(Many-Argument Workhorses)** (@ `.github/workflows/det-sweep.yml`) -> Impact: **735.4** | LOC: 484
  * *Intent:* # #5048: the pull is retried (bounded); a final failure is only logged here, the harness pulls again (pull_image). # The pull overlaps everything belo...
- `Load or build the oracle image, and check it against its pin (` **(Many-Argument Workhorses)** (@ `.github/workflows/det-sweep.yml`) -> Impact: **667.7** | LOC: 454
- `Start Db2 and create its databases in the background (` **(Many-Argument Workhorses)** (@ `.github/workflows/det-sweep.yml`) -> Impact: **640.7** | LOC: 432
  * *Intent:* # Db2 takes minutes to start and its databases to create (#4733): start them now, in the background, so they come # up while the JDK, Maven cache and ...
- `_command` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_java/det/cics.py`) -> Impact: **634.3** | LOC: 526

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `tests/cobol_mainframe` | 282 | 36128.82 | 18.28% | 0.0% |
| `gitgalaxy/core` | 62 | 35620.92 | 49.49% | 4.91% |
| `tests/extraction/languages` | 168 | 17168.04 | 12.97% | 0.0% |
| `tests/core_engine` | 131 | 15472.92 | 14.69% | 0.0% |
| `tests/equivalence/cics` | 6 | 10990.95 | 21.6% | 0.0% |
| `gitgalaxy/recorders` | 8 | 6862.06 | 47.65% | 4.01% |
| `tests/cics_crucible` | 26 | 5602.94 | 18.95% | 0.0% |
| `.github/workflows` | 43 | 4665.62 | 7.68% | 3.93% |
| `gitgalaxy` | 6 | 4468.0 | 37.93% | 1.6% |
| `gitgalaxy/metrics` | 7 | 3964.66 | 46.14% | 10.85% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `.github/ISSUE_TEMPLATE/parsing_discrepancy.yml` -> **97.0688%** Exposure
- `gitgalaxy/core/ebcdic_dbcs.py` -> **88.1655%** Exposure
- `gitgalaxy/core/rule_prefilter.py` -> **65.1355%** Exposure
- `gitgalaxy/core/runtime_options.py` -> **63.8183%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **53.2847%** Exposure
### Highest Mutation Surface (formerly State Flux; Mutation/Volatility)
- `.claude/hooks/pytest_quiet.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/aperture.py` -> **100.0%** Exposure
- `gitgalaxy/core/bms_screen_fields.py` -> **100.0%** Exposure
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
- **Binary Anomalies (X-Ray):** `1` (High entropy, packed payloads, or magic byte mismatches).
- **Blacklisted Dependencies:** `0` explicitly banned packages imported.
- **Unknown Dependencies:** `11403` packages imported that bypass the Zero-Trust whitelist.

## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)
> Ranked by Structural Magnitude: the file's structural weight and centralization within the system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not the vector percentages, is the actionable part.

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 11448.64 | **LOC:** 11036 | **CtrlFlow:** 44.0% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **120** in-repo importer(s); it depends on **20**; blast radius 11.962; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (66.4%)
- **Documentation Coverage:** 18.3871% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1374.9)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 580.7)
  * `splice` **(Many-Argument Workhorses)** (Impact: 477.5)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 254.5)
  * `_slice_by_indentation` **(Many-Argument Workhorses)** (Impact: 251.2)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 3 instances
* *Amplified Cascading Flux:* 1548 instances
* *Concurrency (weighted view):* 21
* *State Mutation (weighted view):* 4868
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 2457`, `structural_boundaries: 737`, `args: 140`, `func_start: 132`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 169`, `state_mutation: 1772`, `dead_code: 52`, `planned_debt: 2`, `fragile_debt: 25`
* *Architecture:* `api: 25`, `concurrency: 6`, `import: 24`
* *Defense:* `safety: 51`, `doc: 129`, `immutability_locks: 55`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 11.962
  * `Choke Point (Betweenness):` 0.001459 | `Ripple Effect (Closeness):` 0.055309
  * `Imports (Out-Degree: 9):` bisect, collections, functools, gitgalaxy.core.cobol_source_format, gitgalaxy.core.fortran_calls, gitgalaxy.core.network_risk_sensor, gitgalaxy.core.prism, gitgalaxy.core.rule_prefilter...
  * `Imported By (In-Degree: 120):` (Excluded from Brief to save tokens)

### `tests/equivalence/cics/ggcics.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 8960.3 | **LOC:** 5076 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **14**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGCWCNV` **(Many-Argument Workhorses)** (Impact: 310.4)
    * *Intent:* /* WEB CONVERSE: GG-NUM the METHOD CVDA (out: STATUSCODE), GG-HOURS PATHLENGTH, GG-MINS QUERYSTRLEN,...
  * `GGCWPRS` **(Many-Argument Workhorses)** (Impact: 257.1)
  * `web_send_body` **(Many-Argument Workhorses)** (Impact: 208.6)
  * `GGCTCPX` **(Many-Argument Workhorses)** (Impact: 156.8)
    * *Intent:* /* GG-LEN CADDRLENGTH, GG-HOURS CNAMELENGTH, GG-MINS SADDRLENGTH, GG-SECS SNAMELENGTH (each in, 0 wh...
  * `GGCSTRT` **(Many-Argument Workhorses)** (Impact: 133.7)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` ctype.h, direct.h, ggcics_containers.c, ggcics_filecontrol.c, ggcics_spec.h, signal.h, stdio.h, stdlib.h...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 3800.76 | **LOC:** 2389 | **CtrlFlow:** 41.9% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **11** in-repo importer(s); it depends on **16**; blast radius 0.96; role: Transceiver (Middle-Tier)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 0.96
  * `Choke Point (Betweenness):` 1.8e-05 | `Ripple Effect (Closeness):` 0.011445
  * `Imports (Out-Degree: 5):` collections, gitgalaxy.core.call_resolver, gitgalaxy.core.compiler_options, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.standards, heapq, hops...
  * `Imported By (In-Degree: 11):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3432.6 | **LOC:** 4536 | **CtrlFlow:** 26.8% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **26** in-repo importer(s); it depends on **77**; blast radius 2.304; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.1%), Complexity Load (formerly Cognitive Load) (80.3%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 19.4805% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 272.8)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 183.4)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `_process_file_worker` **(Many-Argument Workhorses)** (Impact: 170.2)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `main` **(I/O & Config Routines)** (Impact: 118.5)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
  * `_calculate_risk_exposures` **(Many-Argument Workhorses)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 546 instances
* *Concurrency (weighted view):* 17
* *State Mutation (weighted view):* 1870
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 750`, `structural_boundaries: 375`, `args: 62`, `func_start: 50`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 152`, `high_risk_execution: 2`, `state_mutation: 778`, `dead_code: 1`
* *Architecture:* `io: 14`, `api: 17`, `concurrency: 7`, `import: 89`
* *Defense:* `safety: 65`, `doc: 42`, `test: 2`, `immutability_locks: 12`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.304
  * `Choke Point (Betweenness):` 0.000917 | `Ripple Effect (Closeness):` 0.012982
  * `Imports (Out-Degree: 49):` argparse, collections, concurrent.futures, copy, datetime, extraction, functools, gitgalaxy.core.aperture...
  * `Imported By (In-Degree: 26):` (Excluded from Brief to save tokens)

### `.github/workflows/det-sweep.yml` (YAML | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 3397.32 | **LOC:** 708 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **8**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `Name the Db2 image cache entry (` **(Many-Argument Workhorses)** (Impact: 746.1)
    * *Intent:* # #5262: the pinned image comes from actions/cache (key = its digest) so no shard asks icr.io; only ...
  * `Load or pull the pinned Db2 image in the background (` **(Many-Argument Workhorses)** (Impact: 735.4)
    * *Intent:* # #5048: the pull is retried (bounded); a final failure is only logged here, the harness pulls again...
  * `Load or build the oracle image, and check it against its pin (` **(Many-Argument Workhorses)** (Impact: 667.7)
  * `Start Db2 and create its databases in the background (` **(Many-Argument Workhorses)** (Impact: 640.7)
    * *Intent:* # Db2 takes minutes to start and its databases to create (#4733): start them now, in the background,...
  * `Save the pinned Db2 image to the cache (main only,` **(Many-Argument Workhorses)** (Impact: 507.1)
    * *Intent:* # #5262: the cache writer is main's runs (schedule / dispatch on main), one shard, and only on a mis...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` restore@55cc8345863c7cc4c66a329aec7e433d2d1c52a9, save@55cc8345863c7cc4c66a329aec7e433d2d1c52a9, cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9, checkout@3d3c42e5aac5ba805825da76410c181273ba90b1, download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333, setup-java@de7274f081f381c8f8158605e0321c36c376e2e6, setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97, upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/mainframe_boundary.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2904.7 | **LOC:** 2701 | **CtrlFlow:** 41.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **54** in-repo importer(s); it depends on **30**; blast radius 6.499; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.7%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (55.8%)
- **Documentation Coverage:** 11.6438% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_cobol_records` **(Many-Argument Workhorses)** (Impact: 319.9)
  * `_cobol_calls` **(Stateful Encapsulated Methods)** (Impact: 159.8)
    * *Intent:* """Every COBOL invocation site: `CALL`, and CICS `LINK`/`XCTL PROGRAM(...)`. `cics_only` (#3495) rea...
  * `_pli_item_attributes` **(Compute Cores)** (Impact: 72.8)
    * *Intent:* """The record_data fields of one item from its attribute tokens, or None when the declaration is not...
  * `_pli_records` **(Stateful Encapsulated Methods)** (Impact: 56.5)
    * *Intent:* """The DECLAREd data items of one PL/I file as a record tree (#3250). Same flat, source-ordered shap...
  * `_jcl_boundary` **(Compute Cores)** (Impact: 49.0)
    * *Intent:* """JCL `EXEC PGM=` steps and the `DD` statements that bind a ddname to a dataset. #3345: alongside t...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 449 instances
* *State Mutation (weighted view):* 1439
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 705`, `structural_boundaries: 282`, `args: 79`, `func_start: 71`
* *Risk/State:* `safety_bypasses: 94`, `state_mutation: 541`, `dead_code: 2`, `duplicate_logic: 11`
* *Architecture:* `api: 2`, `import: 31`
* *Defense:* `safety: 3`, `doc: 57`, `immutability_locks: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 6.499
  * `Choke Point (Betweenness):` 0.002922 | `Ripple Effect (Closeness):` 0.080853
  * `Imports (Out-Degree: 25):` bisect, gitgalaxy.core.bms_screen_fields, gitgalaxy.core.call_using, gitgalaxy.core.cics_macro_tables, gitgalaxy.core.cics_resources, gitgalaxy.core.cics_tasks, gitgalaxy.core.cobol_preprocessor, gitgalaxy.core.compiler_options...
  * `Imported By (In-Degree: 54):` (Excluded from Brief to save tokens)

### `tests/cics_crucible/test_cics_runtimes.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 2462.82 | **LOC:** 6632 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **13**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_cics_task_sends_a_container_as_the_stub_does` **(Defensive Guards)** (Impact: 40.8)
    * *Intent:* """#5037 (X37): CicsTask.webSendContainer answers the steps above as the stub does and refuses what ...
  * `_sched_stub` **(Type Conversions)** (Impact: 35.2)
    * *Intent:* """The stub runs `steps` (the parent EIBTASKN 100); its lines with RESP by name, a refusal as REFUSE...
  * `test_cics_task_defines_queries_and_wraps_a_doubleword_counter_as_the_stub_does` **(Defensive Guards)** (Impact: 35.0)
    * *Intent:* """#4770 zECS (X45): CicsTask.defineDcounter / queryDcounter / getCounter(.., wrap) answer the scena...
  * `test_cics_task_defines_queries_and_wraps_a_fullword_counter_as_the_stub_does` **(Defensive Guards)** (Impact: 31.8)
    * *Intent:* """#5039 (X50): CicsTask.defineCounter / queryCounter / getCounter(.., wrap) answer the scenarios ab...
  * `_x35_java_steps` **(Stateful Encapsulated Methods)** (Impact: 28.4)
    * *Intent:* """The Java statements for the steps above, printing as the stub's main does."""
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` atexit, cics_crucible, equivalence_cics, functools, gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge, os, pathlib, pytest...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

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

### `tests/cobol_mainframe/test_det_translate.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 2238.68 | **LOC:** 3652 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **18**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_deleteq_ts_and_inquire_association_and_the_receive_map_terminal_option` **(Defensive Guards)** (Impact: 30.6)
    * *Intent:* """#4415 slice 2 (register X29), IBM EXEC CICS DELETEQ TS / INQUIRE ASSOCIATION / RECEIVE MAP: DELET...
  * `test_web_open_converse_close_are_the_tasks_http_client` **(Defensive Guards)** (Impact: 21.7)
    * *Intent:* """#4767 zECS (register X35), IBM WEB OPEN / WEB CONVERSE / WEB CLOSE: OPEN by URIMAP or HOST / HOST...
  * `test_web_browse_forms_are_the_requests_pairs` **(Defensive Guards)** (Impact: 19.9)
    * *Intent:* """#4940 (register X38), IBM WEB STARTBROWSE / READNEXT / ENDBROWSE HTTPHEADER, FORMFIELD, QUERYPARM...
  * `test_inquire_urimap_direct_form_and_inquire_program_status` **(Defensive Guards)** (Impact: 17.0)
    * *Intent:* """#4768 zECS (register X34). IBM INQUIRE URIMAP, the direct form: URIMAP(name) with no browse optio...
  * `test_an_abbreviated_combined_condition_with_not_before_a_line_break_translates` **(Defensive Guards)** (Impact: 16.2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` __future__, com.x., com.x.entity.vsam., contextlib, decimal, gitgalaxy.tools.cobol_to_cobol.galaxy_ir, gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge, gitgalaxy.tools.cobol_to_java.det...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 2126.82 | **LOC:** 2275 | **CtrlFlow:** 27.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **13** in-repo importer(s); it depends on **12**; blast radius 1.195; role: Transceiver (Middle-Tier)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.195
  * `Choke Point (Betweenness):` 1.7e-05 | `Ripple Effect (Closeness):` 0.011917
  * `Imports (Out-Degree: 4):` collections.abc, gitgalaxy.core.function_population, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math...
  * `Imported By (In-Degree: 13):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2046.16 | **LOC:** 1673 | **CtrlFlow:** 46.0% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **19** in-repo importer(s); it depends on **19**; blast radius 2.807; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (53.3%)
- **Documentation Coverage:** 23.4694% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_target_unguarded` **(Many-Argument Workhorses)** (Impact: 220.0)
  * `_resolve_by_name` **(Many-Argument Workhorses)** (Impact: 156.2)
  * `_resolve_in_libraries` **(Many-Argument Workhorses)** (Impact: 87.8)
  * `_resolve_edges` **(Many-Argument Workhorses)** (Impact: 70.3)
    * *Intent:* """ #2992: resolves every file's raw_imports into directed file-to-file edges, keyed (importer, impo...
  * `build_dependency_graph` **(Many-Argument Workhorses)** (Impact: 68.8)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 251 instances
* *State Mutation (weighted view):* 779
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 448`, `structural_boundaries: 204`, `args: 43`, `func_start: 42`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 52`, `high_risk_execution: 1`, `state_mutation: 277`, `dead_code: 5`
* *Architecture:* `io: 5`, `api: 8`, `import: 17`
* *Defense:* `safety: 14`, `doc: 38`, `immutability_locks: 10`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.807
  * `Choke Point (Betweenness):` 0.001222 | `Ripple Effect (Closeness):` 0.04399
  * `Imports (Out-Degree: 8):` collections, gitgalaxy.core.copy_libraries, gitgalaxy.core.graph_engine, gitgalaxy.core.invocation_resolver, gitgalaxy.core.package_self_reference, gitgalaxy.core.path_proximity, gitgalaxy.core.rust_modules, gitgalaxy.core.unicode_paths...
  * `Imported By (In-Degree: 19):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 2018.3 | **LOC:** 2058 | **CtrlFlow:** 35.7% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **58** in-repo importer(s); it depends on **5**; blast radius 4.607; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (46.5%)
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
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.607
  * `Choke Point (Betweenness):` 2.4e-05 | `Ripple Effect (Closeness):` 0.050815
  * `Imports (Out-Degree: 1):` gitgalaxy.core.cobol_source_format, gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 58):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1781.42 | **LOC:** 1633 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **9**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 419.7)
  * `_tier_4_heuristic_discovery` **(Many-Argument Workhorses)** (Impact: 146.2)
    * *Intent:* # ========================================================================= # THE TIER 4 HEURISTIC D...
  * `_evaluate_ecosystem_gravity` **(Many-Argument Workhorses)** (Impact: 103.9)
  * `_tier_3_lexical_scan` **(Many-Argument Workhorses)** (Impact: 76.7)
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

### `tests/cics_crucible/ports/pc-wizard/PCCONF/overlay/cobolrt/Cobol.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 1636.42 | **LOC:** 1657 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 65.5)
    * *Intent:* /** * INSPECT target with its phrases in the order written. The phrases act on the original text; wi...
  * `unstring` **(Many-Argument Workhorses)** (Impact: 55.2)
    * *Intent:* /** * UNSTRING src [DELIMITED BY delims] INTO intos... [WITH POINTER pointer] [TALLYING IN tallying]...
  * `isNumeric` **(Compute Cores)** (Impact: 54.3)
    * *Intent:* // [rule RT-CBL-CLASS-NUMERIC]
  * `alnumToDisplay` **(Stateful Encapsulated Methods)** (Impact: 46.0)
    * *Intent:* /** * An alphanumeric item MOVEd into a zoned (USAGE DISPLAY) numeric one, as libcob 3 (cob_move_alp...
  * `moveBytes` **(Stateful Encapsulated Methods)** (Impact: 37.3)
    * *Intent:* // [rule RT-CBL-MOVE-ELEMENTARY]
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` java.math.BigDecimal, java.math.BigInteger, java.math.RoundingMode, java.nio.charset.Charset, java.util.ArrayList, java.util.Arrays, java.util.List
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cics_crucible/ports/pc-return-immediate/PCIMMA/overlay/cobolrt/Cobol.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 1608.38 | **LOC:** 1583 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 65.5)
    * *Intent:* /** * INSPECT target with its phrases in the order written. The phrases act on the original text; wi...
  * `unstring` **(Many-Argument Workhorses)** (Impact: 55.2)
    * *Intent:* /** * UNSTRING src [DELIMITED BY delims] INTO intos... [WITH POINTER pointer] [TALLYING IN tallying]...
  * `isNumeric` **(Compute Cores)** (Impact: 54.3)
  * `alnumToDisplay` **(Stateful Encapsulated Methods)** (Impact: 46.0)
    * *Intent:* /** * An alphanumeric item MOVEd into a zoned (USAGE DISPLAY) numeric one, as libcob 3 (cob_move_alp...
  * `moveBytes` **(Stateful Encapsulated Methods)** (Impact: 37.2)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` java.math.BigDecimal, java.math.BigInteger, java.math.RoundingMode, java.nio.charset.Charset, java.util.ArrayList, java.util.Arrays, java.util.List
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cobol_mainframe/test_equivalence_cics.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1549.34 | **LOC:** 2724 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **17**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_formattime_day_of_year_and_binary_forms_under_gnucobol_equal_the_java_runtime` **(Defensive Guards)** (Impact: 15.9)
    * *Intent:* """#4415 slice 3 (X46): the translated COBOL, run under GnuCOBOL at the six instants test_cics_runti...
  * `test_the_generated_test_runs_runtask_unless_the_facade_side_is_asked_for` **(Defensive Guards)** (Impact: 13.9)
    * *Intent:* """The runTask side is the default (-Dequivalence.facades unset) and runs as before; the facade side...
  * `test_a_scenario_states_its_own_records_for_a_dataset_of_the_case` **(Defensive Guards)** (Impact: 13.8)
    * *Intent:* """#4622: `scenario_datasets` is each overridden DD's spec with the scenario's `input` / `append`, t...
  * `test_a_case_states_the_installed_urimaps_on_both_sides` **(Defensive Guards)** (Impact: 13.7)
    * *Intent:* """#4270 zECS (X32): INQUIRE URIMAP browses the definitions the run states -- a scenario's (else the...
  * `test_a_carddemo_hand_ports_send_text_carries_the_erase_freekb_its_cobol_passes` **(Defensive Guards)** (Impact: 13.4)
    * *Intent:* """#5440: every CardDemo SEND TEXT ends ERASE FREEKB; #5412 compares the options, so a port that dro...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` base64, decimal, equivalence, equivalence_cics, equivalence_java, gitgalaxy.standards.cics.commands, gitgalaxy.standards.cics.resp, gitgalaxy.tools.cobol_to_cobol.galaxy_ir...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/call_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 1424.38 | **LOC:** 1545 | **CtrlFlow:** 34.8% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **11** in-repo importer(s); it depends on **3**; blast radius 2.086; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (96.5%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (59.2%)
- **Documentation Coverage:** 21.9298% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `resolve_calls` **(Many-Argument Workhorses)** (Impact: 216.0)
  * `_resolve_one` **(Many-Argument Workhorses)** (Impact: 197.1)
  * `_visible_receiver` **(Stateful Encapsulated Methods)** (Impact: 37.2)
    * *Intent:* """An untyped receiver (`x.save()`): confident only when exactly ONE visible class defines the metho...
  * `_index` **(Type Conversions)** (Impact: 32.9)
    * *Intent:* """(link group, name key) -> every definition of that name, in scan order. Functions and classes sha...
  * `_constructor_of` **(Stateful Encapsulated Methods)** (Impact: 31.2)
    * *Intent:* """The constructor method of class definition `cls`, if the scan extracted one. One in the class's o...
**Contextual Mitigations & Amplifications:**
* *Mitigated Danger:* 1 instances
* *Amplified Cascading Flux:* 155 instances
* *High Risk Execution (weighted view):* 2
* *State Mutation (weighted view):* 498
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 381`, `structural_boundaries: 168`, `args: 51`, `func_start: 44`, `class_start: 4`
* *Risk/State:* `safety_bypasses: 38`, `high_risk_execution: 3`, `state_mutation: 188`, `dead_code: 4`
* *Architecture:* `io: 1`, `api: 13`, `import: 3`
* *Defense:* `safety: 5`, `doc: 30`, `immutability_locks: 24`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 2.086
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.021532
  * `Imports (Out-Degree: 0):` collections, posixpath, typing
  * `Imported By (In-Degree: 11):` (Excluded from Brief to save tokens)

### `tests/cobol_mainframe/test_galaxy_ir.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1319.84 | **LOC:** 2449 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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

### `gitgalaxy/core/aperture.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1231.38 | **LOC:** 1331 | **CtrlFlow:** 33.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **21** in-repo importer(s); it depends on **9**; blast radius 2.159; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.2%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (62.1%)
- **Documentation Coverage:** 18.0851% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_check_artifact_integrity` **(Many-Argument Workhorses)** (Impact: 139.8)
  * `_check_ignore_rules` **(Many-Argument Workhorses)** (Impact: 55.2)
    * *Intent:* """ Determines if the path is in a blocked, ignored, or dynamically infected sector. Implements stan...
  * `evaluate_path_integrity` **(Many-Argument Workhorses)** (Impact: 50.9)
    * *Intent:* """ [GATE 1: Perimeter Gating (Zero-I/O Path Evaluation)] Performs high-speed path analysis to build...
  * `_has_definitions` **(Many-Argument Workhorses)** (Impact: 50.4)
    * *Intent:* """#5460: True when the file carries `need` function definitions outside any data table. The payload...
  * `is_in_scope` **(Many-Argument Workhorses)** (Impact: 36.2)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 170 instances
* *State Mutation (weighted view):* 557
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 280`, `structural_boundaries: 200`, `args: 37`, `func_start: 37`, `class_start: 7`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 217`
* *Architecture:* `io: 9`, `api: 15`, `import: 9`
* *Defense:* `safety: 22`, `doc: 35`, `sync_locks: 2`, `immutability_locks: 24`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 2.159
  * `Choke Point (Betweenness):` 5.8e-05 | `Ripple Effect (Closeness):` 0.02557
  * `Imports (Out-Degree: 3):` fnmatch, gitgalaxy.core.model_magic, gitgalaxy.core.source_text, gitgalaxy.standards.gitgalaxy_config, logging, os, pathlib, re...
  * `Imported By (In-Degree: 21):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1169.46 | **LOC:** 3073 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
- **Magnitude:** 1106.7 | **LOC:** 1169 | **CtrlFlow:** 24.5% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **8** in-repo importer(s); it depends on **10**; blast radius 0.735; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (96.8%), Complexity Load (formerly Cognitive Load) (85.5%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 26.4706% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `generate_report` **(Many-Argument Workhorses)** (Impact: 353.1)
  * `_mainframe_facts_block` **(Many-Argument Workhorses)** (Impact: 191.0)
    * *Intent:* """The Named System Facts for one file (#3200/#3201/#3246/#3250/#3344/#3356), or {} if none. The for...
  * `descale` **(Defensive Guards)** (Impact: 14.1)
    * *Intent:* """Dynamically scales integers back to floats using a fixed-string check."""
  * `_completeness_block` **(Stateful Encapsulated Methods)** (Impact: 8.3)
    * *Intent:* """#3506: GalaxyIR.completeness() in the audit's labelled style -- the score, each channel's resolve...
  * `format_label` **(Generic / Templated Code)** (Impact: 7.6)
    * *Intent:* """Translates raw dictionary keys into descriptive human-readable labels."""
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Cascading Flux:* 155 instances
* *State Mutation (weighted view):* 490
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 222`, `structural_boundaries: 41`, `args: 15`, `func_start: 9`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 18`, `state_mutation: 180`
* *Architecture:* `io: 3`, `api: 7`, `import: 10`
* *Defense:* `safety: 10`, `doc: 7`, `sync_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 0.735
  * `Choke Point (Betweenness):` 1e-05 | `Ripple Effect (Closeness):` 0.010524
  * `Imports (Out-Degree: 3):` argparse, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.standards, json, logging, os, pathlib...
  * `Imported By (In-Degree: 8):` (Excluded from Brief to save tokens)

### `tests/equivalence/cics/ggcics_filecontrol.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1095.14 | **LOC:** 573 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `browse_read` **(Many-Argument Workhorses)** (Impact: 127.6)
    * *Intent:* /* READNEXT (dir 1) / READPREV (dir -1) FILE(name1) INTO RIDFLD. */
  * `GGCREAD` **(Many-Argument Workhorses)** (Impact: 119.1)
  * `GGCDELT` **(Many-Argument Workhorses)** (Impact: 112.7)
    * *Intent:* /* DELETE FILE(name1) [RIDFLD]: the record with that key, or (no RIDFLD: GG-FLAGS 'HELD') the one a ...
  * `rba_read` **(Many-Argument Workhorses)** (Impact: 101.4)
    * *Intent:* /* READNEXT (dir 1) / READPREV (dir -1) ... RBA: GG-FLAGS 'RBA'; the browse is an RBA browse. */
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
  * `Imports (Out-Degree: 0):` None
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/security/manifest_parser.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1062.76 | **LOC:** 752 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **6**
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
  * `Imports (Out-Degree: 0):` gitgalaxy.core.source_text, json, logging, os, pathlib, re
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/recorders/record_keeper.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1056.52 | **LOC:** 3866 | **CtrlFlow:** 21.5% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **43** in-repo importer(s); it depends on **13**; blast radius 3.692; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (92.7%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (46.2%)
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
* *Structure:* `branch: 408`, `structural_boundaries: 85`, `args: 34`, `func_start: 16`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 303`, `dead_code: 5`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 5`, `import: 13`
* *Defense:* `safety: 31`, `doc: 65`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 3.692
  * `Choke Point (Betweenness):` 7e-05 | `Ripple Effect (Closeness):` 0.022755
  * `Imports (Out-Degree: 6):` gitgalaxy.core.call_resolver, gitgalaxy.core.fact_channels, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.metrics.archetype_parity, gitgalaxy.standards.analysis_lens, json, logging...
  * `Imported By (In-Degree: 43):` (Excluded from Brief to save tokens)

### `tests/equivalence/carddemo-cardlist/port/service/CocrdlicService.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 1049.6 | **LOC:** 1073 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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

## 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 12.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/galaxyscope.py` -> Churn: **63.32%** | Cog Load: 80.2816% | Debt: 0.0%
- `gitgalaxy/core/detector.py` -> Churn: **57.82%** | Cog Load: 66.3698% | Debt: 14.1614%
- `gitgalaxy/core/mainframe_boundary.py` -> Churn: **52.54%** | Cog Load: 55.8011% | Debt: 29.9835%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 11448.64
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3800.76
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3432.6
- `gitgalaxy/core/mainframe_boundary.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2904.7
- `gitgalaxy/metrics/signal_processor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2126.82

## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 0.292** (Bridge: 0.0029 * Flux: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py` -> **Severity: 0.187** (Bridge: 0.0019 * Flux: 100.0%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.146** (Bridge: 0.0015 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.122** (Bridge: 0.0012 * Flux: 100.0%)
- `gitgalaxy/core/invocation_resolver.py` -> **Severity: 0.093** (Bridge: 0.0009 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/core/source_text.py` -> **Severity: 14.191** (Embedded: 0.1494 * Error Risk: 95.0099%)
- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 10.804** (Embedded: 0.1088 * Error Risk: 99.3102%)
- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 10.32** (Embedded: 0.1046 * Error Risk: 98.6853%)
- `gitgalaxy/core/compiler_options.py` -> **Severity: 8.903** (Embedded: 0.0899 * Error Risk: 99.0522%)
- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 8.065** (Embedded: 0.0809 * Error Risk: 99.7463%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 1226.0** (Blast Radius: 12.26 * Doc Risk: 100.0%)
- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 1163.168** (Blast Radius: 28.433 * Doc Risk: 40.9091%)
- `gitgalaxy/tools/cobol_to_java/det/cobolrt/Field.java` -> **Severity: 815.9** (Blast Radius: 16.318 * Doc Risk: 50.0%)
- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 754.24** (Blast Radius: 18.856 * Doc Risk: 40.0%)
- `gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java` -> **Severity: 581.153** (Blast Radius: 17.661 * Doc Risk: 32.906%)

## 13. MAINFRAME SYSTEM FACTS (Named Relations & Record Layouts)
> **AI CONTEXT:** Named mainframe relations the structural signal counts flatten -- the call graph (`CALL`/CICS `LINK`·`XCTL`/JCL `EXEC PGM=`), the dataset boundary (`SELECT…ASSIGN` + `OPEN` modes, JCL `DD`→dataset), and record layouts (COBOL DATA DIVISION items, PL/I `DECLARE`d structures). BMS screen maps (every field's position, length and attributes, `screen_field_data`) are the 3270 UI surface. These are the schema of the system: use them to trace which program runs which, which dataset a job binds, and the shape of the records that flow between them. Extracted by the engine (`core/mainframe_boundary.py`) and carried in the master DB (`call_site_data`/`dataset_data`/`record_data`); resolution to files is redone per scan.

- **Coverage:** `147` files carry mainframe facts -- `186` call sites, `89` dataset bindings, `4116` record items.

- **DB2 schemas:** `23` columns of `EXEC SQL DECLARE ... TABLE` (inline or DCLGEN members), full shape in `sql_table_data`.

- **DB2 table access:** `85` embedded SQL statements touching `13` tables (SELECT/INSERT/UPDATE/DELETE, cursors, host variables) in `sql_statement_data`; the program x table read/write matrix is `GalaxyIR.sql_table_access()`.

- **CICS resources:** `263` CSD `DEFINE` records (FILE→DSNAME, TDQUEUE, DB2TRAN→DB2ENTRY→PLAN, MAPSET, LIBRARY, ...), full attributes in `csd_resource_data`.

- **CICS operations:** `140` EXEC CICS operations naming a resource (`10` CHANNEL, `29` CONTAINER, `30` FILE, `60` MAP, `7` QUEUE, `4` WEB); verb, direction, VALUE-resolved name and INTO/FROM record in `cics_resource_data`.

- **CICS task control:** `19` commands (`6` DELAY, `5` FETCH CHILD, `7` RUN, `1` START); child transid (or its STRING-built pattern), channel, CHILD/REQID token and timing in `cics_task_data`.

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

### `tests/equivalence/ims/fixture/DLILVL.cbl` (COBOL)
- **Calls:** `CALL CBLTDLI`
- **Record layouts (72 items):** `PCB1 (10)`, `PCB2 (10)`, `Q-DEPT (6)`, `Q-EMP (6)`, `Q-SAL (6)`, `Q-NAME (6)`, `Q-NOFLD (6)`, `IOA-EMP (5)`, `W-STEP (1)`, `W-LEN (1)`, `W-KFB (1)`, `W-IO (1)` … (+13 more)
- **Data moves:** 65 (ADD 2, MOVE 63); most-fed items `W-LEN`, `W-IO`, `W-KFB`
- **IMS DL/I:** `F-GU Q-DEPT`, `F-GNP`, `F-GN S-DEPT`, `F-GN`, `F-GU Q-DEPT,Q-EMP`, `F-GU Q-DEPT,Q-SAL`, `F-GU Q-DEPT,Q-NAME`, `F-GU S-DEPT,Q-EMP`, `F-GNP S-SKILL`, `F-ISRT Q-DEPT,S-EMP`, `F-ISRT S-DEPT`, `F-GHU Q-DEPT,Q-EMP`, `F-REPL`, `F-DLET`, `F-GU S-NOSEG`, `F-GU S-DEPT,Q-NOFLD`, `F-BAD`, `F-GU`

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

### `tests/cobol_mainframe/refraction_excerpts/cics-async-api-credit-card-application-example/src/ASYNCPNT.cbl` (COBOL)
- **Calls:** `RUN TRANSID CREDIT-CHECK-TRAN`, `RUN TRANSID GET-ADDR-TRAN`, `RUN TRANSID CSSTATUS-TRAN`, `RUN TRANSID GET-NAME-TRAN`, `RUN TRANSID DB-CACHE-TRAN`
- **Record layouts (87 items):** `PRINT-LINE (26)`, `CONTAINER-NAMES (8)`, `TRANSIDS (8)`, `CHILD-TOKENS (8)`, `RETURN-CHANNELS (8)`, `RETURN-DATA (7)`, `PROG-NAMES (6)`, `READ-INPUT (4)`, `ACCOUNT-NUMBER-IN (2)`, `APPLICATION-SUCCESS (1)`, `APPLICATION-FAILED (1)`, `READ-INPUT-LENGTH (1)` … (+7 more)
- **CICS operations:** `CONTAINER INPUTCONTAINER (write)`, `CHANNEL MYCHANNEL (pass)`, `CONTAINER CREDITCHECKCONT (read)`, `CONTAINER GETNAMECONTAINER (read)`, `CONTAINER GETVIPSTATUS (read)`, `CONTAINER GETADDRCONTAINER (read)`, `CONTAINER GETPOSTCODE (read)`, `CONTAINER ASYNCPNT (read/write)`
- **CICS task control:** `RUN ICCK`, `RUN GETA`, `RUN STUS`, `RUN GETN`, `FETCH CHILD`, `RUN UPDB`
- **Compiler options:** `TRUNC(STD)`
- **Data moves:** 15 (MOVE 15); most-fed items `ACCOUNT-NUM`, `APPLICATION-RESULT`, `CUST-NO-IN`, `RESULT-TEXT`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `0/9` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/cics-genapp/base/src/lgtestp1.cbl` (COBOL)
- **Calls:** `LINK LGIPOL01`, `LINK LGAPOL01`, `LINK LGDPOL01`, `LINK LGUPOL01`, `RETURN TRANSID SSP1`
- **COMMAREA passed:** `LINK LGIPOL01 ← COMM-AREA LENGTH(32500)`, `LINK LGAPOL01 ← COMM-AREA LENGTH(32500)`, `LINK LGDPOL01 ← COMM-AREA LENGTH(32500)`, `LINK LGUPOL01 ← COMM-AREA LENGTH(32500)`, `RETURN TRANSID SSP1 ← COMM-AREA`
- **Record layouts (2 items):** `MSGEND (1)`, `COMM-AREA (1)`
- **CICS operations:** `MAP SSMAPP1 (read/write)`
- **Data moves:** 101 (INITIALIZE 7, MOVE 94); most-fed items `CA-CUSTOMER-NUM`, `CA-POLICY-NUM`, `CA-EXPIRY-DATE`, `CA-ISSUE-DATE`, `CA-M-ACCIDENTS`, `CA-M-CC`
- **Unit of work:** `0` commit / `2` rollback points; handlers `MAPFAIL->ENDIT`; `0/0` RESP results tested

### `tests/cobol_mainframe/refraction_excerpts/cics-async-api-credit-card-application-example/src/SEQPNT.cbl` (COBOL)
- **Calls:** `LINK CREDIT-CHECK`, `LINK GET-NAME`, `LINK GET-ADDR`, `LINK CSSTATUS`, `LINK DB-CACHE`
- **Record layouts (61 items):** `PRINT-LINE (26)`, `CONTAINER-NAMES (8)`, `RETURN-DATA (7)`, `PROG-NAMES (6)`, `READ-INPUT (4)`, `ACCOUNT-NUMBER-IN (2)`, `APPLICATION-SUCCESS (1)`, `APPLICATION-FAILED (1)`, `READ-INPUT-LENGTH (1)`, `IS-TERMINAL-BASED (1)`, `START-CODE (1)`, `MYCHANNEL (1)` … (+2 more)
- **CICS operations:** `CONTAINER INPUTCONTAINER (write)`, `CHANNEL MYCHANNEL (pass)`, `CONTAINER CREDITCHECKCONT (read)`, `CONTAINER GETNAMECONTAINER (read)`, `CONTAINER GETADDRCONTAINER (read)`, `CONTAINER GETPOSTCODE (read)`, `CONTAINER GETVIPSTATUS (read)`, `CONTAINER SEQPNT (read/write)`
- **Compiler options:** `TRUNC(STD)`
- **Data moves:** 15 (MOVE 15); most-fed items `ACCOUNT-NUM`, `APPLICATION-RESULT`, `CUST-NO-IN`, `RESULT-TEXT`
- **Unit of work:** `0` commit / `0` rollback points; handlers none; `0/14` RESP results tested

*(+127 more files with mainframe facts; full detail in `record_data`/`call_site_data`/`dataset_data`.)*

- **Mainframe skeleton completeness:** 52% (mean channel ratio; channel table in the audit report, section 7). Top missing inputs: application programs (source or load-module list) (70 gaps); BMS map sources (32 gaps); JCL and PROC libraries (15 gaps).

## 14. PROJECT IDIOM WRAPPERS (Hidden Literal Vocabulary)
> **AI CONTEXT:** Project-local helpers that wrap a literal primitive (print, abort, allocation). Their call sites are NOT in the literal signal counts above -- read a low `debug_prints`/`panics_and_aborts`/`memory_alloc` count together with this list. Full detail in `wrapper_data`.

- **`debug_prints`:** 134 literal sites + 349 sites through wrappers = 483
- **`memory_alloc`:** 0 literal sites + 13 sites through wrappers = 13
- **`panics_and_aborts`:** 66 literal sites + 356 sites through wrappers = 422

- `refuse` (function, debug_prints, primitive): 246 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `refuse` (function, panics_and_aborts, primitive): 246 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `refuse` (function, debug_prints, primitive): 37 call sites in 1 files -- `tests/equivalence/ims/ggdli.c`
- `refuse` (function, panics_and_aborts, primitive): 37 call sites in 1 files -- `tests/equivalence/ims/ggdli.c`
- `refuse` (function, debug_prints, primitive): 26 call sites in 1 files -- `tests/equivalence/mq/ggmq.c`
- `refuse` (function, panics_and_aborts, primitive): 26 call sites in 1 files -- `tests/equivalence/mq/ggmq.c`
- `refuse` (function, debug_prints, primitive): 9 call sites in 1 files -- `tests/equivalence/le/le_time.c`
- `refuse` (function, panics_and_aborts, primitive): 9 call sites in 1 files -- `tests/equivalence/le/le_time.c`
- `_fail` (function, debug_prints, primitive): 8 call sites in 1 files -- `gitgalaxy/tools/readiness/assess.py`
- `blk_set_new` (function, memory_alloc, via blk_new): 8 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `abend` (function, panics_and_aborts, primitive): 7 call sites in 1 files -- `tests/equivalence/carddemo-trnrpt/port/service/Cbtrn03cService.java`
- `die` (function, debug_prints, primitive): 4 call sites in 1 files -- `tests/tools/crucible_pins.py`
*(+23 more in `wrapper_data`.)*

## 15. FUNCTION CALL RESOLUTION (Call Graph Confidence)
> **AI CONTEXT:** Each function's callee names, linked to the definition they most plausibly mean. *scoped* = same class/file, an imported file, or a class-qualified call; *unique* = the only definition in the repository; *ambiguous* = several candidates or an untyped receiver (never a graph edge); *external* = defined nowhere here (built-ins, packages). A high scoped/unique share means the resolver made a confident choice, not that the choice was correct; resolution accuracy is measured separately (gitgalaxy#3332). Detail in `fcall_data` / `fcall_rate_data`.

- **Repository:** 95262 call pairs -- scoped 29.7%, unique 0.1%, ambiguous 12.9%, external 57.3%

| Language | Pairs | Scoped | Unique | Ambiguous | External |
|---|---|---|---|---|---|
| python | 77988 | 28.4% | 0.0% | 12.1% | 59.5% |
| java | 14833 | 33.7% | 0.0% | 19.1% | 47.2% |
| c | 1951 | 43.5% | 2.7% | 1.5% | 52.3% |
| cobol | 358 | 93.6% | 0.8% | 0.8% | 4.7% |
| javascript | 85 | 11.8% | 0.0% | 0.0% | 88.2% |
| jcl | 34 | 0.0% | 0.0% | 0.0% | 100.0% |
| pli | 13 | 84.6% | 15.4% | 0.0% | 0.0% |

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
