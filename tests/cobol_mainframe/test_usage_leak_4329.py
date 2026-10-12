"""#4329: the last DATA DIVISION entry's window runs into the PROCEDURE DIVISION, and its USAGE was
read from there: a `DISPLAY` verb, or a usage word inside a literal (`MOVE 'BINARY' TO ...`), which
made `PIC 9(4)` a 2-byte binary item. A usage is read only from the entry's own text (up to its
separator period, literals blanked), as NATIONAL already was (#3816)."""

from gitgalaxy.core.mainframe_boundary import extract_boundary

HEAD = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. USG.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
)


def _usage(src: str) -> dict:
    return {r["name"]: r["usage"] for r in extract_boundary("cobol", HEAD + src)["records"]}


def test_a_display_verb_is_not_the_last_items_usage():
    got = _usage(
        "       01  WS-COUNT               PIC 9(4) VALUE 0.\n"
        "       01  WS-MSG                 PIC X(40).\n"
        "       PROCEDURE DIVISION.\n       MAIN-PARA.\n"
        "           MOVE 'HELLO' TO WS-MSG\n           DISPLAY WS-MSG\n           GOBACK.\n"
    )
    assert got == {"WS-COUNT": None, "WS-MSG": None}


def test_a_usage_word_in_a_procedure_literal_is_not_a_usage():
    got = _usage(
        "       01  WS-MODE                PIC X(8).\n"
        "       01  WS-LEN                 PIC 9(4).\n"
        "       PROCEDURE DIVISION.\n       MAIN-PARA.\n"
        "           MOVE 'BINARY' TO WS-MODE\n           MOVE 12 TO WS-LEN\n           GOBACK.\n"
    )
    assert got["WS-LEN"] is None


def test_a_group_before_a_copy_takes_no_usage_from_the_procedure():
    # estate-crucible ACCTAUD.cbl:9 -- `01 LK-UPD-CONTROL.` then `COPY UPDCTL.`, last in the LINKAGE SECTION
    got = _usage(
        "       LINKAGE SECTION.\n       01  LK-UPD-CONTROL.\n           COPY UPDCTL.\n"
        "       PROCEDURE DIVISION USING LK-UPD-CONTROL.\n           DISPLAY 'AUDIT'\n           GOBACK.\n"
    )
    assert got == {"LK-UPD-CONTROL": None}


def test_the_entrys_own_usage_is_still_read():
    got = _usage(
        "       01  WS-A PIC S9(4) COMP.\n"
        "       01  WS-B PIC S9(7) USAGE IS\n               PACKED-DECIMAL.\n"
        "       01  WS-C PIC 9(4) BINARY.\n"
        "       PROCEDURE DIVISION.\n           DISPLAY WS-A\n           GOBACK.\n"
    )
    assert got == {"WS-A": "COMP", "WS-B": "PACKED-DECIMAL", "WS-C": "BINARY"}
