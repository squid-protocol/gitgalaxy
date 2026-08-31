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
        "target_version": "Zig 0.15.2 (Modern Comptime, Explicit Allocators, Error Sets)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard sources and Zig Object Notation (ZON) files which are structurally Zig AST.
    "extensions": [".zig", ".zon"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: The pure-code build scripts that act as the architectural anchors of a Zig project.
    "exact_matches": ["build.zig", "build.zig.zon"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Zig's build system files ensure that ambiguous contexts are locked in perfectly.
    "discriminators": [".zig", "build.zig", "build.zig.zon"],
    # EXECUTION SIGNATURES: Zig is compiled, but `zig run` can be invoked via shebang in scripting scenarios.
    "shebangs": ["zig"],
    # UPGRADED: Maps to Family 8 (Singular/Unique)
    # Rationale: Zig intentionally omits multi-line block comments to keep parsing simple, exclusively using '//'.
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow. Includes unique 'orelse' and 'catch' patterns.
        "branch": re.compile(
            r"(?<!@\")\b(if|else|switch|while|for|try|catch|orelse|break|continue|return)\b(?!\")|&&|\|\|"
        ),
        # 2. args: Parameters / Coupling. Captures parameters in function signatures.
        "args": re.compile(
            r"\bfn[ \t\n]*(?:@\"[^\"]+\"|[a-zA-Z_]\w*[ \t\n]*)?\(((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\([^)(]*\))*\))*\))*\))*)\)"
        ),
        # #1645: group 1 above captures ONLY the bare inner parameter-list
        # text -- never a self-wrapped "(...)" pair of its own (unlike
        # python's args group, this one never shares group(0) with a
        # "fn name(...)" prefix). Tells detector.py's args-counting to
        # depth-count top-level commas directly over the whole captured
        # string instead of either the naive whitespace-split fallback
        # (which miscounts a single typed param like `self: Default` as 2
        # tokens) or `_count_top_level_args`'s default wrapper-detection
        # (which mistakes a param TYPE's own parens -- `ctx: @This()`,
        # function-pointer params -- for the signature's outer wrapper and
        # truncates/zeroes the count). See `_args_bare_body_groups` in
        # detector.py's `_calculate_block_metrics` for the full story.
        "_args_bare_body_groups": {1},
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and const (freeze_hits).
        "structural_boundaries": re.compile(
            r"(?<!@\")\b(var|return|defer|errdefer|unreachable|resume|suspend|await|nosuspend|usingnamespace)\b(?!\")"
        ),
        # 4. func_start: Executable Logic Anchors. Anchors logic blocks (fn). EXCLUDES struct/enum/union headers.
        "func_start": re.compile(
            r"^[ \t]*(?:(?:pub|export(?:[ \t]+\"(?:[^\"\\]|\\.)*\")?|extern(?:[ \t]+\"(?:[^\"\\]|\\.)*\")?|inline|noinline|callconv\((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\([^)(]*\))*\))*\))*\))*\)|linksection\((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\([^)(]*\))*\))*\))*\))*\)|align\((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\((?:[^)(]|\([^)(]*\))*\))*\))*\))*\))[ \t\n]+)*fn[ \t\n]+(@\"(?:[^\"\\]|\\.)*\"|[a-zA-Z_]\w*)(?=[ \t\n]*\()",
            re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Defines structural entities (struct, enum, union, error, opaque).
        # #1295: an optional `\(` and/or `\*` step-over added between `=`
        # and the packed/extern modifier so two real corpus-confirmed
        # idioms aren't missed: a parenthesized-wrapped anonymous struct
        # (`const lenAsc = (struct { ... }).lenAsc;`, common for a
        # struct-as-namespace immediately projecting one declaration out
        # of itself) and a pointer-to-opaque handle type (`const HMONITOR
        # = *opaque {};`, the standard idiom for an opaque OS handle).
        "class_start": re.compile(
            r"^[ \t]*(?:pub[ \t\n]+)?(?:const|var)[ \t\n]+(@\"[^\"]+\"|[a-zA-Z_]\w*)(?:(?!\b(?:const|var)\b)[^=;]){0,150}=[ \t\n]*(?:List\([ \t\n]*|\[_\][ \t\n]*|if[ \t]*\([^)]*\)[ \t\n]*|(?:[A-Za-z0-9_. \t\n]+\|\|[ \t\n]*)+|(?:\(|\*)[ \t\n]*|(?:packed|extern|inline)[ \t\n]+|align\([^)]*\)[ \t\n]+)*(?:struct|enum|union|error|opaque)(?=[ \t\n]*[{(])",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Error handling, payload capturing (|val|), and debug assertions.
        "safety": re.compile(r"\b(try|catch|orelse|errdefer|std\.debug\.assert)\b|\|[ \t]*[a-zA-Z_]\w*[ \t]*\|"),
        # 7. safety_neg: Safety Bypasses. Bypassing safety (undefined, unreachable, raw ptr casting).
        # BUG FIX: the 6 `@`-prefixed builtins (Zig's cast/truncate
        # operations are all `@builtin` forms) start with a non-word
        # char, so the shared leading \b could only fire when a word
        # char immediately preceded the `@` -- never true for how
        # builtins are actually written. None of the 6 ever matched.
        "safety_bypasses": re.compile(
            r"\b(?:undefined|unreachable)\b"
            r"|@ptrCast|@intCast|@alignCast|@bitCast|@truncate|@enumFromInt"
        ),
        # 8. danger: High-Risk Execution. Forceful panics and process terminations.
        # BUG FIX: `@panic` is `@`-prefixed -- same leading-\b bug.
        "high_risk_execution": re.compile(r"\b(?:panic|std\.process\.exit)\b|@panic"),
        # 9. io: I/O & Network Boundaries. Standard library IO, Network, and Filesystem interactions.
        "io": re.compile(r"\b(std\.fs|std\.net|std\.io(?!\.getStdOut)|std\.ChildProcess|std\.posix|std\.os)\b"),
        # 10. api: Public Surface Area. Exposed boundaries via 'pub' and 'export' (C ABI).
        "api": re.compile(r"\b(pub|export)\b"),
        # 11. flux: State Mutation. State mutation (var) and pointer dereference assignments (.* =).
        "state_mutation": re.compile(r"\bvar\b|\.\*[ \t]*=[^=]"),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code.
        "dead_code": re.compile(r"//[ \t]*(?:fn|const|var|pub|if|for|while|try|catch)\b"),
        # 13. doc: Structured Documentation. Structured documentation (/// and //!).
        "doc": re.compile(r"///|//!"),
        # 14. test: Testing & Assertions. Native test framework blocks.
        # BUG FIX: `test\s+"[^"]*"` ended on `"`, inside the shared
        # trailing `\b` group. The char after a closing quote (space,
        # then `{`) is also non-word, so `\b` between two non-word
        # chars never fired -- the quoted-test-name form (`test "basic"
        # {`), Zig's dominant real-world test declaration shape, never
        # matched at all. Pulled out with no trailing `\b`
        # (self-delimiting on the closing quote).
        "test": re.compile(
            r'test\s+"[^"]*"|\b(?:test\s+[a-zA-Z_]\w*|std\.testing\.expect|std\.testing\.expectEqual)\b'
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. Suspend/resume and thread primitives.
        # BUG FIX: `@atomicLoad`/`@atomicStore`/`@atomicRmw` are
        # `@`-prefixed builtins -- same leading-\b bug.
        "concurrency": re.compile(
            r"\b(?:std\.Thread|std\.Thread\.Mutex|std\.Thread\.RwLock|std\.atomic|suspend|resume|await)\b"
            r"|@atomicLoad|@atomicStore|@atomicRmw"
        ),
        # 16. ui_framework: UI / View Components. (Zig lacks native UI; targets common bindings like Mach/zgui).
        "ui_framework": re.compile(r"\b(mach\.|zgui\.|zopengl\.|capy\.|vaxis\.|raylib\.)\b"),
        # 17. closures: Closures / Anonymous Functions. (Zig lacks traditional anonymous closures).
        "closures": None,
        # 18. globals: Global / Shared State. Top-level file-scoped state.
        "globals": re.compile(
            r"^[ \t]*(?:pub[ \t]+)?(?:threadlocal[ \t]+)?(?:comptime[ \t]+)?(?:const|var)\s+[a-zA-Z_]\w*\s*(?::[^=]+)?=",
            re.M,
        ),
        # 19. decorators: Decorators / Annotations. (Zig uses @builtins instead).
        "decorators": None,
        # 20. generics: Generics / Type Parameters. Comptime parameters and 'anytype' duck typing.
        "generics": re.compile(r"\b(anytype|type)\b|\bcomptime\s+[a-zA-Z_]\w*\s*:\s*type\b"),
        # 21. comprehensions: Iterators / Comprehensions. (Not native to Zig).
        "comprehensions": None,
        # 22. scientific: Numerical / Compute Libraries. Math intrinsics and SIMD @Vector support.
        # BUG FIX: `@Vector`/`@sqrt`/`@sin`/`@cos`/`@splat`/`@reduce`
        # are `@`-prefixed builtins -- same leading-\b bug.
        "scientific": re.compile(r"\b(?:std\.math|f16|f32|f64|f80|f128)\b|@Vector|@sqrt|@sin|@cos|@splat|@reduce"),
        # 23. heat_triggers: Metaprogramming & Reflection. Comptime metaprogramming and reflection.
        # BUG FIX: `@Type`/`@typeInfo`/`@compileLog`/`@hasDecl`/
        # `@hasField` are `@`-prefixed builtins -- same leading-\b bug.
        "reflection_metaprogramming": re.compile(
            r"\b(?:comptime[ \t]*\{|inline\s+for|inline\s+while)\b|@Type|@typeInfo|@compileLog|@hasDecl|@hasField"
        ),
        # 24. import: Dependency Inclusions. Module and C-header bridges.
        # BUG FIX: all 3 are `@`-prefixed builtins -- same leading-\b
        # bug. None ever matched.
        "import": re.compile(r"@import\b|@cImport\b|@cInclude\b"),
        "_dependency_capture": re.compile(
            r"(?:^[ \t]*(?:(?:pub[ \t]+)?const[ \t]+(?:@\"[^\"]+\"|[a-zA-Z_]\w*)[ \t]*=[ \t]*|_[ \t]*=[ \t]*)?@import|(?:^[ \t]*(?:const[ \t]+(?:@\"[^\"]+\"|[a-zA-Z_]\w*)[ \t]*=[ \t]*)?@cImport[ \t\n]*\{[ \t\n]*)?@cInclude|[ \t]*@cInclude)[ \t\n]*\([ \t\n]*['\"]([^'\"]+)['\"]",
            re.M,
        ),
        # 25. ownership: Authorship indicators in comments.
        "ownership": re.compile(r"//\s*(?:Author|Created by|Maintainer|Copyright):\s+([^\n]+)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
        # 31. ssr_boundaries: View Horizon. Zap/httpz response handlers.
        "ssr_boundaries": re.compile(r"\b(zap\.Endpoint|zap\.Request|httpz\.Request|std\.http\.Server\.Request)\b"),
        # 32. events: Pub/Sub Network. OS-level event loops.
        "events": re.compile(r"\b(std\.posix\.epoll_wait|std\.posix\.kevent|xev\.Loop)\b"),
        # 33. dependency_injection: Inversion of Control.
        "dependency_injection": None,
        # 34. macros: Preprocessor Hooks. (Zig lacks macros).
        "macros": None,
        # 35. pointers: Memory Map. Explicit pointer tracking.
        "pointers": re.compile(
            r"(?<=[=\s,(])\*(?:const\s+|volatile\s+|allowzero[ \t]+)?[a-zA-Z_]\w*|\[\*c?\][a-zA-Z_]\w*|\.\*"
        ),
        # 36. memory_alloc: Manual Memory Management. Allocators bypassing the GC.
        "memory_alloc": re.compile(
            r"\b(std\.mem\.Allocator|allocator\.alloc|allocator\.free|allocator\.create|ArenaAllocator|c_allocator|page_allocator)\b"
        ),
        # 37. inline_asm: Bare Metal.
        "inline_asm": re.compile(r"\basm\b(?:\s+volatile)?\s*\([^)]+\)"),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics.
        "telemetry": re.compile(r"\b(?:std\.log\.(?:info|err|warn|debug)|std\.log\.scoped)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
        "debug_prints": re.compile(r"\b(std\.debug\.print)\b"),
        # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit casting.
        # BUG FIX: all 5 are `@`-prefixed builtins -- same leading-\b
        # bug. None ever matched.
        "explicit_casts": re.compile(r"@ptrCast\b|@intCast\b|@alignCast\b|@bitCast\b|@as\b"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting context.
        # BUG FIX: `@panic` is `@`-prefixed -- same leading-\b bug.
        "panics_and_aborts": re.compile(r"\b(?:unreachable|return)\b|@panic"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits/sleep).
        "thread_sleeps": re.compile(r"\b(std\.time\.sleep)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~"),
        # 44. sync_locks (Resource Management & Stability) Coordinated threading.
        "sync_locks": re.compile(r"\b(Mutex|RwLock|Semaphore|lock|unlock)\b"),
        # 45. immutability_locks (Immutability Constraints) Immutability.
        "immutability_locks": re.compile(r"\bconst\b"),
        # 46. cleanup (Resource Cleanup / Teardown) Resource release.
        "cleanup": re.compile(r"\b(deinit|free|destroy|allocator\.free)\b"),
        # 47. encapsulation Scope hiding (Lack of pub).
        "encapsulation": re.compile(r"^[ \t]*(?!(?:pub|export|extern)\b)(?:const|var|fn)\s+", re.M),
        # 48. listeners (Event Listeners / Observers)
        "listeners": None,
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(std\.testing\.expect|assume|expectError)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Zig Specifics) ---
        "serialization_parsing": re.compile(r"\b(std\.json\.parseFrom(?:Slice|TokenSource)|std\.json\.stringify)\b"),
        "regex_execution": re.compile(
            r"\b(std\.mem\.(?:indexOf|tokenize(?:Any)?|split(?:Sequence|Any)?|replace))\b"
        ),  # Zig has no native regex!
        "time_date_logic": re.compile(r"\b(std\.time\.(?:nanoTimestamp|milliTimestamp|Timer|sleep))\b"),
        "ipc_rpc_bridges": re.compile(
            r"\b(std\.process\.Child|std\.net\.tcpConnectToHost|std\.Thread\.spawn|std\.posix|std\.os\.execve)\b"
        ),
    },
}
