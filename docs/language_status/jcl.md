# JCL (IBM z/OS JCL)

## 1. At a glance

| Metric | Value |
| :--- | :--- |
| **Status** | production |
| **Target Version** | IBM z/OS JCL |
| **Lexical Family** | line_exclusive (with a dedicated `//*` whole-line stripper — see §10) |
| **Rules Wired** | 16 / 27 |
| **Extraction tests** | 42 |
| **Strict tests** | 65 |

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
- `safety`: Matches `COND=` return-code tests (JCL's step error-handling); the bare bypass forms are excluded by lookahead. Added by [#2610](https://github.com/squid-protocol/gitgalaxy/issues/2610).
- `safety_bypasses`: Matches `COND=EVEN` / `COND=ONLY` (run the step despite a prior abend — JCL's native ignore-the-error idiom). The combined form `COND=((4,LT),EVEN)` deliberately counts **both** safety and bypass: it carries a real RC test and a run-after-abend bypass at once. Added by #2610.

**Resource Management**
- `io`: Matches dataset definitions and I/O routing such as `DSN`, `DSNAME`, `SYSOUT`, `SYSPRINT`, `DISP=`.

**State Mutation**
- `state_mutation`: Matches JCL symbolic variable assignments via `SET`.

**Architecture & Domain Sensors**
- `import`: Matches JCL includes (`INCLUDE`).
- `_dependency_capture`: Captures the `MEMBER=` name for the dependency graph, as well as dataset names in `DD` statements and `JCLLIB` orders.
- `ownership`: Matches ownership/maintainer comments like `//* Author:` (counted on the comment stream since #2610 — previously it only worked by accident on the code stream, see §10).
- `telemetry`: Matches `MSGLEVEL=` / `MSGCLASS=` (job-log verbosity and routing — JCL's observability dials). Added by #2610.
- `planned_debt` / `fragile_debt`: The shared `GLOBAL_PLANNED_DEBT` / `GLOBAL_FRAGILE_DEBT` comment-anchored patterns (same wiring as cobol) — a `//* TODO ...` / `//* HACK ...` banner in a job deck now counts. Added by #2610; structurally dead before it because JCL's comment stream was always empty (§10).

## 4. What GitGalaxy explicitly does not track

- `api`: None (JCL has no api rule; in practice `api` still appears on scanned JCL via the
  orphan-conversion mechanism — see the keyword-rosetta ledger's `api-contextual-baseline-fix`).
- `cleanup`: None — **a deliberate decision, not an oversight** (#2610): the honest JCL cleanup
  idiom is `DISP=(...,DELETE)`, but `DISP=` already feeds the `io` rule, so a cleanup rule would
  double-count every disposition. Recorded in the keyword-rosetta deviation ledger
  (`jcl-2610-rebaseline-residual-morphology`) as intended morphology.
- `globals`: None — JCL has no scoped-vs-global variable distinction (`SET` symbolics are already
  `state_mutation`; a `JOBLIB`/`STEPLIB` rule was considered and rejected because those DD
  statements would inflate `io` and `dependency_links`).
- `concurrency`: None.
- `ui_framework`: None.
- `closures`: None.
- `decorators`: None.
- `generics`: None.
- `comprehensions`: None.
- `scientific`: None.
- `reflection_metaprogramming`: None.
- `debug_prints`: None.

## 5. Known limitations (accepted, not fixed)

None currently. ([#2415](https://github.com/squid-protocol/gitgalaxy/issues/2415) — `aperture.py`'s
`infra_path_pattern` had no left word boundary, so `MAPGEN.jcl` (matched `gen`) and `DBRMLIB.jcl`
(matched `lib`) were dropped before extraction — was found by the §9 manual-verification pass and
**fixed**; see §9.)

## 6. Test depth

- **Extraction-gauntlet tests**: 42 cases in `tests/extraction/languages/test_jcl.py`
- **Strict-signature tests**: 65 cases in `tests/extraction/languages/test_jcl_strict.py`
  (grew 51 → 65 with #2610's COND-partition semantics, JES3-guard, and ReDoS detonation cases)

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

  *(Update: both proxy imprecisions above were subsequently fixed — continuation-line `PARM=` by
  [#2482](https://github.com/squid-protocol/gitgalaxy/issues/2482)'s bounded continuation-hop
  addition to the `args` regex, and the `BPXIT` sweep by
  [#2483](https://github.com/squid-protocol/gitgalaxy/issues/2483)'s args-count bound. The dated
  records above are kept as written; the metric remains `none`-granularity either way.)*

## 10. Rosetta cross-language consistency (control-corpus capstone)

This section is the [keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta)
counterpart of §9: where §9 asks "is JCL extraction *accurate* on real code?", the rosetta
control corpus asks "does GitGalaxy measure *identical planted intent* the same in JCL as in the
other 45 languages?" — every deviation from the 46-language median is measured bias, tracked in
[#2581](https://github.com/squid-protocol/gitgalaxy/issues/2581) (epic
[#2560](https://github.com/squid-protocol/gitgalaxy/issues/2560)) and validated in the corpus's
[deviation ledger](https://github.com/squid-protocol/keyword-rosetta/blob/main/deviation_ledger.json).

**Summary (2026-08-31).** JCL went from **13🔴 / 7🟡** out-of-band metrics (4th-worst of 46) to
**6🔴 / 8🟡** (mid-pack) in one pass: gitgalaxy [#2610](https://github.com/squid-protocol/gitgalaxy/issues/2610)
(PR [#2611](https://github.com/squid-protocol/gitgalaxy/pull/2611)) plus keyword-rosetta
[PR #4](https://github.com/squid-protocol/keyword-rosetta/pull/4). The 20 tracked deviations
decomposed into exactly five causes, each with a different fix path — recorded here because the
*taxonomy* is the reusable part (see the keyword-rosetta `rosetta-language-sweep` skill):

1. **One real engine bug** (#2610, fixed): prism never stripped `//*` comments — jcl's
   `line_exclusive` delimiter list is deliberately empty (`//` also prefixes every statement, so
   the stateless per-line stripper cannot express a whole-line positional prefix), and no
   positional path existed either. Every `//*` line sat in the *code* stream: `doc_loc` was 0 for
   all JCL, `comment_analysis` (doc/ownership/debt) ran on an empty string engine-wide, and
   `ownership` only counted by accident via `coding_analysis` on the wrong surface. Fixed with a
   dedicated line-count-preserving `_strip_jcl_comments` partition, guarded (case-sensitively)
   for the ten JES3 `//*`-prefixed control verbs, which are statements, not comments.
2. **Missing rules with genuine JCL morphology** (#2610, added): `safety` = `COND=` RC-tests,
   `safety_bypasses` = `COND=EVEN/ONLY`, `telemetry` = `MSGLEVEL=/MSGCLASS=`, and the shared
   comment-anchored debt patterns (§3). These were recorded as "JCL doesn't have equivalents",
   which was wrong — JCL's error-handling, error-*ignoring*, and log-verbosity idioms are real
   and risk-relevant for legacy modernization.
3. **A corpus authoring gap, not morphology**: `args` measured 1 vs median 13, but JCL expresses
   per-step arguments (`PARM=`) and the engine rule already handled them (#2482) — the rosetta
   shell had simply under-planted. Re-authored with `PARM=` on all 13 EXEC steps → exactly at
   median. Lesson: check whether the language *could* express the spec before ledgering a
   structure deviation as morphology.
4. **Intended morphology, ledgered** (`jcl-2610-rebaseline-residual-morphology`, validated):
   `cleanup`/`doc`/`test`/`globals` zeros (§4 reasoning), `dependency_links` 4 vs 3 (the DD
   `DSN=` capture is deliberate blast-radius design — datasets *are* JCL dependencies), and the
   `comment_lines` residual (JCL permits no blank lines; the metric's `total_loc − coding_loc`
   proxy counts other languages' blank-line style as comment mass).
5. **Median inflation by other languages' bugs — JCL is the honest one**: `branch` 3 and
   `state_mutation` 2 match planted intent exactly; their out-of-band standing is the
   return-counts-as-branch family ([#2545](https://github.com/squid-protocol/gitgalaxy/issues/2545))
   and the ×3 flux weighting ([#2546](https://github.com/squid-protocol/gitgalaxy/issues/2546))
   inflating the cross-language median. No JCL action; re-baselines when those land.

**Remaining out-of-band** (all accounted, none actionable at the JCL level): the bucket-4
morphology zeros (final disposition is the epic's scoring-side "absent morphology = incomparable"
work), the bucket-5 metrics (blocked on #2545/#2546), and the §3 risk-score consequences
(downstream shadows; the epic forbids tuning risk formulas against biased inputs).

Reproduce: `GALAXYSCOPE_BIN=<venv>/bin/galaxyscope python tools/verify_language.py jcl` in the
corpus repo (gate: 76 assertions), `python tools/language_deviations.py jcl` for the live
vs-median band table, and the corpus's
[findings_by_language.md#jcl](https://github.com/squid-protocol/keyword-rosetta/blob/main/docs/findings_by_language.md#jcl) /
[bias chart](https://github.com/squid-protocol/keyword-rosetta/blob/main/docs/bias_variance_chart.svg).
