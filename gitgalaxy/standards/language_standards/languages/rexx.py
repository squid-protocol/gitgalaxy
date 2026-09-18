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

# #2504: REXX -- z/OS TSO/E REXX and classic (SAA) REXX, plus the ooRexx
# directive surface (`::requires` / `::routine` / `::class` / `::method`),
# since `.rexx` files in the wild host ooRexx code too.
#
# A REXX symbol is letters, digits and `. ! ? _` plus the national characters
# `@ # $` (TSO/E REXX Reference, "Tokens"). `\w` covers letters/digits/`_`;
# `! ? @ # $` are regex NON-word characters, so a plain `\b` cannot guard a
# keyword against them (`?EXIT` would satisfy `\bEXIT`): bare keywords use
# these explicit guards, PL/I's discipline. `.` joins both guards -- a
# compound variable's tail (`rc.exit`) must not read as the keyword -- and
# stays OUT of the label-name class below (a label is a simple symbol).
_ID = r"[\w.!?@#$]"
_NAME = r"[\w!?@#$]"
_L = r"(?<![\w.!?@#$])"
_R = r"(?![\w.!?@#$])"

# A statement starts at a line start (REXX is line-oriented; `;` is optional),
# after a `;`, or after the continuation words THEN / ELSE / OTHERWISE.
# Unlike PL/I, a line start IS a statement start: REXX has no margin
# continuation -- continuation is an explicit trailing comma, and such a
# continuation line starts with an operator (`,` glues expressions), never
# with a bare `lvalue =`.
_STMT_START = r"(?:^[ \t]*|;[ \t]*|" + _L + r"(?:THEN|ELSE|OTHERWISE)" + _R + r"[ \t]+)"

# `EXIT` ends the program only when nothing names it as a jump target: real
# execs jump to a label called EXIT (`SIGNAL EXIT`, `CALL EXIT`). One
# fixed-width lookbehind per spacing (PL/I's _NOT_A_TARGET shape), plus a
# lookahead so the label's own definition line (`EXIT:`) is not a statement.
_NOT_A_TARGET = r"(?<!SIGNAL\s)(?<!SIGNAL\s\s)(?<!CALL\s)(?<!CALL\s\s)"

