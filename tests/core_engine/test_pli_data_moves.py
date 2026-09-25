"""#3491 part 3: PL/I assignments as data-move rows (core/pli_data_moves.py). Shapes
are navikt/DSF's. The boundary reads the PRISM code stream (comments already gone)."""

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.pli_data_moves import pli_data_moves


def _rows(src: str) -> list[tuple]:
    return [
        (r["line"], r["source"], r["source_kind"], r["target"], r["corresponding"], r["target_refmod"])
        for r in pli_data_moves(src)
    ]


def test_assignment_forms():
    src = "\n".join(
        [
            "  L1: X = 'ABC';",
            "   A.B(I).C, D = E + F(J) * SUBSTR(G, K, 3);",
            "   IF A = B THEN Y = -1;",
            "   ELSE Z = DATE();",
            "   DO I = 1 TO 10;",
            "   SUBSTR(S, 1, 2) = T;",
            "   W = V, BY NAME;",
            "   N += M;",
            "   P->Q = R;",
            "   RC = DFHRESP(NORMAL);",
            "   CALL X(A);",
            "   %PLATFORM = 'MVS';",
        ]
    )
    assert _rows(src) == [
        (1, "'ABC'", "literal", "X", False, False),
        (2, "E", "item", "A.B.C", False, False),  # subscripts dropped, qualification kept
        (2, "F", "item", "A.B.C", False, False),  # F(J): an array element; J is no source
        (2, "G", "item", "A.B.C", False, False),  # SUBSTR is a built-in: its arguments are sources
        (2, "K", "item", "A.B.C", False, False),
        (2, "E", "item", "D", False, False),
        (2, "F", "item", "D", False, False),
        (2, "G", "item", "D", False, False),
        (2, "K", "item", "D", False, False),
        (3, "-1", "literal", "Y", False, False),  # after IF ... THEN; the IF's `=` is a comparison
        (4, "DATE", "function", "Z", False, False),
        (6, "T", "item", "S", False, True),  # a pseudo-variable target assigns S in part
        (7, "V", "item", "W", True, False),  # BY NAME
        (8, "N", "item", "N", False, False),  # compound: the target is a source too
        (8, "M", "item", "N", False, False),
        (9, "R", "item", "Q", False, False),  # P->Q: the based item
        (10, "DFHRESP(NORMAL)", "cics_constant", "RC", False, False),
    ]  # DO loop control, CALL and the % preprocessor statement move no data


def test_sequence_debris_does_not_hide_a_statement():
    # DSF: a removed comment leaves its sequence field ahead of the next statement,
    # and a field can be glued to the code before it (`...;00000390`).
    src = "\n".join(
        [
            " L230:" + " " * 66 + "00010500",
            "00010510",
            "   FEIL_VED_LABEL = '230';" + " " * 45 + "00010560",
            "   X = Y;00000390",
            "   B.C" + " " * 20 + "00001630",
            "      (1,I - 1)00001640",
            "   = Z;",
        ]
    )
    assert [(r[0], r[1], r[3]) for r in _rows(src)] == [
        (3, "'230'", "FEIL_VED_LABEL"),
        (4, "Y", "X"),
        (5, "Z", "B.C"),
    ]


def test_the_pli_dialect_carries_data_moves():
    rows = extract_boundary("pli", " R: PROC; X = Y; END R;")["data_moves"]
    assert [(r["verb"], r["source"], r["target"]) for r in rows] == [("ASSIGN", "Y", "X")]
