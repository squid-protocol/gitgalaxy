# PL/I — Structural Signature Coverage

Snapshot written 2026-09-15 with the language's addition (#2502, which also closes the earlier
#1142). Source: `LANGUAGE_DEFINITIONS["pli"]` in
`gitgalaxy/standards/language_standards/languages/pli.py`, `tests/extraction/languages/test_pli.py`
/ `test_pli_strict.py`, and a probe of every rule over 1,560 real PL/I files (§8). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

**Scope note:** PL/I has no tree-sitter grammar or ctags parser available to this repo's comparison
tooling, and no ground-truth parser was run, so there is no §9. The pinned language-crucible corpus
carries no PL/I either (its `zopeneditor-sample` copy keeps only the COBOL and JCL members), so the
golden masters cannot see a PL/I regression yet. Adding PL/I repositories to the crucible is a
follow-up.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | IBM Enterprise PL/I for z/OS 6.1 (also the ANSI X3.53-1976 subset) |
| `_meta.blueprint_version` | v6.3 |
| `_meta.last_updated` | 2026-09-15 |
| `lexical_family` | `standard_block` — `/* */` comments that do not nest, plus the `//` line comments Enterprise PL/I accepts. PL/I's margins (columns 2-72) are a compiler option, not a column-indicator comment syntax, so it is not `positional_anchored` like COBOL. |
| Structural signature keys wired | 46 / 54 (8 explicit `None`, see §4; the 54 include `_dependency_capture` and `_visibility_export_list`) |
| Extraction-gauntlet tests (`test_pli.py`) | 54 |
| Strict-signature tests (`test_pli_strict.py`) | 158 |
| Total dedicated PL/I test cases | 212 |

## 2. Identification surface

- **Extensions:** `.pli` (IBM's convention: Z Open Editor, zAppBuild, DBB), `.pl1` (the historic
  one), `.plinc` (include members). `.inc` is **not** claimed: PL/I shops use it for `%INCLUDE`
  members, but so do PHP, Pascal, NASM and every assembler.
- **Exact filenames:** none.
- **Discriminators:** `.pli`, `.pl1`, `.jcl`, `.bms` — the JCL that compiles and runs PL/I and the
  BMS maps its CICS programs send.
- **Shebangs:** none; PL/I is compiled.
- **Case-insensitive imports:** `%INCLUDE` member names are PDS members, so `%INCLUDE p0019908;` and
  `%INCLUDE P0019908;` resolve to the same file.

## 3. What GitGalaxy detects

Every keyword is guarded with `(?<![\w@#$%])` / `(?![\w@#$])` rather than `\b`, because `@`, `#` and
`$` are PL/I identifier characters but regex non-word characters. `\w` is Unicode-aware, so national
letters in names (`KONTROLLER_AU_SØKER`) are identifiers too.

**Every CICS / SQL / DLI rule reuses COBOL's vocabulary verbatim.** #2502 asked for identical
coverage, and `test_pli_counts_embedded_mainframe_commands_like_cobol` pins it command by command.
PL/I ends an `EXEC` statement with `;` where COBOL writes `END-EXEC`. Three places diverge
deliberately; each is pinned in `test_pli_deliberate_divergences_from_cobol`:
- A plain `CALL` is not a bridge in PL/I: it usually calls an internal procedure.
- `EXEC SQL INCLUDE` / `DECLARE` / `WHENEVER` are not io.
- `MQGET` is listeners' only.

### Phase 1 — logic topology and structure
- **`func_start`** — `label: PROC` / `label: PROCEDURE`, naming the label directly before the
  keyword.
  - A multi-label `A: B: PROC;` yields `B`. A condition prefix `(SUBRG):` is skipped.
  - Up to three line breaks may separate label and keyword, each optionally carrying a
    columns-73-80 sequence number. That is navikt/DSF's layout: `NAME:  00000480` on one line,
    `PROC(...);` on the next.
  - A preprocessor procedure (`%NAME: PROC`) is excluded.
