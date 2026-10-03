"""#4037: a COBOL item or record named CURRENT-DATE, USER, ORDER, KEY or YEAR became a column or table of that
name, and the database refused the DDL (H2: "expected identifier"), so the table was never created. A reserved
name is now quoted in the annotation; every other name is unchanged."""

from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import SQL_RESERVED, sql_name
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import generate_java_entity


def test_reserved_names_are_quoted_and_others_are_not():
    assert sql_name("CURRENT_DATE") == '\\"CURRENT_DATE\\"'  # inside a Java string literal
    assert sql_name("order") == '\\"order\\"'
    assert sql_name("CURRENT_YYDDD") == "CURRENT_YYDDD"
    assert sql_name("ACCT_ID") == "ACCT_ID"
    # the issue's words, and H2 2.x keywords COBOL data names often take
    assert {"CURRENT_DATE", "USER", "ORDER", "KEY", "VALUE", "YEAR", "MONTH", "DAY"} <= SQL_RESERVED


def test_the_entity_quotes_a_reserved_column_and_table():
    schema = {
        "title": "ORDER",
        "properties": {
            "CURRENT_DATE": {"type": "integer", "description": "PIC 9(8)"},
            "USER": {"type": "string", "description": "PIC X(8)"},
            "CURRENT_YYDDD": {"type": "integer", "description": "PIC 9(5)"},
        },
    }
    java = generate_java_entity(schema, "com.test")
    assert '@Column(name = "\\"CURRENT_DATE\\"")' in java
    assert '@Column(name = "\\"USER\\"", length = 8)' in java
    assert '@Column(name = "CURRENT_YYDDD")' in java  # not reserved: unchanged
    assert '@Table(name = "\\"ORDER\\"")' in java
