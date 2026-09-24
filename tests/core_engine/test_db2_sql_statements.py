"""#3446: embedded SQL statements -- which tables a program reads and writes.

Each case is a shape from the pinned corpora (CBSA, CardDemo) or DB2's grammar."""

from gitgalaxy.core.db2_sql_statements import extract_sql_statements


def _rows(code: str, dialect: str = "cobol"):
    return [
        (r["ordinal"], r["verb"], r["table"], r["access"], r["cursor"]) for r in extract_sql_statements(code, dialect)
    ]


def test_select_insert_update_delete_name_their_tables():
    code = (
        "           EXEC SQL SELECT ACCOUNT_NUMBER INTO :HV-ACC FROM ACCOUNT WHERE X = :WS-X END-EXEC.\n"
        "           EXEC SQL INSERT INTO PROCTRAN (A) VALUES (:HV-A) END-EXEC.\n"
        "           EXEC SQL UPDATE CARDDEMO.TRANSACTION_TYPE SET TR_DESC = :D WHERE TR_TYPE = :T END-EXEC.\n"
        "           EXEC SQL DELETE FROM CARDDEMO.TRANSACTION_TYPE WHERE TR_TYPE = :T END-EXEC.\n"
    )
    assert _rows(code) == [
        (1, "SELECT", "ACCOUNT", "read", None),
        (2, "INSERT", "PROCTRAN", "insert", None),
        (3, "UPDATE", "CARDDEMO.TRANSACTION_TYPE", "update", None),
        (4, "DELETE", "CARDDEMO.TRANSACTION_TYPE", "delete", None),
    ]


def test_cursor_lifecycle_is_kept_and_named():
    code = (
        "           EXEC SQL DECLARE ACC-CURSOR CURSOR WITH HOLD FOR\n"
        "                SELECT A FROM ACCOUNT WHERE B = :WS-B FOR FETCH ONLY\n"
        "           END-EXEC.\n"
        "           EXEC SQL OPEN ACC-CURSOR END-EXEC.\n"
        "           EXEC SQL FETCH NEXT FROM ACC-CURSOR INTO :HV-A END-EXEC.\n"
        "           EXEC SQL CLOSE ACC-CURSOR END-EXEC.\n"
    )
    assert _rows(code) == [
        (1, "DECLARE CURSOR", "ACCOUNT", "read", "ACC-CURSOR"),
        (2, "OPEN", None, None, "ACC-CURSOR"),
        (3, "FETCH", None, None, "ACC-CURSOR"),
        (4, "CLOSE", None, None, "ACC-CURSOR"),
    ]


def test_joins_from_lists_subqueries_and_merge():
    code = (
        "           EXEC SQL SELECT 1 INTO :X FROM A.T1 X, T2 AS Y JOIN T3 ON X.K = T3.K\n"
        "              WHERE X.K IN (SELECT K FROM T4) END-EXEC.\n"
        "           EXEC SQL INSERT INTO HIST SELECT * FROM LIVE END-EXEC.\n"
        "           EXEC SQL MERGE INTO TGT USING SRC ON 1 = 1 WHEN MATCHED THEN UPDATE SET A = 1 END-EXEC.\n"
    )
    rows = _rows(code)
    assert [(r[2], r[3]) for r in rows if r[0] == 1] == [
        ("A.T1", "read"),
        ("T2", "read"),
        ("T3", "read"),
        ("T4", "read"),
    ]
    assert [(r[2], r[3]) for r in rows if r[0] == 2] == [("HIST", "insert"), ("LIVE", "read")]
    assert [(r[2], r[3]) for r in rows if r[0] == 3] == [("TGT", "merge"), ("SRC", "read")]


def test_includes_declare_tables_whenever_and_literals_are_not_statements():
    code = (
        "           EXEC SQL INCLUDE SQLCA END-EXEC.\n"
        "           EXEC SQL DECLARE ACCOUNT TABLE ( A CHAR(1) ) END-EXEC.\n"
        "           EXEC SQL WHENEVER SQLERROR GOTO ERR END-EXEC.\n"
        "           DISPLAY 'EXEC SQL SELECT X FROM FAKE END-EXEC'.\n"
        "           EXEC SQL SELECT A INTO :A FROM REAL WHERE B = 'FROM NOTME' END-EXEC.\n"
        "           EXEC SQL COMMIT END-EXEC.\n"
    )
    assert _rows(code) == [(1, "SELECT", "REAL", "read", None), (2, "COMMIT", None, None, None)]


def test_host_variables_and_sequence_fields():
    code = (
        "030400     EXEC SQL SELECT A INTO :HV-A :HV-IND FROM T                  03040000\n"
        "030500        WHERE K = :WS-KEY END-EXEC.                               03050000\n"
    )
    (row,) = extract_sql_statements(code)
    assert (row["table"], row["host_variables"], row["line"]) == ("T", "HV-A,HV-IND,WS-KEY", 1)


def test_pli_statements_end_at_the_semicolon():
    code = " EXEC SQL SELECT DEPTNAME INTO :NAME FROM DSN8C10.DEPT WHERE DEPTNO = :NO;\n X = 1;\n"
    assert _rows(code, "pli") == [(1, "SELECT", "DSN8C10.DEPT", "read", None)]


def test_an_unterminated_statement_reads_nothing():
    assert extract_sql_statements("           EXEC SQL SELECT A FROM T\n" * 3) == []
