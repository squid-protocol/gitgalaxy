# Kotlin — Structural Signature Coverage

Snapshot generated 2026-08-22 against `main`. Source: `LANGUAGE_DEFINITIONS["kotlin"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_kotlin.py` /
`test_kotlin_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Kotlin 2.3.10 (K2 Compiler / Wasm / Java 25 Support) |
| `_meta.blueprint_version` | *(unset)* |
| `_meta.last_updated` | 2026-03-12 |
| `lexical_family` | `standard_block` (`//` and nestable `/* /* */ */` block comments — Kotlin explicitly allows nesting, so C-family single-level block-comment handling would terminate early) |
| Structural signature keys wired | 51 / 52 (1 explicit `None`, see §4) |
| Extraction-gauntlet + strict-signature tests (`test_kotlin.py` + `test_kotlin_strict.py`) | 133 |
| Tri-comparison sweep (GitGalaxy vs. tree-sitter vs. ctags) | 4/4 discrepancy shapes validated, 2 real audit-tool bugs fixed — see §9 |

## 2. Identification surface

- **Extensions:** `.kt .kts .ktm` — standard sources, Kotlin script files (heavily used in modern Gradle build logic), and module declarations.
- **Exact filenames:** none — Kotlin rarely uses extensionless execution scripts.
- **Discriminators:** `.kt`, `build.gradle.kts`, `settings.gradle.kts`, `gradle.properties` — Kotlin-DSL Gradle build files used as ecosystem anchors.
- **Shebangs:** `kotlin`, `kotlinc`, `kscript`.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` and `how_to_add_a_language.md` use.
Description is what Kotlin's *actual* regex matches, not the generic cross-language definition.

**Topology & structure**
| Key | What it captures for Kotlin |
|---|---|
| `branch` | `if else when for while do try catch finally break continue return`, plus the Elvis operator (`?:`) and `&&`/`\|\|` |
| `args` | `fun`/`constructor` parameter lists, with a dedicated "lambda parameter shield" (one-level parenthesis nesting) for default-argument/lambda-typed parameters, bounded generic step-over (`<T, U : Comparable<U>>`), backtick-quoted arbitrary identifiers, and a second alternative for bare trailing-lambda syntax (`list.forEach { item -> ... }`) |
| `structural_boundaries` | `package import return class interface object fun typealias` |
| `func_start` | Anchors `fun`, `init`, or `constructor`, stepping over up to 10 annotation lines and 5 modifier keywords (`public private protected internal open override abstract final suspend inline tailrec infix operator external expect actual`), an optional `context(...)` receiver, and bounded generics — captures the literal name for the `init`/`constructor` forms since neither has a user-chosen identifier |
| `class_start` | `class interface object enum class`, plus a dedicated (usually-anonymous, optionally-named) `companion object` alternative — `fun` is itself a valid modifier here for `fun interface Foo` (SAM/functional-interface declarations) |

**Safety & risk**
| Key | What it captures for Kotlin |
|---|---|
| `safety` | Safe-call chains ending the line (`?.` at end), `as?`, `require requireNotNull check checkNotNull error sealed is !is Result onSuccess onFailure fold runCatching`, Elvis (`?:`) |
| `safety_bypasses` | Force-unwrap (`!!`), unsafe cast (`as` without `?`), `lateinit var`, `@Suppress` |
| `high_risk_execution` | `System.exit exitProcess Runtime.getRuntime Thread.stop` |
| `io` | `File InputStream OutputStream Retrofit OkHttpClient Ktor HttpClient RoomDatabase Dao SharedPreferences DataStore java.nio` |
| `api` | `public`/`internal` visibility keywords, Ktor/Spring route annotations (`@RestController @Controller @Service @Component @RequestMapping @GetMapping @PostMapping @Route`) |
| `state_mutation` | `var`, mutable collection/state types (`MutableList MutableMap MutableSet MutableState MutableStateFlow Atomic*`), line-start assignment expressions, mutator calls (`.add/.addAll/.remove/.put/.set/.update`) |
| `dead_code` | Commented-out `// val/var/fun/class/interface/object/if/when/for/return` |
| `doc` | `/** @param @return @property @receiver @constructor @throws @see @since` |
| `test` | JUnit-style (`@Test @ParameterizedTest @BeforeTest @AfterTest`), `assert*(`, MockK (`mockk spyk every{ verify{`), Kotest (`shouldBe shouldNotBe`) |

