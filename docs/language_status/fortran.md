# Fortran — Structural Signature Coverage

Snapshot generated 2026-08-21 against `main`. Source: `LANGUAGE_DEFINITIONS["fortran"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_fortran.py` /
`test_fortran_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Fortran 2018 (backwards compatible with Legacy Fortran 77) |
| `_meta.blueprint_version` | v7.0 |
| `_meta.last_updated` | 2026-03-01 |
| `lexical_family` | `positional_anchored` (Family 7, "the Positional Ancients" — fixed-format requires column-1 monitoring for `C`/`*`; free-format uses `!`. Shares its comment-stripping code path, `Prism._strip_positional_comments`, with `cobol`, which additionally watches column 7 — Fortran does not, see §7) |
| Structural signature keys wired | 45 / 52 (7 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_fortran.py`) | 35 |
| Strict-signature tests (`test_fortran_strict.py`) | 101 |
| Total dedicated Fortran test cases | 136 |

## 2. Identification surface

- **Extensions:** `.f .f90 .f77 .for .fpp .f95 .f03 .f08 .f18 .ftn .inc` — every standard fixed-
  and free-format generation from F77 through F2018, plus a preprocessor variant (`.fpp`) and a
  generic legacy include (`.inc`, shared ambiguously with other languages — see discriminators).
- **Exact filenames:** none.
- **Discriminators:** `.f90`, `.f77`, `.f`, `fpm.toml` (the Fortran Package Manager manifest),
  `CMakeLists.txt`, `Makefile` — ecosystem anchors used mainly to resolve ambiguous files like
  `.inc`.
