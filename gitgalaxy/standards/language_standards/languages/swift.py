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
        "target_version": "Swift 6.2 / iOS 18+ / Strict Concurrency, Macros & Swift Testing",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard sources and module interface declarations.
    "extensions": [".swift", ".swiftinterface"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Tooling configurations that are secretly pure Swift code.
    "exact_matches": ["Package.swift"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and package manager lockfiles to resolve ambiguous files in mixed Apple environments.
    "discriminators": [".swift", "Package.resolved", "project.pbxproj"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for Swift-based scripting and automation.
    "shebangs": ["swift", "swift-sh"],
    # UPGRADED: Maps to Family 2 (Nested C)
    # Rationale: Supports nested block comments (/* /* */ */), necessitating depth-aware stripping
    # rather than standard C-style early termination.
    "lexical_family": "recursive_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. Includes modern typed throws (throws(Error)).
        # EXCLUDES throw/rethrows (bailout_hits).
        "branch": re.compile(
            r"\b(if|else|guard|switch|case|default|for|while|repeat|do|catch|break|continue|defer|try|throws)\b|&&|\|\||\?|\?\?"
        ),
        # 2. args (Parameters / Coupling)
        # Parameter blocks. Bounded negation [^)]* and <[^>]*> to prevent ReDoS.
        "args": re.compile(
            # =====================================================================
            # [ THE ESCAPING CLOSURE SHIELD (SWIFT) ]
            # Swift functions often take escaping closures `(Result<Void, Error>) -> Void`
            # as parameters. The inner `()` breaks the `[^)]*` matcher.
            # FIX: Upgraded horizontal spaces to `[ \t\n]+` to allow vertical jumps,
            # and injected the 1-Level Nesting Trick `(?:[^)(]+|\([^)]*\))*` to safely
            # capture the entire parameter block without ReDoS.
            # =====================================================================
            # RULE 11 FIX (epic #813/#824): the generic-parameter step-over was the flat
            # `<[^>]*>`, truncating at the FIRST `>` and breaking any nested generic bound via
            # a primary associated type constraint (`func foo<T: Collection<Int>>(x: T) {`,
            # Swift 5.7+, mainstream). Widened to the established one-level-nesting idiom.
            # #1209: parameter-list span wrapped in its own capture group
            # in both alternatives (was only reachable via group(0), the
            # whole match including the "func"/name prefix, or for
            # trailing-closure syntax the leading "{"/capture-list) so
            # detector.py's counter isolates just the real parameter text
            # -- the whole-match fallback overcounted every zero/one-arg
            # signature by +1 the same way Python's did (#1199). Name
            # group added to the first alternative too, purely so
            # existing extraction tests keep passing.
            r"\b((?:func|init\??|subscript)[ \t\n]*(?:[a-zA-Z_]\w*)?)(?:[ \t\n]*<(?:[^<>]|<[^<>]*(?:<[^<>]*>[^<>]*)*>)*>)?[ \t\n]*(\((?:[^)(]|\([^)(]*(?:\([^)]*\)[^)(]*)*\))*\))|\{[ \t\n]*(?:\[[^\]]*\][ \t\n]*)?(\([^)]*\)|[a-zA-Z_]\w*(?:[ \t\n]*,[ \t\n]*[a-zA-Z_]\w*){0,50})?[ \t\n]*in\b",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and let (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(func|init|subscript|var|struct|class|enum|protocol|extension|actor|macro|import|typealias|associatedtype|mutating|nonmutating|isolated|nonisolated|return|yield|await|inout)\b|(?<!\blet )(?<!\bvar )(?<!\bfunc )(?<!\bclass )(?<!\bstruct )\b(some|any|consume|borrow|discard)\b|~Copyable"
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks. EXCLUDES types/classes. Steps over Concurrency modifiers.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL ATTRIBUTE & GENERICS SHIELD ]
            # Swift allows heavy modifier stacking and disconnected generics.
            # FIX: Upgraded horizontal `[ \t]+` spaces to vertical `[ \t\n]+` across
            # decorators and modifiers, and safely detached the generic stepper
            # `(?:[ \t\n]*<[^>]*>)?` from the function name capture.
            # RULE 11 FIX (epic #813/#824): that generic stepper was flat, truncating at the
            # FIRST `>` and breaking any nested generic bound via a primary associated type
            # constraint (`func foo<T: Collection<Int>>(x: T) {`, Swift 5.7+, mainstream) --
            # same gap as args above. Widened to the established one-level-nesting idiom.
            # =====================================================================
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}"
            r"(?:(?:public|private|fileprivate|internal|open|package|override|final|static|class|mutating|nonmutating|isolated|nonisolated(?:\(unsafe\))?|distributed|required|convenience)[ \t\n]+){0,5}"
            r"(?:func[ \t\n]+([a-zA-Z_]\w*|[=/\-+!*%<>&|^?~]+)(?:[ \t\n]*<(?:[^<>]|<[^<>]*(?:<[^<>]*>[^<>]*)*>)*>)?|(init\??)|(subscript))(?=[ \t\n]*\()",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # #1295: name wrapped in a capture group so the named-entity
        # extractor (detector.py's _CLASS_START_NAMED_EXTRACTION_LANGS)
        # can recover real names instead of flooding class_data with one
        # "Anonymous_Class" phantom per match. Widened to an optional
        # dotted chain (`\.[a-zA-Z_]\w*`) so nested-type extensions
        # (`extension AFError.ParameterEncoderFailureReason { ... }`,
        # mainstream in real Swift error-handling code) capture their
        # full qualified name instead of truncating at the first dot.
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]*){0,5}(?:(?:public|private|fileprivate|internal|open|package|final|distributed|indirect)[ \t]+){0,5}(?:class|struct|enum|protocol|actor|extension|macro)\s+([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # BUG FIX: `try\?`/`as\?` both end on `?` (non-word), so the
        # shared trailing \b could never fire -- whatever follows
        # these operators (a space, then the expression) is never a
        # word character. Neither of Swift's two most common
        # error-softening operators ever matched.
        "safety": re.compile(
            r"\b(?:guard\s+let|if\s+let|guard\s+var|if\s+var|catch|is|Sendable|Result|assert|precondition|Mutex)\b"
            r"|try\?|as\?|@MainActor|\?\?"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Unsafe pointers and linter bypasses. EXCLUDES forced unwraps (moved to friction).
        "safety_bypasses": re.compile(
            r"\bunowned(?:\(unsafe\))?\b|\bnonisolated\(unsafe\)|\bunsafeDowncast\b|//\s*swiftlint:disable"
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Fatal traps and process killers. EXCLUDES TODO (debt) and print (print_hits).
        "high_risk_execution": re.compile(r"\b(fatalError|preconditionFailure|assertionFailure|abort|exit)\b"),
        # 9. io (I/O & Network Boundaries)
        # BUG FIX: `Data\(contentsOf:`/`write\(to:` both end on `:`
        # (non-word), so the shared trailing \b could never fire.
        # Neither ever matched.
        "io": re.compile(
            r"\b(?:URLSession|FileManager|FileHandle|UserDefaults|CoreData|SwiftData|NWConnection)\b"
            r"|Data\(contentsOf:|write\(to:"
        ),
        # 10. api (Public Surface Area)
        # Exposed surface area. Explicit visibility and Objective-C bridges.
        # BUG FIX: 7 of the 10 alternatives are `@`-prefixed attributes,
        # which start with a non-word char -- the shared leading \b
        # could only fire when a word char immediately preceded the
        # `@`, never true for how attributes are actually written.
        # Never matched at all.
        "api": re.compile(
            r"\b(?:public|open|package)\b"
            r"|@usableFromInline|@objc|@objcMembers|@_exported|@IBAction|@IBOutlet|@Published"
        ),
        # 11. flux (State Mutation)
        # Mutation of state. EXCLUDES let (freeze_hits).
        "state_mutation": re.compile(
            r"\b(var|inout|mutating|didSet|willSet|_modify)\b|@(?:State|Binding|FocusState|Bindable|Observable)|^[ \t]*(?:self\.)?[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*){0,5}\s*[-+*/]?=|\.(?:append|insert|remove|toggle|updateValue)\("
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"//[ \t]*(?:let|var|func|class|struct|actor|extension|if|guard|return)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"///|/\*\*|-\s*parameter|-\s*returns:|-\s*throws:|-\s*warning:"),
        # 14. test (Testing & Assertions)
        "test": re.compile(
            r"\b(?:XCTest|XCTestCase|XCTAssert[A-Za-z]*|setUp|tearDown)\b|@(?:Test|Suite)\b|#(?:expect|require)\b"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(async|await|actor|Task|TaskGroup|DispatchQueue|OperationQueue|MainActor|Sendable|isolated|nonisolated|continuation)\b"
        ),
        # 16. ui_framework (UI / View Components)
        # BUG FIX: `@State`/`@Binding`/`@Environment` are `@`-prefixed --
        # same leading-\b bug as api above.
        "ui_framework": re.compile(
            r"\b(?:View|Body|ZStack|VStack|HStack|Text|Image|Button|SwiftUI|UIKit|AppKit|UIView|UIViewController|NSView|NSWindow)\b"
            r"|@State|@Binding|@Environment"
        ),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(
            r"completion:[ \t]*\{|\{\s*(?:\[[^\]]*\]\s*)?(?:\([^)]*\)|[a-zA-Z_]\w*(?:[ \t\n]*,[ \t\n]*[a-zA-Z_]\w*){0,50})[ \t\n]+in\b"
        ),
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            r"\b(?:static\s+let|static\s+var|shared|standard|default|NotificationCenter\.default|UserDefaults\.standard|FileManager\.default)\b|@Environment\b"
        ),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"@[a-zA-Z_]\w*(?:\([^)]*\))?"),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(r"<\s*[A-Z][^>]*>|\bwhere\s+[a-zA-Z_]\w*\s*:|\b(?:some|any|each)\s+[A-Z]\w*"),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(
            r"\.(?:map|compactMap|flatMap|filter|reduce|forEach|allSatisfy|contains)\s*(?:\(|\{)"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(
            r"\b(simd|Accelerate|Double|Float|Float16|CGFloat|Decimal|CoreML|CreateML|vDSP|sqrt|pow|sin|cos|tan)\b"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Reflection and Dynamic Dispatch.
        # BUG FIX: `@objc` is `@`-prefixed -- same leading-\b bug.
        "reflection_metaprogramming": re.compile(
            r"\b(?:dynamic|Mirror\(|unsafeBitCast|withUnsafe\w+|KeyPath|WritableKeyPath)\b|@objc|\\\.[\w.]+"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"^[ \t]*(?:@_exported[ \t]+)?import\s+[a-zA-Z_]\w*", re.M),
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:@_exported[ \t]+)?import\s+(?:(?:typealias|struct|class|enum|protocol|let|var|func)\s+)?([a-zA-Z_][\w.]+)",
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"//\s*(?:Created by|Author:|Copyright):\s+(.*)", re.I),
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
            r"\b(Vapor|Hummingbird|Request|Response|Route|app\.get|app\.post|EventLoopFuture)\b"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # BUG FIX: `@Published` is `@`-prefixed -- same leading-\b bug.
        # (`.sink`/`.assign` are left as-is: a leading `.` is preceded
        # by an identifier in real method-chain usage, e.g.
        # `publisher.sink { ... }`, so that leading \b fires correctly.)
        "events": re.compile(
            r"\b(?:NotificationCenter|Combine|Publisher|Subscriber|CurrentValueSubject|PassthroughSubject|AnyCancellable|ObservableObject|Observation)\b"
            r"|\.sink|\.assign|@Published"
        ),
        # 33. dependency_injection (Dependency Injection / IoC)
        # BUG FIX: `@Environment`/`@EnvironmentObject`/`@Inject`/
        # `@Dependency` are all `@`-prefixed -- same leading-\b bug.
        "dependency_injection": re.compile(
            r"\b(?:Swinject|Container|Resolver|Factory)\b|@Environment|@EnvironmentObject|@Inject|@Dependency"
        ),
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(
            r"#(?:Preview|Predicate|OptionSet|Rule|warning|error)\b|@(?:freestanding|attached)|#[A-Z]\w*"
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": re.compile(
            r"\b(?:Unsafe(?:Mutable)?(?:Raw|Buffer)?Pointer|OpaquePointer|CVaListPointer|Unmanaged)\b|\.pointee\b|(?<=[=\s,(])&\w+"
        ),
        # 36. memory_alloc (Manual Memory Management)
        # BUG FIX: `\.allocate\(capacity:` ends on `:` and
        # `\.deallocate\(\)` ends on `)` -- both non-word, so the
        # shared trailing \b could never fire. Neither ever matched.
        "memory_alloc": re.compile(r"\b(?:malloc|calloc|free|ManagedBuffer)\b|\.allocate\(capacity:|\.deallocate\(\)"),
        # 37. inline_asm
        "inline_asm": None,  # Swift delegates ASM to C-headers.
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(?:Logger|OSLog|os_log)\b|\bLogger\([^)]*\)\.(?:info|error|warning|debug|trace|notice|critical|fault)\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(print|debugPrint|dump)\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            r"\bas[!?]?\s+[A-Z]\w*|\bis\s+[A-Z]\w*|\b(?:Int|Double|Float|Float16|CGFloat|String|Bool)\s*\("
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|fatalError|abort|exit|preconditionFailure)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(sleep|delay|Task\.sleep)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>|\^|(?<![=!])~|<<=|>>=|\^="),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(
            r"\b(mutex|lock|synchronized|Semaphore|OSAllocatedUnfairLock|MainActor|distributed)\b",
            re.I,
        ),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(let|final|static|readonly|Immutable|Sendable)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(deinit|close|free|dispose|shutdown|removeAll)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        "encapsulation": re.compile(r"\b(private|fileprivate|internal)\b"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\.onAppear\(|\.onChange\(|\.sink\(|addObserver|subscribe"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # BUG FIX: `mock\(`/`stub\(`/`fake\(`/`double\(` all end on `(`
        # (non-word), so the shared trailing \b only fired when a word
        # char immediately followed the paren -- true for most
        # single-argument calls, but never for the zero-argument form
        # (`double()`), where `)` follows instead.
        "test_skip": re.compile(r"\bXCTSkip\b|\bmock\(|\bstub\(|\bfake\(|\bdouble\("),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Swift Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(JSONDecoder|JSONEncoder|PropertyListSerialization|NSKeyedUnarchiver|XMLParser)\b"
        ),
        "regex_execution": re.compile(r"\b(NSRegularExpression|Regex|try\s+Regex|\.range\(of:.*\.regularExpression)\b"),
        # BUG FIX: `Date\(\)` ends on `)` (non-word), so the shared
        # trailing \b could never fire. Never matched.
        "time_date_logic": re.compile(
            r"\b(?:Calendar\.current|DateFormatter|DispatchTime\.now|Timer\.scheduledTimer)\b|\bDate\(\)"
        ),
        # BUG FIX: `Process\(\)` ends on `)` -- same bug. Never matched.
        "ipc_rpc_bridges": re.compile(
            r"\b(?:URLSession|NSXPCConnection|NotificationCenter|DispatchQueue)\b|\bProcess\(\)"
        ),
    },
}
