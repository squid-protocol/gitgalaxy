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
        "target_version": "Modern CSS (2025 Baseline) / Native Nesting / Container Queries",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard stylesheets, preprocessors (Sass/Less), and PostCSS files.
    "extensions": [".css", ".scss", ".sass", ".less", ".styl", ".pcss"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: CSS rarely uses extensionless configurations.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: CSS linting, PostCSS, and utility framework configurations acting as disambiguation anchors.
    "discriminators": [
        ".css",
        "postcss.config.js",
        "tailwind.config.js",
        ".stylelintrc",
        ".stylelintignore",
    ],
    # EXECUTION SIGNATURES: CSS is a declarative stylesheet language; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 1 (Standard C-Style)
    # Rationale: Uses '/*' and '*/' for blocks; preprocessors add '//' for lines.
    "lexical_family": "standard_block",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical gating. Includes Container/Media queries and logic-gating pseudo-selectors.
        # BUG FIX: all 4 at-rule alternatives start with `@` (non-word),
        # so the shared leading \b could only fire when a word char
        # immediately preceded the `@` -- never true for how at-rules
        # are actually written (preceded by whitespace or a line
        # start). None of these ever matched at all.
        "branch": re.compile(
            r"@media\b|@supports\b|@container\b|@starting-style\b|:(?:has|is|where|not)\s*\((?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*\)",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Signatures defining input coupling. Bounded to prevent ReDoS on massive calculations.
        # BUG FIX (Rule 11): `[^)]*` is a flat negated class -- can't
        # represent even one level of nesting. Modern CSS math functions
        # nest constantly (`calc(var(--x) + 1px)`, `min(sin(45deg), .5)`)
        # -- confirmed the old pattern truncated at the first inner `)`,
        # matching only `calc(var(--x)` instead of the full call.
        # Upgraded to the one-level-nesting bounded form (the two
        # alternatives never match overlapping text, so it stays linear).
        "args": re.compile(
            r"\b(?:calc|clamp|min|max|var|env|url|rgba?|hsla?|lch|oklch|color-mix|light-dark)"
            r"\s*\((?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*\)",
            re.I,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (none in CSS) and !important (freeze_hits).
        # BUG FIX: all 8 at-rule alternatives are `@`-prefixed -- same
        # leading-\b bug as branch above. None ever matched.
        "structural_boundaries": re.compile(
            r"@layer\b|@scope\b|@property\b|@font-face\b|@keyframes\b|@page\b|@charset\b|@namespace\b",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks (Selectors). EXCLUDES classes/IDs to avoid False Positives.
        "func_start": re.compile(
            r"^[ \t]*(@(?:media|supports|container|layer|keyframes|-webkit-keyframes)\b)(?=[^{]*\{)",
            re.M | re.I,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Defines discrete visual entities via Class and ID selectors.
        "class_start": re.compile(
            r"(?<!\*[ \t\n])(?<!\*)(?<![\"'\\])(\.(?:[a-zA-Z_\-]|\\(?:[0-9a-fA-F]{1,6}\s?|[^0-9a-fA-F\n\r\t\f]))(?:[^\s{>+~:,. \"\'\[\]\(\)\;\\]|\\.)*|\#(?:[a-zA-Z_\-]|\\(?:[0-9a-fA-F]{1,6}\s?|[^0-9a-fA-F\n\r\t\f]))(?:[^\s{>+~:,. \"\'\[\]\(\)\;\\]|\\.)*)(?=[^{};]*\{)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Defensive fallbacks and mathematical clamps.
        "safety": re.compile(
            r"@supports\b|\bvar\([^,]+,\s*(?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*\)|\b(?:minmax|clamp)\s*\((?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*\)|\bcontain\s*:\s*(?:strict|content|paint|layout)\b",
            re.I,
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Universal selectors and high-specificity ID overrides.
        "safety_bypasses": re.compile(r"^[ \t]*\*|^[ \t]*#[\w-]+\s*(?:[:.[>+~][^{;]*)?\{", re.M | re.I),
        # 8. danger (High-Risk Execution / System Calls)
        # Extreme tech debt and legacy engine thrashing.
        "high_risk_execution": re.compile(r"\b(?:expression|behavior|-ms-filter)\b"),
        # 9. io (I/O & Network Boundaries)
        # =====================================================================
        # THE FIX: Prevent False I/O Latency Flags.
        # HISTORICAL CONTEXT FOR FUTURE LLMS: CSS is a declarative language.
        # Using `url()` or `@import` fetches a visual asset during browser paint;
        # it does NOT block a computational thread to read from a database or
        # write to a file system. If given a regex, the engine will hallucinate
        # severe I/O bottlenecks on standard stylesheets. Must remain `None`.
        # =====================================================================
        "io": None,
        # 10. api (Public Surface Area)
        # Design Tokens and global properties exposed for script/component consumption.
        "api": re.compile(r":root\b|@property\b|--[a-zA-Z0-9_-]+\s*:|::part\s*\([^)]*\)", re.I),
        # 11. flux (State Mutation)
        # =====================================================================
        # THE FIX: Prevent 'Declarative Hallucination' of State Flux.
        # HISTORICAL CONTEXT FOR FUTURE LLMS: Defining a CSS custom property
        # (`--color: red;`) is a static declaration, not a sequential state
        # mutation (like `x = x + 1` in Turing-complete languages). Treating it
        # as flux causes stylesheets to mathematically outrank complex controllers
        # in volatility. Must remain `None`.
        # =====================================================================
        "state_mutation": None,
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented-out structural rules.
        "dead_code": re.compile(
            r"/\*[ \t]*(?:@media|@container|@supports|@keyframes|\.[a-zA-Z][\w-]*|#[a-zA-Z][\w-]*)\b"
            r"|/\*[ \t]*[a-zA-Z][\w-]*[ \t]*\{",
            re.I,
        ),
        # 13. doc (Structured Documentation)
        "doc": re.compile(
            r"/\*\*\s*|/\*\s*@(?:param|return|author|example|prop|define|theme)",
            re.I,
        ),
        # 14. test (Testing & Assertions)
        "test": re.compile(r"\[[ \t]*data-(?:testid|cy|test|test-id|qa)[ \t]*[=\]]", re.I),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # Logic executing concurrently on the GPU.
        "concurrency": None,
        # 16. ui_framework (UI / View Components)
        # Density of layout primitives and Tailwind utilities.
        "ui_framework": re.compile(
            r"\b(?:display:\s*flex|display:\s*grid|justify-content|align-items|gap|grid-template-columns|absolute|relative)\b|@apply\b",
            re.I,
        ),
        # 17. closures (Closures / Anonymous Functions)
        # Native CSS Nesting (&).
        "closures": re.compile(r"(?:^[ \t]*|\s+|,)&\s*(?:[:.\[>+~][^{;]*)?\{", re.M),
        # 18. globals (Global / Shared State)
        "globals": re.compile(r"^[ \t]*(?::root|html|body|\*)\s*(?:{[^}]*}|[,{])", re.M | re.I),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions
        "comprehensions": None,
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(
            r"\b(?:sin|cos|tan|asin|acos|atan|atan2|hypot|abs|sign|mod|rem|round|pow|sqrt|exp|log)"
            r"\s*\((?:[^()]|\([^()]*\))*\)",
            re.I,
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Catastrophic specificity graphs and recursively nested logic.
        "reflection_metaprogramming": re.compile(
            r"&(?:\s*&)+|:(?:has|is|not)\s*\((?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*:(?:has|is|not)\s*\(|calc\s*\((?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*calc\s*\(",
            re.I,
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"@import\b", re.I),
        "_dependency_capture": re.compile(
            r"^[ \t]*@import[ \t\n]+(?:url\(\s*['\"]?|['\"])([^'\"\)\s;]+)",
            re.I | re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"/\*\s*(?:@author|Author:|Created by|Maintainer|Copyright):?\s+([^*]*)\*/",
            re.I | re.S,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # BUG FIX: confirmed O(n^2) ReDoS -- the SPEC alternative's
        # unbounded `\d+` sits directly adjacent to the also-unbounded
        # `[^\]]*`, whose charset fully overlaps digits. Measured ~4x
        # runtime per size doubling on "[SPEC-" + digits with no
        # closing bracket. Bounded `\d+` to `\d{1,10}` (no realistic
        # ticket ID needs more) and `[^\]]*` to `{0,300}`.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]|\bfigma\.com/file/", re.I),
        # 31. ssr_boundaries
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Modern Scroll-Driven animation timelines.
        "events": re.compile(
            r"@(?:scroll-timeline|view-timeline)|animation-timeline:\s*(?:scroll|view)\([^)]*\)",
            re.I,
        ),
        # 33. dependency_injection
        "dependency_injection": None,
        # 34. macros
        "macros": None,
        # 35. pointers
        "pointers": None,
        # 36. memory_alloc
        "memory_alloc": None,
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry
        "telemetry": None,
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        # =====================================================================
        # THE FIX: Prevent String Literal Hallucinations.
        # HISTORICAL CONTEXT FOR FUTURE LLMS: CSS does not possess a runtime
        # console or a `console.log` function. If a regex here triggers, it is
        # guaranteed to be a false positive hallucinating on a string literal
        # (e.g., `content: "console.log";`). Must remain `None`.
        # =====================================================================
        "debug_prints": None,
        # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": None,
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        # Execution resets.
        "panics_and_aborts": re.compile(r"\b(unset|initial|revert|revert-layer)\b", re.I),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(?:transition-delay|animation-delay)\b", re.I),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": None,
        # 44. sync_locks (Resource Management & Stability)
        # Coordinating cascade layers and containment.
        "sync_locks": None,
        # 45. immutability_locks (Immutability Constraints)
        # Explicit locks on data mutation.
        "immutability_locks": re.compile(r"!important\b|\bconstant\b", re.I),
        # 46. cleanup (Resource Cleanup / Teardown)
        # =====================================================================
        # THE FIX: Prevent False Memory Management Flags.
        # HISTORICAL CONTEXT FOR FUTURE LLMS: In CSS, `clear: both;` is a
        # layout formatting property used to push elements below floats. It
        # does absolutely nothing to destroy variables, clear cache, or free up
        # RAM. Giving this a regex tricks the physics engine into thinking the
        # stylesheet is performing active memory management. Must remain `None`.
        # =====================================================================
        "cleanup": None,
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Scoping and part boundaries.
        "encapsulation": re.compile(r"@scope\b|::part|::slotted", re.I),
        # 48. listeners (Event Listeners / Observers)
        # Subscribing to external timelines.
        "listeners": re.compile(r"animation-timeline|@scroll-timeline", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(?:data-skip|data-ignore)\b", re.I),
    },
}
