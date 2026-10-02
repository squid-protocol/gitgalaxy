"""The Db2 equivalence harness's precompiler (tests/tools/equivalence_sql.py): EXEC SQL to CALL 'GGSQL' and the
statement table ggsql.c reads -- each host variable's Db2 type as the Db2 precompiler declares it for COBOL. No
database needed: the statements' meaning is proven by the Db2 cases (equivalence.py with a "db2" section)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_sql as Q  # noqa: E402


def program(data: list[str], proc: list[str]) -> str:
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. SQLT.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION.", "           EXEC SQL INCLUDE SQLCA END-EXEC.",
             *[f"       {x}" for x in data], "       PROCEDURE DIVISION.", *[f"           {x}" for x in proc],
             "           GOBACK."]  # fmt: skip
    return "\n".join(lines) + "\n"


DATA = [
    "01 HV-TYPE PIC X(2).",
    "01 HV-DESC.",
    "   49 HV-DESC-LEN PIC S9(4) COMP.",
    "   49 HV-DESC-TEXT PIC X(50).",
    "01 HV-AMT PIC S9(7)V99 COMP-3.",
    "01 HV-COUNT PIC S9(9) COMP.",
    "01 HV-ZONED PIC 9(4).",
    "01 HV-IND PIC S9(4) COMP.",
    "01 HV-ROW.",
    "   05 HV-ROW-TYPE PIC X(2).",
    "   05 HV-ROW-AMT PIC S9(5)V99 COMP-3.",
]


def precompile(proc: list[str], data: list[str] = DATA, tmp: Path | None = None) -> tuple[str, str]:
    return Q.precompile(program(data, proc), [], Path("SQLT.cbl"))


def test_insert_binds_each_host_variable_as_its_db2_type():
    prog, table = precompile(["EXEC SQL INSERT INTO T (A, B, C, D, E)", "  VALUES (:HV-TYPE, :HV-DESC, :HV-AMT,",
                              "  :HV-COUNT, :HV-ZONED) END-EXEC"])  # fmt: skip
    lines = table.splitlines()
    assert lines[0] == "S 1 EXEC 5 0 -"
    # CHAR(2); VARCHAR(50) from the 49-level pair; DECIMAL(9,2) packed; INTEGER binary; DECIMAL(4,0) zoned
    assert lines[1:6] == ["I 0 X 2 0 0 0 -1", "I 1 V 50 0 0 0 -1", "I 2 P 5 9 2 1 -1", "I 3 B 4 9 0 1 -1",
                          "I 4 Z 4 4 0 0 -1"]  # fmt: skip
    assert lines[6] == "Q INSERT INTO T (A, B, C, D, E) VALUES (?, ?, ?, ?, ?)"
    assert "CALL 'GGSQL' USING GG-SQL-ID SQLCA" in prog and "EXEC SQL" not in prog.split("PROCEDURE DIVISION.")[1]


def test_select_into_a_host_structure_with_an_indicator():
    _, table = precompile(["EXEC SQL SELECT A, B", "  INTO :HV-ROW-TYPE:HV-IND, :HV-ROW-AMT",
                           "  FROM T WHERE A = :HV-TYPE", "END-EXEC"])  # fmt: skip
    lines = table.splitlines()
    assert lines[0] == "S 1 SELECT1 1 2 -"
    assert lines[1] == "I 3 X 2 0 0 0 -1"  # the WHERE's host variable (arguments: the INTO list first)
    assert lines[2:4] == ["O 0 X 2 0 0 0 1", "O 2 P 4 7 2 1 -1"]  # the indicator is argument 1
    assert lines[4] == "Q SELECT A, B FROM T WHERE A = ?"


def test_a_host_structure_expands_to_its_members():
    _, table = precompile(["EXEC SQL SELECT A, B INTO :HV-ROW FROM T END-EXEC"])
    assert [ln for ln in table.splitlines() if ln.startswith("O")] == ["O 0 X 2 0 0 0 -1", "O 1 P 4 7 2 1 -1"]


def test_a_cursor_runs_its_select_at_open_and_fetches_into_host_variables():
    _, table = precompile(["EXEC SQL DECLARE C1 CURSOR FOR SELECT A, B FROM T", "  WHERE A >= :HV-TYPE ORDER BY A",
                           "END-EXEC", "EXEC SQL OPEN C1 END-EXEC", "EXEC SQL FETCH C1",
                           "  INTO :HV-ROW-TYPE, :HV-ROW-AMT END-EXEC", "EXEC SQL CLOSE C1 END-EXEC"])  # fmt: skip
    lines = table.splitlines()
    assert lines[0] == "S 1 OPEN 1 0 C1" and lines[2] == "Q SELECT A, B FROM T WHERE A >= ? ORDER BY A"
    assert lines[3] == "S 2 FETCH 0 2 C1" and lines[4:6] == ["O 0 X 2 0 0 0 -1", "O 1 P 4 7 2 1 -1"]
    assert lines[7] == "S 3 CLOSE 0 0 C1"


def test_return_code_is_kept_around_the_stub_call():
    prog, _ = precompile(["EXEC SQL DELETE FROM T WHERE A = :HV-TYPE END-EXEC."])
    body = [ln.strip() for ln in prog.split("PROCEDURE DIVISION.")[1].splitlines() if ln.strip()]
    assert body[:5] == ["MOVE 0001 TO GG-SQL-ID", "MOVE RETURN-CODE TO GG-SQL-RC",
                        "CALL 'GGSQL' USING GG-SQL-ID SQLCA", "HV-TYPE", "MOVE GG-SQL-RC TO RETURN-CODE."]  # fmt: skip


@pytest.mark.parametrize(
    ("proc", "why"),
    [
        (["EXEC SQL WHENEVER SQLERROR GO TO X END-EXEC"], "WHENEVER"),
        (["EXEC SQL UPDATE T SET A = 1 WHERE CURRENT OF C1 END-EXEC"], "CURRENT OF"),
        (["EXEC SQL PREPARE S1 FROM :HV-DESC END-EXEC"], "PREPARE"),
        (["EXEC SQL INSERT INTO T VALUES (:NOT-DECLARED) END-EXEC"], "not declared"),
    ],
)  # fmt: skip
def test_a_form_not_modelled_is_refused_by_name(proc, why):
    with pytest.raises(Q.Unsupported, match=why):
        precompile(proc)


def test_set_assigns_a_values_row_to_host_variables():
    """GenApp's SET :DB2-CUSTOMERNUM-INT = IDENTITY_VAL_LOCAL(): one row of VALUES into the host variables."""
    _, table = precompile(["EXEC SQL SET :HV-COUNT = IDENTITY_VAL_LOCAL() END-EXEC",
                           "EXEC SQL SET (:HV-TYPE, :HV-AMT) =", "  ('AB', COALESCE(:HV-ZONED, 0))",
                           "END-EXEC"])  # fmt: skip
    lines = table.splitlines()
    assert lines[:3] == ["S 1 SELECT1 0 1 -", "O 0 B 4 9 0 1 -1", "Q VALUES (IDENTITY_VAL_LOCAL())"]
    assert lines[3] == "S 2 SELECT1 1 2 -" and lines[-1] == "Q VALUES ('AB', COALESCE(?, 0))"


def test_set_of_a_special_register_is_refused():
    with pytest.raises(Q.Unsupported, match="SET"):
        precompile(["EXEC SQL SET CURRENT SQLID = 'X' END-EXEC"])
