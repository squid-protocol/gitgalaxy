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
- **Scope:** 2604 analyzed artifact(s), 453944 LOC.
- **Load-bearing artifact:** `gitgalaxy/core/detector.py` -- 165 in-repo importer(s) depend on it. Changes here propagate furthest.
- **Top orchestrator:** `tests/extraction/languages/test_ai_ml_import_anchor_4150.py` -- pulls in 82 dependencies, the widest assembly point in the scan.
- **Heaviest artifact:** `gitgalaxy/core/detector.py` at magnitude 12757.26 (structural weight, not risk).
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
| Total Artifacts | 6216 |
| Analyzed Artifacts (Scanned) | 2604 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 3612 |
| Total LOC | 453944 |
| Volatility Index | 0.003 |
| % Scanned of codebase = | 41.9% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.714 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.1694 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 2.8% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 3.5163 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 217 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 1666 | 354103 | 64.0% |
| PLAINTEXT | 286 | 0 | 11.0% |
| JAVA | 206 | 60049 | 7.9% |
| COBOL | 112 | 15141 | 4.3% |
| YAML | 65 | 7020 | 2.5% |
| BINARY_THREAT | 53 | 53 | 2.0% |
| MARKDOWN | 51 | 0 | 2.0% |
| HLASM | 32 | 675 | 1.2% |
| SQLITE | 28 | 1900 | 1.1% |
| C | 26 | 9588 | 1.0% |
| M4 | 14 | 36 | 0.5% |
| JCL | 14 | 456 | 0.5% |
| SHELL | 12 | 363 | 0.5% |
| PLI | 10 | 1425 | 0.4% |
| CSD | 8 | 1155 | 0.3% |
| BMS | 8 | 1471 | 0.3% |
| DB2_SQL | 7 | 114 | 0.3% |
| DOCKERFILE | 2 | 17 | 0.1% |
| CSV | 1 | 45 | 0.0% |
| GO | 1 | 162 | 0.0% |
| XML | 1 | 0 | 0.0% |
| JAVASCRIPT | 1 | 171 | 0.0% |

## 4.1 SOURCE ENCODINGS
| Encoding | Decode | Files |
|---|---|---|
| utf-8 | utf-8 | 2551 |
| unknown | unknown | 53 |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Hub-Coupled Monorepo`
> **Architectural Drift Z-Score:** `3.374`
> **Composition Archetype:** `Hub-Coupled Monorepo` (z +3.37; from the repo's file-archetype mix)
> **File Composition:** Large Core Modules (2) 37%, Data / Markup / Trivial 21%, Large Core Modules (3) 12%, Declarative / Non-Code 6%, Generic / Templated Code Files 6%
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 2214 | 85.0% |
| Unknown | 53 | 2.0% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 337 | 12.9% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 3612*

**Composition by Extension & Reason:**
- `.json`: 1293x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.snap`: 777x Excluded (Unsupported Extension: '.snap'), 425x Unsupported Format (.snap)
- `.md`: 703x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 58 LOC), 1x Excluded (Machine-Generated Source Code Signature: 467 LOC)
- `no_extension`: 202x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 3x Unsupported Format (.undeterminable)
- `.png`: 59x Excluded (Explicitly Denied Extension: '.png')
- `.gz`: 44x Excluded (Explicitly Denied Extension: '.gz')
- `.gif`: 17x Excluded (Explicitly Denied Extension: '.gif')
- `.txt`: 1x Excluded (Machine-Generated Source Code Signature: 120 LOC), 1x Excluded (Machine-Generated Source Code Signature: 176 LOC), 1x Excluded (Machine-Generated Source Code Signature: 589 LOC)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 357 LOC), 1x Excluded (Saturation: Line 46 exceeds 500 chars)
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.java`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Lexical Monotony: High structural repetition detected in 2361 LOC)
- `.html`: 6x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.svg`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.yml`: 1x Excluded (Static Asset Blob without Intent: 1007 LOC), 1x Excluded (Static Asset Blob without Intent: 1650 LOC), 1x Excluded (Saturation: Line 73 exceeds 500 chars)
- `.jsonl`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Saturation: Line 1 exceeds 500 chars)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 85.6 | 2.0 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 100.0 | 3.6 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 97.1 | 0.2 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 2.3 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 63.1 | 0.6 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 100.0 | 0.1 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 3.6 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 86.9 | 0.1 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 7.4 | 0.1 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 88.9 | 0.7 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) _(coverage)_ | 0.0 | 100.0 | 0.8 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

> `Doc Surface (formerly Documentation Exposure)` is **documentation coverage, not a fragility driver**. It is reported for context beside program length, and is deliberately excluded from the ranked-file drivers in this brief: it measures the share of a file's unit weight a reader cannot recover from documentation, so on a codebase that documents little it sits near ceiling everywhere and describes the repo rather than distinguishing files within it.
> `Spec Alignment (formerly Specification Exposure)` was **not measured** on this scan and is therefore absent above rather than reported as 0 (which would assert full alignment). Enable it with `--spec-alignment` if this codebase uses the corresponding convention.

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 950 | 63 | 0 | `gitgalaxy/recorders/record_keeper.py` |
| cleanup | 25 | 11 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 2265 | 81 | 0 | `gitgalaxy/core/detector.py` |
| danger | 1677 | 80 | 0 | `gitgalaxy/core/detector.py` |
| concurrency | 54 | 16 | 0 | `gitgalaxy/galaxyscope.py` |
| connectivity | 473 | 81 | 0 | `gitgalaxy/core/detector.py` |
| io | 222 | 44 | 0 | `.claude/hooks/session-start.sh` |
| crypto | 5 | 5 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 44 | 6 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 51 | 4 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 586 | 54 | 0 | `gitgalaxy/core/detector.py` |
| events | 309 | 23 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 6 | 4 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 1030 | 86 | 0 | `gitgalaxy/core/detector.py` |
| debt | 226 | 27 | 0 | `gitgalaxy/cobol_to_java_controller.py` |
| mutation | 18806 | 84 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 91 | 14 | 0 | `gitgalaxy/core/detector.py` |
| credential | 6 | 4 | 0 | `gitgalaxy/core/detector.py` |
| threat | 110 | 19 | 0 | `gitgalaxy/core/rule_prefilter.py` |
| ml_ai | 1 | 1 | 0 | `.claude/hooks/session-start.sh` |
| ui | 9 | 2 | 0 | `gitgalaxy/recorders/llm_recorder.py` |

**Relations (repo medians):**
- `guard_balance_ratio` (guards / (danger + 1)): **0.0**
- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **0.0**

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `.claude/hooks/session-start.sh` (Hits: 64)
- `scripts/setup_java_toolchain.sh` (Hits: 17)
- `gitgalaxy/core/prefetch.py` (Hits: 16)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **detector.py** (`gitgalaxy/core/detector.py`) — 165 inbound connections
2. **__init__.py** (`gitgalaxy/tools/cobol_to_java/det/__init__.py`) — 153 inbound connections
3. **source_text.py** (`gitgalaxy/core/source_text.py`) — 139 inbound connections
4. **equivalence_cics.py** (`tests/tools/equivalence_cics.py`) — 85 inbound connections
5. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 83 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **test_ai_ml_import_anchor_4150.py** (`tests/extraction/languages/test_ai_ml_import_anchor_4150.py`) — 82 outbound dependencies
2. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 78 outbound dependencies
3. **README.md** (`gitgalaxy/tools/cobol_to_java/README.md`) — 62 outbound dependencies
4. **BANK.csd** (`tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/etc/install/base/installjcl/BANK.csd`) — 54 outbound dependencies
5. **test_import_graph_accuracy.py** (`tests/tools/test_import_graph_accuracy.py`) — 50 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_translate` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_java/det/program.py`) -> Impact: **1475.1** | LOC: 842
- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1434.7** | LOC: 1442
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **924.6** | LOC: 1093
- `_calculate_block_metrics` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **852.8** | LOC: 686
- `_translate_command` **(Many-Argument Workhorses)** (@ `tests/tools/equivalence_cics.py`) -> Impact: **825.1** | LOC: 543
  * *Intent:* """One EXEC CICS body -> the COBOL statements that replace it. `labels` are the program's HANDLE labels (handler_labels), which a condition or abend e...
- `run_cobol_cics` **(Many-Argument Workhorses)** (@ `tests/tools/equivalence_cics.py`) -> Impact: **778.7** | LOC: 387
- `score` **(Many-Argument Workhorses)** (@ `tests/tools/cobol_answer_key.py`) -> Impact: **745.4** | LOC: 748
- `_command` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_java/det/cics.py`) -> Impact: **668.2** | LOC: 565
- `Name the Db2 image cache entry (` **(Many-Argument Workhorses)** (@ `.github/workflows/equivalence-e2e.yml`) -> Impact: **552.5** | LOC: 407
  * *Intent:* # #7002: a shard's Db2-backed proof (cbsa-updacc) starts the Db2 container; its cold icr.io pull timed out on main. # Same cache entry and background ...
