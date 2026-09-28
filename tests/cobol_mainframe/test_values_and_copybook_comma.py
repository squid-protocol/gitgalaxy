"""#3943: the plural `VALUES [ARE]` is a VALUE clause; #3942: a copybook keeps `12345,67` as written.

A copybook has no SPECIAL-NAMES -- DECIMAL-POINT IS COMMA belongs to the program that COPYs it -- and a
separator comma is a comma followed by a space, so a comma between digits there can only be part of one
literal. A program that does not declare the decimal comma keeps its behaviour (the value stops at the comma).
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
)


def _values(src: str) -> dict:
    return {r["name"]: r["value"] for r in extract_boundary("cobol", src)["records"]}


def test_values_is_a_value_clause():
    got = _values(
        PROGRAM + "       01 A PIC 9.\n"
        "          88 A1 VALUES 1, 2, 3.\n"
        "          88 A2 VALUES ARE 'A' THRU 'F'.\n"
        "          88 A3 VALUE 7.\n"
        "          88 A4 VALUE IS 8.\n"
    )
    assert (got["A1"], got["A2"], got["A3"], got["A4"]) == ("1", "A", "7", "8")


def test_high_values_is_a_value_not_the_keyword():
    got = _values(PROGRAM + "       01 B PIC X VALUE HIGH-VALUES.\n       01 C PIC X VALUE HIGH-VALUE.\n")
    assert (got["B"], got["C"]) == ("HIGH-VALUES", "HIGH-VALUE")


def test_a_copybook_keeps_its_decimal_comma_literal():
    got = _values("       01 CPY-A PIC 9(5)V99 VALUE 12345,67.\n          88 CPY-L VALUES 1, 2, 3.\n")
    assert got["CPY-A"] == "12345,67"
    assert got["CPY-L"] == "1"  # comma + space still separates


def test_a_program_without_the_decimal_comma_is_unchanged():
    assert _values(PROGRAM + "       01 C PIC 9(5)V99 VALUE 12345,67.\n")["C"] == "12345"


def test_a_decimal_comma_program_with_values_lists():
    src = (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n       SPECIAL-NAMES.\n           DECIMAL-POINT IS COMMA.\n"
        "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01 Z PIC 9V9.\n          88 Z1 VALUES 1,5 2,5.\n"
    )
    assert _values(src)["Z1"] == "1,5"
