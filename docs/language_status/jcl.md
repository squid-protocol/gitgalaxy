# JCL (IBM z/OS JCL)

## 1. At a glance

| Metric | Value |
| :--- | :--- |
| **Status** | production |
| **Target Version** | IBM z/OS JCL |
| **Lexical Family** | line_exclusive |
| **Rules Wired** | 11 / 24 |
| **Extraction tests** | 41 |
| **Strict tests** | 51 |

## 2. Identification surface

- **Extensions**: `.jcl`, `.prc`, `.bms`
- **Exact matches**: (none)
- **Discriminators**: `.cbl`, `.cob`, `.cpy`
- **Shebangs**: (none)

## 3. What GitGalaxy detects

**Topology & Structure**
- `branch`: Matches conditional structures like `IF`, `ELSE`, `ENDIF`.
- `args`: Matches step parameters (`PARM=`) and proc arguments (`PROC ...`).
- `structural_boundaries`: Matches structural statements and commands (`DD`, `INCLUDE`, `SET`, `PROC`, `PEND`).
- `func_start`: Matches JCL EXEC steps.
- `class_start`: Matches JCL JOB cards.

**Safety & Risk**
- `high_risk_execution`: Matches execution of specific programs via `PGM=`.

**Resource Management**
- `io`: Matches dataset definitions and I/O routing such as `DSN`, `DSNAME`, `SYSOUT`, `SYSPRINT`, `DISP=`.

**State Mutation**
- `state_mutation`: Matches JCL symbolic variable assignments via `SET`.

**Architecture & Domain Sensors**
- `import`: Matches JCL includes (`INCLUDE`).
- `_dependency_capture`: Captures the `MEMBER=` name for the dependency graph, as well as dataset names in `DD` statements and `JCLLIB` orders.
- `ownership`: Matches ownership/maintainer comments like `//* Author:`.

## 4. What GitGalaxy explicitly does not track

