# COBOL — Structural Signature Coverage

Snapshot generated 2026-08-19 against `main`. Source: `LANGUAGE_DEFINITIONS["cobol"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_cobol.py` /
`test_cobol_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

**Scope note:** COBOL has no tree-sitter grammar available to this repo's comparison tooling (one
of 9 "tree-sitter-blind" languages), so §9 below is a 2-way GitGalaxy/ctags comparison rather than
the usual 3-way tree-sitter-baselined shape used elsewhere in this doc set.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Enterprise COBOL 6.4 (IBM) & GnuCOBOL 3.2 |
| `_meta.blueprint_version` | v5.1 |
| `_meta.last_updated` | 2026-03-10 |
| `lexical_family` | `positional_anchored` (Family 7, "the Positional Ancients" — strictly fixed-format; the engine watches column 7 for a `*`/`/` line-comment indicator rather than a delimiter token) |
| Structural signature keys wired | 48 / 52 (4 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_cobol.py`) | 62 |
| Strict-signature tests (`test_cobol_strict.py`) | 82 |
| Total dedicated COBOL test cases | 144 |

## 2. Identification surface

- **Extensions:** `.cbl .cob .cpy .cobol .pco .cut` — standard source, the widely-used `.cob`
  variant, copybooks (`.cpy`, COBOL's header-file equivalent), and two rarer legacy-toolchain
  extensions (`.pco`, `.cut`).
- **Exact filenames:** none — mainframe shops don't use an extensionless canonical entry-point
  convention the way Python (`setup.py`) or PHP (`artisan`) do.
- **Discriminators:** `.cbl`, `.cob`, `.cpy`, `.jcl` — the sibling copybook extension plus Job
  Control Language, the batch-orchestration format that historically invoked COBOL programs on
  IBM mainframes.
- **Shebangs:** `cobc` — GnuCOBOL's compiler/interpreter invocation, the one realistic way a
  modern COBOL script gets a line-1 shebang at all.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` uses for COBOL. Description is what COBOL's
*actual* regex matches, not the generic cross-language definition.

**Logic topology & structure**
| Key | What it captures for COBOL |
|---|---|
| `branch` | `IF ELSE EVALUATE WHEN PERFORM UNTIL VARYING TIMES DEPENDING ON ON EXCEPTION AT END INVALID KEY ON SIZE ERROR ON OVERFLOW`, case-insensitive |
| `args` | `USING`/`RETURNING` parameter lists from `PROCEDURE DIVISION` headers and `CALL` statements, including `BY REFERENCE/CONTENT/VALUE` qualifiers and up to 20 comma-separated names; a negative lookahead excludes the literal word `RETURNING` from `USING`'s own capture so a combined `USING ... RETURNING ...` header (declaring a parameter and a return value in one line, common real Enterprise COBOL/GnuCOBOL) yields two separate `finditer` matches instead of one bleeding into the other (epic #813/#854 fix) |
| `structural_boundaries` | `DIVISION SECTION EXIT CONTINUE GOBACK ACCEPT XML PARSE JSON GENERATE DISPLAY STOP RUN` — deliberately excludes `GLOBAL`/`EXTERNAL` access modifiers to avoid inflating structural-complexity counts |
| `func_start` | Anchors paragraphs/sections via the "Iron Wall": an optional 6-character sequence-number margin-eater followed by a hard `\b` (the "Greedy Margin Trap" fix, so a flush-left name like `TargetFunc.` isn't chopped mid-word by the margin-eater); negative lookaheads ban data-division level numbers (`01`-`88`), ~30 reserved verbs/division/section headers, and any name immediately followed by `DIVISION`; captures the identifier, then an optional `SECTION` plus an optional 1-2-digit legacy segment number (COBOL-68/74-era program segmentation), terminated by a period. Handles both strict 80-column fixed format and free format |
| `class_start` | Anchors `PROGRAM-ID`/`CLASS-ID`/`INTERFACE-ID`/`FACTORY`/`OBJECT`, capturing the entity name and allowing up to 6 bounded trailing clause words (`IS INITIAL PROGRAM`, `IS COMMON PROGRAM`, `FINAL`, `INHERITS Base`) before the terminating period; `DIVISION` is excluded from that trailing-clause loop specifically so `FACTORY.`/`OBJECT.` (bare OO-COBOL structural markers, always followed by their own division header) don't miscapture the division name as if it were an entity name |

**Risk & structural integrity**
| Key | What it captures for COBOL |
|---|---|
| `safety` | `END-IF END-PERFORM END-EVALUATE END-READ END-WRITE END-COMPUTE END-CALL DECLARATIVES VALIDATE CHECK` — scope terminators and declarative blocks |
| `safety_bypasses` | `NEXT SENTENCE GO TO CORRESPONDING ANY LENGTH OMITTED` — unpredictable jumps and loose group-move correspondence |
| `high_risk_execution` | `STOP RUN ALTER CANCEL` — process termination and self-modifying-code (`ALTER`) risk |
| `io` | `READ WRITE REWRITE OPEN CLOSE START DELETE`, plus `EXEC SQL` and `EXEC CICS READ/WRITE/REWRITE/DELETE` — disk, database, and CICS transaction I/O |
| `api` | `ENTRY LINKAGE SECTION CALL INVOKE EXPORT` — exposed linkage points and external entry points |
| `state_mutation` | `MOVE COMPUTE ADD SUBTRACT MULTIPLY DIVIDE SET INITIALIZE REPLACE STRING UNSTRING` — the core of COBOL data manipulation |
| `dead_code` | Column-7 `*` or free-format `*>` comment prefix immediately followed by a real statement verb (`MOVE COMPUTE IF PERFORM CALL EXEC`) — i.e. commented-out logic, not just any comment |
| `doc` | `AUTHOR.`/`DATE-WRITTEN.`/`DATE-COMPILED.`/`REMARKS.`/`INSTALLATION.` identification-division headers, or `*> @param`/`@return`/`@author`-style Doxygen-ish tags |
| `test` | `ZUNIT CBLUNIT ASSERT TEST-CASE READY TRACE` — COBOL unit-testing framework markers |

**Architecture & domain sensors**
| Key | What it captures for COBOL |
|---|---|
| `concurrency` | `EXEC CICS ENQ/DEQ/WAIT/START/DELAY` — CICS task and resource coordination |
| `ui_framework` | `SCREEN SECTION`, `EXEC CICS SEND MAP`, `DFHMDF DFHMDI DFHMSD` — screen sections and CICS BMS map macros |
| `closures` | `None` — see §4 |
| `globals` | `WORKING-STORAGE SECTION COMMON GLOBAL EXTERNAL` |
| `decorators` | `>>` compiler-directive lines (`IF ELSE END-IF DEFINE CALL-CONVENTION`) — COBOL's nearest equivalent to annotations |
| `generics` | `CLASS-ID. Name USING Param` — parameterized classes (Modern/OO COBOL) |
| `comprehensions` | `None` — see §4 |
| `scientific` | `FUNCTION ACOS/ASIN/ATAN/COS/EXP/FACTORIAL/LOG/LOG10/MOD/RANDOM/SQRT/TAN/VARIANCE` — intrinsic math functions |
| `reflection_metaprogramming` | `REDEFINES RENAMES OCCURS DEPENDING ON EVALUATE TRUE EXEC CICS EXEC SQL` — memory aliasing/reinterpretation plus a bare CICS/SQL catch-all (see the double-classification note below) |
| `import` | `COPY`/`INCLUDE` copybook-inclusion statements. This key was added as a real, non-`None` rule under the Strict Feature Parity rule (`how_to_add_a_language.md`'s Rule 4) — it was previously silently absent from the `rules` dict entirely (not even an explicit `None`) despite `_dependency_capture` immediately below already extracting the same targets |
| `_dependency_capture` | Extracts the copybook name from `COPY`/`INCLUDE`, handling optional quotes and `OF`/`IN` library qualifiers |
| `ownership` | `AUTHOR.` line, capturing the author-name text that follows |

**Specialized subsystems**
| Key | What it captures for COBOL |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`, `[spec ...]`, `[audit ...]` traceability tags |
| `ssr_boundaries` | `EXEC CICS WEB SEND/DOCUMENT/WEB READ` — CICS web endpoints |
| `events` | `EXEC CICS SIGNAL/HANDLE CONDITION`, `CALL 'MQPUT'/'MQGET'` — signal handlers and MQ pub/sub bindings |
| `dependency_injection` | `None` — see §4 |
| `macros` | `DEFINE` directive lines / `>>DEFINE` — COBOL's compiler-directive preprocessor hooks |
| `pointers` | `POINTER PROCEDURE-POINTER FUNCTION-POINTER`, `ADDRESS OF` |
| `memory_alloc` | `ALLOCATE FREE`, `EXEC CICS GETMAIN/FREEMAIN` — heap and CICS-managed allocation |
| `inline_asm` | `None` — see §4 |

**Resource management & stability**
| Key | What it captures for COBOL |
|---|---|
| `telemetry` | `EXEC CICS WRITEQ TD`, `CEE3DMP CEEMOUT CEEDUMP` — CICS transient-data queues and Language Environment diagnostics |
| `debug_prints` | `DISPLAY` |
| `explicit_casts` | `REDEFINES` — memory reinterpretation, COBOL's closest analogue to a type cast |
| `panics_and_aborts` | `STOP RUN EXIT PROGRAM GOBACK` |
| `thread_sleeps` | `EXEC CICS DELAY` |
| `bitwise_ops` | `FUNCTION BIT-AND/BIT-OR/BIT-XOR/BIT-NOT` — modern intrinsic bitwise functions |
| `sync_locks` | `EXEC CICS ENQ` |
| `immutability_locks` | `CONSTANT` |
| `cleanup` | `CLOSE FREE END-DECLARATIVES` |
| `encapsulation` | `LOCAL-STORAGE SECTION`, `PRIVATE` |
| `listeners` | `MQGET`, `EXEC CICS RECEIVE` |
| `test_skip` | `IGNORE` |

**Hybrid domain sensors (COBOL specifics)**
| Key | What it captures for COBOL |
|---|---|
| `serialization_parsing` | `UNSTRING STRING`, `JSON PARSE/GENERATE`, `XML PARSE/GENERATE` |
| `regex_execution` | `INSPECT TALLYING REPLACING` — COBOL has no true regex engine; this is its nearest hardware-level string-manipulation equivalent |
| `time_date_logic` | `ACCEPT identifier FROM DATE/TIME/DAY`, `CURRENT-DATE`/`WHEN-COMPILED`. A severe ReDoS (`\s+.*\s+FROM`, confirmed 9+ seconds at just n=2000 — far worse than this epic's typical ~4x-per-doubling shape) was fixed by replacing the unbounded `.*` between two `\s+` quantifiers with a real identifier character class |
| `ipc_rpc_bridges` | `CALL '...'` (quoted or bare program name), `EXEC CICS LINK/XCTL/START/RETURN`, `EXEC SQL` |

**Intentional double-classifications.** Several constructs deliberately fire two signatures
representing different perspectives on the same action, asserted together in
`test_cobol_intentional_double_classification_sweep`: `AUTHOR.` → `doc` + `ownership`;
`REDEFINES` → `explicit_casts` + `reflection_metaprogramming`; `EXEC CICS DELAY` →
`concurrency` + `thread_sleeps`; `EXEC CICS ENQ` → `concurrency` + `sync_locks`;
`CALL 'MQGET'` → `events` + `listeners`; `FREE` → `cleanup` + `memory_alloc`;
`STOP RUN`/`GOBACK` → `high_risk_execution` + `panics_and_aborts` + `structural_boundaries`;
`STRING ... INTO ...` → `serialization_parsing` + `state_mutation`; and any `EXEC CICS`/`EXEC SQL`
statement also fires `reflection_metaprogramming`'s own bare catch-all alternative, layered on top
of whichever CICS/SQL-specific signature it also matches (`io`, `concurrency`, `telemetry`, etc.).

## 4. What GitGalaxy explicitly does not track

Four keys are hard-set to `None` in COBOL's `rules` dict (Rule 4 of the engine's generation rules:
explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`closures`** — "Closures / Anonymous Functions. (COBOL lacks native lambdas.)"
- **`comprehensions`** — "Iterators / Comprehensions. (Not native to COBOL.)"
- **`dependency_injection`** — "Inversion of Control." (no further inline reason given; COBOL has
  no DI-framework convention the way `struct *_ops` vtables give C a real, if informal, one)
- **`inline_asm`** — "Bare Metal." (no further inline reason given; COBOL has no inline-assembly
  syntax in any dialect this engine targets)

## 5. Known limitations (accepted, not fixed)

One gap is deliberately documented (rather than fixed) via a `known_limitation`-named test in
`test_cobol.py`:

1. **`func_start` cannot distinguish a multi-line `PERFORM` invocation from a genuine new
   paragraph declaration.** A statement like `PERFORM\n    TargetFunc.` (invoking an *existing*
   paragraph, split across two lines purely for readability — common real COBOL style) is
   structurally indistinguishable from `TargetFunc.` appearing as its own new paragraph header,
   because the rule has no cross-line statement-context tracking — it can't know the previous
   physical line ended with `PERFORM` rather than a real statement terminator. Fixing this would
   require real statement-boundary tracking this regex-only engine doesn't have; documented as a
   known, architecturally-not-fixed limitation
   (`test_cobol_func_start_known_limitation_multiline_perform_target_still_matches`), not
   attempted.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 62 tests in
  `tests/extraction/languages/test_cobol.py` — valid/invalid/pathological cases per rule, plus
  the known-limitation test above and several regression tests for bugs found during hardening
  (segment-number handling, trailing-clause parsing, `USING`/`RETURNING` bleed). Fully migrated
  to the per-language file (epic #813, issue #854) — nothing left for `cobol` in the old
  monolithic gauntlet files. Per the file's own header comment, `args` and `class_start` had
  **zero** prior test coverage at all before this migration (the two old monolithic dict files
  that did have a cobol entry — `test_function_extraction_strict.py`,
  `test_dependency_extraction_strict.py` — covered only `func_start` and `_dependency_capture`).
- **Strict signature suite** (all other wired keys): 82 tests in
  `tests/extraction/languages/test_cobol_strict.py`. Two layers: the original full per-signature
  suite from epic #518/issue #776 (positive/negative coverage for every wired key, the
  ghost-satellite/SQL-column/data-division false-positive regression, the `import`
  schema-completeness regression, the `MQPUT`/`CALL` word-boundary regressions, the severe
  `time_date_logic` ReDoS regression, the `explicit_casts`-vs-`pointers` no-false-collision test,
  and the intentional-double-classification sweep described in §3); plus ~30 "deep adversarial"
  parametrized cases added later by the cross-language strict-hardening epic (#1069/#1071, PR
  #1087) covering multiline/comma-separated `args`, line-wrapped multi-word `branch` keywords,
  and margin/reserved-word edge cases for `func_start`/`class_start`/`structural_boundaries`.

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#776](https://github.com/squid-protocol/gitgalaxy/issues/776) (CLOSED, merged
  [#783](https://github.com/squid-protocol/gitgalaxy/pull/783)) — Strict parsing tests for COBOL
  structural signatures (epic #518). Established the first full per-signature test suite; COBOL
  previously had only one isolated regression test
  (`test_cobol_ghost_satellite_prevention`, false-positive prevention against SQL columns and
  data-division structs).
- [#854](https://github.com/squid-protocol/gitgalaxy/issues/854) (CLOSED, merged
  [#925](https://github.com/squid-protocol/gitgalaxy/pull/925)) — Extraction hardening for COBOL
  (epic #813): the `func_start`/`args`/`class_start` bug fixes and the `_dependency_capture`
  extraction-gauntlet migration described throughout §3/§6.
- [#1071](https://github.com/squid-protocol/gitgalaxy/issues/1071) (epic #1069, merged
  [#1087](https://github.com/squid-protocol/gitgalaxy/pull/1087)) — cross-language deep
  adversarial strict-signature coverage pass; added the ~30 extra parametrized cases noted in §6.

**Real bugs found and fixed (COBOL-specific, epic #813/#854 unless noted):**
- **`args` `USING`/`RETURNING` bleed-through.** The parameter-name repetition had no exclusion
  for the literal word `RETURNING`, so `PROCEDURE DIVISION USING WS-A RETURNING WS-B.` (declaring
  a parameter and a return value in one division header — extremely common real Enterprise
  COBOL/GnuCOBOL) had `USING`'s own capture bleed straight through `RETURNING` and swallow `WS-B`
  too. Fixed with a negative lookahead so `finditer` correctly yields two separate matches.
- **`func_start` `SECTION` segment-number gap.** `SECTION` had no allowance for a trailing
  segment number (`MAIN-PARA SECTION 10.`), a real COBOL-68/74-era program-segmentation feature
  still accepted by modern compilers for legacy support — any segmented section header was
  entirely invisible. Fixed with an optional 1-2-digit segment number after `SECTION`.
- **`class_start` trailing-clause gap, plus a false positive it reopened.** The lookahead
  required the entity name to be immediately followed by a period/newline/EOS, with no allowance
  for standard trailing clauses (`PROGRAM-ID. Foo IS INITIAL PROGRAM.`, `CLASS-ID. Foo FINAL.`,
  `CLASS-ID. Foo INHERITS Base.`, etc.) — all real, documented Enterprise COBOL syntax were
  entirely invisible. Fixed with a bounded (max 6) trailing-clause word loop. That widening itself
  reopened a *different* false-positive vector, caught before shipping: `FACTORY.`/`OBJECT.` are
  bare OO-COBOL structural markers always immediately followed by a division header
  (`FACTORY.\n    IDENTIFICATION DIVISION.`), and the widened loop started miscapturing
  `IDENTIFICATION`/`PROCEDURE` as the entity name with `DIVISION` swallowed as a trailing clause
  word — fixed by excluding `DIVISION` from the trailing-clause loop specifically.
- **`import` key completeness gap** (Strict Feature Parity, Rule 4) — the `import` key was
  missing from the `rules` dict entirely (not even an explicit `None`), despite COBOL clearly
  having a real dependency-inclusion mechanism (`COPY`/`INCLUDE`) that `_dependency_capture`
  already extracted correctly. Added as a real, wired key.
- **`events` quoted-`CALL` word-boundary bug.** The `CALL 'MQPUT'`/`CALL 'MQGET'` alternative
  shared a trailing `\b` with a word-ending sibling alternative, but ends in a literal `'`
  (non-word) — `\b` right after can only fire if the next character is a word character, which is
  never true for the realistic form (`CALL 'MQPUT' USING queue-name.`, whitespace then a quote).
  Pulled into its own group.
- **`ipc_rpc_bridges` `CALL` whitespace-boundary bug** — same root shape as the `events` bug
  above: `CALL\s+` shared a trailing `\b` with word-ending siblings but ends in whitespace
  (non-word), breaking on the dominant realistic call form (`CALL 'SUBPROGRAM' USING ...`, a quote
  following the consumed whitespace); only the less-common unquoted data-name form
  (`CALL WS-PROGRAM-NAME`) happened to work before the fix.
- **`time_date_logic` severe ReDoS.** `\s+.*\s+FROM` has three adjacent quantifiers whose
  character sets overlap (`.` matches whitespace too), letting the engine partition the space
  between the receiving identifier and the two `\s+`s in exponentially many ways — confirmed 9+
  seconds at just n=2000. Fixed by replacing the unbounded `.*` with a real identifier character
  class.

**Reopened during this doc's research (not resolved despite being closed):**
- [#259](https://github.com/squid-protocol/gitgalaxy/issues/259) — "Fixed-form COBOL/Fortran
  comment stripping doesn't shield string literals." Originally closed with a comment claiming
  "resolved by #273," but #273 only ever touched `network_risk_sensor.py`
  (an unrelated file-deduplication fix) and never touched `prism.py`. Direct verification against
  current `main`'s `Prism._strip_positional_comments` (the function backing COBOL's
  `positional_anchored` family) confirms the originally-reported bug is still live: unlike every
  other stripping path in `prism.py`, it splits directly on `*>`/`!` with no
  `LITERAL_MASK_PATTERN` shielding beforehand, so a COBOL string literal containing either
  character (e.g. `DISPLAY "Rate *> 5%" TO CONSOLE.`) gets truncated mid-literal — the text after
  the in-string delimiter silently disappears from the code stream as if it were a comment. This
  sits upstream of every rule described in §3 (it corrupts the `code_stream` those regexes run
  against), has no regression test guarding it, and was reopened with a fresh repro rather than
  fixed inline as part of writing this doc — see the issue for the full reproduction and analysis.
  This is a `prism.py`-level gap, not a `language_standards.py` regex defect, and equally affects
  `fortran` (the other `positional_anchored`-family language sharing this same function).

Search performed via `gh issue list --search 'in:title "Extraction hardening: cobol"'` /
`'in:title "Strict parsing tests: \`cobol\`"'` / `'in:title cobol'` (2026-08-19). Two other
`cobol`-title hits were excluded as unrelated to the structural-signature engine: #501 (a Ruff
lint fix inside `cobol_to_java` string literals, a `gitgalaxy/tools/` migration-tool file) and
#292 (a DB-connection/missing-return bug in `cobol_refractor_controller.py`, also a `tools/`
migration utility, not `language_standards.py`/`prism.py`/`detector.py`).

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Four repos from the `v2.4.7` batch, chosen for a size/era spread — a huge adversarial IDE-tooling
test corpus, a mid-size practice-program collection, a small foundation-backed teaching course,
and a tiny reference-sample set:

- **[`che-che4z-lsp-for-cobol`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/che-che4z-lsp-for-cobol/che-che4z-lsp-for-cobol_galaxy_llm.md)**
  — Eclipse/Broadcom's COBOL Language Server Protocol implementation
  (`eclipse/che-che4z-lsp-for-cobol.git`). The largest and most adversarial COBOL data point
  available: 678,343 total LOC, COBOL the dominant language, and — being an LSP's own parser
  test/fixture corpus — heavy on exactly the deliberately-edge-case COBOL syntax `func_start`'s
  "Iron Wall" negative-lookahead shield exists for. Scanned in 21.64s, the slowest of the four.
- **[`Cobol-Projects`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/Cobol-Projects/Cobol-Projects_galaxy_llm.md)**
  — a curated collection of small COBOL practice/coursework programs
  (`dscobol/Cobol-Projects.git`), 29,282 LOC, COBOL-dominant. A useful mid-size, many-small-files
  contrast to the LSP corpus's single-large-adversarial-project shape. Scanned in 0.76s.
- **[`cobol-programming-course`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/cobol-programming-course/cobol-programming-course_galaxy_llm.md)**
  — the Open Mainframe Project's official COBOL training course
  (`openmainframeproject/cobol-programming-course.git`), 4,080 LOC. Small and foundation-backed;
  its dominant-language reading of JCL over COBOL is itself a real, on-brand data point — this is
  exactly the COBOL/JCL pairing GitGalaxy's `discriminators` list (`.jcl`) exists to disambiguate.
  Scanned in 0.65s.
- **[`cobol-samples`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/cobol-samples/cobol-samples_galaxy_llm.md)**
  — neopragma's small reference/tutorial COBOL sample set (`neopragma/cobol-samples.git`), 1,522
  LOC, COBOL-dominant. The smallest, cleanest data point of the four — a useful low-noise
  contrast against the LSP corpus's adversarial extreme. Scanned in 0.13s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

Note: `awesome-cobol` (a curated links-list repo, 0 LOC scanned, dominant language Markdown) and
`COBOL-Guide` (0 LOC scanned) were checked and excluded — neither contains real COBOL source, just
Markdown link lists, despite the repo name.
## 9. Tri-comparison: GitGalaxy vs. ctags (no privileged ground truth)

COBOL is one of 9 languages with no tree-sitter grammar in GitGalaxy's comparison tooling, so
this is a 2-way comparison against universal-ctags, not the usual 3-way GitGalaxy/tree-sitter/
ctags split. See `docs/self_scan/how_to_investigate_a_discrepancy.md` for the methodology and
`docs/self_scan/tri_comparison_ledger.json` (filter to `cobol/`) for the full record.

**Summary.** All 3 discrepancy shapes the tri-comparison tool ever flagged for cobol have been
investigated and validated (2026-08-19, via the `tri-comparison-ledger-sweep` skill). 170 total
occurrences covered. 3 confirmed GitGalaxy/audit-tool defects found and filed
([#1890](https://github.com/squid-protocol/gitgalaxy/issues/1890),
[#1891](https://github.com/squid-protocol/gitgalaxy/issues/1891),
[#1892](https://github.com/squid-protocol/gitgalaxy/issues/1892)), plus one existing issue
([#1858](https://github.com/squid-protocol/gitgalaxy/issues/1858)) had its root-cause diagnosis
corrected. Notably, every one of the 3 shapes turned out to be **mixed-cause** — a real defect
hiding underneath a larger, unrelated pattern in the same shape — which is why the sweep read
every sampled case individually rather than trusting the majority pattern to explain the whole
count.

### Where the disagreement was ctags/harness noise, not a GitGalaxy problem

- **`function/existence`, ctags-alone, 133 occurrences** (shape
  `cobol/function/existence/agree[ctags]_vs[gitgalaxy]`): the majority is Universal Ctags' own
  COBOL parser tagging *any* period-terminated word as a "paragraph," including scope terminators
  like `END-IF.`/`END-PERFORM.` that are not paragraph definitions — confirmed via a live `ctags
  -x` run on `cics-banking-sample-application-cbsa/BANKDATA.cbl` showing dozens of plain
  `END-IF.` lines tagged as paragraphs. GitGalaxy correctly excludes these via its own
  `END-[A-Za-z0-9_-]+` reserved-word shield. Permanent, structural ctags limitation, documented in
  `tests/tools/ctags_reader.py`'s cobol kind-map comment.
- **`function/existence`, GitGalaxy-alone, 18 occurrences** (shape
  `cobol/function/existence/agree[gitgalaxy]_vs[ctags]`): the `MAINLINE`/`TIMESTAMP`-style
  majority is real COBOL `SECTION` headers that both GitGalaxy and ctags correctly identify —
  ctags tags them as kind `section` (`s`), not `paragraph` (`p`), and `ctags_reader.py`'s
  `CTAGS_FUNC_KINDS["cobol"]` only read `{"p"}`, silently dropping ctags' own correct reading
  before comparison. This was a test-harness bug, not a real disagreement — filed as
  [#1891](https://github.com/squid-protocol/gitgalaxy/issues/1891).

### Where GitGalaxy has a real, confirmed defect

- **`func_start`'s `LOCAL-STORAGE` false positive** (part of the 18-occurrence shape above): the
  `func_start` regex's reserved-word negative lookahead bans `WORKING-STORAGE` and `LINKAGE` as
  Data Division section headers but omits `LOCAL-STORAGE` — so `LOCAL-STORAGE SECTION.` (a pure
  data-item header, no executable logic, confirmed at
  `cics-banking-sample-application-cbsa/XFRFUN.cbl:107`) gets miscounted as a paragraph. Filed as
  [#1890](https://github.com/squid-protocol/gitgalaxy/issues/1890).
- **`func_start`'s hyphen/word-boundary false negatives** (~20 of the 133-occurrence shape above):
  the reserved-word negative lookahead ends in a bare `\b`, and since `-` is a non-word character
  in Python `re`, any real paragraph name that *starts with* a banned keyword followed by a hyphen
  — a common COBOL verb-prefixed naming convention (`WRITE-*`, `READ-*`, `SET-*`, `DELETE-*`, ...)
  — is wrongly excluded. Verified directly against the compiled regex: `DELETE-POLICY-DB2-INFO.`
  (a real, `PERFORM`'d paragraph at `cics-genapp/lgdpol01.cbl:139`) and `WRITE-ERROR-MESSAGE.`
  (`cics-genapp/lgapol01.cbl:137`) both fail to match. A corpus-wide grep found ~20 real paragraphs
  affected. Filed as [#1892](https://github.com/squid-protocol/gitgalaxy/issues/1892).
- **`class_start` named-extraction gap, 19/19 occurrences** (shape
  `cobol/class/existence/agree[ctags]_vs[gitgalaxy]`): GitGalaxy's own cobol `class_start` regex
  already matches `PROGRAM-ID` correctly and identically to ctags (verified directly:
  `PROGRAM-ID. BANKDATA.` at `cics-banking-sample-application-cbsa/BANKDATA.cbl:35` matches,
  capturing `BANKDATA`) — but the match never reaches named-entity output because
  `gitgalaxy/core/detector.py`'s `_CLASS_START_NAMED_EXTRACTION_LANGS` allowlist (built by epic
  [#1295](https://github.com/squid-protocol/gitgalaxy/issues/1295), closed 2026-08-12, 11/13
  languages) never included cobol — not decided out like css/html, simply never in scope, since
  that epic's own verification method requires a tree-sitter grammar cobol doesn't have. Every
  language missing from the allowlist falls through to a hardcoded
  `class|struct|interface|trait|enum` fallback regex that cannot match COBOL syntax at all. This
  corrects issue [#1858](https://github.com/squid-protocol/gitgalaxy/issues/1858)'s original
  diagnosis (which claimed the regex itself never matches — it does; the gap is one step
  downstream). A quick sibling check found cobol is the only one of the 9 tree-sitter-blind
  languages missing from that same allowlist with *live, ctags-corroborated* evidence of the bug —
  `assembly`/`scheme` have no comparable ctags class-kind mapping to expose it (or the corpus
  simply has no real matches either way), and `ada`/`sqlite`/`embedded_python` have no
  `language-crucible` corpus at all; `dockerfile`/`abap`/`jcl`/`livecode`/`yaml` have corpora but
  zero real functions/classes found by any tool regardless of the allowlist gap.

### Audit-tool bugs found and fixed along the way

Both confirmed test-harness gaps (`ctags_reader.py`'s missing `s` kind, and the pre-existing wrong
diagnosis in #1858) were corrected as part of this sweep rather than left as silent noise — see
[#1891](https://github.com/squid-protocol/gitgalaxy/issues/1891) and the corrective comment on
[#1858](https://github.com/squid-protocol/gitgalaxy/issues/1858).

Full record: `docs/self_scan/tri_comparison_ledger.json` (filter keys starting `cobol/`),
rendered summary in `docs/self_scan/tri_comparison_points_of_interest.md`.
