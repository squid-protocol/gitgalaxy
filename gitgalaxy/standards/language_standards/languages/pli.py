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

# PL/I identifiers are letters, digits, `_`, `@`, `#` and `$` (IBM Enterprise PL/I
# Language Reference, "Identifiers"), and real mainframe source also carries national
# letters -- navikt/DSF names procedures `KONTROLLER_AU_SØKER`. `\w` is Unicode-aware
# on a str pattern, so `[\w@#$]` covers both. `@#$` are regex NON-word characters, so
# a plain `\b` cannot guard a keyword against them (`$STOP` would satisfy `\bSTOP`):
# every bare keyword below uses these explicit guards instead. `%` joins the left
# guard wherever the same word is also a preprocessor statement (`%IF`, `%DO`, `%END`).
_ID = r"[\w@#$]"
_L = r"(?<![\w@#$%])"
_R = r"(?![\w@#$])"

# Condition names an ON statement can install a handler for (Language Reference,
# "Conditions"), with their documented abbreviations. The file conditions and
# CONDITION(name) always carry a parenthesised reference, which the rules require --
# `KEY`, `NAME` and `RECORD` are everyday words, and Rocket BankDemo's prose carries
# 62 `ON WEDNESDAY` hits that must not read as a handler.
_ON_BARE = (
    r"(?:ANYCONDITION|ANYCOND|AREA|ATTENTION|ATTN|CONVERSION|CONV|ERROR|FINISH|FIXEDOVERFLOW|FOFL"
    r"|INVALIDOP|OVERFLOW|OFL|SIZE|STORAGE|STRINGRANGE|STRG|STRINGSIZE|STRZ|SUBSCRIPTRANGE|SUBRG"
    r"|UNDERFLOW|UFL|ZERODIVIDE|ZDIV)"
)
_ON_FILE = r"(?:ENDFILE|ENDPAGE|KEY|NAME|RECORD|TRANSMIT|UNDEFINEDFILE|UNDF|CONDITION|COND)[ \t]*\([^()\n]{0,64}\)"
_ON_UNIT = r"\bON[ \t]+(?:" + _ON_BARE + _R + r"|" + _ON_FILE + r")"

# Checks a condition prefix `(<conds>):` switches ON for the one statement it prefixes
# (SIZE, SUBSCRIPTRANGE, STRINGRANGE and STRINGSIZE are disabled by default), and the
# NO- forms that switch a default-enabled check OFF. The prefix list is bounded
# (`{0,5}`) and must close with `):` -- `CHAR(SIZE)` has no colon and never matches.
_PREFIX_TAIL = r"(?:[ \t]*,[ \t]*[A-Z]{2,16}){0,5}[ \t]*\)[ \t]*:"
_ENABLE_PREFIX = r"\([ \t]*(?:SUBSCRIPTRANGE|SUBRG|STRINGRANGE|STRG|STRINGSIZE|STRZ|SIZE|CHECK)" + _PREFIX_TAIL
_DISABLE_PREFIX = (
    r"\([ \t]*NO(?:SUBSCRIPTRANGE|SUBRG|STRINGRANGE|STRG|STRINGSIZE|STRZ|SIZE|FIXEDOVERFLOW|FOFL"
    r"|OVERFLOW|OFL|ZERODIVIDE|ZDIV|CONVERSION|CONV|UNDERFLOW|UFL|INVALIDOP)" + _PREFIX_TAIL
)

# A statement starts after `;`, or after THEN / ELSE / OTHERWISE, or after a WHEN(...)
# guard. Real fixed-format source (navikt/DSF) carries an 8-digit sequence number in
# columns 73-80 of every line, so the gap after a `;` may hold one before the next line.
# A line start alone is NOT a statement start: a multi-line IF condition continues
# `B01.Y = 'U' !` at the margin, and that `=` is a comparison.
_SEQ = r"(?:[A-Z]{0,4}[0-9]{2,8}[ \t]{0,8})?"
_STMT_START = (
    r"(?:;[ \t]{0,80}" + _SEQ + r"(?:\r?\n[ \t]{0,80}" + _SEQ + r"){0,3}"
    r"|\b(?:THEN|ELSE|OTHERWISE)[ \t\r\n]{1,80}"
    r"|\bWHEN[ \t]*\((?:[^()\n]|\([^()\n]*\)){0,120}\)[ \t]{1,80})"
)

