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
- **Scope:** 3038 analyzed artifact(s), 510358 LOC.
- **Load-bearing artifact:** `gitgalaxy/core/detector.py` -- 207 in-repo importer(s) depend on it. Changes here propagate furthest.
- **Top orchestrator:** `gitgalaxy/tools/cobol_to_java/README.md` -- pulls in 98 dependencies, the widest assembly point in the scan.
- **Heaviest artifact:** `gitgalaxy/core/detector.py` at magnitude 14590.54 (structural weight, not risk).
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
| Total Artifacts | 7602 |
| Analyzed Artifacts (Scanned) | 3038 |
| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | 4564 |
| Total LOC | 510358 |
| Volatility Index | 0.002 |
| % Scanned of codebase = | 40.0% |
| Dominant Lang | PYTHON |

## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)
| Metric | Value | Interpretation |
|---|---|---|
| Modularity | 0.7166 | High = Clean micro-boundaries. Low = Spaghetti coupling. |
| Assortativity | -0.1674 | Positive = Resilient core. Negative = Fragile single-points-of-failure. |
| Cyclic Density | 3.3% | % of files trapped in dependency loops (Static Friction). |
| Avg Path Length | 3.5647 | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |
| Articulation Pts | 230 | Number of single files that, if removed, shatter the network. |

## 4. COMPOSITION
| Lang | Files | LOC | Share |
|---|---|---|---|
| PYTHON | 1961 | 402847 | 64.5% |
| PLAINTEXT | 362 | 0 | 11.9% |
| JAVA | 220 | 65727 | 7.2% |
| COBOL | 120 | 16399 | 3.9% |
| YAML | 67 | 7299 | 2.2% |
| BINARY_THREAT | 56 | 56 | 1.8% |
| MARKDOWN | 53 | 0 | 1.7% |
| SQLITE | 51 | 1944 | 1.7% |
| C | 34 | 9941 | 1.1% |
| HLASM | 32 | 675 | 1.1% |
| M4 | 15 | 39 | 0.5% |
| JCL | 15 | 485 | 0.5% |
| SHELL | 12 | 379 | 0.4% |
| PLI | 10 | 1425 | 0.3% |
| CSD | 8 | 1155 | 0.3% |
| BMS | 8 | 1471 | 0.3% |
| DB2_SQL | 7 | 114 | 0.2% |
| CSV | 2 | 52 | 0.1% |
| DOCKERFILE | 2 | 17 | 0.1% |
| GO | 1 | 162 | 0.0% |
| XML | 1 | 0 | 0.0% |
| JAVASCRIPT | 1 | 171 | 0.0% |

## 4.1 SOURCE ENCODINGS
| Encoding | Decode | Files |
|---|---|---|
| utf-8 | utf-8 | 2982 |
| unknown | unknown | 56 |

## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)
> **Assigned Ecosystem Baseline:** `Hub-Coupled Monorepo`
> **Architectural Drift Z-Score:** `3.339`
> **Composition Archetype:** `Hub-Coupled Monorepo` (z +3.34; from the repo's file-archetype mix)
> **File Composition:** Large Core Modules (2) 39%, Data / Markup / Trivial 22%, Large Core Modules (3) 12%, Generic / Templated Code Files 6%, Encapsulated Accessors Files 6%
> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern.

## 4.6 FILE ARCHETYPES & STATIC ASSETS
### Active Execution Logic (ML Clusters)
| Archetype | Count | Repo % |
|---|---|---|
| Unclassified | 2567 | 84.5% |
| Unknown | 56 | 1.8% |

### Inert Structural Mass (Static Categories)
| Category | Count | Repo % |
|---|---|---|
| Static: Literature & Documentation | 415 | 13.7% |

## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)
*Total Excluded Artifacts: 4564*

**Composition by Extension & Reason:**
- `.json`: 1653x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.snap`: 1066x Excluded (Unsupported Extension: '.snap'), 563x Unsupported Format (.snap)
- `.md`: 727x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 62 LOC), 1x Excluded (Machine-Generated Source Code Signature: 472 LOC)
- `no_extension`: 273x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 3x Unsupported Format (.undeterminable)
- `.png`: 74x Excluded (Explicitly Denied Extension: '.png')
- `.gz`: 44x Excluded (Explicitly Denied Extension: '.gz')
- `.gif`: 32x Excluded (Explicitly Denied Extension: '.gif')
- `.svg`: 29x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.txt`: 2x Excluded (Machine-Generated Source Code Signature: 67 LOC), 1x Excluded (Machine-Generated Source Code Signature: 120 LOC), 1x Excluded (Machine-Generated Source Code Signature: 176 LOC)
- `.py`: 2x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Machine-Generated Source Code Signature: 357 LOC), 1x Excluded (Saturation: Line 46 exceeds 500 chars)
- `.mp4`: 13x Excluded (Explicitly Denied Extension: '.mp4')
- `.js`: 11x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.html`: 8x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir)
- `.java`: 5x Excluded (System Exclusion, Hidden Directory, or Dynamic Ignored Dir), 1x Excluded (Lexical Monotony: High structural repetition detected in 2456 LOC)
- `.yml`: 1x Excluded (Static Asset Blob without Intent: 1092 LOC), 1x Excluded (Static Asset Blob without Intent: 1831 LOC), 1x Excluded (Saturation: Line 73 exceeds 500 chars)

## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)
| Structural Surface Vector | Min | Max | Mean | Med | Mode |
|---|---|---|---|---|---|
| Complexity Load (formerly Cognitive Load Exposure) | 0.0 | 89.3 | 2.2 | 0.0 | 0.0 |
| Guard Balance (formerly Error & Exception Exposure) | 0.0 | 100.0 | 3.8 | 0.0 | 0.0 |
| Debt Markers (formerly Tech Debt Exposure) | 0.0 | 97.1 | 0.2 | 0.0 | 0.0 |
| Test Surface (formerly Testing Exposure) | 0.0 | 80.0 | 2.2 | 0.0 | 0.0 |
| Connectivity (formerly API Exposure) | 0.0 | 69.8 | 0.5 | 0.0 | 0.0 |
| Concurrency Surface (formerly Concurrency Exposure) | 0.0 | 100.0 | 0.1 | 0.0 | 0.0 |
| Mutation Surface (formerly State Flux Exposure) | 0.0 | 100.0 | 3.9 | 0.0 | 0.0 |
| Dead Code Surface (formerly Commented Logic Exposure) | 0.0 | 86.9 | 0.1 | 0.0 | 0.0 |
| Historical Stability (predictive layer, promotion pending #2987) (formerly Instability Exposure) | 0.0 | 9.1 | 0.1 | 0.0 | 0.0 |
| Historical Churn (predictive layer, promotion pending #2987) (formerly Volatility Exposure) | 0.0 | 91.5 | 0.7 | 0.0 | 0.0 |
| Doc Surface (formerly Documentation Exposure) _(coverage)_ | 0.0 | 100.0 | 1.1 | 0.0 | 0.0 |
| Credential Material (formerly Hardcoded Payload Artifacts) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

> `Doc Surface (formerly Documentation Exposure)` is **documentation coverage, not a fragility driver**. It is reported for context beside program length, and is deliberately excluded from the ranked-file drivers in this brief: it measures the share of a file's unit weight a reader cannot recover from documentation, so on a codebase that documents little it sits near ceiling everywhere and describes the repo rather than distinguishing files within it.
> `Spec Alignment (formerly Specification Exposure)` was **not measured** on this scan and is therefore absent above rather than reported as 0 (which would assert full alignment). Enable it with `--spec-alignment` if this codebase uses the corresponding convention.

## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)
> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot percentiles are SNAPSHOT-RELATIVE: "87" means this file's value sits at the 87th percentile of THIS repo's files for that surface -- true by construction (Hazen average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid scores above. An all-zero surface across the whole repo reads as 0.0 for every file, never a false-median 50.
| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |
|---|---|---|---|---|
| memory | 1337 | 79 | 0 | `gitgalaxy/core/detector.py` |
| cleanup | 31 | 15 | 0 | `gitgalaxy/galaxyscope.py` |
| guards | 2762 | 97 | 0 | `gitgalaxy/core/detector.py` |
| danger | 1955 | 97 | 0 | `gitgalaxy/core/detector.py` |
| concurrency | 74 | 21 | 0 | `gitgalaxy/core/detector.py` |
| connectivity | 669 | 100 | 0 | `scripts/media/scan_flow_explainer.py` |
| io | 353 | 58 | 0 | `.claude/hooks/session-start.sh` |
| crypto | 5 | 5 | 0 | `gitgalaxy/core/detector.py` |
| ipc | 79 | 15 | 0 | `gitgalaxy/galaxyscope.py` |
| time | 51 | 4 | 0 | `gitgalaxy/galaxyscope.py` |
| serialization | 0 | 0 | 0 | - |
| regex | 743 | 64 | 0 | `gitgalaxy/core/detector.py` |
| events | 313 | 23 | 0 | `gitgalaxy/galaxyscope.py` |
| tests | 6 | 4 | 0 | `.claude/hooks/pytest_quiet.py` |
| docs | 1234 | 105 | 0 | `gitgalaxy/core/detector.py` |
| debt | 242 | 38 | 0 | `gitgalaxy/cobol_to_java_controller.py` |
| mutation | 24380 | 103 | 0 | `gitgalaxy/core/detector.py` |
| dead_code | 103 | 19 | 0 | `gitgalaxy/core/detector.py` |
| credential | 10 | 6 | 0 | `gitgalaxy/core/detector.py` |
| threat | 118 | 20 | 0 | `gitgalaxy/core/rule_prefilter.py` |
| ml_ai | 11 | 8 | 0 | `scripts/media/agents_explainer.py` |
| ui | 31 | 7 | 0 | `scripts/media/scan_flow_explainer.py` |

**Relations (repo medians):**
- `guard_balance_ratio` (guards / (danger + 1)): **0.0**
- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **0.0**

## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES
### Top I/O Latency Risks
- `.claude/hooks/session-start.sh` (Hits: 86)
- `scripts/setup_java_toolchain.sh` (Hits: 17)
- `gitgalaxy/core/prefetch.py` (Hits: 16)

### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)
These are the most interconnected files relative to the rest of this repository. On a repo with dense internal coupling, that means core load-bearing infrastructure -- changes carry real cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may be small, and this list is a weaker signal accordingly; compare the connection counts below before treating it as a verdict.

1. **detector.py** (`gitgalaxy/core/detector.py`) — 207 inbound connections
2. **__init__.py** (`gitgalaxy/tools/cobol_to_java/det/__init__.py`) — 202 inbound connections
3. **source_text.py** (`gitgalaxy/core/source_text.py`) — 156 inbound connections
4. **equivalence_cics.py** (`tests/tools/equivalence_cics.py`) — 129 inbound connections
5. **_shared_patterns.py** (`gitgalaxy/standards/language_standards/_shared_patterns.py`) — 87 inbound connections

### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)
These files pull in the most external dependencies. They are highly coupled and fragile to API changes.

1. **README.md** (`gitgalaxy/tools/cobol_to_java/README.md`) — 98 outbound dependencies
2. **test_ai_ml_import_anchor_4150.py** (`tests/extraction/languages/test_ai_ml_import_anchor_4150.py`) — 82 outbound dependencies
3. **galaxyscope.py** (`gitgalaxy/galaxyscope.py`) — 79 outbound dependencies
4. **BANK.csd** (`tests/cobol_mainframe/refraction_excerpts/cics-banking-sample-application-cbsa/etc/install/base/installjcl/BANK.csd`) — 54 outbound dependencies
5. **equivalence_cics.py** (`tests/tools/equivalence_cics.py`) — 52 outbound dependencies

## 8. CORE FUNCTION HITLIST (Heaviest Functions)
> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*

- `_translate` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_java/det/program.py`) -> Impact: **1636.7** | LOC: 899
- `_slice_by_braces` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1500.0** | LOC: 1478
- `_calculate_block_metrics` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **1019.0** | LOC: 766
- `_build_markdown` **(Many-Argument Workhorses)** (@ `gitgalaxy/recorders/llm_recorder.py`) -> Impact: **927.8** | LOC: 1096
- `run_cobol_cics` **(Many-Argument Workhorses)** (@ `tests/tools/equivalence_cics.py`) -> Impact: **826.4** | LOC: 410
- `score` **(Many-Argument Workhorses)** (@ `tests/tools/cobol_answer_key.py`) -> Impact: **745.4** | LOC: 748
- `splice` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/detector.py`) -> Impact: **683.9** | LOC: 1006
- `resolve_calls` **(Many-Argument Workhorses)** (@ `gitgalaxy/core/call_resolver.py`) -> Impact: **670.8** | LOC: 399
- `Name the Db2 image cache entry (` **(Many-Argument Workhorses)** (@ `.github/workflows/equivalence-e2e.yml`) -> Impact: **577.4** | LOC: 423
  * *Intent:* # #7002: a shard's Db2-backed proof (cbsa-updacc) starts the Db2 container; its cold icr.io pull timed out on main. # Same cache entry and background ...
- `load_galaxy_ir` **(Many-Argument Workhorses)** (@ `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py`) -> Impact: **534.0** | LOC: 807
  * *Intent:* """Loads the latest snapshot of one repo from a master DB, opened read-only."""

*Function archetypes referenced above:*
  * **Many-Argument Workhorses**: large, many-parameter procedural function doing heavy lifting

## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)
| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |
|---|---|---|---|---|
| `tests/cobol_mainframe` | 476 | 57494.9 | 19.19% | 0.0% |
| `gitgalaxy/core` | 74 | 48225.18 | 50.03% | 3.8% |
| `tests/extraction/languages` | 261 | 21342.92 | 13.34% | 0.0% |
| `tests/core_engine` | 206 | 21226.76 | 15.51% | 0.0% |
| `tests/equivalence/cics` | 21 | 13088.47 | 35.0% | 0.0% |
| `tests/cics_crucible` | 59 | 8916.66 | 22.41% | 0.0% |
| `scripts/media` | 11 | 6587.84 | 65.86% | 3.94% |
| `gitgalaxy/recorders` | 8 | 6397.58 | 46.37% | 4.05% |
| `gitgalaxy` | 6 | 4748.04 | 37.51% | 1.6% |
| `gitgalaxy/metrics` | 7 | 4168.66 | 46.37% | 11.14% |

## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)
### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)
- `.github/ISSUE_TEMPLATE/parsing_discrepancy.yml` -> **97.0688%** Exposure
- `gitgalaxy/core/ebcdic_dbcs.py` -> **88.1655%** Exposure
- `gitgalaxy/core/rule_prefilter.py` -> **65.1355%** Exposure
- `gitgalaxy/metrics/archetype_classifier.py` -> **53.2847%** Exposure
- `gitgalaxy/core/prism.py` -> **42.8644%** Exposure
### Highest Mutation Surface (formerly State Flux; Mutation/Volatility)
- `.claude/hooks/pytest_quiet.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_refractor_controller.py` -> **100.0%** Exposure
- `gitgalaxy/cobol_to_java_controller.py` -> **100.0%** Exposure
- `gitgalaxy/core/aperture.py` -> **100.0%** Exposure
- `gitgalaxy/core/bms_screen_fields.py` -> **100.0%** Exposure
### Highest Design Slop (Dead & Duplicated Logic)
- `gitgalaxy/core/mainframe_boundary.py` -> **0** Orphaned Functions | **11** Duplicates
- `gitgalaxy/metrics/archetype_classifier.py` -> **4** Orphaned Functions | **0** Duplicates
- `scripts/media/scan_flow_explainer.py` -> **1** Orphaned Functions | **2** Duplicates
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
- **Unknown Dependencies:** `16990` packages imported that bypass the Zero-Trust whitelist.

## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)
> Ranked by Structural Magnitude: the file's structural weight and centralization within the system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not the vector percentages, is the actionable part.

### `gitgalaxy/core/detector.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: 0.0 IQR)
- **Magnitude:** 14590.54 | **LOC:** 12979 | **CtrlFlow:** 46.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **207** in-repo importer(s); it depends on **28**; blast radius 14.535; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.6%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (91.5%), Test Surface (formerly Verification) (80.0%)
- **Documentation Coverage:** 16.6667% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_slice_by_braces` **(Many-Argument Workhorses)** (Impact: 1500.0)
  * `_calculate_block_metrics` **(Many-Argument Workhorses)** (Impact: 1019.0)
  * `splice` **(Many-Argument Workhorses)** (Impact: 683.9)
  * `_slice_by_keywords` **(Many-Argument Workhorses)** (Impact: 271.5)
  * `_slice_by_indentation` **(Many-Argument Workhorses)** (Impact: 265.4)
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 6 instances
* *Amplified Cascading Flux:* 1926 instances
* *Concurrency (weighted view):* 40
* *State Mutation (weighted view):* 6056
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 3226`, `structural_boundaries: 990`, `args: 188`, `func_start: 179`, `class_start: 6`
* *Risk/State:* `safety_bypasses: 203`, `state_mutation: 2204`, `dead_code: 59`, `planned_debt: 2`, `fragile_debt: 25`
* *Architecture:* `api: 33`, `concurrency: 10`, `import: 37`
* *Defense:* `safety: 64`, `doc: 172`, `immutability_locks: 107`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 14.535
  * `Choke Point (Betweenness):` 0.001518 | `Ripple Effect (Closeness):` 0.06566
  * `Imports (Out-Degree: 17):` bisect, collections, functools, gitgalaxy.core, gitgalaxy.core.call_resolver, gitgalaxy.core.cobol_source_format, gitgalaxy.core.cpp_ctor_forms, gitgalaxy.core.dense_source...
  * `Imported By (In-Degree: 207):` (Excluded from Brief to save tokens)

