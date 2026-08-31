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
        "target_version": "ABAP 2025 (ABAP Cloud / RAP / Modern 7.5x+ Syntax)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard Advanced Business Application Programming sources and modern Core Data Services.
    "extensions": [".abap", ".asddls"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: ABAP is executed within the SAP environment; no extensionless exact configurations exist.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: SAP deployment artifacts acting as disambiguation anchors.
    "discriminators": [".abap", "package.devc.xml", ".apc"],
    # EXECUTION SIGNATURES: Executed exclusively within the SAP NetWeaver/ABAP platform; no shebangs exist.
    "shebangs": [],
    # UPGRADED: Maps to Family 7 (The Positional Ancients)
    # Rationale: Strictly fixed-format legacy constraints. The engine must monitor Column 1
    # for an asterisk '*' to identify line-level Commented / Non-Executable Text, while allowing '"' for inline.
    # ABAP code uses " as inline comment, requiring a specialized positional family
    "lexical_family": "positional_abap",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow. Includes modern COND/SWITCH expressions.
        "branch": re.compile(
            r"^[ \t]*(IF|ELSE|ELSEIF|CASE|WHEN|WHILE|DO|LOOP\s+AT|TRY|CATCH|CLEANUP|CHECK|EXIT|CONTINUE|RETURN|COND|SWITCH)\b",
            re.I | re.M,
        ),
        # 2. args: Parameters / Coupling. Captures explicit parameter binding keywords.
        # BUG FIX (#1917, args regex correctness): two independent issues found while
        # investigating the tri-comparison chart's per-function args count.
        #   1. The trailing identifier had no `!?` -- ABAP's classic parameter-name
        #      escape prefix (`!iv_url TYPE string`, used to avoid a keyword collision,
        #      extremely common in real code) isn't in `[a-zA-Z_]`, so a clause whose
        #      FIRST declared parameter uses it failed to match AT ALL, silently making
        #      the whole clause invisible to this signal (confirmed: `IMPORTING
        #      !ii_custom_mapping TYPE ...` in abapGit's zcl_abapgit_ajson.clas.abap).
        #   2. `(?:VALUE\s*\([^)]*\)\s+)?[a-zA-Z_][a-zA-Z0-9_-]*` treated VALUE(...) as
        #      an OPTIONAL PREFIX before a still-mandatory trailing identifier, instead
        #      of as its own complete alternative -- so `RETURNING VALUE(ro_instance)
        #      TYPE ...` matched through to the literal word "TYPE", mis-capturing it as
        #      if it were a second parameter name. Restructured as a real alternation
        #      (VALUE(...) OR a bare identifier, never both in sequence) so the match
        #      ends where the real parameter reference ends.
        "args": re.compile(
            r"\b(IMPORTING|EXPORTING|CHANGING|RETURNING|RECEIVING|EXCEPTIONS)\s+(?!TYPE\b)"
            r"(?:VALUE\s*\([^)]*\)|!?[a-zA-Z_][a-zA-Z0-9_-]*)",
            re.I,
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and constants.
        "structural_boundaries": re.compile(
            r"^[ \t]*(DATA|TYPES|FIELD-SYMBOLS|CLASS|INTERFACE|METHOD|FORM|FUNCTION|MODULE|REPORT|PROGRAM|IMPORT|EXPORT)(?![(-])\b",
            re.I | re.M,
        ),
        # 4. func_start: Executable Logic Anchors. Anchors executable logic. EXCLUDES structural headers.
        "func_start": re.compile(
            r"^[ \t]*(?!(?:CLASS|INTERFACE|DATA|TYPES|CONSTANTS)\b)(?:METHOD|FORM|FUNCTION|MODULE)\s+([a-zA-Z0-9_~-]+)(?=[ \t\n\.]|$)",
            re.I | re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Defines OO boundaries and RAP CDS Entities.
        # BUG FIX: `VIEW` and `ENTITY` were mutually-exclusive alternatives,
        # but the standard modern RAP syntax is `DEFINE VIEW ENTITY <name>`
        # (both words together, exactly what this dict's target_version
        # claims to cover) -- so the regex matched `VIEW` as the keyword
        # and then captured the literal word `ENTITY` as if it were the
        # entity name. `ENTITY` is now optional after `VIEW`/`PROJECTION
        # VIEW` instead of a same-tier alternative.
        "class_start": re.compile(
            r"^[ \t]*(?:CLASS|INTERFACE)\s+([a-zA-Z0-9_-]+)(?=[ \t]+DEFINITION|[ \t\n\.]|$)"
            r"|^[ \t]*DEFINE\s+(?:ROOT\s+)?(?:(?:VIEW|PROJECTION\s+VIEW)(?:\s+ENTITY)?|(?:ABSTRACT\s+|CUSTOM\s+)?ENTITY|BEHAVIOR\s+FOR)\s+([a-zA-Z0-9_-]+)",
            re.I | re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Binding checks and authorization boundaries.
        "safety": re.compile(
            r"\b(TRY|CATCH|CLEANUP|ASSERT|AUTHORITY-CHECK|IS\s+BOUND|IS\s+ASSIGNED|IS\s+NOT\s+INITIAL|FINAL|READ-ONLY)\b",
            re.I,
        ),
        # 7. safety_neg: Safety Bypasses. Actively bypassing safety (casting/unchecked generics).
        "safety_bypasses": re.compile(
            r"\b(UNASSIGNED|TYPE\s+ANY|TYPE\s+REF\s+TO\s+DATA|IGNORE\s+ERRORS)\b|ASSIGN\s+[^\n;]+\s+TO\s+<[^>]+>\s+CASTING",
            re.I,
        ),
        # 8. danger: High-Risk Execution. Raw SQL/Kernel bypasses and mass deletion.
        "high_risk_execution": re.compile(
            r"\b(SYSTEM-CALL|EXEC\s+SQL|DELETE\s+FROM|TRUNCATE|GENERATE\s+SUBROUTINE\s+POOL)\b",
            re.I,
        ),
        # 9. io: I/O & Network Boundaries. Database interaction and File datasets.
        "io": re.compile(
            r"^[ \t]*(SELECT|INSERT\s+(?:INTO\b)?|UPDATE\b|MODIFY\b|OPEN\s+DATASET|TRANSFER|READ\s+DATASET|CLOSE\s+DATASET|CL_HTTP_CLIENT|CL_WEB_HTTP_CLIENT)\b",
            re.I | re.M,
        ),
        # 10. api: Public Surface Area. Exposed RFCs, OData publishing, and Public sections.
        # BUG FIX: `@OData\.publish` is `@`-prefixed -- the shared
        # leading \b could only fire when a word char immediately
        # preceded the `@`, never true for how this annotation is
        # actually written. Never matched at all.
        "api": re.compile(
            r"\b(?:REMOTE\s+FUNCTION|DEFINE\s+VIEW|DEFINE\s+SERVICE|EXPOSED|PUBLIC\s+SECTION)\b|@OData\.publish",
            re.I,
        ),
        # 11. flux: State Mutation. State mutation (The core of ABAP data manipulation).
        "state_mutation": re.compile(
            r"^[ \t]*(MOVE|MOVE-CORRESPONDING|APPEND|MODIFY\s+TABLE|DELETE\s+TABLE)\b|^[ \t]*INSERT\s+[^\n;]+\s+INTO\s+TABLE",
            re.I | re.M,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural logic (supports * and ").
        "dead_code": re.compile(
            r'^[ \t]*\*[ \t]*(?:DATA|METHOD|IF|SELECT|WRITE)\b|"[ \t]*(?:DATA|METHOD|IF|SELECT|WRITE)\b',
            re.I | re.M,
        ),
        # 13. doc: Structured Documentation. ABAP Doc annotations and metadata headers.
        # BUG FIX: the trailing `\b` sat right after a literal `:` (Rule 9,
        # mirror case). Real headers are written as "AUTHOR: Jane Doe" --
        # the space after `:` means both sides of that position are
        # non-word, so `\b` never fired and the realistic form never
        # matched. `:` is already self-delimiting; `\b` dropped.
        "doc": re.compile(
            r'^"!\s*@(?:parameter|raising|return)|\b(?:AUTHOR|DESCRIPTION|PURPOSE|REMARKS):',
            re.I | re.M,
        ),
        # 14. test: Testing & Assertions. ABAP Unit markers and test-injection.
        "test": re.compile(
            r"\b(FOR\s+TESTING|RISK\s+LEVEL|DURATION\s+SHORT|CL_ABAP_UNIT_ASSERT|ZCL_ABAP_UNIT)\b",
            re.I,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. Async RFCs and background tasks.
        # BUG FIX (Rule 9, mirror case): ENQUEUE_/DEQUEUE_ end in `_`, a
        # word character, and real function-module names always continue
        # with more word characters right after (ENQUEUE_FOO) -- so the
        # shared trailing `\b` could never fire for them (both sides of
        # that position are word chars). Pulled out of the group with the
        # trailing `\b` dropped, since the prefix is already unambiguous.
        "concurrency": re.compile(
            r"\b(?:STARTING\s+NEW\s+TASK|WAIT\s+UP\s+TO)\b|\b(?:ENQUEUE_|DEQUEUE_)"
            r"|CALL\s+FUNCTION\s+[^\n;]+\s+IN\s+BACKGROUND\s+TASK",
            re.I,
        ),
        # 16. ui_framework: UI / View Components. Screen programming and HTML viewers.
        "ui_framework": re.compile(
            r"\b(CALL\s+SCREEN|SELECTION-SCREEN|PARAMETERS|WDDOMODIFYVIEW|CL_GUI_HTML_VIEWER|CL_SALV_TABLE)\b",
            re.I,
        ),
        # 17. closures: Closures / Anonymous Functions. (ABAP lacks anonymous closures).
        "closures": None,
        # 18. globals: Global / Shared State. Global program data and the system registry.
        "globals": re.compile(r"\b(TABLES|STATICS|CLASS-DATA|SY-[A-Z0-9_]+)\b", re.I),
        # 19. decorators: Decorators / Annotations. CDS and class annotations.
        "decorators": re.compile(r"@[A-Za-z0-9_.]+(?:\([^)]*\))?", re.I),
        # 20. generics: Generics / Type Parameters. Generic data references and field symbols.
        "generics": re.compile(
            r"\b(TYPE\s+ANY(?:\s+TABLE)?|TYPE\s+INDEX\s+TABLE|TYPE\s+STANDARD\s+TABLE|TYPE\s+REF\s+TO\s+DATA)\b",
            re.I,
        ),
        # 21. comprehensions: Iterators / Comprehensions. Modern constructor expressions.
        "comprehensions": re.compile(
            r"\b(?:VALUE|REDUCE|FILTER|CORRESPONDING|NEW)\s+#?\s*\(|\bFOR\s+[a-zA-Z_]\w*\s+IN\b",
            re.I,
        ),
        # 22. scientific: Numerical / Compute Libraries. Standard numerical built-ins.
        "scientific": re.compile(
            r"\b(ABS|SQRT|LOG|EXP|SIN|COS|TAN|ROUND|CEIL|FLOOR|DECFLOAT16|DECFLOAT34)\b",
            re.I,
        ),
        # 23. heat_triggers: Metaprogramming & Reflection. RTTS and Dynamic assignment logic.
        "reflection_metaprogramming": re.compile(
            r"\b(CL_ABAP_TYPEDESCR|CL_ABAP_CLASSDESCR|ASSIGN\s+\([a-zA-Z0-9_-]+\)\s+TO|GENERATE\s+SUBROUTINE\s+POOL)\b",
            re.I,
        ),
        # 24. import: Dependency Inclusions. Includes and type pools.
        "import": re.compile(r"\b(INCLUDE|TYPE-POOLS)\b", re.I),
        "_dependency_capture": re.compile(r"^[ \t]*(?:INCLUDE|TYPE-POOLS)[ \t\n]+([A-Za-z0-9_/]+)", re.I | re.M),
        # 25. ownership: Authorship indicators.
        "ownership": re.compile(
            r"(?:AUTHOR|CREATED\s+BY|MAINTAINER|Tim Berners-Lee):\s+([^\n]+)",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags and architecture docs.
        "spec_exposure": re.compile(
            r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]|\b(?:WorldWideWeb|RFC|W3C|CERN|TBL|ENQUIRE)\b",
            re.I,
        ),
        # 31. ssr_boundaries: View Horizon. ICF and BSP request handlers.
        "ssr_boundaries": re.compile(
            r"\b(IF_HTTP_EXTENSION~HANDLE_REQUEST|CL_BSP_CONTEXT|CL_BSP_RUNTIME|IF_HTTP_REQUEST|IF_HTTP_RESPONSE|HTML_STRING)\b",
            re.I,
        ),
        # 32. events: Pub/Sub Network. Native OO event architecture.
        "events": re.compile(r"\b(RAISE\s+EVENT|SET\s+HANDLER)\b|FOR\s+EVENT\s+[^\n;]+\s+OF", re.I),
        # 33. dependency_injection: Inversion of Control. BAdIs and Test Doubles.
        "dependency_injection": re.compile(r"\b(GET\s+BADI|CALL\s+BADI|CL_BADI_BASE|CL_ABAP_TESTDOUBLE)\b", re.I),
        # 34. macros: Preprocessor Hooks. ABAP macro definitions.
        "macros": re.compile(
            r"^[ \t]*DEFINE\s+[a-zA-Z0-9_-]+\.|^[ \t]*END-OF-DEFINITION\s*\.",
            re.I | re.M,
        ),
        # 35. pointers: Memory Map. Field-Symbols and data references.
        "pointers": re.compile(r"<[A-Za-z0-9_-]+>|->\*|\b(?:GET\s+REFERENCE\s+OF|REF\s+TO)\b", re.I),
        # 36. memory_alloc: Manual Memory Management. Heap allocations.
        "memory_alloc": re.compile(r"\b(CREATE\s+OBJECT|CREATE\s+DATA|FREE|CLEAR)\b", re.I),
        # 37. inline_asm: Bare Metal.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics.
        "telemetry": re.compile(r"\b(BAL_LOG_CREATE|BAL_DB_SAVE|CL_BALI_LOG|CL_BALI_MSG_SETTER)\b", re.I),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
        "debug_prints": re.compile(r"^[ \t]*(WRITE)\b", re.I | re.M),
        # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit casting and conversions.
        "explicit_casts": re.compile(
            r"\b(?:CAST|CONV)\s*[a-zA-Z0-9_~-]*\s*#?\s*\(|ASSIGNING\s+<[^>]+>\s+CASTING",
            re.I,
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting execution or error messages.
        "panics_and_aborts": re.compile(
            r'\b(RAISE\s+EXCEPTION|MESSAGE\s+[^\n;]+\s+TYPE\s+[\'"][EX][\'"]|LEAVE\s+PROGRAM)\b',
            re.I,
        ),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) Thread sleep.
        "thread_sleeps": re.compile(r"\bWAIT\s+UP\s+TO\b", re.I),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"\b(BIT-AND|BIT-OR|BIT-XOR|BIT-NOT)\b", re.I),
        # 44. sync_locks (Resource Management & Stability)
        # BUG FIX (Rule 9, mirror case): see the matching fix in
        # `concurrency` above -- the trailing `\b` right after `_` could
        # never fire since real function-module names always continue
        # with more word characters (ENQUEUE_FOO).
        "sync_locks": re.compile(r"\b(?:ENQUEUE_|DEQUEUE_)", re.I),
        # 45. immutability_locks (Immutability Constraints) Immutability (constants).
        "immutability_locks": re.compile(r"\b(CONSTANTS|FINAL|READ-ONLY)\b", re.I),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"^[ \t]*(FREE|CLEAR|CLOSE\s+DATASET)\b", re.I | re.M),
        # 47. encapsulation (Encapsulation / Access Modifiers)
        "encapsulation": re.compile(r"\b(PRIVATE\s+SECTION|PROTECTED\s+SECTION)\b", re.I),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\bFOR\s+EVENT\s+[^\n;]+\s+OF\b", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(IGNORE)\b", re.I),
    },
}