- **`args`** — the parameter list of a `label: PROC(...)` or `label: ENTRY(...)` statement. Call
  sites, `DCL E ENTRY(CHAR(8))` descriptors and preprocessor procedures don't count.
- **`class_start`** — Enterprise PL/I's named types: `DEFINE STRUCTURE` and `DEFINE ORDINAL`.
  `DEFINE ALIAS` is excluded.
- **`branch`** — IF, ELSE, the `SELECT (expr);` group, WHEN, OTHERWISE, and the loop openers (`DO
  WHILE`, `DO UNTIL`, `DO LOOP`, `DO FOREVER`, `DO I = ...`).
  - `SELECT` needs its `(`/`;` form, so `EXEC SQL SELECT` stays SQL.
  - A plain `DO;` group doesn't count.
- **`structural_boundaries`** — PROC/PROCEDURE, BEGIN, END, RETURN, DCL/DECLARE, PACKAGE.

### Phase 2 — safety and execution risk
- **`safety`** — an ON-unit installs a handler.
  - Bare conditions: `ON ERROR`, `ON CONVERSION` and the rest.
  - File conditions and `CONDITION(name)` need their parenthesised reference, so BankDemo's 62
    `ON WEDNESDAY` hits in prose don't count.
  - An enabling condition prefix, e.g. `(SUBSCRIPTRANGE):`, counts.
  - COBOL's CICS / SQL / DLI handlers, `DFHRESP(` checks and `IF SQLCODE` tests (with or without
    a parenthesis) count too.
- **`safety_bypasses`** — a disabling prefix (`(NOSIZE):`), a null on-unit (`ON CONVERSION;`),
  `GO TO` / `GOTO`, and COBOL's `IGNORE CONDITION`, `NOHANDLE` and `WHENEVER ... CONTINUE`.
- **`high_risk_execution`** — `STOP;` / `EXIT;`, `FETCH name;` / `RELEASE name;` (loading and
  unloading code at run time), and dynamic SQL.
  - `GO TO EXIT;` and `CALL STOP;` are excluded, because there `EXIT` and `STOP` name a target.
- **`io`** — record I/O: `OPEN` / `READ` / `WRITE` / `REWRITE` / `DELETE FILE(...)` and `LOCATE rec
  FILE(...)`.
  - Stream input (`GET`) and `PUT ... FILE(f)` to a file other than SYSPRINT count.
  - COBOL's CICS file/queue/counter commands, `EXEC SQL` / `EXEC DLI`, and `CALL PLITDLI` /
    `AIBTDLI` / `CEETDLI` count too.
- **`api`** — fallback family (`docs/api_rule_contract.md`): `OPTIONS(MAIN)` / `OPTIONS(FETCHABLE)`,
  a `PACKAGE`'s `EXPORTS(...)`, and a `label: ENTRY` statement.
  - An external procedure is public by default, but nothing in its syntax separates it from an
    internal one.
