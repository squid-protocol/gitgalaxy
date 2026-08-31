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
        "target_version": "Fortran 2018 (Backwards compatible with Legacy Fortran 77)",
        "last_updated": "2026-03-01",
        "blueprint_version": "v7.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard fixed-format, free-format, legacy dialects, and preprocessor files.
    "extensions": [
        ".f",
        ".f90",
        ".f77",
        ".for",
        ".fpp",
        ".f95",
        ".f03",
        ".f08",
        ".f18",
        ".ftn",
        ".inc",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Fortran rarely uses extensionless configurations.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests (fpm), and build files to resolve ambiguous files like .inc.
    "discriminators": [
        ".f90",
        ".f77",
        ".f",
        "fpm.toml",
        "CMakeLists.txt",
        "Makefile",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for modern Fortran "scripting" wrappers.
    "shebangs": ["fortran", "f90", "f77", "gfortran"],
    # UPGRADED: Maps to Family 7 (The Positional Ancients)
    # Rationale: Fixed-format requires Column 1 monitoring ('C' or '*'); Free-format uses '!'.
    "lexical_family": "positional_anchored",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Control flow that forces the CPU to make a decision or jump. High density creates jagged shapes.
        # Includes standard conditional blocks, legacy computed GO TO, and modern SELECT TYPE / SELECT RANK.
        "branch": re.compile(
            r"\b(IF|ELSEIF|ELSE|DO|WHILE|SELECT\s+CASE|CASE|DEFAULT|WHERE|ELSEWHERE|GO\s*TO|GOTO|SELECT\s+TYPE|SELECT\s+RANK|EXIT|CYCLE)\b|\.AND\.|\.OR\.",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Signatures defining input parameters. Drives the physical size/mass of the function.
        # Upgraded to capture both the declaration block and explicit INTENT binding markers
        # that act as the true coupling mass in legacy Fortran, as well as VALUE and OPTIONAL.
        # #1209: name and parameter-list span split into their own
        # capture groups (was only reachable via group(0), the whole
        # match including the "SUBROUTINE"/"FUNCTION"/"ENTRY" prefix and
        # name) so detector.py's counter isolates just "(...)" instead of
        # whitespace-splitting the prefix text -- the same overcount
        # shape #1199 fixed elsewhere. The args group's trailing empty
        # alternative (`|`) makes it participate even when the parens are
        # genuinely absent (a bare `SUBROUTINE Foo` with zero arguments
        # is valid Fortran with no "()" at all) -- without it, a
        # zero-arg bare subroutine's ONLY participating group would be
        # the name itself, which the existing whitespace-split fallback
        # would then miscount as 1 argument instead of 0. The bare
        # INTENT/VALUE/OPTIONAL alternative is left alone -- it's a
        # signal for keyword usage inside a parameter declaration line,
        # not a per-function signature match, and (per func_start's own
        # anchoring at the declaration line) is never actually the FIRST
        # match within a sliced function block in practice.
        "args": re.compile(
            r"\b(?:SUBROUTINE|FUNCTION|ENTRY)\s+([A-Za-z_]\w*)\s*(\([^)]*\)|)|\b(?:INTENT\s*\(\s*(?:IN|OUT|INOUT)\s*\)|VALUE\b|OPTIONAL\b)",
            re.I,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries defining straight-line execution and data types.
        # CRITICAL GUARDRAIL: Access modifiers (PUBLIC, PRIVATE, PROTECTED) do not belong here. Explicitly omitted to prevent the Structural Complexity Inflation Bug
        "structural_boundaries": re.compile(
            r"\b(PROGRAM|MODULE|SUBMODULE|BLOCK\s+DATA|CONTAINS|END\s+(?:PROGRAM|MODULE|SUBROUTINE|FUNCTION|BLOCK|TYPE|ASSOCIATE)|RETURN|IMPLICIT|USE|ASSOCIATE|BLOCK|INTEGER|REAL|COMPLEX|LOGICAL|CHARACTER|DOUBLE\s+PRECISION|CLASS)\b",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # =====================================================================
        # [ CONTEXT: FORTRAN FUNCTION AST EXTRACTOR & REDOS SHIELD]
        # PURPOSE: Anchors executable logic blocks (Program, Subroutine, Function, Entry)
        #   across 60+ years of Fortran dialects (F77 through F2018).
        # VULNERABILITY: Fortran allows extreme signature variability: prefix stacking
        #   (PURE RECURSIVE), legacy memory sizing (REAL*8), modern kinds (INTEGER(KIND=4)),
        #   derived types (TYPE(MyStruct)), object-oriented classes (CLASS(Obj)), and
        #   trailing attributes (RESULT, BIND(C)). Using unbounded `\s+` across these
        #   permutations causes Catastrophic Backtracking (ReDoS) on large legacy files.
        # THE "IRON WALL" FIX:
        #   1. Strict `[ \t\n]` bounds prevent horizontal/vertical bleeding.
        #   2. Negative lookahead `(?!\bEND\b)` prevents ghosting `END SUBROUTINE FOO`.
        #   3. Clamped quantifiers `{0,5}` on prefixes stop runaway recursion.
        #   4. Added `CLASS` to the base types to support modern Object-Oriented Fortran.
        #   5. Positive lookaheads on the tail `(?=...)` safely handle line continuations (`&`)
        #      and F90 comments (`!`) without consuming them into the capture group.
        # =====================================================================
        "func_start": re.compile(
            # 1. THE HORIZONTAL ANCHOR & END SHIELD
            # Stops O(N^2) vertical spirals. Explicitly blocks "END SUBROUTINE FOO" from triggering.
            r"^[ \t]*(?!\bEND\b)"
            # =====================================================================
            # [ THE VERTICAL LEGACY SHIELD ] (Hard-learned from Pathological Fuzzer):
            # Fortran allows extreme prefix stacking (e.g., `PURE RECURSIVE REAL*8`).
            # We previously restricted this to `[ \t]+` to avoid newline spirals.
            # FIX: Fortran developers frequently use line continuations (`&`) or split types.
            # We carefully upgraded `[ \t]` to `[ \t\n]` inside the rigidly bounded
            # `{0,5}` modifier limits so the engine can safely leap over vertical lines
            # without resorting to unbounded `\s+` which triggers ReDoS.
            # =====================================================================
            # 2. THE PREFIX STACK
            # F95/F2008 allows stacking prefixes. Capped at {0,5} to prevent ReDoS.
            r"(?:(?:PURE|ELEMENTAL|RECURSIVE|IMPURE|MODULE)[ \t\n]+){0,5}"
            # 3. THE RETURN TYPE
            # Optional for Subroutines/Programs, mandatory for explicit Functions.
            r"(?:"
            # 3a. Base Types (Primitives + Derived + Classes + Legacy + Complex)
            r"(?:INTEGER|REAL|COMPLEX|LOGICAL|CHARACTER|TYPE|CLASS|DOUBLE[ \t\n]+PRECISION|DOUBLE[ \t\n]+COMPLEX)"
            # 3b. Legacy Sizing (*8) or Modern Kinds/Lengths ((KIND=4, LEN=*)) and Attributes.
            # #1531: this lazy class includes letters/newlines with no length cap, so on a
            # body-less type declaration line immediately preceding an unrelated later
            # SUBROUTINE/FUNCTION (e.g. `CHARACTER(len=*), INTENT(IN) :: message` followed a
            # few lines later by `END SUBROUTINE wrf_message`), backtracking let it swallow
            # the ENTIRE intervening subroutine body -- including its own trailing
            # `END SUBROUTINE <name>` -- and match keyword+identifier there instead,
            # producing a phantom duplicate whose start_line/args belonged to a type
            # declaration, not any real definition. `{0,40}` caps the class at comfortably
            # more than any real single/continued attribute list needs (confirmed against
            # language-crucible's fortran corpus) while landing well short of the ~95+ chars
            # needed to reach a phantom match. A per-character `(?!\bEND\b)` exclusion was
            # tried first and is more semantically precise, but disables the `re` module's
            # fast path for a plain bounded character class -- confirmed via direct timing
            # (0.01s here vs. ~13s with the lookahead) on a payload of thousands of repeated
            # type-declaration lines with one distant END, a real ReDoS regression on a
            # non-pathological, plausible shape. A numeric bound has none of that risk.
            r"(?:[A-Za-z0-9_ \t&*,()=:]|&\s*\n){0,40}?"
            r")?"
            # 4. THE EXECUTION BLOCK KEYWORD
            # Supports multi-line continuation `&` inside the spaces
            r"(?:FUNCTION|SUBROUTINE|PROGRAM|ENTRY)[ \t\n&+]+"
            # 5. THE IDENTIFIER CAPTURE (FUNCTION IDENTIFIER - GROUP 1)
            # Extracts the actual block name.
            r"([A-Za-z_]\w*)"
            # 6. THE TRAILING ANCHOR (Lookahead)
            # Confirms the boundary without consuming it. Handles opening parens `(`, comments `!`,
            # line continuations `&`, EOF `$`, or explicit F2003+ modifiers (RESULT, BIND).
            r"(?=[ \t\n]*(?:[\(!&]|$|\bRESULT\b|\bBIND\b))",
            re.I | re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Defines object-oriented and structural boundaries. Drives API Surface Area math.
        # Maps to Fortran MODULEs, SUBMODULEs, INTERFACEs, and structural TYPE definitions (Fortran's struct/class equivalent).
        # Upgraded to handle SUBMODULE (parent) child syntax and trailing comments.
        # #1264: `(?!PROCEDURE\b)` excludes `MODULE PROCEDURE name1, name2` --
        # a separate-module-procedure implementation stub, not a `MODULE
        # <name>` declaration -- from being misread as a module named
        # "PROCEDURE". Invisible until #1264 wired class_start into the
        # named-entity extractor; previously class_start only fed a
        # numeric signal count that never surfaced the bad name.
        "class_start": re.compile(
            r"^[ \t]*(?!\bEND\b)(?:(?:MODULE|BLOCK\s+DATA|INTERFACE)\s+|SUBMODULE\s*(?:\([^)]*\))?\s+)(?!PROCEDURE\b)([A-Za-z_]\w*)|"
            r"^[ \t]*(?!\bEND\b)TYPE(?:[ \t]*::\s*|,[^:]*::\s*|\s+)([A-Za-z_]\w*)(?=[ \t]*(?:!|\n|$))",
            re.I | re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming)
        # Fortification markers establishing strict boundaries: explicit typing (`IMPLICIT NONE`),
        # explicit intent (`INTENT(IN)`), bounds safety (`ALLOCATABLE`), and fatal assertions (`ERROR STOP`).
        # BUG FIX: the shared trailing `\b` broke the INTENT(...) alternative,
        # which ends in a literal `)` (non-word) -- `\b` right after can only
        # fire if the very next char is a word character, never true for the
        # realistic form ("INTENT(IN) :: x", followed by whitespace). INTENT(...)
        # never actually matched in practice. Split it out of the shared group.
        "safety": re.compile(
            r"\bIMPLICIT\s+NONE\b|\bINTENT\s*\(\s*(?:IN|OUT|INOUT)\s*\)|"
            r"\b(?:ALLOCATABLE|SAVE|PARAMETER|VALUE|ERROR\s+STOP|ASYNCHRONOUS|ASSOCIATED|ALLOCATED|PRESENT)\b",
            re.I,
        ),
        # 7. safety_neg (Safety Bypasses)
        # Actively bypasses memory safety and compiler predictability.
        # Legacy memory sharing (`COMMON`, `EQUIVALENCE`), dangerous implicit typing rules, and unprotected legacy array `DIMENSION` bounds.
        "safety_bypasses": re.compile(
            r"\b(COMMON|EQUIVALENCE|IMPLICIT\s+(?:REAL|INTEGER|CHARACTER|COMPLEX|LOGICAL|DOUBLE))\b",
            re.I,
        ),
        # 8. danger (High-Risk Execution)
        # Extreme tech debt, unconstrained legacy jumps (`GO TO`, `ASSIGN`), and raw terminal output.
        # CRITICAL GUARDRAIL: Terminal prints (`PRINT`, `WRITE(*,...)`) strictly routed here, away from `io` and `telemetry`.
        "high_risk_execution": re.compile(r"\b(GO\s*TO|GOTO|ASSIGN|RETURN\s+\d+)\b", re.I),
        # 9. io (I/O & Network Boundaries)
        # File operations, hardware inquiries, and disk boundaries.
        # Negatively asserts `*` or `6` to ensure raw standard-out terminal prints do not trigger IO.
        # BUG FIX: the shared trailing `\b` broke the WRITE alternative, which
        # ends in a literal comma (non-word) -- `\b` right after can only fire
        # if the very next char is a word character, never true for the
        # overwhelmingly common realistic forms ("WRITE(10,*)", "WRITE(10,
        # '(I5)')", "WRITE(10, x)" -- all followed by `*`, `'`, or whitespace).
        # This made the file-unit-WRITE detection almost never fire in
        # practice. Split WRITE out of the shared-boundary group; it's already
        # unambiguously delimited by its own literal `(` and trailing `,`.
        "io": re.compile(
            r"\b(?:OPEN|CLOSE|READ|INQUIRE|REWIND|BACKSPACE|ENDFILE|FLUSH|FORMAT)\b|"
            r"\bWRITE\s*\(\s*(?!\*|6\b)[^,]+,",
            re.I,
        ),
        # 10. api (Public Surface Area)
        # Code exposed to the outside world. Visibility exports (`PUBLIC`) and FFI bridges (`BIND(C)`).
        "api": re.compile(
            r"\b(PUBLIC|BIND\s*\(\s*C\s*\))\b|"
            r"^[ \t]*(?:(?:PURE|ELEMENTAL|RECURSIVE)[ \t]+){0,5}(?:TYPE\s*\([^)]*\)[ \t]+)?(?:SUBROUTINE|FUNCTION)\s+[A-Za-z_]\w*",
            re.M | re.I,
        ),
        # 11. flux (State Mutation)
        # Mutation of state. Variable assignments and standard memory manipulations.
        # Captures standard `=` (avoiding `==`, `<=`, etc.)
        # TWO FIXES:
        # 1. QUADRATIC BLOWUP: the unbounded `[A-Za-z0-9_%()]+` (no \b
        #    anchor) got retried at every position in a long `=`-less
        #    line, backtracking O(n) per position for O(n^2) total.
        #    Bounded to {0,199}; real Fortran variable/array-element
        #    expressions (even with subscripts) don't get remotely
        #    that long.
        # 2. KIND=/LEN=/etc EXCLUSION WAS LEAKY: the negative lookahead
        #    only blocks a match starting exactly at "KIND", not one
        #    starting mid-word (e.g. "KIND = 5" still matched "IND = "
        #    starting at position 1, since \bKIND doesn't apply there).
        #    Added a real `\b` + explicit `[A-Za-z_]` first-char
        #    requirement so the match can only start at a genuine word
        #    boundary, where the exclusion lookahead actually applies.
        "state_mutation": re.compile(
            r"(?!\b(?:KIND|LEN|UNIT|FMT|FILE|STATUS|ACTION)\s*=)\b[A-Za-z_][A-Za-z0-9_%\(\)]{0,199}[ \t]*=[^=>]",
            re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented-out logic, commented-out structural code. Supports both Fortran 90+ (`!`) and legacy F77 (`C`/`*` in column 1).
        "dead_code": re.compile(r"(?i)(?:!|^[cC*])[ \t]*(?:if|do|where|call|function|subroutine|allocate)\b"),
        # 13. doc (Structured Documentation)
        # Documentation meant to be parsed by generators (Doxygen style `!>`, `!<`, or `! @`).
        "doc": re.compile(
            r"^[Cc*!dD][ \t]*[@><\\]|^[ \t]*![ \t]*(?:Author|Description|Param|Return):",
            re.I | re.M,
        ),
        # 14. test (Testing & Assertions)
        # Test frameworks like pFUnit, generic assertions, and verification routines.
        # BUG FIX: all 5 pFUnit alternatives are `@`-prefixed -- the
        # leading \b could only fire when a word char immediately
        # preceded the `@`, never true for how these annotations are
        # actually written. None ever matched at all.
        "test": re.compile(
            r"@test\b|@assertEqual\b|@assertTrue\b|@assertFalse\b|@assertException\b|call[ \t]+assert_[a-z_]+",
            re.I,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # Fortran 2008/2018 Coarrays (distributed shared memory programming natively in the language) and OpenMP pragmas.
        "concurrency": re.compile(
            r"\b(COARRAY|SYNC\s+ALL|SYNC\s+IMAGES|SYNC\s+MEMORY|CRITICAL|LOCK|UNLOCK|FAIL\s+IMAGE|FORM\s+TEAM|MPI_[A-Za-z_]+)\b|!\$(?:OMP|ACC)\b",
            re.I,
        ),
        # 16. ui_framework (UI / View Components)
        # Fortran handles math and background computing. No native UI frameworks exist.
        "ui_framework": None,
        # 17. closures (Closures / Anonymous Functions)
        # Fortran does not natively support closures, lambdas, or anonymous functions.
        "closures": None,
        # 18. globals (Global / Shared State)
        # Persistent application state across scopes. F77 `COMMON` blocks, `SAVE` variables, and `EXTERNAL` procedures.
        "globals": re.compile(r"\b(COMMON|SAVE|EXTERNAL)\b", re.I),
        # 19. decorators (Decorators / Annotations)
        # Fortran does not have Python-style decorators, but compiler directives heavily modify block execution behaviors.
        # BUG FIX: the shared trailing `\b` after the `$`-ending alternatives
        # (!DIR$/cDEC$) is a no-op in the realistic form -- real directives are
        # always written with a space after the `$` ("!DIR$ SIMD"), and `\b`
        # can never fire between two non-word characters. Only the OMP/ACC
        # alternatives (which end in a word character) legitimately need it.
        "decorators": re.compile(r"^[ \t]*(?:!DIR\$|cDEC\$|!\$OMP\b|!\$ACC\b)", re.I | re.M),
        # 20. generics (Generics / Type Parameters)
        # Fortran Generic Interfaces overriding operators/assignments, and Parameterized Derived Types (PDTs).
        # CRITICAL GUARDRAIL: Safely bounds `<[^>]*>` and parentheses `\([^)]*\)` to avoid ReDoS.
        # BUG FIX: the shared trailing `\b` applied to every alternative broke
        # 3 of 5 -- GENERIC::, TYPE name(...), and EXTENDS(...) all end in a
        # non-word character (`:` or `)`), so a `\b` immediately after can only
        # fire if the very next character is a word character, never true for
        # realistic code ("GENERIC :: foo", "TYPE point(k, n)", "EXTENDS(base)"
        # followed by whitespace/newline/EOF). Moved the boundary onto only the
        # two alternatives that actually end in a word character.
        "generics": re.compile(
            r"\b(?:INTERFACE\s+ASSIGNMENT\b|INTERFACE\s+OPERATOR\b|GENERIC\s*::|"
            r"TYPE\s+[A-Za-z_]\w*\s*\([^)]*\)|EXTENDS\s*\([^)]*\))",
            re.I,
        ),
        # 21. comprehensions (Iterators / Comprehensions)
        # Modern Fortran implicit loops, array constructors (`[...]`, `(/.../)`), and parallel execution syntax (`DO CONCURRENT`, `FORALL`).
        "comprehensions": re.compile(r"\b(?:FORALL|DO\s+CONCURRENT)\b|\[[^\]]+\]|\(\/[^/]+\/\)", re.I),
        # 22. scientific (Numerical / Compute Libraries)
        # Native Fortran superpower: Vectorized matrix operations, tensor reductions, and strict scientific primitive typing.
        "scientific": re.compile(
            r"\b(MATMUL|DOT_PRODUCT|TRANSPOSE|SUM|PRODUCT|MAXVAL|MINVAL|MAXLOC|MINLOC|RESHAPE|SQRT|EXP|LOG|LOG10|SIN|COS|TAN|ASIN|ACOS|ATAN|ATAN2|SINH|COSH|TANH|KIND=|CEILING|FLOOR|MOD|MODULO)\b",
            re.I,
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # High Cognitive Load: Memory aliasing (`EQUIVALENCE`), multiple entry points (`ENTRY`), Object-Oriented runtime dispatch (`CLASS DEFAULT`, `%`), and unstructured `NAMELIST` loading.
        "reflection_metaprogramming": re.compile(
            r"\b(EQUIVALENCE|ENTRY|SELECT\s+TYPE|CLASS\s+DEFAULT|NAMELIST|VOLATILE)\b",
            re.I,
        ),
        # 24. import (Dependency Inclusions)
        # Dependency linkage across Fortran modules and files.
        "import": re.compile(r"\b(USE|INCLUDE|IMPORT)\b", re.I),
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:USE(?:\s+|\s*(?:,[^:]*)?::\s*)([a-zA-Z0-9_]+)|INCLUDE[ \t\n]*['\"]([^'\"]+)['\"]|SUBMODULE\s*\(\s*([^):]+)[^)]*\))",
            re.IGNORECASE | re.MULTILINE,
        ),
        # 25. ownership (Authorship Metadata)
        # Identifying the developer, maintainer, or copyright holder natively.
        "ownership": re.compile(
            r"^[cCdD*!][ \t]*(?:Author|Created by|Maintainer|Developer):\s+(.*)",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # Audit tags establishing traceability of intent back to physics papers or architectural specifications.
        # CRITICAL: Removed (?i) to enforce strict uppercase [SPEC-XYZ] tags and prevent prose collisions.
        "spec_exposure": re.compile(r"\[\s*(?:SPEC\s*-\s*\d+|AUDIT-[A-Z0-9_-]+)\s*\]"),
        # 31. ssr_boundaries (Server-Side Rendering)
        # Fortran does not perform Server-Side Rendering.
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Fortran 2018 natively introduced Event-Driven programming primitives for Coarray synchronization.
        "events": re.compile(r"\b(EVENT\s+POST|EVENT\s+WAIT|EVENT_QUERY)\b", re.I),
        # 33. dependency_injection (Dependency Injection / IoC)
        # Fortran handles linkages procedurally or via modules. No native DI containers or decorators exist.
        "dependency_injection": None,
        # Low-level systems language concepts mapped to Fortran paradigms.
        # 34. macros (Preprocessor Directives / Macros)
        # Fortran utilizes the standard C Preprocessor (cpp) allowing for structural `#define`, `#ifdef` pathing (e.g., `#ifdef MPI`).
        "macros": re.compile(
            r"^[ \t]*#(?:define|undef|if|ifdef|ifndef|elif|else|endif|include|pragma)\b",
            re.M | re.I,
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Explicit memory mapping. Includes native Fortran `POINTER` logic, assignments `=>`, and C-FFI pointer bridges (`C_PTR`).
        "pointers": re.compile(r"(?i)\bpointer\b|[ \t]*=>[ \t]*"),
        # 36. memory_alloc (Manual Memory Management)
        # Dynamic memory allocation managed explicitly by the developer on the heap.
        "memory_alloc": re.compile(r"\b(ALLOCATE|DEALLOCATE|MOVE_ALLOC|MALLOC|FREE)\b", re.I),
        # 37. inline_asm (The Bare Metal)
        # Fortran delegates assembly to standard C linkage. Inline ASM is explicitly not supported natively in Fortran code.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (The Structured Observers)
        # CRITICAL GUARDRAIL: Isolates structured diagnostic output (custom Fortran loggers) away from raw terminal prints.
        "telemetry": re.compile(
            r"\b(?:call[ \t]+)?(?:log_info|log_error|log_warn|log_debug|logger%info|logger%error|logger%warn|logger%debug|flog)\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        # Raw terminal output natively dumping to stdout.
        "debug_prints": re.compile(r"\b(?:PRINT\b|WRITE\s*\(\s*(?:\*|6)\s*[,)])", re.I),
        # # 40. explicit_casts (Explicit Type Casting)
        # Forceful type coercion bypassing the safety engine. Strictly defining known Fortran intrinsic type conversion functions.
        "explicit_casts": re.compile(r"(?i)\b(?:int|real|cmplx|dble|achar|char|iachar|ichar)[ \t]*\([^)]*\)"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        # Hard execution destruction and unrecoverable exceptions.
        "panics_and_aborts": re.compile(r"(?i)\b(?:stop|error[ \t]+stop|return)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        # Forcing threads to sleep.
        "thread_sleeps": re.compile(r"(?i)\bcall[ \t]+(?:sleep|usleep)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        # Low-level byte manipulation utilizing Fortran's explicit intrinsic bitwise functions.
        "bitwise_ops": re.compile(r"(?i)\b(?:iand|ior|ieor|not|ishft|ishftc|btest|ibset|ibclr|ibits)\b"),
        # 44. sync_locks (Resource Management & Stability)
        # Explicit coordination to prevent race conditions .
        "sync_locks": re.compile(r"(?i)\b(?:lock|unlock|critical|sync[ \t]+all|sync[ \t]+images|sync[ \t]+memory)\b"),
        # 45. immutability_locks (Immutability Constraints)
        # Explicit locking of data to prevent mutation .
        # BUG FIX: the shared trailing `\b` broke the intent(...) alternative,
        # which ends in a literal `)` (non-word) -- same defect class as the
        # `safety` rule's INTENT(...) alternative above. Dropped the trailing
        # boundary for it; `)` is already unambiguous.
        "immutability_locks": re.compile(r"(?i)\bparameter\b|\bintent[ \t]*\([ \t]*in[ \t]*\)"),
        # 46. cleanup (Resource Cleanup / Teardown)
        # Explicit destruction of state or closing of streams .
        "cleanup": re.compile(r"(?i)\b(?:close|deallocate|nullify)\b"),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Logic hidden from view via visibility modifiers .
        "encapsulation": re.compile(r"(?i)\bprivate\b"),
        # 48. listeners (Event Listeners / Observers)
        # Waiting to receive state from an external broadcast .
        "listeners": None,
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # Framework code that explicitly bypasses verification.
        "test_skip": None,
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Fortran Specifics) ---
        "serialization_parsing": re.compile(r"(?i)\b(NAMELIST|READ\s*\(|WRITE\s*\(|FORMAT|OPEN\s*\()\b"),
        "regex_execution": re.compile(
            r"(?i)\b(SCAN|INDEX|VERIFY|ADJUSTL|ADJUSTR)\b"
        ),  # Relies on intrinsic string processing
        "time_date_logic": re.compile(r"(?i)\b(DATE_AND_TIME|SYSTEM_CLOCK|CPU_TIME)\b"),
        # BUG FIX: the shared trailing `\b` made the `OMP_` prefix alternative
        # unreachable -- `OMP_` ends in `_` (a word char), and real OpenMP
        # runtime calls always continue with more word characters right after
        # (`OMP_GET_THREAD_NUM`), so the boundary could never fire (both sides
        # word chars). `OMP_` was clearly meant as a prefix match, not an
        # exact-token match -- dropped the trailing boundary for it.
        "ipc_rpc_bridges": re.compile(r"(?i)\b(?:MPI_Init|MPI_Send|MPI_Recv|MPI_Bcast|EXECUTE_COMMAND_LINE)\b|\bOMP_"),
    },
}
