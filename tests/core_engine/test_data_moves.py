"""
#3452: field-level data movement (core/data_moves.py) through `extract_boundary`
-- one source -> target row per MOVE / COMPUTE / arithmetic / STRING / UNSTRING /
INITIALIZE, operands as written -- and the #3452 record-parser fix: a level-number
line inside an unfinished entry (`88 X VALUES` + `1 THROUGH 12.`) is not an item.
"""

from gitgalaxy.core.mainframe_boundary import extract_boundary


def _program(*statements: str) -> str:
    head = [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. MOVES.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
        "       01 WS-A PIC X(4).",
        "       PROCEDURE DIVISION.",
    ]
    return "\n".join(head + [f"           {s}" for s in statements]) + "\n"


def _rows(src: str) -> list[tuple]:
    out = []
    for r in extract_boundary("cobol", src)["data_moves"]:
        src_text = (r["source"] or "-") + ("(:)" if r["source_refmod"] else "")
        tgt = r["target"] + ("(:)" if r["target_refmod"] else "")
        out.append((r["line"], r["verb"] + (" CORR" if r["corresponding"] else ""), src_text, r["source_kind"], tgt))
    return out


def test_move_forms():
    src = _program(
        "MOVE WS-A TO WS-B WS-C (I).",
        "MOVE 'FAILED TO READ' TO ERR-MSG OF ERR-AREA.",
        "MOVE SPACES TO WS-D  MOVE ALL '9' TO WS-E.",
        "MOVE CORRESPONDING IN-REC TO OUT-REC.",
        "MOVE DFHCOMMAREA(1:EIBCALEN) TO WS-COMM(3:10).",
        "MOVE FUNCTION CURRENT-DATE TO WS-TS. MOVE LENGTH OF WS-A TO WS-L.",
    )
    assert _rows(src) == [
        (7, "MOVE", "WS-A", "item", "WS-B"),
        (7, "MOVE", "WS-A", "item", "WS-C"),  # a subscript is not a reference modification
        (8, "MOVE", "'FAILED TO READ'", "literal", "ERR-MSG OF ERR-AREA"),
        (9, "MOVE", "SPACES", "figurative", "WS-D"),
        (9, "MOVE", "ALL '9'", "figurative", "WS-E"),
        (10, "MOVE CORR", "IN-REC", "item", "OUT-REC"),
        (11, "MOVE", "DFHCOMMAREA(:)", "item", "WS-COMM(:)"),
        (12, "MOVE", "FUNCTION CURRENT-DATE", "function", "WS-TS"),
        (12, "MOVE", "LENGTH OF WS-A", "length", "WS-L"),
    ]


def test_arithmetic_string_unstring_initialize():
    src = _program(
        "COMPUTE WS-T ROUNDED = WS-A * FUNCTION NUMVAL(WS-B) + 1",
        "   ON SIZE ERROR MOVE 1 TO WS-ERR END-COMPUTE.",
        "ADD WS-A WS-B TO WS-T.",
        "SUBTRACT WS-A FROM WS-B GIVING WS-C.",
        "DIVIDE WS-A INTO WS-B GIVING WS-Q REMAINDER WS-R.",
        "STRING WS-A DELIMITED BY SPACE ' / ' DELIMITED BY SIZE",
        "   INTO WS-MSG WITH POINTER WS-P END-STRING.",
        "UNSTRING WS-LINE DELIMITED BY ',' INTO WS-X COUNT IN WS-N",
        "   WS-Y TALLYING IN WS-T.",
        "INITIALIZE WS-REC WS-TAB REPLACING NUMERIC DATA BY 0.",
    )
    assert _rows(src) == [
        (7, "COMPUTE", "WS-A", "item", "WS-T"),
        (7, "COMPUTE", "WS-B", "item", "WS-T"),  # a FUNCTION's arguments feed it
        (8, "MOVE", "1", "literal", "WS-ERR"),
        (9, "ADD", "WS-A", "item", "WS-T"),
        (9, "ADD", "WS-B", "item", "WS-T"),
        (10, "SUBTRACT", "WS-A", "item", "WS-C"),
        (10, "SUBTRACT", "WS-B", "item", "WS-C"),
        (11, "DIVIDE", "WS-A", "item", "WS-Q"),
        (11, "DIVIDE", "WS-B", "item", "WS-Q"),
        (11, "DIVIDE", "WS-A", "item", "WS-R"),
        (11, "DIVIDE", "WS-B", "item", "WS-R"),
        (12, "STRING", "WS-A", "item", "WS-MSG"),  # delimiters and the pointer are control
        (12, "STRING", "' / '", "literal", "WS-MSG"),
        (14, "UNSTRING", "WS-LINE", "item", "WS-X"),  # COUNT IN / TALLYING are control
        (14, "UNSTRING", "WS-LINE", "item", "WS-Y"),
        (16, "INITIALIZE", "-", None, "WS-REC"),
        (16, "INITIALIZE", "-", None, "WS-TAB"),
    ]


