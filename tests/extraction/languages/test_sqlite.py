"""
SQLite extraction hardening (epic #813, issue #836). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for sqlite in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the two old
monolithic dict files that had sqlite entries (test_function_extraction_
strict.py, test_dependency_extraction_strict.py -- test_args_extraction_
strict.py and test_class_extraction_strict.py had no sqlite entry at all;
args and class_start had zero prior test coverage before this file).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo, so a dotted
# `tests.extraction._extraction_harness` import only works by accident
# locally (e.g. `python -m pytest` from the repo root happens to put the
# root on sys.path) and fails in CI, which invokes the `pytest` console
# script directly. Insert this file's parent (tests/extraction/) onto
# sys.path instead, so the harness imports as a plain top-level module.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

SQLITE_RULES = LANGUAGE_DEFINITIONS["sqlite"]["rules"]

# ==============================================================================
# FUNC_START (func_start) -- CREATE TRIGGER/VIEW/INDEX.
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("CREATE TRIGGER TargetFunc", "TargetFunc"),  # carried-forward
        ("CREATE VIEW TargetFunc", "TargetFunc"),  # carried-forward
        ("CREATE UNIQUE INDEX TargetFunc", "TargetFunc"),  # carried-forward
        ("CREATE INDEX idx_email ON users(email);", "idx_email"),  # basic index
        ("CREATE TRIGGER my_trigger AFTER INSERT ON users BEGIN\nEND;", "my_trigger"),
        (
            "CREATE TRIGGER main.my_trigger AFTER INSERT ON users BEGIN\nEND;",
            "my_trigger",
        ),  # schema-qualified -- was a real bug, now fixed
        ("CREATE INDEX main.idx_email ON users(email);", "idx_email"),  # schema-qualified index
        ('CREATE VIEW "group" AS SELECT 1;', "group"),  # double-quoted (reserved-word name) -- was a real bug, now fixed
        ("CREATE INDEX [my index] ON users(email);", "my index"),  # bracket-quoted with space -- was a real bug, now fixed
        ("CREATE TRIGGER `my_trigger` AFTER INSERT ON users BEGIN\nEND;", "my_trigger"),  # backtick-quoted
    ],
    "invalid": [
        "CREATE TABLE TargetFunc",  # carried-forward: TABLE isn't TRIGGER/VIEW/INDEX
        "DROP VIEW TargetFunc",  # carried-forward: DROP isn't CREATE
        "-- CREATE TRIGGER my_trigger AFTER INSERT ON users BEGIN",  # commented-out (-- line comment)
        "SELECT * FROM users;",  # unrelated statement
    ],
    "pathological": [
        (
            "CREATE \n TEMPORARY \n TRIGGER \n IF \n NOT \n EXISTS \n TargetFunc \n ",
            "TargetFunc",
        ),  # carried-forward: vertical modifier stacking
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_sqlite_func_start_valid(payload, expected_name):
    assert_valid_match(SQLITE_RULES["func_start"], payload, expected_name, "sqlite.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_sqlite_func_start_invalid(payload):
    assert_invalid_no_match(SQLITE_RULES["func_start"], payload, "sqlite.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_sqlite_func_start_pathological(payload, expected_name):
    assert_pathological_match(SQLITE_RULES["func_start"], payload, expected_name, "sqlite.func_start")


def test_sqlite_func_start_schema_qualified_name_regression():
    """
    Regression test for a real bug (epic #813/#836): no allowance for a
    schema-qualified name (`CREATE TRIGGER main.my_trigger ...`) -- standard,
    common SQLite syntax when working with ATTACHed databases or explicitly
    targeting `temp.`. Since `\\w` never spans a literal `.`, the old pattern
    couldn't capture "main.my_trigger" as one token and had no fallback to
    skip the schema prefix -- the whole match failed outright. Fixed with an
    optional schema-prefix skip before the capture.
    """
    func_start = SQLITE_RULES["func_start"]
    m = func_start.search("CREATE TRIGGER main.my_trigger AFTER INSERT ON users BEGIN\nEND;")
    assert m and m.group(1) == "my_trigger", "schema-qualified trigger name regressed"


def test_sqlite_func_start_quoted_identifier_regression():
    """
    Regression test for a real bug (epic #813/#836): no allowance for any of
    SQLite's three quoted-identifier styles (`"name"`, `` `name` ``,
    `[name]`) -- so even a plain quoted name with no special characters at
    all failed outright. Quoting a name to avoid a reserved-word collision
    (`CREATE VIEW "group" AS ...`) is the single most common real reason to
    quote an identifier. Fixed by adding the three quoted forms as
    alternatives inside the SAME capture group (quotes included in the
    captured text) rather than new numbered groups, since detector.py
    reserves capture group 2 specifically for class_start's
    inheritance-parent extraction on other languages.
    """
    func_start = SQLITE_RULES["func_start"]
    m = func_start.search('CREATE VIEW "group" AS SELECT 1;')
    assert m and m.group(1) == '"group"', "double-quoted reserved-word name regressed"
    assert func_start.groups == 1, "must stay a single capture group (class_start's group-2 convention)"


def test_sqlite_func_start_redos_immunity():
    """ReDoS sweep for the schema-prefix skip and quoted-identifier alternatives."""
    func_start = SQLITE_RULES["func_start"]
    assert_redos_immune(func_start, 'CREATE TRIGGER "' + "a" * 200000, timeout_sec=3.0)
    assert_redos_immune(func_start, "CREATE TRIGGER [" + "a" * 200000, timeout_sec=3.0)
    assert func_start.search("CREATE TRIGGER foo")


# ==============================================================================
# CLASS_START (class_start) -- CREATE TABLE.
# NOTE: test_class_extraction_strict.py had NO sqlite entry at all --
# class_start had zero prior test coverage before this file.
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("CREATE TABLE users (id INTEGER);", "users"),
        ("CREATE TABLE IF NOT EXISTS users (id INTEGER);", "users"),
        ("CREATE TEMP TABLE users (id INTEGER);", "users"),
        ("CREATE TEMPORARY TABLE users (id INTEGER);", "users"),
        ("CREATE VIRTUAL TABLE fts USING fts5(content);", "fts"),
        ("CREATE TABLE main.users (id INTEGER);", "users"),  # schema-qualified -- was a real bug, now fixed
        ("CREATE TABLE temp.users (id INTEGER);", "users"),  # temp-qualified -- was a real bug, now fixed
        ('CREATE TABLE "my_table"(id INTEGER);', "my_table"),  # double-quoted -- was a real bug, now fixed
        ('CREATE TABLE "my table"(id INTEGER);', "my table"),  # double-quoted with space -- was a real bug, now fixed
        ("CREATE TABLE [my_table](id INTEGER);", "my_table"),  # bracket-quoted
        ("CREATE TABLE users (id INTEGER) STRICT;", "users"),  # STRICT clause after
        ("CREATE TABLE users (id INTEGER) WITHOUT ROWID;", "users"),  # WITHOUT ROWID clause after
    ],
    "invalid": [
        "-- CREATE TABLE users (id INTEGER);",  # commented-out (-- line comment)
        "SELECT * FROM users;",  # unrelated statement
    ],
    "pathological": [
        (
            "CREATE \n TABLE \n IF \n NOT \n EXISTS \n users \n (id INTEGER);",
            "users",
        ),  # vertical modifier stacking
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_sqlite_class_start_valid(payload, expected_name):
    assert_valid_match(SQLITE_RULES["class_start"], payload, expected_name, "sqlite.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_sqlite_class_start_invalid(payload):
    assert_invalid_no_match(SQLITE_RULES["class_start"], payload, "sqlite.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_sqlite_class_start_pathological(payload, expected_name):
    assert_pathological_match(SQLITE_RULES["class_start"], payload, expected_name, "sqlite.class_start")


def test_sqlite_class_start_schema_qualified_and_quoted_regression():
    """
    Regression test for a real bug (epic #813/#836), same root cause and
    fix as func_start's own regressions above: `CREATE TABLE main.users
    (...)` (schema-qualified) and `CREATE TABLE "my table" (...)` (quoted,
    with a space) were both entirely invisible.
    """
    class_start = SQLITE_RULES["class_start"]
    m1 = class_start.search("CREATE TABLE main.users (id INTEGER);")
    assert m1 and m1.group(1) == "users", "schema-qualified table name regressed"
    m2 = class_start.search('CREATE TABLE "my table"(id INTEGER);')
    assert m2 and m2.group(1) == '"my table"', "quoted table name with space regressed"
    assert class_start.groups == 1, "must stay a single capture group (the inheritance-parent convention)"


def test_sqlite_class_start_if_not_exists_vertical_gap_regression():
    """
    Regression test for a genuinely pre-existing bug (not introduced by this
    issue's other fixes -- found via this file's own vertical-formatting
    pathological case, not a pre-flagged finding): the "IF NOT EXISTS"
    clause's own trailing gap used `[ \\t]+`, unlike its internal `NOT`/
    `EXISTS` gaps (`\\s+`, which already included newlines). func_start's own
    "VERTICAL MODIFIER SHIELD" fix (see its comment) already covers this
    exact shape for TRIGGER/VIEW/INDEX, but was never applied to
    class_start's parallel TABLE clause -- so a real, common vertical
    formatting style (`CREATE TABLE IF NOT EXISTS\\n    users (...)`)
    silently captured "IF" as the table name instead of "users". Widened to
    `[ \\t\\n]+`, matching func_start's existing idiom.
    """
    class_start = SQLITE_RULES["class_start"]
    m = class_start.search("CREATE TABLE IF NOT EXISTS \n users (id INTEGER);")
    assert m and m.group(1) == "users", "vertical gap after IF NOT EXISTS regressed -- captured IF instead"


def test_sqlite_class_start_redos_immunity():
    """ReDoS sweep for the schema-prefix skip and quoted-identifier alternatives."""
    class_start = SQLITE_RULES["class_start"]
    assert_redos_immune(class_start, 'CREATE TABLE "' + "a" * 200000, timeout_sec=3.0)
    assert class_start.search("CREATE TABLE foo (id INTEGER);")


# ==============================================================================
# ARGS (args) -- positional/named params, VALUES/IN clauses, CTE definitions.
# NOTE: test_args_extraction_strict.py had no sqlite entry at all -- args had
# zero prior test coverage before this file. This rule has ZERO capture
# groups by design (every alternative is checked via whole-match substring),
# so all assertions below check `match.group(0)`, not a captured group.
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("?", "?"),
        ("?1", "?1"),
        (":name", ":name"),
        ("@name", "@name"),
        ("$name", "$name"),
        ("VALUES(1, 2, 3)", "VALUES(1, 2, 3)"),
        ("WHERE id IN (1, 2, 3)", "IN (1, 2, 3)"),
        ("cte_name (col1, col2) AS (", "cte_name (col1, col2) AS ("),  # true-line-start CTE
        (
            "WITH cte_name (col1, col2) AS (SELECT 1, 2)",
            "WITH cte_name (col1, col2) AS (",
        ),  # inline CTE -- was a real bug, now fixed
        (
            "WITH RECURSIVE cte_name (col1, col2) AS (SELECT 1, 2)",
            "WITH RECURSIVE cte_name (col1, col2) AS (",
        ),  # inline recursive CTE
        (
            "WHERE id IN (SELECT id FROM (SELECT id FROM other))",
            "IN (SELECT id FROM (SELECT id FROM other))",
        ),  # nested subquery -- was a real bug, now fixed
    ],
    "invalid": [
        "SELECT name FROM users;",  # no args markers at all
    ],
    "pathological": [
        (
            "WITH \n RECURSIVE \n cte_name \n (col1, col2) \n AS \n (SELECT 1, 2)",
            "cte_name",
        ),  # inline recursive CTE, vertically split
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_sqlite_args_valid(payload, expected_name):
    assert_valid_match(SQLITE_RULES["args"], payload, expected_name, "sqlite.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_sqlite_args_invalid(payload):
    assert_invalid_no_match(SQLITE_RULES["args"], payload, "sqlite.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_sqlite_args_pathological(payload, expected_name):
    assert_pathological_match(SQLITE_RULES["args"], payload, expected_name, "sqlite.args")


def test_sqlite_args_nested_subquery_in_clause_regression():
    """
    Regression test for a real bug (epic #813/#836, Rule 11 shape): the
    VALUES/IN clause's `\\([^)]{0,2000}\\)` was a flat, unnested paren match
    -- a nested subquery (`IN (SELECT id FROM (SELECT id FROM other))`,
    common real SQL) truncated at the FIRST closing paren (the inner
    subquery's own) instead of covering the whole clause. Widened to the
    established one-level-nesting-safe idiom.
    """
    args = SQLITE_RULES["args"]
    m = args.search("WHERE id IN (SELECT id FROM (SELECT id FROM other))")
    assert m and m.group(0) == "IN (SELECT id FROM (SELECT id FROM other))", "nested-subquery IN clause regressed"


def test_sqlite_args_inline_with_cte_regression():
    """
    Regression test for a real bug (epic #813/#836): the CTE alternative
    required the CTE name to be at TRUE line start -- but the single most
    common way to actually write a CTE is inline, right after the `WITH`
    keyword on the same line (`WITH cte_name (col1, col2) AS (...)`), which
    this pattern never matched at all. Added an alternative anchor
    (immediately after `WITH`/`WITH RECURSIVE`) alongside the original
    line-start anchor, without introducing a new capture group (this rule
    has zero groups by design).
    """
    args = SQLITE_RULES["args"]
    assert args.groups == 0, "must stay group-free (whole-match substring convention for every alternative)"
    m1 = args.search("WITH cte_name (col1, col2) AS (SELECT 1, 2)")
    assert m1 and "cte_name" in m1.group(0), "inline WITH-prefixed CTE regressed"
    m2 = args.search("WITH RECURSIVE cte_name (col1, col2) AS (SELECT 1, 2)")
    assert m2 and "cte_name" in m2.group(0), "inline WITH RECURSIVE-prefixed CTE regressed"


def test_sqlite_args_redos_immunity():
    """ReDoS sweep for the widened IN/VALUES nesting and the new WITH-prefix anchor."""
    args = SQLITE_RULES["args"]
    assert_redos_immune(args, "IN (" + "a," * 200000, timeout_sec=3.0)
    assert_redos_immune(args, "WITH " + "a" * 200000, timeout_sec=3.0)
    assert args.search("IN (1, 2, 3)")


# ==============================================================================
# DEPENDENCY (_dependency_capture) -- ATTACH DATABASE, load_extension, dot-commands.
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("ATTACH DATABASE 'file.db' AS file;", "file.db"),  # carried-forward
        (".read schema.sql", "schema.sql"),  # carried-forward
        ("ATTACH 'file.db' AS mydb;", "file.db"),  # without DATABASE keyword
        ("load_extension('mymodule.so')", "mymodule.so"),
        (
            "ATTACH DATABASE '/path with spaces/file.db' AS mydb;",
            "/path with spaces/file.db",
        ),  # quoted path with a space -- was a real bug, now fixed
        (
            'ATTACH DATABASE "/path with spaces/file.db" AS mydb;',
            "/path with spaces/file.db",
        ),  # double-quoted variant of the same fix
        (".import data.csv mytable", "data.csv"),
    ],
    "invalid": [
        "SELECT 'ATTACH DATABASE';",  # carried-forward: keyword appears only inside a string literal
    ],
    "pathological": [
        ("load_extension \n ( \n 'crypto.so' \n )", "crypto.so"),  # carried-forward: vertical spacing
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_sqlite_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(SQLITE_RULES["_dependency_capture"], payload, expected_path, "sqlite._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_sqlite_dependency_capture_invalid(payload):
    assert_invalid_no_match(SQLITE_RULES["_dependency_capture"], payload, "sqlite._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_sqlite_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        SQLITE_RULES["_dependency_capture"], payload, expected_path, "sqlite._dependency_capture"
    )


def test_sqlite_dependency_capture_quoted_path_with_space_regression():
    """
    Regression test for a real bug (epic #813/#836): the ATTACH clause's
    optional-quote-pair idiom (`['"]?...['"]?`) excluded whitespace from the
    capture regardless of whether a quote was actually present -- the same
    bug class already confirmed for PowerShell's _dependency_capture
    (recurring class 39), but a worse "total failure" variant here: because
    the mandatory literal `AS` keyword must immediately follow the closing
    quote, a quoted path containing a space (a real, common absolute path
    shape) didn't just truncate -- it failed to match AT ALL. Fixed with
    real per-quote-style alternatives (single-quoted, double-quoted, bare).
    """
    dep = SQLITE_RULES["_dependency_capture"]
    m = dep.search("ATTACH DATABASE '/path with spaces/file.db' AS mydb;")
    captured = next((g for g in m.groups() if g), None) if m else None
    assert captured == "/path with spaces/file.db", "quoted-path-with-space capture regressed"


def test_sqlite_dependency_capture_redos_immunity():
    """ReDoS sweep for the new per-quote-style alternatives."""
    dep = SQLITE_RULES["_dependency_capture"]
    assert_redos_immune(dep, "ATTACH DATABASE '" + "a" * 200000, timeout_sec=3.0)
    assert dep.search("ATTACH DATABASE 'file.db' AS mydb;")
