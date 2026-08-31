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
        "target_version": "Embedded Python (MicroPython / CircuitPython / Bare-Metal)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard Python suffixes and pre-compiled MicroPython bytecode (.mpy).
    "extensions": [".py", ".mpy"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: The strict execution entry points for microcontroller boot sequences.
    "exact_matches": ["boot.py"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, boot sequence files, and the MicroPython package installer (mip) configs.
    "discriminators": ["boot.py", "mip.json", "upip"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 for embedded discovery and cross-compilation.
    "shebangs": ["micropython", "mpy-cross"],
    # Instantly claims any .py file utilizing embedded electronics networking or GPIO libraries
    "internal_discriminator": re.compile(
        r"^[ \t]*(?:import|from)\s+(?:machine|board|microcontroller|busio|digitalio|analogio|usb_hid|neopixel|rp2|esp32|pyb|wifi|socketpool)\b",
        re.M,
    ),
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: Uses '#' for line-level literature; multi-line literature
    # (docstrings) is handled by the Section 2.3.C.3 Heuristic Pass.
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. EXCLUDES raise (bailout_hits).
        "branch": re.compile(r"\b(if|elif|else|for|while|with|try|finally|match|case|and|or)\b"),
        # 2. args (Parameters / Coupling)
        # Parameter blocks of functions/lambdas. Bounded negation to prevent ReDoS.
        # #1199: the parameter list is now captured in its own group
        # (group 1 for def/lambda-with-parens, group 2 for bare
        # lambda params) instead of only ever being reachable via
        # group(0), which used to include the "def name"/"lambda"
        # keyword prefix -- that prefix supplied a spurious extra
        # whitespace-split token that overcounted every zero/one-arg
        # signature by +1 downstream in detector.py's args-counter.
        # Group 1's body also steps over one level of nested parens
        # (the same bounded one-level-nesting idiom RULE 11 already
        # uses for square brackets above) so a default value that's
        # itself a call, e.g. `def f(x=foo(1, 2), y=3):`, doesn't
        # truncate the capture at the default's own closing paren and
        # silently drop every parameter after it.
        "args": re.compile(
            r"(?:async[ \t]+)?def[ \t]+(\w+)(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?[ \t]*(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))|\blambda\b[ \t]*([^:]*):",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: _private (encapsulation) and Final (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(def|class|return|import|from|as|pass|continue|break|yield|await|assert|del|global|nonlocal|type)\b"
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks. EXCLUDES classes. Steps safely over hardware decorators.
        "func_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}(?:async[ \t]+)?def[ \t]+(\w+)(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?[ \t]*\(",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}class[ \t]+([a-zA-Z_]\w*)(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?(?:[ \t]*\(([^)]*)\))?",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Hardware watchdogs and standard Python safety checks.
        "safety": re.compile(
            r"\b(try|except|finally|assert|machine\.WDT|isinstance|issubclass|hasattr|getattr|alloc_emergency_exception_buf)\b"
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Bare excepts and blocking the event loop (detrimental in embedded async).
        "safety_bypasses": re.compile(
            r"\bpass\b[ \t]*$|except\s*[:\n]|except\s+(?:Base)?Exception|from\s+[\w.]+\s+import\s+\*|\btime\.sleep(?:_ms|_us)?\b",
            re.M,
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Hardware resets and raw memory pokes. EXCLUDES TODO (debt) and print (print_hits).
        "high_risk_execution": re.compile(
            r"\b(machine\.reset|machine\.deepsleep|machine\.bootloader|machine\.disable_irq|eval|exec|sys\.exit)\b"
        ),
        # 9. io (I/O & Network Boundaries)
        # Hardware Peripherals (I2C, SPI, UART, Pin) and Networking.
        "io": re.compile(
            r"\b(open|Pin|I2C|SPI|UART|ADC|PWM|RTC|SDCard|I2S|WLAN|LAN|socket|usocket|uos\.mount|aiohttp)\b"
        ),
        # 10. api (Public Surface Area)
        # Implicit public defaults (undercased root defs) + explicit exports.
        "api": re.compile(
            r"^[ \t]*(?:async[ \t]+)?def\s+[^_]\w+|^[ \t]*class\s+[^_]\w+|^__all__[ \t]*=",
            re.M,
        ),
        # 11. flux (State Mutation)
        # State mutation including hardware value toggling.
        "state_mutation": re.compile(
            r"\bglobal\b|\bnonlocal\b|\b(?:self|cls)\.\w+[ \t]*=|:=|(?:\.\w+)?\.(?:append|extend|update|pop|remove|insert|clear)\s*\(|\.(?:value|on|off|high|low|toggle)\s*\("
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"#[ \t]*(?:def|class|import|if|for|while|try|print|machine\.Pin)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r'"""|\'\'\'|:param|:return|:raises|:type|#\s*Pin[ \t]*=|#\s*GPIO'),
        # 14. test (Testing & Assertions)
        # BUG FIX: `test_` was wrapped inside the shared `\b(...)\b` group.
        # `_` is a word character, so the trailing `\b` after `test_` demands
        # a NON-word character immediately follow -- never true for the
        # standard pytest convention (`test_login`, `test_parse_url`), where
        # more word characters always continue the name. Only a bare,
        # standalone trailing "test_" (unrealistic) ever matched. Anchored
        # as `def[ \t]+test_` instead (matches python's own fix for the
        # identical trap), dropping the trailing `\b` so it fires on the
        # realistic `def test_<name>` shape.
        "test": re.compile(r"\b(unittest|pytest|assert|setUp|tearDown|Mock)\b|def[ \t]+test_"),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(async|await|uasyncio|asyncio|Timer\.init|_thread|start_new_thread|allocate_lock|gather|create_task|Event|Lock)\b"
        ),
        # 16. ui_framework (UI / View Components)
        # Framebuffers and embedded OLED/TFT drivers.
        "ui_framework": re.compile(
            r"\b(framebuf|ssd1306|st7789|ili9341|epaper|lvgl|display|text|fill|pixel|show|scroll)\b"
        ),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(r"\blambda\b"),
        # 18. globals (Global / Shared State)
        "globals": re.compile(r"\bglobal\b|\bglobals\(\)|\blocals\(\)|\b(sys\.path|sys\.modules|os\.environ)\b"),
        # 19. decorators (Decorators / Annotations)
        # Generic decorators. (Specific ASM/Viper optimizations moved to heat_triggers/inline_asm).
        "decorators": re.compile(
            r"^[ \t]*@(?!(?:micropython\.viper|micropython\.asm|micropython\.native))[\w.]+",
            re.M,
        ),
        # 20. generics (Generics / Type Parameters)
        # QUADRATIC BLOWUP FIX: `[^\]]*` was unbounded. On a run of
        # repeated unclosed openers (e.g. "List[List[List[..."), each
        # "List[" occurrence is a fresh search start; at every one the
        # engine greedily consumes to end-of-string then backtracks
        # character-by-character looking for a "]" that never appears,
        # O(n) work per start position across O(n) start positions, for
        # O(n^2) total. Confirmed empirically (~4x runtime per size
        # doubling at n=2000/4000/8000/16000 on a "List[" * n payload).
        # Bounded to {0,300}; real generic parameter lists don't get
        # remotely that long. Post-fix scaling is linear (~2x/doubling).
        "generics": re.compile(
            r"\b(?:List|Dict|Set|Tuple|Optional|Union|Any|Callable|Sequence|Iterable)\[[^\]]{0,300}\]|->"
        ),
        # 21. comprehensions (Iterators / Comprehensions)
        # QUADRATIC BLOWUP FIX: the 3 negated-class quantifiers were
        # unbounded -- on a long run of unclosed brackets/braces/parens
        # (e.g. "((((((..."), each opening char is tried as a match
        # start, and each attempt scans to the end of the string looking
        # for "for" + closer, for O(n^2) total. Bounded to {0,500}; real
        # comprehensions don't get remotely that long.
        "comprehensions": re.compile(
            r"\[[^\]]{0,500}\bfor\b[^\]]{0,500}\]|\{[^}]{0,500}\bfor\b[^}]{0,500}\}|\([^)]{0,500}\bfor\b[^)]{0,500}\)"
        ),
        # 22. scientific (Numerical / Compute Libraries)
        # Math, complex arrays, and ulab (MicroPython's NumPy).
        "scientific": re.compile(
            r"\b(math|cmath|ulab|numpy|ndarray|struct\.pack|struct\.unpack|bin|hex|oct|abs|sin|cos|tan)\b"
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # High Cognitive Load: Dunder methods and Viper/Native emitters.
        "reflection_metaprogramming": re.compile(
            r"__(?:getattr|setattr|new|call|dict|dir|import)__|@(?:staticmethod|classmethod|property)|@micropython\.(?:viper|native)\b|\b(?:getattr|setattr|hasattr)\b"
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"^[ \t]*(?:import|from)\b\s+[\w.]+", re.M),
        "_dependency_capture": re.compile(r"^[ \t]*(?:import|from)\b\s+([\w.]+)", re.M),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"(?:__author__[ \t]*=|Author:|Created by:)\s*(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # QUADRATIC BLOWUP FIX: the SPEC alternative's `\d+` was
        # unbounded and directly precedes `[^\]]*`, an ALSO-unbounded
        # class whose character set overlaps it (digits satisfy both).
        # On a long run of digits with no closing "]" (e.g.
        # "[SPEC-" + "1" * n), `\d+` greedily consumes them all, then
        # backtracks one digit at a time while `[^\]]*` re-consumes the
        # released digit and re-fails to find "]" -- classic adjacent
        # overlapping-quantifier O(n^2). Confirmed empirically (~4x
        # runtime per size doubling at n=2000/4000/8000/16000). Bounded
        # `\d+` to `\d{1,10}` (no realistic ticket ID needs more digits)
        # and `[^\]]*` to `{0,300}`; post-fix scaling is immeasurably
        # fast even at n=32000.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries (Server-Side Rendering)
        # Lightweight web servers (Microdot, Picoweb).
        # BUG FIX: `@app\.get`/`@app\.post` are `@`-prefixed -- the
        # shared leading \b could only fire when a word char
        # immediately preceded the `@`, never true for how route
        # decorators are actually written. Never matched at all.
        "ssr_boundaries": re.compile(
            r"\b(?:microdot|picoweb|MicroWebSrv|tinyweb|render_template|Response)\b|@app\.get|@app\.post"
        ),
        # 32. events (Event Emitters / Pub-Sub)
        # Hardware interrupts and async event flags.
        "events": re.compile(
            r"\b(irq|Pin\.irq|Timer\.irq|machine\.enable_irq|trigger|set_callback|Event\.set|schedule)\b"
        ),
        # 33. dependency_injection
        "dependency_injection": None,  # MicroPython strictly follows imperative wiring due to RAM limits.
        # 34. macros
        # MicroPython's const() acts as a compile-time macro.
        "macros": re.compile(r"\bconst\s*\([^)]+\)"),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Pointer manipulation enabled by Viper/uctypes.
        "pointers": re.compile(
            r"\b(uctypes\.addressof|uctypes\.bytearray_at|ptr8|ptr16|ptr32|machine\.mem8|machine\.mem16|machine\.mem32)\b"
        ),
        # 36. memory_alloc
        "memory_alloc": re.compile(r"\b(bytearray|memoryview|alloc_emergency_exception_buf)\b"),
        # 37. inline_asm (The Bare Metal)
        "inline_asm": re.compile(r"@(?:micropython\.asm_thumb|micropython\.asm_xtensa|rp2\.asm_pio)\b"),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(logging|logger|ulogging|syslog)\.(?:info|error|warn|warning|debug|trace|critical|exception)\b"
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(print|input)\s*\("),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"\b(int|str|float|list|dict|set|tuple|bool|bytes|cast)\b\s*\("),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(raise|quit|exit|sys\.exit|abort)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(time\.sleep|asyncio\.sleep|Thread\.join)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"<<|>>|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(Lock|RLock|Semaphore|Event|Condition|allocate_lock)\b"),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(Final|frozenset|mappingproxy|immutable)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(close|__exit__|del|gc\.collect|cleanup)\b\s*\("),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        "encapsulation": re.compile(r"\b_[a-zA-Z_]\w*\b"),
        # 48. listeners (Event Listeners / Observers)
        # Waiting for state broadcast via hardware IRQs or event listeners.
        "listeners": re.compile(r"\.irq\(|handler=|callback="),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(pytest\.mark\.skip|unittest\.skip|mock\.|MagicMock)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Embedded Python Specifics) ---
        "serialization_parsing": re.compile(r"\b(ujson\.loads?|ujson\.dumps?|ustruct\.pack|ustruct\.unpack)\b"),
        "regex_execution": re.compile(r"\b(ure\.compile|ure\.search|ure\.match|ure\.sub)\b"),
        "time_date_logic": re.compile(r"\b(utime\.sleep_ms|utime\.ticks_ms|utime\.ticks_diff|machine\.RTC)\b"),
        "ipc_rpc_bridges": re.compile(
            r"\b(machine\.Pin|machine\.I2C|machine\.UART|network\.WLAN|usocket\.socket|busio\.I2C)\b"
        ),
    },
}
