# Refraction pipeline vs. engine DB: the #3120 differential

#3120 asked the COBOL refraction pipeline (`cobol-refractor` → `cobol-to-java`) to use the
engine's `<repo>_galaxy_master.db` as its IR instead of its own COBOL parsers. The issue
required a differential run on a real corpus first, with every delta explained rather than
assumed to be an improvement. This page records that run and what it decided.

**Neither side is the oracle.** Each delta below is attributed to one of four causes:
- **old-parser defect**: a bug in the forge tools
- **engine defect**: a bug in the engine
- **semantic difference**: the two sides measure different things
- **stated absence**: the DB does not carry the datum at all

Each attribution was checked against the real source lines.

Harness: [`tests/tools/refraction_differential.py`](../tests/tools/refraction_differential.py).
Reader: [`gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py`](../gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py).

```sh
# fetch the pinned corpus and build (or reuse) its master DB -- #3213
python tests/tools/mainframe_corpus.py fetch <corpus>
python tests/tools/mainframe_corpus.py scan <corpus>
python tests/tools/refraction_differential.py "$(python tests/tools/mainframe_corpus.py path <corpus>)" \
    --db "$(python tests/tools/mainframe_corpus.py path <corpus> --db)" --json d.json --md d.md
```

For a repository outside the manifest, scan it yourself first:
`GITGALAXY_DISABLE_GIT_HISTORY=1 galaxyscope <repo> --db-only --output <dir>`.

## Corpora (run 2026-09-19, engine at `44ffeb1e`)

