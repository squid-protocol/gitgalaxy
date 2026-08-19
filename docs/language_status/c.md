# C — Structural Signature Coverage

Snapshot generated 2026-08-19 against `main`. Source: `LANGUAGE_DEFINITIONS["c"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_c.py` /
`test_c_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | C23 (ISO/IEC 9899:2024 — `constexpr`, `#embed`, `[[attributes]]`, `nullptr`, `typeof`) |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `standard_block` (`//` line comments, `/* */` block comments — C has no raw-string syntax, unlike C++'s `R"()"`) |
| Structural signature keys wired | 50 / 52 (2 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_c.py`) | 42 |
| Strict-signature tests (`test_c_strict.py`) | 86 |
| Total dedicated C test cases | 128 |

## 2. Identification surface

- **Extensions:** `.c .h .cl .inc .y .idc .cats .dts .dtsi` — standard sources/headers, OpenCL
  kernels, Yacc grammars, C-like ATS/scripting files, and Device Tree Source (`.dts`/`.dtsi`,
  hardware maps).
- **Exact filenames:** none — C has no extensionless canonical entry-point convention the way
  Python (`setup.py`) or PHP (`artisan`) do.
- **Discriminators:** `.c`, `Makefile`, `configure.ac`, `configure.in`, `configure`,
  `CMakeLists.txt`, `Kconfig` — ecosystem anchors used to disambiguate `.h`/`.inc` from other
  C-family or unrelated languages.
- **Shebangs:** `tcc`, `picoc`, `cscript` — the three real C interpreters/scripters that appear on
  a line-1 shebang.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` uses for C. Description is what C's *actual*
regex matches, not the generic cross-language definition.

**Topology & structure**
| Key | What it captures for C |
|---|---|
| `branch` | `if else switch case default for while do break continue goto`, plus `&& \|\| ?` |
| `args` | Parameter-list capture guarded by the "Nested Pointer Shield" (a 1-level nesting trick so function-pointer parameters like `void (*cb)(int)` don't need unbounded backtracking) and a typed-parameter-list requirement (C builtin primitives, `struct`/`enum`, PascalCase/typedef'd `_t`-suffixed names, or leading-underscore reserved identifiers like `_PyStackRef`) so it doesn't fire on bare control-flow keywords; #1209 wrapped the parenthesized span in its own capture group so the counter isolates just `(...)`; #1282/#1283 widened the whitelist after finding it only ever recognized builtin primitives, missing the overwhelming majority of real cpython signatures (`FILE *fp`, `PyThreadState *tstate`) |
| `structural_boundaries` | `struct union enum typedef return void restrict auto bool true false _BitInt alignas alignof` |
| `func_start` | Anchors function definitions: steps over up to 5 stacked `__attribute__((...))` lines (the "Compiler Attribute Shield"), up to 3 storage/linkage modifiers (`static inline extern _Noreturn __inline__ __forceinline constexpr`), an optional `struct/union/enum` prefix, a linear return type, and up to 5 macro-wrapper tokens between the return type and the name (`PyAPI_FUNC(int)`, `_Py_HOT_FUNCTION`); also supports legacy K&R-style parameter declarations between `)` and `{` (up to 15 semicolon-terminated lines) and the MS-DOS `BEGIN` macro as a brace substitute (DOOM/legacy-DOS-era code). Guarded by the "K&R Ambiguity Trap"/"Iron Wall" fix that instantly rejects control-flow keywords (`if for while switch return`, and `BEGIN` itself inside the K&R gap) rather than backtracking through whitespace permutations |
| `class_start` | Anchors `struct`/`union`/`enum`, optionally preceded by `typedef`; the tag name is optional so anonymous `typedef struct { ... } MyStruct;` matches. Deliberately also fires on bare variable declarations of an existing struct type (`struct foo_ops ops;`) — documented as intentional in `test_c_intentional_double_classification_sweep` so it can pair with the `_ops`-vtable-style `dependency_injection` heuristic below |

**Safety & risk**
| Key | What it captures for C |
|---|---|
| `safety` | `assert static_assert _Static_assert size_t snprintf strncat strncpy calloc nullptr unreachable ckd_add ckd_sub ckd_mul` |
| `safety_bypasses` | `strcpy strcat sprintf gets alloca`, plus raw C-style pointer casts (`(type *)ptr`) |
| `high_risk_execution` | `system popen execl execv fork longjmp setjmp` |
| `io` | `fopen fclose fread fwrite fscanf sscanf socket recv send open read write close stat fseek remove rename` |
| `api` | `extern`, `__declspec(dllexport)`, `__attribute__((visibility("default")))`, and non-`static` top-level variable/function declarations (linker-visible-by-default heuristic — same "public unless marked otherwise" logic C's linkage rules actually use) |
| `state_mutation` | Bare `=` (excludes `== != <= >=`), pointer-deref assignment (`*x = ...`, excludes `*const`), `++`/`--` |
| `dead_code` | Commented-out (`//` or `/*`) `if for while struct union enum void int return` |
| `doc` | `///`, `/**`, Doxygen `@param @return @brief @details` and `\param \return \brief \details` |
| `test` | `TEST TEST_F TEST_CASE CU_ASSERT RUN_TEST EXPECT_* ASSERT_*`, plus `assert(` |

**Architecture & domain sensors**
| Key | What it captures for C |
|---|---|
| `concurrency` | `thrd_create thrd_join mtx_lock pthread_create pthread_mutex_lock atomic_int _Atomic memory_order_* thread_local` |
| `ui_framework` | `GtkWidget CreateWindow MessageBox XOpenDisplay gtk_window_new Fl_Window initscr wprintw` |
| `closures` | `None` — see §4 |
| `globals` | Top-level (optionally `static`/`extern`) variable declaration with an initializer |
| `decorators` | C23 `[[attribute]]` bracket syntax |
| `generics` | `_Generic(...)` (C11 type-generic selection) |
| `comprehensions` | `None` — see §4 |
| `scientific` | `math.h tgmath.h complex.h dgemm sin cos tan exp log sqrt complex I _Float* __m*`, plus a `cblas_` prefix match (BLAS routines) |
| `reflection_metaprogramming` | Function-like macro definitions (`#define NAME(...)`) and `goto` |
| `import` | `#include`/`#embed` with `<>` or `""` delimiters |
| `_dependency_capture` | Extracts the exact include target path from the above |
| `ownership` | `@author \author Author: Created by: Copyright` |

**Specialized subsystems**
| Key | What it captures for C |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`, `[spec ...]`, `[audit ...]` traceability tags, bounded to 300 chars to avoid the adjacent-unbounded-quantifier ReDoS shape (recurring bug class, same family fixed elsewhere via #713) |
| `ssr_boundaries` | `FCGI_Accept khttp_parse MHD_start_daemon facil.io` |
| `events` | `epoll_wait epoll_ctl kqueue kevent select poll libev libuv` |
| `dependency_injection` | `plugin_register vtable`, and `struct *_ops` (vtable-suffix convention) |
| `macros` | `#define #undef #if #elif #else #endif #pragma #warning #error` |
| `pointers` | `->`, `uintptr_t intptr_t ptrdiff_t size_t`, address-of `&x` and dereference `*x` in argument/assignment position |
| `memory_alloc` | `malloc calloc realloc free aligned_alloc mmap alloca` |
| `inline_asm` | `__asm__`/`asm`/`__asm` (with optional `volatile`/`__volatile__`), parenthesized or brace form |

**Resource management & stability**
| Key | What it captures for C |
|---|---|
| `telemetry` | `syslog openlog log_info log_error log_warn log_debug vsyslog` |
| `debug_prints` | `printf fprintf vprintf puts putchar perror` |
| `explicit_casts` | `(int\|float\|double\|char\|bool\|long\|short\|unsigned\|signed\|void [*]*) identifier` |
| `panics_and_aborts` | `abort exit _Exit quick_exit`, and `return -1` |
| `thread_sleeps` | `sleep usleep nanosleep thrd_sleep` |
| `bitwise_ops` | `<< >> ^ ~ <<= >>= &= \|= ^=` |
| `sync_locks` | `mtx_lock mtx_unlock pthread_mutex_lock atomic_flag_test_and_set atomic_store` |
| `immutability_locks` | `const constexpr alignas restrict` |
| `cleanup` | `free( fclose( close( munmap( destroy( shutdown(` |
| `encapsulation` | Leading `static` at line start — translation-unit-private linkage, C's only real privacy signal |
| `listeners` | `on_event handler callback signal( sigaction(` |
| `test_skip` | `IGNORE_TEST test.skip`, `mock(`, `fake(` |

**Hybrid domain sensors (C specifics)**
| Key | What it captures for C |
|---|---|
| `serialization_parsing` | `cJSON_Parse json_loads xmlReadMemory xmlParseFile jansson` |
| `regex_execution` | `regcomp regexec regfree` |
| `time_date_logic` | `time_t clock_gettime gettimeofday localtime_r? strftime` |
| `ipc_rpc_bridges` | `fork pipe shmget shmat mmap socket bind listen accept` |

Several of the pairs above are **deliberate double-classifications**, not collisions — e.g.
`free(p)` fires both `cleanup` and `memory_alloc`; `mmap(...)` fires both `memory_alloc` and
`ipc_rpc_bridges`; `pthread_mutex_lock(&m)` fires both `concurrency` and `sync_locks`; `restrict`
and `alignas(...)` fire both `structural_boundaries` and `immutability_locks`. All ten pairs are
enumerated and asserted in `test_c_intentional_double_classification_sweep`
(`tests/extraction/languages/test_c_strict.py`).

## 4. What GitGalaxy explicitly does not track

Two keys are hard-set to `None` in C's `rules` dict (Rule 4 of the engine's generation rules:
explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`closures`** — strict C23 has no native closure construct (GCC/Clang "nested functions" and
  Apple "blocks" are non-standard compiler extensions, not part of the target C23 standard).
- **`comprehensions`** — C has no list/set/dict comprehension or generator-expression syntax at
  all (no inline reason comment in source for this one; the omission is self-evident given the
  language has never had this construct in any standard revision).

## 5. Known limitations (accepted, not fixed)

One gap is deliberately documented rather than fixed, via a `known_limitation`-named test in
`test_c.py`:

1. **`func_start` matches function-shaped text on undecorated block-comment continuation lines.**
   The rule has no comment/string awareness at the point it anchors `^[ \t]*` — a block comment
   like `/*\nint TargetFunc() {\n*/` with no leading `*` continuation marker (a common real style
   for commenting out code) still matches at true line start. This is a variant of recurring bug
   class 3 (`tests/extraction/how_to_harden_extraction.md`) manifesting via **comments** rather
   than **string literals**. A companion test in the same file
   (`test_c_func_start_string_literal_concatenation_does_not_false_positive`) confirms the
   string-literal variant of this bug class does *not* reproduce for C: C has no raw-string syntax
   (unlike C++'s `R"()"`), so every string-literal content line necessarily starts with a literal
   `"` character, which blocks `^[ \t]*` from ever reaching function-shaped text before it. The
   real fix (matching against shielded code) lives in `detector.py`'s `_slice_by_braces` and is
   currently gated to javascript/typescript only — not fixed here, tracked as future follow-up
   work in the epic.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 42 tests in
  `tests/extraction/languages/test_c.py` — valid/invalid/pathological cases per rule, plus the
  known-limitation test and its string-literal-concatenation companion above. Fully migrated to
  the per-language file (epic #813, issue #822) — nothing left for `c` in the old monolithic
  gauntlet files, and `class_start` had no prior test entry at all before this migration.
- **Strict signature suite** (all other wired keys): 86 tests in
  `tests/extraction/languages/test_c_strict.py` (epic #518, issue #773) — positive/negative match
  coverage per signature, a ReDoS-immunity sweep, K&R-ambiguity and pointer-ambiguity regression
  tests, `__declspec`/`__attribute__` visibility-boundary regression, `cblas_` prefix boundary
  regression, `test_skip` empty-call boundary regression, `spec_exposure` ReDoS regression,
  `explicit_casts`-vs-`pointers` and `func_start`-vs-macros no-false-collision tests, and the
  10-pair intentional-double-classification sweep described in §3.

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#773](https://github.com/squid-protocol/gitgalaxy/issues/773) — Strict parsing tests for C
  structural signatures (epic #518).
- [#822](https://github.com/squid-protocol/gitgalaxy/issues/822) — Extraction hardening for C
  (epic #813).

**Real bugs found and fixed (C-specific):**
- [#1754](https://github.com/squid-protocol/gitgalaxy/issues/1754) (CLOSED, merged
  [#1794](https://github.com/squid-protocol/gitgalaxy/pull/1794)) — `func_start` missed
  macro-wrapped parameter names (`Py_UNUSED(consts)`), function-pointer arguments, and
  macro-decorated return types/annotations. Fixed via macro shielding and nested-parenthesis
  tracking; also cleared tree-sitter "macro hallucination" false positives from the accuracy
  baseline. Newly recovered real functions on cpython included `_PyEval_EvalFrameDefault` and
  `PlinkPrint`.
- [#1282](https://github.com/squid-protocol/gitgalaxy/issues/1282) (CLOSED, merged
  [#1283](https://github.com/squid-protocol/gitgalaxy/pull/1283)) — the `args` regex's
  typed-parameter-list whitelist only ever recognized C's built-in primitive keywords, so a
  parameter typed with a real-world custom typedef/struct name (`FILE *fp`, `PyThreadState
  *tstate`) never matched at all — `args_count` silently fell back to 0 for functions with real,
  nonzero arity. Confirmed against cpython's `ceval.c` that this is the overwhelming majority
  shape of real C signatures, not an edge case.
- [#1646](https://github.com/squid-protocol/gitgalaxy/issues/1646) (CLOSED, merged
  [#1672](https://github.com/squid-protocol/gitgalaxy/pull/1672), superseding an earlier attempt
  [#1671](https://github.com/squid-protocol/gitgalaxy/pull/1671) that was closed unmerged) — the
  `args` regex's unbounded `.search()` wasn't bounded to the signature span, so on at least one
  real cpython function (`_PyCompile_MaybeAddStaticAttributeToClass`) it skipped the real
  `(compiler *c, expr_ty e)` signature entirely and matched a `RETURN_IF_ERROR(...)` call several
  lines into the function body instead — previously masked by an unrelated depth-counting
  coincidence in the zig-specific fix #1645. Two-part fix: bounded the args search to the
  signature span only (generalizing objc's `objc_args_sig_end` mechanism from #1335 into a
  general `args_sig_end` for `c`), and widened the type-alternation to accept a lowercase
  custom-typedef-plus-pointer/identifier shape as a parameter's first token.

**Cross-language fixes that touched C along the way:**
- [#1816](https://github.com/squid-protocol/gitgalaxy/pull/1816) (MERGED) — a same-day
  multi-language parsing pass (TypeScript/JavaScript/Go/Rust/C); C's piece hardened the K&R
  parameter gap with the "Iron Wall" fix, forcing instant regex failure on control-flow keywords
  (`BEGIN if while`) inside the K&R gap instead of backtracking through whitespace permutations
  (the original 34-second ReDoS hang documented in `func_start`'s own header comment).

**Measurement-tool-only findings (not GitGalaxy engine defects):**
- [#1265](https://github.com/squid-protocol/gitgalaxy/issues/1265) (CLOSED, diagnosis landed in
  [#1280](https://github.com/squid-protocol/gitgalaxy/pull/1280)) — the tree-sitter accuracy
  measurement tool reported `real_functions=0` across 31 real C corpus files, which looked
  implausible. Root cause: `tree_sitter_accuracy_audit.py`'s `_get_node_name()` reads a node's
  name via `child_by_field_name("name")`, but tree-sitter-c's `function_definition` node has no
  `name` field at all — the identifier sits two levels deep behind a `function_declarator` (and an
  extra `pointer_declarator` for pointer-returning functions). Confirmed as a measurement-tool
  ground-truth gap, not a GitGalaxy regression; this is the same underlying tree-sitter-C-grammar
  shape independently documented for `args`-counting in
  [#1282](https://github.com/squid-protocol/gitgalaxy/issues/1282) above.
- [#1641](https://github.com/squid-protocol/gitgalaxy/issues/1641) (CLOSED, merged
  [#1643](https://github.com/squid-protocol/gitgalaxy/pull/1643)) — the same measurement tool's
  `class_precision` for C looked artificially low (78.2%); all 17 "extra classes" it counted were
  the exact same literal string `Anonymous_Class` — GitGalaxy's own synthetic placeholder name for
  an anonymous `typedef struct {...}` — being compared against tree-sitter's real class names
  instead of being excluded the same way the tool already excluded synthetic function names.

Search performed via `gh issue list --search 'in:title "Extraction hardening: c"'` /
`'in:title "Strict parsing tests: \`c\`"'` / `'in:title c'` (2026-08-19), plus direct checks of
issues #1754/#1794/#1816/#1826/#1828 per the skill's own pointer list — #1826 was excluded (a
routine auto-generated tree-sitter-accuracy-history CSV update, not a C-specific change) and #1828
was excluded (its title mentions "C++, PHP, and Zig" — `cpp`, not `c`).

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Four repos from the `v2.4.7` batch, chosen for a size/era spread — a large adversarial kernel, a
small 1990s-era legacy codebase, a famous mid-size single-purpose library, and a well-known
small-to-mid networking library:

- **[`linux`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/linux/linux_galaxy_llm.md)**
  — the Linux kernel (`torvalds/linux.git`), the largest and most adversarial C corpus available:
  decades of eras, heavy macro/attribute stacking, every K&R-to-C23 idiom the engine's `func_start`
  regex has hardening comments for. Scanned in 387.42s.
- **[`original_doom`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/original_doom/original_doom_galaxy_llm.md)**
  — id Software's original 1993 DOOM source (`id-Software/DOOM.git`). A small, genuinely
  legacy-era C codebase, directly relevant to the MS-DOS `BEGIN`-macro and K&R parameter-gap
  handling documented inline in `func_start`'s own regex comments. Scanned in 0.59s.
- **[`sqlite`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/sqlite/sqlite_galaxy_llm.md)**
  — SQLite's own reference implementation (`sqlite/sqlite.git`), a famous mid-size single-purpose
  C library; its generated parser `lemon.c` is one of the corpus files behind the `class_start`
  measurement-tool finding in #1641 above. Scanned in 5.62s.
- **[`curl`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/curl/curl_galaxy_llm.md)**
  — curl's own C implementation (`curl/curl`), a well-known small-to-mid networking library;
  a useful lower-noise contrast point against the kernel and legacy-game extremes above. Scanned
  in 3.33s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

Note: the `v2.4.7` batch also contains a repo named `redis`, but its scan target path
(`pypi_top_200/redis`) and 0.32s scan duration confirm it's the Python `redis` client package, not
the actual C `redis` server — excluded here as not a genuine C data point.

## 9. Tri-comparison: GitGalaxy vs. tree-sitter vs. ctags

This section is a different shape from python.md's/javascript.md's §9 on purpose: those diff
GitGalaxy against one privileged ground-truth parser (`ast`, `tree-sitter-language-pack`). C has
two independent, non-privileged comparison tools available (`tree-sitter-c` and `universal-ctags`)
and neither is treated as ground truth — see
`tests/tools/tri_comparison_reconcile.py`'s own module docstring for why (multiple confirmed cases
below show GitGalaxy right when tree-sitter is wrong, and vice versa). Every discrepancy the three
tools produced against each other was investigated by reading real source
(`docs/self_scan/how_to_investigate_a_discrepancy.md`'s process), not assumed — the full record is
`docs/self_scan/tri_comparison_ledger.json`, filterable to `"language": "c"`.

**Result: 11 of 11 discrepancy shapes (766 individual occurrences) resolved, zero confirmed
GitGalaxy engine defects.** Every disagreement either resolved in GitGalaxy's favor, or turned out
to be a bug in this repo's own comparison tooling (found and fixed as part of the same pass) or a
known tree-sitter-c/ctags limitation — never GitGalaxy's regex engine itself. Current measured
numbers (`tests/tools/tri_comparison_chart.py --languages c`, `language-crucible/data/c/` —
cpython, doom, sqlite, micropython, and more):

| Signal | GitGalaxy | tree-sitter | ctags | Read as |
|---|---|---|---|---|
| Functions found (of 1,814 total claimed by any tool) | 1,730 | 1,790 | 1,733 | tree-sitter's higher count is mostly noise, not real recall — see precision row |
| Function precision (of what each tool claimed, how much corroborates) | **99.8%** (1726/1730) | 95.9% (1716/1790) | 99.6% (1726/1733) | GitGalaxy has the highest precision of the three |
| Class recall/precision | **100%** (61/61) | 100% (61/61) | 100% (61/61) | fully reconciled after this pass's fixes — see below |
| Args exact-match | **100%** (1710/1710) | 99.9% (1709/1710) | 100% (1710/1710) | tied for best |

### Where GitGalaxy wins outright

- **Macro-body parsing.** GitGalaxy's regex has no concept of "inside a macro" and simply parses
  whatever function-shaped text it finds — which turns out to be a real advantage. A bare
  `SLOT0`/`SLOT1`/`RICHCMP_WRAPPER(...)`-style macro-invocation line (CPython's `typeobject.c`
  boilerplate generators, no trailing semicolon, not valid freestanding C without macro expansion)
  locally confuses both tree-sitter's and ctags' parse of the single real function immediately
  following it — GitGalaxy has no such adjacency sensitivity and finds all of them (confirmed at 4
  sites: `slot_mp_ass_subscript`, `slot_nb_inplace_power`, `slot_tp_repr`, `slot_tp_hash`). New
  evidence for `docs/why_gitgalaxy_beats_ast_here.md`'s Claim 3 (parse-error cascade).
- **CPP-directive immunity.** tree-sitter-c has no preprocessor model at all and loses real
  functions at 3 distinct trigger shapes GitGalaxy is entirely unaffected by: an `#if`/`#else`
  pair splitting a single `if` condition mid-body, an `#if`/`#endif` wrapping only the `static`
  storage-class specifier (separating it from the rest of the signature), and bare
  un-semicoloned diagnostic-pragma macros the grammar can't cleanly recover from (13 occurrences
  total, `cpython/ceval.c`, `cpython/object.c`, `micropython/compile.c`). New evidence for Claim 7
  (CPP-directive recall loss, previously only cited for Fortran) — C's version is local (one
  function lost per trigger), not Fortran's cascading whole-section loss.
- **Dead-code and macro-hallucination immunity (precision).** tree-sitter hallucinates functions
  from text that merely *looks* structural: the bare keyword `if` (a preprocessor-guarded
  `#if`/`else if` sequence desyncs the parse), `PyMethodDef` array-initializer macro names
  (`DICT___REVERSED___METHODDEF`), and genuinely well-formed functions sitting entirely inside
  `#if 0 ... #endif` dead-code blocks (`_PyObject_ManagedDictValidityCheck`,
  `tos_char`/`print_stack`/`print_stacks`) — 71 of tree-sitter's raw `extra_functions` on this
  corpus trace to exactly this (Claim 8). GitGalaxy's own `extra_functions` on the same corpus: 9,
  all genuine regex false positives, none of this shape.

### Where the *other* tools have real, documented gaps (not GitGalaxy's problem to fix)

- ctags misreads the same macro-invocation lines as GitGalaxy correctly skips, tagging
  `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/`SLOT1BINFULL` themselves as function names (7 occurrences) —
  and separately fails to tag the real function immediately following one (3 more, shared root
  cause with the tree-sitter Claim 3 instance above). Documented in `tests/tools/ctags_reader.py`,
  not fixed (would require a curated macro-name list, the same kind of ground-truth judgment call
  this tooling deliberately keeps out of the raw readers).
- ctags' C parser has no kind for `union` at all (confirmed via `ctags --list-kinds-full=C`) — a
  real `union Foo { ... }` (Rust-adjacent, but real, common C, e.g. wasmtime's register-union
  types) is structurally invisible to it.

### Two real bugs found in this repo's own tooling, fixed the same session

Not GitGalaxy, tree-sitter, or ctags defects — bugs in `tests/tools/ctags_reader.py`'s own parsing
of ctags' output, found while investigating why ctags appeared to miss things it actually handles
fine:

1. **Tab-splitting bug.** Old-style C source using literal tab characters for column alignment
   (`byte*⇥I_AllocLow(int length)`, confirmed in `doom/i_system.c`) gets that tab echoed verbatim
   into ctags' own tag-file address field; `read_ctags_symbols`' blind `line.split("\t")` then
   misreads a fragment of the *source line* as the kind field and silently drops the symbol.
   Reproduced byte-for-byte by running ctags with the exact flags this code uses. Fixed: parse now
   locates the tag-file format's guaranteed `;"` address-terminator instead of blind-splitting.
2. **`CTAGS_CLASS_KINDS["c"]` was struct-only.** GitGalaxy's own C `class_start` regex matches
   `struct|union|enum`, but the ctags kind map only ever included `struct` — silently dropping
   every real enum/union from the comparison for no reason (ctags itself parses them fine). Fixed:
   now `{"s", "g", "u"}`. The same gap was found unfixed in `cpp`'s equivalent map
   ([#1877](https://github.com/squid-protocol/gitgalaxy/issues/1877), filed not fixed — C++'s
   scoped-vs-unscoped `enum class` distinction needs its own verification before assuming the same
   fix shape applies).

### Confirmed GitGalaxy engine bugs found for C: zero

Contrast with `rust`, where the same sweep methodology found and filed two real GitGalaxy
`detector.py` bugs
([#1872](https://github.com/squid-protocol/gitgalaxy/issues/1872) — a lifetime-tick handling
defect in argument counting). For C, every one of the 766 investigated occurrences resolved
without implicating GitGalaxy's own regex engine — the closest thing to a caveat is the tab-
splitting and ctags-kind-mapping bugs above, both in this repo's *test tooling*, not the shipped
`gitgalaxy` package.

**Full investigation record:** `docs/self_scan/tri_comparison_ledger.json` (filter to
`"language": "c"`), rendered human-readable at
`docs/self_scan/tri_comparison_points_of_interest.md`.