def test_what_is_not_a_row():
    src = _program(
        "EXEC SQL SELECT A INTO :WS-A FROM T END-EXEC.",
        "READ F INVALID KEY MOVE 4 TO WS-RC NOT INVALID KEY CONTINUE END-READ.",
        "MOVE WS-A TO".ljust(61) + "12345678",  # cols 73-80 sequence tag
        "   WS-B.",
    )
    src += "      *    MOVE WS-A TO WS-COMMENTED.\n"
    src += "      D    MOVE WS-A TO WS-DEBUG.\n"
    assert _rows(src) == [(8, "MOVE", "4", "literal", "WS-RC"), (9, "MOVE", "WS-A", "item", "WS-B")]


def test_a_procedure_copybook_and_pseudo_text():
    # No PROCEDURE DIVISION header: a member of procedure statements is read whole;
    # pseudo-text awaiting COPY REPLACING is not an operand.
    src = "           MOVE WS-A TO WS-B.\n           MOVE DFHRED TO\n                (SCRNVAR2)C OF (MAPNAME3)O\n"
    assert _rows(src) == [(1, "MOVE", "WS-A", "item", "WS-B")]


def test_a_value_continuation_line_is_not_an_item():
    src = "\n".join(
        [
            "           10 WS-DATE.",
            "              20 WS-MM                   PIC X(2).",
            "                 88 WS-VALID-MONTH       VALUES",
            "                                         1 THROUGH 12.",
            "              20 WS-DD                   PIC X(2).",
        ]
    )
    records = extract_boundary("cobol", src)["records"]
    assert [(r["level"], r["name"], r["parent_ordinal"]) for r in records] == [
        (10, "WS-DATE", None),
        (20, "WS-MM", 0),
        (88, "WS-VALID-MONTH", 1),
        (20, "WS-DD", 0),
    ]


def test_file_io_verbs_move_whole_records():
    # #3492: READ / RETURN INTO, WRITE / REWRITE / RELEASE FROM, ACCEPT [FROM].
    src = _program(
        "READ ACCT-FILE NEXT RECORD INTO WS-ACCT",
        "    AT END MOVE 'Y' TO WS-EOF",
        "END-READ.",
        "READ XREF-FILE KEY IS WS-KEY INVALID KEY MOVE 1 TO WS-RC.",
        "WRITE OUT-REC FROM WS-LINE AFTER ADVANCING 1.",
        "WRITE OUT-REC.",
        "REWRITE ACCT-REC FROM WS-ACCT.",
        "RELEASE SORT-REC FROM WS-ACCT.",
        "RETURN SORT-FILE INTO WS-SORTED AT END CONTINUE.",
        "ACCEPT WS-DATE FROM DATE YYYYMMDD.",
        "ACCEPT WS-PARM.",
    )
    assert _rows(src) == [
        (7, "READ", "ACCT-FILE", "file", "WS-ACCT"),
        (8, "MOVE", "'Y'", "literal", "WS-EOF"),
        (10, "MOVE", "1", "literal", "WS-RC"),  # no INTO: the FD record is the buffer, no move
        (11, "WRITE", "WS-LINE", "item", "OUT-REC"),
        (13, "REWRITE", "WS-ACCT", "item", "ACCT-REC"),
        (14, "RELEASE", "WS-ACCT", "item", "SORT-REC"),
        (15, "RETURN", "SORT-FILE", "file", "WS-SORTED"),
        (16, "ACCEPT", "DATE YYYYMMDD", "special", "WS-DATE"),
        (17, "ACCEPT", "SYSIN", "special", "WS-PARM"),
    ]
