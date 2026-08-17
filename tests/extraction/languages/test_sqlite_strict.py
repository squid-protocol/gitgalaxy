"""sqlite strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

# ==============================================================================
# SQLITE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #612)
# ==============================================================================
SQLITE_RULES = LANGUAGE_DEFINITIONS["sqlite"]["rules"]

_SQLITE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "CASE WHEN status = 1 THEN 'active' ELSE 'inactive' END", "SELECT id FROM users"),
    ("args", "SELECT * FROM t WHERE id = :id", "SELECT * FROM t WHERE id = 5"),
    ("structural_boundaries", "SELECT * FROM users", "PRAGMA foreign_keys = ON;"),
    (
        "func_start",
        "CREATE TRIGGER trg_users_audit AFTER UPDATE ON users BEGIN SELECT 1; END;",
        "CREATE TABLE users (id INTEGER);",
    ),
    (
        "class_start",
        "CREATE TABLE users (id INTEGER PRIMARY KEY);",
        "CREATE VIEW active_users AS SELECT * FROM users;",
    ),
    ("safety", "CREATE TABLE t (id INTEGER PRIMARY KEY, CHECK (id > 0));", "SELECT * FROM t;"),
    ("safety_bypasses", "DROP TABLE IF EXISTS staging;", "CREATE TABLE staging (id INTEGER);"),
    ("high_risk_execution", ".shell ls -la", "SELECT 1;"),
    ("io", "SELECT * FROM users;", "BEGIN TRANSACTION;"),
    ("api", "CREATE VIEW active_users AS SELECT * FROM users;", "CREATE TABLE users (id INTEGER);"),
    ("state_mutation", "UPDATE users SET status = 'inactive' WHERE id = 1;", "SELECT * FROM users;"),
    ("dead_code", "-- SELECT * FROM old_table", "-- This is just a comment"),
    ("doc", "-- @param id The user id", "-- just a note"),
    ("test", "EXPLAIN QUERY PLAN SELECT * FROM users;", "SELECT * FROM users;"),
    ("concurrency", "BEGIN EXCLUSIVE;", "BEGIN;"),
    ("globals", "SELECT * FROM sqlite_master;", "SELECT * FROM users;"),
    ("decorators", "SELECT * FROM t INDEXED BY idx_t_x WHERE x = 1;", "SELECT * FROM t WHERE x = 1;"),
    ("generics", "SELECT CAST(x AS INTEGER) FROM t;", "SELECT x FROM t;"),
    (
        "comprehensions",
        "SELECT ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary) FROM emp;",
        "SELECT dept, salary FROM emp;",
    ),
    ("scientific", "SELECT sqrt(4);", "SELECT 4;"),
    (
        "reflection_metaprogramming",
        "WITH RECURSIVE counter(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM counter WHERE x<10) SELECT * FROM counter;",
        "SELECT * FROM counter;",
    ),
    ("import", "ATTACH DATABASE 'other.db' AS other;", "SELECT * FROM other.t;"),
    ("ownership", "-- Author: Jane Doe", "-- just a comment"),
    ("planned_debt", "-- TODO: add index on created_at", "-- normal comment"),
    ("fragile_debt", "-- HACK: workaround for legacy bug", "-- normal comment"),
    ("spec_exposure", "-- [SPEC-123] audit trail requirements", "-- normal comment"),
    ("events", "CREATE TRIGGER trg AFTER UPDATE ON t BEGIN SELECT 1; END;", "CREATE TABLE t (id INTEGER);"),
    ("dependency_injection", "SELECT load_extension('json1');", "SELECT * FROM t;"),
    ("macros", "PRAGMA compile_options;", "PRAGMA foreign_keys = ON;"),
    ("memory_alloc", "PRAGMA mmap_size = 268435456;", "PRAGMA foreign_keys = ON;"),
    ("telemetry", "ANALYZE;", "SELECT 1;"),
    ("debug_prints", ".print 'debug'", "SELECT 1;"),
    ("explicit_casts", "SELECT CAST(x AS INTEGER);", "SELECT x;"),
    ("panics_and_aborts", "SELECT RAISE(ABORT, 'blocked');", "SELECT 1;"),
    ("thread_sleeps", "PRAGMA busy_timeout = 5000;", "PRAGMA foreign_keys = ON;"),
    ("bitwise_ops", "SELECT x >> 2;", "SELECT x + 2;"),
    ("sync_locks", "BEGIN EXCLUSIVE;", "BEGIN;"),
    ("immutability_locks", "CREATE TABLE t (id INTEGER) STRICT;", "CREATE TABLE t (id INTEGER);"),
    ("cleanup", "VACUUM;", "SELECT 1;"),
    ("encapsulation", "CREATE TEMP TABLE staging (id INTEGER);", "CREATE TABLE staging (id INTEGER);"),
    ("listeners", "CREATE TRIGGER trg BEFORE INSERT ON t BEGIN SELECT 1; END;", "CREATE TABLE t (id INTEGER);"),
    ("test_skip", ".testcase skip", "SELECT 1;"),
    ("serialization_parsing", "SELECT json_extract(data, '$.id') FROM t;", "SELECT data FROM t;"),
    ("regex_execution", "SELECT * FROM t WHERE x REGEXP '^a';", "SELECT * FROM t WHERE x = 'a';"),
    ("time_date_logic", "SELECT datetime('now');", "SELECT 1;"),
    ("ipc_rpc_bridges", "ATTACH DATABASE 'other.db' AS other;", "SELECT 1;"),

    # ==========================================
    # ADVERSARIAL DEEP CASES
    # ==========================================
    # branch
    ("branch", "select * from t wHeRe id=1", "SELECT where_id FROM t"),
    ("branch", "SELECT SUM(x) FILTER(WHERE y=1) FROM t", "SELECT filtered_val FROM t"),
    ("branch", "SELECT COALESCE(a, b) FROM t", "CREATE TABLE coalesce_table (id INT)"),
    ("branch", "SELECT IIF(x>0, 'A', 'B')", "SELECT x_iif FROM t"),
    ("branch", "SELECT x FROM t HAVING COUNT(*) > 1", "SELECT having_clause FROM t"),
    ("branch", "SELECT CASE x WHEN 1 THEN 2 ELSE 3 END", "SELECT end_time FROM t"),

    # args
    ("args", "WITH recursive my_cte (col1, col2) AS (SELECT 1, 2)", "WITH my_cte AS (SELECT 1, 2)"),
    ("args", "SELECT * FROM t WHERE id IN (SELECT id FROM other)", "SELECT * FROM t WHERE id = 1"),
    ("args", "INSERT INTO t VALUES (1, 2, 3)", "INSERT INTO t DEFAULT VALUES"),
    ("args", "SELECT * FROM t WHERE id = ?123", "SELECT a_123 FROM t"),
    ("args", "SELECT * FROM t WHERE id = @param_name", "SELECT param_name FROM t"),
    ("args", "SELECT * FROM t WHERE id = $param_name", "SELECT param_name FROM t"),
    ("args", "SELECT * FROM t WHERE id = :param_name", "SELECT param_name FROM t"),

    # structural_boundaries
    ("structural_boundaries", "A INNER JOIN B", "UPDATE t SET inner_join_val = 1"),
    ("structural_boundaries", "A LEFT JOIN B", "UPDATE t SET left_join_val = 1"),
    ("structural_boundaries", "A CROSS JOIN B", "UPDATE t SET cross_join_val = 1"),
    ("structural_boundaries", "A RIGHT JOIN B", "UPDATE t SET right_join_val = 1"),
    ("structural_boundaries", "A FULL JOIN B", "UPDATE t SET full_join_val = 1"),
    ("structural_boundaries", "A NATURAL JOIN B", "UPDATE t SET natural_join_val = 1"),
    ("structural_boundaries", "CREATE TABLE t (id INT) STRICT", "CREATE TABLE t (strict_val INT)"),
    ("structural_boundaries", "CREATE TABLE t (id INT) WITHOUT ROWID", "UPDATE t SET without_rowid_val = 1"),
    ("structural_boundaries", "SELECT ROW_NUMBER() OVER (PARTITION BY x)", "UPDATE t SET partition_by_val = 1"),
    ("structural_boundaries", "SELECT a FROM t GROUP BY a", "UPDATE t SET group_by_val = 1"),
    ("structural_boundaries", "SELECT a FROM t ORDER BY a", "UPDATE t SET order_by_val = 1"),

    # func_start
    ("func_start", "CREATE TRIGGER IF NOT EXISTS main.my_trig AFTER INSERT", "CREATE TABLE main_my_trig (id INT)"),
    ("func_start", "CREATE TEMP VIEW [my view] AS SELECT 1", "CREATE TABLE temp_view (id INT)"),
    ("func_start", "CREATE UNIQUE INDEX `my idx` ON t(a)", "CREATE TABLE unique_index (id INT)"),
    ("func_start", "CREATE TRIGGER \"my trig\" BEFORE UPDATE", "CREATE TABLE my_trig (id INT)"),
    ("func_start", "CREATE VIEW IF NOT EXISTS v AS SELECT 1", "CREATE TABLE view_if_not_exists (id INT)"),
    ("func_start", "CREATE \n TRIGGER \n trg \n AFTER", "CREATE TABLE trg (id INT)"),

    # class_start
    ("class_start", "CREATE TABLE IF NOT EXISTS main.[my table] (id INT)", "CREATE VIEW main.[my table] AS SELECT 1"),
    ("class_start", "CREATE TEMP TABLE `my table` (id INT)", "CREATE VIEW temp_table AS SELECT 1"),
    ("class_start", "CREATE VIRTUAL TABLE t USING fts5", "CREATE VIEW virtual_table AS SELECT 1"),
    ("class_start", "CREATE \n TABLE \n IF NOT EXISTS \n tbl (id INT)", "CREATE VIEW tbl AS SELECT 1"),
    ("class_start", "CREATE TABLE \"table with spaces\" (id INT)", "CREATE VIEW \"table with spaces\" AS SELECT 1"),
]


@pytest.mark.parametrize("signature,positive,negative", _SQLITE_SIMPLE_CASES)
def test_sqlite_signature_positive_and_negative(signature, positive, negative):
    pattern = SQLITE_RULES[signature]
    assert pattern is not None, f"sqlite's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"sqlite {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"sqlite {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_sqlite_dependency_capture_extracts_path():
    """
    _dependency_capture is paired with `import` and must extract the exact
    dependency path/module string into a capture group, not just detect
    presence. Covers all three import shapes sqlite supports.

    Checks "any non-None group" rather than a hardcoded group index,
    matching how galaxyscope.py's own consumer actually reads this rule
    (`next((g for g in match.groups() if g), None)`, not `match.group(N)`)
    -- the real contract is "the path is in SOME group", not "group 1/2/3
    specifically". The ATTACH alternative below has three of its own
    sub-groups (single-quoted/double-quoted/bare, epic #813/#836's quoted-
    path-with-space fix), which already shifted load_extension's and the
    dot-command's own group numbers once; a hardcoded index would have
    been re-broken by the next legitimate restructuring too.
    """
    pattern = SQLITE_RULES["_dependency_capture"]

    m = pattern.search("ATTACH DATABASE 'other.db' AS other;")
    assert m and next((g for g in m.groups() if g), None) == "other.db"

    m = pattern.search("SELECT load_extension('json1');")
    assert m and next((g for g in m.groups() if g), None) == "json1"

    m = pattern.search(".import data.csv mytable")
    assert m and next((g for g in m.groups() if g), None) == "data.csv"


def test_sqlite_high_risk_execution_dot_command_leading_boundary_and_case_regression():
    """
    Regression test for two compounded bugs in the same rule:

    1. `.shell`/`.system`/`.exit`/`.quit` all start with `.` (non-word), so
       the shared leading `\\b` inside `\\b(...)\\b` could only fire when a
       word char immediately preceded the `.` -- never true for how these
       sqlite3 CLI dot-commands are actually written (always the first
       token on a line, preceded only by whitespace or nothing). All four
       of the CLI's process-killing/shell-escape commands never matched at
       all.
    2. The rule also had no `re.I` flag at all (every sibling Phase-2 rule
       does), so even the keyword alternatives (`PRAGMA legacy_alter_table`,
       `DROP DATABASE`) were silently case-sensitive-only and missed
       lowercase SQL, which is extremely common in real migration scripts.

    Fixed by pulling the dot-commands out into a `^[ \\t]*\\.` anchored
    alternative (matching the pattern already used correctly by
    import/debug_prints/telemetry/macros/dependency_injection) and adding
    `re.I`.
    """
    pattern = SQLITE_RULES["high_risk_execution"]
    assert pattern.search(".shell ls -la"), ".shell still didn't match"
    assert pattern.search(".system ls"), ".system still didn't match"
    assert pattern.search(".exit"), ".exit still didn't match"
    assert pattern.search(".quit"), ".quit still didn't match"
    assert pattern.search("pragma legacy_alter_table=1;"), "lowercase PRAGMA still didn't match"
    assert pattern.search("drop database foo;"), "lowercase DROP DATABASE still didn't match"
    assert pattern.search("DROP DATABASE foo;"), "uppercase form regressed"


def test_sqlite_io_dot_command_leading_boundary_regression():
    """
    Regression test: `.import`/`.output`/`.dump`/`.read` all start with `.`
    (non-word), so the shared leading `\\b` inside `\\b(...)\\b` could only
    fire when a word char immediately preceded the `.` -- never true for
    how these sqlite3 CLI I/O dot-commands are actually written (always
    the first token on a line). All four never matched at all.
    """
    pattern = SQLITE_RULES["io"]
    assert pattern.search(".import data.csv mytable"), ".import still didn't match"
    assert pattern.search(".output out.txt"), ".output still didn't match"
    assert pattern.search(".dump"), ".dump still didn't match"
    assert pattern.search(".read script.sql"), ".read still didn't match"
    assert pattern.search("SELECT * FROM users;"), "SELECT regressed"


def test_sqlite_test_dot_command_leading_boundary_regression():
    """
    Regression test: `.lint`/`.testcase` both start with `.` (non-word), so
    the shared leading `\\b` inside `\\b(...)\\b` could only fire when a
    word char immediately preceded the `.` -- never true for how these
    dot-commands are actually written. Both never matched at all.
    """
    pattern = SQLITE_RULES["test"]
    assert pattern.search(".lint fkey-indexes"), ".lint still didn't match"
    assert pattern.search(".testcase foo"), ".testcase still didn't match"
    assert pattern.search("EXPLAIN QUERY PLAN SELECT * FROM users;"), "EXPLAIN QUERY PLAN regressed"


def test_sqlite_unanchored_dot_command_false_positive_regression():
    """
    Regression test for the mirror-image bug of the leading-boundary cases
    above: `panics_and_aborts` (`.exit`/`.quit`), `thread_sleeps`
    (`.pause`), and `test_skip` (`.testcase skip`) each referenced their
    dot-command as a bare, unanchored literal with no `\\b` at all. Since
    a bare `.exit` is just a substring, it matched inside completely
    ordinary qualified column references like `app.exitcode` or
    `s.pause_time` -- a table-qualified column happening to start with the
    same letters as the CLI command. Anchored each to `^[ \\t]*\\.`
    (line-start), matching the correct existing pattern used elsewhere in
    this dict, which eliminates the false positive without affecting the
    real dot-command usage.
    """
    panics = SQLITE_RULES["panics_and_aborts"]
    assert panics.search(".exit"), "real .exit dot-command regressed"
    assert panics.search(".quit"), "real .quit dot-command regressed"
    assert not panics.search("SELECT s.exitcode FROM sessions s;"), (
        "panics_and_aborts incorrectly matched a qualified column reference"
    )
    assert panics.search("RAISE(ABORT, 'x');"), "keyword form regressed"

    sleeps = SQLITE_RULES["thread_sleeps"]
    assert sleeps.search(".pause"), "real .pause dot-command regressed"
    assert not sleeps.search("SELECT s.pause_time FROM sessions s;"), (
        "thread_sleeps incorrectly matched a qualified column reference"
    )
    assert sleeps.search("PRAGMA busy_timeout = 5000;"), "PRAGMA form regressed"

    skip = SQLITE_RULES["test_skip"]
    assert skip.search(".testcase skip"), "real .testcase skip dot-command regressed"
    assert not skip.search("UPDATE t SET note='x.testcase skip flaky';"), (
        "test_skip incorrectly matched inside a string literal"
    )
    assert skip.search("PRAGMA ignore_check_constraints = 1;"), "PRAGMA form regressed"


def test_sqlite_comprehensions_over_trailing_boundary_regression():
    """
    Regression test: the shared trailing `\\b` after the `OVER\\s*\\([^)]*\\)`
    alternative required a word character immediately following the
    closing `)` -- never true for how a window-function clause is
    actually written (always followed by `;`, whitespace, a comma, or
    end-of-string, all non-word). SQLite's `OVER (...)` window-function
    syntax -- this signature's whole reason for existing -- never matched
    at all. Fixed by dropping the trailing `\\b` for that alternative (the
    `)` is already self-delimiting, same principle as Rule 10).
    """
    pattern = SQLITE_RULES["comprehensions"]
    assert pattern.search("SELECT ROW_NUMBER() OVER (PARTITION BY x ORDER BY y);"), (
        "OVER(...) followed by ';' still didn't match"
    )
    assert pattern.search("SELECT ROW_NUMBER() OVER (PARTITION BY x ORDER BY y)"), (
        "OVER(...) at end-of-string still didn't match"
    )
    assert pattern.search("SELECT ROW_NUMBER() OVER (ORDER BY y), name FROM t"), (
        "OVER(...) followed by ',' still didn't match"
    )
    assert pattern.search("SELECT json_each.value FROM json_each(t.tags);"), "json_each regressed"


def test_sqlite_explicit_casts_nested_paren_regression():
    """
    Regression test (Rule 11, nested-delimiter coverage): the flat negated
    class `[^)]+` between `CAST(` and the required `AS <type>)` couldn't
    represent one level of nested parens, so any CAST wrapping a nested
    function call -- extremely idiomatic SQLite
    (`CAST(json_extract(data,'$.id') AS INTEGER)`,
    `CAST(COALESCE(x, 0) AS INTEGER)`) -- never matched at all, unlike the
    identical form with a bare column. Fixed with a bounded one-level
    nesting form: `(?:[^()]{0,500}|\\([^()]{0,500}\\)){0,500}`.
    """
    pattern = SQLITE_RULES["explicit_casts"]
    assert pattern.search("SELECT CAST(x AS INTEGER);"), "plain CAST regressed"
    assert pattern.search("SELECT CAST(json_extract(data,'$.id') AS INTEGER);"), (
        "CAST wrapping json_extract(...) still didn't match"
    )
    assert pattern.search("SELECT CAST(COALESCE(a, 0) AS INTEGER);"), "CAST wrapping COALESCE(...) still didn't match"


def test_sqlite_dead_code_comment_style_completeness_regression():
    """
    Regression test (Rule 12): sqlite's `lexical_family` is
    `multi_style_dash`, meaning both `--` line comments AND `/* */` block
    comments are valid non-executable text. The original `dead_code`
    regex only checked the `--` prefix, so commented-out DDL/DML written
    with a `/* ... */` block comment -- an equally common style for
    temporarily disabling a chunk of SQL -- never fired at all. Fixed to
    check both markers.
    """
    pattern = SQLITE_RULES["dead_code"]
    assert pattern.search("-- SELECT * FROM old_table"), "'--' style regressed"
    assert pattern.search("/* SELECT * FROM old_table */"), "'/* */' style still didn't match"
    assert pattern.search("/* INSERT INTO t VALUES (1) */"), "'/* */' style with INSERT still didn't match"


def test_sqlite_reflection_metaprogramming_virtual_table_false_collision_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: the bare `VIRTUAL`
    alternative was intended to catch the storage mode of a generated
    column (`GENERATED ALWAYS AS (expr) VIRTUAL`), per this rule's own doc
    comment ("Recursive logic and JSON paths"). But as a standalone
    keyword it also fired on the completely unrelated and far more common
    `CREATE VIRTUAL TABLE ... USING fts5(...)` construct (SQLite's
    full-text-search/extension-module table syntax), which is not
    generated-column metaprogramming at all. Fixed by requiring
    `STORED`/`VIRTUAL` to actually follow a `GENERATED ALWAYS AS (...)`
    clause.
    """
    pattern = SQLITE_RULES["reflection_metaprogramming"]
    assert pattern.search("price_with_tax INTEGER GENERATED ALWAYS AS (price * 1.08) STORED"), (
        "real generated-column STORED form regressed"
    )
    assert pattern.search("price_with_tax INTEGER GENERATED ALWAYS AS (price * 1.08) VIRTUAL"), (
        "real generated-column VIRTUAL form regressed"
    )
    assert not pattern.search("CREATE VIRTUAL TABLE fts USING fts5(body);"), (
        "incorrectly classified an unrelated CREATE VIRTUAL TABLE as metaprogramming"
    )
    assert pattern.search("WITH RECURSIVE counter(x) AS (SELECT 1)"), "WITH RECURSIVE regressed"


