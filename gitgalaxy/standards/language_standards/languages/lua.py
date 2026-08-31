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
        "target_version": "Lua 5.5 / Luau / LuaLS Annotations / LuaJIT",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard scripts, Luau (Roblox), Nmap Scripting Engine (.nse), and LuaRocks package specs (.rockspec).
    "extensions": [".lua", ".luau", ".nse", ".pd_lua", ".wlua", ".rockspec"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Tooling and documentation configurations that are secretly pure Lua code.
    "exact_matches": ["config.ld"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and linting configs to resolve ambiguous files.
    "discriminators": [".lua", ".luacheckrc", "stylua.toml", ".rockspec"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for CLI, Game-Engine, and embedded scripts.
    "shebangs": ["lua", "luajit", "luau", "texlua"],
    # Maps to Family 5 (Hybrid Dash) -- #621: this comment always said
    # "Family 5 (Hybrid Dash)" but the value below was "standard_block"
    # until now, so lua shared a regex with C-style languages and got
    # zero comment stripping (standard_block never used the `--` token).
    # "multi_style_dash" is the real family for this shape.
    # Rationale: Uses '--' for lines and '--[[ ... ]]' for blocks.
    "lexical_family": "multi_style_dash",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow. Includes standard loops and Lua 5.2+ goto.
        "branch": re.compile(r"\b(if|then|elseif|else|for|in|while|do|repeat|until|break|continue|goto|and|or|not)\b"),
        # 2. args: Parameters / Coupling. Captures parameters in named and anonymous function signatures.
        # #1209: parameter-list span wrapped in its own capture group (was
        # only reachable via group(0), the whole match including the
        # "function"/name prefix) so detector.py's counter isolates just
        # "(...)" -- the whole-match fallback overcounted every zero/
        # one-arg signature by +1 the same way Python's did (#1199). Name
        # group added too, purely so existing extraction tests keep
        # passing.
        "args": re.compile(
            r"\bfunction\s*([a-zA-Z_][\w.:]*\s*)?(?:<(?:[^<>]|<[^<>]*>)*>\s*)?(\([^()]*(?:\([^()]*(?:\([^()]*\)[^()]*)*\)[^()]*)*\))"
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope and data definitions.
        "structural_boundaries": re.compile(
            r"\b(local|end|require|module|return|export\s+type|type)\b|<\s*(?:const|close|toclose)\s*>"
        ),
        # 4. func_start: Executable Logic Anchors. Anchors executable logic blocks (named functions).
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL FUNCTION SHIELD (LUA) ]
            # Lua developers frequently split the `local`, `function`, and identifier
            # across newlines.
            # FIX: Upgraded horizontal `[ \t]+` bounds to `[ \t\n]+` across the
            # modifier stack, and securely allowed `[ \t\n]*` in the positive
            # lookahead for the parenthesis. Includes support for Luau generic types.
            # =====================================================================
            # #2461: also anchor after a `;` -- a `local function` / `function`
            # declaration is not always the first statement on its line
            # (`local a; local function f(x) ... end`, common in the Lua test
            # suite). `;` is a bare statement separator once strings/comments
            # are shielded, so a `function` keyword immediately after one is a
            # real declaration head, not text.
            r"(?:^[ \t]*|;[ \t]*)(?:local[ \t\n]+)?(?:export[ \t\n]+)?function[ \t\n]+([a-zA-Z_][\w.:]*)(?=[ \t\n]*(?:<(?:[^<>]|<[^<>]*>)*>[ \t\n]*)?\()",
            re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Captures proto-tables or EmmyLua class definitions.
        "class_start": re.compile(
            r"^[ \t]*---@class\s+([a-zA-Z_]\w*)|^[ \t]*(?:local[ \t\n]+)?(?:export[ \t\n]+)?(?:type[ \t\n]+)?([A-Z][a-zA-Z0-9_]*)(?=[ \t\n]*=[ \t\n]*\{)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Protected calls, assertions, and type checks.
        "safety": re.compile(
            r"\b(pcall|xpcall|assert|error|type|getmetatable|rawequal|ipairs|pairs|next)\b|<\s*(?:const|close|toclose)\s*>"
        ),
        # 7. safety_neg: Safety Bypasses. Actively bypassing safety (environment manipulation/raw access).
        "safety_bypasses": re.compile(
            r"\b(rawget|rawset|rawlen|debug\.[a-zA-Z0-9_]+|collectgarbage|_G|_ENV|getfenv|setfenv)\b"
        ),
        # 8. danger: High-Risk Execution. Dynamic evaluation and OS-level execution hooks.
        "high_risk_execution": re.compile(r"\b(os\.execute|os\.exit|os\.remove|os\.rename|load|loadstring|loadfile)\b"),
        # 9. io: I/O & Network Boundaries. Standard IO library and environment inquiries.
        "io": re.compile(r"\b(io\.open|io\.read|io\.lines|io\.close|io\.input|io\.output|io\.popen|os\.getenv)\b"),
        # 10. api: Public Surface Area. Functions NOT marked local or explicit module returns.
        "api": re.compile(
            r"^[ \t]*function\s+[^_][\w.:]*|^[ \t]*return\s+[a-zA-Z_]\w*[ \t]*$|---@public|\bexport\b",
            re.M,
        ),
        # 11. flux: State Mutation. State mutation (assignments and table mutators).
        "state_mutation": re.compile(
            r"\b[a-zA-Z_]\w*(?:\[[^\]]+\]|\.[a-zA-Z_]\w*)?\s*(?<![=<>~])=(?![=])|\btable\.(?:insert|remove|move|sort|concat)\b"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code trails.
        "dead_code": re.compile(
            r"(?:--|--\[=*\[)[ \t]*(?:if|local|function|for|while|print|return)\b",
            re.M,
        ),
        # 13. doc: Structured Documentation. LDoc/EmmyLua style documentation.
        "doc": re.compile(
            r"---@(?:param|return|field|see|alias|private|protected|diagnostic)|---\s*[A-Z]",
            re.M,
        ),
        # 14. test: Testing & Assertions. Busted, LuaUnit, and custom verification markers.
        "test": re.compile(
            r'\b(?:setup|teardown|busted|luassert|assert|mock|stub|spy|luaunit|Test[A-Z]\w*)\b|\b(?:describe|it)\s*[\'"(]'
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. Lua coroutines and task schedulers.
        "concurrency": re.compile(
            r"\b(coroutine\.(?:create|resume|yield|wrap|status|isyieldable|close)|task\.(?:spawn|wait|defer|delay)|uv\.[a-zA-Z0-9_]+)\b"
        ),
        # 16. ui_framework: UI / View Components. Game engine hooks (LÖVE, Solar2D, Defold, Roblox).
        "ui_framework": re.compile(
            r"\b(love\.[a-zA-Z0-9_]+|display\.new[a-zA-Z0-9_]+|gui\.[a-zA-Z0-9_]+|Roact\.[a-zA-Z0-9_]+|Instance\.new)\b"
        ),
        # 17. closures: Closures / Anonymous Functions. Anonymous function depth.
        "closures": re.compile(r"(?:^|[(=,\s])function\s*\([^)]*\)", re.M),
        # 18. globals: Global / Shared State. Access to global registries.
        "globals": re.compile(r"\b(_G|_ENV|_VERSION|arg)\b|^[ \t]*[A-Z][A-Z0-9_]*[ \t]*=(?![=])", re.M),
        # 19. decorators: Decorators / Annotations. EmmyLua annotations.
        "decorators": re.compile(r"^[ \t]*---@[a-zA-Z_]\w*", re.M),
        # 20. generics: Generics / Type Parameters. EmmyLua generic type annotations.
        "generics": re.compile(r"---@(?:generic|type)\s+[a-zA-Z_]\w*(?:<[^>]*>)?"),
        # 21. comprehensions: Iterators / Comprehensions. Functional iterator patterns.
        "comprehensions": re.compile(
            r"\b(?:pairs|ipairs|next|string\.gmatch)\b|\b(?:lume|moses|_\.)(?:map|filter|reduce|each|find|any|all)\b"
        ),
        # 22. scientific: Numerical / Compute Libraries. Standard math library.
        "scientific": re.compile(r"\b(math\.[a-zA-Z0-9_]+|bit32\.[a-zA-Z0-9_]+)\b|<<|>>|//"),
        # 23. heat_triggers: Metaprogramming & Reflection. Metatable overrides and Dunder methods.
        "reflection_metaprogramming": re.compile(
            r"\b(__index|__newindex|__call|__add|__sub|__mul|__div|__mod|__pow|__unm|__idiv|__band|__bor|__bxor|__bnot|__shl|__shr|__concat|__len|__eq|__lt|__le|__gc|__close|__mode)\b"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"\b(?:require|dofile)\b[ \t\n]*\(?[ \t\n]*['\"]", re.M),
        "_dependency_capture": re.compile(
            # =====================================================================
            # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (LUA) ]
            # PURPOSE: Extracts external dependencies for the Network Graph and Firewall.
            #
            # HISTORICAL BUG: Anchored to `^[ \t]*`. In Lua, modules are simply tables
            # returned by the `require` function. They are frequently lazy-loaded
            # inside local functions or conditionally assigned. Furthermore, because
            # the regex demanded the assignment (`local x = require...`) to touch the
            # left margin, it missed indented conditionals and inline evaluations entirely.
            #
            # THE FIX: Stripped the `^` anchor and completely deleted the bloated
            # variable-assignment capture group. We now scan directly for the `require`
            # or `dofile` boundary.
            #
            # [ THE PARENTHESIS SHIELD ]
            # Lua allows calling functions with a single string argument without
            # parentheses: `require "math"` vs `require("math")`. The `\(?` safely
            # bridges both syntaxes.
            # =====================================================================
            r"\b(?:require|dofile)[ \t\n]*\(?[ \t\n]*['\"]([^'\"]+)['\"]",
            re.M,
        ),
        # 25. ownership: Authorship metadata in comments.
        "ownership": re.compile(
            r"--\s*(?:Author|Copyright|License|Maintainer):\s+([^\n]+)|---\s*@author\s+([^\n]+)",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
        # 31. ssr_boundaries: View Horizon. Server-side rendering (Lapis/OpenResty).
        "ssr_boundaries": re.compile(r"\b(ngx\.say|ngx\.print|ngx\.exit|ngx\.req|lapis\.Serve|lapis\.Application)\b"),
        # 32. events: Pub/Sub Network. Signal handlers and event brokers.
        "events": re.compile(
            r"\b(addEventListener|removeEventListener|dispatchEvent|on|emit|EventEmitter|Connect|FireServer|FireClient)\b"
        ),
        # 33. dependency_injection: Inversion of Control. Service locator patterns.
        "dependency_injection": re.compile(r"\b(inject|container:get|container:resolve|Locator)\b"),
        # 34. macros: Preprocessor Hooks. (Lua lacks a native preprocessor).
        "macros": None,
        # 35. pointers: Memory Map. FFI raw memory interactions.
        "pointers": re.compile(
            r"\b(ffi\.cast|ffi\.new|ffi\.cdef|ffi\.typeof|ffi\.sizeof|ffi\.alignof|ffi\.offsetof|ffi\.string|ffi\.copy|ffi\.fill)\b"
        ),
        # 36. memory_alloc: Manual Memory Management. Garbage collection triggers and FFI malloc.
        "memory_alloc": re.compile(r"\b(ffi\.C\.malloc|ffi\.C\.free|ffi\.C\.calloc|ffi\.C\.realloc|collectgarbage)\b"),
        # 37. inline_asm: Bare Metal.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics.
        "telemetry": re.compile(r"\b(?:log\.(?:info|warn|error|debug|trace)|ngx\.log|ngx\.ERR|ngx\.INFO)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
        "debug_prints": re.compile(r"\b(print|warn|io\.write)\b"),
        # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax.
        "explicit_casts": re.compile(r"\b(ffi\.cast|tonumber|tostring)\b"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(error|assert|os\.exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r'\b(task\.wait|os\.execute\s*\(?[\'"]sleep)\b'),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>|&|\||\^|~(?!=)"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(mutex|lock|semaphore|critical_section|uv\.mutex)\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"<\s*const\s*>"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(ffi\.C\.free|collectgarbage|io\.close|:[ \t]*close)\b|<\s*(?:close|toclose)\s*>"),
        # 47. encapsulation
        "encapsulation": re.compile(r"\b(local|_ENV)\b|---@private", re.M),
        # 48. listeners (Event Listeners / Observers)
        # BUG FIX: `on\s*\(` ends on `(` (non-word), so the shared
        # trailing \b could only fire when a word char immediately
        # followed the paren -- never true for the common real call
        # shape `emitter:on('event', cb)`, where a quote follows.
        "listeners": re.compile(r"\bon\s*\(|\b(?:subscribe|Connect|addEventListener)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(xdescribe|xit|skip)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Lua Specifics) ---
        "serialization_parsing": re.compile(r"\b(string\.dump|loadstring|load|cjson\.decode|cjson\.encode)\b"),
        "regex_execution": re.compile(r"\b(string\.match|string\.gmatch|string\.find|string\.gsub)\b"),
        "time_date_logic": re.compile(r"\b(os\.time|os\.clock|os\.date|os\.difftime)\b"),
        "ipc_rpc_bridges": re.compile(
            r"\b(os\.execute|io\.popen|coroutine\.create|coroutine\.resume|coroutine\.yield)\b"
        ),
    },
}
