"""
SQL routine call edges (#5635): a routine body's calls to another routine -- `CALL p(...)` (Db2, PL/pgSQL),
`PERFORM f(...)`, `SELECT f(...)`, `x := f(...)`, `FROM f(...)`, a trigger's `EXECUTE FUNCTION f()` -- land in
`calls_out_to` for db2_sql and postgresql; built-ins, type constructors, clause words and DDL heads never do.
SQLite has no stored routines (its units are statement buckets), so its calls_out stays unsupported.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PG_BODY = """\
CREATE OR REPLACE FUNCTION doom_a(x int, n numeric(10,2)) RETURNS int AS $$
DECLARE v varchar(20); r int;
BEGIN
  r := public.doom_b(x) + COALESCE(x, 0) + SUM(x) + ABS(n)::int;
  PERFORM doom_c(x);
  CALL doom_p(x);
  SELECT doom_d(x) INTO r FROM doom_t WHERE x IN (1, 2);
  INSERT INTO log_t (a, b) VALUES (1, 2);
  RETURN (SELECT count(*) FROM doom_e(x) OVER (PARTITION BY x));
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION doom_b(x int) RETURNS int AS $$
BEGIN RETURN x; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg BEFORE INSERT ON t FOR EACH ROW EXECUTE FUNCTION trg_fn();
"""

DB2_BODY = """\
CREATE PROCEDURE HR.RAISE_PAY (IN P_ID INTEGER, IN AMT DECIMAL(9,2))
LANGUAGE SQL
BEGIN
  DECLARE V_NAME VARCHAR(40);
  CALL HR.AUDIT_LOG(P_ID);
  CALL NOTIFY_ONE;
  SET V_NAME = UPPER(HR.FULL_NAME(P_ID));
  INSERT INTO HR.EMP_LOG (ID, NAME) VALUES (P_ID, COALESCE(V_NAME, 'x'));
  SELECT TAX_OF(AMT), MAX(AMT) FROM HR.EMP WHERE ID IN (P_ID);
END;
"""


def _calls(lang: str, src: str) -> dict[str, list[str]]:
    result = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(src, "")
    return {f["name"]: f["calls_out_to"] for f in result["functions"]}


def test_postgresql_function_call_shapes():
    calls = _calls("postgresql", PG_BODY)
    # function syntax (schema-qualified, bare name kept), PERFORM, CALL, SELECT, FROM f(...)
    assert calls["doom_a"] == ["doom_b", "doom_c", "doom_p", "doom_d", "doom_e"]
    assert calls["doom_b"] == []


def test_postgresql_trigger_execute_function_is_a_call():
    assert _calls("postgresql", PG_BODY)["trg"] == ["trg_fn"]


def test_db2_call_and_function_shapes():
    calls = _calls("db2_sql", DB2_BODY)
    # CALL with and without a parenthesis, a qualified scalar function, a user function in SELECT
    assert calls["RAISE_PAY"] == ["AUDIT_LOG", "NOTIFY_ONE", "FULL_NAME", "TAX_OF"]


def test_db2_script_with_postgres_shapes_also_records_calls():
    # a `.sql` file the lens leaves on db2_sql still gets its edges (the sqldoom mislabel, #5622)
    assert _calls("db2_sql", PG_BODY)["doom_a"] == ["doom_b", "doom_c", "doom_p", "doom_d", "doom_e"]


@pytest.mark.parametrize("lang", ["db2_sql", "postgresql"])
@pytest.mark.parametrize(
    "builtin",
    ["COALESCE(a, b)", "SUM(a)", "COUNT(*)", "UPPER(a)", "NUMERIC(10, 2)", "VARCHAR(20)", "NOW()", "CAST(a AS int)"],
)
def test_builtins_and_types_are_not_calls(lang, builtin):
    src = f"CREATE FUNCTION f1(a int) RETURNS int AS $$ BEGIN RETURN {builtin}; END; $$ LANGUAGE sql;\n"
    assert _calls(lang, src) == {"f1": []}


@pytest.mark.parametrize("lang", ["db2_sql", "postgresql"])
def test_ddl_heads_are_not_calls(lang):
    src = (
        "CREATE FUNCTION f2() RETURNS int AS $$ BEGIN\n"
        "  CREATE TABLE tmp_t (id int);\n  INSERT INTO tmp_t (id) VALUES (1);\n"
        "  DROP FUNCTION old_fn(int);\nEND; $$ LANGUAGE sql;\n"
    )
    assert _calls(lang, src) == {"f2": []}


def test_sqlite_has_no_routines_to_record():
    # SQLite statements are not named routines: calls_out is declared unsupported on purpose.
    assert LANGUAGE_DEFINITIONS["sqlite"]["rules"]["calls_out"] is None
    assert all(not c for c in _calls("sqlite", PG_BODY).values())
