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
        "target_version": "Java 25 (Project Loom, Panama, Amber) / Spring Boot 3.4+",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, server-side templates, and embedded scripting formats.
    "extensions": [".java", ".jav", ".jsp", ".jspf", ".jspx", ".jws", ".bsh"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
    "discriminators": [
        ".java",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "build.xml",
        "mvnw",
        "gradlew",
        ".classpath",
        ".project",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["java", "jshell"],
    # UPGRADED: Maps to Family 1 (Standard C)
    # Rationale: Uses '//' for line-level literature; multi-line literature
    # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Includes modern switch expressions (yield) and pattern guards (when).
        # EXCLUDES: Exceptions (throw) - moved to bailout_hits.
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|while|do|catch|finally|continue|break|yield|try|when)\b|\?|:"
        ),
        # 2. args (Parameters / Coupling)
        # Captures method/constructor params and lambdas. Bounded to prevent ReDoS.
        "args": re.compile(
            # =====================================================================
            # [ THE GHOST ARGS SHIELD (JAVA) ]
            # Same architectural fix as C#. Demands structural proof to separate
            # definitions from invocations.
            # Branch 1: Standard Methods MUST have a return type.
            # Branch 2: Constructors MUST be anchored to `{` or `throws`.
            # Branch 3: Standard lambdas and method references `::`.
            # QUADRATIC BLOWUP FIX: Branch 3's bare-identifier lambda form
            # (`[a-zA-Z_$][\w_$]*` with no \b anchor, unlike Branches 1/2
            # which are `^`-anchored) got retried at every position in a
            # long `->`-less line, backtracking O(n) per position for
            # O(n^2) total (same bug found and fixed in javascript's args).
            # Bounded to {0,100}; real identifiers don't get that long.
            # RULE 11 FIX (epic #813/#816): Branch 1's generic-bound modifier
            # alternative was a flat `<[^>]*>`, truncating at the first `>` and
            # breaking any single-line one-level-nested generic bound (e.g.
            # `public static <T, U extends Comparable<U>> T Foo(T a, U b) {` --
            # the same Rule 11 shape already fixed elsewhere; see
            # how_to_add_a_language.md). Widened to the established
            # one-level-nesting idiom `<(?:[^<>]|<[^<>]*>)*>`.
            # =====================================================================
            # #1209: parameter-list span wrapped in its own capture group
            # in branches 1/2/3 (was only reachable via group(0), the
            # whole match including the annotation/modifier/return-type/
            # name prefix, or for lambdas nothing at all) so detector.py's
            # counter isolates just the real parameter text -- the
            # whole-match fallback overcounted every zero/one-arg
            # signature by +1 the same way Python's did (#1199). Name
            # groups added to branches 1/2 too, purely so existing
            # extraction tests keep passing. The bare `::` method-
            # reference alternative is left alone -- it has no name or
            # parameter list to capture at all.
            r"(?:"
            # 1. Standard Methods
            # #2091 (sibling gap to #1486/#1489): the modifier-repeat group
            # only allowed annotations at the very start (before any
            # modifier), not interleaved between a generic type parameter
            # and the return type -- but JSpecify/Checker Framework
            # return-type annotations (`private <T> @Nullable T foo(...)`,
            # common in modern Spring code) sit exactly there. func_start's
            # own equivalent modifier group already got this exact fix in
            # #1486/#1489 (`@[\w.]+(?:\(...\))?` as one of its repeated
            # alternatives); args' Branch 1 never got the matching fix, so
            # a signature
            # with an interleaved annotation failed this whole branch and
            # fell through to Branch 3, incidentally matching an unrelated
            # lambda inside the function's own BODY and misattributing its
            # tiny arg count as the function's real parameter count
            # (confirmed: `Binder.java`'s `handleBindResult`, 6 real params,
            # measured 1 -- borrowed from a `(dataObjectBinder) ->` lambda
            # three lines into the body).
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}(?!(?:new|return|throw|if|else|while|for|switch|catch)\b)(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|strictfp|<(?:[^<>]|<[^<>]*>)*>|@[\w.]+(?:\([^)]*\))?)[ \t\n]+){0,5}(?:[\w<>\[\]?.,]+[ \t\n]+)(\w+)[ \t\n]*(\([^)]*\))|"
            # 2. Constructors
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}(?!(?:new|return|throw|if|else|while|for|switch|catch)\b)(?:(?:public|protected|private|static)[ \t\n]+)?([A-Z]\w*)[ \t\n]*(\([^)]*\))[ \t\n]*(?:throws[ \t\n]+[\w., \t\n]+)?[{]|"
            # 3. Lambdas & Method Refs
            r"(\([^)]*\)|[a-zA-Z_$][\w_$]{0,100})[ \t\n]*->|::"
            r")",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and final (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(void|return|import|package|class|interface|enum|record|extends|implements|var|sealed|non-sealed|permits|new|throws|module|requires|exports|opens|provides|uses)\b"
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks. EXCLUDES classes/interfaces. Steps over annotations.
        "func_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,10}"
            # =====================================================================
            # [THE EXECUTION SHIELD]: AST-FREE HALLUCINATION PREVENTION
            # Previously, the "Instantiation Shield" only stopped `new`. However,
            # execution verbs like `return TargetFunc();` or `throw TargetFunc();`
            # were being blindly swallowed by the return-type matcher, treating
            # 'return' as the data type and 'TargetFunc' as the function name!
            # FIX: Expanded the shield to explicitly abort on ALL control flow and
            # execution keywords at the start of the sequence.
            # =====================================================================
            r"(?!(?:new|return|throw|if|else|while|for|switch|catch)\b)"
            # RULE 11 FIX (epic #813/#816): the generic-bound modifier
            # alternative was a flat `<[^>]*>`, truncating at the first `>` and
            # breaking any single-line one-level-nested generic bound (e.g.
            # `public static <T, U extends Comparable<U>> T Foo(T a, U b) {`).
            # Widened to the established one-level-nesting idiom.
            r"(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|<(?:[^<>]|<[^<>]*>)*>|@[\w.]+(?:\([^)]*\))?)[ \t\n]+){0,5}"
            # #1221: the return-type group used to be `{0,5}` (zero
            # allowed) with the trailing lookahead accepting EITHER `{`
            # OR `;` (the latter for abstract/interface method stubs,
            # `abstract Foo bar();`) -- but a bare call statement
            # (`next();`) has zero modifiers AND zero return-type
            # tokens too, and satisfies that same `;`-terminated shape,
            # so it false-positive-matched as a method. A real Java
            # method always has an explicit return type (even `void`)
            # UNLESS it's the constructor-shape branch this same regex
            # also intentionally matches (`public TargetFunc(int x) {`,
            # no return type but ends in `{`, never `;` -- constructors
            # can't be abstract/have no body). Split into two mutually
            # exclusive alternatives instead of making the return-type
            # group conditional on itself (a `(?(name)...)` conditional
            # would need to capture it, which shifts every downstream
            # group's number and breaks callers/tests indexing the
            # identifier capture positionally): return-type present
            # allows `;` (stub) or `{` (body); return-type absent (bare
            # call OR constructor shape) requires `{` only, since only
            # a constructor legitimately reaches this branch with no
            # return type, and constructors always have a body.
            r"(?:"
            r"(?:[a-zA-Z_$][\w<>$\[\]?.,]*[ \t\n]+){1,5}"
            r"(?!(?:if|for|while|switch|catch|new|return|class|interface|enum|record)\b)([A-Za-z_$][\w_$]*)\s*\((?=[^)]*\)[ \t\n]*(?:throws[ \t\n]+[\w., \t\n]+)?[{;])"
            r"|"
            r"(?!(?:if|for|while|switch|catch|new|return|class|interface|enum|record)\b)([A-Za-z_$][\w_$]*)\s*\((?=[^)]*\)[ \t\n]*\{)"
            r")",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # RULE 11 FIX (epic #813/#816): there was no generic-parameter
        # step-over between the class name and the extends/implements
        # check at all, so ANY generic class declaration (e.g.
        # `class Foo<T> extends Base<T> {`, `class Foo<T extends
        # Comparable<T>> implements Serializable {`) left the class's own
        # `<...>` unconsumed right before `extends`/`implements`, silently
        # losing the entire inheritance capture (group 2) even though the
        # class name (group 1) still matched fine.
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]*){0,5}(?:(?:public|protected|private|static|final|sealed|non-sealed|abstract|strictfp)[ \t]+){0,5}(?:class|interface|enum|record)\s+([A-Za-z_$][\w_$]*)(?:\s*<(?:[^<>]|<[^<>]*>)*>)?(?:\s+(?:extends|implements)\s+([A-Za-z_$][\w_$, \t<>\?]*))?",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(try|catch|finally|assert|Optional|Objects\.requireNonNull|instanceof)\b|@(Valid|Validated|NotNull|NonNull|NotBlank|Immutable|Transactional)\b"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        "safety_bypasses": re.compile(
            r"\b(null)\b|return\s+null|\([A-Z]\w+\)\s*(?!->)[a-zA-Z_$]|catch\s*\(\s*(?:Exception|Throwable)\b|@SuppressWarnings|@SneakyThrows|\.get\(\)"
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Process killers and raw memory/execution risks. EXCLUDES prints (Phase 5).
        "high_risk_execution": re.compile(
            r"\b(Runtime\.getRuntime\(\)\.exec|ProcessBuilder|System\.exit|Thread\.stop|Unsafe)\b"
        ),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(File|InputStream|OutputStream|Reader|Writer|Scanner|Files\.|Path|Socket|RestTemplate|WebClient|RestClient|HttpClient|Connection|ResultSet|Statement|EntityManager|DataSource|Repository)\b"
        ),
        # 10. api (Public Surface Area)
        "api": re.compile(
            r"\b(public|protected)\b|@(RestController|Controller|Service|Component|Bean|Produces|Consumes|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|Endpoint|WebFilter)\b"
        ),
        # 11. flux (State Mutation)
        # Mutation of state. EXCLUDES final (freeze_hits).
        # BUG FIX (ReDoS): confirmed genuine O(n^2) scaling (0.045s/
        # 0.18s/0.71s/2.85s/11.2s for n=5k/10k/20k/40k/80k, ~4x per
        # doubling) against a long run of plain word characters with
        # no `.`/`(` anywhere: the unanchored `(?:\w+\.)?` before the
        # method-name keywords greedily consumes the whole remaining
        # run, fails to find the `.`, and backtracks one character at
        # a time -- O(n) work at each of the O(n) positions re.search
        # retries this unanchored alternative at. Bounded to
        # `\w{0,100}`, matching the fix shape used throughout this
        # sweep.
        "state_mutation": re.compile(
            r"\b(volatile|Atomic\w+)\b|^[ \t]*(?:this\.)?\w+[ \t]*=|@(?:Setter|Data)\b"
            r"|(?:\w{0,100}\.)?(?:set[A-Z]\w+|add|put|remove|clear|addAll|replace|computeIfAbsent)\s*\("
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"//[ \t]*(?:public|private|protected|class|void|if|for|while|return|import)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(
            r"/\*\*|@param|@return|@throws|@deprecated|@see|@since|@apiNote|@implSpec|@Operation|@Schema"
        ),
        # 14. test (Testing & Assertions)
        "test": re.compile(
            r"@(?:Test|ParameterizedTest|Before|After|BeforeEach|AfterEach|Mock|InjectMocks)|assert[A-Za-z0-9_]*\s*\(|\b(?:verify|expect|given|when)\s*\("
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(synchronized|Thread|Runnable|Future|CompletableFuture|ExecutorService|Semaphore|Atomic\w+|VirtualThread|StructuredTaskScope|ScopedValue|Mono|Flux|Publisher)\b|@(?:Async|Scheduled)"
        ),
        # 16. ui_framework (UI / View Components)
        # BUG FIX: `@ModelAttribute` starts with `@` (non-word), so the
        # shared leading \b could only fire when a word char
        # immediately preceded it -- never true for how annotations are
        # actually written (preceded by whitespace or a line start).
        # Never matched at all.
        "ui_framework": re.compile(
            r"\b(?:SwingUtilities|JFrame|JPanel|javafx\.|ModelAndView|ModelMap|Model|VaadinSession|FacesContext|UIComponent)\b"
            r"|@ModelAttribute"
        ),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(r"->|::"),
        # 18. globals (Global / Shared State)
        # BUG FIX: the `public static final ... =` alternative ends on
        # `=` (non-word), so the shared trailing \b could never fire --
        # whatever follows the `=` in a real declaration (a space, then
        # the value) is never a word character. This extremely common
        # Java constant-declaration idiom never matched at all.
        "globals": re.compile(
            r"\b(?:System\.getProperty|System\.getenv|ThreadLocal|ScopedValue)\b"
            r"|public\s+static\s+(?:final[ \t]+)?\w+\s+[A-Z_0-9]+[ \t]*="
            r"|@(?:Value|ConfigurationProperties)"
        ),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"^[ \t]*@[\w.]+(?:\([^)]*\))?", re.M),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(r"<\s*[A-Z?][^>]*>"),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(
            r"\.(?:stream|parallelStream|map|filter|reduce|collect|flatMap|forEach|anyMatch|noneMatch|gather)\("
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(
            r"\b(Math\.|BigDecimal|BigInteger|Random|SecureRandom|StrictMath|VectorSpecies|FloatVector|IntVector)\b"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Reflection and dynamic proxies.
        "reflection_metaprogramming": re.compile(
            r"\b(reflect\.|native|Class\.forName|Method\.invoke|Field\.setAccessible|Proxy\.newProxyInstance|ClassLoader|MethodHandles|VarHandle|Linker\.nativeLinker)\b|@SneakyThrows"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"^[ \t]*import\s+(?:static[ \t]+)?[\w.]+;", re.M),
        "_dependency_capture": re.compile(r"^[ \t]*import[ \t\n]+(?:static[ \t\n]+)?([\w.*]+)[ \t\n]*;", re.M),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"@author\s+(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        # BUG FIX: `@ResponseBody`/`@ResponseStatus` both start with `@`
        # (non-word) -- same leading-\b bug as ui_framework above.
        "ssr_boundaries": re.compile(
            r"\b(?:ModelAndView|FacesServlet|HttpServletRequest|HttpServletResponse|JspWriter|ThymeleafViewResolver)\b"
            r"|@ResponseBody|@ResponseStatus"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # BUG FIX: `@EventListener`/`@KafkaListener`/`@RabbitListener`/
        # `@JmsListener` all start with `@` -- same bug.
        "events": re.compile(
            r"\b(?:ApplicationEvent|ApplicationEventPublisher|ApplicationListener|EventObject|publishEvent)\b"
            r"|@EventListener|@KafkaListener|@RabbitListener|@JmsListener"
        ),
        # 33. dependency_injection (Dependency Injection / IoC)
        # BUG FIX: 10 of the 12 alternatives are `@`-prefixed Spring/
        # Guice annotations -- same bug, at scale.
        "dependency_injection": re.compile(
            r"\b(?:ApplicationContext|BeanFactory)\b"
            r"|@Autowired|@Inject|@Qualifier|@Primary|@Component|@Service|@Repository|@Bean|@Configuration|@Provides"
        ),
        # 34. macros
        "macros": None,  # Java lacks preprocessor macros.
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Project Panama (Java 22+) bridging to native memory.
        "pointers": re.compile(r"\b(MemorySegment|MemoryLayout|ValueLayout|AddressLayout|SymbolLookup)\b"),
        # 36. memory_alloc
        "memory_alloc": re.compile(
            r"\b(Arena\.ofConfined|Arena\.ofShared|Arena\.ofAuto|Arena\.global|SegmentAllocator|allocateFrom|ByteBuffer\.allocateDirect)\b"
        ),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(log|logger|LOGGER|LoggerFactory|LogManager|MDC|Tracer|Span)\.(?:info|error|warn|warning|debug|trace|log)\b|@Slf4j|@Log4j2"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
        # BUG FIX: `\.printStackTrace\(\)` ends on `)` (non-word), so
        # the shared trailing \b could never fire. Never matched.
        "debug_prints": re.compile(
            r"\b(?:System\.out\.(?:print|println|printf)|System\.err\.(?:print|println|printf))\b"
            r"|\.printStackTrace\(\)"
        ),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            r"\(\s*(?:int|long|short|byte|char|float|double|boolean|[A-Z][A-Za-z0-9_]*)\s*\)\s*[a-zA-Z_$]"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|abort|System\.exit|halt)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(Thread\.sleep|TimeUnit\.[A-Z_]+\.sleep|delay|CountDownLatch\.await)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>>?|\^|~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(
            r"\b(mutex|lock|synchronized|Semaphore|ReentrantLock|ReadWriteLock|Condition)\b",
            re.I,
        ),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(final|immutable|unmodifiable[A-Z]\w*|Object\.freeze)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(close|dispose|shutdown|free|release|cleaner\.register)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        "encapsulation": re.compile(r"\b(private|protected|internal)\b"),
        # 48. listeners (Event Listeners / Observers)
        # BUG FIX: `@KafkaListener`/`@RabbitListener` start with `@` --
        # same leading-\b bug as dependency_injection above.
        "listeners": re.compile(r"\b(?:on[A-Z]\w*|addEventListener|subscribe)\b|@KafkaListener|@RabbitListener"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"@(?:Ignore|Disabled)|test\.skip\(|mock\(|spy\(|verifyZeroInteractions"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Java Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(ObjectMapper|readValue|readTree|fromJson|ObjectInputStream|DocumentBuilder|SAXParser)\b"
        ),
        "regex_execution": re.compile(r"\b(Pattern\.compile|Matcher\.find|\.matches\()\b"),
        "time_date_logic": re.compile(
            r"\b(LocalDate(?:Time)?|ZonedDateTime|Instant|Duration|System\.currentTimeMillis|Calendar\.getInstance)\b"
        ),
        "ipc_rpc_bridges": re.compile(r"\b(ProcessBuilder|KafkaTemplate|RabbitTemplate|JmsTemplate|java\.rmi)\b"),
    },
}
