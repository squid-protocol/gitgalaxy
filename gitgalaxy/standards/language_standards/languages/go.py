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
        "target_version": "Go 1.22+ (Generics, Slog, Workspace paradigms)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    "extensions": [".go"],
    "exact_matches": [],
    "discriminators": [
        ".go",
        "go.mod",
        "go.sum",
        "go.work",
        "Gopkg.toml",
        "Gopkg.lock",
        "glide.yaml",
        "vendor/modules.txt",
    ],
    "shebangs": ["go", "gorun", "yaegi"],
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Includes select/case and range-based loops. EXCLUDES panic (bailout_hits).
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|range|select|goto|break|continue|fallthrough)\b|&&|\|\|"
        ),
        # 2. args (Parameters / Coupling)
        # Parameter blocks for functions and methods. Bounded generics [^\]]* and params [^)]*.
        # #1209: parameter-list span wrapped in its own capture group (was
        # only reachable via group(0), the whole match including the
        # "func"/receiver/name prefix) so detector.py's counter isolates
        # just "(...)" -- the whole-match fallback overcounted every
        # zero/one-arg signature by +1 the same way Python's did (#1199).
        # Name group added too, purely so existing extraction tests (which
        # check the captured name) keep passing.
        "args": re.compile(
            r"func[ \t\n]+(?:\([^)]*\)[ \t\n]+)?(\w*)(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?[ \t\n]*(\((?:[^()]|\([^()]*\))*\))",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: const/var (freeze_hits) and Capitalization (encapsulation).
        "structural_boundaries": re.compile(r"\b(package|import|return|type|go|defer|chan|map|interface|struct)\b"),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks.
        # Bypasses the 'func' keyword, skips optional method receivers (e.g. (s *Server)),
        # and strictly captures the actual identifier name. Ignores anonymous functions.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL RECEIVER SHIELD ]
            # Go developers occasionally format complex struct receivers across multiple lines.
            # FIX: Replaced horizontal spaces `[ \t]+` with `[ \t\n]+` around the `func`
            # keyword, receiver block, and function name to safely leap across vertical gaps.
            # GENERIC FUNCTION FIX (epic #813/#817): a top-level generic function's own
            # type-parameter list (`func Foo[T constraints.Ordered](a, b T) T {`, Go 1.18+,
            # mainstream since 2022) went straight from the captured name to `[ \t\n]*\(` with
            # no allowance for a `[...]` list in between, so the whole function was invisible
            # to the engine. (Generic *methods* with a receiver already matched by accident --
            # the receiver's own `[^)]+` char class doesn't care about brackets -- and
            # class_start/args already had this exact step-over; func_start was the outlier.)
            # Added the same bounded, already-proven-safe `(?:[ \t\n]*\[[^\]]*\])?` step-over.
            # =====================================================================
            r"^[ \t]*func(?:[ \t\n]+\([^)]+\))?[ \t\n]+([A-Za-z_$][\w_$]*)(?:[ \t\n]*\[(?:[^\[\]]|\[[^\[\]]*\])*\])?[ \t\n]*\(",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # =====================================================================
        # [ THE VERTICAL GENERICS SHIELD (GO) ]
        # Go 1.18+ introduces generic type parameters `[T any]` which can be
        # vertically formatted before the `struct` or `interface` keyword.
        # FIX: Injected a capture group `([a-zA-Z_]\w*)` for exact entity name
        # extraction. Upgraded the `\s+` to explicitly bounded `[ \t\n]+` and
        # decoupled the generic stepper `(?:[ \t\n]*\[[^\]]*\])?` to safely
        # leap across vertical boundaries.
        # =====================================================================
        "class_start": re.compile(
            r"^[ \t]*type[ \t\n]+([a-zA-Z_]\w*)(?:[ \t\n]*\[(?:[^\[\]]|\[[^\[\]]*\])*\])?[ \t\n]+(?:struct|interface)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # BUG FIX: `recover\(\)` ends on `)` (non-word), so the shared
        # trailing \b could never fire -- the classic
        # `defer func() { recover() }()` idiom never matched.
        "safety": re.compile(
            r"err\s*!=\s*nil|\b(?:errors\.(?:Is|As|New|Join)|sync\.(?:Once|WaitGroup)|context\.Context)\b|\brecover\(\)"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Explicitly ignoring errors via blank identifier.
        "safety_bypasses": re.compile(r'_\s*,\s*err[ \t]*=|_[ \t]*=\s*\w+|\bimport\s+(?:\.[ \t]+)?"'),
        # 8. danger (High-Risk Execution / System Calls)
        # Process-killing commands and direct syscalls. EXCLUDES TODO (debt) and fmt.Print (print_hits).
        "high_risk_execution": re.compile(r"\b(os\.Exit|syscall\.Kill|syscall\.RawSyscall|log\.Fatal(?:f|ln)?)\b"),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(os\.(?:Open|Create|ReadFile)|io\.(?:Reader|Writer|Copy)|net/http|database/sql|bufio\.|grpc\.|sqlx\.|pgx\.)\b"
        ),
        # 10. api (Public Surface Area)
        # Implicit Public Reality: Capitalized top-level identifiers in Go are public.
        # BUG FIX: `^[ \t]*` allowed arbitrary leading whitespace, so
        # the original (no-prefix) form matched ANY indented line
        # starting with a capitalized word -- including a bare call to
        # an exported function inside a function body
        # (`    DoSomething()`), which is not a declaration at all.
        # Column-0-only anchoring alone overcorrects: Go's grouped
        # `var (...)`/`const (...)` blocks legitimately indent their
        # member declarations (e.g. `const (\n\tBurstReplicas = 500\n)`
        # in real k8s source), and those ARE top-level/exported. So:
        # explicit `func`/`type`/`var`/`const` keyword forms stay
        # anchored to column 0 (gofmt never indents these), while the
        # no-prefix fallback (for grouped members) keeps indentation
        # tolerance but requires it (a bare col-0 identifier isn't
        # valid Go outside a group) and excludes anything immediately
        # followed by `(` -- a grouped member is `Name = value` or
        # `Name Type`, never `Name(`, which is what a real function
        # CALL statement looks like. The trailing `\b` before the
        # lookahead is required: without it, greedy `\w+` can
        # backtrack one character short of the real identifier end
        # purely to dodge the `(?!\()` check (matching `DoSomethin`
        # instead of `DoSomething` to sidestep the `(` in
        # `DoSomething(`) -- `\b` forces the lookahead to apply at the
        # true word boundary, where backtracking can't produce a
        # second valid stopping point.
        "api": re.compile(
            r"^func\s+(?:\([^)]*\)[ \t]+)?[A-Z]\w+|^(?:type|var|const)\s+[A-Z]\w+|^[ \t]+\b[A-Z]\w+\b(?!\()",
            re.M,
        ),
        # 11. flux (State Mutation)
        # Mutation of state. Reassignment and channel sends.
        "state_mutation": re.compile(r":=|(?<![=!<>])=(?![=])|<-|\bappend\(|\batomic\.(?:Add|Store|Swap)"),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"//[ \t]*(?:func|type|var|const|import|if|for|switch|select|return)\b"),
        # 13. doc (Structured Documentation)
        # GoDoc standard: comments immediately preceding a declaration.
        "doc": re.compile(r"^[ \t]*//\s+[A-Z][a-zA-Z0-9_]+\s+.*|^[ \t]*//\s*Package\s+", re.M),
        # 14. test (Testing & Assertions)
        "test": re.compile(r"\b(?:Test|Benchmark|Fuzz)[A-Z]\w*\b|t\.Run\b|\b(?:assert|require|mock)\.\w+\("),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # BUG FIX: `select[ \t]*\{` ends on `{` (non-word), so the
        # shared trailing \b only fired when a word char immediately
        # followed the brace -- never true in real Go, where a `select`
        # block's body always starts on the next line (or at least
        # with whitespace) after the opening brace. This core
        # concurrency primitive never matched at all, spaced or not.
        "concurrency": re.compile(
            r"\b(?:go\s+func|go\s+\w+|chan\s+|context\.(?:WithTimeout|WithCancel)|errgroup\.Group)\b"
            r"|select[ \t]*\{"
        ),
        # 16. ui_framework (UI / View Components)
        # Go is primarily backend; targets templates and web handlers.
        "ui_framework": re.compile(
            r"\b(html/template|text/template|http\.HandleFunc|ServeHTTP|gin\.|echo\.|fiber\.)\b"
        ),
        # 17. closures (Closures / Anonymous Functions)
        # BUG FIX (ReDoS): confirmed genuine O(n^2) scaling (0.32s/
        # 1.27s/5.12s/20.6s for n=2k/4k/8k/16k, ~4x per doubling; 68.6s
        # observed at n=30k) against an adversarial payload with two
        # large whitespace runs (`func` + huge ws + `(recv)` + huge ws
        # + unclosed name) that ultimately fails to complete a match --
        # the three unbounded `\s*` occurrences plus the two unbounded
        # `[^)]*`/`[^\]]*` classes force exhaustive backtracking across
        # every combination of how much each could consume. Bounded
        # every quantifier, and replaced the two narrowly-specific
        # optional groups (generics brackets, multi-return parens) with
        # one bounded `[^{]{0,80}` gap -- this also fixes a real,
        # separate gap: a bare (non-parenthesized) single return type
        # (`func(x int) int {`) never matched either shape.
        "closures": re.compile(r"func[ \t\n]{0,80}\([^)]{0,300}\)[^{]{0,80}\{"),
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            r"^[ \t]*var\s+[a-zA-Z_]\w*\s*(?:[a-zA-Z_]\w*\s*)?=|os\.Getenv|os\.Environ",
            re.M,
        ),
        # 19. decorators (Decorators / Annotations)
        # Go lacks @decorators; uses Struct Tags and Build Tags.
        "decorators": re.compile(r'`[^`]*?(?:json|xml|yaml|gorm|db|bson):"[^"]*"[^`]*?`|//go:build|//\s*\+build'),
        # 20. generics (Generics / Type Parameters)
        # BUG FIX: `~[a-zA-Z_]\w*` (the Go 1.18+ approximation-element
        # constraint, e.g. `~int`) starts with `~` (non-word), so the
        # shared leading \b could only fire when a word char
        # immediately preceded the `~` -- never true for how this
        # constraint is actually written (always preceded by a space
        # or `|` inside the type-parameter brackets). Never matched.
        "generics": re.compile(
            r"\[(?:[^\[\]]|\[[^\[\]]*\])*(?:\b(?:any|comparable)\b|~[a-zA-Z_]\w*\b)(?:[^\[\]]|\[[^\[\]]*\])*\]|\bany\b"
        ),
        # 21. comprehensions (Iterators / Comprehensions)
        # Functional iteration helpers from the slices/maps packages.
        "comprehensions": re.compile(r"\b(slices\.(?:Delete|Filter|Sort|Compact)|maps\.(?:Keys|Values))\b"),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(math\.|math/cmplx\.|math/rand\.|crypto/rand\.|gonum\.)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Reflection, CGO, and Unsafe triggers.
        "reflection_metaprogramming": re.compile(r'import\s+"C"|\b(reflect\.|unsafe\.|cgo|go:linkname)\b'),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r'^[ \t]*import\s*(?:\(|"[^"]+")', re.M),
        # ---> THE FIX: Strictly bounded to valid Go import path characters <---
        # Prevents raw HTTP string literals in test files from being hallucinated as packages.
        "_dependency_capture": re.compile(
            r'^[ \t]*(?:import\s+)?(?:\(\s*)?(?:[a-zA-Z0-9_.]+\s+)?["`]([a-zA-Z0-9_.\-/]+)["`]',
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"(?://|#|/\*)\s*(?:Author|Maintainer|Created by|Owner):?\s+([a-zA-Z0-9_ -]+)",
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
        "ssr_boundaries": re.compile(r"\b(html/template|ExecuteTemplate|http\.ResponseWriter|Render|gin\.Context)\b"),
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(r"\b(EventBus|Publish|Subscribe|kafka\.|rabbitmq\.|Emit|OnEvent)\b"),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(
            r"\b(wire\.Build|wire\.NewSet|fx\.New|fx\.Provide|fx\.Invoke|dig\.Provide|do\.Provide)\b"
        ),
        # 34. macros (Preprocessor Directives / Macros)
        # Go lacks a preprocessor; //go: directives act as compile-time hooks.
        "macros": re.compile(r"^//go:(?:generate|build|noinline|nosplit|noescape|linkname)\b", re.M),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Explicit pointer addressing and dereferencing.
        "pointers": re.compile(
            r"\b(?:uintptr|unsafe\.Pointer)\b|&\w+|\*(?:[A-Z]\w*|int\d*|uint\d*|float\d*|byte|rune|string|bool)\b"
        ),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(r"\b(make|new)\s*\(|sync\.Pool\b"),
        # 37. inline_asm
        "inline_asm": None,  # Go handles ASM in separate .s files.
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(slog|logrus|zap|zerolog|log)\.(?:Info|Warn|Error|Debug|Trace)(?:f|ln)?\b|\btrace\.Span\b"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(fmt\.Print|fmt\.Println|fmt\.Printf|println|print)\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        # Type assertions and conversions.
        "explicit_casts": re.compile(
            r"\.\([a-zA-Z_]\w*\)|\b(?:int|int8|int16|int32|int64|uint|uint8|uint16|uint32|uint64|float32|float64|byte|rune|uintptr|string)\s*\("
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(panic|os\.Exit|log\.Fatal)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(time\.Sleep|time\.After|runtime\.Gosched)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>|\^|&\^"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(Mutex|RWMutex|Lock|Unlock|RLock|RUnlock|atomic\.|sync\.Map|sync\.Pool)\b"),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\bconst\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(defer|Close|Unlock|RUnlock|Stop|Cleanup)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Unexported identifiers (lowercase) in Go are private/internal.
        # BUG FIX (two layered issues):
        # 1. `^[ \t]*` allowed arbitrary leading whitespace, so this
        #    matched ANY indented line starting with a lowercase word
        #    -- effectively every statement in Go (`if`, `for`,
        #    `return`, a bare function call, ...), since almost all
        #    keywords and local identifiers are lowercase. gofmt never
        #    indents real package-level declarations (always column
        #    0), so anchored to `^` with no whitespace tolerance,
        #    matching the same fix applied to `api` above.
        # 2. Even after that fix, the `func` prefix in alt 1 was
        #    OPTIONAL, so on a line like `func Foo() {` the engine
        #    could skip matching "func" as the prefix and instead
        #    fall through to matching the literal word "func" itself
        #    via the bare `[a-z]\w+` fallback (since "func" is itself
        #    lowercase) -- misclassifying an exported, PUBLIC function
        #    as private. `type`/`var`/`const` don't have this problem
        #    in alt 2 since consuming the keyword is mandatory there.
        #    Made the `func` prefix mandatory in alt 1 too (Go has no
        #    top-level declaration form other than these 4 keywords,
        #    so there's no real case an optional prefix was needed for).
        # 3. Column-0-only anchoring alone overcorrects: Go's grouped
        #    `var (...)`/`const (...)` blocks legitimately indent their
        #    member declarations, and an unexported member of one of
        #    those groups IS still a private top-level identifier. The
        #    no-prefix fallback keeps indentation tolerance for this
        #    case, but requires it (bare col-0 identifiers aren't valid
        #    Go outside a group) and explicitly excludes Go's
        #    lowercase reserved keywords (which is what let `if`/`for`/
        #    `return`/etc. through in the first place) and anything
        #    immediately followed by `(` (a real function CALL
        #    statement, not a `Name = value`/`Name Type` group member).
        #    The trailing `\b` before the lookahead is required for
        #    the same reason as in `api` above: without it, greedy
        #    `\w+` can backtrack one character short of the real
        #    identifier end purely to dodge the `(?!\()` check.
        "encapsulation": re.compile(
            r"^func\s+(?:\([^)]*\)[ \t]+)?[a-z]\w+|^(?:type|var|const)\s+[a-z]\w+"
            r"|^[ \t]+(?!(?:if|else|for|switch|case|default|break|continue|goto|fallthrough"
            r"|return|go|defer|select|range|func|type|var|const|package|import|struct"
            r"|interface|map|chan|make|new|nil|true|false|iota)\b)\b[a-z]\w+\b(?!\()",
            re.M,
        ),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"<-chan\b|\.On\(|\.Subscribe\("),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\bt\.Skip(?:f|Now)?\(|mock\.|gomock\."),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Go Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(json\.Unmarshal|json\.Marshal|xml\.Unmarshal|xml\.Marshal|gob\.NewEncoder)\b"
        ),
        "regex_execution": re.compile(r"\b(regexp\.Compile|regexp\.MustCompile|\.MatchString)\b"),
        # BUG FIX: `time\.Now\(\)` ends on `)` (non-word), so the
        # shared trailing \b could never fire (whatever follows a
        # function call -- `;`, a newline, another `.method()`, or end
        # of string -- is never a word character). Go's single most
        # common time-related call never matched in any real usage.
        "time_date_logic": re.compile(r"\b(?:time\.Parse|time\.Duration|time\.Sleep|time\.Since)\b|time\.Now\(\)"),
        "ipc_rpc_bridges": re.compile(r"\b(net/rpc|grpc\.Dial|grpc\.NewServer|exec\.Command|syscall)\b"),
    },
}