- `splice` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **521.3** | LOC: 865

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `tests/cobol_mainframe` | 405 | 50474.62 | 19.4% | 0.0% |
| `gitgalaxy/core` | 66 | 40561.66 | 49.96% | 4.08% |
| `tests/extraction/languages` | 215 | 19475.86 | 13.2% | 0.0% |
| `tests/core_engine` | 158 | 18329.4 | 15.32% | 0.0% |
| `tests/equivalence/cics` | 13 | 12213.93 | 31.29% | 0.0% |
| `tests/cics_crucible` | 45 | 7789.76 | 21.41% | 0.0% |
| `gitgalaxy/recorders` | 8 | 6351.62 | 46.29% | 4.02% |
| `gitgalaxy` | 6 | 4603.58 | 37.75% | 1.6% |
| `tests/equivalence/zecs-zecs000` | 9 | 4001.0 | 0.0% | 0.0% |
| `gitgalaxy/metrics` | 7 | 3992.58 | 46.05% | 10.77% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `.github/ISSUE_TEMPLATE/parsing_discrepancy.yml` -> **97.0688%** Exposure
- `gitgalaxy/core/ebcdic_dbcs.py` -> **88.1655%** Exposure
- `gitgalaxy/core/rule_prefilter.py` -> **65.1355%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **53.2847%** Exposure
- `gitgalaxy/core/prism.py` -> **42.9196%** Exposure
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
- **Unknown Dependencies:** `14759` packages imported that bypass the Zero-Trust whitelist.

## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)
> Ranked by Structural Magnitude: the file's structural weight and centralization within the system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not the vector percentages, is the actionable part.

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 12757.26 | **LOC:** 11867 | **CtrlFlow:** 45.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **165** in-repo importer(s); it depends on **23**; blast radius 14.024; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (88.9%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 16.9444% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1434.7)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 852.8)
  * `splice` **(Many-Argument Workhorses)** (Impact: 521.3)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 271.5)
  * `_slice_by_indentation` **(Many-Argument Workhorses)** (Impact: 257.3)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 3 instances
* *Amplified Cascading Flux:* 1696 instances
* *Concurrency (weighted view):* 21
* *State Mutation (weighted view):* 5341
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 2786`, `structural_boundaries: 840`, `args: 161`, `func_start: 153`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 183`, `state_mutation: 1949`, `dead_code: 58`, `planned_debt: 2`, `fragile_debt: 25`
* *Architecture:* `api: 29`, `concurrency: 6`, `import: 27`
* *Defense:* `safety: 57`, `doc: 148`, `immutability_locks: 96`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 14.024
  * `Choke Point (Betweenness):` 0.001405 | `Ripple Effect (Closeness):` 0.060506
  * `Imports (Out-Degree: 12):` bisect, collections, functools, gitgalaxy.core, gitgalaxy.core.call_resolver, gitgalaxy.core.cobol_source_format, gitgalaxy.core.fortran_calls, gitgalaxy.core.network_risk_sensor...
  * `Imported By (In-Degree: 165):` (Excluded from Brief to save tokens)

