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

from .._shared_patterns import (
    GLOBAL_DL_FRAMEWORKS,
    GLOBAL_FRAGILE_DEBT,
    GLOBAL_LLM_API,
    GLOBAL_LLM_ORCHESTRATOR,
    GLOBAL_LLM_VECTOR_STORE,
    GLOBAL_ML_TRADITIONAL,
    GLOBAL_PLANNED_DEBT,
)

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "ES2025 / React 19 / Node 22+",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, legacy server-side formats, UI extensions, and embedded scripts.
    "extensions": [
        ".js",
        ".mjs",
        ".cjs",
        ".jsx",
        ".es6",
        ".es",
        ".pac",
        ".sjs",
        ".ssjs",
        ".xsjs",
        ".xsjslib",
        ".jsm",
        "._js",
        ".bones",
        ".gs",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
    "exact_matches": ["Jakefile"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
    "discriminators": [
        ".js",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bower.json",
        ".eslintrc",
        ".prettierrc",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["node", "nodejs", "deno", "bun", "zx", "phantomjs", "casperjs"],
    # UPGRADED: Maps to Family 1 (Standard C)
    # Rationale: Uses '//' for line-level literature; multi-line literature
    # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. EXCLUDES throw (bailout_hits).
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|while|do|catch|finally|continue|break|try)\b|&&|\|\||\?|\?\?"
        ),
        # 2. args (Parameters / Coupling)
        # Parameter blocks. Bounded to prevent ReDoS on massive positional/destructured sets.
        "args": re.compile(
            # =====================================================================
            # [ THE GHOST ARGS SHIELD (JAVASCRIPT) ]
            # JS class methods (e.g., `TargetFunc(config) {`) lack the `function` keyword.
            # Without an anchor, the engine hallucinated standard invocations as definitions.
            # FIX 1 (Invocation Shield): Injected `(?=[ \t\n]*\{)` at the end of the class
            # method branch, demanding structural proof that the signature opens a logic block.
            # FIX 2 (Control Flow Shield): `while (i < 10) {` structurally mimics a method.
            # Injected `(?!(?:if|for|while|switch|catch|return)\b)` to prevent reserve words
            # from being mapped as method names.
            # FIX 3 (Quadratic Blowup Shield): The arrow-function branch's identifier
            # match used an unbounded `[\w$]*`. On a long line with no `=>` at all
            # (e.g. a single massive minified/obfuscated line), the engine retried the
            # greedy-then-backtrack identifier match at every starting position,
            # producing O(n^2) time (empirically: ~3.5s at 20,000 chars, scaling
            # quadratically from there). Bounded to {0,100} -- real identifiers don't
            # get remotely that long -- per this doc's own "strict numeric clamps"
            # rule; possessive quantifiers (`*+`) would be cleaner but aren't
            # available until Python 3.11, and this package supports 3.9+.
            # =====================================================================
            # GENERATOR METHOD FIX (epic #813/#814): the class-method branch had no
            # allowance for the leading `*` ES6 generator method shorthand uses
            # (`*foo(a, b) {}`, `async *foo(a, b) {}`) -- same gap already fixed in
            # func_start for this language. Deliberately NO whitespace tolerance
            # between `*` and the name (unlike the other modifier gaps): a real
            # generator method always hugs the star to the name with zero space
            # (Prettier/every real formatter), and allowing whitespace there let a
            # JSDoc comment continuation line (`* A (storage) buffer...` -- the `*`
            # is the comment marker, "A" is prose) false-positive-match as a
            # generator method named "A" -- caught empirically via crucible_check.py
            # against real corpus code (threejs), not by any test case alone.
            # #1209: parameter-list span wrapped in its own capture group
            # in all three branches (was only reachable via group(0), the
            # whole match including the "function"/"static"/name prefix)
            # so detector.py's counter isolates just the real parameter
            # text -- the whole-match fallback overcounted every zero/
            # one-arg signature by +1 the same way Python's did (#1199).
            # Name groups added to branches 1/3 too, purely so existing
            # extraction tests keep passing.
            r"(?:"
            r"\b(?:async[ \t\n]+)?function[ \t\n]*\*?[ \t\n]*(\w*)[ \t\n]*(\([^)]*\))|"
            r"(\([^)]*\)|[a-zA-Z_$][\w$]{0,100})[ \t\n]*=>|"
            r"^[ \t]*(?:static[ \t\n]+)?(?:async[ \t\n]+)?(?:get[ \t\n]+|set[ \t\n]+)?\*?(?!(?:if|for|while|switch|catch|return)\b)(#?[a-zA-Z_$][\w$]*)[ \t\n]*(\([^)]*\))(?=[ \t\n]*\{)"
            r")",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural declaration boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(let|var|import|export|return|class|extends|super|await|delete|yield)\b|=>"
        ),
        # 4. func_start (Executable Logic Anchors)
        # Uses positive lookaheads (?=) to stop the match exactly at the identifier name.
        # Captures standard functions, namespace assignments (foo.bar = function),
        # object literal methods (foo: function), and ES6 methods.
        "func_start": re.compile(
            r"(?:"
            r"\b(?:async\s+)?function\s*\*?\s+[a-zA-Z_$][\w$]*(?=\s*\()|"
            # =====================================================================
            # [ THE VERTICAL ASSIGNMENT SHIELD ] (Hard-learned lesson from Pathological Fuzzer)
            # PURPOSE: JavaScript developers frequently format complex asynchronous
            # fat-arrow functions across multiple lines (e.g., `export const \n foo \n = \n async () =>`).
            # THE FIX: We replaced horizontal-only spaces `[ \t]*` with `[ \t\n]*`
            # around the `=` and `:` assignment operators, as well as the `=>` arrow.
            # This allows the lookahead to safely cross vertical line breaks without
            # resorting to an unbounded `\s*` which causes ReDoS.
            # =====================================================================
            r"(?:^|(?<=[^<>(,\s]))[ \t\n]*(?<!\.\.\.)\b[a-zA-Z_$][\w$]*(?:\[[^\]\n]+\])?(?=[ \t\n]*=[ \t\n]*(?:async\s*)?(?:function(?:\s*\*)?\b|\([^)]*\)[ \t\n]*(?::[^=;]+)?[ \t\n]*=>|[a-zA-Z_$][\w$]*[ \t\n]*=>))|"
            r"^[ \t]*(?:\[[^\]\n]+\]|[a-zA-Z_$][\w$]*)(?=[ \t\n]*:[ \t\n]*(?:async\s*)?(?:function(?:\s*\*)?\b|\([^)]*\)[ \t\n]*(?::[^=;]+)?[ \t\n]*=>|[a-zA-Z_$][\w$]*[ \t\n]*=>))|"
            # GENERATOR METHOD FIX (epic #813/#814): class/object-literal generator
            # methods (`*foo() {}`, `async *foo() {}`, `static *foo() {}`) were
            # completely invisible -- this branch had no allowance for the leading
            # `*` that ES6 generator method shorthand uses (unlike the plain
            # `function*` declaration branch above, which already had `\*?`).
            # Deliberately NO whitespace tolerance between `*` and the name: a real
            # generator method always hugs the star to the name with zero space
            # (every real formatter), and allowing whitespace there let a JSDoc
            # comment continuation line (`* A (storage) buffer...` -- the `*` is the
            # comment marker, "A" is prose) false-positive-match as a generator
            # method named "A" -- caught empirically via crucible_check.py against
            # real corpus code (threejs), not by any test case alone.
            # #1221: the trailing lookahead used to be just `(?=\s*\()`
            # -- proof a `(` follows, nothing more -- so any bare call
            # statement starting a line (`next();`) false-positive-
            # matched as a method definition, the exact defect class
            # this file's own `args` regex already named and fixed for
            # this identical branch shape ("Invocation Shield",
            # `(?=[ \t\n]*\{)`). Mirrored here: now requires the
            # (non-nested, same bound as `args`) parameter list to
            # actually close and be followed by a real body opener.
            # `(?:=>[ \t\n]*)?` before the `{` is NOT real JS method
            # syntax (methods never have `=>` between params and body)
            # -- it exists solely to keep matching the ALREADY-
            # documented, deliberately-NOT-fixed harder ambiguity
            # (`describe('x', () => {`-shaped call-with-inline-callback
            # statements, see the known_limitation test right below)
            # working the same as before; only a bare statement with
            # neither `{` nor `=>` anywhere (e.g. `next();`) is newly
            # rejected.
            r"^[ \t]*(?:static[ \t\n]+)?(?:async[ \t\n]+)?(?:get\s+|set\s+)?\*?(?!(?:if|for|while|switch|catch|return|throw|new|typeof|jQuery|function)\b|\$)#?[a-zA-Z_$][\w$]*(?=[ \t\n]*\([^)(]*\)[ \t\n]*(?::[^{=;]+)?[ \t\n]*(?:=>[ \t\n]*)?\{)"
            r")",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]+){0,5}(?:export[ \t]+)?(?:default[ \t]+)?class\s+([a-zA-Z_$][\w$]*)(?:\s+extends\s+([a-zA-Z_$][\w$.]*))?",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(try|catch|finally|typeof|instanceof|Array\.isArray|Number\.(?:isFinite|isNaN)|Object\.hasOwn)\b|===|!==|\?\?|\?\."
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Loose equality and bypasses. (?<![=!]) on the == branch: without
        # it, `===`/`!==` (strict equality/inequality -- explicitly SAFE
        # per this language's own `safety` rule) both still matched via
        # their trailing `==` substring at a shifted offset.
        "safety_bypasses": re.compile(r"(?<![=!])==(?!=)|!=(?!=)|\b(with|void)\b|eslint-disable|@ts-nocheck"),
        # 8. danger (High-Risk Execution / System Calls)
        # Catastrophic vulnerabilities. EXCLUDES console.log (print_hits) and TODO (debt).
        "high_risk_execution": re.compile(
            r"\b(eval|document\.write|innerHTML|outerHTML|dangerouslySetInnerHTML|debugger|alert|process\.exit)\b"
        ),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(fetch|axios|http|https|fs|path|database|sql|localStorage|sessionStorage|indexedDB|document\.cookie|XMLHttpRequest|child_process)\b"
        ),
        # 10. api (Public Surface Area)
        # Exposure surface. Explicit exports + implicit architectural defaults.
        "api": re.compile(r"\b(export|module\.exports|exports\.)\b|@(Controller|Resolver|Get|Post|Put|Delete)\b"),
        # 11. flux (State Mutation)
        # Mutation of state. EXCLUDES const (freeze_hits).
        "state_mutation": re.compile(
            r"\b(let|var|this\.|setState|mut|push|pop|shift|unshift|splice|sort|reverse|\.current[ \t]*=|\.set\(|\.delete\(|\.add\()\b"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"//[ \t]*(?:if|for|while|function|class|return|var|const|let|import)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"/\*\*|@param|@return|@throws|@deprecated|@typedef|@type|@template"),
        # 14. test (Testing & Assertions)
        # (?<!\.) on the it|test alternation: TypeScript's near-identical rule
        # already carries this guard so `myRegex.test('x')` (a regex method
        # call) isn't miscounted as a test-framework call -- JavaScript's own
        # rule never got the same fix despite the identical ambiguity.
        "test": re.compile(
            r"\b(describe|expect|assert|beforeEach|afterEach|jest|mocha|vitest|cy\.)\b|(?<!\.)\b(?:it|test)\s*\("
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(async|await|Promise|requestAnimationFrame|setImmediate|setTimeout|setInterval|queueMicrotask|Worker|postMessage)\b|\.then\(|\.catch\("
        ),
        # 16. ui_framework (UI / View Components)
        "ui_framework": re.compile(
            r'<[A-Z]\w+|className=|use(?:State|Effect|Context|Reducer|Ref|Memo|Callback|Transition)|props\.|this\.state|document\.(?:getElementById|querySelector|addEventListener)|["\']use\s+(?:client|server)["\']'
        ),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(r"=>[ \t]*\{|\(\)[ \t]*=>|function\s*\([^)]*\)[ \t]*\{"),
        # 18. globals (Global / Shared State)
        "globals": re.compile(r"\b(window\.|global\.|process\.env|document\.|navigator\.|self\.|globalThis\.)\b"),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"@\w+"),
        # 20. generics (Generics / Type Parameters)
        # Simulated/JSDoc generics in JS.
        "generics": re.compile(r"@template\s+\w+|/\*\*\s*@type\s*(?:\{|<\w+)"),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(r"\.(?:map|filter|reduce|flatMap|some|every|find|forEach|groupBy)\s*\("),
        "scientific": re.compile(r"\b(?:import|require|from)\b.*?(?:numpy|pandas|scipy|matplotlib|opencv|cv2)\b"),
        "hardware_bridge": re.compile(
            r"\b(?:import|require|from)\b.*?(?:serialport|usb|bluetooth|socket\.io|websocket|printer|webgl)\b"
        ),
        "cryptography": re.compile(
            r"\b(?:import|require|from)\b.*?(?:crypto|bcrypt|x509|tls|ssl|jsonwebtoken|argon2)\b"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        "reflection_metaprogramming": re.compile(
            r"\b(arguments\.|prototype|__proto__|Object\.assign|Reflect|Proxy|Object\.defineProperty|\.bind\(|\.call\(|\.apply\()\b"
        ),
        # --- AI & LLM SDK SENSORS (GLOBAL_, see #322) ---
        "llm_api": GLOBAL_LLM_API,
        "llm_orchestrator": GLOBAL_LLM_ORCHESTRATOR,
        "llm_vector_store": GLOBAL_LLM_VECTOR_STORE,
        "ml_traditional": GLOBAL_ML_TRADITIONAL,
        "dl_frameworks": GLOBAL_DL_FRAMEWORKS,
        # 24. import (Dependency Inclusions)
        "import": re.compile(
            r"\b(?:import|export)\b[^;]*?\bfrom\b|\brequire\s*\(|\bimport\s*\(",
            re.M,
        ),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (JAVASCRIPT) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
            #
            # HISTORICAL BUG: Originally, the `import` regex was anchored to the start of the
            # line `^[ \t]*`. While this perfectly prevented the engine from hallucinating
            # commented-out imports, it completely blinded the firewall to dynamic/inline execution.
            # If an attacker tucked an import inside a function (e.g., `const payload = require('malware')`
            # or `await import('trojan')`), it bypassed the sensors entirely.
            #
            # THE FIX: The `^` anchor has been stripped across both the counter and the capture regex.
            # We now rely on the `\b` word boundary to find the keywords anywhere in the file.
            # (Note: The engine's optical comment-stripper runs BEFORE this regex, naturally preventing
            # the commented-out hallucination issue without needing strict line anchors).
            #
            # [ THE VERTICAL DESTRUCTURING SHIELD ]
            # We enforce `[ \t\n]*` near the `from` and inside the `require()` parentheses to safely
            # leap across vertical multi-line destructured imports (e.g., `import \n { \n Component \n } \n from`).
            # =====================================================================
            r"(?:import|export)\b[^;]*?\bfrom\s*['\"]([^'\"]+)['\"]|\b(?:require|import)\s*\(\s*['\"]([^'\"]+)['\"]",
            re.M,
        ),
        "_named_token_capture": re.compile(r"(?:import|export)\s+\{([^}]+)\}", re.M),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"(?:@author|Created by)\s+(.*)", re.I),
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
            r"\b(getServerSideProps|getStaticProps|getInitialProps|renderToString|hydrateRoot)\b"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(r"\b(emit|on|once|off|dispatchEvent|EventEmitter|EventTarget)\b"),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(r"\b(Inject|Injectable|Container|resolve|register|inversify)\b"),
        # 34. macros
        "macros": None,
        # 35. pointers
        "pointers": None,
        # 36. memory_alloc
        "memory_alloc": re.compile(r"\bnew\s+[A-Z]\w*"),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(logger|winston|pino|morgan|datadog|prometheus|newrelic|sentry)\.(?:info|error|warn|debug|trace|log)\b"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\bconsole\.(?:log|warn|error|dir|trace|info|table|time)\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"\b(Number|String|Boolean|BigInt|Symbol|Array\.from)\b\s*\("),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|abort|process\.exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(sleep|delay|setTimeout|setInterval|Atomics\.wait)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>>?|\^|~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(
            r"\b(mutex|lock|synchronized|Semaphore|Atomics\.lock|Atomics\.wait)\b",
            re.I,
        ),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(const|readonly|final|Object\.freeze|Object\.seal)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(dispose|close|destroy|clearTimeout|clearInterval|removeEventListener|delete)\b"),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # JS private fields and keywords. `#` needed its own un-bounded
        # branch: \b#\b can only match when `#` is directly sandwiched
        # between two word characters with no separator (e.g. "x#y"),
        # which never happens in real private-field syntax (`#foo` is
        # always preceded by `{`, whitespace, or `.` -- never a bare word
        # char) -- so the `#` alternative was completely unreachable.
        "encapsulation": re.compile(r"\b(private|protected|internal)\b|#[a-zA-Z_$]"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(on|addEventListener|subscribe|watch|effect)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(test\.skip|it\.skip|describe\.skip|xit|xdescribe|mock|stub)\b"),
        # --- NEW: ADVANCED ALGORITHMIC SENSORS ---
        "lazy_evaluation": re.compile(r"\b(yield|yield\s*\*|function\s*\*)\b"),
        "vectorized_math": re.compile(r"\b(matmul|dot|cross|multiply)\s*\("),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (JS/TS Specifics) ---
        "serialization_parsing": re.compile(r"\b(JSON\.parse|JSON\.stringify)\b"),
        "regex_execution": re.compile(r"\bnew\s+RegExp\b|\.(match|replace|search|split)\s*\("),
        "time_date_logic": re.compile(
            r"\b(Date\.now|new\s+Date|setTimeout|setInterval|clearTimeout|clearInterval|performance\.now)\b"
        ),
        "ipc_rpc_bridges": re.compile(r"\b(postMessage|Worker|MessageChannel|child_process|worker_threads|cluster)\b"),
        # --- PHASE 4: APPSEC & AI SENSORS (Zero-Trust Pipelines) ---
        "rce_funnel": re.compile(r"child_process\.(?:spawn|exec|execSync)\s*\(\s*['\"](?:python|bash|sh|bun|node)\b"),
        "exfiltration_camouflage": re.compile(
            r"\b(fetch|axios\.post|https\.request)\s*\([^)]*(?:checkmarx|telemetry|metrics|audit|log)\b",
            re.I,
        ),
    },
}
