---
description: "Snapshot written 2026-09-16 with the language's addition (#2503, under the legacy-mainframe"
---
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
routing tests and the golden-master run. The rules were validated by the 185-case strict
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
| Strict-signature tests (`test_hlasm_strict.py`) | 185 |

## 2. Identification surface — the `.asm` collision (#2503's core requirement)

`hlasm` claims `.asm` (contested — the x86/ARM `assembly` profile's oldest extension), `.mac`
(macro members) and `.hlasm` (IBM Z Open Editor / zAppBuild convention, uncontested). `.asm`
is registered in `_lens_config.py`'s `COLLISION_FREQUENCIES`, so Tier 1 never locks it on
extension alone (without that entry, `_calibrate_lookup_maps`' registration-order overwrite
would silently hand it to whichever profile registered last — the #2511 `.sql` lesson).
Routing then resolves in order:

1. **Tier 2 — `internal_discriminator`** (raw content, pre-comment-strip): tokens no x86/ARM
   assembler file can carry in operation-field position — `CSECT`, `DSECT`, `RSECT`,
   `AMODE`, `RMODE`, `USING`, and the CICS bridge pair `DFHEIENT`/`DFHEIRET`. `MEND` and `LTORG`
   no longer lock on their own (#7064): ARM `armasm` closes its `MACRO` with `MEND` too and has
   `LTORG`, so ten ARM64 `.asm` files in a .NET runtime checkout routed to hlasm. They count only
   with HLASM-only evidence: a `MACRO` whose prototype line carries an `&` symbolic parameter
   (armasm's are `$`), or an `AIF`/`AGO`/`ANOP`/`MNOTE` statement (`MEXIT`, `GBLA`, `SETA` exist
   in armasm and are not used). The name-field anchor (`^[A-Za-z0-9@#$]{0,63}[ \t]+`) refuses
   a `*` comment line, so a banner *mentioning* CSECT cannot lock a file. `assembly`
   deliberately has no internal_discriminator, so a z/OS fingerprint wins outright and a
   NASM/GAS file falls through.
2. **Tier 1.5 — ecosystem gravity**: discriminators `.mac`, `.jcl`, `.cbl`, `.cob`, `.cpy`,
   `.pli`, `.pl1`, `.bms` (the mainframe repo an HLASM member lives in). `.mac` is also in
   `extensions_needing_discriminator` (#7064): it is proof-only for hlasm, because NASM, MASM,
   troff and DSP macro files share it. A `.mac` locks hlasm only through the Tier 2 patterns
   above (an `&` macro prototype is enough, so maclib members route correctly). Disqualifiers
   `.nasm`, `.masm`, `.s`, `.S`, `.ld`, `CMakeLists.txt` collapse the hlasm claim in an
   x86/ARM neighborhood (the #377 toxic-neighbor mechanism, bms's `.map` shape).
3. **Extensionless PDS members (#7064)**: a file with no extension under a directory whose last dot-suffix is `asm`
   or `maclib` (`PAYR.ASM/ACCTPGM`, `SYS1.MACLIB/GETIT`; the dataset qualifier of an exported PDS) routes hlasm at
   Tier 1.5, but only with content evidence: the `internal_discriminator`, or hlasm winning the lexical scan.
   `library_directory_suffixes` on the definition holds the suffixes; `LanguageDetector._pds_library_lang` reads it.
   Pinned in `test_hlasm_strict.py`.
4. **Tier 3 — lexical scan** as the last resort, over both candidates' rules.

No shebangs (assembled by ASMA90), no exact filenames. `case_insensitive_imports: True`
(COPY members are PDS members).

## 3. What GitGalaxy detects

The x/y/z coverage #2503 asked for, plus the rest of the baseline schema. Identifier class
is `[A-Za-z@#$][A-Za-z0-9@#$]{0,62}` (ordinary symbols, 63 chars); every code-stream rule
anchors the operation field (`^name-or-nothing + blanks + OP`) and terminates it on
blank/EOL — never `\b`, which would fire between `WAIT` and `=` on a keyword operand
(`WAIT=YES` on a continuation line is the Rule 9 trap the strict suite pins).

### Call graph (`calls_out`, #7063)
- **`calls_out`** names the callee of three forms, one capture group: the `=V(name)` address constant;
  the `CALL name[,(parms)]` macro (the first operand is the target); and `LINK` / `XCTL ... EP=name`
  (`EP=` may follow other keyword operands). `CALL (15)`, `CALL &SYM`, `EPLOC=`, `SF=` and
  `DFHPC TYPE=LINK` name no literal program and add no edge. The x86/ARM `assembly` profile is
  untouched. Strict suite: 33 new cases (152 -> 185) (one per form, plus the near-miss class and ReDoS payloads).

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
- **Strict suite**: 185 cases — per-rule positive/negative coverage, schema completeness,
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

- ~~No real-corpus HLASM in language-crucible~~ — crucible v1.5.0 added `hlasm/zecs` (the zECS
  CICS service's assembler) beside `che4z_hlasm` and `zopeneditor_sample` (22 files). *(2026-09-25)*
- Continuation semantics (non-blank column 72, resume at column 16) are still not modeled by the
  **signal** rules: a multi-line macro counts once per statement because the rules anchor on its
  first physical line. **`EXEC CICS` statements are the exception**: `core/hlasm_cics.py` (#3495)
  joins their continuations and parses the operands (§11).
- Extensionless PDS-style members (`HASH.ASM/MEMBER`, `*.MACLIB/MEMBER`) are not routed to hlasm
  (§12 sibling gap).
- `.mlc`/`.asmpgm` (other IBM DBB conventions) are unclaimed; add on demand.

## 11. CICS / mainframe system facts (added 2026-09-25)

The cross-language page is [cics_mainframe_facts.md](cics_mainframe_facts.md). What assembler gets:

- **Command-level `EXEC CICS`** (#3495). `core/hlasm_cics.py` rewrites each assembler statement, with
  its column-72 continuations joined, into the shape the COBOL walkers read. Assembler programs then
  get the same channels as COBOL:
  - call sites (LINK / XCTL / RETURN TRANSID);
  - CICS resource operations;
  - task control;
  - units of work, handlers and ABENDs.

  Operands resolve through `DC C'...'` constants. `OC v,v` and `CLC v,=F'n'` count as RESP checks.
  `name DFHEIENT` opens a program unit that other programs' LINKs resolve to.
- **Verification:** zECS's assembler programs are inside zECS's cross-verified counts: 61 CICS
  resource operations, 7 task-control rows and 134 unit-of-work rows, blind-reviewed in full.
- **Translation** (#5859, added 2026-10-29). Command-level CICS assembler inside the subset in
  [hlasm_cics_design.md](hlasm_cics_design.md) is lowered to a COBOL program (`det/hlasm.py`), then
  det-ported and proven like COBOL. ZECSNC and ZECS002 translate whole, and ZECS001 LINKs the
  lowered ZECS002. A POPS interpreter and a per-instruction differential cross-check the lowering.
  Outside the subset (for example arithmetic, packed decimal, `MVI`) a program is refused whole, by name.
- **IMS PSB / DBD macros** (`core/ims_gen.py`, #3477): cross-verified on CardDemo (39 facts,
  together with the JCL region steps).
- **Not supported:**
  - **macro-level CICS** (`DFHPC`, `DFHFC`, `DFHTC`, … — the pre-command-level API);
  - general macro expansion (a user macro that wraps `EXEC CICS` is not expanded);
  - any fact beyond CICS, DLI and IMS definitions outside the translation subset — for example, the
    register-level data flow of an assembler program the lowering refuses;
  - call-graph edges for `LINK`/`XCTL EPLOC=` (needs the `DC CL8'...'` constant) and user-macro
    uses (an operation-field name a `.mac` member or in-file `MACRO` prototype defines): they do not
    become edges. The `CALL` macro and `LINK`/`XCTL EP=` do (§3, #7063).
- **Single-sourced:** HLASM CICS rests on one corpus (zECS, a small service). The burned-estate census
  (#6963) pins every burned assembler member: the two zECS programs lowered, CardDemo's two batch
  routines modelled by hand-written runtime code.

## 12. Real-file probe and `.asm`/`.mac` misrouting (2026-10-29, #7064)

**Misrouting.** The corpus DB (`master_db_v2.9.0`) labels 112 files `hlasm`; the ones from
non-mainframe repos were re-routed with the current engine:

| Source | DB files | Cause | Now |
|---|---|---|---|
| .NET runtime ARM64 `.asm` | 10 | `MEND` (armasm's macro closer) locked Tier 2 | `assembly` (fixed) |
| NASM `.mac`, MS-DOS `.MAC` | 18 + 5 | DB predates #4975 / `.mac` was uncontested | fixed for hlasm (proof-only `.mac`); NASM goes to easytrieve through its `%macro` discriminator (sibling gap) |
| illumos DSP `.mac`, FreeBSD troff `.mac` | 2 + 2 | same | no longer hlasm; DSP lands in plaintext, troff in easytrieve (sibling gaps) |

The 24 `.asm`/`.mac`/`.hlasm` files that matched the old discriminator were re-checked: the
real HLASM ones that lost only the `MEND` lock (`mac.asm`, `ASMWAIT.mac`) are recovered by the
`&`-prototype rule; the rest are `.hlasm` (Tier 1). Pinned in `test_hlasm_strict.py`.

**Probe.** Genuine z/OS assembler (about 18k lines of code stream, 94 files) was run through every rule:
che4z samples 35, IBM-Z-zOS 1, CardDemo 12, zopeneditor-sample 3, zECS 2 (all route hlasm), plus
42 members of two PDS-layout repos probed with the hlasm rules forced (they do not route, below). The emulator repo's 32 DB-labelled files were not probed here (see the addendum).

| Signal | Files / hits | Reading |
|---|---|---|
| `func_start`, `class_start`, `api` | 40 / 53, 22 / 46, 38 / 62 | CSECT/RSECT/DSECT fire as intended |
| `macros` | 30 / 427 | MACRO/MEND/MEXIT/AGO/MNOTE; correct |
| `args` | 6 / 11 | macro prototype line only |
| `branch` | 32 / 415 | `J`/`JZ`/`JE`/`BE` fire; includes IBM extended mnemonics. A trailing remark such as `@L1A` stays in the line (positional comment, expected) |
| `safety_bypasses`, `io`, `memory_alloc`, `concurrency`, `auth_middleware`, `cleanup` | fire | system macros (NOHANDLE, STORAGE OBTAIN/RELEASE, ENQ/DEQ, RACROUTE) match |
| `immutability_locks` | 45 / 771 | `R0 EQU 0` register equates: correct per the profile, but dominates the count |
| `dead_code` | 6 / 11 | commented-out instructions (`*TRY LR 1,1`): correct |
| `test`, `closures`, `generics`, `comprehensions`, `regex_execution`, `encapsulation`, `inline_asm`, `hardcoded_secrets`, `dependency_injection`, `system_config_mutation` | none | explicit `None`, nothing expected |
| `calls_out` | 0 | **defect at probe time**, since fixed by #7063 / #7068 (CALL macro and LINK/XCTL `EP=` callees now named; see §3) |

False positives and misses recorded:

- **`calls_out` read 0 on every real file at probe time** (the rule matched only `=V(name)`); #7063 / #7068
  merged while this probe was in flight and added the CALL macro and `LINK`/`XCTL` `EP=` forms. Not re-measured here.
- **`pointers`/`globals` over-count `DC V(name)`** (7 + 6 + 3 identical hits in one hash-table
  file): `DC V()` is an address constant, so it is a legitimate pointer, but it is also counted as
  a global; the same line owns two signals.
- **`api`/`func_start` double-count a CSECT line** (`DSNX@XAC CSECT` fires both): the documented
  dual ruling, not a defect.
- **`fragile_debt` matches `xxx` placeholders in message text** (`RETURN CODE xxx`, `DS CL3'xxx'`):
  15 hits in one file, none are debt.
- **`planned_debt` matches `LOAD EP=BPX1GLG` stub lines** (9 hits in one file) where "stub" is the
  system service name, not a TODO.
- **`reflection_metaprogramming` counts every `EX R5,TBL`** (execute-target); it is the
  instruction-level analogue, kept by design.
- **PDS members are not routed to hlasm.** Extensionless members under `*.ASM/` and `*.MACLIB/`
  directories go to `go` (19), `undeterminable` (19) and `plaintext` (4) in the two PDS-layout
  repos (Tier 2 never runs without a candidate extension). The member files are genuine z/OS
  assembler.

Defect classes (one item each, reported to churn): (1) `BAL`/`BALR`/`BASR`/`ATTACH`/`LOAD` callee forms
still unnamed by `calls_out` after #7068 (unverified against it);
(2) `fragile_debt`/`planned_debt` false positives on message text and stub names; (3) PDS-style
extensionless members unrouted; (4) non-hlasm `.mac` families still misroute (NASM and troff
into easytrieve, DSP into plaintext).

### Addendum (2026-10-30, #7064): emulator-repo probe, `calls_out` re-measure, PDS routing

**Emulator-repo probe.** A shallow, read-only clone of the S/370-family emulator repo (scratch copy, nothing committed) holds
128 `.asm`/`.mac`/`.hlasm` files (test programs for the instruction set). All 123 the scan kept route `hlasm` (160,865 lines,
122,610 of code); none went to `assembly`. Per signal: `func_start` 182 and `class_start` 70 (CSECT/DSECT/RSECT), `branch` 2,090,
`macros` 1,225, `api` 182, `pointers` 5,176, `planned_debt` 1, `fragile_debt` 121. `pointers` dominates because the tests are
`DC A()`/`V()` address tables (the same line also counts as a global, as in the earlier probe); `fragile_debt` is the `xxx`
placeholder class again (message text in expected-result tables), not debt. Nothing else new: no non-HLASM file was labelled
`hlasm`, so the DB's 32 emulator files are not a routing bug.

**`calls_out` after #7068: 0 of 182 functions, and that is correct for these files.** The tests contain no `CALL`, `LINK`,
`XCTL`, `ATTACH` or `LOAD` statement at all (0 each); control transfer is `BAL` 515, `BASR` 245, `BALR` 149, whose targets are
registers or in-file labels, so no external callee can be named. The same holds for the 8 `.asm` files in the held mainframe
corpora (0 CALL/LINK/XCTL/LOAD, 24 `BAL`, 1 `BALR`). The Che4z samples are not held in this checkout, so the CALL-macro and `EP=`
forms are covered by the strict suite (`test_hlasm_calls_out_forms`) but have no real-file count here. Defect class (1) narrows to
"`BAL`/`BALR`/`BASR` to an in-file label is an internal edge, not an import": unmeasured, kept open.

**PDS routing.** Fixed (section 2, item 3). Members of the two PDS-layout repos are no longer split across `go`, `plaintext` and
`undeterminable` when they carry HLASM evidence. Sibling gaps (same mechanism, not done): `*.COPYLIB/`/`*.COBOL/` (cobol),
`*.PLI/` (pli), `*.JCL/`/`*.CNTL/` (jcl): each is one `library_directory_suffixes` entry plus a pin.
