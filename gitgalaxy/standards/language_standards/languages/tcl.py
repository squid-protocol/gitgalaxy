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
        "target_version": "Tcl 8.6 / SQLite Test Suite",
        "last_updated": "2026-03-11",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard scripts and Tcl modules.
    "extensions": [".tcl", ".itcl", ".tbc", ".tm"],  # Removed .test
    # ABSOLUTE IDENTITY & EXACT FILENAMES:
    "exact_matches": ["tclIndex", "pkgIndex.tcl"],
    # ECOSYSTEM ANCHORS: Added .test here so it only anchors, but doesn't claim globally.
    "discriminators": [".tcl", "tclIndex", ".test", "Makefile"],
    # EXECUTION SIGNATURES: Standard interpreters found on Line 1.
    "shebangs": ["tclsh", "wish", "bin/expect", "jimsh"],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: Tcl natively uses '#' exclusively for line-level comments. It does not
    # have native block comments (developers sometimes hack `if 0 { ... }`, but `#` is the standard).
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Tcl control flow keywords.
        "branch": re.compile(r"\b(?:if|elseif|else|switch|while|for|foreach|catch|try|trap|finally)\b"),
        # 2. args (Parameters / Coupling)
        # Safely captures the parameter list `{...}` immediately following a proc name.
        "args": re.compile(
            # =====================================================================
            # [ THE VERTICAL PROC SHIELD (TCL) ]
            # Tcl developers can break the `proc`, name, and argument brace `{}`
            # across newlines.
            # FIX: Upgraded horizontal `[ \t]+` constraints to vertical `[ \t\n]+`.
            # =====================================================================
            # BUG FIX: Expanded to support 3 levels of nesting to handle deeply nested default values.
            # BUG FIX: Expanded name character set to include -, !, ?
            r"^[ \t]*proc[ \t\n]+[a-zA-Z0-9_:\-!?]+[ \t\n]+\{((?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*)\}",
            re.M,
        ),
        # Tcl default-value argument lists (#1512): opt-in for depth-aware braced parameter parsing.
        "_args_tcl_pattern_list_groups": {1},
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: global/upvar (globals/heat).
        "structural_boundaries": re.compile(r"\b(?:proc|return|break|continue|namespace|variable|yield)\b"),
        # 4. func_start (Executable Logic Anchors)
        # MUST HAVE EXACTLY ONE CAPTURE GROUP.
        # Captures standard procs and namespaced procs (e.g., `proc ::my::func`).
        # BUG FIX: Expanded name character set to include -, !, ?
        "func_start": re.compile(
            r"^[ \t]*proc[ \t\n]+([a-zA-Z0-9_:\-!?]+)(?:[ \t\n]+\{(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*\})?(?=[ \t\n]*\{|[ \t\n]|$)",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Captures TclOO, Snit, and Itcl class definitions.
        # BUG FIX: Expanded name character set to include -, !, ?
        "class_start": re.compile(
            r"^[ \t]*(?:oo::class[ \t\n]+create|snit::type|itcl::class)[ \t\n]+([a-zA-Z0-9_:\-!?]+)(?=[ \t]*\{|[ \t\n]|$)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Safe evaluation and error catching.
        "safety": re.compile(r"\b(?:catch|try|trap|finally|info[ \t]+exists|assert)\b"),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Unrestricted evaluation and context manipulation.
        "safety_bypasses": re.compile(r"\b(?:eval|uplevel|upvar)\b"),
        # 8. danger (High-Risk Execution / System Calls)
        # OS command execution and process termination.
        "high_risk_execution": re.compile(r"\b(?:exec|exit)\b|file[ \t]+delete[ \t]+-force"),
        # 9. io (I/O & Network Boundaries)
        # File system, sockets, and configuration. (Excludes puts which is mapped to print_hits).
        "io": re.compile(r"\b(?:open|close|read|gets|socket|fconfigure|file|source|vfs::)\b"),
        # 10. api (Public Surface Area)
        # Exposing packages or namespace exports.
        "api": re.compile(r"^[ \t]*(?:package[ \t]+provide|namespace[ \t]+export)\b", re.M),
        # 11. flux (State Mutation)
        # Variable state mutations.
        "state_mutation": re.compile(
            r"\b(?:set|lappend|dict[ \t]+set|array[ \t]+set|incr|append)\b[ \t]+[a-zA-Z0-9_:]+"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented out structural code.
        "dead_code": re.compile(r"^[ \t]*#[ \t]*(?:proc|set|if|while|foreach|return)\b", re.M),
        # 13. doc (Structured Documentation)
        # Tcl doc blocks.
        "doc": re.compile(r"^[ \t]*#[ \t]*@(?:param|return|brief|author)", re.M),
        # 14. test (Testing & Assertions)
        # *THE SQLITE MEGA-SENSOR*: Accurately maps the SQLite custom test harnesses alongside standard tcltest.
        "test": re.compile(
            r"\b(?:do_test|do_execsql_test|do_catchsql_test|do_eqp_test|do_ioerr_test|do_faultsim_test|test\s+[a-zA-Z0-9_-]+|tcltest::|finish_test)\b"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # Event loops, delays, and threads.
        "concurrency": re.compile(r"\b(?:vwait|after|thread::|coroutine|yield)\b"),
        # 16. ui_framework (UI / View Components)
        # Tkinter/Tk graphical elements.
        "ui_framework": re.compile(r"\b(?:button|pack|grid|place|canvas|frame|label|ttk::)\b"),
        # 17. closures (Closures / Anonymous Functions)
        # Tcl 8.6 anonymous functions.
        "closures": re.compile(r"\bapply[ \t]+\{"),
        # 18. globals (Global / Shared State)
        # Tcl relies heavily on global imports and environment arrays.
        # BUG FIX: `::env` starts with `::` (non-word) inside the
        # shared `\b(...)\b` group. Real usage (`$::env(HOME)`) always
        # precedes it with `$`, also non-word -- `\b` between two
        # non-word chars can never fire, so `::env` never matched.
        # Pulled out with no leading `\b` (self-delimiting on `::`).
        "globals": re.compile(r"\bglobal\b|::env\b|upvar[ \t]+#0"),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions
        # Tcl 8.6 list map.
        "comprehensions": re.compile(r"\blmap\b"),
        # 22. scientific (Numerical / Compute Libraries)
        # Explicit math invocations via expr.
        "scientific": re.compile(r"\b(?:expr|math::)\b|\b(?:sin|cos|tan|sqrt|exp|log|pow)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # High Cognitive Load: Intercepting variables, tracking execution, and runtime aliasing.
        "reflection_metaprogramming": re.compile(r"\b(?:trace[ \t]+add|rename|interp[ \t]+create|interp[ \t]+alias)\b"),
        # 24. import (Dependency Inclusions)
        # Package and module loading.
        "import": re.compile(r"^[ \t]*(?:package[ \t]+require|source|load)\b", re.M),
        "dependency_injection": None,
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:package[ \t\n]+require|source|load)[ \t\n]+(?:-exact[ \t\n]+)?(?:\{?[\"']?)([^\"'\s#{}]+)",
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"^[ \t]*#[ \t]*(?:Author|Created by|Maintainer|Copyright):\s+(.*)",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # BUG FIX: confirmed O(n^2) ReDoS -- the SPEC alternative's
        # unbounded `\d+` sits directly adjacent to the also-unbounded
        # `[^\]]*`, whose charset fully overlaps digits. Same bug shape
        # already found and fixed in embedded_python's and css's
        # independent copies of this pattern. Measured ~4x runtime per
        # doubling. Bounded `\d+` to `\d{1,10}` and `[^\]]*` to
        # `{0,300}`.
        "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Tcl event bindings and file event handlers.
        "events": re.compile(r"\b(?:bind|fileevent|vwait|trace[ \t]+add)\b"),
        "macros": None,
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(r"\b(?:log::log|logger::|syslog)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\bputs\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"\bexpr[ \t]+(?:int|double|wide)\("),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(?:error|exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\bafter[ \t]+[0-9]+\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~|<<|>>"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(?:thread::mutex|thread::rwmutex|thread::cond)\b"),
        # 45. immutability_locks (Immutability Constraints)
        # Tcl lacks `const`, but setting a trace to prevent writes is the Tcl idiom for freezing.
        "immutability_locks": re.compile(r"\btrace[ \t]+add[ \t]+variable[ \t]+[a-zA-Z0-9_:]+[ \t]+write\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r'\b(?:close|unset)\b|rename[ \t]+[a-zA-Z0-9_:]+[ \t]+""'),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Internal namespaces and private `_` prefixed procs.
        "encapsulation": re.compile(r"\bnamespace[ \t]+eval\b|^[ \t]*proc[ \t]+_[a-zA-Z0-9_:]+", re.M),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(?:bind|fileevent)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # Using TclTest constraints to silently skip tests on certain OS environments.
        "test_skip": re.compile(r"-constraints[ \t]+[a-zA-Z0-9_]+\b|\btestConstraint\b"),
    },
}
