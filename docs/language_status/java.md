# Java — Structural Signature Coverage

Snapshot generated 2026-08-21 against `main`. Source: `LANGUAGE_DEFINITIONS["java"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_java.py` /
`test_java_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Java 25 (Project Loom, Panama, Amber) / Spring Boot 3.4+ |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `standard_block` (C-family `//` line comments, `/* */` block comments) |
| Structural signature keys wired | 50 / 52 (2 explicit `None` — `macros`, `inline_asm`; Java has no C-style preprocessor or inline-asm syntax) |
| Extraction-gauntlet tests (`test_java.py`) | 70 |
| Strict-signature tests (`test_java_strict.py`) | 91 |
| Total dedicated Java test cases | 161 |
| Real-world function precision vs. ctags + tree-sitter (real pipeline) | 318/318 (100%) — see §9 |
| Real-world class precision vs. ctags + tree-sitter | 35/35 (100%) — see §9 |

## 2. Identification surface

- **Extensions:** `.java .jav .jsp .jspf .jspx .jws .bsh` — standard modern suffixes, server-side
  JSP templates, and Beanshell embedded scripting.
- **Exact filenames:** none.
- **Discriminators:** `.java`, `pom.xml`, `build.gradle`, `build.gradle.kts`, `settings.gradle`,
  `build.xml`, `mvnw`, `gradlew`, `.classpath`, `.project` — Maven/Gradle/Ant ecosystem anchors
  used to disambiguate.