**Architecture & domain sensors**
| Key | What it captures for Kotlin |
|---|---|
| `concurrency` | `suspend launch async CoroutineScope GlobalScope Dispatchers Flow StateFlow SharedFlow Channel yield runBlocking withContext Mutex` |
| `ui_framework` | Jetpack Compose (`@Composable Modifier Column Row Box Text Image Button Scaffold LazyColumn LazyRow Surface remember mutableStateOf`) and classic Android views (`findViewById View Activity Fragment`) |
| `closures` | Bare trailing-lambda shape (`{ x -> ...`, up to a 150-char parameter clause) |
| `globals` | `object`/`companion object`, top-level `const val SCREAMING_CASE =` |
| `decorators` | Any `@`-prefixed annotation, with a bounded 300-char argument list |
| `generics` | Uppercase-bound generic parameters (`<T>`, `<in T>`, `<out T>`), `reified`, `where` clauses |
| `comprehensions` | Functional collection transforms (`.map .mapNotNull .filter .filterNot .reduce .fold .flatMap .zip .associate .groupBy .forEach .any .all .none .find`) |
| `scientific` | `kotlin.math. java.lang.Math. StrictMath. Random.` and common math function names, `BigDecimal BigInteger` |
| `reflection_metaprogramming` | `::class`, `javaClass`, `@JvmOverloads @JvmStatic @JvmField @JvmName`, `inline crossinline noinline invoke context tailrec` |
| `import` / `_dependency_capture` | `import [static] pkg.path` (Java-interop-style `import static` included) |
| `ownership` | `@author`/`@since` KDoc tags, `// Created by:`/`Maintainer:`/`Copyright:` comments |

