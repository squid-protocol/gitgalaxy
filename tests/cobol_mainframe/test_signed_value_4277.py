"""#4277: a numeric VALUE literal may open with its sign. `_VALUE_CLAUSE` could not start a
bareword with `+` / `-`, so `VALUE +0` / `VALUE -1` read no value at all (GenApp
lgicdb01.cbl:35 `01 WS-ABSTIME PIC S9(8) COMP VALUE +0.`; 132 items in the det-port estates).
A sign only counts in front of a digit (or a decimal point and a digit): `VALUE - 1` and a
quoted `'-'` are unchanged."""

from gitgalaxy.core.mainframe_boundary import extract_boundary

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
)


def _values(src: str) -> dict:
    return {r["name"]: r["value"] for r in extract_boundary("cobol", src)["records"]}


def test_signed_numeric_values_are_read():
    got = _values(
        PROGRAM + "       01  WS-ABSTIME                  PIC S9(8) COMP VALUE +0.\n"
        "       01  WS-NEG                      PIC S9(4) COMP VALUE -1.\n"
        "       01  WS-DEC                      PIC S9V99 VALUE IS -12.5.\n"
        "       01  WS-POINT                    PIC SV99 VALUE +.5.\n"
        "       01  WS-SPLIT                    PIC S9(4)\n"
        "                                       VALUE -42.\n"
    )
    assert (got["WS-ABSTIME"], got["WS-NEG"], got["WS-DEC"], got["WS-POINT"], got["WS-SPLIT"]) == (
        "+0",
        "-1",
        "-12.5",
        "+.5",
        "-42",
    )


def test_a_sign_not_before_a_digit_is_not_a_value():
    got = _values(PROGRAM + "       01  WS-DASH PIC X VALUE '-'.\n       01  WS-ODD  PIC X VALUE - 1.\n")
    assert got["WS-DASH"] == "-"
    assert got["WS-ODD"] is None
