"""
PostgreSQL dialect (#5622): chosen over db2_sql / sqlite by content evidence, and its function / type /
DO-block shapes extracted through Mode E with dollar-quoted bodies kept whole. Every snippet is a real
PostgreSQL shape. Routing runs through the real language lens in both collision directions.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

PG = LANGUAGE_DEFINITIONS["postgresql"]
PG_RULES = PG["rules"]

PLPGSQL_FN = (
    "CREATE OR REPLACE FUNCTION public.add_one(x int) RETURNS int AS $$\n"
    "BEGIN\n"
    "  IF x > 1 THEN RETURN x + 1; END IF;\n"
    "  RETURN x::int;\n"
    "END;\n"
    "$$ LANGUAGE plpgsql;\n"
)
SQL_FN_TAGGED = "CREATE FUNCTION sq(a int) RETURNS int LANGUAGE sql AS $body$\n  SELECT a * a;\n  SELECT 1;\n$body$;\n"
RETURNS_TABLE_FN = (
    "CREATE FUNCTION recent(n int) RETURNS TABLE(id int, name text) AS $fn$\n"
    "  SELECT id, name FROM t LIMIT n;\n"
    "$fn$ LANGUAGE sql STABLE;\n"
)
PROCEDURE = "CREATE PROCEDURE bump() LANGUAGE sql AS $$ UPDATE t SET n = n + 1; $$;\n"
DO_BLOCK = "DO $$ BEGIN PERFORM 1; PERFORM 2; END $$;\n"
ENUM_TYPE = "CREATE TYPE mood AS ENUM ('sad', 'ok');\n"
COMPOSITE_TYPE = "CREATE TYPE pair AS (a int, b int);\n"

DB2_PROC = "CREATE PROCEDURE HR.RAISE_PAY (IN P_ID INTEGER)\nLANGUAGE SQL\nBEGIN\n  UPDATE HR.EMP SET X = 1;\nEND;\n"
SQLITE_SCRIPT = (
    "PRAGMA foreign_keys = ON;\n"
    "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);\n"
    "INSERT INTO users VALUES (1, 'alice');\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("postgresql", LANGUAGE_DEFINITIONS).splice(content, "")


def _fn(result: dict, name: str) -> dict:
    return next(f for f in result["functions"] if f["name"] == name)


# --- routing ------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [PLPGSQL_FN, SQL_FN_TAGGED, RETURNS_TABLE_FN, PROCEDURE, DO_BLOCK, ENUM_TYPE],
    ids=["plpgsql", "sql_tagged", "returns_table", "procedure", "do_block", "enum"],
)
def test_postgres_content_beats_db2_and_sqlite_for_each_shape(content):
    # `LANGUAGE sql` sits in db2_sql's own discriminator: postgresql must be tried first.
    assert _route("schema.sql", content) == "postgresql"


def test_postgresql_precedes_db2_sql_in_the_registry():
    order = list(LANGUAGE_DEFINITIONS)
    assert order.index("postgresql") < order.index("db2_sql")


def test_db2_and_sqlite_files_are_not_claimed_by_postgresql():
    assert not PG["internal_discriminator"].search(DB2_PROC)
    assert not PG["internal_discriminator"].search(SQLITE_SCRIPT)
    assert _route("proc.sql", DB2_PROC) == "db2_sql"
    assert _route("app.sql", SQLITE_SCRIPT) == "sqlite"


# --- extraction ---------------------------------------------------------------


def test_plpgsql_function_spans_its_dollar_body():
    result = _splice(PLPGSQL_FN)
    assert [f["name"] for f in result["functions"]] == ["add_one"]
    fn = _fn(result, "add_one")
    assert (fn["start_line"], fn["end_line"]) == (1, 6)


def test_tagged_sql_function_is_not_cut_at_inner_semicolons():
    result = _splice(SQL_FN_TAGGED)
    assert [f["name"] for f in result["functions"]] == ["sq"]
    assert _fn(result, "sq")["end_line"] == 4


def test_returns_table_function_is_one_function():
    assert [f["name"] for f in _splice(RETURNS_TABLE_FN)["functions"]] == ["recent"]


def test_create_procedure_is_a_function():
    assert [f["name"] for f in _splice(PROCEDURE)["functions"]] == ["bump"]


def test_do_block_is_a_closure_and_not_a_named_function():
    assert PG_RULES["closures"].search(DO_BLOCK)
    assert not PG_RULES["func_start"].search(DO_BLOCK)


def test_create_type_is_a_named_class():
    assert {c["name"] for c in _splice(ENUM_TYPE + COMPOSITE_TYPE)["classes"]} == {"mood", "pair"}


def test_every_function_in_a_mixed_file_is_counted():
    result = _splice(PLPGSQL_FN + "\n" + SQL_FN_TAGGED + "\n" + PROCEDURE + "\n" + DO_BLOCK)
    assert {f["name"] for f in result["functions"]} >= {"add_one", "sq", "bump"}


# --- ReDoS --------------------------------------------------------------------

_N = 20000


@pytest.mark.parametrize(
    ("signature", "payload"),
    [
        ("func_start", "CREATE FUNCTION " + "a." * _N),
        ("func_start", "CREATE OR REPLACE " * _N),
        ("func_start", 'CREATE FUNCTION "' + "a" * _N),
        ("class_start", "CREATE TYPE " + "a" * _N),
        ("class_start", "CREATE " + "UNLOGGED " * _N),
        ("closures", "DO " + "$" * _N),
        ("closures", "DO LANGUAGE " + "a" * _N),
    ],
    ids=lambda v: v if len(v) <= 30 else f"{v[:12].strip()}...x{len(v)}",
)
def test_postgresql_redos_immunity(signature, payload):
    assert_redos_immune(PG_RULES[signature], payload, timeout_sec=3.0)


def test_discriminator_is_redos_immune():
    for payload in ("AS " + "$" * _N, "CREATE TYPE " + "a " * _N, "x" + "::" * _N, "RETURNS " * _N):
        assert_redos_immune(PG["internal_discriminator"], payload, timeout_sec=3.0)


def test_a_plain_script_without_postgres_evidence_is_not_claimed_by_postgresql():
    plain = "DROP TABLE IF EXISTS user;\nCREATE TABLE user (id INTEGER PRIMARY KEY, name TEXT NOT NULL);\n"
    # Lexical scoring among the pre-existing SQL dialects is unchanged: db2_sql/sqlite decide it, as before.
    assert _route("schema.sql", plain) in {"sqlite", "db2_sql"}


def test_postgresql_is_not_a_neighbourhood_gravity_candidate_for_the_shared_extensions(tmp_path):
    # A third claimant would dilute sqlite's dominance below the threshold and tip plain scripts to a lexical
    # vote: the proof-only language is dropped from the gravity candidate pool (#5622).
    plain = "CREATE TABLE a (id INTEGER PRIMARY KEY, name TEXT);\n"
    for i in range(4):
        (tmp_path / f"t{i}.sql").write_text(plain)
    lens = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    seen: list[str] = []
    real = lens._resolve_by_sibling_content

    def spy(file_path, ext, candidates):
        seen.extend(candidates)
        return real(file_path, ext, candidates)

    lens._resolve_by_sibling_content = spy  # type: ignore[method-assign]
    lens._evaluate_ecosystem_gravity(tmp_path / "t0.sql", ".sql", {".sql": 4})
    assert seen
    assert "postgresql" not in seen
    assert "sqlite" in seen


# --- sibling vote for files with no Postgres-only evidence of their own (#5622 slice 2) ---
PLAIN_DDL = "CREATE TABLE a (id INTEGER PRIMARY KEY, name TEXT);\n"


def _route_in_dir(folder: Path, name: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).inspect(
        folder / name, (folder / name).read_text(), ext_tally={".sql": 9}
    )["lang_id"]


@pytest.mark.parametrize("ext", [".sql", ".ddl", ".dml"])
def test_plain_script_follows_two_proving_postgres_siblings(tmp_path, ext):
    (tmp_path / f"f1{ext}").write_text(PLPGSQL_FN)
    (tmp_path / f"f2{ext}").write_text(SQL_FN_TAGGED)
    (tmp_path / f"plain{ext}").write_text(PLAIN_DDL)
    assert _route_in_dir(tmp_path, f"plain{ext}") == "postgresql"


def test_one_proving_sibling_does_not_relabel_the_folder(tmp_path):
    (tmp_path / "f1.sql").write_text(PLPGSQL_FN)
    (tmp_path / "plain.sql").write_text(PLAIN_DDL)
    assert _route_in_dir(tmp_path, "plain.sql") in {"sqlite", "db2_sql"}


def test_postgres_siblings_do_not_capture_a_folder_of_proven_db2(tmp_path):
    for i in range(3):
        (tmp_path / f"d{i}.sql").write_text(DB2_PROC)
    (tmp_path / "f1.sql").write_text(PLPGSQL_FN)
    (tmp_path / "f2.sql").write_text(SQL_FN_TAGGED)
    (tmp_path / "plain.sql").write_text(PLAIN_DDL)
    assert _route_in_dir(tmp_path, "plain.sql") in {"sqlite", "db2_sql"}  # 2 of 5 proving votes < 70%


def test_proving_siblings_in_another_folder_do_not_vote(tmp_path):
    (tmp_path / "pg").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "pg" / "f1.sql").write_text(PLPGSQL_FN)
    (tmp_path / "pg" / "f2.sql").write_text(SQL_FN_TAGGED)
    (tmp_path / "other" / "plain.sql").write_text(PLAIN_DDL)
    assert _route_in_dir(tmp_path / "other", "plain.sql") in {"sqlite", "db2_sql"}
