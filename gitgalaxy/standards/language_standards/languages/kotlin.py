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
        "target_version": "Kotlin 2.3.10 (K2 Compiler / Wasm / Java 25 Support)",
        "last_updated": "2026-03-12",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard sources, Kotlin script files (heavily used in modern Gradle), and module declarations.
    "extensions": [".kt", ".kts", ".ktm"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Kotlin rarely uses extensionless execution scripts.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and Kotlin-DSL Gradle build files to lock in context.
    "discriminators": [
        ".kt",
        "build.gradle.kts",
        "settings.gradle.kts",
        "gradle.properties",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for Kotlin scripting.
    "shebangs": ["kotlin", "kotlinc", "kscript"],
    # UPGRADED: Maps to Family 2 (Nested C)
    # Rationale: (CORRECTION) While Kotlin uses // and /* */, it officially allows nested
    # block comments (/* /* */ */). Using standard C parsing would cause early termination here.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. Includes modern 'when' and Elvis operator.
        # EXCLUDES throw (bailout_hits).
        "branch": re.compile(r"\b(if|else|when|for|while|do|try|catch|finally|break|continue|return)\b|\?:|&&|\|\|"),
        # 2. args (Parameters / Coupling)
        # OPTIMIZED: Removed overlapping whitespace quantifiers to fix Regex Sludge.
        "args": re.compile(
            # =====================================================================
            # [ THE LAMBDA PARAMETER SHIELD (KOTLIN) ]
            # Kotlin default arguments `emptyList()` and lambda parameters `(Result<T>) -> Unit`
            # contain parentheses that shatter standard `[^)]*` boundaries.
            # FIX: Implemented the 1-Level Nesting Trick `(?:[^)(]+|\([^)]*\))*` to
            # absorb the inner parentheses. Upgraded spaces to `[ \t\n]*` for vertical layouts.
            # =====================================================================
            # RULE 11 FIX (epic #813/#823): the generic-parameter step-over was the flat
            # `<[^>]{0,100}>`, truncating at the FIRST `>` and breaking any nested generic
            # bound (`fun <T, U : Comparable<U>> foo(x: T, y: U): T {`, a realistic bounded
            # generic function). Widened to the established one-level-nesting idiom.
            # IDENTIFIER-GRAMMAR FIX (epic #813/#899): the name step-over required a plain
            # `[a-zA-Z_]\w*`, so backtick-quoted arbitrary identifiers never matched. Added
            # as an alternative, not a widened class.
            # MULTI-DOT RECEIVER FIX: Upgraded the receiver capture to `[\w.]+` to support
            # fully qualified extension receivers (e.g., `com.example.Foo.ext()`).
            # ANONYMOUS FUNCTION FIX: Made the name capture optional to support `fun(x: Int)`.
            # #1209: parameter-list span wrapped in its own capture group
            # in both alternatives (was only reachable via group(0), the
            # whole match including the "fun"/receiver/name prefix, or for
            # trailing-lambda syntax the leading "{") so detector.py's
            # counter isolates just the real parameter text -- the
            # whole-match fallback overcounted every zero/one-arg
            # signature by +1 the same way Python's did (#1199), including
            # a bare trailing lambda (`list.forEach { item -> ... }`).
            # Name group added to the first alternative too, purely so
            # existing extraction tests keep passing.
            r"\b(?:fun|constructor)\b(?:[ \t\n]*<(?:[^<>]|<[^<>]*>)*>)?[ \t\n]*((?:(?:`[^`\n]{1,200}`|[\w.]+)\.)?(?:`[^`\n]{1,200}`|[a-zA-Z_]\w*))?[ \t\n]*(\((?:[^)(]|\([^)]*\))*\))|\{[ \t\n]*([a-zA-Z_][a-zA-Z0-9_ \t\n:<>,.?]{0,150}?)->",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries defining file architecture and control returns.
        "structural_boundaries": re.compile(r"\b(package|import|return|class|interface|object|fun|typealias)\b"),
        # 4. func_start (Executable Logic Anchors)
        # OPTIMIZED: Bound annotation parenthesis scanning to prevent multi-line bleeding.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL MODIFIER & GENERIC SHIELD (KOTLIN) ]
            # Kotlin allows annotations, modifiers, the 'fun' keyword, generics,
            # and the function name to be split across multiple lines.
            # FIX: Upgraded `[ \t]+` to `[ \t\n]+` across the decorator and modifier
            # stacks. Modified the generic stepper to `(?:<[^>]{0,100}>[ \t\n]*)?`
            # (removing the `\n` restriction) and updated the trailing lookahead
            # to `[ \t\n]*[\(\{]` so it can safely jump vertical gaps to the parameters.
            # =====================================================================
            # RULE 11 FIX (epic #813/#823): same generic-parameter nesting gap as args above
            # -- widened to the established one-level-nesting idiom.
            # IDENTIFIER-GRAMMAR FIX (epic #813/#899): same backtick-identifier gap as `args`
            # above (doc's Rule 16) -- added as an alternative capture group.
            # MULTI-DOT RECEIVER FIX: Upgraded receiver to `[\w.]+` (e.g. `com.example.Foo.ext`).
            r"^[ \t]*(?:@[\w.]+(?:\([^)\{]{0,300}\))?[ \t\n]*){0,10}"
            r"(?:(?:public|private|protected|internal|open|override|abstract|final|suspend|inline|tailrec|infix|operator|external|expect|actual)[ \t\n]+){0,5}"
            r"(?:context\s*\([^)]*\)\s*)?"
            r"(?:(?:\bfun\b)[ \t\n]*(?:<(?:[^<>]|<[^<>]*>)*>[ \t\n]*)?(?:(?:(?:`[^`\n]{1,200}`|[\w.]+)\.)?(?:`([^`\n]{1,200})`|([a-zA-Z_]\w*)))?|(init)|(constructor))(?=[ \t\n]*[\(\{])",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # OPTIMIZED: Applied the same 300-char bounds to class annotations.
        # COMPANION OBJECT FIX (epic #813/#823): `companion object { ... }` (almost always
        # anonymous -- a name is rare and optional) never matched at all: "companion" wasn't in
        # the modifier list, and even if it were, the class/interface/object/enum-class branch's
        # name was mandatory. Added a dedicated alternative for it with an OPTIONAL name, kept
        # narrowly scoped to the literal `companion object` shape rather than making the name
        # optional for the general branch -- doing that broadly would have opened a new false
        # positive on object EXPRESSIONS (`object : Base() {`, an anonymous object literal used
        # inline, a different construct from an object DECLARATION).
        # #1295: both name alternatives wrapped in capture groups (group 1
        # for the main class/interface/object/enum-class branch, group 2
        # for companion object's own optional name) so the named-entity
        # extractor (detector.py's _CLASS_START_NAMED_EXTRACTION_LANGS)
        # can recover real names instead of flooding class_data with one
        # "Anonymous_Class" phantom per match -- same alternation shape
        # `_resolve_class_start_match` already handles for Fortran/Lua.
        # #1295: `fun` added to the modifier set for `fun interface Foo {`
        # (SAM/functional-interface declarations, mainstream since Kotlin
        # 1.4) -- previously unrecognized, a real recall gap confirmed
        # against okhttp's `fun interface Factory`.
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)\{]{0,300}\))?[ \t]*){0,10}(?:(?:public|private|protected|internal|open|abstract|final|sealed|data|value|annotation|expect|actual|inner|fun)[ \t]+){0,5}(?:(?:class|interface|object|enum\s+class)\s+(`[^`\n]{1,200}`|[a-zA-Z_]\w*)|companion[ \t\n]+object(?:\s+(`[^`\n]{1,200}`|[a-zA-Z_]\w*))?)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\?\.(?!.)|as\?|\b(require|requireNotNull|check|checkNotNull|error|sealed|is|!is|Result|onSuccess|onFailure|fold|runCatching)\b|\?:"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Force unwrapping, unsafe casts, and suppression.
        "safety_bypasses": re.compile(r"!!|as(?!\?)\b|\blateinit\s+var\b|@Suppress\b"),
        # 8. danger (High-Risk Execution / System Calls)
        # Process killers and raw system triggers. EXCLUDES println (Phase 5).
        "high_risk_execution": re.compile(r"\b(System\.exit|exitProcess|Runtime\.getRuntime|Thread\.stop)\b"),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(File|InputStream|OutputStream|Retrofit|OkHttpClient|Ktor|HttpClient|RoomDatabase|Dao|SharedPreferences|DataStore|java\.nio)\b"
        ),
        # 10. api (Public Surface Area)
        # Exposed surface. Implicit public/internal defaults + Ktor/Spring routes.
        "api": re.compile(
            r"\b(public|internal)\b|@(RestController|Controller|Service|Component|RequestMapping|GetMapping|PostMapping|Route)\b"
        ),
        # 11. flux (State Mutation)
        # CRITICAL FIX: Added re.M so it scans every line, not just the first line of the file!
        "state_mutation": re.compile(
            r"\b(var|MutableList|MutableMap|MutableSet|MutableState|MutableStateFlow|Atomic[A-Za-z0-9]+)\b|^[ \t]*(?:this\.)?[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*\s*[-+*/%]?=|\.(?:add|addAll|remove|put|set|update)\(",
            re.M,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"//[ \t]*(?:val|var|fun|class|interface|object|if|when|for|return|import)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"/\*\*|@param|@return|@property|@receiver|@constructor|@throws|@see|@since"),
        # 14. test (Testing & Assertions)
        "test": re.compile(
            r"@(?:Test|ParameterizedTest|BeforeTest|AfterTest)|\b(?:assert[A-Za-z0-9_]*|mockk|spyk|test)\s*\(|\b(?:shouldBe|shouldNotBe)\b|\b(?:every|verify)\s*\{"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(suspend|launch|async|CoroutineScope|GlobalScope|Dispatchers|Flow|StateFlow|SharedFlow|Channel|yield|runBlocking|withContext|Mutex)\b"
        ),
        # 16. ui_framework (UI / View Components)
        "ui_framework": re.compile(
            r"@Composable|Modifier|\b(Column|Row|Box|Text|Image|Button|Scaffold|LazyColumn|LazyRow|Surface|remember|mutableStateOf|findViewById|View|Activity|Fragment)\b"
        ),
        # 17. closures (Closures / Anonymous Functions)
        # OPTIMIZED: Removed overlapping whitespace quantifiers to fix ReDoS.
        "closures": re.compile(r"\{[ \t\n]*[a-zA-Z_][a-zA-Z0-9_ \t\n:<>,.?]{0,150}?->"),
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            r"\b(object|companion\s+object)\b|^[ \t]*(?:const[ \t]+)?val\s+[A-Z_0-9]+[ \t]*=",
            re.M,
        ),
        # 19. decorators (Decorators / Annotations)
        # OPTIMIZED: Bounded arguments.
        "decorators": re.compile(r"@[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*(?:\([^)\{]{0,300}\))?"),
        # 20. generics (Generics / Type Parameters)
        # Prevented catastrophic backtracking across newlines.
        "generics": re.compile(r"<\s*(?:in|out)?\s*[A-Z][^>\n]{0,100}>|\breified\b|\bwhere\b"),
        # 21. comprehensions (Iterators / Comprehensions)
        # Functional collection transformations.
        "comprehensions": re.compile(
            r"\.(?:map|mapNotNull|filter|filterNot|reduce|fold|flatMap|zip|associate|groupBy|forEach|any|all|none|find)\b"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(
            r"\b(kotlin\.math\.|java\.lang\.Math\.|StrictMath\.|Random\.|sin|cos|tan|sqrt|exp|log|abs|BigDecimal|BigInteger)\b"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Reflection and optimization hooks.
        "reflection_metaprogramming": re.compile(
            r"::class|javaClass|@JvmOverloads|@JvmStatic|@JvmField|@JvmName|\b(inline|crossinline|noinline|invoke|context|tailrec)\b"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"^[ \t]*import\s+(?:static[ \t]+)?[\w.]+;?", re.M),
        "_dependency_capture": re.compile(r"^[ \t]*import[ \t\n]+(?:static[ \t\n]+)?([\w.*]+)", re.M),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"@(?:author|since)\s+(.*)|//\s*(?:Created by|Maintainer|Copyright):\s+(.*)",
            re.I,
        ),
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
        "ssr_boundaries": re.compile(
            r"\b(ApplicationCall|call\.respond|call\.respondText|call\.respondHtml|ServerResponse|ModelAndView)\b"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # BUG FIX: required a literal `(`, but Kotlin's idiomatic
        # SAM-conversion trailing-lambda form (`flow.collect { value ->
        # ... }`, omitting the parens entirely) is the dominant
        # real-world style for Flow collectors -- more common than the
        # parenthesized form. Widened to accept either `(` or `{`.
        "events": re.compile(
            r"\.(?:collect|collectLatest|observe|subscribe|onNext)\s*[\(\{]|\b(LiveData|Observer|Observable|FlowCollector)\b"
        ),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(
            r"@(?:Inject|Module|Provides|Binds|HiltViewModel|AndroidEntryPoint|Component|Autowired)|(?:koin|get|inject)\(\)"
        ),
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(r"@(?:OptIn|RequiresOptIn|Suppress|SuppressWarnings)\b"),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Kotlin/Native FFI boundaries.
        "pointers": re.compile(r"\b(?:CPointer|COpaquePointer|CFunction|CValue|CPointed)\b"),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(r"\b(?:memScoped|alloc|allocArray|nativeHeap\.alloc|nativeHeap\.free)\b"),
        # 37. inline_asm
        "inline_asm": None,  # Usually bridged via C-headers in Native.
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(?:Timber|Log|Logger|LoggerFactory)\.(?:i|e|w|d|v|info|error|warn|warning|debug|trace|verbose)\b|@Slf4j"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(println|print)\b\s*\("),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            r"\bas\??\s+[A-Z]\w*|\.to(?:Int|Long|Short|Byte|Double|Float|String|Boolean|UInt|ULong|UShort|UByte)\(\)"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|raise|exitProcess|return|panic)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(delay|Thread\.sleep|yield)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"\.(?:shl|shr|ushr|and|or|xor|inv)\(|\b(?:shl|shr|ushr|xor)\b"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(mutex|lock|synchronized|Semaphore|Atomic[A-Z]\w*)\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(val|const|immutable|readonly)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(close|dispose|shutdown|use|cleanup)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        "encapsulation": re.compile(r"\b(private|protected|internal)\b"),
        # 48. listeners (Event Listeners / Observers)
        # BUG FIX: required a literal `(`, but the idiomatic Kotlin
        # SAM-conversion trailing-lambda form (`button.setOnClickListener
        # { ... }`, omitting the parens entirely) is the dominant
        # real-world style for Android/Compose listeners. Widened to
        # accept either `(` or `{`.
        "listeners": re.compile(r"\.(?:collect|observe|subscribe|on[A-Z]\w*|set[A-Z]\w*Listener)\s*[\(\{]"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"@(?:Ignore|Disabled)|test\.skip\(|mockk|spyK|fake\("),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Kotlin Specifics) ---
        # BUG FIX: `Gson\(\)` ends on `)` -- shared trailing \b never
        # fired. Never matched.
        "serialization_parsing": re.compile(
            r"\b(?:Json\.decodeFromString|Json\.encodeToString|Moshi|ObjectMapper)\b|\bGson\(\)"
        ),
        # BUG FIX: `Regex\(\)` required LITERALLY EMPTY parens, but
        # Kotlin's `Regex` class has no zero-arg constructor -- real
        # usage is always `Regex(pattern)`, which never matched even
        # before the `\)` trailing-\b bug is considered. Widened to
        # `Regex\(` (matching the constructor call regardless of its
        # argument). `\.toRegex\(\)` (the real zero-arg extension
        # function on String) keeps its literal empty parens but still
        # needed the same trailing-\b fix as the rest of this sweep.
        "regex_execution": re.compile(r"\bRegex\(|\.toRegex\(\)|\.matches\(|\.find\("),
        "time_date_logic": re.compile(
            r"\b(Clock\.System\.now|Instant\.now|System\.currentTimeMillis|Duration\.minutes|LocalDate)\b"
        ),
        # BUG FIX: `Intent\(`/`HttpClient\(` both end on `(` (non-word),
        # so the shared trailing \b only fired when a word char
        # immediately followed the paren -- true for the common
        # `Intent(this, Foo::class.java)` form, but never for the
        # zero-argument form (`HttpClient()`), where `)` follows.
        "ipc_rpc_bridges": re.compile(
            r"\b(?:BroadcastReceiver|ProcessBuilder|bindService)\b|\bIntent\(|\bHttpClient\("
        ),
    },
}
