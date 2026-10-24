"""#6271 (register X73): Db2 abend injection. A scenario `sql_faults` entry naming its statement by `line` and failing it
with -911 may add `"abend": "AD2Z"`: the statement fails as planned and the task then abends AD2Z (IBM: the CICS-Db2 attach's
syncpoint rollback after the deadlock fails, DFHDB2070, abend AD2Z). The end-to-end proof is cbsa-dbcrfun's
`update-deadlock-abends-ad2z` (det_port.py run); these are the unit pieces: the plan's accept / refuse table, the marker
planted after the statement's call and its translation."""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402

TABLE = "S 1 EXEC 0 0 - DBCRFUN 391\nQ UPDATE ACCOUNT SET X = 1\nS 2 EXEC 0 0 - DBCRFUN 520\nQ INSERT INTO PROCTRAN VALUES (1)\n"
CASE = {"program": "DBCRFUN", "scenarios": []}
FAULT = {"program": "DBCRFUN", "line": 391, "sqlcode": -911, "abend": "AD2Z"}


def _scenario(**kw):
    return {"name": "s", "sql_faults": [{**FAULT, **kw}]}


def test_an_ad2z_abend_is_planned_beside_its_sql_fault():
    sc = _scenario()
    assert ec.sql_fault_plan(CASE, sc, TABLE) == ["DBCRFUN 391 1 -911 40001"]
    assert ec.fault_lines(sc) == ["SQL DBCRFUN:391 1 -1 0 AD2Z"]


def test_nth_follows_the_sql_fault():
    sc = _scenario(nth=2)
    assert ec.sql_fault_plan(CASE, sc, TABLE) == ["DBCRFUN 391 2 -911 40001"]
    assert ec.fault_lines(sc) == ["SQL DBCRFUN:391 2 -1 0 AD2Z"]


def test_a_plan_with_no_abend_adds_no_cics_line():
    sc = {"name": "s", "sql_faults": [{"program": "DBCRFUN", "line": 391, "sqlcode": -911}]}
    ec.sql_fault_plan(CASE, sc, TABLE)
    assert ec.fault_lines(sc) == []


@pytest.mark.parametrize(
    "bad",
    [
        {"abend": "ASRA"},  # no source ties another code to a Db2 statement
        {"abend": "ad2z"},
        {"sqlcode": -913},  # only the deadlock's rollback path is sourced
        {"sqlcode": 100},
        {"line": 999},  # names no statement
    ],
)
def test_every_other_sql_abend_plan_is_refused(bad):
    with pytest.raises(ec.Unsupported):
        ec.sql_fault_plan(CASE, _scenario(**bad), TABLE)


def test_a_statement_selected_by_table_and_verb_is_refused():
    sc = {"name": "s", "sql_faults": [{"table": "ACCOUNT", "verb": "UPDATE", "sqlcode": -911, "abend": "AD2Z"}]}
    with pytest.raises(ec.Unsupported):
        ec.sql_fault_plan(CASE, sc, TABLE)


PRECOMPILED = (
    "           MOVE 0001 TO GG-SQL-ID\n"
    "           MOVE RETURN-CODE TO GG-SQL-RC\n"
    "           CALL 'GGSQL' USING GG-SQL-ID SQLCA\n"
    "           MOVE GG-SQL-RC TO RETURN-CODE.\n"
    "           MOVE 0002 TO GG-SQL-ID\n"
    "           MOVE RETURN-CODE TO GG-SQL-RC\n"
    "           CALL 'GGSQL' USING GG-SQL-ID SQLCA\n"
    "           MOVE GG-SQL-RC TO RETURN-CODE.\n"
    "           EXEC CICS HANDLE ABEND LABEL(AH010) END-EXEC.\n"
)


def test_the_marker_follows_only_the_planned_statement_before_the_return_code_restore():
    case = {**CASE, "scenarios": [_scenario()]}
    out = ec.mark_sql_abends(case, PRECOMPILED, TABLE, "DBCRFUN").split("\n")
    mark = "           EXEC CICS GGSQLAB NAME('DBCRFUN:391') END-EXEC"
    assert out.count(mark) == 1
    at = out.index(mark)
    assert out[at - 1].startswith("           CALL 'GGSQL'")
    assert out[at + 1] == "           MOVE GG-SQL-RC TO RETURN-CODE."  # the sentence still ends there


def test_no_planned_abend_leaves_the_source_alone():
    assert ec.mark_sql_abends(CASE, PRECOMPILED, TABLE, "DBCRFUN") == PRECOMPILED


def test_a_program_with_no_handle_abend_is_refused():
    case = {**CASE, "scenarios": [_scenario()]}
    with pytest.raises(ec.Unsupported):
        ec.mark_sql_abends(case, PRECOMPILED.replace("HANDLE ABEND", "HANDLE AID"), TABLE, "DBCRFUN")


def test_the_marker_calls_the_stub_and_takes_the_exit():
    lines = ec.translate_command("GGSQLAB NAME('DBCRFUN:391')", labels=["AH010"])
    assert lines[:2] == ["MOVE 0 TO GG-GOTO", "MOVE 'DBCRFUN:391' TO GG-FLAGS"]
    assert "CALL 'GGCSQLAB' USING GG-CICS" in lines
    assert lines[-6:] == ["GO TO", "    AH010", "    DEPENDING ON GG-GOTO", "IF GG-GOTO < 0", "    GOBACK", "END-IF"]
