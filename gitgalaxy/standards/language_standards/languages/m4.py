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
        "target_version": "GNU M4 1.4+ / Autoconf 2.71+",
        "last_updated": "2026-03-11",
        "blueprint_version": "v5.1",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard macros, Autotest suites (.at), Autoconf logic (.ac), and template stubs (.in).
    "extensions": [".m4", ".at", ".ac", ".in"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: The undeniable structural anchors of the GNU build system.
    "exact_matches": ["configure.ac", "configure.in"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Automake configurations and standard Makefiles acting as contextual baselines for ambiguous .in templates.
    "discriminators": [
        ".m4",
        "Makefile.am",
        "Makefile.in",
        "aclocal.m4",
        "config.h.in",
    ],
    # EXECUTION SIGNATURES: M4 is a macro processor; no traditional shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 8 (Singular/Unique)
    # Rationale: M4 uniquely uses the `dnl` (Delete to NewLine) macro to act as its
    # line-level Commented / Non-Executable Text.
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # M4 branching logic and Autoconf shell-generation branches.
        "branch": re.compile(r"\b(?:ifelse|ifdef|AS_IF|AS_CASE|m4_if|m4_case|m4_cond|m4_ifval|m4_ifblank)\b"),
        # 2. args (Parameters / Coupling)
        # M4 positional arguments.
        "args": re.compile(r"\$[0-9]+|\$[@*#]"),
        # 3. linear (Sequential Boundaries)
        # Execution flow diversion and dependency signaling.
        "structural_boundaries": re.compile(r"\b(?:divert|undivert|m4_divert|m4_undivert|m4_require|AC_REQUIRE)\b"),
        # 4. func_start (Executable Logic Anchors)
        # Defining a macro establishes an executable logic block in M4.
        # BUG FIX (2026-08-20, tri-comparison ledger sweep): the old pattern captured
        # the DEFUN KEYWORD itself as group 1 (e.g. "AC_DEFUN"), not the macro actually
        # being defined -- structurally identical to matching "def" as a function's name
        # instead of what follows it. Now captures the real first-argument macro name,
        # tolerating all three real m4 quoting conventions seen in production autoconf
        # code: classic backtick/apostrophe (`name'), bracket (`[name]`, or the more
        # defensive double-bracket `[[name]]`), and unquoted.
        "func_start": re.compile(
            r"^[ \t]*(?:m4_define|define|AC_DEFUN|AC_DEFUN_ONCE|AU_DEFUN|m4_defun)\s*\("
            r"\s*(?:`([A-Za-z_][A-Za-z0-9_]*)'|\[{1,2}([A-Za-z_][A-Za-z0-9_]*)\]{0,2}|([A-Za-z_][A-Za-z0-9_]*))",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        "class_start": None,  # M4 is a macro processor, lacking objects.
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Autoconf environment checks and M4 assertions.
        "safety": re.compile(
            r"\b(?:m4_assert|AS_VERSION_COMPARE|AC_CHECK_PROGS?|AC_CHECK_LIB|AC_CHECK_HEADERS?|AC_CHECK_FUNCS?|m4_warn)\b"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Dynamically altering the quote characters or comment strings breaks the parser context completely.
        "safety_bypasses": re.compile(r"\b(?:changequote|changecom|m4_changequote|m4_changecom|m4_ignore)\b"),
        # 8. danger (High-Risk Execution / System Calls)
        # Executing raw shell commands during macro expansion (not generation).
        "high_risk_execution": re.compile(r"\b(?:syscmd|esyscmd|m4_syscmd|m4_esyscmd)\b"),
        # 9. io (I/O & Network Boundaries)
        # Reading system values, creating temp files, or emitting generated configurations.
        "io": re.compile(r"\b(?:sysval|mkstemp|maketemp|m4_mkstemp|m4_maketemp|AC_CONFIG_FILES|AC_OUTPUT)\b"),
        # 10. api (Public Surface Area)
        # M4 macros are inherently public, but these explicitly export state into the generated Makefile/C headers.
        "api": re.compile(r"\b(?:AC_SUBST|AC_DEFINE|AC_PROVIDE|m4_provide)\b"),
        # 11. flux (State Mutation)
        # Stack-based macro overriding and list appending.
        "state_mutation": re.compile(
            r"\b(?:pushdef|popdef|m4_pushdef|m4_popdef|m4_append|m4_append_uniq|m4_combine)\b"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented-out macro definitions.
        # COMMENT-STYLE COMPLETENESS (Engine Rule 12): GNU M4's actual default
        # lexer-level comment delimiter is `#`-to-newline (confirmed in the shared
        # line_exclusive family table in gitgalaxy_config.py, which prism.py uses
        # to segment the comment stream for every line_exclusive language) --
        # `dnl` is a separate, macro-level discard-to-newline mechanism. Real
        # Autoconf/m4 corpus files use `#` comments as heavily as (often more
        # heavily than) `dnl`. Wired to both prefixes; only checking `dnl` missed
        # the dominant style.
        "dead_code": re.compile(r"^[ \t]*(?:dnl[ \t]+|#[ \t]*)(?:m4_define|define|AC_DEFUN|ifelse|AS_IF)\b", re.M),
        # 13. doc (Structured Documentation)
        # Documentation blocks or explicit copyright insertions into the output script.
        # Same comment-style completeness fix as dead_code above.
        "doc": re.compile(r"^[ \t]*(?:dnl[ \t]+|#[ \t]*)@(?:param|return|brief)|AC_COPYRIGHT\b", re.M),
        # 14. test (Testing & Assertions)
        # The GNU Autotest framework.
        "test": re.compile(r"\b(?:AT_SETUP|AT_CHECK|AT_CLEANUP|AT_INIT|AT_DATA)\b"),
        # --- 🔬 PHASE 3: SPECIALIZED SENSORS (Architecture & Complexity) ---
        # 15. concurrency
        "concurrency": None,
        # 16. ui_framework
        "ui_framework": None,
        # 17. closures
        "closures": None,
        # 18. globals (Global / Shared State)
        # Environment variables mapped into the configure script.
        "globals": re.compile(r"\b(?:AC_ARG_VAR|AC_ENV_VAR|m4_divert_text)\b"),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions (Iterators / Comprehensions)
        # M4 map and foreach iterative constructs.
        "comprehensions": re.compile(r"\b(?:m4_foreach|m4_foreach_w|m4_map|m4_map_sep)\b"),
        # 22. scientific (Numerical / Compute Libraries)
        # M4's native integer arithmetic evaluator.
        "scientific": re.compile(r"\b(?:eval|m4_eval)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Advanced string metaprogramming and regex substitutions.
        "reflection_metaprogramming": re.compile(
            r"\b(?:translit|patsubst|regexp|m4_translit|m4_bpatsubst|m4_bregexp|m4_pattern_allow)\b"
        ),
        # 24. import (Dependency Inclusions)
        # File inclusions.
        "import": re.compile(r"^[ \t]*(?:include|sinclude|m4_include|m4_sinclude)\b", re.M),
        # 25. ownership (Authorship Metadata)
        # Same comment-style completeness fix as dead_code above (Engine Rule 12).
        "ownership": re.compile(
            r"^[ \t]*(?:dnl[ \t]+|#[ \t]*)(?:Author|Maintainer|Copyright|License):|AC_COPYRIGHT",
            re.I | re.M,
        ),
        # --- 🌌 PHASE 4: EXTENDED DIMENSIONS (Specialized Sub-Equations) ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[[ \t]*(?:SPEC[ \t]*-[ \t]*\d{1,10}|\b(?:spec|audit)\b)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries
        "ssr_boundaries": None,
        # 32. events
        "events": None,
        # 33. dependency_injection
        # M4 dependency chaining to ensure macros execute in the correct order.
        "dependency_injection": re.compile(r"\b(?:AC_REQUIRE|m4_require)\b"),
        # 34. macros (Preprocessor Directives / Macros)
        # M4 is the macro engine, but this tracks configuring C-level preprocessor hooks.
        "macros": re.compile(r"\b(?:AC_DEFINE|AC_DEFINE_UNQUOTED|AH_TEMPLATE)\b"),
        # 35. pointers
        "pointers": None,
        # 36. memory_alloc
        "memory_alloc": None,
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        # Logging configure progress securely to stdout and config.log.
        "telemetry": re.compile(r"\b(?:AC_MSG_CHECKING|AC_MSG_RESULT|AC_MSG_WARN|AC_MSG_NOTICE)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        # Raw M4 error printing.
        "debug_prints": re.compile(r"\b(?:errprint|m4_errprint)\b"),
        # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": None,
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        # Hard aborts.
        "panics_and_aborts": re.compile(r"\b(?:m4_fatal|AC_MSG_ERROR|AC_MSG_FAILURE|AS_EXIT)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        # Raw sleeps in generated scripts.
        "thread_sleeps": re.compile(r"\b(?:sleep)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": None,
        # 44. sync_locks
        "sync_locks": None,
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": None,  # M4 macros are mutable by design.
        # 46. cleanup (Resource Cleanup / Teardown)
        # Macro unloading and Autotest tear-downs.
        "cleanup": re.compile(r"\b(?:m4_popdef|popdef|AT_CLEANUP)\b"),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Forbidding specific patterns from reaching the output script.
        "encapsulation": re.compile(r"\b(?:m4_pattern_forbid)\b"),
        # 48. listeners
        "listeners": None,
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # Skipping tests in the Autotest framework.
        "test_skip": re.compile(r"\b(?:AT_SKIP_IF)\b"),
    },
}
