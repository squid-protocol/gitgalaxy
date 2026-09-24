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


# ==============================================================================
# #3348: every record field the pinned corpora hold (3,853/3,853 after this fix)
# ==============================================================================
def test_forge_schemas_reads_whole_entries(tmp_path):
    """Each shape the line reader lost, from CBSA / CardDemo / zopeneditor:
    an edited picture on an 01 (`PIC +9(10).99`), REDEFINES before PIC, a PIC on
    the next line, a sequence-numbered line, zopeneditor's `R2` change marker,
    and a line that is only a sequence number (it used to swallow the entry)."""
    cpy = tmp_path / "PROG.cbl"
    cpy.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PROG.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 ACTUAL-BALANCE-DISPLAY       PIC +9(10).99.\n"
        "       01 ACCOUNT-KY2                  PIC 9(16).\n"
        "       01 ACCOUNT-KY2-BYTES REDEFINES ACCOUNT-KY2 PIC X(16).\n"
        "       01 WS-RANGES.\n"
        "          07 WS-CUSTOMER-RANGE-BOTTOM\n"
        "                                       PIC 9(10) VALUE 1.\n"
        "009300\n"
        "009800   05 WS-INPUT-FLAG              PIC X(1).\n"
        "R2      05 NUM-PRE-CUSTOMERS          PIC S9(9) COMP-3 VALUE +0.\n"
        "      *  05 COMMENTED-OUT                PIC X.\n"
        "          05 FILLER                     PIC X(4).\n"
        "          05 WS-MSG PIC X(20) VALUE 'A. B'.\n"
        "             88 MSG-OK VALUE 'Y'.\n"
        "       PROCEDURE DIVISION.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    props = forge_module.forge_schemas(cpy)["json"]["properties"]
    assert set(props) == {
        "ACTUAL_BALANCE_DISPLAY",
        "ACCOUNT_KY2",
        "ACCOUNT_KY2_BYTES",
        "WS_CUSTOMER_RANGE_BOTTOM",
        "WS_INPUT_FLAG",
        "NUM_PRE_CUSTOMERS",
        "WS_MSG",
    }
    assert props["ACTUAL_BALANCE_DISPLAY"]["description"] == "Legacy PIC: +9(10).99"
