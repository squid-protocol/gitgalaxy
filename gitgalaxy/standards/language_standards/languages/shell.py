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
        "target_version": "Bash 5.2 / Zsh 5.9 / Modern DevOps Scripts",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    "extensions": [
        ".sh",
        ".bash",
        ".zsh",
        ".ksh",
        ".dash",
        ".command",
        ".csh",
        ".tcsh",
        ".fish",
        ".bats",
    ],
    # Thorough Exact Match List: Captures hidden configuration and profile scripts.
    "exact_matches": [
        ".bashrc",
        ".zshrc",
        ".profile",
        ".bash_profile",
        ".bash_logout",
        ".inputrc",
        "bash_completion",
        "PKGBUILD",
    ],
    # Thorough Shebang mapping: Essential for identifying extensionless scripts.
    "shebangs": ["bash", "sh", "zsh", "ksh", "dash", "ash", "rbash"],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: Relies strictly on '#' for line-level Commented / Non-Executable Text; no native block delimiters.
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logic jumps. Includes test constructs [[ ]] and [ ].
        # CRITICAL: Excluded bare '((' and '))' to prevent ReDoS on massive subshell nesting.
        "branch": re.compile(
            r"\b(if|then|else|elif|fi|case|esac|for|while|do|done|until|select|break|continue)\b|&&|\|\||\[\[|\]\]|(?:^|(?<=\s|;|\||&))\[(?=\s)|(?<=\s)\](?=\s|;|\||&|$)"
        ),
        # 2. args (Parameters / Coupling)
        # Positional parameters and expansion markers.
        # BUG FIX (epic #813/#835): the braced form only matched a bare
        # `${1}`/`${10}` -- it had no allowance for the extremely common
        # bash default-value/error-message expansion operators (`:-`,
        # `:=`, `:?`, `:+`), so `${1:-default}` (arguably the single most
        # common way positional params actually appear in real scripts)
        # was entirely invisible to this rule. Added an optional
        # `:[-=?+]...` suffix using the same one-level-nesting-safe idiom
        # already established elsewhere in this file's `safety` rule
        # (`(?:[^{}]|\{[^{}]*\})*`), so a nested default like
        # `${1:-${DEFAULT:-x}}` is captured in full instead of truncating
        # at the inner `}`. Confirmed linear-time (no ReDoS) up to a
        # 200k-char adversarial input before landing.
        # #1518: whole rule wrapped in one outer capture group so
        # detector.py's counter can name it in `_args_findall_max_groups`
        # below -- bash has no formal parameter list at all (a function's
        # own `()` are always empty, permanently, by grammar), so a
        # single match only ever sees the FIRST positional-parameter
        # reference in the block and silently drops every one after it
        # (`readlink "$1"` ... later `"$2"` measured got=1, not 2). This
        # tells the shared counter to re-scan the WHOLE block and take
        # the highest $N seen instead of trusting the first hit.
        "args": re.compile(r'(\$(?:[1-9]|\{#?[1-9][0-9]*(?:[:#%^,/~-](?:[^{}]|\{[^{}]*\})*)?\}|@|\*|#)|"\$@"|"\$\*")'),
        "_args_findall_max_groups": {1},
        # 3. linear (Sequential Boundaries)
        # Structural boundaries and straight-line execution verbs.
        # BOUNDARY FIX: `.` (the dot-source operator) is a non-word char, so it
        # can never satisfy a shared leading `\b` -- the same trap documented on
        # `_dependency_capture` below. Pulled out into its own statement-boundary
        # anchored alternative instead of sitting inside the `\b(...)\b` group.
        "structural_boundaries": re.compile(
            r"\b(local|readonly|export|declare|typeset|return|exit|source|read|cd|pwd|ls|cp|mv|rm|mkdir|touch)\b|(?<!\|)\|(?!\s*\|)|(?:^|[ \t;|&])\.(?=[ \t])",
            re.M,
        ),
        # Anchors executable logic blocks. Captures `function foo` or `foo()`.
        # Handled by Mode D (Semantic Handshake) in detector.py.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL FUNCTION SHIELD (SHELL) ]
            # Bash/Zsh allow extreme spacing and newlines between the `function`
            # keyword and the identifier name.
            # FIX: Upgraded horizontal spaces `[ \t]+` to `[ \t\n]+` for the
            # `function` keyword path, allowing it to easily consume weird formatting.
            #
            # BUG FIX (epic #813/#835): the POSIX `name()` branch's keyword
            # exclusion only listed 5 of bash's ~17 word-based reserved words
            # (if/while/for/case/until) -- `done() {`, `elif() {`, `select() {`,
            # `function() {`, etc. all falsely matched as function definitions.
            # None of these are ever valid bash (a reserved word can't be used
            # as a POSIX function name -- the real parser errors on it), but
            # this is a regex-only engine scanning arbitrary/malformed text, so
            # the same defensive intent that motivated the original 5-word list
            # applies equally to the rest. Widened to the full reserved-word set.
            # =====================================================================
            r"^[ \t]*(?:function[ \t\n]+([a-zA-Z_][a-zA-Z0-9_.:-]*)|"
            r"(?!(?:if|then|elif|else|fi|case|esac|while|until|for|in|do|done|function|select|time|coproc)\b)"
            r"([a-zA-Z_][a-zA-Z0-9_.:-]*)[ \t\n]*\(\))",
            re.M,
        ),
        # 5. class_start
        # Shell is strictly procedural.
        "class_start": None,
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Shell hardening: strict modes, traps, and robust quoting.
        # QUADRATIC BLOWUP + NESTING FIX: the trap clause's `[^\n]*` and both
        # `${...}` clauses' flat `[^}]+`/`[^}]*` were unbounded and unanchored --
        # O(n^2) on a long run of unclosed traps/expansions (confirmed ~4x
        # slowdown per input-size doubling). The trap clause is bounded to
        # {0,300}; the `${...}` clauses use the one-level-nesting form so a
        # realistic nested default like `${LOG_LEVEL:-${DEFAULT:-info}}` is
        # captured in full instead of truncating at the inner `}`.
        "safety": re.compile(
            r'\b(set\s+-(?:[a-zA-Z]*e[a-zA-Z]*|u|o\s+pipefail)|trap\s+[^\n]{0,300}(?:ERR|EXIT|INT|TERM))\b|"\$[@*]"|"\$\{(?:[^{}]|\{[^{}]*\})+\}"|\bcommand\s+-v\b|\$\{[a-zA-Z0-9_]+:[-=?](?:[^{}]|\{[^{}]*\})*\}'
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Unquoted variables, dynamic evaluation, and blind network-to-shell piping.
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Unquoted variables, dynamic evaluation, and blind network-to-shell piping.
        "safety_bypasses": re.compile(
            r'\b(eval)\b(?!\s*\()|(?<!")\$(?![\(?])\w+(?!")|\|\|\s*true\b|>\s*/dev/null(?:\s*2>&1)?|\bcurl\s+[^|\n]{1,200}\|[ \t]*(?:bash|sh|zsh)\b'
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Destructive commands and privilege elevation. EXCLUDES echo (Phase 5).
        "high_risk_execution": re.compile(
            r"\b(rm\s+-[rR]f|sudo|chmod\s+(?:-R[ \t]+)?777|chown\s+(?:-R[ \t]+)?root|mkfs|dd|kill(?:all)?)\b"
        ),
        # 9. io (I/O & Network Boundaries)
        # Redirections, pipes, and network clients.
        "io": re.compile(r">|>>|<|\|(?:&)?|\b(curl|wget|nc|ssh|scp|ftp|rsync|cat|tail|grep|find|xargs|jq)\b"),
        # 10. api (Public Surface Area)
        # Exported variables and identifiers modifying the global environment.
        "api": re.compile(r"^[ \t]*export\s+[a-zA-Z_]\w*", re.M),
        # 11. flux (State Mutation)
        # Mutation of state via assignment or arithmetic.
        # QUADRATIC BLOWUP FIX: the arithmetic-expansion branch's two
        # `[^)]*` quantifiers were unbounded -- on a long run of unclosed
        # `(` characters, each opening pair is a candidate match start
        # scanning to the end looking for the required operator + `))`,
        # for O(n^2) total. Bounded to {0,200} each; real `(( ... ))`
        # arithmetic expressions don't get remotely that long.
        "state_mutation": re.compile(
            r"^[ \t]*[a-zA-Z_]\w*(?:\[[^\]]+\])?\+?=(?![=~])|\b(?:let|declare)\s+[a-zA-Z_]\w*\+?=|\(\([^)]{0,200}(?:\+\+|--|[-+*/%]=)[^)]{0,200}\)\)",
            re.M,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented-out execution logic indicating dead features.
        "dead_code": re.compile(r"#[ \t]*(?:if|for|while|function|export|echo|printf|cd|rm|sudo|ls)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(
            r"^[ \t]*#\s*(?:@param|@return|Usage:|Description:|Examples:|Options:)|#\s*shellcheck\s+disable",
            re.M | re.I,
        ),
        # 14. test (Testing & Assertions)
        # Triggers indicating internal verification. Anchored to shell-specific testing framework commands.
        "test": re.compile(
            r"\b(assert_?eq|assertTrue|assertFalse|assert_?match|bats|shunit2)\b|^@test\s+|\brun\s+[a-zA-Z0-9_-]+",
            re.M,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # QUADRATIC BLOWUP + NESTING FIX: the process-substitution clauses'
        # flat `[^)]*` were unbounded and unanchored -- O(n^2) on a long run
        # of unclosed `<(`/`>(` (confirmed ~4x slowdown per input-size
        # doubling). Upgraded to the one-level-nesting form so a realistic
        # nested process substitution (e.g. `diff <(sort <(cat a)) <(sort b)`)
        # is captured in full instead of truncating at the inner `)`.
        "concurrency": re.compile(
            r"&[ \t]*$|\b(wait(?:\s+-n)?|coproc|nohup|parallel|jobs|fg|bg|disown|xargs\s+-P)\b|&\s*\|\||<\((?:[^()]|\([^()]*\))*\)|>\((?:[^()]|\([^()]*\))*\)",
            re.M,
        ),
        # 16. ui_framework (UI / View Components)
        # Terminal UI builders and ANSI sequences.
        "ui_framework": re.compile(
            r"\b(dialog|whiptail|zenity|kdialog|notify-send|tput|gum|tmux)\b|\\033\[[0-9;]+m|\\e\[[0-9;]+m"
        ),
        # 17. closures
        "closures": None,  # Shell lacks native anonymous lambdas.
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            r"\b(PATH|HOME|USER|SHELL|EDITOR|PWD|OLDPWD|TERM|LANG|OSTYPE|MACHTYPE|UID|EUID|GROUPS)\b"
        ),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions (Iterators / Comprehensions)
        # Brace expansions acting as inline loops.
        "comprehensions": re.compile(r"\{[0-9]+(?:\.\.|,)[0-9]+(?:\.\.[0-9]+)?\}|\{[a-zA-Z]\.\.[a-zA-Z]\}"),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(bc|awk|dc|expr|jq|RANDOM|SRANDOM)\b|\$\(\("),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Sub-languages and indirect expansion. (ReDoS Shielded)
        # QUADRATIC BLOWUP + NESTING FIX: `$(...)`'s flat `[^)]+` was
        # unbounded and unanchored -- O(n^2) on a long run of unclosed
        # `$(` (confirmed ~4x slowdown per input-size doubling). Upgraded
        # to the one-level-nesting form so the common nested command
        # substitution idiom (e.g. `DIR=$(cd "$(dirname "$0")" && pwd)`)
        # is captured in full instead of truncating at the inner `)`.
        "reflection_metaprogramming": re.compile(
            r'\$\((?:[^()]|\([^()]*\))+\)|`[^`]+`|\b(?:awk|sed|perl|python[23]?|ruby)\s+[\'"][^\'"]{0,500}|\beval\s+\$|\$\{!?[a-zA-Z0-9_]+\}'
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"(?:^|[ \t;|&])(?:source\b|\.(?=[ \t]))[ \t]+[^\s;]+", re.M),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (SHELL) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
            #
            # HISTORICAL BUG: Originally, this regex was anchored to the start of the
            # line `^[ \t]*`. This blinded the firewall to dynamic or conditional shell
            # execution. Shell scripts frequently source environment files inside `if`
            # blocks (e.g., `if [ -f .env ]; then source .env; fi`) or after logical
            # operators (e.g., `test -f lib.sh && . lib.sh`). The anchored regex missed
            # these entirely.
            #
            # THE FIX: The `^` anchor has been replaced with a Shell Statement Boundary:
            # `(?:^|[ \t;|&])`. This allows the engine to recognize a `source` or `.`
            # command immediately following a pipe `|`, a background task `&`, a logic
            # gate `&&`, a command separator `;`, or standard whitespace, without
            # triggering false positives on prose in echo statements.
            #
            # [ THE DOT-OPERATOR WORD BOUNDARY TRAP ]
            # We CANNOT use a standard `\b` word boundary for the entire group because
            # the dot operator (`.`) is a non-word character. `\b\.` will fail.
            # Therefore, we explicitly branch: `source` gets a word boundary `\b`,
            # and `.` gets a positive lookahead for whitespace `(?=[ \t])`.
            # =====================================================================
            r"(?:^|[ \t;|&])(?:source\b|\.(?=[ \t]))[ \t]+['\"]?([^'\"\s;]+)['\"]?",
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"^[ \t]*#\s*(?:Author|Created by|Maintainer|Copyright):?\s+(.*)",
            re.M | re.I,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # QUADRATIC BLOWUP FIX: the trailing `[^\]]*` was unbounded and
        # unanchored -- O(n^2) on a long run of unclosed `#[SPEC-...` tags
        # (confirmed ~4x slowdown per input-size doubling). Bounded to
        # {0,300}; real spec/audit tags don't get remotely that long.
        "spec_exposure": re.compile(r"#\s*\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        # Legacy CGI shell environments.
        "ssr_boundaries": re.compile(
            r'\b(?:CONTENT_TYPE|QUERY_STRING|HTTP_USER_AGENT)\b|echo\s+"Content-type:\s*text/(?:html|plain|json)'
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # Named pipes and OS signal handlers.
        "events": re.compile(
            r"\b(mkfifo|mknod|inotifywait|inotifywatch|fswatch|tail\s+-f|kill\s+-(?:SIG)?(?:USR1|USR2|HUP|TERM))\b"
        ),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(r"\$\{1:-\w+\}|\$\{2:-\w+\}|\b(?:command\s+-v|type\s+-p)\b"),
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(r"^[ \t]*(?:alias|shopt)\b", re.M),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Raw memory addressing. Shell uses namerefs and indirect expansion.
        "pointers": re.compile(r"\b(?:declare\s+-n|typeset\s+-n)\b|\$\{\!"),
        # 36. memory_alloc
        "memory_alloc": None,
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(?:logger|syslog|log_info|log_err|log_warn|log_debug)\b|>\s*/dev/(?:stderr|console)"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(echo|printf|print|read)\b"),
        # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": None,
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(exit|kill|abort|halt|return\s+[1-9][0-9]*)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(sleep|read\s+-t)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": None,
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(flock|mkdir|mkfifo|lockfile|sem)\b"),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(readonly|declare\s+-r|typeset\s+-r)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        # QUADRATIC BLOWUP FIX: same class of bug as `safety`'s trap clause
        # above -- the unbounded `.*` before the required `EXIT` literal was
        # unanchored, O(n^2) on a long run of `trap ` occurrences that never
        # resolve to EXIT (confirmed ~4x slowdown per input-size doubling).
        # Bounded to {0,300}, matching the fix already applied to `safety`.
        "cleanup": re.compile(r"\b(rm\s+-f|trap\s+.{0,300}EXIT|unset|exit|logout)\b"),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Physical Reality: local variables represent internal state scope.
        "encapsulation": re.compile(r"\b(local|typeset|declare)\b"),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(read|inotifywait|nc\s+-l|while\s+read)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # BOUNDARY FIX: `#\s*SKIP` starts with `#` (non-word), so it could
        # never satisfy the shared leading `\b` -- real comment markers are
        # always preceded by whitespace or line start (also non-word), so a
        # `# SKIP: ...` comment never matched at all. Pulled out of the
        # group with the leading `\b` dropped (the `#` is self-delimiting).
        "test_skip": re.compile(r"\b(test\.skip|bats_skip|mock|stub)\b|#\s*SKIP\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Shell Specifics) ---
        "serialization_parsing": re.compile(r"\b(jq|yq|awk|sed|xmlstarlet)\b"),
        "regex_execution": re.compile(r"\b(grep|egrep|sed|awk)\b|=~"),
        # BOUNDARY FIX: the trailing `\s+` before the shared closing `\b`
        # required a word char to immediately follow the whitespace --
        # never true for how `date`/`sleep` are actually invoked (almost
        # always followed by a `-flag` or `+FORMAT`, both non-word). The
        # single most common real-world form of `date` (`date +%Y-%m-%d`)
        # never matched at all. The `\s+` was redundant anyway -- `\b`
        # alone already prevents partial-word matches like "update".
        "time_date_logic": re.compile(r"\b(date|sleep|uptime|times)\b"),
        "ipc_rpc_bridges": re.compile(r"\b(curl|wget|nc|netcat|ssh|scp|xargs|socat)\b"),
    },
}