- **Shebangs:** `fortran`, `f90`, `f77`, `gfortran`.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py`/`how_to_add_a_language.md` use. Description
is what Fortran's *actual* regex captures, not the generic cross-language definition.

**Logic topology & structure**
| Key | What it captures for Fortran |
|---|---|
| `branch` | `IF ELSEIF ELSE DO WHILE SELECT CASE CASE DEFAULT WHERE ELSEWHERE GOTO/GO TO SELECT TYPE SELECT RANK EXIT CYCLE`, plus `.AND.`/`.OR.` logical operators |
| `args` | `SUBROUTINE`/`FUNCTION`/`ENTRY` parameter-list parens (own capture group per #1209/#1218, participates even when the parens are genuinely absent for a bare zero-arg subroutine), plus a separate bare-keyword alternative for `INTENT(IN/OUT/INOUT)`/`VALUE`/`OPTIONAL` usage as a coupling signal |
| `structural_boundaries` | `PROGRAM MODULE SUBMODULE BLOCK DATA CONTAINS END <block> RETURN IMPLICIT USE ASSOCIATE BLOCK INTEGER REAL COMPLEX LOGICAL CHARACTER DOUBLE PRECISION CLASS` — deliberately excludes `PUBLIC`/`PRIVATE`/`PROTECTED` access modifiers to avoid inflating structural-complexity counts |
| `func_start` | The "Iron Wall" anchor for `PROGRAM`/`SUBROUTINE`/`FUNCTION`/`ENTRY`: blocks `END <keyword>` via a leading negative lookahead, allows up to 5 stacked prefixes (`PURE RECURSIVE ELEMENTAL IMPURE MODULE`), an optional return-type clause bounded to `{0,40}` chars (the #1531 ReDoS/phantom-match fix, see §7), and a trailing lookahead that tolerates line continuations (`&`), inline comments (`!`), EOF, or `RESULT`/`BIND` modifiers without consuming them |
| `class_start` | Two alternation branches sharing groups: `MODULE`/`BLOCK DATA`/`INTERFACE`/`SUBMODULE(parent)` names in group 1 (excluding `MODULE PROCEDURE` stubs via #1264's negative lookahead), and standalone `TYPE`/`TYPE ::`-declared derived-type names in group 2 — the two groups are alternation-exclusive, never name+parent (see §7's #1983 note) |

**Risk & structural integrity**
| Key | What it captures for Fortran |
|---|---|
| `safety` | `IMPLICIT NONE`, `INTENT(IN/OUT/INOUT)` (split into its own alternative so the trailing `\b` boundary bug that silenced it doesn't recur), `ALLOCATABLE SAVE PARAMETER VALUE ERROR STOP ASYNCHRONOUS ASSOCIATED ALLOCATED PRESENT` |
| `safety_bypasses` | `COMMON EQUIVALENCE`, unsafe `IMPLICIT REAL/INTEGER/CHARACTER/COMPLEX/LOGICAL` typing |
| `high_risk_execution` | `GOTO`/`GO TO`, `ASSIGN`, `RETURN <n>` (legacy alternate-return) |
| `io` | `OPEN CLOSE READ INQUIRE REWIND BACKSPACE ENDFILE FLUSH FORMAT`, plus `WRITE(...)` to a real file unit (negatively asserting `*`/`6` so terminal prints route to `debug_prints` instead) |
| `api` | `PUBLIC`, `BIND(C)` FFI bridges, plus a line-anchored `SUBROUTINE`/`FUNCTION` declaration pattern (implicit-public-by-default) |
| `state_mutation` | Real `=` assignment (not `==`/`<=`), bounded to 199 chars, excluding `KIND=`/`LEN=`/`UNIT=`/`FMT=`/`FILE=`/`STATUS=`/`ACTION=` keyword-argument forms via a real `\b`-anchored lookahead |
| `dead_code` | `!`-prefixed or column-1 `C`/`*`-prefixed lines immediately followed by a real statement verb (`if do where call function subroutine allocate`) |
| `doc` | Doxygen-style `!>`/`!<`/`! @` markers, or `! Author:`/`Description:`/`Param:`/`Return:` tags |
| `test` | pFUnit annotations (`@test @assertEqual @assertTrue @assertFalse @assertException`), `call assert_*` |

**Architecture & domain sensors**
| Key | What it captures for Fortran |
|---|---|
| `concurrency` | Fortran 2008/2018 coarray primitives (`COARRAY SYNC ALL/IMAGES/MEMORY CRITICAL LOCK UNLOCK FAIL IMAGE FORM TEAM`), `MPI_*` calls, `!$OMP`/`!$ACC` pragmas |
| `globals` | `COMMON SAVE EXTERNAL` |
| `decorators` | `!DIR$`/`cDEC$` compiler directives, `!$OMP`/`!$ACC` pragma lines |
| `generics` | `INTERFACE ASSIGNMENT`/`INTERFACE OPERATOR`, `GENERIC ::`, parameterized derived types (`TYPE name(k, n)`), `EXTENDS(...)` |
| `comprehensions` | `FORALL`/`DO CONCURRENT`, `[...]` array constructors, legacy `(/.../)` array constructors |
| `scientific` | `MATMUL DOT_PRODUCT TRANSPOSE SUM PRODUCT MAXVAL MINVAL MAXLOC MINLOC RESHAPE` plus the standard trig/exponential/log intrinsics, `KIND=`, `CEILING FLOOR MOD MODULO` |
| `reflection_metaprogramming` | `EQUIVALENCE ENTRY SELECT TYPE CLASS DEFAULT NAMELIST VOLATILE` |
| `import` | `USE INCLUDE IMPORT` |
| `_dependency_capture` | Extracts the module name from `USE`, the path from `INCLUDE '...'`, and the parent module from `SUBMODULE(parent)` |
| `ownership` | Column-anchored `Author:`/`Created by:`/`Maintainer:`/`Developer:` tags |

**Specialized subsystems**
| Key | What it captures for Fortran |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`, `[AUDIT-XYZ]` traceability tags, strict uppercase only |
| `events` | Fortran 2018 event-driven coarray sync primitives (`EVENT POST/WAIT`, `EVENT_QUERY`) |
| `macros` | Standard C-preprocessor directives (`#define #undef #if #ifdef #ifndef #elif #else #endif #include #pragma`) — Fortran source routed through `cpp` is common, especially in WRF-style scientific codebases |
| `pointers` | `POINTER` keyword, `=>` pointer-assignment operator |
| `memory_alloc` | `ALLOCATE DEALLOCATE MOVE_ALLOC`, plus C-FFI `MALLOC`/`FREE` |

