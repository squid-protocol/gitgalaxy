"""
IBM DB2 SQL / SQL PL strict structural-signature coverage (#2511, epic #2516). See
gitgalaxy/standards/how_to_add_a_language.md's Strict Testing & Crucible Verification
Framework for the methodology -- an adversarial pass against the signatures registered
in languages/db2_sql.py, not a continuation of the generation work.

Every snippet is a real DB2 shape: the DSN8 sample-database DDL shipped with Db2 for
z/OS (tablespaces, EBCDIC CCSIDs, STOGROUP/PRIQTY storage clauses), SQL PL stored
procedures in the IBM documentation's shape, and CLP scripts. The `.sql`/`.ddl`/`.dml`
extension collision with sqlite (this profile's whole reason to exist) gets its own
routing section below.
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

DB2 = LANGUAGE_DEFINITIONS["db2_sql"]
DB2_RULES = DB2["rules"]
SQLITE = LANGUAGE_DEFINITIONS["sqlite"]

# ==============================================================================
# TEST 1: PER-SIGNATURE POSITIVE/NEGATIVE COVERAGE
# ==============================================================================
_DB2_SQL_SIMPLE_CASES = [
    ("branch", "IF RATING = 1 THEN", "END IF;"),
    ("branch", "WHILE V_COUNTER < P_MAX DO", "END WHILE;"),
    ("branch", "REPEAT FETCH C1 INTO V_ID; UNTIL SQLCODE <> 0 END REPEAT;", None),
    ("branch", "CASE WHEN SALARY > 100000 THEN 'HIGH' ELSE 'LOW' END", "END CASE;"),
    ("branch", "FOR V AS SELECT ID FROM T DO", "SELECT 1 FROM T FOR UPDATE;"),
    ("args", "CREATE PROCEDURE MEDIAN_RESULT_SET (OUT medianSalary DOUBLE)", "CALL MEDIAN_RESULT_SET(V_OUT)"),
    ("args", "SELECT NAME FROM EMP WHERE ID = :HV_ID", None),
    ("structural_boundaries", "SELECT EMPNO FROM DSN8C10.EMP;", "X"),
    ("structural_boundaries", "FETCH FIRST 10 ROWS ONLY", None),
    ("func_start", "CREATE PROCEDURE DSN8.PGM1 (IN X INT) LANGUAGE SQL", "CALL DSN8.PGM1(1);"),
    ("func_start", 'CREATE OR REPLACE FUNCTION "Tax_Rate" (P DECIMAL(15,2))', "DROP FUNCTION TAX_RATE;"),
    ("func_start", "CREATE TRIGGER NEW_HIRE AFTER INSERT ON EMP", "CREATE TABLE EMP (X INT);"),
    ("class_start", "CREATE TABLE DSN8C10.EMP (EMPNO CHAR(6) NOT NULL)", "DECLARE GLOBAL TEMPORARY TABLE SESSION.T1 (X INT);"),
    ("class_start", "CREATE LARGE TABLESPACE DSN8S13E IN DSN8D13A", "ALTER TABLESPACE DSN8D13A.DSN8S13E BUFFERPOOL BP2;"),
    ("class_start", "CREATE VIEW DSN8C10.VDEPT AS SELECT DEPTNO FROM DSN8C10.DEPT", None),
    ("safety", "DECLARE EXIT HANDLER FOR SQLEXCEPTION SET RC = -1;", None),
    ("safety", "PRIMARY KEY (EMPNO)", None),
    ("safety", "BEGIN ATOMIC", None),
    ("safety_bypasses", "ALTER TABLE T1 ACTIVATE NOT LOGGED INITIALLY;", None),
    ("safety_bypasses", "SET INTEGRITY FOR T1 ALL IMMEDIATE UNCHECKED;", None),
    ("safety_bypasses", "GOTO FAIL_EXIT;", None),
    ("high_risk_execution", "EXECUTE IMMEDIATE V_DYNSQL;", None),
    ("high_risk_execution", "PREPARE S1 FROM :STMT_TEXT;", None),
    ("high_risk_execution", "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE T1');", None),
    ("high_risk_execution", "DROP TABLESPACE DSN8D13A.DSN8S13E;", "DROP TABLE DSN8C10.EMP;"),
    ("high_risk_execution", "SET CURRENT SQLID = 'SYSADM';", "SET V_ID = 1;"),
    ("io", "OPEN C1;", "CLOSE C1;"),
    ("io", "FETCH C1 INTO :HV_EMPNO;", "FETCH FIRST 5 ROWS ONLY"),
    ("io", "EXPORT TO result.csv OF DEL SELECT * FROM EMP", None),
    ("api", "CREATE VIEW DSN8C10.VEMP AS SELECT EMPNO FROM DSN8C10.EMP", "SELECT * FROM VEMP;"),
    ("api", "CREATE ALIAS PAYROLL FOR DSN8C10.EMP;", None),
    ("state_mutation", "UPDATE DSN8C10.EMP SET SALARY = SALARY * 1.05 WHERE EMPNO = '000010';", None),
    ("state_mutation", "INSERT INTO DSN8C10.DEPT VALUES ('E31', 'PUBLISHING');", None),
    ("state_mutation", "MERGE INTO ARCHIVE AR USING (SELECT * FROM EMP) NE ON AR.ID = NE.ID", None),
    ("state_mutation", "BEGIN\n  SET V_TOTAL = 0;", "SET CURRENT DEGREE = 'ANY';"),
    ("dead_code", "-- SELECT COUNT(*) FROM DSN8C10.EMP;", "-- the employee table"),
    ("dead_code", "/* UPDATE EMP SET SALARY = 0; */", "/* salary rules */"),
    ("doc", "-- @param P_EMPNO the employee number", "-- the employee number"),
    ("doc", "/** Computes the median salary. */", None),
    ("test", "EXPLAIN PLAN SET QUERYNO = 13 FOR SELECT * FROM EMP;", None),
    ("test", "SET CURRENT EXPLAIN MODE = YES;", None),
    ("concurrency", "SELECT * FROM EMP WITH UR;", None),
    ("concurrency", "SELECT * FROM T1 SKIP LOCKED DATA;", None),
    ("globals", "SET V_WHO = SESSION_USER;", None),
    ("globals", "SELECT NAME FROM SYSIBM.SYSTABLES WHERE CREATOR = 'DSN8C10';", None),
    ("globals", "CREATE VARIABLE SCHEMA1.GV_COUNTER INTEGER DEFAULT 0;", None),
    ("decorators", "SELECT * FROM EMP OPTIMIZE FOR 10 ROWS;", None),
    ("decorators", "QUERYNO 13", None),
    ("comprehensions", "ROW_NUMBER() OVER (PARTITION BY DEPT ORDER BY SALARY DESC)", None),
    ("scientific", "SET V_STDDEV = SQRT(V_VARIANCE);", "SELECT SQRT_APPROX FROM T;"),
    ("reflection_metaprogramming", "GET DIAGNOSTICS V_COUNT = ROW_COUNT;", None),
    ("reflection_metaprogramming", "EMPNO_INT INTEGER GENERATED ALWAYS AS (INT(EMPNO))", None),
    ("import", "CONNECT TO SAMPLE;", "-- CONNECT TO SAMPLE;"),
    ("ownership", "-- Author: Joe Esquibel", "-- the author table"),
    ("planned_debt", "-- TODO: add the bonus column", "-- done"),
    ("fragile_debt", "-- HACK: mirrors DSNTEP2 behavior", "-- clean"),
    ("spec_exposure", "-- [SPEC-2511] mainframe modernization", "-- a note"),
    ("events", "CREATE TRIGGER AUDIT_TRG AFTER UPDATE ON EMP", None),
    ("memory_alloc", "USING STOGROUP DSN8G130 PRIQTY 20 SECQTY 20", None),
    ("memory_alloc", "BUFFERPOOL BP2", None),
    ("memory_alloc", "ALLOCATE C1 CURSOR FOR RESULT SET RS1;", None),
    ("telemetry", "RUNSTATS ON TABLE DSN8C10.EMP", None),
    ("telemetry", "SELECT * FROM TABLE(MON_GET_TABLE('', '', -1));", None),
    ("debug_prints", "CALL DBMS_OUTPUT.PUT_LINE('starting payroll run');", None),
    ("explicit_casts", "SELECT CAST(SALARY AS INTEGER) FROM EMP;", "SELECT SALARY FROM EMP;"),
    ("panics_and_aborts", "SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'bad input';", None),
    ("panics_and_aborts", "RESIGNAL;", None),
    ("thread_sleeps", "CALL DBMS_LOCK.SLEEP(5);", None),
    ("bitwise_ops", "SET V_FLAGS = BITAND(V_FLAGS, 240);", "WHERE A = 1 AND B = 2"),
    ("sync_locks", "LOCK TABLE DSN8C10.EMP IN EXCLUSIVE MODE;", None),
    ("sync_locks", "DECLARE C1 CURSOR WITH HOLD FOR SELECT 1 FROM T;", None),
    ("immutability_locks", "SELECT * FROM EMP FOR READ ONLY;", None),
    ("cleanup", "CLOSE C1;", None),
    ("cleanup", "DELETE FROM DSN8C10.EMP WHERE EMPNO = '000010';", None),
    ("cleanup", "DROP TABLE SESSION.SCRATCH;", None),
    ("encapsulation", "GRANT SELECT ON DSN8C10.EMP TO PUBLIC;", "-- GRANT nothing"),
    ("encapsulation", "REVOKE UPDATE ON DSN8C10.EMP FROM USER1;", None),
    ("encapsulation", "DECLARE GLOBAL TEMPORARY TABLE SESSION.T1 (X INT);", None),
    ("listeners", "CREATE TRIGGER TRG1 AFTER DELETE ON EMP FOR EACH ROW", "AFTER UPDATE, THE BATCH RUNS"),
    ("serialization_parsing", "SELECT JSON_VALUE(DOC, '$.name') FROM T;", None),
    ("serialization_parsing", "XMLSERIALIZE(CONTENT X AS CLOB)", None),
    ("regex_execution", "WHERE REGEXP_LIKE(NAME, '^[A-Z]{3}')", None),
    ("regex_execution", "WHERE NAME LIKE 'SMI%'", None),
    ("time_date_logic", "SET V_NOW = CURRENT TIMESTAMP;", "TS TIMESTAMP(6) NOT NULL"),
    ("time_date_logic", "SELECT TIMESTAMPDIFF(16, CHAR(TS2 - TS1)) FROM T;", None),
    ("ipc_rpc_bridges", "CREATE NICKNAME REMOTE_EMP FOR ORASERVER.HR.EMP;", None),
    ("ipc_rpc_bridges", "CALL DBMS_ALERT.SIGNAL('done', 'payload');", None),
]


@pytest.mark.parametrize("signature,positive,negative", _DB2_SQL_SIMPLE_CASES)
def test_db2_sql_signature_positive_and_negative(signature, positive, negative):
    pattern = DB2_RULES[signature]
    assert pattern is not None, f"db2_sql's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"db2_sql {signature!r} failed its documented positive case: {positive!r}"
    if negative is not None:
        assert not pattern.search(negative), f"db2_sql {signature!r} matched an excluded case: {negative!r}"


def test_every_non_none_rule_has_a_simple_case():
    covered = {sig for sig, _, _ in _DB2_SQL_SIMPLE_CASES}
    live = {k for k, v in DB2_RULES.items() if v is not None and not k.startswith("_")}
    assert live - covered == set(), f"rules with no positive/negative case: {sorted(live - covered)}"


# ==============================================================================
# TEST 2: SCHEMA COMPLETENESS (Rule 4 / Step 4 item 9)
# ==============================================================================
_BASELINE_KEYS = [
    "branch", "args", "structural_boundaries", "func_start", "class_start",
    "safety", "safety_bypasses", "high_risk_execution", "io", "api",
    "state_mutation", "dead_code", "doc", "test",
    "concurrency", "ui_framework", "closures", "globals", "decorators",
    "generics", "comprehensions", "scientific", "reflection_metaprogramming",
    "import", "_dependency_capture", "ownership",
    "planned_debt", "fragile_debt", "hardcoded_secrets", "spec_exposure",
    "ssr_boundaries", "events", "dependency_injection",
    "macros", "pointers", "memory_alloc", "inline_asm",
    "telemetry", "debug_prints", "explicit_casts", "panics_and_aborts",
    "thread_sleeps", "bitwise_ops", "sync_locks", "immutability_locks",
    "cleanup", "encapsulation", "listeners", "test_skip",
    "serialization_parsing", "regex_execution", "time_date_logic", "ipc_rpc_bridges",
]  # fmt: skip

# DB2 SQL has none of these: no UI surface, no anonymous callable, no parametric
# types, no IoC convention, no address syntax, no inline machine code, no rendering
# framework, no test-skip marker; the SPUFI `--#SET` directive lives on a comment
# line the code stream never carries (macros); hardcoded_secrets is a baseline rule
# in three languages only (the security lens covers the rest).
_EXPECTED_NONE_KEYS = {
    "ui_framework", "closures", "generics", "hardcoded_secrets", "dependency_injection",
    "ssr_boundaries", "macros", "pointers", "inline_asm", "test_skip",
}  # fmt: skip


def test_db2_sql_schema_completeness():
    missing = set(_BASELINE_KEYS) - set(DB2_RULES)
    assert not missing, f"db2_sql rules dict is missing baseline keys entirely (not even None): {missing}"
    extra = set(DB2_RULES) - set(_BASELINE_KEYS)
    assert extra == set(), f"unexpected non-baseline keys: {extra}"


def test_db2_sql_none_keys_are_the_intended_set():
    actual_none = {k for k, v in DB2_RULES.items() if v is None}
    assert actual_none == _EXPECTED_NONE_KEYS, f"unexpected None keys: {actual_none ^ _EXPECTED_NONE_KEYS}"


def test_db2_sql_registration():
    assert set(DB2["extensions"]) == {".sql", ".ddl", ".dml"}
    assert set(DB2["discriminators"]) == {".cbl", ".cob", ".cpy", ".jcl", ".bms", ".pli", ".pl1"}
    assert set(DB2["disqualifiers"]) == {".sqlite", ".sqlite3", ".db3", ".s3db", ".sl3"}
    assert DB2["shebangs"] == []
    # Positional, sqlite's exact #2866 position: the extracted units are Mode E's
    # statement buckets, and nothing reaches a statement by its extracted name --
    # `CALL SP1` invokes the database object, not the unit. Without this the
    # unreferenced_by_name census measures bucket-label collisions (a flat 0
    # against a 2.50 median on the rosetta corpus).
    assert DB2["invocation_model"] == "positional"


# ==============================================================================
# TEST 3: LEXICAL-FAMILY SANITY CHECK (Step 4 item 8), through the real Prism.
# Issue #2511 said "standard_block"; that family's delimiters are C's `//`+`/* */`
# and never strip `--` at all (sqlite's #621 defect, verbatim). multi_style_dash is
# the real family, and this test proves it against the actual stripper.
# ==============================================================================
def test_db2_sql_lexical_family_strips_both_comment_styles_and_keeps_strings():
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    assert DB2["lexical_family"] == "multi_style_dash"
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    sample = (
        "-- HEADER: this script never calls FETCH\n"
        "CREATE PROCEDURE P1 (IN X INT)\n"
        "LANGUAGE SQL\n"
        "BEGIN\n"
        "  DECLARE MSG VARCHAR(60) DEFAULT 'it''s -- not a comment /* either */';\n"
        "  /* multi-line\n     comment IF X THEN */ SET MSG = 'x';\n"
        "END;\n"
    )
    result = prism.split_streams(sample, "db2_sql")
    code, comments = result["code_stream"], result["comment_stream"]

    assert "never calls FETCH" in comments and "never calls FETCH" not in code
    assert "comment IF X THEN" in comments and "comment IF X THEN" not in code
    # a quoted `--` and a quoted `/* */` are data, not comments
    assert "it''s -- not a comment /* either */" in code
    assert "CREATE PROCEDURE P1 (IN X INT)" in code


# ==============================================================================
# TEST 4: SYMBOLIC-BOUNDARY AUDIT (Rule 9/10) -- `@ # $` are identifier characters,
# and call forms take zero / quoted first arguments.
# ==============================================================================
def test_db2_sql_call_forms_match_with_zero_and_quoted_first_arguments():
    assert DB2_RULES["debug_prints"].search("CALL DBMS_OUTPUT.PUT_LINE('x');")
    assert DB2_RULES["scientific"].search("SET R = RAND();")
    assert DB2_RULES["serialization_parsing"].search("JSON_OBJECT('a' VALUE 1)")
    assert DB2_RULES["high_risk_execution"].search("CALL SYSPROC.ADMIN_CMD('REORG TABLE T1')")


def test_db2_sql_delimited_and_national_identifiers():
    # Delimited (double-quoted) names capture with the quotes inside group 1
    # (sqlite's epic #813/#836 convention; detector.py strips the pair).
    m = DB2_RULES["class_start"].search('CREATE TABLE "Sales Order" (ID INT);')
    assert m and m.group(1) == '"Sales Order"'
    # National characters are ordinary identifier characters on z/OS.
    m = DB2_RULES["func_start"].search("CREATE PROCEDURE ACCT#DEPT.P$1 (IN X INT)")
    assert m and m.group(1) == "P$1"
    # A schema-qualified, quoted-schema name skips the qualifier.
    m = DB2_RULES["class_start"].search('CREATE TABLE "DSN8C10".EMP (EMPNO CHAR(6));')
    assert m and m.group(1) == "EMP"


# ==============================================================================
# TEST 5: RE.M COMPLETENESS AUDIT (Rule 13)
# ==============================================================================
def test_db2_sql_caret_anchored_rules_all_set_multiline_flag():
    caret = [k for k, p in DB2_RULES.items() if isinstance(p, re.Pattern) and re.search(r"(?<!\\)(?<!\[)\^", p.pattern)]
    assert caret, "expected ^-anchored rules (func_start/class_start/api/...) -- audit is a no-op otherwise"
    for key in caret:
        assert DB2_RULES[key].flags & re.M, f"db2_sql {key!r} uses ^ without re.M"


# ==============================================================================
# TEST 6: THE .sql / .ddl / .dml COLLISION WITH SQLITE (#2511's routing requirement)
# ==============================================================================
def test_db2_sql_and_sqlite_contest_the_same_extensions_and_the_lens_knows():
    from gitgalaxy.standards.language_standards import LENS_CONFIG

    shared = set(DB2["extensions"]) & set(SQLITE["extensions"])
    assert shared == {".sql", ".ddl", ".dml"}
    # Every shared extension must be declared contested, or _calibrate_lookup_maps'
    # registration-order overwrite silently hands it to whichever profile loads last
    # and Tier 1 locks it with no content or ecosystem check at all.
    missing = shared - LENS_CONFIG["COLLISION_FREQUENCIES"]
    assert not missing, f"contested extensions absent from COLLISION_FREQUENCIES: {missing}"


def test_db2_sql_internal_discriminator_separates_db2_from_sqlite_content():
    disc = DB2["internal_discriminator"]
    db2_shapes = [
        "--#SET TERMINATOR #",
        "CREATE LARGE TABLESPACE DSN8S13E IN DSN8D13A USING STOGROUP DSN8G130",
        "  BUFFERPOOL BP2",
        "  CCSID EBCDIC",
        "SET CURRENT SQLID = 'SYSADM';",
        "CREATE PROCEDURE P1 (IN X INT) LANGUAGE SQL BEGIN END",
        "WLM ENVIRONMENT DSNWLM1",
        "SELECT NAME FROM SYSIBM.SYSTABLES;",
        "DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET RC = 1;",
        "EXECUTE IMMEDIATE :STMT;",
    ]
    for shape in db2_shapes:
        assert disc.search(shape), f"internal_discriminator missed a DB2-only shape: {shape!r}"

    # A realistic SQLite script must NOT fingerprint as DB2 -- sqlite has no
    # internal_discriminator of its own, so a false positive here would steal
    # every plain .sql file at Tier 2.
    sqlite_script = (
        "PRAGMA foreign_keys = ON;\n"
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);\n"
        "CREATE INDEX idx_users_name ON users(name);\n"
        "INSERT INTO users VALUES (1, 'alice');\n"
        "SELECT * FROM users WHERE name LIKE 'a%';\n"
        ".import data.csv users\n"
    )
    assert not disc.search(sqlite_script), "internal_discriminator fired on a plain SQLite script"
    assert SQLITE.get("internal_discriminator") is None, (
        "sqlite grew its own internal_discriminator -- re-audit the Tier 2 loop order "
        "for the .sql collision before trusting this test"
    )


def test_db2_sql_ecosystem_gravity_prefers_the_mainframe_neighborhood():
    """
    The Tier 1.5 scoring loop's own arithmetic (language_lens.py: base_mass +
    discrim_mass * 2.0), evaluated on two census shapes: a mainframe repo (many
    cobol/jcl siblings) must hand .sql to db2_sql; a plain SQL repo must keep sqlite
    dominant (its own discriminators include .sql itself).
    """

    def score(profile, tally, ext=".sql"):
        support = [e for e in profile["extensions"] if e != ext]
        base = sum(tally.get(e, 0) for e in support) or tally.get(ext, 0)
        discrim = sum(tally.get(d, 0) for d in profile.get("discriminators", []))
        toxic = sum(tally.get(dq, 0) for dq in profile.get("disqualifiers", []))
        return 0.0 if toxic else base + discrim * 2.0

    mainframe = {".sql": 4, ".cbl": 30, ".jcl": 12, ".cpy": 18, ".bms": 3}
    s_db2, s_lite = score(DB2, mainframe), score(SQLITE, mainframe)
    assert s_db2 / (s_db2 + s_lite) >= 0.70, (s_db2, s_lite)

    plain_sql = {".sql": 9, ".db": 1}
    s_db2, s_lite = score(DB2, plain_sql), score(SQLITE, plain_sql)
    assert s_lite / (s_db2 + s_lite) >= 0.70, (s_db2, s_lite)

    sqlite_repo = {".sql": 3, ".sqlite3": 1, ".py": 40}
    assert score(DB2, sqlite_repo) == 0.0, "a .sqlite3 artifact must collapse the DB2 claim"


# ==============================================================================
# TEST 7: AMBIGUITY SWEEP (Rule 6) -- intended duals and enforced separations
# ==============================================================================
def test_db2_sql_intentional_double_classifications():
    duals = [
        ("CREATE TRIGGER TRG1 AFTER INSERT ON EMP", "func_start", "events"),
        ("CREATE VIEW V1 AS SELECT 1 FROM T", "class_start", "api"),
        ("SET CURRENT SQLID = 'SYSADM';", "high_risk_execution", "globals"),  # #2878 escape + #2858 register
        ("DROP TABLE SESSION.SCRATCH;", "safety_bypasses", "cleanup"),  # sqlite's structural-removal dual
        ("AFTER UPDATE ON EMP", "events", "listeners"),  # sqlite's trigger-timing dual
    ]
    for text, a, b in duals:
        assert DB2_RULES[a].search(text), f"{a} should own {text!r}"
        assert DB2_RULES[b].search(text), f"{b} should also own {text!r}"


def test_db2_sql_enforced_separations():
    # FETCH FIRST is a query clause (structural_boundaries'), never a cursor read.
    clause = "SELECT * FROM EMP FETCH FIRST 10 ROWS ONLY;"
    assert not DB2_RULES["io"].search(clause)
    assert DB2_RULES["structural_boundaries"].search("FETCH FIRST 10 ROWS ONLY")
    # The EXECUTE *privilege* in a GRANT list is encapsulation's, not dynamic SQL.
    grant = "GRANT EXECUTE ON PROCEDURE DSN8.PGM1 TO USER1;"
    assert DB2_RULES["encapsulation"].search(grant)
    assert not DB2_RULES["high_risk_execution"].search(grant)
    # DROP TABLE is cleanup's removal; DROP TABLESPACE is whole-store destruction.
    assert not DB2_RULES["high_risk_execution"].search("DROP TABLE DSN8C10.EMP;")
    assert DB2_RULES["high_risk_execution"].search("DROP TABLESPACE DSN8D13A.DSN8S13E;")
    # A column type's precision is not a clock call; the register is.
    assert not DB2_RULES["time_date_logic"].search("TS TIMESTAMP(6) NOT NULL")
    assert DB2_RULES["time_date_logic"].search("SET TS = CURRENT TIMESTAMP;")
    # CASE the expression counts once; END CASE the closer counts zero (#2822 C2).
    assert len(DB2_RULES["branch"].findall("CASE V WHEN 1 THEN 'A' END CASE;")) == 2  # CASE + WHEN
    assert len(DB2_RULES["branch"].findall("END IF;\nEND WHILE;\nEND REPEAT;")) == 0
    # XMLCAST is explicit_casts' alone; the JSON/XML builders are serialization's.
    xml = "XMLCAST(X AS VARCHAR(10))"
    assert DB2_RULES["explicit_casts"].search(xml) and not DB2_RULES["serialization_parsing"].search(xml)
    # SQL PL's variable SET is one write; a special-register SET is globals' side.
    assert not DB2_RULES["state_mutation"].search("BEGIN\n SET CURRENT DEGREE = 'ANY';")


def test_db2_sql_one_statement_is_one_hit():
    # A MERGE with a clause-internal `WHEN MATCHED THEN UPDATE SET` is ONE write.
    merge = (
        "MERGE INTO ARCHIVE AR USING (SELECT ID, SALARY FROM EMP) NE\n"
        "  ON AR.ID = NE.ID\n"
        "  WHEN MATCHED THEN\n"
        "    UPDATE SET AR.SALARY = NE.SALARY\n"
        "  WHEN NOT MATCHED THEN\n"
        "    INSERT (ID, SALARY) VALUES (NE.ID, NE.SALARY);"
    )
    assert len(DB2_RULES["state_mutation"].findall(merge)) == 1
    # An UPDATE whose SET clause wraps to its own line is still ONE write.
    update = "UPDATE DSN8C10.EMP\n  SET SALARY = SALARY * 1.05,\n      BONUS = 500\n  WHERE EMPNO = '000010';"
    assert len(DB2_RULES["state_mutation"].findall(update)) == 1
    # Three SQL PL assignments after statement starts are three writes.
    block = "BEGIN\n  SET A = 1;\n  SET B = 2; SET C = 3;\nEND"
    assert len(DB2_RULES["state_mutation"].findall(block)) == 3


# ==============================================================================
# TEST 8: THE REAL EXTRACTOR -- Mode E terminator cleaving via the "sql" alias,
# named classes via the allowlist (#1264's shape)
# ==============================================================================
def test_db2_sql_slices_through_mode_e_and_names_its_classes():
    from gitgalaxy.core.detector import StructuralExtractor

    program = (
        "CREATE PROCEDURE HR.RAISE_PAY (IN P_ID INTEGER, IN P_PCT DECIMAL(5,2))\n"
        "LANGUAGE SQL\n"
        "BEGIN\n"
        "  UPDATE HR.EMP SET SALARY = SALARY * (1 + P_PCT / 100) WHERE ID = P_ID;\n"
        "END;\n"
        "\n"
        'CREATE TABLE "DSN8C10".EMP (ID INTEGER NOT NULL, SALARY DECIMAL(15,2)) IN DB1.TS1;\n'
        "\n"
        "CREATE VIEW HR.V_EMP AS SELECT ID FROM HR.EMP;\n"
    )
    result = StructuralExtractor("db2_sql", LANGUAGE_DEFINITIONS).splice(program, "")
    # Mode E's statement buckets (#2792's CREATE_Statement/Declarative_Block shape).
    assert any(f["name"] == "CREATE_Statement" for f in result["functions"])
    # The named-class allowlist reuses class_start's capture, quotes stripped.
    assert {c["name"] for c in result["classes"]} == {"EMP", "V_EMP"}


def test_db2_sql_is_in_the_sql_alias_and_named_class_allowlist():
    import inspect

    from gitgalaxy.core import detector

    assert "db2_sql" in detector._CLASS_START_NAMED_EXTRACTION_LANGS
    assert detector.ScopeParsingRegistry.get_mode("db2_sql") == "mode_e"
    assert detector.ScopeParsingRegistry.get_mode("db2_sql") == detector.ScopeParsingRegistry.get_mode("sqlite")
    source = inspect.getsource(detector)
    assert '"db2_sql": "sql",' in source


# ==============================================================================
# TEST 9: REDOS ADVERSARIAL SWEEP (Rule 5/14) -- "never closes" payloads. The
# harness scales each payload geometrically and fails on super-linear growth;
# n starts small because Rule 14's adjacent-quantifier shape detonates early.
# ==============================================================================
_N = 200000


@pytest.mark.parametrize(
    "signature,payload",
    [
        ("args", "CREATE PROCEDURE P1 (" + "IN A INT," * (_N // 9)),
        ("args", "PROCEDURE P1 " + " " * _N),
        ("args", "FUNCTION F1 (" + "(" * _N),
        ("func_start", "CREATE PROCEDURE " + " " * _N),
        ("func_start", "CREATE " + "OR REPLACE " * (_N // 11)),
        ("func_start", 'CREATE PROCEDURE "' + "A" * _N),
        ("class_start", "CREATE TABLE IF NOT EXISTS " + " " * _N),
        ("class_start", "CREATE TABLE " + "A." * (_N // 2)),
        ("state_mutation", "BEGIN" + " " * _N),
        ("state_mutation", ";" + " SET A" * (_N // 6)),
        ("state_mutation", "UPDATE " + "A" * _N),
        ("io", "OPEN " + "A" * _N),
        ("io", "FETCH" + " " * _N),
        ("high_risk_execution", "PREPARE " + "A" * _N),
        ("high_risk_execution", "TRUNCATE TABLE " + '"' + "A" * _N),
        ("explicit_casts", "CAST(" + "A" * _N),
        ("explicit_casts", "CAST(" + "(A)" * (_N // 3)),
        ("explicit_casts", "CAST(" + " AS " * (_N // 4)),
        ("comprehensions", "OVER (" + "(" * _N),
        ("comprehensions", "OVER (" + "(A)" * (_N // 3)),
        ("globals", "SYSIBM." + "A" * _N),
        ("memory_alloc", "ALLOCATE " + "A" * _N),
        ("memory_alloc", "BUFFERPOOL " + "A" * _N),
        ("cleanup", "CLOSE " + "A" * _N),
        ("encapsulation", "GRANT " + "A" * _N),
        ("import", "CONNECT TO " + "A" * _N),
        ("_dependency_capture", "CONNECT TO " + "A" * _N),
        ("ownership", "-- Author:" + " " * _N),
        ("spec_exposure", "--[SPEC-" + "1" * _N),
        ("dead_code", "-- SELECT " + "A" * _N),
        ("doc", "--@param " + "A" * _N),
        ("decorators", "OPTIMIZE FOR " + "1" * _N),
        ("branch", "FOR " + "A" * _N),
        ("telemetry", "MON_GET_" + "A" * _N),
        ("time_date_logic", "CURRENT " + " " * _N),
        ("ipc_rpc_bridges", "DBMS_PIPE." + "A" * _N),
    ],
    ids=lambda v: v if len(v) <= 30 else f"{v[:12].strip()}...x{len(v)}",
)
def test_db2_sql_redos_immunity(signature, payload):
    assert_redos_immune(DB2_RULES[signature], payload, timeout_sec=3.0)


# ==============================================================================
# TEST 10: THE #2511 DEVIATION LEDGER -- the two places this profile deliberately
# diverges from the issue text, each because a stated contract owns the construct.
# ==============================================================================
def test_db2_sql_close_is_cleanups_not_ios():
    # #2841 C2: releasing a resource is cleanup's. The issue's io list said
    # FETCH/OPEN/CLOSE; CLOSE lands in cleanup instead, OPEN/FETCH stay io's.
    assert DB2_RULES["cleanup"].search("CLOSE C1;")
    assert not DB2_RULES["io"].search("CLOSE C1;")


def test_db2_sql_delete_is_cleanups_not_state_mutations():
    # #2843/#2888 and sqlite parity: DELETE FROM removes entries from a live store
    # (cleanup); the issue's state_mutation list said INSERT/UPDATE/DELETE/SET/MERGE.
    stmt = "DELETE FROM DSN8C10.EMP WHERE EMPNO = '000010';"
    assert DB2_RULES["cleanup"].search(stmt)
    assert not DB2_RULES["state_mutation"].search(stmt)