def test_sqlite_bitwise_ops_json_arrow_false_collision_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: bitwise_ops' bare `>>`
    alternative matched as a substring inside sqlite's `->>` "extract as
    text" JSON path operator, misclassifying every JSON field access as a
    bitwise right-shift. Fixed with a negative lookbehind excluding `>>`
    when immediately preceded by `-`.
    """
    bitwise_ops = SQLITE_RULES["bitwise_ops"]
    reflection = SQLITE_RULES["reflection_metaprogramming"]

    json_arrow = "SELECT data ->> '$.id' FROM events;"
    assert reflection.search(json_arrow)
    assert not bitwise_ops.search(json_arrow), "bitwise_ops incorrectly matched inside the '->>' JSON operator"

    real_shift = "SELECT x >> 2 FROM t;"
    assert bitwise_ops.search(real_shift), "real bitwise right-shift regressed"


def test_sqlite_class_start_end_of_string_boundary_regression():
    """
    Regression test: class_start's table-name lookahead was
    `(?=[ \\t\\(\\n;])`, missing the `|$` end-of-string alternative that
    func_start's near-identical lookahead already carries (added in an
    earlier fix for the exact same construct). A file whose final line is
    a bare `CREATE TABLE foo` with no trailing newline/paren/semicolon
    never matched.
    """
    pattern = SQLITE_RULES["class_start"]
    assert pattern.search("CREATE TABLE foo (id INTEGER);"), "normal mid-file form regressed"
    assert pattern.search("CREATE TABLE foo"), "end-of-string form (no trailing char) still didn't match"


def test_sqlite_redos_immunity():
    """
    Regression test for five confirmed real O(n^2) ReDoS vectors, all
    sharing the same root cause: a flat, unbounded negated-class delimiter
    matcher (`[^)]*`/`[^\\]]*`) combined with an unanchored search over a
    payload that repeats the opening anchor keyword/delimiter many times
    with no closing delimiter anywhere in the file. Each starting position
    then scans to the end of the file before failing, giving O(n^2) total
    work. Confirmed genuine ~4x-per-doubling scaling at n=2k/4k/8k/16k
    before bounding (e.g. explicit_casts: ~0.11s/0.43s/1.73s/6.95s;
    args (VALUES): ~0.015s/0.058s/0.23s/0.92s; generics (CAST):
    ~0.009s/0.036s/0.14s/0.57s; comprehensions (OVER):
    ~0.011s/0.044s/0.17s/0.69s; spec_exposure: ~0.04s/0.17s/0.69s/2.74s).
    All five bounded to generous-but-finite numeric caps.
    """
    assert_redos_immune(SQLITE_RULES["args"], "VALUES (" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["args"], "x IN (" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["generics"], "CAST(" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["comprehensions"], "OVER (" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["explicit_casts"], "CAST(" * 20000, timeout_sec=3.0)
    assert_redos_immune(SQLITE_RULES["spec_exposure"], "-- [SPEC-1 [" * 20000, timeout_sec=3.0)

    # Realistic-but-large inputs must still match after bounding.
    assert SQLITE_RULES["args"].search("INSERT INTO t VALUES (" + "1," * 400 + "1);")
    assert SQLITE_RULES["generics"].search("SELECT CAST(COALESCE(a, 0) AS INTEGER);")
    assert SQLITE_RULES["comprehensions"].search("SELECT ROW_NUMBER() OVER (PARTITION BY x ORDER BY y);")
    assert SQLITE_RULES["explicit_casts"].search("SELECT CAST(json_extract(data,'$.id') AS INTEGER);")
    assert SQLITE_RULES["spec_exposure"].search("-- [SPEC-123] audit trail")


def test_sqlite_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for sqlite that are
    genuine, intentional double-classifications (not bugs) -- confirmed
    via direct empirical verification against realistic SQL:

    - `structural_boundaries` <-> `safety`/`immutability_locks` on
      `STRICT`: a STRICT table declaration is simultaneously a structural
      qualifier and an integrity/immutability guarantee -- all three
      rules deliberately list it.
    - `structural_boundaries` <-> `io` on `SELECT`: a SELECT is
      simultaneously query structure and a read I/O operation.
    - `func_start` <-> `api` on `CREATE VIEW`: a view is simultaneously
      executable query logic and explicitly public surface area.
    - `func_start` <-> `events` on `CREATE TRIGGER`: a trigger is
      simultaneously executable logic and an event-driven construct.
    - `events` <-> `listeners` on `AFTER`/`BEFORE`: a trigger's timing
      keyword is simultaneously the event definition and the listener
      registration for it.
    - `scientific` <-> `regex_execution` on `MATCH`: sqlite overloads the
      `MATCH` operator across FTS5 full-text search (a text-ranking/
      analytical operation) and generic virtual-table pattern matching --
      both classifications are correct for the same operator.
    - `ipc_rpc_bridges`'s bare `PRAGMA` deliberately overlaps nearly every
      other PRAGMA-based rule (concurrency, safety, thread_sleeps,
      memory_alloc, macros, test) -- it is intentionally a broad
      catch-all for engine-control statements, not a bug to narrow.
    """
    structural_boundaries = SQLITE_RULES["structural_boundaries"]
    safety = SQLITE_RULES["safety"]
    immutability_locks = SQLITE_RULES["immutability_locks"]
    io = SQLITE_RULES["io"]
    func_start = SQLITE_RULES["func_start"]
    api = SQLITE_RULES["api"]
    events = SQLITE_RULES["events"]
    listeners = SQLITE_RULES["listeners"]
    scientific = SQLITE_RULES["scientific"]
    regex_execution = SQLITE_RULES["regex_execution"]
    ipc_rpc_bridges = SQLITE_RULES["ipc_rpc_bridges"]
    concurrency = SQLITE_RULES["concurrency"]

    strict_table = "CREATE TABLE t (id INTEGER) STRICT;"
    assert structural_boundaries.search(strict_table)
    assert safety.search(strict_table)
    assert immutability_locks.search(strict_table)

    select_stmt = "SELECT * FROM t;"
    assert structural_boundaries.search(select_stmt)
    assert io.search(select_stmt)

    view = "CREATE VIEW active_users AS SELECT * FROM users;"
    assert func_start.search(view)
    assert api.search(view)

    trigger = "CREATE TRIGGER trg AFTER UPDATE ON t BEGIN SELECT 1; END;"
    assert func_start.search(trigger)
    assert events.search(trigger)
    assert listeners.search(trigger)

    fts_match = "SELECT * FROM docs WHERE body MATCH 'sqlite';"
    assert scientific.search(fts_match)
    assert regex_execution.search(fts_match)

    pragma_wal = "PRAGMA journal_mode = WAL;"
    assert ipc_rpc_bridges.search(pragma_wal)
    assert concurrency.search(pragma_wal)