- `safety`: None (JCL doesn't have traditional code equivalents for these, kept null to prevent crashes).
- `api`: None (JCL doesn't have traditional code equivalents for these, kept null to prevent crashes).
- `concurrency`: None.
- `ui_framework`: None.
- `closures`: None.
- `globals`: None.
- `decorators`: None.
- `generics`: None.
- `comprehensions`: None.
- `scientific`: None.
- `reflection_metaprogramming`: None.
- `telemetry`: None.
- `debug_prints`: None.

## 5. Known limitations (accepted, not fixed)

None currently. ([#2415](https://github.com/squid-protocol/gitgalaxy/issues/2415) — `aperture.py`'s
`infra_path_pattern` had no left word boundary, so `MAPGEN.jcl` (matched `gen`) and `DBRMLIB.jcl`
(matched `lib`) were dropped before extraction — was found by the §9 manual-verification pass and
**fixed**; see §9.)

## 6. Test depth

- **Extraction-gauntlet tests**: 41 cases in `tests/extraction/languages/test_jcl.py`
- **Strict-signature tests**: 51 cases in `tests/extraction/languages/test_jcl_strict.py`

## 7. Relevant closed work

- **Epic-level hardening passes vs real bugs**:
  - [#850](https://github.com/squid-protocol/gitgalaxy/issues/850): Extraction hardening: jcl
  - [#590](https://github.com/squid-protocol/gitgalaxy/issues/590): Strict parsing tests: `jcl` structural signatures
- **Cross-language fixes**:
  - [#1975](https://github.com/squid-protocol/gitgalaxy/issues/1975): jcl and m4 (and possibly makefile) have the same Mode B brace-search func_start recall bug as dockerfile/abap/scheme

## 8. Real-world evidence

- [`jcl-assess`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/jcl-assess/jcl-assess_galaxy_llm.md) - A dedicated assessment project demonstrating pure JCL scanning.
- [`cics-genapp`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/cics-genapp/cics-genapp_galaxy_llm.md) - IBM's standard CICS General Insurance Application sample, showcasing JCL operating alongside COBOL in a larger mainframe system.
## 9. Manual verification (no comparison tool)

JCL has no tree-sitter or ctags parser available for the tri-comparison tool, so its precision
and recall are verified by hand and recorded in `docs/self_scan/manual_verification.json` (read
directly by `tri_comparison_chart.py` to render the `**` marker and award GitGalaxy's badge). See
`docs/self_scan/how_to_investigate_a_discrepancy.md` for the methodology and the
`tri-comparison-ledger-sweep` skill's manual-verification fallback for the procedure.

### 2026-08-30: re-verified against the v1.2.0 corpus expansion

`language-crucible` v1.2.0 (pin bumped in [#2478](https://github.com/squid-protocol/gitgalaxy/pull/2478))
added one `.jcl` file — `cics-java-jcics-samples/etc_VSAM_DEFVSAM.jcl`, an IDCAMS VSAM-cluster
define job — bringing JCL's corpus to **186 `.jcl` files across 6 repos** (185 pipeline-scanned).
#2478 bumped the pin without refreshing `manual_verification.json`, so the 2026-08-29 record
(`375 / 117`) went stale against the pinned corpus and JCL's precision panels dropped back to a
bare `0/376` / `0/118` with no badge. This pass re-established the record.

**Method.** The same three independent readings as the 2026-08-29 pass, over the whole v1.2.0
corpus: GitGalaxy's own `func_start` / `class_start` regex; an independent line scanner sharing no
implementation; and a `galaxyscope --db-only` pipeline cross-check (`struct_*` vs. `*_count` vs.
`function_data` / `class_data` row counts), per file.

| Signature | Corpus truth | Independent scanner | Pipeline | False positives | Misses |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `func_start` (EXEC steps) | **376 / 376** | 376 | 376 | 0 | 0 |
| `class_start` (JOB cards) | **118 / 118** | 118 | 118 | 0 | 0 |

- The single new file contributes exactly **one EXEC step** (`//DEFINE EXEC PGM=IDCAMS`) and
  **one JOB card** (`//DEFVSAM JOB`). Its instream IDCAMS control statements (`DELETE`,
  `DEFINE CLUSTER`) between `//SYSIN DD *` and `/*` are correctly **not** matched — the same
  SYSIN-payload rejection the 2026-08-29 pass verified, holding on new content.
- Net effect of the v1.2.0 expansion is `+1 / +1`. No engine change, no new defect, no
  regression: every other JCL count is identical to the 2026-08-29 reading, and per-file
  `struct_*` still equals the raw regex count on every scanned file.
- `DFH$SIP1.jcl` remains the one correctly-unscanned `.jcl` (SIP parameter deck, `*`-prefixed
  lines, zero real signatures).

**Chart records** (`manual_verification.json`, `2026-08-30`): Functions `376 / 376`, Classes
`118 / 118`. Args unchanged — still `none`-granularity, no entry.

### 2026-08-29: re-verified against the v1.1.0 corpus expansion

`language-crucible` v1.1.0 (pin bumped in [#2398](https://github.com/squid-protocol/gitgalaxy/pull/2398))
grew JCL's corpus from **3 files** to **185 `.jcl` files / ~8.7k lines** across five IBM
mainframe sample repos (`cash-account-cobol`, `cics-banking-sample-application-cbsa`,
`cics-genapp`, `cobol-programming-course`, `zopeneditor-sample`). The 2026-08-23 3-file record
(3/3/1) went stale, dropping JCL's precision panels to a bare `0/370` / `0/116` with no badge.
This pass re-established the record against the full corpus.

**Method.** Two independent readings per signature, sharing no implementation:

1. GitGalaxy's own `func_start` / `class_start` regexes applied directly to raw source text
   across all 185 files.
2. An independent line scanner (skip any line starting `//*`; `^//([A-Za-z0-9#$@]{1,8})\s+JOB\b`
   for JOB cards, `^//([A-Za-z0-9#$@]{0,8})\s+EXEC\s` for EXEC steps).

Plus a step-2b pipeline cross-check: `file_data.struct_func_start` / `struct_class_start` from a
real `galaxyscope --db-only` run, per file, against the raw regex count.

| Signature | Corpus truth | Independent scanner | False positives | Misses | Pipeline (`struct_*`) vs. raw, per scanned file |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `func_start` (EXEC steps) | **375 / 375** | 375 | 0 | 0 | identical on all 184 scanned files |
| `class_start` (JOB cards) | **117 / 117** | 117 | 0 | 0 | identical on all 184 scanned files |

- **100% precision, 100% recall** for both signatures across the whole corpus. GitGalaxy
  correctly rejects every `//*`-commented JOB/EXEC line, every keyword buried in inline SYSIN
  card data, and the `//<CMASAPPL> JOB` angle-bracket template placeholder in `sampcma.jcl` /
  `sampwui.jcl`. A naive `^//\S+\s+JOB` grep's 15 extra "hits" are all such noise.
- **Extraction path is clean.** For every one of the 184 files the pipeline scans, the raw regex
  count equals `struct_*` exactly — no `prism.py` comment-splitter corruption, no `detector.py`
  body-slicing drop. Mode A (greedy-to-next-label) slicing is correct for JCL, which has no
  brace-delimited bodies. `DFH$SIP1.jcl` is the one `.jcl` file not scanned, correctly: it is a
  SYSIN parameter deck (`*`-prefixed lines, no `//` statements) with zero real signatures.

**One engine defect found and fixed**
([#2415](https://github.com/squid-protocol/gitgalaxy/issues/2415)): `aperture.py`'s
`infra_path_pattern` "Semantic Path Shield" had an optional `[-_./\\]?` prefix and no left word
boundary, so an infra word (`gen` / `lib` / `out` / `test` / `spec` / `build` / …) matched as the
*suffix* of any path component sitting right before a `.` or `/` — `MAPGEN.jcl` (`gen`),
`DBRMLIB.jcl` (`lib`) — dropping those files at the perimeter before extraction. Not JCL-specific:
the same pass fixed 23 wrongly-excluded files across 12 languages (`codegen.c`, `layout.html`,
`autogen.sh`, `Alamofire.podspec`, `speedtest.tcl`, `CommonLibrary.psm1`, …). Fixed by requiring
a real left boundary (`(?:^|[-_./\\])`); both golden masters re-blessed in the same PR.

**Chart records** (`manual_verification.json`, keyed to GitGalaxy's live claim count as the
staleness anchor — a PRECISION record):

- **Functions (EXEC steps)**: `375 / 375` verified — every EXEC step the engine extracts is a
  real one, and nothing real is missed anywhere in the corpus. (Was `370 / 370` before #2415's
  fix restored `MAPGEN.jcl` / `DBRMLIB.jcl`.)
- **Classes (JOB cards)**: `117 / 117` verified — same standard. (Was `116 / 116` pre-fix.)
- **Args**: JCL `func_start` matches `EXEC` job steps, a document-structural marker with no
  parameter-list concept at any granularity (`ARGS_GRANULARITY["jcl"] == "none"`). The chart
  shows GitGalaxy's raw `PARM=` / PROC-symbolic signal count with the granularity marker and no
  `**` — there is nothing to verify, so JCL carries no `args` entry in `manual_verification.json`
  (same as `dockerfile`, the other `none`-granularity gg-only language). The 2026-08-23 `1/1`
  args entry was removed. For the record, GitGalaxy's `args` regex matches 28 real `PARM=`
  strings / PROC symbolic-parameter declarations across the full corpus, zero spurious. Two
  known, accepted proxy imprecisions, neither worth its own issue since the metric is `none`:
  (1) the line-anchored `args` regex only sees `PARM=` when it sits on the `EXEC` line itself, so
  ~16–18 `//` continuation-line `PARM=(...)` occurrences (`asmmap.jcl`, `BATCH.jcl`, `CICS.jcl`,
  `CICSTS56.jcl:45`, `cobol.jcl:68`, `defdrep.jcl:39`, …) are not counted; (2) the per-step
  `Occurrence.args` values feeding `gg_args_found` (`24‡`) are `0` for 352 steps, `1` for 17
  (a `PARM=` is present), and `7` for one — `ZOSCSEC.jcl`'s `BPXIT` step, a mild over-count where
  Mode A's unbounded args search (see [#1973](https://github.com/squid-protocol/gitgalaxy/issues/1973))
  sweeps a multi-line `PARM='SH chmod …'` string.