**Resource management & stability**
| Key | What it captures for Fortran |
|---|---|
| `telemetry` | `log_info/log_error/log_warn/log_debug`, `logger%info/%error/%warn/%debug`, `flog` — custom structured Fortran loggers, kept separate from raw terminal prints |
| `debug_prints` | `PRINT`, `WRITE(*,...)`/`WRITE(6,...)` — raw terminal output |
| `explicit_casts` | `INT REAL CMPLX DBLE ACHAR CHAR IACHAR ICHAR` intrinsic conversion calls |
| `panics_and_aborts` | `STOP`, `ERROR STOP`, `RETURN` |
| `thread_sleeps` | `CALL SLEEP`/`CALL USLEEP` |
| `bitwise_ops` | `IAND IOR IEOR NOT ISHFT ISHFTC BTEST IBSET IBCLR IBITS` intrinsic bitwise functions |
| `sync_locks` | `LOCK UNLOCK CRITICAL SYNC ALL/IMAGES/MEMORY` |
| `immutability_locks` | `PARAMETER`, `INTENT(IN)` |
| `cleanup` | `CLOSE DEALLOCATE NULLIFY` |
| `encapsulation` | `PRIVATE` |

**Hybrid domain sensors (Fortran specifics)**
| Key | What it captures for Fortran |
|---|---|
| `serialization_parsing` | `NAMELIST READ( WRITE( FORMAT OPEN(` |
| `regex_execution` | `SCAN INDEX VERIFY ADJUSTL ADJUSTR` — Fortran's nearest equivalent, intrinsic string-processing functions (no true regex engine) |
| `time_date_logic` | `DATE_AND_TIME SYSTEM_CLOCK CPU_TIME` |
| `ipc_rpc_bridges` | `MPI_Init MPI_Send MPI_Recv MPI_Bcast EXECUTE_COMMAND_LINE`, plus any `OMP_*` runtime call as a prefix match |

## 4. What GitGalaxy explicitly does not track

Seven keys are hard-set to `None` in Fortran's `rules` dict (Rule 4 of the engine's generation
rules: explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`ui_framework`** — "Fortran handles math and background computing. No native UI frameworks
  exist."
- **`closures`** — "Fortran does not natively support closures, lambdas, or anonymous functions."
- **`ssr_boundaries`** — "Fortran does not perform Server-Side Rendering."
- **`dependency_injection`** — "Fortran handles linkages procedurally or via modules. No native DI
  containers or decorators exist."
- **`inline_asm`** — "Fortran delegates assembly to standard C linkage. Inline ASM is explicitly
  not supported natively in Fortran code."
- **`listeners`** — no inline reason given; no native event-listener/observer registration
  construct in the language.
- **`test_skip`** — no inline reason given; no standardized bypassed-test-marker convention across
  Fortran test frameworks the way `pytest.mark.skip` gives Python one.

## 5. Known limitations (accepted, not fixed)

