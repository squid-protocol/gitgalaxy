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
        "target_version": "x86-64 (NASM/GAS) & ARMv8 (AArch64) - Backwards Compatible",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard assembly, GNU Assembler, NASM, MASM, and architecture-specific extensions.
    "extensions": [
        ".asm",
        ".s",
        ".S",
        ".inc",
        ".nasm",
        ".s64",
        ".masm",
        ".arm",
        ".a51",
    ],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Assembly is assembled directly to machine code; no extensionless exact configurations exist.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, linker scripts (.ld), and build systems acting as disambiguation anchors to resolve .inc or .s files.
    "discriminators": [
        ".asm",
        ".s",
        ".S",
        ".c",
        ".cpp",
        ".ld",
        "Makefile",
        "CMakeLists.txt",
    ],
    # EXECUTION SIGNATURES: Assembly is compiled/assembled to binary; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 8 (Singular/Unique)
    # Rationale: Uses unique line delimiters ';' (NASM/Intel) and '#' (GAS/ARM).
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. EXCLUDES system exits/halts (bailout_hits).
        "branch": re.compile(
            r"\b(jmp|je|jne|jz|jnz|ja|jb|jl|jg|jge|jle|jae|jbe|call|ret|b|bl|bx|blr|cbz|cbnz|tbz|tbnz|beq|bne|loop)\b",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Assembly uses ABI registers for parameter coupling. Also covers the
        # legacy 8/16-bit x86 register forms (al/ah/ax, etc.) and the r8/r9
        # sub-register suffixes (r8d/r8w/r8b), since this language's own
        # _meta declares it "Backwards Compatible" and real corpus code
        # (e.g. 16-bit real-mode bootloaders) uses exactly these forms for
        # register-coupling. (#856 follow-up) Previously `[er][89]` matched
        # the nonexistent registers "e8"/"e9" while failing to match the
        # real r8d/r9d/r8w/r9w/r8b/r9b forms, since the trailing `\b` never
        # fires between two word characters (the digit and the size suffix).
        "args": re.compile(
            r"\b([er]di|[er]si|[er]dx|[er]cx|r[89][dwb]?|x[0-7]|w[0-7]|v[0-7]|xmm[0-7]|r[0-7]"
            r"|a[xhl]|b[xhl]|c[xhl]|d[xhl]|si|di)\b",
            re.I,
        ),
        # 3. linear (Sequential Boundaries)
        # Data movement and arithmetic primitives. EXCLUDES: Linker visibility (api) and sections (globals).
        "structural_boundaries": re.compile(
            r"\b(mov(?:abs|[sz]x|[bwlq]|aps|ups|dqu)?|vmov[a-z]+|lea|ldr[s]?[bhw]?|str[bhw]?|push|pop|add|sub|inc|dec|mul|imul|div|idiv|nop|ldp|stp)\b",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # Subroutine entry points. EXCLUDES data labels or local loop markers.
        # The trailing negative lookahead is the generic-assembly counterpart to
        # agc_assembly's "label must be followed by a real opcode" positive lookahead,
        # inverted for the own-line-label convention this dialect uses: a label whose
        # colon is followed (same line, or the very next line) only by a pure
        # data-emission / location-counter directive (`.asciz`, `.byte`, `.org`,
        # `.endobj`, NASM `db`/`resb`/`times`, ...) is a data object, not a subroutine
        # entry -- e.g. cosmopolitan/ape.S's `ape.mbrpad:` / `.org 0x1b4`
        # (assembly/function/existence/agree[gitgalaxy]_vs[ctags], the mirror of
        # agc_assembly's own data-label win). Section/visibility/type/align directives
        # are deliberately NOT in the list -- those legitimately sit between a real
        # function's label and its first instruction.
        "func_start": re.compile(
            r"^[ \t]*(?!\.L|\.LC|\d|\.text|\.data|\.bss)([a-zA-Z_?@.][a-zA-Z0-9_.$?@]*)(?=[ \t]*:)"
            r"(?![ \t]*:[ \t]*(?:\r?\n[ \t]*)?"
            r"(?:\.(?:org|endobj|asciz|ascii|string|byte|hword|short|word|long|int|value"
            r"|quad|octa|single|double|float|fill|space|skip|zero|incbin)"
            r"|d[bwdq]|res[bwdq]|times)\b)",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Maps to assembler structure definition macros.
        "class_start": re.compile(
            r"^[ \t]*(?:(?:struc|STRUCT|\.struct)[ \t]+[a-zA-Z_?@.][a-zA-Z0-9_.$?@]*|[a-zA-Z_?@.][a-zA-Z0-9_.$?@]*[ \t]+(?:struc|STRUCT|\.struct))\b",
            re.M | re.I,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Stack preservation and defensive frame setups.
        "safety": re.compile(
            r"\b(enter|leave|endbr64|paciasp|autiasp|bti|retab|\.align|\.p2align)\b|\b(?:stp|ldp)\s+x29,\s*x30",
            re.I,
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Indirect jumps and hardware interrupt disabling.
        "safety_bypasses": re.compile(
            r"\b(?:jmp|call)\s+(?:\*|\[|[er]?[abcd]x|r\d+)\b|\bbr\s+[xw]\d+\b|\b(cli|msr\s+daifclr)\b",
            re.I,
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # CPU halts and debug traps. EXCLUDES prints (Phase 5).
        "high_risk_execution": re.compile(r"\b(hlt|int\s+3|brk|ud2|sys_exit|sys_kill)\b", re.I),
        # 9. io (I/O & Network Boundaries)
        # System calls and hardware I/O ports.
        "io": re.compile(
            r"\b(in|out|ins[bdw]|outs[bdw]|syscall|svc\b|int\s+0x80|sys_read|sys_open)\b",
            re.I,
        ),
        # 10. api (Public Surface Area)
        # Linker-visible global exports.
        "api": re.compile(
            r"^[ \t]*(?:\.global|\.globl|global|EXPORT|PUBLIC|EXTERN|IMPORT)\b",
            re.M | re.I,
        ),
        # 11. flux (State Mutation)
        # Explicit memory/register swaps and atomic increments.
        "state_mutation": re.compile(r"\b(xchg|cmpxchg|inc|dec)\b", re.I),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"(?i)(?:;|#|//)[ \t]*(?:jmp|call|mov|push|pop|cmp|add|sub)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"^[;#@/|]+\s*@(?:param|return|brief|author|note)", re.M | re.I),
        # 14. test (Testing & Assertions)
        "test": re.compile(r"(?i)\b(?:describe|expect|assert|TestCase)\b|\bit[ \t]*\("),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(lock|xadd|mfence|lfence|sfence|dmb|dsb|isb|ldxr|stxr|ldaxr|stlxr)\b",
            re.I,
        ),
        # 16. ui_framework
        "ui_framework": None,
        # 17. closures
        "closures": None,
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            r"^[ \t]*(?:\.data|\.bss|\.rodata|\.comm|section\s+\.data|section\s+\.bss)\b",
            re.M | re.I,
        ),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions (Iterators / Comprehensions)
        # Instruction repetition prefixes.
        "comprehensions": re.compile(
            r"^[ \t]*(?:%rep|\.rept|\.irp)\b|\b(?:rep|repe|repne|repz|repnz)\b",
            re.M | re.I,
        ),
        # 22. scientific (Numerical / Compute Libraries)
        # FPU, SSE, AVX, and NEON instructions.
        "scientific": re.compile(
            r"\b(fadd|fsub|fmul|fdiv|fsqrt|vadd[ps][sd]|vsub[ps][sd]|vmul[ps][sd]|fmla|fmov)\b",
            re.I,
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Complex SIB addressing and block replication.
        "reflection_metaprogramming": re.compile(r"\[\s*[a-zA-Z0-9_]+\s*\+\s*[a-zA-Z0-9_]+\s*\*\s*\d+", re.I),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"^[ \t]*(?:%include|\.include|\.incbin|INCLUDE|INCLUDELIB)\b", re.M | re.I),
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:%include|\.include|\.incbin|INCLUDE|INCLUDELIB)\s+(?:['\"]([^'\"]+)['\"]|([^'\"\s]+))",
            re.M | re.I,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"^[;#@/|]+\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)",
            re.M | re.I,
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
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit|rfc)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Interrupt vectors and exception handlers.
        "events": re.compile(
            r"\b(int\s+(?:0x)?[0-9a-fA-F]+|iret[qd]?|reti|svc|hvc|smc)\b|^[ \t]*(?:vector|handler|isr)_[a-zA-Z0-9_]+:",
            re.M | re.I,
        ),
        # 33. dependency_injection
        "dependency_injection": None,
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(
            r"^[ \t]*(?:%macro|\.macro|%endmacro|\.endm|%define|\.equ|\.set|#define)\b",
            re.M | re.I,
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Raw memory addressing and dereferencing.
        "pointers": re.compile(r"(?i)(?:byte|word|dword|qword)[ \t]+ptr[ \t]*\[[^\]]*\]|\[[^\]]+\]"),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(
            r"\b(?:call|bl)\s+(?:_?malloc|_?calloc)\b|\b(?:sys_mmap|sys_brk)\b",
            re.I,
        ),
        # 37. inline_asm
        "inline_asm": None,  # This is base assembly.
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(?:call|bl)\s+(?:log_info|log_error|log_warn|log_debug|syslog)\b",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\b(?:call|bl)\s+(?:printf|puts|sys_write)\b", re.I),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"(?i)\b(?:byte|word|dword|qword)[ \t]+ptr\b"),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        # Hard execution destruction and unrecoverable hardware exceptions. [cite: 780]
        "panics_and_aborts": re.compile(r"(?i)\b(?:hlt|ud2|brk|svc|int[ \t]+3)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        # Forcing hardware threads to sleep or pause execution. [cite: 781]
        "thread_sleeps": re.compile(r"(?i)\b(?:pause|hlt|wfi|wfe)\b"),
        # 43. bitwise_ops (Bitwise Operations)
        # Low-level byte manipulation natively supported by the instruction set. [cite: 782]
        "bitwise_ops": re.compile(r"(?i)\b(?:and|or|xor|not|shl|shr|sal|sar|rol|ror|lsl|lsr|asr)\b"),
        # 44. sync_locks (Resource Management & Stability)
        # Explicit hardware coordination to prevent race conditions (e.g., atomic instructions, memory barriers). [cite: 783]
        "sync_locks": re.compile(r"(?i)\b(?:lock|xchg|cmpxchg|stxr|ldxr|dmb|dsb|isb)\b"),
        # 45. immutability_locks (Immutability Constraints)
        # Explicit locking of data to prevent mutation (e.g., read-only data sections or constants). [cite: 784]
        "immutability_locks": re.compile(r"(?i)\b(?:equ|\.rodata|\.rdata)\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        # Assembly relies on manual memory management via standard instructions, lacking dedicated cleanup APIs. [cite: 785]
        "cleanup": re.compile(r"\b(?:call|bl)\s+_?free\b", re.I),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Logic hidden from view via visibility directives. [cite: 786]
        "encapsulation": re.compile(r"^[ \t]*(?:\.local|\.private)\b", re.M | re.I),
        # 48. listeners (Event Listeners / Observers)
        # Assembly relies on hardware interrupts rather than high-level listener subscriptions. [cite: 787]
        "listeners": None,
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # Framework code that explicitly bypasses verification. [cite: 788]
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        # serialization_parsing: Assembly has no native or universal JSON/XML/YAML
        # parsing construct -- unlike malloc/free/printf there is no single
        # ubiquitous libc convention for this, so per Strict Feature Parity
        # (Rule 4) this stays None rather than forcing a fit.
        "serialization_parsing": None,
        # regex_execution: No native regex instruction; the realistic native
        # equivalent is a call into the POSIX libc regex API.
        "regex_execution": re.compile(
            r"\b(?:call|bl)\s+_?(?:regcomp|regexec|regfree|re_search|re_match)\b",
            re.I,
        ),
        # time_date_logic: rdtsc/rdtscp are real native timestamp-counter
        # instructions; also covers calls into the libc time API.
        "time_date_logic": re.compile(
            r"\brdtscp?\b|\b(?:call|bl)\s+_?(?:time|clock|clock_gettime|gettimeofday)\b",
            re.I,
        ),
        # ipc_rpc_bridges: Raw process/IPC syscalls and their libc wrappers.
        # Distinct from `io`'s generic sys_read/sys_open/syscall tokens.
        "ipc_rpc_bridges": re.compile(
            r"\b(?:call|bl)\s+_?(?:fork|execve|pipe|socket|clone)\b|\bsys_(?:fork|execve|pipe|clone)\b",
            re.I,
        ),
    },
}
