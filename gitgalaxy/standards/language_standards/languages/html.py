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
    _HTML_NONEXECUTABLE_SCRIPT_TYPES,
    GLOBAL_FRAGILE_DEBT,
    GLOBAL_PLANNED_DEBT,
)

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Modern HTML Living Standard (2025) & Web Components",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard markup, XML-based HTML, and modern JS/server-side UI component frameworks.
    "extensions": [
        ".html",
        ".htm",
        ".xhtml",
        ".cshtml",
        ".vue",
        ".svelte",
        ".astro",
        ".ejs",
        ".hbs",
        ".twig",
        ".erb",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Standardized routing and entry points.
    "exact_matches": ["index.html", "404.html"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and frontend build tools to prove context.
    "discriminators": [
        ".html",
        "package.json",
        "vite.config.js",
        "webpack.config.js",
        "nuxt.config.js",
    ],
    # EXECUTION SIGNATURES: HTML is a declarative markup language; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 8 (Singular/Unique)
    # Rationale: Uses SGML-style block delimiters () exclusively; no single-line anchor.
    "lexical_family": "block_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # User-driven branching and declarative framework conditionals.
        # BUG FIX: `*ngIf` was inside the shared `\b(...)"[^"]*"` group.
        # `*` is a non-word char always preceded by whitespace in real
        # markup (`<div *ngIf="cond">`) -- a `\b` between two non-word
        # characters can never fire, so Angular's structural directive
        # never matched. Pulled out with no leading `\b` (self-delimiting).
        # BUG FIX (#735): every `"[^"]*"`-shaped attribute-value pattern
        # in this rules dict assumed double-quoted HTML attributes only
        # -- `<div v-if='cond'>` (single-quoted, equally valid HTML)
        # never matched. Swapped the literal `"` delimiters for a
        # `["\']` quote-character class and widened the wildcard
        # content class to `[^"\']` (excludes either quote char) --
        # the same idiom this file's own `_dependency_capture` already
        # uses. No ReDoS risk added: still exactly one unbounded
        # quantifier per gap, just a wider character class.
        "branch": re.compile(
            r"<(?:details|summary|noscript)(?=[ \t\n\r\f/>])|\b(?:v-if|ng-if|x-if|hx-swap)=(?:\"[^\"]*\"|'[^']*')|\*ngIf=(?:\"[^\"]*\"|'[^']*')|\{%\s*(?:if|elif|else|endif)\s*[^%]*%\}|\{\{#if\s+[^}]+\}\}",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Attribute signatures defining input coupling. Bounded to prevent ReDoS on massive data attrs.
        "args": re.compile(
            r"\b(data-[a-zA-Z0-9_-]+|aria-[a-z]+|name|value|placeholder|for|alt|step|min|max)(?:[ \t\n\r\f]*=[ \t\n\r\f]*(?:\"[^\"]*\"|'[^']*'|[^ \t\n\r\f>\"']+))?",
            re.IGNORECASE,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural document flow tags. Includes 1990 CERN tags (<nextid>, <address>) alongside modern semantic ones.
        "structural_boundaries": re.compile(
            r"<(?:html|head|body|main|section|article|header|footer|div|span|p|h[1-6]|ul|ol|li|dl|dt|dd|nav|aside|figure|figcaption|search|address|nextid|hp[1-2]|dir|menu)(?=[ \t\n\r\f/>])",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable behavior blocks. The negative lookahead (Rule 15)
        # excludes a `<script>` whose `type` is a non-executable value -- a
        # browser treats any `type` outside the JS-MIME / `module` set as an
        # inert data block and never runs it (#2492). This lookahead gates the
        # raw structural-signal count (matched against un-shielded source);
        # detector.py's Mode B slicer re-applies HTML_NONEXECUTABLE_SCRIPT_TAG
        # against raw source for the named-function list, because the shared
        # brace-safe stream has blanked the `type` value by the time this
        # regex runs there.
        "func_start": re.compile(
            r"<(script|style)"
            r"(?![^>]*\btype[ \t\n\r\f]*=[ \t\n\r\f]*[\"']?(?:" + _HTML_NONEXECUTABLE_SCRIPT_TYPES + r"))"
            r"(?=[ \t\n\r\f/>])",
            re.IGNORECASE,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Defines structural entities, Web Components, and template boundaries.
        "class_start": re.compile(
            r"<(form|table|svg|canvas|picture|video|audio|dialog|template|fieldset|legend|[a-z][a-z0-9]*-[a-z0-9-]+)(?=[ \t\n\r\f/>])",
            re.IGNORECASE,
        ),
        # --- PHASE 2: RISK ENGINE (Structural Integrity & Debt) ---
        # 6. safety (Defensive Programming / Validation)
        # Browser security and validation constraints.
        # BUG FIX: `pattern="..."`/`sandbox="..."`/`rel="noopener..."`/
        # `integrity="..."` were inside the shared `\b(...)\b` group.
        # Each ends on a literal `"`, and the char immediately after a
        # closing attribute quote (a space or `>`) is also non-word --
        # `\b` between two non-word characters can never fire, so all
        # four never matched. Pulled out with no trailing `\b`
        # (self-delimiting on the closing quote).
        "safety": re.compile(
            r"\b(?:required|readonly|disabled)\b|pattern=(?:\"[^\"]*\"|'[^']*')|sandbox=(?:\"[^\"]*\"|'[^']*')|rel=(?:\"noopener(?: noreferrer)?\"|'noopener(?: noreferrer)?')"
            r"|integrity=(?:\"[^\"]*\"|'[^']*')|<meta\s+http-equiv=(?:\"Content-Security-Policy\"|'Content-Security-Policy')",
            re.I,
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Actively bypasses standard browser safety (e.g. target="_blank" without noopener).
        "safety_bypasses": re.compile(
            r"target=(?:\"_blank\"|'_blank')(?!\s+rel=(?:\"noopener\"|'noopener'))|href=(?:\"javascript:[^\"]*\"|'javascript:[^']*')|on[a-z]+=(?:\"[^\"]*(?:eval\(|document\.write\()|'[^']*(?:eval\(|document\.write\()')",
            re.I,
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # HTML is declarative markup. Execution dangers (eval, setTimeout) belong in JS.
        "high_risk_execution": None,
        # 9. io (I/O & Network Boundaries)
        # Hyperlink navigation and resource fetching. (The core of the Web).
        "io": re.compile(
            r"\b(?:src|href|action|poster|data)=(?:\"[^\"]*\"|'[^']*')|<(?:a|form|iframe|audio|video|object|embed|source|track|img)(?=[ \t\n\r\f/>])",
            re.I,
        ),
        # 10. api (Public Surface Area)
        # Exposed identifiers and metadata consumption surface.
        "api": re.compile(
            r"\b(?:id|name|role|exportparts|part|itemprop|itemscope|itemtype)=(?:\"[^\"]*\"|'[^']*')|<slot(?=[ \t\n\r\f/>])|<meta\s+(?:property=(?:\"og:|'og:)|name=(?:\"twitter:|'twitter:))",
            re.I,
        ),
        # 11. flux (State Mutation)
        # HTML is declarative markup. State mutation (DOM manipulation) belongs in JS.
        "state_mutation": None,
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented-out structural logic.
        "dead_code": re.compile(
            r"<!--[ \t]*<(?:div|script|style|form|table|a|p|section|span|img|ul|li|nav|header|footer|main)(?=[ \t\n\r\f/>])",
            re.I,
        ),
        # 13. doc (Structured Documentation)
        # Structured intent for crawlers and accessibility.
        "doc": re.compile(
            r"<title>[^<]*</title>|<meta\s+name=(?:\"(?:description|keywords|author)\"|'(?:description|keywords|author)')\s+content=(?:\"[^\"]*\"|'[^']*')|\baria-(?:description|label|labelledby|describedby|details)=(?:\"[^\"]*\"|'[^']*')",
            re.I,
        ),
        # 14. test (Testing & Assertions)
        "test": re.compile(r"\bdata-(?:testid|cy|test|test-id|qa)[ \t]*=", re.I),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # Prioritization and asynchronous fetching logic.
        # BUG FIX: same trailing-`\b`-after-quote trap as `safety` above --
        # `loading="lazy"`/`fetchpriority="..."`/`decoding="async"` all end
        # on `"`, and the shared trailing `\b` can't fire against the
        # non-word char that follows a closing attribute quote. Pulled out.
        "concurrency": re.compile(
            r"\b(?:async|defer)\b|loading=(?:\"lazy\"|'lazy')|fetchpriority=(?:\"(?:high|low)\"|'(?:high|low)')|decoding=(?:\"async\"|'async')"
            r"|<link\s+rel=(?:\"(?:preload|prefetch|preconnect|modulepreload|prerender)\"|'(?:preload|prefetch|preconnect|modulepreload|prerender)')",
            re.I,
        ),
        # 16. ui_framework (UI / View Components)
        # Formatting tags and Tailwind/Bootstrap utility density.
        "ui_framework": re.compile(
            r"<(?:b|i|u|strong|em|mark|small|del|ins|sub|sup)(?=[ \t\n\r\f/>])|\bclass=(?:\"[^\"]*(?:flex|grid|absolute|relative|block|inline-block|container|row|col-[0-9]+|justify-center|items-center|w-full|h-full)[^\"]*\"|'[^']*(?:flex|grid|absolute|relative|block|inline-block|container|row|col-[0-9]+|justify-center|items-center|w-full|h-full)[^']*')",
            re.I,
        ),
        # 17. closures (Closures / Anonymous Functions)
        # DOM encapsulation via Shadow DOM.
        "closures": re.compile(
            r"<template\s+shadowrootmode=(?:\"[^\"]*\"|'[^']*')>|<template\s+shadowroot=(?:\"[^\"]*\"|'[^']*')>",
            re.I,
        ),
        # 18. globals (Global / Shared State)
        # HTML is declarative markup. Browser globals (window, document) belong in JS.
        "globals": None,
        # 19. decorators (Decorators / Annotations)
        # Directive-based logic mutation (HTMX, Vue, Alpine).
        # BUG FIX: `hidden`/`inert` are true HTML boolean attributes,
        # almost always written bare (`<div hidden>`) with no `=` at
        # all -- the old pattern required `[ \t]*=` unconditionally
        # after every alternative, so the dominant real-world form of
        # these two never matched. Made the `=...` suffix optional only
        # for hidden/inert; the rest (class/style/tabindex/etc.) always
        # require an explicit value in real markup, so they keep the
        # mandatory `=`.
        "decorators": re.compile(
            r"\b(?:hidden|inert)\b(?:[ \t]*=)?"
            r"|\b(?:class|style|tabindex|draggable|spellcheck|dir|lang|translate)[ \t]*="
            r"|hx-[a-z-]+=(?:\"[^\"]*\"|'[^']*')|x-[a-z-]+=(?:\"[^\"]*\"|'[^']*')|v-[a-z-]+=(?:\"[^\"]*\"|'[^']*')",
            re.I,
        ),
        "generics": re.compile(r"<slot(?=[ \t\n\r\f/>])[^>]*>", re.I),
        # 21. comprehensions (Iterators / Comprehensions)
        # Declarative array iteration in markup.
        # BUG FIX: same leading-`\b`-before-`*` trap as `branch` above --
        # `*ngFor` is always preceded by whitespace in real markup, so
        # the shared leading `\b` (boundary between two non-word chars)
        # never fired. Pulled out with no leading `\b`.
        "comprehensions": re.compile(
            r"\b(?:v-for|ng-repeat|x-for)=(?:\"[^\"]*\"|'[^']*')|\*ngFor=(?:\"[^\"]*\"|'[^']*')|\{%\s*for\b[^%]*%\}|\{\{#each\b[^}]*\}\}",
            re.I,
        ),
        # 22. scientific (Numerical / Compute Libraries)
        # MathML and SVG path math.
        "scientific": re.compile(
            r'<(?:math|mfrac|mi|mo|svg|canvas|path|circle|rect|polygon|polyline)(?=[ \t\n\r\f/>])|\bd=(?:"[MmLlHhVvCcSsQqTtAaZz0-9\s,.-]+"|\'[MmLlHhVvCcSsQqTtAaZz0-9\s,.-]+\')',
            re.I,
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Extreme logic heat: heavy inline styles and JS pollution.
        # BUG FIX: `style="[^"]*;"` required a literal trailing `;`
        # immediately before the closing quote. CSS allows omitting the
        # last declaration's semicolon, and most real inline styles
        # (hand-written or minified) don't carry one -- confirmed
        # `style="color:red"` and `style="color:red;font-size:12px"`
        # (multi-declaration, no trailing `;`) never matched under the
        # old pattern. Dropped the semicolon requirement; presence of
        # any inline style attribute is the actual intent here.
        "reflection_metaprogramming": re.compile(
            r"style=(?:\"[^\"]*\"|'[^']*')|\bon[a-z]+=(?:\"[^\"]*\"|'[^']*')", re.I
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(
            r"<script\s+type=(?:\"(?:importmap|module)\"|'(?:importmap|module)')|<link\s+(?:rel=(?:\"stylesheet\"|'stylesheet')|rev=(?:\"[^\"]*\"|'[^']*'))",
            re.I,
        ),
        "_dependency_capture": re.compile(
            r'<(?:script(?=[ \t\n\r\f/>])[^>]*?\bsrc|link(?=[ \t\n\r\f/>])[^>]*?\bhref)[ \t\n\r\f]*=[ \t\n\r\f]*(?:"([^"]*)"|\'([^\']*)\'|([^ \t\n\r\f>"\']+))',
            re.IGNORECASE,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"<meta\s+name=(?:\"(?:author|creator|publisher)\"|'(?:author|creator|publisher)')\s+content=(?:\"([^\"]+)\"|'([^']+)')|<link\s+rev=(?:\"made\"|'made')\s+href=(?:\"mailto:[^\"]+\"|'mailto:[^']+')",
            re.I,
        ),
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
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit|RFC|W3C|CERN|TBL)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        # Back-end template engine hydration.
        "ssr_boundaries": re.compile(
            r"<\?php|<%|<%=|\{\{\s*[^}]+\s*\}\}|\{%\s*[^%]+\s*%\}|\b(?:data-reactroot|data-server-rendered|ng-version|nuxt-ssr)=[\"'][^\"']*[\"']",
            re.I,
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # Declarative event dispatchers.
        "events": re.compile(
            r"\bhx-trigger=[\"'][^\"']*[\"']|@[a-z]+=[\"'][^\"']*[\"']|v-on:[a-z]+=[\"'][^\"']*[\"']|\([a-z]+\)=[\"'][^\"']*[\"']",
            re.I,
        ),
        # 33. dependency_injection (Dependency Injection / IoC)
        # BUG FIX: trailing `\b` right after the closing `"` -- same
        # shared-boundary trap as safety/concurrency above (the char
        # after a closing attribute quote is never a word char), so
        # this never matched at all. Self-delimiting on the quote.
        "dependency_injection": re.compile(r"<script\s+type=[\"']importmap[\"']", re.I),
        # 34. macros (Preprocessor Directives / Macros)
        # Server Side Includes (SSI).
        "macros": re.compile(r"<!--#\s*(?:include|exec|echo|config|if|else|endif)\b", re.I),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Fragment identifiers and original name pointers.
        "pointers": None,
        # 36. memory_alloc
        "memory_alloc": None,
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        # Professional analytics trackers.
        "telemetry": re.compile(
            r"<script[^>]*src=[\"'][^\"']*(?:analytics|gtag|gtm|segment|plausible|mixpanel)[^\"']*[\"']|\bdata-layer\b|\bnavigator\.sendBeacon\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        # Ad-hoc debug statements in scripts.
        "debug_prints": re.compile(
            r"\b(?:document\.write|alert|confirm|prompt|console\.(?:log|error|warn|dir|trace|info))\s*\(",
            re.I,
        ),
        # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": None,
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(?:process\.exit|history\.back|window\.close)\s*\(", re.I),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(?:setTimeout|setInterval)\s*\(", re.I),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": None,
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": None,
        # 45. immutability_locks (Immutability Constraints)
        # BUG FIX: `aria-disabled="true"` ended on `"`, inside the same
        # shared trailing-`\b` trap as safety/concurrency above. It
        # happened to still match in practice only because "disabled" is
        # a substring of "aria-disabled" and self-heals via the bare
        # `disabled` alternative (matching regardless of the actual
        # true/false value, which was never the intent) -- pulled out so
        # the match is for the right reason.
        "immutability_locks": re.compile(r"\b(?:readonly|disabled|inert)\b|aria-disabled=[\"']true[\"']", re.I),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(
            r'\b(?:removeEventListener|clearInterval|clearTimeout|remove|innerHTML\s*=\s*[\'"][\'"])\s*\(',
            re.I,
        ),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Declarative and Shadow DOM boundaries.
        "encapsulation": re.compile(r"<(?:template|shadowrootmode|slot)\b", re.I),
        # 48. listeners (Event Listeners / Observers)
        # Event sinks waiting for state broadcast.
        "listeners": re.compile(r"\bhx-trigger|v-on:|@[a-z]+=|addEventListener|on[a-z]+=", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(?:data-skip|data-ignore|mock-data|test-skip)\b", re.I),
    },
}
