"""#4282: the OCCURS ... DEPENDING ON object keeps its qualifiers. A bare `BETA` can name a
different item than `BETA OF ALPHA` (cobol-check EXR001.CBL:5), so the qualified name is
recorded as written: upper-cased, whitespace (a line break included) collapsed to one space,
`OF` / `IN` kept -- the det translator's spelling."""

from gitgalaxy.core.mainframe_boundary import extract_boundary

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
    "       01 ALPHA.\n          05 BETA PIC 99.\n"
)


def _depending(src: str) -> dict:
    return {r["name"]: r["occurs_depending_on"] for r in extract_boundary("cobol", PROGRAM + src)["records"]}


def test_qualified_object_is_kept():
    got = _depending(
        "       01 T1.\n          05 E1 PIC X OCCURS 1 TO 9 DEPENDING ON BETA OF ALPHA.\n"
        "       01 T2.\n          05 E2 PIC X OCCURS 1 TO 9 DEPENDING ON beta in alpha.\n"
        "       01 T3.\n          05 E3 PIC X OCCURS 1 TO 9\n                DEPENDING ON BETA\n                OF ALPHA.\n"
        "       01 T4.\n          05 E4 PIC X OCCURS 1 TO 9 DEPENDING X OF Y IN Z.\n"
    )
    assert (got["E1"], got["E2"], got["E3"], got["E4"]) == (
        "BETA OF ALPHA",
        "BETA IN ALPHA",
        "BETA OF ALPHA",
        "X OF Y IN Z",
    )


def test_unqualified_object_and_following_clauses_are_unchanged():
    got = _depending(
        "       01 T5.\n          05 E5 PIC X OCCURS 1 TO 9 DEPENDING ON BETA.\n"
        "       01 T6.\n          05 E6 OCCURS 1 TO 9 DEPENDING ON BETA INDEXED BY IX.\n            10 F6 PIC X.\n"
    )
    assert (got["E5"], got["E6"]) == ("BETA", "BETA")


def test_redefines_target_on_the_next_line_4281():
    # #4281 (carddemo COTRTUPC.cbl:115-116): already fixed on main by #4300 -- the target used to
    # read the next line's sequence number `011600`, which no name pattern matches. Pinned here.
    src = (
        "011400     10  WS-EDIT-DATE-X                      PIC X(10).\n"
        "011500     10  WS-EDIT-DATE-9 REDEFINES\n"
        "011600         WS-EDIT-DATE-X                      PIC 9(10).\n"
    )
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    code = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(PROGRAM + src, "cobol")["code_stream"]
    records = {r["name"]: r for r in extract_boundary("cobol", code)["records"]}
    assert records["WS-EDIT-DATE-9"]["redefines"] == "WS-EDIT-DATE-X"
