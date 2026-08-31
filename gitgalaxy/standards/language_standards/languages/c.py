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
        "target_version": "C23 (ISO/IEC 9899:2024 - constexpr, #embed, [[attributes]], nullptr, typeof)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard sources, headers, OpenCL kernels, Yacc grammars, and C-like scripting/ATS language files.
    # THE FIX: Added .dts and .dtsi (Device Tree Source) to parse hardware maps.
    "extensions": [
        ".c",
        ".h",
        ".cl",
        ".inc",
        ".y",
        ".idc",
        ".cats",
        ".dts",
        ".dtsi",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files (like .h or .inc).
    "discriminators": [
        ".c",
        "Makefile",
        "configure.ac",
        "configure.in",
        "configure",
        "CMakeLists.txt",
        "Kconfig",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["tcc", "picoc", "cscript"],
    # UPGRADED: Maps to Family 1 (Standard C)
    # Rationale: Uses '//' for line-level literature; multi-line literature
    # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and jumps. EXCLUDES exit/abort (bailout_hits).
        "branch": re.compile(r"\b(if|else|switch|case|default|for|while|do|break|continue|goto)\b|&&|\|\||\?"),
        # 2. args (Parameters / Coupling)
        # Parameter blocks. Bounded negation [^)]* to prevent ReDoS on massive param lists.
        "args": re.compile(
            # =====================================================================
            # [ THE NESTED POINTER SHIELD (C) ]
            # Standard parameter capture `[^)]*` fails instantly on function pointers
            # like `void (*cb)(int)`.
            # FIX: Replaced `[^)]*` with the 1-Level Nesting Trick `(?:[^)(]+|\([^)]*\))*`
            # to safely swallow function pointer parameters without triggering ReDoS.
            # Upgraded horizontal `[ \t*]*` to `[ \t\n*]*` to support vertical signatures.
            # =====================================================================
            # #1209: parameter-list span wrapped in its own capture group
            # (was the whole match, "name(...)") so detector.py's counter
            # isolates just "(...)" instead of falling back to whitespace-
            # splitting the name-plus-parens text, which overcounted every
            # zero/one-arg signature by +1 the same way Python's did (#1199).
            # BUG FIX (#1282): the typed-parameter-list requirement only ever
            # recognized C's builtin primitive keywords -- a parameter typed
            # as a custom typedef/struct name (`PyThreadState *tstate`,
            # `FILE *fp`, `size_t n`; the overwhelming majority of real-world C
            # signatures, confirmed against cpython/ceval.c) never matched at
            # all, so `_calculate_block_metrics` fell through to args_count's
            # 0 default for functions with real, nonzero arity. cpp's own args
            # rule already carries this exact fallback (`[A-Z]\w*` for
            # PascalCase/typedef'd types, `[a-z_]\w*_t` for the `_t` typedef
            # convention); mirrored here, plus `_*` ahead of the PascalCase
            # branch for C's leading-underscore "reserved identifier"
            # convention (`_PyStackRef`, `_Bool`, ...), extremely common in
            # cpython internals and not covered by cpp's own version of this
            # fallback.
            r"(?!(?:if|for|while|switch|return|sizeof|typeof|_Alignof|__typeof__|__builtin_[a-zA-Z0-9_]+)\b)\b([a-zA-Z_]\w*)[ \t\n*]*(\(\s*(?:const\s+|volatile\s+)?(?:int|char|void|float|double|long|short|unsigned|signed|struct|enum|_*[A-Z]\w*|[a-z_]\w*_t|[a-z_]\w*\s+[*&]*\s*[a-zA-Z_]\w*)\b(?:[^)(]|\([^)]*\))*\))",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(struct|union|enum|typedef|return|void|restrict|auto|bool|true|false|_BitInt|alignas|alignof)\b"
        ),
        "func_start": re.compile(
            # =====================================================================
            # [ CRITICAL ROADMAP FOR FUTURE LLMs & MAINTAINERS: THE REDOS IRON WALL ]
            # PURPOSE: Anchors executable logic blocks (functions) in C.
            #
            # 1. THE K&R AMBIGUITY TRAP (The Original Fix):
            #    The engine was consuming `BEGIN` as a parameter type (e.g. `BEGIN i;`).
            #    When it failed to find a semicolon, it backtracked through 15 loops of
            #    whitespace combinations causing 34-second ReDoS hangs.
            #    RULE: The K&R gap MUST use `(?!(?:BEGIN...)\b)[a-zA-Z_]` to instantly reject.
            #    RULE: NO OVERLAPPING WHITESPACE: `\s+` exclusively owns all spaces.
            #
            # 2. [ THE COMPILER ATTRIBUTE SHIELD ] (Hard-learned from Pathological Fuzzer):
            #    Kernel and embedded C code frequently stack `__attribute__((...))`
            #    definitions across multiple vertical lines before the function signature.
            #    FIX: Injected a dedicated, bounded `__attribute__` scanner `(?:__attribute__\s*\([^)]*\)\s*){0,5}`
            #    at the start of the pipeline. This explicitly permits multi-line `\s*` traversal
            #    without triggering Catastrophic Backtracking against the modifiers.
            # =====================================================================
            # 1. The Horizontal Anchor
            r"^[ \t]*"
            # [ THE COMPILER ATTRIBUTE SHIELD ]: Safely consumes GCC/Clang attributes across newlines.
            # #2460: also a SAL / entry-point annotation macro before the return type
            # (`__control_entrypoint(DllExport) STDAPI Foo()`, `_Ret_maybenull_`) --
            # a `__`- or `_Uppercase`-prefixed identifier, optionally with a bracketed
            # argument. Naming-shape bounded so it can't eat an ordinary function call.
            r"(?:(?:__attribute__\s*\((?:[^)(]|\((?:[^)(]|\([^)]*\))*\))*\)|(?:__[a-z]\w*|_[A-Z][A-Za-z0-9]*_)(?:\s*\((?:[^)(]|\([^)]*\))*\))?)\s*){0,5}"
            # 2. Modifiers (Strictly bounded)
            r"(?:(?:static|inline|extern|_Noreturn|__inline__|__forceinline|constexpr)\s+){0,3}"
            # 3. Complex types
            r"(?:(?:struct|union|enum)\s+)?"
            # 4. Return type (Strictly linear)
            r"(?:[a-zA-Z_]\w+\s+){0,3}[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)"
            # [ MACRO SHIELD ]: Support macros between return type and function name (e.g. PyAPI_FUNC(int) or _Py_HOT_FUNCTION)
            r"(?:[a-zA-Z_]\w+(?:\s*\([^)]*\))?\s+){0,5}"
            # 5. The "Not a Function" Shield
            r"(?!(?:if|for|while|switch|return|sizeof)\b)"
            # 6. The Identifier Capture (Satellite Name - Group 1)
            r"([a-zA-Z_]\w*)"
            # [NESTED PARENTHESIS FIX]: Uses 1-Level Nesting Trick to swallow function pointers and macros without ReDoS.
            r"\s*\((?:[^)(]|\([^)]*\))*\)"
            # 8. The K&R C Parameter Gap (Legacy support for DOOM/MS-DOS)
            # [IRON WALL FIX]: Forces instant failure if it encounters BEGIN or control flow.
            r"(?:\s+(?!(?:BEGIN|if|for|while|switch|return)\b)[a-zA-Z_][^;{]{0,150};){0,15}"
            # 9. The Ignition (Includes the MS-DOS 'BEGIN' macro)
            r"\s*(?:\{|BEGIN\b)",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # C uses structs/unions/enums as the primary entity entities.
        # BUG FIX (epic #813/#822): the tag name was mandatory, so anonymous typedef'd structs
        # (`typedef struct { ... } MyStruct;`, an extremely common real C idiom) never matched
        # at all -- undercounting this structural signature. Made the tag name optional.
        # NOTE: a trailing-`{` requirement was tried and reverted -- it would have "fixed" this
        # rule matching bare variable declarations of an existing struct type
        # (`struct foo_ops ops;`), but test_c_intentional_double_classification_sweep
        # (tests/extraction/languages/test_c_strict.py) documents that co-firing as DELIBERATE: it's how
        # the `_ops`-vtable-style dependency_injection heuristic pairs with class_start for
        # exactly this shape. Any future change here must keep that test passing.
        "class_start": re.compile(r"^[ \t]*(?:typedef[ \t]+)?(?:struct|union|enum)\b(?:\s+([a-zA-Z_]\w*))?", re.M),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(assert|static_assert|_Static_assert|size_t|snprintf|strncat|strncpy|calloc|nullptr|unreachable|ckd_add|ckd_sub|ckd_mul)\b"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Dangerous legacy functions and raw void manipulation.
        "safety_bypasses": re.compile(r"\b(strcpy|strcat|sprintf|gets|alloca)\b|\([a-zA-Z_]\w*\s*\*\)\s*[a-zA-Z_]\w*"),
        # 8. danger (High-Risk Execution / System Calls)
        # Process killers and context switches. EXCLUDES prints (Phase 5).
        "high_risk_execution": re.compile(r"\b(system|popen|execl|execv|fork|longjmp|setjmp)\b"),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(fopen|fclose|fread|fwrite|fscanf|sscanf|socket|recv|send|open|read|write|close|stat|fseek|remove|rename)\b"
        ),
        # 10. api (Public Surface Area)
        # Linker-visible global exports.
        "api": re.compile(
            # =====================================================================
            # [ROADMAP: AMBIGUITY OVERLAP AVOIDANCE]
            # Previously used `[ \t*]+` between words. If a string failed to match,
            # the engine backtracked to see if it should assign spaces to the left
            # word, right word, or the wildcard.
            # FIX: We now use strict O(1) alternation `(?:\s*[*&]+\s*|\s+)` which
            # forces the engine to choose exactly one path and never backtrack.
            # =====================================================================
            # BUG FIX (Rule 9): `__declspec(dllexport)` and
            # `__attribute__((visibility("default")))` both end in `)`
            # (non-word) but shared a trailing `\b` with word-ending
            # `extern` -- `\b` right after can only fire if the next char
            # is a word character, never true for the realistic form
            # (whitespace/newline before the return type follows). Pulled
            # both out of the shared boundary group.
            r"\bextern\b|__declspec\(dllexport\)|"
            r'__attribute__\(\(visibility\("default"\)\)\)|'
            r"^[ \t]*(?!static\b)[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*(?:\[[^\]]*\])?\s*=?|"
            r"^[ \t]*[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*\s*\([^)]*\)\s*;",
            re.M,
        ),
        # 11. flux (State Mutation)
        # Mutation of state. EXCLUDES const/constexpr (freeze_hits).
        "state_mutation": re.compile(r"(?<![=!<>])=(?![=])|\*(?!\s*const)\w+[ \t]*=|(?:\+\+|--)"),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"(?://|/\*)[ \t]*(?:if|for|while|struct|union|enum|void|int|return)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"///|/\*\*|@param|@return|@brief|@details|\\param|\\return|\\brief|\\details"),
        # 14. test (Testing & Assertions)
        "test": re.compile(
            r"\b(?:TEST|TEST_F|TEST_CASE|CU_ASSERT|RUN_TEST|EXPECT_[A-Z_]+|ASSERT_[A-Z_]+)\b|\bassert\s*\("
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(thrd_create|thrd_join|mtx_lock|pthread_create|pthread_mutex_lock|atomic_int|_Atomic|memory_order_[a-z]+|thread_local)\b"
        ),
        # 16. ui_framework (UI / View Components)
        "ui_framework": re.compile(
            r"\b(GtkWidget|CreateWindow|MessageBox|XOpenDisplay|gtk_window_new|Fl_Window|initscr|wprintw)\b"
        ),
        # 17. closures
        "closures": None,  # Strict C23 lacks native closures (blocks are non-standard).
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            # =====================================================================
            # [ROADMAP: AMBIGUITY OVERLAP AVOIDANCE]
            # Same strict O(1) alternation fix applied here as in the `api` rule
            # to prevent exponential space/asterisk evaluation.
            # =====================================================================
            r"^[ \t]*(?:static\s+|extern[ \t]+)?[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*(?:\[[^\]]*\])?\s*=(?![ \t]*==)",
            re.M,
        ),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"\[\[\s*[a-zA-Z_:][^\]]*\s*\]\]"),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(r"\b_Generic\s*\([^)]*\)"),
        # 21. comprehensions
        "comprehensions": None,
        # 22. scientific (Numerical / Compute Libraries)
        # BUG FIX (Rule 9): `cblas_` ends in `_` (a word char) and was
        # clearly intended as a prefix match for any BLAS routine
        # (`cblas_dgemm`, `cblas_sgemm`, ...), but shared a trailing `\b`
        # with word-ending siblings -- real usage always continues with
        # more word characters right after (`cblas_dgemm`), so the
        # boundary could never fire (both sides word chars). Pulled out
        # of the shared group with only a leading `\b`.
        "scientific": re.compile(
            r"\b(?:math\.h|tgmath\.h|complex\.h|dgemm|sin|cos|tan|exp|log|sqrt|complex|I|_Float\d+|__m\d+)\b|\bcblas_"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Macros with args and unstructured jumps.
        "reflection_metaprogramming": re.compile(r"^#\s*define\s+[a-zA-Z_]\w*\([^)]*\)|\bgoto\b", re.M),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r'^[ \t]*#[ \t]*(?:include|embed)\s*[<"][^>"]+[>"]', re.M),
        "_dependency_capture": re.compile(r'^[ \t]*#[ \t\n]*(?:include|embed)[ \t\n]*[<"]([^>"]+)[>"]', re.M),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"(?:@author|\\author|Author:|Created by:|Copyright)\s+(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # BUG FIX (Rule 14): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, and
        # rust earlier in this epic. Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        "ssr_boundaries": re.compile(r"\b(FCGI_Accept|khttp_parse|MHD_start_daemon|facil\.io)\b"),
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(r"\b(epoll_wait|epoll_ctl|kqueue|kevent|select|poll|libev|libuv)\b"),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(r"\b(plugin_register|vtable|struct\s+[a-zA-Z_]\w*_ops)\b"),
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(
            r"^[ \t]*#[ \t]*(?:define|undef|if|elif|else|endif|pragma|warning|error)\b",
            re.M,
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": re.compile(
            r"->|\b(?:uintptr_t|intptr_t|ptrdiff_t|size_t)\b|(?<=[=\s,(])&\w+|(?<=[=\s,(])\*(?:\s*const\s*)?\w+"
        ),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(r"\b(malloc|calloc|realloc|free|aligned_alloc|mmap|alloca)\b"),
        # 37. inline_asm (The Bare Metal)
        "inline_asm": re.compile(
            r"\b(?:__asm__|asm|__asm)\b(?:\s+(?:volatile|__volatile__))?\s*\(|\b(?:__asm__|asm|__asm)\b[ \t]*\{"
        ),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(r"\b(?:syslog|openlog|log_info|log_error|log_warn|log_debug|vsyslog)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(printf|fprintf|vprintf|puts|putchar|perror)\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            # =====================================================================
            # [ROADMAP: NESTED OPTIONAL SPACES (ReDoS TRAP)]
            # FIX 2: `\s*[*]*\s*` is highly vulnerable to ReDoS if the payload
            # is spaced asterisks like `(int * * *)`. Flattened to strictly linear
            # `[ \t\n]*(?:\*[ \t\n]*)*` to prevent any overlapping whitespace matching.
            # =====================================================================
            r"\(\s*(?:int|float|double|char|bool|long|short|unsigned|signed|void)[ \t\n]*(?:\*[ \t\n]*)*\)\s*[a-zA-Z_]"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(abort|exit|_Exit|quick_exit|return\s+-1)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(sleep|usleep|nanosleep|thrd_sleep)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>|\^|(?<![=!])~|<<=|>>=|&=|\|=|\^="),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(mtx_lock|mtx_unlock|pthread_mutex_lock|atomic_flag_test_and_set|atomic_store)\b"),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(const|constexpr|alignas|restrict)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(free|fclose|close|munmap|destroy|shutdown)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Physical Reality: Static functions/variables are internal/private to the translation unit.
        "encapsulation": re.compile(r"^[ \t]*static\b", re.M),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(on_event|handler|callback|signal\(|sigaction\()"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # BUG FIX (Rule 10): `mock\(`/`fake\(` end in a literal `(` but
        # shared a trailing `\b` with word-ending siblings -- broke on
        # the truly-empty-argument call form (`mock()`), where the next
        # char after `(` is `)`, not a word char.
        "test_skip": re.compile(r"\b(?:IGNORE_TEST|test\.skip)\b|mock\(|fake\("),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (C Specifics) ---
        "serialization_parsing": re.compile(r"\b(cJSON_Parse|json_loads|xmlReadMemory|xmlParseFile|jansson)\b"),
        "regex_execution": re.compile(r"\b(regcomp|regexec|regfree)\b"),
        "time_date_logic": re.compile(r"\b(time_t|clock_gettime|gettimeofday|localtime_r?|strftime)\b"),
        "ipc_rpc_bridges": re.compile(r"\b(fork|pipe|shmget|shmat|mmap|socket|bind|listen|accept)\b"),
    },
}