### `tests/equivalence/cics/ggcics.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 3877.22 | **LOC:** 2566 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **21**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGCWTO` **(Many-Argument Workhorses)** (Impact: 85.1)
    * *Intent:* /* WRITE OPERATOR TEXT(from) of GG-LEN bytes: a message to the console, recorded with its text. A te...
  * `counter_step_x` **(Many-Argument Workhorses)** (Impact: 81.2)
    * *Intent:* /* GET with #5039 (X53)'s REDUCE ("the request succeeds with the current value set to the maximum pl...
  * `get_counter_x` **(Many-Argument Workhorses)** (Impact: 70.4)
    * *Intent:* /* GET COUNTER / DCOUNTER with REDUCE, COMPAREMIN, COMPAREMAX (#5039, register X53; IBM, EXEC CICS G...
  * `GGCQCNT` **(Many-Argument Workhorses)** (Impact: 66.5)
    * *Intent:* /* QUERY COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (IBM CICS TS, EXEC CICS QUERY COUNTER; #44...
  * `GGCDCNT` **(Many-Argument Workhorses)** (Impact: 64.3)
    * *Intent:* /* DEFINE COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4270, register X30; #5039, X50; IBM, EX...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` ctype.h, direct.h, ggcics_conditions.c, ggcics_containers.c, ggcics_enq.c, ggcics_faults.c, ggcics_filecontrol.c, ggcics_spec.h...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3568.18 | **LOC:** 4671 | **CtrlFlow:** 27.1% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **34** in-repo importer(s); it depends on **78**; blast radius 2.624; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.0%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (79.2%)
- **Documentation Coverage:** 20.7865% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 272.8)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 183.4)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `_process_file_worker` **(Many-Argument Workhorses)** (Impact: 170.2)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `main` **(I/O & Config Routines)** (Impact: 113.7)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
  * `_calculate_risk_exposures` **(Many-Argument Workhorses)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 563 instances
* *Concurrency (weighted view):* 17
* *State Mutation (weighted view):* 1924
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 783`, `structural_boundaries: 399`, `args: 70`, `func_start: 58`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 151`, `high_risk_execution: 2`, `state_mutation: 798`, `dead_code: 1`
* *Architecture:* `io: 14`, `api: 20`, `concurrency: 7`, `import: 91`
* *Defense:* `safety: 71`, `doc: 47`, `test: 2`, `immutability_locks: 24`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.624
  * `Choke Point (Betweenness):` 0.000976 | `Ripple Effect (Closeness):` 0.015082
  * `Imports (Out-Degree: 50):` argparse, collections, concurrent.futures, copy, datetime, extraction, functools, gitgalaxy.core.aperture...
  * `Imported By (In-Degree: 34):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3548.34 | **LOC:** 2484 | **CtrlFlow:** 38.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **11** in-repo importer(s); it depends on **17**; blast radius 0.757; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (72.6%)
- **Documentation Coverage:** 40.3226% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_build_markdown` **(Many-Argument Workhorses)** (Impact: 924.6)
  * `_executive_summary_lines` **(Stateful Encapsulated Methods)** (Impact: 58.0)
  * `_mainframe_facts_lines` **(Stateful Encapsulated Methods)** (Impact: 44.7)
    * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These ar...
  * `generate_artifacts` **(Many-Argument Workhorses)** (Impact: 42.2)
  * `_source_encoding_lines` **(Stateful Encapsulated Methods)** (Impact: 36.8)
    * *Intent:* """#3813: how the parsed files' bytes became text. One line when every file is UTF-8; otherwise a ta...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 553 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1795
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 681`, `structural_boundaries: 231`, `args: 84`, `func_start: 53`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 105`, `state_mutation: 689`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `io: 2`, `api: 6`, `concurrency: 2`, `import: 16`
* *Defense:* `safety: 17`, `doc: 25`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 0.757
  * `Choke Point (Betweenness):` 1.6e-05 | `Ripple Effect (Closeness):` 0.012369
  * `Imports (Out-Degree: 5):` collections, collections.abc, gitgalaxy.core.call_resolver, gitgalaxy.core.compiler_options, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.standards, heapq...
  * `Imported By (In-Degree: 11):` (Excluded from Brief to save tokens)

### `tests/equivalence/cics/ggcics_web.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_3` (Drift: N/A IQR)
- **Magnitude:** 3379.16 | **LOC:** 1134 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGCWPRS` **(Many-Argument Workhorses)** (Impact: 326.9)
  * `GGCWCNV` **(Many-Argument Workhorses)** (Impact: 314.7)
    * *Intent:* /* WEB CONVERSE: GG-NUM the METHOD CVDA (out: STATUSCODE), GG-HOURS PATHLENGTH, GG-MINS QUERYSTRLEN,...
  * `web_send_body` **(Many-Argument Workhorses)** (Impact: 230.6)
  * `GGCTCPX` **(Many-Argument Workhorses)** (Impact: 156.8)
    * *Intent:* /* GG-LEN CADDRLENGTH, GG-HOURS CNAMELENGTH, GG-MINS SADDRLENGTH, GG-SECS SNAMELENGTH (each in, 0 wh...
  * `GGCWEXT` **(Many-Argument Workhorses)** (Impact: 133.3)
    * *Intent:* /* GG-LEN HOSTLENGTH, GG-HOURS METHODLENGTH, GG-MINS VERSIONLEN, GG-SECS PATHLENGTH, GG-ITEM QUERYST...
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

### `gitgalaxy/core/mainframe_boundary.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 2972.74 | **LOC:** 2771 | **CtrlFlow:** 41.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **57** in-repo importer(s); it depends on **32**; blast radius 5.054; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.7%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (55.5%)
- **Documentation Coverage:** 12.1795% of unit weight undocumented
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
* *Amplified Cascading Flux:* 458 instances
* *State Mutation (weighted view):* 1470
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 719`, `structural_boundaries: 298`, `args: 83`, `func_start: 75`
* *Risk/State:* `safety_bypasses: 97`, `state_mutation: 554`, `dead_code: 2`, `duplicate_logic: 11`
* *Architecture:* `api: 3`, `import: 33`
* *Defense:* `safety: 3`, `doc: 59`, `immutability_locks: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 5.054
  * `Choke Point (Betweenness):` 0.002687 | `Ripple Effect (Closeness):` 0.085278
  * `Imports (Out-Degree: 26):` bisect, collections.abc, gitgalaxy.core.bms_screen_fields, gitgalaxy.core.call_using, gitgalaxy.core.cics_macro_tables, gitgalaxy.core.cics_resources, gitgalaxy.core.cics_tasks, gitgalaxy.core.cobol_conditional...
  * `Imported By (In-Degree: 57):` (Excluded from Brief to save tokens)

### `tests/cics_crucible/test_cics_runtimes.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 2758.12 | **LOC:** 7268 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **15**
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
  * `Imports (Out-Degree: 0):` atexit, cics_crucible, equivalence_cics, functools, gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge, javac_server, os, pathlib...
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
- **Magnitude:** 2424.46 | **LOC:** 3892 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **22**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_deleteq_ts_and_inquire_association_and_the_receive_map_terminal_option` **(Defensive Guards)** (Impact: 30.6)
    * *Intent:* """#4415 slice 2 (register X29), IBM EXEC CICS DELETEQ TS / INQUIRE ASSOCIATION / RECEIVE MAP: DELET...
  * `test_web_open_converse_close_are_the_tasks_http_client` **(Defensive Guards)** (Impact: 21.7)
    * *Intent:* """#4767 zECS (register X35), IBM WEB OPEN / WEB CONVERSE / WEB CLOSE: OPEN by URIMAP or HOST / HOST...
  * `test_web_browse_forms_are_the_requests_pairs` **(Defensive Guards)** (Impact: 19.9)
    * *Intent:* """#4940 (register X38), IBM WEB STARTBROWSE / READNEXT / ENDBROWSE HTTPHEADER, FORMFIELD, QUERYPARM...
  * `test_inquire_urimap_browse_and_write_operator` **(Defensive Guards)** (Impact: 17.8)
    * *Intent:* """#4270 zECS (register X32), IBM INQUIRE URIMAP ("Browsing resource definitions") / WRITE OPERATOR:...
  * `test_inquire_urimap_direct_form_and_inquire_program_status` **(Defensive Guards)** (Impact: 17.0)
    * *Intent:* """#4768 zECS (register X34). IBM INQUIRE URIMAP, the direct form: URIMAP(name) with no browse optio...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` __future__, com.x., com.x.entity.vsam., contextlib, decimal, det_port, equivalence_cics, gitgalaxy.standards.cics.commands...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/network_risk_sensor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2243.8 | **LOC:** 1817 | **CtrlFlow:** 46.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **21** in-repo importer(s); it depends on **21**; blast radius 2.532; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.5%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (53.5%)
- **Documentation Coverage:** 25.4386% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_target_unguarded` **(Many-Argument Workhorses)** (Impact: 232.3)
  * `_resolve_by_name` **(Many-Argument Workhorses)** (Impact: 165.5)
  * `_resolve_in_libraries` **(Many-Argument Workhorses)** (Impact: 87.8)
  * `_resolve_edges` **(Many-Argument Workhorses)** (Impact: 83.1)
    * *Intent:* """ #2992: resolves every file's raw_imports into directed file-to-file edges, keyed (importer, impo...
  * `build_dependency_graph` **(Many-Argument Workhorses)** (Impact: 68.8)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 266 instances
* *State Mutation (weighted view):* 826
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 501`, `structural_boundaries: 230`, `args: 49`, `func_start: 48`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 55`, `high_risk_execution: 1`, `state_mutation: 294`, `dead_code: 6`
* *Architecture:* `io: 5`, `api: 10`, `import: 19`
* *Defense:* `safety: 15`, `doc: 42`, `immutability_locks: 11`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.532
  * `Choke Point (Betweenness):` 0.001076 | `Ripple Effect (Closeness):` 0.046658
  * `Imports (Out-Degree: 9):` collections, collections.abc, gitgalaxy.core.copy_libraries, gitgalaxy.core.go_modules, gitgalaxy.core.graph_engine, gitgalaxy.core.invocation_resolver, gitgalaxy.core.package_self_reference, gitgalaxy.core.path_proximity...
  * `Imported By (In-Degree: 21):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 2131.98 | **LOC:** 2278 | **CtrlFlow:** 27.5% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **14** in-repo importer(s); it depends on **12**; blast radius 1.018; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.4%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (63.5%)
- **Documentation Coverage:** 29.3103% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` **(Many-Argument Workhorses)** (Impact: 256.3)
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
* *State Mutation (weighted view):* 1109
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 369`, `structural_boundaries: 147`, `args: 48`, `func_start: 37`, `class_start: 2`
* *Risk/State:* `safety_bypasses: 44`, `state_mutation: 461`, `dead_code: 1`, `planned_debt: 1`, `fragile_debt: 1`
* *Architecture:* `io: 1`, `api: 10`, `concurrency: 2`, `import: 13`
* *Defense:* `safety: 29`, `doc: 28`, `immutability_locks: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 1.018
  * `Choke Point (Betweenness):` 1.4e-05 | `Ripple Effect (Closeness):` 0.012919
  * `Imports (Out-Degree: 4):` collections.abc, gitgalaxy.core.function_population, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math...
  * `Imported By (In-Degree: 14):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/call_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2119.12 | **LOC:** 1981 | **CtrlFlow:** 38.3% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **26** in-repo importer(s); it depends on **4**; blast radius 3.727; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (97.4%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (68.1%)
- **Documentation Coverage:** 21.6418% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `resolve_calls` **(Many-Argument Workhorses)** (Impact: 431.6)
  * `_resolve_one` **(Many-Argument Workhorses)** (Impact: 243.2)
  * `_init_entry_not_a_base` **(Many-Argument Workhorses)** (Impact: 74.8)
  * `_expand_super_ctor` **(Many-Argument Workhorses)** (Impact: 54.7)
  * `_visible_receiver` **(Stateful Encapsulated Methods)** (Impact: 37.2)
    * *Intent:* """An untyped receiver (`x.save()`): confident only when exactly ONE visible class defines the metho...
**Contextual Mitigations & Amplifications:**
* *Mitigated Danger:* 1 instances
* *Amplified Cascading Flux:* 223 instances
* *High Risk Execution (weighted view):* 2
* *State Mutation (weighted view):* 708
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 534`, `structural_boundaries: 205`, `args: 59`, `func_start: 52`, `class_start: 4`
* *Risk/State:* `safety_bypasses: 47`, `high_risk_execution: 3`, `state_mutation: 262`, `dead_code: 4`, `planned_debt: 4`
* *Architecture:* `io: 1`, `api: 15`, `import: 4`
* *Defense:* `safety: 5`, `doc: 40`, `immutability_locks: 43`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 3.727
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.053566
  * `Imports (Out-Degree: 0):` collections, posixpath, re, typing
  * `Imported By (In-Degree: 26):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 2022.44 | **LOC:** 2061 | **CtrlFlow:** 35.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **62** in-repo importer(s); it depends on **5**; blast radius 3.842; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (46.5%)
- **Documentation Coverage:** 20.7547% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` **(Many-Argument Workhorses)** (Impact: 124.2)
    * *Intent:* """ Single-line comment stripper for the "line_exclusive" family, driven by each language's own real...
  * `_strip_single_line_comments_positional` **(Many-Argument Workhorses)** (Impact: 122.2)
    * *Intent:* """Positional sibling of `_strip_single_line_comments`: same per-line masking and carry-quote discip...
  * `_strip_positional_comments` **(Many-Argument Workhorses)** (Impact: 97.5)
  * `_mask_perl_line_positional` **(Many-Argument Workhorses)** (Impact: 75.4)
  * `_mask_perl_line` **(Many-Argument Workhorses)** (Impact: 75.4)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 291 instances
* *State Mutation (weighted view):* 928
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 350`, `structural_boundaries: 178`, `args: 48`, `func_start: 45`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 34`, `state_mutation: 346`, `fragile_debt: 6`, `duplicate_logic: 2`
* *Architecture:* `api: 11`, `import: 5`
* *Defense:* `safety: 4`, `doc: 42`, `immutability_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 3.842
  * `Choke Point (Betweenness):` 1.7e-05 | `Ripple Effect (Closeness):` 0.052558
  * `Imports (Out-Degree: 1):` gitgalaxy.core.cobol_source_format, gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 62):` (Excluded from Brief to save tokens)

### `tests/equivalence/ims/ggdli.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 2021.68 | **LOC:** 1321 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **3**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `get` **(Many-Argument Workhorses)** (Impact: 197.6)
    * *Intent:* /* GU / GN / GNP and their holds */
  * `GGDLIX` **(Many-Argument Workhorses)** (Impact: 134.2)
  * `parse_ssas` **(Many-Argument Workhorses)** (Impact: 131.7)
    * *Intent:* /* The SSAs of a call: 0, or the status code that rejects them. */
  * `change` **(Many-Argument Workhorses)** (Impact: 86.8)
    * *Intent:* /* REPL / DLET: on the segment the previous call on this PCB held */
  * `check_codes` **(Many-Argument Workhorses)** (Impact: 76.1)
    * *Intent:* /* Command codes (#5233): Q on a get (no effect: one program, so no other program to wait for); F an...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` stdio.h, stdlib.h, string.h
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1860.76 | **LOC:** 1696 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **8**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 444.6)
  * `_tier_4_heuristic_discovery` **(Many-Argument Workhorses)** (Impact: 135.5)
    * *Intent:* # ========================================================================= # THE TIER 4 HEURISTIC D...
  * `_evaluate_ecosystem_gravity` **(Many-Argument Workhorses)** (Impact: 103.9)
  * `_tier_3_lexical_scan` **(Many-Argument Workhorses)** (Impact: 76.7)
  * `_resolve_by_sibling_content` **(Many-Argument Workhorses)** (Impact: 42.6)
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` gitgalaxy.core.source_text, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, logging, math, pathlib, re, typing
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/cobol_mainframe/test_equivalence_cics.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1783.74 | **LOC:** 3025 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **20**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_formattime_day_of_year_and_binary_forms_under_gnucobol_equal_the_java_runtime` **(Defensive Guards)** (Impact: 15.9)
    * *Intent:* """#4415 slice 3 (X46): the translated COBOL, run under GnuCOBOL at the six instants test_cics_runti...
  * `test_no_case_says_a_writeq_past_from_is_refused` **(Defensive Guards)** (Impact: 14.9)
    * *Intent:* """#6271: since #6573 a WRITEQ whose LENGTH runs past FROM is written padded (X6) and the task is co...
  * `test_the_generated_test_runs_runtask_unless_the_facade_side_is_asked_for` **(Defensive Guards)** (Impact: 13.9)
    * *Intent:* """The runTask side is the default (-Dequivalence.facades unset) and runs as before; the facade side...
  * `test_a_scenario_states_untyped_commarea_bytes_for_a_case_with_no_layout` **(Defensive Guards)** (Impact: 13.8)
    * *Intent:* """#5859 (ZECSNC): `"commarea_hex"` is the exact bytes the caller passed to a program with no typed ...
  * `test_a_scenario_states_its_own_records_for_a_dataset_of_the_case` **(Defensive Guards)** (Impact: 13.8)
    * *Intent:* """#4622: `scenario_datasets` is each overridden DD's spec with the scenario's `input` / `append`, t...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` ast, base64, datetime, decimal, equivalence, equivalence_cics, equivalence_java, gitgalaxy.standards.cics.commands...
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

### `tests/cobol_mainframe/test_galaxy_ir.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1320.88 | **LOC:** 2452 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **11**
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
  * `Imports (Out-Degree: 0):` com.ibm.cics.server.Program, gitgalaxy.cobol_refractor_controller, gitgalaxy.tools.cobol_to_cobol.galaxy_ir, os, pathlib, pytest, scan_server, shutil...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/equivalence/db2/ggsql.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1290.1 | **LOC:** 817 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `run` **(Many-Argument Workhorses)** (Impact: 156.4)
  * `num_store` **(Many-Argument Workhorses)** (Impact: 94.8)
    * *Intent:* /* decimal text into a numeric host variable; -304 when the integer part does not fit, 0 when stored...
  * `GGSQL` **(Many-Argument Workhorses)** (Impact: 61.2)
    * *Intent:* /* ---- the entry ----------------------------------------------------------------------------------...
  * `num_text` **(Stateful Encapsulated Methods)** (Impact: 58.0)
    * *Intent:* /* a numeric host variable's value as decimal text ("-123.45"); 0 when its bytes are no number */
  * `fetch_into` **(Many-Argument Workhorses)** (Impact: 45.0)
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

