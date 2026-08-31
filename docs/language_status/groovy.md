# Groovy — Structural Signature Coverage

Snapshot generated 2026-08-31 against `main`. Source:
`LANGUAGE_DEFINITIONS["groovy"]` in
`gitgalaxy/standards/language_standards/languages/groovy.py`,
`tests/extraction/languages/test_groovy.py` / `test_groovy_strict.py`, closed GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

**No tree-sitter ground truth exists for this language.** `tests/tools/tree_sitter_accuracy_audit.py`
used to carry a `groovy` entry in `NODE_MAPS`, but a direct inspection during this session's
tri-comparison manual-verification pass (2026-08-31) confirmed `tree-sitter-language-pack`'s
`"groovy"` grammar has no `class_declaration`/`method_declaration` node type at all — `class Foo {`
parses into generic command/unit/block soup (3.2% ERROR rate across a 30-file/13K-node sample), and
the two node types the old mapping used (`"func"`, `"generics_class"`) turned out to be semantically
wrong rather than merely imprecise: `"func"` nodes are call expressions
(`getLogger(JiraService.class)`), not definitions, and `"generics_class"` nodes are generic type
*usage* (`Map<String, X>`), not class declarations. The entry was removed (see the rationale comment
immediately after `NODE_MAPS = {...}` closes in that file) and replaced with an independent,
grep-based ground-truth cross-check across a 188-file corpus instead — that verification is what
produced the three engine fixes referenced in §7 below and is written up in full in §9.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Groovy 4.0 / Gradle 8+ |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-03-12 |
| `lexical_family` | `standard_block` (both `//` line comments and `/* */` block comments — `dead_code`'s inline comment notes this was a real bug once: the rule originally only fired on `//`, silently missing every block-commented-out construct) |
| Structural signature keys wired | 44 / 48 (4 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_groovy.py`) | 53 |
| Strict-signature tests (`test_groovy_strict.py`) | 91 |
| Total dedicated Groovy test cases | 144 |

## 2. Identification surface

- **Extensions:** `.groovy .gradle .gvy .gy .gsh` — the canonical extension, Gradle build scripts,
  and Groovy's two less-common short forms.
- **Exact filenames:** `Jenkinsfile` — Jenkins Pipeline DSL scripts, extensionless by convention.
- **Discriminators:** `build.gradle`, `settings.gradle`, `gradle.properties`, `pom.xml`, `.java` —
  Gradle-ecosystem anchors, plus `.java` as a disambiguator against the JVM sibling language it
  most often sits alongside.
- **Shebangs:** `groovy`.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py`/`how_to_add_a_language.md` use (groovy's own
file labels them slightly differently in its inline comments — e.g. "RISK ENGINE" for what the
schema doc calls "Safety & Execution Risk" — but the underlying key set is the same). Description
is what Groovy's *actual* regex matches, not the generic cross-language definition. Groovy's
`rules` dict has 48 total keys (fewer than e.g. python's 64) — this is a difference in
`blueprint_version` (v5.0 vs python's 6.30), not a gap; keys like `lazy_evaluation`,
`vectorized_math`, or the AI/ML extension pack simply aren't part of this language's schema at all,
which is distinct from an explicit `None` (see §4).

**Topology & structure**
| Key | What it captures for Groovy |
|---|---|
| `branch` | `if else switch case default for while in try catch finally` plus a bare `?` (ternary) |
| `args` | Method/constructor parameter blocks and closure parameter lists (`x, y ->`), anchored to real signatures via a negative lookahead that excludes control-flow keywords (`if for while switch catch synchronized`) so a condition's parenthesized expression isn't misread as a parameter list; handles one level of nested parens in default values (`int y = Math.max(3, 4)`) and multi-param generic return types (`Map<String, Integer> foo()`) |
| `structural_boundaries` | `def class interface trait enum record import package extends implements return yield sealed permits non-sealed` |
| `func_start` | Anchors method/constructor signatures via two branches: branch 1 requires at least one modifier/annotation/generic-bound/return-type prefix token (lenient — no trailing `{`/`;` required); branch 2 permits precisely zero prefix tokens (covering bare constructors like `MyClass(String arg) {`) but in exchange must fully close a non-nested parameter list and reach a real `{`. Both branches exclude a long list of control-flow and Gradle-DSL keywords (`if for while switch catch synchronized new return class interface enum trait def implementation testImplementation api compileOnly runtimeOnly classpath dependency from file mavenCentral plugins dependencies repositories task project allprojects subprojects ext`) — `def` was added to that exclusion list in this session's tri-comparison pass so a Spock quoted-description feature method (`def "invalidates cache upon change to X"() {`) can never be misnamed literally `"def"` |
| `class_start` | Anchors `class interface trait enum record` + name, with an optional modifier/annotation prefix; the name is captured into a real group (fixed this session — previously had zero capturing groups, so every match silently fell back to the generic `"Anonymous_Class"` placeholder even though class *existence* counts were correct) |

**Safety & risk**
| Key | What it captures for Groovy |
|---|---|
| `safety` | `try catch finally assert instanceof Optional` plus `@Valid @Validated @NotNull @NonNull @Immutable` |
| `safety_bypasses` | Bare `null`, `return null`, `catch (Exception\|Throwable ...)`, `@SuppressWarnings`, `@SneakyThrows`, `.get()` |
| `high_risk_execution` | `System.exit`, `Runtime.getRuntime().exec`, `execute` |
| `io` | `File Files Paths FileReader FileWriter file copy sync uri url Socket Connection ResultSet` |
| `api` | Bare `public` keyword plus Spring-style route/component annotations (`@RestController @Controller @Service @Component @Bean @RequestMapping @GetMapping @PostMapping @PutMapping @DeleteMapping @PatchMapping`) — Groovy methods/classes are implicitly public by default, so this key intentionally treats the whole file as exposed unless a narrower modifier is present |
| `state_mutation` | Line-leading `identifier(.identifier)* =` assignment (excluding `==` via a negative lookahead — an earlier bug matched the first `=` of every equality comparison) plus `@Setter`/`@Data` |
| `dead_code` | `//`- or `/* */`-prefixed `def class void if for while import implementation compile api testImplementation` |
| `doc` | `/**`, `@param @return @throws @deprecated @see` |
| `test` | JUnit-style `@Test @Before @After @BeforeEach @AfterEach @Mock`, `assert\w*\s*\(`, and Spock's block labels (`given: when: then: expect: setup: cleanup: where:`) anchored to same-line leading whitespace only (bounded to `[ \t]*` after a bug where `\s*` let the anchor stretch across blank lines in multiline mode) |

**Architecture & domain sensors**
| Key | What it captures for Groovy |
|---|---|
| `concurrency` | `synchronized Thread Runnable Future ExecutorService Promise Atomic\w+ task` plus `@Async @Scheduled` |
| `ui_framework` | `SwingBuilder JFrame JPanel ModelAndView ModelMap Model UIComponent` |
| `closures` | Groovy's idiomatic paren-less trailing closure (`.each { it }`, `.collect { it * 2 }` — a dot-method-call directly into a brace), a bracketed closure with a bounded parameter list before `->` (`{ x, y -> ... }`), or a bare `->` |
| `globals` | `System.getProperty System.getenv project.ext` plus `@Value` |
| `decorators` | Any line-leading `@Name(...)` annotation, with bounded one-level-nesting in the argument parens (`@Grab(..., version=resolve())`) |
| `generics` | `<...>` type-parameter syntax with bounded one-level-nesting (`Map<String, List<Id>>`) |
| `comprehensions` | `.collect .find .findAll .grep .inject .each .eachWithIndex .map .filter .reduce` followed by `(` or `{` — covers both the call-with-parens form and Groovy's far more common paren-less trailing-closure form |
| `scientific` | `Math. BigDecimal BigInteger Random SecureRandom` |
| `reflection_metaprogramming` | Groovy's Meta-Object Protocol hooks: `invokeMethod getProperty setProperty methodMissing propertyMissing ExpandoMetaClass metaClass` |
| `import` | `import [static] dotted.path[;]` |
| `_dependency_capture` | Extracts the dotted module path (including a wildcard `*`) from the same import statement, feeding the dependency DAG — this key was entirely absent (not `None`) until fixed as a real coverage gap: every other JVM-family language here pairs `import` with `_dependency_capture`, and Groovy imports follow identical syntax |
| `ownership` | `@author <name>` |

**Specialized subsystems**
| Key | What it captures for Groovy |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]` / `[spec ...]` / `[audit ...]` traceability tags, bounded to 300 chars (a ReDoS fix — the original unbounded `[^\]]*` form was copy-pasted across 28 languages, see §7) |
| `ssr_boundaries` | `MarkupBuilder StreamingMarkupBuilder TemplateEngine HttpServletRequest HttpServletResponse` plus `@ResponseBody` |
| `events` | `ApplicationEvent ApplicationListener publishEvent` plus `@EventListener` |
| `dependency_injection` | `apply plugin`, `plugins {`, `dependencies {` (Gradle DSL entry points) plus Spring-style `@Autowired @Inject @Component @Service @Repository @Bean @Configuration` |

**Resource management & stability**
| Key | What it captures for Groovy |
|---|---|
| `telemetry` | `log logger LOGGER LoggerFactory` `.info/.error/.warn/.warning/.debug/.trace` plus `@Slf4j @Log4j2 @Log` |
| `debug_prints` | `println print printf System.out.print System.err.print` plus `.printStackTrace()` |
| `explicit_casts` | `as Type` coercion syntax or a C-style `(Type) identifier` cast |
| `panics_and_aborts` | `throw System.exit GradleException` |
| `thread_sleeps` | `Thread.sleep sleep` |
| `bitwise_ops` | `^` and `~` only — `<<`/`>>` are deliberately excluded because Groovy heavily overloads `<<` for list/stream appending |
| `sync_locks` | `synchronized ReentrantLock ReadWriteLock Semaphore Lock Mutex` |
| `immutability_locks` | `final` plus `@Immutable` |
| `cleanup` | `close dispose shutdown` followed by `(` |
| `encapsulation` | `private protected` |
| `listeners` | `addListener on[A-Z]\w* subscribe` |
| `test_skip` | `@Ignore @Disabled @PendingFeature` plus `mock(` / `spy(` |

Several of the annotation-based alternatives above (`api`, `dead_code`→n/a, `ssr_boundaries`,
`events`, `dependency_injection`, `debug_prints`, `immutability_locks`) share a documented bug
class: a naive shared trailing `\b` after an alternation can't fire when the preceding character
is `@` or a non-word character like `{`/`)`, so several `@`-prefixed annotations and brace-ending
Gradle DSL keywords (`plugins {`, `dependencies {`) never matched at all until fixed — noted inline
throughout `groovy.py` as "same leading-`\b` bug" / "same bug, at scale".

## 4. What GitGalaxy explicitly does not track

Four keys are hard-set to `None` in Groovy's `rules` dict:

- **`macros`** — no inline comment beyond the key name itself (unlike python's `None` entries,
  which each carry a one-line reason). Consistent with every other JVM-hosted language in this
  registry (`java`, `kotlin`, `csharp`) having the same `None`: the JVM has no C-style
  preprocessor, so there's nothing for this key to match.
- **`pointers`** (labelled "Pointer Arithmetic / Memory Addressing" in the inline comment) — same
  no-reason-given pattern; Groovy, like every JVM language here, has no raw pointer/address
  arithmetic construct.
- **`memory_alloc`** — no inline reason given; consistent with the JVM's GC-managed memory model,
  same as `java`/`kotlin`/`csharp`.
- **`inline_asm`** — no inline reason given; no native inline-assembly construct on the JVM.

## 5. Known limitations (accepted, not fixed)

**No `known_limitation`-named tests exist** in `test_groovy.py` or `test_groovy_strict.py` as of
this writing (confirmed via `grep -n "known_limitation"` across both files — zero matches).

One real, current gap is documented instead as
**[#2530](https://github.com/squid-protocol/gitgalaxy/issues/2530) (OPEN)** — filed during this
same session's tri-comparison manual-verification pass, and deliberately left unfixed rather than
patched with a fragile denylist:

- **MarkupBuilder / Jenkins-Pipeline-DSL trailing-closure calls misdetected as function
  definitions.** `func_start`'s zero-prefix branch (needed to match real bare constructors like
  `MyClass(String arg) {`) is syntactically indistinguishable from Groovy's extremely common
  "call a builder method with a named-argument map plus a trailing closure" idiom —
  `button(name: "clear", type: "submit") { raw _("Dismiss") }`,
  `l.layout(title: "...") { ... }`, `stage("Build") { ... }`. This is the standard
  `MarkupBuilder`/`NodeBuilder` DSL shape (used pervasively in Jenkins's own `.groovy` view
  templates, which replaced Jelly) and also covers Jenkins Pipeline steps (`stage`, `node`, `dir`,
  `timeout`) and Gradle DSL blocks. `func_start` already excludes a hand-picked list of known
  Gradle keywords for exactly this reason, but an arbitrary builder/tag method name (`div`, `a`,
  `button`, `li`, ...) can't be enumerated the same way — the set of possible builder tag names is
  unbounded. Measured against the `language-crucible/data/groovy/jenkins_view_groovy/` corpus (29
  files): 57 of 718 total named functions found across the whole Groovy corpus (~8%) come from
  this one folder, and essentially all of them are DSL/builder calls misread as definitions
  (`div`×9, `span`×7, `li`×7, `a`×7, `ul`×4, `stage`×4, `section`×4, `node`×3, and others), with two
  qualified-form cases (`l.layout(...)`, `l.main_panel()`) falling back to the generic
  `Unknown_Block` name entirely. Judged a real grammar ambiguity rather than a deterministic
  defect — a correct fix needs either a curated (necessarily incomplete) denylist of
  HTML/XML-tag-shaped builder names, or a smarter heuristic (e.g. treating a named-argument map as
  the sole/first parameter as a builder-call signal a real constructor rarely has), which needs its
  own design pass and full-corpus verification rather than a drive-by regex tweak.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 53 tests in
  `tests/extraction/languages/test_groovy.py` — valid/invalid/pathological cases per rule. Fully
  migrated to the per-language file (epic #813, issue #829) — nothing left in the old monolithic
  gauntlet files for Groovy.
- **Strict signature suite** (all other wired keys): 91 tests in
  `tests/extraction/languages/test_groovy_strict.py` — positive match, negative/false-positive
  match, cross-rule ambiguity (including 3 explicit intentional-overlap tests:
  `high_risk_execution`/`panics_and_aborts` sharing `System.exit`, `closures`/`comprehensions`
  sharing the trailing-closure shape, and a `dead_code`/`doc` no-false-collision check), and
  ReDoS-immunity checks per signature (epic #518, issue #584). Combined total: 144 tests.

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#518](https://github.com/squid-protocol/gitgalaxy/issues/518) — Epic: Strict & exact regex test
  coverage for all structural signatures, per language.
- [#813](https://github.com/squid-protocol/gitgalaxy/issues/813) — Epic: Harden the four extraction
  gauntlets (function/args/class/dependency) per language.
- [#584](https://github.com/squid-protocol/gitgalaxy/issues/584) — Strict parsing tests for Groovy
  structural signatures (epic #518). Also removed the dead `_line_anchor`/`_inline_comment`/
  `_block_start`/`_block_end` checklist items (confirmed never read anywhere in `gitgalaxy/` —
  comment-stripping is driven entirely by `lexical_family` against `gitgalaxy_config.py`'s
  family-level table, not per-language keys).
- [#829](https://github.com/squid-protocol/gitgalaxy/issues/829) — Extraction hardening for Groovy
  (epic #813): migrated the four extraction gauntlets into `test_groovy.py`.

**Cross-language fixes that touched Groovy along the way:**
- [#713](https://github.com/squid-protocol/gitgalaxy/issues/713) — `spec_exposure`'s unbounded
  `[^\]]*` ReDoS pattern, copy-pasted across 28 languages; Groovy was already fixed by the time
  this issue was filed (found while closing #584), so this issue tracked the other 27.
- [#1041](https://github.com/squid-protocol/gitgalaxy/issues/1041) — Nested functions were silently
  dropped from extraction for every Mode B/brace-family language routed through the shared
  extractor path, Groovy included.
- [#1209](https://github.com/squid-protocol/gitgalaxy/issues/1209), fixed via PR
  [#1216](https://github.com/squid-protocol/gitgalaxy/pull/1216) — `args`' parameter-list span had
  no capturing group of its own in 25 languages (a regression from #1199's Python fix), so
  detector.py's counter fell back to `group(0)` — the whole match including modifier/return-type
  prefix — overcounting every zero/one-arg signature by +1. Groovy was one of the 7 languages fixed
  in PR #1216 (alongside csharp/java/javascript/typescript/ruby/powershell).
- [#1221](https://github.com/squid-protocol/gitgalaxy/issues/1221), fixed via
  [#1800](https://github.com/squid-protocol/gitgalaxy/pull/1800) — `func_start` was missing the
  `args` regex's "Invocation Shield": a bare call statement (`next();`, zero prefix tokens, no
  terminator check) satisfied the same shape as a real signature. Groovy was one of 7 affected
  languages (`javascript typescript java csharp apex dart groovy`); fixed with the two-branch split
  described in §3 above (neither "always require a trailing `{`" nor "always require a prefix"
  alone works for Groovy, since it needs to keep matching both a genuinely bare constructor and a
  fully-prefixed signature with no terminator at all).
- [#1264](https://github.com/squid-protocol/gitgalaxy/issues/1264) — Fixed `detector.py`'s
  named-entity class extractor to reuse each language's own `class_start` rule instead of one
  hardcoded, language-agnostic regex, scoped to an allowlist
  (`_CLASS_START_NAMED_EXTRACTION_LANGS`) of languages verified clean against the
  `language-crucible` corpus via tree-sitter — Groovy was one of the 18 languages on that allowlist
  (per [#1295](https://github.com/squid-protocol/gitgalaxy/issues/1295)'s summary of #1264's scope).
  Notably, that "verified clean" allowlist membership didn't catch the zero-capture-group defect
  fixed this session (§3/§5) — class *existence* counts were correct so the tree-sitter comparison
  passed, but the *named* class list was 100% synthetic `"Anonymous_Class"` placeholders the whole
  time.

**Real defects found via this session's tri-comparison manual-verification work (2026-08-31),
found and fixed directly in the same pass rather than filed-then-fixed separately (see §9 for the
full write-up):**
- The `class_start` zero-capturing-group defect (§3/§4 above).
- A Prism triple-quoted-string (`"""`/`'''`) shielding gap specific to Groovy — `standard_block`'s
  shared comment-stripping only ever handled `//`/`/* */`, leaving multi-line string mass
  (Gradle integration-test fixture strings, Spock compiler-smoke-test source samples) completely
  unshielded, so `class_start`/`func_start` could match real-looking text *inside* a string literal
  and a stray/mismatched leftover quote could desync brace-counting downstream.
- The `func_start`/`_extract_name` "`def`"-as-bare-name collision for Spock quoted feature-method
  descriptions (`def "invalidates cache upon change to X"() { ... }`) — see §3's `func_start` and
  `class_start` rows above for the mechanism.

The one remaining gap this same pass found but deliberately did **not** fix is
[#2530](https://github.com/squid-protocol/gitgalaxy/issues/2530) — see §5.

Search performed via `gh issue list --search 'in:title "Extraction hardening: groovy"'` /
`'in:title "Strict parsing tests: `groovy`"'` / `'in:title groovy'` (2026-08-31) — the broader third
query also surfaced the ~50 per-signature "Strict parsing tests: `<key>` structural signature
across all languages" epic-518 sub-issues (#519–#566), which are generic across all languages and
not groovy-specific beyond being superseded by the consolidated #584; excluded here as noise for
this doc's purposes.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Three repos from the `v2.4.7` batch, chosen to cover Groovy's three distinct real-world roles
(Gradle build-tooling DSL, Jenkins Pipeline/view DSL, and the Spock testing framework whose
block-label syntax `test` explicitly detects):

- **[`gradle`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/gradle/gradle_galaxy_llm.md)**
  — Gradle's own build-tool source, the reference implementation of the `.gradle` DSL this
  language's `dependency_injection`/Gradle-keyword-exclusion logic is tuned against. Scanned in
  53.47s.
- **[`jenkins`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/jenkins/jenkins_galaxy_llm.md)**
  — the Jenkins core repo, source of the extensionless `Jenkinsfile` exact-match and the
  `.groovy` view-template files (`jenkins_view_groovy/`) that motivated the MarkupBuilder
  false-positive investigation in §5/issue #2530. Scanned in 16.41s.
- **[`spock`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/spock/spock_galaxy_llm.md)**
  — the Spock testing framework's own repo, the canonical corpus for the `test` rule's
  `given:`/`when:`/`then:`/`expect:`/`setup:`/`cleanup:`/`where:` block-label detection. Scanned
  in 3.44s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

## 9. Measured accuracy (tri-comparison manual verification, 2026-08-31)

### Why this is a manual verification, not a standard tri-comparison

tree-sitter has no usable grammar for Groovy despite `tree_sitter_language_pack` nominally
shipping a "groovy" grammar that loads without error. Direct inspection (parsing a 30-file/13K-node
sample from the corpus below) found no `class_declaration`/`method_declaration` node type at all —
`class Foo {` parses into a generic `command`/`unit`/`block` soup with a 3.2% `ERROR` rate. The two
node types this repo's `tree_sitter_accuracy_audit.py` used to map groovy to were semantically
wrong, not just imprecise: `"func"` nodes are **call expressions**
(`getLogger(JiraService.class)`, `ConnectionPool(5, 60, TimeUnit.SECONDS)` — both invocations, not
definitions), and `"generics_class"` nodes are **generic type usage** (`Map<String, X>`,
`List<JiraIssue>`), not class declarations. This is why the committed baseline read
`real_functions=0`/`real_classes=0` against hundreds of genuine GitGalaxy detections it had no way
to corroborate. `ctags` has zero Groovy support at all (confirmed via `ctags --list-languages` —
absent from all 135 supported languages). Groovy was moved out of `NODE_MAPS` into GitGalaxy's
`_gg_only_langs` treatment as a result (see `tree_sitter_accuracy_audit.py`'s own exclusion
comment, right after `NODE_MAPS = {...}` closes, for the full rationale) — this is the same
category abap/dockerfile/jcl/livecode/yaml are already in, just discovered later.

With no automated cross-tool ground truth available, this section instead documents a manual
verification: an independent grep-based ground-truth scan across the full corpus (built from
Groovy grammar knowledge, sharing no implementation with GitGalaxy's own `func_start`/`class_start`
regexes), cross-checked against the real pipeline's actual database output — not just the raw
regex run in isolation — per this repo's `tri-comparison-ledger-sweep` skill's manual-verification
fallback procedure.

### Corpus

`language-crucible` v1.2.0 pin, `data/groovy/` — 188 real `.groovy`/`Jenkinsfile` files across 9
real-world repositories: Apache Fineract's Gradle plugin, Gradle's own build-logic and
integration-test sources, Spock's core/smoke-test/spec suites, and Jenkins's own `.groovy` view
templates (Jelly's Groovy-based successor). ~19,000 lines scanned.

### Method

1. Ran the real `galaxyscope` pipeline (not the regex in isolation) against the corpus and
   compared the raw structural signal (`file_data.struct_func_start`/`struct_class_start`) against
   the named list actually reaching consumers (`function_data`/`class_data`) — this is what
   surfaced the first two defects below (a signal/name split for classes, and a signal/name gap
   for functions).
2. Built an independent candidate-declaration scanner (regex patterns written from Groovy grammar
   knowledge, not derived from or shared with GitGalaxy's own `func_start`/`class_start`), and
   diffed its findings against GitGalaxy's actual named output, by name, across every one of the
   188 files.
3. Where the independent scanner disagreed, traced each case back to source — tracking
   triple-quoted (`"""`/`'''`) string-literal spans by quote-parity so fixture/example code
   embedded in a multi-line string (common in this corpus: Gradle integration tests generate
   throwaway build scripts as string templates, and Spock's own compiler-smoke-tests feed example
   Groovy source through `compiler.compileSpecBody("""...""")`) wasn't mistaken for real top-level
   declarations by either side.
4. Manually spot-checked 50+ randomly-sampled named functions/classes against their real source
   line for precision (false positives), independent of the recall pass above.

### Results

| Signal | Raw structural count | Named (pre-fix) | Named (post-fix) | Independent-grep recall gap (post-fix) | Precision (post-fix) |
|---|---|---|---|---|---|
| `func_start` | 851 | 721 (1003 raw pre-shielding-fix; 282 silently dropped, ~57% misnamed `"def"`/truncated where present) | 718 | 0 unexplained | 661/718 (92.1%) — see false-positive class below |
| `class_start` | 222 | 286 (100% misnamed `"Anonymous_Class"`; included ~64 fixture-string false positives before the Prism fix) | 222 | 0 unexplained | 222/222 (100%) |

Recall: zero real declarations found by the independent ground-truth scanner and missed by
GitGalaxy anywhere in the 188-file corpus, for either signal, after accounting for triple-quoted
fixture-text spans on both sides.

Precision: functions carry one confirmed, unfixed false-positive class (57 of 718, ~8%) — see
below. Classes have none found in spot-checking (`class_start` requires an explicit
`class`/`interface`/`trait`/`enum`/`record` keyword, a far more constrained grammar shape than
`func_start`'s zero-prefix branch, so the ambiguity affecting functions doesn't apply here).

### Three confirmed GitGalaxy engine defects found and fixed

1. **`class_start` had zero capture groups.** `pattern.groups() == 0` — the name portion
   (`[A-Za-z_$][\w_$]*`) at the end of the pattern wasn't wrapped in parentheses at all. Class
   *existence* was detected correctly (`struct_class_start`'s raw count matched real declarations
   exactly), but `detector.py`'s `_resolve_class_start_match` could never extract a name from a
   group that didn't exist, so every one of the 286 pre-fix `class_data` rows was literally named
   the generic placeholder `"Anonymous_Class"` — confirmed the only language in
   `_CLASS_START_NAMED_EXTRACTION_LANGS` with this defect (checked all 36). Fix: wrapped the name
   in a capturing group.
2. **Prism never shielded Groovy's `"""`/`'''` multi-line strings.** `PRISM_CONFIG`'s shared
   `SHIELD_PATTERN` only handles single-line `"..."`/`'...'`/`` `...` `` strings; nothing in the
   pipeline shielded Groovy's triple-quoted GStrings before this fix, so code-shaped fixture text
   embedded in one (Gradle build-script snippets generated by integration tests, Spock's own
   compiler-smoke-test source samples) leaked straight into the real code stream. This corrupted
   extraction for the *rest* of the file, not just the string span itself: unshielded `{`/`}`
   characters inside the fixture text desynced the brace-depth counter, dropping or misattributing
   real declarations after the string closed. Fix: a new `_strip_groovy_triple_quoted_strings`
   method in `prism.py`, mirroring the existing `_strip_powershell_herestrings`/
   `_mask_lua_long_brackets` idiom (blank the span to same-length whitespace, capture it to the
   documentation stream, preserve line numbers).
3. **`func_start`'s zero-prefix branch matched the bare `def` keyword as a function name.** Spock
   feature methods routinely use a quoted description as their own name (`def "invalidates cache
   upon change to X"() { ... }`). `detector.py`'s brace-safety pass (`_build_brace_safe_stream`,
   needed so a literal `{`/`}` inside a string can't fool the brace-depth counter) correctly
   blanked that quoted span — but with the name gone, `func_start`'s zero-prefix branch then
   matched the bare `def` token immediately followed by the now-blanked-then-real `() {`, exactly
   satisfying its own shape. Every quoted-description method was misnamed literally `"def"`
   instead of being silently missed. Two-part fix: excluded `def` from both branches' exclusion
   lookahead (defense in depth — real Groovy can never have `def` alone with no name at all as a
   legitimate declaration), and — the fix that actually restores the real name — preserved a
   quoted string immediately following `def` in `_build_brace_safe_stream`'s shielding pass
   instead of blanking it (mirroring the existing `zig`/`@"..."` exception in the same function).
   A fourth, related defect was found one layer up: `detector.py`'s `_extract_name` — a generic
   "last-token" heuristic used across every language — silently reduced a quoted multi-word
   description down to just its last word (confirmed via `LANGUAGE_DEFINITIONS` scan: groovy is
   currently the *only* language whose `func_start` captures a quoted name at all, so this fix is
   zero-blast-radius elsewhere). Fixed with an early-return fast path that preserves a fully
   quoted `raw_match` verbatim, matching the convention `tests/extraction/languages/test_groovy.py`
   already asserts for the regex's own captured group.

All three verified with the full chain: standalone regex re-test, the extraction gauntlet + strict
test suite, `ruff`/`mypy` audits, the full pytest suite (7145 passed), and the full ~80-repo
`crucible_check.py` differential scan (2109 diffs — 1587 directly groovy-attributable, the
remaining 522 all tiny ripple, <1% relative, from the shared force-directed graph layout
recomputing and global risk-normalization shifting slightly; both golden master fixtures
re-blessed after confirming no diff traced to an unrelated language).

### One confirmed, unfixed false-positive class

**MarkupBuilder/Jenkins-Pipeline-DSL calls with a trailing closure are syntactically
indistinguishable from a zero-prefix function declaration.** `a(href: "x", class: "y") { ... }`,
`button(name: "clear") { ... }`, `l.layout(title: "...") { ... }` are Groovy's standard builder-DSL
call shape (a named-argument map plus a trailing closure) — `func_start`'s zero-prefix branch
(needed for real bare constructors like `MyClass(String arg) {`) can't tell these apart from a real
declaration at the lexical level. Confirmed concentrated entirely in the `jenkins_view_groovy/`
corpus folder (29 files, Jenkins's own `.groovy` UI templates): 57 of the 718 total named functions
(~8%) are this shape — `div`(9), `span`(7), `li`(7), `a`(7), `ul`(4), `stage`(4), `section`(4),
`node`(3), `withChecks`(2), `dir`(2), `Unknown_Block`(2, the qualified `l.layout(...)`/
`l.main_panel()` form), `timeout`/`table`/`recordIssues`/`realtimeJUnit`/`form`/`button` (1 each).
Filed as [#2530](https://github.com/squid-protocol/gitgalaxy/issues/2530) rather than fixed in this
pass — unlike the three defects above, this needs a real design decision (a curated
builder-tag-name denylist is fragile and incomplete by construction; a smarter heuristic like
"named-argument-map-shaped first parameter" needs its own full-corpus verification to confirm it
doesn't trade these false positives for new false negatives on real bare constructors).

### Ledger and manual-verification record

The pre-existing ledger shape `groovy/function/existence/agree[gitgalaxy]_vs[tree_sitter]` (721
occurrences, unvalidated) was reviewed and closed out with `status: validated`,
`credit_tools: ["gitgalaxy"]` (tree-sitter's non-corroboration is a confirmed structural limitation
in the tool itself, not evidence against GitGalaxy) — see
`docs/self_scan/tri_comparison_ledger.json`. It now reads `still_reproduces: false` since groovy no
longer goes through tree-sitter comparison at all. The verified counts (661/718 functions,
222/222 classes) are recorded in `docs/self_scan/manual_verification.json` under `"groovy"`,
following the same `**`-badge convention abap/dockerfile/jcl/livecode/yaml already use.
