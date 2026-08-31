# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re
from typing import Any

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Groovy 4.0 / Gradle 8+",
        "last_updated": "2026-03-12",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA
    "extensions": [".groovy", ".gradle", ".gvy", ".gy", ".gsh"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES
    "exact_matches": ["Jenkinsfile"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION
    "discriminators": [
        "build.gradle",
        "settings.gradle",
        "gradle.properties",
        "pom.xml",
        ".java",
    ],
    # EXECUTION SIGNATURES
    "shebangs": ["groovy"],
    # LEXICAL FAMILY
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        "branch": re.compile(r"\b(if|else|switch|case|default|for|while|in|try|catch|finally)\b|\?"),
        # 2. args (Parameters / Coupling)
        # Captures standard method arguments and Groovy closures (x, y ->)
        # CRITICAL FIX: Anchored the parenthesis capture to method signatures so it
        # doesn't hallucinate every standard method call or if-statement in the file.
        # QUADRATIC BLOWUP FIX: the closure form's bare-identifier branch
        # (`[a-zA-Z_$][\w_$]*` with no \b anchor) got retried at every
        # position in a long `->`-less line -- O(n^2) (same bug found and
        # fixed in javascript's args). Bounded to {0,100}.
        # BUG FIX: the return-type stepper required an uppercase first
        # char, so lowercase primitive/void return types (`void foo()`,
        # `int add()`) never matched at all. It also excluded `,`, so
        # multi-param generic return types (`Map<String, Integer> foo()`)
        # broke after the first type param. Added a primitive-keyword
        # alternative and `,` to the class (same technique already used
        # by C#'s func_start for this exact bug class).
        # NESTED-DELIMITER FIX: the flat `[^)]*` param-list matcher broke
        # on one-level-nested calls in default values (`int y =
        # Math.max(3, 4)`), truncating at the inner `)`. Swapped for a
        # bounded one-level-nesting form.
        # BUG FIX (ambiguity sweep): despite the "CRITICAL FIX" comment's
        # claim, this had no exclusion for control-flow keywords at all,
        # so `if (x) {`, `while (x) {`, `switch (x) {`, `for (i in ...) {`,
        # `catch (Exception e) {`, and `synchronized(lock) {` were all
        # hallucinated as method parameter blocks (the condition
        # misread as an argument list). Added the same style of negative
        # lookahead func_start already uses.
        # #1209: parameter-list span wrapped in its own capture group in
        # both branches (was only reachable via group(0), the whole match
        # including the modifier/return-type/name prefix, or for
        # closures the leading "{") so detector.py's counter isolates
        # just the real parameter text -- the whole-match fallback
        # overcounted every zero/one-arg signature by +1 the same way
        # Python's did (#1199). Name group added to branch 1 too, purely
        # so existing extraction tests keep passing.
        "args": re.compile(
            r"^[ \t]*(?:(?:public|private|protected|static|final|def|abstract|@[A-Za-z0-9_.]+(?:\([^)]*\))?)[ \t\n]+){0,10}"
            r"(?:(?:(?:void|int|long|short|byte|char|float|double|boolean)(?:\[\])?|[a-zA-Z_][a-zA-Z0-9_<>\[\]?,\.]*)[ \t]+){0,3}"
            r"(?!(?:if|for|while|switch|catch|synchronized)\b)"
            r"([A-Za-z_$][\w_$]*|\"[^\"]*\"|'[^']*')[ \t\n]*(\((?:[^()]|\([^()]*\))*\))"
            r"|(?:\{[ \t\n]*)?(\((?:[^()]|\([^()]*\))*\)|[a-zA-Z_$][\w_$]{0,100}|)[ \t\n]*->",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        "structural_boundaries": re.compile(
            r"\b(def|class|interface|trait|enum|record|import|package|extends|implements|return|yield|sealed|permits|non-sealed)\b"
        ),
        # 4. func_start (Executable Logic Anchors)
        # HIGHLY TUNED: Uses Negative Lookahead to explicitly ignore Gradle DSL keywords (implementation, api, task)
        # Uses Positive Lookahead (?=[ \t]*\() to stop exactly at the function name without consuming punctuation.
        # BUG FIX: same return-type stepper bug as `args` above -- lowercase
        # primitive/void return types and multi-param generic return types
        # (`Map<String, Integer> foo()`) never matched. See `args` comment.
        # BUG FIX (ambiguity sweep): `synchronized` was missing from the
        # exclusion list, so a synchronized block (`synchronized(lock) {
        # ... }`) had the identical `identifier(...) {` shape as a real
        # method and was misclassified as a method declaration named
        # "synchronized". Confirmed pre-existing (not introduced by the
        # return-type fix above); added to the exclusion list alongside
        # the other control-flow-shaped keywords.
        # #1221: func_start used to have one unified branch whose
        # annotation/modifier prefix, generic bound, and return-type
        # were all independently optional -- so a bare call statement
        # (`next();`, zero prefix tokens) satisfied the exact same
        # shape as a real signature, since (like csharp/apex before
        # their own #789/#1221 fixes) this branch never verified a
        # trailing `{`/`;` terminator either, deferring entirely to
        # the pipeline's post-hoc brace search. Unlike apex (whose
        # func_start has NO legitimate zero-prefix case, so a simple
        # prefix-presence gate sufficed) groovy also has to keep
        # matching a genuinely bare constructor shape with no
        # modifier/return-type at all (`MyClass(String arg) {`,
        # covered by test_groovy.py) *and* a fully-prefixed signature
        # with no terminator at all (`abstract Map<String, Integer>
        # calculateTotals(List<Item> items)`, covered by
        # test_groovy_strict.py's deep-signature sweep) -- so neither
        # "always require closure" (javascript's/java's fix shape) nor
        # "always require a prefix" (apex's) works alone here. Split
        # instead: branch 1 requires >=1 prefix token (merging
        # modifier/annotation/generic-bound/return-type into one
        # alternation so "at least one of any kind" is expressible as
        # a single `{1,18}` repeat) and keeps the original lenient,
        # no-terminator-required lookahead; branch 2 requires
        # PRECISELY ZERO prefix tokens and, in exchange, must close
        # its (non-nested, same bound as `args`) parameter list and
        # reach a real `{` -- `next();` has neither a prefix nor a
        # closing `{`, so it satisfies neither branch.
        # BUG FIX (tri-comparison manual verification, 2026-08-31): "def" added to
        # both branches' exclusion lookahead. Spock feature methods routinely use a
        # quoted description as the method's own name (`def "invalidates cache upon
        # change to X"() { ... }`); detector.py's brace-safety pass (needed to keep
        # string content from corrupting brace-depth counting) correctly blanks that
        # quoted span to same-length whitespace before this regex ever runs against
        # it -- but with the name gone, branch 2 (zero-prefix) then matched the bare
        # "def" keyword itself as if IT were the function's own name (nothing in its
        # exclusion list stopped it, and "def" immediately followed by the
        # now-blanked-then-real `() {` satisfies branch 2's shape exactly), so every
        # quoted-description method was misnamed literally "def" instead of being
        # silently missed. Real Groovy code can never have "def" alone (with no name
        # at all after it) as a legitimate declaration, so this costs no real
        # coverage. Confirmed via a 188-file corpus scan: after this fix, the
        # remaining "def"-named entries in the named function list dropped to zero.
        "func_start": re.compile(
            r"^[ \t]*(?:"
            r"(?:(?:public|private|protected|static|final|def|abstract|@[A-Za-z0-9_.]+(?:\([^)]*\))?|<[^>]{0,100}(?:<[^>]{0,100}>[^>]{0,100}){0,5}>|(?:void|int|long|short|byte|char|float|double|boolean)(?:\[\])?|[a-zA-Z_][a-zA-Z0-9_<>\[\]?,\.]*)[ \t\n]+){1,18}"
            r"(?!(?:if|for|while|switch|catch|synchronized|new|return|class|interface|enum|trait|def|implementation|testImplementation|api|compileOnly|runtimeOnly|classpath|dependency|from|file|mavenCentral|plugins|dependencies|repositories|task|project|allprojects|subprojects|ext)\b)"
            r"([A-Za-z_$][\w_$]*|\"[^\"]*\"|'[^']*')(?=[ \t\n]*\()"
            r"|"
            r"(?!(?:if|for|while|switch|catch|synchronized|new|return|class|interface|enum|trait|def|implementation|testImplementation|api|compileOnly|runtimeOnly|classpath|dependency|from|file|mavenCentral|plugins|dependencies|repositories|task|project|allprojects|subprojects|ext)\b)"
            r"([A-Za-z_$][\w_$]*|\"[^\"]*\"|'[^']*')(?=[ \t\n]*\((?![^)]*\b[A-Za-z_$][\w$]*:(?!:))[^)]*\)[ \t\n]*(?:throws[ \t\n]+[\w.,<> \t\n]+)?[ \t\n]*\{)"
            r")",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        "class_start": re.compile(
            r"^[ \t]*(?:(?:public|private|protected|static|final|abstract|sealed|non-sealed|@[A-Za-z0-9_.]+(?:\([^)]*\))?)[ \t\n]+){0,10}"
            # BUG FIX (tri-comparison manual verification, 2026-08-31): the name
            # portion had no capturing group at all (pattern.groups == 0), so
            # detector.py's _resolve_class_start_match could never extract a real
            # name and silently fell back to "Anonymous_Class" for every single
            # match -- class *existence* was detected correctly (struct_class_start
            # counts were right), but the named class list was 100% synthetic
            # placeholders. Confirmed the only language in
            # _CLASS_START_NAMED_EXTRACTION_LANGS with this defect (checked all 36).
            r"(?:class|interface|trait|enum|record)\s+([A-Za-z_$][\w_$]*)",
            re.M,
        ),
        # --- PHASE 2: RISK ENGINE (Structural Integrity) ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(try|catch|finally|assert|instanceof|Optional)\b|@(?:Valid|Validated|NotNull|NonNull|Immutable)"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        "safety_bypasses": re.compile(
            r"\b(null)\b|return\s+null|catch\s*\(\s*(?:Exception|Throwable)\b|@SuppressWarnings|@SneakyThrows|\.get\(\)"
        ),
        # 8. danger (High-Risk Execution / System Calls)
        "high_risk_execution": re.compile(r"\b(System\.exit|Runtime\.getRuntime\(\)\.exec|execute)\b"),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(File|Files|Paths|FileReader|FileWriter|file|copy|sync|uri|url|Socket|Connection|ResultSet)\b"
        ),
        # 10. api (Public Surface Area)
        # Groovy classes/methods are implicitly public by default, making the whole file highly exposed.
        "api": re.compile(
            r"\b(public)\b|@(RestController|Controller|Service|Component|Bean|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\b"
        ),
        # 11. flux (State Mutation)
        # BUG FIX: the trailing bare `=` matched the first `=` of `==`,
        # miscounting every equality comparison (`result == expected`) as
        # an assignment. Added a negative lookahead to exclude `==`.
        "state_mutation": re.compile(r"^[ \t]*\w+(?:\.\w+)*[ \t]*=(?!=)|@(?:Setter|Data)\b", re.M),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Tuned to catch dead Gradle definitions and Groovy logic.
        # BUG FIX (Rule 12): groovy is `standard_block` (both `//` and
        # `/* */`), but this only ever fired on `//` -- every block-
        # commented-out construct (`/* class Foo {} */`) silently never
        # matched.
        "dead_code": re.compile(
            r"(?://|/\*)[ \t]*(?:def|class|void|if|for|while|import|implementation|compile|api|testImplementation)\b"
        ),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"/\*\*|@param|@return|@throws|@deprecated|@see"),
        # 14. test (Testing & Assertions)
        # Integrates Spock Framework keywords (given:, when:, then:, expect:) alongside JUnit.
        # BUG FIX (Rule 5): `^\s*` matches newlines in re.M mode, so the
        # Spock-label anchor could stretch across blank lines. Bounded to
        # `[ \t]*` (same-line whitespace only).
        "test": re.compile(
            r"@(?:Test|Before|After|BeforeEach|AfterEach|Mock)|assert\w*\s*\(|^[ \t]*(?:given|when|then|expect|setup|cleanup|where):",
            re.M,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(synchronized|Thread|Runnable|Future|ExecutorService|Promise|Atomic\w+|task)\b|@(?:Async|Scheduled)"
        ),
        # 16. ui_framework (UI / View Components)
        "ui_framework": re.compile(r"\b(SwingBuilder|JFrame|JPanel|ModelAndView|ModelMap|Model|UIComponent)\b"),
        # 17. closures (Closures / Anonymous Functions)
        # REDOS FIX: `[\w\s,]+` followed by a separate trailing `\s*`
        # let both consume the same whitespace run -- an unclosed `{`
        # followed by thousands of spaces caused catastrophic
        # backtracking (confirmed hang at n=2000). Collapsed into one
        # bounded, non-overlapping class before the required `->`
        # (same technique as kotlin's closures fix).
        # BUG FIX: idiomatic paren-less trailing closures (`list.each {
        # it }`, `.collect { it * 2 }`) have no `->` at all and never
        # matched either alternative, missing Groovy's single most
        # common closure shape. Added a dot-method-call-into-brace form.
        "closures": re.compile(r"\.\w+[ \t]*\{|\{[ \t\n]*[a-zA-Z_][a-zA-Z0-9_ \t\n,]{0,150}?->|->"),
        # 18. globals (Global / Shared State)
        "globals": re.compile(r"\b(System\.getProperty|System\.getenv|project\.ext)\b|@Value"),
        # 19. decorators (Decorators / Annotations)
        # NESTED-DELIMITER FIX (Rule 11): the flat `[^)]*` broke on one-
        # level-nested annotation args (`@Grab(..., version=resolve())`),
        # truncating at the inner `)`. Swapped for a bounded
        # one-level-nesting form.
        "decorators": re.compile(r"^[ \t]*@[\w.]+(?:\((?:[^()]|\([^()]*\))*\))?", re.M),
        # 20. generics (Generics / Type Parameters)
        # NESTED-DELIMITER FIX (Rule 11): the flat `[^>]*` broke on one-
        # level-nested generics (`Map<String, List<Id>>`), truncating at
        # the first `>` and leaving the real closing `>` unconsumed.
        # Swapped for a bounded one-level-nesting form.
        "generics": re.compile(r"<\s*[A-Z?][^<>]{0,100}(?:<[^<>]{0,100}>[^<>]{0,100})*>"),
        # 21. comprehensions (Iterators / Comprehensions)
        # BUG FIX: required a literal `(` right after the method name,
        # but Groovy's idiomatic call form for these is a paren-less
        # trailing closure (`list.each { it }`, `.collect { it * 2 }`)
        # -- the far more common shape never matched at all.
        "comprehensions": re.compile(
            r"\.(?:collect|find|findAll|grep|inject|each|eachWithIndex|map|filter|reduce)[ \t]*[({]"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(Math\.|BigDecimal|BigInteger|Random|SecureRandom)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Groovy's highly dynamic Meta-Object Protocol (MOP).
        "reflection_metaprogramming": re.compile(
            r"\b(invokeMethod|getProperty|setProperty|methodMissing|propertyMissing|ExpandoMetaClass|metaClass)\b"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"^[ \t]*import\s+(?:static[ \t]+)?[\w.]+;?", re.M),
        # BUG FIX: this key was entirely absent (not `None`), so Groovy
        # imports never fed the dependency graph at all -- unlike every
        # other JVM-family language here (e.g. java), which pairs
        # `import` with a `_dependency_capture` group. Groovy imports
        # follow the identical syntax, so this was a coverage gap, not
        # an intentional Strict-Feature-Parity `None`.
        "_dependency_capture": re.compile(
            r"^[ \t]*import[ \t\n\\]+(?:static[ \t\n\\]+)?([\w*]+(?:[ \t\n]*\.[ \t\n]*[\w*]+)*)[ \t]*;?", re.M
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"@author\s+(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # QUADRATIC BLOWUP FIX: `\d+` and the trailing `[^\]]*` both
        # greedily match digits with no closing `]` ever present, so an
        # unclosed `[SPEC-11111...` tag backtracks by re-scanning an
        # ever-shrinking suffix -- O(n^2) (confirmed ~4x slowdown per
        # input-size doubling; same bug class already fixed for shell
        # and sqlite's spec_exposure elsewhere in this file). Bounded to
        # {0,300}; real spec/audit tags don't get remotely that long.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        # BUG FIX: `@ResponseBody` is `@`-prefixed -- the shared leading
        # \b could only fire when a word char immediately preceded the
        # `@`, never true for how annotations are actually written.
        # Never matched at all.
        "ssr_boundaries": re.compile(
            r"\b(?:MarkupBuilder|StreamingMarkupBuilder|TemplateEngine|HttpServletRequest|HttpServletResponse)\b"
            r"|@ResponseBody"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # BUG FIX: `@EventListener` is `@`-prefixed -- same bug.
        "events": re.compile(r"\b(?:ApplicationEvent|ApplicationListener|publishEvent)\b|@EventListener"),
        # 33. dependency_injection (Dependency Injection / IoC)
        # Heavily captures Gradle plugin and dependency architecture.
        # BUG FIX: 7 of the 10 alternatives are `@`-prefixed Spring
        # annotations -- same bug, at scale.
        # BUG FIX (Rule 9): `plugins\s*\{` and `dependencies\s*\{` both
        # end on `{`, a non-word char, so the shared trailing `\b` could
        # never fire (no word/non-word transition between `{` and
        # whatever follows it) -- `plugins {` / `dependencies {` never
        # matched at all, the two most common Gradle DSL entry points.
        "dependency_injection": re.compile(
            r"\bapply\s+plugin\b|\bplugins\s*\{|\bdependencies\s*\{"
            r"|@Autowired|@Inject|@Component|@Service|@Repository|@Bean|@Configuration"
        ),
        # 34. macros
        "macros": None,
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": None,
        # 36. memory_alloc
        "memory_alloc": None,
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(log|logger|LOGGER|LoggerFactory)\.(?:info|error|warn|warning|debug|trace)\b|@Slf4j|@Log4j2|@Log"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
        # BUG FIX: `\.printStackTrace\(\)` ends on `)` (non-word), so
        # the shared trailing \b could never fire. Never matched.
        "debug_prints": re.compile(
            r"\b(?:println|print|printf|System\.out\.print|System\.err\.print)\b|\.printStackTrace\(\)"
        ),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            r"\bas\s+[A-Z]\w*|\(\s*(?:int|long|short|byte|char|float|double|boolean|[A-Z][A-Za-z0-9_]*)\s*\)\s*[a-zA-Z_$]"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|System\.exit|GradleException)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(Thread\.sleep|sleep)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        # EXCLUDES `<<` and `>>` because Groovy heavily overloads `<<` for list/stream appending.
        "bitwise_ops": re.compile(r"\^|~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(synchronized|ReentrantLock|ReadWriteLock|Semaphore|Lock|Mutex)\b"),
        # 45. immutability_locks (Immutability Constraints)
        # BUG FIX: `@Immutable` is `@`-prefixed -- same leading-\b bug.
        "immutability_locks": re.compile(r"\bfinal\b|@Immutable"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(close|dispose|shutdown)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        "encapsulation": re.compile(r"\b(private|protected)\b"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(addListener|on[A-Z]\w*|subscribe)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"@(?:Ignore|Disabled|PendingFeature)\b|mock\s*\(|spy\s*\("),
    },
}