# `STOP;` / `EXIT;` are statements only when nothing names them as an operand: the
# Zowe samples jump to a label called EXIT (`GO TO EXIT;`, `THEN GOTO EXIT;`), and a
# procedure may be named STOP (`CALL STOP;`). One fixed-width lookbehind per spacing.
_NOT_A_TARGET = r"(?<!TO\s)(?<!TO\s\s)(?<!CALL\s)"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "IBM Enterprise PL/I for z/OS 6.1 (also the ANSI X3.53-1976 subset)",
        "last_updated": "2026-09-15",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: `.pli` is IBM's own convention (Z Open Editor, zAppBuild,
    # DBB), `.pl1` the historic one. `.inc` is deliberately NOT claimed: PL/I shops use it
    # for %INCLUDE members, but so do PHP, Pascal, NASM and every assembler -- the
    # extension says nothing about which language is inside. `.plinc` is unambiguous.
    "extensions": [".pli", ".pl1", ".plinc"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS: sibling mainframe sources that live beside PL/I in the same
    # repository (the BMS maps and JCL that compile and run it).
    "discriminators": [".pli", ".pl1", ".jcl", ".bms"],
    # EXECUTION SIGNATURES: PL/I is compiled; no interpreter shebang exists.
    "shebangs": [],
    # Rationale (how_to_add_a_language.md Step 4 item 8): PL/I's comment is `/* ... */`
    # and it does NOT nest (the first `*/` closes it, Language Reference "Comments").
    # Enterprise PL/I also accepts `//` line comments -- the Zowe PL/I language-support
    # samples use them (`DCL BUF1_CLOB; // SQL TYPE IS CLOB_FILE;`) -- and `//` is no
    # operator (concatenation is `||`), so the C-style standard_block family is exact.
    # It is NOT positional_anchored like COBOL: PL/I's margins (2-72) are a compiler
    # option, not a column-indicator comment syntax.
    "lexical_family": "standard_block",
    # %INCLUDE member names resolve to PDS members, which are case-insensitive:
    # `%INCLUDE p0019908;` binds the same member as `%INCLUDE P0019908;`.
    "case_insensitive_imports": True,
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: IF / ELSE, the SELECT group and its WHEN / OTHERWISE arms, and the loop
        # openers (DO WHILE / UNTIL / LOOP / FOREVER and the iterative `DO I = ...`). A
        # plain `DO;` is a group, not a choice, and THEN / END are continuation and closing
        # words (#2822 C2). `SELECT` needs its `(expr);` or `;` form so `EXEC SQL SELECT col`
        # stays SQL. `%IF` / `%DO` are the preprocessor's (macros). `&` and `|` are PL/I's
        # logical operators but also operate on bit strings, and `||` is concatenation, so
        # the operator form is not counted. ON-units are safety's -- an installed handler.
        "branch": re.compile(
            _L
            + r"(?:IF|ELSE|OTHERWISE|WHEN)"
            + _R
            + r"|"
            + _L
            + r"SELECT(?=[ \t]*[(;])"
            + r"|"
            + _L
            + r"DO[ \t]+(?:(?:WHILE|UNTIL|LOOP|FOREVER)"
            + _R
            + r"|"
            + _ID
            + r"{1,31}[ \t]*=)",
            re.I,
        ),
        # args: the parameter list of a PROCEDURE statement or a secondary ENTRY statement.
        # PL/I parameter lists hold bare names (their attributes are DECLAREd in the body),
        # so one level of plain names is the whole grammar. Anchored to the declaring
        # statement's own `label:` (func_start's shape): `CALL P(X, Y)` passes actuals,
        # `DCL E ENTRY(CHAR(8))` describes an external entry's parameters, and a
        # preprocessor procedure's `%DOUBLE: PROCEDURE(N)` runs at compile time -- none of
        # them declares a parameter of an executable unit (#2773 contract).
        "args": re.compile(
            r"(?<![\w@#$%])" + _ID + r"{1,64}[ \t]*:"
            r"(?:[ \t]{0,80}" + _SEQ + r"\r?\n){0,3}[ \t]{0,80}"
            r"(?:PROC(?:EDURE)?|ENTRY)[ \t\r\n]{0,20}\(([^()]{0,500})\)",
            re.I,
        ),
        # structural_boundaries: #1142's ask (PROCEDURE / BEGIN / END) plus RETURN, the
        # DECLARE statement and PACKAGE -- the vocabulary tally of PL/I's block structure.
        "structural_boundaries": re.compile(
            _L + r"(?:PROC(?:EDURE)?|BEGIN|END|RETURN|DCL|DECLARE|PACKAGE)" + _R,
            re.I,
        ),
        # func_start: `label: PROCEDURE` (or `PROC`). The name is the label IMMEDIATELY
        # before the keyword, so a multi-label `A: B: PROC;` yields `B` (finditer never
        # sees `A` as adjacent) and a condition prefix `(SUBRG): name: PROC` is skipped
        # naturally. Real fixed-format source puts the label and PROC on separate lines
        # with a sequence number in columns 73-80 between them (navikt/DSF R0011803.pli:
        # `KONTROLLER_AU_SØKER:  00000480` / `PROC(FEIL_FUNNET);`), so up to three line
        # breaks, each optionally carrying a sequence field, may separate the two. A
        # preprocessor procedure (`%SETUPL: PROC`) runs at compile time and is macros',
        # not an executable block. BEGIN blocks are unnamed and ENTRY is an alternate way
        # into an existing procedure (api's), so neither opens a new unit here.
        "func_start": re.compile(
            r"(?<![\w@#$%])(" + _ID + r"{1,64})[ \t]*:"
            r"(?:[ \t]{0,80}" + _SEQ + r"\r?\n){0,3}[ \t]{0,80}"
            r"PROC(?:EDURE)?" + _R,
            re.I,
        ),
        # class_start: PL/I has no classes. Enterprise PL/I's named-type declarations are
        # DEFINE STRUCTURE (a named record type) and DEFINE ORDINAL (an enum) -- both
        # listed in the #2856 contract's "struct, record ... enum". DEFINE ALIAS is a type
        # alias and declares no new type.
        "class_start": re.compile(
            _L + r"DEFINE[ \t\r\n]+(?:STRUCTURE[ \t\r\n]+[0-9]{1,2}[ \t\r\n]+|ORDINAL[ \t\r\n]+)(" + _ID + r"{1,64})",
            re.I,
        ),
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety (#2869): an ON-unit installs a handler for a condition -- PL/I's
        # try/catch -- except the null on-unit `ON cond;`, which swallows it
        # (safety_bypasses'). An enabling condition prefix `(SUBSCRIPTRANGE):` switches a
        # runtime check on for the statement. The CICS / SQL / DLI vocabulary is cobol's,
        # verbatim (#2990), so the two mainframe hosts count the same commands the same
        # way: HANDLE CONDITION / ABEND, PUSH / POP HANDLE, SYNCPOINT / RESYNC, SQL
        # COMMIT / ROLLBACK / WHENEVER ... GO TO, DLI checkpoints, DFHRESP( checks and
        # `IF SQLCODE` response tests. PL/I writes the SQLCODE test with or without a
        # parenthesis (`IF SQLCODE < 0`, `IF (SQLCODE ^= 0)`).
        "safety": re.compile(
            _ON_UNIT
            + r"(?![ \t]*;)"
            + r"|"
            + _ENABLE_PREFIX
            + r"|\bEXEC\s+CICS\s+(?:HANDLE\s+(?:CONDITION|ABEND)|PUSH\s+HANDLE|POP\s+HANDLE|SYNCPOINT|RESYNC)\b"
            r"|\bEXEC\s+SQL\s+(?:COMMIT|ROLLBACK|WHENEVER\s+(?:SQLERROR|SQLWARNING|NOT\s+FOUND)\s+GO\s*TO)\b"
            r"|\bEXEC\s+DLI\s+(?:CHKP|SYMCHKP|ROLB|ROLL|ROLS)\b"
            r"|\bDFHRESP[ \t]*\("
            r"|" + _L + r"(?:IF|SELECT)[ \t]*\(?[ \t]*(?:SQLCODE|SQLSTATE)" + _R,
            re.I,
        ),
        # safety_bypasses: a disabling condition prefix `(NOSIZE):` switches a runtime
        # check off; a null on-unit `ON CONVERSION;` swallows the condition; GO TO is an
        # unstructured jump (cobol's GO TO, same key). The CICS / SQL error-swallowing
        # forms are cobol's: IGNORE CONDITION, NOHANDLE, WHENEVER ... CONTINUE. The GO TO
        # alternative is guarded so a `WHENEVER SQLERROR GO TO` handler install (safety's)
        # does not count twice.
        "safety_bypasses": re.compile(
            _DISABLE_PREFIX
            + r"|"
            + _ON_UNIT
            + r"[ \t]*;"
            + r"|(?<!SQLERROR\s)(?<!SQLWARNING\s)(?<!FOUND\s)"
            + _L
            + r"GO[ \t]*TO"
            + _R
            + r"|\bEXEC\s+CICS\s+IGNORE\s+CONDITION\b"
            r"|"
            + _L
            + r"NOHANDLE"
            + _R
            + r"|\bEXEC\s+SQL\s+WHENEVER\s+(?:SQLERROR|SQLWARNING|NOT\s+FOUND)\s+CONTINUE\b",
            re.I,
        ),
        # high_risk_execution (#2878): STOP ends the program (raising FINISH) and EXIT ends
        # the thread -- the termination family, cobol's STOP RUN. FETCH loads an executable
        # module at run time and RELEASE unloads it (the loading-code family; cobol's
        # CANCEL). Both need the statement's own shape, a module name and the `;` (or a
        # TITLE option), so `EXEC SQL FETCH C1 INTO ...` and CICS `SEND PAGE RELEASE`
        # never reach them. Dynamic SQL is cobol's family-2 alternative, verbatim.
        "high_risk_execution": re.compile(
            _NOT_A_TARGET
            + _L
            + r"(?:STOP|EXIT)[ \t]*;"
            + r"|(?<!SQL\s)(?<!PAGE\s)"
            + _L
            + r"(?:FETCH|RELEASE)[ \t]+"
            + _ID
            + r"{1,31}[ \t]*(?:TITLE[ \t]*\([^()\n]{0,64}\)[ \t]*)?;"
            + r"|\bEXEC\s+SQL\s+(?:PREPARE|EXECUTE(?:\s+IMMEDIATE)?|TRUNCATE|DROP\s+DATABASE)\b",
            re.I,
        ),
        # io (#2841): PL/I's record I/O statements name their file in a FILE( option --
        # OPEN / READ / WRITE / REWRITE / DELETE FILE(...), `LOCATE rec FILE(...)` -- and
        # its stream input is GET (from SYSIN or a FILE). Stream OUTPUT is split by where it
        # goes: `PUT ... FILE(f)` to a named file is io, `PUT SKIP LIST(...)` to SYSPRINT is
        # the print statement (debug_prints'), and `GET` / `PUT STRING(...)` format memory,
        # crossing no boundary. CLOSE is cleanup's (#2841 C2). One statement is one hit:
        # `OPEN FILE(A), FILE(B);` matches once, at OPEN.
        #
        # The CICS / DLI vocabulary is cobol's verbatim (#2485, #2990), and PL/I's DL/I
        # call interface is `CALL PLITDLI(` (unquoted -- cobol writes `CALL 'CBLTDLI'`).
        # `EXEC SQL` counts as cobol's embedded-database boundary except for the four
        # statements that move no data: INCLUDE (import's), DECLARE (a cursor or table
        # definition), WHENEVER (safety's handler install) and BEGIN/END DECLARE SECTION.
        # finditer never re-reads `READ FILE(` inside `EXEC CICS READ FILE(...)`: the CICS
        # alternative consumes through the verb first.
        "io": re.compile(
            r"\bEXEC\s+CICS\s+(?:READQ|WRITEQ|DELETEQ)\s+(?:TS|TD)\b"
            r"|\bEXEC\s+CICS\s+(?:READ|WRITE|REWRITE|DELETE|UNLOCK|STARTBR|READNEXT|READPREV|ENDBR|RESETBR"
            r"|SPOOL(?:OPEN|READ|WRITE|CLOSE)|(?:DEFINE|GET|QUERY|UPDATE|REWIND|DELETE)\s+D?COUNTER)\b"
            r"|\bEXEC\s+SQL\b(?!\s+(?:INCLUDE|DECLARE|WHENEVER|BEGIN\s+DECLARE|END\s+DECLARE)\b)"
            r"|\bEXEC\s+DLI\b"
            r"|\bCALL[ \t]+(?:PLITDLI|AIBTDLI|CEETDLI)"
            + _R
            + r"|"
            + _L
            + r"(?:OPEN|READ|WRITE|REWRITE|DELETE)[ \t\r\n]+FILE[ \t]*\("
            + r"|"
            + _L
            + r"LOCATE[ \t]+"
            + _ID
            + r"[\w@#$.]{0,63}[ \t\r\n]+FILE[ \t]*\("
            + r"|"
            + _L
            + r"GET(?=[ \t\r\n]+(?:FILE|EDIT|LIST|DATA|SKIP|COPY)"
            + _R
            + r")"
            + r"|"
            + _L
            + r"PUT(?=[^;]{0,300}?\bFILE[ \t]*\((?![ \t]*SYSPRINT[ \t]*\)))",
            re.I,
        ),
        # api (#2730): the explicit publishing markers PL/I has. An external procedure is
        # public by default, but nothing in the syntax separates it from an internal one
        # (both sit in column 2 -- navikt/DSF's %INCLUDE members hold internal procedures
        # at the same margin), so this is the fallback family (docs/api_rule_contract.md):
        # a PACKAGE's EXPORTS list, a procedure declared OPTIONS(MAIN) or
        # OPTIONS(FETCHABLE) (the entry points the runtime and FETCH reach), and a
        # secondary `label: ENTRY` statement. `DCL x ENTRY EXTERNAL` declares a reference
        # to someone else's entry and does not count.
        "api": re.compile(
            _L
            + r"EXPORTS[ \t]*\("
            + r"|"
            + _L
            + r"OPTIONS[ \t]*\([^()\n]{0,40}?"
            + _L
            + r"(?:MAIN|FETCHABLE)"
            + _R
            + r"|(?<=:)[ \t]*ENTRY"
            + _R
            + r"(?![ \t]*EXT)",
            re.I,
        ),
        # A PACKAGE statement names every exported procedure in one list; that mention
        # must not clear those procedures' unreferenced_by_name flag (#2823's shape, the
        # haskell/scheme export list). `EXPORTS(*)` names nothing and is harmless.
        "_visibility_export_list": re.compile(r"\bEXPORTS[ \t]*\(([^()]{0,4000})\)", re.I),
        # state_mutation (#2765): an assignment statement -- a bare lvalue (qualified,
        # subscripted or pointer-qualified) followed by `=` or a compound operator
        # (`+=`, `-=`, `*=`, `/=`, `||=`, `|=`, `&=`) -- anchored to a statement start.
        # PL/I spells equality and assignment the same way, so the anchor is the whole
        # rule: `IF X = 1 THEN` and a continued condition line `B01.Y = 'U' !` are
        # comparisons, `DO I = 1 TO N` is a loop header, and `DCL X INIT(0)` declares.
        # `A, B = 0;` assigns two targets in one statement and counts once.
        "state_mutation": re.compile(
            _STMT_START
            + r"(?<![\w@#$%])"
            + _ID
            + r"{1,64}(?:[ \t]*->[ \t]*"
            + _ID
            + r"{1,64}|\."
            + _ID
            + r"{1,64}){0,6}"
            r"(?:[ \t]*\((?:[^()\n]|\([^()\n]*\)){0,120}\)(?:\." + _ID + r"{1,64}){0,4})?"
            r"(?:[ \t]*,[ \t]*" + _ID + r"{1,64}(?:\." + _ID + r"{1,64}){0,4}){0,8}"
            r"[ \t]*(?:\|\||[-+*/|&])?=(?!=)",
            re.I,
        ),
        # dead_code: a comment whose text is a PL/I statement -- a CALL, an IF ... THEN, a
        # loop opener, a DECLARE, an embedded EXEC, or an %INCLUDE. Wired to both comment
        # styles the family supports (Rule 12).
        "dead_code": re.compile(
            r"(?://|/\*)[ \t]*(?:CALL[ \t]+" + _ID + r"{1,64}[ \t]*[(;]"
            r"|IF\b[^\n*]{0,80}\bTHEN\b|DO[ \t]+(?:WHILE|UNTIL)\b|(?:DCL|DECLARE)[ \t]+[\w@#$(]"
            r"|EXEC[ \t]+(?:CICS|SQL)\b|%[ \t]*INCLUDE[ \t]+[\w@#$('\"])",
            re.I,
        ),
        # doc: PL/I has no generator-read comment syntax of its own. Two conventions are in
        # use: a `/**` doc-comment block (Z Open Editor renders it as hover text) and a
        # structured header block tagged PURPOSE: / DESCRIPTION: / ABSTRACT: / REMARKS:
        # (cobol's REMARKS paragraph). The `/**` form must stay open past its own line: a
        # one-line `/** ... **/` is an emphasised comment (navikt/DSF writes 579 of them as
        # section banners) and a `/*****` row is a box border.
        "doc": re.compile(
            r"/\*\*(?![*/])(?![^\n]*\*/)|^[ \t]*/\*[ \t]*(?:PURPOSE|DESCRIPTION|ABSTRACT|REMARKS)[ \t]*:",
            re.I | re.M,
        ),
        # test (#2852): IBM zUnit and Test4z are the frameworks that execute PL/I test
        # cases; both are unambiguous framework names and fire bare (the contract's
        # "the framework named as such"). No per-case keyword of PL/I's own exists.
        "test": re.compile(_L + r"(?:ZUNIT|TEST4Z)" + _R, re.I),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # concurrency: PL/I's own multitasking (ATTACH a thread, DETACH it, WAIT on an
        # EVENT) plus cobol's CICS task-coordination vocabulary verbatim (#2990).
        "concurrency": re.compile(
            _L
            + r"(?:ATTACH|DETACH)"
            + _R
            + r"|"
            + _L
            + r"WAIT[ \t]*\("
            + r"|\bEXEC\s+CICS\s+(?:ENQ|DEQ|WAIT|WAITCICS|START|RETRIEVE|CANCEL|POST|DELAY|SUSPEND"
            r"|RUN\s+(?:TRANSID|ACTIVITY|ACQPROCESS)|FETCH\s+(?:CHILD|ANY)|FREE\s+CHILD)\b",
            re.I,
        ),
        # ui_framework: the CICS terminal surface (BMS maps and 3270 control), cobol's
        # vocabulary verbatim (#2990).
        "ui_framework": re.compile(
            r"\bEXEC\s+CICS\s+(?:SEND|CONVERSE|ROUTE|PURGE\s+MESSAGE|ISSUE\s+ERASEAUP)\b"
            r"|\b(?:DFHMDF|DFHMDI|DFHMSD)\b",
            re.I,
        ),
        # closures: PL/I has no anonymous procedure; every procedure carries a label.
        "closures": None,
        # globals (#2858): a declaration with program lifetime -- STATIC storage (a STATIC
        # local lives as long as the program, the contract's "program-lifetime local") and
        # EXTERNAL storage shared across compilation units. `STATIC EXTERNAL` is one
        # binding and one hit (the alternation consumes both words). An EXTERNAL ENTRY is
        # linkage, not state (the contract's `extern "C"` / fortran EXTERNAL exclusion):
        # `ENTRY EXTERNAL`, `EXTERNAL ENTRY` (navikt/DSF: `DCL PLITDLI EXTERNAL ENTRY;`) and
        # `EXTERNAL('NAME')` are excluded.
        "globals": re.compile(
            r"(?<!ENTRY\s)"
            + _L
            + r"(?:STATIC(?:[ \t]+EXT(?:ERNAL)?)?|EXT(?:ERNAL)?(?:[ \t]+STATIC)?)"
            + _R
            + r"(?![ \t]*\()(?![ \t]+ENTRY"
            + _R
            + r")",
            re.I,
        ),
        # decorators: the `*PROCESS` / `%PROCESS` compiler-option directive (a pragma line)
        # and the OPTIONS(...) attribute list a PROCEDURE or ENTRY carries.
        "decorators": re.compile(
            r"^[ \t]*[*%][ \t]*PROCESS\b|" + _L + r"OPTIONS[ \t]*\(",
            re.I | re.M,
        ),
        # generics: no parametric types. (The GENERIC attribute selects among entry
        # constants by argument attributes -- overload resolution, not a type parameter.)
        "generics": None,
        # comprehensions: no collection-transform form; array expressions are whole-array
        # arithmetic, not an iteration construct.
        "comprehensions": None,
        # scientific: the mathematical built-in functions, in call form. The everyday
        # names (ABS, MOD, MAX, MIN, SUM, ROUND) are left out: PL/I subscripts arrays with
        # parentheses too, so `SUM(I)` is as often an array element as a call.
        "scientific": re.compile(
            _L + r"(?:SQRT|SIN|COS|TAN|SIND|COSD|TAND|ASIN|ACOS|ATAN|ATAND|ATANH|SINH|COSH|TANH"
            r"|LOG|LOG2|LOG10|EXP|ERF|ERFC|GAMMA|LOGGAMMA|POLY|PROD|RANDOM)[ \t]*\(",
            re.I,
        ),
        # reflection_metaprogramming: storage overlay -- the DEFINED attribute aliases one
        # variable onto another's storage (cobol's REDEFINES) -- plus cobol's EXEC blanket
        # verbatim (#2990: the EXEC CICS/SQL/DLI surface the per-verb rules do not own).
        "reflection_metaprogramming": re.compile(
            _L + r"DEFINED" + _R + r"|\bEXEC\s+(?:CICS|SQL|DLI)\b",
            re.I,
        ),
        # import (#2875): %INCLUDE (and %XINCLUDE, include-once) in every member form --
        # `%INCLUDE name;`, `%INCLUDE ddname(member);`, `%INCLUDE 'file';` -- and the
        # precompiler's `EXEC SQL INCLUDE`. One statement is one hit.
        "import": re.compile(
            r"%[ \t]*X?INCLUDE" + _R + r"|\bEXEC[ \t\r\n]+SQL[ \t\r\n]+INCLUDE\b",
            re.I,
        ),
        # _dependency_capture: the included member. `ddname(member)` and `(member)` bind
        # the member, not the DD name; a quoted path binds the path; `SQLCA`/`SQLDA` from
        # `EXEC SQL INCLUDE` bind the precompiler's own structures and resolve to nothing,
        # like any unresolvable import. Group order is irrelevant: galaxyscope reads the
        # first non-empty group.
        "_dependency_capture": re.compile(
            r"(?:%[ \t]*X?INCLUDE|\bEXEC[ \t\r\n]+SQL[ \t\r\n]+INCLUDE)[ \t]+"
            r"(?:" + _ID + r"{1,8}[ \t]*\([ \t]*(" + _ID + r"{1,64})[ \t]*\)"
            r"|\([ \t]*(" + _ID + r"{1,64})[ \t]*\)"
            r"|['\"]([^'\"\n]{1,200})['\"]"
            r"|(" + _ID + r"{1,64}))",
            re.I,
        ),
        # ownership (#2882): an author/maintainer tag inside a /* */ or // comment -- the
        # C family's rule, since PL/I shares its comment syntax.
        "ownership": re.compile(
            r"@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/)?[ \t]*$"
            r"|^[ \t]*(?:/\*+|\*+|//+)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)"
            r"[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # hardcoded_secrets: a baseline rule in three languages only; the security lens's
        # own detector covers PL/I.
        "hardcoded_secrets": None,
        "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*[0-9]{1,10}|spec|audit)\]", re.I),
        # ssr_boundaries: the CICS web / document API, cobol's vocabulary verbatim (#2990).
        "ssr_boundaries": re.compile(
            r"\bEXEC\s+CICS\s+(?:WEB\s+[A-Z]+|DOCUMENT\s+[A-Z]+|SOAPFAULT|EXTRACT\s+(?:WEB|TCPIP|CERTIFICATE))\b",
            re.I,
        ),
        # events: CICS event processing's SIGNAL EVENT and an MQ put. The receiving side
        # (MQGET) is listeners' alone -- the declared events row excludes it.
        "events": re.compile(
            r"\bEXEC\s+CICS\s+SIGNAL\s+EVENT\b|\bCALL[ \t]+MQPUT1?[ \t]*\(",
            re.I,
        ),
        "dependency_injection": None,
        # macros: the PL/I preprocessor -- %DECLARE, %IF / %ELSE / %DO / %END, %ACTIVATE /
        # %DEACTIVATE, %REPLACE, %NOTE, %GO TO and a preprocessor procedure (`%name: PROC`).
        # %INCLUDE is import's and %PROCESS decorators'; %SKIP / %PAGE / %PRINT only format
        # the compiler listing and generate nothing.
        "macros": re.compile(
            r"%[ \t]*(?:DCL|DECLARE|IF|ELSE|DO|END|ACTIVATE|ACT|DEACTIVATE|DEACT|REPLACE|NOTE|GO[ \t]*TO)"
            + _R
            + r"|%[ \t]*"
            + _ID
            + r"{1,64}[ \t]*:[ \t]*PROC(?:EDURE)?"
            + _R,
            re.I,
        ),
        # pointers: the POINTER attribute (PTR), a BASED variable's overlay through a
        # locator, the `->` locator qualifier, ADDR( / NULL( / SYSNULL(, the PTRADD family,
        # and CICS ADDRESS (cobol's). HANDLE is left out: CICS spells HANDLE CONDITION /
        # ABEND / AID with the same word.
        "pointers": re.compile(
            _L
            + r"(?:POINTER|PTR|BASED|PTRADD|PTRSUBTRACT|POINTERADD|POINTERSUBTRACT|PTRVALUE|POINTERVALUE)"
            + _R
            + r"|"
            + _L
            + r"(?:ADDR|NULL|SYSNULL)[ \t]*\("
            + r"|->"
            + r"|\bEXEC\s+CICS\s+ADDRESS\b",
            re.I,
        ),
        # memory_alloc: ALLOCATE (ALLOC) a BASED or CONTROLLED variable, and FREE it --
        # #1142's explicit ask, and the same ALLOCATE/FREE pair cobol's rule counts (the
        # declared row's FREE-is-also-cleanup dual). CICS GETMAIN / FREEMAIN are cobol's.
        # FREE is the statement form; CICS `FREE CHILD` discards an async token and the
        # bare CICS FREE releases a terminal, so neither counts.
        "memory_alloc": re.compile(
            _L
            + r"ALLOC(?:ATE)?[ \t]+[\w@#$(]"
            + r"|(?<!CICS\s)"
            + _L
            + r"FREE[ \t]+(?!CHILD"
            + _R
            + r")"
            + _ID
            + r"|\bEXEC\s+CICS\s+(?:GETMAIN|FREEMAIN)(?:64)?\b",
            re.I,
        ),
        # inline_asm: no embedding form. OPTIONS(ASSEMBLER) is the linkage convention of a
        # separately assembled routine, not inline machine code.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # telemetry: cobol's CICS diagnostic emissions verbatim (#2990) plus the Language
        # Environment dump and message services and DSNTIAR, in PL/I's unquoted CALL form.
        "telemetry": re.compile(
            r"\bEXEC\s+CICS\s+(?:WRITEQ\s+TD|WRITE\s+JOURNALNAME|WRITE\s+OPERATOR|DUMP\s+TRANSACTION|ENTER\s+TRACENUM)\b"
            r"|\bEXEC\s+DLI\s+LOG\b"
            r"|\bCALL[ \t]+(?:PLIDUMP|CEE3DMP|CEEMOUT|CEEDUMP|DSNTIAR)" + _R,
            re.I,
        ),
        # debug_prints: the stream-output statement written to SYSPRINT -- `PUT SKIP
        # LIST(...)`, `PUT EDIT(...)`, `PUT FILE(SYSPRINT) ...` -- and DISPLAY( to the
        # operator console. A PUT naming any other FILE is io's; `PUT STRING(...)` formats
        # memory and is neither.
        "debug_prints": re.compile(
            _L + r"PUT(?=[ \t\r\n]+(?:SKIP|LIST|EDIT|DATA|PAGE|LINE|FILE)" + _R + r")"
            r"(?![^;]{0,300}?(?:\bFILE[ \t]*\((?![ \t]*SYSPRINT[ \t]*\))|\bSTRING[ \t]*\())"
            + r"|"
            + _L
            + r"DISPLAY[ \t]*\(",
            re.I,
        ),
        # explicit_casts: the conversion built-ins (UNSPEC reinterprets a value's bits;
        # HEX / HEXIMAGE / BINVALUE / CHARVAL / UCHAR / WCHAR / UTF8 convert encodings),
        # and the type-named built-ins FIXED( / FLOAT( / DECIMAL( / BINARY( / CHAR( / BIT(
        # in EXPRESSION position -- right after an assignment or operator. The same words
        # are declaration attributes (`DCL X CHAR(8)`), which follow a space, not an
        # operator, and never match.
        "explicit_casts": re.compile(
            _L + r"(?:UNSPEC|HEX|HEXIMAGE|BINVALUE|CHARVAL|UCHAR|WCHAR|UTF8|UTF8TOCHAR|CHARGRAPHIC|GRAPHICCHAR)[ \t]*\("
            r"|(?<=[=|&+*/])[ \t]*(?:FIXED|FLOAT|DEC(?:IMAL)?|BIN(?:ARY)?|CHAR(?:ACTER)?|BIT)[ \t]*\(",
            re.I,
        ),
        # panics_and_aborts: SIGNAL / RESIGNAL raise a condition (PL/I's throw), STOP and
        # EXIT end execution (the deliberate high_risk_execution dual, #2878), and cobol's
        # EXEC CICS ABEND and the LE abend service CEE3ABD. CICS `SIGNAL EVENT` is events'.
        "panics_and_aborts": re.compile(
            _L
            + r"SIGNAL(?![ \t]+EVENT\b)[ \t]+"
            + _ID
            + r"|"
            + _L
            + r"RESIGNAL"
            + _R
            + r"|"
            + _NOT_A_TARGET
            + _L
            + r"(?:STOP|EXIT)[ \t]*;"
            + r"|\bEXEC\s+CICS\s+ABEND\b|\bCALL[ \t]+CEE3ABD"
            + _R,
            re.I,
        ),
        # thread_sleeps: the DELAY(milliseconds) statement and cobol's CICS DELAY / SUSPEND.
        "thread_sleeps": re.compile(_L + r"DELAY[ \t]*\(|\bEXEC\s+CICS\s+(?:DELAY|SUSPEND)\b", re.I),
        # bitwise_ops: the integer bit built-ins. `&` / `|` / `^` are PL/I's logical
        # operators on BIT(1) values (and `||` is concatenation), so the operator forms
        # say nothing about bit manipulation.
        "bitwise_ops": re.compile(
            _L + r"(?:IAND|IOR|IEOR|INOT|ISLL|ISRL|ISRA|RAISE2|BOOL)[ \t]*\(",
            re.I,
        ),
        # sync_locks: cobol's CICS ENQ.
        "sync_locks": re.compile(r"\bEXEC\s+CICS\s+ENQ\b", re.I),
        # immutability_locks (#2772): the VALUE attribute declares a named constant -- the
        # contract's "restricted constant-declaration form distinct from the general-
        # purpose binding" (INIT is the mutable initial value) -- and NONASSIGNABLE
        # (NONASGN) forbids assignment to a variable or parameter.
        "immutability_locks": re.compile(
            _L + r"VALUE[ \t]*\(|" + _L + r"(?:NONASSIGNABLE|NONASGN)" + _R,
            re.I,
        ),
        # cleanup (#2888): CLOSE FILE(...), DELETE FILE(...) (removes a record -- cobol's
        # DELETE, also io), FREE of an allocated variable (also memory_alloc's, above),
        # SQL CLOSE of a cursor, and cobol's CICS ENDBR / SPOOLCLOSE / DELETE / FREE CHILD
        # (discarding an async child's token is a release of state, #2990).
        "cleanup": re.compile(
            _L
            + r"(?:CLOSE|DELETE)[ \t\r\n]+FILE[ \t]*\("
            + r"|(?<!CICS\s)"
            + _L
            + r"FREE[ \t]+(?!CHILD"
            + _R
            + r")"
            + _ID
            + r"|\bEXEC\s+SQL\s+CLOSE\b"
            r"|\bEXEC\s+CICS\s+(?:ENDBR|SPOOLCLOSE|DELETE|FREE\s+CHILD)\b",
            re.I,
        ),
        # encapsulation (#2766): the INTERNAL attribute keeps a name inside its block. It is
        # the default for most names, which the contract still counts when written.
        # A quoted 'INTERNAL' is a data value (Zowe CHART.pli: `CALL GET_ENTRY ('INTERNAL')`).
        "encapsulation": re.compile(r"(?<!['\"])" + _L + r"INTERNAL" + _R + r"(?!['\"])", re.I),
        # listeners: the receiving side -- an MQ get and cobol's CICS RECEIVE / CONVERSE /
        # HANDLE AID.
        "listeners": re.compile(
            r"\bCALL[ \t]+MQGET[ \t]*\(|\bEXEC\s+CICS\s+(?:RECEIVE|CONVERSE|HANDLE\s+AID)\b",
            re.I,
        ),
        # test_skip: no framework form marks a PL/I test skipped.
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        # auth_middleware (#3004): cobol's CICS/SQL auth surface verbatim -- SIGNON/SIGNOFF,
        # VERIFY/CHANGE PASSWORD|PHRASE, QUERY SECURITY, and embedded EXEC SQL GRANT/REVOKE
        # (the DCL privilege boundary; one owner across languages). EXEC-anchored so a bare
        # word in a label, comment or string never counts (cobol's carddemo lesson).
        "auth_middleware": re.compile(
            r"\bEXEC\s+CICS\s+(?:SIGNON|SIGNOFF|(?:VERIFY|CHANGE)\s+(?:PASSWORD|PHRASE)|QUERY\s+SECURITY)\b"
            r"|\bEXEC\s+SQL\s+(?:GRANT|REVOKE)\b",
            re.I,
        ),
        # serialization_parsing: Enterprise PL/I's JSON built-ins (JSONPUTVALUE,
        # JSONGETMEMBER, JSONVALID ...), its XML generation (XMLCHAR) and SAX parsers
        # (PLISAXA-D), and cobol's CICS TRANSFORM.
        "serialization_parsing": re.compile(
            _L + r"(?:JSON[A-Z]{3,24}|XMLCHAR|XMLCLEAN|PLISAX[A-D])[ \t]*\(|\bEXEC\s+CICS\s+TRANSFORM\b",
            re.I,
        ),
        # regex_execution: no regular-expression facility. INDEX / VERIFY / SEARCH / TALLY
        # are plain substring searches (the declared row's exclusion).
        "regex_execution": None,
        # time_date_logic: the date/time built-ins in call form, cobol's CICS ASKTIME /
        # FORMATTIME / CONVERTTIME, and the LE date services.
        "time_date_logic": re.compile(
            _L + r"(?:DATETIME|DATE|TIME|DAYS|DAYSTODATE|DAYSTOSECS|SECS|SECSTODATE|SECSTODAYS|VALIDDATE"
            r"|WEEKDAY|Y4DATE|Y4JULIAN|Y4YEAR|REPATTERN|TIMESTAMP)[ \t]*\("
            r"|\bEXEC\s+CICS\s+(?:ASKTIME|FORMATTIME|CONVERTTIME)\b"
            r"|\bCALL[ \t]+CEE(?:GMT|DATM|DATE|LOCT|SECS|DAYS|UTC)" + _R,
            re.I,
        ),
        # ipc_rpc_bridges: cobol's CICS program-control and channel vocabulary verbatim
        # (LINK / XCTL / START / RETURN / RUN TRANSID / INVOKE, PUT / GET / MOVE CONTAINER),
        # the embedded SQL / DLI bridge, and the IMS call interfaces. Unlike cobol, a plain
        # CALL does not count: a PL/I CALL invokes a procedure -- usually an internal one in
        # the same program -- and crosses no process boundary.
        "ipc_rpc_bridges": re.compile(
            r"\bEXEC\s+CICS\s+(?:LINK|XCTL|START|RETURN|RUN\s+TRANSID|INVOKE\s+(?:APPLICATION|SERVICE|WEBSERVICE))\b"
            r"|\bEXEC\s+CICS\s+(?:PUT|GET|MOVE)\s+CONTAINER\b"
            r"|\bEXEC\s+(?:SQL|DLI)\b"
            r"|\bCALL[ \t]+(?:PLITDLI|AIBTDLI|CEETDLI)" + _R,
            re.I,
        ),
    },
}
