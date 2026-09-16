# HLASM / IBM Z Assembly — Structural Signature Coverage

Snapshot written 2026-09-16 with the language's addition (#2503, under the legacy-mainframe
epic #2516). Source: `LANGUAGE_DEFINITIONS["hlasm"]` in
`gitgalaxy/standards/language_standards/languages/hlasm.py` and
`tests/extraction/languages/test_hlasm_strict.py`. Re-run the `language-status` skill's
data-gathering commands before trusting these numbers if this doc looks old relative to
`last_updated` below.

**Scope note:** HLASM is tree-sitter-blind to this repo's comparison tooling (the
jcl/cobol/bms/db2_sql position), and no ground-truth parser diff was run, so there is no §9.
The pinned language-crucible corpus carries no z/Architecture sources — its `.asm` files are
all genuinely x86/ARM (NASM test suite, bare-metal Raspberry Pi kernels) and must STAY
classified `assembly` through this change; that regression is pinned by the strict suite's
routing tests and the golden-master run. The rules were validated by the 145-case strict
suite and the keyword-rosetta `data/hlasm/` control shell (98 gate assertions), not yet by a
large real-file probe like pli's 1,560-file pass.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | IBM High Level Assembler (HLASM) V1R6 for z/OS (z/Architecture) |
| `_meta.blueprint_version` | v6.3 |
| `_meta.last_updated` | 2026-09-16 |
| `lexical_family` | `positional_anchored`, through prism's **bms mode** (`*` and `.*` in column 1 only, no column-7 check, no inline split — #2505 built the mode for BMS, which *is* HLASM macro source; #2503 widened the gate to `lang_id in ("bms", "hlasm")` at both call sites). Trailing remarks are positional, not delimited, and stay in the code stream; operation-field anchoring is every rule's shield. |
| `invocation_model` | default (`by_name`), deliberately unlike bms/jcl: `L 15,=V(name)` + `BALR`, the `CALL` macro and `USING dsect,reg` reach extracted units by name, so the `unreferenced_by_name` census applies (#2866 corollary 4 answered *yes*). |
| Structural signature keys wired | 44 / 54 (10 explicit `None`, see §4) |
| Extraction-gauntlet tests | — (strict suite drives the real extractor directly) |
| Strict-signature tests (`test_hlasm_strict.py`) | 145 |

## 2. Identification surface — the `.asm` collision (#2503's core requirement)

`hlasm` claims `.asm` (contested — the x86/ARM `assembly` profile's oldest extension), `.mac`
(macro members) and `.hlasm` (IBM Z Open Editor / zAppBuild convention, uncontested). `.asm`
is registered in `_lens_config.py`'s `COLLISION_FREQUENCIES`, so Tier 1 never locks it on
extension alone (without that entry, `_calibrate_lookup_maps`' registration-order overwrite
would silently hand it to whichever profile registered last — the #2511 `.sql` lesson).
Routing then resolves in order:

1. **Tier 2 — `internal_discriminator`** (raw content, pre-comment-strip): tokens no x86/ARM
   assembler file can carry in operation-field position — `CSECT`, `DSECT`, `RSECT`,
   `AMODE`, `RMODE`, `USING`, `LTORG`, `MEND` (MASM's closer is `ENDM`), and the CICS bridge
   pair `DFHEIENT`/`DFHEIRET`. The name-field anchor (`^[A-Za-z0-9@#$]{0,63}[ \t]+`) refuses
   a `*` comment line, so a banner *mentioning* CSECT cannot lock a file. `assembly`
   deliberately has no internal_discriminator, so a z/OS fingerprint wins outright and a
   NASM/GAS file falls through.
2. **Tier 1.5 — ecosystem gravity**: discriminators `.mac`, `.jcl`, `.cbl`, `.cob`, `.cpy`,
   `.pli`, `.pl1`, `.bms` (the mainframe repo an HLASM member lives in). Disqualifiers
   `.nasm`, `.masm`, `.s`, `.S`, `.ld`, `CMakeLists.txt` collapse the hlasm claim in an
   x86/ARM neighborhood (the #377 toxic-neighbor mechanism, bms's `.map` shape).
3. **Tier 3 — lexical scan** as the last resort, over both candidates' rules.

No shebangs (assembled by ASMA90), no exact filenames. `case_insensitive_imports: True`
(COPY members are PDS members).

## 3. What GitGalaxy detects

The x/y/z coverage #2503 asked for, plus the rest of the baseline schema. Identifier class
is `[A-Za-z@#$][A-Za-z0-9@#$]{0,62}` (ordinary symbols, 63 chars); every code-stream rule
anchors the operation field (`^name-or-nothing + blanks + OP`) and terminates it on
blank/EOL — never `\b`, which would fire between `WAIT` and `=` on a keyword operand
(`WAIT=YES` on a continuation line is the Rule 9 trap the strict suite pins).

### Topology (x)
- **`func_start`** — `name CSECT`, `name RSECT`, `name START`: the named control sections
  other members reach via `=V(name)`/`CALL`. **Documented deviation from the issue text:**
  #2503 asked for DSECT here too, but a dummy section is a named storage *layout* that
  assembles no executable logic — #2856's type-declaration exclusion — so:
- **`class_start`** — `name DSECT` (the record/struct family, reached by `USING name,reg`).
  Named-class extraction is enabled via `_CLASS_START_NAMED_EXTRACTION_LANGS`.
- **`args`** — the MACRO prototype's symbolic-parameter list (`&LAB MYMAC &A,&K=dflt`),
  spanning the `MACRO` line onto the prototype line: the only construct that *declares*
  parameters (executable units receive theirs via the undeclared R1 convention — the #2773
  fallback family).
- Extraction runs through **Mode A** ("greedy to the next func_start match" — the
  bms/#3077 slot in `detector.py`'s routing tuple): control sections never nest, so each
  named section's body ends where the next section statement (or EOF) begins.
- **`branch`** — conditional branches only: extended mnemonics (`BE/BNE/BH/BNL/...` and `R`
  forms), `BC/BCR`, relative `J*`, branch-on-count/index loops (`BCT/BCTR/BCTG/BXH/BXLE`),
  compare-and-branch (`CIJ/CRJ/CLIJ/...`). Unconditional `B/BR/J/BAL/BALR/BAS/BASR` are
  `structural_boundaries`' (#2764: a call is not a decision), alongside the
  load/store/move/compare/arithmetic core and the assembler's structural directives.

### CICS / system bridges (y)
- **`ipc_rpc_bridges`** — `DFHEIENT`/`DFHEIRET` (the issue's named ask: the command-level
  entry/return bridge), z/OS `LINK`/`XCTL` with the `EP=/EPLOC=/DE=` operand shape, and the
  CICS program-control + container vocabulary shared verbatim with cobol/pli (#2990):
  `EXEC CICS LINK/XCTL/START/RETURN/RUN TRANSID/INVOKE`, `PUT/GET/MOVE CONTAINER`,
  `EXEC SQL`/`EXEC DLI`, and `CALL ASMTDLI/AIBTDLI/CEETDLI`.
- The whole CICS command surface is inherited from the cobol/pli vocabulary (#2990) so the
  three mainframe hosts count the same commands the same way: io (file/queue commands +
  native `OPEN/GET/PUT/READ/WRITE/CHECK/POINT` access-method macros), safety
  (`HANDLE CONDITION`, `ESTAE(X)/ESPIE/SPIE/SETRP` recovery installs), ui_framework
  (`SEND/CONVERSE` + the `DFHMSD/MDI/MDF` macros for mapsets kept in `.asm` members),
  concurrency (`ATTACH/DETACH/WAIT/POST` + CICS task coordination), and the rest.

### Macros (z)
- **`macros`** — `MACRO`/`MEND`/`MEXIT`, conditional assembly (`AIF/AGO/ANOP/ACTR/AREAD`),
  `MNOTE`, the `SET` statements and their `GBL*/LCL*` declarations; the name field widens to
  sequence symbols (`.SKIP ANOP`) and SET symbols (`&X SETA 1`) — bms's shape, verbatim.

### Notable single-owner / dual rulings (decision-table entries where they exist)
- `ABEND` → `high_risk_execution` **and** `panics_and_aborts` (the #2878 termination dual);
  `MODESET` → protection escape; `LOAD/DELETE EP=` → the loading-code family (pli's
  FETCH/RELEASE precedent).
- Storage RMW (`OI/NI/XI/OC/NC/XC/AP/SP/MP/DP`) → `state_mutation` (assembly.py's
  fallback-family ruling: a plain `ST`/`MVC` store is the language's baseline, not a
  re-assignment signal); register logicals + shifts (`NR/OR/XR/SLL/...`) → `bitwise_ops`.
  One owner per form.
- `FREEMAIN`/`STORAGE RELEASE` → `memory_alloc` **and** `cleanup` (pli's ALLOCATE/FREE
  dual); `CLOSE` → `cleanup` alone (#2841 C2).
- `name DC` (named, initialized storage) → `globals`; named `DS` is **excluded** by Rule
  17's enclosing-form ambiguity (the identical line is program storage in a CSECT and a
  zero-emission layout field in a DSECT). `GBLA/GBLB/GBLC` stay `macros`' (bms's ruling).
- `name EQU` + `RSECT` → `immutability_locks`; `EQU` was removed from the structural tally
  to keep one owner.
- `EX/EXRL` → `reflection_metaprogramming` (runtime instruction modification); `LA` is
  **excluded** from `pointers` (it is also assembler's everyday unsigned add — Rule 2);
  pointers = the `A`/`V` address constants (`DC A(x)`, `=V(sub)`).
- `WTO/WTOR` → `debug_prints` (operator dialog); `SNAP(X)/WTL` + CICS diagnostics →
  `telemetry`.
- `ESTAE 0` (handler **cancel**) → `safety_bypasses`, guarded out of `safety` by a
  negative lookahead the strict suite detonates (Rule 15).

## 4. Explicit `None` keys (10)

`closures` (every unit carries a name), `generics`, `comprehensions`, `test` + `test_skip`
(zUnit/Test4z execute COBOL/PL/I test cases, not assembler — the yacc ledger family),
`dependency_injection`, `inline_asm` (this *is* assembly — the assembly/agc ledger absence),
`encapsulation` (a non-section label is file-local by *lexical scope*, which #2766 rules out
— the perl `my`/shell `local` precedent), `regex_execution` (`TR`/`TRT` are table
translate/scan, no pattern — pli's INDEX/VERIFY exclusion), `hardcoded_secrets` (the
security lens's own detector covers hlasm).

## 5. Corpus / verification evidence

- **keyword-rosetta `data/hlasm/`** (companion PR, branch `corpus/hlasm2503`): 4-file
  COPY-chained shell, 13 CSECT units, 98 gate assertions, PASS. Notable engine facts it
  pinned: `api_orphan_credit` reads 0 because every uncalled CSECT's declaration line is
  itself an api hit (#2731, the go shell's shape); the string decoy works through the
  *unanchored* `EXEC CICS` alternations (statement-anchored rules cannot be struck
  mid-literal, so `DC C'EXEC CICS ABEND ...'` is the one shape that pins gitgalaxy#2535
  here).
- **Strict suite**: 145 cases — per-rule positive/negative coverage, schema completeness,
  collision routing through the real `LanguageDetector` (HLASM-in-`.asm` → hlasm, NASM-in-
  `.asm` → assembly), prism family checks (the #1898 C-name survival, third landing), Mode A
  extraction, and a 35-payload ReDoS detonation sweep including the issue's named "long
  macros" case. The adversarial pass caught and fixed two real defects pre-merge:
  `dead_code` firing on `* DC POWER SUPPLY NOTES` banner prose, and
  `_visibility_export_list` capturing a blanks-only region.
- **Golden crucible**: the corpus carries no z/Architecture sources; the assertion this
  change makes is *negative* — every NASM/bare-metal `.asm` file keeps `assembly` (see the
  engine PR's diff narrative).

## 6. Known gaps / follow-ups

- No real-corpus HLASM in language-crucible; adding a genuine z/OS member set (e.g. a
  CICS sample application's assembler parts) is a follow-up, mirroring the db2_sql note.
- Continuation semantics (non-blank column 72, resume at column 16) are not modeled as
  columns; multi-line macro invocations count once per statement only because the rules
  anchor the first physical line. Adequate for counting, not for operand parsing.
- `.mlc`/`.asmpgm` (other IBM DBB conventions) are unclaimed; add on demand.
