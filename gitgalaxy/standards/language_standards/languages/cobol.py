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
    # `.dcl` (#3365): DB2 DCLGEN members generated with LANGUAGE(COBOL) -- an `EXEC SQL
    # DECLARE ... TABLE` block plus its `01 DCL...` host-variable record, pulled in by
    # `EXEC SQL INCLUDE`. carddemo keeps them in `dcl/` folders. No other registry
    # language claims `.dcl` (Clean's definition modules use it, but Clean is not in the registry).
    "extensions": [".cbl", ".cob", ".cpy", ".cobol", ".pco", ".cut", ".dcl"],
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
    # #2540: COBOL copybook names are case-insensitive (`COPY A.` binds the
    # same copybook as `copy a.`), so the dependency DAG's import-token ->
    # file lookup (network_risk_sensor.py) case-folds for this language.
    "case_insensitive_imports": True,
    # #3199: this language's import statement names a library MEMBER that the
    # compiler pastes into the importing compilation unit (COBOL `COPY` / `EXEC SQL INCLUDE`). A member is
    # source in this same language by construction, so when a copied name is
    # ambiguous the resolver only ever chooses a candidate in it, and drops the
    # edge when there is none. Without that, CBSA's `COPY BNK1CAM` -- a BMS
    # symbolic map, generated at build time and absent from the repository --
    # resolved to whichever same-named file happened to be nearest, which is the
    # map's own build JCL. Every other language keeps unconstrained
    # cross-language resolution (an HTML page importing a .css file).
    "imports_are_source_members": True,
    # #3198: COBOL's own identifier lexicon, for the `unreferenced_by_name`
    # census. Names are case-insensitive (`perform a-para` reaches `A-PARA`),
    # and `-` is a name character -- without that, `B-PARA-EXIT` counted as a
    # mention of `B-PARA` and cleared its flag, so a paragraph read as
    # referenced because a DIFFERENT paragraph's name began with its name.
    # Verified on the #3198 micro-repro and both mainframe corpora.
    "identifier_case": "insensitive",
    "identifier_extra_chars": "-",
    # #3200/#3201: opts cobol into the named mainframe boundary channel --
    # CALL / CICS LINK / XCTL targets, and SELECT/ASSIGN ddnames with their
    # OPEN modes. The counted rules (`ipc_rpc_bridges`, `io`) say THAT this
    # program calls out and touches files; they cannot say WHAT, so the call
    # graph and the dataset lineage were stated absences in the DB.
    # Implemented by core/mainframe_boundary.py, which reads the prism code
    # stream (never the raw file, so a commented-out CALL draws no edge).
    #
    # TOP LEVEL, not inside `rules`, and that is load-bearing: language_lens.py's
    # `_calibrate_lookup_maps` re.compile()s every STRING value inside `rules`
    # (a guard for definitions loaded from external JSON). A string helper key
    # put there becomes `re.compile("cobol")` in a real scan while every unit
    # test -- which builds from LANGUAGE_DEFINITIONS directly -- stays green.
    # That is exactly how #2806 blessed a wrong golden master.
    "boundary_extraction": "cobol",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: Entscheidungslogik. Control flow that splits execution paths.
        "branch": re.compile(
            r"\b((?<!END-)IF|ELSE|(?<!END-)EVALUATE|WHEN|UNTIL|VARYING|TIMES|DEPENDING\s+ON|ON\s+EXCEPTION|AT\s+END|INVALID\s+KEY|ON\s+SIZE\s+ERROR|ON\s+OVERFLOW)\b",
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
        # BUG FIX #2804: the inter-operand separator was `\s*,?`, which
        # consumes trailing space THEN an optional comma -- so after
        # `WS-A,` the next operand iteration began on the space in
        # `WS-A, WS-B` and its leading `[A-Z0-9_-]+` failed immediately,
        # stopping the capture at the first operand. `USING WS-A, WS-B,
        # WS-C` (comma-SPACE separated -- the dominant real formatting)
        # captured only `WS-A,` and read as one parameter, silently
        # dropping WS-B/WS-C (they carry no USING/RETURNING anchor of
        # their own, so `finditer` never sees them either).
        #
        # The separator is `(?:[ \t\r\n]*,[ \t\r\n]*|[ \t]+)?`: an operand
        # list may cross a newline ONLY when the operands are joined by a
        # comma (COBOL's optional separator comma), and may otherwise be
        # separated by inline horizontal whitespace on the same line. This
        # is deliberate. A COBOL statement is terminated by a period, not a
        # newline, and a period is frequently omitted until the end of a
        # sentence -- so `CALL 'X' USING A , B , C` (no closing period)
        # followed by a blank line and an `IF ...` statement has no lexical
        # boundary a flat pattern can see. An earlier `[\s,]*` separator
        # that crossed newlines unconditionally swept that trailing `IF
        # WS-SEVERITY-N` straight into the operand list (real regression:
        # carddemo CSUTLDPY.cpy read 5 operands for a 3-operand CALL).
        # Requiring a comma to cross a line stops at the real list end for
        # the common continued form (leading-comma continuation, which is
        # exactly how carddemo wraps its USING lists) without over-reading
        # into the next statement; a rarer newline-separated list with NO
        # commas at all is conservatively counted from its first operand
        # rather than risk swallowing the following verb.
        #
        # The same-line branch is `[ \t]{1,4}`, not `[ \t]+`, on purpose.
        # Fixed-format COBOL carries an 8-char program identifier in
        # columns 73-80 of every line (e.g. NIST CCVS `IC2014.2`), and a
        # space-separated `USING DN1 DN2 DN3 DN4` with no terminating
        # period runs a long whitespace gap straight to that column -- an
        # unbounded `[ \t]+` bridged it and captured the sequence id as a
        # bogus extra operand (real regression: IC2014.2.cbl read 45 for a
        # 44-operand file). A real inter-operand gap on one physical line
        # is one space (occasionally a few); capping the same-line run at 4
        # blocks the ~30-space identification-area bridge while leaving
        # normal spacing untouched. Wider single-line alignment (rare for a
        # USING list -- multi-operand lists wrap with commas) is
        # conservatively counted short, never over-read. Column-73 blanking
        # is not done here because it is unsafe without fixed/free-format
        # detection (free-format lines legitimately run past column 72).
        #
        # Both branches of the separator are disjoint from the operand's
        # own `[A-Z0-9_-]+`, the operand is non-nullable, and the
        # repetition stays `{0,20}`-bounded -- so this is still ReDoS-proof
        # (no overlapping-quantifier ambiguity). The `(?!RETURNING\b)`
        # boundary is unchanged, so `USING A RETURNING B` still yields two
        # separate matches. The captured list is turned into a real
        # parameter COUNT (operands, not clauses) by detector.py's
        # `_count_cobol_using_operands`.
        "args": re.compile(
            r"\b(?:USING|RETURNING)\s+"
            r"((?:(?:BY\s+(?:REFERENCE|CONTENT|VALUE)\s+)?(?!RETURNING\b)"
            r"[A-Z0-9_-]+(?:[ \t\r\n]*,[ \t\r\n]*|[ \t]{1,4})?){0,20})",
            re.I,
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining straight-line execution flow.
        # EXCLUDES access modifiers (GLOBAL, EXTERNAL) to prevent Structural Complexity Inflation.
        "structural_boundaries": re.compile(
            r"\b(DIVISION|SECTION|EXIT|CONTINUE|GOBACK|ACCEPT|XML\s+PARSE|JSON\s+GENERATE|DISPLAY|STOP\s+RUN|PERFORM)\b",
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
            # #3533: the rest of the ENVIRONMENT DIVISION's header paragraphs --
            # navikt/DSF FRMERK `SPECIAL-NAMES.` / `C01 IS PAGE1.` read as a unit.
            r"SPECIAL-NAMES|I-O-CONTROL|REPOSITORY|"
            # FILE-CONTROL is the INPUT-OUTPUT SECTION (ENVIRONMENT DIVISION) header
            # paragraph, never PROCEDURE DIVISION logic -- same reserved-header class
            # as INPUT-OUTPUT/CONFIGURATION beside it. The bare `FILE` entry above
            # can't shield it: the closing `(?=[ \t\n.])` boundary rejects `FILE`
            # when a `-CONTROL` follows, so `FILE-CONTROL.` slipped through as a
            # phantom paragraph (confirmed FP against data/corpus_cobol/FPS.cob).
            r"INPUT-OUTPUT|CONFIGURATION|FILE-CONTROL|DISPLAY|CALL|MOVE|COMPUTE|PERFORM|ADD|SUBTRACT|MULTIPLY|"
            r"DIVIDE|INITIALIZE|SET|IF|ELSE|GOBACK|EXIT|STOP|EVALUATE|WHEN|READ|WRITE|REWRITE|"
            # CONTINUE is a no-op statement (COBOL's `pass`); on its own line
            # `CONTINUE.` is `<verb>.`, not a paragraph header. Confirmed FP against
            # language-crucible v1.2.0 (che-che4z_nist_ccvs85/IF4014.2.cbl:30 etc.,
            # cobol-sample_SAMPLE1.cbl). Same class as LOCAL-STORAGE (#1890).
            r"DELETE|OPEN|CLOSE|CONTINUE|"
            # #2538: CEE3DMP/CEEMOUT/CEEDUMP are Language Environment (LE)
            # runtime diagnostic service names -- already recognized elsewhere
            # in this file as the `telemetry` class (see that rule below) -- not
            # paragraph names. A bare `CEE3DMP.` statement call sitting on its
            # own line, indented into Area B, was being swept up as a paragraph
            # header: this shield had no entry for them, and the post-sequence-
            # area slot (`[ \t]*`, item 1 above) tolerates any horizontal
            # indent to support genuinely free-format source, so it doesn't
            # distinguish Area A (paragraph names, columns 8-11) from Area B on
            # its own. Confirmed FP: `data/cobol/b.cpy` (che-che4z #1096 control
            # corpus) planted `CEE3DMP.`/`CEEMOUT.` in Area B and both were
            # captured as extra paragraphs (func_start=5 for 3 real paragraphs).
            # Scoped narrowly to these three known LE tokens, same fix class as
            # CONTINUE/LOCAL-STORAGE above, rather than a general Area-A column
            # anchor: the sequence-area consumer in item 1 can't reliably tell
            # a genuine fixed-format sequence number from 6 free-format leading
            # spaces, so a real structural fix needs file-level fixed/free-
            # format detection -- out of scope for this narrow token exclusion.
            r"CEE3DMP|CEEMOUT|CEEDUMP|"
            r"PROGRAM-ID|CLASS-ID|SECTION|DIVISION|END-[A-Za-z0-9_-]+)(?=[ \t\n.]))"
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
            # #3533: a procedure name may be all digits (navikt/DSF R001BYDL `0000.` /
            # `9999.`) -- unlike a data name. At most 5 digits: a 6-digit (cols 1-6)
            # or 8-digit (cols 73-80) sequence field before a lone period (CardDemo
            # `045100 .`) is never one. A continued numeric VALUE line (`1000.`) does
            # not begin a sentence, so the cobol_sentence_start filter drops it.
            r"(?:\b|(?<=[0-9]{6}[ \-Dd]))([0-9_-]*[A-Za-z][A-Za-z0-9_-]*|[0-9]{1,5}(?![0-9]))"
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
            # #3419: the separator period may sit on the NEXT line (CardDemo
            # COTRTLIC `127400 2000-SEND-MAP` / `127500      .`, PERFORMed THRU five
            # times). Bounded: exactly one newline, then the fixed 6-char
            # sequence area, then the period -- no open-ended vertical gap,
            # which is what the #2480 note above rejected.
            r"(?=(?:[ \t\n]+SECTION(?:[ \t\n]+[0-9]{1,2})?)?"
            r"(?:[ \t]*\.|[ \t]*\n(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*\.)(?:[ \t\n]|$))",
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
        # 3. #3418: `PROGRAM-ID.` alone on its line, name on the next. `\s+` ran
        #    straight into the next line's sequence area (CardDemo COTRTLIC
        #    read `002600`) or, with nothing else on the line, into the cols
        #    73-80 identification area (COTRTUPC read `00220000`). A COBOL
        #    user-defined word must contain a letter, so the name now does; and
        #    when the name is not on the same line, the gap may cross one
        #    identification-area token, the newline and the next line's
        #    sequence area -- the same `[0-9a-zA-Z \t]{6}[ \-]?` prefix the rule
        #    already allows at line start. The `\b` before the name is func_start's
        #    greedy-margin guard: without it that 6-char prefix ate `    My` of an
        #    indented `MyProgram` and captured `Program`.
        "class_start": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:PROGRAM-ID|CLASS-ID|INTERFACE-ID|FACTORY|OBJECT)\."
            r"(?:[ \t]+|(?:[ \t]+\S{1,8})?[ \t]*\n(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*)"
            r"\b([0-9_-]*[A-Za-z][A-Za-z0-9_-]*)(?:[ \t\n]+(?!DIVISION\b)[A-Za-z0-9_-]+){0,6}(?=[ \t]*\.|\n|$)",
            re.I | re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. Defensive scope terminators and declarative blocks.
        # C2: END-* closers are structure. C4: hyphen guards (#2622 shape). ON ERROR/AT END/INVALID KEY stay branch's (verified owner, #2822 disposition).
        # #2990: the stated #2869 sentence names "an installed failure handler" and "a
        # value-level failure check". CICS installs handlers with HANDLE CONDITION / HANDLE
        # ABEND (PUSH/POP HANDLE stack them) -- HANDLE CONDITION moved here from `events`,
        # whose declared row excludes the receiving side. SYNCPOINT [ROLLBACK] / RESYNC,
        # EXEC SQL COMMIT/ROLLBACK and EXEC DLI CHKP/ROLB/ROLL are unit-of-work control, the
        # transactional guard sqlite.py already counts as safety. `DFHRESP(` comparisons and
        # `IF|EVALUATE SQLCODE` are the mainframe try/catch: the value-level check of a
        # command's response (393 / 132 crucible hits, no owner before this). The IF form is
        # also branch's decision -- the jcl COND=((4,LT),EVEN) dual shape, deliberate.
        # `WHENEVER <cond> GO TO` installs a handler (its CONTINUE form is safety_bypasses').
        "safety": re.compile(
            r"(?<!-)\b(?:DECLARATIVES|VALIDATE|CHECK)\b(?!-)"
            r"|\bEXEC\s+CICS\s+(?:HANDLE\s+(?:CONDITION|ABEND)|PUSH\s+HANDLE|POP\s+HANDLE|SYNCPOINT|RESYNC)\b"
            r"|\bEXEC\s+SQL\s+(?:COMMIT|ROLLBACK|WHENEVER\s+(?:SQLERROR|SQLWARNING|NOT\s+FOUND)\s+GO\s*TO)\b"
            r"|\bEXEC\s+DLI\s+(?:CHKP|SYMCHKP|ROLB|ROLL|ROLS)\b"
            r"|\bDFHRESP\("
            r"|\b(?:IF|EVALUATE)\s+(?:SQLCODE|SQLSTATE)\b",
            re.I,
        ),
        # 7. safety_neg: Safety Bypasses. Bypassing logic or unpredictable jumps.
        # #2485: `EXEC CICS IGNORE CONDITION <cond>` switches OFF the handler
        # for a condition for the rest of the task -- error handling
        # deliberately disabled, which is what this key means. The issue
        # proposed `panics_and_aborts`; that is the opposite reading (an abend
        # raises, IGNORE CONDITION suppresses), so it is routed here instead.
        # #2990: NOHANDLE on a command switches CICS exception handling off for that one
        # command, and `EXEC SQL WHENEVER <cond> CONTINUE` tells the precompiler to ignore
        # the condition -- both swallow errors, which is this key. The GO TO alternative is
        # guarded (fixed-width lookbehinds, one per condition word) so `WHENEVER SQLERROR GO
        # TO` -- a handler install, safety's -- is not also counted as a bypass.
        "safety_bypasses": re.compile(
            r"\b(?:NEXT\s+SENTENCE|(?<!SQLERROR\s)(?<!SQLWARNING\s)(?<!FOUND\s)GO\s+TO|CORRESPONDING"
            r"|ANY\s+LENGTH|OMITTED|EXEC\s+CICS\s+IGNORE\s+CONDITION)\b"
            r"|(?<![-\w])NOHANDLE(?![-\w])"
            r"|\bEXEC\s+SQL\s+WHENEVER\s+(?:SQLERROR|SQLWARNING|NOT\s+FOUND)\s+CONTINUE\b",
            re.I,
        ),
        # 8. danger: High-Risk Execution. Process-stopping commands and self-modifying code (ALTER).
        # #2878 contract C2: hyphen-guarded -- `ALTER-TEST-INIT.` is a paragraph name, not the
        # ALTER statement (the #2622 shape). ALTER rewrites control (C3), CANCEL unloads code (C1c).
        # #2990: the COBOL CANCEL verb unloads a program and takes a program operand
        # (`CANCEL 'SUBPROG'`, `CANCEL WS-PGM`). The same word is a CICS option with no
        # operand -- `EXEC CICS ABEND ABCODE('X') CANCEL`, `HANDLE ABEND CANCEL` -- and the
        # interval-control command `EXEC CICS CANCEL REQID(...)` (concurrency's). The bare
        # token fired on all of them (31% of the crucible's ABEND blocks read as high-risk
        # execution). CANCEL now needs an operand on its line and must not be the CICS form.
        # Dynamic SQL runs text as code (contract family 2: PREPARE / EXECUTE [IMMEDIATE]);
        # TRUNCATE and DROP DATABASE are whole-store destruction (family 4).
        "high_risk_execution": re.compile(
            r"(?<![-\w])(?:STOP\s+RUN|ALTER"
            r"|CANCEL(?![ \t]+(?:REQID|TRANSID|SYSID|END-EXEC)\b)(?=[ \t]+['\"A-Z0-9]))(?![-\w])"
            r"|\bEXEC\s+SQL\s+(?:PREPARE|EXECUTE(?:\s+IMMEDIATE)?|TRUNCATE|DROP\s+DATABASE)\b",
            re.I,
        ),
        # 9. io: I/O & Network Boundaries. Disk, Database (SQL), and CICS communication.
        # #2485: the queue verbs are a SEPARATE alternative from the bare
        # file-control ones, not extra letters on them. `EXEC CICS READQ TS`
        # cannot reach the `READ` alternative -- the trailing `\b` needs a
        # word/non-word transition and `READ` is followed by `Q` -- so before
        # this the whole TSQ/TDQ lifecycle recorded no io at all (30 real
        # occurrences in the crucible: WRITEQ TS 17, READQ TS 7, DELETEQ TS 6).
        # Reading or writing a temporary-storage or transient-data queue is a
        # read/write of a queue resource outside the program, which is what
        # this signal means. `WRITEQ TD` deliberately counts BOTH here and in
        # `telemetry`: a transient-data write is a real io boundary AND the
        # CICS journalling idiom, the same dual as sqlite's `.read`
        # (keyword-rosetta ledger sqlite-dot-read-dual-import-io).
        "io": re.compile(
            # #2841 contract C2: CLOSE is cleanup's hit.
            # #2990: the VSAM browse family (STARTBR/READNEXT/READPREV/ENDBR/RESETBR), UNLOCK,
            # the spool API and the named-counter API (a shared counter in the coupling
            # facility is an external store: DEFINE/GET/QUERY/UPDATE/REWIND/DELETE COUNTER)
            # are boundary operations with no owner before this. `EXEC DLI` (IMS) and the
            # CBLTDLI call interface join `EXEC SQL` as the embedded-database boundary. The
            # bare file-positioning verb START is guarded so `EXEC CICS START TRANSID` (a task
            # spawn: concurrency + ipc_rpc_bridges) no longer reads as a file operation. The
            # lookbehind alone assumes exactly one space after CICS; real source varies
            # (cics-genapp's lgwebst5.cbl has two), so a lookahead on the CICS-only operand
            # words (TRANSID/BREXIT/CHANNEL/AFTER, never a file-control START's next token)
            # backs it up regardless of spacing.
            r"\b(READ|WRITE|REWRITE|OPEN|(?<!CICS\s)START(?!\s+(?:TRANSID|BREXIT|CHANNEL|AFTER)\b)|DELETE|EXEC\s+(?:SQL|DLI)"
            r"|EXEC\s+CICS\s+(?:READQ|WRITEQ|DELETEQ)\s+(?:TS|TD)"
            r"|EXEC\s+CICS\s+(?:READ|WRITE|REWRITE|DELETE|UNLOCK|STARTBR|READNEXT|READPREV|ENDBR|RESETBR"
            r"|SPOOL(?:OPEN|READ|WRITE|CLOSE)|(?:DEFINE|GET|QUERY|UPDATE|REWIND|DELETE)\s+D?COUNTER))\b"
            r"|CALL\s+'(?:CBLTDLI|AIBTDLI)'",
            re.I,
        ),
        # 10. api: Public Surface Area. Exposed linkage points and external entries.
        # BUG FIX #2730 (api contract): `CALL`/`INVOKE` are call SITES -- a
        # reference to a name declared elsewhere, not a declaration that
        # publishes one. They also swept up `END-CALL` (`\b` fires after the
        # hyphen), which alone was 108 of the crucible corpus's 1396 matches;
        # 843 of the 1396 came from this pair. `ENTRY` (a secondary entry
        # point) and `LINKAGE SECTION` (the called program's parameter
        # contract) are COBOL's real published surface.
        "api": re.compile(r"\b(ENTRY|LINKAGE\s+SECTION|EXPORT)\b", re.I),
        # 11. flux: State Mutation. State mutation (The core of COBOL data manipulation).
        # #2484: `PUT CONTAINER` writes program state into a channel that
        # outlives the current program, so it is a mutation as well as a
        # transfer -- it counts here AND in `ipc_rpc_bridges`, deliberately.
        # `GET CONTAINER` is NOT here: reading a container mutates nothing.
        # (`MOVE CONTAINER` already reaches this rule through the bare `MOVE`
        # alternative, which is why it is not listed again.)
        "state_mutation": re.compile(
            # #2765 contract: the verb that performs the write, once per statement. The
            # scope terminators (`END-STRING`, `END-ADD`, `END-COMPUTE`...) are excluded by
            # the hyphen guard; `REPLACE` is a compiler directive, not a write.
            r"(?<![-\w])(?:MOVE|COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|SET|INITIALIZE|STRING|UNSTRING"
            r"|EXEC\s+CICS\s+PUT\s+CONTAINER)\b",
            re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural logic (Column 7 indicator).
        "dead_code": re.compile(
            r"^(?:.{6}\*|[ \t]*\*>)[ \t]*(?:MOVE|COMPUTE|IF|PERFORM|CALL|EXEC)\b",
            re.I | re.M,
        ),
        # 13. doc: Structured Documentation. Identification metadata and structured comments.
        # BUG FIX #2672/#2661 step 2: `AUTHOR.` was claimed by both `doc`
        # and `ownership`, so an IDENTIFICATION DIVISION with an AUTHOR
        # paragraph double-counted (the #2659 shape). `ownership` already
        # owns `AUTHOR` exclusively; drop it here and leave the other
        # header fields and the `*>` tags (including `@author` inline
        # comments, which are distinct from the AUTHOR paragraph) as-is.
        # #2882 contract C4: doc counts the block, not the author tag -- `*> @author` is ownership's alone.
        "doc": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:DATE-WRITTEN|DATE-COMPILED|REMARKS|INSTALLATION)\.|\*>\s*@(?:param|return)",
            re.I | re.M,
        ),
        # 14. test: Testing & Assertions. Unit testing framework markers (ZUnit).
        # #2852 contract C3: hyphen guards -- UT-TEST-CASE-COUNT is an identifier, not a test case (the #2622 hyphen shape)
        # #2852 contract C3: hyphen guards -- UT-TEST-CASE-COUNT is an identifier, not a test case (the #2622 hyphen shape)
        "test": re.compile(r"(?<!-)\b(ZUNIT|CBLUNIT|ASSERT|TEST-CASE|READY\s+TRACE)\b(?!-)", re.I),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: Temporal Static. CICS Task and resource coordination.
        # #2990: the Async API (RUN TRANSID spawns a child task, FETCH CHILD/ANY joins it,
        # FREE CHILD discards its token), interval control (START/RETRIEVE/CANCEL/POST) and
        # task control (WAIT*, WAITCICS, SUSPEND) are CICS's task-coordination surface. Before
        # this a modern async CICS app read arch_concurrency = 0. RUN TRANSID also counts in
        # ipc_rpc_bridges (the dual START already carries); SUSPEND also in thread_sleeps.
        "concurrency": re.compile(
            r"\bEXEC\s+CICS\s+(?:ENQ|DEQ|WAIT|WAITCICS|START|RETRIEVE|CANCEL|POST|DELAY|SUSPEND"
            r"|RUN\s+(?:TRANSID|ACTIVITY|ACQPROCESS)|FETCH\s+(?:CHILD|ANY)|FREE\s+CHILD)\b",
            re.I,
        ),
        # 16. ui_framework: UI / View Components. Screen sections and CICS maps.
        # #2990: SEND MAP was the only terminal output counted; SEND TEXT / SEND CONTROL /
        # SEND PAGE and the bare SEND (37 crucible blocks) write the same 3270 screen, and
        # CONVERSE / ROUTE / PURGE MESSAGE / ISSUE ERASEAUP are the rest of the terminal-
        # control surface. `WEB SEND` cannot reach the SEND alternative (CICS must be
        # adjacent) -- it stays ssr_boundaries'. CONVERSE is also a listener (send+receive).
        "ui_framework": re.compile(
            r"\b(?:SCREEN\s+SECTION|EXEC\s+CICS\s+(?:SEND|CONVERSE|ROUTE|PURGE\s+MESSAGE|ISSUE\s+ERASEAUP)"
            r"|DFHMDF|DFHMDI|DFHMSD)\b",
            re.I,
        ),
        # 17. closures: Closures / Anonymous Functions. (COBOL lacks native lambdas).
        "closures": None,
        # 18. globals: Global / Shared State. Global storage and external linkages.
        # BUG FIX #2805: dropped `WORKING-STORAGE SECTION` from this rule. The
        # item-level clauses (`GLOBAL`, `EXTERNAL`, `COMMON`) are what mark shared
        # state -- `GLOBAL`/`EXTERNAL` publish one data item outside the program,
        # `COMMON` a program to its siblings. `WORKING-STORAGE SECTION` is a REGION
        # HEADER: it opens the area where a program declares its own state, and it
        # is mandatory in every COBOL program that declares any. Counting it stacked
        # a phantom `globals >= 1` on every real COBOL file with a working-storage
        # section whether or not it shares anything -- an unconditional per-file +1
        # (a program with a working-storage section and five `GLOBAL` items scored 6,
        # one with a section and nothing global scored 1). It also inflated the
        # `encapsulation_ratio` numerator (`1 - globals / (core_var_decl + globals)`)
        # on that same file. Working-storage is program-private static storage, not
        # global surface; `SECTION` still counts as a structural boundary via the
        # `structural_boundaries` rule above, so no structural signal is lost.
        # #2858 contract corollary 3: `-` is a regex word boundary, so the bare
        # keyword matched inside `COMMON-RETURN` / `CA-POLICY-COMMON` (185
        # crucible hits, every one an identifier -- the #2622 hyphen shape).
        "globals": re.compile(r"(?<![-\w])(COMMON|GLOBAL|EXTERNAL)(?![-\w])", re.I),
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
        # #2990: the statistical and remaining math intrinsics (410 crucible calls in 35
        # files read no scientific signal: MEAN, MEDIAN, STANDARD-DEVIATION, SUM, RANGE,
        # ANNUITY ...). The hyphen guard keeps INTEGER off INTEGER-OF-DATE (time's) and
        # E off EXP; NUMVAL* are conversions (explicit_casts'), not math.
        "scientific": re.compile(
            r"\bFUNCTION\s+(?:ACOS|ASIN|ATAN|COS|SIN|TAN|EXP|EXP10|LOG|LOG10|SQRT|FACTORIAL|ABS|PI|E|MOD|REM"
            r"|INTEGER|INTEGER-PART|RANDOM|SUM|MEAN|MEDIAN|MIDRANGE|RANGE|VARIANCE|STANDARD-DEVIATION"
            r"|MIN|MAX|ORD-MIN|ORD-MAX|ANNUITY|PRESENT-VALUE)(?![-\w])",
            re.I,
        ),
        # 23. heat_triggers: Metaprogramming & Reflection. Metaprogramming and memory aliasing.
        "reflection_metaprogramming": re.compile(
            # #2990: the EXEC blanket also covers EXEC DLI (IMS); docs/cobol_semantic_coverage.md
            # records which verbs this blanket is the semantic owner of (ASSIGN, INQUIRE ...).
            r"\b(REDEFINES|RENAMES|OCCURS\s+DEPENDING\s+ON|EVALUATE\s+TRUE|EXEC\s+(?:CICS|SQL|DLI))\b",
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
        # #3416: `EXEC SQL INCLUDE <member> END-EXEC` on ONE line was invisible --
        # INCLUDE had to begin its own line, which only the two-line form
        # (`EXEC SQL` / `INCLUDE X`, CBSA's style) satisfies. CardDemo's
        # app-transaction-type-db2 programs use the one-line form, so 6 copybook
        # edges (CSDB2RWY, CSDB2RPY and the DCLGEN .dcl members) were lost.
        "import": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:EXEC[ \t]+SQL[ \t]+)?(?:COPY|INCLUDE)\b", re.I | re.M
        ),
        "_dependency_capture": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:EXEC[ \t]+SQL[ \t]+)?(?:COPY|INCLUDE)[ \t\n]+['\"]?([A-Za-z0-9_-]+)['\"]?",
            re.I | re.M,
        ),
        # 25. ownership: Authorship indicators.
        # #2882 contract: C1 `* Author :` comment lines join the AUTHOR. paragraph; `*> @author` is ownership's (doc released it, C4)
        "ownership": re.compile(
            r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*AUTHOR\.\s+([^\n]+)|\*>[ \t]*@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^(?:[0-9a-zA-Z \t]{6}[*/\-]|[ \t]*\*>)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?-i:(?:Author|AUTHOR)(?:s|S)?|Created[ \t]+by|CREATED[ \t]+BY|Maintainer(?:s)?|MAINTAINER(?:S)?|Owner(?:s)?|OWNER(?:S)?|Developer(?:s)?|DEVELOPER(?:S)?|Contact|CONTACT)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)(?<![,;{(])[ \t]*(?:\*/|-->)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt: The Promise. Future work markers.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure: Map vs. Territory. Audit tags.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
        # 31. ssr_boundaries: View Horizon. CICS web endpoints.
        # #2990: the whole WEB / DOCUMENT API (WEB OPEN/CLOSE/RECEIVE/WRITE/EXTRACT/CONVERSE,
        # DOCUMENT CREATE/INSERT/SET/RETRIEVE), SOAPFAULT and the EXTRACT WEB/TCPIP/CERTIFICATE
        # inquiries are CICS's HTTP surface, not only WEB SEND / WEB READ.
        "ssr_boundaries": re.compile(
            r"\bEXEC\s+CICS\s+(?:WEB\s+[A-Z]+|DOCUMENT\s+[A-Z]+|SOAPFAULT|EXTRACT\s+(?:WEB|TCPIP|CERTIFICATE))\b",
            re.I,
        ),
        # 32. events: Pub/Sub Network. Signal handlers and MQ bindings.
        # BUG FIX: the `CALL 'MQPUT'`/`CALL 'MQGET'` alternative shared a
        # trailing `\b` with the word-ending EXEC CICS alternative, but
        # ends in a literal `'` (non-word) -- `\b` right after can only
        # fire if the next char is a word character, never true for the
        # realistic form (`CALL 'MQPUT' USING queue-name.`, whitespace
        # after the closing quote). Pulled out of the shared group.
        # #2990: HANDLE CONDITION moved to `safety` (an installed failure handler is the
        # stated #2869 contract's; the declared events row excludes the receiving side).
        # SIGNAL EVENT is the CICS event-processing emit and stays.
        "events": re.compile(
            r"\bEXEC\s+CICS\s+SIGNAL\s+EVENT\b|CALL\s+'(?:MQPUT|MQGET)'",
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
            # #2990: EXEC CICS ADDRESS obtains the address of a CICS area (COMMAREA, EIB, CWA).
            r"\b(?:POINTER|PROCEDURE-POINTER|FUNCTION-POINTER)\b|\bADDRESS\s+OF\b|\bEXEC\s+CICS\s+ADDRESS\b",
            re.I,
        ),
        # 36. memory_alloc: Manual Memory Management. Heap and CICS allocation.
        # #2990: FREE CHILD discards an async child's token (cleanup's), not storage;
        # GETMAIN64 / FREEMAIN64 are the 64-bit forms.
        "memory_alloc": re.compile(
            r"\b(?:ALLOCATE|FREE(?!\s+CHILD\b)|EXEC\s+CICS\s+(?:GETMAIN|FREEMAIN)(?:64)?)\b", re.I
        ),
        # 37. inline_asm: Bare Metal.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry: Professional diagnostics.
        # #2990: journal writes, operator messages, transaction dumps and trace entries are
        # CICS's other diagnostic emissions (WRITE JOURNALNAME is also an io write, the
        # WRITEQ TD dual); EXEC DLI LOG writes the IMS log; DSNTIAR formats a Db2
        # diagnostic message (the CEEMOUT class).
        "telemetry": re.compile(
            r"\b(?:EXEC\s+CICS\s+(?:WRITEQ\s+TD|WRITE\s+JOURNALNAME|WRITE\s+OPERATOR|DUMP\s+TRANSACTION|ENTER\s+TRACENUM)"
            r"|EXEC\s+DLI\s+LOG|CEE3DMP|CEEMOUT|CEEDUMP)\b|CALL\s+'DSNTIAR'",
            re.I,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
        # #2990: EXHIBIT is DISPLAY's OS/VS ancestor (still compiled). READY TRACE is left
        # in `test` (unchanged) -- the stated #2852 contract already pins it as a positive
        # case there (test_test_contract_2852.py) and this is a single-language coverage
        # pass, not a contract revision; RESET TRACE (the trace-off form the contract does
        # not mention) is added here as the debug-artifact toggle's other half.
        "debug_prints": re.compile(r"\b(?:DISPLAY|EXHIBIT|RESET\s+TRACE)\b", re.I),
        # 40. explicit_casts (Explicit Type Casting): Explicit type coercion/casting.
        # #2990: NUMVAL / NUMVAL-C / NUMVAL-F, DISPLAY-OF / NATIONAL-OF and HEX-OF /
        # HEX-TO-CHAR are COBOL's conversion calls (string <-> numeric / encoding), and
        # EXEC CICS BIF DEEDIT converts an edited numeric field back to a number -- the
        # declared explicit_casts sentence's "conversion call" form.
        "explicit_casts": re.compile(
            r"\b(?:REDEFINES)\b"
            r"|\bFUNCTION\s+(?:NUMVAL|NUMVAL-C|NUMVAL-F|DISPLAY-OF|NATIONAL-OF|HEX-OF|HEX-TO-CHAR)(?![-\w])"
            r"|\bEXEC\s+CICS\s+BIF\s+DEEDIT\b",
            re.I,
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting execution.
        # #2485: `EXEC CICS ABEND` terminates the task abnormally and is the
        # CICS sibling of `STOP RUN` -- 91 occurrences across 47 crucible
        # files, none of which recorded an abort before this. Deliberately NOT
        # added to `high_risk_execution`: engine rule 3 keeps that key for
        # things that EXECUTE, and an abend runs nothing. (`STOP RUN` sits in
        # both today; widening high_risk_execution by 91 hits across 47 files
        # is a scoring change that needs its own justification, not a
        # side effect of this one.)
        # #2990: CALL 'CEE3ABD' is the Language Environment abend service -- the batch
        # sibling of EXEC CICS ABEND (8 crucible calls, ipc-only before this).
        "panics_and_aborts": re.compile(
            r"\b(?:STOP\s+RUN|EXIT\s+PROGRAM|GOBACK|EXEC\s+CICS\s+ABEND)\b|CALL\s+'CEE3ABD'", re.I
        ),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits).
        # #2990: SUSPEND yields the task to CICS (a forced pause); also concurrency's.
        "thread_sleeps": re.compile(r"\bEXEC\s+CICS\s+(?:DELAY|SUSPEND)\b", re.I),
        # 43. bitwise_ops (Bitwise Operations) (Modern intrinsic bitwise).
        "bitwise_ops": re.compile(r"\bFUNCTION\s+(?:BIT-AND|BIT-OR|BIT-XOR|BIT-NOT)\b", re.I),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\bEXEC\s+CICS\s+ENQ\b", re.I),
        # 45. immutability_locks (Immutability Constraints) Immutability.
        "immutability_locks": re.compile(
            r"(?<![\w'-])(CONSTANT)(?![\w-])", re.I
        ),  # #2772 C3: hyphen/quote guards -- AN-CONSTANT is a name, not a lock (the #2888 cobol shape)
        # 46. cleanup (Resource Cleanup / Teardown) Resource release.
        # #2990: ENDBR releases a VSAM browse cursor and SPOOLCLOSE a spool report -- the
        # `EXEC SQL CLOSE` (cursor) shape, cleanup + io. FREE CHILD / DELETE COUNTER / DELETE
        # CONTAINER reach the bare verbs already and are contract-correct releases of state.
        "cleanup": re.compile(
            r"(?<![\w\'-])(CLOSE|FREE|DELETE)(?![\w-])|\bEXEC\s+CICS\s+(?:ENDBR|SPOOLCLOSE)\b", re.I
        ),  # #2888 C3: \\b fired inside 9000-DALYTRAN-CLOSE and \'CLOSE...\' literals; END-DECLARATIVES is a structural closer (#2869\'s END-* family); DELETE removes a record (#2843)
        # 47. encapsulation (Encapsulation / Access Modifiers)
        # #2766: LOCAL-STORAGE SECTION dropped -- it is per-invocation memory
        # allocation (recursion support), not a name-visibility marker. PRIVATE is
        # OO COBOL's genuine non-public marker.
        "encapsulation": re.compile(r"\bPRIVATE\b", re.I),
        # 48. listeners (Event Listeners / Observers)
        # #2990: HANDLE AID registers a handler for a terminal attention key (PF/PA/ENTER)
        # -- a registration to receive from the terminal; CONVERSE is a send+receive pair.
        "listeners": re.compile(r"\b(?:MQGET|EXEC\s+CICS\s+(?:RECEIVE|CONVERSE|HANDLE\s+AID))\b", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"\b(IGNORE)\b", re.I),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (COBOL Specifics) ---
        # #3004: the CICS/SQL auth surface, unowned since the #2990 census. SIGNON/SIGNOFF
        # start and end an authenticated terminal session; VERIFY/CHANGE PASSWORD|PHRASE
        # authenticate or rotate a credential; QUERY SECURITY asks RACF whether the task's
        # user may touch a resource; embedded EXEC SQL GRANT/REVOKE is the DCL privilege
        # boundary (one owner across languages -- db2_sql's moved here from encapsulation in
        # the same pass). EXEC-anchored on purpose: carddemo's 14 bare `SIGNON` hits are
        # paragraph names and comments (SEND-SIGNON-SCREEN), not one real command, so a bare
        # word never counts. The EXEC SQL/CICS block dual with ipc_rpc_bridges is the
        # existing deliberate one.
        "auth_middleware": re.compile(
            r"(?i)\bEXEC\s+CICS\s+(?:SIGNON|SIGNOFF|(?:VERIFY|CHANGE)\s+(?:PASSWORD|PHRASE)|QUERY\s+SECURITY)\b"
            r"|\bEXEC\s+SQL\s+(?:GRANT|REVOKE)\b"
        ),
        "serialization_parsing": re.compile(
            # #2990: EXEC CICS TRANSFORM DATATOXML / XMLTODATA / DATATOJSON / JSONTODATA.
            r"(?i)\b(UNSTRING|STRING|JSON\s+PARSE|JSON\s+GENERATE|XML\s+PARSE|XML\s+GENERATE|EXEC\s+CICS\s+TRANSFORM)\b"
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
        # #2990: ASKTIME / FORMATTIME / CONVERTTIME are CICS's clock and calendar calls
        # (119 crucible blocks in 51 files, no owner before this); the date intrinsics
        # convert between calendar forms; CEEGMT/CEEDATM/... are the LE date services.
        "time_date_logic": re.compile(
            r"(?i)\bACCEPT\s+[A-Za-z0-9_-]+\s+FROM\s+(?:DATE|TIME|DAY-OF-WEEK|DAY)\b|\b(?:CURRENT-DATE|WHEN-COMPILED)\b"
            r"|\bEXEC\s+CICS\s+(?:ASKTIME|FORMATTIME|CONVERTTIME)\b"
            r"|\bFUNCTION\s+(?:INTEGER-OF-DATE|DATE-OF-INTEGER|INTEGER-OF-DAY|DAY-OF-INTEGER|DATE-TO-YYYYMMDD"
            r"|DAY-TO-YYYYDDD|YEAR-TO-YYYY|SECONDS-PAST-MIDNIGHT|SECONDS-FROM-FORMATTED-TIME"
            r"|FORMATTED-(?:DATE|TIME|DATETIME|CURRENT-DATE)|INTEGER-OF-FORMATTED-DATE|COMBINED-DATETIME"
            r"|TEST-(?:DATE-YYYYMMDD|DAY-YYYYDDD|FORMATTED-DATETIME))(?![-\w])"
            r"|CALL\s+'CEE(?:GMT|DATM|DATE|LOCT|SECS|DAYS|UTC)'"
        ),
        # BUG FIX: `CALL\s+` shared a trailing `\b` with word-ending
        # siblings, but ends in whitespace (non-word) -- broke on the
        # dominant realistic call form, a quoted program-name literal
        # (`CALL 'SUBPROGRAM' USING ...`), where a quote (non-word)
        # follows the consumed whitespace. Only the less-common unquoted
        # data-name form (`CALL WS-PROGRAM-NAME`) happened to work.
        # #2484: channels and containers are the modern replacement for the
        # 32KB COMMAREA on LINK/XCTL, so they belong beside them -- 18 real
        # occurrences in the crucible (PUT 9, GET 9) that recorded no bridge
        # before this. MOVE CONTAINER is included for completeness; the
        # crucible carries none today.
        "ipc_rpc_bridges": re.compile(
            r"(?i)\bCALL\s+"
            # #2990: RUN TRANSID hands work to another transaction (START's shape: also
            # concurrency); INVOKE APPLICATION / SERVICE / WEBSERVICE cross to another
            # application context; EXEC DLI is the IMS database bridge beside EXEC SQL.
            r"|\bEXEC\s+CICS\s+(?:LINK|XCTL|START|RETURN|RUN\s+TRANSID|INVOKE\s+(?:APPLICATION|SERVICE|WEBSERVICE))\b"
            r"|\bEXEC\s+CICS\s+(?:PUT|GET|MOVE)\s+CONTAINER\b"
            r"|\bEXEC\s+(?:SQL|DLI)\b"
        ),
        # system_config_mutation (#3084): contract-level absence. deferred, see
        # 3084: EXEC CICS SET mutates running-CICS resource state (same intent
        # family as DFHCSDUP); adjudication owed before owning it.
        "system_config_mutation": None,
        # 50. calls_out (Information Flow / Call Graph)
        # Replaces the generic `name(` regex which falsely captured intrinsics/subscripts.
        # Captures explicit subroutine execution and cross-module linkages.
        # #3362: GO TO left calls_out -- a jump that never returns is not a call
        # (docs/calls_out_rule_contract.md C4) -- and is recorded beside it as a
        # transfer (`_transfers_out` below), so the paragraphs reached only by
        # GO TO (a quarter of the crucible's) stay reachable.
        # #3359: `(?<![\w-])`, not `\b` -- the scope terminators `END-PERFORM` /
        # `END-CALL` end in the verb, so `\b` let the NEXT statement's first word
        # (`END-PERFORM` newline `MOVE ...`) be captured as a callee.
        "calls_out": re.compile(r"(?i)(?<![\w-])(?:PERFORM|CALL)\s+['\"]?([A-Za-z0-9_-]+)['\"]?"),
        # #3393: in `CALL 'SUBPROG'` the literal IS the callee (as JCL's PGM=
        # is), but the literal shield blanked it before calls_out ran, so only
        # `CALL WS-PGM` and PERFORM reached calls_out_to. A literal right after
        # this verb is kept (detector._blank_literals_except_callee).
        "_calls_out_literal_callee": re.compile(r"(?i)(?<![\w-])CALL\s+$"),
        # #3359 (contract C2): the inline PERFORM forms (`PERFORM VARYING ...`,
        # `PERFORM UNTIL ...`, `PERFORM WITH TEST ...`) name no paragraph.
        "_calls_out_ignore": frozenset(
            {
                "varying",
                "until",
                "with",
            }
        ),
        # #3362: GO TO <paragraph|section> -- an unconditional transfer of control.
        # First target only for `GO TO A B C DEPENDING ON X` (one occurrence on
        # the whole crucible). WHENEVER ... GO TO (embedded SQL) is excluded: that
        # installs a handler, it does not transfer here.
        "_transfers_out": re.compile(r"(?i)(?<!SQLERROR\s)(?<!SQLWARNING\s)(?<!FOUND\s)\bGO\s+TO\s+([A-Za-z0-9_-]+)"),
        # #3197: a paragraph/section header begins a SENTENCE. `func_start`
        # alone cannot see that -- the deciding context is the PREVIOUS line,
        # and a lookbehind cannot span one -- so the last line of a multi-line
        # statement or data description (`DISPLAY 'Total: '` then
        # `WS-COUNT.`, `... REDEFINES` then `ACUP-OLD-OPEN-DATE.`) read as a
        # paragraph: 9 phantom units on IBM/zopeneditor-sample and 26 + 4 on
        # cics-banking-sample-application-cbsa, each one also splitting the
        # real paragraph's span. #2538 shielded three LE tokens of this shape
        # and deferred the structural fix to "file-level fixed/free-format
        # detection"; the sentence rule needs no such detection, and unlike an
        # Area-A column anchor it keeps the real Area-B paragraphs that accepted
        # source contains (crucible CBL0601v01InOutLineLoop.cbl et al).
        # Implemented by detector.py's `_cobol_sentence_start_offsets`.
        "_scope_filters": {"func_start": "cobol_sentence_start"},
        # COBOL words run through hyphens, and `\b` fires at every one of them,
        # so a keyword rule matched INSIDE names: `io` counted WRITE in
        # `WRITE-LINE` / `FAIL-ROUTINE-WRITE`, `serialization_parsing` counted
        # the `END-STRING` terminator as a STRING, `ipc_rpc_bridges` END-CALL,
        # `debug_prints` `SQLCODE-DISPLAY`, `api` `ENTRY-1`. Earlier fixes guarded
        # rules one at a time (#2537, #2772, #2888, #3359); this drops a match
        # glued to a hyphenated word for EVERY cobol rule (detector.py
        # _glued_to_hyphen_word). Found by the #3210 ground-truth work, where the
        # same `\b`-after-hyphen bug turned up in three independent readers.
        "_hyphenated_words": True,
    },
}
