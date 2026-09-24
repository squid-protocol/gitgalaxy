"""#3491 part 2: PL/I units of work and handlers -- ON / REVERT / SIGNAL rows, and the
CICS SYNCPOINT / HANDLE / ABEND rows of a PL/I program. Shapes are navikt/DSF's. The
boundary reads the PRISM code stream (comments already removed): fixtures carry none."""

from gitgalaxy.core.mainframe_boundary import _pli_records, _pli_value_map, extract_boundary
from gitgalaxy.core.pli_on_units import pli_on_units

SOURCE = "\n".join(
    [
        "".ljust(72) + "00000390",  # a removed header comment leaves its sequence field
        "    ON ERROR SNAP BEGIN;",
        "       CALL FEIL;",
        "    END;",
        " R: PROC OPTIONS(MAIN);",
        "   ON ERROR SYSTEM;",
        "   ON ENDFILE (INFIL) EOF = '1'B;",
        "   ON KEY(F) CALL KEYFEIL;",
        "   ON CONDITION(MYCOND) GO TO UT;",
        "   ON ZERODIVIDE;",
        "   IF X THEN ON ERROR SYSTEM;",
        "   DCL ON_KEY BIT(1);",
        "   DCL STOP CHAR(4) INIT('0450'), FEIL BIT(1) INIT('0'B);",
        "   EXEC CICS HANDLE CONDITION NOTFND(IKKE_FUNNET) ERROR;",
        "   EXEC CICS ABEND ABCODE(STOP);",
        "   EXEC CICS ABEND ABCODE(FEIL);",
        "   EXEC CICS SYNCPOINT;",
        "   REVERT ERROR;",
        "   SIGNAL FINISH;",
    ]
)


def _rows(src: str) -> list[tuple]:
    return [
        (r["kind"], r["condition"], r["target"], r["target_kind"], r["attributes"], r["line"])
        for r in pli_on_units(src)
    ]


def test_on_units_by_what_they_do():
    assert _rows(SOURCE) == [
        ("ON_UNIT", "ERROR", None, "BLOCK", "SNAP", 2),  # after a removed comment block
        ("ON_UNIT", "ERROR", None, "SYSTEM", None, 6),
        ("ON_UNIT", "ENDFILE(INFIL)", None, "STATEMENT", None, 7),
        ("ON_UNIT", "KEY(F)", "KEYFEIL", "PROCEDURE", None, 8),
        ("ON_UNIT", "CONDITION(MYCOND)", "UT", "LABEL", None, 9),
        ("ON_UNIT", "ZERODIVIDE", None, "NULL", None, 10),  # a null on-unit swallows the condition
        ("ON_UNIT", "ERROR", None, "SYSTEM", None, 11),  # after THEN
        ("REVERT", "ERROR", None, None, None, 18),
        ("SIGNAL", "FINISH", None, None, None, 19),
    ]  # `DCL ON_KEY` is a data name, not a handler


def test_the_pli_dialect_carries_cics_and_pli_handler_rows():
    rows = extract_boundary("pli", SOURCE)["uow_handlers"]
    cics = [(r["kind"], r["condition"], r["target"], r["target_kind"]) for r in rows if r["source"] == "CICS"]
    assert cics == [
        ("HANDLE_CONDITION", "NOTFND", "IKKE_FUNNET", "LABEL"),
        ("HANDLE_CONDITION", "ERROR", None, "DEFAULT"),
        ("ABEND", "0450", None, None),  # a CHAR item's all-digit INIT is its value
        ("ABEND", "FEIL", None, None),  # a bit string is no value: the data name stays
        ("COMMIT", None, None, None),
    ]
    assert sum(1 for r in rows if r["source"] == "PLI") == 9


def test_value_map_keeps_character_digits_and_drops_bit_strings():
    values = _pli_value_map(
        _pli_records("DCL STOP CHAR(4) INIT('0450'), N FIXED BIN(15) INIT(7), B BIT(1) INIT('1'B);")
    )
    assert values == {"STOP": "0450"}