### `gitgalaxy/galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3708.1 | **LOC:** 4786 | **CtrlFlow:** 27.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **48** in-repo importer(s); it depends on **79**; blast radius 3.31; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.1%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (77.4%)
- **Documentation Coverage:** 19.4737% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_dependency_graph` **(Many-Argument Workhorses)** (Impact: 183.4)
    * *Intent:* """ Pass 1.5: Optimized relational token aggregation & Fuzzy Suffix Matching. Defused O(N^2) Bomb us...
  * `_process_file_worker` **(Many-Argument Workhorses)** (Impact: 170.2)
    * *Intent:* """Processes a single file path using the worker's cached hardware modules."""
  * `execute_pipeline` **(Many-Argument Workhorses)** (Impact: 126.7)
    * *Intent:* """ Executes the synthesis protocol with a multi-recorder exit strategy. PIPELINE ONBOARDING (Execut...
  * `main` **(I/O & Config Routines)** (Impact: 119.0)
    * *Intent:* # ============================================================================== # ORCHESTRATOR CORE...
  * `_calculate_risk_exposures` **(Many-Argument Workhorses)** (Impact: 106.7)
    * *Intent:* """ Phase 3: Universal Exposure Framework & Signal Processing. Translates raw Structural Signatures ...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Mitigated Danger:* 2 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 582 instances
* *High Risk Execution (weighted view):* 2
* *Concurrency (weighted view):* 17
* *State Mutation (weighted view):* 1990
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 821`, `structural_boundaries: 419`, `args: 76`, `func_start: 64`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 158`, `high_risk_execution: 4`, `state_mutation: 826`, `dead_code: 2`
* *Architecture:* `io: 16`, `api: 20`, `concurrency: 7`, `import: 92`
* *Defense:* `safety: 75`, `doc: 53`, `test: 2`, `immutability_locks: 24`, `cleanup: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 3.31
  * `Choke Point (Betweenness):` 0.000857 | `Ripple Effect (Closeness):` 0.016393
  * `Imports (Out-Degree: 51):` argparse, collections, concurrent.futures, copy, datetime, extraction, functools, gitgalaxy.core.aperture...
  * `Imported By (In-Degree: 48):` (Excluded from Brief to save tokens)