No `known_limitation`-named tests exist for Fortran in either `test_fortran.py` or
`test_fortran_strict.py` (confirmed via `grep -n known_limitation` against both files, zero
matches) — unlike `python`/`cobol`, Fortran currently has no gap that was deliberately investigated
and then accepted as unfixable rather than fixed. This is a statement about what's *documented* as
accepted, not a claim that no gaps exist at all — see §7 for real, still-open defects that simply
haven't gone through that documentation step yet.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 35 tests in
  `tests/extraction/languages/test_fortran.py` — valid/invalid/pathological cases per rule, two
  dedicated ReDoS-immunity probes for `func_start` (including the #1531 phantom-match regression,
  see §7), and the full `_dependency_capture` valid/invalid set. **Coverage gap found while
  writing this doc:** the four `test_fortran_args_valid` parametrized cases
  (`ARGS_VALID`, lines 105–113) are collected and pass, but the test body is a bare `pass` — the
  function never actually calls `assert_valid_match` or inspects the regex at all. `args` has no
  real extraction-gauntlet assertion coverage despite appearing to (documentation only, not
  fixed as part of writing this doc per the task's scope discipline).
- **Strict signature suite** (all other wired keys): 101 tests in
  `tests/extraction/languages/test_fortran_strict.py` — positive/negative coverage per signature,
  a dedicated `state_mutation` ReDoS/`KIND=`-exclusion regression, a pFUnit-annotation leading-
  boundary regression, ~15 intentional-double-classification / no-false-collision pairs (e.g.
  `io` vs. `debug_prints` terminal-write, `explicit_casts` vs. `pointers`, `func_start` vs.
  `macros`, `func_start` vs. `generics`), a dedicated ReDoS-immunity sweep, and a parametrized deep
  adversarial case block (`test_fortran_signature_deep_cases`) added by the cross-language
  strict-hardening epic.

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#855](https://github.com/squid-protocol/gitgalaxy/issues/855) (CLOSED, merged
  [#949](https://github.com/squid-protocol/gitgalaxy/pull/949)) — Extraction hardening for Fortran
  (epic #813): added multi-line continuation (`&`) support, `VALUE`/`OPTIONAL` argument
  attributes, `SUBMODULE` parent-dependency capture, and `PURE`/`ELEMENTAL` prefix stacking;
  eliminated a `_dependency_capture` ReDoS (unbounded whitespace between `USE` and the module
  name).
- [#581](https://github.com/squid-protocol/gitgalaxy/issues/581) (CLOSED, merged
  [#764](https://github.com/squid-protocol/gitgalaxy/pull/764)) — Strict parsing tests for
  Fortran structural signatures (epic #518). Found and fixed 6 real bugs, all one root-cause
  defect class: a shared trailing `\b` boundary applied across an alternation where some
  alternatives end in a non-word character (`decorators`' `!DIR$`, `generics`' `GENERIC::`/`TYPE
  name(...)`/`EXTENDS(...)`, `io`'s file-unit `WRITE`, `safety`'s `INTENT(...)`,
  `ipc_rpc_bridges`' `OMP_` prefix) — the boundary could only fire if the character right after
  the literal happened to be a word character, never true for the realistic form.
- [#1209](https://github.com/squid-protocol/gitgalaxy/issues/1209) (CLOSED, Fortran's share
  merged in [#1218](https://github.com/squid-protocol/gitgalaxy/pull/1218)) — `args` had zero
  capture groups, so detector.py's counter whitespace-split the *entire* match (prefix keyword +
  name included) instead of isolating just the parameter list. Fortran needed bespoke handling
  (Tier 2, not a mechanical port) since its parens are optional and its alternation also matches
  unrelated `INTENT`/`VALUE`/`OPTIONAL` keyword usage.
- [#1264](https://github.com/squid-protocol/gitgalaxy/issues/1264) / (epic
  [#1295](https://github.com/squid-protocol/gitgalaxy/issues/1295)) (CLOSED, merged
  [#1296](https://github.com/squid-protocol/gitgalaxy/pull/1296)) — `detector.py`'s named-entity
  class extractor never consulted per-language `class_start` at all, zeroing class recall for
  apex/csharp/**fortran**/solidity despite each language's own `class_start` regex being correct.
  Root cause was architectural (a hardcoded language-agnostic fallback regex), not a broken
  Fortran pattern.
- [#1531](https://github.com/squid-protocol/gitgalaxy/issues/1531) (CLOSED, merged
  [#1555](https://github.com/squid-protocol/gitgalaxy/pull/1555)) — `func_start`'s optional
  return-type "legacy sizing/attributes" character class had no length cap and included letters/
  newlines; on a body-less type-declaration line immediately preceding an unrelated later
  `SUBROUTINE`/`FUNCTION`, backtracking let it swallow the *entire* intervening subroutine body —
  including that body's own trailing `END SUBROUTINE <name>` — producing a phantom duplicate
  match with a `start_line` ~370 lines off. Confirmed on WRF's `module_initialize_real.F`. Fixed
  with a `{0,40}` numeric bound (a per-character `(?!\bEND\b)` exclusion was tried first and is
  more semantically precise, but disabled `re`'s fast path: 0.01s vs. ~13s on a pathological
  payload).

**Cross-language fixes that touched Fortran along the way:**
- [#1949](https://github.com/squid-protocol/gitgalaxy/issues/1949) (CLOSED, merged
  [#1959](https://github.com/squid-protocol/gitgalaxy/pull/1959)) — `detector.py`'s Mode A
  label-slicing path (`_slice_by_labels`, shared by `assembly`/`cobol`/**`fortran`**/`abap`/
  `agc_assembly`) had two independent bugs silently truncating or discarding real function bodies.
  Found while investigating `agc_assembly`'s tri-comparison ledger, confirmed to generalize to
  Fortran and its Mode A siblings.
- [#1973](https://github.com/squid-protocol/gitgalaxy/issues/1973) (CLOSED, merged
  [#1985](https://github.com/squid-protocol/gitgalaxy/pull/1985)) — Mode A's generic per-function
  `args_count` search ran against the *entire* greedy block between one `func_start` match and the
  next, so an unrelated later statement's args could get misattributed to the current label. Fixed
  by bounding the search to the matched label's own statement span, following real Fortran
  line-continuation syntax (`&`) including inline comments, blank lines, and cpp-directive
  interruptions — necessary because WRF's real subroutines can have 200+ parameters spread across
  90+ continuation lines.
- [#1745](https://github.com/squid-protocol/gitgalaxy/pull/1745) (MERGED) — fixed geometry
  (line-number) corruption in `prism.py` by ensuring skipped positional comments (Fortran, COBOL)
  still append blank lines to the code stream instead of silently swallowing newlines; also added
  tree-sitter ERROR/preproc blind-spot handling for Fortran to avoid false-positive "extra
  functions" in the tree-sitter accuracy audit (closes
  [#1717](https://github.com/squid-protocol/gitgalaxy/issues/1717) — `tree-sitter-fortran`
  completely fails to parse CPP-heavy WRF-style files, undercounting tree-sitter's own ground
  truth, not a GitGalaxy defect).

**This session's fortran fix (uncommitted in this working tree, ships together with this doc as
one PR per the task's instructions):**
- `prism.py`'s `_strip_positional_comments` previously applied COBOL's column-7 indicator-area
  check to Fortran too (via a shared `POSITIONAL_ANCHORS` set with no Fortran/COBOL distinction).
  Real fixed-form Fortran 77 has no column-7 comment convention at all — column 6 is a
  continuation flag, not a comment marker — so any statement whose 7th character happened to
  coincide with an anchor character (e.g. a 3-space-indented `   FUNCTION foo(...)` puts the `C`
  of `FUNCTION` at column 7) was silently erased as a bogus comment before `func_start` ever saw
  it. Confirmed via the `tri-comparison-ledger-sweep` skill's fortran pass against real WRF source
  (`wrf/module_configure.F:353` `in_use_for_config`, `wrf/module_domain.F:1693`
  `first_loc_integer`). Fixed by gating the column-7 check to `cobol_mode` only.

**Still-open, real defects (not fixed as part of writing this doc, per its documentation-only
scope):**
- [#2077](https://github.com/squid-protocol/gitgalaxy/issues/2077) (OPEN) — the `args` regex
  undercounts a subroutine's parameter count when the parameter list contains an embedded
  C-preprocessor conditional (`#if (...)`/`#ifdef`) whose own guard expression has a `)` before
  the real signature's closing paren is reached. Found via the `tri-comparison-ledger-sweep`
  skill's fortran pass.
- [#1982](https://github.com/squid-protocol/gitgalaxy/issues/1982) (OPEN) — a related but
  distinct shape from the #1531 fix above: `func_start`'s optional return-type prefix can still
  bridge across an unrelated statement to a distant `SUBROUTINE`/`FUNCTION` in some cases the
  `{0,40}` bound doesn't fully close.
- [#1983](https://github.com/squid-protocol/gitgalaxy/issues/1983) (OPEN) — `detector.py`'s
  "lineage extractor" unconditionally treats any `class_start` match's capture group 2 as an
  inheritance parent whenever the pattern has 2+ groups. Fortran's `class_start` (§3) uses group 1
  and group 2 as alternation-exclusive branches (`MODULE`/`INTERFACE`/`SUBMODULE` name vs. `TYPE`
  name), never name+parent — so a bare `TYPE foo` declaration's own name gets swept into
  `extracted_parents` and shows up as that file's `parent_entity` metadata, double-counting the
  type's own name as if it were a lineage relationship. Confirmed already live in production
  (`status: production`); low-priority per the issue since it's cosmetic metadata, not incorrect
  *class* extraction (that path already handles the alternation correctly).
- [#259](https://github.com/squid-protocol/gitgalaxy/issues/259) (OPEN, reopened 2026-08-20) —
  `_strip_positional_comments`'s two *inline* comment splits (`*>` for free-form COBOL, `!` for
  Fortran/free-form) still have no `LITERAL_MASK_PATTERN` string-literal shielding, unlike every
  other stripping path in `prism.py`. A line like `PRINT *, "Warning!"` gets truncated at the `!`
  inside the string literal, misclassifying the rest of the line as a comment. Distinct from the
  column-7 fix above (that one was the column-*anchored* check; this is the separate inline-marker
  split) and not touched by it.

Search performed via `gh issue list --search 'in:title "Extraction hardening: fortran"'` /
`'in:title "Strict parsing tests: fortran"'` / `'in:title fortran'` (2026-08-21), cross-checked
against PRs mentioning `fortran` over the same window. Excluded as not language-coverage-specific:
generic tree-sitter-accuracy-tooling/CI-rollout issues that mention fortran only incidentally
(#1253, #1717's audit-tooling half already covered above, #1858/#1898/#1911/#1913's ABAP-specific
fixes to the shared `_strip_positional_comments`/Mode A code paths that don't change Fortran's own
observed behavior).

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Only one repo in the `v2.4.7` batch has Fortran as its dominant language — the corpus this
session's own tri-comparison sweep and several of the fixes above (#1531, #1745, #1973, the
uncommitted column-7 fix) were diagnosed against:

- **[`wrf-fortran`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/wrf-fortran/wrf-fortran_galaxy_llm.md)**
  — the Weather Research and Forecasting model (`wrf-model/WRF.git`), a large, decades-old
  production numerical-weather-prediction codebase: 1,137,651 total LOC, 4,915 total artifacts
  (3,547 analyzed, 72.2% scanned), Fortran the dominant language. Heavy real-world use of exactly
  the syntax shapes this doc's §3/§7 describe — CPP-guarded parameter lists, deep multi-line
  continuations, legacy fixed-form column conventions mixed with modern free-form modules. Scanned
  in 30.78s.

`_galaxy_audit.json.gz` and `_galaxy_sbom.json.gz` in the same directory carry the raw per-file
signature counts and SBOM if deeper inspection is needed.

## 9. Tri-comparison: GitGalaxy vs. tree-sitter vs. ctags

Same shape as `docs/language_status/c.md`'s §9 (not python.md's/javascript.md's, which diff
against one privileged ground-truth parser) — Fortran has two independent, non-privileged
comparison tools (`tree-sitter-fortran`, `universal-ctags`) and neither is treated as ground
truth; every discrepancy was resolved by reading real source
(`docs/self_scan/how_to_investigate_a_discrepancy.md`'s process), via the
`tri-comparison-ledger-sweep` skill (2026-08-21). Full record:
`docs/self_scan/tri_comparison_ledger.json`, filterable to `"language": "fortran"`.

**Result: all 5 open discrepancy shapes from this pass validated** (a 6th, older shape —
`fortran/function/args/agree[ctags,tree_sitter]_vs[gitgalaxy]` — was already validated from a
prior session and untouched here). Two were confirmed real GitGalaxy engine defects (one fixed in
this same pass, one filed as still-open since it needs real design work); one was a real
GitGalaxy-correct-but-uncorroborated case (also fixed, both other tools' non-corroboration
traced to their own confirmed limitations); two were confirmed real bugs in this repo's own
`ctags_reader.py` comparison tooling, not GitGalaxy or ctags itself. Current measured numbers
(`tests/tools/tri_comparison_chart.py --languages fortran`, `language-crucible/data/fortran/wrf/`
— the WRF numerical-weather-model corpus, the same one §8 describes):

| Signal | GitGalaxy | tree-sitter | ctags | Read as |
|---|---|---|---|---|
| Functions found (of 139 total claimed by any tool) | **139** | 123 | 138 | GitGalaxy finds every real function; tree-sitter's CPP-cascade gap and ctags' one unexplained file-specific miss both real, both explained below |
| Function precision (of what each tool claimed, how much corroborates) | **100%** (139/139) | 100% (123/123) | 100% (138/138) | 3-way tie on rate — broken by absolute validated-correct count (139 > 138 > 123), GitGalaxy wins outright |
| Class recall/precision | **100%** (11/11) | 100% (11/11) | 100% (11/11) | fully reconciled after this pass's ctags_reader.py fix — see below |
| Args found (of 123 total claimed by any tool) | **123** | 123 | 95 | tied for best; a separate, narrower per-function args-*count* defect exists independent of this existence panel — see below |

**Recall audit (2026-08-29, skill step 2.6).** Every function tree-sitter reports that GitGalaxy
does not (2 occurrences — `compute_eta`, `wrf_error_fatal`) was individually read. Both are
**phantoms tree-sitter parses from inside the `#ifdef VERT_UNIT` unit-test driver** — the
top-level `program vint` / `program foo` blocks (`module_initialize_real.F:5375` / `:7519`) that
are alternative compilation roots, dead when the file is built as a module. tree-sitter has no
preprocessor model; GitGalaxy finds both real `SUBROUTINE` definitions (lines 5471 / 7567) and
correctly ignores the driver blocks. The accuracy audit was corrected to mark a module file's
`program`…`end program` spans as blind spots — **Fortran func recall 98.6% → 100.0%**, zero real
recall gaps.

Before this pass: Functions Found showed 137*/123*/137* (all three asterisked — unvalidated),
Func Precision 135/137*/123/123*/137/137*, Classes Found 11*/11*/3* (ctags badly undercounting),
Args Found 121*/121*/95*. Every asterisk here is now cleared and GitGalaxy holds an outright
badge on Func Precision (the tie-break rule: a rate tie is broken by each tied party's absolute
count of validated-correct occurrences, not the raw claim count — GitGalaxy's 139 validated-real
functions beats ctags' 138 and tree-sitter's 123, all three otherwise tied at 100%).

### Where GitGalaxy wins outright

- **CPP-directive recall, cascading region (Fortran's own version of Claim 7).** 14 real
  subroutines across two WRF files (`bl_init`/`ra_init`/`landuse_init`/`mp_init`/`cu_init`/
  `shcu_init`/`CAM_INIT`/`z2sigma`/`fdob_init`/`fg_init`/`ALLOCATE_CAM_ARRAYS` in
  `module_physics_init.F`; `calc_p8w`/`calc_ts`/`write_ts` in `wrf_timeseries.F`) are correctly
  found by both GitGalaxy and ctags but invisible to tree-sitter-fortran, whose grammar cascades
  into `ERROR`/`preproc_*` nodes around the surrounding `#if`/`#endif` guards. Directly verified
  against `_find_blind_spot_ranges()`'s own parse-tree walk: every one of the 14 occurrences sits
  inside a real blind-spot span (e.g. one continuous `(2203, 4393)` span in `module_physics_init.F`
  covers 4 of them at once). This re-confirms the original accuracy-audit finding behind Claim 7 in
  `docs/why_gitgalaxy_beats_ast_here.md` via an independently-sourced comparison path (a raw
  per-file name diff, not the audit tool's own blind-spot promotion logic) — new evidence added to
  that claim, not a separate one.
- **PROGRAM-kind recall inside dead/conditional code.** `vint` (`module_initialize_real.F:5375`,
  inside `#ifdef VERT_UNIT`) and `foo` (`:7519`, inside `#if 0`) are both real, syntactically valid
  `PROGRAM name` declarations GitGalaxy finds and both other tools miss — tree-sitter via the same
  CPP-cascade mechanism above, ctags for two structurally different reasons (see below).

### Where the *other* tools have real, confirmed gaps

- **tree-sitter-fortran**: the CPP-cascade limitation above, already tracked as #1709 and Claim 7
  — not re-filed, just re-confirmed with fresh evidence.
- **ctags**: genuinely, unexplainedly fails to tag `vint` under any kind at all in
  `module_initialize_real.F`, despite tagging an isolated test file with identical
  `#ifdef`-wrapped `program vint` syntax correctly. Not a preprocessor-conditional-skip decision
  (confirmed: it also successfully tags `foo`, sitting inside an unconditionally-false `#if 0`, in
  the very same real file) — some other file-specific parser-state issue, not chased further for a
  single occurrence.

### Two real bugs found in this repo's own tooling, fixed the same pass

Not GitGalaxy, tree-sitter, or ctags defects — gaps in `tests/tools/ctags_reader.py`'s own
kind-to-signal mapping, the same bug *shape* as the already-documented cpp/csharp
`CTAGS_CLASS_KINDS` gaps in that file:

1. **`CTAGS_CLASS_KINDS['fortran']` was `{'t'}`** (derived types only) — missing `'m'` (module),
   `'i'` (interface), `'S'` (submodule), `'b'` (blockData), even though GitGalaxy's own
   `class_start` regex treats all five as class-shaped. ctags itself tags every real WRF
   `MODULE`/`INTERFACE` correctly (confirmed directly via `ctags -x --kinds-Fortran=m`); they were
   just invisible to this comparison. Fixed: now `{'t','m','i','S','b'}`. Effect: ctags' own
   Classes Found jumped from 3 to 11 — an 8-occurrence undercount in ctags' own reported numbers
   that had nothing to do with ctags' actual tagging ability.
2. **`CTAGS_FUNC_KINDS['fortran']` was `{'f','s'}`** (functions/subroutines only) — missing
   `'p'` (program), `'e'` (entry point), even though GitGalaxy's own `func_start` regex treats
   `PROGRAM`/`ENTRY` as equally function-shaped. Confirmed ctags tags `foo`
   (`module_initialize_real.F:7519`) as a real `'p'` kind via `ctags -x --kinds-Fortran=p`. Fixed:
   now `{'f','s','p','e'}`.

### A real GitGalaxy engine defect, found, fixed, and shipped in this same pass

`prism.py`'s `_strip_positional_comments` applied COBOL's column-7 indicator-area convention to
Fortran too (a shared `POSITIONAL_ANCHORS` set with no per-language distinction) — real fixed-form
Fortran 77 has no column-7 comment convention at all (only column 1; column 6 is a continuation
flag). A 3-space-indented `   FUNCTION foo(...)` puts the `C` of `FUNCTION` at column 7, tripping
the check and silently erasing the entire declaration line as a bogus comment before `func_start`
ever ran. Found two real, silently-dropped functions this way:
`module_configure.F:353`'s `in_use_for_config` and `module_domain.F:1693`'s `first_loc_integer`.
Fixed by gating the column-7 check to `cobol_mode` only. Full differential-scan protocol run
before shipping: fortran+cobol extraction gauntlet/strict tests (280 passed), `test_prism.py`/
`test_detector.py` (182 passed), ruff/mypy audits clean, `crucible_check.py` against the full
~80-repo corpus (134 diffs, 100% traced to this fix's direct effect on `fortran/wrf` plus expected
downstream ripple — global aggregates, topological coordinates, one `cobol` file's relative-risk
percentage shifting by 0.01 from a corpus-wide denominator), both golden masters re-blessed.

### A real GitGalaxy defect found, filed, not yet fixed

Unlike the C sweep (`docs/language_status/c.md` §9), this methodology *did* surface a genuine,
still-open GitGalaxy regex defect: **[#2077](https://github.com/squid-protocol/gitgalaxy/issues/2077)**
— the `args` regex's `\([^)]*\)` capture has no paren-depth awareness, so it stops at the first
literal `)` anywhere in a subroutine's parameter list — which, for `module_physics_init.F`'s
`phy_init` (a genuine 677-parameter subroutine, confirmed via `ctags --fields=+S`), is a `)`
closing an embedded `#if ( EM_CORE == 1 )` guard ~12 lines in, not the real signature close ~245
lines later. GitGalaxy reports 40 args, tree-sitter 39 (same #1709 cascade, applied to its own
parse of this signature), only ctags gets the true count right. This is a genuine 3-way split (no
two tools agree with each other at all), so no credit/debit ledger adjustment applies, and it
doesn't move the Args Found panel above (an existence count, not a per-function accuracy check —
`phy_init` is still correctly *found* by all three, just with three different parameter counts).
Left open rather than fixed inline: the real fix needs a depth-aware paren scanner (mirroring
dart's `_count_top_level_args` / cpp's `_cpp_class_has_body` pattern) over `detector.py`'s Mode A
args-derivation path, not a one-line regex tweak.
