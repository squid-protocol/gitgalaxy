# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

from gitgalaxy.standards.language_standards import _lazy_re as re  # #3914: compiled on first use

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT
from . import db2_sql as _db2_sql

# PostgreSQL ordinary identifiers start with a letter or `_` and continue with
# letters, digits, `_` and `$` (PostgreSQL docs, "Identifiers and Key Words"); a
# delimited identifier uses double quotes only. The quote pair stays INSIDE the
# capture group (sqlite/db2_sql convention) and detector.py strips it.
_ID = r"[\w$]"
_NAME = r"(?:\"[^\"\n]{1,128}\"|[^\W\d]" + _ID + r"{0,127})"
# schema.object, optionally catalog.schema.object; each qualifier consumes its own dot.
_QUAL = r"(?:" + _NAME + r"[ \t]*\.[ \t]*){0,2}"
# A dollar-quote delimiter: `$$` or `$tag$` (a tag never starts with a digit).
_DOLLAR = r"\$(?:[^\W\d]\w{0,30})?\$"

# The Db2 profile shares this dialect's comment surface (`--`, `/* */`), debt
# markers and ownership comment; those rules are reused, not re-derived.
_DB2 = _db2_sql.DEFINITION["rules"]

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "PostgreSQL 17 SQL / PL/pgSQL (CedarDB and other PG-wire engines read the same dialect)",
        "last_updated": "2026-10-19",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # The same three extensions sqlite and db2_sql claim (#5622): all three are in
    # _lens_config.py's COLLISION_FREQUENCIES, so none locks at Tier 1 and the
    # collision resolves through internal_discriminator (Tier 2), ecosystem
    # gravity (Tier 1.5) or the lexical scan (Tier 3).
    "extensions": [".sql", ".ddl", ".dml", ".psql", ".pgsql"],
    # Owns the contested SQL extensions only on proof (its internal_discriminator, tried at Tier 2). It is neither
    # a lexical nor a gravity candidate for them: a third claimant dilutes sqlite's neighbourhood dominance below
    # the threshold and a plain script would fall to lexical score (#5622, #4546).
    "extensions_needing_discriminator": [".sql", ".ddl", ".dml"],
    "exact_matches": [],
    "discriminators": [".psql", ".pgsql"],
    # A repository carrying SQLite database artifacts is a SQLite ecosystem.
    "disqualifiers": [".sqlite", ".sqlite3", ".db3", ".s3db", ".sl3"],
    # COLLISION RESOLUTION ONLY: tokens no SQLite or Db2 script carries. Tier 2
    # tries languages in registry order and postgresql is registered BEFORE db2_sql
    # because db2_sql's own `LANGUAGE SQL` alternative also matches a Postgres
    # `LANGUAGE sql` function: a file with real Postgres evidence must not reach it.
    "internal_discriminator": re.compile(
        r"\bAS[ \t\r\n]+"
        + _DOLLAR
        + r"|\bDO[ \t\r\n]+(?:LANGUAGE[ \t]+\w{1,30}[ \t\r\n]+)?"
        + _DOLLAR
        + r"|\bLANGUAGE[ \t]+plpgsql\b"
        r"|\bRETURNS[ \t]+SETOF\b"
        r"|\bCREATE[ \t]+EXTENSION\b|\bCREATE[ \t]+UNLOGGED[ \t]+TABLE\b"
        r"|\bCREATE[ \t]+TYPE[ \t]+" + _QUAL + _NAME + r"[ \t]+AS[ \t]+(?:ENUM|RANGE)\b"
        r"|\bON[ \t]+CONFLICT\b|\bSET[ \t]+search_path\b"
        r"|\b(?:SERIAL|BIGSERIAL|SMALLSERIAL|JSONB|BYTEA|TIMESTAMPTZ)\b"
        r"|\)::[a-z_]|\w::(?:int|integer|bigint|smallint|text|varchar|numeric|boolean|bool|float[48]?|real|double"
        r"|jsonb?|date|timestamp|timestamptz|bytea|regclass|uuid|interval)\b",
        re.I | re.M,
    ),
    "shebangs": [],
    "lexical_family": "multi_style_dash",
    # Mode E units are statement buckets, so the positional contract applies as for db2_sql/sqlite
    # (#2866 corollary 4; the language-addition audit enforces it for every Mode E slicer).
    "invocation_model": "positional",
    # #5736: `CALL name` sites leaving the file reach call_site_data (mainframe_boundary's `sql` dialect, shared with
    # db2_sql). TOP LEVEL, not `rules`: language_lens compiles every string value inside `rules` (#2806).
    "boundary_extraction": "sql",
    "rules": {
        "calls_out": _db2_sql._SQL_CALLS_OUT,
        # branch: PL/pgSQL control (IF / ELSIF / ELSE, CASE and WHEN arms, LOOP
        # exits via EXIT WHEN, WHILE) plus SQL's row-level deciders. THEN and the
        # `END IF` / `END CASE` / `END LOOP` closers are continuation words.
        "branch": re.compile(
            r"(?<!END )(?<!END\t)\b(?:IF|CASE|WHILE)\b"
            r"|\b(?:ELSIF|ELSEIF|ELSE|WHEN|WHERE|HAVING|COALESCE|NULLIF|FILTER)\b"
            r"|\bFOR[ \t]+" + _ID + r"{1,128}[ \t]+IN\b",
            re.I,
        ),
        # args: the declared parameter list of a CREATE FUNCTION / PROCEDURE (one
        # level of nested parens for `numeric(15,2)`), the positional `$1` parameter
        # references a `LANGUAGE sql` body uses, and psql `:var` interpolation.
        "args": re.compile(
            r"\$[0-9]{1,3}\b|(?<!:):" + _ID + r"{1,128}"
            r"|\b(?:PROCEDURE|FUNCTION)[ \t\r\n]{1,20}"
            + _QUAL
            + _NAME
            + r"[ \t\r\n]{0,20}\((?:[^()]|\([^()]{0,200}\)){0,2000}\)",
            re.I,
        ),
        "structural_boundaries": re.compile(
            r"\b(?:SELECT|FROM|JOIN|GROUP[ \t]+BY|ORDER[ \t]+BY|LIMIT|OFFSET|FETCH[ \t]+FIRST"
            r"|UNION|INTERSECT|EXCEPT|INTO|AS|RETURNS?|RETURNING|DECLARE|BEGIN|END|THEN|LANGUAGE"
            r"|PARTITION[ \t]+BY|LATERAL|WINDOW)\b",
            re.I,
        ),
        # func_start: CREATE [OR REPLACE] FUNCTION / PROCEDURE / TRIGGER (also
        # CONSTRAINT TRIGGER), name captured after any schema qualifier. Vertical
        # gaps allowed. The `$$` body that follows is Mode E's to keep whole
        # (detector.py's dollar-quote tracking).
        "func_start": re.compile(
            r"^[ \t]*CREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?(?:CONSTRAINT[ \t\n]+)?"
            r"(?:PROCEDURE|FUNCTION|TRIGGER)[ \t\n]+" + _QUAL + r"(" + _NAME + r")(?=[ \t(\n;]|$)",
            re.I | re.M,
        ),
        # class_start: the named type or container declarations -- tables
        # (UNLOGGED / TEMP / FOREIGN), views (MATERIALIZED / RECURSIVE / TEMP), and
        # CREATE TYPE / DOMAIN (composite, enum, range).
        "class_start": re.compile(
            r"^[ \t]*CREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?"
            r"(?:(?:UNLOGGED[ \t\n]+|GLOBAL[ \t\n]+|LOCAL[ \t\n]+|TEMP(?:ORARY)?[ \t\n]+|FOREIGN[ \t\n]+)?TABLE"
            r"|(?:MATERIALIZED[ \t\n]+|RECURSIVE[ \t\n]+|TEMP(?:ORARY)?[ \t\n]+)?VIEW|TYPE|DOMAIN)[ \t\n]+"
            r"(?:IF[ \t\n]+NOT[ \t\n]+EXISTS[ \t\n]+)?" + _QUAL + r"(" + _NAME + r")(?=[ \t(\n;]|$)",
            re.I | re.M,
        ),
        # safety: the exception block (PL/pgSQL's try/catch), transaction guards and
        # the declared integrity constraints.
        "safety": re.compile(
            r"\bEXCEPTION[ \t\r\n]{1,20}WHEN\b|\bCOMMIT\b|\bROLLBACK\b|\bSAVEPOINT\b"
            r"|\bPRIMARY[ \t]+KEY\b|\bFOREIGN[ \t]+KEY\b|\bREFERENCES\b|\bUNIQUE\b"
            r"|\bCHECK[ \t]*\(|\bWITH[ \t]+CHECK[ \t]+OPTION\b|\bNOT[ \t]+NULL\b",
            re.I,
        ),
        # safety_bypasses: constraints waved through (NOT VALID), logging off
        # (UNLOGGED), triggers and row security switched off, and structural removals.
        "safety_bypasses": re.compile(
            r"\bUNLOGGED\b|\bNOT[ \t]+VALID\b"
            r"|\b(?:DISABLE|NO[ \t]+FORCE)[ \t]+(?:TRIGGER|ROW[ \t]+LEVEL[ \t]+SECURITY)\b"
            r"|\bDROP[ \t]+(?:TABLE|VIEW|MATERIALIZED[ \t]+VIEW|INDEX|TRIGGER|PROCEDURE|FUNCTION|SEQUENCE|TYPE|DOMAIN)\b",
            re.I,
        ),
        # high_risk_execution: dynamic SQL (`EXECUTE format(...)` / `EXECUTE '...'`;
        # `GRANT EXECUTE ON` never matches because ON follows), SECURITY DEFINER
        # (runs with the owner's rights), server-side file and program access, and
        # whole-store destruction.
        "high_risk_execution": re.compile(
            r"\bEXECUTE[ \t\r\n]+(?:format[ \t]*\(|quote_\w{1,20}[ \t]*\(|')"
            r"|\bSECURITY[ \t]+DEFINER\b"
            r"|\bCOPY\b[^;]{0,300}\bPROGRAM\b"
            r"|\b(?:pg_read_file|pg_read_binary_file|lo_import|lo_export|dblink_exec)[ \t]*\("
            r"|\bDROP[ \t]+(?:DATABASE|SCHEMA|TABLESPACE|ROLE|USER|OWNED)\b"
            r"|\bTRUNCATE[ \t]+(?:TABLE[ \t]+)?" + _NAME,
            re.I,
        ),
        # io: cursor movement out of the engine (OPEN / FETCH) and the file-crossing
        # COPY (FROM / TO a file, STDIN or STDOUT) and psql's \copy.
        "io": re.compile(
            r"\bFETCH\b(?![ \t]+FIRST\b)"
            r"|\bOPEN[ \t]+" + _ID + r"{1,128}[ \t]*(?:;|FOR\b|$)"
            r"|\bCOPY\b[^;]{0,300}\b(?:FROM|TO)[ \t]+(?:STDIN|STDOUT|PROGRAM|')"
            r"|^[ \t]*\\copy\b",
            re.I | re.M,
        ),
        # api: the declarations that publish a read surface.
        "api": re.compile(
            r"^[ \t]*CREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?(?:MATERIALIZED[ \t\n]+|RECURSIVE[ \t\n]+)?VIEW\b",
            re.I | re.M,
        ),
        # state_mutation: one statement is one hit -- INSERT INTO / MERGE INTO /
        # UPDATE at a statement start, and PL/pgSQL's `var := expr` assignment.
        "state_mutation": re.compile(
            r"^[ \t]*(?:INSERT[ \t\n]+INTO\b|UPDATE(?![ \t\n]+SET\b)[ \t\n]+[\w\"]|MERGE[ \t\n]+INTO\b)"
            r"|\b[\w.]{1,128}(?:\[[^\]\n]{0,60}\])?[ \t]*:=",
            re.I | re.M,
        ),
        "dead_code": _DB2["dead_code"],
        "doc": _DB2["doc"],
        # test: pgTAP's plan/assertion functions and the EXPLAIN options a script
        # uses to interrogate its own plans.
        "test": re.compile(
            r"\bEXPLAIN[ \t]*(?:\([ \t]*ANALYZE|ANALYZE|VERBOSE)\b"
            r"|\b(?:lives_ok|throws_ok|results_eq|results_ne|set_eq|bag_eq|is_empty|has_table|has_function"
            r"|runtests)[ \t]*\(|\bSELECT[ \t]+(?:plan|finish|no_plan)[ \t]*\(",
            re.I,
        ),
        # concurrency: isolation levels and lock-skipping reads.
        "concurrency": re.compile(
            r"\bISOLATION[ \t]+LEVEL\b|\bSKIP[ \t]+LOCKED\b|\bNOWAIT\b|\bSET[ \t]+TRANSACTION\b",
            re.I,
        ),
        "ui_framework": None,
        # closures: the DO block -- an anonymous, unnamed code block run once.
        "closures": re.compile(
            r"\bDO[ \t\r\n]+(?:LANGUAGE[ \t]+\w{1,30}[ \t\r\n]+)?" + _DOLLAR,
            re.I,
        ),
        # globals: session and catalog handles. set_config() is
        # system_config_mutation's alone.
        "globals": re.compile(
            r"\bcurrent_setting[ \t]*\("
            r"|\b(?:pg_catalog|information_schema)[ \t]*\.[ \t]*" + _ID + r"{1,128}"
            r"|\bSET[ \t]+search_path\b"
            r"|\bCURRENT_(?:USER|SCHEMA|DATABASE|CATALOG|ROLE)\b|\bSESSION_USER\b",
            re.I,
        ),
        # decorators: the volatility / strictness / cost attributes attached to a
        # function declaration.
        "decorators": re.compile(
            r"\b(?:IMMUTABLE|STABLE|VOLATILE|LEAKPROOF|PARALLEL[ \t]+(?:SAFE|UNSAFE|RESTRICTED)"
            r"|COST[ \t]+[0-9]{1,10}|RETURNS[ \t]+NULL[ \t]+ON[ \t]+NULL[ \t]+INPUT)\b",
            re.I,
        ),
        # generics: the polymorphic pseudo-types a function is declared over.
        "generics": re.compile(
            r"\bany(?:element|array|nonarray|enum|range|multirange|compatible\w{0,20})\b",
            re.I,
        ),
        # comprehensions: window OVER(...), UNNEST and generate_series row sources.
        "comprehensions": re.compile(
            r"\bOVER[ \t]*\((?:[^()]|\([^()]{0,200}\)){0,500}\)|\b(?:UNNEST|generate_series)[ \t]*\(",
            re.I,
        ),
        "scientific": re.compile(
            r"\b(?:sqrt|cbrt|ln|log|log10|exp|power|sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh"
            r"|random|setseed|radians|degrees|ceil|ceiling|floor|pi)[ \t]*\(",
            re.I,
        ),
        # reflection_metaprogramming: trigger context variables (TG_OP ...), the
        # %TYPE / %ROWTYPE copies, GET DIAGNOSTICS and generated columns.
        "reflection_metaprogramming": re.compile(
            r"\bTG_(?:OP|TABLE_NAME|TABLE_SCHEMA|NAME|WHEN|LEVEL|ARGV|NARGS|RELNAME)\b"
            r"|%(?:ROW)?TYPE\b|\bGET[ \t]+(?:CURRENT[ \t]+|STACKED[ \t]+)?DIAGNOSTICS\b"
            r"|\bGENERATED[ \t]+(?:ALWAYS|BY[ \t]+DEFAULT)[ \t]+AS\b|\bpg_typeof[ \t]*\(",
            re.I,
        ),
        # import: CREATE EXTENSION binds an external module into the database.
        "import": re.compile(
            r"^[ \t]*CREATE[ \t]+EXTENSION[ \t]+(?:IF[ \t]+NOT[ \t]+EXISTS[ \t]+)?[\w\"]{1,128}",
            re.I | re.M,
        ),
        "_dependency_capture": re.compile(
            r"^[ \t]*CREATE[ \t]+EXTENSION[ \t]+(?:IF[ \t]+NOT[ \t]+EXISTS[ \t]+)?([\w\"]{1,128})",
            re.I | re.M,
        ),
        "ownership": _DB2["ownership"],
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "hardcoded_secrets": None,
        "spec_exposure": _DB2["spec_exposure"],
        "ssr_boundaries": None,
        # events: trigger publication and the NOTIFY channel.
        "events": re.compile(
            r"\bCREATE[ \t\n]+(?:OR[ \t\n]+REPLACE[ \t\n]+)?(?:CONSTRAINT[ \t\n]+|EVENT[ \t\n]+)?TRIGGER\b"
            r"|\bNOTIFY[ \t]+\w|\bpg_notify[ \t]*\(",
            re.I,
        ),
        "dependency_injection": None,
        "macros": None,
        "pointers": None,
        # memory_alloc: the physical storage a schema declares.
        "memory_alloc": re.compile(
            r"\bFILLFACTOR[ \t]*=[ \t]*[0-9]{1,3}\b|\bTABLESPACE[ \t]+[\w\"]{1,128}"
            r"|\bCREATE[ \t]+(?:TEMP(?:ORARY)?[ \t]+)?SEQUENCE\b",
            re.I,
        ),
        "inline_asm": None,
        # telemetry: statistics views and ANALYZE.
        "telemetry": re.compile(r"\bpg_stat_[a-z_]{1,64}|^[ \t]*ANALYZE\b", re.I | re.M),
        # debug_prints: RAISE at a non-error level.
        "debug_prints": re.compile(r"\bRAISE[ \t]+(?:DEBUG[1-5]?|LOG|INFO|NOTICE|WARNING)\b", re.I),
        # explicit_casts: `::type` and CAST(expr AS type) (linear form, not the
        # ReDoS-prone adjacent-quantifier idiom -- see db2_sql's explicit_casts).
        "explicit_casts": re.compile(
            r"::[ \t]*[a-zA-Z_]\w{0,30}"
            r"|\bCAST[ \t]*\([^()]{0,500}(?:\([^()]{0,300}\)[^()]{0,300}){0,10}[ \t]+AS[ \t]+[a-zA-Z_]\w{0,30}",
            re.I,
        ),
        # panics_and_aborts: RAISE EXCEPTION, a bare re-raise, and ASSERT.
        "panics_and_aborts": re.compile(
            r"\bRAISE[ \t]+EXCEPTION\b|^[ \t]*RAISE[ \t]*;|^[ \t]*ASSERT\b",
            re.I | re.M,
        ),
        "thread_sleeps": re.compile(r"\bpg_sleep(?:_for|_until)?[ \t]*\(", re.I),
        # bitwise_ops: the bit functions and the infix operators (`&` `|` `#` `<<` `>>`).
        "bitwise_ops": re.compile(
            r"\b(?:bit_and|bit_or|bit_xor|bit_count|get_bit|set_bit)[ \t]*\(|[ \t](?:[&|#]|<<|>>)[ \t]",
            re.I,
        ),
        # sync_locks: explicit lock coordination -- LOCK TABLE, row-lock intent and
        # advisory locks.
        "sync_locks": re.compile(
            r"\bLOCK[ \t]+TABLE\b|\bFOR[ \t]+(?:NO[ \t]+KEY[ \t]+)?(?:UPDATE|SHARE)\b"
            r"|\bpg_(?:try_)?advisory_(?:xact_)?lock(?:_shared)?[ \t]*\(",
            re.I,
        ),
        "immutability_locks": re.compile(r"\bREAD[ \t]+ONLY\b", re.I),
        # cleanup: cursor CLOSE, DELETE FROM, VACUUM / DEALLOCATE / DISCARD and DROP.
        "cleanup": re.compile(
            r"\bCLOSE[ \t]+" + _ID + r"{1,128}|\bDELETE[ \t]+FROM\b|\b(?:VACUUM|DEALLOCATE|DISCARD)\b"
            r"|\bDROP[ \t]+(?:TABLE|VIEW|MATERIALIZED[ \t]+VIEW|INDEX|TRIGGER|PROCEDURE|FUNCTION|SEQUENCE|TYPE|DOMAIN)\b",
            re.I,
        ),
        # encapsulation: session-private temporary relations.
        "encapsulation": re.compile(
            r"\bCREATE[ \t]+(?:GLOBAL[ \t]+|LOCAL[ \t]+)?TEMP(?:ORARY)?[ \t]+(?:TABLE|VIEW)\b", re.I
        ),
        # listeners: the receiving side of a trigger or notification.
        "listeners": re.compile(
            r"\b(?:BEFORE|AFTER)[ \t]+(?:INSERT|UPDATE|DELETE|TRUNCATE)[ \t]+(?:OR[ \t]+\w+[ \t]+)*ON\b"
            r"|\bINSTEAD[ \t]+OF\b|^[ \t]*LISTEN\b",
            re.I | re.M,
        ),
        "test_skip": None,
        # auth_middleware: the privilege boundary -- GRANT / REVOKE and row-level
        # security policy.
        "auth_middleware": re.compile(
            r"^[ \t]*(?:GRANT|REVOKE)[ \t]+[A-Z]|\bCREATE[ \t]+POLICY\b|\bENABLE[ \t]+ROW[ \t]+LEVEL[ \t]+SECURITY\b",
            re.I | re.M,
        ),
        # serialization_parsing: JSON / XML built-ins and the JSON accessor operators.
        "serialization_parsing": re.compile(
            r"\b(?:jsonb?_(?:build_object|build_array|extract_path\w{0,5}|array_elements\w{0,5}|object_keys"
            r"|each\w{0,5}|populate_record\w{0,5}|to_record\w{0,5}|agg|set|path_query\w{0,10}|typeof|strip_nulls)"
            r"|to_jsonb?|row_to_json|array_to_json|xpath|xmlelement|xmlagg|xmlparse|xmlserialize|query_to_xml)"
            r"[ \t]*\(|[ \t](?:->>?|#>>?)[ \t]",
            re.I,
        ),
        # regex_execution: POSIX operators, SIMILAR TO, the regexp_ family and LIKE.
        "regex_execution": re.compile(
            r"[ \t]!?~\*?[ \t]|\bSIMILAR[ \t]+TO\b|\bregexp_(?:match|matches|replace|split_to_table|split_to_array|count"
            r"|instr|like|substr)[ \t]*\(|\bI?LIKE\b",
            re.I,
        ),
        "time_date_logic": re.compile(
            r"\b(?:CURRENT_(?:DATE|TIME|TIMESTAMP)|LOCALTIME(?:STAMP)?|INTERVAL)\b"
            r"|\b(?:now|clock_timestamp|statement_timestamp|transaction_timestamp|timeofday|to_timestamp|to_date"
            r"|to_char|date_trunc|date_part|extract|age|make_date|make_time|make_timestamptz?|make_interval"
            r"|justify_days|justify_hours)[ \t]*\(",
            re.I,
        ),
        # ipc_rpc_bridges: foreign servers, wrappers, subscriptions and dblink.
        "ipc_rpc_bridges": re.compile(
            r"\bCREATE[ \t]+(?:SERVER|FOREIGN[ \t]+(?:DATA[ \t]+WRAPPER|TABLE)|USER[ \t]+MAPPING|SUBSCRIPTION"
            r"|PUBLICATION)\b|\bdblink(?:_[a-z_]{1,32})?[ \t]*\(",
            re.I,
        ),
        # system_config_mutation: ALTER SYSTEM and per-database/role settings, and
        # set_config().
        "system_config_mutation": re.compile(
            r"\bALTER[ \t]+(?:SYSTEM|DATABASE[ \t]+" + _NAME + r"|ROLE[ \t]+" + _NAME + r")[ \t]+(?:SET|RESET)\b"
            r"|\bALTER[ \t]+SYSTEM\b|\bset_config[ \t]*\(",
            re.I,
        ),
    },
}
