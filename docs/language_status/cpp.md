# C++ — Structural Signature Coverage

Snapshot generated 2026-08-21 against `main`. Source: `LANGUAGE_DEFINITIONS["cpp"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_cpp.py` /
`test_cpp_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below. This doc covers sections 1-8 only (documentation, not engine
changes) — a §9 measured-accuracy section using this sweep's own tri-comparison data is being
appended separately by the main session.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | C++23 (Modules, Concepts, Coroutines, Ranges, `std::print`) |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `standard_block` (`//` line comments + `/* */` block comments, non-nesting) |
| Structural signature keys wired | 52 / 52 (0 explicit `None` — see §4 for what's absent instead) |
| Extraction-gauntlet tests (`test_cpp.py`) | 46 |
| Strict-signature tests (`test_cpp_strict.py`) | 76 |
| Total dedicated C++ test cases | 122 |

Note on the "52/52" figure: cpp carries every key in the universal 52-key baseline schema
(`how_to_add_a_language.md`'s OUTPUT SCHEMA), all wired to a real regex — none set to explicit
`None`. That's different from `hardcoded_secrets` (present in the schema template but only
actually wired for a small handful of languages, e.g. `solidity`/`yaml`) and the opt-in AI/ML
extension pack (`llm_api`/`dl_frameworks`/etc., currently `python`/`javascript`/`typescript`
only) — cpp simply doesn't carry either, which is correct per the extension-pack doc's own
opt-in rule, not a gap. See §4.

## 2. Identification surface

- **Extensions:** `.cpp .cc .cxx .c++ .hpp .hh .hxx .h++ .tpp .inc .inl .ipp .cp .C .H` — every
  common source/header suffix across GNU, MSVC, and legacy UNIX-casing conventions, plus
  template-implementation (`.tpp`/`.ipp`) and generic-include (`.inc`/`.inl`) suffixes.
- **Exact filenames:** none.
- **Discriminators:** `.cpp`, `.cc`, `.cxx`, `CMakeLists.txt`, `conanfile.txt`, `vcpkg.json`,
  `Makefile`, `BUILD.bazel`, `WORKSPACE` — build-system/package-manifest anchors used to
  disambiguate ambiguous shared extensions (`.h`, `.inc`) from plain `c`.
- **Shebangs:** `cling`, `cint` — C++ interpreter/REPL front-ends.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py`/`how_to_add_a_language.md` use. Description
is what C++'s *actual* regex matches, not the generic cross-language definition.

**Topology & structure**
| Key | What it captures for C++ |
|---|---|
| `branch` | `if else switch case default for while do catch break continue goto co_yield co_await`, `&& \|\| ?` — includes C++20 coroutine jumps, excludes exceptions (those live in `panics_and_aborts`) |
| `args` | Parameter blocks of free functions/methods/lambdas, including class-qualified operator names (`TargetClass::operator=`), bounded 2-level nested template args, and out-of-line definitions; the parameter-list span is its own capture group (#1209) so the arg counter isolates just `(...)`, not the whole name+template+params match |
| `structural_boundaries` | `namespace using class struct enum union template typename concept requires auto return void inline virtual explicit friend module export import typedef` |
| `func_start` | A ten-stage pipeline (attributes → linkage/storage modifiers → return type with bounded 2-level template nesting and pointer/reference handling on either side of whitespace → operator/destructor/qualified-name capture → parameter block via 1-level nesting trick → trailing `const`/`noexcept`/`override`/trailing-return-type → K&R/constructor-initializer-list gap → opening `{`); explicitly rejects control-flow keywords (`if`, `for`, `if constexpr`, etc.) as false function names and shields against crossing into `#`-preprocessor lines mid-signature |
| `class_start` | `class struct union enum class enum struct`, optional `export`/template prefix (2-level nested template default-arg tolerant), optional `[[attribute]]`/`__attribute__` step-over, single capture group for the entity name only — deliberately does not capture the base-class/interface list (§5) |

**Safety & risk**
| Key | What it captures for C++ |
|---|---|
| `safety` | `try catch finally`, `std::unique_ptr/shared_ptr/weak_ptr`, `override final noexcept static_assert assert`, `std::optional/expected/span/variant`, `std::lock_guard`, `std::atomic` |
| `safety_bypasses` | `std::any`, `void*`/`void *` (any spacing), `catch (...)` |
| `high_risk_execution` | `system memcpy memset abort exit std::terminate longjmp setjmp` |
| `io` | `std::fstream/ifstream/ofstream/filesystem`, `fopen fclose fread fwrite`, `socket recv send`, `asio::`, `curl_easy_perform`, `std::cin` |
| `api` | `export module` / `export import` / `export class`, `public:`, `__declspec(dllexport)`, `__attribute__((visibility("default")))`, or a bare line-leading `export` not followed by `module` |
| `state_mutation` | `mutable std::move std::exchange std::swap std::atomic`, bare assignment `=` (excluding `==`/`!=`/`<=`/`>=`), reference-bind `&` (excluding `& const`), `++ --`, compound assignment operators |
| `dead_code` | `//` or `/*` immediately followed by `if for while auto class struct std::cout std::print printf void int return` — covers both comment styles (a `standard_block` requirement) |
| `doc` | `///`, `/**`, Doxygen `@param/@return/@brief/@details/@tparam` and their `\param`-style backslash equivalents |
| `test` | `TEST TEST_F TEST_CASE SECTION REQUIRE CHECK EXPECT_* ASSERT_*`, `Catch:: GTest` — anchored to GTest/Catch2 macro shapes to avoid prose collisions |

**Architecture & domain sensors**
| Key | What it captures for C++ |
|---|---|
| `concurrency` | `std::thread/jthread/mutex/future/promise/async/latch/barrier/condition_variable/semaphore`, `co_await`, `std::coroutine_handle` |
| `ui_framework` | `Q_OBJECT QWidget wxFrame ImGui:: Fl_Window`, `slots:`, `signals:` |
| `closures` | Lambda capture-list `[...]` through an optional template-arg list, optional parameter list, optional `mutable`/`constexpr`/`consteval`/`noexcept`, optional trailing return type, up to the opening `{` |
| `globals` | `extern static thread_local inline constexpr` (with `static` excluding `static_assert`), or a line-leading `static`/`extern` typed declaration with assignment |
| `decorators` | `[[attribute]]`-style C++11/20 attribute annotations |
| `generics` | `template<...>`, `concept`, `requires` |
| `comprehensions` | `std::ranges:: std::views:: views:: std::transform/accumulate/reduce/for_each/filter`, or `\| std::views::` pipeline syntax |
| `scientific` | `std::cmath/complex/linalg/mdspan`, `Eigen:: blaze::`, `std::simd`, `__m128/__m256/__m512`, `std::numbers::` |
| `reflection_metaprogramming` | `if constexpr`, `if consteval`, `std::enable_if/is_same/any_cast/bit_cast`, `decltype`, `sizeof...`, `#define <identifier>` |
| `import` | Line-leading `#include <...>`/`#include "..."`, `import name;`, `export import name;` |
| `_dependency_capture` | Extracts the exact include path or module name from the four import forms above |
| `ownership` | `@author`/`\author`/`Author:`/`Created by:`/`Copyright` (case-insensitive, captures the rest of the line) |

**Specialized subsystems**
| Key | What it captures for C++ |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`, `[spec ...]`, `[audit ...]` traceability tags (bounded quantifiers, ReDoS-hardened per #713) |
| `ssr_boundaries` | `FCGI_Accept render_template Inja:: ctemplate::` |
| `events` | `emit signal slot notify publish subscribe boost::signals2` |
| `dependency_injection` | `boost.di fruit:: Inject IServiceCollection` |
| `macros` | Line-leading `#define/undef/if/elif/else/endif/pragma/warning/error` |
| `pointers` | `->`, `uintptr_t intptr_t ptrdiff_t size_t`, lookbehind-guarded `&var`/`*var` dereference forms that exclude ordinary multiplication/logical-AND |
| `memory_alloc` | `new malloc calloc realloc aligned_alloc mmap alloca` |
| `inline_asm` | `__asm__`/`asm`/`__asm` followed by `(` (optionally with `volatile`/`__volatile__`) or by `{` |

**Resource management & stability**
| Key | What it captures for C++ |
|---|---|
| `telemetry` | `log/logger/LOGGER/spdlog/glog/syslog` `.info/.error/.warn/.debug/.trace` |
| `debug_prints` | `std::cout/cerr/clog printf fprintf vprintf puts putchar std::print std::println` |
| `explicit_casts` | `static_cast dynamic_cast reinterpret_cast const_cast bit_cast`, functional-cast-style single-identifier templates followed by `(` (e.g. `narrow_cast<int>(x)`, deliberately excluding plain declarations like `std::vector<int>`), and C-style casts including pointer casts (`(int*)ptr`) |
| `panics_and_aborts` | `throw abort exit _Exit quick_exit std::terminate longjmp` |
| `thread_sleeps` | `sleep delay usleep nanosleep std::this_thread::sleep_for` |
| `bitwise_ops` | `^`, `~` (not preceded by `=`/`!`), `<<= >>= &= \|= ^=` — bare `<< >>` deliberately excluded to avoid `std::cout`/`std::cin` stream-operator false positives |
| `sync_locks` | `mutex lock synchronized Semaphore std::lock_guard/scoped_lock/unique_lock mtx_lock` (case-insensitive) |
| `immutability_locks` | `const constexpr consteval constinit final readonly Immutable` |
| `cleanup` | `delete free close fclose dispose shutdown std::destroy reset` immediately followed by `(` |
| `encapsulation` | `private: protected: internal:` |
| `listeners` | `on addEventListener subscribe connect handler callback` |
| `test_skip` | `GTEST_SKIP test.skip it.skip`, `mock(`, `fake(` |

**Hybrid domain sensors**
| Key | What it captures for C++ |
|---|---|
| `serialization_parsing` | `nlohmann::json rapidjson boost::archive ParseFromString SerializeToString` |
| `regex_execution` | `std::regex std::regex_match/search/replace` |
| `time_date_logic` | `std::chrono::system_clock/steady_clock/duration`, `std::time_t`, `std::localtime` |
| `ipc_rpc_bridges` | `boost::interprocess mmap shm_open pipe fork grpc::ServerBuilder` |

## 4. What GitGalaxy explicitly does not track

Unlike many languages in this repo, cpp has **zero keys explicitly set to `None`** — every key in
the universal 52-key baseline schema is wired to a real regex. What cpp *doesn't* carry is instead
simply absent from its `rules` dict entirely (no key, no comment explaining why), which is a
different and normal situation for two categories of key:

- **`hardcoded_secrets`** — present in the schema template's OUTPUT SCHEMA comment block, but in
  practice only actually wired for a small number of languages (`solidity`, `yaml`, and a couple
  others) across the whole registry — not a universal-baseline expectation despite appearing in
  the template. cpp not having it is consistent with the vast majority of other languages, not a
  cpp-specific gap.
- **The AI/ML extension pack** (`llm_api`, `llm_orchestrator`, `llm_vector_store`, `ml_traditional`,
  `dl_frameworks`, `hardware_bridge`, `cryptography`, `rce_funnel`, `exfiltration_camouflage`,
  `memory_scraping`, `lazy_evaluation`, `vectorized_math`, `_named_token_capture`) — explicitly
  opt-in per `how_to_add_a_language.md`'s "Optional: AI/ML & Literate-Programming Extension Pack"
  section, currently carried only by `python`/`javascript`/`typescript`. C++ is a plausible host
  for some of this (e.g. it does have ML/scientific-computing use), but no one has opted it in yet
  — not evaluated in this pass as a gap since it's out of scope for a documentation-only sweep.

## 5. Known limitations (accepted, not fixed)

Two gaps are deliberately documented rather than fixed, via `known_limitation`-named tests in
`test_cpp.py`:

1. **`func_start` has no string/comment awareness of its own.** Function-shaped text inside a raw
   string literal (`R"(...)"`, commonly used to embed SQL/regex/JSON) that happens to land at true
   line start still matches as if it were a real function. This is the same architectural gap
   already confirmed for JavaScript/TypeScript template literals, Java text blocks, Go raw
   strings, Rust raw strings, and C# verbatim strings (recurring bug class 3 in
   `tests/extraction/how_to_harden_extraction.md`) — cpp is a sixth language hitting it. cpp
   currently routes through Mode B (`_slice_by_braces`), which is gated to `javascript`/
   `typescript` only for the mitigation; not fixed here, tracked as future work in the epic.
2. **`class_start` never captures the base-class/interface list.** `struct Foo : public Base {`
   only captures `"Foo"` — nothing for `"Base"`. This is the original, pre-existing design (only
   one capture group exists at all), unlike `java`/`csharp`/`python`'s `class_start` where a
   second capture group for the base list already exists. Not treated as a gap: `class_start`'s
   contract here is anchoring the START position, and the base-list was never part of it.

**Six additional real engine defects** were found in a companion tri-comparison-ledger sweep on
2026-08-21 and filed the same day. Five are still open as of this doc's snapshot; one
(**#2011**) was fixed in a follow-up commit in the same PR, once its downstream effect surfaced
as a CI regression (see §9 for the full story) rather than being left filed-but-unfixed:

- **[#2009](https://github.com/squid-protocol/gitgalaxy/issues/2009)** — `func_start` recall gap
  on functions whose constructor-initializer-list span exceeds the rule's bounded length cap. Open.
- **[#2010](https://github.com/squid-protocol/gitgalaxy/issues/2010)** — `func_start` recall gap
  on template-return-type conversion operators. Open.
- **[#2011](https://github.com/squid-protocol/gitgalaxy/issues/2011)** — `class_start` false
  positive on forward declarations (`class Foo;`) that never actually define the class body.
  **Fixed** — `_cpp_class_has_body` in `detector.py` now does a depth-aware scan past an optional
  inheritance-list clause (so C++ multiple inheritance and templated base classes aren't falsely
  excluded the way a naive copy of C's own flat lookahead would be) before checking for a real
  `{`. Verified via 11 hand-built regression cases, the full extraction gauntlet, and
  `crucible_check.py` against the full corpus.
- **[#2012](https://github.com/squid-protocol/gitgalaxy/issues/2012)** — `args` counting bugs
  (parameter-count miscounts on specific real-world signature shapes). Open.
- **[#2013](https://github.com/squid-protocol/gitgalaxy/issues/2013)** — `func_start` false
  positive on a lambda defined inside a constructor's initializer list. Open.
- **[#2014](https://github.com/squid-protocol/gitgalaxy/issues/2014)** — a tree-sitter tooling
  defect (not a GitGalaxy engine defect), noted here for completeness since it surfaced in the same
  cpp-focused sweep. Open (tooling-only, no production blast radius).

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 46 tests in
  `tests/extraction/languages/test_cpp.py` — valid/invalid/pathological cases per rule, plus the
  ReDoS-immunity sweep and the two known-limitation tests above. Fully migrated to the
  per-language file (epic #813, issue #821) — cpp's entries were removed from the four old
  monolithic gauntlet files (`test_function_extraction_strict.py` etc.) when this file was added,
  so nothing is left behind there for cpp.
- **Strict signature suite** (all other wired keys): 76 tests in
  `tests/extraction/languages/test_cpp_strict.py` — positive/negative match, cross-rule ambiguity
  (`explicit_casts` vs. `pointers`, `bitwise_ops` vs. `std::cout`, `func_start` vs. macros, an
  intentional-double-classification sweep), ReDoS-immunity checks, and per-signature deep-case
  batteries for `branch`/`args`/`func_start`/`class_start`/`structural_boundaries` (epic #518,
  issue #774).

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#774](https://github.com/squid-protocol/gitgalaxy/issues/774) (PR
  [#787](https://github.com/squid-protocol/gitgalaxy/pull/787)) — Strict parsing tests for C++
  structural signatures (epic #518): built the full per-signature positive/negative/ambiguity/
  ReDoS template cpp had never received, folding in the handful of pre-existing scattered
  regression tests (`test_cpp_macro_multiline_spiral`, the C++ half of
  `test_thermodynamic_operator_collisions`) rather than duplicating them.
- [#821](https://github.com/squid-protocol/gitgalaxy/issues/821) (PR
  [#882](https://github.com/squid-protocol/gitgalaxy/pull/882)) — Extraction hardening for C++
  (epic #813): built the valid/invalid/pathological gauntlet for `func_start`/`args`/
  `class_start`/`_dependency_capture`, migrated off the old monolithic dict files.

**Real bugs found and fixed along the way:**
- [#1263](https://github.com/squid-protocol/gitgalaxy/issues/1263) (PR
  [#1281](https://github.com/squid-protocol/gitgalaxy/pull/1281)) — `func_start` missed
  pointer/reference return types in the common `Type *name()`/`Type * name()` form (only the
  glued `Type* name()` form worked), and mishandled operator/destructor names; also the origin of
  the class-qualified out-of-line operator support (`TargetClass::operator=`) now present in both
  `func_start` and `args`.
- [#1265](https://github.com/squid-protocol/gitgalaxy/issues/1265) (PR
  [#1280](https://github.com/squid-protocol/gitgalaxy/pull/1280)) — confirmed the *measurement
  tool's* ground truth was broken, not GitGalaxy: `tree_sitter_accuracy_audit.py`'s `_get_node_name`
  had no handling for C/C++-family grammars' `function_definition` node (which carries no `name`
  field directly), making every C/C++ function appear unnamed to the audit regardless of what
  GitGalaxy itself found. Fixing the measurement tool is what made #1263's real (much smaller) gap
  visible in the first place.
- [#1719](https://github.com/squid-protocol/gitgalaxy/issues/1719) — `func_start` had no support
  for type-conversion operators containing alphanumeric/namespaced names (`operator bool`,
  `operator Variant`, `operator ::AABB() const`) or the functor call operator (`operator()`);
  fixed on `main` (commit `424bdeae`).
- [#1720](https://github.com/squid-protocol/gitgalaxy/issues/1720) (PR
  [#1764](https://github.com/squid-protocol/gitgalaxy/pull/1764)) — the shared macro-shielding
  logic (`_build_brace_safe_stream`) assumed the first branch of any `#if`/`#ifndef` was always the
  active code and blindly shielded out the `#else` branch, hiding real implementations that live
  there instead.
- [#1718](https://github.com/squid-protocol/gitgalaxy/issues/1718) (PR
  [#1761](https://github.com/squid-protocol/gitgalaxy/pull/1761)) — modern C++ digit separators
  (`512'000`) were misread by the shared literal-shielding logic as an opening single-quote char
  literal, shielding out every function between the separator and the next stray apostrophe.

**Cross-language fixes that happened to touch cpp along the way:**
- [#713](https://github.com/squid-protocol/gitgalaxy/issues/713) — fixed `spec_exposure`'s
  unbounded `[^\]]*` ReDoS shape, copy-pasted across 28 languages including cpp.
- [#1209](https://github.com/squid-protocol/gitgalaxy/issues/1209) — wrapped the parameter-list
  span of `args` in its own capture group across languages (including cpp) so detector.py's
  counter isolates just `(...)` instead of falling back to the whole name+params match, which
  overcounted every zero/one-arg signature by +1 (the same shape as Python's #1199).

Search performed via `gh issue list --search 'in:title "Extraction hardening: cpp"'` /
`'in:title "Strict parsing tests: `cpp`"'` / `'in:title cpp'` plus the issues named in this doc's
generation prompt (#1263, #1265, #2009-#2014) (2026-08-21).

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Four repos from the `v2.4.7` batch, chosen for a spread across game-engine, computer-vision,
and classic small-C-library shapes:

- **[`godot`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/godot/godot_galaxy_llm.md)**
  — a large, heavily templated modern C++ game engine (rendering, physics, scripting bridge);
  a good stress test for `func_start`'s template/attribute/pointer-reference handling at scale.
  Scanned in 48.96s.
- **[`opencv`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/opencv/opencv_galaxy_llm.md)**
  — a long-lived computer-vision library with heavy operator-overload and template usage
  (`Mat`, matrix math), a natural fit for exercising the operator/conversion-operator paths in
  `func_start`/`args`. Scanned in 30.19s.
- **[`curl`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/curl/curl_galaxy_llm.md)**
  — small, canonical, mostly-C networking library routed under the shared `.h`/discriminator
  surface; a low-noise contrast case against the two large C++-heavy engines above. Scanned in
  3.33s.
- **[`sqlite`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/sqlite/sqlite_galaxy_llm.md)**
  — another small, classic C systems library; useful as a second low-noise baseline with a very
  different domain (embedded database engine vs. networking). Scanned in 5.62s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.
## 9. Tri-comparison findings (GitGalaxy vs. tree-sitter vs. ctags)

A 2026-08-21 tri-comparison-ledger-sweep investigated every unvalidated discrepancy shape for
`cpp` in `docs/self_scan/tri_comparison_ledger.json` (14 shapes total). Unlike the measured-
accuracy section other language docs may carry (a single tool scored against a privileged ground
truth), this comparison has no privileged tool — see `tests/tools/tri_comparison_reconcile.py`'s
own module docstring for why. All 14 shapes are now `status: "validated"`; the summary below is
built entirely from that investigation's evidence trail, not from memory of it.

### Summary

| | Occurrences investigated | Confirmed GitGalaxy defects | Confirmed comparison-tooling defects | Confirmed ctags-structural limitations |
|---|---|---|---|---|
| cpp | ~780 (raw ledger counts, updated after the macro-shield fix) | 6 (4 filed and open, 2 filed and fixed) | 4 (fixed across two follow-up rounds) | 3 (documented, not fixable here) |

Six real GitGalaxy engine defects were confirmed and filed in this sweep — more than any other
language this sweep methodology has been run against so far, though that reflects C++'s syntactic
complexity (templates, operator overloading, out-of-class definitions, GNU extensions in real
corpus code) at least as much as it reflects anything specific to this scanner's cpp rules. Two of
the six were fixed in follow-up commits rather than staying open: #2011 (forward declarations) the
same day, and a macro-invocation false-positive class (never filed as its own numbered issue —
diagnosed and fixed directly by comparing against ctags' own working behavior) the day after,
which is what moved cpp's Func Precision badge from ctags to GitGalaxy — see "Where GitGalaxy wins
outright" below for the full story.

### Where GitGalaxy wins outright

**Update (2026-08-21): GitGalaxy now holds the Func Precision badge for cpp outright** — 99.7%
(1356/1360) vs. ctags' 97.8% (1348/1378) and tree-sitter's 87.0% (1297/1491). This flipped from
ctags leading (97.8% vs. GitGalaxy's ~92%) earlier the same day, via a real fix: `detector.py`'s
`_slice_by_braces` (the cpp/c integration mode) now scans each file for `#define NAME(...)`
function-like macro definitions and excludes any `func_start` match whose captured name is a
known macro — the exact fact universal-ctags itself already relies on (confirmed via a direct
`ctags -f -` run: ctags tags a macro name once, at its own `#define` line, and never re-tags an
invocation of it as a function; it isn't smarter about the invocation's shape, it just already
knows the name is a macro). This eliminated a 105-occurrence false-positive class GitGalaxy shared
with tree-sitter (`OPCODE(OPCODE_OPERATOR) { ... }`, a bytecode-dispatch macro in
`godot/gdscript_vm.cpp` — `#define OPCODE(m_op) case m_op:`) that had been the single largest
factor dragging GitGalaxy's precision below ctags'. The same fix (shared code path, `lang_id in
("c", "cpp")`) also resolved the already-documented C `RICHCMP_WRAPPER`/`SLOT0`/`SLOT1`/
`SLOT1BINFULL`/`DICT___REVERSED___METHODDEF` false positives for free — see `c.md`'s own §9 for
that side. Verified via 11 hand-built regression cases were not needed here (no new capture-group
edge cases, purely a post-match name-exclusion filter); instead verified via 3 repeated
full-corpus scans producing byte-identical function-name lists, the full extraction gauntlet, and
both golden masters re-blessed.

- **Macro-invocation false positives ARE caught correctly in most cases** — GitGalaxy's own
  func_start regex does not get fooled by ordinary macro calls the way ctags' parser sometimes is
  (see `ctags_reader.py`'s cpp KIND MAPS bullet for the `IFACEMETHODIMP_`/`FUNC2`/`GDCLASS`-body
  cases where only ctags is wrong).
- Out-of-class method definitions, once the comparison tooling itself was fixed to read them
  correctly (see below), show GitGalaxy in essentially full agreement with tree-sitter's own
  parse across NVDA/storage.cpp, godot/*, and mlir/flatbuffer_export.cc — thousands of real
  qualified methods, zero disagreement once compared correctly.
- **A genuine, not-yet-root-caused ctags gap on ordinary methods with no macro involvement at
  all** surfaced once the macro-family false positives were cleared out of the way: ctags produces
  zero tags anywhere near `virtual RID mesh_create_from_surfaces(const Vector<RenderingServerTypes::
  SurfaceData> &p_surfaces, int p_blend_shape_count = 0) override { ... }`
  (`godot/rendering_server_default.h`) and 4 sibling methods in the same class — a real,
  independently-confirmed ctags limitation, not a macro-parsing issue at all.

### Confirmed real GitGalaxy defects

Five of six needed (and still need) the full Differential Scan verification chain before shipping
— real blast radius and/or open design questions the sweep's own investigation flagged
explicitly, so they were filed rather than patched inline:

- **[#2009](https://github.com/squid-protocol/gitgalaxy/issues/2009)** — func_start misses
  constructors whose member-initializer-list exceeds the regex's 500-character cap for that
  clause (confirmed: a real 906-character initializer list in `mlir/flatbuffer_export.cc`). Open.
- **[#2010](https://github.com/squid-protocol/gitgalaxy/issues/2010)** — func_start misses
  conversion operators with a template/generic return type (`operator Vector<T>()`) — the
  operator-name regex branch has no support for angle-bracket generics. Open.
- **[#2011](https://github.com/squid-protocol/gitgalaxy/issues/2011)** — class_start counted a
  bare forward declaration (`class Foo;`) as a real class definition — the same
  `_CLASS_START_REQUIRES_BODY_ANCHOR` guard that already protects C was never extended to cpp.
  **Fixed in a follow-up commit in this same PR**, once the fix's own downstream effect (the
  tree-sitter walker fix above no longer agreeing with GitGalaxy's false positives) surfaced as a
  `tests/tree_sitter_accuracy_baseline_cpp.json` CI regression, making the gap impossible to
  ignore rather than leaving it filed-but-unfixed. A naive copy of C's flat lookahead regex was
  confirmed unsafe first (C++ multiple inheritance, `class Foo : public A, public B {`, hits its
  comma stop-char before the real `{`) -- fixed instead with a depth-aware scanner
  (`_cpp_class_has_body`) that correctly walks through an inheritance clause's own top-level
  commas and template args. Verified via 11 hand-built regression cases (including multi-
  inheritance and templated bases), the full 122-test extraction gauntlet, and `crucible_check.py`
  against the full ~80-repo corpus (zero golden-master diff, confirmed to be because the golden
  master's audit report only exposes the raw class_start signal count, not the named-class list
  this fix touches -- verified directly by querying a fresh scan's DB instead of trusting the
  zero-diff result blind).
- **[#2012](https://github.com/squid-protocol/gitgalaxy/issues/2012)** — args-counting reads 0
  for out-of-class methods and `operator()` overloads with real parameters, and off-by-one
  overcounts a constructor with an initializer list but zero real parameters. Two sub-patterns,
  possibly two root causes.
- **[#2013](https://github.com/squid-protocol/gitgalaxy/issues/2013)** — func_start false
  positive: a lambda passed as a constructor argument or member-initializer-list entry
  (`m_draggingState([this]() {...}),`, `std::thread([...]() {...}).detach();`) is misread as a
  function definition named after the lambda's target.
- **[#2014](https://github.com/squid-protocol/gitgalaxy/issues/2014)** — not a GitGalaxy defect;
  listed here for completeness since it was found in the same investigation. tree-sitter's own
  shared `_get_param_count` helper (`tests/tools/tree_sitter_accuracy_audit.py`, used by the
  verification tooling only) undercounts by exactly 1 for any parameter with a default value.

### Comparison-tooling defects found and fixed in the same session

Three bugs lived in this repo's own comparison tooling (`tests/tools/ctags_reader.py`,
`tests/tools/tri_comparison_gatherer.py`, `tests/tools/tree_sitter_accuracy_audit.py`) — not in
GitGalaxy, not in tree-sitter or ctags themselves:

1. **ctags name/scope re-qualification** — ctags reports an out-of-class method's bare,
   unqualified name plus a separate `class:`/`namespace:` scope field; GitGalaxy and tree-sitter
   both read the fully-qualified identifier straight from source text. Fixed by re-joining
   name+scope from ctags' own tag data (`_QUALIFY_NAME_WITH_SCOPE`,
   `_cpp_qualified_name_candidates`), gated on the qualified text actually appearing in the tag's
   own verbatim source line (via a new `--pattern-length-limit=0` ctags flag, since the default
   ~100-char truncation was silently breaking this check on longer signatures) so an ordinary
   in-class-body method — never qualified in source — isn't wrongly qualified too. This alone
   resolved roughly 1000 of the original ~2170 combined occurrences behind cpp's two largest
   ledger shapes.
2. **Missing enum/union ctags kinds** — `CTAGS_CLASS_KINDS["cpp"]` had neither ctags' `"u"`
   (union) nor `"g"` (enum) kind mapped, so real `union Foo {...}` and `enum class Foo {...}`
   definitions GitGalaxy correctly counts as classes had no ctags counterpart at all. Fixed by
   adding both, with enum gated on the tag's own source line actually saying `enum class`/
   `enum struct` (`_is_cpp_unscoped_enum`) since ctags' "g" kind doesn't itself distinguish a
   scoped C++11 enum from a plain, unscoped one the way GitGalaxy's own class_start regex does.
   The identical gap was also found and fixed for `csharp` in the same pass (C# has no
   scoped/unscoped distinction, so that fix is unconditional).
3. **Forward declarations and unscoped enums over-counted as classes by the tree-sitter walker**
   — both `tri_comparison_gatherer.py`'s own walker and `tree_sitter_accuracy_audit.py`'s
   `measure()` had a `lang == "c"`-only guard against counting a bodyless `class_specifier`
   (forward declaration) as a real class definition, never extended to cpp despite tree-sitter-cpp
   inheriting the identical grammar shape from tree-sitter-c. Separately, both walkers counted
   every `enum_specifier` node unconditionally, with no gate for C++11's scoped-vs-unscoped
   distinction the way GitGalaxy's own regex already has. Both fixed in both files (checking
   `node.child_by_field_name("body")` and a new `_is_cpp_unscoped_enum` node-shape check,
   respectively).

### Confirmed ctags-structural limitations (not fixable in this repo)

- ctags parses **inside C++ macro DEFINITION bodies** as if they were real, already-expanded code
  — `godot/object.h`'s `GDCLASS`/`_FORCE_INLINE_`-based macros define method-shaped text that
  only becomes real code once expanded at a call site elsewhere, but ctags tags the
  never-actually-compiled-as-written declarator text inside the macro body anyway (9 sampled
  cases, all the same macro family).
- ctags mistags a **macro used as a return-type prefix or dispatch label** as the function itself
  — Windows COM's `IFACEMETHODIMP_(void) FancyZones::Run() noexcept {...}` tags `IFACEMETHODIMP_`
  as a complete function and loses the real `FancyZones::Run` name entirely; the same shape hits
  `godot/rendering_server_default.h`'s `FUNC2`/`FUNC3`/`FUNCRIDTEX1` macros. **Update
  (2026-08-21):** `godot/gdscript_vm.cpp`'s `OPCODE`/`OPCODE_WHILE`/`OPCODE_SWITCH`
  bytecode-dispatch macros used to be in this same bullet as a case GitGalaxy and tree-sitter also
  got fooled by (a genuine shared mistake, not real corroboration) — GitGalaxy no longer does,
  fixed by teaching it the same fact ctags already relies on (see "Where GitGalaxy wins outright"
  above); tree-sitter's own copy of this mistake is unchanged and now cleanly isolated in the
  ledger's `agree[tree_sitter]_vs[ctags,gitgalaxy]` shape instead.
- ctags **misses an ordinary method with no macro involvement at all** — confirmed once the
  macro-family false positives above stopped crowding out everything else in the same shape:
  `godot/rendering_server_default.h`'s `mesh_create_from_surfaces` and 4 sibling methods (real
  `virtual ... override` declarations, templated parameter types, default parameter values, no
  macros anywhere nearby) get zero ctags tags at all. Confirmed real, not yet root-caused to a
  specific parser trigger.

### Full record

Filtered ledger: `jq '.entries | to_entries[] | select(.key | startswith("cpp/"))'
docs/self_scan/tri_comparison_ledger.json`. Rendered summary with source citations:
`docs/self_scan/tri_comparison_points_of_interest.md` (search for `cpp`).