**Specialized subsystems**
| Key | What it captures for Kotlin |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`, `[spec ...]`, `[audit ...]` traceability tags |
| `ssr_boundaries` | `ApplicationCall call.respond call.respondText call.respondHtml ServerResponse ModelAndView` |
| `events` | `.collect .collectLatest .observe .subscribe .onNext` called with either `(` or a bare trailing `{` (Flow's idiomatic SAM-conversion collector style), `LiveData Observer Observable FlowCollector` |
| `dependency_injection` | `@Inject @Module @Provides @Binds @HiltViewModel @AndroidEntryPoint @Component @Autowired`, Koin's `get()`/`inject()` |
| `macros` | `@OptIn @RequiresOptIn @Suppress @SuppressWarnings` |
| `pointers` | Kotlin/Native FFI types (`CPointer COpaquePointer CFunction CValue CPointed`) |
| `memory_alloc` | Kotlin/Native manual memory (`memScoped alloc allocArray nativeHeap.alloc nativeHeap.free`) |
| `telemetry` | `Timber Log Logger LoggerFactory` log-level calls, `@Slf4j` |
| `debug_prints` | `println(`/`print(` |
| `explicit_casts` | `as`/`as?` to a capitalized type, `.toInt() .toLong() .toShort() .toByte() .toDouble() .toFloat() .toString() .toBoolean() .toUInt() .toULong() .toUShort() .toUByte()` |
| `panics_and_aborts` | `throw raise exitProcess return panic` |
| `thread_sleeps` | `delay Thread.sleep yield` |
| `bitwise_ops` | `.shl() .shr() .ushr() .and() .or() .xor() .inv()`, bare `shl shr ushr xor` |
| `sync_locks` | `mutex lock synchronized Semaphore Atomic*` (case-insensitive) |
| `immutability_locks` | `val const immutable readonly` |
| `cleanup` | `close() dispose() shutdown() use() cleanup()` |
| `encapsulation` | `private protected internal` |
| `listeners` | `.collect .observe .subscribe .on<Event> .set<X>Listener` called with either `(` or a bare trailing `{` (same SAM-conversion idiom as `events`) |
| `test_skip` | `@Ignore @Disabled`, `test.skip(`, `mockk spyK fake(` |
| `serialization_parsing` | `Json.decodeFromString Json.encodeToString Moshi ObjectMapper`, `Gson()` |
| `regex_execution` | `Regex(`, `.toRegex()`, `.matches(`, `.find(` |
| `time_date_logic` | `Clock.System.now Instant.now System.currentTimeMillis Duration.minutes LocalDate` |
| `ipc_rpc_bridges` | `BroadcastReceiver ProcessBuilder bindService`, `Intent(`, `HttpClient(` |

## 4. What GitGalaxy explicitly does not track

- **`inline_asm`** — `None`. Kotlin has no native inline-assembly syntax; Kotlin/Native FFI bridges to raw assembly go through C headers instead (covered indirectly by `pointers`/`memory_alloc`).

## 5. Known limitations (accepted, not fixed)

One documented `known_limitation` test (`test_kotlin.py`):

- **`func_start` has no string/comment awareness.** Function-shaped text sitting inside a Kotlin raw (triple-quoted) string literal that happens to land at true line start still matches at the regex level (e.g. a `"""...fun TargetFunc() {...."""` string). This is the same architectural gap already confirmed on six other languages (JS/TS template literals, Java text blocks, Go/Rust raw strings, C# verbatim/raw strings — recurring bug class 3 in `how_to_harden_extraction.md`), now a seventh confirmed instance for Kotlin. Not fixed at the regex level — Kotlin routes through `detector.py`'s Mode B (`_slice_by_braces`), which is currently only string-shielded for JavaScript/TypeScript; extending that shielding to Kotlin is tracked as a future audited follow-up in the epic, not addressed here.

## 6. Test depth

`test_kotlin.py` + `test_kotlin_strict.py`: **133 collected test cases** (pytest `--collect-only`,
counts parametrized cases individually). Includes a dedicated ReDoS regression sweep
(`test_kotlin_redos_immunity_sweep`, added by #1070) and two cross-signature false-collision
guards (`test`/`regex_execution`, `explicit_casts`/`pointers`).

## 7. Relevant closed work

**Epic-level hardening passes**
- [#823](https://github.com/squid-protocol/gitgalaxy/issues/823) — Extraction hardening: kotlin (epic #813 sub-issue). Fixed the generic-parameter nesting gap (Rule 11), added backtick-identifier support to `func_start`/`args`, and the `companion object`/`fun interface` recall gaps in `class_start`.
- [#592](https://github.com/squid-protocol/gitgalaxy/issues/592) — Strict parsing tests: `kotlin` structural signatures (epic #1069 sub-issue).
- [#1070](https://github.com/squid-protocol/gitgalaxy/issues/1070) — Added ReDoS regression tests for 6 languages with zero prior coverage, including kotlin.
- [#1295](https://github.com/squid-protocol/gitgalaxy/issues/1295) — Extended per-language `class_start` named-entity extraction to kotlin (companion objects, `object`/`enum class` declarations resolve to real names instead of a generic "Anonymous_Class" placeholder).

**Real engine bugs found and fixed**
- [#899](https://github.com/squid-protocol/gitgalaxy/issues/899) — `func_start`/`args` missing backtick-identifier support (found during #825).
- [#1209](https://github.com/squid-protocol/gitgalaxy/issues/1209) — `args`' capture group was missing in 25 languages including kotlin (regression from the #1199 Python fix) — every zero/one-arg signature, including a bare trailing lambda, was overcounted by +1.
- [#1405](https://github.com/squid-protocol/gitgalaxy/issues/1405) (PR [#1413](https://github.com/squid-protocol/gitgalaxy/pull/1413)) — `func_start` missed expression-bodied and bodyless interface method declarations, measured at 39.1% recall against the real okhttp corpus before the fix.

**Measurement-tooling bugs (not engine bugs, but shaped what could be measured)**
- [#1313](https://github.com/squid-protocol/gitgalaxy/issues/1313) / PR [#1315](https://github.com/squid-protocol/gitgalaxy/pull/1315) — `tree_sitter_accuracy_audit.py` reported kotlin's `real_functions`/`real_classes` as 0 despite confirmed function-shaped nodes in real corpus files — a `_get_node_name` no-"name"-field gap (kotlin's `function_declaration`/`class_declaration`/`object_declaration` nodes carry the identifier as a plainly-typed child, not a tree-sitter field), not an extraction gap. This masked #1405's real gap until fixed.

**This session (tri-comparison-ledger-sweep, 2026-08-22)** — see §9 for the full writeup:
- `tests/tools/ctags_reader.py`'s kotlin `CLASS_KINDS` was missing `"o"` (objects), silently excluding every `object Foo { ... }` singleton declaration from the ctags-side class comparison.
- `tests/tools/tree_sitter_accuracy_audit.py`'s kotlin `func_node_types` was missing `secondary_constructor` (and, proactively, `anonymous_initializer`), so tree-sitter's own real-function count silently excluded every Kotlin secondary constructor.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

- **[`kotlin`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/kotlin/kotlin_galaxy_llm.md)** — the Kotlin compiler's own reference implementation ([JetBrains/kotlin](https://github.com/JetBrains/kotlin)). The most adversarial Kotlin codebase available: self-hosting compiler internals, every language-generation era, heavy multiplatform/`expect`/`actual` usage. Scanned in 148.9s.
- **[`okhttp`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/okhttp/okhttp_galaxy_llm.md)** — [square/okhttp](https://github.com/square/okhttp), a mid-size, long-lived production networking library — the same corpus §9's tri-comparison sweep investigated directly. Scanned in 2.36s.
- **[`retrofit`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/retrofit/retrofit_galaxy_llm.md)** — [square/retrofit](https://github.com/square/retrofit), a small, canonical single-purpose REST client library — a useful low-noise baseline. Scanned in 1.68s.

## 9. Tri-comparison: GitGalaxy vs. tree-sitter vs. ctags

This section is a different shape from a §9 that diffs GitGalaxy against one privileged
ground-truth parser (see python.md's/javascript.md's §9): Kotlin has two independent,
non-privileged comparison tools available (`tree-sitter-kotlin` and `universal-ctags`) and
neither is treated as ground truth — see `tests/tools/tri_comparison_reconcile.py`'s own module
docstring for why. Every discrepancy the three tools produced was investigated by reading real
source (`docs/self_scan/how_to_investigate_a_discrepancy.md`'s process), not assumed — the full
record is `docs/self_scan/tri_comparison_ledger.json`, filterable to `"language": "kotlin"`.

**Result: 4/4 discrepancy shapes validated, 2 confirmed real audit-tool defects found and fixed in
this pass** (`tests/tools/ctags_reader.py` and `tests/tools/tree_sitter_accuracy_audit.py` —
GitGalaxy's own engine had zero confirmed defects among the discrepancies this methodology
surfaced). All 5 language-crucible/data/kotlin/okhttp corpus files. Current measured numbers
(`tests/tools/tri_comparison_chart.py --languages kotlin`):

| Signal | GitGalaxy | tree-sitter | ctags | Read as |
|---|---|---|---|---|
| Functions found (of 43 total claimed by any tool) | 28 | 28 | 42 | ctags' higher count is mostly noise (false positives), not real recall — see precision row |
| Function precision (of what each tool claimed, how much corroborates) | **100%** (28/28) | **100%** (28/28) | 28.6% (12/42)\* | tied GitGalaxy/tree-sitter win; ctags' precision reflects a confirmed, permanent over-detection bug (see below) |
| Class recall/precision | **100%** (7/7) | **100%** (7/7) | **100%** (7/7) | fully reconciled after this pass's fix — see below |
| Args exact-match | **100%** (27/27) | **100%** (27/27) | N/A (0/0) | ctags emits no per-function parameter-count data for Kotlin at all |

\* ctags' function precision reflects `tri_comparison_ledger.py`'s verified debit mechanism — its
raw agreement-based precision (before this pass) would have been higher only in the sense that
those 15 occurrences were still counted as "claimed"; the debit doesn't change what ctags claimed,
only whether the claim should count as corroborated (it shouldn't — see below).

### Where GitGalaxy (and tree-sitter) win outright

- **Kotlin secondary constructors.** `okhttp/Dispatcher.kt:119`'s `constructor(executorService:
  ExecutorService?) : this() { ... }` is a real, named-by-keyword Kotlin construct. GitGalaxy's
  `func_start` regex already had a dedicated `(constructor)` alternative for it. tree-sitter-kotlin
  gives it its own `secondary_constructor` node type, distinct from `function_declaration` — real,
  just invisible to `tree_sitter_accuracy_audit.py` pre-fix (see below). ctags' own Kotlin parser
  does not recognize this construct as a symbol at all, under any kind — a genuine parser gap, not
  a kind-mapping one (confirmed via `ctags -x --languages=Kotlin` emitting no entry whatsoever for
  line 119).
- **`object` singleton declarations as classes.** `okhttp/OkHttp.kt`/`OkHttp.android.kt`/
  `OkHttp.jvm.kt` each declare `(actual|expect) object OkHttp { ... }`. GitGalaxy's `class_start`
  regex and tree-sitter-kotlin's `object_declaration` node both already correctly treat `object`
  as class-shaped. ctags' own parser tags it too, just under its own distinct `object` kind
  (`o`) rather than `class` (`c`) — invisible to the comparison only because
  `ctags_reader.py`'s kotlin `CLASS_KINDS` set was missing `"o"` (fixed this pass).

### Confirmed audit-tool bugs found and fixed this pass

- **`tests/tools/ctags_reader.py`'s kotlin `CLASS_KINDS`** was `{"c", "i"}`, missing `"o"`
  (objects) — the exact same shape as this file's already-documented cpp/fortran `CLASS_KINDS`
  gaps. Fixed by adding `"o"`.
- **`tests/tools/tree_sitter_accuracy_audit.py`'s kotlin `func_node_types`** was missing
  `secondary_constructor` (and, proactively, `anonymous_initializer` for `init { }` blocks — same
  no-name-field shape, same regex's `(init)` sibling alternative, no live occurrence in this
  corpus but the identical underlying gap). Fixed by adding both node types plus matching
  `_get_node_name`/`_get_param_count` branches (the literal keyword text is the name — neither
  construct has a user-chosen identifier in Kotlin).

### Confirmed ctags-side limitation (not fixable via this repo's tooling)

- **ctags' own Kotlin parser tags two non-function shapes with the same generic `method` kind as
  real functions**, and — unlike the object/class gap above — this isn't a kind-mapping omission;
  ctags simply gives Kotlin no separate kind for either shape in the first place. Confirmed via
  direct `ctags -x --languages=Kotlin` inspection of `okhttp/Dispatcher.kt`, 15 occurrences: (1)
  10 trailing-lambda blocks passed as call arguments (`require(x >= 1) { "..." }`,
  `synchronized(this) { ... }`, `.also { ... }`, `.map { it.call }`) tag as a synthetic `<lambda>`
  symbol; (2) 5 `for (x in collection)` loop iteration variables tag as a method literally named
  after the variable (`call`, `existingCall`). GitGalaxy's `func_start` regex and tree-sitter's
  grammar both correctly require a real `fun`/constructor declaration, so their agreement here is
  real corroboration, not a shared miss — ctags' own claim on this shape is debited in the ledger
  (documented in `ctags_reader.py`'s kotlin `FUNCTION_KINDS` comment for future reference).
  Separately, and in the opposite direction: ctags' Kotlin parser also fails to recognize
  secondary constructors as symbols at all (see above) — a real, permanent ctags parser
  limitation this repo's tooling cannot work around.