- **`_visibility_export_list`** — the `EXPORTS(...)` region, so naming a procedure in the export
  list does not clear its `unreferenced_by_name` flag (#2823's shape).
- **`state_mutation`** — an assignment statement, including compound operators and multiple
  targets (`A, B = 0;`), anchored to a statement start: after `;`, THEN, ELSE, OTHERWISE or a
  `WHEN(...)` guard.
  - PL/I spells assignment and equality alike, so the anchor is the whole rule.
  - `IF X = 1`, a continued condition line, `DO I = 1` and `DCL ... INIT(0)` don't count.
- **`dead_code`** — a `/*` or `//` comment whose text is a statement: CALL, IF ... THEN, DO WHILE,
  DCL, EXEC CICS/SQL, or `%INCLUDE`.
- **`doc`** — a `/**` block still open at the end of its line, or a `/* PURPOSE:` /
  `DESCRIPTION:` / `ABSTRACT:` / `REMARKS:` header.
  - One-line `/** ... **/` banners are excluded: navikt/DSF writes 579 of them.
- **`test`** — the framework names ZUNIT and TEST4Z.

### Phase 3 — architecture and domain sensors
- **`concurrency`** — ATTACH, DETACH, `WAIT(`, and COBOL's CICS async / interval / task-control
  commands.
- **`ui_framework`** — COBOL's CICS terminal commands (SEND, CONVERSE, ...) and the BMS macro names.
- **`globals`** — STATIC and EXTERNAL storage (`STATIC EXTERNAL` counts once). EXTERNAL ENTRY
  declarations are linkage, not state, and don't count.
- **`decorators`** — the `*PROCESS` / `%PROCESS` directive and an `OPTIONS(...)` attribute list.
- **`scientific`** — the math built-ins in call form (SQRT, SIN, ..., RANDOM). ABS, MOD, MAX, MIN
  and SUM are excluded, because PL/I subscripts arrays with parentheses too.
- **`reflection_metaprogramming`** — the DEFINED overlay attribute, and COBOL's EXEC blanket.
- **`import`** / **`_dependency_capture`** — `%INCLUDE` / `%XINCLUDE` in every form (`name`,
  `ddname(member)` → the member, `(member)`, a quoted path) and `EXEC SQL INCLUDE`.
- **`ownership`** — the C family's author/maintainer comment tags.

### Phase 4 — specialised subsystems
- **`planned_debt`** / **`fragile_debt`** — the shared global patterns.
- **`spec_exposure`** — `[SPEC-n]` / `[spec]` / `[audit]`.
- **`ssr_boundaries`** — COBOL's CICS WEB / DOCUMENT API.
- **`events`** — CICS SIGNAL EVENT and `CALL MQPUT(`.
- **`macros`** — the preprocessor (`%DCL`, `%IF`, `%DO`, `%END`, `%ACTIVATE`, `%REPLACE`, `%NOTE`,
  `%GO TO`) and `%name: PROC`. `%INCLUDE` is import's; `%SKIP` / `%PAGE` / `%PRINT` only format the
  listing.
- **`pointers`** — POINTER/PTR, BASED, `->`, `ADDR(` / `NULL(` / `SYSNULL(`, the PTRADD family, and
  CICS ADDRESS. HANDLE is left out: CICS spells HANDLE CONDITION with the same word.
- **`memory_alloc`** — ALLOCATE/ALLOC, FREE (the COBOL / #1142 dual with `cleanup`), and CICS
  GETMAIN / FREEMAIN.

### Phase 5 — resource management and stability
- **`telemetry`** — COBOL's CICS diagnostics, plus `CALL PLIDUMP` / `CEE3DMP` / `CEEMOUT` /
  `CEEDUMP` / `DSNTIAR`.
- **`debug_prints`** — PUT to SYSPRINT (`PUT SKIP LIST(...)`, `PUT FILE(SYSPRINT) ...`) and
  `DISPLAY(`. `PUT STRING(...)` formats memory and is neither.
- **`explicit_casts`** — UNSPEC / HEX / HEXIMAGE / BINVALUE / CHARVAL / UCHAR / WCHAR / UTF8, and
  FIXED( / FLOAT( / DEC( / BIN( / CHAR( / BIT( right after an operator. The same words as
  declaration attributes (`DCL X CHAR(8)`) don't count.
- **`panics_and_aborts`** — SIGNAL / RESIGNAL, STOP / EXIT (the #2878 dual), CICS ABEND, and
  `CALL CEE3ABD`.
- **`thread_sleeps`** — `DELAY(ms)` and CICS DELAY / SUSPEND.
- **`bitwise_ops`** — IAND, IOR, IEOR, INOT, ISLL, ISRL, ISRA, RAISE2, BOOL. `&` / `|` are the
  logical operators on BIT(1) values.
- **`sync_locks`** — CICS ENQ.
- **`immutability_locks`** — the `VALUE(` named-constant attribute, and NONASSIGNABLE / NONASGN.
- **`cleanup`** — `CLOSE FILE(`, `DELETE FILE(`, `FREE name`, SQL CLOSE, and CICS ENDBR /
  SPOOLCLOSE / DELETE / FREE CHILD.
- **`encapsulation`** — the INTERNAL attribute (a quoted `'INTERNAL'` is data).
- **`listeners`** — `CALL MQGET(`, and CICS RECEIVE / CONVERSE / HANDLE AID.
- **`serialization_parsing`** — the JSON built-ins, XMLCHAR / XMLCLEAN, PLISAXA-D, and CICS
  TRANSFORM.
- **`time_date_logic`** — the date/time built-ins in call form, CICS ASKTIME / FORMATTIME /
  CONVERTTIME, and the LE date services.
- **`ipc_rpc_bridges`** — COBOL's CICS program-control and channel commands, `EXEC SQL` / `DLI`,
  and the IMS call interfaces.

## 4. What GitGalaxy explicitly does not track

| key | why `None` |
|---|---|
| `closures` | no anonymous procedure; every procedure carries a label |
| `generics` | no parametric types (GENERIC selects among entry constants — overload resolution) |
| `comprehensions` | no collection-transform form; array expressions are whole-array arithmetic |
| `hardcoded_secrets` | a baseline rule in three languages only; the security lens covers PL/I |
| `dependency_injection` | no IoC convention |
| `inline_asm` | no embedding form; `OPTIONS(ASSEMBLER)` is a linkage convention |
| `test_skip` | no framework marker for a skipped PL/I test |
| `regex_execution` | no regular-expression facility; INDEX/VERIFY/SEARCH/TALLY are plain searches |

## 5. Known limitations (accepted, not fixed)

No test is named `known_limitation`. The approximations below are documented in the rule comments,
and §8 measures them:

- **Nested procedures end their parent's body early.** Mode A slicing runs a body to the next
  `func_start` match, so an internal procedure cuts its parent's body off. Ada's nested
  subprograms take the same approximation.
- **`api` sees only explicit entry points.** A plain external procedure with no `OPTIONS(MAIN)`
  is public but invisible to the rule.
- **`state_mutation` misses a labelled assignment** (`L1: X = 1;`) and an assignment right after
  an ON condition. Both are rare in the measured corpora.
- **`time_date_logic` counts `TIME(` inside CICS timer options** (`EXEC CICS POST TIME(...)`).
- **The golden masters cannot catch a PL/I regression yet** (see the scope note).

## 6. Test depth

- `tests/extraction/languages/test_pli.py` — 54 cases: `func_start`, `args`, `class_start`,
  `_dependency_capture` × valid/invalid/pathological, plus ReDoS detonations.
- `tests/extraction/languages/test_pli_strict.py` — 158 cases:
  - a positive/negative pair for every live rule;
  - schema completeness and the exact `None` set;
  - Prism stripping on both comment styles, with a quoted `/* */` and `//`;
  - the `@#$` identifier-guard audit and the `re.M` audit;
  - CICS/SQL/DLI parity with COBOL;
  - the intended duals and enforced separations, and an exact `state_mutation` count;
  - the real extractor's Mode A slicing and per-procedure args;
  - 30 ReDoS payloads, and the api contract.

## 7. Relevant closed work

- #2502 — this addition (CICS / SQL / io focus, epic #2516).
- #1142 — the earlier aerospace-epic (#75) PL/I issue (`structural_boundaries` / `memory_alloc`),
  consolidated into the same profile.

## 8. Real-world evidence

`gitgalaxy-raw-output` has no PL/I scan yet: its `zopeneditor-sample` run predates the language, so
the PL/I members were never classified. The rules were measured instead by a probe of every
compiled rule over the Prism code stream (comment rules over the raw text) of **1,560 PL/I files
(~620k lines)** from five public repositories:

| repository | license | PL/I files | what it exercises |
|---|---|---|---|
| [navikt/DSF](https://github.com/navikt/DSF) | MIT | 1,473 | decades of production CICS + IMS (`CALL PLITDLI`), fixed format with columns-73-80 sequence numbers, Norwegian identifiers, CRLF |
| [zowe/zowe-pli-language-support](https://github.com/zowe/zowe-pli-language-support) | EPL-2.0 | 73 | deliberate syntax samples: `EXEC SQL`, preprocessor, `DEFINE ORDINAL`, `//` comments, PACKAGE |
| [RocketSoftwareCOBOLandMainframe/BankDemo](https://github.com/RocketSoftwareCOBOLandMainframe/BankDemo) | demo | 30 | CICS + SQL banking app |
| [IBM/Bank-of-Z](https://github.com/IBM/Bank-of-Z) | Apache-2.0 | 2 | Db2 batch |
| [IBM/zopeneditor-sample](https://github.com/IBM/zopeneditor-sample) | Apache-2.0 | 8 | plain batch SAM I/O, preprocessor procedures |

Headline counts from that probe:
- **func_start:** 4,674 procedures in 1,542 files. The raw `PROC`/`PROCEDURE` token count is
  about 4,820; the difference is mostly `%` preprocessor procedures and tokens outside a
  declaration.
- **import:** 7,733 `%INCLUDE` statements.
- **CICS** (a sample of the `EXEC CICS` rules): `ui_framework` 2,348, `listeners` 651, and
  `ipc_rpc_bridges` 3,028 (with IMS).
- **io:** 2,295.
- **pointers:** 4,910.
- **state_mutation:** 98,367.

Precision was checked by reading random samples for every rule, and five problems found that way
were fixed before merge:
1. `GO TO EXIT;` read as a program exit.
2. `EXTERNAL ENTRY` read as a global.
3. `/** banner **/` read as a doc comment (579 → 3).
4. A quoted `'INTERNAL'` read as encapsulation.
5. Preprocessor-procedure parameters were counted as args.

End to end, a real `galaxyscope` scan classifies every `.pli` in the Zowe samples (72 files, 215
procedures) and in zopeneditor-sample (4 files, 8 procedures — every real procedure, none of the 3
preprocessor ones), with PSAM2's two-line parameter list counted as `args = 2`.

## 10. Rosetta cross-language consistency (control-corpus capstone)

The `data/pli/` control folder was authored with the language (keyword-rosetta companion PR to
#3057). Measured against this branch at full precision: `verify_language.py pli` **PASS, 74
assertions** — every probe reads its planted count — and `language_deviations.py pli` reports **0
red / 0 amber unexplained across 59 comparable metrics**. The corpus-wide open-defect share stays at
0 of 2,691 cells with pli included.

Grouped by the `rosetta-language-sweep` five-cause taxonomy:

- **Real engine bug:** none.
- **Missing rule with genuine morphology:** none.
- **Corpus authoring gap:** one, fixed before the folder shipped. `c.pli` first lacked the
  corpus-wide engine-lens secret plant (`api_key = "R0SETTA-PLANT-SECRET-2026"` in a comment), so
  `risk_secrets_risk` read 0 against a median of 25.
- **Intended morphology (ledgered):** `raw_arch_api` reads 1.25 against a median of 3. A PL/I
  PACKAGE names its whole public surface once, in `EXPORTS(...)`, so api is 1 per file (2 in main,
  where `OPTIONS(MAIN)` also counts). It is haskell's shape, and pli joins the
  `api-export-list-morphology` entry.
- **Median inflation:** none.

The remaining out-of-band cells are `risk_churn` and `risk_stability`, which measure commit age
(the folder is new). They are not gated.
