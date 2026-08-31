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
        "target_version": "Enterprise COBOL 6.4 (IBM) & GnuCOBOL 3.2",
        "last_updated": "2026-03-10",
        "blueprint_version": "v5.1",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard COBOL source files and copybooks (.cpy) which act as legacy header files.
    "extensions": [".cbl", ".cob", ".cpy", ".cobol", ".pco", ".cut"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Mainframe environments do not typically use extensionless execution scripts.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and Job Control Language (.jcl) files which orchestrated legacy COBOL execution.
    "discriminators": [".cbl", ".cob", ".cpy", ".jcl"],
    # EXECUTION SIGNATURES: Interpreters found on Line 1 (primarily for modern GnuCOBOL scripting).
    "shebangs": ["cobc"],
    # UPGRADED: Maps to Family 7 (The Positional Ancients)
    # Rationale: Strictly fixed-format. The engine must monitor Column 7 for an asterisk '*'
    # or slash '/' to identify line-level Commented / Non-Executable Text.
    "lexical_family": "positional_anchored",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: Entscheidungslogik. Control flow that splits execution paths.
        "branch": re.compile(
            r"\b(IF|ELSE|EVALUATE|WHEN|PERFORM|UNTIL|VARYING|TIMES|DEPENDING\s+ON|ON\s+EXCEPTION|AT\s+END|INVALID\s+KEY|ON\s+SIZE\s+ERROR|ON\s+OVERFLOW)\b",
            re.I,
        ),
        # 2. args: Parameters / Coupling. Captures USING and RETURNING signatures in PROCEDURE division or CALLs.
        # BUG FIX (epic #813/#854): the parameter-name repetition had no
        # exclusion for the literal word "RETURNING" -- so
        # `PROCEDURE DIVISION USING WS-A RETURNING WS-B.` (declaring both
        # a parameter AND a return value in one division header,
        # extremely common real Enterprise COBOL/GnuCOBOL) had USING's
        # own capture bleed straight through "RETURNING" and swallow
        # WS-B too, instead of stopping at the clause boundary. Fixed
        # with a negative lookahead excluding "RETURNING" from the
        # parameter-name alternative, so `finditer` now correctly yields
        # two separate matches (USING -> WS-A, RETURNING -> WS-B).
        "args": re.compile(
            r"\b(?:USING|RETURNING)\s+((?:(?:BY\s+(?:REFERENCE|CONTENT|VALUE)\s+)?(?!RETURNING\b)[A-Z0-9_-]+\s*,?){0,20})",
            re.I,
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining straight-line execution flow.
        # EXCLUDES access modifiers (GLOBAL, EXTERNAL) to prevent Structural Complexity Inflation.
        "structural_boundaries": re.compile(
            r"\b(DIVISION|SECTION|EXIT|CONTINUE|GOBACK|ACCEPT|XML\s+PARSE|JSON\s+GENERATE|DISPLAY|STOP\s+RUN)\b",
            re.I,
        ),
        # 4. func_start: Executable Logic Anchors. Anchors logic blocks (Paragraphs and Sections).
        # =====================================================================
        # [ CONTEXT: COBOL FUNCTION/PARAGRAPH AST EXTRACTOR & REDOS SHIELD]
        # PURPOSE: Anchors executable logic blocks (Paragraphs and Sections) in COBOL.
        # VULNERABILITY: COBOL spans 60 years of formatting rules (Fixed vs Free format).
        #   Without strict column boundaries, standard verbs or data definitions
        #   (like 01 levels) resting against the margin will hallucinate False Positives.
        # THE "IRON WALL" FIX: Combines strict leading-margin allowances with
        #   comprehensive negative lookaheads to explicitly ban COBOL reserved words,
        #   data structures, and Division headers.
        # =====================================================================
        # 4. func_start: Executable Logic Anchors. Anchors logic blocks (Paragraphs and Sections).
        "func_start": re.compile(
            # =====================================================================
            # [ CONTEXT: COBOL FUNCTION/PARAGRAPH AST EXTRACTOR & REDOS SHIELD ]
            # PURPOSE: Anchors executable logic blocks (Paragraphs and Sections) in COBOL.
            #
            # [ THE GREEDY MARGIN TRAP ] (Hard-learned from Pathological Fuzzer):
            # Legacy COBOL uses a 6-character sequence area. Our regex optionally
            # eats these 6 characters: `(?:[0-9a-zA-Z \t]{6}[ \-]?)?`.
            # If a free-format developer writes a paragraph flush against the left
            # margin (e.g., `TargetFunc.`), the regex greedily eats the first 6
            # characters (`Target`) as the sequence number, and captures `Func` as
            # the paragraph name!
            # THE FIX: We injected a strict word boundary `\b` right before the
            # identifier capture group. If the margin-eater chops a word in half,
            # the `\b` fails, forcing the regex engine to backtrack, skip the
            # optional margin-eater, and correctly capture the full word `TargetFunc`.
            # =====================================================================
            # 1. THE HORIZONTAL ANCHOR & FORMAT SHIELD
            # Safely handles strict 80-column punched card formats (6-char sequence)
            # and modern free-format code.
            # The column-7 indicator slot accepts a blank/`-` (continuation), and a
            # `D`/`d` debug flag ONLY when a name-char immediately follows it
            # (`064100D` + `DEBUG-LINE-TEST-03-A`, otherwise captured as
            # `DDEBUG-LINE-TEST-03-A`). The `(?=[A-Za-z])` keeps this narrow: a `D`
            # followed by whitespace (`064000D        PASS.`) is left to the normal
            # path so debug-only paragraph *redefinitions* aren't newly counted --
            # this fix is about a mangled name, not about widening what counts.
            # `*`/`/` (comment, page-eject) are excluded -- prism.py strips those
            # first, and a commented-out paragraph is dead_code, not a func_start.
            # The post-anchor slot is `[ \t]*` -- HORIZONTAL whitespace only, no
            # `\n`. #2480: the old `[ \t\n]*` let `^` (re.M) match on a blank line
            # that prism.py leaves behind after stripping the `*` comment lines that
            # bracket a debug paragraph, then skip forward across the newline INTO
            # the real content line -- PAST the col-1-6 sequence-area shield -- so the
            # sequence number + col-7 `D` were swept into the captured name
            # (`066600DDEBUG-LINE-TEST-05-A` in DB1034.2.cbl:665). Dropping `\n` here
            # fixes it with no loss: `^` already re-anchors on the real line under
            # re.M, and the one genuine vertical gap (name and its `SECTION` keyword
            # on separate physical lines) is consumed by the section-6 lookahead's
            # own `[ \t\n]+SECTION`, not here. Re-adding a blank-line consumer was
            # tried and rejected -- every variant either regressed corpus output or
            # was measurably catastrophic on a whitespace-heavy pathological input.
            # Confirmed against language-crucible v1.2.0
            # (che-che4z_nist_ccvs85/DB1024.2.cbl:640, DB1034.2.cbl:665).
            r"^(?:[0-9a-zA-Z \t]{6}(?:[ \-]|(?<=[0-9])[Dd](?=[A-Za-z]))?)?[ \t]*"
            # 2. THE DATA DIVISION SHIELD
            # Explicitly bans data level indicators (01 through 88).
            # Prevents massive "01 POLICY." data structures from being hallucinated as paragraphs.
            r"(?!(?:01|02|03|04|05|10|15|20|66|77|88)\s+)"
            # 3. THE RESERVED VERB & SCOPE TERMINATOR SHIELD
            # Explicitly bans standard COBOL execution verbs, divisions, and scope terminators (`END-*`).
            # Prevents rogue commands like "PERFORM." from spawning false positive logic anchors.
            r"(?!(?:WORKING-STORAGE|LOCAL-STORAGE|DATA|ENVIRONMENT|IDENTIFICATION|ID|LINKAGE|FILE|DECLARATIVES|"
            r"AUTHOR|DATE-WRITTEN|DATE-COMPILED|INSTALLATION|REMARKS|SECURITY|"
            # #1949 follow-up: SOURCE-COMPUTER/OBJECT-COMPUTER are CONFIGURATION
            # SECTION (ENVIRONMENT DIVISION) header paragraphs, never real PROCEDURE
            # DIVISION logic -- same reserved-header category as INPUT-OUTPUT/
            # CONFIGURATION two lines below, just missing from this list. Surfaced
            # once Mode A stopped discarding single-line bodies (real fix for #1949's
            # own Bug 2): `SOURCE-COMPUTER.  IBM-370.` collapses to one line and was
            # previously masked by that discard guard, not by this shield --
            # confirmed false positive against real corpus source
            # (`cics-banking-sample-application-cbsa/BNKMENU.cbl:23`).
            r"SOURCE-COMPUTER|OBJECT-COMPUTER|"
            r"INPUT-OUTPUT|CONFIGURATION|DISPLAY|CALL|MOVE|COMPUTE|PERFORM|ADD|SUBTRACT|MULTIPLY|"
            r"DIVIDE|INITIALIZE|SET|IF|ELSE|GOBACK|EXIT|STOP|EVALUATE|WHEN|READ|WRITE|REWRITE|"
            # CONTINUE is a no-op statement (COBOL's `pass`); on its own line
            # `CONTINUE.` is `<verb>.`, not a paragraph header. Confirmed FP against
            # language-crucible v1.2.0 (che-che4z_nist_ccvs85/IF4014.2.cbl:30 etc.,
            # cobol-sample_SAMPLE1.cbl). Same class as LOCAL-STORAGE (#1890).
            r"DELETE|OPEN|CLOSE|CONTINUE|PROGRAM-ID|CLASS-ID|SECTION|DIVISION|END-[A-Za-z0-9_-]+)(?=[ \t\n.]))"
            # 4. THE DIVISION/SECTION HEADER SHIELD
            # Bans any word followed immediately by DIVISION (e.g., "PROCEDURE DIVISION").
            # Upgraded to `[ \t\n]+` to prevent vertical ghosting.
            r"(?![A-Za-z0-9_-]+[ \t\n]+DIVISION\b)"
            # 5. THE IDENTIFIER CAPTURE (FUNCTION IDENTIFIER - GROUP 1)
            # [ THE GREEDY MARGIN SHIELD ]: The `\b` forces the engine to evaluate the whole word,
            # preventing the 6-character margin-eater from splitting flush-left identifiers.
            # The `(?<=[0-9]{6}[ \-Dd])` alternative to `\b` lets the name start
            # immediately after a real fixed-format col-1-7 prefix (6-digit sequence
            # + indicator) even when col-7 is a `D` debug flag glued to a word-char
            # name start (`064100D` + `DEBUG-LINE-TEST-03-A`) -- the digit prefix
            # proves it's a genuine sequence area, not the greedy-margin trap
            # (`TargetFunc.`), whose 6 non-digit chars fail this lookbehind.
            # The name must contain at least one letter: a pure-digit token is a
            # stray sequence number, not a paragraph name (a real digit-led name
            # like `0000-MAIN` still matches -- it has letters). Both confirmed FP
            # against language-crucible v1.2.0 (che-che4z_nist_ccvs85/DB1024.2.cbl:640,
            # NC1134.2.cbl:118).
            r"(?:\b|(?<=[0-9]{6}[ \-Dd]))([0-9_-]*[A-Za-z][A-Za-z0-9_-]*)"
            # 6. THE IGNITION & TRAILING ANCHOR (Lookahead)
            # Confirms paragraph/section by looking for an optional "SECTION", then a mandatory ".".
            # Upgraded to `[ \t\n]+` to allow vertical separation between the name and SECTION.
            # THE "SQL GHOST" FIX: `(?:\s|$)` blocks SQL qualifiers (e.g., "POLICY.CUSTOMERNUMBER").
            # BUG FIX (epic #813/#854): SECTION had no allowance for a
            # trailing SEGMENT-NUMBER (`MAIN-PARA SECTION 10.`) -- a real
            # COBOL-68/74-era feature (program segmentation/overlay
            # structuring for early mainframes' limited memory) still
            # accepted by modern compilers for legacy program support.
            # Without it, any segmented section header was entirely
            # invisible. Added an optional 1-2-digit segment number.
            r"(?=(?:[ \t\n]+SECTION(?:[ \t\n]+[0-9]{1,2})?)?[ \t]*\.(?:[ \t\n]|$))",
            re.I | re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Defines structural program and modern OO boundaries.
        # BUG FIX (epic #813/#854), two findings:
        # 1. The lookahead required the entity name to be IMMEDIATELY
        #    followed by a period/newline/EOS, with no allowance for the
        #    standard trailing clauses these paragraphs actually support
        #    -- `PROGRAM-ID. Foo IS INITIAL PROGRAM.`, `PROGRAM-ID. Foo
        #    IS COMMON PROGRAM.`, `CLASS-ID. Foo FINAL.`, `CLASS-ID. Foo
        #    INHERITS Base.`, `INTERFACE-ID. Foo INHERITS Base.` -- all
        #    real, documented Enterprise COBOL syntax -- were entirely
        #    invisible. Fixed with a bounded (max 6) run of additional
        #    space-separated clause words between the captured name and
        #    the terminating period; the loop can't cross into an
        #    unrelated following paragraph since it requires whitespace
        #    before each word and a bare period (not preceded by
        #    whitespace) always stops it at the real statement boundary.
        # 2. That widening itself reopened a DIFFERENT false-positive
        #    vector, caught before shipping: FACTORY./OBJECT. are
        #    standalone structural markers (never followed by a real
        #    name), always immediately followed by a division header
        #    (`FACTORY.\n    IDENTIFICATION DIVISION.`) -- with the
        #    trailing-clause loop now wide enough to eat one extra word,
        #    "IDENTIFICATION"/"PROCEDURE"/etc. got captured as the name
        #    and "DIVISION" got swallowed as if it were a trailing
        #    clause word. Fixed by excluding "DIVISION" from the
        #    trailing-clause loop specifically -- no real PROGRAM-ID/
        #    CLASS-ID/INTERFACE-ID clause ever legitimately contains
        #    that word, since a division header always starts its own
        #    separate paragraph.
        "class_start": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:PROGRAM-ID|CLASS-ID|INTERFACE-ID|FACTORY|OBJECT)\.\s+([A-Za-z0-9_-]+)(?:[ \t\n]+(?!DIVISION\b)[A-Za-z0-9_-]+){0,6}(?=[ \t]*\.|\n|$)",
            re.I | re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Defensive scope terminators and declarative blocks.
        "safety": re.compile(
            r"\b(END-IF|END-PERFORM|END-EVALUATE|END-READ|END-WRITE|END-COMPUTE|END-CALL|DECLARATIVES|VALIDATE|CHECK)\b",
            re.I,
        ),
        # 7. safety_neg: Safety Bypasses. Bypassing logic or unpredictable jumps.
        "safety_bypasses": re.compile(
            r"\b(NEXT\s+SENTENCE|GO\s+TO|CORRESPONDING|ANY\s+LENGTH|OMITTED)\b",
            re.I,
        ),
        # 8. danger: High-Risk Execution. Process-stopping commands and self-modifying code (ALTER).
        "high_risk_execution": re.compile(r"\b(STOP\s+RUN|ALTER|CANCEL)\b", re.I),
        # 9. io: I/O & Network Boundaries. Disk, Database (SQL), and CICS communication.
        "io": re.compile(
            r"\b(READ|WRITE|REWRITE|OPEN|CLOSE|START|DELETE|EXEC\s+SQL|EXEC\s+CICS\s+(?:READ|WRITE|REWRITE|DELETE))\b",
            re.I,
        ),
        # 10. api: Public Surface Area. Exposed linkage points and external entries.
        "api": re.compile(r"\b(ENTRY|LINKAGE\s+SECTION|CALL|INVOKE|EXPORT)\b", re.I),
        # 11. flux: State Mutation. State mutation (The core of COBOL data manipulation).
        "state_mutation": re.compile(
            r"\b(MOVE|COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|SET|INITIALIZE|REPLACE|STRING|UNSTRING)\b",
            re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural logic (Column 7 indicator).
        "dead_code": re.compile(
            r"^(?:.{6}\*|[ \t]*\*>)[ \t]*(?:MOVE|COMPUTE|IF|PERFORM|CALL|EXEC)\b",
            re.I | re.M,
        ),
        # 13. doc: Structured Documentation. Identification metadata and structured comments.
        "doc": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:AUTHOR|DATE-WRITTEN|DATE-COMPILED|REMARKS|INSTALLATION)\.|\*>\s*@(?:param|return|author)",
            re.I | re.M,
        ),
        # 14. test: Testing & Assertions. Unit testing framework markers (ZUnit).
        "test": re.compile(r"\b(ZUNIT|CBLUNIT|ASSERT|TEST-CASE|READY\s+TRACE)\b", re.I),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. CICS Task and resource coordination.
        "concurrency": re.compile(r"\bEXEC\s+CICS\s+(?:ENQ|DEQ|WAIT|START|DELAY)\b", re.I),
        # 16. ui_framework: UI / View Components. Screen sections and CICS maps.
        "ui_framework": re.compile(
            r"\b(SCREEN\s+SECTION|EXEC\s+CICS\s+SEND\s+MAP|DFHMDF|DFHMDI|DFHMSD)\b",
            re.I,
        ),
        # 17. closures: Closures / Anonymous Functions. (COBOL lacks native lambdas).
        "closures": None,
        # 18. globals: Global / Shared State. Global storage and external linkages.
        "globals": re.compile(r"\b(WORKING-STORAGE\s+SECTION|COMMON|GLOBAL|EXTERNAL)\b", re.I),
        # 19. decorators: Decorators / Annotations. (COBOL uses compiler directives).
        "decorators": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*>>\s*(?:IF|ELSE|END-IF|DEFINE|CALL-CONVENTION)",
            re.I | re.M,
        ),
        # 20. generics: Generics / Type Parameters. Parameterized classes (Modern COBOL).
        "generics": re.compile(r"\bCLASS-ID\.\s+[A-Za-z0-9_-]+\s+USING\s+[A-Za-z0-9_-]+", re.I),
        # 21. comprehensions: Iterators / Comprehensions. (Not native to COBOL).
        "comprehensions": None,
        # 22. scientific: Numerical / Compute Libraries. Intrinsic math functions.
        "scientific": re.compile(
            r"\bFUNCTION\s+(?:ACOS|ASIN|ATAN|COS|EXP|FACTORIAL|LOG|LOG10|MOD|RANDOM|SQRT|TAN|VARIANCE)\b",
            re.I,
        ),
        # 23. heat_triggers: Metaprogramming & Reflection. Metaprogramming and memory aliasing.
        "reflection_metaprogramming": re.compile(
            r"\b(REDEFINES|RENAMES|OCCURS\s+DEPENDING\s+ON|EVALUATE\s+TRUE|EXEC\s+CICS|EXEC\s+SQL)\b",
            re.I,
        ),
        # 24. import (Dependency Inclusions)
        # BUG FIX (Strict Feature Parity, Rule 4): this key was missing
        # entirely (not even explicitly None), despite COBOL clearly
        # having a real dependency-inclusion mechanism (COPY/INCLUDE
        # copybooks) -- confirmed by `_dependency_capture` immediately
        # below already correctly extracting these same targets. Every
        # language's rules dict is expected to define every baseline
        # key, using None only where genuinely inapplicable (per
        # how_to_add_a_language.md's Strict Feature Parity rule); a
        # silently absent key is a real schema-completeness gap, not an
        # intentional None.
        "import": re.compile(r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:COPY|INCLUDE)\b", re.I | re.M),
        "_dependency_capture": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:COPY|INCLUDE)[ \t\n]+['\"]?([A-Za-z0-9_-]+)['\"]?",
            re.I | re.M,
        ),
        # 25. ownership: Authorship indicators.
        "ownership": re.compile(r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*AUTHOR\.\s+([^\n]+)", re.I | re.M),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
        # 31. ssr_boundaries: View Horizon. CICS web endpoints.
        "ssr_boundaries": re.compile(r"\bEXEC\s+CICS\s+(?:WEB\s+SEND|DOCUMENT|WEB\s+READ)\b", re.I),
        # 32. events: Pub/Sub Network. Signal handlers and MQ bindings.
        # BUG FIX: the `CALL 'MQPUT'`/`CALL 'MQGET'` alternative shared a
        # trailing `\b` with the word-ending EXEC CICS alternative, but
        # ends in a literal `'` (non-word) -- `\b` right after can only
        # fire if the next char is a word character, never true for the
        # realistic form (`CALL 'MQPUT' USING queue-name.`, whitespace
        # after the closing quote). Pulled out of the shared group.
        "events": re.compile(
            r"\bEXEC\s+CICS\s+(?:SIGNAL|HANDLE\s+CONDITION)\b|CALL\s+'(?:MQPUT|MQGET)'",
            re.I,
        ),
        # 33. dependency_injection: Inversion of Control.
        "dependency_injection": None,
        # 34. macros: Preprocessor Hooks. DEFINE directives.
        "macros": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*DEFINE\s+[A-Z0-9_-]+\.|>>DEFINE",
            re.I | re.M,
        ),
        # 35. pointers: Memory Map. Explicit pointer tracking.
        "pointers": re.compile(
            r"\b(?:POINTER|PROCEDURE-POINTER|FUNCTION-POINTER)\b|\bADDRESS\s+OF\b",
            re.I,
        ),
        # 36. memory_alloc: Manual Memory Management. Heap and CICS allocation.
        "memory_alloc": re.compile(r"\b(?:ALLOCATE|FREE|EXEC\s+CICS\s+(?:GETMAIN|FREEMAIN))\b", re.I),
        # 37. inline_asm: Bare Metal.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics.
        "telemetry": re.compile(r"\b(?:EXEC\s+CICS\s+WRITEQ\s+TD|CEE3DMP|CEEMOUT|CEEDUMP)\b", re.I),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
        "debug_prints": re.compile(r"\b(DISPLAY)\b", re.I),
        # 40. explicit_casts (Explicit Type Casting): Explicit type coercion/casting.
        "explicit_casts": re.compile(r"\b(REDEFINES)\b", re.I),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting execution.
        "panics_and_aborts": re.compile(r"\b(STOP\s+RUN|EXIT\s+PROGRAM|GOBACK)\b", re.I),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits).
        "thread_sleeps": re.compile(r"\bEXEC\s+CICS\s+DELAY\b", re.I),
        # 43. bitwise_ops (Bitwise Operations) (Modern intrinsic bitwise).
        "bitwise_ops": re.compile(r"\bFUNCTION\s+(?:BIT-AND|BIT-OR|BIT-XOR|BIT-NOT)\b", re.I),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\bEXEC\s+CICS\s+ENQ\b", re.I),
        # 45. immutability_locks (Immutability Constraints) Immutability.
        "immutability_locks": re.compile(r"\b(CONSTANT)\b", re.I),
        # 46. cleanup (Resource Cleanup / Teardown) Resource release.
        "cleanup": re.compile(r"\b(CLOSE|FREE|END-DECLARATIVES)\b", re.I),
        # 47. encapsulation (Encapsulation / Access Modifiers)
        "encapsulation": re.compile(r"\b(LOCAL-STORAGE\s+SECTION|PRIVATE)\b", re.I),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(?:MQGET|EXEC\s+CICS\s+RECEIVE)\b", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(IGNORE)\b", re.I),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (COBOL Specifics) ---
        "serialization_parsing": re.compile(
            r"(?i)\b(UNSTRING|STRING|JSON\s+PARSE|JSON\s+GENERATE|XML\s+PARSE|XML\s+GENERATE)\b"
        ),
        "regex_execution": re.compile(
            r"(?i)\b(INSPECT|TALLYING|REPLACING)\b"
        ),  # COBOL's hardware-level string manipulation engine
        # BUG FIX (severe ReDoS): `\s+.*\s+FROM` has three adjacent
        # quantifiers whose character sets overlap (`.` matches
        # whitespace too), so the engine can partition the space between
        # the receiving-identifier and the two `\s+`s in exponentially
        # many ways before finding `FROM` -- confirmed 9+ seconds at just
        # n=2000 (far worse than the typical ~4x/doubling shape). Real
        # COBOL syntax only ever has a single identifier there, so
        # replaced the unbounded `.*` with a real identifier character
        # class, which is both correct and eliminates the ambiguity.
        "time_date_logic": re.compile(
            r"(?i)\bACCEPT\s+[A-Za-z0-9_-]+\s+FROM\s+(?:DATE|TIME|DAY)\b|\b(?:CURRENT-DATE|WHEN-COMPILED)\b"
        ),
        # BUG FIX: `CALL\s+` shared a trailing `\b` with word-ending
        # siblings, but ends in whitespace (non-word) -- broke on the
        # dominant realistic call form, a quoted program-name literal
        # (`CALL 'SUBPROGRAM' USING ...`), where a quote (non-word)
        # follows the consumed whitespace. Only the less-common unquoted
        # data-name form (`CALL WS-PROGRAM-NAME`) happened to work.
        "ipc_rpc_bridges": re.compile(r"(?i)\bCALL\s+|\bEXEC\s+CICS\s+(?:LINK|XCTL|START|RETURN)\b|\bEXEC\s+SQL\b"),
    },
}
