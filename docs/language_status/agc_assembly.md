# AGC Assembly — Structural Signature Coverage

Snapshot generated 2026-08-20 against `main`. Source: `LANGUAGE_DEFINITIONS["agc_assembly"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_agc_assembly.py` /
`test_agc_assembly_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

Section 9 (measured accuracy) below is a tri-comparison writeup, not a single-ground-truth
comparison — agc_assembly has no tree-sitter grammar, so the only other tool in the picture is
ctags, and unlike Python-vs-`ast` neither side gets to be assumed correct by default.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Apollo Guidance Computer (Luminary 099 / Comanche 055 — Apollo 11) |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `line_exclusive` (single `#` line comments; digitized AGC source has no block-comment syntax at all) |
| Structural signature keys wired | 39 / 48 (9 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_agc_assembly.py`) | 155 |
| Strict-signature tests (`test_agc_assembly_strict.py`) | 76 |
| Total dedicated agc_assembly test cases | 231 |

## 2. Identification surface

- **Extensions:** `.agc` — the only real extension digitized Apollo Guidance Computer source ships
  under.
- **Exact filenames:** none. Inline comment: "AGC code is hardware-level; no extensionless exact
  configurations exist."
- **Discriminators:** `.agc`, `yaYUL` — the sibling extension plus the modern assembler/emulator
  toolchain name used to lock in historical context.
- **Shebangs:** none. Inline comment: "AGC code is hardware-level or emulator-resident; no
  shebangs exist."

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` uses for this entry. Description is what
agc_assembly's *actual* regex captures, not the generic cross-language definition.

**Phase 1: Logic topology & structure**
| Key | What it captures for agc_assembly |
|---|---|
| `branch` | Conditional/jump opcodes: `TC TCF BZF BZMF BZE BMN BPL BMI CCS RESUME RETURN TCR OVSK BVBZ CALL GOTO` — deliberately excludes fatal-alarm instructions, which live under `high_risk_execution` instead. |
| `args` | Hardware registers (`A Q L Z`) only when explicitly coupled to a real AGC math/memory opcode (`CA CS TS AD SU MULT DV MASK DXCH LXCH QXCH XCH INDEX AUG DIM INCR CCS`), plus `EBANK=`/`FBANK=`/`BBANK=` bank-assignment declarations. |
| `structural_boundaries` | Standard instruction-flow and data-marker opcodes: `CA CAF CS TS DXCH LXCH QXCH XCH AD SU MULT DV MASK CCS SETLOC BANK COUNT ADRES OCTAL 2OCT DEC 2DEC BLOCK ERASE`. |
| `func_start` | A same-line label followed (within `[ \t]+`, never crossing a newline) by one of ~41 real subroutine-entry opcodes — the union of every opcode this file's other rules already vet as legitimate (`TC/TCF/CA/CAF/CS/TS/DXCH/LXCH/QXCH/XCH/CCS/DLOAD/STORE/CALL/INDEX/EXTEND/INHINT/RELINT/EDRUPT/BZF/BZMF/BPL/BMI/BZE/BMN/RESUME/RETURN/TCR/GOTO/OVSK/BVBZ/AD/ADS/SU/MULT/DV/MASK/INCR/AUG/DIM/DAS/RVQ`). Data/constant pseudo-ops (`OCT`, `OCTAL`, `DEC`, `2DEC`, `ADRES`, `EQUALS`, ...) are deliberately excluded — they mark data declarations, not subroutine entries. |

**Phase 2: Risk & structural integrity**
| Key | What it captures for agc_assembly |
|---|---|
| `safety` | Interrupt-control and defensive guards: `INHINT RELINT TC DOWNRUPT CS ERESTORE MUST RESTORE EDRUPT`. |
| `safety_bypasses` | Task-management risk shortcuts: `TC JOBSLEEP TC JOBWAKE TCF 2 TASKOVER TCF ADRERR`. |
| `high_risk_execution` | Fatal alarm/failure states: `CURTAINS SOFTWARE RESTART SYSTEM_FAILURE WHIMPER HALT`. Excludes MOD-history text, which is Phase 4 debt tracking. |
| `io` | Hardware I/O bridging to the Command/Lunar Module: `DSKY CHANNEL READ WRITE`, DSKY verb/noun pairs (`V\d+N\d+`), and `OUT\d+`/`IN\d+` channel I/O. |
| `api` | Global `EQUALS` label declarations and `SUBROUTINE`/`BEXT`/`EXTEND` entry markers — the closest AGC equivalent to a public surface. |
| `state_mutation` | Register/memory writes: `TS DXCH LXCH QXCH XCH INCR AUG DIM WRSUB AUGMENT DIMINISH STORE STQ STCALL DAS`. |
| `dead_code` | Commented-out opcode lines: `#` followed by `TCF CCS INDEX BZF BZN CA CS`. |
| `doc` | Structured header comments: `# Page`, `MOD BY`/`MOD NO`, `FUNCTIONAL DESCRIPTION`, `SUBROUTINE`, `PURPOSE`, `CALLING SEQUENCE`, `AUTHOR`, `PROGRAM`, `REVISION`. |
| `test` | System self-check instructions: `TC ALARM2 SELFCHECK ROPECHK ERASCHK CNTRCHK CHECK TC BANKJUMP`. |

**Phase 3: Architecture & domain sensors**
| Key | What it captures for agc_assembly |
|---|---|
| `concurrency` | The priority multitasking scheduler and task-management vocabulary: `PRIO1`–`PRIO9`, `EXEC`, `TC NOVAC`, `TC WAITLIST`, `TC FINDVAC`, `ENDOFJOB`, `PHASCHNG`, `AWAKE`, `SLEEP`, `VARDELAY`. |
| `ui_framework` | DSKY (Display/Keyboard) UI vocabulary: `V \d+`, `N \d+`, `NOUN`, `VERB`, `ENTER`, `PROCEED`. |
| `globals` | Memory-division markers: `ERASABLE MEMORY`, `FIXED MEMORY`, `WORKING-STORAGE`, `COMMON`, `FLAGWRD\d+`, `BIT\d+`. |
| `scientific` | The AGC interpreter's vector-math/orbital-navigation opcode set: `VAD VSUB BDSU DDV DMP DSU SQRT NORM SIGN ABS SIN COS ASIN ACOS SPCOS SPSIN DOT CROSS UNIT ABVAL VXV VXM MXV`. |
| `reflection_metaprogramming` | Self-modifying/interpreter-entry constructs: `INDEX`, `TC INTPRET`, `DXCH 0000`, `RVQ`. |
| `import` | Module/bank inclusion markers: `BANK`, `SETLOC`, `EBANK=`. |
| `_dependency_capture` | Extracts the target symbol from `BANK`, `SETLOC`, and `EBANK=` lines (feeds the dependency DAG). |
| `ownership` | Header authorship metadata: `# MOD BY`, `AUTHOR`, `CREATED BY`, `MAINTAINER`, `Contact:`. |

**Phase 4: Specialized subsystems**
| Key | What it captures for agc_assembly |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers, same as every other language. |
| `spec_exposure` | Mission/spec traceability tags: `GSOP LUMINARY COMANCHE COLOSSUS SUNDISK SUNBURST`, `PCR \d+`, `PCN \d+`, `SPEC-\d+`, `# REF:`. |
| `events` | Hardware interrupt vectors ("rupts"): `RUPT TIME1 TIME2 KEYRUPT UPRUPT DOWNRUPT RADAR OPTIC HANDRUPT ERRUPT`. |
| `macros` | Assembler macro directives: `MACRO`, `ENDMAC`, `DEFINE`. |
| `pointers` | Address/indirection constructs: `INDEX INDIRECT POINTER CADR FCADR ECADR`, plus a leading `*` address-reference sigil. |
| `memory_alloc` | Memory-declaration keywords: `ERASABLE FIXED EQUALS SHARE`. |

**Phase 5: Resource management & stability**
| Key | What it captures for agc_assembly |
|---|---|
| `telemetry` | Spacecraft downlink routines: `DNTM DOWNLINK TELEM TM DUMPTEL`, `TM WORD`. |
| `debug_prints` | DSKY/display artifacts: `FLASH PINBALL OUT\d+`. |
| `explicit_casts` | `EXTEND` — the AGC's own "next instruction uses the extended opcode set" prefix, the nearest analog to an explicit type/mode cast. |
| `panics_and_aborts` | Fatal-abort vocabulary: `POODOO BAILOUT TC ALARM ABORT`. |
| `thread_sleeps` | Blocking/delay instructions: `TC JOBSLEEP`, `VARDELAY`. |
| `bitwise_ops` | Arithmetic/masking opcodes reused as the bitwise-operation proxy: `MASK AD SU MULT DV`. |
| `sync_locks` | Interrupt-control and lock vocabulary: `INHINT RELINT LOCK UNLOCK`. |
| `immutability_locks` | `FIXED MEMORY` — AGC's ROM-resident (non-writable) memory region. |
| `cleanup` | Task-teardown opcodes: `ENDOFJOB RESUME EXIT`. |
| `encapsulation` | Any line-leading label token (`[A-Za-z0-9_][a-zA-Z0-9_.]*` at line start) as AGC's closest analog to an internal, task-local (non-global) tag. |
| `listeners` | `EVENT WAIT`, `TC WAITLIST`. |

## 4. What GitGalaxy explicitly does not track

Nine keys are hard-set to `None` in agc_assembly's `rules` dict:

- **`class_start`** — has an explicit inline comment: "AGC lacks native objects." There is no
  object-oriented or class construct anywhere in the language for this key to match; it was never
  a partially-implemented gap, it's structurally out of scope.
- **`closures`** — no inline comment. AGC assembly has no first-class function values or anonymous
  function/lambda syntax for a closure signal to attach to.
- **`decorators`** — no inline comment. No decorator/annotation syntax exists in AGC source.
- **`generics`** — no inline comment. No generic/parametric type system exists at the assembly
  level.
- **`comprehensions`** — no inline comment. No comprehension or collection-expression syntax
  exists; AGC has no collection literals in the modern-language sense.
- **`ssr_boundaries`** — no inline comment. AGC assembly targets spacecraft guidance hardware, not
  a web server; there is no server-side-rendering boundary concept to detect.
- **`dependency_injection`** — no inline comment. No DI framework or container concept exists in
  1960s hardware assembly.
- **`inline_asm`** — no inline comment, but self-evidently out of scope: this key exists to flag
  inline assembly *embedded inside a higher-level language*; agc_assembly source **is** the
  assembly, so the concept of "inline asm within it" doesn't apply.
- **`test_skip`** — no inline comment. `test` already covers AGC's self-check/verification opcode
  vocabulary (`SELFCHECK`, `ROPECHK`, etc.); there's no formal test-framework skip/ignore
  annotation convention for assembly source to detect.

## 5. Known limitations (accepted, not fixed)

None. Grepping both `tests/extraction/languages/test_agc_assembly.py` and
`test_agc_assembly_strict.py` for `known_limitation`-named tests returns nothing — there are no
deliberately-not-fixed gaps documented for this language at this time.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`_dependency_capture` — `class_start` is out of
  scope since it's `None`): 155 tests in `tests/extraction/languages/test_agc_assembly.py` —
  valid/invalid/pathological cases per rule. Fully migrated to the per-language file (epic #813,
  issue #857); nothing left in the old monolithic gauntlet files for agc_assembly.
- **Strict signature suite** (all other wired keys): 76 tests in
  `tests/extraction/languages/test_agc_assembly_strict.py` — positive match, negative/
  false-positive match, cross-rule ambiguity, and ReDoS-immunity checks per signature (epic #518,
  issue #572; deepened further by issue #1074's cross-language batch pass, see §7).

## 7. Relevant closed work

**Dedicated agc_assembly hardening:**
- [#572](https://github.com/squid-protocol/gitgalaxy/issues/572) → PR
  [#743](https://github.com/squid-protocol/gitgalaxy/pull/743) — strict parsing tests (epic #518):
  45 tests added, found and fixed 2 real bugs — `func_start`'s lookahead could cross a newline and
  falsely bind a bare label to an unrelated opcode several lines later (bounded to `[ \t]+`, same
  physical line only); `encapsulation` required a lowercase-starting label even though authentic
  AGC source is uppercase-only (widened to accept any case).
- [#857](https://github.com/squid-protocol/gitgalaxy/issues/857) → PR
  [#931](https://github.com/squid-protocol/gitgalaxy/pull/931) — extraction hardening (epic #813):
  ~136 tests added for `func_start`/`args`/`_dependency_capture`. A first review pass claimed the
  patterns were "already extremely robust" with zero bugs; a follow-up review challenged that
  given every other language in the epic found real bugs, and found two: `func_start`'s opcode
  whitelist covered only 16 real instructions (missing `CAF` — the single most common AGC
  instruction after `TC`/`CS`/`TS`/`CA`, 94 occurrences in the real corpus — plus ~24 others each
  already vetted by this file's own sibling rules), and `args` was missing the `AUG`/`DIM`/`INCR`
  register-coupling opcodes. Both fixes verified against the real Apollo 11 corpus in
  language-crucible: `func_start` matches rose from 609 to 812 (+33%) with zero new false
  positives against data/constant pseudo-ops.

**Cross-language work that touched agc_assembly:**
- [#1074](https://github.com/squid-protocol/gitgalaxy/issues/1074) → PR
  [#1087](https://github.com/squid-protocol/gitgalaxy/pull/1087) — part of a 34-language batch
  deepening strict-signature test depth (epic #1069 follow-on); `test_agc_assembly_strict.py` was
  one of the files directly touched.
- [#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193) → PR
  [#1197](https://github.com/squid-protocol/gitgalaxy/pull/1197) — `prism.py`'s comment-delimiter
  resolution for the entire `line_exclusive` family (20 languages, agc_assembly included) was
  previously shared across the whole family rather than resolved per-language, which could let a
  sibling language's delimiter (`;`, `%`) leak into languages that don't use it. agc_assembly's
  own delimiter (`#`) was already correct, but this hardened the shared comment-shielding
  machinery its extraction depends on.
- [#713](https://github.com/squid-protocol/gitgalaxy/issues/713) → PR
  [#798](https://github.com/squid-protocol/gitgalaxy/pull/798) — bounded `spec_exposure`'s
  ReDoS-vulnerable `[^\]]*` shape across 17 languages. agc_assembly was explicitly audited as part
  of this fix and confirmed **not** affected — the crucible corpus's only 18 real
  Spec-Traceability-Tag hits are in `cobol`/`agc_assembly`, and agc_assembly's own `spec_exposure`
  regex was already outside the vulnerable shape.

**Real bug found along the way (not a dedicated agc_assembly PR):**
- [#1054](https://github.com/squid-protocol/gitgalaxy/issues/1054) → PR
  [#1063](https://github.com/squid-protocol/gitgalaxy/pull/1063) — `detector.py`'s
  `MAX_SATELLITES = 250` hard cap silently discarded any functions beyond the 250th in a single
  file, repo-wide. Only 5 files in the entire ~935-file language-crucible corpus ever hit it, and
  agc_assembly's own `apollo-11/PINBALL_GAME_BUTTONS_AND_LIGHTS.agc` was one of them — its real
  function count was frozen at exactly 250, understating that file's structural mass and blast
  radius. Cap removed entirely.

Search performed via `gh issue list --search 'in:title agc_assembly'` / `'in:title AGC'` /
`'in:title "Extraction hardening: agc_assembly"'` / `'in:title "Strict parsing tests:
`agc_assembly`"'` and `gh pr list --search 'agc_assembly'` (2026-08-20) — several matched PRs
(tri-comparison tooling, other languages' docs/fixes that merely mention agc_assembly in passing)
were skimmed and excluded as not changing this language's own extraction behavior.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

One repo found in the `v2.4.7` batch of `gitgalaxy-raw-output` under AGC/Apollo-related naming —
this is a genuinely niche, historical language, so a thin match count here is expected rather than
a gap in the search:

- **[`Apollo-11`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/Apollo-11/Apollo-11_galaxy_llm.md)**
  — a scan of [`chrislgarry/Apollo-11`](https://github.com/chrislgarry/Apollo-11), the
  publicly-digitized original Luminary 099 (Lunar Module) and Comanche 055 (Command Module) AGC
  source. 74,063 total LOC across both program listings, scanned in 1.26s. This is real,
  unmodified historical NASA/MIT Instrumentation Laboratory source — the same Luminary/Comanche
  corpus the extraction-hardening work in §7 validated its fixes against (via the local
  `language-crucible/data/agc_assembly/apollo-11/` mirror, described below), now confirmed running
  end-to-end through the full scan pipeline on the real upstream repository rather than just the
  isolated regex layer.

**Local corpus** (not `gitgalaxy-raw-output`, but the only other real-world AGC evidence
available): `language-crucible/data/agc_assembly/apollo-11/` holds 10 real `.agc` files from the
same Luminary/Comanche source tree (`AGC_BLOCK_TWO_SELF-CHECK.agc`, `ALARM_AND_ABORT.agc`,
`BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc`, `EXECUTIVE.agc`, `INTERPRETER.agc`,
`LUNAR_LANDING_GUIDANCE_EQUATIONS.agc`, `PINBALL_GAME_BUTTONS_AND_LIGHTS.agc`,
`RCS_FAILURE_MONITOR.agc`, `THE_LUNAR_LANDING.agc`, `WAITLIST.agc`). This is the corpus
`crucible_check.py` and the §7 hardening passes used for empirical before/after validation
(e.g. the 609→812 `func_start` match-count measurement).

## 9. Measured tri-comparison: GitGalaxy vs. ctags (no tree-sitter grammar)

agc_assembly has no tree-sitter grammar, so `tree_sitter_accuracy_audit.py`'s single-ground-truth
methodology doesn't apply here. `ctags_reader.py` maps it to Universal Ctags' generic `Asm`
parser (kind `l`, labels — there is no dedicated AGC parser) as the only other signal to compare
against. `class` has no tri-comparison entries at all: both sides agree there's nothing to find
(`class_start` is `None` per §4, and `ctags_reader.py`'s own kind-map for agc_assembly is an empty
set for the same reason) — a clean agreement, not an unmeasured gap. `args` is out of scope for
this tri-comparison methodology entirely: ctags emits no `signature:` field for Asm-parsed files,
so there's no second reading to compare GitGalaxy's register-mention proxy metric against.

Two `function/existence` shapes existed in `docs/self_scan/tri_comparison_ledger.json`, both
investigated and validated 2026-08-20 by reading the real corpus source and cross-referencing
GitGalaxy's raw regex, GitGalaxy's actual pipeline/DB output, and ctags' actual tagged output
directly (not by trusting either tool's self-report):

**GitGalaxy solo-correct (35 occurrences, `agree[gitgalaxy]_vs[ctags]`), credited to GitGalaxy.**
All 35 are real AGC labels using naming conventions ctags' generic `Asm` parser structurally
can't tag: 14/35 have an embedded hyphen (AGC's own "offset from an event" idiom — `TIG-35`,
`TIG-30`, `CALLT-35` in `BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc:250,292,222`, meaning "35/30
seconds before Time of Ignition"); 21/35 start with a digit or a leading minus sign (`1CHK`,
`2EBANK`, `-1CHK` in `AGC_BLOCK_TWO_SELF-CHECK.agc:184`). Confirmed directly: running
`ctags --language-force=Asm --kinds-Asm=l` against the real corpus files emits **zero** tags for
any of these 35 names, while tagging every plain-alphanumeric sibling normally in the same files
(`CNTRCHK`, `ERASCHK`, `SELFCHK` are all tagged; `-1CHK` is not) — ctags' `Asm` identifier
validation requires a leading letter and no internal hyphen, neither of which is a real
constraint in AGC's own label syntax. Logged as Claim 12 in
[`docs/why_gitgalaxy_beats_ast_here.md`](../why_gitgalaxy_beats_ast_here.md).

**ctags solo-correct (265 occurrences, `agree[ctags]_vs[gitgalaxy]`), mixed cause, no
credit/debit.** A full corpus-wide cross-reference (ctags' actual tagged output vs. GitGalaxy's
raw `func_start` regex matches vs. GitGalaxy's real DB output) accounts for all 265 with no
residual:
- **215/265 — a genuine, intentional precision distinction, not a bug.** ctags' `Asm` `l` kind
  tags every line-start label unconditionally, including pure data/constant-definition labels
  (`ERASCON1 OCTAL 00061`, `S10BITS`, `LSTBNKCH` — `AGC_BLOCK_TWO_SELF-CHECK.agc:133` and nearby).
  GitGalaxy's `func_start` deliberately requires the label be followed by a real instruction
  mnemonic (§3 above), so it correctly excludes these as data labels, not subroutine entries.
  ctags' generic parser has no way to draw that distinction at all.
- **50/265 — a real, confirmed GitGalaxy defect in `detector.py`'s `_slice_by_labels` (Mode A),
  two independent root causes**, found by comparing `struct_func_start` (raw regex signal) against
  `function_count` (named functions actually reaching output) in the real pipeline DB — an 11.6%
  gap across the 10-file corpus (52 total, 50 of which trace to labels ctags also independently
  confirms are real):
  1. `RELINT` is listed in `detector.py`'s `assembly_returns` early-termination keyword set
     (line 572), on the assumption it's a return/exit instruction. In real AGC assembly it means
     "release interrupt inhibit" and commonly *opens* a long interrupt-handler routine rather than
     closing one — confirmed at `ELOOPFIN`, `AGC_BLOCK_TWO_SELF-CHECK.agc:303`, a 20+-line real
     routine truncated to just its own label line. A label literally named `EXIT` (itself one of
     the keywords) at `INTERPRETER.agc:762` self-truncates the same way.
  2. The `len(block.splitlines()) < 2` guard (`detector.py:1973`) discards any function whose
     sliced body reduces to a single non-blank line after stripping — a real, common pattern in
     AGC assembly, where single-instruction "trampoline" labels are completely normal (confirmed
     at `SOPTION1`–`SOPTION7`/`SOPTON10`, `AGC_BLOCK_TWO_SELF-CHECK.agc:210-219`, seven consecutive
     one-instruction labels, all discarded).

  Filed as [#1949](https://github.com/squid-protocol/gitgalaxy/issues/1949) rather than
  credited/debited in the ledger — this is GitGalaxy's own unresolved bug, not something ctags
  corroborates or contradicts. A follow-up read-only investigation confirmed both root causes
  generalize beyond agc_assembly to the shared `_slice_by_labels` mechanism used by every
  label-based language (`assembly`, `cobol`, `fortran`, `abap` all independently exhibit bug 1;
  `assembly`/`cobol` also exhibit bug 2) — #1949 will move to §7 once closed.

Net effect after validation: agc_assembly's Func Precision panel moved from an unvalidated
725/760\* to a clean **760/760**, GitGalaxy's first outright badge on this language's chart row.
Full verdicts with complete citations live in
`docs/self_scan/tri_comparison_ledger.json` (search for `"language": "agc_assembly"`).