- **Shebangs:** `java`, `jshell`.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` and `how_to_add_a_language.md` use.
Description is what Java's *actual* regex matches, not the generic cross-language definition.

**Topology & structure**
| Key | What it captures for Java |
|---|---|
| `branch` | `if else switch case default for while do catch finally continue break yield try when`, `?`, `:` — includes modern switch expressions (`yield`) and pattern-matching guards (`when`) |
| `args` | Method/constructor parameter lists (3 branches: standard methods with a required return type, constructors anchored to `{`/`throws`, and lambdas/method-refs). Bounded one-level-nesting generic-bound support (`<T, U extends Comparable<U>>`); modifier-repeat group now also accepts an interleaved return-type annotation (`private <T> @Nullable T foo(...)`, #2091) |
| `structural_boundaries` | `void return import package class interface enum record extends implements var sealed non-sealed permits new throws module requires exports opens provides uses` |
| `func_start` | Anchors method/constructor declarations, stepping over up to 10 annotation lines and a bounded one-level-nesting generic-bound modifier. Explicitly shields against `new`/`return`/`throw`/control-flow keywords being mistaken for a return type ("Execution Shield"). Bodyless abstract/interface method declarations (`;`-terminated) are now correctly recognized as real functions, not silently dropped (#2089) |
| `class_start` | Anchors `class interface enum record`, steps over a generic type-parameter list before checking `extends`/`implements`, captures class name + inheritance list |

**Safety & risk**
| Key | What it captures for Java |
|---|---|
| `safety` | `try catch finally assert Optional Objects.requireNonNull instanceof`, `@Valid @Validated @NotNull @NonNull @NotBlank @Immutable @Transactional` |
| `safety_bypasses` | Bare `null`, `return null`, C-style casts not followed by `->` (excludes lambda param-type ascription false positives), `catch (Exception\|Throwable`, `@SuppressWarnings`, `@SneakyThrows`, `.get()` (unchecked `Optional`/`Future` unwrap) |
| `high_risk_execution` | `Runtime.getRuntime().exec ProcessBuilder System.exit Thread.stop Unsafe` |
| `io` | `File InputStream OutputStream Reader Writer Scanner Files. Path Socket RestTemplate WebClient RestClient HttpClient Connection ResultSet Statement EntityManager DataSource Repository` |
| `api` | `public`/`protected` visibility, Spring/JAX-RS surface annotations (`@RestController @Controller @Service @Component @Bean @Produces @Consumes @RequestMapping @GetMapping @PostMapping @PutMapping @DeleteMapping @PatchMapping @Endpoint @WebFilter`) |
| `state_mutation` | `volatile`, `Atomic*` types, `this.field =` / bare `field =` assignment, `@Setter`/`@Data` (Lombok), mutator-method calls (`setX/add/put/remove/clear/addAll/replace/computeIfAbsent`) |
| `dead_code` | Commented-out `// public/private/protected/class/void/if/for/while/return/import` |
| `doc` | `/**` Javadoc opener, `@param @return @throws @deprecated @see @since @apiNote @implSpec`, OpenAPI `@Operation @Schema` |
| `test` | `@Test @ParameterizedTest @Before @After @BeforeEach @AfterEach @Mock @InjectMocks`, `assert*(`, `verify/expect/given/when(` |

**Architecture & domain sensors**
| Key | What it captures for Java |
|---|---|
| `concurrency` | `synchronized Thread Runnable Future CompletableFuture ExecutorService Semaphore Atomic* VirtualThread StructuredTaskScope ScopedValue Mono Flux Publisher`, `@Async @Scheduled` |
| `ui_framework` | `SwingUtilities JFrame JPanel javafx. ModelAndView ModelMap Model VaadinSession FacesContext UIComponent`, `@ModelAttribute` |
| `closures` | `->`, `::` (lambdas and method references) |
| `globals` | `System.getProperty System.getenv ThreadLocal ScopedValue`, `public static final TYPE NAME =` constant idiom, `@Value @ConfigurationProperties` |
| `decorators` | Any leading `@Annotation(...)` at line start |
| `generics` | `<T...>` / `<? ...>` type-parameter/wildcard shapes |
| `comprehensions` | Stream pipeline calls: `.stream .parallelStream .map .filter .reduce .collect .flatMap .forEach .anyMatch .noneMatch .gather` |
| `scientific` | `Math. BigDecimal BigInteger Random SecureRandom StrictMath VectorSpecies FloatVector IntVector` |
| `reflection_metaprogramming` | `reflect. native Class.forName Method.invoke Field.setAccessible Proxy.newProxyInstance ClassLoader MethodHandles VarHandle Linker.nativeLinker`, `@SneakyThrows` |
| `import` / `_dependency_capture` | `import [static] pkg.Type;` |
| `ownership` | `@author Name` (Javadoc tag) |

**Specialized subsystems (Java-specific hybrid sensors)**
| Key | What it captures for Java |
|---|---|
| `planned_debt` / `fragile_debt` | Global TODO/FIXME conventions shared across all languages |
| `spec_exposure` | `[SPEC-123 ...]` / `[spec ...]` / `[audit ...]` bracketed traceability markers |
| `ssr_boundaries` | `ModelAndView FacesServlet HttpServletRequest HttpServletResponse JspWriter ThymeleafViewResolver`, `@ResponseBody @ResponseStatus` |
| `events` | `ApplicationEvent ApplicationEventPublisher ApplicationListener EventObject publishEvent`, `@EventListener @KafkaListener @RabbitListener @JmsListener` |
| `dependency_injection` | `ApplicationContext BeanFactory`, `@Autowired @Inject @Qualifier @Primary @Component @Service @Repository @Bean @Configuration @Provides` |
| `pointers` | `MemorySegment MemoryLayout ValueLayout AddressLayout SymbolLookup` (Project Panama native-memory bridging) |
| `memory_alloc` | `Arena.ofConfined/ofShared/ofAuto/global SegmentAllocator allocateFrom ByteBuffer.allocateDirect` |
| `serialization_parsing` | `ObjectMapper readValue readTree fromJson ObjectInputStream DocumentBuilder SAXParser` |
| `regex_execution` | `Pattern.compile Matcher.find .matches(` |
| `time_date_logic` | `LocalDate[Time] ZonedDateTime Instant Duration System.currentTimeMillis Calendar.getInstance` |
| `ipc_rpc_bridges` | `ProcessBuilder KafkaTemplate RabbitTemplate JmsTemplate java.rmi` |

**Resource management & stability**
| Key | What it captures for Java |
|---|---|
| `telemetry` | `log/logger/LOGGER.info/error/warn/debug/trace`, `LoggerFactory LogManager MDC Tracer Span`, `@Slf4j @Log4j2` |
| `debug_prints` | `System.out.print/println/printf`, `System.err.print/println/printf`, `.printStackTrace()` |
| `explicit_casts` | `(Type) identifier` C-style casts (primitives + capitalized reference types) |
| `panics_and_aborts` | `throw abort System.exit halt` |
| `thread_sleeps` | `Thread.sleep TimeUnit.X.sleep delay CountDownLatch.await` |
| `bitwise_ops` | `<< >> >>> ^ ~` |
| `sync_locks` | `mutex lock synchronized Semaphore ReentrantLock ReadWriteLock Condition` |
| `immutability_locks` | `final immutable unmodifiableX Object.freeze` |
| `cleanup` | `close/dispose/shutdown/free/release/cleaner.register(` |
| `encapsulation` | `private protected internal` |
| `listeners` | `onX addEventListener subscribe`, `@KafkaListener @RabbitListener` |
| `test_skip` | `@Ignore @Disabled`, `test.skip(`, `mock( spy( verifyZeroInteractions` |

## 4. What GitGalaxy explicitly does not track

- **`macros`** — Java has no C-style preprocessor; there is no macro-definition/expansion
  syntax to signature.
- **`inline_asm`** — no inline-assembly syntax in the language.

Java has no dedicated `naming_convention`/`shadow_apis`-style entries wired either (those newer
universal-regex signature keys from #1145/#1148 are not currently in this language's `rules`
dict) — not a gap specific to Java, just not yet retrofitted here.

## 5. Known limitations (accepted, not fixed)

Two `known_limitation`-named tests, both the same underlying architectural class, on two
different syntax features:

- **`func_start` / `_dependency_capture` have no string/comment awareness of their own.**
  Function-shaped text inside a Java 15+ text block (`"""..."""`) that happens to land at true
  line start still matches at the regex level (e.g. a text block literally containing
  `public void TargetFunc() {`). This is the same architectural class already documented for
  javascript/typescript template literals (recurring bug class #3 in
  `how_to_harden_extraction.md`), now confirmed on Java text blocks too. The real fix — matching
  against `prism.py`-shielded text — lives in `detector.py`'s `_slice_by_braces` and is currently
  gated to javascript/typescript only; broadening it to other Mode B languages (Java included) is
  tracked as a future audited follow-up, not fixed here.

## 6. Test depth

161 total dedicated Java test cases: 70 in `test_java.py` (the extraction gauntlet —
func_start/args/class_start/`_dependency_capture`) and 91 in `test_java_strict.py` (every other
signature key, plus ReDoS immunity checks). Both live at
`tests/extraction/languages/test_java.py` / `test_java_strict.py` — fully migrated to the
per-language layout, nothing left in the old monolithic four-file structure.

## 7. Relevant closed work

**Epic-level hardening passes**
- [#816](https://github.com/squid-protocol/gitgalaxy/issues/816) "Extraction hardening: java"
  (epic #813) — closed via PR
  [#868](https://github.com/squid-protocol/gitgalaxy/pull/868).
- [#588](https://github.com/squid-protocol/gitgalaxy/issues/588) "Strict parsing tests: `java`
  structural signatures" — closed via PR
  [#655](https://github.com/squid-protocol/gitgalaxy/pull/655), "fix 2 real bugs (1 ReDoS)".

**Real bugs found and fixed along the way**
- [#1486](https://github.com/squid-protocol/gitgalaxy/issues/1486) — `func_start` didn't match a
  JSR-308 type-use annotation (`@Nullable`) sitting between a modifier and the return type
  (`protected @Nullable Foo bar(...)`); measured func recall 87.6% pre-fix. Fixed via PR
  [#1489](https://github.com/squid-protocol/gitgalaxy/pull/1489).
- [#2089](https://github.com/squid-protocol/gitgalaxy/issues/2089) — `detector.py`'s generic
  Mode-B body-slicing fallback silently dropped bodyless abstract/interface method declarations
  (`protected abstract long startTime();`) since Java had no dedicated terminator-search handling
  the way csharp/rust/go/objective-c/dart/perl already do. Fixed in this sweep (tri-comparison
  ledger investigation, 2026-08-21).
- [#2091](https://github.com/squid-protocol/gitgalaxy/issues/2091) — sibling gap to #1486: the
  `args` rule's modifier-repeat group never got the matching interleaved-annotation fix
  `func_start` got, so a signature like `private <T> @Nullable T handleBindResult(...)` fell
  through to the lambda-matching branch and misattributed an unrelated in-body lambda's arg count
  as the function's own. Fixed in this sweep.

**Cross-language fixes that happened to touch Java**
- [#1221](https://github.com/squid-protocol/gitgalaxy/issues/1221) "func_start Invocation
  Shield" — phantom-function false positives from unguarded bare call statements, affected
  java/typescript/csharp/apex/dart/groovy; fixed via PR
  [#1226](https://github.com/squid-protocol/gitgalaxy/pull/1226).
- Multiple `ReDoS` bounding passes across epic #813/#1069 touched Java's `state_mutation` and
  `spec_exposure` rules (unbounded-quantifier fixes shared with several other C-family languages).

## 8. Real-world evidence

From [`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output)'s
`v2.4.7` snapshot — each repo directory has a `_galaxy_llm.md` (human-readable summary),
`_galaxy_audit.json.gz`, `_galaxy_sbom.json.gz`, etc.:

- **[spring-boot](https://github.com/squid-protocol/gitgalaxy-raw-output/tree/main/v2.4.7/spring-boot)**
  — the same framework the `language-crucible` corpus's own `springboot/` sample files are drawn
  from; a large, actively-maintained enterprise framework with heavy annotation usage
  (`@Autowired`, `@RestController`, JSR-308 type-use annotations), abstract-class hierarchies,
  and varargs-heavy constructors — exactly the shapes this sweep's fixes target.
- **[elasticsearch](https://github.com/squid-protocol/gitgalaxy-raw-output/tree/main/v2.4.7/elasticsearch)**
  — a very large, complex distributed-systems codebase; a useful adversarial-scale data point for
  how the engine holds up on a huge, deeply-nested real-world project.
  [okhttp](https://github.com/squid-protocol/gitgalaxy-raw-output/tree/main/v2.4.7/okhttp)
  — a small, focused HTTP client library; a useful contrast in size/shape against
  spring-boot/elasticsearch.

## 9. Measured accuracy (tri-comparison: GitGalaxy vs. ctags vs. tree-sitter)

Unlike python.md's §9 (which diffs against a single privileged ground-truth parser, Python's own
`ast`), Java has no single authoritative parser available in this pipeline — this section instead
uses GitGalaxy's tri-comparison methodology
(`tests/tools/tri_comparison_reconcile.py`/`tri_comparison_ledger.py`), diffing GitGalaxy's
extraction against both `ctags` and `tree-sitter-language-pack`'s `tree-sitter-java` grammar over
the full `language-crucible/data/java/` corpus (7 files, ~14,600 real lines, Spring Boot
production source), treating agreement between the *other* two tools as the tie-breaker when
GitGalaxy disagrees with one of them.

**Investigation summary (2026-08-21 sweep):** 4 unvalidated ledger shapes covering the language,
all investigated directly (no dispatch needed — each resolved to an obvious, checkable root cause
from source), all traced to real, fixable causes, all now `status: "validated"` with
`still_reproduces: false`.

| Shape | Occurrences | Root cause | Resolution |
|---|---|---|---|
| `function/args/agree[ctags,tree_sitter]_vs[gitgalaxy]` | 28 | GitGalaxy engine defect: `args` regex missing the interleaved-return-type-annotation fix `func_start` already had (sibling gap to #1486) | Fixed, [#2091](https://github.com/squid-protocol/gitgalaxy/issues/2091) |
| `function/args/agree[ctags,gitgalaxy]_vs[tree_sitter]` | 12 | Audit-tool defect: `tree_sitter_accuracy_audit.py`'s `_get_param_count` missing java's `spread_parameter` (varargs) node type from its whitelist — same recurring per-grammar gap as #1339/#1506/#1570/#1319 | Fixed, [#2090](https://github.com/squid-protocol/gitgalaxy/issues/2090) |
| `function/existence/agree[ctags,tree_sitter]_vs[gitgalaxy]` | 3 | GitGalaxy engine defect: bodyless abstract-method declarations silently dropped by `detector.py`'s generic Mode-B fallback (Java never got dedicated terminator-search handling, unlike csharp/rust/go/objc/dart/perl) | Fixed, [#2089](https://github.com/squid-protocol/gitgalaxy/issues/2089) |
| `function/args/agree[none]_vs[ctags,gitgalaxy,tree_sitter]` | 1 | Compound of the two args bugs above, on the same occurrence | Resolved by both fixes together |

**Results after fix, full corpus:**

| Signal | Before | After |
|---|---|---|
| Function existence precision (3-way agreement) | 315/318 | 318/318 (100%) |
| Function args exact-match | 278/318 | 318/318 (100%) |
| Class existence / precision | 35/35 (already clean) | 35/35 (100%) |

Verified via a full `tri_comparison_gatherer.gather_language("java")` name+line diff across every
corpus file (not just the ledger's capped 10-example samples per shape): zero functions
tree-sitter finds that GitGalaxy misses, zero args mismatches anywhere. Both golden-master
fixtures (`tests/golden_master_audit.json`, `tests/golden_master_zero_dep_audit.json`) re-blessed
against the full ~80-repo differential-scan corpus; the only files outside `java/springboot`
affected were `.java` files living inside `groovy/gradle`/`groovy/spock` repos (real, expected —
same java rules apply regardless of the repo's dominant ecosystem label) plus the usual
topological-coordinate ripple in a handful of unrelated files from the whole-graph layout
recomputing with corrected counts.

See [`docs/self_scan/tri_comparison_ledger.json`](../self_scan/tri_comparison_ledger.json)
(filtered to `java/`) and
[`docs/self_scan/tri_comparison_points_of_interest.md`](../self_scan/tri_comparison_points_of_interest.md)
for the full record.
