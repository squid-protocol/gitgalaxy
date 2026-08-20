# ABAP — Structural Signature Coverage

Snapshot generated 2026-08-19 against `main`. Source: `LANGUAGE_DEFINITIONS["abap"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_abap.py` /
`test_abap_strict.py`, and closed GitHub issues. Re-run the `language-status` skill's
data-gathering commands before trusting these numbers if this doc looks old relative to
`last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | ABAP 2025 (ABAP Cloud / RAP / Modern 7.5x+ Syntax) |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `positional_abap` — a dedicated positional family (mapped in the source to "Family 7, The Positional Ancients"): the engine must watch column 1 for a leading `*` to identify a line-level comment, while still recognizing `"` as ABAP's inline comment marker |
| Structural signature keys wired | 46 / 48 (2 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_abap.py`) | 42 |
| Strict-signature tests (`test_abap_strict.py`) | 87 |
| Total dedicated ABAP test cases | 129 |
| Measured real-world accuracy vs. an independent ground-truth parser | Not applicable — see §9 |

ABAP has neither a tree-sitter grammar nor a ctags parser, so there is no automatable §9 the way
`c.md`/other tree-sitter-baselined languages get one. §9 below is a manual, by-hand verification
pass instead, using `tri-comparison-ledger-sweep`'s dedicated fallback procedure for languages with
no comparison tool at all.

## 2. Identification surface

- **Extensions:** `.abap`, `.asddls` — standard ABAP sources and modern Core Data Services
  definitions.
- **Exact filenames:** none — ABAP runs inside the SAP NetWeaver/ABAP platform, so there are no
  extensionless exact-match configuration files the way other ecosystems have (`Makefile`,
  `Dockerfile`, etc.).
- **Discriminators:** `.abap`, `package.devc.xml`, `.apc` — SAP deployment-artifact anchors used
  to disambiguate.
- **Shebangs:** none — ABAP is never invoked as a standalone interpreted script.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` and `how_to_add_a_language.md` use.
Description is what ABAP's *actual* regex matches, not the generic cross-language definition.
Several rules carry inline "BUG FIX" comments in the source documenting a specific correctness
fix baked directly into the current pattern — called out below where present, since they're real
evidence of hardening even though a standalone issue number for each couldn't be traced (see §7's
note on squashed git history).

**Topology & structure**
| Key | What it captures for ABAP |
|---|---|
| `branch` | Line-anchored `IF ELSE ELSEIF CASE WHEN WHILE DO LOOP AT TRY CATCH CLEANUP CHECK EXIT CONTINUE RETURN`, plus modern `COND`/`SWITCH` expressions |
| `args` | `IMPORTING EXPORTING CHANGING RETURNING RECEIVING EXCEPTIONS` parameter-binding keywords, with a negative lookahead excluding a following `TYPE` and optional support for the `VALUE(...)` by-value binding syntax |
| `structural_boundaries` | Line-anchored `DATA TYPES FIELD-SYMBOLS CLASS INTERFACE METHOD FORM FUNCTION MODULE REPORT PROGRAM IMPORT EXPORT`, excluding access-modifier/paren-adjacent forms |
| `func_start` | Anchors `METHOD FORM FUNCTION MODULE` declarations and captures the identifier; explicitly excludes `CLASS INTERFACE DATA TYPES CONSTANTS` headers so they aren't miscounted as executable-logic entry points |
| `class_start` | `CLASS`/`INTERFACE` declarations, plus modern RAP CDS entity declarations (`DEFINE [ROOT] VIEW [ENTITY]` / `PROJECTION VIEW [ENTITY]` / `[ABSTRACT\|CUSTOM] ENTITY` / `BEHAVIOR FOR`). **Inline bug-fix note:** `VIEW` and `ENTITY` used to be mutually-exclusive alternatives, so the standard modern syntax `DEFINE VIEW ENTITY <name>` matched `VIEW` as the keyword and then captured the literal word `ENTITY` as if it were the entity name; `ENTITY` is now optional after `VIEW`/`PROJECTION VIEW` instead of a same-tier alternative |