def test_sqlite_func_start_and_macros_no_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line
    preprocessor/macro spiral fooling func_start, as found in C++): not
    applicable to sqlite. SQLite has no C-style textual preprocessor --
    `macros` here maps to `PRAGMA compile_options`/
    `sqlite_compileoption_used` (introspecting how the SQLite library
    itself was compiled) and the `.parameter set/init` CLI bind-parameter
    commands, none of which share any token with func_start's
    `CREATE TRIGGER/VIEW/INDEX` anchors. Empirically confirmed neither
    rule ever fires on the other's construct.
    """
    func_start = SQLITE_RULES["func_start"]
    macros = SQLITE_RULES["macros"]

    trigger = "CREATE TRIGGER trg AFTER UPDATE ON t BEGIN SELECT 1; END;"
    assert func_start.search(trigger)
    assert not macros.search(trigger)

    compile_opts = "PRAGMA compile_options;"
    assert macros.search(compile_opts)
    assert not func_start.search(compile_opts)


def test_sqlite_test_and_regex_execution_no_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style
    regex method miscounted as a test-framework call, as found in
    TypeScript): confirmed not applicable to sqlite. sqlite has no native
    `.test(`-style regex method -- `test` maps to
    `EXPLAIN QUERY PLAN`/`PRAGMA integrity_check`/`PRAGMA foreign_key_check`/
    the `.testcase`/`.lint` CLI commands, and `regex_execution` maps to the
    `REGEXP`/`GLOB`/`LIKE`/`MATCH` pattern-matching operators. These two
    vocabularies are fully disjoint; empirically confirmed neither rule
    ever fires on the other's construct.
    """
    test = SQLITE_RULES["test"]
    regex_execution = SQLITE_RULES["regex_execution"]

    regexp_query = "SELECT * FROM t WHERE x REGEXP '^a';"
    assert regex_execution.search(regexp_query)
    assert not test.search(regexp_query)

    eqp = "EXPLAIN QUERY PLAN SELECT * FROM t;"
    assert test.search(eqp)
    assert not regex_execution.search(eqp)