| repo | revision | COBOL programs | mainframe inventory (files / units) |
|---|---|---|---|
| [IBM/zopeneditor-sample](https://github.com/IBM/zopeneditor-sample) | `8f98353` (v6.7.1) | 5 | cobol 5/70, jcl 9/25, pli 4/8, rexx 3/4, hlasm 1/1 |
| [cicsdev/cics-banking-sample-application-cbsa](https://github.com/cicsdev/cics-banking-sample-application-cbsa) | `4173345` (`July2024Refresh`; `main` was emptied at the 2024 sunset) | 31 | cobol 36/716, jcl 107/172, bms 10/10 |

The zopeneditor inventory reproduces the counts in the issue (cobol 70, jcl 25, rexx 4,
hlasm 1). pli reads 8 instead of the issue's 7.

## Summary: what the DB can and cannot replace

| datum | old parser | engine DB | verdict |
|---|---|---|---|
| program list | `*.cbl`/`*.cob` glob | `class_data` PROGRAM-ID | **DB**, with an identical list on both corpora (36/36). Extension-independent; separates programs from copybooks, including procedure copybooks |
| PROGRAM-ID | forge regex | `class_data.class_name` | **agree**, 36/36 |
| COPY dependencies | `resolve_copybooks` (same directory only) | `edge_data` | **DB**, though both are incomplete (see D3) |
| paragraph inventory | graveyard regex | `function_data` | **neither is clean** (D1). The DB is carried as data only |
| dead paragraphs | graveyard reachability | `usage_status` | **not replaceable** (D2) |
| DATA DIVISION items, FD record layouts | `cobol_schema_forge` (flat) | `record_data` | **DB** since #3246 — the full item tree (level/PIC/USAGE/OCCURS/REDEFINES/VALUE) and FD→file binding; a field the engine carries and the forge's flat single-line reader drops is `forge_flat_schema` |
| orphaned variables | graveyard | — | **stated absence**: the by-name unused-variable count is a graveyard signal, not a layout |
| DD names, OPEN modes, dataset lineage | forge / DAG architect | `dataset_data` | **DB** since #3201 — exact against the answer key on both corpora (see the #3200/#3201 update) |
| unresolved CALLs | DAG architect | `call_site_data` | **DB** since #3200 — every call site, resolved or not, with its verb, form and line |
| CICS transaction map | `cics_transaction_reader` (CSD) | `transaction_data` | **DB** since #3247 — which transaction id entry-points into which program, from the CSD decks; exact against the key on CBSA (14/14). `transaction` is an INDEPENDENT key field |
| CICS / DB2 presence | forge regex | hit columns | **forge**. Presence agrees 36/36 with a line-level check. The hit columns (`arch_io`, `arch_ipc`) mix CICS verbs, SQL, DLI and CALL, so they cannot give a clean flag (D4) |

The refractor therefore takes the program list, PROGRAM-ID, COPY edges and the unit inventory
from the DB (`--galaxy-db` / `--scan`). It keeps the forge tools for dead code, lineage,
data items and subsystem flags. The generated JCL and schemas are byte-identical with and
without the DB on CBSA. Without the flag, the output is identical to `main`.

## D1. Paragraph inventory

| | zopeneditor | CBSA |
|---|---|---|
| paragraphs only the old parser finds | 17 | 277 |
| — scope terminators (`END-IF.`, `END-EXEC.`, `GOBACK.`, `EXIT.`) | 17 | 128 |
| — paragraphs of **another program** inlined as a "copybook" | 0 | 149 |
| units only the DB finds | 9 | 254 |
| — `SECTION` headers | 0 | 228 |
| — Area-B continuation lines ending in a period | 9 | 26 |

- **Old-parser defects.**
  - **Scope terminators counted as paragraphs.** The graveyard's `^[ \t]{0,11}NAME\.` accepts up to 11 leading blanks, so it reaches into Area B and counts `END-IF.` / `GOBACK.` as paragraph headers.
  - **Other programs inlined as copybooks.** `resolve_copybooks` tries `.cbl`/`.cob` as copybook extensions in the program's own directory. In 18 of CBSA's 31 programs, `COPY ACCTCTRL` (the copybook lives in `cobol_copy/`) resolves to the program `cobol_src/ACCTCTRL.cbl`, often the program itself, and inlines it up to three times.
  - **Section headers invisible.** The graveyard cannot see `SECTION` headers at all.
- **Engine defect.** `func_start` accepts a lone `NAME.` in Area B. It matches:
  - continuation lines: `CURRENT-SECOND.` closing a multi-line `DISPLAY`, and `REPORT-FILE.` closing an `OPEN`
  - data-division `OCCURS ... DEPENDING ON` / `REDEFINES` continuations in copybooks
  - `PROCEDURE DIVISION USING` continuations

  Paragraph names belong in Area A.
- **Semantic difference, engine correct.** CBSA is sectioned code, and the engine records `SECTION` headers as units.

## D2. Dead paragraphs: `usage_status` is not reachability

| | zopeneditor | CBSA |
|---|---|---|
| old parser "dead" | 17 (**all** scope terminators, so 0 real) | 623 |
| DB `usage_status = 1` | 5 | 248 |
| both agree | 0 | 221 |

- **CBSA old-parser "dead" breaks down as:**
  - 119 scope terminators
  - 118 paragraphs of an inlined foreign program (D1)
  - 165 paragraphs the DB calls referenced
  - 221 agreements

  The 165 are live by `SECTION` fall-through (e.g. `GMOFH010` right after `GET-ME-OUT-OF-HERE SECTION.`). The graveyard has no model of sections, so this is an **old-parser defect**.
- **The DB is right about those 165, but not for the right reason.** Its units are `is_public = 1` (the api rule), which suppresses the orphan flag. That is not a reachability analysis.
- **Every DB-only "dead" unit but one is an entry point or a phantom.**
  - CBSA (27): the entry `PREMIERE SECTION` in 17 programs, its first paragraph `A010` in 7, two Area-B phantoms (`COMM-ACT-BAL`, `COMM-AV-BAL`), and the one true positive below.
  - zopeneditor (5): `000-MAIN` in 4 programs, and one Area-B phantom (`SAM2-PARMS`).

  An entry point is never PERFORMed by name, so a by-name test flags exactly the code that always runs. This is an **engine semantics defect** for use as dead code.
- **One engine true positive the old parser misses:** `BANKDATA.cbl`'s `CALC-DAY-OF-WEEK SECTION` is never PERFORMed.

`usage_status` is therefore recorded in the IR as `engine_units[].usage_status` and is **not**
fed to dead-code masking (`extract_lineage`, the slicer, the schema forge).

## D3. COPY dependencies

| | zopeneditor | CBSA |
|---|---|---|
| COPY names (as the old regex sees them) | 12 | 119 |
| resolved by the old parser | 0 | 29, and all 29 are **wrong** (a `.cbl` program, see D1) |
| DB edges matching those names | 0 | 63 |
| DB edges the old regex never sees | 2 | 15 |

- **Old-parser defects.**
  - **Same directory only.** Resolution looks only in the program's own directory, so zopeneditor's `COPYBOOK/` and CBSA's `cobol_copy/` are never found.
  - **Sequence-number fields.** The patterns require blanks before `COPY`, so `R2     COPY SAM2PARM.` is missed. The DB's 2 zopeneditor edges are exactly these lines.
  - **`EXEC SQL INCLUDE` ignored.** The DB's 15 extra CBSA edges are these (`ACCDB2` ×8, `PROCDB2` ×6, `CONTDB2` ×1).
- **Engine defect: ambiguous targets are dropped (fixed by #3199).** An ambiguous target produced no edge at all. This dropped all 12 zopeneditor COPYs, and 36 CBSA COPYs whose copybook does exist in `cobol_copy/`:
  - zopeneditor ships each copybook twice (`COPYBOOK/` and `multiroot/copybooks/`).
  - CBSA's `ACCTCTRL` stem matches `.cbl`, `.cpy`, `.jcl` and `.lked`.
  - CBSA's `CUSTOMER` stem matches `CUSTOMER.cpy` and `CUSTOMER.java`.

  A COPY target now prefers a copybook in the same language, then one that is not itself a
  program (a PROGRAM-ID disqualifies the `.cbl`), then the nearest path; a remaining tie still
  draws nothing. Engine `copybook paths` went from P 78/78 · R 78/114 to P 114/114 · R 114/114
  on CBSA and from P 2/2 · R 2/14 to P 14/14 · R 14/14 on zopeneditor.
- **Semantic difference.**
  - 11 CBSA names are system-supplied (CICS `DFHAID` ×9 and `DFHBMSCA`, Language Environment `CEEIGZCT`) and absent from the repo; unresolvable by construction.
  - 9 CBSA names are BMS symbolic-map copybooks (`BNK1CAM` …), generated from `bms_src/*.bms` at build time. That edge belongs to the Phase-2 BMS work (#3122).

## D4. CICS / DB2 flags

- **Presence agrees.** The forge's `is_cics` / `is_db2` booleans agree with a line-level `EXEC CICS` / `EXEC SQL` count on all 36 programs.
- **Old-parser defect: the counts are wrong.** `cics_calls` and `sql_calls` are low (e.g. `BNKMENU` 6 vs 62). `EXEC\s+CICS.*?END-EXEC\.` needs a period after `END-EXEC`, so a block inside an `IF` is skipped and the lazy match swallows the following blocks. This is the same unbounded pattern the issue cites as a ReDoS shape.
- **Why the flags stay on the forge.** Only the booleans reach generated output (the JCL `ARCHITECTURE REQUIRES` comment). The DB cannot supply a clean equivalent.

## Also found

- **The refractor edits its target in place.** `patch_lexical_traps` rewrites `NEXT SENTENCE` into the customer's source files. A `--scan` DB describes the source before that patch.
- **The DAG architect reports no outputs on either corpus.** It records the first mode of an `OPEN` for every file in it, so `OPEN INPUT A OUTPUT B` makes `B` an input. As a result, every generated JCL DD gets `DISP=SHR`, including SAM1's two output files.

- **Checked, not a defect: JCL `DSN=` edges.** The resolver turns a DSN's dots into slashes and matches the last qualifier against file stems. That could attach a job to an unrelated program. On both corpora there are 0 JCL edges into another language. All 63 JCL→JCL edges are `INCLUDE MEMBER=` / `JCLLIB` members.

## What #3120 still needs

Dead code and lineage can move to the DB only when the engine carries them. Filed from this run:

| issue | side | finding |
|---|---|---|
| #3197 | engine | Area-B continuation lines become paragraphs (D1) |
| #3198 | engine | `usage_status`: entry flagged, case-sensitive, `NAME-EXIT` counts as a reference (D2) |
| #3199 | engine | resolver drops ambiguous COPY targets (D3) — **fixed**; both corpora now score `copybook paths` exact |
| #3200 | engine | no CALL / CICS LINK / JCL `EXEC PGM=` edges; unresolved CALLs unrecorded — **fixed** |
| #3201 | engine | no named SELECT/ASSIGN / OPEN-mode / DD extraction — **fixed** |
| #3202 | engine | `calls_out_to` is meaningless for COBOL |
| #3203 | forge | graveyard finder defects (D1–D3) |
| #3204 | forge | DAG architect's multi-mode OPEN: no outputs, every DD `DISP=SHR` |
| #3205 | forge | JCL forge's EXEC CICS/SQL counts and unbounded regex (D4) |
| #3206 | forge | refractor rewrites the target's source in place |

The switch for dead code needs #3198. The switch for lineage needs #3200 and #3201 (**both landed** — see the #3200/#3201 update at the end of this page; the forge-side switch itself is still to do).
(Superseded for dead code by the #3197/#3198 update at the end of this page: the
census cannot be dead code under its own contract, so the forge keeps that half.)

## Update: forge fixes (#3203 defects 1–4, #3204, #3205, #3206)

The forge-side findings above were fixed together. Scores come from the answer key (`tests/tools/cobol_answer_key.py score`, pinned refs) and show the forge before → after. `P` is correct/reported, `R` is correct/true.

| field | zopeneditor-sample | CBSA |
|---|---|---|
| units | P 58/75 → **58/58** | P 452/729 → **452/452** (R 452/680) |
| dead (non-trivial) | P 0/17 → nothing claimed (0 true) | P 5/571 → 5/328 |
| copybook paths | R 0/14 → 12/14 | P 0/29 · R 0/114 → **P 99/99** · R 99/114 |
| inputs | P 6/12 → **6/6** | — |
| outputs | R 0/6 → **6/6** | R 0/1 → **1/1** (BANKDATA) |

- **D1 paragraphs.** A header now has to start in Area A (cols 8–11). `END-*`, `GOBACK`, `EXIT` and `CONTINUE` are never headers. A sequence field in cols 1–6 is tolerated, and the operand of `PROCEDURE DIVISION USING X.` is no longer read as the entry paragraph (it was on 18 CBSA programs, which is how BANKDATA's `A010` read as dead).
- **D3 copybooks.** Lookup covers the whole repository, nearest first. A member with a `PROGRAM-ID` is never inlined.
- **What is left is SECTION-related (#3203 defect 5).** All 228 missing CBSA units are sections, and all 323 remaining false dead claims are in programs that use sections (fall-through is not modelled).
- **D4.** EXEC CICS / EXEC SQL are counted per statement. They match a line-level count on all 31 CBSA programs (BNKMENU 62, XFRFUN 77, BNK1CAC 37).
- **Target left untouched.** The refractor writes lexically patched programs to `<clean room>/00_patched_source/` and never writes to the target repository. IR dumps serialise sets sorted, so they are deterministic (#3212).
- **Harnesses.** `refraction_differential.py` and `cobol_answer_key.py` now call the graveyard's own `paragraph_headers` / `find_copybook` instead of copies of its old regexes, and search copybooks under the repository as the refractor does.

## Update: SECTION model (#3203 defect 5) and per-path output keys (#3218)

`x_ray_dead_code` now runs a reachability pass instead of "named in a PERFORM or GO TO anywhere". It follows ranges from the entry:
- fall-through until a terminal statement;
- PERFORM of a paragraph, of a section (to its last paragraph), and PERFORM … THRU;
- GO TO;
- a unit ending in a PERFORM of a range that never returns counts as terminal;
- CICS HANDLE labels are entry points.

Comment lines and literals are ignored. Sections are units. The `*-EXIT` exemption is gone: an EXIT paragraph nothing reaches is dead (trivial) code.

| field (forge) | zopeneditor-sample | CBSA |
|---|---|---|
| units | P 58/58 · R 58/58 | R 452/680 → **680/680** (P 680/680) |
| dead | — (0 true, 0 claimed) | P 57/380 → **62/62** · R 62/62 |
| dead (non-trivial) | — | P 5/328 → **10/10** · R 10/10 |

**These scores are not independent evidence.** The pass follows the same control-flow model as the answer key's `draft` (the forge's own implementation; the drafter is still not imported by any parser). The key itself is hand-verified, but exact agreement is expected wherever the hand pass left the draft unchanged. A defect in the shared model would be invisible to this score.

The DAG architect's and the microservice slicer's dead-unit masking now find headers with the graveyard's `unit_header`. Before, each used its own `^[ \t]{0,7}NAME\.`, which missed sections and sequence-numbered source.

Clean-room outputs and the dead-code IR state are keyed by each program's stem when that is unique in the run, and otherwise by its path flattened with `__`. Anomaly tags carry the path under the target. On zopeneditor, `COBOL/SAM1`/`SAM2` and `multiroot/sam/SAM1`/`SAM2` used to overwrite each other; in SQLite mode they also merged their dead code (#3218).

## Update: engine paragraph inventory (#3197) and the census lexicon (#3198)

Both findings D1 and D2 filed against the engine are addressed here. Scores from
`python tests/tools/mainframe_corpus.py score` (#3213), engine column, before → after:

| field | zopeneditor-sample | CBSA |
|---|---|---|
| units | P 58/67 → **58/58** | P 680/706 → **680/680** |
| `usage_status` claims | 5 → 4 | 248 → 247 |

**D1 — paragraph inventory (#3197).** A paragraph or section header begins a
SENTENCE, so the previous code line must end with a period. The last line of a
multi-line statement or data description is therefore not a paragraph, however
it is indented. Recall was already complete, so the phantoms were pure
precision loss: the engine's units now agree exactly with the hand-verified key
on both corpora, and with the forge.

The fix is not the file-level fixed/free-format detection #2538 deferred, and
not an Area-A column anchor. Measured over language-crucible v1.3.0,
keyword-rosetta and all three pinned corpora: **every** Area-A header follows a
completed sentence (0 exceptions), and real paragraphs DO appear in Area B in
accepted source, so a column anchor would have dropped them. The deciding
context is the previous line, which no lookbehind can span, so this is a
registry-declared scope filter honoured by both `func_start` consumers — the
count in `coding_analysis` and the unit list in `_slice_by_labels`.

**D2 — `usage_status` (#3198).** Two defects of the name test itself are fixed,
under the census's own contract:
- COBOL names are case-insensitive, so `perform a-para` now names `A-PARA`.
- `-` is a COBOL name character, so `B-PARA-EXIT` is no longer a mention of
  `B-PARA` (13 units across the corpora were cleared by a *different*
  paragraph's name).

**What does NOT change, and why the D2 verdict stands.** The entry paragraph is
still flagged. Nothing in the file names it — it is reached by fall-through —
and `docs/unreferenced_by_name_contract.md` corollary 3 says plainly that the
census reports "nothing else in this file names this unit", never "this unit is
dead". Making it mean reachability would change the signal for every consumer of
`state_unreferenced`.

So **#3120's dead-code switch is re-scoped, not pending**: the engine supplies
the unit inventory (now exact), and dead code stays with the forge's own
reachability pass, which the answer key scores at 62/62 · 10/10 non-trivial on
CBSA. A future engine-side reachability signal would be a new field beside
`usage_status`, not a redefinition of it, and would need its own issue and
evidence.

## Update: Java names come from the clean-room key (#3221)

The Java half of #3218. The clean room had already been keyed per path, but the
forges under `gitgalaxy/tools/cobol_to_java/` re-derived their names downstream:
a service and a controller from the IR's `metadata.file_name`, an entity from
the schema's `title`. Neither is unique across a repository, so generation was
not one output file per input file — the later file in filename order simply
overwrote the earlier, with no warning.

`cobol_to_java_names.py` now derives every generated name, and only, from the
key (`output_key` → `java_class_base` / `java_url_segment`). A key that is a
plain stem produces exactly the name the old code produced, so only a genuinely
ambiguous program is renamed.

| corpus | IR dumps | services (was) | schemas | entities (was) |
|---|---|---|---|---|
| zopeneditor-sample | 5 | 6 (3) | 5 | **5** (2) |
| cics-banking-sample-application-cbsa | 31 | 31 (31) | 29 | **29** (3) |
| aws-mainframe-modernization-carddemo | 39 | 44 (44) | 36 | **36** (13) |

Service counts include mock services for unresolved CALLs, which is why they can
exceed the IR count. Entities now match schemas exactly on all three corpora; 54
programs' data layouts were being discarded, 26 of them on CBSA alone, because
every CICS program titles its record `DFHCOMMAREA`.

Two consequences worth naming:

- **The `@Table` name is unchanged.** Only the Java class is disambiguated; the
  COBOL 01-level it maps keeps its own name. CBSA therefore generates 20 entity
  classes that all declare `@Table(name = "DFHCOMMAREA")` (the 26 discarded layouts
  above are across all three colliding titles — 20 `DFHCOMMAREA`, plus the
  `ABNDINFO_REC` and `PARM_BUFFER` collisions). That is a faithful report of the
  source — they really are 20 different layouts of one CICS communication area —
  and deciding what table each should map to is a semantic question, tracked
  separately, not a naming one.
- **An ambiguous CALL target now resolves to a mock.** zopeneditor's two SAM1
  programs both `CALL SAM2`, and there are two SAM2 programs. Before, the class
  named `Sam2Service` happened to be whichever real SAM2 was written last, so the
  call silently bound to one of them. The real services are now
  `CobolSam2Service` and `MultirootSamSam2Service`, and `Sam2Service` is the
  generated mock for the unresolved call. The ambiguity was always there; it is
  now visible in the output instead of resolved by file-write order.

## Update: the mainframe call graph and dataset boundary (#3200, #3201) — 2026-09-20

Two of this page's stated absences are gone. The engine now extracts the named
invocation and dataset facts, and the master DB persists them, so the DB can
answer "program P opens DD X for INPUT; job J step S binds DD X to dataset D"
without the forge's own SELECT/OPEN parser.

**What the DB carries now.** A language opts in with a top-level
`boundary_extraction` declaration (cobol, jcl); `core/mainframe_boundary.py`
reads the prism **code stream**, and `core/invocation_resolver.py` resolves names
to files across the repository.

| table | content |
|---|---|
| `call_site_data` | one row per COBOL `CALL`, CICS `LINK`/`XCTL PROGRAM(...)`, JCL `EXEC PGM=` — with `verb`, `form` (literal / identifier), the operand as written, the target program name, the resolved file (or NULL), and the line |
| `dataset_data` | COBOL `SELECT ... ASSIGN` + the `OPEN` modes actually used; JCL `DD` ddname → DSN with its step |
| `edge_data` | gains `edge_kind` `'call'` and `'exec'` for the resolved program-to-program invocations |

**Scores against the answer key** (engine column; the forge column is unchanged
by this PR, and no snapshot moved):

| corpus | field | before | after |
|---|---|---|---|
| zopeneditor-sample | DD names | not carried | P 12/12 · R 12/12 |
| zopeneditor-sample | inputs | not carried | P 6/6 · R 6/6 |
| zopeneditor-sample | outputs | not carried | P 6/6 · R 6/6 |
| zopeneditor-sample | dynamic CALLs | not carried | P 3/3 · R 3/3 |
| zopeneditor-sample | call targets | not carried | P 3/3 · R 3/3 |
| cics-banking-sample-application-cbsa | DD names | not carried | P 1/1 · R 1/1 |
| cics-banking-sample-application-cbsa | outputs | not carried | P 1/1 · R 1/1 |
| cics-banking-sample-application-cbsa | call targets | not carried | P 45/45 · R 45/45 |

`call targets` is a new scored field: every program name a call site denotes,
literal or resolved through a working-storage `VALUE`. It has no forge column —
the DAG architect records only non-literal `CALL` operands and never sees
`EXEC CICS LINK`/`XCTL` at all, which is 140 of CBSA's 144 call sites.

The extraction was verified site-by-site before any of it was wired in: all 147
call sites across both corpora match the key on verb, form, operand, target
**and line**, and all 13 dataset records match on internal name, DD and modes,
with no false positives. JCL has no answer key, so `EXEC PGM=` was checked
against an independent raw-file scan instead: 24 / 77 / 150 steps on the three
corpora, exactly matching.

**Three readings worth recording, because each one is a decision:**

- **A call edge is not a dependency edge.** `edge_kind` is `'call'`/`'exec'` and
  these never enter the DiGraph, so `pagerank_score`, `popularity`,
  `internal_dependency_links`, betweenness, the archetypes and every risk score
  are byte-for-byte unchanged. Whether a runtime invocation *should* count as
  architectural coupling is a scoring question with its own measured
  before/after; it is deliberately not settled here, and is filed as #3237. One consequence: #2992's
  per-file reconciliation is now scoped to `WHERE edge_kind = 'import'`, and so
  is `galaxy_ir`'s `copy_deps`.
- **A CALL resolves by PROGRAM-ID, nearest-wins — the import resolver's rule is
  wrong for this relation.** An import names a file, so an ambiguous stem is
  refused rather than guessed (#3199). A called program is chosen by library
  concatenation order at link-edit or CICS-install time, which is what the
  answer key records for zopeneditor's two `SAM2` programs. Nothing is lost when
  the choice is debatable: `target` keeps the name regardless of which file it
  was attributed to.
- **Unresolved is data, not a gap.** Most real call sites resolve to nothing —
  `CALL 'CEEGMT'` is an LE service and `EXEC PGM=IEFBR14` a system utility — and
  those rows are the answer to "the old pipeline's `unresolved_calls` has no DB
  equivalent". The table distinguishes "the name itself was unreadable"
  (`target IS NULL`, dynamic dispatch through a copybook's `VALUE`) from "named
  but external" (`dst_file_id IS NULL`).

**Delta mode carries it too.** `state_rehydrator.py` restores both tables for
unchanged files, the way #3220 restores `raw_imports`; a full scan and an
incremental scan of zopeneditor produce byte-identical `call_site_data` and
`dataset_data`. Resolution is not restored and is redone every scan, because a
file added or deleted this commit can change what an unchanged file's `CALL`
resolves to.

**Since delivered (#3246):** FD/01 record layouts. What this update called
data-division item extraction — a level-number/PIC/OCCURS/REDEFINES walker — now
lives in the same `core/mainframe_boundary.py` channel and persists to
`record_data`; see the #3246 update below. Dataset lineage never needed it.

**Still absent, structurally:** reachability. An `OPEN` in an unreachable
paragraph is extracted, because the engine has no reachability model and
inventing one in this channel would repeat the mistake #3198 corrected. The
forge keeps dead-code masking.
## Update: a DFHCOMMAREA maps to a DTO, not an entity (#3233)

This is the "tracked separately" semantic question the #3221 update left open. Once
every CICS program got its own entity class, the `@Table` name it kept exposed the
real defect: a program's `DFHCOMMAREA` is its **communication area** — a parameter
block passed on `EXEC CICS LINK`/`XCTL`, not a shared table. Every CICS program
declares one, so the forge emitted N entity classes, each a different layout, all
bound to `@Table(name = "DFHCOMMAREA")`. Hibernate refuses to start on that
(`Multiple entities mapped to table DFHCOMMAREA`), so the generated tree could not
boot — a faithful *report* of the source that is not a runnable *mapping* of it.

**The rule.** A record whose 01-level title is `DFHCOMMAREA` is transient state and
generates a **plain Lombok POJO DTO** in the `dto` package instead of a JPA entity:
`@Data @NoArgsConstructor`, no `@Entity`/`@Table`, no synthetic `@Id` surrogate key,
no `@Column`/`@Transient`/`@ElementCollection`, no `jakarta.persistence` import. The
COBOL layout is preserved as plain fields (order, `BigDecimal` precision, OCCURS as
`List<>`, REDEFINES aliases as fields) because the block is still read and written by
the migrated logic — it simply is not persisted. The class keeps its clean-room-keyed
name with a `Dto` suffix (`Bnk1cacDfhcommareaDto`), so it never collides with an
entity. Applied by `cobol_to_java_spring_forge.generate_java_dto`, selected by
`is_transient_record`, wired through `cobol_to_java_controller`.

| corpus | JPA entities | DFHCOMMAREA DTOs (was entities) |
|---|---|---|
| zopeneditor-sample | 5 | 0 |
| cics-banking-sample-application-cbsa | 9 | **20** |
| aws-mainframe-modernization-carddemo | 15 | **21** |

Totals are unchanged from the #3221 table (CBSA 29, carddemo 36, zopeneditor 5); the
DFHCOMMAREA rows have moved from `entity/` to `dto/`. No generated service,
controller or repository referenced these classes, so nothing else moved except the
per-corpus `java_migration_audit.txt` count line.

**Why the title, and only the title.** The schema JSON the forge consumes carries
`title`/`type`/`properties` and nothing else, so the 01-level name is the only signal
at the forge boundary. The more faithful rule — persist only records a program
actually reads or writes to a file (its SELECT/ASSIGN and OPEN lineage), DTO the rest
— needs named dataset lineage from the engine and is **blocked on #3201**; until then
other working-storage records (`WS_FIELDS`, `PARM_BUFFER`, …) stay entities. Whether
the generated tree actually *compiles and boots* is a separate gap, tracked in #3121.

## Update: cause codes, a key verdict and a zero-unexplained gate (#3211)

The attributions above (D1–D4) were made with throwaway scripts and recorded here in prose.
#3211 moves the classifiers into the harness: `refraction_differential.py` now attaches a
`cause` to every delta, so "every delta explained" is a command, not an afternoon.

**Mechanism causes.** Each delta is read off the source with the same fixed-format model the
answer key uses (`cobol_answer_key.Source` / `_units` / `reachability` / `resolve_copybook`), so
a cause is never a fourth parser's opinion:

| cause | the delta it explains | D-section |
|---|---|---|
| `scope_terminator` | a forge unit/dead that is `END-*`/`GOBACK`/`EXIT`/… (`cobol_graveyard_finder._NOT_A_PARAGRAPH`) | D1 |
| `program_inlined_as_copybook` | a forge unit/dead that is not one of this program's own Area-A units | D1/D3 |
| `section_header` | a DB unit that is a real `SECTION` header | D1 |
| `area_b_header` | a DB unit that is a lone `NAME.` the engine read in Area B, not a real header | D1 |
| `entry_point` | a DB `usage_status` "dead" that is a real unit reached by fall-through/entry (not by name) | D2 |
| `usage_status_not_reachability` | a forge-dead unit the engine's `usage_status` does not flag — the two measure different things (#3198, by design) | D2 |
| `ambiguous_copy_target` | a COPY whose stem is shared across members/extensions (`resolve_copybook` "AMBIGUOUS", or a shared stem the engine drops) | D3 |
| `exec_sql_include` | a DB edge from `EXEC SQL INCLUDE` | D3 |
| `sequence_number_field` | a COPY behind a cols-1..6 sequence field | D3 |
| `system_copybook` | a `DFH`/`CEE`/`SQLCA`/`SQLDA` member, unresolvable by construction | D3 |
| `bms_symbolic_map` | a member generated from a `.bms` map at build time | D3 |
| `forge_flat_schema` | a DATA DIVISION field the engine carries that the forge's flat single-line `cobol_schema_forge` reader drops (group item, continuation-line PIC, copybook layout) | #3246 |
| `stated_absence` | every `forge_only` datum and the CICS/SQL flags — the DB carries no equivalent (`galaxy_ir.py` SCOPE) | D4 |

**A verdict from the key.** Where the corpus has a *validated* answer key (#3210), a delta on an
**independent** field — `program_id` or `copybook` — is adjudicated directly from truth
(`db` side carries a true value → old-parser defect; a false one → engine defect; and the mirror
for the `old` side). This clears the delta with no mechanism cause needed. For `units`/`dead` the
key's `draft` shares the forge's control-flow model (#3219), so an agreement there is **not**
independent evidence and never clears a delta on its own — those verdicts are recorded with
`confidence: shared_model`.

**The gate.** A delta neither a mechanism nor an independent key verdict explains is
`unexplained`. `refraction_differential.py --ci` classifies the committed excerpts and fails when
a run ADDS unexplained deltas over `tests/cobol_mainframe/refraction_differential_baseline.json`;
`--corpus NAME …` does the same over the full pinned corpora (local, needs a fetch+scan), and
`--update-baseline` blesses the matching scope. `by_cause` is recorded for visibility and does not
gate. CI runs the excerpts only (it does not clone the corpora); `test_refraction_differential.py`
wraps both, the full-corpus half skipped unless the clone is present, exactly as the snapshot test.

**Where the corpora stand.** Both keyed corpora reach **0 unexplained** on the full run; carddemo's
residual is baselined with a note:

| corpus (full) | unexplained | why it stands |
|---|---|---|
| zopeneditor-sample | 0 | fully classified / key-adjudicated |
| cics-banking-sample-application-cbsa | 0 | 33 `usage_status_not_reachability` cells (forge-dead vs the engine's by-name `usage_status`) are an explained, by-design semantic difference (#3198 closed; `docs/unreferenced_by_name_contract.md`), not a pending fix |
| aws-mainframe-modernization-carddemo | 157 | no answer key yet (#3210 pending for carddemo), so no delta can be adjudicated from truth. 142 are real paragraphs the forge's reader drops on cols-73-80 right-margin sequence numbers (**#3244**); expected to fall to ~15 once #3244 lands and to 0 with a carddemo key |

So the #3120 gate is now a command: `--corpus` returns 0 unexplained on both keyed corpora, and
names precisely what the one remaining corpus is waiting on (a fix, #3244, and a key).

## Update: DATA DIVISION items and FD record layouts (#3246) — 2026-09-20

The last structural datum this page listed as a stated absence — "no data items are extracted" — is
gone. `core/mainframe_boundary.py` now walks the DATA DIVISION (WORKING-STORAGE / LINKAGE /
LOCAL-STORAGE and the FILE SECTION `FD`/`01`), one row per data description entry: level, name, PIC,
USAGE/COMP-3, OCCURS `[DEPENDING ON]`, REDEFINES and VALUE, with each `01` bound to the `FD`/`SD`
file it describes. The master DB persists it as `record_data` (a per-file table, cascade-deleted with
`file_data`, restored on delta scans like the other boundary tables), and `galaxy_ir.py` rebuilds the
`01/05/10/...` tree as `EngineFile.records` from `ordinal`/`parent_ordinal`. It is **same-file only**,
like the value map: a copybook carries its own layout, and cross-file COPY assembly stays a consumer's
job. Byte offsets, COMP-3 width and REDEFINES overlays are not computed here — that is a layer on top.

**In the differential.** Record layouts are now a real forge-vs-engine datum (`records`), not a
stated absence. Both sides read this file's own DATA DIVISION — the engine's `data_items` vs the
forge's `cobol_schema_forge` columns — and a delta gets a real cause: a field the engine carries that
the forge's flat single-line reader drops is `forge_flat_schema` (group items, continuation-line PICs,
copybook layouts). A field the forge reads that the engine's walker misses stays `unexplained` (a real
engine gap) until a validated key adjudicates it — `record` is an INDEPENDENT key field. On the three
committed excerpts this is `forge_flat_schema` 4 / 5 / 7 with **0** engine-side gaps, so the gate holds
at 0 unexplained. The answer keys carry a drafted `records` field (`status: draft`), validated
incrementally; the forge's own entity/DTO generators sourcing these fields from the DB instead of
re-parsing is the tracked follow-up under epic #3122.

## Update: the CICS transaction map (#3247) — 2026-09-22

The engine's CICS extraction (`transaction_data`, landed in the #3211-followup PR) is now a
compared datum. In a CICS application the transaction is the *front door*: a terminal user submits a
4-character transaction id and CICS routes it to a program. `refraction_differential.py` now reports,
per COBOL program, the entry transaction id(s) that route into it — `transactions_old` /
`transactions_db` / `transactions_agree` in the summary, and per-program `transaction` deltas.

**Three independent parses of the same decks.** The comparison is genuinely three-sided, which is
what lets `transaction` adjudicate a verdict (an INDEPENDENT key field):

- **forge / old side** — `gitgalaxy/tools/cobol_to_cobol/cics_transaction_reader.py`, a self-contained
  CSD reader that imports neither the engine nor the answer key.
- **engine / db side** — `galaxy_ir.transaction_map()`, read from `transaction_data`.
- **answer-key oracle** — `cobol_answer_key._key_transactions`, a third CSD parser (the two operands
  the key keeps, `PROGRAM`/`TRANSID`, are bare names, so it needs no paren-balanced attribute scan).

All three read a repo's `.csd` decks (standalone files and DFHCSDUP SYSIN carried inline in JCL),
the `DEFINE TRANSACTION(T) ... PROGRAM(P)` records plus the `DEFINE PROGRAM(P) ... TRANSID(T)`
autoinstall pairing, excluding `DEFINE DB2TRAN`'s TRANSID. On the pinned corpora the three agree
exactly — CBSA 14/14 (14 of its 17 transactions route to in-repo COBOL programs; 3 are external),
carddemo 33/33, zopeneditor none — so the datum adds **0** unexplained deltas and the `--corpus`
gate holds at its prior counts. The CBSA and zopeneditor answer keys carry the `transactions` field
with `transactions_validated: true`; carddemo stays `answer_key: null` (differential-only). Surfacing
the transaction map in the audit/LLM reports (`audit_recorder`/`llm_recorder`) is the tracked
follow-up under epic #3122 — it moves the golden master, so it ships on its own.

## Update: PL/I DECLARE structures (#3250) — 2026-09-22

PL/I `DECLARE`d structures now ride the `record_data` channel (a `pli` boundary dialect) and are a
compared datum. No PL/I forge exists, so the compared side is the answer key's own PL/I reader
(`cobol_answer_key.pli_data_items`: a tokenizer over the RAW file that strips its own comments and
numbered columns 73-80, never the engine's PRISM stream). The unit is the dotted leaf path
(`CUSTOMER_RECORD.CUSTOMER_KEY.CUST_ID`), reported as `pli_record` deltas and
`pli_record_fields_key` / `_db` / `_agree` in the summary. A delta is `unexplained` (a real parser
defect on one side, never `stated_absence`) until the file is signed off with `records_validated`.

On zopeneditor-sample's four PL/I programs (now in its excerpt) the two agree 113/113, and the gate
holds at 0 unexplained on every excerpt and every full corpus. Beyond the pinned corpora, both
readers were run over navikt/DSF (1,473 fixed-format PL/I files): they agree on every file, 26,518
leaf fields. The first run did not: the engine missed fields in 179 DSF files, because PRISM strips a
trailing comment but not the column-73 sequence number after it, and two such orphaned numbers in a
row hid the next `DCL`. The engine now skips any run of them.