# The conditions SIGNAL ON / CALL ON can install a handler for (TSO/E REXX
# Reference, "Conditions"; ooRexx adds USER conditions and ANY).
_CONDS = r"(?:ERROR|FAILURE|HALT|NOVALUE|SYNTAX|LOSTDIGITS|NOTREADY|ANY|USER[ \t]+" + _NAME + r"{1,64})"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "z/OS TSO/E REXX (SAA) + Open Object Rexx 5.0 directives",
        "last_updated": "2026-09-16",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA (#2504's ask): `.rexx` is unambiguous, `.exec`
    # is the z/OS convention (Zowe, IBM samples: SYSEXEC members). `.cmd` is
    # CONTESTED -- the Windows/OS2 `batch` profile claims it too -- so it joins
    # COLLISION_FREQUENCIES (_lens_config.py) and never locks at Tier 1 on
    # extension alone; routing resolves through the internal_discriminator
    # below (the classic OS/2-and-z/OS rule: a .cmd that opens with `/*` is
    # REXX), ecosystem gravity, or the lexical scan.
    "extensions": [".rexx", ".exec", ".cmd"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS: the mainframe sources a REXX exec lives beside -- the
    # JCL that runs it (IRXJCL/IKJEFT01) and sibling execs in the same library.
    "discriminators": [".rexx", ".exec", ".jcl"],
    # TOXIC NEIGHBORS (hlasm's `.ld` reasoning): a `.cmd` sitting beside `.bat`
    # files is a Windows batch script, never REXX -- gravity must collapse the
    # claim there. (Tier 2's internal_discriminator still wins for a real REXX
    # exec wherever it lives; disqualifiers only gate the gravity path.)
    "disqualifiers": [".bat", ".btm"],
    # EXECUTION SIGNATURES: Regina/ooRexx scripts on Unix carry a shebang
    # (Regina documents the `#!` first line as a special case it skips).
    "shebangs": ["rexx", "regina", "rexx64", "oorexx"],
    # Rationale (how_to_add_a_language.md Step 4 item 8): REXX's comment is
    # `/* ... */` and it DOES nest ("comments may be nested within other
    # comments", TSO/E REXX Reference) -- the recursive_block algorithm -- but
    # the shared recursive_block family also strips `//` line comments, and
    # `//` is REXX's INTEGER-REMAINDER operator (`a // b`), so that family
    # would truncate real arithmetic. `recursive_block_rexx` is the same
    # nested-peel algorithm with REXX's own tokens (the haskell/lisp dialect
    # precedent, #621/#770): `--` line comments (ooRexx/Regina/NetRexx; classic
    # z/OS REXX has none, and adjacent `--` double-negation is vanishingly rare
    # in real source) and REXX quote morphology (quotes double to escape, no
    # backslash escapes, strings never span lines).
    "lexical_family": "recursive_block_rexx",
    # External execs and ::REQUIRES members resolve to PDS members / host
    # filesystems where case is not significant.
    "case_insensitive_imports": True,
    # Collision resolution for `.cmd` (the hlasm-vs-assembly `.asm` mechanism):
    # a `.cmd` whose FIRST token is `/*` is REXX by the platform's own loader
    # rule (OS/2's and z/OS's actual dispatch test), and PARSE / ADDRESS /
    # SIGNAL ON / EXECIO / `::` directives are REXX-only line shapes a batch
    # file cannot carry. Strictly consulted for known extension collisions,
    # never as a global scanner (language_lens.py's Tier 2 guard). Reads RAW
    # text, so the leading `/* REXX */` banner is exactly what it anchors.
    "internal_discriminator": re.compile(
        r"\A[ \t]*/\*"
        r"|^[ \t]*(?:PARSE[ \t]+(?:UPPER[ \t]+|LOWER[ \t]+)?(?:ARG|PULL|SOURCE|VAR)"
        r"|ADDRESS[ \t]+[A-Z@#$][\w@#$]{0,15}"
        r"|(?:SIGNAL|CALL)[ \t]+(?:ON|OFF)[ \t]"
        r"|::[ \t]*(?:REQUIRES|ROUTINE|CLASS|METHOD)\b)",
        re.M | re.I,
    ),
    # invocation_model: DEFAULT (by_name), deliberately: REXX reaches the units
    # func_start extracts by writing their names -- `CALL PROBE_IO`, the
    # function form `probe_io(x)`, and `SIGNAL label`. The #2866 census applies.
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch (#2822): IF / ELSE and the SELECT group's WHEN / OTHERWISE
        # arms; SELECT itself needs its `;`/end-of-line (or LABEL) shape so
        # prose in a string can't fire it; the loop openers DO WHILE / UNTIL /
        # FOREVER and the iterative `DO i = ...`. THEN is a continuation word
        # and END a closer (#2822 C2); a plain `DO;` is a group, not a choice;
        # LEAVE / ITERATE are transfers, not decisions.
        "branch": re.compile(
            _L
            + r"(?:IF|ELSE|WHEN|OTHERWISE)"
            + _R
            + r"|"
            + _L
            + r"SELECT(?=[ \t]*;|[ \t]*$|[ \t]+LABEL"
            + _R
            + r")"
            + r"|"
            + _L
            + r"DO[ \t]+(?:(?:WHILE|UNTIL|FOREVER)"
            + _R
            + r"|"
            + _NAME
            + r"{1,64}(?:\."
            + _NAME
            + r"{0,64}){0,4}[ \t]*=)",
            re.I | re.M,
        ),
        # args (#2773 fallback family): REXX has no formal parameter list on
        # the label -- the construct that stands in for a declared parameter
        # is the argument-parsing statement: `PARSE [UPPER|LOWER] ARG
        # <template>`, statement-position `ARG <template>` (its short form)
        # and ooRexx `USE [STRICT] ARG`. `ARG(1)` is the built-in function (a
        # call site) and never matches; bare ARG is anchored to a statement
        # start so `SAY ARG` stays a reference. Each alternative CAPTURES the
        # template (to the statement's `;`/EOL): detector.py's per-function
        # args counter reads the matched group, and a groupless match falls
        # back to whitespace-splitting group(0) -- 'parse arg' = 2 forever,
        # the ada #6169-shape artifact the bias report surfaced. REXX
        # templates separate arguments with commas, so the comma/whitespace
        # split over the real template is the honest count.
        "args": re.compile(
            _L
            + r"PARSE[ \t]+(?:UPPER[ \t]+|LOWER[ \t]+)?ARG"
            + _R
            + r"([^\n;]{0,200})"
            + r"|"
            + _STMT_START
            + r"(?:USE[ \t]+(?:STRICT[ \t]+)?ARG|ARG)"
            + _R
            + r"(?![ \t]*\()([^\n;]{0,200})",
            re.I | re.M,
        ),
        # structural_boundaries: the vocabulary tally of REXX's block
        # structure -- RETURN, PROCEDURE, END, NOP -- plus CALL (a call is not
        # a decision, #2764's family; CALL ON / OFF is the handler form and
        # safety's / safety_bypasses' alone).
        "structural_boundaries": re.compile(
            _L + r"(?:RETURN|PROCEDURE|END|NOP)" + _R + r"|" + _L + r"CALL" + _R + r"(?![ \t]+(?:ON|OFF)" + _R + r")",
            re.I,
        ),
        # func_start (#2856): a label -- `name:` at a statement's line start
        # -- opens the subroutine/function that CALL, the function form and
        # SIGNAL reach; the name is a simple symbol (no `.`). PROCEDURE, when
        # present, FOLLOWS the label on the same or next statement, so the
        # label alone is the opener. ooRexx's `::ROUTINE name` / `::METHOD
        # name` directives declare named callables the same way. A `::` line
        # never satisfies the label alternative (`:` is not in the name
        # class); Mode A reads the name from whichever group matched
        # (match.lastindex).
        "func_start": re.compile(
            r"^[ \t]*(" + _NAME + r"{1,250})[ \t]*:(?!:)"
            r"|^[ \t]*::[ \t]*(?:ROUTINE|METHOD)[ \t]+(" + _NAME + r"{1,250})",
            re.I | re.M,
        ),
        # class_start (#2856): ooRexx `::CLASS name` is the one named-type
        # declaration REXX has; classic REXX has none (the shell/makefile
        # stated-absence family would apply, but the ooRexx form is real in
        # `.rexx` files, so the rule carries it).
        "class_start": re.compile(
            r"^[ \t]*::[ \t]*CLASS[ \t]+(" + _NAME + r"{1,250})",
            re.I | re.M,
        ),
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety (#2869): SIGNAL ON / CALL ON install a condition handler --
        # REXX's try/catch -- and the z/OS return-code test `IF RC` / `WHEN
        # RC` is the response check every host-command exec writes (PL/I's
        # `IF SQLCODE` precedent). `¬` and `\` are REXX's negation characters.
        "safety": re.compile(
            _L + r"(?:SIGNAL|CALL)[ \t]+ON[ \t]+" + _CONDS + _R + r"|" + _L + r"(?:IF|WHEN)[ \t]*\(?[ \t]*RC" + _R,
            re.I,
        ),
        # safety_bypasses: SIGNAL OFF / CALL OFF remove an installed handler
        # (the disabling form), and the bare `SIGNAL label` / `SIGNAL VALUE
        # expr` is an unstructured jump -- the GO TO ruling (PL/I's key). The
        # jump alternative excludes ON / OFF so a handler install never counts
        # twice.
        "safety_bypasses": re.compile(
            _L
            + r"(?:SIGNAL|CALL)[ \t]+OFF[ \t]+"
            + _CONDS
            + _R
            + r"|"
            + _L
            + r"SIGNAL[ \t]+(?!ON"
            + _R
            + r"|OFF"
            + _R
            + r")(?:VALUE[ \t]+)?"
            + _NAME
            + r"{1,250}",
            re.I,
        ),
        # high_risk_execution (#2878): INTERPRET runs text as code (the eval
        # family) and EXIT ends the whole program -- even from inside a nested
        # subroutine -- the termination family (deliberate panics_and_aborts
        # dual). EXIT excludes its own label definition (`EXIT:`) and jump
        # operands (`SIGNAL EXIT`).
        "high_risk_execution": re.compile(
            _L + r"INTERPRET" + _R + r"|" + _NOT_A_TARGET + _L + r"EXIT" + _R + r"(?![ \t]*:)",
            re.I,
        ),
        # io (#2841): EXECIO is z/OS REXX's dataset I/O (issued as a quoted
        # host command -- strings stay in the code stream, Rule 18, so the
        # quoted form is exactly what fires); the SAA stream functions
        # LINEIN / LINEOUT / CHARIN / CHAROUT / STREAM and TSO's OUTTRAP in
        # call form; PULL / PARSE PULL read the external data queue or
        # terminal and PUSH / QUEUE write it (the stack is how execs feed
        # EXECIO and host commands -- it crosses the program boundary). The
        # PARSE PULL alternative comes first so one statement is one hit; the
        # bare stack verbs are statement-anchored so a variable named `queue`
        # in expression position stays invisible.
        "io": re.compile(
            _L
            + r"EXECIO"
            + _R
            + r"|"
            + _L
            + r"(?:LINEIN|LINEOUT|CHARIN|CHAROUT|STREAM|OUTTRAP)[ \t]*\("
            + r"|"
            + _L
            + r"PARSE[ \t]+(?:UPPER[ \t]+|LOWER[ \t]+)?PULL"
            + _R
            + r"|"
            + _STMT_START
            + r"(?:PULL|PUSH|QUEUE)"
            + _R
            + r"(?![ \t]*[=(])",
            re.I | re.M,
        ),
        # api (#2730): the explicit publishing marker REXX has -- an ooRexx
        # directive declared PUBLIC. Classic REXX has no per-function
        # visibility syntax at all (an exec is reached by member name, not by
        # a declaration), so classic files legitimately read 0.
        "api": re.compile(
            r"^[ \t]*::[ \t]*(?:ROUTINE|CLASS|METHOD|ATTRIBUTE)[ \t]+"
            + _NAME
            + r"{1,250}(?:[ \t]+"
            + _NAME
            + r"{1,64}){0,5}[ \t]+PUBLIC"
            + _R,
            re.I | re.M,
        ),
        # state_mutation (#2765): REXX has no declaration syntax, so the
        # assignment statement is the write and counts (the shell/php/tcl
        # ruling): a bare lvalue -- simple or compound symbol (`rec.1`,
        # trailing-dot stem `rec.`) -- at a statement start, followed by `=`.
        # `IF X = 1` and `DO I = 1` never match: the keyword sits at the
        # statement start and the comparison's lvalue does not. PARSE VAR /
        # PARSE VALUE assign through a template -- the same write (PARSE ARG
        # is args', PARSE PULL io's: one owner per form).
        # (The compound tail's segment class is _NAME, not _ID: a dot inside
        # the segment class overlaps the `\.` separator -- how_to Rule 14's
        # adjacent-quantifier shape, caught by the strict suite's detonation
        # on a long dot run. Each `\.` owns its dot; segments hold none.)
        "state_mutation": re.compile(
            _STMT_START
            + _NAME
            + r"{1,64}(?:\."
            + _NAME
            + r"{0,64}){0,6}[ \t]*=(?!=)"
            + r"|"
            + _L
            + r"PARSE[ \t]+(?:UPPER[ \t]+|LOWER[ \t]+)?(?:VAR|VALUE)"
            + _R,
            re.I | re.M,
        ),
        # dead_code: a comment whose text is a REXX statement -- a CALL, an
        # IF ... THEN, a loop opener, an EXECIO, a PARSE statement or an
        # assignment. Wired to BOTH comment styles the family supports
        # (Rule 12): `/*` blocks and `--` lines. Bare SAY / ADDRESS are left
        # out deliberately -- "say" and "address" are everyday English words
        # in comment prose.
        "dead_code": re.compile(
            r"(?:/\*|--)[ \t]*(?:CALL[ \t]+" + _NAME + r"{1,64}"
            r"|IF[ \t][^\n]{0,120}?" + _L + r"THEN" + _R + r"|DO[ \t]+(?:WHILE|UNTIL)" + _R + r"|EXECIO[ \t]"
            r"|PARSE[ \t]+(?:UPPER[ \t]+|LOWER[ \t]+)?(?:ARG|VAR|VALUE|PULL)"
            + _R
            + r"|"
            + _NAME
            + r"{1,64}[ \t]*=[ \t]*[\w.!?@#$'\"])",
            re.I,
        ),
        # doc: REXX has no generator-read comment syntax of its own; the
        # conventions in real execs are a `/**` doc block left open past its
        # own line (PL/I's rule -- a one-line `/** ... **/` is an emphasised
        # banner) and the z/OS header-box tags PURPOSE: / DESCRIPTION: /
        # ABSTRACT: / REMARKS: / FUNCTION:.
        "doc": re.compile(
            r"/\*\*(?![*/])(?![^\n]*\*/)"
            r"|^[ \t]*(?:/\*+|\*+|--+)[ \t]*(?:PURPOSE|DESCRIPTION|ABSTRACT|REMARKS|FUNCTION)[ \t]*:",
            re.I | re.M,
        ),
        # test (#2852): no framework executes classic REXX test cases as a
        # recognized idiom (ooTest exists but has no per-case keyword an
        # everyday exec carries). Stated absence.
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # concurrency: classic/z/OS REXX has no asynchronous form. (ooRexx's
        # early-REPLY is real but marginal; recorded absence.)
        "concurrency": None,
        # ui_framework: the ISPF panel services -- the 3270 surface a TSO exec
        # drives: `ISPEXEC` followed on the same command by DISPLAY / ADDPOP /
        # REMPOP / SETMSG / PQUERY / LMDDISP. Quoted host commands stay in the
        # code stream, so the idiomatic `Address ISPEXEC "DISPLAY PANEL(P1)"`
        # is exactly what fires.
        "ui_framework": re.compile(
            _L + r"ISPEXEC[^;\n]{0,120}?" + _L + r"(?:DISPLAY|ADDPOP|REMPOP|SETMSG|PQUERY|LMDDISP)" + _R,
            re.I,
        ),
        # closures: REXX has no anonymous callable; every routine is a label.
        "closures": None,
        # globals (#2858): `PROCEDURE EXPOSE` names the caller-pool (program
        # lifetime) bindings a protected routine shares; SYSVAR( / MVSVAR(
        # read the system's ambient state through its named handles; ooRexx's
        # `.environment` / `.local` are the process's named environment
        # objects (the lookbehind keeps a compound variable's `a.local` tail
        # invisible).
        "globals": re.compile(
            _L
            + r"PROCEDURE[ \t]+EXPOSE"
            + _R
            + r"|"
            + _L
            + r"(?:SYSVAR|MVSVAR)[ \t]*\("
            + r"|"
            + _L
            + r"\.(?:ENVIRONMENT|LOCAL)"
            + _R,
            re.I,
        ),
        # decorators: no attribute syntax. OPTIONS is a runtime instruction,
        # not a marker attached to a declaration.
        "decorators": None,
        # generics: no parametric types.
        "generics": None,
        # comprehensions: no collection-transform form.
        "comprehensions": None,
        # scientific: RANDOM( is the one numeric built-in beyond everyday
        # arithmetic (REXX has no native SQRT/SIN/...; ABS/MAX/MIN are
        # everyday words and array-like subscripts).
        "scientific": re.compile(_L + r"RANDOM[ \t]*\(", re.I),
        # reflection_metaprogramming: VALUE( reads/writes a variable by
        # computed name, SYMBOL( asks whether a name is a variable, and
        # SOURCELINE( reads the program's own source text.
        "reflection_metaprogramming": re.compile(
            _L + r"(?:VALUE|SYMBOL|SOURCELINE)[ \t]*\(",
            re.I,
        ),
        # import (#2875): ooRexx `::REQUIRES` is REXX's one dependency-binding
        # form. Classic REXX reaches another exec by CALL -- an invocation,
        # not a binding -- so classic files legitimately read 0.
        "import": re.compile(r"^[ \t]*::[ \t]*REQUIRES" + _R, re.I | re.M),
        # _dependency_capture: the required file -- quoted (`::requires
        # 'a.rexx'`) or bare. galaxyscope reads the first non-empty group.
        "_dependency_capture": re.compile(
            r"::[ \t]*REQUIRES[ \t]+(?:['\"]([^'\"\n]{1,200})['\"]|(" + _ID + r"{1,200}))",
            re.I,
        ),
        # ownership (#2882): an author/maintainer tag inside a `/* */` block
        # or `--` line comment -- PL/I's rule with the family's markers.
        "ownership": re.compile(
            r"@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/)?[ \t]*$"
            r"|^[ \t]*(?:/\*+|\*+|--+)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)"
            r"[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # hardcoded_secrets: a baseline rule in three languages only; the
        # security lens's own detector covers REXX.
        "hardcoded_secrets": None,
        "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*[0-9]{1,10}|spec|audit)\]", re.I),
        # ssr_boundaries: no rendering framework.
        "ssr_boundaries": None,
        # events: no event/message channel of its own.
        "events": None,
        "dependency_injection": None,
        # macros: no preprocessor or macro system.
        "macros": None,
        # pointers: STORAGE( reads or writes absolute storage addresses
        # (TSO/E) -- a raw-address dereference in call form.
        "pointers": re.compile(_L + r"STORAGE[ \t]*\(", re.I),
        # memory_alloc: no allocator call; REXX storage is implicit.
        "memory_alloc": None,
        # inline_asm: no embedding form.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # telemetry: the TRACE instruction is REXX's built-in execution
        # tracing (observability of the running exec). TRACE( is the built-in
        # function (reads the current setting) and does not count.
        "telemetry": re.compile(_L + r"TRACE" + _R + r"(?![ \t]*\()", re.I),
        # debug_prints: SAY writes to the terminal -- the print statement.
        "debug_prints": re.compile(_L + r"SAY" + _R, re.I),
        # explicit_casts: the radix/encoding conversion built-ins in call
        # form -- REXX's explicit representation changes.
        "explicit_casts": re.compile(
            _L + r"(?:C2D|C2X|D2C|D2X|X2C|X2D|B2X|X2B)[ \t]*\(",
            re.I,
        ),
        # panics_and_aborts: EXIT ends execution (the deliberate
        # high_risk_execution dual, #2878 -- same guards), and ooRexx RAISE
        # raises a condition (REXX's throw), anchored to its condition word so
        # an everyday identifier `raise` stays invisible.
        "panics_and_aborts": re.compile(
            _NOT_A_TARGET
            + _L
            + r"EXIT"
            + _R
            + r"(?![ \t]*:)"
            + r"|"
            + _L
            + r"RAISE[ \t]+(?:ERROR|FAILURE|SYNTAX|HALT|NOVALUE|NOTREADY|LOSTDIGITS|PROPAGATE|USER"
            + _R
            + r")",
            re.I,
        ),
        # thread_sleeps: SysSleep -- RexxUtil's blocking delay (ooRexx /
        # Regina), in call or CALL-statement form.
        "thread_sleeps": re.compile(
            _L + r"SYSSLEEP[ \t]*\(|" + _L + r"CALL[ \t]+SYSSLEEP" + _R,
            re.I,
        ),
        # bitwise_ops: the bit built-ins in call form; REXX has no bitwise
        # operators (`&` / `|` are its logical operators).
        "bitwise_ops": re.compile(_L + r"(?:BITAND|BITOR|BITXOR)[ \t]*\(", re.I),
        # sync_locks: no coordination primitive of its own.
        "sync_locks": None,
        # immutability_locks (#2772): ooRexx `::CONSTANT` is the restricted
        # constant-declaration form distinct from the general-purpose binding.
        # Classic REXX has none.
        "immutability_locks": re.compile(r"^[ \t]*::[ \t]*CONSTANT" + _R, re.I | re.M),
        # cleanup (#2888): DROP returns variables to their unset state (the
        # matlab `clear` ruling); FINIS is EXECIO's close operand (inside the
        # quoted host command, which stays in the code stream); `FREE
        # F(...)` / `FI(` / `DD(` / `DDNAME(` is TSO's deallocation command in
        # the same quoted form.
        "cleanup": re.compile(
            _L
            + r"DROP[ \t]+"
            + _NAME
            + r"|"
            + _L
            + r"FINIS"
            + _R
            + r"|"
            + _L
            + r"FREE[ \t]+(?:DDNAME|DATASET|DSNAME|DD|DA|FI|F)[ \t]*\(",
            re.I,
        ),
        # encapsulation (#2766): an ooRexx directive declared PRIVATE -- the
        # declaration-position marker that excludes the name from the public
        # surface. PROCEDURE (lexical scoping) is scope, not visibility -- the
        # perl/shell ruling -- and never counts.
        "encapsulation": re.compile(
            r"^[ \t]*::[ \t]*(?:METHOD|ROUTINE|ATTRIBUTE)[ \t]+"
            + _NAME
            + r"{1,250}(?:[ \t]+"
            + _NAME
            + r"{1,64}){0,5}[ \t]+PRIVATE"
            + _R,
            re.I | re.M,
        ),
        # listeners: no subscription form.
        "listeners": None,
        # test_skip: no test framework, no skip marker.
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        # auth_middleware (#3004): contract-level absence. RACF administration
        # from rexx rides quoted host-command strings through ADDRESS TSO --
        # the bridge statement is ipc_rpc_bridges' -- and the language itself
        # has no auth vocabulary.
        "auth_middleware": None,
        # serialization_parsing: PARSE is template parsing of strings, not an
        # interchange format (the fortran exclusion's shape).
        "serialization_parsing": None,
        # regex_execution: POS / INDEX / VERIFY take no pattern -- plain
        # substring/character-set searches (the declared row's exclusion).
        "regex_execution": None,
        # time_date_logic: the DATE( and TIME( built-ins in call form -- the
        # language's clock/calendar constructors.
        "time_date_logic": re.compile(_L + r"(?:DATE|TIME)[ \t]*\(", re.I),
        # ipc_rpc_bridges: the ADDRESS statement routes commands to another
        # subsystem -- TSO, ISPEXEC, CICS, SYSCALL, an external environment --
        # REXX's host-command bridge. DOCUMENTED DEVIATION from #2504's issue
        # text (which grouped ADDRESS under io): the io contract's data movers
        # are EXECIO/LINEIN/..., and the bridge statement is ipc's "site that
        # crosses a process or host boundary" (the hlasm-DSECT
        # contract-over-issue-text shape, pinned in the strict suite).
        # ADDRESS( is the built-in function (reads the current environment)
        # and does not count.
        "ipc_rpc_bridges": re.compile(_L + r"ADDRESS" + _R + r"(?![ \t]*\()", re.I),
        # system_config_mutation (#3084): contract-level absence. deferred, see
        # 3084: ADDRESS host-command environments (16 crucible files) can
        # durably alter system state, but the command text is opaque at the
        # language layer and executor ownership is high_risk_execution's.
        "system_config_mutation": None,
    },
}