### `tests/equivalence/cics/ggcics_filecontrol.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1261.68 | **LOC:** 628 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `browse_read` **(Many-Argument Workhorses)** (Impact: 138.3)
    * *Intent:* /* READNEXT (dir 1) / READPREV (dir -1) FILE(name1) INTO RIDFLD. */
  * `GGCDELT` **(Many-Argument Workhorses)** (Impact: 120.7)
    * *Intent:* /* DELETE FILE(name1) [RIDFLD]: the record with that key, or (no RIDFLD: GG-FLAGS 'HELD') the one a ...
  * `GGCREAD` **(Many-Argument Workhorses)** (Impact: 111.4)
  * `rba_read` **(Many-Argument Workhorses)** (Impact: 101.4)
    * *Intent:* /* READNEXT (dir 1) / READPREV (dir -1) ... RBA: GG-FLAGS 'RBA'; the browse is an RBA browse. */
  * `browse_event` **(Stateful Encapsulated Methods)** (Impact: 54.8)
    * *Intent:* /* #6262, SPEC 6.2 STARTBR / READNEXT / READPREV event: `rid=` the RIDFLD on entry as hex (a key may...
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

### `tests/equivalence/cics/ggcics_taskcontrol.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1252.88 | **LOC:** 868 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGCSTRT` **(Many-Argument Workhorses)** (Impact: 133.7)
  * `GGCFETCH` **(Compute Cores)** (Impact: 64.9)
    * *Intent:* /* #4884, #4950: FETCH ANY / FETCH CHILD(token) (IBM, EXEC CICS FETCH), as CicsTask.fetch: GG-FLAGS ...
  * `GGCRTRV` **(Many-Argument Workhorses)** (Impact: 59.6)
  * `GGCDLAY` **(Compute Cores)** (Impact: 50.0)
    * *Intent:* /* #4950: DELAY (IBM, EXEC CICS DELAY), as CicsTask.delay / delayMillis: GG-FLAGS INTERVAL (GG-NUM h...
  * `GGCPOST` **(Many-Argument Workhorses)** (Impact: 39.2)
    * *Intent:* /* POST INTERVAL(hhmmss) | TIME(hhmmss) (GG-NUM) | AFTER / AT HOURS MINUTES SECONDS (GG-HOURS / GG-M...
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

### `gitgalaxy/core/aperture.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1234.24 | **LOC:** 1336 | **CtrlFlow:** 33.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **21** in-repo importer(s); it depends on **9**; blast radius 1.988; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.2%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (54.3%)
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
* *State Mutation (weighted view):* 558
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 281`, `structural_boundaries: 200`, `args: 37`, `func_start: 37`, `class_start: 7`
* *Risk/State:* `safety_bypasses: 20`, `state_mutation: 218`
* *Architecture:* `io: 9`, `api: 15`, `import: 9`
* *Defense:* `safety: 22`, `doc: 35`, `sync_locks: 2`, `immutability_locks: 25`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 1.988
  * `Choke Point (Betweenness):` 4.7e-05 | `Ripple Effect (Closeness):` 0.026067
  * `Imports (Out-Degree: 3):` fnmatch, gitgalaxy.core.model_magic, gitgalaxy.core.source_text, gitgalaxy.standards.gitgalaxy_config, logging, os, pathlib, re...
  * `Imported By (In-Degree: 21):` (Excluded from Brief to save tokens)

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1171.44 | **LOC:** 3082 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **26**
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

### `tests/equivalence/carddemo-copaus0c/port/service/Copaus0cService.java` (JAVA | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 1161.94 | **LOC:** 2851 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **28**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `in_Copaus0cCarddemoCommarea` **(Compute Cores)** (Impact: 101.4)
  * `runTask` **(Defensive Guards)** (Impact: 86.2)
    * *Intent:* /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */
  * `p12` **(I/O & Config Routines)** (Impact: 76.0)
    * *Intent:* /** RECEIVE-PAULST-SCREEN. */
  * `run` **(Compute Cores)** (Impact: 63.5)
  * `p1` **(I/O & Config Routines)** (Impact: 27.7)
    * *Intent:* /** PROCESS-ENTER-KEY. */
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