**Safety & risk**
| Key | What it captures for ABAP |
|---|---|
| `safety` | `TRY CATCH CLEANUP ASSERT AUTHORITY-CHECK IS BOUND IS ASSIGNED IS NOT INITIAL FINAL READ-ONLY` |
| `safety_bypasses` | `UNASSIGNED`, `TYPE ANY`, `TYPE REF TO DATA`, `IGNORE ERRORS`, and dynamic `ASSIGN ... TO <fs> CASTING` |
| `high_risk_execution` | `SYSTEM-CALL`, `EXEC SQL`, `DELETE FROM`, `TRUNCATE`, `GENERATE SUBROUTINE POOL` |
| `io` | Line-anchored `SELECT`, `INSERT [INTO]`, `UPDATE`, `MODIFY`, `OPEN DATASET`, `TRANSFER`, `READ DATASET`, `CLOSE DATASET`, `CL_HTTP_CLIENT`, `CL_WEB_HTTP_CLIENT` |
| `api` | `REMOTE FUNCTION`, `DEFINE VIEW`, `DEFINE SERVICE`, `EXPOSED`, `PUBLIC SECTION`, plus the `@OData.publish` annotation. **Inline bug-fix note:** the `@`-prefixed annotation form previously never matched — a shared leading `\b` required a preceding word character, never true for how `@OData.publish` is actually written |
| `state_mutation` | Line-anchored `MOVE`, `MOVE-CORRESPONDING`, `APPEND`, `MODIFY TABLE`, `DELETE TABLE`, plus `INSERT ... INTO TABLE` |
| `dead_code` | Commented-out `DATA METHOD IF SELECT WRITE` lines, supporting both `*`-prefixed line comments and `"` inline comments |
| `doc` | ABAP Doc annotations (`"! @parameter/@raising/@return`) and `AUTHOR:/DESCRIPTION:/PURPOSE:/REMARKS:` headers. **Inline bug-fix note:** a trailing `\b` sitting right after the literal `:` never fired for realistic `AUTHOR: Jane Doe`-style headers, since the space after `:` puts non-word characters on both sides of that boundary position; dropped since `:` is already self-delimiting |
| `test` | `FOR TESTING`, `RISK LEVEL`, `DURATION SHORT`, `CL_ABAP_UNIT_ASSERT`, `ZCL_ABAP_UNIT` |

**Architecture & domain sensors**
| Key | What it captures for ABAP |
|---|---|
| `concurrency` | `STARTING NEW TASK`, `WAIT UP TO`, `ENQUEUE_`/`DEQUEUE_` prefixes, `CALL FUNCTION ... IN BACKGROUND TASK`. **Inline bug-fix note:** `ENQUEUE_`/`DEQUEUE_` end in `_` (a word character), and real function-module names always continue with more word characters right after (`ENQUEUE_FOO`), so a shared trailing `\b` could never fire; pulled into its own alternative with the trailing `\b` dropped |
| `ui_framework` | `CALL SCREEN`, `SELECTION-SCREEN`, `PARAMETERS`, `WDDOMODIFYVIEW`, `CL_GUI_HTML_VIEWER`, `CL_SALV_TABLE` |
| `closures` | `None` — ABAP has no anonymous-closure construct (see §4) |
| `globals` | `TABLES`, `STATICS`, `CLASS-DATA`, `SY-*` system-field references |
| `decorators` | Any `@`-prefixed annotation, with an optional parenthesized argument list |
| `generics` | `TYPE ANY [TABLE]`, `TYPE INDEX TABLE`, `TYPE STANDARD TABLE`, `TYPE REF TO DATA` |
| `comprehensions` | Modern constructor expressions `VALUE/REDUCE/FILTER/CORRESPONDING/NEW #( ... )` and `FOR ... IN` iteration expressions |
| `scientific` | `ABS SQRT LOG EXP SIN COS TAN ROUND CEIL FLOOR DECFLOAT16 DECFLOAT34` |
| `reflection_metaprogramming` | `CL_ABAP_TYPEDESCR`, `CL_ABAP_CLASSDESCR`, dynamic `ASSIGN (name) TO`, `GENERATE SUBROUTINE POOL` |
| `import` | `INCLUDE`, `TYPE-POOLS` |
| `_dependency_capture` | Extracts the include-program/type-pool name following a line-anchored `INCLUDE`/`TYPE-POOLS` |
| `ownership` | `AUTHOR:/CREATED BY:/MAINTAINER:` headers (the alternation also includes a literal `Tim Berners-Lee:` string — a shared cross-language pattern quirk, not ABAP-specific) |

