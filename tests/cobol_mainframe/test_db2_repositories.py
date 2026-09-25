"""#3618: embedded DB2 -> Spring JDBC repositories.

The engine now keeps each embedded SQL statement's text (sql_statement_data.statement_text);
GalaxyIR.db2_tables joins each table's DECLARE to every statement against it; the Db2Forge
turns that into a row class per DECLAREd table and a repository per table whose methods run
the program's own SQL. A real scan backs the end-to-end test.
"""

import shutil
import sqlite3
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_db2_forge import sql_java_type, to_jdbc

DCLACCT = """\
           EXEC SQL DECLARE ACCOUNT TABLE
           ( ACCT_ID                        CHAR(11) NOT NULL,
             ACCT_BAL                       DECIMAL(11, 2),
             ACCT_OPENED                    DATE
           ) END-EXEC.
       01  DCLACCOUNT.
           10 ACCT-ID             PIC X(11).
           10 ACCT-BAL            PIC S9(9)V99 COMP-3.
           10 ACCT-OPENED         PIC X(10).
"""

ACCTDB = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTDB.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE DCLACCT END-EXEC.
       01  WS-ID                  PIC X(11).
       01  WS-BAL                 PIC S9(9)V99 COMP-3.
       01  WS-BAL-IND             PIC S9(4) COMP.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC SQL SELECT ACCT_BAL INTO :WS-BAL :WS-BAL-IND
                FROM ACCOUNT WHERE ACCT_ID = :WS-ID
           END-EXEC.
           EXEC SQL INSERT INTO ACCOUNT (ACCT_ID, ACCT_BAL)
                VALUES (:WS-ID, :WS-BAL)
           END-EXEC.
           EXEC SQL DECLARE ACC-CUR CURSOR FOR
                SELECT ACCT_ID FROM ACCOUNT WHERE ACCT_BAL > :WS-BAL
           END-EXEC.
           EXEC SQL OPEN ACC-CUR END-EXEC.
           EXEC SQL FETCH ACC-CUR INTO :WS-ID END-EXEC.
           EXEC SQL CLOSE ACC-CUR END-EXEC.
           GOBACK.
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("db2_repos")
    repo = base / "estate"
    for rel, text in {"cbl/ACCTDB.cbl": ACCTDB, "cpy/DCLACCT.cpy": DCLACCT}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_to_jdbc_names_parameters_and_drops_the_singleton_into():
    sql, params, notes = to_jdbc(
        "SELECT ACCT_BAL INTO :WS-BAL :WS-BAL-IND FROM ACCOUNT WHERE ACCT_ID = :WS-ID", "SELECT"
    )
    assert sql == "SELECT ACCT_BAL FROM ACCOUNT WHERE ACCT_ID = :wsId"
    assert params == [("WS-ID", "wsId")] and "INTO host variables" in notes[0]
    sql, params, _ = to_jdbc("INSERT INTO ACCOUNT (A, B) VALUES (:WS-ID, :WS-BAL:WS-BAL-IND)", "INSERT")
    assert sql == "INSERT INTO ACCOUNT (A, B) VALUES (:wsId, :wsBal)"  # INSERT INTO is not a host INTO
    sql, _, _ = to_jdbc(
        "DECLARE C1 INSENSITIVE SCROLL CURSOR WITH HOLD FOR SELECT A FROM T WHERE B = :X", "DECLARE CURSOR"
    )
    assert sql == "SELECT A FROM T WHERE B = :x"
    _, _, notes = to_jdbc("UPDATE T SET A = :A WHERE CURRENT OF C1", "UPDATE")
    assert any("WHERE CURRENT OF" in n for n in notes)


@pytest.mark.parametrize(
    "sql_type, java",
    [("CHAR", "String"), ("VARCHAR", "String"), ("DECIMAL", "BigDecimal"), ("INTEGER", "Integer"),
     ("BIGINT", "Long"), ("DATE", "LocalDate"), ("TIMESTAMP WITH TIME ZONE", "LocalDateTime"), ("BLOB", "byte[]"),
     ("SOMETHING ODD", "String")],
)  # fmt: skip
def test_sql_types_map_to_java(sql_type, java):
    assert sql_java_type(sql_type) == java


def test_db2_tables_join_the_declare_to_every_statement(scanned):
    _, db = scanned
    (acct,) = [t for t in load_galaxy_ir(db).db2_tables() if t["table"] == "ACCOUNT"]
    assert acct["declared_in"] == "cpy/DCLACCT.cpy"
    assert [(c["name"], c["sql_type"], c["nullable"]) for c in acct["columns"]] == [
        ("ACCT_ID", "CHAR", False),
        ("ACCT_BAL", "DECIMAL", True),
        ("ACCT_OPENED", "DATE", True),
    ]
    verbs = [(s["verb"], s["access"]) for s in acct["statements"]]
    assert verbs == [("SELECT", "read"), ("INSERT", "insert"), ("DECLARE CURSOR", "read")]
    cursor = acct["statements"][2]
    assert [u["verb"] for u in cursor["cursor_use"]] == ["OPEN", "FETCH", "CLOSE"]
    assert cursor["statement"].startswith("DECLARE ACC-CUR CURSOR FOR SELECT ACCT_ID FROM ACCOUNT")


def test_a_pre_3618_db_loads_without_statement_text(scanned, tmp_path):
    _, db = scanned
    old = tmp_path / "old.db"
    shutil.copy(db, old)
    with sqlite3.connect(old) as conn:
        conn.execute("ALTER TABLE sql_statement_data DROP COLUMN statement_text")
    stmts = load_galaxy_ir(old).files["cbl/ACCTDB.cbl"].sql_statements
    assert stmts and all(s.statement is None for s in stmts)


def test_the_repository_runs_the_programs_own_sql(scanned, tmp_path):
    from gitgalaxy import cobol_to_java_controller

    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    with patch("sys.argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        cobol_to_java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    src = java / "src/main/java/com/gitgalaxy/modernized"
    row = (src / "dto/db2/AccountRow.java").read_text(encoding="utf-8")
    assert "private String acctId;" in row and "private BigDecimal acctBal;" in row
    assert "import java.time.LocalDate;" in row and "private LocalDate acctOpened;" in row
    rep = (src / "repository/db2/AccountRepository.java").read_text(encoding="utf-8")
    assert "public Map<String, Object> selectL11Acctdb(Map<String, ?> params) {" in rep
    assert "SELECT ACCT_BAL FROM ACCOUNT WHERE ACCT_ID = :wsId" in rep
    assert "public int insertL14Acctdb(Map<String, ?> params) {" in rep
    assert "public List<Map<String, Object>> cursorAccCurL17Acctdb(Map<String, ?> params) {" in rep
    assert "The cursor's OPEN at line 20, FETCH at line 21, CLOSE at line 22." in rep
    assert "TODO: this SQL is DB2's; the configured database is postgresql" in rep
    service = (src / "service/AcctdbService.java").read_text(encoding="utf-8")
    assert "private final AccountRepository accountRepository;" in service
    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "DB2 tables (#3618)       : 1 repositories (1 with DECLAREd row classes), 3 statements as written" in audit
