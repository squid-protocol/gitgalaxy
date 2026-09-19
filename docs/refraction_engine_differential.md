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
GITGALAXY_DISABLE_GIT_HISTORY=1 galaxyscope <repo> --db-only --output <dir>
python tests/tools/refraction_differential.py <repo> --db <dir>/<repo>_galaxy_master.db --json d.json --md d.md
```

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
| orphaned variables | graveyard | — | **stated absence**: no data items are extracted |
| DD names, OPEN modes, dataset lineage | forge / DAG architect | — | **stated absence**: `edge_data` holds only COPY/INCLUDE edges |
| unresolved CALLs | DAG architect | — | **stated absence**: CALL produces no edge and no record |
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
- **Engine defect: ambiguous targets are dropped.** An ambiguous target produces no edge at all. This drops all 12 zopeneditor COPYs, and 36 CBSA COPYs whose copybook does exist in `cobol_copy/`:
  - zopeneditor ships each copybook twice (`COPYBOOK/` and `multiroot/copybooks/`).
  - CBSA's `ACCTCTRL` stem matches `.cbl`, `.cpy`, `.jcl` and `.lked`.
  - CBSA's `CUSTOMER` stem matches `CUSTOMER.cpy` and `CUSTOMER.java`.

  A COPY target should prefer a copybook in the same language, then the nearest path.
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
| #3199 | engine | resolver drops ambiguous COPY targets (D3) |
| #3200 | engine | no CALL / CICS LINK / JCL `EXEC PGM=` edges; unresolved CALLs unrecorded |
| #3201 | engine | no named SELECT/ASSIGN / OPEN-mode / DD extraction |
| #3202 | engine | `calls_out_to` is meaningless for COBOL |
| #3203 | forge | graveyard finder defects (D1–D3) |
| #3204 | forge | DAG architect's multi-mode OPEN: no outputs, every DD `DISP=SHR` |
| #3205 | forge | JCL forge's EXEC CICS/SQL counts and unbounded regex (D4) |
| #3206 | forge | refractor rewrites the target's source in place |

The switch for dead code needs #3198. The switch for lineage needs #3200 and #3201.