### `tests/equivalence/cics/ggcics_web.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_3` (Drift: N/A IQR)
- **Magnitude:** 3602.94 | **LOC:** 1213 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGCWCNV` **(Many-Argument Workhorses)** (Impact: 342.3)
    * *Intent:* /* WEB CONVERSE: GG-NUM the METHOD CVDA (out: STATUSCODE), GG-HOURS PATHLENGTH, GG-MINS QUERYSTRLEN,...
  * `GGCWPRS` **(Many-Argument Workhorses)** (Impact: 326.9)
  * `web_send_body` **(Many-Argument Workhorses)** (Impact: 248.8)
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

### `gitgalaxy/core/call_resolver.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3554.66 | **LOC:** 2794 | **CtrlFlow:** 46.2% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **52** in-repo importer(s); it depends on **7**; blast radius 4.584; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (97.9%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (71.3%)
- **Documentation Coverage:** 20.7921% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `resolve_calls` **(Many-Argument Workhorses)** (Impact: 670.8)
  * `_resolve_one` **(Many-Argument Workhorses)** (Impact: 378.1)
  * `_rust_path` **(Many-Argument Workhorses)** (Impact: 120.2)
    * *Intent:* """#8161 (R1, R3): a Rust call through a path (`a::B::f()`, `crate::m::f()`, `super::f()`; `path` is...
  * `_choose_overloads` **(Many-Argument Workhorses)** (Impact: 102.8)
  * `_init_entry_not_a_base` **(Many-Argument Workhorses)** (Impact: 74.8)
**Contextual Mitigations & Amplifications:**
* *Mitigated Danger:* 1 instances
* *Amplified Cascading Flux:* 354 instances
* *High Risk Execution (weighted view):* 2
* *State Mutation (weighted view):* 1118
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 925`, `structural_boundaries: 324`, `args: 88`, `func_start: 78`, `class_start: 5`
* *Risk/State:* `safety_bypasses: 61`, `high_risk_execution: 3`, `state_mutation: 410`, `dead_code: 6`, `planned_debt: 4`
* *Architecture:* `io: 2`, `api: 23`, `import: 7`
* *Defense:* `safety: 6`, `doc: 62`, `sync_locks: 2`, `immutability_locks: 56`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 4.584
  * `Choke Point (Betweenness):` 2.3e-05 | `Ripple Effect (Closeness):` 0.056948
  * `Imports (Out-Degree: 2):` collections, collections.abc, gitgalaxy.core, gitgalaxy.core.java_arg_types, posixpath, re, typing
  * `Imported By (In-Degree: 52):` (Excluded from Brief to save tokens)

### `gitgalaxy/recorders/llm_recorder.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 3553.58 | **LOC:** 2487 | **CtrlFlow:** 38.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **12** in-repo importer(s); it depends on **17**; blast radius 0.682; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.9%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (72.6%)
- **Documentation Coverage:** 40.3226% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_build_markdown` **(Many-Argument Workhorses)** (Impact: 927.8)
  * `_executive_summary_lines` **(Stateful Encapsulated Methods)** (Impact: 58.0)
  * `_mainframe_facts_lines` **(Stateful Encapsulated Methods)** (Impact: 44.7)
    * *Intent:* """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a file carries them. These ar...
  * `generate_artifacts` **(Many-Argument Workhorses)** (Impact: 42.2)
  * `_source_encoding_lines` **(Stateful Encapsulated Methods)** (Impact: 36.8)
    * *Intent:* """#3813: how the parsed files' bytes became text. One line when every file is UTF-8; otherwise a ta...
**Contextual Mitigations & Amplifications:**
* *Sec High Risk Execution:* 1 instances
* *Amplified Race Conditions:* 2 instances
* *Amplified Cascading Flux:* 554 instances
* *Concurrency (weighted view):* 12
* *State Mutation (weighted view):* 1797
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 682`, `structural_boundaries: 234`, `args: 84`, `func_start: 53`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 105`, `state_mutation: 689`, `planned_debt: 1`, `fragile_debt: 2`
* *Architecture:* `io: 2`, `api: 6`, `concurrency: 2`, `import: 16`
* *Defense:* `safety: 17`, `doc: 25`, `immutability_locks: 1`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 0.682
  * `Choke Point (Betweenness):` 1.4e-05 | `Ripple Effect (Closeness):` 0.012754
  * `Imports (Out-Degree: 5):` collections, collections.abc, gitgalaxy.core.call_resolver, gitgalaxy.core.compiler_options, gitgalaxy.core.function_population, gitgalaxy.metrics, gitgalaxy.standards, heapq...
  * `Imported By (In-Degree: 12):` (Excluded from Brief to save tokens)

### `gitgalaxy/core/mainframe_boundary.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 3019.7 | **LOC:** 2770 | **CtrlFlow:** 41.7% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **60** in-repo importer(s); it depends on **32**; blast radius 4.437; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.7%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (55.7%)
- **Documentation Coverage:** 13.4615% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_cobol_records` **(Many-Argument Workhorses)** (Impact: 319.9)
  * `_cobol_calls` **(Many-Argument Workhorses)** (Impact: 191.4)
  * `_pli_item_attributes` **(Compute Cores)** (Impact: 72.8)
    * *Intent:* """The record_data fields of one item from its attribute tokens, or None when the declaration is not...
  * `_pli_records` **(Stateful Encapsulated Methods)** (Impact: 56.5)
    * *Intent:* """The DECLAREd data items of one PL/I file as a record tree (#3250). Same flat, source-ordered shap...
  * `_jcl_boundary` **(Compute Cores)** (Impact: 49.0)
    * *Intent:* """JCL `EXEC PGM=` steps and the `DD` statements that bind a ddname to a dataset. #3345: alongside t...
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 460 instances
* *State Mutation (weighted view):* 1475
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 728`, `structural_boundaries: 296`, `args: 83`, `func_start: 75`
* *Risk/State:* `safety_bypasses: 99`, `state_mutation: 555`, `dead_code: 2`, `duplicate_logic: 11`
* *Architecture:* `api: 3`, `import: 33`
* *Defense:* `safety: 3`, `doc: 59`, `immutability_locks: 5`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 4.437
  * `Choke Point (Betweenness):` 0.002305 | `Ripple Effect (Closeness):` 0.088934
  * `Imports (Out-Degree: 26):` bisect, collections.abc, gitgalaxy.core.bms_screen_fields, gitgalaxy.core.call_using, gitgalaxy.core.cics_macro_tables, gitgalaxy.core.cics_resources, gitgalaxy.core.cics_tasks, gitgalaxy.core.cobol_conditional...
  * `Imported By (In-Degree: 60):` (Excluded from Brief to save tokens)

### `tests/cics_crucible/test_cics_runtimes.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: N/A IQR)
- **Magnitude:** 2965.02 | **LOC:** 7812 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
  * `_x35_java_steps` **(Stateful Encapsulated Methods)** (Impact: 32.8)
    * *Intent:* """The Java statements for the steps above, printing as the stub's main does."""
  * `test_cics_task_defines_queries_and_wraps_a_fullword_counter_as_the_stub_does` **(Defensive Guards)** (Impact: 31.8)
    * *Intent:* """#5039 (X50): CicsTask.defineCounter / queryCounter / getCounter(.., wrap) answer the scenarios ab...
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
- **Magnitude:** 2562.1 | **LOC:** 6142 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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
- **Magnitude:** 2508.08 | **LOC:** 3985 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **23**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `test_deleteq_ts_and_inquire_association_and_the_receive_map_terminal_option` **(Defensive Guards)** (Impact: 30.6)
    * *Intent:* """#4415 slice 2 (register X29), IBM EXEC CICS DELETEQ TS / INQUIRE ASSOCIATION / RECEIVE MAP: DELET...
  * `test_web_open_converse_close_are_the_tasks_http_client` **(Defensive Guards)** (Impact: 22.7)
    * *Intent:* """#4767 zECS (register X35), IBM WEB OPEN / WEB CONVERSE / WEB CLOSE: OPEN by URIMAP or HOST / HOST...
  * `test_web_browse_forms_are_the_requests_pairs` **(Defensive Guards)** (Impact: 19.9)
    * *Intent:* """#4940 (register X38), IBM WEB STARTBROWSE / READNEXT / ENDBROWSE HTTPHEADER, FORMFIELD, QUERYPARM...
  * `test_inquire_urimap_browse_and_write_operator` **(Defensive Guards)** (Impact: 17.8)
    * *Intent:* """#4270 zECS (register X32), IBM INQUIRE URIMAP ("Browsing resource definitions") / WRITE OPERATOR:...
  * `test_web_send_is_the_response_to_the_stated_request` **(Defensive Guards)** (Impact: 17.8)
    * *Intent:* """#4767 zECS (register X37), IBM WEB SEND (server): CicsTask.webSend takes FROM's text and FROMLENG...
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
- **Magnitude:** 2424.98 | **LOC:** 1972 | **CtrlFlow:** 46.6% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **24** in-repo importer(s); it depends on **22**; blast radius 2.28; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.4%), Test Surface (formerly Verification) (80.0%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (53.7%)
- **Documentation Coverage:** 24.2188% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_resolve_target_unguarded` **(Many-Argument Workhorses)** (Impact: 254.2)
  * `_resolve_by_name` **(Many-Argument Workhorses)** (Impact: 184.3)
  * `_resolve_edges` **(Many-Argument Workhorses)** (Impact: 104.7)
    * *Intent:* """ #2992: resolves every file's raw_imports into directed file-to-file edges, keyed (importer, impo...
  * `build_dependency_graph` **(Many-Argument Workhorses)** (Impact: 68.8)
  * `_resolve_path_mirror` **(Many-Argument Workhorses)** (Impact: 63.3)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 284 instances
* *State Mutation (weighted view):* 889
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 557`, `structural_boundaries: 252`, `args: 56`, `func_start: 55`, `class_start: 1`
* *Risk/State:* `safety_bypasses: 58`, `high_risk_execution: 1`, `state_mutation: 321`, `dead_code: 6`
* *Architecture:* `io: 5`, `api: 10`, `import: 20`
* *Defense:* `safety: 17`, `doc: 48`, `immutability_locks: 16`
* *Network Topology:*
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 2.28
  * `Choke Point (Betweenness):` 0.001039 | `Ripple Effect (Closeness):` 0.049104
  * `Imports (Out-Degree: 10):` collections, collections.abc, gitgalaxy.core.copy_libraries, gitgalaxy.core.go_modules, gitgalaxy.core.graph_engine, gitgalaxy.core.invocation_resolver, gitgalaxy.core.package_self_reference, gitgalaxy.core.path_proximity...
  * `Imported By (In-Degree: 24):` (Excluded from Brief to save tokens)

### `gitgalaxy/metrics/signal_processor.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_4` (Drift: 0.0 IQR)
- **Magnitude:** 2132.46 | **LOC:** 2286 | **CtrlFlow:** 27.4% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **15** in-repo importer(s); it depends on **12**; blast radius 0.926; role: Transceiver (Middle-Tier)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.4%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (63.5%)
- **Documentation Coverage:** 29.3103% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `calculate_risk_vector` **(Many-Argument Workhorses)** (Impact: 256.7)
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
  * `Ecosystem Role:` Transceiver (Middle-Tier) | `Dependency Blast Radius (PageRank):` 0.926
  * `Choke Point (Betweenness):` 1.2e-05 | `Ripple Effect (Closeness):` 0.013324
  * `Imports (Out-Degree: 4):` collections.abc, gitgalaxy.core.function_population, gitgalaxy.core.spatial_correlation, gitgalaxy.metrics, gitgalaxy.standards, gitgalaxy.standards.fidelity_table, logging, math...
  * `Imported By (In-Degree: 15):` (Excluded from Brief to save tokens)

### `gitgalaxy/standards/language_lens.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 2131.92 | **LOC:** 1940 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **10**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `inspect` **(Many-Argument Workhorses)** (Impact: 472.5)
  * `_tier_4_heuristic_discovery` **(Many-Argument Workhorses)** (Impact: 135.5)
    * *Intent:* # ========================================================================= # THE TIER 4 HEURISTIC D...
  * `_evaluate_ecosystem_gravity` **(Many-Argument Workhorses)** (Impact: 103.9)
  * `_tier_3_lexical_scan` **(Many-Argument Workhorses)** (Impact: 76.7)
  * `_library_dir_member_lang` **(Stateful Encapsulated Methods)** (Impact: 43.7)
    * *Intent:* """#8111: `cobol` for an extensionless member whose directory holds COBOL files (a library path: `te...
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* None
* *Risk/State:* None
* *Architecture:* None
* *Defense:* None
* *Network Topology:*
  * `Ecosystem Role:` Unknown | `Dependency Blast Radius (PageRank):` n/a
  * `Choke Point (Betweenness):` n/a | `Ripple Effect (Closeness):` n/a
  * `Imports (Out-Degree: 0):` gitgalaxy.core.source_text, gitgalaxy.standards.gitgalaxy_config, gitgalaxy.standards.language_standards, json, logging, math, os, pathlib...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `gitgalaxy/core/prism.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 2022.26 | **LOC:** 2069 | **CtrlFlow:** 35.5% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **66** in-repo importer(s); it depends on **5**; blast radius 3.347; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (99.8%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (44.8%)
- **Documentation Coverage:** 19.6429% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_strip_single_line_comments` **(Many-Argument Workhorses)** (Impact: 124.2)
    * *Intent:* """ Single-line comment stripper for the "line_exclusive" family, driven by each language's own real...
  * `_strip_single_line_comments_positional` **(Many-Argument Workhorses)** (Impact: 122.2)
    * *Intent:* """Positional sibling of `_strip_single_line_comments`: same per-line masking and carry-quote discip...
  * `_strip_positional_comments` **(Many-Argument Workhorses)** (Impact: 97.5)
  * `_mask_perl_line_positional` **(Many-Argument Workhorses)** (Impact: 75.4)
  * `_mask_perl_line` **(Many-Argument Workhorses)** (Impact: 75.4)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 290 instances
* *State Mutation (weighted view):* 925
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 349`, `structural_boundaries: 182`, `args: 50`, `func_start: 47`, `class_start: 3`
* *Risk/State:* `safety_bypasses: 33`, `state_mutation: 345`, `fragile_debt: 6`, `duplicate_logic: 2`
* *Architecture:* `api: 12`, `import: 5`
* *Defense:* `safety: 4`, `doc: 44`, `immutability_locks: 2`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 3.347
  * `Choke Point (Betweenness):` 1.4e-05 | `Ripple Effect (Closeness):` 0.05561
  * `Imports (Out-Degree: 1):` gitgalaxy.core.cobol_source_format, gitgalaxy.standards.language_standards, logging, re, typing
  * `Imported By (In-Degree: 66):` (Excluded from Brief to save tokens)

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

### `scripts/media/scan_flow_explainer.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1480.88 | **LOC:** 1344 | **CtrlFlow:** 22.9% | **Authorship Centralization:** 100.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **19**; blast radius 0.146; role: Pure Consumer (Orchestrator)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.7%), Complexity Load (formerly Cognitive Load) (62.8%), Historical Churn (predictive layer, promotion pending #2987) (formerly Churn) (15.0%)
- **Documentation Coverage:** 70.7865% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `flow_frames` **(Many-Argument Workhorses)** (Impact: 55.4)
    * *Intent:* """The flow reveals left to right at a constant speed (the clock is linear too). The dots travel as ...
  * `load` **(Many-Argument Workhorses)** (Impact: 43.2)
  * `frame` **(Many-Argument Workhorses)** (Impact: 41.9)
  * `build_flow` **(Compute Cores)** (Impact: 41.8)
    * *Intent:* """Node bars (x, y0, y1) and ribbons between them, in 1x pixels. Ribbon thickness = files (a floor k...
  * `draw_labels_rainbow` **(Many-Argument Workhorses)** (Impact: 39.3)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 226 instances
* *Api Near Db Sink:* 1 instances
* *State Mutation (weighted view):* 756
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 265`, `structural_boundaries: 140`, `args: 51`, `func_start: 45`
* *Risk/State:* `safety_bypasses: 23`, `high_risk_execution: 3`, `state_mutation: 304`, `duplicate_logic: 2`, `unreferenced_by_name: 1`
* *Architecture:* `io: 16`, `api: 44`, `import: 18`
* *Defense:* `doc: 14`, `cleanup: 1`
* *Network Topology:*
  * `Ecosystem Role:` Pure Consumer (Orchestrator) | `Dependency Blast Radius (PageRank):` 0.146
  * `Choke Point (Betweenness):` 0.0 | `Ripple Effect (Closeness):` 0.0
  * `Imports (Out-Degree: 1):` PIL, __future__, _brand, and, argparse, colorsys, datetime, gitgalaxy.standards.language_standards...
  * `Imported By (In-Degree: 0):` None (Orphan / Entrypoint)

### `tests/equivalence/cics/ggcics_taskcontrol.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1369.5 | **LOC:** 932 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGCSTRT` **(Many-Argument Workhorses)** (Impact: 133.7)
  * `GGCDLAY` **(Compute Cores)** (Impact: 83.7)
    * *Intent:* /* #4950: DELAY (IBM, EXEC CICS DELAY), as CicsTask.delay / delayMillis: GG-FLAGS INTERVAL (GG-NUM h...
  * `GGCFETCH` **(Compute Cores)** (Impact: 64.9)
    * *Intent:* /* #4884, #4950: FETCH ANY / FETCH CHILD(token) (IBM, EXEC CICS FETCH), as CicsTask.fetch: GG-FLAGS ...
  * `GGCRTRV` **(Many-Argument Workhorses)** (Impact: 59.6)
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
- **Magnitude:** 1298.52 | **LOC:** 825 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** nothing in-repo imports it (entrypoint or orphan); it depends on **7**
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `run` **(Many-Argument Workhorses)** (Impact: 160.7)
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
- **Magnitude:** 1270.98 | **LOC:** 630 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `browse_read` **(Many-Argument Workhorses)** (Impact: 141.0)
    * *Intent:* /* READNEXT (dir 1) / READPREV (dir -1) FILE(name1) INTO RIDFLD. */
  * `GGCDELT` **(Many-Argument Workhorses)** (Impact: 122.7)
    * *Intent:* /* DELETE FILE(name1) [RIDFLD]: the record with that key, or (no RIDFLD: GG-FLAGS 'HELD') the one a ...
  * `GGCREAD` **(Many-Argument Workhorses)** (Impact: 114.0)
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

### `gitgalaxy/core/aperture.py` (PYTHON | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: 0.0 IQR)
- **Magnitude:** 1267.76 | **LOC:** 1373 | **CtrlFlow:** 33.3% | **Authorship Centralization:** 100.0%
- **Blast Radius:** changing it is visible to **24** in-repo importer(s); it depends on **10**; blast radius 2.085; role: Pure Producer (Foundation)
- **Top Surface Vectors:** Mutation Surface (formerly State Flux) (100.0%), Guard Balance (formerly Safety Score) (98.1%), Test Surface (formerly Verification) (80.0%), Complexity Load (formerly Cognitive Load) (47.4%)
- **Documentation Coverage:** 17.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `_check_artifact_integrity` **(Many-Argument Workhorses)** (Impact: 145.1)
  * `_check_ignore_rules` **(Many-Argument Workhorses)** (Impact: 68.1)
    * *Intent:* """ Determines if the path is in a blocked, ignored, or dynamically infected sector. Implements stan...
  * `evaluate_path_integrity` **(Many-Argument Workhorses)** (Impact: 50.9)
    * *Intent:* """ [GATE 1: Perimeter Gating (Zero-I/O Path Evaluation)] Performs high-speed path analysis to build...
  * `_has_definitions` **(Many-Argument Workhorses)** (Impact: 50.4)
    * *Intent:* """#5460: True when the file carries `need` function definitions outside any data table. The payload...
  * `is_in_scope` **(Many-Argument Workhorses)** (Impact: 36.2)
**Contextual Mitigations & Amplifications:**
* *Amplified Cascading Flux:* 171 instances
* *State Mutation (weighted view):* 565
**Structural Signatures (Net Mitigated Signals):**
* *Structure:* `branch: 287`, `structural_boundaries: 206`, `args: 39`, `func_start: 39`, `class_start: 7`
* *Risk/State:* `safety_bypasses: 21`, `state_mutation: 223`
* *Architecture:* `io: 9`, `api: 16`, `import: 10`
* *Defense:* `safety: 24`, `doc: 37`, `sync_locks: 2`, `immutability_locks: 26`
* *Network Topology:*
  * `Ecosystem Role:` Pure Producer (Foundation) | `Dependency Blast Radius (PageRank):` 2.085
  * `Choke Point (Betweenness):` 0.000139 | `Ripple Effect (Closeness):` 0.059955
  * `Imports (Out-Degree: 4):` fnmatch, gitgalaxy.core.dense_source, gitgalaxy.core.model_magic, gitgalaxy.core.source_text, gitgalaxy.standards.gitgalaxy_config, logging, os, pathlib...
  * `Imported By (In-Degree: 24):` (Excluded from Brief to save tokens)

### `tests/equivalence/cics/ggcics_containers.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_6` (Drift: N/A IQR)
- **Magnitude:** 1241.84 | **LOC:** 798 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `GGCPUTC` **(Many-Argument Workhorses)** (Impact: 103.6)
  * `ccsid_convert_len` **(Many-Argument Workhorses)** (Impact: 62.6)
    * *Intent:* /* convert len bytes of a container's storage; the result is malloc'd, *outlen its length */
  * `GGCGETC` **(Defensive Guards)** (Impact: 54.8)
    * *Intent:* /* GET CONTAINER(GG-QNAME) [CHANNEL] INTO FLENGTH [BYTEOFFSET: GG-NUM] | NODATA (GG-FLAGS); GG-LEN i...
  * `utf8_take` **(Stateful Encapsulated Methods)** (Impact: 46.6)
    * *Intent:* /* strict UTF-8 (no overlong form, no surrogate, nothing past U+10FFFF): the bytes the sequence at s...
  * `GGCMOVC` **(Compute Cores)** (Impact: 39.2)
    * *Intent:* /* ---- #4951: MOVE CONTAINER and the container browse (IBM CICS TS, EXEC CICS MOVE CONTAINER (CHANN...
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

### `tests/equivalence/cics/ggcics_counters.c` (C | Tier 1.5 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_8` (Drift: N/A IQR)
- **Magnitude:** 1241.62 | **LOC:** 563 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
- **Blast Radius:** isolated in the scanned graph -- no in-repo artifact imports it and it imports none
- **Top Surface Vectors:** None above 0%
- **Documentation Coverage:** 0.0% of unit weight undocumented
**Top Internal Functions/Classes:**
  * `counter_step_x` **(Many-Argument Workhorses)** (Impact: 108.5)
    * *Intent:* /* GET with #5039 (X53)'s REDUCE ("the request succeeds with the current value set to the maximum pl...
  * `GGCQCNT` **(Many-Argument Workhorses)** (Impact: 75.0)
    * *Intent:* /* QUERY COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (IBM CICS TS, EXEC CICS QUERY COUNTER; #44...
  * `get_counter_x` **(Many-Argument Workhorses)** (Impact: 70.4)
    * *Intent:* /* GET COUNTER / DCOUNTER with REDUCE, COMPAREMIN, COMPAREMAX (#5039, register X53; IBM, EXEC CICS G...
  * `GGCDCNT` **(Many-Argument Workhorses)** (Impact: 70.0)
    * *Intent:* /* DEFINE COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4270, register X30; #5039, X50; IBM, EX...
  * `GGCDDCN` **(Many-Argument Workhorses)** (Impact: 61.2)
    * *Intent:* /* DEFINE DCOUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4770, register X45; IBM, EXEC CICS DEF...
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

### `tests/core_engine/test_galaxyscope.py` (PYTHON | Tier 2 | AI Safe: 0.0%)
- **Global Archetype:** `file_cluster_15` (Drift: N/A IQR)
- **Magnitude:** 1168.86 | **LOC:** 3074 | **CtrlFlow:** 0.0% | **Authorship Centralization:** 0.0%
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

## 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS
> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.

*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*

## 12.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)
> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).

### 🔥 The Hotspot Matrix (High Volatility + High Risk)
These files are messy, complex, and modified frequently. They are the primary source of developer friction.

- `gitgalaxy/core/detector.py` -> Churn: **91.55%** | Cog Load: 65.9453% | Debt: 12.5712%
- `gitgalaxy/core/call_resolver.py` -> Churn: **71.26%** | Cog Load: 60.1185% | Debt: 8.5084%
- `gitgalaxy/recorders/record_keeper.py` -> Churn: **63.66%** | Cog Load: 50.289% | Debt: 8.691%
- `gitgalaxy/galaxyscope.py` -> Churn: **61.26%** | Cog Load: 77.4369% | Debt: 0.0%
- `gitgalaxy/core/state_rehydrator.py` -> Churn: **58.55%** | Cog Load: 53.7315% | Debt: 0.0%

### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)
These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.

- `gitgalaxy/core/detector.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 14590.54
- `gitgalaxy/galaxyscope.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3708.1
- `gitgalaxy/core/call_resolver.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3554.66
- `gitgalaxy/recorders/llm_recorder.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3553.58
- `gitgalaxy/core/mainframe_boundary.py` -> **Joe Esquibel** (100.0% isolated ownership) | Magnitude: 3019.7

## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)
> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.

### ☣️ Cascading State Flux (Betweenness * State Flux)
These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.

- `gitgalaxy/core/mainframe_boundary.py` -> **Severity: 0.231** (Bridge: 0.0023 * Flux: 100.0%)
- `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py` -> **Severity: 0.179** (Bridge: 0.0018 * Flux: 100.0%)
- `gitgalaxy/core/detector.py` -> **Severity: 0.152** (Bridge: 0.0015 * Flux: 100.0%)
- `gitgalaxy/tools/cobol_to_java/det/cics.py` -> **Severity: 0.107** (Bridge: 0.0011 * Flux: 100.0%)
- `gitgalaxy/core/network_risk_sensor.py` -> **Severity: 0.104** (Bridge: 0.001 * Flux: 100.0%)

### 🃏 House of Cards (Closeness * Error Risk)
These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.

- `gitgalaxy/core/source_text.py` -> **Severity: 15.298** (Embedded: 0.161 * Error Risk: 95.0099%)
- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 11.215** (Embedded: 0.1136 * Error Risk: 98.6853%)
- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 11.102** (Embedded: 0.1118 * Error Risk: 99.3102%)
- `gitgalaxy/core/cobol_source_format.py` -> **Severity: 10.846** (Embedded: 0.1091 * Error Risk: 99.4527%)
- `gitgalaxy/core/compiler_options.py` -> **Severity: 9.54** (Embedded: 0.0963 * Error Risk: 99.0522%)

### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)
These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.

- `gitgalaxy/core/ebcdic_dbcs.py` -> **Severity: 984.927** (Blast Radius: 24.076 * Doc Risk: 40.9091%)
- `gitgalaxy/tools/cobol_to_java/det/cobolrt/Field.java` -> **Severity: 870.0** (Blast Radius: 17.4 * Doc Risk: 50.0%)
- `gitgalaxy/standards/language_standards/_shared_patterns.py` -> **Severity: 867.6** (Blast Radius: 8.676 * Doc Risk: 100.0%)
- `gitgalaxy/standards/language_standards/identifiers.py` -> **Severity: 598.8** (Blast Radius: 14.97 * Doc Risk: 40.0%)
- `gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java` -> **Severity: 587.809** (Blast Radius: 18.474 * Doc Risk: 31.8182%)

## 13. MAINFRAME SYSTEM FACTS (Named Relations & Record Layouts)
> **AI CONTEXT:** Named mainframe relations the structural signal counts flatten -- the call graph (`CALL`/CICS `LINK`·`XCTL`/JCL `EXEC PGM=`), the dataset boundary (`SELECT…ASSIGN` + `OPEN` modes, JCL `DD`→dataset), and record layouts (COBOL DATA DIVISION items, PL/I `DECLARE`d structures). BMS screen maps (every field's position, length and attributes, `screen_field_data`) are the 3270 UI surface. These are the schema of the system: use them to trace which program runs which, which dataset a job binds, and the shape of the records that flow between them. Extracted by the engine (`core/mainframe_boundary.py`) and carried in the master DB (`call_site_data`/`dataset_data`/`record_data`); resolution to files is redone per scan.

- **Coverage:** `162` files carry mainframe facts -- `326` call sites, `101` dataset bindings, `4476` record items.

- **DB2 schemas:** `24` columns of `EXEC SQL DECLARE ... TABLE` (inline or DCLGEN members), full shape in `sql_table_data`.

- **DB2 table access:** `131` embedded SQL statements touching `15` tables (SELECT/INSERT/UPDATE/DELETE, cursors, host variables) in `sql_statement_data`; the program x table read/write matrix is `GalaxyIR.sql_table_access()`.

- **CICS resources:** `263` CSD `DEFINE` records (FILE→DSNAME, TDQUEUE, DB2TRAN→DB2ENTRY→PLAN, MAPSET, LIBRARY, ...), full attributes in `csd_resource_data`.

- **CICS operations:** `168` EXEC CICS operations naming a resource (`10` CHANNEL, `29` CONTAINER, `30` FILE, `86` MAP, `9` QUEUE, `4` WEB); verb, direction, VALUE-resolved name and INTO/FROM record in `cics_resource_data`.

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

*(+142 more files with mainframe facts; full detail in `record_data`/`call_site_data`/`dataset_data`.)*

- **Mainframe skeleton completeness:** 46% (mean channel ratio; channel table in the audit report, section 7). Top missing inputs: application programs (source or load-module list) (87 gaps); BMS map sources (58 gaps); CSD extract (DFHCSDUP LIST / CICSPlex SM), or the web / API layer that LINKs it (20 gaps).

## 14. PROJECT IDIOM WRAPPERS (Hidden Literal Vocabulary)
> **AI CONTEXT:** Project-local helpers that wrap a literal primitive (print, abort, allocation). Their call sites are NOT in the literal signal counts above -- read a low `debug_prints`/`panics_and_aborts`/`memory_alloc` count together with this list. Full detail in `wrapper_data`.

- **`debug_prints`:** 158 literal sites + 157 sites through wrappers = 315
- **`memory_alloc`:** 0 literal sites + 8 sites through wrappers = 8
- **`panics_and_aborts`:** 147 literal sites + 166 sites through wrappers = 313

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
- `refuse` (function, debug_prints, primitive): 6 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
- `refuse` (function, panics_and_aborts, primitive): 6 call sites in 1 files -- `tests/equivalence/cics/ggcics.c`
*(+28 more in `wrapper_data`.)*

## 15. FUNCTION CALL RESOLUTION (Call Graph Confidence)
> **AI CONTEXT:** Each function's callee names, linked to the definition they most plausibly mean. *scoped* = same class/file, an imported file, or a class-qualified call; *unique* = the only definition in the repository; *ambiguous* = several candidates or an untyped receiver (never a graph edge); *external* = defined nowhere here (built-ins, packages). A high scoped/unique share means the resolver made a confident choice, not that the choice was correct; resolution accuracy is measured separately (gitgalaxy#3332). Detail in `fcall_data` / `fcall_rate_data`.

- **Repository:** 141547 call pairs -- scoped 29.1%, unique 0.2%, ambiguous 15.7%, external 55.0%

| Language | Pairs | Scoped | Unique | Ambiguous | External |
|---|---|---|---|---|---|
| python | 117018 | 27.5% | 0.0% | 15.3% | 57.2% |
| java | 21526 | 36.3% | 0.0% | 19.5% | 44.2% |
| c | 2433 | 30.9% | 12.1% | 5.3% | 51.7% |
| cobol | 386 | 93.0% | 0.8% | 1.3% | 4.9% |
| javascript | 88 | 11.4% | 0.0% | 0.0% | 88.6% |
| jcl | 50 | 0.0% | 0.0% | 0.0% | 100.0% |
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
