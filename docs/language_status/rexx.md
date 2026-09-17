# REXX — Structural Signature Coverage

Snapshot written 2026-09-16 with the language's addition (#2504, under the legacy-mainframe
epic #2516). Source: `LANGUAGE_DEFINITIONS["rexx"]` in
`gitgalaxy/standards/language_standards/languages/rexx.py` and
`tests/extraction/languages/test_rexx_strict.py`. Re-run the `language-status` skill's
data-gathering commands before trusting these numbers if this doc looks old relative to
`last_updated` below.

**Scope note:** REXX is tree-sitter-blind to this repo's comparison tooling (the
jcl/cobol/bms/hlasm position), and no ground-truth parser diff was run, so there is no §9.
The pinned language-crucible corpus carries no REXX sources — its `.cmd` files are Windows
batch wrappers (`@echo off` + `%~dp0`) and must STAY classified `batch` through this change;
that regression is pinned by the strict suite's routing tests in both directions and by the
golden-master run (whose only diffs were `.bat` identity upgrades from batch's new
discriminator). The rules were validated by the 97-case strict suite and the keyword-rosetta
`data/rexx/` control shell (97 gate assertions).

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | z/OS TSO/E REXX (SAA) + Open Object Rexx 5.0 directives |
| `_meta.blueprint_version` | v6.3 |
| `_meta.last_updated` | 2026-09-16 |
| `lexical_family` | `recursive_block_rexx` — a new prism dialect family (#2504, the haskell/lisp #621/#770 precedent): the same nested-peel algorithm as `recursive_block` (REXX block comments genuinely nest), but **without** the shared family's `//` line token — `//` is REXX's integer-remainder operator — and with `--` (ooRexx/Regina/NetRexx) as the line comment. prism's combined literal pass also swaps to REXX quote morphology for this family: quotes double to escape (`'don''t'`), never backslash, and strings cannot span lines (both quote branches line-bounded, no backtick branch). The classic-REXX `5--3` double-negation is truncated by the `--` token — a documented, strict-suite-pinned trade (vanishingly rare vs. ubiquitous ooRexx comments). |
| `invocation_model` | default (`by_name`): `CALL name`, the function form `name()`, and `SIGNAL name` reach labels by writing their names, so the `unreferenced_by_name` census applies (#2866). |
| Structural signature keys wired | 35 / 53 (18 explicit `None`, see §4) |
| Extraction-gauntlet tests | — (strict suite drives the real extractor directly) |
| Strict-signature tests (`test_rexx_strict.py`) | 97 |

## 2. Identification surface — the `.cmd` collision (#2504's contested extension)

`rexx` claims `.rexx` (uncontested), `.exec` (z/OS SYSEXEC convention, uncontested) and
`.cmd` (contested — Windows/OS2 `batch` claims it too). `.cmd` is registered in
`_lens_config.py`'s `COLLISION_FREQUENCIES`, so Tier 1 never locks it on extension alone.
Routing then resolves:

1. **Tier 2 — `internal_discriminator`s, both claimants.** rexx's: a file whose first token
   is `/*` (the OS/2 and z/OS loaders' own dispatch rule for .cmd), or a line-anchored
   `PARSE ARG/PULL/SOURCE/VAR`, `ADDRESS <env>`, `SIGNAL/CALL ON|OFF`, `EXECIO`, or an
   ooRexx `::requires/::routine/::class/::method` directive. batch — whose `rules` dict is
   empty, so it can never win a Tier 3 lexical scan — gained its own discriminator in the
   same change (`@echo off/on`, `SETLOCAL/ENDLOCAL`, `goto :label`, `set NAME=` with no
   spaces, `if exist/defined`, `%~dp0`-style modifiers, `%ERRORLEVEL%`); registry order
   checks batch first, and its shapes are chosen to be impossible in REXX (bare `rem` and
   spaced `set = 1` are deliberately excluded — both are legal REXX assignments).
2. **Tier 1.5 — ecosystem gravity**: discriminators `.rexx`, `.exec`, `.jcl`; disqualifiers
   `.bat`, `.btm` (a `.cmd` beside `.bat` files is a Windows tree).
3. **Tier 3 — lexical scan** as the last resort.

Shebangs `rexx`, `regina`, `rexx64`, `oorexx` (Regina documents skipping a `#!` first
line). `case_insensitive_imports: True` (PDS members / case-blind host filesystems).

## 3. What GitGalaxy detects

The x/y/z coverage #2504 asked for, plus the rest of the baseline schema. The identifier
guards are explicit classes (`(?<![\w.!?@#$])` / `(?![\w.!?@#$])`) because REXX symbols
carry `! ? @ # $` and compound-variable dots — regex non-word characters a bare `\b`
cannot police (pli's discipline).

### Topology (x)
- **`func_start`** — a label `name:` at a line start (the subroutine/function `CALL`, the
  function form and `SIGNAL` reach; `PROCEDURE`, when present, follows the label and needs
  no separate alternative), plus ooRexx `::ROUTINE name` / `::METHOD name`. The `(?!:)`
  guard keeps `::` directive lines out of the label alternative.
- **`class_start`** — ooRexx `::CLASS name` only (named-class extraction enabled via
  `_CLASS_START_NAMED_EXTRACTION_LANGS`); classic REXX has no type declaration.
- **`args`** — `PARSE [UPPER|LOWER] ARG`, statement-position `ARG <template>` and ooRexx
  `USE [STRICT] ARG`: the constructs that stand in for a declared parameter list (#2773's
  fallback family — labels carry no formal list). `ARG(1)` is the built-in and never
  matches.
- Extraction runs through **Mode A** ("greedy to the next func_start match", COBOL's
  paragraph slot): routines never nest, and `RETURN`/`EXIT` are already in the shared
  `assembly_returns` terminator vocabulary, so each label's body ends at its return or the
  next label.

### I/O & bridging (y)
- **`io`** — `EXECIO` (z/OS dataset I/O, issued as a quoted host command — string
  literals stay in the code stream, #2535, so the quoted form is exactly what fires); the
  SAA stream functions `LINEIN( LINEOUT( CHARIN( CHAROUT( STREAM(` and TSO's `OUTTRAP(`;
  `PULL` / `PARSE PULL` (external data queue / terminal reads) and statement-position
  `PUSH` / `QUEUE` (stack writes — the stack is how execs feed EXECIO and host commands).
- **`ipc_rpc_bridges`** — the `ADDRESS` statement (`ADDRESS TSO`, `ADDRESS ISPEXEC`,
  `ADDRESS VALUE expr`): REXX's host-command bridge. **Documented deviation from the issue
  text:** #2504 grouped ADDRESS under `io`, but the io contract's unit is a data mover and
  the bridge statement is ipc's "site that crosses a process or host boundary" (the
  hlasm-DSECT contract-over-issue-text shape, pinned in the strict suite). `ADDRESS()` is
  the built-in and never matches.

### Control flow (z)
- **`branch`** — `IF`/`ELSE` and `SELECT`'s `WHEN`/`OTHERWISE` arms (SELECT anchored to
  its `;`/EOL/`LABEL` shape), loop openers `DO WHILE/UNTIL/FOREVER` and the iterative
  `DO i = ...`. `THEN` is #2822's excluded continuation word, `END` a closer, plain `DO;`
  a group, `LEAVE`/`ITERATE` transfers.

### Safety & risk
- **`safety`** — `SIGNAL ON <cond>` / `CALL ON <cond>` handler installs, and the
  `IF RC` / `WHEN RC` return-code test every host-command exec writes (pli's `IF SQLCODE`
  precedent; `when rc = 8` is a deliberate branch+safety dual, pinned).
- **`safety_bypasses`** — `SIGNAL OFF` / `CALL OFF` (handler removal) and the bare
  `SIGNAL label` / `SIGNAL VALUE expr` unstructured jump (the GO TO ruling).
- **`high_risk_execution`** — `INTERPRET` (running text as code) and the `EXIT` statement
  (termination; the #2878 dual with `panics_and_aborts`, which also carries ooRexx
  `RAISE <cond>`). `SIGNAL EXIT` / `CALL EXIT` / a label line `EXIT:` fire neither.
- **`state_mutation`** — statement-anchored assignment (REXX has no declaration syntax,
  so the assignment is the write — the shell/php/tcl ruling) with compound/stem lvalues,
  plus `PARSE VAR` / `PARSE VALUE` (one owner per PARSE form: ARG is args', PULL io's).

### The rest, by owner
`globals` (`PROCEDURE EXPOSE`, `SYSVAR(`/`MVSVAR(`, ooRexx `.environment`/`.local`);
`telemetry` (the `TRACE` statement; `TRACE(` is the built-in); `debug_prints` (`SAY`);
`ui_framework` (ISPF panel services: `ISPEXEC ... DISPLAY/ADDPOP/REMPOP/SETMSG/PQUERY/
LMDDISP`); `cleanup` (`DROP`, EXECIO's `FINIS`, quoted TSO `FREE F|FI|DD|DDNAME|DA|
DATASET|DSNAME(`); `pointers` (`STORAGE(` — TSO/E absolute-address access);
`explicit_casts` (the radix built-ins `C2D( C2X( D2C( D2X( X2C( X2D( B2X( X2B(`);
`bitwise_ops` (`BITAND( BITOR( BITXOR(`); `scientific` (`RANDOM(`);
`reflection_metaprogramming` (`VALUE( SYMBOL( SOURCELINE(`); `time_date_logic`
(`DATE( TIME(`); `thread_sleeps` (`SysSleep`); `import`/`_dependency_capture` (ooRexx
`::REQUIRES`, quoted or bare member); `api` (`::ROUTINE/CLASS/METHOD/ATTRIBUTE ...
PUBLIC`); `encapsulation` (`... PRIVATE`; `PROCEDURE` alone is lexical scope, which #2766
excludes — the perl/shell precedent); `immutability_locks` (`::CONSTANT`); `doc` (`/**`
block open past its own line + `PURPOSE:/DESCRIPTION:/ABSTRACT:/REMARKS:/FUNCTION:`
header tags); `ownership` (author tags in `/* */`, `*` and `--` comments); `dead_code`
(commented-out CALL/IF-THEN/DO WHILE/EXECIO/PARSE/assignment under BOTH comment styles);
`structural_boundaries` (`RETURN PROCEDURE END NOP` + `CALL`, excluding `CALL ON/OFF`);
`planned_debt`/`fragile_debt` (the shared GLOBAL rules); `spec_exposure` (`[SPEC-n]`).

## 4. What it deliberately doesn't detect (18 explicit `None`s)

`test` (no framework executes classic REXX cases; ooTest has no per-case keyword),
`concurrency` (strictly serial; ooRexx early-REPLY has no anchorable shape),
`sync_locks` (serialization is the host's — a quoted `"ENQ ..."` is the host-command
surface), `closures` (every routine is a label), `decorators` (OPTIONS is a runtime
instruction, not an attribute), `generics`, `comprehensions`, `memory_alloc` (storage is
implicit), `inline_asm`, `macros` (no preprocessor), `dependency_injection`,
`ssr_boundaries`, `events`, `listeners`, `test_skip`, `serialization_parsing` (PARSE is
template parsing of strings, not an interchange format), `regex_execution`
(POS/INDEX/VERIFY take no pattern), `hardcoded_secrets` (the security lens's detector
covers rexx). The keyword-rosetta side ledgers the gated three as
`rexx-stated-absences` (concurrency|sync_locks|test).

## 5. Issues & evidence

- #2504 — the language-addition issue (this change; engine PR + keyword-rosetta corpus PR
  landed together).
- `tests/extraction/languages/test_rexx_strict.py` — 97 cases: per-signature
  positive/negative coverage, the nested `/* /* */ */` shielding proof the issue
  demanded, the `.cmd` collision in both directions, the SIGNAL/EXIT/PARSE ownership
  pins, the ADDRESS-is-ipc deviation pin, `re.M` and schema-completeness audits, and the
  scaled ReDoS detonation — which caught a real Rule-14 adjacent-quantifier defect in the
  first draft's compound-lvalue tails (`(?:\.[class-with-dot]{0,64}){0,6}` on a long dot
  run), fixed by excluding the dot from the segment class.
- keyword-rosetta `data/rexx/` — the 12-probe control shell (97 gate assertions), with
  the string decoy planted as a bare-string host-command statement (REXX's own idiom) so
  it adds no assignment.
