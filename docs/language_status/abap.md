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

**Revised a fourth time, 2026-08-20 — all five engine bugs found across this investigation are now
FIXED, and each fix was re-verified rather than assumed complete.** Recapping the timeline for
anyone reading this cold: the first pass (2026-08-19) ran ABAP's `func_start`/`class_start`
regexes directly against raw file text and concluded "100% precision, zero engine defects" — true
of the regexes *in isolation*, but not the same claim as "GitGalaxy correctly extracts ABAP,"
since the real pipeline also runs `prism.py`'s comment/code splitter and `detector.py`'s
segment-routing logic first. A same-day revision caught this and filed two real, confirmed engine
defects ([#1898](https://github.com/squid-protocol/gitgalaxy/issues/1898),
[#1899](https://github.com/squid-protocol/gitgalaxy/issues/1899)). Fixing and re-verifying those
two (rather than trusting the fix and moving on) surfaced two MORE, independent bugs one layer
deeper — [#1904](https://github.com/squid-protocol/gitgalaxy/issues/1904) (a separate named-
class-extraction allowlist gap) and [#1907](https://github.com/squid-protocol/gitgalaxy/issues/1907)
(a class-boundary detector confused by ABAP's own string-template syntax) — and going back to
close out that revision's one remaining open question (`args`' unexplained discrepancy) found a
FIFTH, [#1911](https://github.com/squid-protocol/gitgalaxy/issues/1911) (the same `prism.py`
comment-stripper, but a different unqualified character: `!`, ABAP's formal-parameter-name escape
prefix, mistaken for Fortran's inline-comment marker). All five are now fixed (see each subsection
below for the specific mechanism) and verified against the real `galaxyscope` pipeline output, not
just the regex. The lesson still generalizes, and generalizes further than every prior revision
realized: for a zero-comparison-tool language, "run the regex against text" is necessary but not
sufficient, fixing one confirmed bug is not proof the surrounding extraction path is now fully
correct, AND an "open question, not yet root-caused" note is not a stopping point — it's a lead
that hadn't been chased down yet. Re-verify after every fix, and close out every open question,
instead of stopping at the first green result.

ABAP is one of only 5 languages in the whole registry with **neither** a tree-sitter grammar nor a
ctags parser (the others: `dockerfile`, `jcl`, `livecode`, `yaml` — confirmed against
`tests/tools/ctags_reader.py`'s own LANGUAGE COVERAGE docstring, 2026-08-19). The normal
`tri-comparison-ledger-sweep` methodology (§9 in `c.md`/other languages) needs at least two tools
disagreeing to produce a ledger shape worth investigating — for ABAP there is no second tool, so
`docs/self_scan/tri_comparison_ledger.json` has zero ABAP entries and always will under the current
tool set. This section is a manual by-hand substitute, corrected to check the real pipeline output
(via `galaxyscope ... --db-only` and the resulting sqlite DB), not just the regex.

**Corpus:** `language-crucible/data/abap/abapGit/` — 7 files, 4,006 lines, a local crucible subset
of the same `abapGit` project scanned at full scale in §8 (not the same snapshot or line count —
this is a small, hand-checkable slice, not the 142K-LOC production repo). **Yes, this corpus has
real classes** — all 6 `.clas.abap` files have exactly one real class each (`CLASS <name>
DEFINITION` / `CLASS <name> IMPLEMENTATION.` pairs, confirmed by direct source read) — ABAP is not
a classless language, so a 0 in any class-related metric here is a signal to investigate, never an
assumed "N/A." ABAP also has a real, detectable `args` construct (`IMPORTING`/`EXPORTING`/
`CHANGING`/`RETURNING`/`RECEIVING`/`EXCEPTIONS` parameter-binding keywords) — not every
zero-comparison-tool language has every construct (bash has no formal parameter list at all, for
example), so check what a language actually has before treating an empty measurement as expected.

### `func_start`: the raw regex signal is correct; the *named function list* was not — FIXED (#1899)

**Method:** ran ABAP's actual `func_start` regex from `language_standards.py` against every file's
raw text, recorded every match, then independently re-derived ground truth by reading the source
and cross-checking with a second, unrelated grep (`grep -nE "^\s*METHOD\s+[a-zA-Z]"` per file) that
does not share the primary regex's implementation at all.

**Raw-regex result — 100% precision and 100% recall on every real example in the corpus:**

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

**But the raw regex signal is not what reaches the database.** `detector.py`'s `_function_slice()`
routes each language to an "integration mode" that actually bounds each function's body (needed for
the named function list, complexity metrics, orphan/duplicate detection, etc.), separately from the
raw regex count above. ABAP has no entry in `ScopeParsingRegistry.DEFINITIONS`, so it silently falls
through to `Mode_B_Braces` — brace-delimited slicing — even though ABAP has no braces at all
(methods are delimited by `METHOD <name>. ... ENDMETHOD.`, not `{`/`}`). Running the real pipeline
(`galaxyscope language-crucible/data/abap --db-only`) and querying the resulting DB:

| File | `struct_func_start` (raw signal, correct) | `function_count` (named list, via Mode_B_Braces) |
|---|---|---|
| `zcl_abapgit_ajson.clas.abap` | 47 | 4 |
| `zcl_abapgit_git_porcelain.clas.abap` | 19 | 5 |
| `zcl_abapgit_http_client.clas.abap` | 10 | 1 |
| `zcl_abapgit_objects.clas.abap` | 30 | 5 |
| `zcl_abapgit_persistence_db.clas.abap` | 13 | 1 |
| `zcl_abapgit_xml_output.clas.abap` | 5 | 0 |
| **Total** | **124** | **16 (13%)** |

Only functions that happen to sit near a stray `{`/`}`-like character survive Mode B's brace search
by coincidence — the other 87% were silently dropped from `function_data`, `function_count`, and
therefore from the tri-comparison chart's "Functions Found" number too.

**Fix (2026-08-20):** added `abap` to the language list routed through Mode A
(`_slice_by_labels`) in `detector.py`'s `_function_slice()` instead of falling through to Mode B.
Mode A already existed for COBOL's own label-only paragraphs (no closing keyword at all) — it
bounds each function's body by taking everything from one `func_start` match up to the START of
the next one, which is a correct heuristic for ABAP too, since ABAP methods are never nested
inside each other. No new slicing mode was needed. Re-verified against the real pipeline after the
fix: `function_count` now equals `struct_func_start` exactly for every file (124/124 total, 0
false positives/negatives), and every real name — including tilde-qualified interface methods like
`zif_abapgit_ajson~get_string` — comes through the named list intact. **Fixed via
[#1899](https://github.com/squid-protocol/gitgalaxy/issues/1899).**

### `class_start`: not a double-count question — the class lines never reached the regex at all — FIXED (#1898)

The first version of this section asked "does `class_start` double-count `DEFINITION` +
`IMPLEMENTATION` the way objective-c's `@interface`/`@implementation` intentionally does?" — a
reasonable question, but the wrong one. Running the real pipeline and checking `file_data.
struct_class_start` (the raw signal count, computed independently of the named-list issue above):
**0 for every single ABAP file**, including all 6 files with a real class. The regex itself is
fine — running it directly against unprocessed file text finds all 12 real `DEFINITION`/
`IMPLEMENTATION` matches (2 per class, 6 classes) — but it never gets the chance to run against
that text, because `prism.py` deletes it first.

Root cause: `prism.py`'s `_strip_positional_comments()` treats any line whose column-1 character is
in the shared `POSITIONAL_ANCHORS` set (`{"*", "C", "c", "/", "!"}`, built for Fortran's
column-1-`C`-means-comment convention and COBOL) as a full-line comment. ABAP's own real column-1
comment marker is `*` only — but real ABAP classes are written flush-left (`CLASS <name>
DEFINITION`), so column 1 is a literal `C`, and the shared Fortran/COBOL rule erases the entire
line into the comment stream before `detector.py` ever sees it. Isolated repro:

```python
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.language_standards import LENS_CONFIG, LANGUAGE_DEFINITIONS
p = Prism(LENS_CONFIG.get("COMMENT_DEFINITIONS", {}), LANGUAGE_DEFINITIONS)
result = p.split_streams("CLASS zcl_foo DEFINITION\n  PUBLIC\n  CREATE PUBLIC .\nENDCLASS.\n", "abap")
print(result["code_stream"])     # '\n  PUBLIC\n  CREATE PUBLIC .\nENDCLASS.\n' -- header line GONE
print(result["comment_stream"])  # 'CLASS zcl_foo DEFINITION' -- misclassified as a comment
```

This also blocked `detector.py`'s class→method linkage (`parent_class_name`/`class_methods_by_id`)
for every ABAP file, since there were never any `classes` entries to link methods into.

**Fix (2026-08-20):** `_strip_positional_comments()` now takes an ABAP-specific anchor set (just
`*`, the language's own real column-1 comment marker) instead of the shared Fortran/COBOL
`POSITIONAL_ANCHORS`, and skips the column-7 check entirely (a fixed-form COBOL/Fortran concept
that doesn't apply to free-form ABAP). COBOL and Fortran are unaffected — they still use the full
shared anchor set, verified via their own test suites (321 tests) plus an isolated repro showing a
literal `C This is a classic fortran comment` line still strips correctly. Re-verified against the
real pipeline after the fix: `struct_class_start`/`class_count` now show 2 per real class file
(the `DEFINITION` + `IMPLEMENTATION` pair, matching the engine-wide "OO boundary" convention
already established for objective-c) and 0 for the one file with no class — exactly matching the
12 real matches found by applying the regex directly to unprocessed text. **Fixed via
[#1898](https://github.com/squid-protocol/gitgalaxy/issues/1898).**

### Named class list still empty after #1898 — a third, separate bug — FIXED (#1904)

Fixing #1898 correctly restored `struct_class_start`/`class_count` to 2 per real class file, but
regenerating `docs/self_scan/tri_comparison_chart.svg` afterward showed abap's "Classes Found"/
"Class Precision" panels still completely blank, and `tri_comparison_gatherer.gather_language
("abap")` still returned `gg_classes: []` for every file. `struct_class_start` (the raw regex
signal) and the actual *named* `classes` list (what feeds `class_data`/the chart) turned out to be
two independent code paths, and only the first one was fixed by #1898.

Root cause: `detector.py`'s named-class extraction in `splice()` only reuses a language's own
`class_start` rule when that language is listed in `_CLASS_START_NAMED_EXTRACTION_LANGS` (epic
#1295) — every other language falls through to a generic legacy regex, `(?:class|struct|interface
|trait|enum)`, compiled **without** `re.I`. ABAP was never added to that set — likely because the
epic's own documented verification method (`tree_sitter_accuracy_audit.py --lang <x>` against
tree-sitter ground truth) structurally cannot run for a language with no tree-sitter grammar at
all. Real ABAP classes are always uppercase (`CLASS <name> DEFINITION`), so the case-sensitive
fallback regex could never match ABAP source regardless of #1898's fix — the named list was
guaranteed empty by construction.

**Fix (2026-08-20):** added `"abap"` to `_CLASS_START_NAMED_EXTRACTION_LANGS`, using the
verification already done in this doc (100% precision on all 12 real matches, direct source
cross-check) in place of the epic's tree-sitter-based method, which doesn't apply here. Re-verified
via `tri_comparison_gatherer.gather_language("abap")`: every real class file now returns 2 named
class entries with correct names (e.g. `['zcl_abapgit_ajson', 'zcl_abapgit_ajson']` for the
`DEFINITION`+`IMPLEMENTATION` pair — one file's two entries even preserve genuinely different
source casing, `zcl_abapgit_xml_output` vs. `ZCL_ABAPGIT_XML_OUTPUT`, extracted faithfully rather
than normalized away). **Fixed via
[#1904](https://github.com/squid-protocol/gitgalaxy/issues/1904).**

### Class→method linkage truncated by ABAP's own string-template syntax — a fourth bug — FIXED (#1907)

Found while verifying #1904's fix: `zcl_abapgit_objects.clas.abap` has 30 real methods
(`struct_func_start`/`function_count` both correctly show 30), but its class entry's
`method_count` came back as **2**. `splice()`'s class-boundary resolver tries a brace-delimited
body search first and only falls back to a flat "next class match" boundary if no `{` is found
within 2000 chars. ABAP has no brace-delimited bodies at all, but it DOES have string-template
interpolation syntax that legitimately contains braces:

```abap
ii_log->add_success( iv_msg = |Object { is_item-obj_name } ...| ).
```

`_build_brace_safe_stream()` shields `"`/`'`/backtick-style string literals before the brace
search runs, but has no knowledge of ABAP's `|...|` pipe-delimited templates, so this `{` reached
the search unshielded, got mistaken for the class's real body opener, and truncated the scope
right after the first couple of methods — every subsequent method in the file never got linked to
its class.

**Fix (2026-08-20):** since ABAP classes are never nested, the flat "next class match, or EOF"
fallback (already computed unconditionally at the call site) is always correct for ABAP — the
brace-search path is now skipped entirely for `abap` rather than teaching the shared brace-safe
stream builder about pipe-delimited string templates (a bigger, riskier change touching other
regex signals too). Re-verified: `zcl_abapgit_objects`' class entry now shows `method_count: 30`,
matching its real function count exactly, and every other file's linkage still matches its real
method count too. **Fixed via
[#1907](https://github.com/squid-protocol/gitgalaxy/issues/1907).**

### `args`: a fifth bug, same shape as #1898 but a different character — FIXED (#1911)

`file_data.struct_args` vs. a raw-regex count on unprocessed text disagreed in both directions
(e.g. `zcl_abapgit_objects.clas.abap`: 49 in the DB vs. 37 raw; `zcl_abapgit_persistence_db.
clas.abap`: 16 vs. 10) rather than the DB consistently undercounting the way func/class did before
their own fixes — a strong hint the root cause was structurally different from #1898/#1899, not
just "the same bug, smaller."

Root cause, found by diffing `code_stream` against raw file text directly: `prism.py`'s
`_strip_positional_comments()` has a "Modern Inline Fortran (`!`)" comment-stripping branch that,
unlike the `"` branch right above it, was **not gated by `abap_mode`**. `!` has no comment meaning
in ABAP at all — but ABAP uses a leading `!` to escape formal parameter names in method signatures,
extremely common syntax:

```abap
CLASS-METHODS pull_by_branch
  IMPORTING
    !iv_url          TYPE string
  RETURNING
    VALUE(rs_result) TYPE ty_pull_result
```

Every such line was truncated at the `!`, erasing the parameter name and its `TYPE` clause.
`zcl_abapgit_git_porcelain.clas.abap`'s raw text is 26,121 chars; its `code_stream` was only
23,214 — prism.py is supposed to preserve length/line structure, only blanking content in place,
so a ~2,900 char loss was itself a red flag before even looking at `args`. With the real parameter
names blanked to whitespace, the `args` regex's `\s+` reached across the empty lines to the NEXT
keyword (e.g. `RETURNING`) and mismatched it as the current keyword's own parameter name —
producing a completely different match set (31 matches on the corrupted `code_stream` vs. 22 on
raw text, zero overlap between the two sets), not a simple over- or under-count. `func_start`/
`class_start` were unaffected because their matches come from the `IMPLEMENTATION` section
(`METHOD name.` / `CLASS name IMPLEMENTATION.`), which never contains `!param` syntax — only the
`DEFINITION` section's method signatures do, exactly where `args` reads from.

**Fix (2026-08-20):** gated the `!` branch the same way the `"` branch already was
(`elif not abap_mode and "!" in line:`) — ABAP has no `!`-based comment convention at all, so this
is a clean full exclusion, not a partial one. Fortran (which legitimately uses `!` for inline
comments) is unaffected, verified via its own test suite plus an isolated repro. Re-verified:
`code_stream`'s `args` match count now equals the raw-text count exactly for all 7 corpus files
(23/23, 22/22, 12/12, 37/37, 10/10, 1/1, 0/0), and `struct_args` in the DB matches too. The fix's
blast radius is wider than just `args` — restoring the erased parameter-name text also corrected
`core_var_decl`/casing-classifier counts and indentation-based signals for the same files, since
those regexes were scanning the same corrupted `code_stream`. **Fixed via
[#1911](https://github.com/squid-protocol/gitgalaxy/issues/1911).**

**Summary:** five confirmed engine defects found, fixed, and re-verified against the real pipeline
(#1898, #1899, #1904, #1907, #1911 — all closed). Every fix was found by re-verifying the PREVIOUS
fix against the real pipeline rather than assuming one fix meant the whole extraction path was now
correct — #1899 surfaced while checking #1898's numbers against actual DB output, #1904 surfaced
while regenerating the tri-comparison chart after #1898/#1899 merged, #1907 surfaced while
verifying #1904's fix itself, and #1911 (this section) was the "not yet root-caused" open question
from the previous revision, resolved by the same "diff the actual code_stream against raw text"
technique that found #1898 in the first place. No `credit_tools`/`debit_tools` adjustment applies
to any of the five (there's no second tool to credit or debit against, and these were
GitGalaxy-side bugs, not a cross-tool disagreement). Corpus is small (7 files) — a wider manual
pass (or, if ABAP ever gets ctags/tree-sitter support upstream, the normal ledger pipeline) would
surface more; the finding here is real for the *sampled* corpus, not a guarantee no other issue
exists. #1898/#1899/#1911 each went through the full Differential Scan protocol
(`crucible_check.py` against the ~80-repo language-crucible corpus, both full-precision and
zero-dependency modes) and required regenerating both golden master fixtures; #1904/#1907 live
entirely in the SQLite recorder's named-class-list path, which those fixtures don't exercise at
all — `crucible_check.py` passed with zero drift both before and after those two, confirmed via
the tri-comparison gatherer and a direct `--db-only` scan instead.