**Specialized subsystems**
| Key | What it captures for ABAP |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`/`[spec ...]`/`[audit ...]` traceability tags, plus a literal `WorldWideWeb RFC W3C CERN TBL ENQUIRE` alternation (a shared cross-language pattern, not ABAP-specific) |
| `ssr_boundaries` | `IF_HTTP_EXTENSION~HANDLE_REQUEST`, `CL_BSP_CONTEXT`, `CL_BSP_RUNTIME`, `IF_HTTP_REQUEST`, `IF_HTTP_RESPONSE`, `HTML_STRING` |
| `events` | `RAISE EVENT`, `SET HANDLER`, `FOR EVENT ... OF` |
| `dependency_injection` | `GET BADI`, `CALL BADI`, `CL_BADI_BASE`, `CL_ABAP_TESTDOUBLE` |
| `macros` | Line-anchored `DEFINE <name>.` / `END-OF-DEFINITION.` |
| `pointers` | Field-symbol angle-bracket references `<fs>`, `->*`, `GET REFERENCE OF`, `REF TO` |
| `memory_alloc` | `CREATE OBJECT`, `CREATE DATA`, `FREE`, `CLEAR` |
| `inline_asm` | `None` — no bare-metal/inline-assembly construct (see §4) |

**Resource management & stability**
| Key | What it captures for ABAP |
|---|---|
| `telemetry` | `BAL_LOG_CREATE`, `BAL_DB_SAVE`, `CL_BALI_LOG`, `CL_BALI_MSG_SETTER` |
| `debug_prints` | Line-anchored `WRITE` statements |
| `explicit_casts` | `CAST`/`CONV #( ... )` constructor casts, `ASSIGNING <fs> CASTING` |
| `panics_and_aborts` | `RAISE EXCEPTION`, `MESSAGE ... TYPE 'E'/'X'`, `LEAVE PROGRAM` |
| `thread_sleeps` | `WAIT UP TO` |
| `bitwise_ops` | `BIT-AND`, `BIT-OR`, `BIT-XOR`, `BIT-NOT` |
| `sync_locks` | `ENQUEUE_`/`DEQUEUE_` prefixes (same trailing-`\b` mirror-case fix as `concurrency` above) |
| `immutability_locks` | `CONSTANTS`, `FINAL`, `READ-ONLY` |
| `cleanup` | Line-anchored `FREE`, `CLEAR`, `CLOSE DATASET` |
| `encapsulation` | `PRIVATE SECTION`, `PROTECTED SECTION` |
| `listeners` | `FOR EVENT ... OF` |
| `test_skip` | `IGNORE` |

Note: ABAP's `rules` dict has 48 total keys, not the 64 seen in some newer language entries
(e.g. `python.md` §3's "advanced algorithmic / hybrid domain / AppSec sensors" tier —
`lazy_evaluation`, `vectorized_math`, `serialization_parsing`, `regex_execution`,
`time_date_logic`, `ipc_rpc_bridges`, `memory_scraping`, `exfiltration_camouflage` — and the
`llm_api`/`ml_*`/`dl_frameworks` AI-SDK sensors) — those keys simply don't exist in ABAP's
schema shape rather than being present-but-`None`.

## 4. What GitGalaxy explicitly does not track

Two keys are hard-set to `None` in ABAP's `rules` dict (Rule 4 of the engine's generation rules:
explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`closures`** — ABAP has no anonymous closures / lambda construct.
- **`inline_asm`** — no bare-metal / inline-assembly construct.

## 5. Known limitations (accepted, not fixed)

