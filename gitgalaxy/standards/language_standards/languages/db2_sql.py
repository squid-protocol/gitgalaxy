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

from .._shared_patterns import CALLS_OUT_CALL_VERB, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# Db2 ordinary identifiers allow the national characters `#`, `$` and `@` alongside
# letters, digits and `_` (IBM Db2 13 for z/OS SQL Reference, "Identifiers") -- the
# same charset as PL/I, its mainframe host. `\w` is Unicode-aware on a str pattern.
# Delimited identifiers use double quotes ONLY (no backticks or brackets -- those are
# MySQL's and SQL Server's); the quote characters stay INSIDE the capture group,
# sqlite's epic #813/#836 convention, and detector.py strips the matched pair.
_ID = r"[\w#$@]"
_NAME = r"(?:\"[^\"\n]{1,128}\"|" + _ID + r"{1,128})"
# A (possibly remote) object name may be qualified up to three parts:
# location.schema.object. Each qualifier consumes its own trailing dot, so the
# repetition is unambiguous (never two ways to split the same text).
_QUAL = r"(?:" + _NAME + r"[ \t]*\.[ \t]*){0,2}"
# SQL PL's block closers re-state their opener's keyword (`END IF`, `END CASE`,
# `END WHILE`, `END REPEAT`) -- continuation/closing words are excluded from branch
# (#2822 C2). One fixed-width lookbehind per spacing character.
_NOT_END = r"(?<!END )(?<!END\t)"


DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "IBM Db2 13 for z/OS SQL / SQL PL (also Db2 12 FL 510 and LUW 11.5)",
        "last_updated": "2026-09-16",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: the same three extensions sqlite claims, on purpose
    # (#2511) -- enterprise DB2 schemas and SQL PL stored procedures ship as .sql/.ddl/
    # .dml too. All three are therefore contested and listed in _lens_config.py's
    # COLLISION_FREQUENCIES, so Tier 1 never locks them on extension alone and the
    # collision resolves through the internal_discriminator (Tier 2), ecosystem
    # gravity (Tier 1.5) or the lexical scan (Tier 3).
    "extensions": [".sql", ".ddl", ".dml"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS: the mainframe sources that live beside DB2 DDL/SQL PL in the
    # same repository -- the COBOL and PL/I programs that embed its SQL, and the JCL
    # and BMS that compile and run them. A .sql file surrounded by these belongs to
    # DB2, not SQLite (#2511's routing requirement).
    "discriminators": [".cbl", ".cob", ".cpy", ".jcl", ".bms", ".pli", ".pl1"],
    # TOXIC SIGNALS: a repository carrying actual SQLite database artifacts is a
    # SQLite ecosystem; collapse the DB2 claim rather than out-gravitating it.
    # (.db is deliberately absent -- too generic to be proof of anything.)
    "disqualifiers": [".sqlite", ".sqlite3", ".db3", ".s3db", ".sl3"],
    # COLLISION RESOLUTION ONLY (the bms/.map shape): tokens no SQLite script can
    # carry -- z/OS physical storage DDL (TABLESPACE/BUFFERPOOL/STOGROUP/CCSID),
    # special registers, WLM, SPUFI/DSNTEP2's `--#SET` directive line (visible here
    # because this regex runs on RAW content, before prism strips comments), the
    # SQL PL condition-handler declaration, and dynamic SQL's EXECUTE IMMEDIATE.
    # LANGUAGE SQL / SYSIBM catalog references are shared with other big-iron SQL
    # dialects, but the only other candidate for these extensions is sqlite, which
    # has none of them.
    "internal_discriminator": re.compile(
        r"^[ \t]*--#SET[ \t]+[A-Z]"
        r"|\bCREATE[ \t]+(?:LARGE[ \t]+)?TABLESPACE\b"
        r"|\bBUFFERPOOL\b|\bSTOGROUP\b"
        r"|\bCCSID[ \t]+(?:EBCDIC|ASCII|UNICODE)\b"
        r"|\bSET[ \t]+CURRENT[ \t]+(?:SQLID|DEGREE|PACKAGE[ \t]+PATH)\b"
        r"|\bWLM[ \t]+ENVIRONMENT\b"
        r"|\bSYS(?:IBM|CAT|PROC)[ \t]*\." + _ID + r"|\b(?:CONTINUE|EXIT|UNDO)[ \t]+HANDLER[ \t]+FOR\b"
        r"|\bEXECUTE[ \t]+IMMEDIATE\b"
        r"|\bLANGUAGE[ \t]+SQL\b",
        re.I | re.M,
    ),
    # EXECUTION SIGNATURES: DB2 scripts run through SPUFI, DSNTEP2 or the CLP; none
    # is named on a shebang line.
    "shebangs": [],
    # Rationale (how_to_add_a_language.md Step 4 item 8): Db2 SQL uses `--` for
    # line-level and `/*` `*/` for block-level Commented / Non-Executable Text, and
    # blocks do not nest -- the exact family sqlite's #621 fix landed on. Issue #2511
    # says "standard_block", but standard_block is the C-style `//` family and never
    # strips `--` at all (the same defect #621 fixed for sqlite); multi_style_dash is
    # the real family for this comment shape.
    "lexical_family": "multi_style_dash",
    # #2866 contract (corollary 4, sqlite's exact position): the units func_start
    # feeds are Mode E's STATEMENT buckets (`CREATE_Statement` / `Declarative_Block`,
    # #2792), and no SQL syntax reaches a statement by the name the extractor gives
    # it -- a script's statements execute top to bottom on every run. `CALL SP1`
    # invokes the database OBJECT a statement created, not the extracted unit, so a
    # name-recurrence census over these units measures bucket-label collisions, not
    # reachability (proven empirically: the keyword-rosetta shell read a flat 0
    # against a 2.50 by_name median before this declaration). TOP-LEVEL property,
    # not a rule (the #2806 language_lens pre-compiler trap).
    "invocation_model": "positional",
    "rules": {
        # Epic #3264: Explicitly declare the structural invocation paradigm
        "calls_out": CALLS_OUT_CALL_VERB,
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch (#2822): SQL PL's control statements (IF / ELSEIF / ELSE, CASE and
        # its WHEN arms, WHILE, REPEAT ... UNTIL, the cursor FOR-loop) plus SQL's
        # own row-level deciders (WHERE / HAVING, the value fallbacks). THEN and the
        # `END xxx` closers are continuation/closing words (excluded via _NOT_END);
        # LEAVE / ITERATE / GOTO are unconditional transfers (GOTO is
        # safety_bypasses'). The FOR-loop needs its `FOR name AS` shape so `FOR
        # UPDATE` / `FOR EACH ROW` / `FOR READ ONLY` clauses stay out.
        "branch": re.compile(
            _NOT_END + r"\b(?:IF|CASE|WHILE|REPEAT)\b"
            r"|\b(?:ELSEIF|ELSE|WHEN|UNTIL|WHERE|HAVING|COALESCE|NULLIF)\b"
            r"|\bFOR[ \t]+" + _ID + r"{1,128}[ \t]+AS\b",
            re.I,
        ),
        # args (#2773): the declared parameter list of a CREATE PROCEDURE / FUNCTION
        # (anchored to its declaration keyword so a CALL's argument list never
        # counts; type specs like DECIMAL(15,2) nest parens one level -- Rule 11's
        # bounded idiom), plus dynamic SQL's `?` parameter markers and embedded
        # `:host` variables.
        "args": re.compile(
            r"\?|:" + _ID + r"{1,128}"
            r"|\b(?:PROCEDURE|FUNCTION)[ \t\r\n]{1,20}"
            + _QUAL
            + _NAME
            + r"[ \t\r\n]{0,20}\((?:[^()]|\([^()]{0,200}\)){0,2000}\)",
            re.I,
        ),
        # structural_boundaries: the vocabulary tally of query and block structure.
        # A single JOIN token covers every join phrase (LEFT OUTER JOIN carries it).
        # Access modifiers and immutability words are excluded per Rule 6/#2772.
        "structural_boundaries": re.compile(
            r"\b(?:SELECT|FROM|JOIN|GROUP[ \t]+BY|ORDER[ \t]+BY|FETCH[ \t]+FIRST"
            r"|UNION|INTERSECT|EXCEPT|INTO|AS|RETURNS?|DECLARE|BEGIN|END|THEN"
            r"|PARTITION[ \t]+BY)\b",
            re.I,
        ),
        # func_start (#2856, #2511): THE SYNTAX THAT OPENS AN EXECUTABLE BLOCK UNDER
        # ITS OWN NAME -- CREATE [OR REPLACE] PROCEDURE / FUNCTION / TRIGGER, the
        # units that lock business logic inside the database. Vertical formatting
        # gaps allowed (sqlite's VERTICAL MODIFIER SHIELD idiom); schema/location
        # qualifiers skipped; the delimited-identifier quotes stay inside capture
        # group 1 (group 2 stays reserved for class_start's inheritance parent).
        # CREATE TABLE / VIEW / TABLESPACE are class_start's (type declarations).
        "func_start": re.compile(
            r"^[ \t]*CREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?"
            r"(?:PROCEDURE|FUNCTION|TRIGGER)[ \t\n]+" + _QUAL + r"(" + _NAME + r")(?=[ \t(\n;]|$)",
            re.I | re.M,
        ),
        # class_start (#2856, #2511): THE DECLARATION OF A NAMED TYPE OR CONTAINER --
        # CREATE TABLE (including GLOBAL TEMPORARY), CREATE VIEW, and CREATE
        # [LARGE] TABLESPACE (the physical container an enterprise schema cannot
        # exist without). VIEW is a deliberate dual with api (the exposed surface).
        # IF NOT EXISTS is LUW syntax; harmless on z/OS sources.
        "class_start": re.compile(
            r"^[ \t]*CREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?"
            r"(?:(?:GLOBAL[ \t\n]+TEMPORARY[ \t\n]+)?TABLE|VIEW|(?:LARGE[ \t\n]+)?TABLESPACE)[ \t\n]+"
            r"(?:IF[ \t\n]+NOT[ \t\n]+EXISTS[ \t\n]+)?" + _QUAL + r"(" + _NAME + r")(?=[ \t(\n;]|$)",
            re.I | re.M,
        ),
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety (#2869): the SQL PL condition handler (`DECLARE CONTINUE|EXIT|UNDO
        # HANDLER FOR ...` -- DB2's try/catch), transaction guards, BEGIN ATOMIC,
        # and the declared integrity constraints. SIGNAL raises (panics_and_aborts).
        "safety": re.compile(
            r"\b(?:CONTINUE|EXIT|UNDO)[ \t]+HANDLER[ \t]+FOR\b"
            r"|\bCOMMIT\b|\bROLLBACK\b|\bSAVEPOINT\b"
            r"|\bBEGIN[ \t]+ATOMIC\b"
            r"|\bPRIMARY[ \t]+KEY\b|\bFOREIGN[ \t]+KEY\b|\bREFERENCES\b"
            r"|\bCHECK[ \t]*\(|\bWITH[ \t]+CHECK[ \t]+OPTION\b|\bNOT[ \t]+NULL\b",
            re.I,
        ),
        # safety_bypasses: logging switched off (NOT LOGGED [INITIALLY]), integrity
        # checking waved through (SET INTEGRITY ... IMMEDIATE UNCHECKED), structural
        # removals (the sqlite DROP shape), and SQL PL's unstructured GOTO (the
        # pli GO TO precedent).
        "safety_bypasses": re.compile(
            r"\bNOT[ \t]+LOGGED(?:[ \t]+INITIALLY)?\b"
            r"|\bIMMEDIATE[ \t]+UNCHECKED\b"
            r"|\bDROP[ \t]+(?:TABLE|VIEW|INDEX|TRIGGER|PROCEDURE|FUNCTION|ALIAS|SEQUENCE)\b"
            r"|\bGOTO[ \t]+" + _ID,
            re.I,
        ),
        # high_risk_execution (#2878): running text as code (EXECUTE IMMEDIATE,
        # PREPARE ... FROM, EXECUTE of a prepared statement -- guarded so the
        # EXECUTE *privilege* in a GRANT/REVOKE list stays auth_middleware's, #3004), running
        # another program (SYSPROC.ADMIN_CMD / DSNUTILU hand control to utilities),
        # whole-store destruction (DROP DATABASE / TABLESPACE / STOGROUP, TRUNCATE),
        # and the authorization-context switch SET CURRENT SQLID (protection escape;
        # deliberate dual with globals' special-register read).
        "high_risk_execution": re.compile(
            r"\bEXECUTE[ \t]+IMMEDIATE\b"
            r"|\bPREPARE[ \t]+" + _ID + r"{1,128}[ \t]+FROM\b"
            r"|(?<!GRANT )(?<!REVOKE )\bEXECUTE[ \t]+" + _ID + r"{1,128}[ \t]*(?:;|USING\b)"
            r"|\bCALL[ \t]+SYSPROC[ \t]*\.[ \t]*(?:ADMIN_CMD|DSNUTILU|DSNUTILV|ADMIN_TASK_ADD)[ \t]*\("
            r"|\bDROP[ \t]+(?:DATABASE|TABLESPACE|STOGROUP)\b"
            r"|\bTRUNCATE[ \t]+(?:TABLE[ \t]+)?" + _NAME + r"|\bSET[ \t]+CURRENT[ \t]+SQLID\b",
            re.I,
        ),
        # io (#2841, #2511): the cursor operations that move rows out of the engine
        # toward the caller -- OPEN and FETCH (FETCH FIRST is a query clause,
        # structural_boundaries') -- and the CLP's file-crossing utilities. CLOSE is
        # cleanup's (#2841 C2 -- the one deviation from #2511's io list, ledgered
        # there); DML executes inside the store and is computation (#2841 C3).
        "io": re.compile(
            r"\bFETCH\b(?![ \t]+FIRST\b)"
            r"|\bOPEN[ \t]+" + _ID + r"{1,128}[ \t]*(?:;|USING\b|$)"
            r"|\b(?:IMPORT[ \t]+FROM|EXPORT[ \t]+TO|LOAD[ \t]+FROM)\b",
            re.I | re.M,
        ),
        # api (#2730): the declarations that publish a surface -- views, aliases and
        # synonyms exist to be read by others. VIEW is the stated dual with
        # class_start.
        "api": re.compile(
            r"^[ \t]*CREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?"
            r"(?:VIEW|ALIAS|(?:PUBLIC[ \t\n]+)?SYNONYM)\b",
            re.I | re.M,
        ),
        # state_mutation (#2765, #2511): one statement is one hit. INSERT INTO /
        # MERGE INTO / UPDATE are statement-anchored; `UPDATE(?!...SET)` excludes
        # MERGE's clause-internal `WHEN MATCHED THEN UPDATE SET` from re-counting
        # the MERGE. SQL PL's `SET var = expr` counts at a statement start (after
        # `;`, BEGIN, THEN, ELSE or DO) so an UPDATE's own line-wrapped SET clause
        # is not a second hit, and `SET CURRENT ...` special registers are globals'
        # territory. DELETE is cleanup's (#2843/#2888, sqlite parity -- the one
        # deviation from #2511's state_mutation list, ledgered there).
        "state_mutation": re.compile(
            r"^[ \t]*(?:INSERT[ \t\n]+INTO\b"
            r"|UPDATE(?![ \t\n]+SET\b)[ \t\n]+[\w#$@\"]"
            r"|MERGE[ \t\n]+INTO\b)"
            r"|(?:;|\bBEGIN\b|\bTHEN\b|\bELSE\b|\bDO\b)[ \t\r\n]{0,80}"
            r"SET[ \t]+(?!CURRENT\b)[\w#$@\"]{1,130}[ \t]*=",
            re.I | re.M,
        ),
        # dead_code: a comment whose text is a SQL statement, wired to BOTH comment
        # styles the family supports (Rule 12).
        "dead_code": re.compile(
            r"(?:--|/\*)[ \t]*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|CALL|DECLARE|GRANT|COMMIT)\b",
            re.I,
        ),
        # doc: structured header conventions -- `--@param`-style tags, `/**` doc
        # blocks, and `-- Description:` headers (sqlite's set).
        "doc": re.compile(
            r"--[ \t]*@(?:param|return|brief|table|column|version)\b|/\*\*|--[ \t]*Description[ \t]*:",
            re.I,
        ),
        # test (#2852): the diagnostic idioms a DB2 script uses to interrogate its
        # own plans (EXPLAIN and the CURRENT EXPLAIN register) and db2unit, the
        # framework name, which fires bare.
        "test": re.compile(
            r"\bEXPLAIN[ \t]+(?:PLAN|ALL|STMTCACHE)\b|\bSET[ \t]+CURRENT[ \t]+EXPLAIN\b|\bDB2UNIT\b",
            re.I,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # concurrency: the isolation-level clauses (WITH UR/CS/RS/RR), lock-skipping
        # reads, currently-committed semantics, and CURRENT DEGREE (query
        # parallelism).
        "concurrency": re.compile(
            r"\bWITH[ \t]+(?:UR|CS|RS|RR)\b|\bSKIP[ \t]+LOCKED[ \t]+DATA\b"
            r"|\bCURRENTLY[ \t]+COMMITTED\b|\bSET[ \t]+CURRENT[ \t]+DEGREE\b",
            re.I,
        ),
        # ui_framework: SQL builds no user-interface surface.
        "ui_framework": None,
        # closures: no anonymous callable -- every routine is CREATEd under a name
        # (a compound statement is a block, not a value).
        "closures": None,
        # globals (#2858): the ambient environment through its named handles -- the
        # special registers (CURRENT SQLID / SCHEMA / SERVER / MEMBER / PATH /
        # DEGREE / PACKAGE PATH), the USER registers, the SYSIBM / SYSCAT / SYSPROC
        # catalog (sqlite_master's shape) -- and CREATE VARIABLE, a session-global
        # declaration. CURRENT DATE / TIME / TIMESTAMP are time_date_logic's.
        "globals": re.compile(
            r"\bCREATE[ \t]+(?:OR[ \t]+REPLACE[ \t]+)?VARIABLE\b"
            r"|\bSYS(?:IBM|CAT|PROC|IBMADM)[ \t]*\.[ \t]*" + _ID + r"{1,128}"
            r"|\bCURRENT[ \t]+(?:SQLID|SCHEMA|SERVER|MEMBER|PATH|DEGREE|PACKAGE[ \t]+PATH)\b"
            r"|\bSESSION_USER\b|\bSYSTEM_USER\b|\bCURRENT_USER\b",
            re.I,
        ),
        # decorators: optimizer hints attached to the statement they tune --
        # OPTIMIZE FOR n ROWS, the z/OS QUERYNO hint anchor, and LUW's SELECTIVITY.
        "decorators": re.compile(
            r"\bOPTIMIZE[ \t]+FOR[ \t]+[0-9]{1,10}[ \t]+ROWS?\b"
            r"|\bQUERYNO[ \t]+[0-9]{1,10}\b"
            r"|\bSELECTIVITY[ \t]+[0-9][0-9.]{0,10}\b",
            re.I,
        ),
        # generics: no parametric types (Rule 4 -- sqlite's ANY/CAST reading is not
        # a type parameter and is not copied).
        "generics": None,
        # comprehensions: the inline iteration forms -- a window OVER(...) clause
        # (sqlite parity) and UNNEST( over an array. JSON_TABLE / XMLTABLE are
        # serialization_parsing's alone (one owner).
        "comprehensions": re.compile(
            r"\bOVER[ \t]*\((?:[^()]|\([^()]{0,200}\)){0,500}\)|\bUNNEST[ \t]*\(",
            re.I,
        ),
        # scientific: the math built-ins, in call form only (bare ABS/MOD/MAX/MIN
        # are everyday column expressions).
        "scientific": re.compile(
            r"\b(?:SQRT|LN|LOG10|EXP|POWER|SIN|COS|TAN|ASIN|ACOS|ATAN|ATAN2|SINH|COSH|TANH"
            r"|RAND|RADIANS|DEGREES|CEILING|CEIL|FLOOR)[ \t]*\(",
            re.I,
        ),
        # reflection_metaprogramming: the statement-introspection forms -- DESCRIBE
        # of a prepared statement / table / cursor, GET DIAGNOSTICS, and GENERATED
        # ... AS computed columns (sqlite's GENERATED shape).
        "reflection_metaprogramming": re.compile(
            r"\bDESCRIBE[ \t]+(?:INPUT|OUTPUT|PROCEDURE|TABLE|CURSOR)\b"
            r"|\bGET[ \t]+DIAGNOSTICS\b"
            r"|\bGENERATED[ \t]+(?:ALWAYS|BY[ \t]+DEFAULT)[ \t]+AS\b",
            re.I,
        ),
        # import (#2875): CONNECT TO binds an external database into the script's
        # session -- the CLP script's one real dependency form. (`--#SET` directives
        # live in the comment stream, which code rules never see; SPUFI has no
        # include form.)
        "import": re.compile(
            r"^[ \t]*CONNECT[ \t]+TO[ \t]+[\w#$@.\-]{1,128}",
            re.I | re.M,
        ),
        # _dependency_capture: the connected database's name.
        "_dependency_capture": re.compile(
            r"^[ \t]*CONNECT[ \t]+TO[ \t]+([\w#$@.\-]{1,128})",
            re.I | re.M,
        ),
        # ownership (#2882): sqlite's rule verbatim -- the two languages share the
        # exact comment surface (`--` line, `/* */` block).
        "ownership": re.compile(
            r"^[ \t]*(?:--+|/\*+|\*+)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?-i:(?:Author|AUTHOR)(?:s|S)?|Created[ \t]+by|CREATED[ \t]+BY|Maintainer(?:s)?|MAINTAINER(?:S)?|Owner(?:s)?|OWNER(?:S)?|Developer(?:s)?|DEVELOPER(?:S)?|Contact|CONTACT)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)(?<![,;{(])[ \t]*(?:\*/|-->)?[ \t]*$|@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # hardcoded_secrets: a baseline rule in three languages only; the security
        # lens's own detector covers db2_sql.
        "hardcoded_secrets": None,
        "spec_exposure": re.compile(
            r"--[ \t]*\[(?:[ \t]*SPEC[ \t]*-[ \t]*[0-9]{1,10}|spec|audit)[^\]\n]{0,300}\]",
            re.I,
        ),
        # ssr_boundaries: no rendering framework.
        "ssr_boundaries": None,
        # events: trigger wiring -- the publishing construct and its timing clauses
        # (sqlite parity; CREATE TRIGGER is the stated dual with func_start).
        "events": re.compile(
            r"\bCREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?TRIGGER\b"
            r"|\b(?:AFTER|BEFORE)[ \t]+(?:INSERT|UPDATE|DELETE)\b"
            r"|\bINSTEAD[ \t]+OF\b",
            re.I,
        ),
        # dependency_injection: no IoC convention. EXTERNAL NAME binds an
        # implementation and WLM ENVIRONMENT names a runtime target -- neither is a
        # provider registration.
        "dependency_injection": None,
        # macros: no preprocessor the engine can see -- SPUFI/DSNTEP2's `--#SET
        # TERMINATOR` directive is real but lives on a `--` comment line, and the
        # code stream a rules regex runs over has comments stripped (Rule 18). The
        # directive still anchors the internal_discriminator above, which runs on
        # raw content.
        "macros": None,
        # pointers: no address syntax (LOB locators are handles, not addresses).
        "pointers": None,
        # memory_alloc (#2511's z-dimension): the physical storage allocations an
        # enterprise schema declares -- PRIQTY/SECQTY/PCTFREE/FREEPAGE space
        # numbers, the BUFFERPOOL and STOGROUP assignments -- and ALLOCATE CURSOR
        # for a returned result set.
        "memory_alloc": re.compile(
            r"\b(?:PRIQTY|SECQTY|PCTFREE|FREEPAGE)[ \t]+[0-9]{1,10}\b"
            r"|\bBUFFERPOOL[ \t]+" + _ID + r"{1,18}"
            r"|\bSTOGROUP[ \t]+" + _ID + r"{1,128}"
            r"|\bALLOCATE[ \t]+" + _ID + r"{1,128}[ \t]+CURSOR\b",
            re.I,
        ),
        # inline_asm: no embedding form.
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # telemetry: statistics and monitoring -- RUNSTATS, the LUW monitor table
        # functions, and event monitors.
        "telemetry": re.compile(
            r"\bRUNSTATS\b|\bMON_GET_" + _ID + r"{1,64}"
            r"|\bSNAP_GET_" + _ID + r"{1,64}"
            r"|\bCREATE[ \t]+EVENT[ \t]+MONITOR\b",
            re.I,
        ),
        # debug_prints: DBMS_OUTPUT.PUT_LINE (the compatibility module's ad-hoc
        # print) and the CLP's ECHO line.
        "debug_prints": re.compile(
            r"\bDBMS_OUTPUT[ \t]*\.[ \t]*PUT(?:_LINE)?[ \t]*\(|^[ \t]*ECHO[ \t]+",
            re.I | re.M,
        ),
        # explicit_casts: CAST(expr AS type) plus XMLCAST. NOT sqlite's
        # `(?:[^()]{0,500}|\(...\)){0,500}` idiom -- that is Rule 14's
        # adjacent-overlapping-quantifier shape (a `[^()]` run can be split
        # between iterations exponentially many ways), and this suite's
        # detonation payload `CAST( + 'A'*200000` confirmed it hangs. The
        # linear form below alternates one flat run with bounded paren
        # groups, so no two quantifiers ever compete for the same text.
        "explicit_casts": re.compile(
            r"\bCAST[ \t]*\([^()]{0,500}(?:\([^()]{0,300}\)[^()]{0,300}){0,10}"
            r"[ \t]+AS[ \t]+[a-zA-Z_]\w{0,30}"
            r"|\bXMLCAST[ \t]*\(",
            re.I,
        ),
        # panics_and_aborts: SIGNAL SQLSTATE / RESIGNAL raise a condition (SQL PL's
        # throw) and RAISE_ERROR( does the same in expression form.
        "panics_and_aborts": re.compile(
            r"\bSIGNAL[ \t]+SQLSTATE\b|\bRESIGNAL\b|\bRAISE_ERROR[ \t]*\(",
            re.I,
        ),
        # thread_sleeps: the compatibility module's blocking wait.
        "thread_sleeps": re.compile(r"\bDBMS_LOCK[ \t]*\.[ \t]*SLEEP[ \t]*\(", re.I),
        # bitwise_ops: the BITAND family, in call form -- Db2 SQL has no bitwise
        # operators (`&`/`|` are not SQL operators here).
        "bitwise_ops": re.compile(r"\bBIT(?:AND|ANDNOT|OR|XOR|NOT)[ \t]*\(", re.I),
        # sync_locks: explicit lock coordination -- LOCK TABLE, its SHARE/EXCLUSIVE
        # modes, FOR UPDATE row-lock intent, and WITH HOLD cursors surviving COMMIT.
        "sync_locks": re.compile(
            r"\bLOCK[ \t]+TABLE\b|\bIN[ \t]+(?:SHARE|EXCLUSIVE)[ \t]+MODE\b"
            r"|\bFOR[ \t]+UPDATE\b|\bWITH[ \t]+HOLD\b",
            re.I,
        ),
        # immutability_locks (#2772): the read-only cursor clauses -- FOR READ ONLY
        # / FOR FETCH ONLY pin a result set against positioned writes.
        "immutability_locks": re.compile(r"\bFOR[ \t]+(?:READ|FETCH)[ \t]+ONLY\b", re.I),
        # cleanup (#2888): CLOSE of a cursor (#2841 C2), DELETE FROM (removal of
        # entries from a live store, #2843 -- sqlite parity), FREE LOCATOR, and the
        # DROP family (the stated safety_bypasses dual, sqlite's shape). DROP
        # DATABASE / TABLESPACE / STOGROUP are whole-store destruction
        # (high_risk_execution's).
        "cleanup": re.compile(
            r"\bCLOSE[ \t]+" + _ID + r"{1,128}"
            r"|\bDELETE[ \t]+FROM\b|\bFREE[ \t]+LOCATOR\b"
            r"|\bDROP[ \t]+(?:TABLE|VIEW|INDEX|TRIGGER|PROCEDURE|FUNCTION|SEQUENCE|ALIAS|VARIABLE)\b",
            re.I,
        ),
        # encapsulation (#2766, #2511): DECLARE GLOBAL TEMPORARY TABLE, a
        # session-private (non-public) store. GRANT / REVOKE lived here until #3004
        # re-homed the whole privilege surface to auth_middleware (one owner across
        # languages -- cobol/pli's embedded EXEC SQL GRANT joined the same key);
        # SQL's only other visibility construct is the temporary table, so this
        # cell now reads honestly thin.
        "encapsulation": re.compile(
            r"\bDECLARE[ \t]+GLOBAL[ \t]+TEMPORARY[ \t]+TABLE\b",
            re.I,
        ),
        # listeners: the receiving-side wiring of a trigger -- its timing clause
        # bound to the table it watches (sqlite's dual with events, kept).
        "listeners": re.compile(
            r"\b(?:BEFORE|AFTER)[ \t]+(?:INSERT|UPDATE|DELETE)[ \t]+ON\b|\bINSTEAD[ \t]+OF\b",
            re.I,
        ),
        # test_skip: no framework form marks a DB2 test skipped.
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        # auth_middleware (#3004): the GRANT / REVOKE privilege boundary, re-homed
        # from encapsulation (#2766/#2511) so the whole auth/privilege surface reads
        # on one dimension across languages. The statement anchor is kept verbatim:
        # the words only count where they gate access, never license-text "granted"
        # or a comment. SET CURRENT SQLID stays high_risk_execution's (the
        # authorization-context *switch*, not a privilege statement).
        "auth_middleware": re.compile(
            r"^[ \t]*(?:GRANT|REVOKE)[ \t]+[A-Z]",
            re.I | re.M,
        ),
        # serialization_parsing: the JSON and XML publishing/shredding built-ins, in
        # call form. XMLCAST is explicit_casts' alone.
        "serialization_parsing": re.compile(
            r"\b(?:JSON_(?:VALUE|QUERY|TABLE|OBJECT|ARRAY|EXISTS)"
            r"|XML(?:PARSE|SERIALIZE|QUERY|TABLE|ELEMENT|DOCUMENT|AGG))[ \t]*\(",
            re.I,
        ),
        # regex_execution: the REGEXP_ family evaluates real regular expressions;
        # LIKE evaluates a pattern (sqlite parity).
        "regex_execution": re.compile(
            r"\bREGEXP_(?:LIKE|COUNT|INSTR|SUBSTR|REPLACE)[ \t]*\(|\bLIKE\b",
            re.I,
        ),
        # time_date_logic: the special registers and the date/time built-ins in
        # call form. Bare DATE( / TIME( / TIMESTAMP( are left out: `TIMESTAMP(6)`
        # is a column type's precision, not a clock call.
        "time_date_logic": re.compile(
            r"\bCURRENT[ \t]+(?:DATE|TIME(?:STAMP)?)\b|\bCURRENT_(?:DATE|TIME|TIMESTAMP)\b"
            r"|\b(?:TIMESTAMPDIFF|TIMESTAMP_FORMAT|VARCHAR_FORMAT|MONTHS_BETWEEN|TO_DATE|TO_CHAR"
            r"|EXTRACT|DAYS|MIDNIGHT_SECONDS)[ \t]*\(",
            re.I,
        ),
        # ipc_rpc_bridges: federation's bridges to external systems (CREATE SERVER /
        # WRAPPER / NICKNAME) and the compatibility modules' cross-session channels.
        "ipc_rpc_bridges": re.compile(
            r"\bCREATE[ \t]+(?:OR[ \t]+REPLACE[ \t]+)?(?:SERVER|WRAPPER|NICKNAME)\b"
            r"|\bDBMS_(?:ALERT|PIPE)[ \t]*\.[ \t]*" + _ID + r"{1,64}",
            re.I,
        ),
        # system_config_mutation (#3084): contract-level absence. deferred, see
        # 3084: subsystem-tunable DDL (ALTER BUFFERPOOL/STOGROUP) exists but
        # crucible incidence is 0; GRANT/REVOKE is auth_middleware's (#3157).
        "system_config_mutation": None,
    },
}