- `gitgalaxy/core/detector.py` -> Churn: **88.94%** | Cog Load: 65.9396% | Debt: 13.3867%
- `gitgalaxy/core/call_resolver.py` -> Churn: **68.09%** | Cog Load: 59.3789% | Debt: 8.9405%
- `gitgalaxy/galaxyscope.py` -> Churn: **59.93%** | Cog Load: 79.1808% | Debt: 0.0%
- `gitgalaxy/core/mainframe_boundary.py` -> Churn: **52.56%** | Cog Load: 55.5243% | Debt: 28.9615%
- `gitgalaxy/core/runtime_options.py` -> Churn: **51.2%** | Cog Load: 53.4696% | Debt: 21.7467%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 12757.26
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3568.18
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3548.34
- `gitgalaxy/core/mainframe_boundary.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2972.74
- `gitgalaxy/core/network_risk_sensor.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 2243.8

## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 0.269** (Bridge: 0.0027 * Flux: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py` -> **Severity: 0.192** (Bridge: 0.0019 * Flux: 100.0%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.141** (Bridge: 0.0014 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.108** (Bridge: 0.0011 * Flux: 100.0%)
- `gitgalaxy/galaxyscope.py` -> **Severity: 0.098** (Bridge: 0.001 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/core/source_text.py` -> **Severity: 14.966** (Embedded: 0.1575 * Error Risk: 95.0099%)
- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 10.999** (Embedded: 0.1115 * Error Risk: 98.6853%)
- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 10.749** (Embedded: 0.1082 * Error Risk: 99.3102%)
- `gitgalaxy/core/cobol_source_format.py` -> **Severity: 10.308** (Embedded: 0.1037 * Error Risk: 99.4527%)
- `gitgalaxy/core/compiler_options.py` -> **Severity: 9.31** (Embedded: 0.094 * Error Risk: 99.0522%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 1065.968** (Blast Radius: 26.057 * Doc Risk: 40.9091%)
- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 981.6** (Blast Radius: 9.816 * Doc Risk: 100.0%)
- `gitgalaxy/tools/cobol_to_java/det/cobolrt/Field.java` -> **Severity: 913.65** (Blast Radius: 18.273 * Doc Risk: 50.0%)
- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 630.36** (Blast Radius: 15.759 * Doc Risk: 40.0%)
- `gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java` -> **Severity: 625.82** (Blast Radius: 19.181 * Doc Risk: 32.6271%)

## 13. MAINFRAME SYSTEM FACTS (Named Relations & Record Layouts)
> **AI CONTEXT:** Named mainframe relations the structural signal counts flatten -- the call graph (`CALL`/CICS `LINK`·`XCTL`/JCL `EXEC PGM=`), the dataset boundary (`SELECT…ASSIGN` + `OPEN` modes, JCL `DD`→dataset), and record layouts (COBOL DATA DIVISION items, PL/I `DECLARE`d structures). BMS screen maps (every field's position, length and attributes, `screen_field_data`) are the 3270 UI surface. These are the schema of the system: use them to trace which program runs which, which dataset a job binds, and the shape of the records that flow between them. Extracted by the engine (`core/mainframe_boundary.py`) and carried in the master DB (`call_site_data`/`dataset_data`/`record_data`); resolution to files is redone per scan.

- **Coverage:** `153` files carry mainframe facts -- `278` call sites, `96` dataset bindings, `4407` record items.

- **DB2 schemas:** `24` columns of `EXEC SQL DECLARE ... TABLE` (inline or DCLGEN members), full shape in `sql_table_data`.

- **DB2 table access:** `129` embedded SQL statements touching `14` tables (SELECT/INSERT/UPDATE/DELETE, cursors, host variables) in `sql_statement_data`; the program x table read/write matrix is `GalaxyIR.sql_table_access()`.

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

### `tests/equivalence/ims/fixture/DLICMD.cbl` (COBOL)
- **Calls:** `CALL CBLTDLI`
- **Record layouts (165 items):** `PCB1 (10)`, `PCB2 (10)`, `C-DDQ (6)`, `C-DQP (6)`, `C-DQ (6)`, `C-DQQ (6)`, `C-EQ2 (6)`, `C-EQ3 (6)`, `C-DQ9 (6)`, `C-CDE (5)`, `C-CE2 (4)`, `C-CS2 (4)` … (+43 more)
- **Data moves:** 181 (MOVE 181); most-fed items `W-IO`
- **IMS DL/I:** `F-GU C-DL`, `F-GN S-DEPT`, `F-GU C-DF`, `F-GU C-DN`, `F-GU S-DEPT,C-EL`, `F-GU C-DQ,C-EL`, `F-GU S-DEPT,C-EFL`, `F-GU S-DEPT,S-EMP,C-SKL`, `F-ISRT C-DQ,C-EF`, `F-GU C-DP,S-EMP`, `F-GNP`, `F-GU S-DEPT,C-EP`, `F-GU C-DQP,S-EMP`, `F-GU C-CE2`, `F-GU C-CS2`, `F-GU C-CE9`, `F-GU C-CE3`, `F-GU C-DD,C-ED,S-SKL`, `F-GN C-ED,S-SKL`, `F-GU C-DD,S-EMP`, `F-GU C-DD`, `F-GU C-DDQ,C-ED,S-SKL`, `F-GU C-DDP,S-EMP`, `F-GNP C-ED,S-SKL`, `F-GHU C-DD,S-EMP`, `F-GU C-DK`, `F-GU C-DQQ,S-EMP`, `F-GN C-EK`, `F-GNP C-SK`, `F-GHU C-DQQ,C-EK`, `F-GU S-DEPT,C-EKL`, `F-GU C-DU,S-EMP`, `F-GU C-DU,C-EQ2`, `F-GU C-DV,C-EV`, `F-GU S-DEPT,C-EU`, `F-GN C-DU,S-PROJ`, `F-GU C-DV`, `F-GNP S-EMP`, `F-GNP S-SKL`, `F-GNP C-EV,S-SKL`, `F-GU C-DU,C-EQ3`, `F-GHU C-DDN,S-EMP`, `F-REPL`, `F-GU S-DEPT,S-EMP`, `F-GU S-DEPT`, `F-GHU C-DD,C-EDN`, `F-ISRT C-DD,S-EMP`, `F-GU C-CN1`, `F-GU C-CN2`, `F-ISRT C-DD,C-ED,S-SKL`, `F-GU C-CN4`, `F-ISRT C-DQ,C-ED,S-SKL`, `F-GU C-CN3`, `F-GU C-CN5`, `F-ISRT C-DQ9,C-ED,S-SKL`

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

### `tests/equivalence/ims/fixture/DLIBOOL.cbl` (COBOL)
- **Calls:** `CALL CBLTDLI`
- **Record layouts (100 items):** `Q2 (14)`, `Q4 (14)`, `Q1 (10)`, `Q3 (10)`, `Q6 (10)`, `Q7 (10)`, `PCB1 (10)`, `PCB2 (10)`, `Q5 (6)`, `W-Q (1)`, `W-IO (1)`, `IOA (1)` … (+3 more)
- **Data moves:** 17 (MOVE 17); most-fed items `W-IO`
- **IMS DL/I:** `F-GU S-DEPT,Q1`, `F-GN Q1`, `F-GU S-DEPT,Q2`, `F-GU S-DEPT,Q3`, `F-GU S-DEPT,Q4`, `F-GU S-DEPT,Q5`, `F-GU S-DEPT,Q6`, `F-GU S-DEPT,Q7`

*(+133 more files with mainframe facts; full detail in `record_data`/`call_site_data`/`dataset_data`.)*

- **Mainframe skeleton completeness:** 52% (mean channel ratio; channel table in the audit report, section 7). Top missing inputs: application programs (source or load-module list) (70 gaps); BMS map sources (32 gaps); JCL and PROC libraries (19 gaps).

## 14. PROJECT IDIOM WRAPPERS (Hidden Literal Vocabulary)
> **AI CONTEXT:** Project-local helpers that wrap a literal primitive (print, abort, allocation). Their call sites are NOT in the literal signal counts above -- read a low `debug_prints`/`panics_and_aborts`/`memory_alloc` count together with this list. Full detail in `wrapper_data`.

- **`debug_prints`:** 147 literal sites + 242 sites through wrappers = 389
- **`memory_alloc`:** 0 literal sites + 8 sites through wrappers = 8
- **`panics_and_aborts`:** 99 literal sites + 251 sites through wrappers = 350

- `refuse` (function, debug_prints, primitive): 91 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `refuse` (function, panics_and_aborts, primitive): 91 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `refuse` (function, debug_prints, primitive): 74 call sites in 1 files -- `tests/equivalence/ims/ggdli.c`
- `refuse` (function, panics_and_aborts, primitive): 74 call sites in 1 files -- `tests/equivalence/ims/ggdli.c`
- `refuse` (function, debug_prints, primitive): 26 call sites in 1 files -- `tests/equivalence/mq/ggmq.c`
- `refuse` (function, panics_and_aborts, primitive): 26 call sites in 1 files -- `tests/equivalence/mq/ggmq.c`
- `refuse` (function, debug_prints, primitive): 10 call sites in 1 files -- `tests/equivalence/le/le_time.c`
- `refuse` (function, panics_and_aborts, primitive): 10 call sites in 1 files -- `tests/equivalence/le/le_time.c`
- `refuse` (function, debug_prints, primitive): 9 call sites in 1 files -- `tests/equivalence/le/ggtiot.c`
- `refuse` (function, panics_and_aborts, primitive): 9 call sites in 1 files -- `tests/equivalence/le/ggtiot.c`
- `_fail` (function, debug_prints, primitive): 8 call sites in 1 files -- `gitgalaxy/tools/readiness/assess.py`
- `abend` (function, panics_and_aborts, primitive): 7 call sites in 1 files -- `tests/equivalence/carddemo-trnrpt/port/service/Cbtrn03cService.java`
*(+27 more in `wrapper_data`.)*

## 15. FUNCTION CALL RESOLUTION (Call Graph Confidence)
> **AI CONTEXT:** Each function's callee names, linked to the definition they most plausibly mean. *scoped* = same class/file, an imported file, or a class-qualified call; *unique* = the only definition in the repository; *ambiguous* = several candidates or an untyped receiver (never a graph edge); *external* = defined nowhere here (built-ins, packages). A high scoped/unique share means the resolver made a confident choice, not that the choice was correct; resolution accuracy is measured separately (gitgalaxy#3332). Detail in `fcall_data` / `fcall_rate_data`.

- **Repository:** 123554 call pairs -- scoped 29.3%, unique 0.2%, ambiguous 13.7%, external 56.8%

| Language | Pairs | Scoped | Unique | Ambiguous | External |
|---|---|---|---|---|---|
| python | 100798 | 27.6% | 0.0% | 12.9% | 59.4% |
| java | 19845 | 36.0% | 0.0% | 19.0% | 45.0% |
| c | 2377 | 36.4% | 8.3% | 3.4% | 52.0% |
| cobol | 365 | 93.2% | 0.8% | 0.8% | 5.2% |
| javascript | 88 | 11.4% | 0.0% | 0.0% | 88.6% |
| jcl | 35 | 0.0% | 0.0% | 0.0% | 100.0% |
| go | 33 | 6.1% | 0.0% | 0.0% | 93.9% |
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
