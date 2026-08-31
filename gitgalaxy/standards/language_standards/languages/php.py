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
        "target_version": "PHP 8.5.x / Modern Laravel 11+, Symfony 7+, & PSR-12 Paradigms",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Merged standard suffixes, legacy formats, UI templates (.phtml, .ctp), and CMS "unparsable artifacts" (.module, .inc).
    "extensions": [
        ".php",
        ".phtml",
        ".php3",
        ".php4",
        ".php5",
        ".php7",
        ".php8",
        ".phps",
        ".ctp",
        ".module",
        ".inc",
        ".theme",
        ".install",
        ".profile",
        ".engine",
        ".aw",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless framework CLI entry points that are secretly pure PHP code.
    "exact_matches": ["artisan", "composer.phar", "drush", "wp-cli", "phpunit"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files (like .inc).
    "discriminators": [
        ".php",
        "composer.json",
        "composer.lock",
        "phpunit.xml",
        "phpunit.xml.dist",
        "phpcs.xml",
        ".php_cs",
        ".php_cs.dist",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["php", "php-cli", "php-cgi", "hhvm"],
    # UPGRADED: Maps to Family 6 (Polyglot)
    # Rationale: PHP fundamentally operates within an HTML context, requiring the parser
    # to explicitly hunt for <?php execution boundaries. It also supports multiple
    # comment styles (//, #, and /* */).
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Control flow. Includes modern match expression. EXCLUDES throw (bailout_hits).
        "branch": re.compile(
            r"(?<!\$)(?<!->)(?<!::)\b(if|else|elseif|switch|case|default|foreach|for|while|do|try|catch|finally|break|continue|match|goto)\b|&&|\|\||\?\?|\?"
        ),
        # 2. args (Parameters / Coupling)
        # Signatures for functions and arrow functions. Bounded to prevent ReDoS.
        # #1209: parameter-list span wrapped in its own capture group (was
        # only reachable via group(0), the whole match including the
        # "function"/"fn"/name prefix) so detector.py's counter isolates
        # just "(...)" -- the whole-match fallback overcounted every
        # zero/one-arg signature by +1 the same way Python's did (#1199).
        # Name group added too, purely so existing extraction tests keep
        # passing.
        "args": re.compile(
            r"(?<!\$)(?<!->)(?<!::)\b(?:function|fn)[ \t\n]*(?:&[ \t\n]*)?(?:/\*.*?\*/[ \t\n]*){0,3}([a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*)?[ \t\n]*(\((?:(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")|\((?:(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")|\((?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")*\))*\))*\))",
            re.M | re.I,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const/readonly (freeze_hits).
        "structural_boundaries": re.compile(
            r"(?<!\$)(?<!->)(?<!::)\b(namespace|use|class|interface|trait|enum|function|return|yield|declare|require|require_once|include|include_once|as|implements|extends|clone|new)\b"
        ),
        "func_start": re.compile(
            r"(?:^|(?<!->)(?<!::)[^a-zA-Z0-9_$])(?:#\[(?:[^\]\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")*\][ \t\n]*){0,10}"
            r"(?:(?:public|protected|private|static|final|abstract)[ \t\n]+){0,5}"
            r"(?<!->)(?<!::)\bfunction[ \t\n]+(?:&[ \t\n]*)?(?:/\*.*?\*/[ \t\n]*){0,3}([a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*)[ \t\n]*(?=\()",
            re.M | re.I,
        ),
        "class_start": re.compile(
            r"^[ \t]*(?:#\[(?:[^\]\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")*\][ \t\n]*){0,10}"
            r"(?:(?:abstract|final|readonly)[ \t\n]+){0,3}(?:class|interface|trait|enum)[ \t\n]+(?:/\*.*?\*/[ \t\n]*){0,3}(?!(?:extends|implements)\b)([a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*)(?![a-zA-Z0-9_\x80-\xff])",
            re.M | re.I,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(try|catch|finally|declare\s*\(\s*strict_types[ \t]*=\s*1\s*\)|readonly|Throwable|Exception|assert|isset|empty|is_null|instanceof)\b|\?\?|\?->|#\[Override\]"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Error suppression, dangerous eval, and loose equality.
        # (?<![=!]) on the == branch: without it, `===`/`!==` (strict
        # equality/inequality, explicitly SAFE per this language's own
        # `safety` rule above) both still matched via their trailing `==`
        # substring at a shifted offset -- same bug found in javascript.
        # BUG FIX: the `@` error-suppression check required the next
        # char to be a letter/underscore, matching `@someFunc()` but
        # missing PHP's extremely common `@$array['key']`/`@$var`
        # suppression idiom (silencing "undefined index" notices).
        # Widened to also allow `$` immediately after `@`.
        "safety_bypasses": re.compile(
            r"@(?:[a-zA-Z_\x80-\xff]|\$)|\b(unserialize|extract|parse_str|phpinfo)\b|error_reporting\s*\(\s*0\s*\)|(?<![=!])==(?!=)|!=(?!=)"
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Shell execution and process killers. EXCLUDES prints (Phase 5).
        "high_risk_execution": re.compile(r"\b(exec|shell_exec|system|passthru|proc_open|popen)\b|`[^`]+`"),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(fopen|fread|fwrite|file_get_contents|file_put_contents|PDO|mysqli|curl_exec|socket|header|setcookie)\b|\$_(?:GET|POST|FILES|REQUEST|COOKIE)"
        ),
        # 10. api (Public Surface Area)
        # Exposed surface. Explicit public markers + attribute routes.
        "api": re.compile(r"\b(public)\b|#\[(?:ApiResource|Route|Get|Post|Put|Delete|Patch)[^\]]*\]"),
        # 11. flux (State Mutation)
        # Mutation of state. Variable reassignments and array mutators.
        # QUADRATIC BLOWUP FIX: the optional `(?:\w+)?` before the
        # required-but-often-absent `->`/`::` was unbounded with no
        # preceding \b anchor -- O(n^2) on a long run of word characters
        # with neither token present. Bounded to {1,100}.
        "state_mutation": re.compile(
            r"\$[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*\s*(?:[-+*./%&|])?=|&\$|\bglobal\s+\$|(?:\w{1,100})?(?:->|::)[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*[ \t]*=|array_(?:push|pop|shift|unshift|splice)\b|(?:\+\+|--)"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # BUG FIX: the `function|class|namespace|use|if|foreach`
        # keyword check only ran after `/*` (the rare block-comment
        # form) -- a commented-out declaration using `//` (PHP's
        # standard, far more common single-line comment style, e.g.
        # `// function foo() {}`) never matched at all. Applied the
        # same keyword check to both comment styles.
        "dead_code": re.compile(
            r"//\s*[;{}]|(?://|/\*)\s*(?:function|class|namespace|use|if|foreach)\b"
            r"|#\s*\$|//\s*(?:echo|print|\$|return|var_dump)"
        ),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"/\*\*|@param|@return|@throws|@var|@deprecated|@property|@method"),
        # 14. test (Testing & Assertions)
        "test": re.compile(
            r"\b(PHPUnit|TestCase|assertSame|assertEquals|assertTrue|assertFalse|mock|spy|expects|toBe|test|it)\b|#\[Test\]"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # BUG FIX: `go\(` ends on `(` (non-word), so the shared
        # trailing \b only fired when a word char immediately followed
        # the paren -- never true for the zero-argument form (`go();`).
        "concurrency": re.compile(
            r"\b(?:Fiber|yield|Swoole|React\\|Amp\\|Coroutine|await|suspend|resume|pcntl_fork)\b|\bgo\("
        ),
        # 16. ui_framework (UI / View Components)
        # BUG FIX: `view\s*\(`/`render\s*\(` both end on `(` (non-word),
        # so the shared trailing \b only fired when a word char
        # immediately followed the paren -- never true for the common
        # real call shape `view("index")`, where a quote follows.
        "ui_framework": re.compile(
            r"\b(?:renderView|extends\s+Controller|Blade::|Twig\\Environment)\b"
            r"|\bview\s*\(|\brender\s*\("
            r'|@(?:if|foreach|yield|section|extends)\b|<\?=|echo\s+[\'"]<|\{\{[^}]*\}\}|\{%\s*[^%]*\s*%\}'
        ),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(r"\b(?:function\s*\([^)]*\)\s*(?:use\s*\([^)]*\)\s*)?\{|fn\s*\([^)]*\)[ \t]*=>)"),
        # 18. globals (Global / Shared State)
        # BUG FIX: the leading \b before `$_SERVER`/`$_SESSION`/
        # `$_ENV`/`$GLOBALS` requires a word char immediately before
        # the `$` -- never true in real PHP, where a superglobal is
        # always preceded by whitespace, `=`, `(`, or a line start
        # (all non-word). All 4 of PHP's most common superglobal
        # accesses never matched at all. `$` is unambiguous as a
        # start anchor on its own; no leading \b was needed.
        "globals": re.compile(r"(?:\$_SERVER|\$_SESSION|\$_ENV|\$GLOBALS)\b|\bglobal\s+\$", re.I),
        # 19. decorators (Decorators / Annotations)
        # BUG FIX (ReDoS): `[a-zA-Z0-9_:\\]+` and `[^\]]*` are two
        # adjacent unbounded quantifiers matching an overlapping
        # character set (both match plain letters/digits) -- against
        # an adversarial attribute name with no closing `]`, every
        # possible split between the two quantifiers gets tried
        # before failing. Confirmed genuine O(n^2) scaling (0.045s/
        # 0.18s/0.71s/2.85s for n=10k/20k/40k/80k, ~4x per doubling).
        # Bounded both to reasonable caps.
        "decorators": re.compile(r"#\[\s*[a-zA-Z0-9_:\\]{1,100}[^\]]{0,300}\]", re.M),
        # 20. generics (Generics / Type Parameters)
        # Simulated/Docblock generics.
        "generics": re.compile(
            r"@(?:template|implements|extends|use)\s+[a-zA-Z0-9_\\]+(?:<[^>]*>)?|\b(?:array|iterable|Collection)<[^>]*>"
        ),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(
            r"\b(array_map|array_filter|array_reduce|array_walk|array_column|array_find|array_any|array_all)\b"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(bcadd|bcsub|bcmul|bcdiv|gmp_add|gmp_mul|abs|cos|sin|tan|sqrt|log|exp|pow)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Magic methods, reflection, and variable variables.
        "reflection_metaprogramming": re.compile(
            r"\b(__(?:get|set|call|callStatic|invoke|destruct|clone)|Reflection(?:Class|Method|Property)|call_user_func(?:_array)?)\b|\$\$[a-zA-Z_\x80-\xff]"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(
            r"\b(?:use\s+(?:function|const[ \t]+)?[\w\\]+|require|include|require_once|include_once)\b",
            re.M,
        ),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (PHP) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
            #
            # HISTORICAL BUG: Originally, this regex was anchored to the start of the
            # line `^[ \t]*`. This blinded the firewall to PHP's dynamic execution
            # patterns. PHP applications (especially legacy frameworks) frequently
            # lazy-load files inside controllers, `if` statements, or assign the result
            # of a file inclusion directly to a variable (e.g., `$config = require 'cfg.php';`).
            #
            # THE FIX: The `^` anchor has been stripped. We now rely on the `\b` word
            # boundary to find the inclusion keywords anywhere in the file.
            #
            # [ THE ASSIGNMENT SHIELD SIMPLIFICATION ]
            # Because the regex is no longer anchored to the start of the line, we were
            # able to completely delete the bloated, ReDoS-prone assignment capture group
            # `(?:\$[a-zA-Z_]...=)?`. The engine now effortlessly ignores the `$var = `
            # portion and skips straight to the `require` boundary.
            #
            # [ THE PARENTHESIS SHIELD ]
            # PHP allows `require 'file.php'` and `require('file.php')`. The `\(?` safely
            # bridges both syntaxes while capturing the target path.
            # =====================================================================
            r"\b(?:use[ \t\n]+(?:function[ \t\n]+|const[ \t\n]+)?([a-zA-Z0-9_\\]+(?:[ \t\n]*(?:as[ \t\n]+|[,{])[a-zA-Z0-9_\\ \t\n{},]+?)?)[ \t\n]*;|(?:require|require_once|include|include_once)[ \t\n]*\(?[ \t\n]*(?:['\"]([^'\"]+)['\"]|([^;]+?)[ \t\n]*(?=\)?\s*;)))",
            re.M | re.I,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"@(?:author|copyright)\s+(.*)|(?:Created by|Maintainer):?\s+(.*)", re.I),
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
            r"\b(Response|JsonResponse|HtmlResponse|RedirectResponse|Symfony\\Component\\HttpFoundation|Illuminate\\Http\\Response)\b"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(r"\b(EventDispatcher|dispatchEvent|Listener|dispatch|broadcast|notify|Event::|listen)\b"),
        # 33. dependency_injection (Dependency Injection / IoC)
        # BUG FIX: `app\(`/`make\(` both end on `(` (non-word), so the
        # shared trailing \b only fired when a word char immediately
        # followed the paren -- never true for the zero-argument form
        # (`app();`/`make();`).
        "dependency_injection": re.compile(
            r"\b(?:ContainerInterface|Container|getContainer|inject|bind|singleton)\b"
            r"|\bapp\(|\bmake\(|#\[(?:Inject|Autowire)[^\]]*\]"
        ),
        # 34. macros (Preprocessor Directives / Macros)
        # BUG FIX: `macro\s*\(`/`mixin\s*\(` both end on `(` -- the
        # shared trailing \b only fired when a word char immediately
        # followed the paren, e.g. `mixin(new Foo())` worked (`new`
        # follows) but `macro("foo", ...)` didn't (a quote follows).
        "macros": re.compile(r"\bMacroable\b|\bmacro\s*\(|\bmixin\s*\("),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": re.compile(r"\b(FFI::cast|FFI::addr|FFI::scope|FFI::new)\b"),
        # 36. memory_alloc
        "memory_alloc": re.compile(r"\bnew\s+[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*"),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        # BUG FIX: `logger\(` ends on `(` (non-word), so the shared
        # trailing \b only fired when a word char immediately followed
        # the paren -- never true for the idiomatic Laravel chain form
        # `logger()->info('message')`, where `)` follows.
        "telemetry": re.compile(
            r"(?:\b(?:Log::|LoggerInterface|Monolog\\|error_log|Psr\\Log)\b|logger\()"
            r".*?(?:info|error|warning|debug|trace|notice|critical|alert|emergency)\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(echo|print|var_dump|print_r|printf|vprintf|var_export|die|exit|dd|dump)\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            r"\((?:int|integer|bool|boolean|float|double|string|array|object|unset)\)\s*|\bsettype\s*\("
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(throw|die|exit|abort)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(sleep|usleep|time_nanosleep|time_sleep_until)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(mutex|lock|synchronized|Semaphore|flock|sem_acquire)\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(const|readonly|final)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(unset|fclose|mysql_close|mysqli_close|PDO::null|dispose|cleanup)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        "encapsulation": re.compile(r"\b(private|protected|internal)\b"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\.on\(|addEventListener|subscribe|@KafkaListener|@RabbitListener"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # BUG FIX: `mock\(`/`fake\(` both end on `(` (non-word), so the
        # shared trailing \b only fired when a word char immediately
        # followed the paren -- never true for the zero-argument form
        # (`mock();`).
        "test_skip": re.compile(r"\b(?:markTestSkipped|test\.skip|it\.skip)\b|\bmock\(|\bfake\("),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (PHP Specifics) ---
        "serialization_parsing": re.compile(
            r"\b(unserialize|serialize|json_decode|json_encode|simplexml_load_(?:string|file)|DOMDocument)\b"
        ),
        "regex_execution": re.compile(r"\b(preg_match(?:_all)?|preg_replace(?:_callback)?|preg_split|preg_filter)\b"),
        # BUG FIX: `time\s*\(`/`date\s*\(` both end on `(` (non-word),
        # so the shared trailing \b only fired when a word char
        # immediately followed the paren -- never true for the
        # zero-argument form (`time()`) or a quoted format string
        # (`date("Y-m-d")`).
        "time_date_logic": re.compile(r"\b(?:strtotime|DateTime(?:Immutable)?|date_create)\b|\btime\s*\(|\bdate\s*\("),
        "ipc_rpc_bridges": re.compile(r"\b(shell_exec|exec|system|passthru|proc_open|curl_exec|fsockopen)\b"),
    },
}
