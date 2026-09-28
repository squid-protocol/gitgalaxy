"""#3910: a declared PICTURE SYMBOL (CURRENCY SIGN IS 'INR ' WITH PICTURE SYMBOL 'I') is a floating currency
symbol when the schema and the Spring entity count a PICTURE's digits -- as the record layout already sizes it.
#3911: under DECIMAL-POINT IS COMMA a VALUE's comma is its decimal point (`VALUE 12345,67`), kept as written."""

import pytest

from gitgalaxy.core.mainframe_boundary import _cobol_records
from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import forge_schemas, parse_cobol_picture
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import parse_pic_precision
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import generate_java_entity, parse_pic_clause


@pytest.mark.parametrize(
    "pic, symbols, want",
    [
        ("UUU,UU9.99", ["U"], (7, 2)),  # 'EUR ' / U: 5 floating U are 4 digits + the sign, then 9.99
        ("III,II9.99", ["I"], (7, 2)),  # 'INR ' / I
        ("KK,KK,KK9.99", ["K"], (8, 2)),  # 'Rs' / K, lakh-grouped
        ("K(3),KK,KK9.99", ["K"], (9, 2)),
        ("kk,kk,kk9.99", ["K"], (8, 2)),  # the PICTURE's case does not matter
        ("U9.99", ["U"], (3, 2)),  # one symbol is a fixed insertion: no digit
        ("£££,££9.99", [], (7, 2)),  # a Unicode sign needs no declaration (#3857)
        ("$$$,$$9.99", ["I"], (7, 2)),
        ("ZZZ,ZZ9.99", ["U"], (8, 2)),  # the symbols do not change a PICTURE without them
    ],
)
def test_a_picture_symbol_is_a_floating_currency_symbol(pic, symbols, want):
    assert parse_pic_precision(pic, False, symbols) == want


def test_without_the_declaration_the_letter_is_no_digit():
    """The #3910 failure, which the declaration fixes: the letters were not counted at all."""
    assert parse_pic_precision("UUU,UU9.99", False) == (3, 2)


def test_the_schema_forge_reads_the_programs_picture_symbols(tmp_path):
    src = tmp_path / "INRPROG.cbl"
    src.write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. INRPROG.\n       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n       SPECIAL-NAMES.\n"
        "           CURRENCY SIGN IS 'INR ' WITH PICTURE SYMBOL 'I'\n"
        "           CURRENCY SIGN IS 'Rs' WITH PICTURE SYMBOL 'K'.\n"
        "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01 WS-REC.\n"
        "          05 WS-DUE PIC III,II9.99.\n          05 WS-LAKH PIC KK,KK,KK9.99.\n"
        "       PROCEDURE DIVISION.\n           STOP RUN.\n",
        encoding="utf-8",
    )
    out = forge_schemas(src)
    assert out is not None
    assert "WS_DUE                         DECIMAL(7, 2)" in out["sql"]
    assert "WS_LAKH                        DECIMAL(8, 2)" in out["sql"]
    assert out["json"]["currency_symbols"] == ["I", "K"]


def test_a_program_without_picture_symbols_keeps_its_schema_shape():
    assert parse_cobol_picture("$$$,$$9.99") == {"sql": "DECIMAL(7, 2)", "json": "number"}
    assert parse_cobol_picture("III,II9.99", False, None, ["I"]) == {"sql": "DECIMAL(7, 2)", "json": "number"}


def test_the_spring_entity_takes_the_schemas_picture_symbols():
    assert parse_pic_clause("PIC KK,KK,KK9.99", False, ["K"]) == {"precision": 8, "scale": 2}
    schema = {
        "title": "ACCT",
        "currency_symbols": ["U"],
        "properties": {"DUE": {"type": "number", "description": "Legacy PIC: UUU,UU9.99"}},
    }
    assert 'name = "DUE", precision = 7, scale = 2' in generate_java_entity(schema, "com.test")


# ---- #3911 ---------------------------------------------------------------------------------------
_DECIMAL_COMMA = "       SPECIAL-NAMES.\n           DECIMAL-POINT IS COMMA.\n"
_DATA = (
    "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
    "       01  WS-LIMIT   PIC 9(5)V99 VALUE 12345,67.\n"
    "       01  WS-RATE    PIC 9V9(4) VALUE IS 0,0125.\n"
    "       01  WS-COUNT   PIC 9(3) VALUE 7.\n"
    "       01  WS-CODE    PIC 9.\n"
    "           88 WS-LOW  VALUE 1, 2, 3.\n"
    "           88 WS-HIGH VALUE IS 7 , 8.\n"
    "       01  WS-TEXT    PIC X(5) VALUE '1,5'.\n"
    "       PROCEDURE DIVISION.\n           GOBACK.\n"
)


def _values(source: str, decimal_comma=None) -> dict:
    return {r["name"]: r["value"] for r in _cobol_records(source, decimal_comma)}


def test_a_decimal_comma_value_keeps_its_fraction_as_written():
    source = "       IDENTIFICATION DIVISION.\n       ENVIRONMENT DIVISION.\n" + _DECIMAL_COMMA + _DATA
    values = _values(source)
    assert values["WS-LIMIT"] == "12345,67"
    assert values["WS-RATE"] == "0,0125"
    assert values["WS-COUNT"] == "7"
    assert values["WS-LOW"] == "1"  # a comma and a space separate the 88's values
    assert values["WS-HIGH"] == "7"
    assert values["WS-TEXT"] == "1,5"
    assert _values(source, True) == values  # the caller's reading of SPECIAL-NAMES is the same


def test_without_decimal_point_is_comma_the_comma_separates():
    source = "       IDENTIFICATION DIVISION.\n" + _DATA.replace("12345,67", "12345.67")
    values = _values(source)
    assert values["WS-LIMIT"] == "12345.67"
    assert values["WS-RATE"] == "0"  # `0,0125` is two literals here, as COBOL reads it
    assert values["WS-LOW"] == "1"
