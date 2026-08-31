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
        "target_version": "SQLite 3.51.2+ (STRICT Tables, JSONB, RETURNING, Math & CTEs)",
        "last_updated": "2026-02-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard SQL scripts, data definition, and data manipulation files.
    "extensions": [".sql", ".ddl", ".dml"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: Standard SQLite configuration and history files that consist of CLI commands/SQL.
    "exact_matches": [".sqliterc"],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Binary database files acting as gravitational anchors to prove a .sql file is SQLite and not Postgres/MySQL.
    "discriminators": [
        ".sql",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".db3",
        ".s3db",
        ".sl3",
    ],
    # EXECUTION SIGNATURES: Interpreters found on Line 1.
    "shebangs": ["sqlite3", "sqlite"],
    # Maps to Family 5 (Hybrid Dash) -- #621: this comment always said
    # "Family 5 (Hybrid Dash)" but the value below was "standard_block"
    # until now, so sqlite shared a regex with C-style languages and got
    # zero comment stripping (standard_block never used the `--` token).
    # "multi_style_dash" is the real family for this shape.
    # Rationale: Uses '--' for line-level and '/*' '*/' for block-level Commented / Non-Executable Text.
    "lexical_family": "multi_style_dash",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical filters. Includes case logic and modern IIF().
        "branch": re.compile(
            r"\b(CASE|WHEN|THEN|ELSE|END|IFNULL|NULLIF|COALESCE|IIF|FILTER|WHERE|HAVING)\b",
            re.I,
        ),
        # 2. args (Parameters / Coupling)
        # Parameter blocks and input coupling. Bounded to prevent ReDoS on massive IN clauses.
        # Now explicitly captures CTE scoped arguments: cte_name (col1, col2)
        # BUG FIX (epic #813/#836), two findings:
        # 1. Rule 11 shape: the VALUES/IN clause's `\([^)]{0,2000}\)` was a
        #    flat, unnested paren match -- a nested subquery (`IN (SELECT
        #    id FROM (SELECT id FROM other))`, common real SQL) truncated
        #    at the FIRST closing paren (the inner subquery's own),
        #    silently ending the match one paren early instead of
        #    covering the whole clause. Widened to the established
        #    one-level-nesting-safe idiom, bounded on both the inner and
        #    outer repetition to stay ReDoS-safe.
        # 2. The CTE alternative required the CTE name to be at TRUE line
        #    start (`^[ \t]*`) -- but the single most common way to
        #    actually write a CTE is inline, right after the `WITH`
        #    keyword on the same line (`WITH cte_name (col1, col2) AS
        #    (...)`), which this pattern never matched at all. Added an
        #    alternative anchor: immediately after `WITH` or `WITH
        #    RECURSIVE`, in addition to (not instead of) true line start
        #    (multi-CTE statements formatted one-per-line still hit the
        #    original anchor). Kept as a non-capturing addition -- this
        #    rule has zero capture groups by design (every alternative is
        #    checked via whole-match substring, not a captured group), so
        #    adding a real group here would have changed that convention
        #    for every OTHER alternative too.
        "args": re.compile(
            r"\?[0-9]*|[:@$][a-zA-Z_]\w*|\b(?:VALUES|IN)\s*\((?:[^()]|\([^()]{0,2000}\)){0,2000}\)|"
            r"(?:^[ \t]*|\bWITH(?:[ \t\n]+RECURSIVE)?[ \t\n]+)[a-zA-Z_]\w*[ \t\n]*\([^)]{0,2000}\)[ \t\n]*AS[ \t\n]*\(",
            re.I | re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries defining query execution flow.
        "structural_boundaries": re.compile(
            r"\b(SELECT|FROM|JOIN|(?:INNER|LEFT|RIGHT|FULL|CROSS|NATURAL)(?:\s+OUTER)?\s+JOIN|GROUP\s+BY|ORDER\s+BY|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT|RETURNING|AS|INTO|WINDOW|STRICT|WITHOUT\s+ROWID|PARTITION\s+BY|PRECEDING|FOLLOWING|UNBOUNDED|CURRENT\s+ROW)\b",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # Executable logic wrappers. EXCLUDES tables to avoid False Positives.
        "func_start": re.compile(
            # =====================================================================
            # [ THE VERTICAL MODIFIER SHIELD (SQLITE) ]
            # SQL developers frequently format DDL statements across multiple lines,
            # stacking `CREATE`, `TEMPORARY TRIGGER`, and `IF NOT EXISTS` vertically.
            # FIX: Upgraded the `\s+` and `[ \t]+` modifier bounds to `[ \t\n]+`.
            # Critically, the `IF NOT EXISTS` block previously failed to capture
            # the vertical gap, causing the engine to capture `IF` as the target name.
            #
            # BUG FIX (epic #813/#836), two findings:
            # 1. No allowance for a schema-qualified name (`CREATE
            #    TRIGGER main.my_trigger ...`) -- standard, common SQLite
            #    syntax when working with ATTACHed databases or
            #    explicitly targeting `temp.`. Since `\w` never spans a
            #    literal `.`, the old pattern couldn't capture "main.my_
            #    trigger" as one token and had no fallback to skip the
            #    schema prefix and capture just the real name -- the
            #    whole match failed outright. Added an optional
            #    `(?:[a-zA-Z_]\w*\.)?` schema-prefix skip before the
            #    capture.
            # 2. No allowance for any of SQLite's three quoted-identifier
            #    styles (`"name"`, `` `name` ``, `[name]`) -- so even a
            #    plain quoted name with no special characters at all
            #    (`CREATE VIEW "group" AS ...`, quoting a name that
            #    happens to collide with a reserved word -- the single
            #    most common real reason to quote an identifier) failed
            #    outright. Added the three quoted forms as alternatives
            #    inside the SAME capture group (quotes included in the
            #    captured text) rather than as separate numbered groups,
            #    since detector.py reserves capture group 2 specifically
            #    for class_start's inheritance-parent extraction on other
            #    languages -- adding new numbered groups here would have
            #    silently shifted that convention.
            # =====================================================================
            r"^[ \t]*CREATE[ \t\n]+(?:(?:TEMP|TEMPORARY)[ \t\n]+)?(?:UNIQUE[ \t\n]+)?(?:TRIGGER|VIEW|INDEX)[ \t\n]+"
            r"(?:IF[ \t\n]+NOT[ \t\n]+EXISTS[ \t\n]+)?(?:[a-zA-Z_]\w*\.)?"
            r"((?:\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[a-zA-Z_]\w*))(?=[ \t\(\n;]|$)",
            re.I | re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Physical entity instantiation (Tables).
        # BUG FIX (epic #813/#836), three findings:
        # 1/2. Same schema-qualifier and quoted-identifier gaps as
        #    func_start above -- `CREATE TABLE main.users (...)` and
        #    `CREATE TABLE "my table" (...)` were both entirely
        #    invisible. Same fix, same single-group approach.
        # 3. Pre-existing (not introduced by the above): the "IF NOT
        #    EXISTS" clause's own trailing gap used `[ \t]+` -- unlike
        #    its internal `NOT`/`EXISTS` gaps (`\s+`, which already
        #    included newlines), the FINAL gap before the table name
        #    didn't allow a newline. func_start's own "VERTICAL MODIFIER
        #    SHIELD" fix (see its comment above) already covers this
        #    exact shape for TRIGGER/VIEW/INDEX, but was never applied to
        #    class_start's parallel TABLE clause -- so `CREATE TABLE IF
        #    NOT EXISTS\n    users (...)` (a real, common vertical
        #    formatting style) silently captured "IF" as the table name
        #    instead of "users". Widened to `[ \t\n]+`, matching
        #    func_start's existing idiom.
        "class_start": re.compile(
            r"^[ \t]*CREATE\s+(?:(?:TEMP|TEMPORARY)\s+)?(?:VIRTUAL[ \t]+)?TABLE\s+"
            r"(?:IF\s+NOT\s+EXISTS[ \t\n]+)?(?:[a-zA-Z_]\w*\.)?"
            r"((?:\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[a-zA-Z_]\w*))(?=[ \t\(\n;]|$)",
            re.I | re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Programming / Validation)
        "safety": re.compile(
            r"\b(TRANSACTION|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|CONSTRAINT|CHECK|UNIQUE|PRIMARY\s+KEY|FOREIGN\s+KEY|STRICT|IF\s+NOT\s+EXISTS|ON\s+DELETE\s+CASCADE|PRAGMA\s+foreign_keys[ \t]*=\s*(?:1|ON))\b",
            re.I,
        ),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Bypassing safety checks and structural removals.
        "safety_bypasses": re.compile(
            r"\b(DROP\s+TABLE|DROP\s+VIEW|DROP\s+INDEX|PRAGMA\s+foreign_keys[ \t]*=\s*(?:0|OFF)|PRAGMA\s+writable_schema[ \t]*=\s*(?:1|ON)|PRAGMA\s+ignore_check_constraints[ \t]*=\s*(?:1|ON)|IF\s+EXISTS)\b",
            re.I,
        ),
        # 8. danger (High-Risk Execution / System Calls)
        # Destructive schema actions and system bypasses.
        "high_risk_execution": re.compile(
            r"\b(PRAGMA\s+legacy_alter_table|DROP\s+DATABASE)\b|^[ \t]*\.(?:shell|system|exit|quit)\b",
            re.I | re.M,
        ),
        # 9. io (I/O & Network Boundaries)
        "io": re.compile(
            r"\b(SELECT|INSERT|UPDATE|DELETE|REPLACE|ATTACH\s+DATABASE|DETACH\s+DATABASE|readfile|writefile)\b|^[ \t]*\.(?:import|output|dump|read)\b",
            re.I | re.M,
        ),
        # 10. api (Public Surface Area)
        # Exposed surface area (Views and Virtual Tables).
        "api": re.compile(
            r"^[ \t]*CREATE\s+(?:TEMP|TEMPORARY)?\s*(?:VIEW|VIRTUAL\s+TABLE)\s+",
            re.I | re.M,
        ),
        # 11. flux (State Mutation)
        # Mutation of state. Includes UPSERT.
        "state_mutation": re.compile(
            r"\b(UPDATE|SET|ALTER\s+TABLE|ADD\s+COLUMN|DROP\s+COLUMN|RENAME\s+TO|UPSERT|ON\s+CONFLICT\s+DO\s+UPDATE|ON\s+CONFLICT\s+DO\s+NOTHING|REPLACE\s+INTO|EXCLUDED\.[a-zA-Z_]\w*|jsonb?_(?:insert|replace|set|remove|patch))\b",
            re.I,
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        "dead_code": re.compile(
            r"(?:--|/\*)[ \t]*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|PRAGMA)\b",
            re.I,
        ),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"--\s*@(?:param|return|brief|table|column)|/\*\*|--\s*Description:"),
        # 14. test (Testing & Assertions)
        "test": re.compile(
            r"\b(?:EXPLAIN[ \t]+QUERY[ \t]+PLAN|PRAGMA[ \t]+integrity_check|PRAGMA[ \t]+foreign_key_check)\b|^[ \t]*\.(?:testcase|lint)\b",
            re.I | re.M,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(BEGIN\s+EXCLUSIVE|BEGIN\s+IMMEDIATE|PRAGMA\s+journal_mode[ \t]*=\s*WAL|PRAGMA\s+busy_timeout|PRAGMA\s+synchronous|PRAGMA\s+wal_checkpoint)\b",
            re.I,
        ),
        # 16. ui_framework
        "ui_framework": None,
        # 17. closures (Closures / Anonymous Functions)
        # SQLite does not support functional closures/lambdas. (CTEs are structural boundaries/loops).
        "closures": None,
        # 18. globals (Global / Shared State)
        "globals": re.compile(
            r"\b(sqlite_master|sqlite_schema|sqlite_sequence|sqlite_temp_schema|sqlite_stat\d+|PRAGMA\s+global_)\b",
            re.I,
        ),
        # 19. decorators (Decorators / Annotations)
        # Optimizer hints.
        "decorators": re.compile(
            r"\b(?:INDEXED\s+BY|NOT\s+INDEXED|MATERIALIZED|NOT\s+MATERIALIZED)\b",
            re.I,
        ),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(r"\bANY\b|\bCAST\s*\([^)]{0,500}\)", re.I),
        # 21. comprehensions (Iterators / Comprehensions)
        # JSON iterations and windowing.
        "comprehensions": re.compile(
            r"\b(json_each|json_tree|json_group_array|json_group_object)\b|\bOVER\s*\([^)]{0,500}\)",
            re.I,
        ),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(
            r"\b(abs|acos|asin|atan|ceil|cos|degrees|exp|floor|ln|log|pi|pow|radians|sin|sqrt|tan|random|match|bm25|snippet|highlight|rtree|geopoly_[a-z_]+)\b",
            re.I,
        ),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Recursive logic and JSON paths.
        "reflection_metaprogramming": re.compile(
            r"\bWITH\s+RECURSIVE\b|\bGENERATED\s+ALWAYS\s+AS\b[^,;()]{0,20}\([^()]{0,300}\)[ \t]*(?:STORED|VIRTUAL)\b|->>|->|\b(?:json_extract|jsonb_extract)\b",
            re.I,
        ),
        # 24. import (Dependency Inclusions)
        "import": re.compile(
            r"\b(ATTACH\s+DATABASE|load_extension)\b|^[ \t]*\.(?:read|load|import)\s+",
            re.I | re.M,
        ),
        # BUG FIX (epic #813/#836): the ATTACH clause's optional-quote-pair
        # idiom (`['"]?...['"]?`) excluded whitespace from the capture
        # regardless of whether a quote was actually present -- the same
        # bug class already confirmed for PowerShell's _dependency_capture
        # (recurring class 39), but a worse "total failure" variant here:
        # because the mandatory literal `AS` keyword must immediately
        # follow the (optional) closing quote, a quoted path containing a
        # space (a real, common Windows/macOS absolute path shape) didn't
        # just truncate -- it failed to match AT ALL, since there was no
        # way to reach "AS" with the space excluded from the capture.
        # Fixed with real per-quote-style alternatives (single-quoted,
        # double-quoted, bare), consistent with the PowerShell fix.
        # BUG FIX (2026-08-30, sqlite tri-comparison validation pass): the
        # `.import`/`.read`/`.load` alternative captured the FIRST
        # whitespace-delimited token after the dot-command unconditionally
        # -- but SQLite CLI's real `.import` accepts leading flags
        # (`-csv`, `-ascii`, `-colsep ","`, `-skip N`, `-schema NAME`,
        # `-v`), a documented, common shape (`sqlite_cli_scripts/import01.
        # sql`'s corpus is full of `.import -csv file1.csv t4`). The old
        # pattern captured `-csv` itself as the "dependency path" -- a
        # real false positive polluting the dependency DAG with a garbage
        # flag-shaped node instead of the actual imported file. There's no
        # safe, bounded way to know which flags take a value (`-colsep`)
        # vs. are boolean (`-csv`) without a flag table this regex layer
        # doesn't have, so guessing past them risks capturing a flag's
        # OWN value instead (worse: still wrong, now silently so). Given
        # that choice, requiring the captured token not start with `-`
        # trades a miss (no dependency edge for a flagged `.import`) for
        # what this signal already prioritizes elsewhere in this file --
        # never a wrong path -- consistent with `.import data.csv mytable`
        # (no flags) staying captured correctly.
        "_dependency_capture": re.compile(
            r"\bATTACH\s+(?:DATABASE\s+)?(?:'([^']+)'|\"([^\"]+)\"|([^'\"\s;]+))\s+AS|"
            r"\bload_extension\s*\(\s*['\"]([^'\"]+)['\"]|^[ \t]*\.(?:read|load|import)\s+['\"]?([^'\"\s-][^'\"\s]*)['\"]?",
            re.I | re.M,
        ),
        # 25. ownership (Authorship Metadata)
        "ownership": re.compile(r"--\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # 29. spec_exposure (Spec / Audit Traceability)
        "spec_exposure": re.compile(r"--\s*\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]{0,300}\]", re.I),
        # 31. ssr_boundaries
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        "events": re.compile(
            r"\b(CREATE\s+TRIGGER|AFTER\s+UPDATE|AFTER\s+INSERT|AFTER\s+DELETE|BEFORE\s+UPDATE|BEFORE\s+INSERT|BEFORE\s+DELETE|INSTEAD\s+OF)\b",
            re.I,
        ),
        # 33. dependency_injection (Dependency Injection / IoC)
        "dependency_injection": re.compile(
            r"\b(?:sqlite3_load_extension|SELECT\s+load_extension)\b|^[ \t]*\.load\b",
            re.I | re.M,
        ),
        # 34. macros (Preprocessor Directives / Macros)
        "macros": re.compile(
            r"\b(PRAGMA\s+compile_options|sqlite_compileoption_used)\b|^[ \t]*\.parameter\s+(?:set|init)\b",
            re.I | re.M,
        ),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        "pointers": None,
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(
            r"\bPRAGMA\s+(?:mmap_size|cache_size|temp_store|page_size|shrink_memory)\b",
            re.I,
        ),
        # 37. inline_asm
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(
            r"\b(?:sqlite_stat1|sqlite_stat4|ANALYZE)\b|^[ \t]*\.(?:trace|log|show|stats|timer)\b",
            re.I | re.M,
        ),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(
            r"\b(?:disp|warning|fprintf(?![ \t]*\([ \t]*[a-zA-Z_]))\b|^\.print\b|^\.echo\b",
            re.I | re.M,
        ),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(
            r"\bCAST[ \t]*\((?:[^()]{0,500}|\([^()]{0,500}\)){0,500}[ \t]+AS[ \t]+[a-zA-Z_]+\s*\)", re.I
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        "panics_and_aborts": re.compile(r"\b(ABORT|RAISE|EXIT|QUIT)\b|^[ \t]*\.(?:exit|quit)\b", re.I | re.M),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\bPRAGMA\s+busy_timeout\b|^[ \t]*\.pause\b", re.I | re.M),
        # 43. bitwise_ops (Bitwise Operations)
        # (?<!-)>> excludes the `->>` JSON arrow operator (reflection_metaprogramming),
        # which is not a bitwise right-shift.
        "bitwise_ops": re.compile(r"<<|(?<!-)>>|\^|~|(?<!\|)\|(?!\|)"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(BEGIN\s+EXCLUSIVE|BEGIN\s+IMMEDIATE|PRAGMA\s+synchronous)\b", re.I),
        # 45. immutability_locks (Immutability Constraints)
        "immutability_locks": re.compile(r"\b(STRICT|WITHOUT\s+ROWID|CONSTANT|READONLY)\b", re.I),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(r"\b(DROP\s+TABLE|VACUUM|DETACH|CLOSE|CLEAR|DELETE\s+FROM)\b", re.I),
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Temporary/Local scopes and hidden columns.
        "encapsulation": re.compile(r"\b(TEMP|TEMPORARY|HIDDEN)\b", re.I),
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(BEFORE\s+|AFTER\s+|INSTEAD\s+OF)\b", re.I),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        "test_skip": re.compile(r"^[ \t]*\.testcase\s+skip\b|\bPRAGMA\s+ignore_check_constraints\b", re.I | re.M),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (SQLite / SQL Specifics) ---
        "serialization_parsing": re.compile(
            r"(?i)\b(json_extract|json_tree|json_each|json_object|json_array|json_type)\b"
        ),
        "regex_execution": re.compile(r"(?i)\b(REGEXP|GLOB|LIKE|MATCH)\b"),
        "time_date_logic": re.compile(
            r"(?i)\b(strftime|datetime|julianday|unixepoch|current_timestamp|current_date|current_time)\b"
        ),
        "ipc_rpc_bridges": re.compile(r"(?i)\b(ATTACH\s+DATABASE|DETACH\s+DATABASE|PRAGMA)\b"),
    },
}
