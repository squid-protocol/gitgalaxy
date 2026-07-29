# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge as forge_module


# ==============================================================================
# TEST 1: The Data Type Translation Engine
# ==============================================================================
def test_parse_cobol_picture():
    """
    Proves the engine mathematically translates legacy COBOL PIC clauses into
    precise PostgreSQL boundaries and JSON REST types.
    """
    # 1. Strings / Text
    assert forge_module.parse_cobol_picture("X(50)") == {
        "sql": "VARCHAR(50)",
        "json": "string",
    }
    assert forge_module.parse_cobol_picture("XXX") == {
        "sql": "VARCHAR(3)",
        "json": "string",
    }

    # 2. Packed Decimals / Currency
    assert forge_module.parse_cobol_picture("9(5)V99") == {
        "sql": "DECIMAL(7, 2)",
        "json": "number",
    }
    assert forge_module.parse_cobol_picture("9(5)V9(2)") == {
        "sql": "DECIMAL(7, 2)",
        "json": "number",
    }
    assert forge_module.parse_cobol_picture("999.99") == {
        "sql": "DECIMAL(5, 2)",
        "json": "number",
    }

    # 3. Integers (Scaling based on byte boundaries)
    assert forge_module.parse_cobol_picture("9(4)") == {
        "sql": "SMALLINT",
        "json": "integer",
    }
    assert forge_module.parse_cobol_picture("9(7)") == {
        "sql": "INTEGER",
        "json": "integer",
    }
    assert forge_module.parse_cobol_picture("9(12)") == {
        "sql": "BIGINT",
        "json": "integer",
    }


# ==============================================================================
# TEST 2: The Bloat Cutter (IR Context Synergy)
# ==============================================================================
def test_forge_schemas_bloat_cutter(tmp_path):
    """
    Proves that the engine successfully ignores FILLER spaces, 88-level booleans,
    and intentionally drops variables proven to be dead memory by the IR RAM.
    """
    cpy = tmp_path / "MEMORY.cpy"
    cpy.write_text(
        """
        01 ROOT-TABLE.
           05 USED-VAR PIC X(10).
           05 DEAD-VAR PIC 9(4).
           05 FILLER   PIC X(5).
           88 FLAG-VAR VALUE 'Y'.
    """,
        encoding="utf-8",
    )

    # Pass "DEAD-VAR" into the IR ignore list
    schemas = forge_module.forge_schemas(cpy, ignore_vars={"DEAD-VAR"})
    sql_ddl = schemas["sql"]

    # Assertions
    assert "USED_VAR" in sql_ddl
    assert "DEAD_VAR" not in sql_ddl, "Bloat Cutter failed! Dead memory was migrated to the cloud."
    assert "FILLER" not in sql_ddl, "Engine hallucinated a FILLER column!"
    assert "FLAG_VAR" not in sql_ddl, "Engine hallucinated an 88-level column!"


# ==============================================================================
# TEST 3: The E2E Forge & Honesty Sensor
# ==============================================================================
def test_forge_schemas_e2e(tmp_path):
    """
    Proves the engine can slice the DATA DIVISION, generate a compliant PostgreSQL
    table, build a REST JSON schema, and explicitly flag dangerous legacy patterns.
    """
    cbl = tmp_path / "PGM.cbl"
    cbl.write_text(
        """
       DATA DIVISION.
       01 ACCOUNT-RECORD.
          05 ACCT-ID PIC 9(8) COMP-3.
          05 ACCT-NAME PIC X(20) OCCURS 1 TO 5 TIMES DEPENDING ON ACCT-COUNT.
       PROCEDURE DIVISION.
    """,
        encoding="utf-8",
    )

    schemas = forge_module.forge_schemas(cbl)
    sql_ddl = schemas["sql"]
    json_schema = schemas["json"]

    # 1. SQL DDL Verification
    assert "CREATE TABLE ACCOUNT_RECORD" in sql_ddl, "Failed to name the table from the 01-level!"
    assert "ACCT_ID" in sql_ddl and "ACCT_NAME" in sql_ddl

    # 2. Honesty Sensor Verification
    assert "COMP-3 (Packed Decimal)" in sql_ddl, "Failed to tag the legacy COMP-3 footprint!"
    assert "WARNING: OCCURS DEPENDING ON detected. Use JSONB." in sql_ddl, "Failed to trap the dynamic array!"

    # 3. JSON REST API Schema Verification
    assert json_schema["title"] == "ACCOUNT_RECORD"
    assert json_schema["properties"]["ACCT_ID"]["type"] == "integer"
    assert "Legacy PIC: 9(8)" in json_schema["properties"]["ACCT_ID"]["description"]