No `known_limitation`-named tests exist in `test_abap.py` or `test_abap_strict.py` as of this
snapshot — grepped both files for the marker and found none. This reads as "nothing documented as
a deliberately-accepted gap," not as a claim that ABAP extraction is flawless; see §7 for the one
real pipeline-level bug (#746) found and fixed for this language, and §9 for a manual verification
pass against real corpus source.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 42 tests in
  `tests/extraction/languages/test_abap.py` — valid/invalid/pathological cases per rule. Fully
  migrated to the per-language file (epic #813, issue #853) — nothing left in the old monolithic
  gauntlet files for ABAP (confirmed via grep). Note: PR #1001 explicitly removed several
  pathological multiline test cases that relied on `\n` injections across logic anchors, because
  the engine processes ABAP strictly line-by-line (`re.M`) and those cases were mathematically
  impossible to trigger under that constraint — not a coverage gap, a corrected test suite.
- **Strict signature suite** (all other wired keys): 87 tests in
  `tests/extraction/languages/test_abap_strict.py` — positive match, negative/false-positive
  match, cross-rule ambiguity, ReDoS-immunity sweep, and family-specific checks (e.g. a dedicated
  `test_abap_lexical_family_no_block_terminator_state_to_confuse` test for the `positional_abap`
  family, and a `func_start`-vs-`generics` collision check) per signature. Originated from epic
  #518 (issue #571), later deepened further by the cross-language #1074 pass (epic #1069, PR
  #1087) alongside every other supported language.

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#571](https://github.com/squid-protocol/gitgalaxy/issues/571) (PR
  [#750](https://github.com/squid-protocol/gitgalaxy/pull/750)) — Strict parsing tests for ABAP
  structural signatures (epic #518).
- [#853](https://github.com/squid-protocol/gitgalaxy/issues/853) (PR
  [#1001](https://github.com/squid-protocol/gitgalaxy/pull/1001)) — Extraction hardening for ABAP
  (epic #813): migrated ABAP's monolithic gauntlet cases to the dedicated per-language file,
  removed pathological multiline test cases that were impossible under the engine's strict
  line-by-line (`re.M`) execution model.
- Epic #1069's cross-language strict-suite deepening pass (issue #1074, PR
  [#1087](https://github.com/squid-protocol/gitgalaxy/pull/1087)) included ABAP in one of its
  seven language batches, adding deeper multi-case adversarial matrices on top of the #571
  baseline.

**Real bug found and fixed, specific to ABAP:**
- [#746](https://github.com/squid-protocol/gitgalaxy/issues/746) (PR
  [#756](https://github.com/squid-protocol/gitgalaxy/pull/756)) — ABAP's `"` inline comment
  marker was invisible to `prism.py`'s `positional_anchored`-family stripper, meaning code
  following an inline `"` comment on the same line could be misread as live code. This was a
  pipeline (`prism.py`) fix, not a `language_standards.py` regex fix.

**Note on inline bug-fix comments without a traceable issue number:** several of the regexes in
§3 above (`class_start`'s VIEW/ENTITY collision, `api`'s `@OData.publish` leading-`\b` fix,
`doc`'s `AUTHOR:` trailing-`\b` fix, `concurrency`/`sync_locks`'s `ENQUEUE_`/`DEQUEUE_`
trailing-`\b` fix) carry explanatory "BUG FIX" comments directly in the source but couldn't be
tied to a standalone GitHub issue via title search — `git log`/`git blame` on
`language_standards.py` bottoms out at a single large repo-restructuring commit
(`fb24cd6a`, "spoke & hub") that appears to have replaced the file's prior history, so earlier
per-fix commits aren't reachable. Most likely these were folded into the #853 or #1074 batch work
above without a dedicated issue of their own; noted here as real, evidenced hardening regardless
of the missing paper trail.

Search performed via `gh issue list --search 'in:title "Extraction hardening: abap"'` /
`'in:title "Strict parsing tests: `abap`"'` / `'in:title abap'` (2026-08-19).

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Three repos from the `v2.4.7` batch — every ABAP-primary or ABAP-related project present in that
corpus, chosen for a size/shape spread:

- **[`abapGit`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/abapGit/abapGit_galaxy_llm.md)** — the largest of the three: 1,508 artifacts, 142,141 total LOC, dominant language ABAP. abapGit is itself a widely-used ABAP version-control tool, so this is real production ABAP at scale.
- **[`abap2xlsx`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/abap2xlsx/abap2xlsx_galaxy_llm.md)** — a mid-size, dominant-ABAP library (407 artifacts, 32,529 LOC) for generating Excel files from ABAP; a lower-noise baseline compared to abapGit.
- **[`abap-cleaner`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/abap-cleaner/abap-cleaner_galaxy_llm.md)** — the adversarial/polyglot case: 731 artifacts, 103,796 LOC, but its *dominant* detected language is JAVA, not ABAP (it's an ABAP source-formatting tool implemented in Java that ships ABAP fixtures/test data alongside its own Java codebase) — useful evidence that ABAP identification stays correct even as a minority language inside a mixed-language repo.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

## 9. Manual verification: GitGalaxy alone (no tree-sitter or ctags for ABAP)

ABAP is one of only 5 languages in the whole registry with **neither** a tree-sitter grammar nor a
ctags parser (the others: `dockerfile`, `jcl`, `livecode`, `yaml` — confirmed against
`tests/tools/ctags_reader.py`'s own LANGUAGE COVERAGE docstring, 2026-08-19). The normal
`tri-comparison-ledger-sweep` methodology (§9 in `c.md`/other languages) needs at least two tools
disagreeing to produce a ledger shape worth investigating — for ABAP there is no second tool, so
`docs/self_scan/tri_comparison_ledger.json` has zero ABAP entries and always will under the current
tool set. This section is a manual by-hand substitute: GitGalaxy's regex output checked directly
against hand-read source, using the `tri-comparison-ledger-sweep` skill's dedicated fallback
procedure for exactly this situation.

**Corpus:** `language-crucible/data/abap/abapGit/` — 7 files, 4,006 lines, a local crucible subset
of the same `abapGit` project scanned at full scale in §8 (not the same snapshot or line count —
this is a small, hand-checkable slice, not the 142K-LOC production repo).

**Method:** ran ABAP's actual `func_start`/`class_start` regexes from `language_standards.py`
against every file, recorded every match with line number and captured text, then independently
re-derived ground truth by reading the source and cross-checking with a second, unrelated grep
(`grep -nE "^\s*METHOD\s+[a-zA-Z]"` per file) that does not share the primary regex's
implementation at all.

**`func_start` result — 100% precision and 100% recall on every real example in the corpus:**

| File | `func_start` matches | Independent `METHOD` grep count |
|---|---|---|
| `zabapgit.prog.abap` | 0 | 0 |
| `zcl_abapgit_ajson.clas.abap` | 47 | 47 |
| `zcl_abapgit_git_porcelain.clas.abap` | 19 | 19 |
| `zcl_abapgit_http_client.clas.abap` | 10 | 10 |
| `zcl_abapgit_objects.clas.abap` | 30 | 30 |
| `zcl_abapgit_persistence_db.clas.abap` | 13 | 13 |
| `zcl_abapgit_xml_output.clas.abap` | 5 | 5 |

All 124 matches are genuine `METHOD <name>.` implementations (including tilde-qualified interface
methods like `zif_abapgit_ajson~get_string`); zero false positives. `zabapgit.prog.abap` is a
driver program with no `METHOD`/`FORM`/`FUNCTION`/`MODULE` at all (only `PERFORM` calls into
`INCLUDE`d forms and event blocks like `START-OF-SELECTION`) — GitGalaxy correctly returns 0/0 for
it rather than false-matching on `PERFORM`. The regex also correctly excludes `METHODS <name>`
(plural) declarations in `DEFINITION` sections, since it requires whitespace immediately after the
literal `METHOD` and `METHODS` has no such whitespace before its trailing `S`.

**Coverage gap, not a bug:** none of the 7 corpus files contain a `FORM`, `FUNCTION`, or `MODULE`
definition, so `func_start`'s recall on those three keywords is untested by this corpus — stated
here rather than silently implied as verified.

**`class_start` — apparent double-count, ruled out as intentional engine convention:** every
`.clas.abap` file has exactly one real class, but `class_start` matches it twice — once for
`CLASS <name> DEFINITION` and once for `CLASS <name> IMPLEMENTATION.` (confirmed for all 6 files;
e.g. `zcl_abapgit_ajson.clas.abap` line 1 and line 137). In isolation this reads as a double-
counting defect. Cross-referencing sibling languages before filing (per the skill's fallback step
5) found the same shape already exists deliberately in `objective-c`'s own `class_start` regex,
which matches `@interface`, `@implementation`, and `@protocol` for the same class name as three
separate hits — i.e. this engine's established `class_start` semantic is "count of OO-boundary
*syntax blocks*," not "count of unique class *entities*." ABAP's DEFINITION+IMPLEMENTATION double
count is consistent with that convention, not an ABAP-specific bug. **No GitHub issue filed.**

**Summary:** zero confirmed engine defects found. One apparent bug investigated and ruled out via
cross-language precedent. No `credit_tools`/`debit_tools` adjustment applies (there's no second
tool to credit or debit against). Corpus is small (7 files) — a wider manual pass (or, if ABAP ever
gets ctags/tree-sitter support upstream, the normal ledger pipeline) would be needed before calling
this exhaustive; the finding here is that the *sampled* corpus shows no discrepancy, not a
guarantee about the full language.
