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
        "target_version": "R5RS / R6RS / Guile (GnuPG gpgscm)",
        "last_updated": "2026-03-11",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard Scheme, legacy PLT/Chez suffixes, and Racket sources.
    "extensions": [".scm", ".ss", ".rkt", ".sch", ".sld", ".sls", ".sps"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Scheme rarely uses extensionless configurations.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Guile build definitions, Racket manifests, and Lisp package formats.
    "discriminators": [".scm", ".rkt", "info.rkt", "guix.scm"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for shell wrappers invoking Scheme/Guile/Racket.
    "shebangs": ["guile", "scheme", "csi", "racket", "racketsh"],
    # BUG FIX (#770): this comment always described a genuine nested
    # block-comment family ("Perfectly captures the Lisp ecosystem's
    # reliance on ';' for line-level comments and `#| |#` for nested
    # block-level Commented / Non-Executable Text"), but the field itself
    # was left at "line_exclusive" -- which has NO cross-line state at
    # all (per how_to_add_a_language.md: "no native multi-line block
    # syntax; the engine ignores closing tags"), the literal opposite of
    # what this comment claims. Confirmed empirically: a real multi-line
    # `#| ... |#` block only had its first line recognized as a comment;
    # every subsequent line up to and including the closing `|#` leaked
    # into code_stream as live code. Fixed by actually creating the
    # dedicated family (recursive_block_lisp), reusing the same
    # iterative-peel algorithm recursive_block_haskell already uses for
    # {- -}, just with Scheme's own ; / #| / |# tokens.
    "lexical_family": "recursive_block_lisp",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Lisp control flow branches. Uses custom S-expression boundaries.
        "branch": re.compile(r"(?<![^ \t\n\r(\[])(if|cond|case|and|or|when|unless)(?![^ \t)\]\n\r])"),
        # 2. args (Parameters / Coupling)
        # Captures the parameter list inside a standard function definition: (define (func arg1 arg2) ...)
        "args": re.compile(
            # =====================================================================
            # [ THE S-EXPRESSION ARGS SHIELD (SCHEME) ]
            # Scheme arguments are inside the same parenthesis as the function name.
            # FIX 1 (Pathological): Upgraded horizontal spaces to `[ \t\n]*` for vertical layouts.
            # FIX 2 (Positive): The previous regex strictly required a space and arguments.
            # Made the argument capture group `(?:[ \t\n]+[^)]*)?` optional so
            # parameter-less functions like `(define (func))` cleanly pass.
            # =====================================================================
            # #1209: name and parameter-list span split into their own
            # capture groups (was only reachable via group(0), the whole
            # "(define (name arg1 arg2)" match including the "(define"
            # prefix and function name) so detector.py's counter isolates
            # just the space-separated parameter text -- the whole-match
            # fallback whitespace-split "(define" and the name as
            # spurious extra args on top of the real ones (the same
            # overcount shape #1199 fixed for Python, just off by 2 here
            # instead of 1 since Scheme has two prefix tokens, not one).
            # REDOS FIX (found verifying #1209, pre-existing -- not
            # introduced by the groups above): the name class
            # `[^ \t\n()]+` and the trailing `[^)]*` are adjacent
            # unbounded quantifiers over near-identical character
            # classes (the second is a superset of the first), so an
            # unterminated `(define (xxxx...` with no closing `)`
            # anywhere made the engine give back the name one char at a
            # time and re-scan the whole remaining run as the args span
            # at each step -- O(n^2) confirmed via scaling sweep (247x
            # time for 16x input). Bounding the name to a realistic
            # identifier length caps the number of give-back steps to a
            # constant, restoring linear behavior.
            r"^[ \t\n]*\([ \t\n]*define[ \t\n]+\([ \t\n]*([^ \t\n()]{1,100})([^)]*)\)",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries defining scope and sequential execution.
        "structural_boundaries": re.compile(r"(?<![^ \t\n\r(\[])(let|let\*|letrec|letrec\*|begin|do)(?![^ \t)\]\n\r])"),
        # 4. func_start (Executable Logic Anchors)
        # Anchors logic blocks. Captures the function name immediately following the parenthesis.
        # BUG FIX: the identifier capture class `[a-zA-Z0-9_!?-]+` excluded
        # `> < = * + / . ~ $ % ^ &` -- but real Scheme identifiers are
        # extremely permissive (R7RS special-initial/special-subsequent
        # chars), and the "X->Y" type-conversion naming convention
        # (`list->vector`, `string->number`, ...) is idiomatic in the
        # standard library itself. The truncated capture broke the
        # following lookahead entirely, so func_start silently failed to
        # match ANY such definition (`1+`, `foo*`, `list->vector`, etc.),
        # not just a partial-name capture. Widened to the realistic set.
        "func_start": re.compile(
            # =====================================================================
            # [ THE S-EXPRESSION SHIELD (SCHEME/LISP) ]
            # S-expressions format heavily around parentheses, often pushing the
            # `define`, the inner parenthesis `(`, and the identifier onto separate lines.
            # FIX: Replaced `\s+` and `\s*` with `[ \t\n]+` and `[ \t\n]*` inside
            # the S-expression structure to ensure the parser can track the
            # identifier no matter how deeply it is vertically nested.
            # =====================================================================
            r"^[ \t\n]*\([ \t\n]*define[ \t\n]+\([ \t\n]*([a-zA-Z0-9_!?*+/<>=.~$%^&:-]+)(?![^ \t\n)\]\r])",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Scheme lacks traditional objects; SRFI-9 Records serve as structural entities.
        # BUG FIX: same identifier-capture defect as func_start above --
        # missed the extremely common `<TypeName>` angle-bracket naming
        # convention for record types (SRFI-9/R6RS idiom, e.g. `<point>`).
        "class_start": re.compile(
            r"^[ \t\n]*\([ \t\n]*define-record-type[ \t\n]+(?:\([ \t\n]*)?([a-zA-Z0-9_!?*+/<>=.~$%^&:-]+)(?![^ \t\n)\]\r])",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Continuations, exception guards, and dynamic-wind state protectors.
        "safety": re.compile(
            r"(?<![^ \t\n\r(\[])(guard|dynamic-wind|with-exception-handler|call-with-current-continuation|call/cc|assert|check)(?![^ \t)\]\n\r])"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Explicit, raw manipulation of cons cells or unrestricted environments.
        "safety_bypasses": re.compile(
            r"(?<![^ \t\n\r(\[])(set-car!|set-cdr!|interaction-environment)(?![^ \t)\]\n\r])"
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Dynamic code execution and emergency system exits.
        "high_risk_execution": re.compile(r"(?<![^ \t\n\r(\[])(eval|exit|emergency-exit|quit)(?![^ \t)\]\n\r])"),
        # 9. io (I/O & Network Boundaries)
        # File operations and output ports.
        "io": re.compile(
            r"(?<![^ \t\n\r(\[])(open-input-file|open-output-file|read|read-char|write|display|newline|call-with-input-file|call-with-output-file|load|format)(?![^ \t)\]\n\r])"
        ),
        # 10. api (Public Surface Area)
        # Module exports defining the public surface.
        "api": re.compile(r"^[ \t]*\([ \t]*(?:export|define-public)(?![^ \t)\]\n\r])", re.M),
        # 11. flux (State Mutation)
        # Mutation of state. In Scheme, all mutating functions end with a bang (!).
        "state_mutation": re.compile(
            r"(?<![^ \t\n\r(\[])(set!|vector-set!|string-set!|hash-table-set!|bytevector-u8-set!)(?![^ \t)\]\n\r])"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented out S-expressions.
        "dead_code": re.compile(
            r"^[ \t]*;+[ \t]*\([ \t]*(?:define|let|if|cond|lambda)(?![^ \t)\]\n\r])",
            re.M,
        ),
        # 13. doc (Structured Documentation)
        # Scheme documentation standards (triple semicolons or texinfo).
        "doc": re.compile(r"^[ \t]*;;;|^[ \t]*;[ \t]*@(?:param|return|author)", re.M),
        # 14. test (Testing & Assertions)
        # SRFI-64 and Guile testing frameworks (essential for mapping gpgscm tests).
        "test": re.compile(
            r"(?<=\()(test-begin|test-end|test-assert|test-eqv|test-equal|test-eq|check-equal\?|check-true|test)(?![^ \t)\]\n\r])"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # SRFI-18 Multithreading primitives.
        "concurrency": re.compile(
            r"(?<![^ \t\n\r(\[])(make-thread|thread-start!|thread-yield!|mutex-lock!|mutex-unlock!|condition-variable-signal!)(?![^ \t)\]\n\r])"
        ),
        # 16. ui_framework
        "ui_framework": None,
        # 17. closures (Closures / Anonymous Functions)
        # Anonymous function depth.
        "closures": re.compile(r"(?<![^ \t\n\r(\[])lambda(?![^ \t)\]\n\r])"),
        # 18. globals (Global / Shared State)
        # Top-level state bindings (defines that are NOT functions).
        # BUG FIX: same identifier-class defect as func_start/class_start --
        # a top-level binding using the "X->Y" convention (e.g.
        # `default->value`) failed to match at all.
        "globals": re.compile(r"^[ \t]*\([ \t]*define\s+[a-zA-Z0-9_!?*+/<>=.~$%^&:-]+\s+[^(\s]", re.M),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions (Iterators / Comprehensions)
        # Functional list operations (SRFI-1).
        "comprehensions": re.compile(
            r"(?<![^ \t\n\r(\[])(map|for-each|filter|fold|reduce|fold-right|fold-left)(?![^ \t)\]\n\r])"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        # Scheme's native mathematical tower.
        "scientific": re.compile(
            r"(?<![^ \t\n\r(\[])(sin|cos|tan|asin|acos|atan|exp|log|sqrt|expt|abs|gcd|lcm|numerator|denominator|floor|ceiling|truncate|round|exact->inexact)(?![^ \t)\]\n\r])"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Metaprogramming and syntactic abstractions.
        "reflection_metaprogramming": re.compile(
            r"(?<![^ \t\n\r(\[])(define-macro|define-syntax|syntax-rules|syntax-case|let-syntax|letrec-syntax)(?![^ \t)\]\n\r])"
        ),
        # 24. import (Dependency Inclusions)
        # Scheme module resolution dependencies.
        "import": re.compile(r"^[ \t]*\([ \t]*(?:import|use-modules|require)(?![^ \t)\]\n\r])", re.M),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"^[ \t]*;+\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)",
            re.I | re.M,
        ),
        # --- 🌌 PHASE 4: EXTENDED DIMENSIONS (Specialized Sub-Equations) ---
        # 26. planned_debt
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure
        # BUG FIX: adjacent unbounded quantifiers with overlapping character
        # sets (`\d+` immediately followed by `[^\]]*`, which also matches
        # digits) -- the same ReDoS shape already found and fixed
        # independently in embedded_python, css, tcl, and matlab earlier in
        # this epic. Confirmed via scaling sweep (~4x per doubling before,
        # ~linear after bounding both quantifiers).
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Hook paradigms common in Guile/Emacs environments.
        "events": re.compile(r"(?<![^ \t\n\r(\[])(hook|add-hook!|run-hooks)(?![^ \t)\]\n\r])"),
        # 33. dependency_injection
        "dependency_injection": None,
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(
            r"(?<![^ \t\n\r(\[])(define-syntax|define-macro|syntax-rules|syntax-case)(?![^ \t)\]\n\r])"
        ),
        # 35. pointers
        "pointers": None,
        # 36. memory_alloc
        # Explicit heap instantiations.
        "memory_alloc": re.compile(
            r"(?<![^ \t\n\r(\[])(make-vector|make-string|make-bytevector|make-hash-table|cons|list)(?![^ \t)\]\n\r])"
        ),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(r"(?<![^ \t\n\r(\[])(log-info|log-error|log-warn|log-debug|syslog)(?![^ \t)\]\n\r])"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"(?<![^ \t\n\r(\[])(display|write|newline|format\s+#t)(?![^ \t)\]\n\r])"),
        # # 40. explicit_casts (Explicit Type Casting)
        # Type coercions crossing memory boundaries.
        "explicit_casts": re.compile(
            r"(?<![^ \t\n\r(\[])(number->string|string->number|symbol->string|string->symbol|list->vector|vector->list|char->integer|integer->char)(?![^ \t)\]\n\r])"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"(?<![^ \t\n\r(\[])(error|abort|exit|emergency-exit)(?![^ \t)\]\n\r])"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"(?<![^ \t\n\r(\[])(sleep|usleep|thread-sleep!)(?![^ \t)\]\n\r])"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(
            r"(?<![^ \t\n\r(\[])(bitwise-and|bitwise-ior|bitwise-xor|bitwise-not|arithmetic-shift|ash)(?![^ \t)\]\n\r])"
        ),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"(?<![^ \t\n\r(\[])(mutex-lock!|make-mutex)(?![^ \t)\]\n\r])"),
        # 45. immutability_locks (Immutability Constraints)
        # Immutable strings and explicit quotations (meaning the list cannot be mutated safely).
        "immutability_locks": re.compile(
            r"(?<![^ \t\n\r(\[])(quote|string->immutable-string)(?![^ \t)\]\n\r])|\'(?=\()"
        ),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"(?<![^ \t\n\r(\[])(close-input-port|close-output-port|close-port)(?![^ \t)\]\n\r])"),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Module-internal definitions.
        "encapsulation": re.compile(r"^[ \t]*\([ \t]*define-private(?![^ \t)\]\n\r])", re.M),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"(?<![^ \t\n\r(\[])(add-hook!)(?![^ \t)\]\n\r])"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"(?<![^ \t\n\r(\[])(test-skip|test-expect-fail)(?![^ \t)\]\n\r])"),
    },
}
