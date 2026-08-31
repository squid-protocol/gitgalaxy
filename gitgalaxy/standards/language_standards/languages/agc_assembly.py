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
        "target_version": "Apollo Guidance Computer (Luminary 099 / Comanche 055 - Apollo 11)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard Apollo Guidance Computer digitized source files.
    "extensions": [".agc"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: AGC code is hardware-level; no extensionless exact configurations exist.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and emulator/assembler tools to lock in the historical context.
    "discriminators": [".agc", "yaYUL"],
    # EXECUTION SIGNATURES: AGC code is hardware-level or emulator-resident; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: Digitized source uses '#' for line-level Commented / Non-Executable Text.
    "lexical_family": "line_exclusive",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. EXCLUDES fatal alarms (bailout_hits).
        "branch": re.compile(
            r"\b(TC|TCF|BZF|BZMF|BZE|BMN|BPL|BMI|CCS|RESUME|RETURN|TCR|OVSK|BVBZ|CALL|GOTO)\b",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Safely captures hardware registers (A, Q, L, Z) ONLY when they are
        # explicitly coupled to an AGC mathematical/memory opcode.
        # Also captures the Bank assignment declarations.
        # BUG FIX (epic #813/#857): AUG/DIM/INCR (real register-mutating
        # instructions already recognized by this file's own
        # `state_mutation` rule) were missing from the opcode list, so
        # `AUG A`/`DIM Q`/`INCR A` -- real, common coupling of a hardware
        # register to an instruction -- were invisible.
        "args": re.compile(
            r"\b(?:[EFB]BANK)="
            r"|"
            r"\b(?:CA|CS|TS|AD|SU|MULT|DV|MASK|DXCH|LXCH|QXCH|XCH|INDEX|AUG|DIM|INCR|CCS)[ \t]+(?:A|Q|L|Z)\b",
            re.I,
        ),
        # 3. linear (Sequential Boundaries)
        # Standard instruction flow and data markers.
        "structural_boundaries": re.compile(
            r"\b(CA|CAF|CS|TS|DXCH|LXCH|QXCH|XCH|AD|SU|MULT|DV|MASK|CCS|SETLOC|BANK|COUNT|ADRES|OCTAL|2OCT|DEC|2DEC|BLOCK|ERASE)\b",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # Subroutine entry points anchoring logic blocks.
        # BUG FIX: the lookahead's `\s+` can cross a newline (Rule 5),
        # so a bare label on its own line (nothing else on that line)
        # could get falsely bound to an unrelated opcode several blank
        # lines later -- confirmed "MYLABEL\n\n\n\tTC INTERNAL\n"
        # incorrectly captured MYLABEL. Real AGC label+opcode pairs are
        # always on the same physical line (fixed-column YUL/GAP
        # format); bounded to `[ \t]+`.
        # BUG FIX (epic #813/#857): the opcode whitelist was a small,
        # ad hoc subset of the real AGC instruction set -- missing
        # instructions this SAME file's own sibling rules already
        # recognize as legitimate (`args`'s CA|CS|TS|AD|SU|MULT|DV|MASK|
        # DXCH|LXCH|QXCH|XCH|INDEX, `branch`'s TCF|BZE|BMN|RESUME|
        # RETURN|TCR|GOTO|OVSK|BVBZ, `safety`'s RELINT|EDRUPT,
        # `state_mutation`'s INCR|AUG|DIM|DAS), so a label followed by
        # ANY of these real, common opcodes was invisible as a
        # subroutine entry. Confirmed empirically against the real
        # Apollo 11 (Luminary/Comanche) source corpus in
        # language-crucible: the old pattern matched 609 label+opcode
        # pairs across the corpus; `CAF` alone (Clear and Add Fixed --
        # arguably the single most common AGC instruction after
        # TC/CS/TS/CA, 94 occurrences in this corpus) was entirely
        # missing. Widened to the union of opcodes already vetted
        # elsewhere in this file, confirmed against the real corpus to
        # raise total matches to 812 (+33%) with zero new false
        # positives against data/constant pseudo-ops (OCT/OCTAL/DEC/
        # 2DEC/ADRES/CADR/EQUALS/etc. all correctly stay excluded --
        # those mark data declarations, not subroutine entries).
        "func_start": re.compile(
            r"^([A-Z0-9_-]+)(?=[ \t]+(?:TC|TCF|CA|CAF|CS|TS|DXCH|LXCH|QXCH|XCH|CCS|DLOAD|STORE|CALL|INDEX|"
            r"EXTEND|INHINT|RELINT|EDRUPT|BZF|BZMF|BPL|BMI|BZE|BMN|RESUME|RETURN|TCR|GOTO|OVSK|BVBZ|"
            r"AD|ADS|SU|MULT|DV|MASK|INCR|AUG|DIM|DAS|RVQ)\b)",
            re.M | re.I,
        ),
        # 5. class_start
        # AGC lacks native objects.
        "class_start": None,
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        # Real-time safety guards and interrupt control.
        "safety": re.compile(
            r"\b(INHINT|RELINT|TC\s+DOWNRUPT|CS\s+ERESTORE|MUST\s+RESTORE|EDRUPT)\b",
            re.I,
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Bypassing predictable flow or task management risks.
        "safety_bypasses": re.compile(r"\b(TC\s+JOBSLEEP|TC\s+JOBWAKE|TCF\s+2|TASKOVER|TCF\s+ADRERR)\b", re.I),
        # 8. danger (High-Risk Execution / System Calls)
        # High-risk failure states and alarms. EXCLUDES MOD history (Phase 2 debt).
        "high_risk_execution": re.compile(r"\b(CURTAINS|SOFTWARE\s+RESTART|SYSTEM_FAILURE|WHIMPER|HALT)\b", re.I),
        # 9. io (I/O & Network Boundaries)
        # Hardware I/O bridging to the Command/Lunar Module.
        "io": re.compile(r"\b(DSKY|CHANNEL|READ|WRITE|V\d+N\d+|OUT\d+|IN\d+)\b", re.I),
        # 10. api (Public Surface Area)
        # Global labels and externally visible entry points.
        "api": re.compile(
            r"^[A-Z0-9_-]+\s+EQUALS|^[ \t]*(?:SUBROUTINE|BEXT|EXTEND)\b",
            re.M | re.I,
        ),
        # 11. flux (State Mutation)
        # Direct state mutation and register storage.
        "state_mutation": re.compile(
            r"\b(TS|DXCH|LXCH|QXCH|XCH|INCR|AUG|DIM|WRSUB|AUGMENT|DIMINISH|STORE|STQ|STCALL|DAS)\b",
            re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(r"(?i)#[ \t]*(?:TCF|CCS|INDEX|BZF|BZN|CA|CS)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(
            r"^#\s*(?:Page|MOD\s+(?:BY|NO)|FUNCTIONAL\s+DESCRIPTION|SUBROUTINE|PURPOSE|CALLING\s+SEQUENCE|AUTHOR|PROGRAM|REVISION)",
            re.M | re.I,
        ),
        # 14. test (Testing & Assertions)
        # System integrity verifications and self-checks.
        "test": re.compile(
            r"\b(TC\s+ALARM2|SELFCHECK|ROPECHK|ERASCHK|CNTRCHK|CHECK|TC\s+BANKJUMP)\b",
            re.I,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # Priority multitasking scheduler and task management.
        "concurrency": re.compile(
            r"\b(PRIO[1-9]|EXEC|TC\s+NOVAC|TC\s+WAITLIST|TC\s+FINDVAC|ENDOFJOB|PHASCHNG|AWAKE|SLEEP|VARDELAY)\b",
            re.I,
        ),
        # 16. ui_framework (UI / View Components)
        # DSKY (Display/Keyboard) UI verbs and nouns.
        "ui_framework": re.compile(r"\b(V\s+\d+|N\s+\d+|NOUN|VERB|ENTER|PROCEED)\b", re.I),
        # 17. closures
        "closures": None,
        # 18. globals (Global / Shared State)
        # Memory division markers.
        "globals": re.compile(
            r"\b(ERASABLE\s+MEMORY|FIXED\s+MEMORY|WORKING-STORAGE|COMMON|FLAGWRD\d+|BIT\d+)\b",
            re.I,
        ),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions
        "comprehensions": None,
        # 22. scientific (Numerical / Compute Libraries)
        # Vector math and orbital navigation interpreter routines.
        "scientific": re.compile(
            r"\b(VAD|VSUB|BDSU|DDV|DMP|DSU|SQRT|NORM|SIGN|ABS|SIN|COS|ASIN|ACOS|SPCOS|SPSIN|DOT|CROSS|UNIT|ABVAL|VXV|VXM|MXV)\b",
            re.I,
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Self-modifying logic and VM entry.
        "reflection_metaprogramming": re.compile(r"\b(INDEX|TC\s+INTPRET|DXCH\s+0000|RVQ)\b", re.I),
        # 24. import (Dependency Inclusions)
        "import": re.compile(r"\b(BANK|SETLOC|EBANK=)\b", re.I),
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:BANK[ \t\n]+|SETLOC[ \t\n]+|EBANK=[ \t\n]*)([A-Za-z0-9_]+)",
            re.I | re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(
            r"^#\s*(?:MOD\s+BY|AUTHOR|CREATED\s+BY|MAINTAINER|Contact)\s*[:\-]\s*(.*)",
            re.M | re.I,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        # Linkage to MIT GSOP or mission versions.
        "spec_exposure": re.compile(
            r"\b(GSOP|LUMINARY|COMANCHE|COLOSSUS|SUNDISK|SUNBURST|PCR\s*\d+|PCN\s*\d+|SPEC\s*-\s*\d+|#\s*REF:)\b",
            re.I,
        ),
        # 31. ssr_boundaries
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Hardware interrupt vectors (Rupts).
        "events": re.compile(
            r"\b(RUPT|TIME1|TIME2|KEYRUPT|UPRUPT|DOWNRUPT|RADAR|OPTIC|HANDRUPT|ERRUPT)\b",
            re.I,
        ),
        # 33. dependency_injection
        "dependency_injection": None,
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(r"^[ \t]*(?:MACRO|ENDMAC|DEFINE)\b", re.M | re.I),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": re.compile(r"\b(?:INDEX|INDIRECT|POINTER|CADR|FCADR|ECADR)\b|\*[A-Z0-9_-]+", re.I),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(r"\b(?:ERASABLE|FIXED|EQUALS|SHARE)\b", re.I),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        # Spacecraft downlink routines.
        "telemetry": re.compile(r"\b(DNTM|DOWNLINK|TELEM|TM|DUMPTEL|TM\s+WORD)\b", re.I),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
        "debug_prints": re.compile(r"\b(?:FLASH|PINBALL|OUT\d+)\b", re.I),
        # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"\bEXTEND\b", re.I),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(POODOO|BAILOUT|TC\s+ALARM|ABORT)\b", re.I),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\b(TC\s+JOBSLEEP|VARDELAY)\b", re.I),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"\b(MASK|AD|SU|MULT|DV)\b", re.I),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(INHINT|RELINT|LOCK|UNLOCK)\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\bFIXED\s+MEMORY\b", re.I),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(ENDOFJOB|RESUME|EXIT)\b", re.I),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Internal task-local labels or non-global tags.
        # BUG FIX: required a lowercase-starting label, but authentic
        # AGC assembly source is uppercase-only (per this section's own
        # convention -- every other rule here uses `re.I`, and
        # func_start's own capture class is `[A-Z0-9_-]+`) -- confirmed
        # a realistic label ("MYLABEL") never matched at all. Widened
        # to accept any case.
        "encapsulation": re.compile(r"^[ \t]*[A-Za-z0-9_][a-zA-Z0-9_.]*", re.M),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(EVENT\s+WAIT|TC\s+WAITLIST)\b", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": None,
    },
}
