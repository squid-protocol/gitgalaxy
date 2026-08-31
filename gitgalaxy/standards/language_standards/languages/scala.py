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
        "target_version": "Scala 3 (Dotty / Braceless Syntax / Contextual Abstractions)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard sources, worksheet files (.sc), and pure-Scala build tool configurations (.sbt).
    "extensions": [".scala", ".sc", ".sbt", ".kojo"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Scala build definitions are typically handled by .sbt extensions rather than extensionless files.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, build files, and Play framework configurations to anchor the ecosystem.
    "discriminators": [
        ".scala",
        "build.sbt",
        "application.conf",
        "Dependencies.scala",
        "project/build.properties",
        "project/plugins.sbt",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for Scala scripting and the Ammonite REPL.
    "shebangs": ["scala", "amm", "scala-cli"],
    # UPGRADED: Maps to Family 2 (Nested C)
    # Rationale: Scala explicitly supports nested multi-line comments (/* /* */ */),
    # requiring depth-aware stripping to prevent premature termination.
    "lexical_family": "recursive_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow. Includes Scala 3 if-then and match-case.
        "branch": re.compile(
            r"\b(if|then|else|match|case|try|catch|finally|for|while|do|throw|yield)\b|&&|\|\|",
            re.I,
        ),
        # 2. args: Parameters / Coupling. Captures parameters in method signatures and lambdas.
        # RULE 11 FIX (epic #813/#825): the generic-parameter step-over was the flat
        # `\[[^\]]*\]`, truncating at the FIRST `]` and breaking any nested generic bound
        # (`def foo[T <: Comparable[T]](x: T): T = {`, a realistic bounded generic method --
        # the square-bracket variant of the same Rule-11 bug class already fixed for
        # java/typescript/python/rust/csharp/kotlin/swift).
        # IDENTIFIER-GRAMMAR FIX (epic #813/#825): the name step-over required a plain
        # `[a-zA-Z_]\w*`, so any backtick-quoted arbitrary identifier (Scala's escape hatch for
        # reserved-word/space-containing method names, e.g. `` def `must not fail`(x: Int): Int
        # = x ``, a realistic idiom for Java-interop/reserved-word names) never matched at all
        # (doc's Rule 16 shape). Added as an alternative, not a widened class, so it can't loosen
        # the plain-identifier path.
        # #1209: parameter-list span wrapped in its own capture group in
        # all three alternatives (was only reachable via group(0), the
        # whole match including the "def"/name prefix, or for arrow
        # functions the trailing "=>") so detector.py's counter isolates
        # just the real parameter text -- the whole-match fallback
        # overcounted every zero/one-arg signature by +1 the same way
        # Python's did (#1199), including the bare single-identifier
        # arrow form (`x => ...`, always exactly 1 arg). Name group added
        # to the first alternative too, purely so existing extraction
        # tests keep passing.
        "args": re.compile(
            r"\bdef\s+(`[^`\n]{1,200}`|[a-zA-Z_]\w*)(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?\s*(\((?:[^()]|\([^()]*\))*\))|(\((?:[^()]|\([^()]*\))*\))[ \t]*=>|\b([a-zA-Z_]\w*)[ \t]*=>"
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and val/var.
        "structural_boundaries": re.compile(
            r"\b(lazy|type|opaque|class|trait|object|enum|extension|import|export|return|extends|with|derives|new|given|using)\b"
        ),
        # 4. func_start: Executable Logic Anchors. Anchors executable logic. EXCLUDES structural headers.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL MODIFIER SHIELD (SCALA) ]
            # Scala 3 developers frequently stack modifiers (inline, transparent)
            # and annotations across multiple lines before the `def` keyword.
            # FIX: Upgraded horizontal spaces `[ \t]+` to vertical spaces `[ \t\n]+`
            # across the attribute stepper and modifier capture, explicitly allowing
            # the engine to wrap lines without triggering ReDoS.
            # =====================================================================
            # IDENTIFIER-GRAMMAR FIX (epic #813/#825): same backtick-identifier gap as `args`
            # above (doc's Rule 16) -- added as an alternative capture group, not a widened
            # class. detector.py already resolves the fired group via `match.lastindex` for
            # exactly this kind of multi-alternative name capture (see java's `(init)|
            # (constructor)` groups), so no downstream change is needed.
            # QUALIFIED-ACCESS FIX (#1266): `private`/`protected` accept an optional
            # bracketed scope qualifier (`private[kafka]`, `private[this]`,
            # `protected[network]`) -- a mainstream Scala idiom for package-/
            # instance-private members, not a rare one (confirmed: every missing
            # function found investigating #1266's scala recall gap on a real Kafka
            # corpus file used this form). Without it, the bare `private`/`protected`
            # alternative consumed nothing (no trailing whitespace immediately
            # follows before the `[`), so the whole match failed to reach `def` at
            # all -- not a partial/wrong match, a total miss.
            r"^[ \t]*(?:@[\w.]+(?:\((?:[^()]|\([^()]*\))*\))?[ \t\n]*){0,5}"
            r"(?:(?:override|private(?:\[[\w.]+\])?|protected(?:\[[\w.]+\])?|final|implicit|inline|transparent|open|lazy)[ \t\n]+){0,3}"
            r"def[ \t\n]+(?:`([^`\n]{1,200})`|([a-zA-Z_]\w*))(?=[ \t\n]*[\[(:=]|$)",
            re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Defines structural entities and OO boundaries.
        # BUG FIX (#1295 polish pass): the modifier alternation was missing
        # private(?:[scope])?/protected(?:[scope])? -- func_start right above already handles
        # these correctly, class_start just never got the same list. Real recall gap, confirmed
        # via kafka's `private class LogRecoveryThreadFactory`, `private[kafka] abstract class
        # Acceptor`, `private[network] case class DelayedCloseSocket`.
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\((?:[^()]|\([^()]*\))*\))?[ \t\n]*){0,5}"
            r"(?:(?:sealed|abstract|final|case|open|opaque|transparent|private(?:\[[\w.]+\])?|protected(?:\[[\w.]+\])?)[ \t\n]+){0,3}"
            r"(?:class|trait|object|enum)\s+([A-Za-z_]\w*)(?=[ \t]*[\[({]|\s+extends|\n|$)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Monadic error handling (Option/Try) and assertions.
        "safety": re.compile(
            r"\b(Option|Some|None|Try|Success|Failure|Either|Left|Right|sealed|require|assert|assume)\b|\|\s*Null\b"
        ),
        # 7. safety_neg: Safety Bypasses. Actively bypassing type safety (asInstanceOf, .get).
        # BUG FIX: `@unchecked` is `@`-prefixed -- the shared leading
        # \b could only fire when a word char immediately preceded the
        # `@`, never true for how annotations are actually written.
        # Never matched at all. (`.get` is left as-is: a leading `.` is
        # preceded by an identifier in real method-chain usage, so that
        # leading \b fires correctly.)
        "safety_bypasses": re.compile(r"\b(?:null|asInstanceOf|isInstanceOf|Any|AnyRef)\b|\.get\b(?!Class)|@unchecked"),
        # 8. danger: High-Risk Execution. Process killers and catastrophic exit commands.
        "high_risk_execution": re.compile(r"\b(System\.exit|sys\.exit|Thread\.stop|Runtime\.getRuntime\.exec)\b"),
        # 9. io: I/O & Network Boundaries. Filesystem, Network, and Http Clients (Includes CERN triggers).
        "io": re.compile(
            r"\b(Source|java\.io|java\.nio|Files\.|Socket|ServerSocket|sttp|Http|WSClient|HTLoad|HTGet|ENQUIRE)\b"
        ),
        # 10. api: Public Surface Area. Implicit public visibility and Scala 3 @main entry points.
        "api": re.compile(
            r"\b(export)\b|@(?:main|GetMapping|PostMapping|Endpoint|Path)\b|^[ \t]*(?:override\s+|inline\s+|transparent[ \t]+)?def\s+[^_]\w+",
            re.M,
        ),
        # 11. flux: State Mutation. State mutation (var and mutable collection updates).
        "state_mutation": re.compile(
            r"\b(var|scala\.collection\.mutable|AtomicReference|AtomicInteger)\b|^[ \t]*[a-zA-Z_]\w*[ \t]*=",
            re.M,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code or logic trails.
        "dead_code": re.compile(
            r"//[ \t]*(?:def|val|var|class|object|trait|if|match|println|import)\b|/\*[ \t]*(?:def|val|class|object)"
        ),
        # 13. doc: Structured Documentation. Scaladoc documentation (/**) and annotations.
        "doc": re.compile(r"/\*\*|@param|@return|@tparam|@throws|@see|@note"),
        # 14. test: Testing & Assertions. ScalaTest, MUnit, and standard expect/verify markers.
        # BUG FIX: `test\s*\(` ends on `(` (non-word), so the shared
        # trailing \b could never fire. Never matched.
        "test": re.compile(
            r"\b(?:it\s+should|assertEquals|assertThrows|AnyFunSuite|WordSpec|munit|weaver)\b"
            r"|\btest\s*\(|\b(?:must|expect|assert)\s*[\(\{]"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. Effect systems and Actor paradigms (ZIO, Cats Effect, Akka).
        "concurrency": re.compile(
            r"\b(Future|Promise|Await|Actor|Behavior|ZIO|UIO|Task|RIO|cats\.effect\.IO|Fiber|FiberRef|Ref|Deferred|Semaphore)\b"
        ),
        # 16. ui_framework: UI / View Components. Scala.js DOM and XML literals (Includes TBL triggers).
        "ui_framework": re.compile(
            r"\b(dom\.|Laminar|Tyrian|HtmlElement|Document|Node|SGML|HyperLink|scala\.xml|Elem|XML|WorldWideWeb|BrowserView)\b"
        ),
        # 17. closures: Closures / Anonymous Functions. Anonymous function fat-arrows and underscores.
        "closures": re.compile(r"=>|(?<=\()\s*_\s*(?=[\),])|(?<=\W)_\s*(?=\W)"),
        # 18. globals: Global / Shared State. Singletons (objects) and JVM environment bindings.
        "globals": re.compile(
            r"\b(object\s+[A-Z]\w*|sys\.env|sys\.props|System\.getProperty|scala\.util\.Properties)\b"
        ),
        # 19. decorators: Decorators / Annotations. Method and class annotations.
        "decorators": re.compile(r"@[A-Za-z_]\w*(?:\([^)]*\))?"),
        # 20. generics: Generics / Type Parameters. Type parameterization and HKT constraints.
        "generics": re.compile(r"\[\s*[+-]?[A-Z][^\]]*\]|\bF\[_\]|<:|>:|\[[ \t]*_\s*\]"),
        # 21. comprehensions: Iterators / Comprehensions. For-comprehensions and monadic chains.
        "comprehensions": re.compile(
            r"\bfor\s*(?:\{[^}]*\}|\([^)]*\))\s*yield\b|\.(?:map|flatMap|filter|withFilter|foldLeft|reduce|collect)\s*[\(\{]"
        ),
        # 22. scientific: Numerical / Compute Libraries. Math library and linear algebra wrappers.
        "scientific": re.compile(
            r"\b(scala\.math|breeze\.|spire\.|algebird|Math\.|StrictMath\.|DenseMatrix|DenseVector)\b"
        ),
        # 23. heat_triggers: Metaprogramming & Reflection. Contextual abstractions and implicit resolution.
        "reflection_metaprogramming": re.compile(
            r"\b(implicit|given|using|inline|extension|TypeTag|ClassTag|scala\.reflect|Typeable|Dynamic|summon|derives)\b"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"\b(?:import|export)\s+[\w.{}\s,]+", re.M),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (SCALA) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Firewall.
            #
            # HISTORICAL BUG: Anchored to the start of the line `^[ \t]*`. Scala
            # developers frequently scope imports locally inside methods, classes,
            # or traits to prevent namespace pollution. The anchored regex missed
            # all of these local dependencies.
            #
            # THE FIX: Stripped the `^` anchor and rely on the `\b` word boundary.
            #
            # [ THE BLOCK DESTRUCTURING SHIELD ]
            # Scala relies heavily on bracketed block imports: `import java.util.{List, Map}`.
            # A trailing `{...}` block is captured as its own alternative below so its content
            # (which may span multiple lines and contain `=>` renames) is swallowed whole. The
            # downstream parser (galaxyscope.py) flattens this string and splits on commas/
            # brackets to extract the individual modules.
            #
            # BUG FIX (epic #813/#825): the previous capture, `[\w.{}\s,]+`, was a single flat
            # character class with no statement boundary at all -- since `\s` matches newlines,
            # it kept consuming across subsequent, unrelated lines (including a SECOND import
            # statement) until it happened to hit some character outside the class. Confirmed on
            # a realistic 2-import file: the first match's capture group swallowed the entire
            # second `import` line plus part of the following `case class` line, so the second
            # import was never separately detected at all. The same flat class also truncated at
            # the first `*`/`=`/`>`, so Scala 3 wildcard imports (`import scala.util.chaining.*`)
            # lost their trailing `*` and `=>`-renamed block imports (`import scala.util.{Try =>
            # STry}`) were cut off mid-block. Replaced with a properly bounded
            # segmented-dotted-path grammar: repeat `identifier.` segments, then end on either a
            # `{...}` block (unrestricted content except braces themselves, so `=>` renames and
            # multi-line layouts both work) or a bare trailing identifier/wildcard segment
            # (`[\w*]+`, covering both Scala 2 `_` and Scala 3 `*` wildcards via `\w`/`*`). This
            # is bounded per-statement by construction -- there is no `\s`/`.` left dangling
            # outside an explicit brace block for it to bleed through.
            # =====================================================================
            r"\b(?:import|export)\s+((?:[\w]+\.)*(?:\{[^{}]*\}|[\w*]+))",
            re.M,
        ),
        # 25. ownership: Authorship indicators.
        # BUG FIX: the Scaladoc `@author` tag was grouped with
        # `Created by`/`Maintainer`/`Copyright`, all of which require a
        # literal `:` -- but Scaladoc's actual convention (matching
        # Javadoc, and how java's own ownership rule already handles
        # it) is `@author Jane Doe`, with no colon at all. The colon
        # requirement meant the real Scaladoc tag never matched.
        "ownership": re.compile(
            r"@author\s+([^\n]+)|(?:Created by|Maintainer|Copyright|Tim Berners-Lee):\s+([^\n]+)",
            re.I,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags and architecture specs.
        "spec_exposure": re.compile(
            r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]|\b(?:WorldWideWeb|HyperText\s+Proposal|NeXTSTEP)\b",
            re.I,
        ),
        # 31. ssr_boundaries: View Horizon. Play Framework and twirl template endpoints.
        # BUG FIX: `Ok\(`/`BadRequest\(` both end on `(` (non-word), so
        # the shared trailing \b could never fire. Neither of Play's
        # two most common Result constructors ever matched.
        "ssr_boundaries": re.compile(
            r"\b(?:Action|Controller|HttpRoutes|ServerEndpoint|twirl|html\.[a-zA-Z_]\w*)\b|\bOk\(|\bBadRequest\("
        ),
        # 32. events: Pub/Sub Network. Stream processing and event bus signatures.
        "events": re.compile(r"\b(Source|Flow|Sink|fs2\.Stream|ZStream|EventBus|system\.eventStream|Observable)\b"),
        # 33. dependency_injection: Inversion of Control. ZLayer and ReaderT patterns.
        # BUG FIX: `@Inject` is `@`-prefixed -- the shared leading \b
        # could only fire when a word char immediately preceded the
        # `@`, never true for how annotations are actually written.
        # Never matched at all.
        "dependency_injection": re.compile(
            r"\b(?:wire\[|ZLayer|ZLayer\.from|provide|provideSome|ReaderT|Kleisli|requires)\b|@Inject"
        ),
        # 34. macros: Preprocessor Hooks. Scala 3 inline and quoted metaprogramming.
        "macros": re.compile(
            r"\b(inline\s+def|transparent\s+inline|macro|scala\.quoted|Expr|Type|Quotes)\b|\$\{.*?\}|\'\{"
        ),
        # 35. pointers: Memory Map. Scala Native C-Interop pointers.
        # BUG FIX: `Ptr\[[^\]]+\]` ends on the closing `]` (non-word),
        # so the shared trailing \b could never fire -- unlike
        # `decode\[` elsewhere (bounded only by the opening `[`, always
        # followed by a word-char type name), this alternative matches
        # through the CLOSING bracket, and whatever follows a type
        # declaration (` = `, `;`, a newline) is never a word
        # character. Never matched. Also bounded the previously
        # unbounded `[^\]]+` to `{1,200}`. (`!ptr` is left as-is: it's
        # harmlessly masked by `ptr\.` matching the same text via its
        # own valid boundary, since `!` immediately preceding `ptr` is
        # a valid non-word-to-word transition.)
        "pointers": re.compile(
            r"\bPtr\[[^\]]{1,200}\]|\b(?:scala\.scalanative\.unsafe|!ptr|ptr\.|CFuncPtr|CStruct\d+)\b"
        ),
        # 36. memory_alloc: Manual Memory Management. Heap and Native allocations.
        # BUG FIX: `zone[ \t]*\{` ends on `{` and `alloc\[[^\]]+\]` ends
        # on the closing `]` -- both non-word, so the shared trailing
        # \b could never fire for either. Neither ever matched. Also
        # bounded the previously unbounded `[^\]]+` to `{1,200}`.
        "memory_alloc": re.compile(
            r"\b(?:Zone|malloc|calloc|free|scala\.scalanative\.libc\.stdlib)\b"
            r"|zone[ \t]*\{|alloc\[[^\]]{1,200}\]"
        ),
        # 37. inline_asm: Bare Metal.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics (Structured logs).
        "telemetry": re.compile(
            r"\b(?:logger|log|ZIO\.log|LoggerFactory|log4cats|slf4j)\.(?:info|error|warn|debug|trace)\b|@Slf4j"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
        "debug_prints": re.compile(r"\b(println|print|Console\.println)\b"),
        # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit type coercion.
        "explicit_casts": re.compile(r"\basInstanceOf\[[^\]]*\]|\.(?:toInt|toLong|toFloat|toDouble|toByte|toShort)\b"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting context.
        "panics_and_aborts": re.compile(r"\b(throw|panic|abort|sys\.error|exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits/sleep).
        "thread_sleeps": re.compile(r"\b(Thread\.sleep|delay|setTimeout|setInterval)\s*\("),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~"),
        # 44. sync_locks (Resource Management & Stability) Coordinated threading.
        "sync_locks": re.compile(r"\b(synchronized|volatile|Semaphore|Mutex|lock|unlock)\b"),
        # 45. immutability_locks (Immutability Constraints) Immutability.
        "immutability_locks": re.compile(r"\b(val|final|sealed|readonly|Object\.freeze|immutable)\b"),
        # 46. cleanup (Resource Cleanup / Teardown) Resource release.
        "cleanup": re.compile(r"\b(dispose|close|cleanup|cancel|free|bracket|finally|onException)\b"),
        # 47. encapsulation (Encapsulation / Access Modifiers)
        "encapsulation": re.compile(r"\b(private|protected)\b|private\[[^\]]+\]"),
        # 48. listeners (Event Listeners / Observers) Waiting for state broadcasts.
        # BUG FIX: `on\(` ends on `(` (non-word), so the shared
        # trailing \b could never fire -- never true for the common
        # real call shape `on('event', ...)`, where a quote follows.
        "listeners": re.compile(r"\bon\(|\b(?:addEventListener|subscribe|watch|useEffect|listen)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(ignore|pending|skip|xit|xdescribe)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Scala Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(io\.circe|decode\[|asJson|Json\.parse|Json\.toJson|upickle\.default)\b"
        ),
        "regex_execution": re.compile(r'"[^"]+"\.r\b|\bRegex\s*\(|\.(findAllIn|findFirstIn|replaceAllIn)\b'),
        # BUG FIX: `Duration\s*\(` ends on `(` (non-word), so the
        # shared trailing \b only fired for the non-empty-argument form
        # (`Duration(5, SECONDS)`, where a digit follows the paren),
        # not the empty-argument form (`Duration()`).
        "time_date_logic": re.compile(
            r"\b(?:FiniteDuration|System\.currentTimeMillis|LocalDate\.now)\b|\bDuration\s*\("
        ),
        # BUG FIX: `Process\s*\(` ends on `(` -- same bug. Never
        # matched the common `Process("cmd")` form (a quote follows).
        "ipc_rpc_bridges": re.compile(r"\b(?:ActorSystem|ActorRef|sys\.process\._|Future\.apply)\b|\bProcess\s*\("),
    },
}
