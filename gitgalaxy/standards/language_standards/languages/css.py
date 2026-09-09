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
        # =====================================================================
        # A STATED ABSENCE (#2893). The `args` contract is "the parameters a
        # callable declares". CSS declares no callable, so it declares no
        # parameter surface: every parenthesis in a stylesheet is a CALL into a
        # builtin. Count contract corollary 3 -- a language that cannot express
        # the construct records "a contract-level absence (`None` rule + a
        # ledgered `intended-morphology` entry) rather than a manufactured
        # construct. The two answers cannot coexist inside one signal." Same
        # answer solidity's `io: None` records (docs/io_rule_contract.md C3).
        #
        # HISTORICAL CONTEXT FOR FUTURE LLMS: this matched CSS value-function
        # calls -- calc|clamp|min|max|var|env|url|rgba?|hsla?|lch|oklch|
        # color-mix|light-dark. docs/args_rule_contract.md called that "the one
        # place in this document where the contract is deliberately not met",
        # kept because "the honest alternatives are this approximation or 0
        # forever, and 0 says a stylesheet full of computed values has no
        # coupling at all". Both halves of that were wrong by 2026-09-08:
        #   1. The third alternative is None, not 0, and None is not scored.
        #   2. A stylesheet's coupling IS measured, by the rules that own it.
        #      Of the 3855 hits this rule made on the crucible's 38 css files
        #      (code stream, the text detector.py actually hands the rule):
        #      2521 `var(` reads, 931 colour literals (rgba/rgb/oklch -- never
        #      coupling), 321 `calc(` (226 of them already containing a
        #      `var()`), 77 `url(` and 5 `clamp(`/`min(`. Meanwhile `api` counts
        #      3597 `--custom-property:` DECLARATIONS (the definitions those
        #      `var()`s read, a larger surface than the reads), `safety` counts
        #      512 guarded `var(x, fallback)` reads plus `clamp()`, `io` counts
        #      the 14 real url() fetches (#2752) and `reflection_metaprogramming`
        #      the 24 nested `calc(`.
        # It was also wrong twice per file: css gets no `args_search_text`, so
        # `_calculate_block_metrics` searched the whole block BODY and took the
        # first match -- 6 at-rules carried 13 phantom parameters borrowed from
        # their own bodies (preflight.css:291's `@supports` read arity 3 off a
        # `color-mix()` on line 294). tree-sitter reads 0 for all 25; this takes
        # `args_exact_match` from 19/25 to 25/25.
        #
        # THE NAMED RESIDUAL: the UNGUARDED `var(--x)` read (2521 - 512 = 2009
        # crucible occurrences) is now unmeasured. Deliberate -- no stated
        # contract owns "reads a document-lifetime binding by name" (the globals
        # contract's C2 excludes an ordinary read), and inventing one to keep the
        # number is the failure this change exists to end. It earns its own
        # signal or it stays unmeasured.
        #
        # REOPEN CONDITION: `extensions` above claims .scss/.sass/.less/.styl/
        # .pcss, and Sass/Less DO declare parameters -- `@mixin b($size, $color)`,
        # `@function f($a, $b)`, Less `.mixin(@a; @b)`. Those are real declared
        # parameter surfaces and this absence does NOT cover them. It stands only
        # because there are zero .scss/.sass/.less files in the language-crucible
        # and zero in keyword-rosetta, so such a rule would be unmeasurable on
        # either corpus. If a preprocessor dialect enters the crucible, write the
        # declaration-form rule and retire this absence.
        # Corpus: keyword-rosetta `args-no-parameter-surface-morphology`.
        # =====================================================================
        "args": None,
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
        # #2866 contract: `@keyframes` is the one at-rule that declares a NAMED
        # unit the language reaches by that name (`animation-name: slide` /
        # `animation: slide 2s`), so its custom-ident is captured as the unit
        # name and the block joins the orphan census -- tailwind's theme.css
        # carries 4 keyframes nothing in the file animates, and that is a true
        # unreferenced-by-name reading. The other at-rules stay group-1 keyword
        # buckets, excluded by derivation (#2728). Same two-group shape as
        # yaml's #2767 rule: group 1 a bare literal alternation for
        # `_closed_literal_capture`, group 2 the open name capture; a
        # `@keyframes` with no ident (invalid CSS) simply stops matching.
        "func_start": re.compile(
            r"^[ \t]*(?:(@(?:media|supports|container|layer)\b)"
            r"|@(?:-webkit-)?keyframes[ \t]+([A-Za-z_-][\w-]*))(?=[^{]*\{)",
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
        # #2878 contract C2: the IE forms -- `expression(` as a value, `behavior:`/`-ms-filter:` as
        # the property; `scroll-behavior:`/`overscroll-behavior:` are ordinary properties.
        "high_risk_execution": re.compile(r"\bexpression\s*\(|(?<![-\w])(?:behavior|-ms-filter)\s*:"),
        # 9. io (I/O & Network Boundaries)
        # =====================================================================
        # A DECLARATION WHOSE VALUE FETCHES AN EXTERNAL RESOURCE (#2752).
        # HISTORICAL CONTEXT FOR FUTURE LLMS: this was `None` under the
        # rationale that a `url()`/`@import` fetch "happens during browser
        # paint and does not block a computational thread". That is true and
        # is NOT the deciding factor: html's own `io` rule counts `src=` /
        # `href=` / `<img>` / `<iframe>`, which are the same non-blocking,
        # paint-time loads, and counts them as I/O. A resource boundary is
        # what `io` measures; blocking-ness is not.
        #
        # Three exclusions carry the rest of the old caution, and each is
        # load-bearing (all three were measured against a quote-aware
        # oracle over 136 real stylesheets, 185 fetches, zero disagreement):
        #
        #  1. `@import` is NOT counted. The rule is anchored on a
        #     declaration's `:` (with `(?<=[-\w])` for the property name it
        #     terminates), and an at-rule prelude has no colon, so
        #     `@import url("a.css")` keeps exactly the two hits it has today
        #     (`import` + `_dependency_capture`) instead of a third. `@` is
        #     excluded from the value span so no earlier declaration's colon
        #     can bridge into an at-rule either. (keyword-rosetta ledger
        #     `css-import-url-io-triple-overlap`.)
        #  2. `url(data:...)` is NOT counted. A data URI is an inline
        #     payload, not a boundary -- nothing is fetched. This is the
        #     majority construct in the wild: 59 of language-crucible's 117
        #     `url(` tokens are data URIs, and only 18 are real fetches.
        #  3. `url(#fragment)` is NOT counted -- `clip-path: url(#mask)`
        #     references an element in the same document.
        #
        # `%` and `<>` are excluded from the value span for exclusion 2's
        # sake: a `data:image/svg+xml` payload is a whole SVG document
        # inlined as text, and it contains its own `url(#...)` references
        # plus `xmlns='http:`-shaped colons. Without that guard the scan
        # walks INTO the payload and hallucinates a fetch per embedded icon
        # (measured: 70 hits instead of 14 on the crucible corpus). Both the
        # percent-escaped (`%3Csvg`) and raw (`<svg`) inlining styles are
        # covered. Cost: a value that writes a percentage before its url
        # (`background: 50% 50% url(x.png)`) is missed -- zero occurrences
        # in the 136-file sample.
        #
        # Rule 14: the property name is a fixed-width LOOKBEHIND, not a
        # match. Spelling it `[-a-zA-Z_][-\w]*[ \t]*:` puts an unbounded
        # `[-\w]*` adjacent to a required `:`, and every identifier char in
        # the file becomes a start position that backtracks the whole run --
        # measured quadratic (1.3s / 5.5s / 13.5s / 54s over 10k-80k chars
        # of `background:aaaa...`). The lookbehind form is linear on the
        # same inputs (0.5 / 0.8 / 1.7 / 3.2 ms).
        # =====================================================================
        "io": re.compile(
            r"(?<=[-\w])[ \t]*:[^;{}@%<>]{0,200}?\burl\s*\((?!\s*['\"]?\s*(?:data:|#))",
            re.I,
        ),
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
        # #2882 contract C4: doc counts the block, not the author tag -- `/* @author` is ownership's alone.
        "doc": re.compile(
            r"/\*\*\s*|/\*\s*@(?:param|return|example|prop|define|theme)",
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
        # #2882 contract: C2 `Copyright` out; @author is ownership's (doc released it, C4); the `*/` is stripped from the value (C3)
        "ownership": re.compile(
            r"@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?:/\*+|\*+)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?-i:(?:Author|AUTHOR)(?:s|S)?|Created[ \t]+by|CREATED[ \t]+BY|Maintainer(?:s)?|MAINTAINER(?:S)?|Owner(?:s)?|OWNER(?:S)?|Developer(?:s)?|DEVELOPER(?:S)?|Contact|CONTACT)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)(?<![,;{(])[ \t]*(?:\*/|-->)?[ \t]*$",
            re.I | re.M,
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
        # #2766: contract-level absence. @scope/::part/::slotted are DOM/style
        # isolation boundaries, not markers excluding a NAME from a public surface;
        # css has no name-visibility construct.
        "encapsulation": None,
        # 48. listeners (Event Listeners / Observers)
        # Subscribing to external timelines.
        "listeners": re.compile(r"animation-timeline|@scroll-timeline", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(?:data-skip|data-ignore)\b", re.I),
    },
}
